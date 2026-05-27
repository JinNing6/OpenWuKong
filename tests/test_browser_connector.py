import http.server
import base64
import hashlib
import json
import socketserver
import struct
import threading
import unittest

from openwukong.connectors import BrowserDevToolsClient, BrowserSessionConnector, ConnectorTarget
from openwukong.connectors.browser import BrowserDevToolsTarget


class _TestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            "<html><head><title>Browser Connector Test</title></head>"
            "<body><h1>Hello Browser</h1><p>connector-ok</p></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _DevToolsListHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/json/list":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(
            [
                {
                    "id": "page-1",
                    "type": "page",
                    "title": "DevTools Page",
                    "url": "https://example.test/devtools",
                    "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/page-1",
                }
            ]
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class _FakeCdpWebSocketHandler(socketserver.StreamRequestHandler):
    def handle(self):
        key = ""
        while True:
            line = self.rfile.readline().decode("ascii").strip()
            if not line:
                break
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()

        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.wfile.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        message = self._read_client_json()
        self.server.last_request = message
        params = message.get("params", {})
        result_value = params.get("expression") or message["method"]
        response = {
            "id": message["id"],
            "result": {
                "result": {
                    "type": "string",
                    "value": f"ok:{result_value}",
                }
            },
        }
        self._send_server_json(response)

    def _read_client_json(self):
        first, second = self.rfile.read(2)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.rfile.read(8))[0]
        mask = self.rfile.read(4)
        payload = self.rfile.read(length)
        unmasked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return json.loads(unmasked.decode("utf-8"))

    def _send_server_json(self, message):
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        if len(payload) <= 125:
            header.append(len(payload))
        elif len(payload) <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", len(payload)))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", len(payload)))
        self.wfile.write(bytes(header) + payload)


class _FakeDevToolsClient:
    def __init__(self, targets):
        self.targets = tuple(targets)
        self.list_calls = []
        self.evaluate_calls = []

    def list_targets(self, debugger_url):
        self.list_calls.append(debugger_url)
        return self.targets

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        return {
            "type": "string",
            "value": f"{target.title}:{expression}",
        }


class BrowserConnectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _TestHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.base_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def test_devtools_client_lists_targets_from_debugger_endpoint(self):
        server = socketserver.TCPServer(("127.0.0.1", 0), _DevToolsListHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            debugger_url = f"http://127.0.0.1:{server.server_address[1]}"
            targets = BrowserDevToolsClient().list_targets(debugger_url)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_id, "page-1")
        self.assertEqual(targets[0].title, "DevTools Page")
        self.assertEqual(targets[0].web_socket_debugger_url, "ws://127.0.0.1/devtools/page/page-1")

    def test_devtools_client_evaluates_runtime_expression_over_websocket(self):
        server = socketserver.TCPServer(("127.0.0.1", 0), _FakeCdpWebSocketHandler)
        server.last_request = {}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = BrowserDevToolsTarget(
                target_id="page-1",
                type="page",
                title="DevTools Page",
                url="https://example.test/devtools",
                web_socket_debugger_url=f"ws://127.0.0.1:{server.server_address[1]}/devtools/page/page-1",
            )
            result = BrowserDevToolsClient().evaluate(
                "http://127.0.0.1:9222",
                target,
                "document.title",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result["value"], "ok:document.title")
        self.assertEqual(server.last_request["method"], "Runtime.evaluate")
        self.assertEqual(server.last_request["params"]["expression"], "document.title")
        self.assertTrue(server.last_request["params"]["returnByValue"])

    def test_devtools_client_calls_generic_cdp_method_over_websocket(self):
        server = socketserver.TCPServer(("127.0.0.1", 0), _FakeCdpWebSocketHandler)
        server.last_request = {}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = BrowserDevToolsTarget(
                target_id="page-1",
                type="page",
                title="DevTools Page",
                url="https://example.test/devtools",
                web_socket_debugger_url=f"ws://127.0.0.1:{server.server_address[1]}/devtools/page/page-1",
            )
            result = BrowserDevToolsClient().call_method(
                "http://127.0.0.1:9222",
                target,
                "Page.navigate",
                {"url": "https://example.test/search?q=openwukong"},
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result["result"]["value"], "ok:Page.navigate")
        self.assertEqual(server.last_request["method"], "Page.navigate")
        self.assertEqual(
            server.last_request["params"]["url"],
            "https://example.test/search?q=openwukong",
        )

    def test_browser_connector_supports_browser_process(self):
        connector = BrowserSessionConnector()
        target = ConnectorTarget(process_name="msedge.exe")
        self.assertTrue(connector.supports_target(target))

    def test_browser_connector_gets_page_and_extracts_title(self):
        connector = BrowserSessionConnector()
        target = ConnectorTarget(resource_url=self.base_url, workspace_hint="browser")
        result = connector.send_message(target, self.base_url)
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["title"], "Browser Connector Test")
        self.assertIn("connector-ok", result.payload["text_excerpt"])

    def test_browser_connector_transcript_contains_navigation(self):
        connector = BrowserSessionConnector()
        target = ConnectorTarget(resource_url=self.base_url, workspace_hint="browser")
        result = connector.send_message(target, f"GET {self.base_url}")
        self.assertTrue(result.success, result.error)
        transcript = connector.read_conversation(target)
        self.assertIn("Browser Connector Test", transcript)
        self.assertIn("$ GET", transcript)

    def test_browser_connector_http_fallback_payload_exposes_route_contract(self):
        connector = BrowserSessionConnector()
        target = ConnectorTarget(resource_url=self.base_url, workspace_hint="browser")
        result = connector.send_message(target, f"GET {self.base_url}")
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["route_id"], "browser-http-session")
        self.assertEqual(result.payload["transport"], "requests-session")

    def test_browser_connector_uses_devtools_eval_when_debugger_url_present(self):
        devtools_target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([devtools_target])
        connector = BrowserSessionConnector(devtools_client=fake)
        target = ConnectorTarget(
            process_name="msedge.exe",
            resource_url="https://example.test/app",
            debugger_url="http://127.0.0.1:9222",
        )

        result = connector.send_message(target, "EVAL document.title")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action, "devtools_evaluate")
        self.assertEqual(result.payload["route_id"], "browser-devtools-or-extension")
        self.assertEqual(result.payload["transport"], "chrome-devtools-protocol")
        self.assertEqual(result.payload["target_id"], "page-1")
        self.assertEqual(result.payload["expression"], "document.title")
        self.assertEqual(result.payload["result"]["value"], "Example App:document.title")
        self.assertEqual(fake.list_calls, ["http://127.0.0.1:9222"])
        self.assertEqual(fake.evaluate_calls[0][1], devtools_target)
        transcript = connector.read_conversation(target)
        self.assertIn("$ CDP Runtime.evaluate document.title", transcript)

    def test_browser_connector_selects_devtools_target_by_resource_url_before_title(self):
        title_match = BrowserDevToolsTarget(
            target_id="title-match",
            type="page",
            title="Example App",
            url="https://wrong.example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/title-match",
        )
        url_match = BrowserDevToolsTarget(
            target_id="url-match",
            type="page",
            title="Different Title",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/url-match",
        )
        fake = _FakeDevToolsClient([title_match, url_match])
        connector = BrowserSessionConnector(devtools_client=fake)
        target = ConnectorTarget(
            window_title="Example App - Microsoft Edge",
            resource_url="https://example.test/app",
            debugger_url="http://127.0.0.1:9222",
        )

        result = connector.send_message(target, "EVAL location.href")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["target_id"], "url-match")
        self.assertEqual(fake.evaluate_calls[0][1], url_match)

    def test_browser_connector_reports_missing_devtools_target(self):
        fake = _FakeDevToolsClient([])
        connector = BrowserSessionConnector(devtools_client=fake)
        target = ConnectorTarget(
            process_name="chrome.exe",
            resource_url="https://example.test/app",
            debugger_url="http://127.0.0.1:9222",
        )

        result = connector.send_message(target, "EVAL document.title")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "devtools_target_not_found")
        self.assertEqual(fake.evaluate_calls, [])


if __name__ == "__main__":
    unittest.main()
