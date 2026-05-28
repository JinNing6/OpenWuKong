import unittest

from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.foreground_takeover import (
    ForegroundTakeoverRequest,
    validate_foreground_takeover_request,
)
from openwukong.evaluation.accessibility_probe import AccessibilityWindowSnapshot


def _window(process_name: str, title: str):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=(),
    )


class ForegroundTakeoverTests(unittest.TestCase):
    def test_control_fabric_returns_foreground_takeover_request_for_foreground_required_transport(self):
        report = ControlFabric().execute(
            _window("Weixin.exe", "微信"),
            ControlIntent(action="send_message", text="probe"),
            allow_control=True,
        )
        data = report.to_dict()
        request = data["foreground_takeover_request"]

        self.assertEqual(data["transport_gate_decision"], "blocked_foreground_takeover_required")
        self.assertEqual(request["mode"], "foreground-takeover-request")
        self.assertEqual(request["status"], "approval_required")
        self.assertEqual(request["action"], "send_message")
        self.assertEqual(request["target_process_name"], "Weixin.exe")
        self.assertEqual(request["target_window_title"], "微信")
        self.assertEqual(request["selected_transport"], "foreground-keyboard-clipboard")
        self.assertEqual(request["control_allowed"], False)
        self.assertEqual(request["control_attempts"], 0)
        self.assertIn("pre_action_target_verification", request["verification_requirements"])

    def test_foreground_takeover_request_validation_requires_matching_action_transport_and_target(self):
        request = ForegroundTakeoverRequest(
            status="approval_required",
            action="send_message",
            app_family="im",
            target_process_name="Weixin.exe",
            target_window_title="微信",
            selected_route="app-native-bridge-required",
            selected_transport="foreground-keyboard-clipboard",
            transport_channel="foreground_input",
            risk_flags=("native_connector_missing",),
            verification_requirements=("pre_action_target_verification",),
        )

        valid = validate_foreground_takeover_request(
            request,
            action="send_message",
            target_process_names=("weixin.exe", "wechat.exe"),
            selected_transport="foreground-keyboard-clipboard",
        ).to_dict()
        wrong_action = validate_foreground_takeover_request(
            request,
            action="run_command",
            target_process_names=("weixin.exe", "wechat.exe"),
            selected_transport="foreground-keyboard-clipboard",
        ).to_dict()

        self.assertTrue(valid["valid"])
        self.assertEqual(valid["decision"], "allow_foreground_takeover")
        self.assertFalse(wrong_action["valid"])
        self.assertEqual(wrong_action["decision"], "foreground_takeover_action_mismatch")


if __name__ == "__main__":
    unittest.main()
