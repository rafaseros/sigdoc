"""Unit tests for UserModel ORM column defaults — T-INFRA-04.

Must FAIL (red) before T-INFRA-05 updates user.py defaults.

REQs: REQ-ROLE-05
ADRs: ADR-ROLE-03
"""

import pytest

from app.infrastructure.persistence.models.user import UserModel


class TestUserModelRoleDefaults:
    """Assert UserModel.role column has the correct Python-side and DB-side defaults."""

    def test_python_default_is_document_generator(self):
        """UserModel.role column Python-side default must be 'document_generator'."""
        col = UserModel.__table__.c["role"]
        assert col.default.arg == "document_generator", (
            f"Expected Python default='document_generator', got {col.default.arg!r}"
        )

    def test_server_default_is_document_generator(self):
        """UserModel.role column DB-side server_default must be 'document_generator'."""
        col = UserModel.__table__.c["role"]
        assert col.server_default.arg == "document_generator", (
            f"Expected server_default='document_generator', got {col.server_default.arg!r}"
        )
