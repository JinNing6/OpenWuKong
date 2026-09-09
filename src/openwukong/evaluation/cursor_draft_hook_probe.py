# -*- coding: utf-8 -*-
"""Probe the Cursor draft-only extension hook.

The default path is dry-run and does not write to Cursor. Real draft writes are
blocked unless the caller explicitly requests the isolated probe safety profile.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


ISOLATED_SAFETY_PROFILE = "isolated_cursor_draft_probe"
LIVE_ATTACH_SAFETY_PROFILE = "live_cursor_attach_draft_probe"
LIVE_ATTACH_WRITE_SAFETY_PROFILE = "live_cursor_attach_draft_write_probe"
WRITE_SAFETY_PROFILES = {ISOLATED_SAFETY_PROFILE, LIVE_ATTACH_WRITE_SAFETY_PROFILE}


@dataclasses.dataclass(frozen=True)
class CursorDraftHookProbeReport:
    bridge_url: str
    workspace_path: str
    message: str
    allow_write: bool = False
    safety_profile: str = ""
    composer_ids: tuple[str, ...] = ()
    bridge_probe_attempts: int = 0
    draft_write_attempts: int = 0
    decision: str = ""
    response: dict = dataclasses.field(default_factory=dict)
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-draft-hook-probe"

    @property
    def safety_mode(self) -> str:
        if self.allow_write and self.safety_profile == ISOLATED_SAFETY_PROFILE:
            return "isolated_draft_write_probe"
        if self.allow_write and self.safety_profile == LIVE_ATTACH_WRITE_SAFETY_PROFILE:
            return "live_attach_draft_write_probe"
        return "dry_run_bridge_contract"

    @property
    def control_allowed(self) -> bool:
        return self.allow_write and self.safety_profile in WRITE_SAFETY_PROFILES

    @property
    def control_attempts(self) -> int:
        return self.draft_write_attempts if self.control_allowed else 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return bool(self.response.get("ok", False)) if self.response else False

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
            "bridge_probe_attempts": self.bridge_probe_attempts,
            "draft_write_attempts": self.draft_write_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "allow_write": self.allow_write,
            "safety_profile": self.safety_profile,
            "composer_ids": list(self.composer_ids),
            "response": dict(self.response),
            "error": self.error,
        }


def probe_cursor_draft_hook(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    message: str,
    allow_write: bool = False,
    safety_profile: str = "",
    composer_ids: Iterable[str] = (),
    bridge_client: IDEExtensionBridgeClient | None = None,
    request_timeout: float = 5.0,
) -> CursorDraftHookProbeReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    selected_composer_ids = tuple(_clean_strings(composer_ids))
    if allow_write and safety_profile not in WRITE_SAFETY_PROFILES:
        return CursorDraftHookProbeReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            composer_ids=selected_composer_ids,
            decision="cursor_draft_hook_write_requires_isolated_profile",
            error="cursor_draft_hook_write_requires_isolated_profile",
        )

    target = ConnectorTarget(
        project_name=Path(workspace).name if workspace else "",
        workspace_path=workspace,
        workspace_hint=Path(workspace).name if workspace else "",
        ide_bridge_url=bridge_url,
    )
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    try:
        response = client.cursor_draft_hook(
            bridge_url,
            target,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            composer_ids=list(selected_composer_ids),
        )
    except Exception as exc:
        return CursorDraftHookProbeReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            composer_ids=selected_composer_ids,
            bridge_probe_attempts=1,
            draft_write_attempts=0,
            decision="cursor_draft_hook_probe_failed",
            error=str(exc) or exc.__class__.__name__,
        )
    return CursorDraftHookProbeReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=allow_write,
        safety_profile=safety_profile,
        composer_ids=selected_composer_ids,
        bridge_probe_attempts=1,
        draft_write_attempts=1 if allow_write else 0,
        decision=str(response.get("decision", "") or "cursor_draft_hook_response"),
        response=response,
        error="" if response.get("ok", False) else str(response.get("error", "")),
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--bridge-registry-path", action="append", default=[])
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--message", required=True)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--safety-profile", default="")
    parser.add_argument("--composer-id", action="append", default=[])
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    bridge_url = resolve_ide_bridge_url(
        args.bridge_url,
        agent_id="cursor",
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.bridge_registry_path or ()),
    )
    report = probe_cursor_draft_hook(
        bridge_url,
        workspace_path=args.workspace_path,
        message=args.message,
        allow_write=args.allow_write,
        safety_profile=args.safety_profile,
        composer_ids=tuple(args.composer_id or ()),
        request_timeout=args.request_timeout,
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
            "Cursor draft hook probe: "
            f"decision={data['decision']} "
            f"bridge_probe_attempts={data['bridge_probe_attempts']} "
            f"draft_write_attempts={data['draft_write_attempts']}"
        )
    return 0 if data["ok"] or data["decision"] == "cursor_draft_hook_write_requires_isolated_profile" else 1


def _clean_strings(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        selected.append(item)
        seen.add(item)
    return tuple(selected)


if __name__ == "__main__":
    raise SystemExit(main())
