import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control import run_agent_conversation
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.agent_conversation_runner import main


class _FakeExecutionResult:
    def __init__(self, *, ok=True, stdout="", stderr="", error=""):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr
        self.error = error

    def to_dict(self):
        return {
            "mode": "fake-command-execution",
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
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


class _FakeAppSurfaceProbeReport:
    def __init__(self, **payload):
        self.payload = dict(payload)

    def to_dict(self):
        return dict(self.payload)


class AgentConversationTests(unittest.TestCase):
    def test_default_run_writes_targeted_conversation_draft_without_execution(self):
        resolver = _resolver_with_codex_cli()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="codex",
                project_name="openwukong",
                task_name="browser-search-smoke",
                message="Plan a no-op browser search validation.",
                acceptance_criteria=("No files are changed.", "Return a final PASS marker."),
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
                workspace_root=str(root),
                output_root=str(root / "out"),
                resolver=resolver,
                command_executor=executor,
            )
            data = report.to_dict()
            draft = json.loads(Path(data["draft_artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(data["mode"], "agent-conversation-runner")
        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "conversation_draft_written")
        self.assertEqual(data["project_name"], "openwukong")
        self.assertEqual(data["task_name"], "browser-search-smoke")
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertIn("Project: openwukong", data["composed_message"])
        self.assertIn("Task: browser-search-smoke", data["composed_message"])
        self.assertIn("OPENWUKONG_ACCEPTANCE: PASS", data["composed_message"])
        self.assertEqual(draft["mode"], "agent-conversation-draft")
        self.assertEqual(draft["project_name"], "openwukong")
        self.assertEqual(draft["task_name"], "browser-search-smoke")

    def test_confirmed_dry_run_builds_codex_command_with_targeted_message(self):
        resolver = _resolver_with_codex_cli()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="codex",
                project_name="openwukong",
                task_name="result-readback",
                message="Describe how you would verify the last run.",
                acceptance_criteria=("Explain the readback source.",),
                required_markers=("READBACK_READY",),
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
        self.assertEqual(data["decision"], "conversation_dry_run_ready")
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        argv = data["agent_task_report"]["command_plan"]["argv"]
        self.assertIn("exec", argv)
        self.assertIn("Project: openwukong", argv[-1])
        self.assertIn("Task: result-readback", argv[-1])
        self.assertIn("READBACK_READY", argv[-1])

    def test_confirmed_execute_accepts_result_when_required_markers_are_present(self):
        resolver = _resolver_with_codex_cli()
        executor = _FakeCommandExecutor(
            _FakeExecutionResult(stdout='{"msg":"OPENWUKONG_ACCEPTANCE: PASS"}\nREADBACK_READY')
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="codex",
                project_name="openwukong",
                task_name="fake-execute",
                message="Return the requested markers.",
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS", "READBACK_READY"),
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
        self.assertEqual(data["decision"], "conversation_executed_and_accepted")
        self.assertEqual(data["agent_command_attempts"], 1)
        self.assertTrue(data["acceptance_report"]["accepted"])
        self.assertEqual(data["acceptance_report"]["missing_required_markers"], [])

    def test_app_surface_execute_requires_foreground_or_native_bridge_without_command_attempt(self):
        resolver = _resolver_with_claude_desktop()
        executor = _FakeCommandExecutor()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="claude desktop",
                project_name="openwukong",
                task_name="desktop-message",
                message="Send this through the app surface.",
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

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_conversation_requires_app_bridge_or_foreground")
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertEqual(data["foreground_takeover_request"]["mode"], "foreground-takeover-request")
        self.assertEqual(data["foreground_takeover_request"]["action"], "send_agent_conversation_message")
        self.assertEqual(
            data["foreground_takeover_request"]["selected_transport"],
            "desktop-shell-native-bridge-or-foreground",
        )

    def test_app_surface_execute_runs_read_only_probe_diagnostics_when_bridge_required(self):
        resolver = _resolver_with_claude_desktop()
        executor = _FakeCommandExecutor()
        probe_calls = []

        def _fake_probe_runner(**kwargs):
            probe_calls.append(dict(kwargs))
            return _FakeAppSurfaceProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_app_window_not_found",
                agent=kwargs["agent"],
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                app_uia_probe={"decision": "agent_app_window_not_found"},
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="claude desktop",
                project_name="openwukong",
                task_name="desktop-message",
                message="Send this through the app surface.",
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
                app_surface_probe_runner=_fake_probe_runner,
            )
            data = report.to_dict()
            draft = json.loads(Path(data["draft_artifact_path"]).read_text(encoding="utf-8"))

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_conversation_requires_app_bridge_or_foreground")
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(len(executor.requests), 0)
        self.assertEqual(len(probe_calls), 1)
        self.assertEqual(probe_calls[0]["agent"], "claude desktop")
        self.assertEqual(probe_calls[0]["project_name"], "openwukong")
        self.assertEqual(probe_calls[0]["task_name"], "desktop-message")
        self.assertIs(probe_calls[0]["resolver"], resolver)
        self.assertEqual(data["app_surface_probe"]["mode"], "agent-native-connector-probe")
        self.assertEqual(data["app_surface_probe"]["decision"], "agent_app_window_not_found")
        self.assertEqual(data["app_surface_probe"]["control_attempts"], 0)
        self.assertEqual(draft["app_surface_probe"]["decision"], "agent_app_window_not_found")

    def test_app_surface_probe_receives_screenshot_dir_when_requested(self):
        resolver = _resolver_with_claude_desktop()
        executor = _FakeCommandExecutor()
        probe_calls = []

        def _fake_probe_runner(**kwargs):
            probe_calls.append(dict(kwargs))
            return _FakeAppSurfaceProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                control_allowed=False,
                control_attempts=0,
                app_uia_probe={
                    "background_screenshot_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            screenshot_dir = root / "screenshots"
            report = run_agent_conversation(
                agent="claude desktop",
                project_name="openwukong",
                task_name="desktop-message",
                message="Send this through the app surface.",
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
                app_surface_probe_runner=_fake_probe_runner,
                app_surface_screenshot_dir=str(screenshot_dir),
            )
            data = report.to_dict()

        self.assertEqual(len(probe_calls), 1)
        self.assertEqual(probe_calls[0]["screenshot_dir"], str(screenshot_dir))
        self.assertEqual(
            data["app_surface_probe"]["app_uia_probe"]["background_screenshot_count"],
            1,
        )

    def test_app_surface_probe_ready_attaches_bridge_dry_run_contract(self):
        resolver = _resolver_with_claude_desktop()
        executor = _FakeCommandExecutor()

        def _fake_probe_runner(**kwargs):
            del kwargs
            return _ready_native_bridge_probe()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_conversation(
                agent="claude desktop",
                project_name="openwukong",
                task_name="desktop-message",
                message="Send this through the app surface.",
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
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
                app_surface_probe_runner=_fake_probe_runner,
            )
            data = report.to_dict()
            draft = json.loads(Path(data["draft_artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(data["decision"], "agent_conversation_requires_app_bridge_or_foreground")
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(data["app_bridge_dry_run"]["decision"], "app_bridge_dry_run_ready")
        self.assertEqual(data["app_bridge_dry_run"]["bridge_send_attempts"], 0)
        self.assertEqual(
            data["app_bridge_dry_run"]["request"]["payload"]["required_markers"],
            ["OPENWUKONG_ACCEPTANCE: PASS"],
        )
        self.assertEqual(
            draft["app_bridge_dry_run"]["request"]["target"]["hwnd"],
            138024,
        )

    def test_main_writes_json_report(self):
        resolver = _resolver_with_codex_cli()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-conversation.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "cli-main",
                        "--message",
                        "Draft a message.",
                        "--acceptance-marker",
                        "OPENWUKONG_ACCEPTANCE: PASS",
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
        self.assertEqual(payload["mode"], "agent-conversation-runner")
        self.assertEqual(payload["decision"], "conversation_draft_written")
        self.assertEqual(payload["agent_command_attempts"], 0)

    def test_main_attaches_app_surface_probe_for_app_execute_request(self):
        resolver = _resolver_with_claude_desktop()
        probe_calls = []

        def _fake_probe_runner(**kwargs):
            probe_calls.append(dict(kwargs))
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_native_connector_not_exposed",
                "control_allowed": False,
                "control_attempts": 0,
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-conversation.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "claude desktop",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "desktop-message",
                        "--message",
                        "Draft a message.",
                        "--workspace-root",
                        str(root),
                        "--output-root",
                        str(root / "out"),
                        "--execute",
                        "--allow-agent-task",
                        "--confirm-effect",
                        "agent_task_submission.submit_task",
                        "--confirm-effect",
                        "agent_start.start_agent",
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: resolver,
                    app_surface_probe_runner=_fake_probe_runner,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["decision"], "agent_conversation_requires_app_bridge_or_foreground")
        self.assertEqual(payload["agent_command_attempts"], 0)
        self.assertEqual(payload["app_surface_probe"]["mode"], "agent-native-connector-probe")
        self.assertEqual(payload["app_surface_probe"]["decision"], "agent_native_connector_not_exposed")
        self.assertEqual(len(probe_calls), 1)
        self.assertEqual(probe_calls[0]["agent"], "claude desktop")

    def test_main_passes_app_surface_screenshot_dir_to_probe_runner(self):
        resolver = _resolver_with_claude_desktop()
        probe_calls = []

        def _fake_probe_runner(**kwargs):
            probe_calls.append(dict(kwargs))
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_native_connector_not_exposed",
                "control_allowed": False,
                "control_attempts": 0,
                "app_uia_probe": {
                    "background_screenshot_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-conversation.json"
            screenshot_dir = root / "screenshots"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "claude desktop",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "desktop-message",
                        "--message",
                        "Draft a message.",
                        "--workspace-root",
                        str(root),
                        "--output-root",
                        str(root / "out"),
                        "--execute",
                        "--allow-agent-task",
                        "--confirm-effect",
                        "agent_task_submission.submit_task",
                        "--confirm-effect",
                        "agent_start.start_agent",
                        "--app-surface-screenshot-dir",
                        str(screenshot_dir),
                        "--output",
                        str(output),
                        "--json",
                    ],
                    resolver_factory=lambda args: resolver,
                    app_surface_probe_runner=_fake_probe_runner,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(len(probe_calls), 1)
        self.assertEqual(probe_calls[0]["screenshot_dir"], str(screenshot_dir))
        self.assertEqual(
            payload["app_surface_probe"]["app_uia_probe"]["background_screenshot_count"],
            1,
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


def _resolver_with_claude_desktop():
    return WindowsAppResolver(
        candidate_providers=(
            StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="start-apps",
                        display_name="Claude",
                        metadata={"app_id": "Claude_pzs8sxrjxfjjc!Claude"},
                    ),
                ]
            ),
        )
    )


def _ready_native_bridge_probe():
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_ready",
        "control_allowed": False,
        "control_attempts": 0,
        "endpoint_count": 1,
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "debugger_url": "http://127.0.0.1:9333",
                "ready": True,
                "targets": [
                    {
                        "target_id": "page-1",
                        "title": "Claude",
                        "url": "app://claude/index.html",
                        "ready": True,
                    }
                ],
            }
        ],
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "semantic_composer_count": 1,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "claude.exe",
                    "pid": 77064,
                    "window_title": "Claude",
                    "hwnd": 138024,
                }
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
