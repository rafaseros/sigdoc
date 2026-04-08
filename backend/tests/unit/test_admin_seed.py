"""Unit tests for migration 008 admin seed logic.

Spec: SCEN-SEED-01 through SCEN-SEED-05

These tests validate the seed logic by exercising the upgrade() function
against a mock SQLAlchemy connection that simulates database responses.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ADMIN_EMAIL = "devrafaseros@gmail.com"
ADMIN_FULL_NAME = "Jose Rafael Gallegos Rojas"

_MIGRATION_PATH = (
    Path(__file__).parent.parent.parent
    / "alembic"
    / "versions"
    / "008_admin_seed_canonical.py"
)


def _load_migration():
    """Load the migration module dynamically (filename starts with digit)."""
    spec = importlib.util.spec_from_file_location("migration_008", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_conn_mock(existing_user=None, existing_tenant_id=None):
    """Build a mock connection whose execute() returns controlled results."""
    conn = MagicMock()

    def execute_side_effect(stmt, params=None):
        result = MagicMock()
        sql_text = str(stmt)

        if "SELECT id FROM users" in sql_text:
            result.fetchone.return_value = existing_user
        elif "SELECT id FROM tenants" in sql_text:
            if existing_tenant_id:
                row = MagicMock()
                row.__getitem__ = lambda self, idx: existing_tenant_id
                result.fetchone.return_value = row
            else:
                result.fetchone.return_value = None
        else:
            result.fetchone.return_value = None

        return result

    conn.execute.side_effect = execute_side_effect
    return conn


# ── SCEN-SEED-01: Fresh DB — inserts admin with hashed password ───────────────


def test_seed_fresh_db_inserts_admin():
    """SCEN-SEED-01: On a fresh DB, admin is inserted with ADMIN_PASSWORD."""
    with patch.dict(os.environ, {"ADMIN_PASSWORD": "securepassword123"}):
        conn = _make_conn_mock(existing_user=None, existing_tenant_id=str(uuid.uuid4()))
        migration = _load_migration()

        with patch.object(migration.op, "get_bind", return_value=conn):
            migration.upgrade()

        all_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "INSERT INTO users" in all_sql


def test_seed_fresh_db_no_tenant_creates_one():
    """SCEN-SEED-01 variant: When no tenant exists, a seed tenant is created."""
    with patch.dict(os.environ, {"ADMIN_PASSWORD": "securepassword123"}):
        conn = _make_conn_mock(existing_user=None, existing_tenant_id=None)
        migration = _load_migration()

        with patch.object(migration.op, "get_bind", return_value=conn):
            migration.upgrade()

        all_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "INSERT INTO tenants" in all_sql
        assert "INSERT INTO users" in all_sql


# ── SCEN-SEED-02: Existing user — updates name/role, skips password ──────────


def test_seed_existing_user_updates_name_and_role():
    """SCEN-SEED-02: If user already exists, only update full_name and role."""
    existing_row = MagicMock()
    existing_row.__getitem__ = lambda self, idx: str(uuid.uuid4())
    conn = _make_conn_mock(existing_user=existing_row)
    migration = _load_migration()

    with patch.dict(os.environ, {"ADMIN_PASSWORD": "does-not-matter"}):
        with patch.object(migration.op, "get_bind", return_value=conn):
            migration.upgrade()

    all_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "UPDATE users" in all_sql
    # Must NOT attempt to INSERT when user exists
    assert "INSERT INTO users" not in all_sql


def test_seed_existing_user_does_not_require_password():
    """SCEN-SEED-02: Existing user update must NOT fail even if ADMIN_PASSWORD is unset."""
    existing_row = MagicMock()
    existing_row.__getitem__ = lambda self, idx: str(uuid.uuid4())
    conn = _make_conn_mock(existing_user=existing_row)
    migration = _load_migration()

    # Remove ADMIN_PASSWORD from env
    env_without_pw = {k: v for k, v in os.environ.items() if k != "ADMIN_PASSWORD"}
    with patch.dict(os.environ, env_without_pw, clear=True):
        with patch.object(migration.op, "get_bind", return_value=conn):
            # Should NOT raise RuntimeError
            migration.upgrade()


# ── SCEN-SEED-03: Missing ADMIN_PASSWORD on fresh DB raises error ─────────────


def test_seed_missing_password_on_fresh_db_raises():
    """SCEN-SEED-03: Fresh DB + no ADMIN_PASSWORD → RuntimeError."""
    conn = _make_conn_mock(existing_user=None, existing_tenant_id=str(uuid.uuid4()))
    migration = _load_migration()

    env_without_pw = {k: v for k, v in os.environ.items() if k != "ADMIN_PASSWORD"}
    with patch.dict(os.environ, env_without_pw, clear=True):
        with patch.object(migration.op, "get_bind", return_value=conn):
            with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
                migration.upgrade()
