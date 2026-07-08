from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class PresetCreateRequest(BaseModel):
    """POST body for creating a template preset.

    `values` keys are NOT validated against the version's variables —
    template versions evolve independently of stored presets, so the
    intersection between preset keys and current variables is computed by
    the client at load time.
    """

    name: str
    values: dict[str, str] = {}

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _strip_and_validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not (1 <= len(stripped) <= 120):
            raise ValueError(
                "name must be between 1 and 120 characters after stripping whitespace"
            )
        return stripped


class PresetUpdateRequest(BaseModel):
    """PATCH body for renaming a preset and/or replacing its values.

    Both fields are optional individually, but at least one must be
    *present* in the request body (empty body `{}` is rejected with 422).
    Use `model_fields_set` (via `"name" in body.model_fields_set`) to
    distinguish "explicitly provided" from "omitted" — mirrors
    TemplateUpdateRequest's explicit-field-set pattern.
    """

    name: str | None = None
    values: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def _strip_and_validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("name cannot be null")
        stripped = v.strip()
        if not (1 <= len(stripped) <= 120):
            raise ValueError(
                "name must be between 1 and 120 characters after stripping whitespace"
            )
        return stripped

    @field_validator("values")
    @classmethod
    def _values_cannot_be_null(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        # `values` is NOT NULL in the DB — there is no explicit-null-clear
        # semantics for it (unlike TemplateUpdateRequest.description). To
        # clear all stored values, submit an empty dict `{}` instead.
        if v is None:
            raise ValueError("values cannot be null — submit an empty object {} to clear it")
        return v

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "PresetUpdateRequest":
        if not ({"name", "values"} & self.model_fields_set):
            raise ValueError("At least one of 'name' or 'values' must be provided")
        return self


class PresetResponse(BaseModel):
    id: str
    name: str
    values: dict[str, str]
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PresetListResponse(BaseModel):
    presets: list[PresetResponse]
