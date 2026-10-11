#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.640062
Revised: 2026/10/11 16:27:25.076429
"""

import flet as ft
import pytest

import main
from share.deliver import Delivery
from ui import app as app_mod
from ui import context as context_mod
from ui.app import TABS, build_view, install_routing


# ---- routing ------------------------------------------------------------------
@pytest.mark.parametrize(("route", "index"), [("/events", 0), ("/stats", 1), ("/settings", 2), ("/", 0), ("/x", 0)])
def test_tab_views(ctx, route, index):
    view = build_view(ctx, route)
    assert view.route == TABS[index]
    assert view.navigation_bar.selected_index == index


def test_event_view_has_back_stack_and_delete(ctx, sample_event):
    view = build_view(ctx, f"/event/{sample_event.id}")
    assert view.navigation_bar is None
    assert view.appbar.actions[0].data == "delete-event"


@pytest.mark.parametrize("route", ["/event/999999", "/event/abc"])
def test_missing_event_falls_back_to_list(ctx, page, route):
    view = build_view(ctx, route)
    assert view.route == "/events"
    assert page.dialogs[-1].bgcolor == ft.Colors.ERROR


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
    ctx.on_language_change()
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
    assert page.dialogs[-1].bgcolor == ft.Colors.ERROR


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
    page.on_disconnect(None)


async def test_main_reports_database_failure(page, monkeypatch):
    added = []
    page.add = added.append

    def broken():
        raise OSError("disk full")

    monkeypatch.setattr(main, "open_database", broken)
    await main.main(page)
    assert "disk full" in added[0].content.value
