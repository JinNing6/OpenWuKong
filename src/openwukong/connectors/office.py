# -*- coding: utf-8 -*-
"""Workspace-bound Microsoft Office object-model connector.

The connector keeps Office actions behind the shared typed-intent boundary.
It creates a private COM application instance, performs one bounded operation,
reads the resulting state back, and quits the instance.  It never drives the
visible Office window or uses keyboard/mouse input.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from typing import Any, Callable

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)


_OFFICE_PROCESSES = {
    "winword.exe": "word",
    "word.exe": "word",
    "excel.exe": "excel",
    "powerpnt.exe": "powerpoint",
    "powerpoint.exe": "powerpoint",
}
_OFFICE_TITLES = {
    "word": ("word", "文档"),
    "excel": ("excel", "工作簿"),
    "powerpoint": ("powerpoint", "演示文稿"),
}
_READ_ACTIONS = {
    "office.document.inspect",
    "office.document.read",
    "office.word.read",
    "office.excel.read_cell",
    "office.spreadsheet.read_cell",
    "office.powerpoint.read",
    "office.presentation.read",
}
_WRITE_ACTIONS = {
    "office.document.create",
    "office.document.write",
    "office.document.append",
    "office.word.create",
    "office.word.write",
    "office.word.append",
    "office.excel.write_cell",
    "office.spreadsheet.write_cell",
    "office.powerpoint.add_text",
    "office.presentation.add_text",
}


@dataclasses.dataclass(frozen=True)
class OfficeDocumentIdentity:
    path: str
    app_kind: str
    suffix: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class OfficeSessionConnector(SessionConnector):
    """Execute basic Word, Excel, and PowerPoint operations through COM."""

    connector_id = "office"
    display_name = "Microsoft Office"
    route_id = "office-object-model-or-addin"
    route_ids = ("office-object-model-or-addin",)
    transport_mode = "background_native"

    def __init__(
        self,
        *,
        application_factory: Callable[[str], object] | None = None,
    ):
        self._application_factory = application_factory or _create_application

    def supports_target(self, target: ConnectorTarget) -> bool:
        return _target_app_kind(target) is not None

    def match_score(self, target: ConnectorTarget) -> int:
        kind = _target_app_kind(target)
        if kind is None:
            return -1
        process = str(target.process_name or "").strip().casefold()
        if process in _OFFICE_PROCESSES:
            return 240
        suffix = Path(str(target.workspace_path or target.resource_url or "")).suffix.casefold()
        if suffix in _suffixes_for(kind):
            return 220
        return 140

    def route_ready(self, route_id: str, target: ConnectorTarget) -> bool:
        if route_id not in self.route_ids or not self.supports_target(target):
            return False
        try:
            import pythoncom  # noqa: F401
            import win32com.client  # noqa: F401
        except Exception:
            return False
        return True

    def read_conversation(self, target: ConnectorTarget) -> str:
        """Return a short read-only identity for legacy callers."""
        kind = _target_app_kind(target) or "office"
        return f"{kind} target: {target.window_title or target.workspace_path}".strip()

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown, message
        return self._failure("send_message", "office_requires_typed_intent", target)

    def execute_action(
        self,
        target: ConnectorTarget,
        intent: object,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        del cooldown
        action = _normalize_action(getattr(intent, "action", ""))
        parameters = _intent_parameters(intent)
        kind = _target_app_kind(target)
        if kind is None:
            return self._failure(action, "office_target_required", target)
        if action not in _READ_ACTIONS | _WRITE_ACTIONS:
            return self._failure(action, "office_capability_missing", target)
        if action in _WRITE_ACTIONS and not bool(
            getattr(intent, "allow_submit", False) or parameters.get("confirmed", False)
        ):
            return self._failure(action, "office_confirmation_required", target)

        try:
            if action == "office.document.inspect":
                return self._success(action, _inspect_path(target, parameters, kind))
            path = _resolve_owned_path(target, parameters)
            if action in {"office.document.read", "office.word.read"}:
                payload = self._run(kind, lambda app: _read_document(app, kind, path))
            elif action in {"office.word.create", "office.document.create"}:
                body = str(parameters.get("body", parameters.get("text", "")) or "")
                payload = self._run(kind, lambda app: _write_word(app, path, body, append=False))
            elif action in {"office.word.write", "office.document.write"}:
                body = str(parameters.get("body", parameters.get("text", "")) or "")
                payload = self._run(kind, lambda app: _write_word(app, path, body, append=False))
            elif action in {"office.word.append", "office.document.append"}:
                body = str(parameters.get("body", parameters.get("text", "")) or "")
                payload = self._run(kind, lambda app: _write_word(app, path, body, append=True))
            elif action in {"office.excel.read_cell", "office.spreadsheet.read_cell"}:
                payload = self._run(
                    "excel",
                    lambda app: _read_excel_cell(
                        app,
                        path,
                        str(parameters.get("sheet", "Sheet1") or "Sheet1"),
                        str(parameters.get("cell", "") or ""),
                    ),
                )
            elif action in {"office.excel.write_cell", "office.spreadsheet.write_cell"}:
                payload = self._run(
                    "excel",
                    lambda app: _write_excel_cell(
                        app,
                        path,
                        str(parameters.get("sheet", "Sheet1") or "Sheet1"),
                        str(parameters.get("cell", "") or ""),
                        parameters.get("value"),
                    ),
                )
            elif action in {"office.powerpoint.read", "office.presentation.read"}:
                payload = self._run("powerpoint", lambda app: _read_powerpoint(app, path))
            elif action in {"office.powerpoint.add_text", "office.presentation.add_text"}:
                payload = self._run(
                    "powerpoint",
                    lambda app: _add_powerpoint_text(
                        app,
                        path,
                        str(parameters.get("text", parameters.get("body", "")) or ""),
                    ),
                )
            else:
                return self._failure(action, "office_capability_missing", target)
        except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as exc:
            return self._failure(action, str(exc), target)
        except Exception as exc:
            return self._failure(
                action,
                f"office_{exc.__class__.__name__.casefold()}",
                target,
            )
        payload = dict(payload or {})
        payload.setdefault("background_safe", True)
        payload.setdefault("foreground_required", False)
        payload.setdefault("control_attempts", 1)
        payload.setdefault("com_attempts", 1)
        payload.setdefault("readback_verified", False)
        return self._success(action, payload)

    def _run(self, kind: str, operation: Callable[[object], dict]) -> dict:
        app = None
        initialized = False
        try:
            try:
                import pythoncom

                pythoncom.CoInitialize()
                initialized = True
            except Exception:
                pass
            app = self._application_factory(kind)
            _set_background_mode(app, kind)
            return dict(operation(app) or {})
        finally:
            _quit_application(app)
            if initialized:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _success(self, action: str, payload: dict) -> ConnectorActionResult:
        return ConnectorActionResult(
            success=bool(payload.get("readback_verified")),
            connector_id=self.connector_id,
            action=action,
            action_key=f"{action}:{payload.get('path', payload.get('document_path', ''))}",
            payload=payload,
            error="" if payload.get("readback_verified") else "office_readback_not_verified",
        )

    def _failure(self, action: str, error: str, target: ConnectorTarget) -> ConnectorActionResult:
        return ConnectorActionResult(
            success=False,
            connector_id=self.connector_id,
            action=action or "unknown",
            action_key=f"{action}:{target.workspace_path}",
            payload={
                "control_attempts": 0,
                "com_attempts": 0,
                "background_safe": True,
                "foreground_required": False,
            },
            error=error,
        )


def _normalize_action(value: object) -> str:
    return str(value or "").strip().casefold()


def _intent_parameters(intent: object) -> dict[str, Any]:
    value = getattr(intent, "parameters", {})
    return dict(value) if isinstance(value, dict) else {}


def _target_app_kind(target: ConnectorTarget) -> str | None:
    process = str(target.process_name or "").strip().casefold()
    if process in _OFFICE_PROCESSES:
        return _OFFICE_PROCESSES[process]
    identity = target.identity_text().casefold()
    for kind, labels in _OFFICE_TITLES.items():
        if any(label in identity for label in labels):
            return kind
    suffix = Path(str(target.workspace_path or target.resource_url or "")).suffix.casefold()
    for kind in _OFFICE_TITLES:
        if suffix in _suffixes_for(kind):
            return kind
    return None


def _suffixes_for(kind: str) -> set[str]:
    return {
        "word": {".docx", ".docm", ".doc", ".dotx", ".dotm"},
        "excel": {".xlsx", ".xlsm", ".xls", ".xltx", ".xltm"},
        "powerpoint": {".pptx", ".pptm", ".ppt", ".potx", ".potm"},
    }.get(kind, set())


def _resolve_owned_path(target: ConnectorTarget, parameters: dict[str, Any]) -> Path:
    raw = str(
        parameters.get("path", parameters.get("document_path", ""))
        or target.workspace_path
        or ""
    ).strip()
    if not raw:
        raise ValueError("office_document_path_required")
    path = Path(raw).expanduser().resolve()
    root_raw = str(parameters.get("approved_root", "") or target.workspace_path or "").strip()
    if not root_raw:
        raise PermissionError("office_authorized_root_required")
    root = Path(root_raw).expanduser().resolve()
    if root.is_file():
        root = root.parent
    if not root.is_dir():
        raise NotADirectoryError("office_authorized_root_not_directory")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError("office_path_outside_root") from exc
    if path.exists() and not path.is_file():
        raise ValueError("office_document_not_file")
    if not path.exists() and path.parent != root and not path.parent.is_dir():
        raise NotADirectoryError("office_document_parent_not_directory")
    return path


def _inspect_path(target: ConnectorTarget, parameters: dict[str, Any], kind: str) -> dict:
    path = _resolve_owned_path(target, parameters)
    if not path.exists():
        return {
            "path": str(path),
            "app_kind": kind,
            "exists": False,
            "readback_verified": True,
            "control_attempts": 0,
            "com_attempts": 0,
        }
    identity = _identity(path, kind)
    return {
        **identity.to_dict(),
        "exists": True,
        "readback_verified": True,
        "control_attempts": 0,
        "com_attempts": 0,
    }


def _identity(path: Path, kind: str) -> OfficeDocumentIdentity:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return OfficeDocumentIdentity(
        path=str(path),
        app_kind=kind,
        suffix=path.suffix.casefold(),
        size=path.stat().st_size,
        sha256=digest.hexdigest(),
    )


def _read_document(app: object, kind: str, path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError("office_document_not_found")
    if kind != "word":
        if kind == "excel":
            return {"path": str(path), "readback_verified": True}
        return _read_powerpoint(app, path)
    document = None
    try:
        document = app.Documents.Open(
            FileName=str(path),
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        text = str(document.Content.Text or "")
        return {
            "path": str(path),
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "readback_verified": True,
        }
    finally:
        _close(document)


def _write_word(app: object, path: Path, body: str, *, append: bool) -> dict:
    if not body:
        raise ValueError("office_word_body_required")
    document = None
    try:
        if append:
            if not path.is_file():
                raise FileNotFoundError("office_document_not_found")
            document = app.Documents.Open(
                FileName=str(path),
                ReadOnly=False,
                AddToRecentFiles=False,
                Visible=False,
            )
            document.Content.InsertAfter(body)
            document.Save()
        else:
            document = app.Documents.Add()
            document.Content.Text = body
            document.SaveAs2(
                FileName=str(path),
                FileFormat=12 if path.suffix.casefold() != ".doc" else 0,
                AddToRecentFiles=False,
            )
        _close(document)
        document = None
        readback = _read_document(app, "word", path)
        readback["write_mode"] = "append" if append else "replace"
        readback["requested_body_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        readback["readback_verified"] = body in str(readback.get("text", ""))
        return readback
    finally:
        _close(document)


def _excel_workbook(app: object, path: Path, *, read_only: bool):
    if not path.is_file():
        raise FileNotFoundError("office_workbook_not_found")
    return app.Workbooks.Open(
        FileName=str(path),
        ReadOnly=read_only,
        UpdateLinks=0,
        AddToMru=False,
    )


def _excel_sheet(workbook: object, name: str):
    sheet_name = str(name or "").strip()
    if not sheet_name:
        raise ValueError("office_excel_sheet_required")
    return workbook.Worksheets.Item(sheet_name)


def _excel_cell(sheet: object, address: str):
    cell = str(address or "").strip()
    if not cell:
        raise ValueError("office_excel_cell_required")
    return sheet.Range(cell)


def _read_excel_cell(app: object, path: Path, sheet: str, cell: str) -> dict:
    workbook = _excel_workbook(app, path, read_only=True)
    try:
        value = _excel_cell(_excel_sheet(workbook, sheet), cell).Value
        return {
            "path": str(path),
            "sheet": sheet,
            "cell": cell,
            "value": value,
            "readback_verified": True,
        }
    finally:
        _close(workbook)


def _write_excel_cell(app: object, path: Path, sheet: str, cell: str, value: object) -> dict:
    workbook = _excel_workbook(app, path, read_only=False)
    try:
        target = _excel_cell(_excel_sheet(workbook, sheet), cell)
        target.Value = value
        workbook.Save()
        observed = target.Value
        return {
            "path": str(path),
            "sheet": sheet,
            "cell": cell,
            "value": observed,
            "requested_value": value,
            "readback_verified": observed == value,
        }
    finally:
        _close(workbook)


def _read_powerpoint(app: object, path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError("office_presentation_not_found")
    presentation = None
    try:
        presentation = app.Presentations.Open(
            FileName=str(path),
            ReadOnly=True,
            WithWindow=False,
        )
        texts: list[str] = []
        for index in range(1, int(presentation.Slides.Count) + 1):
            slide = presentation.Slides.Item(index)
            for shape_index in range(1, int(slide.Shapes.Count) + 1):
                shape = slide.Shapes.Item(shape_index)
                try:
                    if shape.HasTextFrame and shape.TextFrame.HasText:
                        texts.append(str(shape.TextFrame.TextRange.Text or ""))
                except Exception:
                    continue
        text = "\n".join(item for item in texts if item)
        return {"path": str(path), "text": text, "slide_count": int(presentation.Slides.Count), "readback_verified": True}
    finally:
        _close(presentation)


def _add_powerpoint_text(app: object, path: Path, text: str) -> dict:
    if not text:
        raise ValueError("office_powerpoint_text_required")
    presentation = None
    if path.is_file():
        presentation = app.Presentations.Open(
            FileName=str(path), ReadOnly=False, WithWindow=False
        )
    else:
        presentation = app.Presentations.Add(False)
        presentation.SaveAs(str(path))
    try:
        slide = presentation.Slides.Add(int(presentation.Slides.Count) + 1, 12)
        slide.Shapes.Title.TextFrame.TextRange.Text = text
        presentation.Save()
        observed = _read_powerpoint(app, path)
        observed["readback_verified"] = text in observed.get("text", "")
        return observed
    finally:
        _close(presentation)


def _create_application(kind: str) -> object:
    try:
        import win32com.client
    except Exception as exc:
        raise RuntimeError(f"pywin32_not_available: {exc}") from exc
    progids = {
        "word": "Word.Application",
        "excel": "Excel.Application",
        "powerpoint": "PowerPoint.Application",
    }
    try:
        return win32com.client.DispatchEx(progids[kind])
    except Exception as exc:
        raise RuntimeError(f"office_com_dispatch_failed:{kind}:{exc}") from exc


def _set_background_mode(app: object, kind: str) -> None:
    for name, value in (("Visible", False), ("DisplayAlerts", 0)):
        try:
            setattr(app, name, value)
        except Exception:
            pass
    if kind == "excel":
        try:
            app.ScreenUpdating = False
        except Exception:
            pass


def _close(value: object | None) -> None:
    if value is None:
        return
    try:
        value.Close(SaveChanges=False)
    except Exception:
        try:
            value.Close()
        except Exception:
            pass


def _quit_application(app: object | None) -> None:
    if app is None:
        return
    try:
        app.Quit()
    except Exception:
        pass


__all__ = ["OfficeDocumentIdentity", "OfficeSessionConnector"]
