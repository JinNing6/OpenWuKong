import contextlib
import base64
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.control.session_readiness_plan import (
    SessionReadinessPlanOptions,
    SubprocessSessionReadinessLauncher,
    TaskTreeSessionReadinessTerminator,
    _managed_process_tokens,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.evaluation.session_readiness_plan import main


class SessionReadinessPlanTests(unittest.TestCase):
    def test_browser_plan_uses_isolated_profile_and_remote_debugging_port(self):
        options = SessionReadinessPlanOptions(
            browser_executable="C:/Program Files/Google/Chrome/Application/chrome.exe",
            browser_debug_port=9222,
            browser_user_data_dir="logs/runtime/openwukong-chrome-profile",
            browser_url="about:blank",
        )

        report = build_session_readiness_plan(
            routes=("browser-devtools-or-extension",),
            options=options,
        )
        data = report.to_dict()
        action = data["actions"][0]

        self.assertEqual(data["mode"], "session-readiness-launch-plan")
        self.assertEqual(data["safety_mode"], "plan_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(action["route_id"], "browser-devtools-or-extension")
        self.assertEqual(action["connector_id"], "browser")
        self.assertTrue(action["creates_isolated_profile"])
        self.assertIn("--remote-debugging-port=9222", action["command"])
        user_data_arg = next(
            item for item in action["argv"] if item.startswith("--user-data-dir=")
        )
        user_data_dir = user_data_arg.split("=", 1)[1]
        self.assertTrue(Path(user_data_dir).is_absolute())
        self.assertIn("--user-data-dir=", action["command"])
        self.assertIn("--remote-debugging-port=9222", action["argv"])
        self.assertIn("--headless", action["argv"])
        self.assertIn("--disable-crash-reporter", action["argv"])
        self.assertNotIn("--new-window", action["argv"])

    def test_ide_plan_uses_extension_host_and_bridge_settings_preview(self):
        options = SessionReadinessPlanOptions(
            ide_executable="C:/Program Files/Cursor/Cursor.exe",
            ide_user_data_dir="E:/tmp/openwukong-cursor-user-data",
            ide_extensions_dir="E:/tmp/openwukong-cursor-extensions",
            ide_extension_dir="E:/ideaProjects/agent/openwukong/extensions/openwukong-vscode",
            ide_bridge_port=8787,
            workspace_root="E:/ideaProjects/agent/openwukong",
        )

        report = build_session_readiness_plan(
            routes=("ide-extension-connector",),
            options=options,
        )
        action = report.to_dict()["actions"][0]

        self.assertEqual(action["route_id"], "ide-extension-connector")
        self.assertEqual(action["connector_id"], "ide-extension")
        self.assertTrue(action["creates_isolated_profile"])
        user_data_arg = next(
            item for item in action["argv"] if item.startswith("--user-data-dir=")
        )
        extensions_arg = next(
            item for item in action["argv"] if item.startswith("--extensions-dir=")
        )
        self.assertTrue(Path(user_data_arg.split("=", 1)[1]).is_absolute())
        self.assertTrue(Path(extensions_arg.split("=", 1)[1]).is_absolute())
        self.assertIn("--extensionDevelopmentPath=E:/ideaProjects/agent/openwukong/extensions/openwukong-vscode", action["command"])
        self.assertEqual(action["readiness_url"], "http://127.0.0.1:8787")
        self.assertTrue(action["settings_preview"]["openwukong.bridge.autoStart"])
        self.assertEqual(action["settings_preview"]["openwukong.bridge.port"], 8787)

    def test_terminal_plan_binds_existing_workspace_without_launching_foreground_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = SessionReadinessPlanOptions(workspace_root=tmp)

            report = build_session_readiness_plan(
                routes=("terminal-native-session",),
                options=options,
            )
            action = report.to_dict()["actions"][0]

            self.assertEqual(action["route_id"], "terminal-native-session")
            self.assertEqual(action["connector_id"], "terminal")
            self.assertEqual(Path(action["workspace_root"]).resolve(), Path(tmp).resolve())
            self.assertEqual(action["command"], "")
            self.assertFalse(action["foreground_required"])

    def test_agent_native_cdp_bridge_plan_uses_background_python_helper_and_registry(self):
        options = SessionReadinessPlanOptions(
            agent_bridge_python_executable="python.exe",
            agent_bridge_agent="codex app",
            agent_bridge_agent_id="codex",
            agent_bridge_host="127.0.0.1",
            agent_bridge_port=18888,
            agent_bridge_debugger_url="http://127.0.0.1:9555",
            agent_bridge_registry_path="E:/tmp/openwukong/native-bridges.json",
            agent_bridge_process_name="Codex.exe",
            agent_bridge_pid=42,
            agent_bridge_hwnd=70038,
            agent_bridge_window_title="Codex",
            agent_bridge_project_name="openwukong",
            agent_bridge_task_name="desktop-message",
            agent_bridge_target_title="openwukong",
        )

        report = build_session_readiness_plan(
            routes=("agent-native-cdp-bridge",),
            options=options,
        )
        action = report.to_dict()["actions"][0]

        self.assertEqual(action["action_id"], "launch_agent_native_cdp_bridge")
        self.assertEqual(action["route_id"], "agent-native-cdp-bridge")
        self.assertEqual(action["connector_id"], "agent-native-bridge")
        self.assertEqual(action["readiness_url"], "http://127.0.0.1:18888")
        self.assertTrue(action["managed_background_helper"])
        self.assertFalse(action["creates_isolated_profile"])
        self.assertFalse(action["foreground_required"])
        self.assertIn("openwukong.control.agent_native_cdp_bridge", action["argv"])
        self.assertIn("--debugger-url", action["argv"])
        self.assertIn("http://127.0.0.1:9555", action["argv"])
        self.assertIn("--registry-path", action["argv"])
        self.assertIn("E:/tmp/openwukong/native-bridges.json", action["argv"])
        self.assertIn("--process-name", action["argv"])
        self.assertIn("Codex.exe", action["argv"])
        self.assertIn("--project", action["argv"])
        self.assertIn("openwukong", action["argv"])

    def test_agent_app_devtools_owned_plan_uses_isolated_profile_and_remote_debugging(self):
        options = SessionReadinessPlanOptions(
            agent_app_executable="C:/Users/me/AppData/Local/Programs/Codex/Codex.exe",
            agent_app_debug_port=9555,
            agent_app_user_data_dir="logs/runtime/openwukong-codex-app-profile",
            agent_app_url="openwukong://workspace/E:/ideaProjects/agent/openwukong",
        )

        report = build_session_readiness_plan(
            routes=("agent-app-devtools-owned",),
            options=options,
        )
        action = report.to_dict()["actions"][0]

        self.assertEqual(action["action_id"], "launch_agent_app_devtools_owned")
        self.assertEqual(action["route_id"], "agent-app-devtools-owned")
        self.assertEqual(action["connector_id"], "agent-app-devtools")
        self.assertEqual(action["readiness_url"], "http://127.0.0.1:9555")
        self.assertTrue(action["creates_isolated_profile"])
        self.assertTrue(action["managed_background_helper"])
        self.assertFalse(action["foreground_required"])
        self.assertIn("--remote-debugging-port=9555", action["argv"])
        self.assertNotIn("--headless", action["argv"])
        user_data_arg = next(
            item for item in action["argv"] if item.startswith("--user-data-dir=")
        )
        self.assertTrue(Path(user_data_arg.split("=", 1)[1]).is_absolute())
        self.assertIn("--no-first-run", action["argv"])
        self.assertIn("--disable-crash-reporter", action["argv"])
        self.assertEqual(
            action["argv"][-1],
            "openwukong://workspace/E:/ideaProjects/agent/openwukong",
        )

    def test_agent_app_devtools_owned_plan_can_open_workspace_context(self):
        options = SessionReadinessPlanOptions(
            agent_app_executable="C:/Users/me/AppData/Local/Programs/Cursor/Cursor.exe",
            agent_app_debug_port=9557,
            agent_app_user_data_dir="logs/runtime/openwukong-cursor-app-profile",
            agent_app_workspace_path="E:/ideaProjects/agent/openwukong",
        )

        report = build_session_readiness_plan(
            routes=("agent-app-devtools-owned",),
            options=options,
        )
        action = report.to_dict()["actions"][0]

        workspace_arg = action["argv"][-1]
        self.assertEqual(
            Path(workspace_arg).resolve(),
            Path("E:/ideaProjects/agent/openwukong").resolve(),
        )
        self.assertIn("E:/ideaProjects/agent/openwukong", action["command"])

    def test_execute_allows_agent_app_devtools_owned_and_writes_manifest(self):
        class _FakeLauncher:
            def __init__(self):
                self.calls = []

            def launch(self, argv, cwd=None):
                self.calls.append((tuple(argv), cwd))
                return 8181

        with tempfile.TemporaryDirectory() as tmp:
            launcher = _FakeLauncher()
            profile = Path(tmp) / "codex-app-profile"
            manifest_path = Path(tmp) / "manifest.json"
            plan = build_session_readiness_plan(
                routes=("agent-app-devtools-owned",),
                options=SessionReadinessPlanOptions(
                    agent_app_executable="Codex.exe",
                    agent_app_debug_port=9555,
                    agent_app_user_data_dir=str(profile),
                ),
            )

            report = execute_session_readiness_plan(
                plan,
                manifest_path=str(manifest_path),
                launcher=launcher,
            )
            data = report.to_dict()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            profile_exists_at_launch = profile.is_dir()

        self.assertEqual(data["launch_attempts"], 1)
        self.assertEqual(data["results"][0]["status"], "started")
        self.assertEqual(data["results"][0]["pid"], 8181)
        self.assertTrue(profile_exists_at_launch)
        self.assertEqual(
            manifest["launches"][0]["action_id"],
            "launch_agent_app_devtools_owned",
        )
        self.assertIn("--remote-debugging-port=9555", launcher.calls[0][0])

    def test_subprocess_launcher_uses_no_activate_startupinfo_on_windows(self):
        if not hasattr(subprocess, "STARTUPINFO"):
            self.skipTest("Windows subprocess startup info is unavailable")

        class _FakeProcess:
            pid = 9090

        calls = []

        def _fake_popen(argv, **kwargs):
            calls.append((tuple(argv), dict(kwargs)))
            return _FakeProcess()

        with patch(
            "openwukong.control.session_readiness_plan.subprocess.Popen",
            side_effect=_fake_popen,
        ):
            pid = SubprocessSessionReadinessLauncher().launch(
                ("Codex.exe", "--remote-debugging-port=9555")
            )

        self.assertEqual(pid, 9090)
        kwargs = calls[0][1]
        startupinfo = kwargs["startupinfo"]
        self.assertTrue(
            startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
        )
        self.assertEqual(startupinfo.wShowWindow, 7)
        self.assertTrue(
            kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP
        )

    def test_execute_allows_agent_native_cdp_bridge_managed_background_helper(self):
        class _FakeLauncher:
            def __init__(self):
                self.calls = []

            def launch(self, argv, cwd=None):
                self.calls.append((tuple(argv), cwd))
                return 7171

        with tempfile.TemporaryDirectory() as tmp:
            launcher = _FakeLauncher()
            manifest_path = Path(tmp) / "manifest.json"
            plan = build_session_readiness_plan(
                routes=("agent-native-cdp-bridge",),
                options=SessionReadinessPlanOptions(
                    agent_bridge_python_executable="python.exe",
                    agent_bridge_port=18889,
                    agent_bridge_debugger_url="http://127.0.0.1:9555",
                    agent_bridge_registry_path=str(Path(tmp) / "native-bridges.json"),
                    agent_bridge_agent_id="codex",
                    agent_bridge_process_name="Codex.exe",
                ),
            )

            report = execute_session_readiness_plan(
                plan,
                manifest_path=str(manifest_path),
                launcher=launcher,
            )
            data = report.to_dict()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["launch_attempts"], 1)
        self.assertEqual(data["results"][0]["status"], "started")
        self.assertEqual(data["results"][0]["pid"], 7171)
        self.assertEqual(manifest["launches"][0]["action_id"], "launch_agent_native_cdp_bridge")
        self.assertIn("--registry-path", launcher.calls[0][0])

    def test_cli_outputs_readiness_plan_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--route",
                    "browser-devtools-or-extension",
                    "--browser-executable",
                    "chrome.exe",
                    "--browser-debug-port",
                    "9222",
                    "--browser-user-data-dir",
                    "E:/tmp/profile",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "session-readiness-launch-plan")
        self.assertEqual(data["actions"][0]["connector_id"], "browser")

    def test_cli_outputs_agent_native_cdp_bridge_plan_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--route",
                    "agent-native-cdp-bridge",
                    "--agent-bridge-python-executable",
                    "python.exe",
                    "--agent-bridge-agent",
                    "codex app",
                    "--agent-bridge-agent-id",
                    "codex",
                    "--agent-bridge-port",
                    "18888",
                    "--agent-bridge-debugger-url",
                    "http://127.0.0.1:9555",
                    "--agent-bridge-registry-path",
                    "E:/tmp/openwukong/native-bridges.json",
                    "--agent-bridge-process-name",
                    "Codex.exe",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        action = data["actions"][0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(action["route_id"], "agent-native-cdp-bridge")
        self.assertEqual(action["connector_id"], "agent-native-bridge")
        self.assertTrue(action["managed_background_helper"])
        self.assertIn("--registry-path", action["argv"])

    def test_cli_outputs_agent_app_devtools_owned_plan_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--route",
                    "agent-app-devtools-owned",
                    "--agent-app-executable",
                    "Codex.exe",
                    "--agent-app-debug-port",
                    "9555",
                    "--agent-app-user-data-dir",
                    "E:/tmp/openwukong-codex-profile",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        action = data["actions"][0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(action["route_id"], "agent-app-devtools-owned")
        self.assertEqual(action["connector_id"], "agent-app-devtools")
        self.assertTrue(action["managed_background_helper"])
        self.assertIn("--remote-debugging-port=9555", action["argv"])

    def test_cli_execute_writes_execution_report_without_launching_workspace_bind(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "execution.json"
            manifest_path = Path(tmp) / "manifest.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--route",
                        "terminal-native-session",
                        "--workspace-root",
                        tmp,
                        "--execute",
                        "--manifest",
                        str(manifest_path),
                        "--output",
                        str(output_path),
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(data["mode"], "session-readiness-execution")
            self.assertEqual(data["launch_attempts"], 0)
            self.assertEqual(data["results"][0]["status"], "workspace_bound")
            self.assertTrue(output_path.exists())
            self.assertTrue(manifest_path.exists())

    def test_execute_launches_only_isolated_helper_actions_and_writes_manifest(self):
        class _FakeLauncher:
            def __init__(self):
                self.calls = []

            def launch(self, argv, cwd=None):
                self.calls.append((tuple(argv), cwd))
                return 4242

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            plan = build_session_readiness_plan(
                routes=(
                    "browser-devtools-or-extension",
                    "terminal-native-session",
                ),
                options=SessionReadinessPlanOptions(
                    browser_executable="chrome.exe",
                    browser_user_data_dir=str(Path(tmp) / "browser-profile"),
                    workspace_root=tmp,
                ),
            )

            report = execute_session_readiness_plan(
                plan,
                manifest_path=str(manifest_path),
                launcher=_FakeLauncher(),
            )
            data = report.to_dict()

            self.assertEqual(data["mode"], "session-readiness-execution")
            self.assertEqual(data["safety_mode"], "isolated_helper_launch")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["launch_attempts"], 1)
            self.assertEqual(data["results"][0]["pid"], 4242)
            self.assertEqual(data["results"][0]["status"], "started")
            self.assertEqual(data["results"][1]["status"], "workspace_bound")
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["launches"][0]["pid"], 4242)

    def test_execute_creates_isolated_profile_directories_before_launch(self):
        class _AssertingLauncher:
            def launch(self, argv, cwd=None):
                paths = [
                    item.split("=", 1)[1]
                    for item in argv
                    if item.startswith("--user-data-dir=")
                    or item.startswith("--extensions-dir=")
                ]
                self.paths = paths
                self.existed_at_launch = [Path(path).is_dir() for path in paths]
                return 5151

        with tempfile.TemporaryDirectory() as tmp:
            launcher = _AssertingLauncher()
            browser_profile = Path(tmp) / "missing-browser-profile"
            ide_profile = Path(tmp) / "missing-ide-profile"
            ide_extensions = Path(tmp) / "missing-ide-extensions"
            plan = build_session_readiness_plan(
                routes=(
                    "browser-devtools-or-extension",
                    "ide-extension-connector",
                ),
                options=SessionReadinessPlanOptions(
                    browser_executable="chrome.exe",
                    browser_user_data_dir=str(browser_profile),
                    ide_executable="cursor.exe",
                    ide_user_data_dir=str(ide_profile),
                    ide_extensions_dir=str(ide_extensions),
                    ide_extension_dir=str(Path(tmp) / "extension"),
                ),
            )

            report = execute_session_readiness_plan(
                plan,
                manifest_path=str(Path(tmp) / "manifest.json"),
                launcher=launcher,
            )

            self.assertEqual(report.launch_attempts, 2)
            self.assertTrue(all(launcher.existed_at_launch))
            self.assertTrue(browser_profile.is_dir())
            self.assertTrue(ide_profile.is_dir())
            self.assertTrue(ide_extensions.is_dir())

    def test_execute_writes_ide_bridge_settings_into_isolated_user_data_before_launch(self):
        class _AssertingLauncher:
            def launch(self, argv, cwd=None):
                del cwd
                user_data_arg = next(
                    item for item in argv if item.startswith("--user-data-dir=")
                )
                settings_path = Path(user_data_arg.split("=", 1)[1]) / "User" / "settings.json"
                self.settings_path = settings_path
                self.settings_existed_at_launch = settings_path.exists()
                self.settings_at_launch = json.loads(settings_path.read_text(encoding="utf-8"))
                return 6262

        with tempfile.TemporaryDirectory() as tmp:
            launcher = _AssertingLauncher()
            user_data = Path(tmp) / "cursor-user-data"
            extensions_dir = Path(tmp) / "cursor-extensions"
            plan = build_session_readiness_plan(
                routes=("ide-extension-connector",),
                options=SessionReadinessPlanOptions(
                    ide_executable="cursor.exe",
                    ide_user_data_dir=str(user_data),
                    ide_extensions_dir=str(extensions_dir),
                    ide_extension_dir=str(Path(tmp) / "extension"),
                    ide_bridge_host="127.0.0.1",
                    ide_bridge_port=8791,
                ),
            )

            report = execute_session_readiness_plan(
                plan,
                manifest_path=str(Path(tmp) / "manifest.json"),
                launcher=launcher,
            )

        self.assertEqual(report.launch_attempts, 1)
        self.assertTrue(launcher.settings_existed_at_launch)
        self.assertEqual(launcher.settings_at_launch["openwukong.bridge.autoStart"], True)
        self.assertEqual(launcher.settings_at_launch["openwukong.bridge.host"], "127.0.0.1")
        self.assertEqual(launcher.settings_at_launch["openwukong.bridge.port"], 8791)

    def test_execute_rejects_non_isolated_command_actions(self):
        from openwukong.control.session_readiness_plan import SessionReadinessAction

        unsafe_plan = build_session_readiness_plan(
            routes=(),
            options=SessionReadinessPlanOptions(),
        )
        unsafe_plan = unsafe_plan.with_actions(
            (
                SessionReadinessAction(
                    action_id="unsafe",
                    route_id="browser-devtools-or-extension",
                    connector_id="browser",
                    description="unsafe",
                    command="chrome.exe",
                    argv=("chrome.exe",),
                    creates_isolated_profile=False,
                ),
            )
        )

        report = execute_session_readiness_plan(unsafe_plan)
        result = report.to_dict()["results"][0]

        self.assertEqual(result["status"], "rejected")
        self.assertIn("isolated_profile_required", result["error"])

    def test_stop_manifest_terminates_only_started_isolated_helper_pids(self):
        class _FakeTerminator:
            def __init__(self):
                self.pids = []

            def terminate_tree(self, pid):
                self.pids.append(pid)

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "route_id": "browser-devtools-or-extension",
                                "connector_id": "browser",
                                "status": "started",
                                "pid": 5151,
                            },
                            {
                                "action_id": "bind_terminal_workspace",
                                "route_id": "terminal-native-session",
                                "connector_id": "terminal",
                                "status": "workspace_bound",
                                "pid": 0,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

            self.assertEqual(data["mode"], "session-readiness-stop")
            self.assertEqual(data["safety_mode"], "manifest_pid_tree_stop")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["stop_attempts"], 1)
            self.assertEqual(data["results"][0]["status"], "stopped")
            self.assertEqual(terminator.pids, [5151])

    def test_stop_manifest_terminates_owned_residual_processes_from_manifest_argv(self):
        class _FakeTerminator:
            def __init__(self):
                self.tree_pids = []
                self.owned_argv = []

            def terminate_tree(self, pid):
                self.tree_pids.append(pid)

            def terminate_owned_processes(self, argv):
                self.owned_argv.append(tuple(argv))

        with tempfile.TemporaryDirectory() as tmp:
            profile = str(Path(tmp) / "profile").replace("\\", "/")
            manifest_path = Path(tmp) / "manifest.json"
            argv = (
                "chrome.exe",
                "--remote-debugging-port=9234",
                f"--user-data-dir={profile}",
                "--new-window",
                "about:blank",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "route_id": "browser-devtools-or-extension",
                                "connector_id": "browser",
                                "status": "started",
                                "pid": 5151,
                                "argv": list(argv),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

            self.assertEqual(data["results"][0]["status"], "stopped")
            self.assertEqual(terminator.tree_pids, [5151])
            self.assertEqual(terminator.owned_argv, [argv])

    def test_stop_manifest_cleans_owned_residuals_when_recorded_pid_already_exited(self):
        class _FakeTerminator:
            def __init__(self):
                self.owned_argv = []

            def terminate_tree(self, pid):
                raise RuntimeError(f'ERROR: The process "{pid}" not found.')

            def terminate_owned_processes(self, argv):
                self.owned_argv.append(tuple(argv))

        with tempfile.TemporaryDirectory() as tmp:
            profile = str(Path(tmp) / "profile").replace("\\", "/")
            manifest_path = Path(tmp) / "manifest.json"
            argv = (
                "chrome.exe",
                "--remote-debugging-port=9234",
                f"--user-data-dir={profile}",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "route_id": "browser-devtools-or-extension",
                                "connector_id": "browser",
                                "status": "started",
                                "pid": 5151,
                                "argv": list(argv),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

            self.assertEqual(data["results"][0]["status"], "stopped")
            self.assertEqual(data["results"][0]["error"], "")
            self.assertEqual(terminator.owned_argv, [argv])

    def test_stop_manifest_treats_tree_child_warning_as_stopped_after_owned_residual_cleanup(self):
        class _FakeTerminator:
            def __init__(self):
                self.owned_argv = []

            def terminate_tree(self, pid):
                raise RuntimeError(
                    "ERROR: The process with PID 80556 (child process of PID "
                    f"{pid}) could not be terminated.\n"
                    "Reason: The operation attempted is not supported."
                )

            def terminate_owned_processes(self, argv):
                self.owned_argv.append(tuple(argv))

        with tempfile.TemporaryDirectory() as tmp:
            profile = str(Path(tmp) / "profile").replace("\\", "/")
            manifest_path = Path(tmp) / "manifest.json"
            argv = (
                "chrome.exe",
                "--remote-debugging-port=9234",
                f"--user-data-dir={profile}",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "route_id": "browser-devtools-or-extension",
                                "connector_id": "browser",
                                "status": "started",
                                "pid": 5151,
                                "argv": list(argv),
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

            self.assertEqual(data["stop_attempts"], 1)
            self.assertEqual(data["results"][0]["status"], "stopped")
            self.assertEqual(data["results"][0]["error"], "")
            self.assertIn("operation attempted is not supported", data["results"][0]["warning"])
            self.assertEqual(terminator.owned_argv, [argv])

    def test_tasktree_owned_process_scan_uses_encoded_command_without_stdin_script(self):
        class _Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        calls = []

        def _fake_run(args, **kwargs):
            calls.append((tuple(args), dict(kwargs)))
            return _Completed()

        with patch(
            "openwukong.control.session_readiness_plan.subprocess.run",
            side_effect=_fake_run,
        ), patch("openwukong.control.session_readiness_plan.time.sleep") as sleep:
            TaskTreeSessionReadinessTerminator().terminate_owned_processes(
                (
                    "chrome.exe",
                    "--remote-debugging-port=9234",
                    "--user-data-dir=E:/tmp/openwukong-profile",
                )
            )

        self.assertEqual(len(calls), 6)
        self.assertEqual(sleep.call_count, 5)
        self.assertNotIn("input", calls[0][1])
        self.assertIn("stdin", calls[0][1])
        self.assertIn("-EncodedCommand", calls[0][0])
        encoded_index = calls[0][0].index("-EncodedCommand") + 1
        script = base64.b64decode(calls[0][0][encoded_index]).decode("utf-16le")
        self.assertIn("FromBase64String", script)
        self.assertIn("$self = $PID", script)
        self.assertIn("[Console]::OutputEncoding", script)
        self.assertIn("$proc.ProcessId -eq $self", script)
        self.assertIn("$hit = $false", script)
        self.assertNotIn("return", script)

    def test_tasktree_owned_process_cleanup_ignores_already_gone_child_pids(self):
        class _Completed:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        calls = []
        scan_count = 0

        def _fake_run(args, **kwargs):
            nonlocal scan_count
            calls.append((tuple(args), dict(kwargs)))
            if args[0] == "powershell":
                scan_count += 1
                return _Completed(stdout="111\n222\n" if scan_count == 1 else "")
            if args[:2] == ["taskkill", "/PID"] and args[2] == "111":
                return _Completed()
            if args[:2] == ["taskkill", "/PID"] and args[2] == "222":
                return _Completed(returncode=128, stderr='ERROR: The process "222" not found.')
            raise AssertionError(args)

        with patch(
            "openwukong.control.session_readiness_plan.subprocess.run",
            side_effect=_fake_run,
        ), patch("openwukong.control.session_readiness_plan.time.sleep"):
            TaskTreeSessionReadinessTerminator().terminate_owned_processes(
                (
                    "chrome.exe",
                    "--remote-debugging-port=9234",
                    "--user-data-dir=E:/tmp/openwukong-profile",
                )
            )

        taskkill_pids = [
            call[0][2]
            for call in calls
            if call[0][:2] == ("taskkill", "/PID")
        ]
        self.assertEqual(taskkill_pids[:2], ["111", "222"])

    def test_tasktree_owned_process_cleanup_uses_final_rescan_after_taskkill_child_warning(self):
        class _Completed:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        calls = []
        scan_count = 0

        def _fake_run(args, **kwargs):
            nonlocal scan_count
            calls.append((tuple(args), dict(kwargs)))
            if args[0] == "powershell":
                scan_count += 1
                return _Completed(stdout="85636\n" if scan_count == 1 else "")
            if args[:2] == ["taskkill", "/PID"] and args[2] == "85636":
                return _Completed(
                    returncode=1,
                    stderr=(
                        "ERROR: The process with PID 83012 (child process of PID 85636) "
                        "could not be terminated.\n"
                        "Reason: The operation attempted is not supported."
                    ),
                )
            raise AssertionError(args)

        with patch(
            "openwukong.control.session_readiness_plan.subprocess.run",
            side_effect=_fake_run,
        ), patch("openwukong.control.session_readiness_plan.time.sleep"):
            TaskTreeSessionReadinessTerminator().terminate_owned_processes(
                (
                    "chrome.exe",
                    "--remote-debugging-port=9234",
                    "--user-data-dir=E:/tmp/openwukong-profile",
                )
            )

        taskkill_pids = [
            call[0][2]
            for call in calls
            if call[0][:2] == ("taskkill", "/PID")
        ]
        self.assertEqual(taskkill_pids, ["85636"])
        self.assertGreaterEqual(scan_count, 2)

    def test_stop_manifest_rejects_unmanaged_manifest(self):
        class _FakeTerminator:
            def terminate_tree(self, pid):
                raise AssertionError("terminator should not be called")

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "unknown",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "status": "started",
                                "pid": 5151,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=_FakeTerminator(),
            )
            data = report.to_dict()

            self.assertEqual(data["stop_attempts"], 0)
            self.assertEqual(data["results"][0]["status"], "rejected")
            self.assertIn("unmanaged_manifest", data["results"][0]["error"])

    def test_cli_stop_manifest_outputs_stop_report_json(self):
        class _FakeTerminator:
            def __init__(self):
                self.pids = []

            def terminate_tree(self, pid):
                self.pids.append(pid)

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            output_path = Path(tmp) / "stop.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_ide_bridge_isolated",
                                "route_id": "ide-extension-connector",
                                "connector_id": "ide-extension",
                                "status": "started",
                                "pid": 6262,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--stop-manifest",
                        str(manifest_path),
                        "--output",
                        str(output_path),
                        "--json",
                    ],
                    terminator=terminator,
                )

            data = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(data["mode"], "session-readiness-stop")
            self.assertEqual(data["stop_attempts"], 1)
            self.assertEqual(terminator.pids, [6262])
            self.assertTrue(output_path.exists())

    def test_stop_manifest_accepts_agent_native_cdp_bridge_helper(self):
        class _FakeTerminator:
            def __init__(self):
                self.tree_pids = []
                self.owned_argv = []

            def terminate_tree(self, pid):
                self.tree_pids.append(pid)

            def terminate_owned_processes(self, argv):
                self.owned_argv.append(tuple(argv))

        with tempfile.TemporaryDirectory() as tmp:
            registry_path = str(Path(tmp) / "native-bridges.json").replace("\\", "/")
            argv = (
                "python.exe",
                "-m",
                "openwukong.control.agent_native_cdp_bridge",
                "--host",
                "127.0.0.1",
                "--port",
                "18888",
                "--agent-id",
                "codex",
                "--debugger-url",
                "http://127.0.0.1:9555",
                "--process-name",
                "Codex.exe",
                "--registry-path",
                registry_path,
            )
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_agent_native_cdp_bridge",
                                "route_id": "agent-native-cdp-bridge",
                                "connector_id": "agent-native-bridge",
                                "status": "started",
                                "pid": 7171,
                                "argv": list(argv),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

        self.assertEqual(data["stop_attempts"], 1)
        self.assertEqual(data["results"][0]["status"], "stopped")
        self.assertEqual(terminator.tree_pids, [7171])
        self.assertEqual(terminator.owned_argv, [argv])

    def test_stop_manifest_accepts_agent_app_devtools_owned_helper(self):
        class _FakeTerminator:
            def __init__(self):
                self.tree_pids = []
                self.owned_argv = []

            def terminate_tree(self, pid):
                self.tree_pids.append(pid)

            def terminate_owned_processes(self, argv):
                self.owned_argv.append(tuple(argv))

        with tempfile.TemporaryDirectory() as tmp:
            profile = str(Path(tmp) / "codex-app-profile").replace("\\", "/")
            argv = (
                "Codex.exe",
                "--remote-debugging-port=9555",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--disable-crash-reporter",
            )
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_agent_app_devtools_owned",
                                "route_id": "agent-app-devtools-owned",
                                "connector_id": "agent-app-devtools",
                                "status": "started",
                                "pid": 8181,
                                "argv": list(argv),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            terminator = _FakeTerminator()

            report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            data = report.to_dict()

        self.assertEqual(data["stop_attempts"], 1)
        self.assertEqual(data["results"][0]["status"], "stopped")
        self.assertEqual(terminator.tree_pids, [8181])
        self.assertEqual(terminator.owned_argv, [argv])

    def test_agent_native_cdp_bridge_residual_tokens_exclude_target_debugger_url(self):
        registry_path = "E:/tmp/openwukong/native-bridges.json"
        argv = (
            "python.exe",
            "-m",
            "openwukong.control.agent_native_cdp_bridge",
            "--host",
            "127.0.0.1",
            "--port",
            "18888",
            "--agent-id",
            "codex",
            "--debugger-url",
            "http://127.0.0.1:65530",
            "--process-name",
            "Codex.exe",
            "--registry-path",
            registry_path,
        )

        tokens = _managed_process_tokens(argv)

        self.assertIn("openwukong.control.agent_native_cdp_bridge", tokens)
        self.assertIn(registry_path, tokens)
        self.assertNotIn("http://127.0.0.1:65530", tokens)


if __name__ == "__main__":
    unittest.main()
