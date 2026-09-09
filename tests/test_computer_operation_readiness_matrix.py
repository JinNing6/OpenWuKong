import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from openwukong.evaluation.computer_operation_readiness_matrix import (
    BACKGROUND_EXECUTE,
    BACKGROUND_EXECUTE_VERIFIED,
    BLOCKED,
    CURSOR_SUBMIT_BLOCKED,
    FOREGROUND_REQUIRED,
    WECHAT_NATIVE_SEND_BLOCKED,
    ComputerOperationReadinessOptions,
    build_computer_operation_readiness_matrix,
)


class ComputerOperationReadinessMatrixTests(unittest.TestCase):
    def test_default_matrix_keeps_unverified_desktop_surfaces_blocked(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(workspace_path=workspace)
            ).to_dict()

        self.assertEqual(matrix["mode"], "computer-operation-readiness-matrix")
        self.assertEqual(matrix["safety_mode"], "plan_only")
        self.assertFalse(matrix["control_allowed"])
        self.assertEqual(matrix["control_attempts"], 0)
        self.assertFalse(matrix["background_operation_ready"])

        surfaces = _surfaces(matrix)
        self.assertEqual(surfaces["codex"]["readiness_level"], BLOCKED)
        self.assertEqual(surfaces["codex"]["operation_status"], BLOCKED)
        self.assertIn(
            "codex_app_server_turn_start_report_missing",
            surfaces["codex"]["required_evidence"],
        )

        self.assertEqual(surfaces["terminal"]["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(surfaces["terminal"]["dispatch_decision"], "dispatch_connector")
        self.assertTrue(surfaces["terminal"]["connector_ready"])
        self.assertTrue(surfaces["terminal"]["can_write_without_focus"])

        self.assertEqual(surfaces["git"]["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(surfaces["git"]["selected_transport"], "workspace-bound-git-cli")
        self.assertTrue(surfaces["git"]["can_write_without_focus"])

        self.assertEqual(surfaces["browser"]["readiness_level"], BLOCKED)
        self.assertIn("browser_debugger_url_missing", surfaces["browser"]["required_evidence"])
        self.assertFalse(surfaces["browser"]["connector_ready"])

        self.assertEqual(surfaces["ide"]["readiness_level"], BLOCKED)
        self.assertIn("ide_bridge_url_missing", surfaces["ide"]["required_evidence"])

        self.assertEqual(surfaces["cursor"]["readiness_level"], BLOCKED)
        self.assertEqual(surfaces["cursor"]["operation_status"], CURSOR_SUBMIT_BLOCKED)
        self.assertIn(
            "submit_capable_cursor_native_hook",
            surfaces["cursor"]["required_evidence"],
        )
        self.assertIn(
            "assistant_response_marker_readback",
            surfaces["cursor"]["required_evidence"],
        )
        self.assertFalse(surfaces["cursor"]["can_execute_without_focus"])

        self.assertEqual(surfaces["wechat"]["readiness_level"], BLOCKED)
        self.assertIn(
            "wechat_native_bridge_url_missing",
            surfaces["wechat"]["required_evidence"],
        )
        self.assertIn(
            "background_screenshot_not_verified",
            surfaces["wechat"]["required_evidence"],
        )

        self.assertEqual(surfaces["office"]["readiness_level"], BLOCKED)
        self.assertIn(
            "office_object_model_connector_missing",
            surfaces["office"]["required_evidence"],
        )

        self.assertEqual(
            surfaces["generic_desktop"]["readiness_level"],
            FOREGROUND_REQUIRED,
        )
        self.assertFalse(surfaces["generic_desktop"]["can_write_without_focus"])
        self.assertEqual(matrix["summary"]["background_execute_surfaces"], ["terminal", "git"])
        self.assertEqual(matrix["summary"]["background_execute_verified_surfaces"], [])

    def test_cursor_preserves_draft_and_foreground_fallback_without_claiming_submit(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    cursor_bridge_url="http://127.0.0.1:8787",
                    cursor_draft_hook_report=_cursor_draft_hook_report(),
                    cursor_foreground_fallback_report=_cursor_foreground_fallback_report(),
                    cursor_background_safe_probe_report=_cursor_background_safe_probe_report(),
                )
            ).to_dict()

        cursor = _surfaces(matrix)["cursor"]

        self.assertEqual(cursor["readiness_level"], BLOCKED)
        self.assertEqual(cursor["operation_status"], CURSOR_SUBMIT_BLOCKED)
        self.assertFalse(cursor["verified"])
        self.assertFalse(cursor["can_execute_without_focus"])
        self.assertTrue(cursor["can_write_without_focus"])
        self.assertTrue(cursor["connector_ready"])
        self.assertEqual(cursor["selected_transport"], "cursor-draft-hook")
        self.assertEqual(cursor["transport_capability_level"], "background-draft")
        self.assertIn("background_draft_injection", cursor["verified_capabilities"])
        self.assertIn(
            "foreground_uia_clipboard_draft_fallback",
            cursor["verified_capabilities"],
        )
        self.assertIn(
            "composer_send_dispatch_resolved_without_assistant_readback",
            cursor["partial_capabilities"],
        )
        self.assertIn("cursor-foreground-uia-clipboard", cursor["fallback_transports"])
        self.assertEqual(cursor["blocking_reason"], "cursor_submit_readback_not_verified")
        self.assertIn(
            "cursor_submit_native_service_hook",
            cursor["missing_capabilities"],
        )
        self.assertTrue(cursor["evidence"]["cursor_draft_hook_verified"])
        self.assertTrue(cursor["evidence"]["cursor_foreground_fallback_verified"])
        self.assertTrue(cursor["evidence"]["cursor_background_uia_requires_foreground"])
        self.assertNotIn("cursor", matrix["summary"]["background_execute_surfaces"])
        self.assertNotIn(
            "cursor",
            matrix["summary"]["background_execute_verified_surfaces"],
        )
        self.assertIn("cursor", matrix["summary"]["background_draft_surfaces"])
        self.assertEqual(matrix["summary"]["verified_background_draft_count"], 1)

    def test_codex_app_server_report_marks_background_execute_verified(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    codex_app_server_ws_url="ws://127.0.0.1:19731",
                    codex_app_server_turn_start_report=_codex_turn_report(),
                )
            ).to_dict()

        surfaces = _surfaces(matrix)
        codex = surfaces["codex"]

        self.assertEqual(codex["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(codex["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertTrue(codex["verified"])
        self.assertTrue(codex["connector_ready"])
        self.assertTrue(codex["can_execute_without_focus"])
        self.assertTrue(codex["can_write_without_focus"])
        self.assertTrue(codex["requires_user_confirmation"])
        self.assertEqual(codex["selected_transport"], "codex-app-server-ws")
        self.assertEqual(codex["blocking_reason"], "")
        self.assertTrue(codex["evidence"]["strict_assistant_readback_verified"])
        self.assertIn("codex", matrix["summary"]["background_execute_surfaces"])
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["codex"],
        )
        self.assertEqual(matrix["summary"]["verified_background_execute_count"], 1)

    def test_owned_browser_demo_report_marks_background_execute_verified(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    owned_browser_demo_report=_owned_browser_demo_report(),
                )
            ).to_dict()

        surfaces = _surfaces(matrix)
        browser = surfaces["browser"]

        self.assertEqual(browser["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(browser["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertTrue(browser["verified"])
        self.assertTrue(browser["connector_ready"])
        self.assertTrue(browser["can_execute_without_focus"])
        self.assertTrue(browser["can_write_without_focus"])
        self.assertEqual(browser["selected_transport"], "chrome-devtools-protocol")
        self.assertEqual(browser["blocking_reason"], "")
        self.assertTrue(browser["evidence"]["owned_browser_demo_verified"])
        self.assertEqual(browser["evidence"]["window_input_attempts"], 0)
        self.assertEqual(browser["evidence"]["desktop_control_attempts"], 0)
        self.assertEqual(browser["evidence"]["browser_quality_failed"], 0)
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["browser"],
        )

    def test_owned_ide_demo_report_marks_background_execute_verified(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    owned_ide_demo_report=_owned_ide_demo_report(),
                )
            ).to_dict()

        surfaces = _surfaces(matrix)
        ide = surfaces["ide"]

        self.assertEqual(ide["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(ide["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertTrue(ide["verified"])
        self.assertTrue(ide["connector_ready"])
        self.assertTrue(ide["can_execute_without_focus"])
        self.assertTrue(ide["can_write_without_focus"])
        self.assertEqual(ide["selected_transport"], "vscode-extension-bridge")
        self.assertEqual(ide["blocking_reason"], "")
        self.assertTrue(ide["evidence"]["owned_ide_demo_verified"])
        self.assertEqual(ide["evidence"]["window_input_attempts"], 0)
        self.assertEqual(ide["evidence"]["keyboard_input_attempts"], 0)
        self.assertEqual(ide["evidence"]["clipboard_write_attempts"], 0)
        self.assertEqual(ide["evidence"]["ide_quality_failed"], 0)
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["ide"],
        )

    def test_explicit_connector_evidence_promotes_browser_ide_but_not_wechat_without_send_readback(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    browser_debugger_url="http://127.0.0.1:9222",
                    ide_bridge_url="http://127.0.0.1:8787",
                    wechat_native_bridge_url="http://127.0.0.1:18180",
                    wechat_background_screenshot_count=1,
                    wechat_background_screenshot_success_count=1,
                )
            ).to_dict()

        surfaces = _surfaces(matrix)
        for surface_id in ("browser", "terminal", "git", "ide"):
            self.assertEqual(surfaces[surface_id]["readiness_level"], BACKGROUND_EXECUTE)
            self.assertEqual(surfaces[surface_id]["dispatch_decision"], "dispatch_connector")
            self.assertTrue(surfaces[surface_id]["connector_ready"])
            self.assertTrue(surfaces[surface_id]["can_write_without_focus"])

        self.assertEqual(surfaces["wechat"]["readiness_level"], BLOCKED)
        self.assertEqual(
            surfaces["wechat"]["operation_status"],
            WECHAT_NATIVE_SEND_BLOCKED,
        )
        self.assertEqual(surfaces["wechat"]["selected_transport"], "wechat-native-bridge")
        self.assertTrue(surfaces["wechat"]["requires_user_confirmation"])
        self.assertTrue(surfaces["wechat"]["connector_ready"])
        self.assertFalse(surfaces["wechat"]["can_write_without_focus"])
        self.assertIn(
            "wechat_native_bridge_route_ready",
            surfaces["wechat"]["partial_capabilities"],
        )
        self.assertIn(
            "wechat_native_bridge_send_report_missing",
            surfaces["wechat"]["missing_capabilities"],
        )
        self.assertEqual(surfaces["office"]["readiness_level"], BLOCKED)
        self.assertEqual(surfaces["generic_desktop"]["readiness_level"], FOREGROUND_REQUIRED)
        self.assertEqual(
            matrix["summary"]["background_execute_surfaces"],
            ["browser", "terminal", "git", "ide"],
        )
        self.assertEqual(matrix["summary"]["write_ready_count"], 4)

    def test_wechat_foreground_filehelper_send_is_preserved_without_background_claim(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    wechat_foreground_send_report=_wechat_foreground_send_report(),
                )
            ).to_dict()

        wechat = _surfaces(matrix)["wechat"]

        self.assertEqual(wechat["readiness_level"], FOREGROUND_REQUIRED)
        self.assertEqual(wechat["operation_status"], FOREGROUND_REQUIRED)
        self.assertFalse(wechat["verified"])
        self.assertFalse(wechat["can_execute_without_focus"])
        self.assertFalse(wechat["can_write_without_focus"])
        self.assertTrue(wechat["foreground_required"])
        self.assertEqual(wechat["selected_transport"], "foreground-keyboard-clipboard")
        self.assertIn("foreground_file_transfer_send", wechat["verified_capabilities"])
        self.assertIn("foreground_post_send_marker_readback", wechat["verified_capabilities"])
        self.assertIn("foreground-keyboard-clipboard", wechat["fallback_transports"])
        self.assertIn("foreground_focus_required", wechat["risk_flags"])
        self.assertTrue(wechat["evidence"]["wechat_foreground_send_verified"])
        self.assertTrue(wechat["evidence"]["wechat_foreground_post_send_verified"])
        self.assertEqual(
            wechat["evidence"]["wechat_foreground_post_send_verification_method"],
            "windows-media-ocr-readback",
        )
        self.assertEqual(
            wechat["evidence"]["wechat_foreground_post_send_ocr_method"],
            "python-winrt-windows-media-ocr",
        )
        self.assertTrue(
            wechat["evidence"]["wechat_foreground_post_send_normalized_marker_matched"]
        )
        self.assertEqual(
            wechat["blocking_reason"],
            "wechat_native_send_readback_not_verified",
        )
        self.assertNotIn("wechat", matrix["summary"]["background_execute_surfaces"])
        self.assertIn("wechat", matrix["summary"]["foreground_required_surfaces"])
        self.assertIn("wechat", matrix["summary"]["foreground_send_surfaces"])

    def test_wechat_native_send_report_marks_background_execute_verified(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    wechat_native_bridge_url="http://127.0.0.1:18180",
                    wechat_background_screenshot_count=1,
                    wechat_background_screenshot_success_count=1,
                    wechat_foreground_send_report=_wechat_foreground_send_report(),
                    wechat_native_bridge_send_report=_wechat_native_bridge_send_report(),
                    wechat_native_bridge_fixture_report=_wechat_fixture_report(),
                )
            ).to_dict()

        wechat = _surfaces(matrix)["wechat"]

        self.assertEqual(wechat["readiness_level"], BACKGROUND_EXECUTE)
        self.assertEqual(wechat["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertTrue(wechat["verified"])
        self.assertTrue(wechat["connector_ready"])
        self.assertTrue(wechat["background_safe"])
        self.assertTrue(wechat["can_execute_without_focus"])
        self.assertTrue(wechat["can_write_without_focus"])
        self.assertEqual(wechat["selected_transport"], "wechat-native-bridge")
        self.assertIn(
            "background_native_file_transfer_send",
            wechat["verified_capabilities"],
        )
        self.assertIn(
            "foreground_file_transfer_send",
            wechat["verified_capabilities"],
        )
        self.assertIn(
            "native_bridge_fixture_send_verified",
            wechat["partial_capabilities"],
        )
        self.assertEqual(wechat["missing_capabilities"], [])
        self.assertTrue(wechat["evidence"]["wechat_native_send_verified"])
        self.assertFalse(wechat["evidence"]["wechat_native_send_is_fixture"])
        self.assertIn("wechat", matrix["summary"]["background_execute_surfaces"])
        self.assertIn(
            "wechat",
            matrix["summary"]["background_execute_verified_surfaces"],
        )

    def test_wechat_fixture_send_does_not_promote_real_background_send(self):
        with tempfile.TemporaryDirectory() as workspace:
            matrix = build_computer_operation_readiness_matrix(
                options=ComputerOperationReadinessOptions(
                    workspace_path=workspace,
                    wechat_native_bridge_fixture_report=_wechat_fixture_report(),
                )
            ).to_dict()

        wechat = _surfaces(matrix)["wechat"]

        self.assertEqual(wechat["readiness_level"], BLOCKED)
        self.assertEqual(wechat["operation_status"], WECHAT_NATIVE_SEND_BLOCKED)
        self.assertIn(
            "native_bridge_fixture_send_verified",
            wechat["partial_capabilities"],
        )
        self.assertNotIn("wechat", matrix["summary"]["background_execute_surfaces"])

    def test_cli_writes_json_without_control_attempts(self):
        from openwukong.evaluation import computer_operation_readiness_matrix

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "matrix.json"
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = computer_operation_readiness_matrix.main(
                    [
                        "--workspace-path",
                        root,
                        "--browser-debugger-url",
                        "http://127.0.0.1:9222",
                        "--codex-app-server-ws-url",
                        "ws://127.0.0.1:19731",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Computer operation readiness:", stdout.getvalue())

        self.assertIn('"mode": "computer-operation-readiness-matrix"', text)
        self.assertIn('"control_attempts": 0', text)

    def test_cli_reads_codex_turn_report_json(self):
        from openwukong.evaluation import computer_operation_readiness_matrix

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "matrix.json"
            report = Path(root) / "codex-turn-report.json"
            report.write_text(
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
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = computer_operation_readiness_matrix.main(
                    [
                        "--workspace-path",
                        root,
                        "--codex-app-server-turn-start-report",
                        str(report),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            matrix = json.loads(output.read_text(encoding="utf-8"))
        codex = _surfaces(matrix)["codex"]
        self.assertEqual(codex["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["codex"],
        )

    def test_cli_reads_owned_browser_demo_json(self):
        from openwukong.evaluation import computer_operation_readiness_matrix

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "matrix.json"
            report = Path(root) / "owned-browser-demo.json"
            report.write_text(
                json.dumps(_owned_browser_demo_report(), ensure_ascii=False),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = computer_operation_readiness_matrix.main(
                    [
                        "--workspace-path",
                        root,
                        "--owned-browser-demo-report",
                        str(report),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            matrix = json.loads(output.read_text(encoding="utf-8"))
        browser = _surfaces(matrix)["browser"]
        self.assertEqual(browser["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["browser"],
        )

    def test_cli_reads_owned_ide_demo_json(self):
        from openwukong.evaluation import computer_operation_readiness_matrix

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "matrix.json"
            report = Path(root) / "owned-ide-demo.json"
            report.write_text(
                json.dumps(_owned_ide_demo_report(), ensure_ascii=False),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = computer_operation_readiness_matrix.main(
                    [
                        "--workspace-path",
                        root,
                        "--owned-ide-demo-report",
                        str(report),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            matrix = json.loads(output.read_text(encoding="utf-8"))
        ide = _surfaces(matrix)["ide"]
        self.assertEqual(ide["operation_status"], BACKGROUND_EXECUTE_VERIFIED)
        self.assertEqual(
            matrix["summary"]["background_execute_verified_surfaces"],
            ["ide"],
        )


def _surfaces(matrix: dict) -> dict:
    return {item["surface_id"]: item for item in matrix["surfaces"]}


def _cursor_draft_hook_report() -> dict:
    return {
        "mode": "cursor-draft-hook-validation",
        "safety_mode": "live_attach_draft_write_validation",
        "ok": True,
        "decision": "cursor_draft_hook_validated",
        "control_allowed": True,
        "control_attempts": 1,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "bridge_probe_attempts": 2,
        "draft_write_attempts": 1,
        "foreground_changed": False,
        "system_dialog_detected": False,
        "readback_verified": True,
        "bridge_url": "http://127.0.0.1:8787",
        "workspace_path": "E:/ideaProjects/agent/PaoPaoHeZi",
        "write_report": {
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        },
        "readback_report": {
            "decision": "cursor_transcript_readback_accepted",
            "required_response_role": "user",
        },
    }


def _cursor_foreground_fallback_report() -> dict:
    return {
        "mode": "application-control-input-action",
        "safety_mode": "non_submit_write_verify_clear",
        "ok": True,
        "control_attempts": 2,
        "target": {
            "process_name": "Cursor.exe",
            "window_title": "config - PaoPaoHeZi - Cursor",
        },
        "write_method": "clipboard_paste",
        "token_visible_after_write": True,
        "token_visible_after_clear": False,
        "submitted": False,
        "steps": [
            "window_focused",
            "input_focused",
            "clipboard_paste:verified",
            "force_cleared_after",
        ],
    }


def _cursor_background_safe_probe_report() -> dict:
    return {
        "mode": "application-control-input-action",
        "safety_mode": "background_semantic_write_verify_clear",
        "ok": False,
        "control_attempts": 1,
        "foreground_interaction_allowed": False,
        "foreground_required": True,
        "error": "foreground_required",
        "write_method": "",
        "token_visible_after_write": False,
        "token_visible_after_clear": False,
    }


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


def _owned_browser_demo_report() -> dict:
    marker = "OPENWUKONG_BROWSER_ACCEPTANCE"
    url = f"http://127.0.0.1:18888/verified?marker={marker}"
    return {
        "mode": "owned-browser-safe-operation-demo",
        "safety_mode": "isolated_owned_browser_devtools",
        "ok": True,
        "decision": "owned_browser_demo_verified",
        "control_allowed": True,
        "control_attempts": 3,
        "desktop_control_allowed": False,
        "desktop_control_attempts": 0,
        "window_input_attempts": 0,
        "controlled_page": {
            "url": "http://127.0.0.1:18888/",
            "marker": marker,
        },
        "readiness_execution": {
            "results": [
                {
                    "action_id": "launch_browser_devtools_isolated",
                    "route_id": "browser-devtools-or-extension",
                    "connector_id": "browser",
                    "status": "started",
                    "readiness_url": "http://127.0.0.1:19999",
                }
            ]
        },
        "browser_workflow": {
            "ok": True,
            "control_allowed": True,
            "control_attempts": 3,
            "step_count": 5,
            "final_page_identity": {
                "title": "OpenWukong Controlled Page - Verified",
                "href": url,
                "readyState": "complete",
            },
            "quality_summary": {
                "total": 6,
                "passed": 6,
                "failed": 0,
            },
        },
        "readiness_stop": {
            "stop_attempts": 1,
            "results": [
                {
                    "status": "stopped",
                    "error": "",
                }
            ],
        },
        "profile_cleanup": {
            "attempted": True,
            "deleted": True,
            "kept": False,
        },
    }


def _owned_ide_demo_report() -> dict:
    marker = "OPENWUKONG_IDE_ACCEPTANCE"
    workspace = "C:/tmp/openwukong-owned-ide/workspace"
    bridge_url = "http://127.0.0.1:18877"
    write_execution = {
        "ok": True,
        "control_allowed": True,
        "control_attempts": 1,
        "window_input_attempts": 0,
        "ownership_required": True,
        "ownership": {"owned": True},
        "selected_route": "ide-extension-connector",
        "selected_connector_id": "ide-extension",
        "action_report": {
            "payload": {
                "bridge_action": "execute_command",
                "command_id": "openwukong.writeScratch",
                "window_input_attempts": 0,
                "keyboard_input_attempts": 0,
                "clipboard_write_attempts": 0,
            }
        },
    }
    return {
        "mode": "owned-ide-live-bridge-demo",
        "safety_mode": "live_owned_ide_bridge_no_foreground",
        "ok": True,
        "decision": "owned_ide_live_bridge_demo_verified",
        "control_allowed": True,
        "control_attempts": 2,
        "desktop_control_attempts": 0,
        "window_input_attempts": 0,
        "selected_write_command": "openwukong.writeScratch",
        "bridge": {
            "bridge_url": bridge_url,
            "workspace_path": workspace,
        },
        "workspace_binding": {
            "ok": True,
            "expected_workspace_path": workspace,
            "observed_first_workspace_path": workspace,
        },
        "read_state_execution": {
            "ok": True,
            "control_attempts": 1,
            "window_input_attempts": 0,
            "action_report": {
                "payload": {
                    "bridge_action": "read_state",
                    "window_input_attempts": 0,
                    "keyboard_input_attempts": 0,
                    "clipboard_write_attempts": 0,
                }
            },
        },
        "write_execution": write_execution,
        "readback": {
            "ok": True,
            "marker": marker,
            "readback_text": marker,
            "readback_verified": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
        },
        "quality_summary": {
            "passed": 10,
            "failed": 0,
        },
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
        "post_send_screenshot_path": "logs/runtime/wechat/post_send_verify.png",
        "post_send_verified": True,
        "post_send_verification": {
            "verified": True,
            "method": "windows-media-ocr-readback",
            "ocr_method": "python-winrt-windows-media-ocr",
            "normalized_marker_matched": True,
            "error": "",
        },
        "transport": "foreground-keyboard-clipboard",
        "error": "",
    }


def _wechat_native_bridge_send_report(
    *,
    bridge_name: str = "OpenWukong Live WeChat Bridge",
    conversation_id: str = "filehelper",
) -> dict:
    marker = "OPENWUKONG_WECHAT_NATIVE: PASS"
    request = {
        "mode": "wechat-native-bridge-request",
        "schema_version": "wechat-native-bridge-v1",
        "request_id": "wcn-test",
        "bridge_url": "http://127.0.0.1:18180",
        "native_endpoint_ready": True,
        "target_ready": True,
        "send_action_ready": True,
        "background_safe": True,
        "background_screenshot_focus_stable": True,
        "background_screenshot_count": 1,
        "background_screenshot_success_count": 1,
        "background_screenshot_verified": True,
        "target_name": "File Transfer Assistant",
        "target": {
            "target_name": "File Transfer Assistant",
            "target_matched": True,
            "name": "File Transfer Assistant",
            "conversation_id": conversation_id,
            "available": True,
        },
        "payload": {
            "message": marker,
            "required_markers": [marker],
            "forbidden_markers": ["OPENWUKONG_WECHAT_NATIVE: FAIL"],
        },
    }
    dry_run = {
        "mode": "wechat-native-bridge-dry-run",
        "safety_mode": "dry_run",
        "ok": True,
        "decision": "wechat_native_bridge_dry_run_ready",
        "control_allowed": False,
        "control_attempts": 0,
        "send_attempts": 0,
        "window_input_attempts": 0,
        "capability_probe_attempts": 1,
        "native_endpoint_ready": True,
        "target_ready": True,
        "send_action_ready": True,
        "background_safe": True,
        "validation_errors": [],
        "error": "",
        "capability_report": {
            "ok": True,
            "bridge": {"name": bridge_name},
            "background_safe": True,
            "requires_foreground": False,
            "window_input_required": False,
            "keyboard_input_required": False,
            "mouse_input_required": False,
            "clipboard_required": False,
            "capabilities": ["wechat.conversation.send_message"],
            "targets": [request["target"]],
        },
        "request": request,
    }
    return {
        "mode": "wechat-native-bridge-send",
        "safety_mode": "native_bridge_execute",
        "ok": True,
        "decision": "wechat_native_bridge_send_accepted",
        "control_allowed": True,
        "control_attempts": 0,
        "send_attempts": 1,
        "native_call_attempts": 1,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
        "foreground_focus_stable": True,
        "missing_required_markers": [],
        "present_forbidden_markers": [],
        "action_result": {
            "ok": True,
            "sent": True,
            "foreground_focus_stable": True,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "readbackText": f"File Transfer Assistant\n{marker}",
        },
        "error": "",
        "dry_run_report": dry_run,
        "request": request,
    }


def _wechat_fixture_report() -> dict:
    send_report = _wechat_native_bridge_send_report(
        bridge_name="OpenWukong Owned WeChat Fixture",
        conversation_id="owned-fixture-filehelper",
    )
    return {
        "mode": "wechat-native-bridge-fixture-smoke",
        "safety_mode": "local_owned_wechat_native_bridge_fixture",
        "ok": True,
        "decision": "wechat_native_bridge_fixture_smoke_verified",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "native_call_attempts": 1,
        "send_attempts": 1,
        "send_report": send_report,
    }


if __name__ == "__main__":
    unittest.main()
