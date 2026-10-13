#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.861081
Revised: 2026/10/13 01:17:15.926761
"""

import datetime as dt
import json

import flet as ft
import pytest

from catalog import sync as sync_mod
from catalog.optcgapi import CatalogError, LeaderRecord
from ui import settings_view as settings_mod
from ui.leader_picker import MAX_RESULTS, build_picker
from ui.settings_view import SettingsScreen
from ui.stats_view import StatsScreen
from ui.theme import THEMES
from uitools import by_data, fire, texts, walk


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
    assert not any("·" in t and "%" in t for t in shown)  # record and rate are always separate badges
    tagged = [c.data for c in walk(s.body)]
    # the four split tiles, best/worst matchup and every matchup row each show a record and a rate badge
    assert tagged.count("rate-badge") >= 6 and tagged.count("record-badge") >= tagged.count("rate-badge")


@pytest.mark.regression
def test_best_and_worst_matchup_each_get_a_full_row(ctx, sample_event):
    """Side by side, the matchup tiles broke long leader names mid-word at 360 dp."""
    s = StatsScreen(ctx)
    s.build()
    rows_with_both = [
        c for c in walk(s.body) if isinstance(c, ft.Row) and {"Best matchup", "Worst matchup"} <= set(texts(c))
    ]
    assert rows_with_both == []
    assert {"Best matchup", "Worst matchup"} <= set(texts(s.body))


async def test_stats_filters(ctx, sample_event, events, leader_ids):
    other = events.create("Other deck", "treasure_cup", dt.date(2026, 1, 1), leader_ids[5])
    r = events.add_round(other.id, leader_ids[1])
    events.update_game(r.id, 1, result="L")
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


@pytest.mark.parametrize("card", ["summary_card", "matchups_card"])
@pytest.mark.parametrize("narrowed", [True, False])
async def test_stats_share_passes_the_one_leader_played(ctx, sample_event, monkeypatch, card, narrowed):
    """Narrowed to one own leader, the shared card gets that leader for its header portrait."""
    from share import render
    from stats.compute import Filters

    seen = []
    monkeypatch.setattr(render, card, lambda *args: seen.append(args[-1]))

    async def fake_share(draw, *, title, mime_type="image/png"):
        draw()

    monkeypatch.setattr(ctx, "share_file", fake_share)
    s = StatsScreen(ctx)
    if narrowed:
        s.filters = Filters(sample_event.leader_id)
    s.build()
    btn = by_data(s.body, "share-summary" if card == "summary_card" else "share-matchups")
    await fire(btn.on_click, btn)
    assert seen == [ctx.leaders_by_id[sample_event.leader_id] if narrowed else None]


# ---- leader picker --------------------------------------------------------
async def test_picker_search_and_limit(ctx):
    picked = []
    sheet = build_picker(ctx, "Pick", picked.append)
    field, results = by_data(sheet, "leader-search"), by_data(sheet, "leader-results")
    assert len(ctx.leaders) > MAX_RESULTS
    assert len([c for c in results.controls if isinstance(c.data, int)]) == MAX_RESULTS
    # the list says it stops, so a leader past the cut isn't taken for missing
    assert texts(by_data(results, "more-leaders")) == [
        f"{MAX_RESULTS} of {len(ctx.leaders)} leaders — search to find the rest"
    ]
    field.value = "zzzz-no-match"
    await fire(field.on_change, field)
    assert texts(results) == ["No leader matches"]
    field.value = "OP01-001"
    await fire(field.on_change, field)
    assert len(results.controls) == 1  # under the cut: no hint
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
    assert by_data(settings.body, "logo").width == 56


@pytest.mark.parametrize(("failed", "kind"), [(0, "info"), (1, "error")])
async def test_update_leaders_success(settings, ctx, monkeypatch, page, prefs, failed, kind):
    asked = []
    monkeypatch.setattr(
        sync_mod, "fetch_leaders", lambda: [LeaderRecord("OP99-001", "Newbie", "OP99", "Future", ("Red",))]
    )
    monkeypatch.setattr(sync_mod, "fetch_sources", lambda: ("OP-99",))
    monkeypatch.setattr(
        sync_mod.portraits, "download_missing", lambda codes: asked.append(codes) or (1 - failed, failed)
    )
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    assert any(ld.code == "OP99-001" for ld in ctx.leaders)
    assert asked == [["OP99-001"]]
    message = page.dialogs[-1].content.value
    assert "1 new" in message
    assert ("pictures could not be downloaded" in message) is bool(failed)
    assert page.dialogs[-1].data == kind
    assert settings.busy is False
    assert prefs["timtapper.leader_sources"] == "OP-99"


async def test_update_leaders_offline(settings, monkeypatch, page, prefs, caplog):
    def offline():
        raise CatalogError("offline")

    monkeypatch.setattr(sync_mod, "fetch_leaders", offline)
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].data == "error"
    assert settings.busy is False
    assert prefs == {}
    assert any(r.name == "timtapper.ui.settings" and r.levelname == "WARNING" for r in caplog.records)


@pytest.mark.regression
async def test_update_leaders_reports_an_unexpected_failure(settings, monkeypatch, page, prefs, caplog):
    """Anything but a download error (a database error, a full disk) left the button with no message."""

    def broken():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(sync_mod, "fetch_leaders", broken)
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].data == "error"
    assert page.dialogs[-1].content.value == "Could not update leaders (RuntimeError)"
    assert "leader update failed" in caplog.text
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
    events.create("extra", "treasure_cup", dt.date(2026, 1, 2))
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


async def test_a_restore_that_brings_new_leaders_updates_their_count(settings, ctx, monkeypatch, page, tmp_path):
    from backup.json_backup import FORMAT, VERSION

    before = len(ctx.leaders)
    event = {"name": "x", "event_type": "locals", "date": "2026-01-01", "leader": "OP99-001", "rounds": []}
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [event]}).encode()
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "b.json", len(data), bytes=data)])
    )
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    await fire(page.dialogs[-1].actions[1].on_click, page.dialogs[-1].actions[1])
    assert f"{before + 1} leaders in the catalogue. New sets are added automatically." in texts(settings.body)


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
    assert page.dialogs[-1].data == "error"
    assert len(events.list()) == 1


@pytest.mark.regression
async def test_an_invalid_backup_is_explained_in_the_users_language(settings, monkeypatch, page, tmp_path):
    """The reason after "No es una copia válida:" was English."""
    from i18n import set_lang

    set_lang(page, "es")
    path = tmp_path / "bad.json"
    path.write_bytes(b"{}")
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "bad.json", 2, path=str(path))])
    )
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert page.dialogs[-1].content.value == "No es una copia válida: no es una copia de timtapper"


@pytest.mark.parametrize(
    ("picker", "expect_error"),
    [(FakePicker(None), False), (FakePicker([]), False), (FakePicker(exc=RuntimeError("no picker")), True)],
)
async def test_import_cancel_or_picker_failure(settings, monkeypatch, page, picker, expect_error):
    monkeypatch.setattr(settings_mod.ft, "FilePicker", picker)
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    errors = [d for d in page.dialogs if isinstance(d, ft.SnackBar) and d.data == "error"]
    assert bool(errors) is expect_error
    assert not any(isinstance(d, ft.AlertDialog) for d in page.dialogs)


async def test_import_unreadable_file(settings, monkeypatch, page):
    monkeypatch.setattr(settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "x.json", 0)]))
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].content.value == "Could not read that file"


async def test_import_from_a_path_that_cannot_be_read(settings, monkeypatch, page, tmp_path, caplog):
    gone = tmp_path / "gone.json"
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "gone.json", 0, path=str(gone))])
    )
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    assert page.dialogs[-1].content.value == "Could not read that file"
    assert "could not read" in caplog.text


@pytest.mark.regression
async def test_import_reports_an_unexpected_failure_and_keeps_the_events(
    settings, ctx, events, sample_event, monkeypatch, page, tmp_path
):
    """A database error during the restore reached no one: the dialog closed and nothing was said."""
    from backup.json_backup import export_backup

    data = export_backup(events.list(), ctx.leaders_by_id)
    path = tmp_path / "b.json"
    path.write_bytes(data)
    monkeypatch.setattr(
        settings_mod.ft, "FilePicker", FakePicker([ft.FilePickerFile(1, "b.json", len(data), path=str(path))])
    )

    def broken(db, raw):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(settings_mod, "import_backup", broken)
    btn = by_data(settings.body, "import")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert page.dialogs[-1].data == "error"
    assert page.dialogs[-1].content.value == "Could not restore the backup (RuntimeError)"
    assert [e.name for e in events.list()] == ["Sunday locals"]


async def test_language_and_theme(settings, ctx, monkeypatch):
    saved, changed = {}, []

    class Prefs:
        async def set(self, key, value):
            saved[key] = value
            return True

    monkeypatch.setattr("ui.context.ft.SharedPreferences", Prefs)
    ctx.on_appearance_change = lambda: changed.append(ctx.lang)
    lang = by_data(settings.body, "language")
    lang.value = "es"
    await fire(lang.on_select, lang)
    mode = by_data(settings.body, "mode")
    mode.selected = ["dark"]
    await fire(mode.on_change, mode)
    nord = by_data(settings.body, "theme-nord")
    await fire(nord.on_click, nord)
    assert saved == {"timtapper.lang": "es", "timtapper.theme": "dark", "timtapper.palette": "nord"}
    assert changed == ["es", "es", "es"]  # language, mode and theme each rebuild the screen
    assert ctx.page.theme_mode == ft.ThemeMode.DARK
    assert ctx.theme.key == "nord" and ctx.scheme is THEMES["nord"].dark
    assert ctx.page.dark_theme.color_scheme.primary == THEMES["nord"].dark.primary


def test_theme_swatches_mark_the_active_theme(settings, ctx):
    assert ctx.theme.key == "gruvbox"  # default
    swatches = {key: by_data(settings.body, f"theme-{key}") for key in THEMES}
    widths = {key: sw.border.top.width for key, sw in swatches.items()}
    assert widths["gruvbox"] > max(w for k, w in widths.items() if k != "gruvbox")
    assert "Classic" in texts(swatches["classic"])


def test_theme_names_are_never_ellipsized(settings):
    """Text is never cut off with "…" anywhere (project rule); the swatch labels were."""
    labels = [c for key in THEMES for c in walk(by_data(settings.body, f"theme-{key}")) if isinstance(c, ft.Text)]
    assert labels and all(t.overflow != ft.TextOverflow.ELLIPSIS and t.max_lines is None for t in labels)


def test_every_language_has_a_flag():
    from xml.etree import ElementTree

    from core.paths import ASSETS_DIR
    from i18n import LANGUAGES
    from ui.widgets import LANGUAGE_FLAGS

    assert set(LANGUAGE_FLAGS) == set(LANGUAGES)
    for path in LANGUAGE_FLAGS.values():
        root = ElementTree.parse(ASSETS_DIR / path).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg", path


def test_language_dropdown_shows_flags(settings, ctx):
    lang = by_data(settings.body, "language")
    flags = {o.key: o.leading_icon.content.content.src for o in lang.options}
    assert flags == {"en": "flags/gb.svg", "es": "flags/es.svg", "gl": "flags/gl.svg"}
    assert lang.leading_icon.content.content.src == flags[ctx.lang]


# ---- leader portrait ----------------------------------------------------------
def test_leader_portrait_bundled_unknown_and_none(ctx):
    from catalog.repository import Leader
    from ui.widgets import leader_portrait

    known = next(ld for ld in ctx.leaders if ld.code == "OP01-001")
    frame = leader_portrait(known, 40)
    assert frame.data == "portrait-frame"
    img = frame.content.content
    assert isinstance(img, ft.Image) and img.src == "leaders/OP01-001.webp"
    assert isinstance(img.error_content, ft.Icon)
    stranger = Leader(0, "OP99-999", "Nobody", None, ())
    assert isinstance(leader_portrait(stranger).content.content, ft.Icon)
    placeholder = leader_portrait(None)
    assert isinstance(placeholder.content, ft.Icon) and placeholder.data != "portrait-frame"


def test_stats_without_games_show_dashes(ctx):
    s = StatsScreen(ctx)
    s.build()
    tagged = [c.data for c in walk(s.body)]
    assert "rate-badge" not in tagged  # no 0% badges when nothing was played
    assert tagged.count("record-badge") >= 4  # the four split tiles each show a dash
    assert all(texts(c) == ["—"] for c in walk(s.body) if getattr(c, "data", None) == "record-badge")


def test_stats_split_tiles_use_large_badges(ctx, sample_event):
    s = StatsScreen(ctx)
    s.build()
    sizes = {
        t.size
        for c in walk(s.body)
        if getattr(c, "data", None) in ("record-badge", "rate-badge")
        for t in walk(c)
        if isinstance(t, ft.Text)
    }
    assert sizes == {13, 15}  # 15 in the split tiles, 13 in matchup rows and tiles


@pytest.mark.regression
@pytest.mark.parametrize("lang", ["en", "es", "gl"])
def test_mode_labels_never_wrap(ctx, lang):
    """Regression: "System"/"Sistema" used to wrap mid-word in the 360 dp window."""
    from i18n import set_lang

    set_lang(ctx.page, lang)
    s = SettingsScreen(ctx)
    s.build()
    segments = by_data(s.body, "mode").segments
    assert [seg.value for seg in segments] == ["system", "light", "dark"]
    for seg in segments:
        assert isinstance(seg.label, ft.Text) and seg.label.no_wrap
        assert seg.label.overflow == ft.TextOverflow.VISIBLE and seg.icon is not None
    assert [seg.label.value for seg in segments] == [ctx._("System"), ctx._("Light"), ctx._("Dark")]


@pytest.mark.live
async def test_live_update_leaders_button(settings, ctx, page, prefs):
    """Settings → Update leaders against the real optcgapi.com: no mocks between the button and the database."""
    before = len(ctx.leaders)
    btn = by_data(settings.body, "update-leaders")
    await fire(btn.on_click, btn)
    message = page.dialogs[-1]
    assert message.data == "info", message.content.value  # an error snackbar means the real update failed
    assert message.content.value.startswith("Leaders updated:")
    assert len(ctx.leaders) >= before
    assert "OP-01" in prefs["timtapper.leader_sources"].split(",")
    assert settings.busy is False and not by_data(settings.body, "update-leaders").disabled


def test_stats_show_games_and_who_chose_the_turn(ctx, events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[2], "top_cut")
    events.update_game(r.id, 1, result="L", went_first=True, chose_turn=True)
    events.update_game(r.id, 2, result="W")  # you chose (lost game 1)
    events.update_game(r.id, 3, result="W")  # they chose (you won game 2)
    s = StatsScreen(ctx)
    s.build()
    shown = texts(s.body)
    for label in ("You chose turn", "They chose turn", "Games"):
        assert label in shown
    games_tile = by_data(s.body, "games")
    assert "4-2" in texts(games_tile)  # sample: W L W + this round's L W W
    assert "3-1" in shown  # matches: the best of 3 counts once


def test_byes_get_their_own_tile_and_stay_out_of_the_record(ctx, events, sample_event):
    events.add_round(sample_event.id, None, "bye")
    s = StatsScreen(ctx)
    s.build()
    games = by_data(s.body, "games")
    assert "Byes" in texts(games) and "1" in texts(games)
    assert "2-1" in texts(s.body)  # the record still counts only the played rounds


def test_no_byes_no_byes_tile(ctx, sample_event):
    s = StatsScreen(ctx)
    s.build()
    assert "Byes" not in texts(s.body)


def test_the_scope_names_the_set(ctx, events, sample_event):
    from stats.compute import Filters

    s = StatsScreen(ctx)
    s.filters = Filters(set_code="OP16")
    assert s.scope_label() == "All leaders · OP16"
