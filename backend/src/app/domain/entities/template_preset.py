from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class TemplatePreset:
    """A named, reusable set of variable values for a template — e.g. a
    recurring client's data. Shared by everyone with access to the
    template (owner, shared users, admins), unlike folders which are
    strictly owner-scoped: presets are a convenience for whoever generates
    documents from the template, not a personal organization tool.
    """

    id: UUID
    tenant_id: UUID
    template_id: UUID
    name: str
    values: dict[str, str] = field(default_factory=dict)
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
