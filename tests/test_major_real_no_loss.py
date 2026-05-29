import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.major_real_no_loss import (
    run_major_scenario_real_no_loss,
)


class _FakeReport:
    def __init__(self, data):
        self._data = dict(data)

    def to_dict(self):
        return dict(self._data)


class MajorRealNoLossTests(unittest.TestCase):
    def test_runner_aggregates_main_surfaces_and_marks_unmet_background_actions(self):
        primary_calls = []
        app_calls = []
        cli_calls = []

        def _primary_runner(fixture, **kwargs):
            primary_calls.append({"fixture": fixture, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "owned_app_launch_attempts": 1,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 5,
                    "failed_cases": 0,
                    "real_verified_cases": 4,
                    "cases": [
                        {
                            "scenario_id": "wechat.chat.draft_reply",
                            "status": "verified",
                            "real_verified": True,
                            "details": {
                                "background_screenshot_focus_stable": True,
                                "uia_semantic_action_ready": False,
                                "uia_semantic_action_dry_run": {
                                    "decision": "wechat_uia_semantic_action_target_not_ready"
                                },
                            },
                        },
                        {
                            "scenario_id": "browser.research.collect_sources",
                            "status": "verified",
                            "real_verified": True,
                        },
                        {
                            "scenario_id": "files.search.find_candidate",
                            "status": "verified",
                            "real_verified": True,
                        },
                        {
                            "scenario_id": "word.document.create_background",
                            "status": "verified",
                            "real_verified": True,
                        },
                        {
                            "scenario_id": "codex.project.submit_task_draft",
                            "status": "unavailable",
                            "real_verified": False,
                        },
                    ],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_count": 3,
                    "background_screenshot_success_count": 3,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 3,
                    "failed_cases": 0,
                    "native_ready_cases": 0,
                    "gated_cases": 2,
                    "real_verified_cases": 2,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "gated_native_endpoint_missing",
                            "real_verified": True,
                            "native_ready": False,
                            "uia_semantic_action_ready": False,
                        },
                        {
                            "agent": "claude desktop",
                            "status": "unavailable",
                            "real_verified": False,
                            "native_ready": False,
                            "uia_semantic_action_ready": False,
                        },
                        {
                            "agent": "cursor",
                            "status": "gated_native_endpoint_missing",
                            "real_verified": True,
                            "native_ready": False,
                            "uia_semantic_action_ready": False,
                        },
                    ],
                }
            )

        def _agent_cli_runner(**kwargs):
            cli_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-cli-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent_command_attempts": 2,
                    "foreground_focus_stable": True,
                    "passed_cases": 2,
                    "failed_cases": 0,
                    "verified_cases": 1,
                    "cases": [
                        {
                            "agent": "codex",
                            "status": "verified",
                            "real_verified": True,
                            "foreground_focus_stable": True,
                        },
                        {
                            "agent": "claude",
                            "status": "cli_auth_required",
                            "real_verified": False,
                            "foreground_focus_stable": True,
                        },
                    ],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                allow_owned_browser_helper_launch=True,
                allow_agent_cli_execution=True,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

            output_path = Path(data["artifact_path"])
            self.assertTrue(output_path.is_file())
            artifact = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(data["mode"], "major-scenario-real-no-loss")
        self.assertEqual(data["safety_mode"], "real_no_loss")
        self.assertFalse(data["control_allowed"])
        self.assertFalse(data["goal_complete"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["agent_command_attempts"], 2)
        self.assertEqual(data["background_screenshot_count"], 4)
        self.assertEqual(data["background_screenshot_success_count"], 4)
        self.assertTrue(data["background_screenshot_focus_stable"])
        self.assertEqual(data["failed_runner_count"], 0)

        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["wechat_background_observation"]["status"], "verified")
        self.assertEqual(requirements["wechat_background_send"]["status"], "gated")
        self.assertEqual(requirements["word_background_document"]["status"], "verified")
        self.assertEqual(requirements["browser_background_research"]["status"], "verified")
        self.assertEqual(requirements["file_background_search"]["status"], "verified")
        self.assertEqual(requirements["codex_cli_background_task"]["status"], "verified")
        self.assertEqual(requirements["claude_cli_background_task"]["status"], "auth_required")
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "gated")
        self.assertEqual(requirements["claude_desktop_background_chat"]["status"], "unavailable")
        self.assertEqual(requirements["cursor_background_chat"]["status"], "gated")
        self.assertIn("wechat_background_send", data["unmet_requirements"])
        self.assertIn("claude_cli_background_task", data["unmet_requirements"])
        self.assertEqual(artifact["mode"], "major-scenario-real-no-loss")

        self.assertTrue(primary_calls[0]["kwargs"]["allow_owned_browser_helper_launch"])
        self.assertEqual(app_calls[0]["agents"], ("codex app", "claude desktop", "cursor"))
        self.assertEqual(cli_calls[0]["agents"], ("codex", "claude"))
        self.assertTrue(cli_calls[0]["allow_cli_execution"])

    def test_runner_passes_app_bridge_send_options_and_marks_app_requirement_verified(self):
        app_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 1,
                    "agent_command_attempts": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "app_bridge_send_verified_cases": 1,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "app_bridge_send_accepted",
                            "real_verified": True,
                            "native_ready": True,
                            "app_bridge_send_verified": True,
                        }
                    ],
                }
            )

        def _agent_cli_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-cli-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent_command_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("codex app",),
                cli_agents=(),
                project_name="openwukong",
                task_name="codex-app-message",
                allow_app_bridge_send=True,
                app_bridge_message="OPENWUKONG APP BRIDGE CHECK",
                app_bridge_required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
                app_bridge_forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(app_calls[0]["allow_app_bridge_send"], True)
        self.assertEqual(app_calls[0]["bridge_message"], "OPENWUKONG APP BRIDGE CHECK")
        self.assertEqual(
            app_calls[0]["required_markers"],
            ("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        self.assertEqual(
            app_calls[0]["forbidden_markers"],
            ("OPENWUKONG_ACCEPTANCE: FAIL",),
        )
        self.assertEqual(data["bridge_send_attempts"], 1)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "verified")

    def test_runner_passes_uia_semantic_options_and_marks_app_requirement_verified(self):
        app_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "uia_value_set_attempts": 1,
                    "uia_invoke_attempts": 1,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "uia_semantic_action_send_verified_cases": 1,
                    "cases": [
                        {
                            "agent": "cursor",
                            "status": "uia_semantic_action_send_accepted",
                            "real_verified": True,
                            "native_ready": False,
                            "uia_semantic_action_send_verified": True,
                        }
                    ],
                }
            )

        def _agent_cli_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-cli-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent_command_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("cursor",),
                cli_agents=(),
                project_name="openwukong",
                task_name="cursor-uia-message",
                allow_uia_semantic_action=True,
                uia_message="OPENWUKONG UIA CHECK",
                uia_required_markers=("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
                uia_forbidden_markers=("OPENWUKONG_UIA_ACCEPTANCE: FAIL",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(app_calls[0]["allow_uia_semantic_action"], True)
        self.assertEqual(app_calls[0]["uia_message"], "OPENWUKONG UIA CHECK")
        self.assertEqual(
            app_calls[0]["uia_required_markers"],
            ("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
        )
        self.assertEqual(
            app_calls[0]["uia_forbidden_markers"],
            ("OPENWUKONG_UIA_ACCEPTANCE: FAIL",),
        )
        self.assertEqual(data["window_input_attempts"], 0)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["cursor_background_chat"]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
