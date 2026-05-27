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
