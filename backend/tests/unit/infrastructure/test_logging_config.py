"""Unit tests for application logging configuration.

Verifies that configure_logging() derives the level correctly, is idempotent
(no duplicate handlers on repeated calls), and leaves stdlib logging in a
consistent state. The root logger is snapshotted/restored so these tests never
leak handler state into the rest of the suite.
"""
import logging

import pytest

from app.config import Settings
from app.infrastructure.logging_config import (
    LOG_FORMAT,
    configure_logging,
    resolve_log_level,
)


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """Snapshot and restore the root logger around each test.

    configure_logging() reconfigures the root logger via dictConfig, which
    replaces its handlers. Restoring afterwards keeps pytest's own log capture
    intact and prevents cross-test bleed.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def _make_settings(**overrides) -> Settings:
    # Required fields (database_url, secret_key, minio_*) come from the test env
    # set in tests/conftest.py; overrides pin the logging-relevant fields.
    return Settings(**overrides)


def test_configure_logging_sets_level_from_settings():
    configure_logging(_make_settings(log_level="WARNING", debug=False))
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_lowercase_level_is_normalized():
    configure_logging(_make_settings(log_level="error", debug=False))
    assert logging.getLogger().level == logging.ERROR


def test_debug_flag_forces_debug_level():
    # debug=True overrides an explicit higher log_level.
    configure_logging(_make_settings(log_level="ERROR", debug=True))
    assert logging.getLogger().level == logging.DEBUG


def test_invalid_log_level_falls_back_to_info():
    assert resolve_log_level(_make_settings(log_level="NONSENSE")) == "INFO"
    configure_logging(_make_settings(log_level="NONSENSE", debug=False))
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_is_idempotent_no_duplicate_handlers():
    settings = _make_settings(log_level="INFO")

    configure_logging(settings)
    first = len(logging.getLogger().handlers)

    configure_logging(settings)
    second = len(logging.getLogger().handlers)

    assert first == second == 1


def test_configure_logging_installs_stdout_stream_handler_with_format():
    import sys

    configure_logging(_make_settings(log_level="INFO"))
    handlers = logging.getLogger().handlers

    assert len(handlers) == 1
    handler = handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert handler.formatter is not None
    assert handler.formatter._fmt == LOG_FORMAT
