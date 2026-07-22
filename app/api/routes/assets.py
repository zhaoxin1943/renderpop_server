from fastapi import APIRouter, status

from app.core.deps import AssetServiceDep, UserIdDep
from app.schemas.asset import (
    AssetResponse,
    CompleteUploadBody,
    CreateUploadIntentBody,
    UploadIntentResponse,
)

router = APIRouter(prefix="/v1/assets", tags=["assets"])


@router.post(
    "/upload-intents",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_intent(
    body: CreateUploadIntentBody,
    service: AssetServiceDep,
    user_id: UserIdDep,
) -> UploadIntentResponse:
    return await service.create_upload_intent(
        user_id=user_id,
        filename=body.filename,
        content_type=body.content_type,
        byte_size=body.byte_size,
        purpose=body.purpose,
    )


@router.post("/{asset_id}/complete", response_model=AssetResponse)
async def complete_upload(
    asset_id: str,
    service: AssetServiceDep,
    user_id: UserIdDep,
    body: CompleteUploadBody | None = None,
) -> AssetResponse:
    _ = body
    return await service.complete_upload(asset_id=asset_id, user_id=user_id)
