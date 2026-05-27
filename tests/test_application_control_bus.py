import contextlib
import io
import json
import unittest

from openwukong.control.application_bus import (
    ApplicationControlBus,
    ControlElementSnapshot,
    ControlTarget,
    InputActionOptions,
    TextHit,
)
from openwukong.evaluation.uia_input_probe import main


class _FakeInputBackend:
    def __init__(self):
        self.text = ""
        self.clipboard_restored = False
        self.calls = []
        self.element = object()

    def find_input(self, target):
        self.calls.append(("find_input", target.pid))
        return self.element

    def snapshot_element(self, element):
        self.calls.append(("snapshot_element", element is self.element))
        return ControlElementSnapshot(
            control_type="Edit",
            name="",
            automation_id="",
            rect=(1747, 224, 2504, 281),
            value_preview=self.text,
        )

    def focus_window(self, target):
        self.calls.append(("focus_window", target.window_title))

    def focus_input(self, element):
        self.calls.append(("focus_input", element is self.element))

    def clear_input(self, element):
        self.calls.append(("clear_input", element is self.element))
        self.text = ""

    def set_text(self, element, text):
        self.calls.append(("set_text", text))
        return True

    def paste_text(self, element, text):
        self.calls.append(("paste_text", text))
        self.text = text
        return True

    def type_text(self, element, text):
        self.calls.append(("type_text", text))
        self.text = text
        return True

    def visible_text_hits(self, target, token):
        self.calls.append(("visible_text_hits", token))
        if token != self.text:
            return ()
        return (
            TextHit(
                source="value_preview",
                text_preview=self.text,
                control_type="Edit",
                rect=(1747, 224, 2504, 281),
            ),
        )

    def restore_clipboard(self):
        self.calls.append(("restore_clipboard",))
        self.clipboard_restored = True


class _FakeNoOpClearBackend(_FakeInputBackend):
    def clear_input(self, element):
        self.calls.append(("clear_input_noop", element is self.element))

    def force_clear_input(self, element):
        self.calls.append(("force_clear_input", element is self.element))
        self.text = ""
        return True


class _FakeSetTextBackend(_FakeInputBackend):
    def set_text(self, element, text):
        self.calls.append(("set_text", text))
        self.text = text
        return True


class ApplicationControlBusTests(unittest.TestCase):
    def test_write_text_falls_back_to_paste_when_set_text_is_not_verified(self):
        backend = _FakeInputBackend()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(clear_after=True),
        )
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(data["mode"], "application-control-input-action")
        self.assertEqual(data["safety_mode"], "non_submit_write_verify_clear")
        self.assertEqual(data["control_attempts"], 2)
        self.assertEqual(data["write_method"], "clipboard_paste")
        self.assertFalse(data["submitted"])
        self.assertTrue(data["token_visible_after_write"])
        self.assertFalse(data["token_visible_after_clear"])
        self.assertEqual(backend.text, "")
        self.assertTrue(backend.clipboard_restored)
        self.assertIn(("set_text", "OPENWUKONG_TOKEN"), backend.calls)
        self.assertIn(("paste_text", "OPENWUKONG_TOKEN"), backend.calls)

    def test_write_text_fails_when_no_method_verifies_visible_text(self):
        backend = _FakeInputBackend()
        backend.visible_text_hits = lambda target, token: ()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(clear_after=True, methods=("set_text",)),
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.to_dict()["error"], "write_not_verified")
        self.assertEqual(report.to_dict()["control_attempts"], 1)

    def test_clear_after_uses_force_clear_when_regular_clear_is_not_verified(self):
        backend = _FakeNoOpClearBackend()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(clear_after=True, methods=("clipboard_paste",)),
        )

        self.assertTrue(report.ok)
        self.assertFalse(report.to_dict()["token_visible_after_clear"])
        self.assertIn(("clear_input_noop", True), backend.calls)
        self.assertIn(("force_clear_input", True), backend.calls)

    def test_background_mode_does_not_use_focus_clipboard_or_keyboard_fallbacks(self):
        backend = _FakeInputBackend()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(allow_foreground_interaction=False),
        )
        data = report.to_dict()

        self.assertFalse(report.ok)
        self.assertEqual(data["error"], "foreground_required")
        self.assertTrue(data["foreground_required"])
        self.assertFalse(data["foreground_interaction_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertIn(("set_text", "OPENWUKONG_TOKEN"), backend.calls)
        self.assertNotIn(("focus_window", "config - PaoPaoHeZi - Cursor"), backend.calls)
        self.assertNotIn(("paste_text", "OPENWUKONG_TOKEN"), backend.calls)
        self.assertNotIn(("type_text", "OPENWUKONG_TOKEN"), backend.calls)

    def test_background_mode_can_write_and_clear_when_set_text_verifies(self):
        backend = _FakeSetTextBackend()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(allow_foreground_interaction=False, clear_after=True),
        )
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(data["safety_mode"], "background_semantic_write_verify_clear")
        self.assertEqual(data["write_method"], "set_text")
        self.assertFalse(data["foreground_required"])
        self.assertFalse(data["foreground_interaction_allowed"])
        self.assertFalse(data["token_visible_after_clear"])
        self.assertEqual(backend.text, "")
        self.assertIn(("set_text", "OPENWUKONG_TOKEN"), backend.calls)
        self.assertIn(("set_text", ""), backend.calls)
        self.assertNotIn(("focus_window", "config - PaoPaoHeZi - Cursor"), backend.calls)
        self.assertNotIn(("paste_text", "OPENWUKONG_TOKEN"), backend.calls)

    def test_submit_is_rejected_unless_explicitly_allowed(self):
        backend = _FakeInputBackend()
        bus = ApplicationControlBus(backend)

        report = bus.write_text(
            ControlTarget(pid=50200, process_name="Cursor.exe", window_title="config - PaoPaoHeZi - Cursor"),
            "OPENWUKONG_TOKEN",
            InputActionOptions(submit=True, allow_submit=False),
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.to_dict()["error"], "submit_not_allowed")
        self.assertEqual(report.to_dict()["control_attempts"], 0)
        self.assertNotIn(("paste_text", "OPENWUKONG_TOKEN"), backend.calls)

    def test_probe_cli_outputs_bus_report_json(self):
        backend = _FakeInputBackend()
        bus = ApplicationControlBus(backend)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--pid",
                    "50200",
                    "--process-name",
                    "Cursor.exe",
                    "--window-title",
                    "config - PaoPaoHeZi - Cursor",
                    "--token",
                    "OPENWUKONG_TOKEN",
                    "--json",
                ],
                bus=bus,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"]["pid"], 50200)
        self.assertEqual(data["write_method"], "clipboard_paste")

    def test_probe_cli_supports_background_safe_mode(self):
        backend = _FakeInputBackend()
        bus = ApplicationControlBus(backend)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--pid",
                    "50200",
                    "--process-name",
                    "Cursor.exe",
                    "--window-title",
                    "config - PaoPaoHeZi - Cursor",
                    "--token",
                    "OPENWUKONG_TOKEN",
                    "--background-safe",
                    "--json",
                ],
                bus=bus,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertFalse(data["foreground_interaction_allowed"])
        self.assertTrue(data["foreground_required"])


if __name__ == "__main__":
    unittest.main()
