# -*- coding: utf-8 -*-
"""Bridge supervisor goals into structured command control execution."""

from __future__ import annotations

import dataclasses
import time

from openwukong.control import (
    CommandPlanIntent,
    CommandPlanReport,
    CommandProcessBroker,
    CommandProcessBrokerConfig,
    ControlCommandExecutionReport,
    ControlFabric,
)


@dataclasses.dataclass(frozen=True)
class SupervisorCommandExecutionConfig:
    """Execution defaults applied when a goal does not override them."""

    timeout_sec: float = 60.0
    audit_log_path: str = ""
    require_owned_session: bool = False
    max_output_chars: int = 8000
    process_storage_path: str = "logs/runtime/supervisor-command-processes.json"


@dataclasses.dataclass(frozen=True)
class SupervisorCommandProcessStartReport:
    command_plan: CommandPlanReport
    decision: str
    ok: bool
    allow_control: bool
    ownership_required: bool
    broker_report: dict | None = None
    broker_snapshot: dict | None = None
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "supervisor-command-process-start"

    @property
    def safety_mode(self) -> str:
        return "explicit_control_gate"

    @property
    def control_allowed(self) -> bool:
        return bool(self.allow_control and self.ok)

    @property
    def control_attempts(self) -> int:
        return int((self.broker_report or {}).get("control_attempts", 0) or 0)

    @property
    def process_id(self) -> str:
        return str((self.broker_report or {}).get("process_id", "") or "")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "decision": self.decision,
            "ownership_required": self.ownership_required,
            "process_id": self.process_id,
            "command_plan": self.command_plan.to_dict(),
            "broker_report": dict(self.broker_report or {}),
            "broker_snapshot": dict(self.broker_snapshot or {}),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class SupervisorCommandExecutor:
    """Plan and execute TaskGoal command fields through ControlFabric."""

    def __init__(
        self,
        *,
        fabric: ControlFabric | None = None,
        config: SupervisorCommandExecutionConfig | None = None,
    ):
        self.config = config or SupervisorCommandExecutionConfig()
        self.fabric = fabric or ControlFabric(
            require_owned_session_for_execution=self.config.require_owned_session
        )

    def intent_for_goal(self, goal: object) -> CommandPlanIntent:
        workspace_path = str(getattr(goal, "workspace_path", "") or "")
        return CommandPlanIntent(
            operation=str(getattr(goal, "command_operation", "") or "raw.argv"),
            workspace_root=workspace_path,
            cwd=workspace_path,
            argv=_string_sequence(getattr(goal, "command_argv", ())),
            args=_string_sequence(getattr(goal, "command_args", ())),
            reason=_goal_reason(goal),
            effects=_string_sequence(getattr(goal, "command_effects", ())),
            profile_id=str(getattr(goal, "command_profile", "") or ""),
            timeout_sec=_float_value(
                getattr(goal, "command_timeout_sec", None),
                self.config.timeout_sec,
            ),
            audit_log_path=str(
                getattr(goal, "command_audit_log_path", "") or self.config.audit_log_path
            ),
            require_owned_session=bool(
                getattr(goal, "command_require_owned_session", False)
                or self.config.require_owned_session
            ),
            max_output_chars=self.config.max_output_chars,
        )

    def plan_goal(self, goal: object) -> CommandPlanReport:
        return self.fabric.plan_command_intent(self.intent_for_goal(goal))

    def execute_goal(
        self,
        goal: object,
        *,
        allow_control: bool = False,
    ) -> ControlCommandExecutionReport:
        return self.fabric.execute_command_intent(
            self.intent_for_goal(goal),
            allow_control=allow_control,
        )

    def start_process_goal(
        self,
        goal: object,
        *,
        allow_control: bool = False,
    ) -> SupervisorCommandProcessStartReport:
        started = time.perf_counter()
        plan = self.plan_goal(goal)
        ownership_required = bool(
            self.config.require_owned_session
            or plan.policy.require_owned_session
        )
        if not plan.ok:
            return SupervisorCommandProcessStartReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=allow_control,
                ownership_required=ownership_required,
                error=plan.error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        if not allow_control:
            return SupervisorCommandProcessStartReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=False,
                ownership_required=ownership_required,
                error="explicit_control_permission_required",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        if ownership_required and not plan.execution_request.ownership.owned:
            return SupervisorCommandProcessStartReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=True,
                ownership_required=True,
                error="owned_session_required",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        broker = CommandProcessBroker(
            CommandProcessBrokerConfig(
                workspace_root=plan.policy.workspace_root,
                storage_path=_process_storage_path(goal, self.config),
                profile_id=plan.policy.profile_id,
                timeout_sec=plan.policy.timeout_sec,
                audit_log_path=plan.policy.audit_log_path,
                require_owned_session=ownership_required,
            )
        )
        broker_report = broker.start(
            argv=plan.execution_request.argv,
            cwd=plan.execution_request.cwd,
            effects=plan.execution_request.effects,
            reason=plan.execution_request.reason,
            env=plan.execution_request.env,
            ownership=plan.execution_request.ownership,
            allow_control=True,
        )
        broker_snapshot = broker.snapshot()
        ok = bool(broker_report.get("ok"))
        return SupervisorCommandProcessStartReport(
            command_plan=plan,
            decision="started_process" if ok else "failed",
            ok=ok,
            allow_control=True,
            ownership_required=ownership_required,
            broker_report=broker_report,
            broker_snapshot=broker_snapshot,
            error=str(broker_report.get("error", "") or ""),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


def goal_has_structured_command(goal: object) -> bool:
    return bool(
        str(getattr(goal, "command_operation", "") or "").strip()
        or _string_sequence(getattr(goal, "command_argv", ()))
        or _string_sequence(getattr(goal, "command_args", ()))
    )


def goal_uses_process_broker(goal: object) -> bool:
    mode = str(getattr(goal, "command_run_mode", "") or "").strip().lower()
    mode = mode.replace("_", "-").replace(" ", "-")
    return mode in {
        "background",
        "broker",
        "long-running",
        "managed-process",
        "process",
        "process-broker",
    }


def _goal_reason(goal: object) -> str:
    task_name = str(getattr(goal, "task_name", "") or "").strip()
    goal_text = str(getattr(goal, "goal", "") or "").strip()
    if task_name and goal_text:
        return f"{task_name}: {goal_text}"
    return task_name or goal_text


def _string_sequence(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _float_value(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _process_storage_path(
    goal: object,
    config: SupervisorCommandExecutionConfig,
) -> str:
    return str(
        getattr(goal, "command_process_storage_path", "")
        or config.process_storage_path
        or ""
    )
