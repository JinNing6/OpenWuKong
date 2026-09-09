# -*- coding: utf-8 -*-
"""Base connector abstractions for AIOS Copilot execution."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Optional


@dataclasses.dataclass(frozen=True)
class ConnectorTarget:
    """Normalized target identity for connector routing."""

    workspace_id: str = ""
    session_id: str = ""
    pid: int = 0
    process_name: str = ""
    window_title: str = ""
    project_name: str = ""
    workspace_hint: str = ""
    workspace_path: str = ""
    resource_url: str = ""
    debugger_url: str = ""
    ide_bridge_url: str = ""
    agent_native_bridge_url: str = ""
    wechat_native_bridge_url: str = ""
    conversation_name: str = ""
    background_screenshot_focus_stable: bool = True
    background_screenshot_count: int = 0
    background_screenshot_success_count: int = 0

    def identity_text(self) -> str:
        """Flatten the target identity into a lowercase blob for scoring."""
        parts = [
            self.workspace_id,
            self.session_id,
            self.process_name,
            self.window_title,
            self.project_name,
            self.workspace_hint,
            self.workspace_path,
            self.resource_url,
            self.debugger_url,
            self.ide_bridge_url,
            self.agent_native_bridge_url,
            self.wechat_native_bridge_url,
            self.conversation_name,
        ]
        return " ".join((part or "").strip().lower() for part in parts if part).strip()


@dataclasses.dataclass
class ConnectorActionResult:
    """Structured execution result returned by a connector."""

    success: bool
    connector_id: str
    action: str
    action_key: str = ""
    payload: Optional[dict] = None
    error: str = ""


class SessionConnector(ABC):
    """A connector that can read and steer a target session."""

    connector_id = "unknown"
    display_name = "Unknown"

    def match_score(self, target: ConnectorTarget) -> int:
        """
        Return a routing score for the target.

        Higher scores win. Negative means unsupported.
        """
        return 100 if self.supports_target(target) else -1

    @abstractmethod
    def supports_target(self, target: ConnectorTarget) -> bool:
        """Return True when this connector can handle the target."""

    @abstractmethod
    def read_conversation(self, target: ConnectorTarget) -> str:
        """Read recent conversation content from the target session."""

    @abstractmethod
    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        """Inject a message into the target session."""

    def execute_action(
        self,
        target: ConnectorTarget,
        intent: object,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        """Execute a normalized action, defaulting to the legacy message path.

        Existing session connectors only need ``send_message``. Connectors with
        richer action vocabularies can override this method without forcing
        every connector to understand desktop-specific intent fields.
        """
        message = ""
        for name in ("text", "value", "url", "action"):
            value = str(getattr(intent, name, "") or "").strip()
            if value:
                message = value
                break
        return self.send_message(target, message, cooldown=cooldown)
