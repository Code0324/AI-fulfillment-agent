"""Structured application logging configuration."""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application.

    Uses JSON-style structured output in production and a
    human-readable format during development.
    """
    log_level = logging.DEBUG if settings.is_development else logging.INFO

    formatter: logging.Formatter
    if settings.is_development:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# Convenience logger for application code
logger = logging.getLogger("app")
