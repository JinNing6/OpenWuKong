import ctypes
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openwukong.control.foreground_takeover import ForegroundTakeoverRequest
from openwukong.control.windows_file_clipboard import ClipboardTextSnapshot
from openwukong.evaluation.wechat_send_probe import (
    FakeWeChatKeyboardAutomation,
    Win32WeChatKeyboardAutomation,
    run_wechat_file_helper_send_probe,
)


def approval():
    return ForegroundTakeoverRequest(
        status="approved", action="send_message", app_family="im",
        target_process_name="Weixin.exe", target_window_title="微信",
        selected_transport="foreground-keyboard-clipboard",
    )


class WeChatFocusSafetyTests(unittest.TestCase):
    def test_restoring_another_window_does_not_refocus_cached_wechat(self):
        current = [1001]
        user32 = SimpleNamespace(
            SetForegroundWindow=lambda hwnd: current.__setitem__(0, int(hwnd)) or True,
            GetForegroundWindow=lambda: current[0],
        )
        automation = Win32WeChatKeyboardAutomation(action_delay=0)
        automation._window = SimpleNamespace(handle=1001, set_focus=Mock())
        with patch.object(ctypes, "windll", SimpleNamespace(user32=user32), create=True):
            self.assertTrue(automation.set_foreground_window(9001))
        automation._window.set_focus.assert_not_called()
        self.assertEqual(current[0], 9001)

    def test_focus_claim_is_verified_against_actual_foreground(self):
        user32 = SimpleNamespace(
            SetForegroundWindow=lambda hwnd: True,
            GetForegroundWindow=lambda: 9999,
        )
        automation = Win32WeChatKeyboardAutomation(action_delay=0)
        with patch.object(ctypes, "windll", SimpleNamespace(user32=user32), create=True):
            self.assertFalse(automation.set_foreground_window(1001))

    def test_screenshot_refuses_covered_window_instead_of_capturing_foreground_app(self):
        automation = Win32WeChatKeyboardAutomation(action_delay=0)
        automation._window = SimpleNamespace(
            handle=1001,
            capture_as_image=lambda: SimpleNamespace(save=lambda _path: None),
        )
        with patch.object(automation, "get_foreground_window", return_value=9001):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RuntimeError, "screenshot_target_not_foreground"):
                    automation.screenshot(Path(directory) / "covered.png")

    def test_failed_focus_prevents_search_or_paste(self):
        class FailedFocus(FakeWeChatKeyboardAutomation):
            def set_foreground_window(self, hwnd):
                self.events.append(f"failed_focus:{hwnd}")
                return False

        automation = FailedFocus()
        with tempfile.TemporaryDirectory() as directory:
            report = run_wechat_file_helper_send_probe(
                message="test", allow_send=True, automation=automation,
                output_dir=directory, foreground_takeover_request=approval(),
            )
        self.assertEqual(report.send_attempts, 0)
        self.assertEqual(report.keyboard_input_attempts, 0)
        self.assertFalse(any(event.startswith("paste:") for event in automation.events))
        self.assertNotEqual(report.status, "sent")

    def test_restore_result_is_evidence_not_an_attempt_counter(self):
        automation = FakeWeChatKeyboardAutomation()
        with tempfile.TemporaryDirectory() as directory:
            report = run_wechat_file_helper_send_probe(
                message="test", allow_send=True, automation=automation,
                output_dir=directory, foreground_takeover_request=approval(),
            )
        self.assertTrue(report.to_dict()["foreground_restored"])
        self.assertEqual(report.to_dict()["final_foreground_hwnd"], 9001)

    def test_exception_after_send_dispatch_preserves_attempt(self):
        class SendRaises(FakeWeChatKeyboardAutomation):
            def press(self, key):
                super().press(key)
                if self.events.count("press:enter") == 2:
                    raise RuntimeError("uncertain delivery after dispatch")

        with tempfile.TemporaryDirectory() as directory:
            report = run_wechat_file_helper_send_probe(
                message="test", allow_send=True, automation=SendRaises(),
                output_dir=directory, foreground_takeover_request=approval(),
            )
        self.assertEqual(report.status, "failed")
        self.assertEqual(report.send_attempts, 1)

    def test_file_paste_captures_and_restores_text_clipboard(self):
        class Clipboard:
            def __init__(self):
                self.events = []

            def capture_text(self):
                self.events.append("capture")
                return ClipboardTextSnapshot("old clipboard")

            def set_files(self, paths):
                self.events.append(("set_files", tuple(paths)))

            def restore_text(self, snapshot):
                self.events.append(("restore", snapshot.text))

        clipboard = Clipboard()
        automation = Win32WeChatKeyboardAutomation(
            action_delay=0,
            file_clipboard=clipboard,
        )
        automation._window = SimpleNamespace(handle=1001)
        with patch.object(automation, "get_foreground_window", return_value=1001):
            with patch("pywinauto.keyboard.send_keys") as send_keys:
                automation.paste_files(["C:/approved/report.txt"])
                automation.restore_clipboard()
        self.assertEqual(clipboard.events[0], "capture")
        self.assertEqual(clipboard.events[1][0], "set_files")
        self.assertEqual(clipboard.events[-1], ("restore", "old clipboard"))
        send_keys.assert_called_once_with("^v")


if __name__ == "__main__":
    unittest.main()
