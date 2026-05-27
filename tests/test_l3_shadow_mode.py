import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import openwukong.evaluation.shadow as shadow_module
from openwukong.evaluation.shadow import (
    L3ShadowHarness,
    StaticStateObserver,
    load_shadow_states,
    main,
)
from openwukong.evaluation.simulation import load_simulation_fixture
from openwukong.monitor.ai_monitor import AIProjectState, AIStatus


def _state(
    *,
    pid: int,
    process_name: str,
    project_name: str,
    window_title: str,
) -> AIProjectState:
    return AIProjectState(
        timestamp=1.0,
        pid=pid,
        process_name=process_name,
        project_name=project_name,
        window_title=window_title,
        ai_status=AIStatus.UNKNOWN,
        ai_model="",
        agent_enabled=False,
        progress_text="",
        progress_pct=-1.0,
        last_ai_output="",
        ai_element_count=0,
    )


class _SequenceObserver:
    def __init__(self, snapshots):
        self._snapshots = [tuple(snapshot) for snapshot in snapshots]
        self._last_snapshot = tuple()

    def snapshot(self):
        if self._snapshots:
            self._last_snapshot = self._snapshots.pop(0)
        return self._last_snapshot


class L3ShadowModeTests(unittest.TestCase):
    def test_shadow_run_generates_read_only_plan_from_observed_state(self):
        fixture = {
            "suite": "l3-shadow-smoke",
            "cases": [
                {
                    "case_id": "codex_shadow_route",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Shadow Codex",
                        "goal": "Plan a Codex steer without executing it",
                        "retry_command": "continue",
                        "connector_hint": "codex",
                    },
                    "expect": {
                        "matched_pid": 3101,
                        "connector_id": "codex",
                        "workspace_id_prefix": "workspace:openwukong",
                    },
                }
            ],
        }
        observer = StaticStateObserver([
            _state(
                pid=3101,
                process_name="Codex.exe",
                project_name="openwukong",
                window_title="openwukong - Codex",
            )
        ])

        report = L3ShadowHarness(observer=observer).run_suite(fixture)

        self.assertEqual(report.total_cases, 1)
        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(report.observed_state_count, 1)
        self.assertEqual(report.to_dict()["observed_states"][0]["pid"], 3101)
        self.assertEqual(report.to_dict()["observed_states"][0]["process_name"], "Codex.exe")
        plan = report.plans[0]
        self.assertEqual(plan.case_id, "codex_shadow_route")
        self.assertEqual(plan.connector_id, "codex")
        self.assertEqual(plan.matched_pid, 3101)
        self.assertEqual(plan.safety_decision, "observe_only")
        self.assertEqual(plan.proposed_action, "shadow_send_message")
        self.assertEqual(plan.risks, ())

    def test_shadow_run_reports_unverifiable_cases_without_control(self):
        fixture = {
            "suite": "l3-shadow-risk",
            "cases": [
                {
                    "case_id": "missing_shadow_route",
                    "goal": {
                        "window_match": "missing-project",
                        "task_name": "Missing target",
                        "goal": "Plan should stay blocked when no target is visible",
                        "retry_command": "continue",
                        "connector_hint": "codex",
                    },
                    "expect": {
                        "matched_pid": 4101,
                        "connector_id": "codex",
                    },
                }
            ],
        }

        report = L3ShadowHarness(observer=StaticStateObserver([])).run_suite(fixture)

        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(report.failed_cases, 1)
        self.assertEqual(report.unverifiable_cases, ("missing_shadow_route",))
        plan = report.plans[0]
        self.assertIn("unverifiable", plan.risks)
        self.assertEqual(plan.safety_decision, "block_unverifiable")

    def test_shadow_plan_embeds_route_policy_and_blocks_unsafe_targets(self):
        fixture = {
            "suite": "l3-shadow-route-policy",
            "cases": [
                {
                    "case_id": "weixin_shadow_route_policy",
                    "goal": {
                        "window_match": "微信",
                        "task_name": "Weixin route policy",
                        "goal": "Do not control an app without a deterministic route.",
                        "retry_command": "continue",
                        "connector_hint": "auto",
                    },
                    "expect": {
                        "matched_pid": 58756,
                    },
                }
            ],
        }
        observer = StaticStateObserver([
            _state(
                pid=58756,
                process_name="Weixin.exe",
                project_name="微信",
                window_title="微信",
            )
        ])

        report = L3ShadowHarness(observer=observer).run_suite(fixture)
        data = report.to_dict()
        plan = data["plans"][0]

        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(plan["app_family"], "im")
        self.assertEqual(plan["primary_route_id"], "app-native-bridge-required")
        self.assertEqual(plan["route_control_decision"], "block_until_deterministic_route")
        self.assertIn("route_policy_blocked", plan["risks"])
        self.assertEqual(plan["safety_decision"], "block_route_policy")

    def test_goal_profile_ignores_synthetic_pid_when_route_confidence_is_high(self):
        fixture = {
            "suite": "l3-shadow-goal-profile",
            "cases": [
                {
                    "case_id": "codex_goal_profile",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Goal profile Codex",
                        "goal": "Judge live shadow by connector and confidence, not a recorded PID.",
                        "retry_command": "continue",
                        "connector_hint": "codex",
                    },
                    "expect": {
                        "matched_pid": 9999,
                        "connector_id": "codex",
                        "workspace_id_prefix": "workspace:openwukong",
                    },
                }
            ],
        }
        observer = StaticStateObserver([
            _state(
                pid=3101,
                process_name="Codex.exe",
                project_name="openwukong",
                window_title="openwukong - Codex",
            )
        ])

        report = L3ShadowHarness(
            observer=observer,
            expectation_profile="goal",
        ).run_suite(fixture)

        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.failed_cases, 0)
        data = report.to_dict()
        self.assertEqual(data["expectation_profile"], "goal")
        self.assertIn("matched_pid", data["plans"][0]["ignored_expectations"])
        self.assertEqual(data["plans"][0]["risks"], [])

    def test_goal_profile_requires_confidence_for_visible_targets(self):
        fixture = {
            "suite": "l3-shadow-goal-profile",
            "cases": [
                {
                    "case_id": "codex_goal_profile_low_confidence",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Missing live Codex target",
                        "goal": "Low-confidence live matches should stay blocked.",
                        "retry_command": "continue",
                        "connector_hint": "codex",
                    },
                    "expect": {
                        "matched_pid": 9999,
                        "connector_id": "codex",
                    },
                }
            ],
        }

        report = L3ShadowHarness(
            observer=StaticStateObserver([]),
            expectation_profile="goal",
        ).run_suite(fixture)

        self.assertEqual(report.failed_cases, 1)
        self.assertEqual(report.low_confidence_cases, ("codex_goal_profile_low_confidence",))
        self.assertIn("low_confidence", report.plans[0].risks)
        self.assertEqual(report.plans[0].safety_decision, "block_low_confidence")

    def test_cli_can_run_shadow_mode_with_recorded_state_file(self):
        fixture = {
            "suite": "l3-shadow-cli",
            "cases": [
                {
                    "case_id": "terminal_shadow",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal shadow",
                        "goal": "Plan terminal action without executing command",
                        "retry_command": "git status",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        states = {"states": []}

        with tempfile.TemporaryDirectory() as td:
            fixture_path = Path(td) / "fixture.json"
            states_path = Path(td) / "states.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            states_path.write_text(json.dumps(states), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    str(fixture_path),
                    "--states",
                    str(states_path),
                    "--profile",
                    "goal",
                    "--json",
                ])

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["mode"], "l3-shadow")
        self.assertEqual(data["expectation_profile"], "goal")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["observed_states"], [])
        self.assertEqual(data["plans"][0]["connector_id"], "terminal")

    def test_dedicated_l3_goal_fixture_replays_without_exact_pid_expectations(self):
        fixture_path = Path("tests/fixtures/evaluation/l3_goal_current_desktop_20260518.json")
        fixture = load_simulation_fixture(fixture_path)
        states = load_shadow_states(fixture_path)

        for raw_case in fixture["cases"]:
            expectation = raw_case.get("expect", {})
            self.assertNotIn("matched_pid", expectation)
            self.assertNotIn("forbidden_matched_pid", expectation)
            self.assertNotIn("matched_window_title", expectation)

        report = L3ShadowHarness(
            observer=StaticStateObserver(states),
            expectation_profile="goal",
        ).run_suite(fixture)

        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(
            [plan.connector_id for plan in report.plans],
            ["codex", "browser", "cursor", "cursor", "uia-ide"],
        )

    def test_bridge_present_l3_fixture_plans_ide_extension_route_without_control(self):
        fixture_path = Path("tests/fixtures/evaluation/l3_ide_extension_bridge_present.json")
        fixture = load_simulation_fixture(fixture_path)
        states = load_shadow_states(fixture_path)

        for raw_case in fixture["cases"]:
            expectation = raw_case.get("expect", {})
            self.assertNotIn("matched_pid", expectation)
            self.assertNotIn("forbidden_matched_pid", expectation)
            self.assertNotIn("matched_window_title", expectation)

        report = L3ShadowHarness(
            observer=StaticStateObserver(states),
            expectation_profile="goal",
        ).run_suite(fixture)

        self.assertEqual(report.total_cases, 3)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.control_attempts, 0)
        for plan in report.plans:
            self.assertEqual(plan.connector_id, "ide-extension")
            self.assertEqual(plan.app_family, "ide")
            self.assertEqual(plan.primary_route_id, "ide-extension-connector")
            self.assertEqual(plan.route_control_decision, "prefer_deterministic_connector")
            self.assertEqual(plan.proposed_action, "shadow_send_message")
            self.assertEqual(plan.safety_decision, "observe_only")

    def test_builds_l3_shadow_trend_report_from_repeated_reports(self):
        self.assertTrue(hasattr(shadow_module, "build_shadow_trend_report"))
        fixture = {
            "suite": "l3-shadow-trend",
            "cases": [
                {
                    "case_id": "codex_shadow_stability",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Trend Codex",
                        "goal": "Track repeated shadow-route stability.",
                        "retry_command": "continue",
                        "connector_hint": "codex",
                    },
                    "expect": {
                        "connector_id": "codex",
                        "workspace_id_prefix": "workspace:openwukong",
                    },
                }
            ],
        }
        observer = StaticStateObserver([
            _state(
                pid=3101,
                process_name="Codex.exe",
                project_name="openwukong",
                window_title="openwukong - Codex",
            )
        ])
        harness = L3ShadowHarness(observer=observer, expectation_profile="goal")

        trend = shadow_module.build_shadow_trend_report([
            harness.run_suite(fixture),
            harness.run_suite(fixture),
        ])

        data = trend.to_dict()
        self.assertEqual(data["mode"], "l3-shadow-trend")
        self.assertEqual(data["expectation_profile"], "goal")
        self.assertEqual(data["run_count"], 2)
        self.assertEqual(data["total_cases"], 2)
        self.assertEqual(data["passed_cases"], 2)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["observed_state_counts"], [1, 1])
        self.assertEqual(data["connectors"]["codex"]["runs"], 2)
        self.assertEqual(data["unstable_cases"], [])

    def test_l3_shadow_trend_reports_connector_and_window_drift(self):
        self.assertTrue(hasattr(shadow_module, "build_shadow_trend_report"))
        fixture = {
            "suite": "l3-shadow-drift",
            "cases": [
                {
                    "case_id": "openwukong_ide_drift",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Drift target",
                        "goal": "Detect when the same goal routes to different apps.",
                        "retry_command": "continue",
                        "connector_hint": "auto",
                    },
                    "expect": {
                        "min_match_score": 70,
                    },
                }
            ],
        }
        observer = _SequenceObserver([
            [
                _state(
                    pid=3101,
                    process_name="Codex.exe",
                    project_name="openwukong",
                    window_title="openwukong - Codex",
                )
            ],
            [
                _state(
                    pid=4201,
                    process_name="Cursor.exe",
                    project_name="openwukong",
                    window_title="openwukong - Cursor",
                )
            ],
        ])
        harness = L3ShadowHarness(observer=observer, expectation_profile="goal")

        trend = shadow_module.build_shadow_trend_report([
            harness.run_suite(fixture),
            harness.run_suite(fixture),
        ])

        data = trend.to_dict()
        self.assertEqual(data["run_count"], 2)
        unstable = data["unstable_cases"]
        self.assertEqual(len(unstable), 1)
        self.assertEqual(unstable[0]["case_id"], "openwukong_ide_drift")
        self.assertEqual(unstable[0]["connectors"], ["codex", "cursor"])
        self.assertIn("connector", unstable[0]["drift_dimensions"])
        self.assertIn("window", unstable[0]["drift_dimensions"])

    def test_cli_repeat_generates_l3_shadow_trend_report_without_control(self):
        fixture = {
            "suite": "l3-shadow-cli-repeat",
            "cases": [
                {
                    "case_id": "terminal_shadow_repeat",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal shadow repeat",
                        "goal": "Repeat terminal planning without executing command.",
                        "retry_command": "git status",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        states = {"states": []}

        with tempfile.TemporaryDirectory() as td:
            fixture_path = Path(td) / "fixture.json"
            states_path = Path(td) / "states.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            states_path.write_text(json.dumps(states), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    str(fixture_path),
                    "--states",
                    str(states_path),
                    "--profile",
                    "goal",
                    "--repeat",
                    "2",
                    "--json",
                ])

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["mode"], "l3-shadow-trend")
        self.assertEqual(data["run_count"], 2)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["observed_state_counts"], [0, 0])
        self.assertEqual(data["connectors"]["terminal"]["cases"], 2)

    def test_shadow_plan_embeds_structured_command_plan_without_control(self):
        fixture = {
            "suite": "l3-shadow-structured-command",
            "cases": [
                {
                    "case_id": "pytest_shadow_command_plan",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Shadow pytest command",
                        "goal": "Plan pytest without executing it.",
                        "retry_command": "do not parse this text",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                        "command_operation": "pytest.run",
                        "command_args": ["tests/test_command_planner.py"],
                    },
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                        "command_plan": {
                            "ok": True,
                            "operation": "pytest.run",
                            "argv_prefix": [sys.executable, "-m", "pytest"],
                        },
                    },
                }
            ],
        }

        report = L3ShadowHarness(
            observer=StaticStateObserver([]),
            expectation_profile="goal",
        ).run_suite(fixture)
        plan = report.to_dict()["plans"][0]

        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(plan["proposed_action"], "shadow_plan_command_intent")
        self.assertEqual(plan["safety_decision"], "observe_only")
        self.assertEqual(plan["command_plan"]["operation"], "pytest.run")
        self.assertEqual(plan["command_plan"]["control_attempts"], 0)

    def test_shadow_blocks_invalid_structured_command_plan(self):
        fixture = {
            "suite": "l3-shadow-structured-command",
            "cases": [
                {
                    "case_id": "invalid_npm_shadow_command_plan",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Invalid npm command",
                        "goal": "Plan should block before any control.",
                        "retry_command": "do not parse this text",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                        "command_operation": "npm.run",
                        "command_args": [],
                    },
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }

        report = L3ShadowHarness(
            observer=StaticStateObserver([]),
            expectation_profile="goal",
        ).run_suite(fixture)
        plan = report.to_dict()["plans"][0]

        self.assertEqual(report.failed_cases, 1)
        self.assertEqual(report.control_attempts, 0)
        self.assertIn("command_plan_invalid", plan["risks"])
        self.assertEqual(plan["safety_decision"], "block_command_plan")
        self.assertEqual(plan["command_plan"]["error"], "npm_script_required")

    def test_structured_command_fixture_replays_in_l3_shadow(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_structured_command_goals.json")
        fixture = load_simulation_fixture(fixture_path)

        report = L3ShadowHarness(
            observer=StaticStateObserver([]),
            expectation_profile="goal",
        ).run_suite(fixture)
        data = report.to_dict()

        self.assertEqual(report.total_cases, 3)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.control_attempts, 0)
        self.assertTrue(all(plan["proposed_action"] == "shadow_plan_command_intent" for plan in data["plans"]))
        self.assertEqual(
            [plan["command_plan"]["operation"] for plan in data["plans"]],
            ["pytest.run", "npm.run", "docker.compose.dry-run-up"],
        )

    def test_broker_managed_process_fixture_replays_in_l3_shadow(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_broker_managed_process_lifecycle.json")
        fixture = load_simulation_fixture(fixture_path)

        report = L3ShadowHarness(
            observer=StaticStateObserver([]),
            expectation_profile="goal",
        ).run_suite(fixture)
        data = report.to_dict()
        plan = data["plans"][0]
        registry = plan["session_registry"]

        self.assertEqual(report.total_cases, 1)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(report.control_attempts, 0)
        self.assertEqual(plan["proposed_action"], "shadow_plan_command_process_start")
        self.assertEqual(plan["safety_decision"], "observe_only")
        self.assertEqual(plan["command_plan"]["control_attempts"], 0)
        self.assertEqual(registry["control_attempts"], 0)
        self.assertEqual(registry["session_count"], 1)
        self.assertEqual(registry["preferred_route_counts"], {"command-process-broker": 1})
        self.assertEqual(registry["sessions"][0]["session_id"], "command-process:proc-l1-http")


if __name__ == "__main__":
    unittest.main()
