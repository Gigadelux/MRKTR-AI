"""Logging setup: console plus a rotating file the dashboard can tail."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.backend.core.settings import Settings

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(settings: Settings) -> None:
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    console = logging.StreamHandler()
    root = logging.getLogger()
    root.handlers.clear()
    for handler in (file_handler, console):
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    root.setLevel(logging.INFO)
