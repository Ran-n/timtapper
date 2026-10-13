#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:43:10.828223
Revised: 2026/10/13 07:39:28.021719

davyback.gg icon scraping: srcset parsing (widest variant per card) and icon -> portrait conversion.
"""

import importlib.util
import io
import json
from pathlib import Path

import pytest
import respx
from PIL import Image, UnidentifiedImageError

from catalog.portraits import SIZE

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "fetch_davyback_portraits.py"
_spec = importlib.util.spec_from_file_location("fetch_davyback_portraits", _PATH)
davy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(davy)

A = "/_app/immutable/assets/"


def test_largest_icons_picks_widest_variant_per_code():
    page = (
        f'<img srcset="{A}Buggy_OP16_041_blue.a1.webp 800w, {A}Buggy_OP16_041_blue.a2.webp 400w">'
        f'<img srcset="{A}Buggy_OP16_041_blue.b1.png 200w, {A}Buggy_OP16_041_blue.b2.png 100w">'
        f'<img srcset="{A}Boa%20Hancock_OP14_041_blue_yellow.c1.png 400w">'
        f'<img srcset="{A}Sanji_PRB01_001_red.d1.webp 100w">'
    )
    assert davy.largest_icons(page) == {
        "OP16-041": f"{A}Buggy_OP16_041_blue.a1.webp",
        "OP14-041": f"{A}Boa%20Hancock_OP14_041_blue_yellow.c1.png",
        "PRB01-001": f"{A}Sanji_PRB01_001_red.d1.webp",
    }


@pytest.mark.parametrize("page", ["", "<img src='/cards/luffy-base.webp'>", 'srcset="/x.png 1x"'])
def test_largest_icons_ignores_unrelated_markup(page):
    assert davy.largest_icons(page) == {}


def png(size, mode="RGB", color=(200, 0, 0)) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, "PNG")
    return out.getvalue()


@pytest.mark.parametrize("size", [(800, 800), (120, 120), (300, 200), (200, 300)])
def test_to_portrait_is_a_square_webp(size):
    img = Image.open(io.BytesIO(davy.to_portrait(png(size))))
    assert img.format == "WEBP" and img.size == (SIZE, SIZE)


def test_to_portrait_flattens_transparency_onto_black():
    img = Image.open(io.BytesIO(davy.to_portrait(png((100, 100), "RGBA", (255, 0, 0, 0))))).convert("RGB")
    assert max(img.getpixel((SIZE // 2, SIZE // 2))) < 20


def test_to_portrait_rejects_non_images():
    with pytest.raises(UnidentifiedImageError):
        davy.to_portrait(b"<html>")


@pytest.mark.regression
@respx.mock
def test_a_failed_download_keeps_an_earlier_icon_listed(tmp_path, monkeypatch):
    """The list used to be rewritten from one run's successes: an icon that failed to download once dropped off it,
    and the next `build_leaders.py --force` re-cropped the card over davyback.gg's icon."""
    listing = tmp_path / "davyback_portraits.json"
    listing.write_text('["OP01-001"]', encoding="utf-8")
    monkeypatch.setattr(davy, "LIST", listing)
    monkeypatch.setattr(davy, "BUNDLED_DIR", tmp_path)
    page = f'<img srcset="{A}Zoro_OP01_001_red.z.png 400w"><img srcset="{A}Luffy_OP01_003_red.l.png 400w">'
    respx.get(f"{davy.SITE}/").respond(text=page)
    respx.get(f"{davy.SITE}{A}Zoro_OP01_001_red.z.png").respond(status_code=503)
    respx.get(f"{davy.SITE}{A}Luffy_OP01_003_red.l.png").respond(content=png((120, 120)))
    assert davy.main() == 1  # the failure is still reported
    assert json.loads(listing.read_text(encoding="utf-8")) == ["OP01-001", "OP01-003"]


def test_davyback_list_matches_bundled_portraits():
    import json

    from catalog.portraits import BUNDLED_DIR

    codes = json.loads((_PATH.parent / "davyback_portraits.json").read_text(encoding="utf-8"))
    assert codes == sorted(set(codes))
    assert all((BUNDLED_DIR / f"{c}.webp").is_file() for c in codes)


@pytest.mark.live
def test_live_davyback_still_serves_icons_for_our_leaders():
    """The scraper's srcset pattern still matches davyback.gg, and an icon it finds converts to a portrait."""
    import httpx

    from catalog.repository import load_bundled

    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "timtapper-build"}) as client:
        icons = davy.largest_icons(client.get(f"{davy.SITE}/").raise_for_status().text)
        ours = sorted(set(icons) & {r.code for r in load_bundled()})
        assert ours, "no icon on davyback.gg matches a bundled leader: the page or its srcset format changed"
        raw = client.get(davy.SITE + icons[ours[0]]).raise_for_status().content
    assert Image.open(io.BytesIO(davy.to_portrait(raw))).size == (SIZE, SIZE)
