import subprocess
import sys
import tempfile
import unittest

from openwukong.connectors import (
    ConnectorActionResult,
    GitCommandConnector,
    ConnectorManager,
    ConnectorTarget,
    SessionConnector,
    TerminalCommandConnector,
)
from openwukong.control.command_planner import CommandPlanIntent
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
)


class _FakeBrowserActionReport:
    def __init__(self, *, ok=True, control_attempts=1, error=""):
        self.ok = ok
        self.error = error
        self._control_attempts = control_attempts

    def to_dict(self):
        return {
            "mode": "browser-devtools-action",
            "safety_mode": "gated_browser_devtools_action",
            "ok": self.ok,
            "control_allowed": True,
            "control_attempts": self._control_attempts,
            "action": "navigate_url",
            "error": self.error,
        }


class _FakeBrowserActionRunner:
    def __init__(self, report=None):
        self.report = report or _FakeBrowserActionReport()
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return self.report


class _FakeTerminalConnector(SessionConnector):
    connector_id = "terminal"
    route_id = "terminal-native-session"
    display_name = "Fake Terminal"

    def __init__(self):
        self.calls = []

    def supports_target(self, target: ConnectorTarget) -> bool:
        return bool(target.workspace_path)

    def read_conversation(self, target: ConnectorTarget) -> str:
        del target
        return ""

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        self.calls.append(
            {
                "workspace_path": target.workspace_path,
                "message": message,
                "cooldown": cooldown,
            }
        )
        return ConnectorActionResult(
            success=True,
            connector_id=self.connector_id,
            action="send_message",
            action_key="terminal:1",
            payload={
                "mode": "connector-action",
                "control_attempts": 1,
                "stdout": "terminal-ok",
            },
        )


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements=()):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=tuple(elements),
    )


class ControlFabricExecutionTests(unittest.TestCase):
    def test_execute_requires_explicit_control_permission(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-execution")
        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertEqual(runner.calls, [])

    def test_execute_runs_ready_browser_devtools_action_behind_dispatch_gate(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(
                action="navigate_url",
                url="https://www.bing.com/search?q=openwukong",
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "browser-devtools-or-extension")
        self.assertEqual(data["selected_connector_id"], "browser")
        self.assertEqual(data["action_report"]["mode"], "browser-devtools-action")
        self.assertEqual(data["transport_gate_decision"], "allow")
        self.assertEqual(
            data["dispatch_report"]["transport_capability_level"],
            "background-native",
        )
        self.assertEqual(len(runner.calls), 1)
        call = runner.calls[0]
        self.assertEqual(call["debugger_url"], "http://127.0.0.1:9222")
        self.assertEqual(call["window_title"], "about:blank - Google Chrome")
        self.assertEqual(call["resource_url"], "about:blank")
        self.assertEqual(call["action"], "navigate_url")
        self.assertEqual(call["url"], "https://www.bing.com/search?q=openwukong")

    def test_execute_blocks_ready_browser_action_when_owned_session_is_required(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors(
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "owned_session_required")
        self.assertTrue(data["ownership_required"])
        self.assertFalse(data["ownership"]["owned"])
        self.assertEqual(runner.calls, [])

    def test_execute_allows_owned_browser_action_matched_from_ownership_index(self):
        runner = _FakeBrowserActionRunner()
        ownership = SessionOwnership(
            owned=True,
            ownership_source="session_readiness_manifest",
            manifest_path="browser.json",
            route_id="browser-devtools-or-extension",
            connector_id="browser",
            action_id="launch_browser_devtools_isolated",
            pid=4242,
            endpoint="http://127.0.0.1:9222",
            profile_path="E:/tmp/openwukong-owned-browser",
            cleanup_ready=True,
        )
        fabric = ControlFabric.with_default_connectors(
            ownership_index=SessionOwnershipIndex((ownership,)),
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
                debugger_url="http://127.0.0.1:9222",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["manifest_path"], "browser.json")
        self.assertEqual(len(runner.calls), 1)

    def test_execute_runs_ready_terminal_connector_through_fabric(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(
                action="run_command",
                text="pwd",
                preferred_route_id="terminal-native-session",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["selected_route"], "terminal-native-session")
        self.assertEqual(data["selected_connector_id"], "terminal")
        self.assertEqual(data["action_report"]["connector_id"], "terminal")
        self.assertEqual(data["action_report"]["payload"]["stdout"], "terminal-ok")
        self.assertEqual(connector.calls[0]["message"], "pwd")

    def test_execute_does_not_call_connector_when_side_effect_gate_blocks(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
        )

        with tempfile.TemporaryDirectory() as td:
            report = fabric.execute(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="PowerShell",
                    workspace_path=td,
                ),
                ControlIntent(
                    action="run_command",
                    text="Write-Output unsafe-write",
                    preferred_route_id="terminal-native-session",
                    side_effect_policy=build_side_effect_policy(
                        blocked_effect_ids=("file_modify.modify_file",),
                    ),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "side_effect_confirmation_required")
        self.assertEqual(data["dispatch_report"]["decision"], "side_effect_confirmation_required")
        self.assertEqual(connector.calls, [])

    def test_execute_blocks_terminal_connector_when_owned_session_is_required(self):
        connector = _FakeTerminalConnector()
        fabric = ControlFabric(
            connector_manager=ConnectorManager([connector]),
            require_connector_session_ready=True,
            require_owned_session_for_execution=True,
        )

        report = fabric.execute(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="PowerShell",
                workspace_path=".",
            ),
            ControlIntent(
                action="run_command",
                text="pwd",
                preferred_route_id="terminal-native-session",
            ),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["error"], "owned_session_required")
        self.assertEqual(connector.calls, [])

    def test_execute_refuses_browser_action_when_dispatch_gate_is_not_ready(self):
        runner = _FakeBrowserActionRunner()
        fabric = ControlFabric.with_default_connectors()

        report = fabric.execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Chrome",
            ),
            ControlIntent(action="navigate_url", url="https://example.test/search"),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "dispatch_gate_not_ready")
        self.assertEqual(data["dispatch_report"]["decision"], "connector_required")
        self.assertEqual(runner.calls, [])

    def test_execute_blocks_foreground_required_transport_before_action_runner(self):
        fabric = ControlFabric()

        report = fabric.execute(
            _window(
                "Weixin.exe",
                "微信",
                [_element("Pane"), _element("TitleBar")],
            ),
            ControlIntent(action="send_message", text="probe"),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "foreground_takeover_confirmation_required")
        self.assertEqual(
            data["transport_gate_decision"],
            "blocked_foreground_takeover_required",
        )
        self.assertEqual(
            data["dispatch_report"]["transport_capability_level"],
            "foreground-required",
        )
        self.assertTrue(data["dispatch_report"]["transport_capability"]["foreground_required"])

    def test_execute_blocks_no_deterministic_transport_before_generic_dispatch_failure(self):
        fabric = ControlFabric()

        report = fabric.execute(
            _window("NVIDIA Overlay.exe", "NVIDIA GeForce Overlay", []),
            ControlIntent(action="write_text", text="probe"),
            allow_control=True,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "transport_capability_blocked")
        self.assertEqual(data["transport_gate_decision"], "blocked_transport_capability")
        self.assertEqual(
            data["dispatch_report"]["transport_capability_level"],
            "blocked",
        )
        self.assertEqual(
            data["dispatch_report"]["transport_capability"]["blocking_reason"],
            "no_deterministic_transport",
        )

    def test_execute_command_intent_requires_explicit_control_permission(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    effects=("read",),
                )
            )
            data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-command-execution")
        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertTrue(data["command_plan"]["ok"])
        self.assertEqual(data["action_report"], {})

    def test_execute_command_intent_runs_planned_argv_through_runner(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('fabric-planned-runner')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["command_plan"]["profile_id"], "read-only")
        self.assertIn("fabric-planned-runner", data["action_report"]["stdout"])

    def test_execute_command_intent_blocks_invalid_plan_before_runner(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric()
            report = fabric.execute_command_intent(
                {
                    "operation": "raw.argv",
                    "workspace_root": td,
                    "command": "git status && git diff",
                },
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "shell_command_not_allowed")
        self.assertFalse(data["command_plan"]["ok"])

    def test_execute_command_intent_requires_owned_workspace_when_configured(self):
        with tempfile.TemporaryDirectory() as td:
            fabric = ControlFabric(require_owned_session_for_execution=True)
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('must-not-run')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "blocked")
        self.assertEqual(data["error"], "owned_session_required")
        self.assertTrue(data["ownership_required"])
        self.assertFalse(data["ownership"]["owned"])
        self.assertEqual(data["control_attempts"], 0)

    def test_execute_command_intent_binds_owned_workspace_from_fabric_index(self):
        with tempfile.TemporaryDirectory() as td:
            ownership = _workspace_ownership(td, route_id="terminal-native-session", connector_id="terminal")
            fabric = ControlFabric(
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )
            report = fabric.execute_command_intent(
                CommandPlanIntent(
                    operation="raw.argv",
                    workspace_root=td,
                    argv=(sys.executable, "-c", "print('owned-fabric-plan')"),
                    effects=("read",),
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["connector_id"], "terminal")
        self.assertIn("owned-fabric-plan", data["action_report"]["stdout"])

    def test_execute_runs_real_terminal_connector_when_owned_session_matches(self):
        with tempfile.TemporaryDirectory() as td:
            ownership = _workspace_ownership(td, route_id="terminal-native-session", connector_id="terminal")
            fabric = ControlFabric(
                connector_manager=ConnectorManager(
                    [TerminalCommandConnector(command_timeout=5.0)]
                ),
                require_connector_session_ready=True,
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )

            report = fabric.execute(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="PowerShell",
                    workspace_path=td,
                ),
                ControlIntent(
                    action="run_command",
                    text="Write-Output fabric-owned-terminal",
                    preferred_route_id="terminal-native-session",
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["selected_connector_id"], "terminal")
        self.assertIn("fabric-owned-terminal", data["action_report"]["payload"]["stdout"])

    def test_execute_runs_real_git_connector_when_owned_session_matches(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True, text=True)
            ownership = _workspace_ownership(td, route_id="git-cli", connector_id="git")
            fabric = ControlFabric(
                connector_manager=ConnectorManager([GitCommandConnector(command_timeout=5.0)]),
                require_connector_session_ready=True,
                ownership_index=SessionOwnershipIndex((ownership,)),
                require_owned_session_for_execution=True,
            )

            report = fabric.execute(
                ConnectorTarget(
                    process_name="git.exe",
                    window_title="git",
                    workspace_path=td,
                    workspace_hint="git",
                ),
                ControlIntent(
                    action="run_command",
                    text="git status --short",
                    preferred_route_id="git-cli",
                ),
                allow_control=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["selected_connector_id"], "git")
        self.assertEqual(data["action_report"]["payload"]["exit_code"], 0)


def _workspace_ownership(workspace_root: str, *, route_id: str, connector_id: str) -> SessionOwnership:
    return SessionOwnership(
        owned=True,
        ownership_source="session_readiness_manifest",
        manifest_path=f"{connector_id}.json",
        route_id=route_id,
        connector_id=connector_id,
        action_id=f"bind_{connector_id}_workspace",
        workspace_root=workspace_root,
        cleanup_ready=False,
    )


if __name__ == "__main__":
    unittest.main()
