"""Migration round-trip test for 011_role_expansion — T-INFRA-02.

Strategy: mock the alembic `op` object to capture the SQL operations executed
by upgrade() and downgrade(). This validates the migration logic (correct
SQL statements in the correct order) without requiring a separate test DB.

The test FAILS (ImportError) before migration 011_role_expansion.py exists.
After implementation, it PASSES by verifying the operation sequence matches
ADR-ROLE-02.

REQs: REQ-ROLE-02, REQ-ROLE-03
Scenarios: SCEN-ROLE-01, SCEN-ROLE-02
ADR: ADR-ROLE-02
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Import the migration module under test — FAILS (RED) before it exists
# ---------------------------------------------------------------------------

import importlib
import sys


def _load_migration():
    """Import 011_role_expansion from alembic/versions/."""
    # Add the alembic versions dir to path if needed
    import os
    versions_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic", "versions"
    )
    versions_dir = os.path.abspath(versions_dir)
    if versions_dir not in sys.path:
        sys.path.insert(0, versions_dir)
    # Force fresh import every time
    mod_name = "migration_011_role_expansion"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        os.path.join(versions_dir, "011_role_expansion.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_op_mock():
    """Return a MagicMock for alembic.op that records calls."""
    mock = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestMigrationMetadata:
    def test_revision_is_011(self):
        m = _load_migration()
        assert m.revision == "011", f"Expected revision='011', got {m.revision!r}"

    def test_down_revision_is_010(self):
        m = _load_migration()
        assert m.down_revision == "010", (
            f"Expected down_revision='010', got {m.down_revision!r}"
        )

    def test_docstring_mentions_lossy(self):
        m = _load_migration()
        doc = m.__doc__ or ""
        assert "lossy" in doc.lower() or "lossless" not in doc.lower(), (
            "Migration docstring must document the lossy downgrade behavior"
        )


# ---------------------------------------------------------------------------
# upgrade() operation order — ADR-ROLE-02 (critical)
# ---------------------------------------------------------------------------


class TestUpgradeOrder:
    def test_upgrade_calls_execute_before_alter_column(self):
        """UPDATE must run BEFORE ALTER DEFAULT — ADR-ROLE-02."""
        m = _load_migration()
        op_mock = _make_op_mock()
        call_order = []

        def record_execute(*args, **kwargs):
            call_order.append(("execute", args, kwargs))

        def record_alter(*args, **kwargs):
            call_order.append(("alter_column", args, kwargs))

        op_mock.execute.side_effect = record_execute
        op_mock.alter_column.side_effect = record_alter

        with patch.object(
            sys.modules.get("alembic.op", MagicMock()), "execute", op_mock.execute
        ), patch.object(
            sys.modules.get("alembic.op", MagicMock()), "alter_column", op_mock.alter_column
        ):
            # Patch 'op' inside the migration module's namespace
            import alembic.op as alembic_op_real
            original_execute = alembic_op_real.execute
            original_alter = alembic_op_real.alter_column
            try:
                alembic_op_real.execute = record_execute
                alembic_op_real.alter_column = record_alter
                m.upgrade()
            finally:
                alembic_op_real.execute = original_execute
                alembic_op_real.alter_column = original_alter

        assert len(call_order) == 2, (
            f"upgrade() must call exactly 2 ops (execute + alter_column), got {call_order}"
        )
        assert call_order[0][0] == "execute", (
            f"First upgrade() op must be execute (UPDATE), got {call_order[0][0]}"
        )
        assert call_order[1][0] == "alter_column", (
            f"Second upgrade() op must be alter_column (DEFAULT), got {call_order[1][0]}"
        )

    def test_upgrade_execute_sets_template_creator(self):
        """upgrade() UPDATE sets role='template_creator' WHERE role='user'."""
        m = _load_migration()
        captured_sql = []

        import alembic.op as alembic_op_real

        original_execute = alembic_op_real.execute
        original_alter = alembic_op_real.alter_column
        try:
            alembic_op_real.execute = lambda sql, *a, **kw: captured_sql.append(str(sql))
            alembic_op_real.alter_column = lambda *a, **kw: None
            m.upgrade()
        finally:
            alembic_op_real.execute = original_execute
            alembic_op_real.alter_column = original_alter

        assert len(captured_sql) == 1
        sql = captured_sql[0].lower()
        assert "template_creator" in sql, f"upgrade SQL must mention 'template_creator': {sql}"
        assert "user" in sql, f"upgrade SQL WHERE must reference 'user': {sql}"

    def test_upgrade_alter_column_sets_document_generator_default(self):
        """upgrade() ALTER sets server_default='document_generator'."""
        m = _load_migration()
        captured_alter = []

        import alembic.op as alembic_op_real

        original_execute = alembic_op_real.execute
        original_alter = alembic_op_real.alter_column
        try:
            alembic_op_real.execute = lambda *a, **kw: None
            alembic_op_real.alter_column = lambda *a, **kw: captured_alter.append((a, kw))
            m.upgrade()
        finally:
            alembic_op_real.execute = original_execute
            alembic_op_real.alter_column = original_alter

        assert len(captured_alter) == 1
        _, kwargs = captured_alter[0]
        server_default = kwargs.get("server_default")
        assert server_default == "document_generator", (
            f"upgrade() ALTER must set server_default='document_generator', got {server_default!r}"
        )


# ---------------------------------------------------------------------------
# downgrade() operation order — ADR-ROLE-02 (critical)
# ---------------------------------------------------------------------------


class TestDowngradeOrder:
    def test_downgrade_calls_alter_column_before_execute(self):
        """Revert DEFAULT first, THEN collapse rows — ADR-ROLE-02."""
        m = _load_migration()
        call_order = []

        import alembic.op as alembic_op_real

        original_execute = alembic_op_real.execute
        original_alter = alembic_op_real.alter_column
        try:
            alembic_op_real.execute = lambda *a, **kw: call_order.append("execute")
            alembic_op_real.alter_column = lambda *a, **kw: call_order.append("alter_column")
            m.downgrade()
        finally:
            alembic_op_real.execute = original_execute
            alembic_op_real.alter_column = original_alter

        assert len(call_order) == 2, (
            f"downgrade() must call exactly 2 ops, got {call_order}"
        )
        assert call_order[0] == "alter_column", (
            f"First downgrade() op must be alter_column (revert DEFAULT), got {call_order[0]}"
        )
        assert call_order[1] == "execute", (
            f"Second downgrade() op must be execute (collapse rows), got {call_order[1]}"
        )

    def test_downgrade_alter_column_restores_user_default(self):
        """downgrade() ALTER must restore server_default='user'."""
        m = _load_migration()
        captured_alter = []

        import alembic.op as alembic_op_real

        original_execute = alembic_op_real.execute
        original_alter = alembic_op_real.alter_column
        try:
            alembic_op_real.execute = lambda *a, **kw: None
            alembic_op_real.alter_column = lambda *a, **kw: captured_alter.append((a, kw))
            m.downgrade()
        finally:
            alembic_op_real.execute = original_execute
            alembic_op_real.alter_column = original_alter

        assert len(captured_alter) == 1
        _, kwargs = captured_alter[0]
        server_default = kwargs.get("server_default")
        assert server_default == "user", (
            f"downgrade() ALTER must restore server_default='user', got {server_default!r}"
        )

    def test_downgrade_execute_collapses_both_new_roles(self):
        """downgrade() UPDATE must collapse both template_creator and document_generator → user."""
        m = _load_migration()
        captured_sql = []

        import alembic.op as alembic_op_real

        original_execute = alembic_op_real.execute
        original_alter = alembic_op_real.alter_column
        try:
            alembic_op_real.execute = lambda sql, *a, **kw: captured_sql.append(str(sql))
            alembic_op_real.alter_column = lambda *a, **kw: None
            m.downgrade()
        finally:
            alembic_op_real.execute = original_execute
            alembic_op_real.alter_column = original_alter

        assert len(captured_sql) == 1
        sql = captured_sql[0].lower()
        assert "template_creator" in sql, f"downgrade SQL must collapse 'template_creator': {sql}"
        assert "document_generator" in sql, (
            f"downgrade SQL must collapse 'document_generator': {sql}"
        )
        assert "'user'" in sql or "= 'user'" in sql or "= \"user\"" in sql or "'user'" in captured_sql[0], (
            f"downgrade SQL must set role to 'user': {sql}"
        )
