# -*- coding: utf-8 -*-
"""Compact status report for computer-operation readiness and artifacts."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.evaluation.computer_operation_readiness_matrix import (
    ComputerOperationReadinessOptions,
    build_computer_operation_readiness_matrix,
    _codex_turn_start_report_from_json,
)


OWNED_BROWSER_REPORT_NAME = "owned_browser_safe_operation_demo.json"
OWNED_IDE_REPORT_NAME = "owned_ide_safe_operation_demo.json"
OWNED_IDE_LIVE_REPORT_NAME = "owned_ide_live_bridge_demo.json"


@dataclasses.dataclass(frozen=True)
class ComputerOperationStatusReport:
    readiness_matrix: dict
    owned_browser_demo: dict
    owned_ide_demo: dict
    next_actions: tuple[str, ...] = ()
    output_path: str = ""
    markdown_path: str = ""

    @property
    def mode(self) -> str:
        return "computer-operation-status-report"

    @property
    def safety_mode(self) -> str:
        return "read_only_report"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def summary(self) -> dict:
        matrix_summary = dict(self.readiness_matrix.get("summary", {}) or {})
        owned_browser = dict(self.owned_browser_demo or {})
        owned_ide = dict(self.owned_ide_demo or {})
        return {
            "surface_count": int(matrix_summary.get("surface_count", 0) or 0),
            "background_execute_count": len(
                matrix_summary.get("background_execute_surfaces", []) or []
            ),
            "background_draft_count": len(
                matrix_summary.get("background_draft_surfaces", []) or []
            ),
            "foreground_send_count": len(
                matrix_summary.get("foreground_send_surfaces", []) or []
            ),
            "read_only_count": len(matrix_summary.get("read_only_surfaces", []) or []),
            "foreground_required_count": len(
                matrix_summary.get("foreground_required_surfaces", []) or []
            ),
            "blocked_count": len(matrix_summary.get("blocked_surfaces", []) or []),
            "write_ready_count": int(matrix_summary.get("write_ready_count", 0) or 0),
            "connector_ready_count": int(
                matrix_summary.get("connector_ready_count", 0) or 0
            ),
            "verified_background_execute_count": int(
                matrix_summary.get("verified_background_execute_count", 0) or 0
            ),
            "verified_background_draft_count": int(
                matrix_summary.get("verified_background_draft_count", 0) or 0
            ),
            "owned_browser_demo_status": str(owned_browser.get("status", "") or ""),
            "owned_browser_demo_ok": bool(owned_browser.get("ok", False)),
            "owned_browser_artifact_count": int(
                owned_browser.get("artifact_summary", {}).get("artifact_count", 0) or 0
            ),
            "owned_ide_demo_status": str(owned_ide.get("status", "") or ""),
            "owned_ide_demo_ok": bool(owned_ide.get("ok", False)),
            "owned_ide_artifact_count": int(
                owned_ide.get("artifact_summary", {}).get("artifact_count", 0) or 0
            ),
            "observed_prior_control_attempts": int(
                owned_browser.get("control_attempts_observed", 0) or 0
            )
            + int(owned_ide.get("control_attempts_observed", 0) or 0),
            "observed_prior_desktop_control_attempts": int(
                owned_browser.get("desktop_control_attempts_observed", 0) or 0
            )
            + int(owned_ide.get("desktop_control_attempts_observed", 0) or 0),
            "observed_prior_window_input_attempts": int(
                owned_browser.get("window_input_attempts_observed", 0) or 0
            )
            + int(owned_ide.get("window_input_attempts_observed", 0) or 0),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "summary": self.summary(),
            "readiness_matrix": dict(self.readiness_matrix),
            "owned_browser_demo": dict(self.owned_browser_demo),
            "owned_ide_demo": dict(self.owned_ide_demo),
            "next_actions": list(self.next_actions),
            "output_path": self.output_path,
            "markdown_path": self.markdown_path,
        }


def build_computer_operation_status_report(
    *,
    options: ComputerOperationReadinessOptions | None = None,
    owned_browser_report_path: str | Path = "",
    owned_ide_report_path: str | Path = "",
    runtime_root: str | Path = "logs/runtime",
    discover_owned_browser_report: bool = True,
    discover_owned_ide_report: bool = True,
) -> ComputerOperationStatusReport:
    owned_browser_summary = summarize_owned_browser_demo(
        owned_browser_report_path,
        runtime_root=runtime_root,
        discover=discover_owned_browser_report,
    )
    owned_ide_summary = summarize_owned_ide_demo(
        owned_ide_report_path,
        runtime_root=runtime_root,
        discover=discover_owned_ide_report,
    )
    active_options = _options_with_owned_ide_evidence(
        _options_with_owned_browser_evidence(
            options or ComputerOperationReadinessOptions(),
            owned_browser_summary,
        ),
        owned_ide_summary,
    )
    readiness = build_computer_operation_readiness_matrix(
        options=active_options,
    ).to_dict()
    return ComputerOperationStatusReport(
        readiness_matrix=readiness,
        owned_browser_demo=owned_browser_summary,
        owned_ide_demo=owned_ide_summary,
        next_actions=_next_actions(readiness, owned_browser_summary, owned_ide_summary),
    )


def summarize_owned_browser_demo(
    report_path: str | Path = "",
    *,
    runtime_root: str | Path = "logs/runtime",
    discover: bool = True,
) -> dict:
    path = _resolve_owned_browser_report_path(
        report_path,
        runtime_root=runtime_root,
        discover=discover,
    )
    if path is None:
        return {
            "status": "not_provided",
            "ok": False,
            "report_path": "",
            "trajectory_path": "",
            "artifact_summary": _empty_artifact_summary("not_provided"),
        }
    if not path.is_file():
        return {
            "status": "missing",
            "ok": False,
            "report_path": str(path),
            "trajectory_path": "",
            "error": "owned_browser_report_missing",
            "artifact_summary": _empty_artifact_summary("missing"),
        }

    data = _load_json(path)
    if not data:
        return {
            "status": "invalid",
            "ok": False,
            "report_path": str(path),
            "trajectory_path": "",
            "error": "owned_browser_report_invalid_json",
            "artifact_summary": _empty_artifact_summary("invalid"),
        }

    trajectory_path = _resolve_report_relative(
        data.get("trajectory_path", ""),
        base=path.parent,
    )
    artifact_summary = _trajectory_artifact_summary(trajectory_path)
    workflow = dict(data.get("browser_workflow", {}) or {})
    quality = dict(workflow.get("quality_summary", {}) or {})
    readiness_url = _first_started_readiness_url(
        dict(data.get("readiness_execution", {}) or {})
    )
    controlled_page = dict(data.get("controlled_page", {}) or {})
    ok = bool(data.get("ok", False))
    return {
        "status": "verified" if ok else "failed",
        "ok": ok,
        "decision": str(data.get("decision", "") or ""),
        "report_path": str(path),
        "trajectory_path": str(trajectory_path) if trajectory_path else "",
        "readiness_url": readiness_url,
        "controlled_page_url": str(controlled_page.get("url", "") or ""),
        "control_attempts_observed": int(data.get("control_attempts", 0) or 0),
        "desktop_control_attempts_observed": int(
            data.get("desktop_control_attempts", 0) or 0
        ),
        "window_input_attempts_observed": int(
            data.get("window_input_attempts", 0) or 0
        ),
        "quality_failed": int(quality.get("failed", 0) or 0),
        "quality_passed": int(quality.get("passed", 0) or 0),
        "profile_deleted": bool(data.get("profile_cleanup", {}).get("deleted", False)),
        "matrix_evidence": _owned_browser_matrix_evidence(data),
        "artifact_summary": artifact_summary,
        "error": str(data.get("error", "") or ""),
    }


def summarize_owned_ide_demo(
    report_path: str | Path = "",
    *,
    runtime_root: str | Path = "logs/runtime",
    discover: bool = True,
) -> dict:
    path = _resolve_owned_ide_report_path(
        report_path,
        runtime_root=runtime_root,
        discover=discover,
    )
    if path is None:
        return {
            "status": "not_provided",
            "ok": False,
            "report_path": "",
            "trajectory_path": "",
            "artifact_summary": _empty_artifact_summary("not_provided"),
        }
    if not path.is_file():
        return {
            "status": "missing",
            "ok": False,
            "report_path": str(path),
            "trajectory_path": "",
            "error": "owned_ide_report_missing",
            "artifact_summary": _empty_artifact_summary("missing"),
        }

    data = _load_json(path)
    if not data:
        return {
            "status": "invalid",
            "ok": False,
            "report_path": str(path),
            "trajectory_path": "",
            "error": "owned_ide_report_invalid_json",
            "artifact_summary": _empty_artifact_summary("invalid"),
        }

    trajectory_path = _resolve_report_relative(
        data.get("trajectory_path", ""),
        base=path.parent,
    )
    bridge = dict(data.get("bridge", {}) or {})
    quality = dict(data.get("quality_summary", {}) or {})
    ok = bool(data.get("ok", False))
    return {
        "status": "verified" if ok else "failed",
        "ok": ok,
        "decision": str(data.get("decision", "") or ""),
        "report_path": str(path),
        "trajectory_path": str(trajectory_path) if trajectory_path else "",
        "readiness_url": str(bridge.get("bridge_url", "") or ""),
        "workspace_path": str(bridge.get("workspace_path", "") or ""),
        "control_attempts_observed": int(data.get("control_attempts", 0) or 0),
        "desktop_control_attempts_observed": int(
            data.get("desktop_control_attempts", 0) or 0
        ),
        "window_input_attempts_observed": int(
            data.get("window_input_attempts", 0) or 0
        ),
        "quality_failed": int(quality.get("failed", 0) or 0),
        "quality_passed": int(quality.get("passed", 0) or 0),
        "matrix_evidence": _owned_ide_matrix_evidence(data),
        "artifact_summary": _trajectory_artifact_summary(trajectory_path),
        "error": str(data.get("error", "") or ""),
    }


def render_computer_operation_status_markdown(
    report: ComputerOperationStatusReport | dict,
) -> str:
    data = report.to_dict() if hasattr(report, "to_dict") else dict(report)
    summary = dict(data.get("summary", {}) or {})
    readiness = dict(data.get("readiness_matrix", {}) or {})
    owned_browser = dict(data.get("owned_browser_demo", {}) or {})
    owned_ide = dict(data.get("owned_ide_demo", {}) or {})
    lines = [
        "# OpenWuKong Computer Operation Status",
        "",
        "## Summary",
        "",
        f"- Surfaces: {summary.get('surface_count', 0)}",
        f"- Background execute: {summary.get('background_execute_count', 0)}",
        f"- Background draft: {summary.get('background_draft_count', 0)}",
        f"- Foreground send: {summary.get('foreground_send_count', 0)}",
        f"- Read only: {summary.get('read_only_count', 0)}",
        f"- Foreground required: {summary.get('foreground_required_count', 0)}",
        f"- Blocked: {summary.get('blocked_count', 0)}",
        f"- Owned browser demo: {summary.get('owned_browser_demo_status', '')}",
        f"- Owned IDE demo: {summary.get('owned_ide_demo_status', '')}",
        f"- Report control attempts: {data.get('control_attempts', 0)}",
        f"- Observed prior control attempts: {summary.get('observed_prior_control_attempts', 0)}",
        f"- Observed prior window input attempts: {summary.get('observed_prior_window_input_attempts', 0)}",
        "",
        "## Surface Readiness",
        "",
        "| Surface | Level | Status | Transport | Connector | Blocking reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for surface in readiness.get("surfaces", ()) or ():
        if not isinstance(surface, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    surface.get("display_name", "") or surface.get("surface_id", ""),
                    surface.get("readiness_level", ""),
                    surface.get("operation_status", ""),
                    surface.get("selected_transport", ""),
                    surface.get("connector_id", ""),
                    surface.get("blocking_reason", ""),
                )
            )
            + " |"
        )

    artifact_summary = dict(owned_browser.get("artifact_summary", {}) or {})
    lines.extend(
        [
            "",
            "## Owned Browser Demo",
            "",
            f"- Status: {owned_browser.get('status', '')}",
            f"- Decision: {owned_browser.get('decision', '')}",
            f"- Report: {owned_browser.get('report_path', '')}",
            f"- Trajectory: {owned_browser.get('trajectory_path', '')}",
            f"- Artifacts: {artifact_summary.get('artifact_count', 0)}",
            "",
            "## Browser Artifact Roles",
            "",
        ]
    )
    roles = artifact_summary.get("roles", []) or []
    if roles:
        lines.extend(f"- {role}" for role in roles)
    else:
        lines.append("- none")

    ide_artifact_summary = dict(owned_ide.get("artifact_summary", {}) or {})
    lines.extend(
        [
            "",
            "## Owned IDE Demo",
            "",
            f"- Status: {owned_ide.get('status', '')}",
            f"- Decision: {owned_ide.get('decision', '')}",
            f"- Report: {owned_ide.get('report_path', '')}",
            f"- Trajectory: {owned_ide.get('trajectory_path', '')}",
            f"- Artifacts: {ide_artifact_summary.get('artifact_count', 0)}",
            "",
            "## IDE Artifact Roles",
            "",
        ]
    )
    ide_roles = ide_artifact_summary.get("roles", []) or []
    if ide_roles:
        lines.extend(f"- {role}" for role in ide_roles)
    else:
        lines.append("- none")

    lines.extend(["", "## Next Actions", ""])
    actions = data.get("next_actions", []) or ()
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a compact report for computer operation readiness."
    )
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--codex-app-server-ws-url", default="")
    parser.add_argument("--codex-app-server-turn-start-report", default="")
    parser.add_argument("--browser-debugger-url", default="")
    parser.add_argument("--browser-resource-url", default="about:blank")
    parser.add_argument("--ide-bridge-url", default="")
    parser.add_argument("--cursor-bridge-url", default="")
    parser.add_argument("--cursor-draft-hook-report", default="")
    parser.add_argument("--cursor-foreground-fallback-report", default="")
    parser.add_argument("--cursor-background-safe-probe-report", default="")
    parser.add_argument("--cursor-submit-report", default="")
    parser.add_argument("--wechat-native-bridge-url", default="")
    parser.add_argument("--wechat-conversation-name", default="File Transfer Assistant")
    parser.add_argument("--wechat-background-screenshot-count", type=int, default=0)
    parser.add_argument(
        "--wechat-background-screenshot-success-count",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--wechat-background-screenshot-focus-unstable",
        action="store_true",
    )
    parser.add_argument("--wechat-foreground-send-report", default="")
    parser.add_argument("--wechat-native-bridge-send-report", default="")
    parser.add_argument("--wechat-native-bridge-fixture-report", default="")
    parser.add_argument("--owned-browser-report", default="")
    parser.add_argument("--owned-ide-report", default="")
    parser.add_argument("--runtime-root", default="logs/runtime")
    parser.add_argument(
        "--no-discover-owned-browser-report",
        action="store_true",
        help="Do not scan runtime root for an owned browser demo report.",
    )
    parser.add_argument(
        "--no-discover-owned-ide-report",
        action="store_true",
        help="Do not scan runtime root for an owned IDE demo report.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--markdown-output", default="", help="Optional output Markdown path.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    args = parser.parse_args(argv)

    report = build_computer_operation_status_report(
        options=ComputerOperationReadinessOptions(
            workspace_path=args.workspace_path,
            codex_app_server_ws_url=args.codex_app_server_ws_url,
            codex_app_server_turn_start_report=_codex_turn_start_report_from_json(
                _load_json_file(args.codex_app_server_turn_start_report)
            ),
            browser_debugger_url=args.browser_debugger_url,
            browser_resource_url=args.browser_resource_url,
            ide_bridge_url=args.ide_bridge_url,
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
            wechat_background_screenshot_success_count=(
                args.wechat_background_screenshot_success_count
            ),
            wechat_foreground_send_report=_load_json_file(
                args.wechat_foreground_send_report
            ),
            wechat_native_bridge_send_report=_load_json_file(
                args.wechat_native_bridge_send_report
            ),
            wechat_native_bridge_fixture_report=_load_json_file(
                args.wechat_native_bridge_fixture_report
            ),
        ),
        owned_browser_report_path=args.owned_browser_report,
        owned_ide_report_path=args.owned_ide_report,
        runtime_root=args.runtime_root,
        discover_owned_browser_report=not bool(args.no_discover_owned_browser_report),
        discover_owned_ide_report=not bool(args.no_discover_owned_ide_report),
    )
    data = report.to_dict()
    markdown = render_computer_operation_status_markdown(report)

    output_path = ""
    markdown_path = ""
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        data["output_path"] = str(path)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        output_path = str(path)
    if args.markdown_output:
        path = Path(args.markdown_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        markdown_path = str(path)
        data["markdown_path"] = markdown_path
        if output_path:
            Path(output_path).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        summary = data["summary"]
        _write_stdout(
            "Computer operation status: "
            f"surfaces={summary['surface_count']} "
            f"background_execute={summary['background_execute_count']} "
            f"blocked={summary['blocked_count']} "
            f"owned_browser={summary['owned_browser_demo_status']} "
            f"owned_ide={summary['owned_ide_demo_status']} "
            f"artifacts={summary['owned_browser_artifact_count'] + summary['owned_ide_artifact_count']}"
        )
    return 0


def _options_with_owned_browser_evidence(
    options: ComputerOperationReadinessOptions,
    owned_summary: dict,
) -> ComputerOperationReadinessOptions:
    updates: dict = {}
    matrix_evidence = _dict_value(owned_summary.get("matrix_evidence"))
    if matrix_evidence and not options.owned_browser_demo_report:
        updates["owned_browser_demo_report"] = matrix_evidence
    readiness_url = str(owned_summary.get("readiness_url", "") or "").strip()
    if readiness_url and not options.browser_debugger_url.strip():
        updates["browser_debugger_url"] = readiness_url
        updates["browser_resource_url"] = str(
            owned_summary.get("controlled_page_url", "") or options.browser_resource_url
        )
    return dataclasses.replace(options, **updates) if updates else options


def _options_with_owned_ide_evidence(
    options: ComputerOperationReadinessOptions,
    owned_summary: dict,
) -> ComputerOperationReadinessOptions:
    updates: dict = {}
    matrix_evidence = _dict_value(owned_summary.get("matrix_evidence"))
    if matrix_evidence and not options.owned_ide_demo_report:
        updates["owned_ide_demo_report"] = matrix_evidence
    readiness_url = str(owned_summary.get("readiness_url", "") or "").strip()
    workspace_path = str(owned_summary.get("workspace_path", "") or options.workspace_path)
    if readiness_url and not options.ide_bridge_url.strip():
        updates["ide_bridge_url"] = readiness_url
    if workspace_path and not options.workspace_path:
        updates["workspace_path"] = workspace_path
    return dataclasses.replace(options, **updates) if updates else options


def _owned_browser_matrix_evidence(data: dict) -> dict:
    return {
        "mode": str(data.get("mode", "") or ""),
        "safety_mode": str(data.get("safety_mode", "") or ""),
        "ok": bool(data.get("ok", False)),
        "decision": str(data.get("decision", "") or ""),
        "control_allowed": bool(data.get("control_allowed", False)),
        "control_attempts": int(data.get("control_attempts", 0) or 0),
        "desktop_control_allowed": bool(data.get("desktop_control_allowed", False)),
        "desktop_control_attempts": int(data.get("desktop_control_attempts", 0) or 0),
        "window_input_attempts": int(data.get("window_input_attempts", 0) or 0),
        "controlled_page": _dict_value(data.get("controlled_page")),
        "readiness_execution": _dict_value(data.get("readiness_execution")),
        "browser_workflow": _dict_value(data.get("browser_workflow")),
        "readiness_stop": _dict_value(data.get("readiness_stop")),
        "profile_cleanup": _dict_value(data.get("profile_cleanup")),
    }


def _owned_ide_matrix_evidence(data: dict) -> dict:
    return {
        "mode": str(data.get("mode", "") or ""),
        "safety_mode": str(data.get("safety_mode", "") or ""),
        "ok": bool(data.get("ok", False)),
        "decision": str(data.get("decision", "") or ""),
        "control_allowed": bool(data.get("control_allowed", False)),
        "control_attempts": int(data.get("control_attempts", 0) or 0),
        "desktop_control_attempts": int(data.get("desktop_control_attempts", 0) or 0),
        "window_input_attempts": int(data.get("window_input_attempts", 0) or 0),
        "selected_write_command": str(data.get("selected_write_command", "") or ""),
        "bridge": _dict_value(data.get("bridge")),
        "workspace_binding": _dict_value(data.get("workspace_binding")),
        "read_state_execution": _dict_value(data.get("read_state_execution")),
        "write_execution": _dict_value(data.get("write_execution")),
        "readback": _dict_value(data.get("readback")),
        "quality_summary": _dict_value(data.get("quality_summary")),
    }


def _resolve_owned_browser_report_path(
    report_path: str | Path,
    *,
    runtime_root: str | Path,
    discover: bool,
) -> Path | None:
    text = str(report_path or "").strip()
    if text:
        return Path(text).expanduser().resolve()
    if not discover:
        return None
    return _discover_latest_owned_browser_report(runtime_root)


def _resolve_owned_ide_report_path(
    report_path: str | Path,
    *,
    runtime_root: str | Path,
    discover: bool,
) -> Path | None:
    text = str(report_path or "").strip()
    if text:
        return Path(text).expanduser().resolve()
    if not discover:
        return None
    return _discover_latest_report(
        runtime_root,
        (OWNED_IDE_REPORT_NAME, OWNED_IDE_LIVE_REPORT_NAME),
    )


def _discover_latest_owned_browser_report(runtime_root: str | Path) -> Path | None:
    return _discover_latest_report(runtime_root, OWNED_BROWSER_REPORT_NAME)


def _discover_latest_report(
    runtime_root: str | Path,
    filename: str | tuple[str, ...],
) -> Path | None:
    root = Path(runtime_root)
    if not root.is_dir():
        return None
    filenames = (filename,) if isinstance(filename, str) else tuple(filename)
    candidates = [
        path
        for name in filenames
        for path in root.rglob(name)
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime).resolve()


def _trajectory_artifact_summary(path: Path | None) -> dict:
    if path is None:
        return _empty_artifact_summary("not_provided")
    if not path.is_file():
        return _empty_artifact_summary("missing")
    data = _load_json(path)
    if not data:
        return _empty_artifact_summary("invalid")

    artifacts = []
    for step in data.get("steps", ()) or ():
        if not isinstance(step, dict):
            continue
        phase = str(step.get("phase", "") or "")
        for artifact in step.get("artifacts", ()) or ():
            if not isinstance(artifact, dict):
                continue
            artifact_path = _resolve_report_relative(
                artifact.get("path", ""),
                base=path.parent,
            )
            artifacts.append(
                {
                    "phase": phase,
                    "role": str(artifact.get("role", "") or ""),
                    "path": str(artifact_path) if artifact_path else "",
                    "exists": bool(artifact_path and artifact_path.is_file()),
                    "media_type": str(artifact.get("media_type", "") or ""),
                    "sha256": str(artifact.get("sha256", "") or ""),
                }
            )
    roles = _unique(item["role"] for item in artifacts)
    media_counts = dict(sorted(Counter(item["media_type"] for item in artifacts).items()))
    return {
        "status": "loaded",
        "trajectory_path": str(path),
        "step_count": int(data.get("step_count", len(data.get("steps", ()) or ())) or 0),
        "artifact_count": len(artifacts),
        "existing_artifact_count": sum(1 for item in artifacts if item["exists"]),
        "roles": roles,
        "media_type_counts": media_counts,
        "artifacts": artifacts,
    }


def _empty_artifact_summary(status: str) -> dict:
    return {
        "status": status,
        "trajectory_path": "",
        "step_count": 0,
        "artifact_count": 0,
        "existing_artifact_count": 0,
        "roles": [],
        "media_type_counts": {},
        "artifacts": [],
    }


def _next_actions(readiness: dict, owned_browser: dict, owned_ide: dict) -> tuple[str, ...]:
    surfaces = {
        str(surface.get("surface_id", "") or ""): surface
        for surface in readiness.get("surfaces", ()) or ()
        if isinstance(surface, dict)
    }
    actions: list[str] = []
    if surfaces.get("ide", {}).get("readiness_level") != "background_execute":
        actions.append("Provide or launch IDE bridge evidence, then run the IDE owned-session demo.")
    if surfaces.get("cursor", {}).get("readiness_level") != "background_execute":
        actions.append(
            "Build Cursor submit/readback evidence around a native submit hook or assistant transcript surface; keep draft and UIA fallback separate."
        )
    wechat = surfaces.get("wechat", {})
    wechat_caps = set(wechat.get("verified_capabilities", []) or [])
    if wechat.get("operation_status") != "background_execute_verified":
        if "foreground_file_transfer_send" in wechat_caps:
            actions.append(
                "Implement the real WeChat native File Transfer Assistant send/readback backend; foreground File Transfer Assistant send is verified but not background-safe."
            )
        else:
            actions.append(
                "Attach a real WeChat native bridge send/readback report before claiming background WeChat send readiness."
            )
    if surfaces.get("office", {}).get("readiness_level") == "blocked":
        actions.append("Add an Office object-model connector before claiming background Office write readiness.")
    if not owned_browser.get("ok", False):
        actions.append("Run the owned browser demo and attach its trajectory report.")
    if not owned_ide.get("ok", False):
        actions.append("Run the owned IDE bridge demo and attach its trajectory report.")
    return tuple(actions[:4])


def _first_started_readiness_url(data: dict) -> str:
    for result in data.get("results", ()) or ():
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") != "started":
            continue
        text = str(result.get("readiness_url", "") or "").strip()
        if text:
            return text
    return ""


def _resolve_report_relative(value: object, *, base: Path) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = base / path
        return path.resolve()
    except (OSError, ValueError):
        return None


def _load_json_file(value: str) -> dict:
    text = str(value or "").strip()
    if not text:
        return {}
    return _load_json(Path(text))


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _md_cell(value: object) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "\\|")
    return text.strip()


def _unique(items: Iterable[object]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item or "").strip()))


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
