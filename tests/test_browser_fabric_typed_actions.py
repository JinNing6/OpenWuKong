import unittest

from openwukong.connectors.base import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent


class BrowserFabricTypedActionTests(unittest.TestCase):
    def test_fabric_maps_typed_read_before_devtools_runner(self):
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            return {"ok": True, "readback_verified": True, "action": kwargs["action"]}

        target = ConnectorTarget(
            process_name="chrome.exe",
            window_title="Example - Chrome",
            resource_url="https://example.test/",
            debugger_url="http://127.0.0.1:9222",
        )
        report = ControlFabric.with_default_connectors().execute(
            target,
            ControlIntent(action="browser.page.read"),
            allow_control=True,
            browser_action_runner=runner,
        )
        self.assertTrue(report.ok, report.error)
        self.assertEqual(calls[0]["action"], "read_page")

    def test_fabric_forwards_typed_input_parameters(self):
        calls = []

        def runner(**kwargs):
            calls.append(kwargs)
            return {"ok": True, "readback_verified": True}

        target = ConnectorTarget(
            process_name="msedge.exe",
            resource_url="https://example.test/",
            debugger_url="http://127.0.0.1:9222",
        )
        report = ControlFabric.with_default_connectors().execute(
            target,
            ControlIntent(
                action="browser.input.set",
                parameters={"selector": "#q", "value": "hello"},
            ),
            allow_control=True,
            browser_action_runner=runner,
        )
        self.assertTrue(report.ok, report.error)
        self.assertEqual(calls[0]["action"], "set_input_value")
        self.assertEqual(calls[0]["selector"], "#q")
        self.assertEqual(calls[0]["value"], "hello")


if __name__ == "__main__":
    unittest.main()
