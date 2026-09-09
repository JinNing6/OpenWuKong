# -*- coding: utf-8 -*-
"""Read-only discovery for locally registered WeChat native bridge endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION = (
    "openwukong-wechat-native-bridge-registry-v1"
)
ENV_WECHAT_NATIVE_BRIDGE_URLS = "OPENWUKONG_WECHAT_NATIVE_BRIDGE_URLS"
ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS = (
    "OPENWUKONG_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS"
)


def discover_wechat_native_bridge_urls(
    explicit_urls=(),
    *,
    registry_paths=(),
    environment: dict | None = None,
) -> tuple[str, ...]:
    env = os.environ if environment is None else environment
    urls: list[str] = []
    _extend_unique_local_urls(urls, explicit_urls)
    _extend_unique_local_urls(urls, _split_values(env.get(ENV_WECHAT_NATIVE_BRIDGE_URLS, "")))
    for registry_path in _effective_registry_paths(registry_paths, env):
        _extend_unique_local_urls(urls, _urls_from_registry_file(registry_path))
    return tuple(urls)


def _effective_registry_paths(registry_paths, environment: dict) -> tuple[Path, ...]:
    values: list[Path] = []
    for item in registry_paths or ():
        path = _path_value(item)
        if path and path not in values:
            values.append(path)
    for item in _split_values(environment.get(ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS, "")):
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
    return tuple(root / "wechat-native-bridges.json" for root in roots)


def _urls_from_registry_file(path: Path) -> tuple[str, ...]:
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
        url = _entry_url(entry)
        if url:
            urls.append(url)
    return tuple(urls)


def _registry_entries(data: dict) -> tuple[dict, ...]:
    entries: list[dict] = []
    for key in ("wechat_native_bridges", "wechat_bridges", "bridges"):
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
        or "wechat_native_bridge"
    ).strip().casefold().replace("-", "_")
    return value in {
        "wechat_native_bridge",
        "wechat_bridge",
        "wechat",
    }


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


__all__ = [
    "ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS",
    "ENV_WECHAT_NATIVE_BRIDGE_URLS",
    "WECHAT_NATIVE_BRIDGE_REGISTRY_SCHEMA_VERSION",
    "discover_wechat_native_bridge_urls",
]
