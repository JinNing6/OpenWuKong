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
    _merge_win32_fallback_windows,
    _merge_process_only_fallback_windows,
    _process_only_fallback_windows_from_rows,
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

    def test_win32_fallback_adds_top_level_window_missing_from_uia(self):
        existing = AccessibilityWindowSnapshot(
            pid=30608,
            process_name="Codex.exe",
            window_title="Codex",
            class_name="Chrome_WidgetWin_1",
            hwnd=658028,
            elements=(_element("Document", name="Codex", patterns=("Text",)),),
        )
        duplicate = AccessibilityWindowSnapshot(
            pid=30608,
            process_name="codex",
            window_title="Codex",
            class_name="Chrome_WidgetWin_1",
            hwnd=658028,
            elements=(),
        )
        missed = AccessibilityWindowSnapshot(
            pid=42028,
            process_name="claude",
            window_title="Claude",
            class_name="Chrome_WidgetWin_1",
            hwnd=855894,
            elements=(),
        )

        merged = _merge_win32_fallback_windows(
            (existing,),
            (duplicate, missed),
            max_windows=10,
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].process_name, "Codex.exe")
        self.assertEqual(merged[0].element_count, 1)
        self.assertEqual(merged[1].process_name, "claude")
        self.assertEqual(merged[1].window_title, "Claude")
        self.assertEqual(merged[1].element_count, 0)
        self.assertEqual(merged[1].hwnd, 855894)

    def test_process_only_fallback_keeps_running_wechat_visible_to_readiness(self):
        fallback = _process_only_fallback_windows_from_rows(
            (
                {"pid": 4628, "name": "Weixin.exe", "executable_path": "E:/software/Weixin/Weixin.exe"},
                {"pid": 16444, "name": "Cursor.exe", "executable_path": "E:/cursor/Cursor.exe"},
                {"pid": 9999, "name": "notepad.exe", "executable_path": "C:/Windows/notepad.exe"},
            )
        )

        process_names = {window.process_name for window in fallback}
        wechat = next(window for window in fallback if window.process_name == "Weixin.exe")

        self.assertIn("Weixin.exe", process_names)
        self.assertIn("Cursor.exe", process_names)
        self.assertNotIn("notepad.exe", process_names)
        self.assertEqual(wechat.window_title, "Weixin.exe")
        self.assertEqual(wechat.hwnd, 0)
        self.assertEqual(wechat.element_count, 0)
        self.assertEqual(wechat.capability_level(), "window_only")
        self.assertEqual(wechat.recommended_routes()[0], "app-native-bridge-required")
        self.assertIn("process_only_no_top_level_window", wechat.scan_error)

    def test_process_only_fallback_routes_claude_as_agent_app_native_bridge_required(self):
        fallback = _process_only_fallback_windows_from_rows(
            (
                {
                    "pid": 13176,
                    "name": "claude.exe",
                    "executable_path": "C:/Users/me/AppData/Local/Programs/Claude/Claude.exe",
                },
            )
        )

        report = WindowsCapabilityProbe(observer=StaticAccessibilityObserver(fallback)).run()
        window = report.to_dict(include_elements=False)["windows"][0]

        self.assertEqual(window["process_name"], "claude.exe")
        self.assertEqual(window["recommended_routes"][0], "app-native-bridge-required")
        self.assertEqual(window["control_route_plan"]["app_family"], "agent-app")
        self.assertEqual(
            window["control_route_plan"]["primary_route"]["route_id"],
            "app-native-bridge-required",
        )
        self.assertEqual(
            window["control_route_plan"]["control_decision"],
            "block_until_deterministic_route",
        )

    def test_process_only_fallback_does_not_duplicate_existing_process_window(self):
        existing = AccessibilityWindowSnapshot(
            pid=4628,
            process_name="Weixin.exe",
            window_title="文件传输助手 - 微信",
            hwnd=1001,
        )
        fallback = _process_only_fallback_windows_from_rows(
            ({"pid": 4628, "name": "Weixin.exe"},)
        )

        merged = _merge_process_only_fallback_windows(
            (existing,),
            fallback,
            max_windows=10,
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].window_title, "文件传输助手 - 微信")


if __name__ == "__main__":
    unittest.main()
