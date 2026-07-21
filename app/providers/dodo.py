"""Dodo Payments Checkout Session client."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Official API base (test vs live share host; key selects mode)
DODO_API_BASE = "https://api.dodopayments.com"


class DodoClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.dodo_api_key
        self._env = settings.dodo_environment

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    async def create_checkout_session(
        self,
        *,
        product_id: str,
        return_url: str,
        customer_email: str | None,
        customer_name: str | None,
        metadata: dict[str, str],
    ) -> dict[str, Any]:
        if not self._key:
            # Dev stub
            session_id = f"cks_stub_{metadata.get('order_id', 'x')[:8]}"
            return {
                "session_id": session_id,
                "checkout_url": f"https://test.checkout.dodopayments.com/session/{session_id}",
                "_stub": True,
            }

        body: dict[str, Any] = {
            "product_cart": [{"product_id": product_id, "quantity": 1}],
            "return_url": return_url,
            "metadata": metadata,
        }
        if customer_email:
            body["customer"] = {
                "email": customer_email,
                "name": customer_name or customer_email,
            }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Checkout Sessions API path per Dodo docs
            resp = await client.post(
                f"{DODO_API_BASE}/checkouts",
                headers=self._headers(),
                json=body,
            )
            if resp.status_code >= 400:
                logger.error("Dodo checkout error %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.json()

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature_header: str | None,
    ) -> bool:
        """
        Best-effort HMAC verification.

        Exact header scheme depends on Dodo webhook config; when webhook key
        is empty (dev), accept. Production must set DODO_WEBHOOK_KEY.
        """
        secret = self._settings.dodo_webhook_key
        if not secret:
            if self._settings.is_production:
                return False
            return True
        if not signature_header:
            return False
        # Common pattern: hex HMAC-SHA256 of raw body
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        # Header may be "sha256=<hex>" or raw hex
        provided = signature_header.removeprefix("sha256=")
        return hmac.compare_digest(expected, provided)
