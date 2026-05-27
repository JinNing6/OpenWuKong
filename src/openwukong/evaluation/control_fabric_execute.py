# -*- coding: utf-8 -*-
"""Explicit Control Fabric execution CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_discovery import SessionDiscovery, SessionDiscoveryOptions
from openwukong.control.session_ownership import build_ownership_index


def main(
    argv: Optional[list[str]] = None,
    *,
    fabric: ControlFabric | None = None,
    browser_action_runner: Optional[object] = None,
    session_discovery: Optional[object] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicit Control Fabric execution behind route gates."
    )
    parser.add_argument("--process-name", default="")
    parser.add_argument("--window-title", default="")
    parser.add_argument("--resource-url", default="")
    parser.add_argument("--debugger-url", default="")
    parser.add_argument("--discover-sessions", action="store_true")
    parser.add_argument("--browser-debug-port", action="append", type=int, default=None)
    parser.add_argument("--discovery-timeout", type=float, default=0.2)
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--ide-bridge-url", default="")
    parser.add_argument("--readiness-manifest", action="append", default=None)
    parser.add_argument("--readiness-manifest-dir", action="append", default=None)
    parser.add_argument("--require-owned-session", action="store_true")
    parser.add_argument("--action", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--selector", default="")
    parser.add_argument("--value", default="")
    parser.add_argument("--allow-control", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    target = ConnectorTarget(
        process_name=args.process_name,
        window_title=args.window_title,
        resource_url=args.resource_url,
        debugger_url=args.debugger_url,
        workspace_path=args.workspace_path,
        ide_bridge_url=args.ide_bridge_url,
    )
    execution_target = _discover_target_if_requested(
        target,
        discover_sessions=args.discover_sessions,
        browser_debug_ports=tuple(args.browser_debug_port or ()),
        discovery_timeout=float(args.discovery_timeout or 0.2),
        session_discovery=session_discovery,
    )
    intent = ControlIntent(
        action=args.action,
        text=args.text,
        url=args.url,
        selector=args.selector,
        value=args.value,
    )
    ownership_paths = _manifest_paths_from_args(
        tuple(args.readiness_manifest or ()),
        tuple(args.readiness_manifest_dir or ()),
    )
    require_owned_session = bool(args.require_owned_session or ownership_paths)
    active_fabric = fabric or ControlFabric.with_default_connectors(
        ownership_index=build_ownership_index(ownership_paths),
        require_owned_session_for_execution=require_owned_session,
    )
    report = active_fabric.execute(
        execution_target,
        intent,
        allow_control=args.allow_control,
        browser_action_runner=browser_action_runner,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Control Fabric execute: "
            f"ok={data['ok']} "
            f"decision={data['decision']} "
            f"route={data['selected_route']} "
            f"attempts={data['control_attempts']}"
        )
    return 0 if report.ok else 1


def _discover_target_if_requested(
    target: ConnectorTarget,
    *,
    discover_sessions: bool,
    browser_debug_ports: tuple[int, ...],
    discovery_timeout: float,
    session_discovery: Optional[object],
) -> object:
    if not discover_sessions:
        return target
    discovery = session_discovery or SessionDiscovery(
        SessionDiscoveryOptions(
            browser_debug_ports=browser_debug_ports or SessionDiscoveryOptions().browser_debug_ports,
            request_timeout=max(0.05, float(discovery_timeout)),
        )
    )
    enrich = getattr(discovery, "enrich")
    return enrich(target)


def _manifest_paths_from_args(paths: tuple[str, ...], dirs: tuple[str, ...]) -> tuple[Path, ...]:
    collected: list[Path] = []
    for value in paths or ():
        path = Path(str(value))
        if path.is_file():
            collected.append(path)
    for value in dirs or ():
        directory = Path(str(value))
        if not directory.is_dir():
            continue
        collected.extend(sorted(directory.glob("*.json")))
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in collected:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)


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
