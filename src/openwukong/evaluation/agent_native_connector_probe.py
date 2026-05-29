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
from urllib.parse import urlsplit

from openwukong.control.app_resolution import WindowsAppResolver, lower_text
from openwukong.control.agent_native_bridge import (
    SEND_ACTION as AGENT_NATIVE_SEND_ACTION,
    AgentNativeBridgeDryRunAdapter,
    build_agent_native_bridge_request,
)
from openwukong.control.native_bridge_registry import discover_agent_native_bridge_urls
from openwukong.evaluation.agent_app_uia_probe import (
    AgentAppUiaProbeReport,
    run_agent_app_uia_probe,
)
from openwukong.evaluation.ide_bridge_capture import capture_ide_bridge_capabilities


class NativeConnectorHTTPProbe(Protocol):
    def get_json(self, url: str, timeout: float = 0.2):
        ...


@dataclasses.dataclass(frozen=True)
class NativeProcessSnapshot:
    pid: int
    process_name: str
    executable_path: str = ""
    command_line: str = ""
    listening_ports: tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return {
            "pid": int(self.pid or 0),
            "process_name": self.process_name,
            "executable_path": self.executable_path,
            "command_line": self.command_line,
            "listening_ports": [int(port) for port in self.listening_ports],
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
    endpoint_type: str = "devtools"
    bridge_url: str = ""
    process: NativeProcessSnapshot | None = None
    version: dict | None = None
    targets: tuple[NativeConnectorTarget, ...] = ()
    metadata: dict | None = None
    commands: tuple[str, ...] = ()
    chat_adapters: tuple[dict, ...] = ()
    adapter_mapping: dict | None = None
    preferred_chat_adapter: str = ""
    send_command_id: str = ""
    capability_ok: bool = False
    error: str = ""

    @property
    def ready(self) -> bool:
        if self.endpoint_type == "ide_bridge":
            return bool(
                not self.error
                and self.capability_ok
                and self.bridge_url
                and (self.preferred_chat_adapter or self.send_command_id)
            )
        if self.endpoint_type == "agent_native_bridge":
            return bool(
                not self.error
                and self.capability_ok
                and self.bridge_url
                and self.preferred_chat_adapter
                and self.send_command_id
                and _agent_native_bridge_surface_ok(dict(self.metadata or {}))
                and _agent_native_bridge_app_binding_ok(dict(self.metadata or {}))
            )
        return bool(not self.error and self.version and any(target.ready for target in self.targets))

    @property
    def target_count(self) -> int:
        return len(self.targets)

    def to_dict(self) -> dict:
        return {
            "endpoint_type": self.endpoint_type,
            "debugger_url": self.debugger_url,
            "bridge_url": self.bridge_url,
            "port": int(self.port or 0),
            "source": self.source,
            "ready": self.ready,
            "target_count": self.target_count,
            "version": dict(self.version or {}),
            "targets": [target.to_dict() for target in self.targets],
            "metadata": dict(self.metadata or {}),
            "command_count": len(self.commands),
            "commands": list(self.commands),
            "chat_adapters": [dict(adapter) for adapter in self.chat_adapters],
            "adapter_mapping": dict(self.adapter_mapping or {}),
            "preferred_chat_adapter": self.preferred_chat_adapter,
            "send_command_id": self.send_command_id,
            "capability_ok": self.capability_ok,
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
    debugger_urls: Iterable[str] = (),
    ide_bridge_urls: Iterable[str] = (),
    ide_bridge_probe: Callable[..., object] | None = None,
    agent_native_bridge_urls: Iterable[str] = (),
    agent_native_bridge_registry_paths: Iterable[str | Path] = (),
    agent_native_bridge_probe: Callable[..., object] | None = None,
    workspace_path: str = "",
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
    debugger_endpoints = _discover_debugger_endpoints(
        matching,
        reserved_ports=_ports_from_debugger_urls(debugger_urls),
        http_probe=http_probe or RequestsNativeConnectorHTTPProbe(),
        timeout=max(0.05, float(request_timeout)),
    )
    explicit_debugger_endpoints = _discover_explicit_debugger_endpoints(
        debugger_urls,
        matching_processes=matching,
        known_ports={endpoint.port for endpoint in debugger_endpoints},
        http_probe=http_probe or RequestsNativeConnectorHTTPProbe(),
        timeout=max(0.05, float(request_timeout)),
    )
    ide_endpoints = _discover_ide_bridge_endpoints(
        ide_bridge_urls,
        ide_bridge_probe=ide_bridge_probe or capture_ide_bridge_capabilities,
        timeout=max(0.05, float(request_timeout)),
        workspace_path=str(workspace_path or ""),
        agent_id=app_probe.surface_binding.agent_id,
    )
    agent_native_endpoints = _discover_agent_native_bridge_endpoints(
        discover_agent_native_bridge_urls(
            agent_native_bridge_urls,
            agent_id=app_probe.surface_binding.agent_id,
            registry_paths=agent_native_bridge_registry_paths,
        ),
        agent_native_bridge_probe=(
            agent_native_bridge_probe
            or AgentNativeBridgeDryRunAdapter(
                request_timeout=max(0.05, float(request_timeout))
            ).prepare
        ),
        agent=str(agent or "").strip(),
        agent_id=app_probe.surface_binding.agent_id,
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        app_probe=app_probe,
    )
    return AgentNativeConnectorProbeReport(
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        app_uia_probe=app_probe,
        endpoints=(
            tuple(debugger_endpoints)
            + tuple(explicit_debugger_endpoints)
            + tuple(ide_endpoints)
            + tuple(agent_native_endpoints)
        ),
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

    listening_ports_by_pid = _listening_ports_by_pid(psutil)
    snapshots: list[NativeProcessSnapshot] = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            info = proc.info
            pid = int(info.get("pid", 0) or 0)
            cmdline = info.get("cmdline") or ()
            command_text = _join_command_line(cmdline)
            snapshots.append(
                NativeProcessSnapshot(
                    pid=pid,
                    process_name=str(info.get("name", "") or ""),
                    executable_path=str(info.get("exe", "") or ""),
                    command_line=command_text,
                    listening_ports=tuple(listening_ports_by_pid.get(pid, ())),
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
        endpoint_url = (
            endpoint.bridge_url
            if endpoint.endpoint_type in {"ide_bridge", "agent_native_bridge"}
            else endpoint.debugger_url
        )
        lines.append(
            f"- {endpoint_url} type={endpoint.endpoint_type} ready={str(endpoint.ready).lower()} "
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
    ide_bridge_probe: Callable[..., object] | None = None,
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
        help="Explicit IDE extension/native bridge URL to probe read-only. Repeat for multiple bridges.",
    )
    parser.add_argument(
        "--agent-native-bridge-url",
        action="append",
        default=[],
        help="Explicit agent app native bridge URL to probe read-only. Repeat for multiple bridges.",
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
        debugger_urls=tuple(args.debugger_url or ()),
        ide_bridge_urls=tuple(args.ide_bridge_url or ()),
        ide_bridge_probe=ide_bridge_probe,
        agent_native_bridge_urls=tuple(args.agent_native_bridge_url or ()),
        agent_native_bridge_registry_paths=tuple(args.agent_native_bridge_registry or ()),
        workspace_path=args.workspace_path,
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
        if _extract_remote_debugging_ports(process.command_line):
            matched.append(process)
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
    reserved_ports: Iterable[int] = (),
    http_probe: NativeConnectorHTTPProbe,
    timeout: float,
) -> tuple[NativeConnectorEndpoint, ...]:
    endpoints: list[NativeConnectorEndpoint] = []
    seen_ports: set[int] = set(int(port) for port in reserved_ports if int(port or 0) > 0)
    process_list = tuple(processes or ())
    for process in process_list:
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
    for process in process_list:
        for port in sorted(_positive_int_set(process.listening_ports)):
            if port in seen_ports:
                continue
            seen_ports.add(port)
            endpoint = _probe_process_listening_debugger_endpoint(
                port,
                process=process,
                http_probe=http_probe,
                timeout=timeout,
            )
            if endpoint is not None:
                endpoints.append(endpoint)
    return tuple(endpoints)


def _ports_from_debugger_urls(debugger_urls: Iterable[str]) -> tuple[int, ...]:
    ports: list[int] = []
    for value in debugger_urls or ():
        base = _normalize_local_debugger_url(value)
        port = _port_from_url(base)
        if port > 0 and port not in ports:
            ports.append(port)
    return tuple(ports)


def _discover_explicit_debugger_endpoints(
    debugger_urls: Iterable[str],
    *,
    matching_processes: Iterable[NativeProcessSnapshot],
    known_ports: set[int],
    http_probe: NativeConnectorHTTPProbe,
    timeout: float,
) -> tuple[NativeConnectorEndpoint, ...]:
    endpoints: list[NativeConnectorEndpoint] = []
    seen_ports = set(int(port) for port in known_ports if int(port or 0) > 0)
    processes = tuple(matching_processes or ())
    for raw_url in debugger_urls or ():
        base = _normalize_local_debugger_url(raw_url)
        if not base:
            continue
        port = _port_from_url(base)
        if port <= 0 or port in seen_ports:
            continue
        seen_ports.add(port)
        process = _process_listening_on_port(processes, port)
        if process is None:
            endpoints.append(
                NativeConnectorEndpoint(
                    debugger_url=base,
                    port=port,
                    source="explicit-devtools-url",
                    error="devtools_endpoint_not_bound_to_agent_process",
                )
            )
            continue
        endpoints.append(
            _probe_debugger_endpoint(
                port,
                process=process,
                source="explicit-devtools-url",
                http_probe=http_probe,
                timeout=timeout,
            )
        )
    return tuple(endpoints)


def _discover_ide_bridge_endpoints(
    bridge_urls: Iterable[str],
    *,
    ide_bridge_probe: Callable[..., object],
    timeout: float,
    workspace_path: str,
    agent_id: str,
) -> tuple[NativeConnectorEndpoint, ...]:
    endpoints: list[NativeConnectorEndpoint] = []
    seen: set[str] = set()
    for raw_url in bridge_urls or ():
        bridge_url = str(raw_url or "").strip().rstrip("/")
        if not bridge_url or bridge_url in seen:
            continue
        seen.add(bridge_url)
        endpoints.append(
            _probe_ide_bridge_endpoint(
                bridge_url,
                ide_bridge_probe=ide_bridge_probe,
                timeout=timeout,
                workspace_path=workspace_path,
                agent_id=agent_id,
            )
        )
    return tuple(endpoints)


def _probe_ide_bridge_endpoint(
    bridge_url: str,
    *,
    ide_bridge_probe: Callable[..., object],
    timeout: float,
    workspace_path: str,
    agent_id: str,
) -> NativeConnectorEndpoint:
    try:
        raw_report = ide_bridge_probe(
            bridge_url,
            workspace_path=workspace_path,
            request_timeout=timeout,
        )
        data = _report_to_dict(raw_report)
        metadata = _dict_value(data.get("metadata"))
        commands = tuple(_string_list(data.get("commands")))
        chat_adapters = tuple(
            dict(item) for item in data.get("chat_adapters", []) if isinstance(item, dict)
        )
        adapter_mapping = _dict_value(data.get("adapter_mapping"))
        preferred_adapter = _preferred_chat_adapter(
            adapter_mapping,
            chat_adapters,
            agent_id=agent_id,
        )
        send_command_id = _send_command_id(data, metadata)
        ok = bool(data.get("ok", False))
        return NativeConnectorEndpoint(
            debugger_url=bridge_url,
            bridge_url=bridge_url,
            port=_port_from_url(bridge_url),
            source="explicit-ide-bridge-url",
            endpoint_type="ide_bridge",
            metadata=metadata,
            commands=commands,
            chat_adapters=chat_adapters,
            adapter_mapping=adapter_mapping,
            preferred_chat_adapter=preferred_adapter,
            send_command_id=send_command_id,
            capability_ok=ok,
            error="" if ok else str(data.get("error", "ide_bridge_capability_failed") or "ide_bridge_capability_failed"),
        )
    except Exception as exc:
        return NativeConnectorEndpoint(
            debugger_url=bridge_url,
            bridge_url=bridge_url,
            port=_port_from_url(bridge_url),
            source="explicit-ide-bridge-url",
            endpoint_type="ide_bridge",
            error=str(exc) or exc.__class__.__name__,
        )


def _discover_agent_native_bridge_endpoints(
    bridge_urls: Iterable[str],
    *,
    agent_native_bridge_probe: Callable[..., object],
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    app_probe: AgentAppUiaProbeReport,
) -> tuple[NativeConnectorEndpoint, ...]:
    endpoints: list[NativeConnectorEndpoint] = []
    seen: set[str] = set()
    for raw_url in bridge_urls or ():
        bridge_url = str(raw_url or "").strip().rstrip("/")
        if not bridge_url or bridge_url in seen:
            continue
        seen.add(bridge_url)
        endpoints.append(
            _probe_agent_native_bridge_endpoint(
                bridge_url,
                agent_native_bridge_probe=agent_native_bridge_probe,
                agent=agent,
                agent_id=agent_id,
                project_name=project_name,
                task_name=task_name,
                app_probe=app_probe,
            )
        )
    return tuple(endpoints)


def _probe_agent_native_bridge_endpoint(
    bridge_url: str,
    *,
    agent_native_bridge_probe: Callable[..., object],
    agent: str,
    agent_id: str,
    project_name: str,
    task_name: str,
    app_probe: AgentAppUiaProbeReport,
) -> NativeConnectorEndpoint:
    request = build_agent_native_bridge_request(
        bridge_url=bridge_url,
        agent=agent,
        agent_id=agent_id,
        project_name=project_name,
        task_name=task_name,
        message="OPENWUKONG_AGENT_NATIVE_BRIDGE_PROBE",
        composed_message=(
            f"Project: {project_name}\n"
            f"Task: {task_name}\n\n"
            "Message:\nOPENWUKONG_AGENT_NATIVE_BRIDGE_PROBE"
        ),
        expected_app_process_names=_agent_process_names(agent_id),
        expected_app_pids=_app_probe_matched_pids(app_probe),
        expected_app_hwnds=_app_probe_matched_hwnds(app_probe),
    )
    try:
        raw_report = agent_native_bridge_probe(request)
        data = _report_to_dict(raw_report)
        capability_report = _dict_value(data.get("capability_report"))
        request_data = _dict_value(data.get("request"))
        metadata = _agent_native_bridge_metadata(
            request_data,
            capability_report,
            agent_id=agent_id,
            project_name=project_name,
            task_name=task_name,
        )
        surface_ok = _agent_native_bridge_surface_ok(metadata)
        app_binding_ok = _agent_native_bridge_app_binding_ok(metadata)
        ok = bool(data.get("ok", False) and surface_ok and app_binding_ok)
        return NativeConnectorEndpoint(
            debugger_url=bridge_url,
            bridge_url=bridge_url,
            port=_port_from_url(bridge_url),
            source="explicit-agent-native-bridge-url",
            endpoint_type="agent_native_bridge",
            metadata=metadata,
            preferred_chat_adapter=str(agent_id or "").strip().lower() if ok else "",
            send_command_id=AGENT_NATIVE_SEND_ACTION if ok else "",
            capability_ok=ok,
            error="" if ok else str(
                data.get("error", "")
                or ("" if surface_ok else "agent_native_bridge_surface_not_ready")
                or ("" if app_binding_ok else "agent_native_bridge_app_binding_not_ready")
                or data.get("decision", "")
                or "agent_native_bridge_capability_failed"
            ),
        )
    except Exception as exc:
        return NativeConnectorEndpoint(
            debugger_url=bridge_url,
            bridge_url=bridge_url,
            port=_port_from_url(bridge_url),
            source="explicit-agent-native-bridge-url",
            endpoint_type="agent_native_bridge",
            error=str(exc) or exc.__class__.__name__,
        )


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


def _probe_process_listening_debugger_endpoint(
    port: int,
    *,
    process: NativeProcessSnapshot,
    http_probe: NativeConnectorHTTPProbe,
    timeout: float,
) -> NativeConnectorEndpoint | None:
    base = f"http://127.0.0.1:{int(port)}"
    try:
        version = http_probe.get_json(f"{base}/json/version", timeout=timeout)
    except Exception:
        return None
    if not isinstance(version, dict) or not _looks_like_devtools_version(version):
        return None
    try:
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
            source="process-listening-port",
            process=process,
            version=version,
            targets=targets,
        )
    except Exception as exc:
        return NativeConnectorEndpoint(
            debugger_url=base,
            port=int(port),
            source="process-listening-port",
            process=process,
            version=version,
            error=str(exc) or exc.__class__.__name__,
        )


def _looks_like_devtools_version(data: dict) -> bool:
    return any(
        key in data
        for key in (
            "Browser",
            "Protocol-Version",
            "V8-Version",
            "webSocketDebuggerUrl",
        )
    )


def _target_from_dict(data: dict) -> NativeConnectorTarget:
    return NativeConnectorTarget(
        target_id=str(data.get("id", "") or data.get("targetId", "") or ""),
        type=str(data.get("type", "") or ""),
        title=str(data.get("title", "") or ""),
        url=str(data.get("url", "") or ""),
        web_socket_debugger_url=str(data.get("webSocketDebuggerUrl", "") or ""),
    )


def _preferred_chat_adapter(
    adapter_mapping: dict,
    chat_adapters: tuple[dict, ...],
    *,
    agent_id: str,
) -> str:
    normalized_agent = lower_text(agent_id)
    if normalized_agent:
        mapped = adapter_mapping.get(normalized_agent)
        if isinstance(mapped, dict) and bool(mapped.get("available", False)):
            command_id = str(mapped.get("commandId", "") or mapped.get("command_id", "") or "").strip()
            if command_id:
                return normalized_agent
        for adapter in chat_adapters:
            adapter_id = str(adapter.get("adapter_id", "") or "").strip()
            if lower_text(adapter_id) != normalized_agent:
                continue
            command_id = str(adapter.get("command_id", "") or adapter.get("commandId", "") or "").strip()
            if command_id and bool(adapter.get("available", False)):
                return adapter_id
        return ""
    for adapter in chat_adapters:
        adapter_id = str(adapter.get("adapter_id", "") or "").strip()
        command_id = str(adapter.get("command_id", "") or adapter.get("commandId", "") or "").strip()
        if adapter_id and command_id and bool(adapter.get("available", False)):
            return adapter_id
    for adapter_id, mapped in adapter_mapping.items():
        if not isinstance(mapped, dict):
            continue
        command_id = str(mapped.get("commandId", "") or mapped.get("command_id", "") or "").strip()
        if adapter_id and command_id and bool(mapped.get("available", False)):
            return str(adapter_id)
    return ""


def _send_command_id(data: dict, metadata: dict) -> str:
    for source in (data, metadata):
        value = str(
            source.get("send_command_id", "")
            or source.get("sendCommandId", "")
            or source.get("send_command", "")
            or source.get("sendCommand", "")
            or ""
        ).strip()
        if value:
            return value
    return ""


def _agent_native_bridge_metadata(
    request_data: dict,
    capability_report: dict,
    *,
    agent_id: str,
    project_name: str,
    task_name: str,
) -> dict:
    target = _dict_value(request_data.get("target"))
    app_binding = _dict_value(
        capability_report.get("app_binding")
        or capability_report.get("desktop_app_binding")
        or capability_report.get("target_app")
        or target.get("app_binding")
    )
    metadata = {
        "agent_id": str(
            request_data.get("agent_id", "")
            or capability_report.get("agent_id", "")
            or agent_id
            or ""
        ).strip().lower(),
        "project_name": str(
            request_data.get("project_name", "")
            or capability_report.get("project_name", "")
            or project_name
            or ""
        ).strip(),
        "task_name": str(
            request_data.get("task_name", "")
            or capability_report.get("task_name", "")
            or task_name
            or ""
        ).strip(),
        "background_safe": bool(capability_report.get("background_safe", True)),
        "surface_kind": str(
            capability_report.get("surface_kind", "")
            or capability_report.get("surface_type", "")
            or capability_report.get("bridge_surface", "")
            or ""
        ).strip(),
        "required_surface_kind": str(request_data.get("required_surface_kind", "") or "desktop_app").strip(),
        "expected_app_process_names": list(request_data.get("expected_app_process_names", []) or []),
        "expected_app_pids": list(request_data.get("expected_app_pids", []) or []),
        "expected_app_hwnds": list(request_data.get("expected_app_hwnds", []) or []),
        "app_binding": app_binding,
        "app_binding_ready": bool(
            request_data.get("app_binding_ready", False)
            or target.get("app_binding_ready", False)
        ),
        "capabilities": list(capability_report.get("capabilities", []) or []),
    }
    for key in ("agents", "projects", "tasks", "workspaces", "sessions"):
        value = capability_report.get(key)
        if isinstance(value, list):
            metadata[key] = [dict(item) for item in value if isinstance(item, dict)]
    return metadata


def _agent_native_bridge_surface_ok(metadata: dict) -> bool:
    return _normalize_surface_kind(metadata.get("surface_kind", "")) == "desktop_app"


def _agent_native_bridge_app_binding_ok(metadata: dict) -> bool:
    binding = metadata.get("app_binding")
    if not isinstance(binding, dict) or not binding:
        return False
    expected_names = {
        _normalize_process_name(name)
        for name in metadata.get("expected_app_process_names", []) or []
        if _normalize_process_name(name)
    }
    actual_name = _binding_process_name(binding)
    if expected_names and actual_name not in expected_names:
        return False
    expected_pids = _positive_int_set(metadata.get("expected_app_pids", []) or [])
    if expected_pids:
        pid = _int_value(binding.get("pid"))
        if pid not in expected_pids:
            return False
    expected_hwnds = _positive_int_set(metadata.get("expected_app_hwnds", []) or [])
    if expected_hwnds:
        hwnd = _int_value(binding.get("hwnd"))
        if hwnd not in expected_hwnds:
            return False
    return bool(
        actual_name
        or _int_value(binding.get("pid"))
        or _int_value(binding.get("hwnd"))
        or str(binding.get("window_title", "") or binding.get("title", "") or "").strip()
    )


def _normalize_surface_kind(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _report_to_dict(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _port_from_url(url: str) -> int:
    match = re.search(r":(\d+)(?:/|$)", str(url or ""))
    if not match:
        return 0
    port = int(match.group(1))
    return port if 0 < port <= 65535 else 0


def _normalize_local_debugger_url(value: object) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except Exception:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = str(parsed.hostname or "").strip().casefold()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    if not port or not (0 < int(port) <= 65535):
        return ""
    path = str(parsed.path or "").strip()
    if path and path != "/":
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _process_listening_on_port(
    processes: Iterable[NativeProcessSnapshot],
    port: int,
) -> NativeProcessSnapshot | None:
    expected = int(port or 0)
    if expected <= 0:
        return None
    for process in processes or ():
        ports = _positive_int_set(process.listening_ports)
        if expected in ports:
            return process
    return None


def _listening_ports_by_pid(psutil_module) -> dict[int, tuple[int, ...]]:
    try:
        connections = psutil_module.net_connections(kind="tcp")
    except Exception:
        return {}
    listen_status = str(getattr(psutil_module, "CONN_LISTEN", "LISTEN") or "LISTEN")
    values: dict[int, list[int]] = {}
    for connection in connections:
        try:
            pid = int(getattr(connection, "pid", 0) or 0)
            status = str(getattr(connection, "status", "") or "")
            if pid <= 0 or status != listen_status:
                continue
            laddr = getattr(connection, "laddr", None)
            port = int(getattr(laddr, "port", 0) or (laddr[1] if laddr else 0) or 0)
            if 0 < port <= 65535:
                values.setdefault(pid, [])
                if port not in values[pid]:
                    values[pid].append(port)
        except Exception:
            continue
    return {pid: tuple(ports) for pid, ports in values.items()}


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
    if normalized == "cursor":
        return ("cursor.exe",)
    return (normalized,)


def _app_probe_matched_pids(app_probe: AgentAppUiaProbeReport) -> tuple[int, ...]:
    values: list[int] = []
    for window in _app_probe_matched_windows(app_probe):
        value = _int_value(window.get("pid"))
        if value > 0 and value not in values:
            values.append(value)
    return tuple(values)


def _app_probe_matched_hwnds(app_probe: AgentAppUiaProbeReport) -> tuple[int, ...]:
    values: list[int] = []
    for window in _app_probe_matched_windows(app_probe):
        value = _int_value(window.get("hwnd"))
        if value > 0 and value not in values:
            values.append(value)
    return tuple(values)


def _app_probe_matched_windows(app_probe: AgentAppUiaProbeReport) -> tuple[dict, ...]:
    data = app_probe.to_dict()
    windows = data.get("matched_windows")
    if not isinstance(windows, list):
        return ()
    return tuple(dict(item) for item in windows if isinstance(item, dict))


def _positive_int_set(values: object) -> set[int]:
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    result: set[int] = set()
    for item in items:
        value = _int_value(item)
        if value > 0:
            result.add(value)
    return result


def _binding_process_name(binding: dict) -> str:
    for key in ("process_name", "processName", "executable_name", "executableName"):
        value = _normalize_process_name(binding.get(key, ""))
        if value:
            return value
    for key in ("executable_path", "executablePath", "path"):
        value = _normalize_process_name(binding.get(key, ""))
        if value:
            return value
    return ""


def _normalize_process_name(value: object) -> str:
    text = str(value or "").strip().casefold().replace("\\", "/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


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
