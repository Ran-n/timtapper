#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 13:05:25.583730
Revised: 2026/10/15 00:58:28.881651

What the app loads before its first screen: on the web every package it imports there is unpacked and compiled in
the browser (Pyodide) while the visitor waits, so the heavy ones it only needs later stay out of the startup path.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "timtapper"
# loaded only by a leader update or a share card (PIL, which the web build loads only then), or only by the libraries'
# test suites, which the web build leaves out of the Python archive (scripts/build_web.py UNUSED)
NOT_AT_STARTUP = ("PIL", "sqlalchemy.testing", "alembic.testing")

STARTUP = """
import json, sys
import main
main.open_database()
print(json.dumps(sorted(sys.modules)))
"""


@pytest.fixture(scope="module")
def startup_modules(tmp_path_factory) -> set[str]:
    """Modules loaded after importing the app and opening a fresh database, as main() does, in a clean interpreter."""
    storage = tmp_path_factory.mktemp("storage")
    env = os.environ | {"FLET_APP_STORAGE_DATA": str(storage), "FLET_APP_STORAGE_TEMP": str(storage / "tmp")}
    result = subprocess.run(
        [sys.executable, "-c", STARTUP], cwd=APP, env=env, capture_output=True, text=True, check=True
    )
    return set(json.loads(result.stdout.splitlines()[-1]))


@pytest.mark.regression
@pytest.mark.parametrize("package", NOT_AT_STARTUP)
def test_startup_leaves_out(startup_modules, package):
    """PIL was imported at startup (through ui.widgets -> catalog.portraits, and the share views), which on the web
    held up the first screen while its WebAssembly extensions loaded."""
    assert not {m for m in startup_modules if m == package or m.startswith(f"{package}.")}


def test_startup_does_load_the_database_stack(startup_modules):
    """The check above sees real imports: the libraries the startup path needs are there."""
    assert {"sqlalchemy", "alembic", "flet"} <= startup_modules


@pytest.mark.regression
def test_the_driven_app_imports_no_pil_either():
    """The web build leaves PIL out of its archive, so a module that imports it at the top can't start there: the
    driven test app's demo_driver did, and the driven web build never started."""
    code = "import json, sys\nimport driven_main\nprint(json.dumps(sorted(sys.modules)))"
    env = os.environ | {"PYTHONPATH": os.pathsep.join([str(APP), str(ROOT / "scripts")])}
    result = subprocess.run([sys.executable, "-c", code], cwd=APP, env=env, capture_output=True, text=True, check=True)
    assert not {m for m in json.loads(result.stdout.splitlines()[-1]) if m == "PIL" or m.startswith("PIL.")}
