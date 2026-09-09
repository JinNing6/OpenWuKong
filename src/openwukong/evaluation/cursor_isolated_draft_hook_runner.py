# -*- coding: utf-8 -*-
"""Run Cursor draft-hook validation inside an owned isolated profile."""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

from openwukong.connectors.base import ConnectorTarget
from openwukong.connectors.ide_extension import IDEExtensionBridgeClient
from openwukong.control.app_resolution import WindowsAppResolver
from openwukong.control.session_readiness_plan import (
    SessionReadinessPlanOptions,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.evaluation.cursor_draft_hook_probe import ISOLATED_SAFETY_PROFILE
from openwukong.evaluation.cursor_draft_hook_validation import (
    validate_cursor_draft_hook,
)
from openwukong.evaluation.ide_bridge_contract_probe import (
    _capture_focus,
    _foreground_changed,
)


DEFAULT_EXTENSION_DIR = Path(__file__).resolve().parents[3] / "extensions" / "openwukong-vscode"


@dataclasses.dataclass(frozen=True)
class CursorIsolatedDraftHookRunReport:
    output_root: str
    bridge_url: str
    cursor_executable: str = ""
    workspace_path: str = ""
    manifest_path: str = ""
    decision: str = ""
    launch_report: dict = dataclasses.field(default_factory=dict)
    bridge_readiness_report: dict = dataclasses.field(default_factory=dict)
    validation_report: dict = dataclasses.field(default_factory=dict)
    stop_report: dict = dataclasses.field(default_factory=dict)
    cleanup_report: dict = dataclasses.field(default_factory=dict)
    before_launch_focus: dict = dataclasses.field(default_factory=dict)
    after_launch_focus: dict = dataclasses.field(default_factory=dict)
    resolver_report: dict = dataclasses.field(default_factory=dict)
    visible_gui_launch_allowed: bool = False
    error: str = ""

    @property
    def mode(self) -> str:
        return "cursor-isolated-draft-hook-run"

    @property
    def safety_mode(self) -> str:
        return "isolated_cursor_profile_validation"

    @property
    def launch_foreground_changed(self) -> bool:
        return _foreground_changed(self.before_launch_focus, self.after_launch_focus)

    @property
    def control_allowed(self) -> bool:
        return bool(self.validation_report.get("control_allowed", False))

    @property
    def control_attempts(self) -> int:
        return int(self.validation_report.get("control_attempts", 0) or 0)

    @property
    def window_input_attempts(self) -> int:
        return int(self.validation_report.get("window_input_attempts", 0) or 0)

    @property
    def bridge_send_attempts(self) -> int:
        return int(self.validation_report.get("bridge_send_attempts", 0) or 0)

    @property
    def draft_write_attempts(self) -> int:
        return int(self.validation_report.get("draft_write_attempts", 0) or 0)

    @property
    def launch_attempts(self) -> int:
        return int(self.launch_report.get("launch_attempts", 0) or 0)

    @property
    def stop_attempts(self) -> int:
        return int(self.stop_report.get("stop_attempts", 0) or 0)

    @property
    def ok(self) -> bool:
        if self.decision not in {
            "cursor_draft_hook_validated",
            "cursor_draft_hook_dry_run_ready",
        }:
            return False
        return bool(self.validation_report.get("ok", False)) and _stop_report_ok(self.stop_report) and bool(
            self.cleanup_report.get("ok", True)
        )

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
            "draft_write_attempts": self.draft_write_attempts,
            "launch_attempts": self.launch_attempts,
            "stop_attempts": self.stop_attempts,
            "launch_foreground_changed": self.launch_foreground_changed,
            "visible_gui_launch_allowed": bool(self.visible_gui_launch_allowed),
            "bridge_url": self.bridge_url,
            "cursor_executable": self.cursor_executable,
            "workspace_path": self.workspace_path,
            "manifest_path": self.manifest_path,
            "output_root": self.output_root,
            "before_launch_focus": dict(self.before_launch_focus),
            "after_launch_focus": dict(self.after_launch_focus),
            "resolver_report": dict(self.resolver_report),
            "launch_report": dict(self.launch_report),
            "bridge_readiness_report": dict(self.bridge_readiness_report),
            "validation_report": dict(self.validation_report),
            "stop_report": dict(self.stop_report),
            "cleanup_report": dict(self.cleanup_report),
            "error": self.error,
        }


def run_cursor_isolated_draft_hook_validation(
    *,
    output_root: str | Path = "logs/runtime/cursor-isolated-draft-hook",
    cursor_executable: str = "",
    workspace_path: str | Path = "",
    extension_dir: str | Path = DEFAULT_EXTENSION_DIR,
    bridge_host: str = "127.0.0.1",
    bridge_port: int = 0,
    message: str = "OPENWUKONG_CURSOR_ISOLATED_DRAFT_HOOK",
    allow_write: bool = False,
    cleanup_profiles: bool = True,
    resolver: object | None = None,
    focus_observer: object | None = None,
    plan_executor: Callable[..., object] | None = None,
    stop_manifest: Callable[..., object] | None = None,
    bridge_waiter: Callable[..., dict] | None = None,
    validator: Callable[..., object] | None = None,
    request_timeout: float = 5.0,
    bridge_ready_timeout_sec: float = 30.0,
    post_action_observation_delay_sec: float = 0.5,
    allow_visible_gui_launch: bool = False,
) -> CursorIsolatedDraftHookRunReport:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    user_data_dir = root / "user-data"
    extensions_dir = root / "extensions"
    workspace = Path(workspace_path).expanduser().resolve() if workspace_path else root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _ensure_workspace_marker(workspace)
    configured_bridge_port = int(bridge_port)
    bridge_url = (
        ""
        if configured_bridge_port == 0
        else f"http://{bridge_host}:{configured_bridge_port}"
    )

    executable, resolver_report = _resolve_cursor_executable(
        cursor_executable,
        resolver=resolver,
    )
    if not executable:
        return CursorIsolatedDraftHookRunReport(
            output_root=str(root),
            bridge_url=bridge_url,
            workspace_path=str(workspace),
            manifest_path=str(manifest_path),
            decision="cursor_executable_not_resolved",
            resolver_report=resolver_report,
            visible_gui_launch_allowed=bool(allow_visible_gui_launch),
            cleanup_report={"ok": True, "paths": []},
            error=str(resolver_report.get("error", "cursor_executable_not_resolved")),
        )

    before_launch_focus = _capture_focus(focus_observer)
    if not allow_visible_gui_launch:
        return CursorIsolatedDraftHookRunReport(
            output_root=str(root),
            bridge_url=bridge_url,
            cursor_executable=executable,
            workspace_path=str(workspace),
            manifest_path=str(manifest_path),
            decision="cursor_visible_gui_launch_blocked",
            resolver_report=resolver_report,
            before_launch_focus=before_launch_focus,
            after_launch_focus=dict(before_launch_focus),
            visible_gui_launch_allowed=False,
            cleanup_report={"ok": True, "paths": []},
            error="visible_gui_launch_requires_explicit_allow_visible_gui_launch",
        )
    plan = build_session_readiness_plan(
        routes=("ide-extension-connector",),
        options=SessionReadinessPlanOptions(
            ide_executable=executable,
            ide_user_data_dir=str(user_data_dir),
            ide_extensions_dir=str(extensions_dir),
            ide_extension_dir=str(Path(extension_dir).expanduser().resolve()),
            ide_bridge_host=bridge_host,
            ide_bridge_port=configured_bridge_port,
            workspace_root=str(workspace),
        ),
    )

    launch_report: dict = {}
    bridge_readiness_report: dict = {}
    validation_report: dict = {}
    stop_report: dict = {}
    cleanup_report: dict = {"ok": True, "paths": []}
    decision = ""
    error = ""
    after_launch_focus = {}

    try:
        active_executor = plan_executor or execute_session_readiness_plan
        launch_result = active_executor(plan, manifest_path=str(manifest_path))
        launch_report = _to_dict(launch_result)
        launched_bridge_url = _launch_readiness_url(
            launch_report,
            action_id="launch_ide_bridge_isolated",
        )
        if launched_bridge_url:
            bridge_url = launched_bridge_url
        after_launch_focus = _capture_focus(focus_observer)

        if not _launch_report_started(launch_report):
            decision = "cursor_isolated_launch_failed"
            error = _first_report_error(launch_report) or decision
        elif not bridge_url:
            decision = "cursor_isolated_dynamic_bridge_url_missing"
            error = decision
        elif _foreground_changed(before_launch_focus, after_launch_focus):
            decision = "cursor_isolated_launch_changed_foreground"
            error = decision
        else:
            active_waiter = bridge_waiter or wait_for_ide_bridge
            bridge_readiness_report = dict(
                active_waiter(
                    bridge_url=bridge_url,
                    workspace_path=str(workspace),
                    request_timeout=request_timeout,
                    timeout_sec=bridge_ready_timeout_sec,
                )
            )
            if not bridge_readiness_report.get("ok", False):
                decision = "cursor_isolated_bridge_not_ready"
                error = str(bridge_readiness_report.get("error", "") or decision)
            else:
                active_validator = validator or _default_validate_cursor_draft_hook
                validation_report = _to_dict(
                    active_validator(
                        bridge_url=bridge_url,
                        workspace_path=str(workspace),
                        message=message,
                        allow_write=bool(allow_write),
                        safety_profile=ISOLATED_SAFETY_PROFILE if allow_write else "",
                        request_timeout=request_timeout,
                        post_action_observation_delay_sec=post_action_observation_delay_sec,
                    )
                )
                decision = str(
                    validation_report.get("decision", "")
                    or "cursor_validation_missing_decision"
                )
                error = str(validation_report.get("error", ""))
    except Exception as exc:
        decision = "cursor_isolated_runner_failed"
        error = str(exc) or exc.__class__.__name__
    finally:
        if launch_report:
            stop_report = _to_dict(
                (stop_manifest or stop_session_readiness_manifest)(str(manifest_path))
            )
            if cleanup_profiles:
                cleanup_report = _cleanup_owned_dirs(
                    root,
                    (user_data_dir, extensions_dir),
                )

    return CursorIsolatedDraftHookRunReport(
        output_root=str(root),
        bridge_url=bridge_url,
        cursor_executable=executable,
        workspace_path=str(workspace),
        manifest_path=str(manifest_path),
        decision=decision,
        resolver_report=resolver_report,
        launch_report=launch_report,
        bridge_readiness_report=bridge_readiness_report,
        validation_report=validation_report,
        stop_report=stop_report,
        cleanup_report=cleanup_report,
        before_launch_focus=before_launch_focus,
        after_launch_focus=after_launch_focus,
        error=error,
        visible_gui_launch_allowed=bool(allow_visible_gui_launch),
    )


def wait_for_ide_bridge(
    *,
    bridge_url: str,
    workspace_path: str,
    request_timeout: float = 5.0,
    timeout_sec: float = 30.0,
) -> dict:
    client = IDEExtensionBridgeClient(request_timeout=request_timeout)
    target = ConnectorTarget(
        project_name=Path(workspace_path).name if workspace_path else "",
        workspace_path=str(workspace_path or ""),
        workspace_hint=Path(workspace_path).name if workspace_path else "",
        ide_bridge_url=bridge_url,
    )
    started = time.perf_counter()
    attempts = 0
    last_error = ""
    deadline = started + max(0.1, float(timeout_sec or 0.1))
    while time.perf_counter() <= deadline:
        attempts += 1
        try:
            state = client.read_state(bridge_url, target)
            if state.get("ok", False):
                return {
                    "ok": True,
                    "decision": "ide_bridge_ready",
                    "attempts": attempts,
                    "bridge_url": bridge_url,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "metadata": dict(state.get("metadata", {}) or {}),
                }
            last_error = str(state.get("error", "bridge_state_not_ok"))
        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__
        time.sleep(0.5)
    return {
        "ok": False,
        "decision": "ide_bridge_not_ready",
        "attempts": attempts,
        "bridge_url": bridge_url,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "error": last_error,
    }


def _default_validate_cursor_draft_hook(**kwargs):
    return validate_cursor_draft_hook(**kwargs)


def _resolve_cursor_executable(cursor_executable: str, *, resolver: object | None) -> tuple[str, dict]:
    explicit = str(cursor_executable or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return str(path.resolve()), {
                "ok": True,
                "decision": "explicit_cursor_executable",
                "path": str(path.resolve()),
            }
        return "", {
            "ok": False,
            "decision": "explicit_cursor_executable_invalid",
            "path": explicit,
            "error": "cursor_executable_not_file",
        }

    active_resolver = resolver or WindowsAppResolver()
    try:
        raw_report = active_resolver.resolve("cursor")
    except Exception as exc:
        return "", {
            "ok": False,
            "decision": "cursor_resolution_failed",
            "error": str(exc) or exc.__class__.__name__,
        }
    report = _to_dict(raw_report)
    if not report.get("ok", False):
        return "", report
    path = str(report.get("path", "") or "").strip()
    if not path or not Path(path).is_file():
        data = dict(report)
        data["ok"] = False
        data["error"] = "cursor_resolution_missing_executable_path"
        return "", data
    return str(Path(path).resolve()), report


def _ensure_workspace_marker(workspace: Path) -> None:
    marker = workspace / "README.md"
    if not marker.exists():
        marker.write_text("OpenWukong isolated Cursor validation workspace.\n", encoding="utf-8")


def _launch_report_started(report: dict) -> bool:
    return any(
        isinstance(item, dict) and item.get("status") == "started"
        for item in report.get("results", [])
    )


def _first_report_error(report: dict) -> str:
    for item in report.get("results", []):
        if isinstance(item, dict) and item.get("error"):
            return str(item.get("error", ""))
    return str(report.get("error", ""))


def _launch_readiness_url(report: dict, *, action_id: str = "") -> str:
    if not isinstance(report, dict):
        return ""
    fallback_url = ""
    for result in report.get("results", []) or ():
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") != "started":
            continue
        url = str(result.get("readiness_url", "") or "").strip()
        if not url:
            continue
        if action_id and str(result.get("action_id", "") or "") != action_id:
            if not fallback_url:
                fallback_url = url
            continue
        return url
    for launch in report.get("launches", []) or ():
        if not isinstance(launch, dict):
            continue
        url = str(launch.get("readiness_url", "") or "").strip()
        if not url:
            continue
        if action_id and str(launch.get("action_id", "") or "") != action_id:
            if not fallback_url:
                fallback_url = url
            continue
        return url
    return fallback_url


def _cleanup_owned_dirs(root: Path, paths: tuple[Path, ...]) -> dict:
    root_resolved = root.resolve()
    cleaned: list[str] = []
    errors: list[str] = []
    for path in paths:
        try:
            resolved = path.resolve()
            if resolved == root_resolved or not _is_relative_to(resolved, root_resolved):
                errors.append(f"unsafe_cleanup_path:{path}")
                continue
            if resolved.exists():
                shutil.rmtree(resolved)
            cleaned.append(str(resolved))
        except Exception as exc:
            errors.append(f"{path}:{str(exc) or exc.__class__.__name__}")
    return {
        "ok": not errors,
        "paths": cleaned,
        "errors": errors,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _stop_report_ok(report: dict) -> bool:
    if not report:
        return False
    for item in report.get("results", []):
        if isinstance(item, dict) and item.get("status") in {"failed", "rejected"}:
            return False
    return True


def _to_dict(value: object) -> dict:
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if isinstance(value, dict):
        return dict(value)
    return {}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="logs/runtime/cursor-isolated-draft-hook")
    parser.add_argument("--cursor-executable", default="")
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    parser.add_argument("--bridge-port", type=int, default=0)
    parser.add_argument("--message", default="OPENWUKONG_CURSOR_ISOLATED_DRAFT_HOOK")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--allow-visible-gui-launch", action="store_true")
    parser.add_argument("--no-cleanup-profiles", action="store_true")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--bridge-ready-timeout-sec", type=float, default=30.0)
    parser.add_argument("--post-action-observation-delay-sec", type=float, default=0.5)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_cursor_isolated_draft_hook_validation(
        output_root=args.output_root,
        cursor_executable=args.cursor_executable,
        workspace_path=args.workspace_path,
        extension_dir=args.extension_dir,
        bridge_port=args.bridge_port,
        message=args.message,
        allow_write=args.allow_write,
        allow_visible_gui_launch=args.allow_visible_gui_launch,
        cleanup_profiles=not args.no_cleanup_profiles,
        request_timeout=args.request_timeout,
        bridge_ready_timeout_sec=args.bridge_ready_timeout_sec,
        post_action_observation_delay_sec=args.post_action_observation_delay_sec,
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
            "Cursor isolated draft hook run: "
            f"decision={data['decision']} ok={data['ok']} "
            f"launch_foreground_changed={data['launch_foreground_changed']}"
        )
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
