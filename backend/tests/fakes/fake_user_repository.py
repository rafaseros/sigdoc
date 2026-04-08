from uuid import UUID

from app.domain.entities import User
from app.domain.ports.user_repository import UserRepository


class FakeUserRepository(UserRepository):
    """Dict-backed in-memory implementation of UserRepository for testing."""

    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        # Secondary index: email → user_id for fast lookup
        self._by_email: dict[str, UUID] = {}

    async def get_by_email(self, email: str) -> User | None:
        user_id = self._by_email.get(email)
        if user_id is None:
            return None
        user = self._users.get(user_id)
        # Mirror real repo: only return active users
        if user is None or not user.is_active:
            return None
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def create(self, user: User) -> User:
        self._users[user.id] = user
        self._by_email[user.email] = user.id
        return user

    async def list_by_tenant(
        self, page: int = 1, size: int = 20
    ) -> tuple[list[User], int]:
        """Return all users (fake does not filter by tenant — tests control data)."""
        items = list(self._users.values())
        total = len(items)
        offset = (page - 1) * size
        page_items = items[offset : offset + size]
        return page_items, total

    async def update(self, user_id: UUID, **kwargs) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        # Keep email index in sync if email changed
        if "email" in kwargs:
            # Remove old email index entries for this user_id
            stale_emails = [
                e for e, uid in self._by_email.items() if uid == user_id
            ]
            for e in stale_emails:
                del self._by_email[e]
            self._by_email[user.email] = user_id
        return user

    async def deactivate(self, user_id: UUID) -> None:
        user = self._users.get(user_id)
        if user is not None:
            user.is_active = False

    async def count_active_by_tenant(self, tenant_id: UUID) -> int:
        """Return count of active users in the given tenant."""
        return sum(
            1
            for u in self._users.values()
            if u.tenant_id == tenant_id and u.is_active
        )

    async def count_admins_by_tenant(self, tenant_id: UUID) -> int:
        """Return count of active admin users in the given tenant."""
        return sum(
            1
            for u in self._users.values()
            if u.tenant_id == tenant_id and u.is_active and u.role == "admin"
        )

    async def get_by_verification_token(self, token: str) -> "User | None":
        """Find a user by their email verification token."""
        for u in self._users.values():
            if getattr(u, "email_verification_token", None) == token:
                return u
        return None

    async def get_by_reset_token(self, token: str) -> "User | None":
        """Find a user by their password reset token."""
        for u in self._users.values():
            if getattr(u, "password_reset_token", None) == token:
                return u
        return None
