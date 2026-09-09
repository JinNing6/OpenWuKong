# -*- coding: utf-8 -*-
"""Validate Cursor Glass Agent query dispatch with strict transcript readback."""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.evaluation.cursor_glass_agent_query_probe import (
    LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE,
    probe_cursor_glass_agent_query,
)
from openwukong.evaluation.cursor_transcript_readback import (
    run_cursor_transcript_readback,
)
from openwukong.evaluation.ide_bridge_contract_probe import (
    _capture_focus,
    _foreground_changed,
    _system_dialog_detected,
)
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


@dataclasses.dataclass(frozen=True)
class CursorGlassAgentQueryValidationReport:
    bridge_url: str
    workspace_path: str
    message: str
    required_markers: tuple[str, ...] = ()
    allow_write: bool = False
    safety_profile: str = ""
    dry_run_report: dict = dataclasses.field(default_factory=dict)
    send_report: dict = dataclasses.field(default_factory=dict)
    user_readback_report: dict = dataclasses.field(default_factory=dict)
    assistant_readback_report: dict = dataclasses.field(default_factory=dict)
    before_focus: dict = dataclasses.field(default_factory=dict)
    after_focus: dict = dataclasses.field(default_factory=dict)
    settled_focus: dict = dataclasses.field(default_factory=dict)
    decision: str = ""
    user_prompt_verified: bool = False
    assistant_response_verified: bool = False
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-glass-agent-query-validation"

    @property
    def safety_mode(self) -> str:
        if self.allow_write and self.safety_profile == LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE:
            return "live_glass_agent_query_validation"
        return "dry_run_bridge_contract"

    @property
    def control_allowed(self) -> bool:
        return self.allow_write and self.safety_profile == LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE

    @property
    def agent_request_attempts(self) -> int:
        return int(self.send_report.get("agent_request_attempts", 0) or 0)

    @property
    def control_attempts(self) -> int:
        return self.agent_request_attempts if self.control_allowed else 0

    @property
    def bridge_probe_attempts(self) -> int:
        return int(self.dry_run_report.get("bridge_probe_attempts", 0) or 0) + int(
            self.send_report.get("bridge_probe_attempts", 0) or 0
        )

    @property
    def bridge_send_attempts(self) -> int:
        return int(self.send_report.get("bridge_send_attempts", 0) or 0)

    @property
    def foreground_changed(self) -> bool:
        return _foreground_changed(self.before_focus, self.after_focus) or _foreground_changed(
            self.before_focus,
            self.settled_focus,
        )

    @property
    def system_dialog_detected(self) -> bool:
        return _system_dialog_detected(self.after_focus) or _system_dialog_detected(
            self.settled_focus,
        )

    @property
    def ok(self) -> bool:
        if self.decision == "cursor_glass_agent_query_assistant_validated":
            return True
        if self.decision == "cursor_glass_agent_query_dry_run_ready":
            return not self.system_dialog_detected
        return False

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "bridge_send_attempts": self.bridge_send_attempts,
            "bridge_probe_attempts": self.bridge_probe_attempts,
            "agent_request_attempts": self.agent_request_attempts,
            "foreground_changed": self.foreground_changed,
            "system_dialog_detected": self.system_dialog_detected,
            "user_prompt_verified": self.user_prompt_verified,
            "assistant_response_verified": self.assistant_response_verified,
            "readback_verified": self.assistant_response_verified,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "required_markers": list(self.required_markers),
            "allow_write": self.allow_write,
            "safety_profile": self.safety_profile,
            "before_focus": dict(self.before_focus),
            "after_focus": dict(self.after_focus),
            "settled_focus": dict(self.settled_focus),
            "dry_run_report": dict(self.dry_run_report),
            "send_report": dict(self.send_report),
            "user_readback_report": dict(self.user_readback_report),
            "assistant_readback_report": dict(self.assistant_readback_report),
            "error": self.error,
        }


def validate_cursor_glass_agent_query(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    message: str,
    required_markers: Iterable[str] = (),
    allow_write: bool = False,
    safety_profile: str = "",
    bridge_client=None,
    cursor_transcript_readback_runner: Callable[..., dict] | None = None,
    focus_observer: object | None = None,
    request_timeout: float = 5.0,
    post_action_observation_delay_sec: float = 0.25,
    assistant_readback_polls: int = 1,
    assistant_readback_interval_sec: float = 2.0,
    max_blob_rows: int = 500,
) -> CursorGlassAgentQueryValidationReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    readback_markers = _clean_markers(required_markers) or _clean_markers((message,))
    before_focus = _capture_focus(focus_observer)
    dry_run = probe_cursor_glass_agent_query(
        bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=False,
        safety_profile=safety_profile,
        bridge_client=bridge_client,
        request_timeout=request_timeout,
    ).to_dict()

    if not dry_run.get("ok", False):
        after_focus = _capture_focus(focus_observer)
        return CursorGlassAgentQueryValidationReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            required_markers=readback_markers,
            allow_write=allow_write,
            safety_profile=safety_profile,
            dry_run_report=dry_run,
            before_focus=before_focus,
            after_focus=after_focus,
            settled_focus=dict(after_focus),
            decision="cursor_glass_agent_query_dry_run_failed",
            error=str(dry_run.get("error", "")),
        )

    if not allow_write:
        after_focus = _capture_focus(focus_observer)
        return CursorGlassAgentQueryValidationReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            required_markers=readback_markers,
            allow_write=False,
            safety_profile=safety_profile,
            dry_run_report=dry_run,
            before_focus=before_focus,
            after_focus=after_focus,
            settled_focus=dict(after_focus),
            decision="cursor_glass_agent_query_dry_run_ready",
            error="",
        )

    send_report = probe_cursor_glass_agent_query(
        bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=True,
        safety_profile=safety_profile,
        bridge_client=bridge_client,
        request_timeout=request_timeout,
    ).to_dict()
    after_focus = _capture_focus(focus_observer)
    if post_action_observation_delay_sec > 0:
        time.sleep(max(0.0, float(post_action_observation_delay_sec)))
        settled_focus = _capture_focus(focus_observer)
    else:
        settled_focus = dict(after_focus)

    user_readback_report = {}
    assistant_readback_report = {}
    user_prompt_verified = False
    assistant_response_verified = False
    if send_report.get("ok", False):
        user_readback_report = _run_transcript_readback(
            workspace,
            readback_markers,
            role="user",
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            max_blob_rows=max_blob_rows,
        )
        user_prompt_verified = _marker_accepted(readback_markers, user_readback_report)
        assistant_readback_report = _poll_transcript_readback(
            workspace,
            readback_markers,
            role="assistant",
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            polls=assistant_readback_polls,
            interval_sec=assistant_readback_interval_sec,
            max_blob_rows=max_blob_rows,
        )
        assistant_response_verified = _marker_accepted(readback_markers, assistant_readback_report)

    decision = _validation_decision(
        send_report,
        user_prompt_verified=user_prompt_verified,
        assistant_response_verified=assistant_response_verified,
        foreground_changed=_foreground_changed(before_focus, after_focus)
        or _foreground_changed(before_focus, settled_focus),
        system_dialog_detected=_system_dialog_detected(after_focus)
        or _system_dialog_detected(settled_focus),
    )
    return CursorGlassAgentQueryValidationReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        message=message,
        required_markers=readback_markers,
        allow_write=allow_write,
        safety_profile=safety_profile,
        dry_run_report=dry_run,
        send_report=send_report,
        user_readback_report=user_readback_report,
        assistant_readback_report=assistant_readback_report,
        before_focus=before_focus,
        after_focus=after_focus,
        settled_focus=settled_focus,
        decision=decision,
        user_prompt_verified=user_prompt_verified,
        assistant_response_verified=assistant_response_verified
        and decision == "cursor_glass_agent_query_assistant_validated",
        error="" if decision == "cursor_glass_agent_query_assistant_validated" else _error_for_decision(decision, send_report),
    )


def _run_transcript_readback(
    workspace_path: str,
    required_markers: tuple[str, ...],
    *,
    role: str,
    cursor_transcript_readback_runner: Callable[..., dict] | None,
    max_blob_rows: int,
) -> dict:
    runner = cursor_transcript_readback_runner or run_cursor_transcript_readback
    data = runner(
        workspace_path=workspace_path,
        required_markers=required_markers,
        required_response_role=role,
        max_blob_rows=max_blob_rows,
    )
    return data.to_dict() if hasattr(data, "to_dict") else dict(data)


def _poll_transcript_readback(
    workspace_path: str,
    required_markers: tuple[str, ...],
    *,
    role: str,
    cursor_transcript_readback_runner: Callable[..., dict] | None,
    polls: int,
    interval_sec: float,
    max_blob_rows: int,
) -> dict:
    attempts = max(1, int(polls or 1))
    last_report = {}
    for index in range(attempts):
        last_report = _run_transcript_readback(
            workspace_path,
            required_markers,
            role=role,
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            max_blob_rows=max_blob_rows,
        )
        if last_report.get("decision") == "cursor_transcript_readback_accepted":
            break
        if index + 1 < attempts and interval_sec > 0:
            time.sleep(max(0.0, float(interval_sec)))
    report = dict(last_report)
    report["poll_attempts"] = attempts
    report["poll_interval_sec"] = max(0.0, float(interval_sec))
    return report


def _marker_accepted(required_markers: tuple[str, ...], report: dict) -> bool:
    expected = set(str(item) for item in required_markers if str(item or "").strip())
    if not expected or not isinstance(report, dict):
        return False
    if report.get("decision") != "cursor_transcript_readback_accepted":
        return False
    found = set(str(item) for item in report.get("required_markers_found", []))
    return expected.issubset(found)


def _clean_markers(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        selected.append(item)
        seen.add(item)
    return tuple(selected)


def _validation_decision(
    send_report: dict,
    *,
    user_prompt_verified: bool,
    assistant_response_verified: bool,
    foreground_changed: bool,
    system_dialog_detected: bool,
) -> str:
    if not send_report.get("ok", False):
        return "cursor_glass_agent_query_send_failed"
    if system_dialog_detected:
        return "cursor_glass_agent_query_failed_system_dialog"
    if foreground_changed:
        return "cursor_glass_agent_query_failed_foreground_changed"
    if assistant_response_verified:
        return "cursor_glass_agent_query_assistant_validated"
    if user_prompt_verified:
        return "cursor_glass_agent_query_user_marker_only"
    return "cursor_glass_agent_query_readback_pending"


def _error_for_decision(decision: str, send_report: dict) -> str:
    if decision == "cursor_glass_agent_query_send_failed":
        return str(send_report.get("error", "") or decision)
    return decision


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--message", required=True)
    parser.add_argument("--required-marker", action="append", default=[])
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--safety-profile", default="")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--post-action-observation-delay-sec", type=float, default=0.25)
    parser.add_argument("--assistant-readback-polls", type=int, default=1)
    parser.add_argument("--assistant-readback-interval-sec", type=float, default=2.0)
    parser.add_argument("--max-blob-rows", type=int, default=500)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bridge_url = resolve_ide_bridge_url(
        args.bridge_url,
        agent_id="cursor",
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.bridge_registry_path or ()),
    )
    report = validate_cursor_glass_agent_query(
        bridge_url,
        workspace_path=args.workspace_path,
        message=args.message,
        required_markers=tuple(args.required_marker or ()),
        allow_write=args.allow_write,
        safety_profile=args.safety_profile,
        request_timeout=args.request_timeout,
        post_action_observation_delay_sec=args.post_action_observation_delay_sec,
        assistant_readback_polls=args.assistant_readback_polls,
        assistant_readback_interval_sec=args.assistant_readback_interval_sec,
        max_blob_rows=args.max_blob_rows,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Cursor Glass Agent query validation: "
            f"decision={data['decision']} "
            f"assistant_response_verified={data['assistant_response_verified']} "
            f"foreground_changed={data['foreground_changed']}"
        )
    return 0 if data["ok"] or data["decision"] == "cursor_glass_agent_query_dry_run_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
