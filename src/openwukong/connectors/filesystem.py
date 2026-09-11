# -*- coding: utf-8 -*-
"""Workspace-bound filesystem operations for the File Explorer surface."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)


class FileSystemConnector(SessionConnector):
    connector_id = "filesystem"
    route_id = "filesystem-native"
    route_ids = ("filesystem-native",)
    display_name = "Workspace File Operations"

    _READ_ACTIONS = {"file.inspect", "file.list", "file.search", "file.stat"}
    _WRITE_ACTIONS = {
        "file.mkdir",
        "file.copy",
        "file.move",
        "file.rename",
    }

    def supports_target(self, target: ConnectorTarget) -> bool:
        process = str(target.process_name or "").strip().casefold()
        return process in {"explorer.exe", "fileexplorer.exe", "explorer"} and bool(
            str(target.workspace_path or "").strip()
        )

    def match_score(self, target: ConnectorTarget) -> int:
        return 65 if self.supports_target(target) else -1

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        if route_id != self.route_id or not self.supports_target(target):
            return False
        try:
            self._root(target, {})
        except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError):
            return False
        return True

    def read_conversation(self, target: ConnectorTarget) -> str:
        result = self.execute_action(
            target,
            _Intent("file.inspect"),
        )
        return str((result.payload or {}).get("text", "") or "") if result.success else ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del message, cooldown
        return self._failure("send_message", "filesystem_requires_typed_intent", target)

    def execute_action(
        self,
        target: ConnectorTarget,
        intent: object,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        action = str(getattr(intent, "action", "") or "").strip().casefold()
        parameters = _parameters(intent)
        if not self.supports_target(target):
            return self._failure(action, "filesystem_workspace_target_required", target)
        if action in self._WRITE_ACTIONS and not bool(
            getattr(intent, "allow_submit", False)
        ):
            return self._failure(action, "filesystem_confirmation_required", target)
        try:
            if action in {"file.inspect", "file.list"}:
                payload = self._list(target, parameters)
            elif action == "file.search":
                payload = self._search(target, parameters)
            elif action == "file.stat":
                payload = self._stat(target, parameters)
            elif action == "file.mkdir":
                payload = self._mkdir(target, parameters)
            elif action == "file.copy":
                payload = self._copy(target, parameters)
            elif action == "file.move":
                payload = self._move(target, parameters)
            elif action == "file.rename":
                payload = self._rename(target, parameters)
            elif action == "file.delete":
                return self._failure(action, "filesystem_delete_not_implemented", target)
            elif action == "file.open":
                return self._failure(action, "filesystem_open_requires_foreground", target)
            else:
                return self._failure(action, "filesystem_capability_missing", target)
        except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError, OSError) as exc:
            return self._failure(action, _error_code(exc), target)
        payload.setdefault("control_attempts", 1 if action in self._WRITE_ACTIONS else 0)
        payload.setdefault("window_input_attempts", 0)
        payload.setdefault("keyboard_input_attempts", 0)
        payload.setdefault("mouse_input_attempts", 0)
        return ConnectorActionResult(
            success=True,
            connector_id=self.connector_id,
            action=action,
            action_key=_action_key(target, action, parameters),
            payload=payload,
        )

    def _root(self, target: ConnectorTarget, parameters: dict[str, Any]) -> Path:
        root_text = str(
            parameters.get("authorized_root", "") or target.workspace_path or ""
        ).strip()
        if not root_text:
            raise PermissionError("filesystem_authorized_root_required")
        root = Path(root_text).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError("filesystem_root_not_found")
        if not root.is_dir():
            raise NotADirectoryError("filesystem_root_not_directory")
        return root

    def _path(
        self,
        target: ConnectorTarget,
        parameters: dict[str, Any],
        key: str = "path",
        *,
        default_root: bool = False,
    ) -> Path:
        root = self._root(target, parameters)
        value = str(parameters.get(key, "") or "").strip()
        if not value and default_root:
            return root
        if not value:
            raise ValueError(f"filesystem_{key}_required")
        candidate = Path(value).expanduser()
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError("filesystem_path_outside_root") from exc
        return resolved

    def _list(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._path(target, parameters, default_root=True)
        if not root.is_dir():
            raise NotADirectoryError("filesystem_list_path_not_directory")
        pattern = str(parameters.get("pattern", "*") or "*")
        recursive = bool(parameters.get("recursive", False))
        entries = sorted(root.rglob(pattern) if recursive else root.glob(pattern))
        limit = max(1, min(int(parameters.get("max_results", 200) or 200), 2000))
        return {
            "decision": "filesystem_list_verified",
            "root": str(root),
            "entries": [_metadata(item, root) for item in entries[:limit]],
            "readback_verified": True,
        }

    def _search(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._path(target, parameters, default_root=True)
        if not root.is_dir():
            raise NotADirectoryError("filesystem_search_path_not_directory")
        query = str(parameters.get("query", "") or "").strip().casefold()
        if not query:
            raise ValueError("filesystem_search_query_required")
        extensions = {
            str(item).casefold()
            if str(item).startswith(".")
            else "." + str(item).casefold()
            for item in (parameters.get("file_types", ()) or ())
        }
        limit = max(1, min(int(parameters.get("max_results", 200) or 200), 2000))
        candidates = []
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            if query not in item.name.casefold() and query not in str(item.relative_to(root)).casefold():
                continue
            if extensions and item.suffix.casefold() not in extensions:
                continue
            candidates.append(_metadata(item, root))
            if len(candidates) >= limit:
                break
        return {
            "decision": "filesystem_search_verified",
            "root": str(root),
            "query": query,
            "candidates": candidates,
            "readback_verified": True,
        }

    def _stat(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._root(target, parameters)
        path = self._path(target, parameters)
        return {
            "decision": "filesystem_stat_verified",
            "metadata": _metadata(path, root),
            "readback_verified": True,
        }

    def _mkdir(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        path = self._path(target, parameters)
        path.mkdir(parents=bool(parameters.get("parents", False)), exist_ok=False)
        return {
            "decision": "filesystem_mkdir_verified",
            "path": str(path),
            "created": path.is_dir(),
            "readback_verified": path.is_dir(),
        }

    def _copy(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._root(target, parameters)
        source = self._path(target, parameters, "source")
        destination = self._path(target, parameters, "destination")
        _ensure_destination(destination)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return _write_result("filesystem_copy_verified", source, destination, root)

    def _move(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._root(target, parameters)
        source = self._path(target, parameters, "source")
        destination = self._path(target, parameters, "destination")
        _ensure_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return _write_result("filesystem_move_verified", source, destination, root)

    def _rename(self, target: ConnectorTarget, parameters: dict[str, Any]) -> dict:
        root = self._root(target, parameters)
        source = self._path(target, parameters)
        new_name = str(parameters.get("new_name", "") or "").strip()
        if not new_name or new_name in {".", ".."} or Path(new_name).name != new_name:
            raise ValueError("filesystem_new_name_invalid")
        destination = self._path(
            target,
            {**parameters, "path": str(source.parent / new_name)},
        )
        _ensure_destination(destination)
        source.rename(destination)
        return _write_result("filesystem_rename_verified", source, destination, root)

    @staticmethod
    def _failure(action: str, error: str, target: ConnectorTarget) -> ConnectorActionResult:
        return ConnectorActionResult(
            success=False,
            connector_id="filesystem",
            action=action or "unknown",
            action_key=_action_key(target, action, {}),
            payload={
                "control_attempts": 0,
                "window_input_attempts": 0,
                "keyboard_input_attempts": 0,
                "mouse_input_attempts": 0,
            },
            error=error,
        )


class _Intent:
    def __init__(self, action):
        self.action = action
        self.parameters = {}


def _parameters(intent: object) -> dict[str, Any]:
    value = getattr(intent, "parameters", {})
    return dict(value) if isinstance(value, dict) else {}


def _metadata(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "relative_path": str(path.relative_to(root)),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size": int(stat.st_size) if path.is_file() else 0,
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_destination(destination: Path) -> None:
    if destination.exists():
        raise FileExistsError("filesystem_destination_exists")


def _write_result(decision: str, source: Path, destination: Path, root: Path) -> dict:
    if not destination.exists():
        raise OSError("filesystem_destination_readback_missing")
    verification: dict[str, Any] = {
        "source": _metadata(source, root) if source.exists() else {},
        "destination": _metadata(destination, root),
    }
    if destination.is_file():
        verification["sha256"] = _file_hash(destination)
    return {
        "decision": decision,
        "source": str(source),
        "destination": str(destination),
        "verification": verification,
        "readback_verified": True,
    }


def _action_key(target: ConnectorTarget, action: str, parameters: dict[str, Any]) -> str:
    resource = parameters.get("path") or parameters.get("source") or "workspace"
    return f"{target.workspace_path}:{action}:{resource}"


def _error_code(exc: Exception) -> str:
    text = str(exc or "").strip()
    if text.startswith("filesystem_"):
        return text
    if isinstance(exc, FileExistsError):
        return "filesystem_destination_exists"
    if isinstance(exc, FileNotFoundError):
        return "filesystem_path_not_found"
    if isinstance(exc, PermissionError):
        return "filesystem_permission_denied"
    return f"filesystem_{exc.__class__.__name__.casefold()}"


__all__ = ["FileSystemConnector"]
