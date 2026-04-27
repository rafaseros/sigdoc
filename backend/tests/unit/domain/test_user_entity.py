"""Unit tests for the User domain entity.

T-DOMAIN-05 (roles-expansion): Default role must be 'document_generator' when
no role argument is supplied at construction time.
REQ-ROLE-04, SCEN-ROLE-09, ADR-ROLE-03.
"""
import uuid
from datetime import datetime, timezone

from app.domain.entities.user import User


def _make_user(**kwargs) -> User:
    """Build a minimal valid User, overridable by kwargs."""
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password_value",
        full_name="Test User",
    )
    defaults.update(kwargs)
    return User(**defaults)


class TestUserEntityDefaultRole:
    """T-DOMAIN-05: User entity role default is 'document_generator'."""

    def test_default_role_is_document_generator(self) -> None:
        """SCEN-ROLE-09: User instantiated with no role arg → role == 'document_generator'."""
        user = _make_user()
        assert user.role == "document_generator"

    def test_explicit_role_is_preserved(self) -> None:
        """Explicit role kwarg is not overridden by the default."""
        user = _make_user(role="admin")
        assert user.role == "admin"

    def test_template_creator_role_accepted(self) -> None:
        """template_creator can be explicitly set."""
        user = _make_user(role="template_creator")
        assert user.role == "template_creator"

    def test_document_generator_explicit_equals_default(self) -> None:
        """Explicitly passing document_generator yields same result as default."""
        user_default = _make_user()
        user_explicit = _make_user(role="document_generator")
        assert user_default.role == user_explicit.role


class TestUserEntityEmailVerifiedDefault:
    """REQ-SOS-15: User entity email_verified default must be True after single-org-cutover.

    Previously the default was False (migration 009 field). Post-cutover it must be
    True so any newly constructed User — before DB persistence — is treated as verified.
    """

    def test_user_entity_email_verified_default_is_true(self) -> None:
        """REQ-SOS-15 / SCEN: User() with no email_verified arg → email_verified is True.

        RED: fails while user.py still has email_verified: bool = False.
        GREEN: passes after default is changed to True.
        """
        user = _make_user()
        assert user.email_verified is True, (
            f"Expected email_verified=True (single-org-cutover default), got {user.email_verified}"
        )

    def test_explicit_false_is_still_accepted(self) -> None:
        """Triangulation: explicit False can still be set (DB rows may have legacy False).

        This confirms the dataclass does not coerce False to True — the default is True,
        but explicit False must be preserved for existing DB rows.
        """
        user = _make_user(email_verified=False)
        assert user.email_verified is False

    def test_explicit_true_is_preserved(self) -> None:
        """Triangulation: explicit True is preserved (no override of caller's intent)."""
        user = _make_user(email_verified=True)
        assert user.email_verified is True
