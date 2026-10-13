#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.147840
Revised: 2026/10/13 11:44:57.736906

Leader data from optcgapi.com — a public, read-only card API. Used both by
scripts/build_leaders.py (to refresh the leaders.json bundled with the app)
and by the in-app leader update (manual or automatic), so the two never parse
differently.
"""

import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx

from core.logging import get_logger

_log = get_logger("catalog.optcgapi")

BASE_URL = "https://optcgapi.com/api"
ENDPOINTS = ("allSetCards", "allSTCards")
# Small lists of every released booster / starter deck (a few KB, vs MBs for the
# card lists): a new id here means a new set is out and the leaders need a refresh.
SOURCE_ENDPOINTS = {"allSets": "set_id", "allDecks": "structure_deck_id"}
IMAGE_URL = "https://optcgapi.com/media/static/Card_Images/{code}.jpg"
# seconds: the card lists run to MBs on a phone connection; one card image is a few hundred KB
LIST_TIMEOUT, IMAGE_TIMEOUT = 60, 30
_COLORS = {"Red", "Green", "Blue", "Purple", "Black", "Yellow"}
# "Monkey.D.Luffy (003)", "Sanji (PRB01-001)", "Trafalgar Law - OP14-001",
# "... (Parallel)", "... (Alternate Art)" -> the bare character name
_NAME_SUFFIX = re.compile(r"(\s*\([^)]*\)|\s+-\s+[A-Z]+\d*-\d+)+$")
_CODE = re.compile(r"([A-Z]+\d*)-\d+")  # a card code, e.g. OP01-001: its set code, a dash, its number
_SET_CODE = re.compile(r"[A-Z]+\d*")


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
    return _NAME_SUFFIX.sub("", raw.strip()).strip()


def is_card_code(value: object) -> bool:
    """`value` is shaped like a card code ("OP01-001"): safe to put in a file name or a URL."""
    return isinstance(value, str) and _CODE.fullmatch(value) is not None


def is_set_code(value: object) -> bool:
    """`value` is shaped like a set code ("OP16", "PRB01")."""
    return isinstance(value, str) and _SET_CODE.fullmatch(value) is not None


def set_code_of(card_code: str) -> str:
    match = _CODE.fullmatch(card_code)
    if not match:
        raise ValueError(f"not a card code: {card_code!r}")
    return match.group(1)


def _text(card: dict, key: str) -> str:
    """A card's text field; anything else the API sends there (null, a number) reads as empty."""
    value = card.get(key)
    return value if isinstance(value, str) else ""


def parse_leaders(cards: list[dict]) -> list[LeaderRecord]:
    """Unique leaders (alt arts/parallels collapsed onto the base print), sorted by code."""
    leaders: dict[str, LeaderRecord] = {}
    for card in cards:
        if not isinstance(card, dict):
            _log.warning("skipping a card entry that is not an object: %r", card)
            continue
        if card.get("card_type") != "Leader":
            continue
        code = _text(card, "card_set_id")
        try:
            set_code = set_code_of(code)
        except ValueError:
            _log.warning("skipping leader with malformed code %r", code)
            continue
        is_base_print = card.get("card_image_id") == code
        if code in leaders and not is_base_print:
            continue
        colors = tuple(c for c in _text(card, "card_color").split() if c in _COLORS)
        if not colors:
            _log.warning("skipping leader %s with no recognised color", code)
            continue
        leaders[code] = LeaderRecord(
            code, clean_name(_text(card, "card_name") or code), set_code, _text(card, "set_name") or None, colors
        )
    return sorted(leaders.values(), key=lambda r: r.code)


@contextmanager
def client_session(client: httpx.Client | None = None, timeout: float = LIST_TIMEOUT) -> Generator[httpx.Client]:
    """The caller's client, or a fresh one (`timeout` seconds per request) closed on exit."""
    if client is not None:
        yield client
        return
    with httpx.Client(timeout=timeout, follow_redirects=True) as own:
        yield own


def _get_list(client: httpx.Client, endpoint: str) -> list:
    """GET a JSON list from the API. Raises CatalogError."""
    url = f"{BASE_URL}/{endpoint}/"
    _log.info("fetching %s", url)
    try:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        _log.warning("%s download failed: %s", endpoint, exc)
        raise CatalogError(str(exc)) from exc
    except ValueError as exc:  # invalid JSON
        _log.warning("%s returned invalid JSON: %s", endpoint, exc)
        raise CatalogError(str(exc)) from exc
    if not isinstance(payload, list):
        raise CatalogError(f"{endpoint}: expected a list, got {type(payload).__name__}")
    return payload


def fetch_leaders(client: httpx.Client | None = None) -> list[LeaderRecord]:
    """Download every set + starter deck and extract the leaders. Raises CatalogError."""
    with client_session(client) as c:
        cards = [card for endpoint in ENDPOINTS for card in _get_list(c, endpoint)]
    leaders = parse_leaders(cards)
    if not leaders:
        raise CatalogError("no leaders found in the downloaded card lists")
    _log.info("downloaded %d leaders", len(leaders))
    return leaders


def fetch_sources(client: httpx.Client | None = None) -> tuple[str, ...]:
    """Ids of every released set and starter deck, sorted (e.g. "OP-01", "ST-21"). Raises CatalogError."""
    with client_session(client) as c:
        ids = {
            str(item[key])
            for endpoint, key in SOURCE_ENDPOINTS.items()
            for item in _get_list(c, endpoint)
            if isinstance(item, dict) and item.get(key)
        }
    if not ids:
        raise CatalogError("no sets found in the set lists")
    return tuple(sorted(ids))
