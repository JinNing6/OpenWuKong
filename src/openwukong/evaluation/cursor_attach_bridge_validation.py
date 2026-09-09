# -*- coding: utf-8 -*-
"""Attach to an existing Cursor bridge without launching a visible GUI."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Callable, Optional

from openwukong.evaluation.cursor_draft_hook_validation import (
    validate_cursor_draft_hook,
)
from openwukong.evaluation.cursor_draft_hook_probe import LIVE_ATTACH_SAFETY_PROFILE
from openwukong.evaluation.cursor_isolated_draft_hook_runner import (
    wait_for_ide_bridge,
)
from openwukong.evaluation.ide_bridge_contract_probe import (
    _capture_focus,
    _foreground_changed,
    _system_dialog_detected,
)
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


@dataclasses.dataclass(frozen=True)
class CursorAttachBridgeValidationReport:
    bridge_url: str
    workspace_path: str = ""
    message: str = ""
    allow_write: bool = False
    safety_profile: str = ""
    bridge_readiness_report: dict = dataclasses.field(default_factory=dict)
    validation_report: dict = dataclasses.field(default_factory=dict)
    before_focus: dict = dataclasses.field(default_factory=dict)
    after_focus: dict = dataclasses.field(default_factory=dict)
    decision: str = ""
    output_path: str = ""
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-attach-bridge-validation"

    @property
    def safety_mode(self) -> str:
        return "attach_only_existing_bridge"

    @property
    def ok(self) -> bool:
        return self.decision in {
            "cursor_attach_bridge_dry_run_ready",
            "cursor_attach_bridge_validated",
        } and bool(self.validation_report.get("ok", False))

    @property
    def launch_attempts(self) -> int:
        return 0

    @property
    def stop_attempts(self) -> int:
        return 0

    @property
    def control_allowed(self) -> bool:
        return bool(self.validation_report.get("control_allowed", False))

    @property
    def control_attempts(self) -> int:
        return int(self.validation_report.get("control_attempts", 0) or 0)

    @property
    def window_input_attempts(self) -> int:
        return int(self.validation_report.get("window_input_attempts", 0) or 0)

    @property
    def bridge_send_attempts(self) -> int:
        return int(self.validation_report.get("bridge_send_attempts", 0) or 0)

    @property
    def draft_write_attempts(self) -> int:
        return int(self.validation_report.get("draft_write_attempts", 0) or 0)

    @property
    def foreground_changed(self) -> bool:
        return _foreground_changed(self.before_focus, self.after_focus) or bool(
            self.validation_report.get("foreground_changed", False)
        )

    @property
    def system_dialog_detected(self) -> bool:
        return _system_dialog_detected(self.after_focus) or bool(
            self.validation_report.get("system_dialog_detected", False)
        )

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
            "draft_write_attempts": self.draft_write_attempts,
            "launch_attempts": self.launch_attempts,
            "stop_attempts": self.stop_attempts,
            "foreground_changed": self.foreground_changed,
            "system_dialog_detected": self.system_dialog_detected,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "message": self.message,
            "allow_write": self.allow_write,
            "safety_profile": self.safety_profile,
            "before_focus": dict(self.before_focus),
            "after_focus": dict(self.after_focus),
            "bridge_readiness_report": dict(self.bridge_readiness_report),
            "validation_report": dict(self.validation_report),
            "output_path": self.output_path,
            "error": self.error,
        }


def run_cursor_attach_bridge_validation(
    *,
    bridge_url: str = "",
    bridge_registry_paths=(),
    workspace_path: str | Path = "",
    message: str = "OPENWUKONG_CURSOR_ATTACH_BRIDGE_DRY_RUN",
    allow_write: bool = False,
    safety_profile: str = "",
    request_timeout: float = 5.0,
    bridge_ready_timeout_sec: float = 3.0,
    post_action_observation_delay_sec: float = 0.5,
    output_path: str | Path = "",
    focus_observer: object | None = None,
    bridge_waiter: Callable[..., dict] | None = None,
    validator: Callable[..., object] | None = None,
) -> CursorAttachBridgeValidationReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    bridge = resolve_ide_bridge_url(
        bridge_url,
        agent_id="cursor",
        workspace_path=workspace,
        registry_paths=tuple(bridge_registry_paths or ()),
    )
    output = str(Path(output_path)) if output_path else ""
    before_focus = _capture_focus(focus_observer)

    if not bridge:
        report = CursorAttachBridgeValidationReport(
            bridge_url=bridge,
            workspace_path=workspace,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            before_focus=before_focus,
            after_focus=dict(before_focus),
            decision="cursor_attach_bridge_url_missing",
            output_path=output,
            error="missing_bridge_url",
        )
        return _write_report_if_requested(report, output)

    if allow_write:
        report = CursorAttachBridgeValidationReport(
            bridge_url=bridge,
            workspace_path=workspace,
            message=message,
            allow_write=True,
            safety_profile=safety_profile,
            before_focus=before_focus,
            after_focus=dict(before_focus),
            decision="cursor_attach_bridge_write_blocked",
            output_path=output,
            error="attach_only_write_not_enabled",
        )
        return _write_report_if_requested(report, output)

    active_waiter = bridge_waiter or wait_for_ide_bridge
    readiness = dict(
        active_waiter(
            bridge_url=bridge,
            workspace_path=workspace,
            request_timeout=request_timeout,
            timeout_sec=bridge_ready_timeout_sec,
        )
    )
    if not readiness.get("ok", False):
        after_focus = _capture_focus(focus_observer)
        report = CursorAttachBridgeValidationReport(
            bridge_url=bridge,
            workspace_path=workspace,
            message=message,
            allow_write=False,
            safety_profile=safety_profile,
            bridge_readiness_report=readiness,
            before_focus=before_focus,
            after_focus=after_focus,
            decision="cursor_attach_bridge_not_ready",
            output_path=output,
            error=str(readiness.get("error", "") or "cursor_attach_bridge_not_ready"),
        )
        return _write_report_if_requested(report, output)

    active_validator = validator or validate_cursor_draft_hook
    validation = _to_dict(
        active_validator(
            bridge_url=bridge,
            workspace_path=workspace,
            message=message,
            allow_write=False,
            safety_profile=LIVE_ATTACH_SAFETY_PROFILE,
            request_timeout=request_timeout,
            post_action_observation_delay_sec=post_action_observation_delay_sec,
            focus_observer=focus_observer,
        )
    )
    after_focus = _capture_focus(focus_observer)
    validation_decision = str(validation.get("decision", "") or "")
    decision = _attach_validation_decision(
        validation,
        validation_decision=validation_decision,
        foreground_changed=_foreground_changed(before_focus, after_focus),
        system_dialog_detected=_system_dialog_detected(after_focus),
    )
    report = CursorAttachBridgeValidationReport(
        bridge_url=bridge,
        workspace_path=workspace,
        message=message,
        allow_write=False,
        safety_profile=safety_profile,
        bridge_readiness_report=readiness,
        validation_report=validation,
        before_focus=before_focus,
        after_focus=after_focus,
        decision=decision,
        output_path=output,
        error="" if decision == "cursor_attach_bridge_dry_run_ready" else str(
            validation.get("error", "") or decision
        ),
    )
    return _write_report_if_requested(report, output)


def _attach_validation_decision(
    validation: dict,
    *,
    validation_decision: str,
    foreground_changed: bool,
    system_dialog_detected: bool,
) -> str:
    if _validation_error(validation) == "not_found":
        return "cursor_attach_bridge_draft_hook_unavailable"
    if system_dialog_detected:
        return "cursor_attach_bridge_system_dialog_detected"
    if foreground_changed or bool(validation.get("foreground_changed", False)):
        return "cursor_attach_bridge_foreground_changed"
    if validation.get("ok", False) and validation_decision == "cursor_draft_hook_dry_run_ready":
        return "cursor_attach_bridge_dry_run_ready"
    return "cursor_attach_bridge_validation_failed"


def _validation_error(validation: dict) -> str:
    direct = str(validation.get("error", "") or "").strip()
    if direct:
        return direct
    dry_run = validation.get("dry_run_report", {})
    if not isinstance(dry_run, dict):
        return ""
    nested = str(dry_run.get("error", "") or "").strip()
    if nested:
        return nested
    response = dry_run.get("response", {})
    if isinstance(response, dict):
        return str(response.get("error", "") or "").strip()
    return ""


def _write_report_if_requested(
    report: CursorAttachBridgeValidationReport,
    output_path: str,
) -> CursorAttachBridgeValidationReport:
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _to_dict(value: object) -> dict:
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if isinstance(value, dict):
        return dict(value)
    return {}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--message", default="OPENWUKONG_CURSOR_ATTACH_BRIDGE_DRY_RUN")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--safety-profile", default="")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--bridge-ready-timeout-sec", type=float, default=3.0)
    parser.add_argument("--post-action-observation-delay-sec", type=float, default=0.5)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_cursor_attach_bridge_validation(
        bridge_url=args.bridge_url,
        bridge_registry_paths=tuple(args.bridge_registry_path or ()),
        workspace_path=args.workspace_path,
        message=args.message,
        allow_write=args.allow_write,
        safety_profile=args.safety_profile,
        request_timeout=args.request_timeout,
        bridge_ready_timeout_sec=args.bridge_ready_timeout_sec,
        post_action_observation_delay_sec=args.post_action_observation_delay_sec,
        output_path=args.output,
    )
    data = report.to_dict()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Cursor attach bridge validation: "
            f"decision={data['decision']} ok={data['ok']} "
            f"launch_attempts={data['launch_attempts']}"
        )
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
