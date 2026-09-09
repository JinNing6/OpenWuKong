import unittest
from datetime import datetime, timezone

from openwukong.control.desktop_action import (
    DesktopAction,
    DesktopApproval,
    DesktopTarget,
)
from openwukong.control.desktop_action_planner import plan_desktop_action
from openwukong.control.surface_capabilities import SurfaceCapabilityProfile


NOW = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)


def _wechat_action(*, approval=None):
    return DesktopAction(
        action="wechat.chat.send_text",
        target=DesktopTarget(
            process_name="Weixin.exe",
            window_title="微信",
            pid=123,
            hwnd=456,
            conversation_name="张三",
        ),
        parameters={
            "text": "hello",
            "wechat_native_bridge_url": "http://127.0.0.1:18888",
            "background_screenshot_count": 1,
            "background_screenshot_success_count": 1,
        },
        effect_class="external_communication",
        approval=approval
        or DesktopApproval(
            required=True,
            confirmed=True,
            allow_foreground=False,
            approval_id="approval-1",
        ),
    )


def _profile(capabilities):
    return SurfaceCapabilityProfile(
        process_name="Weixin.exe",
        window_title="微信",
        pid=123,
        hwnd=456,
        observed_at=NOW,
        capabilities=capabilities,
    )


class _NativeConnector:
    connector_id = "wechat-native-bridge"
    route_id = "app-native-bridge-required"

    def __init__(self, ready=True):
        self.ready = ready

    def supports_target(self, target):
        return target.process_name.casefold() in {"wechat.exe", "weixin.exe"}

    def route_ready(self, route_id, target):
        return (
            self.ready
            and route_id == self.route_id
            and self.supports_target(target)
            and bool(target.wechat_native_bridge_url)
            and target.background_screenshot_success_count == 1
        )


class _ForegroundConnector(_NativeConnector):
    execution_mode = "foreground_desktop"


class DesktopActionPlannerTests(unittest.TestCase):
    def test_native_connector_is_preferred_when_action_and_target_are_ready(self):
        plan = plan_desktop_action(
            action=_wechat_action(),
            profile=_profile(
                {
                    "wechat.chat.send_text": {
                        "route": "uia-semantic",
                        "confidence": 90,
                        "read_only": False,
                    }
                }
            ),
            connectors=(_NativeConnector(),),
            now=NOW,
        )

        self.assertFalse(plan.blocked)
        self.assertEqual(plan.selected_route, "app-native-bridge-required")
        self.assertEqual(plan.selected_connector_id, "wechat-native-bridge")
        self.assertEqual(plan.execution_mode, "background_native")
        self.assertTrue(plan.background_safe)

    def test_wechat_without_native_bridge_uses_verified_uia_semantic_fallback(self):
        plan = plan_desktop_action(
            action=_wechat_action(),
            profile=_profile(
                {
                    "wechat.chat.send_text": {
                        "route": "uia-semantic",
                        "confidence": 90,
                        "read_only": False,
                    }
                }
            ),
            connectors=(),
            now=NOW,
        )

        self.assertFalse(plan.blocked)
        self.assertEqual(plan.selected_route, "uia-semantic")
        self.assertEqual(plan.execution_mode, "background_semantic")
        self.assertTrue(plan.background_safe)
        self.assertFalse(plan.foreground_required)

    def test_missing_write_capability_is_blocked_without_attempts(self):
        plan = plan_desktop_action(
            action=_wechat_action(),
            profile=_profile(
                {
                    "wechat.chat.read": {
                        "route": "uia-structural-observe",
                        "confidence": 90,
                        "read_only": True,
                    }
                }
            ),
            connectors=(),
            now=NOW,
        )

        self.assertTrue(plan.blocked)
        self.assertEqual(plan.reason, "capability_missing")
        self.assertEqual(plan.control_attempts, 0)
        self.assertEqual(plan.execution_mode, "none")

    def test_structural_write_requires_exact_foreground_approval(self):
        action = _wechat_action(
            approval=DesktopApproval(
                required=True,
                confirmed=True,
                allow_foreground=True,
                approval_id="approval-foreground",
            )
        )
        plan = plan_desktop_action(
            action=action,
            profile=_profile(
                {
                    "wechat.chat.send_text": {
                        "route": "uia-structural",
                        "confidence": 80,
                        "read_only": False,
                    }
                }
            ),
            connectors=(),
            now=NOW,
        )

        self.assertFalse(plan.blocked)
        self.assertEqual(plan.selected_route, "uia-structural")
        self.assertEqual(plan.execution_mode, "foreground_desktop")
        self.assertTrue(plan.foreground_required)
        self.assertFalse(plan.background_safe)

    def test_external_communication_without_approval_is_blocked_before_routing(self):
        plan = plan_desktop_action(
            action=_wechat_action(
                approval=DesktopApproval(required=True, confirmed=False)
            ),
            profile=_profile(
                {
                    "wechat.chat.send_text": {
                        "route": "uia-semantic",
                        "confidence": 90,
                        "read_only": False,
                    }
                }
            ),
            connectors=(_NativeConnector(),),
            now=NOW,
        )

        self.assertTrue(plan.blocked)
        self.assertEqual(plan.reason, "side_effect_confirmation_required")
        self.assertEqual(plan.selected_route, "")
        self.assertEqual(plan.control_attempts, 0)

    def test_connector_declaring_foreground_mode_is_not_promoted_to_background(self):
        plan = plan_desktop_action(
            action=_wechat_action(),
            profile=_profile(
                {
                    "wechat.chat.send_text": {
                        "route": "uia-semantic",
                        "confidence": 90,
                        "read_only": False,
                    }
                }
            ),
            connectors=(_ForegroundConnector(),),
            now=NOW,
        )

        self.assertFalse(plan.blocked)
        self.assertEqual(plan.execution_mode, "foreground_desktop")
        self.assertTrue(plan.foreground_required)
        self.assertFalse(plan.background_safe)


if __name__ == "__main__":
    unittest.main()
