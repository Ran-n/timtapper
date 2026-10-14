#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:45.015285
Revised: 2026/10/14 10:32:27.275289

Shared fixtures. Every DB test runs against a real, freshly migrated SQLite
file (never mocks), seeded with the bundled leader catalogue.
"""

import datetime as dt
from types import SimpleNamespace

import pytest

from catalog import portraits
from catalog.repository import LeaderRepository, install_bundled
from db import Database
from events.repository import EventRepository


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    """Keep every file the app writes inside the test's tmp dir."""
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("FLET_APP_STORAGE_TEMP", str(tmp_path / "temp"))
    portraits.source.cache_clear()  # its cache would otherwise leak one test's data dir into the next
    yield
    portraits.source.cache_clear()


def uses_playwright(item) -> bool:
    """Whether a test pulls in the shared sync Playwright: directly, or as the rendered `app` fixture's web target."""
    callspec = getattr(item, "callspec", None)
    return "playwright" in getattr(item, "fixturenames", ()) or (
        callspec is not None and callspec.params.get("app") == "web"
    )


def pytest_collection_modifyitems(config, items):
    """Run every test that uses the shared sync Playwright last: its event loop keeps running in this thread until
    the session ends, so an asyncio test after it failed ("Runner.run() cannot be called from a running event loop")
    whenever `-m live` or a mixed run reached the web target first."""
    items.sort(key=uses_playwright)  # stable: keeps the collected order within each group


@pytest.fixture(scope="session")
def playwright():
    """One sync Playwright for the whole run, shared by the rendered web target and tests/web: a second
    sync_playwright() in this thread while the first still runs fails ("Sync API inside the asyncio loop"), so
    tests/web errored whenever the rendered web tests had run before it."""
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        yield p


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.migrate()
    yield database
    database.dispose()


@pytest.fixture
def seeded_db(db):
    install_bundled(LeaderRepository(db))
    return db


@pytest.fixture
def leaders(seeded_db):
    return LeaderRepository(seeded_db)


@pytest.fixture
def events(seeded_db):
    return EventRepository(seeded_db)


@pytest.fixture
def leader_ids(leaders):
    """A few real leader ids, stable across tests (sorted by code)."""
    return [ld.id for ld in sorted(leaders.all(), key=lambda ld: ld.code)][:6]


@pytest.fixture
def sample_event(events, leader_ids):
    """Locals with 3 decided rounds (W first, L second, W unknown order) and one pending."""
    ev = events.create("Sunday locals", "locals", dt.date(2026, 10, 5), leader_ids[0])
    r1 = events.add_round(ev.id, leader_ids[1])
    r2 = events.add_round(ev.id, leader_ids[2])
    r3 = events.add_round(ev.id, leader_ids[1])
    events.add_round(ev.id, leader_ids[3])
    events.update_game(r1.id, 1, result="W", went_first=True, chose_turn=True)
    events.update_game(r2.id, 1, result="L", went_first=False, chose_turn=False)
    events.update_game(r3.id, 1, result="W")
    return events.get(ev.id)


class FakePage(SimpleNamespace):
    """Just enough of ft.Page for building screens outside a running app."""

    def __init__(self):
        super().__init__(
            dialogs=[], routes=[], views=[], route="/", updates=0, tasks=[], window=SimpleNamespace(icon=None)
        )

    def run_task(self, handler, *args):
        self.tasks.append(handler)

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return self.dialogs.pop() if self.dialogs else None

    def navigate(self, route):
        self.routes.append(route)

    def update(self, *controls):
        self.updates += 1


@pytest.fixture
def page():
    return FakePage()


class MemoryPrefs:
    """In-memory stand-in for ft.SharedPreferences (instances share one store, like the real thing)."""

    def __init__(self, store: dict):
        self.store = store

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value
        return True


@pytest.fixture
def prefs(monkeypatch):
    """Saved preferences as a plain dict."""
    import flet as ft

    store: dict = {}
    monkeypatch.setattr(ft, "SharedPreferences", lambda: MemoryPrefs(store))
    return store


@pytest.fixture
def ctx(page, seeded_db):
    from ui.context import AppContext

    return AppContext(page, seeded_db)
