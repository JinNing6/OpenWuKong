# -*- coding: utf-8 -*-
"""Probe Cursor's Glass Agent query command through the IDE bridge.

This path is for live logged-in Cursor windows only when the caller explicitly
uses the live Cursor safety profile. It does not use mouse, keyboard, clipboard,
or a fresh Cursor launch.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.evaluation.ide_bridge_url_resolution import resolve_ide_bridge_url


LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE = "live_cursor_glass_agent_query_probe"


@dataclasses.dataclass(frozen=True)
class CursorGlassAgentQueryProbeReport:
    bridge_url: str
    workspace_path: str
    message: str
    allow_write: bool = False
    safety_profile: str = ""
    bridge_probe_attempts: int = 0
    agent_request_attempts: int = 0
    decision: str = ""
    response: dict = dataclasses.field(default_factory=dict)
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-glass-agent-query-probe"

    @property
    def safety_mode(self) -> str:
        if self.allow_write and self.safety_profile == LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE:
            return "live_glass_agent_query_probe"
        return "dry_run_bridge_contract"

    @property
    def control_allowed(self) -> bool:
        return self.allow_write and self.safety_profile == LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE

    @property
    def control_attempts(self) -> int:
        return self.agent_request_attempts if self.control_allowed else 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def keyboard_input_attempts(self) -> int:
        return 0

    @property
    def clipboard_write_attempts(self) -> int:
        return 0

    @property
    def bridge_send_attempts(self) -> int:
        return self.agent_request_attempts if self.control_allowed else 0

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
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "bridge_send_attempts": self.bridge_send_attempts,
            "bridge_probe_attempts": self.bridge_probe_attempts,
            "agent_request_attempts": self.agent_request_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "allow_write": self.allow_write,
            "safety_profile": self.safety_profile,
            "response": dict(self.response),
            "error": self.error,
        }


def probe_cursor_glass_agent_query(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    message: str,
    allow_write: bool = False,
    safety_profile: str = "",
    bridge_client: IDEExtensionBridgeClient | None = None,
    request_timeout: float = 5.0,
) -> CursorGlassAgentQueryProbeReport:
    workspace = str(Path(workspace_path)) if workspace_path else ""
    if allow_write and safety_profile != LIVE_GLASS_AGENT_QUERY_SAFETY_PROFILE:
        return CursorGlassAgentQueryProbeReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=True,
            safety_profile=safety_profile,
            decision="cursor_glass_agent_query_requires_live_profile",
            error="cursor_glass_agent_query_requires_live_profile",
        )

    target = ConnectorTarget(
        project_name=Path(workspace).name if workspace else "",
        workspace_path=workspace,
        workspace_hint=Path(workspace).name if workspace else "",
        ide_bridge_url=bridge_url,
    )
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    try:
        response = client.cursor_glass_agent_query(
            bridge_url,
            target,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
        )
    except Exception as exc:
        return CursorGlassAgentQueryProbeReport(
            bridge_url=bridge_url,
            workspace_path=workspace,
            message=message,
            allow_write=allow_write,
            safety_profile=safety_profile,
            bridge_probe_attempts=1,
            agent_request_attempts=0,
            decision="cursor_glass_agent_query_probe_failed",
            error=str(exc) or exc.__class__.__name__,
        )
    return CursorGlassAgentQueryProbeReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        message=message,
        allow_write=allow_write,
        safety_profile=safety_profile,
        bridge_probe_attempts=1,
        agent_request_attempts=1 if allow_write else 0,
        decision=str(response.get("decision", "") or "cursor_glass_agent_query_response"),
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
    report = probe_cursor_glass_agent_query(
        bridge_url,
        workspace_path=args.workspace_path,
        message=args.message,
        allow_write=args.allow_write,
        safety_profile=args.safety_profile,
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
            "Cursor Glass Agent query probe: "
            f"decision={data['decision']} "
            f"bridge_probe_attempts={data['bridge_probe_attempts']} "
            f"agent_request_attempts={data['agent_request_attempts']}"
        )
    return 0 if data["ok"] or data["decision"] == "cursor_glass_agent_query_requires_live_profile" else 1


if __name__ == "__main__":
    raise SystemExit(main())
