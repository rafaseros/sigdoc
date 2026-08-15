"""Migration round-trip test for 017_document_group_labels.

Strategy (same as test_template_version_files_migration.py): patch the
functions on the `alembic.op` proxy module to capture the operations executed
by upgrade() and downgrade(). This validates the migration logic (correct
objects in the correct order) without requiring a separate test DB.

Migration 017 adds two columns to `documents`:
  - related_label   (nullable) — NULL = primary; the related file's label
                                  for related documents.
  - group_position  (NOT NULL, server_default 0) — 0 = primary, 1..N =
                                  related files in render (position) order.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_migration():
    """Import 017_document_group_labels from alembic/versions/."""
    versions_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "alembic", "versions"
    )
    versions_dir = os.path.abspath(versions_dir)
    if versions_dir not in sys.path:
        sys.path.insert(0, versions_dir)
    mod_name = "migration_017_document_group_labels"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        os.path.join(versions_dir, "017_document_group_labels.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _OpRecorder:
    """Patch the alembic.op functions used by 017 and record every call."""

    FUNCS = ("add_column", "drop_column")

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
    def test_revision_is_017(self):
        m = _load_migration()
        assert m.revision == "017"

    def test_down_revision_is_016(self):
        m = _load_migration()
        assert m.down_revision == "016"


class TestUpgradeOperations:
    def test_adds_related_label_and_group_position_columns(self):
        m = _load_migration()
        with _OpRecorder() as rec:
            m.upgrade()

        add_columns = rec.named("add_column")
        # Two columns added, both on the documents table
        assert len(add_columns) == 2
        tables = {c[1][0] for c in add_columns}
        assert tables == {"documents"}

        cols = {c[1][1].name: c[1][1] for c in add_columns}
        assert set(cols) == {"related_label", "group_position"}

        # related_label — nullable
        assert cols["related_label"].nullable is True

        # group_position — NOT NULL with a server_default of 0
        assert cols["group_position"].nullable is False
        assert cols["group_position"].server_default is not None
        assert "0" in str(cols["group_position"].server_default.arg)


class TestDowngradeOperations:
    def test_downgrade_drops_both_columns(self):
        m = _load_migration()
        with _OpRecorder() as rec:
            m.downgrade()

        drop_columns = rec.named("drop_column")
        assert len(drop_columns) == 2
        dropped = [(c[1][0], c[1][1]) for c in drop_columns]
        # Both dropped from documents; group_position first (reverse of add)
        assert dropped == [
            ("documents", "group_position"),
            ("documents", "related_label"),
        ]
