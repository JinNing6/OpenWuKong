import unittest

from openwukong.connectors.route_policy import (
    build_control_route_matrix,
    build_control_route_plan,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityCapabilityReport,
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        automation_id=name.lower().replace(" ", "-"),
        class_name="",
        value_preview="",
        rect=(0, 0, 100, 40),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements=(), class_name: str = "Window"):
    return AccessibilityWindowSnapshot(
        pid=100,
        process_name=process_name,
        window_title=title,
        class_name=class_name,
        hwnd=200,
        elements=tuple(elements),
    )


class ControlRoutePolicyTests(unittest.TestCase):
    def test_browser_prefers_devtools_extension_before_uia_fallback(self):
        window = _window(
            "msedge.exe",
            "Inbox - Microsoft Edge",
            [
                _element("Edit", name="Search", patterns=("Value", "Text")),
                _element("Button", name="Send", patterns=("Invoke",)),
            ],
        )

        plan = build_control_route_plan(window)
        data = plan.to_dict()

        self.assertEqual(data["app_family"], "browser")
        self.assertEqual(data["primary_route"]["route_id"], "browser-devtools-or-extension")
        self.assertEqual(data["primary_route"]["locator_source"], "browser-dom-or-accessibility-tree")
        self.assertIn("extension_command", data["primary_route"]["action_primitives"])
        self.assertIn("uia-semantic", [route["route_id"] for route in data["fallback_routes"]])
        self.assertEqual(data["control_decision"], "prefer_deterministic_connector")

    def test_terminal_uses_native_session_and_demotes_uia_to_observation(self):
        window = _window(
            "WindowsTerminal.exe",
            "Windows PowerShell",
            [
                _element("Button", name="New tab", patterns=("Invoke",)),
                _element("Text", name="Prompt", patterns=("Text",)),
            ],
        )

        plan = build_control_route_plan(window)
        data = plan.to_dict()

        self.assertEqual(data["app_family"], "terminal")
        self.assertEqual(data["primary_route"]["route_id"], "terminal-native-session")
        self.assertEqual(data["primary_route"]["locator_source"], "conpty-or-managed-shell-session")
        self.assertNotIn("uia-semantic", [route["route_id"] for route in data["fallback_routes"]])
        self.assertIn("uia-observe-chrome-only", [route["route_id"] for route in data["fallback_routes"]])
        self.assertIn("terminal_buffer_not_uia_writable", data["missing_capabilities"])

    def test_weak_im_surface_requires_native_bridge_before_vision(self):
        window = _window(
            "Weixin.exe",
            "微信",
            [
                _element("Pane", name=""),
                _element("TitleBar", name=""),
            ],
        )

        plan = build_control_route_plan(window)
        data = plan.to_dict()

        self.assertEqual(data["app_family"], "im")
        self.assertEqual(data["primary_route"]["route_id"], "app-native-bridge-required")
        self.assertEqual(data["control_decision"], "block_until_deterministic_route")
        self.assertIn("no_semantic_input", data["missing_capabilities"])
        self.assertEqual(data["fallback_routes"][-1]["route_id"], "vision-fallback-last")

    def test_text_only_document_is_readable_but_not_writable_for_uia_control(self):
        window = _window(
            "reader.exe",
            "Reader",
            [
                _element("Document", name="Document", patterns=("Text",)),
            ],
        )

        plan = build_control_route_plan(window)
        data = plan.to_dict()

        self.assertEqual(data["app_family"], "generic-desktop")
        self.assertEqual(data["primary_route"]["route_id"], "uia-structural-observe")
        self.assertEqual(data["control_decision"], "observe_until_writable_locator")
        self.assertIn("no_semantic_input", data["missing_capabilities"])

    def test_route_matrix_summarizes_families_routes_and_blocked_windows(self):
        report = AccessibilityCapabilityReport(
            windows=(
                _window(
                    "msedge.exe",
                    "Inbox - Microsoft Edge",
                    [_element("Edit", name="Search", patterns=("Value",))],
                ),
                _window("Weixin.exe", "微信", [_element("Pane")]),
                _window("NVIDIA Overlay.exe", "NVIDIA GeForce Overlay", []),
            )
        )

        matrix = build_control_route_matrix(report)
        data = matrix.to_dict()

        self.assertEqual(data["mode"], "control-route-matrix")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["app_family_counts"]["browser"], 1)
        self.assertEqual(data["app_family_counts"]["im"], 1)
        self.assertEqual(data["app_family_counts"]["overlay"], 1)
        self.assertEqual(data["primary_route_counts"]["browser-devtools-or-extension"], 1)
        self.assertIn("微信", data["blocked_windows"])
        self.assertIn("NVIDIA GeForce Overlay", data["blocked_windows"])


if __name__ == "__main__":
    unittest.main()
