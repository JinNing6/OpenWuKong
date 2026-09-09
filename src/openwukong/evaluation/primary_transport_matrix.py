# -*- coding: utf-8 -*-
"""Plan-only transport matrix for primary desktop scenarios."""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Iterable


BACKGROUND_NATIVE = "background-native"
BACKGROUND_READ_ONLY = "background-read-only"
FOREGROUND_REQUIRED = "foreground-required"
BLOCKED = "blocked"


@dataclasses.dataclass(frozen=True)
class PrimaryScenarioTransportEntry:
    scenario_id: str
    case_id: str
    surface: str
    required_action: str
    selected_transport: str
    transport_channel: str
    capability_level: str
    operation_scope: str
    ready: bool = False
    requires_background_write: bool = False
    can_execute_without_focus: bool = False
    can_write_without_focus: bool = False
    requires_user_confirmation: bool = False
    blocking_reason: str = ""
    risk_flags: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    fallback_transports: tuple[str, ...] = ()
    evidence: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "case_id": self.case_id,
            "surface": self.surface,
            "required_action": self.required_action,
            "selected_transport": self.selected_transport,
            "transport_channel": self.transport_channel,
            "capability_level": self.capability_level,
            "operation_scope": self.operation_scope,
            "ready": self.ready,
            "requires_background_write": self.requires_background_write,
            "can_execute_without_focus": self.can_execute_without_focus,
            "can_write_without_focus": self.can_write_without_focus,
            "requires_user_confirmation": self.requires_user_confirmation,
            "blocking_reason": self.blocking_reason,
            "risk_flags": list(self.risk_flags),
            "verification_requirements": list(self.verification_requirements),
            "fallback_transports": list(self.fallback_transports),
            "evidence": dict(self.evidence),
        }


@dataclasses.dataclass(frozen=True)
class PrimaryScenarioTransportMatrixReport:
    scenarios: tuple[PrimaryScenarioTransportEntry, ...]

    @property
    def mode(self) -> str:
        return "primary-scenario-transport-matrix"

    @property
    def safety_mode(self) -> str:
        return "plan_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def goal_complete(self) -> bool:
        return bool(
            self.scenarios
            and all(item.can_execute_without_focus for item in self.scenarios)
            and all(
                item.can_write_without_focus
                for item in self.scenarios
                if item.requires_background_write
            )
            and not any(item.capability_level == BLOCKED for item in self.scenarios)
        )

    def summary(self) -> dict:
        levels = Counter(item.capability_level for item in self.scenarios)
        selected = Counter(item.selected_transport or "none" for item in self.scenarios)
        return {
            "scenario_count": len(self.scenarios),
            "goal_complete": self.goal_complete,
            "background_execute_ready_cases": sum(
                1 for item in self.scenarios if item.can_execute_without_focus
            ),
            "background_write_ready_cases": sum(
                1
                for item in self.scenarios
                if item.requires_background_write and item.can_write_without_focus
            ),
            "background_read_only_cases": levels.get(BACKGROUND_READ_ONLY, 0),
            "foreground_required_cases": levels.get(FOREGROUND_REQUIRED, 0),
            "blocked_cases": levels.get(BLOCKED, 0),
            "write_blocked_cases": sum(
                1
                for item in self.scenarios
                if item.requires_background_write and not item.can_write_without_focus
            ),
            "selected_transport_counts": dict(sorted(selected.items())),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "goal_complete": self.goal_complete,
            "summary": self.summary(),
            "scenarios": [item.to_dict() for item in self.scenarios],
        }


def build_primary_transport_matrix(
    cases: Iterable[dict | object],
) -> PrimaryScenarioTransportMatrixReport:
    entries = tuple(_entry_for_case(_case_dict(case)) for case in cases)
    return PrimaryScenarioTransportMatrixReport(scenarios=entries)


def _entry_for_case(case: dict) -> PrimaryScenarioTransportEntry:
    scenario_id = str(case.get("scenario_id", "") or "")
    if scenario_id == "wechat.chat.draft_reply":
        return _wechat_entry(case)
    if scenario_id == "browser.research.collect_sources":
        return _browser_entry(case)
    if scenario_id == "files.search.find_candidate":
        return _file_entry(case)
    if scenario_id == "word.document.create_background":
        return _word_entry(case)
    if scenario_id == "codex.project.submit_task_draft":
        return _codex_entry(case)
    return _generic_entry(case)


def _wechat_entry(case: dict) -> PrimaryScenarioTransportEntry:
    details = _details(case)
    matching_window_count = int(details.get("matching_window_count", 0) or 0)
    screenshot_focus_stable = bool(details.get("background_screenshot_focus_stable", True))
    background_send_verified = bool(details.get("background_send_verified", False))
    native_bridge_ready = bool(details.get("wechat_native_bridge_ready", False))
    semantic_ready = bool(details.get("uia_semantic_action_ready", False))
    computer_use_probe = _dict_value(details.get("computer_use_probe"))
    computer_use_ready = bool(details.get("computer_use_read_only_ready", False))

    fallbacks = [
        "wechat-native-bridge",
        "uia-semantic-dry-run",
        "win32-msaa-read-only",
    ]
    if computer_use_probe or computer_use_ready:
        fallbacks.append("computer-use-window2")
    fallbacks.append("foreground-request")

    if matching_window_count <= 0 or not bool(case.get("real_verified", False)):
        return _entry(
            case,
            surface="wechat",
            required_action="send_message",
            selected_transport="none",
            transport_channel="none",
            capability_level=BLOCKED,
            operation_scope="send-readback",
            requires_background_write=True,
            blocking_reason="wechat_window_unavailable",
            risk_flags=("external_communication_surface", "target_window_missing"),
            fallback_transports=fallbacks,
        )

    risk_flags = [
        "external_communication_surface",
    ]
    if not native_bridge_ready and not background_send_verified:
        risk_flags.append("native_bridge_required_for_write")
    if bool(computer_use_probe.get("input_actions_activate_window", True)):
        risk_flags.append("computer_use_input_activates_window")
    if not screenshot_focus_stable:
        risk_flags.append("background_focus_unstable")

    if background_send_verified:
        return _entry(
            case,
            surface="wechat",
            required_action="send_message",
            selected_transport=_verified_wechat_send_transport(details),
            transport_channel="native_or_accessibility",
            capability_level=BACKGROUND_NATIVE,
            operation_scope="send-readback",
            ready=True,
            requires_background_write=True,
            can_execute_without_focus=True,
            can_write_without_focus=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "readback_markers",
                "no_window_input",
                "foreground_stability",
            ),
            fallback_transports=fallbacks,
            risk_flags=risk_flags,
            evidence=_wechat_evidence(details),
        )

    if native_bridge_ready:
        return _entry(
            case,
            surface="wechat",
            required_action="send_message",
            selected_transport="wechat-native-bridge",
            transport_channel="native_bridge",
            capability_level=BACKGROUND_NATIVE,
            operation_scope="send-dry-run-ready",
            ready=True,
            requires_background_write=True,
            can_execute_without_focus=True,
            can_write_without_focus=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "native_bridge_capability_ok",
                "readback_markers",
                "no_window_input",
            ),
            fallback_transports=fallbacks,
            risk_flags=risk_flags,
            evidence=_wechat_evidence(details),
        )

    return _entry(
        case,
        surface="wechat",
        required_action="send_message",
        selected_transport=(
            "wechat-uia-semantic-dry-run" if semantic_ready else "wechat-read-only-locator"
        ),
        transport_channel="accessibility",
        capability_level=BACKGROUND_READ_ONLY,
        operation_scope="inspect-or-dry-run-only",
        ready=True,
        requires_background_write=True,
        can_execute_without_focus=True,
        can_write_without_focus=False,
        requires_user_confirmation=True,
        blocking_reason="wechat_native_bridge_required_for_background_send",
        risk_flags=risk_flags,
        verification_requirements=(
            "native_bridge_or_verified_uia_send_required",
            "post_send_readback_required",
            "no_window_input",
        ),
        fallback_transports=fallbacks,
        evidence=_wechat_evidence(details),
    )


def _browser_entry(case: dict) -> PrimaryScenarioTransportEntry:
    details = _details(case)
    ok = bool(case.get("real_verified", False)) and bool(details.get("target_match_ok", True))
    if not ok:
        return _entry(
            case,
            surface="browser",
            required_action="read_page",
            selected_transport="none",
            transport_channel="none",
            capability_level=BLOCKED,
            operation_scope="read-page",
            blocking_reason="owned_browser_devtools_not_verified",
            risk_flags=("owned_browser_helper_required",),
        )
    return _entry(
        case,
        surface="browser",
        required_action="read_page",
        selected_transport="browser-devtools-owned",
        transport_channel="chrome_devtools_protocol",
        capability_level=BACKGROUND_NATIVE,
        operation_scope="read-page",
        ready=True,
        can_execute_without_focus=True,
        verification_requirements=("cdp_target_match", "dom_readback"),
        fallback_transports=("browser-extension", "foreground-request"),
        evidence={
            "real_probe_kind": str(case.get("real_probe_kind", "") or ""),
            "owned_app_launch_attempts": _counter(case, "owned_app_launch_attempts"),
            "action": str(details.get("action", "") or ""),
        },
    )


def _file_entry(case: dict) -> PrimaryScenarioTransportEntry:
    details = _details(case)
    ok = bool(case.get("real_verified", False)) and int(details.get("candidate_count", 0) or 0) > 0
    if not ok:
        return _entry(
            case,
            surface="filesystem",
            required_action="find_file",
            selected_transport="none",
            transport_channel="none",
            capability_level=BLOCKED,
            operation_scope="owned-index-search",
            blocking_reason="owned_filesystem_index_not_verified",
        )
    return _entry(
        case,
        surface="filesystem",
        required_action="find_file",
        selected_transport="owned-filesystem-index",
        transport_channel="filesystem_api",
        capability_level=BACKGROUND_NATIVE,
        operation_scope="owned-index-search",
        ready=True,
        can_execute_without_focus=True,
        verification_requirements=("owned_root_boundary", "candidate_readback"),
        fallback_transports=("windows-search-index", "foreground-request"),
        evidence={
            "owned_filesystem_scan_attempts": _counter(case, "owned_filesystem_scan_attempts"),
            "candidate_count": int(details.get("candidate_count", 0) or 0),
        },
    )


def _word_entry(case: dict) -> PrimaryScenarioTransportEntry:
    details = _details(case)
    foreground_no_steal = bool(details.get("foreground_no_steal_verified", True))
    foreground_focus_stable = bool(details.get("foreground_focus_stable", True))
    risk_flags = ["document_write_surface"]
    if not foreground_no_steal or not foreground_focus_stable:
        risk_flags.append("foreground_focus_unstable")
    ok = bool(
        case.get("real_verified", False)
        and details.get("decision") == "word_background_probe_verified"
        and bool(details.get("save_verified", False))
        and bool(details.get("readback_verified", False))
        and _counter(details, "window_input_attempts") == 0
        and foreground_no_steal
    )
    if not ok:
        return _entry(
            case,
            surface="word",
            required_action="create_document",
            selected_transport="none",
            transport_channel="none",
            capability_level=BLOCKED,
            operation_scope="owned-document-create",
            requires_background_write=True,
            blocking_reason="office_word_com_not_verified",
            risk_flags=risk_flags,
            evidence=_word_evidence(details),
        )
    return _entry(
        case,
        surface="word",
        required_action="create_document",
        selected_transport="office-word-com",
        transport_channel="office_com",
        capability_level=BACKGROUND_NATIVE,
        operation_scope="owned-document-create",
        ready=True,
        requires_background_write=True,
        can_execute_without_focus=True,
        can_write_without_focus=True,
        verification_requirements=("save_verified", "object_model_readback", "no_window_input"),
        fallback_transports=("office-js-addin", "foreground-request"),
        evidence=_word_evidence(details),
    )


def _word_evidence(details: dict) -> dict:
    return {
        "office_com_attempts": _counter(details, "office_com_attempts"),
        "visible_requested": bool(details.get("visible_requested", False)),
        "window_input_attempts": _counter(details, "window_input_attempts"),
        "foreground_focus_stable": bool(details.get("foreground_focus_stable", True)),
        "foreground_no_steal_verified": bool(
            details.get("foreground_no_steal_verified", True)
        ),
        "foreground_change_classification": str(
            details.get("foreground_change_classification", "") or "stable"
        ),
    }


def _codex_entry(case: dict) -> PrimaryScenarioTransportEntry:
    details = _details(case)
    reports = [_dict_value(item) for item in _list_value(details.get("reports"))]
    bridge_ready = bool(details.get("ok_bridge_url", "")) or any(
        bool(report.get("ok", False)) for report in reports
    )
    submit_verified = bool(details.get("background_submit_verified", False))
    if submit_verified:
        return _entry(
            case,
            surface="codex",
            required_action="submit_project_task",
            selected_transport="ide-bridge-submit-task",
            transport_channel="ide_extension_bridge",
            capability_level=BACKGROUND_NATIVE,
            operation_scope="submit-readback",
            ready=True,
            requires_background_write=True,
            can_execute_without_focus=True,
            can_write_without_focus=True,
            requires_user_confirmation=True,
            verification_requirements=("bridge_submit_result", "task_readback", "no_window_input"),
            fallback_transports=("codex-cli-managed-terminal", "foreground-request"),
            evidence=_codex_evidence(details, reports),
        )
    if bridge_ready:
        return _entry(
            case,
            surface="codex",
            required_action="submit_project_task",
            selected_transport="ide-bridge-capabilities-read-only",
            transport_channel="ide_extension_bridge",
            capability_level=BACKGROUND_READ_ONLY,
            operation_scope="capability-capture-only",
            ready=True,
            requires_background_write=True,
            can_execute_without_focus=True,
            can_write_without_focus=False,
            requires_user_confirmation=True,
            blocking_reason="ide_task_submit_not_verified",
            risk_flags=("agent_task_surface", "submit_not_executed"),
            verification_requirements=("bridge_submit_probe_required", "task_readback_required"),
            fallback_transports=("codex-cli-managed-terminal", "foreground-request"),
            evidence=_codex_evidence(details, reports),
        )
    return _entry(
        case,
        surface="codex",
        required_action="submit_project_task",
        selected_transport="none",
        transport_channel="none",
        capability_level=BLOCKED,
        operation_scope="submit-readback",
        requires_background_write=True,
        blocking_reason="ide_bridge_unavailable",
        risk_flags=("agent_task_surface", "native_endpoint_missing"),
        fallback_transports=("codex-cli-managed-terminal", "foreground-request"),
        evidence=_codex_evidence(details, reports),
    )


def _generic_entry(case: dict) -> PrimaryScenarioTransportEntry:
    if bool(case.get("real_verified", False)):
        return _entry(
            case,
            surface="generic",
            required_action="observe",
            selected_transport="real-no-loss-read-only",
            transport_channel="read_only_probe",
            capability_level=BACKGROUND_READ_ONLY,
            operation_scope="observe-only",
            ready=True,
            can_execute_without_focus=True,
        )
    return _entry(
        case,
        surface="generic",
        required_action="unknown",
        selected_transport="none",
        transport_channel="none",
        capability_level=BLOCKED,
        operation_scope="unknown",
        blocking_reason="unsupported_primary_scenario",
    )


def _entry(
    case: dict,
    *,
    surface: str,
    required_action: str,
    selected_transport: str,
    transport_channel: str,
    capability_level: str,
    operation_scope: str,
    ready: bool = False,
    requires_background_write: bool = False,
    can_execute_without_focus: bool = False,
    can_write_without_focus: bool = False,
    requires_user_confirmation: bool = False,
    blocking_reason: str = "",
    risk_flags: Iterable[str] = (),
    verification_requirements: Iterable[str] = (),
    fallback_transports: Iterable[str] = (),
    evidence: dict | None = None,
) -> PrimaryScenarioTransportEntry:
    return PrimaryScenarioTransportEntry(
        scenario_id=str(case.get("scenario_id", "") or ""),
        case_id=str(case.get("case_id", "") or ""),
        surface=surface,
        required_action=required_action,
        selected_transport=selected_transport,
        transport_channel=transport_channel,
        capability_level=capability_level,
        operation_scope=operation_scope,
        ready=ready,
        requires_background_write=requires_background_write,
        can_execute_without_focus=can_execute_without_focus,
        can_write_without_focus=can_write_without_focus,
        requires_user_confirmation=requires_user_confirmation,
        blocking_reason=blocking_reason,
        risk_flags=_unique(risk_flags),
        verification_requirements=_unique(verification_requirements),
        fallback_transports=_unique(fallback_transports),
        evidence=dict(evidence or {}),
    )


def _verified_wechat_send_transport(details: dict) -> str:
    native_report = _dict_value(details.get("wechat_native_bridge_send_report"))
    if bool(native_report.get("ok", False)):
        return "wechat-native-bridge"
    semantic_report = _dict_value(details.get("uia_semantic_action_send_report"))
    if bool(semantic_report.get("ok", False)):
        return "wechat-uia-semantic"
    return "wechat-background-send-verified"


def _wechat_evidence(details: dict) -> dict:
    computer_use = _dict_value(details.get("computer_use_probe"))
    return {
        "matching_window_count": int(details.get("matching_window_count", 0) or 0),
        "background_screenshot_focus_stable": bool(
            details.get("background_screenshot_focus_stable", True)
        ),
        "background_screenshot_success_count": int(
            details.get("background_screenshot_success_count", 0) or 0
        ),
        "background_send_verified": bool(details.get("background_send_verified", False)),
        "wechat_native_bridge_ready": bool(details.get("wechat_native_bridge_ready", False)),
        "wechat_native_bridge_dry_run_decision": str(
            details.get("wechat_native_bridge_dry_run_decision", "") or ""
        ),
        "uia_semantic_action_ready": bool(details.get("uia_semantic_action_ready", False)),
        "computer_use_read_only_ready": bool(
            details.get("computer_use_read_only_ready", False)
        ),
        "computer_use_decision": str(computer_use.get("decision", "") or ""),
        "computer_use_attempts": _counter(computer_use, "computer_use_attempts"),
        "computer_use_window_input_attempts": _counter(computer_use, "window_input_attempts"),
    }


def _codex_evidence(details: dict, reports: list[dict]) -> dict:
    commands: list[str] = []
    for report in reports:
        commands.extend(str(item) for item in _list_value(report.get("commands")))
    return {
        "ok_bridge_url": str(details.get("ok_bridge_url", "") or ""),
        "report_count": len(reports),
        "ok_report_count": sum(1 for report in reports if bool(report.get("ok", False))),
        "commands": sorted(set(commands)),
    }


def _case_dict(value: dict | object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _details(case: dict) -> dict:
    return _dict_value(case.get("details"))


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in items if str(item or "").strip()))
