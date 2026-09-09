# -*- coding: utf-8 -*-
"""Validate Cursor draft-hook safety with focus gates and live readback."""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.evaluation.cursor_draft_hook_probe import (
    ISOLATED_SAFETY_PROFILE,
    LIVE_ATTACH_SAFETY_PROFILE,
    LIVE_ATTACH_WRITE_SAFETY_PROFILE,
    WRITE_SAFETY_PROFILES,
    probe_cursor_draft_hook,
)
from openwukong.evaluation.cursor_live_composer_state import (
    probe_cursor_live_composer_state,
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
class CursorDraftHookValidationReport:
    bridge_url: str
    workspace_path: str
    message: str
    allow_write: bool = False
    safety_profile: str = ""
    composer_ids: tuple[str, ...] = ()
    dry_run_report: dict = dataclasses.field(default_factory=dict)
    write_report: dict = dataclasses.field(default_factory=dict)
    readback_report: dict = dataclasses.field(default_factory=dict)
    before_focus: dict = dataclasses.field(default_factory=dict)
    after_focus: dict = dataclasses.field(default_factory=dict)
    settled_focus: dict = dataclasses.field(default_factory=dict)
    decision: str = ""
    readback_verified: bool = False
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-draft-hook-validation"

    @property
    def safety_mode(self) -> str:
        if self.allow_write and self.safety_profile == ISOLATED_SAFETY_PROFILE:
            return "isolated_draft_write_validation"
        if self.allow_write and self.safety_profile == LIVE_ATTACH_WRITE_SAFETY_PROFILE:
            return "live_attach_draft_write_validation"
        return "dry_run_bridge_contract"

    @property
    def control_allowed(self) -> bool:
        return self.allow_write and self.safety_profile in WRITE_SAFETY_PROFILES

    @property
    def draft_write_attempts(self) -> int:
        return int(self.write_report.get("draft_write_attempts", 0) or 0)

    @property
    def control_attempts(self) -> int:
        return self.draft_write_attempts if self.control_allowed else 0

    @property
    def bridge_probe_attempts(self) -> int:
        return int(self.dry_run_report.get("bridge_probe_attempts", 0) or 0) + int(
            self.write_report.get("bridge_probe_attempts", 0) or 0
        )

    @property
    def readonly_command_attempts(self) -> int:
        return int(self.readback_report.get("readonly_command_attempts", 0) or 0)

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
        if self.decision == "cursor_draft_hook_validated":
            return True
        if self.decision == "cursor_draft_hook_dry_run_ready":
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
            "bridge_send_attempts": 0,
            "bridge_probe_attempts": self.bridge_probe_attempts,
            "draft_write_attempts": self.draft_write_attempts,
            "readonly_command_attempts": self.readonly_command_attempts,
            "foreground_changed": self.foreground_changed,
            "system_dialog_detected": self.system_dialog_detected,
            "readback_verified": self.readback_verified,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "allow_write": self.allow_write,
            "safety_profile": self.safety_profile,
            "composer_ids": list(self.composer_ids),
            "before_focus": dict(self.before_focus),
            "after_focus": dict(self.after_focus),
            "settled_focus": dict(self.settled_focus),
            "dry_run_report": dict(self.dry_run_report),
            "write_report": dict(self.write_report),
            "readback_report": dict(self.readback_report),
            "error": self.error,
        }


def validate_cursor_draft_hook(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    message: str,
    allow_write: bool = False,
    safety_profile: str = "",
    composer_ids: Iterable[str] = (),
    bridge_client=None,
    live_state_runner: Callable[..., dict] | None = None,
    cursor_transcript_readback_runner: Callable[..., dict] | None = None,
    focus_observer: object | None = None,
    request_timeout: float = 5.0,
    post_action_observation_delay_sec: float = 0.25,
) -> CursorDraftHookValidationReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    selected_composer_ids = tuple(_clean_strings(composer_ids))
    before_focus = _capture_focus(focus_observer)
    dry_run = probe_cursor_draft_hook(
        bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=False,
        safety_profile=safety_profile,
        composer_ids=selected_composer_ids,
        bridge_client=bridge_client,
        request_timeout=request_timeout,
    ).to_dict()

    if not dry_run.get("ok", False):
        after_focus = _capture_focus(focus_observer)
        return CursorDraftHookValidationReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            composer_ids=selected_composer_ids,
            dry_run_report=dry_run,
            before_focus=before_focus,
            after_focus=after_focus,
            settled_focus=dict(after_focus),
            decision="cursor_draft_hook_dry_run_failed",
            error=str(dry_run.get("error", "")),
        )

    if not allow_write:
        after_focus = _capture_focus(focus_observer)
        return CursorDraftHookValidationReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=False,
            safety_profile=safety_profile,
            composer_ids=selected_composer_ids,
            dry_run_report=dry_run,
            before_focus=before_focus,
            after_focus=after_focus,
            settled_focus=dict(after_focus),
            decision="cursor_draft_hook_dry_run_ready",
            error="",
        )

    write_report = probe_cursor_draft_hook(
        bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=True,
        safety_profile=safety_profile,
        composer_ids=selected_composer_ids,
        bridge_client=bridge_client,
        request_timeout=request_timeout,
    ).to_dict()
    after_focus = _capture_focus(focus_observer)
    if post_action_observation_delay_sec > 0:
        time.sleep(max(0.0, float(post_action_observation_delay_sec)))
        settled_focus = _capture_focus(focus_observer)
    else:
        settled_focus = dict(after_focus)

    readback_report = {}
    readback_verified = False
    if write_report.get("ok", False):
        if safety_profile == LIVE_ATTACH_WRITE_SAFETY_PROFILE:
            readback_report = _run_local_draft_storage_readback(
                workspace,
                message,
                cursor_transcript_readback_runner,
            )
            readback_verified = _message_in_storage_readback(message, readback_report)
        else:
            readback_composer_ids = selected_composer_ids or _write_report_composer_ids(
                write_report
            )
            readback_report = _run_live_state_readback(
                bridge_url,
                workspace,
                readback_composer_ids,
                bridge_client,
                request_timeout,
                live_state_runner,
                safety_profile,
            )
            readback_verified = _message_in_readback(message, readback_report)

    decision = _validation_decision(
        write_report,
        readback_verified=readback_verified,
        foreground_changed=_foreground_changed(before_focus, after_focus)
        or _foreground_changed(before_focus, settled_focus),
        system_dialog_detected=_system_dialog_detected(after_focus)
        or _system_dialog_detected(settled_focus),
    )
    return CursorDraftHookValidationReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=allow_write,
        safety_profile=safety_profile,
        composer_ids=selected_composer_ids,
        dry_run_report=dry_run,
        write_report=write_report,
        readback_report=readback_report,
        before_focus=before_focus,
        after_focus=after_focus,
        settled_focus=settled_focus,
        decision=decision,
        readback_verified=readback_verified and decision == "cursor_draft_hook_validated",
        error="" if decision == "cursor_draft_hook_validated" else _error_for_decision(decision, write_report),
    )


def _run_live_state_readback(
    bridge_url: str,
    workspace_path: str,
    composer_ids: tuple[str, ...],
    bridge_client,
    request_timeout: float,
    live_state_runner: Callable[..., dict] | None,
    safety_profile: str,
) -> dict:
    if live_state_runner is not None:
        data = live_state_runner(
            bridge_url=bridge_url,
            workspace_path=workspace_path,
            composer_ids=composer_ids,
            bridge_client=bridge_client,
            request_timeout=request_timeout,
            include_handles=True,
            safety_profile="isolated_cursor_read_probe"
            if safety_profile == ISOLATED_SAFETY_PROFILE
            else "",
        )
        return data.to_dict() if hasattr(data, "to_dict") else dict(data)
    return probe_cursor_live_composer_state(
        bridge_url,
        workspace_path=workspace_path,
        composer_ids=composer_ids,
        bridge_client=bridge_client,
        request_timeout=request_timeout,
        include_handles=True,
        safety_profile="isolated_cursor_read_probe"
        if safety_profile == ISOLATED_SAFETY_PROFILE
        else "",
    ).to_dict()


def _run_local_draft_storage_readback(
    workspace_path: str,
    message: str,
    cursor_transcript_readback_runner: Callable[..., dict] | None,
) -> dict:
    runner = cursor_transcript_readback_runner or run_cursor_transcript_readback
    data = runner(
        workspace_path=workspace_path,
        required_markers=(message,),
        required_response_role="user",
        max_blob_rows=500,
    )
    return data.to_dict() if hasattr(data, "to_dict") else dict(data)


def _validation_decision(
    write_report: dict,
    *,
    readback_verified: bool,
    foreground_changed: bool,
    system_dialog_detected: bool,
) -> str:
    if not write_report.get("ok", False):
        return "cursor_draft_hook_write_failed"
    if system_dialog_detected:
        return "cursor_draft_hook_validation_failed_system_dialog"
    if foreground_changed:
        return "cursor_draft_hook_validation_failed_foreground_changed"
    if not readback_verified:
        return "cursor_draft_hook_validation_failed_readback"
    return "cursor_draft_hook_validated"


def _message_in_readback(message: str, readback_report: dict) -> bool:
    expected = str(message or "")
    if not expected:
        return False
    for composer in readback_report.get("composers", []) if isinstance(readback_report, dict) else []:
        if not isinstance(composer, dict):
            continue
        text = str(composer.get("text", "") or "")
        rich_text = str(composer.get("rich_text", "") or "")
        if expected in text or expected in rich_text:
            return True
    return False


def _message_in_storage_readback(message: str, readback_report: dict) -> bool:
    expected = str(message or "")
    if not expected or not isinstance(readback_report, dict):
        return False
    if expected in set(str(item) for item in readback_report.get("required_markers_found", [])):
        return True
    return bool(readback_report.get("ok", False)) and expected not in set(
        str(item) for item in readback_report.get("missing_required_markers", [])
    )


def _write_report_composer_ids(write_report: dict) -> tuple[str, ...]:
    if not isinstance(write_report, dict):
        return ()
    response = write_report.get("response", {})
    if not isinstance(response, dict):
        return ()
    return _clean_strings((response.get("composer_id", ""),))


def _error_for_decision(decision: str, write_report: dict) -> str:
    if decision == "cursor_draft_hook_write_failed":
        return str(write_report.get("error", "") or decision)
    return decision


def _clean_strings(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        selected.append(item)
        seen.add(item)
    return tuple(selected)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--message", required=True)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--safety-profile", default="")
    parser.add_argument("--composer-id", action="append", default=[])
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--post-action-observation-delay-sec", type=float, default=0.25)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bridge_url = resolve_ide_bridge_url(
        args.bridge_url,
        agent_id="cursor",
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.bridge_registry_path or ()),
    )
    report = validate_cursor_draft_hook(
        bridge_url,
        workspace_path=args.workspace_path,
        message=args.message,
        allow_write=args.allow_write,
        safety_profile=args.safety_profile,
        composer_ids=tuple(args.composer_id or ()),
        request_timeout=args.request_timeout,
        post_action_observation_delay_sec=args.post_action_observation_delay_sec,
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
            "Cursor draft hook validation: "
            f"decision={data['decision']} "
            f"readback_verified={data['readback_verified']} "
            f"foreground_changed={data['foreground_changed']}"
        )
    return 0 if data["ok"] or data["decision"] == "cursor_draft_hook_dry_run_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
