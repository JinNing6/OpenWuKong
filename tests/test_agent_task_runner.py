import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control import run_agent_task
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.agent_task_runner import main


class _FakeExecutionResult:
    def __init__(self, *, ok=True, stdout="ok", error=""):
        self.ok = ok
        self.stdout = stdout
        self.error = error

    def to_dict(self):
        return {
            "mode": "fake-command-execution",
            "ok": self.ok,
            "stdout": self.stdout,
            "error": self.error,
            "control_attempts": 1,
        }


class _FakeCommandExecutor:
    def __init__(self, result=None):
        self.requests = []
        self.result = result or _FakeExecutionResult()

    def execute(self, request):
        self.requests.append(request)
        return self.result


class AgentTaskRunnerTests(unittest.TestCase):
    def test_default_run_writes_draft_without_executing_claude(self):
        resolver = _resolver_with_claude()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_task(
                agent="claude",
                task="summarize this repository without editing files",
                workspace_root=str(root),
                output_root=str(root / "out"),
                resolver=resolver,
                command_executor=executor,
            )
            data = report.to_dict()
            draft_path = Path(data["draft_artifact_path"])
            draft = json.loads(draft_path.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "draft_written")
        self.assertEqual(data["safety_mode"], "draft_only")
        self.assertFalse(data["execution_requested"])
        self.assertFalse(data["execution_attempted"])
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertEqual(data["selected_transport"]["transport_id"], "claude-code-cli-managed-terminal")
        self.assertEqual(data["command_plan"]["argv"][1:4], ["-p", "--permission-mode", "plan"])
        self.assertIn("--no-session-persistence", data["command_plan"]["argv"])
        self.assertEqual(draft["task"], "summarize this repository without editing files")
        self.assertEqual(draft["execution_allowed"], False)

    def test_execute_is_blocked_until_agent_effects_are_confirmed(self):
        resolver = _resolver_with_codex()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_task(
                agent="codex",
                task="list the files you would inspect",
                workspace_root=str(root),
                output_root=str(root / "out"),
                execute=True,
                resolver=resolver,
                command_executor=executor,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_task_confirmation_required")
        self.assertTrue(data["execution_requested"])
        self.assertFalse(data["execution_attempted"])
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertEqual(
            data["side_effect_gate"]["confirmation_required_effect_ids"],
            ["agent_task_submission.submit_task", "agent_start.start_agent"],
        )
        self.assertIn("exec", data["command_plan"]["argv"])
        self.assertLess(
            data["command_plan"]["argv"].index("--ask-for-approval"),
            data["command_plan"]["argv"].index("exec"),
        )
        self.assertLess(
            data["command_plan"]["argv"].index("--sandbox"),
            data["command_plan"]["argv"].index("exec"),
        )
        self.assertIn("--sandbox", data["command_plan"]["argv"])
        self.assertIn("read-only", data["command_plan"]["argv"])
        self.assertIn("--ask-for-approval", data["command_plan"]["argv"])
        self.assertIn("never", data["command_plan"]["argv"])
        self.assertIn("--skip-git-repo-check", data["command_plan"]["argv"])
        self.assertIn("--ephemeral", data["command_plan"]["argv"])
        self.assertIn("--ignore-rules", data["command_plan"]["argv"])
        self.assertIn("--json", data["command_plan"]["argv"])
        self.assertIn("-C", data["command_plan"]["argv"])

    def test_dry_run_with_confirmed_effects_builds_command_but_does_not_execute(self):
        resolver = _resolver_with_claude()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_task(
                agent="claude code",
                task="plan a no-op smoke test",
                workspace_root=str(root),
                output_root=str(root / "out"),
                execute=True,
                dry_run=True,
                allow_agent_task=True,
                confirmed_effect_ids=(
                    "agent_task_submission.submit_task",
                    "agent_start.start_agent",
                ),
                resolver=resolver,
                command_executor=executor,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "dry_run_ready")
        self.assertEqual(data["safety_mode"], "dry_run")
        self.assertFalse(data["execution_attempted"])
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertEqual(data["side_effect_gate"]["decision"], "allow")
        self.assertEqual(data["command_plan"]["argv"][-1], "plan a no-op smoke test")

    def test_confirmed_execute_calls_injected_command_executor(self):
        resolver = _resolver_with_claude()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_task(
                agent="claude",
                task="return a one-line health check",
                workspace_root=str(root),
                output_root=str(root / "out"),
                execute=True,
                allow_agent_task=True,
                confirmed_effect_ids=(
                    "agent_task_submission.submit_task",
                    "agent_start.start_agent",
                ),
                resolver=resolver,
                command_executor=executor,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "executed")
        self.assertTrue(data["execution_attempted"])
        self.assertEqual(data["agent_command_attempts"], 1)
        self.assertEqual(len(executor.requests), 1)
        self.assertEqual(executor.requests[0].effects, ("read", "workspace_write", "network"))
        self.assertEqual(data["execution_report"]["mode"], "fake-command-execution")

    def test_main_writes_json_draft(self):
        resolver = _resolver_with_claude()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-task.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "claude",
                        "--task",
                        "draft only",
                        "--workspace-root",
                        str(root),
                        "--output-root",
                        str(root / "out"),
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: resolver,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "agent-task-runner")
        self.assertEqual(payload["decision"], "draft_written")
        self.assertEqual(payload["agent_command_attempts"], 0)


def _resolver_with_claude():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="path",
                        display_name="claude",
                        executable_name="claude.cmd",
                        path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                    ),
                ]
            ),
        )
    )


def _resolver_with_codex():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="path",
                        display_name="codex",
                        executable_name="codex.exe",
                        path="C:/Users/me/AppData/Local/OpenAI/Codex/bin/958d608/codex.exe",
                    ),
                ]
            ),
        )
    )


if __name__ == "__main__":
    unittest.main()
