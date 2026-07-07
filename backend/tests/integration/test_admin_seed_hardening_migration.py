"""Migration round-trip test for 013_admin_seed_hardening.

This repository is PUBLIC. Migration 012 (demo reset) seeds a hardcoded
admin credential (devrafaseros@gmail.com / admin123!). Migration 013 makes
every fresh deploy safe:

  1. If ADMIN_EMAIL/ADMIN_PASSWORD are configured, it ensures an admin user
     with that email/password exists (update-in-place, legacy row rename,
     or fresh insert — never destructive).
  2. Regardless of env configuration, it neutralizes the legacy hardcoded
     demo credential wherever it is still found and still matches the
     publicly-known demo password.

Strategy: mock the alembic `op` object and the DB connection to capture the
SQL operations executed by upgrade(). This validates migration logic without
requiring a live database. Real bcrypt hashes are generated with passlib
where the migration must verify a candidate hash against the legacy
password.

Spec: production admin credential hardening, 2026-07
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import uuid
from typing import Callable
from unittest.mock import MagicMock, patch

from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------

_VERSIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "alembic", "versions")
)


def _load_migration():
    """Import 013_admin_seed_hardening from alembic/versions/ with a fresh
    module each time."""
    if _VERSIONS_DIR not in sys.path:
        sys.path.insert(0, _VERSIONS_DIR)

    mod_name = "migration_013_admin_seed_hardening"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(
        mod_name,
        os.path.join(_VERSIONS_DIR, "013_admin_seed_hardening.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures / helpers shared by all tests
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "SuperSecret123!"
LEGACY_DEMO_EMAIL = "devrafaseros@gmail.com"
LEGACY_DEMO_PASSWORD = "admin123!"

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_hash(password: str) -> str:
    return _PWD_CONTEXT.hash(password)


def _env_without(*keys: str) -> dict:
    """Return a copy of the current environment with `keys` removed."""
    return {k: v for k, v in os.environ.items() if k not in keys}


Predicate = Callable[[str, dict], bool]


def _make_conn(rules: list[tuple[Predicate, object]]) -> MagicMock:
    """Build a mock connection whose `.execute(...).scalar()` result is
    controlled by `rules` — an ordered list of (predicate, scalar_value)
    pairs matched against (lowercased sql text, bound params).

    Every call is recorded on `conn.calls` for later assertions.
    """
    conn = MagicMock()
    calls: list[tuple[str, dict]] = []

    def _execute(stmt, params=None, **kwargs):
        sql_text = str(stmt).lower().strip()
        bound_params = dict(params or {})
        calls.append((sql_text, bound_params))
        result = MagicMock()
        for predicate, value in rules:
            if predicate(sql_text, bound_params):
                result.scalar.return_value = value
                break
        else:
            result.scalar.return_value = None
        return result

    conn.execute.side_effect = _execute
    conn.calls = calls
    return conn


def _run_upgrade(conn: MagicMock):
    m = _load_migration()

    import alembic.op as alembic_op_real

    original_get_bind = alembic_op_real.get_bind
    try:
        alembic_op_real.get_bind = lambda: conn
        m.upgrade()
    finally:
        alembic_op_real.get_bind = original_get_bind
    return m


def _inserts(calls: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return [(s, p) for s, p in calls if s.startswith("insert into")]


def _updates(calls: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return [(s, p) for s, p in calls if s.startswith("update")]


def _deletes(calls: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return [(s, p) for s, p in calls if s.startswith("delete")]


# Predicates matching the specific queries the migration issues.


def _is_admin_count(sql: str, params: dict) -> bool:
    return "count(*)" in sql and "admin_email" in sql


def _is_legacy_count(sql: str, params: dict) -> bool:
    return "count(*)" in sql and "legacy_email" in sql


def _is_tenant_lookup(sql: str, params: dict) -> bool:
    return "select id from tenants" in sql


def _is_legacy_hash_lookup(sql: str, params: dict) -> bool:
    return "select hashed_password from users" in sql


# ---------------------------------------------------------------------------
# 1. Metadata
# ---------------------------------------------------------------------------


class TestMigrationMetadata:
    def test_revision_is_013(self):
        m = _load_migration()
        assert m.revision == "013", f"Expected revision='013', got {m.revision!r}"

    def test_down_revision_is_012(self):
        m = _load_migration()
        assert m.down_revision == "012", (
            f"Expected down_revision='012', got {m.down_revision!r}"
        )

    def test_docstring_mentions_non_destructive_and_idempotent(self):
        m = _load_migration()
        doc = (m.__doc__ or "").lower()
        assert "non-destructive" in doc or "not destructive" in doc, (
            "Docstring must state the migration is non-destructive"
        )
        assert "idempotent" in doc, "Docstring must state the migration is idempotent"

    def test_docstring_explains_why_public_repo_hardcoded_credentials(self):
        m = _load_migration()
        doc = (m.__doc__ or "").lower()
        assert "public" in doc, "Docstring must explain the repo is public"
        assert "hardcoded" in doc or "hard-coded" in doc, (
            "Docstring must mention the hardcoded demo credential"
        )

    def test_legacy_constants_match_migration_012(self):
        m = _load_migration()
        assert m.LEGACY_DEMO_EMAIL == "devrafaseros@gmail.com"
        assert m.LEGACY_DEMO_PASSWORD == "admin123!"


# ---------------------------------------------------------------------------
# 2. ADMIN_EMAIL row already exists -> UPDATE in place, no INSERT
# ---------------------------------------------------------------------------


class TestAdminEmailRowAlreadyExists:
    def test_updates_existing_admin_row_no_insert(self):
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_conn(
                [
                    (_is_admin_count, 1),
                    (_is_legacy_hash_lookup, None),
                ]
            )
            _run_upgrade(conn)

        admin_updates = [
            (s, p)
            for s, p in _updates(conn.calls)
            if p.get("admin_email") == ADMIN_EMAIL and "role" in p
        ]
        assert len(admin_updates) == 1, (
            f"Expected exactly one admin UPDATE, got: {conn.calls}"
        )
        _, params = admin_updates[0]
        assert params["hashed_password"].startswith("$2")
        assert params["role"] == "admin"
        assert params["is_active"] is True
        assert params["email_verified"] is True

        assert not _inserts(conn.calls), (
            f"No INSERT expected when ADMIN_EMAIL row already exists, "
            f"got: {_inserts(conn.calls)}"
        )


# ---------------------------------------------------------------------------
# 3. No ADMIN_EMAIL row, legacy row exists -> in-place rename UPDATE
# ---------------------------------------------------------------------------


class TestLegacyRowRename:
    def test_renames_legacy_row_in_place(self):
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_conn(
                [
                    (_is_admin_count, 0),
                    (_is_legacy_count, 1),
                    (_is_legacy_hash_lookup, None),
                ]
            )
            _run_upgrade(conn)

        rename_updates = [
            (s, p)
            for s, p in _updates(conn.calls)
            if p.get("new_email") == ADMIN_EMAIL
            and p.get("legacy_email") == LEGACY_DEMO_EMAIL
        ]
        assert len(rename_updates) == 1, (
            f"Expected exactly one rename UPDATE, got: {conn.calls}"
        )
        _, params = rename_updates[0]
        assert params["hashed_password"].startswith("$2")
        assert params["role"] == "admin"

        assert not _inserts(conn.calls), "Rename path must not INSERT"
        assert not _deletes(conn.calls), "Rename path must not DELETE"


# ---------------------------------------------------------------------------
# 4. Neither row exists, tenant exists -> INSERT user bound to that tenant
# ---------------------------------------------------------------------------


class TestFreshInsertWithExistingTenant:
    def test_inserts_admin_user_bound_to_existing_tenant(self):
        existing_tenant_id = str(uuid.uuid4())
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_conn(
                [
                    (_is_admin_count, 0),
                    (_is_legacy_count, 0),
                    (_is_tenant_lookup, existing_tenant_id),
                    (_is_legacy_hash_lookup, None),
                ]
            )
            _run_upgrade(conn)

        tenant_inserts = _inserts(conn.calls)
        tenant_inserts = [
            (s, p) for s, p in tenant_inserts if s.startswith("insert into tenants")
        ]
        assert not tenant_inserts, (
            "Must not create a tenant when one already exists"
        )

        user_inserts = [
            (s, p) for s, p in _inserts(conn.calls) if s.startswith("insert into users")
        ]
        assert len(user_inserts) == 1, f"Expected one user INSERT, got: {conn.calls}"
        _, params = user_inserts[0]
        assert params["email"] == ADMIN_EMAIL
        assert params["role"] == "admin"
        assert params["tenant_id"] == existing_tenant_id
        assert params["hashed_password"].startswith("$2")


# ---------------------------------------------------------------------------
# 5. Neither row exists, no tenant -> INSERT tenant then INSERT user
# ---------------------------------------------------------------------------


class TestFreshInsertWithNewTenant:
    def test_inserts_tenant_then_admin_user(self):
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_conn(
                [
                    (_is_admin_count, 0),
                    (_is_legacy_count, 0),
                    (_is_tenant_lookup, None),
                    (_is_legacy_hash_lookup, None),
                ]
            )
            _run_upgrade(conn)

        insert_stmts = _inserts(conn.calls)
        assert len(insert_stmts) == 2, (
            f"Expected exactly 2 INSERT statements (tenant + user), got: {insert_stmts}"
        )
        assert insert_stmts[0][0].startswith("insert into tenants"), (
            f"First INSERT must be for tenants, got: {insert_stmts[0][0][:60]}"
        )
        assert insert_stmts[1][0].startswith("insert into users"), (
            f"Second INSERT must be for users, got: {insert_stmts[1][0][:60]}"
        )

        tenant_params = insert_stmts[0][1]
        free_tier_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "sigdoc.tier.free"))
        assert tenant_params.get("tier_id") == free_tier_id, (
            f"Tenant tier_id must be the Free tier UUID, got {tenant_params.get('tier_id')!r}"
        )
        assert tenant_params.get("is_active") is True

        user_params = insert_stmts[1][1]
        assert user_params.get("tenant_id") == tenant_params.get("id"), (
            "User must be bound to the newly created tenant"
        )
        assert user_params.get("role") == "admin"
        assert user_params.get("email") == ADMIN_EMAIL
        assert user_params.get("hashed_password", "").startswith("$2")


# ---------------------------------------------------------------------------
# 6. Env absent -> no admin seeding INSERT/UPDATE, no raise
# ---------------------------------------------------------------------------


class TestEnvAbsent:
    def test_no_seeding_when_env_vars_absent(self):
        env = _env_without("ADMIN_EMAIL", "ADMIN_PASSWORD")
        with patch.dict(os.environ, env, clear=True):
            conn = _make_conn(
                [
                    (_is_legacy_hash_lookup, None),
                ]
            )
            _run_upgrade(conn)  # must not raise

        assert not _inserts(conn.calls), "No INSERT expected when env vars are unset"
        assert not _updates(conn.calls), "No UPDATE expected when env vars are unset"


# ---------------------------------------------------------------------------
# 7. Neutralization of the compromised legacy credential (both env cases)
# ---------------------------------------------------------------------------


class TestNeutralizesCompromisedLegacyCredential:
    def test_neutralizes_when_env_present(self):
        """ADMIN_EMAIL row exists separately from the legacy row; the legacy
        row still carries the known-compromised admin123! hash and must be
        neutralized in addition to the ADMIN_EMAIL update."""
        real_legacy_hash = _bcrypt_hash(LEGACY_DEMO_PASSWORD)
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_conn(
                [
                    (_is_admin_count, 1),
                    (_is_legacy_hash_lookup, real_legacy_hash),
                ]
            )
            _run_upgrade(conn)

        neutralize_updates = [
            (s, p)
            for s, p in _updates(conn.calls)
            if p.get("legacy_email") == LEGACY_DEMO_EMAIL and "role" not in p
        ]
        assert len(neutralize_updates) == 1, (
            f"Expected a neutralizing UPDATE for the legacy row, got: {conn.calls}"
        )
        _, params = neutralize_updates[0]
        assert not _PWD_CONTEXT.verify(LEGACY_DEMO_PASSWORD, params["hashed_password"]), (
            "Replacement hash must NOT verify against the known demo password"
        )

    def test_neutralizes_when_env_absent(self):
        """Even with no ADMIN_EMAIL/ADMIN_PASSWORD configured, a legacy row
        still carrying the compromised admin123! hash must be neutralized."""
        real_legacy_hash = _bcrypt_hash(LEGACY_DEMO_PASSWORD)
        env = _env_without("ADMIN_EMAIL", "ADMIN_PASSWORD")
        with patch.dict(os.environ, env, clear=True):
            conn = _make_conn(
                [
                    (_is_legacy_hash_lookup, real_legacy_hash),
                ]
            )
            _run_upgrade(conn)

        neutralize_updates = [
            (s, p)
            for s, p in _updates(conn.calls)
            if p.get("legacy_email") == LEGACY_DEMO_EMAIL and "role" not in p
        ]
        assert len(neutralize_updates) == 1, (
            f"Expected a neutralizing UPDATE for the legacy row, got: {conn.calls}"
        )
        _, params = neutralize_updates[0]
        assert not _PWD_CONTEXT.verify(LEGACY_DEMO_PASSWORD, params["hashed_password"]), (
            "Replacement hash must NOT verify against the known demo password"
        )


# ---------------------------------------------------------------------------
# 8. Legacy row re-passworded legitimately -> must NOT be touched
# ---------------------------------------------------------------------------


class TestLeavesRepasswordedLegacyRowAlone:
    def test_does_not_touch_legacy_row_with_different_password(self):
        other_hash = _bcrypt_hash("some-other-legit-password")
        env = _env_without("ADMIN_EMAIL", "ADMIN_PASSWORD")
        with patch.dict(os.environ, env, clear=True):
            conn = _make_conn(
                [
                    (_is_legacy_hash_lookup, other_hash),
                ]
            )
            _run_upgrade(conn)

        assert not _updates(conn.calls), (
            f"Legacy row with a different password must not be touched, "
            f"got: {conn.calls}"
        )


# ---------------------------------------------------------------------------
# 9. Malformed legacy hash -> treated as no-match, never raises
# ---------------------------------------------------------------------------


class TestMalformedLegacyHash:
    def test_malformed_hash_treated_as_no_match(self):
        """A garbage (non-bcrypt) stored hash must not crash passlib.verify
        and must not trigger a neutralizing UPDATE."""
        env = _env_without("ADMIN_EMAIL", "ADMIN_PASSWORD")
        with patch.dict(os.environ, env, clear=True):
            conn = _make_conn(
                [
                    (_is_legacy_hash_lookup, "not-a-real-hash"),
                ]
            )
            _run_upgrade(conn)  # must not raise

        assert not _updates(conn.calls), (
            f"A malformed legacy hash must be left alone, got: {conn.calls}"
        )


# ---------------------------------------------------------------------------
# 10. Double-run idempotency — two upgrades converge to the same end state
# ---------------------------------------------------------------------------


def _make_stateful_conn(users: dict[str, str], tenants: list[str]) -> MagicMock:
    """Mock connection backed by a tiny in-memory users/tenants state so the
    migration can be run twice and asserted to converge. `users` maps email
    to hashed_password; `tenants` is a list of tenant ids."""
    conn = MagicMock()
    calls: list[tuple[str, dict]] = []

    def _execute(stmt, params=None, **kwargs):
        sql = str(stmt).lower().strip()
        p = dict(params or {})
        calls.append((sql, p))
        result = MagicMock()
        result.scalar.return_value = None
        if "count(*)" in sql and "admin_email" in sql:
            result.scalar.return_value = 1 if p["admin_email"] in users else 0
        elif "count(*)" in sql and "legacy_email" in sql:
            result.scalar.return_value = 1 if p["legacy_email"] in users else 0
        elif "select id from tenants" in sql:
            result.scalar.return_value = tenants[0] if tenants else None
        elif "select hashed_password from users" in sql:
            result.scalar.return_value = users.get(p["legacy_email"])
        elif sql.startswith("insert into tenants"):
            tenants.append(p["id"])
        elif sql.startswith("insert into users"):
            users[p["email"]] = p["hashed_password"]
        elif sql.startswith("update") and "new_email" in p:
            users.pop(p["legacy_email"], None)
            users[p["new_email"]] = p["hashed_password"]
        elif sql.startswith("update") and "role" in p:
            users[p["admin_email"]] = p["hashed_password"]
        elif sql.startswith("update") and "legacy_email" in p:
            users[p["legacy_email"]] = p["hashed_password"]
        return result

    conn.execute.side_effect = _execute
    conn.calls = calls
    return conn


class TestDoubleRunIdempotency:
    def test_two_runs_converge_from_fresh_demo_state(self):
        """Starting from the state migration 012 leaves behind (single legacy
        admin with the demo password), two consecutive runs of 013 must end
        with exactly one user (ADMIN_EMAIL) whose password is the env one,
        the demo password dead, and no duplicate tenants or INSERTs."""
        users = {LEGACY_DEMO_EMAIL: _bcrypt_hash(LEGACY_DEMO_PASSWORD)}
        tenants = ["tenant-1"]
        with patch.dict(
            os.environ, {"ADMIN_EMAIL": ADMIN_EMAIL, "ADMIN_PASSWORD": ADMIN_PASSWORD}
        ):
            conn = _make_stateful_conn(users, tenants)
            _run_upgrade(conn)
            first_pass_users = dict(users)
            _run_upgrade(conn)

        assert set(first_pass_users) == {ADMIN_EMAIL}, (
            "First run must already converge to the env admin only"
        )
        assert set(users) == {ADMIN_EMAIL}, (
            f"Second run must not add or rename rows, got: {set(users)}"
        )
        assert len(tenants) == 1, "No duplicate tenant may be created"
        assert _PWD_CONTEXT.verify(ADMIN_PASSWORD, users[ADMIN_EMAIL])
        assert not _PWD_CONTEXT.verify(LEGACY_DEMO_PASSWORD, users[ADMIN_EMAIL])
        assert not _inserts(conn.calls), "No INSERT should occur in either run"


# ---------------------------------------------------------------------------
# 11. downgrade() is a no-op
# ---------------------------------------------------------------------------


class TestDowngrade:
    def test_downgrade_executes_no_sql(self):
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

        assert not sql_calls, f"downgrade() must be a no-op but executed: {sql_calls}"
