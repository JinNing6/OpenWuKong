import contextlib
import io
import json
import unittest

from openwukong.connectors.browser import BrowserDevToolsTarget
from openwukong.evaluation.browser_devtools_action import (
    main,
    run_browser_devtools_action,
)


class _FakeDevToolsClient:
    def __init__(self, targets, evaluate_results=None, command_results=None):
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
                }
            ]
        )
        self.command_results = list(command_results or [{"frameId": "frame-1"}])
        self.list_calls = []
        self.evaluate_calls = []
        self.command_calls = []

    def list_targets(self, debugger_url):
        self.list_calls.append(debugger_url)
        return self.targets

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        if not self.evaluate_results:
            raise AssertionError("unexpected evaluate call")
        return self.evaluate_results.pop(0)

    def call_method(self, debugger_url, target, method, params=None):
        self.command_calls.append((debugger_url, target, method, dict(params or {})))
        if not self.command_results:
            return {}
        return self.command_results.pop(0)


class BrowserDevToolsActionTests(unittest.TestCase):
    def test_navigate_url_action_uses_page_navigate_after_health_gate(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="about:blank",
            url="about:blank",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient(
            [target],
            evaluate_results=[
                {
                    "type": "object",
                    "value": {
                        "title": "",
                        "href": "about:blank",
                        "readyState": "complete",
                    },
                },
                {
                    "type": "object",
                    "value": {
                        "title": "Search",
                        "href": "https://www.bing.com/search?q=openwukong",
                        "readyState": "complete",
                    },
                },
            ],
            command_results=[{"frameId": "frame-1", "loaderId": "loader-1"}],
        )

        report = run_browser_devtools_action(
            debugger_url="http://127.0.0.1:9223",
            window_title="about:blank - Google Chrome",
            resource_url="about:blank",
            action="navigate_url",
            url="https://www.bing.com/search?q=openwukong",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "browser-devtools-action")
        self.assertEqual(data["safety_mode"], "gated_browser_devtools_action")
        self.assertEqual(data["action"], "navigate_url")
        self.assertTrue(data["ok"])
        self.assertTrue(data["health_ok"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["action_result"]["navigated_url"], "https://www.bing.com/search?q=openwukong")
        self.assertEqual(data["post_action_identity"]["href"], "https://www.bing.com/search?q=openwukong")
        self.assertEqual(fake.command_calls[0][2], "Page.navigate")
        self.assertEqual(fake.command_calls[0][3]["url"], "https://www.bing.com/search?q=openwukong")

    def test_set_input_value_action_sets_value_and_dispatches_events(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Search",
            url="https://example.test/search",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient(
            [target],
            evaluate_results=[
                {
                    "type": "object",
                    "value": {
                        "title": "Search",
                        "href": "https://example.test/search",
                        "readyState": "complete",
                    },
                },
                {
                    "type": "object",
                    "value": {
                        "found": True,
                        "selector": "input[name=q]",
                        "value": "openwukong",
                    },
                },
            ],
        )

        report = run_browser_devtools_action(
            debugger_url="http://127.0.0.1:9223",
            window_title="Search - Google Chrome",
            resource_url="https://example.test/search",
            action="set_input_value",
            selector="input[name=q]",
            value="openwukong",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["action"], "set_input_value")
        self.assertEqual(data["action_result"]["selector"], "input[name=q]")
        self.assertEqual(data["action_result"]["value"], "openwukong")
        self.assertEqual(data["control_attempts"], 1)
        expression = fake.evaluate_calls[1][2]
        self.assertIn("querySelector", expression)
        self.assertIn("input", expression)
        self.assertIn("change", expression)

    def test_submit_form_action_submits_selector_form(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Search",
            url="https://example.test/search",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient(
            [target],
            evaluate_results=[
                {
                    "type": "object",
                    "value": {
                        "title": "Search",
                        "href": "https://example.test/search",
                        "readyState": "complete",
                    },
                },
                {
                    "type": "object",
                    "value": {
                        "found": True,
                        "submitted": True,
                        "selector": "input[name=q]",
                        "formAction": "https://example.test/search",
                    },
                },
                {
                    "type": "object",
                    "value": {
                        "title": "Results",
                        "href": "https://example.test/search?q=openwukong",
                        "readyState": "complete",
                    },
                },
            ],
        )

        report = run_browser_devtools_action(
            debugger_url="http://127.0.0.1:9223",
            window_title="Search - Google Chrome",
            resource_url="https://example.test/search",
            action="submit_form",
            selector="input[name=q]",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["action"], "submit_form")
        self.assertEqual(data["action_result"]["selector"], "input[name=q]")
        self.assertTrue(data["action_result"]["submitted"])
        self.assertEqual(data["post_action_identity"]["href"], "https://example.test/search?q=openwukong")
        self.assertEqual(data["control_attempts"], 1)
        expression = fake.evaluate_calls[1][2]
        self.assertIn("requestSubmit", expression)
        self.assertIn("closest('form')", expression)

    def test_action_refuses_when_health_gate_fails(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="Search",
            url="https://example.test/search",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        fake = _FakeDevToolsClient([target])

        report = run_browser_devtools_action(
            debugger_url="http://127.0.0.1:9223",
            window_title="Other - Google Chrome",
            resource_url="https://example.test/other",
            action="set_input_value",
            selector="input[name=q]",
            value="openwukong",
            devtools_client=fake,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertFalse(data["health_ok"])
        self.assertEqual(data["error"], "devtools_target_not_matched")
        self.assertEqual(fake.command_calls, [])
        self.assertEqual(fake.evaluate_calls, [])

    def test_cli_outputs_browser_devtools_action_json(self):
        target = BrowserDevToolsTarget(
            target_id="page-1",
            type="page",
            title="about:blank",
            url="about:blank",
            web_socket_debugger_url="ws://127.0.0.1/devtools/page/page-1",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--debugger-url",
                    "http://127.0.0.1:9223",
                    "--window-title",
                    "about:blank - Google Chrome",
                    "--resource-url",
                    "about:blank",
                    "--action",
                    "navigate_url",
                    "--url",
                    "https://www.bing.com/search?q=openwukong",
                    "--json",
                ],
                devtools_client=_FakeDevToolsClient(
                    [target],
                    evaluate_results=[
                        {
                            "type": "object",
                            "value": {
                                "title": "",
                                "href": "about:blank",
                                "readyState": "complete",
                            },
                        },
                        {
                            "type": "object",
                            "value": {
                                "title": "Search",
                                "href": "https://www.bing.com/search?q=openwukong",
                                "readyState": "complete",
                            },
                        },
                    ],
                ),
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "browser-devtools-action")
        self.assertTrue(data["ok"], data["error"])
        self.assertEqual(data["action"], "navigate_url")


if __name__ == "__main__":
    unittest.main()
