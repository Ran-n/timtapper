#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.566957
Revised: 2026/10/11 16:27:24.066000

`uv run timtapper`: desktop launch from the installed package. The app's
modules import each other as top-level packages (the layout flet build
packages), so put this directory on sys.path before handing over to main.
"""

import sys
from pathlib import Path


def run() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import main

    main.run()
