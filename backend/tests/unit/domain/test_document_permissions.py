"""Unit tests for can_download_format — SCEN-DDF-16 truth table.

T-DOMAIN-01: write tests FIRST; must FAIL before T-DOMAIN-02 is implemented.
"""
import pytest


@pytest.mark.parametrize(
    "role, format_, expected",
    [
        ("admin", "docx", True),
        ("admin", "pdf", True),
        ("user", "docx", False),
        ("user", "pdf", True),
        ("unknown_role", "docx", False),
        ("unknown_role", "pdf", True),
    ],
    ids=[
        "admin-docx",
        "admin-pdf",
        "user-docx",
        "user-pdf",
        "unknown-docx",
        "unknown-pdf",
    ],
)
def test_can_download_format_truth_table(role: str, format_: str, expected: bool) -> None:
    """SCEN-DDF-16: can_download_format must return expected bool for every role×format combo."""
    from app.domain.services.document_permissions import can_download_format

    assert can_download_format(role, format_) is expected
