# -*- coding: utf-8 -*-
"""Explicit opt-in WeChat File Transfer Assistant send probe.

This module is intentionally separate from the default real no-loss harness.
It can send a real message only when explicitly opted in, the target is the
File Transfer Assistant, and the opened target is confirmed before sending.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Optional

from openwukong.control.foreground_takeover import (
    ForegroundTakeoverRequest,
    validate_foreground_takeover_request,
)


_FILE_HELPER_TARGET = "文件传输助手"
_MAX_MESSAGE_LENGTH = 500


@dataclasses.dataclass(frozen=True)
class WeChatSendProbeReport:
    status: str
    target_name: str
    message: str
    allow_send: bool
    control_allowed: bool = False
    send_attempts: int = 0
    keyboard_input_attempts: int = 0
    clipboard_write_attempts: int = 0
    clipboard_restore_attempts: int = 0
    foreground_restore_attempts: int = 0
    target_verified: bool = False
    window_hwnd: int = 0
    previous_foreground_hwnd: int = 0
    pre_send_screenshot_path: str = ""
    post_send_screenshot_path: str = ""
    post_send_screenshot_hwnd: int = 0
    post_send_screenshot_bound: bool = False
    post_send_screenshot_mode: str = ""
    post_send_verified: bool = False
    post_send_verification: dict = dataclasses.field(default_factory=dict)
    artifact_path: str = ""
    transport: str = "foreground-keyboard-clipboard"
    foreground_takeover_validated: bool = False
    foreground_takeover_validation: dict = dataclasses.field(default_factory=dict)
    foreground_takeover_request: dict = dataclasses.field(default_factory=dict)
    phases: tuple[dict, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-file-helper-send-probe"

    @property
    def safety_mode(self) -> str:
        return "explicit_opt_in_real_send"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "status": self.status,
            "target_name": self.target_name,
            "message": self.message,
            "allow_send": self.allow_send,
            "control_allowed": self.control_allowed,
            "send_attempts": self.send_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "clipboard_restore_attempts": self.clipboard_restore_attempts,
            "foreground_restore_attempts": self.foreground_restore_attempts,
            "target_verified": self.target_verified,
            "window_hwnd": self.window_hwnd,
            "previous_foreground_hwnd": self.previous_foreground_hwnd,
            "pre_send_screenshot_path": self.pre_send_screenshot_path,
            "post_send_screenshot_path": self.post_send_screenshot_path,
            "post_send_screenshot_hwnd": self.post_send_screenshot_hwnd,
            "post_send_screenshot_bound": self.post_send_screenshot_bound,
            "post_send_screenshot_mode": self.post_send_screenshot_mode,
            "post_send_verified": self.post_send_verified,
            "post_send_verification": dict(self.post_send_verification),
            "artifact_path": self.artifact_path,
            "transport": self.transport,
            "foreground_takeover_validated": self.foreground_takeover_validated,
            "foreground_takeover_validation": dict(self.foreground_takeover_validation),
            "foreground_takeover_request": dict(self.foreground_takeover_request),
            "phases": [dict(phase) for phase in self.phases],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class FakeWeChatKeyboardAutomation:
    def __init__(self, *, target_verified: bool = True, window_hwnd: int = 1001, foreground_hwnd: int = 9001):
        self.target_verified = target_verified
        self.window_hwnd = window_hwnd
        self.foreground_hwnd = foreground_hwnd
        self.events: list[str] = []

    def find_wechat_window(self) -> int:
        self.events.append("find_window")
        return self.window_hwnd

    def get_foreground_window(self) -> int:
        self.events.append("get_foreground")
        return self.foreground_hwnd

    def set_foreground_window(self, hwnd: int) -> bool:
        self.events.append(f"set_foreground:{int(hwnd)}")
        return True

    def hotkey(self, *keys: str) -> None:
        self.events.append("hotkey:" + "+".join(keys))

    def select_all(self) -> None:
        self.events.append("select_all")

    def paste_text(self, text: str) -> None:
        self.events.append(f"paste:{text}")

    def press(self, key: str) -> None:
        self.events.append(f"press:{key}")

    def screenshot(self, output_path: Path) -> str:
        self.events.append("screenshot")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake screenshot")
        return str(output_path)

    def capture_bound_window(self, hwnd: int, output_path: Path) -> str:
        self.events.append(f"background_screenshot:{int(hwnd)}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake bound screenshot")
        return str(output_path)

    def verify_target(self, target_name: str, screenshot_path: str) -> bool:
        del screenshot_path
        self.events.append(f"verify_target:{target_name}")
        return self.target_verified

    def restore_clipboard(self) -> None:
        self.events.append("restore_clipboard")

    def sleep(self, seconds: float) -> None:
        del seconds


class Win32WeChatKeyboardAutomation:
    def __init__(self, *, action_delay: float = 0.35):
        self.action_delay = action_delay
        self._saved_clipboard: str | None = None
        self._window = None

    def find_wechat_window(self) -> int:
        import psutil
        from pywinauto import Desktop

        best = None
        for wrapper in Desktop(backend="win32").windows():
            try:
                pid = int(wrapper.process_id())
                pname = psutil.Process(pid).name().lower()
                class_name = wrapper.class_name()
                title = wrapper.window_text()
                handle = int(wrapper.handle)
            except Exception:
                continue
            if pname not in {"weixin.exe", "wechat.exe"}:
                continue
            if class_name != "Qt51514QWindowIcon":
                continue
            if not title.strip():
                continue
            best = wrapper
            break
        if best is None:
            raise RuntimeError("wechat_window_not_found")
        self._window = best
        return int(best.handle)

    def get_foreground_window(self) -> int:
        import ctypes

        return int(ctypes.windll.user32.GetForegroundWindow())

    def set_foreground_window(self, hwnd: int) -> bool:
        import ctypes

        ok = bool(ctypes.windll.user32.SetForegroundWindow(int(hwnd)))
        if self._window is not None:
            try:
                self._window.set_focus()
                ok = True
            except Exception:
                pass
        self.sleep(self.action_delay)
        return ok

    def hotkey(self, *keys: str) -> None:
        from pywinauto.keyboard import send_keys

        if tuple(key.lower() for key in keys) == ("ctrl", "f"):
            send_keys("^f")
        else:
            raise ValueError(f"unsupported_hotkey:{keys}")
        self.sleep(self.action_delay)

    def select_all(self) -> None:
        from pywinauto.keyboard import send_keys

        send_keys("^a")
        self.sleep(self.action_delay)

    def paste_text(self, text: str) -> None:
        import pyperclip
        from pywinauto.keyboard import send_keys

        if self._saved_clipboard is None:
            try:
                self._saved_clipboard = pyperclip.paste()
            except Exception:
                self._saved_clipboard = ""
        pyperclip.copy(text)
        self.sleep(0.1)
        send_keys("^v")
        self.sleep(self.action_delay)

    def press(self, key: str) -> None:
        from pywinauto.keyboard import send_keys

        if key.lower() != "enter":
            raise ValueError(f"unsupported_key:{key}")
        send_keys("{ENTER}")
        self.sleep(self.action_delay)

    def screenshot(self, output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self._window is None:
            raise RuntimeError("wechat_window_not_bound")
        image = self._window.capture_as_image()
        image.save(output_path)
        return str(output_path)

    def capture_bound_window(self, hwnd: int, output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if _capture_hwnd_with_print_window(int(hwnd), output_path):
            return str(output_path)
        return ""

    def verify_target(self, target_name: str, screenshot_path: str) -> bool:
        del target_name, screenshot_path
        return False

    def restore_clipboard(self) -> None:
        if self._saved_clipboard is None:
            return
        try:
            import pyperclip

            pyperclip.copy(self._saved_clipboard)
        finally:
            self._saved_clipboard = None

    def sleep(self, seconds: float) -> None:
        time.sleep(max(0.0, float(seconds)))


def run_wechat_file_helper_send_probe(
    *,
    message: str,
    target_name: str = _FILE_HELPER_TARGET,
    allow_send: bool = False,
    allow_external_target: bool = False,
    confirm_target_after_open: bool = False,
    automation: object | None = None,
    output_dir: str | Path = "",
    foreground_takeover_request: ForegroundTakeoverRequest | dict | None = None,
) -> WeChatSendProbeReport:
    started = time.perf_counter()
    target = str(target_name or "").strip()
    text = str(message or "").strip()
    if not allow_send:
        return _report(
            started,
            status="blocked_requires_explicit_opt_in",
            target_name=target or _FILE_HELPER_TARGET,
            message=text,
            allow_send=False,
        )
    if target != _FILE_HELPER_TARGET and not allow_external_target:
        return _report(
            started,
            status="blocked_external_target_requires_explicit_permission",
            target_name=target,
            message=text,
            allow_send=True,
        )
    if not text:
        return _report(
            started,
            status="blocked_empty_message",
            target_name=target,
            message=text,
            allow_send=True,
        )
    if len(text) > _MAX_MESSAGE_LENGTH:
        return _report(
            started,
            status="blocked_message_too_long",
            target_name=target,
            message=text,
            allow_send=True,
        )

    takeover_validation = validate_foreground_takeover_request(
        foreground_takeover_request,
        action="send_message",
        target_process_names=("weixin.exe", "wechat.exe"),
        selected_transport="foreground-keyboard-clipboard",
    )
    takeover_fields = _takeover_report_fields(takeover_validation)
    if not takeover_validation.valid:
        missing = takeover_validation.decision == "missing_foreground_takeover_request"
        return _report(
            started,
            status=(
                "blocked_foreground_takeover_request_required"
                if missing
                else "blocked_foreground_takeover_request_invalid"
            ),
            target_name=target,
            message=text,
            allow_send=True,
            error=takeover_validation.decision,
            **takeover_fields,
        )

    active = automation or Win32WeChatKeyboardAutomation()
    root = Path(output_dir or Path("logs") / "runtime" / "wechat-file-helper-send").resolve()
    screenshot_path = root / "pre_send_target.png"
    post_send_screenshot_path = root / "post_send_verify.png"
    artifact_path = root / "report.json"
    phases: list[dict] = []
    keyboard_inputs = 0
    clipboard_writes = 0
    clipboard_restores = 0
    foreground_restores = 0
    window_hwnd = 0
    previous_hwnd = 0
    screenshot = ""
    post_send_screenshot = ""
    try:
        window_hwnd = int(active.find_wechat_window())
        previous_hwnd = int(active.get_foreground_window())
        phases.append({"phase": "bind_window", "status": "ok", "window_hwnd": window_hwnd})
        active.set_foreground_window(window_hwnd)
        active.hotkey("ctrl", "f")
        keyboard_inputs += 1
        active.select_all()
        keyboard_inputs += 1
        active.paste_text(target)
        keyboard_inputs += 1
        clipboard_writes += 1
        active.press("enter")
        keyboard_inputs += 1
        active.sleep(1.0)
        screenshot = str(active.screenshot(screenshot_path))
        phases.append({"phase": "open_target", "status": "ok", "screenshot_path": screenshot})
        target_verified = bool(confirm_target_after_open or active.verify_target(target, screenshot))
        phases.append(
            {
                "phase": "verify_target",
                "status": "ok" if target_verified else "blocked",
                "target_verified": target_verified,
                "confirmation_override": bool(confirm_target_after_open),
            }
        )
        if not target_verified:
            active.restore_clipboard()
            clipboard_restores += 1
            _restore_foreground(active, previous_hwnd)
            foreground_restores += int(previous_hwnd > 0)
            phases.append({"phase": "restore_state", "status": "ok"})
            return _persist_report(
                started,
                artifact_path,
                status="blocked_target_not_verified",
                target_name=target,
                message=text,
                allow_send=True,
                keyboard_input_attempts=keyboard_inputs,
                clipboard_write_attempts=clipboard_writes,
                clipboard_restore_attempts=clipboard_restores,
                foreground_restore_attempts=foreground_restores,
                target_verified=False,
                window_hwnd=window_hwnd,
                previous_foreground_hwnd=previous_hwnd,
                pre_send_screenshot_path=screenshot,
                phases=tuple(phases),
                **takeover_fields,
            )

        active.paste_text(text)
        keyboard_inputs += 1
        clipboard_writes += 1
        active.press("enter")
        keyboard_inputs += 1
        active.sleep(0.8)
        post_send_screenshot = _capture_bound_screenshot(
            active,
            window_hwnd,
            post_send_screenshot_path,
        )
        post_send_bound = bool(post_send_screenshot)
        post_send_verification = _verify_post_send_message(
            active,
            target,
            text,
            post_send_screenshot,
        )
        post_send_verified = bool(post_send_verification.get("verified"))
        phases.append(
            {
                "phase": "send_message",
                "status": "ok" if post_send_bound else "ok_needs_visual_confirmation",
                "send_attempts": 1,
                "post_send_screenshot_path": post_send_screenshot,
                "post_send_screenshot_bound": post_send_bound,
            }
        )
        phases.append(
            {
                "phase": "post_action_verify",
                "status": "ok" if post_send_verified else "unverified",
                "verified": post_send_verified,
                "method": post_send_verification.get("method", ""),
            }
        )
        active.restore_clipboard()
        clipboard_restores += 1
        _restore_foreground(active, previous_hwnd)
        foreground_restores += int(previous_hwnd > 0)
        phases.append({"phase": "restore_state", "status": "ok"})
        return _persist_report(
            started,
            artifact_path,
            status="sent",
            target_name=target,
            message=text,
            allow_send=True,
            control_allowed=True,
            send_attempts=1,
            keyboard_input_attempts=keyboard_inputs,
            clipboard_write_attempts=clipboard_writes,
            clipboard_restore_attempts=clipboard_restores,
            foreground_restore_attempts=foreground_restores,
            target_verified=True,
            window_hwnd=window_hwnd,
            previous_foreground_hwnd=previous_hwnd,
            pre_send_screenshot_path=screenshot,
            post_send_screenshot_path=post_send_screenshot,
            post_send_screenshot_hwnd=window_hwnd if post_send_bound else 0,
            post_send_screenshot_bound=post_send_bound,
            post_send_screenshot_mode="bound-window" if post_send_bound else "",
            post_send_verified=post_send_verified,
            post_send_verification=post_send_verification,
            phases=tuple(phases),
            **takeover_fields,
        )
    except Exception as exc:
        try:
            active.restore_clipboard()
            clipboard_restores += 1
        except Exception:
            pass
        if previous_hwnd:
            try:
                _restore_foreground(active, previous_hwnd)
                foreground_restores += 1
            except Exception:
                pass
        phases.append({"phase": "failed", "status": "failed", "error": str(exc)})
        return _persist_report(
            started,
            artifact_path,
            status="failed",
            target_name=target,
            message=text,
            allow_send=True,
            keyboard_input_attempts=keyboard_inputs,
            clipboard_write_attempts=clipboard_writes,
            clipboard_restore_attempts=clipboard_restores,
            foreground_restore_attempts=foreground_restores,
            window_hwnd=window_hwnd,
            previous_foreground_hwnd=previous_hwnd,
            pre_send_screenshot_path=screenshot,
            post_send_screenshot_path=post_send_screenshot,
            phases=tuple(phases),
            error=str(exc),
            **takeover_fields,
        )


def _restore_foreground(active: object, hwnd: int) -> None:
    if int(hwnd or 0) <= 0:
        return
    active.set_foreground_window(int(hwnd))


def _capture_bound_screenshot(active: object, hwnd: int, output_path: Path) -> str:
    capture = getattr(active, "capture_bound_window", None)
    if capture is None:
        return ""
    try:
        return str(capture(int(hwnd), output_path) or "")
    except Exception:
        return ""


def _verify_post_send_message(
    active: object,
    target_name: str,
    message: str,
    screenshot_path: str,
) -> dict:
    verifier = getattr(active, "verify_post_send_message", None)
    if not callable(verifier):
        return {
            "verified": False,
            "method": "not_available",
            "target_name": target_name,
            "message_preview": _clip(message),
            "screenshot_path": screenshot_path,
        }
    try:
        result = verifier(target_name, message, screenshot_path)
    except Exception as exc:
        return {
            "verified": False,
            "method": "verification_error",
            "target_name": target_name,
            "message_preview": _clip(message),
            "screenshot_path": screenshot_path,
            "error": str(exc),
        }
    if isinstance(result, dict):
        data = dict(result)
    else:
        data = {"verified": bool(result)}
    data.setdefault("method", "custom-verifier")
    data.setdefault("target_name", target_name)
    data.setdefault("message_preview", _clip(message))
    data.setdefault("screenshot_path", screenshot_path)
    data["verified"] = bool(data.get("verified"))
    return data


def _report(started: float, **kwargs) -> WeChatSendProbeReport:
    return WeChatSendProbeReport(
        elapsed_ms=(time.perf_counter() - started) * 1000,
        **kwargs,
    )


def _persist_report(started: float, artifact_path: Path, **kwargs) -> WeChatSendProbeReport:
    report = _report(started, artifact_path=str(artifact_path), **kwargs)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def _clip(value: str, limit: int = 500) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


def _takeover_report_fields(validation) -> dict:
    data = validation.to_dict()
    return {
        "foreground_takeover_validated": bool(validation.valid),
        "foreground_takeover_validation": data,
        "foreground_takeover_request": dict(data.get("request") or {}),
    }


def _capture_hwnd_with_print_window(hwnd: int, output_path: Path) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
    except Exception:
        return False

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return False
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        return False

    hwnd_dc = user32.GetWindowDC(wintypes.HWND(hwnd))
    if not hwnd_dc:
        return False
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)
    try:
        ok = bool(user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, 2))
        if not ok:
            ok = bool(user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, 0))
        if not ok:
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
            return False
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
        image.save(output_path)
        return True
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(wintypes.HWND(hwnd), hwnd_dc)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit opt-in WeChat File Transfer Assistant send probe.")
    parser.add_argument("--message", required=True)
    parser.add_argument("--target-name", default=_FILE_HELPER_TARGET)
    parser.add_argument("--allow-send", action="store_true")
    parser.add_argument("--allow-external-target", action="store_true")
    parser.add_argument("--confirm-target-after-open", action="store_true")
    parser.add_argument("--foreground-takeover-request", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_wechat_file_helper_send_probe(
        message=args.message,
        target_name=args.target_name,
        allow_send=args.allow_send,
        allow_external_target=args.allow_external_target,
        confirm_target_after_open=args.confirm_target_after_open,
        output_dir=args.output_dir,
        foreground_takeover_request=_load_foreground_takeover_request(args.foreground_takeover_request),
    )
    data = report.to_dict()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"{data['status']} target={data['target_name']} send_attempts={data['send_attempts']}")
    return 0 if report.status in {"sent", "blocked_target_not_verified"} else 1


def _load_foreground_takeover_request(path: str) -> dict | None:
    if not str(path or "").strip():
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("foreground_takeover_request"), dict):
        return dict(payload["foreground_takeover_request"])
    if isinstance(payload, dict):
        return payload
    return None


if __name__ == "__main__":
    raise SystemExit(main())
