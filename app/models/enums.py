"""
Domain StrEnums — single source of truth for persisted status/type values.

Stored as VARCHAR (native_enum=False) so schema stays portable and values can
evolve without MySQL ENUM ALTER migrations.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.types import TypeEngine


def sa_str_enum[E: StrEnum](enum_cls: type[E], *, length: int = 32) -> TypeEngine[E]:
    """VARCHAR-backed SQLAlchemy enum type (no DB-native ENUM)."""
    return SAEnum(
        enum_cls,
        values_callable=lambda obj: [item.value for item in obj],
        native_enum=False,
        length=length,
        validate_strings=True,
    )


# ---------------------------------------------------------------------------
# User / identity
# ---------------------------------------------------------------------------


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class IdentityProvider(StrEnum):
    GOOGLE = "google"
    EMAIL = "email"


# ---------------------------------------------------------------------------
# Plans / products / commerce
# ---------------------------------------------------------------------------


class PlanCode(StrEnum):
    """Quota / membership plan keys. FREE and VISITOR are not paid memberships."""

    FREE = "FREE"
    CREATOR = "CREATOR"
    PRO = "PRO"
    VISITOR = "VISITOR"


class MembershipPlan(StrEnum):
    """Paid membership plans stored on subscriptions / product.plan_code."""

    CREATOR = "CREATOR"
    PRO = "PRO"


class ProductCode(StrEnum):
    CREATOR_MONTHLY = "CREATOR_MONTHLY"
    PRO_MONTHLY = "PRO_MONTHLY"
    CREDIT_400 = "CREDIT_400"
    CREDIT_900 = "CREDIT_900"
    CREDIT_2000 = "CREDIT_2000"


class ProductType(StrEnum):
    SUBSCRIPTION = "SUBSCRIPTION"
    CREDIT_PACK = "CREDIT_PACK"


class ProductEnvironment(StrEnum):
    SANDBOX = "sandbox"
    LIVE = "live"


class BillingInterval(StrEnum):
    MONTH = "month"


class PaymentProvider(StrEnum):
    DODO = "dodo"


# ---------------------------------------------------------------------------
# Orders / subscriptions / payments
# ---------------------------------------------------------------------------


class OrderType(StrEnum):
    SUBSCRIPTION = "SUBSCRIPTION"
    CREDIT_PACK = "CREDIT_PACK"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    EXPIRED = "EXPIRED"


class SubscriptionStatus(StrEnum):
    INCOMPLETE = "INCOMPLETE"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class PaymentEventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class RefundStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------


class CreditGrantType(StrEnum):
    SIGNUP_BONUS = "SIGNUP_BONUS"
    PROMO = "PROMO"
    SUBSCRIPTION = "SUBSCRIPTION"
    PURCHASED = "PURCHASED"
    COMPENSATION = "COMPENSATION"


class CreditSourceType(StrEnum):
    ORDER = "ORDER"
    SUBSCRIPTION_PERIOD = "SUBSCRIPTION_PERIOD"
    SIGNUP = "SIGNUP"
    PROMO = "PROMO"
    ADMIN = "ADMIN"
    REFUND = "REFUND"


class CreditGrantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    EXHAUSTED = "EXHAUSTED"


class CreditTxnType(StrEnum):
    GRANT = "GRANT"
    RESERVE = "RESERVE"
    CAPTURE = "CAPTURE"
    RELEASE = "RELEASE"
    EXPIRE = "EXPIRE"
    REVOKE = "REVOKE"
    ADJUST = "ADJUST"


class CreditReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CAPTURED = "CAPTURED"
    RELEASED = "RELEASED"


# ---------------------------------------------------------------------------
# Generation / assets
# ---------------------------------------------------------------------------


class TaskType(StrEnum):
    FAST_IMAGE = "FAST_IMAGE"
    PRO_IMAGE = "PRO_IMAGE"
    TEXT_VIDEO = "TEXT_VIDEO"
    IMAGE_VIDEO = "IMAGE_VIDEO"
    DANCE_VIDEO = "DANCE_VIDEO"  # reserved (templates / face)


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    MODERATING = "MODERATING"
    QUEUED = "QUEUED"
    SUBMITTING = "SUBMITTING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"

    @classmethod
    def active(cls) -> frozenset[TaskStatus]:
        """In-flight statuses that count against concurrent job limits."""
        return frozenset(
            {
                cls.CREATED,
                cls.MODERATING,
                cls.QUEUED,
                cls.SUBMITTING,
                cls.PROCESSING,
                cls.CANCEL_REQUESTED,
            }
        )

    @classmethod
    def terminal(cls) -> frozenset[TaskStatus]:
        return frozenset(
            {
                cls.SUCCEEDED,
                cls.FAILED,
                cls.CANCELED,
                cls.REJECTED,
                cls.EXPIRED,
            }
        )

    @classmethod
    def submittable(cls) -> frozenset[TaskStatus]:
        return frozenset({cls.CREATED, cls.QUEUED})

    @classmethod
    def pollable(cls) -> frozenset[TaskStatus]:
        return frozenset({cls.PROCESSING, cls.SUBMITTING})


class TransferStatus(StrEnum):
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class GenerationProvider(StrEnum):
    RUNNINGHUB = "runninghub"
    POLLO = "pollo"


class ModelModality(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class GenerationModelStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class PricingType(StrEnum):
    FIXED = "FIXED"
    FORMULA = "FORMULA"
    LOOKUP = "LOOKUP"


class PolloTaskStatus(StrEnum):
    """External Pollo generation status strings."""

    WAITING = "waiting"
    PROCESSING = "processing"
    SUCCEED = "succeed"
    FAILED = "failed"


class AttemptStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class AssetType(StrEnum):
    INPUT_IMAGE = "INPUT_IMAGE"
    OUTPUT_IMAGE = "OUTPUT_IMAGE"
    OUTPUT_VIDEO = "OUTPUT_VIDEO"
    THUMBNAIL = "THUMBNAIL"


class AssetStatus(StrEnum):
    UPLOADING = "UPLOADING"
    READY = "READY"
    PENDING_TRANSFER = "PENDING_TRANSFER"
    QUARANTINED = "QUARANTINED"
    DELETED = "DELETED"


class PricingMode(StrEnum):
    FREE_DAILY = "free_daily"
    CREDITS = "credits"


class FailureCode(StrEnum):
    PROVIDER_SUBMIT_FAILED = "PROVIDER_SUBMIT_FAILED"
    PROVIDER_FAILED = "PROVIDER_FAILED"


class RunningHubStatus(StrEnum):
    """External RunningHub task status strings (mapped at provider boundary)."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"


# ---------------------------------------------------------------------------
# Usage counters
# ---------------------------------------------------------------------------


class UsageSubjectType(StrEnum):
    USER = "USER"
    VISITOR = "VISITOR"
    IP_RISK_BUCKET = "IP_RISK_BUCKET"


class UsageFeature(StrEnum):
    FAST_IMAGE = "FAST_IMAGE"
