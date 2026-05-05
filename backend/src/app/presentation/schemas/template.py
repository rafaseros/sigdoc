from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


VariableType = Literal["text", "integer", "decimal", "select"]


class VariableMeta(BaseModel):
    name: str
    contexts: list[str] = []
    type: VariableType = "text"
    options: list[str] | None = None
    help_text: str | None = None


class VariableTypeOverride(BaseModel):
    name: str
    type: VariableType
    options: list[str] | None = None
    help_text: str | None = None

    @model_validator(mode="after")
    def validate_select_has_options(self) -> "VariableTypeOverride":
        if self.type == "select" and not (self.options and len(self.options) > 0):
            raise ValueError("options is required and must be non-empty when type is 'select'")
        return self


class UpdateVariableTypesRequest(BaseModel):
    overrides: list[VariableTypeOverride]


class TemplateVersionResponse(BaseModel):
    id: str
    version: int
    variables: list[str]
    variables_meta: list[VariableMeta] = []
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    current_version: int
    variables: list[str] = []  # from current version
    versions: list[TemplateVersionResponse] = []
    created_at: datetime
    updated_at: datetime
    access_type: str = "owned"  # "owned" | "shared" | "admin"
    is_owner: bool = True
    shared_by_email: str | None = None  # populated only when access_type == "shared"

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int
    page: int
    size: int


class TemplateUploadResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    version: int
    variables: list[str]
    created_at: datetime


class ShareTemplateRequest(BaseModel):
    email: str


class TemplateShareResponse(BaseModel):
    id: str
    template_id: str
    user_id: str
    user_email: str | None = None
    tenant_id: str
    shared_by: str
    shared_at: datetime | None = None


# ---------------------------------------------------------------------------
# Document structure preview — used by the generation UI to show the full
# document context (body + headers + footers) with placeholders inline.
# ---------------------------------------------------------------------------

NodeKind = Literal["paragraph", "heading"]


class StructureSpan(BaseModel):
    """A run of text inside a paragraph. When `variable` is non-null the span
    represents a `{{ variable }}` placeholder — `text` keeps the original
    placeholder string for display.
    """

    text: str
    variable: str | None = None


class StructureNode(BaseModel):
    """A paragraph from the document. `level` is 1-6 for headings, 0 otherwise."""

    kind: NodeKind = "paragraph"
    level: int = 0
    spans: list[StructureSpan] = []


class TemplateStructureResponse(BaseModel):
    headers: list[StructureNode] = []
    body: list[StructureNode] = []
    footers: list[StructureNode] = []
