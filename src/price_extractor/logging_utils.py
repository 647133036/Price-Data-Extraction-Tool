from __future__ import annotations

import logging

from .config import ROOT, LoggingSettings


def setup_logging(settings: LoggingSettings) -> logging.Logger:
    log_dir = ROOT / settings.directory
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / settings.filename

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(settings.level.upper())
    root.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return logging.getLogger("price_extractor")
