import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control import build_agent_surface_binding
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.agent_surface_report import (
    build_agent_surface_report,
    main,
)


class AgentSurfaceReportTests(unittest.TestCase):
    def test_agent_surface_binding_is_exported_from_control_package(self):
        self.assertTrue(callable(build_agent_surface_binding))

    def test_codex_surface_prefers_standalone_cli_over_desktop_shell_for_background(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="Codex.exe",
                            process_name="Codex.exe",
                            executable_name="Codex.exe",
                            path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                            pid=3001,
                        ),
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="codex.exe",
                            process_name="codex.exe",
                            executable_name="codex.exe",
                            path="C:/Users/me/AppData/Local/OpenAI/Codex/bin/958d608/codex.exe",
                            pid=3002,
                        ),
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="codex.exe",
                            process_name="codex.exe",
                            executable_name="codex.exe",
                            path="C:/Users/me/.cursor/extensions/openai.chatgpt/bin/codex.exe",
                            pid=3003,
                        ),
                    ]
                ),
            )
        )

        data = build_agent_surface_report(["codex"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertEqual(data["mode"], "agent-surface-report")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["summary"]["resolved"], 1)
        self.assertEqual(surface["agent_id"], "codex")
        self.assertEqual(surface["selected_transport"]["transport_id"], "codex-cli-managed-terminal")
        self.assertTrue(surface["selected_transport"]["background_capable"])
        self.assertFalse(surface["selected_transport"]["execution_allowed"])
        self.assertEqual(
            [transport["transport_id"] for transport in surface["transports"]],
            [
                "codex-cli-managed-terminal",
                "codex-desktop-shell",
                "codex-extension-worker",
            ],
        )
        self.assertEqual(
            surface["side_effect_gate"]["decision"],
            "side_effect_confirmation_required",
        )
        self.assertEqual(
            surface["side_effect_gate"]["confirmation_required_effect_ids"],
            ["agent_task_submission.submit_task", "agent_start.start_agent"],
        )

    def test_codex_app_alias_selects_desktop_shell_not_cli(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="Codex.exe",
                            process_name="Codex.exe",
                            executable_name="Codex.exe",
                            path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                            pid=3001,
                        ),
                        AppResolutionCandidate(
                            source="path",
                            display_name="codex",
                            executable_name="codex.cmd",
                            path="C:/Users/me/AppData/Roaming/npm/codex.cmd",
                        ),
                    ]
                ),
            )
        )

        data = build_agent_surface_report(["codex app"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertEqual(surface["agent_id"], "codex")
        self.assertEqual(surface["selected_transport"]["transport_id"], "codex-desktop-shell")
        self.assertFalse(surface["selected_transport"]["background_capable"])
        self.assertFalse(surface["selected_transport"]["execution_allowed"])
        self.assertEqual(
            [transport["transport_id"] for transport in surface["transports"]],
            ["codex-desktop-shell"],
        )

    def test_claude_surface_uses_code_cli_managed_terminal(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="path",
                            display_name="claude",
                            executable_name="claude.cmd",
                            path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                        ),
                        AppResolutionCandidate(
                            source="start-menu",
                            display_name="Claude Opus 4.6 Thinking",
                            path="C:/Start Menu/Claude Opus 4.6 Thinking.lnk",
                        ),
                    ]
                ),
            )
        )

        data = build_agent_surface_report(["claude code"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertEqual(surface["agent_id"], "claude")
        self.assertEqual(surface["app_resolution"]["resolution"]["app_id"], "claude")
        self.assertEqual(surface["selected_transport"]["transport_id"], "claude-code-cli-managed-terminal")
        self.assertEqual(surface["selected_transport"]["command_family"], "claude -p")
        self.assertTrue(surface["selected_transport"]["background_capable"])
        self.assertFalse(surface["selected_transport"]["execution_allowed"])
        self.assertEqual(
            [transport["display_name"] for transport in surface["transports"]],
            ["Claude Code CLI"],
        )

    def test_claude_generic_surface_reports_cli_and_desktop_but_prefers_background_cli(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="path",
                            display_name="claude",
                            executable_name="claude.cmd",
                            path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                        ),
                        AppResolutionCandidate(
                            source="start-apps",
                            display_name="Claude",
                            metadata={"app_id": "Claude_pzs8sxrjxfjjc!Claude"},
                        ),
                    ]
                ),
            )
        )

        data = build_agent_surface_report(["claude"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertEqual(surface["selected_transport"]["transport_id"], "claude-code-cli-managed-terminal")
        self.assertTrue(surface["selected_transport"]["background_capable"])
        self.assertEqual(
            [transport["transport_id"] for transport in surface["transports"]],
            ["claude-code-cli-managed-terminal", "claude-desktop-shell"],
        )

    def test_claude_desktop_alias_selects_app_surface_not_cli(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="path",
                            display_name="claude",
                            executable_name="claude.cmd",
                            path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                        ),
                        AppResolutionCandidate(
                            source="start-apps",
                            display_name="Claude",
                            metadata={"app_id": "Claude_pzs8sxrjxfjjc!Claude"},
                        ),
                    ]
                ),
            )
        )

        data = build_agent_surface_report(["claude desktop"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertEqual(surface["agent_id"], "claude")
        self.assertEqual(surface["selected_transport"]["transport_id"], "claude-desktop-shell")
        self.assertEqual(surface["selected_transport"]["path"], "Claude_pzs8sxrjxfjjc!Claude")
        self.assertFalse(surface["selected_transport"]["background_capable"])
        self.assertFalse(surface["selected_transport"]["execution_allowed"])
        self.assertEqual(
            surface["selected_transport"]["notes"],
            ["app_task_submit_requires_native_bridge_or_foreground_takeover"],
        )
        self.assertEqual(
            [transport["transport_id"] for transport in surface["transports"]],
            ["claude-desktop-shell"],
        )

    def test_claude_desktop_alias_is_not_satisfied_by_cli_only(self):
        resolver = WindowsAppResolver(
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

        data = build_agent_surface_report(["claude app"], resolver=resolver).to_dict()
        surface = data["agents"][0]

        self.assertFalse(surface["ok"])
        self.assertEqual(surface["decision"], "agent_transport_not_ready")
        self.assertEqual(surface["transports"], [])

    def test_main_writes_json_without_control_attempts(self):
        resolver = WindowsAppResolver(
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

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "agent-surfaces.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["--agent", "claude", "--output", str(output), "--json"],
                    resolver_factory=lambda args: resolver,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "agent-surface-report")
        self.assertEqual(payload["control_attempts"], 0)
        self.assertEqual(payload["agents"][0]["selected_transport"]["transport_id"], "claude-code-cli-managed-terminal")


if __name__ == "__main__":
    unittest.main()
