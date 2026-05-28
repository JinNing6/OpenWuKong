# -*- coding: utf-8 -*-
"""Read-only background window capture helpers."""

from __future__ import annotations

import dataclasses
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class BackgroundWindowCaptureReport:
    hwnd: int
    output_path: str
    ok: bool
    mode: str = "print-window"
    width: int = 0
    height: int = 0
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    error: str = ""

    @property
    def foreground_changed(self) -> bool:
        before = int(self.foreground_hwnd_before or 0)
        after = int(self.foreground_hwnd_after or 0)
        return bool(before and after and before != after)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "hwnd": int(self.hwnd or 0),
            "output_path": self.output_path,
            "width": int(self.width or 0),
            "height": int(self.height or 0),
            "foreground_hwnd_before": int(self.foreground_hwnd_before or 0),
            "foreground_hwnd_after": int(self.foreground_hwnd_after or 0),
            "foreground_changed": self.foreground_changed,
            "error": self.error,
        }


class PrintWindowBackgroundCaptureProvider:
    """Capture a window by HWND without changing foreground focus."""

    def capture_window(self, hwnd: int, output_path: str | Path) -> BackgroundWindowCaptureReport:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        hwnd_int = int(hwnd or 0)
        foreground_before = _get_foreground_window()
        try:
            result = _capture_hwnd_with_print_window(hwnd_int, target)
        except Exception as exc:
            foreground_after = _get_foreground_window()
            return BackgroundWindowCaptureReport(
                hwnd=hwnd_int,
                output_path=str(target),
                ok=False,
                foreground_hwnd_before=foreground_before,
                foreground_hwnd_after=foreground_after,
                error=f"capture_exception:{type(exc).__name__}",
            )
        foreground_after = _get_foreground_window()
        return dataclasses.replace(
            result,
            foreground_hwnd_before=foreground_before,
            foreground_hwnd_after=foreground_after,
        )


def _get_foreground_window() -> int:
    try:
        import ctypes

        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return 0


def _capture_hwnd_with_print_window(hwnd: int, output_path: Path) -> BackgroundWindowCaptureReport:
    if int(hwnd or 0) <= 0:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd or 0),
            output_path=str(output_path),
            ok=False,
            error="invalid_hwnd",
        )
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
    except Exception:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            error="capture_dependencies_unavailable",
        )

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            error="get_window_rect_failed",
        )
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            width=width,
            height=height,
            error="empty_window_rect",
        )

    hwnd_dc = user32.GetWindowDC(wintypes.HWND(hwnd))
    if not hwnd_dc:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            width=width,
            height=height,
            error="get_window_dc_failed",
        )
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)
    try:
        ok = bool(user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, 2))
        if not ok:
            ok = bool(user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, 0))
        if not ok:
            return BackgroundWindowCaptureReport(
                hwnd=int(hwnd),
                output_path=str(output_path),
                ok=False,
                width=width,
                height=height,
                error="print_window_failed",
            )

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [
                ("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3),
            ]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(
            mem_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(bmi),
            0,
        )
        if not lines:
            return BackgroundWindowCaptureReport(
                hwnd=int(hwnd),
                output_path=str(output_path),
                ok=False,
                width=width,
                height=height,
                error="get_dibits_failed",
            )
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
        image.save(output_path)
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=True,
            width=width,
            height=height,
        )
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(wintypes.HWND(hwnd), hwnd_dc)


__all__ = [
    "BackgroundWindowCaptureReport",
    "PrintWindowBackgroundCaptureProvider",
]
