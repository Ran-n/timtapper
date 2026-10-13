#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.310929
Revised: 2026/10/13 22:03:52.116841

Hand a file to the user: the native share sheet where the platform has one
(Android, and desktops whose share_plus supports files), otherwise a "save
as" dialog. Used for share cards and backup exports alike. In a browser the
file only exists in the app's in-memory file system, so its bytes are handed
over instead of its path, and "save as" is the browser's download.
"""

from enum import Enum
from pathlib import Path

import flet as ft

from core.logging import get_logger
from core.web import IS_WEB

_log = get_logger("share.deliver")


class Delivery(Enum):
    SHARED = "shared"
    SAVED = "saved"
    CANCELLED = "cancelled"


async def save_as(path: Path, *, web: bool = IS_WEB) -> Delivery:
    """'Save as' dialog. The picker writes `src_bytes` itself where it can (mobile, web, Flet's desktop); whatever
    the chosen file holds afterwards, if it isn't the card or backup, is written here."""
    data = path.read_bytes()
    target = await ft.FilePicker().save_file(file_name=path.name, src_bytes=data)
    if web:  # the browser downloads src_bytes itself and reports no path
        _log.info("downloaded %s", path.name)
        return Delivery.SAVED
    if not target:
        _log.info("save of %s cancelled", path.name)
        return Delivery.CANCELLED
    target_path = Path(target)
    # compared, not just checked for being there: replacing an older file leaves that one's bytes until written
    if not target_path.is_file() or target_path.read_bytes() != data:
        target_path.write_bytes(data)
    _log.info("saved %s to %s", path.name, target_path)
    return Delivery.SAVED


def share_file(path: Path, mime_type: str, *, web: bool = IS_WEB) -> ft.ShareFile:
    """The browser can't open a path in the app's in-memory file system, so on the web the bytes go instead."""
    if web:
        return ft.ShareFile(data=path.read_bytes(), mime_type=mime_type, name=path.name)
    return ft.ShareFile(path=str(path), mime_type=mime_type, name=path.name)


async def deliver(path: Path, *, title: str, mime_type: str, web: bool = IS_WEB) -> Delivery:
    """Share sheet first; save dialog where sharing files isn't supported. Raises on I/O failure."""
    try:
        result = await ft.Share().share_files([share_file(path, mime_type, web=web)], title=title)
    except Exception as exc:  # share_plus raises on platforms without file sharing
        _log.info("share sheet unavailable (%s), falling back to save dialog", type(exc).__name__)
        return await save_as(path, web=web)
    _log.info("share sheet for %s closed: %s", path.name, result.status.value)
    return Delivery.CANCELLED if result.status == ft.ShareResultStatus.DISMISSED else Delivery.SHARED
