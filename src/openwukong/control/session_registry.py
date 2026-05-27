# -*- coding: utf-8 -*-
"""Unified read-only registry for controllable application sessions."""

from __future__ import annotations

import dataclasses
import re
from collections import Counter
from pathlib import PurePath, PureWindowsPath

from openwukong.connectors import ConnectorTarget
from openwukong.connectors.route_policy import (
    ControlRoutePlan,
    ControlRouteStep,
    build_control_route_plan,
)
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex


@dataclasses.dataclass(frozen=True)
class SessionCapability:
    capability_id: str
    route_id: str
    channel: str
    action_ids: tuple[str, ...] = ()
    locator_source: str = ""
    background_safe: bool = False
    confidence_floor: int = 0
    evidence: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "route_id": self.route_id,
            "channel": self.channel,
            "action_ids": list(self.action_ids),
            "locator_source": self.locator_source,
            "background_safe": self.background_safe,
            "confidence_floor": self.confidence_floor,
            "evidence": [dict(item) for item in self.evidence],
        }


@dataclasses.dataclass(frozen=True)
class ControlSession:
    session_id: str
    target: ConnectorTarget
    app_family: str
    route_plan: ControlRoutePlan
    capabilities: tuple[SessionCapability, ...] = ()
    session_discovery: dict | None = None
    ownership: SessionOwnership = dataclasses.field(default_factory=SessionOwnership.unowned)

    def __getattr__(self, name: str):
        return getattr(self.target, name)

    @property
    def preferred_route(self) -> str:
        return self.route_plan.primary_route.route_id

    @property
    def background_safe(self) -> bool:
        return any(capability.background_safe for capability in self.capabilities)

    def capability_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.capability_id for item in self.capabilities))

    def action_ids(self) -> tuple[str, ...]:
        actions: list[str] = []
        for capability in self.capabilities:
            actions.extend(capability.action_ids)
        return tuple(dict.fromkeys(actions))

    def to_connector_target(self) -> ConnectorTarget:
        return dataclasses.replace(self.target, session_id=self.session_id)

    def session_discovery_dict(self) -> dict:
        return self.session_discovery or {
            "discovered_fields": {},
            "evidence": [],
        }

    def merge(self, other: "ControlSession") -> "ControlSession":
        if self.session_id != other.session_id:
            raise ValueError("cannot_merge_different_sessions")
        target = _merge_targets(self.target, other.target)
        capabilities = _merge_capabilities(self.capabilities, other.capabilities)
        discovery = _merge_discovery(self.session_discovery, other.session_discovery)
        ownership = other.ownership if other.ownership.owned else self.ownership
        route_plan = other.route_plan if _target_richness(other.target) >= _target_richness(self.target) else self.route_plan
        return ControlSession(
            session_id=self.session_id,
            target=target,
            app_family=other.app_family or self.app_family,
            route_plan=route_plan,
            capabilities=capabilities,
            session_discovery=discovery,
            ownership=ownership,
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "app_family": self.app_family,
            "preferred_route": self.preferred_route,
            "background_safe": self.background_safe,
            "capability_ids": list(self.capability_ids()),
            "action_ids": list(self.action_ids()),
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "session_discovery": self.session_discovery_dict(),
            "ownership": self.ownership.to_dict(),
            "target": _target_to_dict(self.to_connector_target()),
            "route_plan": self.route_plan.to_dict(),
        }


@dataclasses.dataclass(frozen=True)
class SessionRegistrySnapshot:
    sessions: tuple[ControlSession, ...]

    @property
    def mode(self) -> str:
        return "session-registry-snapshot"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def app_family_counts(self) -> dict:
        return dict(sorted(Counter(session.app_family for session in self.sessions).items()))

    def preferred_route_counts(self) -> dict:
        return dict(sorted(Counter(session.preferred_route for session in self.sessions).items()))

    def ownership_counts(self) -> dict:
        owned = sum(1 for session in self.sessions if session.ownership.owned)
        return {
            "owned": owned,
            "unowned": len(self.sessions) - owned,
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "session_count": len(self.sessions),
            "app_family_counts": self.app_family_counts(),
            "preferred_route_counts": self.preferred_route_counts(),
            "ownership_counts": self.ownership_counts(),
            "sessions": [session.to_dict() for session in self.sessions],
        }


class SessionRegistry:
    """Read-only in-memory registry of discovered control sessions."""

    def __init__(self, *, ownership_index: SessionOwnershipIndex | None = None):
        self._sessions: dict[str, ControlSession] = {}
        self._ownership_index = ownership_index or SessionOwnershipIndex()

    def register(self, target_or_window: object) -> ControlSession:
        target = _connector_target_from(target_or_window)
        route_plan = build_control_route_plan(target_or_window)
        session_id = _session_id_for(target, route_plan.app_family)
        discovery = _session_discovery_dict(target_or_window)
        session = ControlSession(
            session_id=session_id,
            target=dataclasses.replace(target, session_id=session_id),
            app_family=route_plan.app_family,
            route_plan=route_plan,
            capabilities=_capabilities_for(target, route_plan, discovery),
            session_discovery=discovery,
            ownership=self._ownership_index.match(target),
        )
        existing = self._sessions.get(session_id)
        if existing is not None:
            session = existing.merge(session)
        self._sessions[session_id] = session
        return session

    def register_process_broker_snapshot(self, broker_snapshot: dict) -> tuple[ControlSession, ...]:
        sessions: list[ControlSession] = []
        if not isinstance(broker_snapshot, dict):
            return ()
        for process in broker_snapshot.get("processes", ()) or ():
            session = _session_from_broker_process(process, broker_snapshot)
            if session is None:
                continue
            if not session.ownership.owned:
                matched_ownership = self._ownership_index.match(session.target)
                if matched_ownership.owned:
                    session = dataclasses.replace(session, ownership=matched_ownership)
            existing = self._sessions.get(session.session_id)
            if existing is not None:
                session = existing.merge(session)
            self._sessions[session.session_id] = session
            sessions.append(session)
        return tuple(sessions)

    def snapshot(self) -> SessionRegistrySnapshot:
        sessions = tuple(
            self._sessions[key]
            for key in sorted(self._sessions)
        )
        return SessionRegistrySnapshot(sessions=sessions)


def build_session_registry_snapshot(
    targets_or_windows,
    *,
    process_broker_snapshots=(),
) -> SessionRegistrySnapshot:
    registry = SessionRegistry()
    for target in targets_or_windows:
        registry.register(target)
    for broker_snapshot in process_broker_snapshots or ():
        registry.register_process_broker_snapshot(broker_snapshot)
    return registry.snapshot()


def _capabilities_for(
    target: ConnectorTarget,
    route_plan: ControlRoutePlan,
    discovery: dict | None,
) -> tuple[SessionCapability, ...]:
    route = route_plan.primary_route
    evidence = tuple((discovery or {}).get("evidence", ()) or ())
    capabilities: list[SessionCapability] = []

    if route.route_id == "browser-devtools-or-extension":
        if target.debugger_url:
            capabilities.append(
                _capability(
                    "browser_devtools",
                    route,
                    ("navigate_url", "read_page", "set_input", "submit", "extract_results"),
                    True,
                    evidence,
                )
            )
        capabilities.append(
            _capability("dom_locator", route, ("read_page", "set_input", "click", "submit"), True)
        )
    elif route.route_id == "ide-extension-connector":
        if target.ide_bridge_url:
            capabilities.append(
                _capability(
                    "ide_bridge",
                    route,
                    ("read_state", "edit_file", "send_message", "run_command"),
                    True,
                    evidence,
                )
            )
        else:
            capabilities.append(_capability("ide_bridge_required", route, (), True))
    elif route.route_id == "terminal-native-session":
        capabilities.append(
            _capability(
                "terminal_native_session",
                route,
                ("run_command", "read_stdout", "send_stdin", "cleanup"),
                True,
                evidence,
            )
        )
    elif route.route_id == "git-cli":
        capabilities.append(
            _capability(
                "git_cli",
                route,
                ("git_command", "read_status", "read_diff"),
                True,
                evidence,
            )
        )
    elif route.route_id == "office-object-model-or-addin":
        capabilities.append(
            _capability(
                "office_object_model",
                route,
                ("read_document", "edit_document", "save_document"),
                True,
                evidence,
            )
        )
    elif route.route_id == "uia-semantic":
        capabilities.append(
            _capability(
                "uia_semantic",
                route,
                ("read_state", "set_text", "click", "select", "toggle"),
                False,
                evidence,
            )
        )
    elif route.route_id in {"uia-structural", "uia-structural-observe"}:
        capabilities.append(
            _capability(
                "uia_structural",
                route,
                ("read_state", "locate_control"),
                False,
                evidence,
            )
        )
    else:
        capabilities.append(
            _capability("observe_only", route, ("read_state",), False, evidence)
        )
    return tuple(capabilities)


def _capability(
    capability_id: str,
    route,
    action_ids: tuple[str, ...],
    background_safe: bool,
    evidence: tuple[dict, ...] = (),
) -> SessionCapability:
    return SessionCapability(
        capability_id=capability_id,
        route_id=route.route_id,
        channel=route.channel,
        action_ids=action_ids,
        locator_source=route.locator_source,
        background_safe=background_safe,
        confidence_floor=route.confidence_floor,
        evidence=tuple(dict(item) for item in evidence),
    )


def _connector_target_from(target_or_window: object) -> ConnectorTarget:
    if isinstance(target_or_window, ConnectorTarget):
        return target_or_window
    to_connector_target = getattr(target_or_window, "to_connector_target", None)
    if callable(to_connector_target):
        target = to_connector_target()
        if isinstance(target, ConnectorTarget):
            return target
    return ConnectorTarget(
        pid=int(_value(target_or_window, "pid", 0) or 0),
        process_name=str(_value(target_or_window, "process_name", "") or ""),
        window_title=str(_value(target_or_window, "window_title", "") or ""),
        project_name=str(_value(target_or_window, "project_name", "") or ""),
        workspace_hint=str(_value(target_or_window, "workspace_hint", "") or ""),
        workspace_path=str(_value(target_or_window, "workspace_path", "") or ""),
        resource_url=str(_value(target_or_window, "resource_url", "") or ""),
        debugger_url=str(_value(target_or_window, "debugger_url", "") or ""),
        ide_bridge_url=str(_value(target_or_window, "ide_bridge_url", "") or ""),
    )


def _session_from_broker_process(process: object, broker_snapshot: dict) -> ControlSession | None:
    if not isinstance(process, dict):
        return None
    process_id = str(process.get("process_id", "") or "").strip()
    if not process_id:
        return None
    argv = tuple(str(item) for item in process.get("argv", ()) or () if str(item).strip())
    process_name = _process_name_from_argv(argv) or "managed-process"
    pid = _safe_int(process.get("pid"))
    cwd = str(process.get("cwd", "") or "").strip()
    broker = broker_snapshot.get("broker", {}) if isinstance(broker_snapshot, dict) else {}
    if not isinstance(broker, dict):
        broker = {}
    workspace_path = cwd or str(broker.get("workspace_root", "") or "").strip()
    session_id = f"command-process:{process_id}"
    route_plan = _process_broker_route_plan(process_name, process_id)
    target = ConnectorTarget(
        session_id=session_id,
        pid=pid,
        process_name=process_name,
        window_title=f"Managed process {process_id}",
        project_name=_workspace_name(workspace_path),
        workspace_hint=workspace_path,
        workspace_path=workspace_path,
    )
    evidence = _broker_process_evidence(process, broker)
    capability = SessionCapability(
        capability_id="command_process_broker",
        route_id="command-process-broker",
        channel="native-process-broker",
        action_ids=("read_process_snapshot", "stop_process", "stop_all_processes"),
        locator_source="broker-process-id",
        background_safe=True,
        confidence_floor=99,
        evidence=(evidence,),
    )
    discovery = {
        "discovered_fields": {
            "process_id": process_id,
            "pid": str(pid) if pid else "",
            "cwd": workspace_path,
            "broker_storage_path": str(broker.get("storage_path", "") or ""),
            "broker_profile_id": str(broker.get("profile_id", "") or ""),
        },
        "evidence": [evidence],
    }
    return ControlSession(
        session_id=session_id,
        target=target,
        app_family="managed-process",
        route_plan=route_plan,
        capabilities=(capability,),
        session_discovery=discovery,
        ownership=_ownership_from_dict(process.get("ownership")),
    )


def _process_broker_route_plan(process_name: str, process_id: str) -> ControlRoutePlan:
    return ControlRoutePlan(
        process_name=process_name,
        window_title=f"Managed process {process_id}",
        app_family="managed-process",
        capability_level="broker_managed",
        capability_score=100,
        primary_route=ControlRouteStep(
            route_id="command-process-broker",
            channel="native-process-broker",
            locator_source="broker-process-id",
            action_primitives=(
                "read_process_snapshot",
                "stop_process",
                "stop_all_processes",
            ),
            confidence_floor=99,
            role="primary",
            reason="A broker-managed background process is addressable by process_id without foreground focus.",
        ),
        fallback_routes=(),
        control_decision="prefer_deterministic_connector",
        missing_capabilities=(),
        risks=(),
    )


def _broker_process_evidence(process: dict, broker: dict) -> dict:
    return {
        "kind": "command_process_broker",
        "process_id": str(process.get("process_id", "") or ""),
        "pid": _safe_int(process.get("pid")),
        "argv": [str(item) for item in process.get("argv", ()) or () if str(item).strip()],
        "cwd": str(process.get("cwd", "") or ""),
        "reason": str(process.get("reason", "") or ""),
        "effects": [str(item) for item in process.get("effects", ()) or () if str(item).strip()],
        "running": bool(process.get("running", False)),
        "restored": bool(process.get("restored", False)),
        "started_at": process.get("started_at"),
        "broker": {
            "workspace_root": str(broker.get("workspace_root", "") or ""),
            "storage_path": str(broker.get("storage_path", "") or ""),
            "profile_id": str(broker.get("profile_id", "") or ""),
        },
    }


def _ownership_from_dict(value: object) -> SessionOwnership:
    if isinstance(value, SessionOwnership):
        return value
    if not isinstance(value, dict):
        return SessionOwnership.unowned()
    return SessionOwnership(
        owned=bool(value.get("owned", False)),
        ownership_source=str(value.get("ownership_source", "") or ""),
        manifest_path=str(value.get("manifest_path", "") or ""),
        route_id=str(value.get("route_id", "") or ""),
        connector_id=str(value.get("connector_id", "") or ""),
        action_id=str(value.get("action_id", "") or ""),
        pid=_safe_int(value.get("pid")),
        endpoint=str(value.get("endpoint", "") or ""),
        profile_path=str(value.get("profile_path", "") or ""),
        extensions_path=str(value.get("extensions_path", "") or ""),
        workspace_root=str(value.get("workspace_root", "") or ""),
        cleanup_ready=bool(value.get("cleanup_ready", False)),
    )


def _process_name_from_argv(argv: tuple[str, ...]) -> str:
    if not argv:
        return ""
    first = str(argv[0] or "").strip()
    if not first:
        return ""
    return PureWindowsPath(first).name or PurePath(first).name or first


def _workspace_name(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return PureWindowsPath(text).name or PurePath(text).name or text


def _session_discovery_dict(target_or_window: object) -> dict | None:
    getter = getattr(target_or_window, "session_discovery_dict", None)
    if callable(getter):
        data = getter()
        if isinstance(data, dict):
            return data
    return None


def _session_id_for(target: ConnectorTarget, app_family: str) -> str:
    if target.session_id:
        return target.session_id
    parts = [
        app_family,
        target.process_name,
        target.workspace_path,
        target.resource_url,
        target.window_title,
        str(target.pid or ""),
    ]
    identity = next((part for part in parts[2:] if str(part or "").strip()), target.process_name)
    return f"{_slug(app_family)}:{_slug(target.process_name or 'unknown')}:{_slug(identity)}"


def _merge_targets(first: ConnectorTarget, second: ConnectorTarget) -> ConnectorTarget:
    values = {}
    for field in dataclasses.fields(ConnectorTarget):
        first_value = getattr(first, field.name)
        second_value = getattr(second, field.name)
        values[field.name] = second_value or first_value
    values["session_id"] = first.session_id or second.session_id
    return ConnectorTarget(**values)


def _merge_capabilities(
    first: tuple[SessionCapability, ...],
    second: tuple[SessionCapability, ...],
) -> tuple[SessionCapability, ...]:
    items: dict[str, SessionCapability] = {item.capability_id: item for item in first}
    for capability in second:
        existing = items.get(capability.capability_id)
        if existing is None:
            items[capability.capability_id] = capability
            continue
        actions = tuple(dict.fromkeys(existing.action_ids + capability.action_ids))
        evidence = _dedupe_evidence(tuple(existing.evidence) + tuple(capability.evidence))
        items[capability.capability_id] = dataclasses.replace(
            existing,
            action_ids=actions,
            background_safe=existing.background_safe or capability.background_safe,
            confidence_floor=max(existing.confidence_floor, capability.confidence_floor),
            evidence=evidence,
        )
    return tuple(items[key] for key in sorted(items))


def _dedupe_evidence(items: tuple[dict, ...]) -> tuple[dict, ...]:
    deduped: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        if copied not in deduped:
            deduped.append(copied)
    return tuple(deduped)


def _merge_discovery(first: dict | None, second: dict | None) -> dict:
    fields = {}
    evidence: list[dict] = []
    for data in (first, second):
        if not isinstance(data, dict):
            continue
        discovered = data.get("discovered_fields", {})
        if isinstance(discovered, dict):
            fields.update({str(key): str(value) for key, value in discovered.items() if value})
        for item in data.get("evidence", ()) or ():
            if isinstance(item, dict) and item not in evidence:
                evidence.append(dict(item))
    return {
        "discovered_fields": fields,
        "evidence": evidence,
    }


def _target_richness(target: ConnectorTarget) -> int:
    return sum(1 for field in dataclasses.fields(ConnectorTarget) if getattr(target, field.name))


def _target_to_dict(target: ConnectorTarget) -> dict:
    return {
        "workspace_id": target.workspace_id,
        "session_id": target.session_id,
        "pid": target.pid,
        "process_name": target.process_name,
        "window_title": target.window_title,
        "project_name": target.project_name,
        "workspace_hint": target.workspace_hint,
        "workspace_path": target.workspace_path,
        "resource_url": target.resource_url,
        "debugger_url": target.debugger_url,
        "ide_bridge_url": target.ide_bridge_url,
    }


def _value(obj: object, name: str, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"
