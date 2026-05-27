import contextlib
import io
import json
import unittest

from openwukong.connectors.browser import BrowserDevToolsTarget
from openwukong.evaluation.browser_devtools_dom_probe import (
    main,
    run_browser_devtools_dom_probe,
)


class _FakeDevToolsClient:
    def __init__(self, targets, evaluate_results=None):
        self.targets = tuple(targets)
        self.evaluate_results = list(
            evaluate_results
            or [
                {
                    "type": "object",
                    "value": {
                        "title": "Example App",
                        "href": "https://example.test/app",
                        "readyState": "complete",
                    },
                },
                {"type": "object", "value": {"present": True, "text": "OPENWUKONG_PROBE"}},
                {"type": "object", "value": {"present": True, "text": "OPENWUKONG_PROBE"}},
                {"type": "object", "value": {"removed": True}},
                {"type": "object", "value": {"present": False, "text": ""}},
            ]
        )
        self.list_calls = []
        self.evaluate_calls = []

    def list_targets(self, debugger_url):
        self.list_calls.append(debugger_url)
        return self.targets

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        if not self.evaluate_results:
            raise AssertionError("unexpected evaluate call")
        return self.evaluate_results.pop(0)


class BrowserDevToolsDomProbeTests(unittest.TestCase):
    def test_dom_probe_writes_verifies_clears_and_verifies_absence(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([target])

        report = run_browser_devtools_dom_probe(
            debugger_url="http://127.0.0.1:9223",
            window_title="Example App - Google Chrome",
            resource_url="https://example.test/app",
            token="OPENWUKONG_PROBE",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "browser-devtools-dom-probe")
        self.assertEqual(data["safety_mode"], "isolated_dom_write_clear_probe")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertTrue(data["ok"])
        self.assertTrue(data["health_ok"])
        self.assertTrue(data["write_verified"])
        self.assertTrue(data["clear_verified"])
        self.assertTrue(data["token_visible_after_write"])
        self.assertFalse(data["token_visible_after_clear"])
        self.assertEqual(data["token"], "OPENWUKONG_PROBE")
        self.assertEqual(data["target"]["target_id"], "page-1")
        expressions = [call[2] for call in fake.evaluate_calls]
        self.assertIn("document.title", expressions[0])
        self.assertIn("openwukong-dom-probe", expressions[1])
        self.assertIn("OPENWUKONG_PROBE", expressions[1])
        self.assertIn("openwukong-dom-probe", expressions[3])

    def test_dom_probe_refuses_when_health_target_does_not_match(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Example App",
            url="https://example.test/app",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([target])

        report = run_browser_devtools_dom_probe(
            debugger_url="http://127.0.0.1:9223",
            window_title="Other Page - Google Chrome",
            resource_url="https://example.test/other",
            token="OPENWUKONG_PROBE",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertFalse(data["health_ok"])
        self.assertFalse(data["write_verified"])
        self.assertFalse(data["clear_verified"])
        self.assertEqual(data["error"], "devtools_target_not_matched")
        self.assertEqual(fake.evaluate_calls, [])

    def test_cli_outputs_dom_probe_json(self):
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
                    "--token",
                    "OPENWUKONG_PROBE",
                    "--json",
                ],
                devtools_client=_FakeDevToolsClient([target]),
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "browser-devtools-dom-probe")
        self.assertTrue(data["ok"])
        self.assertTrue(data["clear_verified"])


if __name__ == "__main__":
    unittest.main()
