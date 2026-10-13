#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 08:59:20.385126
Revised: 2026/10/13 08:59:31.194181

English release dates of every set, from Limitless TCG's set list (optcgapi.com has none). The page is HTML: a
table row per set whose first three cells are its code, name and release date ("OP16 | The Time of Battle |
12 Jun 26"); every other row (headings, promos) is skipped.
"""

import datetime as dt
import re
from html.parser import HTMLParser

import httpx

from catalog.optcgapi import LIST_TIMEOUT, CatalogError, client_session
from core.logging import get_logger

_log = get_logger("catalog.limitless")

SETS_URL = "https://onepiece.limitlesstcg.com/cards"
_CODE = re.compile(r"^[A-Z]+\d+$")
_DATE = re.compile(r"^(\d{1,2}) ([A-Z][a-z]{2}) (\d{2})$")
# spelled out, not strptime's %b: that one follows the process locale, and Spanish or Galician would read "Aug" as no
# month at all
_MONTHS = {
    month: number
    for number, month in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1
    )
}


class _Rows(HTMLParser):
    """The text of each table row's cells."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self.rows.append([])
        elif tag in {"td", "th"} and self.rows:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None:
            self.rows[-1].append(" ".join("".join(self._cell).split()))
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_date(text: str) -> dt.date | None:
    """The day a cell like "12 Jun 26" names (2026-06-12); None for anything else."""
    match = _DATE.match(text)
    if not match or match[2] not in _MONTHS:
        return None
    try:
        return dt.date(2000 + int(match[3]), _MONTHS[match[2]], int(match[1]))
    except ValueError:  # 31 Feb
        return None


def parse_release_dates(html: str) -> dict[str, dt.date]:
    """Set code -> release date, for every row that has both."""
    parser = _Rows()
    parser.feed(html)
    releases = {}
    for cells in parser.rows:
        if len(cells) < 3 or not _CODE.match(cells[0]):
            continue
        day = parse_date(cells[2])
        if day is None:
            _log.warning("skipping set %s with unreadable release date %r", cells[0], cells[2])
            continue
        releases[cells[0]] = day
    return releases


def fetch_release_dates(client: httpx.Client | None = None) -> dict[str, dt.date]:
    """Download the set list and read every set's release date. Raises CatalogError."""
    _log.info("fetching %s", SETS_URL)
    try:
        with client_session(client, LIST_TIMEOUT) as c:
            response = c.get(SETS_URL)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        _log.warning("set release dates download failed: %s", exc)
        raise CatalogError(str(exc)) from exc
    releases = parse_release_dates(response.text)
    if not releases:
        raise CatalogError("no release dates found in the set list")
    _log.info("read %d set release dates", len(releases))
    return releases
