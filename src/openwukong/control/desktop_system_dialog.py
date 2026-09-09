# -*- coding: utf-8 -*-
"""Read-only Windows system-dialog preflight for no-loss desktop runs."""

from __future__ import annotations

import ctypes
import dataclasses
import sys
import time
from ctypes import wintypes


@dataclasses.dataclass(frozen=True)
class DesktopSystemDialogPreflightReport:
    system_dialog_snapshots: tuple[dict, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "desktop-system-dialog-preflight"

    @property
    def safety_mode(self) -> str:
        return "read_only_desktop_scan"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def native_call_attempts(self) -> int:
        return 0

    @property
    def system_dialog_detected(self) -> bool:
        return bool(self.system_dialog_snapshots)

    @property
    def ok(self) -> bool:
        return bool(not self.system_dialog_detected and not self.error)

    @property
    def decision(self) -> str:
        if self.system_dialog_detected:
            return "system_dialog_detected"
        if self.error:
            return "system_dialog_scan_failed"
        return "system_dialog_clear"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "native_call_attempts": self.native_call_attempts,
            "system_dialog_detected": self.system_dialog_detected,
            "system_dialog_count": len(self.system_dialog_snapshots),
            "system_dialog_snapshots": [
                dict(item) for item in self.system_dialog_snapshots
            ],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_desktop_system_dialog_preflight(
    *,
    observer: object | None = None,
) -> DesktopSystemDialogPreflightReport:
    started = time.perf_counter()
    try:
        snapshots = _capture_system_dialog_snapshots(observer)
        return DesktopSystemDialogPreflightReport(
            system_dialog_snapshots=tuple(dict(item) for item in snapshots),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:
        return DesktopSystemDialogPreflightReport(
            error=str(exc) or exc.__class__.__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


def _capture_system_dialog_snapshots(observer: object | None = None) -> tuple[dict, ...]:
    snapshots = _capture_observed_dialog_snapshots(observer)
    if observer is None:
        snapshots.extend(_capture_windows_system_dialogs())
    normalized = (
        _normalize_system_dialog_snapshot(item)
        for item in snapshots
        if isinstance(item, dict)
    )
    return tuple(
        snapshot
        for snapshot in normalized
        if snapshot and _system_dialog_detected(snapshot)
    )


def _capture_observed_dialog_snapshots(observer: object | None) -> list[dict]:
    if observer is None:
        return []
    value = None
    for method_name in ("capture_system_dialogs", "capture_all", "capture"):
        method = getattr(observer, method_name, None)
        if callable(method):
            value = method()
            break
    if value is None and callable(observer):
        value = observer()
    if isinstance(value, dict):
        dialogs = value.get("dialogs")
        if isinstance(dialogs, list):
            return [item for item in dialogs if isinstance(item, dict)]
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, dict)]
    return []


def _capture_windows_system_dialogs() -> list[dict]:
    if not sys.platform.startswith("win"):
        return []
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        snapshots: list[dict] = []
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _visit(hwnd, _lparam):
            hwnd_int = int(hwnd)
            is_visible = getattr(user32, "IsWindowVisible", None)
            if callable(is_visible) and not bool(is_visible(wintypes.HWND(hwnd_int))):
                return True
            title = _get_window_text(user32, hwnd_int, max_chars=512)
            class_name = _get_class_name(user32, hwnd_int)
            process_id, thread_id = _get_window_process_identity(user32, hwnd_int)
            process_name, executable_path = _process_identity_for_pid(process_id)
            snapshot = {
                "available": True,
                "hwnd": hwnd_int,
                "title": title,
                "class_name": class_name,
                "process_id": process_id,
                "thread_id": thread_id,
                "process_name": process_name,
                "executable_path": executable_path,
                "child_texts": [],
            }
            if (
                not _system_dialog_detected(snapshot)
                and _should_probe_child_texts_for_system_dialog(snapshot)
            ):
                snapshot["child_texts"] = _child_window_texts(user32, hwnd_int)
            if _system_dialog_detected(snapshot):
                snapshots.append(snapshot)
            return True

        user32.EnumWindows(enum_proc(_visit), wintypes.LPARAM(0))
        return snapshots[:16]
    except Exception:
        return []


def _normalize_system_dialog_snapshot(value: dict) -> dict:
    data = dict(value)
    data["available"] = bool(data.get("available", True))
    try:
        data["hwnd"] = int(data.get("hwnd", 0) or 0)
    except Exception:
        data["hwnd"] = 0
    if "child_texts" in data and not isinstance(data.get("child_texts"), list):
        data["child_texts"] = []
    return data


def _system_dialog_detected(snapshot: dict) -> bool:
    fields = [
        str(snapshot.get("title", "") or ""),
        str(snapshot.get("class_name", "") or ""),
        str(snapshot.get("process_name", "") or ""),
        str(snapshot.get("executable_path", "") or ""),
        str(snapshot.get("text", "") or ""),
        str(snapshot.get("error", "") or ""),
    ]
    fields.extend(str(item or "") for item in _list_value(snapshot.get("child_texts")))
    haystack = "\n".join(item.casefold() for item in fields if item)
    if not haystack:
        return False
    hard_markers = (
        "session-start",
        "\u9009\u62e9\u5e94\u7528\u4ee5\u6253\u5f00",
        "choose an app",
        "how do you want to open",
        "open with",
        "error launching app",
        "unable to find electron app",
        "cannot find module",
        "a javascript error occurred in the main process",
        "uncaught exception",
        "attachconsole failed",
        "?type=click",
        "type=click&tag",
    )
    if any(marker in haystack for marker in hard_markers):
        return True
    title = str(snapshot.get("title", "") or "").strip().casefold()
    if title == "error" and _has_codex_electron_error_identity(haystack):
        return True
    return False


def _should_probe_child_texts_for_system_dialog(snapshot: dict) -> bool:
    title = str(snapshot.get("title", "") or "").strip().casefold()
    class_name = str(snapshot.get("class_name", "") or "").strip().casefold()
    fields = [
        title,
        class_name,
        str(snapshot.get("process_name", "") or "").casefold(),
        str(snapshot.get("executable_path", "") or "").casefold(),
        str(snapshot.get("text", "") or "").casefold(),
        str(snapshot.get("error", "") or "").casefold(),
    ]
    haystack = "\n".join(item for item in fields if item)
    if title == "error" or class_name == "#32770":
        return True
    return any(
        marker in haystack
        for marker in (
            "session-start",
            "\u9009\u62e9\u5e94\u7528\u4ee5\u6253\u5f00",
            "choose an app",
            "how do you want to open",
            "open with",
            "error launching app",
            "unable to find electron app",
            "a javascript error occurred in the main process",
            "attachconsole failed",
            "?type=click",
            "type=click&tag",
        )
    )


def _has_codex_electron_error_identity(haystack: str) -> bool:
    text = str(haystack or "").casefold()
    return bool(
        "codex.exe" in text
        or "openai.codex" in text
        or "electron" in text
        or ("windowsapps" in text and "codex" in text)
    )


def _get_window_text(user32, hwnd: int, *, max_chars: int) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(max_chars)
        copied = user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
        if not copied:
            return ""
        return buffer.value
    except Exception:
        return ""


def _get_window_message_text(user32, hwnd: int, *, max_chars: int) -> str:
    try:
        send_message_timeout = getattr(user32, "SendMessageTimeoutW", None)
        if not callable(send_message_timeout):
            return ""
        buffer = ctypes.create_unicode_buffer(max_chars)
        result = ctypes.c_size_t(0)
        ok = send_message_timeout(
            wintypes.HWND(hwnd),
            0x000D,
            wintypes.WPARAM(max_chars),
            ctypes.byref(buffer),
            0x0002,
            100,
            ctypes.byref(result),
        )
        if not ok:
            return ""
        return buffer.value
    except Exception:
        return ""


def _get_class_name(user32, hwnd: int) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(256)
        copied = user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
        if not copied:
            return ""
        return buffer.value
    except Exception:
        return ""


def _get_window_process_identity(user32, hwnd: int) -> tuple[int, int]:
    try:
        process_id = wintypes.DWORD(0)
        thread_id = int(
            user32.GetWindowThreadProcessId(
                wintypes.HWND(hwnd),
                ctypes.byref(process_id),
            )
            or 0
        )
        return int(process_id.value or 0), thread_id
    except Exception:
        return 0, 0


def _child_window_texts(user32, hwnd: int) -> list[str]:
    texts: list[str] = []
    try:
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _visit(child_hwnd, _lparam):
            text = _get_window_text(user32, int(child_hwnd), max_chars=1024).strip()
            if not text:
                text = _get_window_message_text(
                    user32,
                    int(child_hwnd),
                    max_chars=1024,
                ).strip()
            if text and text not in texts:
                texts.append(text)
            return True

        user32.EnumChildWindows(wintypes.HWND(hwnd), enum_proc(_visit), wintypes.LPARAM(0))
    except Exception:
        return texts
    return texts[:32]


def _process_identity_for_pid(process_id: int) -> tuple[str, str]:
    if int(process_id or 0) <= 0:
        return "", ""
    try:
        import psutil

        proc = psutil.Process(int(process_id))
        return str(proc.name() or ""), str(proc.exe() or "")
    except Exception:
        return "", ""


def _list_value(value: object) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = [
    "DesktopSystemDialogPreflightReport",
    "run_desktop_system_dialog_preflight",
]
