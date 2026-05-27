# -*- coding: utf-8 -*-
"""Guarded application control bus.

The bus treats UI actions as auditable transactions: locate a target, execute a
bounded primitive, verify the visible state, and optionally clean up.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Iterable, Optional, Protocol


@dataclasses.dataclass(frozen=True)
class ControlTarget:
    pid: int = 0
    process_name: str = ""
    window_title: str = ""

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
        }


@dataclasses.dataclass(frozen=True)
class ControlElementSnapshot:
    control_type: str = ""
    name: str = ""
    automation_id: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    value_preview: str = ""

    def to_dict(self) -> dict:
        return {
            "control_type": self.control_type,
            "name": self.name,
            "automation_id": self.automation_id,
            "rect": list(self.rect),
            "value_preview": _clip(self.value_preview),
        }


@dataclasses.dataclass(frozen=True)
class TextHit:
    source: str
    text_preview: str
    control_type: str = ""
    automation_id: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "text_preview": _clip(self.text_preview),
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "rect": list(self.rect),
        }


@dataclasses.dataclass(frozen=True)
class InputActionOptions:
    clear_before: bool = True
    clear_after: bool = True
    submit: bool = False
    allow_submit: bool = False
    allow_foreground_interaction: bool = True
    methods: tuple[str, ...] = ("set_text", "clipboard_paste", "type_text")


@dataclasses.dataclass(frozen=True)
class InputActionReport:
    target: ControlTarget
    text: str
    ok: bool
    control_attempts: int
    selected_element: Optional[ControlElementSnapshot] = None
    write_method: str = ""
    token_visible_after_write: bool = False
    token_visible_after_clear: Optional[bool] = None
    hits_after_write: tuple[TextHit, ...] = ()
    hits_after_clear: tuple[TextHit, ...] = ()
    submitted: bool = False
    foreground_interaction_allowed: bool = True
    foreground_required: bool = False
    error: str = ""
    steps: tuple[str, ...] = ()
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "application-control-input-action"

    @property
    def safety_mode(self) -> str:
        if self.submitted:
            return "submit_write_verify"
        if not self.foreground_interaction_allowed:
            if self.token_visible_after_clear is None:
                return "background_semantic_write_verify"
            return "background_semantic_write_verify_clear"
        if self.token_visible_after_clear is None:
            return "non_submit_write_verify"
        return "non_submit_write_verify_clear"

    @property
    def control_allowed(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "target": self.target.to_dict(),
            "text_preview": _clip(self.text),
            "ok": self.ok,
            "selected_element": (
                self.selected_element.to_dict() if self.selected_element else None
            ),
            "write_method": self.write_method,
            "token_visible_after_write": self.token_visible_after_write,
            "token_visible_after_clear": self.token_visible_after_clear,
            "hit_count_after_write": len(self.hits_after_write),
            "hits_after_write": [hit.to_dict() for hit in self.hits_after_write],
            "hit_count_after_clear": len(self.hits_after_clear),
            "hits_after_clear": [hit.to_dict() for hit in self.hits_after_clear],
            "submitted": self.submitted,
            "foreground_interaction_allowed": self.foreground_interaction_allowed,
            "foreground_required": self.foreground_required,
            "error": self.error,
            "steps": list(self.steps),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class InputAutomationBackend(Protocol):
    def find_input(self, target: ControlTarget) -> object:
        ...

    def snapshot_element(self, element: object) -> ControlElementSnapshot:
        ...

    def focus_window(self, target: ControlTarget) -> None:
        ...

    def focus_input(self, element: object) -> None:
        ...

    def clear_input(self, element: object) -> None:
        ...

    def force_clear_input(self, element: object) -> bool:
        ...

    def set_text(self, element: object, text: str) -> bool:
        ...

    def paste_text(self, element: object, text: str) -> bool:
        ...

    def type_text(self, element: object, text: str) -> bool:
        ...

    def visible_text_hits(self, target: ControlTarget, token: str) -> tuple[TextHit, ...]:
        ...

    def restore_clipboard(self) -> None:
        ...


class ApplicationControlBus:
    """Execute guarded UI input actions with action-after verification."""

    def __init__(self, backend: InputAutomationBackend):
        self._backend = backend

    def write_text(
        self,
        target: ControlTarget,
        text: str,
        options: InputActionOptions | None = None,
    ) -> InputActionReport:
        opts = options or InputActionOptions()
        started = time.perf_counter()
        steps: list[str] = []
        attempts = 0
        selected: Optional[ControlElementSnapshot] = None
        write_method = ""
        hits_after_write: tuple[TextHit, ...] = ()
        hits_after_clear: tuple[TextHit, ...] = ()
        token_visible_after_clear: Optional[bool] = None

        if opts.submit and not opts.allow_submit:
            return self._report(
                target,
                text,
                started,
                ok=False,
                control_attempts=0,
                error="submit_not_allowed",
            )
        if opts.submit:
            return self._report(
                target,
                text,
                started,
                ok=False,
                control_attempts=0,
                error="submit_not_implemented",
                foreground_interaction_allowed=opts.allow_foreground_interaction,
            )

        try:
            element = self._backend.find_input(target)
            if element is None:
                raise RuntimeError("input_not_found")
            selected = self._backend.snapshot_element(element)
            steps.append("input_found")

            if opts.allow_foreground_interaction:
                self._backend.focus_window(target)
                steps.append("window_focused")
                self._backend.focus_input(element)
                steps.append("input_focused")

            if opts.clear_before and opts.allow_foreground_interaction:
                self._backend.clear_input(element)
                steps.append("cleared_before")

            for method in _select_methods(opts.methods, opts.allow_foreground_interaction):
                attempts += 1
                if not self._execute_method(method, element, text):
                    steps.append(f"{method}:failed")
                    continue
                steps.append(f"{method}:executed")
                hits_after_write = self._backend.visible_text_hits(target, text)
                if hits_after_write:
                    write_method = method
                    steps.append(f"{method}:verified")
                    break
                steps.append(f"{method}:not_verified")

            token_visible_after_write = bool(hits_after_write)
            error = "" if token_visible_after_write else "write_not_verified"
            foreground_required = False
            if not token_visible_after_write and not opts.allow_foreground_interaction:
                error = "foreground_required"
                foreground_required = True

            if opts.clear_after:
                if opts.allow_foreground_interaction:
                    self._backend.focus_input(element)
                    self._backend.clear_input(element)
                    steps.append("cleared_after")
                else:
                    self._backend.set_text(element, "")
                    steps.append("background_cleared_after")
                hits_after_clear = self._backend.visible_text_hits(target, text)
                token_visible_after_clear = bool(hits_after_clear)
                if token_visible_after_clear and opts.allow_foreground_interaction:
                    force_clear = getattr(self._backend, "force_clear_input", None)
                    if callable(force_clear):
                        self._backend.focus_input(element)
                        if force_clear(element):
                            steps.append("force_cleared_after")
                            hits_after_clear = self._backend.visible_text_hits(target, text)
                            token_visible_after_clear = bool(hits_after_clear)
                if token_visible_after_write and token_visible_after_clear:
                    error = "clear_not_verified"

            ok = token_visible_after_write and not bool(token_visible_after_clear)
            return self._report(
                target,
                text,
                started,
                ok=ok,
                control_attempts=attempts,
                selected_element=selected,
                write_method=write_method,
                token_visible_after_write=token_visible_after_write,
                token_visible_after_clear=token_visible_after_clear,
                hits_after_write=hits_after_write,
                hits_after_clear=hits_after_clear,
                foreground_interaction_allowed=opts.allow_foreground_interaction,
                foreground_required=foreground_required,
                error=error,
                steps=tuple(steps),
            )
        except Exception as exc:
            return self._report(
                target,
                text,
                started,
                ok=False,
                control_attempts=attempts,
                selected_element=selected,
                foreground_interaction_allowed=opts.allow_foreground_interaction,
                error=str(exc) or exc.__class__.__name__,
                steps=tuple(steps),
            )
        finally:
            try:
                self._backend.restore_clipboard()
            except Exception:
                pass

    def _execute_method(self, method: str, element: object, text: str) -> bool:
        if method == "set_text":
            return bool(self._backend.set_text(element, text))
        if method == "clipboard_paste":
            return bool(self._backend.paste_text(element, text))
        if method == "type_text":
            return bool(self._backend.type_text(element, text))
        raise ValueError(f"unsupported_input_method:{method}")

    @staticmethod
    def _report(
        target: ControlTarget,
        text: str,
        started: float,
        *,
        ok: bool,
        control_attempts: int,
        selected_element: Optional[ControlElementSnapshot] = None,
        write_method: str = "",
        token_visible_after_write: bool = False,
        token_visible_after_clear: Optional[bool] = None,
        hits_after_write: tuple[TextHit, ...] = (),
        hits_after_clear: tuple[TextHit, ...] = (),
        foreground_interaction_allowed: bool = True,
        foreground_required: bool = False,
        error: str = "",
        steps: tuple[str, ...] = (),
    ) -> InputActionReport:
        return InputActionReport(
            target=target,
            text=text,
            ok=ok,
            control_attempts=control_attempts,
            selected_element=selected_element,
            write_method=write_method,
            token_visible_after_write=token_visible_after_write,
            token_visible_after_clear=token_visible_after_clear,
            hits_after_write=hits_after_write,
            hits_after_clear=hits_after_clear,
            foreground_interaction_allowed=foreground_interaction_allowed,
            foreground_required=foreground_required,
            error=error,
            steps=steps,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class PywinautoUIABackend:
    """pywinauto implementation for UIA-backed input control."""

    def __init__(self, backend: str = "uia"):
        self._backend = backend
        self._apps: dict[int, object] = {}
        self._clipboard_captured = False
        self._clipboard_text = ""

    def find_input(self, target: ControlTarget) -> object:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        app = self._app(target)
        element = SteerOperator.find_chat_input(app, target.window_title)
        if element is None:
            raise RuntimeError("input_not_found")
        return element

    def snapshot_element(self, element: object) -> ControlElementSnapshot:
        return ControlElementSnapshot(
            control_type=_safe_element_attr(element, "control_type"),
            name=_safe_element_attr(element, "name"),
            automation_id=_safe_element_attr(element, "automation_id"),
            rect=_safe_rect(element),
            value_preview=_read_element_text(element),
        )

    def focus_window(self, target: ControlTarget) -> None:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        windows = SteerOperator._ordered_windows(self._app(target), target.window_title)
        if windows:
            SteerOperator._focus_window(windows[0])

    def focus_input(self, element: object) -> None:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        SteerOperator._focus_input(element)

    def clear_input(self, element: object) -> None:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        SteerOperator._clear_input(element)

    def force_clear_input(self, element: object) -> bool:
        for clear_action in (
            self._send_keyboard_clear,
            lambda: element.type_keys("^a{BACKSPACE}", set_foreground=True, pause=0.02),
        ):
            try:
                clear_action()
                return True
            except Exception:
                continue
        return False

    def set_text(self, element: object, text: str) -> bool:
        try:
            element.set_edit_text(text)
            return True
        except Exception:
            return False

    def paste_text(self, element: object, text: str) -> bool:
        try:
            import pyperclip
            from pywinauto.keyboard import send_keys

            self._capture_clipboard()
            pyperclip.copy(text)
            send_keys("^v", pause=0.02)
            return True
        except Exception:
            return False

    def type_text(self, element: object, text: str) -> bool:
        try:
            from pywinauto.keyboard import send_keys

            send_keys(text, with_spaces=True, pause=0.01)
            return True
        except Exception:
            try:
                element.type_keys(text, with_spaces=True, set_foreground=True, pause=0.01)
                return True
            except Exception:
                return False

    def visible_text_hits(self, target: ControlTarget, token: str) -> tuple[TextHit, ...]:
        from openwukong.supervisor.agent_supervisor import SteerOperator

        needle = str(token or "").lower()
        if not needle:
            return ()
        hits: list[TextHit] = []
        app = self._app(target)
        for win in SteerOperator._ordered_windows(app, target.window_title)[:3]:
            try:
                title = win.window_text() or ""
                if needle in title.lower():
                    hits.append(TextHit(source="window_title", text_preview=title))
                for descendant in win.descendants():
                    hits.extend(_hits_for_element(descendant, needle))
            except Exception:
                continue
        return tuple(hits)

    def restore_clipboard(self) -> None:
        if not self._clipboard_captured:
            return
        try:
            import pyperclip

            pyperclip.copy(self._clipboard_text)
        finally:
            self._clipboard_captured = False
            self._clipboard_text = ""

    def _app(self, target: ControlTarget) -> object:
        if not target.pid:
            raise ValueError("pid_required")
        if target.pid not in self._apps:
            from pywinauto.application import Application

            self._apps[target.pid] = Application(backend=self._backend).connect(
                process=target.pid
            )
        return self._apps[target.pid]

    def _capture_clipboard(self) -> None:
        if self._clipboard_captured:
            return
        import pyperclip

        self._clipboard_text = pyperclip.paste()
        self._clipboard_captured = True

    @staticmethod
    def _send_keyboard_clear() -> None:
        from pywinauto.keyboard import send_keys

        send_keys("^a{BACKSPACE}", pause=0.02)


def _normalize_methods(methods: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for method in methods or ():
        item = str(method or "").strip()
        if item and item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)


def _select_methods(
    methods: Iterable[str],
    allow_foreground_interaction: bool,
) -> tuple[str, ...]:
    selected = _normalize_methods(methods)
    if allow_foreground_interaction:
        return selected
    return tuple(method for method in selected if method in {"set_text"})


def _hits_for_element(element: object, needle: str) -> list[TextHit]:
    hits: list[TextHit] = []
    for source, text in (
        ("name", _safe_element_attr(element, "name")),
        ("value_preview", _read_element_text(element)),
        ("legacy", _read_legacy_value(element)),
    ):
        if text and needle in text.lower():
            hits.append(
                TextHit(
                    source=source,
                    text_preview=text,
                    control_type=_safe_element_attr(element, "control_type"),
                    automation_id=_safe_element_attr(element, "automation_id"),
                    rect=_safe_rect(element),
                )
            )
    return hits


def _safe_element_attr(element: object, attr: str) -> str:
    try:
        return str(getattr(element.element_info, attr) or "")
    except Exception:
        return ""


def _read_element_text(element: object) -> str:
    for reader in (
        lambda: element.window_text(),
        lambda: element.text_block(),
        lambda: _read_legacy_value(element),
    ):
        try:
            value = reader() or ""
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def _read_legacy_value(element: object) -> str:
    try:
        legacy = element.legacy_properties()
        if isinstance(legacy, dict):
            return str(legacy.get("Value") or legacy.get("Name") or "")
        return str(legacy or "")
    except Exception:
        return ""


def _safe_rect(element: object) -> tuple[int, int, int, int]:
    try:
        rect = element.rectangle()
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return (0, 0, 0, 0)


def _clip(value: str, limit: int = 500) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]
