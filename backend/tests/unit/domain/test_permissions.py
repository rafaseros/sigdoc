"""Unit tests for the centralized role-based permission helpers.

Each helper is a pure domain function: `(role: str) -> bool`.
Truth table per helper: admin → True, user → False, unknown → False.
Unknown-role default mirrors the safe-by-default approach in
`document_permissions.can_download_format` (deny non-PDF for unknown roles).

T-PERM-01: write tests FIRST; must FAIL before T-PERM-02 implements the helpers.
"""
import pytest


# (role, expected) — same truth table is reused for every helper.
ROLE_EXPECTATIONS = [
    ("admin", True),
    ("user", False),
    ("unknown_role", False),
]
ROLE_IDS = ["admin", "user", "unknown"]


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_manage_users(role: str, expected: bool) -> None:
    from app.domain.services.permissions import can_manage_users

    assert can_manage_users(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_view_audit(role: str, expected: bool) -> None:
    from app.domain.services.permissions import can_view_audit

    assert can_view_audit(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_view_tenant_usage(role: str, expected: bool) -> None:
    from app.domain.services.permissions import can_view_tenant_usage

    assert can_view_tenant_usage(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_view_all_documents(role: str, expected: bool) -> None:
    from app.domain.services.permissions import can_view_all_documents

    assert can_view_all_documents(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_view_all_templates(role: str, expected: bool) -> None:
    from app.domain.services.permissions import can_view_all_templates

    assert can_view_all_templates(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_is_admin_role(role: str, expected: bool) -> None:
    """Entity-state check for "is this role the admin role?".

    Used for the last-admin invariant guard in `update_user` / `delete_user`,
    NOT for permission decisions (use the capability helpers for those).
    """
    from app.domain.services.permissions import is_admin_role

    assert is_admin_role(role) is expected


@pytest.mark.parametrize("role, expected", ROLE_EXPECTATIONS, ids=ROLE_IDS)
def test_can_include_both_formats(role: str, expected: bool) -> None:
    """Capability gate for the bulk-download `include_both` toggle.

    Distinct from `can_download_format` (which is per format) — this checks the
    cross-format combo capability for ZIP packaging.
    """
    from app.domain.services.permissions import can_include_both_formats

    assert can_include_both_formats(role) is expected


def test_permissions_reexports_can_download_format() -> None:
    """The new permissions module should re-export the existing download helper
    so callers have a single import surface."""
    from app.domain.services.permissions import can_download_format
    from app.domain.services.document_permissions import (
        can_download_format as original,
    )

    assert can_download_format is original
