"""
Centralized logging configuration for Paper-CAD backend.

Usage:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Processing started")
    logger.debug("Detail: %s", detail)
    logger.warning("Something unusual")
    logger.error("Operation failed: %s", err)
"""

import logging
import os
import sys

_configured = False


def setup_logging() -> None:
    """
    Configure root logger based on ENV.

    - development: DEBUG level, verbose format
    - demo/production: INFO level, concise format

    Call once at application startup. Subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    _configured = True

    env = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))

    if env in ("demo", "production"):
        level = logging.INFO
        fmt = "[%(levelname)s] %(name)s: %(message)s"
    else:
        level = logging.DEBUG
        fmt = "[%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers to avoid duplicates
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "httpcore", "httpx", "asyncio", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger, ensuring logging is configured.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    setup_logging()
    return logging.getLogger(name)
