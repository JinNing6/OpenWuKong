import json
import http.server
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.supervisor.agent_supervisor import AgentSupervisor, TaskGoal, load_goals


class _SupervisorChatBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))

        if self.path == "/v1/ide/chat":
            self._send_json(
                {
                    "ok": True,
                    "action_key": "supervisor-chat-action",
                    "metadata": {
                        "ide_name": "Cursor",
                        "adapter_id": payload.get("adapter_id", ""),
                        "command_id": "composer.startComposerPrompt",
                    },
                    "conversation": "chat-dispatched",
                }
            )
            return

        self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class SupervisorIDEExtensionConfigTests(unittest.TestCase):
    def test_load_goals_preserves_ide_extension_bridge_url(self):
        config = {
            "goals": [
                {
                    "window_match": "openwukong",
                    "task_name": "IDE bridge route",
                    "goal": "Route through IDE extension bridge",
                    "retry_command": "Continue implementation",
                    "connector_hint": "ide-extension",
                    "workspace_path": "E:\\ideaProjects\\agent\\openwukong",
                    "ide_bridge_url": "http://127.0.0.1:8787",
                    "ide_chat_adapter": "cursor",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goals.json"
            path.write_text(json.dumps(config), encoding="utf-8")

            goals = load_goals(str(path))

        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].connector_hint, "ide-extension")
        self.assertEqual(goals[0].ide_bridge_url, "http://127.0.0.1:8787")
        self.assertEqual(goals[0].ide_chat_adapter, "cursor")

    def test_supervisor_wraps_ide_extension_retry_command_with_chat_adapter(self):
        _SupervisorChatBridgeHandler.requests = []
        server = socketserver.TCPServer(("127.0.0.1", 0), _SupervisorChatBridgeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        bridge_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            goal = TaskGoal(
                window_match="workspace",
                task_name="Cursor chat dispatch",
                goal="Dispatch message through Cursor chat adapter",
                success_keywords=[],
                failure_keywords=[],
                retry_command="Continue from supervisor",
                connector_hint="ide-extension",
                workspace_path="E:\\ideaProjects\\agent\\openwukong",
                ide_bridge_url=bridge_url,
                ide_chat_adapter="cursor",
            )
            supervisor = AgentSupervisor([goal])
            target = ConnectorTarget(
                process_name="Cursor.exe",
                project_name="workspace",
                workspace_path=goal.workspace_path,
                ide_bridge_url=bridge_url,
            )

            supervisor._steer(goal, target, dry_run=False, steer_content=goal.retry_command)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(goal.retry_count, 1)
        self.assertEqual(supervisor._total_steers, 1)
        self.assertEqual(len(_SupervisorChatBridgeHandler.requests), 1)
        path, payload = _SupervisorChatBridgeHandler.requests[0]
        self.assertEqual(path, "/v1/ide/chat")
        self.assertEqual(payload["adapter_id"], "cursor")
        self.assertEqual(payload["message"], "Continue from supervisor")


if __name__ == "__main__":
    unittest.main()
