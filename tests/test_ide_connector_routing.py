import unittest

from openwukong.connectors import (
    CodexDesktopConnector,
    ConnectorManager,
    ConnectorTarget,
    CopilotIDEConnector,
    CursorIDEConnector,
    GitCommandConnector,
    UIAIDEConnector,
)


class IDEConnectorRoutingTests(unittest.TestCase):
    def test_codex_connector_beats_generic_uia(self):
        manager = ConnectorManager([UIAIDEConnector(), CodexDesktopConnector()])
        target = ConnectorTarget(pid=101, process_name="Codex.exe", window_title="OpenWukong - Codex")
        resolved = manager.resolve_session_connector(target)
        self.assertEqual(resolved.connector_id, "codex")

    def test_cursor_connector_beats_generic_uia(self):
        manager = ConnectorManager([UIAIDEConnector(), CursorIDEConnector()])
        target = ConnectorTarget(pid=202, process_name="Cursor.exe", window_title="main.py - openwukong - Cursor")
        resolved = manager.resolve_session_connector(target)
        self.assertEqual(resolved.connector_id, "cursor")

    def test_copilot_connector_beats_generic_uia_for_vscode(self):
        manager = ConnectorManager([UIAIDEConnector(), CopilotIDEConnector()])
        target = ConnectorTarget(pid=303, process_name="Code.exe", window_title="app.py - openwukong - Visual Studio Code")
        resolved = manager.resolve_session_connector(target)
        self.assertEqual(resolved.connector_id, "copilot")

    def test_git_connector_does_not_steal_ide_target_from_uia(self):
        manager = ConnectorManager([GitCommandConnector(), UIAIDEConnector()])
        target = ConnectorTarget(
            pid=404,
            process_name="Cursor.exe",
            window_title="main.py - openwukong - Cursor",
            workspace_path=".",
        )
        resolved = manager.resolve_session_connector(target)
        self.assertEqual(resolved.connector_id, "uia-ide")


if __name__ == "__main__":
    unittest.main()
