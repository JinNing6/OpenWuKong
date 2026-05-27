# -*- coding: utf-8 -*-
"""Read-only IDE bridge capability capture.

This module only calls `/v1/ide/capabilities`. It does not execute IDE
commands, send chat messages, click UI, type input, or inspect UIA trees.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Optional

from openwukong.connectors import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient


@dataclasses.dataclass(frozen=True)
class IDEBridgeCapabilityCaptureReport:
    bridge_url: str
    ok: bool
    metadata: dict
    commands: tuple[str, ...]
    chat_adapters: tuple[dict, ...]
    adapter_mapping: dict
    response: dict
    error: str = ""
    request_path: str = "/v1/ide/capabilities"
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "ide-bridge-capability-capture"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "bridge_url": self.bridge_url,
            "request_path": self.request_path,
            "ok": self.ok,
            "error": self.error,
            "metadata": dict(self.metadata),
            "command_count": len(self.commands),
            "commands": list(self.commands),
            "chat_adapters": [dict(adapter) for adapter in self.chat_adapters],
            "adapter_mapping": self.adapter_mapping,
            "response": dict(self.response),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def capture_ide_bridge_capabilities(
    bridge_url: str,
    *,
    workspace_path: str = "",
    request_timeout: float = 5.0,
    bridge_client: Optional[IDEExtensionBridgeClient] = None,
) -> IDEBridgeCapabilityCaptureReport:
    started = time.perf_counter()
    client = bridge_client or IDEExtensionBridgeClient(request_timeout=request_timeout)
    target = ConnectorTarget(
        process_name="code.exe",
        workspace_path=workspace_path,
        ide_bridge_url=bridge_url,
    )
    try:
        data = client.read_capabilities(bridge_url, target)
    except Exception as exc:
        return IDEBridgeCapabilityCaptureReport(
            bridge_url=bridge_url,
            ok=False,
            metadata={},
            commands=(),
            chat_adapters=(),
            adapter_mapping={},
            response={},
            error=str(exc),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    metadata = data.get("metadata", {})
    commands = data.get("commands", [])
    chat_adapters = data.get("chat_adapters", [])
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(commands, list):
        commands = []
    if not isinstance(chat_adapters, list):
        chat_adapters = []

    normalized_adapters = tuple(
        _normalize_adapter(adapter)
        for adapter in chat_adapters
        if isinstance(adapter, dict)
    )
    return IDEBridgeCapabilityCaptureReport(
        bridge_url=bridge_url,
        ok=bool(data.get("ok", False)),
        metadata=metadata,
        commands=tuple(str(command) for command in commands if isinstance(command, str)),
        chat_adapters=normalized_adapters,
        adapter_mapping=build_adapter_mapping(normalized_adapters),
        response=data,
        error="" if data.get("ok", False) else str(data.get("error", "bridge_capabilities_failed") or ""),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def build_adapter_mapping(chat_adapters) -> dict:
    mapping = {}
    for adapter in chat_adapters:
        if not isinstance(adapter, dict):
            continue
        adapter_id = str(adapter.get("adapter_id", "") or "").strip()
        if not adapter_id:
            continue
        available = bool(adapter.get("available", False))
        command_id = str(adapter.get("command_id", "") or "").strip()
        available_candidates = _string_list(adapter.get("available_candidates", []))
        command_candidates = _stable_unique(
            [command_id]
            + _string_list(adapter.get("command_candidates", []))
            + available_candidates
        )
        mapping[adapter_id] = {
            "label": str(adapter.get("label", "") or adapter_id),
            "commandId": command_id if available and command_id else "",
            "commandCandidates": command_candidates,
            "available": available,
            "availableCandidates": available_candidates,
        }
    return mapping


def _normalize_adapter(adapter: dict) -> dict:
    return {
        "adapter_id": str(adapter.get("adapter_id", "") or ""),
        "label": str(adapter.get("label", "") or ""),
        "command_id": str(adapter.get("command_id", "") or ""),
        "command_candidates": _string_list(adapter.get("command_candidates", [])),
        "available": bool(adapter.get("available", False)),
        "available_candidates": _string_list(adapter.get("available_candidates", [])),
    }


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _stable_unique(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture read-only IDE bridge capabilities from /v1/ide/capabilities."
    )
    parser.add_argument("bridge_url", help="IDE bridge URL, for example http://127.0.0.1:8787")
    parser.add_argument("--workspace-path", default="", help="Optional workspace path to include in the target payload.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP request timeout in seconds.")
    parser.add_argument("--output", default="", help="Optional path to write the JSON report.")
    parser.add_argument("--json", action="store_true", help="Print the JSON report.")
    args = parser.parse_args(argv)

    report = capture_ide_bridge_capabilities(
        args.bridge_url,
        workspace_path=args.workspace_path,
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

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        status = "ok" if report.ok else "failed"
        print(
            f"IDE bridge capability capture {status}: "
            f"commands={len(report.commands)} adapters={len(report.chat_adapters)}"
        )
        if report.error:
            print(f"error={report.error}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
