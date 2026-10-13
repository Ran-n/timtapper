#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:10:19.051520
Revised: 2026/10/13 11:42:03.229450

Leader portraits: a small square crop of each leader card's art (the face sits
in the upper middle of every card; a two-character card gets one strip per face,
with the "SAMPLE" watermark lifted where it crosses one). Portraits for the bundled catalogue ship in
assets/leaders/; leaders added later by "Update leaders" get theirs downloaded
into the app's data dir.
"""

import io
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFilter, UnidentifiedImageError

from catalog.optcgapi import IMAGE_TIMEOUT, IMAGE_URL, client_session, is_card_code
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

# One face, or several for cards that show more than one character (Ace & Newgate):
# each face then fills an equal vertical strip of the portrait, left to right.
Faces = Face | tuple[Face, ...]

# opacity of the white "SAMPLE" watermark, measured on flat art under it (OP09-001, ST22-001)
WATERMARK_ALPHA = 0.717


@dataclass(frozen=True, slots=True)
class Overlay:
    """A flat white overlay to undo before cropping: the "SAMPLE" watermark's letter pieces as boxes
    (x0, y0, x1, y1, fractions of the card's WIDTH) and its opacity. Its position differs from card to
    card, so it's measured per card (scripts/portrait_overlays.json); the opacity is the same everywhere."""

    boxes: tuple[tuple[float, float, float, float], ...]
    alpha: float = WATERMARK_ALPHA


class PortraitError(Exception):
    """A card image could not be downloaded or decoded."""


def filename(code: str) -> str:
    """The portrait's file name. Raises ValueError for anything not shaped like a card code: a code restored from a
    backup is the user's input, and "../x" would name a file outside the portrait folders."""
    if not is_card_code(code):
        raise ValueError(f"not a card code: {code!r}")
    return f"{code}.webp"


def cache_dir() -> Path:
    path = data_dir() / "leaders"
    path.mkdir(parents=True, exist_ok=True)
    return path


def crop(card_image: bytes, faces: Faces = DEFAULT_FACE, size: int = SIZE, overlay: Overlay | None = None) -> bytes:
    """Card image bytes -> a size x size WebP around `faces`, each box kept inside the card. Raises PortraitError.
    With n faces, face i fills strip i of the portrait: a (side / n) x side box centred on it, side by side.
    An `overlay` is lifted off the card first."""
    try:
        img = Image.open(io.BytesIO(card_image)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise PortraitError(f"not an image: {exc}") from exc
    if overlay is not None:
        img = lift_overlay(img, overlay)
    faces = faces if isinstance(faces, tuple) else (faces,)
    if not faces:
        raise PortraitError("no face to crop")
    portrait = Image.new("RGB", (size, size))
    edges = [round(i * size / len(faces)) for i in range(len(faces) + 1)]
    for face, (left, right) in zip(faces, pairwise(edges), strict=True):
        box = _strip_box(img.size, face, len(faces))
        portrait.paste(img.crop(box).resize((right - left, size), Image.Resampling.LANCZOS), (left, 0))
    out = io.BytesIO()
    portrait.save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def lift_overlay(img: Image.Image, overlay: Overlay) -> Image.Image:
    """Undo a white overlay blended at `overlay.alpha` inside its boxes: shown = a * 255 + (1 - a) * original,
    so original = (shown - 255 a) / (1 - a). The boxes' antialiased, JPEG-ringed border is median-filtered away."""
    w = img.width
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    for x0, y0, x1, y1 in overlay.boxes:
        draw.rectangle((round(x0 * w), round(y0 * w), round(x1 * w) - 1, round(y1 * w) - 1), fill=255)
    a = overlay.alpha
    lifted = img.point([min(255, max(0, round((v - 255 * a) / (1 - a)))) for v in range(256)] * 3)
    out = Image.composite(lifted, img, mask.filter(ImageFilter.BoxBlur(0.5)))
    seam = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask.filter(ImageFilter.MinFilter(5)))
    return Image.composite(out.filter(ImageFilter.MedianFilter(5)), out, seam)


def _strip_box(card: tuple[int, int], face: Face, strips: int) -> tuple[int, int, int, int]:
    """Pixel box of one strip: `face.side` tall, 1/strips of that wide, centred on the face, inside the card."""
    w, h = card
    height = min(round(face.side * w), w, h)
    width = round(height / strips)
    x = min(max(round((face.cx * w) - width / 2), 0), w - width)
    y = min(max(round((face.cy * w) - height / 2), 0), h - height)
    return (x, y, x + width, y + height)


def download(code: str, client: httpx.Client, face: Faces = DEFAULT_FACE, overlay: Overlay | None = None) -> bytes:
    """The cropped portrait for `code`, fetched from the card API. Raises PortraitError."""
    try:
        response = client.get(IMAGE_URL.format(code=code))
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PortraitError(f"{code}: {exc}") from exc
    return crop(response.content, face, overlay=overlay)


def download_missing(codes: list[str], client: httpx.Client | None = None) -> tuple[int, int]:
    """Download portraits for leaders that have none yet into the cache. Returns (saved, failed)."""
    missing = [c for c in codes if source(c) is None]
    saved = failed = 0
    try:
        with client_session(client, IMAGE_TIMEOUT) as c:
            for code in missing:
                try:
                    _write_whole(cache_dir() / filename(code), download(code, c))
                    saved += 1
                # OSError: the cache folder is full or not writable; ValueError: not a card code
                except (PortraitError, OSError, ValueError) as exc:
                    _log.warning("portrait for %s not saved: %s", code, exc)
                    failed += 1
    finally:
        source.cache_clear()
    if missing:
        _log.info("portraits: %d downloaded, %d failed", saved, failed)
    return saved, failed


def _write_whole(path: Path, data: bytes) -> None:
    """Write `data` to a temporary file beside `path`, then move it into place: an app killed mid-write leaves no
    half portrait, which would count as downloaded and never be fetched again."""
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    partial.replace(path)


def local_file(code: str) -> Path | None:
    """`code`'s portrait on disk: the bundled one, else one downloaded later, else None (also for a code that is no
    card code)."""
    if not is_card_code(code):
        return None
    for folder in (BUNDLED_DIR, cache_dir()):
        path = folder / filename(code)
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=512)
def source(code: str) -> str | bytes | None:
    """What ft.Image(src=...) needs for `code`'s portrait: an asset path when bundled,
    the cached file's bytes when downloaded later (works on Android too), else None."""
    path = local_file(code)
    if path is None:
        return None
    return f"leaders/{path.name}" if path.parent == BUNDLED_DIR else path.read_bytes()
