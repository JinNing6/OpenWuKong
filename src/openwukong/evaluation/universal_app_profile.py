# -*- coding: utf-8 -*-
"""Universal read-only application control profiler.

The profiler is the "one pass" layer: it does not try to control every app.
Instead, it classifies each visible application into the safest available route
family so higher layers can avoid per-app guesswork.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors.route_policy import ControlRoutePlan, build_control_route_plan
from openwukong.evaluation.accessibility_probe import (
    PywinautoAccessibilityObserver,
    WindowsCapabilityProbe,
)


_CONNECTOR_ROUTE_IDS = {
    "browser-devtools-or-extension",
    "git-cli",
    "ide-extension-connector",
    "office-object-model-or-addin",
    "terminal-native-session",
}


@dataclasses.dataclass(frozen=True)
class UniversalAppProfile:
    pid: int
    process_name: str
    window_title: str
    app_family: str
    one_step_status: str
    recommended_route: str
    background_safe: bool
    foreground_required: bool
    blocked: bool
    capability_level: str
    capability_score: int
    element_count: int
    semantic_input_count: int
    semantic_action_count: int
    risks: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "app_family": self.app_family,
            "one_step_status": self.one_step_status,
            "recommended_route": self.recommended_route,
            "background_safe": self.background_safe,
            "foreground_required": self.foreground_required,
            "blocked": self.blocked,
            "capability_level": self.capability_level,
            "capability_score": self.capability_score,
            "element_count": self.element_count,
            "semantic_input_count": self.semantic_input_count,
            "semantic_action_count": self.semantic_action_count,
            "risks": list(self.risks),
            "missing_capabilities": list(self.missing_capabilities),
        }


@dataclasses.dataclass(frozen=True)
class UniversalAppProfileReport:
    windows: tuple[UniversalAppProfile, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "universal-application-control-profile"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_count(self) -> int:
        return len(self.windows)

    def status_counts(self) -> dict:
        return dict(sorted(Counter(profile.one_step_status for profile in self.windows).items()))

    def route_counts(self) -> dict:
        return dict(sorted(Counter(profile.recommended_route for profile in self.windows).items()))

    def app_family_counts(self) -> dict:
        return dict(sorted(Counter(profile.app_family for profile in self.windows).items()))

    def summary(self) -> dict:
        return {
            "auto_background_ready": sum(1 for item in self.windows if item.one_step_status == "background_semantic_ready"),
            "connector_required": sum(1 for item in self.windows if item.one_step_status == "connector_required"),
            "foreground_required": sum(1 for item in self.windows if item.one_step_status == "foreground_or_native_required"),
            "blocked": sum(1 for item in self.windows if item.one_step_status == "blocked"),
            "unknown_or_observe_only": sum(1 for item in self.windows if item.one_step_status == "observe_only"),
        }

    def to_dict(self) -> dict:
        sorted_windows = sorted(
            self.windows,
            key=lambda item: (
                _status_rank(item.one_step_status),
                item.app_family,
                item.process_name.lower(),
                item.window_title.lower(),
            ),
        )
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_count": self.window_count,
            "summary": self.summary(),
            "status_counts": self.status_counts(),
            "route_counts": self.route_counts(),
            "app_family_counts": self.app_family_counts(),
            "windows": [profile.to_dict() for profile in sorted_windows],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def profile_applications(windows: Iterable[object]) -> UniversalAppProfileReport:
    started = time.perf_counter()
    profiles = tuple(_profile_window(window) for window in windows)
    return UniversalAppProfileReport(
        windows=profiles,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def run_live_profile(
    *,
    max_windows: int = 80,
    max_elements: int = 1000,
) -> UniversalAppProfileReport:
    observer = PywinautoAccessibilityObserver(
        max_windows=max(1, int(max_windows)),
        max_elements_per_window=max(1, int(max_elements)),
    )
    accessibility_report = WindowsCapabilityProbe(observer=observer).run()
    return profile_applications(accessibility_report.windows)


def main(argv: Optional[list[str]] = None, *, observer: Optional[object] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only universal control profile for visible desktop apps."
    )
    parser.add_argument("--max-windows", type=int, default=80, help="Maximum top-level windows to inspect.")
    parser.add_argument("--max-elements", type=int, default=1000, help="Maximum descendants to inspect per window.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print profile JSON.")
    args = parser.parse_args(argv)

    if observer is not None:
        accessibility_report = WindowsCapabilityProbe(observer=observer).run()
        report = profile_applications(accessibility_report.windows)
    else:
        report = run_live_profile(
            max_windows=args.max_windows,
            max_elements=args.max_elements,
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
            "Universal app profile: "
            f"windows={report.window_count} "
            f"background={summary['auto_background_ready']} "
            f"connectors={summary['connector_required']} "
            f"foreground={summary['foreground_required']} "
            f"blocked={summary['blocked']}"
        )
    return 0


def _profile_window(window: object) -> UniversalAppProfile:
    plan = build_control_route_plan(window)
    route_id = plan.primary_route.route_id
    status = _status_for(window, plan)

    return UniversalAppProfile(
        pid=int(getattr(window, "pid", 0) or 0),
        process_name=str(getattr(window, "process_name", "") or ""),
        window_title=str(getattr(window, "window_title", "") or ""),
        app_family=plan.app_family,
        one_step_status=status,
        recommended_route=route_id,
        background_safe=status in {"background_semantic_ready", "connector_required"},
        foreground_required=status == "foreground_or_native_required",
        blocked=status == "blocked",
        capability_level=str(_call_or_value(window, "capability_level", default="window_only")),
        capability_score=int(_call_or_value(window, "capability_score", default=0) or 0),
        element_count=int(getattr(window, "element_count", 0) or 0),
        semantic_input_count=int(getattr(window, "semantic_input_count", 0) or 0),
        semantic_action_count=int(getattr(window, "semantic_action_count", 0) or 0),
        risks=tuple(_call_or_value(window, "risks", default=()) or ()),
        missing_capabilities=plan.missing_capabilities,
    )


def _status_for(window: object, plan: ControlRoutePlan) -> str:
    route_id = plan.primary_route.route_id
    if route_id in {"no-deterministic-route"} or int(getattr(window, "element_count", 0) or 0) == 0:
        return "blocked"
    if plan.is_blocked:
        if int(getattr(window, "input_candidate_count", 0) or 0) > 0:
            return "foreground_or_native_required"
        return "blocked"
    if route_id in _CONNECTOR_ROUTE_IDS:
        return "connector_required"
    if route_id == "uia-semantic":
        return "background_semantic_ready"
    if route_id in {"uia-structural-observe", "uia-structural"}:
        if int(getattr(window, "input_candidate_count", 0) or 0) > 0:
            return "foreground_or_native_required"
        return "observe_only"
    if route_id == "app-native-bridge-required":
        return "foreground_or_native_required"
    return "observe_only"


def _status_rank(status: str) -> int:
    order = {
        "connector_required": 0,
        "background_semantic_ready": 1,
        "foreground_or_native_required": 2,
        "observe_only": 3,
        "blocked": 4,
    }
    return order.get(status, 99)


def _call_or_value(obj: object, name: str, *, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


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
