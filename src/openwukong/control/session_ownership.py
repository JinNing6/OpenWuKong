# -*- coding: utf-8 -*-
"""Read-only ownership labels for managed connector sessions."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class SessionOwnership:
    owned: bool = False
    ownership_source: str = ""
    manifest_path: str = ""
    route_id: str = ""
    connector_id: str = ""
    action_id: str = ""
    pid: int = 0
    endpoint: str = ""
    profile_path: str = ""
    extensions_path: str = ""
    workspace_root: str = ""
    cleanup_ready: bool = False

    def to_dict(self) -> dict:
        return {
            "owned": self.owned,
            "ownership_source": self.ownership_source,
            "manifest_path": self.manifest_path,
            "route_id": self.route_id,
            "connector_id": self.connector_id,
            "action_id": self.action_id,
            "pid": self.pid,
            "endpoint": self.endpoint,
            "profile_path": self.profile_path,
            "extensions_path": self.extensions_path,
            "workspace_root": self.workspace_root,
            "cleanup_ready": self.cleanup_ready,
        }

    @classmethod
    def unowned(cls) -> "SessionOwnership":
        return cls()


class SessionOwnershipIndex:
    def __init__(self, ownerships=()):
        self._ownerships = tuple(
            item for item in ownerships if isinstance(item, SessionOwnership) and item.owned
        )

    def match(self, target_or_window: object) -> SessionOwnership:
        target = _connector_target_from(target_or_window)
        for ownership in self._ownerships:
            if _matches_ownership(ownership, target):
                return ownership
        return SessionOwnership.unowned()

    def to_dict(self) -> dict:
        return {
            "mode": "session-ownership-index",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": 0,
            "ownership_count": len(self._ownerships),
            "ownerships": [ownership.to_dict() for ownership in self._ownerships],
        }


def build_ownership_index(manifest_paths) -> SessionOwnershipIndex:
    ownerships: list[SessionOwnership] = []
    for path in manifest_paths or ():
        ownerships.extend(load_readiness_manifest_ownership(path))
    return SessionOwnershipIndex(tuple(ownerships))


def load_readiness_manifest_ownership(manifest_path: str | Path) -> tuple[SessionOwnership, ...]:
    path = Path(manifest_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    if (
        not isinstance(data, dict)
        or data.get("mode") != "session-readiness-execution"
        or data.get("safety_mode") != "isolated_helper_launch"
    ):
        return ()

    ownerships: list[SessionOwnership] = []
    for launch in data.get("launches", ()) or ():
        if isinstance(launch, dict):
            ownership = _ownership_from_record(launch, str(path), cleanup_ready=True)
            if ownership.owned:
                ownerships.append(ownership)
    for result in data.get("results", ()) or ():
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") != "workspace_bound":
            continue
        ownership = _ownership_from_record(result, str(path), cleanup_ready=False)
        if ownership.owned:
            ownerships.append(ownership)
    return tuple(ownerships)


def _ownership_from_record(record: dict, manifest_path: str, *, cleanup_ready: bool) -> SessionOwnership:
    route_id = str(record.get("route_id", "") or "")
    connector_id = str(record.get("connector_id", "") or "")
    action_id = str(record.get("action_id", "") or "")
    endpoint = str(record.get("readiness_url", "") or "")
    workspace_root = _normalize_path(str(record.get("workspace_root", "") or ""))
    argv = tuple(str(item) for item in record.get("argv", ()) or () if str(item).strip())
    profile_path = _argv_value(argv, "--user-data-dir")
    extensions_path = _argv_value(argv, "--extensions-dir")
    if not route_id or not connector_id:
        return SessionOwnership.unowned()
    if not endpoint and not workspace_root:
        return SessionOwnership.unowned()
    return SessionOwnership(
        owned=True,
        ownership_source="session_readiness_manifest",
        manifest_path=manifest_path,
        route_id=route_id,
        connector_id=connector_id,
        action_id=action_id,
        pid=_safe_int(record.get("pid")),
        endpoint=endpoint,
        profile_path=profile_path,
        extensions_path=extensions_path,
        workspace_root=workspace_root,
        cleanup_ready=bool(cleanup_ready and action_id.startswith("launch_")),
    )


def _matches_ownership(ownership: SessionOwnership, target: object) -> bool:
    if ownership.route_id == "browser-devtools-or-extension":
        return _same_url(target.debugger_url, ownership.endpoint)
    if ownership.route_id == "ide-extension-connector":
        if not _same_url(target.ide_bridge_url, ownership.endpoint):
            return False
        if ownership.workspace_root:
            return _same_path(target.workspace_path, ownership.workspace_root)
        return True
    if ownership.route_id in {"terminal-native-session", "git-cli"}:
        return bool(ownership.workspace_root and _same_path(target.workspace_path, ownership.workspace_root))
    if ownership.endpoint:
        return _same_url(target.debugger_url, ownership.endpoint) or _same_url(target.ide_bridge_url, ownership.endpoint)
    if ownership.workspace_root:
        return _same_path(target.workspace_path, ownership.workspace_root)
    return False


def _connector_target_from(target_or_window: object) -> ConnectorTarget:
    ConnectorTarget = _connector_target_class()
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


def _connector_target_class():
    from openwukong.connectors.base import ConnectorTarget

    return ConnectorTarget


def _argv_value(argv: tuple[str, ...], prefix: str) -> str:
    prefix_text = f"{prefix}="
    for item in argv:
        if item.startswith(prefix_text):
            return _normalize_path(item.split("=", 1)[1])
    return ""


def _same_url(first: str, second: str) -> bool:
    return _normalize_url(first) == _normalize_url(second) and bool(_normalize_url(first))


def _normalize_url(value: str) -> str:
    return str(value or "").strip().rstrip("/").lower()


def _same_path(first: str, second: str) -> bool:
    return _normalize_path(first) == _normalize_path(second) and bool(_normalize_path(first))


def _normalize_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("\\", "/").rstrip("/")


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _value(obj: object, name: str, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value
