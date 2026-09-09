import unittest

from openwukong.evaluation.wechat_basic_operations_demo import (
    run_wechat_basic_operations_demo,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


def _element(control_type, name, patterns=(), automation_id=""):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        automation_id=automation_id,
        rect=(10, 20, 300, 60),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window():
    return AccessibilityWindowSnapshot(
        pid=7101,
        process_name="Weixin.exe",
        window_title="File Transfer Assistant - WeChat",
        class_name="Qt51514QWindowIcon",
        hwnd=1001,
        elements=(
            _element("Text", "File Transfer Assistant"),
            _element("Edit", "Type a message", ("Value", "TextEdit"), "composer"),
            _element("Button", "Send", ("Invoke",), "send"),
            _element("Button", "Moments", ("Invoke",), "moments"),
            _element("Button", "Publish", ("Invoke",), "publish"),
        ),
    )


class WeChatBasicOperationsDemoTests(unittest.TestCase):
    def test_dry_run_reports_capabilities_target_and_zero_control_attempts(self):
        report = run_wechat_basic_operations_demo(
            windows=(_window(),),
            target_name="File Transfer Assistant",
            dry_run=True,
        )

        self.assertFalse(report["control_allowed"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["keyboard_input_attempts"], 0)
        self.assertEqual(report["clipboard_write_attempts"], 0)
        self.assertEqual(report["surface"]["decision"], "surface_ready")
        self.assertEqual(report["target"]["decision"], "target_exactly_resolved")
        self.assertTrue(report["capabilities"]["wechat.chat.send_text"])
        self.assertTrue(report["capabilities"]["wechat.moments.publish"])
        self.assertEqual(report["planned_side_effects"], [])

    def test_dry_run_without_target_does_not_guess_a_conversation(self):
        report = run_wechat_basic_operations_demo(
            windows=(_window(),),
            target_name="Someone Else",
            dry_run=True,
        )

        self.assertFalse(report["control_allowed"])
        self.assertEqual(report["target"]["decision"], "target_not_found")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["planned_side_effects"], [])

    def test_send_mode_is_not_available_without_explicit_dry_run_contract(self):
        with self.assertRaises(ValueError):
            run_wechat_basic_operations_demo(windows=(_window(),), dry_run=False)


if __name__ == "__main__":
    unittest.main()
