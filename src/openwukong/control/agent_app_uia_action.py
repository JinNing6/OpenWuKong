# -*- coding: utf-8 -*-
"""Dry-run contract for UIA semantic app-side agent actions.

This module only validates whether an app surface exposes enough UI Automation
semantics for a future background action. It does not call SetValue, Invoke,
keyboard, mouse, or clipboard APIs.
"""

from __future__ import annotations

import dataclasses
import uuid


UIA_ACTION_SCHEMA_VERSION = "agent-app-uia-semantic-action-v1"


@dataclasses.dataclass(frozen=True)
class AgentAppUiaSemanticActionRequest:
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    message: str
    selected_transport: dict
    app_surface_probe: dict
    request_id: str = dataclasses.field(default_factory=lambda: f"uiasa-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "agent-app-uia-semantic-action-request"

    @property
    def schema_version(self) -> str:
        return UIA_ACTION_SCHEMA_VERSION

    @property
    def app_uia_probe(self) -> dict:
        value = self.app_surface_probe.get("app_uia_probe")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def visual_focus_stable(self) -> bool:
        if "background_screenshot_focus_stable" not in self.app_uia_probe:
            return True
        return bool(self.app_uia_probe.get("background_screenshot_focus_stable", False))

    @property
    def target_ready(self) -> bool:
        return bool(
            self.app_uia_probe.get("target_matched", False)
            and int(self.app_uia_probe.get("semantic_composer_count", 0) or 0) > 0
        )

    @property
    def composer(self) -> dict:
        for candidate in _list_dicts(self.app_uia_probe.get("composer_candidates")):
            patterns = set(str(item) for item in candidate.get("patterns", []) or [])
            if (
                bool(candidate.get("semantic_composer", False))
                and bool(candidate.get("visible", False))
                and bool(candidate.get("is_enabled", False))
                and "Value" in patterns
            ):
                return candidate
        return {}

    @property
    def submit_control(self) -> dict:
        for candidate in _list_dicts(self.app_uia_probe.get("submit_candidates")):
            patterns = set(str(item) for item in candidate.get("patterns", []) or [])
            if (
                bool(candidate.get("visible", False))
                and bool(candidate.get("is_enabled", False))
                and "Invoke" in patterns
            ):
                return candidate
        return {}

    @property
    def uia_value_pattern_ready(self) -> bool:
        return bool(self.composer)

    @property
    def uia_invoke_pattern_ready(self) -> bool:
        return bool(self.submit_control)

    @property
    def ready(self) -> bool:
        return bool(
            self.message
            and self.target_ready
            and self.uia_value_pattern_ready
            and self.uia_invoke_pattern_ready
            and self.visual_focus_stable
        )

    @property
    def target(self) -> dict:
        window = {}
        windows = _list_dicts(self.app_uia_probe.get("matched_windows"))
        if windows:
            window = windows[0]
        return {
            "process_name": str(window.get("process_name", "") or ""),
            "pid": int(window.get("pid", 0) or 0),
            "window_title": str(window.get("window_title", "") or ""),
            "hwnd": int(window.get("hwnd", 0) or 0),
            "project_name": self.project_name,
            "task_name": self.task_name,
            "target_matched": self.target_ready,
            "semantic_composer_count": int(self.app_uia_probe.get("semantic_composer_count", 0) or 0),
            "submit_candidate_count": int(self.app_uia_probe.get("submit_candidate_count", 0) or 0),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "ready": self.ready,
            "target_ready": self.target_ready,
            "uia_value_pattern_ready": self.uia_value_pattern_ready,
            "uia_invoke_pattern_ready": self.uia_invoke_pattern_ready,
            "visual_focus_stable": self.visual_focus_stable,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "target": self.target,
            "composer": dict(self.composer),
            "submit_control": dict(self.submit_control),
            "payload": {
                "schema_version": self.schema_version,
                "request_id": self.request_id,
                "action": "agent_app_conversation.uia_semantic_send_message",
                "agent": self.agent,
                "agent_id": self.agent_id,
                "project_name": self.project_name,
                "task_name": self.task_name,
                "message": self.message,
            },
            "diagnostics": {
                "app_surface_decision": str(self.app_surface_probe.get("decision", "") or ""),
                "app_uia_decision": str(self.app_uia_probe.get("decision", "") or ""),
                "background_screenshot_count": int(self.app_uia_probe.get("background_screenshot_count", 0) or 0),
                "background_screenshot_focus_stable": self.visual_focus_stable,
            },
        }


@dataclasses.dataclass(frozen=True)
class AgentAppUiaSemanticActionDryRunReport:
    request: AgentAppUiaSemanticActionRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "agent-app-uia-semantic-action-dry-run"

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
    def window_input_attempts(self) -> int:
        return 0

    @property
    def uia_value_set_attempts(self) -> int:
        return 0

    @property
    def uia_invoke_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return not self.validation_errors

    @property
    def decision(self) -> str:
        if not self.request.message:
            return "uia_semantic_action_message_required"
        if not self.request.target_ready:
            return "uia_semantic_action_target_not_ready"
        if not self.request.uia_value_pattern_ready:
            return "uia_semantic_action_value_pattern_not_ready"
        if not self.request.uia_invoke_pattern_ready:
            return "uia_semantic_action_invoke_pattern_not_ready"
        if not self.request.visual_focus_stable:
            return "uia_semantic_action_visual_focus_not_stable"
        if self.validation_errors:
            return "uia_semantic_action_request_invalid"
        return "uia_semantic_action_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


class AgentAppUiaSemanticActionDryRunAdapter:
    def prepare(
        self,
        request: AgentAppUiaSemanticActionRequest,
    ) -> AgentAppUiaSemanticActionDryRunReport:
        return AgentAppUiaSemanticActionDryRunReport(
            request=request,
            validation_errors=_validate_request(request),
        )


def build_agent_app_uia_semantic_action_request(
    *,
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    message: str,
    selected_transport: dict | object,
    app_surface_probe: dict | object,
) -> AgentAppUiaSemanticActionRequest:
    return AgentAppUiaSemanticActionRequest(
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        selected_transport=_dict_from_report(selected_transport),
        app_surface_probe=_dict_from_report(app_surface_probe),
    )


def _validate_request(request: AgentAppUiaSemanticActionRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.agent_id:
        errors.append("agent_id_required")
    if not request.message:
        errors.append("message_required")
    if not request.target_ready:
        errors.append("target_not_ready")
    if not request.uia_value_pattern_ready:
        errors.append("uia_value_pattern_not_ready")
    if not request.uia_invoke_pattern_ready:
        errors.append("uia_invoke_pattern_not_ready")
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


def _list_dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


__all__ = [
    "UIA_ACTION_SCHEMA_VERSION",
    "AgentAppUiaSemanticActionDryRunAdapter",
    "AgentAppUiaSemanticActionDryRunReport",
    "AgentAppUiaSemanticActionRequest",
    "build_agent_app_uia_semantic_action_request",
]
