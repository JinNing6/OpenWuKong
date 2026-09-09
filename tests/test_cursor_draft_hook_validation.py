import unittest
from pathlib import Path

from openwukong.evaluation.cursor_draft_hook_validation import (
    validate_cursor_draft_hook,
)


class CursorDraftHookValidationTests(unittest.TestCase):
    def test_dry_run_validation_does_not_write_or_readback(self):
        client = _DraftHookClient()
        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_DRY_RUN",
            allow_write=False,
            bridge_client=client,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "cursor-draft-hook-validation")
        self.assertEqual(data["safety_mode"], "dry_run_bridge_contract")
        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "cursor_draft_hook_dry_run_ready")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertEqual(data["bridge_probe_attempts"], 1)
        self.assertEqual(data["readonly_command_attempts"], 0)
        self.assertEqual(client.calls[0]["allow_write"], False)

    def test_isolated_write_validation_requires_readback_and_stable_focus(self):
        client = _DraftHookClient()

        def live_state_runner(**kwargs):
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 2,
                "composers": [
                    {
                        "composer_id": "composer-1",
                        "text": "OPENWUKONG_ISOLATED_WRITE",
                        "rich_text": "OPENWUKONG_ISOLATED_WRITE",
                    }
                ],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path=Path("E:/ideaProjects/agent/openwukong"),
            message="OPENWUKONG_ISOLATED_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
            bridge_client=client,
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validated")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["draft_write_attempts"], 1)
        self.assertEqual(data["bridge_probe_attempts"], 2)
        self.assertEqual(data["readonly_command_attempts"], 2)
        self.assertTrue(data["readback_verified"])
        self.assertFalse(data["foreground_changed"])
        self.assertFalse(data["system_dialog_detected"])
        self.assertEqual(client.calls[0]["allow_write"], False)
        self.assertEqual(client.calls[0]["safety_profile"], "isolated_cursor_draft_probe")
        self.assertEqual(client.calls[1]["allow_write"], True)

    def test_isolated_write_readback_uses_created_composer_id_from_write_response(self):
        seen = {}

        def live_state_runner(**kwargs):
            seen["composer_ids"] = kwargs["composer_ids"]
            seen["include_handles"] = kwargs["include_handles"]
            seen["safety_profile"] = kwargs["safety_profile"]
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 1,
                "composers": [
                    {
                        "composer_id": "created-composer",
                        "text": "OPENWUKONG_CREATED_COMPOSER_WRITE",
                    }
                ],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_CREATED_COMPOSER_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            bridge_client=_DraftHookClient(write_composer_id="created-composer"),
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validated")
        self.assertEqual(seen["composer_ids"], ("created-composer",))
        self.assertTrue(seen["include_handles"])
        self.assertEqual(seen["safety_profile"], "isolated_cursor_read_probe")

    def test_live_attach_write_validation_uses_local_storage_readback_without_handles(self):
        seen = {}

        def cursor_transcript_readback_runner(**kwargs):
            seen.update(kwargs)
            return {
                "decision": "cursor_transcript_readback_accepted",
                "ok": True,
                "required_response_role": "user",
                "required_markers_found": ["OPENWUKONG_LIVE_DRAFT_WRITE"],
                "missing_required_markers": [],
                "response_marker_locations": [
                    {
                        "family": "composerData",
                        "key": "composerData:created-composer",
                        "marker": "OPENWUKONG_LIVE_DRAFT_WRITE",
                        "role": "user",
                    }
                ],
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_LIVE_DRAFT_WRITE",
            allow_write=True,
            safety_profile="live_cursor_attach_draft_write_probe",
            bridge_client=_DraftHookClient(write_decision="cursor_draft_hook_live_attach_written"),
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            live_state_runner=lambda **kwargs: self.fail("live handle readback must not run"),
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validated")
        self.assertEqual(data["safety_mode"], "live_attach_draft_write_validation")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["draft_write_attempts"], 1)
        self.assertEqual(data["readback_report"]["required_response_role"], "user")
        self.assertEqual(seen["required_response_role"], "user")
        self.assertEqual(seen["required_markers"], ("OPENWUKONG_LIVE_DRAFT_WRITE",))
        self.assertEqual(seen["workspace_path"], "E:\\ideaProjects\\agent\\openwukong")

    def test_isolated_write_validation_rejects_system_dialog_even_if_readback_succeeds(self):
        def live_state_runner(**kwargs):
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 2,
                "composers": [
                    {
                        "composer_id": "composer-1",
                        "text": "OPENWUKONG_DIALOG_WRITE",
                    }
                ],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_DIALOG_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
            bridge_client=_DraftHookClient(),
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 300, "title": '选择应用以打开 "session-start"'},
                {"hwnd": 300, "title": '选择应用以打开 "session-start"'},
            ]),
            post_action_observation_delay_sec=0.001,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validation_failed_system_dialog")
        self.assertTrue(data["system_dialog_detected"])
        self.assertTrue(data["foreground_changed"])
        self.assertFalse(data["readback_verified"])

    def test_isolated_write_validation_rejects_codex_msix_electron_error_dialog(self):
        def live_state_runner(**kwargs):
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 2,
                "composers": [
                    {
                        "composer_id": "composer-1",
                        "text": "OPENWUKONG_ELECTRON_ERROR_WRITE",
                    }
                ],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_ELECTRON_ERROR_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
            bridge_client=_DraftHookClient(),
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence(
                [
                    {"hwnd": 100, "title": "Weixin"},
                    {"hwnd": 100, "title": "Weixin"},
                    {
                        "hwnd": 301,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "text": (
                            "Error launching app\n"
                            "Unable to find Electron app at "
                            "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                            "?type=click&tag=9560196064345231071\n"
                            "Cannot find module"
                        ),
                    },
                    {
                        "hwnd": 301,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "text": "Cannot find module",
                    },
                ]
            ),
            post_action_observation_delay_sec=0.001,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validation_failed_system_dialog")
        self.assertTrue(data["system_dialog_detected"])
        self.assertTrue(data["foreground_changed"])
        self.assertFalse(data["readback_verified"])

    def test_isolated_write_validation_rejects_codex_attach_console_error_dialog(self):
        def live_state_runner(**kwargs):
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 2,
                "composers": [
                    {
                        "composer_id": "composer-1",
                        "text": "OPENWUKONG_ATTACH_CONSOLE_WRITE",
                    }
                ],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_ATTACH_CONSOLE_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
            bridge_client=_DraftHookClient(),
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence(
                [
                    {"hwnd": 100, "title": "Weixin"},
                    {"hwnd": 100, "title": "Weixin"},
                    {
                        "hwnd": 303,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "child_texts": [
                            "A JavaScript error occurred in the main process",
                            "Uncaught Exception:",
                            "Error: AttachConsole failed",
                        ],
                    },
                    {
                        "hwnd": 303,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "text": "Error: AttachConsole failed",
                    },
                ]
            ),
            post_action_observation_delay_sec=0.001,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validation_failed_system_dialog")
        self.assertTrue(data["system_dialog_detected"])
        self.assertTrue(data["foreground_changed"])
        self.assertFalse(data["readback_verified"])

    def test_isolated_write_validation_rejects_missing_readback_marker(self):
        def live_state_runner(**kwargs):
            return {
                "decision": "cursor_live_composer_state_ready",
                "readonly_command_attempts": 2,
                "composers": [{"composer_id": "composer-1", "text": ""}],
            }

        report = validate_cursor_draft_hook(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_MISSING_READBACK",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
            bridge_client=_DraftHookClient(),
            live_state_runner=live_state_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
                {"hwnd": 100, "title": "Weixin"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_validation_failed_readback")
        self.assertFalse(data["readback_verified"])
        self.assertFalse(data["foreground_changed"])


class _DraftHookClient:
    def __init__(self, *, write_composer_id="composer-1", write_decision="cursor_draft_hook_written"):
        self.calls = []
        self.write_composer_id = write_composer_id
        self.write_decision = write_decision

    def cursor_draft_hook(
        self,
        bridge_url,
        target,
        *,
        message,
        allow_write=False,
        safety_profile="",
        composer_ids=None,
    ):
        del bridge_url, target
        self.calls.append(
            {
                "message": message,
                "allow_write": allow_write,
                "safety_profile": safety_profile,
                "composer_ids": list(composer_ids or []),
            }
        )
        return {
            "ok": True,
            "decision": self.write_decision if allow_write else "cursor_draft_hook_ready",
            "dry_run": not allow_write,
            "can_write_draft": True,
            "composer_id": self.write_composer_id if allow_write else (composer_ids or ["composer-1"])[0],
        }


class _FocusSequence:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture(self):
        if self.index >= len(self.snapshots):
            return dict(self.snapshots[-1])
        value = dict(self.snapshots[self.index])
        self.index += 1
        return value


if __name__ == "__main__":
    unittest.main()
