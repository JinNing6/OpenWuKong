import unittest

from openwukong.control.desktop_action import (
    DesktopAction,
    DesktopApproval,
    DesktopTarget,
    DesktopVerification,
)


class DesktopActionTests(unittest.TestCase):
    def test_action_round_trip_preserves_target_parameters_and_effect(self):
        action = DesktopAction(
            action="wechat.chat.send_text",
            target=DesktopTarget(
                process_name="Weixin.exe",
                conversation_name="张三",
                pid=123,
                hwnd=456,
            ),
            parameters={"text": "hello", "emoji": False},
            effect_class="external_communication",
            verification=DesktopVerification(required_markers=("hello",)),
            approval=DesktopApproval(required=True, approval_id="approval-1"),
        )

        restored = DesktopAction.from_dict(action.to_dict())

        self.assertEqual(restored, action)

    def test_high_risk_action_requires_exact_approval(self):
        action = DesktopAction(
            action="wechat.contact.add",
            target=DesktopTarget(
                process_name="Weixin.exe",
                conversation_name="张三",
                pid=123,
                hwnd=456,
            ),
            effect_class="high_risk",
        )

        self.assertTrue(action.requires_confirmation)
        self.assertTrue(action.approval.required)
        self.assertFalse(action.approval.confirmed)

    def test_action_converts_to_legacy_control_intent_without_losing_approval(self):
        action = DesktopAction(
            action="wechat.chat.send_text",
            target=DesktopTarget(process_name="Weixin.exe", conversation_name="张三"),
            parameters={"text": "hello", "submit": True},
            effect_class="external_communication",
            approval=DesktopApproval(
                required=True,
                confirmed=True,
                allow_foreground=True,
                approval_id="approval-2",
                confirmed_effect_ids=("external_communication.send_message",),
            ),
        )

        intent = action.to_control_intent()

        self.assertEqual(intent.action, "wechat.chat.send_text")
        self.assertEqual(intent.text, "hello")
        self.assertTrue(intent.submit)
        self.assertTrue(intent.allow_submit)
        self.assertTrue(intent.allow_foreground_interaction)
        self.assertEqual(
            intent.confirmed_effect_ids,
            ("external_communication.send_message",),
        )

    def test_unknown_schema_version_is_rejected(self):
        with self.assertRaises(ValueError):
            DesktopAction.from_dict(
                {
                    "schema_version": "openwukong-desktop-action-v999",
                    "action": "wechat.chat.read",
                    "target": {"process_name": "Weixin.exe"},
                }
            )


if __name__ == "__main__":
    unittest.main()
