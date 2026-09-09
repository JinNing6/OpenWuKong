# -*- coding: utf-8 -*-
"""Connector for deterministic WeChat native bridge sends."""

from __future__ import annotations

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeClient,
    WeChatNativeBridgeSenderAdapter,
    build_wechat_native_bridge_request,
)


class WeChatNativeBridgeConnector(SessionConnector):
    """Execute WeChat sends through a verified local native endpoint."""

    connector_id = "wechat-native-bridge"
    route_id = "app-native-bridge-required"
    display_name = "WeChat Native Bridge"

    def __init__(self, *, client: object | None = None, request_timeout: float = 10.0):
        self._client = client or WeChatNativeBridgeClient(request_timeout=request_timeout)
        self._request_timeout = float(request_timeout)

    def supports_target(self, target: ConnectorTarget) -> bool:
        return _is_wechat_target(target)

    def match_score(self, target: ConnectorTarget) -> int:
        if not _is_wechat_target(target):
            return -1
        score = 80
        if _bridge_url(target):
            score += 20
        if _target_name(target):
            score += 5
        if _background_screenshot_verified(target):
            score += 5
        return score

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        return (
            route_id == self.route_id
            and bool(_bridge_url(target))
            and bool(_target_name(target))
            and _background_screenshot_verified(target)
        )

    def read_conversation(self, target: ConnectorTarget) -> str:
        request = _request_from_target(target, message="", request_timeout=self._request_timeout)
        try:
            capabilities = self._client.read_capabilities(request)
        except Exception:
            return ""
        for key in ("readbackText", "readback_text", "conversation", "transcript", "text"):
            value = capabilities.get(key) if isinstance(capabilities, dict) else ""
            if value:
                return str(value)
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        request = _request_from_target(
            target,
            message=message,
            request_timeout=self._request_timeout,
        )
        report = WeChatNativeBridgeSenderAdapter(
            client=self._client,
            request_timeout=self._request_timeout,
        ).send(request)
        data = report.to_dict()
        return ConnectorActionResult(
            success=report.ok,
            connector_id=self.connector_id,
            action="send_message",
            action_key=request.request_id,
            payload=data,
            error="" if report.ok else report.decision,
        )


def _request_from_target(
    target: ConnectorTarget,
    *,
    message: str,
    request_timeout: float,
):
    del request_timeout
    return build_wechat_native_bridge_request(
        bridge_url=_bridge_url(target),
        target_name=_target_name(target),
        message=str(message or ""),
        background_screenshot_focus_stable=bool(
            target.background_screenshot_focus_stable
        ),
        background_screenshot_count=int(target.background_screenshot_count or 0),
        background_screenshot_success_count=int(
            target.background_screenshot_success_count or 0
        ),
        required_markers=(str(message or ""),) if str(message or "").strip() else (),
    )


def _bridge_url(target: ConnectorTarget) -> str:
    return str(target.wechat_native_bridge_url or "").strip()


def _target_name(target: ConnectorTarget) -> str:
    for value in (target.conversation_name, target.session_id):
        text = str(value or "").strip()
        if text:
            return text
    identity = target.identity_text()
    if "file transfer assistant" in identity:
        return "File Transfer Assistant"
    if "文件传输助手" in identity:
        return "文件传输助手"
    return ""


def _is_wechat_target(target: ConnectorTarget) -> bool:
    if _bridge_url(target):
        return True
    text = " ".join(
        str(value or "")
        for value in (
            target.process_name,
            target.window_title,
            target.project_name,
            target.workspace_hint,
            target.conversation_name,
        )
    ).casefold()
    return any(value in text for value in ("weixin", "wechat", "wxwork", "微信"))


def _background_screenshot_verified(target: ConnectorTarget) -> bool:
    return bool(
        target.background_screenshot_focus_stable
        and int(target.background_screenshot_success_count or 0) > 0
    )


__all__ = ["WeChatNativeBridgeConnector"]
