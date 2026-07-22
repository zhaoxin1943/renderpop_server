"""Create and complete Fast/Pro image and AI video generation tasks."""

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
    VIDEO_DEFAULT_ASPECT_RATIO,
    VIDEO_DEFAULT_LENGTH,
    VIDEO_DEFAULT_RESOLUTION,
    video_credits_from_pricing_config,
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
    PolloTaskStatus,
    PricingMode,
    RunningHubStatus,
    TaskStatus,
    TaskType,
    TransferStatus,
)
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.providers.pollo import PROVIDER_IMAGE_URL_EXPIRES, PolloClient
from app.providers.runninghub import RunningHubClient
from app.providers.s3 import S3Storage
from app.repo.generation_model_repo import GenerationModelRepo
from app.repo.generation_repo import GenerationRepo
from app.schemas.generation import GenerationQuoteResponse, GenerationTaskResponse
from app.service.credit_service import CreditService
from app.service.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)

_IMAGE_TASK_TYPES = frozenset({TaskType.FAST_IMAGE, TaskType.PRO_IMAGE})
_VIDEO_TASK_TYPES = frozenset({TaskType.TEXT_VIDEO, TaskType.IMAGE_VIDEO})
_CREATABLE_TASK_TYPES = _IMAGE_TASK_TYPES | _VIDEO_TASK_TYPES


class GenerationService:
    def __init__(
        self,
        generation_repo: GenerationRepo,
        credit_service: CreditService,
        entitlement_service: EntitlementService,
        settings: Settings,
        rh: RunningHubClient | None = None,
        pollo: PolloClient | None = None,
        s3: S3Storage | None = None,
        model_repo: GenerationModelRepo | None = None,
    ) -> None:
        self._repo = generation_repo
        self._credits = credit_service
        self._entitlements = entitlement_service
        self._settings = settings
        self._rh = rh or RunningHubClient(settings)
        self._pollo = pollo or PolloClient(settings)
        self._s3 = s3 or S3Storage(settings)
        self._models = model_repo or GenerationModelRepo(generation_repo.session)

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
        prompt: str | None = None,
        aspect_ratio: str | None = None,
        idempotency_key: str,
        length: int | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
        input_asset_id: str | None = None,
    ) -> GenerationTask:
        try:
            task_type = TaskType(task_type)
        except ValueError as exc:
            raise ValidationFailed("unsupported task_type") from exc
        if task_type not in _CREATABLE_TASK_TYPES:
            raise ValidationFailed("unsupported task_type")

        existing = await self._repo.get_by_idempotency(idempotency_key)
        if existing:
            return existing

        if task_type in _VIDEO_TASK_TYPES:
            return await self._create_video_task(
                user_id=user_id,
                visitor_id=visitor_id,
                task_type=task_type,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                idempotency_key=idempotency_key,
                length=length,
                resolution=resolution,
                generate_audio=generate_audio,
                input_asset_id=input_asset_id,
            )
        return await self._create_image_task(
            user_id=user_id,
            visitor_id=visitor_id,
            task_type=task_type,
            prompt=prompt or "",
            aspect_ratio=aspect_ratio or "9:16",
            idempotency_key=idempotency_key,
        )

    async def _create_image_task(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        task_type: TaskType,
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

        visitor_id = await self._ensure_visitor(visitor_id)
        await self._check_concurrent(user_id=user_id, visitor_id=visitor_id)

        plan = await self._entitlements.resolve_plan(user_id) if user_id else PLAN_FREE
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

    async def _create_video_task(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        task_type: TaskType,
        prompt: str | None,
        aspect_ratio: str | None,
        idempotency_key: str,
        length: int | None,
        resolution: str | None,
        generate_audio: bool | None,
        input_asset_id: str | None,
    ) -> GenerationTask:
        if not user_id:
            raise AuthRequired("Login required for video generation")

        model = await self._models.get_default_for_task_type(task_type)
        if model is None:
            raise ValidationFailed(
                "Video generation is not configured",
                code="MODEL_UNAVAILABLE",
            )

        length = int(length if length is not None else (model.default_length or VIDEO_DEFAULT_LENGTH))
        resolution = (
            resolution
            if resolution is not None
            else (model.default_resolution or VIDEO_DEFAULT_RESOLUTION)
        )
        aspect_ratio = (
            aspect_ratio
            if aspect_ratio is not None
            else (model.default_aspect_ratio or VIDEO_DEFAULT_ASPECT_RATIO)
        )
        if generate_audio is None:
            generate_audio = bool(model.default_generate_audio)
        else:
            generate_audio = bool(generate_audio)
        if generate_audio and not model.supports_audio:
            raise ValidationFailed(
                "audio generation is not enabled for this model",
                code="AUDIO_NOT_SUPPORTED",
            )

        supported_lengths = model.supported_lengths or []
        supported_resolutions = model.supported_resolutions or []
        supported_aspects = model.supported_aspect_ratios or []
        if length not in supported_lengths:
            raise ValidationFailed(f"length must be one of {supported_lengths}")
        if resolution not in supported_resolutions:
            raise ValidationFailed(f"resolution must be one of {supported_resolutions}")
        if task_type == TaskType.TEXT_VIDEO and aspect_ratio not in supported_aspects:
            raise ValidationFailed(
                f"aspect_ratio must be one of {supported_aspects}"
            )

        prompt = (prompt or "").strip()
        if task_type == TaskType.TEXT_VIDEO:
            if not prompt or len(prompt) > 2000:
                raise ValidationFailed("prompt must be 1–2000 characters")
        else:
            if len(prompt) > 2000:
                raise ValidationFailed("prompt must be at most 2000 characters")
            if not input_asset_id:
                raise ValidationFailed("input_asset_id is required for IMAGE_VIDEO")
            asset = await self._repo.session.get(Asset, input_asset_id)
            if asset is None or asset.owner_user_id != user_id:
                raise ValidationFailed("invalid input_asset_id", code="INVALID_ASSET")
            if asset.status != AssetStatus.READY:
                raise ValidationFailed(
                    "input asset is not ready", code="INVALID_ASSET"
                )
            if asset.asset_type != AssetType.INPUT_IMAGE:
                raise ValidationFailed(
                    "input asset must be an image", code="INVALID_ASSET"
                )
            if not asset.storage_key:
                raise ValidationFailed(
                    "input asset missing storage", code="INVALID_ASSET"
                )

        try:
            credits = video_credits_from_pricing_config(
                model.pricing_config or {},
                length=length,
                resolution=resolution,
                generate_audio=generate_audio,
            )
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

        await self._check_concurrent(user_id=user_id, visitor_id=None)
        plan = await self._entitlements.resolve_plan(user_id)
        task_id = new_id()
        pricing: dict[str, Any] = {
            "mode": PricingMode.CREDITS.value,
            "credits": credits,
            "plan": plan.value if isinstance(plan, PlanCode) else plan,
            "model_id": model.id,
            "model_code": model.code,
            "pricing_version": model.pricing_version,
            "pricing_type": model.pricing_type.value
            if hasattr(model.pricing_type, "value")
            else str(model.pricing_type),
            "length": length,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
            "pricing_config_snapshot": model.pricing_config,
        }
        reservation = await self._credits.reserve_for_task(
            user_id=user_id,
            task_id=task_id,
            amount=credits,
            pricing_snapshot=pricing,
        )
        input_params = {
            "length": length,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
            "provider_model_ref": model.provider_model_ref,
        }

        task = GenerationTask(
            id=task_id,
            user_id=user_id,
            visitor_id=None,
            task_type=task_type,
            status=TaskStatus.QUEUED,
            prompt=prompt or "",
            aspect_ratio=aspect_ratio,
            model_id=model.id,
            model_code=model.code,
            input_asset_id=input_asset_id,
            input_params=input_params,
            pricing_snapshot=pricing,
            credits_reserved=credits,
            credit_reservation_id=reservation.id,
            provider=GenerationProvider.POLLO,
            provider_app_id=model.provider_model_ref,
            idempotency_key=idempotency_key,
            result_transfer_status=TransferStatus.PENDING,
        )
        await self._repo.add(task)
        return task

    async def _check_concurrent(
        self, *, user_id: str | None, visitor_id: str | None
    ) -> None:
        plan = await self._entitlements.resolve_plan(user_id) if user_id else PLAN_FREE
        if user_id:
            active = await self._repo.count_active_for_user(user_id)
            limit = CONCURRENT_JOB_LIMITS.get(plan, 1)
        else:
            if not visitor_id:
                raise AuthRequired("Visitor or user required")
            active = await self._repo.count_active_for_visitor(visitor_id)
            limit = CONCURRENT_JOB_LIMITS[PlanCode.VISITOR]
        if active >= limit:
            raise ConcurrentJobLimit()

    async def get_task(self, task_id: str, *, user_id: str | None) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound("Task not found")
        if user_id and task.user_id and task.user_id != user_id:
            raise NotFound("Task not found")
        return task

    async def quote(
        self,
        *,
        user_id: str | None,
        task_type: TaskType | str,
        length: int | None = None,
        resolution: str | None = None,
        generate_audio: bool | None = None,
    ) -> GenerationQuoteResponse:
        try:
            task_type = TaskType(task_type)
        except ValueError as exc:
            raise ValidationFailed("unsupported task_type") from exc

        if task_type == TaskType.FAST_IMAGE:
            return GenerationQuoteResponse(
                job_type=task_type,
                credits_required=0,
                length=0,
                resolution="",
                generate_audio=None,
                can_generate=True,
                pricing_version="image-fast",
            )
        if task_type == TaskType.PRO_IMAGE:
            available = None
            can = None
            if user_id:
                bal = await self._credits.get_balance(user_id)
                available = bal.available
                can = bal.available >= PRO_IMAGE_CREDITS
            return GenerationQuoteResponse(
                job_type=task_type,
                credits_required=PRO_IMAGE_CREDITS,
                length=0,
                resolution="",
                generate_audio=None,
                can_generate=can,
                available_credits=available,
                pricing_version="image-pro",
            )
        if task_type not in _VIDEO_TASK_TYPES:
            raise ValidationFailed("unsupported task_type")

        model = await self._models.get_default_for_task_type(task_type)
        if model is None:
            raise ValidationFailed(
                "Video generation is not configured",
                code="MODEL_UNAVAILABLE",
            )
        length = int(
            length if length is not None else (model.default_length or VIDEO_DEFAULT_LENGTH)
        )
        resolution = (
            resolution
            if resolution is not None
            else (model.default_resolution or VIDEO_DEFAULT_RESOLUTION)
        )
        if generate_audio is None:
            generate_audio = bool(model.default_generate_audio)
        else:
            generate_audio = bool(generate_audio)
        if generate_audio and not model.supports_audio:
            raise ValidationFailed(
                "audio generation is not enabled for this model",
                code="AUDIO_NOT_SUPPORTED",
            )
        try:
            credits = video_credits_from_pricing_config(
                model.pricing_config or {},
                length=length,
                resolution=resolution,
                generate_audio=generate_audio,
            )
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

        available = None
        can = None
        if user_id:
            bal = await self._credits.get_balance(user_id)
            available = bal.available
            can = bal.available >= credits

        return GenerationQuoteResponse(
            job_type=task_type,
            credits_required=credits,
            length=length,
            resolution=resolution,
            generate_audio=generate_audio,
            can_generate=can,
            available_credits=available,
            pricing_version=model.pricing_version,
        )

    async def submit_to_provider(self, task_id: str) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound()
        if task.status not in TaskStatus.submittable():
            return task

        if task.task_type in _VIDEO_TASK_TYPES:
            return await self._submit_video(task)
        return await self._submit_image(task)

    async def _submit_image(self, task: GenerationTask) -> GenerationTask:
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
            webhook_url = (
                f"{base}{self._settings.api_prefix}/v1/webhooks/generation/runninghub"
            )

        try:
            resp = await self._rh.submit(
                app_id=app_id,
                node_info_list=nodes,
                webhook_url=webhook_url,
            )
        except Exception as exc:
            logger.exception("RH submit failed task=%s", task.id)
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

        if provider_status == RunningHubStatus.SUCCESS and resp.get("results"):
            await self._complete_success(task, resp, media=AssetType.OUTPUT_IMAGE)
        else:
            task.status = TaskStatus.PROCESSING
        await self._repo.session.flush()
        return task

    async def _submit_video(self, task: GenerationTask) -> GenerationTask:
        task.status = TaskStatus.SUBMITTING
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.flush()

        params = task.input_params or {}
        length = int(params.get("length") or VIDEO_DEFAULT_LENGTH)
        resolution = str(params.get("resolution") or VIDEO_DEFAULT_RESOLUTION)
        aspect_ratio = str(params.get("aspect_ratio") or task.aspect_ratio)
        generate_audio = bool(params.get("generate_audio") or False)
        model_ref = str(
            task.provider_app_id
            or params.get("provider_model_ref")
            or "pollo-v2-0"
        )

        try:
            if task.task_type == TaskType.IMAGE_VIDEO:
                if not task.input_asset_id:
                    raise ValidationFailed("missing input_asset_id")
                asset = await self._repo.session.get(Asset, task.input_asset_id)
                if asset is None or not asset.storage_key:
                    raise ValidationFailed("input asset not available")
                image_url = await self._s3.presign_get(
                    asset.storage_key,
                    expires_in=PROVIDER_IMAGE_URL_EXPIRES,
                )
                input_payload = self._pollo.build_image_input(
                    image_url=image_url,
                    prompt=task.prompt or None,
                    length=length,
                    resolution=resolution,
                    generate_audio=generate_audio,
                )
            else:
                input_payload = self._pollo.build_text_input(
                    prompt=task.prompt,
                    aspect_ratio=aspect_ratio,
                    length=length,
                    resolution=resolution,
                    generate_audio=generate_audio,
                )
        except Exception as exc:
            logger.exception("Pollo input build failed task=%s", task.id)
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

        webhook_url = None
        if self._settings.public_api_base_url:
            base = self._settings.public_api_base_url.rstrip("/")
            webhook_url = (
                f"{base}{self._settings.api_prefix}/v1/webhooks/generation/pollo"
            )

        try:
            resp = await self._pollo.submit(
                model_ref=model_ref,
                input_payload=input_payload,
                webhook_url=webhook_url,
            )
        except Exception as exc:
            logger.exception("Pollo submit failed task=%s", task.id)
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

        provider_task_id = str(resp.get("taskId") or "")
        provider_status = str(resp.get("status") or PolloTaskStatus.PROCESSING.value)
        task.provider_task_id = provider_task_id or None
        task.provider_status = provider_status
        task.started_at = datetime.now(UTC)

        # Do not persist full presigned image URL in attempt logs long-term if possible;
        # keep length/resolution only for image mode.
        safe_request = {
            "model_ref": model_ref,
            "mode": task.task_type.value,
            "length": length,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
            "has_image": task.task_type == TaskType.IMAGE_VIDEO,
        }
        await self._repo.add_attempt(
            GenerationAttempt(
                id=new_id(),
                task_id=task.id,
                attempt_no=task.attempt_count,
                status=AttemptStatus.SUBMITTED,
                provider_task_id=provider_task_id or None,
                request_meta=safe_request,
                response_meta={k: resp[k] for k in resp if k != "generations"}
                if isinstance(resp, dict)
                else {"raw": str(resp)[:500]},
            )
        )

        # Stub path may return generations immediately
        if (
            provider_status == PolloTaskStatus.SUCCEED.value
            and (resp.get("generations") or resp.get("_stub"))
        ):
            await self._complete_pollo_success(task, resp)
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
            await self._complete_success(task, payload, media=AssetType.OUTPUT_IMAGE)
        elif status == RunningHubStatus.FAILED:
            await self._fail_task(
                task,
                FailureCode.PROVIDER_FAILED,
                str(
                    payload.get("errorMessage")
                    or payload.get("failedReason")
                    or "failed"
                ),
            )
        await self._repo.session.flush()
        return task

    async def handle_pollo_webhook(
        self,
        *,
        payload: dict[str, Any],
        webhook_id: str | None,
        webhook_timestamp: str | None,
        signature: str | None,
        raw_body: bytes,
    ) -> GenerationTask | None:
        """
        Pollo webhook body is only { taskId, status }.
        On success we must query status for the video URL.
        """
        if self._settings.pollo_webhook_secret:
            if not (webhook_id and webhook_timestamp and signature):
                logger.warning("Pollo webhook missing signature headers")
                raise ValidationFailed("invalid webhook signature")
            ok = self._pollo.verify_webhook_signature(
                webhook_id=webhook_id,
                webhook_timestamp=webhook_timestamp,
                body=raw_body,
                signature=signature,
            )
            if not ok:
                raise ValidationFailed("invalid webhook signature")
        else:
            logger.warning(
                "POLLO_WEBHOOK_SECRET unset; accepting webhook without verify (dev)"
            )

        provider_task_id = str(payload.get("taskId") or "")
        if not provider_task_id:
            return None
        task = await self._repo.get_by_provider_task_id(provider_task_id)
        if task is None:
            logger.warning("No task for pollo taskId=%s", provider_task_id)
            return None
        if task.status in TaskStatus.terminal():
            return task

        status = str(payload.get("status") or "")
        task.provider_status = status
        if status == PolloTaskStatus.FAILED.value:
            await self._fail_task(task, FailureCode.PROVIDER_FAILED, "pollo failed")
            await self._repo.session.flush()
            return task
        if status == PolloTaskStatus.SUCCEED.value:
            detail = await self._pollo.query(provider_task_id)
            await self._complete_pollo_success(task, detail)
            await self._repo.session.flush()
            return task
        # waiting/processing — ignore
        await self._repo.session.flush()
        return task

    async def poll_provider(self, task_id: str) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound()
        if task.status in TaskStatus.submittable():
            return await self.submit_to_provider(task_id)
        if not task.provider_task_id or task.status not in TaskStatus.pollable():
            return task

        if task.provider == GenerationProvider.POLLO or task.task_type in _VIDEO_TASK_TYPES:
            payload = await self._pollo.query(task.provider_task_id)
            status = self._pollo.aggregate_status(payload)
            task.provider_status = status
            if status == PolloTaskStatus.SUCCEED.value:
                await self._complete_pollo_success(task, payload)
            elif status == PolloTaskStatus.FAILED.value:
                fail_msg = "pollo failed"
                for gen in payload.get("generations") or []:
                    if isinstance(gen, dict) and gen.get("failMsg"):
                        fail_msg = str(gen["failMsg"])
                        break
                await self._fail_task(task, FailureCode.PROVIDER_FAILED, fail_msg)
            await self._repo.session.flush()
        else:
            payload = await self._rh.query(task.provider_task_id)
            await self.handle_provider_payload(payload)

        refreshed = await self._repo.get(task_id)
        assert refreshed is not None
        return refreshed

    async def _complete_pollo_success(
        self, task: GenerationTask, payload: dict[str, Any]
    ) -> None:
        task.provider_raw_result = payload
        if "credit" in payload:
            task.provider_usage = {
                **(task.provider_usage or {}),
                "pollo_credit": payload.get("credit"),
            }
        source_url = self._pollo.extract_video_url(payload)
        task.status = TaskStatus.SUCCEEDED
        task.completed_at = datetime.now(UTC)
        task.failure_code = None
        task.failure_detail = None

        if task.credits_reserved > 0:
            await self._credits.capture_reservation(task_id=task.id)

        await self._transfer_result(
            task, source_url=source_url or "", media=AssetType.OUTPUT_VIDEO
        )

    async def _complete_success(
        self,
        task: GenerationTask,
        payload: dict[str, Any],
        *,
        media: AssetType = AssetType.OUTPUT_IMAGE,
    ) -> None:
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

        await self._transfer_result(task, source_url=source_url or "", media=media)

    async def _transfer_result(
        self,
        task: GenerationTask,
        *,
        source_url: str,
        media: AssetType = AssetType.OUTPUT_IMAGE,
    ) -> None:
        """Download provider temporary URL into private S3 and attach Asset row."""
        asset = Asset(
            id=new_id(),
            owner_user_id=task.user_id,
            visitor_id=task.visitor_id if not task.user_id else None,
            asset_type=media,
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
        params = task.input_params or {}
        generate_audio = params.get("generate_audio")
        if generate_audio is not None:
            generate_audio = bool(generate_audio)
        return GenerationTaskResponse(
            job_id=task.id,
            task_type=task.task_type,
            status=task.status,
            aspect_ratio=task.aspect_ratio,
            credits_reserved=task.credits_reserved,
            length=params.get("length"),
            resolution=params.get("resolution"),
            generate_audio=generate_audio,
            result_transfer_status=task.result_transfer_status,
            result_urls=result_urls,
            failure_code=task.failure_code,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )

    async def _result_urls_for_client(self, task: GenerationTask) -> list[str] | None:
        """Prefer short-lived S3 presigned URL; fall back to provider temporary URL."""
        if task.result_asset_id and task.result_transfer_status == TransferStatus.SUCCEEDED:
            asset = await self._repo.session.get(Asset, task.result_asset_id)
            if asset and asset.storage_key and asset.status == AssetStatus.READY:
                try:
                    url = await self._s3.presign_get(asset.storage_key)
                    return [url]
                except Exception:
                    logger.exception("presign failed asset=%s", asset.id)

        if task.provider_raw_result and isinstance(task.provider_raw_result, dict):
            # Pollo
            url = self._pollo.extract_video_url(task.provider_raw_result)
            if url:
                return [url]
            results = task.provider_raw_result.get("results")
            if results:
                urls = [
                    r.get("url")
                    for r in results
                    if isinstance(r, dict) and r.get("url")
                ]
                return urls or None
        return None

    def is_video_task(self, task: GenerationTask) -> bool:
        return task.task_type in _VIDEO_TASK_TYPES
