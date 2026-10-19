#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:11:03.555531
Revised: 2026/10/15 01:12:58.361062

Entry point of the driven web and Android builds (scripts/build_driven.py): the real app on the demo data
(scripts/demo_driver.py), taking its commands from the rendered-test harness instead of a person. It polls the
harness over HTTP: on the web the harness serves the site, so it asks its own origin; on Android it asks
127.0.0.1:8765, which `adb reverse` maps to the harness on the host. Never shipped: release builds start main.py.
"""

import asyncio
import json
import urllib.request

import flet as ft
from demo_driver import TODAY, Demo, answer

from core.logging import get_logger, setup_logging
from core.web import IS_WEB

_log = get_logger("scripts.driven_main")

TITLE = "timtapper driven"
# Android: the harness listens on the host and `adb reverse` maps the phone's port to it
DRIVER_PORT = 8765
POLL_PATH = "/driver"
POLL_TIMEOUT = 60  # seconds; the harness answers an idle poll after about 20
RETRY_DELAY = 1.0


def driver_url() -> str:
    if IS_WEB:  # pragma: no cover - only inside Pyodide: the harness serves the site itself, same origin
        # run_js, not the js module: a Pyodide made to be snapshotted (scripts/prestart/worker.js) fails reading
        # js.location ("Illegal invocation")
        from pyodide.code import run_js

        return f"{run_js('location.origin')}{POLL_PATH}"
    return f"http://127.0.0.1:{DRIVER_PORT}{POLL_PATH}"


def _post_blocking(url: str, body: dict) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=POLL_TIMEOUT) as response:
        return json.loads(response.read())


async def post(url: str, body: dict) -> dict:
    """POST `body` as JSON and return the JSON reply: the browser's fetch on the web (Pyodide has no sockets),
    a plain HTTP request off the event loop elsewhere."""
    if IS_WEB:  # pragma: no cover - only inside Pyodide
        from pyodide.http import pyfetch

        response = await pyfetch(
            url, method="POST", body=json.dumps(body), headers={"Content-Type": "application/json"}
        )
        return await response.json()
    return await asyncio.to_thread(_post_blocking, url, body)


async def poll(demo: Demo, url: str) -> None:
    """Send the last reply, get the next command, until "quit". Each poll carries the reply to the command before it
    (the first: the ready message), so the harness sees every reply in order. A failed poll is logged and sent again:
    the harness may not be listening yet."""
    commands = demo.commands()
    body: dict = {"seq": 0, "reply": {"ok": True, "ready": True, "newest": demo.newest}}
    while True:
        try:
            request = await post(url, body)
        except Exception as exc:
            _log.warning("driver poll to %s failed (%s: %s); retrying", url, type(exc).__name__, exc)
            await asyncio.sleep(RETRY_DELAY)
            continue
        seq = request.pop("seq", None)
        if request.get("cmd") == "idle":
            body = {"seq": None}
            continue
        if request.get("cmd") == "quit":
            await post(url, {"seq": seq, "reply": {"ok": True}})
            _log.info("driver quit")
            return
        body = {"seq": seq, "reply": await answer(commands, request)}


async def main(page: ft.Page) -> None:
    demo = Demo(page, TODAY, TITLE)
    demo.show("/events")
    url = driver_url()
    _log.info("driven app ready; polling %s", url)
    page.run_task(poll, demo, url)


if __name__ == "__main__":
    setup_logging()
    ft.run(main, assets_dir="assets")
