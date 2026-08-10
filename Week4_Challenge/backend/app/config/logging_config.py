"""Structured logging configuration.

Every agent invocation and every tool invocation is logged as a structured
(JSON-serializable) event — never as free-form prose — so that the execution
trace can be reconstructed and audited without re-reading chain-of-thought.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

import structlog

from app.config.settings import get_settings

_CONFIGURED = False


def configure_logging() -> None:
    """Idempotently configure structlog + stdlib logging handlers."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_dir_path / "evident.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler, file_handler]
    root_logger.setLevel(log_level)

    # Quiet down noisy third-party loggers while keeping our own verbose.
    for noisy in ("httpx", "httpcore", "openai", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound with a component name."""

    configure_logging()
    return structlog.get_logger(name)
