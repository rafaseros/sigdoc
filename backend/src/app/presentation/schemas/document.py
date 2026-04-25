from datetime import datetime

from pydantic import BaseModel, computed_field, model_validator


class GenerateRequest(BaseModel):
    template_version_id: str
    variables: dict[str, str]


class DocumentResponse(BaseModel):
    """Response schema for a generated document.

    Phase 2 (pdf-export): added explicit docx_file_name / pdf_file_name fields.
    The legacy `file_name` field is kept for API backward compatibility —
    it is populated from docx_file_name.  Frontend Phase 5 will migrate to
    the explicit fields; `file_name` will be removed in a future cleanup.
    """

    id: str
    template_version_id: str
    # Backward-compat field — always equals docx_file_name (populated via model_validator)
    file_name: str = ""
    # Explicit dual-format fields (Phase 2+)
    docx_file_name: str = ""
    pdf_file_name: str | None = None
    generation_type: str
    status: str
    download_url: str | None = None
    variables_snapshot: dict
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _populate_file_name_alias(self) -> "DocumentResponse":
        """Keep file_name in sync with docx_file_name for backward compat."""
        if self.docx_file_name and not self.file_name:
            self.file_name = self.docx_file_name
        elif self.file_name and not self.docx_file_name:
            # Fallback: ORM gave us file_name but not docx_file_name (shouldn't happen post-migration)
            self.docx_file_name = self.file_name
        return self


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
