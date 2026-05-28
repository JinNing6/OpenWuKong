# -*- coding: utf-8 -*-
"""Real no-loss probes for the primary user scenarios.

This runner is intentionally stricter than "live automation": every scenario
must either use an owned resource or a read-only probe. It never sends chat
messages, types into user windows, opens user files, modifies user files, or
submits agent tasks.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Callable, Optional

from openwukong.control.session_readiness_plan import (
    SessionReadinessLauncher,
    SessionReadinessTerminator,
)
from openwukong.control.wechat_uia_action import (
    WeChatUiaSemanticActionDryRunAdapter,
    build_wechat_uia_semantic_action_request,
)
from openwukong.evaluation.accessibility_probe import (
    PywinautoAccessibilityObserver,
    WindowsCapabilityProbe,
)
from openwukong.evaluation.ide_bridge_capture import capture_ide_bridge_capabilities
from openwukong.evaluation.office_word_runner import run_office_word_background_probe
from openwukong.evaluation.primary_scenario_smoke import (
    OwnedBrowserHelperActionRunner,
    OwnedBrowserHelperReadinessProbe,
    run_primary_scenario_smoke,
)
from openwukong.evaluation.simulation import (
    L1SimulationHarness,
    load_simulation_fixture,
)
from openwukong.evaluation.wechat_locator import build_wechat_locator_report
from openwukong.evaluation.window_capture import (
    BackgroundWindowCaptureReport,
    PrintWindowBackgroundCaptureProvider,
)


IDEBridgeProbe = Callable[[str], dict]
WordBackgroundProbeRunner = Callable[..., object]
BrowserExecutableResolver = Callable[[str], str]


@dataclasses.dataclass(frozen=True)
class PrimaryRealNoLossCase:
    case_id: str
    scenario_id: str
    status: str
    passed: bool
    real_verified: bool
    real_probe_kind: str
    artifact_path: str = ""
    details: dict = dataclasses.field(default_factory=dict)
    send_attempts: int = 0
    submit_attempts: int = 0
    start_agent_attempts: int = 0
    window_input_attempts: int = 0
    owned_filesystem_scan_attempts: int = 0
    real_user_filesystem_scan_attempts: int = 0
    user_file_modification_attempts: int = 0
    owned_app_launch_attempts: int = 0
    errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "primary-scenario-real-no-loss-case"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self, *, include_details: bool = True) -> dict:
        data = {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "case_id": self.case_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "passed": self.passed,
            "real_verified": self.real_verified,
            "real_probe_kind": self.real_probe_kind,
            "artifact_path": self.artifact_path,
            "send_attempts": self.send_attempts,
            "submit_attempts": self.submit_attempts,
            "start_agent_attempts": self.start_agent_attempts,
            "window_input_attempts": self.window_input_attempts,
            "owned_filesystem_scan_attempts": self.owned_filesystem_scan_attempts,
            "real_user_filesystem_scan_attempts": self.real_user_filesystem_scan_attempts,
            "user_file_modification_attempts": self.user_file_modification_attempts,
            "owned_app_launch_attempts": self.owned_app_launch_attempts,
            "errors": list(self.errors),
        }
        if include_details:
            data["details"] = dict(self.details)
        return data


@dataclasses.dataclass(frozen=True)
class PrimaryRealNoLossReport:
    suite: str
    output_root: str
    cases: tuple[PrimaryRealNoLossCase, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "primary-scenario-real-no-loss"

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
    def external_communication_attempts(self) -> int:
        return sum(case.send_attempts for case in self.cases)

    @property
    def window_input_attempts(self) -> int:
        return sum(case.window_input_attempts for case in self.cases)

    @property
    def uia_semantic_action_ready_cases(self) -> int:
        return sum(
            1
            for case in self.cases
            if bool(case.details.get("uia_semantic_action_ready", False))
        )

    @property
    def uia_value_set_attempts(self) -> int:
        return sum(
            int(
                case.details.get("uia_semantic_action_dry_run", {}).get(
                    "uia_value_set_attempts",
                    0,
                )
                or 0
            )
            for case in self.cases
        )

    @property
    def uia_invoke_attempts(self) -> int:
        return sum(
            int(
                case.details.get("uia_semantic_action_dry_run", {}).get(
                    "uia_invoke_attempts",
                    0,
                )
                or 0
            )
            for case in self.cases
        )

    @property
    def real_user_filesystem_scan_attempts(self) -> int:
        return sum(case.real_user_filesystem_scan_attempts for case in self.cases)

    @property
    def user_file_modification_attempts(self) -> int:
        return sum(case.user_file_modification_attempts for case in self.cases)

    @property
    def owned_app_launch_attempts(self) -> int:
        return sum(case.owned_app_launch_attempts for case in self.cases)

    @property
    def background_screenshot_count(self) -> int:
        return sum(_case_background_screenshot_count(case) for case in self.cases)

    @property
    def background_screenshot_success_count(self) -> int:
        return sum(_case_background_screenshot_success_count(case) for case in self.cases)

    @property
    def background_screenshot_focus_stable(self) -> bool:
        return not any(_case_background_screenshot_focus_changed(case) for case in self.cases)

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
    def real_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.real_verified)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "suite": self.suite,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "external_communication_attempts": self.external_communication_attempts,
            "window_input_attempts": self.window_input_attempts,
            "uia_semantic_action_ready_cases": self.uia_semantic_action_ready_cases,
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
            "real_user_filesystem_scan_attempts": self.real_user_filesystem_scan_attempts,
            "user_file_modification_attempts": self.user_file_modification_attempts,
            "owned_app_launch_attempts": self.owned_app_launch_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "output_root": self.output_root,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "real_verified_cases": self.real_verified_cases,
            "cases": [case.to_dict() for case in self.cases],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_primary_real_no_loss(
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
    owned_browser_url: str = "",
    browser_executable_resolver: BrowserExecutableResolver | None = None,
    accessibility_observer: object | None = None,
    wechat_win32_observer: object | None = None,
    ide_bridge_urls: tuple[str, ...] = ("http://127.0.0.1:8787",),
    ide_bridge_probe: IDEBridgeProbe | None = None,
    word_background_probe_runner: WordBackgroundProbeRunner | None = None,
    background_screenshot_dir: str | Path = "",
    window_capture_provider: object | None = None,
) -> PrimaryRealNoLossReport:
    started = time.perf_counter()
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    active_harness = harness or L1SimulationHarness()
    l1_report = active_harness.run_suite(fixture)
    plans = [
        _plan_row(result.to_dict())
        for result in l1_report.results
    ]
    browser_smoke_cases = _browser_smoke_cases(
        fixture,
        output_root=root,
        allow_owned_browser_helper_launch=allow_owned_browser_helper_launch,
        owned_browser_helper_launcher=owned_browser_helper_launcher,
        owned_browser_helper_terminator=owned_browser_helper_terminator,
        owned_browser_helper_readiness_probe=owned_browser_helper_readiness_probe,
        owned_browser_helper_action_runner=owned_browser_helper_action_runner,
        owned_browser_debug_port=owned_browser_debug_port,
        owned_browser_executable=_resolve_requested_browser_executable(
            owned_browser_executable,
            browser_executable_resolver,
        ),
        owned_browser_url=owned_browser_url,
    )

    cases: list[PrimaryRealNoLossCase] = []
    for row in plans:
        scenario_id = str(row["plan"].get("scenario_id", "") or "")
        if scenario_id == "browser.research.collect_sources":
            case = _browser_case(row, root, browser_smoke_cases)
        elif scenario_id == "wechat.chat.draft_reply":
            case = _wechat_case(
                row,
                root,
                accessibility_observer,
                wechat_win32_observer,
                background_screenshot_dir,
                window_capture_provider,
            )
        elif scenario_id == "files.search.find_candidate":
            case = _file_case(row, root)
        elif scenario_id == "word.document.create_background":
            case = _word_case(row, root, word_background_probe_runner)
        elif scenario_id == "codex.project.submit_task_draft":
            case = _codex_case(row, root, ide_bridge_urls, ide_bridge_probe)
        else:
            case = _generic_unavailable_case(row, root)
        cases.append(_write_case_artifact(root, case))

    return PrimaryRealNoLossReport(
        suite=str(l1_report.suite),
        output_root=str(root),
        cases=tuple(cases),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _resolve_requested_browser_executable(
    requested: str,
    resolver: BrowserExecutableResolver | None,
) -> str:
    text = str(requested or "").strip() or "chrome.exe"
    if callable(resolver):
        resolved = str(resolver(text) or "").strip()
        return resolved or text
    return text


def _resolve_installed_browser_executable(
    requested: str,
    *,
    resolver: object | None = None,
) -> str:
    text = str(requested or "").strip() or "chrome.exe"
    path = Path(text)
    if path.is_file():
        return str(path.resolve())
    if path.is_absolute() and not path.exists():
        return text
    requested_name = path.name.lower()
    if requested_name not in {"chrome.exe", "msedge.exe", "browser"}:
        return text

    active_resolver = resolver
    if active_resolver is None:
        from openwukong.control.app_resolution import WindowsAppResolver

        active_resolver = WindowsAppResolver()

    app_names = ("edge",) if requested_name == "msedge.exe" else ("chrome", "edge")
    for app_name in app_names:
        try:
            report = active_resolver.resolve(app_name)
        except Exception:
            continue
        executable = _first_existing_executable_from_resolution(report)
        if executable:
            return executable
    return text


def _first_existing_executable_from_resolution(resolution: object) -> str:
    selected = getattr(resolution, "selected_candidate", None)
    candidates = getattr(resolution, "candidates", ()) or ()
    for candidate in (selected, *tuple(candidates)):
        if candidate is None:
            continue
        path = Path(str(getattr(candidate, "path", "") or ""))
        if path.is_file() and path.suffix.lower() == ".exe":
            return str(path.resolve())
    return ""


def summarize_report(report: PrimaryRealNoLossReport) -> dict:
    return {
        "mode": "primary-scenario-real-no-loss-summary",
        "suite": report.suite,
        "safety_mode": report.safety_mode,
        "control_allowed": report.control_allowed,
        "control_attempts": report.control_attempts,
        "external_communication_attempts": report.external_communication_attempts,
        "window_input_attempts": report.window_input_attempts,
        "uia_semantic_action_ready_cases": report.uia_semantic_action_ready_cases,
        "uia_value_set_attempts": report.uia_value_set_attempts,
        "uia_invoke_attempts": report.uia_invoke_attempts,
        "real_user_filesystem_scan_attempts": report.real_user_filesystem_scan_attempts,
        "user_file_modification_attempts": report.user_file_modification_attempts,
        "owned_app_launch_attempts": report.owned_app_launch_attempts,
        "background_screenshot_count": report.background_screenshot_count,
        "background_screenshot_success_count": report.background_screenshot_success_count,
        "background_screenshot_focus_stable": report.background_screenshot_focus_stable,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "real_verified_cases": report.real_verified_cases,
        "scenarios": [
            case.to_dict(include_details=False)
            for case in report.cases
        ],
    }


def _plan_row(result: dict) -> dict:
    return {
        "case_id": str(result.get("case_id", "") or "unnamed-case"),
        "source_l1_passed": bool(result.get("passed", False)),
        "plan": dict(result.get("primary_scenario_plan", {}) or {}),
    }


def _browser_smoke_cases(
    fixture: dict,
    *,
    output_root: Path,
    allow_owned_browser_helper_launch: bool,
    owned_browser_helper_launcher: SessionReadinessLauncher | None,
    owned_browser_helper_terminator: SessionReadinessTerminator | None,
    owned_browser_helper_readiness_probe: OwnedBrowserHelperReadinessProbe | None,
    owned_browser_helper_action_runner: OwnedBrowserHelperActionRunner | None,
    owned_browser_debug_port: int,
    owned_browser_executable: str,
    owned_browser_url: str,
) -> dict[str, dict]:
    report = run_primary_scenario_smoke(
        fixture,
        output_root=output_root / "owned_browser_primary_smoke",
        allow_owned_browser_helper_launch=allow_owned_browser_helper_launch,
        owned_browser_helper_launcher=owned_browser_helper_launcher,
        owned_browser_helper_terminator=owned_browser_helper_terminator,
        owned_browser_helper_readiness_probe=owned_browser_helper_readiness_probe,
        owned_browser_helper_action_runner=owned_browser_helper_action_runner,
        owned_browser_debug_port=owned_browser_debug_port,
        owned_browser_executable=owned_browser_executable,
        owned_browser_url=owned_browser_url,
    )
    return {case.case_id: case.to_dict() for case in report.cases}


def _browser_case(
    row: dict,
    output_root: Path,
    browser_smoke_cases: dict[str, dict],
) -> PrimaryRealNoLossCase:
    case_id = str(row["case_id"])
    smoke_case = browser_smoke_cases.get(case_id, {})
    helper_path = str(smoke_case.get("owned_browser_helper_artifact_path", "") or "")
    if not helper_path:
        return PrimaryRealNoLossCase(
            case_id=case_id,
            scenario_id="browser.research.collect_sources",
            status="skipped_requires_owned_browser_helper_opt_in",
            passed=True,
            real_verified=False,
            real_probe_kind="owned-browser-devtools-read-page",
            details={"reason": "allow_owned_browser_helper_launch was false"},
        )
    try:
        helper = json.loads(Path(helper_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return PrimaryRealNoLossCase(
            case_id=case_id,
            scenario_id="browser.research.collect_sources",
            status="failed",
            passed=False,
            real_verified=False,
            real_probe_kind="owned-browser-devtools-read-page",
            errors=(f"helper_artifact_read_failed:{exc}",),
            owned_app_launch_attempts=1,
        )
    action = dict(helper.get("owned_browser_action", {}) or {})
    action_report = dict(action.get("action_report", {}) or {})
    action_result = dict(action_report.get("action_result", {}) or {})
    ok = (
        helper.get("status") == "started_and_stopped"
        and bool(helper.get("readiness_probe", {}).get("target_match_ok", False))
        and bool(action.get("ok", False))
        and int(helper.get("owned_browser_action_control_attempts", 0) or 0) == 0
    )
    return PrimaryRealNoLossCase(
        case_id=case_id,
        scenario_id="browser.research.collect_sources",
        status="verified" if ok else "failed",
        passed=ok,
        real_verified=ok,
        real_probe_kind="owned-browser-devtools-read-page",
        owned_app_launch_attempts=1,
        details={
            "helper_artifact_path": helper_path,
            "helper_status": str(helper.get("status", "") or ""),
            "target_match_ok": bool(helper.get("readiness_probe", {}).get("target_match_ok", False)),
            "action": str(action_report.get("action", "") or ""),
            "action_title": str(action_result.get("title", "") or ""),
            "action_text_excerpt": str(action_result.get("textExcerpt", "") or "")[:500],
        },
        errors=tuple(str(item) for item in helper.get("errors", []) or []),
    )


def _wechat_case(
    row: dict,
    output_root: Path,
    accessibility_observer: object | None,
    wechat_win32_observer: object | None,
    background_screenshot_dir: str | Path,
    window_capture_provider: object | None,
) -> PrimaryRealNoLossCase:
    observer = accessibility_observer or PywinautoAccessibilityObserver(
        max_windows=40,
        max_elements_per_window=120,
    )
    report = WindowsCapabilityProbe(observer=observer).run()
    matches = [
        window
        for window in report.windows
        if _is_wechat_window(window.process_name, window.window_title)
    ]
    locator = build_wechat_locator_report(
        matches,
        win32_observer=wechat_win32_observer,
    )
    screenshot_root = _resolve_background_screenshot_dir(
        background_screenshot_dir,
        output_root=output_root,
        case_id=str(row["case_id"]),
    )
    background_screenshots = _capture_background_screenshots(
        matches,
        screenshot_dir=screenshot_root,
        window_capture_provider=window_capture_provider,
    )
    background_focus_stable = not any(
        item.foreground_changed for item in background_screenshots
    )
    semantic_action_dry_run = _wechat_uia_semantic_action_dry_run(
        row,
        matches,
        background_screenshot_focus_stable=background_focus_stable,
    )
    details = {
        "matching_window_count": len(matches),
        "windows": [
            window.to_dict(include_elements=False)
            for window in matches
        ],
        "locator": locator.to_dict(include_children=False),
        "background_screenshot_count": len(background_screenshots),
        "background_screenshot_success_count": sum(
            1 for item in background_screenshots if item.ok
        ),
        "background_screenshot_focus_stable": background_focus_stable,
        "background_screenshots": [
            item.to_dict() for item in background_screenshots
        ],
        "uia_semantic_action_ready": bool(semantic_action_dry_run.get("ok", False)),
        "uia_semantic_action_dry_run": semantic_action_dry_run,
        "total_scanned_windows": report.window_count,
        "total_scanned_elements": report.total_elements,
    }
    return PrimaryRealNoLossCase(
        case_id=str(row["case_id"]),
        scenario_id="wechat.chat.draft_reply",
        status="verified" if matches else "unavailable",
        passed=True,
        real_verified=bool(matches),
        real_probe_kind="wechat-uia-win32-read-only-locator",
        details=details,
        send_attempts=0,
        window_input_attempts=0,
    )


def _wechat_uia_semantic_action_dry_run(
    row: dict,
    matches: list[object],
    *,
    background_screenshot_focus_stable: bool,
) -> dict:
    plan = dict(row.get("plan", {}) or {})
    intent = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    target_name = str(
        intent.get("contact", "")
        or intent.get("target_name", "")
        or intent.get("recipient", "")
        or ""
    ).strip()
    message = str(intent.get("message", "") or "").strip()
    request = build_wechat_uia_semantic_action_request(
        target_name=target_name,
        message=message,
        windows=tuple(matches),
        background_screenshot_focus_stable=background_screenshot_focus_stable,
        selected_transport={
            "transport_id": "wechat-uia-semantic-dry-run",
            "transport_channel": "uia",
            "safety_mode": "dry_run",
        },
    )
    return WeChatUiaSemanticActionDryRunAdapter().prepare(request).to_dict()


def _file_case(row: dict, output_root: Path) -> PrimaryRealNoLossCase:
    case_id = str(row["case_id"])
    plan = dict(row["plan"])
    intent = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    query = str(intent.get("query", "") or "openwukong")
    owned_root = output_root / "owned_file_search" / _safe_filename(case_id)
    owned_root.mkdir(parents=True, exist_ok=True)
    seed_files = {
        "openwukong-plan.md": "# openwukong plan\nreal no-loss primary scenario probe\n",
        "openwukong-index.json": json.dumps(
            {"project": "openwukong", "probe": "real-no-loss"},
            ensure_ascii=False,
        ),
        "unrelated.txt": "not a candidate\n",
    }
    for filename, content in seed_files.items():
        (owned_root / filename).write_text(content, encoding="utf-8")

    candidate_paths = _search_owned_files(owned_root, query)
    return PrimaryRealNoLossCase(
        case_id=case_id,
        scenario_id="files.search.find_candidate",
        status="verified" if candidate_paths else "failed",
        passed=bool(candidate_paths),
        real_verified=bool(candidate_paths),
        real_probe_kind="owned-filesystem-temp-index",
        owned_filesystem_scan_attempts=1,
        real_user_filesystem_scan_attempts=0,
        user_file_modification_attempts=0,
        details={
            "owned_root": str(owned_root),
            "query": query,
            "created_file_count": len(seed_files),
            "candidate_count": len(candidate_paths),
            "candidate_paths": [str(path) for path in candidate_paths],
        },
    )


def _codex_case(
    row: dict,
    output_root: Path,
    ide_bridge_urls: tuple[str, ...],
    ide_bridge_probe: IDEBridgeProbe | None,
) -> PrimaryRealNoLossCase:
    plan = dict(row["plan"])
    intent = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    workspace = str(intent.get("workspace", "") or output_root)
    reports: list[dict] = []
    active_probe = ide_bridge_probe or (
        lambda url: capture_ide_bridge_capabilities(
            url,
            workspace_path=workspace,
            request_timeout=0.3,
        ).to_dict()
    )
    for bridge_url in ide_bridge_urls:
        data = active_probe(str(bridge_url))
        reports.append(dict(data) if isinstance(data, dict) else {"ok": False, "error": "invalid_probe_result"})
        if reports[-1].get("ok"):
            break

    ok_reports = [report for report in reports if report.get("ok")]
    ok = bool(ok_reports)
    return PrimaryRealNoLossCase(
        case_id=str(row["case_id"]),
        scenario_id="codex.project.submit_task_draft",
        status="verified" if ok else "unavailable",
        passed=True,
        real_verified=ok,
        real_probe_kind="ide-bridge-capabilities-read-only",
        submit_attempts=0,
        start_agent_attempts=0,
        details={
            "workspace": workspace,
            "probed_bridge_urls": list(ide_bridge_urls),
            "ok_bridge_url": str(ok_reports[0].get("bridge_url", "")) if ok_reports else "",
            "reports": reports,
        },
    )


def _word_case(
    row: dict,
    output_root: Path,
    word_background_probe_runner: WordBackgroundProbeRunner | None,
) -> PrimaryRealNoLossCase:
    case_id = str(row["case_id"])
    plan = dict(row["plan"])
    intent = dict(plan.get("draft_action", {}).get("intent", {}) or {})
    marker = str(intent.get("marker", "") or "OPENWUKONG_WORD_PRIMARY_SCENARIO")
    document_name = str(
        intent.get("document_name", "") or "openwukong-word-primary-scenario.docx"
    )
    document_path = output_root / "word" / _safe_filename(case_id) / _safe_filename(document_name)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    runner = word_background_probe_runner or run_office_word_background_probe
    raw_report = runner(document_path=str(document_path), marker=marker)
    report_data = _report_to_dict(raw_report)
    ok = bool(report_data.get("ok", False))
    errors: tuple[str, ...] = ()
    error_text = str(report_data.get("error", "") or "").strip()
    if error_text:
        errors = (error_text,)
    return PrimaryRealNoLossCase(
        case_id=case_id,
        scenario_id="word.document.create_background",
        status="verified" if ok else str(report_data.get("decision", "") or "failed"),
        passed=ok,
        real_verified=ok,
        real_probe_kind="office-word-com-owned-document-background",
        details={
            "document_path": str(report_data.get("document_path", "") or document_path),
            "marker": str(report_data.get("marker", "") or marker),
            "decision": str(report_data.get("decision", "") or ""),
            "save_verified": bool(report_data.get("save_verified", False)),
            "readback_verified": bool(report_data.get("readback_verified", False)),
            "word_started": bool(report_data.get("word_started", False)),
            "visible_requested": bool(report_data.get("visible_requested", False)),
            "control_attempts": int(report_data.get("control_attempts", 0) or 0),
            "window_input_attempts": int(report_data.get("window_input_attempts", 0) or 0),
            "office_com_attempts": int(report_data.get("office_com_attempts", 0) or 0),
        },
        window_input_attempts=int(report_data.get("window_input_attempts", 0) or 0),
        user_file_modification_attempts=0,
        errors=errors,
    )


def _generic_unavailable_case(row: dict, output_root: Path) -> PrimaryRealNoLossCase:
    del output_root
    plan = dict(row["plan"])
    return PrimaryRealNoLossCase(
        case_id=str(row["case_id"]),
        scenario_id=str(plan.get("scenario_id", "") or ""),
        status="unavailable",
        passed=True,
        real_verified=False,
        real_probe_kind="none",
        details={"reason": "unsupported primary real no-loss scenario"},
    )


def _write_case_artifact(output_root: Path, case: PrimaryRealNoLossCase) -> PrimaryRealNoLossCase:
    artifact_dir = output_root / "real_no_loss"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_filename(case.case_id)}.json"
    data = case.to_dict()
    artifact_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return dataclasses.replace(case, artifact_path=str(artifact_path))


def _search_owned_files(root: Path, query: str) -> list[Path]:
    terms = [
        term.lower()
        for term in str(query or "").replace("/", " ").replace("\\", " ").split()
        if term.strip()
    ]
    if not terms:
        terms = ["openwukong"]
    candidates: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        haystack = f"{path.name.lower()} {text}"
        if any(term in haystack for term in terms):
            candidates.append(path.resolve())
    return candidates


def _is_wechat_window(process_name: str, window_title: str) -> bool:
    process = str(process_name or "").lower()
    title = str(window_title or "").lower()
    if process in {"wxwork.exe"}:
        return False
    if any(
        marker in title
        for marker in ("企业微信", "浼佷笟寰", "wecom", "wxwork", "enterprise wechat")
    ):
        return False
    return process in {"wechat.exe", "weixin.exe"} or "微信" in title or "wechat" in title


def _resolve_background_screenshot_dir(
    screenshot_dir: str | Path,
    *,
    output_root: Path,
    case_id: str,
) -> Path | None:
    text = str(screenshot_dir or "").strip()
    if not text:
        return None
    root = Path(text).expanduser()
    if not root.is_absolute():
        root = root.resolve()
    return root.resolve() / _safe_filename(case_id)


def _capture_background_screenshots(
    windows: list[object],
    *,
    screenshot_dir: Path | None,
    window_capture_provider: object | None,
) -> tuple[BackgroundWindowCaptureReport, ...]:
    if screenshot_dir is None:
        return ()
    provider = window_capture_provider or PrintWindowBackgroundCaptureProvider()
    capture = getattr(provider, "capture_window", None)
    if not callable(capture):
        return ()
    reports: list[BackgroundWindowCaptureReport] = []
    for index, window in enumerate(windows, start=1):
        hwnd = int(getattr(window, "hwnd", 0) or 0)
        if hwnd <= 0:
            continue
        process_name = str(getattr(window, "process_name", "") or "window")
        pid = int(getattr(window, "pid", 0) or 0)
        output_path = screenshot_dir / _safe_filename(
            f"{index:02d}-{process_name}-{pid}-{hwnd}"
        )
        output_path = output_path.with_suffix(".png")
        try:
            result = capture(hwnd, output_path)
        except Exception as exc:
            result = BackgroundWindowCaptureReport(
                hwnd=hwnd,
                output_path=str(output_path),
                ok=False,
                error=f"capture_exception:{type(exc).__name__}",
            )
        if isinstance(result, BackgroundWindowCaptureReport):
            reports.append(result)
        else:
            reports.append(
                BackgroundWindowCaptureReport(
                    hwnd=hwnd,
                    output_path=str(output_path),
                    ok=False,
                    error="invalid_capture_report",
                )
            )
    return tuple(reports)


def _case_background_screenshot_count(case: PrimaryRealNoLossCase) -> int:
    return int(case.details.get("background_screenshot_count", 0) or 0)


def _case_background_screenshot_success_count(case: PrimaryRealNoLossCase) -> int:
    return int(case.details.get("background_screenshot_success_count", 0) or 0)


def _case_background_screenshot_focus_changed(case: PrimaryRealNoLossCase) -> bool:
    for item in case.details.get("background_screenshots", []) or []:
        if isinstance(item, dict) and bool(item.get("foreground_changed", False)):
            return True
    return False


def _resolve_output_root(output_root: str | Path) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve()
    return (Path("logs") / "runtime" / "primary-real-no-loss").resolve()


def _safe_filename(value: str) -> str:
    text = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in str(value or "").strip()
    )
    return text.strip("._") or "unnamed"


def _report_to_dict(report: object) -> dict:
    if isinstance(report, dict):
        return dict(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {"ok": False, "error": "invalid_word_probe_report"}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run real no-loss probes for primary user scenarios."
    )
    parser.add_argument("fixture", help="Path to an L1 primary user scenario fixture JSON file.")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-owned-browser-helper-launch", action="store_true")
    parser.add_argument("--owned-browser-debug-port", type=int, default=9238)
    parser.add_argument("--owned-browser-executable", default="chrome.exe")
    parser.add_argument("--owned-browser-url", default="")
    parser.add_argument("--ide-bridge-url", action="append", default=None)
    parser.add_argument("--background-screenshot-dir", default="")
    args = parser.parse_args(argv)

    report = run_primary_real_no_loss(
        load_simulation_fixture(args.fixture),
        output_root=args.output_root,
        allow_owned_browser_helper_launch=args.allow_owned_browser_helper_launch,
        owned_browser_debug_port=args.owned_browser_debug_port,
        owned_browser_executable=args.owned_browser_executable,
        owned_browser_url=args.owned_browser_url,
        browser_executable_resolver=_resolve_installed_browser_executable,
        ide_bridge_urls=tuple(args.ide_bridge_url or ("http://127.0.0.1:8787",)),
        background_screenshot_dir=args.background_screenshot_dir,
    )
    if args.summary_json:
        print(json.dumps(summarize_report(report), ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            "Primary real no-loss: "
            f"{report.passed_cases}/{report.total_cases} no-loss passed, "
            f"real_verified={report.real_verified_cases}"
        )
    return 0 if report.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
