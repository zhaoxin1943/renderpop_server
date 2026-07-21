from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.enums import IdentityProvider
from app.models.identity import Identity
from app.models.session import Session
from app.models.user import User
from app.repo.base import BaseRepo


class UserRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_identity(
        self, provider: IdentityProvider | str, provider_subject: str
    ) -> Identity | None:
        stmt = select(Identity).where(
            Identity.provider == provider,
            Identity.provider_subject == provider_subject,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_identity(self, identity: Identity) -> Identity:
        self.session.add(identity)
        await self.session.flush()
        await self.session.refresh(identity)
        return identity

    async def create_session(self, session_row: Session) -> Session:
        self.session.add(session_row)
        await self.session.flush()
        await self.session.refresh(session_row)
        return session_row

    async def get_session_by_token_hash(self, token_hash: str) -> Session | None:
        stmt = select(Session).where(Session.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
