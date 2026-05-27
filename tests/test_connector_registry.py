import unittest

from openwukong.connectors import (
    ConnectorManager,
    ConnectorTarget,
    TerminalCommandConnector,
    UIAIDEConnector,
)


class ConnectorRegistryTests(unittest.TestCase):
    def test_uia_connector_supports_codex_process(self):
        connector = UIAIDEConnector()
        target = ConnectorTarget(pid=123, process_name="Codex.exe", window_title="Codex")
        self.assertTrue(connector.supports_target(target))

    def test_manager_returns_explicit_preference(self):
        connector = UIAIDEConnector()
        manager = ConnectorManager([connector])
        target = ConnectorTarget(pid=123, process_name="Codex.exe")
        resolved = manager.resolve_session_connector(target, preferred="uia-ide")
        self.assertIs(resolved, connector)

    def test_manager_falls_back_by_target_support(self):
        connector = UIAIDEConnector()
        manager = ConnectorManager([connector])
        target = ConnectorTarget(pid=456, process_name="Cursor.exe")
        resolved = manager.resolve_session_connector(target)
        self.assertEqual(resolved.connector_id, "uia-ide")

    def test_route_policy_enforcement_blocks_unsafe_app_even_with_explicit_preference(self):
        manager = ConnectorManager([UIAIDEConnector()])
        target = ConnectorTarget(
            pid=58756,
            process_name="Weixin.exe",
            window_title="微信",
        )

        with self.assertRaisesRegex(PermissionError, "route_policy_blocked"):
            manager.resolve_session_connector(
                target,
                preferred="uia-ide",
                enforce_route_policy=True,
            )

    def test_route_policy_enforcement_allows_terminal_native_connector(self):
        terminal = TerminalCommandConnector()
        manager = ConnectorManager([UIAIDEConnector(), terminal])
        target = ConnectorTarget(
            pid=5248,
            process_name="WindowsTerminal.exe",
            window_title="Windows PowerShell",
            workspace_path=".",
        )

        resolved = manager.resolve_session_connector(
            target,
            enforce_route_policy=True,
        )

        self.assertIs(resolved, terminal)


if __name__ == "__main__":
    unittest.main()
