# -*- coding: utf-8 -*-
"""Guarded targeted conversation runner for Codex/Claude-style agent surfaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from openwukong.control.agent_conversation import run_agent_conversation


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
    command_executor: object | None = None,
    app_surface_probe_runner: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Draft or execute a guarded targeted agent conversation message."
    )
    parser.add_argument("--agent", required=True, help="Agent product name or alias.")
    parser.add_argument("--message", required=True, help="Message text to draft or submit.")
    parser.add_argument("--project-name", default="", help="Target project name.")
    parser.add_argument("--task-name", default="", help="Target task or session name.")
    parser.add_argument(
        "--acceptance-criterion",
        action="append",
        default=[],
        help="Acceptance criterion. Repeat for multiple criteria.",
    )
    parser.add_argument(
        "--acceptance-marker",
        action="append",
        default=[],
        help="Required marker expected in the agent result. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--forbid-marker",
        action="append",
        default=[],
        help="Forbidden marker that fails acceptance if present.",
    )
    parser.add_argument("--workspace-root", default="", help="Workspace root for the agent task.")
    parser.add_argument("--output-root", default="", help="Directory for draft artifacts.")
    parser.add_argument("--output", default="", help="Optional JSON report path.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    parser.add_argument("--execute", action="store_true", help="Request real agent command execution.")
    parser.add_argument("--dry-run", action="store_true", help="Build command without running it.")
    parser.add_argument(
        "--allow-agent-task",
        action="store_true",
        help="Allow confirmed agent task side effects to proceed.",
    )
    parser.add_argument(
        "--confirm-effect",
        action="append",
        default=[],
        help="Confirmed side-effect id. Repeat for submit_task and start_agent.",
    )
    parser.add_argument("--timeout-sec", type=float, default=120.0, help="Agent command timeout.")
    parser.add_argument("--audit-log", default="", help="Optional command audit log path.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero unless the report is ok.")
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else None
    probe_runner = (
        app_surface_probe_runner
        if callable(app_surface_probe_runner)
        else _default_app_surface_probe_runner
    )
    report = run_agent_conversation(
        agent=args.agent,
        message=args.message,
        project_name=args.project_name,
        task_name=args.task_name,
        acceptance_criteria=tuple(args.acceptance_criterion or ()),
        required_markers=tuple(args.acceptance_marker or ()),
        forbidden_markers=tuple(args.forbid_marker or ()),
        workspace_root=args.workspace_root,
        output_root=args.output_root,
        execute=args.execute,
        dry_run=args.dry_run,
        allow_agent_task=args.allow_agent_task,
        confirmed_effect_ids=tuple(args.confirm_effect or ()),
        resolver=resolver,
        command_executor=command_executor,
        app_surface_probe_runner=probe_runner,
        timeout_sec=args.timeout_sec,
        audit_log_path=args.audit_log,
    )
    data = report.to_dict()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Agent conversation runner: "
            f"agent={data['agent_id']} "
            f"project={data['project_name']} "
            f"task={data['task_name']} "
            f"decision={data['decision']} "
            f"attempts={data['agent_command_attempts']}"
        )

    if args.strict and not data["ok"]:
        return 1
    return 0


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


def _default_app_surface_probe_runner(**kwargs):
    from openwukong.evaluation.agent_native_connector_probe import (
        run_agent_native_connector_probe,
    )

    return run_agent_native_connector_probe(**kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
