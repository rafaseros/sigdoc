"""Migration round-trip test for 012_demo_reset — demo VPS wipe + re-seed.

Strategy: mock the alembic `op` object and the DB connection to capture the
SQL operations executed by upgrade(). This validates migration logic without
requiring a live database.

Tests:
  - Safety guard fires when user_count > 10 (raises RuntimeError)
  - Safety guard passes when user_count <= 10 (migration proceeds)
  - DELETE statements are executed in FK-safe order (children first)
  - INSERT for tenants includes the Free tier_id
  - INSERT for users has the expected email, role=admin, email_verified=True
  - downgrade() is a no-op (no SQL executed)

Spec: demo VPS reset for CAINCO demo, 2026-04-27
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------

_VERSIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions")
)


def _load_migration():
    """Import 012_demo_reset from alembic/versions/ with a fresh module each time."""
    if _VERSIONS_DIR not in sys.path:
        sys.path.insert(0, _VERSIONS_DIR)

    mod_name = "migration_012_demo_reset"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(
        mod_name,
        os.path.join(_VERSIONS_DIR, "012_demo_reset.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestMigrationMetadata:
    def test_revision_is_012(self):
        m = _load_migration()
        assert m.revision == "012", f"Expected revision='012', got {m.revision!r}"

    def test_down_revision_is_011(self):
        m = _load_migration()
        assert m.down_revision == "011", (
            f"Expected down_revision='011', got {m.down_revision!r}"
        )

    def test_docstring_warns_about_destructive_nature(self):
        m = _load_migration()
        doc = (m.__doc__ or "").lower()
        assert "destructive" in doc or "irreversible" in doc, (
            "Migration docstring must warn about destructive/irreversible nature"
        )

    def test_docstring_mentions_safety_guard(self):
        m = _load_migration()
        doc = (m.__doc__ or "").lower()
        assert "safety" in doc, (
            "Migration docstring must mention the safety guard"
        )

    def test_safety_threshold_is_10(self):
        m = _load_migration()
        assert m.SAFETY_THRESHOLD == 10, (
            f"Safety threshold must be 10, got {m.SAFETY_THRESHOLD}"
        )


# ---------------------------------------------------------------------------
# Helper: build a mock connection whose execute() returns configurable scalars
# ---------------------------------------------------------------------------


def _make_conn_mock(user_count: int) -> MagicMock:
    """Return a mock connection that returns `user_count` for COUNT queries."""
    conn = MagicMock()
    sql_calls: list[str] = []

    def _execute(stmt, params=None, **kwargs):
        sql_text = str(stmt).lower()
        sql_calls.append(sql_text)
        result = MagicMock()
        if "count" in sql_text:
            result.scalar.return_value = user_count
        return result

    conn.execute.side_effect = _execute
    conn._sql_calls = sql_calls
    return conn


# ---------------------------------------------------------------------------
# Safety guard tests
# ---------------------------------------------------------------------------


class TestSafetyGuard:
    def test_aborts_when_user_count_exceeds_threshold(self):
        """Migration must raise RuntimeError when there are > 10 users."""
        m = _load_migration()
        conn = _make_conn_mock(user_count=11)

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            with pytest.raises(RuntimeError, match="11 users found"):
                m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

    def test_aborts_with_message_containing_threshold(self):
        """RuntimeError message must mention the safety threshold of 10."""
        m = _load_migration()
        conn = _make_conn_mock(user_count=15)

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            with pytest.raises(RuntimeError, match="10"):
                m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

    def test_proceeds_when_user_count_is_below_threshold(self):
        """Migration must NOT raise when there are <= 10 users."""
        m = _load_migration()
        conn = _make_conn_mock(user_count=5)

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            # Should not raise
            m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

    def test_proceeds_when_user_count_equals_threshold(self):
        """Exactly 10 users must pass (threshold is > not >=)."""
        m = _load_migration()
        conn = _make_conn_mock(user_count=10)

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

    def test_aborts_at_boundary_plus_one(self):
        """11 users (threshold + 1) must raise."""
        m = _load_migration()
        conn = _make_conn_mock(user_count=11)

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            with pytest.raises(RuntimeError):
                m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind


# ---------------------------------------------------------------------------
# SQL execution order — DELETE then INSERT
# ---------------------------------------------------------------------------


class TestSQLExecutionOrder:
    """Verify that DELETE statements appear before INSERT statements and
    follow FK-safe order (children before parents)."""

    def _run_and_capture(self, user_count: int = 2):
        m = _load_migration()

        executed_stmts: list[str] = []

        conn = MagicMock()

        def _execute(stmt, params=None, **kwargs):
            sql_text = str(stmt).lower().strip()
            executed_stmts.append(sql_text)
            result = MagicMock()
            result.scalar.return_value = user_count
            return result

        conn.execute.side_effect = _execute

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

        return executed_stmts

    def test_deletes_audit_logs_before_tenants(self):
        stmts = self._run_and_capture()
        tables = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        assert "audit_logs" in tables, "audit_logs must be deleted"
        assert "tenants" in tables, "tenants must be deleted"
        assert tables.index("audit_logs") < tables.index("tenants"), (
            "audit_logs must be deleted before tenants (FK order)"
        )

    def test_deletes_documents_before_tenants(self):
        stmts = self._run_and_capture()
        tables = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        assert tables.index("documents") < tables.index("tenants"), (
            "documents must be deleted before tenants"
        )

    def test_deletes_users_before_tenants(self):
        stmts = self._run_and_capture()
        tables = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        assert tables.index("users") < tables.index("tenants"), (
            "users must be deleted before tenants"
        )

    def test_deletes_template_shares_before_templates(self):
        stmts = self._run_and_capture()
        tables = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        assert tables.index("template_shares") < tables.index("templates"), (
            "template_shares must be deleted before templates"
        )

    def test_inserts_tenant_before_user(self):
        stmts = self._run_and_capture()
        insert_stmts = [s for s in stmts if "insert into" in s]
        assert len(insert_stmts) == 2, (
            f"Expected exactly 2 INSERT statements (tenant + user), got {len(insert_stmts)}"
        )
        assert "tenants" in insert_stmts[0], (
            f"First INSERT must be for tenants, got: {insert_stmts[0][:60]}"
        )
        assert "users" in insert_stmts[1], (
            f"Second INSERT must be for users, got: {insert_stmts[1][:60]}"
        )

    def test_all_expected_tables_deleted(self):
        stmts = self._run_and_capture()
        deleted = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        expected_tables = {
            "audit_logs",
            "usage_events",
            "template_shares",
            "documents",
            "template_versions",
            "templates",
            "users",
            "tenants",
        }
        missing = expected_tables - set(deleted)
        assert not missing, (
            f"The following tables were not deleted: {missing}"
        )

    def test_subscription_tiers_not_deleted(self):
        stmts = self._run_and_capture()
        deleted = [s.split("from")[-1].strip() for s in stmts if "delete from" in s]
        assert "subscription_tiers" not in deleted, (
            "subscription_tiers must NOT be deleted (it holds config seed data)"
        )


# ---------------------------------------------------------------------------
# INSERT parameter validation
# ---------------------------------------------------------------------------


class TestInsertParameters:
    """Verify the re-seed INSERT statements contain the expected values."""

    def _run_and_capture_params(self, user_count: int = 2):
        m = _load_migration()

        insert_calls: list[tuple[str, dict]] = []

        conn = MagicMock()

        def _execute(stmt, params=None, **kwargs):
            sql_text = str(stmt).lower().strip()
            result = MagicMock()
            result.scalar.return_value = user_count
            if "insert into" in sql_text:
                insert_calls.append((sql_text, params or {}))
            return result

        conn.execute.side_effect = _execute

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            m.upgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

        return insert_calls

    def test_tenant_insert_has_correct_name(self):
        calls = self._run_and_capture_params()
        tenant_sql, tenant_params = calls[0]
        assert "tenants" in tenant_sql
        assert tenant_params.get("name") == "SigDoc Demo", (
            f"Tenant name must be 'SigDoc Demo', got {tenant_params.get('name')!r}"
        )

    def test_tenant_insert_has_correct_slug(self):
        calls = self._run_and_capture_params()
        _, tenant_params = calls[0]
        assert tenant_params.get("slug") == "sigdoc-demo", (
            f"Tenant slug must be 'sigdoc-demo', got {tenant_params.get('slug')!r}"
        )

    def test_tenant_insert_has_free_tier_id(self):
        calls = self._run_and_capture_params()
        _, tenant_params = calls[0]
        free_tier_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free"))
        assert tenant_params.get("tier_id") == free_tier_id, (
            f"Tenant tier_id must be the Free tier UUID, got {tenant_params.get('tier_id')!r}"
        )

    def test_tenant_insert_is_active(self):
        calls = self._run_and_capture_params()
        _, tenant_params = calls[0]
        assert tenant_params.get("is_active") is True, (
            "Tenant must be inserted as is_active=True"
        )

    def test_user_insert_has_correct_email(self):
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        assert user_params.get("email") == "devrafaseros@gmail.com", (
            f"User email must be 'devrafaseros@gmail.com', got {user_params.get('email')!r}"
        )

    def test_user_insert_has_admin_role(self):
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        assert user_params.get("role") == "admin", (
            f"User role must be 'admin', got {user_params.get('role')!r}"
        )

    def test_user_insert_is_active(self):
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        assert user_params.get("is_active") is True, (
            "User must be inserted as is_active=True"
        )

    def test_user_insert_email_verified(self):
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        assert user_params.get("email_verified") is True, (
            "User must be inserted as email_verified=True"
        )

    def test_user_insert_has_hashed_password(self):
        """Password must be hashed (bcrypt starts with $2b$)."""
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        hashed = user_params.get("hashed_password", "")
        assert hashed.startswith("$2"), (
            f"hashed_password must be a bcrypt hash (starts with $2), got: {hashed[:10]!r}"
        )

    def test_user_insert_has_correct_full_name(self):
        calls = self._run_and_capture_params()
        _, user_params = calls[1]
        assert user_params.get("full_name") == "Jose Rafael Gallegos Rojas", (
            f"User full_name mismatch: {user_params.get('full_name')!r}"
        )


# ---------------------------------------------------------------------------
# downgrade() is a no-op
# ---------------------------------------------------------------------------


class TestDowngrade:
    def test_downgrade_executes_no_sql(self):
        """downgrade() must not touch the database."""
        m = _load_migration()

        sql_calls: list[str] = []
        conn = MagicMock()
        conn.execute.side_effect = lambda *a, **kw: sql_calls.append(str(a))

        import alembic.op as alembic_op_real

        original_get_bind = alembic_op_real.get_bind
        try:
            alembic_op_real.get_bind = lambda: conn
            m.downgrade()
        finally:
            alembic_op_real.get_bind = original_get_bind

        assert not sql_calls, (
            f"downgrade() must be a no-op but executed: {sql_calls}"
        )
