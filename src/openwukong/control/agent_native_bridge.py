# -*- coding: utf-8 -*-
"""Native bridge contract for deterministic agent app background sends.

This layer only speaks an explicit local JSON bridge. It does not use keyboard,
mouse, clipboard, SendInput, or foreground window takeover.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.error
import urllib.request
import uuid


AGENT_NATIVE_BRIDGE_SCHEMA_VERSION = "agent-native-bridge-v1"

SEND_ACTION = "agent_app_conversation.native_bridge_send_message"
_SEND_CAPABILITY_NAMES = {
    SEND_ACTION,
    "agent_app_conversation.send_message",
    "agent.chat.send_message",
    "agent.send_message",
    "send_message",
}


@dataclasses.dataclass(frozen=True)
class AgentNativeBridgeRequest:
    bridge_url: str
    agent: str
    agent_id: str
    project_name: str
    task_name: str
    message: str
    composed_message: str
    selected_transport: dict = dataclasses.field(default_factory=dict)
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    request_id: str = dataclasses.field(default_factory=lambda: f"anb-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "agent-native-bridge-request"

    @property
    def schema_version(self) -> str:
        return AGENT_NATIVE_BRIDGE_SCHEMA_VERSION

    @property
    def payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "action": SEND_ACTION,
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "message": self.message,
            "composed_message": self.composed_message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
        }

    def to_dict(self, capability_report: dict | None = None) -> dict:
        capabilities = dict(capability_report or {})
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "bridge_url": self.bridge_url,
            "native_endpoint_ready": _native_endpoint_ready(self, capabilities),
            "agent_ready": _agent_ready(capabilities, self.agent_id),
            "project_ready": _project_ready(capabilities, self.project_name),
            "task_ready": _task_ready(capabilities, self.task_name),
            "send_action_ready": _send_action_ready(capabilities),
            "background_safe": _background_safe(capabilities),
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "target": _target_summary(capabilities, self),
            "payload": self.payload,
        }


@dataclasses.dataclass(frozen=True)
class AgentNativeBridgeDryRunReport:
    request: AgentNativeBridgeRequest
    capability_report: dict = dataclasses.field(default_factory=dict)
    capability_probe_attempts: int = 0
    validation_errors: tuple[str, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-native-bridge-dry-run"

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
    def window_input_attempts(self) -> int:
        return 0

    @property
    def native_endpoint_ready(self) -> bool:
        return _native_endpoint_ready(self.request, self.capability_report)

    @property
    def agent_ready(self) -> bool:
        return _agent_ready(self.capability_report, self.request.agent_id)

    @property
    def project_ready(self) -> bool:
        return _project_ready(self.capability_report, self.request.project_name)

    @property
    def task_ready(self) -> bool:
        return _task_ready(self.capability_report, self.request.task_name)

    @property
    def send_action_ready(self) -> bool:
        return _send_action_ready(self.capability_report)

    @property
    def background_safe(self) -> bool:
        return _background_safe(self.capability_report)

    @property
    def ok(self) -> bool:
        return not self.validation_errors and not self.error

    @property
    def decision(self) -> str:
        if not self.request.bridge_url:
            return "agent_native_bridge_url_missing"
        if not self.request.message:
            return "agent_native_bridge_message_required"
        if self.error:
            return "agent_native_bridge_capability_probe_failed"
        if not self.native_endpoint_ready:
            return "agent_native_bridge_not_ready"
        if not self.agent_ready:
            return "agent_native_bridge_agent_not_ready"
        if not self.project_ready:
            return "agent_native_bridge_project_not_ready"
        if not self.task_ready:
            return "agent_native_bridge_task_not_ready"
        if not self.send_action_ready:
            return "agent_native_bridge_send_action_not_ready"
        if not self.background_safe:
            return "agent_native_bridge_background_not_safe"
        if self.validation_errors:
            return "agent_native_bridge_request_invalid"
        return "agent_native_bridge_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "window_input_attempts": self.window_input_attempts,
            "capability_probe_attempts": self.capability_probe_attempts,
            "native_endpoint_ready": self.native_endpoint_ready,
            "agent_ready": self.agent_ready,
            "project_ready": self.project_ready,
            "task_ready": self.task_ready,
            "send_action_ready": self.send_action_ready,
            "background_safe": self.background_safe,
            "validation_errors": list(self.validation_errors),
            "error": self.error,
            "capability_report": dict(self.capability_report),
            "request": self.request.to_dict(self.capability_report),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class AgentNativeBridgeDryRunAdapter:
    def __init__(self, *, client: object | None = None, request_timeout: float = 3.0):
        self._client = client or AgentNativeBridgeClient(request_timeout=request_timeout)

    def prepare(self, request: AgentNativeBridgeRequest) -> AgentNativeBridgeDryRunReport:
        started = time.perf_counter()
        capability_report: dict = {}
        capability_probe_attempts = 0
        error = ""
        if request.bridge_url:
            capability_probe_attempts = 1
            try:
                data = self._client.read_capabilities(request)
                capability_report = dict(data) if isinstance(data, dict) else {}
            except Exception as exc:
                error = str(exc) or exc.__class__.__name__
        validation_errors = _validate_request(request, capability_report)
        return AgentNativeBridgeDryRunReport(
            request=request,
            capability_report=capability_report,
            capability_probe_attempts=capability_probe_attempts,
            validation_errors=validation_errors,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


@dataclasses.dataclass(frozen=True)
class AgentNativeBridgeSendReport:
    request: AgentNativeBridgeRequest
    dry_run_report: AgentNativeBridgeDryRunReport
    action_result: dict = dataclasses.field(default_factory=dict)
    native_call_attempts: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-native-bridge-send"

    @property
    def safety_mode(self) -> str:
        return "native_bridge_execute"

    @property
    def control_allowed(self) -> bool:
        return bool(self.dry_run_report.ok and self.native_call_attempts and not self.error)

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 1 if self.native_call_attempts else 0

    @property
    def window_input_attempts(self) -> int:
        return _int_value(self.action_result, "window_input_attempts")

    @property
    def keyboard_input_attempts(self) -> int:
        return _int_value(self.action_result, "keyboard_input_attempts")

    @property
    def clipboard_write_attempts(self) -> int:
        return _int_value(self.action_result, "clipboard_write_attempts")

    @property
    def foreground_focus_stable(self) -> bool:
        if "foreground_focus_stable" in self.action_result:
            return bool(self.action_result.get("foreground_focus_stable", False))
        if "foreground_changed" in self.action_result:
            return not bool(self.action_result.get("foreground_changed", False))
        return True

    @property
    def readback_text(self) -> str:
        return _first_text(
            self.action_result,
            "readbackText",
            "readback_text",
            "conversation",
            "transcript",
            "text",
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
        return self.decision == "agent_native_bridge_send_accepted"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "agent_native_bridge_request_not_ready"
        if self.error:
            return "agent_native_bridge_send_failed"
        if not self.native_call_attempts:
            return "agent_native_bridge_native_call_not_attempted"
        if not _send_result_ok(self.action_result):
            return "agent_native_bridge_send_failed"
        if self.window_input_attempts:
            return "agent_native_bridge_window_input_attempted"
        if self.keyboard_input_attempts:
            return "agent_native_bridge_keyboard_input_attempted"
        if self.clipboard_write_attempts:
            return "agent_native_bridge_clipboard_write_attempted"
        if not self.foreground_focus_stable:
            return "agent_native_bridge_foreground_changed"
        if self.present_forbidden_markers:
            return "agent_native_bridge_forbidden_marker_present"
        if self.missing_required_markers:
            return "agent_native_bridge_acceptance_pending"
        return "agent_native_bridge_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "native_call_attempts": int(self.native_call_attempts or 0),
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "foreground_focus_stable": self.foreground_focus_stable,
            "missing_required_markers": list(self.missing_required_markers),
            "present_forbidden_markers": list(self.present_forbidden_markers),
            "action_result": dict(self.action_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(self.dry_run_report.capability_report),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class AgentNativeBridgeSenderAdapter:
    def __init__(self, *, client: object | None = None, request_timeout: float = 10.0):
        self._client = client or AgentNativeBridgeClient(request_timeout=request_timeout)
        self._request_timeout = request_timeout

    def send(self, request: AgentNativeBridgeRequest) -> AgentNativeBridgeSendReport:
        started = time.perf_counter()
        dry_run = AgentNativeBridgeDryRunAdapter(
            client=self._client,
            request_timeout=self._request_timeout,
        ).prepare(request)
        if not dry_run.ok:
            return AgentNativeBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        native_call_attempts = 1
        try:
            data = self._client.send_message(request)
            action_result = dict(data) if isinstance(data, dict) else {}
            error = ""
        except Exception as exc:
            action_result = {}
            error = str(exc) or exc.__class__.__name__

        return AgentNativeBridgeSendReport(
            request=request,
            dry_run_report=dry_run,
            action_result=action_result,
            native_call_attempts=native_call_attempts,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class AgentNativeBridgeClient:
    def __init__(self, *, request_timeout: float = 3.0):
        self.request_timeout = max(0.1, float(request_timeout))

    def read_capabilities(self, request: AgentNativeBridgeRequest) -> dict:
        return self._post_json(
            request.bridge_url,
            "/v1/agent/capabilities",
            {
                "action": "read_capabilities",
                "agent": request.agent,
                "agent_id": request.agent_id,
                "project_name": request.project_name,
                "task_name": request.task_name,
                "payload": request.payload,
            },
        )

    def send_message(self, request: AgentNativeBridgeRequest) -> dict:
        payload = dict(request.payload)
        payload.update(
            {
                "action": SEND_ACTION,
                "agent": request.agent,
                "agent_id": request.agent_id,
                "project_name": request.project_name,
                "task_name": request.task_name,
                "message": request.message,
                "composed_message": request.composed_message,
            }
        )
        return self._post_json(request.bridge_url, "/v1/agent/chat", payload)

    def _post_json(self, bridge_url: str, path: str, payload: dict) -> dict:
        endpoint = f"{_normalize_bridge_url(bridge_url)}{path}"
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            data = _decode_json_bytes(raw)
            if data:
                return data
            raise
        data = _decode_json_bytes(raw)
        if not isinstance(data, dict):
            raise ValueError("agent_native_bridge_response_not_object")
        return data


def build_agent_native_bridge_request(
    *,
    bridge_url: str,
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    selected_transport: dict | object | None = None,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentNativeBridgeRequest:
    return AgentNativeBridgeRequest(
        bridge_url=str(bridge_url or "").strip(),
        agent=str(agent or "").strip(),
        agent_id=str(agent_id or "").strip().lower(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=str(composed_message or "").strip(),
        selected_transport=_dict_from_report(selected_transport),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
    )


def _validate_request(
    request: AgentNativeBridgeRequest,
    capability_report: dict,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.bridge_url:
        errors.append("bridge_url_required")
    if not request.agent_id:
        errors.append("agent_id_required")
    if not request.message:
        errors.append("message_required")
    if not request.composed_message:
        errors.append("composed_message_required")
    if not _native_endpoint_ready(request, capability_report):
        errors.append("native_endpoint_not_ready")
    if not _agent_ready(capability_report, request.agent_id):
        errors.append("agent_not_ready")
    if not _project_ready(capability_report, request.project_name):
        errors.append("project_not_ready")
    if not _task_ready(capability_report, request.task_name):
        errors.append("task_not_ready")
    if not _send_action_ready(capability_report):
        errors.append("send_action_not_ready")
    if not _background_safe(capability_report):
        errors.append("background_not_safe")
    return tuple(errors)


def _native_endpoint_ready(request: AgentNativeBridgeRequest, capability_report: dict) -> bool:
    return bool(request.bridge_url and capability_report.get("ok", False))


def _agent_ready(capability_report: dict, agent_id: str) -> bool:
    agent = _normalize(agent_id)
    if not agent:
        return False
    for candidate in _agent_candidates(capability_report):
        if candidate.get("available", True) is False:
            continue
        haystack = _candidate_text(candidate, ("agent_id", "id", "name", "label", "adapter_id"))
        if agent in haystack:
            return True
    for key in ("agent_id", "agent", "preferred_agent_id", "preferred_chat_adapter"):
        value = _normalize(capability_report.get(key, ""))
        if value and agent in value:
            return True
    return False


def _project_ready(capability_report: dict, project_name: str) -> bool:
    project = _normalize(project_name)
    if not project:
        return True
    for candidate in _named_candidates(capability_report, ("projects", "workspaces", "workspaceFolders")):
        if candidate.get("available", True) is False:
            continue
        haystack = _candidate_text(candidate, ("name", "project_name", "fsPath", "path", "uri", "title"))
        if project in haystack:
            return True
    for key in ("project_name", "project", "workspace", "workspace_path"):
        value = _normalize(capability_report.get(key, ""))
        if value and project in value.replace("\\", "/"):
            return True
    return False


def _task_ready(capability_report: dict, task_name: str) -> bool:
    task = _normalize(task_name)
    if not task:
        return True
    for candidate in _named_candidates(capability_report, ("tasks", "sessions", "conversations")):
        if candidate.get("available", True) is False:
            continue
        haystack = _candidate_text(candidate, ("name", "task_name", "title", "id", "session_id"))
        if task in haystack:
            return True
    for key in ("task_name", "task", "session", "conversation"):
        value = _normalize(capability_report.get(key, ""))
        if value and task in value:
            return True
    return False


def _target_summary(capability_report: dict, request: AgentNativeBridgeRequest) -> dict:
    return {
        "agent_id": request.agent_id,
        "agent_ready": _agent_ready(capability_report, request.agent_id),
        "project_name": request.project_name,
        "project_ready": _project_ready(capability_report, request.project_name),
        "task_name": request.task_name,
        "task_ready": _task_ready(capability_report, request.task_name),
    }


def _agent_candidates(capability_report: dict) -> tuple[dict, ...]:
    return _named_candidates(capability_report, ("agents", "agent_adapters", "chat_adapters"))


def _named_candidates(capability_report: dict, keys: tuple[str, ...]) -> tuple[dict, ...]:
    candidates: list[dict] = []
    for key in keys:
        value = capability_report.get(key)
        if isinstance(value, list):
            candidates.extend(dict(item) for item in value if isinstance(item, dict))
    return tuple(candidates)


def _candidate_text(candidate: dict, keys: tuple[str, ...]) -> str:
    return " ".join(_normalize(candidate.get(key, "")) for key in keys)


def _send_action_ready(capability_report: dict) -> bool:
    for key in ("send_action_ready", "send_ready", "can_send", "can_send_message"):
        if key in capability_report:
            return bool(capability_report.get(key, False))
    capabilities = capability_report.get("capabilities")
    if isinstance(capabilities, list):
        values = {_normalize(item) for item in capabilities}
        if values & {_normalize(item) for item in _SEND_CAPABILITY_NAMES}:
            return True
    actions = capability_report.get("actions")
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("available", True) is False:
                continue
            value = _normalize(
                action.get("action", "")
                or action.get("id", "")
                or action.get("name", "")
            )
            if value in {_normalize(item) for item in _SEND_CAPABILITY_NAMES}:
                return True
    return False


def _background_safe(capability_report: dict) -> bool:
    unsafe_keys = (
        "requires_foreground",
        "foreground_required",
        "window_input_required",
        "keyboard_input_required",
        "mouse_input_required",
        "clipboard_required",
    )
    if any(bool(capability_report.get(key, False)) for key in unsafe_keys):
        return False
    for key in ("background_safe", "native_background_safe"):
        if key in capability_report and not bool(capability_report.get(key, False)):
            return False
    return True


def _send_result_ok(action_result: dict) -> bool:
    if "ok" in action_result:
        return bool(action_result.get("ok", False))
    return bool(
        action_result.get("sent", False)
        or action_result.get("submitVerified", False)
        or action_result.get("submit_verified", False)
    )


def _normalize_bridge_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.rstrip("/")


def _decode_json_bytes(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig")
    data = json.loads(text)
    return dict(data) if isinstance(data, dict) else {}


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


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


def _first_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _int_value(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


def _normalize(value: object) -> str:
    return str(value or "").strip().casefold()


__all__ = [
    "AGENT_NATIVE_BRIDGE_SCHEMA_VERSION",
    "SEND_ACTION",
    "AgentNativeBridgeClient",
    "AgentNativeBridgeDryRunAdapter",
    "AgentNativeBridgeDryRunReport",
    "AgentNativeBridgeRequest",
    "AgentNativeBridgeSenderAdapter",
    "AgentNativeBridgeSendReport",
    "build_agent_native_bridge_request",
]
