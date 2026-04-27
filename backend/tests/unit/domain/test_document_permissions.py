"""Unit tests for can_download_format — SCEN-DDF-16 truth table.

T-DOMAIN-01: write tests FIRST; must FAIL before T-DOMAIN-02 is implemented.
T-REG-01: extend truth table with template_creator and document_generator rows
          and audit DOWNLOAD_FORMAT_PERMISSIONS for stale "user" key.
"""
import pytest


@pytest.mark.parametrize(
    "role, format_, expected",
    [
        # admin — full access
        ("admin", "docx", True),
        ("admin", "pdf", True),
        # template_creator — PDF-only (REQ-ROLE-01, roles-expansion)
        ("template_creator", "docx", False),
        ("template_creator", "pdf", True),
        # document_generator — PDF-only (REQ-ROLE-01, roles-expansion)
        ("document_generator", "docx", False),
        ("document_generator", "pdf", True),
        # unknown role — safe-default: PDF-only (most-restrictive non-empty)
        ("unknown_role", "docx", False),
        ("unknown_role", "pdf", True),
    ],
    ids=[
        "admin-docx",
        "admin-pdf",
        "template_creator-docx",
        "template_creator-pdf",
        "document_generator-docx",
        "document_generator-pdf",
        "unknown-docx",
        "unknown-pdf",
    ],
)
def test_can_download_format_truth_table(role: str, format_: str, expected: bool) -> None:
    """SCEN-DDF-16: can_download_format must return expected bool for every role×format combo."""
    from app.domain.services.document_permissions import can_download_format

    assert can_download_format(role, format_) is expected


def test_legacy_user_role_resolves_to_pdf_only() -> None:
    """T-REG-01: legacy 'user' role (removed from DOWNLOAD_FORMAT_PERMISSIONS dict)
    must still resolve to PDF-only via the safe-default, not to admin-level access.

    After the roles-expansion migration the 'user' role no longer exists in the system,
    but tokens from before the migration could still carry role='user'. The safe-default
    frozenset({'pdf'}) ensures they can download PDF (not zero-access) but NOT docx.
    """
    from app.domain.services.document_permissions import can_download_format

    assert can_download_format("user", "pdf") is True
    assert can_download_format("user", "docx") is False


def test_download_format_permissions_dict_contains_new_roles() -> None:
    """T-REG-01: DOWNLOAD_FORMAT_PERMISSIONS must have explicit entries for all current
    roles (admin, template_creator, document_generator).
    The stale 'user' key must NOT appear — unknown roles are handled by the safe-default.
    """
    from app.domain.services.document_permissions import DOWNLOAD_FORMAT_PERMISSIONS

    assert "admin" in DOWNLOAD_FORMAT_PERMISSIONS
    assert "template_creator" in DOWNLOAD_FORMAT_PERMISSIONS
    assert "document_generator" in DOWNLOAD_FORMAT_PERMISSIONS
    # Stale legacy role must be absent — the safe-default handles any legacy tokens
    assert "user" not in DOWNLOAD_FORMAT_PERMISSIONS
