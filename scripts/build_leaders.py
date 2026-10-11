#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.795206
Revised: 2026/10/11 16:27:24.282640

Refresh the leader list bundled with the app (src/timtapper/assets/data/leaders.json)
from optcgapi.com. Run before a release when new sets are out:

    uv run python scripts/build_leaders.py
"""

import datetime as dt
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from catalog.optcgapi import CatalogError, fetch_leaders  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402

OUT = APP_DIR / "assets" / "data" / "leaders.json"


def main() -> int:
    setup_logging()
    log = get_logger("scripts.build_leaders")
    try:
        leaders = fetch_leaders()
    except CatalogError as exc:
        log.error("could not build the leader list: %s", exc)
        return 1
    payload = {"generated": dt.date.today().isoformat(), "leaders": [r.to_json() for r in leaders]}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log.info("wrote %d leaders to %s", len(leaders), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
