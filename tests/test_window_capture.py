import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openwukong.evaluation import window_capture
from openwukong.evaluation.window_capture import (
    BackgroundWindowCaptureReport,
    PrintWindowBackgroundCaptureProvider,
)


class WindowCaptureTests(unittest.TestCase):
    def test_background_capture_classifies_unrelated_focus_change_as_external(self):
        report = BackgroundWindowCaptureReport(
            hwnd=7001,
            output_path="window.png",
            ok=True,
            foreground_hwnd_before=9001,
            foreground_hwnd_after=9002,
        )
        data = report.to_dict()

        self.assertTrue(report.foreground_changed)
        self.assertFalse(report.foreground_focus_risk)
        self.assertEqual(report.foreground_change_classification, "external_focus_change")
        self.assertTrue(data["foreground_changed"])
        self.assertFalse(data["foreground_focus_risk"])
        self.assertEqual(data["foreground_change_classification"], "external_focus_change")

    def test_background_capture_classifies_target_activation_as_focus_risk(self):
        report = BackgroundWindowCaptureReport(
            hwnd=7001,
            output_path="window.png",
            ok=True,
            foreground_hwnd_before=9001,
            foreground_hwnd_after=7001,
        )
        data = report.to_dict()

        self.assertTrue(report.foreground_changed)
        self.assertTrue(report.foreground_focus_risk)
        self.assertEqual(report.foreground_change_classification, "changed_to_target_window")
        self.assertTrue(data["foreground_focus_risk"])
        self.assertEqual(data["foreground_change_classification"], "changed_to_target_window")

    def test_print_window_provider_falls_back_to_screen_blt_without_focus_change(self):
        with tempfile.TemporaryDirectory() as td:
            output_path = Path(td) / "window.png"

            with mock.patch.object(
                window_capture,
                "_get_foreground_window",
                side_effect=(9001, 9001),
            ), mock.patch.object(
                window_capture,
                "_capture_hwnd_with_print_window",
                return_value=BackgroundWindowCaptureReport(
                    hwnd=7001,
                    output_path=str(output_path),
                    ok=False,
                    width=800,
                    height=600,
                    error="print_window_failed",
                ),
            ) as print_capture, mock.patch.object(
                window_capture,
                "_capture_hwnd_with_screen_blt",
                create=True,
                return_value=BackgroundWindowCaptureReport(
                    hwnd=7001,
                    output_path=str(output_path),
                    ok=True,
                    mode="screen-bounds-bitblt-fallback",
                    width=800,
                    height=600,
                ),
            ) as fallback_capture:
                report = PrintWindowBackgroundCaptureProvider().capture_window(
                    7001,
                    output_path,
                )

        self.assertTrue(report.ok, report)
        self.assertEqual(report.mode, "screen-bounds-bitblt-fallback")
        self.assertFalse(report.foreground_changed)
        self.assertEqual(report.foreground_hwnd_before, 9001)
        self.assertEqual(report.foreground_hwnd_after, 9001)
        print_capture.assert_called_once_with(7001, output_path)
        fallback_capture.assert_called_once_with(7001, output_path)


if __name__ == "__main__":
    unittest.main()
