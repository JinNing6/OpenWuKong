import os
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget, TerminalCommandConnector


class TerminalConnectorTests(unittest.TestCase):
    def test_terminal_connector_supports_terminal_process(self):
        connector = TerminalCommandConnector()
        target = ConnectorTarget(process_name="powershell.exe")
        self.assertTrue(connector.supports_target(target))

    def test_terminal_connector_uses_workspace_path_as_cwd(self):
        connector = TerminalCommandConnector()
        with tempfile.TemporaryDirectory() as td:
            target = ConnectorTarget(workspace_path=td, workspace_hint="terminal")
            result = connector.send_message(target, "(Get-Location).Path")
            self.assertTrue(result.success, result.error)
            self.assertIn(os.path.basename(td).lower(), result.payload["stdout"].lower())

    def test_terminal_connector_transcript_contains_command_and_output(self):
        connector = TerminalCommandConnector()
        target = ConnectorTarget(workspace_hint="terminal")
        result = connector.send_message(target, 'Write-Output "terminal-transcript-ok"')
        self.assertTrue(result.success, result.error)
        transcript = connector.read_conversation(target)
        self.assertIn("terminal-transcript-ok", transcript)
        self.assertIn("$ Write-Output", transcript)

    def test_terminal_connector_persists_set_location_between_commands(self):
        connector = TerminalCommandConnector()
        with tempfile.TemporaryDirectory() as td:
            child = os.path.join(td, "child")
            os.mkdir(child)
            target = ConnectorTarget(workspace_path=td, workspace_hint="terminal")

            cd_result = connector.send_message(target, "Set-Location child")
            pwd_result = connector.send_message(target, "(Get-Location).Path")

            self.assertTrue(cd_result.success, cd_result.error)
            self.assertTrue(pwd_result.success, pwd_result.error)
            self.assertTrue(os.path.samefile(pwd_result.payload["cwd"], child))
            self.assertIn("child", pwd_result.payload["stdout"].lower())

    def test_terminal_connector_timeout_kills_command_and_records_failure(self):
        connector = TerminalCommandConnector(command_timeout=0.2)
        target = ConnectorTarget(workspace_hint="terminal-timeout")

        result = connector.send_message(
            target,
            'Start-Sleep -Seconds 5; Write-Output "late-output"',
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "timeout")
        self.assertEqual(result.payload["exit_code"], None)
        self.assertEqual(result.payload["timeout_sec"], 0.2)
        self.assertNotIn("late-output", result.payload["stdout"])
        transcript = connector.read_conversation(target)
        self.assertIn("[timeout] 0.2s", transcript)

    def test_terminal_connector_payload_exposes_native_session_contract(self):
        connector = TerminalCommandConnector(command_timeout=5.0)
        target = ConnectorTarget(workspace_hint="terminal-contract")

        result = connector.send_message(target, 'Write-Output "contract-ok"')

        self.assertTrue(result.success, result.error)
        self.assertEqual(result.payload["route_id"], "terminal-native-session")
        self.assertEqual(result.payload["transport"], "managed-powershell-subprocess")
        self.assertEqual(result.payload["shell"], "powershell.exe")
        self.assertIn("session_key", result.payload)
        self.assertEqual(result.payload["command_index"], 1)

    def test_terminal_connector_executes_through_command_runner_audit(self):
        with tempfile.TemporaryDirectory() as td:
            audit_path = Path(td) / "terminal-audit.jsonl"
            connector = TerminalCommandConnector(
                command_timeout=5.0,
                audit_log_path=str(audit_path),
            )
            target = ConnectorTarget(workspace_path=td, workspace_hint="terminal-audit")

            result = connector.send_message(target, 'Write-Output "terminal-runner-ok"')

            self.assertTrue(result.success, result.error)
            self.assertEqual(result.payload["runner_mode"], "command-intelligence-execution")
            self.assertIn("request_id", result.payload)
            self.assertTrue(audit_path.is_file())
            audit = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(audit["result"]["exit_code"], 0)
            self.assertEqual(audit["result"]["control_attempts"], 1)
            self.assertIn("-Command", audit["request"]["argv"])
            self.assertIn("terminal-runner-ok", result.payload["stdout"])


if __name__ == "__main__":
    unittest.main()
