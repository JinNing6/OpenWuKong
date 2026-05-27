# -*- coding: utf-8 -*-
"""IDE-specialized UIA connectors for the developer workstation chain."""

from __future__ import annotations

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.uia_ide import UIAIDEConnector


class _ProcessBoundIDEConnector(UIAIDEConnector):
    """UIA-backed IDE connector that binds to a specific process family."""

    exact_process_names: tuple[str, ...] = ()
    process_keywords: tuple[str, ...] = ()
    identity_keywords: tuple[str, ...] = ()

    def supports_target(self, target: ConnectorTarget) -> bool:
        return self.match_score(target) >= 0

    def match_score(self, target: ConnectorTarget) -> int:
        process_name = (target.process_name or "").strip().lower()
        identity_text = target.identity_text()

        if process_name and process_name in self.exact_process_names:
            return 260

        if process_name and any(keyword in process_name for keyword in self.process_keywords):
            return 220

        if self.identity_keywords and any(keyword in identity_text for keyword in self.identity_keywords):
            return 160 if target.pid else 120

        return -1


class CodexDesktopConnector(_ProcessBoundIDEConnector):
    """Specialized connector for the Codex desktop app."""

    connector_id = "codex"
    display_name = "Codex Desktop"
    exact_process_names = ("codex.exe",)
    process_keywords = ("codex",)
    identity_keywords = ("codex",)


class CursorIDEConnector(_ProcessBoundIDEConnector):
    """Specialized connector for Cursor sessions."""

    connector_id = "cursor"
    display_name = "Cursor IDE"
    exact_process_names = ("cursor.exe",)
    process_keywords = ("cursor",)
    identity_keywords = ("cursor",)


class CopilotIDEConnector(_ProcessBoundIDEConnector):
    """Specialized connector for GitHub Copilot sessions in VS Code."""

    connector_id = "copilot"
    display_name = "GitHub Copilot"
    exact_process_names = ("code.exe", "code - insiders.exe")
    process_keywords = ()
    identity_keywords = ("copilot", "github copilot")
