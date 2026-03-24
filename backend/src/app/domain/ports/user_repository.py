from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        ...

    @abstractmethod
    async def list_by_tenant(self, page: int = 1, size: int = 20) -> tuple[list[User], int]:
        """List all users in the current tenant (filtered by do_orm_execute)."""
        ...

    @abstractmethod
    async def update(self, user_id: UUID, **kwargs) -> User | None:
        """Update user fields."""
        ...

    @abstractmethod
    async def deactivate(self, user_id: UUID) -> None:
        """Soft delete: set is_active=False."""
        ...
