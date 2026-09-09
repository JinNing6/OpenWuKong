# -*- coding: utf-8 -*-
"""Capability-first route negotiation for desktop actions."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from openwukong.control.desktop_action import DesktopAction
from openwukong.control.surface_capabilities import SurfaceCapabilityProfile


@dataclasses.dataclass(frozen=True)
class DesktopActionPlan:
    """Plan-only result; executing a plan is the responsibility of ControlFabric."""

    action: DesktopAction
    selected_route: str = ""
    selected_connector_id: str = ""
    execution_mode: str = "none"
    background_safe: bool = False
    foreground_required: bool = False
    blocked: bool = False
    reason: str = ""
    missing_capabilities: tuple[str, ...] = ()
    fallback_routes: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    control_attempts: int = 0

    @property
    def ready(self) -> bool:
        return bool(not self.blocked and self.selected_route)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "desktop-action-plan",
            "safety_mode": "plan_only",
            "ready": self.ready,
            "blocked": self.blocked,
            "reason": self.reason,
            "selected_route": self.selected_route,
            "selected_connector_id": self.selected_connector_id,
            "execution_mode": self.execution_mode,
            "background_safe": self.background_safe,
            "foreground_required": self.foreground_required,
            "missing_capabilities": list(self.missing_capabilities),
            "fallback_routes": list(self.fallback_routes),
            "risks": list(self.risks),
            "control_attempts": self.control_attempts,
            "action": self.action.to_safe_dict(),
        }


def plan_desktop_action(
    *,
    action: DesktopAction,
    profile: SurfaceCapabilityProfile,
    connectors: Iterable[object] = (),
    now: datetime | None = None,
) -> DesktopActionPlan:
    """Choose the strongest verified route for one action without executing it."""

    if not profile.is_fresh(now=now):
        return _blocked(action, "capability_missing", ("fresh_surface_profile",))
    if action.target.pid and action.target.hwnd and not profile.is_bound(
        pid=action.target.pid, hwnd=action.target.hwnd
    ):
        return _blocked(action, "target_not_bound", ("matching_pid_hwnd",))
    if not action.approval_satisfied:
        return _blocked(action, "side_effect_confirmation_required")

    connector_target = _connector_target(action)
    for connector in connectors:
        if not _connector_supports(connector, action, connector_target):
            continue
        route_id = str(getattr(connector, "route_id", "") or "").strip()
        connector_id = str(getattr(connector, "connector_id", "") or "").strip()
        if not route_id or not connector_id:
            continue
        return DesktopActionPlan(
            action=action,
            selected_route=route_id,
            selected_connector_id=connector_id,
            execution_mode="background_native",
            background_safe=True,
            risks=_risks_for(action, "background_native"),
        )

    grant = profile.grant(action.action)
    if not grant or not profile.supports(action.action, now=now):
        return _blocked(action, "capability_missing", (action.action,))

    route = str(grant.get("route", "") or "").strip()
    read_only = bool(grant.get("read_only", False))
    if route == "uia-semantic" and not read_only:
        return DesktopActionPlan(
            action=action,
            selected_route=route,
            execution_mode="background_semantic",
            background_safe=True,
            risks=_risks_for(action, "background_semantic"),
        )
    if route in {"uia-structural", "uia-structural-observe", "vision-input"}:
        if action.approval.confirmed and action.approval.allow_foreground:
            return DesktopActionPlan(
                action=action,
                selected_route=route,
                execution_mode="foreground_desktop",
                foreground_required=True,
                risks=_risks_for(action, "foreground_desktop"),
            )
        if read_only:
            return DesktopActionPlan(
                action=action,
                selected_route=route,
                execution_mode="read_only",
                background_safe=True,
                risks=_risks_for(action, "read_only"),
            )
        return _blocked(action, "foreground_approval_required", (route,))
    if read_only:
        return DesktopActionPlan(
            action=action,
            selected_route=route,
            execution_mode="read_only",
            background_safe=True,
            risks=_risks_for(action, "read_only"),
        )
    return _blocked(action, "unsupported_route", (route or "action_route",))


def _blocked(
    action: DesktopAction,
    reason: str,
    missing: tuple[str, ...] = (),
) -> DesktopActionPlan:
    return DesktopActionPlan(
        action=action,
        blocked=True,
        reason=reason,
        missing_capabilities=missing,
        risks=_risks_for(action, "blocked"),
    )


def _connector_supports(
    connector: object,
    action: DesktopAction,
    target: object,
) -> bool:
    try:
        supports_target = getattr(connector, "supports_target", None)
        if callable(supports_target) and not bool(supports_target(target)):
            return False
        supports_action = getattr(connector, "supports_action", None)
        if callable(supports_action):
            try:
                if not bool(supports_action(action.action, target)):
                    return False
            except TypeError:
                if not bool(supports_action(action.action)):
                    return False
        route_ready = getattr(connector, "route_ready", None)
        if callable(route_ready):
            return bool(
                route_ready(str(getattr(connector, "route_id", "")), target)
            )
        return True
    except (AttributeError, TypeError, ValueError, OSError):
        return False


def _connector_target(action: DesktopAction) -> object:
    from openwukong.connectors.base import ConnectorTarget

    target = action.target
    parameters = dict(action.parameters)
    return ConnectorTarget(
        workspace_id=target.workspace_id,
        session_id=target.session_id,
        pid=target.pid,
        process_name=target.process_name,
        window_title=target.window_title,
        workspace_path=str(parameters.get("workspace_path", "") or ""),
        resource_url=str(parameters.get("resource_url", "") or ""),
        debugger_url=str(parameters.get("debugger_url", "") or ""),
        ide_bridge_url=str(parameters.get("ide_bridge_url", "") or ""),
        agent_native_bridge_url=str(
            parameters.get("agent_native_bridge_url", "") or ""
        ),
        wechat_native_bridge_url=str(
            parameters.get("wechat_native_bridge_url", "") or ""
        ),
        conversation_name=target.conversation_name,
        background_screenshot_focus_stable=bool(
            parameters.get("background_screenshot_focus_stable", True)
        ),
        background_screenshot_count=int(
            parameters.get("background_screenshot_count", 0) or 0
        ),
        background_screenshot_success_count=int(
            parameters.get("background_screenshot_success_count", 0) or 0
        ),
    )


def _risks_for(action: DesktopAction, mode: str) -> tuple[str, ...]:
    risks = []
    if action.requires_confirmation:
        risks.append("side_effect_confirmation")
    if mode == "foreground_desktop":
        risks.append("foreground_input")
    if action.parameters.get("text") or action.parameters.get("message"):
        risks.append("content_payload")
    return tuple(risks)


__all__ = ["DesktopActionPlan", "plan_desktop_action"]
