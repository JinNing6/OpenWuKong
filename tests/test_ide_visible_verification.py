import contextlib
import io
import json
import unittest

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.ide_visible_verification import (
    main,
    verify_visible_text,
)


def _element(control_type: str, *, name: str = "", value_preview: str = ""):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        value_preview=value_preview,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=("Text",),
    )


def _window(*, process_name: str, title: str, elements):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        hwnd=100,
        elements=tuple(elements),
    )


class IDEVisibleVerificationTests(unittest.TestCase):
    def test_verify_visible_text_finds_token_in_cursor_element_value(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="Cursor.exe",
                title="[Extension Development Host] workspace - Cursor",
                elements=[
                    _element("Edit", name="Composer input", value_preview="OPENWUKONG_VISIBLE_E2E_TOKEN"),
                    _element("Text", name="Status"),
                ],
            )
        ])

        report = verify_visible_text(
            "OPENWUKONG_VISIBLE_E2E_TOKEN",
            observer=observer,
            process_names=("Cursor.exe",),
            title_contains=("workspace",),
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "ide-visible-text-verification")
        self.assertEqual(data["safety_mode"], "read_only_uia_scan")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["message_visible"])
        self.assertEqual(data["hit_count"], 1)
        self.assertEqual(data["hits"][0]["source"], "value_preview")
        self.assertEqual(data["hits"][0]["control_type"], "Edit")

    def test_verify_visible_text_filters_by_process_and_window_title(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="notepad.exe",
                title="workspace - Notepad",
                elements=[
                    _element("Edit", value_preview="OPENWUKONG_VISIBLE_E2E_TOKEN"),
                ],
            ),
            _window(
                process_name="Cursor.exe",
                title="other - Cursor",
                elements=[
                    _element("Edit", value_preview="OPENWUKONG_VISIBLE_E2E_TOKEN"),
                ],
            ),
        ])

        report = verify_visible_text(
            "OPENWUKONG_VISIBLE_E2E_TOKEN",
            observer=observer,
            process_names=("Cursor.exe",),
            title_contains=("workspace",),
        )

        self.assertFalse(report.to_dict()["message_visible"])

    def test_cli_outputs_visible_text_report_json(self):
        observer = StaticAccessibilityObserver([
            _window(
                process_name="Cursor.exe",
                title="workspace - Cursor",
                elements=[
                    _element("Document", name="OPENWUKONG_VISIBLE_E2E_TOKEN"),
                ],
            )
        ])

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "OPENWUKONG_VISIBLE_E2E_TOKEN",
                    "--process-name",
                    "Cursor.exe",
                    "--title-contains",
                    "workspace",
                    "--json",
                ],
                observer=observer,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["message_visible"])
        self.assertEqual(data["hits"][0]["source"], "name")


if __name__ == "__main__":
    unittest.main()
