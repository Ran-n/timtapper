#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.098982
Revised: 2026/10/12 16:55:00.008377
"""

import httpx
import pytest
import respx
from hypothesis import given
from hypothesis import strategies as st

from catalog.optcgapi import (
    BASE_URL,
    CatalogError,
    LeaderRecord,
    clean_name,
    fetch_leaders,
    fetch_sources,
    parse_leaders,
    set_code_of,
)


def card(code, name, color="Red", image_id=None, card_type="Leader", set_name="Romance Dawn"):
    return {
        "card_set_id": code,
        "card_name": name,
        "card_color": color,
        "card_type": card_type,
        "card_image_id": image_id or code,
        "set_name": set_name,
    }


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Monkey.D.Luffy (003)", "Monkey.D.Luffy"),
        ("Sanji (PRB01-001)", "Sanji"),
        ("Sanji (PRB01-001) (Alternate Art)", "Sanji"),
        ("Trafalgar Law - OP14-001", "Trafalgar Law"),
        ("Trafalgar Law - OP14-001 (Alternate Art)", "Trafalgar Law"),
        ("Roronoa Zoro (001) (Parallel)", "Roronoa Zoro"),
        ("Ace & Newgate", "Ace & Newgate"),
    ],
)
def test_clean_name(raw, clean):
    assert clean_name(raw) == clean


@pytest.mark.regression
@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Sanji (Parallel) ", "Sanji"),  # a trailing space stopped the suffix strip ("Sanji (Parallel)")
        ("  Trafalgar Law - OP14-001	", "Trafalgar Law"),
        ("Monkey.D.Luffy - P-001", "Monkey.D.Luffy"),  # " - CODE" tails needed set digits; promo codes have none
    ],
)
def test_clean_name_regressions(raw, clean):
    """Both found by test_property_clean_name_strips_any_suffix_chain."""
    assert clean_name(raw) == clean


@pytest.mark.parametrize(("code", "set_code"), [("OP01-001", "OP01"), ("ST10-002", "ST10"), ("PRB01-001", "PRB01")])
def test_set_code_of(code, set_code):
    assert set_code_of(code) == set_code


@pytest.mark.parametrize("bad", ["", "OP01", "op01-001", "OP01_001"])
def test_set_code_of_rejects_malformed(bad):
    with pytest.raises(ValueError):
        set_code_of(bad)


def test_parse_leaders_collapses_alt_arts_and_skips_non_leaders():
    cards = [
        card("OP01-001", "Roronoa Zoro (001) (Parallel)", image_id="OP01-001_p1"),
        card("OP01-001", "Roronoa Zoro (001)"),
        card("OP01-002", "Trafalgar Law (002)", "Green Red"),
        card("OP01-016", "Nami", card_type="Character"),
    ]
    leaders = parse_leaders(cards)
    assert [r.code for r in leaders] == ["OP01-001", "OP01-002"]
    assert leaders[0] == LeaderRecord("OP01-001", "Roronoa Zoro", "OP01", "Romance Dawn", ("Red",))
    assert leaders[1].colors == ("Green", "Red")


def test_parse_leaders_skips_malformed_and_colorless(caplog):
    leaders = parse_leaders([card("BAD", "x"), card("OP01-003", "y", color="Rainbow")])
    assert leaders == []
    assert "malformed" in caplog.text
    assert "no recognised color" in caplog.text


def test_record_json_roundtrip():
    rec = LeaderRecord("OP01-001", "Zoro", "OP01", None, ("Red", "Green"))
    assert LeaderRecord.from_json(rec.to_json()) == rec


@respx.mock
def test_fetch_leaders_merges_both_endpoints():
    respx.get(f"{BASE_URL}/allSetCards/").respond(json=[card("OP01-001", "Zoro (001)")])
    respx.get(f"{BASE_URL}/allSTCards/").respond(json=[card("ST01-001", "Luffy (001)")])
    assert [r.code for r in fetch_leaders()] == ["OP01-001", "ST01-001"]


@respx.mock
def test_fetch_leaders_http_error():
    respx.get(f"{BASE_URL}/allSetCards/").respond(status_code=503)
    with pytest.raises(CatalogError):
        fetch_leaders()


@respx.mock
def test_fetch_leaders_network_error():
    respx.get(f"{BASE_URL}/allSetCards/").mock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(CatalogError, match="offline"):
        fetch_leaders()


@respx.mock
def test_fetch_leaders_invalid_json():
    respx.get(f"{BASE_URL}/allSetCards/").respond(text="<html>")
    with pytest.raises(CatalogError):
        fetch_leaders()


@respx.mock
def test_fetch_leaders_not_a_list():
    respx.get(f"{BASE_URL}/allSetCards/").respond(json={"error": "nope"})
    with pytest.raises(CatalogError, match="expected a list"):
        fetch_leaders()


@respx.mock
def test_fetch_leaders_empty():
    respx.get(f"{BASE_URL}/allSetCards/").respond(json=[])
    respx.get(f"{BASE_URL}/allSTCards/").respond(json=[])
    with pytest.raises(CatalogError, match="no leaders"):
        fetch_leaders()


def test_fetch_leaders_uses_given_client():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[card("OP02-001", "Newgate (001)")]))
    with httpx.Client(transport=transport) as client:
        assert [r.name for r in fetch_leaders(client)] == ["Newgate"]
        assert not client.is_closed


@respx.mock
def test_fetch_sources_merges_sets_and_decks_sorted_unique():
    respx.get(f"{BASE_URL}/allSets/").respond(
        json=[{"set_id": "OP-02"}, {"set_id": "OP-01"}, {"set_id": "OP-01"}, {"set_name": "no id"}, "junk"]
    )
    respx.get(f"{BASE_URL}/allDecks/").respond(json=[{"structure_deck_id": "ST-01"}])
    assert fetch_sources() == ("OP-01", "OP-02", "ST-01")


@respx.mock
def test_fetch_sources_empty():
    respx.get(f"{BASE_URL}/allSets/").respond(json=[])
    respx.get(f"{BASE_URL}/allDecks/").respond(json=[])
    with pytest.raises(CatalogError, match="no sets"):
        fetch_sources()


@respx.mock
@pytest.mark.parametrize("failure", [{"status_code": 500}, {"json": {"error": "nope"}}, {"text": "<html>"}])
def test_fetch_sources_errors(failure):
    respx.get(f"{BASE_URL}/allSets/").respond(**failure)
    with pytest.raises(CatalogError):
        fetch_sources()


def test_fetch_sources_uses_given_client():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[{"set_id": "OP-01"}]))
    with httpx.Client(transport=transport) as client:
        assert fetch_sources(client) == ("OP-01",)
        assert not client.is_closed


@pytest.mark.live
def test_live_optcgapi_lists_sets():
    sources = fetch_sources()
    assert "OP-01" in sources and "ST-01" in sources


@pytest.mark.live
def test_live_optcgapi_has_leaders():
    leaders = fetch_leaders()
    assert len(leaders) > 100
    assert any(r.code == "OP01-001" for r in leaders)


# ---- properties ------------------------------------------------------------------
# character names as the API spells them: no brackets, no " - CODE" tails
base_names = st.text(st.characters(categories=["L", "N", "Zs"], include_characters=".&'"), min_size=1).filter(
    lambda s: s.strip() and " - " not in s
)
set_prefixes = st.from_regex(r"[A-Z]{1,4}\d{0,3}", fullmatch=True)
card_codes = st.builds(lambda p, n: f"{p}-{n:03d}", set_prefixes, st.integers(0, 999))
suffixes = st.lists(
    st.one_of(
        st.just(" (Parallel)"),
        st.just(" (Alternate Art)"),
        st.integers(0, 999).map(lambda n: f" ({n:03d})"),
        card_codes.map(lambda c: f" ({c})"),
        card_codes.map(lambda c: f" - {c}"),
    ),
    max_size=3,
)


@pytest.mark.property
@given(base_names, suffixes, st.sampled_from(["", " ", "  "]))
def test_property_clean_name_strips_any_suffix_chain(name, tail, padding):
    assert clean_name(name + "".join(tail) + padding) == name.strip()


@pytest.mark.property
@given(st.text())
def test_property_clean_name_is_idempotent(raw):
    once = clean_name(raw)
    assert clean_name(once) == once


@pytest.mark.property
@given(set_prefixes, st.integers(0, 999))
def test_property_set_code_of_returns_the_prefix(prefix, number):
    assert set_code_of(f"{prefix}-{number:03d}") == prefix


@pytest.mark.property
@given(st.text().filter(lambda s: "-" not in s))
def test_property_set_code_of_rejects_anything_without_a_dash(bad):
    with pytest.raises(ValueError):
        set_code_of(bad)


raw_cards = st.lists(
    st.builds(
        card,
        card_codes,
        base_names,
        color=st.sampled_from(["Red", "Green Blue", "Purple", "Colorless", "", "Black Yellow"]),
        image_id=st.one_of(st.none(), st.just("alt")),
        card_type=st.sampled_from(["Leader", "Leader", "Character", "Event"]),
    ),
    max_size=30,
)


@pytest.mark.property
@given(raw_cards)
def test_property_parse_leaders_is_sorted_unique_and_well_formed(cards):
    out = parse_leaders(cards)
    codes = [r.code for r in out]
    assert codes == sorted(set(codes))
    leader_codes = {c["card_set_id"] for c in cards if c["card_type"] == "Leader"}
    for r in out:
        assert r.code in leader_codes
        assert r.colors and set(r.colors) <= {"Red", "Green", "Blue", "Purple", "Black", "Yellow"}
        assert r.set_code == set_code_of(r.code)
        assert LeaderRecord.from_json(r.to_json()) == r


@pytest.mark.property
@given(raw_cards)
def test_property_base_print_always_wins_over_alt_arts(cards):
    by_code = {r.code: r for r in parse_leaders(cards)}
    for c in cards:
        base = c["card_image_id"] == c["card_set_id"] and c["card_type"] == "Leader"
        if base and c["card_set_id"] in by_code and c["card_color"] not in ("", "Colorless"):
            # the last base print of a code is the one kept
            last = [x for x in cards if x["card_set_id"] == c["card_set_id"] and x["card_image_id"] == x["card_set_id"]]
            last = [x for x in last if x["card_type"] == "Leader" and x["card_color"] not in ("", "Colorless")][-1]
            assert by_code[c["card_set_id"]].name == clean_name(last["card_name"])
