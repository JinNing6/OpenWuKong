import dataclasses
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.evaluation import major_real_no_loss
from openwukong.evaluation.major_real_no_loss import (
    MajorScenarioRealNoLossReport,
    prepare_agent_native_cdp_bridge_helper,
    prepare_owned_ide_bridge_helper,
    run_major_scenario_real_no_loss,
)


class _FakeReport:
    def __init__(self, data):
        self._data = dict(data)

    def to_dict(self):
        return dict(self._data)


class _FakeMainReport(_FakeReport):
    safe_run_ok = True


def _major_report(
    output_root="",
    primary=None,
    app=None,
    bridge_fixture_smoke=None,
    native_fixture_smoke=None,
    wechat_fixture_smoke=None,
    cli=None,
    helper=None,
    native_helper=None,
    app_devtools_resolution=None,
    app_devtools_launch=None,
):
    return MajorScenarioRealNoLossReport(
        output_root=output_root,
        artifact_path="",
        primary_report=dict(primary or {}),
        owned_ide_bridge_helper_report=dict(helper or {}),
        agent_native_cdp_bridge_helper_report=dict(native_helper or {}),
        agent_app_report=dict(app or {}),
        agent_app_bridge_fixture_smoke_report=dict(bridge_fixture_smoke or {}),
        agent_native_bridge_fixture_smoke_report=dict(native_fixture_smoke or {}),
        agent_cli_report=dict(cli or {}),
        wechat_native_bridge_fixture_smoke_report=dict(wechat_fixture_smoke or {}),
        agent_app_devtools_resolution_report=dict(app_devtools_resolution or {}),
        agent_app_devtools_owned_launch_report=dict(app_devtools_launch or {}),
        requirements=(),
    )


def _fake_dynamic_devtools_readiness_url(action):
    argv_text = " ".join(str(item) for item in action.get("argv", ()))
    if "Claude.exe" in argv_text:
        return "http://127.0.0.1:19556"
    if "Cursor.exe" in argv_text:
        return "http://127.0.0.1:19557"
    return "http://127.0.0.1:19555"


class MajorRealNoLossTests(unittest.TestCase):
    def test_runner_times_out_hung_primary_runner_and_writes_progress(self):
        release = threading.Event()

        def _preflight_runner():
            return _FakeReport(
                {
                    "mode": "desktop-system-dialog-preflight",
                    "safety_mode": "read_only_desktop_scan",
                    "ok": True,
                    "decision": "system_dialog_clear",
                    "control_allowed": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 0,
                    "system_dialog_detected": False,
                    "system_dialog_count": 0,
                    "system_dialog_snapshots": [],
                }
            )

        def _primary_runner(_fixture, **_kwargs):
            release.wait(10)
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"tasks": []},
                output_root=tmp,
                runner_timeout_sec=0.01,
                run_agent_app_scenarios=False,
                run_agent_cli_scenarios=False,
                system_dialog_preflight_runner=_preflight_runner,
                primary_runner=_primary_runner,
            )
            release.set()
            data = report.to_dict()
            progress = json.loads(
                (Path(tmp) / "major-real-no-loss-progress.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertFalse(data["safe_run_ok"])
        self.assertFalse(data["goal_complete"])
        self.assertTrue(data["runner_timed_out"])
        self.assertEqual(
            data["subreports"]["primary"]["decision"],
            "runner_stage_timeout",
        )
        self.assertEqual(data["subreports"]["primary"]["stage_name"], "primary")
        self.assertFalse(data["subreports"]["primary"]["attempt_counters_reliable"])
        self.assertEqual(progress["stages"][-1]["stage_name"], "primary")
        self.assertEqual(progress["stages"][-1]["status"], "timed_out")

    def test_runner_can_stop_after_first_stage_timeout_and_write_final_report(self):
        release = threading.Event()
        app_calls = []
        cli_calls = []

        def _preflight_runner():
            return _FakeReport(
                {
                    "mode": "desktop-system-dialog-preflight",
                    "safety_mode": "read_only_desktop_scan",
                    "ok": True,
                    "decision": "system_dialog_clear",
                    "control_allowed": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 0,
                    "system_dialog_detected": False,
                    "system_dialog_count": 0,
                    "system_dialog_snapshots": [],
                }
            )

        def _primary_runner(_fixture, **_kwargs):
            release.wait(10)
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            raise AssertionError("agent app runner must not run after timeout")

        def _agent_cli_runner(**kwargs):
            cli_calls.append(dict(kwargs))
            raise AssertionError("agent cli runner must not run after timeout")

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"tasks": []},
                output_root=tmp,
                runner_timeout_sec=0.01,
                stop_on_runner_timeout=True,
                system_dialog_preflight_runner=_preflight_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            release.set()
            data = report.to_dict()

        self.assertTrue(data["runner_timed_out"])
        self.assertTrue(data["runner_stage_failed"])
        self.assertEqual(app_calls, [])
        self.assertEqual(cli_calls, [])
        self.assertEqual(
            data["subreports"]["primary"]["decision"],
            "runner_stage_timeout",
        )
        self.assertEqual(
            data["subreports"]["agent_app"]["decision"],
            "skipped_after_runner_timeout",
        )
        self.assertEqual(
            data["subreports"]["agent_cli"]["decision"],
            "skipped_after_runner_timeout",
        )

    def test_runner_stops_before_subrunners_when_system_dialog_preflight_fails(self):
        primary_calls = []
        app_calls = []
        cli_calls = []
        preflight_calls = []

        def _preflight_runner(**kwargs):
            preflight_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "desktop-system-dialog-preflight",
                    "safety_mode": "read_only_desktop_scan",
                    "ok": False,
                    "decision": "system_dialog_detected",
                    "control_allowed": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 0,
                    "system_dialog_detected": True,
                    "system_dialog_count": 1,
                    "system_dialog_snapshots": [
                        {
                            "hwnd": 301,
                            "title": "Error",
                            "process_name": "Codex.exe",
                            "text": (
                                "Error launching app\n"
                                "Unable to find Electron app at "
                                "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                                "?type=click&tag=11634605478613629973"
                            ),
                        }
                    ],
                }
            )

        def _primary_runner(*args, **kwargs):
            primary_calls.append((args, kwargs))
            raise AssertionError("primary runner must not run after preflight failure")

        def _agent_app_runner(**kwargs):
            app_calls.append(kwargs)
            raise AssertionError("agent app runner must not run after preflight failure")

        def _agent_cli_runner(**kwargs):
            cli_calls.append(kwargs)
            raise AssertionError("agent cli runner must not run after preflight failure")

        with tempfile.TemporaryDirectory() as td:
            report = run_major_scenario_real_no_loss(
                fixture={"tasks": []},
                output_root=td,
                system_dialog_preflight_runner=_preflight_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
        data = report.to_dict()

        self.assertFalse(data["safe_run_ok"])
        self.assertFalse(data["goal_complete"])
        self.assertTrue(data["system_dialog_preflight_failed"])
        self.assertEqual(
            data["system_dialog_preflight"]["decision"],
            "system_dialog_detected",
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(preflight_calls), 1)
        self.assertEqual(primary_calls, [])
        self.assertEqual(app_calls, [])
        self.assertEqual(cli_calls, [])
        self.assertEqual(
            data["subreports"]["system_dialog_preflight"]["system_dialog_count"],
            1,
        )

    def test_runner_passes_existing_system_dialog_preflight_to_primary_runner(self):
        preflight_report = {
            "mode": "desktop-system-dialog-preflight",
            "safety_mode": "read_only_desktop_scan",
            "ok": True,
            "decision": "system_dialog_clear",
            "control_allowed": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "native_call_attempts": 0,
            "system_dialog_detected": False,
            "system_dialog_count": 0,
            "system_dialog_snapshots": [],
        }
        primary_preflight = []

        def _preflight_runner():
            return _FakeReport(preflight_report)

        def _primary_runner(*_args, **kwargs):
            runner = kwargs.get("system_dialog_preflight_runner")
            self.assertTrue(callable(runner))
            primary_preflight.append(runner())
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "external_communication_attempts": 0,
                    "owned_app_launch_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "transport_matrix": {"scenarios": []},
                }
            )

        def _agent_app_runner(**_kwargs):
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_cli_runner(**_kwargs):
            return _FakeReport(
                {
                    "mode": "agent-cli-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent_command_attempts": 0,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        with tempfile.TemporaryDirectory() as td:
            run_major_scenario_real_no_loss(
                fixture={"suite": "empty", "cases": []},
                output_root=td,
                system_dialog_preflight_runner=_preflight_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )

        self.assertEqual(primary_preflight, [preflight_report])

    def test_safe_run_allows_unrelated_focus_change_when_no_automation_attempts(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": False,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
            },
            cli={
                "foreground_focus_stable": False,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 0,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["background_screenshot_focus_stable"])
        self.assertTrue(data["automation_focus_safe"])
        self.assertTrue(data["safe_run_ok"])

    def test_safe_run_fails_focus_change_when_bridge_send_was_attempted(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": False,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "agent_command_attempts": 0,
            },
            cli={
                "foreground_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 0,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["background_screenshot_focus_stable"])
        self.assertFalse(data["automation_focus_safe"])
        self.assertFalse(data["safe_run_ok"])

    def test_safe_run_fails_when_cli_command_steals_foreground(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
            },
            cli={
                "foreground_focus_stable": False,
                "foreground_no_steal_verified": False,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 1,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["cli_foreground_focus_stable"])
        self.assertFalse(data["cli_foreground_no_steal_verified"])
        self.assertFalse(data["automation_focus_safe"])
        self.assertFalse(data["safe_run_ok"])

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
                    "passed_cases": 3,
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
                        {
                            "agent": "cursor",
                            "status": "background_cli_unavailable",
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
                cli_agents=("codex", "claude", "cursor"),
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
        self.assertEqual(requirements["cursor_cli_background_task"]["status"], "gated")
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "gated")
        self.assertEqual(requirements["claude_desktop_background_chat"]["status"], "unavailable")
        self.assertEqual(requirements["cursor_background_chat"]["status"], "gated")
        self.assertIn("wechat_background_send", data["unmet_requirements"])
        self.assertIn("claude_cli_background_task", data["unmet_requirements"])
        self.assertIn("cursor_cli_background_task", data["unmet_requirements"])
        self.assertEqual(artifact["mode"], "major-scenario-real-no-loss")

        self.assertTrue(primary_calls[0]["kwargs"]["allow_owned_browser_helper_launch"])
        self.assertEqual(app_calls[0]["agents"], ("codex app", "claude desktop"))
        self.assertEqual(cli_calls[0]["agents"], ("codex", "claude", "cursor"))
        self.assertTrue(cli_calls[0]["allow_cli_execution"])

    def test_app_requirement_preserves_auth_required_before_native_ready_gating(self):
        requirement = major_real_no_loss._app_requirement(
            "cursor_background_chat",
            "cursor",
            {
                "agent": "cursor",
                "status": "auth_required",
                "native_ready": True,
                "app_bridge_send_report": {
                    "decision": "app_bridge_auth_required",
                    "auth_required": True,
                },
            },
        ).to_dict()

        self.assertEqual(requirement["status"], "auth_required")
        self.assertEqual(requirement["blocking_reason"], "auth_required")

    def test_missing_default_cursor_app_case_is_reported_as_protected_gate(self):
        requirements = {
            item.requirement_id: item.to_dict()
            for item in major_real_no_loss._build_requirements(
                {},
                {"cases": []},
                {},
                include_primary=False,
                include_agent_app=True,
                include_agent_cli=False,
            )
        }

        cursor = requirements["cursor_background_chat"]

        self.assertEqual(cursor["status"], "gated")
        self.assertEqual(
            cursor["blocking_reason"],
            "gated_cursor_desktop_protected_explicit_bridge_required",
        )
        self.assertNotEqual(cursor["blocking_reason"], "case_missing")
        self.assertTrue(cursor["evidence"]["protected_default"])
        self.assertEqual(
            cursor["evidence"]["required_endpoint_kind"],
            "explicit_ide_bridge_or_isolated_cursor_profile",
        )

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

    def test_runner_passes_agent_native_bridge_urls_to_agent_app_runner(self):
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
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 1,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
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
                task_name="codex-agent-native-bridge",
                agent_native_bridge_urls=("http://127.0.0.1:18888",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            app_calls[0]["agent_native_bridge_urls"],
            ("http://127.0.0.1:18888",),
        )
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "gated")
        self.assertEqual(
            requirements["codex_app_background_chat"]["blocking_reason"],
            "native_connector_ready_but_send_not_verified",
        )

    def test_runner_passes_explicit_debugger_urls_to_agent_app_runner(self):
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
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 1,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
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
            run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("claude desktop",),
                cli_agents=(),
                project_name="openwukong",
                task_name="desktop-message",
                debugger_urls=("http://127.0.0.1:9444",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )

        self.assertEqual(app_calls[0]["debugger_urls"], ("http://127.0.0.1:9444",))

    def test_runner_passes_codex_app_server_ws_urls_to_agent_app_runner(self):
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
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 1,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                            "probe": {
                                "endpoints": [
                                    {
                                        "endpoint_type": "codex_app_server_ws",
                                        "bridge_url": "ws://127.0.0.1:19731",
                                        "ready": True,
                                    }
                                ]
                            },
                            "transport_matrix": {
                                "send_ready": False,
                                "best_available_transport": {
                                    "transport_id": "codex-app-server-ws"
                                },
                            },
                            "codex_app_server_thread_start_required": False,
                            "codex_app_server_thread_start_ready": False,
                            "codex_app_server_turn_start_ready": True,
                            "codex_app_server_turn_contract_ready": True,
                            "codex_app_server_turn_dry_run": {
                                "ok": True,
                                "decision": "codex_app_server_turn_dry_run_ready",
                                "control_attempts": 0,
                                "window_input_attempts": 0,
                                "native_call_attempts": 0,
                                "app_server_turn_start_attempts": 0,
                                "request": {
                                    "thread_id": "thread-abc",
                                    "turn_start_params": {
                                        "threadId": "thread-abc",
                                        "input": [
                                            {
                                                "type": "text",
                                                "text": "OPENWUKONG_ACCEPTANCE: PASS",
                                            }
                                        ],
                                    },
                                },
                            },
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
                task_name="desktop-message",
                codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
                allow_codex_app_server_thread_start=True,
                allow_codex_app_server_turn_start=True,
                codex_app_server_turn_start_timeout=12.5,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            app_calls[0]["codex_app_server_ws_urls"],
            ("ws://127.0.0.1:19731",),
        )
        self.assertTrue(app_calls[0]["allow_codex_app_server_thread_start"])
        self.assertTrue(app_calls[0]["allow_codex_app_server_turn_start"])
        self.assertEqual(app_calls[0]["codex_app_server_turn_start_timeout"], 12.5)
        self.assertEqual(data["control_attempts"], 0)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "gated")
        self.assertEqual(
            requirements["codex_app_background_chat"]["blocking_reason"],
            "native_connector_ready_but_send_not_verified",
        )
        readiness_cases = {
            item["agent"]: item for item in data["agent_app_endpoint_readiness"]["cases"]
        }
        self.assertTrue(
            readiness_cases["codex app"]["codex_app_server_turn_contract_ready"]
        )
        self.assertFalse(
            readiness_cases["codex app"]["codex_app_server_thread_start_required"]
        )
        self.assertFalse(
            readiness_cases["codex app"]["codex_app_server_thread_start_ready"]
        )
        self.assertTrue(
            readiness_cases["codex app"]["codex_app_server_turn_start_ready"]
        )
        self.assertEqual(
            readiness_cases["codex app"]["codex_app_server_turn_dry_run"]["decision"],
            "codex_app_server_turn_dry_run_ready",
        )

    def test_runner_passes_agent_native_bridge_registry_paths_to_agent_app_runner(self):
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
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 0,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "gated_native_endpoint_missing",
                            "real_verified": True,
                            "native_ready": False,
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
            registry_path = Path(tmp) / "native-bridges.json"
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("codex app",),
                cli_agents=(),
                project_name="openwukong",
                task_name="codex-agent-native-bridge",
                agent_native_bridge_registry_paths=(registry_path,),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            app_calls[0]["agent_native_bridge_registry_paths"],
            (registry_path,),
        )
        self.assertEqual(data["control_attempts"], 0)

    def test_runner_prepares_agent_native_cdp_bridge_helper_and_forwards_registry(self):
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

        def _helper_runner(**kwargs):
            helper_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-native-cdp-bridge-helper",
                    "safety_mode": "managed_background_helper_launch",
                    "enabled": True,
                    "ready": True,
                    "cleanup_ok": True,
                    "bridge_url": "http://127.0.0.1:18890",
                    "registry_path": str(Path(kwargs["output_root"]) / "native-bridges.json"),
                    "manifest_path": str(Path(kwargs["output_root"]) / "manifest.json"),
                    "launch_attempts": 1,
                    "stop_attempts": 1,
                    "stop_report": {
                        "mode": "session-readiness-stop",
                        "stop_attempts": 1,
                        "results": [{"status": "stopped"}],
                    },
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent": kwargs["agent"],
                    "agent_id": kwargs["agent_id"],
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
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 1,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
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
            explicit_registry = Path(tmp) / "explicit-native-bridges.json"
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("codex app",),
                cli_agents=(),
                project_name="openwukong",
                task_name="codex-agent-native-cdp-helper",
                agent_native_bridge_registry_paths=(explicit_registry,),
                allow_agent_native_cdp_bridge_helper_launch=True,
                agent_native_cdp_bridge_helper_agent="codex app",
                agent_native_cdp_bridge_helper_agent_id="codex",
                agent_native_cdp_bridge_helper_port=18890,
                agent_native_cdp_bridge_helper_debugger_url="http://127.0.0.1:9333",
                agent_native_cdp_bridge_helper_process_name="Codex.exe",
                agent_native_cdp_bridge_helper_runner=_helper_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        helper_registry = Path(tmp) / "agent-native-cdp-bridge" / "native-bridges.json"
        self.assertEqual(len(helper_calls), 1)
        self.assertEqual(helper_calls[0]["agent"], "codex app")
        self.assertEqual(helper_calls[0]["agent_id"], "codex")
        self.assertEqual(helper_calls[0]["debugger_url"], "http://127.0.0.1:9333")
        self.assertEqual(helper_calls[0]["process_name"], "Codex.exe")
        self.assertEqual(
            tuple(Path(path).resolve() for path in app_calls[0]["agent_native_bridge_registry_paths"]),
            (explicit_registry.resolve(), helper_registry.resolve()),
        )
        self.assertEqual(data["agent_native_cdp_bridge_launch_attempts"], 1)
        self.assertEqual(data["agent_native_cdp_bridge_stop_attempts"], 1)
        self.assertTrue(data["agent_native_cdp_bridge_cleanup_ok"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)

    def test_runner_prepares_agent_native_cdp_bridge_helper_fleet(self):
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

        def _helper_runner(**kwargs):
            helper_calls.append(dict(kwargs))
            root = Path(kwargs["output_root"])
            return _FakeReport(
                {
                    "mode": "agent-native-cdp-bridge-helper",
                    "safety_mode": "managed_background_helper_launch",
                    "enabled": True,
                    "ready": True,
                    "cleanup_ok": True,
                    "bridge_url": f"http://127.0.0.1:{kwargs['bridge_port']}",
                    "registry_path": str(root / "native-bridges.json"),
                    "manifest_path": str(root / "manifest.json"),
                    "launch_attempts": 1,
                    "stop_attempts": 1,
                    "stop_report": {
                        "mode": "session-readiness-stop",
                        "stop_attempts": 1,
                        "results": [{"status": "stopped"}],
                    },
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent": kwargs["agent"],
                    "agent_id": kwargs["agent_id"],
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
                    "background_screenshot_count": 3,
                    "background_screenshot_success_count": 3,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 3,
                    "failed_cases": 0,
                    "native_ready_cases": 3,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                        },
                        {
                            "agent": "claude desktop",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                        },
                        {
                            "agent": "cursor",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                        },
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

        specs = (
            {
                "agent": "codex app",
                "agent_id": "codex",
                "bridge_port": 18890,
                "debugger_url": "http://127.0.0.1:9333",
                "process_name": "Codex.exe",
            },
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "bridge_port": 18891,
                "debugger_url": "http://127.0.0.1:9444",
                "process_name": "Claude.exe",
            },
            {
                "agent": "cursor",
                "agent_id": "cursor",
                "bridge_port": 18892,
                "debugger_url": "http://127.0.0.1:9555",
                "process_name": "Cursor.exe",
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("codex app", "claude desktop", "cursor"),
                cli_agents=(),
                project_name="openwukong",
                task_name="agent-native-fleet",
                allow_agent_native_cdp_bridge_helper_launch=True,
                agent_native_cdp_bridge_helper_specs=specs,
                agent_native_cdp_bridge_helper_runner=_helper_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual([call["agent_id"] for call in helper_calls], ["codex", "claude", "cursor"])
        self.assertEqual(data["agent_native_cdp_bridge_launch_attempts"], 3)
        self.assertEqual(data["agent_native_cdp_bridge_stop_attempts"], 3)
        self.assertTrue(data["agent_native_cdp_bridge_cleanup_ok"])
        forwarded = tuple(
            Path(path).name for path in app_calls[0]["agent_native_bridge_registry_paths"]
        )
        self.assertEqual(forwarded, ("native-bridges.json",) * 3)
        helper_report = data["subreports"]["agent_native_cdp_bridge_helper"]
        self.assertEqual(helper_report["mode"], "agent-native-cdp-bridge-helper-fleet")
        self.assertEqual(len(helper_report["helpers"]), 3)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)

    def test_runner_prepares_agent_app_devtools_owned_launch_and_forwards_debugger_urls(self):
        app_calls = []
        devtools_calls = []

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

        class _Resolver:
            def resolve(self, agent):
                exe_name = {
                    "codex app": "Codex.exe",
                    "claude desktop": "Claude.exe",
                }[agent]
                return _FakeReport(
                    {
                        "mode": "app-resolution",
                        "ok": True,
                        "decision": "resolved",
                        "path": f"C:/Apps/{exe_name}",
                        "source": "running-process",
                    }
                )

        def _devtools_launch_runner(**kwargs):
            devtools_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-devtools-owned-launch-fleet",
                    "safety_mode": "managed_background_helper_launch",
                    "enabled": True,
                    "ready": True,
                    "cleanup_ok": True,
                    "output_root": str(kwargs["output_root"]),
                    "launch_attempts": 2,
                    "stop_attempts": 2,
                    "debugger_urls": [
                        "http://127.0.0.1:19555",
                        "http://127.0.0.1:19556",
                    ],
                    "helpers": [
                        {
                            "agent": "codex app",
                            "agent_id": "codex",
                            "ready": True,
                            "cleanup_ok": True,
                            "debugger_url": "http://127.0.0.1:19555",
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                            "manifest_path": "codex-manifest.json",
                            "stop_report": {
                                "mode": "session-readiness-stop",
                                "stop_attempts": 1,
                                "results": [{"status": "stopped"}],
                            },
                        },
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "ready": True,
                            "cleanup_ok": True,
                            "debugger_url": "http://127.0.0.1:19556",
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                            "manifest_path": "claude-manifest.json",
                            "stop_report": {
                                "mode": "session-readiness-stop",
                                "stop_attempts": 1,
                                "results": [{"status": "stopped"}],
                            },
                        },
                    ],
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
                    "background_screenshot_count": 2,
                    "background_screenshot_success_count": 2,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 2,
                    "failed_cases": 0,
                    "native_ready_cases": 2,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                        },
                        {
                            "agent": "claude desktop",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                        },
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
                agent_apps=("codex app", "claude desktop"),
                cli_agents=(),
                project_name="openwukong",
                task_name="agent-app-devtools-owned",
                debugger_urls=("http://127.0.0.1:19444",),
                allow_agent_app_devtools_owned_launch=True,
                agent_app_devtools_resolver=_Resolver(),
                agent_app_devtools_owned_launch_runner=_devtools_launch_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(len(devtools_calls), 1)
        resolution_cases = devtools_calls[0]["resolution_report"]["cases"]
        self.assertEqual(
            [case["executable_path"] for case in resolution_cases],
            ["C:/Apps/Codex.exe", "C:/Apps/Claude.exe"],
        )
        self.assertEqual(
            app_calls[0]["debugger_urls"],
            ("http://127.0.0.1:19444",),
        )
        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["codex"],
            ("http://127.0.0.1:19555",),
        )
        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["claude"],
            ("http://127.0.0.1:19556",),
        )
        self.assertEqual(data["agent_app_devtools_launch_attempts"], 2)
        self.assertEqual(data["agent_app_devtools_stop_attempts"], 2)
        self.assertTrue(data["agent_app_devtools_cleanup_ok"])
        self.assertEqual(
            data["subreports"]["agent_app_devtools_owned_launch"]["mode"],
            "agent-app-devtools-owned-launch-fleet",
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)

    def test_major_report_exposes_agent_app_transport_matrix_summary(self):
        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_app_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                            "transport_matrix": {
                                "send_ready": True,
                                "draft_ready": True,
                                "summary": {
                                    "background_read_only": 0,
                                },
                                "selected_send_transport": {
                                    "transport_id": "agent-native-bridge",
                                },
                            },
                        },
                        {
                            "agent": "cursor",
                            "status": "gated_native_endpoint_missing",
                            "real_verified": True,
                            "native_ready": False,
                            "transport_matrix": {
                                "send_ready": False,
                                "draft_ready": False,
                                "summary": {
                                    "background_read_only": 1,
                                },
                                "selected_send_transport": {},
                            },
                        },
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
                agent_apps=("codex app", "cursor"),
                cli_agents=(),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        summary = data["agent_app_transport_matrix_summary"]
        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["background_send_ready_cases"], 1)
        self.assertEqual(summary["background_draft_ready_cases"], 1)
        self.assertEqual(summary["background_read_only_cases"], 1)
        self.assertEqual(
            summary["selected_send_transport_counts"]["agent-native-bridge"],
            1,
        )
        self.assertEqual(summary["selected_send_transport_counts"]["none"], 1)
        readiness = data["objective_readiness_matrix"]
        self.assertEqual(readiness["mode"], "objective-readiness-matrix")
        self.assertFalse(readiness["goal_complete"])
        self.assertIn("codex_app_background_chat", readiness["summary"]["unsatisfied_requirements"])
        self.assertIn("cursor_background_chat", readiness["summary"]["unsatisfied_requirements"])

    def test_prepare_agent_app_devtools_owned_launch_fleet_launches_resolved_apps(self):
        calls = []

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            calls.append({"action": action, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 4343,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        resolution_report = {
            "mode": "agent-app-devtools-resolution",
            "cases": [
                {
                    "agent": "codex app",
                    "agent_id": "codex",
                    "status": "resolved",
                    "executable_ready": True,
                    "executable_path": "C:/Apps/Codex.exe",
                },
                {
                    "agent": "claude desktop",
                    "agent_id": "claude",
                    "status": "resolved",
                    "executable_ready": True,
                    "executable_path": "C:/Apps/Claude.exe",
                },
                {
                    "agent": "cursor",
                    "agent_id": "cursor",
                    "status": "app_not_found",
                    "executable_ready": False,
                    "executable_path": "",
                },
            ],
        }

        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {"Browser": "Agent/1.0", "Protocol-Version": "1.3"}
                if url.endswith("/json/list"):
                    port = "19556" if ":19556" in url else "19555"
                    return [
                        {
                            "id": f"page-{port}",
                            "type": "page",
                            "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/page-{port}",
                        }
                    ]
                raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report=resolution_report,
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        self.assertEqual(data["launch_attempts"], 2)
        self.assertFalse(data["cleanup_ok"])
        self.assertEqual(
            data["debugger_urls"],
            ["http://127.0.0.1:19555", "http://127.0.0.1:19556"],
        )
        self.assertEqual(
            [call["action"]["route_id"] for call in calls],
            ["agent-app-devtools-owned", "agent-app-devtools-owned"],
        )
        self.assertIn("--remote-debugging-port=0", calls[0]["action"]["argv"])
        self.assertIn("--user-data-dir", " ".join(calls[0]["action"]["argv"]))
        self.assertEqual(data["helpers"][0]["agent_id"], "codex")

    def test_agent_app_devtools_resolution_accepts_start_menu_shortcut_target_exe(self):
        class _Resolver:
            def resolve(self, agent):
                self.agent = agent
                return _FakeReport(
                    {
                        "mode": "app-resolution",
                        "ok": True,
                        "decision": "resolved",
                        "source": "start-menu",
                        "path": "C:/Users/me/AppData/Local/Programs/Cursor/Cursor.exe",
                        "selected_candidate": {
                            "source": "start-menu",
                            "display_name": "Cursor",
                            "path": "C:/Users/me/AppData/Local/Programs/Cursor/Cursor.exe",
                            "executable_name": "Cursor.exe",
                            "metadata": {
                                "shortcut_path": "C:/ProgramData/Microsoft/Windows/Start Menu/Programs/Cursor/Cursor.lnk"
                            },
                        },
                    }
                )

        report = major_real_no_loss._build_agent_app_devtools_resolution_report(
            ("cursor",),
            resolver=_Resolver(),
        )
        case = report["cases"][0]

        self.assertEqual(case["status"], "resolved")
        self.assertTrue(case["executable_ready"])
        self.assertEqual(
            case["executable_path"],
            "C:/Users/me/AppData/Local/Programs/Cursor/Cursor.exe",
        )

    def test_agent_app_devtools_resolution_falls_back_to_launchable_candidate_when_selected_is_pathless(self):
        class _Resolver:
            def resolve(self, agent):
                self.agent = agent
                return _FakeReport(
                    {
                        "mode": "app-resolution",
                        "ok": True,
                        "decision": "resolved",
                        "source": "start-apps",
                        "path": "",
                        "selected_candidate": {
                            "source": "start-apps",
                            "display_name": "Cursor",
                            "path": "",
                            "metadata": {"app_id": "Anysphere.Cursor"},
                        },
                        "candidates": [
                            {
                                "source": "start-apps",
                                "display_name": "Cursor",
                                "path": "",
                                "metadata": {"app_id": "Anysphere.Cursor"},
                            },
                            {
                                "source": "start-menu",
                                "display_name": "Cursor",
                                "path": "E:/cursor/cursor/cursor/Cursor.exe",
                                "executable_name": "Cursor.exe",
                                "metadata": {
                                    "shortcut_path": "C:/ProgramData/Microsoft/Windows/Start Menu/Programs/Cursor/Cursor.lnk"
                                },
                            },
                        ],
                    }
                )

        report = major_real_no_loss._build_agent_app_devtools_resolution_report(
            ("cursor",),
            resolver=_Resolver(),
        )
        case = report["cases"][0]

        self.assertEqual(case["status"], "resolved")
        self.assertTrue(case["executable_ready"])
        self.assertEqual(case["executable_path"], "E:/cursor/cursor/cursor/Cursor.exe")

    def test_prepare_agent_app_devtools_owned_launch_fleet_forwards_workspace_to_cursor_launch(self):
        calls = []

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            calls.append({"action": action, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 5157,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {"Browser": "Cursor/1.0", "Protocol-Version": "1.3"}
                if url.endswith("/json/list"):
                    return [
                        {
                            "id": "cursor-page",
                            "type": "page",
                            "title": "openwukong - Cursor",
                            "url": "vscode-file://vscode-app/E:/ideaProjects/agent/openwukong",
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-page",
                        }
                    ]
                raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report={
                    "mode": "agent-app-devtools-resolution",
                    "cases": [
                        {
                            "agent": "cursor",
                            "agent_id": "cursor",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Apps/Cursor.exe",
                        }
                    ],
                },
                workspace_path="E:/ideaProjects/agent/openwukong",
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        self.assertTrue(data["ready"])
        argv = calls[0]["action"]["argv"]
        self.assertIn("E:/ideaProjects/agent/openwukong", argv)
        self.assertIn(
            "E:/ideaProjects/agent/openwukong",
            calls[0]["action"]["command"],
        )
        self.assertEqual(data["helpers"][0]["workspace_path"], "E:/ideaProjects/agent/openwukong")

    def test_prepare_agent_app_devtools_launch_fleet_can_use_cursor_default_profile(self):
        calls = []

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            calls.append({"action": action, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 5158,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {"Browser": "Cursor/1.0", "Protocol-Version": "1.3"}
                if url.endswith("/json/list"):
                    return [
                        {
                            "id": "cursor-page",
                            "type": "page",
                            "title": "openwukong - Cursor",
                            "url": "vscode-file://vscode-app/E:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-page",
                        }
                    ]
                raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report={
                    "mode": "agent-app-devtools-resolution",
                    "cases": [
                        {
                            "agent": "cursor",
                            "agent_id": "cursor",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Apps/Cursor.exe",
                        }
                    ],
                },
                workspace_path="E:/ideaProjects/agent/openwukong",
                default_profile_agents=("cursor",),
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        argv = calls[0]["action"]["argv"]
        self.assertTrue(data["ready"])
        self.assertFalse(calls[0]["action"]["creates_isolated_profile"])
        self.assertNotIn("--user-data-dir=", " ".join(argv))
        self.assertEqual(data["helpers"][0]["profile_mode"], "default-user-profile")
        self.assertTrue(data["helpers"][0]["uses_default_profile"])
        self.assertEqual(data["helpers"][0]["user_data_dir"], "")

    def test_prepare_agent_app_devtools_launch_fleet_can_use_default_profile_without_workspace_arg(self):
        calls = []

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            calls.append({"action": action, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 6182,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {"Browser": "Codex/1.0", "Protocol-Version": "1.3"}
                if url.endswith("/json/list"):
                    return [
                        {
                            "id": "codex-page",
                            "type": "page",
                            "title": "Codex",
                            "url": "app://codex/index.html",
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19555/devtools/page/codex-page",
                        }
                    ]
                raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report={
                    "mode": "agent-app-devtools-resolution",
                    "cases": [
                        {
                            "agent": "codex app",
                            "agent_id": "codex",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Apps/Codex.exe",
                        }
                    ],
                },
                workspace_path="E:/ideaProjects/agent/openwukong",
                default_profile_agents=("codex app",),
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        argv = calls[0]["action"]["argv"]
        self.assertTrue(data["ready"])
        self.assertFalse(calls[0]["action"]["creates_isolated_profile"])
        self.assertNotIn("--user-data-dir=", " ".join(argv))
        self.assertNotIn("E:/ideaProjects/agent/openwukong", argv)
        self.assertEqual(data["helpers"][0]["profile_mode"], "default-user-profile")
        self.assertTrue(data["helpers"][0]["uses_default_profile"])
        self.assertEqual(data["helpers"][0]["workspace_path"], "")

    def test_prepare_agent_app_devtools_owned_launch_fleet_waits_for_endpoint_health(self):
        http_calls = []

        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                http_calls.append((url, timeout))
                if url.endswith("/json/version"):
                    return {"Browser": "Codex/1.0", "Protocol-Version": "1.3"}
                if url.endswith("/json/list"):
                    return [
                        {
                            "id": "page-1",
                            "type": "page",
                            "title": "Codex",
                            "url": "app://codex/index.html",
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19555/devtools/page/page-1",
                        }
                    ]
                raise AssertionError(url)

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 77524,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report={
                    "mode": "agent-app-devtools-resolution",
                    "cases": [
                        {
                            "agent": "codex app",
                            "agent_id": "codex",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Apps/Codex.exe",
                        }
                    ],
                },
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        self.assertTrue(data["ready"])
        self.assertEqual(data["healthy_endpoint_count"], 1)
        self.assertEqual(data["debugger_urls"], ["http://127.0.0.1:19555"])
        health = data["helpers"][0]["endpoint_health"]
        self.assertTrue(health["ready"])
        self.assertEqual(health["target_count"], 1)
        self.assertEqual(health["targets"][0]["target_id"], "page-1")
        self.assertEqual(data["helpers"][0]["pid"], 77524)
        self.assertEqual(http_calls[0][0], "http://127.0.0.1:19555/json/version")
        self.assertEqual(http_calls[1][0], "http://127.0.0.1:19555/json/list")

    def test_prepare_agent_app_devtools_owned_launch_fleet_probes_browser_level_targets_without_ready(self):
        class _HTTPProbe:
            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {
                        "Browser": "Cursor/1.0",
                        "Protocol-Version": "1.3",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1",
                    }
                if url.endswith("/json/list"):
                    return []
                raise AssertionError(url)

        class _DevToolsClient:
            def __init__(self):
                self.calls = []

            def call_browser_method(self, debugger_url, method, params=None):
                self.calls.append((debugger_url, method, dict(params or {})))
                return {
                    "targetInfos": [
                        {
                            "targetId": "cursor-browser-page",
                            "type": "page",
                            "title": "Cursor",
                            "url": "app://cursor/workbench.html",
                            "attached": False,
                        }
                    ]
                }

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            return _FakeReport(
                {
                    "mode": "session-readiness-execution",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "launch_attempts": 1,
                    "manifest_path": kwargs["manifest_path"],
                    "results": [
                        {
                            "status": "started",
                            "pid": 88457,
                            "readiness_url": _fake_dynamic_devtools_readiness_url(action),
                        }
                    ],
                }
            )

        devtools_client = _DevToolsClient()
        with tempfile.TemporaryDirectory() as tmp:
            report = major_real_no_loss.prepare_agent_app_devtools_owned_launch_fleet(
                output_root=Path(tmp) / "agent-app-devtools",
                resolution_report={
                    "mode": "agent-app-devtools-resolution",
                    "cases": [
                        {
                            "agent": "cursor",
                            "agent_id": "cursor",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Apps/Cursor.exe",
                        }
                    ],
                },
                plan_executor=_execute_plan,
                http_probe=_HTTPProbe(),
                devtools_client=devtools_client,
                endpoint_wait_timeout_sec=0.2,
            )
            data = report.to_dict()

        self.assertFalse(data["ready"])
        self.assertEqual(data["healthy_endpoint_count"], 0)
        self.assertEqual(data["debugger_urls"], [])
        helper = data["helpers"][0]
        self.assertFalse(helper["ready"])
        self.assertEqual(helper["error"], "devtools_targets_not_ready")
        health = helper["endpoint_health"]
        self.assertFalse(health["ready"])
        self.assertEqual(health["error"], "devtools_targets_not_ready")
        self.assertTrue(health["browser_level_ready"])
        self.assertEqual(health["browser_websocket_url"], "ws://127.0.0.1:19557/devtools/browser/browser-1")
        self.assertEqual(health["browser_target_count"], 1)
        self.assertEqual(health["browser_targets"][0]["target_id"], "cursor-browser-page")
        self.assertGreaterEqual(len(devtools_client.calls), 1)
        self.assertTrue(
            all(
                call == ("http://127.0.0.1:19557", "Target.getTargets", {})
                for call in devtools_client.calls
            )
        )

    def test_wait_for_agent_app_devtools_endpoint_health_waits_until_page_target_appears(self):
        class _HTTPProbe:
            def __init__(self):
                self.list_calls = 0

            def get_json(self, url, timeout=0.2):
                if url.endswith("/json/version"):
                    return {
                        "Browser": "Cursor/1.0",
                        "Protocol-Version": "1.3",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1",
                    }
                if url.endswith("/json/list"):
                    self.list_calls += 1
                    if self.list_calls == 1:
                        return []
                    return [
                        {
                            "id": "cursor-page-1",
                            "type": "page",
                            "title": "openwukong - Cursor",
                            "url": "vscode-file://cursor/workbench.html",
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-page-1",
                        }
                    ]
                raise AssertionError(url)

        class _DevToolsClient:
            def __init__(self):
                self.calls = []

            def call_browser_method(self, debugger_url, method, params=None):
                self.calls.append((debugger_url, method, dict(params or {})))
                return {"targetInfos": []}

        http_probe = _HTTPProbe()
        devtools_client = _DevToolsClient()

        health = major_real_no_loss._wait_for_agent_app_devtools_endpoint_health(
            "http://127.0.0.1:19557",
            http_probe=http_probe,
            devtools_client=devtools_client,
            timeout_sec=1.0,
            request_timeout=0.001,
        )

        self.assertTrue(health["ready"])
        self.assertEqual(health["error"], "")
        self.assertGreaterEqual(health["attempts"], 2)
        self.assertEqual(http_probe.list_calls, 2)
        self.assertEqual(health["target_count"], 1)
        self.assertEqual(health["targets"][0]["title"], "openwukong - Cursor")
        self.assertGreaterEqual(len(devtools_client.calls), 2)

    def test_stop_agent_app_devtools_owned_launch_removes_isolated_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper_root = Path(tmp) / "agent-app-devtools" / "01-cursor"
            profile = helper_root / "profile"
            profile.mkdir(parents=True)
            (profile / "state.json").write_text("{}", encoding="utf-8")
            manifest = helper_root / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")

            stop_report = _FakeReport(
                {
                    "mode": "session-readiness-stop",
                    "safety_mode": "manifest_pid_tree_stop",
                    "control_attempts": 0,
                    "stop_attempts": 1,
                    "results": [
                        {
                            "action_id": "launch_agent_app_devtools_owned",
                            "status": "stopped",
                            "error": "",
                        }
                    ],
                }
            )
            launch_report = {
                "mode": "agent-app-devtools-owned-launch",
                "enabled": True,
                "ready": True,
                "manifest_path": str(manifest),
                "user_data_dir": str(profile),
                "cleanup_ok": False,
            }

            with patch(
                "openwukong.evaluation.major_real_no_loss.stop_session_readiness_manifest",
                return_value=stop_report,
            ):
                updated = major_real_no_loss._stop_agent_app_devtools_owned_launch_if_needed(
                    launch_report
                )

            self.assertFalse(profile.exists())
            self.assertTrue(updated["profile_cleanup_attempted"])
            self.assertTrue(updated["profile_cleanup_ok"])
            self.assertTrue(updated["cleanup_ok"])

    def test_runner_forwards_owned_devtools_process_provider_and_urls_by_agent(self):
        app_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _devtools_launch_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-devtools-owned-launch-fleet",
                    "enabled": True,
                    "ready": True,
                    "cleanup_ok": True,
                    "launch_attempts": 2,
                    "stop_attempts": 2,
                    "debugger_urls": [
                        "http://127.0.0.1:19555",
                        "http://127.0.0.1:19556",
                    ],
                    "helpers": [
                        {
                            "agent": "codex app",
                            "agent_id": "codex",
                            "ready": True,
                            "cleanup_ok": True,
                            "debugger_url": "http://127.0.0.1:19555",
                            "debug_port": 19555,
                            "executable_path": "C:/Apps/Codex.exe",
                            "pid": 77524,
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                        },
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "ready": True,
                            "cleanup_ok": True,
                            "debugger_url": "http://127.0.0.1:19556",
                            "debug_port": 19556,
                            "executable_path": "C:/Apps/Claude.exe",
                            "pid": 93796,
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                        },
                    ],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            owned_processes = tuple(kwargs["process_provider"]())
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "codex app",
                            "status": "native_connector_ready",
                            "real_verified": True,
                            "native_ready": True,
                            "owned_processes": [process.to_dict() for process in owned_processes],
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
                agent_apps=("codex app", "claude desktop"),
                cli_agents=(),
                debugger_urls=("http://127.0.0.1:19444",),
                allow_agent_app_devtools_owned_launch=True,
                agent_app_devtools_owned_launch_runner=_devtools_launch_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
                agent_app_process_provider=lambda: (),
            )
            data = report.to_dict()

        self.assertEqual(
            app_calls[0]["debugger_urls"],
            ("http://127.0.0.1:19444",),
        )
        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["codex"],
            ("http://127.0.0.1:19555",),
        )
        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["claude"],
            ("http://127.0.0.1:19556",),
        )
        owned_processes = data["subreports"]["agent_app"]["cases"][0]["owned_processes"]
        self.assertEqual(
            [(item["process_name"], item["pid"], item["listening_ports"]) for item in owned_processes],
            [("Codex.exe", 77524, [19555]), ("Claude.exe", 93796, [19556])],
        )

    def test_runner_forwards_probeable_unready_owned_devtools_for_read_only_matrix(self):
        app_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _devtools_launch_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-devtools-owned-launch-fleet",
                    "enabled": True,
                    "ready": False,
                    "cleanup_ok": True,
                    "launch_attempts": 1,
                    "stop_attempts": 1,
                    "debugger_urls": [],
                    "helpers": [
                        {
                            "agent": "cursor",
                            "agent_id": "cursor",
                            "ready": False,
                            "cleanup_ok": True,
                            "debugger_url": "http://127.0.0.1:19557",
                            "debug_port": 19557,
                            "executable_path": "C:/Apps/Cursor.exe",
                            "pid": 88457,
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                            "endpoint_health": {
                                "ready": False,
                                "error": "devtools_targets_not_ready",
                                "browser_level_ready": True,
                                "browser_websocket_url": "ws://127.0.0.1:19557/devtools/browser/browser-1",
                                "target_count": 0,
                            },
                        }
                    ],
                }
            )

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            owned_processes = tuple(kwargs["process_provider"]())
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "cursor",
                            "status": "gated_native_endpoint_missing",
                            "real_verified": True,
                            "native_ready": False,
                            "owned_processes": [process.to_dict() for process in owned_processes],
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
                allow_agent_app_devtools_owned_launch=True,
                agent_app_devtools_owned_launch_runner=_devtools_launch_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
                agent_app_process_provider=lambda: (),
            )
            data = report.to_dict()

        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["cursor"],
            ("http://127.0.0.1:19557",),
        )
        owned_processes = data["subreports"]["agent_app"]["cases"][0]["owned_processes"]
        self.assertEqual(owned_processes[0]["process_name"], "Cursor.exe")
        self.assertEqual(owned_processes[0]["listening_ports"], [19557])

    def test_runner_forwards_default_profile_agents_to_devtools_launch(self):
        launch_calls = []
        app_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _devtools_launch_runner(**kwargs):
            launch_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-devtools-owned-launch-fleet",
                    "enabled": True,
                    "ready": True,
                    "cleanup_ok": True,
                    "launch_attempts": 1,
                    "stop_attempts": 1,
                    "debugger_urls": ["http://127.0.0.1:19557"],
                    "helpers": [
                        {
                            "agent": "cursor",
                            "agent_id": "cursor",
                            "ready": True,
                            "cleanup_ok": True,
                            "profile_mode": "default-user-profile",
                            "uses_default_profile": True,
                            "debugger_url": "http://127.0.0.1:19557",
                            "debug_port": 19557,
                            "executable_path": "C:/Apps/Cursor.exe",
                            "pid": 5158,
                            "launch_attempts": 1,
                            "stop_attempts": 1,
                        }
                    ],
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
            run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=("cursor",),
                cli_agents=(),
                workspace_path="E:/ideaProjects/agent/openwukong",
                allow_agent_app_devtools_default_profile_launch=True,
                agent_app_devtools_endpoint_wait_timeout_sec=16.0,
                agent_app_devtools_request_timeout_sec=1.5,
                agent_app_devtools_owned_launch_runner=_devtools_launch_runner,
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
                agent_app_process_provider=lambda: (),
            )

        self.assertEqual(launch_calls[0]["default_profile_agents"], ("cursor",))
        self.assertEqual(launch_calls[0]["endpoint_wait_timeout_sec"], 16.0)
        self.assertEqual(launch_calls[0]["request_timeout"], 1.5)
        self.assertEqual(
            app_calls[0]["debugger_urls_by_agent"]["cursor"],
            ("http://127.0.0.1:19557",),
        )
        self.assertEqual(app_calls[0]["request_timeout"], 1.5)

    def test_report_exposes_agent_app_endpoint_acceptance_package(self):
        report = _major_report(
            app={
                "mode": "agent-app-real-no-loss",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "cases": [
                    {
                        "agent": "codex app",
                        "status": "gated_native_endpoint_missing",
                        "real_verified": True,
                        "native_ready": False,
                        "probe": {
                            "agent_id": "codex",
                            "ready_endpoint_count": 0,
                            "endpoint_count": 0,
                            "endpoints": [],
                        },
                    },
                    {
                        "agent": "claude desktop",
                        "status": "agent_native_connector_endpoint_unhealthy",
                        "real_verified": True,
                        "native_ready": False,
                        "probe": {
                            "agent_id": "claude",
                            "ready_endpoint_count": 0,
                            "endpoint_count": 1,
                            "endpoints": [
                                {
                                    "endpoint_type": "agent_native_bridge",
                                    "ready": False,
                                    "bridge_url": "http://127.0.0.1:18891",
                                    "error": "cdp_endpoint_unhealthy",
                                }
                            ],
                        },
                    },
                    {
                        "agent": "cursor",
                        "status": "native_connector_ready",
                        "real_verified": True,
                        "native_ready": True,
                        "probe": {
                            "agent_id": "cursor",
                            "ready_endpoint_count": 1,
                            "endpoint_count": 1,
                            "endpoints": [
                                {
                                    "endpoint_type": "agent_native_bridge",
                                    "ready": True,
                                    "bridge_url": "http://127.0.0.1:18892",
                                }
                            ],
                        },
                    },
                ],
            },
            native_helper={
                "mode": "agent-native-cdp-bridge-helper-fleet",
                "enabled": True,
                "ready": False,
                "cleanup_ok": True,
                "launch_attempts": 3,
                "stop_attempts": 3,
                "helpers": [
                    {
                        "agent": "codex app",
                        "agent_id": "codex",
                        "bridge_url": "http://127.0.0.1:18890",
                        "registry_path": "logs/runtime/codex/native-bridges.json",
                        "ready": False,
                        "error": "agent_native_connector_endpoint_unhealthy",
                    }
                ],
            },
            app_devtools_resolution={
                "mode": "agent-app-devtools-resolution",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "cases": [
                    {
                        "agent": "codex app",
                        "agent_id": "codex",
                        "status": "resolved",
                        "executable_ready": True,
                        "executable_path": "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    },
                    {
                        "agent": "claude desktop",
                        "agent_id": "claude",
                        "status": "resolved_no_executable_path",
                        "executable_ready": False,
                        "executable_path": "",
                    },
                ],
            },
        )

        package = report.to_dict()["agent_app_endpoint_acceptance"]
        self.assertEqual(
            report.to_dict()["agent_app_devtools_resolution"]["mode"],
            "agent-app-devtools-resolution",
        )
        cases = {item["agent_id"]: item for item in package["cases"]}

        self.assertEqual(package["mode"], "agent-app-endpoint-acceptance")
        self.assertFalse(package["safe_to_send_now"])
        self.assertEqual(cases["codex"]["agent"], "codex app")
        self.assertFalse(cases["codex"]["safe_to_send_now"])
        self.assertEqual(
            cases["codex"]["required_endpoint_kind"],
            "owned_local_devtools_or_agent_native_bridge",
        )
        self.assertEqual(
            cases["codex"]["next_action"],
            "provide_owned_debugger_url_or_install_agent_native_bridge",
        )
        self.assertEqual(cases["codex"]["helper_spec_template"]["agent_id"], "codex")
        self.assertEqual(
            cases["codex"]["helper_spec_template"]["process_name"],
            "Codex.exe",
        )
        self.assertEqual(
            cases["codex"]["helper_spec_template"]["debugger_url"],
            "<required-owned-local-devtools-url>",
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["route_id"],
            "agent-app-devtools-owned",
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["debug_port"],
            0,
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["readiness_url"],
            "",
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["executable"],
            "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
        )
        self.assertFalse(
            cases["codex"]["owned_devtools_launch_plan_template"]["executable_ready"],
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["launch_blocking_reason"],
            "msix_windowsapps_not_background_launchable",
        )
        self.assertEqual(
            cases["codex"]["owned_devtools_launch_plan_template"]["startup_mode"],
            "minimized_no_activate",
        )
        self.assertEqual(
            cases["codex"]["helper_status"]["bridge_url"],
            "http://127.0.0.1:18890",
        )
        self.assertEqual(
            cases["claude"]["observed_endpoint_errors"],
            ["cdp_endpoint_unhealthy"],
        )
        self.assertFalse(
            cases["claude"]["owned_devtools_launch_plan_template"]["executable_ready"],
        )
        self.assertEqual(
            cases["claude"]["owned_devtools_launch_plan_template"][
                "executable_resolution_status"
            ],
            "resolved_no_executable_path",
        )
        self.assertEqual(
            cases["cursor"]["next_action"],
            "run_app_bridge_send_acceptance",
        )
        self.assertFalse(cases["cursor"]["safe_to_send_now"])
        self.assertTrue(all(item["no_focus_required"] for item in package["cases"]))

    def test_report_exposes_agent_app_endpoint_readiness_summary(self):
        report = _major_report(
            app={
                "mode": "agent-app-real-no-loss",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "cases": [
                    {
                        "agent": "codex app",
                        "status": "gated_native_endpoint_missing",
                        "real_verified": True,
                        "native_ready": False,
                        "probe": {
                            "agent_id": "codex",
                            "ready_endpoint_count": 0,
                            "endpoint_count": 0,
                            "endpoints": [],
                        },
                    },
                    {
                        "agent": "cursor",
                        "status": "native_connector_ready",
                        "real_verified": True,
                        "native_ready": True,
                        "probe": {
                            "agent_id": "cursor",
                            "ready_endpoint_count": 1,
                            "endpoint_count": 1,
                            "endpoints": [
                                {
                                    "endpoint_type": "agent_native_bridge",
                                    "ready": True,
                                    "bridge_url": "http://127.0.0.1:18892",
                                    "source": "registry",
                                }
                            ],
                        },
                    },
                ],
            },
            app_devtools_resolution={
                "mode": "agent-app-devtools-resolution",
                "cases": [
                    {
                        "agent": "codex app",
                        "agent_id": "codex",
                        "status": "resolved_no_executable_path",
                        "executable_ready": False,
                        "executable_path": "",
                    }
                ],
            },
            # This stale/unavailable IDE bridge must be reported as supplemental
            # evidence only; the ready native bridge remains the send candidate.
            # It must not be forwarded as a ready endpoint.
            # The real R148 state has this shape for Cursor.
            app_devtools_launch={},
        )
        report = dataclasses.replace(
            report,
            ide_extension_readiness_report={
                "mode": "ide-extension-bridge-readiness",
                "status": "bridge_unavailable",
                "blocking_reason": "bridge_endpoint_unavailable",
                "bridge_url": "http://127.0.0.1:8787",
                "agent_id": "cursor",
                "bridge_ready": False,
                "can_execute_without_focus": False,
                "can_write_without_focus": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
            },
        )

        readiness = report.to_dict()["agent_app_endpoint_readiness"]
        cases = {item["agent_id"]: item for item in readiness["cases"]}

        self.assertEqual(readiness["mode"], "agent-app-endpoint-readiness")
        self.assertEqual(readiness["control_attempts"], 0)
        self.assertEqual(readiness["window_input_attempts"], 0)
        self.assertEqual(readiness["bridge_send_attempts"], 0)
        self.assertEqual(readiness["total_cases"], 2)
        self.assertEqual(readiness["observed_endpoint_cases"], 1)
        self.assertEqual(readiness["ready_endpoint_cases"], 1)
        self.assertEqual(readiness["background_send_contract_candidate_cases"], 1)
        self.assertEqual(readiness["blocked_cases"], 1)
        self.assertEqual(cases["codex"]["blocking_reason"], "gated_native_endpoint_missing")
        self.assertEqual(cases["codex"]["ready_endpoint_url"], "")
        self.assertFalse(
            cases["codex"]["owned_devtools_launch_plan_template"]["executable_ready"]
        )
        self.assertEqual(
            cases["cursor"]["ready_endpoint_type"],
            "agent_native_bridge",
        )
        self.assertEqual(
            cases["cursor"]["ready_endpoint_url"],
            "http://127.0.0.1:18892",
        )
        self.assertTrue(cases["cursor"]["can_prepare_background_send_contract"])
        self.assertEqual(
            cases["cursor"]["existing_ide_extension_readiness"]["blocking_reason"],
            "bridge_endpoint_unavailable",
        )

    def test_owned_devtools_launch_plan_template_uses_absolute_owned_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _major_report(
                output_root=tmp,
                app={
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "status": "app_surface_not_ready",
                            "native_ready": False,
                            "real_verified": False,
                            "probe": {
                                "agent_id": "claude",
                                "endpoint_count": 0,
                                "ready_endpoint_count": 0,
                                "endpoints": [],
                            },
                        }
                    ],
                },
                app_devtools_resolution={
                    "mode": "agent-app-devtools-resolution",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Users/me/AppData/Local/Programs/Claude/Claude.exe",
                        }
                    ],
                },
            )
            template = report.to_dict()["agent_app_endpoint_readiness"]["cases"][0][
                "owned_devtools_launch_plan_template"
            ]
            user_data_dir = Path(template["user_data_dir"])
            profile_arg = next(
                arg
                for arg in template["argv"]
                if str(arg).startswith("--user-data-dir=")
            )

            self.assertTrue(user_data_dir.is_absolute())
            self.assertTrue(str(user_data_dir).startswith(str(Path(tmp).resolve())))
            self.assertEqual(profile_arg, f"--user-data-dir={user_data_dir}")
            self.assertFalse(user_data_dir.exists())

    def test_claude_desktop_devtools_resolution_rejects_cli_executable_path(self):
        class _Resolver:
            def resolve(self, agent):
                self.agent = agent
                return {
                    "mode": "app-resolution",
                    "ok": True,
                    "decision": "resolved",
                    "app_name": agent,
                    "app_id": "claude",
                    "path": "C:/Users/me/.local/bin/Claude.exe",
                    "source": "path",
                    "selected_candidate": {
                        "source": "path",
                        "display_name": "Claude",
                        "path": "C:/Users/me/.local/bin/Claude.exe",
                        "executable_name": "Claude.exe",
                    },
                    "candidates": [],
                }

        report = major_real_no_loss._build_agent_app_devtools_resolution_report(
            ("claude desktop",),
            resolver=_Resolver(),
        )
        case = report["cases"][0]

        self.assertEqual(case["agent"], "claude desktop")
        self.assertEqual(case["agent_id"], "claude")
        self.assertFalse(case["executable_ready"])
        self.assertEqual(case["executable_path"], "")
        self.assertEqual(case["status"], "resolved_no_executable_path")
        self.assertEqual(
            case["launch_blocking_reason"],
            "agent_app_cli_path_not_background_launchable",
        )

    def test_claude_desktop_owned_devtools_template_blocks_cli_executable_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _major_report(
                output_root=tmp,
                app={
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "status": "app_surface_not_ready",
                            "native_ready": False,
                            "real_verified": False,
                            "probe": {
                                "agent_id": "claude",
                                "endpoint_count": 0,
                                "ready_endpoint_count": 0,
                                "endpoints": [],
                            },
                        }
                    ],
                },
                app_devtools_resolution={
                    "mode": "agent-app-devtools-resolution",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "agent_id": "claude",
                            "status": "resolved",
                            "executable_ready": True,
                            "executable_path": "C:/Users/me/.local/bin/Claude.exe",
                        }
                    ],
                },
            )
        template = report.to_dict()["agent_app_endpoint_readiness"]["cases"][0][
            "owned_devtools_launch_plan_template"
        ]

        self.assertEqual(
            template["launch_blocking_reason"],
            "agent_app_cli_path_not_background_launchable",
        )
        self.assertFalse(template["executable_ready"])
        self.assertEqual(template["executable"], "C:/Users/me/.local/bin/Claude.exe")
        self.assertEqual(template["argv"], [])

    def test_endpoint_acceptance_uses_actual_default_profile_devtools_launch_report(self):
        report = _major_report(
            app={
                "mode": "agent-app-real-no-loss",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "cases": [
                    {
                        "agent": "cursor",
                        "status": "native_connector_ready",
                        "real_verified": True,
                        "native_ready": True,
                        "probe": {
                            "agent_id": "cursor",
                            "ready_endpoint_count": 1,
                            "endpoint_count": 1,
                            "endpoints": [
                                {
                                    "endpoint_type": "agent_native_bridge",
                                    "ready": True,
                                    "bridge_url": "http://127.0.0.1:19557",
                                }
                            ],
                        },
                    },
                ],
            },
            app_devtools_resolution={
                "mode": "agent-app-devtools-resolution",
                "cases": [
                    {
                        "agent": "cursor",
                        "agent_id": "cursor",
                        "status": "resolved",
                        "executable_ready": True,
                        "executable_path": "E:/cursor/cursor/cursor/Cursor.exe",
                    }
                ],
            },
            app_devtools_launch={
                "mode": "agent-app-devtools-owned-launch-fleet",
                "enabled": True,
                "ready": True,
                "cleanup_ok": True,
                "helpers": [
                    {
                        "agent": "cursor",
                        "agent_id": "cursor",
                        "profile_mode": "default-user-profile",
                        "uses_default_profile": True,
                        "user_data_dir": "",
                        "debug_port": 19557,
                        "debugger_url": "http://127.0.0.1:19557",
                        "executable_path": "E:/cursor/cursor/cursor/Cursor.exe",
                        "workspace_path": "E:/ideaProjects/agent/openwukong",
                    }
                ],
            },
        )

        package = report.to_dict()["agent_app_endpoint_acceptance"]
        template = package["cases"][0]["owned_devtools_launch_plan_template"]

        self.assertEqual(template["profile_mode"], "default-user-profile")
        self.assertTrue(template["uses_default_profile"])
        self.assertEqual(template["user_data_dir"], "")
        self.assertEqual(template["executable"], "E:/cursor/cursor/cursor/Cursor.exe")
        self.assertEqual(template["readiness_url"], "http://127.0.0.1:19557")
        self.assertNotIn("--user-data-dir=", " ".join(template["argv"]))

    def test_prepare_agent_native_cdp_bridge_helper_launches_and_waits_for_registry(self):
        calls = []

        def _execute_plan(plan, **kwargs):
            action = plan.to_dict()["actions"][0]
            calls.append({"action": action, "kwargs": dict(kwargs)})
            argv = action["argv"]
            registry_path = Path(argv[argv.index("--registry-path") + 1])
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "openwukong-native-bridge-registry-v1",
                        "agent_native_bridges": [
                            {
                                "url": "http://127.0.0.1:18891",
                                "type": "agent_native_bridge",
                                "agent_id": "codex",
                                "agent": "codex app",
                                "surface_kind": "desktop_app",
                                "enabled": True,
                                "app_binding": {"process_name": "Codex.exe"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
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
                            "pid": 4343,
                            "readiness_url": "http://127.0.0.1:18891",
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = prepare_agent_native_cdp_bridge_helper(
                output_root=Path(tmp) / "agent-native",
                agent="codex app",
                agent_id="codex",
                bridge_port=18891,
                debugger_url="http://127.0.0.1:9333",
                process_name="Codex.exe",
                project_name="openwukong",
                task_name="desktop-message",
                plan_executor=_execute_plan,
                registry_wait_timeout_sec=0.2,
            )
            data = report.to_dict()
            registry_exists = Path(data["registry_path"]).is_file()

        self.assertTrue(data["ready"])
        self.assertEqual(data["launch_attempts"], 1)
        self.assertEqual(data["bridge_url"], "http://127.0.0.1:18891")
        self.assertTrue(registry_exists)
        self.assertEqual(calls[0]["action"]["route_id"], "agent-native-cdp-bridge")
        self.assertIn("--debugger-url", calls[0]["action"]["argv"])
        self.assertIn("--process-name", calls[0]["action"]["argv"])

    def test_cli_forwards_agent_native_cdp_bridge_helper_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--allow-agent-native-cdp-bridge-helper-launch",
                    "--agent-native-cdp-bridge-helper-agent",
                    "codex app",
                    "--agent-native-cdp-bridge-helper-agent-id",
                    "codex",
                    "--agent-native-cdp-bridge-helper-port",
                    "18892",
                    "--agent-native-cdp-bridge-helper-debugger-url",
                    "http://127.0.0.1:9333",
                    "--agent-native-cdp-bridge-helper-process-name",
                    "Codex.exe",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["allow_agent_native_cdp_bridge_helper_launch"])
        self.assertEqual(
            calls[0]["agent_native_cdp_bridge_helper_agent"],
            "codex app",
        )
        self.assertEqual(calls[0]["agent_native_cdp_bridge_helper_agent_id"], "codex")
        self.assertEqual(calls[0]["agent_native_cdp_bridge_helper_port"], 18892)
        self.assertEqual(
            calls[0]["agent_native_cdp_bridge_helper_debugger_url"],
            "http://127.0.0.1:9333",
        )
        self.assertEqual(
            calls[0]["agent_native_cdp_bridge_helper_process_name"],
            "Codex.exe",
        )

    def test_cli_forwards_agent_native_cdp_bridge_helper_specs(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        specs = [
            {
                "agent": "codex app",
                "agent_id": "codex",
                "bridge_port": 18890,
                "debugger_url": "http://127.0.0.1:9333",
                "process_name": "Codex.exe",
            },
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "bridge_port": 18891,
                "debugger_url": "http://127.0.0.1:9444",
                "process_name": "Claude.exe",
            },
        ]

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--allow-agent-native-cdp-bridge-helper-launch",
                    "--agent-native-cdp-bridge-helper-spec",
                    json.dumps(specs[0]),
                    "--agent-native-cdp-bridge-helper-spec",
                    json.dumps(specs[1]),
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["allow_agent_native_cdp_bridge_helper_launch"])
        self.assertEqual(
            tuple(spec["agent_id"] for spec in calls[0]["agent_native_cdp_bridge_helper_specs"]),
            ("codex", "claude"),
        )
        self.assertEqual(
            calls[0]["agent_native_cdp_bridge_helper_specs"][1]["process_name"],
            "Claude.exe",
        )

    def test_cli_forwards_agent_app_devtools_owned_launch_option(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--allow-agent-app-devtools-owned-launch",
                    "--agent-app",
                    "codex app",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["allow_agent_app_devtools_owned_launch"])
        self.assertEqual(calls[0]["agent_apps"], ("codex app",))

    def test_cli_forwards_agent_app_devtools_default_profile_launch_option(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--allow-agent-app-devtools-default-profile-launch",
                    "--agent-app",
                    "cursor",
                    "--workspace-path",
                    "E:/ideaProjects/agent/openwukong",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["allow_agent_app_devtools_default_profile_launch"])
        self.assertEqual(calls[0]["agent_apps"], ("cursor",))
        self.assertEqual(
            calls[0]["workspace_path"],
            "E:/ideaProjects/agent/openwukong",
        )

    def test_cli_default_agent_apps_do_not_probe_user_cursor(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(["--json"])

        self.assertEqual(code, 0)
        self.assertIn("codex app", calls[0]["agent_apps"])
        self.assertIn("claude desktop", calls[0]["agent_apps"])
        self.assertNotIn("cursor", calls[0]["agent_apps"])

    def test_cli_default_cli_agents_keep_claude_on_app_surface_only(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(["--json"])

        self.assertEqual(code, 0)
        self.assertIn("codex", calls[0]["cli_agents"])
        self.assertNotIn("claude", calls[0]["cli_agents"])
        self.assertIn("cursor", calls[0]["cli_agents"])
        self.assertNotIn("cursor app", calls[0]["cli_agents"])
        self.assertNotIn("cursor desktop", calls[0]["cli_agents"])

    def test_claude_installed_app_not_running_is_gated_not_cli_fallback(self):
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
            self.assertEqual(kwargs["agents"], ("claude desktop",))
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": "claude desktop",
                            "status": "app_installed_not_running_connector_required",
                            "real_verified": False,
                            "native_ready": False,
                        }
                    ],
                }
            )

        def _agent_cli_runner(**kwargs):
            self.assertEqual(kwargs["agents"], ())
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
                run_primary_scenarios=False,
                agent_apps=("claude desktop",),
                cli_agents=(),
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
                primary_runner=_primary_runner,
            )
            data = report.to_dict()

        self.assertEqual(data["agent_command_attempts"], 0)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["claude_desktop_background_chat"]["status"], "gated")
        self.assertEqual(
            requirements["claude_desktop_background_chat"]["blocking_reason"],
            "app_installed_not_running_connector_required",
        )
        self.assertNotIn("claude_cli_background_task", requirements)

    def test_cli_forwards_agent_isolation_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--isolate-agent-app-scenarios",
                    "--isolate-agent-cli-scenarios",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["isolate_agent_app_scenarios"])
        self.assertTrue(calls[0]["isolate_agent_cli_scenarios"])

    def test_runner_can_isolate_agent_app_and_cli_scenarios_per_agent(self):
        app_calls = []
        cli_calls = []

        def _agent_app_runner(**kwargs):
            app_calls.append(dict(kwargs))
            agent = kwargs["agents"][0]
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "native_ready_cases": 0,
                    "cases": [
                        {
                            "agent": agent,
                            "status": (
                                "native_connector_ready"
                                if agent == "codex app"
                                else "unavailable"
                            ),
                            "real_verified": True,
                            "native_ready": agent == "codex app",
                        }
                    ],
                }
            )

        def _agent_cli_runner(**kwargs):
            cli_calls.append(dict(kwargs))
            agent = kwargs["agents"][0]
            return _FakeReport(
                {
                    "mode": "agent-cli-real-no-loss",
                    "safety_mode": "real_no_loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "agent_command_attempts": 1 if agent == "codex" else 0,
                    "foreground_focus_stable": True,
                    "foreground_no_steal_verified": True,
                    "passed_cases": 1,
                    "failed_cases": 0,
                    "cases": [
                        {
                            "agent": agent,
                            "status": (
                                "verified"
                                if agent == "codex"
                                else "cli_auth_required"
                            ),
                            "real_verified": agent == "codex",
                            "foreground_focus_stable": True,
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                run_primary_scenarios=False,
                agent_apps=("codex app", "claude desktop"),
                cli_agents=("codex", "claude"),
                isolate_agent_app_scenarios=True,
                isolate_agent_cli_scenarios=True,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            [call["agents"] for call in app_calls],
            [("codex app",), ("claude desktop",)],
        )
        self.assertEqual(
            [call["agents"] for call in cli_calls],
            [("codex",), ("claude",)],
        )
        self.assertEqual(
            [item["stage_name"] for item in data["runner_stage_reports"] if item["status"] == "completed"],
            [
                "system_dialog_preflight",
                "agent_app:codex app",
                "agent_app:claude desktop",
                "agent_cli:codex",
                "agent_cli:claude",
            ],
        )
        self.assertEqual(data["agent_command_attempts"], 1)
        self.assertEqual(data["background_screenshot_count"], 2)
        requirements = {item["requirement_id"]: item for item in data["requirements"]}
        self.assertEqual(requirements["codex_cli_background_task"]["status"], "verified")
        self.assertEqual(requirements["claude_cli_background_task"]["status"], "auth_required")
        self.assertEqual(requirements["codex_app_background_chat"]["status"], "gated")
        self.assertEqual(requirements["claude_desktop_background_chat"]["status"], "unavailable")

    def test_cli_forwards_agent_app_devtools_endpoint_timeouts(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--allow-agent-app-devtools-default-profile-launch",
                    "--agent-app-devtools-endpoint-wait-timeout-sec",
                    "17.5",
                    "--agent-app-devtools-request-timeout-sec",
                    "1.25",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["agent_app_devtools_endpoint_wait_timeout_sec"], 17.5)
        self.assertEqual(calls[0]["agent_app_devtools_request_timeout_sec"], 1.25)

    def test_cli_forwards_existing_ide_extension_bridge_probe_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--probe-existing-ide-extension-bridge",
                    "--ide-extension-bridge-url",
                    "http://127.0.0.1:8787",
                    "--ide-extension-agent-id",
                    "cursor",
                    "--ide-extension-request-timeout-sec",
                    "0.35",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["probe_existing_ide_extension_bridge"])
        self.assertEqual(calls[0]["ide_extension_bridge_url"], "http://127.0.0.1:8787")
        self.assertEqual(calls[0]["ide_extension_agent_id"], "cursor")
        self.assertEqual(calls[0]["ide_extension_request_timeout_sec"], 0.35)

    def test_runner_can_verify_agent_app_bridge_fixture_smoke_without_window_input(self):
        fixture_calls = []

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
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
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

        def _bridge_fixture_runner(**kwargs):
            fixture_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-app-bridge-fixture-smoke",
                    "safety_mode": "local_owned_devtools_fixture",
                    "ok": True,
                    "decision": "agent_app_bridge_fixture_smoke_verified",
                    "desktop_control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_report": {
                        "decision": "app_bridge_send_accepted",
                        "native_call_attempts": 1,
                        "window_input_attempts": 0,
                        "keyboard_input_attempts": 0,
                        "clipboard_write_attempts": 0,
                    },
                    "fixture": {
                        "cdp_request_count": 2,
                        "http_request_count": 2,
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=(),
                cli_agents=(),
                run_agent_app_bridge_fixture_smoke=True,
                agent_app_bridge_fixture_message="OPENWUKONG_FIXTURE_SMOKE",
                agent_app_bridge_fixture_required_markers=("FIXTURE: PASS",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_app_bridge_fixture_smoke_runner=_bridge_fixture_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(fixture_calls[0]["message"], "OPENWUKONG_FIXTURE_SMOKE")
        self.assertEqual(fixture_calls[0]["required_markers"], ("FIXTURE: PASS",))
        self.assertTrue(data["agent_app_bridge_fixture_smoke_enabled"])
        self.assertTrue(data["agent_app_bridge_fixture_smoke_ok"])
        self.assertEqual(data["agent_app_bridge_fixture_native_call_attempts"], 1)
        self.assertEqual(data["agent_app_bridge_fixture_control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertTrue(data["safe_run_ok"])
        self.assertIn("agent_app_bridge_fixture_smoke", data["subreports"])

    def test_agent_app_bridge_fixture_smoke_failure_fails_safe_gate(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
            },
            bridge_fixture_smoke={
                "enabled": True,
                "ok": False,
                "decision": "agent_app_bridge_fixture_smoke_failed",
                "control_attempts": 0,
                "desktop_control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_report": {"native_call_attempts": 0},
            },
            cli={
                "foreground_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 0,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["agent_app_bridge_fixture_smoke_ok"])
        self.assertEqual(data["failed_runner_count"], 1)
        self.assertFalse(data["safe_run_ok"])

    def test_cli_forwards_agent_app_bridge_fixture_smoke_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--run-agent-app-bridge-fixture-smoke",
                    "--agent-app-bridge-fixture-message",
                    "OPENWUKONG_FIXTURE_SMOKE",
                    "--agent-app-bridge-fixture-acceptance-marker",
                    "FIXTURE: PASS",
                    "--agent-app-bridge-fixture-forbid-marker",
                    "FIXTURE: FAIL",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["run_agent_app_bridge_fixture_smoke"])
        self.assertEqual(
            calls[0]["agent_app_bridge_fixture_message"],
            "OPENWUKONG_FIXTURE_SMOKE",
        )
        self.assertEqual(
            calls[0]["agent_app_bridge_fixture_required_markers"],
            ("FIXTURE: PASS",),
        )
        self.assertEqual(
            calls[0]["agent_app_bridge_fixture_forbidden_markers"],
            ("FIXTURE: FAIL",),
        )

    def test_runner_can_verify_agent_native_bridge_fixture_smoke_without_window_input(self):
        fixture_calls = []

        def _primary_runner(fixture, **kwargs):
            del fixture, kwargs
            return _FakeReport(
                {
                    "mode": "primary-scenario-real-no-loss",
                    "control_attempts": 0,
                    "external_communication_attempts": 0,
                    "window_input_attempts": 0,
                    "background_screenshot_focus_stable": True,
                    "failed_cases": 0,
                    "cases": [],
                }
            )

        def _agent_app_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
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

        def _native_fixture_runner(**kwargs):
            fixture_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-native-bridge-fixture-smoke",
                    "safety_mode": "local_owned_http_fixture",
                    "ok": True,
                    "decision": "agent_native_bridge_fixture_smoke_verified",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 1,
                    "send_report": {
                        "decision": "agent_native_bridge_send_accepted",
                        "native_call_attempts": 1,
                        "window_input_attempts": 0,
                        "keyboard_input_attempts": 0,
                        "clipboard_write_attempts": 0,
                        "dry_run_report": {
                            "readback_action_ready": True,
                        },
                    },
                    "fixture": {
                        "capability_request_count": 1,
                        "chat_request_count": 1,
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=(),
                cli_agents=(),
                run_agent_native_bridge_fixture_smoke=True,
                agent_native_bridge_fixture_message="OPENWUKONG_NATIVE_FIXTURE",
                agent_native_bridge_fixture_required_markers=("NATIVE: PASS",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_native_bridge_fixture_smoke_runner=_native_fixture_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(fixture_calls[0]["message"], "OPENWUKONG_NATIVE_FIXTURE")
        self.assertEqual(fixture_calls[0]["required_markers"], ("NATIVE: PASS",))
        self.assertTrue(data["agent_native_bridge_fixture_smoke_enabled"])
        self.assertTrue(data["agent_native_bridge_fixture_smoke_ok"])
        self.assertEqual(data["agent_native_bridge_fixture_native_call_attempts"], 1)
        self.assertEqual(data["agent_native_bridge_fixture_control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertTrue(data["safe_run_ok"])
        self.assertIn("agent_native_bridge_fixture_smoke", data["subreports"])

    def test_agent_native_bridge_fixture_smoke_failure_fails_safe_gate(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
            },
            native_fixture_smoke={
                "enabled": True,
                "ok": False,
                "decision": "agent_native_bridge_fixture_smoke_failed",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "native_call_attempts": 0,
                "send_report": {"native_call_attempts": 0},
            },
            cli={
                "foreground_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 0,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["agent_native_bridge_fixture_smoke_ok"])
        self.assertEqual(data["failed_runner_count"], 1)
        self.assertFalse(data["safe_run_ok"])

    def test_cli_forwards_agent_native_bridge_fixture_smoke_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--run-agent-native-bridge-fixture-smoke",
                    "--agent-native-bridge-fixture-message",
                    "OPENWUKONG_NATIVE_FIXTURE",
                    "--agent-native-bridge-fixture-acceptance-marker",
                    "NATIVE: PASS",
                    "--agent-native-bridge-fixture-forbid-marker",
                    "NATIVE: FAIL",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["run_agent_native_bridge_fixture_smoke"])
        self.assertEqual(
            calls[0]["agent_native_bridge_fixture_message"],
            "OPENWUKONG_NATIVE_FIXTURE",
        )
        self.assertEqual(
            calls[0]["agent_native_bridge_fixture_required_markers"],
            ("NATIVE: PASS",),
        )
        self.assertEqual(
            calls[0]["agent_native_bridge_fixture_forbidden_markers"],
            ("NATIVE: FAIL",),
        )

    def test_runner_can_run_agent_native_fixture_scope_without_real_scenario_runners(self):
        fixture_calls = []

        def _primary_runner(*args, **kwargs):
            del args, kwargs
            raise AssertionError("primary scenarios must be skipped")

        def _agent_app_runner(**kwargs):
            del kwargs
            raise AssertionError("agent app scenarios must be skipped")

        def _agent_cli_runner(**kwargs):
            del kwargs
            raise AssertionError("agent cli scenarios must be skipped")

        def _native_fixture_runner(**kwargs):
            fixture_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "agent-native-bridge-fixture-smoke",
                    "safety_mode": "local_owned_http_fixture",
                    "enabled": True,
                    "ok": True,
                    "decision": "agent_native_bridge_fixture_smoke_verified",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 1,
                    "send_report": {
                        "native_call_attempts": 1,
                        "window_input_attempts": 0,
                        "keyboard_input_attempts": 0,
                        "clipboard_write_attempts": 0,
                    },
                    "fixture": {
                        "capability_request_count": 1,
                        "chat_request_count": 1,
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fixture-only"},
                output_root=tmp,
                run_primary_scenarios=False,
                run_agent_app_scenarios=False,
                run_agent_cli_scenarios=False,
                run_agent_native_bridge_fixture_smoke=True,
                agent_native_bridge_fixture_message="OPENWUKONG_NATIVE_FIXTURE",
                agent_native_bridge_fixture_required_markers=("NATIVE: PASS",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
                agent_native_bridge_fixture_smoke_runner=_native_fixture_runner,
            )
            data = report.to_dict()

        self.assertEqual(len(fixture_calls), 1)
        self.assertTrue(data["scenario_scope"]["primary_scenarios_skipped"])
        self.assertTrue(data["scenario_scope"]["agent_app_scenarios_skipped"])
        self.assertTrue(data["scenario_scope"]["agent_cli_scenarios_skipped"])
        self.assertEqual(data["requirements"], [])
        self.assertEqual(data["unmet_requirements"], [])
        self.assertEqual(data["failed_runner_count"], 0)
        self.assertTrue(data["safe_run_ok"])
        self.assertFalse(data["goal_complete"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["agent_native_bridge_fixture_native_call_attempts"], 1)

    def test_cli_forwards_real_scenario_skip_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": True,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--skip-primary-scenarios",
                    "--skip-agent-app-scenarios",
                    "--skip-agent-cli-scenarios",
                    "--run-agent-native-bridge-fixture-smoke",
                ]
            )

        self.assertEqual(code, 0)
        self.assertFalse(calls[0]["run_primary_scenarios"])
        self.assertFalse(calls[0]["run_agent_app_scenarios"])
        self.assertFalse(calls[0]["run_agent_cli_scenarios"])
        self.assertTrue(calls[0]["run_agent_native_bridge_fixture_smoke"])

    def test_cli_forwards_runner_timeout_option(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": True,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--runner-timeout-sec",
                    "0.25",
                    "--stop-on-runner-timeout",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["runner_timeout_sec"], 0.25)
        self.assertTrue(calls[0]["stop_on_runner_timeout"])

    def test_cli_force_exits_after_runner_timeout_report_is_written(self):
        exits = []

        def _fake_runner(**kwargs):
            del kwargs
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": False,
                    "goal_complete": False,
                    "runner_timed_out": True,
                    "runner_stage_failed": True,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        def _fake_exit(code):
            exits.append(code)
            raise SystemExit(code)

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ), patch.object(
            major_real_no_loss,
            "_force_exit_process",
            _fake_exit,
        ):
            with self.assertRaises(SystemExit) as ctx:
                major_real_no_loss.main(
                    [
                        "--json",
                        "--runner-timeout-sec",
                        "0.25",
                    ]
                )

        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(exits, [1])

    def test_runner_can_verify_wechat_native_bridge_fixture_smoke_without_window_input(self):
        fixture_calls = []

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
            del kwargs
            return _FakeReport(
                {
                    "mode": "agent-app-real-no-loss",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
                    "agent_command_attempts": 0,
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

        def _wechat_fixture_runner(**kwargs):
            fixture_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "wechat-native-bridge-fixture-smoke",
                    "safety_mode": "local_owned_wechat_native_bridge_fixture",
                    "ok": True,
                    "decision": "wechat_native_bridge_fixture_smoke_verified",
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "native_call_attempts": 1,
                    "send_attempts": 1,
                    "send_report": {
                        "decision": "wechat_native_bridge_send_accepted",
                        "native_call_attempts": 1,
                        "window_input_attempts": 0,
                        "keyboard_input_attempts": 0,
                        "clipboard_write_attempts": 0,
                    },
                    "fixture": {
                        "capability_request_count": 1,
                        "send_request_count": 1,
                    },
                    "registry": {
                        "registered": True,
                        "discovered_urls": ["http://127.0.0.1:18888"],
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=(),
                cli_agents=(),
                run_wechat_native_bridge_fixture_smoke=True,
                wechat_native_bridge_fixture_message="OPENWUKONG_WECHAT_FIXTURE",
                wechat_native_bridge_fixture_required_markers=("WECHAT: PASS",),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                wechat_native_bridge_fixture_smoke_runner=_wechat_fixture_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(fixture_calls[0]["message"], "OPENWUKONG_WECHAT_FIXTURE")
        self.assertEqual(fixture_calls[0]["required_markers"], ("WECHAT: PASS",))
        self.assertTrue(data["wechat_native_bridge_fixture_smoke_enabled"])
        self.assertTrue(data["wechat_native_bridge_fixture_smoke_ok"])
        self.assertEqual(data["wechat_native_bridge_fixture_native_call_attempts"], 1)
        self.assertEqual(data["wechat_native_bridge_fixture_control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertTrue(data["safe_run_ok"])
        self.assertIn("wechat_native_bridge_fixture_smoke", data["subreports"])

    def test_wechat_native_bridge_fixture_smoke_failure_fails_safe_gate(self):
        report = _major_report(
            primary={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "external_communication_attempts": 0,
                "owned_app_launch_attempts": 0,
            },
            app={
                "background_screenshot_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 0,
                "agent_command_attempts": 0,
            },
            wechat_fixture_smoke={
                "enabled": True,
                "ok": False,
                "decision": "wechat_native_bridge_fixture_smoke_failed",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "native_call_attempts": 0,
                "send_report": {"native_call_attempts": 0},
            },
            cli={
                "foreground_focus_stable": True,
                "failed_cases": 0,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "agent_command_attempts": 0,
            },
        )
        data = report.to_dict()

        self.assertFalse(data["wechat_native_bridge_fixture_smoke_ok"])
        self.assertEqual(data["failed_runner_count"], 1)
        self.assertFalse(data["safe_run_ok"])

    def test_cli_forwards_wechat_native_bridge_fixture_smoke_options(self):
        calls = []

        def _fake_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeMainReport(
                {
                    "mode": "major-scenario-real-no-loss",
                    "safe_run_ok": True,
                    "goal_complete": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "requirements": [],
                }
            )

        with patch.object(
            major_real_no_loss,
            "run_major_scenario_real_no_loss",
            _fake_runner,
        ):
            code = major_real_no_loss.main(
                [
                    "--json",
                    "--run-wechat-native-bridge-fixture-smoke",
                    "--wechat-native-bridge-fixture-message",
                    "OPENWUKONG_WECHAT_FIXTURE",
                    "--wechat-native-bridge-fixture-acceptance-marker",
                    "WECHAT: PASS",
                    "--wechat-native-bridge-fixture-forbid-marker",
                    "WECHAT: FAIL",
                ]
            )

        self.assertEqual(code, 0)
        self.assertTrue(calls[0]["run_wechat_native_bridge_fixture_smoke"])
        self.assertEqual(
            calls[0]["wechat_native_bridge_fixture_message"],
            "OPENWUKONG_WECHAT_FIXTURE",
        )
        self.assertEqual(
            calls[0]["wechat_native_bridge_fixture_required_markers"],
            ("WECHAT: PASS",),
        )
        self.assertEqual(
            calls[0]["wechat_native_bridge_fixture_forbidden_markers"],
            ("WECHAT: FAIL",),
        )

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

    def test_runner_passes_wechat_native_bridge_registry_paths_to_primary_runner(self):
        primary_calls = []

        def _primary_runner(fixture, **kwargs):
            primary_calls.append({"fixture": fixture, "kwargs": dict(kwargs)})
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
            registry_path = Path(tmp) / "wechat-native-bridges.json"
            report = run_major_scenario_real_no_loss(
                fixture={"suite": "fake-major"},
                output_root=tmp,
                agent_apps=(),
                cli_agents=(),
                wechat_native_bridge_registry_paths=(registry_path,),
                primary_runner=_primary_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(
            primary_calls[0]["kwargs"]["wechat_native_bridge_registry_paths"],
            (registry_path,),
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)

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

    def test_runner_probes_existing_ide_extension_bridge_and_forwards_ready_endpoint(self):
        app_calls = []
        readiness_calls = []

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

        def _ide_extension_readiness_runner(**kwargs):
            readiness_calls.append(dict(kwargs))
            return _FakeReport(
                {
                    "mode": "ide-extension-bridge-readiness",
                    "safety_mode": "read_only",
                    "status": "ready",
                    "blocking_reason": "",
                    "bridge_url": "http://127.0.0.1:8787",
                    "agent_id": "cursor",
                    "bridge_ready": True,
                    "can_write_without_focus": True,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
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
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
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
                agent_apps=("cursor",),
                cli_agents=(),
                project_name="openwukong",
                workspace_path="E:/ideaProjects/agent/openwukong",
                probe_existing_ide_extension_bridge=True,
                ide_extension_bridge_url="http://127.0.0.1:8787",
                ide_extension_agent_id="cursor",
                ide_extension_request_timeout_sec=0.25,
                primary_runner=_primary_runner,
                ide_extension_readiness_runner=_ide_extension_readiness_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()
            artifact = json.loads(Path(data["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(readiness_calls[0]["bridge_url"], "http://127.0.0.1:8787")
        self.assertEqual(readiness_calls[0]["agent_id"], "cursor")
        self.assertEqual(
            readiness_calls[0]["workspace_path"],
            "E:/ideaProjects/agent/openwukong",
        )
        self.assertEqual(app_calls[0]["ide_bridge_urls"], ("http://127.0.0.1:8787",))
        self.assertEqual(data["ide_extension_readiness"]["status"], "ready")
        self.assertEqual(
            artifact["subreports"]["ide_extension_readiness"]["bridge_url"],
            "http://127.0.0.1:8787",
        )

    def test_runner_records_unavailable_existing_ide_extension_bridge_without_forwarding(self):
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

        def _ide_extension_readiness_runner(**kwargs):
            del kwargs
            return _FakeReport(
                {
                    "mode": "ide-extension-bridge-readiness",
                    "safety_mode": "read_only",
                    "status": "bridge_unavailable",
                    "blocking_reason": "bridge_endpoint_unavailable",
                    "bridge_url": "http://127.0.0.1:8787",
                    "agent_id": "cursor",
                    "bridge_ready": False,
                    "control_attempts": 0,
                    "window_input_attempts": 0,
                    "bridge_send_attempts": 0,
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
                    "background_screenshot_count": 0,
                    "background_screenshot_success_count": 0,
                    "background_screenshot_focus_stable": True,
                    "passed_cases": 1,
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
                agent_apps=("cursor",),
                cli_agents=(),
                probe_existing_ide_extension_bridge=True,
                ide_extension_bridge_url="http://127.0.0.1:8787",
                primary_runner=_primary_runner,
                ide_extension_readiness_runner=_ide_extension_readiness_runner,
                agent_app_runner=_agent_app_runner,
                agent_cli_runner=_agent_cli_runner,
            )
            data = report.to_dict()

        self.assertEqual(app_calls[0]["ide_bridge_urls"], ())
        self.assertEqual(
            data["ide_extension_readiness"]["blocking_reason"],
            "bridge_endpoint_unavailable",
        )
        self.assertEqual(data["control_attempts"], 0)

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

    def test_prepare_owned_ide_bridge_helper_uses_dynamic_launch_readiness_url(self):
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
                            "readiness_url": "http://127.0.0.1:19641",
                        }
                    ],
                }
            )

        def _capture(bridge_url, **kwargs):
            calls["capture"].append({"bridge_url": bridge_url, "kwargs": dict(kwargs)})
            return _FakeReport(
                {
                    "mode": "ide-bridge-capability-capture",
                    "ok": True,
                    "bridge_url": bridge_url,
                    "active_mapping": {
                        "cursor": {
                            "available": len(calls["capture"]) > 1,
                            "commandId": "composer.startComposerPrompt"
                            if len(calls["capture"]) > 1
                            else "",
                            "commandCandidates": ["composer.startComposerPrompt"],
                        }
                    },
                    "adapter_mapping": {
                        "cursor": {
                            "available": len(calls["capture"]) > 1,
                            "commandId": "composer.startComposerPrompt"
                            if len(calls["capture"]) > 1
                            else "",
                            "commandCandidates": ["composer.startComposerPrompt"],
                        }
                    },
                    "cursor_review_candidates": ["composer.startComposerPrompt"],
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
                ide_bridge_port=0,
                adapter_id="cursor",
                plan_executor=_execute_plan,
                capability_capture=_capture,
                command_contract_probe=_probe,
                bridge_settings_builder=_settings_builder,
            )
            data = report.to_dict()
            settings = json.loads(Path(data["settings_path"]).read_text(encoding="utf-8"))

        self.assertTrue(data["ready"])
        self.assertEqual(data["bridge_url"], "http://127.0.0.1:19641")
        self.assertEqual(calls["capture"][0]["bridge_url"], "http://127.0.0.1:19641")
        self.assertEqual(calls["probe"][0]["bridge_url"], "http://127.0.0.1:19641")
        self.assertEqual(calls["settings"][0]["kwargs"]["port"], 0)
        self.assertEqual(
            calls["execute"][0]["plan"]["actions"][0]["settings_preview"][
                "openwukong.bridge.port"
            ],
            0,
        )
        self.assertEqual(data["pre_probe_settings"]["openwukong.bridge.port"], 0)
        self.assertEqual(settings["openwukong.bridge.port"], 0)


if __name__ == "__main__":
    unittest.main()
