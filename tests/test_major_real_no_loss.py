import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.major_real_no_loss import (
    prepare_owned_ide_bridge_helper,
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
                ide_bridge_urls=("http://127.0.0.1:8787",),
                workspace_path="E:/ideaProjects/agent/openwukong",
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
        self.assertEqual(app_calls[0]["ide_bridge_urls"], ("http://127.0.0.1:8787",))
        self.assertEqual(app_calls[0]["workspace_path"], "E:/ideaProjects/agent/openwukong")
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

    def test_runner_passes_wechat_uia_send_options_and_marks_wechat_send_verified(self):
        primary_calls = []

        def _primary_runner(fixture, **kwargs):
            primary_calls.append({"fixture": fixture, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 1,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "scenario_id": "wechat.chat.draft_reply",
                            "status": "verified",
                            "real_verified": True,
                            "send_attempts": 1,
                            "window_input_attempts": 0,
                            "details": {
                                "background_send_verified": True,
                                "uia_semantic_action_ready": True,
                                "uia_semantic_action_dry_run": {
                                    "decision": "wechat_uia_semantic_action_dry_run_ready",
                                },
                                "uia_semantic_action_send_report": {
                                    "decision": "wechat_uia_semantic_action_send_accepted",
                                    "send_attempts": 1,
                                    "window_input_attempts": 0,
                                    "foreground_focus_stable": True,
                                },
                            },
                        }
                    ],
                }
            )

        def _agent_app_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
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
                agent_apps=(),
                cli_agents=(),
                allow_wechat_uia_semantic_send=True,
                wechat_uia_message="OPENWUKONG WECHAT UIA CHECK",
                wechat_uia_required_markers=("OPENWUKONG WECHAT UIA CHECK",),
                wechat_uia_forbidden_markers=("OPENWUKONG WECHAT FAIL",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertTrue(primary_calls[0]["kwargs"]["allow_wechat_uia_semantic_send"])
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_uia_message"],
            "OPENWUKONG WECHAT UIA CHECK",
        )
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_uia_required_markers"],
            ("OPENWUKONG WECHAT UIA CHECK",),
        )
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_uia_forbidden_markers"],
            ("OPENWUKONG WECHAT FAIL",),
        )
        self.assertEqual(data["external_communication_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["wechat_background_send"]["status"], "verified")

    def test_runner_passes_wechat_native_bridge_options_and_marks_wechat_send_verified(self):
        primary_calls = []

        def _primary_runner(fixture, **kwargs):
            primary_calls.append({"fixture": fixture, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 1,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "scenario_id": "wechat.chat.draft_reply",
                            "status": "verified",
                            "real_verified": True,
                            "send_attempts": 1,
                            "window_input_attempts": 0,
                            "details": {
                                "background_send_verified": True,
                                "wechat_native_bridge_ready": True,
                                "wechat_native_bridge_dry_run_decision": "wechat_native_bridge_dry_run_ready",
                                "wechat_native_bridge_send_report": {
                                    "decision": "wechat_native_bridge_send_accepted",
                                    "send_attempts": 1,
                                    "native_call_attempts": 1,
                                    "window_input_attempts": 0,
                                    "foreground_focus_stable": True,
                                },
                            },
                        }
                    ],
                }
            )

        def _agent_app_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
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
                agent_apps=(),
                cli_agents=(),
                wechat_native_bridge_urls=("http://127.0.0.1:18180",),
                allow_wechat_native_bridge_send=True,
                wechat_native_bridge_message="OPENWUKONG WECHAT NATIVE CHECK",
                wechat_native_bridge_required_markers=(
                    "OPENWUKONG WECHAT NATIVE CHECK",
                ),
                wechat_native_bridge_forbidden_markers=(
                    "OPENWUKONG WECHAT NATIVE FAIL",
                ),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_native_bridge_urls"],
            ("http://127.0.0.1:18180",),
        )
        self.assertTrue(primary_calls[0]["kwargs"]["allow_wechat_native_bridge_send"])
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_native_bridge_message"],
            "OPENWUKONG WECHAT NATIVE CHECK",
        )
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_native_bridge_required_markers"],
            ("OPENWUKONG WECHAT NATIVE CHECK",),
        )
        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_native_bridge_forbidden_markers"],
            ("OPENWUKONG WECHAT NATIVE FAIL",),
        )
        self.assertEqual(data["external_communication_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["wechat_background_send"]["status"], "verified")
        self.assertEqual(
            requirements["wechat_background_send"]["evidence"][
                "wechat_native_bridge_dry_run_decision"
            ],
            "wechat_native_bridge_dry_run_ready",
        )

    def test_runner_prepares_owned_ide_bridge_and_forwards_endpoint_to_agent_app(self):
        app_calls = []
        helper_calls = []

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

        def _owned_ide_bridge_helper_runner(**kwargs):
            helper_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "owned-ide-bridge-helper",
                    "safety_mode": "isolated_helper_launch",
                    "enabled": True,
                    "ready": True,
                    "bridge_url": "http://127.0.0.1:8792",
                    "workspace_path": "E:/tmp/openwukong-owned-ide-workspace",
                    "launch_attempts": 1,
                    "stop_attempts": 1,
                    "isolated_command_probe_attempts": 3,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "cleanup_ok": True,
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
                            "agent": "cursor",
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
                agent_apps=("cursor",),
                cli_agents=(),
                project_name="openwukong",
                task_name="cursor-owned-bridge",
                allow_app_bridge_send=True,
                allow_owned_ide_bridge_helper_launch=True,
                owned_ide_executable="C:/Program Files/Cursor/Cursor.exe",
                owned_ide_bridge_port=8792,
                owned_ide_workspace_root="E:/tmp/openwukong-owned-ide-workspace",
                owned_ide_chat_adapter_id="cursor",
                primary_runner=_primary_runner,
                owned_ide_bridge_helper_runner=_owned_ide_bridge_helper_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()
            artifact = json.loads(Path(data["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(len(helper_calls), 1)
        self.assertEqual(helper_calls[0]["ide_executable"], "C:/Program Files/Cursor/Cursor.exe")
        self.assertEqual(helper_calls[0]["ide_bridge_port"], 8792)
        self.assertEqual(helper_calls[0]["workspace_root"], "E:/tmp/openwukong-owned-ide-workspace")
        self.assertEqual(helper_calls[0]["adapter_id"], "cursor")
        self.assertEqual(app_calls[0]["ide_bridge_urls"], ("http://127.0.0.1:8792",))
        self.assertEqual(app_calls[0]["workspace_path"], "E:/tmp/openwukong-owned-ide-workspace")
        self.assertEqual(data["owned_ide_bridge_launch_attempts"], 1)
        self.assertEqual(data["owned_ide_bridge_stop_attempts"], 1)
        self.assertEqual(data["isolated_ide_command_probe_attempts"], 3)
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["subreports"]["owned_ide_bridge_helper"]["cleanup_ok"])
        self.assertEqual(
            artifact["subreports"]["owned_ide_bridge_helper"]["bridge_url"],
            "http://127.0.0.1:8792",
        )
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["cursor_background_chat"]["status"], "verified")

    def test_prepare_owned_ide_bridge_helper_validates_adapter_with_injected_safe_steps(self):
        calls = {
            "execute": [],
            "capture": [],
            "probe": [],
            "settings": [],
        }

        def _execute_plan(plan, **kwargs):
            calls["execute"].append({"plan": plan.to_dict(), "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "control_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 4242,
                            "readiness_url": "http://127.0.0.1:8793",
                        }
                    ],
                }
            )

        def _capture(bridge_url, **kwargs):
            calls["capture"].append({"bridge_url": bridge_url, "kwargs": dict(kwargs)})
            if len(calls["capture"]) == 1:
                return _FakeReport(
                    {
                        "mode": "ide-bridge-capability-capture",
                        "ok": True,
                        "bridge_url": bridge_url,
                        "active_mapping": {
                            "cursor": {
                                "available": False,
                                "commandId": "",
                                "commandCandidates": ["composer.startComposerPrompt"],
                            }
                        },
                        "adapter_mapping": {},
                        "cursor_review_candidates": ["composer.startComposerPrompt"],
                    }
                )
            return _FakeReport(
                {
                    "mode": "ide-bridge-capability-capture",
                    "ok": True,
                    "bridge_url": bridge_url,
                    "adapter_mapping": {
                        "cursor": {
                            "available": True,
                            "commandId": "composer.startComposerPrompt",
                            "commandCandidates": ["composer.startComposerPrompt"],
                        }
                    },
                }
            )

        def _probe(bridge_url, **kwargs):
            calls["probe"].append({"bridge_url": bridge_url, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "ide-bridge-contract-probe",
                    "control_attempts": 3,
                    "validated_mapping": {
                        "cursor": {
                            "label": "cursor",
                            "commandId": "composer.startComposerPrompt",
                            "commandCandidates": ["composer.startComposerPrompt"],
                            "available": True,
                        }
                    },
                }
            )

        def _settings_builder(report, **kwargs):
            calls["settings"].append({"report": dict(report), "kwargs": dict(kwargs)})
            return {
                "openwukong.bridge.autoStart": True,
                "openwukong.bridge.host": kwargs["host"],
                "openwukong.bridge.port": kwargs["port"],
                "openwukong.bridge.allowedCommands": ["composer.startComposerPrompt"],
                "openwukong.bridge.chatAdapters": {
                    "cursor": {
                        "label": "cursor",
                        "commandId": "composer.startComposerPrompt",
                        "commandCandidates": ["composer.startComposerPrompt"],
                    }
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            report = prepare_owned_ide_bridge_helper(
                output_root=Path(tmp) / "owned-ide",
                project_name="openwukong",
                ide_executable="cursor.exe",
                ide_bridge_port=8793,
                adapter_id="cursor",
                plan_executor=_execute_plan,
                capability_capture=_capture,
                command_contract_probe=_probe,
                bridge_settings_builder=_settings_builder,
            )
            data = report.to_dict()
            settings = json.loads(Path(data["settings_path"]).read_text(encoding="utf-8"))

        self.assertTrue(data["ready"])
        self.assertEqual(data["launch_attempts"], 1)
        self.assertEqual(data["isolated_command_probe_attempts"], 3)
        self.assertEqual(data["bridge_url"], "http://127.0.0.1:8793")
        self.assertEqual(calls["probe"][0]["kwargs"]["command_ids"], ["composer.startComposerPrompt"])
        self.assertEqual(
            data["pre_probe_settings"]["openwukong.bridge.allowedCommands"],
            ["composer.startComposerPrompt"],
        )
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "composer.startComposerPrompt",
        )


if __name__ == "__main__":
    unittest.main()
