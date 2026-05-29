import http.server
import json
import socketserver
import threading
import unittest

from openwukong.control.agent_native_bridge import (
    AgentNativeBridgeDryRunAdapter,
    AgentNativeBridgeSenderAdapter,
    build_agent_native_bridge_request,
)


class _AgentBridgeHandler(http.server.BaseHTTPRequestHandler):
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
            if "readbackText" not in response:
                response["readbackText"] = (
                    f"{payload.get('agent_id', '')}\n"
                    f"{payload.get('project_name', '')}\n"
                    f"{payload.get('task_name', '')}\n"
                    f"{payload.get('message', '')}"
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


class AgentNativeBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _AgentBridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _AgentBridgeHandler.requests = []
        _AgentBridgeHandler.capabilities_payload = {
            "ok": True,
            "bridge": {"name": "OpenWukong Agent Native Bridge"},
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "pid": 32000,
                "hwnd": 2491830,
                "window_title": "Codex",
            },
            "requires_foreground": False,
            "window_input_required": False,
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": "codex", "available": True}],
            "projects": [{"name": "openwukong", "available": True}],
            "tasks": [{"name": "desktop-message", "available": True}],
        }
        _AgentBridgeHandler.send_payload = {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def test_dry_run_reads_only_capabilities_and_reports_ready(self):
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE: PASS",
            composed_message=(
                "Project: openwukong\nTask: desktop-message\n\n"
                "Message:\nOPENWUKONG_AGENT_NATIVE: PASS"
            ),
            required_markers=("OPENWUKONG_AGENT_NATIVE: PASS",),
        )

        report = AgentNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data["validation_errors"])
        self.assertEqual(data["decision"], "agent_native_bridge_dry_run_ready")
        self.assertEqual(data["safety_mode"], "dry_run")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["capability_probe_attempts"], 1)
        self.assertTrue(data["request"]["agent_ready"])
        self.assertTrue(data["request"]["surface_ready"])
        self.assertTrue(data["request"]["app_binding_ready"])
        self.assertTrue(data["request"]["project_ready"])
        self.assertTrue(data["request"]["task_ready"])
        self.assertEqual(len(_AgentBridgeHandler.requests), 1)
        self.assertEqual(_AgentBridgeHandler.requests[0][0], "/v1/agent/capabilities")
        self.assertEqual(
            _AgentBridgeHandler.requests[0][1]["payload"]["action"],
            "agent_app_conversation.native_bridge_send_message",
        )

    def test_sender_uses_native_endpoint_and_verifies_readback_without_window_input(self):
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE_SEND: PASS",
            composed_message=(
                "Project: openwukong\nTask: desktop-message\n\n"
                "Message:\nOPENWUKONG_AGENT_NATIVE_SEND: PASS"
            ),
            required_markers=("OPENWUKONG_AGENT_NATIVE_SEND: PASS",),
            forbidden_markers=("OPENWUKONG_AGENT_NATIVE_SEND: FAIL",),
        )

        report = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data["decision"])
        self.assertEqual(data["decision"], "agent_native_bridge_send_accepted")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["missing_required_markers"], [])
        self.assertEqual(data["present_forbidden_markers"], [])
        paths = [item[0] for item in _AgentBridgeHandler.requests]
        self.assertEqual(paths, ["/v1/agent/capabilities", "/v1/agent/chat"])
        self.assertEqual(
            _AgentBridgeHandler.requests[-1][1]["message"],
            "OPENWUKONG_AGENT_NATIVE_SEND: PASS",
        )

    def test_sender_refuses_when_bridge_serves_a_different_agent(self):
        _AgentBridgeHandler.capabilities_payload["agents"] = [
            {"agent_id": "claude", "available": True}
        ]
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE_SEND: PASS",
            composed_message="Project: openwukong\nTask: desktop-message",
            required_markers=("OPENWUKONG_AGENT_NATIVE_SEND: PASS",),
        )

        dry_run = AgentNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        send = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)

        self.assertFalse(dry_run.ok)
        self.assertEqual(dry_run.decision, "agent_native_bridge_agent_not_ready")
        self.assertFalse(send.ok)
        self.assertEqual(send.decision, "agent_native_bridge_request_not_ready")
        self.assertEqual(send.bridge_send_attempts, 0)
        self.assertNotIn("/v1/agent/chat", [item[0] for item in _AgentBridgeHandler.requests])

    def test_sender_refuses_cli_only_bridge_for_desktop_app_request(self):
        _AgentBridgeHandler.capabilities_payload["surface_kind"] = "cli"
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE_SEND: PASS",
            composed_message="Project: openwukong\nTask: desktop-message",
            required_markers=("OPENWUKONG_AGENT_NATIVE_SEND: PASS",),
        )

        dry_run = AgentNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        send = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)

        self.assertFalse(dry_run.ok)
        self.assertEqual(dry_run.decision, "agent_native_bridge_surface_not_ready")
        self.assertFalse(send.ok)
        self.assertEqual(send.decision, "agent_native_bridge_request_not_ready")
        self.assertEqual(send.bridge_send_attempts, 0)
        self.assertNotIn("/v1/agent/chat", [item[0] for item in _AgentBridgeHandler.requests])

    def test_sender_refuses_unbound_bridge_for_desktop_app_request(self):
        _AgentBridgeHandler.capabilities_payload.pop("app_binding", None)
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE_SEND: PASS",
            composed_message="Project: openwukong\nTask: desktop-message",
            required_markers=("OPENWUKONG_AGENT_NATIVE_SEND: PASS",),
        )

        dry_run = AgentNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        send = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)

        self.assertFalse(dry_run.ok)
        self.assertEqual(dry_run.decision, "agent_native_bridge_app_binding_not_ready")
        self.assertIn("app_binding_not_ready", dry_run.validation_errors)
        self.assertFalse(send.ok)
        self.assertEqual(send.decision, "agent_native_bridge_request_not_ready")
        self.assertEqual(send.bridge_send_attempts, 0)
        self.assertNotIn("/v1/agent/chat", [item[0] for item in _AgentBridgeHandler.requests])

    def test_sender_refuses_bridge_bound_to_wrong_desktop_process(self):
        _AgentBridgeHandler.capabilities_payload["app_binding"] = {
            "process_name": "Claude.exe",
            "pid": 32000,
            "hwnd": 2491830,
            "window_title": "Claude",
        }
        request = build_agent_native_bridge_request(
            bridge_url=self.bridge_url,
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="OPENWUKONG_AGENT_NATIVE_SEND: PASS",
            composed_message="Project: openwukong\nTask: desktop-message",
            required_markers=("OPENWUKONG_AGENT_NATIVE_SEND: PASS",),
        )

        dry_run = AgentNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        send = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)

        self.assertFalse(dry_run.ok)
        self.assertEqual(dry_run.decision, "agent_native_bridge_app_binding_not_ready")
        self.assertIn("app_binding_not_ready", dry_run.validation_errors)
        self.assertFalse(send.ok)
        self.assertEqual(send.decision, "agent_native_bridge_request_not_ready")
        self.assertEqual(send.bridge_send_attempts, 0)
        self.assertNotIn("/v1/agent/chat", [item[0] for item in _AgentBridgeHandler.requests])


if __name__ == "__main__":
    unittest.main()
