import unittest

from openwukong.evaluation.primary_transport_matrix import (
    build_primary_transport_matrix,
)


class PrimaryTransportMatrixTests(unittest.TestCase):
    def test_classifies_primary_scenarios_without_promoting_read_only_to_write(self):
        matrix = build_primary_transport_matrix(
            (
                _case(
                    "wechat.chat.draft_reply",
                    real_probe_kind="wechat-uia-win32-read-only-locator",
                    details={
                        "matching_window_count": 1,
                        "background_screenshot_focus_stable": True,
                        "background_screenshot_success_count": 1,
                        "background_send_verified": False,
                        "wechat_native_bridge_ready": False,
                        "wechat_native_bridge_dry_run_decision": "wechat_native_bridge_url_missing",
                        "uia_semantic_action_ready": False,
                        "computer_use_read_only_ready": True,
                        "computer_use_probe": {
                            "ready": True,
                            "native_pipe_ready": True,
                            "window_state_ready": True,
                            "background_snapshot_ready": True,
                            "input_actions_activate_window": True,
                            "control_attempts": 0,
                            "window_input_attempts": 0,
                            "computer_use_attempts": 1,
                        },
                    },
                ),
                _case(
                    "browser.research.collect_sources",
                    real_probe_kind="owned-browser-devtools-read-page",
                    details={"target_match_ok": True, "action": "read_page"},
                    owned_app_launch_attempts=1,
                ),
                _case(
                    "files.search.find_candidate",
                    real_probe_kind="owned-filesystem-temp-index",
                    details={"candidate_count": 2},
                    owned_filesystem_scan_attempts=1,
                ),
                _case(
                    "word.document.create_background",
                    real_probe_kind="office-word-com-owned-document-background",
                    details={
                        "decision": "word_background_probe_verified",
                        "save_verified": True,
                        "readback_verified": True,
                        "office_com_attempts": 1,
                        "window_input_attempts": 0,
                        "foreground_focus_stable": True,
                        "foreground_no_steal_verified": True,
                        "foreground_change_classification": "stable",
                    },
                ),
                _case(
                    "codex.project.submit_task_draft",
                    real_probe_kind="ide-bridge-capabilities-read-only",
                    details={
                        "ok_bridge_url": "http://127.0.0.1:8787",
                        "reports": [
                            {
                                "ok": True,
                                "bridge_url": "http://127.0.0.1:8787",
                                "commands": [
                                    "openwukong.readState",
                                    "openwukong.sendMessage",
                                ],
                            }
                        ],
                    },
                ),
            )
        ).to_dict()

        self.assertEqual(matrix["mode"], "primary-scenario-transport-matrix")
        self.assertEqual(matrix["safety_mode"], "plan_only")
        self.assertFalse(matrix["control_allowed"])
        self.assertEqual(matrix["control_attempts"], 0)
        self.assertFalse(matrix["goal_complete"])

        entries = {entry["scenario_id"]: entry for entry in matrix["scenarios"]}
        wechat = entries["wechat.chat.draft_reply"]
        self.assertEqual(wechat["selected_transport"], "wechat-read-only-locator")
        self.assertEqual(wechat["capability_level"], "background-read-only")
        self.assertTrue(wechat["can_execute_without_focus"])
        self.assertFalse(wechat["can_write_without_focus"])
        self.assertEqual(
            wechat["blocking_reason"],
            "wechat_native_bridge_required_for_background_send",
        )
        self.assertIn("computer-use-window2", wechat["fallback_transports"])
        self.assertIn("computer_use_input_activates_window", wechat["risk_flags"])

        self.assertEqual(
            entries["browser.research.collect_sources"]["selected_transport"],
            "browser-devtools-owned",
        )
        self.assertEqual(
            entries["files.search.find_candidate"]["selected_transport"],
            "owned-filesystem-index",
        )
        word = entries["word.document.create_background"]
        self.assertEqual(word["selected_transport"], "office-word-com")
        self.assertTrue(word["can_write_without_focus"])
        self.assertTrue(word["evidence"]["foreground_no_steal_verified"])
        self.assertEqual(word["evidence"]["foreground_change_classification"], "stable")

        codex = entries["codex.project.submit_task_draft"]
        self.assertEqual(codex["selected_transport"], "ide-bridge-capabilities-read-only")
        self.assertEqual(codex["capability_level"], "background-read-only")
        self.assertFalse(codex["can_write_without_focus"])
        self.assertEqual(codex["blocking_reason"], "ide_task_submit_not_verified")

        self.assertEqual(matrix["summary"]["scenario_count"], 5)
        self.assertEqual(matrix["summary"]["background_execute_ready_cases"], 5)
        self.assertEqual(matrix["summary"]["background_write_ready_cases"], 1)
        self.assertEqual(matrix["summary"]["background_read_only_cases"], 2)
        self.assertEqual(matrix["summary"]["write_blocked_cases"], 2)
        self.assertEqual(
            matrix["summary"]["selected_transport_counts"]["office-word-com"],
            1,
        )

    def test_failed_or_unavailable_case_is_blocked(self):
        matrix = build_primary_transport_matrix(
            (
                _case(
                    "wechat.chat.draft_reply",
                    status="unavailable",
                    real_verified=False,
                    real_probe_kind="wechat-uia-win32-read-only-locator",
                    details={
                        "matching_window_count": 0,
                        "wechat_native_bridge_ready": False,
                        "wechat_native_bridge_dry_run_decision": "wechat_native_bridge_url_missing",
                    },
                ),
            )
        ).to_dict()

        entry = matrix["scenarios"][0]
        self.assertEqual(entry["capability_level"], "blocked")
        self.assertFalse(entry["can_execute_without_focus"])
        self.assertFalse(entry["can_write_without_focus"])
        self.assertEqual(entry["blocking_reason"], "wechat_window_unavailable")
        self.assertEqual(matrix["summary"]["blocked_cases"], 1)

    def test_word_foreground_steal_blocks_background_write(self):
        matrix = build_primary_transport_matrix(
            (
                _case(
                    "word.document.create_background",
                    real_probe_kind="office-word-com-owned-document-background",
                    details={
                        "decision": "word_foreground_stolen",
                        "save_verified": True,
                        "readback_verified": True,
                        "office_com_attempts": 1,
                        "window_input_attempts": 0,
                        "foreground_focus_stable": False,
                        "foreground_no_steal_verified": False,
                        "foreground_change_classification": "changed_to_word_surface",
                    },
                ),
            )
        ).to_dict()

        entry = matrix["scenarios"][0]
        self.assertEqual(entry["capability_level"], "blocked")
        self.assertFalse(entry["can_write_without_focus"])
        self.assertEqual(entry["blocking_reason"], "office_word_com_not_verified")
        self.assertIn("foreground_focus_unstable", entry["risk_flags"])


def _case(
    scenario_id,
    *,
    status="verified",
    real_verified=True,
    real_probe_kind="",
    details=None,
    owned_app_launch_attempts=0,
    owned_filesystem_scan_attempts=0,
):
    return {
        "scenario_id": scenario_id,
        "case_id": scenario_id.replace(".", "_"),
        "status": status,
        "passed": True,
        "real_verified": real_verified,
        "real_probe_kind": real_probe_kind,
        "control_attempts": 0,
        "send_attempts": 0,
        "submit_attempts": 0,
        "start_agent_attempts": 0,
        "window_input_attempts": 0,
        "owned_app_launch_attempts": owned_app_launch_attempts,
        "owned_filesystem_scan_attempts": owned_filesystem_scan_attempts,
        "details": dict(details or {}),
    }


if __name__ == "__main__":
    unittest.main()
