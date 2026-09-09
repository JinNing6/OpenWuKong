import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.computer_operation_status_report import (
    build_computer_operation_status_report,
)
from openwukong.evaluation.owned_ide_live_bridge_demo import (
    REPORT_NAME,
    SAFE_WRITE_COMMAND_ID,
    main,
    run_owned_ide_live_bridge_demo,
)
from openwukong.evaluation.owned_ide_safe_operation_demo import (
    DEFAULT_MARKER,
    HermeticIDEBridgeFixture,
)


class OwnedIDELiveBridgeDemoTests(unittest.TestCase):
    def test_demo_uses_explicit_live_bridge_url_and_owned_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "demo"
            workspace = output / "owned_ide_live_workspace"
            fixture = HermeticIDEBridgeFixture(
                workspace_path=workspace,
                artifact_root=root / "fixture-artifacts",
                marker=DEFAULT_MARKER,
            )
            fixture.start()
            try:
                report = run_owned_ide_live_bridge_demo(
                    output_root=output,
                    ide_bridge_url=fixture.bridge_url,
                    workspace_path=workspace,
                    marker=DEFAULT_MARKER,
                    settle_seconds=0.0,
                )
            finally:
                fixture.stop()
            data = report.to_dict()
            report_path = Path(data["report_path"])
            trajectory_path = Path(data["trajectory_path"])
            report_exists = report_path.is_file()
            trajectory_exists = trajectory_path.is_file()
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["mode"], "owned-ide-live-bridge-demo")
        self.assertEqual(data["decision"], "owned_ide_live_bridge_demo_verified")
        self.assertEqual(data["safety_mode"], "live_owned_ide_bridge_no_foreground")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["desktop_control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["selected_write_command"], SAFE_WRITE_COMMAND_ID)
        self.assertTrue(data["capability_capture"]["ok"])
        self.assertTrue(data["workspace_binding"]["ok"])
        self.assertEqual(data["readback"]["readback_text"], DEFAULT_MARKER)
        self.assertEqual(data["quality_summary"]["failed"], 0)
        self.assertTrue(report_exists)
        self.assertTrue(trajectory_exists)

        write = data["write_execution"]
        self.assertTrue(write["ok"], write["error"])
        self.assertTrue(write["ownership_required"])
        self.assertTrue(write["ownership"]["owned"])
        self.assertEqual(write["selected_route"], "ide-extension-connector")
        self.assertEqual(write["selected_connector_id"], "ide-extension")
        self.assertEqual(write["action_report"]["payload"]["bridge_action"], "execute_command")
        self.assertEqual(write["action_report"]["payload"]["command_id"], SAFE_WRITE_COMMAND_ID)

        self.assertEqual(trajectory["scenario"], "owned-ide-live-bridge-demo")
        phases = [step["phase"] for step in trajectory["steps"]]
        self.assertEqual(
            phases,
            [
                "capability_capture",
                "workspace_binding",
                "ownership",
                "read_state",
                "write_scratch",
                "final_report",
            ],
        )
        final_roles = {
            artifact["role"]
            for artifact in trajectory["steps"][-1]["artifacts"]
        }
        self.assertEqual(final_roles, {"owned_ide_live_demo_report"})

    def test_demo_blocks_when_live_bridge_workspace_is_not_owned_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "demo"
            actual_workspace = output / "actual-live-workspace"
            requested_workspace = output / "owned_ide_live_workspace"
            fixture = HermeticIDEBridgeFixture(
                workspace_path=actual_workspace,
                artifact_root=root / "fixture-artifacts",
                marker=DEFAULT_MARKER,
            )
            fixture.start()
            try:
                report = run_owned_ide_live_bridge_demo(
                    output_root=output,
                    ide_bridge_url=fixture.bridge_url,
                    workspace_path=requested_workspace,
                    marker=DEFAULT_MARKER,
                    settle_seconds=0.0,
                )
            finally:
                fixture.stop()
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "owned_ide_live_bridge_workspace_mismatch")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["workspace_binding"]["error"], "bridge_first_workspace_not_owned_scratch")
        self.assertFalse(
            (requested_workspace / "openwukong-owned-scratch.txt").is_file()
        )

    def test_demo_rejects_workspace_outside_output_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            report = run_owned_ide_live_bridge_demo(
                output_root=Path(tmp) / "demo",
                workspace_path=outside,
                marker=DEFAULT_MARKER,
                settle_seconds=0.0,
            ).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "owned_ide_live_bridge_workspace_rejected")
        self.assertEqual(report["error"], "workspace_path_must_be_inside_output_root")
        self.assertEqual(report["control_attempts"], 0)

    def test_status_report_discovers_live_ide_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "runtime" / "ide-live"
            workspace = output / "owned_ide_live_workspace"
            fixture = HermeticIDEBridgeFixture(
                workspace_path=workspace,
                artifact_root=root / "fixture-artifacts",
                marker=DEFAULT_MARKER,
            )
            fixture.start()
            try:
                demo = run_owned_ide_live_bridge_demo(
                    output_root=output,
                    ide_bridge_url=fixture.bridge_url,
                    workspace_path=workspace,
                    marker=DEFAULT_MARKER,
                    settle_seconds=0.0,
                ).to_dict()
            finally:
                fixture.stop()
            self.assertEqual(Path(demo["report_path"]).name, REPORT_NAME)
            status = build_computer_operation_status_report(
                runtime_root=root / "runtime",
                discover_owned_browser_report=False,
                discover_owned_ide_report=True,
            ).to_dict()

        surfaces = {
            item["surface_id"]: item
            for item in status["readiness_matrix"]["surfaces"]
        }
        self.assertEqual(surfaces["ide"]["readiness_level"], "background_execute")
        self.assertEqual(surfaces["ide"]["operation_status"], "background_execute_verified")
        self.assertTrue(surfaces["ide"]["verified"])
        self.assertEqual(status["summary"]["owned_ide_demo_status"], "verified")
        self.assertEqual(status["owned_ide_demo"]["decision"], "owned_ide_live_bridge_demo_verified")

    def test_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "demo"
            workspace = output / "owned_ide_live_workspace"
            fixture = HermeticIDEBridgeFixture(
                workspace_path=workspace,
                artifact_root=root / "fixture-artifacts",
                marker=DEFAULT_MARKER,
            )
            fixture.start()
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "--output-root",
                            str(output),
                            "--ide-bridge-url",
                            fixture.bridge_url,
                            "--workspace-path",
                            str(workspace),
                            "--settle-seconds",
                            "0",
                            "--json",
                        ]
                    )
            finally:
                fixture.stop()
            data = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "owned-ide-live-bridge-demo")
        self.assertTrue(data["ok"], data["error"])


if __name__ == "__main__":
    unittest.main()
