# -*- coding: utf-8 -*-
"""Read-only probe for the OpenAI Codex VS Code/Cursor extension bridge route."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


OPENAI_CODEX_EXTENSION_ID = "openai.chatgpt"
WEBVIEW_ROUTE_MARKERS = (
    "composer_prefill",
    "shared-object-set",
    "open-vscode-command",
)


@dataclasses.dataclass(frozen=True)
class CodexExtensionBridgeProbeReport:
    bridge_url: str
    workspace_path: str = ""
    project_name: str = ""
    extension_installed: bool = False
    extension_path: str = ""
    extension_version: str = ""
    extension_display_name: str = ""
    extension_exports_type: str = ""
    extension_export_keys: tuple[str, ...] = ()
    decision: str = ""
    prompt_send_ready: bool = False
    requires_webview_bridge: bool = False
    command_roles: tuple[dict, ...] = ()
    contributed_commands: tuple[dict, ...] = ()
    webview_route_markers: tuple[str, ...] = ()
    webview_route_evidence: tuple[dict, ...] = ()
    bridge_response: dict = dataclasses.field(default_factory=dict)
    error: str = ""

    @property
    def mode(self) -> str:
        return "codex-extension-bridge-probe"

    @property
    def safety_mode(self) -> str:
        return "read_only_codex_extension_discovery"

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
    def keyboard_input_attempts(self) -> int:
        return 0

    @property
    def clipboard_write_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return self.decision in {
            "codex_extension_webview_bridge_required",
            "codex_extension_prompt_command_available",
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "project_name": self.project_name,
            "extension_installed": self.extension_installed,
            "extension_path": self.extension_path,
            "extension_version": self.extension_version,
            "extension_display_name": self.extension_display_name,
            "extension_exports_type": self.extension_exports_type,
            "extension_export_keys": list(self.extension_export_keys),
            "prompt_send_ready": self.prompt_send_ready,
            "requires_webview_bridge": self.requires_webview_bridge,
            "command_roles": [dict(item) for item in self.command_roles],
            "contributed_commands": [dict(item) for item in self.contributed_commands],
            "webview_route_markers": list(self.webview_route_markers),
            "webview_route_evidence": [dict(item) for item in self.webview_route_evidence],
            "bridge_response": dict(self.bridge_response),
            "error": self.error,
        }


def probe_codex_extension_bridge(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    project_name: str = "",
    bridge_client: IDEExtensionBridgeClient | None = None,
    request_timeout: float = 5.0,
    installed_extension_roots: Iterable[str | Path] = (),
) -> CodexExtensionBridgeProbeReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    target = ConnectorTarget(
        project_name=project_name or (Path(workspace).name if workspace else ""),
        workspace_path=workspace,
        workspace_hint=Path(workspace).name if workspace else "",
        ide_bridge_url=bridge_url,
    )
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    try:
        response = client.read_codex_capabilities(bridge_url, target)
    except Exception as exc:
        return CodexExtensionBridgeProbeReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            decision="codex_extension_bridge_endpoint_unavailable",
            error=str(exc) or exc.__class__.__name__,
        )

    extension = response.get("extension", {})
    if not isinstance(extension, dict):
        extension = {}
    extension_path = str(extension.get("extension_path", "") or "")
    if not extension_path:
        extension_path = _find_codex_extension_path(installed_extension_roots)
    evidence = _scan_webview_route_evidence(Path(extension_path)) if extension_path else ()
    prompt_send_ready = bool(response.get("prompt_send_ready", False))
    requires_webview_bridge = bool(response.get("requires_webview_bridge", False))
    extension_installed = bool(extension.get("installed", False)) or bool(extension_path)

    if not extension_installed:
        decision = "codex_extension_missing"
    elif prompt_send_ready:
        decision = "codex_extension_prompt_command_available"
    elif requires_webview_bridge and evidence:
        decision = "codex_extension_webview_bridge_required"
    elif requires_webview_bridge:
        decision = "codex_extension_webview_route_unverified"
    else:
        decision = "codex_extension_prompt_route_unknown"

    return CodexExtensionBridgeProbeReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        project_name=target.project_name,
        extension_installed=extension_installed,
        extension_path=extension_path,
        extension_version=str(extension.get("version", "") or ""),
        extension_display_name=str(extension.get("display_name", "") or ""),
        extension_exports_type=str(extension.get("exports_type", "") or ""),
        extension_export_keys=tuple(_clean_strings(extension.get("export_keys", ()))),
        decision=decision,
        prompt_send_ready=prompt_send_ready,
        requires_webview_bridge=requires_webview_bridge,
        command_roles=_clean_dicts(response.get("command_roles", ())),
        contributed_commands=_clean_dicts(response.get("contributed_commands", ())),
        webview_route_markers=WEBVIEW_ROUTE_MARKERS,
        webview_route_evidence=evidence,
        bridge_response=response,
        error="" if decision in {
            "codex_extension_webview_bridge_required",
            "codex_extension_prompt_command_available",
        } else str(response.get("error", "") or decision),
    )


def _find_codex_extension_path(roots: Iterable[str | Path] = ()) -> str:
    for root in tuple(roots) or _default_extension_roots():
        base = Path(root).expanduser()
        if not base.is_dir():
            continue
        candidates = sorted(
            base.glob("openai.chatgpt-*"),
            key=lambda item: item.stat().st_mtime if item.exists() else 0,
            reverse=True,
        )
        for candidate in candidates:
            package = candidate / "package.json"
            if package.is_file():
                return str(candidate)
    return ""


def _default_extension_roots() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".cursor" / "extensions",
        home / ".vscode" / "extensions",
    )


def _scan_webview_route_evidence(extension_path: Path) -> tuple[dict, ...]:
    if not extension_path.is_dir():
        return ()
    files = [extension_path / "out" / "extension.js"]
    assets_dir = extension_path / "webview" / "assets"
    if assets_dir.is_dir():
        files.extend(sorted(assets_dir.glob("*.js")))
    evidence: list[dict] = []
    for file_path in files:
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        markers = tuple(marker for marker in WEBVIEW_ROUTE_MARKERS if marker in text)
        if not markers:
            continue
        evidence.append(
            {
                "path": str(file_path),
                "markers": list(markers),
                "size": file_path.stat().st_size,
            }
        )
        if _has_all_markers(evidence):
            break
    return tuple(evidence)


def _has_all_markers(evidence: Iterable[dict]) -> bool:
    found: set[str] = set()
    for item in evidence:
        found.update(str(marker) for marker in item.get("markers", ()))
    return set(WEBVIEW_ROUTE_MARKERS).issubset(found)


def _clean_dicts(values: object) -> tuple[dict, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(dict(item) for item in values if isinstance(item, dict))


def _clean_strings(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
    return tuple(cleaned)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--installed-extension-root", action="append", default=[])
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bridge_url = resolve_ide_bridge_url(
        args.bridge_url,
        agent_id="cursor",
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.bridge_registry_path or ()),
    )
    report = probe_codex_extension_bridge(
        bridge_url,
        workspace_path=args.workspace_path,
        project_name=args.project_name,
        request_timeout=args.request_timeout,
        installed_extension_roots=tuple(args.installed_extension_root or ()),
    )
    data = report.to_dict()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Codex extension bridge probe: "
            f"decision={data['decision']} "
            f"prompt_send_ready={str(data['prompt_send_ready']).lower()} "
            f"requires_webview_bridge={str(data['requires_webview_bridge']).lower()}"
        )
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
