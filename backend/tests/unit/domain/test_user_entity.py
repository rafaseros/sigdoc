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
