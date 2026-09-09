import unittest

from openwukong.control.desktop_system_dialog import (
    _should_probe_child_texts_for_system_dialog,
    run_desktop_system_dialog_preflight,
)


class _Observer:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def capture_system_dialogs(self):
        return self.snapshots


class DesktopSystemDialogPreflightTests(unittest.TestCase):
    def test_detects_codex_msix_electron_click_tag_dialog(self):
        report = run_desktop_system_dialog_preflight(
            observer=_Observer(
                [
                    {
                        "hwnd": 301,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "text": (
                            "Error launching app\n"
                            "Unable to find Electron app at "
                            "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                            "?type=click&tag=11634605478613629973\n"
                            "Cannot find module"
                        ),
                    }
                ]
            )
        ).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "system_dialog_detected")
        self.assertTrue(report["system_dialog_detected"])
        self.assertEqual(report["system_dialog_count"], 1)
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 0)

    def test_clear_when_observer_reports_unrelated_window(self):
        report = run_desktop_system_dialog_preflight(
            observer=_Observer(
                [
                    {
                        "hwnd": 100,
                        "title": "Search - Google Chrome",
                        "process_name": "chrome.exe",
                    }
                ]
            )
        ).to_dict()

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "system_dialog_clear")
        self.assertFalse(report["system_dialog_detected"])
        self.assertEqual(report["system_dialog_count"], 0)

    def test_generic_windowsapps_error_without_codex_evidence_is_not_system_dialog(self):
        report = run_desktop_system_dialog_preflight(
            observer=_Observer(
                [
                    {
                        "hwnd": 500,
                        "title": "Error",
                        "process_name": "Notepad.exe",
                        "executable_path": (
                            "C:/Program Files/WindowsApps/"
                            "Microsoft.WindowsNotepad_11.2604/Notepad.exe"
                        ),
                    }
                ]
            )
        ).to_dict()

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "system_dialog_clear")
        self.assertFalse(report["system_dialog_detected"])

    def test_child_text_probe_is_limited_to_likely_system_dialog_candidates(self):
        self.assertFalse(
            _should_probe_child_texts_for_system_dialog(
                {
                    "title": "notes.txt - Notepad",
                    "class_name": "Notepad",
                    "process_name": "Notepad.exe",
                    "executable_path": (
                        "C:/Program Files/WindowsApps/"
                        "Microsoft.WindowsNotepad_11.2604/Notepad.exe"
                    ),
                }
            )
        )
        self.assertTrue(
            _should_probe_child_texts_for_system_dialog(
                {
                    "title": "Error",
                    "class_name": "#32770",
                    "process_name": "",
                    "executable_path": "",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
