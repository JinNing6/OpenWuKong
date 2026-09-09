import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.wechat_desktop import WeChatDesktopConnector
from openwukong.control.fabric import ControlIntent


class FakeWeChatSendBackend:
    def __init__(self, *, verify=True):
        self.events = []
        self.verify = verify

    def send_text(self, target, parameters):
        self.events.append(("send_text", parameters))
        return {
            "sent": True,
            "send_attempts": 1,
            "message_marker": parameters["text"],
            "readback_verified": self.verify,
        }

    def send_emoji(self, target, parameters):
        self.events.append(("send_emoji", parameters))
        return {
            "sent": True,
            "send_attempts": 1,
            "emoji": parameters["emoji"],
            "readback_verified": self.verify,
        }

    def send_media(self, target, parameters):
        self.events.append(("send_media", parameters))
        return {
            "sent": True,
            "send_attempts": 1,
            "attachment_name": Path(parameters["path"]).name,
            "readback_verified": self.verify,
        }

    def send_file(self, target, parameters):
        self.events.append(("send_file", parameters))
        return {
            "sent": True,
            "send_attempts": 1,
            "attachment_name": Path(parameters["path"]).name,
            "readback_verified": self.verify,
        }


class WeChatDesktopSendTransferTests(unittest.TestCase):
    def _target(self, root):
        return ConnectorTarget(
            pid=7101,
            process_name="Weixin.exe",
            window_title="微信",
            conversation_name="张三",
            workspace_path=str(root),
        )

    def _intent(self, action, **parameters):
        return ControlIntent(
            action=action,
            parameters=parameters,
            allow_submit=True,
        )

    def test_send_text_requires_approval_and_verifies_readback(self):
        backend = FakeWeChatSendBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            self._intent("wechat.chat.send_text", text="hello"),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["send_attempts"], 1)
        self.assertTrue(result.payload["verification"]["verified"])
        self.assertEqual(backend.events[0][0], "send_text")

    def test_emoji_send_uses_same_side_effect_gate(self):
        backend = FakeWeChatSendBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            self._intent("wechat.chat.send_emoji", emoji="[鼓掌]"),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["emoji"], "[鼓掌]")

    def test_send_without_approval_is_blocked_before_backend_call(self):
        backend = FakeWeChatSendBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            ControlIntent(
                action="wechat.chat.send_text",
                parameters={"text": "must not send"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_side_effect_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(backend.events, [])

    def test_file_send_rejects_path_outside_authorized_root(self):
        backend = FakeWeChatSendBackend()
        connector = WeChatDesktopConnector(backend=backend)
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            outside = root.parent / "outside-openwukong.txt"
            outside.write_text("secret", encoding="utf-8")

            result = connector.execute_action(
                self._target(root),
                self._intent("wechat.file.send", path=str(outside)),
            )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_attachment_path_outside_root")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(backend.events, [])

    def test_file_send_records_file_metadata_and_verifies_attachment(self):
        backend = FakeWeChatSendBackend()
        connector = WeChatDesktopConnector(backend=backend)
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            attachment = root / "report.txt"
            attachment.write_text("hello file", encoding="utf-8")

            result = connector.execute_action(
                self._target(root),
                self._intent("wechat.file.send", path=str(attachment)),
            )

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["attachment_name"], "report.txt")
        self.assertEqual(result.payload["attachment"]["size"], len("hello file".encode("utf-8")))
        self.assertRegex(result.payload["attachment"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(backend.events[0][0], "send_file")

    def test_missing_readback_is_unknown_and_never_retried(self):
        backend = FakeWeChatSendBackend(verify=False)
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            self._target(Path(".")),
            self._intent("wechat.chat.send_text", text="one attempt"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_verification_failed")
        self.assertEqual(result.payload["send_attempts"], 1)
        self.assertEqual(len(backend.events), 1)


if __name__ == "__main__":
    unittest.main()
