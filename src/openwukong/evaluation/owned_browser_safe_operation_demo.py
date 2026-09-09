# -*- coding: utf-8 -*-
"""End-to-end safe operation demo for an owned isolated browser."""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from openwukong.control.fabric import ControlFabric
from openwukong.control.session_ownership import build_ownership_index
from openwukong.control.session_readiness_plan import (
    SessionReadinessLauncher,
    SessionReadinessPlanOptions,
    SessionReadinessTerminator,
    build_session_readiness_plan,
    execute_session_readiness_plan,
    stop_session_readiness_manifest,
)
from openwukong.control.trajectory import (
    ControlTrajectoryRecorder,
    build_trajectory_artifact,
)
from openwukong.evaluation.control_fabric_browser_workflow import (
    BrowserWorkflowExpectations,
    BrowserWorkflowStep,
    run_control_fabric_browser_workflow,
)


DEFAULT_MARKER = "OPENWUKONG_OWNED_BROWSER_DEMO"


@dataclasses.dataclass(frozen=True)
class ControlledPageServerReport:
    url: str
    marker: str
    host: str = "127.0.0.1"
    port: int = 0
    ok: bool = True
    error: str = ""

    @property
    def mode(self) -> str:
        return "owned-browser-controlled-page-server"

    @property
    def safety_mode(self) -> str:
        return "local_loopback_controlled_page"

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
            "url": self.url,
            "marker": self.marker,
            "host": self.host,
            "port": self.port,
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class OwnedBrowserSafeOperationDemoReport:
    ok: bool
    decision: str
    output_root: str
    report_path: str
    controlled_page: dict
    readiness_plan: dict
    readiness_execution: dict
    browser_workflow: dict
    readiness_stop: dict
    profile_cleanup: dict
    trajectory_path: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "owned-browser-safe-operation-demo"

    @property
    def safety_mode(self) -> str:
        return "isolated_owned_browser_devtools"

    @property
    def control_allowed(self) -> bool:
        return bool(self.ok and self.browser_workflow.get("control_allowed"))

    @property
    def control_attempts(self) -> int:
        return int(self.browser_workflow.get("control_attempts", 0) or 0)

    @property
    def desktop_control_allowed(self) -> bool:
        return False

    @property
    def desktop_control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "desktop_control_allowed": self.desktop_control_allowed,
            "desktop_control_attempts": self.desktop_control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "output_root": self.output_root,
            "report_path": self.report_path,
            "trajectory_path": self.trajectory_path,
            "controlled_page": dict(self.controlled_page),
            "readiness_plan": dict(self.readiness_plan),
            "readiness_execution": dict(self.readiness_execution),
            "browser_workflow": dict(self.browser_workflow),
            "readiness_stop": dict(self.readiness_stop),
            "profile_cleanup": dict(self.profile_cleanup),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class ControlledPageServer:
    """Local loopback page for deterministic DOM operation and readback."""

    def __init__(self, *, marker: str):
        self.marker = str(marker or DEFAULT_MARKER)
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _controlled_page_handler(self.marker),
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="openwukong-owned-browser-controlled-page",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/"

    def start(self) -> ControlledPageServerReport:
        self._thread.start()
        return ControlledPageServerReport(
            url=self.url,
            marker=self.marker,
            port=int(self._server.server_address[1]),
        )

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


def run_owned_browser_safe_operation_demo(
    *,
    output_root: str | Path = "logs/runtime/owned-browser-safe-operation-demo",
    browser_executable: str = "chrome.exe",
    browser_debug_port: int = 0,
    marker: str = DEFAULT_MARKER,
    keep_profile: bool = False,
    launcher: SessionReadinessLauncher | None = None,
    terminator: SessionReadinessTerminator | None = None,
    browser_action_runner: Optional[object] = None,
    settle_seconds: float = 0.1,
) -> OwnedBrowserSafeOperationDemoReport:
    started = time.perf_counter()
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "owned_browser_safe_operation_demo.json"
    workflow_path = root / "browser_workflow.json"
    stop_path = root / "readiness_stop.json"
    profile_path = root / "owned_browser_profile"
    manifest_path = root / "session_readiness_manifest.json"
    trajectory_root = root / "control_trajectories"

    controlled_server = ControlledPageServer(marker=marker)
    server_report = controlled_server.start()
    readiness_plan = build_session_readiness_plan(
        routes=("browser-devtools-or-extension",),
        options=SessionReadinessPlanOptions(
            browser_executable=str(browser_executable or "chrome.exe"),
            browser_debug_port=int(browser_debug_port or 0),
            browser_user_data_dir=str(profile_path),
            browser_url=server_report.url,
        ),
    )
    launch_data: dict = {}
    workflow_data: dict = {}
    stop_data: dict = {}
    cleanup_data: dict = {}
    trajectory_path = ""
    error = ""
    decision = "owned_browser_demo_failed"

    try:
        launch_report = execute_session_readiness_plan(
            readiness_plan,
            manifest_path=str(manifest_path),
            launcher=launcher,
        )
        launch_data = launch_report.to_dict()
        debugger_url = _first_started_readiness_url(launch_data)
        if not debugger_url:
            error = _first_report_error(launch_data) or "owned_browser_launch_not_ready"
        else:
            workflow = run_control_fabric_browser_workflow(
                process_name=Path(str(browser_executable or "chrome.exe")).name,
                window_title="OpenWukong Controlled Page - Google Chrome",
                resource_url=server_report.url,
                debugger_url=debugger_url,
                steps=_demo_steps(server_report.url, marker),
                expectations=_demo_expectations(marker),
                allow_control=True,
                settle_seconds=max(0.0, float(settle_seconds or 0.0)),
                fabric=ControlFabric.with_default_connectors(
                    ownership_index=build_ownership_index((manifest_path,)),
                    require_owned_session_for_execution=True,
                ),
                browser_action_runner=browser_action_runner,
                session_discovery=None,
            )
            workflow_data = workflow.to_dict()
            _write_json(workflow_path, workflow_data)
            if workflow.ok:
                decision = "owned_browser_demo_verified"
            else:
                error = workflow.error or "owned_browser_workflow_failed"
    finally:
        if manifest_path.exists():
            stop_report = stop_session_readiness_manifest(
                str(manifest_path),
                terminator=terminator,
            )
            stop_data = stop_report.to_dict()
            _write_json(stop_path, stop_data)
        else:
            stop_data = {
                "mode": "session-readiness-stop",
                "safety_mode": "manifest_pid_tree_stop",
                "control_allowed": False,
                "control_attempts": 0,
                "stop_attempts": 0,
                "manifest_path": str(manifest_path),
                "results": [],
                "error": "manifest_not_written",
            }
        controlled_server.stop()
        cleanup_data = _cleanup_profile(profile_path, output_root=root, keep_profile=keep_profile)

    ok = bool(decision == "owned_browser_demo_verified" and workflow_data.get("ok"))
    if ok and _stop_failed(stop_data):
        ok = False
        decision = "owned_browser_demo_stop_failed"
        error = _first_report_error(stop_data) or "owned_browser_stop_failed"
    if ok and not keep_profile and not bool(cleanup_data.get("deleted", False)):
        ok = False
        decision = "owned_browser_demo_profile_cleanup_failed"
        error = str(cleanup_data.get("error", "") or "profile_cleanup_failed")

    recorder = ControlTrajectoryRecorder(
        trajectory_root,
        scenario="owned-browser-safe-operation-demo",
        target_id=server_report.url,
        metadata={
            "browser_executable": str(browser_executable or ""),
            "marker": str(marker or ""),
            "manifest_path": str(manifest_path),
        },
    )
    recorder.record_step(
        phase="controlled_page",
        action="serve_loopback_page",
        report=server_report,
    )
    recorder.record_step(
        phase="launch",
        action="launch_browser_devtools_isolated",
        report=launch_data,
        artifacts=_existing_artifacts(
            (manifest_path, "session_readiness_manifest", "application/json"),
        ),
    )
    recorder.record_step(
        phase="workflow",
        action="controlled_dom_operation",
        report=workflow_data,
        artifacts=_existing_artifacts(
            (workflow_path, "browser_workflow_report", "application/json"),
        ),
    )
    recorder.record_step(
        phase="cleanup",
        action="stop_owned_browser_and_cleanup_profile",
        report={
            "readiness_stop": stop_data,
            "profile_cleanup": cleanup_data,
            "control_attempts": 0,
        },
        artifacts=_existing_artifacts(
            (stop_path, "readiness_stop_report", "application/json"),
        ),
    )
    trajectory_path = str(recorder.manifest_path)

    report = OwnedBrowserSafeOperationDemoReport(
        ok=ok,
        decision=decision,
        output_root=str(root),
        report_path=str(report_path),
        trajectory_path=trajectory_path,
        controlled_page=server_report.to_dict(),
        readiness_plan=readiness_plan.to_dict(),
        readiness_execution=launch_data,
        browser_workflow=workflow_data,
        readiness_stop=stop_data,
        profile_cleanup=cleanup_data,
        error="" if ok else error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    _write_json(report_path, report.to_dict())
    recorder.record_step(
        phase="final_report",
        action="write_demo_report",
        report=report,
        artifacts=_existing_artifacts(
            (report_path, "owned_browser_demo_report", "application/json"),
        ),
    )
    return report


def main(
    argv: Optional[list[str]] = None,
    *,
    launcher: SessionReadinessLauncher | None = None,
    terminator: SessionReadinessTerminator | None = None,
    browser_action_runner: Optional[object] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run an owned isolated browser safe-operation demo."
    )
    parser.add_argument("--output-root", default="logs/runtime/owned-browser-safe-operation-demo")
    parser.add_argument("--browser-executable", default="chrome.exe")
    parser.add_argument("--browser-debug-port", type=int, default=0)
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    parser.add_argument("--keep-profile", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=0.1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_owned_browser_safe_operation_demo(
        output_root=args.output_root,
        browser_executable=args.browser_executable,
        browser_debug_port=args.browser_debug_port,
        marker=args.marker,
        keep_profile=bool(args.keep_profile),
        launcher=launcher,
        terminator=terminator,
        browser_action_runner=browser_action_runner,
        settle_seconds=float(args.settle_seconds or 0.0),
    )
    data = report.to_dict()
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "Owned browser safe operation demo: "
            f"ok={data['ok']} "
            f"decision={data['decision']} "
            f"control_attempts={data['control_attempts']} "
            f"trajectory={data['trajectory_path']}"
        )
    return 0 if report.ok else 1


def _demo_steps(page_url: str, marker: str) -> tuple[BrowserWorkflowStep, ...]:
    return (
        BrowserWorkflowStep(action="navigate_url", url=page_url),
        BrowserWorkflowStep(
            action="set_input_value",
            selector="#task-input",
            value=marker,
        ),
        BrowserWorkflowStep(action="submit_form", selector="#run-button"),
        BrowserWorkflowStep(action="read_page"),
        BrowserWorkflowStep(action="extract_results", selector="#result a"),
    )


def _demo_expectations(marker: str) -> BrowserWorkflowExpectations:
    return BrowserWorkflowExpectations(
        expected_url_contains=("verified",),
        expected_text_contains=(marker, "OpenWukong DOM verified"),
        expected_link_href_contains=(quote(marker, safe=""),),
        expected_link_text_contains=("OpenWukong DOM verified",),
        min_result_count=1,
    )


def _controlled_page_handler(marker: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/favicon.ico"):
                self._send_bytes(b"", content_type="image/x-icon")
                return
            self._send_bytes(
                _controlled_page_html(marker).encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )

        def log_message(self, format, *args):
            return

        def _send_bytes(self, body: bytes, *, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _controlled_page_html(marker: str) -> str:
    marker_json = json.dumps(str(marker or DEFAULT_MARKER))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OpenWukong Controlled Page</title>
</head>
<body>
  <main>
    <h1>OpenWukong Owned Browser Demo</h1>
    <form id="probe-form">
      <label for="task-input">Marker</label>
      <input id="task-input" name="task" autocomplete="off">
      <button id="run-button" type="submit">Run</button>
    </form>
    <section id="result" aria-live="polite"></section>
  </main>
  <script>
    const expectedMarker = {marker_json};
    const form = document.querySelector('#probe-form');
    const input = document.querySelector('#task-input');
    const result = document.querySelector('#result');
    form.addEventListener('submit', (event) => {{
      event.preventDefault();
      const value = input.value || expectedMarker;
      const encoded = encodeURIComponent(value);
      document.title = 'OpenWukong Controlled Page - Verified';
      history.replaceState(null, '', `/verified?marker=${{encoded}}`);
      result.innerHTML = [
        '<h2>OpenWukong DOM verified</h2>',
        `<p id="result-marker">${{value}}</p>`,
        `<a id="result-link" href="/result?marker=${{encoded}}">OpenWukong DOM verified: ${{value}}</a>`
      ].join('');
    }});
  </script>
</body>
</html>
"""


def _first_started_readiness_url(data: dict) -> str:
    for result in data.get("results", ()) or ():
        if not isinstance(result, dict):
            continue
        if str(result.get("status", "") or "") == "started":
            text = str(result.get("readiness_url", "") or "").strip()
            if text:
                return text
    return ""


def _first_report_error(data: dict) -> str:
    if isinstance(data.get("error"), str) and data.get("error"):
        return str(data.get("error"))
    for key in ("results", "launches"):
        for result in data.get(key, ()) or ():
            if isinstance(result, dict) and str(result.get("error", "") or "").strip():
                return str(result.get("error"))
    return ""


def _stop_failed(stop_data: dict) -> bool:
    results = tuple(item for item in stop_data.get("results", ()) or () if isinstance(item, dict))
    if not results:
        return False
    return any(str(item.get("status", "") or "") == "failed" for item in results)


def _cleanup_profile(
    profile_path: Path,
    *,
    output_root: Path,
    keep_profile: bool,
) -> dict:
    path = Path(profile_path).resolve()
    root = Path(output_root).resolve()
    result = {
        "attempted": False,
        "deleted": False,
        "kept": bool(keep_profile),
        "path": str(path),
        "safety_root": str(root),
        "error": "",
    }
    if keep_profile:
        return result
    if not _is_relative_to(path, root):
        result["error"] = "profile_path_outside_output_root"
        return result
    result["attempted"] = True
    if not path.exists():
        result["deleted"] = True
        return result
    try:
        shutil.rmtree(path, onerror=_rmtree_remove_readonly)
    except Exception as exc:
        result["error"] = str(exc) or exc.__class__.__name__
        result["deleted"] = not path.exists()
        return result
    result["deleted"] = not path.exists()
    if not result["deleted"]:
        result["error"] = "profile_still_exists"
    return result


def _rmtree_remove_readonly(func, path: str, exc_info: object) -> None:
    del exc_info
    try:
        Path(path).chmod(stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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
