# -*- coding: utf-8 -*-
"""Deterministic IDE connector backed by an extension bridge.

The bridge is implemented by an IDE extension or native host. This Python side
does not locate controls visually and does not use UIA; it only speaks the
explicit local JSON contract exposed by that bridge.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time

import requests

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)


@dataclasses.dataclass
class _IDEExtensionSession:
    session_key: str
    bridge_url: str
    transcript: list[str] = dataclasses.field(default_factory=list)
    command_count: int = 0
    last_command_at: float = 0.0


class IDEExtensionBridgeClient:
    """HTTP JSON client for the local IDE extension/native-host bridge."""

    transport = "vscode-extension-bridge"

    def __init__(self, *, request_timeout: float = 10.0):
        self.request_timeout = max(0.1, float(request_timeout))

    def read_conversation(self, bridge_url: str, target: ConnectorTarget) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/read",
            {
                "action": "read_conversation",
                "target": _target_payload(target),
            },
        )

    def read_state(self, bridge_url: str, target: ConnectorTarget) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/state",
            {
                "action": "read_state",
                "target": _target_payload(target),
            },
        )

    def read_capabilities(self, bridge_url: str, target: ConnectorTarget) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/capabilities",
            {
                "action": "read_capabilities",
                "target": _target_payload(target),
            },
        )

    def send_message(
        self,
        bridge_url: str,
        target: ConnectorTarget,
        message: str,
    ) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/send",
            {
                "action": "send_message",
                "command_id": "openwukong.sendMessage",
                "target": _target_payload(target),
                "message": message,
            },
        )

    def execute_command(
        self,
        bridge_url: str,
        target: ConnectorTarget,
        command_id: str,
        arguments: list,
    ) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/command",
            {
                "action": "execute_command",
                "command_id": command_id,
                "arguments": arguments,
                "target": _target_payload(target),
            },
        )

    def send_chat(
        self,
        bridge_url: str,
        target: ConnectorTarget,
        adapter_id: str,
        message: str,
    ) -> dict:
        return self._post_json(
            bridge_url,
            "/v1/ide/chat",
            {
                "action": "chat_send",
                "adapter_id": adapter_id,
                "target": _target_payload(target),
                "message": message,
            },
        )

    def _post_json(self, bridge_url: str, path: str, payload: dict) -> dict:
        endpoint = f"{_normalize_bridge_url(bridge_url)}{path}"
        response = requests.post(
            endpoint,
            json=payload,
            timeout=self.request_timeout,
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise
        if not isinstance(data, dict):
            raise ValueError("ide_bridge_response_not_object")
        if response.status_code >= 400 and "ok" not in data:
            response.raise_for_status()
        return data


class IDEExtensionConnector(SessionConnector):
    """Connector for VS Code/Cursor-compatible extension bridge sessions."""

    connector_id = "ide-extension"
    display_name = "IDE Extension Bridge"
    route_id = "ide-extension-connector"
    transport = IDEExtensionBridgeClient.transport

    def __init__(self, *, bridge_client: IDEExtensionBridgeClient | None = None):
        self._bridge_client = bridge_client or IDEExtensionBridgeClient()
        self._sessions: dict[str, _IDEExtensionSession] = {}
        self._lock = threading.Lock()

    def supports_target(self, target: ConnectorTarget) -> bool:
        return bool((target.ide_bridge_url or "").strip())

    def match_score(self, target: ConnectorTarget) -> int:
        if not self.supports_target(target):
            return -1
        return 340

    def read_conversation(self, target: ConnectorTarget) -> str:
        session = self._ensure_session(target)
        bridge_url = (target.ide_bridge_url or "").strip()
        if not bridge_url:
            session.transcript.append("[bridge_error] missing_ide_bridge_url")
            return "\n".join(session.transcript[-40:]).strip()

        try:
            data = self._bridge_client.read_conversation(bridge_url, target)
        except Exception as exc:
            session.transcript.append(f"[bridge_error] {exc}")
            return "\n".join(session.transcript[-40:]).strip()

        conversation = str(data.get("conversation", "") or "")
        if conversation:
            session.transcript.append(conversation)
        session.transcript = session.transcript[-200:]
        return "\n".join(session.transcript[-40:]).strip()

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        session = self._ensure_session(target)
        session.last_command_at = time.time()
        session.command_count += 1
        action_key = f"{session.session_key}:{session.command_count}"

        bridge_url = (target.ide_bridge_url or "").strip()
        command = (message or "").strip()
        if not bridge_url:
            return self._error_result(
                session,
                action_key,
                "missing_ide_bridge_url",
                command,
            )
        if not command:
            return self._error_result(session, action_key, "empty_ide_message", command)

        semantic = self._parse_semantic_command(command)
        if semantic["error"]:
            return self._error_result(
                session,
                action_key,
                semantic["error"],
                command,
                action=str(semantic["action"] or "send_message"),
                bridge_action=str(semantic["bridge_action"] or "send_message"),
            )
        if semantic["action"] == "read_state":
            return self._send_read_state(target, session, action_key, bridge_url, command)
        if semantic["action"] == "read_capabilities":
            return self._send_read_capabilities(target, session, action_key, bridge_url, command)
        if semantic["action"] == "execute_command":
            return self._send_execute_command(
                target,
                session,
                action_key,
                bridge_url,
                command,
                str(semantic["command_id"]),
                list(semantic["arguments"]),
            )
        if semantic["action"] == "chat_send":
            return self._send_chat(
                target,
                session,
                action_key,
                bridge_url,
                command,
                str(semantic["adapter_id"]),
                str(semantic["message"]),
            )

        try:
            data = self._bridge_client.send_message(bridge_url, target, command)
        except Exception as exc:
            return self._error_result(session, action_key, str(exc), command)

        ok = bool(data.get("ok", False))
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        returned_action_key = str(data.get("action_key", "") or action_key)
        conversation = str(data.get("conversation", "") or "")
        session.transcript.append(f"$ IDE bridge send {command}")
        if conversation:
            session.transcript.append(conversation)
        if not ok:
            session.transcript.append(f"[bridge_error] {data.get('error', 'bridge_send_failed')}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="send_message",
            action_key=returned_action_key if ok else "",
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": bridge_url,
                "bridge_action": "send_message",
                "command_id": str(metadata.get("command_id", "openwukong.sendMessage") or ""),
                "session_key": session.session_key,
                "command_index": session.command_count,
                "ide_name": str(metadata.get("ide_name", "") or ""),
                "workspace_path": target.workspace_path,
                "project_name": target.project_name,
                "response": data,
            },
            error="" if ok else str(data.get("error", "bridge_send_failed") or "bridge_send_failed"),
        )

    def _send_read_state(
        self,
        target: ConnectorTarget,
        session: _IDEExtensionSession,
        action_key: str,
        bridge_url: str,
        command: str,
    ) -> ConnectorActionResult:
        try:
            data = self._bridge_client.read_state(bridge_url, target)
        except Exception as exc:
            return self._error_result(
                session,
                action_key,
                str(exc),
                command,
                action="read_state",
                bridge_action="read_state",
            )

        ok = bool(data.get("ok", False))
        metadata = data.get("metadata", {})
        diagnostics = data.get("diagnostics", [])
        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(diagnostics, list):
            diagnostics = []
        session.transcript.append("$ IDE bridge state")
        session.transcript.append(
            f"[state] ide={metadata.get('ide_name', '')} diagnostics={len(diagnostics)}"
        )
        if not ok:
            session.transcript.append(f"[bridge_error] {data.get('error', 'bridge_state_failed')}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="read_state",
            action_key=action_key,
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": bridge_url,
                "bridge_action": "read_state",
                "session_key": session.session_key,
                "command_index": session.command_count,
                "metadata": metadata,
                "diagnostics": diagnostics,
                "response": data,
            },
            error="" if ok else str(data.get("error", "bridge_state_failed") or "bridge_state_failed"),
        )

    def _send_read_capabilities(
        self,
        target: ConnectorTarget,
        session: _IDEExtensionSession,
        action_key: str,
        bridge_url: str,
        command: str,
    ) -> ConnectorActionResult:
        try:
            data = self._bridge_client.read_capabilities(bridge_url, target)
        except Exception as exc:
            return self._error_result(
                session,
                action_key,
                str(exc),
                command,
                action="read_capabilities",
                bridge_action="read_capabilities",
            )

        ok = bool(data.get("ok", False))
        metadata = data.get("metadata", {})
        commands = data.get("commands", [])
        chat_adapters = data.get("chat_adapters", [])
        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(commands, list):
            commands = []
        if not isinstance(chat_adapters, list):
            chat_adapters = []
        session.transcript.append("$ IDE bridge capabilities")
        session.transcript.append(
            f"[capabilities] ide={metadata.get('ide_name', '')} commands={len(commands)} chat_adapters={len(chat_adapters)}"
        )
        if not ok:
            session.transcript.append(f"[bridge_error] {data.get('error', 'bridge_capabilities_failed')}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="read_capabilities",
            action_key=action_key if ok else "",
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": bridge_url,
                "bridge_action": "read_capabilities",
                "session_key": session.session_key,
                "command_index": session.command_count,
                "metadata": metadata,
                "commands": commands,
                "chat_adapters": chat_adapters,
                "response": data,
            },
            error="" if ok else str(data.get("error", "bridge_capabilities_failed") or "bridge_capabilities_failed"),
        )

    def _send_execute_command(
        self,
        target: ConnectorTarget,
        session: _IDEExtensionSession,
        action_key: str,
        bridge_url: str,
        command: str,
        command_id: str,
        arguments: list,
    ) -> ConnectorActionResult:
        try:
            data = self._bridge_client.execute_command(
                bridge_url,
                target,
                command_id,
                arguments,
            )
        except Exception as exc:
            return self._error_result(
                session,
                action_key,
                str(exc),
                command,
                action="execute_command",
                bridge_action="execute_command",
                command_id=command_id,
            )

        ok = bool(data.get("ok", False))
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        returned_action_key = str(data.get("action_key", "") or action_key)
        session.transcript.append(f"$ IDE bridge command {command_id}")
        if not ok:
            session.transcript.append(f"[bridge_error] {data.get('error', 'bridge_command_failed')}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="execute_command",
            action_key=returned_action_key if ok else "",
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": bridge_url,
                "bridge_action": "execute_command",
                "command_id": str(metadata.get("command_id", command_id) or command_id),
                "arguments": arguments,
                "session_key": session.session_key,
                "command_index": session.command_count,
                "ide_name": str(metadata.get("ide_name", "") or ""),
                "result": data.get("result"),
                "response": data,
            },
            error="" if ok else str(data.get("error", "bridge_command_failed") or "bridge_command_failed"),
        )

    def _send_chat(
        self,
        target: ConnectorTarget,
        session: _IDEExtensionSession,
        action_key: str,
        bridge_url: str,
        command: str,
        adapter_id: str,
        message: str,
    ) -> ConnectorActionResult:
        try:
            data = self._bridge_client.send_chat(bridge_url, target, adapter_id, message)
        except Exception as exc:
            return self._error_result(
                session,
                action_key,
                str(exc),
                command,
                action="chat_send",
                bridge_action="chat_send",
                command_id="",
                adapter_id=adapter_id,
            )

        ok = bool(data.get("ok", False))
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        returned_action_key = str(data.get("action_key", "") or action_key)
        conversation = str(data.get("conversation", "") or "")
        command_id = str(metadata.get("command_id", "") or "")
        returned_adapter_id = str(metadata.get("adapter_id", adapter_id) or adapter_id)
        session.transcript.append(f"$ IDE bridge chat {adapter_id}")
        if conversation:
            session.transcript.append(conversation)
        if not ok:
            session.transcript.append(f"[bridge_error] {data.get('error', 'bridge_chat_failed')}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="chat_send",
            action_key=returned_action_key if ok else "",
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": bridge_url,
                "bridge_action": "chat_send",
                "adapter_id": returned_adapter_id,
                "command_id": command_id,
                "session_key": session.session_key,
                "command_index": session.command_count,
                "ide_name": str(metadata.get("ide_name", "") or ""),
                "conversation": conversation,
                "response": data,
            },
            error="" if ok else str(data.get("error", "bridge_chat_failed") or "bridge_chat_failed"),
        )

    def _error_result(
        self,
        session: _IDEExtensionSession,
        action_key: str,
        error: str,
        command: str,
        *,
        action: str = "send_message",
        bridge_action: str = "send_message",
        command_id: str = "",
        adapter_id: str = "",
    ) -> ConnectorActionResult:
        session.transcript.append(f"$ IDE bridge send {command}")
        session.transcript.append(f"[bridge_error] {error}")
        session.transcript = session.transcript[-200:]
        return ConnectorActionResult(
            success=False,
            connector_id=self.connector_id,
            action=action,
            action_key=action_key,
            payload={
                "route_id": self.route_id,
                "transport": self.transport,
                "bridge_url": session.bridge_url,
                "bridge_action": bridge_action,
                "command_id": command_id,
                "adapter_id": adapter_id,
                "session_key": session.session_key,
                "command_index": session.command_count,
            },
            error=error,
        )

    def _ensure_session(self, target: ConnectorTarget) -> _IDEExtensionSession:
        session_key = self._session_key(target)
        with self._lock:
            session = self._sessions.get(session_key)
            if session is not None:
                return session
            session = _IDEExtensionSession(
                session_key=session_key,
                bridge_url=(target.ide_bridge_url or "").strip(),
            )
            self._sessions[session_key] = session
            return session

    @staticmethod
    def _session_key(target: ConnectorTarget) -> str:
        parts = [
            target.ide_bridge_url.strip().lower(),
            target.workspace_path.strip().lower(),
            target.workspace_hint.strip().lower(),
            target.project_name.strip().lower(),
            target.window_title.strip().lower(),
        ]
        key = "|".join(part for part in parts if part)
        return key or "ide-extension:default"

    @staticmethod
    def _parse_semantic_command(command: str) -> dict:
        stripped = (command or "").strip()
        upper = stripped.upper()
        if upper in {"IDE STATE", "STATE"}:
            return {
                "action": "read_state",
                "bridge_action": "read_state",
                "command_id": "",
                "arguments": [],
                "adapter_id": "",
                "message": "",
                "error": "",
            }

        if upper in {"IDE CAPABILITIES", "CAPABILITIES"}:
            return {
                "action": "read_capabilities",
                "bridge_action": "read_capabilities",
                "command_id": "",
                "arguments": [],
                "adapter_id": "",
                "message": "",
                "error": "",
            }

        prefix = "IDE COMMAND "
        chat_prefix = "IDE CHAT "
        if upper.startswith(chat_prefix):
            first_line, separator, raw_message = stripped.partition("\n\n")
            adapter_id = first_line[len(chat_prefix):].strip()
            if not adapter_id:
                return {
                    "action": "chat_send",
                    "bridge_action": "chat_send",
                    "command_id": "",
                    "arguments": [],
                    "adapter_id": "",
                    "message": "",
                    "error": "missing_ide_chat_adapter",
                }
            if not separator or not raw_message.strip():
                return {
                    "action": "chat_send",
                    "bridge_action": "chat_send",
                    "command_id": "",
                    "arguments": [],
                    "adapter_id": adapter_id,
                    "message": "",
                    "error": "missing_ide_chat_message",
                }
            return {
                "action": "chat_send",
                "bridge_action": "chat_send",
                "command_id": "",
                "arguments": [],
                "adapter_id": adapter_id,
                "message": raw_message.strip(),
                "error": "",
            }

        if not upper.startswith(prefix):
            return {
                "action": "",
                "bridge_action": "",
                "command_id": "",
                "arguments": [],
                "adapter_id": "",
                "message": "",
                "error": "",
            }

        first_line, _, raw_arguments = stripped.partition("\n\n")
        command_id = first_line[len(prefix):].strip()
        if not command_id:
            return {
                "action": "execute_command",
                "bridge_action": "execute_command",
                "command_id": "",
                "arguments": [],
                "adapter_id": "",
                "message": "",
                "error": "missing_ide_command_id",
            }

        arguments: list = []
        if raw_arguments.strip():
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError:
                return {
                    "action": "execute_command",
                    "bridge_action": "execute_command",
                    "command_id": command_id,
                    "arguments": [],
                    "adapter_id": "",
                    "message": "",
                    "error": "invalid_ide_command_arguments",
                }
            arguments = parsed if isinstance(parsed, list) else [parsed]

        return {
            "action": "execute_command",
            "bridge_action": "execute_command",
            "command_id": command_id,
            "arguments": arguments,
            "adapter_id": "",
            "message": "",
            "error": "",
        }


def _normalize_bridge_url(bridge_url: str) -> str:
    value = (bridge_url or "").strip()
    if not value:
        raise ValueError("missing_ide_bridge_url")
    if "://" not in value:
        value = f"http://{value}"
    return value.rstrip("/")


def _target_payload(target: ConnectorTarget) -> dict:
    return {
        "workspace_id": target.workspace_id,
        "session_id": target.session_id,
        "pid": target.pid,
        "process_name": target.process_name,
        "window_title": target.window_title,
        "project_name": target.project_name,
        "workspace_hint": target.workspace_hint,
        "workspace_path": target.workspace_path,
        "resource_url": target.resource_url,
        "debugger_url": target.debugger_url,
        "ide_bridge_url": target.ide_bridge_url,
    }
