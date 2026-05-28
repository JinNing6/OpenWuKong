# -*- coding: utf-8 -*-
"""Dry-run contract for app-side agent message bridges."""

from __future__ import annotations

import dataclasses
import time
import uuid

from openwukong.connectors.browser import BrowserDevToolsClient, BrowserDevToolsTarget


BRIDGE_SCHEMA_VERSION = "agent-app-bridge-v1"


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeRequest:
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    message: str
    composed_message: str
    selected_transport: dict
    app_surface_probe: dict
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    request_id: str = dataclasses.field(default_factory=lambda: f"aab-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "agent-app-bridge-request"

    @property
    def schema_version(self) -> str:
        return BRIDGE_SCHEMA_VERSION

    @property
    def app_uia_probe(self) -> dict:
        value = self.app_surface_probe.get("app_uia_probe")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def target_ready(self) -> bool:
        return bool(
            self.app_uia_probe.get("target_matched", False)
            and int(self.app_uia_probe.get("semantic_composer_count", 0) or 0) > 0
        )

    @property
    def native_endpoint_ready(self) -> bool:
        if int(self.app_surface_probe.get("ready_endpoint_count", 0) or 0) <= 0:
            return False
        return bool(self.endpoint)

    @property
    def visual_focus_stable(self) -> bool:
        if "background_screenshot_focus_stable" not in self.app_uia_probe:
            return True
        return bool(self.app_uia_probe.get("background_screenshot_focus_stable", False))

    @property
    def ready(self) -> bool:
        return bool(self.message and self.target_ready and self.native_endpoint_ready and self.visual_focus_stable)

    @property
    def target(self) -> dict:
        windows = self.app_uia_probe.get("matched_windows")
        window = {}
        if isinstance(windows, list) and windows and isinstance(windows[0], dict):
            window = dict(windows[0])
        return {
            "process_name": str(window.get("process_name", "") or ""),
            "pid": int(window.get("pid", 0) or 0),
            "window_title": str(window.get("window_title", "") or ""),
            "hwnd": int(window.get("hwnd", 0) or 0),
            "project_name": self.project_name,
            "task_name": self.task_name,
            "target_matched": self.target_ready,
            "semantic_composer_count": int(self.app_uia_probe.get("semantic_composer_count", 0) or 0),
        }

    @property
    def endpoint(self) -> dict:
        endpoints = self.app_surface_probe.get("endpoints")
        if not isinstance(endpoints, list):
            return {}
        for endpoint in endpoints:
            if isinstance(endpoint, dict) and bool(endpoint.get("ready", False)):
                return dict(endpoint)
        return {}

    @property
    def payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "action": "agent_app_conversation.send_message",
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "message": self.message,
            "composed_message": self.composed_message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "ready": self.ready,
            "target_ready": self.target_ready,
            "native_endpoint_ready": self.native_endpoint_ready,
            "visual_focus_stable": self.visual_focus_stable,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "target": self.target,
            "endpoint": _endpoint_summary(self.endpoint),
            "payload": self.payload,
            "diagnostics": {
                "app_surface_decision": str(self.app_surface_probe.get("decision", "") or ""),
                "app_uia_decision": str(self.app_uia_probe.get("decision", "") or ""),
                "endpoint_count": int(self.app_surface_probe.get("endpoint_count", 0) or 0),
                "ready_endpoint_count": int(self.app_surface_probe.get("ready_endpoint_count", 0) or 0),
                "background_screenshot_count": int(self.app_uia_probe.get("background_screenshot_count", 0) or 0),
                "background_screenshot_focus_stable": self.visual_focus_stable,
            },
        }


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeDryRunReport:
    request: AgentAppBridgeRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "agent-app-bridge-dry-run"

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
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return not self.validation_errors

    @property
    def decision(self) -> str:
        if not self.request.message:
            return "app_bridge_message_required"
        if not self.request.target_ready:
            return "app_bridge_target_not_ready"
        if not self.request.native_endpoint_ready:
            return "app_bridge_native_connector_not_ready"
        if not self.request.visual_focus_stable:
            return "app_bridge_visual_focus_not_stable"
        if self.validation_errors:
            return "app_bridge_request_invalid"
        return "app_bridge_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


class AgentAppBridgeDryRunAdapter:
    def prepare(self, request: AgentAppBridgeRequest) -> AgentAppBridgeDryRunReport:
        errors = _validate_request(request)
        return AgentAppBridgeDryRunReport(
            request=request,
            validation_errors=errors,
        )


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeSendReport:
    request: AgentAppBridgeRequest
    dry_run_report: AgentAppBridgeDryRunReport
    target: BrowserDevToolsTarget | None = None
    action_result: dict = dataclasses.field(default_factory=dict)
    native_call_attempts: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-bridge-send"

    @property
    def safety_mode(self) -> str:
        return "native_bridge_execute"

    @property
    def control_allowed(self) -> bool:
        return bool(self.dry_run_report.ok and self.target is not None and not self.error)

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 1 if self.native_call_attempts else 0

    @property
    def readback_text(self) -> str:
        return _first_text(
            self.action_result,
            "readbackText",
            "readback_text",
            "pageText",
            "page_text",
            "text",
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
    def accepted(self) -> bool:
        return not self.missing_required_markers and not self.present_forbidden_markers

    @property
    def ok(self) -> bool:
        return self.decision == "app_bridge_send_accepted"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "app_bridge_request_not_ready"
        if self.error:
            return "app_bridge_send_failed"
        if self.target is None:
            return "app_bridge_native_target_not_ready"
        if not self.action_result.get("composerFound"):
            return "app_bridge_composer_not_found"
        if not self.action_result.get("messageSet"):
            return "app_bridge_message_not_verified"
        if not self.action_result.get("submitAttempted"):
            return "app_bridge_submit_not_verified"
        if self.action_result.get("submitVerified") is False:
            return "app_bridge_submit_not_verified"
        if self.present_forbidden_markers:
            return "app_bridge_forbidden_marker_present"
        if self.missing_required_markers:
            return "app_bridge_message_submitted_acceptance_pending"
        return "app_bridge_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "accepted": self.accepted,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "native_call_attempts": int(self.native_call_attempts or 0),
            "missing_required_markers": list(self.missing_required_markers),
            "present_forbidden_markers": list(self.present_forbidden_markers),
            "target": _devtools_target_to_dict(self.target),
            "action_result": dict(self.action_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class AgentAppBridgeCdpAdapter:
    def __init__(self, *, devtools_client: BrowserDevToolsClient | None = None):
        self._devtools_client = devtools_client or BrowserDevToolsClient()

    def send(self, request: AgentAppBridgeRequest) -> AgentAppBridgeSendReport:
        started = time.perf_counter()
        dry_run = AgentAppBridgeDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        target = _select_devtools_target(request.endpoint)
        if target is None:
            return AgentAppBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                error="devtools_target_not_ready",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        debugger_url = str(request.endpoint.get("debugger_url", "") or "").strip()
        native_call_attempts = 1
        try:
            result = self._devtools_client.evaluate(
                debugger_url,
                target,
                _bridge_send_expression(request.composed_message or request.message),
            )
            action_result = _remote_object_value(result)
        except Exception as exc:
            return AgentAppBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                target=target,
                native_call_attempts=native_call_attempts,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        return AgentAppBridgeSendReport(
            request=request,
            dry_run_report=dry_run,
            target=target,
            action_result=action_result,
            native_call_attempts=native_call_attempts,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


def build_agent_app_bridge_request(
    *,
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    selected_transport: dict | object,
    app_surface_probe: dict | object,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentAppBridgeRequest:
    return AgentAppBridgeRequest(
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=str(composed_message or "").strip(),
        selected_transport=_dict_from_report(selected_transport),
        app_surface_probe=_dict_from_report(app_surface_probe),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
    )


def _validate_request(request: AgentAppBridgeRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.agent_id:
        errors.append("agent_id_required")
    if not request.message:
        errors.append("message_required")
    if not request.composed_message:
        errors.append("composed_message_required")
    if not request.target_ready:
        errors.append("target_not_ready")
    if not request.native_endpoint_ready:
        errors.append("native_endpoint_not_ready")
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


def _endpoint_summary(endpoint: dict) -> dict:
    if not endpoint:
        return {}
    return {
        "debugger_url": str(endpoint.get("debugger_url", "") or ""),
        "port": int(endpoint.get("port", 0) or 0),
        "ready": bool(endpoint.get("ready", False)),
        "target_count": int(endpoint.get("target_count", 0) or len(endpoint.get("targets", []) or [])),
    }


def _select_devtools_target(endpoint: dict) -> BrowserDevToolsTarget | None:
    targets = endpoint.get("targets")
    if not isinstance(targets, list):
        return None
    candidates: list[BrowserDevToolsTarget] = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        data = dict(item)
        if "id" not in data and "target_id" in data:
            data["id"] = data["target_id"]
        target = BrowserDevToolsTarget.from_dict(data)
        if target.web_socket_debugger_url:
            candidates.append(target)
    if not candidates:
        return None
    for target in candidates:
        if (target.type or "").lower() in {"page", "webview"}:
            return target
    return candidates[0]


def _remote_object_value(result: dict) -> dict:
    if not isinstance(result, dict):
        return {}
    value = result.get("value")
    if isinstance(value, dict):
        return dict(value)
    if result.get("type") == "exception":
        return {"exception": result.get("exceptionDetails") or result}
    return {"value": value}


def _bridge_send_expression(message: str) -> str:
    message_json = json_dumps_ascii(str(message or ""))
    return (
        "(() => {"
        f"const message = {message_json};"
        "const visible = (el) => {"
        "if (!el) return false;"
        "const rect = el.getBoundingClientRect();"
        "const style = getComputedStyle(el);"
        "return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';"
        "};"
        "const readText = (el) => {"
        "if (!el) return '';"
        "if ('value' in el) return String(el.value || '');"
        "return String(el.innerText || el.textContent || '');"
        "};"
        "const setText = (el, text) => {"
        "if ('value' in el) {"
        "const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')?.set;"
        "if (setter) setter.call(el, text); else el.value = text;"
        "} else {"
        "el.textContent = text;"
        "}"
        "const inputEvent = typeof InputEvent === 'function' "
        "? new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}) "
        ": new Event('input', {bubbles: true});"
        "el.dispatchEvent(inputEvent);"
        "el.dispatchEvent(new Event('change', {bubbles: true}));"
        "};"
        "const composerSelectors = ["
        "'textarea',"
        "'[contenteditable=\"true\"]',"
        "'[role=\"textbox\"]',"
        "'input[type=\"text\"]',"
        "'input:not([type])'"
        "];"
        "const composers = Array.from(document.querySelectorAll(composerSelectors.join(','))).filter(visible);"
        "const composer = composers[0] || null;"
        "if (!composer) {"
        "return {composerFound: false, composerCandidateCount: 0, messageSet: false, submitAttempted: false, submitVerified: false, readbackText: ''};"
        "}"
        "setText(composer, message);"
        "const composerText = readText(composer);"
        "const messageSet = composerText === message || composerText.includes(message);"
        "const buttonSelectors = ['button', '[role=\"button\"]', 'input[type=\"submit\"]'];"
        "const buttons = Array.from(document.querySelectorAll(buttonSelectors.join(','))).filter((el) => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true');"
        "const labelFor = (el) => String(el.getAttribute('aria-label') || el.getAttribute('title') || el.value || el.innerText || el.textContent || '').trim().toLowerCase();"
        "const sendButton = buttons.find((el) => /send|submit|发送|提交|运行|开始/.test(labelFor(el))) || null;"
        "if (!sendButton) {"
        "return {composerFound: true, composerCandidateCount: composers.length, messageSet, submitAttempted: false, submitVerified: false, readbackText: document.body ? document.body.innerText.slice(0, 6000) : ''};"
        "}"
        "sendButton.click();"
        "const readbackText = document.body ? document.body.innerText.slice(0, 6000) : '';"
        "return {"
        "composerFound: true,"
        "composerCandidateCount: composers.length,"
        "messageSet,"
        "submitAttempted: true,"
        "submitVerified: true,"
        "sendButtonLabel: labelFor(sendButton),"
        "readbackText"
        "};"
        "})()"
    )


def _devtools_target_to_dict(target: BrowserDevToolsTarget | None) -> dict:
    if target is None:
        return {}
    return {
        "target_id": target.target_id,
        "type": target.type,
        "title": target.title,
        "url": target.url,
        "webSocketDebuggerUrl": target.web_socket_debugger_url,
    }


def _first_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def json_dumps_ascii(value: str) -> str:
    import json

    return json.dumps(value, ensure_ascii=True)


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


__all__ = [
    "BRIDGE_SCHEMA_VERSION",
    "AgentAppBridgeCdpAdapter",
    "AgentAppBridgeDryRunAdapter",
    "AgentAppBridgeDryRunReport",
    "AgentAppBridgeRequest",
    "AgentAppBridgeSendReport",
    "build_agent_app_bridge_request",
]
