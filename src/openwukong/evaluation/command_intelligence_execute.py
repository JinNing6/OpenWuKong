# -*- coding: utf-8 -*-
"""CLI entrypoint for the owned workspace command runner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.command_runner import (
    CommandExecutionRequest,
    CommandRunner,
    build_command_execution_policy,
)
from openwukong.control.session_ownership import build_ownership_index


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an argv-only command through the Command Intelligence runner."
    )
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--profile", default="workspace-write")
    parser.add_argument("--effect", action="append", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--audit-log", default="")
    parser.add_argument("--readiness-manifest", action="append", default=None)
    parser.add_argument("--readiness-manifest-dir", action="append", default=None)
    parser.add_argument("--require-owned-session", action="store_true")
    parser.add_argument("--reason", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    command_argv = _clean_remainder(tuple(args.argv or ()))
    workspace_path = str(args.workspace_path or "").strip()
    cwd = str(args.cwd or workspace_path or os.getcwd()).strip()
    ownership_paths = _manifest_paths_from_args(
        tuple(args.readiness_manifest or ()),
        tuple(args.readiness_manifest_dir or ()),
    )
    require_owned_session = bool(args.require_owned_session or ownership_paths)
    ownership_index = build_ownership_index(ownership_paths)
    target = ConnectorTarget(
        process_name="powershell.exe",
        window_title="Command Intelligence",
        workspace_path=workspace_path or cwd,
        workspace_hint=workspace_path or cwd,
    )
    ownership = ownership_index.match(target)

    runner = CommandRunner(
        build_command_execution_policy(
            args.profile,
            workspace_root=workspace_path or cwd,
            timeout_sec=max(0.1, float(args.timeout or 60.0)),
            audit_log_path=args.audit_log,
            require_owned_session=require_owned_session,
        )
    )
    report = runner.execute(
        CommandExecutionRequest(
            argv=command_argv,
            cwd=cwd,
            reason=args.reason,
            effects=tuple(args.effect or ()),
            ownership=ownership,
        )
    )
    data = report.to_dict()
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Command Intelligence execute: "
            f"ok={data['ok']} "
            f"attempts={data['control_attempts']} "
            f"exit_code={data['exit_code']} "
            f"error={data['error']}"
        )
    return 0 if report.ok else 1


def _clean_remainder(values: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(str(item) for item in values)
    if items and items[0] == "--":
        items = items[1:]
    return tuple(item for item in items if item)


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
