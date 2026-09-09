import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openwukong.connectors import ConnectorManager, ConnectorTarget
from openwukong.connectors.desktop_uia import DesktopUIAConnector
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)
from openwukong.uia.controller import UIAController
from openwukong.uia.element_finder import ElementFinder, ElementInfo


def _element(
    *,
    name: str,
    automation_id: str,
    control_type: str = "Edit",
    value: str = "",
    patterns=(),
) -> ElementInfo:
    return ElementInfo(
        control_type=control_type,
        name=name,
        automation_id=automation_id,
        value=value,
        rect=(120, 140, 360, 180),
        is_enabled=True,
        is_writable=control_type == "Edit",
        process_name="notepad.exe",
        pid=4242,
        window_title="Untitled - Notepad",
        patterns=tuple(patterns or (("Value", "Text") if control_type == "Edit" else ())),
    )


def _snapshot(
    process_name: str = "notepad.exe",
    *,
    pid: int = 4242,
) -> AccessibilityWindowSnapshot:
    return AccessibilityWindowSnapshot(
        pid=pid,
        process_name=process_name,
        window_title="Untitled - Notepad" if process_name == "notepad.exe" else "Codex",
        class_name="Notepad",
        elements=(
            AccessibilityElementSnapshot(
                control_type="Edit",
                name="Text editor",
                automation_id="editor",
                rect=(120, 140, 360, 180),
                is_enabled=True,
                patterns=("Value", "Text"),
            ),
            AccessibilityElementSnapshot(
                control_type="Button",
                name="Save",
                automation_id="save",
                rect=(120, 200, 180, 230),
                is_enabled=True,
                patterns=("Invoke",),
            ),
        ),
    )


class _FakeController:
    def __init__(self, controls=None):
        self.controls = list(
            [
                _element(name="Text editor", automation_id="editor"),
                _element(
                    name="Save",
                    automation_id="save",
                    control_type="Button",
                ),
            ]
            if controls is None
            else controls
        )
        self.calls = []

    def connect_to(self, pid):
        self.calls.append(("connect", pid))
        return SimpleNamespace(pid=pid, name="notepad.exe")

    def bind_window(self, title):
        self.calls.append(("bind", title))
        return object()

    def disconnect(self):
        self.calls.append(("disconnect",))

    def find_controls(self, control_type="", max_results=200):
        items = self.controls
        if control_type:
            items = [item for item in items if item.control_type == control_type]
        return items[:max_results]

    def read_value(self, element):
        return element.value

    def set_value(self, element, text):
        self.calls.append(("set_value", element.automation_id, text))
        return True, text

    def invoke(self, element):
        self.calls.append(("invoke", element.automation_id))
        return True

    def select(self, element):
        self.calls.append(("select", element.automation_id))
        return True

    def toggle(self, element):
        self.calls.append(("toggle", element.automation_id))
        return True

    def click_input(self, element, *, double=False):
        self.calls.append(("click", element.automation_id, double))
        return True

    def type_keys(self, element, keys, *, clear_first=False):
        self.calls.append(("type_keys", element.automation_id, keys, clear_first))
        return True

    def key_press(self, keys):
        self.calls.append(("key_press", keys))
        return True

    def focus(self, element):
        self.calls.append(("focus", element.automation_id))
        return True

    def click_coordinates(self, x, y, *, double=False):
        self.calls.append(("click_coordinates", x, y, double))
        return True

    def drag(self, start, end, *, duration=0.5):
        self.calls.append(("drag", start, end, duration))
        return True

    def scroll(self, wheel_dist, *, coordinates=None):
        self.calls.append(("scroll", wheel_dist, coordinates))
        return True

    def window_rectangle(self):
        return (100, 100, 500, 400)

    def screenshot_element(self, element, save_path):
        self.calls.append(("screenshot_element", element.automation_id, save_path))
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_bytes(b"png")
        return True

    def screenshot_window(self, save_path):
        self.calls.append(("screenshot_window", save_path))
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_bytes(b"png")
        return True


class _FakeWindow:
    def __init__(self, title):
        self._title = title

    def window_text(self):
        return self._title


class _FakeApplication:
    def __init__(self, titles):
        self._windows = [_FakeWindow(title) for title in titles]

    def top_window(self):
        return self._windows[0]

    def windows(self):
        return list(self._windows)


class _PasswordWrapper:
    def __init__(self):
        self.window_text_calls = 0
        self.element_info = SimpleNamespace(
            control_type="Edit",
            name="Password",
            automation_id="password",
            element=SimpleNamespace(CurrentIsPassword=True),
        )
        self.iface_value = SimpleNamespace(CurrentIsReadOnly=False)

    def window_text(self):
        self.window_text_calls += 1
        return "must-not-be-read"

    def rectangle(self):
        return SimpleNamespace(left=1, top=2, right=3, bottom=4)

    def is_enabled(self):
        return True


class DesktopUIAControllerSafetyTests(unittest.TestCase):
    def test_explicit_window_binding_rejects_ambiguous_partial_title(self):
        controller = UIAController.__new__(UIAController)
        controller._current_app = _FakeApplication(
            ["Draft - Notepad", "Notes - Notepad"]
        )
        controller._current_process = None
        controller._bound_window_title = "Notepad"

        with self.assertRaisesRegex(LookupError, "Ambiguous bound window title"):
            controller.get_window()

    def test_password_detection_does_not_read_the_control_value(self):
        wrapper = _PasswordWrapper()

        element = ElementFinder._extract_info(wrapper)

        self.assertTrue(element.is_password)
        self.assertEqual(element.value, "")
        self.assertFalse(element.is_writable)
        self.assertNotIn("Value", element.patterns)
        self.assertEqual(wrapper.window_text_calls, 0)


class DesktopUIAConnectorTests(unittest.TestCase):
    def _connector(self, controller, **kwargs):
        return DesktopUIAConnector(
            controller_factory=lambda: controller,
            foreground_reader=lambda: 101,
            **kwargs,
        )

    def test_inspect_controls_returns_serializable_inventory_without_input(self):
        controller = _FakeController()
        connector = self._connector(controller)

        result = connector.execute_action(
            ConnectorTarget(
                pid=4242,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
            ),
            ControlIntent(action="inspect_controls"),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["control_count"], 2)
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(result.payload["window_input_attempts"], 0)
        self.assertEqual(result.payload["controls"][0]["automation_id"], "editor")

    def test_set_value_uses_semantic_pattern_and_records_readback(self):
        controller = _FakeController()
        connector = self._connector(controller)

        result = connector.execute_action(
            ConnectorTarget(
                pid=4242,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
            ),
            ControlIntent(
                action="set_value",
                value="OPENWUKONG",
                parameters={"automation_id": "editor"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["readback_text"], "OPENWUKONG")
        self.assertEqual(result.payload["uia_value_set_attempts"], 1)
        self.assertEqual(result.payload["keyboard_input_attempts"], 0)
        self.assertIn(("set_value", "editor", "OPENWUKONG"), controller.calls)

    def test_ambiguous_locator_is_rejected_before_control(self):
        controls = [
            _element(name="Save", automation_id="save-1", control_type="Button"),
            _element(name="Save", automation_id="save-2", control_type="Button"),
        ]
        controller = _FakeController(controls)
        connector = self._connector(controller)

        result = connector.execute_action(
            ConnectorTarget(
                pid=4242,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
            ),
            ControlIntent(action="invoke", parameters={"name": "Save"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "desktop_uia_locator_ambiguous")
        self.assertFalse(any(call[0] == "invoke" for call in controller.calls))

    def test_pointer_action_requires_explicit_foreground_permission(self):
        controller = _FakeController()
        connector = self._connector(controller)

        result = connector.execute_action(
            ConnectorTarget(
                pid=4242,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
            ),
            ControlIntent(action="click", parameters={"automation_id": "save"}),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "desktop_uia_foreground_permission_required")
        self.assertFalse(any(call[0] == "click" for call in controller.calls))

    def test_write_action_requires_an_explicit_window_binding(self):
        controller = _FakeController()
        connector = self._connector(controller)

        result = connector.execute_action(
            ConnectorTarget(pid=4242, process_name="notepad.exe"),
            ControlIntent(
                action="set_value",
                value="OPENWUKONG",
                parameters={"automation_id": "editor"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "desktop_uia_target_window_title_required")
        self.assertEqual(controller.calls, [])

    def test_password_controls_are_redacted_and_cannot_be_read(self):
        password = _element(
            name="Password",
            automation_id="password",
            value="do-not-expose",
        )
        password.is_password = True
        controller = _FakeController([password])
        connector = self._connector(controller)
        target = ConnectorTarget(
            pid=4242,
            process_name="notepad.exe",
            window_title="Untitled - Notepad",
        )

        inventory = connector.execute_action(
            target,
            ControlIntent(action="inspect_controls"),
        )
        readback = connector.execute_action(
            target,
            ControlIntent(
                action="read_text",
                parameters={"automation_id": "password"},
            ),
        )

        self.assertEqual(inventory.payload["controls"][0]["value"], "[redacted]")
        self.assertFalse(readback.success)
        self.assertEqual(readback.error, "desktop_uia_password_control_blocked")

    def test_screenshot_path_must_stay_inside_artifact_root(self):
        controller = _FakeController()
        connector = self._connector(controller)
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            result = connector.execute_action(
                ConnectorTarget(
                    pid=4242,
                    process_name="notepad.exe",
                    window_title="Untitled - Notepad",
                    workspace_path=root,
                ),
                ControlIntent(
                    action="screenshot",
                    parameters={"path": str(Path(outside) / "capture.png")},
                ),
            )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "desktop_uia_artifact_path_outside_root")
        self.assertFalse(any(call[0].startswith("screenshot") for call in controller.calls))

    def test_screenshot_drag_scroll_and_keyboard_primitives_are_available(self):
        controller = _FakeController()
        connector = self._connector(controller)
        target = ConnectorTarget(
            pid=4242,
            process_name="notepad.exe",
            window_title="Untitled - Notepad",
        )

        with tempfile.TemporaryDirectory() as root:
            target = ConnectorTarget(
                pid=target.pid,
                process_name=target.process_name,
                window_title=target.window_title,
                workspace_path=root,
            )
            screenshot = connector.execute_action(
                target,
                ControlIntent(
                    action="screenshot",
                    parameters={"path": "artifacts/window.png"},
                ),
            )
            self.assertTrue(screenshot.success, screenshot.error)
            self.assertTrue(Path(screenshot.payload["screenshot_path"]).is_file())

        foreground_intents = (
            ControlIntent(
                action="click_coordinates",
                allow_foreground_interaction=True,
                parameters={"x": 0.5, "y": 0.5},
            ),
            ControlIntent(
                action="drag",
                allow_foreground_interaction=True,
                parameters={
                    "start_x": 0.2,
                    "start_y": 0.2,
                    "end_x": 0.8,
                    "end_y": 0.8,
                },
            ),
            ControlIntent(
                action="scroll",
                allow_foreground_interaction=True,
                parameters={"direction": "down", "amount": 4},
            ),
            ControlIntent(
                action="type_keys",
                text="hello",
                allow_foreground_interaction=True,
                parameters={"automation_id": "editor"},
            ),
            ControlIntent(
                action="key_press",
                allow_foreground_interaction=True,
                parameters={"keys": "{ENTER}"},
            ),
        )
        results = [connector.execute_action(target, intent) for intent in foreground_intents]

        self.assertTrue(all(result.success for result in results))
        self.assertTrue(all(result.payload["foreground_takeover_attempts"] == 1 for result in results))
        self.assertIn(("click_coordinates", 300, 250, False), controller.calls)
        self.assertIn(("scroll", -4, None), controller.calls)
        self.assertIn(("type_keys", "editor", "hello", False), controller.calls)
        self.assertIn(("key_press", "{ENTER}"), controller.calls)

    def test_invoke_select_and_toggle_use_semantic_methods(self):
        controls = [
            _element(name="Save", automation_id="save", control_type="Button"),
            _element(name="Choice", automation_id="choice", control_type="ListItem"),
            _element(name="Enabled", automation_id="enabled", control_type="CheckBox"),
        ]
        controller = _FakeController(controls)
        connector = self._connector(controller)
        target = ConnectorTarget(
            pid=4242,
            process_name="notepad.exe",
            window_title="Untitled - Notepad",
        )

        results = (
            connector.execute_action(
                target,
                ControlIntent(action="invoke", parameters={"automation_id": "save"}),
            ),
            connector.execute_action(
                target,
                ControlIntent(action="select", parameters={"automation_id": "choice"}),
            ),
            connector.execute_action(
                target,
                ControlIntent(action="toggle", parameters={"automation_id": "enabled"}),
            ),
        )

        self.assertTrue(all(result.success for result in results))
        self.assertIn(("invoke", "save"), controller.calls)
        self.assertIn(("select", "choice"), controller.calls)
        self.assertIn(("toggle", "enabled"), controller.calls)

    def test_launch_is_allowlisted_and_uses_argv_without_shell(self):
        calls = []

        def launcher(argv):
            calls.append(argv)
            return SimpleNamespace(pid=777)

        connector = DesktopUIAConnector(
            foreground_reader=lambda: 101,
            launcher=launcher,
            executable_resolver=lambda name: f"C:/Windows/System32/{name}",
        )
        result = connector.execute_action(
            ConnectorTarget(process_name="notepad.exe"),
            ControlIntent(
                action="launch_application",
                allow_foreground_interaction=True,
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(calls, [["C:/Windows/System32/notepad.exe"]])
        self.assertEqual(result.payload["launched_pid"], 777)
        self.assertEqual(result.payload["launch_attempts"], 1)

    def test_launch_application_must_match_the_approved_target(self):
        calls = []
        connector = DesktopUIAConnector(
            foreground_reader=lambda: 101,
            launcher=lambda argv: calls.append(argv),
            executable_resolver=lambda name: f"C:/Windows/System32/{name}",
        )

        result = connector.execute_action(
            ConnectorTarget(process_name="notepad.exe"),
            ControlIntent(
                action="launch_application",
                allow_foreground_interaction=True,
                parameters={"application": "mspaint.exe"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "desktop_uia_launch_target_mismatch")
        self.assertEqual(calls, [])


class DesktopUIAFabricIntegrationTests(unittest.TestCase):
    def test_raw_pid_target_is_read_only_probed_before_uia_routing(self):
        controller = _FakeController()
        connector = DesktopUIAConnector(
            controller_factory=lambda: controller,
            foreground_reader=lambda: 101,
        )
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        report = fabric.dispatch(
            ConnectorTarget(
                pid=4242,
                process_name="notepad.exe",
                window_title="Untitled - Notepad",
            ),
            ControlIntent(
                action="set_value",
                value="OPENWUKONG",
                parameters={"automation_id": "editor"},
            ),
        ).to_dict()

        self.assertEqual(report["decision"], "dispatch_connector")
        self.assertEqual(report["selected_route"], "uia-semantic")
        self.assertEqual(report["selected_connector_id"], "desktop-uia")
        self.assertIn(("connect", 4242), controller.calls)
        self.assertFalse(any(call[0] == "set_value" for call in controller.calls))

    def test_window_screenshot_remains_available_without_actionable_controls(self):
        controller = _FakeController([])
        connector = DesktopUIAConnector(
            controller_factory=lambda: controller,
            foreground_reader=lambda: 101,
        )
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        with tempfile.TemporaryDirectory() as root:
            report = fabric.execute(
                ConnectorTarget(
                    pid=4242,
                    process_name="notepad.exe",
                    window_title="Untitled - Notepad",
                    workspace_path=root,
                ),
                ControlIntent(
                    action="screenshot",
                    parameters={"path": "artifacts/window.png"},
                ),
                allow_control=True,
            ).to_dict()

        self.assertTrue(report["ok"], report["error"])
        self.assertEqual(report["selected_route"], "uia-window-observe")
        self.assertEqual(report["selected_connector_id"], "desktop-uia")

    def test_semantic_action_executes_through_control_fabric(self):
        controller = _FakeController()
        connector = DesktopUIAConnector(
            controller_factory=lambda: controller,
            foreground_reader=lambda: 101,
        )
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        report = fabric.execute(
            _snapshot(),
            ControlIntent(
                action="set_value",
                value="OPENWUKONG",
                parameters={"automation_id": "editor"},
            ),
            allow_control=True,
        ).to_dict()

        self.assertTrue(report["ok"], report["error"])
        self.assertEqual(report["selected_route"], "uia-semantic")
        self.assertEqual(report["selected_connector_id"], "desktop-uia")
        self.assertEqual(report["action_report"]["action"], "set_value")
        self.assertEqual(
            report["action_report"]["payload"]["decision"],
            "desktop_uia_value_set_verified",
        )
        self.assertTrue(report["no_foreground_validation"]["ok"])

    def test_foreground_click_requires_then_consumes_matching_approval(self):
        controller = _FakeController()
        connector = DesktopUIAConnector(
            controller_factory=lambda: controller,
            foreground_reader=lambda: 101,
        )
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )
        intent = ControlIntent(
            action="click",
            allow_foreground_interaction=True,
            parameters={"automation_id": "save"},
        )

        blocked = fabric.execute(_snapshot(), intent, allow_control=True).to_dict()
        self.assertFalse(blocked["ok"])
        self.assertEqual(
            blocked["transport_gate_decision"],
            "blocked_foreground_takeover_required",
        )
        self.assertFalse(any(call[0] == "click" for call in controller.calls))

        approval = dict(blocked["foreground_takeover_request"])
        approval["status"] = "approved"
        wrong_target = dict(approval)
        wrong_target["target_window_title"] = "Another window"
        rejected = fabric.execute(
            _snapshot(),
            intent,
            allow_control=True,
            foreground_takeover_approval=wrong_target,
        ).to_dict()
        self.assertFalse(rejected["ok"])
        self.assertEqual(
            rejected["transport_gate_error"],
            "foreground_takeover_target_binding_mismatch",
        )
        self.assertFalse(any(call[0] == "click" for call in controller.calls))

        changed_locator = fabric.execute(
            _snapshot(),
            ControlIntent(
                action="click",
                allow_foreground_interaction=True,
                parameters={"automation_id": "editor"},
            ),
            allow_control=True,
            foreground_takeover_approval=approval,
        ).to_dict()
        self.assertFalse(changed_locator["ok"])
        self.assertEqual(
            changed_locator["transport_gate_error"],
            "foreground_takeover_target_binding_mismatch",
        )

        changed_pid = fabric.execute(
            _snapshot(pid=4343),
            intent,
            allow_control=True,
            foreground_takeover_approval=approval,
        ).to_dict()
        self.assertFalse(changed_pid["ok"])
        self.assertEqual(
            changed_pid["transport_gate_error"],
            "foreground_takeover_target_binding_mismatch",
        )

        executed = fabric.execute(
            _snapshot(),
            intent,
            allow_control=True,
            foreground_takeover_approval=approval,
        ).to_dict()

        self.assertTrue(executed["ok"], executed["error"])
        self.assertEqual(
            executed["transport_gate_decision"],
            "allow_approved_foreground_takeover",
        )
        self.assertIn(("click", "save", False), controller.calls)
        self.assertTrue(executed["no_foreground_validation"]["ok"])

    def test_agent_app_cannot_force_uia_route_past_policy(self):
        connector = DesktopUIAConnector(
            controller_factory=lambda: _FakeController(),
            foreground_reader=lambda: 101,
        )
        fabric = ControlFabric(connector_manager=ConnectorManager([connector]))

        report = fabric.dispatch(
            _snapshot("codex.exe"),
            ControlIntent(
                action="set_value",
                value="must not run",
                preferred_route_id="uia-semantic",
                preferred_connector_id="desktop-uia",
                parameters={"automation_id": "editor"},
            ),
        ).to_dict()

        self.assertTrue(report["blocked"])
        self.assertEqual(report["reason"], "uia_route_not_allowed_by_policy")
        self.assertFalse(report["connector_ready"])

    def test_allowlisted_launch_is_integrated_with_foreground_gate(self):
        calls = []
        connector = DesktopUIAConnector(
            foreground_reader=lambda: 101,
            launcher=lambda argv: calls.append(argv) or SimpleNamespace(pid=777),
            executable_resolver=lambda name: f"C:/Windows/System32/{name}",
        )
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )
        target = ConnectorTarget(process_name="notepad.exe")
        intent = ControlIntent(
            action="launch_application",
            allow_foreground_interaction=True,
        )

        blocked = fabric.execute(target, intent, allow_control=True).to_dict()
        approval = dict(blocked["foreground_takeover_request"])
        approval["status"] = "approved"
        executed = fabric.execute(
            target,
            intent,
            allow_control=True,
            foreground_takeover_approval=approval,
        ).to_dict()

        self.assertTrue(executed["ok"], executed["error"])
        self.assertEqual(executed["selected_route"], "desktop-app-launch")
        self.assertEqual(executed["selected_connector_id"], "desktop-uia")
        self.assertEqual(calls, [["C:/Windows/System32/notepad.exe"]])


if __name__ == "__main__":
    unittest.main()
