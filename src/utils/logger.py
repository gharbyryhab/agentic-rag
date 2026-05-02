"""Loguru-based logger with file + console handlers."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

_configured = False


def get_logger(name: str = "agentic_rag"):
    """Return the configured loguru logger."""
    global _configured
    if not _configured:
        _configured = True
        _logger.remove()

        log_dir = Path(__file__).resolve().parents[2] / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        _logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        )
        _logger.add(
            log_dir / "app.log",
            level="DEBUG",
            rotation="10 MB",
            retention="14 days",
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        )

    return _logger.bind(name=name)
