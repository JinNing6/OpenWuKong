# -*- coding: utf-8 -*-

import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.control.command_process_broker import (
    CommandProcessBroker,
    CommandProcessBrokerConfig,
)
from openwukong.supervisor.agent_supervisor import AgentSupervisor, TaskGoal, load_goals


def _load_command_execution_module():
    module_name = "openwukong.supervisor.command_execution"
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise AssertionError(f"{module_name} is not importable")
    return importlib.import_module(module_name)


class SupervisorCommandExecutionTests(unittest.TestCase):
    def test_load_goals_preserves_structured_command_fields(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "goals.json"
            config_path.write_text(
                json.dumps(
                    {
                        "goals": [
                            {
                                "window_match": "openwukong-terminal",
                                "task_name": "structured command",
                                "goal": "run one structured command",
                                "success_keywords": ["ok"],
                                "failure_keywords": ["Traceback"],
                                "retry_command": "do not parse this as shell",
                                "connector_hint": "terminal",
                                "workspace_path": td,
                                "command_operation": "raw.argv",
                                "command_argv": [
                                    sys.executable,
                                    "-c",
                                    "print('supervisor-structured-command')",
                                ],
                                "command_effects": ["read"],
                                "command_profile": "read-only",
                                "command_run_mode": "long-running",
                                "command_process_storage_path": str(Path(td) / "processes.json"),
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            goal = load_goals(str(config_path))[0]

            self.assertEqual(goal.command_operation, "raw.argv")
            self.assertEqual(goal.command_argv[0], sys.executable)
            self.assertEqual(goal.command_effects, ["read"])
            self.assertEqual(goal.command_profile, "read-only")
            self.assertEqual(goal.command_run_mode, "long-running")
            self.assertEqual(goal.command_process_storage_path, str(Path(td) / "processes.json"))

    def test_supervisor_snapshot_exposes_structured_command_fields(self):
        goal = TaskGoal(
            window_match="openwukong-terminal",
            task_name="structured command",
            goal="run one structured command",
            success_keywords=[],
            failure_keywords=[],
            retry_command="do not parse this as shell",
            connector_hint="terminal",
            workspace_path=".",
            command_operation="raw.argv",
            command_argv=[sys.executable, "-c", "print('snapshot-command')"],
            command_effects=["read"],
            command_profile="read-only",
        )

        snapshot = AgentSupervisor([goal]).get_snapshot()
        first_goal = snapshot["goals"][0]

        self.assertEqual(first_goal["command_operation"], "raw.argv")
        self.assertEqual(first_goal["command_argv"][0], sys.executable)
        self.assertEqual(first_goal["command_effects"], ["read"])
        self.assertEqual(first_goal["command_profile"], "read-only")

    def test_supervisor_snapshot_exposes_long_running_command_fields(self):
        goal = TaskGoal(
            window_match="openwukong-terminal",
            task_name="background server",
            goal="run a managed background process",
            success_keywords=[],
            failure_keywords=[],
            retry_command="do not parse this as shell",
            connector_hint="terminal",
            workspace_path=".",
            command_operation="raw.argv",
            command_argv=[sys.executable, "-c", "import time; time.sleep(30)"],
            command_effects=["network"],
            command_profile="network-enabled",
            command_run_mode="long-running",
            command_process_storage_path="logs/runtime/processes.json",
        )

        snapshot = AgentSupervisor([goal]).get_snapshot()
        first_goal = snapshot["goals"][0]

        self.assertEqual(first_goal["command_run_mode"], "long-running")
        self.assertEqual(
            first_goal["command_process_storage_path"],
            "logs/runtime/processes.json",
        )

    def test_executor_plans_structured_goal_without_control_attempts(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="structured command",
                goal="run one structured command",
                success_keywords=[],
                failure_keywords=[],
                retry_command="do not parse this as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[sys.executable, "-c", "print('plan-command')"],
                command_effects=["read"],
                command_profile="read-only",
            )

            report = module.SupervisorCommandExecutor().plan_goal(goal)
            data = report.to_dict()

            self.assertTrue(data["ok"])
            self.assertEqual(data["mode"], "command-intelligence-plan")
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["argv"][:2], [sys.executable, "-c"])
            self.assertEqual(data["profile_id"], "read-only")

    def test_executor_blocks_without_explicit_control(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="structured command",
                goal="run one structured command",
                success_keywords=[],
                failure_keywords=[],
                retry_command="do not parse this as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[sys.executable, "-c", "print('blocked-command')"],
                command_effects=["read"],
                command_profile="read-only",
            )

            report = module.SupervisorCommandExecutor().execute_goal(goal)
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "explicit_control_permission_required")
            self.assertEqual(data["control_attempts"], 0)

    def test_executor_runs_structured_goal_with_explicit_control(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="structured command",
                goal="run one structured command",
                success_keywords=[],
                failure_keywords=[],
                retry_command="do not parse this as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[
                    sys.executable,
                    "-c",
                    "print('supervisor-executed-command')",
                ],
                command_effects=["read"],
                command_profile="read-only",
            )

            report = module.SupervisorCommandExecutor().execute_goal(
                goal,
                allow_control=True,
            )
            data = report.to_dict()

            self.assertTrue(data["ok"])
            self.assertEqual(data["decision"], "executed")
            self.assertEqual(data["control_attempts"], 1)
            self.assertIn(
                "supervisor-executed-command",
                data["action_report"]["stdout"],
            )

    def test_executor_rejects_retry_command_shell_string(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="unstructured command",
                goal="should not run shell text",
                success_keywords=[],
                failure_keywords=[],
                retry_command=f"{sys.executable} -c \"print('must-not-run')\"",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="",
                command_argv=[],
            )

            report = module.SupervisorCommandExecutor().execute_goal(
                goal,
                allow_control=True,
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "empty_argv")
            self.assertEqual(data["control_attempts"], 0)

    def test_executor_starts_long_running_goal_through_process_broker(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="background server",
                goal="run a managed background process",
                success_keywords=[],
                failure_keywords=[],
                retry_command="do not parse this as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[
                    sys.executable,
                    "-c",
                    "import time; time.sleep(30)",
                ],
                command_effects=["network"],
                command_profile="network-enabled",
                command_run_mode="long-running",
                command_process_storage_path=str(storage_path),
            )

            report = module.SupervisorCommandExecutor().start_process_goal(
                goal,
                allow_control=True,
            )
            data = report.to_dict()
            try:
                self.assertTrue(data["ok"], data["error"])
                self.assertEqual(data["mode"], "supervisor-command-process-start")
                self.assertEqual(data["decision"], "started_process")
                self.assertEqual(data["control_attempts"], 1)
                self.assertTrue(data["process_id"])
                self.assertEqual(data["command_plan"]["profile_id"], "network-enabled")
                self.assertEqual(data["broker_report"]["mode"], "command-process-broker-start")
                self.assertEqual(data["broker_snapshot"]["active_count"], 1)
                self.assertEqual(
                    data["broker_snapshot"]["processes"][0]["effects"],
                    ["network"],
                )
            finally:
                cleanup = CommandProcessBroker(
                    CommandProcessBrokerConfig(
                        workspace_root=td,
                        storage_path=str(storage_path),
                    )
                )
                cleanup.stop(data.get("process_id", ""), allow_control=True)

    def test_executor_blocks_long_running_goal_without_explicit_control(self):
        module = _load_command_execution_module()
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="background server",
                goal="run a managed background process",
                success_keywords=[],
                failure_keywords=[],
                retry_command="do not parse this as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[sys.executable, "-c", "import time; time.sleep(30)"],
                command_effects=["network"],
                command_profile="network-enabled",
                command_run_mode="long-running",
                command_process_storage_path=str(storage_path),
            )

            report = module.SupervisorCommandExecutor().start_process_goal(goal)
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["decision"], "blocked")
            self.assertEqual(data["error"], "explicit_control_permission_required")
            self.assertEqual(data["control_attempts"], 0)
            self.assertFalse(storage_path.exists())

    def test_supervisor_steer_executes_structured_command_through_fabric(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "marker.txt"
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="structured command",
                goal="run one structured command",
                success_keywords=[],
                failure_keywords=[],
                retry_command="this text must not be parsed as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({str(marker)!r}).write_text('ok', encoding='utf-8')"
                    ),
                ],
                command_effects=["workspace_write"],
                command_profile="workspace-write",
            )
            supervisor = AgentSupervisor([goal])
            target = ConnectorTarget(
                process_name="powershell.exe",
                window_title="openwukong-terminal",
                workspace_path=td,
                workspace_hint="terminal",
            )

            supervisor._steer(goal, target, dry_run=False, steer_content=goal.retry_command)

            self.assertEqual(marker.read_text(encoding="utf-8"), "ok")
            self.assertEqual(goal.retry_count, 1)
            self.assertEqual(goal.status.value, "running")
            self.assertEqual(supervisor._recent_actions[-1].action_type, "execute_command_intent")

    def test_supervisor_steer_starts_long_running_command_through_broker(self):
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            goal = TaskGoal(
                window_match="openwukong-terminal",
                task_name="background server",
                goal="run a managed background process",
                success_keywords=[],
                failure_keywords=[],
                retry_command="this text must not be parsed as shell",
                connector_hint="terminal",
                workspace_path=td,
                command_operation="raw.argv",
                command_argv=[
                    sys.executable,
                    "-c",
                    "import time; time.sleep(30)",
                ],
                command_effects=["network"],
                command_profile="network-enabled",
                command_run_mode="long-running",
                command_process_storage_path=str(storage_path),
            )
            supervisor = AgentSupervisor([goal])
            target = ConnectorTarget(
                process_name="powershell.exe",
                window_title="openwukong-terminal",
                workspace_path=td,
                workspace_hint="terminal",
            )

            supervisor._steer(goal, target, dry_run=False, steer_content=goal.retry_command)
            process_id = goal.active_session_id.removeprefix("command-process:")
            try:
                snapshot = CommandProcessBroker(
                    CommandProcessBrokerConfig(
                        workspace_root=td,
                        storage_path=str(storage_path),
                    )
                ).snapshot()

                self.assertEqual(snapshot["active_count"], 1)
                self.assertEqual(snapshot["processes"][0]["process_id"], process_id)
                self.assertEqual(goal.retry_count, 1)
                self.assertEqual(goal.status.value, "running")
                self.assertEqual(supervisor._recent_actions[-1].action_type, "start_command_process")
            finally:
                cleanup = CommandProcessBroker(
                    CommandProcessBrokerConfig(
                        workspace_root=td,
                        storage_path=str(storage_path),
                    )
                )
                cleanup.stop(process_id, allow_control=True)


if __name__ == "__main__":
    unittest.main()
