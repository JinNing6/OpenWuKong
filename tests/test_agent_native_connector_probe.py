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
from openwukong.evaluation.agent_native_connector_probe import (
    NativeProcessSnapshot,
    run_agent_native_connector_probe,
    main,
)
from openwukong.evaluation.window_capture import BackgroundWindowCaptureReport


class _FakeHTTPProbe:
    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def get_json(self, url, timeout=0.2):
        del timeout
        self.calls.append(url)
        if url not in self.responses:
            raise OSError("connection_failed")
        return self.responses[url]


class AgentNativeConnectorProbeTests(unittest.TestCase):
    def test_reports_ready_when_remote_debugging_endpoint_is_reachable(self):
        observer = _observer_with_codex_target()
        http_probe = _FakeHTTPProbe(
            {
                "http://127.0.0.1:9333/json/version": {
                    "Browser": "Chrome/126.0 Electron",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/abc",
                },
                "http://127.0.0.1:9333/json/list": [
                    {
                        "id": "page-1",
                        "type": "page",
                        "title": "Codex",
                        "url": "app://codex/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-1",
                    }
                ],
            }
        )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="支持不同 IDE 监工输入",
            observer=observer,
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (
                NativeProcessSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    executable_path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    command_line=(
                        "Codex.exe --remote-debugging-port=9333 "
                        "--user-data-dir=C:/Users/me/AppData/Roaming/Codex"
                    ),
                ),
            ),
            http_probe=http_probe,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_native_connector_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["app_uia_probe"]["project_match"]["decision"], "matched_visible")
        self.assertEqual(data["endpoint_count"], 1)
        self.assertEqual(data["ready_endpoint_count"], 1)
        self.assertEqual(data["endpoints"][0]["debugger_url"], "http://127.0.0.1:9333")
        self.assertEqual(data["endpoints"][0]["target_count"], 1)

    def test_target_visible_but_no_debug_port_reports_native_connector_not_exposed(self):
        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="支持不同 IDE 监工输入",
            observer=_observer_with_codex_target(),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (
                NativeProcessSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    executable_path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    command_line="Codex.exe",
                ),
            ),
            http_probe=_FakeHTTPProbe(),
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_native_connector_not_exposed")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["endpoint_count"], 0)
        self.assertEqual(data["app_uia_probe"]["target_matched"], True)

    def test_no_debug_port_takes_precedence_over_target_visibility(self):
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    window_title="Codex",
                    elements=(),
                )
            ]
        )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="missing-task",
            observer=observer,
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (
                NativeProcessSnapshot(
                    pid=42,
                    process_name="Codex.exe",
                    executable_path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    command_line="Codex.exe",
                ),
            ),
            http_probe=_FakeHTTPProbe(),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "agent_native_connector_not_exposed")
        self.assertFalse(data["app_uia_probe"]["target_matched"])

    def test_passes_background_screenshot_options_to_app_uia_probe(self):
        capture = _FakeBackgroundCaptureProvider()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_native_connector_probe(
                agent="codex app",
                project_name="openwukong",
                task_name="鏀寔涓嶅悓 IDE 鐩戝伐杈撳叆",
                observer=_observer_with_codex_target(hwnd=7101),
                resolver=_resolver_with_codex_desktop(),
                process_provider=lambda: (),
                http_probe=_FakeHTTPProbe(),
                screenshot_dir=root / "screenshots",
                window_capture_provider=capture,
            )
            data = report.to_dict()

        self.assertEqual(capture.events, [7101])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["app_uia_probe"]["background_screenshot_count"], 1)
        self.assertTrue(data["app_uia_probe"]["background_screenshot_focus_stable"])

    def test_main_writes_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "native-probe.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "支持不同 IDE 监工输入",
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: _resolver_with_codex_desktop(),
                    observer=_observer_with_codex_target(),
                    process_provider=lambda: (),
                    http_probe=_FakeHTTPProbe(),
                )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["mode"], "agent-native-connector-probe")
        self.assertEqual(data["decision"], "agent_native_connector_not_exposed")

    def test_main_writes_screenshot_metadata_when_requested(self):
        capture = _FakeBackgroundCaptureProvider()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "native-probe.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "鏀寔涓嶅悓 IDE 鐩戝伐杈撳叆",
                        "--screenshot-dir",
                        str(root / "screenshots"),
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: _resolver_with_codex_desktop(),
                    observer=_observer_with_codex_target(hwnd=7201),
                    process_provider=lambda: (),
                    http_probe=_FakeHTTPProbe(),
                    window_capture_provider=capture,
                )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(capture.events, [7201])
        self.assertEqual(data["app_uia_probe"]["background_screenshot_count"], 1)


def _observer_with_codex_target(*, hwnd=0):
    return StaticAccessibilityObserver(
        [
            AccessibilityWindowSnapshot(
                pid=42,
                process_name="Codex.exe",
                window_title="Codex",
                hwnd=int(hwnd or 0),
                elements=(
                    AccessibilityElementSnapshot(
                        control_type="ListItem",
                        name="openwukong",
                        rect=(10, 20, 300, 90),
                        patterns=("Selection",),
                    ),
                    AccessibilityElementSnapshot(
                        control_type="ListItem",
                        name="支持不同 IDE 监工输入",
                        rect=(10, 100, 300, 160),
                        patterns=("Selection",),
                    ),
                ),
            )
        ]
    )


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
                        path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                        pid=42,
                    ),
                ]
            ),
        )
    )


class _FakeBackgroundCaptureProvider:
    def __init__(self):
        self.events = []

    def capture_window(self, hwnd: int, output_path: Path) -> BackgroundWindowCaptureReport:
        self.events.append(int(hwnd))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake")
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=True,
            mode="fake-background-capture",
            width=800,
            height=600,
            foreground_hwnd_before=1001,
            foreground_hwnd_after=1001,
        )


if __name__ == "__main__":
    unittest.main()
