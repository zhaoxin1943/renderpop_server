"""
Seed the 5 MVP products for sandbox (and empty live placeholders).

  conda activate renderpop
  python -m scripts.seed_products
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as module from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.commerce import SANDBOX_PRODUCT_SEEDS
from app.core.db import dispose_engine, get_session_factory
from app.models.base import new_id
from app.models.enums import PaymentProvider, ProductEnvironment
from app.models.product import Product


async def upsert_products(
    session: AsyncSession, environment: ProductEnvironment, seeds
) -> None:
    for seed in seeds:
        stmt = select(Product).where(
            Product.environment == environment,
            Product.code == seed.code,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.name = seed.name
            row.product_type = seed.product_type
            row.plan_code = seed.plan_code
            row.billing_interval = seed.billing_interval
            row.credits_granted = seed.credits_granted
            row.amount_minor = seed.amount_minor
            row.currency = seed.currency
            if environment == ProductEnvironment.SANDBOX:
                # Only auto-fill provider id for sandbox; live is manual
                row.provider_product_id = seed.provider_product_id
            row.is_active = True
            print(f"updated {environment}/{seed.code}")
        else:
            provider_id = (
                seed.provider_product_id
                if environment == ProductEnvironment.SANDBOX
                else f"REPLACE_ME_{seed.code}"
            )
            session.add(
                Product(
                    id=new_id(),
                    code=seed.code,
                    name=seed.name,
                    product_type=seed.product_type,
                    environment=environment,
                    plan_code=seed.plan_code,
                    billing_interval=seed.billing_interval,
                    credits_granted=seed.credits_granted,
                    amount_minor=seed.amount_minor,
                    currency=seed.currency,
                    provider=PaymentProvider.DODO,
                    provider_product_id=provider_id,
                    is_active=environment == ProductEnvironment.SANDBOX,
                )
            )
            print(f"created {environment}/{seed.code}")


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await upsert_products(session, ProductEnvironment.SANDBOX, SANDBOX_PRODUCT_SEEDS)
        await upsert_products(session, ProductEnvironment.LIVE, SANDBOX_PRODUCT_SEEDS)
        await session.commit()
    await dispose_engine()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
