#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.370391
Revised: 2026/10/11 16:27:21.791840

Logging setup for the whole app: one named logger tree (`timtapper.*`),
isolated from third-party noise, level configurable via `LOG_LEVEL`.
"""

import logging
import os
import sys

APP_LOGGER = "timtapper"
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(module: str) -> logging.Logger:
    """Logger for one module, nested under the app's root logger."""
    return logging.getLogger(f"{APP_LOGGER}.{module}")


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure the app logger once; safe to call again (no duplicate handlers)."""
    root = logging.getLogger(APP_LOGGER)
    root.setLevel((level or os.environ.get("LOG_LEVEL") or "INFO").upper())
    root.propagate = False
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        root.addHandler(handler)
    return root
