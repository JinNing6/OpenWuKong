# -*- coding: utf-8 -*-
"""Resolve IDE bridge URLs from explicit input or the local bridge registry."""

from __future__ import annotations

from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.control.ide_bridge_registry import discover_ide_bridge_urls


def resolve_ide_bridge_url(
    explicit_url: str = "",
    *,
    agent_id: str = "cursor",
    project_name: str = "",
    workspace_path: str | Path = "",
    registry_paths=(),
    environment: dict | None = None,
) -> str:
    """Return an explicit URL or the first matching dynamically registered URL."""

    explicit = str(explicit_url or "").strip()
    if explicit:
        urls = discover_ide_bridge_urls(
            (explicit,),
            target=_bridge_discovery_target(
                agent_id=agent_id,
                project_name=project_name,
                workspace_path=workspace_path,
            ),
            registry_paths=tuple(registry_paths or ()),
            environment=environment,
        )
        return urls[0] if urls else explicit

    urls = discover_ide_bridge_urls(
        (),
        target=_bridge_discovery_target(
            agent_id=agent_id,
            project_name=project_name,
            workspace_path=workspace_path,
        ),
        registry_paths=tuple(registry_paths or ()),
        environment=environment,
    )
    return urls[0] if urls else ""


def _bridge_discovery_target(
    *,
    agent_id: str,
    project_name: str,
    workspace_path: str | Path,
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
    workspace = str(Path(workspace_path)) if workspace_path else ""
    return ConnectorTarget(
        process_name=process_name,
        window_title=window_title,
        project_name=str(project_name or "") or (Path(workspace).name if workspace else ""),
        workspace_path=workspace,
        workspace_hint=Path(workspace).name if workspace else "",
    )


__all__ = ["resolve_ide_bridge_url"]
