"""Create and complete Fast/Pro generation tasks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.commerce import (
    ALLOWED_ASPECT_RATIOS,
    CONCURRENT_JOB_LIMITS,
    PLAN_FREE,
    PRO_IMAGE_CREDITS,
    RH_FAST_APP_ID,
    RH_PRO_APP_ID,
)
from app.core.config import Settings
from app.core.errors import (
    AuthRequired,
    ConcurrentJobLimit,
    NotFound,
    ValidationFailed,
)
from app.models.anonymous_visitor import AnonymousVisitor
from app.models.base import new_id, utc_now
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.providers.runninghub import RunningHubClient, transfer_result_to_s3_stub
from app.repo.generation_repo import GenerationRepo
from app.schemas.generation import GenerationTaskResponse
from app.service.credit_service import CreditService
from app.service.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        generation_repo: GenerationRepo,
        credit_service: CreditService,
        entitlement_service: EntitlementService,
        settings: Settings,
        rh: RunningHubClient | None = None,
    ) -> None:
        self._repo = generation_repo
        self._credits = credit_service
        self._entitlements = entitlement_service
        self._settings = settings
        self._rh = rh or RunningHubClient(settings)

    async def _ensure_visitor(self, visitor_id: str | None) -> str | None:
        if not visitor_id:
            return None
        existing = await self._repo.session.get(AnonymousVisitor, visitor_id)
        if existing:
            existing.last_seen_at = utc_now()
            return existing.id
        visitor = AnonymousVisitor(id=visitor_id, last_seen_at=utc_now())
        self._repo.session.add(visitor)
        await self._repo.session.flush()
        return visitor.id

    async def create_task(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        task_type: str,
        prompt: str,
        aspect_ratio: str,
        idempotency_key: str,
    ) -> GenerationTask:
        prompt = (prompt or "").strip()
        if not prompt or len(prompt) > 2000:
            raise ValidationFailed("prompt must be 1–2000 characters")
        if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
            raise ValidationFailed(
                f"aspect_ratio must be one of {sorted(ALLOWED_ASPECT_RATIOS)}"
            )
        if task_type not in ("FAST_IMAGE", "PRO_IMAGE"):
            raise ValidationFailed("unsupported task_type")

        existing = await self._repo.get_by_idempotency(idempotency_key)
        if existing:
            return existing

        visitor_id = await self._ensure_visitor(visitor_id)

        # Concurrent limit
        plan = await self._entitlements.resolve_plan(user_id) if user_id else PLAN_FREE
        if user_id:
            active = await self._repo.count_active_for_user(user_id)
            limit = CONCURRENT_JOB_LIMITS.get(plan, 1)
        else:
            if not visitor_id:
                raise AuthRequired("Visitor or user required for Fast generation")
            active = await self._repo.count_active_for_visitor(visitor_id)
            limit = CONCURRENT_JOB_LIMITS["VISITOR"]
        if active >= limit:
            raise ConcurrentJobLimit()

        task_id = new_id()
        credits_reserved = 0
        reservation_id = None
        pricing: dict[str, Any]

        if task_type == "FAST_IMAGE":
            await self._entitlements.consume_fast_quota(
                user_id=user_id, visitor_id=visitor_id
            )
            pricing = {
                "mode": "free_daily",
                "credits": 0,
                "plan": plan if user_id else "VISITOR",
            }
            input_params = self._rh.input_params_for_fast(aspect_ratio)
            app_id = RH_FAST_APP_ID
        else:
            if not user_id:
                raise AuthRequired("Login required for Pro image")
            pricing = {
                "mode": "credits",
                "credits": PRO_IMAGE_CREDITS,
                "plan": plan,
            }
            reservation = await self._credits.reserve_for_task(
                user_id=user_id,
                task_id=task_id,
                amount=PRO_IMAGE_CREDITS,
                pricing_snapshot=pricing,
            )
            credits_reserved = PRO_IMAGE_CREDITS
            reservation_id = reservation.id
            input_params = self._rh.input_params_for_pro(aspect_ratio)
            app_id = RH_PRO_APP_ID

        task = GenerationTask(
            id=task_id,
            user_id=user_id,
            visitor_id=visitor_id,
            task_type=task_type,
            status="QUEUED",
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            input_params=input_params,
            pricing_snapshot=pricing,
            credits_reserved=credits_reserved,
            credit_reservation_id=reservation_id,
            provider="runninghub",
            provider_app_id=app_id,
            idempotency_key=idempotency_key,
            result_transfer_status="PENDING",
        )
        await self._repo.add(task)
        return task

    async def get_task(self, task_id: str, *, user_id: str | None) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound("Task not found")
        if user_id and task.user_id and task.user_id != user_id:
            raise NotFound("Task not found")
        return task

    async def submit_to_provider(self, task_id: str) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound()
        if task.status not in ("QUEUED", "CREATED"):
            return task

        task.status = "SUBMITTING"
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.flush()

        if task.task_type == "FAST_IMAGE":
            nodes = self._rh.build_fast_node_list(
                prompt=task.prompt, aspect_ratio=task.aspect_ratio
            )
            app_id = RH_FAST_APP_ID
        else:
            nodes = self._rh.build_pro_node_list(
                prompt=task.prompt, aspect_ratio=task.aspect_ratio
            )
            app_id = RH_PRO_APP_ID

        webhook_url = None
        if self._settings.public_api_base_url:
            base = self._settings.public_api_base_url.rstrip("/")
            webhook_url = f"{base}{self._settings.api_prefix}/v1/webhooks/generation/runninghub"

        try:
            resp = await self._rh.submit(
                app_id=app_id,
                node_info_list=nodes,
                webhook_url=webhook_url,
            )
        except Exception as exc:
            logger.exception("RH submit failed task=%s", task_id)
            await self._fail_task(task, "PROVIDER_SUBMIT_FAILED", str(exc))
            return task

        provider_task_id = str(resp.get("taskId") or "")
        provider_status = str(resp.get("status") or "RUNNING")
        task.provider_task_id = provider_task_id or None
        task.provider_status = provider_status
        task.started_at = datetime.now(UTC)

        await self._repo.add_attempt(
            GenerationAttempt(
                id=new_id(),
                task_id=task.id,
                attempt_no=task.attempt_count,
                status="submitted",
                provider_task_id=provider_task_id or None,
                request_meta={"app_id": app_id, "nodes": nodes},
                response_meta=resp,
            )
        )

        # Immediate success (stub or fast complete)
        if provider_status == "SUCCESS" and resp.get("results"):
            await self._complete_success(task, resp)
        else:
            task.status = "PROCESSING"
        await self._repo.session.flush()
        return task

    async def handle_provider_payload(self, payload: dict[str, Any]) -> GenerationTask | None:
        """Webhook or poll result body from RunningHub."""
        provider_task_id = str(payload.get("taskId") or "")
        if not provider_task_id:
            return None
        task = await self._repo.get_by_provider_task_id(provider_task_id)
        if task is None:
            logger.warning("No task for provider_task_id=%s", provider_task_id)
            return None
        if task.status in ("SUCCEEDED", "FAILED", "CANCELED", "REJECTED"):
            return task

        status = str(payload.get("status") or "")
        task.provider_status = status
        task.provider_usage = payload.get("usage")
        if status == "SUCCESS":
            await self._complete_success(task, payload)
        elif status == "FAILED":
            await self._fail_task(
                task,
                "PROVIDER_FAILED",
                str(payload.get("errorMessage") or payload.get("failedReason") or "failed"),
            )
        await self._repo.session.flush()
        return task

    async def poll_provider(self, task_id: str) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound()
        # If worker never ran, submit on poll (dev-friendly)
        if task.status in ("QUEUED", "CREATED"):
            return await self.submit_to_provider(task_id)
        if not task.provider_task_id or task.status not in ("PROCESSING", "SUBMITTING"):
            return task
        payload = await self._rh.query(task.provider_task_id)
        await self.handle_provider_payload(payload)
        refreshed = await self._repo.get(task_id)
        assert refreshed is not None
        return refreshed

    async def _complete_success(self, task: GenerationTask, payload: dict[str, Any]) -> None:
        task.provider_raw_result = payload
        results = payload.get("results") or []
        source_url = None
        if results and isinstance(results, list):
            source_url = results[0].get("url")

        transfer = await transfer_result_to_s3_stub(
            source_url=source_url or "",
            user_id=task.user_id,
            task_id=task.id,
        )
        task.result_transfer_status = transfer.get("status", "PENDING_TRANSFER")
        # Asset row can be created later when S3 lands; keep raw result for now

        if task.credits_reserved > 0:
            await self._credits.capture_reservation(task_id=task.id)

        task.status = "SUCCEEDED"
        task.completed_at = datetime.now(UTC)
        task.failure_code = None
        task.failure_detail = None

    async def _fail_task(self, task: GenerationTask, code: str, detail: str) -> None:
        task.status = "FAILED"
        task.failure_code = code
        task.failure_detail = detail[:2000]
        task.completed_at = datetime.now(UTC)

        if task.credits_reserved > 0:
            await self._credits.release_reservation(task_id=task.id)
        if task.task_type == "FAST_IMAGE":
            await self._entitlements.refund_fast_quota(
                user_id=task.user_id, visitor_id=task.visitor_id
            )

    def to_public(self, task: GenerationTask) -> GenerationTaskResponse:
        result_urls = None
        if task.provider_raw_result and isinstance(task.provider_raw_result, dict):
            results = task.provider_raw_result.get("results")
            if results:
                result_urls = [r.get("url") for r in results if r.get("url")]
        return GenerationTaskResponse(
            job_id=task.id,
            task_type=task.task_type,
            status=task.status,
            aspect_ratio=task.aspect_ratio,
            credits_reserved=task.credits_reserved,
            result_transfer_status=task.result_transfer_status,
            result_urls=result_urls,
            failure_code=task.failure_code,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )
