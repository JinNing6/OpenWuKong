import contextlib
import io
import json
import unittest
from unittest.mock import patch

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
    WindowsCapabilityProbe,
    _element_from_wrapper,
    main,
)


def _element(
    control_type: str,
    *,
    name: str = "",
    automation_id: str = "",
    patterns=(),
) -> AccessibilityElementSnapshot:
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        automation_id=automation_id,
        class_name="",
        value_preview="",
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(*, process_name: str, title: str, elements) -> AccessibilityWindowSnapshot:
    return AccessibilityWindowSnapshot(
        pid=1001,
        process_name=process_name,
        window_title=title,
        class_name="ApplicationFrameWindow",
        hwnd=0,
        elements=tuple(elements),
        scan_error="",
    )


class AccessibilityProbeTests(unittest.TestCase):
    def test_probe_scores_semantic_input_and_invoke_capabilities(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="notepad.exe",
                title="Untitled - Notepad",
                elements=[
                    _element("Edit", name="Text editor", automation_id="15", patterns=("Value", "Text")),
                    _element("Button", name="Save", automation_id="save", patterns=("Invoke",)),
                    _element("Text", name="Status", patterns=("Text",)),
                ],
            )
        ])

        report = WindowsCapabilityProbe(observer=observer).run()

        data = report.to_dict()
        self.assertEqual(data["mode"], "windows-accessibility-capability")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_count"], 1)
        window = data["windows"][0]
        self.assertEqual(window["process_name"], "notepad.exe")
        self.assertEqual(window["element_count"], 3)
        self.assertEqual(window["input_candidate_count"], 1)
        self.assertEqual(window["semantic_input_count"], 1)
        self.assertEqual(window["semantic_action_count"], 1)
        self.assertEqual(window["text_readable_count"], 2)
        self.assertEqual(window["capability_level"], "semantic")
        self.assertGreaterEqual(window["capability_score"], 80)
        self.assertIn("uia-semantic", window["recommended_routes"])

    def test_probe_recommends_specialized_connector_before_uia_for_known_app_families(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="chrome.exe",
                title="Inbox - Google Chrome",
                elements=[
                    _element("Edit", name="Search", patterns=("Value",)),
                    _element("Button", name="Submit", patterns=("Invoke",)),
                ],
            ),
            _window(
                process_name="cursor.exe",
                title="openwukong - Cursor",
                elements=[
                    _element("Document", name="editor", patterns=("Text",)),
                ],
            ),
            _window(
                process_name="EXCEL.EXE",
                title="Book1 - Excel",
                elements=[
                    _element("DataGrid", name="Worksheet", patterns=("Grid", "Selection")),
                ],
            ),
        ])

        report = WindowsCapabilityProbe(observer=observer).run()
        routes = {
            window["process_name"].lower(): window["recommended_routes"]
            for window in report.to_dict()["windows"]
        }

        self.assertEqual(routes["chrome.exe"][0], "browser-devtools-or-extension")
        self.assertEqual(routes["cursor.exe"][0], "ide-extension-connector")
        self.assertEqual(routes["excel.exe"][0], "office-object-model-or-addin")

    def test_report_embeds_control_route_matrix(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="chrome.exe",
                title="Inbox - Google Chrome",
                elements=[
                    _element("Edit", name="Search", patterns=("Value",)),
                    _element("Button", name="Submit", patterns=("Invoke",)),
                ],
            )
        ])

        report = WindowsCapabilityProbe(observer=observer).run()
        data = report.to_dict(include_elements=False)

        self.assertEqual(data["route_matrix"]["mode"], "control-route-matrix")
        self.assertEqual(data["route_matrix"]["primary_route_counts"]["browser-devtools-or-extension"], 1)
        self.assertEqual(
            data["windows"][0]["control_route_plan"]["primary_route"]["route_id"],
            "browser-devtools-or-extension",
        )

    def test_probe_marks_window_only_targets_as_low_confidence(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="custom-canvas.exe",
                title="Canvas App",
                elements=[],
            )
        ])

        report = WindowsCapabilityProbe(observer=observer).run()
        window = report.to_dict()["windows"][0]

        self.assertEqual(window["capability_level"], "window_only")
        self.assertLess(window["capability_score"], 40)
        self.assertIn("no_accessible_elements", window["risks"])
        self.assertIn("vision-fallback-last", window["recommended_routes"])

    def test_cli_outputs_json_report_from_static_observer(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="notepad.exe",
                title="Untitled - Notepad",
                elements=[
                    _element("Edit", name="Text editor", patterns=("Value", "Text")),
                ],
            )
        ])

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--json"], observer=observer)

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["mode"], "windows-accessibility-capability")
        self.assertEqual(data["window_count"], 1)
        self.assertEqual(data["windows"][0]["process_name"], "notepad.exe")

    def test_cli_json_output_tolerates_non_gbk_window_text(self):
        class GbkOnlyStdout:
            def __init__(self):
                self.buffer = io.BytesIO()

            def write(self, text):
                text.encode("gbk")
                return len(text)

            def flush(self):
                pass

        observer = StaticAccessibilityObserver([
            _window(
                process_name="browser.exe",
                title="Zero\u200bWidth - Browser",
                elements=[
                    _element("Edit", name="Search\u200bBox", patterns=("Value",)),
                ],
            )
        ])
        fake_stdout = GbkOnlyStdout()

        with patch("sys.stdout", fake_stdout):
            exit_code = main(["--json"], observer=observer)

        self.assertEqual(exit_code, 0)
        data = json.loads(fake_stdout.buffer.getvalue().decode("utf-8"))
        self.assertEqual(data["windows"][0]["window_title"], "Zero\u200bWidth - Browser")

    def test_live_wrapper_pattern_inference_does_not_treat_generic_methods_as_capabilities(self):
        class Info:
            control_type = "Pane"
            name = "Container"
            automation_id = ""
            class_name = ""

        class Rect:
            left = 0
            top = 0
            right = 100
            bottom = 100

        class Wrapper:
            element_info = Info()

            def invoke(self):
                raise RuntimeError("not actually supported")

            def scroll(self):
                raise RuntimeError("not actually supported")

            def texts(self):
                return ["Container"]

            def rectangle(self):
                return Rect()

            def is_enabled(self):
                return True

            def window_text(self):
                return "Container"

        element = _element_from_wrapper(Wrapper())

        self.assertEqual(element.control_type, "Pane")
        self.assertEqual(element.patterns, ())

    def test_text_pattern_alone_is_readable_but_not_semantic_input(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="reader.exe",
                title="Reader",
                elements=[
                    _element("Document", name="Read only document", patterns=("Text",)),
                ],
            )
        ])

        report = WindowsCapabilityProbe(observer=observer).run()
        window = report.to_dict()["windows"][0]

        self.assertEqual(window["input_candidate_count"], 1)
        self.assertEqual(window["semantic_input_count"], 0)
        self.assertEqual(window["text_readable_count"], 1)
        self.assertIn("input_without_semantic_pattern", window["risks"])


if __name__ == "__main__":
    unittest.main()
