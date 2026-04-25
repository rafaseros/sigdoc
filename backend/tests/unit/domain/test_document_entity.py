"""Unit tests for Document entity dual file fields — T-DOMAIN-08.

Must FAIL (red) before the entity is updated.
REQ-DDF-01: docx_file_name, pdf_file_name, docx_minio_path, pdf_minio_path.
"""
import uuid
from datetime import datetime, timezone


def _make_document(**overrides):
    """Build a minimal Document with required fields."""
    from app.domain.entities.document import Document

    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        template_version_id=uuid.uuid4(),
        docx_file_name="test.docx",
        docx_minio_path="tenant/doc-id/test.docx",
        generation_type="single",
        variables_snapshot={},
        created_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Document(**defaults)


def test_document_has_docx_file_name() -> None:
    """Document must have docx_file_name attribute (REQ-DDF-01)."""
    doc = _make_document(docx_file_name="report.docx")
    assert doc.docx_file_name == "report.docx"


def test_document_has_docx_minio_path() -> None:
    """Document must have docx_minio_path attribute (REQ-DDF-01)."""
    doc = _make_document(docx_minio_path="tenant/uuid/report.docx")
    assert doc.docx_minio_path == "tenant/uuid/report.docx"


def test_document_has_pdf_file_name_optional() -> None:
    """pdf_file_name must be Optional[str] defaulting to None (REQ-DDF-01)."""
    doc = _make_document()
    assert doc.pdf_file_name is None


def test_document_has_pdf_minio_path_optional() -> None:
    """pdf_minio_path must be Optional[str] defaulting to None (REQ-DDF-01)."""
    doc = _make_document()
    assert doc.pdf_minio_path is None


def test_document_can_set_pdf_fields() -> None:
    """Both PDF fields can be set to non-None string values."""
    doc = _make_document(
        pdf_file_name="report.pdf",
        pdf_minio_path="tenant/uuid/report.pdf",
    )
    assert doc.pdf_file_name == "report.pdf"
    assert doc.pdf_minio_path == "tenant/uuid/report.pdf"


def test_document_file_name_alias_returns_docx_file_name() -> None:
    """file_name property alias must return docx_file_name for backward compat.

    This alias is temporary (Phase 1) — removed in Phase 2 when SQLAlchemy
    model and all call sites are updated to docx_file_name.
    """
    doc = _make_document(docx_file_name="alias-test.docx")
    assert doc.file_name == "alias-test.docx"


def test_document_minio_path_alias_returns_docx_minio_path() -> None:
    """minio_path property alias must return docx_minio_path for backward compat."""
    doc = _make_document(docx_minio_path="alias/path/test.docx")
    assert doc.minio_path == "alias/path/test.docx"


def test_document_no_longer_accepts_old_file_name_kwarg() -> None:
    """After rename, positional field 'file_name' should NOT exist as a field.

    This confirms the rename happened — existing callers need to migrate.
    Note: aliases (property) exist for reading, but the field name in the
    dataclass is docx_file_name, NOT file_name.
    """
    import dataclasses

    from app.domain.entities.document import Document

    field_names = {f.name for f in dataclasses.fields(Document)}
    assert "docx_file_name" in field_names, "docx_file_name field must exist"
    assert "file_name" not in field_names, "file_name field must NOT exist (use docx_file_name)"
