import subprocess
import sys
import tempfile
import http.server
import json
import socketserver
import threading
import unittest
from pathlib import Path

from openwukong.connectors import (
    ConnectorActionResult,
    GitCommandConnector,
    ConnectorManager,
    ConnectorTarget,
    SessionConnector,
    TerminalCommandConnector,
)
from openwukong.control.command_planner import CommandPlanIntent
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


class _FakeBrowserActionReport:
    def __init__(self, *, ok=True, control_attempts=1, error="", extra=None):
        self.ok = ok
        self.error = error
        self._control_attempts = control_attempts
        self.extra = dict(extra or {})

    def to_dict(self):
        data = {
            "mode": "browser-devtools-action",
            "safety_mode": "gated_browser_devtools_action",
            "ok": self.ok,
            "control_allowed": True,
            "control_attempts": self._control_attempts,
            "action": "navigate_url",
            "error": self.error,
        }
        data.update(self.extra)
        return data


class _FakeBrowserActionRunner:
    def __init__(self, report=None):
        self.report = report or _FakeBrowserActionReport()
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return self.report


class _FakeTerminalConnector(SessionConnector):
    connector_id = "terminal"
    route_id = "terminal-native-session"
    display_name = "Fake Terminal"

    def __init__(self):
        self.calls = []

    def supports_target(self, target: ConnectorTarget) -> bool:
        return bool(target.workspace_path)

    def read_conversation(self, target: ConnectorTarget) -> str:
        del target
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        self.calls.append(
            {
                "workspace_path": target.workspace_path,
                "message": message,
                "cooldown": cooldown,
            }
        )
        return ConnectorActionResult(
            success=True,
            connector_id=self.connector_id,
            action="send_message",
            action_key="terminal:1",
            payload={
                "mode": "connector-action",
                "control_attempts": 1,
                "stdout": "terminal-ok",
            },
        )


class _AgentNativeBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []
    capabilities_payload = {}
    send_payload = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))
        if self.path == "/v1/agent/capabilities":
            self._send_json(dict(self.__class__.capabilities_payload))
            return
        if self.path == "/v1/agent/chat":
            response = dict(self.__class__.send_payload)
            response.setdefault(
                "readbackText",
                f"{payload.get('agent_id', '')}\n{payload.get('message', '')}",
            )
            self._send_json(response)
            return
        self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=404)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _WeChatNativeBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []
    capabilities_payload = {}
    send_payload = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))
        if self.path == "/v1/wechat/capabilities":
            self._send_json(dict(self.__class__.capabilities_payload))
            return
        if self.path == "/v1/wechat/send":
            response = dict(self.__class__.send_payload)
            response.setdefault(
                "readbackText",
                f"File Transfer Assistant\n{payload.get('message', '')}",
            )
            self._send_json(response)
            return
        self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=404)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements=()):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=tuple(elements),
    )


class ControlFabricExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._agent_server = socketserver.TCPServer(("127.0.0.1", 0), _AgentNativeBridgeHandler)
        cls._agent_thread = threading.Thread(target=cls._agent_server.serve_forever, daemon=True)
        cls._agent_thread.start()
        cls.agent_native_bridge_url = f"http://127.0.0.1:{cls._agent_server.server_address[1]}"
        cls._wechat_server = socketserver.TCPServer(("127.0.0.1", 0), _WeChatNativeBridgeHandler)
        cls._wechat_thread = threading.Thread(target=cls._wechat_server.serve_forever, daemon=True)
        cls._wechat_thread.start()
        cls.wechat_native_bridge_url = f"http://127.0.0.1:{cls._wechat_server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._agent_server.shutdown()
        cls._agent_server.server_close()
        cls._agent_thread.join(timeout=2)
        cls._wechat_server.shutdown()
        cls._wechat_server.server_close()
        cls._wechat_thread.join(timeout=2)

    def setUp(self):
        _AgentNativeBridgeHandler.requests = []
        _AgentNativeBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "executable_path": "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                "pid": 6516,
                "window_title": "Codex",
            },
            "requires_foreground": False,
            "window_input_required": False,
            "capabilities": [
                "agent_app_conversation.native_bridge_send_message",
                "agent_app_conversation.read_transcript",
            ],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }
        _AgentNativeBridgeHandler.send_payload = {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }
        _WeChatNativeBridgeHandler.requests = []
        _WeChatNativeBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "clipboard_required": False,
            "capabilities": ["wechat.conversation.send_message"],
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
                }
            ],
        }
        _WeChatNativeBridgeHandler.send_payload = {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def test_execute_requires_explicit_control_permission(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-execution")
        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertEqual(runner.calls, [])

    def test_execute_writes_control_trajectory_when_root_is_provided(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        with tempfile.TemporaryDirectory() as tmp:
            report = fabric.execute(
                ConnectorTarget(
                    process_name="chrome.exe",
                    window_title="about:blank - Google Chrome",
                    resource_url="about:blank",
                    debugger_url="http://127.0.0.1:9222",
                ),
                ControlIntent(action="navigate_url", url="https://example.test/search"),
                browser_action_runner=runner,
                trajectory_root=tmp,
                trajectory_metadata={"test_id": "explicit-permission-block"},
            )
            data = report.to_dict()
            manifest_path = Path(data["trajectory_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertFalse(data["ok"])
        self.assertEqual(data["trajectory_error"], "")
        self.assertEqual(manifest_path.name, "manifest.json")
        self.assertEqual(manifest["mode"], "control-trajectory")
        self.assertEqual(manifest["scenario"], "control-fabric-execute")
        self.assertEqual(manifest["metadata"]["test_id"], "explicit-permission-block")
        self.assertEqual(manifest["step_count"], 2)
        self.assertEqual(
            [step["phase"] for step in manifest["steps"]],
            ["dispatch", "execution"],
        )
        self.assertEqual(runner.calls, [])

    def test_execute_trajectory_attaches_action_report_artifacts(self):
        fabric = ControlFabric.with_default_connectors()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_report = root / "action-report.json"
            screenshot = root / "background.png"
            action_report.write_text("{}", encoding="utf-8")
            screenshot.write_bytes(b"fake screenshot")
            runner = _FakeBrowserActionRunner(
                _FakeBrowserActionReport(
                    extra={
                        "artifact_path": str(action_report),
                        "background_screenshots": [
                            {
                                "ok": True,
                                "output_path": str(screenshot),
                            }
                        ],
                    }
                )
            )

            report = fabric.execute(
                ConnectorTarget(
                    process_name="chrome.exe",
                    window_title="about:blank - Google Chrome",
                    resource_url="about:blank",
                    debugger_url="http://127.0.0.1:9222",
                ),
                ControlIntent(action="navigate_url", url="https://example.test/search"),
                allow_control=True,
                browser_action_runner=runner,
                trajectory_root=root / "trajectories",
            )
            manifest = json.loads(
                Path(report.trajectory_path).read_text(encoding="utf-8")
            )

        execution_step = manifest["steps"][1]
        artifacts = {
            artifact["role"]: artifact
            for artifact in execution_step["artifacts"]
        }
        self.assertEqual(execution_step["phase"], "execution")
        self.assertEqual(
            set(artifacts),
            {"artifact_path", "background_screenshots_output_path"},
        )
        self.assertEqual(artifacts["artifact_path"]["media_type"], "application/json")
        self.assertEqual(
            artifacts["background_screenshots_output_path"]["media_type"],
            "image/png",
        )
        self.assertEqual(len(artifacts["artifact_path"]["sha256"]), 64)
        self.assertEqual(
            len(artifacts["background_screenshots_output_path"]["sha256"]),
            64,
        )

    def test_execute_runs_ready_browser_devtools_action_behind_dispatch_gate(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(
                action="navigate_url",
                url="https://www.bing.com/search?q=openwukong",
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "browser-devtools-or-extension")
        self.assertEqual(data["selected_connector_id"], "browser")
        self.assertEqual(data["action_report"]["mode"], "browser-devtools-action")
        self.assertEqual(data["transport_gate_decision"], "allow")
        self.assertEqual(
            data["dispatch_report"]["transport_capability_level"],
            "background-native",
        )
        self.assertEqual(len(runner.calls), 1)
        call = runner.calls[0]
        self.assertEqual(call["debugger_url"], "http://127.0.0.1:9222")
        self.assertEqual(call["window_title"], "about:blank - Google Chrome")
        self.assertEqual(call["resource_url"], "about:blank")
        self.assertEqual(call["action"], "navigate_url")
        self.assertEqual(call["url"], "https://www.bing.com/search?q=openwukong")

    def test_execute_fails_non_command_action_when_no_foreground_contract_is_violated(self):
        runner = _FakeBrowserActionRunner(
            _FakeBrowserActionReport(
                ok=True,
                extra={
                    "foreground_focus_stable": False,
                    "keyboard_input_attempts": 1,
                    "clipboard_write_attempts": 1,
                },
            )
        )
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["decision"], "failed")
        self.assertTrue(data["error"].startswith("no_foreground_contract_violation:"))
        self.assertFalse(data["no_foreground_validation"]["ok"])
        self.assertIn(
            "foreground_focus_changed",
            data["no_foreground_validation"]["violations"],
        )
        self.assertIn(
            "keyboard_input_not_allowed",
            data["no_foreground_validation"]["violations"],
        )
        self.assertIn(
            "clipboard_write_not_allowed",
            data["no_foreground_validation"]["violations"],
        )
        self.assertEqual(len(runner.calls), 1)

    def test_execute_blocks_ready_browser_action_when_owned_session_is_required(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors(
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "owned_session_required")
        self.assertTrue(data["ownership_required"])
        self.assertFalse(data["ownership"]["owned"])
        self.assertEqual(runner.calls, [])

    def test_execute_allows_owned_browser_action_matched_from_ownership_index(self):
        runner = _FakeBrowserActionRunner()
        ownership = SessionOwnership(
            owned=True,
            ownership_source="session_readiness_manifest",
            manifest_path="browser.json",
            route_id="browser-devtools-or-extension",
            connector_id="browser",
            action_id="launch_browser_devtools_isolated",
            pid=4242,
            endpoint="http://127.0.0.1:9222",
            profile_path="E:/tmp/openwukong-owned-browser",
            cleanup_ready=True,
        )
        fabric = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["manifest_path"], "browser.json")
        self.assertEqual(len(runner.calls), 1)

    def test_execute_runs_ready_terminal_connector_through_fabric(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(
                action="run_command",
                text="pwd",
                preferred_route_id="terminal-native-session",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "terminal-native-session")
        self.assertEqual(data["selected_connector_id"], "terminal")
        self.assertEqual(data["action_report"]["connector_id"], "terminal")
        self.assertEqual(data["action_report"]["payload"]["stdout"], "terminal-ok")
        self.assertEqual(connector.calls[0]["message"], "pwd")

    def test_execute_does_not_apply_desktop_no_foreground_hard_gate_to_terminal_route(self):
        class ViolatingTerminalConnector(_FakeTerminalConnector):
            def send_message(
                self,
                target: ConnectorTarget,
                message: str,
                cooldown: float = 10.0,
            ) -> ConnectorActionResult:
                result = super().send_message(target, message, cooldown=cooldown)
                payload = dict(result.payload or {})
                payload["keyboard_input_attempts"] = 1
                payload["foreground_focus_stable"] = False
                return ConnectorActionResult(
                    success=True,
                    connector_id=self.connector_id,
                    action="send_message",
                    action_key="terminal:violating-payload",
                    payload=payload,
                )

        connector = ViolatingTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(
                action="run_command",
                text="pwd",
                preferred_route_id="terminal-native-session",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "terminal-native-session")
        self.assertFalse(data["no_foreground_validation"]["ok"])
        self.assertIn(
            "keyboard_input_not_allowed",
            data["no_foreground_validation"]["violations"],
        )

    def test_execute_runs_owned_agent_native_bridge_without_window_input(self):
        ownership = SessionOwnership(
            owned=True,
            ownership_source="test-agent-native-bridge",
            manifest_path="agent-native.json",
            route_id="app-native-bridge-required",
            connector_id="agent-native-bridge",
            action_id="bind_codex_native_bridge",
            endpoint=self.agent_native_bridge_url,
            workspace_root="E:/ideaProjects/agent/openwukong",
            cleanup_ready=False,
        )
        fabric = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="Codex.exe",
                window_title="Codex",
                project_name="openwukong",
                session_id="desktop-message",
                workspace_path="E:/ideaProjects/agent/openwukong",
                agent_native_bridge_url=self.agent_native_bridge_url,
            ),
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_AGENT_NATIVE_FABRIC: PASS",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="agent-native-bridge",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "app-native-bridge-required")
        self.assertEqual(data["selected_connector_id"], "agent-native-bridge")
        self.assertEqual(data["transport_gate_decision"], "allow")
        self.assertEqual(data["dispatch_report"]["transport_capability_level"], "background-native")
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["action_report"]["connector_id"], "agent-native-bridge")
        self.assertEqual(
            data["action_report"]["payload"]["decision"],
            "agent_native_bridge_send_accepted",
        )
        self.assertEqual(data["action_report"]["payload"]["window_input_attempts"], 0)
        self.assertEqual(data["action_report"]["payload"]["keyboard_input_attempts"], 0)
        self.assertEqual(data["action_report"]["payload"]["clipboard_write_attempts"], 0)
        self.assertEqual(
            [item[0] for item in _AgentNativeBridgeHandler.requests],
            ["/v1/agent/capabilities", "/v1/agent/chat"],
        )

    def test_wechat_native_bridge_requires_background_screenshot_evidence(self):
        fabric = ControlFabric.with_default_connectors()

        report = fabric.dispatch(
            ConnectorTarget(
                process_name="Weixin.exe",
                window_title="File Transfer Assistant - WeChat",
                conversation_name="File Transfer Assistant",
                wechat_native_bridge_url=self.wechat_native_bridge_url,
            ),
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_WECHAT_FABRIC: PASS",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "connector_required")
        self.assertEqual(data["selected_route"], "app-native-bridge-required")
        self.assertIn("wechat-native-bridge", data["candidate_connector_ids"])
        self.assertFalse(data["connector_ready"])
        self.assertEqual(
            data["reason"],
            "connector_installed_session_not_ready:app-native-bridge-required",
        )

    def test_execute_runs_wechat_native_bridge_without_window_input(self):
        ownership = SessionOwnership(
            owned=True,
            ownership_source="wechat_native_bridge_registry",
            route_id="app-native-bridge-required",
            connector_id="wechat-native-bridge",
            endpoint=self.wechat_native_bridge_url,
            cleanup_ready=True,
        )
        fabric = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="Weixin.exe",
                window_title="File Transfer Assistant - WeChat",
                conversation_name="File Transfer Assistant",
                wechat_native_bridge_url=self.wechat_native_bridge_url,
                background_screenshot_focus_stable=True,
                background_screenshot_count=1,
                background_screenshot_success_count=1,
            ),
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_WECHAT_FABRIC: PASS",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_connector_id"], "wechat-native-bridge")
        self.assertEqual(data["selected_route"], "app-native-bridge-required")
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["action_report"]["connector_id"], "wechat-native-bridge")
        payload = data["action_report"]["payload"]
        self.assertEqual(payload["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(payload["send_attempts"], 1)
        self.assertEqual(payload["native_call_attempts"], 1)
        self.assertEqual(payload["window_input_attempts"], 0)
        self.assertEqual(payload["keyboard_input_attempts"], 0)
        self.assertEqual(payload["clipboard_write_attempts"], 0)
        self.assertEqual(
            [item[0] for item in _WeChatNativeBridgeHandler.requests],
            ["/v1/wechat/capabilities", "/v1/wechat/send"],
        )

    def test_execute_does_not_call_connector_when_side_effect_gate_blocks(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        with tempfile.TemporaryDirectory() as td:
            report = fabric.execute(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="PowerShell",
                    workspace_path=td,
                ),
                ControlIntent(
                    action="run_command",
                    text="Write-Output unsafe-write",
                    preferred_route_id="terminal-native-session",
                    side_effect_policy=build_side_effect_policy(
                        blocked_effect_ids=("file_modify.modify_file",),
                    ),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "side_effect_confirmation_required")
        self.assertEqual(data["dispatch_report"]["decision"], "side_effect_confirmation_required")
        self.assertEqual(connector.calls, [])

    def test_execute_blocks_terminal_connector_when_owned_session_is_required(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(
                action="run_command",
                text="pwd",
                preferred_route_id="terminal-native-session",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["error"], "owned_session_required")
        self.assertEqual(connector.calls, [])

    def test_execute_refuses_browser_action_when_dispatch_gate_is_not_ready(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Chrome",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "dispatch_gate_not_ready")
        self.assertEqual(data["dispatch_report"]["decision"], "connector_required")
        self.assertEqual(runner.calls, [])

    def test_execute_blocks_weak_app_surface_without_native_connector_before_action_runner(self):
        fabric = ControlFabric()

        report = fabric.execute(
            _window(
                "Weixin.exe",
                "微信",
                [_element("Pane"), _element("TitleBar")],
            ),
            ControlIntent(action="send_message", text="probe"),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "no_deterministic_route")
        self.assertEqual(data["transport_gate_decision"], "allow")
        self.assertEqual(data["dispatch_report"]["decision"], "blocked")
        self.assertEqual(data["dispatch_report"]["reason"], "no_deterministic_route")
        self.assertFalse(data["dispatch_report"]["background_safe"])

    def test_execute_blocks_no_deterministic_transport_before_generic_dispatch_failure(self):
        fabric = ControlFabric()

        report = fabric.execute(
            _window("NVIDIA Overlay.exe", "NVIDIA GeForce Overlay", []),
            ControlIntent(action="write_text", text="probe"),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "no_deterministic_route")
        self.assertEqual(data["transport_gate_decision"], "blocked_transport_capability")
        self.assertEqual(data["dispatch_report"]["decision"], "blocked")
        self.assertEqual(data["dispatch_report"]["reason"], "no_deterministic_route")
        self.assertEqual(
            data["dispatch_report"]["transport_capability_level"],
            "blocked",
        )
        self.assertEqual(
            data["dispatch_report"]["transport_capability"]["blocking_reason"],
            "no_deterministic_transport",
        )

    def test_execute_command_intent_requires_explicit_control_permission(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    effects=("read",),
                )
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-command-execution")
        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertTrue(data["command_plan"]["ok"])
        self.assertEqual(data["action_report"], {})

    def test_execute_command_intent_runs_planned_argv_through_runner(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('fabric-planned-runner')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["command_plan"]["profile_id"], "read-only")
        self.assertIn("fabric-planned-runner", data["action_report"]["stdout"])

    def test_execute_command_intent_blocks_invalid_plan_before_runner(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                {
                    "operation": "raw.argv",
                    "workspace_root": td,
                    "command": "git status && git diff",
                },
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "shell_command_not_allowed")
        self.assertFalse(data["command_plan"]["ok"])

    def test_execute_command_intent_requires_owned_workspace_when_configured(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric(require_owned_session_for_execution=True)
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "owned_session_required")
        self.assertTrue(data["ownership_required"])
        self.assertFalse(data["ownership"]["owned"])
        self.assertEqual(data["control_attempts"], 0)

    def test_execute_command_intent_binds_owned_workspace_from_fabric_index(self):
        with tempfile.TemporaryDirectory() as td:
            ownership = _workspace_ownership(td, route_id="terminal-native-session", connector_id="terminal")
            fabric = ControlFabric(
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('owned-fabric-plan')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["connector_id"], "terminal")
        self.assertIn("owned-fabric-plan", data["action_report"]["stdout"])

    def test_execute_runs_real_terminal_connector_when_owned_session_matches(self):
        with tempfile.TemporaryDirectory(dir=".") as td:
            ownership = _workspace_ownership(td, route_id="terminal-native-session", connector_id="terminal")
            fabric = ControlFabric(
                connector_manager=ConnectorManager(
                    [TerminalCommandConnector(command_timeout=5.0)]
                ),
                require_connector_session_ready=True,
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )

            report = fabric.execute(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="PowerShell",
                    workspace_path=td,
                ),
                ControlIntent(
                    action="run_command",
                    text="Write-Output fabric-owned-terminal",
                    preferred_route_id="terminal-native-session",
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["selected_connector_id"], "terminal")
        self.assertIn("fabric-owned-terminal", data["action_report"]["payload"]["stdout"])

    def test_execute_runs_real_git_connector_when_owned_session_matches(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True, text=True)
            ownership = _workspace_ownership(td, route_id="git-cli", connector_id="git")
            fabric = ControlFabric(
                connector_manager=ConnectorManager([GitCommandConnector(command_timeout=5.0)]),
                require_connector_session_ready=True,
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )

            report = fabric.execute(
                ConnectorTarget(
                    process_name="git.exe",
                    window_title="git",
                    workspace_path=td,
                    workspace_hint="git",
                ),
                ControlIntent(
                    action="run_command",
                    text="git status --short",
                    preferred_route_id="git-cli",
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["selected_connector_id"], "git")
        self.assertEqual(data["action_report"]["payload"]["exit_code"], 0)


def _workspace_ownership(workspace_root: str, *, route_id: str, connector_id: str) -> SessionOwnership:
    return SessionOwnership(
        owned=True,
        ownership_source="session_readiness_manifest",
        manifest_path=f"{connector_id}.json",
        route_id=route_id,
        connector_id=connector_id,
        action_id=f"bind_{connector_id}_workspace",
        workspace_root=workspace_root,
        cleanup_ready=False,
    )


if __name__ == "__main__":
    unittest.main()
