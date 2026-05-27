import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from openwukong.control.command_runner import (
    CommandExecutionPolicy,
    CommandExecutionRequest,
    CommandProcessRegistry,
    CommandRunner,
    build_command_execution_policy,
)
from openwukong.control.session_ownership import SessionOwnership
from openwukong.evaluation.command_intelligence_execute import main


class CommandIntelligenceTests(unittest.TestCase):
    def test_exports_command_runner_api_from_control_package(self):
        from openwukong.control import (
            CommandExecutionPolicy as ExportedPolicy,
            CommandExecutionRequest as ExportedRequest,
            CommandProcessRegistry as ExportedProcessRegistry,
            CommandRunner as ExportedRunner,
            build_command_execution_policy as exported_build_policy,
        )

        self.assertIs(ExportedPolicy, CommandExecutionPolicy)
        self.assertIs(ExportedRequest, CommandExecutionRequest)
        self.assertIs(ExportedProcessRegistry, CommandProcessRegistry)
        self.assertIs(ExportedRunner, CommandRunner)
        self.assertIs(exported_build_policy, build_command_execution_policy)

    def test_runner_executes_argv_in_workspace_and_writes_audit_log(self):
        with tempfile.TemporaryDirectory() as td:
            audit_path = Path(td) / "audit.jsonl"
            runner = CommandRunner(
                CommandExecutionPolicy(
                    workspace_root=td,
                    audit_log_path=str(audit_path),
                    timeout_sec=5.0,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(
                        sys.executable,
                        "-c",
                        "import os; print(os.path.basename(os.getcwd()))",
                    ),
                    cwd=td,
                    reason="unit test workspace command",
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(data["mode"], "command-intelligence-execution")
            self.assertEqual(data["safety_mode"], "workspace_command_runner")
            self.assertEqual(data["control_attempts"], 1)
            self.assertEqual(data["exit_code"], 0)
            self.assertIn(os.path.basename(td), data["stdout"])
            self.assertFalse(data["shell"])
            self.assertTrue(audit_path.is_file())
            audit = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(audit["request"]["argv"][0], sys.executable)
            self.assertEqual(audit["result"]["exit_code"], 0)
            self.assertEqual(audit["result"]["error"], "")

    def test_runner_blocks_cwd_outside_workspace_before_process_start(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as outside:
            runner = CommandRunner(CommandExecutionPolicy(workspace_root=workspace))

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    cwd=outside,
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "cwd_outside_workspace")
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["stdout"], "")

    def test_read_only_profile_blocks_declared_workspace_write_before_process_start(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CommandRunner(
                build_command_execution_policy(
                    "read-only",
                    workspace_root=td,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    cwd=td,
                    effects=("workspace_write",),
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["profile_id"], "read-only")
            self.assertEqual(data["error"], "effect_not_allowed:workspace_write")
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["stdout"], "")

    def test_workspace_write_profile_allows_declared_workspace_write(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CommandRunner(
                build_command_execution_policy(
                    "workspace-write",
                    workspace_root=td,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('write-ok')"),
                    cwd=td,
                    effects=("workspace_write",),
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(data["profile_id"], "workspace-write")
            self.assertIn("write-ok", data["stdout"])

    def test_elevated_effect_is_forbidden_for_all_profiles(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CommandRunner(
                build_command_execution_policy(
                    "network-enabled",
                    workspace_root=td,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    cwd=td,
                    effects=("elevated",),
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["profile_id"], "network-enabled")
            self.assertEqual(data["error"], "effect_not_allowed:elevated")
            self.assertEqual(data["control_attempts"], 0)

    def test_runner_times_out_and_reports_process_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CommandRunner(
                CommandExecutionPolicy(workspace_root=td, timeout_sec=0.2)
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(5)"),
                    cwd=td,
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "timeout")
            self.assertTrue(data["timed_out"])
            self.assertEqual(data["control_attempts"], 1)

    def test_runner_blocks_unowned_session_when_ownership_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            runner = CommandRunner(
                CommandExecutionPolicy(
                    workspace_root=td,
                    require_owned_session=True,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    cwd=td,
                )
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "owned_session_required")
            self.assertTrue(data["ownership_required"])
            self.assertFalse(data["ownership"]["owned"])
            self.assertEqual(data["control_attempts"], 0)

    def test_runner_executes_owned_workspace_command_when_required(self):
        with tempfile.TemporaryDirectory() as td:
            ownership = _workspace_ownership(td)
            runner = CommandRunner(
                CommandExecutionPolicy(
                    workspace_root=td,
                    require_owned_session=True,
                )
            )

            report = runner.execute(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "print('owned-runner')"),
                    cwd=td,
                    ownership=ownership,
                )
            )
            data = report.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertTrue(data["ownership_required"])
            self.assertTrue(data["ownership"]["owned"])
            self.assertIn("owned-runner", data["stdout"])

    def test_cli_binds_readiness_manifest_ownership_before_command_execution(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = _write_workspace_manifest(Path(td) / "terminal.json", td)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--workspace-path",
                        td,
                        "--readiness-manifest",
                        str(manifest),
                        "--json",
                        "--",
                        sys.executable,
                        "-c",
                        "print('owned-cli')",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertIn("owned-cli", data["stdout"])

    def test_cli_profile_blocks_disallowed_effect_before_command_execution(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--workspace-path",
                        td,
                        "--profile",
                        "read-only",
                        "--effect",
                        "workspace_write",
                        "--json",
                        "--",
                        sys.executable,
                        "-c",
                        "print('must-not-run')",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["profile_id"], "read-only")
        self.assertEqual(data["error"], "effect_not_allowed:workspace_write")
        self.assertEqual(data["control_attempts"], 0)

    def test_cli_requires_owned_session_before_command_execution(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--workspace-path",
                        td,
                        "--require-owned-session",
                        "--json",
                        "--",
                        sys.executable,
                        "-c",
                        "print('must-not-run')",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "owned_session_required")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["stdout"], "")

    def test_process_registry_starts_tracks_and_stops_long_running_process(self):
        with tempfile.TemporaryDirectory() as td:
            registry = CommandProcessRegistry(
                build_command_execution_policy(
                    "workspace-write",
                    workspace_root=td,
                    timeout_sec=5.0,
                )
            )

            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                    effects=("read",),
                )
            )
            start_data = start.to_dict()

            self.assertTrue(start_data["ok"], start_data["error"])
            self.assertEqual(start_data["mode"], "command-intelligence-process-start")
            self.assertEqual(start_data["control_attempts"], 1)
            self.assertTrue(start_data["process_id"])
            self.assertGreater(start_data["pid"], 0)
            self.assertEqual(registry.snapshot()["active_count"], 1)

            stop = registry.stop(start.process_id, grace_seconds=1.0)
            stop_data = stop.to_dict()

            self.assertTrue(stop_data["ok"], stop_data["error"])
            self.assertEqual(stop_data["mode"], "command-intelligence-process-stop")
            self.assertEqual(stop_data["process_id"], start.process_id)
            self.assertEqual(stop_data["pid"], start.pid)
            self.assertEqual(stop_data["control_attempts"], 1)
            self.assertEqual(registry.snapshot()["active_count"], 0)

    def test_process_registry_blocks_unowned_start_before_process_start(self):
        with tempfile.TemporaryDirectory() as td:
            registry = CommandProcessRegistry(
                build_command_execution_policy(
                    "workspace-write",
                    workspace_root=td,
                    require_owned_session=True,
                )
            )

            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            data = start.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "owned_session_required")
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["pid"], 0)
            self.assertEqual(registry.snapshot()["active_count"], 0)

    def test_process_registry_writes_start_and_stop_audit_records(self):
        with tempfile.TemporaryDirectory() as td:
            audit_path = Path(td) / "process-audit.jsonl"
            registry = CommandProcessRegistry(
                build_command_execution_policy(
                    "workspace-write",
                    workspace_root=td,
                    audit_log_path=str(audit_path),
                )
            )

            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            stop = registry.stop(start.process_id)

            self.assertTrue(start.ok, start.error)
            self.assertTrue(stop.ok, stop.error)
            records = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [record["mode"] for record in records],
                [
                    "command-intelligence-process-start-audit-record",
                    "command-intelligence-process-stop-audit-record",
                ],
            )
            self.assertEqual(records[0]["result"]["process_id"], start.process_id)
            self.assertEqual(records[1]["result"]["process_id"], start.process_id)

    def test_process_registry_stop_all_cleans_multiple_processes(self):
        with tempfile.TemporaryDirectory() as td:
            registry = CommandProcessRegistry(
                build_command_execution_policy("workspace-write", workspace_root=td)
            )
            first = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            second = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )

            stop_reports = registry.stop_all(grace_seconds=1.0)

            self.assertEqual({report.process_id for report in stop_reports}, {first.process_id, second.process_id})
            self.assertTrue(all(report.ok for report in stop_reports))
            self.assertEqual(registry.snapshot()["active_count"], 0)

    def test_process_registry_persists_started_process_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "process-registry.json"
            registry = CommandProcessRegistry(
                build_command_execution_policy("workspace-write", workspace_root=td),
                storage_path=str(state_path),
            )
            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            try:
                self.assertTrue(start.ok, start.error)
                data = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(data["mode"], "command-intelligence-process-store")
                self.assertEqual(data["process_count"], 1)
                stored = data["processes"][0]
                self.assertEqual(stored["process_id"], start.process_id)
                self.assertEqual(stored["pid"], start.pid)
                self.assertEqual(stored["argv"][0], sys.executable)
                self.assertEqual(stored["cwd"], td)
            finally:
                registry.stop(start.process_id)

    def test_process_registry_restores_snapshot_from_persistent_storage(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "process-registry.json"
            registry = CommandProcessRegistry(
                build_command_execution_policy("workspace-write", workspace_root=td),
                storage_path=str(state_path),
            )
            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            try:
                restored = CommandProcessRegistry(
                    build_command_execution_policy("workspace-write", workspace_root=td),
                    storage_path=str(state_path),
                )
                snapshot = restored.snapshot()

                self.assertEqual(snapshot["active_count"], 1)
                self.assertEqual(snapshot["processes"][0]["process_id"], start.process_id)
                self.assertEqual(snapshot["processes"][0]["pid"], start.pid)
                self.assertTrue(snapshot["processes"][0]["restored"])
            finally:
                registry.stop(start.process_id)

    def test_process_registry_windows_liveness_check_does_not_call_os_kill(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "process-registry.json"
            state_path.write_text(
                json.dumps(
                    {
                        "mode": "command-intelligence-process-store",
                        "safety_mode": "workspace_process_registry",
                        "process_count": 1,
                        "processes": [
                            {
                                "process_id": "current-test-process",
                                "pid": os.getpid(),
                                "argv": [sys.executable, "-c", "print('running')"],
                                "cwd": td,
                                "reason": "windows liveness safety check",
                                "effects": ["read"],
                                "env_keys": [],
                                "ownership": {},
                                "started_at": 123.0,
                                "restored": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch("openwukong.control.command_runner.os.name", "nt"),
                mock.patch(
                    "openwukong.control.command_runner.os.kill",
                    side_effect=AssertionError("os.kill must not be used for Windows liveness checks"),
                ),
            ):
                restored = CommandProcessRegistry(
                    build_command_execution_policy("workspace-write", workspace_root=td),
                    storage_path=str(state_path),
                )
                snapshot = restored.snapshot()

        self.assertEqual(snapshot["active_count"], 1)
        self.assertEqual(snapshot["processes"][0]["process_id"], "current-test-process")

    def test_process_registry_restored_instance_can_stop_and_remove_process(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "process-registry.json"
            registry = CommandProcessRegistry(
                build_command_execution_policy("workspace-write", workspace_root=td),
                storage_path=str(state_path),
            )
            start = registry.start(
                CommandExecutionRequest(
                    argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                    cwd=td,
                )
            )
            restored = CommandProcessRegistry(
                build_command_execution_policy("workspace-write", workspace_root=td),
                storage_path=str(state_path),
            )

            stop = restored.stop(start.process_id, grace_seconds=1.0)
            data = stop.to_dict()

            self.assertTrue(data["ok"], data["error"])
            self.assertTrue(data["found"])
            self.assertEqual(data["process_id"], start.process_id)
            self.assertEqual(data["pid"], start.pid)
            self.assertEqual(data["control_attempts"], 1)
            stored = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["process_count"], 0)
            self.assertEqual(restored.snapshot()["active_count"], 0)
            self.assertEqual(registry.snapshot()["active_count"], 0)


def _workspace_ownership(workspace_root: str) -> SessionOwnership:
    return SessionOwnership(
        owned=True,
        ownership_source="session_readiness_manifest",
        manifest_path="terminal.json",
        route_id="terminal-native-session",
        connector_id="terminal",
        action_id="bind_terminal_workspace",
        workspace_root=workspace_root,
        cleanup_ready=False,
    )


def _write_workspace_manifest(path: Path, workspace_root: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "mode": "session-readiness-execution",
                "safety_mode": "isolated_helper_launch",
                "launches": [],
                "results": [
                    {
                        "action_id": "bind_terminal_workspace",
                        "route_id": "terminal-native-session",
                        "connector_id": "terminal",
                        "status": "workspace_bound",
                        "workspace_root": workspace_root,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
