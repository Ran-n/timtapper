#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 21:14:59.902374
Revised: 2026/10/12 21:14:59.902374
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from events.naming import numbered, suggest_name


@pytest.mark.parametrize(
    ("template", "name", "expected"),
    [
        ("Local #{n}", "Local #3", 3),
        ("Local #{n}", "Local #12", 12),
        ("Local #{n}", "Local #", None),
        ("Local #{n}", "Local #3b", None),
        ("Local #{n}", "Sunday locals", None),
        ("Local #{n}", "Regional #3", None),
        ("En liña #{n}", "En liña #7", 7),
        ("Event (#{n}).", "Event (#2).", 2),  # regex characters in a template are literal
        ("Event (#{n}).", "Event x#2).", None),
    ],
)
def test_numbered(template, name, expected):
    assert numbered(template, name) == expected


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([], "Local #1"),
        (["Local #1", "Local #2"], "Local #3"),
        (["Sunday locals", "Store champs"], "Local #3"),  # custom names still count
        (["Local #1", "Local #3"], "Local #4"),  # #2 was deleted: no repeat of #3
        (["Local #9"], "Local #10"),
        (["Local #2", "Sunday locals"], "Local #3"),
    ],
)
def test_suggest_name(names, expected):
    assert suggest_name("Local #{n}", names) == expected


@given(st.lists(st.one_of(st.integers(1, 500).map("Local #{}".format), st.text(max_size=12))))
def test_suggestion_is_never_a_name_in_use(names):
    suggested = suggest_name("Local #{n}", names)
    assert suggested not in names
    assert numbered("Local #{n}", suggested) > len(names)
