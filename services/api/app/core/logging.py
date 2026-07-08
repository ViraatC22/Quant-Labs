"""Structured-ish logging configuration for the API.

Keeps the standard-library logger but formats records with a stable prefix so
failure paths (AI provider errors, importer fallbacks, SSRF rejections) are
visible instead of silently swallowed. Call ``configure_logging`` once at app
startup; use ``get_logger(__name__)`` everywhere else.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False

_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = getattr(logging, _LEVEL, logging.INFO)
    logging.basicConfig(level=level, format=_FORMAT)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
