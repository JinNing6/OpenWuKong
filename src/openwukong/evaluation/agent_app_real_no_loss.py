# -*- coding: utf-8 -*-
"""Unified real no-loss probe for agent desktop app surfaces.

The runner is read-only by default: it does not submit tasks, send chat
messages, type into windows, or click UI. A native app bridge send is available
only behind explicit opt-in and only after the dry-run bridge contract is ready.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from openwukong.control.agent_app_bridge import (
    AgentAppBridgeCdpAdapter,
    AgentAppBridgeNativeAdapter,
    AgentAppBridgeDryRunAdapter,
    build_agent_app_bridge_request,
)
from openwukong.control.agent_app_uia_action import (
    AgentAppUiaSemanticActionDryRunAdapter,
    AgentAppUiaSemanticDraftDryRunAdapter,
    AgentAppUiaSemanticDraftWriterAdapter,
    AgentAppUiaSemanticActionSenderAdapter,
    build_agent_app_uia_semantic_action_request,
)
from openwukong.control.agent_conversation import compose_agent_conversation_message
from openwukong.control.agent_app_transport_matrix import (
    build_agent_app_transport_matrix,
    summarize_agent_app_transport_matrices,
)
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
    uia_semantic_action_dry_run: dict = dataclasses.field(default_factory=dict)
    uia_semantic_action_send_report: dict = dataclasses.field(default_factory=dict)
    uia_semantic_draft_dry_run: dict = dataclasses.field(default_factory=dict)
    uia_semantic_draft_report: dict = dataclasses.field(default_factory=dict)
    app_bridge_dry_run: dict = dataclasses.field(default_factory=dict)
    app_bridge_send_report: dict = dataclasses.field(default_factory=dict)
    transport_matrix: dict = dataclasses.field(default_factory=dict)
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
        return _counter(self.probe, "control_attempts") + _counter(
            self.app_bridge_send_report,
            "control_attempts",
        ) + _counter(
            self.uia_semantic_action_send_report,
            "control_attempts",
        )

    @property
    def window_input_attempts(self) -> int:
        return _counter(self.probe, "window_input_attempts") + _counter(
            _app_uia_probe(self.probe),
            "window_input_attempts",
        ) + _counter(
            self.app_bridge_send_report,
            "window_input_attempts",
        ) + _counter(
            self.uia_semantic_action_send_report,
            "window_input_attempts",
        )

    @property
    def bridge_send_attempts(self) -> int:
        return _counter(self.probe, "bridge_send_attempts") + _counter(
            self.app_bridge_send_report,
            "bridge_send_attempts",
        )

    @property
    def agent_command_attempts(self) -> int:
        return _counter(self.probe, "agent_command_attempts")

    @property
    def uia_value_set_attempts(self) -> int:
        return _counter(self.uia_semantic_action_dry_run, "uia_value_set_attempts") + _counter(
            self.uia_semantic_action_send_report,
            "uia_value_set_attempts",
        ) + _counter(
            self.uia_semantic_draft_dry_run,
            "uia_value_set_attempts",
        ) + _counter(
            self.uia_semantic_draft_report,
            "uia_value_set_attempts",
        )

    @property
    def uia_invoke_attempts(self) -> int:
        return _counter(self.uia_semantic_action_dry_run, "uia_invoke_attempts") + _counter(
            self.uia_semantic_action_send_report,
            "uia_invoke_attempts",
        ) + _counter(
            self.uia_semantic_draft_dry_run,
            "uia_invoke_attempts",
        ) + _counter(
            self.uia_semantic_draft_report,
            "uia_invoke_attempts",
        )

    @property
    def uia_semantic_action_ready(self) -> bool:
        return bool(self.uia_semantic_action_dry_run.get("ok", False))

    @property
    def uia_semantic_action_send_verified(self) -> bool:
        return bool(
            str(self.uia_semantic_action_send_report.get("decision", "") or "")
            == "uia_semantic_action_send_accepted"
            and _counter(self.uia_semantic_action_send_report, "control_attempts") == 0
            and _counter(self.uia_semantic_action_send_report, "window_input_attempts") == 0
        )

    @property
    def uia_semantic_draft_ready(self) -> bool:
        return bool(self.uia_semantic_draft_dry_run.get("ok", False))

    @property
    def uia_semantic_draft_verified(self) -> bool:
        return bool(
            str(self.uia_semantic_draft_report.get("decision", "") or "")
            == "uia_semantic_action_draft_verified"
            and _counter(self.uia_semantic_draft_report, "control_attempts") == 0
            and _counter(self.uia_semantic_draft_report, "window_input_attempts") == 0
            and _counter(self.uia_semantic_draft_report, "uia_invoke_attempts") == 0
        )

    @property
    def app_bridge_send_verified(self) -> bool:
        return str(
            self.app_bridge_send_report.get("decision", "") or ""
        ) == "app_bridge_send_accepted"

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
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
            "uia_semantic_action_ready": self.uia_semantic_action_ready,
            "uia_semantic_action_dry_run": dict(self.uia_semantic_action_dry_run),
            "uia_semantic_action_send_verified": self.uia_semantic_action_send_verified,
            "uia_semantic_action_send_report": dict(self.uia_semantic_action_send_report),
            "uia_semantic_draft_ready": self.uia_semantic_draft_ready,
            "uia_semantic_draft_dry_run": dict(self.uia_semantic_draft_dry_run),
            "uia_semantic_draft_verified": self.uia_semantic_draft_verified,
            "uia_semantic_draft_report": dict(self.uia_semantic_draft_report),
            "app_bridge_send_verified": self.app_bridge_send_verified,
            "app_bridge_dry_run": dict(self.app_bridge_dry_run),
            "app_bridge_send_report": dict(self.app_bridge_send_report),
            "transport_matrix": dict(self.transport_matrix),
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
    def uia_value_set_attempts(self) -> int:
        return sum(case.uia_value_set_attempts for case in self.cases)

    @property
    def uia_invoke_attempts(self) -> int:
        return sum(case.uia_invoke_attempts for case in self.cases)

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
    def uia_semantic_action_ready_cases(self) -> int:
        return sum(1 for case in self.cases if case.uia_semantic_action_ready)

    @property
    def uia_semantic_action_send_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.uia_semantic_action_send_verified)

    @property
    def uia_semantic_draft_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.uia_semantic_draft_verified)

    @property
    def app_bridge_send_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.app_bridge_send_verified)

    @property
    def gated_cases(self) -> int:
        return sum(1 for case in self.cases if case.status.startswith("gated_"))

    @property
    def real_verified_cases(self) -> int:
        return sum(1 for case in self.cases if case.real_verified)

    @property
    def transport_matrix_summary(self) -> dict:
        return summarize_agent_app_transport_matrices(
            case.to_dict() for case in self.cases
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "agent_command_attempts": self.agent_command_attempts,
            "uia_value_set_attempts": self.uia_value_set_attempts,
            "uia_invoke_attempts": self.uia_invoke_attempts,
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
            "uia_semantic_action_ready_cases": self.uia_semantic_action_ready_cases,
            "uia_semantic_action_send_verified_cases": self.uia_semantic_action_send_verified_cases,
            "uia_semantic_draft_verified_cases": self.uia_semantic_draft_verified_cases,
            "app_bridge_send_verified_cases": self.app_bridge_send_verified_cases,
            "gated_cases": self.gated_cases,
            "real_verified_cases": self.real_verified_cases,
            "transport_matrix_summary": self.transport_matrix_summary,
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
    debugger_urls: Iterable[str] = (),
    debugger_urls_by_agent: dict | None = None,
    ide_bridge_urls: Iterable[str] = (),
    ide_bridge_probe: object | None = None,
    agent_native_bridge_urls: Iterable[str] = (),
    agent_native_bridge_registry_paths: Iterable[str | Path] = (),
    workspace_path: str = "",
    window_capture_provider: object | None = None,
    max_windows: int = 80,
    max_elements: int = 1200,
    request_timeout: float = 0.2,
    semantic_action_message: str = "OPENWUKONG_UIA_SEMANTIC_ACTION_DRY_RUN",
    allow_uia_semantic_action: bool = False,
    uia_semantic_sender: object | None = None,
    uia_message: str = "OPENWUKONG_UIA_SEMANTIC_ACTION_REAL_NO_LOSS",
    uia_required_markers: tuple[str, ...] = (),
    uia_forbidden_markers: tuple[str, ...] = (),
    allow_uia_semantic_draft: bool = False,
    uia_draft_writer: object | None = None,
    uia_draft_message: str = "OPENWUKONG_UIA_DRAFT_REAL_NO_LOSS",
    cleanup_uia_draft: bool = True,
    uia_draft_restore_value: str = "",
    allow_app_bridge_send: bool = False,
    app_bridge_sender: object | None = None,
    bridge_message: str = "OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
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
            debugger_urls=_debugger_urls_for_agent(
                debugger_urls,
                debugger_urls_by_agent,
                agent,
            ),
            ide_bridge_urls=tuple(ide_bridge_urls or ()),
            ide_bridge_probe=ide_bridge_probe,
            agent_native_bridge_urls=tuple(agent_native_bridge_urls or ()),
            agent_native_bridge_registry_paths=tuple(
                agent_native_bridge_registry_paths or ()
            ),
            workspace_path=workspace_path,
            screenshot_dir=str(agent_screenshot_dir) if agent_screenshot_dir else "",
            window_capture_provider=window_capture_provider,
            max_windows=max_windows,
            max_elements=max_elements,
            request_timeout=request_timeout,
        )
        probe = _report_to_dict(raw_probe)
        cases.append(
            _write_case_artifact(
                root,
                _case_from_probe(
                    agent,
                    probe,
                    project_name=str(project_name or "").strip(),
                    task_name=str(task_name or "").strip(),
                    semantic_action_message=semantic_action_message,
                    allow_uia_semantic_action=allow_uia_semantic_action,
                    uia_semantic_sender=uia_semantic_sender,
                    uia_message=uia_message,
                    uia_required_markers=tuple(uia_required_markers or ()),
                    uia_forbidden_markers=tuple(uia_forbidden_markers or ()),
                    allow_uia_semantic_draft=allow_uia_semantic_draft,
                    uia_draft_writer=uia_draft_writer,
                    uia_draft_message=uia_draft_message,
                    cleanup_uia_draft=cleanup_uia_draft,
                    uia_draft_restore_value=uia_draft_restore_value,
                    allow_app_bridge_send=allow_app_bridge_send,
                    app_bridge_sender=app_bridge_sender,
                    bridge_message=bridge_message,
                    required_markers=tuple(required_markers or ()),
                    forbidden_markers=tuple(forbidden_markers or ()),
                ),
            )
        )
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
    ide_bridge_probe: object | None = None,
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
    parser.add_argument(
        "--debugger-url",
        action="append",
        default=[],
        help="Explicit local DevTools debugger URL to probe read-only after validating port ownership by the target app process.",
    )
    parser.add_argument(
        "--ide-bridge-url",
        action="append",
        default=[],
        help="Explicit IDE extension/native bridge URL to probe read-only and use for app bridge sends when allowed.",
    )
    parser.add_argument(
        "--agent-native-bridge-url",
        action="append",
        default=[],
        help="Explicit agent app native bridge URL to probe read-only and use for app bridge sends when allowed.",
    )
    parser.add_argument(
        "--agent-native-bridge-registry",
        action="append",
        default=[],
        help="Read-only JSON registry file with agent app native bridge URLs.",
    )
    parser.add_argument(
        "--workspace-path",
        default="",
        help="Optional workspace path included in IDE bridge capability probes.",
    )
    parser.add_argument(
        "--semantic-action-message",
        default="OPENWUKONG_UIA_SEMANTIC_ACTION_DRY_RUN",
        help="Message used only to build the UIA semantic dry-run contract; it is never sent.",
    )
    parser.add_argument(
        "--allow-uia-semantic-action",
        action="store_true",
        help="Allow a UIA ValuePattern/InvokePattern semantic send when the dry-run contract is ready.",
    )
    parser.add_argument(
        "--uia-message",
        default="OPENWUKONG_UIA_SEMANTIC_ACTION_REAL_NO_LOSS",
        help="Message used for the optional UIA semantic sender.",
    )
    parser.add_argument(
        "--uia-acceptance-marker",
        action="append",
        default=[],
        help="Required marker expected after UIA semantic action. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--uia-forbid-marker",
        action="append",
        default=[],
        help="Forbidden marker that fails UIA semantic action readback. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--allow-uia-semantic-draft",
        action="store_true",
        help="Allow a UIA ValuePattern draft write and cleanup without invoking submit.",
    )
    parser.add_argument(
        "--uia-draft-message",
        default="OPENWUKONG_UIA_DRAFT_REAL_NO_LOSS",
        help="Message used for the optional UIA semantic draft writer.",
    )
    parser.add_argument(
        "--keep-uia-draft",
        action="store_true",
        help="Leave the UIA draft in the target composer instead of restoring the configured value.",
    )
    parser.add_argument(
        "--uia-draft-restore-value",
        default="",
        help="Value restored after the UIA draft write when cleanup is enabled.",
    )
    parser.add_argument(
        "--allow-app-bridge-send",
        action="store_true",
        help="Allow a native app bridge send when the dry-run contract is ready.",
    )
    parser.add_argument(
        "--bridge-message",
        default="OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
        help="Message used for the optional app bridge sender.",
    )
    parser.add_argument(
        "--acceptance-marker",
        action="append",
        default=[],
        help="Required marker expected in app bridge readback. Repeat for multiple markers.",
    )
    parser.add_argument(
        "--forbid-marker",
        action="append",
        default=[],
        help="Forbidden marker that fails app bridge readback. Repeat for multiple markers.",
    )
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
        debugger_urls=tuple(args.debugger_url or ()),
        ide_bridge_urls=tuple(args.ide_bridge_url or ()),
        ide_bridge_probe=ide_bridge_probe,
        agent_native_bridge_urls=tuple(args.agent_native_bridge_url or ()),
        agent_native_bridge_registry_paths=tuple(args.agent_native_bridge_registry or ()),
        workspace_path=args.workspace_path,
        window_capture_provider=window_capture_provider,
        max_windows=args.max_windows,
        max_elements=args.max_elements,
        request_timeout=args.request_timeout,
        semantic_action_message=args.semantic_action_message,
        allow_uia_semantic_action=args.allow_uia_semantic_action,
        uia_semantic_sender=(
            _default_uia_semantic_sender() if args.allow_uia_semantic_action else None
        ),
        uia_message=args.uia_message,
        uia_required_markers=tuple(args.uia_acceptance_marker or ()),
        uia_forbidden_markers=tuple(args.uia_forbid_marker or ()),
        allow_uia_semantic_draft=args.allow_uia_semantic_draft,
        uia_draft_writer=(
            _default_uia_semantic_draft_writer() if args.allow_uia_semantic_draft else None
        ),
        uia_draft_message=args.uia_draft_message,
        cleanup_uia_draft=not args.keep_uia_draft,
        uia_draft_restore_value=args.uia_draft_restore_value,
        allow_app_bridge_send=args.allow_app_bridge_send,
        app_bridge_sender=_default_app_bridge_sender() if args.allow_app_bridge_send else None,
        bridge_message=args.bridge_message,
        required_markers=tuple(args.acceptance_marker or ()),
        forbidden_markers=tuple(args.forbid_marker or ()),
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


def _case_from_probe(
    agent: str,
    probe: dict,
    *,
    project_name: str = "",
    task_name: str = "",
    semantic_action_message: str = "",
    allow_uia_semantic_action: bool = False,
    uia_semantic_sender: object | None = None,
    uia_message: str = "",
    uia_required_markers: tuple[str, ...] = (),
    uia_forbidden_markers: tuple[str, ...] = (),
    allow_uia_semantic_draft: bool = False,
    uia_draft_writer: object | None = None,
    uia_draft_message: str = "",
    cleanup_uia_draft: bool = True,
    uia_draft_restore_value: str = "",
    allow_app_bridge_send: bool = False,
    app_bridge_sender: object | None = None,
    bridge_message: str = "",
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
) -> AgentAppRealNoLossCase:
    decision = str(probe.get("decision", "") or "")
    transport_matrix = build_agent_app_transport_matrix(probe).to_dict()
    native_ready = int(probe.get("ready_endpoint_count", 0) or 0) > 0
    app_probe = _app_uia_probe(probe)
    matched_window_count = _counter(app_probe, "matched_window_count")
    target_matched = bool(app_probe.get("target_matched", False))
    real_verified = bool(native_ready or matched_window_count > 0 or target_matched)
    app_bridge_dry_run, app_bridge_send_report = _run_app_bridge_path(
        agent=agent,
        probe=probe,
        project_name=project_name,
        task_name=task_name,
        message=bridge_message,
        required_markers=required_markers,
        forbidden_markers=forbidden_markers,
        allow_app_bridge_send=allow_app_bridge_send,
        app_bridge_sender=app_bridge_sender,
    )
    semantic_action_dry_run, semantic_action_send_report = _run_uia_semantic_action_path(
        agent=agent,
        probe=probe,
        message=(uia_message if allow_uia_semantic_action else semantic_action_message),
        required_markers=uia_required_markers,
        forbidden_markers=uia_forbidden_markers,
        allow_uia_semantic_action=allow_uia_semantic_action,
        uia_semantic_sender=uia_semantic_sender,
    )
    semantic_draft_dry_run, semantic_draft_report = _run_uia_semantic_draft_path(
        agent=agent,
        probe=probe,
        message=uia_draft_message,
        required_markers=(),
        forbidden_markers=(),
        allow_uia_semantic_draft=allow_uia_semantic_draft,
        uia_draft_writer=uia_draft_writer,
        cleanup_uia_draft=cleanup_uia_draft,
        restore_value=uia_draft_restore_value,
    )
    control_attempts = _counter(probe, "control_attempts") + _counter(
        app_bridge_send_report,
        "control_attempts",
    ) + _counter(
        semantic_action_send_report,
        "control_attempts",
    ) + _counter(
        semantic_draft_report,
        "control_attempts",
    )
    window_input_attempts = _counter(probe, "window_input_attempts") + _counter(
        app_probe,
        "window_input_attempts",
    ) + _counter(
        app_bridge_send_report,
        "window_input_attempts",
    ) + _counter(
        semantic_action_send_report,
        "window_input_attempts",
    ) + _counter(
        semantic_draft_report,
        "window_input_attempts",
    )
    bridge_send_attempts = _counter(probe, "bridge_send_attempts") + _counter(
        app_bridge_send_report,
        "bridge_send_attempts",
    )
    command_attempts = _counter(probe, "agent_command_attempts")
    errors: list[str] = []
    if control_attempts:
        errors.append("control_attempts_nonzero")
    if window_input_attempts:
        errors.append("window_input_attempts_nonzero")
    bridge_send_verified = str(
        app_bridge_send_report.get("decision", "") or ""
    ) == "app_bridge_send_accepted"
    if bridge_send_attempts and not bridge_send_verified:
        errors.append("bridge_send_attempts_nonzero")
    if command_attempts:
        errors.append("agent_command_attempts_nonzero")
    uia_send_verified = bool(
        str(semantic_action_send_report.get("decision", "") or "")
        == "uia_semantic_action_send_accepted"
        and _counter(semantic_action_send_report, "control_attempts") == 0
        and _counter(semantic_action_send_report, "window_input_attempts") == 0
    )
    uia_draft_verified = bool(
        str(semantic_draft_report.get("decision", "") or "")
        == "uia_semantic_action_draft_verified"
        and _counter(semantic_draft_report, "control_attempts") == 0
        and _counter(semantic_draft_report, "window_input_attempts") == 0
        and _counter(semantic_draft_report, "uia_invoke_attempts") == 0
    )
    uia_draft_decision = str(semantic_draft_report.get("decision", "") or "")
    uia_draft_attempted = bool(
        _counter(semantic_draft_report, "uia_value_set_attempts")
        or _counter(semantic_draft_report, "cleanup_value_set_attempts")
    )
    uia_value_attempts = _counter(semantic_action_dry_run, "uia_value_set_attempts") + _counter(
        semantic_action_send_report,
        "uia_value_set_attempts",
    ) + _counter(
        semantic_draft_dry_run,
        "uia_value_set_attempts",
    ) + _counter(
        semantic_draft_report,
        "uia_value_set_attempts",
    )
    uia_invoke_attempts = _counter(semantic_action_dry_run, "uia_invoke_attempts") + _counter(
        semantic_action_send_report,
        "uia_invoke_attempts",
    ) + _counter(
        semantic_draft_dry_run,
        "uia_invoke_attempts",
    ) + _counter(
        semantic_draft_report,
        "uia_invoke_attempts",
    )
    if uia_value_attempts and not (uia_send_verified or uia_draft_verified):
        errors.append("uia_value_set_attempts_nonzero")
    if uia_invoke_attempts and not uia_send_verified:
        errors.append("uia_invoke_attempts_nonzero")
    if uia_draft_attempted and not uia_draft_verified:
        errors.append("uia_semantic_draft_not_verified")
    if bridge_send_verified:
        status = "app_bridge_send_accepted"
    elif uia_send_verified:
        status = "uia_semantic_action_send_accepted"
    elif uia_draft_verified:
        status = "uia_semantic_action_draft_verified"
    elif uia_draft_decision.startswith("uia_semantic_action_draft_"):
        status = uia_draft_decision
    elif decision == "agent_native_connector_ready":
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
        uia_semantic_action_dry_run=semantic_action_dry_run,
        uia_semantic_action_send_report=semantic_action_send_report,
        uia_semantic_draft_dry_run=semantic_draft_dry_run,
        uia_semantic_draft_report=semantic_draft_report,
        app_bridge_dry_run=app_bridge_dry_run,
        app_bridge_send_report=app_bridge_send_report,
        transport_matrix=transport_matrix,
        errors=tuple(errors),
    )


def _run_app_bridge_path(
    *,
    agent: str,
    probe: dict,
    project_name: str,
    task_name: str,
    message: str,
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
    allow_app_bridge_send: bool,
    app_bridge_sender: object | None,
) -> tuple[dict, dict]:
    request = build_agent_app_bridge_request(
        agent=agent,
        agent_id=str(probe.get("agent_id", "") or _agent_id_from_name(agent)),
        project_name=project_name,
        task_name=task_name,
        message=message,
        composed_message=compose_agent_conversation_message(
            project_name=project_name,
            task_name=task_name,
            message=message,
            required_markers=tuple(required_markers or ()),
            forbidden_markers=tuple(forbidden_markers or ()),
        ),
        selected_transport={"transport_id": f"{_agent_id_from_name(agent)}-desktop-shell"},
        app_surface_probe=probe,
        required_markers=tuple(required_markers or ()),
        forbidden_markers=tuple(forbidden_markers or ()),
    )
    dry_run = AgentAppBridgeDryRunAdapter().prepare(request).to_dict()
    if not allow_app_bridge_send or not bool(dry_run.get("ok", False)):
        return dry_run, {}
    sender = app_bridge_sender or _default_app_bridge_sender()
    try:
        send = getattr(sender, "send", None)
        if callable(send):
            return dry_run, _report_to_dict(send(request))
        if callable(sender):
            return dry_run, _report_to_dict(sender(request))
        return dry_run, {
            "mode": "agent-app-bridge-send",
            "safety_mode": "native_bridge_execute",
            "ok": False,
            "decision": "app_bridge_sender_not_callable",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "bridge_send_attempts": 0,
            "native_call_attempts": 0,
        }
    except Exception as exc:
        return dry_run, {
            "mode": "agent-app-bridge-send",
            "safety_mode": "native_bridge_execute",
            "ok": False,
            "decision": "app_bridge_sender_failed",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "bridge_send_attempts": 1,
            "native_call_attempts": 1,
            "error": str(exc) or exc.__class__.__name__,
            "request": request.to_dict(),
        }


def _default_app_bridge_sender() -> AgentAppBridgeNativeAdapter:
    return AgentAppBridgeNativeAdapter()


def _run_uia_semantic_action_path(
    *,
    agent: str,
    probe: dict,
    message: str,
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
    allow_uia_semantic_action: bool,
    uia_semantic_sender: object | None,
) -> tuple[dict, dict]:
    request = _build_uia_semantic_action_request(
        agent,
        probe,
        message=message,
        required_markers=required_markers,
        forbidden_markers=forbidden_markers,
    )
    dry_run = AgentAppUiaSemanticActionDryRunAdapter().prepare(request).to_dict()
    if not allow_uia_semantic_action or not bool(dry_run.get("ok", False)):
        return dry_run, {}
    sender = uia_semantic_sender or _default_uia_semantic_sender()
    try:
        send = getattr(sender, "send", None)
        if callable(send):
            return dry_run, _report_to_dict(send(request))
        if callable(sender):
            return dry_run, _report_to_dict(sender(request))
        return dry_run, {
            "mode": "agent-app-uia-semantic-action-send",
            "safety_mode": "uia_semantic_execute",
            "ok": False,
            "decision": "uia_semantic_sender_not_callable",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "uia_value_set_attempts": 0,
            "uia_invoke_attempts": 0,
        }
    except Exception as exc:
        return dry_run, {
            "mode": "agent-app-uia-semantic-action-send",
            "safety_mode": "uia_semantic_execute",
            "ok": False,
            "decision": "uia_semantic_action_send_failed",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "uia_value_set_attempts": 0,
            "uia_invoke_attempts": 0,
            "error": str(exc) or exc.__class__.__name__,
            "request": request.to_dict(),
        }


def _run_uia_semantic_draft_path(
    *,
    agent: str,
    probe: dict,
    message: str,
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
    allow_uia_semantic_draft: bool,
    uia_draft_writer: object | None,
    cleanup_uia_draft: bool,
    restore_value: str,
) -> tuple[dict, dict]:
    request = _build_uia_semantic_action_request(
        agent,
        probe,
        message=message,
        required_markers=required_markers,
        forbidden_markers=forbidden_markers,
    )
    dry_run = AgentAppUiaSemanticDraftDryRunAdapter().prepare(request).to_dict()
    if not allow_uia_semantic_draft or not bool(dry_run.get("ok", False)):
        return dry_run, {}
    writer = uia_draft_writer or _default_uia_semantic_draft_writer()
    try:
        draft = getattr(writer, "draft", None)
        if callable(draft):
            return dry_run, _report_to_dict(
                draft(request, cleanup=cleanup_uia_draft, restore_value=restore_value)
            )
        if callable(writer):
            return dry_run, _report_to_dict(
                writer(request, cleanup=cleanup_uia_draft, restore_value=restore_value)
            )
        return dry_run, {
            "mode": "agent-app-uia-semantic-action-draft",
            "safety_mode": "uia_semantic_draft",
            "ok": False,
            "decision": "uia_semantic_draft_writer_not_callable",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "uia_value_set_attempts": 0,
            "uia_invoke_attempts": 0,
            "cleanup_value_set_attempts": 0,
        }
    except Exception as exc:
        return dry_run, {
            "mode": "agent-app-uia-semantic-action-draft",
            "safety_mode": "uia_semantic_draft",
            "ok": False,
            "decision": "uia_semantic_action_draft_failed",
            "control_attempts": 0,
            "window_input_attempts": 0,
            "uia_value_set_attempts": 0,
            "uia_invoke_attempts": 0,
            "cleanup_value_set_attempts": 0,
            "error": str(exc) or exc.__class__.__name__,
            "request": request.to_dict(),
        }


def _default_uia_semantic_sender() -> AgentAppUiaSemanticActionSenderAdapter:
    return AgentAppUiaSemanticActionSenderAdapter()


def _default_uia_semantic_draft_writer() -> AgentAppUiaSemanticDraftWriterAdapter:
    return AgentAppUiaSemanticDraftWriterAdapter()


def _build_uia_semantic_action_dry_run(agent: str, probe: dict, *, message: str) -> dict:
    request = _build_uia_semantic_action_request(agent, probe, message=message)
    return AgentAppUiaSemanticActionDryRunAdapter().prepare(request).to_dict()


def _build_uia_semantic_action_request(
    agent: str,
    probe: dict,
    *,
    message: str,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
):
    app_probe = _app_uia_probe(probe)
    surface = app_probe.get("surface_binding")
    selected_transport = app_probe.get("selected_transport")
    agent_id = str(
        probe.get("agent_id", "")
        or app_probe.get("agent_id", "")
        or _agent_id_from_name(agent)
        or ""
    )
    if not isinstance(surface, dict):
        surface = {}
    if not isinstance(selected_transport, dict):
        selected_transport = {}
    return build_agent_app_uia_semantic_action_request(
        agent=agent,
        agent_id=agent_id,
        project_name=str(probe.get("project_name", "") or ""),
        task_name=str(probe.get("task_name", "") or ""),
        message=message,
        selected_transport=selected_transport,
        app_surface_probe=probe,
        required_markers=tuple(required_markers or ()),
        forbidden_markers=tuple(forbidden_markers or ()),
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


def _debugger_urls_for_agent(
    explicit_urls: Iterable[str],
    debugger_urls_by_agent: dict | None,
    agent: str,
) -> tuple[str, ...]:
    urls: list[str] = []
    for value in explicit_urls or ():
        text = str(value or "").strip()
        if text and text not in urls:
            urls.append(text)
    mapping = debugger_urls_by_agent if isinstance(debugger_urls_by_agent, dict) else {}
    keys = (
        str(agent or "").strip().lower(),
        _agent_id_from_name(agent).lower(),
    )
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            candidates = (value,)
        else:
            candidates = tuple(value or ())
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and text not in urls:
                urls.append(text)
    return tuple(urls)


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


def _agent_id_from_name(agent: str) -> str:
    text = str(agent or "").strip().lower()
    if text.startswith("codex"):
        return "codex"
    if text.startswith("claude"):
        return "claude"
    if text.startswith("cursor"):
        return "cursor"
    return text.split(" ", 1)[0] if text else ""


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
