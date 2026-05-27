# -*- coding: utf-8 -*-
"""L1 offline simulation harness.

L1 fixtures replay recorded metadata only. They do not start, inspect, or
control live desktop applications.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Optional

from openwukong.connectors import (
    BrowserSessionConnector,
    CodexDesktopConnector,
    ConnectorManager,
    ConnectorTarget,
    CopilotIDEConnector,
    CursorIDEConnector,
    GitCommandConnector,
    IDEExtensionConnector,
    TerminalCommandConnector,
    UIAIDEConnector,
)
from openwukong.monitor.ai_monitor import AIProjectState, AIStatus
from openwukong.control.session_registry import build_session_registry_snapshot
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.supervisor.identity import WorkspaceIdentityModel

_DIRECT_CONNECTORS = {"terminal", "git", "browser", "ide-extension"}
_WINDOWLESS_DIRECT_CONNECTORS = {"terminal", "git", "ide-extension"}
_FUZZY_MATCH_MIN_SCORE = 70
_PRIMARY_SCENARIO_SPECS = {
    "wechat.chat.draft_reply": {
        "route_id": "uia-semantic-chat-draft",
        "connector_id": "desktop-uia",
        "proposed_action": "draft_chat_message",
        "requires_confirmation": True,
        "allowed_primitives": ("locate_contact", "locate_input", "write_draft"),
        "blocked_primitives": ("send_message",),
        "allowed_effects": ("recorded_context.read", "local_draft.write"),
        "blocked_effects": ("external_communication.send_message",),
        "risks": ("external_message_send_requires_confirmation",),
    },
    "browser.research.collect_sources": {
        "route_id": "browser-devtools-or-extension",
        "connector_id": "browser",
        "proposed_action": "draft_browser_research_plan",
        "requires_confirmation": False,
        "allowed_primitives": ("read_recorded_dom", "rank_sources", "draft_summary"),
        "blocked_primitives": ("open_live_tab", "submit_form"),
        "allowed_effects": ("recorded_context.read", "local_draft.write"),
        "blocked_effects": (
            "browser_navigation.open_live_tab",
            "browser_form_submit.submit_form",
        ),
        "risks": (),
    },
    "files.search.find_candidate": {
        "route_id": "windows-search-index",
        "connector_id": "file-search",
        "proposed_action": "rank_file_candidates",
        "requires_confirmation": False,
        "allowed_primitives": ("read_index_snapshot", "rank_candidates"),
        "blocked_primitives": ("open_file", "modify_file", "real_filesystem_scan"),
        "allowed_effects": ("recorded_context.read", "local_draft.write"),
        "blocked_effects": (
            "file_open.open_file",
            "file_modify.modify_file",
            "filesystem_scan.real_user_files",
        ),
        "risks": (),
    },
    "codex.project.submit_task_draft": {
        "route_id": "codex-task-draft",
        "connector_id": "codex",
        "proposed_action": "draft_codex_project_task",
        "requires_confirmation": True,
        "allowed_primitives": ("select_recorded_workspace", "build_task_payload", "draft_task"),
        "blocked_primitives": ("submit_task", "start_agent"),
        "allowed_effects": ("recorded_context.read", "local_draft.write"),
        "blocked_effects": (
            "agent_task_submission.submit_task",
            "agent_start.start_agent",
        ),
        "risks": ("agent_start_requires_confirmation",),
    },
}


@dataclasses.dataclass(frozen=True)
class L1CaseResult:
    suite: str
    case_id: str
    passed: bool
    errors: tuple[str, ...]
    matched_pid: int = 0
    matched_window_title: str = ""
    connector_id: str = ""
    expected_connector_id: str = ""
    workspace_id: str = ""
    match_score: int = -1
    min_match_score: int = 0
    command_plan: dict = dataclasses.field(default_factory=dict)
    session_registry: dict = dataclasses.field(default_factory=dict)
    primary_scenario_plan: dict = dataclasses.field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "suite": self.suite,
            "case_id": self.case_id,
            "passed": self.passed,
            "errors": list(self.errors),
            "matched_pid": self.matched_pid,
            "matched_window_title": self.matched_window_title,
            "connector_id": self.connector_id,
            "expected_connector_id": self.expected_connector_id,
            "workspace_id": self.workspace_id,
            "match_score": self.match_score,
            "min_match_score": self.min_match_score,
            "command_plan": dict(self.command_plan),
            "session_registry": dict(self.session_registry),
            "primary_scenario_plan": dict(self.primary_scenario_plan),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class L1SimulationReport:
    suite: str
    results: tuple[L1CaseResult, ...]

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def passed_cases(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    def to_dict(self) -> dict:
        return {
            "suite": self.suite,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "connector_confusion": self.connector_confusion(),
            "low_score_cases": self.low_score_cases(),
            "wrong_target_cases": self.wrong_target_cases(),
            "route_quality": self.route_quality(),
            "results": [result.to_dict() for result in self.results],
        }

    def connector_confusion(self) -> dict:
        matrix: dict[str, dict[str, int]] = {}
        for result in self.results:
            expected = result.expected_connector_id
            actual = result.connector_id
            if not expected or expected == actual:
                continue
            if expected not in matrix:
                matrix[expected] = {}
            matrix[expected][actual] = matrix[expected].get(actual, 0) + 1
        return matrix

    def low_score_cases(self) -> list[dict]:
        cases = []
        for result in self.results:
            if result.min_match_score and result.match_score < result.min_match_score:
                cases.append(
                    {
                        "case_id": result.case_id,
                        "match_score": result.match_score,
                        "min_match_score": result.min_match_score,
                    }
                )
        return cases

    def wrong_target_cases(self) -> list[str]:
        cases = []
        for result in self.results:
            if any("forbidden_matched_pid" in error for error in result.errors):
                cases.append(result.case_id)
        return cases

    def route_quality(self) -> dict:
        grouped: dict[str, list[L1CaseResult]] = {}
        for result in self.results:
            connector_id = result.connector_id or result.expected_connector_id or "unmatched"
            grouped.setdefault(connector_id, []).append(result)

        quality = {}
        for connector_id, results in sorted(grouped.items()):
            scores = [result.match_score for result in results]
            quality[connector_id] = {
                "cases": len(results),
                "passed": sum(1 for result in results if result.passed),
                "failed": sum(1 for result in results if not result.passed),
                "min_match_score": min(scores) if scores else 0,
                "avg_match_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            }
        return quality


@dataclasses.dataclass(frozen=True)
class L1TrendReport:
    reports: tuple[L1SimulationReport, ...]

    @property
    def run_count(self) -> int:
        return len(self.reports)

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

    def to_dict(self) -> dict:
        return {
            "run_count": self.run_count,
            "suites": [report.suite for report in self.reports],
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "connectors": self.connectors(),
            "regressions": self.regressions(),
        }

    def connectors(self) -> dict:
        grouped: dict[str, list[L1CaseResult]] = {}
        connector_runs: dict[str, int] = {}
        for report in self.reports:
            seen_in_report: set[str] = set()
            for result in report.results:
                connector_id = result.connector_id or result.expected_connector_id or "unmatched"
                grouped.setdefault(connector_id, []).append(result)
                seen_in_report.add(connector_id)
            for connector_id in seen_in_report:
                connector_runs[connector_id] = connector_runs.get(connector_id, 0) + 1

        summary = {}
        for connector_id, results in sorted(grouped.items()):
            scores = [result.match_score for result in results]
            summary[connector_id] = {
                "runs": connector_runs.get(connector_id, 0),
                "cases": len(results),
                "passed": sum(1 for result in results if result.passed),
                "failed": sum(1 for result in results if not result.passed),
                "min_match_score": min(scores) if scores else 0,
                "avg_match_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            }
        return summary

    def regressions(self) -> list[dict]:
        items: list[dict] = []
        for report in self.reports:
            for result in report.results:
                if result.passed:
                    continue
                items.append(
                    {
                        "suite": report.suite,
                        "case_id": result.case_id,
                        "connector_id": result.connector_id,
                        "expected_connector_id": result.expected_connector_id,
                        "match_score": result.match_score,
                        "errors": list(result.errors),
                    }
                )
        return items


def build_trend_report(reports: Iterable[L1SimulationReport]) -> L1TrendReport:
    return L1TrendReport(reports=tuple(reports))


class L1SimulationHarness:
    """Run simulation fixtures through offline recognition and routing logic."""

    def __init__(
        self,
        *,
        connector_manager: Optional[ConnectorManager] = None,
        identity_model: Optional[WorkspaceIdentityModel] = None,
    ):
        self.connector_manager = connector_manager or ConnectorManager(
            [
                BrowserSessionConnector(),
                GitCommandConnector(),
                TerminalCommandConnector(),
                IDEExtensionConnector(),
                CodexDesktopConnector(),
                CursorIDEConnector(),
                CopilotIDEConnector(),
                UIAIDEConnector(),
            ]
        )
        self.identity_model = identity_model or WorkspaceIdentityModel(auto_load_config=False)

    def run_suite(self, fixture: dict) -> L1SimulationReport:
        suite = str(fixture.get("suite", "") or "l1-simulation")
        results = tuple(
            self.run_case(suite, raw_case)
            for raw_case in fixture.get("cases", [])
            if isinstance(raw_case, dict)
        )
        return L1SimulationReport(suite=suite, results=results)

    def run_case(self, suite: str, raw_case: dict) -> L1CaseResult:
        started = time.perf_counter()
        case_id = str(raw_case.get("case_id", "") or "unnamed-case")
        goal = _goal_from_dict(raw_case.get("goal", {}))
        states = [_state_from_dict(item) for item in raw_case.get("states", [])]

        matched_state, match_score = self._match_state(goal, states)
        target = self._build_target(goal, matched_state)

        errors: list[str] = []
        expect = raw_case.get("expect", {})
        expected_no_match = isinstance(expect, dict) and expect.get("matched") is False
        connector_id = ""
        if expected_no_match and target.pid == 0:
            connector_id = ""
        else:
            try:
                connector = self.connector_manager.resolve_session_connector(
                    target,
                    preferred=getattr(goal, "connector_hint", ""),
                )
                connector_id = connector.connector_id
            except Exception as exc:
                connector_id = ""
                errors.append(f"connector_resolution: {exc}")

        if expected_no_match and target.pid != 0:
            errors.append(f"matched expected=False actual_pid={target.pid}")
        elif not expected_no_match and target.pid == 0 and not connector_id:
            connector_id = ""
            errors.append("matched expected=True actual_pid=0")

        workspace = self.identity_model.resolve_workspace(
            workspace_path=getattr(goal, "workspace_path", ""),
            resource_url=getattr(goal, "resource_url", ""),
            name_hint=getattr(goal, "window_match", "") or target.project_name,
            title_hint=target.window_title,
        )

        expectation_errors = _compare_expectations(
            expect,
            matched_pid=target.pid,
            connector_id=connector_id,
            workspace_id=workspace.workspace_id,
            matched_window_title=target.window_title,
            match_score=match_score,
        )
        errors.extend(expectation_errors)
        command_plan = _plan_goal_command(goal)
        if command_plan and not command_plan.get("ok"):
            errors.append(f"command_plan error={command_plan.get('error', '')}")
        if isinstance(expect, dict):
            errors.extend(
                _compare_command_plan_expectation(
                    expect.get("command_plan", {}),
                    command_plan,
                )
            )
        session_registry = _case_session_registry(raw_case, states)
        if isinstance(expect, dict):
            errors.extend(
                _compare_session_registry_expectation(
                    expect.get("session_registry", {}),
                    session_registry,
                )
            )
        primary_scenario_plan = _plan_primary_scenario(
            raw_case,
            resolved_connector_id=connector_id,
        )
        if isinstance(expect, dict):
            errors.extend(
                _compare_primary_scenario_plan_expectation(
                    expect.get("primary_scenario_plan", {}),
                    primary_scenario_plan,
                )
            )

        return L1CaseResult(
            suite=suite,
            case_id=case_id,
            passed=not errors,
            errors=tuple(errors),
            matched_pid=target.pid,
            matched_window_title=target.window_title,
            connector_id=connector_id,
            expected_connector_id=str(expect.get("connector_id", "") or "") if isinstance(expect, dict) else "",
            workspace_id=workspace.workspace_id,
            match_score=match_score,
            min_match_score=int(expect.get("min_match_score", 0) or 0) if isinstance(expect, dict) else 0,
            command_plan=command_plan,
            session_registry=session_registry,
            primary_scenario_plan=primary_scenario_plan,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    def _match_state(
        self,
        goal: Any,
        states: Iterable[AIProjectState],
    ) -> tuple[Optional[AIProjectState], int]:
        connector_hint = str(getattr(goal, "connector_hint", "") or "").strip().lower()
        state_list = list(states)
        if connector_hint in _WINDOWLESS_DIRECT_CONNECTORS:
            return None, 1000
        if connector_hint in _DIRECT_CONNECTORS and not state_list:
            return None, 1000

        identity_match, _session, identity_score = self.identity_model.bind_workspace_state_to_goal(
            goal,
            state_list,
        )
        if identity_match is not None:
            return identity_match, identity_score

        match_text = str(getattr(goal, "window_match", "") or "").strip().lower()
        if not match_text:
            return None, -1

        best_state: Optional[AIProjectState] = None
        best_score = -1
        for state in state_list:
            project = (state.project_name or "").strip().lower()
            title = (state.window_title or "").strip().lower()
            if match_text in project or match_text in title:
                return state, 900

            score = int(
                max(
                    difflib.SequenceMatcher(None, match_text, project).ratio(),
                    difflib.SequenceMatcher(None, match_text, title).ratio(),
                )
                * 100
            )
            if score > best_score:
                best_score = score
                best_state = state

        if best_score >= _FUZZY_MATCH_MIN_SCORE:
            return best_state, best_score
        return None, best_score

    @staticmethod
    def _build_target(goal: Any, state: Optional[AIProjectState]) -> ConnectorTarget:
        connector_hint = str(getattr(goal, "connector_hint", "") or "").strip().lower()
        process_name = ""
        window_title = ""
        project_name = str(getattr(goal, "window_match", "") or "")
        pid = 0

        if state is not None:
            pid = state.pid
            process_name = state.process_name
            window_title = state.window_title
            project_name = state.project_name
        elif connector_hint == "terminal":
            process_name = "powershell.exe"
            window_title = str(getattr(goal, "workspace_path", "") or "terminal")
        elif connector_hint == "git":
            process_name = "git.exe"
            window_title = str(getattr(goal, "workspace_path", "") or "git")
        elif connector_hint == "browser":
            process_name = "browser.exe"
            window_title = str(getattr(goal, "resource_url", "") or "browser")
        elif connector_hint == "ide-extension":
            process_name = "code.exe"
            window_title = str(
                getattr(goal, "workspace_path", "")
                or getattr(goal, "ide_bridge_url", "")
                or "ide-extension"
            )

        return ConnectorTarget(
            pid=pid,
            process_name=process_name,
            window_title=window_title,
            project_name=project_name,
            workspace_hint=str(getattr(goal, "window_match", "") or ""),
            workspace_path=str(getattr(goal, "workspace_path", "") or ""),
            resource_url=str(getattr(goal, "resource_url", "") or ""),
            ide_bridge_url=str(getattr(goal, "ide_bridge_url", "") or ""),
        )


def load_simulation_fixture(path: str | Path) -> dict:
    fixture_path = Path(path)
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def format_report(report: L1SimulationReport) -> str:
    lines = [
        f"L1 Simulation: {report.suite}",
        f"Cases: {report.passed_cases}/{report.total_cases} passed ({report.pass_rate:.1%})",
        "",
    ]
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"[{status}] {result.case_id} "
            f"pid={result.matched_pid} connector={result.connector_id or '-'} "
            f"workspace={result.workspace_id or '-'}"
        )
        for error in result.errors:
            lines.append(f"  - {error}")
    return "\n".join(lines).rstrip()


def format_trend_report(report: L1TrendReport) -> str:
    lines = [
        "L1 Trend Report",
        (
            f"Runs: {report.run_count}  Cases: "
            f"{report.passed_cases}/{report.total_cases} passed ({report.pass_rate:.1%})"
        ),
        "",
    ]
    for connector_id, summary in report.connectors().items():
        lines.append(
            f"{connector_id}: {summary['passed']}/{summary['cases']} passed "
            f"min={summary['min_match_score']} avg={summary['avg_match_score']}"
        )
    regressions = report.regressions()
    if regressions:
        lines.append("")
        lines.append("Regressions:")
        for item in regressions:
            lines.append(f"- {item['suite']}::{item['case_id']} [{item['connector_id'] or '-'}]")
    return "\n".join(lines).rstrip()


def summarize_report(report: L1SimulationReport) -> dict:
    scenarios = []
    for result in report.results:
        plan = result.primary_scenario_plan or {}
        if not plan:
            continue
        scenarios.append(
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "scenario_id": str(plan.get("scenario_id", "") or ""),
                "family": str(plan.get("family", "") or ""),
                "route_id": str(plan.get("route_id", "") or ""),
                "connector_id": str(plan.get("connector_id", "") or ""),
                "resolved_connector_id": str(plan.get("resolved_connector_id", "") or ""),
                "proposed_action": str(plan.get("proposed_action", "") or ""),
                "requires_confirmation": bool(plan.get("requires_confirmation", False)),
                "blocked_primitive_count": len(plan.get("blocked_primitives", []) or []),
                "blocked_effect_count": len(
                    plan.get("side_effect_policy", {}).get("blocked_effects", []) or []
                ),
                "blocked_effect_categories": list(
                    plan.get("side_effect_policy", {}).get("blocked_categories", []) or []
                ),
                "confirmation_required_effect_count": len(
                    plan.get("side_effect_policy", {}).get(
                        "confirmation_required_effects",
                        [],
                    )
                    or []
                ),
                "evidence_count": len(plan.get("evidence_ids", []) or []),
            }
        )
    return {
        "mode": "l1-simulation-summary",
        "suite": report.suite,
        "safety_mode": "simulation_only",
        "control_allowed": False,
        "control_attempts": 0,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "pass_rate": round(report.pass_rate, 4),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "route_quality": report.route_quality(),
    }


def _goal_from_dict(data: dict) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=str(data.get("task_id", "") or data.get("task_name", "") or "task"),
        window_match=str(data.get("window_match", "") or ""),
        task_name=str(data.get("task_name", "") or ""),
        goal=str(data.get("goal", "") or ""),
        success_keywords=list(data.get("success_keywords", []) or []),
        failure_keywords=list(data.get("failure_keywords", []) or []),
        retry_command=str(data.get("retry_command", "") or ""),
        connector_hint=str(data.get("connector_hint", "") or "auto"),
        workspace_path=str(data.get("workspace_path", "") or ""),
        resource_url=str(data.get("resource_url", "") or ""),
        ide_bridge_url=str(data.get("ide_bridge_url", "") or ""),
        command_operation=str(data.get("command_operation", "") or ""),
        command_argv=_string_list(data.get("command_argv", [])),
        command_args=_string_list(data.get("command_args", [])),
        command_effects=_string_list(data.get("command_effects", [])),
        command_profile=str(data.get("command_profile", "") or ""),
        command_timeout_sec=float(data.get("command_timeout_sec", 60.0) or 60.0),
        command_audit_log_path=str(data.get("command_audit_log_path", "") or ""),
        command_require_owned_session=bool(data.get("command_require_owned_session", False)),
        command_run_mode=str(data.get("command_run_mode", "") or ""),
        command_process_storage_path=str(data.get("command_process_storage_path", "") or ""),
        matched_pid=int(data.get("matched_pid", 0) or 0),
        matched_window_title=str(data.get("matched_window_title", "") or ""),
        status=SimpleNamespace(value=str(data.get("status", "") or "pending")),
    )


def _string_list(value) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item)]


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


def _compare_expectations(
    expectation: dict,
    *,
    matched_pid: int,
    connector_id: str,
    workspace_id: str,
    matched_window_title: str,
    match_score: int,
) -> list[str]:
    errors: list[str] = []
    if "matched_pid" in expectation and int(expectation["matched_pid"]) != matched_pid:
        errors.append(f"matched_pid expected={expectation['matched_pid']} actual={matched_pid}")
    if "forbidden_matched_pid" in expectation and int(expectation["forbidden_matched_pid"]) == matched_pid:
        errors.append(f"forbidden_matched_pid value={matched_pid}")
    if "connector_id" in expectation and str(expectation["connector_id"]) != connector_id:
        errors.append(f"connector_id expected={expectation['connector_id']} actual={connector_id}")
    if "workspace_id" in expectation and str(expectation["workspace_id"]) != workspace_id:
        errors.append(f"workspace_id expected={expectation['workspace_id']} actual={workspace_id}")
    if "workspace_id_prefix" in expectation and not workspace_id.startswith(
        str(expectation["workspace_id_prefix"])
    ):
        errors.append(
            f"workspace_id_prefix expected={expectation['workspace_id_prefix']} actual={workspace_id}"
        )
    if "matched_window_title" in expectation and str(expectation["matched_window_title"]) != matched_window_title:
        errors.append(
            "matched_window_title "
            f"expected={expectation['matched_window_title']} actual={matched_window_title}"
        )
    if "min_match_score" in expectation and match_score < int(expectation["min_match_score"]):
        errors.append(f"min_match_score expected>={expectation['min_match_score']} actual={match_score}")
    return errors


def _plan_goal_command(goal: object) -> dict:
    from openwukong.supervisor.command_execution import (
        SupervisorCommandExecutor,
        goal_has_structured_command,
    )

    if not goal_has_structured_command(goal):
        return {}
    return SupervisorCommandExecutor().plan_goal(goal).to_dict()


def _case_session_registry(raw_case: dict, states: list[AIProjectState]) -> dict:
    snapshots = _process_broker_snapshots(raw_case)
    if not states and not snapshots:
        return {}
    return build_session_registry_snapshot(
        states,
        process_broker_snapshots=snapshots,
    ).to_dict()


def _process_broker_snapshots(raw_case: dict) -> tuple[dict, ...]:
    raw = raw_case.get("process_broker_snapshots", raw_case.get("broker_snapshots", ()))
    if isinstance(raw, dict):
        raw = (raw,)
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(item for item in raw if isinstance(item, dict))


def _plan_primary_scenario(
    raw_case: dict,
    *,
    resolved_connector_id: str,
) -> dict:
    scenario = raw_case.get("primary_scenario", {})
    if not isinstance(scenario, dict) or not scenario:
        return {}
    scenario_id = str(scenario.get("scenario_id", "") or "").strip()
    family = str(scenario.get("family", "") or "").strip()
    if not family and scenario_id:
        family = scenario_id.split(".", 1)[0]
    spec = dict(_PRIMARY_SCENARIO_SPECS.get(scenario_id, {}))
    route_id = str(spec.get("route_id", "simulation-draft-route"))
    connector_id = str(spec.get("connector_id", resolved_connector_id or family or "simulation"))
    proposed_action = str(spec.get("proposed_action", "draft_primary_scenario_action"))
    intent = scenario.get("intent", {})
    if not isinstance(intent, dict):
        intent = {}
    recorded_context = scenario.get("recorded_context", {})
    if not isinstance(recorded_context, dict):
        recorded_context = {}
    evidence_ids = tuple(
        str(item)
        for item in recorded_context.get("evidence_ids", ()) or ()
        if str(item).strip()
    )
    allowed_primitives = tuple(str(item) for item in spec.get("allowed_primitives", ()) or ())
    blocked_primitives = tuple(str(item) for item in spec.get("blocked_primitives", ()) or ())
    side_effect_policy = build_side_effect_policy(
        allowed_effect_ids=spec.get("allowed_effects", ()),
        blocked_effect_ids=spec.get("blocked_effects", ()),
        confirmation_required_effect_ids=spec.get("confirmation_required_effects", ()),
    )
    draft_action = {
        "action_id": f"{scenario_id or 'primary-scenario'}:draft",
        "status": "draft_only",
        "scenario_id": scenario_id,
        "kind": proposed_action,
        "route_id": route_id,
        "connector_id": connector_id,
        "intent": dict(intent),
    }
    return {
        "mode": "primary-scenario-plan",
        "safety_mode": "simulation_only",
        "control_allowed": False,
        "control_attempts": 0,
        "scenario_id": scenario_id,
        "family": family,
        "route_id": route_id,
        "connector_id": connector_id,
        "resolved_connector_id": str(resolved_connector_id or ""),
        "proposed_action": proposed_action,
        "requires_confirmation": bool(spec.get("requires_confirmation", True)),
        "allowed_primitives": list(allowed_primitives),
        "blocked_primitives": list(blocked_primitives),
        "evidence_ids": list(evidence_ids),
        "recorded_context": dict(recorded_context),
        "draft_action": draft_action,
        "side_effect_policy": side_effect_policy,
        "risks": list(spec.get("risks", ()) or ()),
    }


def _compare_command_plan_expectation(
    expectation: object,
    command_plan: dict,
) -> list[str]:
    if not isinstance(expectation, dict) or not expectation:
        return []
    errors: list[str] = []
    if not command_plan:
        return ["command_plan expected=True actual=missing"]

    if "ok" in expectation and bool(expectation["ok"]) != bool(command_plan.get("ok")):
        errors.append(f"command_plan.ok expected={expectation['ok']} actual={command_plan.get('ok')}")
    for key in ("operation", "profile_id"):
        if key in expectation and str(expectation[key]) != str(command_plan.get(key, "")):
            errors.append(f"command_plan.{key} expected={expectation[key]} actual={command_plan.get(key, '')}")
    if "effects" in expectation and list(expectation["effects"]) != list(command_plan.get("effects", [])):
        errors.append(
            f"command_plan.effects expected={expectation['effects']} actual={command_plan.get('effects', [])}"
        )
    if "argv" in expectation and list(expectation["argv"]) != list(command_plan.get("argv", [])):
        errors.append(f"command_plan.argv expected={expectation['argv']} actual={command_plan.get('argv', [])}")
    if "argv_prefix" in expectation:
        prefix = list(expectation["argv_prefix"])
        actual = list(command_plan.get("argv", []))
        if actual[: len(prefix)] != prefix:
            errors.append(f"command_plan.argv_prefix expected={prefix} actual={actual[:len(prefix)]}")
    return errors


def _compare_session_registry_expectation(
    expectation: object,
    session_registry: dict,
) -> list[str]:
    if not isinstance(expectation, dict) or not expectation:
        return []
    errors: list[str] = []
    if not session_registry:
        return ["session_registry expected=True actual=missing"]

    for key in (
        "session_count",
        "app_family_counts",
        "preferred_route_counts",
        "ownership_counts",
    ):
        if key in expectation and expectation[key] != session_registry.get(key):
            errors.append(
                f"session_registry.{key} expected={expectation[key]} actual={session_registry.get(key)}"
            )

    sessions = tuple(
        session
        for session in session_registry.get("sessions", ()) or ()
        if isinstance(session, dict)
    )
    if "contains_session_id" in expectation:
        expected = str(expectation["contains_session_id"])
        actual = [str(session.get("session_id", "")) for session in sessions]
        if expected not in actual:
            errors.append(f"session_registry.contains_session_id expected={expected} actual={actual}")
    if "contains_capability_id" in expectation:
        expected = str(expectation["contains_capability_id"])
        actual = [
            capability_id
            for session in sessions
            for capability_id in session.get("capability_ids", []) or []
        ]
        if expected not in actual:
            errors.append(f"session_registry.contains_capability_id expected={expected} actual={actual}")
    if "contains_action_id" in expectation:
        expected = str(expectation["contains_action_id"])
        actual = [
            action_id
            for session in sessions
            for action_id in session.get("action_ids", []) or []
        ]
        if expected not in actual:
            errors.append(f"session_registry.contains_action_id expected={expected} actual={actual}")
    return errors


def _compare_primary_scenario_plan_expectation(
    expectation: object,
    primary_scenario_plan: dict,
) -> list[str]:
    if not isinstance(expectation, dict) or not expectation:
        return []
    errors: list[str] = []
    if not primary_scenario_plan:
        return ["primary_scenario_plan expected=True actual=missing"]

    for key in (
        "scenario_id",
        "route_id",
        "connector_id",
        "proposed_action",
        "requires_confirmation",
        "safety_mode",
        "control_attempts",
    ):
        if key in expectation and expectation[key] != primary_scenario_plan.get(key):
            errors.append(
                f"primary_scenario_plan.{key} "
                f"expected={expectation[key]} actual={primary_scenario_plan.get(key)}"
            )

    if "contains_evidence_id" in expectation:
        expected = str(expectation["contains_evidence_id"])
        actual = list(primary_scenario_plan.get("evidence_ids", []) or [])
        if expected not in actual:
            errors.append(f"primary_scenario_plan.contains_evidence_id expected={expected} actual={actual}")

    if "contains_blocked_primitive" in expectation:
        expected = str(expectation["contains_blocked_primitive"])
        actual = list(primary_scenario_plan.get("blocked_primitives", []) or [])
        if expected not in actual:
            errors.append(
                f"primary_scenario_plan.contains_blocked_primitive expected={expected} actual={actual}"
            )

    if "contains_allowed_primitive" in expectation:
        expected = str(expectation["contains_allowed_primitive"])
        actual = list(primary_scenario_plan.get("allowed_primitives", []) or [])
        if expected not in actual:
            errors.append(
                f"primary_scenario_plan.contains_allowed_primitive expected={expected} actual={actual}"
            )

    if "contains_blocked_effect_category" in expectation:
        expected = str(expectation["contains_blocked_effect_category"])
        actual = list(
            primary_scenario_plan.get("side_effect_policy", {}).get("blocked_categories", []) or []
        )
        if expected not in actual:
            errors.append(
                "primary_scenario_plan.contains_blocked_effect_category "
                f"expected={expected} actual={actual}"
            )

    if "contains_blocked_effect_id" in expectation:
        expected = str(expectation["contains_blocked_effect_id"])
        actual = [
            str(effect.get("effect_id", ""))
            for effect in primary_scenario_plan.get("side_effect_policy", {}).get(
                "blocked_effects",
                [],
            )
            or []
            if isinstance(effect, dict)
        ]
        if expected not in actual:
            errors.append(f"primary_scenario_plan.contains_blocked_effect_id expected={expected} actual={actual}")

    return errors


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run L1 offline simulation fixtures.")
    parser.add_argument("fixtures", nargs="+", help="Path(s) to L1 simulation fixture JSON file(s).")
    parser.add_argument("--trend", action="store_true", help="Aggregate multiple fixture runs into a trend report.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--summary-json", action="store_true", help="Print a compact scheduler-friendly JSON summary.")
    args = parser.parse_args(argv)

    harness = L1SimulationHarness()
    reports = [
        harness.run_suite(load_simulation_fixture(fixture_path))
        for fixture_path in args.fixtures
    ]

    if args.trend:
        trend_report = build_trend_report(reports)
        if args.json:
            print(json.dumps(trend_report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_trend_report(trend_report))
        return 0 if trend_report.failed_cases == 0 else 1

    if len(reports) != 1:
        parser.error("multiple fixtures require --trend")

    report = reports[0]
    if args.summary_json:
        print(json.dumps(summarize_report(report), ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
