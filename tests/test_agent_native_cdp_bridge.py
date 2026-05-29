import json
import socketserver
import threading
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.browser import BrowserDevToolsTarget
from openwukong.control.agent_native_bridge import (
    AgentNativeBridgeSenderAdapter,
    build_agent_native_bridge_request,
)
from openwukong.control.agent_native_cdp_bridge import (
    AgentNativeCdpBridgeConfig,
    AgentNativeCdpBridgeService,
    make_agent_native_cdp_bridge_handler,
    write_agent_native_cdp_bridge_registry,
)


class AgentNativeCdpBridgeTests(unittest.TestCase):
    def test_capabilities_report_desktop_app_binding_without_control_attempts(self):
        devtools = _FakeDevToolsClient(
            targets=[
                _target(
                    title="Codex",
                    url="app://codex/index.html",
                )
            ]
        )
        service = AgentNativeCdpBridgeService(
            _config(),
            devtools_client=devtools,
        )

        data = service.capabilities()

        self.assertTrue(data["ok"])
        self.assertEqual(data["surface_kind"], "desktop_app")
        self.assertEqual(data["app_binding"]["process_name"], "Codex.exe")
        self.assertEqual(data["app_binding"]["pid"], 32000)
        self.assertEqual(data["app_binding"]["hwnd"], 2491830)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["agents"][0]["agent_id"], "codex")
        self.assertEqual(devtools.evaluate_calls, [])

    def test_send_uses_cdp_runtime_evaluate_without_window_input(self):
        devtools = _FakeDevToolsClient(
            value={
                "composerFound": True,
                "messageSet": True,
                "submitAttempted": True,
                "submitVerified": True,
                "readbackText": "OPENWUKONG_CDP_BRIDGE: PASS\nCodex accepted.",
            },
            targets=[_target()],
        )
        service = AgentNativeCdpBridgeService(
            _config(),
            devtools_client=devtools,
        )

        data = service.send(
            {
                "agent_id": "codex",
                "project_name": "openwukong",
                "task_name": "desktop-message",
                "message": "OPENWUKONG_CDP_BRIDGE: PASS",
                "composed_message": "Project: openwukong\nTask: desktop-message\n\nMessage:\nOPENWUKONG_CDP_BRIDGE: PASS",
            }
        )

        self.assertTrue(data["ok"], data)
        self.assertTrue(data["sent"])
        self.assertEqual(data["foreground_focus_stable"], True)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertIn("OPENWUKONG_CDP_BRIDGE: PASS", data["readbackText"])
        self.assertEqual(devtools.evaluate_calls[0][0], "http://127.0.0.1:9333")
        self.assertIn("OPENWUKONG_CDP_BRIDGE: PASS", devtools.evaluate_calls[0][2])

    def test_http_handler_satisfies_agent_native_bridge_sender_contract(self):
        devtools = _FakeDevToolsClient(
            value={
                "composerFound": True,
                "messageSet": True,
                "submitAttempted": True,
                "submitVerified": True,
                "readbackText": "OPENWUKONG_CDP_BRIDGE_HTTP: PASS\nCodex accepted.",
            },
            targets=[_target()],
        )
        service = AgentNativeCdpBridgeService(
            _config(),
            devtools_client=devtools,
        )
        handler = make_agent_native_cdp_bridge_handler(service)
        server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            bridge_url = f"http://127.0.0.1:{server.server_address[1]}"
            request = build_agent_native_bridge_request(
                bridge_url=bridge_url,
                agent="codex app",
                agent_id="codex",
                project_name="openwukong",
                task_name="desktop-message",
                message="OPENWUKONG_CDP_BRIDGE_HTTP: PASS",
                composed_message="Project: openwukong\nTask: desktop-message\n\nMessage:\nOPENWUKONG_CDP_BRIDGE_HTTP: PASS",
                expected_app_process_names=("Codex.exe",),
                expected_app_pids=(32000,),
                expected_app_hwnds=(2491830,),
                required_markers=("OPENWUKONG_CDP_BRIDGE_HTTP: PASS",),
            )

            report = AgentNativeBridgeSenderAdapter(request_timeout=2.0).send(request)
            data = report.to_dict()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(data["ok"], data["decision"])
        self.assertEqual(data["decision"], "agent_native_bridge_send_accepted")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(devtools.evaluate_calls[0][0], "http://127.0.0.1:9333")

    def test_write_registry_creates_local_agent_native_bridge_entry(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "native-bridges.json"

            write_agent_native_cdp_bridge_registry(
                registry_path,
                bridge_url="http://127.0.0.1:18888",
                config=_config(),
            )
            data = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], "openwukong-native-bridge-registry-v1")
        self.assertEqual(data["agent_native_bridges"][0]["url"], "http://127.0.0.1:18888")
        self.assertEqual(data["agent_native_bridges"][0]["agent_id"], "codex")
        self.assertEqual(data["agent_native_bridges"][0]["surface_kind"], "desktop_app")
        self.assertTrue(data["agent_native_bridges"][0]["enabled"])
        self.assertEqual(
            data["agent_native_bridges"][0]["app_binding"]["process_name"],
            "Codex.exe",
        )


class _FakeDevToolsClient:
    def __init__(self, value=None, targets=None):
        self.value = dict(value or {})
        self.targets = tuple(targets or ())
        self.list_calls = []
        self.evaluate_calls = []

    def list_targets(self, debugger_url):
        self.list_calls.append(debugger_url)
        return self.targets

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        return {"type": "object", "value": dict(self.value)}


def _config():
    return AgentNativeCdpBridgeConfig(
        agent="codex app",
        agent_id="codex",
        debugger_url="http://127.0.0.1:9333",
        process_name="Codex.exe",
        pid=32000,
        hwnd=2491830,
        window_title="Codex",
        projects=("openwukong",),
        tasks=("desktop-message",),
    )


def _target(title="Codex", url="app://codex/index.html"):
    return BrowserDevToolsTarget(
        target_id="page-1",
        type="page",
        title=title,
        url=url,
        web_socket_debugger_url="ws://127.0.0.1:9333/devtools/page/page-1",
    )


if __name__ == "__main__":
    unittest.main()
