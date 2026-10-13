#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.795206
Revised: 2026/10/13 14:42:56.089178

Refresh the leader list bundled with the app (src/timtapper/assets/data/leaders.json)
and the leader portraits (src/timtapper/assets/leaders/*.webp) from optcgapi.com,
and the sets' release dates from Limitless TCG.
Installed apps pick up new sets on their own; run this before a release so fresh
installs start current and skip that first download:

    uv run python scripts/build_leaders.py            # only portraits that are missing
    uv run python scripts/build_leaders.py --force    # re-crop every portrait
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from PIL import Image

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from catalog.limitless import fetch_release_dates  # noqa: E402
from catalog.optcgapi import IMAGE_TIMEOUT, CatalogError, client_session, fetch_leaders, fetch_sources  # noqa: E402
from catalog.portraits import (  # noqa: E402
    BUNDLED_DIR,
    DEFAULT_FACE,
    OPAQUE,
    WATERMARK_ALPHA,
    Face,
    Faces,
    Overlay,
    PortraitError,
    Word,
    download,
    filename,
)  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402

OUT = APP_DIR / "assets" / "data" / "leaders.json"
FACES = Path(__file__).resolve().parent / "portrait_crops.json"
# "SAMPLE" watermark to lift off before cropping, for faces the watermark crosses
OVERLAYS = Path(__file__).resolve().parent / "portrait_overlays.json"
# the watermark's letters, white on black, cut from a card where it lies on dark art (OP05-060)
GLYPHS = Path(__file__).resolve().parent / "watermark.png"


def load_faces(path: Path = FACES) -> dict[str, Faces]:
    """Each code maps to one box [cx, cy, side], or a list of boxes for a card with several faces."""
    return {
        code: tuple(Face(*b) for b in box) if isinstance(box[0], list) else Face(*box)
        for code, box in json.loads(path.read_text(encoding="utf-8")).items()
    }


def load_overlays(path: Path = OVERLAYS, glyphs: Path = GLYPHS) -> dict[str, Overlay]:
    """Each code maps to its watermark letter boxes [[x0, y0, x1, y1], ...], or to {"word": [x, y, width]}: where
    the whole word sits, drawn with the glyph mask, plus "opaque": true for a solid watermark to paint over rather than
    lift. All fractions of the card width."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    letters = Image.open(glyphs).convert("L") if any(isinstance(v, dict) for v in raw.values()) else None
    return {
        code: Overlay(
            word=Word(*entry["word"]), glyphs=letters, alpha=OPAQUE if entry.get("opaque") else WATERMARK_ALPHA
        )
        if isinstance(entry, dict)
        else Overlay(tuple(tuple(b) for b in entry))
        for code, entry in raw.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--force", action="store_true", help="re-download portraits that already exist")
    args = parser.parse_args()
    setup_logging()
    log = get_logger("scripts.build_leaders")
    try:
        leaders = fetch_leaders()
        sources = fetch_sources()
        releases = fetch_release_dates()
    except CatalogError as exc:
        log.error("could not build the leader list: %s", exc)
        return 1
    payload = {
        "generated": dt.date.today().isoformat(),
        "sources": list(sources),  # lets the app tell when a newer set is out
        # set code -> English release date: a new event goes in the set out on its date
        "releases": {code: day.isoformat() for code, day in sorted(releases.items())},
        "leaders": [r.to_json() for r in leaders],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log.info("wrote %d leaders to %s", len(leaders), OUT)

    faces = load_faces()
    overlays = load_overlays()
    unplaced = [r.code for r in leaders if r.code not in faces]
    if unplaced:
        log.warning("no face placed for %s — default crop used; add them to %s", ", ".join(unplaced), FACES.name)
    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)
    todo = [r.code for r in leaders if args.force or not (BUNDLED_DIR / filename(r.code)).is_file()]
    failed = []
    with client_session(timeout=IMAGE_TIMEOUT) as client:
        for code in todo:
            try:
                (BUNDLED_DIR / filename(code)).write_bytes(
                    download(code, client, faces.get(code, DEFAULT_FACE), overlays.get(code))
                )
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
