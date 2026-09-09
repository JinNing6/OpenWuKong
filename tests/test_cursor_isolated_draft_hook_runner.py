import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.session_readiness_plan import (
    SessionReadinessExecutionReport,
    SessionReadinessLaunchResult,
    SessionReadinessStopReport,
    SessionReadinessStopResult,
)
from openwukong.evaluation.cursor_isolated_draft_hook_runner import (
    run_cursor_isolated_draft_hook_validation,
)


class CursorIsolatedDraftHookRunnerTests(unittest.TestCase):
    def test_runner_launches_isolated_cursor_profile_validates_and_stops(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / "Cursor.exe"
            executable.write_text("", encoding="utf-8")
            calls = _Calls()

            report = run_cursor_isolated_draft_hook_validation(
                output_root=root / "run",
                cursor_executable=str(executable),
                bridge_port=0,
                message="OPENWUKONG_CURSOR_ISOLATED_WRITE",
                allow_write=True,
                allow_visible_gui_launch=True,
                focus_observer=_FocusSequence(
                    [
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                    ]
                ),
                plan_executor=calls.executor,
                stop_manifest=calls.stopper,
                bridge_waiter=calls.waiter,
                validator=calls.validator,
                cleanup_profiles=True,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "cursor_draft_hook_validated")
        self.assertEqual(data["launch_report"]["launch_attempts"], 1)
        self.assertEqual(data["stop_report"]["stop_attempts"], 1)
        self.assertEqual(data["validation_report"]["safety_profile"], "isolated_cursor_draft_probe")
        self.assertEqual(data["validation_report"]["allow_write"], True)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 1)
        argv = calls.launch_argv
        self.assertIn("--extensionDevelopmentPath=" + str((Path.cwd() / "extensions" / "openwukong-vscode").resolve()).replace("\\", "/"), argv)
        self.assertTrue(any(arg.startswith("--user-data-dir=") for arg in argv))
        self.assertTrue(any(arg.startswith("--extensions-dir=") for arg in argv))
        self.assertEqual(calls.plan_settings_preview["openwukong.bridge.port"], 0)
        self.assertEqual(data["bridge_url"], "http://127.0.0.1:19642")
        self.assertEqual(calls.waiter_bridge_urls, ["http://127.0.0.1:19642"])
        self.assertEqual(calls.validator_bridge_urls, ["http://127.0.0.1:19642"])
        self.assertTrue(calls.stopped)
        self.assertTrue(data["cleanup_report"]["ok"])

    def test_runner_stops_and_skips_validation_when_launch_changes_foreground(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / "Cursor.exe"
            executable.write_text("", encoding="utf-8")
            calls = _Calls()

            report = run_cursor_isolated_draft_hook_validation(
                output_root=root / "run",
                cursor_executable=str(executable),
                message="OPENWUKONG_CURSOR_ISOLATED_WRITE",
                allow_write=True,
                allow_visible_gui_launch=True,
                focus_observer=_FocusSequence(
                    [
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                        {"available": True, "hwnd": 20, "title": "Cursor"},
                    ]
                ),
                plan_executor=calls.executor,
                stop_manifest=calls.stopper,
                bridge_waiter=calls.waiter,
                validator=calls.validator,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_isolated_launch_changed_foreground")
        self.assertTrue(data["launch_foreground_changed"])
        self.assertEqual(calls.validation_calls, 0)
        self.assertTrue(calls.stopped)

    def test_runner_blocks_visible_gui_launch_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / "Cursor.exe"
            executable.write_text("", encoding="utf-8")
            calls = _Calls()

            report = run_cursor_isolated_draft_hook_validation(
                output_root=root / "run",
                cursor_executable=str(executable),
                message="OPENWUKONG_CURSOR_ISOLATED_WRITE",
                allow_write=True,
                focus_observer=_FocusSequence(
                    [
                        {"available": True, "hwnd": 10, "title": "Weixin"},
                    ]
                ),
                plan_executor=calls.executor,
                stop_manifest=calls.stopper,
                bridge_waiter=calls.waiter,
                validator=calls.validator,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_visible_gui_launch_blocked")
        self.assertFalse(data["visible_gui_launch_allowed"])
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertEqual(calls.executor_calls, 0)
        self.assertFalse(calls.stopped)

    def test_runner_rejects_unresolved_cursor_without_launching(self):
        calls = _Calls()

        report = run_cursor_isolated_draft_hook_validation(
            cursor_executable="",
            allow_visible_gui_launch=True,
            resolver=_Resolver({"ok": False, "error": "app_not_found"}),
            plan_executor=calls.executor,
            stop_manifest=calls.stopper,
            bridge_waiter=calls.waiter,
            validator=calls.validator,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "cursor_executable_not_resolved")
        self.assertEqual(calls.executor_calls, 0)
        self.assertFalse(calls.stopped)


class _Calls:
    def __init__(self):
        self.executor_calls = 0
        self.validation_calls = 0
        self.stopped = False
        self.launch_argv = ()
        self.plan_settings_preview = {}
        self.waiter_bridge_urls = []
        self.validator_bridge_urls = []

    def executor(self, plan, *, manifest_path):
        self.executor_calls += 1
        action = plan.actions[0]
        self.launch_argv = tuple(action.argv)
        self.plan_settings_preview = dict(action.settings_preview or {})
        readiness_url = action.readiness_url or "http://127.0.0.1:19642"
        Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(manifest_path).write_text(
            json.dumps({"mode": "session-readiness-execution", "safety_mode": "isolated_helper_launch"}),
            encoding="utf-8",
        )
        return SessionReadinessExecutionReport(
            results=(
                SessionReadinessLaunchResult(
                    action_id=action.action_id,
                    route_id=action.route_id,
                    connector_id=action.connector_id,
                    status="started",
                    pid=4242,
                    argv=action.argv,
                    readiness_url=readiness_url,
                    workspace_root=action.workspace_root,
                ),
            ),
            manifest_path=str(manifest_path),
        )

    def stopper(self, manifest_path):
        self.stopped = True
        return SessionReadinessStopReport(
            results=(
                SessionReadinessStopResult(
                    action_id="launch_ide_bridge_isolated",
                    route_id="ide-extension-connector",
                    connector_id="ide-extension",
                    status="stopped",
                    pid=4242,
                ),
            ),
            manifest_path=str(manifest_path),
        )

    def waiter(self, **kwargs):
        self.waiter_bridge_urls.append(kwargs.get("bridge_url", ""))
        return {
            "ok": True,
            "decision": "ide_bridge_ready",
            "attempts": 1,
            "bridge_url": kwargs.get("bridge_url", ""),
        }

    def validator(self, **kwargs):
        self.validation_calls += 1
        self.validator_bridge_urls.append(kwargs.get("bridge_url", ""))
        return {
            "ok": True,
            "decision": "cursor_draft_hook_validated",
            "allow_write": kwargs.get("allow_write", False),
            "safety_profile": kwargs.get("safety_profile", ""),
            "draft_write_attempts": 1,
            "control_attempts": 1,
            "window_input_attempts": 0,
            "bridge_send_attempts": 0,
            "readback_verified": True,
        }


class _FocusSequence:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture(self):
        if self.index >= len(self.snapshots):
            value = self.snapshots[-1]
        else:
            value = self.snapshots[self.index]
        self.index += 1
        return dict(value)


class _Resolver:
    def __init__(self, report):
        self.report = dict(report)

    def resolve(self, app_name):
        return dict(self.report, app_name=app_name)


if __name__ == "__main__":
    unittest.main()
