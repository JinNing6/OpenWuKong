# -*- coding: utf-8 -*-
"""Local WeChat native bridge endpoint publisher.

This module owns only the local HTTP/registry envelope. The actual WeChat
operation backend must be injected by a native adapter; the default backend is
intentionally not send-ready.
"""

from __future__ import annotations

import argparse
import dataclasses
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Protocol

from openwukong.control.wechat_native_bridge_registry import (
    WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION,
)


@dataclasses.dataclass(frozen=True)
class WeChatNativeEndpointConfig:
    host: str = "127.0.0.1"
    port: int = 0
    registry_path: str = ""
    process_name: str = "Weixin.exe"
    pid: int = 0
    hwnd: int = 0
    window_title: str = ""
    conversation_name: str = "File Transfer Assistant"
    conversation_id: str = ""
    backend: str = "read-only-evidence"
    capture_dir: str = "logs/runtime/wechat-native-bridge/captures"
    capability_timeout_sec: float = 5.0
    accessibility_backend: str = "win32"
    accessibility_max_windows: int = 30
    accessibility_max_elements_per_window: int = 0
    msaa_enabled: bool = False
    external_command: tuple[str, ...] = ()
    external_command_timeout_sec: float = 10.0


class WeChatNativeBackend(Protocol):
    def capabilities(self, target_name: str) -> dict:
        ...

    def send_message(self, payload: dict) -> dict:
        ...


class UnavailableWeChatNativeBackend:
    def capabilities(self, target_name: str) -> dict:
        del target_name
        return {
            "ok": False,
            "error": "wechat_native_backend_not_configured",
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "capabilities": [],
            "targets": [],
        }

    def send_message(self, payload: dict) -> dict:
        del payload
        return {
            "ok": False,
            "sent": False,
            "error": "wechat_native_backend_not_configured",
            "foreground_focus_stable": True,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }


class ExternalCommandWeChatNativeBackend:
    """Delegates WeChat native bridge operations to an explicit local command.

    The command receives one JSON object on stdin and must return one JSON
    object on stdout. This adapter never invokes a shell and never performs
    keyboard, mouse, clipboard, or foreground window input itself.
    """

    schema_version = "openwukong-wechat-native-external-command-v1"

    def __init__(self, config: WeChatNativeEndpointConfig):
        self.config = config

    def capabilities(self, target_name: str) -> dict:
        if not self.config.external_command:
            return self._blocked_capabilities("wechat_native_external_command_not_configured")
        result = self._run_external_command(
            {
                "schema_version": self.schema_version,
                "action": "capabilities",
                "target_name": target_name,
            },
            fallback_error="wechat_native_external_capabilities_failed",
        )
        if not result.get("ok", False):
            return self._blocked_capabilities(
                str(result.get("error", "") or "wechat_native_external_capabilities_failed"),
                external_result=result,
            )
        safety_error = self._capability_safety_error(result)
        if safety_error:
            return self._blocked_capabilities(safety_error, external_result=result)
        return self._with_external_defaults(result)

    def send_message(self, payload: dict) -> dict:
        if not self.config.external_command:
            return self._blocked_send("wechat_native_external_command_not_configured")
        result = self._run_external_command(
            {
                "schema_version": self.schema_version,
                "action": "send_message",
                "payload": dict(payload or {}),
                "target_name": str((payload or {}).get("target_name", "") or ""),
                "message": str((payload or {}).get("message", "") or ""),
            },
            fallback_error="wechat_native_external_send_failed",
        )
        if not result.get("ok", False):
            return self._blocked_send(
                str(result.get("error", "") or "wechat_native_external_send_failed"),
                external_result=result,
            )
        safety_error = self._send_safety_error(result)
        if safety_error:
            return self._blocked_send(safety_error, external_result=result)
        return self._with_external_defaults(result)

    def _run_external_command(self, request: dict, *, fallback_error: str) -> dict:
        command = tuple(str(item) for item in self.config.external_command if str(item))
        if not command:
            return {"ok": False, "error": "wechat_native_external_command_not_configured"}
        body = json.dumps(request, ensure_ascii=False)
        try:
            completed = subprocess.run(
                list(command),
                input=body,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(0.1, float(self.config.external_command_timeout_sec or 0)),
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "wechat_native_external_command_timeout"}
        except OSError as exc:
            return {
                "ok": False,
                "error": f"wechat_native_external_command_os_error:{exc.__class__.__name__}",
            }
        stdout = str(completed.stdout or "").strip()
        if int(completed.returncode or 0) != 0:
            return {
                "ok": False,
                "error": fallback_error,
                "external_returncode": int(completed.returncode or 0),
                "external_stderr": _bounded_text(completed.stderr),
            }
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "wechat_native_external_command_invalid_json",
                "external_stdout": _bounded_text(stdout),
                "external_stderr": _bounded_text(completed.stderr),
            }
        if not isinstance(data, dict):
            return {"ok": False, "error": "wechat_native_external_command_response_not_object"}
        data.setdefault("external_command_attempts", 1)
        return data

    def _with_external_defaults(self, data: dict) -> dict:
        result = dict(data)
        result.setdefault("backend", "external-command")
        result.setdefault("requires_foreground", False)
        result.setdefault("foreground_required", False)
        result.setdefault("window_input_required", False)
        result.setdefault("keyboard_input_required", False)
        result.setdefault("mouse_input_required", False)
        result.setdefault("clipboard_required", False)
        result.setdefault("control_attempts", 0)
        result.setdefault("window_input_attempts", 0)
        result.setdefault("keyboard_input_attempts", 0)
        result.setdefault("clipboard_write_attempts", 0)
        result.setdefault("foreground_focus_stable", True)
        return result

    def _capability_safety_error(self, data: dict) -> str:
        missing = []
        if "background_safe" not in data and "native_background_safe" not in data:
            missing.append("background_safe")
        for key in _EXTERNAL_UNSAFE_KEYS:
            if key not in data:
                missing.append(key)
            elif bool(data.get(key, False)):
                return f"wechat_native_external_capability_unsafe:{key}"
        if missing:
            return "wechat_native_external_capability_safety_not_declared:" + ",".join(
                missing
            )
        if not bool(data.get("background_safe", data.get("native_background_safe", False))):
            return "wechat_native_external_capability_background_not_safe"
        return ""

    def _send_safety_error(self, data: dict) -> str:
        missing = []
        if "foreground_focus_stable" not in data and "foreground_changed" not in data:
            missing.append("foreground_focus_stable")
        for key in _EXTERNAL_SEND_COUNTER_KEYS:
            if key not in data:
                missing.append(key)
            elif _int_value(data, key) != 0:
                return f"wechat_native_external_send_input_attempted:{key}"
        if missing:
            return "wechat_native_external_send_safety_not_declared:" + ",".join(missing)
        if "foreground_focus_stable" in data and not bool(data.get("foreground_focus_stable")):
            return "wechat_native_external_send_foreground_changed"
        if bool(data.get("foreground_changed", False)):
            return "wechat_native_external_send_foreground_changed"
        return ""

    def _blocked_capabilities(
        self,
        error: str,
        *,
        external_result: dict | None = None,
    ) -> dict:
        result = {
            "ok": False,
            "error": error,
            "backend": "external-command",
            "background_safe": True,
            "native_background_safe": True,
            "requires_foreground": False,
            "foreground_required": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "send_action_ready": False,
            "send_ready": False,
            "can_send": False,
            "capabilities": [],
            "targets": [],
        }
        if external_result:
            result["external_result"] = dict(external_result)
        return result

    def _blocked_send(
        self,
        error: str,
        *,
        external_result: dict | None = None,
    ) -> dict:
        result = {
            "ok": False,
            "sent": False,
            "error": error,
            "backend": "external-command",
            "foreground_focus_stable": True,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }
        if external_result:
            result["external_result"] = dict(external_result)
        return result


class LiveWeChatEvidenceBackend:
    """Read-only live WeChat evidence backend.

    The backend publishes locator and background screenshot evidence only.
    Sending stays blocked until a native adapter proves a deterministic
    no-foreground write path.
    """

    def __init__(
        self,
        config: WeChatNativeEndpointConfig,
        *,
        accessibility_observer: object | None = None,
        win32_observer: object | None = None,
        msaa_observer: object | None = None,
        capture_provider: object | None = None,
        capture_dir: str | Path | None = None,
    ):
        self.config = config
        self._accessibility_observer = accessibility_observer
        self._win32_observer = win32_observer
        self._msaa_observer = msaa_observer
        self._capture_provider = capture_provider
        self._capture_dir = Path(capture_dir or config.capture_dir)

    def capabilities(self, target_name: str) -> dict:
        return self._capabilities_with_timeout(target_name)

    def _capabilities_with_timeout(self, target_name: str) -> dict:
        import queue

        timeout = max(0.01, float(self.config.capability_timeout_sec or 0))
        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                result_queue.put(self._capabilities_sync(target_name))
            except Exception as exc:
                result_queue.put(_live_evidence_exception_report(exc))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            return _live_evidence_timeout_report()
        try:
            data = result_queue.get_nowait()
        except queue.Empty:
            return _live_evidence_timeout_report()
        return dict(data) if isinstance(data, dict) else _live_evidence_timeout_report()

    def _capabilities_sync(self, target_name: str) -> dict:
        locator_report = self._build_locator_report()
        locator_data = locator_report.to_dict(include_children=False)
        captures = self._capture_windows(locator_report.windows)
        capture_dicts = [item.to_dict() for item in captures]
        screenshot_success_count = sum(1 for item in captures if item.ok)
        screenshot_focus_stable = bool(captures) and not any(
            item.foreground_focus_risk for item in captures
        )
        target = self._target_summary(target_name, locator_report, captures)
        has_top_level_hwnd = any(
            int(getattr(window, "top_level_hwnd", 0) or 0) > 0
            for window in locator_report.windows
        )
        ok = bool(locator_report.read_only_verified and has_top_level_hwnd)
        return {
            "ok": ok,
            "error": _live_evidence_error(locator_report, has_top_level_hwnd),
            "backend": "read-only-evidence",
            "background_safe": True,
            "native_background_safe": True,
            "requires_foreground": False,
            "foreground_required": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "send_action_ready": False,
            "send_ready": False,
            "can_send": False,
            "capabilities": ["wechat.conversation.read_only_evidence"],
            "targets": [target] if target else [],
            "target": target,
            "locator_report": locator_data,
            "background_screenshot_focus_stable": screenshot_focus_stable,
            "background_screenshot_count": len(captures),
            "background_screenshot_success_count": screenshot_success_count,
            "background_screenshots": capture_dicts,
        }

    def send_message(self, payload: dict) -> dict:
        del payload
        return {
            "ok": False,
            "sent": False,
            "error": "wechat_native_send_backend_not_configured",
            "foreground_focus_stable": True,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def _build_locator_report(self):
        from openwukong.evaluation.accessibility_probe import (
            PywinautoAccessibilityObserver,
        )
        from openwukong.evaluation.wechat_locator import (
            StaticMsaaObserver,
            build_wechat_locator_report,
        )

        observer = self._accessibility_observer or self._default_accessibility_observer(
            PywinautoAccessibilityObserver
        )
        windows = tuple(observer.snapshot())
        msaa_observer = self._msaa_observer
        if msaa_observer is None and not bool(self.config.msaa_enabled):
            msaa_observer = StaticMsaaObserver({})
        return build_wechat_locator_report(
            windows,
            win32_observer=self._win32_observer,
            msaa_observer=msaa_observer,
        )

    def _default_accessibility_observer(self, pywinauto_observer_class):
        backend = str(self.config.accessibility_backend or "").strip().casefold()
        if backend in {"", "win32", "fast-win32", "fast_win32"}:
            return FastWin32AccessibilityObserver(
                max_windows=max(1, int(self.config.accessibility_max_windows or 1))
            )
        return pywinauto_observer_class(
            max_windows=max(1, int(self.config.accessibility_max_windows or 1)),
            max_elements_per_window=max(
                0,
                int(self.config.accessibility_max_elements_per_window or 0),
            ),
        )

    def _capture_windows(self, windows: tuple) -> tuple:
        provider = self._capture_provider
        if provider is None:
            from openwukong.evaluation.window_capture import (
                PrintWindowBackgroundCaptureProvider,
            )

            provider = PrintWindowBackgroundCaptureProvider()
        captures = []
        for index, window in enumerate(windows):
            hwnd = int(getattr(window, "top_level_hwnd", 0) or 0)
            if hwnd <= 0:
                continue
            output_path = self._capture_dir / (
                f"wechat-{int(getattr(window, 'pid', 0) or 0)}-{hwnd}-{index}.png"
            )
            try:
                captures.append(provider.capture_window(hwnd, output_path))
            except Exception as exc:
                captures.append(_capture_exception_report(hwnd, output_path, exc))
        return tuple(captures)

    def _target_summary(self, target_name: str, locator_report, captures: tuple) -> dict:
        if not locator_report.windows:
            return {}
        window = locator_report.windows[0]
        if int(window.top_level_hwnd or 0) <= 0:
            return {}
        requested_name = str(target_name or self.config.conversation_name or "").strip()
        conversation_verified = _conversation_name_matches_window_title(
            requested_name,
            window.window_title,
            conversation_id=self.config.conversation_id,
        )
        return {
            "name": requested_name,
            "conversation_name": self.config.conversation_name,
            "conversation_id": self.config.conversation_id,
            "available": conversation_verified,
            "conversation_verified": conversation_verified,
            "availability_reason": (
                "" if conversation_verified else "wechat_conversation_not_verified"
            ),
            "process_name": window.process_name,
            "pid": int(window.pid or 0),
            "hwnd": int(window.top_level_hwnd or 0),
            "window_title": window.window_title,
            "background_screenshot_count": len(captures),
            "background_screenshot_success_count": sum(1 for item in captures if item.ok),
        }


class FastWin32AccessibilityObserver:
    """Fast read-only top-level window observer used by live endpoints."""

    def __init__(self, *, max_windows: int = 30):
        self.max_windows = max(1, int(max_windows or 1))

    def snapshot(self) -> tuple:
        from openwukong.evaluation.accessibility_probe import (
            _capture_process_only_fallback_windows,
            _capture_win32_top_level_windows,
            _merge_process_only_fallback_windows,
        )

        windows = _capture_win32_top_level_windows()
        return _merge_process_only_fallback_windows(
            windows,
            _capture_process_only_fallback_windows(),
            max_windows=self.max_windows,
        )


class WeChatNativeEndpointPublisher:
    def __init__(
        self,
        config: WeChatNativeEndpointConfig,
        *,
        backend: WeChatNativeBackend | None = None,
    ):
        self.config = config
        self.backend = backend or UnavailableWeChatNativeBackend()
        self.bridge_url = ""
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "WeChatNativeEndpointPublisher":
        self.start(background=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self.stop()

    def start(self, *, background: bool = True) -> str:
        if self._server is not None:
            return self.bridge_url
        handler = make_wechat_native_endpoint_handler(self.backend)
        server = http.server.ThreadingHTTPServer(
            (self.config.host, int(self.config.port or 0)),
            handler,
        )
        server.daemon_threads = True
        self._server = server
        host, port = server.server_address
        display_host = self.config.host or str(host or "127.0.0.1")
        self.bridge_url = f"http://{display_host}:{int(port)}"
        if self.config.registry_path:
            write_wechat_native_bridge_registry(
                self.config.registry_path,
                bridge_url=self.bridge_url,
                config=self.config,
            )
        if background:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self._thread = thread
        return self.bridge_url

    def serve_forever(self) -> None:
        if self._server is None:
            self.start(background=False)
        server = self._server
        if server is None:
            raise RuntimeError("wechat_native_endpoint_server_not_started")
        server.serve_forever()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)


def make_wechat_native_endpoint_handler(backend: WeChatNativeBackend):
    class WeChatNativeEndpointHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payload = self._read_json_body()
            if self.path == "/v1/wechat/capabilities":
                target_name = str(payload.get("target_name", "") or "")
                self._send_json(backend.capabilities(target_name))
                return
            if self.path == "/v1/wechat/send":
                self._send_json(backend.send_message(payload))
                return
            self._send_json({"ok": False, "error": "not_found"}, status=404)

        def _read_json_body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length else b""
            try:
                data = json.loads(raw.decode("utf-8-sig")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = {}
            return dict(data) if isinstance(data, dict) else {}

        def _send_json(self, data: dict, *, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args) -> None:
            del format, args

    return WeChatNativeEndpointHandler


def write_wechat_native_bridge_registry(
    registry_path: str | Path,
    *,
    bridge_url: str,
    config: WeChatNativeEndpointConfig,
) -> None:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = _normalized_real_bridge_url(bridge_url)
    entry = {
        "url": url,
        "bridge_url": url,
        "type": "wechat_native_bridge",
        "surface_kind": "desktop_app",
        "enabled": True,
        "app_binding": {
            "process_name": config.process_name,
            "pid": int(config.pid or 0),
            "hwnd": int(config.hwnd or 0),
            "window_title": config.window_title,
        },
        "target": {
            "conversation_name": config.conversation_name,
            "conversation_id": config.conversation_id,
        },
    }
    data = {
        "schema_version": WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION,
        "wechat_native_bridges": _merged_registry_entries(path, entry),
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a local WeChat native bridge endpoint publisher."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local bridge port. Use 0 to let the operating system assign one.",
    )
    parser.add_argument("--registry-path", default="")
    parser.add_argument("--process-name", default="Weixin.exe")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--hwnd", type=int, default=0)
    parser.add_argument("--window-title", default="")
    parser.add_argument("--conversation-name", default="File Transfer Assistant")
    parser.add_argument("--conversation-id", default="")
    parser.add_argument(
        "--backend",
        choices=("read-only-evidence", "external-command", "unavailable"),
        default="read-only-evidence",
    )
    parser.add_argument(
        "--capture-dir",
        default="logs/runtime/wechat-native-bridge/captures",
    )
    parser.add_argument("--capability-timeout-sec", type=float, default=5.0)
    parser.add_argument(
        "--accessibility-backend",
        choices=("win32", "uia"),
        default="win32",
    )
    parser.add_argument("--accessibility-max-windows", type=int, default=30)
    parser.add_argument("--accessibility-max-elements-per-window", type=int, default=0)
    parser.add_argument("--enable-msaa", action="store_true")
    parser.add_argument(
        "--external-command-json",
        default="",
        help="JSON array argv for --backend external-command.",
    )
    parser.add_argument(
        "--external-command-timeout-sec",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--serve-once",
        action="store_true",
        help="Start, publish the registry entry, print the URL, and exit.",
    )
    args = parser.parse_args(argv)
    external_command = _external_command_from_args_or_env(args.external_command_json)

    config = WeChatNativeEndpointConfig(
        host=args.host,
        port=args.port,
        registry_path=args.registry_path,
        process_name=args.process_name,
        pid=args.pid,
        hwnd=args.hwnd,
        window_title=args.window_title,
        conversation_name=args.conversation_name,
        conversation_id=args.conversation_id,
        backend=args.backend,
        capture_dir=args.capture_dir,
        capability_timeout_sec=args.capability_timeout_sec,
        accessibility_backend=args.accessibility_backend,
        accessibility_max_windows=args.accessibility_max_windows,
        accessibility_max_elements_per_window=args.accessibility_max_elements_per_window,
        msaa_enabled=args.enable_msaa,
        external_command=external_command,
        external_command_timeout_sec=args.external_command_timeout_sec,
    )
    publisher = WeChatNativeEndpointPublisher(
        config,
        backend=build_wechat_native_backend(args.backend, config),
    )
    bridge_url = publisher.start(background=bool(args.serve_once))
    _write_stdout(f"wechat_native_bridge_url={bridge_url}")
    if args.serve_once:
        publisher.stop()
        return 0
    try:
        publisher.serve_forever()
    finally:
        publisher.stop()
    return 0


def _merged_registry_entries(path: Path, new_entry: dict) -> list[dict]:
    existing_entries: list[dict] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            raw_entries = data.get("wechat_native_bridges", [])
            if isinstance(raw_entries, list):
                existing_entries = [
                    dict(entry) for entry in raw_entries if isinstance(entry, dict)
                ]
        except Exception:
            existing_entries = []

    new_url = str(new_entry.get("url", "") or "").strip().rstrip("/")
    new_process_name = _entry_process_name(new_entry)
    new_conversation_name = _entry_conversation_name(new_entry)
    merged: list[dict] = []
    for entry in existing_entries:
        existing_url = str(entry.get("url", "") or entry.get("bridge_url", "") or "").strip().rstrip("/")
        same_url = bool(new_url and existing_url == new_url)
        same_target = bool(
            new_process_name
            and new_process_name == _entry_process_name(entry)
            and new_conversation_name
            and new_conversation_name == _entry_conversation_name(entry)
        )
        if same_url or same_target:
            continue
        merged.append(entry)
    merged.append(dict(new_entry))
    return merged


def build_wechat_native_backend(
    backend: str,
    config: WeChatNativeEndpointConfig,
) -> WeChatNativeBackend:
    value = str(backend or "").strip().casefold()
    if value in {"", "read-only-evidence", "read_only_evidence"}:
        return LiveWeChatEvidenceBackend(config)
    if value in {"external-command", "external_command"}:
        return ExternalCommandWeChatNativeBackend(config)
    if value == "unavailable":
        return UnavailableWeChatNativeBackend()
    raise ValueError(f"unsupported_wechat_native_backend:{backend}")


def _live_evidence_error(locator_report, has_top_level_hwnd: bool) -> str:
    if not bool(locator_report.read_only_verified):
        return "wechat_window_not_found"
    if not has_top_level_hwnd:
        return "wechat_top_level_hwnd_missing"
    return ""


def _conversation_name_matches_window_title(
    target_name: str,
    window_title: str,
    *,
    conversation_id: str = "",
) -> bool:
    title = str(window_title or "").strip().casefold()
    if not title:
        return False
    for alias in _conversation_aliases(target_name, conversation_id=conversation_id):
        if alias and alias in title:
            return True
    return False


def _conversation_aliases(target_name: str, *, conversation_id: str = "") -> tuple[str, ...]:
    aliases = {
        str(target_name or "").strip().casefold(),
        str(conversation_id or "").strip().casefold(),
    }
    if "file transfer assistant" in aliases or "filehelper" in aliases:
        aliases.update(
            {
                "file transfer assistant",
                "filehelper",
                "文件传输助手",
                "文件傳輸助手",
            }
        )
    return tuple(item for item in aliases if item)


def _live_evidence_timeout_report() -> dict:
    return _blocked_live_evidence_report("wechat_live_evidence_timeout")


def _live_evidence_exception_report(exc: Exception) -> dict:
    return _blocked_live_evidence_report(
        f"wechat_live_evidence_exception:{type(exc).__name__}"
    )


def _blocked_live_evidence_report(error: str) -> dict:
    return {
        "ok": False,
        "error": error,
        "backend": "read-only-evidence",
        "background_safe": True,
        "native_background_safe": True,
        "requires_foreground": False,
        "foreground_required": False,
        "window_input_required": False,
        "keyboard_input_required": False,
        "mouse_input_required": False,
        "clipboard_required": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
        "send_action_ready": False,
        "send_ready": False,
        "can_send": False,
        "capabilities": ["wechat.conversation.read_only_evidence"],
        "targets": [],
        "target": {},
        "locator_report": {},
        "background_screenshot_focus_stable": False,
        "background_screenshot_count": 0,
        "background_screenshot_success_count": 0,
        "background_screenshots": [],
    }


def _capture_exception_report(hwnd: int, output_path: Path, exc: Exception):
    from openwukong.evaluation.window_capture import BackgroundWindowCaptureReport

    return BackgroundWindowCaptureReport(
        hwnd=int(hwnd or 0),
        output_path=str(output_path),
        ok=False,
        error=f"capture_exception:{type(exc).__name__}",
    )


def _normalized_real_bridge_url(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        raise ValueError("wechat_native_bridge_url_required")
    if text.endswith(":0"):
        raise ValueError("wechat_native_bridge_url_must_use_actual_port")
    return text


def _entry_process_name(entry: dict) -> str:
    binding = entry.get("app_binding")
    if not isinstance(binding, dict):
        binding = {}
    return str(binding.get("process_name", "") or "").strip().casefold()


def _entry_conversation_name(entry: dict) -> str:
    target = entry.get("target")
    if not isinstance(target, dict):
        target = {}
    return str(
        target.get("conversation_name", "")
        or target.get("name", "")
        or target.get("target_name", "")
        or ""
    ).strip().casefold()


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


def _external_command_from_args_or_env(value: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        text = str(os.environ.get("OPENWUKONG_WECHAT_NATIVE_EXTERNAL_COMMAND_JSON", "") or "").strip()
    if not text:
        return ()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("external_command_json_must_be_json_array") from exc
    if not isinstance(data, list) or not all(isinstance(item, str) and item for item in data):
        raise ValueError("external_command_json_must_be_nonempty_string_array")
    return tuple(data)


def _bounded_text(value: object, *, limit: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


_EXTERNAL_UNSAFE_KEYS = (
    "requires_foreground",
    "foreground_required",
    "window_input_required",
    "keyboard_input_required",
    "mouse_input_required",
    "clipboard_required",
)


_EXTERNAL_SEND_COUNTER_KEYS = (
    "control_attempts",
    "window_input_attempts",
    "keyboard_input_attempts",
    "clipboard_write_attempts",
)


def _int_value(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


__all__ = [
    "ExternalCommandWeChatNativeBackend",
    "FastWin32AccessibilityObserver",
    "LiveWeChatEvidenceBackend",
    "UnavailableWeChatNativeBackend",
    "WeChatNativeBackend",
    "WeChatNativeEndpointConfig",
    "WeChatNativeEndpointPublisher",
    "build_wechat_native_backend",
    "main",
    "make_wechat_native_endpoint_handler",
    "write_wechat_native_bridge_registry",
]


if __name__ == "__main__":
    raise SystemExit(main())
