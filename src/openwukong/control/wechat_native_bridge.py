# -*- coding: utf-8 -*-
"""Native bridge contract for deterministic WeChat background sends.

The Python side only speaks an explicit local JSON bridge. It does not use
keyboard, mouse, clipboard, SendInput, or foreground window takeover.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.error
import urllib.request
import uuid


WECHAT_NATIVE_BRIDGE_SCHEMA_VERSION = "wechat-native-bridge-v1"

_SEND_ACTION = "wechat.conversation.native_bridge_send_message"
_SEND_CAPABILITY_NAMES = {
    _SEND_ACTION,
    "wechat.conversation.send_message",
    "wechat.send_message",
    "send_message",
}


@dataclasses.dataclass(frozen=True)
class WeChatNativeBridgeRequest:
    bridge_url: str
    target_name: str
    message: str
    background_screenshot_focus_stable: bool = True
    selected_transport: dict = dataclasses.field(default_factory=dict)
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    request_id: str = dataclasses.field(default_factory=lambda: f"wcn-{uuid.uuid4().hex[:16]}")

    @property
    def mode(self) -> str:
        return "wechat-native-bridge-request"

    @property
    def schema_version(self) -> str:
        return WECHAT_NATIVE_BRIDGE_SCHEMA_VERSION

    @property
    def payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "action": _SEND_ACTION,
            "target_name": self.target_name,
            "message": self.message,
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
            "target_ready": _target_ready(capabilities, self.target_name),
            "send_action_ready": _send_action_ready(capabilities),
            "background_safe": _background_safe(capabilities),
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "target_name": self.target_name,
            "selected_transport": dict(self.selected_transport),
            "target": _target_summary(capabilities, self.target_name),
            "payload": self.payload,
        }


@dataclasses.dataclass(frozen=True)
class WeChatNativeBridgeDryRunReport:
    request: WeChatNativeBridgeRequest
    capability_report: dict = dataclasses.field(default_factory=dict)
    capability_probe_attempts: int = 0
    validation_errors: tuple[str, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-bridge-dry-run"

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
    def native_endpoint_ready(self) -> bool:
        return _native_endpoint_ready(self.request, self.capability_report)

    @property
    def target_ready(self) -> bool:
        return _target_ready(self.capability_report, self.request.target_name)

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
            return "wechat_native_bridge_url_missing"
        if not self.request.message:
            return "wechat_native_bridge_message_required"
        if self.error:
            return "wechat_native_bridge_capability_probe_failed"
        if not self.native_endpoint_ready:
            return "wechat_native_bridge_not_ready"
        if not self.target_ready:
            return "wechat_native_bridge_target_not_ready"
        if not self.send_action_ready:
            return "wechat_native_bridge_send_action_not_ready"
        if not self.background_safe:
            return "wechat_native_bridge_background_not_safe"
        if not self.request.background_screenshot_focus_stable:
            return "wechat_native_bridge_visual_focus_not_stable"
        if self.validation_errors:
            return "wechat_native_bridge_request_invalid"
        return "wechat_native_bridge_dry_run_ready"

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
            "capability_probe_attempts": self.capability_probe_attempts,
            "native_endpoint_ready": self.native_endpoint_ready,
            "target_ready": self.target_ready,
            "send_action_ready": self.send_action_ready,
            "background_safe": self.background_safe,
            "validation_errors": list(self.validation_errors),
            "error": self.error,
            "capability_report": dict(self.capability_report),
            "request": self.request.to_dict(self.capability_report),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class WeChatNativeBridgeDryRunAdapter:
    def __init__(
        self,
        *,
        client: object | None = None,
        request_timeout: float = 3.0,
    ):
        self._client = client or WeChatNativeBridgeClient(request_timeout=request_timeout)

    def prepare(self, request: WeChatNativeBridgeRequest) -> WeChatNativeBridgeDryRunReport:
        started = time.perf_counter()
        capability_report: dict = {}
        capability_probe_attempts = 0
        error = ""
        if request.bridge_url:
            capability_probe_attempts = 1
            try:
                read = getattr(self._client, "read_capabilities")
                data = read(request)
                capability_report = dict(data) if isinstance(data, dict) else {}
            except Exception as exc:
                error = str(exc) or exc.__class__.__name__
        validation_errors = _validate_request(request, capability_report)
        return WeChatNativeBridgeDryRunReport(
            request=request,
            capability_report=capability_report,
            capability_probe_attempts=capability_probe_attempts,
            validation_errors=validation_errors,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


@dataclasses.dataclass(frozen=True)
class WeChatNativeBridgeSendReport:
    request: WeChatNativeBridgeRequest
    dry_run_report: WeChatNativeBridgeDryRunReport
    action_result: dict = dataclasses.field(default_factory=dict)
    native_call_attempts: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-bridge-send"

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
    def window_input_attempts(self) -> int:
        return _int_value(self.action_result, "window_input_attempts")

    @property
    def keyboard_input_attempts(self) -> int:
        return _int_value(self.action_result, "keyboard_input_attempts")

    @property
    def clipboard_write_attempts(self) -> int:
        return _int_value(self.action_result, "clipboard_write_attempts")

    @property
    def send_attempts(self) -> int:
        return 1 if self.native_call_attempts else 0

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
        return self.decision == "wechat_native_bridge_send_accepted"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "wechat_native_bridge_request_not_ready"
        if self.error:
            return "wechat_native_bridge_send_failed"
        if not self.native_call_attempts:
            return "wechat_native_bridge_native_call_not_attempted"
        if not _send_result_ok(self.action_result):
            return "wechat_native_bridge_send_failed"
        if self.window_input_attempts:
            return "wechat_native_bridge_window_input_attempted"
        if self.keyboard_input_attempts:
            return "wechat_native_bridge_keyboard_input_attempted"
        if self.clipboard_write_attempts:
            return "wechat_native_bridge_clipboard_write_attempted"
        if not self.foreground_focus_stable:
            return "wechat_native_bridge_foreground_changed"
        if self.present_forbidden_markers:
            return "wechat_native_bridge_forbidden_marker_present"
        if self.missing_required_markers:
            return "wechat_native_bridge_acceptance_pending"
        return "wechat_native_bridge_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "send_attempts": self.send_attempts,
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


class WeChatNativeBridgeSenderAdapter:
    def __init__(
        self,
        *,
        client: object | None = None,
        request_timeout: float = 10.0,
    ):
        self._client = client or WeChatNativeBridgeClient(request_timeout=request_timeout)
        self._request_timeout = request_timeout

    def send(self, request: WeChatNativeBridgeRequest) -> WeChatNativeBridgeSendReport:
        started = time.perf_counter()
        dry_run = WeChatNativeBridgeDryRunAdapter(
            client=self._client,
            request_timeout=self._request_timeout,
        ).prepare(request)
        if not dry_run.ok:
            return WeChatNativeBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        native_call_attempts = 1
        try:
            send = getattr(self._client, "send_message")
            data = send(request)
            action_result = dict(data) if isinstance(data, dict) else {}
            error = ""
        except Exception as exc:
            action_result = {}
            error = str(exc) or exc.__class__.__name__

        return WeChatNativeBridgeSendReport(
            request=request,
            dry_run_report=dry_run,
            action_result=action_result,
            native_call_attempts=native_call_attempts,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class WeChatNativeBridgeClient:
    def __init__(self, *, request_timeout: float = 3.0):
        self.request_timeout = max(0.1, float(request_timeout))

    def read_capabilities(self, request: WeChatNativeBridgeRequest) -> dict:
        return self._post_json(
            request.bridge_url,
            "/v1/wechat/capabilities",
            {
                "action": "read_capabilities",
                "target_name": request.target_name,
                "payload": request.payload,
            },
        )

    def send_message(self, request: WeChatNativeBridgeRequest) -> dict:
        payload = dict(request.payload)
        payload.update(
            {
                "action": _SEND_ACTION,
                "target_name": request.target_name,
                "message": request.message,
            }
        )
        return self._post_json(request.bridge_url, "/v1/wechat/send", payload)

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
            raise ValueError("wechat_native_bridge_response_not_object")
        return data


def build_wechat_native_bridge_request(
    *,
    bridge_url: str,
    target_name: str,
    message: str,
    background_screenshot_focus_stable: bool = True,
    selected_transport: dict | object | None = None,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> WeChatNativeBridgeRequest:
    return WeChatNativeBridgeRequest(
        bridge_url=str(bridge_url or "").strip(),
        target_name=str(target_name or "").strip(),
        message=str(message or "").strip(),
        background_screenshot_focus_stable=bool(background_screenshot_focus_stable),
        selected_transport=_dict_from_report(selected_transport),
        required_markers=_string_tuple(required_markers),
        forbidden_markers=_string_tuple(forbidden_markers),
    )


def _validate_request(request: WeChatNativeBridgeRequest, capability_report: dict) -> tuple[str, ...]:
    errors: list[str] = []
    if not request.bridge_url:
        errors.append("bridge_url_required")
    if not request.target_name:
        errors.append("target_name_required")
    if not request.message:
        errors.append("message_required")
    if not _native_endpoint_ready(request, capability_report):
        errors.append("native_endpoint_not_ready")
    if not _target_ready(capability_report, request.target_name):
        errors.append("target_not_ready")
    if not _send_action_ready(capability_report):
        errors.append("send_action_not_ready")
    if not _background_safe(capability_report):
        errors.append("background_not_safe")
    if not request.background_screenshot_focus_stable:
        errors.append("background_screenshot_focus_not_stable")
    return tuple(errors)


def _native_endpoint_ready(request: WeChatNativeBridgeRequest, capability_report: dict) -> bool:
    return bool(request.bridge_url and capability_report.get("ok", False))


def _target_ready(capability_report: dict, target_name: str) -> bool:
    return bool(_matching_target(capability_report, target_name))


def _target_summary(capability_report: dict, target_name: str) -> dict:
    target = _matching_target(capability_report, target_name)
    if target:
        return {
            "target_name": target_name,
            "target_matched": True,
            "name": str(
                target.get("name", "")
                or target.get("display_name", "")
                or target.get("target_name", "")
                or ""
            ),
            "conversation_id": str(
                target.get("conversation_id", "")
                or target.get("id", "")
                or target.get("target_id", "")
                or ""
            ),
            "available": target.get("available", True) is not False,
        }
    return {
        "target_name": target_name,
        "target_matched": False,
        "available": False,
    }


def _matching_target(capability_report: dict, target_name: str) -> dict:
    normalized_target = _normalize(target_name)
    if not normalized_target:
        return {}
    for target in _target_candidates(capability_report):
        if target.get("available", True) is False:
            continue
        haystack = " ".join(
            str(target.get(key, "") or "")
            for key in (
                "name",
                "display_name",
                "target_name",
                "conversation_name",
                "title",
                "alias",
                "id",
                "conversation_id",
            )
        )
        if normalized_target in _normalize(haystack):
            return target
    return {}


def _target_candidates(capability_report: dict) -> tuple[dict, ...]:
    candidates: list[dict] = []
    for key in ("targets", "conversations", "sessions"):
        value = capability_report.get(key)
        if isinstance(value, list):
            candidates.extend(dict(item) for item in value if isinstance(item, dict))
    target = capability_report.get("target")
    if isinstance(target, dict):
        candidates.append(dict(target))
    return tuple(candidates)


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
    "WECHAT_NATIVE_BRIDGE_SCHEMA_VERSION",
    "WeChatNativeBridgeClient",
    "WeChatNativeBridgeDryRunAdapter",
    "WeChatNativeBridgeDryRunReport",
    "WeChatNativeBridgeRequest",
    "WeChatNativeBridgeSenderAdapter",
    "WeChatNativeBridgeSendReport",
    "build_wechat_native_bridge_request",
]
