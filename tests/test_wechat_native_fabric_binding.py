import http.server
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.control.session_ownership import SessionOwnershipIndex
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.wechat_native_fabric_binding import (
    ownership_index_from_wechat_native_bridge_registry,
    wechat_native_fabric_bindings_from_registry,
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


class WeChatNativeFabricBindingTests(unittest.TestCase):
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
            "background_screenshot_count": 2,
            "background_screenshot_success_count": 2,
            "process_name": "Weixin.exe",
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
                    "window_title": "File Transfer Assistant - WeChat",
                    "background_screenshot_focus_stable": True,
                    "background_screenshot_count": 2,
                    "background_screenshot_success_count": 2,
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

    def test_registry_binding_reads_capability_evidence_before_fabric_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "wechat-native-bridges.json"
            registry.write_text(
                json.dumps(
                    {
                        "wechat_native_bridges": [
                            {
                                "type": "wechat_native_bridge",
                                "bridge_url": self.bridge_url,
                                "enabled": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            bindings = wechat_native_fabric_bindings_from_registry(
                registry_paths=(registry,),
                target_name="File Transfer Assistant",
            )
            ownership_index = ownership_index_from_wechat_native_bridge_registry(
                registry_paths=(registry,),
                target_name="File Transfer Assistant",
            )

        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].target.wechat_native_bridge_url, self.bridge_url)
        self.assertEqual(bindings[0].target.window_title, "File Transfer Assistant - WeChat")
        self.assertEqual(bindings[0].target.background_screenshot_count, 2)
        self.assertEqual(bindings[0].target.background_screenshot_success_count, 2)
        self.assertTrue(bindings[0].target.background_screenshot_focus_stable)
        self.assertEqual(bindings[0].ownership.connector_id, "wechat-native-bridge")

        fabric = ControlFabric.with_default_connectors(
            ownership_index=ownership_index,
            require_owned_session_for_execution=True,
        )
        report = fabric.execute(
            bindings[0].target,
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_WECHAT_REGISTRY_FABRIC: PASS",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["selected_connector_id"], "wechat-native-bridge")
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["control_attempts"], 0)
        payload = data["action_report"]["payload"]
        self.assertEqual(payload["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(payload["window_input_attempts"], 0)
        self.assertEqual(payload["keyboard_input_attempts"], 0)
        self.assertEqual(payload["clipboard_write_attempts"], 0)
        self.assertEqual(
            [item[0] for item in _WeChatBridgeHandler.requests],
            [
                "/v1/wechat/capabilities",
                "/v1/wechat/capabilities",
                "/v1/wechat/capabilities",
                "/v1/wechat/send",
            ],
        )

    def test_read_only_capability_evidence_does_not_call_send_endpoint(self):
        _WeChatBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "clipboard_required": False,
            "send_action_ready": False,
            "background_screenshot_focus_stable": True,
            "background_screenshot_count": 1,
            "background_screenshot_success_count": 1,
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
                }
            ],
        }
        bindings = wechat_native_fabric_bindings_from_registry(
            (self.bridge_url,),
            target_name="File Transfer Assistant",
        )
        ownership_index = SessionOwnershipIndex(tuple(binding.ownership for binding in bindings))

        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].target.background_screenshot_success_count, 1)

        fabric = ControlFabric.with_default_connectors(
            ownership_index=ownership_index,
            require_owned_session_for_execution=True,
        )
        report = fabric.execute(
            bindings[0].target,
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_WECHAT_READ_ONLY_SHOULD_NOT_SEND",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "failed")
        self.assertEqual(data["selected_connector_id"], "wechat-native-bridge")
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["ownership"]["owned"])
        payload = data["action_report"]["payload"]
        self.assertEqual(payload["decision"], "wechat_native_bridge_request_not_ready")
        self.assertEqual(
            payload["dry_run_report"]["decision"],
            "wechat_native_bridge_send_action_not_ready",
        )
        self.assertEqual(payload["send_attempts"], 0)
        self.assertEqual(payload["native_call_attempts"], 0)
        self.assertEqual(payload["window_input_attempts"], 0)
        self.assertEqual(payload["keyboard_input_attempts"], 0)
        self.assertEqual(payload["clipboard_write_attempts"], 0)
        self.assertEqual(
            [item[0] for item in _WeChatBridgeHandler.requests],
            ["/v1/wechat/capabilities", "/v1/wechat/capabilities"],
        )

    def test_unavailable_capability_target_does_not_promote_screenshot_evidence(self):
        _WeChatBridgeHandler.capabilities_payload = {
            "ok": True,
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "clipboard_required": False,
            "send_action_ready": True,
            "background_screenshot_focus_stable": True,
            "background_screenshot_count": 2,
            "background_screenshot_success_count": 2,
            "targets": [
                {
                    "name": "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": False,
                    "availability_reason": "wechat_conversation_not_verified",
                }
            ],
        }

        bindings = wechat_native_fabric_bindings_from_registry(
            (self.bridge_url,),
            target_name="File Transfer Assistant",
        )

        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].target.background_screenshot_count, 0)
        self.assertEqual(bindings[0].target.background_screenshot_success_count, 0)
        fabric = ControlFabric.with_default_connectors()
        dispatch = fabric.dispatch(
            bindings[0].target,
            ControlIntent(
                action="send_message",
                text="OPENWUKONG_WECHAT_UNVERIFIED_TARGET_SHOULD_BLOCK",
                preferred_route_id="app-native-bridge-required",
                preferred_connector_id="wechat-native-bridge",
            ),
        ).to_dict()

        self.assertFalse(dispatch["connector_ready"])
        self.assertEqual(dispatch["decision"], "connector_required")
        self.assertEqual(_WeChatBridgeHandler.requests[0][0], "/v1/wechat/capabilities")


if __name__ == "__main__":
    unittest.main()
