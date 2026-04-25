"""Unit tests for AuditAction.DOCUMENT_DOWNLOAD — T-DOMAIN-07.

Must FAIL (red) before the constant is added to audit_log.py.
"""


def test_audit_action_has_document_download() -> None:
    """AuditAction must expose DOCUMENT_DOWNLOAD = 'document.download' (REQ-DDF-15)."""
    from app.domain.entities.audit_log import AuditAction

    assert hasattr(AuditAction, "DOCUMENT_DOWNLOAD")
    assert AuditAction.DOCUMENT_DOWNLOAD == "document.download"
