# -*- coding: utf-8 -*-
"""Dry-run contract for app-side agent message bridges."""

from __future__ import annotations

import dataclasses
import uuid


BRIDGE_SCHEMA_VERSION = "agent-app-bridge-v1"


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeRequest:
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    message: str
    composed_message: str
    selected_transport: dict
    app_surface_probe: dict
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    request_id: str = dataclasses.field(default_factory=lambda: f"aab-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "agent-app-bridge-request"

    @property
    def schema_version(self) -> str:
        return BRIDGE_SCHEMA_VERSION

    @property
    def app_uia_probe(self) -> dict:
        value = self.app_surface_probe.get("app_uia_probe")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def target_ready(self) -> bool:
        return bool(
            self.app_uia_probe.get("target_matched", False)
            and int(self.app_uia_probe.get("semantic_composer_count", 0) or 0) > 0
        )

    @property
    def native_endpoint_ready(self) -> bool:
        if int(self.app_surface_probe.get("ready_endpoint_count", 0) or 0) <= 0:
            return False
        return bool(self.endpoint)

    @property
    def visual_focus_stable(self) -> bool:
        if "background_screenshot_focus_stable" not in self.app_uia_probe:
            return True
        return bool(self.app_uia_probe.get("background_screenshot_focus_stable", False))

    @property
    def ready(self) -> bool:
        return bool(self.message and self.target_ready and self.native_endpoint_ready and self.visual_focus_stable)

    @property
    def target(self) -> dict:
        windows = self.app_uia_probe.get("matched_windows")
        window = {}
        if isinstance(windows, list) and windows and isinstance(windows[0], dict):
            window = dict(windows[0])
        return {
            "process_name": str(window.get("process_name", "") or ""),
            "pid": int(window.get("pid", 0) or 0),
            "window_title": str(window.get("window_title", "") or ""),
            "hwnd": int(window.get("hwnd", 0) or 0),
            "project_name": self.project_name,
            "task_name": self.task_name,
            "target_matched": self.target_ready,
            "semantic_composer_count": int(self.app_uia_probe.get("semantic_composer_count", 0) or 0),
        }

    @property
    def endpoint(self) -> dict:
        endpoints = self.app_surface_probe.get("endpoints")
        if not isinstance(endpoints, list):
            return {}
        for endpoint in endpoints:
            if isinstance(endpoint, dict) and bool(endpoint.get("ready", False)):
                return dict(endpoint)
        return {}

    @property
    def payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "action": "agent_app_conversation.send_message",
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "message": self.message,
            "composed_message": self.composed_message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "ready": self.ready,
            "target_ready": self.target_ready,
            "native_endpoint_ready": self.native_endpoint_ready,
            "visual_focus_stable": self.visual_focus_stable,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "target": self.target,
            "endpoint": _endpoint_summary(self.endpoint),
            "payload": self.payload,
            "diagnostics": {
                "app_surface_decision": str(self.app_surface_probe.get("decision", "") or ""),
                "app_uia_decision": str(self.app_uia_probe.get("decision", "") or ""),
                "endpoint_count": int(self.app_surface_probe.get("endpoint_count", 0) or 0),
                "ready_endpoint_count": int(self.app_surface_probe.get("ready_endpoint_count", 0) or 0),
                "background_screenshot_count": int(self.app_uia_probe.get("background_screenshot_count", 0) or 0),
                "background_screenshot_focus_stable": self.visual_focus_stable,
            },
        }


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeDryRunReport:
    request: AgentAppBridgeRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "agent-app-bridge-dry-run"

    @property
    def safety_mode(self) -> str:
        return "dry_run"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return not self.validation_errors

    @property
    def decision(self) -> str:
        if not self.request.message:
            return "app_bridge_message_required"
        if not self.request.target_ready:
            return "app_bridge_target_not_ready"
        if not self.request.native_endpoint_ready:
            return "app_bridge_native_connector_not_ready"
        if not self.request.visual_focus_stable:
            return "app_bridge_visual_focus_not_stable"
        if self.validation_errors:
            return "app_bridge_request_invalid"
        return "app_bridge_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


class AgentAppBridgeDryRunAdapter:
    def prepare(self, request: AgentAppBridgeRequest) -> AgentAppBridgeDryRunReport:
        errors = _validate_request(request)
        return AgentAppBridgeDryRunReport(
            request=request,
            validation_errors=errors,
        )


def build_agent_app_bridge_request(
    *,
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    selected_transport: dict | object,
    app_surface_probe: dict | object,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentAppBridgeRequest:
    return AgentAppBridgeRequest(
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=str(composed_message or "").strip(),
        selected_transport=_dict_from_report(selected_transport),
        app_surface_probe=_dict_from_report(app_surface_probe),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
    )


def _validate_request(request: AgentAppBridgeRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.agent_id:
        errors.append("agent_id_required")
    if not request.message:
        errors.append("message_required")
    if not request.composed_message:
        errors.append("composed_message_required")
    if not request.target_ready:
        errors.append("target_not_ready")
    if not request.native_endpoint_ready:
        errors.append("native_endpoint_not_ready")
    if not request.visual_focus_stable:
        errors.append("visual_focus_not_stable")
    return tuple(errors)


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _endpoint_summary(endpoint: dict) -> dict:
    if not endpoint:
        return {}
    return {
        "debugger_url": str(endpoint.get("debugger_url", "") or ""),
        "port": int(endpoint.get("port", 0) or 0),
        "ready": bool(endpoint.get("ready", False)),
        "target_count": int(endpoint.get("target_count", 0) or len(endpoint.get("targets", []) or [])),
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


__all__ = [
    "BRIDGE_SCHEMA_VERSION",
    "AgentAppBridgeDryRunAdapter",
    "AgentAppBridgeDryRunReport",
    "AgentAppBridgeRequest",
    "build_agent_app_bridge_request",
]
