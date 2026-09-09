# -*- coding: utf-8 -*-
"""Global no-foreground execution contract for desktop control.

The contract records whether a route may run without taking the user's active
desktop session, and validates action reports against that promise. It is a
plan/evidence layer only; it never executes GUI primitives.
"""

from __future__ import annotations

import dataclasses
from typing import Mapping

from openwukong.control.transport_capability import (
    TransportCapabilityReport,
    build_transport_capability,
)


CONTRACT_VERSION = "no-foreground-v1"


@dataclasses.dataclass(frozen=True)
class NoForegroundContract:
    """Declarative focus/cursor/input boundary for a pending control action."""

    action: str
    app_family: str
    route_id: str
    selected_route: str
    selected_transport: str
    transport_channel: str
    foreground_required: bool = False
    foreground_takeover_allowed: bool = False
    can_execute_without_focus: bool = False
    window_focus_must_remain_stable: bool = True
    keyboard_input_allowed: bool = False
    mouse_input_allowed: bool = False
    clipboard_write_allowed: bool = False
    system_cursor_movement_allowed: bool = False
    requires_user_confirmation: bool = False
    required_evidence: tuple[str, ...] = ()
    blocked: bool = False
    blocking_reason: str = ""

    @property
    def mode(self) -> str:
        return "no-foreground-control-contract"

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
        return {
            "mode": self.mode,
            "contract_version": CONTRACT_VERSION,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "action": self.action,
            "app_family": self.app_family,
            "route_id": self.route_id,
            "selected_route": self.selected_route,
            "selected_transport": self.selected_transport,
            "transport_channel": self.transport_channel,
            "foreground_required": self.foreground_required,
            "foreground_takeover_allowed": self.foreground_takeover_allowed,
            "can_execute_without_focus": self.can_execute_without_focus,
            "window_focus_must_remain_stable": self.window_focus_must_remain_stable,
            "keyboard_input_allowed": self.keyboard_input_allowed,
            "mouse_input_allowed": self.mouse_input_allowed,
            "clipboard_write_allowed": self.clipboard_write_allowed,
            "system_cursor_movement_allowed": self.system_cursor_movement_allowed,
            "requires_user_confirmation": self.requires_user_confirmation,
            "required_evidence": list(self.required_evidence),
            "blocked": self.blocked,
            "blocking_reason": self.blocking_reason,
        }


@dataclasses.dataclass(frozen=True)
class NoForegroundValidationReport:
    """Validation of an action report against a no-foreground contract."""

    contract: NoForegroundContract
    ok: bool
    decision: str
    violations: tuple[str, ...] = ()
    action_report_present: bool = False

    @property
    def mode(self) -> str:
        return "no-foreground-contract-validation"

    @property
    def safety_mode(self) -> str:
        return "evidence_validation"

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
            "ok": self.ok,
            "decision": self.decision,
            "violations": list(self.violations),
            "action_report_present": self.action_report_present,
            "contract": self.contract.to_dict(),
        }


def build_no_foreground_contract(
    route_plan: object,
    intent: object | None = None,
    *,
    transport: TransportCapabilityReport | None = None,
    selected_route: str = "",
) -> NoForegroundContract:
    """Build the focus/input contract for a route plan and intent."""

    capability = transport or build_transport_capability(
        route_plan,
        intent,
        selected_route=selected_route,
    )
    foreground_allowed = bool(getattr(intent, "allow_foreground_interaction", False))
    foreground_channel = capability.transport_channel == "foreground_input"
    foreground_inputs_allowed = bool(foreground_allowed and foreground_channel)
    blocked, reason = _contract_block(capability, foreground_allowed)

    return NoForegroundContract(
        action=str(capability.action or ""),
        app_family=str(capability.app_family or ""),
        route_id=str(capability.route_id or ""),
        selected_route=str(capability.selected_route or ""),
        selected_transport=str(capability.selected_transport or ""),
        transport_channel=str(capability.transport_channel or ""),
        foreground_required=bool(capability.foreground_required),
        foreground_takeover_allowed=foreground_allowed,
        can_execute_without_focus=bool(capability.can_execute_without_focus),
        window_focus_must_remain_stable=not foreground_allowed,
        keyboard_input_allowed=foreground_inputs_allowed,
        mouse_input_allowed=foreground_inputs_allowed,
        clipboard_write_allowed=foreground_inputs_allowed,
        system_cursor_movement_allowed=foreground_inputs_allowed,
        requires_user_confirmation=bool(capability.requires_user_confirmation),
        required_evidence=_required_evidence(capability, foreground_allowed),
        blocked=blocked,
        blocking_reason=reason,
    )


def validate_no_foreground_contract(
    contract: NoForegroundContract,
    action_report: Mapping[str, object] | None,
) -> NoForegroundValidationReport:
    """Validate a connector/action report against the declared contract."""

    payload = _validation_payload(action_report)
    if not payload:
        return NoForegroundValidationReport(
            contract=contract,
            ok=not contract.blocked,
            decision="no_action_report",
            violations=("contract_blocked",) if contract.blocked else (),
            action_report_present=False,
        )

    violations: list[str] = []
    if contract.blocked:
        violations.append("contract_blocked")
    if contract.foreground_required and not contract.foreground_takeover_allowed:
        violations.append("foreground_required_without_takeover_permission")
    if contract.window_focus_must_remain_stable and _foreground_changed(payload):
        violations.append("foreground_focus_changed")
    if not contract.keyboard_input_allowed and _attempts(payload, "keyboard_input_attempts") > 0:
        violations.append("keyboard_input_not_allowed")
    if not contract.mouse_input_allowed and _mouse_attempts(payload) > 0:
        violations.append("mouse_input_not_allowed")
    if not contract.clipboard_write_allowed and _attempts(payload, "clipboard_write_attempts") > 0:
        violations.append("clipboard_write_not_allowed")
    if (
        not contract.system_cursor_movement_allowed
        and _attempts(payload, "cursor_movement_attempts") > 0
    ):
        violations.append("system_cursor_movement_not_allowed")
    if (
        not contract.foreground_takeover_allowed
        and _attempts(payload, "foreground_takeover_attempts") > 0
    ):
        violations.append("foreground_takeover_not_allowed")

    unique = tuple(dict.fromkeys(violations))
    return NoForegroundValidationReport(
        contract=contract,
        ok=not unique,
        decision="validated" if not unique else "contract_violation",
        violations=unique,
        action_report_present=True,
    )


def _contract_block(
    capability: TransportCapabilityReport,
    foreground_allowed: bool,
) -> tuple[bool, str]:
    if capability.blocked or capability.capability_level == "blocked":
        return True, capability.blocking_reason or "transport_capability_blocked"
    if capability.foreground_required and not foreground_allowed:
        return True, "foreground_takeover_not_allowed"
    return False, ""


def _required_evidence(
    capability: TransportCapabilityReport,
    foreground_allowed: bool,
) -> tuple[str, ...]:
    evidence = list(capability.verification_requirements)
    if capability.can_execute_without_focus:
        evidence.extend(
            [
                "pre_action_foreground_hwnd",
                "post_action_foreground_hwnd",
                "foreground_focus_stability",
            ]
        )
    if capability.foreground_required or foreground_allowed:
        evidence.extend(
            [
                "explicit_foreground_takeover_request",
                "pre_action_target_verification",
                "post_action_bound_window_verification",
                "foreground_restore_verification",
            ]
        )
    return tuple(dict.fromkeys(item for item in evidence if str(item or "").strip()))


def _foreground_changed(payload: Mapping[str, object]) -> bool:
    if "foreground_changed" in payload:
        return bool(payload.get("foreground_changed"))
    if "foreground_focus_stable" in payload:
        return not bool(payload.get("foreground_focus_stable"))
    before = _safe_int(payload.get("foreground_hwnd_before"))
    after = _safe_int(payload.get("foreground_hwnd_after"))
    return bool(before and after and before != after)


def _validation_payload(action_report: Mapping[str, object] | None) -> dict:
    report = dict(action_report or {})
    nested = report.get("payload")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        merged.update(report)
        return merged
    return report


def _mouse_attempts(payload: Mapping[str, object]) -> int:
    keys = (
        "mouse_input_attempts",
        "mouse_move_attempts",
        "mouse_click_attempts",
        "window_input_attempts",
    )
    return sum(_attempts(payload, key) for key in keys)


def _attempts(payload: Mapping[str, object], key: str) -> int:
    return _safe_int(payload.get(key))


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
