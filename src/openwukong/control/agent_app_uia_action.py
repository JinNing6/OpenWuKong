# -*- coding: utf-8 -*-
"""Contract and opt-in sender for UIA semantic app-side agent actions.

The default path is dry-run only. The sender is an explicit execution primitive
that uses UI Automation Value/Invoke patterns through a native provider. It does
not use keyboard, mouse, or clipboard APIs.
"""

from __future__ import annotations

import dataclasses
import time
import uuid


UIA_ACTION_SCHEMA_VERSION = "agent-app-uia-semantic-action-v1"


@dataclasses.dataclass(frozen=True)
class AgentAppUiaSemanticActionRequest:
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    message: str
    selected_transport: dict
    app_surface_probe: dict
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    request_id: str = dataclasses.field(default_factory=lambda: f"uiasa-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "agent-app-uia-semantic-action-request"

    @property
    def schema_version(self) -> str:
        return UIA_ACTION_SCHEMA_VERSION

    @property
    def app_uia_probe(self) -> dict:
        value = self.app_surface_probe.get("app_uia_probe")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def visual_focus_stable(self) -> bool:
        if "background_screenshot_focus_stable" not in self.app_uia_probe:
            return True
        return bool(self.app_uia_probe.get("background_screenshot_focus_stable", False))

    @property
    def target_ready(self) -> bool:
        return bool(self.app_uia_probe.get("target_matched", False))

    @property
    def composer(self) -> dict:
        for candidate in _list_dicts(self.app_uia_probe.get("composer_candidates")):
            patterns = set(str(item) for item in candidate.get("patterns", []) or [])
            if (
                bool(candidate.get("semantic_composer", False))
                and bool(candidate.get("visible", False))
                and bool(candidate.get("is_enabled", False))
                and "Value" in patterns
            ):
                return candidate
        return {}

    @property
    def submit_control(self) -> dict:
        for candidate in _list_dicts(self.app_uia_probe.get("submit_candidates")):
            patterns = set(str(item) for item in candidate.get("patterns", []) or [])
            if (
                bool(candidate.get("visible", False))
                and bool(candidate.get("is_enabled", False))
                and "Invoke" in patterns
            ):
                return candidate
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
            and self.visual_focus_stable
        )

    @property
    def target(self) -> dict:
        window = {}
        windows = _list_dicts(self.app_uia_probe.get("matched_windows"))
        if windows:
            window = windows[0]
        return {
            "process_name": str(window.get("process_name", "") or ""),
            "pid": int(window.get("pid", 0) or 0),
            "window_title": str(window.get("window_title", "") or ""),
            "hwnd": int(window.get("hwnd", 0) or 0),
            "project_name": self.project_name,
            "task_name": self.task_name,
            "target_matched": self.target_ready,
            "semantic_composer_count": int(self.app_uia_probe.get("semantic_composer_count", 0) or 0),
            "submit_candidate_count": int(self.app_uia_probe.get("submit_candidate_count", 0) or 0),
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
            "visual_focus_stable": self.visual_focus_stable,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "target": self.target,
            "composer": dict(self.composer),
            "submit_control": dict(self.submit_control),
            "payload": {
                "schema_version": self.schema_version,
                "request_id": self.request_id,
                "action": "agent_app_conversation.uia_semantic_send_message",
                "agent": self.agent,
                "agent_id": self.agent_id,
                "project_name": self.project_name,
                "task_name": self.task_name,
                "message": self.message,
                "required_markers": list(self.required_markers),
                "forbidden_markers": list(self.forbidden_markers),
            },
            "diagnostics": {
                "app_surface_decision": str(self.app_surface_probe.get("decision", "") or ""),
                "app_uia_decision": str(self.app_uia_probe.get("decision", "") or ""),
                "background_screenshot_count": int(self.app_uia_probe.get("background_screenshot_count", 0) or 0),
                "background_screenshot_focus_stable": self.visual_focus_stable,
            },
        }


@dataclasses.dataclass(frozen=True)
class AgentAppUiaSemanticActionDryRunReport:
    request: AgentAppUiaSemanticActionRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "agent-app-uia-semantic-action-dry-run"

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
            return "uia_semantic_action_message_required"
        if not self.request.target_ready:
            return "uia_semantic_action_target_not_ready"
        if not self.request.uia_value_pattern_ready:
            return "uia_semantic_action_value_pattern_not_ready"
        if not self.request.uia_invoke_pattern_ready:
            return "uia_semantic_action_invoke_pattern_not_ready"
        if not self.request.visual_focus_stable:
            return "uia_semantic_action_visual_focus_not_stable"
        if self.validation_errors:
            return "uia_semantic_action_request_invalid"
        return "uia_semantic_action_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


class AgentAppUiaSemanticActionDryRunAdapter:
    def prepare(
        self,
        request: AgentAppUiaSemanticActionRequest,
    ) -> AgentAppUiaSemanticActionDryRunReport:
        return AgentAppUiaSemanticActionDryRunReport(
            request=request,
            validation_errors=_validate_request(request),
        )


@dataclasses.dataclass(frozen=True)
class AgentAppUiaSemanticActionSendReport:
    request: AgentAppUiaSemanticActionRequest
    dry_run_report: AgentAppUiaSemanticActionDryRunReport
    operation_result: dict = dataclasses.field(default_factory=dict)
    uia_value_set_attempts: int = 0
    uia_invoke_attempts: int = 0
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-uia-semantic-action-send"

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
    def missing_required_markers(self) -> tuple[str, ...]:
        text = self.readback_text
        return tuple(marker for marker in self.request.required_markers if marker not in text)

    @property
    def present_forbidden_markers(self) -> tuple[str, ...]:
        text = self.readback_text
        return tuple(marker for marker in self.request.forbidden_markers if marker in text)

    @property
    def ok(self) -> bool:
        return self.decision == "uia_semantic_action_send_accepted"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "uia_semantic_action_request_not_ready"
        if self.error:
            return "uia_semantic_action_send_failed"
        if not self.operation_result.get("composer_found"):
            return "uia_semantic_action_composer_not_found"
        if not self.uia_value_set_attempts:
            return "uia_semantic_action_value_not_attempted"
        if not self.operation_result.get("value_set"):
            return "uia_semantic_action_value_not_verified"
        if not self.operation_result.get("submit_found"):
            return "uia_semantic_action_submit_not_found"
        if not self.uia_invoke_attempts:
            return "uia_semantic_action_invoke_not_attempted"
        if not self.operation_result.get("invoke_attempted"):
            return "uia_semantic_action_invoke_not_verified"
        if not self.operation_result.get("invoke_verified"):
            return "uia_semantic_action_submit_not_verified"
        if not self.foreground_focus_stable:
            return "uia_semantic_action_foreground_changed"
        if self.present_forbidden_markers:
            return "uia_semantic_action_forbidden_marker_present"
        if self.missing_required_markers:
            return "uia_semantic_action_acceptance_pending"
        return "uia_semantic_action_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
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


class AgentAppUiaSemanticActionSenderAdapter:
    def __init__(self, *, operator: object | None = None, foreground_hwnd_provider: object | None = None):
        self._operator = operator or PywinautoUiaSemanticActionOperator()
        self._foreground_hwnd_provider = foreground_hwnd_provider or _foreground_hwnd

    def send(self, request: AgentAppUiaSemanticActionRequest) -> AgentAppUiaSemanticActionSendReport:
        started = time.perf_counter()
        dry_run = AgentAppUiaSemanticActionDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppUiaSemanticActionSendReport(
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
        return AgentAppUiaSemanticActionSendReport(
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


class PywinautoUiaSemanticActionOperator:
    """Executes UIA ValuePattern/InvokePattern against the located controls."""

    def execute(self, request: AgentAppUiaSemanticActionRequest) -> dict:
        try:
            from pywinauto import Desktop
        except Exception as exc:
            return {"error": f"dependency_error:{exc}"}

        window = _find_window_wrapper(Desktop(backend="uia"), request.target)
        if window is None:
            return {"window_found": False, "composer_found": False, "submit_found": False}
        composer = _find_descendant_wrapper(window, request.composer)
        submit = _find_descendant_wrapper(window, request.submit_control)
        result = {
            "window_found": True,
            "composer_found": composer is not None,
            "submit_found": submit is not None,
            "value_set_attempted": False,
            "value_set": False,
            "invoke_attempted": False,
            "invoke_verified": False,
            "post_value": "",
            "readbackText": "",
        }
        if composer is not None:
            result["value_set_attempted"] = True
            _set_uia_value(composer, request.message)
            result["post_value"] = _wrapper_value(composer)
            result["value_set"] = request.message in str(result["post_value"] or "")
        if submit is not None:
            result["invoke_attempted"] = True
            _invoke_uia_control(submit)
            result["invoke_verified"] = True
        result["readbackText"] = _window_text_snapshot(window)
        return result


def build_agent_app_uia_semantic_action_request(
    *,
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    message: str,
    selected_transport: dict | object,
    app_surface_probe: dict | object,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentAppUiaSemanticActionRequest:
    return AgentAppUiaSemanticActionRequest(
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        selected_transport=_dict_from_report(selected_transport),
        app_surface_probe=_dict_from_report(app_surface_probe),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
    )


def _validate_request(request: AgentAppUiaSemanticActionRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.agent_id:
        errors.append("agent_id_required")
    if not request.message:
        errors.append("message_required")
    if not request.target_ready:
        errors.append("target_not_ready")
    if not request.uia_value_pattern_ready:
        errors.append("uia_value_pattern_not_ready")
    if not request.uia_invoke_pattern_ready:
        errors.append("uia_invoke_pattern_not_ready")
    if not request.visual_focus_stable:
        errors.append("visual_focus_not_stable")
    return tuple(errors)


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _list_dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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


def _find_window_wrapper(desktop, target: dict):
    target_hwnd = int(target.get("hwnd", 0) or 0)
    target_pid = int(target.get("pid", 0) or 0)
    title = str(target.get("window_title", "") or "")
    try:
        windows = desktop.windows()
    except Exception:
        return None
    for window in windows:
        if target_hwnd and _safe_handle(window) == target_hwnd:
            return window
    for window in windows:
        if target_pid and _safe_process_id(window) == target_pid and (
            not title or title in _safe_window_text(window)
        ):
            return window
    return None


def _find_descendant_wrapper(window, candidate: dict):
    if not candidate:
        return None
    try:
        descendants = window.descendants()
    except Exception:
        descendants = []
    for wrapper in descendants:
        if _wrapper_matches_candidate(wrapper, candidate):
            return wrapper
    return None


def _wrapper_matches_candidate(wrapper, candidate: dict) -> bool:
    control_type = str(candidate.get("control_type", "") or "")
    if control_type and _safe_control_type(wrapper) != control_type:
        return False
    name = str(candidate.get("name", "") or "")
    if name and _safe_element_attr(wrapper, "name") != name:
        return False
    automation_id = str(candidate.get("automation_id", "") or "")
    if automation_id and _safe_element_attr(wrapper, "automation_id") != automation_id:
        return False
    class_name = str(candidate.get("class_name", "") or "")
    if class_name and _safe_element_attr(wrapper, "class_name") != class_name:
        return False
    rect = candidate.get("rect", ())
    if rect and _rect_tuple(rect) != _safe_rect(wrapper):
        return False
    return True


def _set_uia_value(wrapper, value: str) -> None:
    iface_value = getattr(wrapper, "iface_value", None)
    if iface_value is None:
        raise RuntimeError("uia_value_pattern_not_available")
    iface_value.SetValue(str(value or ""))


def _invoke_uia_control(wrapper) -> None:
    iface_invoke = getattr(wrapper, "iface_invoke", None)
    if iface_invoke is None:
        raise RuntimeError("uia_invoke_pattern_not_available")
    iface_invoke.Invoke()


def _wrapper_value(wrapper) -> str:
    for method_name in ("get_value", "window_text"):
        try:
            method = getattr(wrapper, method_name)
            value = method()
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _window_text_snapshot(window) -> str:
    texts: list[str] = []
    try:
        text = window.window_text()
        if text:
            texts.append(str(text))
    except Exception:
        pass
    try:
        descendants = window.descendants()
    except Exception:
        descendants = []
    for wrapper in descendants[:300]:
        value = _wrapper_value(wrapper)
        if value:
            texts.append(value)
    return "\n".join(dict.fromkeys(texts))[:6000]


def _safe_handle(wrapper) -> int:
    for attr in ("handle", "hwnd"):
        try:
            value = getattr(wrapper, attr)
            if callable(value):
                value = value()
            return int(value or 0)
        except Exception:
            continue
    return 0


def _safe_process_id(wrapper) -> int:
    try:
        return int(wrapper.process_id() or 0)
    except Exception:
        return 0


def _safe_window_text(wrapper) -> str:
    try:
        return str(wrapper.window_text() or "")
    except Exception:
        return ""


def _safe_control_type(wrapper) -> str:
    try:
        return str(wrapper.element_info.control_type or "")
    except Exception:
        return ""


def _safe_element_attr(wrapper, attr: str) -> str:
    try:
        return str(getattr(wrapper.element_info, attr) or "")
    except Exception:
        return ""


def _safe_rect(wrapper) -> tuple[int, int, int, int]:
    try:
        rect = wrapper.rectangle()
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return (0, 0, 0, 0)


def _rect_tuple(value: object) -> tuple[int, int, int, int]:
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError:
        items = []
    padded = (items + [0, 0, 0, 0])[:4]
    return tuple(int(item or 0) for item in padded)  # type: ignore[return-value]


__all__ = [
    "UIA_ACTION_SCHEMA_VERSION",
    "AgentAppUiaSemanticActionDryRunAdapter",
    "AgentAppUiaSemanticActionDryRunReport",
    "AgentAppUiaSemanticActionRequest",
    "AgentAppUiaSemanticActionSenderAdapter",
    "AgentAppUiaSemanticActionSendReport",
    "PywinautoUiaSemanticActionOperator",
    "build_agent_app_uia_semantic_action_request",
]
