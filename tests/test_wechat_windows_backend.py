import unittest

from openwukong.connectors.base import ConnectorActionResult, ConnectorTarget
from openwukong.connectors.wechat_desktop import (
    WeChatDesktopConnector,
    WeChatWindowsBackend,
)
from openwukong.control.fabric import ControlIntent
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


TARGET = ConnectorTarget(
    pid=7101,
    process_name="Weixin.exe",
    window_title="微信",
    conversation_name="张三",
)


def _snapshot(*, semantic=False):
    elements = [
        AccessibilityElementSnapshot(
            control_type="Text",
            name="张三",
            rect=(0, 0, 100, 30),
            is_enabled=True,
        )
    ]
    if semantic:
        elements.extend(
            [
                AccessibilityElementSnapshot(
                    control_type="Edit",
                    name="Type a message",
                    automation_id="composer",
                    rect=(0, 30, 300, 60),
                    is_enabled=True,
                    patterns=("Value", "TextEdit"),
                ),
                AccessibilityElementSnapshot(
                    control_type="Button",
                    name="Send",
                    automation_id="send",
                    rect=(300, 30, 350, 60),
                    is_enabled=True,
                    patterns=("Invoke",),
                ),
            ]
        )
    return AccessibilityWindowSnapshot(
        pid=7101,
        process_name="Weixin.exe",
        window_title="微信",
        class_name="Qt51514QWindowIcon",
        hwnd=1001,
        elements=tuple(elements),
    )


class FakeUiaConnector:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def probe_target(self, target):
        self.calls.append(("probe", target.pid))
        return self.snapshot

    def execute_action(self, target, intent):
        self.calls.append(("execute", intent.action, dict(intent.parameters)))
        return ConnectorActionResult(
            success=True,
            connector_id="desktop-uia",
            action=intent.action,
            payload={
                "readback_text": intent.text,
                "value_set": True,
                "readback_verified": True,
                "control_attempts": 1,
            },
        )


class FakeForegroundBackend:
    def __init__(self):
        self.calls = []

    def send_text(self, target, parameters):
        self.calls.append((target, dict(parameters)))
        return {
            "sent": True,
            "readback_verified": True,
            "send_attempts": 1,
            "post_send_verified": True,
        }


class WeChatWindowsBackendTests(unittest.TestCase):
    def test_inspect_and_read_use_uia_without_input(self):
        uia = FakeUiaConnector(_snapshot())
        backend = WeChatWindowsBackend(uia=uia, foreground=FakeForegroundBackend())
        connector = WeChatDesktopConnector(backend=backend)

        inspect = connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.window.inspect"),
        )
        read = connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.chat.read"),
        )

        self.assertTrue(inspect.success, inspect.error)
        self.assertTrue(read.success, read.error)
        self.assertEqual(inspect.payload["control_attempts"], 0)
        self.assertEqual(read.payload["control_attempts"], 0)
        self.assertEqual(read.payload["messages"][0]["text"], "张三")
        self.assertEqual([call[0] for call in uia.calls], ["probe", "probe"])

    def test_draft_uses_uia_semantic_value_set(self):
        uia = FakeUiaConnector(_snapshot(semantic=True))
        backend = WeChatWindowsBackend(uia=uia, foreground=FakeForegroundBackend())
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.draft",
                text="草稿",
                parameters={"text": "草稿"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["draft_readback_verified"])
        self.assertEqual(result.payload["send_attempts"], 0)
        self.assertEqual(uia.calls[0][0], "probe")
        self.assertEqual(uia.calls[1][0], "execute")
        self.assertEqual(uia.calls[1][1], "set_value")

    def test_send_falls_back_to_foreground_backend_when_semantic_route_is_missing(self):
        uia = FakeUiaConnector(_snapshot())
        foreground = FakeForegroundBackend()
        backend = WeChatWindowsBackend(uia=uia, foreground=foreground)
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.send_text",
                allow_submit=True,
                parameters={
                    "text": "hello",
                    "target_name": "张三",
                    "foreground_takeover_request": {"status": "approved"},
                },
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["send_attempts"], 1)
        self.assertEqual(foreground.calls[0][1]["target_name"], "张三")
        self.assertEqual(uia.calls, [("probe", 7101)])


if __name__ == "__main__":
    unittest.main()
