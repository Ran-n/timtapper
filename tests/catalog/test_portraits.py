#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:10:30.268389
Revised: 2026/10/11 17:25:07.119266

Leader portrait cropping, lookup (bundled asset / downloaded cache / none) and download.
"""

import io

import httpx
import pytest
import respx
from PIL import Image

from catalog import portraits
from catalog.optcgapi import IMAGE_URL


def card_jpeg(w=600, h=838) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(out, "JPEG")
    return out.getvalue()


@pytest.mark.parametrize(("w", "h"), [(600, 838), (300, 419), (1200, 1676)])
def test_crop_is_a_square_webp(w, h):
    img = Image.open(io.BytesIO(portraits.crop(card_jpeg(w, h))))
    assert img.format == "WEBP"
    assert img.size == (portraits.SIZE, portraits.SIZE)


def marked_card(mark_box, w=600, h=838) -> bytes:
    """A grey card with a green square at mark_box (pixels)."""
    img = Image.new("RGB", (w, h), (128, 128, 128))
    img.paste((0, 200, 0), mark_box)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_crop_centers_on_the_placed_face():
    # green square centered at (450, 300) px = (0.75, 0.5) of the card width
    face = portraits.Face(0.75, 0.5, 0.2)
    img = Image.open(io.BytesIO(portraits.crop(marked_card((420, 270, 480, 330)), face)))
    r, g, b = img.getpixel((portraits.SIZE // 2, portraits.SIZE // 2))
    assert g > 150 and r < 60  # center of the portrait is the mark
    assert img.getpixel((2, 2))[1] < 150  # corners are card, not mark


@pytest.mark.parametrize(
    "face",
    [portraits.Face(0.0, 0.0, 0.3), portraits.Face(1.0, 1.4, 0.3), portraits.Face(0.5, 0.5, 2.0)],
    ids=["top-left", "bottom-right", "larger-than-card"],
)
def test_crop_keeps_the_box_inside_the_card(face):
    assert Image.open(io.BytesIO(portraits.crop(card_jpeg(), face))).size == (portraits.SIZE, portraits.SIZE)


def test_every_bundled_leader_has_a_placed_face():
    import json
    from pathlib import Path

    from catalog.repository import load_bundled

    path = Path(__file__).resolve().parents[2] / "scripts" / "portrait_crops.json"
    faces = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(r.code for r in load_bundled() if r.code not in faces) == []
    for code, (cx, cy, side) in faces.items():
        assert 0 <= cx <= 1 and 0 <= cy <= 1.4 and 0 < side <= 1, code


def test_crop_custom_size():
    assert Image.open(io.BytesIO(portraits.crop(card_jpeg(), size=40))).size == (40, 40)


@pytest.mark.parametrize("junk", [b"", b"not an image", b"<html>404</html>"])
def test_crop_rejects_non_images(junk):
    with pytest.raises(portraits.PortraitError):
        portraits.crop(junk)


def test_every_bundled_leader_has_a_portrait():
    from catalog.repository import load_bundled

    missing = [r.code for r in load_bundled() if not (portraits.BUNDLED_DIR / portraits.filename(r.code)).is_file()]
    assert missing == []


def test_source_prefers_bundled_asset():
    assert portraits.source("OP01-001") == "leaders/OP01-001.webp"


def test_source_cached_and_missing():
    assert portraits.source("OP99-001") is None
    (portraits.cache_dir() / "OP99-001.webp").write_bytes(b"webp")
    assert portraits.source("OP99-001") is None  # memoised until the next download
    portraits.source.cache_clear()
    assert portraits.source("OP99-001") == b"webp"


@respx.mock
def test_download_missing_saves_new_skips_known_and_counts_failures():
    ok = respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=card_jpeg()))
    respx.get(IMAGE_URL.format(code="OP99-002")).mock(return_value=httpx.Response(404))
    respx.get(IMAGE_URL.format(code="OP99-003")).mock(return_value=httpx.Response(200, content=b"<html>"))
    respx.get(IMAGE_URL.format(code="OP99-004")).mock(side_effect=httpx.ConnectError("offline"))
    bundled = respx.get(IMAGE_URL.format(code="OP01-001"))
    saved, failed = portraits.download_missing(["OP01-001", "OP99-001", "OP99-002", "OP99-003", "OP99-004"])
    assert (saved, failed) == (1, 3)
    assert ok.called and not bundled.called
    assert isinstance(portraits.source("OP99-001"), bytes)  # cache cleared, new file visible
    assert portraits.source("OP99-002") is None


def test_download_missing_nothing_to_do():
    assert portraits.download_missing(["OP01-001"]) == (0, 0)
