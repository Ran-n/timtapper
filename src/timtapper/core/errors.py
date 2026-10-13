#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 22:05:51.724953
Revised: 2026/10/12 22:05:57.744426

Errors shown to the user: their text translates, so a Spanish screen never explains itself in English.
"""

from collections.abc import Callable


class TranslatableError(ValueError):
    """`template` is an English sentence with {placeholders} filled from `params`, and doubles as its
    translation key (tests/test_i18n.py finds every template); str() is the English text, for logs."""

    def __init__(self, template: str, **params: object) -> None:
        super().__init__(template.format(**params))
        self.template = template
        self.params = params

    def translated(self, _: Callable[[str], str]) -> str:
        return _(self.template).format(**self.params)
