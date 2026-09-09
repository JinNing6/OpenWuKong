import unittest
from datetime import datetime, timezone

from openwukong.connectors.wechat_desktop import (
    WeChatSurfaceObserver,
    WeChatSurfaceSnapshot,
)
from openwukong.control.wechat_surface import WeChatTargetResolver
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


NOW = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)


def _element(control_type, name, patterns=(), automation_id=""):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        automation_id=automation_id,
        rect=(10, 20, 300, 60),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _personal_window(
    title="File Transfer Assistant - WeChat",
    *,
    pid=7101,
    hwnd=1001,
    elements=None,
):
    return AccessibilityWindowSnapshot(
        pid=pid,
        process_name="Weixin.exe",
        window_title=title,
        class_name="Qt51514QWindowIcon",
        hwnd=hwnd,
        elements=tuple(
            elements
            or (
                _element("Text", "File Transfer Assistant"),
                _element("Edit", "Type a message", ("Value", "TextEdit"), "composer"),
                _element("Button", "Send", ("Invoke",), "send"),
                _element("Button", "Moments", ("Invoke",), "moments"),
                _element("Button", "Publish", ("Invoke",), "publish"),
            )
        ),
    )


class WeChatSurfaceTests(unittest.TestCase):
    def test_observer_selects_personal_wechat_and_never_controls(self):
        enterprise = AccessibilityWindowSnapshot(
            pid=7102,
            process_name="WXWork.exe",
            window_title="企业微信",
            hwnd=1002,
            elements=(_element("Text", "企业微信"),),
        )
        observer = WeChatSurfaceObserver(
            window_source=lambda: (enterprise, _personal_window())
        )

        snapshot = observer.inspect(observed_at=NOW)

        self.assertIsInstance(snapshot, WeChatSurfaceSnapshot)
        self.assertEqual(snapshot.selected_window.pid, 7101)
        self.assertEqual(snapshot.profile.process_name, "Weixin.exe")
        self.assertEqual(snapshot.profile.control_attempts, 0)
        self.assertEqual(snapshot.control_attempts, 0)
        self.assertEqual(snapshot.login_state, "logged_in")
        self.assertTrue(snapshot.profile.supports("wechat.window.inspect", now=NOW))
        self.assertTrue(snapshot.profile.supports("wechat.window.attach", now=NOW))

    def test_observer_maps_observed_controls_to_scoped_capabilities(self):
        snapshot = WeChatSurfaceObserver(
            window_source=lambda: (_personal_window(),)
        ).inspect(observed_at=NOW)

        self.assertTrue(snapshot.profile.supports("wechat.chat.read", now=NOW))
        self.assertTrue(snapshot.profile.supports("wechat.chat.draft", now=NOW))
        self.assertTrue(snapshot.profile.supports("wechat.chat.send_text", now=NOW))
        self.assertTrue(snapshot.profile.supports("wechat.moments.read", now=NOW))
        self.assertTrue(snapshot.profile.supports("wechat.moments.publish", now=NOW))
        self.assertFalse(snapshot.profile.supports("wechat.contact.add", now=NOW))
        self.assertGreaterEqual(len(snapshot.controls), 4)

    def test_multiple_personal_windows_are_ambiguous_and_unselected(self):
        snapshot = WeChatSurfaceObserver(
            window_source=lambda: (
                _personal_window(pid=7101, hwnd=1001),
                _personal_window(pid=7103, hwnd=1003),
            )
        ).inspect(observed_at=NOW)

        self.assertIsNone(snapshot.selected_window)
        self.assertEqual(snapshot.decision, "multiple_personal_wechat_windows")
        self.assertEqual(snapshot.profile.control_attempts, 0)
        self.assertEqual(snapshot.control_attempts, 0)

    def test_login_window_is_not_reported_as_logged_in(self):
        window = _personal_window(
            title="微信登录",
            elements=(_element("Text", "请使用手机微信扫码登录"),),
        )
        snapshot = WeChatSurfaceObserver(window_source=lambda: (window,)).inspect(
            observed_at=NOW
        )

        self.assertEqual(snapshot.login_state, "logged_out")
        self.assertFalse(snapshot.profile.supports("wechat.chat.send_text", now=NOW))

    def test_target_resolver_requires_exact_match_or_explicit_selection(self):
        snapshot = WeChatSurfaceObserver(
            window_source=lambda: (
                _personal_window(
                    elements=(
                        _element("Text", "张三", ("Text",), "contact-zhang"),
                        _element("Text", "张三同学", ("Text",), "contact-zhang-classmate"),
                        _element("Edit", "Type a message", ("Value", "TextEdit"), "composer"),
                        _element("Button", "Send", ("Invoke",), "send"),
                    )
                ),
            )
        ).inspect(observed_at=NOW)
        resolver = WeChatTargetResolver()

        ambiguous = resolver.resolve(snapshot, target_type="conversation", query="张")
        exact = resolver.resolve(
            snapshot, target_type="conversation", query="张三", selected_index=0
        )

        self.assertFalse(ambiguous.ok)
        self.assertEqual(ambiguous.decision, "target_unresolved")
        self.assertEqual(ambiguous.control_attempts, 0)
        self.assertTrue(exact.ok)
        self.assertEqual(exact.selected.display_name, "张三")
        self.assertEqual(exact.control_attempts, 0)


if __name__ == "__main__":
    unittest.main()
