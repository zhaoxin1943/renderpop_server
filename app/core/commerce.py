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

RH_FAST_APP_ID: Final = "2016540100959674370"
RH_PRO_APP_ID: Final = "2070881747880992769"

PRO_DEFAULT_QUALITY: Final = "medium"
PRO_DEFAULT_RESOLUTION: Final = "2k"
FAST_DEFAULT_SCALE_BY: Final = "1.5"

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
