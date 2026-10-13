#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 21:14:59.826772
Revised: 2026/10/12 21:14:59.826772

Suggested names for new events: the type's numbered template ("Local #{n}")
filled with the next free number for that type.
"""

import re
from collections.abc import Sequence


def _pattern(template: str) -> re.Pattern[str]:
    return re.compile(re.escape(template).replace(re.escape("{n}"), r"(\d+)"))


def numbered(template: str, name: str) -> int | None:
    """The number in `name` when it follows `template` ("Local #3" -> 3), else None."""
    match = _pattern(template).fullmatch(name)
    return int(match[1]) if match else None


def suggest_name(template: str, names: Sequence[str]) -> str:
    """`template` with the number after both the count of `names` (the events of that type) and the
    highest number any of them already carries — so a deleted or renamed event never makes one repeat."""
    used = [n for n in (numbered(template, name) for name in names) if n is not None]
    return template.format(n=max([len(names), *used]) + 1)
