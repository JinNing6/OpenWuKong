# -*- coding: utf-8 -*-
"""Read-only Session Registry report over live or recorded observations."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Optional

from openwukong.control.command_process_broker import (
    CommandProcessBroker,
    CommandProcessBrokerConfig,
)
from openwukong.control.session_discovery import SessionDiscovery, SessionDiscoveryOptions
from openwukong.control.session_ownership import (
    SessionOwnershipIndex,
    build_ownership_index,
)
from openwukong.control.session_registry import (
    SessionRegistry,
    SessionRegistrySnapshot,
)
from openwukong.evaluation.shadow import FastDesktopStateObserver


_DEFAULT_PROCESS_BROKER_STORAGE_RELATIVE_PATHS = (
    Path("logs/runtime/supervisor-command-processes.json"),
    Path("logs/runtime/processes.json"),
)


class StaticRegistryObserver:
    def __init__(self, states: Iterable[object]):
        self._states = tuple(states)

    def snapshot(self) -> tuple[object, ...]:
        return self._states


@dataclasses.dataclass(frozen=True)
class SessionRegistryReport:
    observed_states: tuple[object, ...]
    registry: SessionRegistrySnapshot
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "session-registry-report"

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
    def observed_state_count(self) -> int:
        return len(self.observed_states)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "observed_state_count": self.observed_state_count,
            "observed_states": [_state_to_dict(state) for state in self.observed_states],
            "registry": self.registry.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_session_registry_report(
    *,
    observer: Optional[object] = None,
    session_discovery: Optional[object] = None,
    ownership_index: Optional[SessionOwnershipIndex] = None,
    process_broker_snapshots: Optional[Iterable[dict]] = None,
    process_broker_storage_paths: Optional[Iterable[str | Path]] = None,
    process_broker_workspace_roots: Optional[Iterable[str | Path]] = None,
) -> SessionRegistryReport:
    started = time.perf_counter()
    active_observer = observer or FastDesktopStateObserver()
    states = tuple(active_observer.snapshot())
    registry = SessionRegistry(ownership_index=ownership_index)
    for state in states:
        target = session_discovery.enrich(state) if session_discovery is not None else state
        registry.register(target)
    storage_snapshots = _snapshot_process_broker_storage_paths(
        tuple(process_broker_storage_paths or ()),
        workspace_roots=tuple(process_broker_workspace_roots or ()),
    )
    for broker_snapshot in tuple(process_broker_snapshots or ()) + storage_snapshots:
        registry.register_process_broker_snapshot(broker_snapshot)
    return SessionRegistryReport(
        observed_states=states,
        registry=registry.snapshot(),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def load_registry_states(path: str | Path) -> tuple[object, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw_states = data
    elif isinstance(data, dict) and isinstance(data.get("states"), list):
        raw_states = data["states"]
    elif isinstance(data, dict) and isinstance(data.get("observed_states"), list):
        raw_states = data["observed_states"]
    elif isinstance(data, dict) and isinstance(data.get("windows"), list):
        raw_states = data["windows"]
    else:
        raw_states = []
    return tuple(_state_from_dict(item) for item in raw_states if isinstance(item, dict))


def main(
    argv: Optional[list[str]] = None,
    *,
    observer: Optional[object] = None,
    session_discovery: Optional[object] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only unified Session Registry report."
    )
    parser.add_argument(
        "--states",
        default="",
        help="Optional recorded JSON states/windows file. If omitted, performs a read-only fast desktop scan.",
    )
    parser.add_argument("--discover-sessions", action="store_true")
    parser.add_argument(
        "--broker-only",
        action="store_true",
        help="Skip desktop/window observation and report only broker-managed background sessions.",
    )
    parser.add_argument("--browser-debug-port", action="append", type=int, default=None)
    parser.add_argument("--ide-bridge-url", action="append", default=None)
    parser.add_argument("--workspace-root", action="append", default=None)
    parser.add_argument("--discovery-timeout", type=float, default=0.2)
    parser.add_argument("--readiness-manifest", action="append", default=None)
    parser.add_argument("--readiness-manifest-dir", action="append", default=None)
    parser.add_argument(
        "--process-broker-snapshot",
        action="append",
        default=None,
        help="Optional command-process-broker snapshot JSON file to merge into the unified registry.",
    )
    parser.add_argument(
        "--process-broker-storage",
        action="append",
        default=None,
        help="Optional command-process-broker persistent storage JSON file to snapshot read-only and merge into the unified registry.",
    )
    parser.add_argument(
        "--discover-process-brokers",
        action="store_true",
        help="Discover default command-process-broker storage files under workspace roots and the current directory.",
    )
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    active_observer = observer
    if args.broker_only:
        active_observer = StaticRegistryObserver(())
    elif active_observer is None and args.states:
        active_observer = StaticRegistryObserver(load_registry_states(args.states))

    active_discovery = session_discovery
    if active_discovery is None and args.discover_sessions:
        active_discovery = SessionDiscovery(
            SessionDiscoveryOptions(
                browser_debug_ports=tuple(args.browser_debug_port or SessionDiscoveryOptions().browser_debug_ports),
                ide_bridge_urls=tuple(args.ide_bridge_url or SessionDiscoveryOptions().ide_bridge_urls),
                workspace_roots=tuple(args.workspace_root or ()),
                request_timeout=max(0.05, float(args.discovery_timeout or 0.2)),
            )
        )
    ownership_paths = _manifest_paths_from_args(
        tuple(args.readiness_manifest or ()),
        tuple(args.readiness_manifest_dir or ()),
    )
    ownership_index = build_ownership_index(ownership_paths)
    process_broker_snapshots = tuple(
        _load_process_broker_snapshot(path)
        for path in args.process_broker_snapshot or ()
    )
    process_broker_storage_paths = _process_broker_storage_paths_from_args(
        explicit_paths=tuple(args.process_broker_storage or ()),
        discover=bool(args.discover_process_brokers),
        workspace_roots=tuple(args.workspace_root or ()),
    )

    report = run_session_registry_report(
        observer=active_observer,
        session_discovery=active_discovery,
        ownership_index=ownership_index,
        process_broker_snapshots=process_broker_snapshots,
        process_broker_storage_paths=process_broker_storage_paths,
        process_broker_workspace_roots=tuple(args.workspace_root or ()),
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
        registry = data["registry"]
        _write_stdout(
            "Session Registry report: "
            f"observed={data['observed_state_count']} "
            f"sessions={registry['session_count']} "
            f"families={registry['app_family_counts']} "
            f"routes={registry['preferred_route_counts']}"
        )
    return 0


def _state_from_dict(data: dict) -> object:
    return SimpleNamespace(
        timestamp=float(data.get("timestamp", 0.0) or 0.0),
        pid=int(data.get("pid", 0) or 0),
        process_name=str(data.get("process_name", "") or ""),
        project_name=str(data.get("project_name", "") or ""),
        window_title=str(data.get("window_title", "") or ""),
        class_name=str(data.get("class_name", "") or ""),
        workspace_path=str(data.get("workspace_path", "") or ""),
        resource_url=str(data.get("resource_url", "") or ""),
        debugger_url=str(data.get("debugger_url", "") or ""),
        ide_bridge_url=str(data.get("ide_bridge_url", "") or ""),
        element_count=int(data.get("element_count", data.get("ai_element_count", 0)) or 0),
        input_candidate_count=int(data.get("input_candidate_count", 0) or 0),
        semantic_input_count=int(data.get("semantic_input_count", 0) or 0),
        semantic_action_count=int(data.get("semantic_action_count", 0) or 0),
        text_readable_count=int(data.get("text_readable_count", 0) or 0),
        stable_identifier_count=int(data.get("stable_identifier_count", 0) or 0),
        risks=tuple(data.get("risks", ()) or ()),
    )


def _manifest_paths_from_args(paths: tuple[str, ...], dirs: tuple[str, ...]) -> tuple[Path, ...]:
    items: list[Path] = []
    for path in paths:
        candidate = Path(str(path or ""))
        if candidate.is_file():
            items.append(candidate)
    for directory in dirs:
        root = Path(str(directory or ""))
        if root.is_dir():
            items.extend(sorted(root.glob("*.json")))
    seen: set[str] = set()
    unique: list[Path] = []
    for path in items:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def _load_process_broker_snapshot(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    return {}


def _process_broker_storage_paths_from_args(
    *,
    explicit_paths: tuple[str, ...],
    discover: bool,
    workspace_roots: tuple[str, ...],
) -> tuple[Path, ...]:
    candidates = [
        Path(str(path))
        for path in explicit_paths
        if str(path or "").strip()
    ]
    if discover:
        candidates.extend(
            discover_process_broker_storage_paths(
                workspace_roots=workspace_roots,
                include_cwd=True,
            )
        )
    return _unique_paths(candidates)


def discover_process_broker_storage_paths(
    *,
    workspace_roots: Iterable[str | Path] = (),
    include_cwd: bool = True,
) -> tuple[Path, ...]:
    roots = [
        Path(str(root))
        for root in workspace_roots
        if str(root or "").strip()
    ]
    if include_cwd:
        roots.append(Path.cwd())
    candidates: list[Path] = []
    for root in roots:
        for relative_path in _DEFAULT_PROCESS_BROKER_STORAGE_RELATIVE_PATHS:
            candidate = root / relative_path
            if candidate.is_file():
                candidates.append(candidate)
    return _unique_paths(candidates)


def _snapshot_process_broker_storage_paths(
    paths: tuple[str | Path, ...],
    *,
    workspace_roots: tuple[str | Path, ...] = (),
) -> tuple[dict, ...]:
    snapshots: list[dict] = []
    for path in _unique_paths(Path(str(item)) for item in paths if str(item or "").strip()):
        snapshot = _snapshot_process_broker_storage(path, workspace_roots=workspace_roots)
        if snapshot:
            snapshots.append(snapshot)
    return tuple(snapshots)


def _snapshot_process_broker_storage(
    path: Path,
    *,
    workspace_roots: tuple[str | Path, ...] = (),
) -> dict:
    broker = CommandProcessBroker(
        CommandProcessBrokerConfig(
            workspace_root=_workspace_root_for_storage_path(path, workspace_roots),
            storage_path=str(path),
        )
    )
    return broker.snapshot()


def _workspace_root_for_storage_path(
    path: Path,
    workspace_roots: tuple[str | Path, ...],
) -> str:
    for root in workspace_roots:
        root_text = str(root or "").strip()
        if not root_text:
            continue
        try:
            resolved_path = path.resolve()
            resolved_root = Path(root_text).resolve()
        except OSError:
            continue
        try:
            if resolved_path.is_relative_to(resolved_root):
                return root_text
        except ValueError:
            continue
    return ""


def _unique_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def _state_to_dict(state: object) -> dict:
    return {
        "timestamp": _value(state, "timestamp", 0.0),
        "pid": int(_value(state, "pid", 0) or 0),
        "process_name": str(_value(state, "process_name", "") or ""),
        "project_name": str(_value(state, "project_name", "") or ""),
        "window_title": str(_value(state, "window_title", "") or ""),
        "class_name": str(_value(state, "class_name", "") or ""),
        "workspace_path": str(_value(state, "workspace_path", "") or ""),
        "resource_url": str(_value(state, "resource_url", "") or ""),
        "debugger_url": str(_value(state, "debugger_url", "") or ""),
        "ide_bridge_url": str(_value(state, "ide_bridge_url", "") or ""),
        "element_count": int(_value(state, "element_count", _value(state, "ai_element_count", 0)) or 0),
        "input_candidate_count": int(_value(state, "input_candidate_count", 0) or 0),
        "semantic_input_count": int(_value(state, "semantic_input_count", 0) or 0),
        "semantic_action_count": int(_value(state, "semantic_action_count", 0) or 0),
        "text_readable_count": int(_value(state, "text_readable_count", 0) or 0),
        "stable_identifier_count": int(_value(state, "stable_identifier_count", 0) or 0),
    }


def _value(obj: object, name: str, default):
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
