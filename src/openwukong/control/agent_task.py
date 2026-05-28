# -*- coding: utf-8 -*-
"""Guarded task contract for Codex/Claude-style agent products."""

from __future__ import annotations

import dataclasses
import json
import os
import time
import uuid
from pathlib import Path

from openwukong.control.agent_surface import (
    AGENT_TASK_EFFECT_IDS,
    AgentSurfaceBindingReport,
    build_agent_surface_binding,
)
from openwukong.control.app_resolution import WindowsAppResolver
from openwukong.control.command_runner import (
    CommandExecutionPolicy,
    CommandExecutionRequest,
    CommandRunner,
)
from openwukong.control.side_effects import (
    SideEffectGateReport,
    build_side_effect_policy,
    evaluate_side_effect_policy,
)


AGENT_COMMAND_EFFECTS = ("read", "workspace_write", "network")


@dataclasses.dataclass(frozen=True)
class AgentCommandPlan:
    agent_id: str
    transport_id: str
    argv: tuple[str, ...]
    cwd: str
    command_family: str
    effects: tuple[str, ...] = AGENT_COMMAND_EFFECTS
    ready: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "transport_id": self.transport_id,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "command_family": self.command_family,
            "effects": list(self.effects),
            "ready": self.ready,
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class AgentTaskRunReport:
    agent: str
    task: str
    workspace_root: str
    output_root: str
    surface_binding: AgentSurfaceBindingReport
    command_plan: AgentCommandPlan
    side_effect_gate: SideEffectGateReport
    draft_artifact_path: str = ""
    execution_requested: bool = False
    dry_run: bool = False
    allow_agent_task: bool = False
    execution_attempted: bool = False
    agent_command_attempts: int = 0
    execution_report: dict = dataclasses.field(default_factory=dict)
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-task-runner"

    @property
    def safety_mode(self) -> str:
        if self.execution_attempted:
            return "confirmed_execute"
        if self.dry_run:
            return "dry_run"
        return "draft_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        if self.execution_attempted:
            return bool(self.execution_report.get("ok", False))
        if self.decision == "agent_task_confirmation_required":
            return False
        return bool(self.surface_binding.ok and self.command_plan.ready and self.draft_artifact_path)

    @property
    def decision(self) -> str:
        if not self.surface_binding.ok:
            return self.surface_binding.decision
        if not self.command_plan.ready:
            return "agent_command_plan_not_ready"
        if self.execution_requested and not self.side_effect_gate.allowed:
            return "agent_task_confirmation_required"
        if self.execution_attempted:
            return "executed" if bool(self.execution_report.get("ok", False)) else "execution_failed"
        if self.execution_requested and self.dry_run:
            return "dry_run_ready"
        return "draft_written"

    def to_dict(self) -> dict:
        selected = self.surface_binding.selected_transport
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "agent": self.agent,
            "agent_id": self.surface_binding.agent_id,
            "task": self.task,
            "workspace_root": self.workspace_root,
            "output_root": self.output_root,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "execution_requested": self.execution_requested,
            "dry_run": self.dry_run,
            "allow_agent_task": self.allow_agent_task,
            "execution_attempted": self.execution_attempted,
            "agent_command_attempts": self.agent_command_attempts,
            "draft_artifact_path": self.draft_artifact_path,
            "selected_transport": selected.to_dict() if selected else {},
            "command_plan": self.command_plan.to_dict(),
            "side_effect_gate": self.side_effect_gate.to_dict(),
            "surface_binding": self.surface_binding.to_dict(),
            "execution_report": dict(self.execution_report),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_task(
    *,
    agent: str,
    task: str,
    workspace_root: str = "",
    output_root: str = "",
    execute: bool = False,
    dry_run: bool = False,
    allow_agent_task: bool = False,
    confirmed_effect_ids: tuple[str, ...] = (),
    resolver: WindowsAppResolver | None = None,
    command_executor: object | None = None,
    timeout_sec: float = 120.0,
    audit_log_path: str = "",
) -> AgentTaskRunReport:
    started = time.perf_counter()
    workspace = _resolve_workspace_root(workspace_root)
    output = _resolve_output_root(output_root, workspace)
    task_text = str(task or "").strip()
    binding = build_agent_surface_binding(agent, resolver=resolver)
    command_plan = build_agent_command_plan(binding, task_text=task_text, workspace_root=workspace)
    gate = _evaluate_agent_task_gate(
        confirmed_effect_ids=confirmed_effect_ids,
        allow_agent_task=allow_agent_task,
    )
    draft_artifact_path = _write_task_draft(
        agent=str(agent or "").strip(),
        task=task_text,
        workspace_root=workspace,
        output_root=output,
        binding=binding,
        command_plan=command_plan,
        gate=gate,
        execution_requested=execute,
        dry_run=dry_run,
        allow_agent_task=allow_agent_task,
    )
    execution_attempted = False
    command_attempts = 0
    execution_report: dict = {}
    if execute and gate.allowed and command_plan.ready and not dry_run:
        execution_attempted = True
        command_attempts = 1
        executor = command_executor or CommandRunner(
            CommandExecutionPolicy(
                profile_id="network-enabled",
                workspace_root=workspace,
                timeout_sec=max(0.1, float(timeout_sec or 120.0)),
                audit_log_path=audit_log_path,
                allowed_effects=AGENT_COMMAND_EFFECTS,
            )
        )
        result = executor.execute(
            CommandExecutionRequest(
                argv=command_plan.argv,
                cwd=workspace,
                reason="confirmed agent task execution",
                effects=command_plan.effects,
            )
        )
        execution_report = _execution_report_dict(result)
    return AgentTaskRunReport(
        agent=str(agent or "").strip(),
        task=task_text,
        workspace_root=workspace,
        output_root=output,
        surface_binding=binding,
        command_plan=command_plan,
        side_effect_gate=gate,
        draft_artifact_path=draft_artifact_path,
        execution_requested=bool(execute),
        dry_run=bool(dry_run),
        allow_agent_task=bool(allow_agent_task),
        execution_attempted=execution_attempted,
        agent_command_attempts=command_attempts,
        execution_report=execution_report,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def build_agent_command_plan(
    binding: AgentSurfaceBindingReport,
    *,
    task_text: str,
    workspace_root: str,
) -> AgentCommandPlan:
    selected = binding.selected_transport
    if selected is None:
        return AgentCommandPlan(
            agent_id=binding.agent_id,
            transport_id="",
            argv=(),
            cwd=workspace_root,
            command_family="",
            ready=False,
            error="agent_transport_not_ready",
        )
    executable = str(selected.path or "").strip()
    if not executable:
        return AgentCommandPlan(
            agent_id=binding.agent_id,
            transport_id=selected.transport_id,
            argv=(),
            cwd=workspace_root,
            command_family=selected.command_family,
            ready=False,
            error="agent_executable_path_missing",
        )
    if not task_text:
        return AgentCommandPlan(
            agent_id=binding.agent_id,
            transport_id=selected.transport_id,
            argv=(),
            cwd=workspace_root,
            command_family=selected.command_family,
            ready=False,
            error="task_required",
        )
    if selected.transport_id == "claude-code-cli-managed-terminal":
        argv = (
            executable,
            "-p",
            "--permission-mode",
            "plan",
            "--max-turns",
            "1",
            "--output-format",
            "json",
            "--no-session-persistence",
            task_text,
        )
        return AgentCommandPlan(
            agent_id=binding.agent_id,
            transport_id=selected.transport_id,
            argv=argv,
            cwd=workspace_root,
            command_family="claude -p",
            ready=True,
        )
    if selected.transport_id == "codex-cli-managed-terminal":
        argv = (
            executable,
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "-C",
            workspace_root,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-rules",
            "--json",
            task_text,
        )
        return AgentCommandPlan(
            agent_id=binding.agent_id,
            transport_id=selected.transport_id,
            argv=argv,
            cwd=workspace_root,
            command_family="codex exec",
            ready=True,
        )
    return AgentCommandPlan(
        agent_id=binding.agent_id,
        transport_id=selected.transport_id,
        argv=(),
        cwd=workspace_root,
        command_family=selected.command_family,
        ready=False,
        error="transport_has_no_command_contract",
    )


def _evaluate_agent_task_gate(
    *,
    confirmed_effect_ids: tuple[str, ...],
    allow_agent_task: bool,
) -> SideEffectGateReport:
    policy = build_side_effect_policy(
        blocked_effect_ids=AGENT_TASK_EFFECT_IDS,
        confirmation_required_effect_ids=AGENT_TASK_EFFECT_IDS,
    )
    return evaluate_side_effect_policy(
        policy,
        confirmed_effect_ids=confirmed_effect_ids,
        allow_blocked_effects=allow_agent_task,
    )


def _write_task_draft(
    *,
    agent: str,
    task: str,
    workspace_root: str,
    output_root: str,
    binding: AgentSurfaceBindingReport,
    command_plan: AgentCommandPlan,
    gate: SideEffectGateReport,
    execution_requested: bool,
    dry_run: bool,
    allow_agent_task: bool,
) -> str:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    draft_path = root / f"agent-task-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json"
    payload = {
        "mode": "agent-task-draft",
        "agent": agent,
        "agent_id": binding.agent_id,
        "task": task,
        "workspace_root": workspace_root,
        "execution_requested": bool(execution_requested),
        "dry_run": bool(dry_run),
        "allow_agent_task": bool(allow_agent_task),
        "execution_allowed": bool(gate.allowed),
        "selected_transport": (
            binding.selected_transport.to_dict() if binding.selected_transport else {}
        ),
        "command_plan": command_plan.to_dict(),
        "side_effect_gate": gate.to_dict(),
    }
    draft_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(draft_path)


def _resolve_workspace_root(value: str) -> str:
    candidate = Path(str(value or "").strip() or os.getcwd())
    return str(candidate.resolve())


def _resolve_output_root(value: str, workspace_root: str) -> str:
    if str(value or "").strip():
        return str(Path(str(value)).resolve())
    return str((Path(workspace_root) / "logs" / "runtime" / "agent-tasks").resolve())


def _execution_report_dict(result: object) -> dict:
    if hasattr(result, "to_dict") and callable(getattr(result, "to_dict")):
        return dict(result.to_dict())
    if isinstance(result, dict):
        return dict(result)
    return {"mode": "unknown-execution-result", "ok": bool(getattr(result, "ok", False))}


__all__ = [
    "AGENT_COMMAND_EFFECTS",
    "AgentCommandPlan",
    "AgentTaskRunReport",
    "build_agent_command_plan",
    "run_agent_task",
]
