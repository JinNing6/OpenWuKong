# -*- coding: utf-8 -*-
"""Bounded, read-only WeChat message monitoring."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from typing import Any


@dataclasses.dataclass(frozen=True)
class WeChatMonitorResult:
    ok: bool
    decision: str
    messages: tuple[dict[str, Any], ...] = ()
    cursor: str = ""
    unread_count: int = 0
    notifications: tuple[dict[str, Any], ...] = ()
    error: str = ""
    control_attempts: int = 0
    window_input_attempts: int = 0
    keyboard_input_attempts: int = 0
    clipboard_write_attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "wechat-monitor-result",
            "safety_mode": "read_only",
            "ok": self.ok,
            "decision": self.decision,
            "messages": [dict(message) for message in self.messages],
            "cursor": self.cursor,
            "unread_count": self.unread_count,
            "notifications": [dict(item) for item in self.notifications],
            "error": self.error,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
        }


class WeChatMonitor:
    """Poll a read-only source bound to one WeChat window and conversation."""

    def __init__(
        self,
        *,
        source: object,
        pid: int,
        hwnd: int,
        conversation_id: str = "",
    ):
        self._source = source
        self._pid = int(pid or 0)
        self._hwnd = int(hwnd or 0)
        self._conversation_id = str(conversation_id or "").strip()
        self._seen: set[str] = set()
        self._paused = False
        self._stopped = False
        self._cursor = ""

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True

    def poll_once(self) -> WeChatMonitorResult:
        if self._paused:
            return _result(True, "monitor_paused", cursor=self._cursor)
        if self._stopped:
            return _result(False, "state_changed", cursor=self._cursor)
        state_error = self._validate_source_state()
        if state_error:
            self._stopped = True
            return _result(False, "state_changed", error=state_error, cursor=self._cursor)
        try:
            raw_messages = self._read_messages()
        except Exception as exc:
            self._stopped = True
            return _result(
                False,
                "source_error",
                error=f"{exc.__class__.__name__}: {exc}",
                cursor=self._cursor,
            )
        messages: list[dict[str, Any]] = []
        for raw in _as_sequence(raw_messages):
            message = _normalize_message(raw)
            key = _message_key(message)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._cursor = key
            messages.append(message)
        unread_count = self._read_unread_count()
        notifications = self._read_notifications()
        return _result(
            True,
            "new_messages" if messages else "no_new_messages",
            messages=tuple(messages),
            cursor=self._cursor,
            unread_count=unread_count,
            notifications=notifications,
        )

    def _validate_source_state(self) -> str:
        reader = getattr(self._source, "read_state", None)
        if not callable(reader):
            return ""
        try:
            state = reader()
        except Exception as exc:
            return f"{exc.__class__.__name__}: {exc}"
        if not isinstance(state, Mapping):
            return "monitor_source_state_invalid"
        observed_pid = int(state.get("pid", self._pid) or 0)
        observed_hwnd = int(state.get("hwnd", self._hwnd) or 0)
        observed_conversation = str(
            state.get("conversation_id", self._conversation_id) or ""
        ).strip()
        login_state = str(state.get("login_state", "logged_in") or "").casefold()
        if self._pid and observed_pid != self._pid:
            return "monitor_pid_changed"
        if self._hwnd and observed_hwnd != self._hwnd:
            return "monitor_hwnd_changed"
        if self._conversation_id and observed_conversation != self._conversation_id:
            return "monitor_conversation_changed"
        if login_state and login_state not in {"logged_in", "ready", "ok"}:
            return "monitor_login_state_changed"
        return ""

    def _read_messages(self) -> object:
        reader = getattr(self._source, "read_messages", None)
        if not callable(reader):
            raise RuntimeError("monitor_source_read_messages_missing")
        return reader()

    def _read_unread_count(self) -> int:
        reader = getattr(self._source, "read_unread_count", None)
        if not callable(reader):
            return 0
        try:
            return max(0, int(reader() or 0))
        except Exception:
            return 0

    def _read_notifications(self) -> tuple[dict[str, Any], ...]:
        reader = getattr(self._source, "read_notifications", None)
        if not callable(reader):
            return ()
        try:
            return tuple(
                _normalize_message(item)
                for item in _as_sequence(reader())
            )
        except Exception:
            return ()


def _result(
    ok: bool,
    decision: str,
    *,
    messages: tuple[dict[str, Any], ...] = (),
    cursor: str = "",
    unread_count: int = 0,
    notifications: tuple[dict[str, Any], ...] = (),
    error: str = "",
) -> WeChatMonitorResult:
    return WeChatMonitorResult(
        ok=ok,
        decision=decision,
        messages=messages,
        cursor=cursor,
        unread_count=unread_count,
        notifications=notifications,
        error=error,
    )


def _as_sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping) or isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _normalize_message(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {"text": str(value or "")}


def _message_key(message: Mapping[str, Any]) -> str:
    for field in ("id", "message_id", "msg_id", "uuid"):
        value = str(message.get(field, "") or "").strip()
        if value:
            return f"id:{value}"
    encoded = json.dumps(dict(message), ensure_ascii=False, sort_keys=True, default=str)
    return "hash:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()



__all__ = ["WeChatMonitor", "WeChatMonitorResult"]
