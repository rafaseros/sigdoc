from pydantic import BaseModel, ConfigDict, field_validator


class FolderCreateRequest(BaseModel):
    """POST body for creating a personal template folder."""

    name: str

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


class FolderUpdateRequest(FolderCreateRequest):
    """PATCH body for renaming a personal template folder. Same validation
    as create — a folder's only mutable attribute is its name."""


class FolderResponse(BaseModel):
    id: str
    name: str
    template_count: int = 0

    model_config = {"from_attributes": True}


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]
