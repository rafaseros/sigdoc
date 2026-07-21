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


class PreviewRequest(BaseModel):
    """Request schema for POST /documents/preview.

    Deliberately kept separate from GenerateRequest: the preview path is
    ephemeral (nothing persisted) and must never inherit generation's
    completeness/quota semantics if GenerateRequest grows those later.

    `file_id` (optional) previews a RELATED file of the version instead of
    the primary docx — 404 when it doesn't belong to the version.
    """

    model_config = ConfigDict(extra="forbid")

    template_version_id: str
    variables: dict[str, str]
    file_id: str | None = None


class DocumentResponse(BaseModel):
    """Response schema for a generated document.

    Phase 2 (pdf-export): docx_file_name / pdf_file_name are the canonical fields.
    The legacy file_name alias has been removed — frontend was migrated in cleanup batch.

    template_id / template_name / template_version expose which template and
    which human version number produced the document. Required — the
    documents.template_version_id FK is NOT NULL, so the join always resolves.
    """

    id: str
    template_version_id: str
    template_id: str
    template_name: str
    template_version: int
    docx_file_name: str = ""
    pdf_file_name: str | None = None
    generation_type: str
    status: str
    download_url: str | None = None
    variables_snapshot: dict
    created_at: datetime
    # Documents generated together from one multi-file generation share a
    # group_id; null for documents of versions without related files.
    group_id: str | None = None

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    """Response schema for POST /documents/generate.

    A generation renders the version's primary docx plus every related file
    with ONE shared variable set, so it returns a LIST of documents (primary
    first, then related files by position). `group_id` is the shared group
    of this generation — null when the version has no related files (the
    list then has exactly one element).
    """

    documents: list[DocumentResponse]
    group_id: str | None = None


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
