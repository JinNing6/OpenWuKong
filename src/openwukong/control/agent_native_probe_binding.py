# -*- coding: utf-8 -*-
"""Bind ready agent native connector probe endpoints into Fabric targets."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex


@dataclasses.dataclass(frozen=True)
class AgentNativeFabricBinding:
    ownership: SessionOwnership
    target: ConnectorTarget
    endpoint: dict

    @property
    def mode(self) -> str:
        return "agent-native-fabric-binding"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "ownership": self.ownership.to_dict(),
            "target": _target_to_dict(self.target),
            "endpoint": dict(self.endpoint),
        }


def agent_native_fabric_bindings_from_probe_report(
    report: object,
    *,
    manifest_path: str | Path = "",
    workspace_path: str = "",
) -> tuple[AgentNativeFabricBinding, ...]:
    data = _dict_from_report(report)
    bindings: list[AgentNativeFabricBinding] = []
    for endpoint in data.get("endpoints", ()) or ():
        if not isinstance(endpoint, dict):
            continue
        binding = _binding_from_endpoint(
            endpoint,
            report_data=data,
            manifest_path=str(manifest_path or ""),
            workspace_path=str(workspace_path or ""),
        )
        if binding is not None:
            bindings.append(binding)
    return tuple(bindings)


def ownership_index_from_agent_native_probe_report(
    report: object,
    *,
    manifest_path: str | Path = "",
    workspace_path: str = "",
) -> SessionOwnershipIndex:
    return SessionOwnershipIndex(
        tuple(
            binding.ownership
            for binding in agent_native_fabric_bindings_from_probe_report(
                report,
                manifest_path=manifest_path,
                workspace_path=workspace_path,
            )
        )
    )


def _binding_from_endpoint(
    endpoint: dict,
    *,
    report_data: dict,
    manifest_path: str,
    workspace_path: str,
) -> AgentNativeFabricBinding | None:
    if str(endpoint.get("endpoint_type", "") or "") != "agent_native_bridge":
        return None
    if not bool(endpoint.get("ready", False)):
        return None
    bridge_url = str(endpoint.get("bridge_url", "") or "").strip().rstrip("/")
    if not bridge_url:
        return None
    metadata = _dict(endpoint.get("metadata"))
    app_binding = _dict(metadata.get("app_binding"))
    agent_id = _agent_id(metadata, report_data)
    project_name = _first_text(
        metadata.get("project_name"),
        report_data.get("project_name"),
        app_binding.get("project_name"),
    )
    task_name = _first_text(
        metadata.get("task_name"),
        report_data.get("task_name"),
        app_binding.get("task_name"),
    )
    resolved_workspace = _first_text(
        workspace_path,
        metadata.get("workspace_path"),
        metadata.get("requested_workspace_path"),
        app_binding.get("workspace_path"),
        app_binding.get("workspace"),
    )
    process_name = _first_text(
        app_binding.get("process_name"),
        app_binding.get("processName"),
        app_binding.get("executable_name"),
        app_binding.get("executableName"),
        _default_process_name(agent_id),
    )
    window_title = _first_text(
        app_binding.get("window_title"),
        app_binding.get("windowTitle"),
        app_binding.get("title"),
        process_name,
    )
    pid = _int_value(app_binding.get("pid"))
    target = ConnectorTarget(
        session_id=task_name,
        pid=pid,
        process_name=process_name,
        window_title=window_title,
        project_name=project_name,
        workspace_hint=resolved_workspace or project_name,
        workspace_path=resolved_workspace,
        agent_native_bridge_url=bridge_url,
    )
    ownership = SessionOwnership(
        owned=True,
        ownership_source="agent_native_connector_probe",
        manifest_path=manifest_path,
        route_id="app-native-bridge-required",
        connector_id="agent-native-bridge",
        action_id=f"bind_{agent_id or 'agent'}_native_bridge",
        pid=pid,
        endpoint=bridge_url,
        workspace_root=resolved_workspace,
        cleanup_ready=False,
    )
    return AgentNativeFabricBinding(
        ownership=ownership,
        target=target,
        endpoint=dict(endpoint),
    )


def _dict_from_report(report: object) -> dict:
    if isinstance(report, dict):
        return dict(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _target_to_dict(target: ConnectorTarget) -> dict:
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
        "agent_native_bridge_url": target.agent_native_bridge_url,
    }


def _agent_id(metadata: dict, report_data: dict) -> str:
    text = _first_text(metadata.get("agent_id"), report_data.get("agent_id"), report_data.get("agent"))
    folded = text.casefold()
    if "codex" in folded:
        return "codex"
    if "claude" in folded:
        return "claude"
    if "cursor" in folded:
        return "cursor"
    return folded


def _default_process_name(agent_id: str) -> str:
    if agent_id == "codex":
        return "Codex.exe"
    if agent_id == "claude":
        return "Claude.exe"
    if agent_id == "cursor":
        return "Cursor.exe"
    return ""


def _dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "AgentNativeFabricBinding",
    "agent_native_fabric_bindings_from_probe_report",
    "ownership_index_from_agent_native_probe_report",
]
