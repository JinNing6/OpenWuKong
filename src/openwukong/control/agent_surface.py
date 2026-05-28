# -*- coding: utf-8 -*-
"""Read-only agent product surface binding.

This layer does not execute agent commands. It maps a resolved product identity
to the safest available transport class so execution can stay behind the
existing side-effect gates.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    AppResolutionReport,
    WindowsAppResolver,
    claude_candidate_surface_kind,
    lower_text,
)
from openwukong.control.side_effects import (
    SideEffectGateReport,
    build_side_effect_policy,
    evaluate_side_effect_policy,
)


AGENT_TASK_EFFECT_IDS = (
    "agent_task_submission.submit_task",
    "agent_start.start_agent",
)


@dataclasses.dataclass(frozen=True)
class AgentTransportSurface:
    transport_id: str
    display_name: str
    route_id: str
    transport: str
    source: str = ""
    path: str = ""
    pid: int = 0
    background_capable: bool = False
    ready: bool = False
    execution_allowed: bool = False
    control_allowed: bool = False
    command_family: str = ""
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "transport_id": self.transport_id,
            "display_name": self.display_name,
            "route_id": self.route_id,
            "transport": self.transport,
            "source": self.source,
            "path": self.path,
            "pid": int(self.pid or 0),
            "background_capable": self.background_capable,
            "ready": self.ready,
            "execution_allowed": self.execution_allowed,
            "control_allowed": self.control_allowed,
            "command_family": self.command_family,
            "notes": list(self.notes),
        }


@dataclasses.dataclass(frozen=True)
class AgentSurfaceBindingReport:
    agent_name: str
    app_resolution: AppResolutionReport
    transports: tuple[AgentTransportSurface, ...]
    side_effect_gate: SideEffectGateReport

    @property
    def mode(self) -> str:
        return "agent-surface-binding"

    @property
    def agent_id(self) -> str:
        return self.app_resolution.identity.app_id

    @property
    def selected_transport(self) -> AgentTransportSurface | None:
        for transport in self.transports:
            if transport.ready and transport.background_capable:
                return transport
        for transport in self.transports:
            if transport.ready:
                return transport
        return None

    @property
    def ok(self) -> bool:
        return bool(self.app_resolution.ok and self.selected_transport is not None)

    @property
    def decision(self) -> str:
        if not self.app_resolution.ok:
            return "agent_app_not_found"
        if self.selected_transport is None:
            return "agent_transport_not_ready"
        return "agent_surface_ready"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        selected = self.selected_transport
        return {
            "mode": self.mode,
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "selected_transport": selected.to_dict() if selected else {},
            "transports": [transport.to_dict() for transport in self.transports],
            "side_effect_gate": self.side_effect_gate.to_dict(),
            "app_resolution": _app_resolution_entry(self.agent_name, self.app_resolution),
        }


def build_agent_surface_binding(
    agent_name: str,
    *,
    resolver: WindowsAppResolver | None = None,
) -> AgentSurfaceBindingReport:
    active_resolver = resolver or WindowsAppResolver()
    resolution = active_resolver.resolve(agent_name)
    transports = _build_transports(resolution, requested_agent_name=agent_name)
    policy = build_side_effect_policy(
        blocked_effect_ids=AGENT_TASK_EFFECT_IDS,
        confirmation_required_effect_ids=AGENT_TASK_EFFECT_IDS,
    )
    gate = evaluate_side_effect_policy(policy)
    return AgentSurfaceBindingReport(
        agent_name=str(agent_name or "").strip(),
        app_resolution=resolution,
        transports=transports,
        side_effect_gate=gate,
    )


def _build_transports(
    resolution: AppResolutionReport,
    *,
    requested_agent_name: str = "",
) -> tuple[AgentTransportSurface, ...]:
    if not resolution.ok:
        return ()
    app_id = resolution.identity.app_id
    require_desktop = _request_requires_desktop_surface(requested_agent_name)
    if app_id == "codex":
        return _dedupe_transports(
            _codex_transports(resolution.candidates, require_desktop=require_desktop)
        )
    if app_id == "claude":
        return _dedupe_transports(
            _claude_transports(resolution.candidates, require_desktop=require_desktop)
        )
    if app_id == "cursor":
        return _dedupe_transports(_cursor_transports(resolution.candidates))
    return ()


def _codex_transports(
    candidates: tuple[AppResolutionCandidate, ...],
    *,
    require_desktop: bool = False,
) -> tuple[AgentTransportSurface, ...]:
    cli: list[AgentTransportSurface] = []
    desktop: list[AgentTransportSurface] = []
    workers: list[AgentTransportSurface] = []
    for candidate in candidates:
        exe = _candidate_file_name(candidate)
        if not require_desktop and _is_codex_standalone_cli(candidate):
            cli.append(
                AgentTransportSurface(
                    transport_id="codex-cli-managed-terminal",
                    display_name="Codex CLI",
                    route_id="terminal-native-session",
                    transport="managed-terminal-cli",
                    source=candidate.source,
                    path=candidate.path,
                    pid=candidate.pid,
                    background_capable=True,
                    ready=True,
                    execution_allowed=False,
                    control_allowed=False,
                    command_family="codex",
                    notes=("agent_task_submission_requires_confirmation",),
                )
            )
        elif _is_codex_desktop_shell(candidate):
            desktop.append(
                AgentTransportSurface(
                    transport_id="codex-desktop-shell",
                    display_name="Codex Desktop Shell",
                    route_id="codex-desktop-connector",
                    transport="desktop-shell-uia-or-native-bridge",
                    source=candidate.source,
                    path=_candidate_control_target(candidate),
                    pid=candidate.pid,
                    background_capable=False,
                    ready=True,
                    execution_allowed=False,
                    control_allowed=False,
                    notes=("background_task_submit_requires_ide_or_native_bridge",),
                )
            )
        elif not require_desktop and lower_text(exe).startswith("codex"):
            workers.append(
                AgentTransportSurface(
                    transport_id="codex-extension-worker",
                    display_name="Codex Helper Or Extension Worker",
                    route_id="agent-helper-evidence-only",
                    transport="helper-process",
                    source=candidate.source,
                    path=candidate.path,
                    pid=candidate.pid,
                    background_capable=False,
                    ready=False,
                    execution_allowed=False,
                    control_allowed=False,
                    notes=("helper_process_not_a_task_submission_surface",),
                )
            )
    return tuple(cli + desktop + workers)


def _claude_transports(
    candidates: tuple[AppResolutionCandidate, ...],
    *,
    require_desktop: bool = False,
) -> tuple[AgentTransportSurface, ...]:
    cli: list[AgentTransportSurface] = []
    desktop: list[AgentTransportSurface] = []
    for candidate in candidates:
        if not require_desktop and _is_claude_code_cli(candidate):
            cli.append(
                AgentTransportSurface(
                    transport_id="claude-code-cli-managed-terminal",
                    display_name="Claude Code CLI",
                    route_id="terminal-native-session",
                    transport="managed-terminal-cli",
                    source=candidate.source,
                    path=candidate.path,
                    pid=candidate.pid,
                    background_capable=True,
                    ready=True,
                    execution_allowed=False,
                    control_allowed=False,
                    command_family="claude -p",
                    notes=("agent_task_submission_requires_confirmation",),
                )
            )
        elif _is_claude_desktop_shell(candidate):
            desktop.append(
                AgentTransportSurface(
                    transport_id="claude-desktop-shell",
                    display_name="Claude Desktop Shell",
                    route_id="claude-desktop-connector-required",
                    transport="desktop-shell-native-bridge-or-foreground",
                    source=candidate.source,
                    path=_candidate_control_target(candidate),
                    pid=candidate.pid,
                    background_capable=False,
                    ready=True,
                    execution_allowed=False,
                    control_allowed=False,
                    notes=("app_task_submit_requires_native_bridge_or_foreground_takeover",),
                )
            )
    return tuple(cli + desktop)


def _cursor_transports(
    candidates: tuple[AppResolutionCandidate, ...],
) -> tuple[AgentTransportSurface, ...]:
    desktop: list[AgentTransportSurface] = []
    for candidate in candidates:
        exe = lower_text(_candidate_file_name(candidate))
        if exe != "cursor.exe":
            continue
        desktop.append(
            AgentTransportSurface(
                transport_id="cursor-desktop-shell",
                display_name="Cursor Desktop Shell",
                route_id="cursor-desktop-connector",
                transport="desktop-shell-uia-or-native-bridge",
                source=candidate.source,
                path=_candidate_control_target(candidate),
                pid=candidate.pid,
                background_capable=False,
                ready=True,
                execution_allowed=False,
                control_allowed=False,
                notes=("background_task_submit_requires_ide_or_native_bridge",),
            )
        )
    return tuple(desktop)


def _is_codex_standalone_cli(candidate: AppResolutionCandidate) -> bool:
    path_text = _normalized_path(candidate.path)
    exe = lower_text(_candidate_file_name(candidate))
    if ".cursor/extensions/" in path_text or "/resources/" in path_text:
        return False
    if "/appdata/local/openai/codex/bin/" in path_text:
        return True
    if exe in {"codex.cmd", "codex.bat", "codex"}:
        return True
    return bool(candidate.source == "path" and exe == "codex.exe")


def _is_codex_desktop_shell(candidate: AppResolutionCandidate) -> bool:
    path_text = _normalized_path(candidate.path)
    exe = _candidate_file_name(candidate)
    name = _candidate_normalized_name(candidate)
    if candidate.source == "start-apps" and name in {"codex", "openaicodex"}:
        return True
    return exe == "Codex.exe" or path_text.endswith("/app/codex.exe")


def _is_claude_code_cli(candidate: AppResolutionCandidate) -> bool:
    return claude_candidate_surface_kind(candidate) == "cli"


def _is_claude_desktop_shell(candidate: AppResolutionCandidate) -> bool:
    return claude_candidate_surface_kind(candidate) == "desktop"


def _request_requires_desktop_surface(agent_name: str) -> bool:
    normalized = " ".join(str(agent_name or "").strip().lower().split())
    if not normalized or "cli" in normalized:
        return False
    return any(token in normalized.split() for token in ("app", "desktop"))


def _candidate_executable(candidate: AppResolutionCandidate) -> str:
    for value in (candidate.executable_name, candidate.process_name, Path(candidate.path).name, candidate.display_name):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _candidate_file_name(candidate: AppResolutionCandidate) -> str:
    for value in (
        candidate.executable_name,
        candidate.process_name,
        Path(candidate.path).name if candidate.path else "",
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _candidate_normalized_name(candidate: AppResolutionCandidate) -> str:
    for value in (
        candidate.display_name,
        candidate.executable_name,
        candidate.process_name,
        Path(candidate.path).stem if candidate.path else "",
    ):
        text = "".join(ch for ch in str(value or "").strip().lower() if not ch.isspace())
        if text:
            return text
    return ""


def _candidate_control_target(candidate: AppResolutionCandidate) -> str:
    app_id = ""
    if isinstance(candidate.metadata, dict):
        app_id = str(candidate.metadata.get("app_id", "") or "").strip()
    return str(candidate.path or "").strip() or app_id


def _normalized_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lower()


def _dedupe_transports(
    transports: tuple[AgentTransportSurface, ...],
) -> tuple[AgentTransportSurface, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[AgentTransportSurface] = []
    for transport in transports:
        key = (transport.transport_id, lower_text(transport.path))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(transport)
    return tuple(deduped)


def _app_resolution_entry(agent_name: str, resolution: AppResolutionReport) -> dict:
    data = resolution.to_dict()
    candidates = data.get("candidates", [])
    return {
        "app_name": agent_name,
        "ok": bool(data.get("ok")),
        "decision": str(data.get("decision", "")),
        "source": str(data.get("source", "")),
        "path": str(data.get("path", "")),
        "already_running": bool(data.get("already_running")),
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "selected_candidate": data.get("selected_candidate", {}),
        "resolution": data,
    }


__all__ = [
    "AGENT_TASK_EFFECT_IDS",
    "AgentSurfaceBindingReport",
    "AgentTransportSurface",
    "build_agent_surface_binding",
]
