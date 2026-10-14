#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 16:30:39.355506
Revised: 2026/10/14 16:30:39.355506

The web shell's data (ui/shell.py): every screen the app can open at startup, saved as a tree of its controls for the
page to paint before the app is ready.
"""

import asyncio
import dataclasses
import functools
import json
import threading

import flet as ft
import pytest

from db import Database
from ui import shell as shell_mod
from ui.app import NEW_ROUTE, TABS
from ui.context import AppContext
from ui.shell import Serializer, ShellPage, ShellWriter, default_documents, digest, shell_document, theme_colors
from ui.theme import get_theme


class Memory:
    """A ShellStorage in memory."""

    def __init__(self, saved: str | None = None, fail: Exception | None = None):
        self.saved = saved
        self.fail = fail
        self.saves = 0

    async def save(self, text):
        if self.fail:
            raise self.fail
        self.saves += 1
        self.saved = text

    async def load(self):
        return self.saved


def serializer(nav=lambda _c: None, images=None):
    return Serializer(theme_colors(get_theme(None).light), {} if images is None else images, nav)


def walk(tree):
    """Every node of a serialized tree."""
    if isinstance(tree, dict):
        yield tree
        for value in tree.values():
            yield from walk(value)
    elif isinstance(tree, list):
        for value in tree:
            yield from walk(value)


# ---- the tree --------------------------------------------------------------------
def test_a_control_keeps_only_what_is_set():
    node = serializer().node(ft.Text("Hi", size=17))
    assert node == {"t": "Text", "value": "Hi", "size": 17}


def test_callbacks_are_marked_tappable_not_kept():
    node = serializer().node(ft.Container(content=ft.Text("x"), on_click=lambda _e: None))
    assert node["tap"] is True and "on_click" not in node
    assert serializer().node(ft.Container(on_hover=lambda _e: None)) == {"t": "Container"}


def test_theme_tokens_become_the_palettes_hex():
    scheme = get_theme(None).light
    node = serializer().node(ft.Text("x", color=ft.Colors.ON_SURFACE_VARIANT, bgcolor="primary,0.5"))
    assert node["color"] == scheme.fg_muted
    assert node["bgcolor"] == f"{scheme.primary},0.5"
    assert serializer().node(ft.Text("x", color="#123456"))["color"] == "#123456"
    assert serializer().node(ft.Container(bgcolor="white"))["bgcolor"] == "white"  # a name the page knows


def test_icons_are_their_names():
    node = serializer().node(ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=13))
    assert node["icon"] == {"icon": "calendar_today_outlined"}


def test_enums_nested_dataclasses_lists_and_dicts():
    node = serializer().node(
        ft.Row(
            [ft.Text("a")],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            data="x",  # identifies controls for tests; the page has no use for it
        )
    )
    assert node == {"t": "Row", "controls": [{"t": "Text", "value": "a"}], "alignment": "spaceBetween"}
    tree = serializer().node(ft.Container(padding=ft.Padding(1, 2, 3, 4), col={"xs": 6}))
    assert tree["padding"] == {"t": "Padding", "left": 1, "top": 2, "right": 3, "bottom": 4}
    assert tree["col"] == {"xs": 6}


@pytest.mark.regression
def test_full_width_is_kept_as_inf():
    """width=float("inf") (a full-width button) came out as JSON's invalid Infinity, so the page could not read the
    saved shell and fell back to the first-visit one."""
    node = serializer().node(ft.FilledButton("Share", width=float("inf")))
    assert node["width"] == "inf"
    json.dumps(node, allow_nan=False)


def test_image_bytes_are_kept_once_by_key():
    images = {}
    s = serializer(images=images)
    first = s.node(ft.Image(src=b"webp"))
    again = s.node(ft.Image(src=b"webp"))
    other = s.node(ft.Image(src=b"png"))
    assert first["src"] == again["src"] == {"img": "i0"} and other["src"] == {"img": "i1"}
    assert images == {b"webp": "i0", b"png": "i1"}


def test_what_the_page_cannot_draw_is_dropped():
    class Opaque:
        pass

    @dataclasses.dataclass
    class Holder:
        thing: object = None
        size: int = 0

    assert serializer().value(Opaque()) is None
    assert serializer().node(Holder(Opaque(), 3)) == {"t": "Holder", "size": 3}


def test_hidden_parts_are_left_out():
    s = serializer()
    closed = s.node(ft.ExpansionTile(title=ft.Text("R1"), controls=[ft.Text("editors")]))
    opened = s.node(ft.ExpansionTile(title=ft.Text("R1"), controls=[ft.Text("editors")], expanded=True))
    assert "controls" not in closed and opened["controls"] == [{"t": "Text", "value": "editors"}]
    menu = s.node(ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[ft.PopupMenuItem(content=ft.Text("Delete"))]))
    assert "items" not in menu
    dropdown = s.node(
        ft.Dropdown(value="b", options=[ft.DropdownOption(key="a", text="A"), ft.DropdownOption(key="b", text="B")])
    )
    assert dropdown["options"] == [{"t": "DropdownOption", "key": "b", "text": "B"}]


def test_a_value_that_will_not_compare_counts_as_set():
    class Stubborn:
        def __eq__(self, other):
            raise TypeError("no")

    field = shell_mod.dataclasses.field(default=None)
    field.default = None
    assert shell_mod._is_default(field, Stubborn()) is False


def test_a_field_with_no_default_counts_as_set():
    assert shell_mod._is_default(shell_mod.dataclasses.field(), 0) is False


# ---- screens -----------------------------------------------------------------------
WRITERS: list[ShellWriter] = []


@pytest.fixture(autouse=True)
def _close_writers():
    """Each writer opens its own connection to the database: close them all."""
    yield
    while WRITERS:
        WRITERS.pop().close()


def writer(ctx, db, storage=None):
    WRITERS.append(ShellWriter(ctx, db, storage or Memory()))
    return WRITERS[-1]


async def test_every_tab_and_every_event_is_a_screen(ctx, seeded_db, sample_event):
    doc = json.loads(await writer(ctx, seeded_db).build())
    assert set(doc["views"]) == {*TABS, f"/event/{sample_event.id}"}
    assert doc["tabs"] == TABS and doc["lang"] == "en" and doc["v"] == shell_mod.VERSION
    assert doc["strings"] == {"opening": "Opening…"}
    assert doc["digests"].keys() == {str(sample_event.id)}


async def test_tiles_open_their_event_and_the_button_a_new_one(ctx, seeded_db, sample_event):
    doc = json.loads(await writer(ctx, seeded_db).build())
    navs = {node.get("nav") for node in walk(doc["views"]["/events"])} - {None}
    assert navs == {f"/event/{sample_event.id}", NEW_ROUTE}


@pytest.mark.regression
async def test_every_color_is_resolved(ctx, seeded_db, sample_event):
    """The page knows no theme tokens: anything left as one would paint in the browser's default."""
    doc = json.loads(await writer(ctx, seeded_db).build())
    for node in walk(doc["views"]):
        for key in ("color", "bgcolor", "collapsed_bgcolor"):
            value = node.get(key)
            if isinstance(value, str):
                assert value.startswith("#") or value in {"white", "black", "transparent"}, (key, value)


async def test_a_new_events_draft_is_left_out(ctx, seeded_db, sample_event):
    draft = ctx.new_event("locals", sample_event.date, None)
    doc = json.loads(await writer(ctx, seeded_db).build())
    assert f"/event/{draft.id}" not in doc["views"]


async def test_the_shell_speaks_the_apps_language_and_palette(ctx, seeded_db, page):
    from i18n import set_lang

    set_lang(page, "es")
    page.platform_brightness = ft.Brightness.DARK
    doc = json.loads(await writer(ctx, seeded_db).build())
    assert doc["lang"] == "es" and doc["dark"] is True
    assert doc["strings"]["opening"] == "Abriendo…"
    assert doc["scheme"]["bg"] == ctx.theme.dark.bg


async def test_only_changed_screens_are_built_again(ctx, seeded_db, sample_event, events, monkeypatch):
    other = events.create("Regional", "regional", sample_event.date, None)
    w = writer(ctx, seeded_db)
    await w.build()
    built = []
    real = shell_mod.build_view
    monkeypatch.setattr(shell_mod, "build_view", lambda c, route: built.append(route) or real(c, route))
    await w.build()
    assert built == TABS  # the tabs always; neither event changed
    built.clear()
    events.update(other.id, name="Regional #2")
    await w.build()
    assert built == [*TABS, f"/event/{other.id}"]


async def test_a_new_language_builds_every_screen_again(ctx, seeded_db, sample_event, page, monkeypatch):
    from i18n import set_lang

    w = writer(ctx, seeded_db)
    await w.build()
    built = []
    real = shell_mod.build_view
    monkeypatch.setattr(shell_mod, "build_view", lambda c, route: built.append(route) or real(c, route))
    set_lang(page, "gl")
    await w.build()
    assert f"/event/{sample_event.id}" in built


async def test_deleted_events_leave_the_shell(ctx, seeded_db, sample_event, events):
    w = writer(ctx, seeded_db)
    await w.build()
    events.delete(sample_event.id)
    doc = json.loads(await w.build())
    assert set(doc["views"]) == set(TABS) and doc["digests"] == {}


async def test_downloaded_portraits_travel_as_images(ctx, seeded_db, sample_event, monkeypatch):
    monkeypatch.setattr(shell_mod.portraits, "source", functools.cache(lambda code: b"webp-bytes"))
    doc = json.loads(await writer(ctx, seeded_db).build())
    assert list(doc["images"].values()) == ["d2VicC1ieXRlcw=="]  # one image, however many screens show it
    keys = {node["src"]["img"] for node in walk(doc["views"]) if isinstance(node.get("src"), dict)}
    assert keys == set(doc["images"])


def test_portrait_count_is_part_of_the_look(tmp_path, monkeypatch):
    assert shell_mod._portrait_files() == 0
    (shell_mod.portraits.cache_dir() / "OP01-001.webp").write_bytes(b"x")
    assert shell_mod._portrait_files() == 1
    monkeypatch.setattr(shell_mod.portraits, "cache_dir", lambda: tmp_path / "missing")
    assert shell_mod._portrait_files() == 0


def test_digest_is_stable_and_short():
    assert digest("a", 1) == digest("a", 1) != digest("a", 2)
    assert len(digest("a")) == 24


# ---- saving, and picking up after the last visit ----------------------------------------
async def test_refresh_saves_the_shell(ctx, seeded_db, sample_event):
    storage = Memory()
    w = writer(ctx, seeded_db, storage)
    await w.refresh()
    assert storage.saves == 1 and f"/event/{sample_event.id}" in json.loads(storage.saved)["views"]
    await w.refresh()  # the saved shell is read once, at the first refresh
    assert storage.saves == 2


async def test_a_new_visit_reuses_the_last_ones_screens(ctx, seeded_db, sample_event, monkeypatch):
    storage = Memory()
    await writer(ctx, seeded_db, storage).refresh()
    built = []
    real = shell_mod.build_view
    monkeypatch.setattr(shell_mod, "build_view", lambda c, route: built.append(route) or real(c, route))
    await writer(ctx, seeded_db, storage).refresh()  # the next visit's writer
    assert built == TABS


async def test_saved_images_keep_their_keys(ctx, seeded_db, sample_event, monkeypatch):
    monkeypatch.setattr(shell_mod.portraits, "source", functools.cache(lambda code: b"webp-bytes"))
    storage = Memory()
    await writer(ctx, seeded_db, storage).refresh()
    second = writer(ctx, seeded_db, storage)
    await second.refresh()
    assert second._images == {b"webp-bytes": "i0"}


@pytest.mark.parametrize(
    "saved",
    [None, "not json", json.dumps({"v": -1, "views": {}}), json.dumps({"v": shell_mod.VERSION, "digests": {"9": "x"}})],
)
async def test_a_missing_old_or_broken_saved_shell_builds_every_screen(ctx, seeded_db, sample_event, saved, caplog):
    storage = Memory(saved)
    await writer(ctx, seeded_db, storage).refresh()
    assert f"/event/{sample_event.id}" in json.loads(storage.saved)["views"]
    if saved == "not json":
        assert "not JSON" in caplog.text


async def test_a_failed_save_is_logged_not_raised(ctx, seeded_db, caplog):
    await writer(ctx, seeded_db, Memory(fail=RuntimeError("quota"))).refresh()
    assert "could not write the web shell" in caplog.text and "quota" in caplog.text


async def test_cancelling_a_refresh_is_not_swallowed(ctx, seeded_db):
    w = writer(ctx, seeded_db, Memory())

    async def cancelled():
        raise asyncio.CancelledError

    w.build = cancelled
    with pytest.raises(asyncio.CancelledError):
        await w.refresh()


@pytest.mark.regression
async def test_building_never_fires_the_apps_commit_hook(ctx, tmp_path):
    """Building the shell reads the database, and every read commits: through the app's commit hook each refresh
    scheduled the next, which cancelled the one running before it saved, so the shell was never written."""
    commits = []
    hooked = Database(tmp_path / "hooked.db", on_commit=lambda: commits.append(1))
    hooked.migrate()
    commits.clear()
    w = writer(AppContext(ctx.page, hooked), hooked)
    await w.build()
    assert commits == []
    WRITERS.remove(w)
    w.close()
    hooked.dispose()


async def test_a_burst_of_changes_refreshes_once(ctx, seeded_db, monkeypatch):
    monkeypatch.setattr(shell_mod, "REFRESH_DELAY", 0.01)
    storage = Memory()
    w = writer(ctx, seeded_db, storage)
    for _ in range(3):
        w.schedule()
    await asyncio.sleep(0)  # the restarts run on the loop
    await w._pending
    assert storage.saves == 1


@pytest.mark.regression
async def test_scheduling_from_outside_the_event_loop(ctx, seeded_db, monkeypatch):
    """flet runs a route change's handler outside the event loop, where there is no running loop to start a task
    on: the refresh it asked for was lost (and the pending one cancelled)."""
    monkeypatch.setattr(shell_mod, "REFRESH_DELAY", 0.01)
    storage = Memory()
    w = writer(ctx, seeded_db, storage)
    thread = threading.Thread(target=w.schedule)
    thread.start()
    thread.join()
    for _ in range(100):
        await asyncio.sleep(0.01)
        if storage.saves:
            break
    assert storage.saves == 1


async def test_close_stops_a_pending_refresh(ctx, seeded_db, monkeypatch):
    storage = Memory()
    w = writer(ctx, seeded_db, storage)
    WRITERS.remove(w)
    w.close()  # nothing pending: still fine
    w = writer(ctx, seeded_db, storage)
    WRITERS.remove(w)
    w.schedule()
    await asyncio.sleep(0)
    w.close()
    await asyncio.sleep(0)
    assert w._pending.cancelled() and storage.saves == 0


def test_shell_page_ignores_taps():
    page = ShellPage("es", None)
    assert page.navigate("/x") is None and page.run_task(print) is None
    assert page.show_dialog(object()) is None and page.update() is None
    from i18n import get_lang

    assert get_lang(page) == "es"


# ---- the first visit's shell ---------------------------------------------------------
def test_first_visit_shells_are_the_empty_app_light_and_dark(seeded_db):
    docs = default_documents(seeded_db, get_theme(None), "en")
    assert set(docs) == {"light", "dark"}
    light, dark = (json.loads(docs[name]) for name in ("light", "dark"))
    assert (light["dark"], dark["dark"]) == (False, True)
    assert set(light["views"]) == set(TABS) and light["images"] == {}
    texts = [n.get("value") for n in walk(light["views"]["/events"])]
    assert "No events yet" in texts


def test_shell_document_without_digests():
    ctx = AppContext(ShellPage("en", None), None)
    doc = json.loads(shell_document(ctx, ctx.scheme, {}, {}))
    assert doc["digests"] == {} and doc["views"] == {}
