# -*- coding: utf-8 -*-
"""Read-only Cursor live composer state probe through the IDE bridge."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


SELECTED_COMPOSER_COMMAND = "composer.getOrderedSelectedComposerIds"
COMPOSER_HANDLE_COMMAND = "composer.getComposerHandleById"
ISOLATED_READ_PROFILE = "isolated_cursor_read_probe"


@dataclasses.dataclass(frozen=True)
class CursorLiveComposerStateReport:
    bridge_url: str
    workspace_path: str
    project_name: str = ""
    selected_composer_ids: tuple[str, ...] = ()
    composer_ids: tuple[str, ...] = ()
    composers: tuple[dict, ...] = ()
    state_status: str = ""
    include_handles: bool = False
    handle_read_allowed: bool = False
    handle_read_policy: str = ""
    pending_commands: tuple[dict, ...] = ()
    command_errors: tuple[dict, ...] = ()
    readonly_command_attempts: int = 0
    decision: str = ""
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-live-composer-state"

    @property
    def safety_mode(self) -> str:
        return "read_only_ide_bridge_commands"

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
        return self.decision in {
            "cursor_live_composer_state_ready",
            "cursor_live_composer_selected_ids_ready",
        }

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
            "readonly_command_attempts": self.readonly_command_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "project_name": self.project_name,
            "selected_composer_ids": list(self.selected_composer_ids),
            "composer_ids": list(self.composer_ids),
            "composers": [dict(item) for item in self.composers],
            "state_status": self.state_status,
            "include_handles": self.include_handles,
            "handle_read_allowed": self.handle_read_allowed,
            "handle_read_policy": self.handle_read_policy,
            "pending_commands": [dict(item) for item in self.pending_commands],
            "command_errors": [dict(item) for item in self.command_errors],
            "error": self.error,
        }


def probe_cursor_live_composer_state(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    project_name: str = "",
    composer_ids: Iterable[str] = (),
    bridge_client: IDEExtensionBridgeClient | None = None,
    request_timeout: float = 5.0,
    max_composers: int = 8,
    include_handles: bool = False,
    safety_profile: str = "",
) -> CursorLiveComposerStateReport:
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    workspace = str(workspace_path or "")
    target = ConnectorTarget(
        project_name=project_name or Path(workspace).name,
        workspace_path=workspace,
        workspace_hint=Path(workspace).name if workspace else "",
        ide_bridge_url=bridge_url,
    )
    attempts = 0
    semantic_reader = getattr(client, "cursor_composer_state", None)
    if callable(semantic_reader):
        try:
            response = semantic_reader(
                bridge_url,
                target,
                composer_ids=list(_clean_strings(composer_ids)),
                max_composers=max_composers,
                include_handles=include_handles,
                safety_profile=safety_profile,
            )
            attempts += 1
        except Exception as exc:
            return CursorLiveComposerStateReport(
                bridge_url=bridge_url,
                workspace_path=workspace,
                project_name=target.project_name,
                readonly_command_attempts=attempts + 1,
                decision="cursor_live_composer_semantic_endpoint_unavailable",
                error=str(exc) or exc.__class__.__name__,
            )
        if not bool(response.get("ok", False)):
            return CursorLiveComposerStateReport(
                bridge_url=bridge_url,
                workspace_path=workspace,
                project_name=target.project_name,
                state_status=str(response.get("state_status", "") or ""),
                include_handles=bool(response.get("include_handles", False)),
                handle_read_allowed=bool(response.get("handle_read_allowed", False)),
                handle_read_policy=str(response.get("handle_read_policy", "") or ""),
                selected_composer_ids=_clean_strings(response.get("selected_composer_ids", ())),
                composer_ids=_clean_strings(response.get("composer_ids", ())),
                pending_commands=_clean_dicts(response.get("pending_commands", ())),
                command_errors=_clean_dicts(response.get("command_errors", ())),
                readonly_command_attempts=attempts,
                decision="cursor_live_composer_semantic_endpoint_unavailable",
                error=str(response.get("error", "cursor_composer_state_failed")),
            )
        semantic_composers = tuple(
            dict(item) for item in response.get("composers", []) if isinstance(item, dict)
        )
        state_status = str(response.get("state_status", "") or "")
        pending_commands = _clean_dicts(response.get("pending_commands", ()))
        command_errors = _clean_dicts(response.get("command_errors", ()))
        if state_status == "pending" or pending_commands:
            decision = "cursor_live_composer_state_pending"
        elif semantic_composers:
            decision = "cursor_live_composer_state_ready"
        elif state_status == "selected_only":
            decision = "cursor_live_composer_selected_ids_ready"
        else:
            decision = "cursor_live_composer_state_missing"
        return CursorLiveComposerStateReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            selected_composer_ids=_clean_strings(response.get("selected_composer_ids", ())),
            composer_ids=_clean_strings(response.get("composer_ids", ())),
            composers=semantic_composers,
            state_status=state_status,
            include_handles=bool(response.get("include_handles", False)),
            handle_read_allowed=bool(response.get("handle_read_allowed", False)),
            handle_read_policy=str(response.get("handle_read_policy", "") or ""),
            pending_commands=pending_commands,
            command_errors=command_errors,
            readonly_command_attempts=attempts,
            decision=decision,
            error="",
        )

    try:
        selected_response = client.execute_command(
            bridge_url,
            target,
            SELECTED_COMPOSER_COMMAND,
            [],
        )
        attempts += 1
    except Exception as exc:
        return CursorLiveComposerStateReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            readonly_command_attempts=attempts + 1,
            decision="cursor_live_composer_selected_ids_unavailable",
            error=str(exc) or exc.__class__.__name__,
        )
    if not bool(selected_response.get("ok", False)):
        return CursorLiveComposerStateReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            readonly_command_attempts=attempts,
            decision="cursor_live_composer_selected_ids_unavailable",
            error=str(selected_response.get("error", "selected_composer_command_failed")),
        )

    selected_ids = _clean_strings(selected_response.get("result", []))
    ids = tuple(_dedupe((*selected_ids, *_clean_strings(composer_ids))))
    if not ids:
        return CursorLiveComposerStateReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            selected_composer_ids=selected_ids,
            readonly_command_attempts=attempts,
            decision="cursor_live_composer_ids_missing",
        )

    if not include_handles or safety_profile != ISOLATED_READ_PROFILE:
        return CursorLiveComposerStateReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            project_name=target.project_name,
            selected_composer_ids=selected_ids,
            composer_ids=ids,
            state_status="selected_only",
            include_handles=include_handles,
            handle_read_allowed=False,
            handle_read_policy="isolated_cursor_read_probe_required",
            readonly_command_attempts=attempts,
            decision="cursor_live_composer_selected_ids_ready",
        )

    composers: list[dict] = []
    errors: list[str] = []
    for composer_id in ids[: max(1, int(max_composers or 1))]:
        try:
            response = client.execute_command(
                bridge_url,
                target,
                COMPOSER_HANDLE_COMMAND,
                [composer_id],
                safety_profile=ISOLATED_READ_PROFILE,
            )
            attempts += 1
        except Exception as exc:
            errors.append(f"{composer_id}: {str(exc) or exc.__class__.__name__}")
            continue
        if not bool(response.get("ok", False)):
            errors.append(f"{composer_id}: {response.get('error', 'composer_handle_failed')}")
            continue
        composers.append(summarize_cursor_composer_handle(response.get("result"), composer_id))

    decision = "cursor_live_composer_state_ready" if composers else "cursor_live_composer_state_missing"
    return CursorLiveComposerStateReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        project_name=target.project_name,
        selected_composer_ids=selected_ids,
        composer_ids=ids,
        composers=tuple(composers),
        state_status="ready" if composers else "missing",
        include_handles=include_handles,
        handle_read_allowed=safety_profile == ISOLATED_READ_PROFILE,
        handle_read_policy=ISOLATED_READ_PROFILE
        if safety_profile == ISOLATED_READ_PROFILE
        else "isolated_cursor_read_probe_required",
        readonly_command_attempts=attempts,
        decision=decision,
        error="; ".join(errors),
    )


def summarize_cursor_composer_handle(handle: object, fallback_composer_id: str) -> dict:
    state = _find_composer_state(handle, fallback_composer_id)
    conversation_map = _dict_value(state, "conversationMap")
    conversation_state = _dict_value(state, "conversationState")
    return {
        "composer_id": _string_value(state, "composerId") or _string_value(handle, "composerId") or fallback_composer_id,
        "has_handle": isinstance(handle, dict),
        "has_state": isinstance(state, dict),
        "text": _string_value(state, "text"),
        "rich_text": _string_value(state, "richText"),
        "status": _string_value(state, "status"),
        "unified_mode": _string_value(state, "unifiedMode"),
        "force_mode": _string_value(state, "forceMode"),
        "is_agentic": bool(_value(state, "isAgentic")),
        "has_pending_plan": bool(_value(state, "hasPendingPlan")),
        "has_blocking_pending_actions": bool(_value(state, "hasBlockingPendingActions")),
        "conversation_bubble_count": len(conversation_map),
        "queue_item_count": len(_list_value(state, "queueItems")),
        "todo_count": len(_list_value(state, "todos")),
        "root_prompt_count": len(_list_value(conversation_state, "rootPromptMessagesJson")),
        "turn_count": len(_list_value(conversation_state, "turns")),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--composer-id", action="append", default=[])
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--include-handles", action="store_true")
    parser.add_argument("--safety-profile", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bridge_url = resolve_ide_bridge_url(
        args.bridge_url,
        agent_id="cursor",
        project_name=args.project_name,
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.bridge_registry_path or ()),
    )
    report = probe_cursor_live_composer_state(
        bridge_url,
        workspace_path=args.workspace_path,
        project_name=args.project_name,
        composer_ids=tuple(args.composer_id or ()),
        request_timeout=args.request_timeout,
        include_handles=bool(args.include_handles),
        safety_profile=args.safety_profile,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Cursor live composer state: "
            f"decision={data['decision']} composers={len(data['composers'])}"
        )
    return 0 if report.ok else 1


def _find_composer_state(handle: object, composer_id: str) -> dict:
    if not isinstance(handle, dict):
        return {}
    if handle.get("composerId") == composer_id and (
        isinstance(handle.get("text"), str) or isinstance(handle.get("conversationMap"), dict)
    ):
        return handle
    candidates = (
        _nested(handle, ("byId", composer_id)),
        _nested(handle, ("data", "byId", composer_id)),
        _nested(handle, ("_data", "byId", composer_id)),
        _nested(handle, ("manager", "byId", composer_id)),
        _nested(handle, ("manager", "data", "byId", composer_id)),
        _nested(handle, ("manager", "_data", "byId", composer_id)),
        _nested(handle, ("manager", "backend", "data", "byId", composer_id)),
        _nested(handle, ("manager", "backend", "composerData", "byId", composer_id)),
        _nested(handle, ("manager", "backend", "composerDataService", "data", "byId", composer_id)),
        _nested(handle, ("manager", "loadedComposers", "store", "byId", composer_id)),
        _nested(handle, ("manager", "loadedComposers", "byId", composer_id)),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return handle


def _nested(value: object, keys: tuple[str, ...]) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _value(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, dict) else None


def _string_value(value: object, key: str) -> str:
    item = _value(value, key)
    return item if isinstance(item, str) else ""


def _dict_value(value: object, key: str) -> dict:
    item = _value(value, key)
    return item if isinstance(item, dict) else {}


def _list_value(value: object, key: str) -> list:
    item = _value(value, key)
    return item if isinstance(item, list) else []


def _clean_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _clean_dicts(value: object) -> tuple[dict, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        selected.append(item)
        seen.add(item)
    return tuple(selected)


if __name__ == "__main__":
    raise SystemExit(main())
