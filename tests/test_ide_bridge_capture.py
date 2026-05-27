import contextlib
import http.server
import io
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.evaluation.ide_bridge_capture import (
    capture_ide_bridge_capabilities,
    main,
)


class _CapabilityBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))

        if self.path == "/v1/ide/capabilities":
            self._send_json(
                {
                    "ok": True,
                    "metadata": {
                        "ide_name": "Cursor",
                        "workspaceFolders": [
                            {
                                "name": "openwukong",
                                "fsPath": "E:\\ideaProjects\\agent\\openwukong",
                            }
                        ],
                    },
                    "commands": [
                        "workbench.action.files.save",
                        "cursor.chat.send",
                        "github.copilot.chat.open",
                    ],
                    "chat_adapters": [
                        {
                            "adapter_id": "cursor",
                            "label": "Cursor Chat",
                            "command_id": "cursor.chat.send",
                            "command_candidates": ["cursor.chat.send"],
                            "available": True,
                            "available_candidates": ["cursor.chat.send"],
                        },
                        {
                            "adapter_id": "copilot",
                            "label": "GitHub Copilot Chat",
                            "command_id": "github.copilot.chat.open",
                            "command_candidates": ["github.copilot.chat.open"],
                            "available": False,
                            "available_candidates": [],
                        },
                    ],
                }
            )
            return

        self._send_json(
            {
                "ok": False,
                "error": "unexpected_mutating_endpoint",
            },
            status=500,
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


class IDEBridgeCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _CapabilityBridgeHandler.requests = []
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _CapabilityBridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _CapabilityBridgeHandler.requests = []

    def test_capture_reads_only_capabilities_endpoint(self):
        report = capture_ide_bridge_capabilities(
            self.bridge_url,
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            request_timeout=2.0,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["mode"], "ide-bridge-capability-capture")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["request_path"], "/v1/ide/capabilities")
        self.assertEqual(data["metadata"]["ide_name"], "Cursor")
        self.assertEqual(data["adapter_mapping"]["cursor"]["commandId"], "cursor.chat.send")
        self.assertEqual(data["adapter_mapping"]["copilot"]["commandId"], "")
        self.assertEqual(_CapabilityBridgeHandler.requests[0][0], "/v1/ide/capabilities")
        self.assertEqual(len(_CapabilityBridgeHandler.requests), 1)
        self.assertEqual(
            _CapabilityBridgeHandler.requests[0][1]["target"]["workspace_path"],
            "E:\\ideaProjects\\agent\\openwukong",
        )

    def test_capture_preserves_unavailable_adapter_candidates_without_enabling_them(self):
        report = capture_ide_bridge_capabilities(self.bridge_url, request_timeout=2.0)
        mapping = report.to_dict()["adapter_mapping"]["copilot"]

        self.assertFalse(mapping["available"])
        self.assertEqual(mapping["commandId"], "")
        self.assertEqual(mapping["commandCandidates"], ["github.copilot.chat.open"])

    def test_cli_writes_capture_report_json(self):
        with tempfile.TemporaryDirectory() as td:
            output_path = Path(td) / "ide_bridge_capabilities.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    self.bridge_url,
                    "--output",
                    str(output_path),
                    "--json",
                ])

            printed = json.loads(stdout.getvalue())
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["mode"], "ide-bridge-capability-capture")
        self.assertEqual(saved["adapter_mapping"]["cursor"]["commandId"], "cursor.chat.send")
        self.assertEqual(saved["control_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
