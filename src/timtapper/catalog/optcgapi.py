#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.147840
Revised: 2026/10/11 16:27:21.549308

Leader data from optcgapi.com — a public, read-only card API. Used both by
scripts/build_leaders.py (to refresh the leaders.json bundled with the app)
and by the in-app "Update leaders" action, so the two never parse differently.
"""

import re
from dataclasses import dataclass

import httpx

from core.logging import get_logger

_log = get_logger("catalog.optcgapi")

BASE_URL = "https://optcgapi.com/api"
ENDPOINTS = ("allSetCards", "allSTCards")
IMAGE_URL = "https://optcgapi.com/media/static/Card_Images/{code}.jpg"
_COLORS = {"Red", "Green", "Blue", "Purple", "Black", "Yellow"}
# "Monkey.D.Luffy (003)", "Sanji (PRB01-001)", "Trafalgar Law - OP14-001",
# "... (Parallel)", "... (Alternate Art)" -> the bare character name
_NAME_SUFFIX = re.compile(r"(\s*\([^)]*\)|\s+-\s+[A-Z]+\d+-\d+)+$")
_CODE = re.compile(r"^([A-Z]+\d*)-\d+$")


class CatalogError(Exception):
    """The leader source could not be reached or returned unusable data."""


@dataclass(frozen=True, slots=True)
class LeaderRecord:
    code: str
    name: str
    set_code: str
    set_name: str | None
    colors: tuple[str, ...]

    def to_json(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "set_code": self.set_code,
            "set_name": self.set_name,
            "colors": list(self.colors),
        }

    @classmethod
    def from_json(cls, raw: dict) -> LeaderRecord:
        return cls(raw["code"], raw["name"], raw["set_code"], raw.get("set_name"), tuple(raw["colors"]))


def clean_name(raw: str) -> str:
    return _NAME_SUFFIX.sub("", raw).strip()


def set_code_of(card_code: str) -> str:
    match = _CODE.match(card_code)
    if not match:
        raise ValueError(f"not a card code: {card_code!r}")
    return match.group(1)


def parse_leaders(cards: list[dict]) -> list[LeaderRecord]:
    """Unique leaders (alt arts/parallels collapsed onto the base print), sorted by code."""
    leaders: dict[str, LeaderRecord] = {}
    for card in cards:
        if card.get("card_type") != "Leader":
            continue
        code = card.get("card_set_id") or ""
        try:
            set_code = set_code_of(code)
        except ValueError:
            _log.warning("skipping leader with malformed code %r", code)
            continue
        is_base_print = card.get("card_image_id") == code
        if code in leaders and not is_base_print:
            continue
        colors = tuple(c for c in (card.get("card_color") or "").split() if c in _COLORS)
        if not colors:
            _log.warning("skipping leader %s with no recognised color", code)
            continue
        leaders[code] = LeaderRecord(
            code, clean_name(card.get("card_name") or code), set_code, card.get("set_name"), colors
        )
    return sorted(leaders.values(), key=lambda r: r.code)


def fetch_leaders(client: httpx.Client | None = None) -> list[LeaderRecord]:
    """Download every set + starter deck and extract the leaders. Raises CatalogError."""
    owns_client = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    cards: list[dict] = []
    try:
        for endpoint in ENDPOINTS:
            url = f"{BASE_URL}/{endpoint}/"
            _log.info("fetching %s", url)
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise CatalogError(f"{endpoint}: expected a list, got {type(payload).__name__}")
            cards.extend(payload)
    except httpx.HTTPError as exc:
        _log.warning("leader download failed: %s", exc)
        raise CatalogError(str(exc)) from exc
    except ValueError as exc:  # invalid JSON
        _log.warning("leader download returned invalid JSON: %s", exc)
        raise CatalogError(str(exc)) from exc
    finally:
        if owns_client:
            client.close()
    leaders = parse_leaders(cards)
    if not leaders:
        raise CatalogError("no leaders found in the downloaded card lists")
    _log.info("downloaded %d leaders", len(leaders))
    return leaders
