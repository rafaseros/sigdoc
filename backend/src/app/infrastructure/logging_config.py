"""Application logging configuration.

Centralizes logging setup so every module logger (all created with
`logging.getLogger(__name__)`, which puts them under the `app.*` namespace)
emits through a single, consistently formatted StreamHandler to stdout.

Without this, the module-level `logger.info(...)` / `logger.warning(...)` calls
scattered across the codebase (audit fire-and-forget path, usage service, PDF
converter, ...) run under Python's default root configuration — WARNING+ only
and unformatted — so many lines are silently dropped and nothing is formatted
consistently.

`configure_logging()` is idempotent because it is driven by
`logging.config.dictConfig`, which *replaces* (never appends) the handlers on
the loggers it manages; calling it more than once therefore never duplicates
handlers. It also leaves uvicorn's own loggers untouched
(`disable_existing_loggers=False` and no uvicorn logger entries), so uvicorn's
error/access logs keep their own handlers and are neither silenced nor
double-logged (uvicorn sets `propagate=False` on those loggers).
"""
from __future__ import annotations

import logging
from logging.config import dictConfig

from app.config import Settings

# Consistent line shape: timestamp, level, logger name, message.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


def resolve_log_level(settings: Settings) -> str:
    """Return the effective root log level name.

    DEBUG when ``settings.debug`` is on, otherwise ``settings.log_level``
    (upper-cased). An unrecognized level string falls back to ``INFO`` so a
    configuration typo can never crash application startup.
    """
    if settings.debug:
        return "DEBUG"
    level = (settings.log_level or "INFO").upper()
    return level if level in _VALID_LEVELS else "INFO"


def configure_logging(settings: Settings) -> None:
    """Configure application logging once, idempotently.

    Installs a single stdout ``StreamHandler`` on the root logger with a
    consistent format and the level derived from ``settings``. Every module
    logger (``logging.getLogger(__name__)`` -> ``app.*``) propagates to root and
    is formatted uniformly. Safe to call multiple times: ``dictConfig`` replaces
    handlers rather than appending them, so no duplicates accumulate.
    """
    level = resolve_log_level(settings)
    dictConfig(
        {
            "version": 1,
            # Never disable/hijack loggers created before this call (notably
            # uvicorn's) — we only install our own root handler.
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": LOG_FORMAT,
                    "datefmt": LOG_DATE_FORMAT,
                },
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    # stdout so Docker / uvicorn capture it on the same stream.
                    "stream": "ext://sys.stdout",
                },
            },
            # Configure only the root logger. uvicorn's loggers set
            # propagate=False, so this handler does not double-log their output.
            "root": {
                "level": level,
                "handlers": ["stdout"],
            },
        }
    )
