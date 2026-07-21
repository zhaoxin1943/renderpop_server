import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.deps import BillingServiceDep, UserIdDep
from app.core.errors import AppError
from app.schemas.billing import (
    CheckoutBody,
    CheckoutSessionResponse,
    DodoWebhookResponse,
    ProductListResponse,
)

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/products", response_model=ProductListResponse)
async def list_products(service: BillingServiceDep) -> ProductListResponse:
    return ProductListResponse(items=await service.list_products())


@router.post("/checkout-sessions", response_model=CheckoutSessionResponse)
async def create_checkout(
    body: CheckoutBody,
    service: BillingServiceDep,
    user_id: UserIdDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CheckoutSessionResponse:
    if not idempotency_key:
        raise AppError("VALIDATION_ERROR", "Idempotency-Key header required", 422)
    return await service.create_checkout(
        user_id=user_id,
        product_code=body.product_code,
        idempotency_key=idempotency_key,
        success_url=body.success_url,
    )


@router.post("/webhooks/dodo", response_model=DodoWebhookResponse)
async def dodo_webhook(
    request: Request,
    service: BillingServiceDep,
) -> DodoWebhookResponse:
    raw = await request.body()
    signature = request.headers.get("webhook-signature") or request.headers.get(
        "x-dodo-signature"
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return DodoWebhookResponse(ok=False, error="invalid_json")
    result = await service.process_webhook(
        raw_body=raw, signature=signature, payload=payload
    )
    if not result.ok and result.error == "invalid_signature":
        raise HTTPException(status_code=401, detail="invalid signature")
    return result
