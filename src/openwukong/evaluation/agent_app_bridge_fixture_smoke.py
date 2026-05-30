# -*- coding: utf-8 -*-
"""Owned local DevTools fixture smoke for the app bridge sender."""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import http.server
import json
import socketserver
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from openwukong.control.agent_app_bridge import (
    AgentAppBridgeCdpAdapter,
    build_agent_app_bridge_request,
)


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeFixtureSmokeReport:
    message: str
    required_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...]
    bridge_send_report: dict
    fixture: dict
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-bridge-fixture-smoke"

    @property
    def safety_mode(self) -> str:
        return "local_owned_devtools_fixture"

    @property
    def desktop_control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        composer_probe = self.bridge_send_report.get("composer_probe_report") or {}
        return bool(
            self.bridge_send_report.get("ok", False)
            and int(self.fixture.get("cdp_request_count", 0) or 0) >= 2
            and int(self.bridge_send_report.get("native_probe_attempts", 0) or 0) >= 1
            and composer_probe.get("decision") == "app_bridge_composer_ready"
            and int(self.bridge_send_report.get("window_input_attempts", 0) or 0) == 0
        )

    @property
    def decision(self) -> str:
        return "agent_app_bridge_fixture_smoke_verified" if self.ok else "agent_app_bridge_fixture_smoke_failed"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "message": self.message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "desktop_control_attempts": self.desktop_control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_report": dict(self.bridge_send_report),
            "fixture": dict(self.fixture),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_app_bridge_fixture_smoke(
    *,
    message: str = "OpenWukong app bridge fixture probe.",
    required_markers: tuple[str, ...] = ("OPENWUKONG_ACCEPTANCE: PASS",),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentAppBridgeFixtureSmokeReport:
    started = time.perf_counter()
    message_text = str(message or "").strip()
    required = _string_tuple(required_markers)
    forbidden = _string_tuple(forbidden_markers)
    with _LocalAppBridgeDevToolsFixture(
        expected_message=message_text,
        required_markers=required,
    ) as fixture:
        request = build_agent_app_bridge_request(
            agent="local app bridge fixture",
            agent_id="local-fixture",
            project_name="openwukong",
            task_name="agent-app-bridge-fixture-smoke",
            message=message_text,
            composed_message=message_text,
            selected_transport={
                "transport_id": "local-owned-devtools-fixture",
                "route_id": "agent-app-bridge-cdp",
                "transport": "local-owned-devtools-fixture",
                "background_capable": True,
                "ready": True,
            },
            app_surface_probe=_ready_probe(fixture),
            required_markers=required,
            forbidden_markers=forbidden,
        )
        bridge_report = AgentAppBridgeCdpAdapter().send(request).to_dict()
        fixture_data = fixture.to_dict()
    return AgentAppBridgeFixtureSmokeReport(
        message=message_text,
        required_markers=required,
        forbidden_markers=forbidden,
        bridge_send_report=bridge_report,
        fixture=fixture_data,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an owned local DevTools fixture smoke for the app bridge sender."
    )
    parser.add_argument("--message", default="OpenWukong app bridge fixture probe.")
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

    report = run_agent_app_bridge_fixture_smoke(
        message=args.message,
        required_markers=tuple(args.acceptance_marker or ("OPENWUKONG_ACCEPTANCE: PASS",)),
        forbidden_markers=tuple(args.forbid_marker or ()),
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Agent app bridge fixture smoke: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"cdp_requests={data['fixture']['cdp_request_count']}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


class _LocalAppBridgeDevToolsFixture:
    def __init__(
        self,
        *,
        expected_message: str,
        required_markers: tuple[str, ...],
    ):
        self.expected_message = expected_message
        self.required_markers = required_markers
        self._http_server: http.server.ThreadingHTTPServer | None = None
        self._ws_server: socketserver.ThreadingTCPServer | None = None
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._http_requests: list[dict] = []
        self._cdp_requests: list[dict] = []
        self.debugger_url = ""
        self.websocket_url = ""
        self.target_url = "app://openwukong/local-app-bridge-fixture"
        self.target_title = "OpenWukong Local App Bridge Fixture"

    def __enter__(self) -> "_LocalAppBridgeDevToolsFixture":
        ws_server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0),
            _LocalAppBridgeDevToolsWebSocketHandler,
        )
        ws_server.fixture = self
        ws_server.daemon_threads = True
        self._ws_server = ws_server
        self.websocket_url = f"ws://127.0.0.1:{ws_server.server_address[1]}/devtools/page/page-1"

        http_server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LocalAppBridgeDevToolsHTTPHandler,
        )
        http_server.fixture = self
        http_server.daemon_threads = True
        self._http_server = http_server
        self.debugger_url = f"http://127.0.0.1:{http_server.server_address[1]}"

        self._start_server(ws_server)
        self._start_server(http_server)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        for server in (self._http_server, self._ws_server):
            if server is not None:
                server.shutdown()
                server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)

    def _start_server(self, server) -> None:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._threads.append(thread)

    def target_payload(self) -> dict:
        return {
            "id": "page-1",
            "target_id": "page-1",
            "type": "page",
            "title": self.target_title,
            "url": self.target_url,
            "webSocketDebuggerUrl": self.websocket_url,
            "ready": True,
        }

    def version_payload(self) -> dict:
        return {
            "Browser": "OpenWukongLocalFixture/1.0",
            "Protocol-Version": "1.3",
            "webSocketDebuggerUrl": self.websocket_url,
        }

    def record_http(self, path: str) -> None:
        with self._lock:
            self._http_requests.append({"path": path})

    def record_cdp(self, message: dict) -> None:
        with self._lock:
            self._cdp_requests.append(dict(message))

    def evaluate_remote_object(self, expression: str) -> dict:
        text = str(expression or "")
        message_set = self.expected_message in text
        readback = "\n".join(
            item
            for item in (
                self.expected_message if message_set else "",
                *self.required_markers,
            )
            if item
        )
        value = {
            "composerFound": True,
            "safeComposerFound": True,
            "composerCandidateCount": 1,
            "safeComposerCandidateCount": 1,
            "selectedComposer": {
                "tag": "TEXTAREA",
                "placeholder": "Agent chat message",
                "safeChatHint": True,
            },
            "messageSet": message_set,
            "submitAttempted": message_set,
            "submitVerified": message_set,
            "sendButtonLabel": "send",
            "readbackText": readback,
        }
        return {"type": "object", "value": value}

    def to_dict(self) -> dict:
        with self._lock:
            http_requests = [dict(item) for item in self._http_requests]
            cdp_requests = [dict(item) for item in self._cdp_requests]
        return {
            "mode": "local-app-bridge-devtools-fixture",
            "debugger_url": self.debugger_url,
            "websocket_url": self.websocket_url,
            "target": self.target_payload(),
            "http_request_count": len(http_requests),
            "cdp_request_count": len(cdp_requests),
            "http_requests": http_requests,
            "cdp_requests": cdp_requests,
        }


class _LocalAppBridgeDevToolsHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        fixture = getattr(self.server, "fixture", None)
        if fixture is not None:
            fixture.record_http(self.path)
        if fixture is None:
            self._send_json({}, status=500)
            return
        if self.path == "/json/version":
            self._send_json(fixture.version_payload())
            return
        if self.path in {"/json/list", "/json"}:
            self._send_json([fixture.target_payload()])
            return
        self._send_json({"error": "not_found"}, status=404)

    def _send_json(self, data, *, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        del format, args


class _LocalAppBridgeDevToolsWebSocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        key = ""
        while True:
            line = self.rfile.readline().decode("ascii", errors="replace").strip()
            if not line:
                break
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.wfile.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        message = self._read_client_json()
        fixture = getattr(self.server, "fixture", None)
        if fixture is not None:
            fixture.record_cdp(message)
        expression = str(message.get("params", {}).get("expression", "") or "")
        remote_object = (
            fixture.evaluate_remote_object(expression)
            if fixture is not None
            else {"type": "undefined"}
        )
        self._send_server_json(
            {
                "id": int(message.get("id", 1) or 1),
                "result": {"result": remote_object},
            }
        )

    def _read_client_json(self) -> dict:
        header = self.rfile.read(2)
        if len(header) < 2:
            return {}
        _, second = header
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.rfile.read(8))[0]
        mask = self.rfile.read(4)
        payload = self.rfile.read(length) if length else b""
        if second & 0x80:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = {}
        return message if isinstance(message, dict) else {}

    def _send_server_json(self, message: dict) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))
        self.wfile.write(bytes(header) + payload)


def _ready_probe(fixture: _LocalAppBridgeDevToolsFixture) -> dict:
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_ready",
        "control_allowed": False,
        "control_attempts": 0,
        "endpoint_count": 1,
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "debugger_url": fixture.debugger_url,
                "ready": True,
                "target_count": 1,
                "targets": [fixture.target_payload()],
            }
        ],
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "composer_candidate_count": 1,
            "semantic_composer_count": 1,
            "background_screenshot_count": 0,
            "background_screenshot_success_count": 0,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "openwukong-local-fixture.exe",
                    "pid": 0,
                    "window_title": fixture.target_title,
                    "hwnd": 0,
                }
            ],
        },
    }


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
