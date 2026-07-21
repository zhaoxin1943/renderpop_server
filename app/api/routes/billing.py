from typing import Any

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.core.deps import BillingServiceDep, UserIdDep
from app.core.errors import AppError

router = APIRouter(prefix="/v1/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    product_code: str
    success_url: str | None = None
    cancel_url: str | None = None


@router.get("/products")
async def list_products(service: BillingServiceDep) -> dict[str, Any]:
    return {"items": await service.list_products()}


@router.post("/checkout-sessions")
async def create_checkout(
    body: CheckoutBody,
    service: BillingServiceDep,
    user_id: UserIdDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not idempotency_key:
        raise AppError("VALIDATION_ERROR", "Idempotency-Key header required", 422)
    return await service.create_checkout(
        user_id=user_id,
        product_code=body.product_code,
        idempotency_key=idempotency_key,
        success_url=body.success_url,
    )


@router.post("/webhooks/dodo")
async def dodo_webhook(
    request: Request,
    service: BillingServiceDep,
) -> dict[str, Any]:
    raw = await request.body()
    signature = request.headers.get("webhook-signature") or request.headers.get(
        "x-dodo-signature"
    )
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid_json"}
    # re-parse from raw for consistency
    import json

    payload = json.loads(raw.decode("utf-8"))
    result = await service.process_webhook(
        raw_body=raw, signature=signature, payload=payload
    )
    if not result.get("ok") and result.get("error") == "invalid_signature":
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="invalid signature")
    return result
