#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 22:05:36.483826
Revised: 2026/10/12 22:05:36.483826
"""

from core.errors import TranslatableError


def test_str_is_the_english_sentence_with_its_params():
    exc = TranslatableError("event {event}: invalid date {value!r}", event=2, value="soon")
    assert str(exc) == "event 2: invalid date 'soon'"
    assert (exc.template, exc.params) == ("event {event}: invalid date {value!r}", {"event": 2, "value": "soon"})


def test_translated_fills_the_translated_template():
    table = {"event {event}: invalid date {value!r}": "evento {event}: fecha no válida {value!r}"}
    exc = TranslatableError("event {event}: invalid date {value!r}", event=2, value="soon")
    assert exc.translated(lambda s: table.get(s, s)) == "evento 2: fecha no válida 'soon'"


def test_an_untranslated_template_falls_back_to_english():
    assert TranslatableError("nope").translated(lambda s: s) == "nope"
