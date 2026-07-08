from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TemplatePreset
from app.domain.exceptions import PresetNameCollisionError
from app.domain.ports.template_preset_repository import (
    TemplatePresetRepository as TemplatePresetRepositoryPort,
)
from app.infrastructure.persistence.models.template_preset import TemplatePresetModel


def _to_entity(model: TemplatePresetModel) -> TemplatePreset:
    return TemplatePreset(
        id=model.id,
        tenant_id=model.tenant_id,
        template_id=model.template_id,
        name=model.name,
        values=model.values or {},
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyTemplatePresetRepository(TemplatePresetRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, preset: TemplatePreset) -> TemplatePreset:
        model = TemplatePresetModel(
            id=preset.id,
            tenant_id=preset.tenant_id,
            template_id=preset.template_id,
            name=preset.name,
            values=preset.values,
            created_by=preset.created_by,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise PresetNameCollisionError(preset.name) from exc

        preset.created_at = model.created_at
        preset.updated_at = model.updated_at
        return preset

    async def get_by_id(self, preset_id: UUID) -> TemplatePreset | None:
        stmt = select(TemplatePresetModel).where(TemplatePresetModel.id == preset_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_entity(model)

    async def list_by_template(self, template_id: UUID) -> list[TemplatePreset]:
        stmt = (
            select(TemplatePresetModel)
            .where(TemplatePresetModel.template_id == template_id)
            .order_by(TemplatePresetModel.name)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(
        self,
        preset_id: UUID,
        *,
        name: str | None = None,
        name_provided: bool = False,
        values: dict[str, str] | None = None,
        values_provided: bool = False,
    ) -> TemplatePreset:
        update_values: dict = {}
        if name_provided:
            update_values["name"] = name
        if values_provided:
            update_values["values"] = values

        if update_values:
            stmt = (
                sa_update(TemplatePresetModel)
                .where(TemplatePresetModel.id == preset_id)
                .values(**update_values)
            )
            try:
                await self._session.execute(stmt)
                await self._session.flush()
            except IntegrityError as exc:
                await self._session.rollback()
                raise PresetNameCollisionError(name) from exc

        return await self.get_by_id(preset_id)

    async def delete(self, preset_id: UUID) -> None:
        stmt = sa_delete(TemplatePresetModel).where(TemplatePresetModel.id == preset_id)
        await self._session.execute(stmt)
        await self._session.flush()
