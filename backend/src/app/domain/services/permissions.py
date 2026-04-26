"""Centralized role-based permission decisions.

This module is the SINGLE source of truth for "can role X do Y?" checks across
the application. Every endpoint, service, or repository that needs to make a
permission DECISION based on `role` MUST go through one of the helpers here —
do not write inline `role == "admin"` comparisons elsewhere.

Design notes:
    * Each helper takes a single `role: str` and returns `bool`. Pure function;
      no I/O, no side effects.
    * Unknown roles default to the most restrictive answer (False) — this is
      safe-by-default. The matching pattern in
      `document_permissions.can_download_format` defaults unknown roles to
      PDF-only; here we extend the same philosophy: unknown role = deny.
    * The string `"admin"` is the canonical role value and stays inside this
      module. Callers should never compare role strings directly.
    * `can_download_format` is re-exported from `document_permissions` so that
      every permission decision has a single import surface
      (`from app.domain.services.permissions import ...`). The original module
      remains the home of the download-format permission table.
    * Helpers are intentionally split per capability (not "is_admin") so that
      future role additions can target individual capabilities without
      collateral changes.
"""

from app.domain.services.document_permissions import can_download_format

__all__ = [
    "can_download_format",
    "can_manage_users",
    "can_view_audit",
    "can_view_tenant_usage",
    "can_view_all_documents",
    "can_view_all_templates",
    "can_include_both_formats",
    "can_manage_own_templates",
    "is_admin_role",
]


def can_manage_users(role: str) -> bool:
    """Whether the role may create / list / update / deactivate users.

    Gates the entire `/users` admin surface (REQ-USERS-ADMIN).
    """
    return role == "admin"


def can_view_audit(role: str) -> bool:
    """Whether the role may read the tenant audit log."""
    return role == "admin"


def can_view_tenant_usage(role: str) -> bool:
    """Whether the role may view tenant-wide usage metrics.

    The per-user `/usage` endpoint is open to any authenticated user; only the
    `/usage/tenant` aggregate is gated by this helper.
    """
    return role == "admin"


def can_view_all_documents(role: str) -> bool:
    """Whether the role may list / access documents created by other users.

    Non-admin sees only their own documents (the `created_by` filter is
    applied at the service layer).
    """
    return role == "admin"


def can_view_all_templates(role: str) -> bool:
    """Whether the role may list / access every template in the tenant.

    Non-admin sees owned templates plus those explicitly shared with them.
    """
    return role == "admin"


def can_include_both_formats(role: str) -> bool:
    """Whether the role may request the bulk-download `include_both` toggle.

    This is a different capability from `can_download_format` (which is
    per-format) — it gates the cross-format ZIP packaging option.
    """
    return role == "admin"


def can_manage_own_templates(role: str) -> bool:
    """Whether the role may create, update, or delete their own templates.

    Both `admin` and `template_creator` can manage templates they own.
    `document_generator` and any unknown role are denied (safe-default deny).
    ADR-TMP-01, REQ-TMP-01.
    """
    return role in {"admin", "template_creator"}


def is_admin_role(role: str) -> bool:
    """Whether *role* IS the admin role.

    Use ONLY for entity-state checks (e.g. "is the target user an admin?"
    when guarding the last-admin invariant). For "may current_user do X?"
    decisions, use the capability helpers above instead.
    """
    return role == "admin"
