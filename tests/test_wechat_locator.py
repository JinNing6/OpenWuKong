import unittest

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)
from openwukong.evaluation.wechat_locator import (
    MsaaAccessibleSnapshot,
    StaticMsaaObserver,
    StaticWin32WindowObserver,
    Win32ChildWindowSnapshot,
    build_wechat_locator_report,
)


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(10, 20, 300, 60),
        is_enabled=True,
        patterns=tuple(patterns),
    )


class WeChatLocatorTests(unittest.TestCase):
    def test_merges_uia_and_win32_evidence_without_control_attempts(self):
        windows = (
            AccessibilityWindowSnapshot(
                pid=7101,
                process_name="Weixin.exe",
                window_title="文件传输助手 - 微信",
                class_name="Qt51514QWindowIcon",
                hwnd=1001,
                elements=(
                    _element("List", name="chat list", patterns=("Selection",)),
                    _element("Edit", name="输入", patterns=("Value", "Text")),
                    _element("Button", name="发送", patterns=("Invoke",)),
                ),
            ),
            AccessibilityWindowSnapshot(
                pid=7102,
                process_name="notepad.exe",
                window_title="notes",
                hwnd=2001,
            ),
        )
        win32_observer = StaticWin32WindowObserver(
            {
                1001: (
                    Win32ChildWindowSnapshot(
                        hwnd=1101,
                        parent_hwnd=1001,
                        class_name="Qt51514QWindowIcon",
                        text_preview="",
                        rect=(0, 0, 800, 600),
                        is_visible=True,
                        is_enabled=True,
                    ),
                    Win32ChildWindowSnapshot(
                        hwnd=1102,
                        parent_hwnd=1001,
                        class_name="Edit",
                        text_preview="",
                        rect=(20, 540, 760, 590),
                        is_visible=True,
                        is_enabled=True,
                    ),
                )
            }
        )

        report = build_wechat_locator_report(
            windows,
            win32_observer=win32_observer,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "wechat-read-only-locator")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertTrue(data["read_only_verified"])
        self.assertFalse(data["write_control_ready"])
        self.assertEqual(data["control_decision"], "read_only_verified_write_blocked")
        self.assertEqual(data["window_count"], 1)

        window = data["windows"][0]
        self.assertEqual(window["process_name"], "Weixin.exe")
        self.assertEqual(window["top_level_hwnd"], 1001)
        self.assertEqual(window["uia_semantic_input_count"], 1)
        self.assertEqual(window["win32_child_window_count"], 2)
        self.assertEqual(window["win32_class_counts"]["Edit"], 1)
        self.assertGreaterEqual(window["draft_locator_candidate_count"], 2)
        self.assertFalse(window["write_control_ready"])
        self.assertIn("wechat-native-bridge-required", window["recommended_routes"])

    def test_merges_msaa_accessible_read_only_evidence(self):
        windows = (
            AccessibilityWindowSnapshot(
                pid=7201,
                process_name="Weixin.exe",
                window_title="文件传输助手 - 微信",
                class_name="Qt51514QWindowIcon",
                hwnd=2001,
                elements=(_element("Pane", name="微信"),),
            ),
        )
        win32_observer = StaticWin32WindowObserver(
            {
                2001: (
                    Win32ChildWindowSnapshot(
                        hwnd=2101,
                        parent_hwnd=2001,
                        class_name="Chrome_WidgetWin_0",
                        rect=(0, 0, 800, 600),
                        is_visible=True,
                        is_enabled=True,
                    ),
                )
            }
        )
        msaa_observer = StaticMsaaObserver(
            {
                2001: (
                    MsaaAccessibleSnapshot(
                        hwnd=2001,
                        object_id="OBJID_CLIENT",
                        name="微信",
                        role="ROLE_SYSTEM_CLIENT",
                        state="focusable",
                        child_count=1,
                        source="AccessibleObjectFromWindow",
                    ),
                ),
                2101: (
                    MsaaAccessibleSnapshot(
                        hwnd=2101,
                        object_id="OBJID_CLIENT",
                        name="",
                        role="ROLE_SYSTEM_PANE",
                        value_preview="",
                        state="visible",
                        child_count=0,
                        source="AccessibleObjectFromWindow",
                    ),
                ),
            }
        )

        report = build_wechat_locator_report(
            windows,
            win32_observer=win32_observer,
            msaa_observer=msaa_observer,
        )
        window = report.to_dict()["windows"][0]

        self.assertEqual(window["msaa_object_count"], 2)
        self.assertEqual(window["msaa_name_count"], 1)
        self.assertEqual(window["msaa_role_counts"]["ROLE_SYSTEM_CLIENT"], 1)
        self.assertEqual(window["msaa_role_counts"]["ROLE_SYSTEM_PANE"], 1)
        self.assertIn("AccessibleObjectFromWindow", window["msaa_sources"])
        self.assertIn("get_accName", window["msaa_read_methods"])
        self.assertIn("get_accRole", window["msaa_read_methods"])
        self.assertIn("accDoDefaultAction", window["blocked_msaa_mutation_methods"])
        self.assertIn("put_accValue", window["blocked_msaa_mutation_methods"])
        self.assertEqual(window["control_decision"], "read_only_verified_write_blocked")
        self.assertFalse(window["write_control_ready"])
        self.assertIn("msaa-read-only", window["recommended_routes"])


if __name__ == "__main__":
    unittest.main()
