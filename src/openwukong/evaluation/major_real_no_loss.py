# -*- coding: utf-8 -*-
"""Unified real no-loss acceptance report for the main desktop scenarios."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.evaluation.agent_app_real_no_loss import (
    run_agent_app_real_no_loss,
)
from openwukong.evaluation.agent_cli_real_no_loss import (
    run_agent_cli_real_no_loss,
)
from openwukong.evaluation.primary_real_no_loss import (
    _resolve_installed_browser_executable,
    run_primary_real_no_loss,
)
from openwukong.evaluation.simulation import load_simulation_fixture


DEFAULT_MAJOR_FIXTURE = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
DEFAULT_AGENT_APPS = ("codex app", "claude desktop", "cursor")
DEFAULT_CLI_AGENTS = ("codex", "claude")


PrimaryRunner = Callable[..., object]
AgentAppRunner = Callable[..., object]
AgentCliRunner = Callable[..., object]


@dataclasses.dataclass(frozen=True)
class MajorRequirement:
    requirement_id: str
    surface: str
    capability: str
    status: str
    source_runner: str
    evidence: dict = dataclasses.field(default_factory=dict)
    blocking_reason: str = ""

    @property
    def satisfied(self) -> bool:
        return self.status == "verified"

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "surface": self.surface,
            "capability": self.capability,
            "status": self.status,
            "satisfied": self.satisfied,
            "source_runner": self.source_runner,
            "blocking_reason": self.blocking_reason,
            "evidence": dict(self.evidence),
        }


@dataclasses.dataclass(frozen=True)
class MajorScenarioRealNoLossReport:
    output_root: str
    artifact_path: str
    primary_report: dict
    agent_app_report: dict
    agent_cli_report: dict
    requirements: tuple[MajorRequirement, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "major-scenario-real-no-loss"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return _sum_counter(
            self.primary_report,
            self.agent_app_report,
            self.agent_cli_report,
            key="control_attempts",
        )

    @property
    def external_communication_attempts(self) -> int:
        return _counter(self.primary_report, "external_communication_attempts")

    @property
    def window_input_attempts(self) -> int:
        return _sum_counter(
            self.primary_report,
            self.agent_app_report,
            self.agent_cli_report,
            key="window_input_attempts",
        )

    @property
    def bridge_send_attempts(self) -> int:
        return _counter(self.agent_app_report, "bridge_send_attempts")

    @property
    def agent_command_attempts(self) -> int:
        return _counter(self.agent_app_report, "agent_command_attempts") + _counter(
            self.agent_cli_report,
            "agent_command_attempts",
        )

    @property
    def owned_app_launch_attempts(self) -> int:
        return _counter(self.primary_report, "owned_app_launch_attempts")

    @property
    def background_screenshot_count(self) -> int:
        return _counter(self.primary_report, "background_screenshot_count") + _counter(
            self.agent_app_report,
            "background_screenshot_count",
        )

    @property
    def background_screenshot_success_count(self) -> int:
        return _counter(
            self.primary_report,
            "background_screenshot_success_count",
        ) + _counter(
            self.agent_app_report,
            "background_screenshot_success_count",
        )

    @property
    def background_screenshot_focus_stable(self) -> bool:
        return bool(
            self.primary_report.get("background_screenshot_focus_stable", True)
        ) and bool(self.agent_app_report.get("background_screenshot_focus_stable", True))

    @property
    def failed_runner_count(self) -> int:
        return sum(
            1
            for report in (
                self.primary_report,
                self.agent_app_report,
                self.agent_cli_report,
            )
            if _counter(report, "failed_cases") > 0
        )

    @property
    def unmet_requirements(self) -> tuple[str, ...]:
        return tuple(
            requirement.requirement_id
            for requirement in self.requirements
            if not requirement.satisfied
        )

    @property
    def goal_complete(self) -> bool:
        return bool(
            not self.unmet_requirements
            and self.failed_runner_count == 0
            and self.control_attempts == 0
            and self.window_input_attempts == 0
            and self.background_screenshot_focus_stable
        )

    @property
    def safe_run_ok(self) -> bool:
        return bool(
            self.failed_runner_count == 0
            and self.control_attempts == 0
            and self.window_input_attempts == 0
            and self.background_screenshot_focus_stable
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "external_communication_attempts": self.external_communication_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "owned_app_launch_attempts": self.owned_app_launch_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "failed_runner_count": self.failed_runner_count,
            "goal_complete": self.goal_complete,
            "safe_run_ok": self.safe_run_ok,
            "unmet_requirements": list(self.unmet_requirements),
            "requirements": [
                requirement.to_dict() for requirement in self.requirements
            ],
            "output_root": self.output_root,
            "artifact_path": self.artifact_path,
            "subreports": {
                "primary": dict(self.primary_report),
                "agent_app": dict(self.agent_app_report),
                "agent_cli": dict(self.agent_cli_report),
            },
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_major_scenario_real_no_loss(
    *,
    fixture: dict | None = None,
    fixture_path: str | Path = DEFAULT_MAJOR_FIXTURE,
    output_root: str | Path = "",
    allow_owned_browser_helper_launch: bool = False,
    owned_browser_debug_port: int = 9475,
    owned_browser_executable: str = "chrome.exe",
    owned_browser_url: str = "data:text/html,<title>OpenWukong Major No Loss</title><body>OpenWukong Major No Loss</body>",
    background_screenshot_dir: str | Path = "",
    agent_apps: Iterable[str] = DEFAULT_AGENT_APPS,
    cli_agents: Iterable[str] = DEFAULT_CLI_AGENTS,
    project_name: str = "openwukong",
    task_name: str = "major-real-no-loss",
    allow_uia_semantic_action: bool = False,
    uia_message: str = "OPENWUKONG_UIA_SEMANTIC_ACTION_REAL_NO_LOSS",
    uia_required_markers: tuple[str, ...] = (),
    uia_forbidden_markers: tuple[str, ...] = (),
    allow_app_bridge_send: bool = False,
    app_bridge_message: str = "OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
    app_bridge_required_markers: tuple[str, ...] = (),
    app_bridge_forbidden_markers: tuple[str, ...] = (),
    ide_bridge_urls: Iterable[str] = (),
    workspace_path: str = "",
    allow_agent_cli_execution: bool = False,
    agent_cli_timeout_sec: float = 90.0,
    primary_runner: PrimaryRunner | None = None,
    agent_app_runner: AgentAppRunner | None = None,
    agent_cli_runner: AgentCliRunner | None = None,
) -> MajorScenarioRealNoLossReport:
    started = time.perf_counter()
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    loaded_fixture = fixture if fixture is not None else load_simulation_fixture(fixture_path)

    primary = _report_to_dict(
        (primary_runner or run_primary_real_no_loss)(
            loaded_fixture,
            output_root=root / "primary",
            allow_owned_browser_helper_launch=allow_owned_browser_helper_launch,
            owned_browser_debug_port=owned_browser_debug_port,
            owned_browser_executable=owned_browser_executable,
            owned_browser_url=owned_browser_url,
            browser_executable_resolver=_resolve_installed_browser_executable,
            background_screenshot_dir=(
                background_screenshot_dir
                or root / "background-screenshots" / "primary"
            ),
        )
    )
    app = _report_to_dict(
        (agent_app_runner or run_agent_app_real_no_loss)(
            agents=tuple(agent_apps),
            project_name=project_name,
            task_name=task_name,
            output_root=root / "agent-app",
            screenshot_dir=root / "background-screenshots" / "agent-app",
            allow_uia_semantic_action=allow_uia_semantic_action,
            uia_message=uia_message,
            uia_required_markers=tuple(uia_required_markers or ()),
            uia_forbidden_markers=tuple(uia_forbidden_markers or ()),
            allow_app_bridge_send=allow_app_bridge_send,
            bridge_message=app_bridge_message,
            required_markers=tuple(app_bridge_required_markers or ()),
            forbidden_markers=tuple(app_bridge_forbidden_markers or ()),
            ide_bridge_urls=tuple(ide_bridge_urls or ()),
            workspace_path=workspace_path,
        )
    )
    cli = _report_to_dict(
        (agent_cli_runner or run_agent_cli_real_no_loss)(
            agents=tuple(cli_agents),
            output_root=root / "agent-cli",
            allow_cli_execution=allow_agent_cli_execution,
            timeout_sec=agent_cli_timeout_sec,
        )
    )

    report = MajorScenarioRealNoLossReport(
        output_root=str(root),
        artifact_path="",
        primary_report=primary,
        agent_app_report=app,
        agent_cli_report=cli,
        requirements=_build_requirements(primary, app, cli),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    return _write_report_artifact(root, report)


def format_major_scenario_real_no_loss_report(
    report: MajorScenarioRealNoLossReport,
) -> str:
    lines = [
        "Major scenario real no-loss",
        (
            f"Safe run: {str(report.safe_run_ok).lower()}  "
            f"Goal complete: {str(report.goal_complete).lower()}  "
            f"Unmet: {len(report.unmet_requirements)}"
        ),
        (
            f"Control attempts: {report.control_attempts}  "
            f"Window input: {report.window_input_attempts}  "
            f"Agent commands: {report.agent_command_attempts}"
        ),
        (
            f"Screenshots: {report.background_screenshot_success_count}/"
            f"{report.background_screenshot_count}  "
            f"Focus stable: {str(report.background_screenshot_focus_stable).lower()}"
        ),
    ]
    for requirement in report.requirements:
        lines.append(
            f"- {requirement.requirement_id}: {requirement.status}"
            + (
                f" ({requirement.blocking_reason})"
                if requirement.blocking_reason
                else ""
            )
        )
    return "\n".join(lines).rstrip()


def _build_requirements(primary: dict, app: dict, cli: dict) -> tuple[MajorRequirement, ...]:
    primary_cases = _cases_by_key(primary, "scenario_id")
    app_cases = _cases_by_key(app, "agent")
    cli_cases = _cases_by_key(cli, "agent")
    return (
        _primary_requirement(
            "wechat_background_observation",
            "wechat",
            "background_observation",
            primary_cases.get("wechat.chat.draft_reply", {}),
        ),
        _wechat_background_send_requirement(
            primary_cases.get("wechat.chat.draft_reply", {})
        ),
        _primary_requirement(
            "word_background_document",
            "word",
            "hidden_com_create_save_readback",
            primary_cases.get("word.document.create_background", {}),
        ),
        _primary_requirement(
            "browser_background_research",
            "browser",
            "owned_cdp_read_page",
            primary_cases.get("browser.research.collect_sources", {}),
        ),
        _primary_requirement(
            "file_background_search",
            "files",
            "owned_filesystem_search",
            primary_cases.get("files.search.find_candidate", {}),
        ),
        _cli_requirement(
            "codex_cli_background_task",
            "codex",
            cli_cases.get("codex", {}),
        ),
        _cli_requirement(
            "claude_cli_background_task",
            "claude",
            cli_cases.get("claude", {}),
        ),
        _app_requirement(
            "codex_app_background_chat",
            "codex app",
            app_cases.get("codex app", {}),
        ),
        _app_requirement(
            "claude_desktop_background_chat",
            "claude desktop",
            app_cases.get("claude desktop", {}),
        ),
        _app_requirement(
            "cursor_background_chat",
            "cursor",
            app_cases.get("cursor", {}),
        ),
    )


def _primary_requirement(
    requirement_id: str,
    surface: str,
    capability: str,
    case: dict,
) -> MajorRequirement:
    if _case_verified(case):
        status = "verified"
        reason = ""
    elif not case:
        status = "unavailable"
        reason = "case_missing"
    elif str(case.get("status", "") or "").startswith("failed"):
        status = "failed"
        reason = str(case.get("status", "") or "failed")
    else:
        status = "unavailable"
        reason = str(case.get("status", "") or "not_real_verified")
    return MajorRequirement(
        requirement_id=requirement_id,
        surface=surface,
        capability=capability,
        status=status,
        source_runner="primary_real_no_loss",
        blocking_reason=reason,
        evidence=_compact_case_evidence(case),
    )


def _wechat_background_send_requirement(case: dict) -> MajorRequirement:
    details = _details(case)
    dry_run = _details(details.get("uia_semantic_action_dry_run", {}))
    if bool(details.get("background_send_verified", False)) or bool(
        case.get("background_send_verified", False)
    ):
        status = "verified"
        reason = ""
    elif _case_verified(case):
        status = "gated"
        reason = str(
            dry_run.get("decision", "")
            or "background_send_not_verified"
        )
    elif not case:
        status = "unavailable"
        reason = "case_missing"
    else:
        status = "unavailable"
        reason = str(case.get("status", "") or "wechat_not_observable")
    return MajorRequirement(
        requirement_id="wechat_background_send",
        surface="wechat",
        capability="background_semantic_send",
        status=status,
        source_runner="primary_real_no_loss",
        blocking_reason=reason,
        evidence={
            **_compact_case_evidence(case),
            "uia_semantic_action_ready": bool(
                details.get("uia_semantic_action_ready", False)
            ),
            "dry_run_decision": str(dry_run.get("decision", "") or ""),
        },
    )


def _cli_requirement(requirement_id: str, surface: str, case: dict) -> MajorRequirement:
    raw_status = str(case.get("status", "") or "").strip()
    if raw_status == "verified" and bool(case.get("real_verified", False)):
        status = "verified"
        reason = ""
    elif raw_status == "cli_auth_required":
        status = "auth_required"
        reason = "local_cli_not_logged_in"
    elif raw_status in {"cli_access_denied", "background_cli_unavailable"}:
        status = "gated"
        reason = raw_status
    elif not case:
        status = "unavailable"
        reason = "case_missing"
    else:
        status = "failed" if raw_status.startswith("failed") else "unavailable"
        reason = raw_status or "not_verified"
    return MajorRequirement(
        requirement_id=requirement_id,
        surface=surface,
        capability="background_cli_task",
        status=status,
        source_runner="agent_cli_real_no_loss",
        blocking_reason=reason,
        evidence=_compact_case_evidence(case),
    )


def _app_requirement(requirement_id: str, surface: str, case: dict) -> MajorRequirement:
    raw_status = str(case.get("status", "") or "").strip()
    if bool(case.get("app_bridge_send_verified", False)) or bool(
        case.get("uia_semantic_action_send_verified", False)
    ) or raw_status in {
        "app_bridge_send_accepted",
        "uia_semantic_action_send_accepted",
        "message_submitted_accepted",
    }:
        status = "verified"
        reason = ""
    elif raw_status.startswith("gated_") or bool(case.get("native_ready", False)):
        status = "gated"
        reason = raw_status or "native_ready_send_not_verified"
    elif raw_status == "unavailable" or not case:
        status = "unavailable"
        reason = raw_status or "case_missing"
    else:
        status = "failed" if raw_status.startswith("failed") else "unavailable"
        reason = raw_status or "not_verified"
    return MajorRequirement(
        requirement_id=requirement_id,
        surface=surface,
        capability="background_app_chat",
        status=status,
        source_runner="agent_app_real_no_loss",
        blocking_reason=reason,
        evidence=_compact_case_evidence(case),
    )


def _cases_by_key(report: dict, key: str) -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for item in report.get("cases", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get(key, "") or "").strip().lower()
        if name:
            cases[name] = dict(item)
    return cases


def _case_verified(case: dict) -> bool:
    return bool(case.get("real_verified", False)) and str(
        case.get("status", "") or ""
    ) == "verified"


def _compact_case_evidence(case: dict) -> dict:
    if not case:
        return {}
    evidence = {
        "status": str(case.get("status", "") or ""),
        "real_verified": bool(case.get("real_verified", False)),
    }
    for key in (
        "agent",
        "scenario_id",
        "native_ready",
        "app_bridge_send_verified",
        "uia_semantic_action_send_verified",
        "foreground_focus_stable",
        "background_screenshot_focus_stable",
        "artifact_path",
    ):
        if key in case:
            evidence[key] = case[key]
    details = _details(case.get("details", {}))
    if details:
        for key in (
            "background_screenshot_focus_stable",
            "uia_semantic_action_ready",
            "decision",
        ):
            if key in details:
                evidence[key] = details[key]
    return evidence


def _details(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _write_report_artifact(
    output_root: Path,
    report: MajorScenarioRealNoLossReport,
) -> MajorScenarioRealNoLossReport:
    artifact_path = output_root / "major-real-no-loss-report.json"
    with_path = dataclasses.replace(report, artifact_path=str(artifact_path))
    artifact_path.write_text(
        json.dumps(with_path.to_dict(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return with_path


def _report_to_dict(report: object) -> dict:
    if isinstance(report, dict):
        return dict(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {"mode": "unknown", "failed_cases": 1, "cases": []}


def _sum_counter(*reports: dict, key: str) -> int:
    return sum(_counter(report, key) for report in reports)


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


def _resolve_output_root(output_root: str | Path) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve()
    return (Path("logs") / "runtime" / "major-real-no-loss").resolve()


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2)


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the unified real no-loss report for major desktop scenarios."
    )
    parser.add_argument("--fixture", default=str(DEFAULT_MAJOR_FIXTURE))
    parser.add_argument("--output-root", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-owned-browser-helper-launch", action="store_true")
    parser.add_argument("--owned-browser-debug-port", type=int, default=9475)
    parser.add_argument("--owned-browser-executable", default="chrome.exe")
    parser.add_argument(
        "--owned-browser-url",
        default="data:text/html,<title>OpenWukong Major No Loss</title><body>OpenWukong Major No Loss</body>",
    )
    parser.add_argument("--background-screenshot-dir", default="")
    parser.add_argument("--agent-app", action="append", default=None)
    parser.add_argument("--cli-agent", action="append", default=None)
    parser.add_argument("--project-name", default="openwukong")
    parser.add_argument("--task-name", default="major-real-no-loss")
    parser.add_argument(
        "--allow-uia-semantic-action",
        action="store_true",
        help="Allow UIA ValuePattern/InvokePattern semantic sends for agent app surfaces when ready.",
    )
    parser.add_argument(
        "--uia-message",
        default="OPENWUKONG_UIA_SEMANTIC_ACTION_REAL_NO_LOSS",
        help="Message used for optional app UIA semantic sends.",
    )
    parser.add_argument(
        "--uia-acceptance-marker",
        action="append",
        default=[],
        help="Required UIA semantic action readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--uia-forbid-marker",
        action="append",
        default=[],
        help="Forbidden UIA semantic action readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--allow-app-bridge-send",
        action="store_true",
        help="Allow native app bridge sends for agent app surfaces when their dry-run contracts are ready.",
    )
    parser.add_argument(
        "--app-bridge-message",
        default="OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
        help="Message used for optional agent app bridge sends.",
    )
    parser.add_argument(
        "--app-acceptance-marker",
        action="append",
        default=[],
        help="Required app bridge readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--app-forbid-marker",
        action="append",
        default=[],
        help="Forbidden app bridge readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--ide-bridge-url",
        action="append",
        default=[],
        help="Explicit IDE extension/native bridge URL forwarded to agent app no-loss probes.",
    )
    parser.add_argument(
        "--workspace-path",
        default="",
        help="Optional workspace path included in IDE bridge capability probes.",
    )
    parser.add_argument("--allow-agent-cli-execution", action="store_true")
    parser.add_argument("--agent-cli-timeout-sec", type=float, default=90.0)
    args = parser.parse_args(argv)

    report = run_major_scenario_real_no_loss(
        fixture_path=args.fixture,
        output_root=args.output_root,
        allow_owned_browser_helper_launch=args.allow_owned_browser_helper_launch,
        owned_browser_debug_port=args.owned_browser_debug_port,
        owned_browser_executable=args.owned_browser_executable,
        owned_browser_url=args.owned_browser_url,
        background_screenshot_dir=args.background_screenshot_dir,
        agent_apps=tuple(args.agent_app or DEFAULT_AGENT_APPS),
        cli_agents=tuple(args.cli_agent or DEFAULT_CLI_AGENTS),
        project_name=args.project_name,
        task_name=args.task_name,
        allow_uia_semantic_action=args.allow_uia_semantic_action,
        uia_message=args.uia_message,
        uia_required_markers=tuple(args.uia_acceptance_marker or ()),
        uia_forbidden_markers=tuple(args.uia_forbid_marker or ()),
        allow_app_bridge_send=args.allow_app_bridge_send,
        app_bridge_message=args.app_bridge_message,
        app_bridge_required_markers=tuple(args.app_acceptance_marker or ()),
        app_bridge_forbidden_markers=tuple(args.app_forbid_marker or ()),
        ide_bridge_urls=tuple(args.ide_bridge_url or ()),
        workspace_path=args.workspace_path,
        allow_agent_cli_execution=args.allow_agent_cli_execution,
        agent_cli_timeout_sec=args.agent_cli_timeout_sec,
    )
    payload = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_json_dumps(payload), encoding="utf-8")
    if args.json:
        _write_stdout(_json_dumps(payload))
    else:
        _write_stdout(format_major_scenario_real_no_loss_report(report))
    return 0 if report.safe_run_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
