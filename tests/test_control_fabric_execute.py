import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.session_discovery import DiscoveredControlTarget
from openwukong.evaluation.control_fabric_execute import main


class _FakeBrowserActionReport:
    def to_dict(self):
        return {
            "mode": "browser-devtools-action",
            "safety_mode": "gated_browser_devtools_action",
            "ok": True,
            "control_allowed": True,
            "control_attempts": 1,
            "action": "navigate_url",
            "error": "",
        }


class _FakeBrowserActionRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _FakeBrowserActionReport()


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


class ControlFabricExecuteCliTests(unittest.TestCase):
    def test_cli_refuses_execution_without_explicit_allow_control(self):
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
                    "--action",
                    "navigate_url",
                    "--url",
                    "https://example.test/search",
                    "--json",
                ],
                browser_action_runner=runner,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(data["mode"], "control-fabric-execution")
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "explicit_control_permission_required")
        self.assertEqual(runner.calls, [])

    def test_cli_executes_browser_action_after_allow_control(self):
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
                    "--action",
                    "navigate_url",
                    "--url",
                    "https://example.test/search",
                    "--allow-control",
                    "--json",
                ],
                browser_action_runner=runner,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["decision"], "executed")
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["dispatch_report"]["decision"], "dispatch_connector")
        self.assertEqual(runner.calls[0]["action"], "navigate_url")
        self.assertEqual(runner.calls[0]["url"], "https://example.test/search")

    def test_cli_requires_owned_session_when_requested(self):
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
                    "--action",
                    "navigate_url",
                    "--url",
                    "https://example.test/search",
                    "--allow-control",
                    "--require-owned-session",
                    "--json",
                ],
                browser_action_runner=runner,
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "owned_session_required")
        self.assertTrue(data["ownership_required"])
        self.assertFalse(data["ownership"]["owned"])
        self.assertEqual(runner.calls, [])

    def test_cli_binds_readiness_manifest_ownership_before_execution(self):
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
                        "--action",
                        "navigate_url",
                        "--url",
                        "https://example.test/search",
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
        self.assertTrue(data["ownership_required"])
        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["endpoint"], "http://127.0.0.1:9222")
        self.assertEqual(len(runner.calls), 1)

    def test_cli_discovers_browser_debugger_url_before_execution(self):
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
                    "--action",
                    "navigate_url",
                    "--url",
                    "https://example.test/search",
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
            data["dispatch_report"]["session_discovery"]["discovered_fields"]["debugger_url"],
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
