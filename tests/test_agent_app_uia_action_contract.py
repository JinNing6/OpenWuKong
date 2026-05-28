import unittest

from openwukong.control.agent_app_uia_action import (
    AgentAppUiaSemanticActionDryRunAdapter,
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
