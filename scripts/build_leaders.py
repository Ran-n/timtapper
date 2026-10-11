#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.795206
Revised: 2026/10/11 17:43:10.912808

Refresh the leader list bundled with the app (src/timtapper/assets/data/leaders.json)
and the leader portraits (src/timtapper/assets/leaders/*.webp) from optcgapi.com.
Installed apps pick up new sets on their own; run this before a release so fresh
installs start current and skip that first download:

    uv run python scripts/build_leaders.py            # only portraits that are missing
    uv run python scripts/build_leaders.py --force    # re-crop every portrait
    uv run python scripts/fetch_davyback_portraits.py # then swap in davyback.gg's icons
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import httpx

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from catalog.optcgapi import CatalogError, fetch_leaders, fetch_sources  # noqa: E402
from catalog.portraits import BUNDLED_DIR, DEFAULT_FACE, Face, PortraitError, download, filename  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402

OUT = APP_DIR / "assets" / "data" / "leaders.json"
FACES = Path(__file__).resolve().parent / "portrait_crops.json"
# portraits taken from davyback.gg by fetch_davyback_portraits.py — never re-cropped here
EXTERNAL = Path(__file__).resolve().parent / "davyback_portraits.json"


def load_faces(path: Path = FACES) -> dict[str, Face]:
    return {code: Face(*box) for code, box in json.loads(path.read_text(encoding="utf-8")).items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--force", action="store_true", help="re-download portraits that already exist")
    args = parser.parse_args()
    setup_logging()
    log = get_logger("scripts.build_leaders")
    try:
        leaders = fetch_leaders()
        sources = fetch_sources()
    except CatalogError as exc:
        log.error("could not build the leader list: %s", exc)
        return 1
    payload = {
        "generated": dt.date.today().isoformat(),
        "sources": list(sources),  # lets the app tell when a newer set is out
        "leaders": [r.to_json() for r in leaders],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log.info("wrote %d leaders to %s", len(leaders), OUT)

    faces = load_faces()
    unplaced = [r.code for r in leaders if r.code not in faces]
    if unplaced:
        log.warning("no face placed for %s — default crop used; add them to %s", ", ".join(unplaced), FACES.name)
    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)
    external = set(json.loads(EXTERNAL.read_text(encoding="utf-8"))) if EXTERNAL.is_file() else set()
    todo = [
        r.code
        for r in leaders
        if r.code not in external and (args.force or not (BUNDLED_DIR / filename(r.code)).is_file())
    ]
    failed = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for code in todo:
            try:
                (BUNDLED_DIR / filename(code)).write_bytes(download(code, client, faces.get(code, DEFAULT_FACE)))
            except PortraitError as exc:
                log.error("portrait failed: %s", exc)
                failed.append(code)
    log.info(
        "portraits: %d written, %d failed, %d already present",
        len(todo) - len(failed),
        len(failed),
        len(leaders) - len(todo),
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
