import contextlib
import io
import json
import unittest

from openwukong.connectors.browser import BrowserDevToolsTarget
from openwukong.evaluation.browser_devtools_health import (
    main,
    run_browser_devtools_health,
)


class _FakeDevToolsClient:
    def __init__(self, targets, evaluate_result=None, list_error=None):
        self.targets = tuple(targets)
        self.evaluate_result = evaluate_result or {
            "type": "object",
            "value": {
                "title": "Example App",
                "href": "https://example.test/app",
                "readyState": "complete",
            },
        }
        self.list_error = list_error
        self.list_calls = []
        self.evaluate_calls = []

    def list_targets(self, debugger_url):
        self.list_calls.append(debugger_url)
        if self.list_error:
            raise RuntimeError(self.list_error)
        return self.targets

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        return self.evaluate_result


class BrowserDevToolsHealthTests(unittest.TestCase):
    def test_health_report_reads_page_identity_without_control_attempts(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([target])

        report = run_browser_devtools_health(
            debugger_url="http://127.0.0.1:9223",
            window_title="Example App - Google Chrome",
            resource_url="https://example.test/app",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "browser-devtools-health")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["ok"])
        self.assertTrue(data["endpoint_ready"])
        self.assertTrue(data["target_matched"])
        self.assertTrue(data["evaluated_read_only"])
        self.assertEqual(data["debugger_url"], "http://127.0.0.1:9223")
        self.assertEqual(data["target"]["target_id"], "page-1")
        self.assertEqual(data["page_identity"]["title"], "Example App")
        self.assertEqual(data["page_identity"]["href"], "https://example.test/app")
        self.assertEqual(data["page_identity"]["readyState"], "complete")
        self.assertEqual(fake.list_calls, ["http://127.0.0.1:9223"])
        self.assertEqual(fake.evaluate_calls[0][1], target)
        self.assertIn("document.title", fake.evaluate_calls[0][2])
        self.assertIn("location.href", fake.evaluate_calls[0][2])

    def test_health_report_refuses_unmatched_devtools_target(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([target])

        report = run_browser_devtools_health(
            debugger_url="http://127.0.0.1:9223",
            window_title="Other Page - Google Chrome",
            resource_url="https://example.test/other",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertTrue(data["endpoint_ready"])
        self.assertFalse(data["target_matched"])
        self.assertFalse(data["evaluated_read_only"])
        self.assertEqual(data["error"], "devtools_target_not_matched")
        self.assertEqual(fake.evaluate_calls, [])

    def test_cli_outputs_browser_devtools_health_json(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--debugger-url",
                    "http://127.0.0.1:9223",
                    "--window-title",
                    "Example App - Google Chrome",
                    "--resource-url",
                    "https://example.test/app",
                    "--json",
                ],
                devtools_client=_FakeDevToolsClient([target]),
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "browser-devtools-health")
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"]["target_id"], "page-1")


if __name__ == "__main__":
    unittest.main()
