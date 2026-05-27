import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from openwukong.control.command_process_broker import (
    CommandProcessBroker,
    CommandProcessBrokerConfig,
)
from openwukong.control.session_ownership import SessionOwnership
from openwukong.evaluation.command_process_broker import main


class CommandProcessBrokerTests(unittest.TestCase):
    def test_exports_broker_api_from_control_package(self):
        from openwukong.control import (
            CommandProcessBroker as ExportedBroker,
            CommandProcessBrokerConfig as ExportedConfig,
        )

        self.assertIs(ExportedBroker, CommandProcessBroker)
        self.assertIs(ExportedConfig, CommandProcessBrokerConfig)

    def test_broker_start_requires_explicit_control_permission(self):
        with tempfile.TemporaryDirectory() as td:
            broker = CommandProcessBroker(
                CommandProcessBrokerConfig(
                    workspace_root=td,
                    storage_path=str(Path(td) / "processes.json"),
                )
            )

            report = broker.start(
                argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                cwd=td,
            )
            data = report

            self.assertFalse(data["ok"])
            self.assertEqual(data["mode"], "command-process-broker-start")
            self.assertEqual(data["error"], "explicit_control_permission_required")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(broker.snapshot()["active_count"], 0)

    def test_broker_start_snapshot_stop_lifecycle_uses_persistent_storage(self):
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            broker = CommandProcessBroker(
                CommandProcessBrokerConfig(
                    workspace_root=td,
                    storage_path=str(storage_path),
                )
            )

            start = broker.start(
                argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                cwd=td,
                allow_control=True,
            )
            try:
                self.assertTrue(start["ok"], start["error"])
                self.assertEqual(start["mode"], "command-process-broker-start")
                self.assertEqual(start["control_attempts"], 1)
                self.assertTrue(storage_path.is_file())

                restored = CommandProcessBroker(
                    CommandProcessBrokerConfig(
                        workspace_root=td,
                        storage_path=str(storage_path),
                    )
                )
                snapshot = restored.snapshot()
                self.assertEqual(snapshot["mode"], "command-process-broker-snapshot")
                self.assertEqual(snapshot["active_count"], 1)
                self.assertTrue(snapshot["processes"][0]["restored"])

                stop = restored.stop(start["process_id"], allow_control=True)
                self.assertTrue(stop["ok"], stop["error"])
                self.assertEqual(stop["mode"], "command-process-broker-stop")
                self.assertEqual(stop["process_id"], start["process_id"])
                self.assertEqual(stop["control_attempts"], 1)
                self.assertEqual(restored.snapshot()["active_count"], 0)
            finally:
                broker.stop(start.get("process_id", ""), allow_control=True)

    def test_broker_snapshot_preserves_process_effects_and_ownership_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            ownership = SessionOwnership(
                owned=True,
                ownership_source="test",
                route_id="terminal-native-session",
                connector_id="terminal",
                workspace_root=td,
            )
            broker = CommandProcessBroker(
                CommandProcessBrokerConfig(
                    workspace_root=td,
                    storage_path=str(storage_path),
                )
            )

            start = broker.start(
                argv=(sys.executable, "-c", "import time; time.sleep(30)"),
                cwd=td,
                effects=("workspace_write",),
                reason="background dev server",
                ownership=ownership,
                allow_control=True,
            )
            try:
                self.assertTrue(start["ok"], start["error"])

                snapshot = broker.snapshot()
                process = snapshot["processes"][0]

                self.assertEqual(process["reason"], "background dev server")
                self.assertEqual(process["effects"], ["workspace_write"])
                self.assertTrue(process["ownership"]["owned"])
                self.assertEqual(process["ownership"]["route_id"], "terminal-native-session")
                self.assertEqual(process["ownership"]["workspace_root"], td)
            finally:
                broker.stop(start.get("process_id", ""), allow_control=True)

    def test_cli_snapshot_reports_empty_store_without_control(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "snapshot",
                        "--workspace-path",
                        td,
                        "--storage-path",
                        str(Path(td) / "processes.json"),
                        "--json",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "command-process-broker-snapshot")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["active_count"], 0)

    def test_cli_start_blocks_without_allow_control(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "start",
                        "--workspace-path",
                        td,
                        "--storage-path",
                        str(Path(td) / "processes.json"),
                        "--json",
                        "--",
                        sys.executable,
                        "-c",
                        "import time; time.sleep(30)",
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertEqual(data["control_attempts"], 0)

    def test_cli_start_snapshot_stop_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            storage_path = Path(td) / "processes.json"
            start_stdout = io.StringIO()
            with contextlib.redirect_stdout(start_stdout):
                start_exit = main(
                    [
                        "start",
                        "--workspace-path",
                        td,
                        "--storage-path",
                        str(storage_path),
                        "--allow-control",
                        "--json",
                        "--",
                        sys.executable,
                        "-c",
                        "import time; time.sleep(30)",
                    ]
                )
            start = json.loads(start_stdout.getvalue())
            try:
                self.assertEqual(start_exit, 0)
                self.assertTrue(start["ok"], start["error"])
                self.assertTrue(start["process_id"])

                snapshot_stdout = io.StringIO()
                with contextlib.redirect_stdout(snapshot_stdout):
                    snapshot_exit = main(
                        [
                            "snapshot",
                            "--workspace-path",
                            td,
                            "--storage-path",
                            str(storage_path),
                            "--json",
                        ]
                    )
                snapshot = json.loads(snapshot_stdout.getvalue())
                self.assertEqual(snapshot_exit, 0)
                self.assertEqual(snapshot["active_count"], 1)

                stop_stdout = io.StringIO()
                with contextlib.redirect_stdout(stop_stdout):
                    stop_exit = main(
                        [
                            "stop",
                            "--workspace-path",
                            td,
                            "--storage-path",
                            str(storage_path),
                            "--allow-control",
                            "--process-id",
                            start["process_id"],
                            "--json",
                        ]
                    )
                stop = json.loads(stop_stdout.getvalue())
                self.assertEqual(stop_exit, 0)
                self.assertTrue(stop["ok"], stop["error"])
                self.assertEqual(stop["process_id"], start["process_id"])
            finally:
                cleanup = CommandProcessBroker(
                    CommandProcessBrokerConfig(
                        workspace_root=td,
                        storage_path=str(storage_path),
                    )
                )
                cleanup.stop(start.get("process_id", ""), allow_control=True)


if __name__ == "__main__":
    unittest.main()
