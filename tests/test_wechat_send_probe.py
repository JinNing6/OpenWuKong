import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.wechat_send_probe import (
    FakeWeChatKeyboardAutomation,
    run_wechat_file_helper_send_probe,
)


class WeChatSendProbeTests(unittest.TestCase):
    def test_blocks_send_without_explicit_opt_in(self):
        automation = FakeWeChatKeyboardAutomation()

        report = run_wechat_file_helper_send_probe(
            message="hello",
            allow_send=False,
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "wechat-file-helper-send-probe")
        self.assertEqual(data["status"], "blocked_requires_explicit_opt_in")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(automation.events, [])

    def test_blocks_non_file_helper_targets(self):
        automation = FakeWeChatKeyboardAutomation()

        report = run_wechat_file_helper_send_probe(
            target_name="not-file-helper",
            message="hello",
            allow_send=True,
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_target_not_allowed")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)

    def test_requires_target_confirmation_before_send(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=False)

        report = run_wechat_file_helper_send_probe(
            message="hello",
            allow_send=True,
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_target_not_verified")
        self.assertEqual(data["send_attempts"], 0)
        self.assertGreater(data["keyboard_input_attempts"], 0)
        self.assertIn("paste:文件传输助手", automation.events)
        self.assertNotIn("paste:hello", automation.events)

    def test_sends_after_target_confirmation_and_restores_state(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=True)

        with tempfile.TemporaryDirectory() as tmp:
            report = run_wechat_file_helper_send_probe(
                message="OpenWukong live send probe",
                allow_send=True,
                automation=automation,
                output_dir=tmp,
            )
            data = report.to_dict()

            self.assertEqual(data["status"], "sent")
            self.assertTrue(data["control_allowed"])
            self.assertEqual(data["target_name"], "文件传输助手")
            self.assertEqual(data["send_attempts"], 1)
            self.assertGreaterEqual(data["keyboard_input_attempts"], 6)
            self.assertEqual(data["clipboard_restore_attempts"], 1)
            self.assertEqual(data["foreground_restore_attempts"], 1)
            self.assertTrue(Path(data["pre_send_screenshot_path"]).is_file())
            self.assertTrue(Path(data["post_send_screenshot_path"]).is_file())
            self.assertEqual(data["post_send_screenshot_hwnd"], 1001)
            self.assertTrue(data["post_send_screenshot_bound"])
            self.assertTrue(Path(data["artifact_path"]).is_file())
            self.assertEqual(data["transport"], "foreground-keyboard-clipboard")
            self.assertEqual(
                [phase["phase"] for phase in data["phases"]],
                ["bind_window", "open_target", "verify_target", "send_message", "restore_state"],
            )
            self.assertEqual(
                automation.events,
                [
                    "find_window",
                    "get_foreground",
                    "set_foreground:1001",
                    "hotkey:ctrl+f",
                    "select_all",
                    "paste:文件传输助手",
                    "press:enter",
                    "screenshot",
                    "verify_target:文件传输助手",
                    "paste:OpenWukong live send probe",
                    "press:enter",
                    "background_screenshot:1001",
                    "restore_clipboard",
                    "set_foreground:9001",
                ],
            )

    def test_explicit_confirmation_override_can_unlock_send(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=False)

        report = run_wechat_file_helper_send_probe(
            message="confirmed by operator",
            allow_send=True,
            confirm_target_after_open=True,
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertTrue(data["target_verified"])
        self.assertEqual(data["send_attempts"], 1)
        self.assertIn("paste:confirmed by operator", automation.events)


if __name__ == "__main__":
    unittest.main()
