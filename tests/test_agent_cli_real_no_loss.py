import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.agent_cli_real_no_loss import (
    StaticForegroundObserver,
    run_agent_cli_real_no_loss,
)


class _FakeExecutionResult:
    def __init__(self, *, ok=True, stdout="", stderr="", error="", exit_code=0):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.exit_code = exit_code

    def to_dict(self):
        return {
            "mode": "fake-command-execution",
            "ok": self.ok,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "control_attempts": 1 if self.exit_code is not None else 0,
        }


class _FakeCommandExecutor:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return self.result


class AgentCliRealNoLossTests(unittest.TestCase):
    def test_background_cli_success_is_verified_without_focus_or_workspace_mutation(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                stdout="OPENWUKONG_AGENT_CLI_NO_LOSS: PASS\nNo files changed."
            )
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=root,
                allow_cli_execution=True,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(before=100, after=100),
            )
            data = report.to_dict()
            case = data["cases"][0]
            artifact = json.loads(Path(case["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(data["mode"], "agent-cli-real-no-loss")
        self.assertEqual(data["total_cases"], 1)
        self.assertEqual(data["verified_cases"], 1)
        self.assertEqual(data["agent_command_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertTrue(data["foreground_focus_stable"])
        self.assertEqual(case["status"], "verified")
        self.assertTrue(case["passed"])
        self.assertTrue(case["real_verified"])
        self.assertEqual(case["agent_command_attempts"], 1)
        self.assertEqual(case["workspace_file_delta"], [])
        self.assertTrue(case["workspace_clean"])
        self.assertTrue(case["foreground_focus_stable"])
        self.assertEqual(len(executor.requests), 1)
        self.assertEqual(artifact["status"], "verified")

    def test_auth_failure_is_classified_without_marking_real_verified(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                ok=False,
                stderr="Not logged in - Please run /login",
                error="exit_code=1",
                exit_code=1,
            )
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=Path(td),
                allow_cli_execution=True,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(before=77, after=77),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(case["status"], "cli_auth_required")
        self.assertTrue(case["passed"])
        self.assertFalse(case["real_verified"])
        self.assertEqual(case["agent_command_attempts"], 1)
        self.assertEqual(case["window_input_attempts"], 0)

    def test_cli_probe_records_foreground_change_without_failing_when_no_window_input_happened(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                ok=False,
                stderr="Not logged in - Please run /login",
                error="exit_code=1",
                exit_code=1,
            )
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=Path(td),
                allow_cli_execution=True,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(before=77, after=99),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(case["status"], "cli_auth_required")
        self.assertTrue(case["passed"])
        self.assertFalse(case["foreground_focus_stable"])
        self.assertFalse(data["foreground_focus_stable"])
        self.assertEqual(data["failed_cases"], 0)
        self.assertEqual(case["window_input_attempts"], 0)

    def test_unrelated_foreground_change_is_not_classified_as_cli_focus_steal(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                ok=False,
                stderr="Not logged in - Please run /login",
                error="exit_code=1",
                exit_code=1,
            )
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=Path(td),
                allow_cli_execution=True,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(
                    before=77,
                    after=99,
                    before_process_name="Cursor.exe",
                    before_window_title="openwukong - Cursor",
                    after_process_name="Weixin.exe",
                    after_window_title="微信",
                ),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertFalse(case["foreground_focus_stable"])
        self.assertEqual(
            case["foreground_change_classification"],
            "changed_to_unrelated_surface",
        )
        self.assertTrue(case["foreground_no_steal_verified"])
        self.assertTrue(data["foreground_no_steal_verified"])
        self.assertEqual(case["foreground_snapshot_after"]["process_name"], "Weixin.exe")

    def test_agent_surface_foreground_change_is_classified_as_focus_steal_risk(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                ok=False,
                stderr="Not logged in - Please run /login",
                error="exit_code=1",
                exit_code=1,
            )
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=Path(td),
                allow_cli_execution=True,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(
                    before=77,
                    after=99,
                    before_process_name="Cursor.exe",
                    before_window_title="openwukong - Cursor",
                    after_process_name="Claude.exe",
                    after_window_title="Claude",
                ),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(
            case["foreground_change_classification"],
            "changed_to_agent_surface",
        )
        self.assertFalse(case["foreground_no_steal_verified"])
        self.assertFalse(data["foreground_no_steal_verified"])

    def test_access_denied_is_classified_for_unrunnable_codex_cli_alias(self):
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(
                ok=False,
                stderr="Program 'codex.exe' failed to run: Access is denied",
                error="Access is denied",
                exit_code=1,
            )
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("codex",),
                output_root=Path(td),
                allow_cli_execution=True,
                resolver=_resolver_with_codex_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(before=88, after=88),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(case["status"], "cli_access_denied")
        self.assertTrue(case["passed"])
        self.assertFalse(case["real_verified"])
        self.assertEqual(case["agent_command_attempts"], 1)
        self.assertEqual(case["workspace_file_delta"], [])

    def test_without_execution_opt_in_writes_dry_run_only(self):
        executor = _FakeCommandExecutor(_FakeExecutionResult())

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_cli_real_no_loss(
                agents=("claude",),
                output_root=Path(td),
                allow_cli_execution=False,
                resolver=_resolver_with_claude_cli(),
                command_executor=executor,
                foreground_observer=StaticForegroundObserver(before=1, after=1),
            )
            case = report.to_dict()["cases"][0]

        self.assertEqual(case["status"], "skipped_requires_cli_execution_opt_in")
        self.assertTrue(case["passed"])
        self.assertFalse(case["real_verified"])
        self.assertEqual(case["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)


def _resolver_with_claude_cli():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="path",
                        display_name="claude",
                        executable_name="claude.exe",
                        path="C:/Users/me/.local/bin/claude.exe",
                    ),
                ]
            ),
        )
    )


def _resolver_with_codex_cli():
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
