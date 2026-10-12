#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:02.744293
Revised: 2026/10/12 13:16:02.744293

Find things in a capture of the real app by colour: masks, connected blobs and their holes.
Pure Pillow, so the rendered tests need nothing the app doesn't already ship with.
"""

from collections import deque
from dataclasses import dataclass

from PIL import Image, ImageChops


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@dataclass(frozen=True, slots=True)
class Blob:
    """A 4-connected run of matching pixels: its bounding box [x0, x1) x [y0, y1) and pixel count."""

    x0: int
    y0: int
    x1: int
    y1: int
    area: int

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


def mask(img: Image.Image, color: str, tol: int = 8) -> Image.Image:
    """255 where every channel is within `tol` of `color`, else 0."""
    diff = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, rgb(color)))
    r, g, b = diff.split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return worst.point(lambda v: 255 if v <= tol else 0)


def blobs(m: Image.Image, min_area: int = 1) -> list[Blob]:
    """Connected components of a mask's set pixels, top-to-bottom then left-to-right."""
    w, h = m.size
    px = m.load()
    seen = bytearray(w * h)
    found = []
    for y in range(h):
        for x in range(w):
            if not px[x, y] or seen[y * w + x]:
                continue
            seen[y * w + x] = 1
            queue = deque([(x, y)])
            x0 = x1 = x
            y0 = y1 = y
            area = 0
            while queue:
                cx, cy = queue.popleft()
                area += 1
                x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and not seen[ny * w + nx]:
                        seen[ny * w + nx] = 1
                        queue.append((nx, ny))
            if area >= min_area:
                found.append(Blob(x0, y0, x1 + 1, y1 + 1, area))
    return found


def find(img: Image.Image, color: str, *, tol: int = 8, min_area: int = 1) -> list[Blob]:
    return blobs(mask(img, color, tol), min_area)


def holes(img: Image.Image, blob: Blob, color: str, *, tol: int = 40, min_area: int = 3) -> list[Blob]:
    """Blobs of `color` strictly inside `blob`'s box (pips on a die, a check on a dot)."""
    inner = img.crop(blob.box)
    return [b for b in find(inner, color, tol=tol, min_area=min_area) if b.x0 > 0 and b.y0 > 0]


def count(img: Image.Image, color: str, box: tuple[int, int, int, int], tol: int = 40) -> int:
    """How many pixels in `box` are within `tol` of `color`."""
    return mask(img.crop(box), color, tol).histogram()[255]
