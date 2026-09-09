# -*- coding: utf-8 -*-
"""Read-only observation of the personal Windows WeChat desktop surface."""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.control.surface_capabilities import (
    SurfaceCapabilityProfile,
    profile_from_accessibility_window,
)
from openwukong.control.wechat_surface import (
    WeChatControlCandidate,
    WeChatTargetCandidate,
)
from openwukong.evaluation.accessibility_probe import AccessibilityWindowSnapshot


_PERSONAL_PROCESSES = {"weixin.exe", "wechat.exe"}
_GENERIC_LABELS = {
    "微信",
    "wechat",
    "weixin",
    "send",
    "发送",
    "publish",
    "发布",
    "moments",
    "朋友圈",
    "search",
    "搜索",
    "attachment",
    "附件",
    "file",
    "文件",
    "type a message",
    "输入消息",
    "登录",
    "login",
}
_LOGIN_HINTS = ("登录", "login", "扫码", "sign in")


@dataclasses.dataclass(frozen=True)
class WeChatSurfaceSnapshot:
    windows: tuple[AccessibilityWindowSnapshot, ...]
    selected_window: AccessibilityWindowSnapshot | None
    profile: SurfaceCapabilityProfile
    controls: tuple[WeChatControlCandidate, ...] = ()
    targets: tuple[WeChatTargetCandidate, ...] = ()
    login_state: str = "unknown"
    decision: str = "personal_wechat_window_not_found"
    control_attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "wechat-surface-snapshot",
            "safety_mode": "read_only",
            "decision": self.decision,
            "login_state": self.login_state,
            "control_attempts": self.control_attempts,
            "windows": [_window_to_dict(window) for window in self.windows],
            "selected_window": (
                _window_to_dict(self.selected_window)
                if self.selected_window is not None
                else {}
            ),
            "profile": self.profile.to_dict(),
            "controls": [control.to_dict() for control in self.controls],
            "targets": [target.to_dict() for target in self.targets],
        }


class WeChatSurfaceObserver:
    """Observe a personal WeChat window without focusing or mutating it."""

    def __init__(
        self,
        *,
        window_source: object | None = None,
        ttl_seconds: float = 60.0,
    ):
        self._window_source = window_source
        self._ttl_seconds = float(ttl_seconds)

    def inspect(
        self,
        windows: Iterable[AccessibilityWindowSnapshot] | None = None,
        *,
        observed_at: datetime | None = None,
    ) -> WeChatSurfaceSnapshot:
        observed = observed_at or datetime.now(timezone.utc)
        all_windows = tuple(windows) if windows is not None else self._read_windows()
        personal = tuple(
            window
            for window in all_windows
            if _is_personal_wechat_window(window)
        )
        if not personal:
            profile = SurfaceCapabilityProfile(
                observed_at=observed,
                ttl_seconds=self._ttl_seconds,
            )
            return WeChatSurfaceSnapshot(
                windows=all_windows,
                selected_window=None,
                profile=profile,
                decision="personal_wechat_window_not_found",
            )
        if len(personal) > 1:
            profile = profile_from_accessibility_window(
                personal[0],
                observed_at=observed,
                ttl_seconds=self._ttl_seconds,
            )
            return WeChatSurfaceSnapshot(
                windows=personal,
                selected_window=None,
                profile=profile,
                decision="multiple_personal_wechat_windows",
            )

        window = personal[0]
        controls = _control_candidates(window)
        targets = _target_candidates(window, controls)
        login_state = _login_state(window, controls, targets)
        profile = _wechat_profile(
            window,
            controls=controls,
            targets=targets,
            login_state=login_state,
            observed_at=observed,
            ttl_seconds=self._ttl_seconds,
        )
        return WeChatSurfaceSnapshot(
            windows=personal,
            selected_window=window,
            profile=profile,
            controls=controls,
            targets=targets,
            login_state=login_state,
            decision="surface_ready",
        )

    def _read_windows(self) -> tuple[AccessibilityWindowSnapshot, ...]:
        source = self._window_source
        if source is None:
            from openwukong.evaluation.accessibility_probe import (
                PywinautoAccessibilityObserver,
            )

            return tuple(PywinautoAccessibilityObserver().snapshot())
        if callable(source):
            return tuple(source())
        snapshot = getattr(source, "snapshot", None)
        if callable(snapshot):
            return tuple(snapshot())
        return tuple(source)  # type: ignore[arg-type]


class WeChatActionExecutor:
    """Dispatch typed WeChat actions to an injected surface backend."""

    _ACTION_METHODS = {
        "wechat.window.inspect": "inspect",
        "wechat.window.attach": "inspect",
        "wechat.chat.search": "search_contact",
        "wechat.contact.search": "search_contact",
        "wechat.group.search": "search_group",
        "wechat.chat.open": "open_conversation",
        "wechat.chat.read": "read_conversation",
        "wechat.contact.read": "read_contact",
        "wechat.group.read": "read_group",
        "wechat.chat.draft": "draft_text",
        "wechat.chat.copy": "copy_message",
        "wechat.chat.quote": "quote_message",
        "wechat.chat.reply": "reply_message",
        "wechat.chat.forward": "forward_message",
        "wechat.chat.favorite": "favorite_message",
        "wechat.chat.translate": "translate_message",
        "wechat.chat.mark_unread": "mark_unread",
        "wechat.chat.pin": "pin_conversation",
        "wechat.chat.mute": "mute_conversation",
        "wechat.chat.archive": "archive_conversation",
        "wechat.chat.send_text": "send_text",
        "wechat.chat.send_emoji": "send_emoji",
        "wechat.media.send_image": "send_media",
        "wechat.media.send_video": "send_media",
        "wechat.media.send_voice": "send_media",
        "wechat.file.send": "send_file",
        "wechat.file.download": "download_file",
        "wechat.file.open": "open_file",
        "wechat.moments.open": "open_moments",
        "wechat.moments.read": "read_moments",
        "wechat.moments.draft": "draft_moment",
        "wechat.moments.publish": "publish_moment",
        "wechat.window.minimize": "minimize",
        "wechat.window.restore": "restore",
        "wechat.window.maximize": "maximize",
        "wechat.window.close": "close",
        "wechat.chat.delete": "delete_message",
        "wechat.chat.recall": "recall_message",
        "wechat.contact.add": "add_contact",
        "wechat.group.add_member": "add_group_member",
        "wechat.group.remove_member": "remove_group_member",
        "wechat.chat.bulk_forward": "bulk_forward",
        "wechat.chat.broadcast": "broadcast",
        "wechat.account.switch": "switch_account",
        "wechat.auth.login": "login_authorization",
        "wechat.security.settings": "security_settings",
        "wechat.settings.read": "read_settings",
        "wechat.settings.update": "update_settings",
    }
    _SIDE_EFFECT_ACTIONS = {
        "wechat.chat.send_text",
        "wechat.chat.send_emoji",
        "wechat.media.send_image",
        "wechat.media.send_video",
        "wechat.media.send_voice",
        "wechat.file.send",
        "wechat.file.download",
        "wechat.moments.publish",
        "wechat.window.minimize",
        "wechat.window.restore",
        "wechat.window.maximize",
        "wechat.window.close",
        "wechat.chat.delete",
        "wechat.chat.recall",
        "wechat.contact.add",
        "wechat.group.add_member",
        "wechat.group.remove_member",
        "wechat.chat.bulk_forward",
        "wechat.chat.broadcast",
        "wechat.account.switch",
        "wechat.auth.login",
        "wechat.security.settings",
        "wechat.settings.update",
    }
    _HIGH_RISK_ACTIONS = {
        "wechat.chat.delete",
        "wechat.chat.recall",
        "wechat.contact.add",
        "wechat.group.add_member",
        "wechat.group.remove_member",
        "wechat.chat.bulk_forward",
        "wechat.chat.broadcast",
        "wechat.account.switch",
        "wechat.auth.login",
        "wechat.security.settings",
    }

    def __init__(self, *, backend: object):
        self._backend = backend

    def execute(
        self,
        target: ConnectorTarget,
        intent: object,
    ) -> ConnectorActionResult:
        action = _normalized_action(getattr(intent, "action", ""))
        parameters = _intent_parameters(intent)
        if not _is_personal_target(target):
            return self._failure(action, "wechat_personal_target_required", target)
        if action in self._SIDE_EFFECT_ACTIONS and not bool(
            getattr(intent, "allow_submit", False)
            or parameters.get("confirmed", False)
        ):
            return self._failure(
                action,
                "wechat_side_effect_confirmation_required",
                target,
            )
        if action in self._HIGH_RISK_ACTIONS:
            confirmed_effect_ids = set(
                str(item)
                for item in (
                    getattr(intent, "confirmed_effect_ids", ())
                    or parameters.get("confirmed_effect_ids", ())
                    or ()
                )
            )
            if not bool(getattr(intent, "allow_blocked_side_effects", False)) or (
                action not in confirmed_effect_ids
            ):
                return self._failure(
                    action,
                    "wechat_high_risk_confirmation_required",
                    target,
                )
        method_name = self._ACTION_METHODS.get(action)
        if action == "wechat.chat.search" and str(
            parameters.get("target_type", "conversation")
        ).casefold() in {"group", "群"}:
            method_name = "search_group"
        if not method_name:
            return self._failure(action, "wechat_capability_missing", target)
        method = getattr(self._backend, method_name, None)
        if not callable(method):
            return self._failure(action, "wechat_capability_missing", target)
        if action in {
            "wechat.media.send_image",
            "wechat.media.send_video",
            "wechat.media.send_voice",
            "wechat.file.send",
            "wechat.file.download",
        }:
            try:
                parameters = dict(parameters)
                parameters["attachment"] = _attachment_metadata(target, parameters)
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                return self._failure(action, str(exc), target)
        if action == "wechat.moments.publish":
            try:
                parameters = dict(parameters)
                parameters["media"] = _media_metadata(target, parameters)
            except (FileNotFoundError, PermissionError, ValueError) as exc:
                return self._failure(action, str(exc), target)
        try:
            result = method(target, parameters)
        except Exception as exc:
            return self._failure(action, f"wechat_backend_{exc.__class__.__name__.casefold()}", target)
        if not isinstance(result, dict):
            return self._failure(action, "wechat_backend_result_invalid", target)
        payload = dict(result)
        if "attachment" in parameters:
            payload.setdefault("attachment", dict(parameters["attachment"]))
        if "media" in parameters:
            payload.setdefault("media", [dict(item) for item in parameters["media"]])
        _set_default_counters(payload)
        payload.setdefault("target_pid", int(target.pid or 0))
        payload.setdefault("target_process_name", target.process_name)
        payload.setdefault("target_window_title", target.window_title)
        verified = _action_result_verified(action, payload)
        payload["verification"] = dict(payload.get("verification", {}) or {})
        payload["verification"].setdefault("verified", verified)
        if not verified:
            return ConnectorActionResult(
                success=False,
                connector_id="wechat-desktop",
                action=action,
                action_key=_action_key(target, action, parameters),
                payload=payload,
                error="wechat_verification_failed",
            )
        return ConnectorActionResult(
            success=True,
            connector_id="wechat-desktop",
            action=action,
            action_key=_action_key(target, action, parameters),
            payload=payload,
        )

    @staticmethod
    def _failure(
        action: str,
        error: str,
        target: ConnectorTarget,
    ) -> ConnectorActionResult:
        return ConnectorActionResult(
            success=False,
            connector_id="wechat-desktop",
            action=action or "unknown",
            action_key=_action_key(target, action, {}),
            payload={
                "target_pid": int(target.pid or 0),
                "target_process_name": target.process_name,
                "target_window_title": target.window_title,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "keyboard_input_attempts": 0,
                "clipboard_write_attempts": 0,
                "send_attempts": 0,
                "publish_attempts": 0,
            },
            error=error,
        )


class WeChatDesktopConnector(SessionConnector):
    """Capability-backed connector for personal desktop WeChat actions."""

    connector_id = "wechat-desktop"
    route_id = "wechat-desktop-capability"
    display_name = "Personal WeChat Desktop"

    def __init__(self, *, backend: object):
        self._executor = WeChatActionExecutor(backend=backend)
        self._backend = backend

    def supports_target(self, target: ConnectorTarget) -> bool:
        return _is_personal_target(target)

    def match_score(self, target: ConnectorTarget) -> int:
        return 45 if self.supports_target(target) else -1

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        return route_id == self.route_id and self.supports_target(target)

    def read_conversation(self, target: ConnectorTarget) -> str:
        result = self.execute_action(
            target,
            _Intent("wechat.chat.read"),
        )
        if not result.success:
            return ""
        return str((result.payload or {}).get("text", "") or "")

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        return ConnectorActionResult(
            success=False,
            connector_id=self.connector_id,
            action="send_message",
            payload={"control_attempts": 0},
            error="wechat_desktop_requires_typed_intent",
        )

    def execute_action(
        self,
        target: ConnectorTarget,
        intent: object,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        return self._executor.execute(target, intent)


def _wechat_profile(
    window: AccessibilityWindowSnapshot,
    *,
    controls: tuple[WeChatControlCandidate, ...],
    targets: tuple[WeChatTargetCandidate, ...],
    login_state: str,
    observed_at: datetime,
    ttl_seconds: float,
) -> SurfaceCapabilityProfile:
    base = profile_from_accessibility_window(
        window,
        observed_at=observed_at,
        ttl_seconds=ttl_seconds,
    )
    grants = {name: dict(value) for name, value in base.capabilities.items()}
    roles = {control.role for control in controls}
    if login_state != "logged_out":
        if targets or "message_list" in roles:
            grants["wechat.chat.read"] = _read_grant("uia-structural-observe", 85)
        if "search_input" in roles or "search" in roles:
            grants["wechat.chat.search"] = _read_grant("uia-semantic", 80)
        if "composer" in roles:
            grants["wechat.chat.draft"] = _write_grant("uia-semantic", 88)
        if "composer" in roles and "submit" in roles:
            grants["wechat.chat.send_text"] = _write_grant("uia-semantic", 88)
        if "attachment" in roles and "composer" in roles:
            grants["wechat.file.send"] = _write_grant("uia-semantic", 75)
        if any(item.target_type == "group" for item in targets):
            grants["wechat.group.read"] = _read_grant("uia-structural-observe", 75)
        if targets:
            grants["wechat.contact.read"] = _read_grant("uia-structural-observe", 75)
        if "moments_entry" in roles:
            grants["wechat.moments.read"] = _read_grant("uia-structural-observe", 82)
        if "moments_entry" in roles and "moments_publish" in roles:
            grants["wechat.moments.publish"] = _write_grant("uia-semantic", 82)
    return dataclasses.replace(
        base,
        surface_id=f"wechat:{window.hwnd or window.pid}",
        session_id=f"wechat:{window.pid}:{window.hwnd}",
        capabilities=grants,
    )


def _control_candidates(
    window: AccessibilityWindowSnapshot,
) -> tuple[WeChatControlCandidate, ...]:
    controls: list[WeChatControlCandidate] = []
    for element in window.elements:
        role = _control_role(element)
        if not role:
            continue
        patterns = tuple(str(item) for item in (element.patterns or ()))
        confidence = 90 if element.automation_id or element.name else 65
        controls.append(
            WeChatControlCandidate(
                role=role,
                name=str(element.name or "").strip(),
                automation_id=str(element.automation_id or "").strip(),
                control_type=str(element.control_type or "").strip(),
                patterns=patterns,
                rect=tuple(element.rect),
                confidence=confidence,
                source="uia",
                hwnd=int(window.hwnd or 0),
            )
        )
    return tuple(controls)


def _target_candidates(
    window: AccessibilityWindowSnapshot,
    controls: tuple[WeChatControlCandidate, ...],
) -> tuple[WeChatTargetCandidate, ...]:
    targets: list[WeChatTargetCandidate] = []
    seen: set[tuple[str, str]] = set()
    for element in window.elements:
        name = str(element.name or "").strip()
        if not _is_target_label(name, element.control_type):
            continue
        target_type = _target_type(name)
        key = (target_type, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            WeChatTargetCandidate(
                target_type=target_type,
                display_name=name,
                target_id=str(element.automation_id or "").strip(),
                confidence=80 if element.automation_id else 65,
                source="uia",
                evidence=(f"hwnd:{int(window.hwnd or 0)}",),
            )
        )
    title_name = _conversation_name_from_title(window.window_title)
    if title_name and ("conversation", title_name.casefold()) not in seen:
        targets.append(
            WeChatTargetCandidate(
                target_type="conversation",
                display_name=title_name,
                target_id=f"hwnd:{int(window.hwnd or 0)}",
                confidence=70,
                source="window_title",
                evidence=(f"hwnd:{int(window.hwnd or 0)}",),
            )
        )
    return tuple(targets)


def _control_role(element: object) -> str:
    control_type = str(getattr(element, "control_type", "") or "").strip()
    name = str(getattr(element, "name", "") or "").strip().casefold()
    patterns = {str(item) for item in (getattr(element, "patterns", ()) or ())}
    if control_type in {"Edit", "Document", "ComboBox"} and patterns & {
        "Value",
        "TextEdit",
    }:
        if any(token in name for token in ("搜索", "search", "查找")):
            return "search_input"
        if any(token in name for token in ("消息", "message", "输入", "type", "composer")):
            return "composer"
        return "input"
    if control_type in {"Button", "Hyperlink", "MenuItem", "SplitButton"} and "Invoke" in patterns:
        if any(token in name for token in ("发送", "send", "submit")):
            return "submit"
        if any(token in name for token in ("朋友圈", "moments")):
            return "moments_entry"
        if any(token in name for token in ("发布", "publish", "post")):
            return "moments_publish"
        if any(token in name for token in ("附件", "attachment", "file", "文件", "图片")):
            return "attachment"
        if any(token in name for token in ("搜索", "search", "查找")):
            return "search"
        return "action"
    if control_type in {"Text", "List", "ListItem", "DataItem", "Document"}:
        if any(token in name for token in ("消息", "message", "聊天", "chat", "conversation")):
            return "message_list"
    return ""


def _is_target_label(name: str, control_type: str) -> bool:
    normalized = _normalize(name)
    if not normalized or normalized in _GENERIC_LABELS:
        return False
    if any(token in normalized for token in _LOGIN_HINTS):
        return False
    if control_type not in {"Text", "ListItem", "DataItem", "Document"}:
        return False
    if len(normalized) > 80:
        return False
    return True


def _target_type(name: str) -> str:
    normalized = _normalize(name)
    if any(token in normalized for token in ("群", "group", "群聊")):
        return "group"
    if any(token in normalized for token in ("公众号", "official account")):
        return "official_account"
    return "conversation"


def _conversation_name_from_title(title: str) -> str:
    value = str(title or "").strip()
    if not value or any(token in _normalize(value) for token in _LOGIN_HINTS):
        return ""
    for suffix in (" - WeChat", " - 微信", " | WeChat", " | 微信"):
        if value.casefold().endswith(suffix.casefold()):
            value = value[: -len(suffix)].strip()
            break
    if _normalize(value) in _GENERIC_LABELS or len(value) > 80:
        return ""
    return value


def _login_state(
    window: AccessibilityWindowSnapshot,
    controls: tuple[WeChatControlCandidate, ...],
    targets: tuple[WeChatTargetCandidate, ...],
) -> str:
    title = _normalize(window.window_title)
    names = " ".join(_normalize(item.name) for item in controls)
    if any(token in f"{title} {names}" for token in _LOGIN_HINTS):
        return "logged_out"
    if targets or any(item.role in {"composer", "message_list"} for item in controls):
        return "logged_in"
    return "unknown"


def _is_personal_wechat_window(window: object) -> bool:
    process = str(getattr(window, "process_name", "") or "").strip().casefold()
    return process in _PERSONAL_PROCESSES


def _normalize(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _read_grant(route: str, confidence: int) -> dict[str, Any]:
    return {"route": route, "confidence": confidence, "read_only": True}


def _write_grant(route: str, confidence: int) -> dict[str, Any]:
    return {"route": route, "confidence": confidence, "read_only": False}


def _window_to_dict(window: AccessibilityWindowSnapshot) -> dict[str, Any]:
    return {
        "pid": int(window.pid or 0),
        "process_name": str(window.process_name or ""),
        "window_title": str(window.window_title or ""),
        "class_name": str(window.class_name or ""),
        "hwnd": int(window.hwnd or 0),
        "element_count": len(window.elements),
    }


def _is_personal_target(target: ConnectorTarget) -> bool:
    process = str(target.process_name or "").strip().casefold()
    return process in _PERSONAL_PROCESSES


def _normalized_action(value: object) -> str:
    action = str(value or "").strip().casefold()
    aliases = {
        "inspect": "wechat.window.inspect",
        "read": "wechat.chat.read",
        "read_conversation": "wechat.chat.read",
        "send_message": "wechat.chat.send_text",
        "write_text": "wechat.chat.draft",
    }
    return aliases.get(action, action)


def _intent_parameters(intent: object) -> dict[str, Any]:
    parameters = getattr(intent, "parameters", {})
    return dict(parameters) if isinstance(parameters, dict) else {}


def _set_default_counters(payload: dict[str, Any]) -> None:
    for key in (
        "control_attempts",
        "send_attempts",
        "window_input_attempts",
        "keyboard_input_attempts",
        "mouse_input_attempts",
        "clipboard_write_attempts",
    ):
        payload.setdefault(key, 0)


def _action_result_verified(action: str, payload: dict[str, Any]) -> bool:
    if payload.get("verification", {}).get("verified") is True:
        return True
    if action in {"wechat.window.inspect", "wechat.window.attach"}:
        return bool(payload.get("attached") or payload.get("login_state"))
    if action in {
        "wechat.chat.search",
        "wechat.contact.search",
        "wechat.group.search",
    }:
        verification = payload.get("verification")
        return bool(payload.get("candidates") is not None and (
            isinstance(verification, dict) and verification.get("stable") is True
        ))
    if action in {"wechat.chat.draft"}:
        return bool(payload.get("draft_readback_verified"))
    if action in {
        "wechat.chat.send_text",
        "wechat.chat.send_emoji",
        "wechat.media.send_image",
        "wechat.media.send_video",
        "wechat.media.send_voice",
        "wechat.file.send",
        "wechat.file.download",
    }:
        return bool(
            payload.get("readback_verified")
            and (payload.get("sent") or payload.get("uploaded") or payload.get("downloaded"))
        )
    if action in {"wechat.chat.read", "wechat.contact.read", "wechat.group.read"}:
        return bool(payload.get("readback_verified") or payload.get("messages") is not None)
    if action == "wechat.moments.open":
        return bool(payload.get("moments_open") and payload.get("readback_verified"))
    if action == "wechat.moments.read":
        return bool(payload.get("readback_verified") or payload.get("posts") is not None)
    if action == "wechat.moments.draft":
        return bool(payload.get("draft_readback_verified"))
    if action == "wechat.moments.publish":
        return bool(payload.get("published") and payload.get("readback_verified"))
    if action in {
        "wechat.window.minimize",
        "wechat.window.restore",
        "wechat.window.maximize",
        "wechat.window.close",
    }:
        return bool(
            payload.get("readback_verified")
            and any(payload.get(key) for key in (
                "minimized",
                "restored",
                "maximized",
                "closed",
            ))
        )
    if action in {
        "wechat.chat.delete",
        "wechat.chat.recall",
        "wechat.contact.add",
        "wechat.group.add_member",
        "wechat.group.remove_member",
        "wechat.chat.bulk_forward",
        "wechat.chat.broadcast",
        "wechat.account.switch",
        "wechat.auth.login",
        "wechat.security.settings",
        "wechat.settings.update",
    }:
        return bool(payload.get("readback_verified"))
    if action == "wechat.settings.read":
        return bool(payload.get("readback_verified") or payload.get("settings") is not None)
    if action == "wechat.chat.open":
        return bool(payload.get("target_verified"))
    if action in {
        "wechat.chat.copy",
        "wechat.chat.quote",
        "wechat.chat.reply",
        "wechat.chat.forward",
        "wechat.chat.favorite",
        "wechat.chat.translate",
        "wechat.chat.mark_unread",
        "wechat.chat.pin",
        "wechat.chat.mute",
        "wechat.chat.archive",
    }:
        return bool(payload.get("readback_verified"))
    return False


def _action_key(
    target: ConnectorTarget,
    action: str,
    parameters: dict[str, Any],
) -> str:
    resource = (
        parameters.get("conversation_name")
        or parameters.get("message_id")
        or target.conversation_name
        or "surface"
    )
    return f"{int(target.pid or 0)}:{action}:{resource}"


def _attachment_metadata(
    target: ConnectorTarget,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    path_text = str(parameters.get("path", "") or "").strip()
    if not path_text:
        raise ValueError("wechat_attachment_path_required")
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError("wechat_attachment_not_found")
    if not path.is_file():
        raise ValueError("wechat_attachment_not_file")
    root_text = str(
        parameters.get("approved_root", "") or target.workspace_path or ""
    ).strip()
    if not root_text:
        raise PermissionError("wechat_attachment_root_required")
    root = Path(root_text).expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError("wechat_attachment_path_outside_root") from exc
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return {
        "path": str(path),
        "name": path.name,
        "size": size,
        "sha256": digest.hexdigest(),
    }


def _media_metadata(
    target: ConnectorTarget,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_paths = parameters.get("media_paths", ())
    if isinstance(raw_paths, (str, bytes)) or raw_paths is None:
        raw_paths = (raw_paths,) if raw_paths else ()
    paths = tuple(str(item or "").strip() for item in raw_paths if str(item or "").strip())
    if len(paths) > 9:
        raise ValueError("wechat_moments_media_count_exceeded")
    return [
        _attachment_metadata(target, {**parameters, "path": path})
        for path in paths
    ]


class _Intent:
    def __init__(self, action: str):
        self.action = action
        self.parameters: dict[str, Any] = {}


__all__ = [
    "WeChatActionExecutor",
    "WeChatSurfaceObserver",
    "WeChatSurfaceSnapshot",
    "WeChatDesktopConnector",
]
