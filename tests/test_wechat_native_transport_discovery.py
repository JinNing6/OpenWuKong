import contextlib
import http.server
import io
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.evaluation.wechat_native_transport_discovery import (
    main,
    run_wechat_native_transport_discovery,
)


class _JsonHandler(http.server.BaseHTTPRequestHandler):
    requests = []
    payloads = {}

    def do_GET(self):
        self.__class__.requests.append(("GET", self.path))
        payload = self.__class__.payloads.get(self.path)
        if payload is None:
            self._send_json({"ok": False, "error": "not_found"}, status=404)
            return
        self._send_json(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        self.__class__.requests.append(("POST", self.path, body.decode("utf-8")))
        payload = self.__class__.payloads.get(self.path)
        if payload is None:
            self._send_json({"ok": False, "error": "not_found"}, status=404)
            return
        self._send_json(payload)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _CloseHandler(socketserver.BaseRequestHandler):
    def handle(self):
        return


class WeChatNativeTransportDiscoveryTests(unittest.TestCase):
    def test_unknown_tcp_loopback_port_does_not_become_ready(self):
        with socketserver.TCPServer(("127.0.0.1", 0), _CloseHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                report = run_wechat_native_transport_discovery(
                    explicit_ports=(server.server_address[1],),
                    include_named_pipes=False,
                    request_timeout=0.2,
                    process_snapshot=(),
                    connection_snapshot=(),
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "wechat_loopback_ports_unknown_protocol")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["ports"][0]["protocol_guess"], "tcp-unknown")

    def test_cdp_like_port_is_not_wechat_send_bridge(self):
        _JsonHandler.requests = []
        _JsonHandler.payloads = {
            "/json/version": {
                "Browser": "Chrome/129.0",
                "Protocol-Version": "1.3",
            }
        }
        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _JsonHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                report = run_wechat_native_transport_discovery(
                    explicit_ports=(server.server_address[1],),
                    include_named_pipes=False,
                    request_timeout=1.0,
                    process_snapshot=(),
                    connection_snapshot=(),
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "debug_transport_found_not_wechat_send_bridge")
        self.assertEqual(data["ports"][0]["protocol_guess"], "chrome-devtools-protocol")
        self.assertEqual(data["send_attempts"], 0)

    def test_bridge_contract_probe_finds_send_capable_endpoint_without_send_call(self):
        _JsonHandler.requests = []
        _JsonHandler.payloads = {
            "/v1/wechat/capabilities": {
                "ok": True,
                "background_safe": True,
                "requires_foreground": False,
                "window_input_required": False,
                "keyboard_input_required": False,
                "mouse_input_required": False,
                "clipboard_required": False,
                "send_action_ready": True,
                "targets": [{"name": "File Transfer Assistant", "available": True}],
            }
        }
        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _JsonHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                report = run_wechat_native_transport_discovery(
                    explicit_ports=(server.server_address[1],),
                    include_named_pipes=False,
                    probe_bridge_contract=True,
                    request_timeout=1.0,
                    process_snapshot=(),
                    connection_snapshot=(),
                )
            finally:
                server.shutdown()
                thread.join(timeout=2)
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "send_capable_wechat_native_bridge_found")
        self.assertEqual(
            data["ports"][0]["protocol_guess"],
            "wechat-native-bridge-send-ready",
        )
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertEqual(data["send_attempts"], 0)
        self.assertNotIn(
            ("POST", "/v1/wechat/send"),
            [(item[0], item[1]) for item in _JsonHandler.requests],
        )

    def test_cli_writes_report(self):
        _JsonHandler.requests = []
        _JsonHandler.payloads = {
            "/v1/wechat/capabilities": {
                "ok": True,
                "send_action_ready": False,
            }
        }
        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _JsonHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as td:
                    output = Path(td) / "transport-discovery.json"
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = main(
                            [
                                "--port",
                                str(server.server_address[1]),
                                "--probe-bridge-contract",
                                "--skip-named-pipes",
                                "--output",
                                str(output),
                                "--json",
                            ]
                        )
                    data = json.loads(output.read_text(encoding="utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=2)

        self.assertEqual(code, 0)
        self.assertEqual(data["decision"], "wechat_native_bridge_found_without_send_action")
        self.assertEqual(data["send_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
