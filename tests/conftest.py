#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:45.015285
Revised: 2026/10/11 16:27:25.456085

Shared fixtures. Every DB test runs against a real, freshly migrated SQLite
file (never mocks), seeded with the bundled leader catalogue.
"""

import datetime as dt
from types import SimpleNamespace

import pytest

from catalog.repository import LeaderRepository, load_bundled
from db import Database
from events.repository import EventRepository


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    """Keep every file the app writes inside the test's tmp dir."""
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("FLET_APP_STORAGE_TEMP", str(tmp_path / "temp"))


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.migrate()
    yield database
    database.dispose()


@pytest.fixture
def seeded_db(db):
    LeaderRepository(db).upsert(load_bundled())
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
    events.update_round(r1.id, result="W", went_first=True, won_die_roll=True)
    events.update_round(r2.id, result="L", went_first=False, won_die_roll=False)
    events.update_round(r3.id, result="W")
    return events.get(ev.id)


class FakePage(SimpleNamespace):
    """Just enough of ft.Page for building screens outside a running app."""

    def __init__(self):
        super().__init__(dialogs=[], routes=[], views=[], route="/", updates=0)

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


@pytest.fixture
def ctx(page, seeded_db):
    from ui.context import AppContext

    return AppContext(page, seeded_db)
