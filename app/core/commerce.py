"""
Commercial defaults for MVP (not scattered magic numbers in services).

Products themselves live in DB; these are pricing/quota rules and RunningHub apps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.models.enums import (
    BillingInterval,
    MembershipPlan,
    PlanCode,
    ProductCode,
    ProductType,
)

# --- Plan / quota (aliases keep call sites readable) ---

PLAN_FREE: Final = PlanCode.FREE
PLAN_CREATOR: Final = PlanCode.CREATOR
PLAN_PRO: Final = PlanCode.PRO
PLAN_VISITOR: Final = PlanCode.VISITOR

FAST_DAILY_LIMITS: Final[dict[PlanCode, int]] = {
    PlanCode.FREE: 5,
    PlanCode.CREATOR: 30,
    PlanCode.PRO: 60,
    PlanCode.VISITOR: 2,
}

PRO_IMAGE_CREDITS: Final = 12
SIGNUP_BONUS_CREDITS: Final = 20
SIGNUP_BONUS_DAYS: Final = 7

# Subscription period grant (paid membership plans only)
SUBSCRIPTION_CREDITS: Final[dict[MembershipPlan, int]] = {
    MembershipPlan.CREATOR: 1000,
    MembershipPlan.PRO: 2400,
}

# Max carry of subscription credits = 2 × current period grant
SUBSCRIPTION_CARRY_MULTIPLIER: Final = 2

CREDIT_PACK_EXPIRE_DAYS: Final = 365
SUBSCRIPTION_CREDIT_EXTRA_PERIOD_DAYS: Final = 31  # ~1 billing period buffer
MEMBERSHIP_GRACE_DAYS: Final = 3
RESERVATION_TTL_HOURS: Final = 2

# Concurrent generation tasks
CONCURRENT_JOB_LIMITS: Final[dict[PlanCode, int]] = {
    PlanCode.VISITOR: 1,
    PlanCode.FREE: 1,
    PlanCode.CREATOR: 2,
    PlanCode.PRO: 3,
}

# --- Product codes (must match products table) ---

PRODUCT_CREATOR_MONTHLY: Final = ProductCode.CREATOR_MONTHLY
PRODUCT_PRO_MONTHLY: Final = ProductCode.PRO_MONTHLY
PRODUCT_CREDIT_400: Final = ProductCode.CREDIT_400
PRODUCT_CREDIT_900: Final = ProductCode.CREDIT_900
PRODUCT_CREDIT_2000: Final = ProductCode.CREDIT_2000

ALL_PRODUCT_CODES: Final[tuple[ProductCode, ...]] = (
    ProductCode.CREATOR_MONTHLY,
    ProductCode.PRO_MONTHLY,
    ProductCode.CREDIT_400,
    ProductCode.CREDIT_900,
    ProductCode.CREDIT_2000,
)

# --- RunningHub ---
# Live option catalogs / pricing for RH also live on generation_models (seed).
# Constants below are defaults for seed + unseeded fallback.

RH_FAST_APP_ID: Final = "2016540100959674370"
RH_PRO_APP_ID: Final = "2070881747880992769"
RH_FAST_I2I_APP_ID: Final = "2003708796583198721"
RH_PRO_I2I_APP_ID: Final = "2061699451919618049"
# RunningHub Kling v2.6 Motion Control Standard API
RH_DANCE_APP_ID: Final = "kling-v2.6-std/motion-control"

RH_FAST_IMAGE_MODEL_CODE: Final = "RH_FAST_IMAGE"
RH_PRO_IMAGE_MODEL_CODE: Final = "RH_PRO_IMAGE"
RH_FAST_I2I_MODEL_CODE: Final = "RH_FAST_I2I"
RH_PRO_I2I_MODEL_CODE: Final = "RH_PRO_I2I"
RH_DANCE_MODEL_CODE: Final = "RH_DANCE_VIDEO"

IMAGE_FAST_PRICING_VERSION: Final = "image-fast"
IMAGE_PRO_PRICING_VERSION: Final = "image-pro"
IMAGE_FAST_I2I_PRICING_VERSION: Final = "image-fast-i2i"
IMAGE_PRO_I2I_PRICING_VERSION: Final = "image-pro-i2i"
DANCE_PRICING_VERSION: Final = "dance-v2-per-second"

# Per-second pricing for RunningHub Motion Control ($0.06/s -> $0.15/s -> 15 credits/s)
DANCE_CREDITS_PER_SECOND: Final = 15
DANCE_CREDITS_PER_SECOND_MEMBER: Final = 14
DANCE_MIN_CREDITS: Final = 30
DANCE_CREDITS_FREE: Final = 150
DANCE_CREDITS_MEMBER: Final = 140
DANCE_DEFAULT_ASPECT_RATIO: Final = "9:16"
DANCE_ASPECT_RATIOS: Final[tuple[str, ...]] = (
    "9:16",
    "16:9",
    "1:1",
    "3:4",
    "4:3",
)
DANCE_ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset(DANCE_ASPECT_RATIOS)


@dataclass(frozen=True, slots=True)
class DanceTemplate:
    """Preset dance reference video (node 275)."""

    id: str
    title: str
    duration_seconds: int
    video_url: str
    poster_url: str | None = None
    aspect_ratio: str = DANCE_DEFAULT_ASPECT_RATIO
    sort_order: int = 0




PRO_DEFAULT_QUALITY: Final = "medium"
PRO_DEFAULT_RESOLUTION: Final = "2k"
# Pro image-to-image (RH app 2061699451919618049) node 1
# fieldData resolution: 1k | 2k | 4k (default 2k)
# fieldData aspectRatio: empty, 1:1, 16:9, … (default empty)
# Optional image nodes 3/4/5: send fieldValue=null when unused.
PRO_I2I_RESOLUTIONS: Final[tuple[str, ...]] = ("1k", "2k", "4k")
PRO_I2I_DEFAULT_RESOLUTION: Final = "2k"
PRO_I2I_ALLOWED_RESOLUTIONS: Final[frozenset[str]] = frozenset(PRO_I2I_RESOLUTIONS)
PRO_I2I_ASPECT_RATIOS: Final[tuple[str, ...]] = (
    "empty",
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "21:9",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
)
PRO_I2I_DEFAULT_ASPECT_RATIO: Final = "empty"
PRO_I2I_ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset(PRO_I2I_ASPECT_RATIOS)
FAST_DEFAULT_SCALE_BY: Final = "1.5"
# Free I2I app (2003708796583198721) node 41 "select" — ratio index from RH UI:
# 0 自动匹配图像1比例 | 1 1:1 | 2 2:3 | 3 3:2 | 4 3:4 | 5 4:3
# 6 4:5 | 7 5:4 | 8 9:16 | 9 16:9 | 10 21:9
# Nodes 18/43 are optional extra images — send fieldValue=null when unused.
FAST_I2I_ASPECT_RATIOS: Final[tuple[str, ...]] = (
    "auto",
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)
RH_FAST_I2I_RATIO_SELECT: Final[dict[str, str]] = {
    "auto": "1",
    "1:1": "1",
    "2:3": "2",
    "3:2": "3",
    "3:4": "4",
    "4:3": "5",
    "4:5": "6",
    "5:4": "7",
    "9:16": "8",
    "16:9": "9",
    "21:9": "10",
}
FAST_I2I_DEFAULT_ASPECT_RATIO: Final = "auto"
FAST_I2I_ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset(
    RH_FAST_I2I_RATIO_SELECT.keys()
)

# aspect_ratio -> (width, height) for Fast workflow
# Default product ratio is 9:16 (mobile-first).
FAST_ASPECT_SIZES: Final[dict[str, tuple[int, int]]] = {
    "9:16": (576, 1024),
    "16:9": (1024, 576),
    "1:1": (1024, 1024),
    "3:4": (768, 1024),
    "4:3": (1024, 768),
}

DEFAULT_ASPECT_RATIO: Final = "9:16"

ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset(FAST_ASPECT_SIZES.keys())
FAST_ASPECT_RATIOS: Final[tuple[str, ...]] = tuple(FAST_ASPECT_SIZES.keys())


def default_rh_quota_pricing_config(
    *,
    requires_login: bool,
    pricing_version: str,
) -> dict:
    """Free daily Fast path (text or I2I)."""
    return {
        "type": "quota",
        "credits": 0,
        "uses_fast_daily_quota": True,
        "requires_login": requires_login,
        "pricing_version": pricing_version,
    }


def default_rh_fixed_pricing_config(
    *,
    credits: int = PRO_IMAGE_CREDITS,
    requires_login: bool = True,
    pricing_version: str = IMAGE_PRO_PRICING_VERSION,
    credits_member: int | None = None,
) -> dict:
    """Pro image / Pro I2I / Dance fixed credit charge."""
    cfg: dict = {
        "type": "fixed",
        "credits": credits,
        "uses_fast_daily_quota": False,
        "requires_login": requires_login,
        "pricing_version": pricing_version,
    }
    if credits_member is not None:
        cfg["credits_member"] = credits_member
    return cfg


def default_dance_pricing_config() -> dict:
    return {
        "type": "per_second",
        "credits_per_second": DANCE_CREDITS_PER_SECOND,
        "credits_per_second_member": DANCE_CREDITS_PER_SECOND_MEMBER,
        "min_credits": DANCE_MIN_CREDITS,
        "requires_login": True,
        "pricing_version": DANCE_PRICING_VERSION,
    }


def dance_credits_from_pricing_config(
    pricing_config: dict | None,
    *,
    length: int = 10,
    is_member: bool = False,
) -> int:
    """Resolve Dance credits: per-second calculation based on video duration."""
    cfg = pricing_config or {}
    ptype = cfg.get("type", "per_second")
    if ptype == "fixed":
        free = int(cfg.get("credits", DANCE_CREDITS_FREE))
        member = int(cfg.get("credits_member", DANCE_CREDITS_MEMBER))
        return member if is_member else free

    rate_non_member = int(cfg.get("credits_per_second", DANCE_CREDITS_PER_SECOND))
    rate_member = int(cfg.get("credits_per_second_member", DANCE_CREDITS_PER_SECOND_MEMBER))
    rate = rate_member if is_member else rate_non_member
    min_credits = int(cfg.get("min_credits", DANCE_MIN_CREDITS))

    total = int(round(length * rate))
    return max(total, min_credits)


def image_credits_from_pricing_config(pricing_config: dict | None) -> int:
    """Credits for FIXED/quota image models (0 for free daily)."""
    return int((pricing_config or {}).get("credits", 0))


def pricing_uses_fast_daily_quota(pricing_config: dict | None) -> bool:
    cfg = pricing_config or {}
    if "uses_fast_daily_quota" in cfg:
        return bool(cfg["uses_fast_daily_quota"])
    return cfg.get("type") == "quota"


def pricing_requires_login(pricing_config: dict | None, *, default: bool) -> bool:
    cfg = pricing_config or {}
    if "requires_login" in cfg:
        return bool(cfg["requires_login"])
    return default


# --- AI Video (Pollo) defaults; live pricing lives on generation_models ---

VIDEO_MODEL_CODE: Final = "POLLO_V2_VIDEO"
VIDEO_PROVIDER_MODEL_REF: Final = "pollo-v2-0"
VIDEO_DEFAULT_LENGTH: Final = 5
VIDEO_DEFAULT_RESOLUTION: Final = "720p"
VIDEO_DEFAULT_ASPECT_RATIO: Final = "9:16"
VIDEO_SUPPORTED_LENGTHS: Final[tuple[int, ...]] = (5, 10)
VIDEO_SUPPORTED_RESOLUTIONS: Final[tuple[str, ...]] = ("480p", "720p", "1080p")
VIDEO_SUPPORTED_ASPECT_RATIOS: Final[tuple[str, ...]] = (
    "9:16",
    "16:9",
    "1:1",
    "4:3",
    "3:4",
)
VIDEO_PRICING_VERSION: Final = "video-v1"
# formula: credits = base × duration_mult × resolution_mult × audio_mult
VIDEO_CREDIT_BASE: Final = 15
VIDEO_DURATION_MULT: Final[dict[int, int]] = {5: 1, 10: 2}
VIDEO_RESOLUTION_MULT: Final[dict[str, int]] = {
    "480p": 1,
    "720p": 2,
    "1080p": 4,
}
VIDEO_AUDIO_MULT: Final[dict[bool, int]] = {False: 1, True: 4}


def video_credits(
    *, length: int, resolution: str, generate_audio: bool = False
) -> int:
    """Compute video credits from the BASE=15 formula (optional audio ×4)."""
    d = VIDEO_DURATION_MULT.get(length)
    r = VIDEO_RESOLUTION_MULT.get(resolution)
    if d is None:
        raise ValueError(f"unsupported video length: {length}")
    if r is None:
        raise ValueError(f"unsupported video resolution: {resolution}")
    a = VIDEO_AUDIO_MULT[bool(generate_audio)]
    return VIDEO_CREDIT_BASE * d * r * a


def video_credits_from_pricing_config(
    pricing_config: dict,
    *,
    length: int,
    resolution: str,
    generate_audio: bool = False,
) -> int:
    """
    Evaluate generation_models.pricing_config.

    FORMULA shape:
      base_credits, duration_mult, resolution_mult, optional audio_mult
    LOOKUP shape:
      table: {"5|720p|false": 30, ...}
    """
    ptype = (pricing_config or {}).get("type") or "formula"
    if ptype == "lookup":
        key = f"{length}|{resolution}|{str(generate_audio).lower()}"
        table = pricing_config.get("table") or {}
        if key not in table:
            raise ValueError(f"no lookup price for {key}")
        return int(table[key])

    # formula (default)
    base = int(pricing_config.get("base_credits", VIDEO_CREDIT_BASE))
    dmap = pricing_config.get("duration_mult") or VIDEO_DURATION_MULT
    rmap = pricing_config.get("resolution_mult") or VIDEO_RESOLUTION_MULT
    amap = pricing_config.get("audio_mult") or {
        "false": VIDEO_AUDIO_MULT[False],
        "true": VIDEO_AUDIO_MULT[True],
    }
    d = dmap.get(str(length), dmap.get(length))
    r = rmap.get(resolution)
    a = amap.get(str(generate_audio).lower(), VIDEO_AUDIO_MULT[bool(generate_audio)])
    if d is None or r is None:
        raise ValueError("unsupported length or resolution for formula pricing")
    return int(base) * int(d) * int(r) * int(a)


def default_video_pricing_config() -> dict:
    return {
        "type": "formula",
        "base_credits": VIDEO_CREDIT_BASE,
        "duration_mult": {str(k): v for k, v in VIDEO_DURATION_MULT.items()},
        "resolution_mult": dict(VIDEO_RESOLUTION_MULT),
        "audio_mult": {
            "false": VIDEO_AUDIO_MULT[False],
            "true": VIDEO_AUDIO_MULT[True],
        },
        "member_discount": None,
    }


@dataclass(frozen=True, slots=True)
class ProductSeed:
    code: ProductCode
    name: str
    product_type: ProductType
    plan_code: MembershipPlan | None
    billing_interval: BillingInterval | None
    credits_granted: int
    amount_minor: int
    currency: str
    provider_product_id: str


# Sandbox Dodo product ids (from merchant dashboard 2026-07-21)
SANDBOX_PRODUCT_SEEDS: Final[tuple[ProductSeed, ...]] = (
    ProductSeed(
        code=ProductCode.CREATOR_MONTHLY,
        name="RenderPop Creator Monthly",
        product_type=ProductType.SUBSCRIPTION,
        plan_code=MembershipPlan.CREATOR,
        billing_interval=BillingInterval.MONTH,
        credits_granted=SUBSCRIPTION_CREDITS[MembershipPlan.CREATOR],
        amount_minor=999,  # $9.99
        currency="USD",
        provider_product_id="pdt_0NjeYw0jgwlkQVQqGtrVr",
    ),
    ProductSeed(
        code=ProductCode.PRO_MONTHLY,
        name="RenderPop Pro Monthly",
        product_type=ProductType.SUBSCRIPTION,
        plan_code=MembershipPlan.PRO,
        billing_interval=BillingInterval.MONTH,
        credits_granted=SUBSCRIPTION_CREDITS[MembershipPlan.PRO],
        amount_minor=1999,
        currency="USD",
        provider_product_id="pdt_0NjeZBaaoslC6lRSEusue",
    ),
    ProductSeed(
        code=ProductCode.CREDIT_400,
        name="RenderPop 400 Credits",
        product_type=ProductType.CREDIT_PACK,
        plan_code=None,
        billing_interval=None,
        credits_granted=400,
        amount_minor=499,
        currency="USD",
        provider_product_id="pdt_0NjeZKiCGZeN20mcUv3f7",
    ),
    ProductSeed(
        code=ProductCode.CREDIT_900,
        name="RenderPop 900 Credits",
        product_type=ProductType.CREDIT_PACK,
        plan_code=None,
        billing_interval=None,
        credits_granted=900,
        amount_minor=999,
        currency="USD",
        provider_product_id="pdt_0NjeZTrMPp2krJqSndzD6",
    ),
    ProductSeed(
        code=ProductCode.CREDIT_2000,
        name="RenderPop 2,000 Credits",
        product_type=ProductType.CREDIT_PACK,
        plan_code=None,
        billing_interval=None,
        credits_granted=2000,
        amount_minor=1999,
        currency="USD",
        provider_product_id="pdt_0NjeZdL1H1VzhrOlhvDFZ",
    ),
)
