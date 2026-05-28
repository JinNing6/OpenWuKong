# -*- coding: utf-8 -*-
"""No-loss background Microsoft Word COM probe."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Callable, Optional


WD_FORMAT_XML_DOCUMENT = 12
WD_ALERTS_NONE = 0


@dataclasses.dataclass(frozen=True)
class OfficeWordBackgroundProbeReport:
    document_path: str
    marker: str
    readback_text: str = ""
    ok: bool = False
    error: str = ""
    elapsed_ms: float = 0.0
    word_started: bool = False
    visible_requested: bool = False
    save_verified: bool = False
    readback_verified: bool = False
    office_com_attempts: int = 0

    @property
    def mode(self) -> str:
        return "office-word-background-probe"

    @property
    def safety_mode(self) -> str:
        return "background_office_com_no_loss"

    @property
    def control_allowed(self) -> bool:
        return bool(self.ok)

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def decision(self) -> str:
        if self.ok:
            return "word_background_probe_verified"
        if self.office_com_attempts == 0:
            return "word_com_not_available"
        if not self.save_verified:
            return "word_background_save_not_verified"
        if not self.readback_verified:
            return "word_background_readback_failed"
        return "word_background_probe_failed"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "document_path": self.document_path,
            "marker": self.marker,
            "readback_text": self.readback_text,
            "save_verified": self.save_verified,
            "readback_verified": self.readback_verified,
            "word_started": self.word_started,
            "visible_requested": self.visible_requested,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "office_com_attempts": int(self.office_com_attempts or 0),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_office_word_background_probe(
    *,
    document_path: str,
    marker: str = "OPENWUKONG_WORD_BACKGROUND_OK",
    word_factory: Callable[[], object] | None = None,
) -> OfficeWordBackgroundProbeReport:
    started = time.perf_counter()
    path = Path(document_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    marker_text = str(marker or "").strip() or "OPENWUKONG_WORD_BACKGROUND_OK"
    body = (
        "OpenWukong Word background COM probe\n"
        f"Marker: {marker_text}\n"
        f"Timestamp: {int(time.time())}\n"
    )
    app = None
    office_attempts = 0
    word_started = False
    save_verified = False
    readback_text = ""
    try:
        factory = word_factory or _create_word_application
        try:
            app = factory()
        except Exception as exc:
            return OfficeWordBackgroundProbeReport(
                document_path=str(path),
                marker=marker_text,
                ok=False,
                error=str(exc) or exc.__class__.__name__,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                office_com_attempts=0,
            )
        word_started = True
        office_attempts = 1
        _set_word_background_mode(app)

        document = None
        read_document = None
        try:
            document = app.Documents.Add()
            document.Content.Text = body
            document.SaveAs2(
                FileName=str(path),
                FileFormat=WD_FORMAT_XML_DOCUMENT,
                AddToRecentFiles=False,
            )
            save_verified = path.is_file() and path.stat().st_size > 0
            document.Close(SaveChanges=False)
            document = None

            read_document = app.Documents.Open(
                FileName=str(path),
                ReadOnly=True,
                AddToRecentFiles=False,
                Visible=False,
            )
            readback_text = str(read_document.Content.Text or "")
            read_document.Close(SaveChanges=False)
            read_document = None
        finally:
            if document is not None:
                _close_document(document)
            if read_document is not None:
                _close_document(read_document)
    except Exception as exc:
        return OfficeWordBackgroundProbeReport(
            document_path=str(path),
            marker=marker_text,
            readback_text=readback_text,
            ok=False,
            error=str(exc) or exc.__class__.__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            word_started=word_started,
            save_verified=save_verified,
            readback_verified=marker_text in readback_text,
            office_com_attempts=office_attempts,
        )
    finally:
        if app is not None:
            _quit_word(app)

    readback_verified = marker_text in readback_text
    return OfficeWordBackgroundProbeReport(
        document_path=str(path),
        marker=marker_text,
        readback_text=readback_text,
        ok=bool(save_verified and readback_verified),
        elapsed_ms=(time.perf_counter() - started) * 1000,
        word_started=word_started,
        visible_requested=False,
        save_verified=save_verified,
        readback_verified=readback_verified,
        office_com_attempts=office_attempts,
    )


def format_office_word_background_probe_report(
    report: OfficeWordBackgroundProbeReport,
) -> str:
    return (
        "Office Word background probe\n"
        f"Decision: {report.decision}  OK: {str(report.ok).lower()}  "
        f"Control attempts: {report.control_attempts}  COM attempts: {report.office_com_attempts}\n"
        f"Document: {report.document_path}\n"
        f"Save verified: {str(report.save_verified).lower()}  "
        f"Readback verified: {str(report.readback_verified).lower()}"
    ).rstrip()


def main(
    argv: Optional[list[str]] = None,
    *,
    word_factory: Callable[[], object] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run a hidden Microsoft Word COM no-loss background probe."
    )
    parser.add_argument("--document-path", required=True)
    parser.add_argument("--marker", default="OPENWUKONG_WORD_BACKGROUND_OK")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_office_word_background_probe(
        document_path=args.document_path,
        marker=args.marker,
        word_factory=word_factory,
    )
    payload = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _write_stdout(format_office_word_background_probe_report(report))
    return 0


def _create_word_application() -> object:
    try:
        import pythoncom

        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import win32com.client
    except Exception as exc:
        raise RuntimeError(f"pywin32_not_available: {exc}") from exc
    try:
        return win32com.client.DispatchEx("Word.Application")
    except Exception as exc:
        raise RuntimeError(f"word_com_dispatch_failed: {exc}") from exc


def _set_word_background_mode(app: object) -> None:
    try:
        app.Visible = False
    except Exception:
        pass
    try:
        app.DisplayAlerts = WD_ALERTS_NONE
    except Exception:
        pass


def _close_document(document: object) -> None:
    try:
        document.Close(SaveChanges=False)
    except Exception:
        pass


def _quit_word(app: object) -> None:
    try:
        app.Quit()
    except Exception:
        pass
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except Exception:
        pass


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


if __name__ == "__main__":
    raise SystemExit(main())
