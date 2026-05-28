# -*- coding: utf-8 -*-
"""Unified real no-loss probe for agent desktop app surfaces.

The runner intentionally stays diagnostic-only. It does not submit tasks,
send chat messages, type into windows, or click UI. Each app case delegates to
the read-only native connector probe and aggregates the safety evidence.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.control.app_resolution import WindowsAppResolver
from openwukong.evaluation.agent_native_connector_probe import (
    run_agent_native_connector_probe,
)


ProbeRunner = Callable[..., object]


DEFAULT_AGENT_APP_SURFACES = ("codex app", "claude desktop")


@dataclasses.dataclass(frozen=True)
class AgentAppRealNoLossCase:
    agent: str
    status: str
    passed: bool
    real_verified: bool
    native_ready: bool
    probe: dict
    artifact_path: str = ""
    errors: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "agent-app-real-no-loss-case"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return _counter(self.probe, "control_attempts")

    @property
    def window_input_attempts(self) -> int:
        return _counter(self.probe, "window_input_attempts") + _counter(
            _app_uia_probe(self.probe),
            "window_input_attempts",
        )

    @property
    def bridge_send_attempts(self) -> int:
        return _counter(self.probe, "bridge_send_attempts")

    @property
    def agent_command_attempts(self) -> int:
        return _counter(self.probe, "agent_command_attempts")

    @property
    def background_screenshot_count(self) -> int:
        return _counter(_app_uia_probe(self.probe), "background_screenshot_count")

    @property
    def background_screenshot_success_count(self) -> int:
        return _counter(_app_uia_probe(self.probe), "background_screenshot_success_count")

    @property
    def background_screenshot_focus_stable(self) -> bool:
        value = _app_uia_probe(self.probe).get("background_screenshot_focus_stable")
        return bool(value) if value is not None else True

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "agent": self.agent,
            "status": self.status,
            "passed": self.passed,
            "real_verified": self.real_verified,
            "native_ready": self.native_ready,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "artifact_path": self.artifact_path,
            "errors": list(self.errors),
            "probe": dict(self.probe),
        }


@dataclasses.dataclass(frozen=True)
class AgentAppRealNoLossReport:
    output_root: str
    project_name: str
    task_name: str
    cases: tuple[AgentAppRealNoLossCase, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-real-no-loss"

    @property
    def safety_mode(self) -> str:
        return "real_no_loss"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return sum(case.control_attempts for case in self.cases)

    @property
    def window_input_attempts(self) -> int:
        return sum(case.window_input_attempts for case in self.cases)

    @property
    def bridge_send_attempts(self) -> int:
        return sum(case.bridge_send_attempts for case in self.cases)

    @property
    def agent_command_attempts(self) -> int:
        return sum(case.agent_command_attempts for case in self.cases)

    @property
    def background_screenshot_count(self) -> int:
        return sum(case.background_screenshot_count for case in self.cases)

    @property
    def background_screenshot_success_count(self) -> int:
        return sum(case.background_screenshot_success_count for case in self.cases)

    @property
    def background_screenshot_focus_stable(self) -> bool:
        return all(case.background_screenshot_focus_stable for case in self.cases)

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def passed_cases(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.passed_cases

    @property
    def native_ready_cases(self) -> int:
        return sum(1 for case in self.cases if case.native_ready)

    @property
    def gated_cases(self) -> int:
        return sum(1 for case in self.cases if case.status.startswith("gated_"))

    @property
    def real_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.real_verified)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "output_root": self.output_root,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "native_ready_cases": self.native_ready_cases,
            "gated_cases": self.gated_cases,
            "real_verified_cases": self.real_verified_cases,
            "cases": [case.to_dict() for case in self.cases],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_app_real_no_loss(
    *,
    agents: Iterable[str] = DEFAULT_AGENT_APP_SURFACES,
    project_name: str = "",
    task_name: str = "",
    output_root: str | Path = "",
    screenshot_dir: str | Path = "",
    resolver: WindowsAppResolver | None = None,
    probe_runner: ProbeRunner | None = None,
    process_provider: object | None = None,
    http_probe: object | None = None,
    window_capture_provider: object | None = None,
    max_windows: int = 80,
    max_elements: int = 1200,
    request_timeout: float = 0.2,
) -> AgentAppRealNoLossReport:
    started = time.perf_counter()
    root = _resolve_output_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    screenshot_root = _resolve_optional_path(screenshot_dir)
    active_probe_runner = probe_runner or run_agent_native_connector_probe
    cases: list[AgentAppRealNoLossCase] = []
    for agent in _normalize_agents(agents):
        agent_screenshot_dir = (
            screenshot_root / _safe_filename(agent)
            if screenshot_root is not None
            else ""
        )
        raw_probe = active_probe_runner(
            agent=agent,
            project_name=project_name,
            task_name=task_name,
            resolver=resolver,
            process_provider=process_provider,
            http_probe=http_probe,
            screenshot_dir=str(agent_screenshot_dir) if agent_screenshot_dir else "",
            window_capture_provider=window_capture_provider,
            max_windows=max_windows,
            max_elements=max_elements,
            request_timeout=request_timeout,
        )
        probe = _report_to_dict(raw_probe)
        cases.append(_write_case_artifact(root, _case_from_probe(agent, probe)))
    return AgentAppRealNoLossReport(
        output_root=str(root),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        cases=tuple(cases),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def format_agent_app_real_no_loss_report(report: AgentAppRealNoLossReport) -> str:
    lines = [
        "Agent app real no-loss",
        (
            f"Passed: {report.passed_cases}/{report.total_cases}  "
            f"Native ready: {report.native_ready_cases}  "
            f"Gated: {report.gated_cases}  "
            f"Control attempts: {report.control_attempts}"
        ),
        (
            f"Screenshots: {report.background_screenshot_success_count}/"
            f"{report.background_screenshot_count}  "
            f"Focus stable: {str(report.background_screenshot_focus_stable).lower()}"
        ),
    ]
    for case in report.cases:
        lines.append(f"- {case.agent}: {case.status}")
    return "\n".join(lines).rstrip()


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
    probe_runner: ProbeRunner | None = None,
    process_provider: object | None = None,
    http_probe: object | None = None,
    window_capture_provider: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only real no-loss probes for agent desktop apps."
    )
    parser.add_argument(
        "--agent",
        action="append",
        default=None,
        help="Agent app surface to probe. Repeat for multiple apps.",
    )
    parser.add_argument("--project-name", default="")
    parser.add_argument("--task-name", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-windows", type=int, default=80)
    parser.add_argument("--max-elements", type=int, default=1200)
    parser.add_argument("--request-timeout", type=float, default=0.2)
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else WindowsAppResolver()
    report = run_agent_app_real_no_loss(
        agents=tuple(args.agent or DEFAULT_AGENT_APP_SURFACES),
        project_name=args.project_name,
        task_name=args.task_name,
        output_root=args.output_root,
        screenshot_dir=args.screenshot_dir,
        resolver=resolver,
        probe_runner=probe_runner,
        process_provider=process_provider,
        http_probe=http_probe,
        window_capture_provider=window_capture_provider,
        max_windows=args.max_windows,
        max_elements=args.max_elements,
        request_timeout=args.request_timeout,
    )
    payload = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            _json_dumps(payload),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(_json_dumps(payload))
    else:
        _write_stdout(format_agent_app_real_no_loss_report(report))
    return 0 if report.failed_cases == 0 else 1


def _case_from_probe(agent: str, probe: dict) -> AgentAppRealNoLossCase:
    decision = str(probe.get("decision", "") or "")
    native_ready = int(probe.get("ready_endpoint_count", 0) or 0) > 0
    app_probe = _app_uia_probe(probe)
    matched_window_count = _counter(app_probe, "matched_window_count")
    target_matched = bool(app_probe.get("target_matched", False))
    real_verified = bool(native_ready or matched_window_count > 0 or target_matched)
    control_attempts = _counter(probe, "control_attempts")
    window_input_attempts = _counter(probe, "window_input_attempts") + _counter(
        app_probe,
        "window_input_attempts",
    )
    bridge_send_attempts = _counter(probe, "bridge_send_attempts")
    command_attempts = _counter(probe, "agent_command_attempts")
    errors: list[str] = []
    if control_attempts:
        errors.append("control_attempts_nonzero")
    if window_input_attempts:
        errors.append("window_input_attempts_nonzero")
    if bridge_send_attempts:
        errors.append("bridge_send_attempts_nonzero")
    if command_attempts:
        errors.append("agent_command_attempts_nonzero")
    if decision == "agent_native_connector_ready":
        status = "native_connector_ready"
    elif matched_window_count > 0 or target_matched:
        status = "gated_native_endpoint_missing"
    elif decision in {"agent_app_window_not_found", "agent_app_surface_not_ready"}:
        status = "unavailable"
    else:
        status = decision or "unknown"
    passed = not errors
    return AgentAppRealNoLossCase(
        agent=str(agent or "").strip(),
        status=status,
        passed=passed,
        real_verified=real_verified,
        native_ready=native_ready,
        probe=probe,
        errors=tuple(errors),
    )


def _write_case_artifact(
    output_root: Path,
    case: AgentAppRealNoLossCase,
) -> AgentAppRealNoLossCase:
    artifact_dir = output_root / "agent_app_real_no_loss"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_filename(case.agent)}.json"
    data = case.to_dict()
    artifact_path.write_text(
        _json_dumps(data),
        encoding="utf-8",
    )
    return dataclasses.replace(case, artifact_path=str(artifact_path))


def _normalize_agents(agents: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for agent in agents:
        text = str(agent or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return tuple(normalized or DEFAULT_AGENT_APP_SURFACES)


def _resolve_output_root(output_root: str | Path) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve()
    return (Path("logs") / "runtime" / "agent-app-real-no-loss").resolve()


def _resolve_optional_path(path: str | Path) -> Path | None:
    text = str(path or "").strip()
    if not text:
        return None
    return Path(text).expanduser().resolve()


def _report_to_dict(report: object) -> dict:
    if isinstance(report, dict):
        return dict(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {
        "mode": "agent-native-connector-probe",
        "ok": False,
        "decision": "invalid_probe_report",
        "control_attempts": 0,
        "app_uia_probe": {},
    }


def _app_uia_probe(probe: dict) -> dict:
    value = probe.get("app_uia_probe", {})
    return dict(value) if isinstance(value, dict) else {}


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


def _safe_filename(value: str) -> str:
    text = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in str(value or "").strip()
    )
    return text.strip("._") or "unnamed"


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2)


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
