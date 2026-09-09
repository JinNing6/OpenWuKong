import contextlib
import http.server
import io
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from openwukong.evaluation.ide_bridge_contract_probe import (
    build_bridge_settings_from_probe_report,
    build_probe_allowlist_settings,
    build_argument_variants,
    main,
    probe_ide_command_contracts,
    select_probe_command_ids,
    _system_dialog_detected,
)


class _ContractProbeBridgeHandler(http.server.BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))

        if self.path == "/v1/ide/state":
            self._send_json(
                {
                    "ok": True,
                    "metadata": {
                        "ide_name": "Cursor",
                        "workspaceFolders": [
                            {
                                "name": "probe-workspace",
                                "fsPath": payload.get("target", {}).get("workspace_path", ""),
                            }
                        ],
                    },
                    "diagnostics": [],
                }
            )
            return

        if self.path == "/v1/ide/command":
            command_id = payload.get("command_id", "")
            arguments = payload.get("arguments", [])
            workspace_path = Path(payload.get("target", {}).get("workspace_path", ""))
            if command_id == "composer.startComposerPrompt" and arguments and isinstance(arguments[0], dict):
                self._send_json(
                    {
                        "ok": True,
                        "action_key": "probe-ok",
                        "metadata": {
                            "ide_name": "Cursor",
                            "command_id": command_id,
                        },
                        "result": None,
                    }
                )
                return
            if command_id == "workbench.action.chat.open" and arguments and isinstance(arguments[0], dict):
                if arguments[0].get("query"):
                    self._send_json(
                        {
                            "ok": True,
                            "action_key": "probe-query-draft-ok",
                            "metadata": {
                                "ide_name": "Cursor",
                                "command_id": command_id,
                            },
                            "result": {"composerId": "draft-composer"},
                        }
                    )
                    return
            if command_id == "openwukong.testMutatingCommand":
                (workspace_path / "mutated.txt").write_text("changed", encoding="utf-8")
                self._send_json(
                    {
                        "ok": True,
                        "action_key": "probe-mutated",
                        "metadata": {
                            "ide_name": "Cursor",
                            "command_id": command_id,
                        },
                        "result": None,
                    }
                )
                return
            if command_id == "openwukong.testRuntimeLogMutation":
                log_path = workspace_path / "logs" / "runtime" / "probe.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text("runtime artifact", encoding="utf-8")
                self._send_json(
                    {
                        "ok": True,
                        "action_key": "probe-log-mutated",
                        "metadata": {
                            "ide_name": "Cursor",
                            "command_id": command_id,
                        },
                        "result": None,
                    }
                )
                return

            self._send_json(
                {
                    "ok": False,
                    "error": "bad_arguments",
                    "metadata": {
                        "command_id": command_id,
                    },
                },
                status=409,
            )
            return

        self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class IDEBridgeContractProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ContractProbeBridgeHandler.requests = []
        cls._server = socketserver.TCPServer(("127.0.0.1", 0), _ContractProbeBridgeHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=2)

    def setUp(self):
        _ContractProbeBridgeHandler.requests = []

    def test_detects_exact_chinese_windows_open_with_dialog_title(self):
        self.assertTrue(
            _system_dialog_detected(
                {
                    "available": True,
                    "hwnd": 300,
                    "title": "\u9009\u62e9\u5e94\u7528\u4ee5\u6253\u5f00",
                }
            )
        )

    def test_detects_codex_msix_electron_launch_error_dialog(self):
        self.assertTrue(
            _system_dialog_detected(
                {
                    "available": True,
                    "hwnd": 301,
                    "title": "Error",
                    "process_name": "Codex.exe",
                    "executable_path": (
                        "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/app/Codex.exe"
                    ),
                    "text": (
                        "Error launching app\n"
                        "Unable to find Electron app at "
                        "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                        "?type=click&tag=9560196064345231071\n"
                        "Cannot find module"
                    ),
                }
            )
        )

    def test_detects_codex_msix_attach_console_javascript_error_dialog(self):
        self.assertTrue(
            _system_dialog_detected(
                {
                    "available": True,
                    "hwnd": 303,
                    "title": "Error",
                    "process_name": "Codex.exe",
                    "executable_path": (
                        "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/app/Codex.exe"
                    ),
                    "child_texts": [
                        "A JavaScript error occurred in the main process",
                        "Uncaught Exception:",
                        "Error: AttachConsole failed",
                    ],
                }
            )
        )

    def test_generic_error_title_without_protocol_evidence_is_not_system_dialog(self):
        self.assertFalse(
            _system_dialog_detected(
                {
                    "available": True,
                    "hwnd": 302,
                    "title": "Error",
                }
            )
        )

    def test_select_probe_command_ids_uses_active_adapter_candidates(self):
        candidate_report = {
            "active_mapping": {
                "cursor": {
                    "commandCandidates": [
                        "composer.openComposer",
                        "composer.startComposerPrompt",
                        "composer.openComposer",
                    ]
                }
            },
            "cursor_review_candidates": ["aichat.newchataction"],
        }

        command_ids = select_probe_command_ids(candidate_report, adapter_id="cursor", max_commands=3)

        self.assertEqual(
            command_ids,
            [
                "composer.openComposer",
                "composer.startComposerPrompt",
                "aichat.newchataction",
            ],
        )

    def test_build_argument_variants_includes_safe_contract_shapes(self):
        variants = build_argument_variants("OPENWUKONG_PROBE_NO_EDIT")

        self.assertEqual(
            [variant.name for variant in variants],
            ["no_args", "string_message", "object_message", "query_object"],
        )
        self.assertEqual(variants[0].arguments, [])
        self.assertEqual(variants[1].arguments, ["OPENWUKONG_PROBE_NO_EDIT"])
        self.assertEqual(variants[2].arguments[0]["message"], "OPENWUKONG_PROBE_NO_EDIT")
        self.assertTrue(variants[2].arguments[0]["metadata"]["openwukong_contract_probe"])
        self.assertEqual(variants[3].arguments[0]["query"], "OPENWUKONG_PROBE_NO_EDIT")

    def test_build_probe_allowlist_settings_keeps_adapter_unselected_until_validated(self):
        settings = build_probe_allowlist_settings(
            ["composer.startComposerPrompt", "composer.sendToAgent", "composer.startComposerPrompt"],
            adapter_id="cursor",
            host="127.0.0.1",
            port=8792,
            auto_start=True,
        )

        self.assertEqual(settings["openwukong.bridge.host"], "127.0.0.1")
        self.assertEqual(settings["openwukong.bridge.port"], 8792)
        self.assertTrue(settings["openwukong.bridge.autoStart"])
        self.assertEqual(
            settings["openwukong.bridge.allowedCommands"],
            ["composer.startComposerPrompt", "composer.sendToAgent"],
        )
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "",
        )
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandCandidates"],
            ["composer.startComposerPrompt", "composer.sendToAgent"],
        )

    def test_probe_allowlist_settings_defaults_to_dynamic_port(self):
        settings = build_probe_allowlist_settings(
            ["composer.startComposerPrompt"],
            adapter_id="cursor",
        )

        self.assertEqual(settings["openwukong.bridge.port"], 0)

    def test_validated_bridge_settings_default_to_dynamic_port(self):
        settings = build_bridge_settings_from_probe_report(
            {
                "validated_mapping": {
                    "cursor": {
                        "label": "cursor",
                        "commandId": "composer.startComposerPrompt",
                        "commandCandidates": ["composer.startComposerPrompt"],
                    }
                }
            }
        )

        self.assertEqual(settings["openwukong.bridge.port"], 0)

    def test_probe_records_command_contract_and_control_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            focus = _FocusSequence(
                [
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                ]
            )

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["composer.startComposerPrompt"],
                message="OPENWUKONG_PROBE_NO_EDIT",
                request_timeout=2.0,
                focus_observer=focus,
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "ide-bridge-contract-probe")
        self.assertEqual(data["safety_mode"], "isolated_sacrificial_workspace")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 4)
        self.assertEqual(data["command_count"], 1)
        self.assertEqual(data["results"][0]["command_id"], "composer.startComposerPrompt")
        self.assertEqual(data["results"][0]["status"], "callable")
        self.assertEqual(data["results"][0]["accepted_variant"], "object_message")
        self.assertFalse(data["results"][0]["workspace_changed"])
        self.assertFalse(data["results"][0]["foreground_changed"])
        self.assertFalse(data["results"][0]["target_foreground"])
        self.assertTrue(data["background_execution_observed"])
        self.assertTrue(data["focus_stable"])
        self.assertTrue(data["results"][0]["attempts"][0]["focus_observation_available"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "composer.startComposerPrompt")
        self.assertEqual(
            data["validated_mapping"]["cursor"]["validation"]["acceptedVariant"],
            "object_message",
        )
        self.assertFalse(
            data["validated_mapping"]["cursor"]["validation"]["foregroundChanged"]
        )
        self.assertFalse(
            data["validated_mapping"]["cursor"]["validation"]["targetForeground"]
        )
        settings = build_bridge_settings_from_probe_report(
            data,
            host="127.0.0.1",
            port=8788,
            auto_start=True,
        )
        self.assertTrue(settings["openwukong.bridge.autoStart"])
        self.assertEqual(settings["openwukong.bridge.port"], 8788)
        self.assertEqual(
            settings["openwukong.bridge.allowedCommands"],
            ["composer.startComposerPrompt"],
        )
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "composer.startComposerPrompt",
        )
        self.assertEqual(len(_ContractProbeBridgeHandler.requests), 12)
        self.assertEqual(
            [path for path, _ in _ContractProbeBridgeHandler.requests][:3],
            ["/v1/ide/state", "/v1/ide/command", "/v1/ide/state"],
        )

    def test_probe_recommends_cursor_chat_open_query_contract(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            focus = _FocusSequence(
                [
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 100, "title": "Codex"},
                ]
            )

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["workbench.action.chat.open"],
                message="OPENWUKONG_CURSOR_DRAFT_NO_EDIT",
                request_timeout=2.0,
                variants=tuple(
                    v
                    for v in build_argument_variants("OPENWUKONG_CURSOR_DRAFT_NO_EDIT")
                    if v.name == "query_object"
                ),
                focus_observer=focus,
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "callable")
        self.assertEqual(result["accepted_variant"], "query_object")
        self.assertTrue(result["recommended_adapter"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "workbench.action.chat.open")
        self.assertEqual(
            data["validated_mapping"]["cursor"]["validation"]["acceptedVariant"],
            "query_object",
        )

    def test_probe_marks_mutating_command_as_not_recommended(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["openwukong.testMutatingCommand"],
                request_timeout=2.0,
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "mutating")
        self.assertTrue(result["workspace_changed"])
        self.assertFalse(result["recommended_adapter"])
        self.assertIn("mutated.txt", result["changed_files"])

    def test_probe_ignores_runtime_log_artifacts_when_detecting_workspace_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["openwukong.testRuntimeLogMutation"],
                request_timeout=2.0,
                variants=tuple(
                    v
                    for v in build_argument_variants("OPENWUKONG_PROBE_NO_EDIT")
                    if v.name == "no_args"
                ),
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "callable")
        self.assertFalse(result["workspace_changed"])
        self.assertEqual(result["changed_files"], [])

    def test_probe_marks_foreground_stealing_command_as_not_recommended(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            focus = _FocusSequence(
                [
                    {"hwnd": 100, "title": "Codex"},
                    {"hwnd": 200, "title": "Cursor"},
                ]
            )

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["composer.startComposerPrompt"],
                request_timeout=2.0,
                variants=tuple(v for v in build_argument_variants("OPENWUKONG_PROBE_NO_EDIT") if v.name == "object_message"),
                focus_observer=focus,
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "foreground_changed")
        self.assertTrue(result["foreground_changed"])
        self.assertFalse(result["workspace_changed"])
        self.assertFalse(result["recommended_adapter"])
        self.assertFalse(data["focus_stable"])
        self.assertFalse(data["background_execution_observed"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "")
        self.assertEqual(
            data["validated_mapping"]["cursor"]["validation"]["status"],
            "no_validated_object_message_contract",
        )

    def test_probe_does_not_recommend_when_target_is_already_foreground(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "probe-workspace"
            workspace.mkdir()
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            focus = _FocusSequence(
                [
                    {"hwnd": 200, "title": "[Extension Development Host] probe-workspace - Cursor"},
                    {"hwnd": 200, "title": "[Extension Development Host] probe-workspace - Cursor"},
                ]
            )

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["composer.startComposerPrompt"],
                request_timeout=2.0,
                variants=tuple(v for v in build_argument_variants("OPENWUKONG_PROBE_NO_EDIT") if v.name == "object_message"),
                focus_observer=focus,
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "target_foreground")
        self.assertTrue(result["target_foreground"])
        self.assertFalse(result["foreground_changed"])
        self.assertFalse(result["workspace_changed"])
        self.assertFalse(result["recommended_adapter"])
        self.assertTrue(data["focus_stable"])
        self.assertFalse(data["background_execution_observed"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "")
        self.assertTrue(
            data["validated_mapping"]["cursor"]["validation"]["targetForeground"]
        )

    def test_probe_marks_delayed_system_dialog_as_not_recommended(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            focus = _FocusSequence(
                [
                    {"hwnd": 100, "title": "Weixin"},
                    {"hwnd": 100, "title": "Weixin"},
                    {"hwnd": 300, "title": '选择应用以打开 "session-start"'},
                ]
            )

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["workbench.action.chat.open"],
                message="OPENWUKONG_CURSOR_DIALOG_PROBE_NO_EDIT",
                request_timeout=2.0,
                variants=tuple(
                    v
                    for v in build_argument_variants("OPENWUKONG_CURSOR_DIALOG_PROBE_NO_EDIT")
                    if v.name == "query_object"
                ),
                focus_observer=focus,
                post_action_observation_delay_sec=0.001,
            )
            data = report.to_dict()

        result = data["results"][0]
        self.assertEqual(result["status"], "system_dialog_opened")
        self.assertTrue(result["system_dialog_detected"])
        self.assertTrue(result["foreground_changed"])
        self.assertFalse(result["recommended_adapter"])
        self.assertFalse(data["background_execution_observed"])
        self.assertTrue(data["system_dialog_detected"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "")
        self.assertTrue(
            data["validated_mapping"]["cursor"]["validation"]["systemDialogDetected"]
        )

    def test_cli_writes_probe_report_json(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "workspace"
            workspace.mkdir()
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")
            candidate_report = Path(td) / "candidate_report.json"
            output_path = Path(td) / "contract_probe.json"
            candidate_report.write_text(
                json.dumps(
                    {
                        "active_mapping": {
                            "cursor": {
                                "commandCandidates": ["composer.startComposerPrompt"]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        self.bridge_url,
                        "--candidate-report",
                        str(candidate_report),
                        "--workspace-path",
                        str(workspace),
                        "--output",
                        str(output_path),
                        "--settings-output",
                        str(Path(td) / "settings.json"),
                        "--json",
                    ]
                )

            printed = json.loads(stdout.getvalue())
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            settings = json.loads((Path(td) / "settings.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["mode"], "ide-bridge-contract-probe")
        self.assertEqual(saved["results"][0]["accepted_variant"], "object_message")
        self.assertEqual(saved["control_attempts"], 4)
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "composer.startComposerPrompt",
        )

    def test_cli_can_filter_probe_variants(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "workspace"
            workspace.mkdir()
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        self.bridge_url,
                        "--workspace-path",
                        str(workspace),
                        "--command-id",
                        "composer.startComposerPrompt",
                        "--variant",
                        "object_message",
                        "--json",
                    ]
                )

            printed = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["control_attempts"], 1)
        self.assertEqual(printed["results"][0]["accepted_variants"], ["object_message"])

    def test_cli_can_write_probe_settings_without_contacting_bridge(self):
        with tempfile.TemporaryDirectory() as td:
            candidate_report = Path(td) / "candidate_report.json"
            settings_path = Path(td) / "User" / "settings.json"
            candidate_report.write_text(
                json.dumps(
                    {
                        "active_mapping": {
                            "cursor": {
                                "commandCandidates": [
                                    "composer.startComposerPrompt",
                                    "composer.sendToAgent",
                                ]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "http://127.0.0.1:9",
                        "--candidate-report",
                        str(candidate_report),
                        "--probe-settings-output",
                        str(settings_path),
                        "--write-probe-settings-only",
                        "--json",
                    ]
                )

            printed = json.loads(stdout.getvalue())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["mode"], "ide-bridge-probe-settings")
        self.assertEqual(printed["command_count"], 2)
        self.assertEqual(settings["openwukong.bridge.port"], 0)
        self.assertEqual(
            settings["openwukong.bridge.allowedCommands"],
            ["composer.startComposerPrompt", "composer.sendToAgent"],
        )
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "",
        )


class _FocusSequence:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture(self):
        if self.index >= len(self.snapshots):
            value = self.snapshots[-1]
        else:
            value = self.snapshots[self.index]
        self.index += 1
        return dict(value)


if __name__ == "__main__":
    unittest.main()
