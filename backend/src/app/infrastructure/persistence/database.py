import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import ForeignKey, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column, with_loader_criteria

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


class TenantMixin:
    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        )


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(orm_execute_state):
    if (
        orm_execute_state.is_select
        and not orm_execute_state.is_column_load
        and not orm_execute_state.is_relationship_load
    ):
        tenant_id = orm_execute_state.session.info.get("tenant_id")
        if tenant_id:
            orm_execute_state.statement = orm_execute_state.statement.options(
                with_loader_criteria(
                    TenantMixin,
                    lambda cls: cls.tenant_id == tenant_id,
                    include_aliases=True,
                )
            )


async def get_session(
    tenant_id: str | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        if tenant_id:
            session.info["tenant_id"] = uuid.UUID(tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
