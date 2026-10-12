#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:10:30.268389
Revised: 2026/10/12 01:50:31.256526

Leader portrait cropping, lookup (bundled asset / downloaded cache / none) and download.
"""

import io
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from catalog import portraits
from catalog.optcgapi import IMAGE_URL

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


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


def build_leaders():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_leaders", SCRIPTS / "build_leaders.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_bundled_leader_has_a_placed_face():
    from catalog.repository import load_bundled

    faces = build_leaders().load_faces()
    assert sorted(r.code for r in load_bundled() if r.code not in faces) == []
    for code, placed in faces.items():
        for face in placed if isinstance(placed, tuple) else (placed,):
            assert 0 <= face.cx <= 1 and 0 <= face.cy <= 1.4 and 0 < face.side <= 1, code


@pytest.mark.parametrize(
    ("code", "face"),
    [
        ("OP09-001", portraits.Face(0.45, 0.44, 0.3)),  # red Shanks: the old box showed only his hair
        ("OP05-002", portraits.Face(0.57, 0.41, 0.3)),  # Belo Betty: the old box showed one eye and her forehead
        # Ace & Newgate: one strip per face (the old box showed half of Ace's face and no Newgate)
        ("ST22-001", (portraits.Face(0.41, 0.23, 0.3), portraits.Face(0.81, 0.5, 0.34))),
    ],
)
def test_recropped_faces_are_placed(code, face):
    """Hand-fixed boxes that frame the whole face; a rebuild must not silently revert them."""
    assert build_leaders().load_faces()[code] == face


def test_load_faces_reads_single_and_split_boxes(tmp_path):
    path = tmp_path / "faces.json"
    path.write_text('{"A": [0.5, 0.4, 0.3], "B": [[0.3, 0.3, 0.2], [0.7, 0.5, 0.2]]}', encoding="utf-8")
    assert build_leaders().load_faces(path) == {
        "A": portraits.Face(0.5, 0.4, 0.3),
        "B": (portraits.Face(0.3, 0.3, 0.2), portraits.Face(0.7, 0.5, 0.2)),
    }


def test_two_faces_fill_one_half_each():
    # left mark at (150, 200) px, right mark at (450, 500) px; each face box is centred on its mark
    img = Image.new("RGB", (600, 838), (128, 128, 128))
    img.paste((0, 200, 0), (130, 180, 170, 220))
    img.paste((0, 0, 220), (430, 480, 470, 520))
    out = io.BytesIO()
    img.save(out, "PNG")
    faces = (portraits.Face(0.25, 1 / 3, 0.2), portraits.Face(0.75, 500 / 600, 0.2))
    portrait = Image.open(io.BytesIO(portraits.crop(out.getvalue(), faces)))
    assert portrait.size == (portraits.SIZE, portraits.SIZE)
    q, half = portraits.SIZE // 4, portraits.SIZE // 2
    left, right = portrait.getpixel((q, half)), portrait.getpixel((half + q, half))
    assert left[1] > 150 and left[2] < 80  # green mark centred in the left half
    assert right[2] > 150 and right[1] < 80  # blue mark centred in the right half


def test_crop_needs_a_face():
    with pytest.raises(portraits.PortraitError, match="no face"):
        portraits.crop(card_jpeg(), ())


def test_lift_overlay_restores_the_art():
    art = Image.new("RGB", (600, 838), (40, 120, 200))
    art.paste((200, 60, 30), (300, 0, 600, 838))  # two colours, so the box crosses an edge in the art
    a = portraits.WATERMARK_ALPHA
    marked = art.copy()
    box = (250, 350, 350, 450)
    region = marked.crop(box).point(lambda v: round(255 * a + (1 - a) * v))
    marked.paste(region, box)
    lifted = portraits.lift_overlay(marked, portraits.Overlay(((250 / 600, 350 / 600, 350 / 600, 450 / 600),)))
    for xy in [(270, 400), (330, 400), (300, 360), (100, 100)]:  # inside on both colours, near the edge, outside
        assert max(abs(p - q) for p, q in zip(lifted.getpixel(xy), art.getpixel(xy), strict=True)) <= 3, xy


def test_crop_applies_the_overlay():
    art = Image.new("RGB", (600, 838), (40, 120, 200))
    marked = art.point(lambda v: round(255 * portraits.WATERMARK_ALPHA + (1 - portraits.WATERMARK_ALPHA) * v))
    out = io.BytesIO()
    marked.save(out, "PNG")
    whole = portraits.Overlay(((0, 0, 1, 838 / 600),))
    plain = Image.open(io.BytesIO(portraits.crop(out.getvalue(), overlay=None))).convert("RGB")
    lifted = Image.open(io.BytesIO(portraits.crop(out.getvalue(), overlay=whole))).convert("RGB")
    assert plain.getpixel((80, 80))[0] > 150  # still washed out without it
    assert max(abs(p - q) for p, q in zip(lifted.getpixel((80, 80)), (40, 120, 200), strict=True)) <= 6


def test_overlays_file_is_valid():
    overlays = build_leaders().load_overlays()
    assert "ST22-001" in overlays  # Newgate's moustache sits under the watermark
    for code, overlay in overlays.items():
        assert overlay.boxes, code
        for x0, y0, x1, y1 in overlay.boxes:
            assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1.4, code


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
