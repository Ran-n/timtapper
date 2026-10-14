#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:12:48.505693
Revised: 2026/10/14 01:08:29.351009

A local stand-in for the static hosts the web build is published to, for the tests: the site under /timtapper/,
plus the channel a driven app (scripts/driven_main.py) polls for its commands. The web tests serve the built site
with it; the Android tests only the channel, which `adb reverse` makes reachable from the phone.
"""

import functools
import http.server
import json
import queue
import threading
from pathlib import Path

from core.logging import get_logger

_log = get_logger("scripts.serve_site")

PREFIX = "/timtapper"  # [tool.flet.web] base_url: where GitHub Pages and Codeberg Pages serve the site
DRIVER_PATH = "/driver"
IDLE_AFTER = 20.0  # seconds a poll waits for a command before it's told to poll again


class DriverError(RuntimeError):
    """The driven app failed a command, or didn't answer in time."""


class DriverChannel:
    """Commands from the harness to a driven app that polls for them (scripts/driven_main.py), and its replies.
    Each command carries a sequence number; the app's next poll carries the reply to it."""

    def __init__(self, idle_after: float = IDLE_AFTER) -> None:
        self.idle_after = idle_after
        self._commands: queue.Queue[dict] = queue.Queue()
        self._replies: dict[int, dict] = {}
        self._arrived = threading.Condition()
        self._seq = 0

    def poll(self, body: dict) -> dict:
        """One poll from the app: file the reply it carries, then hand it the next command (or "idle")."""
        seq = body.get("seq")
        if seq is not None:
            with self._arrived:
                self._replies[seq] = body.get("reply", {})
                self._arrived.notify_all()
        try:
            return self._commands.get(timeout=self.idle_after)
        except queue.Empty:
            return {"cmd": "idle"}

    def send(self, cmd: str, timeout: float, **args) -> dict:
        """Queue a command and wait for its reply."""
        self._seq += 1
        self._commands.put({"cmd": cmd, "seq": self._seq, **args})
        return self.wait(self._seq, timeout)

    def wait(self, seq: int, timeout: float) -> dict:
        """The reply to command `seq` (0: the ready message the app sends once it has started)."""
        with self._arrived:
            if not self._arrived.wait_for(lambda: seq in self._replies, timeout):
                raise DriverError(f"no reply to command {seq} within {timeout:.0f}s")
            return self._replies.pop(seq)


class SiteServer:
    """Serves `site` under /timtapper/ as the static hosts do (anything else is a 404), and, given a channel, takes
    a driven app's polls at /driver. Binds 127.0.0.1 on `port` (0: any free one)."""

    def __init__(self, site: Path | None = None, channel: DriverChannel | None = None, port: int = 0) -> None:
        self.site = site
        self.channel = channel
        server = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def translate_path(self, path: str) -> str:
                if server.site is None or not path.startswith(PREFIX):
                    return super().translate_path("/__missing__")
                return super().translate_path(path[len(PREFIX) :])

            def do_POST(self) -> None:  # noqa: N802 - http.server's naming
                if server.channel is None or self.path != DRIVER_PATH:
                    self.send_error(404)
                    return
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                payload = json.dumps(server.channel.poll(body)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt: str, *args) -> None:
                _log.debug("%s %s", self.address_string(), fmt % args)

        directory = str(site) if site is not None else "."
        self._httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", port), functools.partial(Handler, directory=directory)
        )
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._httpd.server_port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}{PREFIX}/"

    def start(self) -> SiteServer:
        self._thread.start()
        _log.info("serving %s on port %d", self.site or "the driver channel", self.port)
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=10)
