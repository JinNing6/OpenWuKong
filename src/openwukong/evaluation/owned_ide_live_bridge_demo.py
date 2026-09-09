# -*- coding: utf-8 -*-
"""Safe-operation demo for a live owned IDE bridge.

The demo never launches an IDE and never uses foreground input. It only talks to
an already running local IDE bridge, verifies that the bridge is bound to an
owned scratch workspace, then writes a scratch file through the extension's
allowlisted ``openwukong.writeScratch`` command.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.ide_bridge_registry import discover_ide_bridge_urls
from openwukong.control.session_ownership import build_ownership_index
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.control.trajectory import (
    ControlTrajectoryRecorder,
    build_trajectory_artifact,
    extract_trajectory_artifacts,
)
from openwukong.evaluation.ide_bridge_capture import capture_ide_bridge_capabilities
from openwukong.evaluation.owned_ide_safe_operation_demo import DEFAULT_MARKER


REPORT_NAME = "owned_ide_live_bridge_demo.json"
SAFE_WRITE_COMMAND_ID = "openwukong.writeScratch"


@dataclasses.dataclass(frozen=True)
class OwnedIDELiveBridgeDemoReport:
    ok: bool
    decision: str
    output_root: str
    report_path: str
    bridge: dict
    capability_capture: dict
    workspace_binding: dict
    ownership_manifest: dict
    read_state_execution: dict
    write_execution: dict
    readback: dict
    quality_summary: dict
    selected_write_command: str = ""
    trajectory_path: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "owned-ide-live-bridge-demo"

    @property
    def safety_mode(self) -> str:
        return "live_owned_ide_bridge_no_foreground"

    @property
    def control_allowed(self) -> bool:
        return bool(self.ok and self.write_execution.get("control_allowed"))

    @property
    def control_attempts(self) -> int:
        return int(self.read_state_execution.get("control_attempts", 0) or 0) + int(
            self.write_execution.get("control_attempts", 0) or 0
        )

    @property
    def desktop_control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return _nested_counter(self.write_execution, "window_input_attempts")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "desktop_control_attempts": self.desktop_control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "output_root": self.output_root,
            "report_path": self.report_path,
            "trajectory_path": self.trajectory_path,
            "bridge": dict(self.bridge),
            "capability_capture": dict(self.capability_capture),
            "workspace_binding": dict(self.workspace_binding),
            "ownership_manifest": dict(self.ownership_manifest),
            "read_state_execution": dict(self.read_state_execution),
            "write_execution": dict(self.write_execution),
            "readback": dict(self.readback),
            "quality_summary": dict(self.quality_summary),
            "selected_write_command": self.selected_write_command,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_owned_ide_live_bridge_demo(
    *,
    output_root: str | Path = "logs/runtime/owned-ide-live-bridge-demo",
    ide_bridge_url: str = "",
    workspace_path: str | Path = "",
    registry_paths: Iterable[str | Path] = (),
    marker: str = DEFAULT_MARKER,
    request_timeout: float = 5.0,
    settle_seconds: float = 0.05,
) -> OwnedIDELiveBridgeDemoReport:
    started = time.perf_counter()
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / REPORT_NAME
    artifact_root = root / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "ide_session_readiness_manifest.json"
    trajectory_root = root / "control_trajectories"

    decision = "owned_ide_live_bridge_demo_failed"
    error = ""
    capability_data: dict = {}
    workspace_binding: dict = {}
    manifest: dict = {}
    read_state_data: dict = {}
    write_data: dict = {}
    readback_data: dict = {}
    quality: dict = _empty_quality()
    trajectory_path = ""
    selected_write_command = ""

    workspace, workspace_error = _resolve_owned_workspace(root, workspace_path)
    if workspace_error:
        decision = "owned_ide_live_bridge_workspace_rejected"
        error = workspace_error
        bridge_data = {
            "bridge_url": "",
            "workspace_path": str(workspace) if workspace else "",
            "artifact_root": str(artifact_root),
            "discovery_source": "not_started",
        }
        report = _build_report(
            ok=False,
            decision=decision,
            error=error,
            root=root,
            report_path=report_path,
            trajectory_path="",
            bridge=bridge_data,
            capability_capture=capability_data,
            workspace_binding=workspace_binding,
            ownership_manifest=manifest,
            read_state_execution=read_state_data,
            write_execution=write_data,
            readback=readback_data,
            quality_summary=quality,
            selected_write_command=selected_write_command,
            started=started,
        )
        _write_json(report_path, report.to_dict())
        return report

    workspace.mkdir(parents=True, exist_ok=True)
    bridge_url, discovery_source = _select_bridge_url(
        ide_bridge_url=ide_bridge_url,
        workspace_path=workspace,
        registry_paths=registry_paths,
    )
    bridge_data = {
        "bridge_url": bridge_url,
        "workspace_path": str(workspace),
        "artifact_root": str(artifact_root),
        "discovery_source": discovery_source,
    }

    if not bridge_url:
        decision = "owned_ide_live_bridge_unavailable"
        error = "missing_local_ide_bridge_url"
    else:
        capability = capture_ide_bridge_capabilities(
            bridge_url,
            workspace_path=str(workspace),
            request_timeout=request_timeout,
        )
        capability_data = capability.to_dict()
        _write_json(artifact_root / "ide_live_capabilities.json", capability_data)
        workspace_binding = _workspace_binding(capability_data, workspace)
        _write_json(artifact_root / "ide_live_workspace_binding.json", workspace_binding)
        selected_write_command = _select_write_command(capability_data)
        if not capability.ok:
            decision = "owned_ide_live_bridge_capability_failed"
            error = capability.error or "ide_bridge_capability_failed"
        elif not bool(workspace_binding.get("ok", False)):
            decision = "owned_ide_live_bridge_workspace_mismatch"
            error = str(workspace_binding.get("error", "") or "workspace_mismatch")
        elif not selected_write_command:
            decision = "owned_ide_live_bridge_write_command_missing"
            error = "openwukong.writeScratch_not_available"
        else:
            manifest = _ownership_manifest(
                manifest_path=manifest_path,
                bridge_url=bridge_url,
                workspace_path=workspace,
            )
            _write_json(manifest_path, manifest)
            fabric = ControlFabric.with_default_connectors(
                ownership_index=build_ownership_index((manifest_path,)),
                require_owned_session_for_execution=True,
            )
            target = ConnectorTarget(
                process_name="Code.exe",
                window_title="OpenWuKong Live IDE Bridge",
                workspace_path=str(workspace),
                ide_bridge_url=bridge_url,
            )
            read_state = fabric.execute(
                target,
                ControlIntent(
                    action="read_state",
                    text="IDE STATE",
                    preferred_route_id="ide-extension-connector",
                ),
                allow_control=True,
                trajectory_root=root / "fabric_trajectories",
                trajectory_metadata={"scenario": "owned-ide-live-read-state"},
            )
            read_state_data = read_state.to_dict()
            time.sleep(max(0.0, float(settle_seconds or 0.0)))
            write = fabric.execute(
                target,
                ControlIntent(
                    action="send_message",
                    text=_write_command_text(selected_write_command, marker),
                    preferred_route_id="ide-extension-connector",
                    side_effect_policy=build_side_effect_policy(
                        allowed_effect_ids=("local_draft.write",)
                    ),
                ),
                allow_control=True,
                trajectory_root=root / "fabric_trajectories",
                trajectory_metadata={"scenario": "owned-ide-live-write-scratch"},
            )
            write_data = write.to_dict()
            readback_data = _write_readback_summary(
                artifact_root,
                marker=marker,
                workspace_path=workspace,
                write_execution=write_data,
            )
            quality = _quality_summary(
                capability_data=capability_data,
                workspace_binding=workspace_binding,
                read_state=read_state_data,
                write=write_data,
                readback=readback_data,
                marker=marker,
                selected_write_command=selected_write_command,
            )
            if int(quality["failed"]) == 0:
                decision = "owned_ide_live_bridge_demo_verified"
            else:
                error = ";".join(quality["failed_checks"]) or "owned_ide_live_quality_failed"

    ok = decision == "owned_ide_live_bridge_demo_verified"
    recorder = ControlTrajectoryRecorder(
        trajectory_root,
        scenario="owned-ide-live-bridge-demo",
        target_id=str(workspace),
        metadata={
            "bridge_url": bridge_url,
            "marker": str(marker or ""),
            "manifest_path": str(manifest_path),
        },
    )
    recorder.record_step(
        phase="capability_capture",
        action="capture_live_ide_bridge_capabilities",
        report=capability_data,
        artifacts=_existing_artifacts(
            (artifact_root / "ide_live_capabilities.json", "ide_capability_capture", "application/json"),
        ),
    )
    recorder.record_step(
        phase="workspace_binding",
        action="verify_owned_workspace_binding",
        report=workspace_binding,
        artifacts=_existing_artifacts(
            (artifact_root / "ide_live_workspace_binding.json", "ide_workspace_binding", "application/json"),
        ),
    )
    if manifest:
        recorder.record_step(
            phase="ownership",
            action="write_owned_ide_manifest",
            report=manifest,
            artifacts=_existing_artifacts(
                (manifest_path, "ide_session_readiness_manifest", "application/json"),
            ),
        )
    if read_state_data:
        recorder.record_step(
            phase="read_state",
            action="read_owned_live_ide_state",
            report=read_state_data,
            artifacts=extract_trajectory_artifacts(read_state_data),
        )
    if write_data:
        recorder.record_step(
            phase="write_scratch",
            action="write_owned_live_ide_scratch",
            report=write_data,
            artifacts=extract_trajectory_artifacts(write_data),
        )
    trajectory_path = str(recorder.manifest_path)

    report = _build_report(
        ok=ok,
        decision=decision,
        error="" if ok else error,
        root=root,
        report_path=report_path,
        trajectory_path=trajectory_path,
        bridge=bridge_data,
        capability_capture=capability_data,
        workspace_binding=workspace_binding,
        ownership_manifest=manifest,
        read_state_execution=read_state_data,
        write_execution=write_data,
        readback=readback_data,
        quality_summary=quality,
        selected_write_command=selected_write_command,
        started=started,
    )
    _write_json(report_path, report.to_dict())
    recorder.record_step(
        phase="final_report",
        action="write_live_ide_demo_report",
        report=report,
        artifacts=_existing_artifacts(
            (report_path, "owned_ide_live_demo_report", "application/json"),
        ),
    )
    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a live owned IDE bridge safe-operation demo."
    )
    parser.add_argument("--output-root", default="logs/runtime/owned-ide-live-bridge-demo")
    parser.add_argument("--ide-bridge-url", default="")
    parser.add_argument("--workspace-path", default="")
    parser.add_argument(
        "--ide-bridge-registry",
        action="append",
        default=[],
        help="Optional IDE bridge registry file or directory to scan.",
    )
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--settle-seconds", type=float, default=0.05)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_owned_ide_live_bridge_demo(
        output_root=args.output_root,
        ide_bridge_url=args.ide_bridge_url,
        workspace_path=args.workspace_path,
        registry_paths=tuple(args.ide_bridge_registry or ()),
        marker=args.marker,
        request_timeout=float(args.request_timeout or 0.0),
        settle_seconds=float(args.settle_seconds or 0.0),
    )
    data = report.to_dict()
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Owned IDE live bridge demo: "
            f"ok={data['ok']} "
            f"decision={data['decision']} "
            f"control_attempts={data['control_attempts']} "
            f"window_input_attempts={data['window_input_attempts']} "
            f"trajectory={data['trajectory_path']}"
        )
    return 0 if report.ok else 1


def _build_report(
    *,
    ok: bool,
    decision: str,
    error: str,
    root: Path,
    report_path: Path,
    trajectory_path: str,
    bridge: dict,
    capability_capture: dict,
    workspace_binding: dict,
    ownership_manifest: dict,
    read_state_execution: dict,
    write_execution: dict,
    readback: dict,
    quality_summary: dict,
    selected_write_command: str,
    started: float,
) -> OwnedIDELiveBridgeDemoReport:
    return OwnedIDELiveBridgeDemoReport(
        ok=ok,
        decision=decision,
        output_root=str(root),
        report_path=str(report_path),
        trajectory_path=trajectory_path,
        bridge=bridge,
        capability_capture=capability_capture,
        workspace_binding=workspace_binding,
        ownership_manifest=ownership_manifest,
        read_state_execution=read_state_execution,
        write_execution=write_execution,
        readback=readback,
        quality_summary=quality_summary,
        selected_write_command=selected_write_command,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _resolve_owned_workspace(root: Path, workspace_path: str | Path) -> tuple[Path | None, str]:
    text = str(workspace_path or "").strip()
    path = Path(text).expanduser() if text else root / "owned_ide_live_workspace"
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            return resolved, "workspace_path_must_be_inside_output_root"
        return resolved, ""
    except (OSError, ValueError) as exc:
        return None, f"invalid_workspace_path:{exc}"


def _select_bridge_url(
    *,
    ide_bridge_url: str,
    workspace_path: Path,
    registry_paths: Iterable[str | Path],
) -> tuple[str, str]:
    target = ConnectorTarget(
        process_name="Code.exe",
        window_title="OpenWuKong Live IDE Bridge",
        workspace_path=str(workspace_path),
    )
    urls = discover_ide_bridge_urls(
        explicit_urls=(ide_bridge_url,) if str(ide_bridge_url or "").strip() else (),
        target=target,
        registry_paths=tuple(registry_paths or ()),
    )
    if not urls:
        return "", "none"
    explicit = str(ide_bridge_url or "").strip().rstrip("/")
    if explicit and urls[0].rstrip("/") == explicit:
        return urls[0], "explicit"
    return urls[0], "registry"


def _select_write_command(capability_data: dict) -> str:
    commands = {
        str(command or "").strip()
        for command in capability_data.get("commands", []) or []
        if str(command or "").strip()
    }
    return SAFE_WRITE_COMMAND_ID if SAFE_WRITE_COMMAND_ID in commands else ""


def _workspace_binding(capability_data: dict, workspace_path: Path) -> dict:
    metadata = dict(capability_data.get("metadata", {}) or {})
    expected = _norm_path(workspace_path)
    workspace_folders = metadata.get("workspaceFolders", [])
    first_workspace = ""
    folder_paths = []
    if isinstance(workspace_folders, list):
        for folder in workspace_folders:
            if not isinstance(folder, dict):
                continue
            value = str(folder.get("fsPath", "") or "").strip()
            if value:
                folder_paths.append(value)
        if folder_paths:
            first_workspace = folder_paths[0]
    fallback_workspace = str(metadata.get("workspace_path", "") or "").strip()
    observed = first_workspace or fallback_workspace
    matched = bool(observed and _norm_path(observed) == expected)
    return {
        "ok": matched,
        "expected_workspace_path": str(workspace_path),
        "observed_first_workspace_path": observed,
        "workspace_folder_paths": folder_paths,
        "metadata_workspace_path": fallback_workspace,
        "error": "" if matched else "bridge_first_workspace_not_owned_scratch",
    }


def _ownership_manifest(*, manifest_path: Path, bridge_url: str, workspace_path: Path) -> dict:
    return {
        "mode": "session-readiness-execution",
        "safety_mode": "isolated_helper_launch",
        "control_allowed": False,
        "control_attempts": 0,
        "launch_attempts": 0,
        "manifest_path": str(manifest_path),
        "results": [
            {
                "route_id": "ide-extension-connector",
                "connector_id": "ide-extension",
                "action_id": "owned_ide_live_bridge",
                "status": "workspace_bound",
                "readiness_url": bridge_url,
                "workspace_root": str(workspace_path),
                "pid": 0,
            }
        ],
        "launches": [],
    }


def _write_command_text(command_id: str, marker: str) -> str:
    return f"IDE COMMAND {command_id}\n\n{json.dumps([marker], ensure_ascii=False)}"


def _write_readback_summary(
    root: Path,
    *,
    marker: str,
    workspace_path: Path,
    write_execution: dict,
) -> dict:
    readback_text = str(_find_first(write_execution, "readback_text") or "")
    scratch_path = str(_find_first(write_execution, "scratch_path") or "")
    readback_verified = _find_first(write_execution, "readback_verified")
    if readback_verified is None:
        readback_verified = bool(readback_text == marker)
    if not scratch_path:
        scratch_path = str(workspace_path / ".openwukong" / "openwukong-owned-scratch.txt")
    data = {
        "ok": bool(readback_verified) and readback_text == marker,
        "marker": marker,
        "readback_text": readback_text,
        "scratch_path": scratch_path,
        "readback_verified": bool(readback_verified),
        "window_input_attempts": _nested_counter(write_execution, "window_input_attempts"),
        "keyboard_input_attempts": _nested_counter(write_execution, "keyboard_input_attempts"),
        "clipboard_write_attempts": _nested_counter(write_execution, "clipboard_write_attempts"),
    }
    _write_json(root / "owned_ide_live_readback_summary.json", data)
    return data


def _quality_summary(
    *,
    capability_data: dict,
    workspace_binding: dict,
    read_state: dict,
    write: dict,
    readback: dict,
    marker: str,
    selected_write_command: str,
) -> dict:
    checks = {
        "capability_capture_ok": bool(capability_data.get("ok")),
        "workspace_binding_ok": bool(workspace_binding.get("ok")),
        "safe_write_command_selected": selected_write_command == SAFE_WRITE_COMMAND_ID,
        "read_state_ok": bool(read_state.get("ok")),
        "write_ok": bool(write.get("ok")),
        "readback_verified": bool(readback.get("readback_verified")),
        "marker_readback": str(readback.get("readback_text", "") or "") == marker,
        "no_desktop_input": _nested_counter(write, "window_input_attempts") == 0,
        "no_keyboard_input": _nested_counter(write, "keyboard_input_attempts") == 0,
        "no_clipboard_write": _nested_counter(write, "clipboard_write_attempts") == 0,
    }
    failed = [key for key, value in checks.items() if not value]
    return {
        "passed": sum(1 for value in checks.values() if value),
        "failed": len(failed),
        "checks": checks,
        "failed_checks": failed,
    }


def _empty_quality() -> dict:
    return {
        "passed": 0,
        "failed": 0,
        "checks": {},
        "failed_checks": [],
    }


def _nested_counter(data: dict, key: str) -> int:
    value = _find_first(data, key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _find_first(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        if key in value:
            return value.get(key)
        for item in value.values():
            found = _find_first(item, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first(item, key)
            if found is not None:
                return found
    return None


def _existing_artifacts(*items: tuple[Path, str, str]):
    artifacts = []
    for path, role, media_type in items:
        if Path(path).is_file():
            artifacts.append(
                build_trajectory_artifact(
                    path,
                    role=role,
                    media_type=media_type,
                    compute_hash=True,
                )
            )
    return tuple(artifacts)


def _norm_path(value: str | Path) -> str:
    try:
        return str(Path(value).expanduser().resolve()).casefold()
    except (OSError, ValueError):
        return str(value or "").strip().casefold()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


if __name__ == "__main__":
    raise SystemExit(main())
