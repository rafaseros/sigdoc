"""Domain service: role-based download format permissions.

This is the SINGLE RBAC decision point for document download format access.
No other code path should make an independent role-vs-format decision.

ADR-PDF-05: dict-based permission table — adding a role is a one-line update.
REQ-DDF-08: can_download_format is the sole arbiter.

roles-expansion (011_role_expansion.py): replaced legacy "user" role with
  "template_creator" and "document_generator". The "user" key is intentionally
  absent — any token still carrying role="user" falls through to the safe-default
  (PDF-only), which is the correct least-privilege behaviour.
"""

# Maps each known role to the set of download formats it may access.
# Default for any unrecognised role → PDF-only (most-restrictive non-empty set).
# NOTE: "user" is deliberately absent — it was the legacy role before migration 011.
#       Stale tokens with role="user" resolve to PDF-only via the safe-default below.
DOWNLOAD_FORMAT_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"docx", "pdf"}),
    "template_creator": frozenset({"pdf"}),
    "document_generator": frozenset({"pdf"}),
}


def can_download_format(role: str, format: str) -> bool:
    """Return True when *role* is allowed to download in *format*.

    Args:
        role: The authenticated user's role string.
              Current valid roles: "admin", "template_creator", "document_generator".
        format: The requested download format ("pdf" or "docx").

    Returns:
        True if the role may download the requested format; False otherwise.

    Notes:
        Unknown roles default to PDF-only — never zero-permission.
        This is a pure domain function; no I/O, no side effects.
    """
    allowed = DOWNLOAD_FORMAT_PERMISSIONS.get(role, frozenset({"pdf"}))
    return format in allowed
