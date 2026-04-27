"""Unit tests — UpdateUserRequest.validate_role (T-PRES-01).

Scenarios covered:
  SCEN-ROLE-03 — document_generator is a valid role value
  SCEN-ROLE-04 — legacy "user" role is rejected with 422-equivalent
  SCEN-ROLE-10 — invalid role value rejected; error message names the 3 allowed values
"""

import pytest
from pydantic import ValidationError

from app.presentation.schemas.user import UpdateUserRequest


# ── SCEN-ROLE-03: valid new-taxonomy roles are accepted ──────────────────────

@pytest.mark.parametrize("valid_role", ["admin", "template_creator", "document_generator"])
def test_valid_roles_are_accepted(valid_role: str) -> None:
    """Each of the three valid roles passes schema validation."""
    req = UpdateUserRequest(role=valid_role)
    assert req.role == valid_role


# ── SCEN-ROLE-04: legacy "user" role is rejected ─────────────────────────────

def test_legacy_user_role_is_rejected() -> None:
    """role='user' must be rejected — it is no longer a valid role value."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateUserRequest(role="user")

    errors = exc_info.value.errors()
    assert len(errors) >= 1
    # Error message must name the three allowed values
    error_msg = errors[0]["msg"]
    assert "admin" in error_msg
    assert "template_creator" in error_msg
    assert "document_generator" in error_msg


# ── SCEN-ROLE-10: completely invalid role value is rejected ───────────────────

def test_invalid_role_value_rejected_with_allowed_values_in_message() -> None:
    """An unknown role string is rejected; the error names all 3 allowed values."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateUserRequest(role="superadmin")

    errors = exc_info.value.errors()
    assert len(errors) >= 1
    error_msg = errors[0]["msg"]
    assert "admin" in error_msg
    assert "template_creator" in error_msg
    assert "document_generator" in error_msg


# ── Role = None is still allowed (partial update) ────────────────────────────

def test_none_role_is_allowed() -> None:
    """role=None means 'don't change the role' — must not raise ValidationError."""
    req = UpdateUserRequest(role=None)
    assert req.role is None


# ── Omitting role field entirely is also fine ────────────────────────────────

def test_missing_role_field_defaults_to_none() -> None:
    """If role is omitted from the request body, it defaults to None."""
    req = UpdateUserRequest()
    assert req.role is None
