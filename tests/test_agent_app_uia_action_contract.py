import unittest

from openwukong.control.agent_app_uia_action import (
    AgentAppUiaSemanticActionDryRunAdapter,
    AgentAppUiaSemanticActionSenderAdapter,
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


if __name__ == "__main__":
    unittest.main()
