"""Migration round-trip test for 016_template_version_files.

Strategy (same as test_role_migration.py): patch the functions on the
`alembic.op` proxy module to capture the operations executed by upgrade()
and downgrade(). This validates the migration logic (correct objects in the
correct order) without requiring a separate test DB.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_migration():
    """Import 016_template_version_files from alembic/versions/."""
    versions_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic", "versions"
    )
    versions_dir = os.path.abspath(versions_dir)
    if versions_dir not in sys.path:
        sys.path.insert(0, versions_dir)
    mod_name = "migration_016_template_version_files"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        os.path.join(versions_dir, "016_template_version_files.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _OpRecorder:
    """Patch the alembic.op functions used by 016 and record every call."""

    FUNCS = (
        "create_table",
        "create_index",
        "add_column",
        "drop_index",
        "drop_column",
        "drop_table",
    )

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self._originals: dict[str, object] = {}

    def __enter__(self):
        import alembic.op as alembic_op

        for name in self.FUNCS:
            self._originals[name] = getattr(alembic_op, name, None)

            def _make_recorder(op_name):
                def _record(*args, **kwargs):
                    self.calls.append((op_name, args, kwargs))

                return _record

            setattr(alembic_op, name, _make_recorder(name))
        return self

    def __exit__(self, *exc):
        import alembic.op as alembic_op

        for name, original in self._originals.items():
            if original is not None:
                setattr(alembic_op, name, original)
            else:
                delattr(alembic_op, name)
        return False

    def named(self, op_name: str) -> list[tuple[str, tuple, dict]]:
        return [c for c in self.calls if c[0] == op_name]


class TestMigrationMetadata:
    def test_revision_is_016(self):
        m = _load_migration()
        assert m.revision == "016"

    def test_down_revision_is_015(self):
        m = _load_migration()
        assert m.down_revision == "015"

    def test_docstring_documents_lossy_downgrade(self):
        m = _load_migration()
        assert "lossy" in (m.__doc__ or "").lower()


class TestUpgradeOperations:
    def test_creates_files_table_indexes_and_group_column(self):
        m = _load_migration()
        with _OpRecorder() as rec:
            m.upgrade()

        # 1. template_version_files table with the expected columns
        create_tables = rec.named("create_table")
        assert len(create_tables) == 1
        _, args, _ = create_tables[0]
        assert args[0] == "template_version_files"
        column_names = {
            col.name for col in args[1:] if hasattr(col, "name") and col.name
        }
        assert {
            "id",
            "tenant_id",
            "version_id",
            "label",
            "minio_path",
            "variables",
            "file_size",
            "position",
            "created_at",
        } <= column_names

        # 2. documents.group_id nullable column
        add_columns = rec.named("add_column")
        assert len(add_columns) == 1
        _, args, _ = add_columns[0]
        assert args[0] == "documents"
        assert args[1].name == "group_id"
        assert args[1].nullable is True

        # 3. Indexes: composite files index + partial documents group index
        index_names = [c[1][0] for c in rec.named("create_index")]
        assert "ix_template_version_files_tenant_version" in index_names
        assert "ix_documents_tenant_group" in index_names

        group_index = next(
            c for c in rec.named("create_index")
            if c[1][0] == "ix_documents_tenant_group"
        )
        _, args, kwargs = group_index
        assert args[1] == "documents"
        assert args[2] == ["tenant_id", "group_id"]
        assert "group_id IS NOT NULL" in str(kwargs.get("postgresql_where"))

    def test_upgrade_creates_table_before_indexes(self):
        m = _load_migration()
        with _OpRecorder() as rec:
            m.upgrade()

        op_order = [c[0] for c in rec.calls]
        assert op_order.index("create_table") < op_order.index("create_index")


class TestDowngradeOperations:
    def test_downgrade_reverses_upgrade(self):
        m = _load_migration()
        with _OpRecorder() as rec:
            m.downgrade()

        op_order = [(c[0], c[1][0]) for c in rec.calls]
        assert op_order == [
            ("drop_index", "ix_documents_tenant_group"),
            ("drop_column", "documents"),
            ("drop_index", "ix_template_version_files_tenant_version"),
            ("drop_table", "template_version_files"),
        ]

        drop_column = rec.named("drop_column")[0]
        assert drop_column[1] == ("documents", "group_id")
