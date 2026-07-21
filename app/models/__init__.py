"""SQLModel table models. Import here so Alembic sees metadata."""

from app.models.anonymous_visitor import AnonymousVisitor
from app.models.asset import Asset
from app.models.base import (
    CreatedAtMixin,
    CreatedModel,
    IdMixin,
    SoftDeleteMixin,
    TimestampedModel,
    UpdatedAtMixin,
)
from app.models.credit import (
    CreditGrant,
    CreditReservation,
    CreditReservationItem,
    CreditTransaction,
)
from app.models.daily_usage import DailyUsageCounter
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.models.identity import Identity
from app.models.order import Order
from app.models.payment_event import PaymentEvent
from app.models.product import Product
from app.models.refund import Refund
from app.models.session import Session
from app.models.subscription import Subscription
from app.models.user import User

__all__ = [
    "AnonymousVisitor",
    "Asset",
    "CreatedAtMixin",
    "CreatedModel",
    "CreditGrant",
    "CreditReservation",
    "CreditReservationItem",
    "CreditTransaction",
    "DailyUsageCounter",
    "GenerationAttempt",
    "GenerationTask",
    "IdMixin",
    "Identity",
    "Order",
    "PaymentEvent",
    "Product",
    "Refund",
    "Session",
    "SoftDeleteMixin",
    "Subscription",
    "TimestampedModel",
    "UpdatedAtMixin",
    "User",
]
