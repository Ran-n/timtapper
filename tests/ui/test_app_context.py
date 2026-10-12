#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.640062
Revised: 2026/10/12 16:55:01.298188
"""

import flet as ft
import pytest

import main
from events.repository import EventError
from share.deliver import Delivery
from ui import app as app_mod
from ui import context as context_mod
from ui.app import TABS, build_view, install_routing
from uitools import fire


# ---- routing ------------------------------------------------------------------
@pytest.mark.parametrize(("route", "index"), [("/events", 0), ("/stats", 1), ("/settings", 2), ("/", 0), ("/x", 0)])
def test_tab_views(ctx, route, index):
    view = build_view(ctx, route)
    assert view.route == TABS[index]
    assert view.navigation_bar.selected_index == index


@pytest.mark.parametrize(("route", "has_logo"), [("/events", True), ("/stats", False), ("/settings", False)])
def test_only_events_app_bar_carries_the_logo(ctx, route, has_logo):
    leading = build_view(ctx, route).appbar.leading
    assert (leading is not None and leading.content.data == "logo") is has_logo


def test_event_view_has_back_stack_and_delete(ctx, sample_event):
    view = build_view(ctx, f"/event/{sample_event.id}")
    assert view.navigation_bar is None
    (menu,) = view.appbar.actions
    assert isinstance(menu, ft.PopupMenuButton) and menu.data == "event-menu" and menu.icon == ft.Icons.MORE_VERT
    assert [item.data for item in menu.items] == ["delete-event"]


def delete_item(ctx, sample_event):
    return build_view(ctx, f"/event/{sample_event.id}").appbar.actions[0].items[0]


async def test_event_menu_delete_confirms_and_deletes(ctx, page, events, sample_event):
    item = delete_item(ctx, sample_event)
    await fire(item.on_click, item)
    dialog = page.dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog) and dialog.title.value == "Delete this event?"
    assert events.get(sample_event.id)  # nothing gone until confirmed
    yes = dialog.actions[1]
    await fire(yes.on_click, yes)
    with pytest.raises(EventError):
        events.get(sample_event.id)
    assert page.routes[-1] == "/events"


async def test_event_menu_delete_cancel_keeps_event(ctx, page, events, sample_event):
    item = delete_item(ctx, sample_event)
    await fire(item.on_click, item)
    cancel = page.dialogs[-1].actions[0]
    await fire(cancel.on_click, cancel)
    assert page.dialogs == []
    assert events.get(sample_event.id).name == "Sunday locals"


@pytest.mark.parametrize("route", ["/event/999999", "/event/abc"])
def test_missing_event_falls_back_to_list(ctx, page, route):
    view = build_view(ctx, route)
    assert view.route == "/events"
    assert page.dialogs[-1].data == "error"


def test_route_change_stack(ctx, page, sample_event):
    route_change = install_routing(ctx)
    route_change()
    assert [v.route for v in page.views] == ["/events"]
    page.route = f"/event/{sample_event.id}"
    route_change()
    assert [v.route for v in page.views] == ["/events", page.route]
    route_change()  # same route again replaces instead of stacking
    assert len(page.views) == 2
    page.route = "/stats"
    route_change()
    assert [v.route for v in page.views] == ["/stats"]


async def test_back_pops_then_needs_double_press(ctx, page, sample_event, monkeypatch):
    route_change = install_routing(ctx)
    page.route = f"/event/{sample_event.id}"
    route_change()
    page.views.insert(0, build_view(ctx, "/events"))
    await page.on_view_pop(None)
    assert page.routes[-1] == "/events"

    closed = []

    class Window:
        async def destroy(self):
            closed.append(True)

    page.window = Window()
    page.views[:] = [build_view(ctx, "/events")]
    monkeypatch.setattr(app_mod.threading, "Timer", lambda *_a: type("T", (), {"start": lambda self: None})())
    await page.on_view_pop(None)
    assert not closed and page.dialogs[-1].content.value == "Press back again to exit"
    await page.on_view_pop(None)
    assert closed == [True]


def test_language_change_rebuilds_top_view(ctx, page):
    install_routing(ctx)()
    from i18n import set_lang

    set_lang(page, "es")
    ctx.on_appearance_change()
    assert page.views[-1].appbar.title.value == "Eventos"


# ---- context --------------------------------------------------------------------
async def test_load_prefs(ctx, monkeypatch, page):
    class Prefs:
        async def get(self, key):
            return {"timtapper.lang": "gl", "timtapper.theme": "light"}.get(key)

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.load_prefs()
    assert ctx.lang == "gl" and page.theme_mode == ft.ThemeMode.LIGHT


async def test_load_prefs_failure_uses_defaults(ctx, monkeypatch, page, caplog):
    class Prefs:
        async def get(self, key):
            raise RuntimeError("no storage")

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.load_prefs()
    assert ctx.lang == "en" and page.theme_mode == ft.ThemeMode.SYSTEM
    assert "could not read saved preferences" in caplog.text


async def test_save_pref_failure_is_reported(ctx, monkeypatch, page):
    class Prefs:
        async def set(self, key, value):
            raise RuntimeError("read-only")

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.change_theme("dark")
    assert page.dialogs[-1].data == "error"


async def test_share_file_success_and_saved(ctx, monkeypatch, page, tmp_path):
    out = tmp_path / "x.png"
    out.write_bytes(b"x")

    async def fake_deliver(path, *, title, mime_type):
        return Delivery.SAVED

    monkeypatch.setattr(context_mod, "deliver", fake_deliver)
    await ctx.share_file(lambda: out, title="t")
    assert page.dialogs[-1].content.value == "Saved"


async def test_share_file_render_failure(ctx, page):
    def broken():
        raise ValueError("bad font")

    await ctx.share_file(broken, title="t")
    assert "ValueError" in page.dialogs[-1].content.value


async def test_share_file_delivery_failure(ctx, monkeypatch, page, tmp_path):
    async def failing(path, *, title, mime_type):
        raise PermissionError("denied")

    monkeypatch.setattr(context_mod, "deliver", failing)
    await ctx.share_file(lambda: tmp_path, title="t")
    assert "PermissionError" in page.dialogs[-1].content.value


def test_leader_cache_invalidation(ctx, leaders):
    first = ctx.leaders
    assert ctx.leaders is first
    ctx.invalidate_leaders()
    assert ctx.leaders is not first and ctx.leaders == first


# ---- entry point ------------------------------------------------------------------
def test_open_database_migrates_and_seeds(tmp_path):
    db = main.open_database()
    try:
        from catalog.repository import LeaderRepository

        assert LeaderRepository(db).count() > 100
        assert db.path.parent == tmp_path / "data"
    finally:
        db.dispose()


async def test_main_renders_first_screen(page, monkeypatch):
    class Prefs:
        async def get(self, key):
            return None

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await main.main(page)
    assert [v.route for v in page.views] == ["/events"]
    assert page.window.icon.endswith("icon.ico")
    assert (page.window.width, page.window.height) == (412, 892)
    assert (page.window.min_width, page.window.min_height) == (360, 640)
    assert page.window.alignment == ft.Alignment.CENTER
    assert [t.__name__ for t in page.tasks] == ["run_if_due"]  # leader check runs after the first screen
    page.on_disconnect(None)


async def test_main_flushes_window_before_awaiting_prefs(page, monkeypatch):
    seen = []

    class Prefs:
        async def get(self, key):
            seen.append((page.updates, page.window.width))
            return None

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await main.main(page)
    assert seen and all(updates >= 1 and width == 412 for updates, width in seen)
    page.on_disconnect(None)


async def test_main_reports_database_failure(page, monkeypatch):
    added = []
    page.add = added.append

    def broken():
        raise OSError("disk full")

    monkeypatch.setattr(main, "open_database", broken)
    await main.main(page)
    assert "disk full" in added[0].content.value


@pytest.mark.parametrize("handler", ["on_close", "on_disconnect"])
async def test_every_quit_path_closes_the_database(page, monkeypatch, handler):
    """Closing the window and losing the client both release the SQLite file."""
    opened = []
    real_open = main.open_database

    def tracking_open():
        db = real_open()
        opened.append(db)
        return db

    class Prefs:
        async def get(self, key):
            return None

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    monkeypatch.setattr(main, "open_database", tracking_open)
    await main.main(page)
    disposed = []
    real_dispose = opened[0].dispose
    monkeypatch.setattr(opened[0], "dispose", lambda: (disposed.append(True), real_dispose()))
    getattr(page, handler)(None)
    assert disposed == [True]


def test_run_sets_up_logging_then_starts_flet(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "setup_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(main.ft, "run", lambda target, **kw: calls.append(("run", target, kw)))
    main.run()
    assert calls == ["logging", ("run", main.main, {"assets_dir": "assets"})]


def test_launcher_puts_the_app_root_on_the_path_and_runs_main(monkeypatch):
    import sys
    from pathlib import Path

    import launcher

    started = []
    monkeypatch.setattr(main, "run", lambda: started.append(True))
    monkeypatch.setattr(sys, "path", list(sys.path))
    launcher.run()
    assert started == [True]
    assert sys.path[0] == str(Path(launcher.__file__).resolve().parent)
