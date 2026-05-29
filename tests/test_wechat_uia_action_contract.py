import unittest

from openwukong.control.wechat_uia_action import (
    WeChatUiaSemanticActionDryRunAdapter,
    WeChatUiaSemanticActionSenderAdapter,
    build_wechat_uia_semantic_action_request,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(10, 20, 300, 60),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _ready_window():
    return AccessibilityWindowSnapshot(
        pid=7101,
        process_name="Weixin.exe",
        window_title="File Transfer Assistant - WeChat",
        class_name="Qt51514QWindowIcon",
        hwnd=1001,
        elements=(
            _element("Text", name="File Transfer Assistant"),
            _element("Edit", name="Type a message", patterns=("Value", "Text")),
            _element("Button", name="Send", patterns=("Invoke",)),
        ),
    )


class WeChatUiaActionContractTests(unittest.TestCase):
    def test_ready_wechat_window_builds_dry_run_contract_without_attempts(self):
        request = build_wechat_uia_semantic_action_request(
            target_name="File Transfer Assistant",
            message="OpenWukong dry-run only",
            windows=(_ready_window(),),
            background_screenshot_focus_stable=True,
        )

        report = WeChatUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "wechat_uia_semantic_action_dry_run_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 0)
        self.assertEqual(data["uia_invoke_attempts"], 0)
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["uia_value_pattern_ready"])
        self.assertTrue(data["request"]["uia_invoke_pattern_ready"])
        self.assertEqual(data["request"]["target"]["hwnd"], 1001)
        self.assertEqual(data["request"]["composer"]["name"], "Type a message")
        self.assertEqual(data["request"]["submit_control"]["name"], "Send")

    def test_target_visible_without_value_pattern_stays_gated(self):
        window = AccessibilityWindowSnapshot(
            pid=7101,
            process_name="Weixin.exe",
            window_title="File Transfer Assistant - WeChat",
            hwnd=1001,
            elements=(
                _element("Text", name="File Transfer Assistant"),
                _element("Edit", name="Type a message", patterns=("Text",)),
                _element("Button", name="Send", patterns=("Invoke",)),
            ),
        )
        request = build_wechat_uia_semantic_action_request(
            target_name="File Transfer Assistant",
            message="OpenWukong dry-run only",
            windows=(window,),
            background_screenshot_focus_stable=True,
        )

        report = WeChatUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertTrue(data["request"]["target_ready"])
        self.assertFalse(data["request"]["uia_value_pattern_ready"])
        self.assertTrue(data["request"]["uia_invoke_pattern_ready"])
        self.assertEqual(data["decision"], "wechat_uia_semantic_action_value_pattern_not_ready")
        self.assertEqual(data["control_attempts"], 0)

    def test_missing_target_contact_stays_gated(self):
        window = AccessibilityWindowSnapshot(
            pid=7101,
            process_name="Weixin.exe",
            window_title="WeChat",
            hwnd=1001,
            elements=(
                _element("Edit", name="Type a message", patterns=("Value", "Text")),
                _element("Button", name="Send", patterns=("Invoke",)),
            ),
        )
        request = build_wechat_uia_semantic_action_request(
            target_name="File Transfer Assistant",
            message="OpenWukong dry-run only",
            windows=(window,),
            background_screenshot_focus_stable=True,
        )

        report = WeChatUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["uia_value_pattern_ready"])
        self.assertTrue(data["request"]["uia_invoke_pattern_ready"])
        self.assertEqual(data["decision"], "wechat_uia_semantic_action_target_not_ready")
        self.assertEqual(data["send_attempts"], 0)

    def test_sender_sets_value_invokes_submit_and_accepts_readback_without_window_input(self):
        operator_calls = []

        class FakeOperator:
            def execute(self, request):
                operator_calls.append(request)
                return {
                    "composer_found": True,
                    "value_set_attempted": True,
                    "value_set": True,
                    "post_value": request.message,
                    "submit_found": True,
                    "invoke_attempted": True,
                    "invoke_verified": True,
                    "readbackText": f"File Transfer Assistant\n{request.message}",
                }

        request = build_wechat_uia_semantic_action_request(
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_UIA_ACCEPTANCE: PASS",
            windows=(_ready_window(),),
            background_screenshot_focus_stable=True,
        )

        report = WeChatUiaSemanticActionSenderAdapter(
            operator=FakeOperator(),
            foreground_hwnd_provider=lambda: 7001,
        ).send(request)
        data = report.to_dict()

        self.assertEqual(len(operator_calls), 1)
        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "wechat_uia_semantic_action_send_accepted")
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 1)
        self.assertTrue(data["foreground_focus_stable"])
        self.assertEqual(data["missing_required_markers"], [])

    def test_sender_rejects_foreground_change_after_semantic_operations(self):
        foreground_values = iter((7001, 9009))

        class FakeOperator:
            def execute(self, request):
                return {
                    "composer_found": True,
                    "value_set_attempted": True,
                    "value_set": True,
                    "post_value": request.message,
                    "submit_found": True,
                    "invoke_attempted": True,
                    "invoke_verified": True,
                    "readbackText": request.message,
                }

        request = build_wechat_uia_semantic_action_request(
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_UIA_ACCEPTANCE: PASS",
            windows=(_ready_window(),),
            background_screenshot_focus_stable=True,
        )

        report = WeChatUiaSemanticActionSenderAdapter(
            operator=FakeOperator(),
            foreground_hwnd_provider=lambda: next(foreground_values),
        ).send(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "wechat_uia_semantic_action_foreground_changed")
        self.assertFalse(data["foreground_focus_stable"])
        self.assertEqual(data["window_input_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
