#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.139229
Revised: 2026/10/13 01:17:15.010020

Settings tab: language, theme, leader catalogue refresh, backup export/import, about.
"""

import asyncio
import datetime as dt
from pathlib import Path

import flet as ft

from backup.json_backup import BackupError, export_backup, import_backup
from catalog.optcgapi import CatalogError
from core.logging import get_logger
from core.paths import temp_file
from core.version import VERSION
from i18n import LANGUAGES
from ui.context import AppContext
from ui.theme import FONT_SEMIBOLD, THEMES, AppTheme, is_dark
from ui.widgets import caption, card, confirm, flag, logo, section, update_if_mounted

_log = get_logger("ui.settings")


def mode_segment(value: str, label: str, icon: ft.IconData) -> ft.Segment:
    """One brightness option. The label stays on one line and may run into the segment's side
    padding: Flet drops a custom segment padding, and Material's 24 dp leaves "Sistema" only
    ~45 dp beside its icon at the 360 dp minimum width, which wrapped it mid-word."""
    return ft.Segment(
        value=value, label=ft.Text(label, size=13, no_wrap=True, overflow=ft.TextOverflow.VISIBLE), icon=icon
    )


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
            result = await self.ctx.leader_updates.run()
        except CatalogError as exc:
            _log.warning("leader update failed: %s", exc)
            self.ctx.notify(_("Could not download leaders — check your connection and try again"), error=True)
        except Exception as exc:
            _log.exception("leader update failed")
            self.ctx.notify(_("Could not update leaders ({error})").format(error=type(exc).__name__), error=True)
        else:
            message = _("Leaders updated: {added} new, {updated} changed").format(
                added=result.added, updated=result.updated
            )
            if result.failed_portraits:
                message += " · " + _("{n} pictures could not be downloaded").format(n=result.failed_portraits)
            self.ctx.notify(message, error=bool(result.failed_portraits))
        finally:
            self.busy = False
            self.refresh()

    # ---- backup --------------------------------------------------------
    async def export(self, _e) -> None:
        _ = self.ctx._
        events, leaders = self.ctx.events.list(), self.ctx.leaders_by_id

        def write() -> Path:
            path = temp_file(f"timtapper-backup-{dt.date.today().isoformat()}.json")
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
            try:
                data = await asyncio.to_thread(Path(picked.path).read_bytes)
            except OSError:
                _log.warning("could not read %s", picked.path, exc_info=True)
        if not data:
            self.ctx.notify(_("Could not read that file"), error=True)
            return

        def do_import() -> None:
            try:
                n = import_backup(self.ctx.db, data)
            except BackupError as exc:
                _log.warning("backup import rejected: %s", exc)
                self.ctx.notify(_("Not a valid backup: {error}").format(error=exc.translated(_)), error=True)
                return
            except Exception as exc:  # the import runs in one transaction: nothing was changed
                _log.exception("backup import failed")
                self.ctx.notify(
                    _("Could not restore the backup ({error})").format(error=type(exc).__name__), error=True
                )
                return
            self.ctx.invalidate_leaders()
            self.refresh()  # the backup may have brought leaders this install didn't list: the count changes
            self.ctx.notify(_("Events restored: {n}").format(n=n))

        confirm(
            self.ctx.page,
            _("Restore this backup?"),
            _("All your current events will be replaced by the ones in the backup."),
            _("Restore"),
            _("Cancel"),
            do_import,
        )

    # ---- appearance ----------------------------------------------------
    def _swatch(self, theme: AppTheme) -> ft.Control:
        """A theme preview drawn in its own colors (in the brightness now on screen)."""
        ctx = self.ctx
        s = theme.scheme(is_dark(ctx.page, ctx.theme_mode))
        selected = theme.key == ctx.theme.key

        async def choose(_e) -> None:
            await ctx.change_theme(theme.key)

        dots = ft.Row(
            [
                ft.Container(width=14, height=14, border_radius=7, bgcolor=c)
                for c in (s.primary, s.secondary, s.tertiary, s.success, s.error)
            ],
            spacing=4,
        )
        return ft.Container(
            col={"xs": 6, "sm": 4},
            height=84,
            padding=12,
            border_radius=16,
            bgcolor=s.bg,
            border=ft.Border.all(2.5 if selected else 1, ctx.scheme.primary if selected else s.outline),
            ink=True,
            on_click=choose,
            data=f"theme-{theme.key}",
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                theme.label(ctx._),
                                font_family=FONT_SEMIBOLD,
                                color=s.fg,
                                expand=True,
                            ),
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=18, color=s.primary, visible=selected),
                        ],
                    ),
                    dots,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    # ---- layout --------------------------------------------------------
    def _controls(self) -> list[ft.Control]:
        _ = self.ctx._

        async def set_lang(e) -> None:
            await self.ctx.change_language(e.control.value)

        async def set_mode(e) -> None:
            await self.ctx.change_mode(e.control.selected[0])

        leader_count = len(self.ctx.leaders)
        return [
            section(_("Appearance")),
            ft.Dropdown(
                label=_("Language"),
                value=self.ctx.lang,
                leading_icon=flag(self.ctx.lang),
                options=[ft.DropdownOption(key=k, text=name, leading_icon=flag(k)) for k, name in LANGUAGES.items()],
                on_select=set_lang,
                width=float("inf"),
                data="language",
            ),
            caption(_("Theme")),
            ft.ResponsiveRow([self._swatch(t) for t in THEMES.values()], spacing=10, run_spacing=10),
            ft.SegmentedButton(
                segments=[
                    mode_segment("system", _("System"), ft.Icons.BRIGHTNESS_AUTO),
                    mode_segment("light", _("Light"), ft.Icons.LIGHT_MODE),
                    mode_segment("dark", _("Dark"), ft.Icons.DARK_MODE),
                ],
                selected=[self.ctx.theme_mode],
                on_change=set_mode,
                width=float("inf"),
                data="mode",
            ),
            section(_("Leaders")),
            ft.Text(
                _("{n} leaders in the catalogue. New sets are added automatically.").format(n=leader_count),
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
            card(
                ft.Row(
                    [
                        logo(56),
                        ft.Column(
                            [
                                ft.Text(f"timtapper {VERSION}", font_family=FONT_SEMIBOLD),
                                caption(
                                    _(
                                        "Fan-made tracker. Not affiliated with or endorsed by Bandai, Eiichiro Oda "
                                        "or Shueisha. Leader data from optcgapi.com."
                                    )
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            ),
            ft.Container(height=24),
        ]

    def build(self) -> ft.Control:
        self.body.controls = self._controls()
        return self.body
