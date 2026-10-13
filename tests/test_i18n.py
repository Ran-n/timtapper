#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:45.093250
Revised: 2026/10/12 23:54:37.510279

Every string the code translates exists in every language, and no table carries stale keys.
"""

import ast
import string
from pathlib import Path

import pytest

from events.repository import _TRISTATE_ERRORS, _WHOLE_NUMBER_ERRORS
from i18n import (
    _EVENT_NAME_TEMPLATES,
    _EVENT_TYPE_LABELS,
    COLOR_LABELS,
    LANGUAGES,
    color_label,
    event_name_template,
    event_type_label,
    translator,
)
from i18n.translations import TRANSLATIONS

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"


def used_keys() -> set[str]:
    """String literals passed to `_()`, `ctx._()` or `self.ctx._()` anywhere in the app, and the EventError and
    BackupError messages (shown translated after "Could not save:" and "Not a valid backup:")."""
    keys = set(_EVENT_TYPE_LABELS.values()) | set(_EVENT_NAME_TEMPLATES.values()) | set(COLOR_LABELS)
    keys |= set(_WHOLE_NUMBER_ERRORS.values()) | set(_TRISTATE_ERRORS.values())
    for path in APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            for kw in node.keywords:  # backup.json_backup's helpers take their error template as msg=
                if kw.arg == "msg" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    keys.add(kw.value.value)
            is_tr = (isinstance(func, ast.Name) and func.id in ("_", "EventError", "BackupError")) or (
                isinstance(func, ast.Attribute) and func.attr == "_"
            )
            if is_tr and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                keys.add(node.args[0].value)
    return keys


def placeholders(s: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(s) if name}


def test_languages_have_tables():
    assert set(LANGUAGES) == set(TRANSLATIONS)


@pytest.mark.parametrize("lang", sorted(TRANSLATIONS))
def test_every_used_string_is_translated(lang):
    missing = used_keys() - set(TRANSLATIONS[lang])
    assert not missing, f"{lang} is missing: {sorted(missing)}"


@pytest.mark.parametrize("lang", sorted(TRANSLATIONS))
def test_no_stale_keys(lang):
    stale = set(TRANSLATIONS[lang]) - used_keys()
    assert not stale, f"{lang} has keys no code uses: {sorted(stale)}"


@pytest.mark.parametrize("lang", sorted(TRANSLATIONS))
def test_placeholders_match(lang):
    for key, value in TRANSLATIONS[lang].items():
        assert placeholders(key) == placeholders(value), (lang, key)


def test_translator_falls_back():
    assert translator("es")("Events") == "Eventos"
    assert translator("xx")("Events") == "Events"
    assert translator("es")("not a key") == "not a key"


def test_event_type_labels():
    _ = translator("gl")
    assert event_type_label(_, "worlds") == "Mundial"
    assert event_type_label(_, "pirates_party") == "Pirates Party"  # official event names stay in English
    assert event_type_label(_, "bogus") == "Outro"
    assert event_type_label(_, "online") == "Outro"  # a dropped type reads as "other"


def test_every_event_type_has_a_label_and_an_icon():
    from db.models import EVENT_TYPES
    from ui.widgets import EVENT_TYPE_ICONS

    assert set(_EVENT_TYPE_LABELS) == set(EVENT_TYPES) == set(EVENT_TYPE_ICONS)
    assert "online" not in EVENT_TYPES


def test_event_name_templates():
    from db.models import EVENT_TYPES

    assert set(_EVENT_NAME_TEMPLATES) == set(EVENT_TYPES)
    assert event_name_template(translator("en"), "locals") == "Local #{n}"
    assert event_name_template(translator("gl"), "regional") == "Rexional #{n}"
    assert event_name_template(translator("es"), "bogus") == "Evento #{n}"


def test_color_labels():
    assert color_label(translator("gl"), "Red") == "Vermello"
    assert color_label(translator("es"), "Yellow") == "Amarillo"
    assert [color_label(translator("en"), c) for c in COLOR_LABELS] == list(COLOR_LABELS)


@pytest.mark.parametrize(
    ("lang", "placement", "players", "expected"),
    [
        ("en", 3, 32, "#3 of 32"),
        ("en", 3, None, "#3"),
        ("en", None, 32, "32 players"),
        ("en", None, None, None),
        ("es", 1, 8, "#1 de 8"),
        ("gl", None, 16, "16 xogadores"),
    ],
)
def test_standing_label(lang, placement, players, expected):
    from i18n import standing_label, translator

    assert standing_label(translator(lang), placement, players) == expected


@pytest.mark.parametrize(
    ("placement", "dropped", "expected"),
    [
        (None, False, None),
        (1, False, "1st place"),
        (2, False, "2nd place"),
        (3, False, "Top 4"),
        (4, False, "Top 4"),
        (5, False, "Top 8"),
        (512, False, "Top 512"),
        (513, False, "Outside the top 512"),
        (3, True, "Dropped"),
        (None, True, "Dropped"),
    ],
)
def test_bracket_label(placement, dropped, expected):
    from i18n import bracket_label

    assert bracket_label(translator("en"), placement, dropped) == expected


def test_bracket_label_translated():
    from i18n import bracket_label

    assert bracket_label(translator("es"), 1) == "1.º puesto"
    assert bracket_label(translator("gl"), 20) == "Top 32"
