#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.229018
Revised: 2026/10/12 16:54:58.117297

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
    "locals": "Locals",
    "regional": "Regional",
    "national": "National",
    "online": "Online",
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


# card colors are stored by their English name, which is also the translation key
COLOR_LABELS = COLORS


def color_label(_: Translate, color: str) -> str:
    return _(color)
