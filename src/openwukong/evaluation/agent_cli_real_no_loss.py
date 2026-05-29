# -*- coding: utf-8 -*-
"""Real no-loss probes for Codex/Claude background CLI transports.

The runner uses owned temporary workspaces and non-interactive CLI transports.
It never drives app windows, keyboard, mouse, or clipboard. A real CLI command
is attempted only when explicitly opted in.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.agent_conversation import run_agent_conversation
from openwukong.control.agent_surface import AGENT_TASK_EFFECT_IDS
from openwukong.control.app_resolution import WindowsAppResolver


_ACCEPTANCE_MARKER = "OPENWUKONG_AGENT_CLI_NO_LOSS: PASS"


@dataclasses.dataclass(frozen=True)
class StaticForegroundObserver:
    before: int = 0
    after: int = 0

    def get_foreground_window(self) -> int:
        return int(self.before or 0)

    def get_foreground_window_after(self) -> int:
        return int(self.after or self.before or 0)


class WindowsForegroundObserver:
    def get_foreground_window(self) -> int:
        try:
            import ctypes

            return int(ctypes.windll.user32.GetForegroundWindow())
        except Exception:
            return 0

    def get_foreground_window_after(self) -> int:
        return self.get_foreground_window()


@dataclasses.dataclass(frozen=True)
class AgentCliNoLossCase:
    agent: str
    status: str
    passed: bool
    real_verified: bool
    artifact_path: str
    workspace_root: str
    output_root: str
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    agent_command_attempts: int = 0
    window_input_attempts: int = 0
    workspace_clean: bool = True
    workspace_file_delta: tuple[str, ...] = ()
    conversation_report: dict = dataclasses.field(default_factory=dict)

    @property
    def mode(self) -> str:
        return "agent-cli-real-no-loss-case"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def foreground_focus_stable(self) -> bool:
        before = int(self.foreground_hwnd_before or 0)
        after = int(self.foreground_hwnd_after or 0)
        return not (before and after and before != after)

    def to_dict(self, *, include_details: bool = True) -> dict:
        data = {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "agent": self.agent,
            "status": self.status,
            "passed": self.passed,
            "real_verified": self.real_verified,
            "artifact_path": self.artifact_path,
            "workspace_root": self.workspace_root,
            "output_root": self.output_root,
            "foreground_hwnd_before": int(self.foreground_hwnd_before or 0),
            "foreground_hwnd_after": int(self.foreground_hwnd_after or 0),
            "foreground_focus_stable": self.foreground_focus_stable,
            "agent_command_attempts": int(self.agent_command_attempts or 0),
            "window_input_attempts": int(self.window_input_attempts or 0),
            "workspace_clean": bool(self.workspace_clean),
            "workspace_file_delta": list(self.workspace_file_delta),
        }
        if include_details:
            data["conversation_report"] = dict(self.conversation_report)
        return data


@dataclasses.dataclass(frozen=True)
class AgentCliNoLossReport:
    agents: tuple[str, ...]
    output_root: str
    cases: tuple[AgentCliNoLossCase, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-cli-real-no-loss"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def passed_cases(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.real_verified)

    @property
    def agent_command_attempts(self) -> int:
        return sum(case.agent_command_attempts for case in self.cases)

    @property
    def window_input_attempts(self) -> int:
        return sum(case.window_input_attempts for case in self.cases)

    @property
    def foreground_focus_stable(self) -> bool:
        return not any(not case.foreground_focus_stable for case in self.cases)

    def to_dict(self, *, include_details: bool = True) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "agents": list(self.agents),
            "output_root": self.output_root,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "verified_cases": self.verified_cases,
            "agent_command_attempts": self.agent_command_attempts,
            "window_input_attempts": self.window_input_attempts,
            "foreground_focus_stable": self.foreground_focus_stable,
            "cases": [
                case.to_dict(include_details=include_details)
                for case in self.cases
            ],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_cli_real_no_loss(
    *,
    agents: Iterable[str],
    output_root: str | Path = "",
    allow_cli_execution: bool = False,
    resolver: WindowsAppResolver | None = None,
    command_executor: object | None = None,
    foreground_observer: object | None = None,
    timeout_sec: float = 90.0,
) -> AgentCliNoLossReport:
    started = time.perf_counter()
    names = tuple(str(agent or "").strip() for agent in agents if str(agent or "").strip())
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    observer = foreground_observer or WindowsForegroundObserver()
    cases = tuple(
        _run_case(
            agent=agent,
            output_root=root,
            allow_cli_execution=allow_cli_execution,
            resolver=resolver,
            command_executor=command_executor,
            foreground_observer=observer,
            timeout_sec=timeout_sec,
        )
        for agent in names
    )
    return AgentCliNoLossReport(
        agents=names,
        output_root=str(root),
        cases=cases,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _run_case(
    *,
    agent: str,
    output_root: Path,
    allow_cli_execution: bool,
    resolver: WindowsAppResolver | None,
    command_executor: object | None,
    foreground_observer: object,
    timeout_sec: float,
) -> AgentCliNoLossCase:
    workspace = output_root / "owned_agent_cli_workspaces" / _safe_filename(agent)
    case_output = output_root / "agent_cli_conversations" / _safe_filename(agent)
    workspace.mkdir(parents=True, exist_ok=True)
    case_output.mkdir(parents=True, exist_ok=True)

    before_files = _snapshot_files(workspace)
    foreground_before = _foreground_before(foreground_observer)
    conversation = run_agent_conversation(
        agent=agent,
        project_name="openwukong",
        task_name="agent-cli-real-no-loss",
        message=_no_loss_message(agent),
        acceptance_criteria=(
            "Use the non-interactive background CLI path only.",
            "Do not edit files, launch GUI windows, or request foreground input.",
            f"Return the exact marker {_ACCEPTANCE_MARKER}.",
        ),
        required_markers=(_ACCEPTANCE_MARKER,),
        forbidden_markers=("OPENWUKONG_AGENT_CLI_NO_LOSS: FAIL",),
        workspace_root=str(workspace),
        output_root=str(case_output),
        execute=True,
        dry_run=not allow_cli_execution,
        allow_agent_task=True,
        confirmed_effect_ids=AGENT_TASK_EFFECT_IDS,
        resolver=resolver,
        command_executor=command_executor,
        timeout_sec=timeout_sec,
        audit_log_path=str(case_output / "command-audit.jsonl"),
    )
    foreground_after = _foreground_after(foreground_observer)
    after_files = _snapshot_files(workspace)
    delta = tuple(sorted(after_files - before_files))
    data = conversation.to_dict()
    status = _classify_status(
        data,
        allow_cli_execution=allow_cli_execution,
        workspace_file_delta=delta,
    )
    window_input_attempts = _window_input_attempts(data)
    workspace_clean = not delta
    passed = bool(
        status
        in {
            "verified",
            "skipped_requires_cli_execution_opt_in",
            "background_cli_unavailable",
            "cli_auth_required",
            "cli_access_denied",
            "cli_executable_not_found",
            "cli_execution_failed",
        }
        and workspace_clean
        and window_input_attempts == 0
    )
    case = AgentCliNoLossCase(
        agent=agent,
        status=status,
        passed=passed,
        real_verified=status == "verified",
        artifact_path="",
        workspace_root=str(workspace),
        output_root=str(case_output),
        foreground_hwnd_before=foreground_before,
        foreground_hwnd_after=foreground_after,
        agent_command_attempts=int(data.get("agent_command_attempts", 0) or 0),
        window_input_attempts=window_input_attempts,
        workspace_clean=workspace_clean,
        workspace_file_delta=delta,
        conversation_report=data,
    )
    return _write_case_artifact(output_root, case)


def _classify_status(
    conversation: dict,
    *,
    allow_cli_execution: bool,
    workspace_file_delta: tuple[str, ...],
) -> str:
    if workspace_file_delta:
        return "failed_workspace_mutated"
    if not allow_cli_execution:
        return "skipped_requires_cli_execution_opt_in"
    if conversation.get("decision") == "agent_conversation_requires_app_bridge_or_foreground":
        return "background_cli_unavailable"
    if bool(conversation.get("ok", False)) and bool(conversation.get("execution_attempted", False)):
        return "verified"

    execution = dict(conversation.get("agent_task_report", {}).get("execution_report", {}) or {})
    evidence = " ".join(
        str(execution.get(key, "") or "")
        for key in ("stdout", "stderr", "error")
    ).casefold()
    if "not logged in" in evidence or "/login" in evidence or "auth" in evidence:
        return "cli_auth_required"
    if "access is denied" in evidence or "permissionerror" in evidence or "winerror 5" in evidence:
        return "cli_access_denied"
    if "executable_not_found" in evidence:
        return "cli_executable_not_found"
    if bool(conversation.get("execution_attempted", False)):
        return "cli_execution_failed"
    return "background_cli_unavailable"


def _window_input_attempts(conversation: dict) -> int:
    bridge = conversation.get("app_bridge_send_report", {})
    if not isinstance(bridge, dict):
        return 0
    return int(bridge.get("window_input_attempts", 0) or 0)


def _write_case_artifact(output_root: Path, case: AgentCliNoLossCase) -> AgentCliNoLossCase:
    artifact_dir = output_root / "agent_cli_no_loss"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_filename(case.agent)}.json"
    data = case.to_dict()
    artifact_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return dataclasses.replace(case, artifact_path=str(artifact_path))


def _snapshot_files(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    }


def _no_loss_message(agent: str) -> str:
    return (
        "This is an OpenWukong no-loss background CLI probe. "
        f"Agent: {agent}. "
        "Do not edit files, run GUI apps, or request foreground input. "
        f"Reply with exactly this marker on its own line: {_ACCEPTANCE_MARKER}"
    )


def _foreground_before(observer: object) -> int:
    getter = getattr(observer, "get_foreground_window", None)
    if not callable(getter):
        return 0
    try:
        return int(getter() or 0)
    except Exception:
        return 0


def _foreground_after(observer: object) -> int:
    getter = getattr(observer, "get_foreground_window_after", None)
    if not callable(getter):
        getter = getattr(observer, "get_foreground_window", None)
    if not callable(getter):
        return 0
    try:
        return int(getter() or 0)
    except Exception:
        return 0


def _focus_stable(before: int, after: int) -> bool:
    return not (int(before or 0) and int(after or 0) and int(before or 0) != int(after or 0))


def _resolve_output_root(output_root: str | Path) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve()
    return (Path("logs") / "runtime" / "agent-cli-real-no-loss").resolve()


def _safe_filename(value: str) -> str:
    text = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in str(value or "").strip()
    )
    return text.strip("._") or "unnamed"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run no-loss real probes for background Codex/Claude CLI transports."
    )
    parser.add_argument("--agent", action="append", required=True)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-cli-execution", action="store_true")
    parser.add_argument("--timeout-sec", type=float, default=90.0)
    args = parser.parse_args(argv)

    report = run_agent_cli_real_no_loss(
        agents=tuple(args.agent or ()),
        output_root=args.output_root,
        allow_cli_execution=args.allow_cli_execution,
        timeout_sec=args.timeout_sec,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Agent CLI real no-loss: "
            f"{report.passed_cases}/{report.total_cases} passed, "
            f"verified={report.verified_cases}, "
            f"attempts={report.agent_command_attempts}"
        )
    return 0 if report.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
