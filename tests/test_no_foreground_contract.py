import unittest

from openwukong.connectors import ConnectorManager, ConnectorTarget
from openwukong.control.execution_contract import (
    build_no_foreground_contract,
    validate_no_foreground_contract,
)
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


class NoForegroundContractTests(unittest.TestCase):
    def test_background_native_route_disallows_keyboard_mouse_and_clipboard(self):
        plan = build_control_route_plan(
            _window(
                "chrome.exe",
                "Search - Google Chrome",
                [_element("Edit", name="Search", patterns=("Value", "Text"))],
            )
        )
        intent = ControlIntent(action="read_page")
        capability = build_transport_capability(plan, intent)

        contract = build_no_foreground_contract(
            plan,
            intent,
            transport=capability,
        ).to_dict()

        self.assertEqual(contract["mode"], "no-foreground-control-contract")
        self.assertEqual(contract["contract_version"], "no-foreground-v1")
        self.assertTrue(contract["can_execute_without_focus"])
        self.assertFalse(contract["foreground_required"])
        self.assertFalse(contract["foreground_takeover_allowed"])
        self.assertFalse(contract["keyboard_input_allowed"])
        self.assertFalse(contract["mouse_input_allowed"])
        self.assertFalse(contract["clipboard_write_allowed"])
        self.assertIn("foreground_focus_stability", contract["required_evidence"])
        self.assertFalse(contract["blocked"])

    def test_structural_write_is_blocked_without_foreground_permission(self):
        plan = build_control_route_plan(
            _window(
                "reader.exe",
                "Reader",
                [_element("Document", name="Document", patterns=("Text",))],
            )
        )
        intent = ControlIntent(action="write_text", text="probe")
        capability = build_transport_capability(
            plan,
            intent,
            selected_route="uia-structural-observe",
        )

        contract = build_no_foreground_contract(
            plan,
            intent,
            transport=capability,
            selected_route="uia-structural-observe",
        ).to_dict()

        self.assertTrue(contract["foreground_required"])
        self.assertFalse(contract["foreground_takeover_allowed"])
        self.assertTrue(contract["blocked"])
        self.assertEqual(contract["blocking_reason"], "foreground_takeover_not_allowed")

    def test_validation_rejects_focus_change_and_forbidden_input_attempts(self):
        plan = build_control_route_plan(
            _window("chrome.exe", "Search - Google Chrome")
        )
        contract = build_no_foreground_contract(
            plan,
            ControlIntent(action="read_page"),
        )

        validation = validate_no_foreground_contract(
            contract,
            {
                "ok": True,
                "foreground_focus_stable": False,
                "keyboard_input_attempts": 1,
                "clipboard_write_attempts": 1,
            },
        ).to_dict()

        self.assertFalse(validation["ok"])
        self.assertEqual(validation["decision"], "contract_violation")
        self.assertIn("foreground_focus_changed", validation["violations"])
        self.assertIn("keyboard_input_not_allowed", validation["violations"])
        self.assertIn("clipboard_write_not_allowed", validation["violations"])

    def test_control_fabric_dispatch_embeds_no_foreground_contract(self):
        fabric = ControlFabric(connector_manager=ConnectorManager([]))
        data = fabric.dispatch(
            ConnectorTarget(process_name="chrome.exe", window_title="Chrome"),
            ControlIntent(action="read_page"),
        ).to_dict()

        self.assertIn("no_foreground_contract", data)
        self.assertEqual(
            data["no_foreground_contract"]["selected_route"],
            "browser-devtools-or-extension",
        )
        self.assertTrue(data["no_foreground_contract"]["can_execute_without_focus"])


if __name__ == "__main__":
    unittest.main()
