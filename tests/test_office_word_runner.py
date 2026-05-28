import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.office_word_runner import (
    run_office_word_background_probe,
    main,
)


class OfficeWordRunnerTests(unittest.TestCase):
    def test_hidden_word_com_probe_writes_saves_reads_and_quits(self):
        fake = _FakeWordFactory()

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "probe.docx"
            report = run_office_word_background_probe(
                document_path=str(output),
                marker="OPENWUKONG_WORD_BACKGROUND_OK",
                word_factory=fake.create,
            )
            data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "word_background_probe_verified")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["office_com_attempts"], 1)
        self.assertEqual(data["visible_requested"], False)
        self.assertIn("OPENWUKONG_WORD_BACKGROUND_OK", data["readback_text"])
        self.assertEqual(fake.app.Visible, False)
        self.assertEqual(fake.app.DisplayAlerts, 0)
        self.assertTrue(fake.app.quit_called)
        resolved_output = str(output.resolve())
        self.assertEqual(fake.saved_paths, [resolved_output])
        self.assertEqual(fake.opened_paths, [resolved_output])

    def test_word_com_unavailable_reports_not_available_without_attempt(self):
        def factory():
            raise RuntimeError("word com unavailable")

        with tempfile.TemporaryDirectory() as td:
            report = run_office_word_background_probe(
                document_path=str(Path(td) / "probe.docx"),
                marker="OPENWUKONG_WORD_BACKGROUND_OK",
                word_factory=factory,
            )
            data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "word_com_not_available")
        self.assertEqual(data["office_com_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertIn("word com unavailable", data["error"])

    def test_cli_writes_json_report(self):
        fake = _FakeWordFactory()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "report.json"
            document = root / "probe.docx"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--document-path",
                        str(document),
                        "--marker",
                        "OPENWUKONG_WORD_BACKGROUND_OK",
                        "--output",
                        str(output),
                        "--json",
                    ],
                    word_factory=fake.create,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "office-word-background-probe")
        self.assertEqual(payload["decision"], "word_background_probe_verified")
        self.assertEqual(payload["control_attempts"], 0)


class _FakeWordFactory:
    def __init__(self):
        self.app = _FakeWordApp(self)
        self.saved_paths = []
        self.opened_paths = []
        self.last_text = ""

    def create(self):
        return self.app


class _FakeWordApp:
    def __init__(self, owner):
        self.owner = owner
        self.Visible = True
        self.DisplayAlerts = -1
        self.Documents = _FakeDocuments(owner)
        self.quit_called = False

    def Quit(self):
        self.quit_called = True


class _FakeDocuments:
    def __init__(self, owner):
        self.owner = owner

    def Add(self):
        return _FakeDocument(self.owner, "")

    def Open(self, **kwargs):
        path = str(kwargs.get("FileName", ""))
        self.owner.opened_paths.append(path)
        return _FakeDocument(self.owner, self.owner.last_text)


class _FakeDocument:
    def __init__(self, owner, text):
        self.owner = owner
        self.Content = _FakeRange(text)
        self.close_calls = []

    def SaveAs2(self, **kwargs):
        path = str(kwargs.get("FileName", ""))
        self.owner.saved_paths.append(path)
        self.owner.last_text = self.Content.Text
        Path(path).write_bytes(b"fake-docx")

    def Close(self, SaveChanges=False):
        self.close_calls.append(SaveChanges)


class _FakeRange:
    def __init__(self, text):
        self.Text = text


if __name__ == "__main__":
    unittest.main()
