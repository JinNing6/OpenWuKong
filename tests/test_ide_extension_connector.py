import json
import http.server
import socketserver
import threading
import unittest

from openwukong.connectors import (
    ConnectorManager,
    ConnectorTarget,
    CursorIDEConnector,
    IDEExtensionConnector,
    UIAIDEConnector,
)


class _BridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))

        if self.path == "/v1/ide/read":
            self._send_json(
                {
                    "ok": True,
                    "conversation": "Bridge conversation\nagent-ready",
                    "metadata": {
                        "ide_name": "Cursor",
                        "active_file": "src/main.py",
                    },
                }
            )
            return

        if self.path == "/v1/ide/send":
            self._send_json(
                {
                    "ok": True,
                    "action_key": "bridge-action-1",
                    "conversation": "Bridge conversation\nmessage-sent",
                    "metadata": {
                        "ide_name": "Cursor",
                        "command_id": "openwukong.sendMessage",
                    },
                }
            )
            return

        if self.path == "/v1/ide/state":
            self._send_json(
                {
                    "ok": True,
                    "metadata": {
                        "ide_name": "Cursor",
                        "activeTextEditor": {
                            "fsPath": "E:\\ideaProjects\\agent\\openwukong\\src\\main.py",
                            "languageId": "python",
                        },
                        "workspaceFolders": [
                            {
                                "name": "openwukong",
                                "fsPath": "E:\\ideaProjects\\agent\\openwukong",
                            }
                        ],
                    },
                    "diagnostics": [
                        {
                            "fsPath": "E:\\ideaProjects\\agent\\openwukong\\src\\main.py",
                            "severity": 1,
                            "message": "Example diagnostic",
                            "line": 10,
                            "character": 4,
                        }
                    ],
                }
            )
            return

        if self.path == "/v1/ide/command":
            self._send_json(
                {
                    "ok": True,
                    "action_key": "command-action-1",
                    "metadata": {
                        "ide_name": "Cursor",
                        "command_id": payload.get("command_id", ""),
                    },
                    "result": {
                        "accepted": True,
                    },
                }
            )
            return

        if self.path == "/v1/ide/capabilities":
            self._send_json(
                {
                    "ok": True,
                    "metadata": {
                        "ide_name": "Cursor",
                    },
                    "commands": [
                        "workbench.action.files.save",
                        "cursor.chat.send",
                    ],
                    "chat_adapters": [
                        {
                            "adapter_id": "cursor",
                            "label": "Cursor Chat",
                            "command_id": "cursor.chat.send",
                            "available": True,
                            "available_candidates": ["cursor.chat.send"],
                        },
                        {
                            "adapter_id": "copilot",
                            "label": "GitHub Copilot Chat",
                            "command_id": "",
                            "available": False,
                            "available_candidates": [],
                        },
                    ],
                }
            )
            return

        if self.path == "/v1/ide/chat":
            if payload.get("adapter_id") == "missing":
                self._send_json(
                    {
                        "ok": False,
                        "error": "chat_adapter_unavailable",
                        "metadata": {
                            "ide_name": "Cursor",
                            "adapter_id": "missing",
                        },
                    },
                    status=409,
                )
                return
            self._send_json(
                {
                    "ok": True,
                    "action_key": "chat-action-1",
                    "metadata": {
                        "ide_name": "Cursor",
                        "adapter_id": payload.get("adapter_id", ""),
                        "command_id": "cursor.chat.send",
                    },
                    "conversation": "chat-dispatched",
                }
            )
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class IDEExtensionConnectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _BridgeHandler.requests = []
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _BridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _BridgeHandler.requests = []

    def test_connector_requires_explicit_ide_bridge_url(self):
        connector = IDEExtensionConnector()

        self.assertFalse(connector.supports_target(ConnectorTarget(process_name="Cursor.exe")))
        self.assertTrue(
            connector.supports_target(
                ConnectorTarget(process_name="Cursor.exe", ide_bridge_url=self.bridge_url)
            )
        )

    def test_manager_prefers_extension_connector_when_bridge_url_is_present(self):
        manager = ConnectorManager(
            [UIAIDEConnector(), CursorIDEConnector(), IDEExtensionConnector()]
        )
        target = ConnectorTarget(
            pid=202,
            process_name="Cursor.exe",
            window_title="main.py - openwukong - Cursor",
            ide_bridge_url=self.bridge_url,
        )

        resolved = manager.resolve_session_connector(target)

        self.assertEqual(resolved.connector_id, "ide-extension")

    def test_manager_keeps_existing_cursor_route_without_bridge_url(self):
        manager = ConnectorManager(
            [IDEExtensionConnector(), UIAIDEConnector(), CursorIDEConnector()]
        )
        target = ConnectorTarget(
            pid=202,
            process_name="Cursor.exe",
            window_title="main.py - openwukong - Cursor",
        )

        resolved = manager.resolve_session_connector(target)

        self.assertEqual(resolved.connector_id, "cursor")

    def test_read_conversation_uses_extension_bridge(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        conversation = connector.read_conversation(target)

        self.assertIn("agent-ready", conversation)
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/read")
        self.assertEqual(payload["target"]["workspace_path"], "E:\\ideaProjects\\agent\\openwukong")

    def test_send_message_uses_extension_bridge_route_contract(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            window_title="main.py - openwukong - Cursor",
            project_name="openwukong",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "Continue the implementation")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action_key, "bridge-action-1")
        self.assertEqual(result.payload["route_id"], "ide-extension-connector")
        self.assertEqual(result.payload["transport"], "vscode-extension-bridge")
        self.assertEqual(result.payload["bridge_url"], self.bridge_url)
        self.assertEqual(result.payload["command_id"], "openwukong.sendMessage")
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/send")
        self.assertEqual(payload["message"], "Continue the implementation")
        self.assertEqual(payload["target"]["project_name"], "openwukong")

    def test_send_message_reports_missing_bridge_url_without_uia_fallback(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(process_name="Cursor.exe")

        result = connector.send_message(target, "hello")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "missing_ide_bridge_url")

    def test_ide_state_command_reads_semantic_state_and_diagnostics(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE STATE")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action, "read_state")
        self.assertEqual(result.payload["bridge_action"], "read_state")
        self.assertEqual(result.payload["metadata"]["ide_name"], "Cursor")
        self.assertEqual(result.payload["diagnostics"][0]["message"], "Example diagnostic")
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/state")
        self.assertEqual(payload["target"]["workspace_path"], "E:\\ideaProjects\\agent\\openwukong")

    def test_ide_command_executes_allowlisted_bridge_command(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(
            target,
            'IDE COMMAND workbench.action.files.save\n\n[{"uri":"file:///tmp/example.py"}]',
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action, "execute_command")
        self.assertEqual(result.action_key, "command-action-1")
        self.assertEqual(result.payload["bridge_action"], "execute_command")
        self.assertEqual(result.payload["command_id"], "workbench.action.files.save")
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/command")
        self.assertEqual(payload["command_id"], "workbench.action.files.save")
        self.assertEqual(payload["arguments"], [{"uri": "file:///tmp/example.py"}])

    def test_ide_command_rejects_invalid_json_arguments_before_bridge_call(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE COMMAND workbench.action.files.save\n\nnot-json")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "invalid_ide_command_arguments")
        self.assertEqual(_BridgeHandler.requests, [])

    def test_ide_capabilities_discovers_chat_adapters(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE CAPABILITIES")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action, "read_capabilities")
        self.assertEqual(result.payload["bridge_action"], "read_capabilities")
        self.assertEqual(result.payload["chat_adapters"][0]["adapter_id"], "cursor")
        self.assertTrue(result.payload["chat_adapters"][0]["available"])
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/capabilities")
        self.assertEqual(payload["target"]["workspace_path"], "E:\\ideaProjects\\agent\\openwukong")

    def test_ide_chat_sends_message_through_named_adapter(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            workspace_path="E:\\ideaProjects\\agent\\openwukong",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE CHAT cursor\n\nContinue the task")

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.action, "chat_send")
        self.assertEqual(result.action_key, "chat-action-1")
        self.assertEqual(result.payload["bridge_action"], "chat_send")
        self.assertEqual(result.payload["adapter_id"], "cursor")
        self.assertEqual(result.payload["command_id"], "cursor.chat.send")
        path, payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/chat")
        self.assertEqual(payload["adapter_id"], "cursor")
        self.assertEqual(payload["message"], "Continue the task")

    def test_ide_chat_requires_message_before_bridge_call(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE CHAT cursor")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "missing_ide_chat_message")
        self.assertEqual(_BridgeHandler.requests, [])

    def test_ide_chat_returns_bridge_contract_error_from_non_2xx_response(self):
        connector = IDEExtensionConnector()
        target = ConnectorTarget(
            process_name="Cursor.exe",
            ide_bridge_url=self.bridge_url,
        )

        result = connector.send_message(target, "IDE CHAT missing\n\nContinue the task")

        self.assertFalse(result.success)
        self.assertEqual(result.action, "chat_send")
        self.assertEqual(result.error, "chat_adapter_unavailable")
        self.assertEqual(result.payload["adapter_id"], "missing")
        path, _payload = _BridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/chat")


if __name__ == "__main__":
    unittest.main()
