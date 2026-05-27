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
    build_argument_variants,
    main,
    probe_ide_command_contracts,
    select_probe_command_ids,
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

        self.assertEqual([variant.name for variant in variants], ["no_args", "string_message", "object_message"])
        self.assertEqual(variants[0].arguments, [])
        self.assertEqual(variants[1].arguments, ["OPENWUKONG_PROBE_NO_EDIT"])
        self.assertEqual(variants[2].arguments[0]["message"], "OPENWUKONG_PROBE_NO_EDIT")
        self.assertTrue(variants[2].arguments[0]["metadata"]["openwukong_contract_probe"])

    def test_probe_records_command_contract_and_control_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "README.md").write_text("probe workspace", encoding="utf-8")

            report = probe_ide_command_contracts(
                self.bridge_url,
                workspace_path=str(workspace),
                command_ids=["composer.startComposerPrompt"],
                message="OPENWUKONG_PROBE_NO_EDIT",
                request_timeout=2.0,
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "ide-bridge-contract-probe")
        self.assertEqual(data["safety_mode"], "isolated_sacrificial_workspace")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 3)
        self.assertEqual(data["command_count"], 1)
        self.assertEqual(data["results"][0]["command_id"], "composer.startComposerPrompt")
        self.assertEqual(data["results"][0]["status"], "callable")
        self.assertEqual(data["results"][0]["accepted_variant"], "object_message")
        self.assertFalse(data["results"][0]["workspace_changed"])
        self.assertEqual(data["validated_mapping"]["cursor"]["commandId"], "composer.startComposerPrompt")
        self.assertEqual(
            data["validated_mapping"]["cursor"]["validation"]["acceptedVariant"],
            "object_message",
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
        self.assertEqual(
            [path for path, _ in _ContractProbeBridgeHandler.requests],
            [
                "/v1/ide/state",
                "/v1/ide/command",
                "/v1/ide/state",
                "/v1/ide/state",
                "/v1/ide/command",
                "/v1/ide/state",
                "/v1/ide/state",
                "/v1/ide/command",
                "/v1/ide/state",
            ],
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
        self.assertEqual(saved["control_attempts"], 3)
        self.assertEqual(
            settings["openwukong.bridge.chatAdapters"]["cursor"]["commandId"],
            "composer.startComposerPrompt",
        )


if __name__ == "__main__":
    unittest.main()
