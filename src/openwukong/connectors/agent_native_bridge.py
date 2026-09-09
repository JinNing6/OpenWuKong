# -*- coding: utf-8 -*-
"""Connector for deterministic agent desktop app native bridges."""

from __future__ import annotations

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.control.agent_native_bridge import (
    AgentNativeBridgeClient,
    AgentNativeBridgeSenderAdapter,
    build_agent_native_bridge_request,
)


class AgentNativeBridgeConnector(SessionConnector):
    """Execute agent app sends through a verified local native endpoint."""

    connector_id = "agent-native-bridge"
    route_id = "app-native-bridge-required"
    display_name = "Agent Native Bridge"

    def __init__(self, *, client: object | None = None, request_timeout: float = 10.0):
        self._client = client or AgentNativeBridgeClient(request_timeout=request_timeout)
        self._request_timeout = float(request_timeout)

    def supports_target(self, target: ConnectorTarget) -> bool:
        return _agent_id_for_target(target) in {"codex", "claude", "cursor"}

    def match_score(self, target: ConnectorTarget) -> int:
        agent_id = _agent_id_for_target(target)
        if agent_id not in {"codex", "claude", "cursor"}:
            return -1
        score = 80
        if _bridge_url(target):
            score += 20
        if target.project_name or target.workspace_path:
            score += 5
        if target.session_id or target.window_title:
            score += 5
        return score

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        return route_id == self.route_id and bool(_bridge_url(target))

    def read_conversation(self, target: ConnectorTarget) -> str:
        request = _request_from_target(target, message="", request_timeout=self._request_timeout)
        try:
            capabilities = self._client.read_capabilities(request)
        except Exception:
            return ""
        for key in ("readbackText", "readback_text", "conversation", "transcript", "text"):
            value = capabilities.get(key) if isinstance(capabilities, dict) else ""
            if value:
                return str(value)
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        request = _request_from_target(
            target,
            message=message,
            request_timeout=self._request_timeout,
        )
        report = AgentNativeBridgeSenderAdapter(
            client=self._client,
            request_timeout=self._request_timeout,
        ).send(request)
        data = report.to_dict()
        return ConnectorActionResult(
            success=report.ok,
            connector_id=self.connector_id,
            action="send_message",
            action_key=request.request_id,
            payload=data,
            error="" if report.ok else report.decision,
        )


def _request_from_target(
    target: ConnectorTarget,
    *,
    message: str,
    request_timeout: float,
):
    del request_timeout
    agent_id = _agent_id_for_target(target)
    project_name = _project_name(target)
    task_name = _task_name(target)
    return build_agent_native_bridge_request(
        bridge_url=_bridge_url(target),
        agent=f"{agent_id} desktop app" if agent_id else "agent desktop app",
        agent_id=agent_id,
        project_name=project_name,
        task_name=task_name,
        message=str(message or ""),
        composed_message=_compose_message(project_name, task_name, message),
        required_surface_kind="desktop_app",
        expected_app_process_names=_expected_process_names(agent_id, target),
        expected_app_pids=(int(target.pid),) if int(target.pid or 0) > 0 else (),
        required_markers=(str(message or ""),) if str(message or "").strip() else (),
    )


def _bridge_url(target: ConnectorTarget) -> str:
    return str(target.agent_native_bridge_url or "").strip()


def _agent_id_for_target(target: ConnectorTarget) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            target.process_name,
            target.window_title,
            target.project_name,
            target.workspace_hint,
            target.resource_url,
        )
    ).casefold()
    if "claude" in text:
        return "claude"
    if "cursor" in text:
        return "cursor"
    if "codex" in text:
        return "codex"
    return ""


def _project_name(target: ConnectorTarget) -> str:
    for value in (target.project_name, target.workspace_hint, target.workspace_path):
        text = str(value or "").strip()
        if text:
            return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return ""


def _task_name(target: ConnectorTarget) -> str:
    for value in (target.session_id, target.window_title):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _compose_message(project_name: str, task_name: str, message: str) -> str:
    return (
        f"Project: {project_name}\n"
        f"Task: {task_name}\n\n"
        f"Message:\n{message}"
    )


def _expected_process_names(agent_id: str, target: ConnectorTarget) -> tuple[str, ...]:
    process_name = str(target.process_name or "").strip()
    if process_name:
        return (process_name,)
    if agent_id == "codex":
        return ("codex.exe",)
    if agent_id == "claude":
        return ("claude.exe",)
    if agent_id == "cursor":
        return ("cursor.exe",)
    return ()


__all__ = ["AgentNativeBridgeConnector"]
