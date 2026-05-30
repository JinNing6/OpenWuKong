# -*- coding: utf-8 -*-
"""Dry-run contract for app-side agent message bridges."""

from __future__ import annotations

import dataclasses
import time
import uuid

from openwukong.connectors import ConnectorTarget
from openwukong.connectors.browser import BrowserDevToolsClient, BrowserDevToolsTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.control.agent_native_bridge import (
    AgentNativeBridgeSenderAdapter,
    SEND_ACTION as AGENT_NATIVE_SEND_ACTION,
    build_agent_native_bridge_request,
)


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
        if bool(self.app_uia_probe.get("target_matched", False)):
            return True
        endpoint = self.endpoint
        return bool(
            (
                _endpoint_supports_ide_chat(endpoint, self.agent_id)
                or _endpoint_supports_agent_native_bridge(endpoint, self.agent_id)
                or _endpoint_supports_app_devtools(endpoint, self.agent_id)
            )
            and _endpoint_matches_project(endpoint, self.project_name)
            and _endpoint_matches_task(endpoint, self.task_name)
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
        window = _select_matched_app_window(
            windows,
            project_name=self.project_name,
            task_name=self.task_name,
        )
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
    composer_probe_report: dict = dataclasses.field(default_factory=dict)
    action_result: dict = dataclasses.field(default_factory=dict)
    native_probe_attempts: int = 0
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
        return bool(
            self.dry_run_report.ok
            and self.target is not None
            and not self.error
            and self.native_call_attempts > 0
        )

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
        if self.composer_probe_report and not bool(self.composer_probe_report.get("ok", False)):
            return str(
                self.composer_probe_report.get("decision", "")
                or "app_bridge_composer_not_ready"
            )
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
            "native_probe_attempts": int(self.native_probe_attempts or 0),
            "native_call_attempts": int(self.native_call_attempts or 0),
            "missing_required_markers": list(self.missing_required_markers),
            "present_forbidden_markers": list(self.present_forbidden_markers),
            "target": _devtools_target_to_dict(self.target),
            "composer_probe_report": dict(self.composer_probe_report),
            "action_result": dict(self.action_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeCdpComposerProbeReport:
    request: AgentAppBridgeRequest
    dry_run_report: AgentAppBridgeDryRunReport
    target: BrowserDevToolsTarget | None = None
    action_result: dict = dataclasses.field(default_factory=dict)
    native_probe_attempts: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-bridge-cdp-composer-probe"

    @property
    def safety_mode(self) -> str:
        return "read_only_native_probe"

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
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def safe_composer_found(self) -> bool:
        return bool(
            self.action_result.get("safeComposerFound", False)
            or int(self.action_result.get("safeComposerCandidateCount", 0) or 0) > 0
        )

    @property
    def ok(self) -> bool:
        return self.decision == "app_bridge_composer_ready"

    @property
    def decision(self) -> str:
        if not self.dry_run_report.ok:
            return "app_bridge_request_not_ready"
        if self.error:
            return "app_bridge_composer_probe_failed"
        if self.target is None:
            return "app_bridge_native_target_not_ready"
        if not self.safe_composer_found:
            return "app_bridge_composer_not_ready"
        return "app_bridge_composer_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "native_probe_attempts": int(self.native_probe_attempts or 0),
            "safe_composer_found": self.safe_composer_found,
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

    def probe_composer(self, request: AgentAppBridgeRequest) -> AgentAppBridgeCdpComposerProbeReport:
        started = time.perf_counter()
        dry_run = AgentAppBridgeDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppBridgeCdpComposerProbeReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        target = _select_devtools_target(
            request.endpoint,
            project_name=request.project_name,
            task_name=request.task_name,
        )
        if target is None:
            return AgentAppBridgeCdpComposerProbeReport(
                request=request,
                dry_run_report=dry_run,
                error="devtools_target_not_ready",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        debugger_url = str(request.endpoint.get("debugger_url", "") or "").strip()
        native_probe_attempts = 1
        try:
            result = self._devtools_client.evaluate(
                debugger_url,
                target,
                _bridge_composer_probe_expression(),
            )
            action_result = _remote_object_value(result)
        except Exception as exc:
            return AgentAppBridgeCdpComposerProbeReport(
                request=request,
                dry_run_report=dry_run,
                target=target,
                native_probe_attempts=native_probe_attempts,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        return AgentAppBridgeCdpComposerProbeReport(
            request=request,
            dry_run_report=dry_run,
            target=target,
            action_result=action_result,
            native_probe_attempts=native_probe_attempts,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    def send(self, request: AgentAppBridgeRequest) -> AgentAppBridgeSendReport:
        started = time.perf_counter()
        dry_run = AgentAppBridgeDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        composer_probe = self.probe_composer(request)
        composer_probe_data = composer_probe.to_dict()
        if not composer_probe.ok:
            return AgentAppBridgeSendReport(
                request=request,
                dry_run_report=dry_run,
                target=composer_probe.target,
                composer_probe_report=composer_probe_data,
                native_probe_attempts=composer_probe.native_probe_attempts,
                error="" if composer_probe.target is not None else "devtools_target_not_ready",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        target = composer_probe.target
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
                composer_probe_report=composer_probe_data,
                native_probe_attempts=composer_probe.native_probe_attempts,
                native_call_attempts=native_call_attempts,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        return AgentAppBridgeSendReport(
            request=request,
            dry_run_report=dry_run,
            target=target,
            composer_probe_report=composer_probe_data,
            action_result=action_result,
            native_probe_attempts=composer_probe.native_probe_attempts,
            native_call_attempts=native_call_attempts,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeIdeExtensionSendReport:
    request: AgentAppBridgeRequest
    dry_run_report: AgentAppBridgeDryRunReport
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
    def transport(self) -> str:
        return IDEExtensionBridgeClient.transport

    @property
    def control_allowed(self) -> bool:
        return bool(self.dry_run_report.ok and self.native_call_attempts and not self.error)

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
            "conversation",
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
        if not _endpoint_is_ide_bridge(self.request.endpoint):
            return "app_bridge_native_target_not_ready"
        if self.error:
            return "app_bridge_send_failed"
        if not self.action_result.get("bridgeOk"):
            return "app_bridge_send_failed"
        if self.present_forbidden_markers:
            return "app_bridge_forbidden_marker_present"
        if self.missing_required_markers:
            return "app_bridge_message_submitted_acceptance_pending"
        return "app_bridge_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "transport": self.transport,
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
            "target": _ide_bridge_target_to_dict(self.request.endpoint, self.action_result),
            "action_result": dict(self.action_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class AgentAppBridgeIdeExtensionAdapter:
    def __init__(self, *, bridge_client: IDEExtensionBridgeClient | None = None):
        self._bridge_client = bridge_client or IDEExtensionBridgeClient()

    def send(self, request: AgentAppBridgeRequest) -> AgentAppBridgeIdeExtensionSendReport:
        started = time.perf_counter()
        dry_run = AgentAppBridgeDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppBridgeIdeExtensionSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        endpoint = request.endpoint
        if not _endpoint_is_ide_bridge(endpoint):
            return AgentAppBridgeIdeExtensionSendReport(
                request=request,
                dry_run_report=dry_run,
                error="ide_bridge_endpoint_not_ready",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        bridge_url = str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or "").strip()
        adapter_id = _select_ide_chat_adapter(endpoint, request.agent_id)
        target = _connector_target_from_request(request)
        native_call_attempts = 1
        try:
            if adapter_id:
                data = self._bridge_client.send_chat(
                    bridge_url,
                    target,
                    adapter_id,
                    request.composed_message or request.message,
                )
            else:
                data = self._bridge_client.send_message(
                    bridge_url,
                    target,
                    request.composed_message or request.message,
                )
            action_result = _ide_bridge_action_result(
                data,
                bridge_url=bridge_url,
                adapter_id=adapter_id,
            )
        except Exception as exc:
            return AgentAppBridgeIdeExtensionSendReport(
                request=request,
                dry_run_report=dry_run,
                native_call_attempts=native_call_attempts,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        return AgentAppBridgeIdeExtensionSendReport(
            request=request,
            dry_run_report=dry_run,
            action_result=action_result,
            native_call_attempts=native_call_attempts,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


@dataclasses.dataclass(frozen=True)
class AgentAppBridgeAgentNativeSendReport:
    request: AgentAppBridgeRequest
    dry_run_report: AgentAppBridgeDryRunReport
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
    def transport(self) -> str:
        return "agent-native-bridge"

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
    def bridge_send_attempts(self) -> int:
        return 1 if self.native_call_attempts else 0

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
        if not _endpoint_is_agent_native_bridge(self.request.endpoint):
            return "app_bridge_native_target_not_ready"
        if self.error:
            return "app_bridge_send_failed"
        if not self.action_result.get("bridgeOk"):
            return "app_bridge_send_failed"
        if self.window_input_attempts:
            return "app_bridge_window_input_attempted"
        if _int_value(self.action_result, "keyboard_input_attempts"):
            return "app_bridge_keyboard_input_attempted"
        if _int_value(self.action_result, "clipboard_write_attempts"):
            return "app_bridge_clipboard_write_attempted"
        if self.action_result.get("foreground_focus_stable") is False:
            return "app_bridge_foreground_changed"
        if self.present_forbidden_markers:
            return "app_bridge_forbidden_marker_present"
        if self.missing_required_markers:
            return "app_bridge_message_submitted_acceptance_pending"
        return "app_bridge_send_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "transport": self.transport,
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
            "target": _agent_native_bridge_target_to_dict(self.request.endpoint, self.action_result),
            "action_result": dict(self.action_result),
            "error": self.error,
            "dry_run_report": self.dry_run_report.to_dict(),
            "request": self.request.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class AgentAppBridgeAgentNativeAdapter:
    def __init__(self, *, bridge_client: object | None = None):
        self._bridge_client = bridge_client

    def send(self, request: AgentAppBridgeRequest) -> AgentAppBridgeAgentNativeSendReport:
        started = time.perf_counter()
        dry_run = AgentAppBridgeDryRunAdapter().prepare(request)
        if not dry_run.ok:
            return AgentAppBridgeAgentNativeSendReport(
                request=request,
                dry_run_report=dry_run,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        endpoint = request.endpoint
        if not _endpoint_is_agent_native_bridge(endpoint):
            return AgentAppBridgeAgentNativeSendReport(
                request=request,
                dry_run_report=dry_run,
                error="agent_native_bridge_endpoint_not_ready",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        bridge_url = str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or "").strip()
        native_request = build_agent_native_bridge_request(
            bridge_url=bridge_url,
            agent=request.agent,
            agent_id=request.agent_id,
            project_name=request.project_name,
            task_name=request.task_name,
            message=request.message,
            composed_message=request.composed_message or request.message,
            expected_app_process_names=_agent_process_names(request.agent_id),
            expected_app_pids=_request_target_pids(request),
            expected_app_hwnds=_request_target_hwnds(request),
            selected_transport=request.selected_transport,
            required_markers=request.required_markers,
            forbidden_markers=request.forbidden_markers,
        )
        native_call_attempts = 0
        try:
            sender = AgentNativeBridgeSenderAdapter(client=self._bridge_client)
            native_report = sender.send(native_request)
            native_data = native_report.to_dict()
            native_call_attempts = int(native_data.get("native_call_attempts", 0) or 0)
            action_result = _agent_native_bridge_action_result(
                native_data,
                bridge_url=bridge_url,
                agent_id=request.agent_id,
            )
            if native_report.ok or bool(action_result.get("bridgeOk", False)):
                error = ""
            else:
                error = str(native_data.get("decision", "") or "agent_native_bridge_send_failed")
        except Exception as exc:
            action_result = {}
            native_call_attempts = 1
            error = str(exc) or exc.__class__.__name__

        return AgentAppBridgeAgentNativeSendReport(
            request=request,
            dry_run_report=dry_run,
            action_result=action_result,
            native_call_attempts=native_call_attempts,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class AgentAppBridgeNativeAdapter:
    def __init__(
        self,
        *,
        devtools_client: BrowserDevToolsClient | None = None,
        ide_bridge_client: IDEExtensionBridgeClient | None = None,
        agent_native_bridge_client: object | None = None,
    ):
        self._cdp = AgentAppBridgeCdpAdapter(devtools_client=devtools_client)
        self._ide = AgentAppBridgeIdeExtensionAdapter(bridge_client=ide_bridge_client)
        self._agent_native = AgentAppBridgeAgentNativeAdapter(
            bridge_client=agent_native_bridge_client
        )

    def send(self, request: AgentAppBridgeRequest):
        if _endpoint_is_ide_bridge(request.endpoint):
            return self._ide.send(request)
        if _endpoint_is_agent_native_bridge(request.endpoint):
            return self._agent_native.send(request)
        return self._cdp.send(request)

    def probe_composer(self, request: AgentAppBridgeRequest):
        if _endpoint_is_devtools(request.endpoint):
            return self._cdp.probe_composer(request)
        return {}


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


def _select_matched_app_window(
    windows: object,
    *,
    project_name: str,
    task_name: str,
) -> dict:
    if not isinstance(windows, list):
        return {}
    candidates = [dict(item) for item in windows if isinstance(item, dict)]
    if not candidates:
        return {}
    queries = [
        str(project_name or "").strip().lower(),
        str(task_name or "").strip().lower(),
    ]
    queries = [query for query in queries if query]
    for query in queries:
        for window in candidates:
            title = str(window.get("window_title", "") or "").lower()
            if query in title:
                return window
    return candidates[0]


def _endpoint_summary(endpoint: dict) -> dict:
    if not endpoint:
        return {}
    summary = {
        "endpoint_type": str(endpoint.get("endpoint_type", "") or "devtools"),
        "debugger_url": str(endpoint.get("debugger_url", "") or ""),
        "bridge_url": str(endpoint.get("bridge_url", "") or ""),
        "port": int(endpoint.get("port", 0) or 0),
        "ready": bool(endpoint.get("ready", False)),
        "target_count": int(endpoint.get("target_count", 0) or len(endpoint.get("targets", []) or [])),
    }
    preferred = str(endpoint.get("preferred_chat_adapter", "") or "")
    if preferred:
        summary["preferred_chat_adapter"] = preferred
    send_command_id = str(endpoint.get("send_command_id", "") or "")
    if send_command_id:
        summary["send_command_id"] = send_command_id
    adapter_mapping = endpoint.get("adapter_mapping")
    if isinstance(adapter_mapping, dict):
        summary["adapter_mapping"] = dict(adapter_mapping)
    return summary


def _select_devtools_target(
    endpoint: dict,
    *,
    project_name: str = "",
    task_name: str = "",
) -> BrowserDevToolsTarget | None:
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
    scored = sorted(
        (
            (
                _devtools_target_match_score(
                    target,
                    project_name=project_name,
                    task_name=task_name,
                ),
                index,
                target,
            )
            for index, target in enumerate(candidates)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    if scored and scored[0][0] > 0:
        return scored[0][2]
    for target in candidates:
        if (target.type or "").lower() in {"page", "webview"}:
            return target
    return candidates[0]


def _devtools_target_match_score(
    target: BrowserDevToolsTarget,
    *,
    project_name: str = "",
    task_name: str = "",
) -> int:
    haystack = " ".join(
        str(item or "").strip().lower()
        for item in (target.title, target.url)
        if str(item or "").strip()
    )
    score = 0
    task = str(task_name or "").strip().lower()
    project = str(project_name or "").strip().lower()
    if task and task in haystack:
        score += 20
    if project and project in haystack:
        score += 10
    return score


def _remote_object_value(result: dict) -> dict:
    if not isinstance(result, dict):
        return {}
    value = result.get("value")
    if isinstance(value, dict):
        return dict(value)
    if result.get("type") == "exception":
        return {"exception": result.get("exceptionDetails") or result}
    return {"value": value}


def _bridge_composer_probe_expression() -> str:
    return (
        "(() => {"
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
        "const bodyText = document.body ? String(document.body.innerText || document.body.textContent || '') : '';"
        "const pageTitle = String(document.title || '');"
        "const pageUrl = String(location.href || '');"
        "const labelFor = (el) => String(el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || el.getAttribute('title') || el.value || el.innerText || el.textContent || '').trim();"
        "const safeChatHint = (label) => /chat|message|ask|agent|composer|prompt|plan|commands|context|send|\\u8f93\\u5165|\\u6d88\\u606f|\\u63d0\\u95ee|\\u53d1\\u9001|\\u547d\\u4ee4/i.test(label || '');"
        "const isCodeEditor = (el) => !!el.closest('.monaco-editor,.cm-editor,[data-mode-id],.editor-instance');"
        "const classText = (el) => String(el.className || '');"
        "const isCursorWorkbench = /cursor/i.test(pageTitle) && /vscode-file:\\/\\/vscode-app/i.test(pageUrl) && /New Agent|Plan, Build|commands|context/i.test(bodyText);"
        "const cursorAislashComposer = (el) => isCursorWorkbench && /(^|\\s)aislash-editor-input(\\s|$)/.test(classText(el)) && (el.getAttribute('role') === 'textbox' || el.isContentEditable || el.getAttribute('contenteditable') === 'true');"
        "const productComposerContractFor = (el) => cursorAislashComposer(el) ? 'cursor-agent-chat-aislash-editor-input' : '';"
        "const composerSelectors = ["
        "'textarea',"
        "'[contenteditable=\"true\"]',"
        "'[role=\"textbox\"]',"
        "'.aislash-editor-input',"
        "'input[type=\"text\"]',"
        "'input:not([type])'"
        "];"
        "const composers = Array.from(document.querySelectorAll(composerSelectors.join(','))).filter(visible).map((el, index) => {"
        "const rect = el.getBoundingClientRect();"
        "const label = labelFor(el);"
        "const editorLike = isCodeEditor(el);"
        "const productComposerContract = productComposerContractFor(el);"
        "const safe = (safeChatHint(label) || !!productComposerContract) && !editorLike;"
        "return {index, tag: el.tagName, role: el.getAttribute('role') || '', ariaLabel: el.getAttribute('aria-label') || '', ariaPlaceholder: el.getAttribute('aria-placeholder') || '', placeholder: el.getAttribute('placeholder') || '', title: el.getAttribute('title') || '', className: String(el.className || '').slice(0, 160), text: label.slice(0, 220), safeChatHint: safeChatHint(label), productComposerContract, isCursorAislashComposer: !!productComposerContract, editorLike, safe, rect: {x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height)}};"
        "});"
        "const safeComposers = composers.filter((item) => item.safe);"
        "const buttonSelectors = ['button', '[role=\"button\"]', 'input[type=\"submit\"]'];"
        "const buttons = Array.from(document.querySelectorAll(buttonSelectors.join(','))).filter((el) => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true');"
        "const sendButtonCandidates = buttons.map((el, index) => {"
        "const rect = el.getBoundingClientRect();"
        "const label = labelFor(el);"
        "return {index, tag: el.tagName, ariaLabel: el.getAttribute('aria-label') || '', title: el.getAttribute('title') || '', text: label.slice(0, 160), sendHint: /send|submit|run|start|\\u53d1\\u9001|\\u63d0\\u4ea4|\\u8fd0\\u884c|\\u5f00\\u59cb/i.test(label), rect: {x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height)}};"
        "}).filter((item) => item.sendHint);"
        "return {"
        "composerFound: safeComposers.length > 0,"
        "safeComposerFound: safeComposers.length > 0,"
        "composerCandidateCount: composers.length,"
        "safeComposerCandidateCount: safeComposers.length,"
        "selectedComposer: safeComposers[0] || null,"
        "composers: composers.slice(0, 40),"
        "buttonCount: buttons.length,"
        "sendButtonCandidates: sendButtonCandidates.slice(0, 20),"
        "readbackText: document.body ? document.body.innerText.slice(0, 6000) : '',"
        "documentTitle: pageTitle,"
        "pageUrl: pageUrl,"
        "readyState: document.readyState || ''"
        "};"
        "})()"
    )


def _bridge_send_expression(message: str) -> str:
    message_json = json_dumps_ascii(str(message or ""))
    return (
        "(async () => {"
        f"const message = {message_json};"
        "const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));"
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
        "const bodyText = document.body ? String(document.body.innerText || document.body.textContent || '') : '';"
        "const pageTitle = String(document.title || '');"
        "const pageUrl = String(location.href || '');"
        "const labelFor = (el) => String(el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || el.getAttribute('title') || el.value || el.innerText || el.textContent || '').trim();"
        "const safeChatHint = (label) => /chat|message|ask|agent|composer|prompt|plan|commands|context|send|\\u8f93\\u5165|\\u6d88\\u606f|\\u63d0\\u95ee|\\u53d1\\u9001|\\u547d\\u4ee4/i.test(label || '');"
        "const isCodeEditor = (el) => !!el.closest('.monaco-editor,.cm-editor,[data-mode-id],.editor-instance');"
        "const classText = (el) => String(el.className || '');"
        "const isCursorWorkbench = /cursor/i.test(pageTitle) && /vscode-file:\\/\\/vscode-app/i.test(pageUrl) && /New Agent|Plan, Build|commands|context/i.test(bodyText);"
        "const cursorAislashComposer = (el) => isCursorWorkbench && /(^|\\s)aislash-editor-input(\\s|$)/.test(classText(el)) && (el.getAttribute('role') === 'textbox' || el.isContentEditable || el.getAttribute('contenteditable') === 'true');"
        "const productComposerContractFor = (el) => cursorAislashComposer(el) ? 'cursor-agent-chat-aislash-editor-input' : '';"
        "const isLexicalEditor = (el) => el.getAttribute('data-lexical-editor') === 'true';"
        "const selectElementContents = (el) => {"
        "const range = document.createRange();"
        "range.selectNodeContents(el);"
        "const selection = window.getSelection();"
        "selection.removeAllRanges();"
        "selection.addRange(range);"
        "};"
        "const setText = (el, text) => {"
        "const value = String(text || '');"
        "if (isLexicalEditor(el)) {"
        "el.focus();"
        "selectElementContents(el);"
        "if (value) document.execCommand('insertText', false, value);"
        "else document.execCommand('delete', false, null);"
        "} else if ('value' in el) {"
        "const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')?.set;"
        "if (setter) setter.call(el, value); else el.value = value;"
        "} else {"
        "el.textContent = value;"
        "}"
        "const inputEvent = typeof InputEvent === 'function' "
        "? new InputEvent('input', {bubbles: true, composed: true, inputType: value ? 'insertText' : 'deleteContentBackward', data: value}) "
        ": new Event('input', {bubbles: true});"
        "el.dispatchEvent(inputEvent);"
        "el.dispatchEvent(new Event('change', {bubbles: true, composed: true}));"
        "};"
        "const cleanupVerified = (current, original) => current === original || (!String(current || '').trim() && !String(original || '').trim());"
        "const restoreText = async (el, targetText, originalText) => {"
        "let cleanupText = readText(el);"
        "for (let cleanupIndex = 0; cleanupIndex < 5 && !cleanupVerified(cleanupText, originalText); cleanupIndex += 1) {"
        "setText(el, targetText);"
        "await sleep(180);"
        "cleanupText = readText(el);"
        "}"
        "return {cleanupText, cleanupVerified: cleanupVerified(cleanupText, originalText)};"
        "};"
        "const composerSelectors = ["
        "'textarea',"
        "'[contenteditable=\"true\"]',"
        "'[role=\"textbox\"]',"
        "'.aislash-editor-input',"
        "'input[type=\"text\"]',"
        "'input:not([type])'"
        "];"
        "const safeComposer = (el) => visible(el) && (safeChatHint(labelFor(el)) || !!productComposerContractFor(el)) && !isCodeEditor(el);"
        "const composers = Array.from(document.querySelectorAll(composerSelectors.join(','))).filter(safeComposer);"
        "const composer = composers[0] || null;"
        "if (!composer) {"
        "return {composerFound: false, safeComposerFound: false, composerCandidateCount: 0, safeComposerCandidateCount: 0, messageSet: false, submitAttempted: false, submitVerified: false, readbackText: document.body ? document.body.innerText.slice(0, 6000) : ''};"
        "}"
        "const productComposerContract = productComposerContractFor(composer);"
        "const originalText = readText(composer);"
        "const cleanupTargetText = String(originalText || '').trim() ? originalText : '';"
        "setText(composer, message);"
        "await sleep(180);"
        "const composerText = readText(composer);"
        "const messageSet = composerText === message || composerText.includes(message);"
        "if (!messageSet) {"
        "const cleanup = await restoreText(composer, cleanupTargetText, originalText);"
        "return {composerFound: true, safeComposerFound: true, productComposerContract, composerCandidateCount: composers.length, safeComposerCandidateCount: composers.length, messageSet: false, submitAttempted: false, submitVerified: false, cleanupAttempted: true, cleanupVerified: cleanup.cleanupVerified, cleanupText: cleanup.cleanupText, readbackText: document.body ? document.body.innerText.slice(0, 6000) : ''};"
        "}"
        "const findSendButton = () => {"
        "const buttonSelectors = ['button', '[role=\"button\"]', 'input[type=\"submit\"]'];"
        "const buttons = Array.from(document.querySelectorAll(buttonSelectors.join(','))).filter((el) => visible(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true');"
        "const genericSendButton = buttons.find((el) => /send|submit|\\u53d1\\u9001|\\u63d0\\u4ea4|\\u8fd0\\u884c|\\u5f00\\u59cb/i.test(labelFor(el))) || null;"
        "const composerRect = composer.getBoundingClientRect();"
        "const cursorArrowIcon = productComposerContract ? Array.from(document.querySelectorAll('.codicon-arrow-up-two')).filter(visible).find((el) => {"
        "const rect = el.getBoundingClientRect();"
        "return rect.x >= composerRect.x && rect.y >= composerRect.y && rect.y <= composerRect.bottom + 80;"
        "}) || null : null;"
        "const cursorArrowButton = cursorArrowIcon ? (cursorArrowIcon.closest('.anysphere-icon-button,.send-with-mode,button,[role=\"button\"],a,[tabindex]') || cursorArrowIcon) : null;"
        "return {sendButton: genericSendButton || cursorArrowButton, cursorArrowButton};"
        "};"
        "let sendButton = null;"
        "let cursorArrowButton = null;"
        "for (let submitWaitIndex = 0; submitWaitIndex < 6 && !sendButton; submitWaitIndex += 1) {"
        "const candidate = findSendButton();"
        "sendButton = candidate.sendButton;"
        "cursorArrowButton = candidate.cursorArrowButton;"
        "if (!sendButton) await sleep(180);"
        "}"
        "if (!sendButton) {"
        "const cleanup = await restoreText(composer, cleanupTargetText, originalText);"
        "return {composerFound: true, safeComposerFound: true, productComposerContract, composerCandidateCount: composers.length, safeComposerCandidateCount: composers.length, messageSet, submitAttempted: false, submitVerified: false, cleanupAttempted: true, cleanupVerified: cleanup.cleanupVerified, cleanupText: cleanup.cleanupText, readbackText: document.body ? document.body.innerText.slice(0, 6000) : ''};"
        "}"
        "sendButton.click();"
        "await sleep(1200);"
        "const postComposerText = readText(composer);"
        "const submitVerified = !postComposerText.includes(message);"
        "const readbackText = document.body ? document.body.innerText.slice(0, 6000) : '';"
        "return {"
        "composerFound: true,"
        "safeComposerFound: true,"
        "productComposerContract,"
        "composerCandidateCount: composers.length,"
        "safeComposerCandidateCount: composers.length,"
        "messageSet,"
        "submitAttempted: true,"
        "submitVerified,"
        "postComposerText,"
        "sendButtonLabel: labelFor(sendButton),"
        "sendButtonClassName: String(sendButton.className || ''),"
        "sendButtonContract: cursorArrowButton ? 'cursor-arrow-up-two-submit' : 'generic-send-button',"
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


def _endpoint_is_ide_bridge(endpoint: dict) -> bool:
    return str(endpoint.get("endpoint_type", "") or "").strip() == "ide_bridge"


def _endpoint_is_agent_native_bridge(endpoint: dict) -> bool:
    return str(endpoint.get("endpoint_type", "") or "").strip() == "agent_native_bridge"


def _endpoint_is_devtools(endpoint: dict) -> bool:
    return str(endpoint.get("endpoint_type", "") or "devtools").strip() == "devtools"


def _endpoint_supports_ide_chat(endpoint: dict, agent_id: str = "") -> bool:
    if not _endpoint_is_ide_bridge(endpoint):
        return False
    if not bool(endpoint.get("ready", False)):
        return False
    normalized_agent = str(agent_id or "").strip().lower()
    preferred = str(endpoint.get("preferred_chat_adapter", "") or "").strip()
    if preferred:
        return not normalized_agent or preferred.lower() == normalized_agent
    adapter_mapping = endpoint.get("adapter_mapping")
    if isinstance(adapter_mapping, dict):
        if normalized_agent:
            item = adapter_mapping.get(normalized_agent)
            if isinstance(item, dict):
                command_id = str(item.get("commandId", "") or item.get("command_id", "") or "").strip()
                return bool(command_id and item.get("available", False))
            return False
        for item in adapter_mapping.values():
            if not isinstance(item, dict):
                continue
            command_id = str(item.get("commandId", "") or item.get("command_id", "") or "").strip()
            if command_id and bool(item.get("available", False)):
                return True
    if str(endpoint.get("send_command_id", "") or "").strip():
        return not normalized_agent
    return False


def _endpoint_supports_agent_native_bridge(endpoint: dict, agent_id: str = "") -> bool:
    if not _endpoint_is_agent_native_bridge(endpoint):
        return False
    if not bool(endpoint.get("ready", False)):
        return False
    metadata = endpoint.get("metadata")
    if not isinstance(metadata, dict):
        return False
    if _normalize_surface_kind(metadata.get("surface_kind", "")) != "desktop_app":
        return False
    if not _endpoint_agent_native_app_binding_matches(metadata, agent_id):
        return False
    normalized_agent = str(agent_id or "").strip().lower()
    preferred = str(endpoint.get("preferred_chat_adapter", "") or "").strip().lower()
    if normalized_agent and preferred and preferred != normalized_agent:
        return False
    if normalized_agent:
        metadata_agent = str(metadata.get("agent_id", "") or "").strip().lower()
        if metadata_agent and metadata_agent != normalized_agent:
            return False
    return bool(str(endpoint.get("send_command_id", "") or "").strip() == AGENT_NATIVE_SEND_ACTION)


def _endpoint_supports_app_devtools(endpoint: dict, agent_id: str = "") -> bool:
    if not _endpoint_is_devtools(endpoint):
        return False
    if not bool(endpoint.get("ready", False)):
        return False
    if not str(endpoint.get("debugger_url", "") or "").strip():
        return False
    if _select_devtools_target(endpoint) is None:
        return False
    return _endpoint_devtools_app_binding_matches(endpoint, agent_id)


def _endpoint_devtools_app_binding_matches(endpoint: dict, agent_id: str) -> bool:
    expected_names = {
        _normalize_process_name(name)
        for name in _agent_process_names(agent_id)
        if _normalize_process_name(name)
    }
    candidates: list[dict] = []
    process = endpoint.get("process")
    if isinstance(process, dict):
        candidates.append(process)
    metadata = endpoint.get("metadata")
    if isinstance(metadata, dict):
        for key in ("app_binding", "desktop_app_binding", "target_app"):
            binding = metadata.get(key)
            if isinstance(binding, dict):
                candidates.append(binding)
    for binding in candidates:
        actual_name = _binding_process_name(binding)
        if expected_names:
            if actual_name in expected_names:
                return True
            continue
        if actual_name:
            return True
    return False


def _endpoint_agent_native_app_binding_matches(metadata: dict, agent_id: str) -> bool:
    binding = metadata.get("app_binding")
    if not isinstance(binding, dict) or not binding:
        return False
    expected_names = {
        _normalize_process_name(name)
        for name in _agent_process_names(agent_id)
        if _normalize_process_name(name)
    }
    actual_name = _binding_process_name(binding)
    if expected_names and actual_name not in expected_names:
        return False
    return bool(
        actual_name
        or _int_value(binding, "pid")
        or _int_value(binding, "hwnd")
        or str(binding.get("window_title", "") or binding.get("title", "") or "").strip()
    )


def _endpoint_matches_project(endpoint: dict, project_name: str) -> bool:
    project = str(project_name or "").strip().lower()
    if not project:
        return True
    if _endpoint_targets_match_query(endpoint, project):
        return True
    metadata = endpoint.get("metadata")
    if not isinstance(metadata, dict):
        return False
    haystack: list[str] = []
    for key in ("project_name", "project", "workspace", "workspace_path"):
        haystack.append(str(metadata.get(key, "") or ""))
    for collection_key in ("projects", "workspaces", "workspaceFolders"):
        items = metadata.get(collection_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            haystack.extend(
                [
                    str(item.get("name", "") or ""),
                    str(item.get("project_name", "") or ""),
                    str(item.get("fsPath", "") or ""),
                    str(item.get("path", "") or ""),
                    str(item.get("uri", "") or ""),
                ]
            )
    folders = metadata.get("workspaceFolders")
    if isinstance(folders, list):
        for folder in folders:
            if not isinstance(folder, dict):
                continue
            haystack.extend(
                [
                    str(folder.get("name", "") or ""),
                    str(folder.get("fsPath", "") or ""),
                    str(folder.get("uri", "") or ""),
                ]
            )
    active_editor = metadata.get("activeTextEditor")
    if isinstance(active_editor, dict):
        haystack.extend(
            [
                str(active_editor.get("fsPath", "") or ""),
                str(active_editor.get("uri", "") or ""),
            ]
        )
    return any(project in text.lower().replace("\\", "/") for text in haystack if text)


def _endpoint_matches_task(endpoint: dict, task_name: str) -> bool:
    task = str(task_name or "").strip().lower()
    if not task:
        return True
    if _endpoint_targets_match_query(endpoint, task):
        return True
    if _endpoint_is_ide_bridge(endpoint):
        return True
    metadata = endpoint.get("metadata")
    if not isinstance(metadata, dict):
        return False
    haystack: list[str] = [
        str(metadata.get("task_name", "") or ""),
        str(metadata.get("task", "") or ""),
        str(metadata.get("session", "") or ""),
        str(metadata.get("conversation", "") or ""),
    ]
    for collection_key in ("tasks", "sessions", "conversations"):
        items = metadata.get(collection_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            haystack.extend(
                [
                    str(item.get("name", "") or ""),
                    str(item.get("task_name", "") or ""),
                    str(item.get("title", "") or ""),
                    str(item.get("id", "") or ""),
                    str(item.get("session_id", "") or ""),
                ]
            )
    return any(task in text.lower() for text in haystack if text)


def _endpoint_targets_match_query(endpoint: dict, query: str) -> bool:
    needle = str(query or "").strip().lower()
    if not needle:
        return True
    targets = endpoint.get("targets")
    if not isinstance(targets, list):
        return False
    for target in targets:
        if not isinstance(target, dict):
            continue
        haystack = " ".join(
            str(target.get(key, "") or "")
            for key in ("title", "url", "target_id", "id")
        ).lower()
        if needle in haystack:
            return True
    return False


def _select_ide_chat_adapter(endpoint: dict, agent_id: str) -> str:
    preferred = str(endpoint.get("preferred_chat_adapter", "") or "").strip()
    normalized_agent = str(agent_id or "").strip().lower()
    if preferred:
        if normalized_agent and preferred.lower() != normalized_agent:
            return ""
        return preferred
    adapter_mapping = endpoint.get("adapter_mapping")
    if isinstance(adapter_mapping, dict):
        if normalized_agent:
            item = adapter_mapping.get(normalized_agent)
            if isinstance(item, dict) and bool(item.get("available", False)):
                command_id = str(item.get("commandId", "") or item.get("command_id", "") or "").strip()
                if command_id:
                    return normalized_agent
            return ""
        for key, item in adapter_mapping.items():
            if not isinstance(item, dict):
                continue
            command_id = str(item.get("commandId", "") or item.get("command_id", "") or "").strip()
            if str(key).strip() and command_id and bool(item.get("available", False)):
                return str(key).strip()
    return ""


def _connector_target_from_request(request: AgentAppBridgeRequest) -> ConnectorTarget:
    target = request.target
    endpoint = request.endpoint
    metadata = endpoint.get("metadata")
    workspace_path = ""
    if isinstance(metadata, dict):
        folders = metadata.get("workspaceFolders")
        if isinstance(folders, list) and folders and isinstance(folders[0], dict):
            workspace_path = str(folders[0].get("fsPath", "") or "")
    return ConnectorTarget(
        pid=int(target.get("pid", 0) or 0),
        process_name=str(target.get("process_name", "") or ""),
        window_title=str(target.get("window_title", "") or ""),
        project_name=request.project_name,
        workspace_path=workspace_path,
        ide_bridge_url=str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or ""),
    )


def _ide_bridge_action_result(data: dict, *, bridge_url: str, adapter_id: str) -> dict:
    if not isinstance(data, dict):
        data = {}
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    command_id = str(metadata.get("command_id", "") or "")
    returned_adapter = str(metadata.get("adapter_id", "") or adapter_id)
    conversation = str(data.get("conversation", "") or "")
    return {
        "bridgeOk": bool(data.get("ok", False)),
        "messageSet": bool(data.get("ok", False)),
        "submitAttempted": bool(data.get("ok", False)),
        "submitVerified": bool(data.get("ok", False)),
        "readbackText": conversation,
        "conversation": conversation,
        "bridge_url": bridge_url,
        "adapter_id": returned_adapter,
        "command_id": command_id,
        "response": dict(data),
    }


def _agent_native_bridge_action_result(data: dict, *, bridge_url: str, agent_id: str) -> dict:
    if not isinstance(data, dict):
        data = {}
    action_result = data.get("action_result")
    if not isinstance(action_result, dict):
        action_result = {}
    bridge_ok = bool(
        action_result.get("ok", False)
        or action_result.get("sent", False)
        or str(data.get("decision", "") or "") == "agent_native_bridge_send_accepted"
    )
    return {
        "bridgeOk": bridge_ok,
        "messageSet": bridge_ok,
        "submitAttempted": bool(data.get("native_call_attempts", 0) or bridge_ok),
        "submitVerified": bridge_ok,
        "readbackText": _first_text(
            action_result,
            "readbackText",
            "readback_text",
            "conversation",
            "transcript",
            "text",
        ),
        "conversation": _first_text(
            action_result,
            "conversation",
            "transcript",
            "readbackText",
            "readback_text",
            "text",
        ),
        "bridge_url": bridge_url,
        "agent_id": agent_id,
        "window_input_attempts": _int_value(action_result, "window_input_attempts"),
        "keyboard_input_attempts": _int_value(action_result, "keyboard_input_attempts"),
        "clipboard_write_attempts": _int_value(action_result, "clipboard_write_attempts"),
        "foreground_focus_stable": action_result.get("foreground_focus_stable", True),
        "response": dict(data),
    }


def _ide_bridge_target_to_dict(endpoint: dict, action_result: dict) -> dict:
    return {
        "endpoint_type": "ide_bridge",
        "bridge_url": str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or ""),
        "adapter_id": str(action_result.get("adapter_id", "") or endpoint.get("preferred_chat_adapter", "") or ""),
        "command_id": str(action_result.get("command_id", "") or ""),
    }


def _agent_native_bridge_target_to_dict(endpoint: dict, action_result: dict) -> dict:
    return {
        "endpoint_type": "agent_native_bridge",
        "bridge_url": str(endpoint.get("bridge_url", "") or endpoint.get("debugger_url", "") or ""),
        "agent_id": str(action_result.get("agent_id", "") or endpoint.get("preferred_chat_adapter", "") or ""),
        "command_id": str(endpoint.get("send_command_id", "") or ""),
    }


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


def _request_target_pids(request: AgentAppBridgeRequest) -> tuple[int, ...]:
    value = _int_value(request.target, "pid")
    return (value,) if value > 0 else ()


def _request_target_hwnds(request: AgentAppBridgeRequest) -> tuple[int, ...]:
    value = _int_value(request.target, "hwnd")
    return (value,) if value > 0 else ()


def _agent_process_names(agent_id: str) -> tuple[str, ...]:
    normalized = str(agent_id or "").strip().casefold()
    if normalized == "codex":
        return ("codex.exe",)
    if normalized == "claude":
        return ("claude.exe",)
    if normalized == "cursor":
        return ("cursor.exe",)
    return (normalized,) if normalized else ()


def _binding_process_name(binding: dict) -> str:
    for key in ("process_name", "processName", "executable_name", "executableName"):
        value = _normalize_process_name(binding.get(key, ""))
        if value:
            return value
    for key in ("executable_path", "executablePath", "path"):
        value = _normalize_process_name(binding.get(key, ""))
        if value:
            return value
    return ""


def _normalize_process_name(value: object) -> str:
    text = str(value or "").strip().casefold().replace("\\", "/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _normalize_surface_kind(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


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
    "AgentAppBridgeAgentNativeAdapter",
    "AgentAppBridgeAgentNativeSendReport",
    "AgentAppBridgeCdpAdapter",
    "AgentAppBridgeCdpComposerProbeReport",
    "AgentAppBridgeDryRunAdapter",
    "AgentAppBridgeDryRunReport",
    "AgentAppBridgeIdeExtensionAdapter",
    "AgentAppBridgeIdeExtensionSendReport",
    "AgentAppBridgeNativeAdapter",
    "AgentAppBridgeRequest",
    "AgentAppBridgeSendReport",
    "build_agent_app_bridge_request",
]
