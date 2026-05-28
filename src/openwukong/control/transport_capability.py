# -*- coding: utf-8 -*-
"""Background-safety transport capability matrix.

This module does not execute desktop actions. It classifies a route plan plus
an intent into the safest available transport tier so callers can decide
whether an action can run without focus, needs a foreground takeover, or must
stay blocked.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable

from openwukong.connectors.route_policy import ControlRoutePlan


BACKGROUND_NATIVE = "background-native"
BACKGROUND_READ_ONLY = "background-read-only"
FOREGROUND_REQUIRED = "foreground-required"
BLOCKED = "blocked"


_READ_ACTIONS = {
    "inspect",
    "locate",
    "observe",
    "read",
    "read_page",
    "read_text",
    "screenshot",
}
_CONFIRMATION_ACTIONS = {
    "external_send",
    "file_modify",
    "send_message",
    "start_agent",
    "submit_form",
    "submit_task",
}
_CONNECTOR_TRANSPORTS = {
    "browser-devtools-or-extension": "chrome-devtools-protocol",
    "git-cli": "workspace-bound-git-cli",
    "ide-extension-connector": "ide-extension-bridge",
    "office-object-model-or-addin": "office-object-model-or-addin",
    "terminal-native-session": "managed-shell-or-conpty",
}


@dataclasses.dataclass(frozen=True)
class TransportCapabilityReport:
    app_family: str
    action: str
    route_id: str
    selected_route: str
    capability_level: str
    selected_transport: str
    transport_channel: str
    background_safe: bool = False
    foreground_required: bool = False
    can_execute_without_focus: bool = False
    requires_user_confirmation: bool = False
    blocked: bool = False
    blocking_reason: str = ""
    risk_flags: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    fallback_transports: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "transport-capability"

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
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "app_family": self.app_family,
            "action": self.action,
            "route_id": self.route_id,
            "selected_route": self.selected_route,
            "capability_level": self.capability_level,
            "selected_transport": self.selected_transport,
            "transport_channel": self.transport_channel,
            "background_safe": self.background_safe,
            "foreground_required": self.foreground_required,
            "can_execute_without_focus": self.can_execute_without_focus,
            "requires_user_confirmation": self.requires_user_confirmation,
            "blocked": self.blocked,
            "blocking_reason": self.blocking_reason,
            "risk_flags": list(self.risk_flags),
            "verification_requirements": list(self.verification_requirements),
            "fallback_transports": list(self.fallback_transports),
        }


def build_transport_capability(
    route_plan: ControlRoutePlan,
    intent: object | None = None,
    *,
    selected_route: str = "",
) -> TransportCapabilityReport:
    """Classify the safest transport tier for a route plan and intent."""

    action = _action(intent)
    route_id = route_plan.primary_route.route_id
    selected = (selected_route or _preferred_route(intent) or route_id).strip()
    requires_confirmation = _requires_confirmation(action, intent)
    fallbacks = _fallback_transport_ids(route_plan)

    if selected in _CONNECTOR_TRANSPORTS:
        return _report(
            route_plan,
            action,
            route_id,
            selected,
            capability_level=BACKGROUND_NATIVE,
            selected_transport=_CONNECTOR_TRANSPORTS[selected],
            transport_channel="connector",
            background_safe=True,
            can_execute_without_focus=True,
            requires_user_confirmation=requires_confirmation,
            verification_requirements=_connector_verification(selected),
            fallback_transports=fallbacks,
        )

    if selected == "uia-semantic":
        return _report(
            route_plan,
            action,
            route_id,
            selected,
            capability_level=BACKGROUND_NATIVE,
            selected_transport="uia-control-patterns",
            transport_channel="accessibility",
            background_safe=True,
            can_execute_without_focus=True,
            requires_user_confirmation=requires_confirmation,
            verification_requirements=("accessibility_readback",),
            fallback_transports=fallbacks,
        )

    if selected in {"uia-structural", "uia-structural-observe"}:
        if _is_read_action(action):
            return _report(
                route_plan,
                action,
                route_id,
                selected,
                capability_level=BACKGROUND_READ_ONLY,
                selected_transport="uia-tree-read",
                transport_channel="accessibility",
                background_safe=True,
                can_execute_without_focus=True,
                verification_requirements=("accessibility_snapshot",),
                fallback_transports=fallbacks,
            )
        return _foreground_report(
            route_plan,
            action,
            route_id,
            selected,
            requires_confirmation=requires_confirmation,
            risk_flags=("weak_semantic_locator", "foreground_focus_steal"),
            fallback_transports=fallbacks,
        )

    if selected == "app-native-bridge-required":
        if _is_read_action(action):
            return _report(
                route_plan,
                action,
                route_id,
                selected,
                capability_level=BACKGROUND_READ_ONLY,
                selected_transport="win32-msaa-uia-read",
                transport_channel="accessibility",
                background_safe=True,
                can_execute_without_focus=True,
                verification_requirements=("read_only_accessibility_snapshot",),
                fallback_transports=fallbacks,
            )
        return _foreground_report(
            route_plan,
            action,
            route_id,
            selected,
            requires_confirmation=True,
            risk_flags=("native_connector_missing", "foreground_focus_steal", "clipboard_mutation"),
            fallback_transports=fallbacks,
        )

    return _report(
        route_plan,
        action,
        route_id,
        selected,
        capability_level=BLOCKED,
        selected_transport="none",
        transport_channel="none",
        blocked=True,
        blocking_reason="no_deterministic_transport",
        risk_flags=("no_deterministic_transport",),
        fallback_transports=fallbacks,
    )


def _foreground_report(
    route_plan: ControlRoutePlan,
    action: str,
    route_id: str,
    selected_route: str,
    *,
    requires_confirmation: bool,
    risk_flags: Iterable[str],
    fallback_transports: Iterable[str],
) -> TransportCapabilityReport:
    return _report(
        route_plan,
        action,
        route_id,
        selected_route,
        capability_level=FOREGROUND_REQUIRED,
        selected_transport="foreground-keyboard-clipboard",
        transport_channel="foreground_input",
        foreground_required=True,
        requires_user_confirmation=requires_confirmation,
        risk_flags=tuple(risk_flags),
        verification_requirements=(
            "pre_action_target_verification",
            "post_action_bound_window_verification",
            "state_restore_verification",
        ),
        fallback_transports=tuple(fallback_transports),
    )


def _report(
    route_plan: ControlRoutePlan,
    action: str,
    route_id: str,
    selected_route: str,
    *,
    capability_level: str,
    selected_transport: str,
    transport_channel: str,
    background_safe: bool = False,
    foreground_required: bool = False,
    can_execute_without_focus: bool = False,
    requires_user_confirmation: bool = False,
    blocked: bool = False,
    blocking_reason: str = "",
    risk_flags: Iterable[str] = (),
    verification_requirements: Iterable[str] = (),
    fallback_transports: Iterable[str] = (),
) -> TransportCapabilityReport:
    return TransportCapabilityReport(
        app_family=route_plan.app_family,
        action=action,
        route_id=route_id,
        selected_route=selected_route,
        capability_level=capability_level,
        selected_transport=selected_transport,
        transport_channel=transport_channel,
        background_safe=background_safe,
        foreground_required=foreground_required,
        can_execute_without_focus=can_execute_without_focus,
        requires_user_confirmation=requires_user_confirmation,
        blocked=blocked,
        blocking_reason=blocking_reason,
        risk_flags=tuple(dict.fromkeys(str(item) for item in risk_flags if str(item or "").strip())),
        verification_requirements=tuple(
            dict.fromkeys(str(item) for item in verification_requirements if str(item or "").strip())
        ),
        fallback_transports=tuple(
            dict.fromkeys(str(item) for item in fallback_transports if str(item or "").strip())
        ),
    )


def _connector_verification(route_id: str) -> tuple[str, ...]:
    if route_id == "browser-devtools-or-extension":
        return ("devtools_result", "post_action_dom_or_accessibility_verification")
    if route_id == "terminal-native-session":
        return ("exit_code", "stdout_stderr_capture")
    if route_id == "git-cli":
        return ("exit_code", "git_stdout_capture")
    if route_id == "ide-extension-connector":
        return ("bridge_response", "ide_state_snapshot")
    if route_id == "office-object-model-or-addin":
        return ("object_model_readback",)
    return ("connector_result",)


def _fallback_transport_ids(route_plan: ControlRoutePlan) -> tuple[str, ...]:
    transports: list[str] = []
    for route in route_plan.fallback_routes:
        route_id = route.route_id
        if route_id in _CONNECTOR_TRANSPORTS:
            transports.append(_CONNECTOR_TRANSPORTS[route_id])
        elif route_id in {"uia-semantic", "uia-structural", "uia-structural-observe"}:
            transports.append(route_id)
        elif route_id == "msaa-win32-fallback":
            transports.append("msaa-win32-read")
        elif route_id == "vision-fallback-last":
            transports.append("vision-verify-last")
        else:
            transports.append(route_id)
    return tuple(dict.fromkeys(transports))


def _requires_confirmation(action: str, intent: object | None) -> bool:
    if action in _CONFIRMATION_ACTIONS:
        return True
    if bool(getattr(intent, "submit", False)) and not bool(getattr(intent, "allow_submit", False)):
        return True
    return False


def _is_read_action(action: str) -> bool:
    return action in _READ_ACTIONS or action.startswith("read_") or action.startswith("inspect_")


def _action(intent: object | None) -> str:
    return str(getattr(intent, "action", "") or "write_text").strip().lower()


def _preferred_route(intent: object | None) -> str:
    return str(getattr(intent, "preferred_route_id", "") or "").strip()
