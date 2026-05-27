import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

from openwukong.control.command_planner import (
    CommandPlanIntent,
    CommandPlanner,
    plan_command_intent,
)
from openwukong.control.command_runner import CommandRunner
from openwukong.evaluation.command_intelligence_plan import main


class CommandPlannerTests(unittest.TestCase):
    def test_exports_command_planner_api_from_control_package(self):
        from openwukong.control import (
            CommandPlanIntent as ExportedIntent,
            CommandPlanner as ExportedPlanner,
            plan_command_intent as exported_plan,
        )

        self.assertIs(ExportedIntent, CommandPlanIntent)
        self.assertIs(ExportedPlanner, CommandPlanner)
        self.assertIs(exported_plan, plan_command_intent)

    def test_planner_maps_git_status_to_read_only_argv(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="git.status",
                    workspace_root=td,
                    reason="inspect workspace git state",
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(data["mode"], "command-intelligence-plan")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["operation"], "git.status")
            self.assertEqual(data["argv"], ["git", "status", "--short"])
            self.assertEqual(data["cwd"], td)
            self.assertEqual(data["effects"], ["read"])
            self.assertEqual(data["profile_id"], "read-only")
            self.assertEqual(data["policy"]["allowed_effects"], ["read"])
            self.assertEqual(report.execution_request.reason, "inspect workspace git state")

    def test_planner_rejects_shell_command_string_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent.from_dict(
                    {
                        "operation": "raw.argv",
                        "workspace_root": td,
                        "command": "git status && git diff",
                    }
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "shell_command_not_allowed")
            self.assertEqual(data["argv"], [])
            self.assertEqual(data["control_attempts"], 0)

    def test_planner_rejects_raw_argv_shell_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=("powershell.exe", "-Command", "Write-Output unsafe"),
                    effects=("read",),
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "shell_launcher_not_allowed:powershell.exe")
            self.assertEqual(data["control_attempts"], 0)

    def test_planner_selects_least_privilege_profiles_from_effects(self):
        with tempfile.TemporaryDirectory() as td:
            write_report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('write')"),
                    effects=("workspace_write",),
                )
            )
            network_report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('network')"),
                    effects=("network",),
                )
            )

            self.assertTrue(write_report.ok, write_report.error)
            self.assertEqual(write_report.policy.profile_id, "workspace-write")
            self.assertTrue(network_report.ok, network_report.error)
            self.assertEqual(network_report.policy.profile_id, "network-enabled")

    def test_planned_command_executes_through_runner_without_shell(self):
        with tempfile.TemporaryDirectory() as td:
            report = plan_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('planned-runner')"),
                    effects=("read",),
                )
            )

            execution = CommandRunner(report.policy).execute(report.execution_request)
            data = execution.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertFalse(data["shell"])
            self.assertIn("planned-runner", data["stdout"])

    def test_cli_outputs_json_plan_from_structured_intent(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--intent-json",
                        json.dumps(
                            {
                                "operation": "git.status",
                                "workspace_root": td,
                                "reason": "cli plan",
                            }
                        ),
                        "--json",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["mode"], "command-intelligence-plan")
        self.assertEqual(data["argv"], ["git", "status", "--short"])
        self.assertEqual(data["profile_id"], "read-only")

    def test_planner_maps_pytest_run_to_python_module_pytest(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="pytest.run",
                    workspace_root=td,
                    args=("tests/test_command_planner.py", "-k", "CommandPlanner"),
                    reason="run focused pytest selection",
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(
                data["argv"],
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_command_planner.py",
                    "-k",
                    "CommandPlanner",
                ],
            )
            self.assertEqual(data["effects"], ["workspace_write"])
            self.assertEqual(data["profile_id"], "workspace-write")

    def test_planner_maps_npm_run_to_platform_command_and_script_args(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="npm.run",
                    workspace_root=td,
                    args=("test", "--grep=planner"),
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(
                data["argv"],
                [_platform_command("npm"), "run", "test", "--", "--grep=planner"],
            )
            self.assertEqual(data["effects"], ["workspace_write"])
            self.assertEqual(data["profile_id"], "workspace-write")

    def test_planner_rejects_npm_run_without_script_name(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="npm.run",
                    workspace_root=td,
                    args=(),
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "npm_script_required")
            self.assertEqual(data["control_attempts"], 0)

    def test_planner_maps_uv_run_to_workspace_write_command(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="uv.run",
                    workspace_root=td,
                    args=("python", "-m", "pytest", "tests"),
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(
                data["argv"],
                [_platform_command("uv"), "run", "python", "-m", "pytest", "tests"],
            )
            self.assertEqual(data["effects"], ["workspace_write"])
            self.assertEqual(data["profile_id"], "workspace-write")

    def test_planner_rejects_wrapped_uv_shell_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="uv.run",
                    workspace_root=td,
                    args=("powershell.exe", "-Command", "Write-Output unsafe"),
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "shell_launcher_not_allowed:powershell.exe")
            self.assertEqual(data["control_attempts"], 0)

    def test_planner_maps_docker_compose_read_only_operations(self):
        with tempfile.TemporaryDirectory() as td:
            ps_report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="docker.compose.ps",
                    workspace_root=td,
                    args=("--all",),
                )
            )
            logs_report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="docker.compose.logs",
                    workspace_root=td,
                    args=("--tail", "20"),
                )
            )

            self.assertEqual(
                ps_report.to_dict()["argv"],
                ["docker", "compose", "ps", "--all"],
            )
            self.assertEqual(ps_report.to_dict()["effects"], ["read"])
            self.assertEqual(ps_report.to_dict()["profile_id"], "read-only")
            self.assertEqual(
                logs_report.to_dict()["argv"],
                ["docker", "compose", "logs", "--tail", "20"],
            )
            self.assertEqual(logs_report.to_dict()["effects"], ["read"])

    def test_planner_maps_docker_compose_dry_run_up_to_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="docker.compose.dry-run-up",
                    workspace_root=td,
                    args=("--build", "-d"),
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(
                data["argv"],
                ["docker", "compose", "--dry-run", "up", "--build", "-d"],
            )
            self.assertEqual(data["effects"], ["read"])
            self.assertEqual(data["profile_id"], "read-only")

    def test_planner_maps_docker_compose_up_to_network_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            report = CommandPlanner().plan(
                CommandPlanIntent(
                    operation="docker.compose.up",
                    workspace_root=td,
                    args=("--build", "--detach", "web"),
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(
                data["argv"],
                ["docker", "compose", "up", "--build", "--detach", "web"],
            )
            self.assertEqual(data["effects"], ["network"])
            self.assertEqual(data["profile_id"], "network-enabled")


def _platform_command(name: str) -> str:
    return f"{name}.cmd" if os.name == "nt" else name


if __name__ == "__main__":
    unittest.main()
