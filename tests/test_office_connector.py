import tempfile
import unittest
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.office import OfficeSessionConnector
from openwukong.control.fabric import ControlIntent


class _FakeWordContent:
    def __init__(self):
        self.Text = ""

    def InsertAfter(self, value):
        self.Text += str(value)


class _FakeWordDocument:
    def __init__(self, store, path=""):
        self._store = store
        self.path = path
        self.Content = _FakeWordContent()
        if path and path in store:
            self.Content.Text = store[path]

    def SaveAs2(self, *, FileName, **kwargs):
        del kwargs
        self.path = str(FileName)
        self._store[self.path] = self.Content.Text
        Path(self.path).write_bytes(self.Content.Text.encode("utf-8"))

    def Save(self):
        self._store[self.path] = self.Content.Text
        Path(self.path).write_bytes(self.Content.Text.encode("utf-8"))

    def Close(self, **kwargs):
        del kwargs


class _FakeWordDocuments:
    def __init__(self, store):
        self._store = store

    def Add(self):
        return _FakeWordDocument(self._store)

    def Open(self, *, FileName, **kwargs):
        del kwargs
        return _FakeWordDocument(self._store, str(FileName))


class _FakeWordApp:
    def __init__(self, store):
        self.Documents = _FakeWordDocuments(store)

    def Quit(self):
        pass


class _FakeExcelCell:
    def __init__(self, sheet, address):
        self.sheet = sheet
        self.address = address

    @property
    def Value(self):
        return self.sheet.values.get(self.address)

    @Value.setter
    def Value(self, value):
        self.sheet.values[self.address] = value


class _FakeExcelSheet:
    def __init__(self):
        self.values = {}

    def Range(self, address):
        return _FakeExcelCell(self, str(address))


class _FakeExcelSheets:
    def __init__(self, sheet):
        self.sheet = sheet

    def Item(self, name):
        del name
        return self.sheet


class _FakeExcelWorkbook:
    def __init__(self, sheet):
        self.Worksheets = _FakeExcelSheets(sheet)

    def Save(self):
        pass

    def Close(self, **kwargs):
        del kwargs


class _FakeExcelWorkbooks:
    def __init__(self, sheet):
        self.sheet = sheet

    def Open(self, **kwargs):
        del kwargs
        return _FakeExcelWorkbook(self.sheet)


class _FakeExcelApp:
    def __init__(self, sheet):
        self.Workbooks = _FakeExcelWorkbooks(sheet)

    def Quit(self):
        pass


class OfficeConnectorTests(unittest.TestCase):
    def test_match_score_is_bound_to_office_targets(self):
        connector = OfficeSessionConnector()
        self.assertGreater(
            connector.match_score(
                ConnectorTarget(process_name="WINWORD.EXE", window_title="a.docx - Word")
            ),
            0,
        )
        self.assertLess(
            connector.match_score(ConnectorTarget(process_name="notepad.exe")),
            0,
        )

    def test_word_create_requires_confirmation_and_reads_back(self):
        store = {}
        connector = OfficeSessionConnector(
            application_factory=lambda kind: _FakeWordApp(store)
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "note.docx"
            target = ConnectorTarget(
                process_name="WINWORD.EXE",
                workspace_path=root,
                window_title="Word",
            )
            blocked = connector.execute_action(
                target,
                ControlIntent(
                    action="office.word.create",
                    parameters={"path": str(path), "body": "hello"},
                ),
            )
            self.assertFalse(blocked.success)
            self.assertEqual(blocked.error, "office_confirmation_required")
            result = connector.execute_action(
                target,
                ControlIntent(
                    action="office.word.create",
                    allow_submit=True,
                    parameters={"path": str(path), "body": "hello"},
                ),
            )
            self.assertTrue(result.success, result.error)
            self.assertTrue(result.payload["readback_verified"])
            self.assertEqual(result.payload["text"], "hello")

    def test_excel_write_cell_reports_value_readback(self):
        sheet = _FakeExcelSheet()
        connector = OfficeSessionConnector(
            application_factory=lambda kind: _FakeExcelApp(sheet)
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "book.xlsx"
            path.write_bytes(b"fixture")
            target = ConnectorTarget(
                process_name="EXCEL.EXE",
                workspace_path=root,
                window_title="Excel",
            )
            result = connector.execute_action(
                target,
                ControlIntent(
                    action="office.excel.write_cell",
                    allow_submit=True,
                    parameters={
                        "path": str(path),
                        "sheet": "Sheet1",
                        "cell": "A1",
                        "value": "42",
                    },
                ),
            )
            self.assertTrue(result.success, result.error)
            self.assertTrue(result.payload["readback_verified"])
            self.assertEqual(result.payload["value"], "42")

    def test_paths_must_stay_inside_workspace_root(self):
        connector = OfficeSessionConnector(
            application_factory=lambda kind: _FakeWordApp({})
        )
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            target = ConnectorTarget(process_name="WINWORD.EXE", workspace_path=root)
            result = connector.execute_action(
                target,
                ControlIntent(
                    action="office.word.create",
                    allow_submit=True,
                    parameters={"path": str(Path(other) / "escape.docx"), "body": "x"},
                ),
            )
            self.assertFalse(result.success)
            self.assertEqual(result.error, "office_path_outside_root")


if __name__ == "__main__":
    unittest.main()
