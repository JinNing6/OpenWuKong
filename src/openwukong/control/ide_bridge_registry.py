# -*- coding: utf-8 -*-
"""Read-only discovery for locally registered IDE bridge endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


IDE_BRIDGE_REGISTRY_SCHEMA_VERSION = "openwukong-ide-bridge-registry-v1"
ENV_IDE_BRIDGE_URLS = "OPENWUKONG_IDE_BRIDGE_URLS"
ENV_IDE_BRIDGE_REGISTRY_PATHS = "OPENWUKONG_IDE_BRIDGE_REGISTRY_PATHS"


def discover_ide_bridge_urls(
    explicit_urls=(),
    *,
    target: object | None = None,
    registry_paths=(),
    environment: dict | None = None,
) -> tuple[str, ...]:
    env = os.environ if environment is None else environment
    urls: list[str] = []
    _extend_unique_local_urls(urls, explicit_urls)
    _extend_unique_local_urls(urls, _split_values(env.get(ENV_IDE_BRIDGE_URLS, "")))
    for registry_path in _effective_registry_paths(registry_paths, env):
        _extend_unique_local_urls(
            urls,
            _urls_from_registry_path(registry_path, target=target),
        )
    return tuple(urls)


def _effective_registry_paths(registry_paths, environment: dict) -> tuple[Path, ...]:
    values: list[Path] = []
    for item in registry_paths or ():
        path = _path_value(item)
        if path and path not in values:
            values.append(path)
    for item in _split_values(environment.get(ENV_IDE_BRIDGE_REGISTRY_PATHS, "")):
        path = _path_value(item)
        if path and path not in values:
            values.append(path)
    if values:
        return tuple(values)
    for item in _default_registry_paths(environment):
        if item and item not in values:
            values.append(item)
    return tuple(values)


def _default_registry_paths(environment: dict) -> tuple[Path, ...]:
    roots: list[Path] = []
    for key in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = str(environment.get(key, "") or "").strip()
        if value:
            roots.append(Path(value) / "OpenWukong")
    return tuple(root / "ide-bridges" for root in roots)


def _urls_from_registry_path(path: Path, *, target: object | None) -> tuple[str, ...]:
    try:
        if path.is_dir():
            urls: list[str] = []
            for item in sorted(path.glob("*.json")):
                urls.extend(_urls_from_registry_file(item, target=target))
            return tuple(urls)
    except Exception:
        return ()
    return _urls_from_registry_file(path, target=target)


def _urls_from_registry_file(path: Path, *, target: object | None) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
    except Exception:
        return ()
    if not isinstance(data, dict):
        return ()
    urls: list[str] = []
    for entry in _registry_entries(data):
        if not _entry_enabled(entry):
            continue
        if not _entry_bridge_type_matches(entry):
            continue
        if not _entry_target_matches(entry, target):
            continue
        url = _entry_url(entry)
        if url:
            urls.append(url)
    return tuple(urls)


def _registry_entries(data: dict) -> tuple[dict, ...]:
    entries: list[dict] = []
    for key in ("ide_bridges", "ide_bridge", "bridges"):
        value = data.get(key)
        if isinstance(value, list):
            entries.extend(dict(item) for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            entries.append(dict(value))
    return tuple(entries)


def _entry_enabled(entry: dict) -> bool:
    return bool(entry.get("enabled", True)) and not bool(entry.get("disabled", False))


def _entry_bridge_type_matches(entry: dict) -> bool:
    value = str(
        entry.get("type", "")
        or entry.get("bridge_type", "")
        or entry.get("kind", "")
        or "ide_bridge"
    ).strip().casefold().replace("-", "_")
    return value in {"ide_bridge", "ide_extension_bridge", "vscode_bridge"}


def _entry_target_matches(entry: dict, target: object | None) -> bool:
    expected = _target_ide_family(target)
    if not expected:
        return _entry_workspace_matches(entry, target)
    values: list[str] = []
    for key in ("ide_id", "ide", "app_name", "product", "adapter_id"):
        if key in entry:
            values.append(str(entry.get(key, "") or ""))
    if values and expected not in {_normalize_ide_family(value) for value in values}:
        return False
    return _entry_workspace_matches(entry, target)


def _target_ide_family(target: object | None) -> str:
    if target is None:
        return ""
    values = [
        _value(target, "process_name", ""),
        _value(target, "window_title", ""),
        _value(target, "project_name", ""),
        _value(target, "workspace_hint", ""),
    ]
    for item in values:
        normalized = _normalize_ide_family(item)
        if normalized:
            return normalized
    return ""


def _normalize_ide_family(value) -> str:
    text = str(value or "").strip().casefold()
    if "cursor" in text:
        return "cursor"
    if "visual studio code" in text or "code.exe" in text or text == "code":
        return "vscode"
    if "codium" in text:
        return "vscode"
    if "copilot" in text:
        return "copilot"
    if "codex" in text:
        return "codex"
    return ""


def _entry_workspace_matches(entry: dict, target: object | None) -> bool:
    expected = _normalize_workspace_path(_value(target, "workspace_path", ""))
    if not expected:
        return True
    observed = {
        _normalize_workspace_path(value)
        for value in _entry_workspace_values(entry)
        if _normalize_workspace_path(value)
    }
    if not observed:
        return False
    return expected in observed


def _entry_workspace_values(entry: dict) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("workspace_path", "workspace_root", "workspace", "cwd"):
        value = str(entry.get(key, "") or "").strip()
        if value:
            values.append(value)
    folders = entry.get("workspace_folders", entry.get("workspaceFolders", ()))
    if isinstance(folders, list):
        for folder in folders:
            if not isinstance(folder, dict):
                continue
            fs_path = str(folder.get("fsPath", "") or "").strip()
            uri = str(folder.get("uri", "") or "").strip()
            if fs_path:
                values.append(fs_path)
            if uri:
                values.append(_file_uri_to_path(uri))
    return tuple(values)


def _file_uri_to_path(value: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
    except Exception:
        return ""
    if parsed.scheme != "file":
        return ""
    path = unquote(parsed.path or "")
    if parsed.netloc:
        path = f"//{parsed.netloc}{path}"
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    return path


def _normalize_workspace_path(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\\", "/")
    text = re.sub(r"/+", "/", text).rstrip("/")
    return text.casefold()


def _entry_url(entry: dict) -> str:
    for key in ("url", "bridge_url", "endpoint", "base_url"):
        value = _normalize_local_url(entry.get(key, ""))
        if value:
            return value
    return ""


def _extend_unique_local_urls(urls: list[str], values) -> None:
    for value in values or ():
        url = _normalize_local_url(value)
        if url and url not in urls:
            urls.append(url)


def _normalize_local_url(value) -> str:
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
    return text


def _split_values(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r"[;,\s]+", str(value or ""))
    return tuple(str(item).strip() for item in items if str(item or "").strip())


def _path_value(value) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def _value(obj: object, name: str, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


__all__ = [
    "ENV_IDE_BRIDGE_REGISTRY_PATHS",
    "ENV_IDE_BRIDGE_URLS",
    "IDE_BRIDGE_REGISTRY_SCHEMA_VERSION",
    "discover_ide_bridge_urls",
]
