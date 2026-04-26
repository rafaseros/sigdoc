from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerateRequest(BaseModel):
    """Request schema for POST /documents/generate.

    REQ-DDF-03: output_format MUST NOT be accepted. extra="forbid" causes
    Pydantic to return HTTP 422 for any unknown field, including output_format.
    """

    model_config = ConfigDict(extra="forbid")

    template_version_id: str
    variables: dict[str, str]


class DocumentResponse(BaseModel):
    """Response schema for a generated document.

    Phase 2 (pdf-export): docx_file_name / pdf_file_name are the canonical fields.
    The legacy file_name alias has been removed — frontend was migrated in cleanup batch.
    """

    id: str
    template_version_id: str
    docx_file_name: str = ""
    pdf_file_name: str | None = None
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
