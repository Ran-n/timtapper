#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:10:19.051520
Revised: 2026/10/11 17:31:28.535170

Leader portraits: a small square crop of each leader card's art (the face sits
in the upper middle of every card). Portraits for the bundled catalogue ship in
assets/leaders/; leaders added later by "Update leaders" get theirs downloaded
into the app's data dir.
"""

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from catalog.optcgapi import IMAGE_URL
from core.logging import get_logger
from core.paths import ASSETS_DIR, data_dir

_log = get_logger("catalog.portraits")

# ~ the source pixels in a face crop (cards are 600 px wide) and enough for 56 dp at 3x density
SIZE = 160
BUNDLED_DIR = ASSETS_DIR / "leaders"


@dataclass(frozen=True, slots=True)
class Face:
    """Where a card's face is: square center (cx, cy) and side, all as fractions of the card's WIDTH."""

    cx: float
    cy: float
    side: float


# Used when a card has no hand-placed face (scripts/portrait_crops.json): the upper middle,
# where most leader art puts the face, clear of the power number and the "SAMPLE" watermark.
DEFAULT_FACE = Face(0.41, 0.31, 0.46)


class PortraitError(Exception):
    """A card image could not be downloaded or decoded."""


def filename(code: str) -> str:
    return f"{code}.webp"


def cache_dir() -> Path:
    path = data_dir() / "leaders"
    path.mkdir(parents=True, exist_ok=True)
    return path


def crop(card_image: bytes, face: Face = DEFAULT_FACE, size: int = SIZE) -> bytes:
    """Card image bytes -> a size x size WebP around `face`, kept inside the card. Raises PortraitError."""
    try:
        img = Image.open(io.BytesIO(card_image)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise PortraitError(f"not an image: {exc}") from exc
    w, h = img.size
    side = min(round(face.side * w), w, h)
    x = min(max(round((face.cx * w) - side / 2), 0), w - side)
    y = min(max(round((face.cy * w) - side / 2), 0), h - side)
    box = (x, y, x + side, y + side)
    out = io.BytesIO()
    img.crop(box).resize((size, size), Image.Resampling.LANCZOS).save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def download(code: str, client: httpx.Client, face: Face = DEFAULT_FACE) -> bytes:
    """The cropped portrait for `code`, fetched from the card API. Raises PortraitError."""
    try:
        response = client.get(IMAGE_URL.format(code=code))
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PortraitError(f"{code}: {exc}") from exc
    return crop(response.content, face)


def download_missing(codes: list[str], client: httpx.Client | None = None) -> tuple[int, int]:
    """Download portraits for leaders that have none yet into the cache. Returns (saved, failed)."""
    missing = [c for c in codes if source(c) is None]
    saved = failed = 0
    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        for code in missing:
            try:
                (cache_dir() / filename(code)).write_bytes(download(code, client))
                saved += 1
            except PortraitError as exc:
                _log.warning("portrait download failed: %s", exc)
                failed += 1
    finally:
        if owns_client:
            client.close()
        source.cache_clear()
    if missing:
        _log.info("portraits: %d downloaded, %d failed", saved, failed)
    return saved, failed


@lru_cache(maxsize=512)
def source(code: str) -> str | bytes | None:
    """What ft.Image(src=...) needs for `code`'s portrait: an asset path when bundled,
    the cached file's bytes when downloaded later (works on Android too), else None."""
    if (BUNDLED_DIR / filename(code)).is_file():
        return f"leaders/{filename(code)}"
    cached = cache_dir() / filename(code)
    if cached.is_file():
        return cached.read_bytes()
    return None
