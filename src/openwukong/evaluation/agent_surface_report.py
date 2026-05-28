# -*- coding: utf-8 -*-
"""Read-only diagnostics for Codex/Claude-style agent surfaces."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.agent_surface import (
    AgentSurfaceBindingReport,
    build_agent_surface_binding,
)
from openwukong.control.app_resolution import WindowsAppResolver


@dataclasses.dataclass(frozen=True)
class AgentSurfaceDiagnosticsReport:
    agent_names: tuple[str, ...]
    bindings: tuple[AgentSurfaceBindingReport, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-surface-report"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def summary(self) -> dict:
        return {
            "agent_count": len(self.bindings),
            "resolved": sum(1 for binding in self.bindings if binding.ok),
            "not_found": sum(
                1 for binding in self.bindings if binding.decision == "agent_app_not_found"
            ),
            "transport_not_ready": sum(
                1 for binding in self.bindings if binding.decision == "agent_transport_not_ready"
            ),
            "background_capable": sum(
                1
                for binding in self.bindings
                if binding.selected_transport and binding.selected_transport.background_capable
            ),
            "confirmation_required": sum(
                1
                for binding in self.bindings
                if binding.side_effect_gate.decision == "side_effect_confirmation_required"
            ),
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "summary": self.summary(),
            "agents": [binding.to_dict() for binding in self.bindings],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def build_agent_surface_report(
    agent_names: Iterable[str],
    *,
    resolver: WindowsAppResolver | None = None,
) -> AgentSurfaceDiagnosticsReport:
    started = time.perf_counter()
    names = tuple(str(name or "").strip() for name in agent_names if str(name or "").strip())
    active_resolver = resolver or WindowsAppResolver()
    bindings = tuple(
        build_agent_surface_binding(name, resolver=active_resolver)
        for name in names
    )
    return AgentSurfaceDiagnosticsReport(
        agent_names=names,
        bindings=bindings,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only Codex/Claude agent surface report."
    )
    parser.add_argument(
        "--agent",
        action="append",
        required=True,
        help="Agent product name or alias. Repeat for multiple agents.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when any agent is unresolved.")
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else None
    report = build_agent_surface_report(args.agent, resolver=resolver)
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
            "Agent surface report: "
            f"agents={summary['agent_count']} "
            f"resolved={summary['resolved']} "
            f"background_capable={summary['background_capable']} "
            f"confirmation_required={summary['confirmation_required']}"
        )

    if args.strict and data["summary"]["resolved"] != data["summary"]["agent_count"]:
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


if __name__ == "__main__":
    raise SystemExit(main())
