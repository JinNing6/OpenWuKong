# -*- coding: utf-8 -*-
"""Dry-run strategy report for a Codex webview/shared-object bridge."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Optional

from openwukong.evaluation.codex_extension_bridge_probe import (
    CodexExtensionBridgeProbeReport,
    probe_codex_extension_bridge,
)


RECOMMENDED_STRATEGY = "codex_side_shared_object_bridge"


@dataclasses.dataclass(frozen=True)
class CodexWebviewBridgeStrategyReport:
    bridge_url: str
    workspace_path: str = ""
    project_name: str = ""
    decision: str = ""
    recommended_strategy: str = ""
    implementation_stage: str = "dry_run_contract"
    public_prompt_command_ready: bool = False
    public_extension_api_ready: bool = False
    webview_route_verified: bool = False
    routes: tuple[dict, ...] = ()
    required_contract: tuple[dict, ...] = ()
    probe_report: dict = dataclasses.field(default_factory=dict)
    error: str = ""

    @property
    def mode(self) -> str:
        return "codex-webview-bridge-strategy"

    @property
    def safety_mode(self) -> str:
        return "dry_run_no_foreground_codex_bridge_design"

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
    def keyboard_input_attempts(self) -> int:
        return 0

    @property
    def clipboard_write_attempts(self) -> int:
        return 0

    @property
    def ok(self) -> bool:
        return self.decision == "codex_webview_bridge_strategy_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "recommended_strategy": self.recommended_strategy,
            "implementation_stage": self.implementation_stage,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "project_name": self.project_name,
            "public_prompt_command_ready": self.public_prompt_command_ready,
            "public_extension_api_ready": self.public_extension_api_ready,
            "webview_route_verified": self.webview_route_verified,
            "routes": [dict(item) for item in self.routes],
            "required_contract": [dict(item) for item in self.required_contract],
            "probe_report": dict(self.probe_report),
            "error": self.error,
        }


def build_codex_webview_bridge_strategy(
    bridge_url: str,
    *,
    workspace_path: str | Path = "",
    project_name: str = "",
    probe_report: CodexExtensionBridgeProbeReport | dict | None = None,
    request_timeout: float = 5.0,
) -> CodexWebviewBridgeStrategyReport:
    if probe_report is None:
        probe = probe_codex_extension_bridge(
            bridge_url,
            workspace_path=workspace_path,
            project_name=project_name,
            request_timeout=request_timeout,
        ).to_dict()
    elif hasattr(probe_report, "to_dict"):
        probe = probe_report.to_dict()
    else:
        probe = dict(probe_report)

    workspace = str(Path(workspace_path)) if workspace_path else str(probe.get("workspace_path", "") or "")
    public_prompt_ready = bool(probe.get("prompt_send_ready", False))
    extension_exports_type = str(probe.get("extension_exports_type", "") or "")
    export_keys = probe.get("extension_export_keys", ())
    public_api_ready = extension_exports_type not in {"", "undefined", "null"} and bool(export_keys)
    webview_verified = _has_webview_markers(probe)
    routes = _candidate_routes(
        public_prompt_ready=public_prompt_ready,
        public_api_ready=public_api_ready,
        webview_verified=webview_verified,
        probe=probe,
    )

    if public_prompt_ready:
        decision = "codex_public_prompt_command_available"
        recommended = "public_prompt_command"
        error = ""
    elif webview_verified:
        decision = "codex_webview_bridge_strategy_ready"
        recommended = RECOMMENDED_STRATEGY
        error = ""
    else:
        decision = "codex_webview_bridge_strategy_blocked"
        recommended = ""
        error = "codex_webview_route_evidence_missing"

    return CodexWebviewBridgeStrategyReport(
        bridge_url=bridge_url,
        workspace_path=workspace,
        project_name=project_name or str(probe.get("project_name", "") or ""),
        decision=decision,
        recommended_strategy=recommended,
        public_prompt_command_ready=public_prompt_ready,
        public_extension_api_ready=public_api_ready,
        webview_route_verified=webview_verified,
        routes=routes,
        required_contract=_required_contract() if recommended == RECOMMENDED_STRATEGY else (),
        probe_report=probe,
        error=error,
    )


def _candidate_routes(
    *,
    public_prompt_ready: bool,
    public_api_ready: bool,
    webview_verified: bool,
    probe: dict,
) -> tuple[dict, ...]:
    return (
        {
            "route_id": "public_vscode_prompt_command",
            "status": "ready" if public_prompt_ready else "blocked",
            "reason": "no chatgpt.* command is classified as prompt_send"
            if not public_prompt_ready
            else "prompt-send command available",
        },
        {
            "route_id": "public_extension_exports_api",
            "status": "ready" if public_api_ready else "blocked",
            "reason": "openai.chatgpt extension.exports is undefined or has no callable keys"
            if not public_api_ready
            else "extension exports callable API keys",
            "exports_type": str(probe.get("extension_exports_type", "") or ""),
            "export_keys": list(probe.get("extension_export_keys", ()) or ()),
        },
        {
            "route_id": "deep_link_prefill",
            "status": "blocked",
            "reason": "Codex URI handler navigates by path and no prompt/prefill URI contract is exposed",
        },
        {
            "route_id": "cross_extension_webview_post_message",
            "status": "blocked",
            "reason": "VS Code API does not expose another extension's webview object for arbitrary postMessage",
        },
        {
            "route_id": RECOMMENDED_STRATEGY,
            "status": "candidate" if webview_verified else "blocked",
            "reason": "composer_prefill/shared-object-set/open-vscode-command markers verified"
            if webview_verified
            else "webview shared-object route markers missing",
        },
        {
            "route_id": "foreground_keyboard_or_clipboard",
            "status": "rejected",
            "reason": "violates no-foreground and no-clipboard operation contract",
        },
    )


def _required_contract() -> tuple[dict, ...]:
    return (
        {
            "step": "codex_side_bridge",
            "requirement": "run inside the Codex extension/webview boundary or an explicitly owned patched Codex profile",
        },
        {
            "step": "prefill",
            "requirement": "set shared object key composer_prefill with text, cwd, and attachments",
        },
        {
            "step": "surface",
            "requirement": "trigger chatgpt.newChat or chatgpt.newCodexPanel after prefill is present",
        },
        {
            "step": "send",
            "requirement": "submit from Codex-side code without keyboard, mouse, or clipboard input",
        },
        {
            "step": "readback",
            "requirement": "read thread or turn state and prove the marker appears in transcript/response",
        },
    )


def _has_webview_markers(probe: dict) -> bool:
    evidence = probe.get("webview_route_evidence", ())
    found: set[str] = set()
    for item in evidence if isinstance(evidence, (list, tuple)) else ():
        if not isinstance(item, dict):
            continue
        found.update(str(marker) for marker in item.get("markers", ()) or ())
    return {"composer_prefill", "shared-object-set", "open-vscode-command"}.issubset(found)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", required=True)
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--probe-report", default="")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    probe_report = None
    if args.probe_report:
        probe_report = json.loads(Path(args.probe_report).read_text(encoding="utf-8"))
    report = build_codex_webview_bridge_strategy(
        args.bridge_url,
        workspace_path=args.workspace_path,
        project_name=args.project_name,
        probe_report=probe_report,
        request_timeout=args.request_timeout,
    )
    data = report.to_dict()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Codex webview bridge strategy: "
            f"decision={data['decision']} "
            f"recommended={data['recommended_strategy'] or 'none'}"
        )
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
