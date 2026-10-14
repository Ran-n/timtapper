#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.055435
Revised: 2026/10/14 08:10:02.249097

One real app per target for the whole rendered-test session, and every rendered test runs on each target:
desktop (marker `desktop`), web (`web`) and Android (`android`), all kept out of the default run. targets.py
starts and drives them.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TARGETS = [
    pytest.param("desktop", marks=pytest.mark.desktop),
    pytest.param("web", marks=pytest.mark.web),
    pytest.param("android", marks=pytest.mark.android),
]


@pytest.fixture(scope="session", params=TARGETS)
def app(request, tmp_path_factory):
    from targets import open_target

    # only the web target needs Playwright (its fixture skips where it isn't installed)
    playwright = request.getfixturevalue("playwright") if request.param == "web" else None
    target = open_target(request.param, tmp_path_factory.mktemp(request.param), playwright)
    yield target
    target.quit()


@pytest.fixture
def scheme():
    """The palette the driver shows by default (gruvbox), per mode."""
    from ui.theme import get_theme

    return lambda mode="dark": get_theme("gruvbox").scheme(dark=mode == "dark")
