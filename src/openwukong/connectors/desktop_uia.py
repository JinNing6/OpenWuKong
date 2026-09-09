# -*- coding: utf-8 -*-
"""Policy-bound general Windows UI Automation connector.

The action vocabulary follows the useful low-level portion of Microsoft UFO²:
control inventory, semantic UIA patterns, screenshots, and explicit foreground
pointer/keyboard primitives. OpenWukong remains responsible for routing,
approval, ownership, side-effect policy, and post-action evidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Mapping, Optional

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.uia.controller import UIAController
from openwukong.uia.element_finder import ElementInfo


_READ_ACTIONS = {
    "inspect_controls",
    "read_text",
    "screenshot",
    "wait",
    "wait_for_element",
}
_SEMANTIC_ACTIONS = {"invoke", "select", "set_value", "toggle"}
_FOREGROUND_ACTIONS = {
    "click",
    "click_coordinates",
    "double_click",
    "drag",
    "focus",
    "key_press",
    "scroll",
    "type_keys",
}
_ACTION_ALIASES = {
    "get_controls": "inspect_controls",
    "inspect": "inspect_controls",
    "read": "read_text",
    "screenshot_window": "screenshot",
    "set_edit_text": "set_value",
    "type_text": "set_value",
    "write_text": "set_value",
    "click_semantic": "invoke",
    "launch_app": "launch_application",
    "start_application": "launch_application",
}

DEFAULT_LAUNCH_ALLOWLIST = {
    "calc": "calc.exe",
    "calc.exe": "calc.exe",
    "calculator": "calc.exe",
    "mspaint": "mspaint.exe",
    "mspaint.exe": "mspaint.exe",
    "notepad": "notepad.exe",
    "notepad.exe": "notepad.exe",
}


class DesktopUIAConnector(SessionConnector):
    """Generic UIA executor that never chooses its own safety route."""

    connector_id = "desktop-uia"
    display_name = "Windows UIA General Operations"
    route_ids = (
        "desktop-app-launch",
        "uia-semantic",
        "uia-structural",
        "uia-structural-observe",
        "uia-window-observe",
    )

    def __init__(
        self,
        *,
        controller_factory: Callable[[], UIAController] = UIAController,
        foreground_reader: Optional[Callable[[], int]] = None,
        launcher: Optional[Callable[[list[str]], object]] = None,
        executable_resolver: Optional[Callable[[str], Optional[str]]] = None,
        launch_allowlist: Optional[Mapping[str, str]] = None,
    ):
        self._controller_factory = controller_factory
        self._foreground_reader = foreground_reader or _foreground_hwnd
        self._launcher = launcher or _launch_process
        self._executable_resolver = executable_resolver or shutil.which
        source = DEFAULT_LAUNCH_ALLOWLIST if launch_allowlist is None else launch_allowlist
        self._launch_allowlist = {
            str(key or "").strip().casefold(): str(value or "").strip()
            for key, value in source.items()
            if str(key or "").strip() and str(value or "").strip()
        }

    def supports_target(self, target: ConnectorTarget) -> bool:
        if int(target.pid or 0) > 0:
            return True
        return _launch_key(target.process_name) in self._launch_allowlist

    def match_score(self, target: ConnectorTarget) -> int:
        return 25 if self.supports_target(target) else -1

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        if route_id == "desktop-app-launch":
            return _launch_key(target.process_name) in self._launch_allowlist
        return int(target.pid or 0) > 0

    def read_conversation(self, target: ConnectorTarget) -> str:
        intent = _SimpleIntent("inspect_controls", parameters={"max_results": 100})
        result = self.execute_action(target, intent)
        if not result.success:
            return ""
        return json.dumps(result.payload or {}, ensure_ascii=False, sort_keys=True)

    def probe_target(self, target: ConnectorTarget):
        """Build a read-only accessibility snapshot for route selection."""
        from openwukong.evaluation.accessibility_probe import (
            AccessibilityElementSnapshot,
            AccessibilityWindowSnapshot,
        )

        controller = self._controller_factory()
        try:
            process = controller.connect_to(int(target.pid))
            _verify_process_identity(process, target)
            bound_window = controller.bind_window(target.window_title)
            actual_window_title = target.window_title
            try:
                actual_window_title = str(bound_window.window_text() or actual_window_title)
            except Exception:
                pass
            controls = controller.find_controls("", max_results=500)
            elements = tuple(
                AccessibilityElementSnapshot(
                    control_type=item.control_type,
                    name=item.name,
                    automation_id=item.automation_id,
                    value_preview=(
                        "[redacted]"
                        if bool(getattr(item, "is_password", False))
                        else str(item.value or "")[:120]
                    ),
                    rect=tuple(item.rect),
                    is_enabled=bool(item.is_enabled),
                    patterns=tuple(getattr(item, "patterns", ()) or ()),
                )
                for item in controls
            )
            return AccessibilityWindowSnapshot(
                pid=int(target.pid),
                process_name=target.process_name or str(getattr(process, "name", "") or ""),
                window_title=actual_window_title,
                elements=elements,
            )
        except Exception as exc:
            return AccessibilityWindowSnapshot(
                pid=int(target.pid or 0),
                process_name=target.process_name,
                window_title=target.window_title,
                elements=(),
                scan_error=_error_code(exc),
            )
        finally:
            try:
                controller.disconnect()
            except Exception:
                pass

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del target, message, cooldown
        return ConnectorActionResult(
            success=False,
            connector_id=self.connector_id,
            action="send_message",
            error="desktop_uia_requires_typed_intent",
        )

    def execute_action(
        self,
        target: ConnectorTarget,
        intent: object,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        action = _normalized_action(getattr(intent, "action", ""))
        parameters = _parameters(intent)
        if action == "launch_application":
            return self._launch_application(target, intent, parameters)
        if action not in _READ_ACTIONS | _SEMANTIC_ACTIONS | _FOREGROUND_ACTIONS:
            return self._failure(action, "unsupported_desktop_uia_action")
        if int(target.pid or 0) <= 0:
            return self._failure(action, "desktop_uia_target_pid_required")
        if action in (_SEMANTIC_ACTIONS | _FOREGROUND_ACTIONS) and not str(
            target.window_title or ""
        ).strip():
            return self._failure(action, "desktop_uia_target_window_title_required")

        before = self._read_foreground()
        controller = self._controller_factory()
        try:
            process = controller.connect_to(int(target.pid))
            _verify_process_identity(process, target)
            controller.bind_window(target.window_title)
            payload = self._execute_connected(
                controller,
                target,
                intent,
                action,
                parameters,
            )
        except Exception as exc:
            return self._failure(
                action,
                _error_code(exc),
                payload={
                    "target_pid": int(target.pid),
                    "target_process_name": target.process_name,
                    "target_window_title": target.window_title,
                },
            )
        finally:
            try:
                controller.disconnect()
            except Exception:
                pass

        after = self._read_foreground()
        payload.update(_focus_evidence(before, after))
        ok = bool(payload.pop("_ok", False))
        error = str(payload.pop("_error", "") or "")
        return ConnectorActionResult(
            success=ok,
            connector_id=self.connector_id,
            action=action,
            action_key=_action_key(target, action, payload),
            payload=payload,
            error=error,
        )

    def _execute_connected(
        self,
        controller: UIAController,
        target: ConnectorTarget,
        intent: object,
        action: str,
        parameters: dict,
    ) -> dict:
        payload = _base_payload(target, action)

        if action == "inspect_controls":
            limit = _bounded_int(parameters.get("max_results", 100), 1, 500)
            control_type = str(parameters.get("control_type", "") or "").strip()
            controls = controller.find_controls(control_type, max_results=limit)
            payload.update(
                _ok_payload(
                    decision="desktop_uia_controls_inspected",
                    controls=[_element_dict(item) for item in controls],
                    control_count=len(controls),
                    control_attempts=0,
                )
            )
            return payload

        if action == "wait":
            duration = _bounded_float(parameters.get("seconds", 0.5), 0.0, 30.0)
            time.sleep(duration)
            payload.update(
                _ok_payload(
                    decision="desktop_uia_wait_completed",
                    waited_seconds=duration,
                    control_attempts=0,
                )
            )
            return payload

        if action == "wait_for_element":
            timeout = _bounded_float(parameters.get("timeout", 10.0), 0.0, 30.0)
            interval = _bounded_float(parameters.get("interval", 0.25), 0.05, 2.0)
            deadline = time.monotonic() + timeout
            element = None
            while time.monotonic() <= deadline:
                try:
                    element = _locate(controller, target, intent, parameters)
                    break
                except LookupError:
                    time.sleep(interval)
            if element is None:
                return _failed_payload(payload, "desktop_uia_element_wait_timeout")
            payload.update(
                _ok_payload(
                    decision="desktop_uia_element_ready",
                    element=_element_dict(element),
                    control_attempts=0,
                )
            )
            return payload

        locator_required = action in {
            "click",
            "double_click",
            "focus",
            "invoke",
            "read_text",
            "select",
            "set_value",
            "toggle",
            "type_keys",
        } or (action == "screenshot" and _has_locator(intent, parameters))
        element = (
            _locate(controller, target, intent, parameters)
            if locator_required
            else None
        )
        if element is not None:
            payload["element"] = _element_dict(element)
            if bool(getattr(element, "is_password", False)):
                return _failed_payload(payload, "desktop_uia_password_control_blocked")

        if action == "read_text":
            payload.update(
                _ok_payload(
                    decision="desktop_uia_text_read",
                    readback_text=controller.read_value(element),
                    control_attempts=0,
                )
            )
            return payload

        if action == "screenshot":
            path = _validated_artifact_path(target, parameters)
            ok = (
                controller.screenshot_element(element, str(path))
                if element is not None
                else controller.screenshot_window(str(path))
            )
            if not ok:
                return _failed_payload(payload, "desktop_uia_screenshot_failed")
            payload.update(
                _ok_payload(
                    decision="desktop_uia_screenshot_captured",
                    screenshot_path=str(path),
                    screenshot_count=1,
                    control_attempts=0,
                )
            )
            return payload

        if action == "set_value":
            value = str(getattr(intent, "value", "") or getattr(intent, "text", "") or "")
            ok, readback = controller.set_value(element, value)
            payload.update(
                {
                    "uia_value_set_attempts": 1,
                    "readback_text": readback,
                    "control_attempts": 1,
                }
            )
            if not ok:
                return _failed_payload(payload, "desktop_uia_value_readback_mismatch")
            payload.update(_ok_payload(decision="desktop_uia_value_set_verified"))
            return payload

        if action in {"invoke", "select", "toggle"}:
            method = getattr(controller, action)
            payload["control_attempts"] = 1
            payload[f"uia_{action}_attempts"] = 1
            if not method(element):
                return _failed_payload(payload, f"desktop_uia_{action}_failed")
            payload.update(_ok_payload(decision=f"desktop_uia_{action}_executed"))
            return payload

        _require_foreground(intent)
        payload.update(_foreground_attempt_payload(action))

        if action in {"click", "double_click"}:
            ok = controller.click_input(element, double=action == "double_click")
        elif action == "click_coordinates":
            x, y = _point(controller, parameters, "")
            payload["coordinates"] = [x, y]
            ok = controller.click_coordinates(
                x,
                y,
                double=bool(parameters.get("double", False)),
            )
        elif action == "drag":
            start = _point(controller, parameters, "start_")
            end = _point(controller, parameters, "end_")
            payload["start"] = list(start)
            payload["end"] = list(end)
            ok = controller.drag(
                start,
                end,
                duration=_bounded_float(parameters.get("duration", 0.5), 0.0, 5.0),
            )
        elif action == "scroll":
            direction = str(parameters.get("direction", "down") or "down").casefold()
            if direction not in {"down", "up"}:
                raise ValueError("desktop_uia_scroll_direction_invalid")
            amount = _bounded_int(parameters.get("amount", 3), 1, 120)
            wheel_dist = amount if direction == "up" else -amount
            coordinates = None
            if "x" in parameters or "y" in parameters:
                coordinates = _point(controller, parameters, "")
            payload["wheel_dist"] = wheel_dist
            ok = controller.scroll(wheel_dist, coordinates=coordinates)
        elif action == "type_keys":
            keys = str(parameters.get("keys", "") or getattr(intent, "text", "") or "")
            if not keys:
                raise ValueError("desktop_uia_keys_required")
            ok = controller.type_keys(
                element,
                keys,
                clear_first=bool(parameters.get("clear_first", False)),
            )
        elif action == "key_press":
            keys = str(parameters.get("keys", "") or "").strip()
            if not keys:
                raise ValueError("desktop_uia_keys_required")
            ok = controller.key_press(keys)
        elif action == "focus":
            ok = controller.focus(element)
        else:
            ok = False

        if not ok:
            return _failed_payload(payload, f"desktop_uia_{action}_failed")
        payload.update(_ok_payload(decision=f"desktop_uia_{action}_executed"))
        return payload

    def _launch_application(
        self,
        target: ConnectorTarget,
        intent: object,
        parameters: dict,
    ) -> ConnectorActionResult:
        action = "launch_application"
        try:
            _require_foreground(intent)
            requested = str(
                parameters.get("application", "") or target.process_name or ""
            ).strip()
            key = _launch_key(requested)
            executable = self._launch_allowlist.get(key, "")
            if not executable:
                raise PermissionError("desktop_uia_launch_not_allowlisted")
            target_executable = self._launch_allowlist.get(
                _launch_key(target.process_name),
                "",
            )
            if not target_executable or target_executable.casefold() != executable.casefold():
                raise PermissionError("desktop_uia_launch_target_mismatch")
            if parameters.get("arguments"):
                raise PermissionError("desktop_uia_launch_arguments_not_allowed")
            resolved = self._executable_resolver(executable)
            if not resolved:
                raise FileNotFoundError("desktop_uia_launch_executable_not_found")

            before = self._read_foreground()
            process = self._launcher([resolved])
            after = self._read_foreground()
            payload = _base_payload(target, action)
            payload.update(
                _ok_payload(
                    decision="desktop_uia_application_launched",
                    application=key,
                    executable_name=Path(resolved).name,
                    launched_pid=int(getattr(process, "pid", 0) or 0),
                    launch_attempts=1,
                    control_attempts=1,
                    foreground_takeover_attempts=1,
                )
            )
            payload.update(_focus_evidence(before, after))
            payload.pop("_ok", None)
            payload.pop("_error", None)
            return ConnectorActionResult(
                success=True,
                connector_id=self.connector_id,
                action=action,
                action_key=f"launch:{key}",
                payload=payload,
            )
        except Exception as exc:
            return self._failure(action, _error_code(exc))

    def _read_foreground(self) -> int:
        try:
            return int(self._foreground_reader() or 0)
        except Exception:
            return 0

    def _failure(
        self,
        action: str,
        error: str,
        *,
        payload: Optional[dict] = None,
    ) -> ConnectorActionResult:
        return ConnectorActionResult(
            success=False,
            connector_id=self.connector_id,
            action=action,
            payload=payload or {"control_attempts": 0},
            error=error,
        )


class _SimpleIntent:
    def __init__(self, action: str, *, parameters: Optional[dict] = None):
        self.action = action
        self.text = ""
        self.value = ""
        self.url = ""
        self.selector = ""
        self.parameters = dict(parameters or {})
        self.allow_foreground_interaction = False


def _normalized_action(value: object) -> str:
    action = str(value or "").strip().casefold()
    return _ACTION_ALIASES.get(action, action)


def _parameters(intent: object) -> dict:
    value = getattr(intent, "parameters", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _verify_process_identity(process: object, target: ConnectorTarget) -> None:
    actual_pid = int(getattr(process, "pid", 0) or 0)
    if actual_pid and actual_pid != int(target.pid):
        raise PermissionError("desktop_uia_target_pid_mismatch")
    actual_name = _launch_key(getattr(process, "name", ""))
    expected_name = _launch_key(target.process_name)
    if actual_name and expected_name and actual_name != expected_name:
        raise PermissionError("desktop_uia_target_process_mismatch")


def _locate(
    controller: UIAController,
    target: ConnectorTarget,
    intent: object,
    parameters: dict,
) -> ElementInfo:
    automation_id = str(parameters.get("automation_id", "") or "").strip()
    name = str(parameters.get("name", "") or "").strip()
    selector = str(getattr(intent, "selector", "") or "").strip()
    control_type = str(parameters.get("control_type", "") or "").strip()
    if not automation_id and not name and not selector:
        raise ValueError("desktop_uia_locator_required")

    controls = controller.find_controls(control_type, max_results=500)
    candidates = controls
    if automation_id:
        candidates = [item for item in candidates if item.automation_id == automation_id]
    if name:
        exact = bool(parameters.get("exact_name", True))
        folded = name.casefold()
        if exact:
            candidates = [item for item in candidates if item.name.casefold() == folded]
        else:
            candidates = [item for item in candidates if folded in item.name.casefold()]
    if selector and not automation_id and not name:
        by_id = [item for item in controls if item.automation_id == selector]
        candidates = by_id or [
            item for item in controls if item.name.casefold() == selector.casefold()
        ]

    title = target.window_title.casefold().strip()
    if title:
        exact_window = [item for item in candidates if item.window_title.casefold() == title]
        candidates = exact_window or [
            item for item in candidates if title in item.window_title.casefold()
        ]
    if not candidates:
        raise LookupError("desktop_uia_element_not_found")

    if "index" not in parameters and len(candidates) != 1:
        raise LookupError("desktop_uia_locator_ambiguous")
    try:
        index = int(parameters.get("index", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("desktop_uia_locator_index_invalid") from exc
    if index < 0 or index >= len(candidates):
        raise LookupError("desktop_uia_locator_index_out_of_range")
    return candidates[index]


def _has_locator(intent: object, parameters: dict) -> bool:
    return bool(
        str(getattr(intent, "selector", "") or "").strip()
        or str(parameters.get("automation_id", "") or "").strip()
        or str(parameters.get("name", "") or "").strip()
    )


def _point(
    controller: UIAController,
    parameters: dict,
    prefix: str,
) -> tuple[int, int]:
    x_key = f"{prefix}x"
    y_key = f"{prefix}y"
    if x_key not in parameters or y_key not in parameters:
        raise ValueError("desktop_uia_coordinates_required")
    x = float(parameters[x_key])
    y = float(parameters[y_key])
    space = str(parameters.get("coordinate_space", "relative") or "relative").casefold()
    if space == "absolute":
        return int(round(x)), int(round(y))
    if space != "relative" or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError("desktop_uia_relative_coordinates_invalid")
    left, top, right, bottom = controller.window_rectangle()
    width = max(1, right - left)
    height = max(1, bottom - top)
    return (
        min(right - 1, left + int(round(x * (width - 1)))),
        min(bottom - 1, top + int(round(y * (height - 1)))),
    )


def _validated_artifact_path(target: ConnectorTarget, parameters: dict) -> Path:
    root_text = str(parameters.get("artifact_root", "") or target.workspace_path or "").strip()
    if not root_text:
        raise PermissionError("desktop_uia_artifact_root_required")
    root = Path(root_text).expanduser().resolve()
    requested = str(parameters.get("path", "") or "").strip()
    if not requested:
        requested = str(Path(".openwukong") / "artifacts" / f"uia-{int(target.pid)}.png")
    path = Path(requested).expanduser()
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("desktop_uia_artifact_path_outside_root") from exc
    return resolved


def _element_dict(element: ElementInfo) -> dict:
    return {
        "control_type": element.control_type,
        "name": element.name,
        "automation_id": element.automation_id,
        "value": "[redacted]" if bool(getattr(element, "is_password", False)) else element.value,
        "rect": list(element.rect),
        "is_enabled": bool(element.is_enabled),
        "is_writable": bool(element.is_writable),
        "is_password": bool(getattr(element, "is_password", False)),
        "patterns": list(getattr(element, "patterns", ()) or ()),
        "pid": int(element.pid),
        "process_name": element.process_name,
        "window_title": element.window_title,
    }


def _base_payload(target: ConnectorTarget, action: str) -> dict:
    return {
        "decision": "desktop_uia_action_pending",
        "action": action,
        "target_pid": int(target.pid or 0),
        "target_process_name": target.process_name,
        "target_window_title": target.window_title,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "mouse_input_attempts": 0,
        "mouse_click_attempts": 0,
        "cursor_movement_attempts": 0,
        "foreground_takeover_attempts": 0,
        "clipboard_write_attempts": 0,
    }


def _ok_payload(**values) -> dict:
    return {"_ok": True, "_error": "", **values}


def _failed_payload(payload: dict, error: str) -> dict:
    payload.update({"_ok": False, "_error": error, "decision": "desktop_uia_action_failed"})
    return payload


def _foreground_attempt_payload(action: str) -> dict:
    payload = {
        "control_attempts": 1,
        "window_input_attempts": 1,
        "foreground_takeover_attempts": 1,
    }
    if action in {"click", "click_coordinates", "double_click", "drag", "scroll"}:
        payload["mouse_input_attempts"] = 1
        payload["cursor_movement_attempts"] = 1
    if action in {"click", "click_coordinates", "double_click"}:
        payload["mouse_click_attempts"] = 1
    if action in {"key_press", "type_keys"}:
        payload["keyboard_input_attempts"] = 1
    return payload


def _focus_evidence(before: int, after: int) -> dict:
    if before <= 0 or after <= 0:
        return {"foreground_focus_evidence_available": False}
    changed = before != after
    return {
        "foreground_focus_evidence_available": True,
        "foreground_hwnd_before": before,
        "foreground_hwnd_after": after,
        "foreground_changed": changed,
        "foreground_focus_stable": not changed,
    }


def _require_foreground(intent: object) -> None:
    if not bool(getattr(intent, "allow_foreground_interaction", False)):
        raise PermissionError("desktop_uia_foreground_permission_required")


def _action_key(target: ConnectorTarget, action: str, payload: dict) -> str:
    element = payload.get("element") if isinstance(payload.get("element"), dict) else {}
    locator = element.get("automation_id") or element.get("name") or "window"
    return f"{int(target.pid)}:{action}:{locator}"


def _launch_key(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    return text.casefold()


def _error_code(exc: Exception) -> str:
    text = str(exc or "").strip()
    if text.startswith("desktop_uia_"):
        return text
    return f"desktop_uia_{exc.__class__.__name__.casefold()}"


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    parsed = int(value)
    return max(minimum, min(parsed, maximum))


def _bounded_float(value: object, minimum: float, maximum: float) -> float:
    parsed = float(value)
    return max(minimum, min(parsed, maximum))


def _foreground_hwnd() -> int:
    try:
        import win32gui

        return int(win32gui.GetForegroundWindow() or 0)
    except Exception:
        return 0


def _launch_process(argv: list[str]):
    return subprocess.Popen(argv, shell=False)
