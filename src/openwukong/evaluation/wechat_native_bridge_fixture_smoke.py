# -*- coding: utf-8 -*-
"""Owned local fixture smoke for the WeChat native bridge contract."""

from __future__ import annotations

import argparse
import dataclasses
import http.server
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeSenderAdapter,
    build_wechat_native_bridge_request,
)
from openwukong.control.wechat_native_bridge_registry import (
    WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION,
    discover_wechat_native_bridge_urls,
)


@dataclasses.dataclass(frozen=True)
class WeChatNativeBridgeFixtureSmokeReport:
    message: str
    required_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...]
    bridge_url: str
    registry: dict
    send_report: dict
    fixture: dict
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-bridge-fixture-smoke"

    @property
    def safety_mode(self) -> str:
        return "local_owned_wechat_native_bridge_fixture"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return _counter(self.send_report, "window_input_attempts")

    @property
    def native_call_attempts(self) -> int:
        return _counter(self.send_report, "native_call_attempts")

    @property
    def send_attempts(self) -> int:
        return _counter(self.send_report, "send_attempts")

    @property
    def ok(self) -> bool:
        return bool(
            self.send_report.get("ok", False)
            and self.send_report.get("decision") == "wechat_native_bridge_send_accepted"
            and self.native_call_attempts == 1
            and self.send_attempts == 1
            and self.window_input_attempts == 0
            and _counter(self.send_report, "keyboard_input_attempts") == 0
            and _counter(self.send_report, "clipboard_write_attempts") == 0
            and _counter(self.fixture, "capability_request_count") == 1
            and _counter(self.fixture, "send_request_count") == 1
            and self.bridge_url in self.registry.get("discovered_urls", [])
        )

    @property
    def decision(self) -> str:
        return (
            "wechat_native_bridge_fixture_smoke_verified"
            if self.ok
            else "wechat_native_bridge_fixture_smoke_failed"
        )

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
            "send_attempts": self.send_attempts,
            "message": self.message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "bridge_url": self.bridge_url,
            "registry": dict(self.registry),
            "send_report": dict(self.send_report),
            "fixture": dict(self.fixture),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_wechat_native_bridge_fixture_smoke(
    *,
    message: str = "OPENWUKONG_WECHAT_FIXTURE: PASS",
    required_markers: tuple[str, ...] = ("OPENWUKONG_WECHAT_FIXTURE: PASS",),
    forbidden_markers: tuple[str, ...] = (),
) -> WeChatNativeBridgeFixtureSmokeReport:
    started = time.perf_counter()
    message_text = str(message or "").strip()
    required = _string_tuple(required_markers)
    forbidden = _string_tuple(forbidden_markers)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with _LocalWeChatNativeBridgeFixture() as fixture:
            registry_path = root / "wechat-native-bridges.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION,
                        "wechat_native_bridges": [
                            {
                                "type": "wechat_native_bridge",
                                "bridge_url": fixture.bridge_url,
                                "enabled": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            discovered_urls = discover_wechat_native_bridge_urls(
                registry_paths=(registry_path,)
            )
            bridge_url = discovered_urls[0] if discovered_urls else ""
            request = build_wechat_native_bridge_request(
                bridge_url=bridge_url,
                target_name="File Transfer Assistant",
                message=message_text,
                background_screenshot_focus_stable=True,
                background_screenshot_count=1,
                background_screenshot_success_count=1,
                required_markers=required,
                forbidden_markers=forbidden,
            )
            send_report = WeChatNativeBridgeSenderAdapter(request_timeout=2.0).send(
                request
            ).to_dict()
            fixture_data = fixture.to_dict()
            registry_data = {
                "registered": registry_path.exists(),
                "registry_path": str(registry_path),
                "discovered_urls": list(discovered_urls),
            }
    return WeChatNativeBridgeFixtureSmokeReport(
        message=message_text,
        required_markers=required,
        forbidden_markers=forbidden,
        bridge_url=bridge_url,
        registry=registry_data,
        send_report=send_report,
        fixture=fixture_data,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an owned local fixture smoke for the WeChat native bridge contract."
    )
    parser.add_argument("--message", default="OPENWUKONG_WECHAT_FIXTURE: PASS")
    parser.add_argument(
        "--acceptance-marker",
        action="append",
        default=[],
        help="Required marker expected in readback. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--forbid-marker",
        action="append",
        default=[],
        help="Forbidden marker that fails readback if present.",
    )
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_wechat_native_bridge_fixture_smoke(
        message=args.message,
        required_markers=tuple(
            args.acceptance_marker or ("OPENWUKONG_WECHAT_FIXTURE: PASS",)
        ),
        forbidden_markers=tuple(args.forbid_marker or ()),
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "WeChat native bridge fixture smoke: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"requests={data['fixture']['request_count']}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


class _LocalWeChatNativeBridgeFixture:
    def __init__(self):
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._requests: list[dict] = []
        self.bridge_url = ""

    def __enter__(self) -> "_LocalWeChatNativeBridgeFixture":
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LocalWeChatNativeBridgeHandler,
        )
        server.fixture = self
        server.daemon_threads = True
        self._server = server
        self.bridge_url = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def capabilities(self, target_name: str) -> dict:
        del target_name
        return {
            "ok": True,
            "bridge": {"name": "OpenWukong Owned WeChat Fixture"},
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "capabilities": ["wechat.conversation.send_message"],
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "owned-fixture-filehelper",
                    "available": True,
                }
            ],
        }

    def send_result(self, payload: dict) -> dict:
        message = str(payload.get("message", "") or "")
        return {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "readbackText": f"File Transfer Assistant\n{message}",
        }

    def record_request(self, path: str, payload: dict) -> None:
        with self._lock:
            self._requests.append({"path": path, "payload": dict(payload)})

    def to_dict(self) -> dict:
        with self._lock:
            requests = [dict(item) for item in self._requests]
        capability_requests = [
            item for item in requests if item.get("path") == "/v1/wechat/capabilities"
        ]
        send_requests = [
            item.get("payload", {})
            for item in requests
            if item.get("path") == "/v1/wechat/send"
        ]
        return {
            "mode": "local-wechat-native-bridge-fixture",
            "bridge_url": self.bridge_url,
            "request_count": len(requests),
            "capability_request_count": len(capability_requests),
            "send_request_count": len(send_requests),
            "requests": requests,
            "send_requests": [dict(item) for item in send_requests],
        }


class _LocalWeChatNativeBridgeHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        fixture = getattr(self.server, "fixture", None)
        payload = self._read_json_body()
        if fixture is not None:
            fixture.record_request(self.path, payload)
        if fixture is None:
            self._send_json({"ok": False, "error": "fixture_missing"}, status=500)
            return
        if self.path == "/v1/wechat/capabilities":
            self._send_json(fixture.capabilities(str(payload.get("target_name", "") or "")))
            return
        if self.path == "/v1/wechat/send":
            self._send_json(fixture.send_result(payload))
            return
        self._send_json({"ok": False, "error": "not_found"}, status=404)

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = {}
        return dict(data) if isinstance(data, dict) else {}

    def _send_json(self, data: dict, *, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        del format, args


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


def _string_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    return tuple(str(item).strip() for item in items if str(item or "").strip())


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


if __name__ == "__main__":
    raise SystemExit(main())
