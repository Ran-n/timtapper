#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.640062
Revised: 2026/10/13 08:59:21.514521
"""

import datetime as dt

import flet as ft
import pytest

import main
from core.version import VERSION
from db import Database
from events.repository import EventError
from share.deliver import Delivery
from ui import app as app_mod
from ui import context as context_mod
from ui.app import TABS, build_view, install_routing
from ui.context import PREF_LANG
from uitools import fire, texts


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


# ---- new-event drafts -------------------------------------------------------------
def make_draft(ctx, leader_id=None):
    return ctx.new_event("locals", dt.date(2026, 10, 12), leader_id)


def test_new_event_is_a_draft_under_its_suggested_name(ctx, events, sample_event):
    draft = make_draft(ctx, sample_event.leader_id)
    assert ctx.draft == draft == events.get(draft.id)
    assert draft.name == "Local #2"


def test_untouched_draft_is_dropped(ctx, events):
    draft = make_draft(ctx)
    ctx.drop_untouched_draft()
    with pytest.raises(EventError):
        events.get(draft.id)
    assert ctx.draft is None


TOUCHES = {
    "name": lambda ev, d, ids: ev.update(d.id, name="Store champs"),
    "notes": lambda ev, d, ids: ev.update(d.id, notes="bring sleeves"),
    "type": lambda ev, d, ids: ev.update(d.id, event_type="regional"),
    "date": lambda ev, d, ids: ev.update(d.id, date=dt.date(2026, 1, 1)),
    "leader": lambda ev, d, ids: ev.update(d.id, leader_id=ids[0]),
    "players": lambda ev, d, ids: ev.update(d.id, players=16),
    "round": lambda ev, d, ids: ev.add_round(d.id, ids[1]),
}


@pytest.mark.parametrize("touch", TOUCHES.values(), ids=TOUCHES.keys())
def test_touched_draft_is_kept(ctx, events, leader_ids, touch):
    draft = make_draft(ctx)
    touch(events, draft, leader_ids)
    ctx.drop_untouched_draft()
    assert events.get(draft.id)
    assert ctx.draft is None


def test_draft_deleted_from_its_menu_is_no_error(ctx, events):
    draft = make_draft(ctx)
    events.delete(draft.id)
    ctx.drop_untouched_draft()
    assert ctx.draft is None


def test_without_a_draft_nothing_is_dropped(ctx, events, sample_event):
    ctx.drop_untouched_draft()
    assert events.get(sample_event.id) == sample_event


def test_leaving_the_draft_drops_it_before_the_list_is_built(ctx, page, events):
    route_change = install_routing(ctx)
    draft = make_draft(ctx)
    page.route = f"/event/{draft.id}"
    route_change()
    assert events.get(draft.id)  # still on its screen: kept
    page.route = "/events"
    route_change()
    assert events.list() == []
    assert "No events yet" in texts(page.views[-1].controls[0])


async def back_from_draft(ctx, page, touch=None):
    route_change = install_routing(ctx)
    route_change()
    draft = make_draft(ctx)
    page.route = f"/event/{draft.id}"
    route_change()
    if touch:
        touch(draft)
    await page.on_view_pop(None)
    page.route = page.routes[-1]
    route_change()  # what Flet does after navigate()
    return draft


async def test_back_from_an_untouched_draft_drops_it(ctx, page, events, sample_event):
    await back_from_draft(ctx, page)
    assert [e.id for e in events.list()] == [sample_event.id]


async def test_back_from_a_draft_with_a_round_keeps_it(ctx, page, events, leader_ids):
    draft = await back_from_draft(ctx, page, lambda d: events.add_round(d.id, leader_ids[0]))
    assert [e.id for e in events.list()] == [draft.id]


def test_language_change_rebuilds_top_view(ctx, page):
    install_routing(ctx)()
    from i18n import set_lang

    set_lang(page, "es")
    ctx.on_appearance_change()
    assert page.views[-1].appbar.title.value == "Eventos"


def test_an_appearance_change_before_any_screen_is_shown_builds_nothing(ctx, page):
    install_routing(ctx)
    ctx.on_appearance_change()  # e.g. the device turned dark while the first screen was still loading
    assert page.views == []


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


@pytest.mark.parametrize("outcome", [Delivery.SHARED, Delivery.CANCELLED])
async def test_share_file_says_nothing_when_shared_or_cancelled(ctx, monkeypatch, page, tmp_path, outcome):
    out = tmp_path / "x.png"
    out.write_bytes(b"x")

    async def fake_deliver(path, *, title, mime_type):
        return outcome

    monkeypatch.setattr(context_mod, "deliver", fake_deliver)
    await ctx.share_file(lambda: out, title="t")
    assert page.dialogs == []  # the share sheet was the feedback (or you closed it)


async def test_share_file_render_failure(ctx, page):
    def broken():
        raise ValueError("bad font")

    await ctx.share_file(broken, title="t")
    # "file", not "image": backups go through here too
    assert page.dialogs[-1].content.value == "Could not create the file (ValueError)"


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


def test_leaders_by_id_is_cached_with_the_leaders(ctx):
    by_id = ctx.leaders_by_id
    assert ctx.leaders_by_id is by_id  # built once, not on every tile and round row
    assert by_id == {leader.id: leader for leader in ctx.leaders}
    ctx.invalidate_leaders()
    assert ctx.leaders_by_id is not by_id and ctx.leaders_by_id == by_id


# ---- entry point ------------------------------------------------------------------
def test_open_database_migrates_and_seeds(tmp_path):
    db = main.open_database()
    try:
        from catalog.repository import LeaderRepository

        assert LeaderRepository(db).count() > 100
        assert LeaderRepository(db).release_dates()["OP01"] == dt.date(2022, 12, 2)
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
    message, report = added[0].content.controls
    assert "disk full" in message.value
    assert report.data == "startup-report" and report.selectable
    assert report.value.startswith(f"timtapper {VERSION} ")
    assert "migrations:" in report.value


async def test_database_failure_speaks_the_saved_language(page, prefs, monkeypatch):
    """The failure screen comes before the app (no context yet), yet says what went wrong in your language."""
    added = []
    page.add = added.append
    prefs[PREF_LANG] = "es"

    def broken():
        raise OSError("disk full")

    monkeypatch.setattr(main, "open_database", broken)
    await main.main(page)
    message, report = added[0].content.controls
    assert message.value == "timtapper no pudo abrir su base de datos: OSError: disk full"
    assert report.value.startswith("timtapper ")  # the report stays English: it's for whoever fixes the app


async def test_unreadable_language_falls_back_to_the_default(page, monkeypatch, caplog):
    class Broken:
        async def get(self, key):
            raise RuntimeError("no storage")

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Broken)
    assert await context_mod.saved_language() == "en"
    assert "could not read the saved language" in caplog.text


async def test_startup_failure_report_carries_the_migration_log(page, monkeypatch):
    """A phone has no debugger: what Alembic did must be on the failure screen itself."""
    added = []
    page.add = added.append

    def broken():
        db = Database(main.db_path())
        db.migrate()
        db.dispose()
        raise OSError("failed after migrating")

    monkeypatch.setattr(main, "open_database", broken)
    await main.main(page)
    report = added[0].content.controls[1].value
    assert "Running upgrade  -> 0001" in report
    assert "alembic_version: [('0006',)]" in report


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
    dropped = []
    monkeypatch.setattr(context_mod.AppContext, "drop_untouched_draft", lambda self: dropped.append(True))
    getattr(page, handler)(None)
    assert disposed == [True]
    assert dropped == [True]  # an untouched new event does not outlive the app either


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


@pytest.mark.regression
async def test_quitting_closes_the_database_even_when_dropping_the_draft_fails(page, monkeypatch, caplog):
    """A database error while dropping the draft skipped db.dispose() and left the file open."""
    opened = []
    real_open = main.open_database
    monkeypatch.setattr(main, "open_database", lambda: opened.append(real_open()) or opened[-1])

    class Prefs:
        async def get(self, key):
            return None

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await main.main(page)
    disposed = []
    real_dispose = opened[0].dispose
    monkeypatch.setattr(opened[0], "dispose", lambda: (disposed.append(True), real_dispose()))

    def broken(self):
        raise RuntimeError("disk I/O error")

    monkeypatch.setattr(context_mod.AppContext, "drop_untouched_draft", broken)
    page.on_disconnect(None)
    assert disposed == [True]
    assert "could not drop the untouched draft event" in caplog.text


def test_a_new_event_is_played_in_the_newest_set(ctx):
    from catalog.repository import set_codes

    draft = make_draft(ctx)  # dated 2026-10-12: OP17 came out on 2026-08-28
    assert draft.set_code == set_codes(ctx.leaders)[0] == "OP17"


@pytest.mark.parametrize(
    ("day", "played_in"),
    [
        (dt.date(2026, 8, 27), "OP16"),  # the day before OP17
        (dt.date(2026, 8, 28), "OP17"),
        (dt.date(2024, 5, 3), "OP06"),  # EB01's release day: still OP06's format
        (dt.date(2022, 11, 30), None),  # before OP01
    ],
)
def test_a_new_event_is_played_in_the_set_out_on_its_date(ctx, day, played_in):
    assert ctx.new_event("locals", day, None).set_code == played_in


def test_a_new_event_without_any_release_date_known_is_played_in_the_newest_set(ctx, monkeypatch):
    """A catalogue from before release dates were kept: the old behaviour, the newest main set."""
    monkeypatch.setattr(type(ctx), "release_dates", property(lambda self: {}))
    assert ctx.new_event("locals", dt.date(2023, 1, 1), None).set_code == "OP17"


def test_release_dates_are_cached_with_the_leaders(ctx):
    dates = ctx.release_dates
    assert ctx.release_dates is dates and dates["OP01"] == dt.date(2022, 12, 2)
    ctx.leader_repo.set_releases({"OP01": dt.date(2022, 12, 3)})
    assert ctx.release_dates["OP01"] == dt.date(2022, 12, 2)
    ctx.invalidate_leaders()
    assert ctx.release_dates["OP01"] == dt.date(2022, 12, 3)


@pytest.mark.parametrize(
    ("chosen", "day", "fields"),
    [
        # still the set its date gave it: it follows the new date
        ("OP17", dt.date(2026, 7, 1), {"date": dt.date(2026, 7, 1), "set_code": "OP16"}),
        ("OP17", dt.date(2022, 11, 1), {"date": dt.date(2022, 11, 1), "set_code": None}),
        # picked by hand, or "Not noted": it stays
        ("OP15", dt.date(2026, 7, 1), {"date": dt.date(2026, 7, 1)}),
        ("EB03", dt.date(2026, 7, 1), {"date": dt.date(2026, 7, 1)}),
        (None, dt.date(2026, 7, 1), {"date": dt.date(2026, 7, 1)}),
        # the same day picked again: nothing but the date
        ("OP17", dt.date(2026, 10, 12), {"date": dt.date(2026, 10, 12)}),
    ],
)
def test_redate_moves_the_set_only_while_it_follows_the_date(ctx, events, chosen, day, fields):
    draft = make_draft(ctx)
    event = events.update(draft.id, set_code=chosen)
    assert ctx.redate(event, day) == fields


def test_redated_back_the_set_follows_again(ctx, events):
    """Moved to July (OP16) and back to October: OP16 is what July gives, so it follows back to OP17."""
    event = make_draft(ctx)
    event = events.update(event.id, **ctx.redate(event, dt.date(2026, 7, 1)))
    event = events.update(event.id, **ctx.redate(event, dt.date(2026, 10, 12)))
    assert event.set_code == "OP17"


def test_a_new_event_without_any_set_known_has_none(ctx, monkeypatch):
    monkeypatch.setattr(type(ctx), "leaders", property(lambda self: []))
    assert make_draft(ctx).set_code is None
