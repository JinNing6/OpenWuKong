# -*- coding: utf-8 -*-
"""Explicit opt-in WeChat File Transfer Assistant send probe.

This module is intentionally separate from the default real no-loss harness.
It can send a real message only when explicitly opted in, the target is the
File Transfer Assistant, and the opened target is confirmed before sending.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from openwukong.control.foreground_takeover import (
    ForegroundTakeoverRequest,
    validate_foreground_takeover_request,
)
from openwukong.control.wechat_visual_evidence import (
    find_chat_header,
    recognize_frame,
    verify_chat_send,
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
    foreground_restored: bool | None = None
    final_foreground_hwnd: int = 0
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
            "foreground_restored": self.foreground_restored,
            "final_foreground_hwnd": self.final_foreground_hwnd,
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
        self.foreground_hwnd = int(hwnd)
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
    def __init__(
        self,
        *,
        action_delay: float = 0.35,
        ocr_timeout: float = 20.0,
        file_clipboard: object | None = None,
    ):
        self.action_delay = action_delay
        self.ocr_timeout = ocr_timeout
        self._saved_clipboard: str | None = None
        if file_clipboard is None:
            from openwukong.control.windows_file_clipboard import Win32FileClipboard

            file_clipboard = Win32FileClipboard()
        self._file_clipboard = file_clipboard
        self._saved_file_clipboard = None
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

        requested = int(hwnd)
        ctypes.windll.user32.SetForegroundWindow(requested)
        if self._window is not None and int(self._window.handle) == requested:
            try:
                self._window.set_focus()
            except Exception:
                pass
        self.sleep(self.action_delay)
        return int(ctypes.windll.user32.GetForegroundWindow()) == requested

    def _assert_bound_foreground(self) -> None:
        if self._window is None:
            raise RuntimeError("wechat_window_not_bound")
        if self.get_foreground_window() != int(self._window.handle):
            raise RuntimeError("wechat_foreground_changed_before_input")

    def hotkey(self, *keys: str) -> None:
        self._assert_bound_foreground()
        from pywinauto.keyboard import send_keys

        if tuple(key.lower() for key in keys) == ("ctrl", "f"):
            send_keys("^f")
        else:
            raise ValueError(f"unsupported_hotkey:{keys}")
        self.sleep(self.action_delay)

    def select_all(self) -> None:
        self._assert_bound_foreground()
        from pywinauto.keyboard import send_keys

        send_keys("^a")
        self.sleep(self.action_delay)

    def paste_text(self, text: str) -> None:
        self._assert_bound_foreground()
        import pyperclip
        from pywinauto.keyboard import send_keys

        if self._saved_clipboard is None:
            try:
                self._saved_clipboard = pyperclip.paste()
            except Exception:
                self._saved_clipboard = ""
        pyperclip.copy(text)
        self.sleep(0.1)
        self._assert_bound_foreground()
        send_keys("^v")
        self.sleep(self.action_delay)

    def paste_files(self, paths: list[str] | tuple[str, ...]) -> None:
        self._assert_bound_foreground()
        snapshot = self._file_clipboard.capture_text()
        self._saved_file_clipboard = snapshot
        self._file_clipboard.set_files(paths)
        self._assert_bound_foreground()
        from pywinauto.keyboard import send_keys

        send_keys("^v")
        self.sleep(self.action_delay)

    def click_relative(self, x: float, y: float) -> None:
        self._assert_bound_foreground()
        x_value = float(x)
        y_value = float(y)
        if not 0.0 <= x_value <= 1.0 or not 0.0 <= y_value <= 1.0:
            raise ValueError("wechat_relative_click_out_of_range")
        left, top, right, bottom = _window_rectangle(self._window)
        absolute = (
            left + int(round(x_value * max(0, right - left - 1))),
            top + int(round(y_value * max(0, bottom - top - 1))),
        )
        from pywinauto import mouse

        mouse.click(coords=absolute)
        self.sleep(self.action_delay)

    def press(self, key: str) -> None:
        self._assert_bound_foreground()
        from pywinauto.keyboard import send_keys

        if key.lower() != "enter":
            raise ValueError(f"unsupported_key:{key}")
        send_keys("{ENTER}")
        self.sleep(self.action_delay)

    def screenshot(self, output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self._window is None:
            raise RuntimeError("wechat_window_not_bound")
        window_hwnd = int(self._window.handle)
        if self.get_foreground_window() != window_hwnd:
            raise RuntimeError("screenshot_target_not_foreground")
        if _capture_hwnd_with_print_window(window_hwnd, output_path):
            return str(output_path)
        image = self._window.capture_as_image()
        image.save(output_path)
        return str(output_path)

    def capture_bound_window(self, hwnd: int, output_path: Path) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if _capture_hwnd_with_print_window(int(hwnd), output_path):
            return str(output_path)
        return ""

    def verify_target(self, target_name: str, screenshot_path: str) -> bool:
        target = str(target_name or "").strip()
        if not target:
            return False
        try:
            frame = recognize_frame(str(screenshot_path or ""), timeout=self.ocr_timeout)
            evidence = find_chat_header(frame, target)
        except Exception:
            return False
        return bool(evidence.get("verified", False))

    def verify_post_send_message(self, target_name: str, message: str, screenshot_path: str) -> dict:
        try:
            frame = recognize_frame(str(screenshot_path or ""), timeout=self.ocr_timeout)
            return verify_chat_send(
                screenshot_path,
                frame,
                target_name=target_name,
                message=message,
            )
        except Exception as exc:
            return {
                "verified": False,
                "method": "positioned-chat-history-readback",
                "target_name": target_name,
                "error": f"positioned_ocr_error:{exc.__class__.__name__}",
            }

    def verify_post_send_attachment(
        self,
        target_name: str,
        filename: str,
        screenshot_path: str,
    ) -> dict:
        try:
            from openwukong.control.wechat_visual_evidence import verify_chat_attachment

            frame = recognize_frame(str(screenshot_path or ""), timeout=self.ocr_timeout)
            return verify_chat_attachment(
                screenshot_path,
                frame,
                target_name=target_name,
                filename=filename,
            )
        except Exception as exc:
            return {
                "verified": False,
                "method": "positioned-chat-attachment-readback",
                "target_name": target_name,
                "filename": filename,
                "error": f"positioned_ocr_error:{exc.__class__.__name__}",
            }

    def verify_moments_surface(self, screenshot_path: str) -> bool:
        from openwukong.control.wechat_visual_evidence import find_moments_surface

        try:
            frame = recognize_frame(str(screenshot_path or ""), timeout=self.ocr_timeout)
            return bool(find_moments_surface(frame).get("verified"))
        except Exception:
            return False

    def verify_publish_panel(self, screenshot_path: str) -> bool:
        from openwukong.control.wechat_visual_evidence import find_publish_panel

        try:
            frame = recognize_frame(str(screenshot_path or ""), timeout=self.ocr_timeout)
            return bool(find_publish_panel(frame).get("verified"))
        except Exception:
            return False

    def verify_published_body(
        self,
        body: str,
        before_screenshot_path: str,
        after_screenshot_path: str = "",
    ) -> dict:
        from openwukong.control.wechat_visual_evidence import (
            recognize_frame,
            verify_moments_publish,
        )

        after_path = after_screenshot_path or before_screenshot_path
        try:
            before = recognize_frame(
                str(before_screenshot_path or ""),
                timeout=self.ocr_timeout,
            )
            after = recognize_frame(str(after_path or ""), timeout=self.ocr_timeout)
            return verify_moments_publish(
                after_path,
                before,
                after,
                body=body,
            )
        except Exception as exc:
            return {
                "verified": False,
                "method": "positioned-moments-publish-readback",
                "error": f"positioned_ocr_error:{exc.__class__.__name__}",
            }

    def restore_clipboard(self) -> None:
        if self._saved_clipboard is not None:
            try:
                import pyperclip

                pyperclip.copy(self._saved_clipboard)
            finally:
                self._saved_clipboard = None
        if self._saved_file_clipboard is not None:
            try:
                self._file_clipboard.restore_text(self._saved_file_clipboard)
            finally:
                self._saved_file_clipboard = None

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
    restore_fields: dict = {}
    send_attempts = 0
    window_hwnd = 0
    previous_hwnd = 0
    screenshot = ""
    post_send_screenshot = ""
    try:
        window_hwnd = int(active.find_wechat_window())
        previous_hwnd = int(active.get_foreground_window())
        phases.append({"phase": "bind_window", "status": "ok", "window_hwnd": window_hwnd})
        if not active.set_foreground_window(window_hwnd):
            raise RuntimeError("wechat_foreground_activation_failed")
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
            restore_fields = _restore_foreground(active, previous_hwnd)
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
                **restore_fields,
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
        send_attempts = 1
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
        restore_fields = _restore_foreground(active, previous_hwnd)
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
            **restore_fields,
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
                restore_fields = _restore_foreground(active, previous_hwnd)
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
            send_attempts=send_attempts,
            keyboard_input_attempts=keyboard_inputs,
            clipboard_write_attempts=clipboard_writes,
            clipboard_restore_attempts=clipboard_restores,
            foreground_restore_attempts=foreground_restores,
            **restore_fields,
            window_hwnd=window_hwnd,
            previous_foreground_hwnd=previous_hwnd,
            pre_send_screenshot_path=screenshot,
            post_send_screenshot_path=post_send_screenshot,
            phases=tuple(phases),
            error=str(exc),
            **takeover_fields,
        )


def run_wechat_file_helper_attachment_probe(
    *,
    file_path: str | Path,
    authorized_root: str | Path,
    target_name: str = _FILE_HELPER_TARGET,
    allow_send: bool = False,
    automation: object | None = None,
    output_dir: str | Path = "",
    foreground_takeover_request: ForegroundTakeoverRequest | dict | None = None,
    max_file_size: int = 100 * 1024 * 1024,
):
    started = time.perf_counter()
    target = str(target_name or "").strip()
    path = Path(str(file_path or "")).expanduser().resolve()
    root_text = str(authorized_root or "").strip()
    root = Path(root_text).expanduser().resolve()
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    file_hash = ""
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        file_hash = digest.hexdigest()

    def build(status: str, **kwargs):
        report = WeChatAttachmentSendReport(
            status=status,
            target_name=target,
            file_name=path.name,
            file_size=file_size,
            file_sha256=file_hash,
            allow_send=allow_send,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            **kwargs,
        )
        artifact = str(report.artifact_path or "")
        if artifact:
            artifact_path = Path(artifact)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return report

    if not allow_send:
        return build("blocked_requires_explicit_opt_in")
    if target != _FILE_HELPER_TARGET:
        return build("blocked_external_target_requires_explicit_permission")
    if not root_text:
        return build("blocked_authorized_root_required")
    if not path.is_file():
        return build("blocked_file_not_found")
    if file_size > max_file_size:
        return build("blocked_file_too_large")
    try:
        path.relative_to(root)
    except ValueError:
        return build("blocked_file_outside_authorized_root")

    validation = validate_foreground_takeover_request(
        foreground_takeover_request,
        action="send_file",
        target_process_names=("weixin.exe", "wechat.exe"),
        selected_transport="foreground-keyboard-clipboard",
    )
    takeover_fields = _takeover_report_fields(validation)
    if not validation.valid:
        return build(
            "blocked_foreground_takeover_request_required"
            if validation.decision == "missing_foreground_takeover_request"
            else "blocked_foreground_takeover_request_invalid",
            error=validation.decision,
            **takeover_fields,
        )

    active = automation or Win32WeChatKeyboardAutomation()
    run_root = Path(
        output_dir
        or Path("logs") / "runtime" / "wechat-file-helper-attachment-send"
    ).resolve()
    pre_path = run_root / "pre_send_target.png"
    post_path = run_root / "post_send_verify.png"
    artifact_path = run_root / "report.json"
    phases: list[dict] = []
    keyboard_inputs = 0
    clipboard_writes = 0
    clipboard_restores = 0
    foreground_restores = 0
    send_attempts = 0
    restore_fields: dict = {}
    window_hwnd = 0
    previous_hwnd = 0
    try:
        window_hwnd = int(active.find_wechat_window())
        previous_hwnd = int(active.get_foreground_window())
        phases.append(
            {"phase": "bind_window", "status": "ok", "window_hwnd": window_hwnd}
        )
        if not active.set_foreground_window(window_hwnd):
            raise RuntimeError("wechat_foreground_activation_failed")
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
        pre = str(active.screenshot(pre_path))
        phases.append({"phase": "open_target", "status": "ok", "screenshot_path": pre})
        target_verified = bool(active.verify_target(target, pre))
        phases.append(
            {
                "phase": "verify_target",
                "status": "ok" if target_verified else "blocked",
                "target_verified": target_verified,
            }
        )
        if not target_verified:
            active.restore_clipboard()
            clipboard_restores += 1
            restore_fields = _restore_foreground(active, previous_hwnd)
            foreground_restores += int(previous_hwnd > 0)
            phases.append({"phase": "restore_state", "status": "ok"})
            return build(
                "blocked_target_not_verified",
                clipboard_write_attempts=clipboard_writes,
                clipboard_restore_attempts=clipboard_restores,
                foreground_restore_attempts=foreground_restores,
                target_verified=False,
                pre_send_screenshot_path=pre,
                artifact_path=str(artifact_path),
                phases=tuple(phases),
                **restore_fields,
                **takeover_fields,
            )
        active.paste_files([str(path)])
        clipboard_writes += 1
        send_attempts = 1
        active.press("enter")
        keyboard_inputs += 1
        active.sleep(1.0)
        post = _capture_bound_screenshot(active, window_hwnd, post_path)
        verification = _verify_post_send_attachment(active, target, path.name, post)
        verified = bool(verification.get("verified"))
        phases.append(
            {
                "phase": "send_file",
                "status": "ok",
                "send_attempts": 1,
                "post_send_screenshot_bound": bool(post),
            }
        )
        phases.append(
            {
                "phase": "post_action_verify",
                "status": "ok" if verified else "unverified",
                "verified": verified,
            }
        )
        active.restore_clipboard()
        clipboard_restores += 1
        restore_fields = _restore_foreground(active, previous_hwnd)
        foreground_restores += int(previous_hwnd > 0)
        phases.append({"phase": "restore_state", "status": "ok"})
        return build(
            "sent" if verified else "unverified",
            control_allowed=True,
            send_attempts=send_attempts,
            keyboard_input_attempts=keyboard_inputs,
            clipboard_write_attempts=clipboard_writes,
            clipboard_restore_attempts=clipboard_restores,
            foreground_restore_attempts=foreground_restores,
            target_verified=True,
            post_send_verified=verified,
            post_send_verification=verification,
            pre_send_screenshot_path=pre,
            post_send_screenshot_path=post,
            post_send_screenshot_bound=bool(post),
            artifact_path=str(artifact_path),
            phases=tuple(phases),
            **restore_fields,
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
                restore_fields = _restore_foreground(active, previous_hwnd)
                foreground_restores += 1
            except Exception:
                pass
        phases.append({"phase": "failed", "status": "failed", "error": str(exc)})
        return build(
            "failed",
            control_allowed=bool(send_attempts),
            send_attempts=send_attempts,
            keyboard_input_attempts=keyboard_inputs,
            clipboard_write_attempts=clipboard_writes,
            clipboard_restore_attempts=clipboard_restores,
            foreground_restore_attempts=foreground_restores,
            artifact_path=str(artifact_path),
            phases=tuple(phases),
            error=str(exc),
            **restore_fields,
            **takeover_fields,
        )


@dataclasses.dataclass(frozen=True)
class WeChatAttachmentSendReport:
    status: str
    target_name: str
    file_name: str
    file_size: int
    file_sha256: str
    allow_send: bool
    control_allowed: bool = False
    send_attempts: int = 0
    keyboard_input_attempts: int = 0
    clipboard_write_attempts: int = 0
    clipboard_restore_attempts: int = 0
    foreground_restore_attempts: int = 0
    foreground_restored: bool | None = None
    final_foreground_hwnd: int = 0
    target_verified: bool = False
    post_send_verified: bool = False
    post_send_verification: dict = dataclasses.field(default_factory=dict)
    pre_send_screenshot_path: str = ""
    post_send_screenshot_path: str = ""
    post_send_screenshot_bound: bool = False
    artifact_path: str = ""
    transport: str = "foreground-keyboard-clipboard"
    foreground_takeover_validated: bool = False
    foreground_takeover_validation: dict = dataclasses.field(default_factory=dict)
    foreground_takeover_request: dict = dataclasses.field(default_factory=dict)
    phases: tuple[dict, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": "wechat-file-helper-attachment-send-probe",
            "safety_mode": "explicit_opt_in_real_send",
            "status": self.status,
            "target_name": self.target_name,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_sha256": self.file_sha256,
            "allow_send": self.allow_send,
            "control_allowed": self.control_allowed,
            "send_attempts": self.send_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "clipboard_restore_attempts": self.clipboard_restore_attempts,
            "foreground_restore_attempts": self.foreground_restore_attempts,
            "foreground_restored": self.foreground_restored,
            "final_foreground_hwnd": self.final_foreground_hwnd,
            "target_verified": self.target_verified,
            "post_send_verified": self.post_send_verified,
            "post_send_verification": dict(self.post_send_verification),
            "pre_send_screenshot_path": self.pre_send_screenshot_path,
            "post_send_screenshot_path": self.post_send_screenshot_path,
            "post_send_screenshot_bound": self.post_send_screenshot_bound,
            "artifact_path": self.artifact_path,
            "transport": self.transport,
            "foreground_takeover_validated": self.foreground_takeover_validated,
            "foreground_takeover_validation": dict(self.foreground_takeover_validation),
            "phases": [dict(phase) for phase in self.phases],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def _restore_foreground(active: object, hwnd: int) -> dict:
    if int(hwnd or 0) <= 0:
        return {"foreground_restored": None, "final_foreground_hwnd": 0}
    active.set_foreground_window(int(hwnd))
    final_hwnd = int(active.get_foreground_window() or 0)
    return {
        "foreground_restored": final_hwnd == int(hwnd),
        "final_foreground_hwnd": final_hwnd,
    }


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


def _verify_post_send_attachment(
    active: object,
    target_name: str,
    filename: str,
    screenshot_path: str,
) -> dict:
    verifier = getattr(active, "verify_post_send_attachment", None)
    if callable(verifier):
        try:
            result = verifier(target_name, filename, screenshot_path)
        except Exception as exc:
            return {
                "verified": False,
                "method": "positioned-chat-attachment-readback",
                "error": f"attachment_verifier_error:{exc.__class__.__name__}",
            }
        return dict(result) if isinstance(result, dict) else {
            "verified": False,
            "method": "positioned-chat-attachment-readback",
            "error": "attachment_verifier_invalid_result",
        }
    try:
        frame = recognize_frame(screenshot_path, timeout=20)
        return verify_chat_attachment(
            screenshot_path,
            frame,
            target_name=target_name,
            filename=filename,
        )
    except Exception as exc:
        return {
            "verified": False,
            "method": "positioned-chat-attachment-readback",
            "error": f"positioned_ocr_error:{exc.__class__.__name__}",
        }


def verify_wechat_post_send_message_from_screenshot(
    *,
    target_name: str,
    message: str,
    screenshot_path: str,
    ocr_timeout: float = 20.0,
    ocr_runner: object | None = None,
) -> dict:
    """Verify a post-send WeChat screenshot contains the sent marker text."""

    path = Path(str(screenshot_path or ""))
    if not screenshot_path or not path.is_file():
        return {
            "verified": False,
            "method": "windows-media-ocr-readback",
            "target_name": target_name,
            "message_preview": _clip(message),
            "screenshot_path": screenshot_path,
            "error": "screenshot_missing",
        }
    runner = ocr_runner if callable(ocr_runner) else _windows_media_ocr_text_from_image
    ocr = runner(str(path), timeout=ocr_timeout)
    if not isinstance(ocr, dict):
        ocr = {"ok": False, "error": "ocr_runner_invalid_result"}
    text = str(ocr.get("text", "") or "")
    marker_seen = _message_seen_in_text(message, text)
    return {
        "verified": bool(ocr.get("ok", False) and marker_seen),
        "method": "windows-media-ocr-readback",
        "target_name": target_name,
        "message_preview": _clip(message),
        "screenshot_path": str(path),
        "ocr_method": str(ocr.get("method", "windows-media-ocr") or ""),
        "ocr_ok": bool(ocr.get("ok", False)),
        "ocr_text_preview": _clip(text, limit=1000),
        "normalized_marker_matched": bool(marker_seen),
        "normalized_marker": _normalize_ocr_match_text(message),
        "normalized_text_preview": _clip(_normalize_ocr_match_text(text), limit=1000),
        "error": str(ocr.get("error", "") or ""),
    }


def _message_seen_in_text(message: str, text: str) -> bool:
    if not message or not text:
        return False
    if str(message) in str(text):
        return True
    marker = _normalize_ocr_match_text(message)
    haystack = _normalize_ocr_match_text(text)
    return bool(marker and marker in haystack)


def _normalize_ocr_match_text(value: str) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _windows_media_ocr_text_from_image(path: str, *, timeout: float = 20.0) -> dict:
    if not sys.platform.startswith("win"):
        return {
            "ok": False,
            "method": "windows-media-ocr",
            "text": "",
            "error": "windows_ocr_requires_windows",
        }
    target = Path(str(path or ""))
    if not target.is_file():
        return {
            "ok": False,
            "method": "windows-media-ocr",
            "text": "",
            "error": "image_missing",
        }
    try:
        text = _run_async_blocking(_python_winrt_ocr_text_from_image(target), timeout=timeout)
    except ImportError as exc:
        missing_name = getattr(exc, "name", "") or exc.__class__.__name__
        return {
            "ok": False,
            "method": "windows-media-ocr",
            "text": "",
            "error": f"python_winrt_ocr_unavailable:{missing_name}",
        }
    except TimeoutError:
        return {
            "ok": False,
            "method": "windows-media-ocr",
            "text": "",
            "error": "ocr_timeout",
        }
    except Exception as exc:
        return {
            "ok": False,
            "method": "windows-media-ocr",
            "text": "",
            "error": f"ocr_error:{exc.__class__.__name__}:{exc}",
        }
    return {
        "ok": True,
        "method": "python-winrt-windows-media-ocr",
        "text": str(text or "").strip(),
        "error": "",
    }


async def _python_winrt_ocr_text_from_image(path: Path) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    try:
        writer.write_bytes(path.read_bytes())
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("ocr_engine_unavailable")
        result = await engine.recognize_async(bitmap)
        return str(result.text or "")
    finally:
        for closeable in (writer, stream):
            close = getattr(closeable, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass


def _run_async_blocking(coro, *, timeout: float):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(asyncio.wait_for(coro, timeout=max(1.0, float(timeout or 0))))

    result: dict[str, object] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(
                asyncio.wait_for(coro, timeout=max(1.0, float(timeout or 0)))
            )
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=max(1.0, float(timeout or 0)) + 1.0)
    if thread.is_alive():
        raise TimeoutError("ocr_timeout")
    error = result.get("error")
    if isinstance(error, BaseException):
        raise error
    return result.get("value")


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


def _window_rectangle(window: object) -> tuple[int, int, int, int]:
    rectangle = getattr(window, "rectangle", None)
    if not callable(rectangle):
        raise RuntimeError("wechat_window_rectangle_unavailable")
    rect = rectangle()
    values = (
        int(getattr(rect, "left", 0)),
        int(getattr(rect, "top", 0)),
        int(getattr(rect, "right", 0)),
        int(getattr(rect, "bottom", 0)),
    )
    if values[2] <= values[0] or values[3] <= values[1]:
        raise RuntimeError("wechat_window_rectangle_invalid")
    return values


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
