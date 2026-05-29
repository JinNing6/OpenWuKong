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

from openwukong.control.session_readiness_plan import (
    SessionReadinessPlanOptions,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.evaluation.agent_app_real_no_loss import (
    run_agent_app_real_no_loss,
)
from openwukong.evaluation.agent_cli_real_no_loss import (
    run_agent_cli_real_no_loss,
)
from openwukong.evaluation.ide_bridge_capture import (
    capture_ide_bridge_capabilities,
)
from openwukong.evaluation.ide_bridge_contract_probe import (
    build_bridge_settings_from_probe_report,
    probe_ide_command_contracts,
    select_probe_command_ids,
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
OwnedIdeBridgeHelperRunner = Callable[..., object]


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
    owned_ide_bridge_helper_report: dict
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
    def owned_ide_bridge_launch_attempts(self) -> int:
        return _counter(self.owned_ide_bridge_helper_report, "launch_attempts")

    @property
    def owned_ide_bridge_stop_attempts(self) -> int:
        return _counter(self.owned_ide_bridge_helper_report, "stop_attempts")

    @property
    def isolated_ide_command_probe_attempts(self) -> int:
        return _counter(
            self.owned_ide_bridge_helper_report,
            "isolated_command_probe_attempts",
        )

    @property
    def owned_ide_bridge_cleanup_ok(self) -> bool:
        if not self.owned_ide_bridge_helper_report:
            return True
        if not bool(self.owned_ide_bridge_helper_report.get("enabled", False)):
            return True
        return bool(self.owned_ide_bridge_helper_report.get("cleanup_ok", False))

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
    def automation_focus_risk_attempts(self) -> int:
        return (
            self.control_attempts
            + self.window_input_attempts
            + self.external_communication_attempts
            + self.owned_ide_bridge_launch_attempts
            + self.bridge_send_attempts
            + self.agent_command_attempts
            + self.owned_app_launch_attempts
        )

    @property
    def automation_focus_safe(self) -> bool:
        if self.background_screenshot_focus_stable:
            return True
        return self.automation_focus_risk_attempts == 0

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
        ) + (0 if self.owned_ide_bridge_cleanup_ok else 1)

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
            and self.automation_focus_safe
            and self.owned_ide_bridge_cleanup_ok
        )

    @property
    def safe_run_ok(self) -> bool:
        return bool(
            self.failed_runner_count == 0
            and self.control_attempts == 0
            and self.window_input_attempts == 0
            and self.automation_focus_safe
            and self.owned_ide_bridge_cleanup_ok
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "external_communication_attempts": self.external_communication_attempts,
            "window_input_attempts": self.window_input_attempts,
            "owned_ide_bridge_launch_attempts": self.owned_ide_bridge_launch_attempts,
            "owned_ide_bridge_stop_attempts": self.owned_ide_bridge_stop_attempts,
            "owned_ide_bridge_cleanup_ok": self.owned_ide_bridge_cleanup_ok,
            "isolated_ide_command_probe_attempts": self.isolated_ide_command_probe_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "owned_app_launch_attempts": self.owned_app_launch_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "automation_focus_risk_attempts": self.automation_focus_risk_attempts,
            "automation_focus_safe": self.automation_focus_safe,
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
                "owned_ide_bridge_helper": dict(self.owned_ide_bridge_helper_report),
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
    allow_wechat_uia_semantic_send: bool = False,
    wechat_uia_message: str = "OPENWUKONG_WECHAT_UIA_SEMANTIC_SEND",
    wechat_uia_required_markers: tuple[str, ...] = (),
    wechat_uia_forbidden_markers: tuple[str, ...] = (),
    wechat_native_bridge_urls: Iterable[str] = (),
    allow_wechat_native_bridge_send: bool = False,
    wechat_native_bridge_message: str = "OPENWUKONG_WECHAT_NATIVE_BRIDGE_SEND",
    wechat_native_bridge_required_markers: tuple[str, ...] = (),
    wechat_native_bridge_forbidden_markers: tuple[str, ...] = (),
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
    debugger_urls: Iterable[str] = (),
    ide_bridge_urls: Iterable[str] = (),
    agent_native_bridge_urls: Iterable[str] = (),
    agent_native_bridge_registry_paths: Iterable[str | Path] = (),
    workspace_path: str = "",
    allow_owned_ide_bridge_helper_launch: bool = False,
    owned_ide_executable: str = "cursor.exe",
    owned_ide_bridge_port: int = 8791,
    owned_ide_user_data_dir: str = "",
    owned_ide_extensions_dir: str = "",
    owned_ide_extension_dir: str = "extensions/openwukong-vscode",
    owned_ide_workspace_root: str = "",
    owned_ide_chat_adapter_id: str = "cursor",
    owned_ide_capability_timeout_sec: float = 30.0,
    allow_agent_cli_execution: bool = False,
    agent_cli_timeout_sec: float = 90.0,
    primary_runner: PrimaryRunner | None = None,
    owned_ide_bridge_helper_runner: OwnedIdeBridgeHelperRunner | None = None,
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
            allow_wechat_uia_semantic_send=allow_wechat_uia_semantic_send,
            wechat_uia_message=wechat_uia_message,
            wechat_uia_required_markers=tuple(wechat_uia_required_markers or ()),
            wechat_uia_forbidden_markers=tuple(wechat_uia_forbidden_markers or ()),
            wechat_native_bridge_urls=tuple(wechat_native_bridge_urls or ()),
            allow_wechat_native_bridge_send=allow_wechat_native_bridge_send,
            wechat_native_bridge_message=wechat_native_bridge_message,
            wechat_native_bridge_required_markers=tuple(
                wechat_native_bridge_required_markers or ()
            ),
            wechat_native_bridge_forbidden_markers=tuple(
                wechat_native_bridge_forbidden_markers or ()
            ),
        )
    )
    helper = _disabled_owned_ide_bridge_helper_report()
    app: dict = {}
    cli: dict = {}
    try:
        if allow_owned_ide_bridge_helper_launch:
            helper = _report_to_dict(
                (owned_ide_bridge_helper_runner or prepare_owned_ide_bridge_helper)(
                    output_root=root / "owned-ide-bridge",
                    project_name=project_name,
                    task_name=task_name,
                    ide_executable=owned_ide_executable,
                    ide_bridge_port=owned_ide_bridge_port,
                    ide_user_data_dir=owned_ide_user_data_dir,
                    ide_extensions_dir=owned_ide_extensions_dir,
                    ide_extension_dir=owned_ide_extension_dir,
                    workspace_root=owned_ide_workspace_root,
                    adapter_id=owned_ide_chat_adapter_id,
                    capability_timeout_sec=owned_ide_capability_timeout_sec,
                )
            )
        effective_ide_bridge_urls = _effective_ide_bridge_urls(
            ide_bridge_urls,
            helper,
        )
        effective_workspace_path = workspace_path or str(
            helper.get("workspace_path", "") or ""
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
                debugger_urls=tuple(debugger_urls or ()),
                ide_bridge_urls=effective_ide_bridge_urls,
                agent_native_bridge_urls=tuple(agent_native_bridge_urls or ()),
                agent_native_bridge_registry_paths=tuple(
                    agent_native_bridge_registry_paths or ()
                ),
                workspace_path=effective_workspace_path,
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
    finally:
        helper = _stop_owned_ide_bridge_helper_if_needed(helper)

    report = MajorScenarioRealNoLossReport(
        output_root=str(root),
        artifact_path="",
        primary_report=primary,
        owned_ide_bridge_helper_report=helper,
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
        (
            f"Owned IDE bridge: launches={report.owned_ide_bridge_launch_attempts}  "
            f"stops={report.owned_ide_bridge_stop_attempts}  "
            f"isolated probes={report.isolated_ide_command_probe_attempts}  "
            f"cleanup={str(report.owned_ide_bridge_cleanup_ok).lower()}"
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
    details = _details(case.get("details", {}))
    dry_run = _details(details.get("uia_semantic_action_dry_run", {}))
    native_dry_run = _details(details.get("wechat_native_bridge_dry_run", {}))
    native_send = _details(details.get("wechat_native_bridge_send_report", {}))
    if bool(details.get("background_send_verified", False)) or bool(
        case.get("background_send_verified", False)
    ):
        status = "verified"
        reason = ""
    elif _case_verified(case):
        status = "gated"
        reason = str(
            details.get("wechat_native_bridge_dry_run_decision", "")
            or native_dry_run.get("decision", "")
            or dry_run.get("decision", "")
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
            "wechat_native_bridge_ready": bool(
                details.get("wechat_native_bridge_ready", False)
            ),
            "wechat_native_bridge_dry_run_decision": str(
                details.get("wechat_native_bridge_dry_run_decision", "")
                or native_dry_run.get("decision", "")
                or ""
            ),
            "wechat_native_bridge_send_decision": str(
                native_send.get("decision", "") or ""
            ),
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
        reason = (
            "native_connector_ready_but_send_not_verified"
            if raw_status == "native_connector_ready"
            else raw_status or "native_ready_send_not_verified"
        )
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


@dataclasses.dataclass(frozen=True)
class OwnedIdeBridgeHelperReport:
    enabled: bool
    output_root: str
    bridge_url: str = ""
    workspace_path: str = ""
    adapter_id: str = "cursor"
    manifest_path: str = ""
    settings_path: str = ""
    ready: bool = False
    cleanup_ok: bool = True
    launch_report: dict = dataclasses.field(default_factory=dict)
    initial_capability_report: dict = dataclasses.field(default_factory=dict)
    pre_probe_settings: dict = dataclasses.field(default_factory=dict)
    contract_probe_report: dict = dataclasses.field(default_factory=dict)
    validated_settings: dict = dataclasses.field(default_factory=dict)
    validated_capability_report: dict = dataclasses.field(default_factory=dict)
    stop_report: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "owned-ide-bridge-helper"

    @property
    def safety_mode(self) -> str:
        return "isolated_helper_launch"

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
    def launch_attempts(self) -> int:
        return _counter(self.launch_report, "launch_attempts")

    @property
    def stop_attempts(self) -> int:
        return _counter(self.stop_report, "stop_attempts")

    @property
    def isolated_command_probe_attempts(self) -> int:
        return _counter(self.contract_probe_report, "control_attempts")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "enabled": self.enabled,
            "ready": self.ready,
            "cleanup_ok": self.cleanup_ok,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "adapter_id": self.adapter_id,
            "manifest_path": self.manifest_path,
            "settings_path": self.settings_path,
            "launch_attempts": self.launch_attempts,
            "stop_attempts": self.stop_attempts,
            "isolated_command_probe_attempts": self.isolated_command_probe_attempts,
            "launch_report": dict(self.launch_report),
            "initial_capability_report": dict(self.initial_capability_report),
            "pre_probe_settings": dict(self.pre_probe_settings),
            "contract_probe_report": dict(self.contract_probe_report),
            "validated_settings": dict(self.validated_settings),
            "validated_capability_report": dict(self.validated_capability_report),
            "stop_report": dict(self.stop_report),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def prepare_owned_ide_bridge_helper(
    *,
    output_root: str | Path,
    project_name: str = "openwukong",
    task_name: str = "major-real-no-loss",
    ide_executable: str = "cursor.exe",
    ide_bridge_port: int = 8791,
    ide_user_data_dir: str = "",
    ide_extensions_dir: str = "",
    ide_extension_dir: str = "extensions/openwukong-vscode",
    workspace_root: str = "",
    adapter_id: str = "cursor",
    capability_timeout_sec: float = 30.0,
    request_timeout_sec: float = 5.0,
    plan_executor: Callable[..., object] | None = None,
    capability_capture: Callable[..., object] | None = None,
    command_contract_probe: Callable[..., object] | None = None,
    bridge_settings_builder: Callable[..., dict] | None = None,
) -> OwnedIdeBridgeHelperReport:
    del task_name
    started = time.perf_counter()
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    host = "127.0.0.1"
    bridge_url = f"http://{host}:{int(ide_bridge_port)}"
    user_data_dir = _owned_helper_path(
        ide_user_data_dir,
        root / "user-data",
    )
    extensions_dir = _owned_helper_path(
        ide_extensions_dir,
        root / "extensions",
    )
    workspace = _owned_helper_path(
        workspace_root,
        root / "workspace" / _safe_path_component(project_name or "workspace"),
    )
    extension_dir = str(Path(ide_extension_dir).expanduser().resolve())
    manifest_path = root / "manifest.json"
    settings_path = Path(user_data_dir) / "User" / "settings.json"
    Path(workspace).mkdir(parents=True, exist_ok=True)

    launch_report: dict = {}
    initial_capability: dict = {}
    pre_probe_settings: dict = {}
    contract_probe: dict = {}
    validated_settings: dict = {}
    validated_capability: dict = {}
    error = ""
    ready = False
    active_plan_executor = plan_executor or execute_session_readiness_plan
    active_capability_capture = capability_capture or capture_ide_bridge_capabilities
    active_contract_probe = command_contract_probe or probe_ide_command_contracts
    active_settings_builder = (
        bridge_settings_builder or build_bridge_settings_from_probe_report
    )

    try:
        plan = build_session_readiness_plan(
            routes=("ide-extension-connector",),
            options=SessionReadinessPlanOptions(
                ide_executable=ide_executable,
                ide_user_data_dir=user_data_dir,
                ide_extensions_dir=extensions_dir,
                ide_extension_dir=extension_dir,
                ide_bridge_host=host,
                ide_bridge_port=int(ide_bridge_port),
                workspace_root=workspace,
            ),
        )
        launch_report = _report_to_dict(
            active_plan_executor(
                plan,
                manifest_path=str(manifest_path),
            )
        )
        if _counter(launch_report, "launch_attempts") <= 0:
            error = "ide_bridge_helper_not_started"
            raise RuntimeError(error)

        initial_capability = _wait_for_ide_bridge_capabilities(
            bridge_url,
            workspace_path=workspace,
            timeout_sec=capability_timeout_sec,
            request_timeout_sec=request_timeout_sec,
            capability_capture=active_capability_capture,
        )
        if not bool(initial_capability.get("ok", False)):
            error = str(
                initial_capability.get("error", "")
                or "ide_bridge_capability_not_ready"
            )
            raise RuntimeError(error)

        command_ids = select_probe_command_ids(
            initial_capability,
            adapter_id=adapter_id,
            max_commands=1,
        )
        if not command_ids:
            error = "ide_bridge_no_probe_candidates"
            raise RuntimeError(error)

        pre_probe_settings = {
            "openwukong.bridge.autoStart": True,
            "openwukong.bridge.host": host,
            "openwukong.bridge.port": int(ide_bridge_port),
            "openwukong.bridge.allowedCommands": command_ids,
        }
        _merge_settings_file(settings_path, pre_probe_settings)

        contract_probe = _report_to_dict(
            active_contract_probe(
                bridge_url,
                workspace_path=workspace,
                command_ids=command_ids,
                adapter_id=adapter_id,
                message="OPENWUKONG_IDE_BRIDGE_CONTRACT_PROBE_NO_EDIT",
                request_timeout=request_timeout_sec,
            )
        )
        validated_settings = active_settings_builder(
            contract_probe,
            host=host,
            port=int(ide_bridge_port),
            auto_start=True,
        )
        _merge_settings_file(settings_path, validated_settings)

        validated_capability = _wait_for_ide_bridge_capabilities(
            bridge_url,
            workspace_path=workspace,
            timeout_sec=capability_timeout_sec,
            request_timeout_sec=request_timeout_sec,
            adapter_id=adapter_id,
            capability_capture=active_capability_capture,
        )
        ready = bool(
            validated_capability.get("ok", False)
            and _adapter_available(validated_capability, adapter_id)
        )
        if not ready:
            error = str(
                validated_capability.get("error", "")
                or "ide_bridge_adapter_not_validated"
            )
    except Exception as exc:
        if not error:
            error = str(exc) or exc.__class__.__name__

    return OwnedIdeBridgeHelperReport(
        enabled=True,
        output_root=str(root),
        bridge_url=bridge_url,
        workspace_path=workspace,
        adapter_id=adapter_id,
        manifest_path=str(manifest_path),
        settings_path=str(settings_path),
        ready=ready,
        cleanup_ok=False,
        launch_report=launch_report,
        initial_capability_report=initial_capability,
        pre_probe_settings=pre_probe_settings,
        contract_probe_report=contract_probe,
        validated_settings=validated_settings,
        validated_capability_report=validated_capability,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _details(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _disabled_owned_ide_bridge_helper_report() -> dict:
    return {
        "mode": "owned-ide-bridge-helper",
        "safety_mode": "isolated_helper_launch",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "enabled": False,
        "ready": False,
        "cleanup_ok": True,
        "bridge_url": "",
        "workspace_path": "",
        "adapter_id": "",
        "manifest_path": "",
        "launch_attempts": 0,
        "stop_attempts": 0,
        "isolated_command_probe_attempts": 0,
    }


def _effective_ide_bridge_urls(
    explicit_urls: Iterable[str],
    helper_report: dict,
) -> tuple[str, ...]:
    urls: list[str] = []
    for value in explicit_urls or ():
        text = str(value or "").strip()
        if text and text not in urls:
            urls.append(text)
    if bool(helper_report.get("ready", False)):
        bridge_url = str(helper_report.get("bridge_url", "") or "").strip()
        if bridge_url and bridge_url not in urls:
            urls.append(bridge_url)
    return tuple(urls)


def _stop_owned_ide_bridge_helper_if_needed(helper_report: dict) -> dict:
    if not bool(helper_report.get("enabled", False)):
        return helper_report
    manifest_path = str(helper_report.get("manifest_path", "") or "").strip()
    if not manifest_path:
        return dict(helper_report)
    existing_stop = helper_report.get("stop_report")
    if isinstance(existing_stop, dict) and existing_stop:
        return dict(helper_report)
    stop_report = stop_session_readiness_manifest(manifest_path).to_dict()
    updated = dict(helper_report)
    updated["stop_report"] = stop_report
    updated["stop_attempts"] = _counter(stop_report, "stop_attempts")
    updated["cleanup_ok"] = _stop_report_cleanup_ok(stop_report)
    return updated


def _stop_report_cleanup_ok(stop_report: dict) -> bool:
    results = stop_report.get("results")
    if not isinstance(results, list):
        return False
    if not results:
        return True
    allowed = {"stopped", "skipped"}
    return all(
        isinstance(result, dict)
        and str(result.get("status", "") or "") in allowed
        and not str(result.get("error", "") or "").strip()
        for result in results
    )


def _owned_helper_path(value: str, default_path: Path) -> str:
    text = str(value or "").strip()
    path = Path(text).expanduser() if text else default_path
    if not path.is_absolute():
        path = path.resolve()
    return path.as_posix()


def _safe_path_component(value: str) -> str:
    text = str(value or "").strip() or "workspace"
    safe = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in text
    )
    return safe.strip(".-") or "workspace"


def _merge_settings_file(settings_path: Path, settings: dict) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if settings_path.exists():
        try:
            parsed = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                existing = parsed
        except Exception:
            existing = {}
    merged = dict(existing)
    merged.update(dict(settings))
    settings_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _wait_for_ide_bridge_capabilities(
    bridge_url: str,
    *,
    workspace_path: str,
    timeout_sec: float,
    request_timeout_sec: float,
    adapter_id: str = "",
    capability_capture: Callable[..., object] | None = None,
) -> dict:
    deadline = time.monotonic() + max(0.1, float(timeout_sec or 0.1))
    last: dict = {}
    active_capture = capability_capture or capture_ide_bridge_capabilities
    while True:
        last = _report_to_dict(
            active_capture(
                bridge_url,
                workspace_path=workspace_path,
                request_timeout=request_timeout_sec,
            )
        )
        if bool(last.get("ok", False)) and (
            not adapter_id or _adapter_available(last, adapter_id)
        ):
            return last
        if time.monotonic() >= deadline:
            if not last.get("error"):
                last["error"] = "ide_bridge_capability_timeout"
            return last
        time.sleep(0.5)


def _adapter_available(capability_report: dict, adapter_id: str) -> bool:
    adapter = {}
    mapping = capability_report.get("adapter_mapping")
    if isinstance(mapping, dict):
        value = mapping.get(adapter_id)
        if isinstance(value, dict):
            adapter = value
    if not adapter:
        active = capability_report.get("active_mapping")
        if isinstance(active, dict):
            value = active.get(adapter_id)
            if isinstance(value, dict):
                adapter = value
    return bool(
        adapter
        and adapter.get("available", False)
        and str(
            adapter.get("commandId", "")
            or adapter.get("command_id", "")
            or ""
        ).strip()
    )


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
    parser.add_argument(
        "--allow-wechat-uia-semantic-send",
        action="store_true",
        help="Allow explicit WeChat UIA ValuePattern/InvokePattern semantic send when the File Transfer Assistant contract is ready.",
    )
    parser.add_argument(
        "--wechat-uia-message",
        default="OPENWUKONG_WECHAT_UIA_SEMANTIC_SEND",
        help="Message used for optional WeChat UIA semantic send.",
    )
    parser.add_argument(
        "--wechat-uia-acceptance-marker",
        action="append",
        default=[],
        help="Required WeChat UIA send readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--wechat-uia-forbid-marker",
        action="append",
        default=[],
        help="Forbidden WeChat UIA send readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--wechat-native-bridge-url",
        action="append",
        default=[],
        help="Explicit local WeChat native bridge URL used for read-only capabilities and optional send.",
    )
    parser.add_argument(
        "--allow-wechat-native-bridge-send",
        action="store_true",
        help="Allow explicit WeChat native bridge sends when the dry-run contract is ready.",
    )
    parser.add_argument(
        "--wechat-native-bridge-message",
        default="OPENWUKONG_WECHAT_NATIVE_BRIDGE_SEND",
        help="Message used for optional WeChat native bridge send.",
    )
    parser.add_argument(
        "--wechat-native-bridge-acceptance-marker",
        action="append",
        default=[],
        help="Required WeChat native bridge readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--wechat-native-bridge-forbid-marker",
        action="append",
        default=[],
        help="Forbidden WeChat native bridge readback marker. Repeat for multiple markers.",
    )
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
        "--debugger-url",
        action="append",
        default=[],
        help="Explicit local DevTools debugger URL forwarded to agent app no-loss probes after process-port ownership validation.",
    )
    parser.add_argument(
        "--ide-bridge-url",
        action="append",
        default=[],
        help="Explicit IDE extension/native bridge URL forwarded to agent app no-loss probes.",
    )
    parser.add_argument(
        "--agent-native-bridge-url",
        action="append",
        default=[],
        help="Explicit agent app native bridge URL forwarded to agent app no-loss probes.",
    )
    parser.add_argument(
        "--agent-native-bridge-registry",
        action="append",
        default=[],
        help="Read-only JSON registry file with agent app native bridge URLs.",
    )
    parser.add_argument(
        "--workspace-path",
        default="",
        help="Optional workspace path included in IDE bridge capability probes.",
    )
    parser.add_argument(
        "--allow-owned-ide-bridge-helper-launch",
        action="store_true",
        help="Launch an isolated VS Code-compatible IDE extension host, validate an IDE bridge chat adapter, and forward it to app probes.",
    )
    parser.add_argument("--owned-ide-executable", default="cursor.exe")
    parser.add_argument("--owned-ide-bridge-port", type=int, default=8791)
    parser.add_argument("--owned-ide-user-data-dir", default="")
    parser.add_argument("--owned-ide-extensions-dir", default="")
    parser.add_argument("--owned-ide-extension-dir", default="extensions/openwukong-vscode")
    parser.add_argument("--owned-ide-workspace-root", default="")
    parser.add_argument("--owned-ide-chat-adapter-id", default="cursor")
    parser.add_argument("--owned-ide-capability-timeout-sec", type=float, default=30.0)
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
        allow_wechat_uia_semantic_send=args.allow_wechat_uia_semantic_send,
        wechat_uia_message=args.wechat_uia_message,
        wechat_uia_required_markers=tuple(args.wechat_uia_acceptance_marker or ()),
        wechat_uia_forbidden_markers=tuple(args.wechat_uia_forbid_marker or ()),
        wechat_native_bridge_urls=tuple(args.wechat_native_bridge_url or ()),
        allow_wechat_native_bridge_send=args.allow_wechat_native_bridge_send,
        wechat_native_bridge_message=args.wechat_native_bridge_message,
        wechat_native_bridge_required_markers=tuple(
            args.wechat_native_bridge_acceptance_marker or ()
        ),
        wechat_native_bridge_forbidden_markers=tuple(
            args.wechat_native_bridge_forbid_marker or ()
        ),
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
        debugger_urls=tuple(args.debugger_url or ()),
        ide_bridge_urls=tuple(args.ide_bridge_url or ()),
        agent_native_bridge_urls=tuple(args.agent_native_bridge_url or ()),
        agent_native_bridge_registry_paths=tuple(args.agent_native_bridge_registry or ()),
        workspace_path=args.workspace_path,
        allow_owned_ide_bridge_helper_launch=args.allow_owned_ide_bridge_helper_launch,
        owned_ide_executable=args.owned_ide_executable,
        owned_ide_bridge_port=args.owned_ide_bridge_port,
        owned_ide_user_data_dir=args.owned_ide_user_data_dir,
        owned_ide_extensions_dir=args.owned_ide_extensions_dir,
        owned_ide_extension_dir=args.owned_ide_extension_dir,
        owned_ide_workspace_root=args.owned_ide_workspace_root,
        owned_ide_chat_adapter_id=args.owned_ide_chat_adapter_id,
        owned_ide_capability_timeout_sec=args.owned_ide_capability_timeout_sec,
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
