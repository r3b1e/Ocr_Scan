"""Rotating file logging shared by every module.

All loggers live under the `ocr_scanner` namespace so a single call to
`setup_logging` configures the whole application.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT_LOGGER_NAME = "ocr_scanner"
LOG_FILE_NAME = "app.log"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(logs_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure the application logger with a rotating file and a stderr handler.

    Calling this more than once is safe: existing handlers are replaced rather
    than duplicated.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)
    file_handler = RotatingFileHandler(
        logs_dir / LOG_FILE_NAME, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger such as `ocr_scanner.core.camera`."""
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
