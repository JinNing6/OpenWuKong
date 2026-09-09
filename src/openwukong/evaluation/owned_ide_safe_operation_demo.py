# -*- coding: utf-8 -*-
"""End-to-end safe operation demo for an owned hermetic IDE bridge."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_ownership import build_ownership_index
from openwukong.control.side_effects import build_side_effect_policy
from openwukong.control.trajectory import (
    ControlTrajectoryRecorder,
    build_trajectory_artifact,
    extract_trajectory_artifacts,
)


DEFAULT_MARKER = "OPENWUKONG_OWNED_IDE_DEMO"


@dataclasses.dataclass(frozen=True)
class HermeticIDEBridgeReport:
    bridge_url: str
    workspace_path: str
    artifact_root: str
    ok: bool = True
    error: str = ""

    @property
    def mode(self) -> str:
        return "owned-ide-hermetic-bridge"

    @property
    def safety_mode(self) -> str:
        return "local_loopback_hermetic_bridge"

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
            "ok": self.ok,
            "bridge_url": self.bridge_url,
            "workspace_path": self.workspace_path,
            "artifact_root": self.artifact_root,
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class OwnedIDESafeOperationDemoReport:
    ok: bool
    decision: str
    output_root: str
    report_path: str
    bridge: dict
    ownership_manifest: dict
    read_state_execution: dict
    write_execution: dict
    readback: dict
    quality_summary: dict
    trajectory_path: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "owned-ide-safe-operation-demo"

    @property
    def safety_mode(self) -> str:
        return "hermetic_owned_ide_bridge"

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
            "ownership_manifest": dict(self.ownership_manifest),
            "read_state_execution": dict(self.read_state_execution),
            "write_execution": dict(self.write_execution),
            "readback": dict(self.readback),
            "quality_summary": dict(self.quality_summary),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class HermeticIDEBridgeFixture:
    """Local JSON bridge that simulates a deterministic IDE extension."""

    def __init__(self, *, workspace_path: str | Path, artifact_root: str | Path, marker: str):
        self.workspace_path = Path(workspace_path).resolve()
        self.artifact_root = Path(artifact_root).resolve()
        self.marker = str(marker or DEFAULT_MARKER)
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _handler(self),
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="openwukong-owned-ide-hermetic-bridge",
            daemon=True,
        )
        self._conversation: list[str] = []
        self.request_count = 0

    @property
    def bridge_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> HermeticIDEBridgeReport:
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        return HermeticIDEBridgeReport(
            bridge_url=self.bridge_url,
            workspace_path=str(self.workspace_path),
            artifact_root=str(self.artifact_root),
        )

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def handle(self, path: str, payload: dict) -> tuple[int, dict]:
        self.request_count += 1
        if path == "/v1/ide/capabilities":
            return 200, self._capabilities()
        if path == "/v1/ide/state":
            return 200, self._state()
        if path == "/v1/ide/read":
            return 200, {
                "ok": True,
                "conversation": "\n".join(self._conversation[-20:]),
                "metadata": self._metadata(),
            }
        if path == "/v1/ide/send":
            return 200, self._write_scratch(str(payload.get("message", "") or ""))
        if path == "/v1/ide/command":
            command_id = str(payload.get("command_id", "") or "")
            if command_id == "openwukong.readState":
                return 200, self._state()
            if command_id == "openwukong.writeScratch":
                args = payload.get("arguments", []) or []
                message = str(args[0] if args else self.marker)
                return 200, self._write_scratch(message)
            return 200, {
                "ok": False,
                "error": "unsupported_hermetic_ide_command",
                "metadata": self._metadata(),
            }
        return 404, {"ok": False, "error": "unknown_ide_bridge_endpoint"}

    def _capabilities(self) -> dict:
        return {
            "ok": True,
            "metadata": self._metadata(),
            "commands": [
                "openwukong.readState",
                "openwukong.writeScratch",
            ],
            "chat_adapters": [
                {
                    "adapter_id": "openwukong",
                    "label": "OpenWuKong Hermetic Adapter",
                    "command_id": "openwukong.writeScratch",
                    "available": True,
                }
            ],
        }

    def _state(self) -> dict:
        state_path = self.artifact_root / "ide_state_snapshot.json"
        data = {
            "ok": True,
            "metadata": self._metadata(),
            "diagnostics": [],
            "workspace_path": str(self.workspace_path),
            "scratch_exists": (self.workspace_path / "openwukong-owned-scratch.txt").is_file(),
            "state_path": str(state_path),
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "foreground_focus_stable": True,
        }
        _write_json(state_path, data)
        return data

    def _write_scratch(self, message: str) -> dict:
        text = message.strip() or self.marker
        scratch_path = self.workspace_path / "openwukong-owned-scratch.txt"
        scratch_path.write_text(text, encoding="utf-8")
        readback_text = scratch_path.read_text(encoding="utf-8")
        readback_path = self.artifact_root / "ide_scratch_readback.json"
        data = {
            "ok": readback_text == text,
            "action_key": f"owned-ide-write-{self.request_count}",
            "conversation": f"OpenWuKong hermetic IDE scratch readback: {readback_text}",
            "metadata": {
                **self._metadata(),
                "command_id": "openwukong.writeScratch",
            },
            "readback_text": readback_text,
            "scratch_path": str(scratch_path),
            "readback_path": str(readback_path),
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "foreground_focus_stable": True,
            "error": "" if readback_text == text else "scratch_readback_mismatch",
        }
        self._conversation.append(data["conversation"])
        _write_json(readback_path, data)
        return data

    def _metadata(self) -> dict:
        return {
            "ide_name": "OpenWuKong Hermetic IDE",
            "workspace_path": str(self.workspace_path),
            "bridge_url": self.bridge_url,
            "owned": True,
        }


def run_owned_ide_safe_operation_demo(
    *,
    output_root: str | Path = "logs/runtime/owned-ide-safe-operation-demo",
    marker: str = DEFAULT_MARKER,
    settle_seconds: float = 0.05,
) -> OwnedIDESafeOperationDemoReport:
    started = time.perf_counter()
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "owned_ide_safe_operation_demo.json"
    artifact_root = root / "artifacts"
    workspace_path = root / "owned_ide_workspace"
    manifest_path = root / "ide_session_readiness_manifest.json"
    trajectory_root = root / "control_trajectories"

    bridge = HermeticIDEBridgeFixture(
        workspace_path=workspace_path,
        artifact_root=artifact_root,
        marker=marker,
    )
    bridge_report = bridge.start()
    bridge_data = bridge_report.to_dict()
    read_state_data: dict = {}
    write_data: dict = {}
    readback_data: dict = {}
    quality: dict = {}
    error = ""
    decision = "owned_ide_demo_failed"
    trajectory_path = ""

    try:
        manifest = _ownership_manifest(
            manifest_path=manifest_path,
            bridge_url=bridge.bridge_url,
            workspace_path=workspace_path,
        )
        _write_json(manifest_path, manifest)
        fabric = ControlFabric.with_default_connectors(
            ownership_index=build_ownership_index((manifest_path,)),
            require_owned_session_for_execution=True,
        )
        target = ConnectorTarget(
            process_name="Code.exe",
            window_title="OpenWuKong Hermetic IDE",
            workspace_path=str(workspace_path),
            ide_bridge_url=bridge.bridge_url,
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
            trajectory_metadata={"scenario": "owned-ide-read-state"},
        )
        read_state_data = read_state.to_dict()
        time.sleep(max(0.0, float(settle_seconds or 0.0)))
        write = fabric.execute(
            target,
            ControlIntent(
                action="send_message",
                text=marker,
                preferred_route_id="ide-extension-connector",
                side_effect_policy=build_side_effect_policy(
                    allowed_effect_ids=("local_draft.write",)
                ),
            ),
            allow_control=True,
            trajectory_root=root / "fabric_trajectories",
            trajectory_metadata={"scenario": "owned-ide-write-scratch"},
        )
        write_data = write.to_dict()
        readback_data = _write_readback_summary(artifact_root, marker, workspace_path)
        quality = _quality_summary(read_state_data, write_data, readback_data, marker)
        if int(quality["failed"]) == 0:
            decision = "owned_ide_demo_verified"
        else:
            error = ";".join(quality["failed_checks"]) or "owned_ide_quality_failed"
    finally:
        bridge.stop()

    ok = decision == "owned_ide_demo_verified"
    recorder = ControlTrajectoryRecorder(
        trajectory_root,
        scenario="owned-ide-safe-operation-demo",
        target_id=str(workspace_path),
        metadata={
            "bridge_url": bridge.bridge_url,
            "marker": str(marker or ""),
            "manifest_path": str(manifest_path),
        },
    )
    recorder.record_step(
        phase="bridge_fixture",
        action="serve_hermetic_ide_bridge",
        report=bridge_data,
    )
    recorder.record_step(
        phase="ownership",
        action="write_owned_ide_manifest",
        report=_load_json(manifest_path),
        artifacts=_existing_artifacts(
            (manifest_path, "ide_session_readiness_manifest", "application/json"),
        ),
    )
    recorder.record_step(
        phase="read_state",
        action="read_owned_ide_state",
        report=read_state_data,
        artifacts=extract_trajectory_artifacts(read_state_data),
    )
    recorder.record_step(
        phase="write_scratch",
        action="write_owned_ide_scratch",
        report=write_data,
        artifacts=extract_trajectory_artifacts(write_data),
    )
    trajectory_path = str(recorder.manifest_path)

    report = OwnedIDESafeOperationDemoReport(
        ok=ok,
        decision=decision,
        output_root=str(root),
        report_path=str(report_path),
        trajectory_path=trajectory_path,
        bridge=bridge_data,
        ownership_manifest=_load_json(manifest_path),
        read_state_execution=read_state_data,
        write_execution=write_data,
        readback=readback_data,
        quality_summary=quality,
        error="" if ok else error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    _write_json(report_path, report.to_dict())
    recorder.record_step(
        phase="final_report",
        action="write_demo_report",
        report=report,
        artifacts=_existing_artifacts(
            (report_path, "owned_ide_demo_report", "application/json"),
        ),
    )
    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a hermetic owned IDE bridge safe-operation demo."
    )
    parser.add_argument("--output-root", default="logs/runtime/owned-ide-safe-operation-demo")
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    parser.add_argument("--settle-seconds", type=float, default=0.05)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_owned_ide_safe_operation_demo(
        output_root=args.output_root,
        marker=args.marker,
        settle_seconds=float(args.settle_seconds or 0.0),
    )
    data = report.to_dict()
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Owned IDE safe operation demo: "
            f"ok={data['ok']} "
            f"decision={data['decision']} "
            f"control_attempts={data['control_attempts']} "
            f"window_input_attempts={data['window_input_attempts']} "
            f"trajectory={data['trajectory_path']}"
        )
    return 0 if report.ok else 1


def _handler(fixture: HermeticIDEBridgeFixture):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self._read_payload()
            status, response = fixture.handle(self.path, payload)
            self._send_json(status, response)

        def log_message(self, format, *args):
            return

        def _read_payload(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(max(0, length)) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                return {}
            return dict(data) if isinstance(data, dict) else {}

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


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
                "action_id": "hermetic_ide_bridge_fixture",
                "status": "workspace_bound",
                "readiness_url": bridge_url,
                "workspace_root": str(workspace_path),
                "pid": 0,
            }
        ],
        "launches": [],
    }


def _write_readback_summary(root: Path, marker: str, workspace_path: Path) -> dict:
    scratch_path = workspace_path / "openwukong-owned-scratch.txt"
    text = scratch_path.read_text(encoding="utf-8") if scratch_path.is_file() else ""
    data = {
        "ok": text == marker,
        "marker": marker,
        "readback_text": text,
        "scratch_path": str(scratch_path),
        "readback_verified": text == marker,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
    }
    _write_json(root / "owned_ide_readback_summary.json", data)
    return data


def _quality_summary(read_state: dict, write: dict, readback: dict, marker: str) -> dict:
    checks = {
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


def _nested_counter(data: dict, key: str) -> int:
    values = []
    if isinstance(data, dict):
        values.append(data.get(key))
        payload = data.get("payload")
        if isinstance(payload, dict):
            values.append(payload.get(key))
            response = payload.get("response")
            if isinstance(response, dict):
                values.append(response.get(key))
    for value in values:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


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


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


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
