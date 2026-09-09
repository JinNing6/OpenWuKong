import subprocess
import unittest
from unittest.mock import patch

from openwukong.evaluation.codex_app_server_probe import (
    CodexAppServerWsClient,
    launch_owned_codex_app_server_ws,
    probe_codex_app_server_ws,
)


class CodexAppServerWsProbeTests(unittest.TestCase):
    def test_read_only_probe_reports_ready_from_initialize_and_thread_list(self):
        client = _FakeCodexAppServerClient(
            initialize_response={
                "id": 1,
                "result": {
                    "codexHome": "C:/Users/Zhangjinqian/.codex",
                    "platformFamily": "windows",
                    "platformOs": "windows",
                    "userAgent": "Codex Desktop/0.136.0",
                },
            },
            thread_list_response={
                "id": 2,
                "result": {
                    "data": [{"id": "thread-1", "cwd": "E:/ideaProjects/agent/openwukong"}],
                    "nextCursor": None,
                },
            },
            notifications=[{"method": "remoteControl/status/changed"}],
        )

        report = probe_codex_app_server_ws(
            "ws://127.0.0.1:19731",
            request_timeout=0.25,
            client=client,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "codex_app_server_ws_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["request_attempts"], 2)
        self.assertEqual(data["observed_thread_count"], 1)
        self.assertEqual(data["selected_thread_id"], "thread-1")
        self.assertEqual(data["selected_thread_cwd"], "E:/ideaProjects/agent/openwukong")
        self.assertEqual(
            data["observed_threads"],
            [{"id": "thread-1", "cwd": "E:/ideaProjects/agent/openwukong", "preview": ""}],
        )
        self.assertEqual(data["codex_home"], "C:/Users/Zhangjinqian/.codex")
        self.assertEqual(client.calls[0][0], "ws://127.0.0.1:19731")

    def test_read_only_probe_reports_thread_list_not_ready(self):
        client = _FakeCodexAppServerClient(
            initialize_response={
                "id": 1,
                "result": {"codexHome": "C:/Users/Zhangjinqian/.codex"},
            },
            thread_list_response={"id": 2, "error": {"message": "not ready"}},
        )

        report = probe_codex_app_server_ws(
            "ws://127.0.0.1:19731",
            request_timeout=0.25,
            client=client,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "codex_app_server_thread_list_not_ready")
        self.assertEqual(data["window_input_attempts"], 0)

    def test_read_only_probe_rejects_missing_url(self):
        report = probe_codex_app_server_ws("", request_timeout=0.25)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "codex_app_server_ws_url_missing")
        self.assertEqual(data["error"], "codex_app_server_ws_url_missing")

    def test_client_starts_turn_and_collects_until_turn_completed(self):
        fake_ws = _FakeJsonRpcWebSocket(
            responses={
                1: {"id": 1, "result": {"codexHome": "C:/Users/me/.codex"}},
                2: {
                    "id": 2,
                    "result": {"status": "ready"},
                },
                3: {
                    "id": 3,
                    "result": {
                        "turn": {
                            "id": "turn-1",
                            "items": [],
                            "status": "inProgress",
                        }
                    },
                },
            },
            messages=[
                {
                    "method": "item/agentMessage/delta",
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "itemId": "agent-message-1",
                        "delta": "OPENWUKONG_ACCEPTANCE: PASS",
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turn": {
                            "id": "turn-1",
                            "items": [],
                            "status": "completed",
                        },
                    },
                },
            ],
        )

        with patch(
            "openwukong.evaluation.codex_app_server_probe._JsonRpcWebSocket",
            lambda ws_url, timeout: fake_ws,
        ):
            data = CodexAppServerWsClient(
                request_timeout=0.25
            ).initialize_start_turn_and_collect(
                "ws://127.0.0.1:19731",
                params={
                    "threadId": "thread-1",
                    "input": [{"type": "text", "text": "probe"}],
                },
                request_timeout=0.25,
            )

        self.assertEqual(data["request_attempts"], 3)
        self.assertEqual(data["turn_start_response"]["result"]["turn"]["id"], "turn-1")
        self.assertEqual(
            data["windows_sandbox_readiness_response"]["result"]["status"],
            "ready",
        )
        self.assertEqual(
            [payload["method"] for payload in fake_ws.sent],
            ["initialize", "windowsSandbox/readiness", "turn/start"],
        )
        self.assertEqual(data["notifications"], fake_ws.messages)

    def test_client_does_not_start_turn_when_windows_sandbox_not_ready(self):
        fake_ws = _FakeJsonRpcWebSocket(
            responses={
                1: {"id": 1, "result": {"codexHome": "C:/Users/me/.codex"}},
                2: {"id": 2, "result": {"status": "notConfigured"}},
            },
            messages=[
                {
                    "method": "item/agentMessage/delta",
                    "params": {"turnId": "turn-1", "delta": "late"},
                }
            ],
        )

        with patch(
            "openwukong.evaluation.codex_app_server_probe._JsonRpcWebSocket",
            lambda ws_url, timeout: fake_ws,
        ):
            data = CodexAppServerWsClient(
                request_timeout=0.25
            ).initialize_start_turn_and_collect(
                "ws://127.0.0.1:19731",
                params={
                    "threadId": "thread-1",
                    "input": [{"type": "text", "text": "probe"}],
                },
                request_timeout=0.25,
            )

        self.assertEqual(data["request_attempts"], 2)
        self.assertEqual(data["turn_start_response"], {})
        self.assertEqual(
            data["windows_sandbox_readiness_response"]["result"]["status"],
            "notConfigured",
        )
        self.assertEqual(
            [payload["method"] for payload in fake_ws.sent],
            ["initialize", "windowsSandbox/readiness"],
        )
        self.assertEqual(len(fake_ws._pending), 1)

    def test_client_stops_turn_collection_on_sandbox_error_notification(self):
        fake_ws = _FakeJsonRpcWebSocket(
            responses={
                1: {"id": 1, "result": {"codexHome": "C:/Users/me/.codex"}},
                2: {
                    "id": 2,
                    "result": {"status": "ready"},
                },
                3: {
                    "id": 3,
                    "result": {
                        "turn": {
                            "id": "turn-1",
                            "items": [],
                            "status": "inProgress",
                        }
                    },
                },
            },
            messages=[
                {
                    "method": "error",
                    "params": {
                        "code": "sandboxError",
                        "message": "windows sandbox: spawn setup refresh",
                    },
                },
                {
                    "method": "item/agentMessage/delta",
                    "params": {"turnId": "turn-1", "delta": "late"},
                },
            ],
        )

        with patch(
            "openwukong.evaluation.codex_app_server_probe._JsonRpcWebSocket",
            lambda ws_url, timeout: fake_ws,
        ):
            data = CodexAppServerWsClient(
                request_timeout=0.25
            ).initialize_start_turn_and_collect(
                "ws://127.0.0.1:19731",
                params={
                    "threadId": "thread-1",
                    "input": [{"type": "text", "text": "probe"}],
                },
                request_timeout=0.25,
            )

        self.assertEqual(data["request_attempts"], 3)
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["notifications"][0]["method"], "error")
        self.assertEqual(len(fake_ws._pending), 1)

    def test_owned_ephemeral_launcher_starts_loopback_app_server(self):
        created = []

        def fake_popen(command, **kwargs):
            process = _FakeProcess(pid=12345)
            created.append({"command": list(command), "kwargs": dict(kwargs), "process": process})
            return process

        with patch(
            "openwukong.evaluation.codex_app_server_probe._wait_for_tcp_socket",
            lambda host, port, **kwargs: host == "127.0.0.1" and port == 19731,
        ):
            endpoint = launch_owned_codex_app_server_ws(
                codex_path="C:/Users/me/AppData/Local/OpenAI/Codex/bin/codex.exe",
                workspace_path="E:/ideaProjects/agent/openwukong",
                output_dir="logs/runtime/test-owned-codex-app-server",
                port=19731,
                popen_factory=fake_popen,
            )

        data = endpoint.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "owned_codex_app_server_ws_ready")
        self.assertEqual(data["ws_url"], "ws://127.0.0.1:19731")
        self.assertEqual(
            created[0]["command"][0].replace("\\", "/"),
            "C:/Users/me/AppData/Local/OpenAI/Codex/bin/codex.exe",
        )
        self.assertEqual(
            created[0]["command"][1:],
            ["app-server", "--listen", "ws://127.0.0.1:19731"],
        )
        self.assertEqual(created[0]["kwargs"]["stdin"], subprocess.DEVNULL)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)

    def test_owned_ephemeral_launcher_terminates_when_socket_not_ready(self):
        process = _FakeProcess(pid=12345)

        def fake_popen(command, **kwargs):
            del command, kwargs
            return process

        with patch(
            "openwukong.evaluation.codex_app_server_probe._wait_for_tcp_socket",
            lambda host, port, **kwargs: False,
        ):
            endpoint = launch_owned_codex_app_server_ws(
                codex_path="C:/Users/me/AppData/Local/OpenAI/Codex/bin/codex.exe",
                workspace_path="E:/ideaProjects/agent/openwukong",
                output_dir="logs/runtime/test-owned-codex-app-server",
                port=19731,
                popen_factory=fake_popen,
            )

        self.assertFalse(endpoint.ok)
        self.assertTrue(process.terminated)
        self.assertEqual(process.poll(), 1)


class _FakeCodexAppServerClient:
    def __init__(self, *, initialize_response, thread_list_response, notifications=()):
        self.initialize_response = dict(initialize_response)
        self.thread_list_response = dict(thread_list_response)
        self.notifications = tuple(dict(item) for item in notifications)
        self.calls = []

    def initialize_and_list_threads(self, ws_url, *, request_timeout, thread_list_limit):
        self.calls.append((ws_url, request_timeout, thread_list_limit))
        return {
            "request_attempts": 2,
            "initialize_response": dict(self.initialize_response),
            "thread_list_response": dict(self.thread_list_response),
            "notifications": [dict(item) for item in self.notifications],
        }


class _FakeJsonRpcWebSocket:
    def __init__(self, *, responses, messages):
        self.responses = {int(key): dict(value) for key, value in responses.items()}
        self.messages = [dict(item) for item in messages]
        self._pending = [dict(item) for item in messages]
        self.notifications = []
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def send_json(self, payload):
        self.sent.append(dict(payload))

    def recv_response(self, request_id):
        return dict(self.responses[int(request_id)])

    def recv_message(self, timeout):
        del timeout
        if not self._pending:
            raise TimeoutError("done")
        message = self._pending.pop(0)
        self.notifications.append(dict(message))
        return message


class _FakeProcess:
    def __init__(self, *, pid):
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 1

    def kill(self):
        self.killed = True
        self.returncode = 1

    def wait(self, timeout=None):
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


if __name__ == "__main__":
    unittest.main()
