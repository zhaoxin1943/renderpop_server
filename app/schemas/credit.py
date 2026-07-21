"""Credit wallet public API shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CreditTxnType


class CreditBalanceResponse(BaseModel):
    available: int
    reserved: int
    expiring_soon: int
    next_expiration_at: datetime | None = None


class CreditTransactionResponse(BaseModel):
    id: str
    type: CreditTxnType | str
    amount: int = Field(description="Signed amount from user perspective")
    generation_task_id: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class CreditTransactionListResponse(BaseModel):
    items: list[CreditTransactionResponse]
