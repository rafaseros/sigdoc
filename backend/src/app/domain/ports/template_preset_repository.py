from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import TemplatePreset


class TemplatePresetRepository(ABC):
    @abstractmethod
    async def create(self, preset: TemplatePreset) -> TemplatePreset:
        """Create a preset. Raises PresetNameCollisionError on a
        (template_id, name) collision."""
        ...

    @abstractmethod
    async def get_by_id(self, preset_id: UUID) -> TemplatePreset | None:
        ...

    @abstractmethod
    async def list_by_template(self, template_id: UUID) -> list[TemplatePreset]:
        """Return the template's presets, ordered by name."""
        ...

    @abstractmethod
    async def update(
        self,
        preset_id: UUID,
        *,
        name: str | None = None,
        name_provided: bool = False,
        values: dict[str, str] | None = None,
        values_provided: bool = False,
    ) -> TemplatePreset:
        """Update the given fields on a preset. Raises PresetNameCollisionError
        on a (template_id, name) collision."""
        ...

    @abstractmethod
    async def delete(self, preset_id: UUID) -> None:
        ...
