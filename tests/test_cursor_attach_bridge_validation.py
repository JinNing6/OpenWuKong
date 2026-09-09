import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.cursor_attach_bridge_validation import (
    run_cursor_attach_bridge_validation,
)


class CursorAttachBridgeValidationTests(unittest.TestCase):
    def test_attach_only_validates_existing_bridge_without_launching_gui(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = _Calls()

            report = run_cursor_attach_bridge_validation(
                bridge_url="http://127.0.0.1:18888",
                workspace_path=root / "workspace",
                message="OPENWUKONG_ATTACH_ONLY_DRY_RUN",
                output_path=root / "report.json",
                focus_observer=_FocusSequence(
                    [
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                    ]
                ),
                bridge_waiter=calls.waiter,
                validator=calls.validator,
            )
            data = report.to_dict()
            self.assertTrue((root / "report.json").exists())

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "cursor_attach_bridge_dry_run_ready")
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["stop_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertFalse(data["foreground_changed"])
        self.assertFalse(data["system_dialog_detected"])
        self.assertEqual(calls.wait_calls, 1)
        self.assertEqual(calls.validation_calls, 1)
        self.assertEqual(calls.validation_kwargs["allow_write"], False)
        self.assertEqual(calls.validation_kwargs["safety_profile"], "live_cursor_attach_draft_probe")

    def test_attach_only_reports_bridge_missing_without_launching_or_validating(self):
        calls = _Calls(wait_ok=False)

        report = run_cursor_attach_bridge_validation(
            bridge_url="http://127.0.0.1:19999",
            message="OPENWUKONG_ATTACH_ONLY_DRY_RUN",
            focus_observer=_FocusSequence(
                [
                    {"available": True, "hwnd": 20, "title": "Codex"},
                    {"available": True, "hwnd": 20, "title": "Codex"},
                ]
            ),
            bridge_waiter=calls.waiter,
            validator=calls.validator,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_attach_bridge_not_ready")
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(calls.wait_calls, 1)
        self.assertEqual(calls.validation_calls, 0)

    def test_attach_only_reports_stale_bridge_when_draft_hook_endpoint_is_missing(self):
        calls = _Calls(validation_ok=False, validation_error="not_found")

        report = run_cursor_attach_bridge_validation(
            bridge_url="http://127.0.0.1:18888",
            message="OPENWUKONG_ATTACH_ONLY_DRY_RUN",
            focus_observer=_FocusSequence(
                [
                    {"available": True, "hwnd": 20, "title": "Codex"},
                    {"available": True, "hwnd": 20, "title": "Codex"},
                    {"available": True, "hwnd": 20, "title": "Codex"},
                ]
            ),
            bridge_waiter=calls.waiter,
            validator=calls.validator,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_attach_bridge_draft_hook_unavailable")
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertEqual(calls.wait_calls, 1)
        self.assertEqual(calls.validation_calls, 1)

    def test_attach_only_rejects_write_without_explicit_safety_profile(self):
        calls = _Calls()

        report = run_cursor_attach_bridge_validation(
            bridge_url="http://127.0.0.1:18888",
            message="OPENWUKONG_ATTACH_ONLY_WRITE",
            allow_write=True,
            safety_profile="",
            focus_observer=_FocusSequence(
                [
                    {"available": True, "hwnd": 20, "title": "Codex"},
                ]
            ),
            bridge_waiter=calls.waiter,
            validator=calls.validator,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_attach_bridge_write_blocked")
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertEqual(calls.wait_calls, 0)
        self.assertEqual(calls.validation_calls, 0)


class _Calls:
    def __init__(self, *, wait_ok=True, validation_ok=True, validation_error=""):
        self.wait_ok = wait_ok
        self.validation_ok = validation_ok
        self.validation_error = validation_error
        self.wait_calls = 0
        self.validation_calls = 0
        self.validation_kwargs = {}

    def waiter(self, **kwargs):
        self.wait_calls += 1
        return {
            "ok": self.wait_ok,
            "decision": "ide_bridge_ready" if self.wait_ok else "ide_bridge_not_ready",
            "attempts": 1,
            "bridge_url": kwargs.get("bridge_url", ""),
            "metadata": {"ide_name": "Cursor"},
            "error": "" if self.wait_ok else "connection_refused",
        }

    def validator(self, **kwargs):
        self.validation_calls += 1
        self.validation_kwargs = dict(kwargs)
        return {
            "ok": self.validation_ok,
            "decision": (
                "cursor_draft_hook_dry_run_ready"
                if self.validation_ok
                else "cursor_draft_hook_dry_run_failed"
            ),
            "allow_write": kwargs.get("allow_write", False),
            "safety_profile": kwargs.get("safety_profile", ""),
            "control_attempts": 0,
            "window_input_attempts": 0,
            "bridge_send_attempts": 0,
            "draft_write_attempts": 0,
            "foreground_changed": False,
            "system_dialog_detected": False,
            "readback_verified": False,
            "dry_run_report": {
                "error": self.validation_error,
                "response": {"error": self.validation_error},
            },
            "error": self.validation_error,
        }


class _FocusSequence:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture(self):
        if self.index >= len(self.snapshots):
            value = self.snapshots[-1]
        else:
            value = self.snapshots[self.index]
        self.index += 1
        return dict(value)


if __name__ == "__main__":
    unittest.main()
