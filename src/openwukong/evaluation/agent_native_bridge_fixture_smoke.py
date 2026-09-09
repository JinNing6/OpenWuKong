# -*- coding: utf-8 -*-
"""Owned local HTTP fixture smoke for the generic agent native bridge."""

from __future__ import annotations

import argparse
import dataclasses
import http.server
import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from openwukong.control.agent_native_bridge import (
    SEND_ACTION,
    AgentNativeBridgeSenderAdapter,
    build_agent_native_bridge_request,
)


@dataclasses.dataclass(frozen=True)
class AgentNativeBridgeFixtureSmokeReport:
    message: str
    required_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...]
    advertise_readback: bool
    send_report: dict
    fixture: dict
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-native-bridge-fixture-smoke"

    @property
    def safety_mode(self) -> str:
        return "local_owned_http_fixture"

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def native_call_attempts(self) -> int:
        return int(self.send_report.get("native_call_attempts", 0) or 0)

    @property
    def ok(self) -> bool:
        dry_run = self.send_report.get("dry_run_report")
        if not isinstance(dry_run, dict):
            dry_run = {}
        return bool(
            self.send_report.get("ok", False)
            and self.send_report.get("decision") == "agent_native_bridge_send_accepted"
            and dry_run.get("decision") == "agent_native_bridge_dry_run_ready"
            and bool(dry_run.get("readback_action_ready", False))
            and self.native_call_attempts == 1
            and int(self.send_report.get("window_input_attempts", 0) or 0) == 0
            and int(self.fixture.get("capability_request_count", 0) or 0) == 1
            and int(self.fixture.get("chat_request_count", 0) or 0) == 1
        )

    @property
    def decision(self) -> str:
        if self.ok:
            return "agent_native_bridge_fixture_smoke_verified"
        return "agent_native_bridge_fixture_smoke_failed"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "message": self.message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "advertise_readback": self.advertise_readback,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "native_call_attempts": self.native_call_attempts,
            "send_report": dict(self.send_report),
            "fixture": dict(self.fixture),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_native_bridge_fixture_smoke(
    *,
    message: str = "OpenWukong agent native bridge fixture probe.",
    required_markers: tuple[str, ...] = ("OPENWUKONG_ACCEPTANCE: PASS",),
    forbidden_markers: tuple[str, ...] = (),
    advertise_readback: bool = True,
) -> AgentNativeBridgeFixtureSmokeReport:
    started = time.perf_counter()
    message_text = str(message or "").strip()
    required = _string_tuple(required_markers)
    forbidden = _string_tuple(forbidden_markers)
    with _LocalAgentNativeBridgeFixture(
        required_markers=required,
        advertise_readback=bool(advertise_readback),
    ) as fixture:
        request = build_agent_native_bridge_request(
            bridge_url=fixture.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="agent-native-bridge-fixture-smoke",
            message=message_text,
            composed_message=(
                "Project: openwukong\n"
                "Task: agent-native-bridge-fixture-smoke\n\n"
                f"Message:\n{message_text}"
            ),
            required_markers=required,
            forbidden_markers=forbidden,
        )
        send_report = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(
            request
        ).to_dict()
        fixture_data = fixture.to_dict()
    return AgentNativeBridgeFixtureSmokeReport(
        message=message_text,
        required_markers=required,
        forbidden_markers=forbidden,
        advertise_readback=bool(advertise_readback),
        send_report=send_report,
        fixture=fixture_data,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an owned local HTTP fixture smoke for the agent native bridge."
    )
    parser.add_argument("--message", default="OpenWukong agent native bridge fixture probe.")
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
    parser.add_argument(
        "--no-readback-capability",
        action="store_true",
        help="Run a negative fixture that does not advertise transcript readback.",
    )
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_agent_native_bridge_fixture_smoke(
        message=args.message,
        required_markers=tuple(args.acceptance_marker or ("OPENWUKONG_ACCEPTANCE: PASS",)),
        forbidden_markers=tuple(args.forbid_marker or ()),
        advertise_readback=not bool(args.no_readback_capability),
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
            "Agent native bridge fixture smoke: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"requests={data['fixture']['request_count']}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


class _LocalAgentNativeBridgeFixture:
    def __init__(
        self,
        *,
        required_markers: tuple[str, ...],
        advertise_readback: bool,
    ):
        self.required_markers = required_markers
        self.advertise_readback = advertise_readback
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._requests: list[dict] = []
        self.bridge_url = ""

    def __enter__(self) -> "_LocalAgentNativeBridgeFixture":
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LocalAgentNativeBridgeHTTPHandler,
        )
        server.fixture = self
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

    def record(self, path: str, payload: dict) -> None:
        with self._lock:
            self._requests.append({"path": path, "payload": dict(payload)})

    def capabilities_payload(self) -> dict:
        capabilities = [SEND_ACTION]
        if self.advertise_readback:
            capabilities.append("agent_app_conversation.read_transcript")
        return {
            "ok": True,
            "bridge": {"name": "OpenWukong Agent Native Bridge Fixture"},
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "executable_path": "C:/Program Files/OpenAI/Codex/app/Codex.exe",
                "pid": 32000,
                "hwnd": 2491830,
                "window_title": "Codex Fixture",
            },
            "requires_foreground": False,
            "window_input_required": False,
            "capabilities": capabilities,
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [
                {
                    "name": "agent-native-bridge-fixture-smoke",
                    "available": True,
                }
            ],
        }

    def chat_response(self, payload: dict) -> dict:
        message = str(payload.get("message", "") or "")
        readback = "\n".join(
            item
            for item in (
                message,
                *self.required_markers,
            )
            if item
        )
        return {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "readbackText": readback,
        }

    def to_dict(self) -> dict:
        with self._lock:
            requests = [dict(item) for item in self._requests]
        capability_payloads = [
            dict(item["payload"])
            for item in requests
            if item.get("path") == "/v1/agent/capabilities"
        ]
        chat_payloads = [
            dict(item["payload"])
            for item in requests
            if item.get("path") == "/v1/agent/chat"
        ]
        return {
            "mode": "local-agent-native-bridge-fixture",
            "bridge_url": self.bridge_url,
            "advertise_readback": self.advertise_readback,
            "request_count": len(requests),
            "capability_request_count": len(capability_payloads),
            "chat_request_count": len(chat_payloads),
            "request_paths": [str(item.get("path", "") or "") for item in requests],
            "capability_payloads": capability_payloads,
            "chat_payloads": chat_payloads,
        }


class _LocalAgentNativeBridgeHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        fixture = getattr(self.server, "fixture", None)
        payload = self._read_json()
        if fixture is not None:
            fixture.record(self.path, payload)
        if fixture is None:
            self._send_json({"ok": False, "error": "fixture_missing"}, status=500)
            return
        if self.path == "/v1/agent/capabilities":
            self._send_json(fixture.capabilities_payload())
            return
        if self.path == "/v1/agent/chat":
            self._send_json(fixture.chat_response(payload))
            return
        self._send_json({"ok": False, "error": "not_found"}, status=404)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(max(0, length))
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8-sig"))
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
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
