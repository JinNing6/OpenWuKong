import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openwukong.control.session_discovery import DiscoveredControlTarget
from openwukong.evaluation.control_fabric_browser_workflow import (
    BrowserWorkflowExpectations,
    BrowserWorkflowStep,
    main,
    run_control_fabric_browser_workflow,
)


class _FakeBrowserActionReport:
    def __init__(self, action, href, *, attempts=1, ok=True, error=""):
        self.action = action
        self.href = href
        self.attempts = attempts
        self.ok = ok
        self.error = error

    def to_dict(self):
        title = "Search Results" if "search" in self.href else "Search Home"
        return {
            "mode": "browser-devtools-action",
            "safety_mode": "gated_browser_devtools_action",
            "ok": self.ok,
            "control_allowed": True,
            "control_attempts": self.attempts,
            "action": self.action,
            "post_action_identity": {
                "title": title,
                "href": self.href,
                "readyState": "complete",
            },
            "action_result": {
                "href": self.href,
                "items": [{"text": "OpenWukong result", "href": "https://example.test/openwukong"}],
            },
            "error": self.error,
        }


class _FakeBrowserActionRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        action = kwargs["action"]
        if action == "navigate_url":
            return _FakeBrowserActionReport(action, kwargs["url"])
        if action == "set_input_value":
            return _FakeBrowserActionReport(action, kwargs["resource_url"])
        if action == "submit_form":
            return _FakeBrowserActionReport(action, "https://example.test/search?q=openwukong")
        if action == "read_page":
            return _FakeBrowserActionReport(action, kwargs["resource_url"], attempts=0)
        if action == "extract_results":
            return _FakeBrowserActionReport(action, kwargs["resource_url"], attempts=0)
        raise AssertionError(f"unexpected action {action}")


class _FakeSessionDiscovery:
    def __init__(self):
        self.calls = []

    def enrich(self, target):
        self.calls.append(target)
        return DiscoveredControlTarget(
            source=target,
            debugger_url="http://127.0.0.1:9222",
            resource_url=getattr(target, "resource_url", ""),
            evidence=(
                {
                    "kind": "browser_devtools",
                    "url": "http://127.0.0.1:9222",
                    "target_title": "about:blank",
                    "target_url": "about:blank",
                },
            ),
        )


class ControlFabricBrowserWorkflowTests(unittest.TestCase):
    def test_workflow_executes_form_steps_and_carries_page_identity_forward(self):
        runner = _FakeBrowserActionRunner()

        report = run_control_fabric_browser_workflow(
            process_name="chrome.exe",
            window_title="about:blank - Google Chrome",
            resource_url="about:blank",
            debugger_url="http://127.0.0.1:9222",
            steps=(
                BrowserWorkflowStep(action="navigate_url", url="https://example.test/"),
                BrowserWorkflowStep(
                    action="set_input_value",
                    selector="input[name=q]",
                    value="openwukong",
                ),
                BrowserWorkflowStep(action="submit_form", selector="input[name=q]"),
                BrowserWorkflowStep(action="read_page"),
                BrowserWorkflowStep(action="extract_results", selector="a"),
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "control-fabric-browser-workflow")
        self.assertTrue(data["ok"], data["error"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 3)
        self.assertEqual(data["step_count"], 5)
        self.assertEqual([step["action"] for step in data["steps"]], [
            "navigate_url",
            "set_input_value",
            "submit_form",
            "read_page",
            "extract_results",
        ])
        self.assertEqual(runner.calls[1]["resource_url"], "https://example.test/")
        self.assertEqual(runner.calls[3]["resource_url"], "https://example.test/search?q=openwukong")
        self.assertEqual(data["final_page_identity"]["href"], "https://example.test/search?q=openwukong")

    def test_workflow_refuses_without_allow_control_before_first_step(self):
        runner = _FakeBrowserActionRunner()

        report = run_control_fabric_browser_workflow(
            process_name="chrome.exe",
            window_title="about:blank - Google Chrome",
            resource_url="about:blank",
            debugger_url="http://127.0.0.1:9222",
            steps=(BrowserWorkflowStep(action="navigate_url", url="https://example.test/"),),
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertEqual(runner.calls, [])

    def test_workflow_waits_after_submit_form_before_next_step(self):
        runner = _FakeBrowserActionRunner()

        with mock.patch("openwukong.evaluation.control_fabric_browser_workflow.time.sleep") as sleep:
            report = run_control_fabric_browser_workflow(
                process_name="chrome.exe",
                window_title="Search - Google Chrome",
                resource_url="https://example.test/",
                debugger_url="http://127.0.0.1:9222",
                steps=(
                    BrowserWorkflowStep(action="submit_form", selector="input[name=q]"),
                    BrowserWorkflowStep(action="read_page"),
                ),
                allow_control=True,
                settle_seconds=0.25,
                browser_action_runner=runner,
            )

        self.assertTrue(report.ok, report.error)
        sleep.assert_called_once_with(0.25)

    def test_workflow_quality_expectations_can_fail_completed_steps(self):
        runner = _FakeBrowserActionRunner()

        report = run_control_fabric_browser_workflow(
            process_name="chrome.exe",
            window_title="Search - Google Chrome",
            resource_url="https://example.test/",
            debugger_url="http://127.0.0.1:9222",
            steps=(
                BrowserWorkflowStep(action="read_page"),
                BrowserWorkflowStep(action="extract_results", selector="a"),
            ),
            expectations=BrowserWorkflowExpectations(
                expected_url_contains=("missing-query",),
                expected_text_contains=("Missing Result",),
                expected_link_href_contains=("missing-link",),
                min_result_count=2,
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "workflow_quality_assertion_failed")
        self.assertEqual(data["quality_summary"]["failed"], 3)
        self.assertEqual(data["quality_summary"]["passed"], 1)
        failed = [check for check in data["quality_checks"] if not check["passed"]]
        self.assertEqual(
            [check["kind"] for check in failed],
            ["expected_url_contains", "expected_text_contains", "expected_link_href_contains"],
        )

    def test_workflow_quality_expectations_pass_with_url_text_and_link_evidence(self):
        runner = _FakeBrowserActionRunner()

        report = run_control_fabric_browser_workflow(
            process_name="chrome.exe",
            window_title="Search - Google Chrome",
            resource_url="https://example.test/",
            debugger_url="http://127.0.0.1:9222",
            steps=(
                BrowserWorkflowStep(action="read_page"),
                BrowserWorkflowStep(action="extract_results", selector="a"),
            ),
            expectations=BrowserWorkflowExpectations(
                expected_url_contains=("example.test",),
                expected_text_contains=("OpenWukong result",),
                expected_link_href_contains=("openwukong",),
                expected_link_text_contains=("OpenWukong",),
                min_result_count=1,
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["quality_summary"]["failed"], 0)
        self.assertEqual(data["quality_summary"]["passed"], 5)

    def test_cli_runs_fixed_form_workflow(self):
        runner = _FakeBrowserActionRunner()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--process-name",
                    "chrome.exe",
                    "--window-title",
                    "about:blank - Google Chrome",
                    "--resource-url",
                    "about:blank",
                    "--debugger-url",
                    "http://127.0.0.1:9222",
                    "--start-url",
                    "https://example.test/",
                    "--input-selector",
                    "input[name=q]",
                    "--query",
                    "openwukong",
                    "--submit-selector",
                    "button[type=submit]",
                    "--results-selector",
                    "a",
                    "--allow-control",
                    "--json",
                ],
                browser_action_runner=runner,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["step_count"], 5)
        self.assertEqual(runner.calls[0]["action"], "navigate_url")
        self.assertEqual(runner.calls[1]["action"], "set_input_value")
        self.assertEqual(runner.calls[2]["action"], "submit_form")

    def test_cli_binds_readiness_manifest_ownership_before_workflow(self):
        runner = _FakeBrowserActionRunner()
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _write_browser_manifest(Path(tmp) / "browser.json")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--process-name",
                        "chrome.exe",
                        "--window-title",
                        "about:blank - Google Chrome",
                        "--resource-url",
                        "about:blank",
                        "--debugger-url",
                        "http://127.0.0.1:9222",
                        "--start-url",
                        "https://example.test/",
                        "--input-selector",
                        "input[name=q]",
                        "--query",
                        "openwukong",
                        "--submit-selector",
                        "button[type=submit]",
                        "--results-selector",
                        "a",
                        "--allow-control",
                        "--readiness-manifest",
                        str(manifest),
                        "--json",
                    ],
                    browser_action_runner=runner,
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        first_execution = data["steps"][0]["execution_report"]
        self.assertTrue(first_execution["ownership_required"])
        self.assertTrue(first_execution["ownership"]["owned"])
        self.assertEqual(first_execution["ownership"]["endpoint"], "http://127.0.0.1:9222")
        self.assertEqual(len(runner.calls), 5)

    def test_cli_accepts_quality_expectation_flags(self):
        runner = _FakeBrowserActionRunner()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--process-name",
                    "chrome.exe",
                    "--window-title",
                    "about:blank - Google Chrome",
                    "--resource-url",
                    "about:blank",
                    "--debugger-url",
                    "http://127.0.0.1:9222",
                    "--start-url",
                    "https://example.test/",
                    "--input-selector",
                    "input[name=q]",
                    "--query",
                    "openwukong",
                    "--submit-selector",
                    "input[name=q]",
                    "--results-selector",
                    "a",
                    "--expect-url-contains",
                    "search",
                    "--expect-text-contains",
                    "OpenWukong",
                    "--expect-link-href-contains",
                    "openwukong",
                    "--min-result-count",
                    "1",
                    "--allow-control",
                    "--json",
                ],
                browser_action_runner=runner,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["quality_summary"]["failed"], 0)

    def test_cli_discovers_browser_debugger_url_before_workflow(self):
        runner = _FakeBrowserActionRunner()
        discovery = _FakeSessionDiscovery()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--process-name",
                    "chrome.exe",
                    "--window-title",
                    "about:blank - Google Chrome",
                    "--resource-url",
                    "about:blank",
                    "--start-url",
                    "https://example.test/",
                    "--input-selector",
                    "input[name=q]",
                    "--query",
                    "openwukong",
                    "--submit-selector",
                    "input[name=q]",
                    "--results-selector",
                    "a",
                    "--discover-sessions",
                    "--allow-control",
                    "--json",
                ],
                browser_action_runner=runner,
                session_discovery=discovery,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(runner.calls[0]["debugger_url"], "http://127.0.0.1:9222")
        self.assertEqual(len(discovery.calls), 1)
        self.assertEqual(
            data["steps"][0]["execution_report"]["dispatch_report"]["session_discovery"]["discovered_fields"]["debugger_url"],
            "http://127.0.0.1:9222",
        )


if __name__ == "__main__":
    unittest.main()


def _write_browser_manifest(path: Path) -> Path:
    path.write_text(
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
                        "pid": 4242,
                        "readiness_url": "http://127.0.0.1:9222",
                        "argv": [
                            "chrome.exe",
                            "--remote-debugging-port=9222",
                            "--user-data-dir=E:/tmp/openwukong-owned-browser",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
