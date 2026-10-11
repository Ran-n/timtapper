#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.861081
Revised: 2026/10/11 16:27:25.307914
"""

import datetime as dt

import flet as ft
import pytest

from catalog.optcgapi import CatalogError, LeaderRecord
from ui import settings_view as settings_mod
from ui.leader_picker import MAX_RESULTS, build_picker
from ui.settings_view import SettingsScreen
from ui.stats_view import StatsScreen
from uitools import by_data, fire, texts


# ---- stats -------------------------------------------------------------
def test_stats_empty_disables_sharing(ctx):
    s = StatsScreen(ctx)
    s.build()
    assert by_data(s.body, "share-summary").disabled is True
    assert by_data(s.body, "share-matchups").disabled is True
    assert "No games logged yet" in texts(s.body)


def test_stats_show_summary_and_matchups(ctx, sample_event):
    s = StatsScreen(ctx)
    s.build()
    shown = texts(s.body)
    assert "2-1" in shown and "67%" in shown
    assert by_data(s.body, "share-summary").disabled is False
    opponent = ctx.leaders_by_id[sample_event.rounds[0].opponent_leader_id].name
    assert opponent in shown


async def test_stats_filters(ctx, sample_event, events, leader_ids):
    other = events.create("Other deck", "online", dt.date(2026, 1, 1), leader_ids[5])
    r = events.add_round(other.id, leader_ids[1])
    events.update_round(r.id, result="L")
    s = StatsScreen(ctx)
    s.build()
    assert "2-2" in texts(s.body)
    dd = by_data(s.body, "filter-leader")
    assert {o.key for o in dd.options} == {"all", str(leader_ids[0]), str(leader_ids[5])}
    dd.value = str(leader_ids[5])
    await fire(dd.on_select, dd)
    assert "0-1" in texts(s.body)
    assert s.scope_label().startswith("Playing ")
    ty = by_data(s.body, "filter-type")
    ty.value = "locals"
    await fire(ty.on_select, ty)
    assert "—" in texts(s.body)  # that leader never played a locals
    dd = by_data(s.body, "filter-leader")
    dd.value = "all"
    await fire(dd.on_select, dd)
    assert s.scope_label() == "All leaders · Locals"


@pytest.mark.parametrize(("tag", "title"), [("share-summary", "Overall record"), ("share-matchups", "Matchups")])
async def test_stats_share(ctx, sample_event, monkeypatch, tag, title):
    calls = []

    async def fake_share(render, *, title, mime_type="image/png"):
        calls.append((render(), title))

    monkeypatch.setattr(ctx, "share_file", fake_share)
    s = StatsScreen(ctx)
    s.build()
    btn = by_data(s.body, tag)
    await fire(btn.on_click, btn)
    assert calls[0][0].exists() and calls[0][1] == title


# ---- leader picker --------------------------------------------------------
async def test_picker_search_and_limit(ctx):
    picked = []
    sheet = build_picker(ctx, "Pick", picked.append)
    _title, field, results = sheet.content.content.controls
    assert len(results.controls) == MAX_RESULTS
    field.value = "zzzz-no-match"
    await fire(field.on_change, field)
    assert texts(results) == ["No leader matches"]
    field.value = "OP01-001"
    await fire(field.on_change, field)
    assert len(results.controls) == 1
    ctx.page.dialogs.append(sheet)
    await fire(results.controls[0].on_click, results.controls[0])
    assert picked[0].code == "OP01-001"
    assert sheet not in ctx.page.dialogs


# ---- settings ---------------------------------------------------------------
@pytest.fixture
def settings(ctx):
    s = SettingsScreen(ctx)
    s.build()
    return s


def test_settings_shows_catalogue_and_version(settings, ctx):
    from core.version import VERSION

    shown = " ".join(texts(settings.body))
    assert f"{len(ctx.leaders)} leaders" in shown
    assert f"timtapper {VERSION}" in shown


async def test_update_leaders_success(settings, ctx, monkeypatch, page):
    monkeypatch.setattr(
        settings_mod, "fetch_leaders", lambda: [LeaderRecord("OP99-001", "Newbie", "OP99", "Future", ("Red",))]
    )
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    assert any(ld.code == "OP99-001" for ld in ctx.leaders)
    assert "1 new" in page.dialogs[-1].content.value
    assert settings.busy is False


async def test_update_leaders_offline(settings, monkeypatch, page):
    def offline():
        raise CatalogError("offline")

    monkeypatch.setattr(settings_mod, "fetch_leaders", offline)
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].bgcolor == ft.Colors.ERROR
    assert settings.busy is False


async def test_export_backup(settings, ctx, sample_event, monkeypatch):
    calls = []

    async def fake_share(render, *, title, mime_type="image/png"):
        calls.append((render(), mime_type))

    monkeypatch.setattr(ctx, "share_file", fake_share)
    btn = by_data(settings.body, "export")
    await fire(btn.on_click, btn)
    path, mime = calls[0]
    assert mime == "application/json"
    assert b"Sunday locals" in path.read_bytes()


class FakePicker:
    def __init__(self, files=None, exc=None):
        self.files, self.exc = files, exc

    def __call__(self):
        return self

    async def pick_files(self, **kwargs):
        if self.exc:
            raise self.exc
        return self.files


async def test_import_backup_flow(settings, ctx, sample_event, events, monkeypatch, page, tmp_path):
    from backup.json_backup import export_backup

    data = export_backup(events.list(), ctx.leaders_by_id)
    path = tmp_path / "b.json"
    path.write_bytes(data)
    events.create("extra", "online", dt.date(2026, 1, 2))
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "b.json", len(data), path=str(path))])
    )
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog)
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert [e.name for e in events.list()] == ["Sunday locals"]
    assert "Events restored: 1" in page.dialogs[-1].content.value


async def test_import_invalid_file_reports_error(settings, events, sample_event, monkeypatch, page, tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"{}")
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "bad.json", 2, path=str(path))])
    )
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert page.dialogs[-1].bgcolor == ft.Colors.ERROR
    assert len(events.list()) == 1


@pytest.mark.parametrize(
    ("picker", "expect_error"),
    [(FakePicker(None), False), (FakePicker([]), False), (FakePicker(exc=RuntimeError("no picker")), True)],
)
async def test_import_cancel_or_picker_failure(settings, monkeypatch, page, picker, expect_error):
    monkeypatch.setattr(settings_mod.ft, "FilePicker", picker)
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    errors = [d for d in page.dialogs if isinstance(d, ft.SnackBar) and d.bgcolor == ft.Colors.ERROR]
    assert bool(errors) is expect_error
    assert not any(isinstance(d, ft.AlertDialog) for d in page.dialogs)


async def test_import_unreadable_file(settings, monkeypatch, page):
    monkeypatch.setattr(settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "x.json", 0)]))
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].content.value == "Could not read that file"


async def test_language_and_theme(settings, ctx, monkeypatch):
    saved, changed = {}, []

    class Prefs:
        async def set(self, key, value):
            saved[key] = value
            return True

    monkeypatch.setattr("ui.context.ft.SharedPreferences", Prefs)
    ctx.on_language_change = lambda: changed.append(ctx.lang)
    lang = by_data(settings.body, "language")
    lang.value = "es"
    await fire(lang.on_select, lang)
    theme = by_data(settings.body, "theme")
    theme.selected = ["dark"]
    await fire(theme.on_change, theme)
    assert saved == {"timtapper.lang": "es", "timtapper.theme": "dark"}
    assert changed == ["es"]
    assert ctx.page.theme_mode == ft.ThemeMode.DARK
