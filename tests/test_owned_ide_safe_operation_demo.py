import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.computer_operation_status_report import (
    build_computer_operation_status_report,
)
from openwukong.evaluation.owned_ide_safe_operation_demo import (
    DEFAULT_MARKER,
    main,
    run_owned_ide_safe_operation_demo,
)


class OwnedIDESafeOperationDemoTests(unittest.TestCase):
    def test_demo_runs_hermetic_bridge_through_fabric_and_writes_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_owned_ide_safe_operation_demo(
                output_root=tmp,
                marker=DEFAULT_MARKER,
                settle_seconds=0.0,
            )
            data = report.to_dict()
            report_path = Path(data["report_path"])
            trajectory_path = Path(data["trajectory_path"])
            scratch_path = Path(data["readback"]["scratch_path"])

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(data["decision"], "owned_ide_demo_verified")
            self.assertEqual(data["safety_mode"], "hermetic_owned_ide_bridge")
            self.assertTrue(data["control_allowed"])
            self.assertEqual(data["desktop_control_attempts"], 0)
            self.assertEqual(data["window_input_attempts"], 0)
            self.assertEqual(data["readback"]["readback_text"], DEFAULT_MARKER)
            self.assertTrue(scratch_path.is_file())
            self.assertTrue(report_path.is_file())
            self.assertTrue(trajectory_path.is_file())

            read_state = data["read_state_execution"]
            write = data["write_execution"]
            self.assertTrue(read_state["ok"], read_state["error"])
            self.assertTrue(write["ok"], write["error"])
            self.assertTrue(read_state["ownership_required"])
            self.assertTrue(write["ownership_required"])
            self.assertTrue(write["ownership"]["owned"])
            self.assertEqual(write["selected_route"], "ide-extension-connector")
            self.assertEqual(write["selected_connector_id"], "ide-extension")
            self.assertEqual(write["action_report"]["payload"]["bridge_action"], "send_message")
            self.assertEqual(
                write["action_report"]["payload"]["response"]["readback_text"],
                DEFAULT_MARKER,
            )

            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            self.assertEqual(trajectory["mode"], "control-trajectory")
            self.assertEqual(trajectory["scenario"], "owned-ide-safe-operation-demo")
            self.assertEqual(trajectory["step_count"], 5)
            phases = [step["phase"] for step in trajectory["steps"]]
            self.assertEqual(
                phases,
                [
                    "bridge_fixture",
                    "ownership",
                    "read_state",
                    "write_scratch",
                    "final_report",
                ],
            )
            write_roles = {
                artifact["role"]
                for artifact in trajectory["steps"][3]["artifacts"]
            }
            self.assertIn("scratch_path", write_roles)
            self.assertIn("readback_path", write_roles)
            final_roles = {
                artifact["role"]
                for artifact in trajectory["steps"][-1]["artifacts"]
            }
            self.assertEqual(final_roles, {"owned_ide_demo_report"})

    def test_status_report_promotes_ide_with_owned_demo_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            demo = run_owned_ide_safe_operation_demo(
                output_root=Path(tmp) / "ide-demo",
                settle_seconds=0.0,
            ).to_dict()
            status = build_computer_operation_status_report(
                owned_browser_report_path="",
                owned_ide_report_path=demo["report_path"],
                discover_owned_browser_report=False,
                discover_owned_ide_report=False,
            ).to_dict()

        surfaces = {
            item["surface_id"]: item
            for item in status["readiness_matrix"]["surfaces"]
        }
        self.assertEqual(surfaces["ide"]["readiness_level"], "background_execute")
        self.assertEqual(surfaces["ide"]["connector_id"], "ide-extension")
        self.assertEqual(status["summary"]["owned_ide_demo_status"], "verified")
        self.assertGreaterEqual(status["summary"]["owned_ide_artifact_count"], 4)
        self.assertNotIn(
            "Run the owned IDE bridge demo",
            " ".join(status["next_actions"]),
        )

    def test_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--output-root",
                        tmp,
                        "--settle-seconds",
                        "0",
                        "--json",
                    ]
            )
            data = json.loads(stdout.getvalue())
            report_path = Path(data["report_path"])
            report_exists = report_path.is_file()

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "owned-ide-safe-operation-demo")
        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(report_exists)


if __name__ == "__main__":
    unittest.main()
