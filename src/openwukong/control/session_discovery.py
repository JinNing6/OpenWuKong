# -*- coding: utf-8 -*-
"""Read-only discovery of connector session coordinates.

Discovery enriches a window snapshot with deterministic connector coordinates
such as DevTools URLs, IDE bridge URLs, and workspace roots. It never sends
control commands to the target application.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Protocol

import requests

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.route_policy import classify_app_family


@dataclasses.dataclass(frozen=True)
class SessionDiscoveryOptions:
    browser_debug_ports: tuple[int, ...] = (9222, 9223)
    ide_bridge_urls: tuple[str, ...] = (
        "http://127.0.0.1:8787",
        "http://127.0.0.1:8788",
        "http://127.0.0.1:8789",
        "http://127.0.0.1:8790",
    )
    workspace_roots: tuple[str, ...] = ()
    request_timeout: float = 0.2


class SessionDiscoveryHTTPProbe(Protocol):
    def get_json(self, url: str, timeout: float = 0.2):
        ...

    def post_json(self, url: str, payload: dict, timeout: float = 0.2):
        ...


class RequestsSessionDiscoveryHTTPProbe:
    """Tiny HTTP probe used only for read-only local discovery endpoints."""

    def get_json(self, url: str, timeout: float = 0.2):
        response = requests.get(url, timeout=max(0.05, float(timeout)))
        response.raise_for_status()
        return response.json()

    def post_json(self, url: str, payload: dict, timeout: float = 0.2):
        response = requests.post(
            url,
            json=payload,
            timeout=max(0.05, float(timeout)),
        )
        response.raise_for_status()
        return response.json()


@dataclasses.dataclass(frozen=True)
class DiscoveredControlTarget:
    """Target wrapper that preserves the original window plus discovered fields."""

    source: object
    debugger_url: str = ""
    ide_bridge_url: str = ""
    workspace_path: str = ""
    resource_url: str = ""
    evidence: tuple[dict, ...] = ()

    def __getattr__(self, name: str):
        return getattr(self.source, name)

    def to_connector_target(self) -> ConnectorTarget:
        return ConnectorTarget(
            pid=int(_value(self, "pid", 0) or 0),
            process_name=str(_value(self, "process_name", "") or ""),
            window_title=str(_value(self, "window_title", "") or ""),
            project_name=str(_value(self, "project_name", "") or ""),
            workspace_hint=str(_value(self, "workspace_hint", "") or ""),
            workspace_path=self.workspace_path or str(_value(self, "workspace_path", "") or ""),
            resource_url=self.resource_url or str(_value(self, "resource_url", "") or ""),
            debugger_url=self.debugger_url or str(_value(self, "debugger_url", "") or ""),
            ide_bridge_url=self.ide_bridge_url or str(_value(self, "ide_bridge_url", "") or ""),
        )

    def session_discovery_dict(self) -> dict:
        discovered: dict[str, str] = {}
        if self.debugger_url:
            discovered["debugger_url"] = self.debugger_url
        if self.ide_bridge_url:
            discovered["ide_bridge_url"] = self.ide_bridge_url
        if self.workspace_path:
            discovered["workspace_path"] = self.workspace_path
        if self.resource_url:
            discovered["resource_url"] = self.resource_url
        return {
            "discovered_fields": discovered,
            "evidence": [dict(item) for item in self.evidence],
        }

    def to_dict(self) -> dict:
        target = self.to_connector_target()
        data = self.session_discovery_dict()
        data["target"] = {
            "pid": target.pid,
            "process_name": target.process_name,
            "window_title": target.window_title,
            "workspace_path": target.workspace_path,
            "resource_url": target.resource_url,
            "debugger_url": target.debugger_url,
            "ide_bridge_url": target.ide_bridge_url,
        }
        return data


class SessionDiscovery:
    """Read-only discovery of connector coordinates for a target window."""

    def __init__(
        self,
        options: SessionDiscoveryOptions | None = None,
        *,
        http_probe: SessionDiscoveryHTTPProbe | None = None,
    ):
        self.options = options or SessionDiscoveryOptions()
        self._http_probe = http_probe or RequestsSessionDiscoveryHTTPProbe()

    def enrich(self, target_or_window: object) -> DiscoveredControlTarget:
        if isinstance(target_or_window, DiscoveredControlTarget):
            return target_or_window

        family = classify_app_family(target_or_window)
        debugger_url = str(_value(target_or_window, "debugger_url", "") or "")
        ide_bridge_url = str(_value(target_or_window, "ide_bridge_url", "") or "")
        workspace_path = str(_value(target_or_window, "workspace_path", "") or "")
        resource_url = str(_value(target_or_window, "resource_url", "") or "")
        evidence: list[dict] = []

        if family == "browser" and not debugger_url:
            discovered = self._discover_browser_debugger_url(target_or_window)
            if discovered:
                debugger_url, item = discovered
                evidence.append(item)

        if family == "ide" and not ide_bridge_url:
            discovered = self._discover_ide_bridge_url(target_or_window)
            if discovered:
                ide_bridge_url, item = discovered
                evidence.append(item)

        if family in {"terminal", "git"} and not workspace_path:
            discovered = self._discover_workspace_root(target_or_window)
            if discovered:
                workspace_path, item = discovered
                evidence.append(item)

        return DiscoveredControlTarget(
            source=target_or_window,
            debugger_url=debugger_url,
            ide_bridge_url=ide_bridge_url,
            workspace_path=workspace_path,
            resource_url=resource_url,
            evidence=tuple(evidence),
        )

    def _discover_browser_debugger_url(self, target_or_window: object) -> tuple[str, dict] | None:
        for port in self.options.browser_debug_ports:
            base = f"http://127.0.0.1:{int(port)}"
            endpoint = f"{base}/json/version"
            try:
                data = self._http_probe.get_json(
                    endpoint,
                    timeout=self.options.request_timeout,
                )
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            browser_name = str(data.get("Browser", "") or "")
            if not _browser_product_matches(target_or_window, browser_name):
                continue
            devtools_target = self._matching_browser_devtools_target(
                base,
                target_or_window,
            )
            if devtools_target is None:
                continue
            if data.get("webSocketDebuggerUrl") or data.get("Browser"):
                return base, {
                    "kind": "browser_devtools",
                    "url": base,
                    "endpoint": endpoint,
                    "browser": browser_name,
                    "target_title": str(devtools_target.get("title", "") or ""),
                    "target_url": str(devtools_target.get("url", "") or ""),
                }
        return None

    def _matching_browser_devtools_target(
        self,
        base: str,
        target_or_window: object,
    ) -> dict | None:
        endpoint = f"{base}/json/list"
        try:
            data = self._http_probe.get_json(
                endpoint,
                timeout=self.options.request_timeout,
            )
        except Exception:
            return None
        if not isinstance(data, list):
            return None
        for item in data:
            if isinstance(item, dict) and _browser_target_matches(target_or_window, item):
                return item
        return None

    def _discover_ide_bridge_url(self, target_or_window: object) -> tuple[str, dict] | None:
        target = _connector_target_from(target_or_window)
        payload = {
            "action": "read_capabilities",
            "target": {
                "pid": target.pid,
                "process_name": target.process_name,
                "window_title": target.window_title,
                "workspace_path": target.workspace_path,
            },
        }
        for base in self.options.ide_bridge_urls:
            url = f"{base.rstrip('/')}/v1/ide/capabilities"
            try:
                data = self._http_probe.post_json(
                    url,
                    payload,
                    timeout=self.options.request_timeout,
                )
            except Exception:
                continue
            if isinstance(data, dict) and data.get("ok") is not False:
                metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
                return base.rstrip("/"), {
                    "kind": "ide_bridge",
                    "url": base.rstrip("/"),
                    "endpoint": url,
                    "ide_name": str(metadata.get("ide_name", "") or ""),
                }
        return None

    def _discover_workspace_root(self, target_or_window: object) -> tuple[str, dict] | None:
        identity = _identity_text(target_or_window)
        for root in self.options.workspace_roots:
            root_path = Path(str(root or "")).expanduser()
            try:
                resolved = root_path.resolve()
            except OSError:
                continue
            if not resolved.is_dir():
                continue
            root_text = str(resolved).lower()
            name_text = resolved.name.lower()
            if root_text in identity or (name_text and name_text in identity):
                return str(resolved), {
                    "kind": "workspace_root",
                    "path": str(resolved),
                    "match": resolved.name,
                }
        return None


def _connector_target_from(target_or_window: object) -> ConnectorTarget:
    if isinstance(target_or_window, ConnectorTarget):
        return target_or_window
    if isinstance(target_or_window, DiscoveredControlTarget):
        return target_or_window.to_connector_target()
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


def _identity_text(target_or_window: object) -> str:
    target = _connector_target_from(target_or_window)
    parts = [
        target.process_name,
        target.window_title,
        target.project_name,
        target.workspace_hint,
        target.workspace_path,
        target.resource_url,
    ]
    return " ".join(part.lower() for part in parts if part)


def _value(obj: object, name: str, default):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def _browser_product_matches(target_or_window: object, browser_name: str) -> bool:
    process_name = str(_value(target_or_window, "process_name", "") or "").lower()
    browser = str(browser_name or "").lower()
    if "msedge" in process_name or "edge" in process_name:
        return "edge" in browser or "edg/" in browser
    if "chrome" in process_name:
        return "chrome" in browser and "edge" not in browser
    return bool(browser)


def _browser_target_matches(target_or_window: object, devtools_target: dict) -> bool:
    window_title = str(_value(target_or_window, "window_title", "") or "").lower()
    resource_url = str(_value(target_or_window, "resource_url", "") or "").lower()
    title = str(devtools_target.get("title", "") or "").strip().lower()
    url = str(devtools_target.get("url", "") or "").strip().lower()
    if title and title in window_title:
        return True
    if url and url in window_title:
        return True
    if resource_url and url and resource_url == url:
        return True
    return False


def default_workspace_roots() -> tuple[str, ...]:
    return (os.getcwd(),)
