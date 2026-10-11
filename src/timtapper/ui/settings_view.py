#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.139229
Revised: 2026/10/11 16:27:23.709973

Settings tab: language, theme, leader catalogue refresh, backup export/import, about.
"""

import asyncio
import datetime as dt
from pathlib import Path

import flet as ft

from backup.json_backup import BackupError, export_backup, import_backup
from catalog.optcgapi import CatalogError, fetch_leaders
from core.logging import get_logger
from core.paths import temp_dir
from core.version import VERSION
from i18n import LANGUAGES
from ui.context import AppContext
from ui.widgets import confirm, section, update_if_mounted

_log = get_logger("ui.settings")


class SettingsScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.body = ft.Column(spacing=10)
        self.busy = False

    def refresh(self) -> None:
        self.body.controls = self._controls()
        update_if_mounted(self.body)

    # ---- leaders -------------------------------------------------------
    async def update_leaders(self, _e) -> None:
        _ = self.ctx._
        self.busy = True
        self.refresh()
        try:
            records = await asyncio.to_thread(fetch_leaders)
            added, updated = await asyncio.to_thread(self.ctx.leader_repo.upsert, records)
        except CatalogError:
            self.ctx.notify(_("Could not download leaders — check your connection and try again"), error=True)
        else:
            self.ctx.invalidate_leaders()
            self.ctx.notify(_("Leaders updated: {added} new, {updated} changed").format(added=added, updated=updated))
        finally:
            self.busy = False
            self.refresh()

    # ---- backup --------------------------------------------------------
    async def export(self, _e) -> None:
        _ = self.ctx._
        events, leaders = self.ctx.events.list(), self.ctx.leaders_by_id

        def write():
            path = temp_dir() / f"timtapper-backup-{dt.date.today().isoformat()}.json"
            path.write_bytes(export_backup(events, leaders))
            return path

        await self.ctx.share_file(write, title=_("timtapper backup"), mime_type="application/json")

    async def pick_import(self, _e) -> None:
        _ = self.ctx._
        try:
            files = await ft.FilePicker().pick_files(
                dialog_title=_("Choose a backup file"),
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
                with_data=True,
            )
        except Exception as exc:
            _log.exception("file picker failed")
            self.ctx.notify(_("Could not open the file picker ({error})").format(error=type(exc).__name__), error=True)
            return
        if not files:
            return
        picked = files[0]
        data = picked.bytes
        if data is None and picked.path:
            data = await asyncio.to_thread(Path(picked.path).read_bytes)
        if not data:
            self.ctx.notify(_("Could not read that file"), error=True)
            return

        def do_import() -> None:
            try:
                n = import_backup(self.ctx.db, data)
            except BackupError as exc:
                _log.warning("backup import rejected: %s", exc)
                self.ctx.notify(_("Not a valid backup: {error}").format(error=exc), error=True)
                return
            self.ctx.invalidate_leaders()
            self.ctx.notify(_("Events restored: {n}").format(n=n))

        confirm(
            self.ctx.page,
            _("Restore this backup?"),
            _("All your current events will be replaced by the ones in the backup."),
            _("Restore"),
            _("Cancel"),
            do_import,
        )

    # ---- layout --------------------------------------------------------
    def _controls(self) -> list[ft.Control]:
        _ = self.ctx._

        async def set_lang(e) -> None:
            await self.ctx.change_language(e.control.value)

        async def set_theme(e) -> None:
            await self.ctx.change_theme(e.control.selected[0])

        leader_count = len(self.ctx.leaders)
        return [
            section(_("Appearance")),
            ft.Dropdown(
                label=_("Language"),
                value=self.ctx.lang,
                options=[ft.DropdownOption(key=k, text=name) for k, name in LANGUAGES.items()],
                on_select=set_lang,
                width=float("inf"),
                data="language",
            ),
            ft.SegmentedButton(
                segments=[
                    ft.Segment(value="system", label=_("System"), icon=ft.Icons.BRIGHTNESS_AUTO),
                    ft.Segment(value="light", label=_("Light"), icon=ft.Icons.LIGHT_MODE),
                    ft.Segment(value="dark", label=_("Dark"), icon=ft.Icons.DARK_MODE),
                ],
                selected=[self.ctx.theme_mode],
                on_change=set_theme,
                data="theme",
            ),
            section(_("Leaders")),
            ft.Text(
                _("{n} leaders in the catalogue. Update after a new set releases.").format(n=leader_count),
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([
                ft.FilledTonalButton(
                    content=_("Updating…") if self.busy else _("Update leaders"),
                    icon=ft.Icons.CLOUD_DOWNLOAD,
                    disabled=self.busy,
                    on_click=self.update_leaders,
                    data="update-leaders",
                ),
                ft.ProgressRing(width=20, height=20, visible=self.busy),
            ]),
            section(_("Backup")),
            ft.Text(
                _("Your data only lives on this device. Export a backup now and then so you never lose it."),
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row(
                [
                    ft.FilledTonalButton(
                        content=_("Export backup"), icon=ft.Icons.UPLOAD_FILE, on_click=self.export, data="export"
                    ),
                    ft.OutlinedButton(
                        content=_("Import backup"), icon=ft.Icons.DOWNLOAD, on_click=self.pick_import, data="import"
                    ),
                ],
                wrap=True,
            ),
            section(_("About")),
            ft.Text(f"timtapper {VERSION}"),
            ft.Text(
                _(
                    "Fan-made tracker. Not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. "
                    "Leader data from optcgapi.com."
                ),
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Container(height=24),
        ]

    def build(self) -> ft.Control:
        self.body.controls = self._controls()
        return self.body
