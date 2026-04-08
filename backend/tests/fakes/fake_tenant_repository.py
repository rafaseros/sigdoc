from app.domain.entities.tenant import Tenant
from app.domain.ports.tenant_repository import TenantRepository


class FakeTenantRepository(TenantRepository):
    """Dict-backed in-memory implementation of TenantRepository for testing."""

    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_name: dict[str, object] = {}
        self._by_slug: dict[str, object] = {}

    async def create(self, tenant: Tenant) -> Tenant:
        self._by_id[tenant.id] = tenant
        self._by_name[tenant.name] = tenant
        self._by_slug[tenant.slug] = tenant
        return tenant

    async def get_by_name(self, name: str) -> Tenant | None:
        return self._by_name.get(name)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        return self._by_slug.get(slug)
