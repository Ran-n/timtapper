#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:10:30.268389
Revised: 2026/10/13 11:42:03.666869

Leader portrait cropping, lookup (bundled asset / downloaded cache / none) and download.
"""

import io
from pathlib import Path

import httpx
import pytest
import respx
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from catalog import portraits
from catalog.optcgapi import IMAGE_URL

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def card_jpeg(w=600, h=838) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(out, "JPEG")
    return out.getvalue()


# a shared card for the property tests, built once (hypothesis reruns them many times)
CARD = card_jpeg()


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


# ---- split crops, more cases ---------------------------------------------------
def test_three_faces_split_the_width_evenly():
    # three marks in three colours; strip edges at 0, 53, 107, 160
    img = Image.new("RGB", (600, 838), (128, 128, 128))
    marks = [((100, 300), (220, 0, 0)), ((300, 300), (0, 220, 0)), ((500, 300), (0, 0, 220))]
    for (x, y), colour in marks:
        img.paste(colour, (x - 15, y - 30, x + 15, y + 30))
    out = io.BytesIO()
    img.save(out, "PNG")
    faces = tuple(portraits.Face(x / 600, y / 600, 0.15) for (x, y), _c in marks)
    portrait = Image.open(io.BytesIO(portraits.crop(out.getvalue(), faces))).convert("RGB")
    for i, (_xy, colour) in enumerate(marks):
        centre = portrait.getpixel((round((i + 0.5) * portraits.SIZE / 3), portraits.SIZE // 2))
        assert max(abs(p - q) for p, q in zip(centre, colour, strict=True)) < 40, (i, centre)


@pytest.mark.property
@given(
    st.lists(
        st.builds(
            portraits.Face,
            st.floats(-0.2, 1.2),
            st.floats(-0.2, 1.6),
            st.floats(0.05, 2.0),
        ),
        min_size=1,
        max_size=4,
    )
)
def test_any_faces_give_a_square_portrait(faces):
    portrait = Image.open(io.BytesIO(portraits.crop(CARD, tuple(faces))))
    assert portrait.size == (portraits.SIZE, portraits.SIZE)


@pytest.mark.property
@given(
    st.builds(portraits.Face, st.floats(-1, 2), st.floats(-1, 3), st.floats(0.01, 3)),
    st.integers(1, 5),
    st.sampled_from([(600, 838), (300, 419), (838, 600)]),
)
def test_strip_box_stays_inside_the_card(face, strips, card):
    x0, y0, x1, y1 = portraits._strip_box(card, face, strips)
    w, h = card
    assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
    assert abs((x1 - x0) - (y1 - y0) / strips) <= 1  # each strip is 1/n as wide as it is tall


def test_single_face_tuple_matches_a_bare_face():
    face = portraits.Face(0.4, 0.3, 0.4)
    assert portraits.crop(CARD, face) == portraits.crop(CARD, (face,))


# ---- watermark lift, more cases -----------------------------------------------
def watermarked(art: Image.Image, box_px: tuple[int, int, int, int]) -> Image.Image:
    a = portraits.WATERMARK_ALPHA
    marked = art.copy()
    marked.paste(marked.crop(box_px).point(lambda v: round(255 * a + (1 - a) * v)), box_px)
    return marked


def as_overlay(box_px, width=600) -> portraits.Overlay:
    return portraits.Overlay((tuple(v / width for v in box_px),))


def test_lift_overlay_leaves_pixels_away_from_the_box_untouched():
    art = Image.new("RGB", (600, 838), (40, 120, 200))
    art.paste((250, 250, 250), (0, 0, 100, 100))
    box = (300, 300, 400, 400)
    lifted = portraits.lift_overlay(watermarked(art, box), as_overlay(box))
    for xy in [(10, 10), (50, 50), (290, 350), (410, 350), (350, 290), (350, 410), (599, 837)]:
        assert lifted.getpixel(xy) == art.getpixel(xy), xy  # outside the box and its seam band: exact


def test_lift_overlay_box_on_the_card_edge():
    art = Image.new("RGB", (600, 838), (90, 30, 160))
    box = (550, 780, 600, 838)
    lifted = portraits.lift_overlay(watermarked(art, box), as_overlay(box))
    assert max(abs(p - q) for p, q in zip(lifted.getpixel((590, 830)), (90, 30, 160), strict=True)) <= 3


@pytest.mark.parametrize("colour", [(0, 0, 0), (255, 255, 255), (12, 200, 90), (250, 5, 128)])
def test_lift_overlay_recovers_extreme_colours(colour):
    art = Image.new("RGB", (600, 838), colour)
    box = (200, 200, 300, 300)
    lifted = portraits.lift_overlay(watermarked(art, box), as_overlay(box))
    assert max(abs(p - q) for p, q in zip(lifted.getpixel((250, 250)), colour, strict=True)) <= 3


def test_lift_overlay_clamps_pixels_darker_than_the_overlay_allows():
    # a pixel below 255a can't come from the overlay model; it clamps to black instead of wrapping
    img = Image.new("RGB", (600, 838), (10, 10, 10))
    box = (100, 100, 200, 200)
    assert portraits.lift_overlay(img, as_overlay(box)).getpixel((150, 150)) == (0, 0, 0)


def test_lift_overlay_keeps_size_and_mode():
    img = Image.new("RGB", (300, 419), (100, 100, 100))
    lifted = portraits.lift_overlay(img, portraits.Overlay(((0.1, 0.1, 0.5, 0.5), (0.6, 0.6, 0.9, 1.2))))
    assert (lifted.size, lifted.mode) == ((300, 419), "RGB")


def test_overlay_defaults_to_the_measured_watermark_opacity():
    assert portraits.Overlay(((0, 0, 1, 1),)).alpha == portraits.WATERMARK_ALPHA
    assert 0.6 < portraits.WATERMARK_ALPHA < 0.8


@respx.mock
def test_download_lifts_the_overlay():
    a = portraits.WATERMARK_ALPHA
    washed = Image.new("RGB", (600, 838), tuple(round(255 * a + (1 - a) * v) for v in (40, 120, 200)))
    out = io.BytesIO()
    washed.save(out, "PNG")
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=out.getvalue()))
    with httpx.Client() as client:
        raw = portraits.download("OP99-001", client, overlay=portraits.Overlay(((0, 0, 1, 838 / 600),)))
    pixel = Image.open(io.BytesIO(raw)).convert("RGB").getpixel((80, 80))
    assert max(abs(p - q) for p, q in zip(pixel, (40, 120, 200), strict=True)) <= 6


@respx.mock
def test_download_http_error_raises():
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(500))
    with httpx.Client() as client, pytest.raises(portraits.PortraitError, match="OP99-001"):
        portraits.download("OP99-001", client)


# ---- build_leaders config loading --------------------------------------------
def test_load_overlays_reads_boxes(tmp_path):
    path = tmp_path / "overlays.json"
    path.write_text('{"X": [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]}', encoding="utf-8")
    assert build_leaders().load_overlays(path) == {"X": portraits.Overlay(((0.1, 0.2, 0.3, 0.4), (0.5, 0.6, 0.7, 0.8)))}


def test_every_overlay_card_has_placed_faces():
    module = build_leaders()
    assert set(module.load_overlays()) <= set(module.load_faces())


def test_build_leaders_passes_faces_and_overlays(tmp_path, monkeypatch):
    from catalog.optcgapi import LeaderRecord

    module = build_leaders()
    records = [
        LeaderRecord("ST22-001", "Ace & Newgate", "ST22", None, ("Blue",)),
        LeaderRecord("OP99-001", "Someone New", "OP99", None, ("Red",)),
        LeaderRecord("EXT-001", "From davyback", "EXT", None, ("Red",)),
    ]
    calls = {}
    monkeypatch.setattr(module, "fetch_leaders", lambda: records)
    monkeypatch.setattr(module, "fetch_sources", lambda: ("OP-99",))
    monkeypatch.setattr(module, "OUT", tmp_path / "leaders.json")
    monkeypatch.setattr(module, "BUNDLED_DIR", tmp_path / "portraits")
    external = tmp_path / "external.json"
    external.write_text('["EXT-001"]', encoding="utf-8")
    monkeypatch.setattr(module, "EXTERNAL", external)
    monkeypatch.setattr(
        module, "download", lambda code, _client, face, overlay: calls.setdefault(code, (face, overlay)) and b"webp"
    )
    monkeypatch.setattr("sys.argv", ["build_leaders.py"])
    monkeypatch.setattr(module, "setup_logging", lambda: None)  # keep the test run's log handlers as they are
    assert module.main() == 0
    faces, overlays = module.load_faces(), module.load_overlays()
    assert calls["ST22-001"] == (faces["ST22-001"], overlays["ST22-001"])  # split faces + watermark lift
    assert calls["OP99-001"] == (portraits.DEFAULT_FACE, None)  # unplaced: default crop, no overlay
    assert "EXT-001" not in calls  # davyback portraits are never re-cropped
    assert (tmp_path / "portraits" / "ST22-001.webp").read_bytes() == b"webp"


@pytest.mark.regression
@respx.mock
def test_download_missing_counts_an_unwritable_cache_as_a_failure(monkeypatch, caplog):
    """A full or read-only cache folder raised OSError out of the sync, after the leaders were stored."""
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=card_jpeg()))
    respx.get(IMAGE_URL.format(code="OP99-002")).mock(return_value=httpx.Response(200, content=card_jpeg()))

    def full(self, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(portraits.Path, "write_bytes", full)
    assert portraits.download_missing(["OP99-001", "OP99-002"]) == (0, 2)
    assert "portrait for OP99-001 not saved" in caplog.text


@pytest.mark.live
def test_live_card_image_downloads_and_crops():
    """IMAGE_URL still serves card art the portrait crop can read (new leaders get their pictures this way)."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        webp = portraits.download("OP01-001", client)
    img = Image.open(io.BytesIO(webp))
    assert (img.format, img.size) == ("WEBP", (portraits.SIZE, portraits.SIZE))


@respx.mock
def test_download_missing_leaves_a_callers_client_open():
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=card_jpeg()))
    with httpx.Client() as client:
        assert portraits.download_missing(["OP99-001"], client) == (1, 0)
        assert not client.is_closed  # the caller made it, the caller closes it


@pytest.mark.regression
@pytest.mark.parametrize("code", ["../../evil", "..\\OP01-001", "OP01-001\n", "", "OP01-001/x"])
def test_codes_that_are_no_card_codes_name_no_file(code):
    """A leader code restored from a backup named the portrait file as-is, so "../../evil" pointed outside the
    portrait folders."""
    with pytest.raises(ValueError, match="not a card code"):
        portraits.filename(code)
    assert portraits.local_file(code) is None


@respx.mock
def test_download_missing_never_writes_for_a_code_that_is_no_card_code(caplog):
    route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, content=card_jpeg()))
    assert portraits.download_missing(["../evil"]) == (0, 1)
    assert not route.called
    assert "portrait for ../evil not saved" in caplog.text


@pytest.mark.regression
@respx.mock
def test_a_download_cut_off_mid_write_leaves_no_portrait(monkeypatch):
    """The portrait was written straight to its file: an app killed mid-write left half a picture, which then counted
    as downloaded and was never fetched again."""
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=card_jpeg()))
    real_write = Path.write_bytes

    def killed(self, data):
        real_write(self, data[: len(data) // 2])
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(portraits.Path, "write_bytes", killed)
    assert portraits.download_missing(["OP99-001"]) == (0, 1)
    assert portraits.local_file("OP99-001") is None


@respx.mock
def test_a_finished_download_leaves_no_partial_file_behind():
    respx.get(IMAGE_URL.format(code="OP99-001")).mock(return_value=httpx.Response(200, content=card_jpeg()))
    assert portraits.download_missing(["OP99-001"]) == (1, 0)
    assert [p.name for p in portraits.cache_dir().iterdir()] == ["OP99-001.webp"]
