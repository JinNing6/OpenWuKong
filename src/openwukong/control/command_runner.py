# -*- coding: utf-8 -*-
"""Owned workspace command runner for deterministic CLI execution."""

from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from openwukong.control.session_ownership import SessionOwnership


_DETACHED_PROCESS_HANDLES: list[subprocess.Popen] = []


@dataclasses.dataclass(frozen=True)
class CommandExecutionPolicy:
    profile_id: str = "workspace-write"
    workspace_root: str = ""
    timeout_sec: float = 60.0
    audit_log_path: str = ""
    require_owned_session: bool = False
    max_output_chars: int = 8000
    allowed_effects: tuple[str, ...] = ("read", "workspace_write")
    forbid_elevation: bool = True


@dataclasses.dataclass(frozen=True)
class CommandExecutionRequest:
    argv: tuple[str, ...]
    cwd: str = ""
    reason: str = ""
    effects: tuple[str, ...] = ()
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    ownership: SessionOwnership = dataclasses.field(default_factory=SessionOwnership.unowned)

    def to_dict(self) -> dict:
        return {
            "argv": list(self.argv),
            "cwd": self.cwd,
            "reason": self.reason,
            "effects": list(self.effects),
            "env_keys": sorted(str(key) for key in self.env),
            "ownership": self.ownership.to_dict(),
        }


@dataclasses.dataclass(frozen=True)
class CommandExecutionReport:
    request: CommandExecutionRequest
    policy: CommandExecutionPolicy
    request_id: str
    ok: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    elapsed_ms: float = 0.0
    control_attempts: int = 0
    timed_out: bool = False

    @property
    def mode(self) -> str:
        return "command-intelligence-execution"

    @property
    def safety_mode(self) -> str:
        return "workspace_command_runner"

    @property
    def control_allowed(self) -> bool:
        return self.control_attempts > 0

    @property
    def shell(self) -> bool:
        return False

    @property
    def ownership_required(self) -> bool:
        return bool(self.policy.require_owned_session)

    @property
    def ownership(self) -> SessionOwnership:
        return self.request.ownership

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "request_id": self.request_id,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "profile_id": self.policy.profile_id,
            "allowed_effects": list(self.policy.allowed_effects),
            "ownership_required": self.ownership_required,
            "ownership": self.ownership.to_dict(),
            "shell": self.shell,
            "argv": list(self.request.argv),
            "cwd": self.request.cwd,
            "workspace_root": self.policy.workspace_root,
            "timeout_sec": max(0.1, float(self.policy.timeout_sec or 60.0)),
            "exit_code": self.exit_code,
            "stdout": _clip(self.stdout, self.policy.max_output_chars),
            "stderr": _clip(self.stderr, self.policy.max_output_chars),
            "error": self.error,
            "timed_out": self.timed_out,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class CommandProcessStartReport:
    request: CommandExecutionRequest
    policy: CommandExecutionPolicy
    process_id: str
    pid: int
    ok: bool
    error: str = ""
    elapsed_ms: float = 0.0
    control_attempts: int = 0

    @property
    def mode(self) -> str:
        return "command-intelligence-process-start"

    @property
    def safety_mode(self) -> str:
        return "workspace_process_registry"

    @property
    def control_allowed(self) -> bool:
        return self.control_attempts > 0

    @property
    def ownership_required(self) -> bool:
        return bool(self.policy.require_owned_session)

    @property
    def ownership(self) -> SessionOwnership:
        return self.request.ownership

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "process_id": self.process_id,
            "pid": self.pid,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "profile_id": self.policy.profile_id,
            "ownership_required": self.ownership_required,
            "ownership": self.ownership.to_dict(),
            "argv": list(self.request.argv),
            "cwd": self.request.cwd,
            "workspace_root": self.policy.workspace_root,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass(frozen=True)
class CommandProcessStopReport:
    process_id: str
    pid: int
    ok: bool
    found: bool
    terminated: bool = False
    killed: bool = False
    exit_code: int | None = None
    error: str = ""
    elapsed_ms: float = 0.0
    control_attempts: int = 0

    @property
    def mode(self) -> str:
        return "command-intelligence-process-stop"

    @property
    def safety_mode(self) -> str:
        return "workspace_process_registry"

    @property
    def control_allowed(self) -> bool:
        return self.control_attempts > 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "process_id": self.process_id,
            "pid": self.pid,
            "ok": self.ok,
            "found": self.found,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "terminated": self.terminated,
            "killed": self.killed,
            "exit_code": self.exit_code,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclasses.dataclass
class _TrackedProcess:
    process_id: str
    request: CommandExecutionRequest
    process: subprocess.Popen | None
    started_at: float
    pid: int = 0
    restored: bool = False


class CommandRunner:
    """Run explicit argv commands inside a workspace policy boundary."""

    def __init__(self, policy: CommandExecutionPolicy | None = None):
        self.policy = policy or CommandExecutionPolicy()

    def execute(self, request: CommandExecutionRequest) -> CommandExecutionReport:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        normalized_request, error = self._normalize_request(request)
        if error:
            report = CommandExecutionReport(
                request=normalized_request,
                policy=self.policy,
                request_id=request_id,
                ok=False,
                error=error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_audit(report)
            return report

        effect_error = _effect_error(normalized_request.effects, self.policy)
        if effect_error:
            report = CommandExecutionReport(
                request=normalized_request,
                policy=self.policy,
                request_id=request_id,
                ok=False,
                error=effect_error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_audit(report)
            return report

        if self.policy.require_owned_session and not normalized_request.ownership.owned:
            report = CommandExecutionReport(
                request=normalized_request,
                policy=self.policy,
                request_id=request_id,
                ok=False,
                error="owned_session_required",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_audit(report)
            return report

        try:
            completed = subprocess.run(
                list(normalized_request.argv),
                cwd=normalized_request.cwd,
                env=_merged_env(normalized_request.env),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(0.1, float(self.policy.timeout_sec or 60.0)),
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            report = CommandExecutionReport(
                request=normalized_request,
                policy=self.policy,
                request_id=request_id,
                ok=False,
                exit_code=None,
                stdout=_timeout_text(exc.stdout),
                stderr=_timeout_text(exc.stderr),
                error="timeout",
                control_attempts=1,
                timed_out=True,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_audit(report)
            return report
        except FileNotFoundError:
            report = CommandExecutionReport(
                request=normalized_request,
                policy=self.policy,
                request_id=request_id,
                ok=False,
                error="executable_not_found",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_audit(report)
            return report

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        report = CommandExecutionReport(
            request=normalized_request,
            policy=self.policy,
            request_id=request_id,
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            error="" if completed.returncode == 0 else f"exit_code={completed.returncode}",
            control_attempts=1,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        self._write_audit(report)
        return report

    def _normalize_request(
        self,
        request: CommandExecutionRequest,
    ) -> tuple[CommandExecutionRequest, str]:
        argv = tuple(str(item) for item in request.argv if str(item).strip())
        effects = tuple(str(item).strip().lower() for item in request.effects if str(item).strip())
        cwd = str(request.cwd or self.policy.workspace_root or os.getcwd()).strip()
        normalized = dataclasses.replace(request, argv=argv, cwd=cwd, effects=effects)
        if not argv:
            return normalized, "empty_argv"
        if not cwd:
            return normalized, "cwd_required"
        cwd_path = Path(cwd)
        if not cwd_path.is_dir():
            return normalized, "cwd_not_directory"
        workspace_root = str(self.policy.workspace_root or "").strip()
        if workspace_root and not _is_relative_to(cwd_path, Path(workspace_root)):
            return normalized, "cwd_outside_workspace"
        return normalized, ""

    def _write_audit(self, report: CommandExecutionReport) -> None:
        audit_path = str(self.policy.audit_log_path or "").strip()
        if not audit_path:
            return
        path = Path(audit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "mode": "command-intelligence-audit-record",
            "request_id": report.request_id,
            "request": report.request.to_dict(),
            "result": {
                "ok": report.ok,
                "exit_code": report.exit_code,
                "error": report.error,
                "control_attempts": report.control_attempts,
                "timed_out": report.timed_out,
                "elapsed_ms": round(report.elapsed_ms, 3),
            },
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class CommandProcessRegistry:
    """Track and clean up long-running argv processes inside a policy boundary."""

    def __init__(
        self,
        policy: CommandExecutionPolicy | None = None,
        *,
        storage_path: str = "",
    ):
        self.policy = policy or CommandExecutionPolicy()
        self.storage_path = str(storage_path or "").strip()
        self._processes: dict[str, _TrackedProcess] = {}
        self._load_store()

    def start(self, request: CommandExecutionRequest) -> CommandProcessStartReport:
        started = time.perf_counter()
        process_id = str(uuid.uuid4())
        normalized_request, error = self._normalize_request(request)
        if not error:
            error = _effect_error(normalized_request.effects, self.policy)
        if not error and self.policy.require_owned_session and not normalized_request.ownership.owned:
            error = "owned_session_required"
        if error:
            report = CommandProcessStartReport(
                request=normalized_request,
                policy=self.policy,
                process_id="",
                pid=0,
                ok=False,
                error=error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_start_audit(report)
            return report

        try:
            process = subprocess.Popen(
                list(normalized_request.argv),
                cwd=normalized_request.cwd,
                env=_merged_env(normalized_request.env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=False,
                shell=False,
            )
        except FileNotFoundError:
            report = CommandProcessStartReport(
                request=normalized_request,
                policy=self.policy,
                process_id="",
                pid=0,
                ok=False,
                error="executable_not_found",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_start_audit(report)
            return report

        self._processes[process_id] = _TrackedProcess(
            process_id=process_id,
            request=normalized_request,
            process=process,
            started_at=time.time(),
            pid=int(process.pid or 0),
        )
        if self.storage_path:
            _remember_detached_handle(process)
        report = CommandProcessStartReport(
            request=normalized_request,
            policy=self.policy,
            process_id=process_id,
            pid=int(process.pid or 0),
            ok=True,
            control_attempts=1,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        self._save_store()
        self._write_start_audit(report)
        return report

    def stop(self, process_id: str, *, grace_seconds: float = 2.0) -> CommandProcessStopReport:
        started = time.perf_counter()
        tracked = self._processes.pop(str(process_id or ""), None)
        if tracked is None:
            report = CommandProcessStopReport(
                process_id=str(process_id or ""),
                pid=0,
                ok=False,
                found=False,
                error="process_not_found",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            self._write_stop_audit(report)
            return report

        process = tracked.process
        terminated = False
        killed = False
        exit_code: int | None = None
        if process is None:
            pid_stop = _terminate_pid(tracked.pid, grace_seconds=grace_seconds)
            terminated = pid_stop["terminated"]
            killed = pid_stop["killed"]
        else:
            if process.poll() is None:
                process.terminate()
                terminated = True
                try:
                    process.wait(timeout=max(0.1, float(grace_seconds or 2.0)))
                except subprocess.TimeoutExpired:
                    process.kill()
                    killed = True
                    process.wait(timeout=2.0)
            exit_code = process.poll()
        _settle_process_exit()
        _refresh_detached_handles()
        self._save_store()
        report = CommandProcessStopReport(
            process_id=tracked.process_id,
            pid=int(tracked.pid or 0),
            ok=True,
            found=True,
            terminated=terminated,
            killed=killed,
            exit_code=exit_code,
            control_attempts=1,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        self._write_stop_audit(report)
        return report

    def stop_all(self, *, grace_seconds: float = 2.0) -> tuple[CommandProcessStopReport, ...]:
        process_ids = tuple(self._processes)
        return tuple(
            self.stop(process_id, grace_seconds=grace_seconds)
            for process_id in process_ids
        )

    def snapshot(self) -> dict:
        active = []
        stale = []
        changed = False
        for process_id, tracked in tuple(self._processes.items()):
            if tracked.process is None:
                running = _pid_running(tracked.pid)
                exit_code = None
            else:
                exit_code = tracked.process.poll()
                running = exit_code is None
            item = {
                "process_id": process_id,
                "pid": int(tracked.pid or 0),
                "argv": list(tracked.request.argv),
                "cwd": tracked.request.cwd,
                "reason": tracked.request.reason,
                "effects": list(tracked.request.effects),
                "ownership": tracked.request.ownership.to_dict(),
                "running": running,
                "exit_code": exit_code,
                "started_at": tracked.started_at,
                "restored": tracked.restored,
            }
            if running:
                active.append(item)
            else:
                stale.append(item)
                self._processes.pop(process_id, None)
                changed = True
        if changed:
            self._save_store()
        return {
            "mode": "command-intelligence-process-snapshot",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": 0,
            "active_count": len(active),
            "stale_count": len(stale),
            "processes": active,
            "stale_processes": stale,
        }

    def _normalize_request(
        self,
        request: CommandExecutionRequest,
    ) -> tuple[CommandExecutionRequest, str]:
        argv = tuple(str(item) for item in request.argv if str(item).strip())
        effects = tuple(str(item).strip().lower() for item in request.effects if str(item).strip())
        cwd = str(request.cwd or self.policy.workspace_root or os.getcwd()).strip()
        normalized = dataclasses.replace(request, argv=argv, cwd=cwd, effects=effects)
        if not argv:
            return normalized, "empty_argv"
        if not cwd:
            return normalized, "cwd_required"
        cwd_path = Path(cwd)
        if not cwd_path.is_dir():
            return normalized, "cwd_not_directory"
        workspace_root = str(self.policy.workspace_root or "").strip()
        if workspace_root and not _is_relative_to(cwd_path, Path(workspace_root)):
            return normalized, "cwd_outside_workspace"
        return normalized, ""

    def _load_store(self) -> None:
        path = self._storage_file()
        if path is None or not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for record in data.get("processes", ()) or ():
            tracked = _tracked_process_from_record(record)
            if tracked is None:
                continue
            if not _pid_running(tracked.pid):
                continue
            self._processes[tracked.process_id] = tracked

    def _save_store(self) -> None:
        path = self._storage_file()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [_tracked_process_to_record(tracked) for tracked in self._processes.values()]
        data = {
            "mode": "command-intelligence-process-store",
            "safety_mode": "workspace_process_registry",
            "process_count": len(records),
            "processes": records,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _storage_file(self) -> Path | None:
        if not self.storage_path:
            return None
        return Path(self.storage_path)

    def _write_start_audit(self, report: CommandProcessStartReport) -> None:
        audit_path = str(self.policy.audit_log_path or "").strip()
        if not audit_path:
            return
        path = Path(audit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "mode": "command-intelligence-process-start-audit-record",
            "request": report.request.to_dict(),
            "result": {
                "ok": report.ok,
                "process_id": report.process_id,
                "pid": report.pid,
                "error": report.error,
                "control_attempts": report.control_attempts,
                "elapsed_ms": round(report.elapsed_ms, 3),
            },
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write_stop_audit(self, report: CommandProcessStopReport) -> None:
        audit_path = str(self.policy.audit_log_path or "").strip()
        if not audit_path:
            return
        path = Path(audit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "mode": "command-intelligence-process-stop-audit-record",
            "result": {
                "ok": report.ok,
                "process_id": report.process_id,
                "pid": report.pid,
                "found": report.found,
                "terminated": report.terminated,
                "killed": report.killed,
                "exit_code": report.exit_code,
                "error": report.error,
                "control_attempts": report.control_attempts,
                "elapsed_ms": round(report.elapsed_ms, 3),
            },
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_command_execution_policy(
    profile_id: str = "workspace-write",
    *,
    workspace_root: str = "",
    timeout_sec: float = 60.0,
    audit_log_path: str = "",
    require_owned_session: bool = False,
    max_output_chars: int = 8000,
) -> CommandExecutionPolicy:
    profile = _normalize_profile_id(profile_id)
    allowed = _allowed_effects_for_profile(profile)
    return CommandExecutionPolicy(
        profile_id=profile,
        workspace_root=workspace_root,
        timeout_sec=timeout_sec,
        audit_log_path=audit_log_path,
        require_owned_session=require_owned_session,
        max_output_chars=max_output_chars,
        allowed_effects=allowed,
        forbid_elevation=True,
    )


def _normalize_profile_id(value: str) -> str:
    profile = str(value or "").strip().lower().replace("_", "-")
    return profile or "workspace-write"


def _allowed_effects_for_profile(profile_id: str) -> tuple[str, ...]:
    if profile_id == "read-only":
        return ("read",)
    if profile_id == "workspace-write":
        return ("read", "workspace_write")
    if profile_id == "network-enabled":
        return ("read", "workspace_write", "network")
    return ("read", "workspace_write")


def _effect_error(effects: tuple[str, ...], policy: CommandExecutionPolicy) -> str:
    allowed = set(policy.allowed_effects)
    for effect in effects:
        if policy.forbid_elevation and effect == "elevated":
            return "effect_not_allowed:elevated"
        if effect not in allowed:
            return f"effect_not_allowed:{effect}"
    return ""


def _merged_env(overrides: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    for key, value in overrides.items():
        text_key = str(key).strip()
        if text_key:
            env[text_key] = str(value)
    return env


def _tracked_process_to_record(tracked: _TrackedProcess) -> dict:
    return {
        "process_id": tracked.process_id,
        "pid": int(tracked.pid or 0),
        "argv": list(tracked.request.argv),
        "cwd": tracked.request.cwd,
        "reason": tracked.request.reason,
        "effects": list(tracked.request.effects),
        "env_keys": sorted(str(key) for key in tracked.request.env),
        "ownership": tracked.request.ownership.to_dict(),
        "started_at": tracked.started_at,
        "restored": tracked.restored,
    }


def _tracked_process_from_record(record: dict) -> _TrackedProcess | None:
    if not isinstance(record, dict):
        return None
    process_id = str(record.get("process_id", "") or "").strip()
    pid = _safe_int(record.get("pid"))
    argv = tuple(str(item) for item in record.get("argv", ()) or () if str(item).strip())
    cwd = str(record.get("cwd", "") or "").strip()
    if not process_id or pid <= 0 or not argv or not cwd:
        return None
    request = CommandExecutionRequest(
        argv=argv,
        cwd=cwd,
        reason=str(record.get("reason", "") or ""),
        effects=tuple(
            str(item).strip().lower()
            for item in record.get("effects", ()) or ()
            if str(item).strip()
        ),
        ownership=_ownership_from_record(record.get("ownership")),
    )
    return _TrackedProcess(
        process_id=process_id,
        request=request,
        process=None,
        started_at=_safe_float(record.get("started_at"), time.time()),
        pid=pid,
        restored=True,
    )


def _ownership_from_record(value) -> SessionOwnership:
    if isinstance(value, SessionOwnership):
        return value
    if not isinstance(value, dict):
        return SessionOwnership.unowned()
    return SessionOwnership(
        owned=bool(value.get("owned", False)),
        ownership_source=str(value.get("ownership_source", "") or ""),
        manifest_path=str(value.get("manifest_path", "") or ""),
        route_id=str(value.get("route_id", "") or ""),
        connector_id=str(value.get("connector_id", "") or ""),
        action_id=str(value.get("action_id", "") or ""),
        pid=_safe_int(value.get("pid")),
        endpoint=str(value.get("endpoint", "") or ""),
        profile_path=str(value.get("profile_path", "") or ""),
        extensions_path=str(value.get("extensions_path", "") or ""),
        workspace_root=str(value.get("workspace_root", "") or ""),
        cleanup_ready=bool(value.get("cleanup_ready", False)),
    )


def _pid_running(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_running(int(pid))
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _windows_pid_running(pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    handle = open_process(
        process_query_limited_information,
        False,
        int(pid),
    )
    if not handle:
        return False
    try:
        return True
    finally:
        close_handle(handle)


def _terminate_pid(pid: int, *, grace_seconds: float) -> dict:
    pid_int = int(pid or 0)
    if pid_int <= 0 or not _pid_running(pid_int):
        return {"terminated": False, "killed": False}
    handle = _detached_handle_for_pid(pid_int)
    if handle is not None:
        return _terminate_popen(handle, grace_seconds=grace_seconds)
    if os.name == "nt":
        return _taskkill_pid(pid_int)
    os.kill(pid_int, signal.SIGTERM)
    terminated = True
    killed = False
    deadline = time.time() + max(0.1, float(grace_seconds or 2.0))
    while time.time() < deadline:
        if not _pid_running(pid_int):
            return {"terminated": terminated, "killed": killed}
        time.sleep(0.05)
    sigkill = getattr(signal, "SIGKILL", None)
    if sigkill is not None and _pid_running(pid_int):
        os.kill(pid_int, sigkill)
        killed = True
    return {"terminated": terminated, "killed": killed}


def _terminate_popen(process: subprocess.Popen, *, grace_seconds: float) -> dict:
    terminated = False
    killed = False
    if process.poll() is None:
        process.terminate()
        terminated = True
        try:
            process.wait(timeout=max(0.1, float(grace_seconds or 2.0)))
        except subprocess.TimeoutExpired:
            process.kill()
            killed = True
            process.wait(timeout=2.0)
    return {"terminated": terminated, "killed": killed}


def _taskkill_pid(pid: int) -> dict:
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5.0,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return {"terminated": False, "killed": False}
    return {
        "terminated": completed.returncode == 0,
        "killed": completed.returncode == 0,
    }


def _detached_handle_for_pid(pid: int) -> subprocess.Popen | None:
    for process in _DETACHED_PROCESS_HANDLES:
        if int(getattr(process, "pid", 0) or 0) == int(pid or 0):
            return process
    return None


def _remember_detached_handle(process: subprocess.Popen) -> None:
    _refresh_detached_handles()
    _DETACHED_PROCESS_HANDLES.append(process)


def _refresh_detached_handles() -> None:
    active: list[subprocess.Popen] = []
    for process in _DETACHED_PROCESS_HANDLES:
        try:
            if process.poll() is None:
                active.append(process)
        except Exception:
            continue
    _DETACHED_PROCESS_HANDLES[:] = active


def _settle_process_exit() -> None:
    if os.name == "nt":
        time.sleep(0.5)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except OSError:
        return False
    normalized_path = os.path.normcase(str(resolved_path))
    normalized_root = os.path.normcase(str(resolved_root))
    try:
        return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
    except ValueError:
        return False


def _timeout_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _clip(value: str, limit: int) -> str:
    text = str(value or "")
    max_chars = max(200, int(limit or 8000))
    return text if len(text) <= max_chars else text[:max_chars]


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
