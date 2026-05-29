import http.server
import json
import socketserver
import threading
import unittest

from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeDryRunAdapter,
    WeChatNativeBridgeSenderAdapter,
    build_wechat_native_bridge_request,
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
            if "readbackText" not in response:
                response["readbackText"] = (
                    f"File Transfer Assistant\n{payload.get('message', '')}"
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


class WeChatNativeBridgeTests(unittest.TestCase):
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
            "bridge": {"name": "OpenWukong WeChat Bridge"},
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "capabilities": ["wechat.conversation.send_message"],
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
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

    def test_dry_run_reads_only_capabilities_and_reports_ready(self):
        request = build_wechat_native_bridge_request(
            bridge_url=self.bridge_url,
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE: PASS",
            required_markers=("OPENWUKONG_WECHAT_NATIVE: PASS",),
        )

        report = WeChatNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data["validation_errors"])
        self.assertEqual(data["decision"], "wechat_native_bridge_dry_run_ready")
        self.assertEqual(data["safety_mode"], "dry_run")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["capability_probe_attempts"], 1)
        self.assertTrue(data["request"]["target"]["target_matched"])
        self.assertTrue(data["request"]["native_endpoint_ready"])
        self.assertEqual(len(_WeChatBridgeHandler.requests), 1)
        self.assertEqual(_WeChatBridgeHandler.requests[0][0], "/v1/wechat/capabilities")
        self.assertEqual(
            _WeChatBridgeHandler.requests[0][1]["payload"]["action"],
            "wechat.conversation.native_bridge_send_message",
        )

    def test_sender_uses_native_endpoint_and_verifies_readback_without_window_input(self):
        request = build_wechat_native_bridge_request(
            bridge_url=self.bridge_url,
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE_SEND: PASS",
            required_markers=("OPENWUKONG_WECHAT_NATIVE_SEND: PASS",),
            forbidden_markers=("OPENWUKONG_WECHAT_NATIVE_SEND: FAIL",),
        )

        report = WeChatNativeBridgeSenderAdapter(request_timeout=2.0).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data["decision"])
        self.assertEqual(data["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["missing_required_markers"], [])
        self.assertEqual(data["present_forbidden_markers"], [])
        paths = [item[0] for item in _WeChatBridgeHandler.requests]
        self.assertEqual(paths, ["/v1/wechat/capabilities", "/v1/wechat/send"])
        self.assertEqual(
            _WeChatBridgeHandler.requests[-1][1]["message"],
            "OPENWUKONG_WECHAT_NATIVE_SEND: PASS",
        )

    def test_sender_refuses_when_target_conversation_is_not_ready(self):
        _WeChatBridgeHandler.capabilities_payload["targets"] = [
            {"name": "Someone Else", "conversation_id": "other", "available": True}
        ]
        request = build_wechat_native_bridge_request(
            bridge_url=self.bridge_url,
            target_name="File Transfer Assistant",
            message="OPENWUKONG_WECHAT_NATIVE_SEND: PASS",
            required_markers=("OPENWUKONG_WECHAT_NATIVE_SEND: PASS",),
        )

        dry_run = WeChatNativeBridgeDryRunAdapter(request_timeout=2.0).prepare(request)
        send = WeChatNativeBridgeSenderAdapter(request_timeout=2.0).send(request)

        self.assertFalse(dry_run.ok)
        self.assertEqual(dry_run.decision, "wechat_native_bridge_target_not_ready")
        self.assertFalse(send.ok)
        self.assertEqual(send.decision, "wechat_native_bridge_request_not_ready")
        self.assertEqual(send.send_attempts, 0)
        self.assertNotIn("/v1/wechat/send", [item[0] for item in _WeChatBridgeHandler.requests])


if __name__ == "__main__":
    unittest.main()
