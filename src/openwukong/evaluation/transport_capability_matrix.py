# -*- coding: utf-8 -*-
"""Read-only transport capability matrix CLI."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.fabric import ControlDispatchReport, ControlFabric, ControlIntent
from openwukong.evaluation.accessibility_probe import (
    PywinautoAccessibilityObserver,
    WindowsCapabilityProbe,
)


@dataclasses.dataclass(frozen=True)
class TransportCapabilityMatrixReport:
    dispatch_plans: tuple[ControlDispatchReport, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "transport-capability-matrix"

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
    def window_count(self) -> int:
        return len(self.dispatch_plans)

    def capability_level_counts(self) -> dict:
        return dict(
            sorted(
                Counter(
                    _transport(plan).capability_level for plan in self.dispatch_plans
                ).items()
            )
        )

    def selected_transport_counts(self) -> dict:
        return dict(
            sorted(
                Counter(
                    _transport(plan).selected_transport for plan in self.dispatch_plans
                ).items()
            )
        )

    def app_family_counts(self) -> dict:
        return dict(
            sorted(Counter(plan.route_plan.app_family for plan in self.dispatch_plans).items())
        )

    def summary(self) -> dict:
        capabilities = tuple(_transport(plan) for plan in self.dispatch_plans)
        return {
            "background_native": sum(
                1 for item in capabilities if item.capability_level == "background-native"
            ),
            "background_read_only": sum(
                1 for item in capabilities if item.capability_level == "background-read-only"
            ),
            "foreground_required": sum(
                1 for item in capabilities if item.capability_level == "foreground-required"
            ),
            "blocked": sum(1 for item in capabilities if item.blocked),
            "can_execute_without_focus": sum(
                1 for item in capabilities if item.can_execute_without_focus
            ),
            "requires_user_confirmation": sum(
                1 for item in capabilities if item.requires_user_confirmation
            ),
        }

    def to_dict(self) -> dict:
        sorted_plans = sorted(
            self.dispatch_plans,
            key=lambda plan: (
                _capability_rank(_transport(plan).capability_level),
                plan.route_plan.app_family,
                plan.target.process_name.lower(),
                plan.target.window_title.lower(),
            ),
        )
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_count": self.window_count,
            "summary": self.summary(),
            "capability_level_counts": self.capability_level_counts(),
            "selected_transport_counts": self.selected_transport_counts(),
            "app_family_counts": self.app_family_counts(),
            "capabilities": [_capability_entry(plan) for plan in sorted_plans],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def build_transport_capability_matrix(
    windows: Iterable[object],
    *,
    fabric: Optional[ControlFabric] = None,
    intent: Optional[ControlIntent] = None,
) -> TransportCapabilityMatrixReport:
    started = time.perf_counter()
    active_fabric = fabric or ControlFabric()
    active_intent = intent or ControlIntent(action="read_text")
    plans = tuple(active_fabric.dispatch(window, active_intent) for window in windows)
    return TransportCapabilityMatrixReport(
        dispatch_plans=plans,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def run_live_matrix(
    *,
    max_windows: int = 80,
    max_elements: int = 1000,
    fabric: Optional[ControlFabric] = None,
    intent: Optional[ControlIntent] = None,
) -> TransportCapabilityMatrixReport:
    observer = PywinautoAccessibilityObserver(
        max_windows=max(1, int(max_windows)),
        max_elements_per_window=max(1, int(max_elements)),
    )
    accessibility_report = WindowsCapabilityProbe(observer=observer).run()
    return build_transport_capability_matrix(
        accessibility_report.windows,
        fabric=fabric,
        intent=intent,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    observer: Optional[object] = None,
    fabric: Optional[ControlFabric] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only transport capability matrix for desktop windows."
    )
    parser.add_argument("--max-windows", type=int, default=80, help="Maximum top-level windows to inspect.")
    parser.add_argument("--max-elements", type=int, default=1000, help="Maximum descendants to inspect per window.")
    parser.add_argument("--action", default="read_text", help="Logical action to classify.")
    parser.add_argument("--text", default="", help="Optional text payload preview for the planned intent.")
    parser.add_argument("--allow-submit", action="store_true", help="Mark submit-style actions as already allowed.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print matrix JSON.")
    args = parser.parse_args(argv)

    intent = ControlIntent(
        action=args.action,
        text=args.text,
        allow_submit=args.allow_submit,
    )
    if observer is not None:
        accessibility_report = WindowsCapabilityProbe(observer=observer).run()
        report = build_transport_capability_matrix(
            accessibility_report.windows,
            fabric=fabric,
            intent=intent,
        )
    else:
        report = run_live_matrix(
            max_windows=args.max_windows,
            max_elements=args.max_elements,
            fabric=fabric,
            intent=intent,
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
        summary = data["summary"]
        _write_stdout(
            "Transport capability matrix: "
            f"windows={report.window_count} "
            f"background_native={summary['background_native']} "
            f"background_read_only={summary['background_read_only']} "
            f"foreground_required={summary['foreground_required']} "
            f"blocked={summary['blocked']}"
        )
    return 0


def _capability_entry(plan: ControlDispatchReport) -> dict:
    transport = _transport(plan)
    return {
        "target": {
            "process_name": plan.target.process_name,
            "window_title": plan.target.window_title,
            "pid": plan.target.pid,
        },
        "app_family": plan.route_plan.app_family,
        "route_id": plan.route_plan.primary_route.route_id,
        "selected_route": plan.selected_route,
        "dispatch_decision": plan.decision,
        "transport_capability": transport.to_dict(),
    }


def _transport(plan: ControlDispatchReport):
    if plan.transport_capability is not None:
        return plan.transport_capability
    return plan.to_dict()["transport_capability"]


def _capability_rank(level: str) -> int:
    order = {
        "background-native": 0,
        "background-read-only": 1,
        "foreground-required": 2,
        "blocked": 3,
    }
    return order.get(level, 99)


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
