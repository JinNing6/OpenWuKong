# -*- coding: utf-8 -*-
"""Read-only discovery for locally registered native bridge endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


AGENT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION = "openwukong-native-bridge-registry-v1"
ENV_AGENT_NATIVE_BRIDGE_URLS = "OPENWUKONG_AGENT_NATIVE_BRIDGE_URLS"
ENV_AGENT_NATIVE_BRIDGE_REGISTRY_PATHS = "OPENWUKONG_AGENT_NATIVE_BRIDGE_REGISTRY_PATHS"


def discover_agent_native_bridge_urls(
    explicit_urls=(),
    *,
    agent_id: str = "",
    registry_paths=(),
    environment: dict | None = None,
) -> tuple[str, ...]:
    env = os.environ if environment is None else environment
    urls: list[str] = []
    _extend_unique_local_urls(urls, explicit_urls)
    _extend_unique_local_urls(urls, _split_values(env.get(ENV_AGENT_NATIVE_BRIDGE_URLS, "")))
    for registry_path in _effective_registry_paths(registry_paths, env):
        _extend_unique_local_urls(
            urls,
            _urls_from_registry_file(registry_path, agent_id=agent_id),
        )
    return tuple(urls)


def _effective_registry_paths(registry_paths, environment: dict) -> tuple[Path, ...]:
    values: list[Path] = []
    for item in registry_paths or ():
        path = _path_value(item)
        if path and path not in values:
            values.append(path)
    for item in _split_values(environment.get(ENV_AGENT_NATIVE_BRIDGE_REGISTRY_PATHS, "")):
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
    return tuple(root / "native-bridges.json" for root in roots)


def _urls_from_registry_file(path: Path, *, agent_id: str) -> tuple[str, ...]:
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
        if not _entry_agent_matches(entry, agent_id):
            continue
        if not _entry_surface_matches(entry):
            continue
        url = _entry_url(entry)
        if url:
            urls.append(url)
    return tuple(urls)


def _registry_entries(data: dict) -> tuple[dict, ...]:
    entries: list[dict] = []
    for key in ("agent_native_bridges", "agent_bridges", "bridges"):
        value = data.get(key)
        if isinstance(value, list):
            entries.extend(dict(item) for item in value if isinstance(item, dict))
    return tuple(entries)


def _entry_enabled(entry: dict) -> bool:
    return bool(entry.get("enabled", True)) and not bool(entry.get("disabled", False))


def _entry_bridge_type_matches(entry: dict) -> bool:
    value = str(
        entry.get("type", "")
        or entry.get("bridge_type", "")
        or entry.get("kind", "")
        or "agent_native_bridge"
    ).strip().casefold().replace("-", "_")
    return value in {
        "agent_native_bridge",
        "agent_app_native_bridge",
        "agent",
    }


def _entry_agent_matches(entry: dict, agent_id: str) -> bool:
    expected = _normalize_agent(agent_id)
    if not expected:
        return True
    values: list[str] = []
    for key in ("agent_id", "agent", "adapter_id"):
        if key in entry:
            values.append(str(entry.get(key, "") or ""))
    agents = entry.get("agents")
    if isinstance(agents, list):
        values.extend(str(item.get("agent_id", "") or item.get("id", "") or item) for item in agents)
    if not values:
        return True
    return expected in {_normalize_agent(value) for value in values}


def _entry_surface_matches(entry: dict) -> bool:
    value = str(
        entry.get("surface_kind", "")
        or entry.get("surface_type", "")
        or entry.get("bridge_surface", "")
        or ""
    ).strip().casefold().replace("-", "_").replace(" ", "_")
    return not value or value == "desktop_app"


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


def _normalize_agent(value) -> str:
    text = str(value or "").strip().casefold()
    if "codex" in text:
        return "codex"
    if "claude" in text:
        return "claude"
    if "cursor" in text:
        return "cursor"
    return text


__all__ = [
    "AGENT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION",
    "ENV_AGENT_NATIVE_BRIDGE_REGISTRY_PATHS",
    "ENV_AGENT_NATIVE_BRIDGE_URLS",
    "discover_agent_native_bridge_urls",
]
