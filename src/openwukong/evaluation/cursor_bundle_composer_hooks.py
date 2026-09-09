# -*- coding: utf-8 -*-
"""Read-only Cursor bundle composer hook discovery.

This module statically inspects Cursor's bundled workbench JavaScript. It does
not start Cursor, execute commands, attach DevTools, send messages, click UI, or
type input.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Optional


CHAT_OPEN_COMMAND = "workbench.action.chat.open"


def analyze_cursor_bundle_composer_hooks(bundle_path: str | Path) -> dict:
    path = Path(bundle_path)
    if not path.exists() or not path.is_file():
        return _base_report(path) | {
            "bundle_found": False,
            "decision": "cursor_bundle_missing",
            "signals": _empty_signals(),
            "risky_commands": [],
            "hook_candidates": [],
            "next_actions": [
                "locate Cursor resources/app/out/vs/workbench/workbench.desktop.main.js",
                "rerun the read-only bundle scan against the discovered bundle path",
            ],
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    signals = _collect_signals(text)
    risky_commands = _discover_risky_commands(text)
    hook_candidates = _discover_hook_candidates(text)
    decision = (
        "cursor_native_hook_candidates_found"
        if hook_candidates
        else "cursor_native_hook_candidates_missing"
    )
    return _base_report(path) | {
        "bundle_found": True,
        "decision": decision,
        "signals": signals,
        "risky_commands": risky_commands,
        "hook_candidates": hook_candidates,
        "next_actions": _next_actions(risky_commands, hook_candidates),
    }


def _base_report(path: Path) -> dict:
    return {
        "mode": "cursor-bundle-composer-hook-discovery",
        "safety_mode": "read_only_static_bundle_scan",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "bridge_send_attempts": 0,
        "bundle_path": str(path),
    }


def _empty_signals() -> dict:
    return {
        "chat_open_command_count": 0,
        "create_composer_partial_state_count": 0,
        "update_composer_data_count": 0,
        "update_composer_data_set_store_count": 0,
        "fire_should_force_text_count": 0,
        "show_and_focus_count": 0,
        "submit_chat_count": 0,
    }


def _collect_signals(text: str) -> dict:
    return {
        "chat_open_command_count": _count(text, f'registerCommand("{CHAT_OPEN_COMMAND}"'),
        "create_composer_partial_state_count": _count(text, "createComposer({partialState"),
        "update_composer_data_count": _count(text, "updateComposerData("),
        "update_composer_data_set_store_count": _count(text, "updateComposerDataSetStore("),
        "fire_should_force_text_count": _count(text, "fireShouldForceText"),
        "show_and_focus_count": _count(text, "showAndFocus("),
        "submit_chat_count": _count(text, "submitChat"),
    }


def _discover_risky_commands(text: str) -> list[dict]:
    snippet = _command_snippet(text, CHAT_OPEN_COMMAND)
    if not snippet:
        return []
    risk_markers = [
        marker
        for marker in ("createComposer({partialState", "fireShouldForceText", "showAndFocus")
        if marker in snippet
    ]
    activation_evidence = "showAndFocus" in snippet
    draft_write_evidence = "createComposer({partialState" in snippet
    return [
        {
            "command_id": CHAT_OPEN_COMMAND,
            "classification": "risky_focus_command",
            "recommendation": "do_not_use_as_background_sender",
            "draft_write_evidence": draft_write_evidence,
            "activation_evidence": activation_evidence,
            "risk_markers": risk_markers,
            "risk": "writes draft but invokes the composer view focus path",
            "evidence_snippet": _trim_snippet(snippet),
        }
    ]


def _discover_hook_candidates(text: str) -> list[dict]:
    candidates: list[dict] = []
    if "createComposer({partialState" in text:
        candidates.append(
            _hook_candidate(
                "composerService.createComposer.partialState",
                capability="draft_create",
                evidence_marker="createComposer({partialState",
            )
        )
    if "updateComposerData(" in text or re.search(r"updateComposerData\([^)]*\)\{[^}]*setData", text):
        candidates.append(
            _hook_candidate(
                "composerDataService.updateComposerData",
                capability="draft_update",
                evidence_marker="updateComposerData",
            )
        )
    if "updateComposerDataSetStore(" in text:
        candidates.append(
            _hook_candidate(
                "composerDataService.updateComposerDataSetStore",
                capability="structured_draft_update",
                evidence_marker="updateComposerDataSetStore",
            )
        )
    return candidates


def _hook_candidate(hook_id: str, *, capability: str, evidence_marker: str) -> dict:
    return {
        "hook_id": hook_id,
        "surface": "cursor_internal_service",
        "capability": capability,
        "background_safety": "candidate_requires_bridge_validation",
        "validation_state": "static_candidate_unvalidated",
        "requires_custom_bridge": True,
        "calls_show_and_focus": False,
        "evidence_markers": [evidence_marker],
        "recommended_probe": "extension_internal_service_probe",
    }


def _next_actions(risky_commands: list[dict], hook_candidates: list[dict]) -> list[str]:
    actions: list[str] = []
    if risky_commands:
        actions.append("keep risky commands out of active background send mappings")
    if hook_candidates:
        actions.append("add an extension-side draft-only endpoint around the internal composer service candidate")
        actions.append("validate the endpoint in an isolated Cursor profile with delayed dialog and foreground gates")
    else:
        actions.append("inspect the bundle for renamed composer data service methods")
    return actions


def _command_snippet(text: str, command_id: str) -> str:
    marker = f'registerCommand("{command_id}"'
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start : min(len(text), start + 2500)]


def _trim_snippet(value: str, limit: int = 900) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _count(text: str, needle: str) -> int:
    return text.count(needle)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only static discovery of Cursor composer hook candidates."
    )
    parser.add_argument("bundle_path", help="Path to Cursor workbench.desktop.main.js")
    parser.add_argument("--output", default="", help="Optional JSON report path.")
    parser.add_argument("--json", action="store_true", help="Print the JSON report.")
    args = parser.parse_args(argv)

    report = analyze_cursor_bundle_composer_hooks(args.bundle_path)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "Cursor bundle composer hook discovery: "
            f"decision={report['decision']} hooks={len(report['hook_candidates'])} "
            f"risky_commands={len(report['risky_commands'])}"
        )
    return 0 if report.get("bundle_found", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
