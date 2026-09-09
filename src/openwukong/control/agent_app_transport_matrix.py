# -*- coding: utf-8 -*-
"""Plan-only transport matrix for agent desktop app chat surfaces."""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Iterable


BACKGROUND_NATIVE = "background-native"
BACKGROUND_READ_ONLY = "background-read-only"
FOREGROUND_REQUIRED = "foreground-required"
BLOCKED = "blocked"


@dataclasses.dataclass(frozen=True)
class AgentAppTransportCandidate:
    transport_id: str
    transport_channel: str
    capability_level: str
    operation_scope: str
    ready: bool = False
    can_send_without_focus: bool = False
    can_draft_without_focus: bool = False
    requires_user_confirmation: bool = False
    blocking_reason: str = ""
    risk_flags: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    evidence: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "transport_id": self.transport_id,
            "transport_channel": self.transport_channel,
            "capability_level": self.capability_level,
            "operation_scope": self.operation_scope,
            "ready": self.ready,
            "can_send_without_focus": self.can_send_without_focus,
            "can_draft_without_focus": self.can_draft_without_focus,
            "requires_user_confirmation": self.requires_user_confirmation,
            "blocking_reason": self.blocking_reason,
            "risk_flags": list(self.risk_flags),
            "verification_requirements": list(self.verification_requirements),
            "evidence": dict(self.evidence),
        }


@dataclasses.dataclass(frozen=True)
class AgentAppTransportMatrixReport:
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    candidates: tuple[AgentAppTransportCandidate, ...]

    @property
    def mode(self) -> str:
        return "agent-app-transport-matrix"

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
    def selected_send_transport(self) -> AgentAppTransportCandidate | None:
        return _best_candidate(
            candidate
            for candidate in self.candidates
            if candidate.ready and candidate.can_send_without_focus
        )

    @property
    def selected_draft_transport(self) -> AgentAppTransportCandidate | None:
        return _best_candidate(
            candidate
            for candidate in self.candidates
            if candidate.ready and candidate.can_draft_without_focus
        )

    @property
    def best_available_transport(self) -> AgentAppTransportCandidate | None:
        return _best_candidate(candidate for candidate in self.candidates if candidate.ready)

    @property
    def send_ready(self) -> bool:
        return self.selected_send_transport is not None

    @property
    def draft_ready(self) -> bool:
        return self.selected_draft_transport is not None

    def summary(self) -> dict:
        levels = Counter(candidate.capability_level for candidate in self.candidates)
        return {
            "background_send_ready": sum(
                1
                for candidate in self.candidates
                if candidate.ready and candidate.can_send_without_focus
            ),
            "background_draft_ready": sum(
                1
                for candidate in self.candidates
                if candidate.ready and candidate.can_draft_without_focus
            ),
            "background_read_only": sum(
                1
                for candidate in self.candidates
                if candidate.ready and candidate.capability_level == BACKGROUND_READ_ONLY
            ),
            "computer_use_read_only": sum(
                1
                for candidate in self.candidates
                if candidate.transport_id == "computer-use-window2"
                and candidate.ready
                and candidate.capability_level == BACKGROUND_READ_ONLY
            ),
            "foreground_required": levels.get(FOREGROUND_REQUIRED, 0),
            "blocked": levels.get(BLOCKED, 0),
        }

    def to_dict(self) -> dict:
        selected_send = self.selected_send_transport
        selected_draft = self.selected_draft_transport
        best_available = self.best_available_transport
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "send_ready": self.send_ready,
            "draft_ready": self.draft_ready,
            "selected_send_transport": (
                selected_send.to_dict() if selected_send is not None else {}
            ),
            "selected_draft_transport": (
                selected_draft.to_dict() if selected_draft is not None else {}
            ),
            "best_available_transport": (
                best_available.to_dict() if best_available is not None else {}
            ),
            "summary": self.summary(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def build_agent_app_transport_matrix(
    probe: dict | object,
    *,
    app_bridge_composer_probe: dict | object | None = None,
    app_bridge_send_report: dict | object | None = None,
    codex_app_server_turn_start_report: dict | object | None = None,
    computer_use_probe: dict | object | None = None,
) -> AgentAppTransportMatrixReport:
    data = _dict_from_report(probe)
    composer_probe = _dict_from_report(app_bridge_composer_probe)
    send_report = _dict_from_report(app_bridge_send_report)
    codex_turn_report = _dict_from_report(codex_app_server_turn_start_report)
    computer_probe = _dict_from_report(computer_use_probe) or _dict_value(
        data.get("computer_use_probe")
    )
    app_uia_probe = _dict_value(data.get("app_uia_probe"))
    agent = str(data.get("agent", "") or app_uia_probe.get("agent", "") or "").strip()
    agent_id = str(
        data.get("agent_id", "") or app_uia_probe.get("agent_id", "") or _agent_id(agent)
    ).strip()
    project_name = str(data.get("project_name", "") or app_uia_probe.get("project_name", "") or "").strip()
    task_name = str(data.get("task_name", "") or app_uia_probe.get("task_name", "") or "").strip()
    endpoints = tuple(_dict_value(item) for item in _list_value(data.get("endpoints")))
    candidates = (
        list(
            _endpoint_candidates(
                endpoints,
                app_uia_probe=app_uia_probe,
                project_name=project_name,
                task_name=task_name,
                app_bridge_composer_probe=composer_probe,
                app_bridge_send_report=send_report,
                codex_app_server_turn_start_report=codex_turn_report,
            )
        )
        + _uia_candidates(app_uia_probe)
        + _computer_use_candidates(computer_probe)
        + [_foreground_candidate(app_uia_probe)]
    )
    return AgentAppTransportMatrixReport(
        agent=agent,
        agent_id=agent_id,
        project_name=project_name,
        task_name=task_name,
        candidates=tuple(candidates),
    )


def _endpoint_candidates(
    endpoints: Iterable[dict],
    *,
    app_uia_probe: dict,
    project_name: str,
    task_name: str,
    app_bridge_composer_probe: dict,
    app_bridge_send_report: dict,
    codex_app_server_turn_start_report: dict,
) -> tuple[AgentAppTransportCandidate, ...]:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    candidates: list[AgentAppTransportCandidate] = []
    agent_native = [item for item in endpoint_list if _endpoint_type(item) == "agent_native_bridge"]
    ide_bridge = [item for item in endpoint_list if _endpoint_type(item) == "ide_bridge"]
    codex_app_server = [item for item in endpoint_list if _endpoint_type(item) == "codex_app_server_ws"]
    devtools = [item for item in endpoint_list if _endpoint_type(item) == "devtools"]

    if agent_native:
        candidates.append(
            _bridge_candidate(
                transport_id="agent-native-bridge",
                transport_channel="agent_native_bridge",
                endpoints=agent_native,
                verification_requirements=(
                    "bridge_capability_ok",
                    "app_binding_verified",
                    "readback_markers",
                    "no_window_input",
                ),
            )
        )
    if ide_bridge:
        candidates.append(
            _bridge_candidate(
                transport_id="ide-extension-bridge",
                transport_channel="ide_extension_bridge",
                endpoints=ide_bridge,
                verification_requirements=(
                    "bridge_capability_ok",
                    "chat_adapter_selected",
                    "readback_markers",
                    "no_window_input",
                ),
            )
        )
    if codex_app_server:
        candidates.append(
            _codex_app_server_candidate(
                codex_app_server,
                turn_start_report=codex_app_server_turn_start_report,
            )
        )
    if devtools:
        candidates.append(
            _devtools_page_candidate(
                devtools,
                target_context_verified=_target_context_verified(
                    app_uia_probe,
                    devtools,
                    project_name=project_name,
                    task_name=task_name,
                ),
                app_bridge_composer_probe=app_bridge_composer_probe,
                app_bridge_send_report=app_bridge_send_report,
            )
        )
        browser_candidate = _devtools_browser_candidate(devtools)
        if browser_candidate is not None:
            candidates.append(browser_candidate)
    return tuple(candidates)


def _codex_app_server_candidate(
    endpoints: Iterable[dict],
    *,
    turn_start_report: dict | None = None,
) -> AgentAppTransportCandidate:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    ready = any(bool(endpoint.get("ready", False)) for endpoint in endpoint_list)
    error = _first_error(endpoint_list)
    evidence = _endpoint_evidence(endpoint_list)
    metadata = _dict_value(endpoint_list[0].get("metadata") if endpoint_list else {})
    turn_report = _dict_value(turn_start_report)
    turn_verified = _codex_app_server_turn_start_verified(turn_report)
    if metadata:
        evidence.update(
            {
                "codex_home": str(metadata.get("codex_home", "") or ""),
                "user_agent": str(metadata.get("user_agent", "") or ""),
                "observed_thread_count": int(metadata.get("observed_thread_count", 0) or 0),
                "probe_decision": str(metadata.get("probe_decision", "") or ""),
                "thread_api_ready": bool(metadata.get("thread_api_ready", False)),
                "send_contract_ready": bool(metadata.get("send_contract_ready", False)),
                "owned_loopback_app_server": bool(
                    metadata.get("owned_loopback_app_server", False)
                ),
                "surface_kind": str(metadata.get("surface_kind", "") or ""),
            }
        )
    if turn_report:
        evidence.update(
            {
                "turn_start_decision": str(turn_report.get("decision", "") or ""),
                "turn_completed": bool(turn_report.get("turn_completed", False)),
                "turn_status": str(turn_report.get("turn_status", "") or ""),
                "foreground_no_steal_verified": bool(
                    turn_report.get("foreground_no_steal_verified", False)
                ),
                "strict_assistant_readback_verified": turn_verified,
                "assistant_readback_text_length": len(
                    str(turn_report.get("assistant_readback_text", "") or "")
                ),
            }
        )
    return AgentAppTransportCandidate(
        transport_id="codex-app-server-ws",
        transport_channel="codex_app_server_ws",
        capability_level=BACKGROUND_NATIVE if ready else BLOCKED,
        operation_scope="send-readback" if turn_verified else "thread-readiness",
        ready=ready,
        can_send_without_focus=bool(ready and turn_verified),
        can_draft_without_focus=False,
        requires_user_confirmation=True,
        blocking_reason=_codex_app_server_blocking_reason(
            ready=ready,
            turn_verified=turn_verified,
            turn_start_report=turn_report,
            endpoint_error=error,
        ),
        risk_flags=(
            ()
            if ready and turn_verified
            else _codex_app_server_risk_flags(
                ready=ready,
                turn_start_report=turn_report,
            )
        ),
        verification_requirements=(
            "app_server_initialize_ok",
            "thread_list_read_only_ok",
            (
                "strict_assistant_marker_readback"
                if turn_verified
                else "turn_send_contract_required"
            ),
            "readback_markers",
            "no_window_input",
        ),
        evidence=evidence,
    )


def _bridge_candidate(
    *,
    transport_id: str,
    transport_channel: str,
    endpoints: Iterable[dict],
    verification_requirements: tuple[str, ...],
) -> AgentAppTransportCandidate:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    ready = any(bool(endpoint.get("ready", False)) for endpoint in endpoint_list)
    error = _first_error(endpoint_list)
    return AgentAppTransportCandidate(
        transport_id=transport_id,
        transport_channel=transport_channel,
        capability_level=BACKGROUND_NATIVE if ready else BLOCKED,
        operation_scope="send-readback",
        ready=ready,
        can_send_without_focus=ready,
        requires_user_confirmation=True,
        blocking_reason="" if ready else error or "native_bridge_not_ready",
        verification_requirements=verification_requirements,
        evidence=_endpoint_evidence(endpoint_list),
    )


def _codex_app_server_turn_start_verified(report: dict) -> bool:
    if not report:
        return False
    assistant_text = str(report.get("assistant_readback_text", "") or "")
    required_markers = [
        str(marker)
        for marker in _list_value(report.get("required_markers"))
        if str(marker or "")
    ]
    missing_markers = _list_value(report.get("missing_required_markers"))
    forbidden_seen = _list_value(report.get("seen_forbidden_markers"))
    required_markers_seen = bool(
        required_markers and all(marker in assistant_text for marker in required_markers)
    )
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "")
        == "codex_app_server_turn_start_verified"
        and _counter(report, "control_attempts") == 0
        and _counter(report, "window_input_attempts") == 0
        and _counter(report, "app_server_turn_start_attempts") == 1
        and bool(report.get("turn_completed", False))
        and str(report.get("turn_status", "") or "") == "completed"
        and bool(report.get("foreground_no_steal_verified", False))
        and not missing_markers
        and not forbidden_seen
        and required_markers_seen
    )


def _codex_app_server_blocking_reason(
    *,
    ready: bool,
    turn_verified: bool,
    turn_start_report: dict,
    endpoint_error: str,
) -> str:
    if not ready:
        return endpoint_error or "codex_app_server_ws_not_ready"
    if turn_verified:
        return ""
    if turn_start_report:
        return str(
            turn_start_report.get("decision", "")
            or "codex_app_server_turn_start_not_verified"
        )
    return "turn_send_contract_required"


def _codex_app_server_risk_flags(
    *,
    ready: bool,
    turn_start_report: dict,
) -> tuple[str, ...]:
    flags: list[str] = []
    if not ready:
        flags.append("codex_app_server_ws_not_ready")
    if not turn_start_report:
        flags.append("turn_start_not_verified")
    elif _counter(turn_start_report, "window_input_attempts"):
        flags.append("window_input_attempts_nonzero")
    elif _counter(turn_start_report, "control_attempts"):
        flags.append("control_attempts_nonzero")
    elif not bool(turn_start_report.get("foreground_no_steal_verified", False)):
        flags.append("foreground_not_verified")
    elif _list_value(turn_start_report.get("missing_required_markers")):
        flags.append("required_marker_missing")
    elif _list_value(turn_start_report.get("seen_forbidden_markers")):
        flags.append("forbidden_marker_seen")
    else:
        flags.append("turn_start_not_verified")
    return tuple(dict.fromkeys(flags))


def _devtools_page_candidate(
    endpoints: Iterable[dict],
    *,
    target_context_verified: bool,
    app_bridge_composer_probe: dict,
    app_bridge_send_report: dict,
) -> AgentAppTransportCandidate:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    ready_endpoints = [
        endpoint
        for endpoint in endpoint_list
        if bool(endpoint.get("ready", False)) and _target_count(endpoint) > 0
    ]
    transport_ready = bool(ready_endpoints)
    target_ready = bool(transport_ready and target_context_verified)
    composer_ready = _app_bridge_composer_ready(app_bridge_composer_probe)
    send_verified = _app_bridge_send_verified(app_bridge_send_report)
    send_ready = bool(target_ready and (composer_ready or send_verified))
    evidence = _endpoint_evidence(endpoint_list)
    evidence.update(
        _app_bridge_evidence(
            app_bridge_composer_probe,
            app_bridge_send_report,
            composer_ready=composer_ready,
            send_verified=send_verified,
        )
    )
    return AgentAppTransportCandidate(
        transport_id="app-devtools-page-target",
        transport_channel="cdp_page_target",
        capability_level=BACKGROUND_NATIVE if transport_ready else BLOCKED,
        operation_scope="send-readback",
        ready=transport_ready,
        can_send_without_focus=send_ready,
        requires_user_confirmation=True,
        blocking_reason=_devtools_page_blocking_reason(
            endpoint_list,
            transport_ready=transport_ready,
            target_context_verified=target_context_verified,
            composer_probe=app_bridge_composer_probe,
            send_ready=send_ready,
        ),
        verification_requirements=(
            "page_target_websocket",
            "target_context_verification",
            "composer_probe_ready",
            "dom_bridge_result",
            "readback_markers",
            "no_window_input",
        ),
        risk_flags=_devtools_page_risk_flags(
            transport_ready=transport_ready,
            target_context_verified=target_context_verified,
            composer_probe=app_bridge_composer_probe,
            send_ready=send_ready,
        ),
        evidence=evidence,
    )


def _devtools_browser_candidate(
    endpoints: Iterable[dict],
) -> AgentAppTransportCandidate | None:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    browser_endpoints = [
        endpoint
        for endpoint in endpoint_list
        if _browser_websocket_url(endpoint)
    ]
    if not browser_endpoints:
        return None
    return AgentAppTransportCandidate(
        transport_id="app-devtools-browser-target",
        transport_channel="cdp_browser_target",
        capability_level=BACKGROUND_READ_ONLY,
        operation_scope="discovery-only",
        ready=True,
        can_send_without_focus=False,
        blocking_reason="page_target_missing",
        verification_requirements=("Target.getTargets", "page_target_required"),
        risk_flags=("browser_target_not_control_surface",),
        evidence=_endpoint_evidence(browser_endpoints),
    )


def _devtools_page_blocking_reason(
    endpoints: Iterable[dict],
    *,
    transport_ready: bool,
    target_context_verified: bool,
    composer_probe: dict,
    send_ready: bool,
) -> str:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    if send_ready:
        return ""
    if not transport_ready:
        return _first_error(endpoint_list) or "page_target_missing"
    if not target_context_verified:
        return "target_context_not_verified"
    if not composer_probe:
        return "composer_probe_required"
    return str(composer_probe.get("decision", "") or "composer_probe_not_ready")


def _devtools_page_risk_flags(
    *,
    transport_ready: bool,
    target_context_verified: bool,
    composer_probe: dict,
    send_ready: bool,
) -> tuple[str, ...]:
    if send_ready:
        return ()
    if not transport_ready:
        return ("page_target_missing",)
    if not target_context_verified:
        return ("target_context_not_verified",)
    if not composer_probe:
        return ("composer_probe_required",)
    return ("composer_not_verified",)


def _app_bridge_composer_ready(report: dict) -> bool:
    if not report:
        return False
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "") == "app_bridge_composer_ready"
        and _counter(report, "control_attempts") == 0
        and _counter(report, "window_input_attempts") == 0
        and _counter(report, "bridge_send_attempts") == 0
    )


def _app_bridge_send_verified(report: dict) -> bool:
    if not report:
        return False
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "") == "app_bridge_send_accepted"
        and _counter(report, "control_attempts") == 0
        and _counter(report, "window_input_attempts") == 0
        and _counter(report, "bridge_send_attempts") == 1
        and _counter(report, "native_call_attempts") == 1
    )


def _app_bridge_evidence(
    composer_probe: dict,
    send_report: dict,
    *,
    composer_ready: bool,
    send_verified: bool,
) -> dict:
    evidence = {
        "composer_probe_decision": str(composer_probe.get("decision", "") or ""),
        "composer_probe_ready": composer_ready,
        "app_bridge_send_decision": str(send_report.get("decision", "") or ""),
        "app_bridge_send_verified": send_verified,
    }
    product_contract = _first_nested_text(
        composer_probe,
        (
            ("action_result", "selectedComposer", "productComposerContract"),
            ("action_result", "productComposerContract"),
        ),
    ) or _first_nested_text(
        send_report,
        (
            ("action_result", "productComposerContract"),
            ("action_result", "selectedComposer", "productComposerContract"),
        ),
    )
    send_button_contract = _first_nested_text(
        send_report,
        (("action_result", "sendButtonContract"),),
    )
    if product_contract:
        evidence["product_composer_contract"] = product_contract
    if send_button_contract:
        evidence["send_button_contract"] = send_button_contract
    return evidence


def _first_nested_text(data: dict, paths: Iterable[tuple[str, ...]]) -> str:
    for path in paths:
        value: object = data
        for key in path:
            if not isinstance(value, dict):
                value = ""
                break
            value = value.get(key, "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _uia_candidates(app_uia_probe: dict) -> list[AgentAppTransportCandidate]:
    target_ready = bool(app_uia_probe.get("target_matched", False))
    semantic_count = int(app_uia_probe.get("semantic_composer_count", 0) or 0)
    submit_count = int(app_uia_probe.get("submit_candidate_count", 0) or 0)
    focus_stable = bool(app_uia_probe.get("background_screenshot_focus_stable", True))
    draft_ready = bool(target_ready and semantic_count > 0 and focus_stable)
    send_ready = bool(draft_ready and submit_count > 0)
    evidence = {
        "target_matched": target_ready,
        "semantic_composer_count": semantic_count,
        "submit_candidate_count": submit_count,
        "background_screenshot_focus_stable": focus_stable,
    }
    return [
        AgentAppTransportCandidate(
            transport_id="uia-semantic-send",
            transport_channel="uia_control_patterns",
            capability_level=BACKGROUND_NATIVE if send_ready else BLOCKED,
            operation_scope="send-readback",
            ready=send_ready,
            can_send_without_focus=send_ready,
            requires_user_confirmation=True,
            blocking_reason="" if send_ready else _uia_blocking_reason(evidence, require_submit=True),
            risk_flags=("uia_provider_must_verify",),
            verification_requirements=(
                "ValuePattern.SetValue",
                "InvokePattern.Invoke",
                "readback_markers",
                "foreground_stability",
            ),
            evidence=evidence,
        ),
        AgentAppTransportCandidate(
            transport_id="uia-semantic-draft",
            transport_channel="uia_control_patterns",
            capability_level=BACKGROUND_NATIVE if draft_ready else BLOCKED,
            operation_scope="draft-only",
            ready=draft_ready,
            can_draft_without_focus=draft_ready,
            blocking_reason="" if draft_ready else _uia_blocking_reason(evidence, require_submit=False),
            risk_flags=("uia_provider_must_verify",),
            verification_requirements=(
                "ValuePattern.SetValue",
                "value_readback",
                "cleanup_readback",
                "foreground_stability",
            ),
            evidence=evidence,
        ),
    ]


def _computer_use_candidates(probe: dict) -> list[AgentAppTransportCandidate]:
    if not probe:
        return []
    native_pipe_ready = bool(probe.get("native_pipe_ready", False))
    ready = bool(
        probe.get("ready", False)
        and native_pipe_ready
        and (
            bool(probe.get("window_state_ready", False))
            or bool(probe.get("background_snapshot_ready", False))
            or bool(probe.get("accessibility_tree_available", False))
        )
        and _counter(probe, "control_attempts") == 0
        and _counter(probe, "window_input_attempts") == 0
    )
    return [
        AgentAppTransportCandidate(
            transport_id="computer-use-window2",
            transport_channel="computer_use_window2",
            capability_level=BACKGROUND_READ_ONLY if ready else BLOCKED,
            operation_scope="inspect-snapshot-only",
            ready=ready,
            can_send_without_focus=False,
            can_draft_without_focus=False,
            requires_user_confirmation=True,
            blocking_reason=_computer_use_blocking_reason(probe, ready=ready),
            risk_flags=_computer_use_risk_flags(probe, ready=ready),
            verification_requirements=(
                "sky.list_apps_or_list_windows",
                "get_window_state",
                "background_screenshot_or_accessibility",
                "no_window_input_for_read_only",
                "foreground_activation_gate_for_input_actions",
            ),
            evidence=_computer_use_evidence(probe),
        )
    ]


def _computer_use_blocking_reason(probe: dict, *, ready: bool) -> str:
    if ready:
        return "computer_use_input_requires_foreground_activation"
    if not bool(probe.get("native_pipe_ready", False)):
        return str(probe.get("decision", "") or "native_pipe_unavailable")
    if _counter(probe, "control_attempts"):
        return "control_attempts_nonzero"
    if _counter(probe, "window_input_attempts"):
        return "window_input_attempts_nonzero"
    if not (
        bool(probe.get("window_state_ready", False))
        or bool(probe.get("background_snapshot_ready", False))
        or bool(probe.get("accessibility_tree_available", False))
    ):
        return str(probe.get("decision", "") or "window_state_not_ready")
    return str(probe.get("decision", "") or "computer_use_not_ready")


def _computer_use_risk_flags(probe: dict, *, ready: bool) -> tuple[str, ...]:
    flags: list[str] = ["computer_use_fallback"]
    if bool(probe.get("input_actions_activate_window", True)):
        flags.append("input_actions_activate_window")
        flags.append("not_background_write_transport")
    if not bool(probe.get("native_pipe_ready", False)):
        flags.append("native_pipe_unavailable")
    if _counter(probe, "control_attempts"):
        flags.append("control_attempts_nonzero")
    if _counter(probe, "window_input_attempts"):
        flags.append("window_input_attempts_nonzero")
    if ready:
        flags.append("read_only_only")
    return tuple(dict.fromkeys(flags))


def _computer_use_evidence(probe: dict) -> dict:
    keys = (
        "ready",
        "native_pipe_ready",
        "window_state_ready",
        "background_snapshot_ready",
        "input_actions_activate_window",
        "accessibility_tree_available",
        "observed_window_count",
        "screenshot_count",
        "computer_use_attempts",
        "control_attempts",
        "window_input_attempts",
        "decision",
        "error",
    )
    evidence: dict = {}
    for key in keys:
        if key in probe:
            evidence[key] = probe.get(key)
    return evidence


def _foreground_candidate(app_uia_probe: dict) -> AgentAppTransportCandidate:
    return AgentAppTransportCandidate(
        transport_id="foreground-request",
        transport_channel="foreground_input",
        capability_level=FOREGROUND_REQUIRED,
        operation_scope="send-readback",
        ready=False,
        requires_user_confirmation=True,
        blocking_reason="foreground_takeover_required",
        risk_flags=("foreground_focus_steal", "keyboard_or_clipboard_input"),
        verification_requirements=(
            "explicit_user_approval",
            "pre_action_target_verification",
            "post_action_bound_window_verification",
        ),
        evidence={
            "target_matched": bool(app_uia_probe.get("target_matched", False)),
            "matched_window_count": int(app_uia_probe.get("matched_window_count", 0) or 0),
        },
    )


def _target_context_verified(
    app_uia_probe: dict,
    endpoints: Iterable[dict],
    *,
    project_name: str,
    task_name: str,
) -> bool:
    if bool(app_uia_probe.get("target_matched", False)):
        return True
    queries = [
        str(project_name or "").strip().lower(),
        str(task_name or "").strip().lower(),
    ]
    queries = [query for query in queries if query]
    if not queries:
        return True
    for endpoint in endpoints:
        for target in _list_value(_dict_value(endpoint).get("targets")):
            data = _dict_value(target)
            text = (
                f"{data.get('title', '')} {data.get('url', '')} "
                f"{data.get('target_id', '')} {data.get('id', '')}"
            ).lower()
            if all(query in text for query in queries):
                return True
    return False


def _uia_blocking_reason(evidence: dict, *, require_submit: bool) -> str:
    if not bool(evidence.get("target_matched", False)):
        return "target_not_ready"
    if int(evidence.get("semantic_composer_count", 0) or 0) <= 0:
        return "semantic_composer_missing"
    if not bool(evidence.get("background_screenshot_focus_stable", True)):
        return "background_focus_unstable"
    if require_submit and int(evidence.get("submit_candidate_count", 0) or 0) <= 0:
        return "submit_control_missing"
    return "uia_semantic_not_ready"


def _endpoint_evidence(endpoints: Iterable[dict]) -> dict:
    endpoint_list = tuple(_dict_value(endpoint) for endpoint in endpoints)
    return {
        "endpoint_count": len(endpoint_list),
        "ready_endpoint_count": sum(1 for endpoint in endpoint_list if bool(endpoint.get("ready", False))),
        "target_count": sum(_target_count(endpoint) for endpoint in endpoint_list),
        "debugger_urls": [
            str(endpoint.get("debugger_url", "") or "")
            for endpoint in endpoint_list
            if str(endpoint.get("debugger_url", "") or "")
        ],
        "bridge_urls": [
            str(endpoint.get("bridge_url", "") or "")
            for endpoint in endpoint_list
            if str(endpoint.get("bridge_url", "") or "")
        ],
        "browser_websocket_urls": [
            _browser_websocket_url(endpoint)
            for endpoint in endpoint_list
            if _browser_websocket_url(endpoint)
        ],
    }


def _best_candidate(
    candidates: Iterable[AgentAppTransportCandidate],
) -> AgentAppTransportCandidate | None:
    items = tuple(candidates)
    if not items:
        return None
    return sorted(items, key=lambda item: _candidate_rank(item.transport_id))[0]


def _candidate_rank(transport_id: str) -> int:
    order = {
        "agent-native-bridge": 0,
        "ide-extension-bridge": 1,
        "app-devtools-page-target": 2,
        "codex-app-server-ws": 3,
        "uia-semantic-send": 4,
        "uia-semantic-draft": 5,
        "app-devtools-browser-target": 6,
        "computer-use-window2": 7,
        "foreground-request": 99,
    }
    return order.get(str(transport_id or ""), 50)


def _endpoint_type(endpoint: dict) -> str:
    return str(endpoint.get("endpoint_type", "") or "devtools").strip()


def _target_count(endpoint: dict) -> int:
    targets = endpoint.get("targets")
    if isinstance(targets, list):
        return len(targets)
    return int(endpoint.get("target_count", 0) or 0)


def _browser_websocket_url(endpoint: dict) -> str:
    version = _dict_value(endpoint.get("version"))
    return str(version.get("webSocketDebuggerUrl", "") or "")


def _first_error(endpoints: Iterable[dict]) -> str:
    for endpoint in endpoints:
        error = str(_dict_value(endpoint).get("error", "") or "").strip()
        if error:
            return error
    return ""


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _agent_id(agent: str) -> str:
    text = str(agent or "").strip().lower()
    if "claude" in text:
        return "claude"
    if "cursor" in text:
        return "cursor"
    if "codex" in text:
        return "codex"
    return text.replace(" ", "-")


def summarize_agent_app_transport_matrices(cases: Iterable[dict]) -> dict:
    matrices = [
        _dict_value(case.get("transport_matrix"))
        for case in cases or ()
        if isinstance(case, dict) and isinstance(case.get("transport_matrix"), dict)
    ]
    return {
        "case_count": len(matrices),
        "background_send_ready_cases": sum(1 for item in matrices if bool(item.get("send_ready", False))),
        "background_draft_ready_cases": sum(1 for item in matrices if bool(item.get("draft_ready", False))),
        "background_read_only_cases": sum(
            1
            for item in matrices
            if int(_dict_value(item.get("summary")).get("background_read_only", 0) or 0) > 0
        ),
        "computer_use_read_only_cases": sum(
            1
            for item in matrices
            if int(_dict_value(item.get("summary")).get("computer_use_read_only", 0) or 0) > 0
        ),
        "selected_send_transport_counts": dict(
            sorted(
                Counter(
                    str(_dict_value(item.get("selected_send_transport")).get("transport_id", "") or "none")
                    for item in matrices
                ).items()
            )
        ),
    }
