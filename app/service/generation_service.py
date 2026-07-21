"""Create and complete Fast/Pro generation tasks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.commerce import (
    ALLOWED_ASPECT_RATIOS,
    CONCURRENT_JOB_LIMITS,
    PLAN_FREE,
    PLAN_VISITOR,
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
from app.models.asset import Asset
from app.models.base import new_id, utc_now
from app.models.enums import (
    AssetStatus,
    AssetType,
    AttemptStatus,
    FailureCode,
    GenerationProvider,
    PlanCode,
    PricingMode,
    RunningHubStatus,
    TaskStatus,
    TaskType,
    TransferStatus,
)
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.providers.runninghub import RunningHubClient
from app.providers.s3 import S3Storage
from app.repo.generation_repo import GenerationRepo
from app.schemas.generation import GenerationTaskResponse
from app.service.credit_service import CreditService
from app.service.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)

_CREATABLE_TASK_TYPES = frozenset({TaskType.FAST_IMAGE, TaskType.PRO_IMAGE})


class GenerationService:
    def __init__(
        self,
        generation_repo: GenerationRepo,
        credit_service: CreditService,
        entitlement_service: EntitlementService,
        settings: Settings,
        rh: RunningHubClient | None = None,
        s3: S3Storage | None = None,
    ) -> None:
        self._repo = generation_repo
        self._credits = credit_service
        self._entitlements = entitlement_service
        self._settings = settings
        self._rh = rh or RunningHubClient(settings)
        self._s3 = s3 or S3Storage(settings)

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
        task_type: TaskType | str,
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
        try:
            task_type = TaskType(task_type)
        except ValueError as exc:
            raise ValidationFailed("unsupported task_type") from exc
        if task_type not in _CREATABLE_TASK_TYPES:
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
            limit = CONCURRENT_JOB_LIMITS[PlanCode.VISITOR]
        if active >= limit:
            raise ConcurrentJobLimit()

        task_id = new_id()
        credits_reserved = 0
        reservation_id = None
        pricing: dict[str, Any]

        if task_type == TaskType.FAST_IMAGE:
            await self._entitlements.consume_fast_quota(
                user_id=user_id, visitor_id=visitor_id
            )
            pricing = {
                "mode": PricingMode.FREE_DAILY.value,
                "credits": 0,
                "plan": plan if user_id else PLAN_VISITOR.value,
            }
            input_params = self._rh.input_params_for_fast(aspect_ratio)
            app_id = RH_FAST_APP_ID
        else:
            if not user_id:
                raise AuthRequired("Login required for Pro image")
            pricing = {
                "mode": PricingMode.CREDITS.value,
                "credits": PRO_IMAGE_CREDITS,
                "plan": plan.value if isinstance(plan, PlanCode) else plan,
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
            status=TaskStatus.QUEUED,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            input_params=input_params,
            pricing_snapshot=pricing,
            credits_reserved=credits_reserved,
            credit_reservation_id=reservation_id,
            provider=GenerationProvider.RUNNINGHUB,
            provider_app_id=app_id,
            idempotency_key=idempotency_key,
            result_transfer_status=TransferStatus.PENDING,
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
        if task.status not in TaskStatus.submittable():
            return task

        task.status = TaskStatus.SUBMITTING
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.flush()

        if task.task_type == TaskType.FAST_IMAGE:
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
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

        provider_task_id = str(resp.get("taskId") or "")
        provider_status = str(resp.get("status") or RunningHubStatus.RUNNING.value)
        task.provider_task_id = provider_task_id or None
        task.provider_status = provider_status
        task.started_at = datetime.now(UTC)

        await self._repo.add_attempt(
            GenerationAttempt(
                id=new_id(),
                task_id=task.id,
                attempt_no=task.attempt_count,
                status=AttemptStatus.SUBMITTED,
                provider_task_id=provider_task_id or None,
                request_meta={"app_id": app_id, "nodes": nodes},
                response_meta=resp,
            )
        )

        # Immediate success (stub or fast complete)
        if provider_status == RunningHubStatus.SUCCESS and resp.get("results"):
            await self._complete_success(task, resp)
        else:
            task.status = TaskStatus.PROCESSING
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
        if task.status in TaskStatus.terminal():
            return task

        status = str(payload.get("status") or "")
        task.provider_status = status
        task.provider_usage = payload.get("usage")
        if status == RunningHubStatus.SUCCESS:
            await self._complete_success(task, payload)
        elif status == RunningHubStatus.FAILED:
            await self._fail_task(
                task,
                FailureCode.PROVIDER_FAILED,
                str(payload.get("errorMessage") or payload.get("failedReason") or "failed"),
            )
        await self._repo.session.flush()
        return task

    async def poll_provider(self, task_id: str) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound()
        # If worker never ran, submit on poll (dev-friendly)
        if task.status in TaskStatus.submittable():
            return await self.submit_to_provider(task_id)
        if not task.provider_task_id or task.status not in TaskStatus.pollable():
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
            first = results[0] if results else None
            if isinstance(first, dict):
                source_url = first.get("url")

        task.status = TaskStatus.SUCCEEDED
        task.completed_at = datetime.now(UTC)
        task.failure_code = None
        task.failure_detail = None

        if task.credits_reserved > 0:
            await self._credits.capture_reservation(task_id=task.id)

        await self._transfer_result(task, source_url=source_url or "")

    async def _transfer_result(self, task: GenerationTask, *, source_url: str) -> None:
        """Download RH temporary URL into private S3 and attach Asset row."""
        asset = Asset(
            id=new_id(),
            owner_user_id=task.user_id,
            visitor_id=task.visitor_id if not task.user_id else None,
            asset_type=AssetType.OUTPUT_IMAGE,
            source_url=source_url or None,
            status=AssetStatus.PENDING_TRANSFER,
        )
        self._repo.session.add(asset)
        await self._repo.session.flush()

        transfer = await self._s3.transfer_from_url(
            source_url=source_url,
            task_id=task.id,
            user_id=task.user_id,
            visitor_id=task.visitor_id,
        )

        if transfer.status == TransferStatus.SUCCEEDED and transfer.storage_key:
            asset.storage_key = transfer.storage_key
            asset.mime_type = transfer.mime_type
            asset.byte_size = transfer.byte_size
            asset.checksum_sha256 = transfer.checksum_sha256
            asset.status = AssetStatus.READY
            task.result_transfer_status = TransferStatus.SUCCEEDED
        elif transfer.status == TransferStatus.SKIPPED:
            asset.status = AssetStatus.PENDING_TRANSFER
            task.result_transfer_status = TransferStatus.SKIPPED
            logger.warning("S3 transfer skipped task=%s: %s", task.id, transfer.error)
        else:
            asset.status = AssetStatus.PENDING_TRANSFER
            task.result_transfer_status = TransferStatus.FAILED
            logger.warning(
                "S3 transfer failed task=%s: %s",
                task.id,
                transfer.error,
            )

        task.result_asset_id = asset.id
        await self._repo.session.flush()

    async def _fail_task(
        self, task: GenerationTask, code: FailureCode | str, detail: str
    ) -> None:
        task.status = TaskStatus.FAILED
        task.failure_code = str(code)
        task.failure_detail = detail[:2000]
        task.completed_at = datetime.now(UTC)

        if task.credits_reserved > 0:
            await self._credits.release_reservation(task_id=task.id)
        if task.task_type == TaskType.FAST_IMAGE:
            await self._entitlements.refund_fast_quota(
                user_id=task.user_id, visitor_id=task.visitor_id
            )

    async def to_public(self, task: GenerationTask) -> GenerationTaskResponse:
        result_urls = await self._result_urls_for_client(task)
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

    async def _result_urls_for_client(self, task: GenerationTask) -> list[str] | None:
        """Prefer short-lived S3 presigned URL; fall back to RH temporary URL."""
        if task.result_asset_id and task.result_transfer_status == TransferStatus.SUCCEEDED:
            asset = await self._repo.session.get(Asset, task.result_asset_id)
            if asset and asset.storage_key and asset.status == AssetStatus.READY:
                try:
                    url = await self._s3.presign_get(asset.storage_key)
                    return [url]
                except Exception:
                    logger.exception("presign failed asset=%s", asset.id)

        if task.provider_raw_result and isinstance(task.provider_raw_result, dict):
            results = task.provider_raw_result.get("results")
            if results:
                urls = [r.get("url") for r in results if isinstance(r, dict) and r.get("url")]
                return urls or None
        return None
