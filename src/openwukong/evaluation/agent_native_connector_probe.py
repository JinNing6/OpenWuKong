# -*- coding: utf-8 -*-
"""Read-only native connector discovery for agent desktop app surfaces."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol

from openwukong.control.app_resolution import WindowsAppResolver, lower_text
from openwukong.evaluation.agent_app_uia_probe import (
    AgentAppUiaProbeReport,
    run_agent_app_uia_probe,
)


class NativeConnectorHTTPProbe(Protocol):
    def get_json(self, url: str, timeout: float = 0.2):
        ...


@dataclasses.dataclass(frozen=True)
class NativeProcessSnapshot:
    pid: int
    process_name: str
    executable_path: str = ""
    command_line: str = ""

    def to_dict(self) -> dict:
        return {
            "pid": int(self.pid or 0),
            "process_name": self.process_name,
            "executable_path": self.executable_path,
            "command_line": self.command_line,
        }


@dataclasses.dataclass(frozen=True)
class NativeConnectorTarget:
    target_id: str = ""
    type: str = ""
    title: str = ""
    url: str = ""
    web_socket_debugger_url: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.web_socket_debugger_url)

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "type": self.type,
            "title": self.title,
            "url": self.url,
            "webSocketDebuggerUrl": self.web_socket_debugger_url,
            "ready": self.ready,
        }


@dataclasses.dataclass(frozen=True)
class NativeConnectorEndpoint:
    debugger_url: str
    port: int
    source: str
    process: NativeProcessSnapshot | None = None
    version: dict | None = None
    targets: tuple[NativeConnectorTarget, ...] = ()
    error: str = ""

    @property
    def ready(self) -> bool:
        return bool(not self.error and self.version and any(target.ready for target in self.targets))

    @property
    def target_count(self) -> int:
        return len(self.targets)

    def to_dict(self) -> dict:
        return {
            "debugger_url": self.debugger_url,
            "port": int(self.port or 0),
            "source": self.source,
            "ready": self.ready,
            "target_count": self.target_count,
            "version": dict(self.version or {}),
            "targets": [target.to_dict() for target in self.targets],
            "process": self.process.to_dict() if self.process else {},
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class AgentNativeConnectorProbeReport:
    agent: str
    project_name: str
    task_name: str
    app_uia_probe: AgentAppUiaProbeReport
    endpoints: tuple[NativeConnectorEndpoint, ...] = ()
    process_count: int = 0
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-native-connector-probe"

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
    def endpoint_count(self) -> int:
        return len(self.endpoints)

    @property
    def ready_endpoint_count(self) -> int:
        return sum(1 for endpoint in self.endpoints if endpoint.ready)

    @property
    def ok(self) -> bool:
        return bool(self.app_uia_probe.target_matched and self.ready_endpoint_count)

    @property
    def decision(self) -> str:
        if self.app_uia_probe.decision == "agent_app_surface_not_ready":
            return "agent_app_surface_not_ready"
        if not self.app_uia_probe.matched_window_count:
            return "agent_app_window_not_found"
        if self.ready_endpoint_count:
            if self.app_uia_probe.target_matched:
                return "agent_native_connector_ready"
            return "agent_app_target_not_visible"
        if self.endpoint_count:
            return "agent_native_connector_endpoint_unhealthy"
        return "agent_native_connector_not_exposed"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "agent": self.agent,
            "agent_id": self.app_uia_probe.surface_binding.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "process_count": int(self.process_count or 0),
            "endpoint_count": self.endpoint_count,
            "ready_endpoint_count": self.ready_endpoint_count,
            "endpoints": [endpoint.to_dict() for endpoint in self.endpoints],
            "app_uia_probe": self.app_uia_probe.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_native_connector_probe(
    *,
    agent: str,
    project_name: str = "",
    task_name: str = "",
    observer: object | None = None,
    resolver: WindowsAppResolver | None = None,
    process_provider: Callable[[], Iterable[NativeProcessSnapshot]] | None = None,
    http_probe: NativeConnectorHTTPProbe | None = None,
    screenshot_dir: str | Path = "",
    window_capture_provider: object | None = None,
    max_windows: int = 80,
    max_elements: int = 1200,
    request_timeout: float = 0.2,
) -> AgentNativeConnectorProbeReport:
    started = time.perf_counter()
    app_probe = run_agent_app_uia_probe(
        agent=agent,
        project_name=project_name,
        task_name=task_name,
        observer=observer,
        resolver=resolver,
        screenshot_dir=screenshot_dir,
        window_capture_provider=window_capture_provider,
        max_windows=max_windows,
        max_elements=max_elements,
    )
    provider = process_provider or list_native_processes
    processes = tuple(provider())
    matching = tuple(_matching_agent_processes(processes, app_probe))
    endpoints = _discover_debugger_endpoints(
        matching,
        http_probe=http_probe or RequestsNativeConnectorHTTPProbe(),
        timeout=max(0.05, float(request_timeout)),
    )
    return AgentNativeConnectorProbeReport(
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        app_uia_probe=app_probe,
        endpoints=endpoints,
        process_count=len(processes),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


class RequestsNativeConnectorHTTPProbe:
    """Small read-only local HTTP probe for DevTools metadata endpoints."""

    def get_json(self, url: str, timeout: float = 0.2):
        import requests

        response = requests.get(url, timeout=max(0.05, float(timeout)))
        response.raise_for_status()
        return response.json()


def list_native_processes() -> tuple[NativeProcessSnapshot, ...]:
    try:
        import psutil
    except Exception:
        return ()

    snapshots: list[NativeProcessSnapshot] = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            info = proc.info
            cmdline = info.get("cmdline") or ()
            command_text = _join_command_line(cmdline)
            snapshots.append(
                NativeProcessSnapshot(
                    pid=int(info.get("pid", 0) or 0),
                    process_name=str(info.get("name", "") or ""),
                    executable_path=str(info.get("exe", "") or ""),
                    command_line=command_text,
                )
            )
        except Exception:
            continue
    return tuple(snapshots)


def format_agent_native_connector_probe_report(report: AgentNativeConnectorProbeReport) -> str:
    lines = [
        "Agent Native Connector Probe",
        f"Decision: {report.decision}  OK: {str(report.ok).lower()}  Control attempts: {report.control_attempts}",
        f"Agent: {report.agent}  Project: {report.project_name or '-'}  Task: {report.task_name or '-'}",
        f"Processes scanned: {report.process_count}  Endpoints: {report.endpoint_count}  Ready: {report.ready_endpoint_count}",
        f"App UIA: {report.app_uia_probe.decision}",
    ]
    for endpoint in report.endpoints:
        lines.append(
            f"- {endpoint.debugger_url} ready={str(endpoint.ready).lower()} "
            f"targets={endpoint.target_count} source={endpoint.source}"
        )
    return "\n".join(lines).rstrip()


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
    observer: object | None = None,
    process_provider: Callable[[], Iterable[NativeProcessSnapshot]] | None = None,
    http_probe: NativeConnectorHTTPProbe | None = None,
    window_capture_provider: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only native connector probe for an agent app."
    )
    parser.add_argument("--agent", required=True)
    parser.add_argument("--project-name", default="")
    parser.add_argument("--task-name", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--max-windows", type=int, default=80)
    parser.add_argument("--max-elements", type=int, default=1200)
    parser.add_argument("--request-timeout", type=float, default=0.2)
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else WindowsAppResolver()
    report = run_agent_native_connector_probe(
        agent=args.agent,
        project_name=args.project_name,
        task_name=args.task_name,
        observer=observer,
        resolver=resolver,
        process_provider=process_provider,
        http_probe=http_probe,
        screenshot_dir=args.screenshot_dir,
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
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _write_stdout(format_agent_native_connector_probe_report(report))
    return 0


def _matching_agent_processes(
    processes: Iterable[NativeProcessSnapshot],
    app_probe: AgentAppUiaProbeReport,
) -> tuple[NativeProcessSnapshot, ...]:
    selected = app_probe.surface_binding.selected_transport
    selected_pid = int(selected.pid or 0) if selected else 0
    selected_path = lower_text(selected.path if selected else "")
    selected_dir = _parent_dir(selected_path)
    expected_names = set(_agent_process_names(app_probe.surface_binding.agent_id))
    matched: list[NativeProcessSnapshot] = []
    for process in processes:
        pname = lower_text(process.process_name)
        path = lower_text(process.executable_path)
        if selected_pid and int(process.pid or 0) == selected_pid:
            matched.append(process)
            continue
        if pname not in expected_names:
            continue
        if selected_dir and path and path.startswith(selected_dir):
            matched.append(process)
            continue
        if not selected_dir:
            matched.append(process)
    return tuple(matched)


def _discover_debugger_endpoints(
    processes: Iterable[NativeProcessSnapshot],
    *,
    http_probe: NativeConnectorHTTPProbe,
    timeout: float,
) -> tuple[NativeConnectorEndpoint, ...]:
    endpoints: list[NativeConnectorEndpoint] = []
    seen_ports: set[int] = set()
    for process in processes:
        for port in _extract_remote_debugging_ports(process.command_line):
            if port in seen_ports:
                continue
            seen_ports.add(port)
            endpoints.append(
                _probe_debugger_endpoint(
                    port,
                    process=process,
                    source="process-command-line",
                    http_probe=http_probe,
                    timeout=timeout,
                )
            )
    return tuple(endpoints)


def _probe_debugger_endpoint(
    port: int,
    *,
    process: NativeProcessSnapshot,
    source: str,
    http_probe: NativeConnectorHTTPProbe,
    timeout: float,
) -> NativeConnectorEndpoint:
    base = f"http://127.0.0.1:{int(port)}"
    try:
        version = http_probe.get_json(f"{base}/json/version", timeout=timeout)
        if not isinstance(version, dict):
            raise ValueError("devtools_version_not_object")
        targets_raw = http_probe.get_json(f"{base}/json/list", timeout=timeout)
        if not isinstance(targets_raw, list):
            raise ValueError("devtools_targets_not_list")
        targets = tuple(
            _target_from_dict(item)
            for item in targets_raw
            if isinstance(item, dict)
        )
        return NativeConnectorEndpoint(
            debugger_url=base,
            port=int(port),
            source=source,
            process=process,
            version=version,
            targets=targets,
        )
    except Exception as exc:
        return NativeConnectorEndpoint(
            debugger_url=base,
            port=int(port),
            source=source,
            process=process,
            error=str(exc) or exc.__class__.__name__,
        )


def _target_from_dict(data: dict) -> NativeConnectorTarget:
    return NativeConnectorTarget(
        target_id=str(data.get("id", "") or data.get("targetId", "") or ""),
        type=str(data.get("type", "") or ""),
        title=str(data.get("title", "") or ""),
        url=str(data.get("url", "") or ""),
        web_socket_debugger_url=str(data.get("webSocketDebuggerUrl", "") or ""),
    )


def _extract_remote_debugging_ports(command_line: str) -> tuple[int, ...]:
    text = str(command_line or "")
    ports: list[int] = []
    patterns = (
        r"--remote-debugging-port=(\d+)",
        r"--remote-debugging-port\s+(\d+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            port = int(match.group(1))
            if 0 < port <= 65535:
                ports.append(port)
    return tuple(dict.fromkeys(ports))


def _agent_process_names(agent_id: str) -> tuple[str, ...]:
    normalized = lower_text(agent_id)
    if normalized == "codex":
        return ("codex.exe",)
    if normalized == "claude":
        return ("claude.exe",)
    return (normalized,)


def _parent_dir(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if "/" not in normalized:
        return ""
    return normalized.rsplit("/", 1)[0].rstrip("/") + "/"


def _join_command_line(cmdline: object) -> str:
    if isinstance(cmdline, str):
        return cmdline
    try:
        return " ".join(str(item) for item in cmdline)
    except TypeError:
        return ""


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
