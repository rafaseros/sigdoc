import math
from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VariableType = Literal["text", "integer", "decimal", "select"]

ComputedOperator = Literal["+", "-", "*", "/"]

# Registry pattern: adding a new computed function is a one-line change to
# this Literal plus the `_FUNCTION_REGISTRY` dict in
# app.domain.services.computed_variables.
ComputedFunctionName = Literal["number_to_words"]


class ComputedFormula(BaseModel):
    """A computed variable derived by applying an arithmetic operator to
    another variable's value and a constant operand."""

    kind: Literal["formula"] = "formula"
    source: str
    operator: ComputedOperator
    operand: float

    model_config = ConfigDict(extra="forbid")

    @field_validator("operand")
    @classmethod
    def _validate_operand_is_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("El operando debe ser un número finito")
        return v

    @model_validator(mode="after")
    def _validate_division_operand_not_zero(self) -> "ComputedFormula":
        if self.operator == "/" and self.operand == 0:
            raise ValueError("El operando de una división no puede ser 0")
        return self


class ComputedFunctionSpec(BaseModel):
    """A computed variable derived by applying a named pure function to
    another variable's value."""

    kind: Literal["function"] = "function"
    function: ComputedFunctionName
    source: str

    model_config = ConfigDict(extra="forbid")


ComputedSpec = Annotated[
    Union[ComputedFormula, ComputedFunctionSpec], Field(discriminator="kind")
]


class VariableMeta(BaseModel):
    name: str
    contexts: list[str] = []
    type: VariableType = "text"
    options: list[str] | None = None
    help_text: str | None = None
    computed: ComputedSpec | None = None


class VariableTypeOverride(BaseModel):
    name: str
    type: VariableType
    options: list[str] | None = None
    help_text: str | None = None
    computed: ComputedSpec | None = None

    @model_validator(mode="after")
    def validate_select_has_options(self) -> "VariableTypeOverride":
        if self.type == "select" and not (self.options and len(self.options) > 0):
            raise ValueError("options is required and must be non-empty when type is 'select'")
        return self


class UpdateVariableTypesRequest(BaseModel):
    overrides: list[VariableTypeOverride]


class TemplateVersionFileResponse(BaseModel):
    """A related .docx attached to a template version (besides the primary).

    `variables` is this file's OWN extracted names — the version's
    `variables` remains the union across the primary and every file.
    """

    id: str
    label: str
    variables: list[str] = []
    file_size: int
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateVersionResponse(BaseModel):
    id: str
    version: int
    variables: list[str]
    variables_meta: list[VariableMeta] = []
    file_size: int
    created_at: datetime
    files: list[TemplateVersionFileResponse] = []

    model_config = {"from_attributes": True}


class TemplateUpdateRequest(BaseModel):
    """PATCH body for renaming a template and/or updating its description.

    Both fields are optional individually, but at least one must be *present*
    in the request body — an empty body `{}` is rejected with 422. `name`
    can never be null (it has a min-length requirement), but `description`
    supports explicit-null semantics: `{"description": null}` is a valid,
    non-empty body that clears the description. Use `model_fields_set` (via
    `"description" in body.model_fields_set`) to distinguish "explicitly set
    to null" from "omitted".
    """

    name: str | None = None
    description: str | None = None
    folder_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _strip_and_validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("name cannot be null")
        stripped = v.strip()
        if not (1 <= len(stripped) <= 255):
            raise ValueError(
                "name must be between 1 and 255 characters after stripping whitespace"
            )
        return stripped

    @field_validator("folder_id")
    @classmethod
    def _validate_folder_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            UUID(v)
        except ValueError:
            raise ValueError("folder_id must be a valid UUID")
        return v

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "TemplateUpdateRequest":
        if not ({"name", "description", "folder_id"} & self.model_fields_set):
            raise ValueError(
                "At least one of 'name', 'description', or 'folder_id' must be provided"
            )
        return self


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
    owner_name: str | None = None  # the template creator's full name
    folder_id: str | None = None  # the owner's personal folder this template is filed in, if any

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

NodeKind = Literal[
    "paragraph",
    "heading",
    "list_bullet",
    "list_number",
    "table",
]


class StructureSpan(BaseModel):
    """A run of text inside a paragraph. When `variable` is non-null the span
    represents a `{{ variable }}` placeholder — `text` keeps the original
    placeholder string for display.
    """

    text: str
    variable: str | None = None


class StructureTableCell(BaseModel):
    """A single cell inside a table row. Holds nested paragraph/heading/list
    nodes (table-in-table is intentionally not recursed)."""

    nodes: list["StructureNode"] = []


class StructureTableRow(BaseModel):
    cells: list[StructureTableCell] = []


class StructureNode(BaseModel):
    """A node in the document.

    - paragraph / heading / list_bullet / list_number: text content via `spans`
    - heading: `level` is 1-6
    - list_bullet / list_number: `level` is the indentation depth (>=1)
    - table: `rows` carries the grid; `spans` is empty
    """

    kind: NodeKind = "paragraph"
    level: int = 0
    spans: list[StructureSpan] = []
    rows: list[StructureTableRow] = []


# Resolve the forward reference inside StructureTableCell.
StructureTableCell.model_rebuild()


class TemplateStructureResponse(BaseModel):
    headers: list[StructureNode] = []
    body: list[StructureNode] = []
    footers: list[StructureNode] = []


# ---------------------------------------------------------------------------
# Template from example — a filled .docx is analyzed, the user maps literal
# texts to variables, and the backend rewrites it into a normal template v1.
# ---------------------------------------------------------------------------

# Lowercase snake_case — the only variable-name shape the engine's validate()
# accepts without errors.
VARIABLE_NAME_PATTERN = r"^[a-z_][a-z0-9_]*$"


class TemplateAnalyzeExampleResponse(BaseModel):
    """Response of POST /templates/analyze-example."""

    structure: TemplateStructureResponse


class VariableMappingItem(BaseModel):
    """One literal-text → variable mapping for POST /templates/from-example.

    `text` is matched exactly (case-sensitive) in the example document, so it
    is intentionally NOT stripped — only required to be non-blank. `variable`
    must be lowercase snake_case.
    """

    text: str
    variable: str = Field(pattern=VARIABLE_NAME_PATTERN)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class VariableMappingsPayload(BaseModel):
    """Validated wrapper for the `mappings` JSON form field of /from-example.

    Rejects an empty list and duplicated texts. The same variable name for
    two different texts IS allowed (both become the same placeholder).
    """

    mappings: list[VariableMappingItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_duplicate_texts(self) -> "VariableMappingsPayload":
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in self.mappings:
            if item.text in seen and item.text not in duplicates:
                duplicates.append(item.text)
            seen.add(item.text)
        if duplicates:
            joined = ", ".join(f"'{t}'" for t in duplicates)
            raise ValueError(f"duplicated texts in mappings: {joined}")
        return self
