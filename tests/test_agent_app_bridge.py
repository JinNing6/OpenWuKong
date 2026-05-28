import unittest

from openwukong.control.agent_app_bridge import (
    AgentAppBridgeDryRunAdapter,
    build_agent_app_bridge_request,
)


class AgentAppBridgeTests(unittest.TestCase):
    def test_ready_native_probe_builds_dry_run_bridge_payload_without_send_attempts(self):
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={
                "transport_id": "claude-desktop-shell",
                "route_id": "claude-desktop-connector-required",
                "transport": "desktop-shell-native-bridge-or-foreground",
                "path": "C:/Program Files/WindowsApps/Claude/app/claude.exe",
                "pid": 11140,
            },
            app_surface_probe=_ready_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("DO_NOT_SEND",),
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_dry_run_ready")
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["request"]["ready"])
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])
        self.assertEqual(data["request"]["target"]["hwnd"], 138024)
        self.assertEqual(data["request"]["endpoint"]["debugger_url"], "http://127.0.0.1:9333")
        self.assertEqual(data["request"]["payload"]["message"], "Summarize the active task.")
        self.assertEqual(
            data["request"]["payload"]["required_markers"],
            ["OPENWUKONG_ACCEPTANCE: PASS"],
        )

    def test_dry_run_reports_native_endpoint_missing_without_falling_back_to_foreground(self):
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe={
                **_ready_probe(),
                "decision": "agent_native_connector_not_exposed",
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "endpoints": [],
            },
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_native_connector_not_ready")
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["request"]["target_ready"])
        self.assertFalse(data["request"]["native_endpoint_ready"])

    def test_dry_run_reports_target_missing_even_when_endpoint_exists(self):
        probe = _ready_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "project_match": {"decision": "missing"},
            "task_match": {"decision": "missing"},
        }
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="missing-project",
            task_name="missing-task",
            message="Summarize the active task.",
            composed_message="Project: missing-project\nTask: missing-task",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "app_bridge_target_not_ready")
        self.assertEqual(report.bridge_send_attempts, 0)


def _ready_probe():
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_ready",
        "control_attempts": 0,
        "endpoint_count": 1,
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "debugger_url": "http://127.0.0.1:9333",
                "ready": True,
                "targets": [
                    {
                        "target_id": "page-1",
                        "title": "Claude",
                        "url": "app://claude/index.html",
                        "ready": True,
                    }
                ],
            }
        ],
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "composer_candidate_count": 1,
            "semantic_composer_count": 1,
            "background_screenshot_count": 1,
            "background_screenshot_success_count": 1,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "claude.exe",
                    "pid": 77064,
                    "window_title": "Claude",
                    "hwnd": 138024,
                }
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
