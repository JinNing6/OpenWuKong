# -*- coding: utf-8 -*-
"""CLI for plan-only connector session readiness launch helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from openwukong.control.session_readiness_plan import (
    SessionReadinessLauncher,
    SessionReadinessPlanOptions,
    SessionReadinessTerminator,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)


def main(
    argv: Optional[list[str]] = None,
    *,
    launcher: SessionReadinessLauncher | None = None,
    terminator: SessionReadinessTerminator | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build, execute, or stop connector session readiness helper reports."
    )
    parser.add_argument("--route", action="append", default=None, help="Route id to make discoverable.")
    parser.add_argument("--browser-executable", default="chrome.exe")
    parser.add_argument("--browser-debug-port", type=int, default=9222)
    parser.add_argument("--browser-user-data-dir", default="logs/runtime/browser-devtools-profile")
    parser.add_argument("--browser-url", default="about:blank")
    parser.add_argument("--ide-executable", default="cursor.exe")
    parser.add_argument("--ide-user-data-dir", default="logs/runtime/ide-bridge-user-data")
    parser.add_argument("--ide-extensions-dir", default="logs/runtime/ide-bridge-extensions")
    parser.add_argument("--ide-extension-dir", default="extensions/openwukong-vscode")
    parser.add_argument("--ide-bridge-host", default="127.0.0.1")
    parser.add_argument("--ide-bridge-port", type=int, default=8787)
    parser.add_argument("--agent-bridge-python-executable", default="")
    parser.add_argument("--agent-bridge-agent", default="agent app")
    parser.add_argument("--agent-bridge-agent-id", default="")
    parser.add_argument("--agent-bridge-host", default="127.0.0.1")
    parser.add_argument("--agent-bridge-port", type=int, default=18888)
    parser.add_argument("--agent-bridge-debugger-url", default="")
    parser.add_argument(
        "--agent-bridge-registry-path",
        default="logs/runtime/agent-native-cdp-bridge/native-bridges.json",
    )
    parser.add_argument("--agent-bridge-process-name", default="")
    parser.add_argument("--agent-bridge-pid", type=int, default=0)
    parser.add_argument("--agent-bridge-hwnd", type=int, default=0)
    parser.add_argument("--agent-bridge-window-title", default="")
    parser.add_argument("--agent-bridge-project", default="")
    parser.add_argument("--agent-bridge-task", default="")
    parser.add_argument("--agent-bridge-target-title", default="")
    parser.add_argument("--agent-bridge-target-url", default="")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", default="logs/runtime/session-readiness/manifest.json")
    parser.add_argument("--stop-manifest", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.stop_manifest:
        report = stop_session_readiness_manifest(
            args.stop_manifest,
            terminator=terminator,
        )
        data = report.to_dict()
        _write_report_output(data, args.output)
        _write_report_stdout(data, args.json)
        return 0

    routes = tuple(args.route or ())
    if not routes:
        routes = (
            "browser-devtools-or-extension",
            "ide-extension-connector",
            "terminal-native-session",
        )
    options = SessionReadinessPlanOptions(
        browser_executable=args.browser_executable,
        browser_debug_port=args.browser_debug_port,
        browser_user_data_dir=args.browser_user_data_dir,
        browser_url=args.browser_url,
        ide_executable=args.ide_executable,
        ide_user_data_dir=args.ide_user_data_dir,
        ide_extensions_dir=args.ide_extensions_dir,
        ide_extension_dir=args.ide_extension_dir,
        ide_bridge_host=args.ide_bridge_host,
        ide_bridge_port=args.ide_bridge_port,
        workspace_root=args.workspace_root,
        agent_bridge_python_executable=(
            args.agent_bridge_python_executable
            or SessionReadinessPlanOptions().agent_bridge_python_executable
        ),
        agent_bridge_agent=args.agent_bridge_agent,
        agent_bridge_agent_id=args.agent_bridge_agent_id,
        agent_bridge_host=args.agent_bridge_host,
        agent_bridge_port=args.agent_bridge_port,
        agent_bridge_debugger_url=args.agent_bridge_debugger_url,
        agent_bridge_registry_path=args.agent_bridge_registry_path,
        agent_bridge_process_name=args.agent_bridge_process_name,
        agent_bridge_pid=args.agent_bridge_pid,
        agent_bridge_hwnd=args.agent_bridge_hwnd,
        agent_bridge_window_title=args.agent_bridge_window_title,
        agent_bridge_project_name=args.agent_bridge_project,
        agent_bridge_task_name=args.agent_bridge_task,
        agent_bridge_target_title=args.agent_bridge_target_title,
        agent_bridge_target_url=args.agent_bridge_target_url,
    )
    plan = build_session_readiness_plan(routes=routes, options=options)
    if args.execute:
        report = execute_session_readiness_plan(
            plan,
            manifest_path=args.manifest,
            launcher=launcher,
        )
    else:
        report = plan
    data = report.to_dict()
    _write_report_output(data, args.output)
    _write_report_stdout(data, args.json)
    return 0


def _write_report_output(data: dict, output: str) -> None:
    if not output:
        return
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_report_stdout(data: dict, as_json: bool) -> None:
    if as_json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
        return
    mode = data.get("mode")
    if mode == "session-readiness-execution":
        _write_stdout(
            "Session readiness execution: "
            f"launch_attempts={data['launch_attempts']} "
            f"safety_mode={data['safety_mode']}"
        )
        return
    if mode == "session-readiness-stop":
        _write_stdout(
            "Session readiness stop: "
            f"stop_attempts={data['stop_attempts']} "
            f"safety_mode={data['safety_mode']}"
        )
        return
    _write_stdout(
        "Session readiness plan: "
        f"actions={data['action_count']} "
        f"safety_mode={data['safety_mode']}"
    )


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
