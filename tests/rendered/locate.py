#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 23:54:26.643279
Revised: 2026/10/13 00:30:08.136661

Where things are in a capture of the real app, found by the theme colours they're drawn in (all in dp).
Shared by the rendered test modules; pixels.py has the colour-blob primitives these build on.
"""

from PIL import ImageChops, ImageFilter

from pixels import Blob, blobs, find, mask

# Flutter's dropdown menus open right under their field: 8 dp of padding, then 48 dp per option
MENU_PAD, MENU_ROW = 8, 48
APP_BAR_H = 56


def rings(physical, color: str, scale: float, *, min_w: int, min_h: int, max_h: int) -> list[Blob]:
    """Outlines drawn in `color` (fields, outlined buttons), top to bottom, in dp. Found in a capture at full
    resolution (`physical`, `scale` pixels per dp): shrunk to dp, their 1 px lines lose whole sides and the rings
    fall apart. A 3 px dilation closes the anti-aliased gaps; a mostly hollow box is a ring, not a filled button."""
    m = mask(physical, color, tol=20).filter(ImageFilter.MaxFilter(3))
    found = [
        b
        for b in blobs(m, 60)
        if b.w >= min_w * scale and min_h * scale <= b.h <= max_h * scale and b.area < 0.5 * b.w * b.h
    ]
    in_dp = [Blob(*(round(v / scale) for v in b.box), b.area) for b in found]
    return sorted(in_dp, key=lambda b: (b.y0, b.x0))


def fields(physical, s, scale: float) -> list[Blob]:
    """Outlined input fields (text fields, dropdowns), top to bottom, in dp; tol 20 keeps paler card borders out."""
    return rings(physical, s.outline, scale, min_w=80, min_h=36, max_h=140)


def menu_rows(before, after, field: Blob, options: int) -> list[tuple[float, float]]:
    """Where each option of the dropdown `field` opened is, from captures before and after opening it. A short menu
    drops under its field, a long one opens over it: its top is the highest pixel that changed in a strip just inside
    the field's left edge (the field's own border rows, restyled when focused, don't count)."""
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    strip = diff.crop((field.x0 + 4, 0, field.x0 + 24, diff.height)).point(lambda v: 255 if v > 24 else 0)
    border = {y for edge in (field.y0, field.y1) for y in range(edge - 3, edge + 4)}
    changed = [y for y in range(strip.height) if y not in border and strip.crop((0, y, strip.width, y + 1)).getbbox()]
    assert changed, "the dropdown did not open"
    top = min(changed)
    return [(field.cx, top + MENU_PAD + MENU_ROW * i + MENU_ROW / 2) for i in range(options)]


def filled(img, color: str, *, min_w: int = 60, min_h: int = 28, max_h: int = 64) -> list[Blob]:
    """Filled buttons, bars and badges of `color`, top to bottom."""
    found = [b for b in find(img, color, tol=6, min_area=600) if b.w >= min_w and min_h <= b.h <= max_h]
    return sorted(found, key=lambda b: b.y0)


def snackbar(img, s, *, error: bool) -> Blob | None:
    """The floating snackbar (error: filled in the error colour; info: in the text colour), if one shows."""
    color = s.error if error else s.fg
    bars = [b for b in filled(img, color, min_w=img.width // 2, min_h=36, max_h=120) if b.y0 > img.height // 2]
    return bars[-1] if bars else None


def nav_tab(img, index: int) -> tuple[float, float]:
    """The bottom navigation bar's destination `index` (0 events, 1 stats, 2 settings)."""
    return img.width * (2 * index + 1) / 6, img.height - 40


def back_arrow() -> tuple[float, float]:
    return 28, APP_BAR_H / 2


def overflow_menu(img) -> tuple[float, float]:
    """The ⋮ button at the app bar's right end."""
    return img.width - 20, APP_BAR_H / 2


def first_popup_item(img) -> tuple[float, float]:
    """The first item of the menu ⋮ opens (it drops from the bar's right end)."""
    return img.width - 100, 40


def confirm_button(img, s) -> Blob:
    """The destructive button of an open confirm dialog: the dialog's one error-filled button."""
    buttons = filled(img, s.error, min_w=60, max_h=56)
    assert buttons, "no confirm dialog with a destructive button on screen"
    return buttons[-1]
