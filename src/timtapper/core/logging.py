#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.370391
Revised: 2026/10/13 22:54:37.921364

Logging setup for the whole app: one named logger tree (`timtapper.*`),
isolated from third-party noise, level configurable via `LOG_LEVEL`.
"""

import logging
import os
import sys
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager

APP_LOGGER = "timtapper"
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LEVEL = "INFO"


def get_logger(module: str) -> logging.Logger:
    """Logger for one module, nested under the app's root logger."""
    return logging.getLogger(f"{APP_LOGGER}.{module}")


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure the app logger once; safe to call again (no duplicate handlers)."""
    root = logging.getLogger(APP_LOGGER)
    wanted = (level or os.environ.get("LOG_LEVEL") or DEFAULT_LEVEL).upper()
    # a misspelt LOG_LEVEL ("verbose") would make setLevel raise and stop the app before it opens
    known = wanted in logging.getLevelNamesMapping()
    root.setLevel(wanted if known else DEFAULT_LEVEL)
    root.propagate = False
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        root.addHandler(handler)
    if not known:
        root.warning("unknown log level %r — using %s", wanted, DEFAULT_LEVEL)
    return root


class LogTail(logging.Handler):
    """Keeps the last `limit` formatted records, so a failure screen can show what led up to it."""

    def __init__(self, limit: int = 60) -> None:
        super().__init__(logging.DEBUG)
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        self.lines: deque[str] = deque(maxlen=limit)

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    @contextmanager
    def attached(self, *names: str, level: int = logging.INFO) -> Generator[LogTail]:
        """Collect from the `names` loggers at `level` or above while inside; their levels come back after."""
        loggers = [logging.getLogger(name) for name in names]
        saved = [lg.level for lg in loggers]
        for lg in loggers:
            lg.addHandler(self)
            if lg.getEffectiveLevel() > level:
                lg.setLevel(level)
        try:
            yield self
        finally:
            for lg, old in zip(loggers, saved, strict=True):
                lg.removeHandler(self)
                lg.setLevel(old)
