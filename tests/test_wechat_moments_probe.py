import tempfile
import unittest
from pathlib import Path

from openwukong.control.foreground_takeover import ForegroundTakeoverRequest
from openwukong.evaluation.wechat_moments_probe import (
    run_wechat_moments_text_publish_probe,
)


def approval():
    return ForegroundTakeoverRequest(
        status="approved",
        action="publish_moments",
        app_family="im",
        target_process_name="Weixin.exe",
        target_window_title="微信",
        selected_transport="foreground-keyboard-clipboard",
    )


class FakeMomentsAutomation:
    def __init__(self, *, surface=True, panel=True, published=True):
        self.surface = surface
        self.panel = panel
        self.published = published
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

    def click_relative(self, x, y):
        self.events.append(f"click_relative:{x}:{y}")

    def paste_text(self, text):
        self.events.append(f"paste_text:{text}")

    def press(self, key):
        self.events.append(f"press:{key}")

    def sleep(self, seconds):
        del seconds

    def screenshot(self, path):
        self.events.append("screenshot")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake")
        return str(path)

    def capture_bound_window(self, hwnd, path):
        self.events.append(f"background_screenshot:{hwnd}")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake")
        return str(path)

    def verify_moments_surface(self, screenshot_path):
        self.events.append("verify_surface")
        return self.surface

    def verify_publish_panel(self, screenshot_path):
        self.events.append("verify_panel")
        return self.panel

    def verify_published_body(self, body, screenshot_path):
        self.events.append(f"verify_body:{body}")
        return {
            "verified": self.published,
            "method": "fake-positioned-ocr",
            "body_sha256": "x",
        }

    def set_visibility(self, visibility):
        self.events.append(f"visibility:{visibility}")
        return True

    def restore_clipboard(self):
        self.events.append("restore_clipboard")


class WeChatMomentsProbeTests(unittest.TestCase):
    def _run(self, automation, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            return run_wechat_moments_text_publish_probe(
                body="今天完成了一个小目标",
                visibility="public",
                allow_publish=True,
                automation=automation,
                output_dir=directory,
                foreground_takeover_request=approval(),
                moments_entry_relative=(0.04, 0.28),
                publish_relative=(0.62, 0.05),
                publish_submit_relative=(0.90, 0.90),
                **kwargs,
            )

    def test_publish_requires_explicit_opt_in(self):
        automation = FakeMomentsAutomation()
        report = run_wechat_moments_text_publish_probe(
            body="不要发布",
            allow_publish=False,
            automation=automation,
        )
        self.assertEqual(report.status, "blocked_requires_explicit_opt_in")
        self.assertEqual(report.publish_attempts, 0)
        self.assertEqual(automation.events, [])

    def test_publish_requires_verified_surface_panel_and_readback(self):
        automation = FakeMomentsAutomation()
        report = self._run(automation)
        data = report.to_dict()
        self.assertEqual(data["status"], "sent")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["publish_attempts"], 1)
        self.assertTrue(data["target_verified"])
        self.assertTrue(data["post_publish_verified"])
        self.assertIn("visibility:public", automation.events)

    def test_missing_panel_stops_before_publish(self):
        automation = FakeMomentsAutomation(panel=False)
        report = self._run(automation)
        self.assertEqual(report.status, "blocked_publish_panel_not_verified")
        self.assertEqual(report.publish_attempts, 0)
        self.assertNotIn("press:enter", automation.events)

    def test_missing_post_publish_readback_is_unknown_and_not_retried(self):
        automation = FakeMomentsAutomation(published=False)
        report = self._run(automation)
        self.assertEqual(report.status, "unverified")
        self.assertEqual(report.publish_attempts, 1)
        self.assertEqual(
            sum(event.startswith("verify_body:") for event in automation.events),
            1,
        )

    def test_missing_coordinates_are_blocked_without_control(self):
        automation = FakeMomentsAutomation()
        report = run_wechat_moments_text_publish_probe(
            body="missing coordinates",
            allow_publish=True,
            automation=automation,
            foreground_takeover_request=approval(),
        )
        self.assertEqual(report.status, "blocked_moments_coordinates_required")
        self.assertEqual(report.publish_attempts, 0)
        self.assertEqual(automation.events, [])


if __name__ == "__main__":
    unittest.main()
