import unittest

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.browser import BrowserSessionConnector
from openwukong.control.fabric import ControlIntent


class _Report:
    def __init__(self, *, ok=True):
        self.ok = ok

    def to_dict(self):
        return {
            "ok": self.ok,
            "action": "read_page",
            "post_action_identity": {"href": "https://example.test/"},
        }


class BrowserTypedActionTests(unittest.TestCase):
    def test_typed_read_maps_to_health_gated_runner(self):
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            return _Report()

        connector = BrowserSessionConnector(action_runner=runner)
        target = ConnectorTarget(
            process_name="msedge.exe",
            debugger_url="http://127.0.0.1:9222",
            resource_url="https://example.test/",
        )
        result = connector.execute_action(
            target,
            ControlIntent(action="browser.page.read"),
        )
        self.assertTrue(result.success, result.error)
        self.assertTrue(result.payload["readback_verified"])
        self.assertEqual(result.payload["route_id"], "browser-devtools-or-extension")
        self.assertEqual(calls[0]["action"], "read_page")

    def test_typed_input_passes_selector_and_value(self):
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            return _Report()

        connector = BrowserSessionConnector(action_runner=runner)
        target = ConnectorTarget(
            process_name="chrome.exe",
            debugger_url="http://127.0.0.1:9222",
        )
        result = connector.execute_action(
            target,
            ControlIntent(
                action="browser.input.set",
                value="hello",
                parameters={"selector": "#q"},
            ),
        )
        self.assertTrue(result.success)
        self.assertEqual(calls[0]["action"], "set_input_value")
        self.assertEqual(calls[0]["selector"], "#q")
        self.assertEqual(calls[0]["value"], "hello")

    def test_typed_action_requires_debugger_url(self):
        connector = BrowserSessionConnector(action_runner=lambda **kwargs: _Report())
        result = connector.execute_action(
            ConnectorTarget(process_name="chrome.exe"),
            ControlIntent(action="browser.page.read"),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "browser_debugger_url_required")


if __name__ == "__main__":
    unittest.main()
