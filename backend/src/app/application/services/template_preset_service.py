from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import TemplatePreset
from app.domain.exceptions import (
    DomainError,
    PresetNameCollisionError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
    TemplatePresetNotFoundError,
)
from app.domain.ports.template_preset_repository import TemplatePresetRepository
from app.domain.ports.template_repository import TemplateRepository

if TYPE_CHECKING:
    from app.application.services.audit_service import AuditService


class TemplatePresetService:
    """Named, reusable variable-value sets for a template — e.g. a recurring
    client's data.

    Access rule for ALL operations: template ACCESS (owner, shared-with-user,
    or admin) — the same rule as GET /templates/{id}. Unlike folders (strictly
    owner-scoped), presets are shared by everyone who can access the template:
    both creators and document generators manage them (explicit product
    decision — presets are a convenience for whoever generates documents from
    the template, not a personal organization tool).
    """

    def __init__(
        self,
        preset_repository: TemplatePresetRepository,
        template_repository: TemplateRepository,
        audit_service: AuditService | None = None,
        ip_address: str | None = None,
    ):
        self._repository = preset_repository
        self._template_repository = template_repository
        self._audit_service = audit_service
        self._ip_address = ip_address

    async def _check_access(self, template_id: UUID, user_id: UUID, role: str) -> None:
        """Raise TemplateNotFoundError / TemplateAccessDeniedError, mirroring
        the GET /templates/{id} access rule (owner, shared user, or admin)."""
        template = await self._template_repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        has_access = await self._template_repository.has_access(template_id, user_id, role)
        if not has_access:
            raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

    async def _get_scoped_preset(self, template_id: UUID, preset_id: UUID) -> TemplatePreset:
        """Return the preset if it exists AND belongs to template_id —
        otherwise raise TemplatePresetNotFoundError, never distinguishing
        between "does not exist" and "belongs to a different template" so
        the 404 never leaks a foreign template's preset."""
        preset = await self._repository.get_by_id(preset_id)
        if preset is None or preset.template_id != template_id:
            raise TemplatePresetNotFoundError(f"Preset {preset_id} not found")
        return preset

    async def list_presets(
        self, template_id: UUID, *, user_id: UUID, role: str
    ) -> list[TemplatePreset]:
        await self._check_access(template_id, user_id, role)
        return await self._repository.list_by_template(template_id)

    async def create_preset(
        self,
        *,
        template_id: UUID,
        user_id: UUID,
        role: str,
        tenant_id: UUID,
        name: str,
        values: dict[str, str],
    ) -> TemplatePreset:
        await self._check_access(template_id, user_id, role)

        preset = TemplatePreset(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            template_id=template_id,
            name=name,
            values=values,
            created_by=user_id,
        )
        try:
            created = await self._repository.create(preset)
        except PresetNameCollisionError:
            raise DomainError(
                f"Ya existe un preset con el nombre '{name}' para esta plantilla. "
                "Use un nombre diferente."
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            self._audit_service.log(
                actor_id=user_id,
                tenant_id=tenant_id,
                action=AuditAction.PRESET_CREATE,
                resource_type="template_preset",
                resource_id=created.id,
                details={"template_id": str(template_id), "name": created.name},
                ip_address=self._ip_address,
            )

        return created

    async def update_preset(
        self,
        *,
        template_id: UUID,
        preset_id: UUID,
        user_id: UUID,
        role: str,
        name: str | None = None,
        name_provided: bool = False,
        values: dict[str, str] | None = None,
        values_provided: bool = False,
    ) -> TemplatePreset:
        await self._check_access(template_id, user_id, role)
        preset = await self._get_scoped_preset(template_id, preset_id)
        old_name = preset.name

        try:
            updated = await self._repository.update(
                preset_id,
                name=name,
                name_provided=name_provided,
                values=values,
                values_provided=values_provided,
            )
        except PresetNameCollisionError:
            raise DomainError(
                f"Ya existe un preset con el nombre '{name}' para esta plantilla. "
                "Use un nombre diferente."
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            details = {"template_id": str(template_id)}
            if name_provided:
                details["old_name"] = old_name
                details["new_name"] = updated.name
            self._audit_service.log(
                actor_id=user_id,
                tenant_id=updated.tenant_id,
                action=AuditAction.PRESET_UPDATE,
                resource_type="template_preset",
                resource_id=preset_id,
                details=details,
                ip_address=self._ip_address,
            )

        return updated

    async def delete_preset(
        self, *, template_id: UUID, preset_id: UUID, user_id: UUID, role: str
    ) -> None:
        await self._check_access(template_id, user_id, role)
        preset = await self._get_scoped_preset(template_id, preset_id)

        await self._repository.delete(preset_id)

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            self._audit_service.log(
                actor_id=user_id,
                tenant_id=preset.tenant_id,
                action=AuditAction.PRESET_DELETE,
                resource_type="template_preset",
                resource_id=preset_id,
                details={"template_id": str(template_id), "name": preset.name},
                ip_address=self._ip_address,
            )
