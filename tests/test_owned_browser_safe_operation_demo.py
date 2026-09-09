import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from openwukong.evaluation.owned_browser_safe_operation_demo import (
    DEFAULT_MARKER,
    main,
    run_owned_browser_safe_operation_demo,
)


class _FakeReadinessLauncher:
    def __init__(self, *, port: int = 19632, pid: int = 424242):
        self.port = port
        self.pid = pid
        self.calls = []

    def launch(self, argv, cwd=None):
        self.calls.append({"argv": tuple(argv), "cwd": cwd})
        user_data_arg = next(value for value in argv if value.startswith("--user-data-dir="))
        profile_path = Path(user_data_arg.split("=", 1)[1])
        profile_path.mkdir(parents=True, exist_ok=True)
        (profile_path / "DevToolsActivePort").write_text(
            f"{self.port}\n/devtools/browser/openwukong-demo\n",
            encoding="utf-8",
        )
        return self.pid


class _FakeReadinessTerminator:
    def __init__(self):
        self.tree_pids = []
        self.owned_argv = []

    def terminate_tree(self, pid):
        self.tree_pids.append(int(pid))

    def terminate_owned_processes(self, argv):
        self.owned_argv.append(tuple(argv))


class _FakeBrowserActionRunner:
    def __init__(self, marker=DEFAULT_MARKER):
        self.marker = marker
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        action = kwargs["action"]
        resource_url = kwargs["resource_url"]
        verified_url = _verified_url(resource_url, self.marker)
        if action == "navigate_url":
            return _action_report(action, kwargs["url"], attempts=1, marker=self.marker)
        if action == "set_input_value":
            return _action_report(action, resource_url, attempts=1, marker=self.marker)
        if action == "submit_form":
            return _action_report(action, verified_url, attempts=1, marker=self.marker)
        if action == "read_page":
            return _action_report(action, resource_url, attempts=0, marker=self.marker)
        if action == "extract_results":
            return _action_report(
                action,
                resource_url,
                attempts=0,
                marker=self.marker,
                items=[
                    {
                        "text": f"OpenWukong DOM verified: {self.marker}",
                        "href": f"{_origin(resource_url)}/result?marker={quote(self.marker, safe='')}",
                    }
                ],
            )
        raise AssertionError(f"unexpected browser action {action}")


class OwnedBrowserSafeOperationDemoTests(unittest.TestCase):
    def test_demo_launches_owned_browser_runs_dom_workflow_and_writes_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            launcher = _FakeReadinessLauncher()
            terminator = _FakeReadinessTerminator()
            runner = _FakeBrowserActionRunner()
            report = run_owned_browser_safe_operation_demo(
                output_root=tmp,
                browser_executable="chrome.exe",
                launcher=launcher,
                terminator=terminator,
                browser_action_runner=runner,
                settle_seconds=0.0,
            )
            data = report.to_dict()

            report_path = Path(data["report_path"])
            trajectory_path = Path(data["trajectory_path"])
            profile_path = Path(data["profile_cleanup"]["path"])

            self.assertTrue(data["ok"], data["error"])
            self.assertEqual(data["decision"], "owned_browser_demo_verified")
            self.assertEqual(data["safety_mode"], "isolated_owned_browser_devtools")
            self.assertTrue(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 3)
            self.assertFalse(data["desktop_control_allowed"])
            self.assertEqual(data["desktop_control_attempts"], 0)
            self.assertEqual(data["window_input_attempts"], 0)
            self.assertEqual(data["readiness_execution"]["launch_attempts"], 1)
            self.assertEqual(
                data["readiness_execution"]["results"][0]["readiness_url"],
                "http://127.0.0.1:19632",
            )
            self.assertEqual(data["readiness_stop"]["stop_attempts"], 1)
            self.assertEqual(terminator.tree_pids, [424242])
            self.assertEqual(len(terminator.owned_argv), 1)
            self.assertTrue(data["profile_cleanup"]["attempted"])
            self.assertTrue(data["profile_cleanup"]["deleted"])
            self.assertFalse(profile_path.exists())

            self.assertEqual(
                [call["action"] for call in runner.calls],
                [
                    "navigate_url",
                    "set_input_value",
                    "submit_form",
                    "read_page",
                    "extract_results",
                ],
            )
            self.assertTrue(data["browser_workflow"]["ok"], data["browser_workflow"]["error"])
            self.assertEqual(data["browser_workflow"]["quality_summary"]["failed"], 0)
            first_execution = data["browser_workflow"]["steps"][0]["execution_report"]
            self.assertTrue(first_execution["ownership_required"])
            self.assertTrue(first_execution["ownership"]["owned"])
            self.assertEqual(first_execution["ownership"]["endpoint"], "http://127.0.0.1:19632")

            self.assertTrue(report_path.is_file())
            self.assertTrue(trajectory_path.is_file())
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            self.assertEqual(trajectory["mode"], "control-trajectory")
            self.assertEqual(trajectory["scenario"], "owned-browser-safe-operation-demo")
            self.assertEqual(trajectory["step_count"], 5)
            phases = [step["phase"] for step in trajectory["steps"]]
            self.assertEqual(
                phases,
                ["controlled_page", "launch", "workflow", "cleanup", "final_report"],
            )
            final_artifacts = trajectory["steps"][-1]["artifacts"]
            self.assertEqual(final_artifacts[0]["role"], "owned_browser_demo_report")
            self.assertTrue(final_artifacts[0]["sha256"])

            argv = launcher.calls[0]["argv"]
            self.assertIn("--headless=new", argv)
            self.assertIn("--remote-debugging-port=0", argv)
            user_data_arg = next(value for value in argv if value.startswith("--user-data-dir="))
            self.assertTrue(str(Path(user_data_arg.split("=", 1)[1])).startswith(str(Path(tmp).resolve())))

    def test_demo_reports_launch_failure_and_still_writes_cleanup_trajectory(self):
        class _FailingLauncher(_FakeReadinessLauncher):
            def launch(self, argv, cwd=None):
                self.calls.append({"argv": tuple(argv), "cwd": cwd})
                raise RuntimeError("launcher_failed_fast")

        with tempfile.TemporaryDirectory() as tmp:
            report = run_owned_browser_safe_operation_demo(
                output_root=tmp,
                launcher=_FailingLauncher(),
                terminator=_FakeReadinessTerminator(),
                browser_action_runner=_FakeBrowserActionRunner(),
                settle_seconds=0.0,
            )
            data = report.to_dict()

            self.assertFalse(data["ok"])
            self.assertEqual(data["decision"], "owned_browser_demo_failed")
            self.assertIn("launcher_failed_fast", data["error"])
            self.assertEqual(data["browser_workflow"], {})
            self.assertTrue(Path(data["trajectory_path"]).is_file())

    def test_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["--output-root", tmp, "--settle-seconds", "0", "--json"],
                    launcher=_FakeReadinessLauncher(),
                    terminator=_FakeReadinessTerminator(),
                    browser_action_runner=_FakeBrowserActionRunner(),
                )
            data = json.loads(stdout.getvalue())
            self.assertTrue(Path(data["report_path"]).is_file())

        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["mode"], "owned-browser-safe-operation-demo")


def _action_report(action, href, *, attempts, marker, items=None):
    title = (
        "OpenWukong Controlled Page - Verified"
        if "verified" in href
        else "OpenWukong Controlled Page"
    )
    return {
        "mode": "browser-devtools-action",
        "safety_mode": "gated_browser_devtools_action",
        "ok": True,
        "control_allowed": True,
        "control_attempts": attempts,
        "action": action,
        "debugger_url": "http://127.0.0.1:19632",
        "page_identity": {
            "title": title,
            "href": href,
            "readyState": "complete",
        },
        "post_action_identity": {
            "title": title,
            "href": href,
            "readyState": "complete",
        },
        "action_result": {
            "title": title,
            "href": href,
            "readyState": "complete",
            "textExcerpt": f"OpenWukong DOM verified {marker}",
            "items": list(items or []),
        },
        "error": "",
    }


def _verified_url(resource_url, marker):
    return f"{_origin(resource_url)}/verified?marker={quote(marker, safe='')}"


def _origin(value):
    text = str(value or "").rstrip("/")
    if not text:
        return ""
    if "://" not in text:
        return text
    scheme, rest = text.split("://", 1)
    host = rest.split("/", 1)[0]
    return f"{scheme}://{host}"


if __name__ == "__main__":
    unittest.main()
