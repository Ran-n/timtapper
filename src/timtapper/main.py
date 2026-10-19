#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.651174
Revised: 2026/10/15 01:26:05.128159

timtapper entry point (what `flet run` / `flet build` start). Opens the local
database, applies migrations, syncs the bundled leader list, shows the events
tab, then checks in the background for leaders from newly released sets.
Everything stays on the device: there is no server. In a browser (the web
build) the data folder is loaded from and saved to the browser's storage.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path

import flet as ft

from catalog import portraits
from catalog.repository import LeaderRepository, install_bundled
from core.logging import APP_LOGGER, LogTail, get_logger, setup_logging
from core.paths import ASSETS_DIR, data_dir, db_path
from core.web import IS_WEB, BrowserStore, RenderDeps, ShellStore, fetch_bytes
from db import Database
from db.database import MIGRATIONS_DIR
from db.diagnostics import startup_report
from i18n import set_lang, tr
from ui.app import install_routing
from ui.context import AppContext, saved_language
from ui.shell import ShellWriter

_log = get_logger("main")

# Desktop window shaped like a phone (logical dp of a typical 6.5" handset), so the
# mobile-first layout looks the same everywhere; mobile and web ignore these.
PHONE_WINDOW = {"width": 412, "height": 892, "min_width": 360, "min_height": 640}


def shape_window(page: ft.Page) -> None:
    window = page.window
    window.icon = str(ASSETS_DIR / "icon.ico")  # Windows only; other platforms take the built app's icon
    for name, value in PHONE_WINDOW.items():
        setattr(window, name, value)
    window.alignment = ft.Alignment.CENTER
    # flush now: awaiting a service (SharedPreferences) before the first update makes
    # the desktop client open at its default size and drop these settings
    page.update()


def open_database(on_commit: Callable[[], None] | None = None, path: Path | None = None) -> Database:
    """The app's database (at `path`: elsewhere than the data folder, as the web build's empty one), migrated, with
    the bundled leaders in."""
    db = Database(path or db_path(), on_commit=on_commit)
    db.migrate()
    install_bundled(LeaderRepository(db))
    return db


def render_deps() -> RenderDeps | None:
    """On the web, what drawing pictures needs that the app's archive leaves out (Pillow, the bundled portraits),
    fetched when needed; None elsewhere, where both are on disk."""
    return RenderDeps(lambda: portraits.fetch_listed(fetch_bytes)) if IS_WEB else None


async def open_browser_store() -> BrowserStore:
    store = BrowserStore(data_dir())
    await store.open()
    return store


def _run_all(hooks: list[Callable[[], None]]) -> None:
    for hook in hooks:
        hook()


def _and_then(first: Callable[..., None] | None, then: Callable[[], None]) -> Callable[..., None]:
    """A handler that runs `first` (if any) with whatever it's given, then `then`."""

    def both(*args) -> None:
        if first is not None:
            first(*args)
        then()

    return both


def start_web_shell(
    ctx: AppContext, shell: ShellWriter, shell_store: ShellStore, on_commit: list[Callable[[], None]]
) -> None:
    """Tell the page the app is on screen, and keep the shell it paints on the next visit up to date: after every
    change to the data, the language or the theme, on every screen change (leaving a new event's screen keeps it or
    drops it, without a commit when kept), and once now (the leaders may have changed since)."""
    on_commit.append(shell.schedule)
    ctx.on_appearance_change = _and_then(ctx.on_appearance_change, shell.schedule)
    ctx.page.on_route_change = _and_then(ctx.page.on_route_change, shell.schedule)
    try:
        shell_store.announce_ready(ctx.page.route)
    except Exception:
        _log.exception("could not tell the page the app is ready; its shell stays until reloaded")
    shell.schedule()


def show_startup_failure(page: ft.Page, exc: Exception, tail: LogTail) -> None:
    """The error in the page's language, then what the app could see (selectable, so it can be copied off a phone;
    left in English, for whoever reads it to fix the app)."""
    report = startup_report(db_path(), MIGRATIONS_DIR, tail.lines)
    _ = tr(page)
    page.add(
        ft.SafeArea(
            ft.Column(
                [
                    ft.Text(
                        _("timtapper could not open its database: {error}").format(error=f"{type(exc).__name__}: {exc}")
                    ),
                    ft.Text(report, selectable=True, size=12, font_family="monospace", data="startup-report"),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )
    )


async def main(page: ft.Page) -> None:
    page.title = "timtapper"
    shape_window(page)
    tail = LogTail()
    on_commit: list[Callable[[], None]] = []  # the web build's: save to the browser's storage, refresh the shell
    try:
        with tail.attached("alembic", APP_LOGGER):
            store = await open_browser_store() if IS_WEB else None
            if store is not None:
                on_commit.append(store.changed)
            db = open_database(partial(_run_all, on_commit) if store else None)
    except Exception as exc:
        _log.exception("could not open the database")
        set_lang(page, await saved_language())
        show_startup_failure(page, exc, tail)
        return

    ctx = AppContext(page, db)
    ctx.render_deps = render_deps()
    await ctx.load_prefs()
    if store is not None:
        store.on_save_failed = lambda: ctx.notify(
            ctx._("Could not save to this browser's storage — export a backup before closing the page"), error=True
        )

    shell_store = ShellStore() if store is not None else None
    shell = ShellWriter(ctx, db, shell_store) if shell_store is not None else None

    def on_disconnect(_e) -> None:
        try:
            ctx.drop_untouched_draft()
        except Exception:
            _log.exception("could not drop the untouched draft event")
        finally:
            if shell is not None:
                shell.close()
            db.dispose()  # whatever happened above, the database is closed

    page.on_disconnect = on_disconnect
    page.on_close = on_disconnect
    route_change = install_routing(ctx)
    _log.info("started (%d leaders, db %s)", len(ctx.leaders), db.path)
    route_change()
    if shell is not None:
        start_web_shell(ctx, shell, shell_store, on_commit)
    if ctx.render_deps is not None:
        ctx.render_deps.prefetch()
    page.run_task(ctx.leader_updates.run_if_due)


def run() -> None:
    setup_logging()
    ft.run(main, assets_dir="assets")


if __name__ == "__main__":
    run()
