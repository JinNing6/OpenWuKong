import contextlib
import io
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeSenderAdapter,
    build_wechat_native_bridge_request,
)
from openwukong.control.wechat_native_bridge_registry import (
    discover_wechat_native_bridge_urls,
)
from openwukong.control.wechat_native_endpoint_publisher import (
    ExternalCommandWeChatNativeBackend,
    LiveWeChatEvidenceBackend,
    WeChatNativeEndpointConfig,
    WeChatNativeEndpointPublisher,
    build_wechat_native_backend,
    main,
    write_wechat_native_bridge_registry,
)
from openwukong.evaluation.accessibility_probe import (
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.wechat_locator import (
    StaticMsaaObserver,
    StaticWin32WindowObserver,
    Win32ChildWindowSnapshot,
)
from openwukong.evaluation.window_capture import BackgroundWindowCaptureReport


class WeChatNativeEndpointPublisherTests(unittest.TestCase):
    def test_write_registry_creates_local_wechat_native_bridge_entry(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "wechat-native-bridges.json"

            write_wechat_native_bridge_registry(
                registry_path,
                bridge_url="http://127.0.0.1:18888",
                config=WeChatNativeEndpointConfig(
                    process_name="Weixin.exe",
                    pid=1234,
                    hwnd=5678,
                    window_title="微信",
                    conversation_name="File Transfer Assistant",
                    conversation_id="filehelper",
                ),
            )
            data = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertEqual(
            data["schema_version"],
            "openwukong-wechat-native-bridge-registry-v1",
        )
        entry = data["wechat_native_bridges"][0]
        self.assertEqual(entry["url"], "http://127.0.0.1:18888")
        self.assertEqual(entry["type"], "wechat_native_bridge")
        self.assertEqual(entry["surface_kind"], "desktop_app")
        self.assertTrue(entry["enabled"])
        self.assertEqual(entry["app_binding"]["process_name"], "Weixin.exe")
        self.assertEqual(entry["target"]["conversation_name"], "File Transfer Assistant")

    def test_write_registry_preserves_other_entries_and_updates_same_conversation(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "wechat-native-bridges.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "openwukong-wechat-native-bridge-registry-v1",
                        "wechat_native_bridges": [
                            {
                                "url": "http://127.0.0.1:18881",
                                "type": "wechat_native_bridge",
                                "enabled": True,
                                "app_binding": {"process_name": "Weixin.exe"},
                                "target": {"conversation_name": "Other"},
                            },
                            {
                                "url": "http://127.0.0.1:18882",
                                "type": "wechat_native_bridge",
                                "enabled": True,
                                "app_binding": {"process_name": "Weixin.exe"},
                                "target": {"conversation_name": "File Transfer Assistant"},
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            write_wechat_native_bridge_registry(
                registry_path,
                bridge_url="http://127.0.0.1:18888",
                config=WeChatNativeEndpointConfig(
                    process_name="Weixin.exe",
                    conversation_name="File Transfer Assistant",
                ),
            )
            data = json.loads(registry_path.read_text(encoding="utf-8"))

        entries = data["wechat_native_bridges"]
        self.assertEqual([entry["target"]["conversation_name"] for entry in entries], ["Other", "File Transfer Assistant"])
        self.assertEqual(entries[1]["url"], "http://127.0.0.1:18888")

    def test_publisher_uses_dynamic_port_writes_registry_and_serves_send_contract(self):
        backend = _OwnedBackend()
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "wechat-native-bridges.json"
            publisher = WeChatNativeEndpointPublisher(
                WeChatNativeEndpointConfig(
                    port=0,
                    registry_path=str(registry_path),
                    conversation_name="File Transfer Assistant",
                ),
                backend=backend,
            )
            with publisher:
                self.assertTrue(publisher.bridge_url.startswith("http://127.0.0.1:"))
                self.assertNotEqual(publisher.bridge_url, "http://127.0.0.1:0")
                discovered = discover_wechat_native_bridge_urls(
                    registry_paths=(registry_path,),
                    environment={},
                )
                request = build_wechat_native_bridge_request(
                    bridge_url=discovered[0],
                    target_name="File Transfer Assistant",
                    message="OPENWUKONG_WECHAT_ENDPOINT: PASS",
                    background_screenshot_count=1,
                    background_screenshot_success_count=1,
                )
                report = WeChatNativeBridgeSenderAdapter(request_timeout=2.0).send(
                    request
                ).to_dict()

        self.assertEqual(discovered, (publisher.bridge_url,))
        self.assertEqual(backend.paths, ["/v1/wechat/capabilities", "/v1/wechat/send"])
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["keyboard_input_attempts"], 0)
        self.assertEqual(report["clipboard_write_attempts"], 0)

    def test_default_publisher_endpoint_is_not_send_ready_without_real_backend(self):
        with WeChatNativeEndpointPublisher(WeChatNativeEndpointConfig(port=0)) as publisher:
            request = urllib.request.Request(
                f"{publisher.bridge_url}/v1/wechat/capabilities",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=2.0) as response:
                data = json.loads(response.read().decode("utf-8"))

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "wechat_native_backend_not_configured")
        self.assertEqual(data["window_input_attempts"], 0)

    def test_live_evidence_backend_publishes_locator_and_background_screenshot(self):
        backend = LiveWeChatEvidenceBackend(
            WeChatNativeEndpointConfig(
                conversation_name="File Transfer Assistant",
            ),
            accessibility_observer=StaticAccessibilityObserver(
                (
                    AccessibilityWindowSnapshot(
                        pid=4628,
                        process_name="Weixin.exe",
                        window_title="File Transfer Assistant - WeChat",
                        class_name="Qt51514QWindowIcon",
                        hwnd=7001,
                    ),
                )
            ),
            win32_observer=StaticWin32WindowObserver(
                {
                    7001: (
                        Win32ChildWindowSnapshot(
                            hwnd=7101,
                            parent_hwnd=7001,
                            class_name="Edit",
                            rect=(10, 500, 780, 560),
                            is_visible=True,
                            is_enabled=True,
                        ),
                    )
                }
            ),
            msaa_observer=StaticMsaaObserver({}),
            capture_provider=_FakeCaptureProvider(ok=True),
            capture_dir="E:/tmp/openwukong-test-captures",
        )

        data = backend.capabilities("File Transfer Assistant")

        self.assertTrue(data["ok"], data)
        self.assertTrue(data["background_safe"])
        self.assertFalse(data["send_action_ready"])
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)
        self.assertEqual(data["background_screenshot_count"], 1)
        self.assertEqual(data["background_screenshot_success_count"], 1)
        self.assertTrue(data["background_screenshot_focus_stable"])
        self.assertEqual(data["targets"][0]["name"], "File Transfer Assistant")
        self.assertEqual(data["targets"][0]["process_name"], "Weixin.exe")
        self.assertEqual(data["locator_report"]["window_count"], 1)

    def test_live_evidence_backend_does_not_claim_unverified_conversation_available(self):
        backend = LiveWeChatEvidenceBackend(
            WeChatNativeEndpointConfig(
                conversation_name="File Transfer Assistant",
            ),
            accessibility_observer=StaticAccessibilityObserver(
                (
                    AccessibilityWindowSnapshot(
                        pid=4628,
                        process_name="Weixin.exe",
                        window_title="Other Chat - WeChat",
                        class_name="Qt51514QWindowIcon",
                        hwnd=7001,
                    ),
                )
            ),
            win32_observer=StaticWin32WindowObserver({}),
            msaa_observer=StaticMsaaObserver({}),
            capture_provider=_FakeCaptureProvider(ok=True),
            capture_dir="E:/tmp/openwukong-test-captures",
        )

        data = backend.capabilities("File Transfer Assistant")

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["background_screenshot_success_count"], 1)
        self.assertEqual(data["targets"][0]["name"], "File Transfer Assistant")
        self.assertFalse(data["targets"][0]["available"])
        self.assertEqual(
            data["targets"][0]["availability_reason"],
            "wechat_conversation_not_verified",
        )

    def test_live_evidence_backend_refuses_send_without_window_input(self):
        backend = LiveWeChatEvidenceBackend(
            WeChatNativeEndpointConfig(),
            accessibility_observer=StaticAccessibilityObserver(()),
            capture_provider=_FakeCaptureProvider(ok=False),
        )

        data = backend.send_message({"message": "should not send"})

        self.assertFalse(data["ok"])
        self.assertFalse(data["sent"])
        self.assertEqual(data["error"], "wechat_native_send_backend_not_configured")
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)

    def test_live_evidence_backend_does_not_promote_process_only_wechat(self):
        backend = LiveWeChatEvidenceBackend(
            WeChatNativeEndpointConfig(),
            accessibility_observer=StaticAccessibilityObserver(
                (
                    AccessibilityWindowSnapshot(
                        pid=4628,
                        process_name="Weixin.exe",
                        window_title="Weixin.exe",
                        hwnd=0,
                        scan_error="process_only_no_top_level_window",
                    ),
                )
            ),
            capture_provider=_FakeCaptureProvider(ok=False),
        )

        data = backend.capabilities("File Transfer Assistant")

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "wechat_top_level_hwnd_missing")
        self.assertEqual(data["targets"], [])
        self.assertEqual(data["background_screenshot_count"], 0)

    def test_live_evidence_backend_times_out_without_input_attempts(self):
        backend = LiveWeChatEvidenceBackend(
            WeChatNativeEndpointConfig(capability_timeout_sec=0.01),
            accessibility_observer=_SlowAccessibilityObserver(),
        )

        data = backend.capabilities("File Transfer Assistant")

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "wechat_live_evidence_timeout")
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["keyboard_input_attempts"], 0)
        self.assertEqual(data["clipboard_write_attempts"], 0)

    def test_external_command_backend_without_command_is_not_send_ready(self):
        backend = build_wechat_native_backend(
            "external-command",
            WeChatNativeEndpointConfig(),
        )

        capabilities = backend.capabilities("File Transfer Assistant")
        send_result = backend.send_message(
            {"target_name": "File Transfer Assistant", "message": "should not send"}
        )

        self.assertIsInstance(backend, ExternalCommandWeChatNativeBackend)
        self.assertFalse(capabilities["ok"])
        self.assertEqual(
            capabilities["error"],
            "wechat_native_external_command_not_configured",
        )
        self.assertFalse(capabilities["send_action_ready"])
        self.assertFalse(send_result["ok"])
        self.assertFalse(send_result["sent"])
        self.assertEqual(send_result["window_input_attempts"], 0)
        self.assertEqual(send_result["keyboard_input_attempts"], 0)
        self.assertEqual(send_result["clipboard_write_attempts"], 0)

    def test_external_command_backend_completes_native_send_contract(self):
        with tempfile.TemporaryDirectory() as td:
            script = _write_external_wechat_command(Path(td) / "wechat_bridge.py")
            backend = build_wechat_native_backend(
                "external-command",
                WeChatNativeEndpointConfig(
                    external_command=(sys.executable, str(script)),
                    external_command_timeout_sec=3.0,
                ),
            )
            with WeChatNativeEndpointPublisher(
                WeChatNativeEndpointConfig(port=0),
                backend=backend,
            ) as publisher:
                request = build_wechat_native_bridge_request(
                    bridge_url=publisher.bridge_url,
                    target_name="File Transfer Assistant",
                    message="OPENWUKONG_WECHAT_EXTERNAL_COMMAND: PASS",
                    background_screenshot_focus_stable=True,
                    background_screenshot_count=1,
                    background_screenshot_success_count=1,
                    required_markers=("OPENWUKONG_WECHAT_EXTERNAL_COMMAND: PASS",),
                )
                report = WeChatNativeBridgeSenderAdapter(request_timeout=3.0).send(
                    request
                ).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "wechat_native_bridge_send_accepted")
        self.assertEqual(report["send_attempts"], 1)
        self.assertEqual(report["native_call_attempts"], 1)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["keyboard_input_attempts"], 0)
        self.assertEqual(report["clipboard_write_attempts"], 0)
        self.assertEqual(report["action_result"]["backend"], "external-command")
        self.assertIn(
            "OPENWUKONG_WECHAT_EXTERNAL_COMMAND: PASS",
            report["action_result"]["readbackText"],
        )

    def test_external_command_backend_failure_keeps_input_attempts_zero(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "failing_bridge.py"
            script.write_text(
                "import sys\nsys.stderr.write('native failure')\nsys.exit(7)\n",
                encoding="utf-8",
            )
            backend = build_wechat_native_backend(
                "external-command",
                WeChatNativeEndpointConfig(
                    external_command=(sys.executable, str(script)),
                    external_command_timeout_sec=3.0,
                ),
            )

            capabilities = backend.capabilities("File Transfer Assistant")
            send_result = backend.send_message(
                {
                    "target_name": "File Transfer Assistant",
                    "message": "OPENWUKONG_WECHAT_EXTERNAL_COMMAND_FAIL",
                }
            )

        self.assertFalse(capabilities["ok"])
        self.assertEqual(
            capabilities["error"],
            "wechat_native_external_capabilities_failed",
        )
        self.assertEqual(capabilities["window_input_attempts"], 0)
        self.assertFalse(send_result["ok"])
        self.assertFalse(send_result["sent"])
        self.assertEqual(send_result["window_input_attempts"], 0)
        self.assertEqual(send_result["keyboard_input_attempts"], 0)
        self.assertEqual(send_result["clipboard_write_attempts"], 0)

    def test_external_command_backend_requires_explicit_safety_declarations(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "underspecified_bridge.py"
            script.write_text(
                """
import json
import sys

request = json.load(sys.stdin)
if request.get("action") == "capabilities":
    print(json.dumps({
        "ok": True,
        "send_action_ready": True,
        "targets": [{"name": "File Transfer Assistant", "available": True}]
    }))
else:
    print(json.dumps({"ok": True, "sent": True, "readbackText": "marker"}))
""".lstrip(),
                encoding="utf-8",
            )
            backend = build_wechat_native_backend(
                "external-command",
                WeChatNativeEndpointConfig(
                    external_command=(sys.executable, str(script)),
                    external_command_timeout_sec=3.0,
                ),
            )

            capabilities = backend.capabilities("File Transfer Assistant")
            send_result = backend.send_message(
                {"target_name": "File Transfer Assistant", "message": "marker"}
            )

        self.assertFalse(capabilities["ok"])
        self.assertTrue(
            capabilities["error"].startswith(
                "wechat_native_external_capability_safety_not_declared:"
            )
        )
        self.assertFalse(send_result["ok"])
        self.assertTrue(
            send_result["error"].startswith(
                "wechat_native_external_send_safety_not_declared:"
            )
        )
        self.assertEqual(send_result["window_input_attempts"], 0)

    def test_main_accepts_external_command_json_for_serve_once(self):
        with tempfile.TemporaryDirectory() as td:
            script = _write_external_wechat_command(Path(td) / "wechat_bridge.py")
            registry_path = Path(td) / "wechat-native-bridges.json"
            command_json = json.dumps([sys.executable, str(script)])
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                rc = main(
                    [
                        "--port",
                        "0",
                        "--registry-path",
                        str(registry_path),
                        "--backend",
                        "external-command",
                        "--external-command-json",
                        command_json,
                        "--serve-once",
                    ]
                )
            data = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertIn("wechat_native_bridge_url=http://127.0.0.1:", output.getvalue())
        self.assertEqual(data["wechat_native_bridges"][0]["type"], "wechat_native_bridge")

    def test_main_prints_dynamic_bridge_url_before_serving(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "wechat-native-bridges.json"
            output = io.StringIO()

            def run():
                with contextlib.redirect_stdout(output):
                    main(
                        [
                            "--port",
                            "0",
                            "--registry-path",
                            str(registry_path),
                            "--serve-once",
                        ]
                    )

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            thread.join(timeout=3)
            text = output.getvalue()
            data = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertFalse(thread.is_alive())
        self.assertIn("wechat_native_bridge_url=http://127.0.0.1:", text)
        self.assertNotIn("wechat_native_bridge_url=http://127.0.0.1:0", text)
        self.assertNotEqual(data["wechat_native_bridges"][0]["url"], "http://127.0.0.1:0")


class _OwnedBackend:
    def __init__(self):
        self.paths = []

    def capabilities(self, target_name):
        self.paths.append("/v1/wechat/capabilities")
        return {
            "ok": True,
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "capabilities": ["wechat.conversation.send_message"],
            "targets": [
                {
                    "name": target_name or "File Transfer Assistant",
                    "conversation_id": "filehelper",
                    "available": True,
                }
            ],
        }

    def send_message(self, payload):
        self.paths.append("/v1/wechat/send")
        message = str(payload.get("message", "") or "")
        return {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "readbackText": f"File Transfer Assistant\n{message}",
        }


class _FakeCaptureProvider:
    def __init__(self, *, ok):
        self.ok = ok
        self.calls = []

    def capture_window(self, hwnd, output_path):
        self.calls.append((int(hwnd), str(output_path)))
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(output_path),
            ok=self.ok,
            width=800 if self.ok else 0,
            height=600 if self.ok else 0,
            foreground_hwnd_before=9001,
            foreground_hwnd_after=9001,
            error="" if self.ok else "capture_failed",
        )


class _SlowAccessibilityObserver:
    def snapshot(self):
        time.sleep(0.2)
        return ()


def _write_external_wechat_command(path: Path) -> Path:
    path.write_text(
        """
import json
import sys

request = json.load(sys.stdin)
action = request.get("action")
if action == "capabilities":
    target_name = request.get("target_name") or "File Transfer Assistant"
    print(json.dumps({
        "ok": True,
        "backend": "external-command",
        "background_safe": True,
        "native_background_safe": True,
        "requires_foreground": False,
        "foreground_required": False,
        "window_input_required": False,
        "keyboard_input_required": False,
        "mouse_input_required": False,
        "clipboard_required": False,
        "send_action_ready": True,
        "send_ready": True,
        "can_send": True,
        "capabilities": ["wechat.conversation.native_bridge_send_message"],
        "targets": [{
            "name": target_name,
            "conversation_id": "filehelper",
            "available": True
        }]
    }))
elif action == "send_message":
    payload = request.get("payload") or {}
    message = payload.get("message") or request.get("message") or ""
    target_name = payload.get("target_name") or request.get("target_name") or "File Transfer Assistant"
    print(json.dumps({
        "ok": True,
        "sent": True,
        "backend": "external-command",
        "foreground_focus_stable": True,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
        "readbackText": target_name + "\\n" + message
    }))
else:
    print(json.dumps({"ok": False, "error": "unknown_action"}))
    sys.exit(2)
""".lstrip(),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
