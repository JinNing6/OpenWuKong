import unittest

from openwukong.connectors import ConnectorManager, ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.transport_capability import build_transport_capability
from openwukong.connectors.route_policy import build_control_route_plan
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


def _window(process_name: str, title: str, elements=(), *, class_name: str = "Window"):
    return AccessibilityWindowSnapshot(
        pid=100,
        process_name=process_name,
        window_title=title,
        class_name=class_name,
        hwnd=200,
        elements=tuple(elements),
    )


class TransportCapabilityMatrixTests(unittest.TestCase):
    def test_browser_devtools_route_is_background_native_and_focus_safe(self):
        plan = build_control_route_plan(
            _window(
                "chrome.exe",
                "Search - Google Chrome",
                [_element("Edit", name="Search", patterns=("Value", "Text"))],
            )
        )

        capability = build_transport_capability(
            plan,
            ControlIntent(action="read_page"),
        ).to_dict()

        self.assertEqual(capability["mode"], "transport-capability")
        self.assertEqual(capability["capability_level"], "background-native")
        self.assertEqual(capability["selected_transport"], "chrome-devtools-protocol")
        self.assertTrue(capability["background_safe"])
        self.assertTrue(capability["can_execute_without_focus"])
        self.assertFalse(capability["foreground_required"])
        self.assertFalse(capability["requires_user_confirmation"])

    def test_app_native_bridge_route_is_background_native_transport_contract(self):
        plan = build_control_route_plan(
            _window(
                "Weixin.exe",
                "微信",
                [_element("Pane"), _element("TitleBar")],
            )
        )

        capability = build_transport_capability(
            plan,
            ControlIntent(action="send_message", text="probe"),
        ).to_dict()

        self.assertEqual(capability["app_family"], "im")
        self.assertEqual(capability["route_id"], "app-native-bridge-required")
        self.assertEqual(capability["capability_level"], "background-native")
        self.assertEqual(capability["selected_transport"], "agent-native-bridge")
        self.assertTrue(capability["background_safe"])
        self.assertFalse(capability["foreground_required"])
        self.assertTrue(capability["requires_user_confirmation"])
        self.assertIn("native_bridge_response", capability["verification_requirements"])

    def test_claude_process_only_routes_to_agent_app_native_bridge_required(self):
        plan = build_control_route_plan(_window("claude.exe", "claude.exe", []))

        capability = build_transport_capability(
            plan,
            ControlIntent(action="submit_task", text="probe"),
        ).to_dict()

        self.assertEqual(plan.app_family, "agent-app")
        self.assertEqual(plan.primary_route.route_id, "app-native-bridge-required")
        self.assertEqual(plan.control_decision, "block_until_deterministic_route")
        self.assertEqual(capability["route_id"], "app-native-bridge-required")
        self.assertEqual(capability["capability_level"], "background-native")
        self.assertEqual(capability["selected_transport"], "agent-native-bridge")
        self.assertTrue(capability["background_safe"])

    def test_structural_uia_read_is_background_read_only(self):
        plan = build_control_route_plan(
            _window(
                "reader.exe",
                "Reader",
                [_element("Document", name="Document", patterns=("Text",))],
            )
        )

        capability = build_transport_capability(
            plan,
            ControlIntent(action="read_text"),
        ).to_dict()

        self.assertEqual(capability["capability_level"], "background-read-only")
        self.assertEqual(capability["selected_transport"], "uia-tree-read")
        self.assertTrue(capability["background_safe"])
        self.assertTrue(capability["can_execute_without_focus"])
        self.assertFalse(capability["foreground_required"])

    def test_overlay_without_deterministic_route_is_blocked(self):
        plan = build_control_route_plan(
            _window("NVIDIA Overlay.exe", "NVIDIA GeForce Overlay", [])
        )

        capability = build_transport_capability(
            plan,
            ControlIntent(action="write_text", text="probe"),
        ).to_dict()

        self.assertEqual(capability["capability_level"], "blocked")
        self.assertEqual(capability["selected_transport"], "none")
        self.assertTrue(capability["blocked"])
        self.assertEqual(capability["blocking_reason"], "no_deterministic_transport")

    def test_control_fabric_report_embeds_transport_capability(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))

        report = fabric.dispatch(
            ConnectorTarget(process_name="chrome.exe", window_title="Chrome"),
            ControlIntent(action="read_page"),
        ).to_dict()

        self.assertEqual(report["transport_capability_level"], "background-native")
        self.assertEqual(report["selected_transport"], "chrome-devtools-protocol")
        self.assertTrue(report["can_execute_without_focus"])
        self.assertEqual(
            report["transport_capability"]["selected_route"],
            "browser-devtools-or-extension",
        )


if __name__ == "__main__":
    unittest.main()
