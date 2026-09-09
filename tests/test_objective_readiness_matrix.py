import unittest

from openwukong.evaluation.objective_readiness_matrix import (
    build_objective_readiness_matrix,
)


class ObjectiveReadinessMatrixTests(unittest.TestCase):
    def test_combines_requirements_with_primary_agent_app_and_cli_transport_evidence(self):
        matrix = build_objective_readiness_matrix(
            primary_report={
                "transport_matrix": {
                    "scenarios": [
                        {
                            "scenario_id": "wechat.chat.draft_reply",
                            "selected_transport": "wechat-read-only-locator",
                            "capability_level": "background-read-only",
                            "can_execute_without_focus": True,
                            "can_write_without_focus": False,
                            "blocking_reason": "wechat_native_bridge_required_for_background_send",
                        },
                        {
                            "scenario_id": "word.document.create_background",
                            "selected_transport": "office-word-com",
                            "capability_level": "background-native",
                            "can_execute_without_focus": True,
                            "can_write_without_focus": True,
                        },
                        {
                            "scenario_id": "browser.research.collect_sources",
                            "selected_transport": "browser-devtools-owned",
                            "capability_level": "background-native",
                            "can_execute_without_focus": True,
                            "can_write_without_focus": False,
                        },
                    ]
                }
            },
            agent_app_report={
                "cases": [
                    {
                        "agent": "codex app",
                        "status": "gated_native_endpoint_missing",
                        "transport_matrix": {
                            "send_ready": False,
                            "best_available_transport": {
                                "transport_id": "computer-use-window2",
                                "capability_level": "background-read-only",
                            },
                            "selected_send_transport": {},
                            "summary": {"background_read_only": 1},
                        },
                    },
                    {
                        "agent": "cursor",
                        "status": "app_bridge_send_accepted",
                        "app_bridge_send_verified": True,
                        "transport_matrix": {
                            "send_ready": True,
                            "selected_send_transport": {
                                "transport_id": "app-devtools-page-target",
                                "capability_level": "background-native",
                            },
                            "summary": {"background_read_only": 0},
                        },
                    },
                ]
            },
            agent_cli_report={
                "cases": [
                    {
                        "agent": "codex",
                        "status": "verified",
                        "real_verified": True,
                        "selected_transport": "codex-cli-managed-terminal",
                    },
                    {
                        "agent": "claude",
                        "status": "cli_auth_required",
                        "real_verified": False,
                    },
                ]
            },
            requirements=(
                _requirement(
                    "wechat_background_send",
                    "wechat",
                    "background_semantic_send",
                    "gated",
                    "wechat_native_bridge_url_missing",
                ),
                _requirement(
                    "word_background_document",
                    "word",
                    "hidden_com_create_save_readback",
                    "verified",
                    "",
                ),
                _requirement(
                    "browser_background_research",
                    "browser",
                    "owned_cdp_read_page",
                    "verified",
                    "",
                ),
                _requirement(
                    "codex_cli_background_task",
                    "codex",
                    "background_cli_task",
                    "verified",
                    "",
                ),
                _requirement(
                    "claude_cli_background_task",
                    "claude",
                    "background_cli_task",
                    "auth_required",
                    "local_cli_not_logged_in",
                ),
                _requirement(
                    "codex_app_background_chat",
                    "codex app",
                    "background_app_chat",
                    "gated",
                    "gated_native_endpoint_missing",
                ),
                _requirement(
                    "cursor_background_chat",
                    "cursor",
                    "background_app_chat",
                    "verified",
                    "",
                ),
            ),
            safe_run_ok=True,
        ).to_dict()

        self.assertEqual(matrix["mode"], "objective-readiness-matrix")
        self.assertEqual(matrix["safety_mode"], "plan_only")
        self.assertFalse(matrix["control_allowed"])
        self.assertEqual(matrix["control_attempts"], 0)
        self.assertFalse(matrix["goal_complete"])

        entries = {entry["requirement_id"]: entry for entry in matrix["requirements"]}
        self.assertEqual(
            entries["wechat_background_send"]["selected_transport"],
            "wechat-read-only-locator",
        )
        self.assertTrue(entries["wechat_background_send"]["can_execute_without_focus"])
        self.assertFalse(entries["wechat_background_send"]["can_write_without_focus"])
        self.assertEqual(
            entries["codex_app_background_chat"]["selected_transport"],
            "computer-use-window2",
        )
        self.assertEqual(
            entries["cursor_background_chat"]["selected_transport"],
            "app-devtools-page-target",
        )
        self.assertTrue(entries["cursor_background_chat"]["satisfied"])

        self.assertEqual(matrix["summary"]["requirement_count"], 7)
        self.assertEqual(matrix["summary"]["satisfied_count"], 4)
        self.assertEqual(matrix["summary"]["gated_count"], 2)
        self.assertEqual(matrix["summary"]["auth_required_count"], 1)
        self.assertEqual(matrix["summary"]["background_execute_ready_count"], 6)
        self.assertEqual(matrix["summary"]["background_write_ready_count"], 3)
        self.assertEqual(
            matrix["summary"]["unsatisfied_requirements"],
            [
                "wechat_background_send",
                "claude_cli_background_task",
                "codex_app_background_chat",
            ],
        )
        self.assertEqual(matrix["summary"]["closure_action_count"], 3)
        self.assertEqual(matrix["summary"]["safe_closure_probe_count"], 2)
        self.assertEqual(matrix["summary"]["external_state_blocked_closure_count"], 1)

        closure = matrix["closure_plan"]
        self.assertEqual(closure["mode"], "objective-closure-plan")
        self.assertEqual(closure["safety_mode"], "plan_only")
        self.assertEqual(closure["control_attempts"], 0)
        self.assertEqual(closure["window_input_attempts"], 0)
        self.assertEqual(closure["action_count"], 3)
        actions = {entry["requirement_id"]: entry for entry in closure["actions"]}
        self.assertEqual(
            actions["wechat_background_send"]["action_id"],
            "attach_wechat_native_bridge_or_verified_uia_send",
        )
        self.assertTrue(actions["wechat_background_send"]["safe_to_run_now"])
        self.assertIn(
            "external_send_without_readback_marker",
            actions["wechat_background_send"]["forbidden_actions"],
        )
        self.assertEqual(
            actions["claude_cli_background_task"]["action_kind"],
            "auth_required",
        )
        self.assertFalse(actions["claude_cli_background_task"]["safe_to_run_now"])
        self.assertTrue(
            actions["claude_cli_background_task"]["blocked_by_external_state"]
        )
        self.assertEqual(
            actions["codex_app_background_chat"]["preferred_transport"],
            "codex-app-server-ws-or-agent-native-bridge",
        )
        self.assertIn(
            "codex_turn_start_when_endpoint_is_desktop_msix",
            actions["codex_app_background_chat"]["forbidden_actions"],
        )

    def test_closure_plan_protects_active_cursor_bridge_updates(self):
        matrix = build_objective_readiness_matrix(
            agent_app_report={
                "cases": [
                    {
                        "agent": "cursor",
                        "status": "gated",
                        "transport_matrix": {
                            "send_ready": False,
                            "best_available_transport": {},
                            "selected_send_transport": {},
                        },
                    }
                ]
            },
            requirements=(
                _requirement(
                    "cursor_background_chat",
                    "cursor",
                    "background_app_chat",
                    "gated",
                    "active_cursor_desktop_protected",
                ),
            ),
            safe_run_ok=True,
        ).to_dict()

        action = matrix["closure_plan"]["actions"][0]
        self.assertEqual(
            action["action_id"],
            "update_or_attach_cursor_ide_bridge_without_touching_active_profile",
        )
        self.assertEqual(action["safe_probe_runner"], "openwukong.evaluation.ide_extension_sync")
        self.assertTrue(action["safe_to_run_now"])
        self.assertIn(
            "patch_active_cursor_profile_without_override",
            action["forbidden_actions"],
        )
        self.assertIn(
            "probe_fixed_8787_by_default",
            action["forbidden_actions"],
        )

    def test_closure_plan_distinguishes_cli_opt_in_from_auth_required(self):
        matrix = build_objective_readiness_matrix(
            agent_cli_report={
                "cases": [
                    {
                        "agent": "claude",
                        "status": "skipped_requires_cli_execution_opt_in",
                        "real_verified": False,
                    },
                ]
            },
            requirements=(
                _requirement(
                    "claude_cli_background_task",
                    "claude",
                    "background_cli_task",
                    "gated",
                    "skipped_requires_cli_execution_opt_in",
                ),
            ),
            safe_run_ok=True,
        ).to_dict()

        action = matrix["closure_plan"]["actions"][0]
        self.assertEqual(
            action["action_id"],
            "rerun_claude_cli_no_loss_with_execution_opt_in",
        )
        self.assertEqual(action["action_kind"], "managed_cli_opt_in")
        self.assertTrue(action["safe_to_run_now"])
        self.assertFalse(action["blocked_by_external_state"])


def _requirement(requirement_id, surface, capability, status, blocking_reason):
    return {
        "requirement_id": requirement_id,
        "surface": surface,
        "capability": capability,
        "status": status,
        "satisfied": status == "verified",
        "source_runner": "fake",
        "blocking_reason": blocking_reason,
        "evidence": {},
    }


if __name__ == "__main__":
    unittest.main()
