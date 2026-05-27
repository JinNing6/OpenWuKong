import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_discovery import (
    DiscoveredControlTarget,
    SessionDiscovery,
    SessionDiscoveryOptions,
)


class _FakeHTTPProbe:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.get_responses = dict(get_responses or {})
        self.post_responses = dict(post_responses or {})
        self.get_calls = []
        self.post_calls = []

    def get_json(self, url, timeout=0.2):
        del timeout
        self.get_calls.append(url)
        if url not in self.get_responses:
            raise OSError("connection_failed")
        return self.get_responses[url]

    def post_json(self, url, payload, timeout=0.2):
        del timeout
        self.post_calls.append((url, payload))
        if url not in self.post_responses:
            raise OSError("connection_failed")
        return self.post_responses[url]


class SessionDiscoveryTests(unittest.TestCase):
    def test_discovers_browser_debugger_url_from_read_only_devtools_endpoint(self):
        probe = _FakeHTTPProbe(
            get_responses={
                "http://127.0.0.1:9222/json/version": {
                    "Browser": "Chrome/126.0",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/abc",
                },
                "http://127.0.0.1:9222/json/list": [
                    {
                        "type": "page",
                        "title": "Example Domain",
                        "url": "https://example.com/",
                    }
                ],
            }
        )
        discovery = SessionDiscovery(
            SessionDiscoveryOptions(browser_debug_ports=(9222,)),
            http_probe=probe,
        )

        result = discovery.enrich(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Example Domain - Google Chrome",
            )
        )
        data = result.to_dict()

        self.assertIsInstance(result, DiscoveredControlTarget)
        self.assertEqual(result.debugger_url, "http://127.0.0.1:9222")
        self.assertEqual(data["discovered_fields"]["debugger_url"], "http://127.0.0.1:9222")
        self.assertEqual(data["evidence"][0]["kind"], "browser_devtools")

        dispatch = ControlFabric.with_default_connectors().dispatch(
            result,
            ControlIntent(action="write_text", text="OPENWUKONG"),
        )
        self.assertEqual(dispatch.to_dict()["decision"], "dispatch_connector")
        self.assertTrue(dispatch.to_dict()["connector_ready"])

    def test_does_not_bind_chrome_devtools_endpoint_to_edge_window(self):
        probe = _FakeHTTPProbe(
            get_responses={
                "http://127.0.0.1:9223/json/version": {
                    "Browser": "Chrome/148.0",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/browser/abc",
                },
                "http://127.0.0.1:9223/json/list": [
                    {
                        "type": "page",
                        "title": "about:blank",
                        "url": "about:blank",
                    }
                ],
            }
        )
        discovery = SessionDiscovery(
            SessionDiscoveryOptions(browser_debug_ports=(9223,)),
            http_probe=probe,
        )

        result = discovery.enrich(
            ConnectorTarget(
                process_name="msedge.exe",
                window_title="Reference - Microsoft Edge",
            )
        )

        self.assertEqual(result.debugger_url, "")
        dispatch = ControlFabric.with_default_connectors().dispatch(
            result,
            ControlIntent(action="write_text", text="OPENWUKONG"),
        )
        self.assertEqual(dispatch.to_dict()["decision"], "connector_required")
        self.assertFalse(dispatch.to_dict()["connector_ready"])

    def test_browser_debugger_discovery_requires_visible_target_match(self):
        probe = _FakeHTTPProbe(
            get_responses={
                "http://127.0.0.1:9223/json/version": {
                    "Browser": "Chrome/148.0",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/browser/abc",
                },
                "http://127.0.0.1:9223/json/list": [
                    {
                        "type": "page",
                        "title": "about:blank",
                        "url": "about:blank",
                    }
                ],
            }
        )
        discovery = SessionDiscovery(
            SessionDiscoveryOptions(browser_debug_ports=(9223,)),
            http_probe=probe,
        )

        result = discovery.enrich(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Unrelated Page - Google Chrome",
            )
        )

        self.assertEqual(result.debugger_url, "")

    def test_discovers_ide_bridge_url_from_read_only_capabilities_endpoint(self):
        probe = _FakeHTTPProbe(
            post_responses={
                "http://127.0.0.1:8787/v1/ide/capabilities": {
                    "ok": True,
                    "metadata": {"ide_name": "Cursor"},
                }
            }
        )
        discovery = SessionDiscovery(
            SessionDiscoveryOptions(ide_bridge_urls=("http://127.0.0.1:8787",)),
            http_probe=probe,
        )

        result = discovery.enrich(
            ConnectorTarget(process_name="Cursor.exe", window_title="Cursor")
        )
        data = result.to_dict()

        self.assertEqual(result.ide_bridge_url, "http://127.0.0.1:8787")
        self.assertEqual(data["discovered_fields"]["ide_bridge_url"], "http://127.0.0.1:8787")
        self.assertEqual(probe.post_calls[0][1]["action"], "read_capabilities")

        dispatch = ControlFabric.with_default_connectors().dispatch(
            result,
            ControlIntent(action="send_message", text="OPENWUKONG"),
        )
        self.assertEqual(dispatch.to_dict()["decision"], "dispatch_connector")
        self.assertEqual(dispatch.to_dict()["selected_connector_id"], "ide-extension")

    def test_discovers_terminal_workspace_only_when_window_identity_matches_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "openwukong"
            workspace.mkdir()
            discovery = SessionDiscovery(
                SessionDiscoveryOptions(workspace_roots=(str(workspace),))
            )

            matched = discovery.enrich(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="openwukong - PowerShell",
                )
            )
            unmatched = discovery.enrich(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="other-project - PowerShell",
                )
            )

            self.assertEqual(Path(matched.workspace_path).resolve(), workspace.resolve())
            self.assertEqual(unmatched.workspace_path, "")
            self.assertEqual(matched.to_dict()["evidence"][0]["kind"], "workspace_root")

    def test_preserves_existing_session_fields_without_probe_calls(self):
        probe = _FakeHTTPProbe()
        discovery = SessionDiscovery(
            SessionDiscoveryOptions(
                browser_debug_ports=(9222,),
                ide_bridge_urls=("http://127.0.0.1:8787",),
            ),
            http_probe=probe,
        )

        result = discovery.enrich(
            ConnectorTarget(
                process_name="Cursor.exe",
                window_title="Cursor",
                ide_bridge_url="http://127.0.0.1:8787",
            )
        )

        self.assertEqual(result.ide_bridge_url, "http://127.0.0.1:8787")
        self.assertEqual(probe.get_calls, [])
        self.assertEqual(probe.post_calls, [])


if __name__ == "__main__":
    unittest.main()
