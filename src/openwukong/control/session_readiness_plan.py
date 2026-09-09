# -*- coding: utf-8 -*-
"""Plan-only helpers for making connector sessions discoverable."""

from __future__ import annotations

import base64
import dataclasses
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

from openwukong.control.ide_bridge_registry import discover_ide_bridge_urls
from openwukong.control.native_bridge_registry import discover_agent_native_bridge_urls
from openwukong.control.wechat_native_bridge_registry import (
    discover_wechat_native_bridge_urls,
)


_MANAGED_HELPER_ACTION_IDS = {
    "launch_agent_native_cdp_bridge",
    "launch_agent_app_devtools_owned",
    "launch_browser_devtools_isolated",
    "launch_ide_bridge_isolated",
    "launch_wechat_native_bridge",
}
_DEVTOOLS_ACTIVE_PORT_FILENAME = "DevToolsActivePort"
_DYNAMIC_DEVTOOLS_PORT_TIMEOUT_SEC = 15.0
_DYNAMIC_DEVTOOLS_PORT_POLL_SEC = 0.1
_DYNAMIC_IDE_BRIDGE_TIMEOUT_SEC = 15.0
_DYNAMIC_IDE_BRIDGE_POLL_SEC = 0.1


@dataclasses.dataclass(frozen=True)
class SessionReadinessPlanOptions:
    browser_executable: str = "chrome.exe"
    browser_debug_port: int = 0
    browser_user_data_dir: str = "logs/runtime/browser-devtools-profile"
    browser_url: str = "about:blank"
    agent_app_executable: str = ""
    agent_app_debug_port: int = 0
    agent_app_user_data_dir: str = "logs/runtime/agent-app-devtools-profile"
    agent_app_url: str = ""
    agent_app_workspace_path: str = ""
    agent_app_use_default_profile: bool = False
    ide_executable: str = "cursor.exe"
    ide_user_data_dir: str = "logs/runtime/ide-bridge-user-data"
    ide_extensions_dir: str = "logs/runtime/ide-bridge-extensions"
    ide_extension_dir: str = "extensions/openwukong-vscode"
    ide_bridge_host: str = "127.0.0.1"
    ide_bridge_port: int = 0
    workspace_root: str = ""
    agent_bridge_python_executable: str = sys.executable or "python"
    agent_bridge_agent: str = "agent app"
    agent_bridge_agent_id: str = ""
    agent_bridge_host: str = "127.0.0.1"
    agent_bridge_port: int = 0
    agent_bridge_debugger_url: str = ""
    agent_bridge_registry_path: str = "logs/runtime/agent-native-cdp-bridge/native-bridges.json"
    agent_bridge_process_name: str = ""
    agent_bridge_pid: int = 0
    agent_bridge_hwnd: int = 0
    agent_bridge_window_title: str = ""
    agent_bridge_project_name: str = ""
    agent_bridge_task_name: str = ""
    agent_bridge_target_title: str = ""
    agent_bridge_target_url: str = ""
    wechat_bridge_python_executable: str = sys.executable or "python"
    wechat_bridge_host: str = "127.0.0.1"
    wechat_bridge_port: int = 0
    wechat_bridge_registry_path: str = "logs/runtime/wechat-native-bridge/wechat-native-bridges.json"
    wechat_bridge_process_name: str = "Weixin.exe"
    wechat_bridge_pid: int = 0
    wechat_bridge_hwnd: int = 0
    wechat_bridge_window_title: str = ""
    wechat_bridge_conversation_name: str = "File Transfer Assistant"
    wechat_bridge_conversation_id: str = ""
    wechat_bridge_backend: str = "read-only-evidence"
    wechat_bridge_capture_dir: str = "logs/runtime/wechat-native-bridge/captures"
    wechat_bridge_capability_timeout_sec: float = 5.0


@dataclasses.dataclass(frozen=True)
class SessionReadinessAction:
    action_id: str
    route_id: str
    connector_id: str
    description: str
    command: str = ""
    argv: tuple[str, ...] = ()
    readiness_url: str = ""
    workspace_root: str = ""
    settings_preview: dict | None = None
    creates_isolated_profile: bool = False
    managed_background_helper: bool = False
    foreground_required: bool = False
    execute_supported: bool = False
    blocked_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "route_id": self.route_id,
            "connector_id": self.connector_id,
            "description": self.description,
            "command": self.command,
            "argv": list(self.argv),
            "readiness_url": self.readiness_url,
            "workspace_root": self.workspace_root,
            "settings_preview": dict(self.settings_preview or {}),
            "creates_isolated_profile": self.creates_isolated_profile,
            "managed_background_helper": self.managed_background_helper,
            "foreground_required": self.foreground_required,
            "execute_supported": self.execute_supported,
            "blocked_reason": self.blocked_reason,
        }


@dataclasses.dataclass(frozen=True)
class SessionReadinessPlanReport:
    actions: tuple[SessionReadinessAction, ...]

    @property
    def mode(self) -> str:
        return "session-readiness-launch-plan"

    @property
    def safety_mode(self) -> str:
        return "plan_only"

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
            "action_count": len(self.actions),
            "actions": [action.to_dict() for action in self.actions],
        }

    def with_actions(
        self,
        actions: tuple[SessionReadinessAction, ...],
    ) -> "SessionReadinessPlanReport":
        return SessionReadinessPlanReport(actions=tuple(actions))


@dataclasses.dataclass(frozen=True)
class SessionReadinessLaunchResult:
    action_id: str
    route_id: str
    connector_id: str
    status: str
    pid: int = 0
    command: str = ""
    argv: tuple[str, ...] = ()
    readiness_url: str = ""
    workspace_root: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "route_id": self.route_id,
            "connector_id": self.connector_id,
            "status": self.status,
            "pid": self.pid,
            "command": self.command,
            "argv": list(self.argv),
            "readiness_url": self.readiness_url,
            "workspace_root": self.workspace_root,
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class SessionReadinessExecutionReport:
    results: tuple[SessionReadinessLaunchResult, ...]
    manifest_path: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "session-readiness-execution"

    @property
    def safety_mode(self) -> str:
        return "isolated_helper_launch"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def launch_attempts(self) -> int:
        return sum(1 for result in self.results if result.status == "started")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "launch_attempts": self.launch_attempts,
            "manifest_path": self.manifest_path,
            "results": [result.to_dict() for result in self.results],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class SessionReadinessStopResult:
    action_id: str
    route_id: str
    connector_id: str
    status: str
    pid: int = 0
    error: str = ""
    warning: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "route_id": self.route_id,
            "connector_id": self.connector_id,
            "status": self.status,
            "pid": self.pid,
            "error": self.error,
            "warning": self.warning,
        }


@dataclasses.dataclass(frozen=True)
class SessionReadinessStopReport:
    results: tuple[SessionReadinessStopResult, ...]
    manifest_path: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "session-readiness-stop"

    @property
    def safety_mode(self) -> str:
        return "manifest_pid_tree_stop"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def stop_attempts(self) -> int:
        return sum(1 for result in self.results if result.status == "stopped")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "stop_attempts": self.stop_attempts,
            "manifest_path": self.manifest_path,
            "results": [result.to_dict() for result in self.results],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class SessionReadinessLauncher(Protocol):
    def launch(self, argv: tuple[str, ...], cwd: str | None = None) -> int:
        ...


class SessionReadinessTerminator(Protocol):
    def terminate_tree(self, pid: int) -> None:
        ...


class SubprocessSessionReadinessLauncher:
    """Launch readiness helpers without shell expansion."""

    def launch(self, argv: tuple[str, ...], cwd: str | None = None) -> int:
        startupinfo = None
        creationflags = 0
        if sys.platform.startswith("win") and hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # SW_SHOWMINNOACTIVE: show minimized without activating the window.
            startupinfo.wShowWindow = 7
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            list(argv),
            cwd=cwd or None,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return int(process.pid)


class TaskTreeSessionReadinessTerminator:
    """Terminate helper process trees recorded in a readiness manifest."""

    def terminate_tree(self, pid: int) -> None:
        process_id = int(pid)
        if process_id <= 0:
            raise ValueError("invalid_pid")
        if sys.platform.startswith("win"):
            completed = subprocess.run(
                ["taskkill", "/PID", str(process_id), "/T", "/F"],
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if completed.returncode != 0:
                message = (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or f"taskkill_exit_{completed.returncode}"
                )
                raise RuntimeError(message)
            return
        os.kill(process_id, signal.SIGTERM)

    def terminate_owned_processes(self, argv: tuple[str, ...]) -> None:
        tokens = _managed_process_tokens(argv)
        if not tokens or not sys.platform.startswith("win"):
            return
        last_error = ""
        last_pids: tuple[int, ...] = ()
        for pass_index in range(6):
            last_pids = self._terminate_owned_processes_once(tokens)
            for process_id in last_pids:
                try:
                    self._terminate_owned_process_tree(process_id)
                except Exception as exc:
                    last_error = str(exc) or exc.__class__.__name__
            if pass_index < 5:
                time.sleep(0.5)
        if last_pids:
            remaining_pids = self._terminate_owned_processes_once(tokens)
            if remaining_pids:
                suffix = f":{last_error}" if last_error else ""
                raise RuntimeError(
                    "owned_processes_still_running:"
                    + ",".join(str(pid) for pid in remaining_pids)
                    + suffix
                )

    def _terminate_owned_processes_once(self, tokens: tuple[str, ...]) -> tuple[int, ...]:
        tokens_json_b64 = base64.b64encode(
            json.dumps(list(tokens), ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        script = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8\n"
            f"$tokensJson = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{tokens_json_b64}'))\n"
            "$tokens = $tokensJson | ConvertFrom-Json\n"
            "$self = $PID\n"
            "$matches = @()\n"
            "foreach ($proc in Get-CimInstance Win32_Process) {\n"
            "  if ($proc.ProcessId -eq $self) { continue }\n"
            "  $cmd = $proc.CommandLine\n"
            "  if (-not $cmd) { continue }\n"
            "  $hit = $false\n"
            "  foreach ($token in $tokens) {\n"
            "    if ($token -and $cmd.Contains([string]$token)) { $hit = $true; break }\n"
            "  }\n"
            "  if ($hit) {\n"
            "    $matches += $proc.ProcessId\n"
            "    }\n"
            "  }\n"
            "$matches | ForEach-Object { [string]$_ }\n"
        )
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        completed = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded_script,
            ],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            message = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"owned_process_scan_exit_{completed.returncode}"
            )
            raise RuntimeError(message)
        pids = tuple(
            _safe_int(line.strip())
            for line in completed.stdout.splitlines()
            if _safe_int(line.strip()) > 0
        )
        return pids

    def _terminate_owned_process_tree(self, process_id: int) -> None:
        kill = subprocess.run(
            ["taskkill", "/PID", str(process_id), "/T", "/F"],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if kill.returncode != 0:
            message = (
                kill.stderr.strip()
                or kill.stdout.strip()
                or f"taskkill_exit_{kill.returncode}"
            )
            if _is_missing_process_error(message):
                return
            raise RuntimeError(message)


def build_session_readiness_plan(
    *,
    routes: tuple[str, ...] | list[str],
    options: SessionReadinessPlanOptions | None = None,
) -> SessionReadinessPlanReport:
    opts = options or SessionReadinessPlanOptions()
    actions: list[SessionReadinessAction] = []
    seen: set[str] = set()
    for route_id in routes or ():
        route = str(route_id or "").strip()
        if not route or route in seen:
            continue
        seen.add(route)
        action = _action_for_route(route, opts)
        if action is not None:
            actions.append(action)
    return SessionReadinessPlanReport(actions=tuple(actions))


def execute_session_readiness_plan(
    plan: SessionReadinessPlanReport,
    *,
    manifest_path: str = "logs/runtime/session-readiness/manifest.json",
    launcher: SessionReadinessLauncher | None = None,
) -> SessionReadinessExecutionReport:
    started = time.perf_counter()
    active_launcher = launcher or SubprocessSessionReadinessLauncher()
    results: list[SessionReadinessLaunchResult] = []
    for action in plan.actions:
        results.append(_execute_action(action, active_launcher))

    report = SessionReadinessExecutionReport(
        results=tuple(results),
        manifest_path=str(manifest_path),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    _write_manifest(report, manifest_path)
    return report


def stop_session_readiness_manifest(
    manifest_path: str,
    *,
    terminator: SessionReadinessTerminator | None = None,
) -> SessionReadinessStopReport:
    started = time.perf_counter()
    path = Path(manifest_path)
    active_terminator = terminator or TaskTreeSessionReadinessTerminator()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return SessionReadinessStopReport(
            results=(
                SessionReadinessStopResult(
                    action_id="",
                    route_id="",
                    connector_id="",
                    status="rejected",
                    error=f"manifest_read_failed:{exc}",
                ),
            ),
            manifest_path=str(manifest_path),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    if (
        data.get("mode") != "session-readiness-execution"
        or data.get("safety_mode") != "isolated_helper_launch"
    ):
        return SessionReadinessStopReport(
            results=(
                SessionReadinessStopResult(
                    action_id="",
                    route_id="",
                    connector_id="",
                    status="rejected",
                    error="unmanaged_manifest",
                ),
            ),
            manifest_path=str(manifest_path),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    results = [
        _stop_manifest_launch(launch, active_terminator)
        for launch in data.get("launches", [])
    ]
    return SessionReadinessStopReport(
        results=tuple(results),
        manifest_path=str(manifest_path),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _execute_action(
    action: SessionReadinessAction,
    launcher: SessionReadinessLauncher,
) -> SessionReadinessLaunchResult:
    argv = tuple(action.argv)
    if action.blocked_reason:
        return SessionReadinessLaunchResult(
            action_id=action.action_id,
            route_id=action.route_id,
            connector_id=action.connector_id,
            status="rejected",
            command=action.command,
            argv=argv,
            readiness_url=action.readiness_url,
            workspace_root=action.workspace_root,
            error=action.blocked_reason,
        )
    if not argv and not action.command:
        return SessionReadinessLaunchResult(
            action_id=action.action_id,
            route_id=action.route_id,
            connector_id=action.connector_id,
            status="workspace_bound" if action.workspace_root else "skipped",
            command=action.command,
            argv=argv,
            readiness_url=action.readiness_url,
            workspace_root=action.workspace_root,
        )
    if not action.creates_isolated_profile and not action.managed_background_helper:
        return SessionReadinessLaunchResult(
            action_id=action.action_id,
            route_id=action.route_id,
            connector_id=action.connector_id,
            status="rejected",
            command=action.command,
            argv=argv,
            readiness_url=action.readiness_url,
            workspace_root=action.workspace_root,
            error="isolated_profile_required",
        )
    if not argv:
        return SessionReadinessLaunchResult(
            action_id=action.action_id,
            route_id=action.route_id,
            connector_id=action.connector_id,
            status="rejected",
            command=action.command,
            argv=argv,
            readiness_url=action.readiness_url,
            workspace_root=action.workspace_root,
            error="argv_required",
        )
    try:
        _prepare_isolated_profile_directories(argv)
        _prepare_isolated_ide_settings(argv, action.settings_preview)
        pid = launcher.launch(argv)
        readiness_url, readiness_error = _resolve_launch_readiness_url(action, argv)
    except Exception as exc:
        return SessionReadinessLaunchResult(
            action_id=action.action_id,
            route_id=action.route_id,
            connector_id=action.connector_id,
            status="failed",
            command=action.command,
            argv=argv,
            readiness_url=action.readiness_url,
            workspace_root=action.workspace_root,
            error=str(exc) or exc.__class__.__name__,
        )
    return SessionReadinessLaunchResult(
        action_id=action.action_id,
        route_id=action.route_id,
        connector_id=action.connector_id,
        status="started",
        pid=pid,
        command=action.command,
        argv=argv,
        readiness_url=readiness_url,
        workspace_root=action.workspace_root,
        error=readiness_error,
    )


def _stop_manifest_launch(
    launch: object,
    terminator: SessionReadinessTerminator,
) -> SessionReadinessStopResult:
    if not isinstance(launch, dict):
        return SessionReadinessStopResult(
            action_id="",
            route_id="",
            connector_id="",
            status="rejected",
            error="invalid_launch_record",
        )
    action_id = str(launch.get("action_id") or "")
    route_id = str(launch.get("route_id") or "")
    connector_id = str(launch.get("connector_id") or "")
    status = str(launch.get("status") or "")
    pid = _safe_int(launch.get("pid"))
    if status != "started":
        return SessionReadinessStopResult(
            action_id=action_id,
            route_id=route_id,
            connector_id=connector_id,
            status="skipped",
            pid=pid,
            error="not_started",
        )
    if action_id not in _MANAGED_HELPER_ACTION_IDS:
        return SessionReadinessStopResult(
            action_id=action_id,
            route_id=route_id,
            connector_id=connector_id,
            status="rejected",
            pid=pid,
            error="unmanaged_launch",
        )
    if pid <= 0:
        return SessionReadinessStopResult(
            action_id=action_id,
            route_id=route_id,
            connector_id=connector_id,
            status="rejected",
            pid=pid,
            error="invalid_pid",
        )
    tree_error = ""
    try:
        terminator.terminate_tree(pid)
    except Exception as exc:
        tree_error = str(exc) or exc.__class__.__name__

    residual_error = ""
    try:
        _terminate_owned_residual_processes(launch, terminator)
    except Exception as exc:
        residual_error = str(exc) or exc.__class__.__name__

    if residual_error or (tree_error and not _is_missing_process_error(tree_error)):
        if residual_error:
            return SessionReadinessStopResult(
                action_id=action_id,
                route_id=route_id,
                connector_id=connector_id,
                status="failed",
                pid=pid,
                error=residual_error,
            )
        return SessionReadinessStopResult(
            action_id=action_id,
            route_id=route_id,
            connector_id=connector_id,
            status="stopped",
            pid=pid,
            warning=tree_error,
        )
    return SessionReadinessStopResult(
        action_id=action_id,
        route_id=route_id,
        connector_id=connector_id,
        status="stopped",
        pid=pid,
    )


def _action_for_route(
    route_id: str,
    options: SessionReadinessPlanOptions,
) -> SessionReadinessAction | None:
    if route_id == "wechat-native-bridge":
        return _wechat_native_bridge_action(options)
    if route_id == "agent-native-cdp-bridge":
        return _agent_native_cdp_bridge_action(options)
    if route_id == "agent-app-devtools-owned":
        return _agent_app_devtools_owned_action(options)
    if route_id == "browser-devtools-or-extension":
        return _browser_action(options)
    if route_id == "ide-extension-connector":
        return _ide_action(options)
    if route_id in {"terminal-native-session", "git-cli"}:
        return _workspace_action(route_id, options)
    return None


def _wechat_native_bridge_action(
    options: SessionReadinessPlanOptions,
) -> SessionReadinessAction:
    bridge_port = int(options.wechat_bridge_port)
    bridge_url = (
        "" if bridge_port == 0 else f"http://{options.wechat_bridge_host}:{bridge_port}"
    )
    registry_path = _normalized_path(options.wechat_bridge_registry_path)
    argv_parts = [
        options.wechat_bridge_python_executable or sys.executable or "python",
        "-m",
        "openwukong.control.wechat_native_endpoint_publisher",
        "--host",
        options.wechat_bridge_host,
        "--port",
        str(bridge_port),
        "--registry-path",
        registry_path,
        "--process-name",
        options.wechat_bridge_process_name,
        "--conversation-name",
        options.wechat_bridge_conversation_name,
        "--backend",
        options.wechat_bridge_backend,
        "--capture-dir",
        _normalized_path(options.wechat_bridge_capture_dir),
        "--capability-timeout-sec",
        str(float(options.wechat_bridge_capability_timeout_sec or 0)),
    ]
    optional_pairs = (
        ("--pid", str(int(options.wechat_bridge_pid or 0))),
        ("--hwnd", str(int(options.wechat_bridge_hwnd or 0))),
        ("--window-title", options.wechat_bridge_window_title),
        ("--conversation-id", options.wechat_bridge_conversation_id),
    )
    for flag, value in optional_pairs:
        text = str(value or "").strip()
        if text and text != "0":
            argv_parts.extend([flag, text])
    return SessionReadinessAction(
        action_id="launch_wechat_native_bridge",
        route_id="wechat-native-bridge",
        connector_id="wechat-native-bridge",
        description="Launch a local background WeChat native bridge endpoint publisher and registry entry.",
        command=_join_command([_quote(part) for part in argv_parts]),
        argv=tuple(argv_parts),
        readiness_url=bridge_url,
        creates_isolated_profile=False,
        managed_background_helper=True,
        foreground_required=False,
    )


def _agent_native_cdp_bridge_action(
    options: SessionReadinessPlanOptions,
) -> SessionReadinessAction:
    bridge_port = int(options.agent_bridge_port)
    bridge_url = (
        "" if bridge_port == 0 else f"http://{options.agent_bridge_host}:{bridge_port}"
    )
    registry_path = _normalized_path(options.agent_bridge_registry_path)
    argv_parts = [
        options.agent_bridge_python_executable or sys.executable or "python",
        "-m",
        "openwukong.control.agent_native_cdp_bridge",
        "--host",
        options.agent_bridge_host,
        "--port",
        str(bridge_port),
        "--agent",
        options.agent_bridge_agent,
        "--agent-id",
        options.agent_bridge_agent_id,
        "--debugger-url",
        options.agent_bridge_debugger_url,
        "--process-name",
        options.agent_bridge_process_name,
        "--registry-path",
        registry_path,
    ]
    optional_pairs = (
        ("--pid", str(int(options.agent_bridge_pid or 0))),
        ("--hwnd", str(int(options.agent_bridge_hwnd or 0))),
        ("--window-title", options.agent_bridge_window_title),
        ("--project", options.agent_bridge_project_name),
        ("--task", options.agent_bridge_task_name),
        ("--target-title", options.agent_bridge_target_title),
        ("--target-url", options.agent_bridge_target_url),
    )
    for flag, value in optional_pairs:
        text = str(value or "").strip()
        if text and text != "0":
            argv_parts.extend([flag, text])
    return SessionReadinessAction(
        action_id="launch_agent_native_cdp_bridge",
        route_id="agent-native-cdp-bridge",
        connector_id="agent-native-bridge",
        description="Launch a local background CDP-backed agent native bridge and registry entry.",
        command=_join_command([_quote(part) for part in argv_parts]),
        argv=tuple(argv_parts),
        readiness_url=bridge_url,
        creates_isolated_profile=False,
        managed_background_helper=True,
        foreground_required=False,
    )


def _browser_action(options: SessionReadinessPlanOptions) -> SessionReadinessAction:
    user_data_dir = _normalized_path(options.browser_user_data_dir)
    debug_port = int(options.browser_debug_port)
    argv = (
        options.browser_executable,
        f"--remote-debugging-port={debug_port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--headless=new",
        "--disable-gpu",
        "--disable-crash-reporter",
        options.browser_url or "about:blank",
    )
    command = _join_command([_quote(part) for part in argv])
    return SessionReadinessAction(
        action_id="launch_browser_devtools_isolated",
        route_id="browser-devtools-or-extension",
        connector_id="browser",
        description="Launch an isolated browser profile with a DevTools endpoint.",
        command=command,
        argv=argv,
        readiness_url="" if debug_port == 0 else f"http://127.0.0.1:{debug_port}",
        creates_isolated_profile=True,
        foreground_required=False,
    )


def _agent_app_devtools_owned_action(
    options: SessionReadinessPlanOptions,
) -> SessionReadinessAction:
    app_executable = str(options.agent_app_executable or "").strip()
    if _is_windowsapps_msix_executable(app_executable):
        return SessionReadinessAction(
            action_id="block_agent_app_devtools_owned_msix",
            route_id="agent-app-devtools-owned",
            connector_id="agent-app-devtools",
            description=(
                "Blocked MSIX/WindowsApps agent desktop shell launch; use an "
                "already-exposed native endpoint, standalone CLI, or extension bridge."
            ),
            foreground_required=True,
            blocked_reason="windowsapps_msix_executable_not_background_launchable",
        )
    use_default_profile = bool(options.agent_app_use_default_profile)
    user_data_dir = (
        ""
        if use_default_profile
        else _normalized_path(options.agent_app_user_data_dir)
    )
    debug_port = int(options.agent_app_debug_port)
    argv_parts = [
        app_executable,
        f"--remote-debugging-port={debug_port}",
        "--no-first-run",
        "--disable-crash-reporter",
    ]
    if user_data_dir:
        argv_parts.insert(2, f"--user-data-dir={user_data_dir}")
    app_url = str(options.agent_app_url or "").strip()
    workspace_path = (
        _normalized_path(options.agent_app_workspace_path)
        if options.agent_app_workspace_path
        else ""
    )
    if workspace_path:
        argv_parts.append(workspace_path)
    if app_url:
        argv_parts.append(app_url)
    argv = tuple(part for part in argv_parts if part)
    return SessionReadinessAction(
        action_id="launch_agent_app_devtools_owned",
        route_id="agent-app-devtools-owned",
        connector_id="agent-app-devtools",
        description="Launch an owned agent desktop app instance with an isolated profile and local DevTools endpoint.",
        command=_join_command([_quote(part) for part in argv]),
        argv=argv,
        readiness_url="" if debug_port == 0 else f"http://127.0.0.1:{debug_port}",
        creates_isolated_profile=not use_default_profile,
        managed_background_helper=True,
        foreground_required=False,
    )


def _ide_action(options: SessionReadinessPlanOptions) -> SessionReadinessAction:
    user_data_dir = _normalized_path(options.ide_user_data_dir)
    extensions_dir = _normalized_path(options.ide_extensions_dir)
    extension_dir = _normalized_path(options.ide_extension_dir)
    bridge_port = int(options.ide_bridge_port)
    bridge_url = "" if bridge_port == 0 else f"http://{options.ide_bridge_host}:{bridge_port}"
    argv_parts = [
        options.ide_executable,
        f"--user-data-dir={user_data_dir}",
        f"--extensions-dir={extensions_dir}",
        f"--extensionDevelopmentPath={extension_dir}",
    ]
    workspace_root = _normalized_path(options.workspace_root) if options.workspace_root else ""
    if workspace_root:
        argv_parts.append(workspace_root)
    settings = {
        "openwukong.bridge.autoStart": True,
        "openwukong.bridge.host": options.ide_bridge_host,
        "openwukong.bridge.port": bridge_port,
    }
    return SessionReadinessAction(
        action_id="launch_ide_bridge_isolated",
        route_id="ide-extension-connector",
        connector_id="ide-extension",
        description="Launch a VS Code-compatible IDE extension host with the OpenWukong bridge enabled.",
        command=_join_command([_quote(part) for part in argv_parts]),
        argv=tuple(argv_parts),
        readiness_url=bridge_url,
        workspace_root=workspace_root,
        settings_preview=settings,
        creates_isolated_profile=True,
        foreground_required=False,
    )


def _workspace_action(
    route_id: str,
    options: SessionReadinessPlanOptions,
) -> SessionReadinessAction:
    connector_id = "terminal" if route_id == "terminal-native-session" else "git"
    workspace_root = _normalized_path(options.workspace_root) if options.workspace_root else ""
    return SessionReadinessAction(
        action_id=f"bind_{connector_id}_workspace",
        route_id=route_id,
        connector_id=connector_id,
        description="Bind an existing workspace root for managed connector sessions.",
        workspace_root=workspace_root,
        creates_isolated_profile=False,
        foreground_required=False,
    )


def _write_manifest(
    report: SessionReadinessExecutionReport,
    manifest_path: str,
) -> None:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "mode": report.mode,
        "safety_mode": report.safety_mode,
        "control_allowed": report.control_allowed,
        "control_attempts": report.control_attempts,
        "launch_attempts": report.launch_attempts,
        "launches": [
            result.to_dict()
            for result in report.results
            if result.status == "started"
        ],
        "results": [result.to_dict() for result in report.results],
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_launch_readiness_url(
    action: SessionReadinessAction,
    argv: tuple[str, ...],
) -> tuple[str, str]:
    if action.action_id in {
        "launch_browser_devtools_isolated",
        "launch_agent_app_devtools_owned",
    }:
        debug_port = _remote_debugging_port(argv)
        if debug_port != 0:
            return action.readiness_url, ""
        return _wait_for_dynamic_devtools_readiness_url(argv)
    if action.action_id == "launch_agent_native_cdp_bridge":
        bridge_port = _flag_int(argv, "--port")
        if bridge_port != 0:
            return action.readiness_url, ""
        return _wait_for_dynamic_agent_native_bridge_readiness_url(argv)
    if action.action_id == "launch_wechat_native_bridge":
        bridge_port = _flag_int(argv, "--port")
        if bridge_port != 0:
            return action.readiness_url, ""
        return _wait_for_dynamic_wechat_native_bridge_readiness_url(argv)
    if action.action_id == "launch_ide_bridge_isolated":
        bridge_port = _safe_int((action.settings_preview or {}).get("openwukong.bridge.port"))
        if bridge_port != 0:
            return action.readiness_url, ""
        return _wait_for_dynamic_ide_bridge_readiness_url(action)
    return action.readiness_url, ""


@dataclasses.dataclass(frozen=True)
class _IDEBridgeDiscoveryTarget:
    process_name: str = ""
    window_title: str = ""
    project_name: str = ""
    workspace_path: str = ""


def _wait_for_dynamic_ide_bridge_readiness_url(
    action: SessionReadinessAction,
) -> tuple[str, str]:
    target = _ide_bridge_discovery_target(action)
    started = time.perf_counter()
    while (time.perf_counter() - started) < _DYNAMIC_IDE_BRIDGE_TIMEOUT_SEC:
        urls = discover_ide_bridge_urls(target=target)
        if urls:
            return urls[0], ""
        time.sleep(_DYNAMIC_IDE_BRIDGE_POLL_SEC)
    return "", "dynamic_ide_bridge_registry_timeout"


def _wait_for_dynamic_agent_native_bridge_readiness_url(
    argv: tuple[str, ...],
) -> tuple[str, str]:
    registry_path = _flag_value(argv, "--registry-path")
    if not registry_path:
        return "", "dynamic_agent_native_bridge_registry_path_missing"
    agent_id = _flag_value(argv, "--agent-id")
    started = time.perf_counter()
    while (time.perf_counter() - started) < _DYNAMIC_IDE_BRIDGE_TIMEOUT_SEC:
        urls = discover_agent_native_bridge_urls(
            agent_id=agent_id,
            registry_paths=(registry_path,),
            environment={},
        )
        if urls:
            return urls[0], ""
        time.sleep(_DYNAMIC_IDE_BRIDGE_POLL_SEC)
    return "", "dynamic_agent_native_bridge_registry_timeout"


def _wait_for_dynamic_wechat_native_bridge_readiness_url(
    argv: tuple[str, ...],
) -> tuple[str, str]:
    registry_path = _flag_value(argv, "--registry-path")
    if not registry_path:
        return "", "dynamic_wechat_native_bridge_registry_path_missing"
    started = time.perf_counter()
    while (time.perf_counter() - started) < _DYNAMIC_IDE_BRIDGE_TIMEOUT_SEC:
        urls = discover_wechat_native_bridge_urls(
            registry_paths=(registry_path,),
            environment={},
        )
        if urls:
            return urls[0], ""
        time.sleep(_DYNAMIC_IDE_BRIDGE_POLL_SEC)
    return "", "dynamic_wechat_native_bridge_registry_timeout"


def _ide_bridge_discovery_target(action: SessionReadinessAction) -> _IDEBridgeDiscoveryTarget:
    executable = _ide_executable_name(action.argv)
    family = _ide_family_from_executable(executable)
    window_title = {
        "cursor": "Cursor",
        "vscode": "Visual Studio Code",
    }.get(family, "")
    project_name = Path(action.workspace_root).name if action.workspace_root else ""
    return _IDEBridgeDiscoveryTarget(
        process_name=executable,
        window_title=window_title,
        project_name=project_name,
        workspace_path=action.workspace_root,
    )


def _ide_executable_name(argv: tuple[str, ...]) -> str:
    if not argv:
        return ""
    text = str(argv[0] or "").strip().replace("\\", "/")
    return text.rsplit("/", 1)[-1]


def _ide_family_from_executable(value: str) -> str:
    text = str(value or "").strip().casefold()
    if "cursor" in text:
        return "cursor"
    if text in {"code.exe", "code", "vscodium.exe", "vscodium"} or "vscode" in text:
        return "vscode"
    return ""


def _wait_for_dynamic_devtools_readiness_url(argv: tuple[str, ...]) -> tuple[str, str]:
    profile_path = _user_data_dir_from_argv(argv)
    if not profile_path:
        return "", "dynamic_devtools_user_data_dir_missing"
    active_port_path = Path(profile_path) / _DEVTOOLS_ACTIVE_PORT_FILENAME
    started = time.perf_counter()
    last_error = ""
    while (time.perf_counter() - started) < _DYNAMIC_DEVTOOLS_PORT_TIMEOUT_SEC:
        readiness_url, error = _read_devtools_active_port(active_port_path)
        if readiness_url:
            return readiness_url, ""
        last_error = error
        time.sleep(_DYNAMIC_DEVTOOLS_PORT_POLL_SEC)
    return "", last_error or "dynamic_devtools_active_port_timeout"


def _read_devtools_active_port(path: Path) -> tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "", "dynamic_devtools_active_port_missing"
    except Exception as exc:
        return "", str(exc) or exc.__class__.__name__
    first_line = ""
    for line in text.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    port = _safe_int(first_line)
    if port <= 0:
        return "", "dynamic_devtools_active_port_invalid"
    return f"http://127.0.0.1:{port}", ""


def _remote_debugging_port(argv: tuple[str, ...]) -> int:
    for value in argv:
        text = str(value or "").strip()
        if text.startswith("--remote-debugging-port="):
            return _safe_int(text.split("=", 1)[1].strip())
    return -1


def _flag_value(argv: tuple[str, ...], flag: str) -> str:
    for index, value in enumerate(argv):
        if str(value or "").strip() != flag:
            continue
        if index + 1 >= len(argv):
            return ""
        return str(argv[index + 1] or "").strip()
    return ""


def _flag_int(argv: tuple[str, ...], flag: str) -> int:
    return _safe_int(_flag_value(argv, flag))


def _user_data_dir_from_argv(argv: tuple[str, ...]) -> str:
    for value in argv:
        text = str(value or "").strip()
        if text.startswith("--user-data-dir="):
            return text.split("=", 1)[1].strip()
    return ""


def _normalized_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    return path.as_posix()


def _quote(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return '""'
    if any(char.isspace() for char in text):
        return f'"{text}"'
    return text


def _join_command(parts: list[str]) -> str:
    return " ".join(part for part in parts if str(part or "").strip())


def _is_windowsapps_msix_executable(value: str) -> bool:
    text = str(value or "").strip().casefold()
    if not text:
        return False
    normalized = text.replace("\\", "/")
    return "/program files/windowsapps/" in normalized and normalized.endswith(".exe")


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_missing_process_error(message: str) -> bool:
    text = str(message or "").lower()
    return (
        "not found" in text
        or "no such process" in text
        or "not exist" in text
        or "不存在" in text
    )


def _terminate_owned_residual_processes(
    launch: dict,
    terminator: SessionReadinessTerminator,
) -> None:
    callback = getattr(terminator, "terminate_owned_processes", None)
    if not callable(callback):
        return
    argv = tuple(str(value) for value in launch.get("argv", ()) if str(value).strip())
    if argv:
        callback(argv)


def _managed_process_tokens(argv: tuple[str, ...]) -> tuple[str, ...]:
    tokens: list[str] = []
    values = tuple(str(value or "").strip() for value in argv)
    for index, text in enumerate(values):
        if not text:
            continue
        previous = values[index - 1] if index > 0 else ""
        if previous == "--debugger-url":
            continue
        if text.startswith("--remote-debugging-port="):
            tokens.extend(_token_variants(text))
        if text == "openwukong.control.agent_native_cdp_bridge":
            tokens.extend(_token_variants(text))
        if (
            previous != "--debugger-url"
            and (
                text.startswith("http://127.0.0.1:")
                or text.startswith("https://127.0.0.1:")
            )
        ):
            tokens.extend(_token_variants(text))
        if text.startswith("--user-data-dir=") or text.startswith("--extensions-dir="):
            tokens.extend(_token_variants(text))
            path_text = text.split("=", 1)[1].strip()
            tokens.extend(_token_variants(path_text))
        if text.startswith("--registry-path="):
            tokens.extend(_token_variants(text))
            path_text = text.split("=", 1)[1].strip()
            tokens.extend(_token_variants(path_text))
        if previous == "--registry-path":
            tokens.extend(_token_variants(text))
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token and token not in seen:
            seen.add(token)
            unique.append(token)
    return tuple(unique)


def _token_variants(value: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    variants = {text, text.replace("/", "\\"), text.replace("\\", "/")}
    return tuple(variant for variant in variants if variant)


def _prepare_isolated_profile_directories(argv: tuple[str, ...]) -> None:
    for value in argv:
        text = str(value or "")
        if text.startswith("--user-data-dir=") or text.startswith("--extensions-dir="):
            path_text = text.split("=", 1)[1].strip()
            if path_text:
                Path(path_text).mkdir(parents=True, exist_ok=True)


def _prepare_isolated_ide_settings(
    argv: tuple[str, ...],
    settings_preview: dict | None,
) -> None:
    if not settings_preview:
        return
    user_data_dir = ""
    for value in argv:
        text = str(value or "")
        if text.startswith("--user-data-dir="):
            user_data_dir = text.split("=", 1)[1].strip()
            break
    if not user_data_dir:
        return
    settings_path = Path(user_data_dir) / "User" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if settings_path.exists():
        try:
            parsed = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                existing = parsed
        except Exception:
            existing = {}
    merged = dict(existing)
    merged.update(dict(settings_preview))
    settings_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
