import http.server
import json
import socketserver
import threading
import unittest

from openwukong.control.agent_native_probe_binding import (
    agent_native_fabric_bindings_from_probe_report,
    ownership_index_from_agent_native_probe_report,
)
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.evaluation.agent_native_connector_probe import run_agent_native_connector_probe
from tests.test_agent_native_connector_probe import (
    _FakeHTTPProbe,
    _observer_with_codex_target,
    _resolver_with_codex_desktop,
)


class _NativeBridgeHandler(http.server.BaseHTTPRequestHandler):
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
                f"{payload.get('agent_id', '')}\n"
                f"{payload.get('project_name', '')}\n"
                f"{payload.get('task_name', '')}\n"
                f"{payload.get('message', '')}",
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


class AgentNativeProbeBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _NativeBridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _NativeBridgeHandler.requests = []
        _NativeBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "executable_path": "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                "pid": 42,
                "hwnd": 70038,
                "window_title": "Codex",
                "workspace_path": "E:/ideaProjects/agent/openwukong",
            },
            "capabilities": [
                "agent_app_conversation.native_bridge_send_message",
                "agent_app_conversation.read_transcript",
            ],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }
        _NativeBridgeHandler.send_payload = {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def test_ready_probe_endpoint_binds_to_fabric_and_executes_background_send(self):
        report = run_agent_native_connector_probe(
            agent="codex app",
            project_name="openwukong",
            task_name="desktop-message",
            observer=_observer_with_codex_target(hwnd=70038, task_name="desktop-message"),
            resolver=_resolver_with_codex_desktop(),
            process_provider=lambda: (),
            http_probe=_FakeHTTPProbe(),
            agent_native_bridge_urls=(self.bridge_url,),
            request_timeout=2.0,
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        probe_data = report.to_dict()

        self.assertTrue(probe_data["ok"], probe_data)
        self.assertEqual(probe_data["decision"], "agent_native_connector_ready")
        self.assertEqual(probe_data["ready_endpoint_count"], 1)

        bindings = agent_native_fabric_bindings_from_probe_report(
            report,
            manifest_path="probe-agent-native.json",
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        self.assertEqual(len(bindings), 1)
        binding = bindings[0]
        self.assertTrue(binding.ownership.owned)
        self.assertEqual(binding.ownership.connector_id, "agent-native-bridge")
        self.assertEqual(binding.ownership.endpoint, self.bridge_url)
        self.assertEqual(binding.target.agent_native_bridge_url, self.bridge_url)
        self.assertEqual(binding.target.process_name, "Codex.exe")

        fabric = ControlFabric.with_default_connectors(
            ownership_index=ownership_index_from_agent_native_probe_report(
                report,
                manifest_path="probe-agent-native.json",
                workspace_path="E:/ideaProjects/agent/openwukong",
            ),
            require_owned_session_for_execution=True,
        )
        execution = fabric.execute(
            binding.target,
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_PROBE_TO_FABRIC: PASS",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="agent-native-bridge",
            ),
            allow_control=True,
        )
        data = execution.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["selected_connector_id"], "agent-native-bridge")
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["action_report"]["payload"]["window_input_attempts"], 0)
        self.assertEqual(data["action_report"]["payload"]["keyboard_input_attempts"], 0)
        self.assertEqual(data["action_report"]["payload"]["clipboard_write_attempts"], 0)
        self.assertEqual(
            data["action_report"]["payload"]["decision"],
            "agent_native_bridge_send_accepted",
        )
        self.assertEqual(
            [item[0] for item in _NativeBridgeHandler.requests],
            [
                "/v1/agent/capabilities",
                "/v1/agent/capabilities",
                "/v1/agent/chat",
            ],
        )


if __name__ == "__main__":
    unittest.main()
