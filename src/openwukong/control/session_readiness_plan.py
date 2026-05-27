# -*- coding: utf-8 -*-
"""Plan-only helpers for making connector sessions discoverable."""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol


_MANAGED_HELPER_ACTION_IDS = {
    "launch_browser_devtools_isolated",
    "launch_ide_bridge_isolated",
}


@dataclasses.dataclass(frozen=True)
class SessionReadinessPlanOptions:
    browser_executable: str = "chrome.exe"
    browser_debug_port: int = 9222
    browser_user_data_dir: str = "logs/runtime/browser-devtools-profile"
    browser_url: str = "about:blank"
    ide_executable: str = "cursor.exe"
    ide_user_data_dir: str = "logs/runtime/ide-bridge-user-data"
    ide_extensions_dir: str = "logs/runtime/ide-bridge-extensions"
    ide_extension_dir: str = "extensions/openwukong-vscode"
    ide_bridge_host: str = "127.0.0.1"
    ide_bridge_port: int = 8787
    workspace_root: str = ""


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
    foreground_required: bool = False
    execute_supported: bool = False

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
            "foreground_required": self.foreground_required,
            "execute_supported": self.execute_supported,
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
        process = subprocess.Popen(
            list(argv),
            cwd=cwd or None,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
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
        script = (
            "$tokens = ConvertFrom-Json @'\n"
            + json.dumps(list(tokens), ensure_ascii=False)
            + "\n'@\n"
            "$matches = Get-CimInstance Win32_Process | Where-Object {\n"
            "  $cmd = $_.CommandLine\n"
            "  if (-not $cmd) { return $false }\n"
            "  foreach ($token in $tokens) {\n"
            "    if ($token -and $cmd.Contains([string]$token)) { return $true }\n"
            "  }\n"
            "  return $false\n"
            "} | Select-Object -ExpandProperty ProcessId\n"
            "$matches | ForEach-Object { [string]$_ }\n"
        )
        completed = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "-",
            ],
            input=script,
            shell=False,
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
        for process_id in pids:
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
    if not action.creates_isolated_profile:
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
        pid = launcher.launch(argv)
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
        readiness_url=action.readiness_url,
        workspace_root=action.workspace_root,
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
    if route_id == "browser-devtools-or-extension":
        return _browser_action(options)
    if route_id == "ide-extension-connector":
        return _ide_action(options)
    if route_id in {"terminal-native-session", "git-cli"}:
        return _workspace_action(route_id, options)
    return None


def _browser_action(options: SessionReadinessPlanOptions) -> SessionReadinessAction:
    user_data_dir = _normalized_path(options.browser_user_data_dir)
    argv = (
        options.browser_executable,
        f"--remote-debugging-port={int(options.browser_debug_port)}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--new-window",
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
        readiness_url=f"http://127.0.0.1:{int(options.browser_debug_port)}",
        creates_isolated_profile=True,
        foreground_required=False,
    )


def _ide_action(options: SessionReadinessPlanOptions) -> SessionReadinessAction:
    user_data_dir = _normalized_path(options.ide_user_data_dir)
    extensions_dir = _normalized_path(options.ide_extensions_dir)
    extension_dir = _normalized_path(options.ide_extension_dir)
    bridge_url = f"http://{options.ide_bridge_host}:{int(options.ide_bridge_port)}"
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
        "openwukong.bridge.port": int(options.ide_bridge_port),
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
    for value in argv:
        text = str(value or "").strip()
        if not text:
            continue
        if text.startswith("--remote-debugging-port="):
            tokens.extend(_token_variants(text))
        if text.startswith("--user-data-dir=") or text.startswith("--extensions-dir="):
            tokens.extend(_token_variants(text))
            path_text = text.split("=", 1)[1].strip()
            tokens.extend(_token_variants(path_text))
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
