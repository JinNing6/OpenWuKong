import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget, GitCommandConnector


class GitConnectorTests(unittest.TestCase):
    def test_git_connector_supports_git_process(self):
        connector = GitCommandConnector()
        target = ConnectorTarget(process_name="git.exe")
        self.assertTrue(connector.supports_target(target))

    def test_git_connector_runs_status_in_workspace(self):
        connector = GitCommandConnector()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True, text=True)
            with open(os.path.join(td, "tracked.txt"), "w", encoding="utf-8") as handle:
                handle.write("hello")
            target = ConnectorTarget(workspace_path=td, workspace_hint="git")
            result = connector.send_message(target, "git status --short")
            self.assertTrue(result.success, result.error)
            self.assertIn("tracked.txt", result.payload["stdout"])

    def test_git_connector_transcript_contains_git_output(self):
        connector = GitCommandConnector()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True, text=True)
            target = ConnectorTarget(workspace_path=td, workspace_hint="git")
            result = connector.send_message(target, "git rev-parse --is-inside-work-tree")
            self.assertTrue(result.success, result.error)
            transcript = connector.read_conversation(target)
            self.assertIn("true", transcript.lower())
            self.assertIn("$ git rev-parse", transcript)

    def test_git_connector_executes_through_command_runner_audit(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True, text=True)
            audit_path = Path(td) / "git-audit.jsonl"
            connector = GitCommandConnector(audit_log_path=str(audit_path))
            target = ConnectorTarget(workspace_path=td, workspace_hint="git-audit")

            result = connector.send_message(target, "git status --short")

            self.assertTrue(result.success, result.error)
            self.assertEqual(result.payload["runner_mode"], "command-intelligence-execution")
            self.assertIn("request_id", result.payload)
            self.assertTrue(audit_path.is_file())
            audit = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(audit["request"]["argv"][:2], ["git", "status"])
            self.assertEqual(audit["result"]["exit_code"], 0)
            self.assertEqual(audit["result"]["control_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
