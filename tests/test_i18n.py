#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:45.093250
Revised: 2026/10/11 16:27:25.526319

Every string the code translates exists in every language, and no table carries stale keys.
"""

import ast
import string
from pathlib import Path

import pytest

from i18n import _EVENT_TYPE_LABELS, LANGUAGES, event_type_label, translator
from i18n.translations import TRANSLATIONS

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"


def used_keys() -> set[str]:
    """String literals passed to `_()`, `ctx._()` or `self.ctx._()` anywhere in the app."""
    keys = set(_EVENT_TYPE_LABELS.values())
    for path in APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            func = node.func
            is_tr = (isinstance(func, ast.Name) and func.id == "_") or (
                isinstance(func, ast.Attribute) and func.attr == "_"
            )
            if is_tr and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
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
    assert event_type_label(_, "online") == "En liña"
    assert event_type_label(_, "bogus") == "Outro"
