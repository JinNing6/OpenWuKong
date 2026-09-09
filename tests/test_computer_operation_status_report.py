import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.computer_operation_status_report import (
    build_computer_operation_status_report,
    main,
    render_computer_operation_status_markdown,
)
from openwukong.evaluation.computer_operation_readiness_matrix import (
    BACKGROUND_EXECUTE,
    ComputerOperationReadinessOptions,
)


class ComputerOperationStatusReportTests(unittest.TestCase):
    def test_report_summarizes_readiness_and_owned_browser_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            owned_report = _write_owned_browser_artifacts(root)

            report = build_computer_operation_status_report(
                options=ComputerOperationReadinessOptions(workspace_path=str(workspace)),
                owned_browser_report_path=owned_report,
                discover_owned_browser_report=False,
                discover_owned_ide_report=False,
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "computer-operation-status-report")
        self.assertEqual(data["safety_mode"], "read_only_report")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)

        summary = data["summary"]
        self.assertEqual(summary["owned_browser_demo_status"], "verified")
        self.assertEqual(summary["observed_prior_control_attempts"], 3)
        self.assertEqual(summary["observed_prior_window_input_attempts"], 0)
        self.assertEqual(summary["owned_browser_artifact_count"], 2)

        surfaces = {
            item["surface_id"]: item
            for item in data["readiness_matrix"]["surfaces"]
        }
        self.assertEqual(surfaces["browser"]["readiness_level"], BACKGROUND_EXECUTE)
        self.assertTrue(surfaces["browser"]["connector_ready"])
        self.assertEqual(surfaces["terminal"]["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(surfaces["git"]["readiness_level"], BACKGROUND_EXECUTE)
        self.assertIn("IDE bridge evidence", " ".join(data["next_actions"]))

        owned = data["owned_browser_demo"]
        artifacts = owned["artifact_summary"]
        self.assertEqual(artifacts["status"], "loaded")
        self.assertEqual(artifacts["step_count"], 2)
        self.assertEqual(artifacts["artifact_count"], 2)
        self.assertEqual(artifacts["existing_artifact_count"], 2)
        self.assertEqual(
            artifacts["roles"],
            ["browser_workflow_report", "owned_browser_demo_report"],
        )
        self.assertEqual(
            artifacts["media_type_counts"],
            {"application/json": 2},
        )

    def test_markdown_contains_surface_table_and_artifact_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            report = build_computer_operation_status_report(
                options=ComputerOperationReadinessOptions(workspace_path=str(workspace)),
                owned_browser_report_path=_write_owned_browser_artifacts(root),
                discover_owned_browser_report=False,
                discover_owned_ide_report=False,
            )

        markdown = render_computer_operation_status_markdown(report)

        self.assertIn("# OpenWuKong Computer Operation Status", markdown)
        self.assertIn(
            "| Surface | Level | Status | Transport | Connector | Blocking reason |",
            markdown,
        )
        self.assertIn("Browser", markdown)
        self.assertIn("Cursor Agent", markdown)
        self.assertIn("- Foreground send:", markdown)
        self.assertIn("browser_workflow_report", markdown)
        self.assertIn("Owned browser demo: verified", markdown)

    def test_wechat_foreground_send_changes_next_action_without_background_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            report = build_computer_operation_status_report(
                options=ComputerOperationReadinessOptions(
                    workspace_path=str(workspace),
                    wechat_foreground_send_report=_wechat_foreground_send_report(),
                ),
                discover_owned_browser_report=False,
                discover_owned_ide_report=False,
            )
            data = report.to_dict()

        surfaces = {
            item["surface_id"]: item
            for item in data["readiness_matrix"]["surfaces"]
        }
        self.assertEqual(surfaces["wechat"]["readiness_level"], "foreground_required")
        self.assertIn(
            "foreground_file_transfer_send",
            surfaces["wechat"]["verified_capabilities"],
        )
        self.assertEqual(data["summary"]["foreground_send_count"], 1)
        self.assertIn(
            "foreground File Transfer Assistant send is verified",
            " ".join(data["next_actions"]),
        )
        self.assertNotIn(
            "wechat",
            data["readiness_matrix"]["summary"]["background_execute_surfaces"],
        )

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            owned_report = _write_owned_browser_artifacts(root)
            output = root / "status.json"
            markdown_output = root / "status.md"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--workspace-path",
                        str(workspace),
                        "--owned-browser-report",
                        str(owned_report),
                        "--no-discover-owned-browser-report",
                        "--no-discover-owned-ide-report",
                        "--output",
                        str(output),
                        "--markdown-output",
                        str(markdown_output),
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())
            markdown_text = markdown_output.read_text(encoding="utf-8")
            output_exists = output.is_file()
            markdown_exists = markdown_output.is_file()

        self.assertEqual(exit_code, 0)
        self.assertTrue(output_exists)
        self.assertTrue(markdown_exists)
        self.assertEqual(data["mode"], "computer-operation-status-report")
        self.assertEqual(data["summary"]["owned_browser_demo_status"], "verified")
        self.assertIn(
            "OpenWuKong Computer Operation Status",
            markdown_text,
        )

    def test_cli_reads_codex_turn_report_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            turn_report = root / "codex-turn-report.json"
            output = root / "status.json"
            turn_report.write_text(
                json.dumps(
                    {
                        "report": {
                            "cases": [
                                {
                                    "codex_app_server_turn_start_report": _codex_turn_report()
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--workspace-path",
                        str(workspace),
                        "--codex-app-server-ws-url",
                        "ws://127.0.0.1:19731",
                        "--codex-app-server-turn-start-report",
                        str(turn_report),
                        "--no-discover-owned-browser-report",
                        "--no-discover-owned-ide-report",
                        "--output",
                        str(output),
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["summary"]["verified_background_execute_count"], 1)
        self.assertEqual(written["summary"]["verified_background_execute_count"], 1)
        surfaces = {
            item["surface_id"]: item
            for item in data["readiness_matrix"]["surfaces"]
        }
        self.assertEqual(
            surfaces["codex"]["operation_status"],
            "background_execute_verified",
        )
        self.assertIn(
            "codex",
            data["readiness_matrix"]["summary"]["background_execute_verified_surfaces"],
        )


def _write_owned_browser_artifacts(root: Path) -> Path:
    workflow = root / "browser_workflow.json"
    final = root / "owned_browser_safe_operation_demo.json"
    trajectory = root / "control_trajectories" / "traj-demo" / "manifest.json"
    workflow.write_text("{}", encoding="utf-8")
    trajectory.parent.mkdir(parents=True, exist_ok=True)
    trajectory.write_text(
        json.dumps(
            {
                "mode": "control-trajectory",
                "scenario": "owned-browser-safe-operation-demo",
                "step_count": 2,
                "steps": [
                    {
                        "phase": "workflow",
                        "artifacts": [
                            {
                                "role": "browser_workflow_report",
                                "path": str(workflow),
                                "media_type": "application/json",
                                "sha256": "a" * 64,
                            }
                        ],
                    },
                    {
                        "phase": "final_report",
                        "artifacts": [
                            {
                                "role": "owned_browser_demo_report",
                                "path": str(final),
                                "media_type": "application/json",
                                "sha256": "b" * 64,
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    final.write_text(
        json.dumps(
            {
                "mode": "owned-browser-safe-operation-demo",
                "ok": True,
                "decision": "owned_browser_demo_verified",
                "control_attempts": 3,
                "desktop_control_attempts": 0,
                "window_input_attempts": 0,
                "report_path": str(final),
                "trajectory_path": str(trajectory),
                "controlled_page": {
                    "url": "http://127.0.0.1:19191/",
                },
                "readiness_execution": {
                    "results": [
                        {
                            "status": "started",
                            "readiness_url": "http://127.0.0.1:19191",
                        }
                    ]
                },
                "browser_workflow": {
                    "quality_summary": {
                        "passed": 3,
                        "failed": 0,
                    }
                },
                "profile_cleanup": {
                    "deleted": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return final


def _codex_turn_report() -> dict:
    return {
        "ok": True,
        "decision": "codex_app_server_turn_start_verified",
        "endpoint_url": "ws://127.0.0.1:19731",
        "assistant_readback_text": "OPENWUKONG_ACCEPTANCE: PASS",
        "required_markers": ["OPENWUKONG_ACCEPTANCE: PASS"],
        "missing_required_markers": [],
        "seen_forbidden_markers": [],
        "turn_completed": True,
        "turn_status": "completed",
        "foreground_no_steal_verified": True,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "app_server_turn_start_attempts": 1,
        "session_task_complete_seen": True,
    }


def _wechat_foreground_send_report() -> dict:
    return {
        "mode": "wechat-file-helper-send-probe",
        "safety_mode": "explicit_opt_in_real_send",
        "status": "sent",
        "target_name": "文件传输助手",
        "message": "OPENWUKONG_WECHAT_FOREGROUND: PASS",
        "allow_send": True,
        "control_allowed": True,
        "send_attempts": 1,
        "keyboard_input_attempts": 6,
        "clipboard_write_attempts": 2,
        "clipboard_restore_attempts": 1,
        "foreground_restore_attempts": 1,
        "target_verified": True,
        "post_send_screenshot_bound": True,
        "transport": "foreground-keyboard-clipboard",
        "error": "",
    }


if __name__ == "__main__":
    unittest.main()
