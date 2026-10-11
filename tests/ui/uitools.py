#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.940076
Revised: 2026/10/11 23:25:32.932497

Walk a Flet control tree and fire handlers without a running client.
"""

import dataclasses
import inspect
from types import SimpleNamespace

import flet as ft


def children(control) -> list:
    out = []
    if not dataclasses.is_dataclass(control):
        return out
    for f in dataclasses.fields(control):
        if f.name in ("parent", "page"):
            continue
        try:
            value = getattr(control, f.name)
        except Exception:
            continue
        if isinstance(value, ft.BaseControl):
            out.append(value)
        elif isinstance(value, list):
            out.extend(v for v in value if isinstance(v, ft.BaseControl))
    return out


def walk(control):
    yield control
    for child in children(control):
        yield from walk(child)


def by_data(root, data):
    found = [c for c in walk(root) if getattr(c, "data", None) == data]
    assert found, f"no control with data={data!r}"
    return found[0]


def texts(root) -> list[str]:
    out = []
    for c in walk(root):
        if isinstance(c, ft.Text) and isinstance(c.value, str):
            out.append(c.value)
        for attr in ("label", "content", "hint_text"):
            value = getattr(c, attr, None)
            if isinstance(value, str):
                out.append(value)
    return out


async def fire(handler, control=None, **event_fields):
    """Call a Flet handler the way the client would, awaiting it if async."""
    result = handler(SimpleNamespace(control=control, **event_fields))
    if inspect.isawaitable(result):
        await result


async def pick_leader(sheet: ft.BottomSheet, leader_id: int, code: str) -> None:
    """Search the picker by code (as a user would) and tap the result."""
    field, results = by_data(sheet, "leader-search"), by_data(sheet, "leader-results")
    field.value = code
    await fire(field.on_change, field)
    option = next(c for c in results.controls if c.data == leader_id)
    await fire(option.on_click, option)
