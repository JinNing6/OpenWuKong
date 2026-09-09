# -*- coding: utf-8 -*-
"""Execution connectors for AIOS Copilot."""

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.connectors.agent_native_bridge import AgentNativeBridgeConnector
from openwukong.connectors.browser import (
    BrowserDevToolsClient,
    BrowserDevToolsTarget,
    BrowserSessionConnector,
)
from openwukong.connectors.desktop_uia import DesktopUIAConnector
from openwukong.connectors.git import GitCommandConnector
from openwukong.connectors.ide_specialized import (
    CodexDesktopConnector,
    CopilotIDEConnector,
    CursorIDEConnector,
)
from openwukong.connectors.ide_extension import (
    IDEExtensionBridgeClient,
    IDEExtensionConnector,
)
from openwukong.connectors.registry import ConnectorManager
from openwukong.connectors.route_policy import (
    ControlRouteMatrix,
    ControlRoutePlan,
    ControlRouteStep,
    build_control_route_matrix,
    build_control_route_plan,
    classify_app_family,
)
from openwukong.connectors.terminal import TerminalCommandConnector
from openwukong.connectors.uia_ide import UIAIDEConnector
from openwukong.connectors.wechat_native_bridge import WeChatNativeBridgeConnector
from openwukong.connectors.wechat_desktop import (
    WeChatActionExecutor,
    WeChatDesktopConnector,
    WeChatWindowsBackend,
    WeChatSurfaceObserver,
    WeChatSurfaceSnapshot,
)

__all__ = [
    "ConnectorActionResult",
    "AgentNativeBridgeConnector",
    "BrowserDevToolsClient",
    "BrowserDevToolsTarget",
    "BrowserSessionConnector",
    "CodexDesktopConnector",
    "ConnectorManager",
    "ConnectorTarget",
    "ControlRouteMatrix",
    "ControlRoutePlan",
    "ControlRouteStep",
    "CopilotIDEConnector",
    "CursorIDEConnector",
    "DesktopUIAConnector",
    "GitCommandConnector",
    "IDEExtensionBridgeClient",
    "IDEExtensionConnector",
    "SessionConnector",
    "TerminalCommandConnector",
    "UIAIDEConnector",
    "WeChatNativeBridgeConnector",
    "WeChatActionExecutor",
    "WeChatDesktopConnector",
    "WeChatWindowsBackend",
    "WeChatSurfaceObserver",
    "WeChatSurfaceSnapshot",
    "build_control_route_matrix",
    "build_control_route_plan",
    "classify_app_family",
]
