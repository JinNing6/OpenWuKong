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


class _FakeIDEBridgeReport:
    def __init__(self, **payload):
        self.payload = dict(payload)

    def to_dict(self):
        return dict(self.payload)


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

    def test_reports_ready_ide_bridge_endpoint_from_explicit_bridge_url(self):
        bridge_calls = []

        def fake_ide_bridge_probe(bridge_url, **kwargs):
            bridge_calls.append((bridge_url, dict(kwargs)))
            return _FakeIDEBridgeReport(
                mode="ide-bridge-capability-capture",
                safety_mode="read_only",
                ok=True,
                control_attempts=0,
                bridge_url=bridge_url,
                metadata={"ide_name": "Cursor", "workspaceFolders": []},
                command_count=2,
                commands=["cursor.chat.submit", "workbench.action.files.save"],
                chat_adapters=[
                    {
                        "adapter_id": "cursor",
                        "label": "Cursor Chat",
                        "command_id": "cursor.chat.submit",
                        "available": True,
                        "available_candidates": ["cursor.chat.submit"],
                    }
                ],
                adapter_mapping={
                    "cursor": {
                        "label": "Cursor Chat",
                        "commandId": "cursor.chat.submit",
                        "available": True,
                        "availableCandidates": ["cursor.chat.submit"],
                        "commandCandidates": ["cursor.chat.submit"],
                    }
                },
            )

        report = run_agent_native_connector_probe(
            agent="cursor",
            project_name="PaoPaoHeZi",
            task_name="desktop-message",
            observer=_observer_with_cursor_target(),
            resolver=_resolver_with_cursor_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            ide_bridge_urls=("http://127.0.0.1:8787",),
            ide_bridge_probe=fake_ide_bridge_probe,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_native_connector_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["endpoint_count"], 1)
        self.assertEqual(data["ready_endpoint_count"], 1)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "ide_bridge")
        self.assertEqual(data["endpoints"][0]["bridge_url"], "http://127.0.0.1:8787")
        self.assertEqual(data["endpoints"][0]["preferred_chat_adapter"], "cursor")
        self.assertEqual(data["endpoints"][0]["adapter_mapping"]["cursor"]["commandId"], "cursor.chat.submit")
        self.assertEqual(bridge_calls[0][0], "http://127.0.0.1:8787")
        self.assertEqual(bridge_calls[0][1]["workspace_path"], "")

    def test_reports_ready_agent_native_bridge_endpoint_from_explicit_bridge_url(self):
        bridge_calls = []
        capability_report = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "pid": 42,
                "hwnd": 70038,
                "window_title": "Codex",
            },
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }

        def fake_agent_native_bridge_probe(request):
            bridge_calls.append(request)
            return _FakeIDEBridgeReport(
                mode="agent-native-bridge-dry-run",
                safety_mode="dry_run",
                ok=True,
                decision="agent_native_bridge_dry_run_ready",
                bridge_send_attempts=0,
                control_attempts=0,
                capability_report=capability_report,
                request=request.to_dict(capability_report),
            )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(task_name="desktop-message"),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            agent_native_bridge_urls=("http://127.0.0.1:18888",),
            agent_native_bridge_probe=fake_agent_native_bridge_probe,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_native_connector_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["endpoint_count"], 1)
        self.assertEqual(data["ready_endpoint_count"], 1)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "agent_native_bridge")
        self.assertEqual(data["endpoints"][0]["bridge_url"], "http://127.0.0.1:18888")
        self.assertEqual(data["endpoints"][0]["preferred_chat_adapter"], "codex")
        self.assertEqual(
            data["endpoints"][0]["send_command_id"],
            "agent_app_conversation.native_bridge_send_message",
        )
        self.assertEqual(bridge_calls[0].agent_id, "codex")
        self.assertEqual(bridge_calls[0].project_name, "openwukong")
        self.assertEqual(bridge_calls[0].expected_app_process_names, ("codex.exe",))
        self.assertTrue(data["endpoints"][0]["metadata"]["app_binding_ready"])

    def test_discovers_agent_native_bridge_endpoint_from_registry_file(self):
        bridge_calls = []
        capability_report = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "pid": 42,
                "hwnd": 70038,
                "window_title": "Codex",
            },
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }

        def fake_agent_native_bridge_probe(request):
            bridge_calls.append(request)
            return _FakeIDEBridgeReport(
                mode="agent-native-bridge-dry-run",
                safety_mode="dry_run",
                ok=True,
                decision="agent_native_bridge_dry_run_ready",
                bridge_send_attempts=0,
                control_attempts=0,
                capability_report=capability_report,
                request=request.to_dict(capability_report),
            )

        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "native-bridges.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "openwukong-native-bridge-registry-v1",
                        "agent_native_bridges": [
                            {
                                "url": "http://127.0.0.1:18888",
                                "agent_id": "codex",
                                "surface_kind": "desktop_app",
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = run_agent_native_connector_probe(
                agent="codex app",
                project_name="openwukong",
                task_name="desktop-message",
                observer=_observer_with_codex_target(hwnd=70038, task_name="desktop-message"),
                resolver=_resolver_with_codex_desktop(),
                process_provider=lambda: (),
                http_probe=_FakeHTTPProbe(),
                agent_native_bridge_registry_paths=(registry_path,),
                agent_native_bridge_probe=fake_agent_native_bridge_probe,
            )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["ready_endpoint_count"], 1)
        self.assertEqual(data["endpoints"][0]["bridge_url"], "http://127.0.0.1:18888")
        self.assertEqual(len(bridge_calls), 1)
        self.assertEqual(bridge_calls[0].agent_id, "codex")

    def test_agent_native_bridge_endpoint_does_not_reuse_wrong_agent(self):
        capability_report = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "pid": 42,
                "hwnd": 70038,
                "window_title": "Codex",
            },
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "cursor", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }

        def fake_agent_native_bridge_probe(request):
            return _FakeIDEBridgeReport(
                mode="agent-native-bridge-dry-run",
                safety_mode="dry_run",
                ok=False,
                decision="agent_native_bridge_agent_not_ready",
                bridge_send_attempts=0,
                control_attempts=0,
                capability_report=capability_report,
                request=request.to_dict(capability_report),
            )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(task_name="desktop-message"),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            agent_native_bridge_urls=("http://127.0.0.1:18888",),
            agent_native_bridge_probe=fake_agent_native_bridge_probe,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["ready_endpoint_count"], 0)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "agent_native_bridge")
        self.assertFalse(data["endpoints"][0]["ready"])

    def test_agent_native_bridge_endpoint_does_not_accept_cli_surface_for_app(self):
        capability_report = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "cli",
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }

        def fake_agent_native_bridge_probe(request):
            return _FakeIDEBridgeReport(
                mode="agent-native-bridge-dry-run",
                safety_mode="dry_run",
                ok=True,
                decision="agent_native_bridge_dry_run_ready",
                bridge_send_attempts=0,
                control_attempts=0,
                capability_report=capability_report,
                request=request.to_dict(capability_report),
            )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(task_name="desktop-message"),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            agent_native_bridge_urls=("http://127.0.0.1:18888",),
            agent_native_bridge_probe=fake_agent_native_bridge_probe,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["ready_endpoint_count"], 0)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "agent_native_bridge")
        self.assertEqual(data["endpoints"][0]["metadata"]["surface_kind"], "cli")
        self.assertFalse(data["endpoints"][0]["ready"])

    def test_agent_native_bridge_endpoint_requires_matching_app_binding(self):
        capability_report = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Claude.exe",
                "pid": 42,
                "hwnd": 70038,
                "window_title": "Claude",
            },
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }

        def fake_agent_native_bridge_probe(request):
            return _FakeIDEBridgeReport(
                mode="agent-native-bridge-dry-run",
                safety_mode="dry_run",
                ok=False,
                decision="agent_native_bridge_app_binding_not_ready",
                bridge_send_attempts=0,
                control_attempts=0,
                capability_report=capability_report,
                request=request.to_dict(capability_report),
            )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(hwnd=70038, task_name="desktop-message"),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            agent_native_bridge_urls=("http://127.0.0.1:18888",),
            agent_native_bridge_probe=fake_agent_native_bridge_probe,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["ready_endpoint_count"], 0)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "agent_native_bridge")
        self.assertFalse(data["endpoints"][0]["ready"])
        self.assertEqual(data["endpoints"][0]["metadata"]["app_binding"]["process_name"], "Claude.exe")
        self.assertFalse(data["endpoints"][0]["metadata"]["app_binding_ready"])
        self.assertEqual(data["endpoints"][0]["error"], "agent_native_bridge_app_binding_not_ready")

    def test_ide_bridge_endpoint_does_not_reuse_cursor_adapter_for_codex_app(self):
        def fake_ide_bridge_probe(bridge_url, **kwargs):
            del kwargs
            return _FakeIDEBridgeReport(
                mode="ide-bridge-capability-capture",
                safety_mode="read_only",
                ok=True,
                control_attempts=0,
                bridge_url=bridge_url,
                metadata={"ide_name": "Cursor", "workspaceFolders": []},
                command_count=1,
                commands=["composer.startComposerPrompt"],
                chat_adapters=[
                    {
                        "adapter_id": "cursor",
                        "label": "Cursor Chat",
                        "command_id": "composer.startComposerPrompt",
                        "available": True,
                        "available_candidates": ["composer.startComposerPrompt"],
                    }
                ],
                adapter_mapping={
                    "cursor": {
                        "label": "Cursor Chat",
                        "commandId": "composer.startComposerPrompt",
                        "available": True,
                        "availableCandidates": ["composer.startComposerPrompt"],
                        "commandCandidates": ["composer.startComposerPrompt"],
                    }
                },
            )

        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            ide_bridge_urls=("http://127.0.0.1:8787",),
            ide_bridge_probe=fake_ide_bridge_probe,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["ready_endpoint_count"], 0)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "ide_bridge")
        self.assertEqual(data["endpoints"][0]["preferred_chat_adapter"], "")
        self.assertFalse(data["endpoints"][0]["ready"])

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

    def test_main_accepts_explicit_ide_bridge_url_without_control_attempts(self):
        bridge_calls = []

        def fake_ide_bridge_probe(bridge_url, **kwargs):
            bridge_calls.append((bridge_url, dict(kwargs)))
            return _FakeIDEBridgeReport(
                ok=True,
                control_attempts=0,
                bridge_url=bridge_url,
                metadata={"ide_name": "Cursor"},
                commands=[],
                chat_adapters=[
                    {
                        "adapter_id": "cursor",
                        "command_id": "cursor.chat.submit",
                        "available": True,
                    }
                ],
                adapter_mapping={
                    "cursor": {
                        "label": "Cursor",
                        "commandId": "cursor.chat.submit",
                        "available": True,
                    }
                },
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "native-probe.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "cursor",
                        "--project-name",
                        "PaoPaoHeZi",
                        "--task-name",
                        "desktop-message",
                        "--ide-bridge-url",
                        "http://127.0.0.1:8787",
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: _resolver_with_cursor_desktop(),
                    observer=_observer_with_cursor_target(),
                    process_provider=lambda: (),
                    http_probe=_FakeHTTPProbe(),
                    ide_bridge_probe=fake_ide_bridge_probe,
                )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["decision"], "agent_native_connector_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["endpoints"][0]["endpoint_type"], "ide_bridge")
        self.assertEqual(bridge_calls[0][0], "http://127.0.0.1:8787")

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


def _observer_with_codex_target(*, hwnd=0, task_name="支持不同 IDE 监工输入"):
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
                        name=task_name,
                        rect=(10, 100, 300, 160),
                        patterns=("Selection",),
                    ),
                ),
            )
        ]
    )


def _observer_with_cursor_target(*, hwnd=70038):
    return StaticAccessibilityObserver(
        [
            AccessibilityWindowSnapshot(
                pid=99496,
                process_name="Cursor.exe",
                window_title="config - PaoPaoHeZi - Cursor",
                hwnd=int(hwnd or 0),
                elements=(
                    AccessibilityElementSnapshot(
                        control_type="ListItem",
                        name="PaoPaoHeZi",
                        rect=(10, 20, 300, 90),
                        patterns=("Selection",),
                    ),
                    AccessibilityElementSnapshot(
                        control_type="ListItem",
                        name="desktop-message",
                        rect=(10, 100, 300, 160),
                        patterns=("Selection",),
                    ),
                    AccessibilityElementSnapshot(
                        control_type="Edit",
                        class_name="aislash-editor-input",
                        name="Plan, Build, / for commands, @ for context",
                        rect=(1290, 164, 1927, 506),
                        patterns=("Value",),
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


def _resolver_with_cursor_desktop():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="running-process",
                        display_name="Cursor",
                        process_name="Cursor.exe",
                        executable_name="Cursor.exe",
                        path="C:/Users/me/AppData/Local/Programs/cursor/Cursor.exe",
                        pid=99496,
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
