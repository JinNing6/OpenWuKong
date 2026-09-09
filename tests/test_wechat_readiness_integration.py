import unittest

from openwukong.connectors import WeChatDesktopConnector
from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.registry import ConnectorManager
from openwukong.control.fabric import ControlIntent


TARGET = ConnectorTarget(
    pid=7101,
    process_name="Weixin.exe",
    window_title="微信",
    conversation_name="张三",
)


class _ReadBackend:
    def read_conversation(self, target, parameters):
        return {"messages": [], "readback_verified": True}


class WeChatReadinessIntegrationTests(unittest.TestCase):
    def test_connector_is_exported_and_resolvable_for_personal_wechat(self):
        connector = WeChatDesktopConnector(backend=_ReadBackend())
        manager = ConnectorManager([connector])

        resolved = manager.resolve_session_connector(TARGET, preferred="wechat-desktop")

        self.assertIs(resolved, connector)
        self.assertIn("app-native-bridge-required", connector.route_ids)
        self.assertIn("uia-semantic", connector.route_ids)
        self.assertTrue(connector.route_ready("app-native-bridge-required", TARGET))

    def test_connector_does_not_claim_unsupported_action(self):
        connector = WeChatDesktopConnector(backend=_ReadBackend())

        self.assertTrue(
            connector.supports_action("wechat.chat.read", TARGET)
        )
        self.assertFalse(
            connector.supports_action("wechat.chat.send_text", TARGET)
        )

        result = connector.execute_action(
            TARGET,
            ControlIntent(action="wechat.chat.send_text", parameters={"text": "x"}),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_side_effect_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
