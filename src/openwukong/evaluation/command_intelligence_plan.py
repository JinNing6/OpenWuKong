# -*- coding: utf-8 -*-
"""CLI entrypoint for structured command planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from openwukong.control.command_planner import CommandPlanIntent, CommandPlanner


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan a structured command intent before CommandRunner execution."
    )
    parser.add_argument("--intent-json", default="")
    parser.add_argument("--intent-file", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    intent_data, load_error = _load_intent_data(args.intent_json, args.intent_file)
    if load_error:
        data = {
            "mode": "command-intelligence-plan",
            "safety_mode": "plan_only",
            "ok": False,
            "error": load_error,
            "control_allowed": False,
            "control_attempts": 0,
        }
        _emit(data, json_mode=args.json)
        return 1

    report = CommandPlanner().plan(CommandPlanIntent.from_dict(intent_data))
    data = report.to_dict()
    _emit(data, json_mode=args.json)
    return 0 if report.ok else 1


def _load_intent_data(intent_json: str, intent_file: str) -> tuple[dict, str]:
    if intent_json and intent_file:
        return {}, "intent_source_conflict"
    if intent_json:
        try:
            data = json.loads(intent_json)
        except json.JSONDecodeError:
            return {}, "invalid_intent_json"
        return data if isinstance(data, dict) else {}, "" if isinstance(data, dict) else "intent_json_must_be_object"
    if intent_file:
        path = Path(intent_file)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}, "intent_file_not_found"
        except json.JSONDecodeError:
            return {}, "invalid_intent_json"
        return data if isinstance(data, dict) else {}, "" if isinstance(data, dict) else "intent_json_must_be_object"
    return {}, "intent_required"


def _emit(data: dict, *, json_mode: bool) -> None:
    if json_mode:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
        return
    _write_stdout(
        "Command Intelligence plan: "
        f"ok={data.get('ok')} "
        f"profile={data.get('profile_id', '')} "
        f"argv={data.get('argv', [])} "
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
