#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 10:32:25.298101
Revised: 2026/10/14 10:33:05.375380

Shared test-run plumbing in tests/conftest.py: the order tests run in.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location("tests_root_conftest", Path(__file__).with_name("conftest.py"))
root_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(root_conftest)


def _item(name, fixtures=(), app=None):
    callspec = SimpleNamespace(params={"app": app}) if app else None
    return SimpleNamespace(name=name, fixturenames=list(fixtures), callspec=callspec)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (_item("plain", ["db"]), False),
        (_item("web_check", ["playwright", "tmp_path"]), True),
        (_item("rendered_web", ["app"], app="web"), True),
        (_item("rendered_desktop", ["app"], app="desktop"), False),
        (_item("rendered_android", ["app"], app="android"), False),
        (SimpleNamespace(name="bare"), False),
    ],
)
def test_uses_playwright(item, expected):
    assert root_conftest.uses_playwright(item) is expected


@pytest.mark.regression
def test_playwright_tests_run_last_in_collected_order():
    """`-m live` ran the rendered web target before two asyncio tests; the shared Playwright's loop, still running,
    made both fail with "Runner.run() cannot be called from a running event loop"."""
    items = [
        _item("rendered_desktop", ["app"], app="desktop"),
        _item("rendered_web", ["app"], app="web"),
        _item("rendered_android", ["app"], app="android"),
        _item("web_check", ["playwright"]),
        _item("async_ui", ["ctx"]),
    ]
    root_conftest.pytest_collection_modifyitems(None, items)
    assert [it.name for it in items] == [
        "rendered_desktop",
        "rendered_android",
        "async_ui",
        "rendered_web",
        "web_check",
    ]
