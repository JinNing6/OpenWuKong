# -*- coding: utf-8 -*-
"""CLI entrypoint for persistent command process broker operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from openwukong.control.command_process_broker import (
    CommandProcessBroker,
    CommandProcessBrokerConfig,
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage long-running argv processes through the persistent broker."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    _add_common_args(start_parser)
    start_parser.add_argument("--cwd", default="")
    start_parser.add_argument("--effect", action="append", default=None)
    start_parser.add_argument("--reason", default="")
    start_parser.add_argument("argv", nargs=argparse.REMAINDER)

    snapshot_parser = subparsers.add_parser("snapshot")
    _add_common_args(snapshot_parser)

    stop_parser = subparsers.add_parser("stop")
    _add_common_args(stop_parser)
    stop_parser.add_argument("--process-id", required=True)
    stop_parser.add_argument("--grace-seconds", type=float, default=2.0)

    stop_all_parser = subparsers.add_parser("stop-all")
    _add_common_args(stop_all_parser)
    stop_all_parser.add_argument("--grace-seconds", type=float, default=2.0)

    args = parser.parse_args(argv)
    broker = CommandProcessBroker(_config_from_args(args))

    if args.command == "start":
        result = broker.start(
            argv=_clean_remainder(tuple(args.argv or ())),
            cwd=args.cwd,
            effects=tuple(args.effect or ()),
            reason=args.reason,
            allow_control=bool(args.allow_control),
        )
    elif args.command == "snapshot":
        result = broker.snapshot()
    elif args.command == "stop":
        result = broker.stop(
            args.process_id,
            allow_control=bool(args.allow_control),
            grace_seconds=float(args.grace_seconds or 2.0),
        )
    else:
        result = broker.stop_all(
            allow_control=bool(args.allow_control),
            grace_seconds=float(args.grace_seconds or 2.0),
        )

    _emit(result, json_mode=bool(args.json))
    return _exit_code(args.command, result)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--storage-path", default="")
    parser.add_argument("--profile", default="workspace-write")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--audit-log", default="")
    parser.add_argument("--require-owned-session", action="store_true")
    parser.add_argument("--allow-control", action="store_true")
    parser.add_argument("--json", action="store_true")


def _config_from_args(args) -> CommandProcessBrokerConfig:
    workspace_root = str(args.workspace_path or os.getcwd())
    return CommandProcessBrokerConfig(
        workspace_root=workspace_root,
        storage_path=str(args.storage_path or ""),
        profile_id=str(args.profile or "workspace-write"),
        timeout_sec=max(0.1, float(args.timeout or 60.0)),
        audit_log_path=str(args.audit_log or ""),
        require_owned_session=bool(args.require_owned_session),
    )


def _clean_remainder(values: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(str(item) for item in values)
    if items and items[0] == "--":
        items = items[1:]
    return tuple(item for item in items if item)


def _exit_code(command: str, result: dict) -> int:
    if command == "snapshot":
        return 0
    return 0 if bool(result.get("ok")) else 1


def _emit(data: dict, *, json_mode: bool) -> None:
    if json_mode:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
        return
    _write_stdout(
        "Command process broker: "
        f"mode={data.get('mode')} "
        f"ok={data.get('ok', True)} "
        f"attempts={data.get('control_attempts', 0)} "
        f"process_id={data.get('process_id', '')} "
        f"error={data.get('error', '')}"
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
