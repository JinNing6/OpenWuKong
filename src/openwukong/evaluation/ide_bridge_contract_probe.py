# -*- coding: utf-8 -*-
"""Probe IDE command argument contracts through the extension bridge.

Unlike the read-only capability capture, this module can execute IDE commands.
It is intended for isolated sacrificial workspaces and temporary IDE profiles.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import hashlib
import json
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient


_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

_IGNORED_PATH_PREFIXES = {
    ("logs", "runtime"),
}


@dataclasses.dataclass(frozen=True)
class IDECommandArgumentVariant:
    name: str
    arguments: list


@dataclasses.dataclass(frozen=True)
class IDECommandVariantProbeResult:
    variant: str
    arguments: list
    ok: bool
    error: str
    workspace_changed: bool
    changed_files: tuple[str, ...]
    foreground_changed: bool
    target_foreground: bool
    system_dialog_detected: bool
    before_focus: dict
    after_focus: dict
    settled_focus: dict
    elapsed_ms: float
    before_state_ok: bool
    after_state_ok: bool
    response: dict

    def to_dict(self) -> dict:
        return {
            "variant": self.variant,
            "arguments": self.arguments,
            "ok": self.ok,
            "error": self.error,
            "workspace_changed": self.workspace_changed,
            "changed_files": list(self.changed_files),
            "foreground_changed": self.foreground_changed,
            "target_foreground": self.target_foreground,
            "system_dialog_detected": self.system_dialog_detected,
            "focus_observation_available": _focus_available(self.before_focus)
            and _focus_available(self.after_focus)
            and _focus_available(self.settled_focus),
            "before_focus": dict(self.before_focus),
            "after_focus": dict(self.after_focus),
            "settled_focus": dict(self.settled_focus),
            "elapsed_ms": round(self.elapsed_ms, 3),
            "before_state_ok": self.before_state_ok,
            "after_state_ok": self.after_state_ok,
            "response": dict(self.response),
        }


@dataclasses.dataclass(frozen=True)
class IDECommandContractProbeResult:
    command_id: str
    status: str
    accepted_variant: str
    accepted_variants: tuple[str, ...]
    workspace_changed: bool
    changed_files: tuple[str, ...]
    foreground_changed: bool
    target_foreground: bool
    system_dialog_detected: bool
    recommended_adapter: bool
    attempts: tuple[IDECommandVariantProbeResult, ...]

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "status": self.status,
            "accepted_variant": self.accepted_variant,
            "accepted_variants": list(self.accepted_variants),
            "workspace_changed": self.workspace_changed,
            "changed_files": list(self.changed_files),
            "foreground_changed": self.foreground_changed,
            "target_foreground": self.target_foreground,
            "system_dialog_detected": self.system_dialog_detected,
            "recommended_adapter": self.recommended_adapter,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclasses.dataclass(frozen=True)
class IDEBridgeContractProbeReport:
    bridge_url: str
    workspace_path: str
    adapter_id: str
    message: str
    results: tuple[IDECommandContractProbeResult, ...]
    started_at: float
    elapsed_ms: float

    @property
    def mode(self) -> str:
        return "ide-bridge-contract-probe"

    @property
    def safety_mode(self) -> str:
        return "isolated_sacrificial_workspace"

    @property
    def control_allowed(self) -> bool:
        return True

    @property
    def control_attempts(self) -> int:
        return sum(len(result.attempts) for result in self.results)

    @property
    def focus_stable(self) -> bool:
        return not any(result.foreground_changed for result in self.results)

    @property
    def background_execution_observed(self) -> bool:
        return any(result.recommended_adapter for result in self.results)

    @property
    def system_dialog_detected(self) -> bool:
        return any(result.system_dialog_detected for result in self.results)

    def to_dict(self) -> dict:
        validated_mapping = _build_validated_mapping(self.adapter_id, self.results)
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "adapter_id": self.adapter_id,
            "message": self.message,
            "command_count": len(self.results),
            "results": [result.to_dict() for result in self.results],
            "focus_stable": self.focus_stable,
            "foreground_changed": not self.focus_stable,
            "system_dialog_detected": self.system_dialog_detected,
            "background_execution_observed": self.background_execution_observed,
            "recommended_commands": [
                result.command_id for result in self.results if result.recommended_adapter
            ],
            "validated_mapping": validated_mapping,
            "started_at": self.started_at,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def build_argument_variants(message: str) -> tuple[IDECommandArgumentVariant, ...]:
    safe_message = str(message or "OPENWUKONG_PROBE_NO_EDIT")
    return (
        IDECommandArgumentVariant(name="no_args", arguments=[]),
        IDECommandArgumentVariant(name="string_message", arguments=[safe_message]),
        IDECommandArgumentVariant(
            name="object_message",
            arguments=[
                {
                    "message": safe_message,
                    "target": {},
                    "metadata": {
                        "openwukong_contract_probe": True,
                        "no_file_edits_requested": True,
                    },
                }
            ],
        ),
        IDECommandArgumentVariant(
            name="query_object",
            arguments=[
                {
                    "query": safe_message,
                    "openwukong_contract_probe": True,
                    "no_file_edits_requested": True,
                }
            ],
        ),
    )


def select_probe_command_ids(
    candidate_report: dict,
    *,
    adapter_id: str = "cursor",
    max_commands: int = 5,
) -> list[str]:
    if not isinstance(candidate_report, dict):
        return []

    raw_candidates: list[str] = []
    active_mapping = candidate_report.get("active_mapping", {})
    if isinstance(active_mapping, dict):
        adapter = active_mapping.get(adapter_id, {})
        if isinstance(adapter, dict):
            raw_candidates.extend(_string_list(adapter.get("commandCandidates", [])))

    raw_candidates.extend(_string_list(candidate_report.get(f"{adapter_id}_review_candidates", [])))
    if adapter_id == "cursor":
        raw_candidates.extend(_string_list(candidate_report.get("cursor_review_candidates", [])))

    selected: list[str] = []
    seen: set[str] = set()
    for command_id in raw_candidates:
        normalized = command_id.strip()
        if not normalized or normalized in seen:
            continue
        selected.append(normalized)
        seen.add(normalized)
        if max_commands > 0 and len(selected) >= max_commands:
            break
    return selected


def probe_ide_command_contracts(
    bridge_url: str,
    *,
    workspace_path: str,
    command_ids: list[str] | tuple[str, ...],
    adapter_id: str = "cursor",
    message: str = "OPENWUKONG_PROBE_NO_EDIT",
    request_timeout: float = 5.0,
    variants: tuple[IDECommandArgumentVariant, ...] | None = None,
    bridge_client: IDEExtensionBridgeClient | None = None,
    focus_observer: object | None = None,
    post_action_observation_delay_sec: float = 0.0,
) -> IDEBridgeContractProbeReport:
    started = time.time()
    perf_started = time.perf_counter()
    workspace = Path(workspace_path).resolve()
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    target = ConnectorTarget(
        project_name=workspace.name,
        workspace_path=str(workspace),
        workspace_hint=workspace.name,
        ide_bridge_url=bridge_url,
    )
    effective_variants = variants or build_argument_variants(message)
    results = tuple(
        _probe_single_command(
            client,
            bridge_url,
            target,
            workspace,
            command_id,
            effective_variants,
            focus_observer,
            post_action_observation_delay_sec,
        )
        for command_id in _dedupe_strings(command_ids)
    )
    return IDEBridgeContractProbeReport(
        bridge_url=bridge_url,
        workspace_path=str(workspace),
        adapter_id=adapter_id,
        message=message,
        results=results,
        started_at=started,
        elapsed_ms=(time.perf_counter() - perf_started) * 1000,
    )


def build_bridge_settings_from_probe_report(
    report: dict,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    auto_start: bool = True,
) -> dict:
    mapping = report.get("validated_mapping", {}) if isinstance(report, dict) else {}
    if not isinstance(mapping, dict):
        mapping = {}

    chat_adapters: dict[str, dict] = {}
    allowed_commands: list[str] = []
    for adapter_id, adapter in mapping.items():
        if not isinstance(adapter, dict):
            continue
        command_id = str(adapter.get("commandId", "") or "").strip()
        candidates = _dedupe_strings(adapter.get("commandCandidates", []))
        if command_id:
            allowed_commands.append(command_id)
            if command_id not in candidates:
                candidates.insert(0, command_id)
        chat_adapters[str(adapter_id)] = {
            "label": str(adapter.get("label", adapter_id) or adapter_id),
            "commandId": command_id,
            "commandCandidates": candidates,
        }

    return {
        "openwukong.bridge.autoStart": bool(auto_start),
        "openwukong.bridge.host": str(host or "127.0.0.1"),
        "openwukong.bridge.port": int(port),
        "openwukong.bridge.allowedCommands": _dedupe_strings(allowed_commands),
        "openwukong.bridge.chatAdapters": chat_adapters,
    }


def build_probe_allowlist_settings(
    command_ids: list[str] | tuple[str, ...],
    *,
    adapter_id: str = "cursor",
    host: str = "127.0.0.1",
    port: int = 0,
    auto_start: bool = True,
) -> dict:
    commands = _dedupe_strings(command_ids)
    adapter_key = str(adapter_id or "cursor").strip() or "cursor"
    return {
        "openwukong.bridge.autoStart": bool(auto_start),
        "openwukong.bridge.host": str(host or "127.0.0.1"),
        "openwukong.bridge.port": int(port),
        "openwukong.bridge.allowedCommands": commands,
        "openwukong.bridge.chatAdapters": {
            adapter_key: {
                "label": adapter_key,
                "commandId": "",
                "commandCandidates": commands,
            }
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe IDE bridge command argument contracts in an isolated workspace."
    )
    parser.add_argument("bridge_url", help="Resolved IDE bridge URL, for example a dynamic URL read from the local bridge registry.")
    parser.add_argument("--workspace-path", default=os.getcwd(), help="Sacrificial workspace path.")
    parser.add_argument("--candidate-report", default="", help="Adapter candidate JSON report.")
    parser.add_argument("--adapter-id", default="cursor", help="Adapter id to select from the candidate report.")
    parser.add_argument("--command-id", action="append", default=[], help="Explicit command id to probe. Repeatable.")
    parser.add_argument("--max-commands", type=int, default=5, help="Maximum candidate commands to probe.")
    parser.add_argument("--message", default="OPENWUKONG_PROBE_NO_EDIT", help="Probe message.")
    parser.add_argument(
        "--variant",
        action="append",
        choices=["no_args", "string_message", "object_message", "query_object"],
        default=[],
        help="Limit argument variants to run. Repeatable.",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP request timeout in seconds.")
    parser.add_argument(
        "--post-action-observation-delay-sec",
        type=float,
        default=0.25,
        help="Delay before the post-command focus check used to catch delayed system dialogs.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument(
        "--probe-settings-output",
        default="",
        help="Optional pre-launch VS Code/Cursor settings JSON with candidate commands allowlisted for an isolated probe profile.",
    )
    parser.add_argument(
        "--write-probe-settings-only",
        action="store_true",
        help="Write --probe-settings-output and exit without contacting the bridge.",
    )
    parser.add_argument("--settings-output", default="", help="Optional VS Code/Cursor settings JSON path.")
    parser.add_argument("--settings-host", default="127.0.0.1", help="Bridge host to write into settings output.")
    parser.add_argument("--settings-port", type=int, default=0, help="Bridge port to write into settings output. Use 0 for an operating-system-assigned unused port.")
    parser.add_argument("--settings-no-autostart", action="store_true", help="Disable bridge autoStart in settings output.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args(argv)

    candidate_report = _load_json_file(args.candidate_report) if args.candidate_report else {}
    command_ids = _dedupe_strings(args.command_id)
    if not command_ids:
        command_ids = select_probe_command_ids(
            candidate_report,
            adapter_id=args.adapter_id,
            max_commands=args.max_commands,
        )
    if not command_ids:
        parser.error("no command ids to probe; pass --command-id or --candidate-report")

    if args.probe_settings_output:
        probe_settings = build_probe_allowlist_settings(
            command_ids,
            adapter_id=args.adapter_id,
            host=args.settings_host,
            port=args.settings_port,
            auto_start=not args.settings_no_autostart,
        )
        probe_settings_path = Path(args.probe_settings_output)
        probe_settings_path.parent.mkdir(parents=True, exist_ok=True)
        probe_settings_path.write_text(
            json.dumps(probe_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if args.write_probe_settings_only:
            data = {
                "mode": "ide-bridge-probe-settings",
                "safety_mode": "isolated_sacrificial_profile",
                "control_allowed": False,
                "control_attempts": 0,
                "adapter_id": args.adapter_id,
                "command_count": len(command_ids),
                "command_ids": command_ids,
                "settings_output": str(probe_settings_path),
            }
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(
                    "IDE bridge probe settings written: "
                    f"commands={data['command_count']} output={data['settings_output']}"
                )
            return 0

    report = probe_ide_command_contracts(
        args.bridge_url,
        workspace_path=args.workspace_path,
        command_ids=command_ids,
        adapter_id=args.adapter_id,
        message=args.message,
        request_timeout=args.timeout,
        variants=_select_variants(args.message, args.variant),
        post_action_observation_delay_sec=args.post_action_observation_delay_sec,
    )
    data = report.to_dict()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.settings_output:
        settings = build_bridge_settings_from_probe_report(
            data,
            host=args.settings_host,
            port=args.settings_port,
            auto_start=not args.settings_no_autostart,
        )
        settings_path = Path(args.settings_output)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        recommended = ", ".join(data["recommended_commands"]) or "none"
        print(
            "IDE bridge contract probe complete: "
            f"commands={data['command_count']} attempts={data['control_attempts']} "
            f"recommended={recommended}"
        )
    return 0


def _probe_single_command(
    client: IDEExtensionBridgeClient,
    bridge_url: str,
    target: ConnectorTarget,
    workspace: Path,
    command_id: str,
    variants: tuple[IDECommandArgumentVariant, ...],
    focus_observer: object | None,
    post_action_observation_delay_sec: float,
) -> IDECommandContractProbeResult:
    attempts: list[IDECommandVariantProbeResult] = []
    for variant in variants:
        attempts.append(
            _probe_single_variant(
                client,
                bridge_url,
                target,
                workspace,
                command_id,
                variant,
                focus_observer,
                post_action_observation_delay_sec,
            )
        )

    accepted = [attempt for attempt in attempts if attempt.ok]
    safe_accepted = [
        attempt
        for attempt in accepted
        if not attempt.workspace_changed and not attempt.foreground_changed
        and not attempt.target_foreground
    ]
    workspace_changed = any(attempt.workspace_changed for attempt in attempts)
    changed_files = _merge_changed_files(attempt.changed_files for attempt in attempts)
    foreground_changed = any(attempt.foreground_changed for attempt in attempts)
    target_foreground = any(attempt.target_foreground for attempt in attempts)
    system_dialog_detected = any(attempt.system_dialog_detected for attempt in attempts)

    if workspace_changed and accepted:
        status = "mutating"
        accepted_variant = accepted[0].variant
    elif system_dialog_detected and accepted:
        status = "system_dialog_opened"
        accepted_variant = accepted[0].variant
    elif foreground_changed and accepted:
        status = "foreground_changed"
        accepted_variant = accepted[0].variant
    elif target_foreground and accepted:
        status = "target_foreground"
        accepted_variant = accepted[0].variant
    elif safe_accepted:
        status = "callable"
        accepted_variant = safe_accepted[0].variant
    elif accepted:
        status = "mutating"
        accepted_variant = accepted[0].variant
    else:
        status = "rejected"
        accepted_variant = ""

    recommended_contract_safe = any(
        attempt.variant in {"object_message", "query_object"}
        and attempt.ok
        and not attempt.workspace_changed
        and not attempt.foreground_changed
        and not attempt.target_foreground
        and not attempt.system_dialog_detected
        for attempt in attempts
    )

    return IDECommandContractProbeResult(
        command_id=command_id,
        status=status,
        accepted_variant=accepted_variant,
        accepted_variants=tuple(attempt.variant for attempt in accepted),
        workspace_changed=workspace_changed,
        changed_files=changed_files,
        foreground_changed=foreground_changed,
        target_foreground=target_foreground,
        system_dialog_detected=system_dialog_detected,
        recommended_adapter=status == "callable" and recommended_contract_safe,
        attempts=tuple(attempts),
    )


def _probe_single_variant(
    client: IDEExtensionBridgeClient,
    bridge_url: str,
    target: ConnectorTarget,
    workspace: Path,
    command_id: str,
    variant: IDECommandArgumentVariant,
    focus_observer: object | None,
    post_action_observation_delay_sec: float,
) -> IDECommandVariantProbeResult:
    before_state = _try_read_state(client, bridge_url, target)
    before_snapshot = _snapshot_workspace(workspace)
    before_focus = _capture_focus(focus_observer)
    started = time.perf_counter()
    response: dict = {}
    error = ""
    ok = False
    try:
        response = client.execute_command(
            bridge_url,
            target,
            command_id,
            list(variant.arguments),
        )
        ok = bool(response.get("ok", False))
        if not ok:
            error = str(response.get("error", "bridge_command_failed") or "bridge_command_failed")
    except Exception as exc:
        error = str(exc)
        response = {"ok": False, "error": error}
    elapsed_ms = (time.perf_counter() - started) * 1000
    after_focus = _capture_focus(focus_observer)
    if post_action_observation_delay_sec > 0:
        time.sleep(max(0.0, float(post_action_observation_delay_sec)))
        settled_focus = _capture_focus(focus_observer)
    else:
        settled_focus = dict(after_focus)
    after_snapshot = _snapshot_workspace(workspace)
    after_state = _try_read_state(client, bridge_url, target)
    changed_files = _diff_snapshots(before_snapshot, after_snapshot)
    foreground_changed = _foreground_changed(before_focus, after_focus) or _foreground_changed(
        before_focus,
        settled_focus,
    )
    target_foreground = _focus_matches_target(before_focus, target) or _focus_matches_target(
        after_focus,
        target,
    ) or _focus_matches_target(
        settled_focus,
        target,
    )
    system_dialog_detected = _system_dialog_detected(after_focus) or _system_dialog_detected(
        settled_focus,
    )

    return IDECommandVariantProbeResult(
        variant=variant.name,
        arguments=list(variant.arguments),
        ok=ok,
        error=error,
        workspace_changed=bool(changed_files),
        changed_files=changed_files,
        foreground_changed=foreground_changed,
        target_foreground=target_foreground,
        system_dialog_detected=system_dialog_detected,
        before_focus=before_focus,
        after_focus=after_focus,
        settled_focus=settled_focus,
        elapsed_ms=elapsed_ms,
        before_state_ok=bool(before_state.get("ok", False)),
        after_state_ok=bool(after_state.get("ok", False)),
        response=response,
    )


def _try_read_state(
    client: IDEExtensionBridgeClient,
    bridge_url: str,
    target: ConnectorTarget,
) -> dict:
    try:
        data = client.read_state(bridge_url, target)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(data, dict):
        return {"ok": False, "error": "ide_bridge_state_not_object"}
    return data


def _build_validated_mapping(
    adapter_id: str,
    results: tuple[IDECommandContractProbeResult, ...],
) -> dict:
    for result in results:
        contract_attempt = next(
            (
                attempt
                for attempt in result.attempts
                if attempt.variant in {"object_message", "query_object"}
                and attempt.ok
                and not attempt.workspace_changed
                and not attempt.foreground_changed
                and not attempt.target_foreground
                and not attempt.system_dialog_detected
            ),
            None,
        )
        if result.recommended_adapter and contract_attempt is not None:
            return {
                adapter_id: {
                    "label": adapter_id,
                    "commandId": result.command_id,
                    "commandCandidates": [result.command_id],
                    "available": True,
                    "validation": {
                        "status": result.status,
                        "acceptedVariant": contract_attempt.variant,
                        "workspaceChanged": False,
                        "foregroundChanged": False,
                        "targetForeground": False,
                        "systemDialogDetected": False,
                        "controlAttempts": len(result.attempts),
                    },
                }
            }
    return {
        adapter_id: {
            "label": adapter_id,
            "commandId": "",
            "commandCandidates": [result.command_id for result in results],
            "available": False,
            "validation": {
                "status": "no_validated_object_message_contract",
                "acceptedVariant": "",
                "workspaceChanged": any(result.workspace_changed for result in results),
                "foregroundChanged": any(result.foreground_changed for result in results),
                "targetForeground": any(result.target_foreground for result in results),
                "systemDialogDetected": any(
                    result.system_dialog_detected for result in results
                ),
                "controlAttempts": sum(len(result.attempts) for result in results),
            },
        }
    }


def _capture_focus(focus_observer: object | None) -> dict:
    if focus_observer is not None:
        try:
            data = focus_observer.capture()
        except Exception as exc:
            return {
                "available": False,
                "hwnd": 0,
                "title": "",
                "error": str(exc) or exc.__class__.__name__,
            }
        return _normalize_focus_snapshot(data)
    return _capture_windows_foreground_window()


def _capture_windows_foreground_window() -> dict:
    if not sys.platform.startswith("win"):
        return {
            "available": False,
            "hwnd": 0,
            "title": "",
            "error": "foreground_window_api_unavailable",
        }
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        hwnd = int(user32.GetForegroundWindow() or 0)
        title = ""
        class_name = ""
        process_id = 0
        thread_id = 0
        process_name = ""
        executable_path = ""
        child_texts: list[str] = []
        if hwnd:
            title = _get_window_text(user32, hwnd, max_chars=512)
            class_buffer = ctypes.create_unicode_buffer(256)
            copied = user32.GetClassNameW(wintypes.HWND(hwnd), class_buffer, len(class_buffer))
            if copied:
                class_name = class_buffer.value
            pid = wintypes.DWORD(0)
            thread_id = int(
                user32.GetWindowThreadProcessId(
                    wintypes.HWND(hwnd),
                    ctypes.byref(pid),
                )
                or 0
            )
            process_id = int(pid.value or 0)
            process_name, executable_path = _process_identity_for_pid(process_id)
            child_texts = _child_window_texts(user32, hwnd)
        return {
            "available": bool(hwnd),
            "hwnd": hwnd,
            "title": title,
            "class_name": class_name,
            "pid": process_id,
            "thread_id": thread_id,
            "process_name": process_name,
            "executable_path": executable_path,
            "child_texts": child_texts,
            "error": "",
        }
    except Exception as exc:
        return {
            "available": False,
            "hwnd": 0,
            "title": "",
            "error": str(exc) or exc.__class__.__name__,
        }


def _normalize_focus_snapshot(value: object) -> dict:
    data = value if isinstance(value, dict) else {}
    hwnd = _safe_int(data.get("hwnd"))
    title = str(data.get("title", "") or "")
    error = str(data.get("error", "") or "")
    available = bool(data.get("available", True)) and hwnd > 0 and not error
    return {
        "available": available,
        "hwnd": hwnd,
        "title": title,
        "class_name": str(data.get("class_name", "") or data.get("className", "") or ""),
        "pid": _safe_int(data.get("pid")),
        "thread_id": _safe_int(data.get("thread_id") or data.get("threadId")),
        "process_name": str(
            data.get("process_name", "") or data.get("processName", "") or ""
        ),
        "executable_path": str(
            data.get("executable_path", "") or data.get("executablePath", "") or ""
        ),
        "text": str(data.get("text", "") or data.get("body", "") or ""),
        "child_texts": _string_list(data.get("child_texts") or data.get("childTexts")),
        "error": error,
    }


def _foreground_changed(before_focus: dict, after_focus: dict) -> bool:
    if not _focus_available(before_focus) or not _focus_available(after_focus):
        return False
    return _safe_int(before_focus.get("hwnd")) != _safe_int(after_focus.get("hwnd"))


def _focus_matches_target(focus: dict, target: ConnectorTarget) -> bool:
    if not _focus_available(focus):
        return False
    title = str(focus.get("title", "") or "").casefold()
    if not title:
        return False
    tokens: list[str] = []
    for value in (
        target.project_name,
        target.workspace_hint,
        Path(target.workspace_path).name if target.workspace_path else "",
    ):
        token = str(value or "").strip().casefold()
        if len(token) >= 3 and token not in tokens:
            tokens.append(token)
    return any(token in title for token in tokens)


def _system_dialog_detected(focus: dict) -> bool:
    return _system_dialog_detected_v2(focus)


def _system_dialog_detected_v2(focus: dict) -> bool:
    if not _focus_available(focus):
        return False
    title = str(focus.get("title", "") or "").strip().casefold()
    fields = [
        title,
        str(focus.get("class_name", "") or "").casefold(),
        str(focus.get("process_name", "") or "").casefold(),
        str(focus.get("executable_path", "") or "").casefold(),
        str(focus.get("text", "") or "").casefold(),
        str(focus.get("error", "") or "").casefold(),
    ]
    fields.extend(str(item or "").casefold() for item in _string_list(focus.get("child_texts")))
    haystack = "\n".join(item for item in fields if item)
    if not haystack:
        return False
    markers = (
        "session-start",
        "选择应用以打开",
        "choose an app",
        "how do you want to open",
        "open with",
        "error launching app",
        "a javascript error occurred in the main process",
        "uncaught exception",
        "attachconsole failed",
        "unable to find electron app",
        "cannot find module",
        "?type=click",
        "type=click&tag",
    )
    if any(marker in haystack for marker in markers):
        return True
    if title == "error" and any(
        marker in haystack
        for marker in (
            "codex.exe",
            "openai.codex",
            "windowsapps",
            "electron",
            "attachconsole failed",
            "a javascript error occurred in the main process",
            "uncaught exception",
        )
    ):
        return True
    return False


def _get_window_text(user32, hwnd: int, *, max_chars: int) -> str:
    buffer = ctypes.create_unicode_buffer(max_chars)
    copied = user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, len(buffer))
    if not copied:
        return ""
    return buffer.value


def _child_window_texts(user32, hwnd: int) -> list[str]:
    texts: list[str] = []
    try:
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _visit(child_hwnd, _lparam):
            text = _get_window_text(user32, int(child_hwnd), max_chars=1024).strip()
            if text and text not in texts:
                texts.append(text)
            return True

        user32.EnumChildWindows(wintypes.HWND(hwnd), enum_proc(_visit), wintypes.LPARAM(0))
    except Exception:
        return texts
    return texts[:32]


def _process_identity_for_pid(process_id: int) -> tuple[str, str]:
    if process_id <= 0:
        return "", ""
    try:
        import psutil

        proc = psutil.Process(process_id)
        return str(proc.name() or ""), str(proc.exe() or "")
    except Exception:
        return "", ""


def _system_dialog_detected_legacy(focus: dict) -> bool:
    if not _focus_available(focus):
        return False
    title = str(focus.get("title", "") or "").casefold()
    if not title:
        return False
    markers = (
        "session-start",
        "选择应用以打开",
        "choose an app",
        "how do you want to open",
        "open with",
    )
    return any(marker in title for marker in markers)


def _focus_available(value: dict) -> bool:
    return bool(value.get("available", False)) and _safe_int(value.get("hwnd")) > 0


def _snapshot_workspace(workspace: Path) -> dict[str, str]:
    if not workspace.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or _is_ignored_path(path, workspace):
            continue
        relative = path.relative_to(workspace).as_posix()
        snapshot[relative] = _hash_file(path)
    return snapshot


def _is_ignored_path(path: Path, workspace: Path) -> bool:
    try:
        relative = path.relative_to(workspace)
    except ValueError:
        return True
    parts = relative.parts
    if any(part in _IGNORED_DIRS for part in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in _IGNORED_PATH_PREFIXES)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        return f"unreadable:{exc.__class__.__name__}"
    return digest.hexdigest()


def _diff_snapshots(before: dict[str, str], after: dict[str, str]) -> tuple[str, ...]:
    changed = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed.append(key)
    return tuple(changed)


def _merge_changed_files(groups) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                merged.append(item)
                seen.add(item)
    return tuple(merged)


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _dedupe_strings(values) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        selected.append(item)
        seen.add(item)
    return selected


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _load_json_file(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("candidate_report_must_be_object")
    return data


def _select_variants(message: str, selected_names: list[str]) -> tuple[IDECommandArgumentVariant, ...] | None:
    selected = _dedupe_strings(selected_names)
    if not selected:
        return None
    variants = build_argument_variants(message)
    return tuple(variant for variant in variants if variant.name in selected)


if __name__ == "__main__":
    raise SystemExit(main())
