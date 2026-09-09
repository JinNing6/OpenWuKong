# -*- coding: utf-8 -*-
"""Unified real no-loss acceptance report for the main desktop scenarios."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import queue
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.connectors.browser import BrowserDevToolsClient
from openwukong.control.agent_app_transport_matrix import (
    summarize_agent_app_transport_matrices,
)
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    WindowsAppResolver,
    claude_candidate_surface_kind,
    codex_candidate_surface_kind,
    cursor_candidate_surface_kind,
)
from openwukong.control.desktop_system_dialog import (
    run_desktop_system_dialog_preflight,
)
from openwukong.control.session_readiness_plan import (
    SessionReadinessPlanOptions,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.evaluation.agent_app_real_no_loss import (
    run_agent_app_real_no_loss,
)
from openwukong.evaluation.agent_app_bridge_fixture_smoke import (
    run_agent_app_bridge_fixture_smoke as run_default_agent_app_bridge_fixture_smoke,
)
from openwukong.evaluation.agent_native_bridge_fixture_smoke import (
    run_agent_native_bridge_fixture_smoke as run_default_agent_native_bridge_fixture_smoke,
)
from openwukong.evaluation.wechat_native_bridge_fixture_smoke import (
    run_wechat_native_bridge_fixture_smoke as run_default_wechat_native_bridge_fixture_smoke,
)
from openwukong.evaluation.agent_native_connector_probe import (
    NativeProcessSnapshot,
    RequestsNativeConnectorHTTPProbe,
    list_native_processes,
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
from openwukong.evaluation.ide_extension_readiness import (
    DEFAULT_BRIDGE_URL as DEFAULT_IDE_EXTENSION_BRIDGE_URL,
    probe_ide_extension_bridge_readiness,
)
from openwukong.evaluation.primary_real_no_loss import (
    _resolve_installed_browser_executable,
    run_primary_real_no_loss,
)
from openwukong.evaluation.objective_readiness_matrix import (
    build_objective_readiness_matrix,
)
from openwukong.evaluation.simulation import load_simulation_fixture


DEFAULT_MAJOR_FIXTURE = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
DEFAULT_AGENT_APPS = ("codex app", "claude desktop")
DEFAULT_CLI_AGENTS = ("codex", "cursor")
CLI_REQUIREMENT_SPECS = {
    "codex": ("codex_cli_background_task", "codex"),
    "claude": ("claude_cli_background_task", "claude"),
    "cursor": ("cursor_cli_background_task", "cursor"),
}


PrimaryRunner = Callable[..., object]
AgentAppRunner = Callable[..., object]
AgentAppBridgeFixtureSmokeRunner = Callable[..., object]
AgentNativeBridgeFixtureSmokeRunner = Callable[..., object]
WeChatNativeBridgeFixtureSmokeRunner = Callable[..., object]
AgentCliRunner = Callable[..., object]
SystemDialogPreflightRunner = Callable[..., object]
OwnedIdeBridgeHelperRunner = Callable[..., object]
AgentNativeCdpBridgeHelperRunner = Callable[..., object]
AgentAppDevToolsOwnedLaunchRunner = Callable[..., object]
IDEExtensionReadinessRunner = Callable[..., object]
AgentAppDevToolsResolver = object


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
    agent_native_cdp_bridge_helper_report: dict
    agent_app_report: dict
    agent_app_bridge_fixture_smoke_report: dict
    agent_cli_report: dict
    requirements: tuple[MajorRequirement, ...]
    agent_native_bridge_fixture_smoke_report: dict = dataclasses.field(
        default_factory=dict
    )
    wechat_native_bridge_fixture_smoke_report: dict = dataclasses.field(
        default_factory=dict
    )
    system_dialog_preflight_report: dict = dataclasses.field(default_factory=dict)
    ide_extension_readiness_report: dict = dataclasses.field(default_factory=dict)
    agent_app_devtools_resolution_report: dict = dataclasses.field(default_factory=dict)
    agent_app_devtools_owned_launch_report: dict = dataclasses.field(default_factory=dict)
    scenario_scope_report: dict = dataclasses.field(default_factory=dict)
    runner_stage_reports: tuple[dict, ...] = dataclasses.field(default_factory=tuple)
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
        return (
            _sum_counter(
                self.system_dialog_preflight_report,
                self.primary_report,
                self.ide_extension_readiness_report,
                self.agent_app_report,
                self.agent_cli_report,
                key="control_attempts",
            )
            + self.agent_app_bridge_fixture_control_attempts
            + self.agent_native_bridge_fixture_control_attempts
            + self.wechat_native_bridge_fixture_control_attempts
        )

    @property
    def external_communication_attempts(self) -> int:
        return _counter(self.primary_report, "external_communication_attempts")

    @property
    def window_input_attempts(self) -> int:
        return _sum_counter(
            self.system_dialog_preflight_report,
            self.primary_report,
            self.ide_extension_readiness_report,
            self.agent_app_bridge_fixture_smoke_report,
            self.agent_native_bridge_fixture_smoke_report,
            self.wechat_native_bridge_fixture_smoke_report,
            self.agent_app_report,
            self.agent_cli_report,
            key="window_input_attempts",
        )

    @property
    def agent_app_bridge_fixture_smoke_enabled(self) -> bool:
        return bool(self.agent_app_bridge_fixture_smoke_report.get("enabled", False))

    @property
    def agent_app_bridge_fixture_smoke_ok(self) -> bool:
        if not self.agent_app_bridge_fixture_smoke_report:
            return True
        if not self.agent_app_bridge_fixture_smoke_enabled:
            return True
        return bool(self.agent_app_bridge_fixture_smoke_report.get("ok", False))

    @property
    def agent_app_bridge_fixture_control_attempts(self) -> int:
        return _counter(
            self.agent_app_bridge_fixture_smoke_report,
            "control_attempts",
        ) + _counter(
            self.agent_app_bridge_fixture_smoke_report,
            "desktop_control_attempts",
        )

    @property
    def agent_app_bridge_fixture_native_call_attempts(self) -> int:
        bridge_send = self.agent_app_bridge_fixture_smoke_report.get(
            "bridge_send_report",
            {},
        )
        if not isinstance(bridge_send, dict):
            bridge_send = {}
        return _counter(bridge_send, "native_call_attempts")

    @property
    def agent_native_bridge_fixture_smoke_enabled(self) -> bool:
        return bool(
            self.agent_native_bridge_fixture_smoke_report.get("enabled", False)
        )

    @property
    def agent_native_bridge_fixture_smoke_ok(self) -> bool:
        if not self.agent_native_bridge_fixture_smoke_report:
            return True
        if not self.agent_native_bridge_fixture_smoke_enabled:
            return True
        return bool(self.agent_native_bridge_fixture_smoke_report.get("ok", False))

    @property
    def agent_native_bridge_fixture_control_attempts(self) -> int:
        return _counter(
            self.agent_native_bridge_fixture_smoke_report,
            "control_attempts",
        ) + _counter(
            self.agent_native_bridge_fixture_smoke_report,
            "desktop_control_attempts",
        )

    @property
    def agent_native_bridge_fixture_native_call_attempts(self) -> int:
        send_report = self.agent_native_bridge_fixture_smoke_report.get(
            "send_report",
            {},
        )
        if not isinstance(send_report, dict):
            send_report = {}
        return _counter(
            self.agent_native_bridge_fixture_smoke_report,
            "native_call_attempts",
        ) or _counter(send_report, "native_call_attempts")

    @property
    def wechat_native_bridge_fixture_smoke_enabled(self) -> bool:
        return bool(
            self.wechat_native_bridge_fixture_smoke_report.get("enabled", False)
        )

    @property
    def wechat_native_bridge_fixture_smoke_ok(self) -> bool:
        if not self.wechat_native_bridge_fixture_smoke_report:
            return True
        if not self.wechat_native_bridge_fixture_smoke_enabled:
            return True
        return bool(self.wechat_native_bridge_fixture_smoke_report.get("ok", False))

    @property
    def wechat_native_bridge_fixture_control_attempts(self) -> int:
        return _counter(
            self.wechat_native_bridge_fixture_smoke_report,
            "control_attempts",
        )

    @property
    def wechat_native_bridge_fixture_native_call_attempts(self) -> int:
        send_report = self.wechat_native_bridge_fixture_smoke_report.get(
            "send_report",
            {},
        )
        if not isinstance(send_report, dict):
            send_report = {}
        return _counter(
            self.wechat_native_bridge_fixture_smoke_report,
            "native_call_attempts",
        ) or _counter(send_report, "native_call_attempts")

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
    def agent_native_cdp_bridge_launch_attempts(self) -> int:
        return _counter(self.agent_native_cdp_bridge_helper_report, "launch_attempts")

    @property
    def agent_native_cdp_bridge_stop_attempts(self) -> int:
        return _counter(self.agent_native_cdp_bridge_helper_report, "stop_attempts")

    @property
    def agent_native_cdp_bridge_cleanup_ok(self) -> bool:
        if not self.agent_native_cdp_bridge_helper_report:
            return True
        if not bool(self.agent_native_cdp_bridge_helper_report.get("enabled", False)):
            return True
        return bool(
            self.agent_native_cdp_bridge_helper_report.get("cleanup_ok", False)
        )

    @property
    def agent_app_devtools_launch_attempts(self) -> int:
        return _counter(self.agent_app_devtools_owned_launch_report, "launch_attempts")

    @property
    def agent_app_devtools_stop_attempts(self) -> int:
        return _counter(self.agent_app_devtools_owned_launch_report, "stop_attempts")

    @property
    def agent_app_devtools_cleanup_ok(self) -> bool:
        if not self.agent_app_devtools_owned_launch_report:
            return True
        if not bool(self.agent_app_devtools_owned_launch_report.get("enabled", False)):
            return True
        return bool(
            self.agent_app_devtools_owned_launch_report.get("cleanup_ok", False)
        )

    @property
    def bridge_send_attempts(self) -> int:
        return _counter(self.ide_extension_readiness_report, "bridge_send_attempts") + _counter(
            self.agent_app_report,
            "bridge_send_attempts",
        )

    @property
    def agent_command_attempts(self) -> int:
        return _counter(self.agent_app_report, "agent_command_attempts") + _counter(
            self.agent_cli_report,
            "agent_command_attempts",
        )

    @property
    def system_dialog_preflight_failed(self) -> bool:
        if not self.system_dialog_preflight_report:
            return False
        return bool(
            self.system_dialog_preflight_report.get("system_dialog_detected", False)
            or not bool(self.system_dialog_preflight_report.get("ok", True))
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
    def cli_foreground_focus_stable(self) -> bool:
        return bool(self.agent_cli_report.get("foreground_focus_stable", True))

    @property
    def cli_foreground_no_steal_verified(self) -> bool:
        return bool(self.agent_cli_report.get("foreground_no_steal_verified", True))

    @property
    def automation_focus_risk_attempts(self) -> int:
        return (
            self.control_attempts
            + self.window_input_attempts
            + self.external_communication_attempts
            + self.owned_ide_bridge_launch_attempts
            + self.agent_app_devtools_launch_attempts
            + self.bridge_send_attempts
            + self.agent_command_attempts
            + self.owned_app_launch_attempts
        )

    @property
    def automation_focus_safe(self) -> bool:
        if self.background_screenshot_focus_stable and self.cli_foreground_no_steal_verified:
            return True
        return self.automation_focus_risk_attempts == 0

    @property
    def agent_app_endpoint_acceptance(self) -> dict:
        return _build_agent_app_endpoint_acceptance(
            self.agent_app_report,
            self.agent_native_cdp_bridge_helper_report,
            self.agent_app_devtools_resolution_report,
            self.agent_app_devtools_owned_launch_report,
            output_root=self.output_root,
        )

    @property
    def agent_app_endpoint_readiness(self) -> dict:
        return _build_agent_app_endpoint_readiness(
            self.agent_app_report,
            self.agent_app_endpoint_acceptance,
            self.ide_extension_readiness_report,
        )

    @property
    def agent_app_transport_matrix_summary(self) -> dict:
        summary = self.agent_app_report.get("transport_matrix_summary")
        if isinstance(summary, dict):
            return dict(summary)
        cases = self.agent_app_report.get("cases", [])
        return summarize_agent_app_transport_matrices(
            item for item in cases if isinstance(item, dict)
        )

    @property
    def objective_readiness_matrix(self) -> dict:
        return build_objective_readiness_matrix(
            primary_report=self.primary_report,
            agent_app_report=self.agent_app_report,
            agent_cli_report=self.agent_cli_report,
            requirements=(item.to_dict() for item in self.requirements),
            safe_run_ok=self.safe_run_ok,
        ).to_dict()

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
        ) + (1 if self.system_dialog_preflight_failed else 0) + (
            0 if self.owned_ide_bridge_cleanup_ok else 1
        ) + (
            0 if self.agent_native_cdp_bridge_cleanup_ok else 1
        ) + (
            0 if self.agent_app_devtools_cleanup_ok else 1
        ) + (
            0 if self.agent_app_bridge_fixture_smoke_ok else 1
        ) + (
            0 if self.agent_native_bridge_fixture_smoke_ok else 1
        ) + (
            0 if self.wechat_native_bridge_fixture_smoke_ok else 1
        )

    @property
    def runner_timed_out(self) -> bool:
        return any(
            bool(item.get("timed_out", False))
            or str(item.get("status", "") or "") == "timed_out"
            for item in self.runner_stage_reports
            if isinstance(item, dict)
        )

    @property
    def runner_stage_failed(self) -> bool:
        return any(
            str(item.get("status", "") or "") in {"failed", "timed_out"}
            for item in self.runner_stage_reports
            if isinstance(item, dict)
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
            self.requirements
            and not self.unmet_requirements
            and self.failed_runner_count == 0
            and self.control_attempts == 0
            and self.window_input_attempts == 0
            and self.automation_focus_safe
            and self.owned_ide_bridge_cleanup_ok
            and self.agent_native_cdp_bridge_cleanup_ok
            and self.agent_app_devtools_cleanup_ok
            and not self.runner_stage_failed
        )

    @property
    def safe_run_ok(self) -> bool:
        return bool(
            self.failed_runner_count == 0
            and self.control_attempts == 0
            and self.window_input_attempts == 0
            and self.automation_focus_safe
            and self.owned_ide_bridge_cleanup_ok
            and self.agent_native_cdp_bridge_cleanup_ok
            and self.agent_app_devtools_cleanup_ok
            and not self.runner_stage_failed
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
            "agent_native_cdp_bridge_launch_attempts": self.agent_native_cdp_bridge_launch_attempts,
            "agent_native_cdp_bridge_stop_attempts": self.agent_native_cdp_bridge_stop_attempts,
            "agent_native_cdp_bridge_cleanup_ok": self.agent_native_cdp_bridge_cleanup_ok,
            "agent_app_devtools_launch_attempts": self.agent_app_devtools_launch_attempts,
            "agent_app_devtools_stop_attempts": self.agent_app_devtools_stop_attempts,
            "agent_app_devtools_cleanup_ok": self.agent_app_devtools_cleanup_ok,
            "agent_app_bridge_fixture_smoke_enabled": self.agent_app_bridge_fixture_smoke_enabled,
            "agent_app_bridge_fixture_smoke_ok": self.agent_app_bridge_fixture_smoke_ok,
            "agent_app_bridge_fixture_control_attempts": self.agent_app_bridge_fixture_control_attempts,
            "agent_app_bridge_fixture_native_call_attempts": self.agent_app_bridge_fixture_native_call_attempts,
            "agent_native_bridge_fixture_smoke_enabled": self.agent_native_bridge_fixture_smoke_enabled,
            "agent_native_bridge_fixture_smoke_ok": self.agent_native_bridge_fixture_smoke_ok,
            "agent_native_bridge_fixture_control_attempts": self.agent_native_bridge_fixture_control_attempts,
            "agent_native_bridge_fixture_native_call_attempts": self.agent_native_bridge_fixture_native_call_attempts,
            "wechat_native_bridge_fixture_smoke_enabled": self.wechat_native_bridge_fixture_smoke_enabled,
            "wechat_native_bridge_fixture_smoke_ok": self.wechat_native_bridge_fixture_smoke_ok,
            "wechat_native_bridge_fixture_control_attempts": self.wechat_native_bridge_fixture_control_attempts,
            "wechat_native_bridge_fixture_native_call_attempts": self.wechat_native_bridge_fixture_native_call_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "owned_app_launch_attempts": self.owned_app_launch_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "cli_foreground_focus_stable": self.cli_foreground_focus_stable,
            "cli_foreground_no_steal_verified": self.cli_foreground_no_steal_verified,
            "automation_focus_risk_attempts": self.automation_focus_risk_attempts,
            "automation_focus_safe": self.automation_focus_safe,
            "failed_runner_count": self.failed_runner_count,
            "runner_timed_out": self.runner_timed_out,
            "runner_stage_failed": self.runner_stage_failed,
            "runner_stage_reports": [dict(item) for item in self.runner_stage_reports],
            "goal_complete": self.goal_complete,
            "safe_run_ok": self.safe_run_ok,
            "scenario_scope": dict(self.scenario_scope_report),
            "system_dialog_preflight_failed": self.system_dialog_preflight_failed,
            "system_dialog_preflight": dict(self.system_dialog_preflight_report),
            "agent_app_endpoint_acceptance": self.agent_app_endpoint_acceptance,
            "agent_app_endpoint_readiness": self.agent_app_endpoint_readiness,
            "agent_app_transport_matrix_summary": self.agent_app_transport_matrix_summary,
            "objective_readiness_matrix": self.objective_readiness_matrix,
            "ide_extension_readiness": dict(self.ide_extension_readiness_report),
            "agent_app_devtools_resolution": dict(
                self.agent_app_devtools_resolution_report
            ),
            "agent_app_bridge_fixture_smoke": dict(
                self.agent_app_bridge_fixture_smoke_report
            ),
            "agent_native_bridge_fixture_smoke": dict(
                self.agent_native_bridge_fixture_smoke_report
            ),
            "wechat_native_bridge_fixture_smoke": dict(
                self.wechat_native_bridge_fixture_smoke_report
            ),
            "unmet_requirements": list(self.unmet_requirements),
            "requirements": [
                requirement.to_dict() for requirement in self.requirements
            ],
            "output_root": self.output_root,
            "artifact_path": self.artifact_path,
            "subreports": {
                "system_dialog_preflight": dict(self.system_dialog_preflight_report),
                "primary": dict(self.primary_report),
                "ide_extension_readiness": dict(self.ide_extension_readiness_report),
                "owned_ide_bridge_helper": dict(self.owned_ide_bridge_helper_report),
                "agent_native_cdp_bridge_helper": dict(
                    self.agent_native_cdp_bridge_helper_report
                ),
                "agent_app": dict(self.agent_app_report),
                "agent_app_devtools_resolution": dict(
                    self.agent_app_devtools_resolution_report
                ),
                "agent_app_devtools_owned_launch": dict(
                    self.agent_app_devtools_owned_launch_report
                ),
                "agent_app_bridge_fixture_smoke": dict(
                    self.agent_app_bridge_fixture_smoke_report
                ),
                "agent_native_bridge_fixture_smoke": dict(
                    self.agent_native_bridge_fixture_smoke_report
                ),
                "wechat_native_bridge_fixture_smoke": dict(
                    self.wechat_native_bridge_fixture_smoke_report
                ),
                "agent_cli": dict(self.agent_cli_report),
            },
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_major_scenario_real_no_loss(
    *,
    fixture: dict | None = None,
    fixture_path: str | Path = DEFAULT_MAJOR_FIXTURE,
    output_root: str | Path = "",
    runner_timeout_sec: float = 0.0,
    stop_on_runner_timeout: bool = False,
    run_primary_scenarios: bool = True,
    run_agent_app_scenarios: bool = True,
    run_agent_cli_scenarios: bool = True,
    isolate_agent_app_scenarios: bool = False,
    isolate_agent_cli_scenarios: bool = False,
    allow_owned_browser_helper_launch: bool = False,
    owned_browser_debug_port: int = 0,
    owned_browser_executable: str = "chrome.exe",
    owned_browser_url: str = "data:text/html,<title>OpenWukong Major No Loss</title><body>OpenWukong Major No Loss</body>",
    background_screenshot_dir: str | Path = "",
    allow_wechat_uia_semantic_send: bool = False,
    wechat_uia_message: str = "OPENWUKONG_WECHAT_UIA_SEMANTIC_SEND",
    wechat_uia_required_markers: tuple[str, ...] = (),
    wechat_uia_forbidden_markers: tuple[str, ...] = (),
    wechat_native_bridge_urls: Iterable[str] = (),
    wechat_native_bridge_registry_paths: Iterable[str | Path] = (),
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
    allow_codex_app_server_thread_start: bool = False,
    codex_app_server_thread_start_timeout: float = 5.0,
    allow_codex_app_server_turn_start: bool = False,
    codex_app_server_turn_start_timeout: float = 30.0,
    run_agent_app_bridge_fixture_smoke: bool = False,
    agent_app_bridge_fixture_message: str = "OPENWUKONG_APP_BRIDGE_FIXTURE_SMOKE",
    agent_app_bridge_fixture_required_markers: tuple[str, ...] = (
        "OPENWUKONG_ACCEPTANCE: PASS",
    ),
    agent_app_bridge_fixture_forbidden_markers: tuple[str, ...] = (),
    run_agent_native_bridge_fixture_smoke: bool = False,
    agent_native_bridge_fixture_message: str = (
        "OPENWUKONG_AGENT_NATIVE_BRIDGE_FIXTURE_SMOKE"
    ),
    agent_native_bridge_fixture_required_markers: tuple[str, ...] = (
        "OPENWUKONG_ACCEPTANCE: PASS",
    ),
    agent_native_bridge_fixture_forbidden_markers: tuple[str, ...] = (),
    run_wechat_native_bridge_fixture_smoke: bool = False,
    wechat_native_bridge_fixture_message: str = "OPENWUKONG_WECHAT_FIXTURE: PASS",
    wechat_native_bridge_fixture_required_markers: tuple[str, ...] = (
        "OPENWUKONG_WECHAT_FIXTURE: PASS",
    ),
    wechat_native_bridge_fixture_forbidden_markers: tuple[str, ...] = (),
    debugger_urls: Iterable[str] = (),
    ide_bridge_urls: Iterable[str] = (),
    probe_existing_ide_extension_bridge: bool = False,
    ide_extension_bridge_url: str = DEFAULT_IDE_EXTENSION_BRIDGE_URL,
    ide_extension_agent_id: str = "cursor",
    ide_extension_request_timeout_sec: float = 0.5,
    agent_native_bridge_urls: Iterable[str] = (),
    agent_native_bridge_registry_paths: Iterable[str | Path] = (),
    codex_app_server_ws_urls: Iterable[str] = (),
    workspace_path: str = "",
    allow_owned_ide_bridge_helper_launch: bool = False,
    owned_ide_executable: str = "cursor.exe",
    owned_ide_bridge_port: int = 0,
    owned_ide_user_data_dir: str = "",
    owned_ide_extensions_dir: str = "",
    owned_ide_extension_dir: str = "extensions/openwukong-vscode",
    owned_ide_workspace_root: str = "",
    owned_ide_chat_adapter_id: str = "cursor",
    owned_ide_capability_timeout_sec: float = 30.0,
    allow_agent_native_cdp_bridge_helper_launch: bool = False,
    agent_native_cdp_bridge_helper_agent: str = "codex app",
    agent_native_cdp_bridge_helper_agent_id: str = "codex",
    agent_native_cdp_bridge_helper_port: int = 0,
    agent_native_cdp_bridge_helper_debugger_url: str = "",
    agent_native_cdp_bridge_helper_process_name: str = "Codex.exe",
    agent_native_cdp_bridge_helper_pid: int = 0,
    agent_native_cdp_bridge_helper_hwnd: int = 0,
    agent_native_cdp_bridge_helper_window_title: str = "",
    agent_native_cdp_bridge_helper_target_title: str = "",
    agent_native_cdp_bridge_helper_target_url: str = "",
    agent_native_cdp_bridge_registry_wait_timeout_sec: float = 5.0,
    agent_native_cdp_bridge_helper_specs: Iterable[dict] = (),
    allow_agent_app_devtools_owned_launch: bool = False,
    allow_agent_app_devtools_default_profile_launch: bool = False,
    agent_app_devtools_endpoint_wait_timeout_sec: float = 10.0,
    agent_app_devtools_request_timeout_sec: float = 0.2,
    allow_agent_cli_execution: bool = False,
    agent_cli_timeout_sec: float = 90.0,
    primary_runner: PrimaryRunner | None = None,
    owned_ide_bridge_helper_runner: OwnedIdeBridgeHelperRunner | None = None,
    agent_native_cdp_bridge_helper_runner: AgentNativeCdpBridgeHelperRunner | None = None,
    agent_app_runner: AgentAppRunner | None = None,
    agent_app_bridge_fixture_smoke_runner: AgentAppBridgeFixtureSmokeRunner | None = None,
    agent_native_bridge_fixture_smoke_runner: (
        AgentNativeBridgeFixtureSmokeRunner | None
    ) = None,
    wechat_native_bridge_fixture_smoke_runner: WeChatNativeBridgeFixtureSmokeRunner | None = None,
    agent_app_devtools_resolver: AgentAppDevToolsResolver | None = None,
    agent_app_devtools_owned_launch_runner: AgentAppDevToolsOwnedLaunchRunner | None = None,
    ide_extension_readiness_runner: IDEExtensionReadinessRunner | None = None,
    agent_app_process_provider: Callable[[], Iterable[NativeProcessSnapshot]] | None = None,
    agent_cli_runner: AgentCliRunner | None = None,
    system_dialog_preflight_runner: SystemDialogPreflightRunner | None = None,
) -> MajorScenarioRealNoLossReport:
    started = time.perf_counter()
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    runner_stages: list[dict] = []
    scenario_scope = _build_scenario_scope_report(
        run_primary_scenarios=run_primary_scenarios,
        run_agent_app_scenarios=run_agent_app_scenarios,
        run_agent_cli_scenarios=run_agent_cli_scenarios,
    )
    system_dialog_preflight = _report_to_dict(
        _run_major_stage(
            "system_dialog_preflight",
            runner_timeout_sec=runner_timeout_sec,
            stage_reports=runner_stages,
            output_root=root,
            runner=lambda: (
                system_dialog_preflight_runner or run_desktop_system_dialog_preflight
            )(),
        )
    )
    if _system_dialog_preflight_failed(system_dialog_preflight):
        report = MajorScenarioRealNoLossReport(
            output_root=str(root),
            artifact_path="",
            primary_report={},
            owned_ide_bridge_helper_report=_disabled_owned_ide_bridge_helper_report(),
            agent_native_cdp_bridge_helper_report=(
                _disabled_agent_native_cdp_bridge_helper_report()
            ),
            agent_app_report={},
            agent_app_bridge_fixture_smoke_report=(
                _disabled_agent_app_bridge_fixture_smoke_report()
            ),
            agent_cli_report={},
            agent_native_bridge_fixture_smoke_report=(
                _disabled_agent_native_bridge_fixture_smoke_report()
            ),
            wechat_native_bridge_fixture_smoke_report=(
                _disabled_wechat_native_bridge_fixture_smoke_report()
            ),
            system_dialog_preflight_report=system_dialog_preflight,
            agent_app_devtools_resolution_report={},
            agent_app_devtools_owned_launch_report=(
                _disabled_agent_app_devtools_owned_launch_report()
            ),
            scenario_scope_report=scenario_scope,
            runner_stage_reports=tuple(runner_stages),
            requirements=(),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        return _write_report_artifact(root, report)
    loaded_fixture = (
        fixture
        if fixture is not None
        else (load_simulation_fixture(fixture_path) if run_primary_scenarios else {})
    )

    primary = _disabled_primary_scenario_report()
    if run_primary_scenarios:
        primary = _report_to_dict(
            _run_major_stage(
                "primary",
                runner_timeout_sec=runner_timeout_sec,
                stage_reports=runner_stages,
                output_root=root,
                runner=lambda: (primary_runner or run_primary_real_no_loss)(
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
                    wechat_uia_required_markers=tuple(
                        wechat_uia_required_markers or ()
                    ),
                    wechat_uia_forbidden_markers=tuple(
                        wechat_uia_forbidden_markers or ()
                    ),
                    wechat_native_bridge_urls=tuple(wechat_native_bridge_urls or ()),
                    wechat_native_bridge_registry_paths=tuple(
                        wechat_native_bridge_registry_paths or ()
                    ),
                    allow_wechat_native_bridge_send=allow_wechat_native_bridge_send,
                    wechat_native_bridge_message=wechat_native_bridge_message,
                    wechat_native_bridge_required_markers=tuple(
                        wechat_native_bridge_required_markers or ()
                    ),
                    wechat_native_bridge_forbidden_markers=tuple(
                        wechat_native_bridge_forbidden_markers or ()
                    ),
                    system_dialog_preflight_runner=lambda: dict(
                        system_dialog_preflight
                    ),
                ),
            )
        )
    helper = _disabled_owned_ide_bridge_helper_report()
    native_helper = _disabled_agent_native_cdp_bridge_helper_report()
    bridge_fixture_smoke = _disabled_agent_app_bridge_fixture_smoke_report()
    native_bridge_fixture_smoke = _disabled_agent_native_bridge_fixture_smoke_report()
    wechat_bridge_fixture_smoke = _disabled_wechat_native_bridge_fixture_smoke_report()
    agent_app_devtools_launch = _disabled_agent_app_devtools_owned_launch_report()
    app: dict = {}
    cli: dict = {}
    app_devtools_resolution: dict = {}
    ide_extension_readiness: dict = {}
    if stop_on_runner_timeout and _runner_stage_timed_out(primary):
        app = (
            _skipped_after_runner_timeout_report("agent_app")
            if run_agent_app_scenarios
            else _disabled_agent_app_scenario_report()
        )
        cli = (
            _skipped_after_runner_timeout_report("agent_cli")
            if run_agent_cli_scenarios
            else _disabled_agent_cli_scenario_report()
        )
        report = MajorScenarioRealNoLossReport(
            output_root=str(root),
            artifact_path="",
            primary_report=primary,
            owned_ide_bridge_helper_report=helper,
            agent_native_cdp_bridge_helper_report=native_helper,
            agent_app_report=app,
            agent_app_bridge_fixture_smoke_report=bridge_fixture_smoke,
            agent_cli_report=cli,
            agent_native_bridge_fixture_smoke_report=native_bridge_fixture_smoke,
            wechat_native_bridge_fixture_smoke_report=wechat_bridge_fixture_smoke,
            system_dialog_preflight_report=system_dialog_preflight,
            ide_extension_readiness_report=ide_extension_readiness,
            agent_app_devtools_resolution_report=app_devtools_resolution,
            agent_app_devtools_owned_launch_report=agent_app_devtools_launch,
            scenario_scope_report=scenario_scope,
            runner_stage_reports=tuple(runner_stages),
            requirements=_build_requirements(
                primary,
                app,
                cli,
                cli_agents=tuple(cli_agents),
                include_primary=run_primary_scenarios,
                include_agent_app=run_agent_app_scenarios,
                include_agent_cli=run_agent_cli_scenarios,
            ),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        return _write_report_artifact(root, report)
    if run_agent_app_scenarios:
        app_devtools_resolution = _build_agent_app_devtools_resolution_report(
            tuple(agent_apps),
            resolver=agent_app_devtools_resolver,
        )
    try:
        if run_agent_app_scenarios and allow_owned_ide_bridge_helper_launch:
            helper = _report_to_dict(
                _run_major_stage(
                    "owned_ide_bridge_helper",
                    runner_timeout_sec=runner_timeout_sec,
                    stage_reports=runner_stages,
                    output_root=root,
                    runner=lambda: (
                        owned_ide_bridge_helper_runner or prepare_owned_ide_bridge_helper
                    )(
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
                    ),
                )
            )
        if run_agent_app_scenarios and allow_agent_native_cdp_bridge_helper_launch:
            helper_specs = tuple(agent_native_cdp_bridge_helper_specs or ())
            if helper_specs:
                native_helper = _report_to_dict(
                    _run_major_stage(
                        "agent_native_cdp_bridge_helper",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: prepare_agent_native_cdp_bridge_helper_fleet(
                            output_root=root / "agent-native-cdp-bridge",
                            specs=helper_specs,
                            project_name=project_name,
                            task_name=task_name,
                            registry_wait_timeout_sec=agent_native_cdp_bridge_registry_wait_timeout_sec,
                            helper_runner=(
                                agent_native_cdp_bridge_helper_runner
                                or prepare_agent_native_cdp_bridge_helper
                            ),
                        ),
                    )
                )
            else:
                native_helper = _report_to_dict(
                    _run_major_stage(
                        "agent_native_cdp_bridge_helper",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: (
                            agent_native_cdp_bridge_helper_runner
                            or prepare_agent_native_cdp_bridge_helper
                        )(
                            output_root=root / "agent-native-cdp-bridge",
                            agent=agent_native_cdp_bridge_helper_agent,
                            agent_id=agent_native_cdp_bridge_helper_agent_id,
                            bridge_port=agent_native_cdp_bridge_helper_port,
                            debugger_url=agent_native_cdp_bridge_helper_debugger_url,
                            process_name=agent_native_cdp_bridge_helper_process_name,
                            pid=agent_native_cdp_bridge_helper_pid,
                            hwnd=agent_native_cdp_bridge_helper_hwnd,
                            window_title=agent_native_cdp_bridge_helper_window_title,
                            project_name=project_name,
                            task_name=task_name,
                            target_title=agent_native_cdp_bridge_helper_target_title,
                            target_url=agent_native_cdp_bridge_helper_target_url,
                            registry_wait_timeout_sec=agent_native_cdp_bridge_registry_wait_timeout_sec,
                        ),
                    )
                )
        if run_agent_app_scenarios and (
            allow_agent_app_devtools_owned_launch
            or allow_agent_app_devtools_default_profile_launch
        ):
            agent_app_devtools_launch = _report_to_dict(
                _run_major_stage(
                    "agent_app_devtools_owned_launch",
                    runner_timeout_sec=runner_timeout_sec,
                    stage_reports=runner_stages,
                    output_root=root,
                    runner=lambda: (
                        agent_app_devtools_owned_launch_runner
                        or prepare_agent_app_devtools_owned_launch_fleet
                    )(
                        output_root=root / "agent-app-devtools",
                        resolution_report=app_devtools_resolution,
                        workspace_path=workspace_path,
                        default_profile_agents=(
                            tuple(agent_apps)
                            if allow_agent_app_devtools_default_profile_launch
                            else ()
                        ),
                        endpoint_wait_timeout_sec=agent_app_devtools_endpoint_wait_timeout_sec,
                        request_timeout=agent_app_devtools_request_timeout_sec,
                    ),
                )
            )
        if run_agent_app_scenarios and probe_existing_ide_extension_bridge:
            ide_extension_readiness = _report_to_dict(
                _run_major_stage(
                    "ide_extension_readiness",
                    runner_timeout_sec=runner_timeout_sec,
                    stage_reports=runner_stages,
                    output_root=root,
                    runner=lambda: (
                        ide_extension_readiness_runner
                        or probe_ide_extension_bridge_readiness
                    )(
                        bridge_url=ide_extension_bridge_url,
                        agent_id=ide_extension_agent_id,
                        project_name=project_name,
                        workspace_path=workspace_path,
                        request_timeout=ide_extension_request_timeout_sec,
                    ),
                )
            )
        if run_agent_app_bridge_fixture_smoke:
            bridge_fixture_smoke = {
                "enabled": True,
                **_report_to_dict(
                    _run_major_stage(
                        "agent_app_bridge_fixture_smoke",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: (
                            agent_app_bridge_fixture_smoke_runner
                            or run_default_agent_app_bridge_fixture_smoke
                        )(
                            message=agent_app_bridge_fixture_message,
                            required_markers=tuple(
                                agent_app_bridge_fixture_required_markers or ()
                            ),
                            forbidden_markers=tuple(
                                agent_app_bridge_fixture_forbidden_markers or ()
                            ),
                        ),
                    )
                ),
            }
        if run_agent_native_bridge_fixture_smoke:
            native_bridge_fixture_smoke = {
                "enabled": True,
                **_report_to_dict(
                    _run_major_stage(
                        "agent_native_bridge_fixture_smoke",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: (
                            agent_native_bridge_fixture_smoke_runner
                            or run_default_agent_native_bridge_fixture_smoke
                        )(
                            message=agent_native_bridge_fixture_message,
                            required_markers=tuple(
                                agent_native_bridge_fixture_required_markers or ()
                            ),
                            forbidden_markers=tuple(
                                agent_native_bridge_fixture_forbidden_markers or ()
                            ),
                        ),
                    )
                ),
            }
        if run_wechat_native_bridge_fixture_smoke:
            wechat_bridge_fixture_smoke = {
                "enabled": True,
                **_report_to_dict(
                    _run_major_stage(
                        "wechat_native_bridge_fixture_smoke",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: (
                            wechat_native_bridge_fixture_smoke_runner
                            or run_default_wechat_native_bridge_fixture_smoke
                        )(
                            message=wechat_native_bridge_fixture_message,
                            required_markers=tuple(
                                wechat_native_bridge_fixture_required_markers or ()
                            ),
                            forbidden_markers=tuple(
                                wechat_native_bridge_fixture_forbidden_markers or ()
                            ),
                        ),
                    )
                ),
            }
        if run_agent_app_scenarios:
            effective_ide_bridge_urls = _effective_ide_bridge_urls(
                ide_bridge_urls,
                helper,
                ide_extension_readiness,
            )
            effective_agent_native_bridge_registry_paths = (
                _effective_agent_native_bridge_registry_paths(
                    agent_native_bridge_registry_paths,
                    native_helper,
                )
            )
            effective_workspace_path = workspace_path or str(
                helper.get("workspace_path", "") or ""
            )
            app_agents = tuple(agent_apps)
            app_runner = agent_app_runner or run_agent_app_real_no_loss
            app_common_kwargs = {
                "project_name": project_name,
                "task_name": task_name,
                "screenshot_dir": root / "background-screenshots" / "agent-app",
                "allow_uia_semantic_action": allow_uia_semantic_action,
                "uia_message": uia_message,
                "uia_required_markers": tuple(uia_required_markers or ()),
                "uia_forbidden_markers": tuple(uia_forbidden_markers or ()),
                "allow_app_bridge_send": allow_app_bridge_send,
                "bridge_message": app_bridge_message,
                "required_markers": tuple(app_bridge_required_markers or ()),
                "forbidden_markers": tuple(app_bridge_forbidden_markers or ()),
                "allow_codex_app_server_thread_start": (
                    allow_codex_app_server_thread_start
                ),
                "codex_app_server_thread_start_timeout": (
                    codex_app_server_thread_start_timeout
                ),
                "allow_codex_app_server_turn_start": (
                    allow_codex_app_server_turn_start
                ),
                "codex_app_server_turn_start_timeout": (
                    codex_app_server_turn_start_timeout
                ),
                "debugger_urls": tuple(debugger_urls or ()),
                "debugger_urls_by_agent": _agent_app_devtools_debugger_urls_by_agent(
                    agent_app_devtools_launch
                ),
                "ide_bridge_urls": effective_ide_bridge_urls,
                "agent_native_bridge_urls": tuple(agent_native_bridge_urls or ()),
                "agent_native_bridge_registry_paths": (
                    effective_agent_native_bridge_registry_paths
                ),
                "codex_app_server_ws_urls": tuple(codex_app_server_ws_urls or ()),
                "workspace_path": effective_workspace_path,
                "process_provider": _combined_agent_app_process_provider(
                    agent_app_process_provider,
                    agent_app_devtools_launch,
                ),
                "request_timeout": agent_app_devtools_request_timeout_sec,
            }
            if isolate_agent_app_scenarios and len(app_agents) > 1:
                app = _merge_agent_runner_reports(
                    [
                        _report_to_dict(
                            _run_major_stage(
                                f"agent_app:{agent}",
                                runner_timeout_sec=runner_timeout_sec,
                                stage_reports=runner_stages,
                                output_root=root,
                                runner=lambda agent=agent: app_runner(
                                    agents=(agent,),
                                    output_root=root / "agent-app" / _safe_stage_id(agent),
                                    **app_common_kwargs,
                                ),
                            )
                        )
                        for agent in app_agents
                    ],
                    mode="agent-app-real-no-loss",
                    safety_mode="real_no_loss",
                )
            else:
                app = _report_to_dict(
                    _run_major_stage(
                        "agent_app",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: app_runner(
                            agents=app_agents,
                            output_root=root / "agent-app",
                            **app_common_kwargs,
                        ),
                    )
                )
        else:
            app = _disabled_agent_app_scenario_report()
        if run_agent_cli_scenarios:
            cli_agents_tuple = tuple(cli_agents)
            cli_runner = agent_cli_runner or run_agent_cli_real_no_loss
            if isolate_agent_cli_scenarios and len(cli_agents_tuple) > 1:
                cli = _merge_agent_runner_reports(
                    [
                        _report_to_dict(
                            _run_major_stage(
                                f"agent_cli:{agent}",
                                runner_timeout_sec=runner_timeout_sec,
                                stage_reports=runner_stages,
                                output_root=root,
                                runner=lambda agent=agent: cli_runner(
                                    agents=(agent,),
                                    output_root=root / "agent-cli" / _safe_stage_id(agent),
                                    allow_cli_execution=allow_agent_cli_execution,
                                    timeout_sec=agent_cli_timeout_sec,
                                ),
                            )
                        )
                        for agent in cli_agents_tuple
                    ],
                    mode="agent-cli-real-no-loss",
                    safety_mode="real_no_loss",
                )
            else:
                cli = _report_to_dict(
                    _run_major_stage(
                        "agent_cli",
                        runner_timeout_sec=runner_timeout_sec,
                        stage_reports=runner_stages,
                        output_root=root,
                        runner=lambda: cli_runner(
                            agents=cli_agents_tuple,
                            output_root=root / "agent-cli",
                            allow_cli_execution=allow_agent_cli_execution,
                            timeout_sec=agent_cli_timeout_sec,
                        ),
                    )
                )
        else:
            cli = _disabled_agent_cli_scenario_report()
    finally:
        native_helper = _stop_agent_native_cdp_bridge_helper_if_needed(native_helper)
        agent_app_devtools_launch = _stop_agent_app_devtools_owned_launch_if_needed(
            agent_app_devtools_launch
        )
        helper = _stop_owned_ide_bridge_helper_if_needed(helper)

    report = MajorScenarioRealNoLossReport(
        output_root=str(root),
        artifact_path="",
        primary_report=primary,
        owned_ide_bridge_helper_report=helper,
        agent_native_cdp_bridge_helper_report=native_helper,
        agent_app_report=app,
        agent_app_bridge_fixture_smoke_report=bridge_fixture_smoke,
        agent_cli_report=cli,
        agent_native_bridge_fixture_smoke_report=native_bridge_fixture_smoke,
        wechat_native_bridge_fixture_smoke_report=wechat_bridge_fixture_smoke,
        system_dialog_preflight_report=system_dialog_preflight,
        ide_extension_readiness_report=ide_extension_readiness,
        agent_app_devtools_resolution_report=app_devtools_resolution,
        agent_app_devtools_owned_launch_report=agent_app_devtools_launch,
        scenario_scope_report=scenario_scope,
        runner_stage_reports=tuple(runner_stages),
        requirements=_build_requirements(
            primary,
            app,
            cli,
            cli_agents=tuple(cli_agents),
            include_primary=run_primary_scenarios,
            include_agent_app=run_agent_app_scenarios,
            include_agent_cli=run_agent_cli_scenarios,
        ),
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
            "Scenario scope: "
            f"primary={str(report.scenario_scope_report.get('primary_scenarios_enabled', True)).lower()}  "
            f"agent_app={str(report.scenario_scope_report.get('agent_app_scenarios_enabled', True)).lower()}  "
            f"agent_cli={str(report.scenario_scope_report.get('agent_cli_scenarios_enabled', True)).lower()}"
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
        (
            f"Agent app DevTools: launches={report.agent_app_devtools_launch_attempts}  "
            f"stops={report.agent_app_devtools_stop_attempts}  "
            f"cleanup={str(report.agent_app_devtools_cleanup_ok).lower()}"
        ),
        (
            "Agent app bridge fixture: "
            f"enabled={str(report.agent_app_bridge_fixture_smoke_enabled).lower()}  "
            f"ok={str(report.agent_app_bridge_fixture_smoke_ok).lower()}  "
            f"native calls={report.agent_app_bridge_fixture_native_call_attempts}"
        ),
        (
            "Agent native bridge fixture: "
            f"enabled={str(report.agent_native_bridge_fixture_smoke_enabled).lower()}  "
            f"ok={str(report.agent_native_bridge_fixture_smoke_ok).lower()}  "
            f"native calls={report.agent_native_bridge_fixture_native_call_attempts}"
        ),
        (
            "WeChat native bridge fixture: "
            f"enabled={str(report.wechat_native_bridge_fixture_smoke_enabled).lower()}  "
            f"ok={str(report.wechat_native_bridge_fixture_smoke_ok).lower()}  "
            f"native calls={report.wechat_native_bridge_fixture_native_call_attempts}"
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


def _build_requirements(
    primary: dict,
    app: dict,
    cli: dict,
    cli_agents: Iterable[str] = DEFAULT_CLI_AGENTS,
    *,
    include_primary: bool = True,
    include_agent_app: bool = True,
    include_agent_cli: bool = True,
) -> tuple[MajorRequirement, ...]:
    primary_cases = _cases_by_key(primary, "scenario_id")
    app_cases = _cases_by_key(app, "agent")
    cli_cases = _cases_by_key(cli, "agent")
    requirements: list[MajorRequirement] = []
    if include_primary:
        requirements.extend(
            [
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
            ]
        )
    if include_agent_cli:
        for agent_id in _selected_cli_requirement_agent_ids(cli_agents):
            requirement_id, surface = CLI_REQUIREMENT_SPECS[agent_id]
            requirements.append(
                _cli_requirement(
                    requirement_id,
                    surface,
                    cli_cases.get(agent_id, {}),
                )
            )
    if include_agent_app:
        requirements.extend(
            [
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
                    app_cases.get("cursor", _protected_cursor_desktop_case()),
                ),
            ]
        )
    return tuple(requirements)


def _selected_cli_requirement_agent_ids(cli_agents: Iterable[str]) -> tuple[str, ...]:
    selected = {
        agent_id
        for agent in cli_agents
        for agent_id in (_cli_requirement_agent_id(agent),)
        if agent_id
    }
    return tuple(agent_id for agent_id in CLI_REQUIREMENT_SPECS if agent_id in selected)


def _cli_requirement_agent_id(agent: str) -> str:
    normalized = str(agent or "").strip().lower().replace("_", " ").replace("-", " ")
    normalized = " ".join(normalized.split())
    if normalized in {"codex", "codex cli", "openai codex"}:
        return "codex"
    if normalized in {"claude", "claude cli", "claude code", "anthropic claude"}:
        return "claude"
    if normalized in {"cursor", "cursor agent", "cursor cli"}:
        return "cursor"
    return ""


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
    elif raw_status == "auth_required":
        status = "auth_required"
        reason = raw_status
    elif raw_status.startswith("gated_") or bool(case.get("native_ready", False)):
        status = "gated"
        native_ready = bool(case.get("native_ready", False))
        reason = (
            "native_connector_ready_but_send_not_verified"
            if native_ready or raw_status == "native_connector_ready"
            else raw_status or "native_ready_send_not_verified"
        )
    elif raw_status == "app_installed_not_running_connector_required":
        status = "gated"
        reason = raw_status
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


def _protected_cursor_desktop_case() -> dict:
    return {
        "agent": "cursor",
        "status": "gated_cursor_desktop_protected_explicit_bridge_required",
        "real_verified": False,
        "native_ready": False,
        "protected_default": True,
        "protection_reason": "active_cursor_desktop_protected",
        "required_endpoint_kind": "explicit_ide_bridge_or_isolated_cursor_profile",
        "next_action": "provide_explicit_bridge_url_or_run_isolated_cursor_profile",
    }


def _build_agent_app_endpoint_acceptance(
    app_report: dict,
    native_helper_report: dict,
    app_devtools_resolution_report: dict | None = None,
    app_devtools_launch_report: dict | None = None,
    output_root: str | Path = "",
) -> dict:
    cases = [
        _build_agent_app_endpoint_acceptance_case(
            case,
            native_helper_report,
            app_devtools_resolution_report or {},
            app_devtools_launch_report or {},
            output_root=output_root,
        )
        for case in app_report.get("cases", []) or []
        if isinstance(case, dict)
    ]
    safe_to_send_now = bool(cases) and all(
        bool(case.get("safe_to_send_now", False)) for case in cases
    )
    return {
        "mode": "agent-app-endpoint-acceptance",
        "safety_mode": "real_no_loss",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "no_focus_required": True,
        "safe_to_send_now": safe_to_send_now,
        "total_cases": len(cases),
        "ready_endpoint_cases": sum(
            1 for case in cases if bool(case.get("endpoint_ready", False))
        ),
        "send_verified_cases": sum(
            1 for case in cases if bool(case.get("send_verified", False))
        ),
        "cases": cases,
    }


def _build_agent_app_endpoint_readiness(
    app_report: dict,
    endpoint_acceptance_report: dict,
    ide_extension_readiness_report: dict | None = None,
) -> dict:
    acceptance_cases = [
        dict(case)
        for case in endpoint_acceptance_report.get("cases", []) or []
        if isinstance(case, dict)
    ]
    app_cases = _cases_by_key(app_report, "agent")
    cases = [
        _build_agent_app_endpoint_readiness_case(
            acceptance_case,
            app_cases.get(str(acceptance_case.get("agent", "") or "").strip(), {}),
            ide_extension_readiness_report or {},
        )
        for acceptance_case in acceptance_cases
    ]
    return {
        "mode": "agent-app-endpoint-readiness",
        "safety_mode": "read_only",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "total_cases": len(cases),
        "observed_endpoint_cases": sum(
            1 for case in cases if int(case.get("observed_endpoint_count", 0) or 0) > 0
        ),
        "ready_endpoint_cases": sum(
            1 for case in cases if bool(case.get("endpoint_ready", False))
        ),
        "background_send_contract_candidate_cases": sum(
            1
            for case in cases
            if bool(case.get("can_prepare_background_send_contract", False))
        ),
        "send_verified_cases": sum(
            1 for case in cases if bool(case.get("send_verified", False))
        ),
        "blocked_cases": sum(
            1 for case in cases if not bool(case.get("endpoint_ready", False))
        ),
        "ready_endpoint_type_counts": _count_case_values(cases, "ready_endpoint_type"),
        "blocking_reason_counts": _count_case_values(cases, "blocking_reason"),
        "cases": cases,
    }


def _build_agent_app_endpoint_readiness_case(
    acceptance_case: dict,
    app_case: dict,
    ide_extension_readiness_report: dict,
) -> dict:
    endpoints = [
        dict(endpoint)
        for endpoint in acceptance_case.get("observed_endpoints", []) or []
        if isinstance(endpoint, dict)
    ]
    ready_endpoint = _first_ready_endpoint(endpoints)
    agent = str(acceptance_case.get("agent", "") or "").strip()
    agent_id = str(acceptance_case.get("agent_id", "") or "").strip()
    endpoint_ready = bool(acceptance_case.get("endpoint_ready", False))
    send_verified = bool(acceptance_case.get("send_verified", False))
    supplemental = _matching_ide_extension_readiness(
        ide_extension_readiness_report,
        agent_id=agent_id,
    )
    blocking_reason = str(acceptance_case.get("blocking_reason", "") or "").strip()
    if not endpoint_ready and supplemental and supplemental.get("blocking_reason"):
        blocking_reason = str(supplemental.get("blocking_reason", "") or blocking_reason)
    codex_app_server_turn_dry_run = _details(
        app_case.get("codex_app_server_turn_dry_run", {})
    )
    codex_app_server_turn_contract_ready = bool(
        app_case.get("codex_app_server_turn_contract_ready", False)
        or codex_app_server_turn_dry_run.get("ok", False)
    )
    codex_app_server_thread_start_required = bool(
        app_case.get("codex_app_server_thread_start_required", False)
        or codex_app_server_turn_dry_run.get("thread_start_required", False)
    )
    codex_app_server_thread_start_ready = bool(
        app_case.get("codex_app_server_thread_start_ready", False)
        or codex_app_server_turn_dry_run.get("thread_start_ready", False)
    )
    codex_app_server_turn_start_ready = bool(
        app_case.get("codex_app_server_turn_start_ready", False)
        or codex_app_server_turn_dry_run.get("turn_start_ready", False)
    )
    return {
        "agent": agent,
        "agent_id": agent_id,
        "status": str(acceptance_case.get("status", "") or "").strip(),
        "endpoint_ready": endpoint_ready,
        "send_verified": send_verified,
        "can_prepare_background_send_contract": bool(endpoint_ready and not send_verified),
        "codex_app_server_turn_contract_ready": codex_app_server_turn_contract_ready,
        "codex_app_server_thread_start_required": codex_app_server_thread_start_required,
        "codex_app_server_thread_start_ready": codex_app_server_thread_start_ready,
        "codex_app_server_turn_start_ready": codex_app_server_turn_start_ready,
        "codex_app_server_turn_dry_run": codex_app_server_turn_dry_run,
        "observed_endpoint_count": int(
            acceptance_case.get("observed_endpoint_count", 0) or 0
        ),
        "ready_endpoint_count": int(acceptance_case.get("ready_endpoint_count", 0) or 0),
        "observed_endpoint_types": _endpoint_types(endpoints),
        "observed_endpoint_errors": list(
            acceptance_case.get("observed_endpoint_errors", []) or []
        ),
        "ready_endpoint_type": str(ready_endpoint.get("endpoint_type", "") or ""),
        "ready_endpoint_url": _endpoint_url(ready_endpoint),
        "ready_endpoint_source": str(ready_endpoint.get("source", "") or ""),
        "required_endpoint_kind": str(
            acceptance_case.get("required_endpoint_kind", "") or ""
        ),
        "next_action": str(acceptance_case.get("next_action", "") or ""),
        "blocking_reason": blocking_reason,
        "no_focus_required": bool(acceptance_case.get("no_focus_required", True)),
        "native_ready": bool(app_case.get("native_ready", False)),
        "real_verified": bool(app_case.get("real_verified", False)),
        "app_status": str(app_case.get("status", "") or ""),
        "existing_ide_extension_readiness": supplemental,
        "helper_status": dict(acceptance_case.get("helper_status", {}) or {}),
        "helper_spec_template": dict(acceptance_case.get("helper_spec_template", {}) or {}),
        "owned_devtools_launch_plan_template": dict(
            acceptance_case.get("owned_devtools_launch_plan_template", {}) or {}
        ),
    }


def _build_agent_app_endpoint_acceptance_case(
    case: dict,
    native_helper_report: dict,
    app_devtools_resolution_report: dict,
    app_devtools_launch_report: dict,
    *,
    output_root: str | Path = "",
) -> dict:
    agent = str(case.get("agent", "") or "").strip()
    defaults = _agent_app_endpoint_defaults(agent)
    agent_id = str(
        case.get("agent_id", "")
        or _details(case.get("probe", {})).get("agent_id", "")
        or defaults["agent_id"]
    ).strip()
    status = str(case.get("status", "") or "").strip()
    probe = _details(case.get("probe", {}))
    endpoints = [
        dict(endpoint)
        for endpoint in probe.get("endpoints", []) or []
        if isinstance(endpoint, dict)
    ]
    ready_endpoint_count = _counter(probe, "ready_endpoint_count")
    if ready_endpoint_count <= 0:
        ready_endpoint_count = sum(
            1 for endpoint in endpoints if bool(endpoint.get("ready", False))
        )
    endpoint_ready = bool(case.get("native_ready", False)) or ready_endpoint_count > 0
    send_verified = bool(
        case.get("app_bridge_send_verified", False)
        or case.get("uia_semantic_action_send_verified", False)
        or status
        in {
            "app_bridge_send_accepted",
            "uia_semantic_action_send_accepted",
            "message_submitted_accepted",
        }
    )
    helper_status = _agent_native_helper_status(native_helper_report, agent, agent_id)
    devtools_resolution = _agent_app_devtools_resolution_status(
        app_devtools_resolution_report,
        agent=agent,
        agent_id=agent_id,
    )
    devtools_launch_helper = _agent_app_devtools_launch_helper_status(
        app_devtools_launch_report,
        agent=agent,
        agent_id=agent_id,
    )
    return {
        "agent": agent,
        "agent_id": agent_id,
        "status": status,
        "native_ready": bool(case.get("native_ready", False)),
        "endpoint_ready": endpoint_ready,
        "send_verified": send_verified,
        "safe_to_send_now": send_verified,
        "required_endpoint_kind": _agent_app_required_endpoint_kind(
            case,
            endpoint_ready=endpoint_ready,
            send_verified=send_verified,
        ),
        "next_action": _agent_app_endpoint_next_action(
            case,
            endpoint_ready=endpoint_ready,
            send_verified=send_verified,
        ),
        "blocking_reason": _agent_app_endpoint_blocking_reason(
            case,
            endpoint_ready=endpoint_ready,
            send_verified=send_verified,
        ),
        "no_focus_required": True,
        "observed_endpoint_count": max(_counter(probe, "endpoint_count"), len(endpoints)),
        "ready_endpoint_count": ready_endpoint_count,
        "observed_endpoint_errors": _observed_endpoint_errors(endpoints),
        "observed_endpoints": endpoints,
        "helper_spec_template": {
            "agent": agent or defaults["agent"],
            "agent_id": agent_id or defaults["agent_id"],
            "bridge_port": defaults["bridge_port"],
            "debugger_url": "<required-owned-local-devtools-url>",
            "process_name": defaults["process_name"],
            "pid": 0,
            "hwnd": 0,
            "window_title": "",
            "target_title": "",
            "target_url": "",
        },
        "owned_devtools_launch_plan_template": _owned_devtools_launch_plan_template(
            agent=agent or defaults["agent"],
            agent_id=agent_id or defaults["agent_id"],
            defaults=defaults,
            resolution=devtools_resolution,
            launch_helper=devtools_launch_helper,
            output_root=output_root,
        ),
        "helper_status": helper_status,
    }


def _build_agent_app_devtools_resolution_report(
    agents: Iterable[str],
    *,
    resolver: AgentAppDevToolsResolver | None = None,
) -> dict:
    cases = [
        _build_agent_app_devtools_resolution_case(agent, resolver=resolver)
        for agent in agents or ()
        if str(agent or "").strip()
    ]
    return {
        "mode": "agent-app-devtools-resolution",
        "safety_mode": "read_only",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "total_cases": len(cases),
        "resolved_cases": sum(1 for case in cases if case.get("status") == "resolved"),
        "executable_ready_cases": sum(
            1 for case in cases if bool(case.get("executable_ready", False))
        ),
        "cases": cases,
    }


def _build_agent_app_devtools_resolution_case(
    agent: str,
    *,
    resolver: AgentAppDevToolsResolver | None,
) -> dict:
    defaults = _agent_app_endpoint_defaults(agent)
    active_resolver = resolver or WindowsAppResolver()
    try:
        resolve = getattr(active_resolver, "resolve", None)
        raw_resolution = resolve(agent) if callable(resolve) else active_resolver(agent)
        resolution = _report_to_dict(raw_resolution)
    except Exception as exc:
        resolution = {
            "mode": "app-resolution",
            "ok": False,
            "decision": "resolution_failed",
            "error": str(exc) or exc.__class__.__name__,
        }
    executable_path, launch_blocking_reason = _launchable_agent_app_executable(
        resolution,
        agent=agent,
        agent_id=defaults["agent_id"],
    )
    if executable_path:
        status = "resolved"
    elif bool(resolution.get("ok", False)):
        status = "resolved_no_executable_path"
    else:
        status = str(
            resolution.get("error", "") or resolution.get("decision", "") or "not_found"
        )
    return {
        "agent": str(agent or "").strip() or defaults["agent"],
        "agent_id": defaults["agent_id"],
        "status": status,
        "executable_ready": bool(executable_path),
        "executable_path": executable_path,
        "launch_blocking_reason": launch_blocking_reason,
        "app_resolution": resolution,
    }


def _launchable_agent_app_executable(
    resolution: dict,
    *,
    agent: str,
    agent_id: str,
) -> tuple[str, str]:
    blocking_reason = ""
    path = str(resolution.get("path", "") or "").strip()
    source = str(resolution.get("source", "") or "").strip()
    selected_path, selected_blocking = _launchable_agent_app_candidate_path(
        {
            "path": path,
            "source": source,
            "display_name": resolution.get("app_name", "") or agent,
            "executable_name": Path(path).name if path else "",
        },
        agent=agent,
        agent_id=agent_id,
    )
    if selected_path:
        return selected_path, ""
    blocking_reason = blocking_reason or selected_blocking
    selected = resolution.get("selected_candidate", {})
    if isinstance(selected, dict):
        selected_candidate_path, selected_candidate_blocking = (
            _launchable_agent_app_candidate_path(
                selected,
                agent=agent,
                agent_id=agent_id,
            )
        )
        if selected_candidate_path:
            return selected_candidate_path, ""
        blocking_reason = blocking_reason or selected_candidate_blocking
    for candidate in resolution.get("candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        candidate_path, candidate_blocking = _launchable_agent_app_candidate_path(
            candidate,
            agent=agent,
            agent_id=agent_id,
        )
        if candidate_path:
            return candidate_path, ""
        blocking_reason = blocking_reason or candidate_blocking
    return "", blocking_reason


def _launchable_agent_app_candidate_path(
    candidate: dict,
    *,
    agent: str,
    agent_id: str,
) -> tuple[str, str]:
    path = str(candidate.get("path", "") or "").strip()
    source = str(candidate.get("source", "") or "").strip()
    if not path or source == "start-apps":
        return "", ""
    blocking_reason = _agent_app_launch_blocking_reason(
        candidate,
        agent=agent,
        agent_id=agent_id,
    )
    if blocking_reason:
        return "", blocking_reason
    if _is_windowsapps_msix_path(path):
        return "", "msix_windowsapps_not_background_launchable"
    if Path(path).suffix.lower() != ".exe":
        return "", ""
    return path, ""


def _agent_app_launch_blocking_reason(
    candidate: dict,
    *,
    agent: str,
    agent_id: str,
) -> str:
    path = str(candidate.get("path", "") or "").strip()
    if not path:
        return ""
    surface = _agent_app_candidate_surface_kind(candidate, agent=agent, agent_id=agent_id)
    if surface == "cli":
        return "agent_app_cli_path_not_background_launchable"
    if _is_windowsapps_msix_path(path):
        return "msix_windowsapps_not_background_launchable"
    return ""


def _agent_app_candidate_surface_kind(
    candidate: dict,
    *,
    agent: str,
    agent_id: str,
) -> str:
    path = str(candidate.get("path", "") or "").strip()
    app_candidate = AppResolutionCandidate(
        source=str(candidate.get("source", "") or "").strip() or "path",
        display_name=str(candidate.get("display_name", "") or agent or "").strip(),
        path=path,
        executable_name=str(
            candidate.get("executable_name", "")
            or (Path(path).name if path else "")
        ).strip(),
        process_name=str(candidate.get("process_name", "") or "").strip(),
        pid=_counter(candidate, "pid"),
        metadata=dict(candidate.get("metadata", {}) or {}),
    )
    normalized_agent_id = str(agent_id or "").strip().lower()
    if normalized_agent_id == "claude":
        return claude_candidate_surface_kind(app_candidate)
    if normalized_agent_id == "codex":
        return codex_candidate_surface_kind(app_candidate)
    if normalized_agent_id == "cursor":
        return cursor_candidate_surface_kind(app_candidate)
    return ""


def _agent_app_devtools_resolution_status(
    report: dict,
    *,
    agent: str,
    agent_id: str,
) -> dict:
    for item in report.get("cases", []) or []:
        if not isinstance(item, dict):
            continue
        item_agent_id = str(item.get("agent_id", "") or "").strip().lower()
        item_agent = str(item.get("agent", "") or "").strip().lower()
        requested_agent_id = str(agent_id or "").strip().lower()
        requested_agent = str(agent or "").strip().lower()
        if item_agent_id == requested_agent_id or item_agent == requested_agent:
            return dict(item)
    return {}


def _agent_app_devtools_launch_helper_status(
    report: dict,
    *,
    agent: str,
    agent_id: str,
) -> dict:
    for item in report.get("helpers", []) or []:
        if not isinstance(item, dict):
            continue
        item_agent_id = str(item.get("agent_id", "") or "").strip().lower()
        item_agent = str(item.get("agent", "") or "").strip().lower()
        if item_agent_id == str(agent_id or "").strip().lower() or item_agent == str(agent or "").strip().lower():
            return dict(item)
    return {}


def _agent_app_endpoint_defaults(agent: str) -> dict:
    key = str(agent or "").strip().lower()
    if key.startswith("claude"):
        return {
            "agent": "claude desktop",
            "agent_id": "claude",
            "process_name": "Claude.exe",
            "bridge_port": 0,
            "devtools_port": 0,
        }
    if key.startswith("cursor"):
        return {
            "agent": "cursor",
            "agent_id": "cursor",
            "process_name": "Cursor.exe",
            "bridge_port": 0,
            "devtools_port": 0,
        }
    return {
        "agent": "codex app",
        "agent_id": "codex",
        "process_name": "Codex.exe",
        "bridge_port": 0,
        "devtools_port": 0,
    }


def _agent_app_accepts_workspace_argument(agent: str) -> bool:
    key = str(agent or "").strip().lower()
    return key.startswith("cursor") or key in {"vscode", "vs code", "code"}


def _owned_devtools_launch_plan_template(
    *,
    agent: str,
    agent_id: str,
    defaults: dict,
    resolution: dict | None = None,
    launch_helper: dict | None = None,
    output_root: str | Path = "",
) -> dict:
    helper = dict(launch_helper or {})
    port = int(helper.get("debug_port") or defaults.get("devtools_port", 0) or 0)
    process_name = str(defaults.get("process_name", "") or "").strip()
    uses_default_profile = bool(helper.get("uses_default_profile", False)) or str(
        helper.get("profile_mode", "") or ""
    ).strip().lower() == "default-user-profile"
    profile_mode = str(
        helper.get("profile_mode", "")
        or ("default-user-profile" if uses_default_profile else "isolated-owned-profile")
    )
    fallback_user_data_dir = _owned_devtools_template_user_data_dir(
        output_root,
        agent_id=agent_id,
    )
    user_data_dir = (
        ""
        if uses_default_profile
        else _normalized_optional_owned_path(
            helper.get("user_data_dir", "") or fallback_user_data_dir
        )
    )
    resolved = dict(resolution or {})
    executable = str(
        helper.get("executable_path", "") or resolved.get("executable_path", "") or ""
    ).strip()
    launch_blocking_reason = str(
        helper.get("launch_blocking_reason", "")
        or resolved.get("launch_blocking_reason", "")
        or ""
    ).strip()
    if executable and not launch_blocking_reason:
        launch_blocking_reason = _agent_app_launch_blocking_reason(
            {
                "path": executable,
                "source": resolved.get("source", "") or "path",
                "display_name": agent,
                "executable_name": Path(executable).name,
            },
            agent=agent,
            agent_id=agent_id,
        )
    executable_ready = bool(
        executable
        and not launch_blocking_reason
        and (bool(helper) or bool(resolved.get("executable_ready", False)))
    )
    if not executable:
        executable = f"<path-to-{process_name or 'agent-app.exe'}>"
    readiness_url = str(
        helper.get("debugger_url", "")
        or ("" if port == 0 else f"http://127.0.0.1:{port}")
    )
    argv: list[str] = []
    if not launch_blocking_reason:
        argv = [
            executable,
            f"--remote-debugging-port={port}",
        ]
        if user_data_dir:
            argv.append(f"--user-data-dir={user_data_dir}")
        argv.extend(
            [
                "--no-first-run",
                "--disable-crash-reporter",
            ]
        )
    workspace_path = str(helper.get("workspace_path", "") or "").strip()
    if (
        workspace_path
        and argv
        and _agent_app_accepts_workspace_argument(agent_id or agent)
    ):
        argv.append(workspace_path)
    return {
        "route_id": "agent-app-devtools-owned",
        "agent": agent,
        "agent_id": agent_id,
        "executable": executable,
        "executable_ready": executable_ready,
        "executable_resolution_status": str(resolved.get("status", "") or "not_resolved"),
        "launch_blocking_reason": launch_blocking_reason,
        "debug_port": port,
        "profile_mode": profile_mode,
        "uses_default_profile": uses_default_profile,
        "user_data_dir": user_data_dir,
        "readiness_url": readiness_url,
        "startup_mode": "minimized_no_activate",
        "workspace_path": workspace_path,
        "argv": argv,
    }


def _owned_devtools_template_user_data_dir(
    output_root: str | Path,
    *,
    agent_id: str,
) -> str:
    root = _normalized_optional_owned_path(output_root)
    if not root:
        root = _normalized_optional_owned_path(Path("logs") / "runtime")
    return str(
        Path(root)
        / "agent-app-devtools"
        / _safe_stage_id(agent_id or "agent")
        / "profile"
    )


def _normalized_optional_owned_path(path: str | Path) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return str(Path(text).expanduser().resolve())


def _is_windowsapps_msix_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/").casefold()
    return "/program files/windowsapps/" in normalized


def _agent_app_required_endpoint_kind(
    case: dict,
    *,
    endpoint_ready: bool,
    send_verified: bool,
) -> str:
    status = str(case.get("status", "") or "").strip()
    if send_verified:
        return "verified_app_bridge_or_uia_semantic_send"
    if endpoint_ready:
        return "ready_endpoint_send_acceptance"
    if status == "unavailable":
        return "app_surface_visibility_or_native_bridge"
    return "owned_local_devtools_or_agent_native_bridge"


def _agent_app_endpoint_next_action(
    case: dict,
    *,
    endpoint_ready: bool,
    send_verified: bool,
) -> str:
    status = str(case.get("status", "") or "").strip()
    if send_verified:
        return "none"
    if endpoint_ready:
        return "run_app_bridge_send_acceptance"
    if status == "unavailable":
        return "open_or_install_app_surface"
    return "provide_owned_debugger_url_or_install_agent_native_bridge"


def _agent_app_endpoint_blocking_reason(
    case: dict,
    *,
    endpoint_ready: bool,
    send_verified: bool,
) -> str:
    if send_verified:
        return ""
    status = str(case.get("status", "") or "").strip()
    if endpoint_ready:
        return "native_connector_ready_but_send_not_verified"
    return status or "agent_app_endpoint_not_ready"


def _observed_endpoint_errors(endpoints: list[dict]) -> list[str]:
    errors: list[str] = []
    for endpoint in endpoints:
        error = str(endpoint.get("error", "") or "").strip()
        if error and error not in errors:
            errors.append(error)
    return errors


def _first_ready_endpoint(endpoints: list[dict]) -> dict:
    for endpoint in endpoints:
        if bool(endpoint.get("ready", False)):
            return dict(endpoint)
    return {}


def _endpoint_types(endpoints: list[dict]) -> list[str]:
    values: list[str] = []
    for endpoint in endpoints:
        value = str(endpoint.get("endpoint_type", "") or "devtools").strip()
        if value and value not in values:
            values.append(value)
    return values


def _endpoint_url(endpoint: dict) -> str:
    if not endpoint:
        return ""
    if str(endpoint.get("endpoint_type", "") or "").strip() in {
        "agent_native_bridge",
        "ide_bridge",
    }:
        return str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or "")
    return str(endpoint.get("debugger_url", "") or endpoint.get("bridge_url", "") or "")


def _matching_ide_extension_readiness(
    report: dict,
    *,
    agent_id: str,
) -> dict:
    if not report:
        return {}
    expected = str(agent_id or "").strip().lower()
    actual = str(report.get("agent_id", "") or "").strip().lower()
    if not expected or actual != expected:
        return {}
    return {
        "status": str(report.get("status", "") or ""),
        "blocking_reason": str(report.get("blocking_reason", "") or ""),
        "bridge_url": str(report.get("bridge_url", "") or ""),
        "bridge_ready": bool(report.get("bridge_ready", False)),
        "can_execute_without_focus": bool(
            report.get("can_execute_without_focus", False)
        ),
        "can_write_without_focus": bool(report.get("can_write_without_focus", False)),
    }


def _count_case_values(cases: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        value = str(case.get(key, "") or "").strip() or "none"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _agent_native_helper_status(
    helper_report: dict,
    agent: str,
    agent_id: str,
) -> dict:
    helper = _matching_agent_native_helper(helper_report, agent, agent_id)
    if not helper:
        return {}
    result: dict = {}
    for key in (
        "agent",
        "agent_id",
        "ready",
        "bridge_url",
        "registry_path",
        "manifest_path",
        "launch_attempts",
        "stop_attempts",
        "cleanup_ok",
        "error",
    ):
        if key in helper:
            result[key] = helper[key]
    return result


def _matching_agent_native_helper(
    helper_report: dict,
    agent: str,
    agent_id: str,
) -> dict:
    helpers = helper_report.get("helpers")
    if isinstance(helpers, list):
        for helper in helpers:
            if not isinstance(helper, dict):
                continue
            if _agent_native_helper_matches(helper, agent, agent_id):
                return dict(helper)
    if _agent_native_helper_matches(helper_report, agent, agent_id):
        return dict(helper_report)
    return {}


def _agent_native_helper_matches(helper: dict, agent: str, agent_id: str) -> bool:
    expected_id = str(agent_id or "").strip().lower()
    expected_agent = str(agent or "").strip().lower()
    helper_id = str(helper.get("agent_id", "") or "").strip().lower()
    helper_agent = str(helper.get("agent", "") or "").strip().lower()
    return bool(
        (expected_id and helper_id == expected_id)
        or (expected_agent and helper_agent == expected_agent)
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
        "protected_default",
        "protection_reason",
        "required_endpoint_kind",
        "next_action",
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


@dataclasses.dataclass(frozen=True)
class AgentNativeCdpBridgeHelperReport:
    enabled: bool
    output_root: str
    agent: str = "codex app"
    agent_id: str = "codex"
    bridge_url: str = ""
    registry_path: str = ""
    manifest_path: str = ""
    ready: bool = False
    cleanup_ok: bool = True
    launch_report: dict = dataclasses.field(default_factory=dict)
    stop_report: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-native-cdp-bridge-helper"

    @property
    def safety_mode(self) -> str:
        return "managed_background_helper_launch"

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
            "agent": self.agent,
            "agent_id": self.agent_id,
            "bridge_url": self.bridge_url,
            "registry_path": self.registry_path,
            "manifest_path": self.manifest_path,
            "launch_attempts": self.launch_attempts,
            "stop_attempts": self.stop_attempts,
            "launch_report": dict(self.launch_report),
            "stop_report": dict(self.stop_report),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class AgentAppDevToolsOwnedLaunchReport:
    enabled: bool
    output_root: str
    helpers: tuple[dict, ...] = ()
    ready: bool = False
    cleanup_ok: bool = True
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-devtools-owned-launch-fleet"

    @property
    def safety_mode(self) -> str:
        return "managed_background_helper_launch"

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
        return sum(_counter(helper, "launch_attempts") for helper in self.helpers)

    @property
    def stop_attempts(self) -> int:
        return sum(_counter(helper, "stop_attempts") for helper in self.helpers)

    @property
    def healthy_endpoint_count(self) -> int:
        return sum(
            1
            for helper in self.helpers
            if bool(_details(helper.get("endpoint_health")).get("ready", False))
        )

    @property
    def debugger_urls(self) -> tuple[str, ...]:
        urls: list[str] = []
        for helper in self.helpers:
            if not bool(helper.get("ready", False)):
                continue
            url = str(helper.get("debugger_url", "") or "").strip()
            if url and url not in urls:
                urls.append(url)
        return tuple(urls)

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
            "output_root": self.output_root,
            "helper_count": len(self.helpers),
            "launch_attempts": self.launch_attempts,
            "stop_attempts": self.stop_attempts,
            "healthy_endpoint_count": self.healthy_endpoint_count,
            "debugger_urls": list(self.debugger_urls),
            "helpers": [dict(helper) for helper in self.helpers],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def prepare_agent_app_devtools_owned_launch_fleet(
    *,
    output_root: str | Path,
    resolution_report: dict,
    workspace_path: str = "",
    default_profile_agents: Iterable[str] = (),
    plan_executor: Callable[..., object] | None = None,
    http_probe: object | None = None,
    devtools_client: object | None = None,
    endpoint_wait_timeout_sec: float = 10.0,
    request_timeout: float = 0.2,
) -> AgentAppDevToolsOwnedLaunchReport:
    started = time.perf_counter()
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    helpers: list[dict] = []
    active_plan_executor = plan_executor or execute_session_readiness_plan
    active_http_probe = http_probe or RequestsNativeConnectorHTTPProbe()
    active_devtools_client = devtools_client or BrowserDevToolsClient(
        request_timeout=max(0.05, float(request_timeout))
    )
    default_profile_keys = {
        str(item or "").strip().lower()
        for item in default_profile_agents or ()
        if str(item or "").strip()
    }

    for index, case in enumerate(_agent_app_devtools_launchable_cases(resolution_report), start=1):
        agent = str(case.get("agent", "") or "").strip()
        agent_id = str(case.get("agent_id", "") or "").strip()
        defaults = _agent_app_endpoint_defaults(agent or agent_id)
        effective_agent_id = agent_id or defaults["agent_id"]
        executable = str(case.get("executable_path", "") or "").strip()
        debug_port = int(defaults.get("devtools_port", 0) or 0)
        default_profile_requested = (
            str(effective_agent_id).lower() in default_profile_keys
            or str(agent).lower() in default_profile_keys
        )
        profile_mode = (
            "default-user-profile"
            if default_profile_requested
            else "isolated-owned-profile"
        )
        helper_workspace_path = (
            str(workspace_path or "").strip()
            if _agent_app_accepts_workspace_argument(effective_agent_id or agent)
            else ""
        )
        helper_root = root / f"{index:02d}-{_safe_path_component(effective_agent_id or agent)}"
        user_data_dir = helper_root / "profile"
        manifest_path = helper_root / "manifest.json"
        readiness_url = "" if debug_port == 0 else f"http://127.0.0.1:{debug_port}"
        launch_report: dict = {}
        endpoint_health: dict = {}
        pid = 0
        command = ""
        ready = False
        error = ""
        try:
            plan = build_session_readiness_plan(
                routes=("agent-app-devtools-owned",),
                options=SessionReadinessPlanOptions(
                    agent_app_executable=executable,
                    agent_app_debug_port=debug_port,
                    agent_app_user_data_dir=str(user_data_dir),
                    agent_app_workspace_path=helper_workspace_path,
                    agent_app_use_default_profile=default_profile_requested,
                ),
            )
            launch_report = _report_to_dict(
                active_plan_executor(
                    plan,
                    manifest_path=str(manifest_path),
                )
            )
            ready = _counter(launch_report, "launch_attempts") > 0
            readiness_url = _readiness_url_from_launch_report(
                launch_report,
                default=readiness_url,
            )
            pid = _pid_from_launch_report(launch_report)
            command = _command_from_launch_report(launch_report)
            if ready and readiness_url:
                endpoint_health = _wait_for_agent_app_devtools_endpoint_health(
                    readiness_url,
                    http_probe=active_http_probe,
                    devtools_client=active_devtools_client,
                    timeout_sec=endpoint_wait_timeout_sec,
                    request_timeout=request_timeout,
                )
                ready = bool(endpoint_health.get("ready", False))
            elif ready:
                ready = False
                error = "agent_app_devtools_readiness_url_missing"
            if not ready:
                error = error or "agent_app_devtools_owned_not_started"
                if endpoint_health.get("error"):
                    error = str(endpoint_health.get("error") or error)
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
        helpers.append(
            {
                "mode": "agent-app-devtools-owned-launch",
                "safety_mode": "managed_background_helper_launch",
                "control_allowed": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "enabled": True,
                "ready": ready,
                "cleanup_ok": False,
                "agent": agent or defaults["agent"],
                "agent_id": effective_agent_id,
                "executable_path": executable,
                "pid": pid,
                "debug_port": debug_port,
                "debugger_url": readiness_url,
                "profile_mode": profile_mode,
                "uses_default_profile": default_profile_requested,
                "user_data_dir": "" if default_profile_requested else str(user_data_dir),
                "workspace_path": helper_workspace_path,
                "manifest_path": str(manifest_path),
                "command": command,
                "launch_attempts": _counter(launch_report, "launch_attempts"),
                "stop_attempts": 0,
                "endpoint_health": endpoint_health,
                "launch_report": launch_report,
                "error": error,
            }
        )

    return _agent_app_devtools_owned_launch_fleet_report(
        output_root=str(root),
        helpers=helpers,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def prepare_agent_native_cdp_bridge_helper(
    *,
    output_root: str | Path,
    agent: str = "codex app",
    agent_id: str = "codex",
    bridge_port: int = 0,
    debugger_url: str = "",
    process_name: str = "Codex.exe",
    pid: int = 0,
    hwnd: int = 0,
    window_title: str = "",
    project_name: str = "openwukong",
    task_name: str = "major-real-no-loss",
    target_title: str = "",
    target_url: str = "",
    registry_wait_timeout_sec: float = 5.0,
    plan_executor: Callable[..., object] | None = None,
) -> AgentNativeCdpBridgeHelperReport:
    started = time.perf_counter()
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    host = "127.0.0.1"
    configured_bridge_port = int(bridge_port)
    bridge_url = (
        "" if configured_bridge_port == 0 else f"http://{host}:{configured_bridge_port}"
    )
    registry_path = root / "native-bridges.json"
    manifest_path = root / "manifest.json"
    launch_report: dict = {}
    error = ""
    ready = False
    active_plan_executor = plan_executor or execute_session_readiness_plan

    try:
        if not str(debugger_url or "").strip():
            error = "agent_native_cdp_bridge_debugger_url_required"
            raise RuntimeError(error)
        if not str(process_name or "").strip():
            error = "agent_native_cdp_bridge_process_name_required"
            raise RuntimeError(error)
        plan = build_session_readiness_plan(
            routes=("agent-native-cdp-bridge",),
            options=SessionReadinessPlanOptions(
                agent_bridge_agent=agent,
                agent_bridge_agent_id=agent_id,
                agent_bridge_host=host,
                agent_bridge_port=configured_bridge_port,
                agent_bridge_debugger_url=debugger_url,
                agent_bridge_registry_path=str(registry_path),
                agent_bridge_process_name=process_name,
                agent_bridge_pid=int(pid or 0),
                agent_bridge_hwnd=int(hwnd or 0),
                agent_bridge_window_title=window_title,
                agent_bridge_project_name=project_name,
                agent_bridge_task_name=task_name,
                agent_bridge_target_title=target_title,
                agent_bridge_target_url=target_url,
            ),
        )
        launch_report = _report_to_dict(
            active_plan_executor(
                plan,
                manifest_path=str(manifest_path),
            )
        )
        if _counter(launch_report, "launch_attempts") <= 0:
            error = "agent_native_cdp_bridge_helper_not_started"
            raise RuntimeError(error)
        launched_bridge_url = _launch_readiness_url(
            launch_report,
            action_id="launch_agent_native_cdp_bridge",
        )
        if launched_bridge_url:
            bridge_url = launched_bridge_url
        if not bridge_url:
            error = "dynamic_agent_native_cdp_bridge_readiness_url_missing"
            raise RuntimeError(error)
        ready = _wait_for_agent_native_cdp_bridge_registry(
            registry_path,
            bridge_url=bridge_url,
            agent_id=agent_id,
            timeout_sec=registry_wait_timeout_sec,
        )
        if not ready:
            error = "agent_native_cdp_bridge_registry_not_ready"
    except Exception as exc:
        if not error:
            error = str(exc) or exc.__class__.__name__

    return AgentNativeCdpBridgeHelperReport(
        enabled=True,
        output_root=str(root),
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip(),
        bridge_url=bridge_url,
        registry_path=str(registry_path),
        manifest_path=str(manifest_path),
        ready=ready,
        cleanup_ok=False,
        launch_report=launch_report,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def prepare_agent_native_cdp_bridge_helper_fleet(
    *,
    output_root: str | Path,
    specs: Iterable[dict],
    project_name: str = "openwukong",
    task_name: str = "major-real-no-loss",
    registry_wait_timeout_sec: float = 5.0,
    helper_runner: Callable[..., object] | None = None,
) -> dict:
    started = time.perf_counter()
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    active_runner = helper_runner or prepare_agent_native_cdp_bridge_helper
    helpers: list[dict] = []
    for index, spec in enumerate(_normalize_agent_native_cdp_bridge_helper_specs(specs), start=1):
        helper_root = root / f"{index:02d}-{_safe_path_component(spec['agent_id'] or spec['agent'])}"
        helpers.append(
            _report_to_dict(
                active_runner(
                    output_root=helper_root,
                    agent=spec["agent"],
                    agent_id=spec["agent_id"],
                    bridge_port=spec["bridge_port"],
                    debugger_url=spec["debugger_url"],
                    process_name=spec["process_name"],
                    pid=spec["pid"],
                    hwnd=spec["hwnd"],
                    window_title=spec["window_title"],
                    project_name=project_name,
                    task_name=task_name,
                    target_title=spec["target_title"],
                    target_url=spec["target_url"],
                    registry_wait_timeout_sec=registry_wait_timeout_sec,
                )
            )
        )
    return _agent_native_cdp_bridge_helper_fleet_report(
        output_root=str(root),
        helpers=helpers,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def prepare_owned_ide_bridge_helper(
    *,
    output_root: str | Path,
    project_name: str = "openwukong",
    task_name: str = "major-real-no-loss",
    ide_executable: str = "cursor.exe",
    ide_bridge_port: int = 0,
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
    configured_bridge_port = int(ide_bridge_port)
    bridge_url = (
        "" if configured_bridge_port == 0 else f"http://{host}:{configured_bridge_port}"
    )
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
                ide_bridge_port=configured_bridge_port,
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
        launched_bridge_url = _launch_readiness_url(
            launch_report,
            action_id="launch_ide_bridge_isolated",
        )
        if launched_bridge_url:
            bridge_url = launched_bridge_url
        if not bridge_url:
            error = "dynamic_ide_bridge_readiness_url_missing"
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
            "openwukong.bridge.port": configured_bridge_port,
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
            port=configured_bridge_port,
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


def _launch_readiness_url(report: dict, *, action_id: str = "") -> str:
    if not isinstance(report, dict):
        return ""
    fallback_url = ""
    for result in report.get("results", []) or ():
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") != "started":
            continue
        url = str(result.get("readiness_url", "") or "").strip()
        if not url:
            continue
        if action_id and str(result.get("action_id", "") or "") != action_id:
            if not fallback_url:
                fallback_url = url
            continue
        if url:
            return url
    for launch in report.get("launches", []) or ():
        if not isinstance(launch, dict):
            continue
        url = str(launch.get("readiness_url", "") or "").strip()
        if not url:
            continue
        if action_id and str(launch.get("action_id", "") or "") != action_id:
            if not fallback_url:
                fallback_url = url
            continue
        if url:
            return url
    return fallback_url


def _system_dialog_preflight_failed(report: dict) -> bool:
    if not report:
        return False
    return bool(
        report.get("system_dialog_detected", False)
        or not bool(report.get("ok", True))
    )


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


def _disabled_agent_native_cdp_bridge_helper_report() -> dict:
    return {
        "mode": "agent-native-cdp-bridge-helper",
        "safety_mode": "managed_background_helper_launch",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "enabled": False,
        "ready": False,
        "cleanup_ok": True,
        "agent": "",
        "agent_id": "",
        "bridge_url": "",
        "registry_path": "",
        "manifest_path": "",
        "launch_attempts": 0,
        "stop_attempts": 0,
    }


def _disabled_agent_app_bridge_fixture_smoke_report() -> dict:
    return {
        "mode": "agent-app-bridge-fixture-smoke",
        "safety_mode": "local_owned_devtools_fixture",
        "control_allowed": False,
        "control_attempts": 0,
        "desktop_control_attempts": 0,
        "window_input_attempts": 0,
        "enabled": False,
        "ok": True,
        "decision": "disabled",
        "bridge_send_report": {
            "native_call_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        },
        "fixture": {
            "cdp_request_count": 0,
            "http_request_count": 0,
        },
    }


def _build_scenario_scope_report(
    *,
    run_primary_scenarios: bool,
    run_agent_app_scenarios: bool,
    run_agent_cli_scenarios: bool,
) -> dict:
    return {
        "mode": "major-scenario-scope",
        "primary_scenarios_enabled": bool(run_primary_scenarios),
        "agent_app_scenarios_enabled": bool(run_agent_app_scenarios),
        "agent_cli_scenarios_enabled": bool(run_agent_cli_scenarios),
        "primary_scenarios_skipped": not bool(run_primary_scenarios),
        "agent_app_scenarios_skipped": not bool(run_agent_app_scenarios),
        "agent_cli_scenarios_skipped": not bool(run_agent_cli_scenarios),
    }


def _disabled_primary_scenario_report() -> dict:
    return {
        "mode": "primary-scenario-real-no-loss",
        "safety_mode": "real_no_loss",
        "enabled": False,
        "decision": "primary_scenarios_skipped",
        "control_allowed": False,
        "control_attempts": 0,
        "external_communication_attempts": 0,
        "window_input_attempts": 0,
        "owned_app_launch_attempts": 0,
        "background_screenshot_count": 0,
        "background_screenshot_success_count": 0,
        "background_screenshot_focus_stable": True,
        "failed_cases": 0,
        "passed_cases": 0,
        "cases": [],
    }


def _disabled_agent_app_scenario_report() -> dict:
    return {
        "mode": "agent-app-real-no-loss",
        "safety_mode": "real_no_loss",
        "enabled": False,
        "decision": "agent_app_scenarios_skipped",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "agent_command_attempts": 0,
        "background_screenshot_count": 0,
        "background_screenshot_success_count": 0,
        "background_screenshot_focus_stable": True,
        "failed_cases": 0,
        "passed_cases": 0,
        "cases": [],
    }


def _disabled_agent_cli_scenario_report() -> dict:
    return {
        "mode": "agent-cli-real-no-loss",
        "safety_mode": "real_no_loss",
        "enabled": False,
        "decision": "agent_cli_scenarios_skipped",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "agent_command_attempts": 0,
        "foreground_focus_stable": True,
        "foreground_no_steal_verified": True,
        "failed_cases": 0,
        "passed_cases": 0,
        "cases": [],
    }


def _disabled_agent_native_bridge_fixture_smoke_report() -> dict:
    return {
        "mode": "agent-native-bridge-fixture-smoke",
        "safety_mode": "local_owned_http_fixture",
        "control_allowed": False,
        "control_attempts": 0,
        "desktop_control_attempts": 0,
        "window_input_attempts": 0,
        "native_call_attempts": 0,
        "enabled": False,
        "ok": True,
        "decision": "disabled",
        "send_report": {
            "native_call_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        },
        "fixture": {
            "capability_request_count": 0,
            "chat_request_count": 0,
        },
    }


def _disabled_wechat_native_bridge_fixture_smoke_report() -> dict:
    return {
        "mode": "wechat-native-bridge-fixture-smoke",
        "safety_mode": "local_owned_wechat_native_bridge_fixture",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "native_call_attempts": 0,
        "send_attempts": 0,
        "enabled": False,
        "ok": True,
        "decision": "disabled",
        "send_report": {
            "native_call_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        },
        "fixture": {
            "capability_request_count": 0,
            "send_request_count": 0,
        },
        "registry": {
            "registered": False,
            "discovered_urls": [],
        },
    }


def _disabled_agent_app_devtools_owned_launch_report() -> dict:
    return {
        "mode": "agent-app-devtools-owned-launch-fleet",
        "safety_mode": "managed_background_helper_launch",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "enabled": False,
        "ready": False,
        "cleanup_ok": True,
        "output_root": "",
        "helper_count": 0,
        "launch_attempts": 0,
        "stop_attempts": 0,
        "debugger_urls": [],
        "helpers": [],
    }


def _agent_app_devtools_launchable_cases(
    resolution_report: dict,
) -> tuple[dict, ...]:
    cases: list[dict] = []
    for raw in resolution_report.get("cases", []) or []:
        if not isinstance(raw, dict):
            continue
        executable = str(raw.get("executable_path", "") or "").strip()
        if not bool(raw.get("executable_ready", False)) or not executable:
            continue
        if _agent_app_launch_blocking_reason(
            raw,
            agent=str(raw.get("agent", "") or ""),
            agent_id=str(raw.get("agent_id", "") or ""),
        ):
            continue
        cases.append(dict(raw))
    return tuple(cases)


def _readiness_url_from_launch_report(launch_report: dict, *, default: str) -> str:
    for result in launch_report.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        url = str(result.get("readiness_url", "") or "").strip()
        if url:
            return url
    return default


def _pid_from_launch_report(launch_report: dict) -> int:
    for result in launch_report.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        pid = _counter(result, "pid")
        if pid > 0:
            return pid
    return 0


def _command_from_launch_report(launch_report: dict) -> str:
    for result in launch_report.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        command = str(result.get("command", "") or "").strip()
        if command:
            return command
        argv = result.get("argv")
        if isinstance(argv, list):
            text = " ".join(str(part) for part in argv if str(part or "").strip())
            if text:
                return text
    return ""


def _wait_for_agent_app_devtools_endpoint_health(
    debugger_url: str,
    *,
    http_probe: object,
    devtools_client: object | None,
    timeout_sec: float,
    request_timeout: float,
) -> dict:
    started = time.perf_counter()
    base = str(debugger_url or "").strip().rstrip("/")
    attempts = 0
    last_error = ""
    last_probe: dict | None = None
    while True:
        attempts += 1
        try:
            version = http_probe.get_json(
                f"{base}/json/version",
                timeout=max(0.05, float(request_timeout)),
            )
            if not isinstance(version, dict):
                raise ValueError("devtools_version_not_object")
            targets_raw = http_probe.get_json(
                f"{base}/json/list",
                timeout=max(0.05, float(request_timeout)),
            )
            if not isinstance(targets_raw, list):
                raise ValueError("devtools_targets_not_list")
            targets = [
                _devtools_target_summary(item)
                for item in targets_raw
                if isinstance(item, dict)
            ]
            ready = any(bool(item.get("webSocketDebuggerUrl", "")) for item in targets)
            browser_probe = _probe_browser_level_devtools_targets(
                base,
                version=version,
                devtools_client=devtools_client,
            )
            probe = {
                "mode": "agent-app-devtools-endpoint-health",
                "safety_mode": "read_only",
                "control_allowed": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "debugger_url": base,
                "ready": ready,
                "attempts": attempts,
                "version": version,
                "target_count": len(targets),
                "targets": targets,
                **browser_probe,
                "error": "" if ready else "devtools_targets_not_ready",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
            if ready:
                return probe
            last_error = str(probe["error"])
            last_probe = probe
        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__
        if time.perf_counter() - started >= max(0.0, float(timeout_sec)):
            if last_probe:
                timed_out_probe = dict(last_probe)
                timed_out_probe["ready"] = False
                timed_out_probe["error"] = last_error or timed_out_probe.get("error") or "devtools_endpoint_not_ready"
                timed_out_probe["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
                return timed_out_probe
            return {
                "mode": "agent-app-devtools-endpoint-health",
                "safety_mode": "read_only",
                "control_allowed": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "debugger_url": base,
                "ready": False,
                "attempts": attempts,
                "version": {},
                "target_count": 0,
                "targets": [],
                "error": last_error or "devtools_endpoint_not_ready",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        time.sleep(min(0.2, max(0.01, float(request_timeout))))


def _devtools_target_summary(data: dict) -> dict:
    return {
        "target_id": str(data.get("id", "") or data.get("targetId", "") or ""),
        "type": str(data.get("type", "") or ""),
        "title": str(data.get("title", "") or ""),
        "url": str(data.get("url", "") or ""),
        "webSocketDebuggerUrl": str(data.get("webSocketDebuggerUrl", "") or ""),
        "ready": bool(data.get("webSocketDebuggerUrl", "")),
    }


def _probe_browser_level_devtools_targets(
    debugger_url: str,
    *,
    version: dict,
    devtools_client: object | None,
) -> dict:
    browser_websocket_url = str(version.get("webSocketDebuggerUrl", "") or "")
    probe = {
        "browser_websocket_url": browser_websocket_url,
        "browser_level_ready": False,
        "browser_target_count": 0,
        "browser_targets": [],
        "browser_level_error": "",
    }
    if not browser_websocket_url:
        return probe
    if devtools_client is None or not hasattr(devtools_client, "call_browser_method"):
        probe["browser_level_error"] = "devtools_browser_probe_unavailable"
        return probe
    try:
        result = devtools_client.call_browser_method(
            debugger_url,
            "Target.getTargets",
            {},
        )
        target_infos = result.get("targetInfos", [])
        if not isinstance(target_infos, list):
            raise ValueError("devtools_browser_targets_not_list")
        browser_targets = [
            _devtools_target_summary(item)
            for item in target_infos
            if isinstance(item, dict)
        ]
        probe["browser_level_ready"] = True
        probe["browser_target_count"] = len(browser_targets)
        probe["browser_targets"] = browser_targets
    except Exception as exc:
        probe["browser_level_error"] = str(exc) or exc.__class__.__name__
    return probe


def _agent_app_devtools_owned_launch_fleet_report(
    *,
    output_root: str,
    helpers: list[dict],
    elapsed_ms: float,
) -> AgentAppDevToolsOwnedLaunchReport:
    enabled = bool(helpers)
    ready = enabled and all(bool(helper.get("ready", False)) for helper in helpers)
    cleanup_ok = all(
        (not bool(helper.get("enabled", False)))
        or bool(helper.get("cleanup_ok", False))
        for helper in helpers
    )
    return AgentAppDevToolsOwnedLaunchReport(
        enabled=enabled,
        output_root=output_root,
        helpers=tuple(dict(helper) for helper in helpers),
        ready=ready,
        cleanup_ok=cleanup_ok,
        elapsed_ms=elapsed_ms,
    )


def _normalize_agent_native_cdp_bridge_helper_specs(
    specs: Iterable[dict],
) -> tuple[dict, ...]:
    normalized: list[dict] = []
    for raw in specs or ():
        if not isinstance(raw, dict):
            continue
        agent = str(raw.get("agent", "") or "").strip()
        agent_id = str(raw.get("agent_id", "") or raw.get("agentId", "") or "").strip()
        debugger_url = str(raw.get("debugger_url", "") or raw.get("debuggerUrl", "") or "").strip()
        process_name = str(raw.get("process_name", "") or raw.get("processName", "") or "").strip()
        bridge_port = _counter({"value": raw.get("bridge_port", raw.get("port", 0))}, "value")
        if not agent or not agent_id or not debugger_url or not process_name or bridge_port < 0:
            continue
        normalized.append(
            {
                "agent": agent,
                "agent_id": agent_id,
                "bridge_port": bridge_port,
                "debugger_url": debugger_url,
                "process_name": process_name,
                "pid": _counter({"value": raw.get("pid", 0)}, "value"),
                "hwnd": _counter({"value": raw.get("hwnd", 0)}, "value"),
                "window_title": str(raw.get("window_title", "") or raw.get("windowTitle", "") or "").strip(),
                "target_title": str(raw.get("target_title", "") or raw.get("targetTitle", "") or "").strip(),
                "target_url": str(raw.get("target_url", "") or raw.get("targetUrl", "") or "").strip(),
            }
        )
    return tuple(normalized)


def _agent_native_cdp_bridge_helper_fleet_report(
    *,
    output_root: str,
    helpers: list[dict],
    elapsed_ms: float,
) -> dict:
    registry_paths = [
        str(helper.get("registry_path", "") or "").strip()
        for helper in helpers
        if str(helper.get("registry_path", "") or "").strip()
    ]
    launch_attempts = sum(_counter(helper, "launch_attempts") for helper in helpers)
    stop_attempts = sum(_counter(helper, "stop_attempts") for helper in helpers)
    enabled = bool(helpers)
    ready = bool(helpers) and all(bool(helper.get("ready", False)) for helper in helpers)
    cleanup_ok = all(
        (not bool(helper.get("enabled", False)))
        or bool(helper.get("cleanup_ok", False))
        for helper in helpers
    )
    return {
        "mode": "agent-native-cdp-bridge-helper-fleet",
        "safety_mode": "managed_background_helper_launch",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "enabled": enabled,
        "ready": ready,
        "cleanup_ok": cleanup_ok,
        "output_root": output_root,
        "helper_count": len(helpers),
        "launch_attempts": launch_attempts,
        "stop_attempts": stop_attempts,
        "registry_paths": registry_paths,
        "helpers": [dict(helper) for helper in helpers],
        "elapsed_ms": round(elapsed_ms, 3),
    }


def _effective_ide_bridge_urls(
    explicit_urls: Iterable[str],
    helper_report: dict,
    ide_extension_readiness_report: dict | None = None,
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
    readiness = ide_extension_readiness_report or {}
    if bool(readiness.get("bridge_ready", False)):
        bridge_url = str(readiness.get("bridge_url", "") or "").strip()
        if bridge_url and bridge_url not in urls:
            urls.append(bridge_url)
    return tuple(urls)


def _agent_app_devtools_debugger_urls_by_agent(
    owned_launch_report: dict,
) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    for helper in owned_launch_report.get("helpers", []) or []:
        if not _probeable_owned_devtools_helper(helper):
            continue
        url = str(helper.get("debugger_url", "") or "").strip()
        if not url:
            continue
        for key in (
            str(helper.get("agent", "") or "").strip().lower(),
            str(helper.get("agent_id", "") or "").strip().lower(),
        ):
            if not key:
                continue
            values = mapping.setdefault(key, [])
            if url not in values:
                values.append(url)
    return {key: tuple(values) for key, values in mapping.items()}


def _combined_agent_app_process_provider(
    base_provider: Callable[[], Iterable[NativeProcessSnapshot]] | None,
    owned_launch_report: dict,
) -> Callable[[], tuple[NativeProcessSnapshot, ...]] | None:
    owned = _agent_app_devtools_process_snapshots(owned_launch_report)
    if not owned:
        return base_provider

    def _provider() -> tuple[NativeProcessSnapshot, ...]:
        base = tuple((base_provider or list_native_processes)() or ())
        seen: set[tuple[int, str, tuple[int, ...]]] = set()
        combined: list[NativeProcessSnapshot] = []
        for process in base + owned:
            key = (
                int(process.pid or 0),
                str(process.process_name or "").lower(),
                tuple(int(port) for port in process.listening_ports),
            )
            if key in seen:
                continue
            seen.add(key)
            combined.append(process)
        return tuple(combined)

    return _provider


def _agent_app_devtools_process_snapshots(
    owned_launch_report: dict,
) -> tuple[NativeProcessSnapshot, ...]:
    snapshots: list[NativeProcessSnapshot] = []
    for helper in owned_launch_report.get("helpers", []) or []:
        if not _probeable_owned_devtools_helper(helper):
            continue
        port = _counter(helper, "debug_port")
        if port <= 0:
            port = _port_from_debugger_url(str(helper.get("debugger_url", "") or ""))
        executable_path = str(helper.get("executable_path", "") or "").strip()
        process_name = _process_name_from_path(executable_path)
        if not process_name:
            process_name = str(helper.get("process_name", "") or "").strip()
        if not process_name or port <= 0:
            continue
        snapshots.append(
            NativeProcessSnapshot(
                pid=_counter(helper, "pid"),
                process_name=process_name,
                executable_path=executable_path,
                command_line=str(helper.get("command", "") or "").strip(),
                listening_ports=(port,),
            )
        )
    return tuple(snapshots)


def _probeable_owned_devtools_helper(helper: object) -> bool:
    if not isinstance(helper, dict):
        return False
    if not str(helper.get("debugger_url", "") or "").strip():
        return False
    return bool(
        helper.get("ready", False)
        or _counter(helper, "launch_attempts") > 0
        or _details(helper.get("endpoint_health")).get("browser_level_ready", False)
    )


def _process_name_from_path(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    normalized = text.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def _port_from_debugger_url(url: str) -> int:
    text = str(url or "").strip().rstrip("/")
    if ":" not in text:
        return 0
    try:
        value = int(text.rsplit(":", 1)[-1])
    except ValueError:
        return 0
    return value if 0 < value <= 65535 else 0


def _effective_agent_native_bridge_registry_paths(
    explicit_paths: Iterable[str | Path],
    helper_report: dict,
) -> tuple[str | Path, ...]:
    paths: list[str | Path] = []
    seen: set[str] = set()
    for value in explicit_paths or ():
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            paths.append(value)
    if bool(helper_report.get("ready", False)):
        registry_path = str(helper_report.get("registry_path", "") or "").strip()
        if registry_path and registry_path not in seen:
            seen.add(registry_path)
            paths.append(Path(registry_path))
        for registry_value in helper_report.get("registry_paths", []) or []:
            registry_text = str(registry_value or "").strip()
            if registry_text and registry_text not in seen:
                seen.add(registry_text)
                paths.append(Path(registry_text))
    for helper in helper_report.get("helpers", []) or []:
        if not isinstance(helper, dict) or not bool(helper.get("ready", False)):
            continue
        registry_path = str(helper.get("registry_path", "") or "").strip()
        if registry_path and registry_path not in seen:
            seen.add(registry_path)
            paths.append(Path(registry_path))
    return tuple(paths)


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


def _stop_agent_native_cdp_bridge_helper_if_needed(helper_report: dict) -> dict:
    if not bool(helper_report.get("enabled", False)):
        return helper_report
    if str(helper_report.get("mode", "") or "") == "agent-native-cdp-bridge-helper-fleet":
        helpers = [
            _stop_agent_native_cdp_bridge_helper_if_needed(dict(helper))
            for helper in helper_report.get("helpers", []) or []
            if isinstance(helper, dict)
        ]
        updated = _agent_native_cdp_bridge_helper_fleet_report(
            output_root=str(helper_report.get("output_root", "") or ""),
            helpers=helpers,
            elapsed_ms=float(helper_report.get("elapsed_ms", 0.0) or 0.0),
        )
        return updated
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


def _stop_agent_app_devtools_owned_launch_if_needed(launch_report: dict) -> dict:
    if not bool(launch_report.get("enabled", False)):
        return launch_report
    if str(launch_report.get("mode", "") or "") == "agent-app-devtools-owned-launch-fleet":
        helpers = [
            _stop_agent_app_devtools_owned_launch_if_needed(dict(helper))
            for helper in launch_report.get("helpers", []) or []
            if isinstance(helper, dict)
        ]
        return _report_to_dict(
            _agent_app_devtools_owned_launch_fleet_report(
                output_root=str(launch_report.get("output_root", "") or ""),
                helpers=helpers,
                elapsed_ms=float(launch_report.get("elapsed_ms", 0.0) or 0.0),
            )
        )
    manifest_path = str(launch_report.get("manifest_path", "") or "").strip()
    if not manifest_path:
        return dict(launch_report)
    existing_stop = launch_report.get("stop_report")
    if isinstance(existing_stop, dict) and existing_stop:
        return dict(launch_report)
    stop_report = stop_session_readiness_manifest(manifest_path).to_dict()
    profile_cleanup = _remove_agent_app_owned_profile_dir(
        launch_report,
        manifest_path=manifest_path,
    )
    updated = dict(launch_report)
    updated["stop_report"] = stop_report
    updated["stop_attempts"] = _counter(stop_report, "stop_attempts")
    updated["profile_cleanup_attempted"] = profile_cleanup["attempted"]
    updated["profile_cleanup_ok"] = profile_cleanup["ok"]
    updated["profile_cleanup_error"] = profile_cleanup["error"]
    updated["cleanup_ok"] = _stop_report_cleanup_ok(stop_report) and bool(
        profile_cleanup["ok"]
    )
    return updated


def _remove_agent_app_owned_profile_dir(
    launch_report: dict,
    *,
    manifest_path: str,
) -> dict:
    profile_text = str(launch_report.get("user_data_dir", "") or "").strip()
    if not profile_text:
        return {"attempted": False, "ok": True, "error": ""}
    try:
        profile_path = Path(profile_text).expanduser().resolve()
        manifest_parent = Path(manifest_path).expanduser().resolve().parent
        if profile_path == manifest_parent or not _path_is_relative_to(
            profile_path,
            manifest_parent,
        ):
            return {
                "attempted": True,
                "ok": False,
                "error": "profile_outside_owned_helper_dir",
            }
        if not profile_path.exists():
            return {"attempted": True, "ok": True, "error": ""}
        shutil.rmtree(profile_path)
        return {
            "attempted": True,
            "ok": not profile_path.exists(),
            "error": "" if not profile_path.exists() else "profile_still_exists",
        }
    except Exception as exc:
        return {
            "attempted": True,
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
        }


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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


def _wait_for_agent_native_cdp_bridge_registry(
    registry_path: Path,
    *,
    bridge_url: str,
    agent_id: str,
    timeout_sec: float,
) -> bool:
    deadline = time.monotonic() + max(0.1, float(timeout_sec or 0.1))
    expected_url = str(bridge_url or "").strip().rstrip("/")
    expected_agent_id = str(agent_id or "").strip().casefold()
    while True:
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            entries = data.get("agent_native_bridges", [])
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry_url = str(entry.get("url", "") or "").strip().rstrip("/")
                    entry_agent_id = str(
                        entry.get("agent_id", "") or ""
                    ).strip().casefold()
                    if (
                        entry_url == expected_url
                        and (not expected_agent_id or entry_agent_id == expected_agent_id)
                    ):
                        return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


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


def _merge_agent_runner_reports(
    reports: Iterable[dict],
    *,
    mode: str,
    safety_mode: str,
) -> dict:
    items = [dict(report) for report in reports if isinstance(report, dict)]
    sum_keys = (
        "control_attempts",
        "window_input_attempts",
        "bridge_send_attempts",
        "agent_command_attempts",
        "background_screenshot_count",
        "background_screenshot_success_count",
        "passed_cases",
        "failed_cases",
        "verified_cases",
        "native_ready_cases",
        "gated_cases",
        "real_verified_cases",
        "app_bridge_send_verified_cases",
        "uia_semantic_action_send_verified_cases",
    )
    merged = {
        "mode": mode,
        "safety_mode": safety_mode,
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "agent_command_attempts": 0,
        "background_screenshot_count": 0,
        "background_screenshot_success_count": 0,
        "background_screenshot_focus_stable": True,
        "foreground_focus_stable": True,
        "foreground_no_steal_verified": True,
        "cases": [],
        "isolated_agent_reports": items,
    }
    for key in sum_keys:
        merged[key] = sum(_counter(report, key) for report in items)
    merged["background_screenshot_focus_stable"] = all(
        bool(report.get("background_screenshot_focus_stable", True))
        for report in items
    )
    merged["foreground_focus_stable"] = all(
        bool(report.get("foreground_focus_stable", True)) for report in items
    )
    merged["foreground_no_steal_verified"] = all(
        bool(report.get("foreground_no_steal_verified", True))
        for report in items
    )
    cases: list[dict] = []
    for report in items:
        raw_cases = report.get("cases", [])
        if isinstance(raw_cases, list):
            cases.extend(dict(item) for item in raw_cases if isinstance(item, dict))
    merged["cases"] = cases
    return merged


def _safe_stage_id(value: str) -> str:
    text = str(value or "").strip().lower()
    safe = "".join(char if char.isalnum() else "-" for char in text)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "agent"


def _run_major_stage(
    stage_name: str,
    *,
    runner_timeout_sec: float,
    stage_reports: list[dict],
    output_root: Path,
    runner: Callable[[], object],
) -> object:
    started = time.perf_counter()
    _record_major_stage(
        stage_reports,
        output_root,
        {
            "stage_name": stage_name,
            "status": "started",
            "timed_out": False,
            "timeout_sec": float(runner_timeout_sec or 0.0),
            "elapsed_ms": 0.0,
        },
    )
    if not runner_timeout_sec or runner_timeout_sec <= 0:
        try:
            result = runner()
        except BaseException as exc:
            _record_major_stage(
                stage_reports,
                output_root,
                _major_stage_failure(stage_name, started, exc),
            )
            raise
        _record_major_stage(
            stage_reports,
            output_root,
            _major_stage_success(stage_name, started),
        )
        return result

    results: queue.Queue = queue.Queue(maxsize=1)

    def _target() -> None:
        try:
            results.put(("ok", runner()))
        except BaseException as exc:  # pragma: no cover - exercised via main thread
            results.put(("error", exc))

    thread = threading.Thread(
        target=_target,
        name=f"openwukong-major-stage-{stage_name}",
        daemon=True,
    )
    thread.start()
    thread.join(float(runner_timeout_sec))
    if thread.is_alive():
        report = _major_stage_timeout_report(
            stage_name,
            timeout_sec=float(runner_timeout_sec),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        _record_major_stage(
            stage_reports,
            output_root,
            {
                "stage_name": stage_name,
                "status": "timed_out",
                "timed_out": True,
                "timeout_sec": float(runner_timeout_sec),
                "elapsed_ms": report["elapsed_ms"],
                "report": dict(report),
            },
        )
        return report

    kind, payload = results.get_nowait()
    if kind == "error":
        _record_major_stage(
            stage_reports,
            output_root,
            _major_stage_failure(stage_name, started, payload),
        )
        raise payload
    _record_major_stage(
        stage_reports,
        output_root,
        _major_stage_success(stage_name, started),
    )
    return payload


def _major_stage_success(stage_name: str, started: float) -> dict:
    return {
        "stage_name": stage_name,
        "status": "completed",
        "timed_out": False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _major_stage_failure(stage_name: str, started: float, exc: object) -> dict:
    return {
        "stage_name": stage_name,
        "status": "failed",
        "timed_out": False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "error_type": exc.__class__.__name__,
        "error": str(exc),
    }


def _major_stage_timeout_report(
    stage_name: str,
    *,
    timeout_sec: float,
    elapsed_ms: float,
) -> dict:
    return {
        "mode": "major-runner-stage-timeout",
        "safety_mode": "real_no_loss",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "agent_command_attempts": 0,
        "failed_cases": 1,
        "cases": [],
        "ok": False,
        "decision": "runner_stage_timeout",
        "stage_name": stage_name,
        "timed_out": True,
        "timeout_sec": timeout_sec,
        "elapsed_ms": round(elapsed_ms, 3),
        "attempt_counters_reliable": False,
        "unknown_post_timeout_runner_state": True,
    }


def _runner_stage_timed_out(report: dict) -> bool:
    return bool(report.get("timed_out", False)) or str(
        report.get("decision", "") or ""
    ) == "runner_stage_timeout"


def _skipped_after_runner_timeout_report(stage_name: str) -> dict:
    return {
        "mode": "major-runner-stage-skipped",
        "safety_mode": "real_no_loss",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "agent_command_attempts": 0,
        "failed_cases": 1,
        "cases": [],
        "ok": False,
        "decision": "skipped_after_runner_timeout",
        "stage_name": stage_name,
    }


def _record_major_stage(
    stage_reports: list[dict],
    output_root: Path,
    entry: dict,
) -> None:
    stage_reports.append(dict(entry))
    _write_major_stage_progress(output_root, stage_reports)


def _write_major_stage_progress(output_root: Path, stage_reports: list[dict]) -> None:
    payload = {
        "mode": "major-real-no-loss-progress",
        "stages": [dict(item) for item in stage_reports],
    }
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "major-real-no-loss-progress.json").write_text(
            _json_dumps(payload),
            encoding="utf-8",
        )
    except OSError:
        pass


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


def _force_exit_process(code: int) -> None:
    os._exit(code)


def _parse_agent_native_cdp_bridge_helper_specs(values: Iterable[str]) -> tuple[dict, ...]:
    specs: list[dict] = []
    for value in values or ():
        text = str(value or "").strip()
        if not text:
            continue
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            specs.append(dict(parsed))
        elif isinstance(parsed, list):
            specs.extend(dict(item) for item in parsed if isinstance(item, dict))
    return tuple(specs)


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
    parser.add_argument(
        "--runner-timeout-sec",
        type=float,
        default=0.0,
        help="Optional per-stage timeout for major runner sub-checks. Zero disables the wrapper.",
    )
    parser.add_argument(
        "--stop-on-runner-timeout",
        action="store_true",
        help="Write the final report after the first timed-out runner stage instead of continuing through later stages.",
    )
    parser.add_argument(
        "--skip-primary-scenarios",
        action="store_true",
        help="Skip primary real scenarios and omit their requirements from this acceptance run.",
    )
    parser.add_argument(
        "--skip-agent-app-scenarios",
        action="store_true",
        help="Skip agent desktop-app scenarios and omit their requirements from this acceptance run.",
    )
    parser.add_argument(
        "--skip-agent-cli-scenarios",
        action="store_true",
        help="Skip agent CLI scenarios and omit their requirements from this acceptance run.",
    )
    parser.add_argument("--allow-owned-browser-helper-launch", action="store_true")
    parser.add_argument("--owned-browser-debug-port", type=int, default=0)
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
        "--wechat-native-bridge-registry",
        action="append",
        default=[],
        help="Read-only JSON registry file with local WeChat native bridge URLs.",
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
    parser.add_argument(
        "--isolate-agent-app-scenarios",
        action="store_true",
        help="Run agent app no-loss probes one agent at a time so one blocked app cannot hide the others.",
    )
    parser.add_argument(
        "--isolate-agent-cli-scenarios",
        action="store_true",
        help="Run agent CLI no-loss probes one agent at a time so one blocked CLI cannot hide the others.",
    )
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
        "--allow-codex-app-server-thread-start",
        action="store_true",
        help="Allow Codex app-server thread/start only; does not run turn/start.",
    )
    parser.add_argument(
        "--codex-app-server-thread-start-timeout",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--allow-codex-app-server-turn-start",
        action="store_true",
        help="Allow Codex app-server turn/start after the verified dry-run contract is ready.",
    )
    parser.add_argument(
        "--codex-app-server-turn-start-timeout",
        type=float,
        default=30.0,
    )
    parser.add_argument(
        "--run-agent-app-bridge-fixture-smoke",
        action="store_true",
        help="Run an owned local DevTools fixture smoke that validates the app bridge sender contract without touching user apps.",
    )
    parser.add_argument(
        "--agent-app-bridge-fixture-message",
        default="OPENWUKONG_APP_BRIDGE_FIXTURE_SMOKE",
        help="Message used for the optional owned app bridge fixture smoke.",
    )
    parser.add_argument(
        "--agent-app-bridge-fixture-acceptance-marker",
        action="append",
        default=[],
        help="Required owned fixture readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--agent-app-bridge-fixture-forbid-marker",
        action="append",
        default=[],
        help="Forbidden owned fixture readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--run-agent-native-bridge-fixture-smoke",
        action="store_true",
        help="Run an owned local HTTP agent native bridge fixture smoke without touching user apps.",
    )
    parser.add_argument(
        "--agent-native-bridge-fixture-message",
        default="OPENWUKONG_AGENT_NATIVE_BRIDGE_FIXTURE_SMOKE",
        help="Message used for the optional owned agent native bridge fixture smoke.",
    )
    parser.add_argument(
        "--agent-native-bridge-fixture-acceptance-marker",
        action="append",
        default=[],
        help="Required owned agent native fixture readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--agent-native-bridge-fixture-forbid-marker",
        action="append",
        default=[],
        help="Forbidden owned agent native fixture readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--run-wechat-native-bridge-fixture-smoke",
        action="store_true",
        help="Run an owned local WeChat native bridge fixture smoke without touching personal chats.",
    )
    parser.add_argument(
        "--wechat-native-bridge-fixture-message",
        default="OPENWUKONG_WECHAT_FIXTURE: PASS",
        help="Message used for the optional owned WeChat native bridge fixture smoke.",
    )
    parser.add_argument(
        "--wechat-native-bridge-fixture-acceptance-marker",
        action="append",
        default=[],
        help="Required owned WeChat fixture readback marker. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--wechat-native-bridge-fixture-forbid-marker",
        action="append",
        default=[],
        help="Forbidden owned WeChat fixture readback marker. Repeat for multiple markers.",
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
        "--probe-existing-ide-extension-bridge",
        action="store_true",
        help="Attach-only read-only probe for an already-running IDE extension bridge; does not launch or reload the IDE.",
    )
    parser.add_argument(
        "--ide-extension-bridge-url",
        default=DEFAULT_IDE_EXTENSION_BRIDGE_URL,
        help="Already-running IDE extension bridge URL used by the attach-only readiness probe.",
    )
    parser.add_argument(
        "--ide-extension-agent-id",
        default="cursor",
        help="Agent adapter id to validate through the already-running IDE extension bridge.",
    )
    parser.add_argument(
        "--ide-extension-request-timeout-sec",
        type=float,
        default=0.5,
        help="Per-request timeout for attach-only IDE extension readiness probes.",
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
        "--codex-app-server-ws-url",
        action="append",
        default=[],
        help="Explicit local Codex app-server WebSocket URL forwarded to agent app no-loss probes.",
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
    parser.add_argument("--owned-ide-bridge-port", type=int, default=0)
    parser.add_argument("--owned-ide-user-data-dir", default="")
    parser.add_argument("--owned-ide-extensions-dir", default="")
    parser.add_argument("--owned-ide-extension-dir", default="extensions/openwukong-vscode")
    parser.add_argument("--owned-ide-workspace-root", default="")
    parser.add_argument("--owned-ide-chat-adapter-id", default="cursor")
    parser.add_argument("--owned-ide-capability-timeout-sec", type=float, default=30.0)
    parser.add_argument(
        "--allow-agent-native-cdp-bridge-helper-launch",
        action="store_true",
        help="Launch a managed local agent-native CDP bridge helper and forward its registry to agent app probes.",
    )
    parser.add_argument("--agent-native-cdp-bridge-helper-agent", default="codex app")
    parser.add_argument("--agent-native-cdp-bridge-helper-agent-id", default="codex")
    parser.add_argument(
        "--agent-native-cdp-bridge-helper-port",
        type=int,
        default=0,
        help="Agent native CDP bridge helper port. Use 0 to let the operating system assign an unused loopback port.",
    )
    parser.add_argument("--agent-native-cdp-bridge-helper-debugger-url", default="")
    parser.add_argument(
        "--agent-native-cdp-bridge-helper-process-name",
        default="Codex.exe",
    )
    parser.add_argument("--agent-native-cdp-bridge-helper-pid", type=int, default=0)
    parser.add_argument("--agent-native-cdp-bridge-helper-hwnd", type=int, default=0)
    parser.add_argument("--agent-native-cdp-bridge-helper-window-title", default="")
    parser.add_argument("--agent-native-cdp-bridge-helper-target-title", default="")
    parser.add_argument("--agent-native-cdp-bridge-helper-target-url", default="")
    parser.add_argument(
        "--agent-native-cdp-bridge-registry-wait-timeout-sec",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--agent-native-cdp-bridge-helper-spec",
        action="append",
        default=[],
        help="JSON object describing one agent native CDP helper. Repeat for Codex/Claude/Cursor helpers.",
    )
    parser.add_argument(
        "--allow-agent-app-devtools-owned-launch",
        action="store_true",
        help="Launch resolved Codex/Claude/Cursor app surfaces with isolated profiles and local DevTools endpoints, then forward those endpoints to no-loss probes.",
    )
    parser.add_argument(
        "--allow-agent-app-devtools-default-profile-launch",
        action="store_true",
        help="Launch agent app surfaces with the user's default profile plus a local DevTools endpoint, then forward the endpoint to no-loss probes.",
    )
    parser.add_argument(
        "--agent-app-devtools-endpoint-wait-timeout-sec",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--agent-app-devtools-request-timeout-sec",
        type=float,
        default=0.2,
    )
    parser.add_argument("--allow-agent-cli-execution", action="store_true")
    parser.add_argument("--agent-cli-timeout-sec", type=float, default=90.0)
    args = parser.parse_args(argv)

    report = run_major_scenario_real_no_loss(
        fixture_path=args.fixture,
        output_root=args.output_root,
        runner_timeout_sec=args.runner_timeout_sec,
        stop_on_runner_timeout=args.stop_on_runner_timeout,
        run_primary_scenarios=not args.skip_primary_scenarios,
        run_agent_app_scenarios=not args.skip_agent_app_scenarios,
        run_agent_cli_scenarios=not args.skip_agent_cli_scenarios,
        isolate_agent_app_scenarios=args.isolate_agent_app_scenarios,
        isolate_agent_cli_scenarios=args.isolate_agent_cli_scenarios,
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
        wechat_native_bridge_registry_paths=tuple(
            args.wechat_native_bridge_registry or ()
        ),
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
        allow_codex_app_server_thread_start=(
            args.allow_codex_app_server_thread_start
        ),
        codex_app_server_thread_start_timeout=(
            args.codex_app_server_thread_start_timeout
        ),
        allow_codex_app_server_turn_start=args.allow_codex_app_server_turn_start,
        codex_app_server_turn_start_timeout=(
            args.codex_app_server_turn_start_timeout
        ),
        run_agent_app_bridge_fixture_smoke=args.run_agent_app_bridge_fixture_smoke,
        agent_app_bridge_fixture_message=args.agent_app_bridge_fixture_message,
        agent_app_bridge_fixture_required_markers=tuple(
            args.agent_app_bridge_fixture_acceptance_marker
            or ("OPENWUKONG_ACCEPTANCE: PASS",)
        ),
        agent_app_bridge_fixture_forbidden_markers=tuple(
            args.agent_app_bridge_fixture_forbid_marker or ()
        ),
        run_agent_native_bridge_fixture_smoke=(
            args.run_agent_native_bridge_fixture_smoke
        ),
        agent_native_bridge_fixture_message=(
            args.agent_native_bridge_fixture_message
        ),
        agent_native_bridge_fixture_required_markers=tuple(
            args.agent_native_bridge_fixture_acceptance_marker
            or ("OPENWUKONG_ACCEPTANCE: PASS",)
        ),
        agent_native_bridge_fixture_forbidden_markers=tuple(
            args.agent_native_bridge_fixture_forbid_marker or ()
        ),
        run_wechat_native_bridge_fixture_smoke=(
            args.run_wechat_native_bridge_fixture_smoke
        ),
        wechat_native_bridge_fixture_message=(
            args.wechat_native_bridge_fixture_message
        ),
        wechat_native_bridge_fixture_required_markers=tuple(
            args.wechat_native_bridge_fixture_acceptance_marker
            or ("OPENWUKONG_WECHAT_FIXTURE: PASS",)
        ),
        wechat_native_bridge_fixture_forbidden_markers=tuple(
            args.wechat_native_bridge_fixture_forbid_marker or ()
        ),
        debugger_urls=tuple(args.debugger_url or ()),
        ide_bridge_urls=tuple(args.ide_bridge_url or ()),
        probe_existing_ide_extension_bridge=args.probe_existing_ide_extension_bridge,
        ide_extension_bridge_url=args.ide_extension_bridge_url,
        ide_extension_agent_id=args.ide_extension_agent_id,
        ide_extension_request_timeout_sec=args.ide_extension_request_timeout_sec,
        agent_native_bridge_urls=tuple(args.agent_native_bridge_url or ()),
        agent_native_bridge_registry_paths=tuple(args.agent_native_bridge_registry or ()),
        codex_app_server_ws_urls=tuple(args.codex_app_server_ws_url or ()),
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
        allow_agent_native_cdp_bridge_helper_launch=(
            args.allow_agent_native_cdp_bridge_helper_launch
        ),
        agent_native_cdp_bridge_helper_agent=(
            args.agent_native_cdp_bridge_helper_agent
        ),
        agent_native_cdp_bridge_helper_agent_id=(
            args.agent_native_cdp_bridge_helper_agent_id
        ),
        agent_native_cdp_bridge_helper_port=(
            args.agent_native_cdp_bridge_helper_port
        ),
        agent_native_cdp_bridge_helper_debugger_url=(
            args.agent_native_cdp_bridge_helper_debugger_url
        ),
        agent_native_cdp_bridge_helper_process_name=(
            args.agent_native_cdp_bridge_helper_process_name
        ),
        agent_native_cdp_bridge_helper_pid=(
            args.agent_native_cdp_bridge_helper_pid
        ),
        agent_native_cdp_bridge_helper_hwnd=(
            args.agent_native_cdp_bridge_helper_hwnd
        ),
        agent_native_cdp_bridge_helper_window_title=(
            args.agent_native_cdp_bridge_helper_window_title
        ),
        agent_native_cdp_bridge_helper_target_title=(
            args.agent_native_cdp_bridge_helper_target_title
        ),
        agent_native_cdp_bridge_helper_target_url=(
            args.agent_native_cdp_bridge_helper_target_url
        ),
        agent_native_cdp_bridge_registry_wait_timeout_sec=(
            args.agent_native_cdp_bridge_registry_wait_timeout_sec
        ),
        agent_native_cdp_bridge_helper_specs=(
            _parse_agent_native_cdp_bridge_helper_specs(
                args.agent_native_cdp_bridge_helper_spec or ()
            )
        ),
        allow_agent_app_devtools_owned_launch=(
            args.allow_agent_app_devtools_owned_launch
        ),
        allow_agent_app_devtools_default_profile_launch=(
            args.allow_agent_app_devtools_default_profile_launch
        ),
        agent_app_devtools_endpoint_wait_timeout_sec=(
            args.agent_app_devtools_endpoint_wait_timeout_sec
        ),
        agent_app_devtools_request_timeout_sec=(
            args.agent_app_devtools_request_timeout_sec
        ),
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
    if args.runner_timeout_sec > 0 and bool(payload.get("runner_timed_out", False)):
        sys.stdout.flush()
        sys.stderr.flush()
        _force_exit_process(1)
    return 0 if report.safe_run_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
