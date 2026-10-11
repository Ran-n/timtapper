#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.676210
Revised: 2026/10/11 16:27:23.334484

Screen routing. Tabs (/events, /stats, /settings) replace the view stack;
/event/<id> is pushed on top so Android's back button returns to the list.
"""

import threading
from collections.abc import Callable

import flet as ft

from core.logging import get_logger
from events.repository import EventError
from ui import events_view
from ui.context import AppContext
from ui.event_view import EventScreen
from ui.settings_view import SettingsScreen
from ui.stats_view import StatsScreen

_log = get_logger("ui.app")

TABS = ["/events", "/stats", "/settings"]


def navbar(ctx: AppContext, route: str) -> ft.NavigationBar:
    _ = ctx._
    return ft.NavigationBar(
        selected_index=TABS.index(route),
        on_change=lambda e: ctx.navigate(TABS[e.control.selected_index]),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.STYLE_OUTLINED, selected_icon=ft.Icons.STYLE, label=_("Events")),
            ft.NavigationBarDestination(
                icon=ft.Icons.INSIGHTS_OUTLINED, selected_icon=ft.Icons.INSIGHTS, label=_("Stats")
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label=_("Settings")
            ),
        ],
    )


def _scroll_body(controls: list[ft.Control] | ft.Control) -> list[ft.Control]:
    content = controls if isinstance(controls, ft.Control) else ft.Column(controls, spacing=10)
    return [ft.Container(content=content, padding=ft.Padding(16, 8, 16, 88))]


def build_view(ctx: AppContext, route: str) -> ft.View:
    _ = ctx._
    if route.startswith("/event/"):
        try:
            screen = EventScreen(ctx, int(route.removeprefix("/event/")))
        except (ValueError, EventError):
            _log.warning("route %s points at no event — back to the list", route)
            ctx.notify(_("That event no longer exists"), error=True)
            return build_view(ctx, "/events")
        return ft.View(
            route=route,
            scroll=ft.ScrollMode.AUTO,
            appbar=ft.AppBar(
                title=ft.Text(_("Event")),
                actions=[
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE,
                        tooltip=_("Delete event"),
                        on_click=lambda _e: screen.delete_event(),
                        data="delete-event",
                    )
                ],
            ),
            controls=_scroll_body(screen.build()),
        )
    if route == "/stats":
        title, body, fab = _("Stats"), StatsScreen(ctx).build(), None
    elif route == "/settings":
        title, body, fab = _("Settings"), SettingsScreen(ctx).build(), None
    else:
        route = "/events"
        controls, fab = events_view.build(ctx)
        title, body = _("Events"), controls
    return ft.View(
        route=route,
        scroll=ft.ScrollMode.AUTO,
        appbar=ft.AppBar(title=ft.Text(title)),
        navigation_bar=navbar(ctx, route),
        floating_action_button=fab,
        controls=_scroll_body(body),
    )


def install_routing(ctx: AppContext) -> Callable[..., None]:
    """Wire routing/back handling; returns the route handler so main() can render the first screen."""
    page = ctx.page

    def route_change(_e=None) -> None:
        route = page.route if page.route in TABS or page.route.startswith("/event/") else "/events"
        view = build_view(ctx, route)
        if view.route in TABS:
            page.views.clear()  # tabs are lateral: don't grow the back stack
        elif page.views and page.views[-1].route == view.route:
            page.views.pop()
        page.views.append(view)
        page.update()

    back = {"armed": False}

    async def view_pop(_e) -> None:
        if len(page.views) > 1:
            page.views.pop()
            page.navigate(page.views[-1].route)
            return
        if back["armed"]:
            _log.info("back pressed twice — closing")
            await page.window.destroy()
            return
        back["armed"] = True
        ctx.notify(ctx._("Press back again to exit"))
        timer = threading.Timer(2.0, lambda: back.update(armed=False))
        timer.daemon = True  # never hold up process exit
        timer.start()

    def language_changed() -> None:
        if page.views:
            page.views[-1] = build_view(ctx, page.views[-1].route)
            page.update()

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    ctx.on_language_change = language_changed
    return route_change
