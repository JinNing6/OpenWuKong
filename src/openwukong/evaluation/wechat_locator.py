# -*- coding: utf-8 -*-
"""Read-only WeChat locator evidence.

The locator combines UI Automation window snapshots with Win32 child-window
metadata. It never clicks, types, invokes controls, sets values, hooks live
events, or sends messages. Its purpose is to decide whether WeChat has enough
deterministic evidence for a later connector/native bridge path.
"""

from __future__ import annotations

import ctypes
import dataclasses
import time
from collections import Counter
from ctypes import wintypes
from typing import Iterable, Mapping, Optional

from openwukong.evaluation.accessibility_probe import AccessibilityWindowSnapshot


_WECHAT_PROCESSES = {"wechat.exe", "weixin.exe", "wxwork.exe"}
_WECHAT_TITLE_HINTS = {"微信", "wechat", "寰俊", "企业微信", "浼佷笟寰俊"}
_INPUT_CLASS_HINTS = ("edit", "richedit", "textinput", "textbox", "input")
_OBJID_CLIENT = 0xFFFFFFFC
_MSAA_READ_METHODS = (
    "AccessibleObjectFromWindow",
    "get_accName",
    "get_accRole",
    "get_accState",
    "get_accValue",
    "get_accChildCount",
)
_BLOCKED_MSAA_MUTATION_METHODS = (
    "accDoDefaultAction",
    "accSelect",
    "put_accName",
    "put_accValue",
)


@dataclasses.dataclass(frozen=True)
class Win32ChildWindowSnapshot:
    hwnd: int
    parent_hwnd: int
    class_name: str = ""
    text_preview: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    is_visible: bool = False
    is_enabled: bool = False

    @property
    def is_input_like(self) -> bool:
        class_name = self.class_name.lower()
        return any(hint in class_name for hint in _INPUT_CLASS_HINTS)

    @property
    def has_locator_signal(self) -> bool:
        return bool(self.class_name.strip() or self.text_preview.strip() or self.rect != (0, 0, 0, 0))

    def to_dict(self) -> dict:
        return {
            "hwnd": self.hwnd,
            "parent_hwnd": self.parent_hwnd,
            "class_name": self.class_name,
            "text_preview": self.text_preview,
            "rect": list(self.rect),
            "is_visible": self.is_visible,
            "is_enabled": self.is_enabled,
            "is_input_like": self.is_input_like,
        }


class StaticWin32WindowObserver:
    def __init__(self, children_by_parent: Mapping[int, Iterable[Win32ChildWindowSnapshot]]):
        self._children_by_parent = {
            int(parent): tuple(children)
            for parent, children in children_by_parent.items()
        }

    def snapshot_children(self, parent_hwnd: int) -> tuple[Win32ChildWindowSnapshot, ...]:
        return self._children_by_parent.get(int(parent_hwnd), ())


class CtypesWin32WindowObserver:
    """Read-only Win32 child HWND observer."""

    def __init__(self, *, max_children_per_window: int = 300):
        self.max_children_per_window = max_children_per_window
        self._user32 = ctypes.windll.user32
        self._enum_child_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def snapshot_children(self, parent_hwnd: int) -> tuple[Win32ChildWindowSnapshot, ...]:
        parent = int(parent_hwnd or 0)
        if parent <= 0:
            return ()
        children: list[Win32ChildWindowSnapshot] = []

        def _callback(hwnd, _lparam):
            if len(children) >= self.max_children_per_window:
                return False
            children.append(self._snapshot_child(int(hwnd), parent))
            return True

        callback = self._enum_child_proc(_callback)
        try:
            self._user32.EnumChildWindows(wintypes.HWND(parent), callback, wintypes.LPARAM(0))
        except Exception:
            return tuple(children)
        return tuple(children)

    def _snapshot_child(self, hwnd: int, parent_hwnd: int) -> Win32ChildWindowSnapshot:
        return Win32ChildWindowSnapshot(
            hwnd=hwnd,
            parent_hwnd=parent_hwnd,
            class_name=_get_class_name(self._user32, hwnd),
            text_preview=_get_window_text(self._user32, hwnd)[:200],
            rect=_get_window_rect(self._user32, hwnd),
            is_visible=bool(self._user32.IsWindowVisible(wintypes.HWND(hwnd))),
            is_enabled=bool(self._user32.IsWindowEnabled(wintypes.HWND(hwnd))),
        )


@dataclasses.dataclass(frozen=True)
class MsaaAccessibleSnapshot:
    hwnd: int
    object_id: str = "OBJID_CLIENT"
    name: str = ""
    role: str = ""
    state: str = ""
    value_preview: str = ""
    child_count: int = 0
    source: str = "AccessibleObjectFromWindow"
    error: str = ""

    @property
    def has_name(self) -> bool:
        return bool(self.name.strip())

    @property
    def has_value(self) -> bool:
        return bool(self.value_preview.strip())

    @property
    def has_locator_signal(self) -> bool:
        return bool(self.has_name or self.role.strip() or self.state.strip() or self.child_count > 0)

    def to_dict(self) -> dict:
        return {
            "hwnd": self.hwnd,
            "object_id": self.object_id,
            "name": self.name,
            "role": self.role,
            "state": self.state,
            "value_preview": self.value_preview,
            "child_count": self.child_count,
            "source": self.source,
            "error": self.error,
        }


class StaticMsaaObserver:
    def __init__(self, accessibles_by_hwnd: Mapping[int, Iterable[MsaaAccessibleSnapshot]]):
        self._accessibles_by_hwnd = {
            int(hwnd): tuple(accessibles)
            for hwnd, accessibles in accessibles_by_hwnd.items()
        }

    def snapshot_accessible(self, hwnd: int) -> tuple[MsaaAccessibleSnapshot, ...]:
        return self._accessibles_by_hwnd.get(int(hwnd), ())


class CtypesMsaaObserver:
    """Read-only OLEACC observer for OBJID_CLIENT IAccessible metadata."""

    def snapshot_accessible(self, hwnd: int) -> tuple[MsaaAccessibleSnapshot, ...]:
        target = int(hwnd or 0)
        if target <= 0:
            return ()
        try:
            import comtypes
            import comtypes.client
            from comtypes.automation import VARIANT
        except Exception as exc:
            return (
                MsaaAccessibleSnapshot(
                    hwnd=target,
                    error=f"dependency_error: {exc}",
                ),
            )

        initialized = False
        try:
            try:
                comtypes.CoInitialize()
                initialized = True
            except Exception:
                initialized = False
            comtypes.client.GetModule("oleacc.dll")
            from comtypes.gen import Accessibility

            accessible = comtypes.POINTER(Accessibility.IAccessible)()
            iid = Accessibility.IAccessible._iid_
            func = ctypes.windll.oleacc.AccessibleObjectFromWindow
            hr = int(
                func(
                    wintypes.HWND(target),
                    wintypes.DWORD(_OBJID_CLIENT),
                    ctypes.byref(iid),
                    ctypes.byref(accessible),
                )
            )
            if hr != 0 or not accessible:
                return (
                    MsaaAccessibleSnapshot(
                        hwnd=target,
                        error=f"AccessibleObjectFromWindow_hresult:{hr}",
                    ),
                )

            child = VARIANT(0)
            name = _safe_msaa_text(lambda: accessible.accName(child))
            role = _safe_msaa_text(lambda: accessible.accRole(child))
            state = _safe_msaa_text(lambda: accessible.accState(child))
            value = _safe_msaa_text(lambda: accessible.accValue(child))
            child_count = _safe_msaa_int(lambda: accessible.accChildCount)
            return (
                MsaaAccessibleSnapshot(
                    hwnd=target,
                    name=name[:200],
                    role=role[:100],
                    state=state[:100],
                    value_preview=value[:200],
                    child_count=child_count,
                    source="AccessibleObjectFromWindow",
                ),
            )
        except Exception as exc:
            return (
                MsaaAccessibleSnapshot(
                    hwnd=target,
                    error=f"msaa_probe_error: {exc}",
                ),
            )
        finally:
            if initialized:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass


@dataclasses.dataclass(frozen=True)
class WeChatWindowLocatorEvidence:
    pid: int
    process_name: str
    window_title: str
    top_level_hwnd: int
    top_level_class_name: str
    uia_element_count: int
    uia_input_candidate_count: int
    uia_semantic_input_count: int
    uia_semantic_action_count: int
    uia_capability_level: str
    uia_risks: tuple[str, ...]
    win32_children: tuple[Win32ChildWindowSnapshot, ...] = ()
    msaa_accessibles: tuple[MsaaAccessibleSnapshot, ...] = ()

    @property
    def win32_child_window_count(self) -> int:
        return len(self.win32_children)

    @property
    def win32_visible_child_count(self) -> int:
        return sum(1 for child in self.win32_children if child.is_visible)

    @property
    def win32_input_like_count(self) -> int:
        return sum(1 for child in self.win32_children if child.is_input_like)

    @property
    def draft_locator_candidate_count(self) -> int:
        semantic_uia = self.uia_semantic_input_count + self.uia_semantic_action_count
        win32_signals = sum(1 for child in self.win32_children if child.has_locator_signal)
        msaa_signals = sum(1 for item in self.msaa_accessibles if item.has_locator_signal)
        return semantic_uia + self.win32_input_like_count + win32_signals + msaa_signals

    @property
    def msaa_object_count(self) -> int:
        return len(self.msaa_accessibles)

    @property
    def msaa_name_count(self) -> int:
        return sum(1 for item in self.msaa_accessibles if item.has_name)

    @property
    def msaa_value_count(self) -> int:
        return sum(1 for item in self.msaa_accessibles if item.has_value)

    @property
    def msaa_error_count(self) -> int:
        return sum(1 for item in self.msaa_accessibles if item.error)

    @property
    def write_control_ready(self) -> bool:
        return False

    def win32_class_counts(self) -> dict:
        return dict(sorted(Counter(child.class_name for child in self.win32_children if child.class_name).items()))

    def msaa_role_counts(self) -> dict:
        return dict(sorted(Counter(item.role for item in self.msaa_accessibles if item.role).items()))

    def msaa_sources(self) -> tuple[str, ...]:
        return tuple(sorted({item.source for item in self.msaa_accessibles if item.source}))

    def risks(self) -> tuple[str, ...]:
        risks = list(self.uia_risks)
        if self.uia_semantic_input_count == 0:
            risks.append("no_uia_semantic_input")
        if self.win32_child_window_count == 0:
            risks.append("no_win32_child_windows")
        if self.win32_input_like_count == 0:
            risks.append("no_win32_input_like_child")
        if self.msaa_object_count == 0:
            risks.append("no_msaa_accessible_object")
        if self.msaa_error_count:
            risks.append("msaa_probe_error")
        risks.append("external_communication_surface")
        risks.append("native_bridge_required_for_write")
        return tuple(dict.fromkeys(risks))

    def recommended_routes(self) -> tuple[str, ...]:
        return (
            "wechat-native-bridge-required",
            "uia-read-only",
            "win32-child-hwnd-read-only",
            "msaa-read-only",
            "vision-fallback-last",
        )

    def to_dict(self, *, include_children: bool = True) -> dict:
        data = {
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "top_level_hwnd": self.top_level_hwnd,
            "top_level_class_name": self.top_level_class_name,
            "uia_element_count": self.uia_element_count,
            "uia_input_candidate_count": self.uia_input_candidate_count,
            "uia_semantic_input_count": self.uia_semantic_input_count,
            "uia_semantic_action_count": self.uia_semantic_action_count,
            "uia_capability_level": self.uia_capability_level,
            "win32_child_window_count": self.win32_child_window_count,
            "win32_visible_child_count": self.win32_visible_child_count,
            "win32_input_like_count": self.win32_input_like_count,
            "win32_class_counts": self.win32_class_counts(),
            "msaa_object_count": self.msaa_object_count,
            "msaa_name_count": self.msaa_name_count,
            "msaa_value_count": self.msaa_value_count,
            "msaa_error_count": self.msaa_error_count,
            "msaa_role_counts": self.msaa_role_counts(),
            "msaa_sources": list(self.msaa_sources()),
            "msaa_read_methods": list(_MSAA_READ_METHODS),
            "blocked_msaa_mutation_methods": list(_BLOCKED_MSAA_MUTATION_METHODS),
            "draft_locator_candidate_count": self.draft_locator_candidate_count,
            "write_control_ready": self.write_control_ready,
            "control_decision": "read_only_verified_write_blocked",
            "risks": list(self.risks()),
            "recommended_routes": list(self.recommended_routes()),
        }
        if include_children:
            data["win32_children"] = [child.to_dict() for child in self.win32_children]
            data["msaa_accessibles"] = [item.to_dict() for item in self.msaa_accessibles]
        return data


@dataclasses.dataclass(frozen=True)
class WeChatLocatorReport:
    windows: tuple[WeChatWindowLocatorEvidence, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-read-only-locator"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def send_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def window_count(self) -> int:
        return len(self.windows)

    @property
    def read_only_verified(self) -> bool:
        return bool(self.windows)

    @property
    def write_control_ready(self) -> bool:
        return False

    @property
    def control_decision(self) -> str:
        if not self.windows:
            return "unavailable"
        return "read_only_verified_write_blocked"

    def to_dict(self, *, include_children: bool = True) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "send_attempts": self.send_attempts,
            "window_input_attempts": self.window_input_attempts,
            "window_count": self.window_count,
            "read_only_verified": self.read_only_verified,
            "write_control_ready": self.write_control_ready,
            "control_decision": self.control_decision,
            "windows": [
                window.to_dict(include_children=include_children)
                for window in self.windows
            ],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def build_wechat_locator_report(
    windows: Iterable[AccessibilityWindowSnapshot],
    *,
    win32_observer: Optional[object] = None,
    msaa_observer: Optional[object] = None,
) -> WeChatLocatorReport:
    started = time.perf_counter()
    hwnd_observer = win32_observer or CtypesWin32WindowObserver()
    accessible_observer = msaa_observer or CtypesMsaaObserver()
    evidence: list[WeChatWindowLocatorEvidence] = []
    for window in windows:
        if not is_wechat_window(window.process_name, window.window_title):
            continue
        try:
            children = tuple(hwnd_observer.snapshot_children(int(window.hwnd or 0)))
        except Exception:
            children = ()
        msaa_accessibles = _collect_msaa_accessibles(
            accessible_observer,
            int(window.hwnd or 0),
            children,
        )
        evidence.append(
            WeChatWindowLocatorEvidence(
                pid=window.pid,
                process_name=window.process_name,
                window_title=window.window_title,
                top_level_hwnd=window.hwnd,
                top_level_class_name=window.class_name,
                uia_element_count=window.element_count,
                uia_input_candidate_count=window.input_candidate_count,
                uia_semantic_input_count=window.semantic_input_count,
                uia_semantic_action_count=window.semantic_action_count,
                uia_capability_level=window.capability_level(),
                uia_risks=window.risks(),
                win32_children=children,
                msaa_accessibles=msaa_accessibles,
            )
        )
    return WeChatLocatorReport(
        windows=tuple(evidence),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def is_wechat_window(process_name: str, window_title: str) -> bool:
    process = str(process_name or "").lower()
    title = str(window_title or "").lower()
    return process in _WECHAT_PROCESSES or any(hint.lower() in title for hint in _WECHAT_TITLE_HINTS)


def _collect_msaa_accessibles(
    observer: object,
    top_level_hwnd: int,
    children: tuple[Win32ChildWindowSnapshot, ...],
) -> tuple[MsaaAccessibleSnapshot, ...]:
    access_hints = [int(top_level_hwnd or 0)]
    access_hints.extend(child.hwnd for child in children[:20])
    seen: set[int] = set()
    snapshots: list[MsaaAccessibleSnapshot] = []
    for hwnd in access_hints:
        if hwnd <= 0 or hwnd in seen:
            continue
        seen.add(hwnd)
        try:
            snapshots.extend(observer.snapshot_accessible(hwnd))
        except Exception as exc:
            snapshots.append(
                MsaaAccessibleSnapshot(
                    hwnd=hwnd,
                    error=f"msaa_observer_error: {exc}",
                )
            )
    return tuple(snapshots)


def _get_class_name(user32, hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    try:
        copied = user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer))
    except Exception:
        return ""
    if not copied:
        return ""
    return buffer.value


def _get_window_text(user32, hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    try:
        copied = user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
    except Exception:
        return ""
    if not copied:
        return ""
    return buffer.value


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _get_window_rect(user32, hwnd: int) -> tuple[int, int, int, int]:
    rect = _RECT()
    try:
        ok = bool(user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)))
    except Exception:
        return (0, 0, 0, 0)
    if not ok:
        return (0, 0, 0, 0)
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _safe_msaa_text(callback) -> str:
    try:
        value = callback()
    except Exception:
        return ""
    if value is None:
        return ""
    return str(value)


def _safe_msaa_int(callback) -> int:
    try:
        value = callback()
    except Exception:
        return 0
    try:
        return int(value or 0)
    except Exception:
        return 0
