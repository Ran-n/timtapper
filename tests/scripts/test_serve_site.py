#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:45:47.987338
Revised: 2026/10/14 01:08:30.495036

The local stand-in for the static hosts (scripts/serve_site.py): the site under /timtapper/ only, and the channel
a driven app polls for its commands, over real HTTP.
"""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from serve_site import DriverChannel, DriverError, SiteServer  # noqa: E402


def post(url: str, body: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.fixture
def site(tmp_path):
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf-8")
    return tmp_path


# ---- the channel ------------------------------------------------------------------------
def test_an_idle_poll_is_told_to_poll_again():
    assert DriverChannel(idle_after=0.05).poll({"seq": None}) == {"cmd": "idle"}


def test_the_ready_message_is_the_reply_to_command_0():
    channel = DriverChannel(idle_after=0.05)
    channel.poll({"seq": 0, "reply": {"ok": True, "ready": True, "newest": 5}})
    assert channel.wait(0, timeout=1) == {"ok": True, "ready": True, "newest": 5}


def test_a_command_goes_out_with_its_number_and_its_reply_comes_back():
    channel = DriverChannel(idle_after=5)

    def app():  # the driven app: one poll fetches the command, the next carries its reply
        command = channel.poll({"seq": None})
        channel.poll({"seq": command["seq"], "reply": {"ok": True, "result": command["route"]}})

    threading.Thread(target=app, daemon=True).start()
    assert channel.send("show", timeout=5, route="/stats") == {"ok": True, "result": "/stats"}


def test_no_reply_in_time_raises():
    with pytest.raises(DriverError, match="no reply to command 1"):
        DriverChannel(idle_after=0.05).send("state", timeout=0.1)


# ---- the server -------------------------------------------------------------------------
def test_serves_the_site_under_its_base_path_only(site):
    server = SiteServer(site).start()
    try:
        with urllib.request.urlopen(server.url + "index.html", timeout=10) as response:
            assert response.read() == b"<html>app</html>"
        with pytest.raises(urllib.error.HTTPError) as outside:
            urllib.request.urlopen(f"http://127.0.0.1:{server.port}/index.html", timeout=10)
        assert outside.value.code == 404  # as on GitHub Pages: the app lives under /timtapper/
    finally:
        server.stop()


def test_takes_polls_at_driver(site):
    channel = DriverChannel(idle_after=0.05)
    server = SiteServer(site, channel).start()
    try:
        assert post(f"http://127.0.0.1:{server.port}/driver", {"seq": 0, "reply": {"ok": True}}) == {"cmd": "idle"}
        assert channel.wait(0, timeout=1) == {"ok": True}
    finally:
        server.stop()


def test_without_a_channel_polls_are_refused(site):
    server = SiteServer(site).start()
    try:
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(f"http://127.0.0.1:{server.port}/driver", {"seq": None})
        assert refused.value.code == 404
    finally:
        server.stop()


def test_without_a_site_nothing_is_served():
    server = SiteServer(None, DriverChannel()).start()
    try:
        with pytest.raises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(server.url, timeout=10)
        assert missing.value.code == 404
    finally:
        server.stop()
