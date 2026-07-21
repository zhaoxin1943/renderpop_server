"""Checkout + webhook fulfillment for Dodo products."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.models.base import new_id
from app.models.order import Order
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription
from app.providers.dodo import DodoClient
from app.repo.order_repo import OrderRepo
from app.repo.product_repo import ProductRepo
from app.repo.subscription_repo import SubscriptionRepo
from app.service.credit_service import CreditService

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(
        self,
        product_repo: ProductRepo,
        order_repo: OrderRepo,
        subscription_repo: SubscriptionRepo,
        credit_service: CreditService,
        settings: Settings,
        dodo: DodoClient | None = None,
    ) -> None:
        self._products = product_repo
        self._orders = order_repo
        self._subs = subscription_repo
        self._credits = credit_service
        self._settings = settings
        self._dodo = dodo or DodoClient(settings)

    def _env(self) -> str:
        return self._settings.product_environment

    async def list_products(self) -> list[dict[str, Any]]:
        rows = await self._products.list_active(self._env())
        return [
            {
                "code": p.code,
                "name": p.name,
                "product_type": p.product_type,
                "plan_code": p.plan_code,
                "billing_interval": p.billing_interval,
                "credits_granted": p.credits_granted,
                "amount_minor": p.amount_minor,
                "currency": p.currency,
                "environment": p.environment,
            }
            for p in rows
        ]

    def _validate_return_url(self, url: str) -> None:
        allowed_host = urlparse(self._settings.web_origin).netloc
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValidationFailed("invalid return_url")
        # Allow web_origin host only
        if parsed.netloc != allowed_host and not self._settings.is_development:
            raise ValidationFailed("return_url host not allowed")

    async def create_checkout(
        self,
        *,
        user_id: str,
        product_code: str,
        idempotency_key: str,
        success_url: str | None,
        customer_email: str | None = None,
        customer_name: str | None = None,
    ) -> dict[str, Any]:
        existing = await self._orders.get_by_idempotency(user_id, idempotency_key)
        if existing and existing.provider_checkout_id:
            return {
                "order_id": existing.id,
                "status": existing.status,
                "checkout_url": None,
                "session_id": existing.provider_checkout_id,
                "reused": True,
            }

        product = await self._products.get_by_code(self._env(), product_code)
        if product is None or not product.is_active:
            raise NotFound("Product not found")

        return_url = success_url or self._settings.dodo_return_url
        self._validate_return_url(return_url)

        snapshot = {
            "code": product.code,
            "name": product.name,
            "product_type": product.product_type,
            "plan_code": product.plan_code,
            "credits_granted": product.credits_granted,
            "amount_minor": product.amount_minor,
            "currency": product.currency,
            "provider_product_id": product.provider_product_id,
            "environment": product.environment,
            "config_version": product.config_version,
        }

        if existing:
            order = existing
        else:
            order = Order(
                id=new_id(),
                user_id=user_id,
                order_type=product.product_type,
                status="PENDING",
                product_code=product.code,
                product_id=product.id,
                product_snapshot=snapshot,
                amount_minor=product.amount_minor,
                currency=product.currency,
                payment_provider="dodo",
                idempotency_key=idempotency_key,
            )
            await self._orders.add(order)

        session = await self._dodo.create_checkout_session(
            product_id=product.provider_product_id,
            return_url=return_url,
            customer_email=customer_email,
            customer_name=customer_name,
            metadata={
                "order_id": order.id,
                "user_id": user_id,
                "product_code": product.code,
            },
        )
        order.provider_checkout_id = session.get("session_id")
        await self._orders.session.flush()

        return {
            "order_id": order.id,
            "status": order.status,
            "checkout_url": session.get("checkout_url"),
            "session_id": session.get("session_id"),
            "reused": False,
            "stub": bool(session.get("_stub")),
        }

    async def process_webhook(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._dodo.verify_webhook_signature(
            payload=raw_body, signature_header=signature
        ):
            return {"ok": False, "error": "invalid_signature"}

        event_type = str(payload.get("type") or payload.get("event_type") or "")
        # Dodo-style: data object may nest under data
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        event_id = str(
            payload.get("event_id")
            or payload.get("id")
            or data.get("event_id")
            or f"{event_type}:{data.get('payment_id') or data.get('subscription_id') or new_id()}"
        )

        existing = await self._orders.get_event("dodo", event_id)
        if existing and existing.status == "PROCESSED":
            return {"ok": True, "duplicate": True}

        if existing is None:
            event = PaymentEvent(
                id=new_id(),
                provider="dodo",
                event_id=event_id,
                event_type=event_type or "unknown",
                status="PROCESSING",
                payload=payload,
                attempt_count=1,
            )
            await self._orders.add_event(event)
        else:
            event = existing
            event.status = "PROCESSING"
            event.attempt_count += 1

        try:
            await self._dispatch_event(event_type, data, event)
            event.status = "PROCESSED"
            event.processed_at = datetime.now(UTC)
            event.error_message = None
        except Exception as exc:
            logger.exception("webhook processing failed event=%s", event_id)
            event.status = "FAILED"
            event.error_message = str(exc)[:1000]
            await self._orders.session.flush()
            raise

        await self._orders.session.flush()
        return {"ok": True, "event_id": event_id, "type": event_type}

    async def _dispatch_event(
        self, event_type: str, data: dict[str, Any], event: PaymentEvent
    ) -> None:
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        order_id = metadata.get("order_id")
        if order_id:
            event.order_id = order_id

        if event_type in ("payment.succeeded", "payment.success"):
            await self._on_payment_succeeded(data, metadata)
        elif event_type in (
            "subscription.active",
            "subscription.renewed",
        ):
            await self._on_subscription_active(data, metadata, renewed=event_type.endswith("renewed"))
        elif event_type == "subscription.on_hold":
            await self._on_subscription_status(data, "ON_HOLD")
        elif event_type == "subscription.cancelled":
            await self._on_subscription_status(data, "CANCELED", cancel=True)
        elif event_type == "subscription.expired":
            await self._on_subscription_status(data, "EXPIRED", ended=True)
        elif event_type == "subscription.failed":
            await self._on_subscription_status(data, "FAILED", ended=True)
        else:
            event.status = "IGNORED"
            logger.info("Ignoring webhook type=%s", event_type)

    async def _on_payment_succeeded(
        self, data: dict[str, Any], metadata: dict[str, Any]
    ) -> None:
        """Credit packs: grant on payment.succeeded. Skip subscription payments (handled by sub events)."""
        order_id = metadata.get("order_id")
        payment_id = str(data.get("payment_id") or data.get("id") or "")
        if not order_id:
            logger.warning("payment.succeeded without order_id metadata")
            return

        order = await self._orders.get(order_id)
        if order is None:
            logger.warning("order not found %s", order_id)
            return

        if order.order_type == "SUBSCRIPTION":
            # Membership credits come from subscription.active/renewed
            order.provider_payment_id = payment_id or order.provider_payment_id
            if order.status == "PENDING":
                order.status = "PAID"
                order.paid_at = datetime.now(UTC)
            return

        if order.status == "PAID":
            return

        order.status = "PAID"
        order.paid_at = datetime.now(UTC)
        order.provider_payment_id = payment_id or order.provider_payment_id

        credits = 0
        if order.product_snapshot:
            credits = int(order.product_snapshot.get("credits_granted") or 0)
        if credits > 0 and payment_id:
            await self._credits.grant_purchased_pack(
                user_id=order.user_id,
                amount=credits,
                order_id=order.id,
                payment_id=payment_id,
                product_code=order.product_code,
            )

    async def _on_subscription_active(
        self,
        data: dict[str, Any],
        metadata: dict[str, Any],
        *,
        renewed: bool,
    ) -> None:
        provider_sub_id = str(
            data.get("subscription_id") or data.get("id") or ""
        )
        if not provider_sub_id:
            return

        user_id = metadata.get("user_id")
        order_id = metadata.get("order_id")
        product_code = metadata.get("product_code")
        plan_code = None
        credits_granted = 0

        order = await self._orders.get(order_id) if order_id else None
        if order:
            user_id = user_id or order.user_id
            product_code = product_code or order.product_code
            if order.product_snapshot:
                plan_code = order.product_snapshot.get("plan_code")
                credits_granted = int(order.product_snapshot.get("credits_granted") or 0)
            order.status = "PAID"
            order.paid_at = order.paid_at or datetime.now(UTC)
            order.provider_subscription_id = provider_sub_id

        if not user_id:
            logger.warning("subscription event missing user_id")
            return

        # Resolve product if needed
        if not plan_code and product_code:
            product = await self._products.get_by_code(self._env(), product_code)
            if product:
                plan_code = product.plan_code
                credits_granted = product.credits_granted

        plan_code = plan_code or "CREATOR"

        period_start = _parse_dt(
            data.get("current_period_start") or data.get("previous_billing_date")
        ) or datetime.now(UTC)
        period_end = _parse_dt(
            data.get("current_period_end") or data.get("next_billing_date")
        )

        sub = await self._subs.get_by_provider_id("dodo", provider_sub_id)
        if sub is None:
            sub = Subscription(
                id=new_id(),
                user_id=user_id,
                plan_code=plan_code,
                product_code=product_code or f"{plan_code}_MONTHLY",
                provider="dodo",
                provider_customer_id=str(data.get("customer_id") or "") or None,
                provider_subscription_id=provider_sub_id,
                status="ACTIVE",
                current_period_start=period_start,
                current_period_end=period_end,
                last_synced_at=datetime.now(UTC),
            )
            await self._subs.add(sub)
        else:
            sub.status = "ACTIVE"
            sub.plan_code = plan_code
            sub.current_period_start = period_start
            sub.current_period_end = period_end
            sub.last_synced_at = datetime.now(UTC)
            sub.ended_at = None

        await self._credits.grant_subscription_period(
            user_id=user_id,
            plan_code=plan_code,
            provider_subscription_id=provider_sub_id,
            period_start=period_start,
            period_end=period_end,
        )
        logger.info(
            "subscription %s user=%s plan=%s renewed=%s credits=%s",
            provider_sub_id,
            user_id,
            plan_code,
            renewed,
            credits_granted,
        )

    async def _on_subscription_status(
        self,
        data: dict[str, Any],
        status: str,
        *,
        cancel: bool = False,
        ended: bool = False,
    ) -> None:
        provider_sub_id = str(data.get("subscription_id") or data.get("id") or "")
        if not provider_sub_id:
            return
        sub = await self._subs.get_by_provider_id("dodo", provider_sub_id)
        if sub is None:
            return
        sub.status = status
        sub.last_synced_at = datetime.now(UTC)
        if cancel:
            sub.cancel_at_period_end = True
            sub.canceled_at = datetime.now(UTC)
        if ended:
            sub.ended_at = datetime.now(UTC)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            # ISO
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None
