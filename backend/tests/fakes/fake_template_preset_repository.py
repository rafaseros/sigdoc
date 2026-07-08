from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import TemplatePreset
from app.domain.exceptions import PresetNameCollisionError
from app.domain.ports.template_preset_repository import TemplatePresetRepository


class FakeTemplatePresetRepository(TemplatePresetRepository):
    """Dict-backed in-memory implementation of TemplatePresetRepository for testing."""

    def __init__(self) -> None:
        self._presets: dict[UUID, TemplatePreset] = {}

    async def create(self, preset: TemplatePreset) -> TemplatePreset:
        for other in self._presets.values():
            if other.template_id == preset.template_id and other.name == preset.name:
                raise PresetNameCollisionError(preset.name)

        now = datetime.now(timezone.utc)
        if preset.created_at is None:
            preset.created_at = now
        if preset.updated_at is None:
            preset.updated_at = now
        self._presets[preset.id] = preset
        return preset

    async def get_by_id(self, preset_id: UUID) -> TemplatePreset | None:
        return self._presets.get(preset_id)

    async def list_by_template(self, template_id: UUID) -> list[TemplatePreset]:
        items = [p for p in self._presets.values() if p.template_id == template_id]
        items.sort(key=lambda p: p.name)
        return items

    async def update(
        self,
        preset_id: UUID,
        *,
        name: str | None = None,
        name_provided: bool = False,
        values: dict[str, str] | None = None,
        values_provided: bool = False,
    ) -> TemplatePreset:
        preset = self._presets.get(preset_id)
        if preset is None:
            raise KeyError(f"Preset {preset_id} not found")

        if name_provided and name is not None:
            for other in self._presets.values():
                if (
                    other.id != preset_id
                    and other.template_id == preset.template_id
                    and other.name == name
                ):
                    raise PresetNameCollisionError(name)
            preset.name = name

        if values_provided:
            preset.values = values or {}

        preset.updated_at = datetime.now(timezone.utc)
        return preset

    async def delete(self, preset_id: UUID) -> None:
        self._presets.pop(preset_id, None)
