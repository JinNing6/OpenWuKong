import contextlib
import http.server
import io
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.evaluation.computer_operation_readiness_matrix import (
    BACKGROUND_EXECUTE,
    BACKGROUND_EXECUTE_VERIFIED,
    ComputerOperationReadinessOptions,
    build_computer_operation_readiness_matrix,
)
from openwukong.evaluation.wechat_native_bridge_real_send_probe import (
    main,
    run_wechat_native_bridge_real_send_probe,
)


class _WeChatBridgeHandler(http.server.BaseHTTPRequestHandler):
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


class WeChatNativeBridgeRealSendProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _WeChatBridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _WeChatBridgeHandler.requests = []
        _WeChatBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "clipboard_required": False,
            "send_action_ready": True,
            "background_screenshot_focus_stable": True,
            "background_screenshot_count": 1,
            "background_screenshot_success_count": 1,
            "process_name": "Weixin.exe",
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
                    "window_title": "File Transfer Assistant - WeChat",
                    "background_screenshot_focus_stable": True,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                }
            ],
        }
        _WeChatBridgeHandler.send_payload = {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def test_without_allow_send_dry_runs_only(self):
        report = run_wechat_native_bridge_real_send_probe(
            bridge_urls=(self.bridge_url,),
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE_REAL: PASS",
            allow_send=False,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "blocked_requires_explicit_opt_in")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertEqual(
            [item[0] for item in _WeChatBridgeHandler.requests],
            ["/v1/wechat/capabilities", "/v1/wechat/capabilities"],
        )

    def test_allow_send_uses_native_bridge_and_outputs_matrix_ready_send_report(self):
        report = run_wechat_native_bridge_real_send_probe(
            bridge_urls=(self.bridge_url,),
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE_REAL: PASS",
            allow_send=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "wechat_native_bridge_real_send_verified")
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["send_report"]["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(data["send_report"]["missing_required_markers"], [])
        self.assertEqual(data["send_report"]["present_forbidden_markers"], [])
        self.assertEqual(
            [item[0] for item in _WeChatBridgeHandler.requests],
            [
                "/v1/wechat/capabilities",
                "/v1/wechat/capabilities",
                "/v1/wechat/capabilities",
                "/v1/wechat/send",
            ],
        )

        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    wechat_native_bridge_url=self.bridge_url,
                    wechat_native_bridge_send_report=data,
                )
            ).to_dict()
        wechat = next(
            item for item in matrix["surfaces"] if item["surface_id"] == "wechat"
        )

        self.assertEqual(wechat["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(wechat["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertTrue(wechat["verified"])
        self.assertTrue(wechat["can_execute_without_focus"])
        self.assertEqual(wechat["evidence"]["wechat_native_window_input_attempts"], 0)

    def test_bridge_not_ready_does_not_call_send_endpoint(self):
        _WeChatBridgeHandler.capabilities_payload["send_action_ready"] = False

        report = run_wechat_native_bridge_real_send_probe(
            bridge_urls=(self.bridge_url,),
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE_REAL: PASS",
            allow_send=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "wechat_native_bridge_send_action_not_ready")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertNotIn("/v1/wechat/send", [item[0] for item in _WeChatBridgeHandler.requests])

    def test_cli_writes_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "wechat-native-real-send.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--bridge-url",
                        self.bridge_url,
                        "--target-name",
                        "File Transfer Assistant",
                        "--message",
                        "OPENWUKONG_WECHAT_NATIVE_REAL: PASS",
                        "--allow-send",
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["send_report"]["decision"], "wechat_native_bridge_send_accepted")


if __name__ == "__main__":
    unittest.main()
