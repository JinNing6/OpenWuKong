# -*- coding: utf-8 -*-
"""Probe IDE command argument contracts through the extension bridge.

Unlike the read-only capability capture, this module can execute IDE commands.
It is intended for isolated sacrificial workspaces and temporary IDE profiles.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import time
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
    port: int = 8787,
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


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe IDE bridge command argument contracts in an isolated workspace."
    )
    parser.add_argument("bridge_url", help="IDE bridge URL, for example http://127.0.0.1:8787")
    parser.add_argument("--workspace-path", default=os.getcwd(), help="Sacrificial workspace path.")
    parser.add_argument("--candidate-report", default="", help="Adapter candidate JSON report.")
    parser.add_argument("--adapter-id", default="cursor", help="Adapter id to select from the candidate report.")
    parser.add_argument("--command-id", action="append", default=[], help="Explicit command id to probe. Repeatable.")
    parser.add_argument("--max-commands", type=int, default=5, help="Maximum candidate commands to probe.")
    parser.add_argument("--message", default="OPENWUKONG_PROBE_NO_EDIT", help="Probe message.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP request timeout in seconds.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--settings-output", default="", help="Optional VS Code/Cursor settings JSON path.")
    parser.add_argument("--settings-host", default="127.0.0.1", help="Bridge host to write into settings output.")
    parser.add_argument("--settings-port", type=int, default=8787, help="Bridge port to write into settings output.")
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

    report = probe_ide_command_contracts(
        args.bridge_url,
        workspace_path=args.workspace_path,
        command_ids=command_ids,
        adapter_id=args.adapter_id,
        message=args.message,
        request_timeout=args.timeout,
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
            )
        )

    accepted = [attempt for attempt in attempts if attempt.ok]
    safe_accepted = [attempt for attempt in accepted if not attempt.workspace_changed]
    workspace_changed = any(attempt.workspace_changed for attempt in attempts)
    changed_files = _merge_changed_files(attempt.changed_files for attempt in attempts)

    if workspace_changed and accepted:
        status = "mutating"
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

    object_message_safe = any(
        attempt.variant == "object_message" and attempt.ok and not attempt.workspace_changed
        for attempt in attempts
    )

    return IDECommandContractProbeResult(
        command_id=command_id,
        status=status,
        accepted_variant=accepted_variant,
        accepted_variants=tuple(attempt.variant for attempt in accepted),
        workspace_changed=workspace_changed,
        changed_files=changed_files,
        recommended_adapter=status == "callable" and object_message_safe,
        attempts=tuple(attempts),
    )


def _probe_single_variant(
    client: IDEExtensionBridgeClient,
    bridge_url: str,
    target: ConnectorTarget,
    workspace: Path,
    command_id: str,
    variant: IDECommandArgumentVariant,
) -> IDECommandVariantProbeResult:
    before_state = _try_read_state(client, bridge_url, target)
    before_snapshot = _snapshot_workspace(workspace)
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
    after_snapshot = _snapshot_workspace(workspace)
    after_state = _try_read_state(client, bridge_url, target)
    changed_files = _diff_snapshots(before_snapshot, after_snapshot)

    return IDECommandVariantProbeResult(
        variant=variant.name,
        arguments=list(variant.arguments),
        ok=ok,
        error=error,
        workspace_changed=bool(changed_files),
        changed_files=changed_files,
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
        object_attempt = next(
            (
                attempt
                for attempt in result.attempts
                if attempt.variant == "object_message" and attempt.ok and not attempt.workspace_changed
            ),
            None,
        )
        if result.recommended_adapter and object_attempt is not None:
            return {
                adapter_id: {
                    "label": adapter_id,
                    "commandId": result.command_id,
                    "commandCandidates": [result.command_id],
                    "available": True,
                    "validation": {
                        "status": result.status,
                        "acceptedVariant": object_attempt.variant,
                        "workspaceChanged": False,
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
                "controlAttempts": sum(len(result.attempts) for result in results),
            },
        }
    }


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
    return any(part in _IGNORED_DIRS for part in relative.parts)


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


def _load_json_file(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("candidate_report_must_be_object")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
