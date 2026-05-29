import unittest

from openwukong.control.agent_app_uia_action import (
    AgentAppUiaSemanticActionDryRunAdapter,
    AgentAppUiaSemanticDraftWriterAdapter,
    AgentAppUiaSemanticActionSenderAdapter,
    AgentAppUiaSemanticDraftDryRunAdapter,
    build_agent_app_uia_semantic_action_request,
)


class AgentAppUiaActionContractTests(unittest.TestCase):
    def test_ready_probe_builds_semantic_action_contract_without_attempts(self):
        request = build_agent_app_uia_semantic_action_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="uia-contract",
            message="Summarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=_ready_uia_probe(),
        )

        report = AgentAppUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_dry_run_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 0)
        self.assertEqual(data["uia_invoke_attempts"], 0)
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["uia_value_pattern_ready"])
        self.assertTrue(data["request"]["uia_invoke_pattern_ready"])
        self.assertEqual(data["request"]["target"]["hwnd"], 138024)
        self.assertEqual(data["request"]["composer"]["name"], "Write your prompt to Claude")
        self.assertEqual(data["request"]["submit_control"]["name"], "Send")

    def test_missing_invoke_submit_control_keeps_contract_gated(self):
        probe = _ready_uia_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "submit_candidate_count": 0,
            "submit_candidates": [],
        }
        request = build_agent_app_uia_semantic_action_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="uia-contract",
            message="Summarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_invoke_pattern_not_ready")
        self.assertEqual(data["control_attempts"], 0)
        self.assertFalse(data["request"]["uia_invoke_pattern_ready"])

    def test_cursor_candidates_select_agent_chat_composer_and_reject_non_send_invoke(self):
        request = build_agent_app_uia_semantic_action_request(
            agent="cursor",
            agent_id="cursor",
            project_name="PaoPaoHeZi",
            task_name="",
            message="OPENWUKONG_UIA_DRAFT_PROBE",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_cursor_probe_with_editor_filter_and_chat_candidates(),
        )

        send_dry_run = AgentAppUiaSemanticActionDryRunAdapter().prepare(request).to_dict()
        draft_dry_run = AgentAppUiaSemanticDraftDryRunAdapter().prepare(request).to_dict()

        self.assertEqual(
            send_dry_run["decision"],
            "uia_semantic_action_invoke_pattern_not_ready",
        )
        self.assertFalse(send_dry_run["request"]["uia_invoke_pattern_ready"])
        self.assertTrue(draft_dry_run["ok"])
        self.assertEqual(
            draft_dry_run["decision"],
            "uia_semantic_action_draft_dry_run_ready",
        )
        self.assertEqual(
            draft_dry_run["request"]["composer"]["class_name"],
            "aislash-editor-input",
        )

    def test_target_visible_without_value_pattern_reports_value_pattern_not_ready(self):
        probe = _ready_uia_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": True,
            "semantic_composer_count": 0,
            "composer_candidates": [],
            "submit_candidate_count": 1,
        }
        request = build_agent_app_uia_semantic_action_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="",
            message="Create a new task.",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppUiaSemanticActionDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertTrue(data["request"]["target_ready"])
        self.assertFalse(data["request"]["uia_value_pattern_ready"])
        self.assertEqual(data["decision"], "uia_semantic_action_value_pattern_not_ready")
        self.assertEqual(data["control_attempts"], 0)

    def test_sender_sets_value_invokes_submit_and_accepts_marker_without_window_input(self):
        operator_calls = []

        class FakeOperator:
            def execute(self, request):
                operator_calls.append(request)
                return {
                    "composer_found": True,
                    "value_set": True,
                    "post_value": request.message,
                    "submit_found": True,
                    "invoke_attempted": True,
                    "invoke_verified": True,
                    "readbackText": "OPENWUKONG_UIA_ACCEPTANCE: PASS",
                }

        request = build_agent_app_uia_semantic_action_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="uia-contract",
            message="Send through UIA.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=_ready_uia_probe(),
            required_markers=("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
        )

        report = AgentAppUiaSemanticActionSenderAdapter(
            operator=FakeOperator(),
            foreground_hwnd_provider=lambda: 100,
        ).send(request)
        data = report.to_dict()

        self.assertEqual(len(operator_calls), 1)
        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_send_accepted")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 1)
        self.assertTrue(data["foreground_focus_stable"])
        self.assertEqual(data["missing_required_markers"], [])
        self.assertEqual(
            data["request"]["payload"]["required_markers"],
            ["OPENWUKONG_UIA_ACCEPTANCE: PASS"],
        )

    def test_sender_does_not_call_operator_when_dry_run_is_not_ready(self):
        operator_calls = []
        probe = _ready_uia_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "submit_candidate_count": 0,
            "submit_candidates": [],
        }
        request = build_agent_app_uia_semantic_action_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="uia-contract",
            message="Send through UIA.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
            required_markers=("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
        )

        class FakeOperator:
            def execute(self, request):
                operator_calls.append(request)
                return {}

        report = AgentAppUiaSemanticActionSenderAdapter(operator=FakeOperator()).send(request)
        data = report.to_dict()

        self.assertEqual(operator_calls, [])
        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_request_not_ready")
        self.assertEqual(data["uia_value_set_attempts"], 0)
        self.assertEqual(data["uia_invoke_attempts"], 0)

    def test_sender_rejects_foreground_change_even_after_semantic_operations(self):
        foreground_values = iter((100, 200))

        class FakeOperator:
            def execute(self, request):
                return {
                    "composer_found": True,
                    "value_set": True,
                    "post_value": request.message,
                    "submit_found": True,
                    "invoke_attempted": True,
                    "invoke_verified": True,
                    "readbackText": "OPENWUKONG_UIA_ACCEPTANCE: PASS",
                }

        request = build_agent_app_uia_semantic_action_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="uia-contract",
            message="Send through UIA.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=_ready_uia_probe(),
            required_markers=("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
        )

        report = AgentAppUiaSemanticActionSenderAdapter(
            operator=FakeOperator(),
            foreground_hwnd_provider=lambda: next(foreground_values),
        ).send(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_foreground_changed")
        self.assertFalse(data["foreground_focus_stable"])
        self.assertEqual(data["window_input_attempts"], 0)

    def test_draft_writer_sets_value_cleans_up_and_never_invokes_submit(self):
        operator_calls = []

        class FakeOperator:
            def draft(self, request, *, cleanup, restore_value):
                operator_calls.append((request, cleanup, restore_value))
                return {
                    "composer_found": True,
                    "original_value": restore_value,
                    "value_set_attempted": True,
                    "value_set": True,
                    "draft_value": request.message,
                    "cleanup_attempted": True,
                    "cleanup_value_set": True,
                    "post_cleanup_value": restore_value,
                    "readbackText": request.message,
                }

        request = build_agent_app_uia_semantic_action_request(
            agent="cursor",
            agent_id="cursor",
            project_name="PaoPaoHeZi",
            task_name="",
            message="OPENWUKONG_UIA_DRAFT_PROBE",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_cursor_probe_with_editor_filter_and_chat_candidates(),
        )

        report = AgentAppUiaSemanticDraftWriterAdapter(
            operator=FakeOperator(),
            foreground_hwnd_provider=lambda: 500,
        ).draft(request, cleanup=True, restore_value="")
        data = report.to_dict()

        self.assertEqual(len(operator_calls), 1)
        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "uia_semantic_action_draft_verified")
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 0)
        self.assertEqual(data["cleanup_value_set_attempts"], 1)
        self.assertTrue(data["cleanup_verified"])
        self.assertTrue(data["foreground_focus_stable"])


def _ready_uia_probe():
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_not_exposed",
        "control_attempts": 0,
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "semantic_composer_count": 1,
            "submit_candidate_count": 1,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "claude.exe",
                    "pid": 77064,
                    "window_title": "Claude",
                    "hwnd": 138024,
                }
            ],
            "composer_candidates": [
                {
                    "control_type": "Edit",
                    "name": "Write your prompt to Claude",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Text", "Value"],
                    "semantic_composer": True,
                    "rect": [1321, 1155, 2385, 1233],
                }
            ],
            "submit_candidates": [
                {
                    "control_type": "Button",
                    "name": "Send",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Invoke"],
                    "rect": [2390, 1155, 2440, 1233],
                }
            ],
        },
    }


def _cursor_probe_with_editor_filter_and_chat_candidates():
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_not_exposed",
        "control_attempts": 0,
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "semantic_composer_count": 3,
            "submit_candidate_count": 2,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "Cursor.exe",
                    "pid": 99496,
                    "window_title": "config - PaoPaoHeZi - Cursor",
                    "hwnd": 70038,
                }
            ],
            "composer_candidates": [
                {
                    "control_type": "Edit",
                    "name": "The editor is not accessible at this time. To enable screen reader optimized mode, use Shift+Alt+F1",
                    "class_name": "inputarea monaco-mouse-cursor-text",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Text", "Value"],
                    "semantic_composer": True,
                    "rect": [799, 1362, 803, 1366],
                },
                {
                    "control_type": "Edit",
                    "name": "Filter Problems",
                    "class_name": "input empty",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Text", "Value"],
                    "semantic_composer": True,
                    "rect": [798, 1272, 1546, 1343],
                },
                {
                    "control_type": "Edit",
                    "name": "",
                    "class_name": "aislash-editor-input",
                    "value_preview": "\n",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Text", "Value"],
                    "semantic_composer": True,
                    "rect": [1687, 230, 2481, 291],
                },
            ],
            "submit_candidates": [
                {
                    "control_type": "Button",
                    "name": "\u4ece\u6b64\u5904\u5f00\u59cb\u5206\u652f",
                    "class_name": "border-token-border user-select-none no-drag cursor-interaction flex items-center gap-1 border white",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Invoke"],
                },
                {
                    "control_type": "MenuItem",
                    "name": "Go",
                    "class_name": "menubar-menu-button",
                    "is_enabled": True,
                    "visible": True,
                    "patterns": ["Invoke"],
                },
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
