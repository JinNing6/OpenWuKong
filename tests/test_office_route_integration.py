import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.office import OfficeSessionConnector
from openwukong.connectors.registry import ConnectorManager
from openwukong.connectors.base import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent


class _FakeDocument:
    def __init__(self, path="", text=""):
        self.path = path
        self.Content = type("Content", (), {"Text": text})()

    def SaveAs2(self, **kwargs):
        self.path = kwargs["FileName"]
        Path(self.path).write_bytes(self.Content.Text.encode())

    def Close(self, **kwargs):
        del kwargs


class _FakeWordApp:
    def __init__(self):
        self.Documents = type("Docs", (), {})()
        self.Documents.Add = lambda: _FakeDocument()
        self.Documents.Open = lambda **kwargs: _FakeDocument(
            kwargs["FileName"], Path(kwargs["FileName"]).read_text(encoding="utf-8")
        )

    def Quit(self):
        pass


class OfficeRouteIntegrationTests(unittest.TestCase):
    def test_dispatch_selects_office_connector_when_com_is_available(self):
        with tempfile.TemporaryDirectory() as root:
            target = ConnectorTarget(
                process_name="WINWORD.EXE",
                window_title="Document - Word",
                workspace_path=root,
            )
            connector = OfficeSessionConnector(application_factory=lambda kind: _FakeWordApp())
            fabric = ControlFabric(
                connector_manager=ConnectorManager([connector]),
                require_connector_session_ready=True,
            )
            report = fabric.dispatch(
                target,
                ControlIntent(action="office.word.create", parameters={"path": str(Path(root) / "x.docx")}),
            )
        self.assertEqual(report.selected_route, "office-object-model-or-addin")
        self.assertEqual(report.selected_connector_id, "office")
        self.assertTrue(report.connector_ready)

    def test_execute_uses_background_com_without_foreground_input(self):
        with tempfile.TemporaryDirectory() as root:
            target = ConnectorTarget(
                process_name="WINWORD.EXE",
                window_title="Document - Word",
                workspace_path=root,
            )
            path = Path(root) / "x.docx"
            connector = OfficeSessionConnector(application_factory=lambda kind: _FakeWordApp())
            fabric = ControlFabric(
                connector_manager=ConnectorManager([connector]),
                require_connector_session_ready=True,
            )
            report = fabric.execute(
                target,
                ControlIntent(
                    action="office.word.create",
                    allow_submit=True,
                    parameters={"path": str(path), "body": "background"},
                ),
                allow_control=True,
            )
        self.assertTrue(report.ok, report.error)
        self.assertEqual(report.selected_route, "office-object-model-or-addin")
        self.assertEqual(report.action_report["payload"]["control_attempts"], 1)
        self.assertFalse(report.action_report["payload"]["foreground_required"])


if __name__ == "__main__":
    unittest.main()
