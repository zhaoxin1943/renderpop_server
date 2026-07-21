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
FAST_ASPECT_SIZES: Final[dict[str, tuple[int, int]]] = {
    "1:1": (1024, 1024),
    "3:4": (1024, 1536),
    "4:3": (1536, 1024),
}

ALLOWED_ASPECT_RATIOS: Final[frozenset[str]] = frozenset(FAST_ASPECT_SIZES.keys())


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
