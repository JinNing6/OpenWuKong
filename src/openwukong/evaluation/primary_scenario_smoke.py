# -*- coding: utf-8 -*-
"""L2.5 isolated smoke runner for primary user scenario drafts.

This runner intentionally reuses the L1 primary_scenario_plan output. It does
not observe the live desktop, launch applications, scan real files, or inject
input into windows.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import http.server
import json
import re
import socketserver
import struct
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from openwukong.connectors import BrowserDevToolsClient, ConnectorTarget
from openwukong.control import (
    ControlFabric,
    ControlIntent,
    SessionOwnership,
    SessionOwnershipIndex,
    build_side_effect_policy,
)
from openwukong.control.session_readiness_plan import (
    SessionReadinessLauncher,
    SessionReadinessPlanOptions,
    SessionReadinessTerminator,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.evaluation.simulation import (
    L1SimulationHarness,
    load_simulation_fixture,
)


OwnedBrowserHelperReadinessProbe = Callable[[str], dict]
OwnedBrowserHelperActionRunner = Callable[..., object]
_OWNED_BROWSER_HELPER_DEFAULT_URL = (
    "data:text/html,%3Ctitle%3EOpenWukong%20Primary%20Smoke%3C/title%3E"
    "%3Cbody%3EOpenWukong%20Primary%20Smoke%3C/body%3E"
)
_OWNED_BROWSER_HELPER_ACTION_ID = "browser-owned-helper-read-page"


@dataclasses.dataclass(frozen=True)
class PrimaryScenarioSmokeCase:
    case_id: str
    passed: bool
    errors: tuple[str, ...]
    source_l1_passed: bool
    scenario_id: str = ""
    route_id: str = ""
    connector_id: str = ""
    proposed_action: str = ""
    artifact_path: str = ""
    adapter_id: str = ""
    adapter_artifact_path: str = ""
    owned_session_dry_run_id: str = ""
    owned_session_dry_run_artifact_path: str = ""
    owned_session_execution_id: str = ""
    owned_session_execution_artifact_path: str = ""
    owned_browser_helper_id: str = ""
    owned_browser_helper_artifact_path: str = ""
    blocked_primitives: tuple[str, ...] = ()
    blocked_effects: tuple[dict, ...] = ()
    confirmation_required_effects: tuple[dict, ...] = ()

    @property
    def mode(self) -> str:
        return "primary-scenario-smoke-case"

    @property
    def safety_mode(self) -> str:
        return "isolated_no_focus"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "case_id": self.case_id,
            "passed": self.passed,
            "errors": list(self.errors),
            "source_l1_passed": self.source_l1_passed,
            "scenario_id": self.scenario_id,
            "route_id": self.route_id,
            "connector_id": self.connector_id,
            "proposed_action": self.proposed_action,
            "artifact_path": self.artifact_path,
            "adapter_id": self.adapter_id,
            "adapter_artifact_path": self.adapter_artifact_path,
            "owned_session_dry_run_id": self.owned_session_dry_run_id,
            "owned_session_dry_run_artifact_path": self.owned_session_dry_run_artifact_path,
            "owned_session_execution_id": self.owned_session_execution_id,
            "owned_session_execution_artifact_path": self.owned_session_execution_artifact_path,
            "owned_browser_helper_id": self.owned_browser_helper_id,
            "owned_browser_helper_artifact_path": self.owned_browser_helper_artifact_path,
            "blocked_primitives": list(self.blocked_primitives),
            "blocked_effects": [dict(effect) for effect in self.blocked_effects],
            "confirmation_required_effects": [
                dict(effect) for effect in self.confirmation_required_effects
            ],
        }


@dataclasses.dataclass(frozen=True)
class PrimaryScenarioSmokeReport:
    suite: str
    output_root: str
    cases: tuple[PrimaryScenarioSmokeCase, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "primary-scenario-smoke"

    @property
    def safety_mode(self) -> str:
        if self.owned_browser_helper_artifact_count:
            return "isolated_no_focus_with_owned_browser_helper_opt_in"
        return "isolated_no_focus"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def desktop_scan_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def live_app_launch_attempts(self) -> int:
        return self.owned_browser_helper_artifact_count

    @property
    def real_filesystem_scan_attempts(self) -> int:
        return 0

    @property
    def owned_browser_helper_artifact_count(self) -> int:
        return sum(1 for case in self.cases if case.owned_browser_helper_artifact_path)

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def passed_cases(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "suite": self.suite,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "desktop_scan_attempts": self.desktop_scan_attempts,
            "window_input_attempts": self.window_input_attempts,
            "live_app_launch_attempts": self.live_app_launch_attempts,
            "real_filesystem_scan_attempts": self.real_filesystem_scan_attempts,
            "owned_browser_helper_artifact_count": self.owned_browser_helper_artifact_count,
            "output_root": self.output_root,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "cases": [case.to_dict() for case in self.cases],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_primary_scenario_smoke(
    fixture: dict,
    *,
    output_root: str | Path = "",
    harness: L1SimulationHarness | None = None,
    allow_owned_browser_helper_launch: bool = False,
    owned_browser_helper_launcher: SessionReadinessLauncher | None = None,
    owned_browser_helper_terminator: SessionReadinessTerminator | None = None,
    owned_browser_helper_readiness_probe: OwnedBrowserHelperReadinessProbe | None = None,
    owned_browser_helper_action_runner: OwnedBrowserHelperActionRunner | None = None,
    owned_browser_debug_port: int = 9238,
    owned_browser_executable: str = "chrome.exe",
    owned_browser_url: str = _OWNED_BROWSER_HELPER_DEFAULT_URL,
) -> PrimaryScenarioSmokeReport:
    started = time.perf_counter()
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    active_harness = harness or L1SimulationHarness()
    l1_report = active_harness.run_suite(fixture)
    cases = tuple(
        _smoke_case_from_l1_result(
            result.to_dict(),
            output_root=root,
            allow_owned_browser_helper_launch=allow_owned_browser_helper_launch,
            owned_browser_helper_launcher=owned_browser_helper_launcher,
            owned_browser_helper_terminator=owned_browser_helper_terminator,
            owned_browser_helper_readiness_probe=owned_browser_helper_readiness_probe,
            owned_browser_helper_action_runner=owned_browser_helper_action_runner,
            owned_browser_debug_port=owned_browser_debug_port,
            owned_browser_executable=owned_browser_executable,
            owned_browser_url=owned_browser_url,
        )
        for result in l1_report.results
    )
    return PrimaryScenarioSmokeReport(
        suite=l1_report.suite,
        output_root=str(root),
        cases=cases,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _smoke_case_from_l1_result(
    result: dict,
    *,
    output_root: Path,
    allow_owned_browser_helper_launch: bool = False,
    owned_browser_helper_launcher: SessionReadinessLauncher | None = None,
    owned_browser_helper_terminator: SessionReadinessTerminator | None = None,
    owned_browser_helper_readiness_probe: OwnedBrowserHelperReadinessProbe | None = None,
    owned_browser_helper_action_runner: OwnedBrowserHelperActionRunner | None = None,
    owned_browser_debug_port: int = 9238,
    owned_browser_executable: str = "chrome.exe",
    owned_browser_url: str = _OWNED_BROWSER_HELPER_DEFAULT_URL,
) -> PrimaryScenarioSmokeCase:
    case_id = str(result.get("case_id", "") or "unnamed-case")
    source_passed = bool(result.get("passed", False))
    plan = result.get("primary_scenario_plan", {})
    errors = list(result.get("errors", []) or [])
    if not isinstance(plan, dict) or not plan:
        errors.append("primary_scenario_plan missing")
        return PrimaryScenarioSmokeCase(
            case_id=case_id,
            passed=False,
            errors=tuple(str(item) for item in errors),
            source_l1_passed=source_passed,
        )

    artifact_path = _write_draft_artifact(
        output_root=output_root,
        case_id=case_id,
        plan=plan,
    )
    adapter_id, adapter_artifact_path = _write_adapter_artifact(
        output_root=output_root,
        case_id=case_id,
        plan=plan,
    )
    dry_run_id, dry_run_artifact_path = _write_owned_session_dry_run_artifact(
        output_root=output_root,
        case_id=case_id,
        plan=plan,
    )
    execution_id, execution_artifact_path = _write_owned_session_execution_artifact(
        output_root=output_root,
        case_id=case_id,
        plan=plan,
    )
    helper_id, helper_artifact_path, helper_errors = _write_owned_browser_helper_artifact(
        output_root=output_root,
        case_id=case_id,
        plan=plan,
        allow_launch=allow_owned_browser_helper_launch,
        launcher=owned_browser_helper_launcher,
        terminator=owned_browser_helper_terminator,
        readiness_probe=owned_browser_helper_readiness_probe,
        action_runner=owned_browser_helper_action_runner,
        debug_port=owned_browser_debug_port,
        browser_executable=owned_browser_executable,
        browser_url=owned_browser_url,
    )
    errors.extend(helper_errors)
    return PrimaryScenarioSmokeCase(
        case_id=case_id,
        passed=source_passed and not errors,
        errors=tuple(str(item) for item in errors),
        source_l1_passed=source_passed,
        scenario_id=str(plan.get("scenario_id", "") or ""),
        route_id=str(plan.get("route_id", "") or ""),
        connector_id=str(plan.get("connector_id", "") or ""),
        proposed_action=str(plan.get("proposed_action", "") or ""),
        artifact_path=str(artifact_path),
        adapter_id=adapter_id,
        adapter_artifact_path=str(adapter_artifact_path),
        owned_session_dry_run_id=dry_run_id,
        owned_session_dry_run_artifact_path=str(dry_run_artifact_path) if dry_run_artifact_path else "",
        owned_session_execution_id=execution_id,
        owned_session_execution_artifact_path=str(execution_artifact_path) if execution_artifact_path else "",
        owned_browser_helper_id=helper_id,
        owned_browser_helper_artifact_path=str(helper_artifact_path) if helper_artifact_path else "",
        blocked_primitives=tuple(
            str(item)
            for item in plan.get("blocked_primitives", []) or []
            if str(item).strip()
        ),
        blocked_effects=tuple(
            dict(effect)
            for effect in plan.get("side_effect_policy", {}).get("blocked_effects", []) or []
            if isinstance(effect, dict)
        ),
        confirmation_required_effects=tuple(
            dict(effect)
            for effect in plan.get("side_effect_policy", {}).get(
                "confirmation_required_effects",
                [],
            )
            or []
            if isinstance(effect, dict)
        ),
    )


def _write_draft_artifact(
    *,
    output_root: Path,
    case_id: str,
    plan: dict,
) -> Path:
    draft_dir = output_root / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = draft_dir / f"{_safe_filename(case_id)}.json"
    artifact = {
        "mode": "primary-scenario-smoke-artifact",
        "status": "draft_only",
        "case_id": case_id,
        "scenario_id": str(plan.get("scenario_id", "") or ""),
        "route_id": str(plan.get("route_id", "") or ""),
        "connector_id": str(plan.get("connector_id", "") or ""),
        "proposed_action": str(plan.get("proposed_action", "") or ""),
        "draft_action": dict(plan.get("draft_action", {}) or {}),
        "side_effect_policy": dict(plan.get("side_effect_policy", {}) or {}),
        "source_plan": dict(plan),
        "isolation": {
            "output_root": str(output_root),
            "desktop_scan_allowed": False,
            "window_input_allowed": False,
            "live_app_launch_allowed": False,
            "real_user_profile_allowed": False,
            "real_filesystem_scan_allowed": False,
        },
    }
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return artifact_path


def _write_adapter_artifact(
    *,
    output_root: Path,
    case_id: str,
    plan: dict,
) -> tuple[str, Path]:
    adapters_dir = output_root / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    scenario_id = str(plan.get("scenario_id", "") or "")
    adapter_id = _adapter_id_for_scenario(scenario_id)
    artifact_path = adapters_dir / f"{_safe_filename(case_id)}.json"
    artifact = _adapter_artifact_payload(
        adapter_id=adapter_id,
        case_id=case_id,
        plan=plan,
        output_root=output_root,
    )
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return adapter_id, artifact_path


def _write_owned_session_dry_run_artifact(
    *,
    output_root: Path,
    case_id: str,
    plan: dict,
) -> tuple[str, Path | None]:
    scenario_id = str(plan.get("scenario_id", "") or "")
    if scenario_id not in {
        "browser.research.collect_sources",
        "codex.project.submit_task_draft",
    }:
        return "", None

    dry_runs_dir = output_root / "owned_session_dry_runs"
    dry_runs_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = dry_runs_dir / f"{_safe_filename(case_id)}.json"
    dry_run_id = _owned_session_dry_run_id(scenario_id)
    artifact = _owned_session_dry_run_payload(
        dry_run_id=dry_run_id,
        case_id=case_id,
        plan=plan,
        output_root=output_root,
    )
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dry_run_id, artifact_path


def _write_owned_session_execution_artifact(
    *,
    output_root: Path,
    case_id: str,
    plan: dict,
) -> tuple[str, Path | None]:
    scenario_id = str(plan.get("scenario_id", "") or "")
    if scenario_id not in {
        "browser.research.collect_sources",
        "codex.project.submit_task_draft",
    }:
        return "", None

    executions_dir = output_root / "owned_session_executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = executions_dir / f"{_safe_filename(case_id)}.json"
    execution_id = _owned_session_execution_id(scenario_id)
    if scenario_id == "browser.research.collect_sources":
        artifact = _browser_owned_session_execution_payload(
            execution_id=execution_id,
            case_id=case_id,
            plan=plan,
            output_root=output_root,
        )
    else:
        artifact = _codex_owned_session_execution_payload(
            execution_id=execution_id,
            case_id=case_id,
            plan=plan,
            output_root=output_root,
        )
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return execution_id, artifact_path


def _write_owned_browser_helper_artifact(
    *,
    output_root: Path,
    case_id: str,
    plan: dict,
    allow_launch: bool = False,
    launcher: SessionReadinessLauncher | None = None,
    terminator: SessionReadinessTerminator | None = None,
    readiness_probe: OwnedBrowserHelperReadinessProbe | None = None,
    action_runner: OwnedBrowserHelperActionRunner | None = None,
    debug_port: int = 9238,
    browser_executable: str = "chrome.exe",
    browser_url: str = _OWNED_BROWSER_HELPER_DEFAULT_URL,
) -> tuple[str, Path | None, tuple[str, ...]]:
    scenario_id = str(plan.get("scenario_id", "") or "")
    if scenario_id != "browser.research.collect_sources" or not allow_launch:
        return "", None, ()

    safe_case = _safe_filename(case_id)
    helper_id = _owned_browser_helper_id(scenario_id)
    helper_dir = output_root / "owned_browser_helpers" / safe_case
    helper_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = helper_dir / "helper.json"
    manifest_path = helper_dir / "manifest.json"
    profile_path = output_root / "owned_sessions" / safe_case / "browser-profile-real-helper"
    profile_path.mkdir(parents=True, exist_ok=True)

    readiness_plan = build_session_readiness_plan(
        routes=("browser-devtools-or-extension",),
        options=SessionReadinessPlanOptions(
            browser_executable=str(browser_executable or "chrome.exe"),
            browser_debug_port=int(debug_port),
            browser_user_data_dir=str(profile_path),
            browser_url=str(browser_url or _OWNED_BROWSER_HELPER_DEFAULT_URL),
        ),
    )
    execution_report = execute_session_readiness_plan(
        readiness_plan,
        manifest_path=str(manifest_path),
        launcher=launcher,
    )
    execution_data = execution_report.to_dict()
    probe_data = _run_owned_browser_helper_readiness_probe(
        execution_data=execution_data,
        readiness_probe=readiness_probe,
        expected_url=str(browser_url or _OWNED_BROWSER_HELPER_DEFAULT_URL),
    )
    action_data = _run_owned_browser_helper_action(
        probe_data=probe_data,
        manifest_path=manifest_path,
        profile_path=profile_path,
        browser_executable=str(browser_executable or "chrome.exe"),
        action_runner=action_runner,
    )
    stop_report = stop_session_readiness_manifest(
        str(manifest_path),
        terminator=terminator,
    )
    stop_data = stop_report.to_dict()
    helper_errors = _owned_browser_helper_errors(
        execution_data=execution_data,
        probe_data=probe_data,
        action_data=action_data,
        stop_data=stop_data,
    )
    status = "started_and_stopped" if not helper_errors else "failed"
    artifact = {
        "mode": "primary-scenario-owned-browser-helper",
        "safety_mode": "isolated_owned_browser_helper_opt_in",
        "status": status,
        "helper_id": helper_id,
        "case_id": case_id,
        "scenario_id": scenario_id,
        "launch_allowed": True,
        "desktop_control_allowed": False,
        "desktop_control_attempts": 0,
        "window_input_attempts": 0,
        "real_user_profile_allowed": False,
        "manifest_path": str(manifest_path),
        "profile_path": str(profile_path),
        "readiness_plan": readiness_plan.to_dict(),
        "readiness_execution": execution_data,
        "readiness_probe": probe_data,
        "owned_browser_action_id": _OWNED_BROWSER_HELPER_ACTION_ID,
        "owned_browser_action_control_attempts": int(
            action_data.get("control_attempts", 0) or 0
        ),
        "owned_browser_action": action_data,
        "readiness_stop": stop_data,
        "errors": helper_errors,
        "isolation": {
            **_isolation_payload(output_root),
            "live_app_launch_allowed": True,
            "live_connector_call_allowed": bool(action_data.get("decision") == "executed"),
            "real_user_profile_allowed": False,
            "owned_session_manifest_only": False,
            "manifest_based_cleanup_required": True,
        },
    }
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return helper_id, artifact_path, tuple(helper_errors)


def _owned_browser_helper_id(scenario_id: str) -> str:
    return {
        "browser.research.collect_sources": "browser-owned-helper-readiness-launch",
    }.get(str(scenario_id or ""), "")


def _run_owned_browser_helper_readiness_probe(
    *,
    execution_data: dict,
    readiness_probe: OwnedBrowserHelperReadinessProbe | None = None,
    expected_url: str = "",
) -> dict:
    readiness_url = _first_started_readiness_url(execution_data)
    if not readiness_url:
        return {
            "mode": "browser-helper-readiness-probe",
            "ok": False,
            "debugger_url": "",
            "attempts": 0,
            "target_count": 0,
            "targets": [],
            "error": "launch_not_started",
            "expected_url": str(expected_url or ""),
            "target_match_ok": False,
            "matched_targets": [],
        }
    active_probe = readiness_probe or _probe_browser_helper_readiness
    try:
        data = active_probe(readiness_url)
    except Exception as exc:
        data = {
            "mode": "browser-helper-readiness-probe",
            "ok": False,
            "debugger_url": readiness_url,
            "attempts": 1,
            "target_count": 0,
            "targets": [],
            "error": str(exc) or exc.__class__.__name__,
        }
    if not isinstance(data, dict):
        data = {
            "mode": "browser-helper-readiness-probe",
            "ok": False,
            "debugger_url": readiness_url,
            "attempts": 1,
            "target_count": 0,
            "targets": [],
            "error": "invalid_probe_result",
        }
    matched_data = _attach_browser_helper_target_match(data, expected_url=expected_url)
    if bool(matched_data.get("target_match_ok", False)) or not str(expected_url or "").strip():
        return matched_data

    open_result = _open_owned_browser_helper_target(
        readiness_url,
        str(expected_url or ""),
    )
    try:
        retry_data = active_probe(readiness_url)
    except Exception as exc:
        retry_data = {
            "mode": "browser-helper-readiness-probe",
            "ok": False,
            "debugger_url": readiness_url,
            "attempts": int(matched_data.get("attempts", 0) or 0) + 1,
            "target_count": 0,
            "targets": [],
            "error": str(exc) or exc.__class__.__name__,
        }
    if not isinstance(retry_data, dict):
        retry_data = {
            "mode": "browser-helper-readiness-probe",
            "ok": False,
            "debugger_url": readiness_url,
            "attempts": int(matched_data.get("attempts", 0) or 0) + 1,
            "target_count": 0,
            "targets": [],
            "error": "invalid_probe_result",
        }
    retry_matched = _attach_browser_helper_target_match(
        retry_data,
        expected_url=expected_url,
    )
    retry_matched["target_open_attempted"] = True
    retry_matched["target_open_result"] = open_result
    if not bool(retry_matched.get("target_match_ok", False)):
        retry_matched["initial_readiness_probe"] = matched_data
    return retry_matched


def _open_owned_browser_helper_target(debugger_url: str, target_url: str) -> dict:
    base_url = str(debugger_url or "").rstrip("/")
    target = str(target_url or "").strip()
    if not base_url or not target:
        return {
            "ok": False,
            "method": "PUT",
            "url": "",
            "error": "missing_debugger_or_target_url",
        }
    request_url = f"{base_url}/json/new?{urllib.parse.quote(target, safe='')}"
    request = urllib.request.Request(request_url, method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            body = response.read().decode("utf-8", errors="replace")
            payload = json.loads(body) if body.strip() else {}
            return {
                "ok": 200 <= int(response.status) < 300,
                "method": "PUT",
                "url": request_url,
                "status": int(response.status),
                "target": payload if isinstance(payload, dict) else {},
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "method": "PUT",
            "url": request_url,
            "error": str(exc) or exc.__class__.__name__,
        }


def _run_owned_browser_helper_action(
    *,
    probe_data: dict,
    manifest_path: Path,
    profile_path: Path,
    browser_executable: str = "chrome.exe",
    action_runner: OwnedBrowserHelperActionRunner | None = None,
) -> dict:
    if not bool(probe_data.get("ok", False)) or not bool(
        probe_data.get("target_match_ok", False)
    ):
        return {
            "mode": "control-fabric-execution",
            "decision": "skipped",
            "ok": False,
            "control_allowed": False,
            "control_attempts": 0,
            "error": "owned_browser_helper_readiness_not_matched",
        }

    matched_target = _first_matched_browser_helper_target(probe_data)
    debugger_url = str(probe_data.get("debugger_url", "") or "").strip()
    target_url = str(matched_target.get("url", "") or "").strip()
    target_title = str(matched_target.get("title", "") or "").strip()
    process_name = Path(str(browser_executable or "chrome.exe")).name or "chrome.exe"
    ownership = SessionOwnership(
        owned=True,
        ownership_source="primary_scenario_smoke_real_browser_helper",
        manifest_path=str(manifest_path),
        route_id="browser-devtools-or-extension",
        connector_id="browser",
        action_id=_OWNED_BROWSER_HELPER_ACTION_ID,
        endpoint=debugger_url,
        profile_path=str(profile_path),
        cleanup_ready=True,
    )
    target = ConnectorTarget(
        process_name=process_name,
        window_title=f"{target_title} - Google Chrome" if target_title else "Google Chrome",
        project_name="browser-research",
        resource_url=target_url,
        debugger_url=debugger_url,
    )
    intent = ControlIntent(
        action="read_page",
        preferred_route_id="browser-devtools-or-extension",
        preferred_connector_id="browser",
        side_effect_policy=build_side_effect_policy(
            allowed_effect_ids=("recorded_context.read", "local_draft.write"),
        ),
    )
    report = ControlFabric.with_default_connectors(
        ownership_index=SessionOwnershipIndex((ownership,)),
        require_owned_session_for_execution=True,
    ).execute(
        target,
        intent,
        allow_control=True,
        browser_action_runner=action_runner,
    )
    return report.to_dict()


def _first_matched_browser_helper_target(probe_data: dict) -> dict:
    for target in probe_data.get("matched_targets", []) or []:
        if isinstance(target, dict):
            return dict(target)
    return {}


def _probe_browser_helper_readiness(debugger_url: str) -> dict:
    started = time.perf_counter()
    client = BrowserDevToolsClient(request_timeout=0.5)
    attempts = 0
    last_error = ""
    while (time.perf_counter() - started) < 5.0:
        attempts += 1
        try:
            targets = client.list_targets(debugger_url)
            target_data = [
                {
                    "id": target.target_id,
                    "type": target.type,
                    "title": target.title,
                    "url": target.url,
                    "webSocketDebuggerUrl": target.web_socket_debugger_url,
                }
                for target in targets
            ]
            has_page = any(str(target.get("type", "") or "") == "page" for target in target_data)
            return {
                "mode": "browser-helper-readiness-probe",
                "ok": has_page,
                "debugger_url": debugger_url,
                "attempts": attempts,
                "target_count": len(target_data),
                "targets": target_data,
                "error": "" if has_page else "no_page_target",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__
            time.sleep(0.1)
    return {
        "mode": "browser-helper-readiness-probe",
        "ok": False,
        "debugger_url": debugger_url,
        "attempts": attempts,
        "target_count": 0,
        "targets": [],
        "error": last_error or "readiness_timeout",
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _attach_browser_helper_target_match(data: dict, *, expected_url: str = "") -> dict:
    result = dict(data)
    expected = str(expected_url or "").strip()
    targets = [
        dict(target)
        for target in result.get("targets", []) or []
        if isinstance(target, dict)
    ]
    matched_targets = [
        target
        for target in targets
        if _browser_helper_target_matches_expected_url(target, expected)
    ]
    target_match_ok = bool(matched_targets) if expected else bool(targets)
    result["expected_url"] = expected
    result["target_match_ok"] = target_match_ok
    result["matched_targets"] = matched_targets
    if not target_match_ok:
        result["ok"] = False
        if not str(result.get("error", "") or "").strip():
            result["error"] = "target_url_mismatch"
    return result


def _browser_helper_target_matches_expected_url(target: dict, expected_url: str) -> bool:
    if not expected_url:
        return True
    target_url = str(target.get("url", "") or "").strip()
    if not target_url:
        return False
    if target_url == expected_url:
        return True
    if expected_url.startswith("data:") and target_url.startswith("data:"):
        return True
    return False


def _first_started_readiness_url(execution_data: dict) -> str:
    for result in execution_data.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") != "started":
            continue
        readiness_url = str(result.get("readiness_url", "") or "").strip()
        if readiness_url:
            return readiness_url
    return ""


def _owned_browser_helper_errors(
    *,
    execution_data: dict,
    probe_data: dict,
    action_data: dict,
    stop_data: dict,
) -> list[str]:
    errors: list[str] = []
    if int(execution_data.get("launch_attempts", 0) or 0) <= 0:
        errors.append(f"owned_browser_helper_launch_failed:{_first_report_error(execution_data)}")
    elif not bool(probe_data.get("ok", False)):
        errors.append(f"owned_browser_helper_readiness_failed:{_first_report_error(probe_data)}")
    elif not bool(action_data.get("ok", False)):
        errors.append(f"owned_browser_helper_action_failed:{_first_report_error(action_data)}")
    if int(stop_data.get("stop_attempts", 0) or 0) < int(
        execution_data.get("launch_attempts", 0) or 0
    ):
        errors.append(f"owned_browser_helper_stop_failed:{_first_report_error(stop_data)}")
    return errors


def _first_report_error(data: dict) -> str:
    top_error = str(data.get("error", "") or "").strip()
    if top_error:
        return top_error
    for result in data.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        error = str(result.get("error", "") or "").strip()
        if error:
            return error
        status = str(result.get("status", "") or "").strip()
        if status and status not in {"started", "stopped"}:
            return status
    return "no_started_launch"


def _owned_session_execution_id(scenario_id: str) -> str:
    return {
        "browser.research.collect_sources": "browser-owned-session-local-mock-devtools",
        "codex.project.submit_task_draft": "codex-owned-session-local-mock-bridge",
    }.get(str(scenario_id or ""), "")


def _owned_session_dry_run_id(scenario_id: str) -> str:
    return {
        "browser.research.collect_sources": "browser-owned-session-dry-run",
        "codex.project.submit_task_draft": "codex-owned-session-dry-run",
    }.get(str(scenario_id or ""), "")


def _owned_session_dry_run_payload(
    *,
    dry_run_id: str,
    case_id: str,
    plan: dict,
    output_root: Path,
) -> dict:
    ownership, target, intent = _owned_session_dry_run_contract(
        dry_run_id=dry_run_id,
        case_id=case_id,
        plan=plan,
        output_root=output_root,
    )
    dispatch_report = ControlFabric.with_default_connectors(
        ownership_index=SessionOwnershipIndex((ownership,)),
        require_owned_session_for_execution=True,
    ).dispatch(target, intent)
    dispatch_data = dispatch_report.to_dict()
    return {
        "mode": "primary-scenario-owned-session-dry-run",
        "safety_mode": "isolated_owned_session_dry_run",
        "status": "dry_run_only",
        "dry_run_id": dry_run_id,
        "case_id": case_id,
        "scenario_id": str(plan.get("scenario_id", "") or ""),
        "route_id": dispatch_data["selected_route"],
        "connector_id": dispatch_data["selected_connector_id"],
        "control_allowed": False,
        "control_attempts": 0,
        "ownership": ownership.to_dict(),
        "target": dispatch_data["target"],
        "control_intent": intent.to_dict(),
        "dispatch_report": dispatch_data,
        "side_effect_gate": dict(dispatch_data.get("side_effect_gate", {}) or {}),
        "source_plan_side_effect_policy": dict(plan.get("side_effect_policy", {}) or {}),
        "dry_run_side_effect_policy": dict(intent.side_effect_policy),
        "isolation": _isolation_payload(output_root),
    }


def _owned_session_dry_run_contract(
    *,
    dry_run_id: str,
    case_id: str,
    plan: dict,
    output_root: Path,
) -> tuple[SessionOwnership, ConnectorTarget, ControlIntent]:
    scenario_id = str(plan.get("scenario_id", "") or "")
    safe_case = _safe_filename(case_id)
    recorded_context = dict(plan.get("recorded_context", {}) or {})
    intent_payload = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    dry_run_policy = build_side_effect_policy(
        allowed_effect_ids=("recorded_context.read", "local_draft.write"),
    )
    session_root = output_root / "owned_sessions" / safe_case
    session_root.mkdir(parents=True, exist_ok=True)

    if scenario_id == "browser.research.collect_sources":
        profile_path = session_root / "browser-profile"
        profile_path.mkdir(parents=True, exist_ok=True)
        endpoint = f"dry-run://browser/{safe_case}"
        ownership = SessionOwnership(
            owned=True,
            ownership_source="primary_scenario_smoke_isolated_dry_run",
            manifest_path=str(session_root / "browser-owned-session.json"),
            route_id="browser-devtools-or-extension",
            connector_id="browser",
            action_id=dry_run_id,
            endpoint=endpoint,
            profile_path=str(profile_path),
            cleanup_ready=False,
        )
        target = ConnectorTarget(
            process_name="chrome.exe",
            window_title="Browser Owned Session Dry Run",
            project_name="browser-research",
            resource_url="about:blank#openwukong-browser-dry-run",
            debugger_url=endpoint,
        )
        intent = ControlIntent(
            action="extract_results",
            selector="a",
            text=str(intent_payload.get("query", "") or ""),
            side_effect_policy=dry_run_policy,
        )
        return ownership, target, intent

    workspace = str(intent_payload.get("workspace", "") or "")
    if not workspace:
        workspace = str(recorded_context.get("workspace", "") or output_root)
    bridge_root = session_root / "ide-bridge"
    bridge_root.mkdir(parents=True, exist_ok=True)
    endpoint = f"dry-run://ide-bridge/{safe_case}"
    project_id = str(recorded_context.get("project_id", "") or "codex")
    ownership = SessionOwnership(
        owned=True,
        ownership_source="primary_scenario_smoke_isolated_dry_run",
        manifest_path=str(session_root / "codex-owned-session.json"),
        route_id="ide-extension-connector",
        connector_id="ide-extension",
        action_id=dry_run_id,
        endpoint=endpoint,
        profile_path=str(bridge_root),
        workspace_root=workspace,
        cleanup_ready=False,
    )
    target = ConnectorTarget(
        process_name="Codex.exe",
        window_title="Codex Owned Session Dry Run",
        project_name=project_id,
        workspace_path=workspace,
        workspace_hint=project_id,
        ide_bridge_url=endpoint,
    )
    intent = ControlIntent(
        action="draft_codex_project_task",
        text=str(intent_payload.get("task", "") or ""),
        side_effect_policy=dry_run_policy,
    )
    return ownership, target, intent


def _browser_owned_session_execution_payload(
    *,
    execution_id: str,
    case_id: str,
    plan: dict,
    output_root: Path,
) -> dict:
    safe_case = _safe_filename(case_id)
    session_root = output_root / "owned_sessions" / safe_case
    profile_path = session_root / "browser-profile-local-mock"
    profile_path.mkdir(parents=True, exist_ok=True)

    with _LocalDevToolsFixture(plan) as fixture:
        ownership, target, intent = _browser_owned_session_execution_contract(
            execution_id=execution_id,
            case_id=case_id,
            plan=plan,
            profile_path=profile_path,
            debugger_url=fixture.debugger_url,
            resource_url=fixture.target_url,
        )
        execute_report = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        ).execute(target, intent, allow_control=True)
        execute_data = execute_report.to_dict()
        fixture_data = fixture.to_dict()

    return {
        "mode": "primary-scenario-owned-session-execution",
        "safety_mode": "isolated_owned_session_local_mock",
        "status": "executed_local_mock",
        "execution_id": execution_id,
        "case_id": case_id,
        "scenario_id": str(plan.get("scenario_id", "") or ""),
        "route_id": execute_data["selected_route"],
        "connector_id": execute_data["selected_connector_id"],
        "desktop_control_allowed": False,
        "desktop_control_attempts": 0,
        "local_connector_call_allowed": True,
        "local_connector_call_attempts": int(fixture_data["cdp_request_count"]),
        "ownership": ownership.to_dict(),
        "target": execute_data["dispatch_report"]["target"],
        "control_intent": intent.to_dict(),
        "execute_report": execute_data,
        "side_effect_gate": dict(
            execute_data.get("dispatch_report", {}).get("side_effect_gate", {}) or {}
        ),
        "source_plan_side_effect_policy": dict(plan.get("side_effect_policy", {}) or {}),
        "execution_side_effect_policy": dict(intent.side_effect_policy),
        "local_devtools_fixture": fixture_data,
        "isolation": {
            **_isolation_payload(output_root),
            "owned_session_manifest_only": False,
            "local_mock_connector_call_allowed": True,
            "live_connector_call_allowed": False,
        },
    }


def _browser_owned_session_execution_contract(
    *,
    execution_id: str,
    case_id: str,
    plan: dict,
    profile_path: Path,
    debugger_url: str,
    resource_url: str,
) -> tuple[SessionOwnership, ConnectorTarget, ControlIntent]:
    intent_payload = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    endpoint = str(debugger_url or "").strip()
    policy = build_side_effect_policy(
        allowed_effect_ids=("recorded_context.read", "local_draft.write"),
    )
    ownership = SessionOwnership(
        owned=True,
        ownership_source="primary_scenario_smoke_local_mock_devtools",
        manifest_path=str(profile_path.parent / "browser-owned-session-local-mock.json"),
        route_id="browser-devtools-or-extension",
        connector_id="browser",
        action_id=execution_id,
        endpoint=endpoint,
        profile_path=str(profile_path),
        cleanup_ready=True,
    )
    target = ConnectorTarget(
        process_name="chrome.exe",
        window_title="OpenWukong Browser Local DevTools Fixture - Google Chrome",
        project_name="browser-research",
        resource_url=str(resource_url or "").strip(),
        debugger_url=endpoint,
    )
    intent = ControlIntent(
        action="extract_results",
        selector="a",
        text=str(intent_payload.get("query", "") or ""),
        preferred_route_id="browser-devtools-or-extension",
        preferred_connector_id="browser",
        side_effect_policy=policy,
    )
    return ownership, target, intent


def _codex_owned_session_execution_payload(
    *,
    execution_id: str,
    case_id: str,
    plan: dict,
    output_root: Path,
) -> dict:
    safe_case = _safe_filename(case_id)
    session_root = output_root / "owned_sessions" / safe_case
    bridge_root = session_root / "ide-bridge-local-mock"
    bridge_root.mkdir(parents=True, exist_ok=True)

    with _LocalMockIDEBridge() as bridge:
        ownership, target, intent = _codex_owned_session_execution_contract(
            execution_id=execution_id,
            plan=plan,
            output_root=output_root,
            bridge_url=bridge.url,
            bridge_root=bridge_root,
        )
        execute_report = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        ).execute(target, intent, allow_control=True)
        execute_data = execute_report.to_dict()
        bridge_requests = bridge.requests()

    return {
        "mode": "primary-scenario-owned-session-execution",
        "safety_mode": "isolated_owned_session_local_mock",
        "status": "executed_local_mock",
        "execution_id": execution_id,
        "case_id": case_id,
        "scenario_id": str(plan.get("scenario_id", "") or ""),
        "route_id": execute_data["selected_route"],
        "connector_id": execute_data["selected_connector_id"],
        "desktop_control_allowed": False,
        "desktop_control_attempts": 0,
        "local_connector_call_allowed": True,
        "local_connector_call_attempts": int(execute_data.get("control_attempts", 0) or 0),
        "ownership": ownership.to_dict(),
        "target": execute_data["dispatch_report"]["target"],
        "control_intent": intent.to_dict(),
        "execute_report": execute_data,
        "side_effect_gate": dict(
            execute_data.get("dispatch_report", {}).get("side_effect_gate", {}) or {}
        ),
        "source_plan_side_effect_policy": dict(plan.get("side_effect_policy", {}) or {}),
        "execution_side_effect_policy": dict(intent.side_effect_policy),
        "mock_bridge": {
            "url": bridge.url,
            "request_count": len(bridge_requests),
            "requests": bridge_requests,
        },
        "isolation": {
            **_isolation_payload(output_root),
            "owned_session_manifest_only": False,
            "local_mock_connector_call_allowed": True,
            "live_connector_call_allowed": False,
        },
    }


def _codex_owned_session_execution_contract(
    *,
    execution_id: str,
    plan: dict,
    output_root: Path,
    bridge_url: str,
    bridge_root: Path,
) -> tuple[SessionOwnership, ConnectorTarget, ControlIntent]:
    recorded_context = dict(plan.get("recorded_context", {}) or {})
    intent_payload = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    workspace = str(intent_payload.get("workspace", "") or "")
    if not workspace:
        workspace = str(recorded_context.get("workspace", "") or output_root)
    project_id = str(recorded_context.get("project_id", "") or "codex")
    policy = build_side_effect_policy(
        allowed_effect_ids=("recorded_context.read", "local_draft.write"),
    )
    ownership = SessionOwnership(
        owned=True,
        ownership_source="primary_scenario_smoke_local_mock_bridge",
        manifest_path=str(bridge_root / "codex-owned-session-local-mock.json"),
        route_id="ide-extension-connector",
        connector_id="ide-extension",
        action_id=execution_id,
        endpoint=bridge_url,
        profile_path=str(bridge_root),
        workspace_root=workspace,
        cleanup_ready=True,
    )
    target = ConnectorTarget(
        process_name="Codex.exe",
        window_title="Codex Owned Session Local Mock",
        project_name=project_id,
        workspace_path=workspace,
        workspace_hint=project_id,
        ide_bridge_url=bridge_url,
    )
    intent = ControlIntent(
        action="draft_codex_project_task",
        text=str(intent_payload.get("task", "") or ""),
        preferred_route_id="ide-extension-connector",
        preferred_connector_id="ide-extension",
        side_effect_policy=policy,
    )
    return ownership, target, intent


def _adapter_id_for_scenario(scenario_id: str) -> str:
    return {
        "wechat.chat.draft_reply": "wechat-recorded-uia-bundle",
        "browser.research.collect_sources": "browser-static-dom-bundle",
        "files.search.find_candidate": "file-search-temp-index",
        "word.document.create_background": "word-owned-docx-template",
        "codex.project.submit_task_draft": "codex-draft-queue",
    }.get(str(scenario_id or ""), "primary-scenario-generic-adapter")


def _adapter_artifact_payload(
    *,
    adapter_id: str,
    case_id: str,
    plan: dict,
    output_root: Path,
) -> dict:
    scenario_id = str(plan.get("scenario_id", "") or "")
    intent = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    recorded_context = dict(plan.get("recorded_context", {}) or {})
    payload = {
        "mode": "primary-scenario-adapter-artifact",
        "adapter_id": adapter_id,
        "case_id": case_id,
        "scenario_id": scenario_id,
        "route_id": str(plan.get("route_id", "") or ""),
        "connector_id": str(plan.get("connector_id", "") or ""),
        "safety_mode": "isolated_no_focus",
        "control_allowed": False,
        "control_attempts": 0,
        "evidence_ids": list(plan.get("evidence_ids", []) or []),
        "side_effect_policy": dict(plan.get("side_effect_policy", {}) or {}),
        "isolation": {
            "output_root": str(output_root),
            "desktop_scan_allowed": False,
            "window_input_allowed": False,
            "live_app_launch_allowed": False,
            "real_user_profile_allowed": False,
            "real_filesystem_scan_allowed": False,
        },
    }
    if scenario_id == "wechat.chat.draft_reply":
        payload["uia_bundle"] = {
            "contact": str(intent.get("contact", "") or ""),
            "message": str(intent.get("message", "") or ""),
            "input_locator": dict(recorded_context.get("input_locator", {}) or {}),
            "send_allowed": False,
        }
    elif scenario_id == "browser.research.collect_sources":
        payload["static_dom"] = {
            "query": str(intent.get("query", "") or ""),
            "source_count": int(intent.get("source_count", 0) or 0),
            "source_titles": list(recorded_context.get("result_titles", []) or []),
            "live_navigation_allowed": False,
        }
    elif scenario_id == "files.search.find_candidate":
        candidates = list(recorded_context.get("candidates", []) or [])
        payload["temp_index"] = {
            "query": str(intent.get("query", "") or ""),
            "file_types": list(intent.get("file_types", []) or []),
            "candidate_count": len(candidates),
            "candidates": candidates,
            "real_filesystem_scan_allowed": False,
        }
    elif scenario_id == "word.document.create_background":
        payload["word_document"] = {
            "document_name": str(
                intent.get("document_name", "") or "openwukong-word-primary-scenario.docx"
            ),
            "marker": str(intent.get("marker", "") or "OPENWUKONG_WORD_PRIMARY_SCENARIO"),
            "document_template": str(recorded_context.get("document_template", "") or "blank"),
            "save_format": str(recorded_context.get("save_format", "") or "wdFormatXMLDocument"),
            "background_only": bool(recorded_context.get("background_only", True)),
            "owned_document_allowed": True,
            "user_document_allowed": False,
            "window_input_allowed": False,
        }
    elif scenario_id == "codex.project.submit_task_draft":
        draft_action = dict(plan.get("draft_action", {}) or {})
        payload["draft_queue"] = {
            "project_id": str(recorded_context.get("project_id", "") or ""),
            "queued_count": 1 if draft_action else 0,
            "items": [draft_action] if draft_action else [],
            "submit_allowed": False,
            "start_agent_allowed": False,
        }
    else:
        payload["generic_bundle"] = {
            "intent": intent,
            "recorded_context": recorded_context,
        }
    return payload


def _resolve_output_root(output_root: str | Path) -> Path:
    text = str(output_root or "").strip()
    if text:
        return Path(text).resolve()
    return Path(tempfile.mkdtemp(prefix="openwukong-primary-smoke-")).resolve()


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    text = text.strip("._")
    return text or "primary-scenario"


def format_report(report: PrimaryScenarioSmokeReport) -> str:
    lines = [
        f"Primary scenario smoke: {report.suite}",
        f"Cases: {report.passed_cases}/{report.total_cases} passed",
        f"Output root: {report.output_root}",
        (
            "No-interference counters: "
            f"desktop={report.desktop_scan_attempts} "
            f"input={report.window_input_attempts} "
            f"launch={report.live_app_launch_attempts} "
            f"fs_scan={report.real_filesystem_scan_attempts}"
        ),
        "",
    ]
    for case in report.cases:
        status = "PASS" if case.passed else "FAIL"
        lines.append(
            f"[{status}] {case.case_id} action={case.proposed_action or '-'} "
            f"artifact={case.artifact_path or '-'}"
        )
        for error in case.errors:
            lines.append(f"  - {error}")
    return "\n".join(lines).rstrip()


def summarize_report(report: PrimaryScenarioSmokeReport) -> dict:
    scenarios = [
        {
            "case_id": case.case_id,
            "passed": case.passed,
            "scenario_id": case.scenario_id,
            "route_id": case.route_id,
            "connector_id": case.connector_id,
            "proposed_action": case.proposed_action,
            "blocked_primitive_count": len(case.blocked_primitives),
            "blocked_effect_count": len(case.blocked_effects),
            "blocked_effect_categories": _effect_categories(case.blocked_effects),
            "confirmation_required_effect_count": len(case.confirmation_required_effects),
            "artifact_written": bool(case.artifact_path),
            "adapter_id": case.adapter_id,
            "adapter_artifact_written": bool(case.adapter_artifact_path),
            "owned_session_dry_run_id": case.owned_session_dry_run_id,
            "owned_session_dry_run_written": bool(case.owned_session_dry_run_artifact_path),
            "owned_session_execution_id": case.owned_session_execution_id,
            "owned_session_execution_written": bool(case.owned_session_execution_artifact_path),
            "owned_browser_helper_id": case.owned_browser_helper_id,
            "owned_browser_helper_written": bool(case.owned_browser_helper_artifact_path),
        }
        for case in report.cases
    ]
    return {
        "mode": "primary-scenario-smoke-summary",
        "suite": report.suite,
        "safety_mode": report.safety_mode,
        "control_allowed": report.control_allowed,
        "control_attempts": report.control_attempts,
        "desktop_scan_attempts": report.desktop_scan_attempts,
        "window_input_attempts": report.window_input_attempts,
        "live_app_launch_attempts": report.live_app_launch_attempts,
        "real_filesystem_scan_attempts": report.real_filesystem_scan_attempts,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "artifact_count": sum(1 for case in report.cases if case.artifact_path),
        "adapter_artifact_count": sum(1 for case in report.cases if case.adapter_artifact_path),
        "owned_session_dry_run_artifact_count": sum(
            1 for case in report.cases if case.owned_session_dry_run_artifact_path
        ),
        "owned_session_execution_artifact_count": sum(
            1 for case in report.cases if case.owned_session_execution_artifact_path
        ),
        "owned_browser_helper_artifact_count": report.owned_browser_helper_artifact_count,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def _effect_categories(effects: tuple[dict, ...]) -> list[str]:
    categories: list[str] = []
    for effect in effects:
        category = str(effect.get("category", "") or "")
        if category and category not in categories:
            categories.append(category)
    return categories


def _isolation_payload(output_root: Path) -> dict:
    return {
        "output_root": str(output_root),
        "desktop_scan_allowed": False,
        "window_input_allowed": False,
        "live_app_launch_allowed": False,
        "live_connector_call_allowed": False,
        "real_user_profile_allowed": False,
        "real_filesystem_scan_allowed": False,
        "owned_session_manifest_only": True,
    }


class _LocalDevToolsFixture:
    def __init__(self, plan: dict):
        self._plan = dict(plan)
        self._http_server: http.server.ThreadingHTTPServer | None = None
        self._ws_server: socketserver.ThreadingTCPServer | None = None
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._http_requests: list[dict] = []
        self._cdp_requests: list[dict] = []
        self.debugger_url = ""
        self.websocket_url = ""
        self.target_url = "about:blank#openwukong-browser-local-devtools"
        self.target_title = "OpenWukong Browser Local DevTools Fixture"

    def __enter__(self) -> "_LocalDevToolsFixture":
        ws_server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0),
            _LocalDevToolsWebSocketHandler,
        )
        ws_server.fixture = self
        ws_server.daemon_threads = True
        self._ws_server = ws_server
        self.websocket_url = (
            f"ws://127.0.0.1:{ws_server.server_address[1]}/devtools/page/page-1"
        )

        http_server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LocalDevToolsHTTPHandler,
        )
        http_server.fixture = self
        http_server.daemon_threads = True
        self._http_server = http_server
        self.debugger_url = f"http://127.0.0.1:{http_server.server_address[1]}"

        self._start_server(ws_server)
        self._start_server(http_server)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        for server in (self._http_server, self._ws_server):
            if server is not None:
                server.shutdown()
                server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)

    def _start_server(self, server) -> None:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._threads.append(thread)

    def target_payload(self) -> dict:
        return {
            "id": "page-1",
            "type": "page",
            "title": self.target_title,
            "url": self.target_url,
            "webSocketDebuggerUrl": self.websocket_url,
        }

    def record_http(self, path: str) -> None:
        with self._lock:
            self._http_requests.append({"path": path})

    def record_cdp(self, message: dict) -> None:
        with self._lock:
            self._cdp_requests.append(dict(message))

    def evaluate_remote_object(self, expression: str) -> dict:
        text = str(expression or "")
        value: object
        recorded_context = dict(self._plan.get("recorded_context", {}) or {})
        titles = [
            str(title)
            for title in recorded_context.get("result_titles", []) or []
            if str(title).strip()
        ]
        if "querySelectorAll" in text and "items" in text:
            value = {
                "selector": "a",
                "items": [
                    {
                        "text": title,
                        "href": f"https://example.test/source/{index + 1}",
                    }
                    for index, title in enumerate(titles)
                ],
            }
        elif "textExcerpt" in text:
            value = {
                "title": self.target_title,
                "href": self.target_url,
                "readyState": "complete",
                "textExcerpt": " ".join(titles),
            }
        elif "document.title" in text and "readyState" in text:
            value = {
                "title": self.target_title,
                "href": self.target_url,
                "readyState": "complete",
            }
        else:
            value = "ok"
        if isinstance(value, dict):
            return {"type": "object", "value": value}
        return {"type": "string", "value": value}

    def to_dict(self) -> dict:
        with self._lock:
            http_requests = [dict(item) for item in self._http_requests]
            cdp_requests = [dict(item) for item in self._cdp_requests]
        return {
            "mode": "local-devtools-fixture",
            "debugger_url": self.debugger_url,
            "websocket_url": self.websocket_url,
            "target": self.target_payload(),
            "http_request_count": len(http_requests),
            "cdp_request_count": len(cdp_requests),
            "http_requests": http_requests,
            "cdp_requests": cdp_requests,
        }


class _LocalDevToolsHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        fixture = getattr(self.server, "fixture", None)
        if fixture is not None:
            fixture.record_http(self.path)
        if self.path not in {"/json/list", "/json"}:
            self.send_response(404)
            self.end_headers()
            return
        targets = [fixture.target_payload()] if fixture is not None else []
        self._send_json(targets)

    def _send_json(self, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        del format, args


class _LocalDevToolsWebSocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        key = ""
        while True:
            line = self.rfile.readline().decode("ascii", errors="replace").strip()
            if not line:
                break
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.wfile.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        message = self._read_client_json()
        fixture = getattr(self.server, "fixture", None)
        if fixture is not None:
            fixture.record_cdp(message)
        expression = str(message.get("params", {}).get("expression", "") or "")
        remote_object = (
            fixture.evaluate_remote_object(expression)
            if fixture is not None
            else {"type": "undefined"}
        )
        self._send_server_json(
            {
                "id": int(message.get("id", 1) or 1),
                "result": {"result": remote_object},
            }
        )

    def _read_client_json(self) -> dict:
        header = self.rfile.read(2)
        if len(header) < 2:
            return {}
        first, second = header
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.rfile.read(8))[0]
        mask = self.rfile.read(4)
        payload = self.rfile.read(length) if length else b""
        if second & 0x80:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = {}
        return message if isinstance(message, dict) else {}

    def _send_server_json(self, message: dict) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))
        self.wfile.write(bytes(header) + payload)


class _LocalMockIDEBridge:
    def __init__(self):
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url = ""

    def __enter__(self) -> "_LocalMockIDEBridge":
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LocalMockIDEBridgeHandler,
        )
        server.requests = []
        self._server = server
        self.url = f"http://127.0.0.1:{server.server_address[1]}"
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        server = self._server
        thread = self._thread
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)

    def requests(self) -> list[dict]:
        server = self._server
        if server is None:
            return []
        return list(getattr(server, "requests", []) or [])


class _LocalMockIDEBridgeHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        request_record = {
            "path": self.path,
            "payload": payload if isinstance(payload, dict) else {},
        }
        requests = getattr(self.server, "requests", None)
        if isinstance(requests, list):
            requests.append(request_record)

        if self.path == "/v1/ide/send":
            self._send_json(
                {
                    "ok": True,
                    "action_key": "local-mock-codex-action-1",
                    "conversation": "Local mock Codex bridge accepted draft task.",
                    "metadata": {
                        "ide_name": "Codex",
                        "command_id": "openwukong.sendMessage",
                    },
                }
            )
            return

        if self.path == "/v1/ide/read":
            self._send_json(
                {
                    "ok": True,
                    "conversation": "Local mock Codex bridge ready.",
                    "metadata": {"ide_name": "Codex"},
                }
            )
            return

        if self.path == "/v1/ide/capabilities":
            self._send_json(
                {
                    "ok": True,
                    "metadata": {"ide_name": "Codex"},
                    "commands": ["openwukong.sendMessage"],
                    "chat_adapters": [],
                }
            )
            return

        self._send_json({"ok": False, "error": "mock_bridge_route_not_found"}, status=404)

    def _send_json(self, data: dict, *, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        del format, args


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run isolated L2.5 primary scenario smoke over L1 fixtures."
    )
    parser.add_argument("fixture", help="Path to an L1 primary user scenario fixture JSON file.")
    parser.add_argument(
        "--output-root",
        default="",
        help="Directory for isolated draft artifacts. Defaults to a secure temporary directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--summary-json", action="store_true", help="Print a compact scheduler-friendly JSON summary.")
    parser.add_argument(
        "--allow-owned-browser-helper-launch",
        action="store_true",
        help="Opt in to launching and immediately stopping an isolated Chrome DevTools helper.",
    )
    parser.add_argument(
        "--owned-browser-debug-port",
        type=int,
        default=9238,
        help="DevTools port for the opt-in isolated browser helper.",
    )
    parser.add_argument(
        "--owned-browser-executable",
        default="chrome.exe",
        help="Browser executable for the opt-in isolated helper.",
    )
    parser.add_argument(
        "--owned-browser-url",
        default=_OWNED_BROWSER_HELPER_DEFAULT_URL,
        help="Initial URL for the opt-in isolated browser helper.",
    )
    args = parser.parse_args(argv)

    report = run_primary_scenario_smoke(
        load_simulation_fixture(args.fixture),
        output_root=args.output_root,
        allow_owned_browser_helper_launch=args.allow_owned_browser_helper_launch,
        owned_browser_debug_port=args.owned_browser_debug_port,
        owned_browser_executable=args.owned_browser_executable,
        owned_browser_url=args.owned_browser_url,
    )
    if args.summary_json:
        print(json.dumps(summarize_report(report), ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
