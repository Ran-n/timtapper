#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.310929
Revised: 2026/10/11 16:27:22.924256

Hand a file to the user: the native share sheet where the platform has one
(Android, and desktops whose share_plus supports files), otherwise a "save
as" dialog. Used for share cards and backup exports alike.
"""

from enum import Enum
from pathlib import Path

import flet as ft

from core.logging import get_logger

_log = get_logger("share.deliver")


class Delivery(Enum):
    SHARED = "shared"
    SAVED = "saved"
    CANCELLED = "cancelled"


async def save_as(path: Path) -> Delivery:
    """'Save as' dialog. Mobile/web pickers write `src_bytes` themselves; desktop only returns a path."""
    data = path.read_bytes()
    target = await ft.FilePicker().save_file(file_name=path.name, src_bytes=data)
    if not target:
        _log.info("save of %s cancelled", path.name)
        return Delivery.CANCELLED
    target_path = Path(target)
    if not target_path.exists() or target_path.stat().st_size == 0:
        target_path.write_bytes(data)
    _log.info("saved %s to %s", path.name, target_path)
    return Delivery.SAVED


async def deliver(path: Path, *, title: str, mime_type: str) -> Delivery:
    """Share sheet first; save dialog where sharing files isn't supported. Raises on I/O failure."""
    try:
        result = await ft.Share().share_files(
            [ft.ShareFile(path=str(path), mime_type=mime_type, name=path.name)], title=title
        )
    except Exception as exc:  # share_plus raises on platforms without file sharing
        _log.info("share sheet unavailable (%s), falling back to save dialog", type(exc).__name__)
        return await save_as(path)
    _log.info("share sheet for %s closed: %s", path.name, result.status.value)
    return Delivery.CANCELLED if result.status == ft.ShareResultStatus.DISMISSED else Delivery.SHARED
