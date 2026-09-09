"""Read-only readiness probe for the VS Code/Cursor IDE extension bridge."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
from typing import Iterable

import requests

from openwukong.connectors import ConnectorTarget
from openwukong.control.ide_bridge_registry import discover_ide_bridge_urls


DEFAULT_BRIDGE_URL = ""
DEFAULT_EXTENSION_DIR = Path(__file__).resolve().parents[3] / "extensions" / "openwukong-vscode"


@dataclasses.dataclass(frozen=True)
class IDEExtensionReadinessReport:
    extension_dir: str
    bridge_url: str
    agent_id: str
    scaffold_present: bool
    package_json_present: bool
    extension_name: str = ""
    extension_publisher: str = ""
    extension_version: str = ""
    installed_instances: tuple[dict, ...] = ()
    bridge_urls: tuple[str, ...] = ()
    bridge_ready: bool = False
    bridge_error: str = ""
    capabilities: dict = dataclasses.field(default_factory=dict)
    cursor_draft_hook: dict = dataclasses.field(default_factory=dict)
    cursor_draft_hook_error: str = ""
    selected_chat_adapter: dict = dataclasses.field(default_factory=dict)
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "ide-extension-bridge-readiness"

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
    def window_input_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def extension_installed(self) -> bool:
        return bool(self.installed_instances)

    @property
    def installed_extension_stale(self) -> bool:
        return any(
            bool(item.get("legacy_fixed_port_risk", False))
            for item in self.installed_instances
        )

    @property
    def can_execute_without_focus(self) -> bool:
        return bool(self.bridge_ready)

    @property
    def can_write_without_focus(self) -> bool:
        if self.agent_id.strip().lower() == "cursor":
            return bool(self.bridge_ready and self.cursor_draft_hook_ready)
        return bool(
            self.bridge_ready
            and self.selected_chat_adapter
            and self.selected_chat_adapter.get("available", False)
        )

    @property
    def cursor_draft_hook_ready(self) -> bool:
        return bool(
            self.cursor_draft_hook.get("ok", False)
            and self.cursor_draft_hook.get("decision") == "cursor_draft_hook_ready"
        )

    @property
    def status(self) -> str:
        if not self.scaffold_present or not self.package_json_present:
            return "scaffold_missing"
        if not self.extension_installed:
            return "extension_not_installed"
        if self.installed_extension_stale:
            return "installed_extension_stale"
        if not self.bridge_ready:
            return "bridge_unavailable"
        if self.agent_id.strip().lower() == "cursor" and not self.cursor_draft_hook_ready:
            return "cursor_draft_hook_unavailable"
        if not self.can_write_without_focus:
            return "chat_adapter_unavailable"
        return "ready"

    @property
    def blocking_reason(self) -> str:
        mapping = {
            "scaffold_missing": "extension_scaffold_missing",
            "extension_not_installed": "install_extension_in_logged_in_ide_profile",
            "installed_extension_stale": "installed_extension_uses_fixed_port_or_disruptive_autostart",
            "bridge_unavailable": "bridge_endpoint_unavailable",
            "cursor_draft_hook_unavailable": "cursor_draft_hook_endpoint_missing_or_stale",
            "chat_adapter_unavailable": "chat_adapter_not_available",
            "ready": "",
        }
        return mapping.get(self.status, self.status)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "status": self.status,
            "blocking_reason": self.blocking_reason,
            "extension_dir": self.extension_dir,
            "bridge_url": self.bridge_url,
            "agent_id": self.agent_id,
            "scaffold_present": self.scaffold_present,
            "package_json_present": self.package_json_present,
            "extension_name": self.extension_name,
            "extension_publisher": self.extension_publisher,
            "extension_version": self.extension_version,
            "extension_installed": self.extension_installed,
            "installed_extension_stale": self.installed_extension_stale,
            "installed_instances": [dict(item) for item in self.installed_instances],
            "bridge_urls": list(self.bridge_urls),
            "bridge_ready": self.bridge_ready,
            "bridge_error": self.bridge_error,
            "capabilities": dict(self.capabilities),
            "cursor_draft_hook_ready": self.cursor_draft_hook_ready,
            "cursor_draft_hook": dict(self.cursor_draft_hook),
            "cursor_draft_hook_error": self.cursor_draft_hook_error,
            "selected_chat_adapter": dict(self.selected_chat_adapter),
            "can_execute_without_focus": self.can_execute_without_focus,
            "can_write_without_focus": self.can_write_without_focus,
            "elapsed_ms": round(float(self.elapsed_ms or 0.0), 3),
        }


class RequestsHTTPProbe:
    def post_json(self, url: str, payload: dict, timeout: float = 2.0) -> dict:
        response = requests.post(url, json=payload, timeout=max(0.1, float(timeout)))
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise
        if not isinstance(data, dict):
            raise ValueError("ide_extension_bridge_response_not_object")
        if response.status_code >= 400 and "ok" not in data:
            response.raise_for_status()
        return data


def probe_ide_extension_bridge_readiness(
    *,
    extension_dir: str | Path = DEFAULT_EXTENSION_DIR,
    installed_extension_roots: Iterable[str | Path] | None = None,
    bridge_url: str = DEFAULT_BRIDGE_URL,
    bridge_registry_paths: Iterable[str | Path] = (),
    environment: dict | None = None,
    agent_id: str = "cursor",
    project_name: str = "openwukong",
    workspace_path: str = "",
    http_probe: object | None = None,
    request_timeout: float = 2.0,
) -> IDEExtensionReadinessReport:
    import time

    started = time.perf_counter()
    source_dir = Path(extension_dir).expanduser()
    package_path = source_dir / "package.json"
    package = _read_package_json(package_path)
    extension_name = str(package.get("name", "") or "")
    extension_publisher = str(package.get("publisher", "") or "")
    extension_version = str(package.get("version", "") or "")
    roots = tuple(installed_extension_roots or _default_installed_extension_roots())
    installed = _find_installed_extensions(
        roots,
        extension_name=extension_name,
        extension_publisher=extension_publisher,
    )
    capabilities: dict = {}
    bridge_error = ""
    selected_adapter: dict = {}
    active_http = http_probe or RequestsHTTPProbe()
    bridge_urls = discover_ide_bridge_urls(
        (_normalize_bridge_url(bridge_url),) if str(bridge_url or "").strip() else (),
        target=_bridge_discovery_target(agent_id, project_name, workspace_path),
        registry_paths=tuple(bridge_registry_paths or ()),
        environment=environment,
    )
    selected_bridge_url = ""
    for candidate_url in bridge_urls:
        try:
            capabilities = active_http.post_json(
                f"{_normalize_bridge_url(candidate_url)}/v1/ide/capabilities",
                {
                    "action": "read_capabilities",
                    "target": {
                        "project_name": project_name,
                        "workspace_path": workspace_path,
                        "agent_id": agent_id,
                    },
                },
                timeout=request_timeout,
            )
            if not isinstance(capabilities, dict):
                raise ValueError("ide_extension_capabilities_not_object")
            if capabilities.get("ok", False):
                selected_bridge_url = _normalize_bridge_url(candidate_url)
                break
        except Exception as exc:
            bridge_error = str(exc) or exc.__class__.__name__
            capabilities = {}
    bridge_ready = bool(capabilities.get("ok", False))
    cursor_draft_hook: dict = {}
    cursor_draft_hook_error = ""
    if bridge_ready and str(agent_id or "").strip().lower() == "cursor":
        try:
            cursor_draft_hook = active_http.post_json(
                f"{selected_bridge_url}/v1/ide/cursor/draft-hook",
                {
                    "action": "cursor_draft_hook",
                    "target": {
                        "project_name": project_name,
                        "workspace_path": workspace_path,
                        "agent_id": agent_id,
                    },
                    "message": "OPENWUKONG_IDE_EXTENSION_READINESS_DRY_RUN",
                    "allow_write": False,
                    "safety_profile": "",
                    "composer_ids": [],
                },
                timeout=request_timeout,
            )
            if not isinstance(cursor_draft_hook, dict):
                raise ValueError("cursor_draft_hook_response_not_object")
        except Exception as exc:
            cursor_draft_hook_error = str(exc) or exc.__class__.__name__
            cursor_draft_hook = {}
    selected_adapter = _select_chat_adapter(
        capabilities.get("chat_adapters", []),
        agent_id=agent_id,
    )
    return IDEExtensionReadinessReport(
        extension_dir=str(source_dir),
        bridge_url=selected_bridge_url,
        agent_id=str(agent_id or "").strip().lower() or "cursor",
        scaffold_present=source_dir.is_dir(),
        package_json_present=package_path.is_file(),
        extension_name=extension_name,
        extension_publisher=extension_publisher,
        extension_version=extension_version,
        installed_instances=tuple(installed),
        bridge_urls=tuple(bridge_urls),
        bridge_ready=bridge_ready,
        bridge_error=bridge_error,
        capabilities=capabilities,
        cursor_draft_hook=cursor_draft_hook,
        cursor_draft_hook_error=cursor_draft_hook_error,
        selected_chat_adapter=selected_adapter,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _read_package_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _find_installed_extensions(
    roots: Iterable[str | Path],
    *,
    extension_name: str,
    extension_publisher: str,
) -> list[dict]:
    matches: list[dict] = []
    normalized_name = str(extension_name or "").strip().lower()
    normalized_publisher = str(extension_publisher or "").strip().lower()
    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.is_dir():
            continue
        for child in root_path.iterdir():
            if not child.is_dir():
                continue
            package = _read_package_json(child / "package.json")
            child_name = str(package.get("name", "") or "").strip().lower()
            child_publisher = str(package.get("publisher", "") or "").strip().lower()
            folder_name = child.name.lower()
            name_match = bool(normalized_name and child_name == normalized_name)
            publisher_match = bool(
                normalized_publisher and child_publisher == normalized_publisher
            )
            folder_match = bool(
                normalized_name
                and normalized_publisher
                and folder_name.startswith(f"{normalized_publisher}.{normalized_name}")
            )
            if name_match and (publisher_match or folder_match):
                diagnostics = _installed_extension_diagnostics(child, package)
                matches.append(
                    {
                        "path": str(child),
                        "name": str(package.get("name", "") or extension_name),
                        "publisher": str(package.get("publisher", "") or extension_publisher),
                        "version": str(package.get("version", "") or ""),
                        **diagnostics,
                    }
                )
    return matches


def _installed_extension_diagnostics(path: Path, package: dict) -> dict:
    source_text = ""
    try:
        source_text = (path / "src" / "extension.js").read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        source_text = ""
    contributes = package.get("contributes", {})
    if not isinstance(contributes, dict):
        contributes = {}
    configuration = contributes.get("configuration", {})
    if not isinstance(configuration, dict):
        configuration = {}
    properties = configuration.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    port_property = (
        properties.get("openwukong.bridge.port", {})
        if isinstance(properties, dict)
        else {}
    )
    auto_start_property = (
        properties.get("openwukong.bridge.autoStart", {})
        if isinstance(properties, dict)
        else {}
    )
    port_default = port_property.get("default") if isinstance(port_property, dict) else None
    auto_start_default = (
        auto_start_property.get("default")
        if isinstance(auto_start_property, dict)
        else None
    )
    adaptive_port_default = port_default == 0
    disruptive_autostart_default = auto_start_default is True
    fixed_port_source_default = 'config.get("bridge.port", 8787)' in source_text
    disruptive_popup_source = "OpenWukong bridge failed to start" in source_text
    dynamic_fallback_declared = bool(
        isinstance(properties, dict)
        and "openwukong.bridge.dynamicPortOnConflict" in properties
    )
    dynamic_fallback_source = (
        "listenOnPort(candidate, host, 0)" in source_text
        and "candidate.address()" in source_text
    )
    legacy_fixed_port_risk = bool(
        (isinstance(port_default, int) and port_default > 0)
        or disruptive_autostart_default
        or fixed_port_source_default
        or disruptive_popup_source
    )
    return {
        "adaptive_port_default": adaptive_port_default,
        "port_default": port_default if isinstance(port_default, int) else None,
        "auto_start_default": (
            auto_start_default if isinstance(auto_start_default, bool) else None
        ),
        "dynamic_port_on_conflict_declared": dynamic_fallback_declared,
        "source_dynamic_port_fallback": dynamic_fallback_source,
        "source_disruptive_start_popup": disruptive_popup_source,
        "legacy_fixed_port_risk": legacy_fixed_port_risk,
    }


def _select_chat_adapter(value: object, *, agent_id: str) -> dict:
    adapters = value if isinstance(value, list) else []
    normalized = str(agent_id or "").strip().lower()
    for item in adapters:
        if not isinstance(item, dict):
            continue
        if str(item.get("adapter_id", "") or "").strip().lower() == normalized:
            return dict(item)
    return {}


def _bridge_discovery_target(
    agent_id: str,
    project_name: str,
    workspace_path: str,
) -> ConnectorTarget:
    normalized = str(agent_id or "").strip().lower()
    process_name = ""
    window_title = ""
    if normalized == "cursor":
        process_name = "Cursor.exe"
        window_title = "Cursor"
    elif normalized in {"vscode", "code"}:
        process_name = "Code.exe"
        window_title = "Visual Studio Code"
    elif normalized:
        process_name = f"{normalized}.exe"
        window_title = normalized
    return ConnectorTarget(
        process_name=process_name,
        window_title=window_title,
        project_name=str(project_name or ""),
        workspace_path=str(workspace_path or ""),
    )


def _default_installed_extension_roots() -> tuple[Path, ...]:
    home = Path(os.path.expanduser("~"))
    return (
        home / ".cursor" / "extensions",
        home / ".vscode" / "extensions",
    )


def _normalize_bridge_url(bridge_url: str) -> str:
    value = str(bridge_url or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"http://{value}"
    return value.rstrip("/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    parser.add_argument("--installed-extension-root", action="append", default=[])
    parser.add_argument("--bridge-url", default=DEFAULT_BRIDGE_URL)
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--agent-id", default="cursor")
    parser.add_argument("--project-name", default="openwukong")
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--request-timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    roots = tuple(args.installed_extension_root) or None
    report = probe_ide_extension_bridge_readiness(
        extension_dir=args.extension_dir,
        installed_extension_roots=roots,
        bridge_url=args.bridge_url,
        bridge_registry_paths=tuple(args.bridge_registry_path or ()),
        agent_id=args.agent_id,
        project_name=args.project_name,
        workspace_path=args.workspace_path,
        request_timeout=args.request_timeout,
    )
    data = report.to_dict()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("IDE extension bridge readiness")
        print(f"Status: {data['status']}  Bridge ready: {str(data['bridge_ready']).lower()}")
        print(f"Installed: {str(data['extension_installed']).lower()}  Write ready: {str(data['can_write_without_focus']).lower()}")
        if data["blocking_reason"]:
            print(f"Blocking: {data['blocking_reason']}")
    return 0 if report.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
