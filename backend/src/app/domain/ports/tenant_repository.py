from abc import ABC, abstractmethod

from app.domain.entities.tenant import Tenant


class TenantRepository(ABC):
    @abstractmethod
    async def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant and return it with its persisted state."""
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Tenant | None:
        """Return the tenant with the given name, or None if not found."""
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Return the tenant with the given slug, or None if not found."""
        ...
