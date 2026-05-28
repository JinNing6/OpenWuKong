import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.agent_app_uia_probe import (
    run_agent_app_uia_probe,
    main,
)
from openwukong.evaluation.window_capture import BackgroundWindowCaptureReport


class AgentAppUiaProbeTests(unittest.TestCase):
    def test_codex_app_target_visible_without_composer_requests_bridge(self):
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    window_title="Codex",
                    elements=(
                        AccessibilityElementSnapshot(
                            control_type="ListItem",
                            name="openwukong",
                            rect=(10, -20, 300, 80),
                            patterns=("Selection",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="ListItem",
                            name="支持不同 IDE 监工输入",
                            rect=(10, 90, 300, 150),
                            patterns=("Selection",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="Document",
                            name="Codex",
                            automation_id="RootWebArea",
                            rect=(0, 0, 1200, 900),
                            patterns=("Text",),
                        ),
                    ),
                )
            ]
        )

        report = run_agent_app_uia_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="支持不同 IDE 监工输入",
            observer=observer,
            resolver=_resolver_with_codex_desktop(),
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_app_uia_target_visible_input_not_found")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["matched_window_count"], 1)
        self.assertEqual(data["project_match"]["decision"], "matched_visible")
        self.assertEqual(data["task_match"]["decision"], "matched_visible")
        self.assertEqual(data["composer_candidate_count"], 0)
        self.assertEqual(data["foreground_takeover_request"]["mode"], "foreground-takeover-request")
        self.assertEqual(
            data["foreground_takeover_request"]["action"],
            "send_agent_app_conversation_message",
        )

    def test_semantic_composer_allows_app_uia_ready_decision_without_control(self):
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=84,
                    process_name="Codex.exe",
                    window_title="Codex",
                    elements=(
                        AccessibilityElementSnapshot(
                            control_type="Text",
                            name="openwukong",
                            rect=(10, 10, 300, 40),
                            patterns=("Text",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="Text",
                            name="smoke-test",
                            rect=(10, 50, 300, 90),
                            patterns=("Text",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="Edit",
                            name="Message Codex",
                            value_preview="",
                            rect=(300, 800, 1000, 880),
                            is_enabled=True,
                            patterns=("Value", "Text"),
                        ),
                    ),
                )
            ]
        )

        report = run_agent_app_uia_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="smoke-test",
            observer=observer,
            resolver=_resolver_with_codex_desktop(),
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_app_uia_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["composer_candidate_count"], 1)
        self.assertEqual(data["semantic_composer_count"], 1)
        self.assertEqual(data["foreground_takeover_request"], {})

    def test_text_match_distinguishes_accessible_tree_from_visible_root_bounds(self):
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    window_title="Codex",
                    elements=(
                        AccessibilityElementSnapshot(
                            control_type="Document",
                            name="Codex",
                            automation_id="RootWebArea",
                            rect=(0, 0, 1200, 900),
                            patterns=("Text",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="ListItem",
                            name="openwukong",
                            rect=(10, 1600, 300, 1680),
                            patterns=("Selection",),
                        ),
                    ),
                )
            ]
        )

        report = run_agent_app_uia_probe(
            agent="codex app",
            project_name="openwukong",
            observer=observer,
            resolver=_resolver_with_codex_desktop(),
        )
        data = report.to_dict()

        self.assertEqual(data["project_match"]["decision"], "matched_accessible_tree_only")
        self.assertTrue(data["project_match"]["matched"])
        self.assertFalse(data["project_match"]["visible"])

    def test_captures_matched_app_window_without_control_attempts_when_requested(self):
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=84,
                    process_name="Codex.exe",
                    window_title="Codex",
                    hwnd=7001,
                    elements=(
                        AccessibilityElementSnapshot(
                            control_type="Text",
                            name="openwukong",
                            rect=(10, 10, 300, 40),
                            patterns=("Text",),
                        ),
                        AccessibilityElementSnapshot(
                            control_type="Edit",
                            name="Ask Codex",
                            rect=(300, 800, 1000, 880),
                            is_enabled=True,
                            patterns=("Value",),
                        ),
                    ),
                )
            ]
        )
        capture = FakeBackgroundCaptureProvider()

        with tempfile.TemporaryDirectory() as td:
            screenshot_dir = Path(td)
            report = run_agent_app_uia_probe(
                agent="codex app",
                project_name="openwukong",
                observer=observer,
                resolver=_resolver_with_codex_desktop(),
                screenshot_dir=screenshot_dir,
                window_capture_provider=capture,
            )
            data = report.to_dict()

        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["background_screenshot_count"], 1)
        self.assertTrue(data["background_screenshot_focus_stable"])
        self.assertEqual(capture.events, [7001])
        self.assertEqual(data["background_screenshots"][0]["hwnd"], 7001)
        self.assertTrue(data["background_screenshots"][0]["ok"])
        self.assertFalse(data["background_screenshots"][0]["foreground_changed"])

    def test_main_can_replay_accessibility_json(self):
        payload = {
            "windows": [
                {
                    "pid": 42,
                    "process_name": "Codex.exe",
                    "window_title": "Codex",
                    "class_name": "Chrome_WidgetWin_1",
                    "hwnd": 123,
                    "elements": [
                        {
                            "control_type": "Text",
                            "name": "openwukong",
                            "rect": [0, 0, 100, 40],
                            "patterns": ["Text"],
                            "is_enabled": True,
                        },
                        {
                            "control_type": "Edit",
                            "name": "Ask Codex",
                            "rect": [100, 700, 900, 780],
                            "patterns": ["Value"],
                            "is_enabled": True,
                        },
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "accessibility.json"
            output_path = root / "probe.json"
            input_path.write_text(json.dumps(payload), encoding="utf-16")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--project-name",
                        "openwukong",
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--json",
                    ],
                    resolver_factory=lambda args: _resolver_with_codex_desktop(),
                )
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["decision"], "agent_app_uia_ready")
        self.assertEqual(data["matched_window_count"], 1)

    def test_main_writes_background_screenshot_artifact_when_requested(self):
        payload = {
            "windows": [
                {
                    "pid": 42,
                    "process_name": "Codex.exe",
                    "window_title": "Codex",
                    "class_name": "Chrome_WidgetWin_1",
                    "hwnd": 123,
                    "elements": [
                        {
                            "control_type": "Text",
                            "name": "openwukong",
                            "rect": [0, 0, 100, 40],
                            "patterns": ["Text"],
                            "is_enabled": True,
                        }
                    ],
                }
            ]
        }
        capture = FakeBackgroundCaptureProvider()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "accessibility.json"
            output_path = root / "probe.json"
            screenshot_dir = root / "screenshots"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--project-name",
                        "openwukong",
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--screenshot-dir",
                        str(screenshot_dir),
                        "--json",
                    ],
                    resolver_factory=lambda args: _resolver_with_codex_desktop(),
                    window_capture_provider=capture,
                )
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(capture.events, [123])
        self.assertEqual(data["background_screenshot_count"], 1)
        self.assertEqual(data["background_screenshots"][0]["mode"], "fake-background-capture")


def _resolver_with_codex_desktop():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="running-process",
                        display_name="Codex",
                        process_name="Codex.exe",
                        executable_name="Codex.exe",
                        path="C:/Users/me/AppData/Local/OpenAI/Codex/app/Codex.exe",
                        pid=42,
                    ),
                ]
            ),
        )
    )


class FakeBackgroundCaptureProvider:
    def __init__(self):
        self.events = []

    def capture_window(self, hwnd: int, output_path: Path) -> BackgroundWindowCaptureReport:
        self.events.append(int(hwnd))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake screenshot")
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=True,
            mode="fake-background-capture",
            width=800,
            height=600,
            foreground_hwnd_before=9001,
            foreground_hwnd_after=9001,
        )


if __name__ == "__main__":
    unittest.main()
