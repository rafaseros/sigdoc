from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.user_repository import UserRepository
from app.infrastructure.persistence.models.user import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_email(self, email: str):
        # Query WITHOUT tenant filter since we don't know
        # the tenant yet at login time.
        stmt = select(UserModel).where(
            UserModel.email == email,
            UserModel.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID):
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user):
        # For MVP, not needed beyond seed
        raise NotImplementedError
