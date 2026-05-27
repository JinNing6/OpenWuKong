# -*- coding: utf-8 -*-
"""L3 read-only shadow-mode evaluation.

Shadow mode observes the current desktop state and produces auditable route
plans. It never reads conversations through connectors, sends messages, clicks,
types, or executes shell/git/browser commands.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Optional

from openwukong.connectors.route_policy import build_control_route_plan
from openwukong.evaluation.simulation import (
    L1CaseResult,
    L1SimulationHarness,
    L1SimulationReport,
    load_simulation_fixture,
)
from openwukong.monitor.ai_monitor import AIProjectState, AIStatus, MultiProjectAIMonitor

_DIRECT_COMMAND_CONNECTORS = {"terminal", "git"}
_EXACT_ONLY_EXPECTATIONS = {
    "matched_pid",
    "forbidden_matched_pid",
    "matched_window_title",
}
_GOAL_PROFILE_MIN_MATCH_SCORE = 70


class StaticStateObserver:
    """Deterministic observer for tests and recorded state replay."""

    def __init__(self, states: Iterable[AIProjectState]):
        self._states = tuple(states)

    def snapshot(self) -> tuple[AIProjectState, ...]:
        return self._states


class FastDesktopStateObserver:
    """Read-only desktop observer using the fast window scan path."""

    def __init__(self, monitor: Optional[MultiProjectAIMonitor] = None):
        self._monitor = monitor or MultiProjectAIMonitor()

    def snapshot(self) -> tuple[AIProjectState, ...]:
        return tuple(self._monitor.scan_windows_fast())


@dataclasses.dataclass(frozen=True)
class L3ShadowPlan:
    case_id: str
    task_id: str
    task_name: str
    connector_id: str
    expected_connector_id: str
    matched_pid: int
    matched_window_title: str
    workspace_id: str
    match_score: int
    proposed_action: str
    safety_decision: str
    app_family: str = ""
    primary_route_id: str = ""
    route_control_decision: str = ""
    route_missing_capabilities: tuple[str, ...] = ()
    command_plan: dict = dataclasses.field(default_factory=dict)
    session_registry: dict = dataclasses.field(default_factory=dict)
    risks: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    ignored_expectations: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "connector_id": self.connector_id,
            "expected_connector_id": self.expected_connector_id,
            "matched_pid": self.matched_pid,
            "matched_window_title": self.matched_window_title,
            "workspace_id": self.workspace_id,
            "match_score": self.match_score,
            "proposed_action": self.proposed_action,
            "safety_decision": self.safety_decision,
            "app_family": self.app_family,
            "primary_route_id": self.primary_route_id,
            "route_control_decision": self.route_control_decision,
            "route_missing_capabilities": list(self.route_missing_capabilities),
            "command_plan": dict(self.command_plan),
            "session_registry": dict(self.session_registry),
            "risks": list(self.risks),
            "errors": list(self.errors),
            "ignored_expectations": list(self.ignored_expectations),
        }


@dataclasses.dataclass(frozen=True)
class L3ShadowReport:
    suite: str
    expectation_profile: str
    plans: tuple[L3ShadowPlan, ...]
    l1_report: L1SimulationReport
    observed_state_count: int
    observed_states: tuple[dict, ...] = ()
    elapsed_ms: float = 0.0

    @property
    def total_cases(self) -> int:
        return self.l1_report.total_cases

    @property
    def passed_cases(self) -> int:
        return self.l1_report.passed_cases

    @property
    def failed_cases(self) -> int:
        return self.l1_report.failed_cases

    @property
    def pass_rate(self) -> float:
        return self.l1_report.pass_rate

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def false_target_cases(self) -> tuple[str, ...]:
        return tuple(plan.case_id for plan in self.plans if "wrong_target" in plan.risks)

    @property
    def unverifiable_cases(self) -> tuple[str, ...]:
        return tuple(plan.case_id for plan in self.plans if "unverifiable" in plan.risks)

    @property
    def low_confidence_cases(self) -> tuple[str, ...]:
        return tuple(plan.case_id for plan in self.plans if "low_confidence" in plan.risks)

    def to_dict(self) -> dict:
        return {
            "mode": "l3-shadow",
            "suite": self.suite,
            "expectation_profile": self.expectation_profile,
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": self.control_attempts,
            "observed_state_count": self.observed_state_count,
            "observed_states": [dict(state) for state in self.observed_states],
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "false_target_cases": list(self.false_target_cases),
            "unverifiable_cases": list(self.unverifiable_cases),
            "low_confidence_cases": list(self.low_confidence_cases),
            "route_quality": self.l1_report.route_quality(),
            "plans": [plan.to_dict() for plan in self.plans],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class L3ShadowTrendReport:
    reports: tuple[L3ShadowReport, ...]

    @property
    def run_count(self) -> int:
        return len(self.reports)

    @property
    def expectation_profile(self) -> str:
        profiles = {report.expectation_profile for report in self.reports}
        if len(profiles) == 1:
            return next(iter(profiles))
        if not profiles:
            return ""
        return "mixed"

    @property
    def total_cases(self) -> int:
        return sum(report.total_cases for report in self.reports)

    @property
    def passed_cases(self) -> int:
        return sum(report.passed_cases for report in self.reports)

    @property
    def failed_cases(self) -> int:
        return sum(report.failed_cases for report in self.reports)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    @property
    def control_attempts(self) -> int:
        return sum(report.control_attempts for report in self.reports)

    @property
    def observed_state_counts(self) -> tuple[int, ...]:
        return tuple(report.observed_state_count for report in self.reports)

    def connectors(self) -> dict:
        grouped: dict[str, list[tuple[L3ShadowPlan, L1CaseResult]]] = {}
        connector_runs: dict[str, int] = {}
        for report in self.reports:
            seen_in_report: set[str] = set()
            for plan, result in zip(report.plans, report.l1_report.results):
                connector_id = plan.connector_id or plan.expected_connector_id or "unmatched"
                grouped.setdefault(connector_id, []).append((plan, result))
                seen_in_report.add(connector_id)
            for connector_id in seen_in_report:
                connector_runs[connector_id] = connector_runs.get(connector_id, 0) + 1

        summary = {}
        for connector_id, items in sorted(grouped.items()):
            scores = [plan.match_score for plan, _result in items]
            summary[connector_id] = {
                "runs": connector_runs.get(connector_id, 0),
                "cases": len(items),
                "passed": sum(1 for _plan, result in items if result.passed),
                "failed": sum(1 for _plan, result in items if not result.passed),
                "min_match_score": min(scores) if scores else 0,
                "avg_match_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            }
        return summary

    def risk_cases(self, risk: str) -> list[dict]:
        cases: list[dict] = []
        for run_index, report in enumerate(self.reports):
            for plan in report.plans:
                if risk not in plan.risks:
                    continue
                cases.append(
                    {
                        "run_index": run_index,
                        "suite": report.suite,
                        "case_id": plan.case_id,
                        "connector_id": plan.connector_id,
                        "match_score": plan.match_score,
                    }
                )
        return cases

    def unstable_cases(self) -> list[dict]:
        grouped: dict[str, list[tuple[int, L3ShadowPlan]]] = {}
        for run_index, report in enumerate(self.reports):
            for plan in report.plans:
                grouped.setdefault(plan.case_id, []).append((run_index, plan))

        unstable: list[dict] = []
        for case_id in sorted(grouped):
            items = grouped[case_id]
            connectors = _stable_unique(plan.connector_id for _idx, plan in items)
            window_titles = _stable_unique(plan.matched_window_title for _idx, plan in items)
            workspace_ids = _stable_unique(plan.workspace_id for _idx, plan in items)

            drift_dimensions = []
            if len(connectors) > 1:
                drift_dimensions.append("connector")
            if len(window_titles) > 1:
                drift_dimensions.append("window")
            if len(workspace_ids) > 1:
                drift_dimensions.append("workspace")
            if not drift_dimensions:
                continue

            unstable.append(
                {
                    "case_id": case_id,
                    "drift_dimensions": drift_dimensions,
                    "connectors": connectors,
                    "matched_window_titles": window_titles,
                    "workspace_ids": workspace_ids,
                    "runs": [
                        {
                            "run_index": run_index,
                            "connector_id": plan.connector_id,
                            "matched_pid": plan.matched_pid,
                            "matched_window_title": plan.matched_window_title,
                            "workspace_id": plan.workspace_id,
                            "match_score": plan.match_score,
                            "safety_decision": plan.safety_decision,
                        }
                        for run_index, plan in items
                    ],
                }
            )
        return unstable

    def to_dict(self) -> dict:
        return {
            "mode": "l3-shadow-trend",
            "expectation_profile": self.expectation_profile,
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": self.control_attempts,
            "run_count": self.run_count,
            "suites": [report.suite for report in self.reports],
            "observed_state_counts": list(self.observed_state_counts),
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "connectors": self.connectors(),
            "low_confidence_cases": self.risk_cases("low_confidence"),
            "unverifiable_cases": self.risk_cases("unverifiable"),
            "false_target_cases": self.risk_cases("wrong_target"),
            "unstable_cases": self.unstable_cases(),
            "runs": [
                {
                    "suite": report.suite,
                    "total_cases": report.total_cases,
                    "passed_cases": report.passed_cases,
                    "failed_cases": report.failed_cases,
                    "pass_rate": round(report.pass_rate, 4),
                    "observed_state_count": report.observed_state_count,
                    "control_attempts": report.control_attempts,
                }
                for report in self.reports
            ],
        }


class L3ShadowHarness:
    """Run L1-style goals against a read-only observed desktop snapshot."""

    def __init__(
        self,
        *,
        observer: Optional[object] = None,
        l1_harness: Optional[L1SimulationHarness] = None,
        expectation_profile: str = "exact",
    ):
        self.observer = observer or FastDesktopStateObserver()
        self.l1_harness = l1_harness or L1SimulationHarness()
        self.expectation_profile = _normalize_expectation_profile(expectation_profile)

    def run_suite(self, fixture: dict) -> L3ShadowReport:
        started = time.perf_counter()
        states = tuple(self.observer.snapshot())
        serialized_states = [_state_to_dict(state) for state in states]
        suite = str(fixture.get("suite", "") or "l3-shadow")

        shadow_cases = []
        source_cases = [
            raw_case
            for raw_case in fixture.get("cases", [])
            if isinstance(raw_case, dict)
        ]
        for raw_case in source_cases:
            shadow_case = _prepare_shadow_case(
                raw_case,
                serialized_states,
                expectation_profile=self.expectation_profile,
            )
            shadow_cases.append(shadow_case)

        l1_report = self.l1_harness.run_suite({
            "suite": suite,
            "cases": shadow_cases,
        })
        plans = tuple(
            _build_shadow_plan(
                raw_case,
                result,
                serialized_states=serialized_states,
                expectation_profile=self.expectation_profile,
            )
            for raw_case, result in zip(source_cases, l1_report.results)
        )

        return L3ShadowReport(
            suite=suite,
            expectation_profile=self.expectation_profile,
            plans=plans,
            l1_report=l1_report,
            observed_states=tuple(serialized_states),
            observed_state_count=len(states),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


def load_shadow_states(path: str | Path) -> tuple[AIProjectState, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw_states = data
    elif isinstance(data, dict) and isinstance(data.get("states"), list):
        raw_states = data["states"]
    elif isinstance(data, dict) and isinstance(data.get("cases"), list):
        raw_states = []
        for raw_case in data["cases"]:
            if isinstance(raw_case, dict):
                raw_states.extend(raw_case.get("states", []) or [])
    else:
        raw_states = []

    return tuple(
        _state_from_dict(item)
        for item in raw_states
        if isinstance(item, dict)
    )


def format_shadow_report(report: L3ShadowReport) -> str:
    lines = [
        f"L3 Shadow: {report.suite}",
        (
            f"Cases: {report.passed_cases}/{report.total_cases} passed "
            f"({report.pass_rate:.1%})"
        ),
        (
            f"Observed states: {report.observed_state_count}  "
            f"Control attempts: {report.control_attempts}"
        ),
        "",
    ]
    for plan in report.plans:
        status = "PASS" if not plan.risks else "RISK"
        lines.append(
            f"[{status}] {plan.case_id} pid={plan.matched_pid} "
            f"connector={plan.connector_id or '-'} action={plan.proposed_action} "
            f"decision={plan.safety_decision}"
        )
        for risk in plan.risks:
            lines.append(f"  - risk: {risk}")
        for error in plan.errors:
            lines.append(f"  - {error}")
    return "\n".join(lines).rstrip()


def build_shadow_trend_report(reports: Iterable[L3ShadowReport]) -> L3ShadowTrendReport:
    return L3ShadowTrendReport(reports=tuple(reports))


def format_shadow_trend_report(report: L3ShadowTrendReport) -> str:
    lines = [
        "L3 Shadow Trend",
        (
            f"Runs: {report.run_count}  Cases: "
            f"{report.passed_cases}/{report.total_cases} passed ({report.pass_rate:.1%})"
        ),
        (
            f"Observed states/run: {list(report.observed_state_counts)}  "
            f"Control attempts: {report.control_attempts}"
        ),
        "",
    ]
    for connector_id, summary in report.connectors().items():
        lines.append(
            f"{connector_id}: {summary['passed']}/{summary['cases']} passed "
            f"runs={summary['runs']} min={summary['min_match_score']} "
            f"avg={summary['avg_match_score']}"
        )

    unstable = report.unstable_cases()
    if unstable:
        lines.append("")
        lines.append("Unstable cases:")
        for item in unstable:
            dimensions = ",".join(item["drift_dimensions"])
            lines.append(f"- {item['case_id']} drift={dimensions}")
    return "\n".join(lines).rstrip()


def _build_shadow_plan(
    raw_case: dict,
    result: L1CaseResult,
    *,
    serialized_states: Iterable[dict] = (),
    expectation_profile: str = "exact",
) -> L3ShadowPlan:
    goal = raw_case.get("goal", {}) if isinstance(raw_case.get("goal", {}), dict) else {}
    connector_id = result.connector_id
    route_plan = _route_plan_for_result(result, serialized_states)
    risks = _classify_risks(result)
    if route_plan is not None and route_plan.is_blocked and "route_policy_blocked" not in risks:
        risks = risks + ("route_policy_blocked",)
    return L3ShadowPlan(
        case_id=result.case_id,
        task_id=str(goal.get("task_id", "") or goal.get("task_name", "") or result.case_id),
        task_name=str(goal.get("task_name", "") or ""),
        connector_id=connector_id,
        expected_connector_id=result.expected_connector_id,
        matched_pid=result.matched_pid,
        matched_window_title=result.matched_window_title,
        workspace_id=result.workspace_id,
        match_score=result.match_score,
        proposed_action=_proposed_action(goal, connector_id),
        safety_decision=_safety_decision(risks),
        app_family=route_plan.app_family if route_plan is not None else "",
        primary_route_id=route_plan.primary_route.route_id if route_plan is not None else "",
        route_control_decision=route_plan.control_decision if route_plan is not None else "",
        route_missing_capabilities=route_plan.missing_capabilities if route_plan is not None else (),
        command_plan=result.command_plan,
        session_registry=result.session_registry,
        risks=risks,
        errors=result.errors,
        ignored_expectations=_ignored_expectations(raw_case, expectation_profile),
    )


def _prepare_shadow_case(
    raw_case: dict,
    serialized_states: list[dict],
    *,
    expectation_profile: str,
) -> dict:
    shadow_case = dict(raw_case)
    shadow_case["states"] = serialized_states
    if expectation_profile == "goal":
        shadow_case["expect"] = _goal_profile_expectation(raw_case)
    return shadow_case


def _goal_profile_expectation(raw_case: dict) -> dict:
    expectation = raw_case.get("expect", {})
    if not isinstance(expectation, dict):
        expectation = {}

    goal = raw_case.get("goal", {}) if isinstance(raw_case.get("goal", {}), dict) else {}
    output = {
        key: value
        for key, value in expectation.items()
        if key not in _EXACT_ONLY_EXPECTATIONS
    }
    if expectation.get("matched") is False:
        return output

    connector_hint = str(goal.get("connector_hint", "") or "").strip().lower()
    if connector_hint not in _DIRECT_COMMAND_CONNECTORS:
        current_min_score = int(output.get("min_match_score", 0) or 0)
        output["min_match_score"] = max(
            current_min_score,
            _GOAL_PROFILE_MIN_MATCH_SCORE,
        )
    return output


def _ignored_expectations(raw_case: dict, expectation_profile: str) -> tuple[str, ...]:
    if expectation_profile != "goal":
        return ()
    expectation = raw_case.get("expect", {})
    if not isinstance(expectation, dict):
        return ()
    return tuple(
        key
        for key in sorted(_EXACT_ONLY_EXPECTATIONS)
        if key in expectation
    )


def _normalize_expectation_profile(profile: str) -> str:
    normalized = (profile or "exact").strip().lower()
    if normalized not in {"exact", "goal"}:
        raise ValueError(f"unsupported expectation_profile={profile!r}")
    return normalized


def _classify_risks(result: L1CaseResult) -> tuple[str, ...]:
    risks: list[str] = []
    for error in result.errors:
        if "forbidden_matched_pid" in error and "wrong_target" not in risks:
            risks.append("wrong_target")
        if "min_match_score" in error and "low_confidence" not in risks:
            risks.append("low_confidence")
        if (
            "actual_pid=0" in error
            or "actual=0" in error
            or error.startswith("connector_resolution")
            or "matched expected=True" in error
        ) and "unverifiable" not in risks:
            risks.append("unverifiable")
        if error.startswith("command_plan") and "command_plan_invalid" not in risks:
            risks.append("command_plan_invalid")

    if not result.passed and "expectation_failed" not in risks:
        risks.append("expectation_failed")
    return tuple(risks)


def _safety_decision(risks: tuple[str, ...]) -> str:
    if "wrong_target" in risks:
        return "block_wrong_target"
    if "command_plan_invalid" in risks:
        return "block_command_plan"
    if "unverifiable" in risks:
        return "block_unverifiable"
    if "route_policy_blocked" in risks:
        return "block_route_policy"
    if "low_confidence" in risks:
        return "block_low_confidence"
    if risks:
        return "block_expectation_failure"
    return "observe_only"


def _route_plan_for_result(
    result: L1CaseResult,
    serialized_states: Iterable[dict],
):
    matched_state = _find_serialized_state_for_result(result, serialized_states)
    if matched_state is not None:
        return build_control_route_plan(
            SimpleNamespace(
                process_name=str(matched_state.get("process_name", "") or ""),
                window_title=str(matched_state.get("window_title", "") or ""),
                class_name=str(matched_state.get("class_name", "") or ""),
                element_count=int(matched_state.get("ai_element_count", 0) or 0),
            )
        )

    process_name = _process_name_for_connector(result.connector_id)
    if result.matched_pid == 0 and result.connector_id not in _DIRECT_COMMAND_CONNECTORS and not process_name:
        return None

    if not process_name and not result.matched_window_title:
        return None

    return build_control_route_plan(
        SimpleNamespace(
            process_name=process_name,
            window_title=result.matched_window_title or result.connector_id,
            class_name="",
            element_count=0,
        )
    )


def _find_serialized_state_for_result(
    result: L1CaseResult,
    serialized_states: Iterable[dict],
) -> Optional[dict]:
    states = tuple(serialized_states)
    if result.matched_pid:
        for state in states:
            if int(state.get("pid", 0) or 0) == result.matched_pid:
                return state
    if result.matched_window_title:
        for state in states:
            if str(state.get("window_title", "") or "") == result.matched_window_title:
                return state
    return None


def _process_name_for_connector(connector_id: str) -> str:
    connector_id = (connector_id or "").strip().lower()
    if connector_id == "terminal":
        return "WindowsTerminal.exe"
    if connector_id == "git":
        return "git.exe"
    if connector_id == "browser":
        return "browser.exe"
    if connector_id == "codex":
        return "Codex.exe"
    if connector_id == "cursor":
        return "Cursor.exe"
    if connector_id == "ide-extension":
        return "Code.exe"
    if connector_id == "copilot":
        return "Code.exe"
    return ""


def _proposed_action(goal: dict, connector_id: str) -> str:
    if _goal_has_structured_command(goal):
        if _goal_uses_process_broker(goal):
            return "shadow_plan_command_process_start"
        return "shadow_plan_command_intent"
    if not str(goal.get("retry_command", "") or "").strip():
        return "shadow_observe"
    if connector_id in _DIRECT_COMMAND_CONNECTORS:
        return "shadow_execute_command"
    return "shadow_send_message"


def _goal_has_structured_command(goal: dict) -> bool:
    return bool(
        str(goal.get("command_operation", "") or "").strip()
        or goal.get("command_argv")
        or goal.get("command_args")
    )


def _goal_uses_process_broker(goal: dict) -> bool:
    mode = str(goal.get("command_run_mode", "") or "").strip().lower()
    mode = mode.replace("_", "-").replace(" ", "-")
    return mode in {
        "background",
        "broker",
        "long-running",
        "managed-process",
        "process",
        "process-broker",
    }


def _state_to_dict(state: AIProjectState) -> dict:
    return {
        "timestamp": state.timestamp,
        "pid": state.pid,
        "process_name": state.process_name,
        "project_name": state.project_name,
        "window_title": state.window_title,
        "ai_status": state.ai_status.value,
        "ai_model": state.ai_model,
        "agent_enabled": state.agent_enabled,
        "progress_text": state.progress_text,
        "progress_pct": state.progress_pct,
        "last_ai_output": state.last_ai_output,
        "ai_element_count": state.ai_element_count,
    }


def _state_from_dict(data: dict) -> AIProjectState:
    raw_status = str(data.get("ai_status", "") or "unknown")
    try:
        status = AIStatus(raw_status)
    except ValueError:
        status = AIStatus.UNKNOWN

    return AIProjectState(
        timestamp=float(data.get("timestamp", 0.0) or 0.0),
        pid=int(data.get("pid", 0) or 0),
        process_name=str(data.get("process_name", "") or ""),
        project_name=str(data.get("project_name", "") or ""),
        window_title=str(data.get("window_title", "") or ""),
        ai_status=status,
        ai_model=str(data.get("ai_model", "") or ""),
        agent_enabled=bool(data.get("agent_enabled", False)),
        progress_text=str(data.get("progress_text", "") or ""),
        progress_pct=float(data.get("progress_pct", -1.0)),
        last_ai_output=str(data.get("last_ai_output", "") or ""),
        ai_element_count=int(data.get("ai_element_count", 0) or 0),
    )


def _stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return sorted(unique)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run L3 read-only shadow mode against L1-style goal fixtures."
    )
    parser.add_argument("fixture", help="Path to an L1-style goal fixture JSON file.")
    parser.add_argument(
        "--states",
        default="",
        help="Optional JSON state snapshot file. If omitted, performs a read-only fast desktop scan.",
    )
    parser.add_argument(
        "--profile",
        choices=["exact", "goal"],
        default="exact",
        help="Expectation profile: exact replays recorded expectations; goal ignores synthetic PID/window expectations.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Run the same shadow suite multiple times and aggregate a trend report.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="Seconds to wait between repeated shadow runs.",
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    if args.interval < 0:
        parser.error("--interval must be >= 0")

    fixture = load_simulation_fixture(args.fixture)
    if args.states:
        observer = StaticStateObserver(load_shadow_states(args.states))
    else:
        observer = FastDesktopStateObserver()

    harness = L3ShadowHarness(
        observer=observer,
        expectation_profile=args.profile,
    )
    reports = []
    for index in range(args.repeat):
        if index and args.interval:
            time.sleep(args.interval)
        reports.append(harness.run_suite(fixture))

    if args.repeat > 1:
        trend_report = build_shadow_trend_report(reports)
        if args.json:
            print(json.dumps(trend_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_shadow_trend_report(trend_report))
        return 0 if trend_report.failed_cases == 0 else 1

    report = reports[0]
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_shadow_report(report))
    return 0 if report.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
