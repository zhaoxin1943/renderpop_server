from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.repo.base import BaseRepo


class ProductRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_active(self, environment: str) -> list[Product]:
        stmt = (
            select(Product)
            .where(
                Product.environment == environment,
                Product.is_active.is_(True),
                Product.deleted_at.is_(None),
            )
            .order_by(Product.product_type.desc(), Product.amount_minor.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, environment: str, code: str) -> Product | None:
        stmt = select(Product).where(
            Product.environment == environment,
            Product.code == code,
            Product.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_id(self, environment: str, provider_product_id: str) -> Product | None:
        stmt = select(Product).where(
            Product.environment == environment,
            Product.provider_product_id == provider_product_id,
            Product.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
