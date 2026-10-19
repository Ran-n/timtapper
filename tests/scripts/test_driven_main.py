#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:45:48.412221
Revised: 2026/10/15 01:26:05.313628

The driven builds' side of the driver: answering one command (scripts/demo_driver.py) and the poll loop
(scripts/driven_main.py), against a scripted harness and a real one.
"""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import driven_main  # noqa: E402
from demo_driver import answer  # noqa: E402
from serve_site import DriverChannel, SiteServer  # noqa: E402


def fake_demo(**commands):
    return SimpleNamespace(newest=7, commands=lambda: commands)


def scripted(*responses):
    """A `post` that answers each poll with the next response (an exception is raised instead), recording bodies."""
    sent, queue = [], list(responses)

    async def post(url, body):
        sent.append(body)
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return dict(response)

    return post, sent


# ---- answer() -------------------------------------------------------------------------------
async def test_answer_runs_the_command_with_its_arguments():
    assert await answer({"round": lambda round_no: {"no": round_no}}, {"cmd": "round", "round_no": 2}) == {
        "ok": True,
        "result": {"no": 2},
    }


async def test_answer_awaits_an_async_command():
    async def later():
        return "done"

    assert await answer({"later": later}, {"cmd": "later"}) == {"ok": True, "result": "done"}


async def test_answer_reports_a_failing_command_and_logs_it(caplog):
    def broken():
        raise LookupError("no control tagged 'name' on screen")

    with caplog.at_level(logging.ERROR, logger="timtapper.scripts.demo_driver"):
        reply = await answer({"field": broken}, {"cmd": "field"})
    assert reply == {"ok": False, "error": "LookupError: no control tagged 'name' on screen"}
    assert "driver command failed" in caplog.text


async def test_answer_reports_an_unknown_command():
    assert (await answer({}, {"cmd": "dance"}))["ok"] is False


# ---- the poll loop --------------------------------------------------------------------------
async def test_first_poll_says_ready_with_the_newest_event(monkeypatch):
    post, sent = scripted({"cmd": "quit", "seq": 1}, {"cmd": "idle"})
    monkeypatch.setattr(driven_main, "post", post)
    await driven_main.poll(fake_demo(), "http://harness/driver")
    assert sent[0] == {"seq": 0, "reply": {"ok": True, "ready": True, "newest": 7}}
    assert sent[1] == {"seq": 1, "reply": {"ok": True}}  # quit is answered before the loop ends


async def test_each_poll_carries_the_reply_to_the_command_before(monkeypatch):
    post, sent = scripted({"cmd": "state", "seq": 1}, {"cmd": "idle"}, {"cmd": "quit", "seq": 2}, {})
    monkeypatch.setattr(driven_main, "post", post)
    await driven_main.poll(fake_demo(state=lambda: {"mode": "dark"}), "url")
    assert sent[1] == {"seq": 1, "reply": {"ok": True, "result": {"mode": "dark"}}}
    assert sent[2] == {"seq": None}  # after an idle poll there is no reply to carry


async def test_a_failed_poll_is_logged_and_sent_again(monkeypatch, caplog):
    post, sent = scripted(OSError("connection refused"), {"cmd": "quit", "seq": 1}, {})
    monkeypatch.setattr(driven_main, "post", post)
    monkeypatch.setattr(driven_main, "RETRY_DELAY", 0)
    with caplog.at_level(logging.WARNING, logger="timtapper.scripts.driven_main"):
        await driven_main.poll(fake_demo(), "url")
    assert sent[0] == sent[1]  # the ready message again: the harness may not have been listening yet
    assert "connection refused" in caplog.text


def test_off_the_web_the_driver_is_on_the_mapped_port():
    assert driven_main.driver_url() == f"http://127.0.0.1:{driven_main.DRIVER_PORT}/driver"


async def test_post_reaches_a_real_harness():
    channel = DriverChannel(idle_after=0.05)
    server = SiteServer(None, channel).start()
    try:
        reply = await driven_main.post(f"http://127.0.0.1:{server.port}/driver", {"seq": 0, "reply": {"ok": True}})
    finally:
        server.stop()
    assert reply == {"cmd": "idle"}
    assert channel.wait(0, timeout=1) == {"ok": True}


def test_the_demo_draws_pictures_as_the_app_does(page, monkeypatch):
    """The demo builds its own context, and on the web it had no RenderDeps: its first share card failed, as the
    archive carries no Pillow."""
    import demo_driver

    import main as app_main

    monkeypatch.setattr(app_main, "IS_WEB", True)
    demo = demo_driver.Demo(page, demo_driver.TODAY, "t")
    try:
        assert isinstance(demo.ctx.render_deps, app_main.RenderDeps)
    finally:
        demo.db.dispose()
