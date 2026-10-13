#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 08:59:20.535763
Revised: 2026/10/13 08:59:31.366389
"""

import datetime as dt

import httpx
import pytest
import respx
from hypothesis import given
from hypothesis import strategies as st

from catalog.limitless import SETS_URL, fetch_release_dates, parse_date, parse_release_dates
from catalog.optcgapi import CatalogError
from catalog.repository import is_main_set, load_bundled, load_bundled_releases


def row(code, name, day, link="/cards/x"):
    return (
        f'<tr>\n  <td><a href="{link}">{code}</a></td>\n  <td><a href="{link}">{name}</a></td>\n'
        f'  <td><a href="{link}">{day}</a></td>\n  <td class="md-only"><a href="{link}">155 '
        f'<span class="playability">70.32%</span></a></td>\n</tr>\n'
    )


# the page as Limitless TCG lays it out: a heading row, a sub-heading per product line, a row per set
PAGE = (
    "<html><body><table>"
    "<tr><th>Code</th><th>Name</th><th>Release Date</th><th class='md-only'>Cards</th></tr>"
    "<tr><th class='sub-heading' colspan=6>Booster Packs</th></tr>"
    + row("OP16", "The Time of Battle", "12 Jun 26")
    + row("EB03", "One Piece Heroines Edition", "20 Feb 26")
    + row("OP01", "Romance Dawn", "02 Dec 22")
    + "<tr><th class='sub-heading' colspan=6>Starter Decks</th></tr>"
    + row("ST36", "YELLOW Eustass&quot;Captain&quot;Kid", "31 Jul 26")
    + "</table><p>Promotional products are now listed on their own page.</p></body></html>"
)


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("12 Jun 26", dt.date(2026, 6, 12)),
        ("02 Dec 22", dt.date(2022, 12, 2)),
        ("2 Dec 22", dt.date(2022, 12, 2)),
        ("31 Feb 26", None),  # no such day
        ("12 Jux 26", None),
        ("12 jun 26", None),
        ("2026-06-12", None),
        ("", None),
    ],
)
def test_parse_date(text, day):
    assert parse_date(text) == day


def test_parse_release_dates_reads_every_set_row_and_skips_headings():
    assert parse_release_dates(PAGE) == {
        "OP16": dt.date(2026, 6, 12),
        "EB03": dt.date(2026, 2, 20),
        "OP01": dt.date(2022, 12, 2),
        "ST36": dt.date(2026, 7, 31),
    }


def test_parse_release_dates_skips_unreadable_dates(caplog):
    page = "<table>" + row("OP99", "Future", "TBA") + row("OP01", "Romance Dawn", "02 Dec 22") + "</table>"
    assert parse_release_dates(page) == {"OP01": dt.date(2022, 12, 2)}
    assert "OP99" in caplog.text and "'TBA'" in caplog.text


@pytest.mark.parametrize("page", ["", "<p>maintenance</p>", "<table><tr><td>OP01</td><td>short</td></tr></table>"])
def test_parse_release_dates_of_a_page_without_sets(page):
    assert parse_release_dates(page) == {}


@pytest.mark.property
@given(st.text())
def test_property_parse_release_dates_never_crashes_on_garbage(html):
    assert isinstance(parse_release_dates(html), dict)


@respx.mock
def test_fetch_release_dates():
    respx.get(SETS_URL).respond(text=PAGE)
    assert fetch_release_dates()["OP16"] == dt.date(2026, 6, 12)


@respx.mock
@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ({"status_code": 503}, "503"),
        ({"text": "<p>maintenance</p>"}, "no release dates"),
    ],
)
def test_fetch_release_dates_errors(failure, message):
    respx.get(SETS_URL).respond(**failure)
    with pytest.raises(CatalogError, match=message):
        fetch_release_dates()


@respx.mock
def test_fetch_release_dates_network_error():
    respx.get(SETS_URL).mock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(CatalogError, match="offline"):
        fetch_release_dates()


def test_fetch_release_dates_uses_given_client():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=PAGE))
    with httpx.Client(transport=transport) as client:
        assert len(fetch_release_dates(client)) == 4
        assert not client.is_closed


def test_every_bundled_main_set_has_a_release_date():
    """A main set without a date can never be the one a new event is put in."""
    releases = load_bundled_releases()
    main = {r.set_code for r in load_bundled() if is_main_set(r.set_code)}
    assert main <= set(releases)
    assert releases["OP01"] == dt.date(2022, 12, 2)


@pytest.mark.live
def test_live_limitless_still_dates_every_bundled_main_set():
    releases = fetch_release_dates()
    bundled = load_bundled_releases()
    for code, day in bundled.items():
        if is_main_set(code):
            assert releases.get(code) == day, code
