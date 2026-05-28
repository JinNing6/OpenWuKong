# -*- coding: utf-8 -*-
"""Targeted conversation contract for agent chat surfaces."""

from __future__ import annotations

import dataclasses
import json
import time
import uuid
from pathlib import Path
from typing import Callable

from openwukong.control.agent_app_bridge import (
    AgentAppBridgeDryRunAdapter,
    build_agent_app_bridge_request,
)
from openwukong.control.agent_task import AgentTaskRunReport, run_agent_task
from openwukong.control.app_resolution import WindowsAppResolver
from openwukong.control.foreground_takeover import ForegroundTakeoverRequest


DEFAULT_ACCEPTANCE_MARKER = "OPENWUKONG_ACCEPTANCE: PASS"


AppSurfaceProbeRunner = Callable[..., object]


@dataclasses.dataclass(frozen=True)
class AgentConversationAcceptanceReport:
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    missing_required_markers: tuple[str, ...] = ()
    present_forbidden_markers: tuple[str, ...] = ()
    evidence_preview: str = ""

    @property
    def mode(self) -> str:
        return "agent-conversation-acceptance"

    @property
    def accepted(self) -> bool:
        return not self.missing_required_markers and not self.present_forbidden_markers

    @property
    def decision(self) -> str:
        return "accepted" if self.accepted else "acceptance_failed"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "accepted": self.accepted,
            "decision": self.decision,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "missing_required_markers": list(self.missing_required_markers),
            "present_forbidden_markers": list(self.present_forbidden_markers),
            "evidence_preview": self.evidence_preview,
        }


@dataclasses.dataclass(frozen=True)
class AgentConversationRunReport:
    agent: str
    project_name: str
    task_name: str
    message: str
    composed_message: str
    acceptance_criteria: tuple[str, ...]
    required_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...]
    agent_task_report: AgentTaskRunReport
    acceptance_report: AgentConversationAcceptanceReport
    draft_artifact_path: str = ""
    foreground_takeover_request: ForegroundTakeoverRequest | None = None
    app_surface_probe: dict = dataclasses.field(default_factory=dict)
    app_bridge_dry_run: dict = dataclasses.field(default_factory=dict)
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-conversation-runner"

    @property
    def safety_mode(self) -> str:
        return self.agent_task_report.safety_mode

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def agent_command_attempts(self) -> int:
        return int(self.agent_task_report.agent_command_attempts or 0)

    @property
    def ok(self) -> bool:
        if self.decision == "agent_conversation_requires_app_bridge_or_foreground":
            return False
        if self.agent_task_report.execution_attempted:
            return bool(self.agent_task_report.ok and self.acceptance_report.accepted)
        return bool(self.agent_task_report.ok and self.draft_artifact_path)

    @property
    def decision(self) -> str:
        if _requires_app_bridge(self.agent_task_report):
            return "agent_conversation_requires_app_bridge_or_foreground"
        task_decision = self.agent_task_report.decision
        if task_decision == "draft_written":
            return "conversation_draft_written"
        if task_decision == "dry_run_ready":
            return "conversation_dry_run_ready"
        if task_decision == "executed":
            if self.acceptance_report.accepted:
                return "conversation_executed_and_accepted"
            return "conversation_executed_acceptance_failed"
        return task_decision

    def to_dict(self) -> dict:
        selected = self.agent_task_report.surface_binding.selected_transport
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "agent": self.agent,
            "agent_id": self.agent_task_report.surface_binding.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "message": self.message,
            "composed_message": self.composed_message,
            "acceptance_criteria": list(self.acceptance_criteria),
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "workspace_root": self.agent_task_report.workspace_root,
            "output_root": self.agent_task_report.output_root,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "execution_requested": self.agent_task_report.execution_requested,
            "execution_attempted": self.agent_task_report.execution_attempted,
            "dry_run": self.agent_task_report.dry_run,
            "agent_command_attempts": self.agent_command_attempts,
            "draft_artifact_path": self.draft_artifact_path,
            "selected_transport": selected.to_dict() if selected else {},
            "foreground_takeover_request": (
                self.foreground_takeover_request.to_dict()
                if self.foreground_takeover_request
                else {}
            ),
            "app_surface_probe": dict(self.app_surface_probe),
            "app_bridge_dry_run": dict(self.app_bridge_dry_run),
            "acceptance_report": self.acceptance_report.to_dict(),
            "agent_task_report": self.agent_task_report.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_conversation(
    *,
    agent: str,
    message: str,
    project_name: str = "",
    task_name: str = "",
    acceptance_criteria: tuple[str, ...] = (),
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
    workspace_root: str = "",
    output_root: str = "",
    execute: bool = False,
    dry_run: bool = False,
    allow_agent_task: bool = False,
    confirmed_effect_ids: tuple[str, ...] = (),
    resolver: WindowsAppResolver | None = None,
    command_executor: object | None = None,
    app_surface_probe_runner: AppSurfaceProbeRunner | None = None,
    app_surface_screenshot_dir: str = "",
    timeout_sec: float = 120.0,
    audit_log_path: str = "",
) -> AgentConversationRunReport:
    started = time.perf_counter()
    normalized_required = _normalized_markers(required_markers)
    normalized_forbidden = _normalized_markers(forbidden_markers)
    criteria = _normalized_tuple(acceptance_criteria)
    composed = compose_agent_conversation_message(
        project_name=project_name,
        task_name=task_name,
        message=message,
        acceptance_criteria=criteria,
        required_markers=normalized_required,
        forbidden_markers=normalized_forbidden,
    )
    task_report = run_agent_task(
        agent=agent,
        task=composed,
        workspace_root=workspace_root,
        output_root=output_root,
        execute=execute,
        dry_run=dry_run,
        allow_agent_task=allow_agent_task,
        confirmed_effect_ids=confirmed_effect_ids,
        resolver=resolver,
        command_executor=command_executor,
        timeout_sec=timeout_sec,
        audit_log_path=audit_log_path,
    )
    acceptance = evaluate_agent_conversation_acceptance(
        task_report.execution_report,
        required_markers=normalized_required,
        forbidden_markers=normalized_forbidden,
    )
    foreground_request = (
        _build_app_foreground_request(task_report)
        if execute and _requires_app_bridge(task_report)
        else None
    )
    app_surface_probe = _run_app_surface_probe(
        runner=app_surface_probe_runner,
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        resolver=resolver,
        screenshot_dir=str(app_surface_screenshot_dir or "").strip(),
        enabled=bool(foreground_request),
    )
    app_bridge_dry_run = _build_app_bridge_dry_run(
        task_report=task_report,
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=composed,
        required_markers=normalized_required,
        forbidden_markers=normalized_forbidden,
        app_surface_probe=app_surface_probe,
        enabled=bool(foreground_request and app_surface_probe),
    )
    draft_path = _write_conversation_draft(
        task_report=task_report,
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=composed,
        acceptance_criteria=criteria,
        required_markers=normalized_required,
        forbidden_markers=normalized_forbidden,
        acceptance_report=acceptance,
        foreground_takeover_request=foreground_request,
        app_surface_probe=app_surface_probe,
        app_bridge_dry_run=app_bridge_dry_run,
    )
    return AgentConversationRunReport(
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=composed,
        acceptance_criteria=criteria,
        required_markers=normalized_required,
        forbidden_markers=normalized_forbidden,
        agent_task_report=task_report,
        acceptance_report=acceptance,
        draft_artifact_path=draft_path,
        foreground_takeover_request=foreground_request,
        app_surface_probe=app_surface_probe,
        app_bridge_dry_run=app_bridge_dry_run,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def compose_agent_conversation_message(
    *,
    project_name: str = "",
    task_name: str = "",
    message: str,
    acceptance_criteria: tuple[str, ...] = (),
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> str:
    project = str(project_name or "").strip()
    task = str(task_name or "").strip()
    body = str(message or "").strip()
    criteria = _normalized_tuple(acceptance_criteria)
    required = _normalized_markers(required_markers)
    forbidden = _normalized_markers(forbidden_markers)
    parts = ["OpenWukong targeted agent conversation message."]
    if project:
        parts.append(f"Project: {project}")
    if task:
        parts.append(f"Task: {task}")
    parts.append("")
    parts.append("Message:")
    parts.append(body)
    if criteria:
        parts.append("")
        parts.append("Acceptance criteria:")
        parts.extend(f"- {item}" for item in criteria)
    if required or forbidden:
        parts.append("")
        parts.append("Result contract:")
        if required:
            parts.append("Include these exact required marker(s) in the final response:")
            parts.extend(f"- {item}" for item in required)
        if forbidden:
            parts.append("Do not include these forbidden marker(s):")
            parts.extend(f"- {item}" for item in forbidden)
    return "\n".join(parts).strip()


def evaluate_agent_conversation_acceptance(
    execution_report: dict,
    *,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentConversationAcceptanceReport:
    evidence = _execution_evidence_text(execution_report)
    required = _normalized_markers(required_markers)
    forbidden = _normalized_markers(forbidden_markers)
    missing = tuple(marker for marker in required if marker not in evidence)
    present_forbidden = tuple(marker for marker in forbidden if marker in evidence)
    return AgentConversationAcceptanceReport(
        required_markers=required,
        forbidden_markers=forbidden,
        missing_required_markers=missing,
        present_forbidden_markers=present_forbidden,
        evidence_preview=_clip(evidence, 1200),
    )


def _write_conversation_draft(
    *,
    task_report: AgentTaskRunReport,
    agent: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    acceptance_criteria: tuple[str, ...],
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
    acceptance_report: AgentConversationAcceptanceReport,
    foreground_takeover_request: ForegroundTakeoverRequest | None,
    app_surface_probe: dict,
    app_bridge_dry_run: dict,
) -> str:
    root = Path(task_report.output_root)
    root.mkdir(parents=True, exist_ok=True)
    draft_path = root / f"agent-conversation-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json"
    payload = {
        "mode": "agent-conversation-draft",
        "agent": agent,
        "agent_id": task_report.surface_binding.agent_id,
        "project_name": project_name,
        "task_name": task_name,
        "message": message,
        "composed_message": composed_message,
        "acceptance_criteria": list(acceptance_criteria),
        "required_markers": list(required_markers),
        "forbidden_markers": list(forbidden_markers),
        "selected_transport": (
            task_report.surface_binding.selected_transport.to_dict()
            if task_report.surface_binding.selected_transport
            else {}
        ),
        "foreground_takeover_request": (
            foreground_takeover_request.to_dict() if foreground_takeover_request else {}
        ),
        "app_surface_probe": dict(app_surface_probe),
        "app_bridge_dry_run": dict(app_bridge_dry_run),
        "acceptance_report": acceptance_report.to_dict(),
        "agent_task_report": task_report.to_dict(),
    }
    draft_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(draft_path)


def _build_app_foreground_request(task_report: AgentTaskRunReport) -> ForegroundTakeoverRequest:
    selected = task_report.surface_binding.selected_transport
    selected_transport = selected.transport if selected else ""
    return ForegroundTakeoverRequest(
        status="approval_required",
        action="send_agent_conversation_message",
        app_family=task_report.surface_binding.agent_id,
        target_process_name=_process_name_for_agent(task_report.surface_binding.agent_id),
        target_window_title=task_report.agent,
        selected_route=selected.route_id if selected else "",
        selected_transport=selected_transport,
        transport_channel="foreground_or_native_bridge",
        risk_flags=("agent_task_submission", "foreground_focus_or_native_bridge"),
        verification_requirements=(
            "target_project_or_task_name_visible",
            "message_echo_or_result_marker_visible",
        ),
        request_reason="agent_app_conversation_requires_foreground_or_native_bridge",
    )


def _build_app_bridge_dry_run(
    *,
    task_report: AgentTaskRunReport,
    agent: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
    app_surface_probe: dict,
    enabled: bool,
) -> dict:
    selected = task_report.surface_binding.selected_transport
    if not enabled or selected is None:
        return {}
    request = build_agent_app_bridge_request(
        agent=agent,
        agent_id=task_report.surface_binding.agent_id,
        project_name=project_name,
        task_name=task_name,
        message=message,
        composed_message=composed_message,
        selected_transport=selected.to_dict(),
        app_surface_probe=app_surface_probe,
        required_markers=required_markers,
        forbidden_markers=forbidden_markers,
    )
    return AgentAppBridgeDryRunAdapter().prepare(request).to_dict()


def _requires_app_bridge(task_report: AgentTaskRunReport) -> bool:
    selected = task_report.surface_binding.selected_transport
    if selected is None:
        return False
    return (
        not selected.background_capable
        and task_report.command_plan.error == "transport_has_no_command_contract"
    )


def _run_app_surface_probe(
    *,
    runner: AppSurfaceProbeRunner | None,
    agent: str,
    project_name: str,
    task_name: str,
    resolver: WindowsAppResolver | None,
    screenshot_dir: str = "",
    enabled: bool,
) -> dict:
    if not enabled or not callable(runner):
        return {}
    try:
        result = runner(
            agent=agent,
            project_name=project_name,
            task_name=task_name,
            resolver=resolver,
            screenshot_dir=screenshot_dir,
        )
        return _report_to_dict(result)
    except Exception as exc:
        return {
            "mode": "agent-app-surface-probe",
            "safety_mode": "read_only",
            "ok": False,
            "decision": "agent_app_surface_probe_failed",
            "control_allowed": False,
            "control_attempts": 0,
            "error": str(exc) or exc.__class__.__name__,
        }


def _report_to_dict(report: object) -> dict:
    if isinstance(report, dict):
        return dict(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {
        "mode": "agent-app-surface-probe",
        "safety_mode": "read_only",
        "ok": False,
        "decision": "agent_app_surface_probe_invalid_report",
        "control_allowed": False,
        "control_attempts": 0,
    }


def _execution_evidence_text(report: dict) -> str:
    if not isinstance(report, dict):
        return ""
    chunks: list[str] = []
    for key in ("stdout", "stderr", "output", "message", "error"):
        value = report.get(key)
        if value:
            chunks.append(str(value))
    payload = report.get("payload")
    if isinstance(payload, dict):
        chunks.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return "\n".join(chunks)


def _process_name_for_agent(agent_id: str) -> str:
    normalized = str(agent_id or "").strip().lower()
    if normalized == "codex":
        return "Codex.exe"
    if normalized == "claude":
        return "Claude.exe"
    return normalized


def _normalized_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(item or "").strip() for item in values if str(item or "").strip())


def _normalized_markers(values: tuple[str, ...]) -> tuple[str, ...]:
    return _normalized_tuple(values)


def _clip(value: str, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


__all__ = [
    "DEFAULT_ACCEPTANCE_MARKER",
    "AgentConversationAcceptanceReport",
    "AgentConversationRunReport",
    "compose_agent_conversation_message",
    "evaluate_agent_conversation_acceptance",
    "run_agent_conversation",
]
