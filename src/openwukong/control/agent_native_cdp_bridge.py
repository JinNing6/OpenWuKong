# -*- coding: utf-8 -*-
"""CDP-backed implementation of the agent native bridge contract."""

from __future__ import annotations

import argparse
import dataclasses
import http.server
import json
import socketserver
import sys
from pathlib import Path

from openwukong.connectors.browser import BrowserDevToolsClient, BrowserDevToolsTarget
from openwukong.control.agent_app_bridge import _bridge_send_expression, _remote_object_value
from openwukong.control.agent_native_bridge import SEND_ACTION
from openwukong.control.native_bridge_registry import AGENT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class AgentNativeCdpBridgeConfig:
    agent: str
    agent_id: str
    debugger_url: str
    process_name: str
    pid: int = 0
    hwnd: int = 0
    window_title: str = ""
    projects: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ()
    target_title: str = ""
    target_url: str = ""
    request_timeout: float = 5.0


class AgentNativeCdpBridgeService:
    def __init__(
        self,
        config: AgentNativeCdpBridgeConfig,
        *,
        devtools_client: BrowserDevToolsClient | None = None,
    ):
        self.config = config
        self._devtools_client = devtools_client or BrowserDevToolsClient(
            request_timeout=config.request_timeout
        )

    def capabilities(self) -> dict:
        selected_target = None
        target_count = 0
        error = ""
        try:
            targets = self._devtools_client.list_targets(self.config.debugger_url)
            target_count = len(targets)
            selected_target = _select_target(targets, self.config)
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
        ok = bool(self.config.debugger_url and selected_target is not None and not error)
        return {
            "ok": ok,
            "bridge": {
                "name": "OpenWukong Agent Native CDP Bridge",
                "transport": "chrome-devtools-protocol",
            },
            "background_safe": True,
            "native_background_safe": True,
            "surface_kind": "desktop_app",
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "capabilities": [SEND_ACTION],
            "agents": [{"agent_id": self.config.agent_id, "available": True}],
            "projects": [
                {"name": project, "available": True}
                for project in self.config.projects
                if project
            ],
            "tasks": [
                {"name": task, "available": True}
                for task in self.config.tasks
                if task
            ],
            "app_binding": self._app_binding(),
            "devtools": {
                "debugger_url": self.config.debugger_url,
                "target_count": target_count,
                "selected_target": _target_to_dict(selected_target),
                "error": error,
            },
            "error": error,
        }

    def send(self, payload: dict) -> dict:
        try:
            target = self._ready_target()
            message = str(
                payload.get("composed_message", "")
                or payload.get("message", "")
                or ""
            )
            result = self._devtools_client.evaluate(
                self.config.debugger_url,
                target,
                _bridge_send_expression(message),
            )
            action = _remote_object_value(result)
        except Exception as exc:
            return {
                "ok": False,
                "sent": False,
                "error": str(exc) or exc.__class__.__name__,
                "foreground_focus_stable": True,
                "window_input_attempts": 0,
                "keyboard_input_attempts": 0,
                "clipboard_write_attempts": 0,
            }
        bridge_ok = bool(
            action.get("composerFound", False)
            and action.get("messageSet", False)
            and action.get("submitAttempted", False)
            and action.get("submitVerified", True) is not False
        )
        data = {
            "ok": bridge_ok,
            "sent": bridge_ok,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "target": _target_to_dict(target),
        }
        data.update(action)
        return data

    def _ready_target(self) -> BrowserDevToolsTarget:
        targets = self._devtools_client.list_targets(self.config.debugger_url)
        target = _select_target(targets, self.config)
        if target is None:
            raise RuntimeError("agent_native_cdp_bridge_target_not_ready")
        return target

    def _app_binding(self) -> dict:
        return {
            "process_name": self.config.process_name,
            "pid": int(self.config.pid or 0),
            "hwnd": int(self.config.hwnd or 0),
            "window_title": self.config.window_title,
        }


def make_agent_native_cdp_bridge_handler(service: AgentNativeCdpBridgeService):
    class AgentNativeCdpBridgeHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("payload_not_object")
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if self.path == "/v1/agent/capabilities":
                self._send_json(service.capabilities())
                return
            if self.path == "/v1/agent/chat":
                self._send_json(service.send(payload))
                return
            self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=404)

        def _send_json(self, data: dict, status: int = 200):
            body = json.dumps(data, ensure_ascii=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return AgentNativeCdpBridgeHandler


def write_agent_native_cdp_bridge_registry(
    registry_path: str | Path,
    *,
    bridge_url: str,
    config: AgentNativeCdpBridgeConfig,
) -> None:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = str(bridge_url or "").strip().rstrip("/")
    entry = {
        "url": url,
        "type": "agent_native_bridge",
        "agent_id": config.agent_id,
        "agent": config.agent,
        "surface_kind": "desktop_app",
        "enabled": True,
        "app_binding": {
            "process_name": config.process_name,
            "pid": int(config.pid or 0),
            "hwnd": int(config.hwnd or 0),
            "window_title": config.window_title,
        },
        "debugger_url": config.debugger_url,
    }
    entries = _merged_registry_entries(path, entry)
    data = {
        "schema_version": AGENT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION,
        "agent_native_bridges": entries,
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _merged_registry_entries(path: Path, new_entry: dict) -> list[dict]:
    existing_entries: list[dict] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw_entries = data.get("agent_native_bridges", [])
            if isinstance(raw_entries, list):
                existing_entries = [
                    dict(entry) for entry in raw_entries if isinstance(entry, dict)
                ]
        except Exception:
            existing_entries = []

    new_url = str(new_entry.get("url", "") or "").strip().rstrip("/")
    new_agent_id = str(new_entry.get("agent_id", "") or "").strip().casefold()
    new_process_name = str(
        (new_entry.get("app_binding") or {}).get("process_name", "") or ""
    ).strip().casefold()
    merged: list[dict] = []
    for entry in existing_entries:
        existing_url = str(entry.get("url", "") or "").strip().rstrip("/")
        existing_agent_id = str(entry.get("agent_id", "") or "").strip().casefold()
        existing_process_name = str(
            (entry.get("app_binding") or {}).get("process_name", "") or ""
        ).strip().casefold()
        same_url = bool(new_url and existing_url == new_url)
        same_agent_process = bool(
            new_agent_id
            and existing_agent_id == new_agent_id
            and new_process_name
            and existing_process_name == new_process_name
        )
        if same_url or same_agent_process:
            continue
        merged.append(entry)
    merged.append(dict(new_entry))
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a local CDP-backed agent native bridge."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--agent", default="agent app")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--debugger-url", required=True)
    parser.add_argument("--process-name", required=True)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--hwnd", type=int, default=0)
    parser.add_argument("--window-title", default="")
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--target-title", default="")
    parser.add_argument("--target-url", default="")
    parser.add_argument("--registry-path", default="")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    service = AgentNativeCdpBridgeService(
        AgentNativeCdpBridgeConfig(
            agent=args.agent,
            agent_id=args.agent_id,
            debugger_url=args.debugger_url,
            process_name=args.process_name,
            pid=args.pid,
            hwnd=args.hwnd,
            window_title=args.window_title,
            projects=tuple(args.project or ()),
            tasks=tuple(args.task or ()),
            target_title=args.target_title,
            target_url=args.target_url,
            request_timeout=args.request_timeout,
        )
    )
    handler = make_agent_native_cdp_bridge_handler(service)
    with socketserver.TCPServer((args.host, int(args.port or 0)), handler) as server:
        host, port = server.server_address
        bridge_url = f"http://{host}:{port}"
        if args.registry_path:
            write_agent_native_cdp_bridge_registry(
                args.registry_path,
                bridge_url=bridge_url,
                config=service.config,
            )
        sys.stdout.write(f"agent_native_cdp_bridge_url={bridge_url}\n")
        sys.stdout.flush()
        server.serve_forever()
    return 0


def _select_target(
    targets: tuple[BrowserDevToolsTarget, ...],
    config: AgentNativeCdpBridgeConfig,
) -> BrowserDevToolsTarget | None:
    candidates = tuple(
        target for target in targets if target.web_socket_debugger_url
    )
    if not candidates:
        return None
    target_url = str(config.target_url or "").strip().casefold()
    if target_url:
        for target in candidates:
            if target_url in str(target.url or "").casefold():
                return target
    target_title = str(config.target_title or config.window_title or "").strip().casefold()
    if target_title:
        for target in candidates:
            if target_title in str(target.title or "").casefold():
                return target
    for target in candidates:
        if str(target.type or "").strip().casefold() in {"page", "webview"}:
            return target
    return candidates[0]


def _target_to_dict(target: BrowserDevToolsTarget | None) -> dict:
    if target is None:
        return {}
    return {
        "target_id": target.target_id,
        "type": target.type,
        "title": target.title,
        "url": target.url,
        "webSocketDebuggerUrl": target.web_socket_debugger_url,
    }


__all__ = [
    "AgentNativeCdpBridgeConfig",
    "AgentNativeCdpBridgeService",
    "make_agent_native_cdp_bridge_handler",
    "write_agent_native_cdp_bridge_registry",
]


if __name__ == "__main__":
    raise SystemExit(main())
