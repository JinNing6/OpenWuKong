# -*- coding: utf-8 -*-
"""Dry-run contract for Codex app-server turn submission."""

from __future__ import annotations

import dataclasses
import ctypes
import json
import sys
import threading
import time
import uuid
from ctypes import wintypes
from pathlib import Path


CODEX_APP_SERVER_TURN_SCHEMA_VERSION = "codex-app-server-turn-v1"


@dataclasses.dataclass(frozen=True)
class CodexAppServerTurnRequest:
    agent: str
    project_name: str
    task_name: str
    message: str
    composed_message: str
    selected_transport: dict
    app_surface_probe: dict
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    workspace_path: str = ""
    request_id: str = dataclasses.field(
        default_factory=lambda: f"cast-{uuid.uuid4().hex[:16]}"
    )

    @property
    def mode(self) -> str:
        return "codex-app-server-turn-request"

    @property
    def schema_version(self) -> str:
        return CODEX_APP_SERVER_TURN_SCHEMA_VERSION

    @property
    def agent_id(self) -> str:
        return str(
            self.app_surface_probe.get("agent_id", "") or _agent_id_from_name(self.agent)
        ).strip()

    @property
    def endpoint(self) -> dict:
        endpoints = self.app_surface_probe.get("endpoints")
        if not isinstance(endpoints, list):
            return {}
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                continue
            if (
                str(endpoint.get("endpoint_type", "") or "").strip()
                == "codex_app_server_ws"
                and bool(endpoint.get("ready", False))
            ):
                return dict(endpoint)
        return {}

    @property
    def endpoint_ready(self) -> bool:
        endpoint = self.endpoint
        metadata = _dict_value(endpoint.get("metadata"))
        return bool(
            self.agent_id == "codex"
            and endpoint
            and bool(endpoint.get("ready", False))
            and bool(metadata.get("thread_api_ready", False))
        )

    @property
    def endpoint_metadata(self) -> dict:
        metadata = _dict_value(self.endpoint.get("metadata"))
        return metadata

    @property
    def observed_threads(self) -> tuple[dict, ...]:
        value = self.endpoint_metadata.get("observed_threads")
        if not isinstance(value, list):
            return ()
        return tuple(dict(item) for item in value if isinstance(item, dict))

    @property
    def selected_thread_id(self) -> str:
        return str(self.endpoint_metadata.get("selected_thread_id", "") or "").strip()

    @property
    def selected_thread_cwd(self) -> str:
        return str(self.endpoint_metadata.get("selected_thread_cwd", "") or "").strip()

    @property
    def selected_thread(self) -> dict:
        if not self.selected_thread_id and not self.selected_thread_cwd:
            return {}
        return {
            "id": self.selected_thread_id,
            "cwd": self.selected_thread_cwd,
            "preview": str(self.endpoint_metadata.get("selected_thread_preview", "") or ""),
        }

    @property
    def matched_thread(self) -> dict:
        if self.force_fresh_thread_start:
            return {}
        for thread in self.observed_threads:
            if _thread_matches_request(thread, self):
                return dict(thread)
        selected = self.selected_thread
        if selected and _thread_matches_request(selected, self):
            return selected
        return {}

    @property
    def thread_id(self) -> str:
        return str(self.matched_thread.get("id", "") or "").strip()

    @property
    def matched_thread_cwd(self) -> str:
        return str(self.matched_thread.get("cwd", "") or "").strip()

    @property
    def thread_start_required(self) -> bool:
        return bool(
            self.endpoint_ready
            and (self.force_fresh_thread_start or not self.matched_thread)
            and str(self.workspace_path or "").strip()
        )

    @property
    def turn_start_ready(self) -> bool:
        return bool(
            self.endpoint_ready
            and self.thread_id
            and self.turn_start_foreground_safe
            and self.text
            and self.required_markers
            and _workspace_matches_request(self)
        )

    @property
    def thread_start_ready(self) -> bool:
        return bool(
            self.endpoint_ready
            and self.thread_start_required
            and str(self.workspace_path or "").strip()
            and self.text
            and self.required_markers
        )

    @property
    def cwd(self) -> str:
        explicit = str(self.workspace_path or "").strip()
        if explicit:
            return explicit
        return self.selected_thread_cwd

    @property
    def force_fresh_thread_start(self) -> bool:
        return bool(_metadata_bool(self.endpoint_metadata, "force_fresh_thread_start"))

    @property
    def text(self) -> str:
        return str(self.composed_message or self.message or "").strip()

    @property
    def turn_start_params(self) -> dict:
        params = {
            "threadId": self.thread_id,
            "input": [{"type": "text", "text": self.text}],
            "clientUserMessageId": self.request_id,
            "approvalPolicy": "never",
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        }
        cwd = self.cwd
        if cwd:
            params["cwd"] = cwd
        return params

    @property
    def turn_start_foreground_safe(self) -> bool:
        metadata = self.endpoint_metadata
        if _endpoint_turn_start_forced_block_reason(metadata):
            return False
        value = metadata.get("turn_start_foreground_safe")
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes"}
        return False

    @property
    def turn_start_block_reason(self) -> str:
        metadata = self.endpoint_metadata
        forced = _endpoint_turn_start_forced_block_reason(metadata)
        if forced:
            return forced
        if self.turn_start_foreground_safe:
            return ""
        surface_kind = str(metadata.get("surface_kind", "") or "").strip().lower()
        platform_os = str(metadata.get("platform_os", "") or "").strip().lower()
        user_agent = str(metadata.get("user_agent", "") or "").strip().lower()
        if _metadata_is_owned_ephemeral_app_server(metadata):
            return "turn_start_foreground_safety_unproven"
        if (
            surface_kind == "desktop_app"
            or platform_os == "windows"
            or "codex desktop" in user_agent
        ):
            return "windows_desktop_app_server_turn_start_foreground_risk"
        return "turn_start_foreground_safety_unproven"

    @property
    def thread_start_params(self) -> dict:
        cwd = str(self.workspace_path or "").strip()
        if not cwd:
            return {}
        return {
            "cwd": cwd,
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "threadSource": "user",
        }

    @property
    def payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "action": "codex.app_server.turn_start",
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "message": self.message,
            "composed_message": self.composed_message,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "thread_start_required": self.thread_start_required,
            "thread_start_params": self.thread_start_params,
            "turn_start_foreground_safe": self.turn_start_foreground_safe,
            "turn_start_block_reason": self.turn_start_block_reason,
            "turn_start_params": self.turn_start_params,
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "ready": _request_ready(self),
            "agent": self.agent,
            "agent_id": self.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "selected_transport": dict(self.selected_transport),
            "endpoint_ready": self.endpoint_ready,
            "thread_id": self.thread_id,
            "cwd": self.cwd,
            "endpoint": _endpoint_summary(self.endpoint),
            "thread_start_required": self.thread_start_required,
            "thread_start_ready": self.thread_start_ready,
            "turn_start_ready": self.turn_start_ready,
            "turn_start_foreground_safe": self.turn_start_foreground_safe,
            "turn_start_block_reason": self.turn_start_block_reason,
            "thread_start_params": self.thread_start_params,
            "turn_start_params": self.turn_start_params,
            "payload": self.payload,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "diagnostics": {
                "app_surface_decision": str(
                    self.app_surface_probe.get("decision", "") or ""
                ),
                "endpoint_count": int(
                    self.app_surface_probe.get("endpoint_count", 0) or 0
                ),
                "ready_endpoint_count": int(
                    self.app_surface_probe.get("ready_endpoint_count", 0) or 0
                ),
                "selected_thread_cwd": self.selected_thread_cwd,
                "matched_thread_id": self.thread_id,
                "matched_thread_cwd": self.matched_thread_cwd,
                "requested_workspace_path": str(self.workspace_path or "").strip(),
                "workspace_match": _workspace_matches_request(self),
                "turn_start_foreground_safe": self.turn_start_foreground_safe,
                "turn_start_block_reason": self.turn_start_block_reason,
            },
        }


@dataclasses.dataclass(frozen=True)
class CodexAppServerTurnDryRunReport:
    request: CodexAppServerTurnRequest
    validation_errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "codex-app-server-turn-dry-run"

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
    def native_call_attempts(self) -> int:
        return 0

    @property
    def app_server_turn_start_attempts(self) -> int:
        return 0

    @property
    def app_server_thread_start_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return not self.validation_errors

    @property
    def decision(self) -> str:
        if "agent_not_codex" in self.validation_errors:
            return "codex_app_server_agent_not_codex"
        if "message_required" in self.validation_errors:
            return "codex_app_server_message_required"
        if "endpoint_not_ready" in self.validation_errors:
            return "codex_app_server_endpoint_not_ready"
        if "thread_id_missing" in self.validation_errors:
            return "codex_app_server_thread_id_missing"
        if "workspace_mismatch" in self.validation_errors:
            return "codex_app_server_workspace_mismatch"
        if "thread_start_workspace_missing" in self.validation_errors:
            return "codex_app_server_thread_start_workspace_missing"
        if "turn_start_foreground_risk" in self.validation_errors:
            return "codex_app_server_turn_start_foreground_risk"
        if "required_marker_missing" in self.validation_errors:
            return "codex_app_server_required_marker_missing"
        if self.validation_errors:
            return "codex_app_server_turn_request_invalid"
        if self.request.thread_start_required:
            return "codex_app_server_thread_start_dry_run_ready"
        return "codex_app_server_turn_dry_run_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "native_call_attempts": self.native_call_attempts,
            "app_server_thread_start_attempts": self.app_server_thread_start_attempts,
            "app_server_turn_start_attempts": self.app_server_turn_start_attempts,
            "thread_start_required": self.request.thread_start_required,
            "thread_start_ready": self.request.thread_start_ready,
            "turn_start_ready": self.request.turn_start_ready,
            "validation_errors": list(self.validation_errors),
            "request": self.request.to_dict(),
        }


@dataclasses.dataclass(frozen=True)
class CodexAppServerThreadStartExecutionReport:
    dry_run: dict
    thread_start_response: dict = dataclasses.field(default_factory=dict)
    thread_list_response: dict = dataclasses.field(default_factory=dict)
    notifications: tuple[dict, ...] = ()
    system_dialog_snapshots: tuple[dict, ...] = ()
    request_attempts: int = 0
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    foreground_snapshot_before: dict = dataclasses.field(default_factory=dict)
    foreground_snapshot_after: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "codex-app-server-thread-start-execution"

    @property
    def safety_mode(self) -> str:
        return "native_app_server_execute"

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
    def app_server_thread_start_attempts(self) -> int:
        return 1 if int(self.request_attempts or 0) > 0 else 0

    @property
    def native_call_attempts(self) -> int:
        return self.app_server_thread_start_attempts

    @property
    def foreground_focus_stable(self) -> bool:
        before = int(self.foreground_hwnd_before or 0)
        after = int(self.foreground_hwnd_after or 0)
        return bool(not before or not after or before == after)

    @property
    def foreground_change_classification(self) -> str:
        return _classify_foreground_change(
            self.foreground_snapshot_before,
            self.foreground_snapshot_after,
        )

    @property
    def foreground_no_steal_verified(self) -> bool:
        return self.foreground_change_classification in {
            "stable",
            "changed_to_unrelated_surface",
        }

    @property
    def foreground_system_dialog_detected(self) -> bool:
        return self.foreground_change_classification == "changed_to_system_dialog"

    @property
    def system_dialog_detected(self) -> bool:
        return any(
            _system_dialog_detected(snapshot)
            for snapshot in self.system_dialog_snapshots
            if isinstance(snapshot, dict)
        )

    @property
    def request(self) -> dict:
        return _dict_value(self.dry_run.get("request"))

    @property
    def endpoint_url(self) -> str:
        endpoint = _dict_value(self.request.get("endpoint"))
        return str(
            endpoint.get("bridge_url", "")
            or endpoint.get("debugger_url", "")
            or ""
        ).strip()

    @property
    def thread_start_params(self) -> dict:
        return _dict_value(self.request.get("thread_start_params"))

    @property
    def thread_start_block_reason(self) -> str:
        endpoint = _dict_value(self.request.get("endpoint"))
        return str(endpoint.get("thread_start_block_reason", "") or "").strip()

    @property
    def requested_workspace_path(self) -> str:
        return str(self.thread_start_params.get("cwd", "") or "").strip()

    @property
    def thread(self) -> dict:
        return _thread_from_thread_start_response(self.thread_start_response)

    @property
    def observed_threads(self) -> tuple[dict, ...]:
        return _threads_from_thread_list_response(self.thread_list_response)

    @property
    def notification_threads(self) -> tuple[dict, ...]:
        return _threads_from_thread_started_notifications(self.notifications)

    @property
    def thread_verified_in_list(self) -> bool:
        thread = self.thread
        if not thread:
            return False
        thread_id = str(thread.get("id", "") or "").strip()
        for observed in self.observed_threads:
            if thread_id and str(observed.get("id", "") or "").strip() == thread_id:
                return True
            if _thread_matches_workspace_text(observed, self.requested_workspace_path):
                return True
        return False

    @property
    def thread_verified_by_notification(self) -> bool:
        thread = self.thread
        if not thread:
            return False
        thread_id = str(thread.get("id", "") or "").strip()
        for observed in self.notification_threads:
            if thread_id and str(observed.get("id", "") or "").strip() != thread_id:
                continue
            if _thread_matches_workspace_text(observed, self.requested_workspace_path):
                return True
        return False

    @property
    def ok(self) -> bool:
        return self.decision == "codex_app_server_thread_start_verified"

    @property
    def decision(self) -> str:
        if not bool(self.dry_run.get("ok", False)):
            return "codex_app_server_thread_start_dry_run_not_ready"
        if not bool(self.dry_run.get("thread_start_required", False)):
            return "codex_app_server_thread_start_not_required"
        if not self.endpoint_url:
            return "codex_app_server_thread_start_endpoint_url_missing"
        if self.thread_start_block_reason:
            return "codex_app_server_thread_start_foreground_risk"
        if self.system_dialog_detected or self.foreground_system_dialog_detected:
            return "codex_app_server_thread_start_system_dialog_detected"
        if self.error:
            return "codex_app_server_thread_start_failed"
        if not self.foreground_no_steal_verified:
            return "codex_app_server_thread_start_foreground_changed"
        if not self.thread:
            return "codex_app_server_thread_start_response_invalid"
        if not _thread_matches_workspace_text(self.thread, self.requested_workspace_path):
            return "codex_app_server_thread_start_workspace_mismatch"
        if not (
            self.thread_verified_in_list or self.thread_verified_by_notification
        ):
            return "codex_app_server_thread_start_list_verification_failed"
        return "codex_app_server_thread_start_verified"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "native_call_attempts": self.native_call_attempts,
            "app_server_thread_start_attempts": self.app_server_thread_start_attempts,
            "request_attempts": int(self.request_attempts or 0),
            "foreground_hwnd_before": int(self.foreground_hwnd_before or 0),
            "foreground_hwnd_after": int(self.foreground_hwnd_after or 0),
            "foreground_focus_stable": self.foreground_focus_stable,
            "foreground_snapshot_before": dict(self.foreground_snapshot_before),
            "foreground_snapshot_after": dict(self.foreground_snapshot_after),
            "foreground_change_classification": self.foreground_change_classification,
            "foreground_no_steal_verified": self.foreground_no_steal_verified,
            "system_dialog_detected": self.system_dialog_detected,
            "system_dialog_snapshots": [
                dict(item) for item in self.system_dialog_snapshots
            ],
            "endpoint_url": self.endpoint_url,
            "thread_start_block_reason": self.thread_start_block_reason,
            "thread_start_params": self.thread_start_params,
            "thread": self.thread,
            "observed_threads": [dict(item) for item in self.observed_threads],
            "notification_threads": [
                dict(item) for item in self.notification_threads
            ],
            "thread_verified_in_list": self.thread_verified_in_list,
            "thread_verified_by_notification": self.thread_verified_by_notification,
            "thread_start_response": dict(self.thread_start_response),
            "thread_list_response": dict(self.thread_list_response),
            "notifications": [dict(item) for item in self.notifications],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "dry_run": dict(self.dry_run),
        }


@dataclasses.dataclass(frozen=True)
class CodexAppServerTurnStartExecutionReport:
    dry_run: dict
    windows_sandbox_readiness_response: dict = dataclasses.field(default_factory=dict)
    turn_start_response: dict = dataclasses.field(default_factory=dict)
    notifications: tuple[dict, ...] = ()
    session_readback_text: str = ""
    session_task_complete_seen: bool = False
    session_artifact_path: str = ""
    system_dialog_snapshots: tuple[dict, ...] = ()
    request_attempts: int = 0
    foreground_hwnd_before: int = 0
    foreground_hwnd_after: int = 0
    foreground_snapshot_before: dict = dataclasses.field(default_factory=dict)
    foreground_snapshot_after: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "codex-app-server-turn-start-execution"

    @property
    def safety_mode(self) -> str:
        return "native_app_server_execute"

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
    def app_server_turn_start_attempts(self) -> int:
        return 1 if bool(self.turn_start_response) else 0

    @property
    def app_server_readiness_attempts(self) -> int:
        return 1 if bool(self.windows_sandbox_readiness_response) else 0

    @property
    def app_server_thread_start_attempts(self) -> int:
        return 0

    @property
    def native_call_attempts(self) -> int:
        return self.app_server_readiness_attempts + self.app_server_turn_start_attempts

    @property
    def foreground_focus_stable(self) -> bool:
        before = int(self.foreground_hwnd_before or 0)
        after = int(self.foreground_hwnd_after or 0)
        return bool(not before or not after or before == after)

    @property
    def foreground_change_classification(self) -> str:
        return _classify_foreground_change(
            self.foreground_snapshot_before,
            self.foreground_snapshot_after,
        )

    @property
    def foreground_no_steal_verified(self) -> bool:
        return self.foreground_change_classification in {
            "stable",
            "changed_to_unrelated_surface",
        }

    @property
    def foreground_system_dialog_detected(self) -> bool:
        return self.foreground_change_classification == "changed_to_system_dialog"

    @property
    def request(self) -> dict:
        return _dict_value(self.dry_run.get("request"))

    @property
    def endpoint_url(self) -> str:
        endpoint = _dict_value(self.request.get("endpoint"))
        return str(
            endpoint.get("bridge_url", "")
            or endpoint.get("debugger_url", "")
            or ""
        ).strip()

    @property
    def turn_start_params(self) -> dict:
        return _dict_value(self.request.get("turn_start_params"))

    @property
    def thread_id(self) -> str:
        return str(self.turn_start_params.get("threadId", "") or "").strip()

    @property
    def required_markers(self) -> tuple[str, ...]:
        return _string_tuple(self.request.get("required_markers"))

    @property
    def forbidden_markers(self) -> tuple[str, ...]:
        return _string_tuple(self.request.get("forbidden_markers"))

    @property
    def turn(self) -> dict:
        completed = self.completed_turn
        if completed:
            return completed
        turn = _turn_from_turn_start_response(self.turn_start_response)
        if self.session_task_complete_seen:
            return {
                "id": str(turn.get("id", "") or "").strip(),
                "status": "completed",
                "error": _dict_value(turn.get("error")),
            }
        return turn

    @property
    def turn_id(self) -> str:
        completed = self.completed_turn
        turn_id = str(completed.get("id", "") or "").strip()
        if turn_id:
            return turn_id
        turn = _turn_from_turn_start_response(self.turn_start_response)
        turn_id = str(turn.get("id", "") or "").strip()
        if turn_id:
            return turn_id
        for notification in self.notifications:
            params = _notification_params(notification)
            value = str(params.get("turnId", "") or "").strip()
            if value:
                return value
        return ""

    @property
    def turn_status(self) -> str:
        return str(self.turn.get("status", "") or "").strip()

    @property
    def completed_turn(self) -> dict:
        return _completed_turn_from_notifications(self.notifications)

    @property
    def turn_completed(self) -> bool:
        return bool(
            (self.completed_turn and self.turn_status == "completed")
            or self.session_task_complete_seen
        )

    @property
    def assistant_readback_text(self) -> str:
        return (
            _assistant_readback_text(self.notifications)
            + str(self.session_readback_text or "")
        )

    @property
    def windows_sandbox_readiness_status(self) -> str:
        result = _dict_value(self.windows_sandbox_readiness_response.get("result"))
        return str(result.get("status", "") or "").strip()

    @property
    def windows_sandbox_ready(self) -> bool:
        status = self.windows_sandbox_readiness_status
        return bool(not status or status == "ready")

    @property
    def system_dialog_detected(self) -> bool:
        return any(
            _system_dialog_detected(snapshot)
            for snapshot in self.system_dialog_snapshots
            if isinstance(snapshot, dict)
        )

    @property
    def sandbox_error_texts(self) -> tuple[str, ...]:
        values: list[str] = []
        if self.error:
            values.append(str(self.error))
        values.extend(_extract_all_strings(self.turn_start_response))
        values.extend(_extract_all_strings(self.notifications))
        return tuple(dict.fromkeys(value for value in values if _looks_like_sandbox_error(value)))

    @property
    def sandbox_setup_failed(self) -> bool:
        haystack = "\n".join(self.sandbox_error_texts).casefold()
        return bool(
            "spawn setup refresh" in haystack
            or "windows sandbox" in haystack
            or "sandboxerror" in haystack
            or "sandbox error" in haystack
        )

    @property
    def missing_required_markers(self) -> tuple[str, ...]:
        text = self.assistant_readback_text
        return tuple(marker for marker in self.required_markers if marker not in text)

    @property
    def seen_forbidden_markers(self) -> tuple[str, ...]:
        text = self.assistant_readback_text
        return tuple(marker for marker in self.forbidden_markers if marker in text)

    @property
    def ok(self) -> bool:
        return self.decision == "codex_app_server_turn_start_verified"

    @property
    def decision(self) -> str:
        if not bool(self.dry_run.get("ok", False)):
            return "codex_app_server_turn_start_dry_run_not_ready"
        if (
            str(self.dry_run.get("decision", "") or "")
            != "codex_app_server_turn_dry_run_ready"
            or not bool(self.dry_run.get("turn_start_ready", False))
        ):
            return "codex_app_server_turn_start_dry_run_not_ready"
        if not self.endpoint_url:
            return "codex_app_server_turn_start_endpoint_url_missing"
        if not self.thread_id:
            return "codex_app_server_turn_start_thread_id_missing"
        if self.system_dialog_detected or self.foreground_system_dialog_detected:
            return "codex_app_server_turn_start_system_dialog_detected"
        if not self.windows_sandbox_ready:
            return "codex_app_server_turn_start_windows_sandbox_not_ready"
        if self.sandbox_setup_failed:
            return "codex_app_server_turn_start_sandbox_setup_failed"
        if self.error:
            return "codex_app_server_turn_start_failed"
        if not self.foreground_no_steal_verified:
            return "codex_app_server_turn_start_foreground_changed"
        if not self.turn_id:
            return "codex_app_server_turn_start_response_invalid"
        if self.turn_status in {"failed", "interrupted"}:
            return "codex_app_server_turn_start_turn_failed"
        if not self.turn_completed:
            return "codex_app_server_turn_start_completion_missing"
        if self.seen_forbidden_markers:
            return "codex_app_server_turn_start_forbidden_marker_seen"
        if self.missing_required_markers:
            return "codex_app_server_turn_start_required_marker_missing"
        return "codex_app_server_turn_start_verified"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "native_call_attempts": self.native_call_attempts,
            "app_server_thread_start_attempts": self.app_server_thread_start_attempts,
            "app_server_readiness_attempts": self.app_server_readiness_attempts,
            "app_server_turn_start_attempts": self.app_server_turn_start_attempts,
            "request_attempts": int(self.request_attempts or 0),
            "foreground_hwnd_before": int(self.foreground_hwnd_before or 0),
            "foreground_hwnd_after": int(self.foreground_hwnd_after or 0),
            "foreground_focus_stable": self.foreground_focus_stable,
            "foreground_snapshot_before": dict(self.foreground_snapshot_before),
            "foreground_snapshot_after": dict(self.foreground_snapshot_after),
            "foreground_change_classification": self.foreground_change_classification,
            "foreground_no_steal_verified": self.foreground_no_steal_verified,
            "endpoint_url": self.endpoint_url,
            "thread_id": self.thread_id,
            "windows_sandbox_readiness_status": self.windows_sandbox_readiness_status,
            "windows_sandbox_ready": self.windows_sandbox_ready,
            "turn_id": self.turn_id,
            "turn_status": self.turn_status,
            "turn_completed": self.turn_completed,
            "turn_start_params": self.turn_start_params,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "session_task_complete_seen": self.session_task_complete_seen,
            "session_artifact_path": self.session_artifact_path,
            "system_dialog_detected": self.system_dialog_detected,
            "system_dialog_snapshots": [
                dict(item) for item in self.system_dialog_snapshots
            ],
            "sandbox_setup_failed": self.sandbox_setup_failed,
            "sandbox_error_texts": list(self.sandbox_error_texts),
            "missing_required_markers": list(self.missing_required_markers),
            "seen_forbidden_markers": list(self.seen_forbidden_markers),
            "assistant_readback_text": self.assistant_readback_text,
            "session_readback_text": self.session_readback_text,
            "turn": self.turn,
            "windows_sandbox_readiness_response": dict(
                self.windows_sandbox_readiness_response
            ),
            "turn_start_response": dict(self.turn_start_response),
            "notifications": [dict(item) for item in self.notifications],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "dry_run": dict(self.dry_run),
        }


class CodexAppServerTurnDryRunAdapter:
    def prepare(
        self,
        request: CodexAppServerTurnRequest,
    ) -> CodexAppServerTurnDryRunReport:
        return CodexAppServerTurnDryRunReport(
            request=request,
            validation_errors=_validate_request(request),
        )


class CodexAppServerThreadStartAdapter:
    def __init__(
        self,
        *,
        client: object | None = None,
        request_timeout: float = 2.0,
        thread_list_limit: int = 5,
        foreground_hwnd_provider: object | None = None,
        system_dialog_observer: object | None = None,
        system_dialog_poll_interval_sec: float = 0.25,
    ):
        self.client = client
        self.request_timeout = max(0.1, float(request_timeout))
        self.thread_list_limit = max(1, int(thread_list_limit or 1))
        self.foreground_hwnd_provider = foreground_hwnd_provider
        self.system_dialog_observer = system_dialog_observer
        self.system_dialog_poll_interval_sec = max(0.05, float(system_dialog_poll_interval_sec))

    def start(
        self,
        dry_run: CodexAppServerTurnDryRunReport | dict,
    ) -> CodexAppServerThreadStartExecutionReport:
        started = time.perf_counter()
        dry_run_dict = _dry_run_to_dict(dry_run)
        preflight = CodexAppServerThreadStartExecutionReport(
            dry_run=dry_run_dict,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        if preflight.decision != "codex_app_server_thread_start_failed" and (
            not bool(dry_run_dict.get("ok", False))
            or not bool(dry_run_dict.get("thread_start_required", False))
            or not preflight.endpoint_url
            or bool(preflight.thread_start_block_reason)
        ):
            return preflight
        client = self.client
        call = getattr(client, "initialize_start_thread_and_list_threads", None)
        if not callable(call):
            return CodexAppServerThreadStartExecutionReport(
                dry_run=dry_run_dict,
                error="codex_app_server_thread_start_client_missing",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        before_snapshot = _read_foreground_snapshot(self.foreground_hwnd_provider)
        before = int(before_snapshot.get("hwnd", 0) or 0)
        dialogs_before = _capture_system_dialog_snapshots(self.system_dialog_observer)
        if dialogs_before:
            return CodexAppServerThreadStartExecutionReport(
                dry_run=dry_run_dict,
                system_dialog_snapshots=tuple(dict(item) for item in dialogs_before),
                foreground_hwnd_before=before,
                foreground_hwnd_after=before,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=before_snapshot,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        sampler = _SystemDialogSampler(
            observer=self.system_dialog_observer,
            interval_sec=self.system_dialog_poll_interval_sec,
        )
        try:
            with sampler:
                data = call(
                    preflight.endpoint_url,
                    params=preflight.thread_start_params,
                    request_timeout=self.request_timeout,
                    thread_list_limit=self.thread_list_limit,
                )
            after_snapshot = _read_foreground_snapshot(
                self.foreground_hwnd_provider,
                after=True,
            )
            after = int(after_snapshot.get("hwnd", 0) or 0)
            dialogs_after = _capture_system_dialog_snapshots(self.system_dialog_observer)
            return CodexAppServerThreadStartExecutionReport(
                dry_run=dry_run_dict,
                thread_start_response=dict(data.get("thread_start_response", {}) or {}),
                thread_list_response=dict(data.get("thread_list_response", {}) or {}),
                notifications=tuple(
                    dict(item)
                    for item in data.get("notifications", []) or []
                    if isinstance(item, dict)
                ),
                system_dialog_snapshots=tuple(
                    dict(item)
                    for item in (
                        list(dialogs_before) + list(sampler.snapshots) + list(dialogs_after)
                    )
                    if isinstance(item, dict)
                ),
                request_attempts=int(data.get("request_attempts", 1) or 1),
                foreground_hwnd_before=before,
                foreground_hwnd_after=after,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=after_snapshot,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            after_snapshot = _read_foreground_snapshot(
                self.foreground_hwnd_provider,
                after=True,
            )
            after = int(after_snapshot.get("hwnd", 0) or 0)
            dialogs_after = _capture_system_dialog_snapshots(self.system_dialog_observer)
            return CodexAppServerThreadStartExecutionReport(
                dry_run=dry_run_dict,
                request_attempts=1,
                system_dialog_snapshots=tuple(
                    dict(item)
                    for item in (
                        list(dialogs_before) + list(sampler.snapshots) + list(dialogs_after)
                    )
                    if isinstance(item, dict)
                ),
                foreground_hwnd_before=before,
                foreground_hwnd_after=after,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=after_snapshot,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )


class CodexAppServerTurnStartAdapter:
    def __init__(
        self,
        *,
        client: object | None = None,
        request_timeout: float = 30.0,
        foreground_hwnd_provider: object | None = None,
        system_dialog_observer: object | None = None,
        system_dialog_poll_interval_sec: float = 0.25,
    ):
        self.client = client
        self.request_timeout = max(0.1, float(request_timeout))
        self.foreground_hwnd_provider = foreground_hwnd_provider
        self.system_dialog_observer = system_dialog_observer
        self.system_dialog_poll_interval_sec = max(0.05, float(system_dialog_poll_interval_sec))

    def start(
        self,
        dry_run: CodexAppServerTurnDryRunReport | dict,
    ) -> CodexAppServerTurnStartExecutionReport:
        started = time.perf_counter()
        dry_run_dict = _dry_run_to_dict(dry_run)
        preflight = CodexAppServerTurnStartExecutionReport(
            dry_run=dry_run_dict,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        if preflight.decision != "codex_app_server_turn_start_failed" and (
            not bool(dry_run_dict.get("ok", False))
            or str(dry_run_dict.get("decision", "") or "")
            != "codex_app_server_turn_dry_run_ready"
            or not bool(dry_run_dict.get("turn_start_ready", False))
            or not preflight.endpoint_url
            or not preflight.thread_id
        ):
            return preflight
        client = self.client
        call = getattr(client, "initialize_start_turn_and_collect", None)
        if not callable(call):
            return CodexAppServerTurnStartExecutionReport(
                dry_run=dry_run_dict,
                error="codex_app_server_turn_start_client_missing",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        before_snapshot = _read_foreground_snapshot(self.foreground_hwnd_provider)
        before = int(before_snapshot.get("hwnd", 0) or 0)
        dialogs_before = _capture_system_dialog_snapshots(self.system_dialog_observer)
        if dialogs_before:
            return CodexAppServerTurnStartExecutionReport(
                dry_run=dry_run_dict,
                system_dialog_snapshots=tuple(dict(item) for item in dialogs_before),
                foreground_hwnd_before=before,
                foreground_hwnd_after=before,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=before_snapshot,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        sampler = _SystemDialogSampler(
            observer=self.system_dialog_observer,
            interval_sec=self.system_dialog_poll_interval_sec,
        )
        try:
            with sampler:
                data = call(
                    preflight.endpoint_url,
                    params=preflight.turn_start_params,
                    request_timeout=self.request_timeout,
                )
            after_snapshot = _read_foreground_snapshot(
                self.foreground_hwnd_provider,
                after=True,
            )
            after = int(after_snapshot.get("hwnd", 0) or 0)
            dialogs_after = _capture_system_dialog_snapshots(self.system_dialog_observer)
            notifications = tuple(
                dict(item)
                for item in data.get("notifications", []) or []
                if isinstance(item, dict)
            )
            session = _session_readback_from_transport_result(data)
            if not session and _turn_start_needs_session_readback(
                notifications,
                request=_dict_value(dry_run_dict.get("request")),
            ):
                session = _codex_session_assistant_readback(preflight.thread_id)
            return CodexAppServerTurnStartExecutionReport(
                dry_run=dry_run_dict,
                turn_start_response=dict(data.get("turn_start_response", {}) or {}),
                windows_sandbox_readiness_response=dict(
                    data.get("windows_sandbox_readiness_response", {}) or {}
                ),
                notifications=notifications,
                session_readback_text=str(session.get("assistant_readback_text", "") or ""),
                session_task_complete_seen=bool(
                    session.get("task_complete_seen", False)
                ),
                session_artifact_path=str(session.get("artifact_path", "") or ""),
                system_dialog_snapshots=tuple(
                    dict(item)
                    for item in (
                        list(dialogs_before) + list(sampler.snapshots) + list(dialogs_after)
                    )
                    if isinstance(item, dict)
                ),
                request_attempts=int(data.get("request_attempts", 1) or 1),
                foreground_hwnd_before=before,
                foreground_hwnd_after=after,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=after_snapshot,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        except Exception as exc:
            after_snapshot = _read_foreground_snapshot(
                self.foreground_hwnd_provider,
                after=True,
            )
            after = int(after_snapshot.get("hwnd", 0) or 0)
            dialogs_after = _capture_system_dialog_snapshots(self.system_dialog_observer)
            return CodexAppServerTurnStartExecutionReport(
                dry_run=dry_run_dict,
                request_attempts=1,
                system_dialog_snapshots=tuple(
                    dict(item)
                    for item in (
                        list(dialogs_before) + list(sampler.snapshots) + list(dialogs_after)
                    )
                    if isinstance(item, dict)
                ),
                foreground_hwnd_before=before,
                foreground_hwnd_after=after,
                foreground_snapshot_before=before_snapshot,
                foreground_snapshot_after=after_snapshot,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )


def build_codex_app_server_turn_request(
    *,
    agent: str,
    project_name: str,
    task_name: str,
    message: str,
    composed_message: str,
    app_surface_probe: dict,
    selected_transport: dict,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
    workspace_path: str | Path = "",
) -> CodexAppServerTurnRequest:
    return CodexAppServerTurnRequest(
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        message=str(message or "").strip(),
        composed_message=str(composed_message or "").strip(),
        selected_transport=dict(selected_transport or {}),
        app_surface_probe=dict(app_surface_probe or {}),
        required_markers=tuple(
            str(marker).strip()
            for marker in required_markers or ()
            if str(marker or "").strip()
        ),
        forbidden_markers=tuple(
            str(marker).strip()
            for marker in forbidden_markers or ()
            if str(marker or "").strip()
        ),
        workspace_path=str(workspace_path or "").strip(),
    )


def _validate_request(request: CodexAppServerTurnRequest) -> tuple[str, ...]:
    errors: list[str] = []
    if request.agent_id != "codex":
        errors.append("agent_not_codex")
    if not request.text:
        errors.append("message_required")
    if not request.endpoint_ready:
        errors.append("endpoint_not_ready")
    if request.thread_start_required:
        if not str(request.workspace_path or "").strip():
            errors.append("thread_start_workspace_missing")
    elif not request.thread_id:
        if request.selected_thread_id and not _workspace_matches_request(request):
            errors.append("workspace_mismatch")
        else:
            errors.append("thread_id_missing")
    elif not _workspace_matches_request(request):
        errors.append("workspace_mismatch")
    elif not request.turn_start_foreground_safe:
        errors.append("turn_start_foreground_risk")
    if not request.required_markers:
        errors.append("required_marker_missing")
    return tuple(dict.fromkeys(errors))


def _request_ready(request: CodexAppServerTurnRequest) -> bool:
    return not _validate_request(request)


def _endpoint_summary(endpoint: dict) -> dict:
    if not endpoint:
        return {}
    metadata = _dict_value(endpoint.get("metadata"))
    forced_block = _endpoint_turn_start_forced_block_reason(metadata)
    thread_start_block = _endpoint_thread_start_forced_block_reason(metadata)
    return {
        "endpoint_type": str(endpoint.get("endpoint_type", "") or ""),
        "debugger_url": str(endpoint.get("debugger_url", "") or ""),
        "bridge_url": str(endpoint.get("bridge_url", "") or ""),
        "source": str(endpoint.get("source", "") or ""),
        "ready": bool(endpoint.get("ready", False)),
        "thread_api_ready": bool(metadata.get("thread_api_ready", False)),
        "turn_start_foreground_safe": bool(
            not forced_block
            and _metadata_bool(metadata, "turn_start_foreground_safe")
        ),
        "turn_start_block_reason": _endpoint_turn_start_block_reason(metadata),
        "thread_start_block_reason": thread_start_block,
        "surface_kind": str(metadata.get("surface_kind", "") or ""),
        "platform_os": str(metadata.get("platform_os", "") or ""),
        "selected_thread_id": str(metadata.get("selected_thread_id", "") or ""),
        "selected_thread_cwd": str(metadata.get("selected_thread_cwd", "") or ""),
        "observed_thread_count": int(metadata.get("observed_thread_count", 0) or 0),
    }


def _metadata_bool(metadata: dict, key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _endpoint_turn_start_block_reason(metadata: dict) -> str:
    forced = _endpoint_turn_start_forced_block_reason(metadata)
    if forced:
        return forced
    if _metadata_bool(metadata, "turn_start_foreground_safe"):
        return ""
    surface_kind = str(metadata.get("surface_kind", "") or "").strip().lower()
    platform_os = str(metadata.get("platform_os", "") or "").strip().lower()
    user_agent = str(metadata.get("user_agent", "") or "").strip().lower()
    if _metadata_is_owned_ephemeral_app_server(metadata):
        return "turn_start_foreground_safety_unproven"
    if (
        surface_kind == "desktop_app"
        or platform_os == "windows"
        or "codex desktop" in user_agent
    ):
        return "windows_desktop_app_server_turn_start_foreground_risk"
    return "turn_start_foreground_safety_unproven"


def _endpoint_turn_start_forced_block_reason(metadata: dict) -> str:
    if _metadata_is_owned_ephemeral_app_server(metadata) and not _metadata_contains_windows_desktop_activation_risk(metadata):
        return ""
    surface_kind = str(metadata.get("surface_kind", "") or "").strip().lower()
    platform_os = str(metadata.get("platform_os", "") or "").strip().lower()
    user_agent = str(metadata.get("user_agent", "") or "").strip().lower()
    if (
        surface_kind == "desktop_app"
        or platform_os == "windows"
        or "codex desktop" in user_agent
        or _metadata_contains_windows_desktop_activation_risk(metadata)
    ):
        return "windows_desktop_app_server_turn_start_foreground_risk"
    return ""


def _endpoint_thread_start_forced_block_reason(metadata: dict) -> str:
    if _metadata_is_owned_ephemeral_app_server(metadata) and not _metadata_contains_windows_desktop_activation_risk(metadata):
        return ""
    surface_kind = str(metadata.get("surface_kind", "") or "").strip().lower()
    user_agent = str(metadata.get("user_agent", "") or "").strip().lower()
    if (
        surface_kind == "desktop_app"
        or "codex desktop" in user_agent
        or _metadata_contains_windows_desktop_activation_risk(metadata)
    ):
        return "windows_desktop_app_server_thread_start_foreground_risk"
    return ""


def _metadata_is_owned_ephemeral_app_server(metadata: dict) -> bool:
    surface_kind = (
        str(metadata.get("surface_kind", "") or "")
        .strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if surface_kind in {
        "owned_ephemeral_app_server",
        "owned_loopback_app_server",
        "ephemeral_loopback_app_server",
    }:
        return True
    return bool(
        _metadata_bool(metadata, "owned_loopback_app_server")
        or _metadata_bool(metadata, "owned_ephemeral_app_server")
    )


def _metadata_contains_windows_desktop_activation_risk(metadata: dict) -> bool:
    values: list[str] = []
    for key in (
        "executable_path",
        "executablePath",
        "process_path",
        "processPath",
        "app_path",
        "path",
        "command_line",
        "commandLine",
        "launch_uri",
        "launchUri",
        "activation_uri",
        "activationUri",
    ):
        value = metadata.get(key)
        if isinstance(value, str):
            values.append(value)
    haystack = "\n".join(value.casefold() for value in values if value)
    return bool(
        "windowsapps" in haystack
        or "openai.codex" in haystack
        or "type=click&tag" in haystack
        or "?type=click" in haystack
    )


def _workspace_matches_request(request: CodexAppServerTurnRequest) -> bool:
    selected_cwd = request.matched_thread_cwd
    workspace_path = str(request.workspace_path or "").strip()
    project_name = str(request.project_name or "").strip()
    if workspace_path:
        if not selected_cwd:
            return False
        return _normalize_path_text(selected_cwd) == _normalize_path_text(workspace_path)
    if project_name:
        if not selected_cwd:
            return False
        project_key = project_name.casefold()
        return project_key in {
            component.casefold()
            for component in _path_components(selected_cwd)
            if component
        }
    return True


def _thread_matches_request(thread: dict, request: CodexAppServerTurnRequest) -> bool:
    cwd = str(thread.get("cwd", "") or "").strip()
    if not cwd:
        return False
    workspace_path = str(request.workspace_path or "").strip()
    if workspace_path:
        return _normalize_path_text(cwd) == _normalize_path_text(workspace_path)
    project_name = str(request.project_name or "").strip()
    if project_name:
        project_key = project_name.casefold()
        return project_key in {
            component.casefold()
            for component in _path_components(cwd)
            if component
        }
    return True


def _normalize_path_text(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/").casefold()


def _path_components(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip().replace("\\", "/")
    return tuple(component for component in normalized.split("/") if component)


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _dry_run_to_dict(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _read_foreground_hwnd(provider: object | None) -> int:
    if provider is None:
        return _current_foreground_hwnd()
    try:
        if callable(provider):
            return int(provider() or 0)
        get_foreground = getattr(provider, "get_foreground_window", None)
        if callable(get_foreground):
            return int(get_foreground() or 0)
    except Exception:
        return 0
    return 0


def _read_foreground_snapshot(
    provider: object | None,
    *,
    after: bool = False,
) -> dict:
    if provider is not None:
        method_names = (
            ("get_foreground_snapshot_after", "get_foreground_snapshot")
            if after
            else ("get_foreground_snapshot",)
        )
        for method_name in method_names:
            getter = getattr(provider, method_name, None)
            if not callable(getter):
                continue
            try:
                return _normalize_foreground_snapshot(getter())
            except Exception:
                continue
    hwnd = _read_foreground_hwnd_after(provider) if after else _read_foreground_hwnd(provider)
    return _foreground_snapshot_from_hwnd(hwnd)


def _read_foreground_hwnd_after(provider: object | None) -> int:
    if provider is None:
        return _current_foreground_hwnd()
    try:
        get_foreground = getattr(provider, "get_foreground_window_after", None)
        if callable(get_foreground):
            return int(get_foreground() or 0)
    except Exception:
        return 0
    return _read_foreground_hwnd(provider)


def _normalize_foreground_snapshot(value: object) -> dict:
    data = dict(value) if isinstance(value, dict) else {}
    hwnd = _safe_int(data.get("hwnd"))
    child_texts = data.get("child_texts")
    return {
        "available": bool(data.get("available", True)),
        "hwnd": hwnd,
        "pid": _safe_int(data.get("pid") or data.get("process_id")),
        "process_id": _safe_int(data.get("process_id") or data.get("pid")),
        "thread_id": _safe_int(data.get("thread_id")),
        "process_name": str(data.get("process_name", "") or ""),
        "executable_path": str(data.get("executable_path", "") or ""),
        "window_title": str(
            data.get("window_title", "")
            or data.get("title", "")
            or ""
        ),
        "title": str(data.get("title", "") or data.get("window_title", "") or ""),
        "class_name": str(data.get("class_name", "") or ""),
        "child_texts": list(child_texts) if isinstance(child_texts, list) else [],
    }


def _foreground_snapshot_from_hwnd(hwnd: int) -> dict:
    handle = int(hwnd or 0)
    if not handle or not sys.platform.startswith("win"):
        return _normalize_foreground_snapshot({"hwnd": handle})
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        process_id, thread_id = _get_window_process_identity(user32, handle)
        process_name, executable_path = _process_identity_for_pid(process_id)
        title = _get_window_text(user32, handle, max_chars=512)
        return _normalize_foreground_snapshot(
            {
                "available": True,
                "hwnd": handle,
                "process_id": process_id,
                "thread_id": thread_id,
                "process_name": process_name,
                "executable_path": executable_path,
                "title": title,
                "window_title": title,
                "class_name": _get_class_name(user32, handle),
                "child_texts": _child_window_texts(user32, handle),
            }
        )
    except Exception:
        return _normalize_foreground_snapshot({"hwnd": handle})


def _current_foreground_hwnd() -> int:
    if not sys.platform.startswith("win"):
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        return int(user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def _classify_foreground_change(before: dict, after: dict) -> str:
    before_snapshot = _normalize_foreground_snapshot(before)
    after_snapshot = _normalize_foreground_snapshot(after)
    before_hwnd = _safe_int(before_snapshot.get("hwnd"))
    after_hwnd = _safe_int(after_snapshot.get("hwnd"))
    if not before_hwnd or not after_hwnd or before_hwnd == after_hwnd:
        return "stable"
    if _system_dialog_detected(after_snapshot):
        return "changed_to_system_dialog"
    if _foreground_snapshot_matches_codex(after_snapshot):
        return "changed_to_agent_surface"
    if _foreground_snapshot_has_identity(after_snapshot):
        return "changed_to_unrelated_surface"
    return "changed_unknown"


def _foreground_snapshot_matches_codex(snapshot: dict) -> bool:
    fields = [
        str(snapshot.get("process_name", "") or ""),
        str(snapshot.get("executable_path", "") or ""),
        str(snapshot.get("window_title", "") or ""),
        str(snapshot.get("title", "") or ""),
        str(snapshot.get("class_name", "") or ""),
    ]
    fields.extend(str(item or "") for item in _list_value(snapshot.get("child_texts")))
    haystack = "\n".join(field.casefold() for field in fields if field)
    return bool("codex" in haystack or "openai.codex" in haystack)


def _foreground_snapshot_has_identity(snapshot: dict) -> bool:
    return bool(
        _safe_int(snapshot.get("pid") or snapshot.get("process_id"))
        or str(snapshot.get("process_name", "") or "").strip()
        or str(snapshot.get("executable_path", "") or "").strip()
        or str(snapshot.get("window_title", "") or "").strip()
        or str(snapshot.get("title", "") or "").strip()
    )


class _SystemDialogSampler:
    def __init__(self, *, observer: object | None, interval_sec: float):
        self.observer = observer
        self.interval_sec = max(0.05, float(interval_sec or 0.05))
        self.snapshots: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_SystemDialogSampler":
        if not self._should_poll:
            return self
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.0)

    @property
    def _should_poll(self) -> bool:
        return bool(self.observer is not None or sys.platform.startswith("win"))

    def _run(self) -> None:
        while not self._stop.is_set():
            self.snapshots.extend(_capture_system_dialog_snapshots(self.observer))
            self._stop.wait(self.interval_sec)


def _capture_system_dialog_snapshots(observer: object | None) -> tuple[dict, ...]:
    snapshots = _capture_observed_dialog_snapshots(observer)
    if observer is None:
        snapshots.extend(_capture_windows_system_dialogs())
    return tuple(
        snapshot
        for snapshot in (_normalize_system_dialog_snapshot(item) for item in snapshots)
        if snapshot and _system_dialog_detected(snapshot)
    )


def _capture_observed_dialog_snapshots(observer: object | None) -> list[object]:
    if observer is None:
        return []
    try:
        value = None
        for method_name in ("capture_system_dialogs", "capture_all", "capture"):
            method = getattr(observer, method_name, None)
            if callable(method):
                value = method()
                break
        if value is None and callable(observer):
            value = observer()
    except Exception as exc:
        return [
            {
                "available": False,
                "hwnd": 0,
                "title": "",
                "error": str(exc) or exc.__class__.__name__,
            }
        ]
    if isinstance(value, dict):
        dialogs = value.get("dialogs")
        if isinstance(dialogs, list):
            return [item for item in dialogs if isinstance(item, dict)]
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, dict)]
    return []


def _capture_windows_system_dialogs() -> list[dict]:
    if not sys.platform.startswith("win"):
        return []
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        snapshots: list[dict] = []
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _visit(hwnd, _lparam):
            hwnd_int = int(hwnd)
            visible = True
            is_visible = getattr(user32, "IsWindowVisible", None)
            if callable(is_visible):
                visible = bool(is_visible(wintypes.HWND(hwnd_int)))
            if not visible:
                return True
            title = _get_window_text(user32, hwnd_int, max_chars=512)
            class_name = _get_class_name(user32, hwnd_int)
            process_id, thread_id = _get_window_process_identity(user32, hwnd_int)
            process_name, executable_path = _process_identity_for_pid(process_id)
            snapshot = {
                "available": True,
                "hwnd": hwnd_int,
                "title": title,
                "class_name": class_name,
                "process_id": process_id,
                "thread_id": thread_id,
                "process_name": process_name,
                "executable_path": executable_path,
                "child_texts": _child_window_texts(user32, hwnd_int),
            }
            if _system_dialog_detected(snapshot):
                snapshots.append(snapshot)
            return True

        user32.EnumWindows(enum_proc(_visit), wintypes.LPARAM(0))
        return snapshots[:16]
    except Exception:
        return []


def _normalize_system_dialog_snapshot(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    data = dict(value)
    data["available"] = bool(data.get("available", True))
    data["hwnd"] = int(data.get("hwnd", 0) or 0)
    if "child_texts" in data and not isinstance(data.get("child_texts"), list):
        data["child_texts"] = []
    return data


def _system_dialog_detected(snapshot: dict) -> bool:
    if not isinstance(snapshot, dict):
        return False
    fields = [
        str(snapshot.get("title", "") or ""),
        str(snapshot.get("class_name", "") or ""),
        str(snapshot.get("process_name", "") or ""),
        str(snapshot.get("executable_path", "") or ""),
        str(snapshot.get("text", "") or ""),
        str(snapshot.get("error", "") or ""),
    ]
    fields.extend(str(item or "") for item in _list_value(snapshot.get("child_texts")))
    haystack = "\n".join(item.casefold() for item in fields if item)
    if not haystack:
        return False
    hard_markers = (
        "session-start",
        "閫夋嫨搴旂敤浠ユ墦寮€",
        "选择应用以打开",
        "choose an app",
        "how do you want to open",
        "open with",
        "error launching app",
        "unable to find electron app",
        "cannot find module",
        "a javascript error occurred in the main process",
        "uncaught exception",
        "attachconsole failed",
        "?type=click",
        "type=click&tag",
    )
    if any(marker in haystack for marker in hard_markers):
        return True
    title = str(snapshot.get("title", "") or "").strip().casefold()
    if title == "error" and any(
        marker in haystack
        for marker in (
            "codex.exe",
            "openai.codex",
            "windowsapps",
            "electron",
        )
    ):
        return True
    return False


def _get_window_text(user32, hwnd: int, *, max_chars: int) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(max_chars)
        copied = user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
        if not copied:
            return ""
        return buffer.value
    except Exception:
        return ""


def _get_class_name(user32, hwnd: int) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(256)
        copied = user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
        if not copied:
            return ""
        return buffer.value
    except Exception:
        return ""


def _get_window_process_identity(user32, hwnd: int) -> tuple[int, int]:
    try:
        process_id = wintypes.DWORD(0)
        thread_id = int(
            user32.GetWindowThreadProcessId(
                wintypes.HWND(hwnd),
                ctypes.byref(process_id),
            )
            or 0
        )
        return int(process_id.value or 0), thread_id
    except Exception:
        return 0, 0


def _child_window_texts(user32, hwnd: int) -> list[str]:
    texts: list[str] = []
    try:
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _visit(child_hwnd, _lparam):
            text = _get_window_text(user32, int(child_hwnd), max_chars=1024).strip()
            if text and text not in texts:
                texts.append(text)
            return True

        user32.EnumChildWindows(wintypes.HWND(hwnd), enum_proc(_visit), wintypes.LPARAM(0))
    except Exception:
        return texts
    return texts[:32]


def _process_identity_for_pid(process_id: int) -> tuple[str, str]:
    if int(process_id or 0) <= 0:
        return "", ""
    try:
        import psutil

        proc = psutil.Process(int(process_id))
        return str(proc.name() or ""), str(proc.exe() or "")
    except Exception:
        return "", ""


def _thread_from_thread_start_response(response: dict) -> dict:
    result = _dict_value(response.get("result"))
    thread = _compact_thread(_dict_value(result.get("thread")))
    if thread and not thread.get("cwd"):
        thread["cwd"] = str(result.get("cwd", "") or "")
    return thread


def _threads_from_thread_list_response(response: dict) -> tuple[dict, ...]:
    result = _dict_value(response.get("result"))
    data = result.get("data")
    if not isinstance(data, list):
        return ()
    return tuple(
        thread
        for thread in (_compact_thread(item) for item in data if isinstance(item, dict))
        if thread
    )


def _threads_from_thread_started_notifications(
    notifications: tuple[dict, ...],
) -> tuple[dict, ...]:
    values: list[dict] = []
    for notification in notifications:
        if not isinstance(notification, dict):
            continue
        if str(notification.get("method", "") or "") != "thread/started":
            continue
        params = _dict_value(notification.get("params"))
        thread = _compact_thread(_dict_value(params.get("thread")))
        if thread:
            values.append(thread)
    return tuple(values)


def _turn_from_turn_start_response(response: dict) -> dict:
    result = _dict_value(response.get("result"))
    return _compact_turn(_dict_value(result.get("turn")))


def _completed_turn_from_notifications(notifications: tuple[dict, ...]) -> dict:
    for notification in reversed(tuple(notifications or ())):
        if not isinstance(notification, dict):
            continue
        method = str(notification.get("method", "") or "")
        params = _notification_params(notification)
        if method and method != "turn/completed":
            continue
        turn = _compact_turn(_dict_value(params.get("turn")))
        if turn:
            return turn
    return {}


def _assistant_readback_text(notifications: tuple[dict, ...]) -> str:
    parts: list[str] = []
    for notification in notifications or ():
        if not isinstance(notification, dict):
            continue
        method = str(notification.get("method", "") or "")
        params = _notification_params(notification)
        if method == "item/agentMessage/delta" or (
            not method and "delta" in params and "itemId" in params
        ):
            parts.append(str(params.get("delta", "") or ""))
            continue
        if method == "item/completed" or (not method and "item" in params):
            item = _dict_value(params.get("item"))
            if _is_assistant_item(item):
                parts.extend(_extract_text_values(item))
    return "".join(parts)


def _turn_start_needs_session_readback(
    notifications: tuple[dict, ...],
    *,
    request: dict,
) -> bool:
    if not _completed_turn_from_notifications(notifications):
        return True
    text = _assistant_readback_text(notifications)
    required_markers = _string_tuple(request.get("required_markers"))
    return any(marker not in text for marker in required_markers)


def _session_readback_from_transport_result(data: dict) -> dict:
    text = str(data.get("session_readback_text", "") or "")
    task_complete_seen = bool(data.get("session_task_complete_seen", False))
    artifact_path = str(data.get("session_artifact_path", "") or "")
    if not text and not task_complete_seen and not artifact_path:
        return {}
    return {
        "assistant_readback_text": text,
        "task_complete_seen": task_complete_seen,
        "artifact_path": artifact_path,
    }


def _codex_session_assistant_readback(thread_id: str) -> dict:
    thread = str(thread_id or "").strip()
    if not thread:
        return {}
    session_path = _find_codex_session_path(thread)
    if not session_path:
        return {}
    parts: list[str] = []
    task_complete_seen = False
    try:
        with session_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                record_type = str(record.get("type", "") or "")
                payload = _dict_value(record.get("payload"))
                if record_type == "response_item":
                    for text in _assistant_response_item_text(payload):
                        _append_session_readback_text(parts, text)
                elif record_type == "event_msg":
                    task_text = _task_complete_last_agent_message(payload)
                    if task_text:
                        task_complete_seen = True
                        _append_session_readback_text(parts, task_text)
    except OSError:
        return {}
    return {
        "assistant_readback_text": "".join(parts),
        "task_complete_seen": task_complete_seen,
        "artifact_path": str(session_path),
    }


def _find_codex_session_path(thread_id: str) -> Path | None:
    base = Path.home() / ".codex" / "sessions"
    if not base.exists():
        return None
    pattern = f"*{thread_id}*.jsonl"
    try:
        matches = [
            path
            for path in base.rglob(pattern)
            if path.is_file() and thread_id in path.name
        ]
    except OSError:
        return None
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _assistant_response_item_text(payload: dict) -> list[str]:
    if str(payload.get("role", "") or "").strip().casefold() != "assistant":
        return []
    return _extract_text_values(payload)


def _append_session_readback_text(parts: list[str], text: str) -> None:
    value = str(text or "")
    if not value:
        return
    joined = "".join(parts)
    if value == joined or value in parts:
        return
    parts.append(value)


def _task_complete_last_agent_message(payload: dict) -> str:
    if str(payload.get("type", "") or "").strip() != "task_complete":
        return ""
    return str(payload.get("last_agent_message", "") or "")


def _notification_params(notification: dict) -> dict:
    params = notification.get("params")
    if isinstance(params, dict):
        return dict(params)
    return dict(notification)


def _compact_turn(turn: dict) -> dict:
    turn_id = str(turn.get("id", "") or "").strip()
    status = str(turn.get("status", "") or "").strip()
    if not turn_id and not status:
        return {}
    return {
        "id": turn_id,
        "status": status,
        "error": _dict_value(turn.get("error")),
    }


def _is_assistant_item(item: dict) -> bool:
    item_type = str(item.get("type", "") or "").strip().casefold()
    role = str(item.get("role", "") or "").strip().casefold()
    if role == "assistant":
        return True
    return bool("agent" in item_type and "message" in item_type)


def _extract_text_values(value: object) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"text", "delta", "message"} and isinstance(child, str):
                texts.append(child)
            elif isinstance(child, (dict, list, tuple)):
                texts.extend(_extract_text_values(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            texts.extend(_extract_text_values(child))
    return texts


def _extract_all_strings(value: object) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            texts.extend(_extract_all_strings(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            texts.extend(_extract_all_strings(child))
    return texts


def _looks_like_sandbox_error(value: str) -> bool:
    text = str(value or "").casefold()
    return bool(
        "windows sandbox" in text
        or "spawn setup refresh" in text
        or "sandboxerror" in text
        or "sandbox error" in text
    )


def _compact_thread(thread: dict) -> dict:
    thread_id = str(thread.get("id", "") or "").strip()
    cwd = str(thread.get("cwd", "") or "").strip()
    preview = str(thread.get("preview", "") or "")
    if not thread_id and not cwd:
        return {}
    return {"id": thread_id, "cwd": cwd, "preview": preview}


def _thread_matches_workspace_text(thread: dict, workspace_path: str) -> bool:
    cwd = str(thread.get("cwd", "") or "").strip()
    if not cwd or not str(workspace_path or "").strip():
        return False
    return _normalize_path_text(cwd) == _normalize_path_text(workspace_path)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item or "").strip())


def _list_value(value: object) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _agent_id_from_name(agent: str) -> str:
    text = str(agent or "").strip().casefold()
    if "codex" in text:
        return "codex"
    return text


__all__ = [
    "CODEX_APP_SERVER_TURN_SCHEMA_VERSION",
    "CodexAppServerThreadStartAdapter",
    "CodexAppServerThreadStartExecutionReport",
    "CodexAppServerTurnStartAdapter",
    "CodexAppServerTurnStartExecutionReport",
    "CodexAppServerTurnDryRunAdapter",
    "CodexAppServerTurnDryRunReport",
    "CodexAppServerTurnRequest",
    "build_codex_app_server_turn_request",
]
