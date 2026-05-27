import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.simulation import (
    L1SimulationHarness,
    build_trend_report,
    main,
    load_simulation_fixture,
)


class L1SimulationHarnessTests(unittest.TestCase):
    def test_routes_codex_goal_from_recorded_window_states(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "codex_route_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Send Codex instruction",
                        "goal": "Send a deterministic instruction to Codex",
                        "retry_command": "echo ok",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 101,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        },
                        {
                            "pid": 202,
                            "process_name": "Cursor.exe",
                            "project_name": "otherrepo",
                            "window_title": "main.py - otherrepo - Cursor",
                        },
                    ],
                    "expect": {
                        "matched_pid": 101,
                        "connector_id": "codex",
                        "workspace_id_prefix": "workspace:openwukong",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.total_cases, 1)
        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.pass_rate, 1.0)
        result = report.results[0]
        self.assertTrue(result.passed)
        self.assertEqual(result.matched_pid, 101)
        self.assertEqual(result.connector_id, "codex")
        self.assertTrue(result.workspace_id.startswith("workspace:openwukong"))

    def test_marks_failed_expectations_without_touching_live_apps(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "wrong_expectation_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Wrong connector expectation",
                        "goal": "Route to Codex",
                        "retry_command": "echo ok",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 303,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        },
                    ],
                    "expect": {
                        "matched_pid": 303,
                        "connector_id": "cursor",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.failed_cases, 1)
        self.assertFalse(report.results[0].passed)
        self.assertIn("connector_id", report.results[0].errors[0])

    def test_browser_goal_matches_recorded_browser_state_when_present(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "browser_route_001",
                    "goal": {
                        "window_match": "local-browser-fixture",
                        "task_name": "Browser route",
                        "goal": "Route to recorded Chrome window",
                        "retry_command": "GET /",
                        "connector_hint": "browser",
                        "resource_url": "http://127.0.0.1:8765/",
                    },
                    "states": [
                        {
                            "pid": 404,
                            "process_name": "chrome.exe",
                            "project_name": "local-browser-fixture",
                            "window_title": "local-browser-fixture - Google Chrome",
                        }
                    ],
                    "expect": {
                        "matched_pid": 404,
                        "connector_id": "browser",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.results[0].matched_pid, 404)

    def test_expected_no_match_does_not_fail_connector_resolution(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "no_match_001",
                    "goal": {
                        "window_match": "missing-project",
                        "task_name": "No match expected",
                        "goal": "Confirm unmatched goals stay unmatched",
                        "retry_command": "status",
                        "connector_hint": "auto",
                    },
                    "states": [
                        {
                            "pid": 505,
                            "process_name": "Cursor.exe",
                            "project_name": "other-project",
                            "window_title": "main.py - other-project - Cursor",
                        }
                    ],
                    "expect": {
                        "matched": False,
                        "connector_id": "",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.results[0].matched_pid, 0)
        self.assertEqual(report.results[0].connector_id, "")

    def test_min_match_score_expectation_flags_weak_matches(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "weak_match_001",
                    "goal": {
                        "window_match": "open-wu-kong",
                        "task_name": "Weak fuzzy match",
                        "goal": "Require a high confidence match",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 606,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 606,
                        "connector_id": "codex",
                        "min_match_score": 95,
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.failed_cases, 1)
        self.assertIn("min_match_score", report.results[0].errors[0])

    def test_forbidden_matched_pid_flags_wrong_target(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "wrong_target_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Wrong target guard",
                        "goal": "Detect a forbidden matched target",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 707,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "forbidden_matched_pid": 707,
                        "connector_id": "codex",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.failed_cases, 1)
        self.assertIn("forbidden_matched_pid", report.results[0].errors[0])
        self.assertEqual(report.to_dict()["wrong_target_cases"], ["wrong_target_001"])

    def test_report_summarizes_connector_confusion_and_low_score_cases(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "connector_confusion_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Connector confusion",
                        "goal": "Show expected cursor but actual codex",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 808,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 808,
                        "connector_id": "cursor",
                    },
                },
                {
                    "case_id": "low_score_001",
                    "goal": {
                        "window_match": "open-wu-kong",
                        "task_name": "Low score summary",
                        "goal": "Collect weak match into summary",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 809,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 809,
                        "connector_id": "codex",
                        "min_match_score": 95,
                    },
                },
            ],
        }

        report_data = L1SimulationHarness().run_suite(fixture).to_dict()

        self.assertEqual(report_data["connector_confusion"]["cursor"]["codex"], 1)
        self.assertEqual(report_data["low_score_cases"][0]["case_id"], "low_score_001")
        self.assertIn("match_score", report_data["low_score_cases"][0])

    def test_report_summarizes_route_quality_by_connector(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "codex_quality_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Codex quality",
                        "goal": "Measure codex route quality",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 901,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 901,
                        "connector_id": "codex",
                    },
                },
                {
                    "case_id": "terminal_quality_001",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal quality",
                        "goal": "Measure terminal route quality",
                        "retry_command": "echo ok",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                },
            ],
        }

        route_quality = L1SimulationHarness().run_suite(fixture).to_dict()["route_quality"]

        self.assertEqual(route_quality["codex"]["cases"], 1)
        self.assertGreaterEqual(route_quality["codex"]["min_match_score"], 900)
        self.assertEqual(route_quality["terminal"]["cases"], 1)
        self.assertEqual(route_quality["terminal"]["min_match_score"], 1000)

    def test_direct_git_route_ignores_recorded_ide_windows(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "git_ignores_ide_state",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Git direct route",
                        "goal": "Plan git command without stealing an IDE window",
                        "retry_command": "git status",
                        "connector_hint": "git",
                        "workspace_path": ".",
                    },
                    "states": [
                        {
                            "pid": 902,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "git",
                        "min_match_score": 1000,
                    },
                }
            ],
        }

        result = L1SimulationHarness().run_suite(fixture).results[0]

        self.assertTrue(result.passed)
        self.assertEqual(result.matched_pid, 0)
        self.assertEqual(result.connector_id, "git")

    def test_direct_ide_extension_route_uses_bridge_without_live_window(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "ide_extension_direct_route",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "IDE bridge direct route",
                        "goal": "Plan IDE command through extension bridge",
                        "retry_command": "Continue implementation",
                        "connector_hint": "ide-extension",
                        "workspace_path": "E:\\ideaProjects\\agent\\openwukong",
                        "ide_bridge_url": "http://127.0.0.1:8787",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "ide-extension",
                        "min_match_score": 1000,
                    },
                }
            ],
        }

        result = L1SimulationHarness().run_suite(fixture).results[0]

        self.assertTrue(result.passed, result.errors)
        self.assertEqual(result.connector_id, "ide-extension")
        self.assertEqual(result.match_score, 1000)

    def test_bridge_present_l1_fixture_routes_ide_extension_without_live_window(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_ide_extension_bridge_present.json")
        fixture = load_simulation_fixture(fixture_path)

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.total_cases, 3)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(
            [result.connector_id for result in report.results],
            ["ide-extension", "ide-extension", "ide-extension"],
        )
        self.assertEqual(
            [result.matched_pid for result in report.results],
            [0, 0, 0],
        )
        self.assertEqual(report.route_quality()["ide-extension"]["min_match_score"], 1000)

    def test_explicit_workspace_path_disambiguates_same_name_states(self):
        fixture = {
            "suite": "developer-workstation-l1",
            "cases": [
                {
                    "case_id": "same_name_path_001",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Same name path route",
                        "goal": "Route to beta openwukong by explicit workspace path",
                        "retry_command": "status",
                        "connector_hint": "cursor",
                        "workspace_path": "E:\\fixtures\\beta\\openwukong",
                    },
                    "states": [
                        {
                            "pid": 1001,
                            "process_name": "Cursor.exe",
                            "project_name": "openwukong",
                            "window_title": "E:\\fixtures\\alpha\\openwukong\\src\\main.py - openwukong - Cursor",
                        },
                        {
                            "pid": 1002,
                            "process_name": "Cursor.exe",
                            "project_name": "openwukong",
                            "window_title": "E:\\fixtures\\beta\\openwukong\\src\\main.py - openwukong - Cursor",
                        },
                    ],
                    "expect": {
                        "matched_pid": 1002,
                        "forbidden_matched_pid": 1001,
                        "connector_id": "cursor",
                        "min_match_score": 1000,
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)

        self.assertEqual(report.passed_cases, 1)
        self.assertEqual(report.results[0].matched_pid, 1002)

    def test_builds_cross_run_trend_report(self):
        pass_fixture = {
            "suite": "run-a",
            "cases": [
                {
                    "case_id": "codex_pass",
                    "goal": {
                        "window_match": "openwukong",
                        "task_name": "Codex pass",
                        "goal": "Route to Codex",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 2001,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 2001,
                        "connector_id": "codex",
                    },
                }
            ],
        }
        fail_fixture = {
            "suite": "run-b",
            "cases": [
                {
                    "case_id": "codex_fail",
                    "goal": {
                        "window_match": "open-wu-kong",
                        "task_name": "Codex fail",
                        "goal": "Route to Codex with strict score",
                        "retry_command": "status",
                        "connector_hint": "codex",
                    },
                    "states": [
                        {
                            "pid": 2002,
                            "process_name": "Codex.exe",
                            "project_name": "openwukong",
                            "window_title": "openwukong - Codex",
                        }
                    ],
                    "expect": {
                        "matched_pid": 2002,
                        "connector_id": "codex",
                        "min_match_score": 95,
                    },
                }
            ],
        }
        harness = L1SimulationHarness()
        reports = [
            harness.run_suite(pass_fixture),
            harness.run_suite(fail_fixture),
        ]

        trend = build_trend_report(reports).to_dict()

        self.assertEqual(trend["run_count"], 2)
        self.assertEqual(trend["total_cases"], 2)
        self.assertEqual(trend["failed_cases"], 1)
        self.assertEqual(trend["connectors"]["codex"]["runs"], 2)
        self.assertEqual(trend["connectors"]["codex"]["cases"], 2)
        self.assertEqual(trend["connectors"]["codex"]["failed"], 1)
        self.assertLess(trend["connectors"]["codex"]["min_match_score"], 95)
        self.assertEqual(trend["regressions"][0]["case_id"], "codex_fail")

    def test_trend_counts_duplicate_suite_runs_separately(self):
        fixture = {
            "suite": "same-suite",
            "cases": [
                {
                    "case_id": "terminal_same_suite",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal same suite",
                        "goal": "Route terminal",
                        "retry_command": "echo ok",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        harness = L1SimulationHarness()
        trend = build_trend_report([
            harness.run_suite(fixture),
            harness.run_suite(fixture),
        ]).to_dict()

        self.assertEqual(trend["connectors"]["terminal"]["runs"], 2)
        self.assertEqual(trend["connectors"]["terminal"]["cases"], 2)

    def test_cli_trend_accepts_multiple_fixture_paths(self):
        fixture_a = {
            "suite": "run-a",
            "cases": [
                {
                    "case_id": "terminal_a",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal A",
                        "goal": "Route terminal A",
                        "retry_command": "echo a",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        fixture_b = {
            "suite": "run-b",
            "cases": [
                {
                    "case_id": "terminal_b",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Terminal B",
                        "goal": "Route terminal B",
                        "retry_command": "echo b",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path_a = Path(td) / "a.json"
            path_b = Path(td) / "b.json"
            path_a.write_text(json.dumps(fixture_a), encoding="utf-8")
            path_b.write_text(json.dumps(fixture_b), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--trend", str(path_a), str(path_b), "--json"])

        self.assertEqual(exit_code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["run_count"], 2)

    def test_loads_fixture_file_and_serializes_report(self):
        fixture = {
            "suite": "file-fixture",
            "cases": [
                {
                    "case_id": "terminal_route_001",
                    "goal": {
                        "window_match": "openwukong-terminal",
                        "task_name": "Run tests",
                        "goal": "Run unit tests in a managed terminal",
                        "retry_command": "python -m unittest",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            fixture_path = Path(td) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            loaded = load_simulation_fixture(fixture_path)
            report = L1SimulationHarness().run_suite(loaded)

        data = report.to_dict()
        self.assertEqual(data["suite"], "file-fixture")
        self.assertEqual(data["passed_cases"], 1)
        self.assertEqual(data["results"][0]["connector_id"], "terminal")

    def test_structured_command_goal_includes_plan_without_control(self):
        fixture = {
            "suite": "structured-command-l1",
            "cases": [
                {
                    "case_id": "pytest_structured_command",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Plan pytest",
                        "goal": "Plan a focused pytest run without executing it.",
                        "retry_command": "do not parse this text",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                        "command_operation": "pytest.run",
                        "command_args": ["tests/test_command_planner.py", "-k", "CommandPlanner"],
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                        "command_plan": {
                            "ok": True,
                            "operation": "pytest.run",
                            "profile_id": "workspace-write",
                            "effects": ["workspace_write"],
                            "argv_prefix": [sys.executable, "-m", "pytest"],
                        },
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)
        data = report.to_dict()
        command_plan = data["results"][0]["command_plan"]

        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(command_plan["control_attempts"], 0)
        self.assertEqual(command_plan["operation"], "pytest.run")
        self.assertEqual(command_plan["argv"][:3], [sys.executable, "-m", "pytest"])

    def test_structured_command_goal_flags_invalid_plan(self):
        fixture = {
            "suite": "structured-command-l1",
            "cases": [
                {
                    "case_id": "invalid_npm_structured_command",
                    "goal": {
                        "window_match": "terminal",
                        "task_name": "Invalid npm plan",
                        "goal": "Missing npm script should block planning.",
                        "retry_command": "do not parse this text",
                        "connector_hint": "terminal",
                        "workspace_path": ".",
                        "command_operation": "npm.run",
                        "command_args": [],
                    },
                    "states": [],
                    "expect": {
                        "matched_pid": 0,
                        "connector_id": "terminal",
                    },
                }
            ],
        }

        report = L1SimulationHarness().run_suite(fixture)
        data = report.to_dict()
        result = data["results"][0]

        self.assertEqual(report.failed_cases, 1)
        self.assertIn("command_plan", result["errors"][0])
        self.assertEqual(result["command_plan"]["error"], "npm_script_required")
        self.assertEqual(result["command_plan"]["control_attempts"], 0)

    def test_structured_command_l1_fixture_scores_command_plans(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_structured_command_goals.json")
        fixture = load_simulation_fixture(fixture_path)

        report = L1SimulationHarness().run_suite(fixture)
        data = report.to_dict()

        self.assertEqual(report.total_cases, 3)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(
            [result["command_plan"]["operation"] for result in data["results"]],
            ["pytest.run", "npm.run", "docker.compose.dry-run-up"],
        )
        self.assertTrue(all(result["command_plan"]["control_attempts"] == 0 for result in data["results"]))

    def test_broker_managed_process_fixture_exports_session_registry(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_broker_managed_process_lifecycle.json")
        fixture = load_simulation_fixture(fixture_path)

        report = L1SimulationHarness().run_suite(fixture)
        data = report.to_dict()
        result = data["results"][0]
        registry = result["session_registry"]

        self.assertEqual(report.total_cases, 1)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(result["command_plan"]["control_attempts"], 0)
        self.assertEqual(registry["control_attempts"], 0)
        self.assertEqual(registry["session_count"], 1)
        self.assertEqual(registry["app_family_counts"], {"managed-process": 1})
        self.assertEqual(
            registry["preferred_route_counts"],
            {"command-process-broker": 1},
        )
        self.assertEqual(registry["ownership_counts"], {"owned": 1, "unowned": 0})
        session = registry["sessions"][0]
        self.assertEqual(session["session_id"], "command-process:proc-l1-http")
        self.assertIn("command_process_broker", session["capability_ids"])
        self.assertIn("stop_process", session["action_ids"])


if __name__ == "__main__":
    unittest.main()
