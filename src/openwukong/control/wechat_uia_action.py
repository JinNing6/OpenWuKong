# -*- coding: utf-8 -*-
"""Dry-run contract for WeChat UIA semantic chat actions.

This module validates whether a WeChat conversation surface exposes enough
semantic UI Automation evidence for a future background action. It does not
call SetValue, Invoke, keyboard, mouse, or clipboard APIs.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Iterable

from openwukong.evaluation.accessibility_probe import AccessibilityWindowSnapshot


WECHAT_UIA_ACTION_SCHEMA_VERSION = "wechat-uia-semantic-action-v1"

_COMPOSER_CONTROL_TYPES = {"Edit", "Document", "ComboBox"}
_SUBMIT_CONTROL_TYPES = {"Button", "Hyperlink", "MenuItem", "SplitButton"}
_VALUE_PATTERNS = {"Value", "TextEdit"}
_INVOKE_PATTERNS = {"Invoke"}


@dataclasses.dataclass(frozen=True)
class WeChatUiaSemanticActionRequest:
    target_name: str
    message: str
    windows: tuple[AccessibilityWindowSnapshot, ...]
    background_screenshot_focus_stable: bool = True
    selected_transport: dict = dataclasses.field(default_factory=dict)
    request_id: str = dataclasses.field(default_factory=lambda: f"wcuia-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "wechat-uia-semantic-action-request"

    @property
    def schema_version(self) -> str:
        return WECHAT_UIA_ACTION_SCHEMA_VERSION

    @property
    def target_window(self) -> AccessibilityWindowSnapshot | None:
        target = _normalize(self.target_name)
        if not target:
            return None
        for window in self.windows:
            if _window_mentions_target(window, target):
                return window
        return None

    @property
    def target_ready(self) -> bool:
        return self.target_window is not None

    @property
    def candidate_windows(self) -> tuple[AccessibilityWindowSnapshot, ...]:
        target = self.target_window
        if target is not None:
            return (target,)
        return self.windows

    @property
    def composer(self) -> dict:
        for window in self.candidate_windows:
            for element in window.elements:
                patterns = set(str(item) for item in element.patterns)
                if (
                    element.control_type in _COMPOSER_CONTROL_TYPES
                    and element.is_enabled
                    and _is_visible_rect(element.rect)
                    and bool(patterns & _VALUE_PATTERNS)
                ):
                    return _element_to_candidate(window, element, semantic_composer=True)
        return {}

    @property
    def submit_control(self) -> dict:
        for window in self.candidate_windows:
            for element in window.elements:
                patterns = set(str(item) for item in element.patterns)
                if (
                    element.control_type in _SUBMIT_CONTROL_TYPES
                    and element.is_enabled
                    and _is_visible_rect(element.rect)
                    and bool(patterns & _INVOKE_PATTERNS)
                ):
                    return _element_to_candidate(window, element, semantic_submit=True)
        return {}

    @property
    def uia_value_pattern_ready(self) -> bool:
        return bool(self.composer)

    @property
    def uia_invoke_pattern_ready(self) -> bool:
        return bool(self.submit_control)

    @property
    def ready(self) -> bool:
        return bool(
            self.message
            and self.target_ready
            and self.uia_value_pattern_ready
            and self.uia_invoke_pattern_ready
            and self.background_screenshot_focus_stable
        )

    @property
    def target(self) -> dict:
        window = self.target_window
        if window is None and self.windows:
            window = self.windows[0]
        return {
            "target_name": self.target_name,
            "target_matched": self.target_ready,
            "process_name": str(getattr(window, "process_name", "") or "") if window else "",
            "pid": int(getattr(window, "pid", 0) or 0) if window else 0,
            "window_title": str(getattr(window, "window_title", "") or "") if window else "",
            "hwnd": int(getattr(window, "hwnd", 0) or 0) if window else 0,
            "window_count": len(self.windows),
            "semantic_composer_count": _semantic_composer_count(self.candidate_windows),
            "submit_candidate_count": _submit_candidate_count(self.candidate_windows),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "ready": self.ready,
            "target_ready": self.target_ready,
            "uia_value_pattern_ready": self.uia_value_pattern_ready,
            "uia_invoke_pattern_ready": self.uia_invoke_pattern_ready,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "target_name": self.target_name,
            "selected_transport": dict(self.selected_transport),
            "target": self.target,
            "composer": dict(self.composer),
            "submit_control": dict(self.submit_control),
            "payload": {
                "schema_version": self.schema_version,
                "request_id": self.request_id,
                "action": "wechat.conversation.uia_semantic_send_message",
                "target_name": self.target_name,
                "message": self.message,
            },
        }


@dataclasses.dataclass(frozen=True)
class WeChatUiaSemanticActionDryRunReport:
    request: WeChatUiaSemanticActionRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "wechat-uia-semantic-action-dry-run"

    @property
    def safety_mode(self) -> str:
        return "dry_run"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def send_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def uia_value_set_attempts(self) -> int:
        return 0

    @property
    def uia_invoke_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return not self.validation_errors

    @property
    def decision(self) -> str:
        if not self.request.message:
            return "wechat_uia_semantic_action_message_required"
        if not self.request.target_ready:
            return "wechat_uia_semantic_action_target_not_ready"
        if not self.request.uia_value_pattern_ready:
            return "wechat_uia_semantic_action_value_pattern_not_ready"
        if not self.request.uia_invoke_pattern_ready:
            return "wechat_uia_semantic_action_invoke_pattern_not_ready"
        if not self.request.background_screenshot_focus_stable:
            return "wechat_uia_semantic_action_visual_focus_not_stable"
        if self.validation_errors:
            return "wechat_uia_semantic_action_request_invalid"
        return "wechat_uia_semantic_action_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "send_attempts": self.send_attempts,
            "window_input_attempts": self.window_input_attempts,
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


class WeChatUiaSemanticActionDryRunAdapter:
    def prepare(
        self,
        request: WeChatUiaSemanticActionRequest,
    ) -> WeChatUiaSemanticActionDryRunReport:
        return WeChatUiaSemanticActionDryRunReport(
            request=request,
            validation_errors=_validate_request(request),
        )


def build_wechat_uia_semantic_action_request(
    *,
    target_name: str,
    message: str,
    windows: Iterable[AccessibilityWindowSnapshot],
    background_screenshot_focus_stable: bool = True,
    selected_transport: dict | object | None = None,
) -> WeChatUiaSemanticActionRequest:
    return WeChatUiaSemanticActionRequest(
        target_name=str(target_name or "").strip(),
        message=str(message or "").strip(),
        windows=tuple(windows),
        background_screenshot_focus_stable=bool(background_screenshot_focus_stable),
        selected_transport=_dict_from_report(selected_transport),
    )


def _validate_request(request: WeChatUiaSemanticActionRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.target_name:
        errors.append("target_name_required")
    if not request.message:
        errors.append("message_required")
    if not request.target_ready:
        errors.append("target_not_ready")
    if not request.uia_value_pattern_ready:
        errors.append("uia_value_pattern_not_ready")
    if not request.uia_invoke_pattern_ready:
        errors.append("uia_invoke_pattern_not_ready")
    if not request.background_screenshot_focus_stable:
        errors.append("background_screenshot_focus_not_stable")
    return tuple(errors)


def _window_mentions_target(window: AccessibilityWindowSnapshot, normalized_target: str) -> bool:
    if normalized_target in _normalize(window.window_title):
        return True
    for element in window.elements:
        haystack = " ".join(
            (
                element.name,
                element.automation_id,
                element.value_preview,
            )
        )
        if normalized_target in _normalize(haystack):
            return True
    return False


def _semantic_composer_count(windows: Iterable[AccessibilityWindowSnapshot]) -> int:
    count = 0
    for window in windows:
        for element in window.elements:
            if (
                element.control_type in _COMPOSER_CONTROL_TYPES
                and element.is_enabled
                and _is_visible_rect(element.rect)
                and bool(set(element.patterns) & _VALUE_PATTERNS)
            ):
                count += 1
    return count


def _submit_candidate_count(windows: Iterable[AccessibilityWindowSnapshot]) -> int:
    count = 0
    for window in windows:
        for element in window.elements:
            if (
                element.control_type in _SUBMIT_CONTROL_TYPES
                and element.is_enabled
                and _is_visible_rect(element.rect)
                and bool(set(element.patterns) & _INVOKE_PATTERNS)
            ):
                count += 1
    return count


def _element_to_candidate(
    window: AccessibilityWindowSnapshot,
    element,
    *,
    semantic_composer: bool = False,
    semantic_submit: bool = False,
) -> dict:
    data = element.to_dict()
    data.update(
        {
            "visible": _is_visible_rect(element.rect),
            "semantic_composer": bool(semantic_composer),
            "semantic_submit": bool(semantic_submit),
            "window": {
                "process_name": window.process_name,
                "pid": window.pid,
                "window_title": window.window_title,
                "hwnd": window.hwnd,
            },
        }
    )
    return data


def _is_visible_rect(rect: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = tuple(rect or (0, 0, 0, 0))
    return int(right) > int(left) and int(bottom) > int(top)


def _normalize(value: str) -> str:
    return str(value or "").strip().casefold()


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


__all__ = [
    "WECHAT_UIA_ACTION_SCHEMA_VERSION",
    "WeChatUiaSemanticActionDryRunAdapter",
    "WeChatUiaSemanticActionDryRunReport",
    "WeChatUiaSemanticActionRequest",
    "build_wechat_uia_semantic_action_request",
]
