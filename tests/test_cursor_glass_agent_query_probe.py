import contextlib
import io
import json
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch

from openwukong.evaluation.cursor_glass_agent_query_probe import (
    main,
    probe_cursor_glass_agent_query,
)


class _GlassAgentQueryHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))
        if self.path != "/v1/ide/cursor/glass-agent-query":
            self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=404)
            return
        self._send_json(
            {
                "ok": True,
                "decision": "cursor_glass_agent_query_ready"
                if not payload.get("allow_write")
                else "cursor_glass_agent_query_dispatched",
                "dry_run": not payload.get("allow_write"),
                "command_id": "glass.newAgentWithQuery",
                "dispatch_status": "resolved" if payload.get("allow_write") else "",
            }
        )

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class CursorGlassAgentQueryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), _GlassAgentQueryHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        _GlassAgentQueryHandler.requests = []

    def test_dry_run_probe_discovers_endpoint_without_control_attempts(self):
        report = probe_cursor_glass_agent_query(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_DRY_RUN",
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "cursor-glass-agent-query-probe")
        self.assertEqual(data["safety_mode"], "dry_run_bridge_contract")
        self.assertTrue(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["bridge_probe_attempts"], 1)
        self.assertEqual(data["agent_request_attempts"], 0)
        self.assertEqual(data["decision"], "cursor_glass_agent_query_ready")
        self.assertEqual(_GlassAgentQueryHandler.requests[0][0], "/v1/ide/cursor/glass-agent-query")
        self.assertFalse(_GlassAgentQueryHandler.requests[0][1]["allow_write"])

    def test_write_probe_is_blocked_without_live_safety_profile(self):
        report = probe_cursor_glass_agent_query(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_WRITE",
            allow_write=True,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_glass_agent_query_requires_live_profile")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["bridge_probe_attempts"], 0)
        self.assertEqual(data["agent_request_attempts"], 0)
        self.assertEqual(_GlassAgentQueryHandler.requests, [])

    def test_live_write_profile_records_single_agent_request(self):
        report = probe_cursor_glass_agent_query(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_WRITE",
            allow_write=True,
            safety_profile="live_cursor_glass_agent_query_probe",
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["safety_mode"], "live_glass_agent_query_probe")
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["agent_request_attempts"], 1)
        self.assertEqual(data["decision"], "cursor_glass_agent_query_dispatched")
        self.assertTrue(_GlassAgentQueryHandler.requests[0][1]["allow_write"])
        self.assertEqual(
            _GlassAgentQueryHandler.requests[0][1]["safety_profile"],
            "live_cursor_glass_agent_query_probe",
        )

    def test_cli_discovers_dynamic_bridge_url_from_registry_when_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            registry = f"{td}/OpenWukong/ide-bridges"
            import os

            os.makedirs(registry, exist_ok=True)
            with open(f"{registry}/cursor.json", "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "schema_version": "openwukong-ide-bridge-registry-v1",
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Cursor",
                                "bridge_url": self.bridge_url,
                                "dynamic_port": True,
                            }
                        ],
                    },
                    handle,
                )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), patch.dict(
                "os.environ",
                {"LOCALAPPDATA": td, "PROGRAMDATA": ""},
                clear=True,
            ):
                exit_code = main(
                    [
                        "--message",
                        "OPENWUKONG_DYNAMIC_REGISTRY_GLASS",
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["bridge_url"], self.bridge_url)
        self.assertEqual(data["decision"], "cursor_glass_agent_query_ready")


if __name__ == "__main__":
    unittest.main()
