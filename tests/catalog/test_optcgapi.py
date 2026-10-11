#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.098982
Revised: 2026/10/11 17:20:13.275773
"""

import httpx
import pytest
import respx

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
