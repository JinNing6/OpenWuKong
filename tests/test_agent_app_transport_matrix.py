import unittest

from openwukong.control.agent_app_transport_matrix import (
    build_agent_app_transport_matrix,
    summarize_agent_app_transport_matrices,
)


class AgentAppTransportMatrixTests(unittest.TestCase):
    def test_browser_level_devtools_is_read_only_not_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "cursor",
                "agent_id": "cursor",
                "project_name": "openwukong",
                "task_name": "cursor-chat",
                "ready_endpoint_count": 0,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:19557",
                        "ready": False,
                        "target_count": 0,
                        "version": {
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1"
                        },
                        "targets": [],
                        "error": "devtools_targets_not_ready",
                    }
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertFalse(matrix["draft_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "app-devtools-browser-target")
        self.assertTrue(candidate["ready"])
        self.assertEqual(candidate["capability_level"], "background-read-only")
        self.assertEqual(candidate["operation_scope"], "discovery-only")
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "page_target_missing")
        self.assertEqual(matrix["summary"]["background_read_only"], 1)
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_agent_native_bridge_is_selected_before_page_target_and_uia(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "project_name": "openwukong",
                "task_name": "claude-task",
                "ready_endpoint_count": 2,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:9333",
                        "ready": True,
                        "target_count": 1,
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "title": "Claude",
                                "url": "app://claude",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-1",
                                "ready": True,
                            }
                        ],
                    },
                    {
                        "endpoint_type": "agent_native_bridge",
                        "bridge_url": "http://127.0.0.1:18888",
                        "ready": True,
                        "preferred_chat_adapter": "claude",
                        "send_command_id": "agent_app_conversation.native_bridge_send_message",
                        "metadata": {"surface_ok": True, "app_binding_ok": True},
                    },
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertTrue(matrix["send_ready"])
        self.assertTrue(matrix["draft_ready"])
        self.assertEqual(
            matrix["selected_send_transport"]["transport_id"],
            "agent-native-bridge",
        )
        self.assertEqual(
            matrix["selected_send_transport"]["transport_channel"],
            "agent_native_bridge",
        )
        self.assertFalse(
            _candidate(matrix, "app-devtools-page-target")["can_send_without_focus"]
        )
        self.assertEqual(
            _candidate(matrix, "app-devtools-page-target")["blocking_reason"],
            "composer_probe_required",
        )
        self.assertTrue(
            _candidate(matrix, "uia-semantic-draft")["can_draft_without_focus"]
        )

    def test_codex_app_server_ws_is_readiness_not_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "codex app",
                "agent_id": "codex",
                "project_name": "openwukong",
                "task_name": "desktop-message",
                "ready_endpoint_count": 1,
                "endpoints": [
                    {
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "send_contract_ready": False,
                            "observed_thread_count": 1,
                            "probe_decision": "codex_app_server_ws_ready",
                        },
                    }
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertFalse(matrix["draft_ready"])
        candidate = _candidate(matrix, "codex-app-server-ws")
        self.assertTrue(candidate["ready"])
        self.assertEqual(candidate["capability_level"], "background-native")
        self.assertEqual(candidate["operation_scope"], "thread-readiness")
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertFalse(candidate["can_draft_without_focus"])
        self.assertIn("turn_send_contract_required", candidate["verification_requirements"])
        self.assertEqual(candidate["evidence"]["observed_thread_count"], 1)
        self.assertEqual(
            matrix["best_available_transport"]["transport_id"],
            "codex-app-server-ws",
        )
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_codex_app_server_ws_becomes_send_ready_after_strict_turn_readback(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "codex app",
                "agent_id": "codex",
                "project_name": "openwukong",
                "task_name": "desktop-message",
                "ready_endpoint_count": 1,
                "endpoints": [
                    {
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list", "turn/start"],
                        "metadata": {
                            "thread_api_ready": True,
                            "send_contract_ready": False,
                            "owned_loopback_app_server": True,
                            "surface_kind": "owned_ephemeral_app_server",
                            "observed_thread_count": 1,
                            "probe_decision": "codex_app_server_ws_ready",
                        },
                    }
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            },
            codex_app_server_turn_start_report={
                "ok": True,
                "decision": "codex_app_server_turn_start_verified",
                "assistant_readback_text": "OPENWUKONG_ACCEPTANCE: PASS",
                "required_markers": ["OPENWUKONG_ACCEPTANCE: PASS"],
                "missing_required_markers": [],
                "seen_forbidden_markers": [],
                "turn_completed": True,
                "turn_status": "completed",
                "foreground_no_steal_verified": True,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "app_server_turn_start_attempts": 1,
            },
        ).to_dict()

        self.assertTrue(matrix["send_ready"])
        candidate = _candidate(matrix, "codex-app-server-ws")
        self.assertTrue(candidate["ready"])
        self.assertTrue(candidate["can_send_without_focus"])
        self.assertEqual(candidate["operation_scope"], "send-readback")
        self.assertEqual(candidate["blocking_reason"], "")
        self.assertEqual(candidate["evidence"]["turn_start_decision"], "codex_app_server_turn_start_verified")
        self.assertTrue(candidate["evidence"]["strict_assistant_readback_verified"])
        self.assertEqual(
            matrix["selected_send_transport"]["transport_id"],
            "codex-app-server-ws",
        )
        self.assertEqual(matrix["summary"]["background_send_ready"], 1)

    def test_page_target_cdp_without_verified_target_context_is_not_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "cursor",
                "agent_id": "cursor",
                "project_name": "openwukong",
                "task_name": "major-real-no-loss",
                "ready_endpoint_count": 1,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:19557",
                        "ready": True,
                        "target_count": 1,
                        "version": {
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1"
                        },
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "title": "Cursor",
                                "url": "app://cursor/workbench.html",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/page-1",
                                "ready": True,
                            }
                        ],
                    }
                ],
                "app_uia_probe": {
                    "target_matched": False,
                    "semantic_composer_count": 4,
                    "submit_candidate_count": 4,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "app-devtools-page-target")
        self.assertTrue(candidate["ready"])
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "target_context_not_verified")
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_page_target_cdp_requires_composer_probe_before_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            _cursor_devtools_probe(target_title="openwukong - Cursor")
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "app-devtools-page-target")
        self.assertTrue(candidate["ready"])
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "composer_probe_required")
        self.assertIn("composer_probe_required", candidate["risk_flags"])
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_page_target_cdp_with_ready_composer_is_background_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            _cursor_devtools_probe(target_title="openwukong - Cursor"),
            app_bridge_composer_probe={
                "ok": True,
                "decision": "app_bridge_composer_ready",
                "action_result": {
                    "selectedComposer": {
                        "productComposerContract": (
                            "cursor-agent-chat-aislash-editor-input"
                        )
                    }
                },
            },
        ).to_dict()

        self.assertTrue(matrix["send_ready"])
        candidate = _candidate(matrix, "app-devtools-page-target")
        self.assertTrue(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "")
        self.assertEqual(
            candidate["evidence"]["composer_probe_decision"],
            "app_bridge_composer_ready",
        )
        self.assertEqual(
            candidate["evidence"]["product_composer_contract"],
            "cursor-agent-chat-aislash-editor-input",
        )
        self.assertEqual(
            matrix["selected_send_transport"]["transport_id"],
            "app-devtools-page-target",
        )
        self.assertEqual(matrix["summary"]["background_send_ready"], 1)

    def test_page_target_cdp_records_verified_app_bridge_send(self):
        matrix = build_agent_app_transport_matrix(
            _cursor_devtools_probe(target_title="openwukong - Cursor"),
            app_bridge_send_report={
                "ok": True,
                "decision": "app_bridge_send_accepted",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "action_result": {
                    "productComposerContract": (
                        "cursor-agent-chat-aislash-editor-input"
                    ),
                    "sendButtonContract": "cursor-arrow-up-two-submit",
                },
            },
        ).to_dict()

        candidate = _candidate(matrix, "app-devtools-page-target")
        self.assertTrue(matrix["send_ready"])
        self.assertTrue(candidate["evidence"]["app_bridge_send_verified"])
        self.assertEqual(
            candidate["evidence"]["app_bridge_send_decision"],
            "app_bridge_send_accepted",
        )
        self.assertEqual(
            candidate["evidence"]["send_button_contract"],
            "cursor-arrow-up-two-submit",
        )

    def test_ready_computer_use_is_read_only_not_background_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "project_name": "openwukong",
                "task_name": "desktop-chat",
                "endpoints": [],
                "app_uia_probe": {
                    "target_matched": True,
                    "matched_window_count": 1,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
                "computer_use_probe": {
                    "ready": True,
                    "native_pipe_ready": True,
                    "window_state_ready": True,
                    "background_snapshot_ready": True,
                    "input_actions_activate_window": True,
                    "computer_use_attempts": 0,
                    "window_input_attempts": 0,
                    "control_attempts": 0,
                    "observed_window_count": 1,
                    "screenshot_count": 1,
                    "accessibility_tree_available": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertFalse(matrix["draft_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "computer-use-window2")
        self.assertTrue(candidate["ready"])
        self.assertEqual(candidate["capability_level"], "background-read-only")
        self.assertEqual(candidate["operation_scope"], "inspect-snapshot-only")
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertFalse(candidate["can_draft_without_focus"])
        self.assertEqual(
            candidate["blocking_reason"],
            "computer_use_input_requires_foreground_activation",
        )
        self.assertIn("input_actions_activate_window", candidate["risk_flags"])
        self.assertEqual(candidate["evidence"]["computer_use_attempts"], 0)
        self.assertEqual(candidate["evidence"]["window_input_attempts"], 0)
        self.assertEqual(
            matrix["best_available_transport"]["transport_id"],
            "computer-use-window2",
        )
        self.assertEqual(matrix["summary"]["background_read_only"], 1)
        self.assertEqual(matrix["summary"]["computer_use_read_only"], 1)
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_computer_use_without_native_pipe_is_blocked_with_explicit_reason(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "codex app",
                "agent_id": "codex",
                "project_name": "openwukong",
                "task_name": "desktop-chat",
                "endpoints": [],
                "app_uia_probe": {
                    "target_matched": True,
                    "matched_window_count": 1,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
                "computer_use_probe": {
                    "ready": False,
                    "native_pipe_ready": False,
                    "decision": "native_pipe_unavailable",
                    "error": "Computer Use native pipe path is unavailable",
                    "computer_use_attempts": 0,
                    "window_input_attempts": 0,
                    "control_attempts": 0,
                },
            }
        ).to_dict()

        candidate = _candidate(matrix, "computer-use-window2")
        self.assertFalse(candidate["ready"])
        self.assertEqual(candidate["capability_level"], "blocked")
        self.assertEqual(candidate["blocking_reason"], "native_pipe_unavailable")
        self.assertIn("native_pipe_unavailable", candidate["risk_flags"])
        self.assertEqual(candidate["evidence"]["error"], "Computer Use native pipe path is unavailable")
        self.assertEqual(matrix["summary"]["computer_use_read_only"], 0)

    def test_transport_matrix_summary_counts_computer_use_read_only_cases(self):
        ready_matrix = build_agent_app_transport_matrix(
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "app_uia_probe": {"target_matched": True, "matched_window_count": 1},
                "computer_use_probe": {
                    "ready": True,
                    "native_pipe_ready": True,
                    "window_state_ready": True,
                    "input_actions_activate_window": True,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                },
            }
        ).to_dict()
        blocked_matrix = build_agent_app_transport_matrix(
            {
                "agent": "codex app",
                "agent_id": "codex",
                "app_uia_probe": {"target_matched": True, "matched_window_count": 1},
                "computer_use_probe": {
                    "ready": False,
                    "native_pipe_ready": False,
                    "decision": "native_pipe_unavailable",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                },
            }
        ).to_dict()

        summary = summarize_agent_app_transport_matrices(
            (
                {"transport_matrix": ready_matrix},
                {"transport_matrix": blocked_matrix},
            )
        )

        self.assertEqual(summary["computer_use_read_only_cases"], 1)
        self.assertEqual(
            summary["selected_send_transport_counts"],
            {"none": 2},
        )


def _candidate(matrix, transport_id):
    for item in matrix["candidates"]:
        if item["transport_id"] == transport_id:
            return item
    raise AssertionError(f"missing candidate {transport_id}: {matrix['candidates']}")


def _cursor_devtools_probe(*, target_title):
    return {
        "agent": "cursor",
        "agent_id": "cursor",
        "project_name": "openwukong",
        "task_name": "",
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "endpoint_type": "devtools",
                "debugger_url": "http://127.0.0.1:19557",
                "ready": True,
                "target_count": 1,
                "targets": [
                    {
                        "target_id": "cursor-workbench",
                        "id": "cursor-workbench",
                        "type": "page",
                        "title": target_title,
                        "url": "vscode-file://vscode-app/e:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                        "ready": True,
                    }
                ],
            }
        ],
        "app_uia_probe": {
            "target_matched": False,
            "matched_window_count": 1,
            "semantic_composer_count": 0,
            "submit_candidate_count": 0,
            "background_screenshot_focus_stable": True,
        },
    }


if __name__ == "__main__":
    unittest.main()
