#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.651174
Revised: 2026/10/11 17:22:24.818267

timtapper entry point (what `flet run` / `flet build` start). Opens the local
database, applies migrations, syncs the bundled leader list, shows the events
tab, then checks in the background for leaders from newly released sets.
Everything stays on the device: there is no server.
"""

import flet as ft

from catalog.repository import LeaderRepository, load_bundled
from core.logging import get_logger, setup_logging
from core.paths import ASSETS_DIR, db_path
from db import Database
from ui.app import install_routing
from ui.context import AppContext

_log = get_logger("main")


def open_database() -> Database:
    db = Database(db_path())
    db.migrate()
    LeaderRepository(db).upsert(load_bundled())
    return db


async def main(page: ft.Page) -> None:
    page.title = "timtapper"
    page.window.icon = str(ASSETS_DIR / "icon.ico")  # Windows only; other platforms take the built app's icon
    try:
        db = open_database()
    except Exception as exc:
        _log.exception("could not open the database")
        page.add(ft.SafeArea(ft.Text(f"timtapper could not open its database: {type(exc).__name__}: {exc}")))
        return

    ctx = AppContext(page, db)
    await ctx.load_prefs()

    def on_disconnect(_e) -> None:
        db.dispose()

    page.on_disconnect = on_disconnect
    page.on_close = on_disconnect
    route_change = install_routing(ctx)
    _log.info("started (%d leaders, db %s)", len(ctx.leaders), db.path)
    route_change()
    page.run_task(ctx.leader_updates.run_if_due)


def run() -> None:
    setup_logging()
    ft.run(main, assets_dir="assets")


if __name__ == "__main__":
    run()
