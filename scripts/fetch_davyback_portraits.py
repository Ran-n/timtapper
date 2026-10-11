#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:43:10.736405
Revised: 2026/10/11 17:43:10.736405

Replace bundled leader portraits with davyback.gg's hand-made leader icons
where it has one. davyback.gg's terms forbid reusing its content without
written permission; this was done knowingly at the project owner's request.
Run after scripts/build_leaders.py; build_leaders.py leaves these portraits
alone (scripts/davyback_portraits.json lists them).

    uv run python scripts/fetch_davyback_portraits.py
"""

import io
import json
import re
import sys
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from catalog.portraits import BUNDLED_DIR, SIZE, filename  # noqa: E402
from catalog.repository import load_bundled  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402

SITE = "https://davyback.gg"
LIST = Path(__file__).resolve().parent / "davyback_portraits.json"
# srcset="/_app/immutable/assets/Buggy_OP16_041_blue.BNmwoE6n.webp 800w, ..."
_SRCSET = re.compile(r'srcset="([^"]+)"')
_ENTRY = re.compile(r"(/_app/immutable/assets/[^\s,]+_([A-Z]+\d*)_(\d{3})_[a-z_]+\.[\w-]+\.(?:png|webp))\s+(\d+)w")


def largest_icons(page: str) -> dict[str, str]:
    """Card code -> URL path of the widest icon variant on the page."""
    best: dict[str, tuple[int, str]] = {}
    for srcset in _SRCSET.findall(page):
        for path, prefix, number, width in _ENTRY.findall(srcset):
            code = f"{prefix}-{number}"
            if int(width) > best.get(code, (0, ""))[0]:
                best[code] = (int(width), path)
    return {code: path for code, (_w, path) in best.items()}


def to_portrait(raw: bytes) -> bytes:
    """Any icon image -> SIZE x SIZE WebP (centre-cropped square, transparency flattened onto black)."""
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    flat = Image.new("RGB", img.size, (0, 0, 0))
    flat.paste(img, mask=img.getchannel("A"))
    out = io.BytesIO()
    flat.save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def main() -> int:
    setup_logging()
    log = get_logger("scripts.fetch_davyback_portraits")
    ours = {r.code for r in load_bundled()}
    saved, failed = [], []
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "timtapper-build"}) as client:
        try:
            page = client.get(f"{SITE}/").raise_for_status().text
        except httpx.HTTPError as exc:
            log.error("could not load %s: %s", SITE, exc)
            return 1
        icons = {c: p for c, p in largest_icons(page).items() if c in ours}
        log.info("davyback.gg has icons for %d of our %d leaders", len(icons), len(ours))
        for code, path in sorted(icons.items()):
            try:
                raw = client.get(SITE + path).raise_for_status().content
                (BUNDLED_DIR / filename(code)).write_bytes(to_portrait(raw))
                saved.append(code)
            except (httpx.HTTPError, UnidentifiedImageError, OSError) as exc:
                log.error("icon for %s failed: %s", code, exc)
                failed.append(code)
    LIST.write_text(json.dumps(sorted(saved), indent=1) + "\n", encoding="utf-8")
    log.info("portraits from davyback.gg: %d written, %d failed", len(saved), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
