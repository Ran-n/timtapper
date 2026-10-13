#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.402251
Revised: 2026/10/13 07:39:27.454209
"""

from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from share import deliver as deliver_mod
from share.deliver import Delivery, deliver, save_as


class FakeShare:
    def __init__(self, status=None, exc=None):
        self.status, self.exc, self.calls = status, exc, []

    def __call__(self):
        return self

    async def share_files(self, files, **kwargs):
        self.calls.append((files, kwargs))
        if self.exc:
            raise self.exc
        return SimpleNamespace(status=self.status)


class FakePicker:
    def __init__(self, target):
        self.target, self.calls = target, []

    def __call__(self):
        return self

    async def save_file(self, **kwargs):
        self.calls.append(kwargs)
        return self.target


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "card.png"
    path.write_bytes(b"\x89PNG fake")
    return path


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (ft.ShareResultStatus.SUCCESS, Delivery.SHARED),
        (ft.ShareResultStatus.UNAVAILABLE, Delivery.SHARED),
        (ft.ShareResultStatus.DISMISSED, Delivery.CANCELLED),
    ],
)
async def test_share_sheet(monkeypatch, png, status, outcome):
    share = FakeShare(status)
    monkeypatch.setattr(deliver_mod.ft, "Share", share)
    assert await deliver(png, title="t", mime_type="image/png") is outcome
    files, kwargs = share.calls[0]
    assert files[0].path == str(png) and files[0].mime_type == "image/png"
    assert kwargs["title"] == "t"


async def test_falls_back_to_save_when_share_unsupported(monkeypatch, png, tmp_path):
    target = tmp_path / "out" / "saved.png"
    target.parent.mkdir()
    monkeypatch.setattr(deliver_mod.ft, "Share", FakeShare(exc=NotImplementedError("desktop")))
    picker = FakePicker(str(target))
    monkeypatch.setattr(deliver_mod.ft, "FilePicker", picker)
    assert await deliver(png, title="t", mime_type="image/png") is Delivery.SAVED
    assert target.read_bytes() == png.read_bytes()  # desktop: we write the file ourselves
    assert picker.calls[0]["file_name"] == "card.png"


async def test_save_cancelled(monkeypatch, png):
    monkeypatch.setattr(deliver_mod.ft, "FilePicker", FakePicker(None))
    assert await save_as(png) is Delivery.CANCELLED


async def test_save_leaves_a_file_the_platform_wrote_alone(monkeypatch, png, tmp_path):
    """Android may hand back a path the app can read but not write: what the picker wrote there is never rewritten."""
    target = tmp_path / "mobile.png"
    target.write_bytes(png.read_bytes())  # the picker wrote src_bytes
    monkeypatch.setattr(deliver_mod.ft, "FilePicker", FakePicker(str(target)))
    monkeypatch.setattr(Path, "write_bytes", lambda *_a: pytest.fail("rewrote the platform's file"))
    assert await save_as(png) is Delivery.SAVED


@pytest.mark.regression
async def test_save_over_an_older_file_replaces_it(monkeypatch, png, tmp_path):
    """Picking an existing file to replace used to keep its old content (it wasn't empty) and still say Saved."""
    target = tmp_path / "backup.json"
    target.write_bytes(b"last week's backup")
    monkeypatch.setattr(deliver_mod.ft, "FilePicker", FakePicker(str(target)))
    assert await save_as(png) is Delivery.SAVED
    assert target.read_bytes() == png.read_bytes()


async def test_save_io_error_propagates(monkeypatch, png, tmp_path):
    monkeypatch.setattr(deliver_mod.ft, "FilePicker", FakePicker(str(tmp_path / "missing-dir" / "x.png")))
    with pytest.raises(OSError):
        await save_as(png)
