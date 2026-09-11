# -*- coding: utf-8 -*-
"""Unified control fabric for route-first desktop automation.

The fabric is the single policy entrypoint above app-specific connectors and
UIA primitives. It turns a target window plus an intent into an auditable
dispatch plan before any control primitive is allowed to run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterable, Mapping, Optional

from openwukong.connectors.base import ConnectorTarget, SessionConnector
from openwukong.connectors.registry import ConnectorManager
from openwukong.connectors.route_policy import (
    ControlRoutePlan,
    build_control_route_plan,
)
from openwukong.control.command_planner import (
    CommandPlanIntent,
    CommandPlanReport,
    CommandPlanner,
)
from openwukong.control.command_runner import CommandRunner
from openwukong.control.execution_contract import (
    build_no_foreground_contract,
    validate_no_foreground_contract,
)
from openwukong.control.foreground_takeover import (
    ForegroundTakeoverRequest,
    build_foreground_takeover_request,
    validate_foreground_takeover_request,
)
from openwukong.control.side_effects import (
    SideEffectGateReport,
    evaluate_side_effect_policy,
)
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex
from openwukong.control.transport_capability import (
    TransportCapabilityReport,
    build_transport_capability,
)
from openwukong.control.trajectory import (
    ControlTrajectoryRecorder,
    extract_trajectory_artifacts,
)


_CONNECTOR_ROUTE_IDS = {
    "app-native-bridge-required",
    "browser-devtools-or-extension",
    "desktop-app-launch",
    "git-cli",
    "filesystem-native",
    "ide-extension-connector",
    "office-object-model-or-addin",
    "terminal-native-session",
}
_ROUTE_CONNECTOR_IDS = {
    "app-native-bridge-required": ("agent-native-bridge", "wechat-native-bridge"),
    "browser-devtools-or-extension": ("browser",),
    "desktop-app-launch": ("desktop-uia",),
    "git-cli": ("git",),
    "filesystem-native": ("filesystem",),
    "ide-extension-connector": ("ide-extension",),
    "office-object-model-or-addin": ("office",),
    "terminal-native-session": ("terminal",),
}
_UIA_CONNECTOR_ROUTE_IDS = {
    "uia-semantic",
    "uia-structural",
    "uia-structural-observe",
    "uia-window-observe",
}
_UIA_GENERAL_ACTIONS = {
    "click",
    "click_coordinates",
    "click_semantic",
    "double_click",
    "drag",
    "focus",
    "get_controls",
    "inspect",
    "inspect_controls",
    "invoke",
    "key_press",
    "read",
    "read_text",
    "screenshot",
    "screenshot_window",
    "scroll",
    "select",
    "set_edit_text",
    "set_value",
    "toggle",
    "type_keys",
    "type_text",
    "wait",
    "wait_for_element",
    "write_text",
}
_FOREGROUND_UIA_ROUTES = {
    "app-native-bridge-required",
    "uia-structural",
    "uia-structural-observe",
}
_COMMAND_EXECUTION_ROUTES = {
    "git-cli",
    "terminal-native-session",
}


@dataclasses.dataclass(frozen=True)
class ControlIntent:
    """Normalized action request independent of any specific application."""

    action: str = "write_text"
    text: str = ""
    url: str = ""
    selector: str = ""
    value: str = ""
    submit: bool = False
    allow_submit: bool = False
    allow_foreground_interaction: bool = False
    allow_blocked_side_effects: bool = False
    confirmed_effect_ids: tuple[str, ...] = ()
    side_effect_policy: dict = dataclasses.field(default_factory=dict)
    preferred_connector_id: str = ""
    preferred_route_id: str = ""
    parameters: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "text_preview": _clip(self.text),
            "url": self.url,
            "selector": self.selector,
            "value_preview": _clip(self.value),
            "submit": self.submit,
            "allow_submit": self.allow_submit,
            "allow_foreground_interaction": self.allow_foreground_interaction,
            "allow_blocked_side_effects": self.allow_blocked_side_effects,
            "confirmed_effect_ids": list(self.confirmed_effect_ids),
            "side_effect_policy_present": bool(self.side_effect_policy),
            "preferred_connector_id": self.preferred_connector_id,
            "preferred_route_id": self.preferred_route_id,
            "parameters": _intent_parameters_to_dict(self.parameters),
        }


@dataclasses.dataclass(frozen=True)
class ControlDispatchReport:
    """Plan-only dispatch report produced by the control fabric."""

    target: ConnectorTarget
    intent: ControlIntent
    route_plan: ControlRoutePlan
    decision: str
    execution_mode: str
    selected_route: str
    selected_connector_id: str = ""
    installed_connector_ids: tuple[str, ...] = ()
    candidate_connector_ids: tuple[str, ...] = ()
    connector_ready: bool = False
    session_discovery: dict | None = None
    background_safe: bool = False
    foreground_required: bool = False
    transport_capability: TransportCapabilityReport | None = None
    side_effect_gate: SideEffectGateReport = dataclasses.field(
        default_factory=lambda: evaluate_side_effect_policy({})
    )
    blocked: bool = False
    reason: str = ""
    ownership: SessionOwnership = dataclasses.field(default_factory=SessionOwnership.unowned)
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "control-fabric-dispatch-plan"

    @property
    def safety_mode(self) -> str:
        return "plan_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        transport = self.transport_capability or build_transport_capability(
            self.route_plan,
            self.intent,
            selected_route=self.selected_route,
        )
        no_foreground_contract = build_no_foreground_contract(
            self.route_plan,
            self.intent,
            transport=transport,
            selected_route=self.selected_route,
        )
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "decision": self.decision,
            "execution_mode": self.execution_mode,
            "selected_route": self.selected_route,
            "selected_connector_id": self.selected_connector_id,
            "installed_connector_ids": list(self.installed_connector_ids),
            "candidate_connector_ids": list(self.candidate_connector_ids),
            "connector_ready": self.connector_ready,
            "session_discovery": self.session_discovery or {
                "discovered_fields": {},
                "evidence": [],
            },
            "background_safe": self.background_safe,
            "foreground_required": self.foreground_required,
            "transport_capability": transport.to_dict(),
            "no_foreground_contract": no_foreground_contract.to_dict(),
            "transport_capability_level": transport.capability_level,
            "selected_transport": transport.selected_transport,
            "can_execute_without_focus": transport.can_execute_without_focus,
            "transport_requires_user_confirmation": transport.requires_user_confirmation,
            "side_effect_gate": self.side_effect_gate.to_dict(),
            "blocked": self.blocked,
            "reason": self.reason,
            "ownership": self.ownership.to_dict(),
            "target": _target_to_dict(self.target),
            "intent": self.intent.to_dict(),
            "route_plan": self.route_plan.to_dict(),
            "fallback_routes": [
                route.route_id for route in self.route_plan.fallback_routes
            ],
            "missing_capabilities": list(self.route_plan.missing_capabilities),
            "risks": list(self.route_plan.risks),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class ControlExecutionReport:
    """Explicit execution report produced after a dispatch gate passes."""

    dispatch_report: ControlDispatchReport
    decision: str
    ok: bool
    allow_control: bool = False
    ownership_required: bool = False
    transport_gate_decision: str = "not_evaluated"
    transport_gate_error: str = ""
    foreground_takeover_request: ForegroundTakeoverRequest | None = None
    action_report: dict | None = None
    error: str = ""
    trajectory_id: str = ""
    trajectory_path: str = ""
    trajectory_error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "control-fabric-execution"

    @property
    def safety_mode(self) -> str:
        return "explicit_control_gate"

    @property
    def control_allowed(self) -> bool:
        return bool(self.allow_control and self.decision == "executed")

    @property
    def control_attempts(self) -> int:
        if not self.action_report:
            return 0
        return int(self.action_report.get("control_attempts", 0) or 0)

    @property
    def selected_route(self) -> str:
        return self.dispatch_report.selected_route

    @property
    def selected_connector_id(self) -> str:
        return self.dispatch_report.selected_connector_id

    @property
    def ownership(self) -> SessionOwnership:
        return self.dispatch_report.ownership

    def to_dict(self) -> dict:
        transport = self.dispatch_report.transport_capability or build_transport_capability(
            self.dispatch_report.route_plan,
            self.dispatch_report.intent,
            selected_route=self.dispatch_report.selected_route,
        )
        no_foreground_contract = build_no_foreground_contract(
            self.dispatch_report.route_plan,
            self.dispatch_report.intent,
            transport=transport,
            selected_route=self.dispatch_report.selected_route,
        )
        no_foreground_validation = validate_no_foreground_contract(
            no_foreground_contract,
            self.action_report,
        )
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "decision": self.decision,
            "ownership_required": self.ownership_required,
            "ownership": self.ownership.to_dict(),
            "transport_gate_decision": self.transport_gate_decision,
            "transport_gate_error": self.transport_gate_error,
            "foreground_takeover_request": (
                self.foreground_takeover_request.to_dict()
                if self.foreground_takeover_request
                else {}
            ),
            "selected_route": self.selected_route,
            "selected_connector_id": self.selected_connector_id,
            "no_foreground_contract": no_foreground_contract.to_dict(),
            "no_foreground_validation": no_foreground_validation.to_dict(),
            "dispatch_report": self.dispatch_report.to_dict(),
            "action_report": dict(self.action_report or {}),
            "error": self.error,
            "trajectory_id": self.trajectory_id,
            "trajectory_path": self.trajectory_path,
            "trajectory_error": self.trajectory_error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class ControlCommandExecutionReport:
    """Execution report for structured command plans run through the fabric gate."""

    command_plan: CommandPlanReport
    decision: str
    ok: bool
    allow_control: bool = False
    ownership_required: bool = False
    action_report: dict | None = None
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "control-fabric-command-execution"

    @property
    def safety_mode(self) -> str:
        return "explicit_control_gate"

    @property
    def control_allowed(self) -> bool:
        return bool(self.allow_control and self.decision == "executed")

    @property
    def control_attempts(self) -> int:
        if not self.action_report:
            return 0
        return int(self.action_report.get("control_attempts", 0) or 0)

    @property
    def ownership(self) -> SessionOwnership:
        return self.command_plan.execution_request.ownership

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "decision": self.decision,
            "ownership_required": self.ownership_required,
            "ownership": self.ownership.to_dict(),
            "command_plan": self.command_plan.to_dict(),
            "action_report": dict(self.action_report or {}),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class _ConnectorResolution:
    connector: Optional[SessionConnector]
    installed_connector_ids: tuple[str, ...]
    candidate_connector_ids: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class _ExecutableConnectorResolution:
    connector: Optional[SessionConnector]
    error: str = ""


@dataclasses.dataclass(frozen=True)
class _TransportExecutionGate:
    allowed: bool
    decision: str = "allow"
    error: str = ""
    takeover_request: ForegroundTakeoverRequest | None = None


class ControlFabric:
    """Build unified dispatch plans for desktop control intents."""

    def __init__(
        self,
        *,
        connector_manager: Optional[ConnectorManager] = None,
        require_connector_session_ready: bool = False,
        ownership_index: SessionOwnershipIndex | None = None,
        require_owned_session_for_execution: bool = False,
    ):
        self._connector_manager = connector_manager or ConnectorManager()
        self._require_connector_session_ready = bool(require_connector_session_ready)
        self._ownership_index = ownership_index or SessionOwnershipIndex()
        self._require_owned_session_for_execution = bool(require_owned_session_for_execution)

    @classmethod
    def with_default_connectors(
        cls,
        *,
        ownership_index: SessionOwnershipIndex | None = None,
        require_owned_session_for_execution: bool = False,
    ) -> "ControlFabric":
        return cls(
            connector_manager=default_connector_manager(),
            require_connector_session_ready=True,
            ownership_index=ownership_index,
            require_owned_session_for_execution=require_owned_session_for_execution,
        )

    def dispatch(self, target_or_window: object, intent: ControlIntent) -> ControlDispatchReport:
        started = time.perf_counter()
        target = _connector_target_from(target_or_window)
        route_source = self._uia_route_source(target_or_window, target, intent)
        route_plan = build_control_route_plan(route_source)
        selected_route = _preferred_route(intent, route_plan)
        session_discovery = _session_discovery_dict(target_or_window)
        ownership = self._ownership_for_target(target_or_window, target)
        side_effect_gate = evaluate_side_effect_policy(
            intent.side_effect_policy,
            confirmed_effect_ids=intent.confirmed_effect_ids,
            allow_blocked_effects=intent.allow_blocked_side_effects,
        )

        report = self._plan_for_route(
            target,
            intent,
            route_plan,
            selected_route,
            started,
            session_discovery,
            ownership,
            side_effect_gate,
        )
        return report

    def _uia_route_source(
        self,
        target_or_window: object,
        target: ConnectorTarget,
        intent: ControlIntent,
    ) -> object:
        """Hydrate a raw target with a read-only UIA snapshot before routing."""
        if int(target.pid or 0) <= 0 or hasattr(target_or_window, "elements"):
            return target_or_window
        action = str(intent.action or "").strip().lower()
        preferred_route = str(intent.preferred_route_id or "").strip()
        initial_plan = build_control_route_plan(target_or_window)
        should_probe = (
            preferred_route in _UIA_CONNECTOR_ROUTE_IDS
            or (
                initial_plan.app_family == "generic-desktop"
                and action in _UIA_GENERAL_ACTIONS
            )
        )
        if not should_probe:
            return target_or_window

        connectors = tuple(getattr(self._connector_manager, "_connectors", ()) or ())
        for connector in connectors:
            if connector.connector_id != "desktop-uia":
                continue
            probe = getattr(connector, "probe_target", None)
            if not callable(probe):
                continue
            try:
                snapshot = probe(target)
            except Exception:
                return target_or_window
            return snapshot or target_or_window
        return target_or_window

    def execute(
        self,
        target_or_window: object,
        intent: ControlIntent,
        *,
        allow_control: bool = False,
        browser_action_runner: Optional[object] = None,
        foreground_takeover_approval: ForegroundTakeoverRequest | Mapping[str, object] | None = None,
        trajectory_root: str | Path = "",
        trajectory_metadata: Optional[dict] = None,
    ) -> ControlExecutionReport:
        started = time.perf_counter()
        dispatch_report = self.dispatch(target_or_window, intent)
        if not allow_control:
            return _finalize_execution_report(
                ControlExecutionReport(
                    dispatch_report=dispatch_report,
                    decision="blocked",
                    ok=False,
                    allow_control=False,
                    ownership_required=self._require_owned_session_for_execution,
                    error="explicit_control_permission_required",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                ),
                trajectory_root=trajectory_root,
                trajectory_metadata=trajectory_metadata,
            )
        transport_gate = _evaluate_transport_execution_gate(
            dispatch_report,
            foreground_takeover_approval=foreground_takeover_approval,
        )
        if dispatch_report.blocked:
            return _finalize_execution_report(
                ControlExecutionReport(
                    dispatch_report=dispatch_report,
                    decision="blocked",
                    ok=False,
                    allow_control=True,
                    ownership_required=self._require_owned_session_for_execution,
                    transport_gate_decision=transport_gate.decision,
                    transport_gate_error=transport_gate.error,
                    error=dispatch_report.reason or dispatch_report.decision,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                ),
                trajectory_root=trajectory_root,
                trajectory_metadata=trajectory_metadata,
            )
        if not transport_gate.allowed:
            takeover_request = transport_gate.takeover_request
            if (
                takeover_request is None
                and transport_gate.decision.startswith("blocked_foreground_takeover")
            ):
                takeover_request = _build_bound_foreground_takeover_request(dispatch_report)
            return _finalize_execution_report(
                ControlExecutionReport(
                    dispatch_report=dispatch_report,
                    decision="blocked",
                    ok=False,
                    allow_control=True,
                    ownership_required=self._require_owned_session_for_execution,
                    transport_gate_decision=transport_gate.decision,
                    transport_gate_error=transport_gate.error,
                    foreground_takeover_request=takeover_request,
                    error=transport_gate.error,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                ),
                trajectory_root=trajectory_root,
                trajectory_metadata=trajectory_metadata,
            )
        if not _dispatch_allows_connector_action(dispatch_report):
            if not dispatch_report.side_effect_gate.allowed:
                return _finalize_execution_report(
                    ControlExecutionReport(
                        dispatch_report=dispatch_report,
                        decision="blocked",
                        ok=False,
                        allow_control=True,
                        ownership_required=self._require_owned_session_for_execution,
                        transport_gate_decision=transport_gate.decision,
                        transport_gate_error=transport_gate.error,
                        error=dispatch_report.side_effect_gate.reason,
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                    ),
                    trajectory_root=trajectory_root,
                    trajectory_metadata=trajectory_metadata,
                )
            return _finalize_execution_report(
                ControlExecutionReport(
                    dispatch_report=dispatch_report,
                    decision="blocked",
                    ok=False,
                    allow_control=True,
                    ownership_required=self._require_owned_session_for_execution,
                    transport_gate_decision=transport_gate.decision,
                    transport_gate_error=transport_gate.error,
                    error="dispatch_gate_not_ready",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                ),
                trajectory_root=trajectory_root,
                trajectory_metadata=trajectory_metadata,
            )
        if self._require_owned_session_for_execution and not dispatch_report.ownership.owned:
            return _finalize_execution_report(
                ControlExecutionReport(
                    dispatch_report=dispatch_report,
                    decision="blocked",
                    ok=False,
                    allow_control=True,
                    ownership_required=True,
                    transport_gate_decision=transport_gate.decision,
                    transport_gate_error=transport_gate.error,
                    error="owned_session_required",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                ),
                trajectory_root=trajectory_root,
                trajectory_metadata=trajectory_metadata,
            )

        if _dispatch_allows_browser_devtools_action(dispatch_report):
            runner = browser_action_runner or _default_browser_action_runner()
            action_report_obj = runner(
                debugger_url=dispatch_report.target.debugger_url,
                window_title=dispatch_report.target.window_title,
                resource_url=dispatch_report.target.resource_url,
                action=intent.action,
                url=intent.url,
                selector=intent.selector,
                value=intent.value or intent.text,
            )
        else:
            resolution = self._resolve_executable_connector(dispatch_report)
            if resolution.connector is None:
                return _finalize_execution_report(
                    ControlExecutionReport(
                        dispatch_report=dispatch_report,
                        decision="blocked",
                        ok=False,
                        allow_control=True,
                        ownership_required=self._require_owned_session_for_execution,
                        transport_gate_decision=transport_gate.decision,
                        transport_gate_error=transport_gate.error,
                        error=resolution.error or "connector_execution_not_available",
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                    ),
                    trajectory_root=trajectory_root,
                    trajectory_metadata=trajectory_metadata,
                )
            connector_result = resolution.connector.execute_action(
                dispatch_report.target,
                intent,
            )
            action_report_obj = _connector_action_result_to_dict(connector_result)
        action_report = (
            action_report_obj.to_dict()
            if hasattr(action_report_obj, "to_dict")
            else dict(action_report_obj or {})
        )
        ok = bool(action_report.get("ok"))
        report = ControlExecutionReport(
            dispatch_report=dispatch_report,
            decision="executed" if ok else "failed",
            ok=ok,
            allow_control=True,
            ownership_required=self._require_owned_session_for_execution,
            transport_gate_decision=transport_gate.decision,
            transport_gate_error=transport_gate.error,
            foreground_takeover_request=transport_gate.takeover_request,
            action_report=action_report,
            error=str(action_report.get("error", "") or ""),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        report = _enforce_no_foreground_contract(report)
        return _finalize_execution_report(
            report,
            trajectory_root=trajectory_root,
            trajectory_metadata=trajectory_metadata,
        )

    def execute_command_intent(
        self,
        intent: CommandPlanIntent | dict,
        *,
        allow_control: bool = False,
    ) -> ControlCommandExecutionReport:
        started = time.perf_counter()
        plan = self.plan_command_intent(intent)
        ownership_required = bool(
            self._require_owned_session_for_execution
            or plan.policy.require_owned_session
        )
        if not plan.ok:
            return ControlCommandExecutionReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=allow_control,
                ownership_required=ownership_required,
                error=plan.error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        if not allow_control:
            return ControlCommandExecutionReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=False,
                ownership_required=ownership_required,
                error="explicit_control_permission_required",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        if ownership_required and not plan.execution_request.ownership.owned:
            return ControlCommandExecutionReport(
                command_plan=plan,
                decision="blocked",
                ok=False,
                allow_control=True,
                ownership_required=True,
                error="owned_session_required",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        action_report = CommandRunner(plan.policy).execute(plan.execution_request).to_dict()
        ok = bool(action_report.get("ok"))
        return ControlCommandExecutionReport(
            command_plan=plan,
            decision="executed" if ok else "failed",
            ok=ok,
            allow_control=True,
            ownership_required=ownership_required,
            action_report=action_report,
            error=str(action_report.get("error", "") or ""),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    def plan_command_intent(self, intent: CommandPlanIntent | dict) -> CommandPlanReport:
        command_intent = self._command_plan_intent(intent)
        return CommandPlanner().plan(command_intent)

    def _plan_for_route(
        self,
        target: ConnectorTarget,
        intent: ControlIntent,
        route_plan: ControlRoutePlan,
        selected_route: str,
        started: float,
        session_discovery: dict | None,
        ownership: SessionOwnership,
        side_effect_gate: SideEffectGateReport,
    ) -> ControlDispatchReport:
        if not side_effect_gate.allowed:
            return _report(
                target,
                intent,
                route_plan,
                started,
                decision=side_effect_gate.decision,
                execution_mode="none",
                selected_route=selected_route,
                blocked=True,
                reason=side_effect_gate.reason,
                session_discovery=session_discovery,
                ownership=ownership,
                side_effect_gate=side_effect_gate,
            )

        if _is_hard_block(target, route_plan, selected_route=selected_route):
            return _report(
                target,
                intent,
                route_plan,
                started,
                decision="blocked",
                execution_mode="none",
                selected_route=selected_route,
                blocked=True,
                reason="no_deterministic_route",
                session_discovery=session_discovery,
                ownership=ownership,
                side_effect_gate=side_effect_gate,
            )

        if selected_route in _UIA_CONNECTOR_ROUTE_IDS:
            if route_plan.is_blocked or not _route_is_declared(route_plan, selected_route):
                return _report(
                    target,
                    intent,
                    route_plan,
                    started,
                    decision="blocked",
                    execution_mode="none",
                    selected_route=selected_route,
                    blocked=True,
                    reason="uia_route_not_allowed_by_policy",
                    session_discovery=session_discovery,
                    ownership=ownership,
                    side_effect_gate=side_effect_gate,
                )
            resolution = self._resolve_route_connector(target, selected_route, intent)
            if resolution.connector is not None:
                transport = build_transport_capability(
                    route_plan,
                    intent,
                    selected_route=selected_route,
                )
                return _report(
                    target,
                    intent,
                    route_plan,
                    started,
                    decision="dispatch_connector",
                    execution_mode=(
                        "foreground_uia" if transport.foreground_required else "background_uia"
                    ),
                    selected_route=selected_route,
                    selected_connector_id=resolution.connector.connector_id,
                    installed_connector_ids=resolution.installed_connector_ids,
                    candidate_connector_ids=resolution.candidate_connector_ids,
                    connector_ready=True,
                    background_safe=transport.background_safe,
                    foreground_required=transport.foreground_required,
                    reason="policy_bound_uia_connector_available",
                    session_discovery=session_discovery,
                    ownership=ownership,
                    side_effect_gate=side_effect_gate,
                )

        if selected_route in _CONNECTOR_ROUTE_IDS:
            resolution = self._resolve_route_connector(target, selected_route, intent)
            if resolution.connector is not None:
                transport = build_transport_capability(
                    route_plan,
                    intent,
                    selected_route=selected_route,
                )
                return _report(
                    target,
                    intent,
                    route_plan,
                    started,
                    decision="dispatch_connector",
                    execution_mode="connector",
                    selected_route=selected_route,
                    selected_connector_id=resolution.connector.connector_id,
                    installed_connector_ids=resolution.installed_connector_ids,
                    candidate_connector_ids=resolution.candidate_connector_ids,
                    connector_ready=True,
                    background_safe=transport.background_safe,
                    foreground_required=transport.foreground_required,
                    reason="deterministic_connector_available",
                    session_discovery=session_discovery,
                    ownership=ownership,
                    side_effect_gate=side_effect_gate,
                )
            if selected_route == "app-native-bridge-required" and not resolution.candidate_connector_ids:
                if _input_candidate_count(target, route_plan) <= 0:
                    return _report(
                        target,
                        intent,
                        route_plan,
                        started,
                        decision="blocked",
                        execution_mode="none",
                        selected_route=selected_route,
                        installed_connector_ids=resolution.installed_connector_ids,
                        candidate_connector_ids=resolution.candidate_connector_ids,
                        blocked=True,
                        reason="no_deterministic_route",
                        session_discovery=session_discovery,
                        ownership=ownership,
                        side_effect_gate=side_effect_gate,
                    )
            else:
                reason = f"no_connector_available:{selected_route}"
                if resolution.candidate_connector_ids:
                    reason = f"connector_installed_session_not_ready:{selected_route}"
                return _report(
                    target,
                    intent,
                    route_plan,
                    started,
                    decision="connector_required",
                    execution_mode="none",
                    selected_route=selected_route,
                    installed_connector_ids=resolution.installed_connector_ids,
                    candidate_connector_ids=resolution.candidate_connector_ids,
                    background_safe=build_transport_capability(
                        route_plan,
                        intent,
                        selected_route=selected_route,
                    ).background_safe,
                    reason=reason,
                    session_discovery=session_discovery,
                    ownership=ownership,
                    side_effect_gate=side_effect_gate,
                )

        if selected_route == "uia-semantic":
            return _report(
                target,
                intent,
                route_plan,
                started,
                decision="dispatch_background_uia",
                execution_mode="background_uia",
                selected_route=selected_route,
                background_safe=True,
                reason="semantic_accessibility_patterns_available",
                session_discovery=session_discovery,
                ownership=ownership,
                side_effect_gate=side_effect_gate,
            )

        if selected_route in _FOREGROUND_UIA_ROUTES or route_plan.primary_route.route_id in _FOREGROUND_UIA_ROUTES:
            if _input_candidate_count(target, route_plan) > 0 and intent.allow_foreground_interaction:
                foreground_route = _first_foreground_route(route_plan, selected_route)
                return _report(
                    target,
                    intent,
                    route_plan,
                    started,
                    decision="dispatch_foreground_uia",
                    execution_mode="foreground_uia",
                    selected_route=foreground_route,
                    foreground_required=True,
                    reason="foreground_uia_fallback_explicitly_allowed",
                    session_discovery=session_discovery,
                    ownership=ownership,
                    side_effect_gate=side_effect_gate,
                )
            return _report(
                target,
                intent,
                route_plan,
                started,
                decision="foreground_or_native_required",
                execution_mode="none",
                selected_route=selected_route,
                foreground_required=True,
                reason="foreground_uia_or_native_connector_required",
                session_discovery=session_discovery,
                ownership=ownership,
                side_effect_gate=side_effect_gate,
            )

        return _report(
            target,
            intent,
            route_plan,
            started,
            decision="observe_only",
            execution_mode="none",
            selected_route=selected_route,
            reason="no_writable_route_selected",
            session_discovery=session_discovery,
            ownership=ownership,
            side_effect_gate=side_effect_gate,
        )

    def _ownership_for_target(
        self,
        target_or_window: object,
        target: ConnectorTarget,
    ) -> SessionOwnership:
        ownership = getattr(target_or_window, "ownership", None)
        if isinstance(ownership, SessionOwnership):
            return ownership
        return self._ownership_index.match(target)

    def _command_plan_intent(self, intent: CommandPlanIntent | dict) -> CommandPlanIntent:
        command_intent = (
            intent
            if isinstance(intent, CommandPlanIntent)
            else CommandPlanIntent.from_dict(intent if isinstance(intent, dict) else {})
        )
        ownership = command_intent.ownership
        if not ownership.owned:
            ownership = self._ownership_index.match(_command_ownership_target(command_intent))
        require_owned = bool(
            command_intent.require_owned_session
            or self._require_owned_session_for_execution
        )
        if ownership is command_intent.ownership and require_owned == command_intent.require_owned_session:
            return command_intent
        return dataclasses.replace(
            command_intent,
            ownership=ownership,
            require_owned_session=require_owned,
        )

    def _resolve_route_connector(
        self,
        target: ConnectorTarget,
        route_id: str,
        intent: ControlIntent,
    ) -> _ConnectorResolution:
        connectors = tuple(getattr(self._connector_manager, "_connectors", ()) or ())
        installed_connector_ids = tuple(connector.connector_id for connector in connectors)
        preferred = (intent.preferred_connector_id or "").strip()
        candidates = _ordered_connectors(connectors, preferred)
        route_candidates = tuple(
            connector
            for connector in candidates
            if _connector_is_candidate_for_route(connector, route_id, target)
        )
        for connector in candidates:
            if not _connector_matches_route(connector, route_id):
                continue
            if not _connector_supports_target(connector, target):
                continue
            if (
                not self._require_connector_session_ready
                or _connector_session_ready(connector, route_id, target)
            ):
                return _ConnectorResolution(
                    connector=connector,
                    installed_connector_ids=installed_connector_ids,
                    candidate_connector_ids=tuple(item.connector_id for item in route_candidates),
                )
        return _ConnectorResolution(
            connector=None,
            installed_connector_ids=installed_connector_ids,
            candidate_connector_ids=tuple(item.connector_id for item in route_candidates),
        )

    def _resolve_executable_connector(
        self,
        report: ControlDispatchReport,
    ) -> _ExecutableConnectorResolution:
        target = report.target
        selected_id = (report.selected_connector_id or "").strip()
        if not selected_id:
            return _ExecutableConnectorResolution(None, "connector_execution_not_available")
        connectors = tuple(getattr(self._connector_manager, "_connectors", ()) or ())
        for connector in connectors:
            if connector.connector_id != selected_id:
                continue
            if not _connector_matches_route(connector, report.selected_route):
                continue
            if not _connector_supports_target(connector, target):
                continue
            return _ExecutableConnectorResolution(connector)
        return _ExecutableConnectorResolution(None, "connector_execution_not_available")


def default_connector_manager() -> ConnectorManager:
    from openwukong.connectors import (
        AgentNativeBridgeConnector,
        BrowserSessionConnector,
        DesktopUIAConnector,
        GitCommandConnector,
        FileSystemConnector,
        OfficeSessionConnector,
        IDEExtensionConnector,
        TerminalCommandConnector,
        WeChatNativeBridgeConnector,
    )

    return ConnectorManager(
        [
            WeChatNativeBridgeConnector(),
            AgentNativeBridgeConnector(),
            BrowserSessionConnector(),
            GitCommandConnector(),
            FileSystemConnector(),
            OfficeSessionConnector(),
            TerminalCommandConnector(),
            IDEExtensionConnector(),
            DesktopUIAConnector(),
        ]
    )


def _finalize_execution_report(
    report: ControlExecutionReport,
    *,
    trajectory_root: str | Path = "",
    trajectory_metadata: Optional[dict] = None,
) -> ControlExecutionReport:
    root_text = str(trajectory_root or "").strip()
    if not root_text:
        return report
    try:
        recorder = ControlTrajectoryRecorder(
            root_text,
            scenario="control-fabric-execute",
            target_id=_trajectory_target_id(report.dispatch_report),
            metadata={
                "route": report.selected_route,
                "connector_id": report.selected_connector_id,
                "decision": report.decision,
                **dict(trajectory_metadata or {}),
            },
        )
        final_report = dataclasses.replace(
            report,
            trajectory_id=recorder.trajectory_id,
            trajectory_path=str(recorder.manifest_path),
        )
        recorder.record_step(
            phase="dispatch",
            action=str(report.dispatch_report.intent.action or ""),
            report=report.dispatch_report,
        )
        recorder.record_step(
            phase="execution",
            action=str(report.dispatch_report.intent.action or ""),
            report=final_report,
            artifacts=extract_trajectory_artifacts(final_report.action_report),
        )
        return final_report
    except OSError as exc:
        return dataclasses.replace(
            report,
            trajectory_error=f"trajectory_write_failed:{type(exc).__name__}",
        )


def _enforce_no_foreground_contract(
    report: ControlExecutionReport,
) -> ControlExecutionReport:
    if report.selected_route in _COMMAND_EXECUTION_ROUTES:
        return report
    if not report.action_report:
        return report

    transport = report.dispatch_report.transport_capability or build_transport_capability(
        report.dispatch_report.route_plan,
        report.dispatch_report.intent,
        selected_route=report.dispatch_report.selected_route,
    )
    contract = build_no_foreground_contract(
        report.dispatch_report.route_plan,
        report.dispatch_report.intent,
        transport=transport,
        selected_route=report.dispatch_report.selected_route,
    )
    validation = validate_no_foreground_contract(contract, report.action_report)
    if validation.ok:
        return report

    violations = ",".join(validation.violations) or validation.decision
    return dataclasses.replace(
        report,
        ok=False,
        decision="failed",
        error=f"no_foreground_contract_violation:{violations}",
    )


def _trajectory_target_id(report: ControlDispatchReport) -> str:
    target = report.target
    for value in (
        target.session_id,
        target.workspace_id,
        target.resource_url,
        target.window_title,
        target.process_name,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return report.selected_route or "control-fabric-target"


def _report(
    target: ConnectorTarget,
    intent: ControlIntent,
    route_plan: ControlRoutePlan,
    started: float,
    *,
    decision: str,
    execution_mode: str,
    selected_route: str,
    selected_connector_id: str = "",
    installed_connector_ids: tuple[str, ...] = (),
    candidate_connector_ids: tuple[str, ...] = (),
    connector_ready: bool = False,
    session_discovery: dict | None = None,
    background_safe: bool = False,
    foreground_required: bool = False,
    blocked: bool = False,
    reason: str = "",
    ownership: SessionOwnership | None = None,
    side_effect_gate: SideEffectGateReport | None = None,
) -> ControlDispatchReport:
    transport_capability = build_transport_capability(
        route_plan,
        intent,
        selected_route=selected_route,
    )
    return ControlDispatchReport(
        target=target,
        intent=intent,
        route_plan=route_plan,
        decision=decision,
        execution_mode=execution_mode,
        selected_route=selected_route,
        selected_connector_id=selected_connector_id,
        installed_connector_ids=installed_connector_ids,
        candidate_connector_ids=candidate_connector_ids,
        connector_ready=connector_ready,
        session_discovery=session_discovery,
        background_safe=background_safe,
        foreground_required=foreground_required,
        transport_capability=transport_capability,
        side_effect_gate=side_effect_gate or evaluate_side_effect_policy({}),
        blocked=blocked,
        reason=reason,
        ownership=ownership or SessionOwnership.unowned(),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _preferred_route(intent: ControlIntent, route_plan: ControlRoutePlan) -> str:
    preferred = (intent.preferred_route_id or "").strip()
    if preferred:
        return preferred
    if str(intent.action or "").strip().lower() in {
        "launch_app",
        "launch_application",
        "start_application",
    }:
        return "desktop-app-launch"
    return route_plan.primary_route.route_id


def _is_hard_block(
    target: ConnectorTarget,
    route_plan: ControlRoutePlan,
    *,
    selected_route: str = "",
) -> bool:
    del target
    if selected_route == "desktop-app-launch":
        return False
    if (
        selected_route in _UIA_CONNECTOR_ROUTE_IDS
        and not route_plan.is_blocked
        and _route_is_declared(route_plan, selected_route)
    ):
        return False
    route_id = route_plan.primary_route.route_id
    if route_id == "no-deterministic-route":
        return True
    if route_id not in _CONNECTOR_ROUTE_IDS and "no_accessible_elements" in route_plan.missing_capabilities:
        return True
    return False


def _route_is_declared(route_plan: ControlRoutePlan, route_id: str) -> bool:
    declared = {route_plan.primary_route.route_id}
    declared.update(route.route_id for route in route_plan.fallback_routes)
    return route_id in declared


def _first_foreground_route(route_plan: ControlRoutePlan, selected_route: str) -> str:
    if selected_route in {"uia-structural", "uia-structural-observe"}:
        return selected_route
    for route in route_plan.fallback_routes:
        if route.route_id in {"uia-structural", "uia-structural-observe"}:
            return route.route_id
    return selected_route


def _ordered_connectors(
    connectors: Iterable[SessionConnector],
    preferred_connector_id: str,
) -> tuple[SessionConnector, ...]:
    items = tuple(connectors)
    preferred = preferred_connector_id.lower()
    if not preferred:
        return items
    return tuple(
        sorted(
            items,
            key=lambda connector: (
                0 if connector.connector_id.lower() == preferred else 1,
                connector.connector_id,
            ),
        )
    )


def _connector_matches_route(connector: SessionConnector, route_id: str) -> bool:
    route_values = {
        str(getattr(connector, "route_id", "") or ""),
        str(getattr(connector, "devtools_route_id", "") or ""),
        str(getattr(connector, "http_route_id", "") or ""),
    }
    if route_id in route_values:
        return True
    route_ids = getattr(connector, "route_ids", ())
    if isinstance(route_ids, str):
        route_ids = (route_ids,)
    if route_id in {str(item or "") for item in route_ids}:
        return True
    return connector.connector_id in _ROUTE_CONNECTOR_IDS.get(route_id, ())


def _connector_is_candidate_for_route(
    connector: SessionConnector,
    route_id: str,
    target: ConnectorTarget,
) -> bool:
    if not _connector_matches_route(connector, route_id):
        return False
    if connector.connector_id in {"agent-native-bridge", "wechat-native-bridge"}:
        return _connector_supports_target(connector, target)
    return True


def _connector_supports_target(connector: SessionConnector, target: ConnectorTarget) -> bool:
    try:
        return int(connector.match_score(target)) >= 0
    except Exception:
        try:
            return bool(connector.supports_target(target))
        except Exception:
            return False


def _connector_session_ready(
    connector: SessionConnector,
    route_id: str,
    target: ConnectorTarget,
) -> bool:
    route_ready = getattr(connector, "route_ready", None)
    if callable(route_ready):
        try:
            return bool(route_ready(route_id, target))
        except Exception:
            return False

    connector_id = connector.connector_id
    if connector_id == "browser" and route_id == "browser-devtools-or-extension":
        return bool((target.debugger_url or "").strip())
    if connector_id == "browser" and route_id == "browser-http-session":
        return bool((target.resource_url or "").strip())
    if connector_id == "ide-extension":
        return bool((target.ide_bridge_url or "").strip())
    if connector_id == "agent-native-bridge":
        return bool((target.agent_native_bridge_url or "").strip())
    if connector_id == "wechat-native-bridge":
        return bool((target.wechat_native_bridge_url or "").strip())
    if connector_id in {"terminal", "git"}:
        return _has_workspace_dir(target)
    return True


def _dispatch_allows_browser_devtools_action(report: ControlDispatchReport) -> bool:
    return (
        report.decision == "dispatch_connector"
        and report.selected_route == "browser-devtools-or-extension"
        and report.selected_connector_id == "browser"
        and report.connector_ready
        and bool((report.target.debugger_url or "").strip())
    )


def _dispatch_allows_connector_action(report: ControlDispatchReport) -> bool:
    return (
        report.decision == "dispatch_connector"
        and report.connector_ready
        and bool(report.selected_connector_id)
        and report.selected_route in (_CONNECTOR_ROUTE_IDS | _UIA_CONNECTOR_ROUTE_IDS)
    )


def _build_bound_foreground_takeover_request(
    report: ControlDispatchReport,
) -> ForegroundTakeoverRequest:
    """Bind an approval artifact to the exact PID and typed action payload."""
    request = build_foreground_takeover_request(report)
    intent = report.intent
    target = report.target
    material = {
        "base_request_id": request.to_dict().get("request_id", ""),
        "selected_route": report.selected_route,
        "selected_transport": str(
            getattr(report.transport_capability, "selected_transport", "") or ""
        ),
        "target": {
            "pid": int(target.pid or 0),
            "process_name": target.process_name,
            "window_title": target.window_title,
            "workspace_id": target.workspace_id,
            "session_id": target.session_id,
        },
        "intent": {
            "action": intent.action,
            "text": intent.text,
            "url": intent.url,
            "selector": intent.selector,
            "value": intent.value,
            "submit": bool(intent.submit),
            "preferred_connector_id": intent.preferred_connector_id,
            "preferred_route_id": intent.preferred_route_id,
            "parameters": _stable_approval_value(intent.parameters),
        },
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return dataclasses.replace(request, request_id=f"fgt-{digest[:24]}")


def _stable_approval_value(value: object):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        pairs = sorted(value.items(), key=lambda item: str(item[0]))
        return {str(key): _stable_approval_value(item) for key, item in pairs}
    if isinstance(value, (list, tuple)):
        return [_stable_approval_value(item) for item in value]
    return {"type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _evaluate_transport_execution_gate(
    report: ControlDispatchReport,
    *,
    foreground_takeover_approval: ForegroundTakeoverRequest | Mapping[str, object] | None = None,
) -> _TransportExecutionGate:
    transport = report.transport_capability or build_transport_capability(
        report.route_plan,
        report.intent,
        selected_route=report.selected_route,
    )
    if transport.blocked or transport.capability_level == "blocked":
        return _TransportExecutionGate(
            allowed=False,
            decision="blocked_transport_capability",
            error="transport_capability_blocked",
        )
    if transport.foreground_required or transport.capability_level == "foreground-required":
        request = _build_bound_foreground_takeover_request(report)
        if foreground_takeover_approval is not None:
            validation = validate_foreground_takeover_request(
                foreground_takeover_approval,
                action=report.intent.action,
                target_process_names=(report.target.process_name,),
                selected_transport=transport.selected_transport,
            )
            approved = validation.request
            if not validation.valid:
                return _TransportExecutionGate(
                    allowed=False,
                    decision="blocked_foreground_takeover_invalid",
                    error=validation.decision,
                    takeover_request=approved or request,
                )
            if not _foreground_approval_matches(request, approved):
                return _TransportExecutionGate(
                    allowed=False,
                    decision="blocked_foreground_takeover_invalid",
                    error="foreground_takeover_target_binding_mismatch",
                    takeover_request=approved or request,
                )
            if str(getattr(approved, "status", "") or "").strip().lower() != "approved":
                return _TransportExecutionGate(
                    allowed=False,
                    decision="blocked_foreground_takeover_not_approved",
                    error="foreground_takeover_approval_required",
                    takeover_request=approved or request,
                )
            if not report.intent.allow_foreground_interaction:
                return _TransportExecutionGate(
                    allowed=False,
                    decision="blocked_foreground_takeover_not_allowed",
                    error="foreground_takeover_not_allowed",
                    takeover_request=approved,
                )
            return _TransportExecutionGate(
                allowed=True,
                decision="allow_approved_foreground_takeover",
                takeover_request=approved,
            )
        return _TransportExecutionGate(
            allowed=False,
            decision="blocked_foreground_takeover_required",
            error="foreground_takeover_confirmation_required",
            takeover_request=request,
        )
    return _TransportExecutionGate(allowed=True)


def _foreground_approval_matches(
    expected: ForegroundTakeoverRequest,
    approved: ForegroundTakeoverRequest | None,
) -> bool:
    if approved is None:
        return False
    expected_data = expected.to_dict()
    approved_data = approved.to_dict()
    for field in (
        "request_id",
        "action",
        "target_process_name",
        "target_window_title",
        "selected_route",
        "selected_transport",
    ):
        left = str(expected_data.get(field, "") or "").strip().casefold()
        right = str(approved_data.get(field, "") or "").strip().casefold()
        if left != right:
            return False
    return True


def _connector_message_from_intent(intent: ControlIntent) -> str:
    for value in (intent.text, intent.value, intent.url):
        message = str(value or "").strip()
        if message:
            return message
    return str(intent.action or "").strip()


def _connector_action_result_to_dict(result) -> dict:
    payload = getattr(result, "payload", None) or {}
    return {
        "mode": "connector-action",
        "ok": bool(getattr(result, "success", False)),
        "control_allowed": bool(getattr(result, "success", False)),
        "control_attempts": _connector_control_attempts(payload),
        "connector_id": str(getattr(result, "connector_id", "") or ""),
        "action": str(getattr(result, "action", "") or ""),
        "action_key": str(getattr(result, "action_key", "") or ""),
        "payload": dict(payload),
        "error": str(getattr(result, "error", "") or ""),
    }


def _connector_control_attempts(payload: dict) -> int:
    if not isinstance(payload, dict):
        return 0
    attempts = payload.get("control_attempts")
    if attempts is not None:
        try:
            return int(attempts)
        except (TypeError, ValueError):
            return 0
    if "exit_code" in payload or "runner_mode" in payload:
        return 1
    return 1


def _default_browser_action_runner():
    from openwukong.evaluation.browser_devtools_action import run_browser_devtools_action

    return run_browser_devtools_action


def _has_workspace_dir(target: ConnectorTarget) -> bool:
    for value in (target.workspace_path, target.workspace_hint):
        candidate = (value or "").strip()
        if candidate and os.path.isdir(candidate):
            return True
    return False


def _command_ownership_target(intent: CommandPlanIntent) -> ConnectorTarget:
    workspace = str(intent.workspace_root or intent.cwd or "").strip()
    operation = str(intent.operation or "").strip().lower()
    process_name = "git.exe" if operation.startswith("git.") else "powershell.exe"
    route_hint = "git" if operation.startswith("git.") else "terminal"
    return ConnectorTarget(
        process_name=process_name,
        window_title="Command Intelligence",
        workspace_path=workspace,
        workspace_hint=workspace or route_hint,
    )


def _connector_target_from(target_or_window: object) -> ConnectorTarget:
    if isinstance(target_or_window, ConnectorTarget):
        return target_or_window
    to_connector_target = getattr(target_or_window, "to_connector_target", None)
    if callable(to_connector_target):
        target = to_connector_target()
        if isinstance(target, ConnectorTarget):
            return target
    return ConnectorTarget(
        pid=int(_attr(target_or_window, "pid", 0) or 0),
        process_name=str(_attr(target_or_window, "process_name", "") or ""),
        window_title=str(_attr(target_or_window, "window_title", "") or ""),
        project_name=str(_attr(target_or_window, "project_name", "") or ""),
        workspace_hint=str(_attr(target_or_window, "workspace_hint", "") or ""),
        workspace_path=str(_attr(target_or_window, "workspace_path", "") or ""),
        resource_url=str(_attr(target_or_window, "resource_url", "") or ""),
        debugger_url=str(_attr(target_or_window, "debugger_url", "") or ""),
        ide_bridge_url=str(_attr(target_or_window, "ide_bridge_url", "") or ""),
        agent_native_bridge_url=str(
            _attr(target_or_window, "agent_native_bridge_url", "") or ""
        ),
        wechat_native_bridge_url=str(
            _attr(target_or_window, "wechat_native_bridge_url", "") or ""
        ),
        conversation_name=str(_attr(target_or_window, "conversation_name", "") or ""),
        background_screenshot_focus_stable=bool(
            _attr(target_or_window, "background_screenshot_focus_stable", True)
        ),
        background_screenshot_count=_safe_int(
            _attr(target_or_window, "background_screenshot_count", 0)
        ),
        background_screenshot_success_count=_safe_int(
            _attr(target_or_window, "background_screenshot_success_count", 0)
        ),
    )


def _session_discovery_dict(target_or_window: object) -> dict | None:
    getter = getattr(target_or_window, "session_discovery_dict", None)
    if callable(getter):
        data = getter()
        if isinstance(data, dict):
            return data
    return None


def _target_to_dict(target: ConnectorTarget) -> dict:
    return {
        "workspace_id": target.workspace_id,
        "session_id": target.session_id,
        "pid": target.pid,
        "process_name": target.process_name,
        "window_title": target.window_title,
        "project_name": target.project_name,
        "workspace_hint": target.workspace_hint,
        "workspace_path": target.workspace_path,
        "resource_url": target.resource_url,
        "debugger_url": target.debugger_url,
        "ide_bridge_url": target.ide_bridge_url,
        "agent_native_bridge_url": target.agent_native_bridge_url,
        "wechat_native_bridge_url": target.wechat_native_bridge_url,
        "conversation_name": target.conversation_name,
        "background_screenshot_focus_stable": target.background_screenshot_focus_stable,
        "background_screenshot_count": target.background_screenshot_count,
        "background_screenshot_success_count": target.background_screenshot_success_count,
    }


def _input_candidate_count(target: ConnectorTarget, route_plan: ControlRoutePlan) -> int:
    del target
    if "no_input_candidate" in route_plan.missing_capabilities:
        return 0
    return 1


def _attr(obj: object, name: str, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _intent_parameters_to_dict(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    redacted = {}
    for key, item in value.items():
        name = str(key or "")
        if name.lower() in {"text", "value", "keys"}:
            redacted[f"{name}_preview"] = _clip(str(item or ""))
        elif name.lower() in {"password", "secret", "token", "api_key"}:
            redacted[name] = "[redacted]"
        else:
            redacted[name] = item
    return redacted


def _clip(value: str, limit: int = 500) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]
