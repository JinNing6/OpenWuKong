# -*- coding: utf-8 -*-
"""UIA-backed IDE session connector."""

from __future__ import annotations

from pywinauto.application import Application

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.monitor.ai_monitor import _is_supported_workspace_process


class UIAIDEConnector(SessionConnector):
    """Fallback IDE connector backed by pywinauto + SteerOperator."""

    connector_id = "uia-ide"
    display_name = "UIA IDE Fallback"

    def supports_target(self, target: ConnectorTarget) -> bool:
        process_name = (target.process_name or "").strip()
        if process_name and _is_supported_workspace_process(process_name):
            return True
        return bool(target.pid)

    def match_score(self, target: ConnectorTarget) -> int:
        process_name = (target.process_name or "").strip()
        if process_name and _is_supported_workspace_process(process_name):
            return 40
        if target.pid:
            return 10
        return -1

    def read_conversation(self, target: ConnectorTarget) -> str:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        app = Application(backend="uia").connect(process=target.pid)
        return SteerOperator.read_conversation(app, target.window_title)

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        app = Application(backend="uia").connect(process=target.pid)
        ok, key = SteerOperator.steer(
            app,
            message,
            target.pid,
            cooldown,
            target.window_title,
        )
        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action="send_message",
            action_key=key if ok else "",
            payload={
                "pid": target.pid,
                "window_title": target.window_title,
            },
            error="" if ok else "send_message_failed",
        )
