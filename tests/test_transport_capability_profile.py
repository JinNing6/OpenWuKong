import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.transport_capability_matrix import main


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
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name=class_name,
        hwnd=3030,
        elements=tuple(elements),
    )


class TransportCapabilityProfileTests(unittest.TestCase):
    def test_cli_outputs_read_only_transport_matrix_from_static_observer(self):
        observer = StaticAccessibilityObserver(
            [
                _window("chrome.exe", "Search - Google Chrome"),
                _window(
                    "reader.exe",
                    "Reader",
                    [_element("Document", name="Document", patterns=("Text",))],
                ),
                _window("NVIDIA Overlay.exe", "NVIDIA GeForce Overlay"),
            ]
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--action", "read_text", "--json"], observer=observer)

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "transport-capability-matrix")
        self.assertEqual(data["safety_mode"], "plan_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_count"], 3)
        self.assertEqual(data["summary"]["background_native"], 1)
        self.assertEqual(data["summary"]["background_read_only"], 1)
        self.assertEqual(data["summary"]["blocked"], 1)
        self.assertEqual(data["summary"]["can_execute_without_focus"], 2)
        self.assertEqual(data["capability_level_counts"]["background-native"], 1)
        self.assertEqual(data["capability_level_counts"]["background-read-only"], 1)
        self.assertEqual(data["selected_transport_counts"]["chrome-devtools-protocol"], 1)
        self.assertEqual(data["selected_transport_counts"]["uia-tree-read"], 1)

    def test_cli_marks_wechat_send_as_foreground_required_with_confirmation(self):
        observer = StaticAccessibilityObserver(
            [
                _window(
                    "Weixin.exe",
                    "微信",
                    [_element("Pane"), _element("TitleBar")],
                )
            ]
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--action", "send_message", "--text", "probe", "--json"], observer=observer)

        data = json.loads(stdout.getvalue())
        capability = data["capabilities"][0]["transport_capability"]
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["summary"]["foreground_required"], 1)
        self.assertEqual(data["summary"]["requires_user_confirmation"], 1)
        self.assertEqual(capability["capability_level"], "foreground-required")
        self.assertEqual(capability["selected_transport"], "foreground-keyboard-clipboard")
        self.assertTrue(capability["requires_user_confirmation"])
        self.assertIn("post_action_bound_window_verification", capability["verification_requirements"])

    def test_cli_writes_json_output_file(self):
        observer = StaticAccessibilityObserver(
            [
                _window("chrome.exe", "Search - Google Chrome"),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "transport.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["--action", "read_page", "--output", str(output_path)],
                    observer=observer,
                )

            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertIn("Transport capability matrix:", stdout.getvalue())
        self.assertEqual(saved["mode"], "transport-capability-matrix")
        self.assertEqual(saved["summary"]["background_native"], 1)


if __name__ == "__main__":
    unittest.main()
