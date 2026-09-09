# -*- coding: utf-8 -*-
"""Plan-only readiness matrix for computer operation surfaces."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlDispatchReport, ControlFabric, ControlIntent
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


BACKGROUND_EXECUTE = "background_execute"
READ_ONLY = "read_only"
FOREGROUND_REQUIRED = "foreground_required"
BLOCKED = "blocked"
BACKGROUND_EXECUTE_VERIFIED = "background_execute_verified"
BACKGROUND_EXECUTE_READY = "background_execute_ready"
READ_ONLY_READY = "read_only_ready"
FOREGROUND_REQUIRED_STATUS = "foreground_required"
BLOCKED_STATUS = "blocked"
CURSOR_SUBMIT_BLOCKED = "cursor_submit_readback_blocked"
WECHAT_NATIVE_SEND_BLOCKED = "wechat_native_send_readback_blocked"


@dataclasses.dataclass(frozen=True)
class ComputerOperationReadinessOptions:
    workspace_path: str = ""
    codex_app_server_ws_url: str = ""
    codex_app_server_turn_start_report: dict = dataclasses.field(default_factory=dict)
    browser_debugger_url: str = ""
    owned_browser_demo_report: dict = dataclasses.field(default_factory=dict)
    browser_resource_url: str = "about:blank"
    ide_bridge_url: str = ""
    owned_ide_demo_report: dict = dataclasses.field(default_factory=dict)
    cursor_bridge_url: str = ""
    cursor_draft_hook_report: dict = dataclasses.field(default_factory=dict)
    cursor_foreground_fallback_report: dict = dataclasses.field(default_factory=dict)
    cursor_background_safe_probe_report: dict = dataclasses.field(default_factory=dict)
    cursor_submit_report: dict = dataclasses.field(default_factory=dict)
    wechat_native_bridge_url: str = ""
    wechat_conversation_name: str = "File Transfer Assistant"
    wechat_background_screenshot_focus_stable: bool = True
    wechat_background_screenshot_count: int = 0
    wechat_background_screenshot_success_count: int = 0
    wechat_foreground_send_report: dict = dataclasses.field(default_factory=dict)
    wechat_native_bridge_send_report: dict = dataclasses.field(default_factory=dict)
    wechat_native_bridge_fixture_report: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ComputerOperationSurfaceReadiness:
    surface_id: str
    display_name: str
    required_action: str
    readiness_level: str
    operation_status: str
    verified: bool
    selected_transport: str
    transport_channel: str
    transport_capability_level: str
    route_id: str
    selected_route: str
    dispatch_decision: str
    connector_id: str = ""
    connector_ready: bool = False
    background_safe: bool = False
    foreground_required: bool = False
    blocked: bool = False
    can_execute_without_focus: bool = False
    can_write_without_focus: bool = False
    requires_user_confirmation: bool = False
    blocking_reason: str = ""
    required_evidence: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    verified_capabilities: tuple[str, ...] = ()
    partial_capabilities: tuple[str, ...] = ()
    fallback_transports: tuple[str, ...] = ()
    evidence: dict = dataclasses.field(default_factory=dict)
    target: dict = dataclasses.field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.readiness_level == BACKGROUND_EXECUTE

    def to_dict(self) -> dict:
        return {
            "surface_id": self.surface_id,
            "display_name": self.display_name,
            "required_action": self.required_action,
            "readiness_level": self.readiness_level,
            "operation_status": self.operation_status,
            "verified": self.verified,
            "ready": self.ready,
            "selected_transport": self.selected_transport,
            "transport_channel": self.transport_channel,
            "transport_capability_level": self.transport_capability_level,
            "route_id": self.route_id,
            "selected_route": self.selected_route,
            "dispatch_decision": self.dispatch_decision,
            "connector_id": self.connector_id,
            "connector_ready": self.connector_ready,
            "background_safe": self.background_safe,
            "foreground_required": self.foreground_required,
            "blocked": self.blocked,
            "can_execute_without_focus": self.can_execute_without_focus,
            "can_write_without_focus": self.can_write_without_focus,
            "requires_user_confirmation": self.requires_user_confirmation,
            "blocking_reason": self.blocking_reason,
            "required_evidence": list(self.required_evidence),
            "verification_requirements": list(self.verification_requirements),
            "risk_flags": list(self.risk_flags),
            "missing_capabilities": list(self.missing_capabilities),
            "verified_capabilities": list(self.verified_capabilities),
            "partial_capabilities": list(self.partial_capabilities),
            "fallback_transports": list(self.fallback_transports),
            "evidence": dict(self.evidence),
            "target": dict(self.target),
        }


@dataclasses.dataclass(frozen=True)
class ComputerOperationReadinessMatrixReport:
    surfaces: tuple[ComputerOperationSurfaceReadiness, ...]

    @property
    def mode(self) -> str:
        return "computer-operation-readiness-matrix"

    @property
    def safety_mode(self) -> str:
        return "plan_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def background_operation_ready(self) -> bool:
        return bool(
            self.surfaces
            and all(
                surface.readiness_level in {BACKGROUND_EXECUTE, READ_ONLY}
                for surface in self.surfaces
            )
            and any(surface.readiness_level == BACKGROUND_EXECUTE for surface in self.surfaces)
        )

    def readiness_counts(self) -> dict:
        return dict(sorted(Counter(item.readiness_level for item in self.surfaces).items()))

    def summary(self) -> dict:
        return {
            "surface_count": len(self.surfaces),
            "background_operation_ready": self.background_operation_ready,
            "background_execute_surfaces": [
                item.surface_id
                for item in self.surfaces
                if item.readiness_level == BACKGROUND_EXECUTE
            ],
            "background_execute_verified_surfaces": [
                item.surface_id
                for item in self.surfaces
                if item.operation_status == BACKGROUND_EXECUTE_VERIFIED
            ],
            "background_draft_surfaces": [
                item.surface_id
                for item in self.surfaces
                if "background_draft_injection" in item.verified_capabilities
            ],
            "foreground_send_surfaces": [
                item.surface_id
                for item in self.surfaces
                if "foreground_file_transfer_send" in item.verified_capabilities
            ],
            "read_only_surfaces": [
                item.surface_id for item in self.surfaces if item.readiness_level == READ_ONLY
            ],
            "foreground_required_surfaces": [
                item.surface_id
                for item in self.surfaces
                if item.readiness_level == FOREGROUND_REQUIRED
            ],
            "blocked_surfaces": [
                item.surface_id for item in self.surfaces if item.readiness_level == BLOCKED
            ],
            "readiness_counts": self.readiness_counts(),
            "write_ready_count": sum(
                1 for item in self.surfaces if item.can_write_without_focus
            ),
            "verified_background_execute_count": sum(
                1
                for item in self.surfaces
                if item.operation_status == BACKGROUND_EXECUTE_VERIFIED
            ),
            "verified_background_draft_count": sum(
                1
                for item in self.surfaces
                if "background_draft_injection" in item.verified_capabilities
            ),
            "connector_ready_count": sum(1 for item in self.surfaces if item.connector_ready),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "background_operation_ready": self.background_operation_ready,
            "summary": self.summary(),
            "surfaces": [item.to_dict() for item in self.surfaces],
        }


@dataclasses.dataclass(frozen=True)
class _SurfaceSpec:
    surface_id: str
    display_name: str
    required_action: str
    target: object
    intent: ControlIntent
    required_evidence: tuple[str, ...] = ()
    evidence: dict = dataclasses.field(default_factory=dict)


def build_computer_operation_readiness_matrix(
    *,
    options: ComputerOperationReadinessOptions | None = None,
    fabric: Optional[ControlFabric] = None,
) -> ComputerOperationReadinessMatrixReport:
    active_options = options or ComputerOperationReadinessOptions()
    active_fabric = fabric or ControlFabric.with_default_connectors()
    surface_readinesses = []
    for spec in _surface_specs(active_options):
        if spec.surface_id == "ide":
            surface_readinesses.append(
                _ide_extension_readiness(active_fabric, active_options, spec)
            )
            surface_readinesses.append(_cursor_agent_readiness(active_options))
        elif spec.surface_id == "wechat":
            surface_readinesses.append(
                _wechat_readiness(active_fabric, active_options, spec)
            )
        else:
            surface_readinesses.append(_surface_readiness(active_fabric, spec))
    surfaces = tuple(
        (
            _codex_app_server_readiness(active_options),
            _browser_devtools_readiness(active_fabric, active_options),
            *surface_readinesses,
        )
    )
    return ComputerOperationReadinessMatrixReport(surfaces=surfaces)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a plan-only readiness matrix for computer operation surfaces."
    )
    parser.add_argument("--workspace-path", default="", help="Workspace path used for terminal/git routes.")
    parser.add_argument("--codex-app-server-ws-url", default="", help="Owned Codex app-server WebSocket endpoint.")
    parser.add_argument(
        "--codex-app-server-turn-start-report",
        default="",
        help="JSON file containing a strict Codex app-server turn/start execution report.",
    )
    parser.add_argument("--browser-debugger-url", default="", help="Owned browser DevTools endpoint.")
    parser.add_argument(
        "--owned-browser-demo-report",
        default="",
        help="JSON file from owned_browser_safe_operation_demo.",
    )
    parser.add_argument("--browser-resource-url", default="about:blank", help="Owned browser target URL.")
    parser.add_argument("--ide-bridge-url", default="", help="IDE extension bridge URL.")
    parser.add_argument(
        "--owned-ide-demo-report",
        default="",
        help="JSON file from owned_ide_live_bridge_demo.",
    )
    parser.add_argument("--cursor-bridge-url", default="", help="Cursor live bridge URL.")
    parser.add_argument(
        "--cursor-draft-hook-report",
        default="",
        help="JSON file from cursor_draft_hook_validation.",
    )
    parser.add_argument(
        "--cursor-foreground-fallback-report",
        default="",
        help="JSON file from guarded Cursor UIA/clipboard fallback validation.",
    )
    parser.add_argument(
        "--cursor-background-safe-probe-report",
        default="",
        help="JSON file from Cursor background-safe UIA probe.",
    )
    parser.add_argument(
        "--cursor-submit-report",
        default="",
        help="JSON file from a strict Cursor assistant submit/readback proof.",
    )
    parser.add_argument("--wechat-native-bridge-url", default="", help="WeChat native bridge URL.")
    parser.add_argument("--wechat-conversation-name", default="File Transfer Assistant")
    parser.add_argument("--wechat-background-screenshot-count", type=int, default=0)
    parser.add_argument("--wechat-background-screenshot-success-count", type=int, default=0)
    parser.add_argument(
        "--wechat-foreground-send-report",
        default="",
        help="JSON file from the explicit opt-in WeChat File Transfer Assistant send probe.",
    )
    parser.add_argument(
        "--wechat-native-bridge-send-report",
        default="",
        help="JSON file from a real WeChat native bridge send/readback proof.",
    )
    parser.add_argument(
        "--wechat-native-bridge-fixture-report",
        default="",
        help="JSON file from the owned local WeChat native bridge fixture smoke.",
    )
    parser.add_argument(
        "--wechat-background-screenshot-focus-unstable",
        action="store_true",
        help="Mark WeChat background screenshot focus evidence as unstable.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print matrix JSON.")
    args = parser.parse_args(argv)

    report = build_computer_operation_readiness_matrix(
        options=ComputerOperationReadinessOptions(
            workspace_path=args.workspace_path,
            codex_app_server_ws_url=args.codex_app_server_ws_url,
            codex_app_server_turn_start_report=_load_codex_turn_start_report_file(
                args.codex_app_server_turn_start_report
            ),
            browser_debugger_url=args.browser_debugger_url,
            owned_browser_demo_report=_load_json_file(args.owned_browser_demo_report),
            browser_resource_url=args.browser_resource_url,
            ide_bridge_url=args.ide_bridge_url,
            owned_ide_demo_report=_load_json_file(args.owned_ide_demo_report),
            cursor_bridge_url=args.cursor_bridge_url,
            cursor_draft_hook_report=_load_json_file(args.cursor_draft_hook_report),
            cursor_foreground_fallback_report=_load_json_file(
                args.cursor_foreground_fallback_report
            ),
            cursor_background_safe_probe_report=_load_json_file(
                args.cursor_background_safe_probe_report
            ),
            cursor_submit_report=_load_json_file(args.cursor_submit_report),
            wechat_native_bridge_url=args.wechat_native_bridge_url,
            wechat_conversation_name=args.wechat_conversation_name,
            wechat_background_screenshot_focus_stable=not bool(
                args.wechat_background_screenshot_focus_unstable
            ),
            wechat_background_screenshot_count=args.wechat_background_screenshot_count,
            wechat_background_screenshot_success_count=args.wechat_background_screenshot_success_count,
            wechat_foreground_send_report=_load_json_file(
                args.wechat_foreground_send_report
            ),
            wechat_native_bridge_send_report=_load_json_file(
                args.wechat_native_bridge_send_report
            ),
            wechat_native_bridge_fixture_report=_load_json_file(
                args.wechat_native_bridge_fixture_report
            ),
        )
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        summary = data["summary"]
        _write_stdout(
            "Computer operation readiness: "
            f"surfaces={summary['surface_count']} "
            f"background_execute={len(summary['background_execute_surfaces'])} "
            f"read_only={len(summary['read_only_surfaces'])} "
            f"foreground_required={len(summary['foreground_required_surfaces'])} "
            f"blocked={len(summary['blocked_surfaces'])}"
        )
    return 0


def _surface_specs(options: ComputerOperationReadinessOptions) -> tuple[_SurfaceSpec, ...]:
    workspace_path = _workspace_path(options.workspace_path)
    return (
        _SurfaceSpec(
            surface_id="terminal",
            display_name="Terminal",
            required_action="run_command",
            target=ConnectorTarget(
                process_name="pwsh.exe",
                window_title="Managed PowerShell",
                workspace_path=workspace_path,
                workspace_hint=workspace_path or "terminal",
            ),
            intent=ControlIntent(action="run_command", text="pwd"),
            required_evidence=("workspace_path", "exit_code", "stdout_stderr_capture"),
            evidence={"workspace_path": workspace_path, "workspace_exists": _path_exists(workspace_path)},
        ),
        _SurfaceSpec(
            surface_id="git",
            display_name="Git",
            required_action="git_status",
            target=ConnectorTarget(
                process_name="git.exe",
                window_title="Workspace Git",
                workspace_path=workspace_path,
                workspace_hint=workspace_path or "git",
            ),
            intent=ControlIntent(action="git_status", text="status --short"),
            required_evidence=("workspace_path", "git_exit_code", "git_stdout_capture"),
            evidence={"workspace_path": workspace_path, "workspace_exists": _path_exists(workspace_path)},
        ),
        _SurfaceSpec(
            surface_id="ide",
            display_name="IDE",
            required_action="send_message",
            target=ConnectorTarget(
                process_name="Cursor.exe",
                window_title="OpenWuKong - Cursor",
                workspace_path=workspace_path,
                ide_bridge_url=options.ide_bridge_url,
            ),
            intent=ControlIntent(action="send_message", text="OPENWUKONG_READINESS_PROBE"),
            required_evidence=(
                "ide_bridge_url",
                "ide_state_snapshot",
                "chat_or_command_readback",
                "zero_window_input",
            ),
            evidence={"ide_bridge_url_present": bool(options.ide_bridge_url.strip())},
        ),
        _SurfaceSpec(
            surface_id="office",
            display_name="Office",
            required_action="create_document",
            target=ConnectorTarget(
                process_name="WINWORD.EXE",
                window_title="Owned Word Document",
                workspace_path=workspace_path,
            ),
            intent=ControlIntent(action="create_document", text="OPENWUKONG_READINESS_PROBE"),
            required_evidence=(
                "owned_document_boundary",
                "office_object_model_connector",
                "document_readback",
                "foreground_stability",
            ),
            evidence={"office_connector_installed": False},
        ),
        _SurfaceSpec(
            surface_id="wechat",
            display_name="WeChat",
            required_action="send_message",
            target=ConnectorTarget(
                process_name="Weixin.exe",
                window_title="File Transfer Assistant - WeChat",
                conversation_name=options.wechat_conversation_name,
                wechat_native_bridge_url=options.wechat_native_bridge_url,
                background_screenshot_focus_stable=options.wechat_background_screenshot_focus_stable,
                background_screenshot_count=options.wechat_background_screenshot_count,
                background_screenshot_success_count=options.wechat_background_screenshot_success_count,
            ),
            intent=ControlIntent(
                action="send_message",
                text="OPENWUKONG_READINESS_PROBE",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
            required_evidence=(
                "wechat_native_bridge_url",
                "file_transfer_assistant_target",
                "background_screenshot_verified",
                "readback_markers",
                "zero_window_input",
            ),
            evidence={
                "wechat_native_bridge_url_present": bool(
                    options.wechat_native_bridge_url.strip()
                ),
                "wechat_conversation_name": options.wechat_conversation_name,
                "background_screenshot_focus_stable": bool(
                    options.wechat_background_screenshot_focus_stable
                ),
                "background_screenshot_count": int(
                    options.wechat_background_screenshot_count or 0
                ),
                "background_screenshot_success_count": int(
                    options.wechat_background_screenshot_success_count or 0
                ),
            },
        ),
        _SurfaceSpec(
            surface_id="generic_desktop",
            display_name="Generic Desktop",
            required_action="read_text",
            target=_generic_read_only_window(),
            intent=ControlIntent(action="read_text"),
            required_evidence=(
                "uia_structural_snapshot",
                "stable_window_identity",
                "semantic_locator_required_for_write",
            ),
            evidence={"generic_write_ready": False},
        ),
    )


def _browser_surface_spec(options: ComputerOperationReadinessOptions) -> _SurfaceSpec:
    return _SurfaceSpec(
        surface_id="browser",
        display_name="Browser",
        required_action="open_url",
        target=ConnectorTarget(
            process_name="chrome.exe",
            window_title="Owned Browser",
            debugger_url=options.browser_debugger_url,
            resource_url=options.browser_resource_url,
        ),
        intent=ControlIntent(action="open_url", url=options.browser_resource_url),
        required_evidence=(
            "owned_browser_profile",
            "browser_debugger_url",
            "dom_or_accessibility_readback",
            "zero_window_input",
        ),
        evidence={
            "browser_debugger_url_present": bool(options.browser_debugger_url.strip()),
            "browser_resource_url": options.browser_resource_url,
        },
    )


def _browser_devtools_readiness(
    fabric: ControlFabric,
    options: ComputerOperationReadinessOptions,
) -> ComputerOperationSurfaceReadiness:
    base = _surface_readiness(fabric, _browser_surface_spec(options))
    report = _dict_value(options.owned_browser_demo_report)
    verified = _owned_browser_demo_verified(report)
    if not report:
        return base
    if not verified:
        missing = _owned_browser_missing_evidence(report, verified=False)
        return dataclasses.replace(
            base,
            operation_status=BLOCKED_STATUS,
            verified=False,
            blocking_reason=base.blocking_reason
            or "missing_evidence:" + ",".join(missing),
            required_evidence=_unique((*base.required_evidence, *missing)),
            risk_flags=_unique((*base.risk_flags, "owned_browser_demo_not_verified")),
            missing_capabilities=_unique((*base.missing_capabilities, *missing)),
            evidence={
                **base.evidence,
                **_owned_browser_demo_evidence(report, verified=False),
            },
        )
    evidence = {
        **base.evidence,
        **_owned_browser_demo_evidence(report, verified=True),
    }
    return dataclasses.replace(
        base,
        readiness_level=BACKGROUND_EXECUTE,
        operation_status=BACKGROUND_EXECUTE_VERIFIED,
        verified=True,
        selected_transport="chrome-devtools-protocol",
        transport_channel="connector",
        transport_capability_level="background-native",
        route_id="browser-devtools-or-extension",
        selected_route="browser-devtools-or-extension",
        dispatch_decision="owned_browser_demo_verified",
        connector_id="browser",
        connector_ready=True,
        background_safe=True,
        foreground_required=False,
        blocked=False,
        can_execute_without_focus=True,
        can_write_without_focus=True,
        requires_user_confirmation=False,
        blocking_reason="",
        required_evidence=_unique(
            (
                "owned_browser_profile",
                "isolated_devtools_endpoint",
                "dom_marker_readback",
                "workflow_quality_checks",
                "zero_window_input",
                "owned_helper_cleanup",
            )
        ),
        verification_requirements=(
            "browser_devtools_health",
            "fabric_execution_gate",
            "dom_readback",
            "quality_checks_passed",
            "manifest_pid_tree_stop",
        ),
        risk_flags=(),
        missing_capabilities=(),
        evidence=evidence,
        target={
            "process_name": "chrome.exe",
            "window_title": "Owned Browser",
            "workspace_path": _workspace_path(options.workspace_path),
            "resource_url": str(
                _dict_value(report.get("controlled_page")).get("url", "")
                or _dict_value(_dict_value(report.get("browser_workflow")).get("final_page_identity")).get("href", "")
                or options.browser_resource_url
                or ""
            ),
        },
    )


def _ide_extension_readiness(
    fabric: ControlFabric,
    options: ComputerOperationReadinessOptions,
    spec: _SurfaceSpec,
) -> ComputerOperationSurfaceReadiness:
    base = _surface_readiness(fabric, spec)
    report = _dict_value(options.owned_ide_demo_report)
    verified = _owned_ide_demo_verified(report)
    if not report:
        return base
    if not verified:
        missing = _owned_ide_missing_evidence(report, verified=False)
        return dataclasses.replace(
            base,
            operation_status=BLOCKED_STATUS,
            verified=False,
            blocking_reason=base.blocking_reason
            or "missing_evidence:" + ",".join(missing),
            required_evidence=_unique((*base.required_evidence, *missing)),
            risk_flags=_unique((*base.risk_flags, "owned_ide_demo_not_verified")),
            missing_capabilities=_unique((*base.missing_capabilities, *missing)),
            evidence={
                **base.evidence,
                **_owned_ide_demo_evidence(report, verified=False),
            },
        )

    bridge = _dict_value(report.get("bridge"))
    evidence = {
        **base.evidence,
        **_owned_ide_demo_evidence(report, verified=True),
    }
    return dataclasses.replace(
        base,
        readiness_level=BACKGROUND_EXECUTE,
        operation_status=BACKGROUND_EXECUTE_VERIFIED,
        verified=True,
        selected_transport="vscode-extension-bridge",
        transport_channel="connector",
        transport_capability_level="background-native",
        route_id="ide-extension-connector",
        selected_route="ide-extension-connector",
        dispatch_decision="owned_ide_live_bridge_demo_verified",
        connector_id="ide-extension",
        connector_ready=True,
        background_safe=True,
        foreground_required=False,
        blocked=False,
        can_execute_without_focus=True,
        can_write_without_focus=True,
        requires_user_confirmation=False,
        blocking_reason="",
        required_evidence=_unique(
            (
                "owned_ide_bridge_url",
                "owned_scratch_workspace_binding",
                "ide_state_snapshot",
                "write_scratch_command_readback",
                "quality_checks_passed",
                "zero_window_keyboard_clipboard_input",
            )
        ),
        verification_requirements=(
            "ide_bridge_capabilities",
            "workspace_binding",
            "fabric_ownership_gate",
            "write_scratch_readback",
            "no_window_keyboard_clipboard_input",
        ),
        risk_flags=(),
        missing_capabilities=(),
        evidence=evidence,
        target={
            "process_name": "Cursor.exe",
            "window_title": "OpenWuKong - Cursor",
            "workspace_path": str(
                bridge.get("workspace_path", "") or _workspace_path(options.workspace_path)
            ),
            "resource_url": str(bridge.get("bridge_url", "") or options.ide_bridge_url),
        },
    )


def _cursor_agent_readiness(
    options: ComputerOperationReadinessOptions,
) -> ComputerOperationSurfaceReadiness:
    draft_report = _dict_value(options.cursor_draft_hook_report)
    foreground_report = _dict_value(options.cursor_foreground_fallback_report)
    background_safe_report = _dict_value(options.cursor_background_safe_probe_report)
    submit_report = _dict_value(options.cursor_submit_report)
    draft_verified = _cursor_draft_hook_verified(draft_report)
    foreground_fallback_verified = _cursor_foreground_fallback_verified(
        foreground_report
    )
    background_uia_requires_foreground = _cursor_background_uia_requires_foreground(
        background_safe_report
    )
    submit_verified = _cursor_submit_verified(submit_report)
    bridge_url = str(
        options.cursor_bridge_url
        or draft_report.get("bridge_url", "")
        or submit_report.get("bridge_url", "")
        or options.ide_bridge_url
        or ""
    ).strip()
    workspace_path = str(
        draft_report.get("workspace_path", "")
        or submit_report.get("workspace_path", "")
        or options.workspace_path
        or ""
    ).strip()
    verified_capabilities = []
    if draft_verified:
        verified_capabilities.append("background_draft_injection")
    if foreground_fallback_verified:
        verified_capabilities.append("foreground_uia_clipboard_draft_fallback")
    partial_capabilities = [
        "composer_send_dispatch_resolved_without_assistant_readback",
        "glass_agent_query_prefill_open_only",
    ]
    fallback_transports = (
        ("cursor-foreground-uia-clipboard",) if foreground_fallback_verified else ()
    )
    evidence = {
        "cursor_bridge_url_present": bool(bridge_url),
        "cursor_draft_hook_verified": draft_verified,
        "cursor_draft_hook_decision": str(draft_report.get("decision", "") or ""),
        "cursor_draft_hook_artifact_mode": str(draft_report.get("mode", "") or ""),
        "cursor_foreground_fallback_verified": foreground_fallback_verified,
        "cursor_foreground_fallback_write_method": str(
            foreground_report.get("write_method", "") or ""
        ),
        "cursor_background_uia_requires_foreground": background_uia_requires_foreground,
        "cursor_background_safe_probe_error": str(
            background_safe_report.get("error", "") or ""
        ),
        "cursor_submit_verified": submit_verified,
        "cursor_submit_decision": str(submit_report.get("decision", "") or ""),
        "draft_window_input_attempts": _nested_counter(
            draft_report, "window_input_attempts"
        ),
        "draft_keyboard_input_attempts": _nested_counter(
            draft_report, "keyboard_input_attempts"
        ),
        "draft_clipboard_write_attempts": _nested_counter(
            draft_report, "clipboard_write_attempts"
        ),
        "draft_foreground_changed": bool(draft_report.get("foreground_changed", False)),
        "foreground_fallback_uses_clipboard": str(
            foreground_report.get("write_method", "") or ""
        )
        == "clipboard_paste",
    }
    if submit_verified:
        return ComputerOperationSurfaceReadiness(
            surface_id="cursor",
            display_name="Cursor Agent",
            required_action="send_message",
            readiness_level=BACKGROUND_EXECUTE,
            operation_status=BACKGROUND_EXECUTE_VERIFIED,
            verified=True,
            selected_transport="cursor-native-submit-hook",
            transport_channel="ide_extension_bridge",
            transport_capability_level="background-native",
            route_id="cursor-native-submit-readback",
            selected_route="cursor-native-submit-readback",
            dispatch_decision="cursor_agent_submit_readback_verified",
            connector_id="cursor-native-submit-hook",
            connector_ready=True,
            background_safe=True,
            foreground_required=False,
            blocked=False,
            can_execute_without_focus=True,
            can_write_without_focus=True,
            requires_user_confirmation=True,
            blocking_reason="",
            required_evidence=(
                "submit_capable_cursor_native_hook",
                "assistant_response_marker_readback",
                "zero_window_keyboard_clipboard_input",
            ),
            verification_requirements=(
                "cursor_bridge_workspace_identity",
                "submitInitialLocalAgentMessage_or_submitChatMaybeAbortCurrent",
                "assistant_response_marker_readback",
                "no_foreground_keyboard_clipboard_input",
            ),
            risk_flags=(),
            missing_capabilities=(),
            verified_capabilities=_unique(
                (*verified_capabilities, "background_agent_submit_readback")
            ),
            partial_capabilities=(),
            fallback_transports=fallback_transports,
            evidence=evidence,
            target={
                "process_name": "Cursor.exe",
                "window_title": "Cursor Agent",
                "workspace_path": workspace_path,
                "resource_url": bridge_url,
            },
        )

    missing = (
        "cursor_submit_native_service_hook",
        "assistant_response_marker_readback",
    )
    return ComputerOperationSurfaceReadiness(
        surface_id="cursor",
        display_name="Cursor Agent",
        required_action="send_message",
        readiness_level=BLOCKED,
        operation_status=CURSOR_SUBMIT_BLOCKED,
        verified=False,
        selected_transport="cursor-draft-hook" if draft_verified else "none",
        transport_channel="ide_extension_bridge" if draft_verified else "none",
        transport_capability_level="background-draft" if draft_verified else BLOCKED,
        route_id="cursor-draft-hook" if draft_verified else "",
        selected_route="cursor-draft-hook" if draft_verified else "",
        dispatch_decision="cursor_agent_submit_readback_required",
        connector_id="cursor-draft-hook" if draft_verified else "",
        connector_ready=draft_verified,
        background_safe=False,
        foreground_required=foreground_fallback_verified,
        blocked=True,
        can_execute_without_focus=False,
        can_write_without_focus=draft_verified,
        requires_user_confirmation=True,
        blocking_reason="cursor_submit_readback_not_verified",
        required_evidence=(
            "submit_capable_cursor_native_hook",
            "assistant_response_marker_readback",
            "zero_window_keyboard_clipboard_input",
        ),
        verification_requirements=(
            "cursor_bridge_workspace_identity",
            "submitInitialLocalAgentMessage_or_submitChatMaybeAbortCurrent",
            "assistant_response_marker_readback",
            "no_foreground_keyboard_clipboard_input",
        ),
        risk_flags=_unique(
            (
                "dispatch_resolved_is_not_completion",
                "prefill_open_is_not_submit",
                "foreground_fallback_requires_focus_clipboard",
            )
        ),
        missing_capabilities=missing,
        verified_capabilities=_unique(verified_capabilities),
        partial_capabilities=_unique(partial_capabilities),
        fallback_transports=fallback_transports,
        evidence=evidence,
        target={
            "process_name": "Cursor.exe",
            "window_title": "Cursor Agent",
            "workspace_path": workspace_path,
            "resource_url": bridge_url,
        },
    )


def _wechat_readiness(
    fabric: ControlFabric,
    options: ComputerOperationReadinessOptions,
    spec: _SurfaceSpec,
) -> ComputerOperationSurfaceReadiness:
    base = _surface_readiness(fabric, spec)
    foreground_report = _dict_value(options.wechat_foreground_send_report)
    native_report = _wechat_native_send_report_from(
        options.wechat_native_bridge_send_report
    )
    fixture_report = _wechat_fixture_report_from(
        options.wechat_native_bridge_fixture_report
    )
    foreground_verified = _wechat_foreground_send_verified(foreground_report)
    native_verified = _wechat_native_bridge_send_verified(native_report)
    fixture_verified = _wechat_native_bridge_fixture_verified(fixture_report)
    native_route_ready = bool(
        base.connector_ready and base.selected_transport == "wechat-native-bridge"
    )

    verified_capabilities: list[str] = []
    partial_capabilities: list[str] = []
    fallback_transports: list[str] = []
    if foreground_verified:
        verified_capabilities.append("foreground_file_transfer_send")
        fallback_transports.append("foreground-keyboard-clipboard")
        if _wechat_foreground_post_send_readback_verified(foreground_report):
            verified_capabilities.append("foreground_post_send_marker_readback")
    if fixture_verified:
        partial_capabilities.append("native_bridge_fixture_send_verified")
    if native_route_ready:
        partial_capabilities.append("wechat_native_bridge_route_ready")
    if native_report and not native_verified:
        partial_capabilities.append("wechat_native_send_report_not_accepted")

    evidence = {
        **base.evidence,
        **_wechat_foreground_send_evidence(
            foreground_report, verified=foreground_verified
        ),
        **_wechat_native_send_evidence(native_report, verified=native_verified),
        **_wechat_fixture_evidence(fixture_report, verified=fixture_verified),
        "wechat_native_bridge_route_ready": native_route_ready,
    }
    target = {
        **base.target,
        "conversation_name": options.wechat_conversation_name,
        "resource_url": str(
            options.wechat_native_bridge_url
            or _dict_value(native_report.get("request")).get("bridge_url", "")
            or native_report.get("bridge_url", "")
            or ""
        ),
    }

    if native_verified:
        return dataclasses.replace(
            base,
            readiness_level=BACKGROUND_EXECUTE,
            operation_status=BACKGROUND_EXECUTE_VERIFIED,
            verified=True,
            selected_transport="wechat-native-bridge",
            transport_channel="connector",
            transport_capability_level="background-native",
            route_id="app-native-bridge-required",
            selected_route="app-native-bridge-required",
            dispatch_decision="wechat_native_bridge_send_readback_verified",
            connector_id="wechat-native-bridge",
            connector_ready=True,
            background_safe=True,
            foreground_required=False,
            blocked=False,
            can_execute_without_focus=True,
            can_write_without_focus=True,
            requires_user_confirmation=True,
            blocking_reason="",
            required_evidence=_unique(
                (
                    "wechat_native_bridge_url",
                    "file_transfer_assistant_target",
                    "background_screenshot_verified",
                    "native_send_report",
                    "readback_markers",
                    "zero_window_keyboard_clipboard_input",
                    "foreground_focus_stable",
                )
            ),
            verification_requirements=(
                "native_bridge_capabilities",
                "file_transfer_assistant_target_match",
                "native_send_readback",
                "no_window_keyboard_clipboard_input",
                "foreground_focus_stable",
            ),
            risk_flags=(),
            missing_capabilities=(),
            verified_capabilities=_unique(
                (*verified_capabilities, "background_native_file_transfer_send")
            ),
            partial_capabilities=_unique(partial_capabilities),
            fallback_transports=_unique(fallback_transports),
            evidence=evidence,
            target=target,
        )

    missing = _wechat_missing_capabilities(
        base,
        native_report=native_report,
        native_route_ready=native_route_ready,
    )
    common_updates = {
        "verified": False,
        "connector_ready": native_route_ready,
        "background_safe": False,
        "blocked": not foreground_verified,
        "can_execute_without_focus": False,
        "can_write_without_focus": False,
        "requires_user_confirmation": True,
        "blocking_reason": "wechat_native_send_readback_not_verified",
        "required_evidence": _unique(
            (
                *base.required_evidence,
                "native_send_report",
                "readback_markers",
                "zero_window_keyboard_clipboard_input",
                *missing,
            )
        ),
        "verification_requirements": _unique(
            (
                "native_bridge_capabilities",
                "file_transfer_assistant_target_match",
                "native_send_readback",
                "no_window_keyboard_clipboard_input",
                "foreground_focus_stable",
            )
        ),
        "missing_capabilities": missing,
        "verified_capabilities": _unique(verified_capabilities),
        "partial_capabilities": _unique(partial_capabilities),
        "fallback_transports": _unique(fallback_transports),
        "evidence": evidence,
        "target": target,
    }

    if foreground_verified:
        return dataclasses.replace(
            base,
            readiness_level=FOREGROUND_REQUIRED,
            operation_status=FOREGROUND_REQUIRED_STATUS,
            selected_transport="foreground-keyboard-clipboard",
            transport_channel="foreground_desktop_input",
            transport_capability_level="foreground-required",
            route_id="wechat-file-helper-foreground-send",
            selected_route="wechat-file-helper-foreground-send",
            dispatch_decision="wechat_foreground_file_transfer_send_verified",
            connector_id="wechat-send-probe",
            foreground_required=True,
            risk_flags=_unique(
                (
                    *base.risk_flags,
                    "foreground_focus_required",
                    "keyboard_input_used",
                    "clipboard_write_used",
                )
            ),
            **common_updates,
        )

    return dataclasses.replace(
        base,
        readiness_level=BLOCKED,
        operation_status=WECHAT_NATIVE_SEND_BLOCKED,
        selected_transport=base.selected_transport if native_route_ready else "none",
        transport_channel=base.transport_channel if native_route_ready else "none",
        transport_capability_level=base.transport_capability_level
        if native_route_ready
        else BLOCKED,
        route_id=base.route_id if native_route_ready else "",
        selected_route=base.selected_route if native_route_ready else "",
        dispatch_decision="wechat_native_send_readback_required",
        connector_id="wechat-native-bridge" if native_route_ready else "",
        foreground_required=False,
        risk_flags=_unique(
            (
                *base.risk_flags,
                "native_bridge_route_without_send_readback",
            )
        )
        if native_route_ready
        else base.risk_flags,
        **common_updates,
    )


def _codex_app_server_readiness(
    options: ComputerOperationReadinessOptions,
) -> ComputerOperationSurfaceReadiness:
    report = _dict_value(options.codex_app_server_turn_start_report)
    verified = _codex_app_server_turn_start_verified(report)
    ws_url = str(
        options.codex_app_server_ws_url
        or report.get("endpoint_url", "")
        or ""
    ).strip()
    ready = bool(ws_url and verified)
    missing = _codex_missing_evidence(ws_url=ws_url, turn_report=report, verified=verified)
    return ComputerOperationSurfaceReadiness(
        surface_id="codex",
        display_name="Codex",
        required_action="send_message",
        readiness_level=BACKGROUND_EXECUTE if ready else BLOCKED,
        operation_status=(
            BACKGROUND_EXECUTE_VERIFIED if ready else BLOCKED_STATUS
        ),
        verified=verified,
        selected_transport="codex-app-server-ws" if ws_url else "none",
        transport_channel="codex_app_server_ws" if ws_url else "none",
        transport_capability_level="background-native" if ws_url else BLOCKED,
        route_id="codex-app-server-turn-start" if ws_url else "",
        selected_route="codex-app-server-turn-start" if ws_url else "",
        dispatch_decision=(
            "codex_app_server_turn_start_verified"
            if verified
            else "codex_app_server_turn_start_required"
        ),
        connector_id="codex-app-server-ws" if ws_url else "",
        connector_ready=ready,
        background_safe=ready,
        blocked=not ready,
        can_execute_without_focus=ready,
        can_write_without_focus=ready,
        requires_user_confirmation=True,
        blocking_reason="" if ready else "missing_evidence:" + ",".join(missing),
        required_evidence=_unique(
            (
                "owned_codex_app_server_ws_url",
                "strict_assistant_marker_readback",
                "task_complete",
                "no_window_input",
                *missing,
            )
        ),
        verification_requirements=(
            "app_server_initialize_ok",
            "thread_start_verified",
            "turn_start_verified",
            "assistant_session_or_delta_readback",
            "no_window_input",
        ),
        risk_flags=() if ready else ("codex_app_server_turn_not_verified",),
        missing_capabilities=missing,
        evidence={
            "codex_app_server_ws_url_present": bool(ws_url),
            "turn_start_decision": str(report.get("decision", "") or ""),
            "turn_completed": bool(report.get("turn_completed", False)),
            "turn_status": str(report.get("turn_status", "") or ""),
            "foreground_no_steal_verified": bool(
                report.get("foreground_no_steal_verified", False)
            ),
            "strict_assistant_readback_verified": verified,
            "session_task_complete_seen": bool(
                report.get("session_task_complete_seen", False)
            ),
            "assistant_readback_text_length": len(
                str(report.get("assistant_readback_text", "") or "")
            ),
            "control_attempts": int(report.get("control_attempts", 0) or 0),
            "window_input_attempts": int(
                report.get("window_input_attempts", 0) or 0
            ),
        },
        target={
            "process_name": "codex.exe" if ws_url else "",
            "window_title": "Codex",
            "workspace_path": _workspace_path(options.workspace_path),
            "resource_url": ws_url,
        },
    )


def _surface_readiness(
    fabric: ControlFabric,
    spec: _SurfaceSpec,
) -> ComputerOperationSurfaceReadiness:
    dispatch = fabric.dispatch(spec.target, spec.intent)
    data = dispatch.to_dict()
    transport = dict(data.get("transport_capability", {}) or {})
    target = dict(data.get("target", {}) or {})
    level = _readiness_level(dispatch, data, transport)
    operation_status = _operation_status(level, verified=False)
    return ComputerOperationSurfaceReadiness(
        surface_id=spec.surface_id,
        display_name=spec.display_name,
        required_action=spec.required_action,
        readiness_level=level,
        operation_status=operation_status,
        verified=operation_status == BACKGROUND_EXECUTE_VERIFIED,
        selected_transport=_selected_transport(data, transport),
        transport_channel=str(transport.get("transport_channel", "") or "none"),
        transport_capability_level=str(transport.get("capability_level", "") or BLOCKED),
        route_id=str(transport.get("route_id", "") or data.get("route_plan", {}).get("primary_route", {}).get("route_id", "")),
        selected_route=str(data.get("selected_route", "") or transport.get("selected_route", "")),
        dispatch_decision=str(data.get("decision", "") or ""),
        connector_id=str(data.get("selected_connector_id", "") or ""),
        connector_ready=bool(data.get("connector_ready", False)),
        background_safe=bool(data.get("background_safe", False)),
        foreground_required=bool(data.get("foreground_required", False))
        or bool(transport.get("foreground_required", False)),
        blocked=bool(data.get("blocked", False)) or level == BLOCKED,
        can_execute_without_focus=bool(transport.get("can_execute_without_focus", False))
        and level in {BACKGROUND_EXECUTE, READ_ONLY},
        can_write_without_focus=_can_write_without_focus(data, transport, level),
        requires_user_confirmation=bool(
            transport.get("requires_user_confirmation", False)
            or data.get("transport_requires_user_confirmation", False)
        ),
        blocking_reason=_blocking_reason(spec, data, transport, level),
        required_evidence=_unique((*spec.required_evidence, *_missing_evidence(spec))),
        verification_requirements=_unique(transport.get("verification_requirements", ())),
        risk_flags=_unique((*_list_value(transport.get("risk_flags")), *_list_value(data.get("risks")))),
        missing_capabilities=_unique(data.get("missing_capabilities", ())),
        evidence={
            **spec.evidence,
            "dispatch_reason": str(data.get("reason", "") or ""),
            "no_foreground_required": bool(
                data.get("no_foreground_contract", {}).get("requires_no_foreground", False)
            ),
            "candidate_connector_ids": list(data.get("candidate_connector_ids", []) or []),
            "installed_connector_ids": list(data.get("installed_connector_ids", []) or []),
        },
        target={
            "process_name": target.get("process_name", ""),
            "window_title": target.get("window_title", ""),
            "workspace_path": target.get("workspace_path", ""),
            "resource_url": target.get("resource_url", ""),
        },
    )


def _readiness_level(
    dispatch: ControlDispatchReport,
    data: dict,
    transport: dict,
) -> str:
    if bool(data.get("foreground_required", False)) or bool(
        transport.get("foreground_required", False)
    ):
        return FOREGROUND_REQUIRED
    if bool(data.get("blocked", False)) or bool(transport.get("blocked", False)):
        return BLOCKED
    decision = str(data.get("decision", "") or "")
    capability_level = str(transport.get("capability_level", "") or "")
    can_execute = bool(transport.get("can_execute_without_focus", False))
    if (
        decision in {"dispatch_connector", "dispatch_background_uia"}
        and capability_level == "background-native"
        and can_execute
    ):
        return BACKGROUND_EXECUTE
    if (
        decision == "dispatch_background_uia"
        and capability_level == "background-read-only"
        and can_execute
    ):
        return READ_ONLY
    if decision == "dispatch_connector" and capability_level == "background-read-only":
        return READ_ONLY
    if dispatch.selected_route in {"uia-structural", "uia-structural-observe"} and can_execute:
        return READ_ONLY
    return BLOCKED


def _operation_status(level: str, *, verified: bool) -> str:
    if level == BACKGROUND_EXECUTE:
        return BACKGROUND_EXECUTE_VERIFIED if verified else BACKGROUND_EXECUTE_READY
    if level == READ_ONLY:
        return READ_ONLY_READY
    if level == FOREGROUND_REQUIRED:
        return FOREGROUND_REQUIRED_STATUS
    return BLOCKED_STATUS


def _codex_app_server_turn_start_verified(report: dict) -> bool:
    if not report:
        return False
    assistant_text = str(report.get("assistant_readback_text", "") or "")
    required_markers = [
        str(marker)
        for marker in _list_value(report.get("required_markers"))
        if str(marker or "")
    ]
    missing_markers = _list_value(report.get("missing_required_markers"))
    forbidden_seen = _list_value(report.get("seen_forbidden_markers"))
    required_markers_seen = bool(
        required_markers and all(marker in assistant_text for marker in required_markers)
    )
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "")
        == "codex_app_server_turn_start_verified"
        and _counter(report, "control_attempts") == 0
        and _counter(report, "window_input_attempts") == 0
        and _counter(report, "app_server_turn_start_attempts") == 1
        and bool(report.get("turn_completed", False))
        and str(report.get("turn_status", "") or "") == "completed"
        and bool(report.get("foreground_no_steal_verified", False))
        and not missing_markers
        and not forbidden_seen
        and required_markers_seen
    )


def _codex_missing_evidence(
    *,
    ws_url: str,
    turn_report: dict,
    verified: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not ws_url:
        missing.append("codex_app_server_ws_url_missing")
    if not turn_report:
        missing.append("codex_app_server_turn_start_report_missing")
    elif not verified:
        missing.append("codex_app_server_turn_start_not_verified")
    return tuple(missing)


def _owned_browser_demo_verified(report: dict) -> bool:
    if not report:
        return False
    workflow = _dict_value(report.get("browser_workflow"))
    quality_summary = _dict_value(workflow.get("quality_summary"))
    stop = _dict_value(report.get("readiness_stop"))
    cleanup = _dict_value(report.get("profile_cleanup"))
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "") == "owned_browser_demo_verified"
        and str(report.get("safety_mode", "") or "") == "isolated_owned_browser_devtools"
        and bool(report.get("control_allowed", False))
        and _counter(report, "control_attempts") > 0
        and not bool(report.get("desktop_control_allowed", False))
        and _counter(report, "desktop_control_attempts") == 0
        and _counter(report, "window_input_attempts") == 0
        and bool(workflow.get("ok", False))
        and _counter(workflow, "control_attempts") > 0
        and _counter(workflow, "step_count") >= 3
        and _counter(quality_summary, "failed") == 0
        and _counter(quality_summary, "passed") > 0
        and _owned_browser_readiness_started(report)
        and _owned_browser_stop_succeeded(stop)
        and bool(cleanup.get("attempted", False))
        and bool(cleanup.get("deleted", False))
    )


def _owned_browser_missing_evidence(
    report: dict,
    *,
    verified: bool,
) -> tuple[str, ...]:
    if verified:
        return ()
    if not report:
        return ("owned_browser_demo_report_missing",)
    missing: list[str] = []
    workflow = _dict_value(report.get("browser_workflow"))
    quality_summary = _dict_value(workflow.get("quality_summary"))
    if not report.get("ok", False):
        missing.append("owned_browser_demo_not_ok")
    if str(report.get("decision", "") or "") != "owned_browser_demo_verified":
        missing.append("owned_browser_demo_decision_not_verified")
    if bool(report.get("desktop_control_allowed", False)) or _counter(
        report, "desktop_control_attempts"
    ) != 0 or _counter(report, "window_input_attempts") != 0:
        missing.append("desktop_or_window_input_seen")
    if not bool(workflow.get("ok", False)):
        missing.append("browser_workflow_not_ok")
    if _counter(quality_summary, "failed") != 0 or _counter(quality_summary, "passed") <= 0:
        missing.append("browser_quality_checks_not_passed")
    if not _owned_browser_readiness_started(report):
        missing.append("owned_browser_readiness_not_started")
    if not _owned_browser_stop_succeeded(_dict_value(report.get("readiness_stop"))):
        missing.append("owned_browser_stop_not_verified")
    if not bool(_dict_value(report.get("profile_cleanup")).get("deleted", False)):
        missing.append("owned_browser_profile_not_deleted")
    return tuple(missing)


def _owned_browser_demo_evidence(report: dict, *, verified: bool) -> dict:
    workflow = _dict_value(report.get("browser_workflow"))
    quality_summary = _dict_value(workflow.get("quality_summary"))
    controlled_page = _dict_value(report.get("controlled_page"))
    final_identity = _dict_value(workflow.get("final_page_identity"))
    return {
        "owned_browser_demo_verified": verified,
        "owned_browser_demo_decision": str(report.get("decision", "") or ""),
        "owned_browser_control_attempts": _counter(report, "control_attempts"),
        "desktop_control_attempts": _counter(report, "desktop_control_attempts"),
        "window_input_attempts": _counter(report, "window_input_attempts"),
        "browser_workflow_ok": bool(workflow.get("ok", False)),
        "browser_workflow_step_count": _counter(workflow, "step_count"),
        "browser_workflow_control_attempts": _counter(workflow, "control_attempts"),
        "browser_quality_failed": _counter(quality_summary, "failed"),
        "browser_quality_passed": _counter(quality_summary, "passed"),
        "controlled_page_marker": str(controlled_page.get("marker", "") or ""),
        "controlled_page_url": str(controlled_page.get("url", "") or ""),
        "final_page_href": str(final_identity.get("href", "") or ""),
        "readiness_started": _owned_browser_readiness_started(report),
        "owned_browser_stop_succeeded": _owned_browser_stop_succeeded(
            _dict_value(report.get("readiness_stop"))
        ),
        "profile_cleanup_deleted": bool(
            _dict_value(report.get("profile_cleanup")).get("deleted", False)
        ),
    }


def _owned_browser_readiness_started(report: dict) -> bool:
    execution = _dict_value(report.get("readiness_execution"))
    for result in execution.get("results", ()) or ():
        item = _dict_value(result)
        if (
            str(item.get("action_id", "") or "") == "launch_browser_devtools_isolated"
            and str(item.get("route_id", "") or "") == "browser-devtools-or-extension"
            and str(item.get("status", "") or "") == "started"
            and str(item.get("readiness_url", "") or "").startswith("http://127.0.0.1:")
        ):
            return True
    return False


def _owned_browser_stop_succeeded(stop: dict) -> bool:
    if _counter(stop, "stop_attempts") <= 0:
        return False
    results = [
        _dict_value(item)
        for item in stop.get("results", ()) or ()
        if isinstance(item, dict)
    ]
    return bool(
        results
        and all(
            str(item.get("status", "") or "") == "stopped"
            and not str(item.get("error", "") or "").strip()
            for item in results
        )
    )


def _owned_ide_demo_verified(report: dict) -> bool:
    if not report:
        return False
    quality = _dict_value(report.get("quality_summary"))
    workspace_binding = _dict_value(report.get("workspace_binding"))
    read_state = _dict_value(report.get("read_state_execution"))
    write = _dict_value(report.get("write_execution"))
    readback = _dict_value(report.get("readback"))
    action_payload = _dict_value(_dict_value(write.get("action_report")).get("payload"))
    ownership = _dict_value(write.get("ownership"))
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "") == "owned_ide_live_bridge_demo_verified"
        and str(report.get("safety_mode", "") or "") == "live_owned_ide_bridge_no_foreground"
        and bool(report.get("control_allowed", False))
        and _counter(report, "control_attempts") > 0
        and _counter(report, "desktop_control_attempts") == 0
        and _nested_counter(report, "window_input_attempts") == 0
        and _nested_counter(report, "keyboard_input_attempts") == 0
        and _nested_counter(report, "clipboard_write_attempts") == 0
        and str(report.get("selected_write_command", "") or "") == "openwukong.writeScratch"
        and bool(workspace_binding.get("ok", False))
        and bool(read_state.get("ok", False))
        and bool(write.get("ok", False))
        and bool(write.get("ownership_required", False))
        and bool(ownership.get("owned", False))
        and str(write.get("selected_route", "") or "") == "ide-extension-connector"
        and str(write.get("selected_connector_id", "") or "") == "ide-extension"
        and str(action_payload.get("bridge_action", "") or "") == "execute_command"
        and str(action_payload.get("command_id", "") or "") == "openwukong.writeScratch"
        and bool(readback.get("ok", False))
        and bool(readback.get("readback_verified", False))
        and str(readback.get("marker", "") or "")
        and str(readback.get("readback_text", "") or "") == str(readback.get("marker", "") or "")
        and _counter(quality, "failed") == 0
        and _counter(quality, "passed") > 0
    )


def _owned_ide_missing_evidence(
    report: dict,
    *,
    verified: bool,
) -> tuple[str, ...]:
    if verified:
        return ()
    if not report:
        return ("owned_ide_demo_report_missing",)
    missing: list[str] = []
    quality = _dict_value(report.get("quality_summary"))
    workspace_binding = _dict_value(report.get("workspace_binding"))
    read_state = _dict_value(report.get("read_state_execution"))
    write = _dict_value(report.get("write_execution"))
    readback = _dict_value(report.get("readback"))
    action_payload = _dict_value(_dict_value(write.get("action_report")).get("payload"))
    ownership = _dict_value(write.get("ownership"))
    if not report.get("ok", False):
        missing.append("owned_ide_demo_not_ok")
    if str(report.get("decision", "") or "") != "owned_ide_live_bridge_demo_verified":
        missing.append("owned_ide_demo_decision_not_verified")
    if str(report.get("safety_mode", "") or "") != "live_owned_ide_bridge_no_foreground":
        missing.append("owned_ide_safety_mode_not_live_no_foreground")
    if _counter(report, "control_attempts") <= 0:
        missing.append("ide_bridge_control_attempts_missing")
    if (
        _counter(report, "desktop_control_attempts") != 0
        or _nested_counter(report, "window_input_attempts") != 0
        or _nested_counter(report, "keyboard_input_attempts") != 0
        or _nested_counter(report, "clipboard_write_attempts") != 0
    ):
        missing.append("desktop_window_keyboard_or_clipboard_input_seen")
    if str(report.get("selected_write_command", "") or "") != "openwukong.writeScratch":
        missing.append("write_scratch_command_not_selected")
    if not bool(workspace_binding.get("ok", False)):
        missing.append("owned_workspace_binding_not_verified")
    if not bool(read_state.get("ok", False)):
        missing.append("ide_read_state_not_ok")
    if not bool(write.get("ok", False)):
        missing.append("ide_write_not_ok")
    if not (bool(write.get("ownership_required", False)) and bool(ownership.get("owned", False))):
        missing.append("fabric_ownership_not_verified")
    if (
        str(write.get("selected_route", "") or "") != "ide-extension-connector"
        or str(write.get("selected_connector_id", "") or "") != "ide-extension"
    ):
        missing.append("ide_extension_route_not_selected")
    if (
        str(action_payload.get("bridge_action", "") or "") != "execute_command"
        or str(action_payload.get("command_id", "") or "") != "openwukong.writeScratch"
    ):
        missing.append("write_scratch_payload_not_verified")
    if not (
        bool(readback.get("ok", False))
        and bool(readback.get("readback_verified", False))
        and str(readback.get("readback_text", "") or "") == str(readback.get("marker", "") or "")
    ):
        missing.append("ide_scratch_readback_not_verified")
    if _counter(quality, "failed") != 0 or _counter(quality, "passed") <= 0:
        missing.append("ide_quality_checks_not_passed")
    return tuple(missing)


def _owned_ide_demo_evidence(report: dict, *, verified: bool) -> dict:
    bridge = _dict_value(report.get("bridge"))
    quality = _dict_value(report.get("quality_summary"))
    readback = _dict_value(report.get("readback"))
    write = _dict_value(report.get("write_execution"))
    return {
        "owned_ide_demo_verified": verified,
        "owned_ide_demo_decision": str(report.get("decision", "") or ""),
        "owned_ide_control_attempts": _counter(report, "control_attempts"),
        "desktop_control_attempts": _counter(report, "desktop_control_attempts"),
        "window_input_attempts": _nested_counter(report, "window_input_attempts"),
        "keyboard_input_attempts": _nested_counter(report, "keyboard_input_attempts"),
        "clipboard_write_attempts": _nested_counter(report, "clipboard_write_attempts"),
        "ide_quality_failed": _counter(quality, "failed"),
        "ide_quality_passed": _counter(quality, "passed"),
        "ide_readback_verified": bool(readback.get("readback_verified", False)),
        "ide_readback_marker": str(readback.get("marker", "") or ""),
        "ide_readback_text_length": len(str(readback.get("readback_text", "") or "")),
        "ide_selected_write_command": str(report.get("selected_write_command", "") or ""),
        "ide_selected_route": str(write.get("selected_route", "") or ""),
        "ide_bridge_url": str(bridge.get("bridge_url", "") or ""),
        "ide_bridge_workspace_path": str(bridge.get("workspace_path", "") or ""),
    }


def _cursor_draft_hook_verified(report: dict) -> bool:
    if not report:
        return False
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "") == "cursor_draft_hook_validated"
        and str(report.get("safety_mode", "") or "")
        == "live_attach_draft_write_validation"
        and bool(report.get("readback_verified", False))
        and _counter(report, "draft_write_attempts") == 1
        and _counter(report, "bridge_send_attempts") == 0
        and _nested_counter(report, "window_input_attempts") == 0
        and _nested_counter(report, "keyboard_input_attempts") == 0
        and _nested_counter(report, "clipboard_write_attempts") == 0
        and not bool(report.get("foreground_changed", False))
        and not bool(report.get("system_dialog_detected", False))
        and str(report.get("bridge_url", "") or "").startswith("http://127.0.0.1:")
    )


def _cursor_foreground_fallback_verified(report: dict) -> bool:
    if not report:
        return False
    return bool(
        report.get("ok", False)
        and str(report.get("mode", "") or "") == "application-control-input-action"
        and str(report.get("safety_mode", "") or "") == "non_submit_write_verify_clear"
        and str(report.get("write_method", "") or "") == "clipboard_paste"
        and bool(report.get("token_visible_after_write", False))
        and not bool(report.get("token_visible_after_clear", True))
        and not bool(report.get("submitted", True))
        and _counter(report, "control_attempts") > 0
    )


def _cursor_background_uia_requires_foreground(report: dict) -> bool:
    if not report:
        return False
    return bool(
        str(report.get("mode", "") or "") == "application-control-input-action"
        and str(report.get("safety_mode", "") or "")
        == "background_semantic_write_verify_clear"
        and not bool(report.get("ok", True))
        and not bool(report.get("foreground_interaction_allowed", True))
        and bool(report.get("foreground_required", False))
        and str(report.get("error", "") or "") == "foreground_required"
    )


def _cursor_submit_verified(report: dict) -> bool:
    if not report:
        return False
    readback = _dict_value(
        report.get("cursor_transcript_readback_report")
        or report.get("readback_report")
    )
    response_role = str(readback.get("required_response_role", "assistant") or "assistant")
    readback_accepted = bool(
        readback.get("ok", False)
        and str(readback.get("decision", "") or "") == "cursor_transcript_readback_accepted"
        and response_role != "user"
        and not _list_value(readback.get("missing_required_markers"))
        and not _list_value(readback.get("forbidden_markers_found"))
        and _list_value(readback.get("required_markers_found"))
    )
    return bool(
        report.get("ok", False)
        and str(report.get("decision", "") or "")
        in {"app_bridge_send_accepted", "cursor_agent_send_accepted"}
        and _counter(report, "bridge_send_attempts") == 1
        and _counter(report, "window_input_attempts") == 0
        and readback_accepted
    )


def _wechat_foreground_send_verified(report: dict) -> bool:
    if not report:
        return False
    target_name = str(report.get("target_name", "") or "").strip().casefold()
    return bool(
        str(report.get("mode", "") or "") == "wechat-file-helper-send-probe"
        and str(report.get("safety_mode", "") or "") == "explicit_opt_in_real_send"
        and str(report.get("status", "") or "") == "sent"
        and bool(report.get("allow_send", False))
        and bool(report.get("control_allowed", False))
        and _counter(report, "send_attempts") == 1
        and _counter(report, "keyboard_input_attempts") > 0
        and _counter(report, "clipboard_write_attempts") > 0
        and _counter(report, "clipboard_restore_attempts") >= 1
        and _counter(report, "foreground_restore_attempts") >= 1
        and bool(report.get("target_verified", False))
        and target_name in {"文件传输助手", "file transfer assistant"}
        and bool(report.get("post_send_screenshot_bound", False))
        and str(report.get("transport", "") or "") == "foreground-keyboard-clipboard"
        and not str(report.get("error", "") or "").strip()
    )


def _wechat_foreground_post_send_readback_verified(report: dict) -> bool:
    verification = _dict_value(report.get("post_send_verification"))
    return bool(
        report
        and bool(report.get("post_send_verified", False))
        and bool(verification.get("verified", False))
        and not str(verification.get("error", "") or "").strip()
    )


def _wechat_native_bridge_send_verified(
    report: dict,
    *,
    allow_fixture: bool = False,
) -> bool:
    if not report:
        return False
    dry_run = _dict_value(report.get("dry_run_report"))
    request = _dict_value(report.get("request"))
    target = _dict_value(request.get("target"))
    if not allow_fixture and _wechat_native_bridge_send_report_is_fixture(report):
        return False
    return bool(
        str(report.get("mode", "") or "") == "wechat-native-bridge-send"
        and str(report.get("safety_mode", "") or "") == "native_bridge_execute"
        and bool(report.get("ok", False))
        and str(report.get("decision", "") or "")
        == "wechat_native_bridge_send_accepted"
        and bool(report.get("control_allowed", False))
        and _counter(report, "control_attempts") == 0
        and _counter(report, "send_attempts") == 1
        and _counter(report, "native_call_attempts") == 1
        and _nested_counter(report, "window_input_attempts") == 0
        and _nested_counter(report, "keyboard_input_attempts") == 0
        and _nested_counter(report, "clipboard_write_attempts") == 0
        and bool(report.get("foreground_focus_stable", False))
        and not _list_value(report.get("missing_required_markers"))
        and not _list_value(report.get("present_forbidden_markers"))
        and not str(report.get("error", "") or "").strip()
        and bool(dry_run.get("ok", False))
        and str(dry_run.get("decision", "") or "")
        == "wechat_native_bridge_dry_run_ready"
        and bool(dry_run.get("native_endpoint_ready", False))
        and bool(dry_run.get("target_ready", False))
        and bool(dry_run.get("send_action_ready", False))
        and bool(dry_run.get("background_safe", False))
        and bool(request.get("background_screenshot_verified", False))
        and bool(target.get("target_matched", False))
    )


def _wechat_native_bridge_fixture_verified(report: dict) -> bool:
    if not report:
        return False
    send_report = _wechat_native_send_report_from(report.get("send_report"))
    return bool(
        str(report.get("mode", "") or "") == "wechat-native-bridge-fixture-smoke"
        and str(report.get("safety_mode", "") or "")
        == "local_owned_wechat_native_bridge_fixture"
        and bool(report.get("ok", False))
        and str(report.get("decision", "") or "")
        == "wechat_native_bridge_fixture_smoke_verified"
        and _counter(report, "control_attempts") == 0
        and _nested_counter(report, "window_input_attempts") == 0
        and _counter(report, "native_call_attempts") == 1
        and _counter(report, "send_attempts") == 1
        and _wechat_native_bridge_send_verified(send_report, allow_fixture=True)
    )


def _wechat_native_bridge_send_report_is_fixture(report: dict) -> bool:
    dry_run = _dict_value(report.get("dry_run_report"))
    capability_report = _dict_value(dry_run.get("capability_report"))
    bridge = _dict_value(capability_report.get("bridge"))
    request = _dict_value(report.get("request"))
    target = _dict_value(request.get("target"))
    text = " ".join(
        str(value or "").casefold()
        for value in (
            bridge.get("name", ""),
            target.get("conversation_id", ""),
            target.get("name", ""),
        )
    )
    return "fixture" in text or "owned-fixture" in text


def _wechat_native_send_report_from(value: object) -> dict:
    report = _dict_value(value)
    if str(report.get("mode", "") or "") == "wechat-native-bridge-send":
        return report
    nested = _dict_value(report.get("send_report"))
    if str(nested.get("mode", "") or "") == "wechat-native-bridge-send":
        return nested
    fixture = _dict_value(report.get("wechat_native_bridge_fixture_smoke"))
    nested = _dict_value(fixture.get("send_report"))
    if str(nested.get("mode", "") or "") == "wechat-native-bridge-send":
        return nested
    return {}


def _wechat_fixture_report_from(value: object) -> dict:
    report = _dict_value(value)
    if str(report.get("mode", "") or "") == "wechat-native-bridge-fixture-smoke":
        return report
    nested = _dict_value(report.get("wechat_native_bridge_fixture_smoke"))
    if str(nested.get("mode", "") or "") == "wechat-native-bridge-fixture-smoke":
        return nested
    return {}


def _wechat_missing_capabilities(
    base: ComputerOperationSurfaceReadiness,
    *,
    native_report: dict,
    native_route_ready: bool,
) -> tuple[str, ...]:
    missing = list(base.missing_capabilities)
    if not native_route_ready:
        missing.append("wechat_native_bridge_route_not_ready")
    if not native_report:
        missing.append("wechat_native_bridge_send_report_missing")
    else:
        missing.append("wechat_native_bridge_send_report_not_accepted")
    missing.append("background_native_readback_not_verified")
    return _unique(missing)


def _wechat_foreground_send_evidence(report: dict, *, verified: bool) -> dict:
    verification = _dict_value(report.get("post_send_verification"))
    return {
        "wechat_foreground_send_verified": verified,
        "wechat_foreground_send_status": str(report.get("status", "") or ""),
        "wechat_foreground_target_name": str(report.get("target_name", "") or ""),
        "wechat_foreground_transport": str(report.get("transport", "") or ""),
        "wechat_foreground_send_attempts": _counter(report, "send_attempts"),
        "wechat_foreground_keyboard_input_attempts": _counter(
            report, "keyboard_input_attempts"
        ),
        "wechat_foreground_clipboard_write_attempts": _counter(
            report, "clipboard_write_attempts"
        ),
        "wechat_foreground_restore_attempts": _counter(
            report, "foreground_restore_attempts"
        ),
        "wechat_foreground_post_send_screenshot_bound": bool(
            report.get("post_send_screenshot_bound", False)
        ),
        "wechat_foreground_post_send_verified": bool(
            report.get("post_send_verified", False)
        ),
        "wechat_foreground_post_send_verification_method": str(
            verification.get("method", "") or ""
        ),
        "wechat_foreground_post_send_ocr_method": str(
            verification.get("ocr_method", "") or ""
        ),
        "wechat_foreground_post_send_normalized_marker_matched": bool(
            verification.get("normalized_marker_matched", False)
        ),
        "wechat_foreground_post_send_screenshot_path": str(
            report.get("post_send_screenshot_path", "") or ""
        ),
    }


def _wechat_native_send_evidence(report: dict, *, verified: bool) -> dict:
    dry_run = _dict_value(report.get("dry_run_report"))
    request = _dict_value(report.get("request"))
    target = _dict_value(request.get("target"))
    return {
        "wechat_native_send_verified": verified,
        "wechat_native_send_decision": str(report.get("decision", "") or ""),
        "wechat_native_send_is_fixture": _wechat_native_bridge_send_report_is_fixture(
            report
        )
        if report
        else False,
        "wechat_native_send_attempts": _counter(report, "send_attempts"),
        "wechat_native_call_attempts": _counter(report, "native_call_attempts"),
        "wechat_native_window_input_attempts": _nested_counter(
            report, "window_input_attempts"
        ),
        "wechat_native_keyboard_input_attempts": _nested_counter(
            report, "keyboard_input_attempts"
        ),
        "wechat_native_clipboard_write_attempts": _nested_counter(
            report, "clipboard_write_attempts"
        ),
        "wechat_native_foreground_focus_stable": bool(
            report.get("foreground_focus_stable", False)
        ),
        "wechat_native_missing_required_marker_count": len(
            _list_value(report.get("missing_required_markers"))
        ),
        "wechat_native_present_forbidden_marker_count": len(
            _list_value(report.get("present_forbidden_markers"))
        ),
        "wechat_native_dry_run_decision": str(dry_run.get("decision", "") or ""),
        "wechat_native_target_matched": bool(target.get("target_matched", False)),
        "wechat_native_background_screenshot_verified": bool(
            request.get("background_screenshot_verified", False)
        ),
    }


def _wechat_fixture_evidence(report: dict, *, verified: bool) -> dict:
    send_report = _wechat_native_send_report_from(report.get("send_report"))
    return {
        "wechat_native_fixture_verified": verified,
        "wechat_native_fixture_decision": str(report.get("decision", "") or ""),
        "wechat_native_fixture_send_attempts": _counter(report, "send_attempts"),
        "wechat_native_fixture_native_call_attempts": _counter(
            report, "native_call_attempts"
        ),
        "wechat_native_fixture_send_decision": str(
            send_report.get("decision", "") or ""
        ),
    }


def _nested_counter(data: object, key: str) -> int:
    if isinstance(data, dict):
        total = _counter(data, key)
        for value in data.values():
            total += _nested_counter(value, key)
        return total
    if isinstance(data, (list, tuple)):
        return sum(_nested_counter(item, key) for item in data)
    return 0


def _selected_transport(data: dict, transport: dict) -> str:
    connector_id = str(data.get("selected_connector_id", "") or "").strip()
    selected_route = str(data.get("selected_route", "") or "").strip()
    if connector_id and selected_route == "app-native-bridge-required":
        return connector_id
    return str(transport.get("selected_transport", "") or "none")


def _can_write_without_focus(data: dict, transport: dict, level: str) -> bool:
    if level != BACKGROUND_EXECUTE:
        return False
    if str(transport.get("capability_level", "") or "") != "background-native":
        return False
    action = str(transport.get("action", "") or data.get("intent", {}).get("action", "")).lower()
    return not _is_read_action(action)


def _blocking_reason(
    spec: _SurfaceSpec,
    data: dict,
    transport: dict,
    level: str,
) -> str:
    if level == BACKGROUND_EXECUTE:
        return ""
    if level == READ_ONLY:
        return "semantic_write_route_not_verified"
    for key in (data.get("reason"), transport.get("blocking_reason")):
        text = str(key or "").strip()
        if text:
            return text
    missing = _missing_evidence(spec)
    if missing:
        return "missing_evidence:" + ",".join(missing)
    return "background_operation_not_ready"


def _missing_evidence(spec: _SurfaceSpec) -> tuple[str, ...]:
    evidence = spec.evidence
    if spec.surface_id == "browser" and not evidence.get("browser_debugger_url_present"):
        return ("browser_debugger_url_missing",)
    if spec.surface_id in {"terminal", "git"} and not evidence.get("workspace_exists"):
        return ("workspace_path_missing_or_not_directory",)
    if spec.surface_id == "ide" and not evidence.get("ide_bridge_url_present"):
        return ("ide_bridge_url_missing",)
    if spec.surface_id == "office" and not evidence.get("office_connector_installed"):
        return ("office_object_model_connector_missing",)
    if spec.surface_id == "wechat":
        missing: list[str] = []
        if not evidence.get("wechat_native_bridge_url_present"):
            missing.append("wechat_native_bridge_url_missing")
        if int(evidence.get("background_screenshot_success_count", 0) or 0) <= 0:
            missing.append("background_screenshot_not_verified")
        if not bool(evidence.get("background_screenshot_focus_stable", True)):
            missing.append("background_screenshot_focus_unstable")
        return tuple(missing)
    return ()


def _generic_read_only_window() -> AccessibilityWindowSnapshot:
    return AccessibilityWindowSnapshot(
        pid=7001,
        process_name="reader.exe",
        window_title="Generic Document",
        class_name="Window",
        hwnd=7002,
        elements=(
            AccessibilityElementSnapshot(
                control_type="Document",
                name="Document",
                rect=(0, 0, 800, 600),
                is_enabled=True,
                patterns=("Text",),
            ),
        ),
    )


def _workspace_path(value: str) -> str:
    text = str(value or "").strip()
    return text or str(Path.cwd())


def _path_exists(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text and Path(text).is_dir())


def _is_read_action(action: str) -> bool:
    text = str(action or "").strip().lower()
    return text in {"inspect", "locate", "observe", "read", "read_page", "read_text", "screenshot"} or text.startswith("read_")


def _load_codex_turn_start_report_file(value: str) -> dict:
    text = str(value or "").strip()
    if not text:
        return {}
    path = Path(text)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _codex_turn_start_report_from_json(data)


def _load_json_file(value: str) -> dict:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(Path(text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _dict_value(data)


def _codex_turn_start_report_from_json(data: object) -> dict:
    root = _dict_value(data)
    if _looks_like_codex_turn_start_report(root):
        return root
    nested = _dict_value(root.get("codex_app_server_turn_start_report"))
    if _looks_like_codex_turn_start_report(nested):
        return nested
    report = _dict_value(root.get("report"))
    nested = _dict_value(report.get("codex_app_server_turn_start_report"))
    if _looks_like_codex_turn_start_report(nested):
        return nested
    for container in (root, report):
        cases = container.get("cases") if isinstance(container, dict) else None
        if not isinstance(cases, list):
            continue
        for case in cases:
            nested = _dict_value(_dict_value(case).get("codex_app_server_turn_start_report"))
            if _looks_like_codex_turn_start_report(nested):
                return nested
    return {}


def _looks_like_codex_turn_start_report(value: dict) -> bool:
    if not value:
        return False
    decision = str(value.get("decision", "") or "")
    mode = str(value.get("mode", "") or "")
    return bool(
        (
            decision.startswith("codex_app_server_turn_start_")
            and (
                "turn_completed" in value
                or "assistant_readback_text" in value
                or "turn_start_response" in value
            )
        )
        or mode == "codex-app-server-turn-start-execution"
    )


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _counter(report: dict, key: str) -> int:
    try:
        return int(report.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _unique(items: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in items if str(item or "").strip()))


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


if __name__ == "__main__":
    raise SystemExit(main())
