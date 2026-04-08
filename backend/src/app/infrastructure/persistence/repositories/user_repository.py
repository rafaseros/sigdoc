from uuid import UUID

from sqlalchemy import func, select
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

    async def create(self, user: UserModel) -> UserModel:
        self._session.add(user)
        await self._session.flush()
        return user

    async def list_by_tenant(self, page: int = 1, size: int = 20) -> tuple[list, int]:
        """List all users in the tenant (auto-filtered by do_orm_execute)."""
        count_stmt = select(func.count()).select_from(UserModel)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = (
            select(UserModel)
            .order_by(UserModel.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self._session.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def update(self, user_id: UUID, **kwargs) -> UserModel | None:
        """Update user fields."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self._session.flush()
        return user

    async def deactivate(self, user_id: UUID) -> None:
        """Soft delete: set is_active=False."""
        user = await self.get_by_id(user_id)
        if user:
            user.is_active = False
            await self._session.flush()

    async def count_active_by_tenant(self, tenant_id: UUID) -> int:
        """Return the count of active users in the given tenant."""
        stmt = select(func.count()).select_from(UserModel).where(
            UserModel.tenant_id == tenant_id,
            UserModel.is_active == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_admins_by_tenant(self, tenant_id: UUID) -> int:
        """Return the count of active admin users in the given tenant."""
        stmt = select(func.count()).select_from(UserModel).where(
            UserModel.tenant_id == tenant_id,
            UserModel.is_active == True,  # noqa: E712
            UserModel.role == "admin",
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_verification_token(self, token: str) -> UserModel | None:
        """Find a user by their email verification token."""
        stmt = select(UserModel).where(UserModel.email_verification_token == token)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: str) -> UserModel | None:
        """Find a user by their password reset token."""
        stmt = select(UserModel).where(UserModel.password_reset_token == token)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
