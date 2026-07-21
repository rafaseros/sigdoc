import uuid
from uuid import UUID

from sqlalchemy import delete, exists, func, select, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import TemplateShare
from app.domain.ports.template_repository import TemplateRepository as TemplateRepositoryPort
from app.domain.services.permissions import can_view_all_templates
from app.infrastructure.persistence.models.template import TemplateModel
from app.infrastructure.persistence.models.template_share import TemplateShareModel
from app.infrastructure.persistence.models.template_version import TemplateVersionModel
from app.infrastructure.persistence.models.template_version_file import (
    TemplateVersionFileModel,
)


class SQLAlchemyTemplateRepository(TemplateRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, template):
        self._session.add(template)
        await self._session.flush()
        return template

    async def get_by_id(self, template_id: UUID):
        stmt = (
            select(TemplateModel)
            .where(TemplateModel.id == template_id)
            .options(selectinload(TemplateModel.versions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list, int]:
        # Base query
        stmt = select(TemplateModel).options(selectinload(TemplateModel.versions))
        count_stmt = select(func.count()).select_from(TemplateModel)

        # Apply search filter
        if search:
            search_filter = TemplateModel.name.ilike(f"%{search}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Apply created_by filter (non-admin users only see their own templates)
        if created_by is not None:
            created_by_filter = TemplateModel.created_by == created_by
            stmt = stmt.where(created_by_filter)
            count_stmt = count_stmt.where(created_by_filter)

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * size
        stmt = stmt.order_by(TemplateModel.created_at.desc()).offset(offset).limit(size)

        result = await self._session.execute(stmt)
        templates = list(result.scalars().unique().all())

        return templates, total

    async def delete(self, template_id: UUID) -> None:
        stmt = delete(TemplateModel).where(TemplateModel.id == template_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def create_version(self, version):
        from app.domain.entities import TemplateVersion as DomainTemplateVersion

        if isinstance(version, DomainTemplateVersion):
            orm_version = TemplateVersionModel(
                id=version.id,
                tenant_id=version.tenant_id,
                template_id=version.template_id,
                version=version.version,
                minio_path=version.minio_path,
                variables=version.variables,
                variables_meta=version.variables_meta or [],
                file_size=version.file_size,
            )
        else:
            orm_version = version

        self._session.add(orm_version)
        await self._session.flush()
        return orm_version

    async def get_version(self, template_id: UUID, version: int):
        stmt = select(TemplateVersionModel).where(
            TemplateVersionModel.template_id == template_id,
            TemplateVersionModel.version == version,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, version_id: UUID):
        stmt = select(TemplateVersionModel).where(
            TemplateVersionModel.id == version_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_template_with_version(
        self,
        *,
        template_id: UUID,
        version_id: UUID,
        name: str,
        description: str | None,
        tenant_id: UUID,
        created_by: UUID,
        version: int,
        minio_path: str,
        variables: list[str],
        variables_meta: list[dict] | None = None,
        file_size: int,
    ) -> TemplateModel:
        """Create a template and its first version atomically."""
        template = TemplateModel(
            id=template_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            current_version=version,
            created_by=created_by,
        )
        self._session.add(template)
        await self._session.flush()

        version_model = TemplateVersionModel(
            id=version_id,
            tenant_id=tenant_id,
            template_id=template_id,
            version=version,
            minio_path=minio_path,
            variables=variables,
            variables_meta=variables_meta or [],
            file_size=file_size,
        )
        self._session.add(version_model)
        await self._session.flush()

        # Refresh to load the versions relationship
        await self._session.refresh(template, ["versions"])
        return template

    async def list_accessible(
        self,
        user_id: UUID,
        role: str,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        folder_id: UUID | None = None,
        folder_filter_unfiled: bool = False,
    ) -> tuple[list, int]:
        """Return templates where user is owner OR has a share record.
        Admin role sees all templates in the tenant (tenant filter applied by TenantMixin event).
        Each returned TemplateModel has a transient `access_type` attribute: "owned" or "shared".

        `folder_filter_unfiled` / `folder_id` restrict results to a specific
        folder (or to unfiled templates). The filter is applied as an
        additional `.where()` on the SAME stmt/count_stmt that already
        carries the owner/shared accessible-ids filter for non-admin users —
        it is NEVER run as an independent query — so it is always
        intersected with visibility, never applied on top of it.
        """
        if can_view_all_templates(role):
            # Admins see everything in the tenant
            stmt = select(TemplateModel).options(selectinload(TemplateModel.versions))
            count_stmt = select(func.count()).select_from(TemplateModel)

            if search:
                search_filter = TemplateModel.name.ilike(f"%{search}%")
                stmt = stmt.where(search_filter)
                count_stmt = count_stmt.where(search_filter)

            if folder_filter_unfiled:
                stmt = stmt.where(TemplateModel.folder_id.is_(None))
                count_stmt = count_stmt.where(TemplateModel.folder_id.is_(None))
            elif folder_id is not None:
                stmt = stmt.where(TemplateModel.folder_id == folder_id)
                count_stmt = count_stmt.where(TemplateModel.folder_id == folder_id)

            total_result = await self._session.execute(count_stmt)
            total = total_result.scalar_one()

            offset = (page - 1) * size
            stmt = stmt.order_by(TemplateModel.created_at.desc()).offset(offset).limit(size)
            result = await self._session.execute(stmt)
            templates = list(result.scalars().unique().all())

            for t in templates:
                t.access_type = "owned" if t.created_by == user_id else "shared"

            return templates, total

        # Non-admin: owned OR shared
        # We build two sub-selects for the IDs (owned + shared), union them,
        # then load full TemplateModel objects.
        owned_ids = select(TemplateModel.id).where(TemplateModel.created_by == user_id)
        shared_ids = select(TemplateShareModel.template_id).where(
            TemplateShareModel.user_id == user_id
        )
        accessible_ids_subq = union_all(owned_ids, shared_ids).subquery()

        stmt = (
            select(TemplateModel)
            .where(TemplateModel.id.in_(select(accessible_ids_subq)))
            .options(selectinload(TemplateModel.versions))
        )
        count_stmt = select(func.count()).select_from(TemplateModel).where(
            TemplateModel.id.in_(select(accessible_ids_subq))
        )

        if search:
            search_filter = TemplateModel.name.ilike(f"%{search}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # CRITICAL: chained onto the SAME stmt/count_stmt that already
        # carries the owned/shared accessible-ids filter above — this
        # intersects (AND) with visibility. Applying the folder filter as a
        # separate query would let another owner's shared templates leak
        # through a folder filter.
        if folder_filter_unfiled:
            stmt = stmt.where(TemplateModel.folder_id.is_(None))
            count_stmt = count_stmt.where(TemplateModel.folder_id.is_(None))
        elif folder_id is not None:
            stmt = stmt.where(TemplateModel.folder_id == folder_id)
            count_stmt = count_stmt.where(TemplateModel.folder_id == folder_id)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = stmt.order_by(TemplateModel.created_at.desc()).offset(offset).limit(size)
        result = await self._session.execute(stmt)
        templates = list(result.scalars().unique().all())

        # Collect share lookups in one query to avoid N+1
        template_ids = [t.id for t in templates]
        if template_ids:
            shares_result = await self._session.execute(
                select(TemplateShareModel.template_id).where(
                    TemplateShareModel.template_id.in_(template_ids),
                    TemplateShareModel.user_id == user_id,
                )
            )
            shared_set = {row[0] for row in shares_result.all()}
        else:
            shared_set = set()

        for t in templates:
            t.access_type = "owned" if t.created_by == user_id else "shared"
            # Validate consistency: if it's in shared_set but not owned, it's "shared"
            if t.id in shared_set and t.created_by != user_id:
                t.access_type = "shared"

        return templates, total

    async def add_share(
        self,
        template_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        shared_by: UUID,
    ) -> TemplateShare:
        """Create a share record. Idempotent — ON CONFLICT DO NOTHING."""
        share_id = uuid.uuid4()
        stmt = (
            pg_insert(TemplateShareModel)
            .values(
                id=share_id,
                template_id=template_id,
                user_id=user_id,
                tenant_id=tenant_id,
                shared_by=shared_by,
            )
            .on_conflict_do_nothing(constraint="uq_template_shares_template_user")
            .returning(
                TemplateShareModel.id,
                TemplateShareModel.template_id,
                TemplateShareModel.user_id,
                TemplateShareModel.tenant_id,
                TemplateShareModel.shared_by,
                TemplateShareModel.shared_at,
            )
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            # Conflict — row already existed; fetch it
            existing = await self._session.execute(
                select(TemplateShareModel).where(
                    TemplateShareModel.template_id == template_id,
                    TemplateShareModel.user_id == user_id,
                )
            )
            model = existing.scalar_one()
            return TemplateShare(
                id=model.id,
                template_id=model.template_id,
                user_id=model.user_id,
                tenant_id=model.tenant_id,
                shared_by=model.shared_by,
                shared_at=model.shared_at,
            )

        return TemplateShare(
            id=row.id,
            template_id=row.template_id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            shared_by=row.shared_by,
            shared_at=row.shared_at,
        )

    async def remove_share(self, template_id: UUID, user_id: UUID) -> None:
        """Delete the share record for (template_id, user_id)."""
        stmt = delete(TemplateShareModel).where(
            TemplateShareModel.template_id == template_id,
            TemplateShareModel.user_id == user_id,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def has_access(self, template_id: UUID, user_id: UUID, role: str) -> bool:
        """Return True if user owns the template, has a share, or is admin."""
        if can_view_all_templates(role):
            return True

        stmt = select(
            exists().where(
                TemplateModel.id == template_id,
            ).where(
                (TemplateModel.created_by == user_id)
                | exists().where(
                    TemplateShareModel.template_id == template_id,
                    TemplateShareModel.user_id == user_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar_one())

    async def list_shares(self, template_id: UUID) -> list[TemplateShare]:
        """Return all share records for a given template."""
        stmt = select(TemplateShareModel).where(
            TemplateShareModel.template_id == template_id
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return [
            TemplateShare(
                id=m.id,
                template_id=m.template_id,
                user_id=m.user_id,
                tenant_id=m.tenant_id,
                shared_by=m.shared_by,
                shared_at=m.shared_at,
            )
            for m in models
        ]

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Return the total number of templates owned by the given tenant."""
        stmt = select(func.count()).select_from(TemplateModel).where(
            TemplateModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_shares(self, template_id: UUID) -> int:
        """Return the number of active share records for the given template."""
        stmt = select(func.count()).select_from(TemplateShareModel).where(
            TemplateShareModel.template_id == template_id,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_owner_id(self, template_id: UUID) -> UUID | None:
        """Return the created_by (owner) UUID for the given template, or None if not found."""
        stmt = select(TemplateModel.created_by).where(TemplateModel.id == template_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def get_share_for_user(
        self, template_id: UUID, user_id: UUID
    ) -> TemplateShare | None:
        """Return the share row for (template_id, user_id), or None if absent."""
        stmt = select(TemplateShareModel).where(
            TemplateShareModel.template_id == template_id,
            TemplateShareModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return TemplateShare(
            id=model.id,
            template_id=model.template_id,
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            shared_by=model.shared_by,
            shared_at=model.shared_at,
        )

    async def update_variables_meta(
        self, version_id: UUID, variables_meta: list[dict]
    ) -> TemplateVersionModel:
        """Replace variables_meta for the given version and return the updated model."""
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(TemplateVersionModel)
            .where(TemplateVersionModel.id == version_id)
            .values(variables_meta=variables_meta)
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Re-fetch to return the updated state
        fetch_stmt = select(TemplateVersionModel).where(TemplateVersionModel.id == version_id)
        result = await self._session.execute(fetch_stmt)
        return result.scalar_one()

    async def add_version_file(self, file) -> TemplateVersionFileModel:
        """Persist a related file row for a template version and return it."""
        from app.domain.entities import TemplateVersionFile as DomainTemplateVersionFile

        if isinstance(file, DomainTemplateVersionFile):
            orm_file = TemplateVersionFileModel(
                id=file.id,
                tenant_id=file.tenant_id,
                version_id=file.version_id,
                label=file.label,
                minio_path=file.minio_path,
                variables=file.variables,
                file_size=file.file_size,
                position=file.position,
            )
        else:
            orm_file = file

        self._session.add(orm_file)
        await self._session.flush()
        return orm_file

    async def get_version_file(
        self, version_id: UUID, file_id: UUID
    ) -> TemplateVersionFileModel | None:
        """Return the related file for (version_id, file_id), or None."""
        stmt = select(TemplateVersionFileModel).where(
            TemplateVersionFileModel.id == file_id,
            TemplateVersionFileModel.version_id == version_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_version_file(self, version_id: UUID, file_id: UUID) -> None:
        """Delete the related file row for (version_id, file_id)."""
        stmt = delete(TemplateVersionFileModel).where(
            TemplateVersionFileModel.id == file_id,
            TemplateVersionFileModel.version_id == version_id,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_version_variables(
        self, version_id: UUID, variables: list[str], variables_meta: list[dict]
    ) -> TemplateVersionModel:
        """Replace variables AND variables_meta for the given version."""
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(TemplateVersionModel)
            .where(TemplateVersionModel.id == version_id)
            .values(variables=variables, variables_meta=variables_meta)
        )
        await self._session.execute(stmt)
        await self._session.flush()

        fetch_stmt = select(TemplateVersionModel).where(
            TemplateVersionModel.id == version_id
        )
        result = await self._session.execute(fetch_stmt)
        return result.scalar_one()

    async def count_by_owner(self, user_id: UUID) -> int:
        """Return the number of templates owned by the given user."""
        stmt = select(func.count()).select_from(TemplateModel).where(
            TemplateModel.created_by == user_id,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def reassign_owner(
        self, from_user_id: UUID, to_user_id: UUID
    ) -> int:
        """Bulk reassign every template owned by `from_user_id` to
        `to_user_id`. Returns the number of templates updated.

        Also clears `folder_id` on every reassigned template: a folder
        belongs to a single owner, so a template can never keep a
        `folder_id` pointing at the previous owner's folder once ownership
        moves — that would leave an orphaned reference, inflate the old
        folder's count, and 404 the new owner when they try to access it.
        """
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(TemplateModel)
            .where(TemplateModel.created_by == from_user_id)
            .values(created_by=to_user_id, folder_id=None)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return int(result.rowcount or 0)

    async def update(
        self,
        template_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        description_provided: bool = False,
        folder_id: UUID | None = None,
        folder_id_provided: bool = False,
    ) -> TemplateModel:
        """Update name/description/folder on a template and return the updated model.

        `name` is applied when not None. `description` and `folder_id` are
        applied whenever their `_provided` flag is True — including clearing
        them to NULL. On a (tenant_id, name) collision, rolls back the
        aborted transaction and raises TemplateNameCollisionError so callers
        never see a leaked sqlalchemy.exc.IntegrityError nor an aborted
        session. Callers are responsible for validating that the target
        folder exists and belongs to the caller BEFORE calling this method."""
        from sqlalchemy import update as sa_update
        from sqlalchemy.exc import IntegrityError

        from app.domain.exceptions import TemplateNameCollisionError

        values: dict = {}
        if name is not None:
            values["name"] = name
        if description_provided:
            values["description"] = description
        if folder_id_provided:
            values["folder_id"] = folder_id

        if values:
            stmt = (
                sa_update(TemplateModel)
                .where(TemplateModel.id == template_id)
                .values(**values)
            )
            try:
                await self._session.execute(stmt)
                await self._session.flush()
            except IntegrityError as exc:
                await self._session.rollback()
                raise TemplateNameCollisionError(name) from exc

        return await self.get_by_id(template_id)
