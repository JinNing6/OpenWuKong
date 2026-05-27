import unittest

from openwukong.connectors import (
    ConnectorActionResult,
    ConnectorManager,
    ConnectorTarget,
    SessionConnector,
    TerminalCommandConnector,
)
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements, *, pid: int = 2026):
    return AccessibilityWindowSnapshot(
        pid=pid,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=tuple(elements),
    )


class _FakeConnector(SessionConnector):
    connector_id = "ide-extension"
    display_name = "IDE Extension Bridge"

    def supports_target(self, target: ConnectorTarget) -> bool:
        return target.process_name.lower() == "cursor.exe"

    def read_conversation(self, target: ConnectorTarget) -> str:
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del target, cooldown
        return ConnectorActionResult(
            success=True,
            connector_id=self.connector_id,
            action="send_message",
            payload={"message": message},
        )


class ControlFabricTests(unittest.TestCase):
    def test_dispatch_plan_selects_available_connector_for_known_app_family(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([_FakeConnector()]))
        report = fabric.dispatch(
            _window(
                "Cursor.exe",
                "openwukong - Cursor",
                [_element("Document", name="editor", patterns=("Text",))],
                pid=50200,
            ),
            ControlIntent(action="send_message", text="OPENWUKONG"),
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-dispatch-plan")
        self.assertEqual(data["safety_mode"], "plan_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "dispatch_connector")
        self.assertEqual(data["execution_mode"], "connector")
        self.assertEqual(data["selected_route"], "ide-extension-connector")
        self.assertEqual(data["selected_connector_id"], "ide-extension")
        self.assertTrue(data["background_safe"])
        self.assertFalse(data["foreground_required"])

    def test_dispatch_plan_reports_connector_required_when_primary_connector_is_missing(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))
        report = fabric.dispatch(
            _window(
                "Cursor.exe",
                "openwukong - Cursor",
                [_element("Document", name="editor", patterns=("Text",))],
            ),
            ControlIntent(action="send_message", text="OPENWUKONG"),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "connector_required")
        self.assertEqual(data["execution_mode"], "none")
        self.assertEqual(data["selected_route"], "ide-extension-connector")
        self.assertEqual(data["selected_connector_id"], "")
        self.assertIn("no_connector_available", data["reason"])
        self.assertTrue(data["background_safe"])
        self.assertFalse(data["foreground_required"])

    def test_dispatch_plan_uses_background_uia_for_semantic_generic_window(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))
        report = fabric.dispatch(
            _window(
                "notepad.exe",
                "Untitled - Notepad",
                [
                    _element("Edit", name="Text editor", patterns=("Value", "Text")),
                    _element("Button", name="Save", patterns=("Invoke",)),
                ],
            ),
            ControlIntent(action="write_text", text="OPENWUKONG"),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "dispatch_background_uia")
        self.assertEqual(data["execution_mode"], "background_uia")
        self.assertEqual(data["selected_route"], "uia-semantic")
        self.assertEqual(data["selected_connector_id"], "")
        self.assertTrue(data["background_safe"])
        self.assertFalse(data["foreground_required"])

    def test_dispatch_plan_requires_foreground_for_structural_input_when_allowed(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))
        report = fabric.dispatch(
            _window(
                "custom-electron.exe",
                "Custom Chat",
                [_element("Edit", name="", patterns=("Text",))],
            ),
            ControlIntent(
                action="write_text",
                text="OPENWUKONG",
                allow_foreground_interaction=True,
            ),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "dispatch_foreground_uia")
        self.assertEqual(data["execution_mode"], "foreground_uia")
        self.assertTrue(data["foreground_required"])
        self.assertFalse(data["background_safe"])

    def test_dispatch_plan_blocks_unsafe_window_even_when_foreground_is_allowed(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))
        report = fabric.dispatch(
            _window("Weixin.exe", "微信", []),
            ControlIntent(
                action="write_text",
                text="OPENWUKONG",
                allow_foreground_interaction=True,
            ),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["execution_mode"], "none")
        self.assertEqual(data["selected_route"], "app-native-bridge-required")
        self.assertTrue(data["blocked"])
        self.assertFalse(data["background_safe"])
        self.assertFalse(data["foreground_required"])

    def test_default_runtime_reports_installed_connector_without_ready_browser_session(self):
        fabric = ControlFabric.with_default_connectors()

        report = fabric.dispatch(
            ConnectorTarget(process_name="chrome.exe", window_title="Chrome"),
            ControlIntent(action="write_text", text="OPENWUKONG"),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "connector_required")
        self.assertEqual(data["execution_mode"], "none")
        self.assertEqual(data["selected_route"], "browser-devtools-or-extension")
        self.assertEqual(data["selected_connector_id"], "")
        self.assertEqual(data["candidate_connector_ids"], ["browser"])
        self.assertIn("browser", data["installed_connector_ids"])
        self.assertFalse(data["connector_ready"])
        self.assertIn("connector_installed_session_not_ready", data["reason"])

    def test_default_runtime_dispatches_browser_connector_when_debugger_url_is_available(self):
        fabric = ControlFabric.with_default_connectors()

        report = fabric.dispatch(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Chrome",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="write_text", text="OPENWUKONG"),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "dispatch_connector")
        self.assertEqual(data["execution_mode"], "connector")
        self.assertEqual(data["selected_connector_id"], "browser")
        self.assertTrue(data["connector_ready"])

    def test_runtime_dispatches_terminal_connector_only_for_bound_workspace_session(self):
        fabric = ControlFabric(
            connector_manager=ConnectorManager([TerminalCommandConnector()]),
            require_connector_session_ready=True,
        )

        missing_workspace = fabric.dispatch(
            ConnectorTarget(process_name="pwsh.exe", window_title="PowerShell"),
            ControlIntent(action="run_command", text="pwd"),
        ).to_dict()
        ready_workspace = fabric.dispatch(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(action="run_command", text="pwd"),
        ).to_dict()

        self.assertEqual(missing_workspace["decision"], "connector_required")
        self.assertFalse(missing_workspace["connector_ready"])
        self.assertEqual(ready_workspace["decision"], "dispatch_connector")
        self.assertEqual(ready_workspace["selected_connector_id"], "terminal")
        self.assertTrue(ready_workspace["connector_ready"])

    def test_runtime_keeps_ide_connector_required_until_bridge_url_exists(self):
        fabric = ControlFabric.with_default_connectors()

        missing_bridge = fabric.dispatch(
            ConnectorTarget(process_name="Cursor.exe", window_title="Cursor"),
            ControlIntent(action="send_message", text="OPENWUKONG"),
        ).to_dict()
        ready_bridge = fabric.dispatch(
            ConnectorTarget(
                process_name="Cursor.exe",
                window_title="Cursor",
                ide_bridge_url="http://127.0.0.1:8787",
            ),
            ControlIntent(action="send_message", text="OPENWUKONG"),
        ).to_dict()

        self.assertEqual(missing_bridge["decision"], "connector_required")
        self.assertEqual(missing_bridge["candidate_connector_ids"], ["ide-extension"])
        self.assertFalse(missing_bridge["connector_ready"])
        self.assertEqual(ready_bridge["decision"], "dispatch_connector")
        self.assertEqual(ready_bridge["selected_connector_id"], "ide-extension")
        self.assertTrue(ready_bridge["connector_ready"])

    def test_dispatch_blocks_available_connector_when_side_effect_requires_confirmation(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([_FakeConnector()]))
        report = fabric.dispatch(
            _window(
                "Cursor.exe",
                "openwukong - Cursor",
                [_element("Document", name="chat", patterns=("Text",))],
            ),
            ControlIntent(
                action="send_message",
                text="send this to a real chat",
                side_effect_policy=build_side_effect_policy(
                    blocked_effect_ids=("external_communication.send_message",),
                ),
            ),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "side_effect_confirmation_required")
        self.assertEqual(data["execution_mode"], "none")
        self.assertTrue(data["blocked"])
        self.assertEqual(data["selected_route"], "ide-extension-connector")
        self.assertEqual(data["reason"], "side_effect_confirmation_required")
        self.assertFalse(data["connector_ready"])
        self.assertEqual(
            data["side_effect_gate"]["confirmation_required_effect_ids"],
            ["external_communication.send_message"],
        )
        self.assertEqual(
            data["side_effect_gate"]["blocked_effect_categories"],
            ["external_communication"],
        )


if __name__ == "__main__":
    unittest.main()
