from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TemplateFolder
from app.domain.exceptions import FolderNameCollisionError
from app.domain.ports.template_folder_repository import (
    TemplateFolderRepository as TemplateFolderRepositoryPort,
)
from app.infrastructure.persistence.models.template import TemplateModel
from app.infrastructure.persistence.models.template_folder import TemplateFolderModel


def _to_entity(model: TemplateFolderModel) -> TemplateFolder:
    return TemplateFolder(
        id=model.id,
        tenant_id=model.tenant_id,
        owner_id=model.owner_id,
        name=model.name,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyTemplateFolderRepository(TemplateFolderRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, folder: TemplateFolder) -> TemplateFolder:
        model = TemplateFolderModel(
            id=folder.id,
            tenant_id=folder.tenant_id,
            owner_id=folder.owner_id,
            name=folder.name,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise FolderNameCollisionError(folder.name) from exc

        folder.created_at = model.created_at
        folder.updated_at = model.updated_at
        return folder

    async def get_by_id(self, folder_id: UUID) -> TemplateFolder | None:
        stmt = select(TemplateFolderModel).where(TemplateFolderModel.id == folder_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _to_entity(model)

    async def list_by_owner(self, owner_id: UUID) -> list[TemplateFolder]:
        """Return the owner's folders, ordered by name, each annotated with a
        transient `template_count` (LEFT JOIN + COUNT against templates).

        The count is grouped by `(folder_id, created_by)` and joined back to
        the folder on BOTH `folder_id == folder.id` AND
        `created_by == folder.owner_id`. This extra correlation is
        defense-in-depth: a folder belongs to exactly one owner, so a
        template row can only ever legitimately count towards a folder if
        its `created_by` matches that folder's `owner_id`. Should a
        template ever end up with a `folder_id` pointing at a folder it no
        longer has access to (e.g. any future code path that forgets to
        clear `folder_id` on an ownership change), this correlation keeps
        it from inflating the folder's `template_count`.
        """
        count_subq = (
            select(
                TemplateModel.folder_id.label("folder_id"),
                TemplateModel.created_by.label("created_by"),
                func.count().label("template_count"),
            )
            .where(TemplateModel.folder_id.isnot(None))
            .group_by(TemplateModel.folder_id, TemplateModel.created_by)
            .subquery()
        )

        stmt = (
            select(TemplateFolderModel, func.coalesce(count_subq.c.template_count, 0))
            .outerjoin(
                count_subq,
                (count_subq.c.folder_id == TemplateFolderModel.id)
                & (count_subq.c.created_by == TemplateFolderModel.owner_id),
            )
            .where(TemplateFolderModel.owner_id == owner_id)
            .order_by(TemplateFolderModel.name)
        )
        result = await self._session.execute(stmt)

        folders: list[TemplateFolder] = []
        for model, count in result.all():
            entity = _to_entity(model)
            entity.template_count = int(count)
            folders.append(entity)
        return folders

    async def update(self, folder_id: UUID, *, name: str) -> TemplateFolder:
        stmt = (
            sa_update(TemplateFolderModel)
            .where(TemplateFolderModel.id == folder_id)
            .values(name=name)
        )
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise FolderNameCollisionError(name) from exc

        updated = await self.get_by_id(folder_id)
        return updated

    async def delete(self, folder_id: UUID) -> None:
        """Delete the folder row. Templates filed in it are unfiled by the
        DB's ON DELETE SET NULL FK on templates.folder_id — no application
        code is needed here to null out folder_id."""
        stmt = sa_delete(TemplateFolderModel).where(TemplateFolderModel.id == folder_id)
        await self._session.execute(stmt)
        await self._session.flush()
