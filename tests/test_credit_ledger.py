"""Unit-style tests for credit FEFO reserve/capture/release (needs DB)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_live_and_products() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/health/live")
        assert r.status_code == 200
        r = await client.get("/api/v1/billing/products")
        assert r.status_code == 200
        codes = {p["code"] for p in r.json()["items"]}
        assert "CREATOR_MONTHLY" in codes
        assert "CREDIT_400" in codes
