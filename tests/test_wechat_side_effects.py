import unittest
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.wechat_desktop import WeChatDesktopConnector
from openwukong.control.fabric import ControlIntent


TARGET = ConnectorTarget(
    pid=7101,
    process_name="Weixin.exe",
    window_title="微信",
    conversation_name="张三",
)


class FakeSideEffectBackend:
    def __init__(self):
        self.events = []

    def delete_message(self, target, parameters):
        self.events.append(("delete_message", parameters))
        return {"deleted": True, "readback_verified": True}

    def recall_message(self, target, parameters):
        self.events.append(("recall_message", parameters))
        return {"recalled": True, "readback_verified": True}

    def add_contact(self, target, parameters):
        self.events.append(("add_contact", parameters))
        return {"added": True, "readback_verified": True}

    def update_settings(self, target, parameters):
        self.events.append(("update_settings", parameters))
        return {"updated": True, "readback_verified": True}

    def minimize(self, target, parameters):
        self.events.append(("minimize", parameters))
        return {"minimized": True, "readback_verified": True}


class WeChatSideEffectTests(unittest.TestCase):
    def test_high_risk_action_requires_confirmation_without_control_attempts(self):
        backend = FakeSideEffectBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.delete",
                parameters={"message_id": "m1"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_side_effect_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(backend.events, [])

    def test_high_risk_action_requires_exact_effect_confirmation(self):
        backend = FakeSideEffectBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.delete",
                allow_submit=True,
                parameters={"message_id": "m1"},
            ),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "wechat_high_risk_confirmation_required")
        self.assertEqual(result.payload["control_attempts"], 0)
        self.assertEqual(backend.events, [])

    def test_high_risk_action_runs_once_after_exact_confirmation_and_readback(self):
        backend = FakeSideEffectBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.chat.delete",
                allow_submit=True,
                allow_blocked_side_effects=True,
                confirmed_effect_ids=("wechat.chat.delete",),
                parameters={"message_id": "m1"},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["verification"]["verified"])
        self.assertEqual(backend.events[0][0], "delete_message")

    def test_ordinary_settings_update_uses_normal_confirmation(self):
        backend = FakeSideEffectBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.settings.update",
                allow_submit=True,
                parameters={"setting": "download_directory", "value": str(Path("."))},
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["updated"])

    def test_window_minimize_is_registered_and_verified(self):
        backend = FakeSideEffectBackend()
        connector = WeChatDesktopConnector(backend=backend)

        result = connector.execute_action(
            TARGET,
            ControlIntent(
                action="wechat.window.minimize",
                allow_submit=True,
            ),
        )

        self.assertTrue(result.success, result.error)
        self.assertEqual(backend.events[0][0], "minimize")


if __name__ == "__main__":
    unittest.main()
