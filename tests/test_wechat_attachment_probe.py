import tempfile
import unittest
from pathlib import Path

from openwukong.control.foreground_takeover import ForegroundTakeoverRequest
from openwukong.evaluation.wechat_send_probe import (
    run_wechat_file_helper_attachment_probe,
)


def approval():
    return ForegroundTakeoverRequest(
        status="approved",
        action="send_file",
        app_family="im",
        target_process_name="Weixin.exe",
        target_window_title="微信",
        selected_transport="foreground-keyboard-clipboard",
    )


class FakeAttachmentAutomation:
    def __init__(self, *, target_verified=True, attachment_verified=True):
        self.target_verified = target_verified
        self.attachment_verified = attachment_verified
        self.events = []

    def find_wechat_window(self):
        self.events.append("find_window")
        return 1001

    def get_foreground_window(self):
        self.events.append("get_foreground")
        return 9001

    def set_foreground_window(self, hwnd):
        self.events.append(f"set_foreground:{hwnd}")
        return True

    def hotkey(self, *keys):
        self.events.append("hotkey:" + "+".join(keys))

    def select_all(self):
        self.events.append("select_all")

    def paste_text(self, value):
        self.events.append(f"paste_text:{value}")

    def paste_files(self, paths):
        self.events.append("paste_files:" + "|".join(str(path) for path in paths))

    def press(self, key):
        self.events.append(f"press:{key}")

    def sleep(self, seconds):
        del seconds

    def screenshot(self, path):
        self.events.append("screenshot")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"pre")
        return str(path)

    def capture_bound_window(self, hwnd, path):
        self.events.append(f"background_screenshot:{hwnd}")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"post")
        return str(path)

    def verify_target(self, target_name, screenshot_path):
        self.events.append(f"verify_target:{target_name}")
        return self.target_verified

    def verify_post_send_attachment(self, target_name, filename, screenshot_path):
        self.events.append(f"verify_attachment:{target_name}:{filename}")
        return {
            "verified": self.attachment_verified,
            "method": "fake-positioned-ocr",
            "target_name": target_name,
            "filename": filename,
        }

    def restore_clipboard(self):
        self.events.append("restore_clipboard")


class WeChatAttachmentProbeTests(unittest.TestCase):
    def test_sends_one_file_to_file_helper_and_reads_back_attachment(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            attachment = root / "report.txt"
            attachment.write_text("safe test file", encoding="utf-8")
            automation = FakeAttachmentAutomation()
            report = run_wechat_file_helper_attachment_probe(
                file_path=attachment,
                authorized_root=root,
                allow_send=True,
                automation=automation,
                output_dir=root / "run",
                foreground_takeover_request=approval(),
            )

        data = report.to_dict()
        self.assertEqual(data["status"], "sent")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["send_attempts"], 1)
        self.assertTrue(data["target_verified"])
        self.assertTrue(data["post_send_verified"])
        self.assertEqual(data["clipboard_restore_attempts"], 1)
        self.assertTrue(any(event.startswith("paste_files:") for event in automation.events))
        self.assertEqual(
            automation.events[-3:],
            ["restore_clipboard", "set_foreground:9001", "get_foreground"],
        )

    def test_missing_file_approval_is_blocked_without_window_input(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            attachment = root / "report.txt"
            attachment.write_text("safe test file", encoding="utf-8")
            automation = FakeAttachmentAutomation()
            report = run_wechat_file_helper_attachment_probe(
                file_path=attachment,
                authorized_root=root,
                allow_send=False,
                automation=automation,
            )

        data = report.to_dict()
        self.assertEqual(data["status"], "blocked_requires_explicit_opt_in")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(automation.events, [])

    def test_file_outside_authorized_root_is_blocked_before_window_input(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            outside = root.parent / "outside-openwukong.txt"
            outside.write_text("safe test file", encoding="utf-8")
            automation = FakeAttachmentAutomation()
            report = run_wechat_file_helper_attachment_probe(
                file_path=outside,
                authorized_root=root,
                allow_send=True,
                automation=automation,
                foreground_takeover_request=approval(),
            )

        data = report.to_dict()
        self.assertEqual(data["status"], "blocked_file_outside_authorized_root")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(automation.events, [])

    def test_missing_authorized_root_is_blocked_before_window_input(self):
        with tempfile.TemporaryDirectory() as root_name:
            attachment = Path(root_name) / "report.txt"
            attachment.write_text("safe test file", encoding="utf-8")
            automation = FakeAttachmentAutomation()
            report = run_wechat_file_helper_attachment_probe(
                file_path=attachment,
                authorized_root="",
                allow_send=True,
                automation=automation,
                foreground_takeover_request=approval(),
            )

        data = report.to_dict()
        self.assertEqual(data["status"], "blocked_authorized_root_required")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(automation.events, [])

    def test_attachment_readback_failure_is_unknown_and_not_retried(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            attachment = root / "report.txt"
            attachment.write_text("safe test file", encoding="utf-8")
            automation = FakeAttachmentAutomation(attachment_verified=False)
            report = run_wechat_file_helper_attachment_probe(
                file_path=attachment,
                authorized_root=root,
                allow_send=True,
                automation=automation,
                foreground_takeover_request=approval(),
            )

        data = report.to_dict()
        self.assertEqual(data["status"], "unverified")
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(
            sum(event.startswith("paste_files:") for event in automation.events),
            1,
        )


if __name__ == "__main__":
    unittest.main()
