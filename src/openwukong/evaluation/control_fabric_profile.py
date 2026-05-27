# -*- coding: utf-8 -*-
"""Read-only Control Fabric dispatch profile for visible desktop apps."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.fabric import (
    ControlDispatchReport,
    ControlFabric,
    ControlIntent,
)
from openwukong.control.session_discovery import (
    SessionDiscovery,
    SessionDiscoveryOptions,
)
from openwukong.evaluation.accessibility_probe import (
    PywinautoAccessibilityObserver,
    WindowsCapabilityProbe,
)


@dataclasses.dataclass(frozen=True)
class ControlFabricProfileReport:
    dispatch_plans: tuple[ControlDispatchReport, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "control-fabric-profile"

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

    def decision_counts(self) -> dict:
        return dict(sorted(Counter(plan.decision for plan in self.dispatch_plans).items()))

    def execution_mode_counts(self) -> dict:
        return dict(sorted(Counter(plan.execution_mode for plan in self.dispatch_plans).items()))

    def route_counts(self) -> dict:
        return dict(sorted(Counter(plan.selected_route for plan in self.dispatch_plans).items()))

    def app_family_counts(self) -> dict:
        return dict(sorted(Counter(plan.route_plan.app_family for plan in self.dispatch_plans).items()))

    def summary(self) -> dict:
        connector_required = tuple(
            plan for plan in self.dispatch_plans if plan.decision == "connector_required"
        )
        return {
            "connector_dispatch_ready": sum(1 for plan in self.dispatch_plans if plan.decision == "dispatch_connector"),
            "connector_required": len(connector_required),
            "connector_missing": sum(
                1 for plan in connector_required if not plan.candidate_connector_ids
            ),
            "connector_installed_not_ready": sum(
                1 for plan in connector_required if plan.candidate_connector_ids
            ),
            "background_uia_ready": sum(1 for plan in self.dispatch_plans if plan.decision == "dispatch_background_uia"),
            "foreground_required": sum(1 for plan in self.dispatch_plans if plan.foreground_required),
            "blocked": sum(1 for plan in self.dispatch_plans if plan.blocked),
        }

    def to_dict(self) -> dict:
        sorted_plans = sorted(
            self.dispatch_plans,
            key=lambda plan: (
                _decision_rank(plan.decision),
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
            "decision_counts": self.decision_counts(),
            "execution_mode_counts": self.execution_mode_counts(),
            "route_counts": self.route_counts(),
            "app_family_counts": self.app_family_counts(),
            "dispatch_plans": [plan.to_dict() for plan in sorted_plans],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def profile_control_fabric(
    windows: Iterable[object],
    *,
    fabric: Optional[ControlFabric] = None,
    intent: Optional[ControlIntent] = None,
    session_discovery: Optional[object] = None,
) -> ControlFabricProfileReport:
    started = time.perf_counter()
    active_fabric = fabric or ControlFabric()
    active_intent = intent or ControlIntent()
    targets = tuple(
        session_discovery.enrich(window) if session_discovery is not None else window
        for window in windows
    )
    plans = tuple(active_fabric.dispatch(target, active_intent) for target in targets)
    return ControlFabricProfileReport(
        dispatch_plans=plans,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def run_live_profile(
    *,
    max_windows: int = 80,
    max_elements: int = 1000,
    intent: Optional[ControlIntent] = None,
    fabric: Optional[ControlFabric] = None,
    session_discovery: Optional[object] = None,
) -> ControlFabricProfileReport:
    observer = PywinautoAccessibilityObserver(
        max_windows=max(1, int(max_windows)),
        max_elements_per_window=max(1, int(max_elements)),
    )
    accessibility_report = WindowsCapabilityProbe(observer=observer).run()
    return profile_control_fabric(
        accessibility_report.windows,
        fabric=fabric,
        intent=intent,
        session_discovery=session_discovery,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    observer: Optional[object] = None,
    fabric: Optional[ControlFabric] = None,
    session_discovery: Optional[object] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only unified Control Fabric dispatch profile."
    )
    parser.add_argument("--max-windows", type=int, default=80, help="Maximum top-level windows to inspect.")
    parser.add_argument("--max-elements", type=int, default=1000, help="Maximum descendants to inspect per window.")
    parser.add_argument("--action", default="write_text", help="Logical control action to plan.")
    parser.add_argument("--text", default="", help="Optional text payload preview for the planned intent.")
    parser.add_argument("--allow-foreground", action="store_true", help="Mark foreground UIA fallback as schedulable.")
    parser.add_argument("--with-default-connectors", action="store_true", help="Bind built-in connectors for readiness planning only.")
    parser.add_argument("--discover-sessions", action="store_true", help="Probe read-only local connector endpoints before planning.")
    parser.add_argument("--workspace-root", action="append", default=None, help="Workspace root candidate for terminal/git session readiness.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print profile JSON.")
    args = parser.parse_args(argv)

    intent = ControlIntent(
        action=args.action,
        text=args.text,
        allow_foreground_interaction=args.allow_foreground,
    )
    active_fabric = fabric
    if active_fabric is None and args.with_default_connectors:
        active_fabric = ControlFabric.with_default_connectors()
    active_discovery = session_discovery
    if active_discovery is None and args.discover_sessions:
        active_discovery = SessionDiscovery(
            SessionDiscoveryOptions(
                workspace_roots=tuple(args.workspace_root or ()),
            )
        )
    if observer is not None:
        accessibility_report = WindowsCapabilityProbe(observer=observer).run()
        report = profile_control_fabric(
            accessibility_report.windows,
            fabric=active_fabric,
            intent=intent,
            session_discovery=active_discovery,
        )
    else:
        report = run_live_profile(
            max_windows=args.max_windows,
            max_elements=args.max_elements,
            fabric=active_fabric,
            session_discovery=active_discovery,
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
            "Control Fabric profile: "
            f"windows={report.window_count} "
            f"connector_ready={summary['connector_dispatch_ready']} "
            f"connectors_required={summary['connector_required']} "
            f"background_uia={summary['background_uia_ready']} "
            f"foreground={summary['foreground_required']} "
            f"blocked={summary['blocked']}"
        )
    return 0


def _decision_rank(decision: str) -> int:
    order = {
        "dispatch_connector": 0,
        "connector_required": 1,
        "dispatch_background_uia": 2,
        "dispatch_foreground_uia": 3,
        "foreground_or_native_required": 4,
        "observe_only": 5,
        "blocked": 6,
    }
    return order.get(decision, 99)


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
