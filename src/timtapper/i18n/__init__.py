#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.229018
Revised: 2026/10/12 23:54:35.927848

UI languages. Translation tables (translations.py) are keyed by the English
source string, so `_("Events")` works the same in every language and a
missing entry is caught by tests/test_i18n.py rather than shown raw.

    from i18n import tr
    _ = tr(page)
    ft.Text(_("Events"))
"""

from collections.abc import Callable

import flet as ft

from db.models import COLORS
from i18n.translations import TRANSLATIONS

DEFAULT_LANG = "en"
# code -> native name (each language names itself)
LANGUAGES = {"en": "English", "es": "Español", "gl": "Galego"}

Translate = Callable[[str], str]

_EVENT_TYPE_LABELS = {
    "testing": "Testing",
    "pirates_party": "Pirates Party",
    "locals": "Locals",
    "release": "Release event",
    "sealed": "Sealed",
    "heroines_battle": "Heroines Battle",
    "team": "Team battle",
    "store_championship": "Store Championship",
    "treasure_cup": "Treasure Cup",
    "flagship": "Flagship Battle",
    "extra_battle": "Extra Grand Battle",
    "regional": "Regional",
    "national": "National",
    "worlds": "World Championship",
    "other": "Other",
}


def translator(lang: str) -> Translate:
    table = TRANSLATIONS.get(lang) or TRANSLATIONS[DEFAULT_LANG]

    def _(text: str) -> str:
        return table.get(text, text)

    return _


def get_lang(page: ft.Page) -> str:
    return getattr(page, "_timtapper_lang", DEFAULT_LANG)


def set_lang(page: ft.Page, code: str) -> str:
    page._timtapper_lang = code if code in LANGUAGES else DEFAULT_LANG
    return page._timtapper_lang


def tr(page: ft.Page) -> Translate:
    """Translate function bound to the page's current language."""
    return translator(get_lang(page))


def event_type_label(_: Translate, key: str) -> str:
    return _(_EVENT_TYPE_LABELS.get(key, "Other"))


# what a new event of each type is called until you rename it; {n} counts that type's events
_EVENT_NAME_TEMPLATES = {
    "testing": "Testing #{n}",
    "pirates_party": "Pirates Party #{n}",
    "locals": "Local #{n}",
    "release": "Release #{n}",
    "sealed": "Sealed #{n}",
    "heroines_battle": "Heroines Battle #{n}",
    "team": "Team battle #{n}",
    "store_championship": "Store Championship #{n}",
    "treasure_cup": "Treasure Cup #{n}",
    "flagship": "Flagship #{n}",
    "extra_battle": "Extra Battle #{n}",
    "regional": "Regional #{n}",
    "national": "National #{n}",
    "worlds": "Worlds #{n}",
    "other": "Event #{n}",
}


def event_name_template(_: Translate, key: str) -> str:
    return _(_EVENT_NAME_TEMPLATES.get(key, _EVENT_NAME_TEMPLATES["other"]))


# testing sessions have no standings: their placement and player count aren't asked for or shown
UNRANKED_EVENT_TYPES = frozenset({"testing"})


def standing_label(_: Translate, placement: int | None, players: int | None) -> str | None:
    """`#3 of 32`, `#3` or `32 players`; None when neither is known."""
    if placement is not None and players is not None:
        return _("#{place} of {players}").format(place=placement, players=players)
    if placement is not None:
        return _("#{place}").format(place=placement)
    if players is not None:
        return _("{players} players").format(players=players)
    return None


BRACKETS = (4, 8, 16, 32, 64, 128, 256, 512)  # top-cut sizes a placement is read as, after 1st and 2nd


def bracket_label(_: Translate, placement: int | None, dropped: bool = False) -> str | None:
    """Where a placement lands, as standings are talked about: "1st place", "2nd place", "Top 8", … "Outside the
    top 512"; "Dropped" when you left; None when neither is known."""
    if dropped:
        return _("Dropped")
    if placement is None:
        return None
    if placement <= 2:
        return _("1st place") if placement == 1 else _("2nd place")
    cut = next((size for size in BRACKETS if placement <= size), None)
    return _("Top {n}").format(n=cut) if cut else _("Outside the top {n}").format(n=BRACKETS[-1])


# card colors are stored by their English name, which is also the translation key
COLOR_LABELS = COLORS


def color_label(_: Translate, color: str) -> str:
    return _(color)
