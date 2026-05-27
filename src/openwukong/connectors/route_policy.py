# -*- coding: utf-8 -*-
"""Deterministic control route policy for desktop app families.

This module turns observed window capabilities into a route contract. It does
not execute actions; it only decides which connector family should be primary,
which fallbacks are acceptable, and which capabilities are missing.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Iterable


_BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "browser.exe",
    "opera.exe",
}
_IDE_PROCESSES = {
    "antigravity.exe",
    "code - insiders.exe",
    "code.exe",
    "codex.exe",
    "cursor.exe",
    "windsurf.exe",
}
_TERMINAL_PROCESSES = {
    "bash.exe",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windows terminal.exe",
    "windowsterminal.exe",
    "wsl.exe",
}
_GIT_PROCESSES = {"git.exe"}
_OFFICE_PROCESSES = {
    "excel.exe",
    "msaccess.exe",
    "onenote.exe",
    "outlook.exe",
    "powerpnt.exe",
    "winword.exe",
}
_IM_PROCESSES = {
    "dingding.exe",
    "lark.exe",
    "qq.exe",
    "slack.exe",
    "teams.exe",
    "wechat.exe",
    "weixin.exe",
}
_OVERLAY_PROCESSES = {
    "nvidia overlay.exe",
}
_SYSTEM_SHELL_PROCESSES = {
    "explorer.exe",
    "shellexperiencehost.exe",
    "searchhost.exe",
}
_ELECTRON_CEF_PROCESSES = {
    "clash-verge.exe",
    "docker desktop.exe",
}


@dataclasses.dataclass(frozen=True)
class ControlRouteStep:
    route_id: str
    channel: str
    locator_source: str
    action_primitives: tuple[str, ...] = ()
    confidence_floor: int = 0
    role: str = "fallback"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "channel": self.channel,
            "locator_source": self.locator_source,
            "action_primitives": list(self.action_primitives),
            "confidence_floor": self.confidence_floor,
            "role": self.role,
            "reason": self.reason,
        }


@dataclasses.dataclass(frozen=True)
class ControlRoutePlan:
    process_name: str
    window_title: str
    app_family: str
    capability_level: str
    capability_score: int
    primary_route: ControlRouteStep
    fallback_routes: tuple[ControlRouteStep, ...] = ()
    control_decision: str = "observe_only"
    missing_capabilities: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()

    @property
    def is_blocked(self) -> bool:
        return self.control_decision.startswith("block_")

    def to_dict(self) -> dict:
        return {
            "process_name": self.process_name,
            "window_title": self.window_title,
            "app_family": self.app_family,
            "capability_level": self.capability_level,
            "capability_score": self.capability_score,
            "primary_route": self.primary_route.to_dict(),
            "fallback_routes": [route.to_dict() for route in self.fallback_routes],
            "control_decision": self.control_decision,
            "missing_capabilities": list(self.missing_capabilities),
            "risks": list(self.risks),
            "is_blocked": self.is_blocked,
        }


@dataclasses.dataclass(frozen=True)
class ControlRouteMatrix:
    plans: tuple[ControlRoutePlan, ...]

    @property
    def control_attempts(self) -> int:
        return 0

    def app_family_counts(self) -> dict:
        return dict(sorted(Counter(plan.app_family for plan in self.plans).items()))

    def primary_route_counts(self) -> dict:
        return dict(sorted(Counter(plan.primary_route.route_id for plan in self.plans).items()))

    def decision_counts(self) -> dict:
        return dict(sorted(Counter(plan.control_decision for plan in self.plans).items()))

    def blocked_windows(self) -> tuple[str, ...]:
        return tuple(
            plan.window_title
            for plan in self.plans
            if plan.is_blocked
        )

    def to_dict(self) -> dict:
        return {
            "mode": "control-route-matrix",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": self.control_attempts,
            "window_count": len(self.plans),
            "app_family_counts": self.app_family_counts(),
            "primary_route_counts": self.primary_route_counts(),
            "decision_counts": self.decision_counts(),
            "blocked_windows": list(self.blocked_windows()),
            "plans": [plan.to_dict() for plan in self.plans],
        }


def build_control_route_matrix(report_or_windows) -> ControlRouteMatrix:
    windows = getattr(report_or_windows, "windows", report_or_windows)
    return ControlRouteMatrix(
        plans=tuple(build_control_route_plan(window) for window in windows)
    )


def build_control_route_plan(window) -> ControlRoutePlan:
    process_name = _text(getattr(window, "process_name", ""))
    window_title = _text(getattr(window, "window_title", ""))
    family = classify_app_family(window)
    level = _call_or_value(window, "capability_level", default="window_only")
    score = int(_call_or_value(window, "capability_score", default=0) or 0)
    risks = tuple(_call_or_value(window, "risks", default=()) or ())
    missing = _missing_capabilities(window, family)

    if family == "browser":
        primary = _step(
            "browser-devtools-or-extension",
            "connector",
            "browser-dom-or-accessibility-tree",
            ("devtools_command", "extension_command", "dom_locator", "accessibility_tree_locator"),
            95,
            "primary",
            "Browsers expose deterministic DOM, DevTools, and extension surfaces.",
        )
        decision = "prefer_deterministic_connector"
        fallbacks = _uia_fallbacks(window, family)
    elif family == "ide":
        primary = _step(
            "ide-extension-connector",
            "connector",
            "ide-extension-api-or-native-rpc",
            ("extension_command", "workspace_rpc", "editor_selection", "chat_message"),
            90,
            "primary",
            "IDE state should come from an extension or native session bridge before UIA.",
        )
        decision = "prefer_deterministic_connector"
        fallbacks = _uia_fallbacks(window, family)
    elif family == "terminal":
        primary = _step(
            "terminal-native-session",
            "connector",
            "conpty-or-managed-shell-session",
            ("run_command", "read_stdout", "send_stdin"),
            98,
            "primary",
            "Terminal buffers require a native session channel; UIA only sees shell chrome reliably.",
        )
        decision = "prefer_deterministic_connector"
        fallbacks = _uia_fallbacks(window, family)
    elif family == "git":
        primary = _step(
            "git-cli",
            "connector",
            "workspace-bound-git-process",
            ("git_command", "read_exit_code", "read_stdout"),
            98,
            "primary",
            "Git should be controlled through CLI plumbing inside the workspace.",
        )
        decision = "prefer_deterministic_connector"
        fallbacks = (_vision_fallback(),)
    elif family == "office":
        primary = _step(
            "office-object-model-or-addin",
            "connector",
            "office-com-or-office-js-object-model",
            ("com_automation", "office_js_command", "document_object_locator"),
            92,
            "primary",
            "Office apps have object models that are more stable than screen controls.",
        )
        decision = "prefer_deterministic_connector"
        fallbacks = _uia_fallbacks(window, family)
    elif family in {"im", "electron-cef"} and not _has_semantic_control(window):
        primary = _step(
            "app-native-bridge-required",
            "missing_connector",
            "app-specific-protocol-extension-or-native-bridge",
            ("app_rpc", "extension_command", "native_bridge_call"),
            90,
            "primary",
            "The accessible surface is too weak for precise control.",
        )
        decision = "block_until_deterministic_route"
        fallbacks = _uia_fallbacks(window, family)
    elif family == "overlay" or _element_count(window) == 0:
        primary = _step(
            "no-deterministic-route",
            "blocked",
            "none",
            (),
            100,
            "primary",
            "The window does not expose enough structure for safe semantic operation.",
        )
        decision = "block_until_deterministic_route"
        fallbacks = (_vision_fallback(),)
    elif _has_semantic_control(window):
        primary = _step(
            "uia-semantic",
            "accessibility",
            "uia-control-patterns",
            ("value_pattern", "invoke_pattern", "selection_pattern", "toggle_pattern"),
            80,
            "primary",
            "The window exposes semantic UI Automation control patterns.",
        )
        decision = "allow_semantic_uia_fallback"
        fallbacks = (_msaa_fallback(), _vision_fallback())
    elif _text_readable_count(window) or _input_candidate_count(window):
        primary = _step(
            "uia-structural-observe",
            "accessibility",
            "uia-control-tree",
            ("read_text", "locate_control"),
            70,
            "primary",
            "The window is inspectable but does not expose a writable semantic input route.",
        )
        decision = "observe_until_writable_locator"
        fallbacks = (_msaa_fallback(), _vision_fallback())
    else:
        primary = _step(
            "app-native-bridge-required",
            "missing_connector",
            "app-specific-protocol-extension-or-native-bridge",
            ("app_rpc", "native_bridge_call"),
            90,
            "primary",
            "No stable semantic route is currently available.",
        )
        decision = "block_until_deterministic_route"
        fallbacks = _uia_fallbacks(window, family)

    return ControlRoutePlan(
        process_name=process_name,
        window_title=window_title,
        app_family=family,
        capability_level=str(level),
        capability_score=score,
        primary_route=primary,
        fallback_routes=fallbacks,
        control_decision=decision,
        missing_capabilities=missing,
        risks=risks,
    )


def classify_app_family(window) -> str:
    process_name = _text(getattr(window, "process_name", "")).lower()
    class_name = _text(getattr(window, "class_name", "")).lower()
    title = _text(getattr(window, "window_title", "")).lower()

    if process_name in _BROWSER_PROCESSES:
        return "browser"
    if process_name in _IDE_PROCESSES:
        return "ide"
    if process_name in _TERMINAL_PROCESSES or "terminal" in title:
        return "terminal"
    if process_name in _GIT_PROCESSES:
        return "git"
    if process_name in _OFFICE_PROCESSES:
        return "office"
    if process_name in _IM_PROCESSES:
        return "im"
    if process_name in _OVERLAY_PROCESSES or "overlay" in title:
        return "overlay"
    if process_name in _SYSTEM_SHELL_PROCESSES:
        return "system-shell"
    if (
        process_name in _ELECTRON_CEF_PROCESSES
        or "chrome_widgetwin" in class_name
        or "cef-" in class_name
        or "tauri" in class_name
    ):
        return "electron-cef"
    return "generic-desktop"


def _uia_fallbacks(window, family: str) -> tuple[ControlRouteStep, ...]:
    if family == "terminal":
        return (
            _step(
                "uia-observe-chrome-only",
                "accessibility",
                "uia-window-chrome",
                ("read_window_title", "observe_tab_buttons"),
                50,
                "fallback",
                "UIA can observe terminal shell chrome but not reliable terminal buffer input.",
            ),
            _vision_fallback(),
        )

    routes: list[ControlRouteStep] = []
    if _has_semantic_control(window):
        routes.append(
            _step(
                "uia-semantic",
                "accessibility",
                "uia-control-patterns",
                ("value_pattern", "invoke_pattern", "selection_pattern", "toggle_pattern"),
                80,
                "fallback",
                "Fallback when the deterministic connector is unavailable.",
            )
        )
    elif _element_count(window):
        routes.append(
            _step(
                "uia-structural",
                "accessibility",
                "uia-control-tree",
                ("read_text", "locate_control"),
                65,
                "fallback",
                "Structural observation only; avoid write actions until a semantic locator exists.",
            )
        )
    routes.append(_msaa_fallback())
    routes.append(_vision_fallback())
    return tuple(routes)


def _missing_capabilities(window, family: str) -> tuple[str, ...]:
    missing: list[str] = []
    if _element_count(window) == 0:
        missing.append("no_accessible_elements")
    if _semantic_input_count(window) == 0 and family not in {"terminal", "git"}:
        missing.append("no_semantic_input")
    if _action_candidate_count(window) and _semantic_action_count(window) == 0:
        missing.append("no_semantic_action")
    if _input_candidate_count(window) == 0 and family not in {"terminal", "git"}:
        missing.append("no_input_candidate")
    if _stable_identifier_count(window) < max(1, _element_count(window) // 3) and _element_count(window):
        missing.append("weak_stable_identifiers")
    if family == "terminal":
        missing.append("terminal_buffer_not_uia_writable")
    return tuple(dict.fromkeys(missing))


def _has_semantic_control(window) -> bool:
    return _semantic_input_count(window) > 0 or _semantic_action_count(window) > 0


def _element_count(window) -> int:
    return int(getattr(window, "element_count", 0) or 0)


def _input_candidate_count(window) -> int:
    return int(getattr(window, "input_candidate_count", 0) or 0)


def _semantic_input_count(window) -> int:
    return int(getattr(window, "semantic_input_count", 0) or 0)


def _semantic_action_count(window) -> int:
    return int(getattr(window, "semantic_action_count", 0) or 0)


def _action_candidate_count(window) -> int:
    elements = tuple(getattr(window, "elements", ()) or ())
    return sum(1 for element in elements if getattr(element, "is_action_candidate", False))


def _text_readable_count(window) -> int:
    return int(getattr(window, "text_readable_count", 0) or 0)


def _stable_identifier_count(window) -> int:
    return int(getattr(window, "stable_identifier_count", 0) or 0)


def _step(
    route_id: str,
    channel: str,
    locator_source: str,
    action_primitives: tuple[str, ...],
    confidence_floor: int,
    role: str,
    reason: str,
) -> ControlRouteStep:
    return ControlRouteStep(
        route_id=route_id,
        channel=channel,
        locator_source=locator_source,
        action_primitives=action_primitives,
        confidence_floor=confidence_floor,
        role=role,
        reason=reason,
    )


def _msaa_fallback() -> ControlRouteStep:
    return _step(
        "msaa-win32-fallback",
        "accessibility",
        "msaa-iaccessible-or-win32-window-handles",
        ("read_acc_name", "read_window_text", "win_event_observe"),
        60,
        "fallback",
        "Legacy accessibility and Win32 handles can improve observation when UIA is weak.",
    )


def _vision_fallback() -> ControlRouteStep:
    return _step(
        "vision-fallback-last",
        "vision",
        "screenshot-and-ocr",
        ("visual_verify", "visual_locate"),
        95,
        "fallback",
        "Use vision as verification or last-resort locator, not as the primary control channel.",
    )


def _call_or_value(obj, name: str, *, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def _text(value) -> str:
    return str(value or "").strip()
