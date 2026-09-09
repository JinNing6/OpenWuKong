# -*- coding: utf-8 -*-
"""Read-only Cursor local transcript marker scanner."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse


@dataclasses.dataclass(frozen=True)
class CursorTranscriptReadbackReport:
    user_data_root: str
    workspace_path: str
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    required_response_role: str = "assistant"
    workspace_storage_dir: str = ""
    workspace_state_db: str = ""
    global_state_db: str = ""
    selected_composer_ids: tuple[str, ...] = ()
    scanned_composer_ids: tuple[str, ...] = ()
    scanned_keys: tuple[str, ...] = ()
    required_markers_found: tuple[str, ...] = ()
    required_markers_found_anywhere: tuple[str, ...] = ()
    missing_required_markers: tuple[str, ...] = ()
    forbidden_markers_found: tuple[str, ...] = ()
    response_marker_locations: tuple[dict[str, str], ...] = ()
    non_response_marker_locations: tuple[dict[str, str], ...] = ()
    readback_text: str = ""
    decision: str = ""
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-transcript-readback"

    @property
    def safety_mode(self) -> str:
        return "read_only_local_storage"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return self.decision == "cursor_transcript_readback_accepted"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "user_data_root": self.user_data_root,
            "workspace_path": self.workspace_path,
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "required_response_role": self.required_response_role,
            "workspace_storage_dir": self.workspace_storage_dir,
            "workspace_state_db": self.workspace_state_db,
            "global_state_db": self.global_state_db,
            "selected_composer_ids": list(self.selected_composer_ids),
            "scanned_composer_ids": list(self.scanned_composer_ids),
            "scanned_keys": list(self.scanned_keys),
            "required_markers_found": list(self.required_markers_found),
            "required_markers_found_anywhere": list(self.required_markers_found_anywhere),
            "missing_required_markers": list(self.missing_required_markers),
            "forbidden_markers_found": list(self.forbidden_markers_found),
            "response_marker_locations": [dict(item) for item in self.response_marker_locations],
            "non_response_marker_locations": [
                dict(item) for item in self.non_response_marker_locations
            ],
            "readback_text": self.readback_text,
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class CursorComposerStateDiscoveryReport:
    user_data_root: str
    workspace_path: str
    required_markers: tuple[str, ...] = ()
    workspace_storage_dir: str = ""
    workspace_state_db: str = ""
    global_state_db: str = ""
    selected_composer_ids: tuple[str, ...] = ()
    scanned_composer_ids: tuple[str, ...] = ()
    scanned_keys: tuple[str, ...] = ()
    key_family_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    marker_locations: tuple[dict[str, str], ...] = ()
    hook_candidates: tuple[str, ...] = ()
    decision: str = ""
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-composer-state-discovery"

    @property
    def safety_mode(self) -> str:
        return "read_only_local_storage"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return self.decision == "cursor_composer_state_surfaces_found"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "user_data_root": self.user_data_root,
            "workspace_path": self.workspace_path,
            "required_markers": list(self.required_markers),
            "workspace_storage_dir": self.workspace_storage_dir,
            "workspace_state_db": self.workspace_state_db,
            "global_state_db": self.global_state_db,
            "selected_composer_ids": list(self.selected_composer_ids),
            "scanned_composer_ids": list(self.scanned_composer_ids),
            "scanned_keys": list(self.scanned_keys),
            "key_family_counts": dict(self.key_family_counts),
            "marker_locations": [dict(item) for item in self.marker_locations],
            "hook_candidates": list(self.hook_candidates),
            "error": self.error,
        }


def run_cursor_transcript_readback(
    *,
    user_data_root: str | Path | None = None,
    workspace_path: str | Path = "",
    required_markers: Iterable[str] = (),
    forbidden_markers: Iterable[str] = (),
    extra_composer_ids: Iterable[str] = (),
    required_response_role: str = "assistant",
    max_blob_rows: int = 250,
) -> CursorTranscriptReadbackReport:
    root = Path(user_data_root) if user_data_root else default_cursor_user_data_root()
    requested_workspace = _normalize_local_path(workspace_path)
    required = _clean_markers(required_markers)
    forbidden = _clean_markers(forbidden_markers)
    required_role = _normalize_role(required_response_role)
    base = {
        "user_data_root": str(root),
        "workspace_path": str(requested_workspace),
        "required_markers": required,
        "forbidden_markers": forbidden,
        "required_response_role": required_role,
    }
    if not root.exists():
        return CursorTranscriptReadbackReport(
            **base,
            decision="cursor_user_data_root_missing",
        )
    workspace_storage_dir = find_workspace_storage_dir(root, requested_workspace)
    if not workspace_storage_dir:
        return CursorTranscriptReadbackReport(
            **base,
            decision="cursor_workspace_storage_not_found",
        )
    workspace_db = workspace_storage_dir / "state.vscdb"
    if not workspace_db.exists():
        return CursorTranscriptReadbackReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            decision="cursor_workspace_state_db_missing",
        )
    try:
        composer_ids = read_selected_composer_ids(workspace_db)
    except Exception as exc:
        return CursorTranscriptReadbackReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            decision="cursor_workspace_state_db_unreadable",
            error=str(exc) or exc.__class__.__name__,
        )
    if not composer_ids:
        extra_ids = _clean_markers(extra_composer_ids)
        if not extra_ids:
            return CursorTranscriptReadbackReport(
                **base,
                workspace_storage_dir=str(workspace_storage_dir),
                workspace_state_db=str(workspace_db),
                decision="cursor_selected_composer_missing",
            )
    else:
        extra_ids = _clean_markers(extra_composer_ids)
    scanned_composer_ids = tuple(dict.fromkeys((*composer_ids, *extra_ids)))
    global_db = root / "globalStorage" / "state.vscdb"
    if not global_db.exists():
        return CursorTranscriptReadbackReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            global_state_db=str(global_db),
            selected_composer_ids=composer_ids,
            scanned_composer_ids=scanned_composer_ids,
            decision="cursor_global_state_db_missing",
        )
    try:
        rows = read_cursor_disk_rows(
            global_db,
            composer_ids=scanned_composer_ids,
            required_markers=required,
            max_blob_rows=max_blob_rows,
        )
    except Exception as exc:
        return CursorTranscriptReadbackReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            global_state_db=str(global_db),
            selected_composer_ids=composer_ids,
            scanned_composer_ids=scanned_composer_ids,
            decision="cursor_global_state_db_unreadable",
            error=str(exc) or exc.__class__.__name__,
        )
    scanned_keys = tuple(key for key, _ in rows)
    marker_hits = _find_marker_hits(rows, tuple(required + forbidden))
    required_found_anywhere = tuple(
        marker for marker in required if any(hit["marker"] == marker for hit in marker_hits)
    )
    response_hits = _filter_marker_hits_by_role(marker_hits, required_role)
    response_required_hits = tuple(
        hit for hit in response_hits if str(hit.get("marker", "")) in required
    )
    required_found = tuple(
        marker for marker in required if any(hit["marker"] == marker for hit in response_required_hits)
    )
    missing_required = tuple(marker for marker in required if marker not in required_found)
    forbidden_hits = tuple(hit for hit in marker_hits if str(hit.get("marker", "")) in forbidden)
    forbidden_found = tuple(
        marker for marker in forbidden if any(hit["marker"] == marker for hit in forbidden_hits)
    )
    response_locations = _marker_hit_locations(response_required_hits)
    non_response_locations = _marker_hit_locations(
        hit
        for hit in marker_hits
        if str(hit.get("marker", "")) in required
        and hit not in response_required_hits
    )
    readback_text = _marker_hit_snippets(
        response_required_hits if response_required_hits else marker_hits
    )
    if forbidden_found:
        decision = "cursor_transcript_readback_forbidden_marker"
    elif required_role and missing_required and required_found_anywhere:
        decision = "cursor_transcript_readback_non_response_marker_only"
    elif missing_required:
        decision = "cursor_transcript_readback_pending"
    else:
        decision = "cursor_transcript_readback_accepted"
    return CursorTranscriptReadbackReport(
        **base,
        workspace_storage_dir=str(workspace_storage_dir),
        workspace_state_db=str(workspace_db),
        global_state_db=str(global_db),
        selected_composer_ids=composer_ids,
        scanned_composer_ids=scanned_composer_ids,
        scanned_keys=scanned_keys,
        required_markers_found=required_found,
        required_markers_found_anywhere=required_found_anywhere,
        missing_required_markers=missing_required,
        forbidden_markers_found=forbidden_found,
        response_marker_locations=response_locations,
        non_response_marker_locations=non_response_locations,
        readback_text=readback_text,
        decision=decision,
    )


def run_cursor_composer_state_discovery(
    *,
    user_data_root: str | Path | None = None,
    workspace_path: str | Path = "",
    required_markers: Iterable[str] = (),
    extra_composer_ids: Iterable[str] = (),
    max_blob_rows: int = 250,
) -> CursorComposerStateDiscoveryReport:
    root = Path(user_data_root) if user_data_root else default_cursor_user_data_root()
    requested_workspace = _normalize_local_path(workspace_path)
    required = _clean_markers(required_markers)
    base = {
        "user_data_root": str(root),
        "workspace_path": str(requested_workspace),
        "required_markers": required,
    }
    if not root.exists():
        return CursorComposerStateDiscoveryReport(
            **base,
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_user_data_root_missing",
        )
    workspace_storage_dir = find_workspace_storage_dir(root, requested_workspace)
    if not workspace_storage_dir:
        return CursorComposerStateDiscoveryReport(
            **base,
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_workspace_storage_not_found",
        )
    workspace_db = workspace_storage_dir / "state.vscdb"
    if not workspace_db.exists():
        return CursorComposerStateDiscoveryReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_workspace_state_db_missing",
        )
    try:
        composer_ids = read_selected_composer_ids(workspace_db)
    except Exception as exc:
        return CursorComposerStateDiscoveryReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_workspace_state_db_unreadable",
            error=str(exc) or exc.__class__.__name__,
        )
    if not composer_ids:
        extra_ids = _clean_markers(extra_composer_ids)
        if not extra_ids:
            return CursorComposerStateDiscoveryReport(
                **base,
                workspace_storage_dir=str(workspace_storage_dir),
                workspace_state_db=str(workspace_db),
                key_family_counts=_empty_cursor_family_counts(),
                decision="cursor_selected_composer_missing",
            )
    else:
        extra_ids = _clean_markers(extra_composer_ids)
    scanned_composer_ids = tuple(dict.fromkeys((*composer_ids, *extra_ids)))
    global_db = root / "globalStorage" / "state.vscdb"
    if not global_db.exists():
        return CursorComposerStateDiscoveryReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            global_state_db=str(global_db),
            selected_composer_ids=composer_ids,
            scanned_composer_ids=scanned_composer_ids,
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_global_state_db_missing",
        )
    try:
        rows = read_cursor_disk_rows(
            global_db,
            composer_ids=scanned_composer_ids,
            required_markers=required,
            max_blob_rows=max_blob_rows,
        )
    except Exception as exc:
        return CursorComposerStateDiscoveryReport(
            **base,
            workspace_storage_dir=str(workspace_storage_dir),
            workspace_state_db=str(workspace_db),
            global_state_db=str(global_db),
            selected_composer_ids=composer_ids,
            scanned_composer_ids=scanned_composer_ids,
            key_family_counts=_empty_cursor_family_counts(),
            decision="cursor_global_state_db_unreadable",
            error=str(exc) or exc.__class__.__name__,
        )
    counts = _count_cursor_key_families(rows)
    locations = _find_marker_locations(rows, required)
    hook_candidates = _build_cursor_hook_candidates(counts, locations)
    has_composer_rows = any(
        counts[family] > 0
        for family in (
            "composerData",
            "bubbleId",
            "messageRequestContext",
            "checkpointId",
        )
    )
    decision = (
        "cursor_composer_state_surfaces_found"
        if has_composer_rows
        else "cursor_composer_state_rows_missing"
    )
    return CursorComposerStateDiscoveryReport(
        **base,
        workspace_storage_dir=str(workspace_storage_dir),
        workspace_state_db=str(workspace_db),
        global_state_db=str(global_db),
        selected_composer_ids=composer_ids,
        scanned_composer_ids=scanned_composer_ids,
        scanned_keys=tuple(key for key, _ in rows),
        key_family_counts=counts,
        marker_locations=locations,
        hook_candidates=hook_candidates if has_composer_rows else (),
        decision=decision,
    )


def default_cursor_user_data_root() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "Cursor" / "User"
    return Path.home() / "AppData" / "Roaming" / "Cursor" / "User"


def find_workspace_storage_dir(user_data_root: Path, workspace_path: Path) -> Path | None:
    workspace_root = user_data_root / "workspaceStorage"
    if not workspace_root.exists():
        return None
    requested = _canonical_path(workspace_path)
    for workspace_json in workspace_root.glob("*/workspace.json"):
        try:
            payload = json.loads(workspace_json.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        folder = str(payload.get("folder", "") or "")
        folder_path = _workspace_folder_uri_to_path(folder)
        if folder_path and _canonical_path(folder_path) == requested:
            return workspace_json.parent
    return None


def read_selected_composer_ids(workspace_state_db: Path) -> tuple[str, ...]:
    value = ""
    conn = _connect_read_only(workspace_state_db)
    try:
        cursor = conn.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("composer.composerData",),
        )
        row = cursor.fetchone()
        if row:
            value = str(row[0] or "")
    finally:
        conn.close()
    if not value:
        return ()
    payload = json.loads(value)
    found: list[str] = []
    _append_composer_ids(found, payload.get("selectedComposerIds"))
    _append_composer_ids(found, payload.get("lastFocusedComposerIds"))
    _append_composer_ids(found, payload.get("lastFocusedComposerId"))
    return tuple(dict.fromkeys(item for item in found if item))


def read_cursor_disk_rows(
    global_state_db: Path,
    *,
    composer_ids: Iterable[str],
    required_markers: Iterable[str],
    max_blob_rows: int,
) -> tuple[tuple[str, str], ...]:
    ids = tuple(dict.fromkeys(str(item) for item in composer_ids if str(item)))
    rows: list[tuple[str, str]] = []
    conn = _connect_read_only(global_state_db)
    try:
        for composer_id in ids:
            patterns = (
                f"composerData:{composer_id}",
                f"bubbleId:{composer_id}:%",
                f"messageRequestContext:{composer_id}:%",
                f"checkpointId:{composer_id}:%",
            )
            for pattern in patterns:
                if pattern.endswith("%"):
                    cursor = conn.execute(
                        "SELECT key, value FROM cursorDiskKV WHERE key LIKE ? ORDER BY key",
                        (pattern,),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT key, value FROM cursorDiskKV WHERE key = ?",
                        (pattern,),
                    )
                rows.extend((str(key), str(value or "")) for key, value in cursor.fetchall())
        for marker in _clean_markers(required_markers):
            cursor = conn.execute(
                """
                SELECT key, value FROM cursorDiskKV
                WHERE (
                    key LIKE 'bubbleId:%'
                    OR key LIKE 'messageRequestContext:%'
                    OR key LIKE 'composerData:%'
                    OR key LIKE 'agentKv:blob:%'
                )
                AND value LIKE ?
                ORDER BY key
                LIMIT ?
                """,
                (f"%{marker}%", int(max_blob_rows or 0)),
            )
            rows.extend((str(key), str(value or "")) for key, value in cursor.fetchall())
    finally:
        conn.close()
    deduped: dict[str, str] = {}
    for key, value in rows:
        deduped[key] = value
    return tuple(deduped.items())


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read Cursor local transcript storage without window input."
    )
    parser.add_argument("--user-data-root", default="", help="Cursor User data root.")
    parser.add_argument("--workspace-path", required=True, help="Workspace path to bind.")
    parser.add_argument("--required-marker", action="append", default=[])
    parser.add_argument("--forbidden-marker", action="append", default=[])
    parser.add_argument("--composer-id", action="append", default=[], help="Extra composer id to scan.")
    parser.add_argument(
        "--required-response-role",
        default="assistant",
        help="Role required for acceptance markers; use empty value to allow any role.",
    )
    parser.add_argument(
        "--allow-any-role",
        action="store_true",
        help="Accept required markers from any role. Intended for discovery only.",
    )
    parser.add_argument("--discover-state", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    response_role = "" if args.allow_any_role else args.required_response_role
    if args.discover_state:
        report = run_cursor_composer_state_discovery(
            user_data_root=args.user_data_root or None,
            workspace_path=args.workspace_path,
            required_markers=tuple(args.required_marker or ()),
            extra_composer_ids=tuple(args.composer_id or ()),
        )
    else:
        report = run_cursor_transcript_readback(
            user_data_root=args.user_data_root or None,
            workspace_path=args.workspace_path,
            required_markers=tuple(args.required_marker or ()),
            forbidden_markers=tuple(args.forbidden_marker or ()),
            extra_composer_ids=tuple(args.composer_id or ()),
            required_response_role=response_role,
        )
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{payload['mode']}: decision={payload['decision']} ok={payload['ok']} ")
    return 0 if report.ok else 1


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, timeout=0.5, uri=True)


def _clean_markers(markers: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(marker) for marker in markers if str(marker)))


def _append_composer_ids(found: list[str], value: object) -> None:
    if isinstance(value, str):
        found.append(value)
        return
    if isinstance(value, dict):
        for item in value.values():
            _append_composer_ids(found, item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _append_composer_ids(found, item)


def _workspace_folder_uri_to_path(value: str) -> Path | None:
    if not value:
        return None
    if value.startswith("file:"):
        parsed = urlparse(value)
        path = unquote(parsed.path or "")
        if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return Path(path)
    return Path(value)


def _normalize_local_path(value: str | Path) -> Path:
    if isinstance(value, Path):
        return value
    return _workspace_folder_uri_to_path(str(value or "")) or Path(str(value or ""))


def _canonical_path(path: Path) -> str:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path.absolute()
    return os.path.normcase(os.path.normpath(str(resolved)))


def _extract_searchable_text(value: str) -> str:
    try:
        payload = json.loads(value)
    except Exception:
        return str(value or "")
    pieces: list[str] = []
    _collect_text_fields(payload, pieces)
    return "\n".join(piece for piece in pieces if piece)


def _find_marker_hits(
    rows: Iterable[tuple[str, str]],
    markers: tuple[str, ...],
) -> tuple[dict[str, str], ...]:
    hits: list[dict[str, str]] = []
    clean_markers = tuple(marker for marker in markers if marker)
    if not clean_markers:
        return ()
    for key, value in rows:
        try:
            payload = json.loads(value)
        except Exception:
            raw = str(value or "")
            _append_text_marker_hits(
                hits,
                key=key,
                path="$",
                text=raw,
                role="ambiguous",
                markers=clean_markers,
            )
            continue
        _collect_marker_hits(
            payload,
            hits,
            key=key,
            path="$",
            ancestors=(),
            markers=clean_markers,
        )
    return tuple(hits)


def _collect_marker_hits(
    value: object,
    hits: list[dict[str, str]],
    *,
    key: str,
    path: str,
    ancestors: tuple[dict, ...],
    markers: tuple[str, ...],
) -> None:
    if isinstance(value, dict):
        next_ancestors = (*ancestors, value)
        for field, item in value.items():
            _collect_marker_hits(
                item,
                hits,
                key=key,
                path=f"{path}.{field}",
                ancestors=next_ancestors,
                markers=markers,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_marker_hits(
                item,
                hits,
                key=key,
                path=f"{path}[{index}]",
                ancestors=ancestors,
                markers=markers,
            )
        return
    if isinstance(value, str):
        role = _infer_marker_role(key, ancestors)
        _append_text_marker_hits(
            hits,
            key=key,
            path=path,
            text=value,
            role=role,
            markers=markers,
        )


def _append_text_marker_hits(
    hits: list[dict[str, str]],
    *,
    key: str,
    path: str,
    text: str,
    role: str,
    markers: tuple[str, ...],
) -> None:
    if not text:
        return
    for marker in markers:
        index = text.find(marker)
        if index < 0:
            continue
        hits.append(
            {
                "family": _cursor_key_family(key),
                "key": key,
                "path": path,
                "marker": marker,
                "role": role or "ambiguous",
                "snippet": _snippet_around(text, index, len(marker)),
            }
        )


def _infer_marker_role(key: str, ancestors: tuple[dict, ...]) -> str:
    for item in reversed(ancestors):
        normalized = _role_from_explicit_fields(item)
        if normalized:
            return normalized
        if key.startswith("bubbleId:") and _looks_like_cursor_bubble(item):
            bubble_role = _role_from_cursor_bubble_type(item.get("type"))
            if bubble_role:
                return bubble_role
    if key.startswith("composerData:"):
        return "user"
    if key.startswith("messageRequestContext:"):
        return "user"
    return "ambiguous"


def _role_from_explicit_fields(item: dict) -> str:
    for key in ("isAssistant", "isAi", "isAgent", "assistant", "ai"):
        if item.get(key) is True:
            return "assistant"
    for key in ("isUser", "isHuman", "human", "user"):
        if item.get(key) is True:
            return "user"
    for key in (
        "role",
        "sender",
        "source",
        "author",
        "speaker",
        "messageRole",
        "message_role",
        "from",
    ):
        if key in item:
            normalized = _normalize_role(item.get(key))
            if normalized:
                return normalized
    return ""


def _looks_like_cursor_bubble(item: dict) -> bool:
    if "type" not in item:
        return False
    return any(
        isinstance(item.get(field), str)
        for field in ("text", "richText", "message", "content")
    )


def _role_from_cursor_bubble_type(value: object) -> str:
    text = str(value)
    if text == "1":
        return "user"
    if text == "2":
        return "assistant"
    return ""


def _normalize_role(value: object) -> str:
    role = str(value or "").strip().lower()
    if not role:
        return ""
    if role in {"assistant", "agent", "ai", "bot", "model", "response"}:
        return "assistant"
    if role in {"user", "human", "request", "prompt", "customer"}:
        return "user"
    return role


def _filter_marker_hits_by_role(
    hits: tuple[dict[str, str], ...],
    role: str,
) -> tuple[dict[str, str], ...]:
    normalized = _normalize_role(role)
    if not normalized:
        return tuple(hits)
    return tuple(hit for hit in hits if _normalize_role(hit.get("role", "")) == normalized)


def _marker_hit_locations(hits: Iterable[dict[str, str]]) -> tuple[dict[str, str], ...]:
    locations: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for hit in hits:
        item = {
            "family": str(hit.get("family", "")),
            "key": str(hit.get("key", "")),
            "path": str(hit.get("path", "")),
            "marker": str(hit.get("marker", "")),
            "role": str(hit.get("role", "")),
        }
        identity = (item["key"], item["path"], item["marker"], item["role"])
        if identity in seen:
            continue
        seen.add(identity)
        locations.append(item)
    return tuple(locations)


def _marker_hit_snippets(hits: Iterable[dict[str, str]]) -> str:
    lines: list[str] = []
    for hit in hits:
        snippet = str(hit.get("snippet", "")).strip()
        if not snippet:
            continue
        lines.append(
            "role={role} family={family} key={key} path={path}\n{snippet}".format(
                role=str(hit.get("role", "")),
                family=str(hit.get("family", "")),
                key=str(hit.get("key", "")),
                path=str(hit.get("path", "")),
                snippet=snippet,
            )
        )
    return "\n---\n".join(dict.fromkeys(lines))


def _collect_text_fields(value: object, pieces: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"text", "richText", "message", "content"} and isinstance(item, str):
                pieces.append(item)
            else:
                _collect_text_fields(item, pieces)
    elif isinstance(value, list):
        for item in value:
            _collect_text_fields(item, pieces)
    elif isinstance(value, str):
        pieces.append(value)


def _marker_snippets(text: str, markers: tuple[str, ...]) -> str:
    if not markers:
        return ""
    lines: list[str] = []
    for marker in markers:
        index = text.find(marker)
        if index < 0:
            continue
        start = max(0, index - 160)
        end = min(len(text), index + len(marker) + 160)
        lines.append(text[start:end].strip())
    return "\n---\n".join(dict.fromkeys(lines))


def _snippet_around(text: str, index: int, marker_len: int) -> str:
    start = max(0, index - 160)
    end = min(len(text), index + marker_len + 160)
    return text[start:end].strip()


def _empty_cursor_family_counts() -> dict[str, int]:
    return {
        "composerData": 0,
        "bubbleId": 0,
        "messageRequestContext": 0,
        "checkpointId": 0,
        "agentKv_blob_matching_marker": 0,
        "unknown": 0,
    }


def _count_cursor_key_families(rows: Iterable[tuple[str, str]]) -> dict[str, int]:
    counts = _empty_cursor_family_counts()
    for key, _ in rows:
        counts[_cursor_key_family(key)] += 1
    return counts


def _find_marker_locations(
    rows: Iterable[tuple[str, str]],
    markers: tuple[str, ...],
) -> tuple[dict[str, str], ...]:
    locations: list[dict[str, str]] = []
    for key, value in rows:
        text = _extract_searchable_text(value)
        for marker in markers:
            if marker in text:
                locations.append(
                    {
                        "family": _cursor_key_family(key),
                        "key": key,
                        "marker": marker,
                    }
                )
    return tuple(locations)


def _build_cursor_hook_candidates(
    counts: dict[str, int],
    marker_locations: tuple[dict[str, str], ...],
) -> tuple[str, ...]:
    candidates: list[str] = []
    if counts.get("composerData", 0) > 0:
        candidates.append("cursor_composer_data_store")
    if counts.get("messageRequestContext", 0) > 0:
        candidates.append("cursor_message_request_context_store")
    if counts.get("bubbleId", 0) > 0:
        candidates.append("cursor_bubble_transcript_store")
    if marker_locations:
        candidates.append("cursor_extension_native_hook")
    return tuple(dict.fromkeys(candidates))


def _cursor_key_family(key: str) -> str:
    if key.startswith("composerData:"):
        return "composerData"
    if key.startswith("bubbleId:"):
        return "bubbleId"
    if key.startswith("messageRequestContext:"):
        return "messageRequestContext"
    if key.startswith("checkpointId:"):
        return "checkpointId"
    if key.startswith("agentKv:blob:"):
        return "agentKv_blob_matching_marker"
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
