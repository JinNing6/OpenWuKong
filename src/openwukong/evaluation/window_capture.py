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

    @property
    def foreground_change_classification(self) -> str:
        before = int(self.foreground_hwnd_before or 0)
        after = int(self.foreground_hwnd_after or 0)
        target = int(self.hwnd or 0)
        if not before or not after:
            return "unknown"
        if before == after:
            return "stable"
        if target and after == target:
            return "changed_to_target_window"
        if target and before == target:
            return "target_lost_focus"
        return "external_focus_change"

    @property
    def foreground_focus_risk(self) -> bool:
        return self.foreground_change_classification == "changed_to_target_window"

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
            "foreground_change_classification": self.foreground_change_classification,
            "foreground_focus_risk": self.foreground_focus_risk,
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
            if not result.ok:
                fallback = _capture_hwnd_with_screen_blt(hwnd_int, target)
                if fallback.ok:
                    result = fallback
                elif result.error == "print_window_failed":
                    result = dataclasses.replace(
                        fallback,
                        error=f"print_window_failed;{fallback.error or 'screen_blt_failed'}",
                    )
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

        if not _save_bitmap_to_png(gdi32, mem_dc, bitmap, width, height, output_path):
            return BackgroundWindowCaptureReport(
                hwnd=int(hwnd),
                output_path=str(output_path),
                ok=False,
                width=width,
                height=height,
                error="get_dibits_failed",
            )
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


def _capture_hwnd_with_screen_blt(hwnd: int, output_path: Path) -> BackgroundWindowCaptureReport:
    if int(hwnd or 0) <= 0:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd or 0),
            output_path=str(output_path),
            ok=False,
            mode="screen-bounds-bitblt-fallback",
            error="invalid_hwnd",
        )
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            mode="screen-bounds-bitblt-fallback",
            error="capture_dependencies_unavailable",
        )

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    bounds = _screen_capture_bounds_for_hwnd(hwnd)
    if bounds is None:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            mode="screen-bounds-bitblt-fallback",
            error="screen_capture_bounds_unavailable",
        )
    left, top, right, bottom = bounds
    width = int(right - left)
    height = int(bottom - top)
    if width <= 0 or height <= 0:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            mode="screen-bounds-bitblt-fallback",
            width=width,
            height=height,
            error="empty_screen_capture_bounds",
        )

    screen_dc = user32.GetDC(wintypes.HWND(0))
    if not screen_dc:
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=False,
            mode="screen-bounds-bitblt-fallback",
            width=width,
            height=height,
            error="get_screen_dc_failed",
        )
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)
    try:
        srccopy = 0x00CC0020
        captureblt = 0x40000000
        if not gdi32.BitBlt(
            mem_dc,
            0,
            0,
            width,
            height,
            screen_dc,
            int(left),
            int(top),
            srccopy | captureblt,
        ):
            return BackgroundWindowCaptureReport(
                hwnd=int(hwnd),
                output_path=str(output_path),
                ok=False,
                mode="screen-bounds-bitblt-fallback",
                width=width,
                height=height,
                error="bitblt_failed",
            )
        if not _save_bitmap_to_png(gdi32, mem_dc, bitmap, width, height, output_path):
            return BackgroundWindowCaptureReport(
                hwnd=int(hwnd),
                output_path=str(output_path),
                ok=False,
                mode="screen-bounds-bitblt-fallback",
                width=width,
                height=height,
                error="get_dibits_failed",
            )
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=True,
            mode="screen-bounds-bitblt-fallback",
            width=width,
            height=height,
        )
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(wintypes.HWND(0), screen_dc)


def _screen_capture_bounds_for_hwnd(hwnd: int) -> tuple[int, int, int, int] | None:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    rect = wintypes.RECT()
    try:
        dwmapi = ctypes.windll.dwmapi
        extended_frame_bounds = 9
        ok = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            extended_frame_bounds,
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
        if ok == 0 and rect.right > rect.left and rect.bottom > rect.top:
            return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        pass

    try:
        user32 = ctypes.windll.user32
        if user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            if rect.right > rect.left and rect.bottom > rect.top:
                return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return None
    return None


def _save_bitmap_to_png(gdi32, mem_dc, bitmap, width: int, height: int, output_path: Path) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
    except Exception:
        return False

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
    bmi.bmiHeader.biWidth = int(width)
    bmi.bmiHeader.biHeight = -int(height)
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buffer = ctypes.create_string_buffer(int(width) * int(height) * 4)
    lines = gdi32.GetDIBits(
        mem_dc,
        bitmap,
        0,
        int(height),
        buffer,
        ctypes.byref(bmi),
        0,
    )
    if not lines:
        return False
    image = Image.frombuffer("RGBA", (int(width), int(height)), buffer, "raw", "BGRA", 0, 1)
    image.save(output_path)
    return True


__all__ = [
    "BackgroundWindowCaptureReport",
    "PrintWindowBackgroundCaptureProvider",
]
