"""Domain service: role-based download format permissions.

This is the SINGLE RBAC decision point for document download format access.
No other code path should make an independent role-vs-format decision.

ADR-PDF-05: dict-based permission table — adding a role is a one-line update.
REQ-DDF-08: can_download_format is the sole arbiter.
"""

# Maps each known role to the set of download formats it may access.
# Default for any unrecognised role → PDF-only (most-restrictive non-empty set).
DOWNLOAD_FORMAT_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"docx", "pdf"}),
    "user": frozenset({"pdf"}),
}


def can_download_format(role: str, format: str) -> bool:
    """Return True when *role* is allowed to download in *format*.

    Args:
        role: The authenticated user's role string (e.g. "admin", "user").
        format: The requested download format ("pdf" or "docx").

    Returns:
        True if the role may download the requested format; False otherwise.

    Notes:
        Unknown roles default to PDF-only — never zero-permission.
        This is a pure domain function; no I/O, no side effects.
    """
    allowed = DOWNLOAD_FORMAT_PERMISSIONS.get(role, frozenset({"pdf"}))
    return format in allowed
