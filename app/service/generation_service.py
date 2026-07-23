"""Create and complete Fast/Pro image and AI video generation tasks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.commerce import (
    ALLOWED_ASPECT_RATIOS,
    CONCURRENT_JOB_LIMITS,
    DANCE_ALLOWED_ASPECT_RATIOS,
    DANCE_ASPECT_RATIOS,
    DANCE_CREDITS_FREE,
    DANCE_CREDITS_MEMBER,
    DANCE_DEFAULT_ASPECT_RATIO,
    DANCE_PRICING_VERSION,
    DANCE_TEMPLATES,
    DEFAULT_ASPECT_RATIO,
    FAST_ASPECT_RATIOS,
    FAST_I2I_ALLOWED_ASPECT_RATIOS,
    FAST_I2I_ASPECT_RATIOS,
    FAST_I2I_DEFAULT_ASPECT_RATIO,
    IMAGE_FAST_I2I_PRICING_VERSION,
    IMAGE_FAST_PRICING_VERSION,
    IMAGE_PRO_I2I_PRICING_VERSION,
    IMAGE_PRO_PRICING_VERSION,
    PLAN_CREATOR,
    PLAN_FREE,
    PLAN_PRO,
    PLAN_VISITOR,
    PRO_I2I_ALLOWED_ASPECT_RATIOS,
    PRO_I2I_ALLOWED_RESOLUTIONS,
    PRO_I2I_ASPECT_RATIOS,
    PRO_I2I_DEFAULT_ASPECT_RATIO,
    PRO_I2I_DEFAULT_RESOLUTION,
    PRO_I2I_RESOLUTIONS,
    PRO_IMAGE_CREDITS,
    RH_DANCE_APP_ID,
    RH_FAST_APP_ID,
    RH_FAST_I2I_APP_ID,
    RH_PRO_APP_ID,
    RH_PRO_I2I_APP_ID,
    VIDEO_DEFAULT_ASPECT_RATIO,
    VIDEO_DEFAULT_LENGTH,
    VIDEO_DEFAULT_RESOLUTION,
    VIDEO_SUPPORTED_ASPECT_RATIOS,
    VIDEO_SUPPORTED_RESOLUTIONS,
    dance_credits_from_pricing_config,
    default_dance_pricing_config,
    get_dance_template,
    image_credits_from_pricing_config,
    pricing_requires_login,
    pricing_uses_fast_daily_quota,
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
from app.models.creation_session import CreationSession
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
from app.models.generation_model import GenerationModel
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.providers.pollo import PROVIDER_IMAGE_URL_EXPIRES, PolloClient
from app.providers.runninghub import RunningHubClient
from app.providers.s3 import S3Storage
from app.repo.generation_model_repo import GenerationModelRepo
from app.repo.generation_repo import GenerationRepo
from app.schemas.generation import (
    DanceTemplateResponse,
    DanceTemplatesResponse,
    GeneratedAssetResponse,
    GeneratedAssetsResponse,
    GenerationJobOptions,
    GenerationOptionsResponse,
    GenerationQuoteResponse,
    GenerationTaskResponse,
)
from app.service.credit_service import CreditService
from app.service.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)

_TEXT_IMAGE_TASK_TYPES = frozenset({TaskType.FAST_IMAGE, TaskType.PRO_IMAGE})
_I2I_TASK_TYPES = frozenset(
    {TaskType.FAST_IMAGE_TO_IMAGE, TaskType.PRO_IMAGE_TO_IMAGE}
)
_IMAGE_TASK_TYPES = _TEXT_IMAGE_TASK_TYPES | _I2I_TASK_TYPES
_FAST_QUOTA_TASK_TYPES = frozenset(
    {TaskType.FAST_IMAGE, TaskType.FAST_IMAGE_TO_IMAGE}
)
# Pollo AI Video (text / image to video)
_POLLO_VIDEO_TASK_TYPES = frozenset({TaskType.TEXT_VIDEO, TaskType.IMAGE_VIDEO})
# RunningHub photo-to-dance
_DANCE_TASK_TYPES = frozenset({TaskType.DANCE_VIDEO})
_VIDEO_TASK_TYPES = _POLLO_VIDEO_TASK_TYPES | _DANCE_TASK_TYPES
_CREATABLE_TASK_TYPES = _IMAGE_TASK_TYPES | _VIDEO_TASK_TYPES
_OPTIONS_TASK_ORDER: tuple[TaskType, ...] = (
    TaskType.FAST_IMAGE,
    TaskType.PRO_IMAGE,
    TaskType.FAST_IMAGE_TO_IMAGE,
    TaskType.PRO_IMAGE_TO_IMAGE,
    TaskType.TEXT_VIDEO,
    TaskType.IMAGE_VIDEO,
    TaskType.DANCE_VIDEO,
)
_MEMBER_PLANS = frozenset({PLAN_CREATOR, PLAN_PRO})

# Unseeded fallback app ids (create/submit when generation_models missing).
_FALLBACK_RH_APP_ID: dict[TaskType, str] = {
    TaskType.FAST_IMAGE: RH_FAST_APP_ID,
    TaskType.PRO_IMAGE: RH_PRO_APP_ID,
    TaskType.FAST_IMAGE_TO_IMAGE: RH_FAST_I2I_APP_ID,
    TaskType.PRO_IMAGE_TO_IMAGE: RH_PRO_I2I_APP_ID,
    TaskType.DANCE_VIDEO: RH_DANCE_APP_ID,
}


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
        template_id: str | None = None,
        reference_video_asset_id: str | None = None,
        session_id: str | None = None,
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

        if task_type in _DANCE_TASK_TYPES:
            return await self._create_dance_task(
                user_id=user_id,
                visitor_id=visitor_id,
                task_type=task_type,
                aspect_ratio=aspect_ratio,
                idempotency_key=idempotency_key,
                input_asset_id=input_asset_id,
                template_id=template_id,
                reference_video_asset_id=reference_video_asset_id,
                session_id=session_id,
            )
        if task_type in _POLLO_VIDEO_TASK_TYPES:
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
                session_id=session_id,
            )
        return await self._create_image_task(
            user_id=user_id,
            visitor_id=visitor_id,
            task_type=task_type,
            prompt=prompt or "",
            aspect_ratio=aspect_ratio,
            idempotency_key=idempotency_key,
            resolution=resolution,
            input_asset_id=input_asset_id,
            session_id=session_id,
        )

    def _image_option_fallback(self, task_type: TaskType) -> dict[str, Any]:
        """Constants used when generation_models row is missing."""
        if task_type == TaskType.FAST_IMAGE:
            return {
                "aspect_ratios": list(FAST_ASPECT_RATIOS),
                "default_aspect_ratio": DEFAULT_ASPECT_RATIO,
                "resolutions": None,
                "default_resolution": None,
                "app_id": RH_FAST_APP_ID,
                "credits": 0,
                "uses_fast_daily_quota": True,
                "requires_login": False,
                "requires_input_asset": False,
                "pricing_version": IMAGE_FAST_PRICING_VERSION,
                "pricing_config": {"type": "quota", "credits": 0},
            }
        if task_type == TaskType.PRO_IMAGE:
            return {
                "aspect_ratios": list(FAST_ASPECT_RATIOS),
                "default_aspect_ratio": DEFAULT_ASPECT_RATIO,
                "resolutions": None,
                "default_resolution": None,
                "app_id": RH_PRO_APP_ID,
                "credits": PRO_IMAGE_CREDITS,
                "uses_fast_daily_quota": False,
                "requires_login": True,
                "requires_input_asset": False,
                "pricing_version": IMAGE_PRO_PRICING_VERSION,
                "pricing_config": {"type": "fixed", "credits": PRO_IMAGE_CREDITS},
            }
        if task_type == TaskType.FAST_IMAGE_TO_IMAGE:
            return {
                "aspect_ratios": list(FAST_I2I_ASPECT_RATIOS),
                "default_aspect_ratio": FAST_I2I_DEFAULT_ASPECT_RATIO,
                "resolutions": None,
                "default_resolution": None,
                "app_id": RH_FAST_I2I_APP_ID,
                "credits": 0,
                "uses_fast_daily_quota": True,
                "requires_login": True,
                "requires_input_asset": True,
                "pricing_version": IMAGE_FAST_I2I_PRICING_VERSION,
                "pricing_config": {"type": "quota", "credits": 0},
            }
        if task_type == TaskType.PRO_IMAGE_TO_IMAGE:
            return {
                "aspect_ratios": list(PRO_I2I_ASPECT_RATIOS),
                "default_aspect_ratio": PRO_I2I_DEFAULT_ASPECT_RATIO,
                "resolutions": list(PRO_I2I_RESOLUTIONS),
                "default_resolution": PRO_I2I_DEFAULT_RESOLUTION,
                "app_id": RH_PRO_I2I_APP_ID,
                "credits": PRO_IMAGE_CREDITS,
                "uses_fast_daily_quota": False,
                "requires_login": True,
                "requires_input_asset": True,
                "pricing_version": IMAGE_PRO_I2I_PRICING_VERSION,
                "pricing_config": {"type": "fixed", "credits": PRO_IMAGE_CREDITS},
            }
        if task_type == TaskType.TEXT_VIDEO:
            return {
                "aspect_ratios": list(VIDEO_SUPPORTED_ASPECT_RATIOS),
                "default_aspect_ratio": VIDEO_DEFAULT_ASPECT_RATIO,
                "resolutions": list(VIDEO_SUPPORTED_RESOLUTIONS),
                "default_resolution": VIDEO_DEFAULT_RESOLUTION,
                "app_id": None,
                "credits": None,
                "uses_fast_daily_quota": False,
                "requires_login": True,
                "requires_input_asset": False,
                "pricing_version": None,
                "pricing_config": {},
            }
        if task_type == TaskType.IMAGE_VIDEO:
            return {
                "aspect_ratios": list(VIDEO_SUPPORTED_ASPECT_RATIOS),
                "default_aspect_ratio": VIDEO_DEFAULT_ASPECT_RATIO,
                "resolutions": list(VIDEO_SUPPORTED_RESOLUTIONS),
                "default_resolution": VIDEO_DEFAULT_RESOLUTION,
                "app_id": None,
                "credits": None,
                "uses_fast_daily_quota": False,
                "requires_login": True,
                "requires_input_asset": True,
                "pricing_version": None,
                "pricing_config": {},
            }
        if task_type == TaskType.DANCE_VIDEO:
            return {
                "aspect_ratios": list(DANCE_ASPECT_RATIOS),
                "default_aspect_ratio": DANCE_DEFAULT_ASPECT_RATIO,
                "resolutions": None,
                "default_resolution": None,
                "app_id": RH_DANCE_APP_ID,
                "credits": DANCE_CREDITS_FREE,
                "credits_member": DANCE_CREDITS_MEMBER,
                "uses_fast_daily_quota": False,
                "requires_login": True,
                "requires_input_asset": True,
                "pricing_version": DANCE_PRICING_VERSION,
                "pricing_config": default_dance_pricing_config(),
                "supports_template": True,
                "supports_reference_video": True,
            }
        raise ValidationFailed(f"unsupported task_type: {task_type}")

    def _resolve_image_catalog(
        self, task_type: TaskType, model: GenerationModel | None
    ) -> dict[str, Any]:
        """Merge generation_models row with constant fallbacks for RH image jobs."""
        fb = self._image_option_fallback(task_type)
        if model is None:
            return fb
        aspects = list(model.supported_aspect_ratios or fb["aspect_ratios"] or [])
        resolutions = (
            list(model.supported_resolutions)
            if model.supported_resolutions is not None
            else fb["resolutions"]
        )
        cfg = model.pricing_config or fb["pricing_config"] or {}
        is_pollo = task_type in _POLLO_VIDEO_TASK_TYPES
        is_dance = task_type in _DANCE_TASK_TYPES
        credits: int | None
        if is_pollo:
            credits = None
        elif is_dance:
            credits = dance_credits_from_pricing_config(cfg, is_member=False)
        else:
            credits = image_credits_from_pricing_config(cfg)
        credits_member = None
        if is_dance:
            credits_member = int(
                cfg.get("credits_member", fb.get("credits_member", DANCE_CREDITS_MEMBER))
            )
        return {
            "aspect_ratios": aspects,
            "default_aspect_ratio": (
                model.default_aspect_ratio
                or fb["default_aspect_ratio"]
                or DEFAULT_ASPECT_RATIO
            ),
            "resolutions": resolutions,
            "default_resolution": model.default_resolution or fb["default_resolution"],
            "app_id": model.provider_model_ref or fb["app_id"],
            "credits": credits if credits is not None else fb["credits"],
            "credits_member": credits_member
            if credits_member is not None
            else fb.get("credits_member"),
            "uses_fast_daily_quota": pricing_uses_fast_daily_quota(cfg)
            if not is_pollo
            else False,
            "requires_login": pricing_requires_login(
                cfg, default=bool(fb["requires_login"])
            ),
            "requires_input_asset": bool(
                model.supports_image_input
                if task_type
                in _I2I_TASK_TYPES | {TaskType.IMAGE_VIDEO, TaskType.DANCE_VIDEO}
                else fb["requires_input_asset"]
            ),
            "pricing_version": model.pricing_version or fb["pricing_version"],
            "pricing_config": cfg,
            "supports_template": bool(
                fb.get("supports_template") or is_dance
            ),
            "supports_reference_video": bool(
                fb.get("supports_reference_video") or is_dance
            ),
            "model": model,
        }

    async def _create_image_task(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        task_type: TaskType,
        prompt: str,
        aspect_ratio: str | None,
        idempotency_key: str,
        resolution: str | None = None,
        input_asset_id: str | None = None,
        session_id: str | None = None,
    ) -> GenerationTask:
        prompt = (prompt or "").strip()
        if not prompt or len(prompt) > 2000:
            raise ValidationFailed("prompt must be 1–2000 characters")

        model = await self._models.get_default_for_task_type(task_type)
        cat = self._resolve_image_catalog(task_type, model)
        aspect_ratio = aspect_ratio or str(cat["default_aspect_ratio"])
        allowed_aspects = set(cat["aspect_ratios"] or [])
        # Keep legacy frozenset allow-lists as secondary when model empty.
        if not allowed_aspects:
            if task_type == TaskType.FAST_IMAGE_TO_IMAGE:
                allowed_aspects = set(FAST_I2I_ALLOWED_ASPECT_RATIOS)
            elif task_type == TaskType.PRO_IMAGE_TO_IMAGE:
                allowed_aspects = set(PRO_I2I_ALLOWED_ASPECT_RATIOS)
            else:
                allowed_aspects = set(ALLOWED_ASPECT_RATIOS)
        if aspect_ratio not in allowed_aspects:
            raise ValidationFailed(
                f"aspect_ratio must be one of {sorted(allowed_aspects)}"
            )

        is_i2i = task_type in _I2I_TASK_TYPES
        if is_i2i:
            # Asset upload requires a logged-in owner (shared S3 input path).
            if not user_id:
                raise AuthRequired("Login required for image-to-image")
            await self._validate_input_image_asset(
                user_id=user_id, input_asset_id=input_asset_id
            )
        elif cat["requires_login"] and not user_id:
            raise AuthRequired("Login required for Pro image")

        visitor_id = await self._ensure_visitor(visitor_id)
        await self._check_concurrent(user_id=user_id, visitor_id=visitor_id)

        plan = await self._entitlements.resolve_plan(user_id) if user_id else PLAN_FREE
        task_id = new_id()
        credits_reserved = 0
        reservation_id = None
        app_id = str(cat["app_id"] or _FALLBACK_RH_APP_ID[task_type])
        i2i_resolution = str(
            cat["default_resolution"] or PRO_I2I_DEFAULT_RESOLUTION
        )

        if cat["uses_fast_daily_quota"] or task_type in _FAST_QUOTA_TASK_TYPES:
            await self._entitlements.consume_fast_quota(
                user_id=user_id, visitor_id=visitor_id
            )
            if user_id:
                plan_snap = plan.value if isinstance(plan, PlanCode) else plan
            else:
                plan_snap = PLAN_VISITOR.value
            pricing = {
                "mode": PricingMode.FREE_DAILY.value,
                "credits": 0,
                "plan": plan_snap,
                "pricing_version": cat["pricing_version"],
            }
            if model is not None:
                pricing["model_id"] = model.id
                pricing["model_code"] = model.code
            if task_type == TaskType.FAST_IMAGE_TO_IMAGE:
                input_params = self._rh.input_params_for_fast_i2i(
                    aspect_ratio=aspect_ratio
                )
            else:
                input_params = self._rh.input_params_for_fast(aspect_ratio)
            input_params["app_id"] = app_id
        else:
            # PRO_IMAGE / PRO_IMAGE_TO_IMAGE
            if not user_id:
                raise AuthRequired("Login required for Pro image")
            credits = int(cat["credits"] if cat["credits"] is not None else PRO_IMAGE_CREDITS)
            if task_type == TaskType.PRO_IMAGE_TO_IMAGE:
                allowed_res = set(cat["resolutions"] or PRO_I2I_ALLOWED_RESOLUTIONS)
                i2i_resolution = (
                    resolution
                    if resolution is not None
                    else str(cat["default_resolution"] or PRO_I2I_DEFAULT_RESOLUTION)
                )
                if i2i_resolution not in allowed_res:
                    raise ValidationFailed(
                        f"resolution must be one of {sorted(allowed_res)}"
                    )
            pricing = {
                "mode": PricingMode.CREDITS.value,
                "credits": credits,
                "plan": plan.value if isinstance(plan, PlanCode) else plan,
                "pricing_version": cat["pricing_version"],
            }
            if model is not None:
                pricing["model_id"] = model.id
                pricing["model_code"] = model.code
                pricing["pricing_config_snapshot"] = cat["pricing_config"]
            reservation = await self._credits.reserve_for_task(
                user_id=user_id,
                task_id=task_id,
                amount=credits,
                pricing_snapshot=pricing,
            )
            credits_reserved = credits
            reservation_id = reservation.id
            if task_type == TaskType.PRO_IMAGE_TO_IMAGE:
                input_params = self._rh.input_params_for_pro_i2i(
                    aspect_ratio=aspect_ratio,
                    resolution=i2i_resolution,
                )
            else:
                input_params = self._rh.input_params_for_pro(aspect_ratio)
            input_params["app_id"] = app_id

        task = GenerationTask(
            id=task_id,
            user_id=user_id,
            visitor_id=visitor_id,
            creation_session_id=session_id,
            task_type=task_type,
            status=TaskStatus.QUEUED,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            model_id=model.id if model is not None else None,
            model_code=model.code if model is not None else None,
            input_asset_id=input_asset_id if is_i2i else None,
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
        await self._touch_creation_session(session_id)
        await self._repo.session.commit()
        return task

    async def _validate_input_image_asset(
        self, *, user_id: str, input_asset_id: str | None
    ) -> Asset:
        if not input_asset_id:
            raise ValidationFailed("input_asset_id is required")
        asset = await self._repo.session.get(Asset, input_asset_id)
        if asset is None or asset.owner_user_id != user_id:
            raise ValidationFailed("invalid input_asset_id", code="INVALID_ASSET")
        if asset.status != AssetStatus.READY:
            raise ValidationFailed("input asset is not ready", code="INVALID_ASSET")
        if asset.asset_type != AssetType.INPUT_IMAGE:
            raise ValidationFailed(
                "input asset must be an image", code="INVALID_ASSET"
            )
        if not asset.storage_key:
            raise ValidationFailed(
                "input asset missing storage", code="INVALID_ASSET"
            )
        return asset

    async def _validate_input_video_asset(
        self, *, user_id: str, video_asset_id: str | None
    ) -> Asset:
        if not video_asset_id:
            raise ValidationFailed("reference_video_asset_id is required")
        asset = await self._repo.session.get(Asset, video_asset_id)
        if asset is None or asset.owner_user_id != user_id:
            raise ValidationFailed(
                "invalid reference_video_asset_id", code="INVALID_ASSET"
            )
        if asset.status != AssetStatus.READY:
            raise ValidationFailed(
                "reference video asset is not ready", code="INVALID_ASSET"
            )
        if asset.asset_type != AssetType.INPUT_VIDEO:
            raise ValidationFailed(
                "reference asset must be a video", code="INVALID_ASSET"
            )
        if not asset.storage_key:
            raise ValidationFailed(
                "reference video missing storage", code="INVALID_ASSET"
            )
        return asset

    async def _create_dance_task(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        task_type: TaskType,
        aspect_ratio: str | None,
        idempotency_key: str,
        input_asset_id: str | None,
        template_id: str | None,
        reference_video_asset_id: str | None,
        session_id: str | None,
    ) -> GenerationTask:
        """Photo-to-dance via RunningHub: photo + preset or user reference video."""
        if not user_id:
            raise AuthRequired("Login required for dance generation")

        has_template = bool(template_id and str(template_id).strip())
        has_ref_video = bool(
            reference_video_asset_id and str(reference_video_asset_id).strip()
        )
        if has_template == has_ref_video:
            # XOR: exactly one of template_id / reference_video_asset_id
            raise ValidationFailed(
                "provide exactly one of template_id or reference_video_asset_id"
            )

        await self._validate_input_image_asset(
            user_id=user_id, input_asset_id=input_asset_id
        )

        template = None
        template_video_url: str | None = None
        ref_video_id: str | None = None
        if has_template:
            template = get_dance_template(str(template_id).strip())
            if template is None:
                raise ValidationFailed(
                    "unknown template_id", code="TEMPLATE_UNAVAILABLE"
                )
            template_video_url = template.video_url
            default_ar = template.aspect_ratio or DANCE_DEFAULT_ASPECT_RATIO
        else:
            await self._validate_input_video_asset(
                user_id=user_id, video_asset_id=reference_video_asset_id
            )
            ref_video_id = str(reference_video_asset_id).strip()
            default_ar = DANCE_DEFAULT_ASPECT_RATIO

        model = await self._models.get_default_for_task_type(task_type)
        cat = self._resolve_image_catalog(task_type, model)
        aspect_ratio = (
            aspect_ratio
            if aspect_ratio is not None
            else default_ar
        )
        allowed_aspects = set(cat["aspect_ratios"] or DANCE_ALLOWED_ASPECT_RATIOS)
        if aspect_ratio not in allowed_aspects:
            raise ValidationFailed(
                f"aspect_ratio must be one of {sorted(allowed_aspects)} "
                "(must match the reference video)"
            )

        await self._check_concurrent(user_id=user_id, visitor_id=None)
        plan = await self._entitlements.resolve_plan(user_id)
        is_member = plan in _MEMBER_PLANS
        cfg = cat.get("pricing_config") or default_dance_pricing_config()
        credits = dance_credits_from_pricing_config(cfg, is_member=is_member)
        app_id = str(cat["app_id"] or RH_DANCE_APP_ID)

        task_id = new_id()
        pricing: dict[str, Any] = {
            "mode": PricingMode.CREDITS.value,
            "credits": credits,
            "plan": plan.value if isinstance(plan, PlanCode) else plan,
            "is_member": is_member,
            "pricing_version": cat.get("pricing_version") or DANCE_PRICING_VERSION,
            "pricing_config_snapshot": cfg,
        }
        if model is not None:
            pricing["model_id"] = model.id
            pricing["model_code"] = model.code

        reservation = await self._credits.reserve_for_task(
            user_id=user_id,
            task_id=task_id,
            amount=credits,
            pricing_snapshot=pricing,
        )
        input_params = self._rh.input_params_for_dance(
            aspect_ratio=aspect_ratio,
            template_id=template.id if template else None,
            reference_video_asset_id=ref_video_id,
            template_video_url=template_video_url,
        )
        input_params["app_id"] = app_id

        task = GenerationTask(
            id=task_id,
            user_id=user_id,
            visitor_id=None,
            creation_session_id=session_id,
            task_type=task_type,
            status=TaskStatus.QUEUED,
            prompt="",
            aspect_ratio=aspect_ratio,
            model_id=model.id if model is not None else None,
            model_code=model.code if model is not None else None,
            input_asset_id=input_asset_id,
            input_params=input_params,
            pricing_snapshot=pricing,
            credits_reserved=credits,
            credit_reservation_id=reservation.id,
            provider=GenerationProvider.RUNNINGHUB,
            provider_app_id=app_id,
            idempotency_key=idempotency_key,
            result_transfer_status=TransferStatus.PENDING,
        )
        await self._repo.add(task)
        await self._touch_creation_session(session_id)
        await self._repo.session.commit()
        return task

    async def list_dance_templates(self) -> DanceTemplatesResponse:
        templates = sorted(DANCE_TEMPLATES, key=lambda t: t.sort_order)
        return DanceTemplatesResponse(
            templates=[
                DanceTemplateResponse(
                    id=t.id,
                    title=t.title,
                    duration_seconds=t.duration_seconds,
                    video_url=t.video_url,
                    poster_url=t.poster_url,
                    aspect_ratio=t.aspect_ratio,
                    sort_order=t.sort_order,
                )
                for t in templates
            ]
        )

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
        session_id: str | None,
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
            await self._validate_input_image_asset(
                user_id=user_id, input_asset_id=input_asset_id
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
            creation_session_id=session_id,
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
        await self._touch_creation_session(session_id)
        await self._repo.session.commit()
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

    async def _touch_creation_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        creation_session = await self._repo.session.get(CreationSession, session_id)
        if creation_session is not None:
            creation_session.updated_at = utc_now()

    async def get_task(self, task_id: str, *, user_id: str | None) -> GenerationTask:
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFound("Task not found")
        if user_id and task.user_id and task.user_id != user_id:
            raise NotFound("Task not found")
        return task

    async def list_generated_assets(
        self,
        *,
        user_id: str,
        media_type: str,
        limit: int = 60,
        offset: int = 0,
    ) -> GeneratedAssetsResponse:
        """List successful output media owned by one signed-in user."""
        task_types = (
            list(_IMAGE_TASK_TYPES)
            if media_type == "image"
            else list(_VIDEO_TASK_TYPES)
        )
        tasks = await self._repo.list_for_user(
            user_id,
            task_types=task_types,
            status=TaskStatus.SUCCEEDED,
            limit=limit,
            offset=offset,
        )
        items: list[GeneratedAssetResponse] = []
        for task in tasks:
            result_urls = await self._result_urls_for_client(task)
            if not result_urls:
                continue
            items.append(
                GeneratedAssetResponse(
                    job_id=task.id,
                    session_id=task.creation_session_id,
                    task_type=task.task_type,
                    model_code=task.model_code,
                    prompt=task.prompt,
                    aspect_ratio=task.aspect_ratio,
                    result_url=result_urls[0],
                    created_at=task.created_at,
                    completed_at=task.completed_at,
                )
            )

        return GeneratedAssetsResponse(
            items=items,
            next_offset=offset + limit if len(tasks) == limit else None,
        )

    async def delete_generated_asset(self, *, user_id: str, job_id: str) -> None:
        """Delete an asset item owned by the specified user."""
        task = await self._repo.get(job_id)
        if not task or task.user_id != user_id:
            raise NotFound("Asset not found")
        task.status = TaskStatus.CANCELED
        if task.result_asset_id:
            asset = await self._repo.session.get(Asset, task.result_asset_id)
            if asset:
                asset.deleted_at = utc_now()
        await self._repo.session.flush()



    async def get_generated_asset_download_url(self, *, user_id: str, job_id: str) -> str:
        """Get the result URL for downloading an asset."""
        task = await self.get_task(job_id, user_id=user_id)
        result_urls = await self._result_urls_for_client(task)
        if not result_urls:
            raise NotFound("Asset result not found")
        return result_urls[0]


    def _job_options_from_catalog(
        self, task_type: TaskType, cat: dict[str, Any]
    ) -> GenerationJobOptions:
        credits = cat.get("credits")
        credits_member = cat.get("credits_member")
        return GenerationJobOptions(
            job_type=task_type,
            aspect_ratios=list(cat.get("aspect_ratios") or []),
            default_aspect_ratio=str(
                cat.get("default_aspect_ratio") or DEFAULT_ASPECT_RATIO
            ),
            resolutions=list(cat["resolutions"])
            if cat.get("resolutions") is not None
            else None,
            default_resolution=cat.get("default_resolution"),
            requires_input_asset=bool(cat.get("requires_input_asset")),
            requires_login=bool(cat.get("requires_login")),
            credits_required=int(credits) if credits is not None else None,
            credits_required_member=(
                int(credits_member) if credits_member is not None else None
            ),
            uses_fast_daily_quota=bool(cat.get("uses_fast_daily_quota")),
            supports_template=bool(cat.get("supports_template")),
            supports_reference_video=bool(cat.get("supports_reference_video")),
        )

    async def list_job_options(
        self, *, job_type: TaskType | str | None = None
    ) -> GenerationOptionsResponse:
        """Public option catalogs from generation_models (fallback to constants)."""
        model_map = await self._models.map_default_by_task_type()
        if job_type is None:
            types = list(_OPTIONS_TASK_ORDER)
        else:
            try:
                tt = TaskType(job_type)
            except ValueError as exc:
                raise ValidationFailed("unsupported task_type") from exc
            if tt not in _OPTIONS_TASK_ORDER:
                raise ValidationFailed("unsupported task_type")
            types = [tt]

        jobs: list[GenerationJobOptions] = []
        for tt in types:
            model = model_map.get(tt.value)
            cat = self._resolve_image_catalog(tt, model)
            jobs.append(self._job_options_from_catalog(tt, cat))
        return GenerationOptionsResponse(jobs=jobs)

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

        if task_type in _IMAGE_TASK_TYPES:
            model = await self._models.get_default_for_task_type(task_type)
            cat = self._resolve_image_catalog(task_type, model)
            if cat["uses_fast_daily_quota"] or task_type in _FAST_QUOTA_TASK_TYPES:
                return GenerationQuoteResponse(
                    job_type=task_type,
                    credits_required=0,
                    length=0,
                    resolution="",
                    generate_audio=None,
                    can_generate=True,
                    pricing_version=str(
                        cat["pricing_version"] or IMAGE_FAST_PRICING_VERSION
                    ),
                )
            credits = int(
                cat["credits"] if cat["credits"] is not None else PRO_IMAGE_CREDITS
            )
            quoted_resolution = ""
            if task_type == TaskType.PRO_IMAGE_TO_IMAGE:
                quoted_resolution = str(
                    resolution
                    if resolution is not None
                    else (cat["default_resolution"] or PRO_I2I_DEFAULT_RESOLUTION)
                )
                allowed_resolutions = set(
                    cat["resolutions"] or PRO_I2I_ALLOWED_RESOLUTIONS
                )
                if quoted_resolution not in allowed_resolutions:
                    raise ValidationFailed(
                        f"resolution must be one of {sorted(allowed_resolutions)}"
                    )
            available = None
            can = None
            if user_id:
                bal = await self._credits.get_balance(user_id)
                available = bal.available
                can = bal.available >= credits
            return GenerationQuoteResponse(
                job_type=task_type,
                credits_required=credits,
                length=0,
                resolution=quoted_resolution,
                generate_audio=None,
                can_generate=can,
                available_credits=available,
                pricing_version=str(
                    cat["pricing_version"] or IMAGE_PRO_PRICING_VERSION
                ),
            )
        if task_type in _DANCE_TASK_TYPES:
            model = await self._models.get_default_for_task_type(task_type)
            cat = self._resolve_image_catalog(task_type, model)
            plan = (
                await self._entitlements.resolve_plan(user_id)
                if user_id
                else PLAN_FREE
            )
            is_member = plan in _MEMBER_PLANS
            cfg = cat.get("pricing_config") or default_dance_pricing_config()
            credits = dance_credits_from_pricing_config(cfg, is_member=is_member)
            available = None
            can = None
            if user_id:
                bal = await self._credits.get_balance(user_id)
                available = bal.available
                can = bal.available >= credits
            return GenerationQuoteResponse(
                job_type=task_type,
                credits_required=credits,
                length=0,
                resolution="",
                generate_audio=None,
                can_generate=can,
                available_credits=available,
                pricing_version=str(
                    cat.get("pricing_version") or DANCE_PRICING_VERSION
                ),
            )
        if task_type not in _POLLO_VIDEO_TASK_TYPES:
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

        if task.task_type in _DANCE_TASK_TYPES:
            return await self._submit_dance(task)
        if task.task_type in _POLLO_VIDEO_TASK_TYPES:
            return await self._submit_video(task)
        return await self._submit_image(task)

    async def _submit_image(self, task: GenerationTask) -> GenerationTask:
        task.status = TaskStatus.SUBMITTING
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.commit()

        try:
            nodes, app_id = await self._build_image_nodes(task)
        except Exception as exc:
            logger.exception("RH input build failed task=%s", task.id)
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

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

        # Avoid persisting full presigned input URLs long-term.
        safe_nodes = [
            (
                {**n, "fieldValue": "[image_url]"}
                if n.get("fieldName") == "image" and n.get("fieldValue")
                else n
            )
            for n in nodes
        ]
        await self._repo.add_attempt(
            GenerationAttempt(
                id=new_id(),
                task_id=task.id,
                attempt_no=task.attempt_count,
                status=AttemptStatus.SUBMITTED,
                provider_task_id=provider_task_id or None,
                request_meta={"app_id": app_id, "nodes": safe_nodes},
                response_meta=resp,
            )
        )

        if provider_status == RunningHubStatus.SUCCESS and resp.get("results"):
            await self._complete_success(task, resp, media=AssetType.OUTPUT_IMAGE)
        else:
            task.status = TaskStatus.PROCESSING
        await self._repo.session.flush()
        return task

    async def _submit_dance(self, task: GenerationTask) -> GenerationTask:
        task.status = TaskStatus.SUBMITTING
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.commit()

        try:
            nodes, app_id = await self._build_dance_nodes(task)
        except Exception as exc:
            logger.exception("RH dance input build failed task=%s", task.id)
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

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
            logger.exception("RH dance submit failed task=%s", task.id)
            await self._fail_task(task, FailureCode.PROVIDER_SUBMIT_FAILED, str(exc))
            return task

        provider_task_id = str(resp.get("taskId") or "")
        provider_status = str(resp.get("status") or RunningHubStatus.RUNNING.value)
        task.provider_task_id = provider_task_id or None
        task.provider_status = provider_status
        task.started_at = datetime.now(UTC)

        safe_nodes = []
        for n in nodes:
            fn = n.get("fieldName")
            if fn in ("image", "video") and n.get("fieldValue"):
                safe_nodes.append({**n, "fieldValue": f"[{fn}_url]"})
            else:
                safe_nodes.append(n)
        await self._repo.add_attempt(
            GenerationAttempt(
                id=new_id(),
                task_id=task.id,
                attempt_no=task.attempt_count,
                status=AttemptStatus.SUBMITTED,
                provider_task_id=provider_task_id or None,
                request_meta={"app_id": app_id, "nodes": safe_nodes},
                response_meta=resp,
            )
        )

        if provider_status == RunningHubStatus.SUCCESS and resp.get("results"):
            await self._complete_success(task, resp, media=AssetType.OUTPUT_VIDEO)
        else:
            task.status = TaskStatus.PROCESSING
        await self._repo.session.flush()
        return task

    async def _build_dance_nodes(
        self, task: GenerationTask
    ) -> tuple[list[dict[str, Any]], str]:
        params = task.input_params or {}
        app_id = str(
            task.provider_app_id
            or params.get("app_id")
            or RH_DANCE_APP_ID
        )
        image_url = await self._presign_input_image_url(task)

        video_url: str | None = None
        ref_video_id = params.get("reference_video_asset_id")
        if ref_video_id:
            asset = await self._repo.session.get(Asset, str(ref_video_id))
            if asset is None or not asset.storage_key:
                raise ValidationFailed("reference video asset not available")
            if not self._s3.configured:
                logger.warning(
                    "S3 not configured; using stub dance video URL task=%s", task.id
                )
                video_url = "https://example.com/stub-dance-ref.mp4"
            else:
                video_url = await self._s3.presign_get(
                    asset.storage_key,
                    expires_in=PROVIDER_IMAGE_URL_EXPIRES,
                )
        else:
            video_url = params.get("template_video_url")
            if not video_url and params.get("template_id"):
                tmpl = get_dance_template(str(params["template_id"]))
                if tmpl:
                    video_url = tmpl.video_url
        if not video_url:
            raise ValidationFailed("missing reference video url")

        nodes = self._rh.build_dance_node_list(
            image_url=image_url,
            video_url=str(video_url),
            aspect_ratio=task.aspect_ratio or DANCE_DEFAULT_ASPECT_RATIO,
        )
        return nodes, app_id

    async def _build_image_nodes(
        self, task: GenerationTask
    ) -> tuple[list[dict[str, Any]], str]:
        params = task.input_params or {}
        app_id = str(
            task.provider_app_id
            or params.get("app_id")
            or _FALLBACK_RH_APP_ID.get(task.task_type, "")
        )
        if task.task_type == TaskType.FAST_IMAGE:
            return (
                self._rh.build_fast_node_list(
                    prompt=task.prompt, aspect_ratio=task.aspect_ratio
                ),
                app_id or RH_FAST_APP_ID,
            )
        if task.task_type == TaskType.PRO_IMAGE:
            return (
                self._rh.build_pro_node_list(
                    prompt=task.prompt, aspect_ratio=task.aspect_ratio
                ),
                app_id or RH_PRO_APP_ID,
            )
        if task.task_type in _I2I_TASK_TYPES:
            image_url = await self._presign_input_image_url(task)
            if task.task_type == TaskType.FAST_IMAGE_TO_IMAGE:
                return (
                    self._rh.build_fast_i2i_node_list(
                        prompt=task.prompt,
                        image_url=image_url,
                        aspect_ratio=task.aspect_ratio,
                    ),
                    app_id or RH_FAST_I2I_APP_ID,
                )
            resolution = str(
                params.get("resolution") or PRO_I2I_DEFAULT_RESOLUTION
            )
            return (
                self._rh.build_pro_i2i_node_list(
                    prompt=task.prompt,
                    image_url=image_url,
                    aspect_ratio=task.aspect_ratio,
                    resolution=resolution,
                ),
                app_id or RH_PRO_I2I_APP_ID,
            )
        raise ValidationFailed(f"unsupported image task_type: {task.task_type}")

    async def _presign_input_image_url(self, task: GenerationTask) -> str:
        if not task.input_asset_id:
            raise ValidationFailed("missing input_asset_id")
        asset = await self._repo.session.get(Asset, task.input_asset_id)
        if asset is None or not asset.storage_key:
            raise ValidationFailed("input asset not available")
        if not self._s3.configured:
            logger.warning(
                "S3 not configured; using stub input image URL task=%s", task.id
            )
            return "https://httpbin.org/image/jpeg"
        return await self._s3.presign_get(
            asset.storage_key,
            expires_in=PROVIDER_IMAGE_URL_EXPIRES,
        )

    async def _submit_video(self, task: GenerationTask) -> GenerationTask:
        task.status = TaskStatus.SUBMITTING
        task.submitted_at = datetime.now(UTC)
        task.attempt_count += 1
        await self._repo.session.commit()

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
            media = (
                AssetType.OUTPUT_VIDEO
                if task.task_type in _DANCE_TASK_TYPES
                else AssetType.OUTPUT_IMAGE
            )
            await self._complete_success(task, payload, media=media)
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

        if (
            task.provider == GenerationProvider.POLLO
            or task.task_type in _POLLO_VIDEO_TASK_TYPES
        ):
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
        if media == AssetType.OUTPUT_VIDEO:
            source_url = self._rh.extract_video_url(payload)
        if not source_url and results and isinstance(results, list):
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
        if task.task_type in _FAST_QUOTA_TASK_TYPES:
            await self._entitlements.refund_fast_quota(
                user_id=task.user_id, visitor_id=task.visitor_id
            )

    async def to_public(self, task: GenerationTask) -> GenerationTaskResponse:
        result_urls = await self._result_urls_for_client(task)
        input_url = await self._input_url_for_client(task)
        params = task.input_params or {}
        generate_audio = params.get("generate_audio")
        if generate_audio is not None:
            generate_audio = bool(generate_audio)
        template_id = params.get("template_id")
        return GenerationTaskResponse(
            job_id=task.id,
            session_id=task.creation_session_id,
            task_type=task.task_type,
            status=task.status,
            prompt=task.prompt,
            aspect_ratio=task.aspect_ratio,
            credits_reserved=task.credits_reserved,
            length=params.get("length"),
            resolution=params.get("resolution"),
            generate_audio=generate_audio,
            template_id=str(template_id) if template_id else None,
            result_transfer_status=task.result_transfer_status,
            result_urls=result_urls,
            input_url=input_url,
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

    async def _input_url_for_client(self, task: GenerationTask) -> str | None:
        if not task.input_asset_id:
            return None
        asset = await self._repo.session.get(Asset, task.input_asset_id)
        if asset is None or not asset.storage_key or asset.status != AssetStatus.READY:
            return None
        try:
            return await self._s3.presign_get(asset.storage_key)
        except Exception:
            logger.exception("presign input failed asset=%s", asset.id)
            return None

    def is_video_task(self, task: GenerationTask) -> bool:
        """Longer worker poll budget for Pollo video and RH dance."""
        return task.task_type in _VIDEO_TASK_TYPES
