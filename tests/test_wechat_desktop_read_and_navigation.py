import unittest

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.wechat_desktop import WeChatDesktopConnector
from openwukong.control.fabric import ControlIntent


TARGET = ConnectorTarget(
    pid=7101,
    process_name="Weixin.exe",
    window_title="微信",
    conversation_name="张三",
)


class FakeWeChatReadBackend:
    def __init__(self):
        self.events = []

    def inspect(self, target, parameters):
        self.events.append(("inspect", target.pid, parameters))
        return {"attached": True, "login_state": "logged_in"}

    def search_contact(self, target, parameters):
        self.events.append(("search_contact", target.pid, parameters))
        return {
            "candidates": [
                {"target_type": "conversation", "display_name": parameters["query"]}
            ],
            "verification": {"source": "uia", "stable": True},
        }

    def open_conversation(self, target, parameters):
        self.events.append(("open_conversation", target.pid, parameters))
        return {
            "conversation_open": True,
            "conversation_name": parameters["conversation_name"],
            "target_verified": True,
        }

    def read_conversation(self, target, parameters):
        self.events.append(("read_conversation", target.pid, parameters))
        return {
            "messages": [{"sender": "张三", "text": "hello", "id": "m1"}],
            "readback_verified": True,
        }

    def draft_text(self, target, parameters):
        self.events.append(("draft_text", target.pid, parameters))
        return {
            "composer_found": True,
            "value_set": True,
            "draft_text": parameters["text"],
            "draft_readback_verified": True,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        }

    def mark_unread(self, target, parameters):
        self.events.append(("mark_unread", target.pid, parameters))
        return {"marked_unread": True, "readback_verified": True}


class WeChatDesktopReadNavigationTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWeChatReadBackend()
        self.connector = WeChatDesktopConnector(backend=self.backend)

    def test_read_and_navigation_actions_do_not_use_desktop_input(self):
        search = self.connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.search",
                parameters={"query": "张三", "target_type": "conversation"},
            ),
        )
        read = self.connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.chat.read"),
        )

        self.assertTrue(search.success, search.error)
        self.assertTrue(read.success, read.error)
        self.assertEqual(search.payload["control_attempts"], 0)
        self.assertEqual(read.payload["control_attempts"], 0)
        self.assertEqual(read.payload["messages"][0]["text"], "hello")
        self.assertEqual(
            [event[0] for event in self.backend.events],
            ["search_contact", "read_conversation"],
        )

    def test_open_conversation_verifies_exact_target(self):
        result = self.connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.open",
                parameters={"conversation_name": "张三"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["target_verified"])
        self.assertEqual(result.payload["control_attempts"], 0)

    def test_draft_requires_readback_and_does_not_send(self):
        result = self.connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.draft",
                text="草稿内容",
                parameters={"text": "草稿内容"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["draft_readback_verified"])
        self.assertEqual(result.payload["send_attempts"], 0)
        self.assertEqual(result.payload["keyboard_input_attempts"], 0)
        self.assertEqual(result.payload["clipboard_write_attempts"], 0)

    def test_lifecycle_and_message_management_are_dispatched_by_action_name(self):
        inspect = self.connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.window.inspect"),
        )
        mark_unread = self.connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.chat.mark_unread"),
        )

        self.assertTrue(inspect.success, inspect.error)
        self.assertTrue(mark_unread.success, mark_unread.error)
        self.assertEqual(inspect.payload["control_attempts"], 0)
        self.assertEqual(mark_unread.payload["control_attempts"], 0)

    def test_non_personal_wechat_target_is_rejected_without_backend_call(self):
        target = ConnectorTarget(
            pid=7102,
            process_name="WXWork.exe",
            window_title="企业微信",
        )
        result = self.connector.execute_action(
            target,
            ControlIntent(action="wechat.chat.read"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_personal_target_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(self.backend.events, [])

    def test_unsupported_action_is_reported_as_missing_capability(self):
        result = self.connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.unknown.operation"),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_capability_missing")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(self.backend.events, [])


if __name__ == "__main__":
    unittest.main()
