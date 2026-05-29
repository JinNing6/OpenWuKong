# -*- coding: utf-8 -*-
"""Dry-run contract for WeChat UIA semantic chat actions.

This module validates whether a WeChat conversation surface exposes enough
semantic UI Automation evidence for a future background action. It does not
call SetValue, Invoke, keyboard, mouse, or clipboard APIs.
"""

from __future__ import annotations

import dataclasses
import time
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
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
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
                "required_markers": list(self.required_markers),
                "forbidden_markers": list(self.forbidden_markers),
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


@dataclasses.dataclass(frozen=True)
class WeChatUiaSemanticActionSendReport:
    request: WeChatUiaSemanticActionRequest
    dry_run_report: WeChatUiaSemanticActionDryRunReport
    operation_result: dict = dataclasses.field(default_factory=dict)
    uia_value_set_attempts: int = 0
    uia_invoke_attempts: int = 0
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-uia-semantic-action-send"

    @property
    def safety_mode(self) -> str:
        return "uia_semantic_execute"

    @property
    def control_allowed(self) -> bool:
        return bool(self.dry_run_report.ok and not self.error)

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def keyboard_input_attempts(self) -> int:
        return 0

    @property
    def clipboard_write_attempts(self) -> int:
        return 0

    @property
    def send_attempts(self) -> int:
        return 1 if self.uia_invoke_attempts else 0

    @property
    def foreground_focus_stable(self) -> bool:
        if not self.foreground_hwnd_before or not self.foreground_hwnd_after:
            return True
        return int(self.foreground_hwnd_before) == int(self.foreground_hwnd_after)

    @property
    def readback_text(self) -> str:
        return _first_text(
            self.operation_result,
            "readbackText",
            "readback_text",
            "pageText",
            "page_text",
            "text",
            "post_value",
        )

    @property
    def required_markers(self) -> tuple[str, ...]:
        if self.request.required_markers:
            return self.request.required_markers
        return (self.request.message,) if self.request.message else ()

    @property
    def missing_required_markers(self) -> tuple[str, ...]:
        text = self.readback_text
        return tuple(marker for marker in self.required_markers if marker not in text)

    @property
    def present_forbidden_markers(self) -> tuple[str, ...]:
        text = self.readback_text
        return tuple(marker for marker in self.request.forbidden_markers if marker in text)

    @property
    def ok(self) -> bool:
        return self.decision == "wechat_uia_semantic_action_send_accepted"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "wechat_uia_semantic_action_request_not_ready"
        if self.error:
            return "wechat_uia_semantic_action_send_failed"
        if not self.operation_result.get("composer_found"):
            return "wechat_uia_semantic_action_composer_not_found"
        if not self.uia_value_set_attempts:
            return "wechat_uia_semantic_action_value_not_attempted"
        if not self.operation_result.get("value_set"):
            return "wechat_uia_semantic_action_value_not_verified"
        if not self.operation_result.get("submit_found"):
            return "wechat_uia_semantic_action_submit_not_found"
        if not self.uia_invoke_attempts:
            return "wechat_uia_semantic_action_invoke_not_attempted"
        if not self.operation_result.get("invoke_attempted"):
            return "wechat_uia_semantic_action_invoke_not_verified"
        if not self.operation_result.get("invoke_verified"):
            return "wechat_uia_semantic_action_submit_not_verified"
        if not self.foreground_focus_stable:
            return "wechat_uia_semantic_action_foreground_changed"
        if self.present_forbidden_markers:
            return "wechat_uia_semantic_action_forbidden_marker_present"
        if self.missing_required_markers:
            return "wechat_uia_semantic_action_acceptance_pending"
        return "wechat_uia_semantic_action_send_accepted"

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
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "uia_value_set_attempts": int(self.uia_value_set_attempts or 0),
            "uia_invoke_attempts": int(self.uia_invoke_attempts or 0),
            "foreground_hwnd_before": int(self.foreground_hwnd_before or 0),
            "foreground_hwnd_after": int(self.foreground_hwnd_after or 0),
            "foreground_focus_stable": self.foreground_focus_stable,
            "missing_required_markers": list(self.missing_required_markers),
            "present_forbidden_markers": list(self.present_forbidden_markers),
            "operation_result": dict(self.operation_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class WeChatUiaSemanticActionSenderAdapter:
    def __init__(self, *, operator: object | None = None, foreground_hwnd_provider: object | None = None):
        self._operator = operator or PywinautoWeChatUiaSemanticActionOperator()
        self._foreground_hwnd_provider = foreground_hwnd_provider or _foreground_hwnd

    def send(self, request: WeChatUiaSemanticActionRequest) -> WeChatUiaSemanticActionSendReport:
        started = time.perf_counter()
        dry_run = WeChatUiaSemanticActionDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return WeChatUiaSemanticActionSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        before = _call_int(self._foreground_hwnd_provider)
        try:
            execute = getattr(self._operator, "execute")
            operation_result = execute(request)
            if not isinstance(operation_result, dict):
                operation_result = {}
            error = ""
        except Exception as exc:
            operation_result = {}
            error = str(exc) or exc.__class__.__name__
        after = _call_int(self._foreground_hwnd_provider)
        return WeChatUiaSemanticActionSendReport(
            request=request,
            dry_run_report=dry_run,
            operation_result=dict(operation_result),
            uia_value_set_attempts=1 if operation_result.get("value_set_attempted") or operation_result.get("value_set") else 0,
            uia_invoke_attempts=1 if operation_result.get("invoke_attempted") else 0,
            foreground_hwnd_before=before,
            foreground_hwnd_after=after,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class PywinautoWeChatUiaSemanticActionOperator:
    """Executes WeChat semantic send through UIA Value/Invoke patterns."""

    def execute(self, request: WeChatUiaSemanticActionRequest) -> dict:
        from openwukong.control.agent_app_uia_action import (
            PywinautoUiaSemanticActionOperator,
        )

        return PywinautoUiaSemanticActionOperator().execute(request)  # type: ignore[arg-type]


def build_wechat_uia_semantic_action_request(
    *,
    target_name: str,
    message: str,
    windows: Iterable[AccessibilityWindowSnapshot],
    background_screenshot_focus_stable: bool = True,
    selected_transport: dict | object | None = None,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> WeChatUiaSemanticActionRequest:
    return WeChatUiaSemanticActionRequest(
        target_name=str(target_name or "").strip(),
        message=str(message or "").strip(),
        windows=tuple(windows),
        background_screenshot_focus_stable=bool(background_screenshot_focus_stable),
        selected_transport=_dict_from_report(selected_transport),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
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


def _first_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _string_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    return tuple(str(item).strip() for item in items if str(item or "").strip())


def _call_int(provider: object) -> int:
    try:
        return int(provider() or 0) if callable(provider) else 0
    except Exception:
        return 0


def _foreground_hwnd() -> int:
    try:
        import ctypes

        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


__all__ = [
    "WECHAT_UIA_ACTION_SCHEMA_VERSION",
    "WeChatUiaSemanticActionDryRunAdapter",
    "WeChatUiaSemanticActionDryRunReport",
    "WeChatUiaSemanticActionRequest",
    "WeChatUiaSemanticActionSenderAdapter",
    "WeChatUiaSemanticActionSendReport",
    "PywinautoWeChatUiaSemanticActionOperator",
    "build_wechat_uia_semantic_action_request",
]
