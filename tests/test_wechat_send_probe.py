import tempfile
import unittest
from pathlib import Path

from openwukong.control.foreground_takeover import ForegroundTakeoverRequest
from openwukong.evaluation.wechat_send_probe import (
    FakeWeChatKeyboardAutomation,
    run_wechat_file_helper_send_probe,
)


def _wechat_takeover_request() -> ForegroundTakeoverRequest:
    return ForegroundTakeoverRequest(
        status="approval_required",
        action="send_message",
        app_family="im",
        target_process_name="Weixin.exe",
        target_window_title="微信",
        selected_route="app-native-bridge-required",
        selected_transport="foreground-keyboard-clipboard",
        transport_channel="foreground_input",
        risk_flags=("native_connector_missing", "foreground_focus_steal", "clipboard_mutation"),
        verification_requirements=(
            "pre_action_target_verification",
            "post_action_bound_window_verification",
            "state_restore_verification",
        ),
    )


class PostSendVerifyingAutomation(FakeWeChatKeyboardAutomation):
    def verify_post_send_message(self, target_name: str, message: str, screenshot_path: str) -> dict:
        self.events.append(f"verify_post_send:{target_name}:{message}")
        return {
            "verified": True,
            "method": "accessibility-text-readback",
            "target_name": target_name,
            "message_preview": message,
            "screenshot_path": screenshot_path,
        }


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

        self.assertEqual(data["status"], "blocked_external_target_requires_explicit_permission")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)

    def test_external_target_requires_extra_permission_before_takeover(self):
        automation = FakeWeChatKeyboardAutomation()

        report = run_wechat_file_helper_send_probe(
            target_name="张三",
            message="hello",
            allow_send=True,
            foreground_takeover_request=_wechat_takeover_request(),
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_external_target_requires_explicit_permission")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(automation.events, [])

    def test_external_target_can_send_with_extra_permission_and_target_verification(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=True)

        report = run_wechat_file_helper_send_probe(
            target_name="张三",
            message="hello",
            allow_send=True,
            allow_external_target=True,
            foreground_takeover_request=_wechat_takeover_request(),
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertEqual(data["target_name"], "张三")
        self.assertEqual(data["send_attempts"], 1)
        self.assertIn("paste:张三", automation.events)
        self.assertIn("paste:hello", automation.events)

    def test_requires_target_confirmation_before_send(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=False)

        report = run_wechat_file_helper_send_probe(
            message="hello",
            allow_send=True,
            automation=automation,
            foreground_takeover_request=_wechat_takeover_request(),
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_target_not_verified")
        self.assertEqual(data["send_attempts"], 0)
        self.assertGreater(data["keyboard_input_attempts"], 0)
        self.assertIn("paste:文件传输助手", automation.events)
        self.assertNotIn("paste:hello", automation.events)
        self.assertTrue(data["foreground_takeover_validated"])
        self.assertEqual(
            data["foreground_takeover_validation"]["decision"],
            "allow_foreground_takeover",
        )

    def test_blocks_allow_send_without_foreground_takeover_request(self):
        automation = FakeWeChatKeyboardAutomation()

        report = run_wechat_file_helper_send_probe(
            message="hello",
            allow_send=True,
            automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_foreground_takeover_request_required")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(automation.events, [])
        self.assertFalse(data["foreground_takeover_validated"])
        self.assertEqual(
            data["foreground_takeover_validation"]["decision"],
            "missing_foreground_takeover_request",
        )

    def test_sends_after_target_confirmation_and_restores_state(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=True)

        with tempfile.TemporaryDirectory() as tmp:
            report = run_wechat_file_helper_send_probe(
                message="OpenWukong live send probe",
                allow_send=True,
                automation=automation,
                output_dir=tmp,
                foreground_takeover_request=_wechat_takeover_request(),
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
            self.assertTrue(data["foreground_takeover_validated"])
            self.assertEqual(
                [phase["phase"] for phase in data["phases"]],
                [
                    "bind_window",
                    "open_target",
                    "verify_target",
                    "send_message",
                    "post_action_verify",
                    "restore_state",
                ],
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

    def test_records_post_send_accessibility_verification_when_available(self):
        automation = PostSendVerifyingAutomation(target_verified=True)

        report = run_wechat_file_helper_send_probe(
            message="verified send",
            allow_send=True,
            automation=automation,
            foreground_takeover_request=_wechat_takeover_request(),
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertTrue(data["post_send_verified"])
        self.assertEqual(data["post_send_verification"]["method"], "accessibility-text-readback")
        self.assertIn("verify_post_send:文件传输助手:verified send", automation.events)

    def test_explicit_confirmation_override_can_unlock_send(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=False)

        report = run_wechat_file_helper_send_probe(
            message="confirmed by operator",
            allow_send=True,
            confirm_target_after_open=True,
            automation=automation,
            foreground_takeover_request=_wechat_takeover_request(),
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertTrue(data["target_verified"])
        self.assertEqual(data["send_attempts"], 1)
        self.assertIn("paste:confirmed by operator", automation.events)


if __name__ == "__main__":
    unittest.main()
