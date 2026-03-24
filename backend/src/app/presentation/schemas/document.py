from datetime import datetime

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    template_version_id: str
    variables: dict[str, str]


class DocumentResponse(BaseModel):
    id: str
    template_version_id: str
    file_name: str
    generation_type: str
    status: str
    download_url: str | None = None
    variables_snapshot: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    size: int


class BulkGenerateResponse(BaseModel):
    batch_id: str
    document_count: int
    download_url: str
    errors: list[dict] = []
