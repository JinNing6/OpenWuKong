import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.control.session_readiness_plan import (
    SessionReadinessPlanOptions,
    TaskTreeSessionReadinessTerminator,
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

    def test_tasktree_owned_process_scan_uses_input_without_stdin_pipe(self):
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
        ):
            TaskTreeSessionReadinessTerminator().terminate_owned_processes(
                (
                    "chrome.exe",
                    "--remote-debugging-port=9234",
                    "--user-data-dir=E:/tmp/openwukong-profile",
                )
            )

        self.assertEqual(len(calls), 1)
        self.assertIn("input", calls[0][1])
        self.assertNotIn("stdin", calls[0][1])

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


if __name__ == "__main__":
    unittest.main()
