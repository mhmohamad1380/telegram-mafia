"""Structured logging configuration using structlog.

Provides a single :func:`configure_logging` entrypoint that wires the standard
library ``logging`` module and structlog together. In development we render
colorized, human-friendly console output; in production we emit JSON so logs can
be ingested by aggregators.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, level: str = "INFO", console: bool = True) -> None:
    """Configure structlog + stdlib logging.

    Args:
        level: Minimum log level (e.g. ``"INFO"``, ``"DEBUG"``).
        console: If ``True``, render pretty console logs; otherwise JSON.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors applied to every event before final rendering.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if console:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (aiogram, sqlalchemy, etc.) through a basic handler so
    # third-party log lines still appear, but keep them at WARNING to avoid noise.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, optionally namespaced by ``name``."""
    return structlog.get_logger(name)
