import contextlib
import io
import json
import unittest

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.universal_app_profile import main
from openwukong.evaluation.universal_app_profile import profile_applications


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=tuple(elements),
    )


class UniversalAppProfileTests(unittest.TestCase):
    def test_profile_classifies_connector_background_foreground_and_blocked_windows(self):
        windows = (
            _window(
                "Cursor.exe",
                "openwukong - Cursor",
                [_element("Document", name="editor", patterns=("Text",))],
            ),
            _window(
                "notepad.exe",
                "Untitled - Notepad",
                [
                    _element("Edit", name="Text editor", patterns=("Value", "Text")),
                    _element("Button", name="Save", patterns=("Invoke",)),
                ],
            ),
            _window(
                "custom-electron.exe",
                "Custom Chat",
                [_element("Edit", name="", patterns=("Text",))],
            ),
            _window("custom-canvas.exe", "Canvas App", []),
        )

        report = profile_applications(windows)
        data = report.to_dict()

        self.assertEqual(data["mode"], "universal-application-control-profile")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_count"], 4)
        self.assertEqual(data["status_counts"]["connector_required"], 1)
        self.assertEqual(data["status_counts"]["background_semantic_ready"], 1)
        self.assertEqual(data["status_counts"]["foreground_or_native_required"], 1)
        self.assertEqual(data["status_counts"]["blocked"], 1)
        self.assertEqual(data["summary"]["auto_background_ready"], 1)
        self.assertEqual(data["summary"]["connector_required"], 1)
        self.assertEqual(data["summary"]["foreground_required"], 1)
        self.assertEqual(data["summary"]["blocked"], 1)

    def test_profile_prioritizes_native_connectors_for_known_app_families(self):
        report = profile_applications(
            (
                _window(
                    "chrome.exe",
                    "Inbox - Google Chrome",
                    [_element("Edit", name="Search", patterns=("Value",))],
                ),
                _window(
                    "EXCEL.EXE",
                    "Book1 - Excel",
                    [_element("DataGrid", name="Worksheet", patterns=("Grid", "Selection"))],
                ),
                _window(
                    "pwsh.exe",
                    "PowerShell",
                    [_element("Document", name="Console", patterns=("Text",))],
                ),
            )
        )

        profiles = {
            item["process_name"].lower(): item
            for item in report.to_dict()["windows"]
        }

        self.assertEqual(profiles["chrome.exe"]["one_step_status"], "connector_required")
        self.assertEqual(profiles["chrome.exe"]["recommended_route"], "browser-devtools-or-extension")
        self.assertEqual(profiles["excel.exe"]["recommended_route"], "office-object-model-or-addin")
        self.assertEqual(profiles["pwsh.exe"]["recommended_route"], "terminal-native-session")

    def test_cli_outputs_profile_json_from_static_observer(self):
        observer = StaticAccessibilityObserver([
            _window(
                "notepad.exe",
                "Untitled - Notepad",
                [_element("Edit", name="Text editor", patterns=("Value", "Text"))],
            )
        ])

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--json"], observer=observer)

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "universal-application-control-profile")
        self.assertEqual(data["window_count"], 1)
        self.assertEqual(data["windows"][0]["one_step_status"], "background_semantic_ready")


if __name__ == "__main__":
    unittest.main()
