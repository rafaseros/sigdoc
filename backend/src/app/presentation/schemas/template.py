from datetime import datetime

from pydantic import BaseModel


class VariableMeta(BaseModel):
    name: str
    contexts: list[str] = []


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
