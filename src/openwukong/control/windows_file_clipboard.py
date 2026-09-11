# -*- coding: utf-8 -*-
"""Windows CF_HDROP clipboard operations with conservative text restoration."""

from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040


@dataclass(frozen=True)
class ClipboardTextSnapshot:
    text: str | None


def build_dropfiles_payload(paths: Iterable[str | Path]) -> bytes:
    normalized = tuple(Path(path).expanduser().resolve() for path in paths)
    if not normalized:
        raise ValueError("clipboard_file_list_empty")
    if any("\x00" in str(path) for path in normalized):
        raise ValueError("clipboard_file_path_contains_nul")
    names = "\x00".join(str(path) for path in normalized) + "\x00\x00"
    # DROPFILES: pFiles=20, point=(0,0), fNC=0, fWide=1.
    return struct.pack("<IiiII", 20, 0, 0, 0, 1) + names.encode("utf-16-le")


class Win32FileClipboard:
    """Set CF_HDROP only after capturing a restorable Unicode text clipboard."""

    def __init__(self, *, user32: object | None = None, kernel32: object | None = None):
        self._user32 = user32 or ctypes.windll.user32
        self._kernel32 = kernel32 or ctypes.windll.kernel32

    def capture_text(self) -> ClipboardTextSnapshot:
        if not self._user32.OpenClipboard(0):
            raise RuntimeError("clipboard_open_failed")
        handle = None
        try:
            if not self._user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                raise RuntimeError("clipboard_original_text_unavailable")
            handle = self._user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise RuntimeError("clipboard_original_text_missing")
            pointer = self._kernel32.GlobalLock(handle)
            if not pointer:
                raise RuntimeError("clipboard_original_text_lock_failed")
            try:
                return ClipboardTextSnapshot(ctypes.wstring_at(pointer))
            finally:
                self._kernel32.GlobalUnlock(handle)
        finally:
            self._user32.CloseClipboard()

    def set_files(self, paths: Iterable[str | Path]) -> None:
        payload = build_dropfiles_payload(paths)
        handle = self._kernel32.GlobalAlloc(
            GMEM_MOVEABLE | GMEM_ZEROINIT,
            len(payload),
        )
        if not handle:
            raise RuntimeError("clipboard_file_global_alloc_failed")
        pointer = self._kernel32.GlobalLock(handle)
        if not pointer:
            self._kernel32.GlobalFree(handle)
            raise RuntimeError("clipboard_file_global_lock_failed")
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            self._kernel32.GlobalUnlock(handle)
        if not self._user32.OpenClipboard(0):
            self._kernel32.GlobalFree(handle)
            raise RuntimeError("clipboard_open_failed")
        try:
            if not self._user32.EmptyClipboard():
                self._kernel32.GlobalFree(handle)
                raise RuntimeError("clipboard_empty_failed")
            if not self._user32.SetClipboardData(CF_HDROP, handle):
                self._kernel32.GlobalFree(handle)
                raise RuntimeError("clipboard_file_set_failed")
            handle = None
        finally:
            self._user32.CloseClipboard()

    def restore_text(self, snapshot: ClipboardTextSnapshot) -> None:
        if snapshot.text is None:
            raise RuntimeError("clipboard_restore_text_unavailable")
        encoded = (snapshot.text + "\x00").encode("utf-16-le")
        handle = self._kernel32.GlobalAlloc(
            GMEM_MOVEABLE | GMEM_ZEROINIT,
            len(encoded),
        )
        if not handle:
            raise RuntimeError("clipboard_restore_alloc_failed")
        pointer = self._kernel32.GlobalLock(handle)
        if not pointer:
            self._kernel32.GlobalFree(handle)
            raise RuntimeError("clipboard_restore_lock_failed")
        try:
            ctypes.memmove(pointer, encoded, len(encoded))
        finally:
            self._kernel32.GlobalUnlock(handle)
        if not self._user32.OpenClipboard(0):
            self._kernel32.GlobalFree(handle)
            raise RuntimeError("clipboard_open_failed")
        try:
            if not self._user32.EmptyClipboard():
                self._kernel32.GlobalFree(handle)
                raise RuntimeError("clipboard_empty_failed")
            if not self._user32.SetClipboardData(CF_UNICODETEXT, handle):
                self._kernel32.GlobalFree(handle)
                raise RuntimeError("clipboard_restore_set_failed")
            handle = None
        finally:
            self._user32.CloseClipboard()


__all__ = [
    "CF_HDROP",
    "ClipboardTextSnapshot",
    "Win32FileClipboard",
    "build_dropfiles_payload",
]
