# -*- coding: utf-8 -*-
"""Managed terminal connector backed by deterministic PowerShell commands."""

from __future__ import annotations

import dataclasses
import os
import re
import threading
import time
from pathlib import Path

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)
from openwukong.control.command_runner import (
    CommandExecutionPolicy,
    CommandExecutionRequest,
    CommandRunner,
)

_TERMINAL_PROCESS_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "bash.exe",
    "wsl.exe",
    "windows terminal.exe",
    "windowsterminal.exe",
}


@dataclasses.dataclass
class _TerminalSession:
    session_key: str
    workspace_root: str
    cwd: str
    transcript: list[str] = dataclasses.field(default_factory=list)
    last_exit_code: int | None = 0
    command_count: int = 0
    last_command_at: float = 0.0


class TerminalCommandConnector(SessionConnector):
    """A deterministic connector that runs commands in a managed PowerShell session."""

    connector_id = "terminal"
    display_name = "Managed Terminal"
    route_id = "terminal-native-session"
    transport = "managed-powershell-subprocess"

    def __init__(
        self,
        *,
        command_timeout: float = 60.0,
        shell_executable: str = "powershell.exe",
        audit_log_path: str = "",
    ):
        self._sessions: dict[str, _TerminalSession] = {}
        self._lock = threading.Lock()
        self.command_timeout = max(0.1, float(command_timeout))
        self.shell_executable = shell_executable
        self.audit_log_path = audit_log_path

    def supports_target(self, target: ConnectorTarget) -> bool:
        process_name = (target.process_name or "").strip().lower()
        if process_name in _TERMINAL_PROCESS_NAMES:
            return True
        return bool(re.search(r"\bterminal\b|终端", target.identity_text()))

    def match_score(self, target: ConnectorTarget) -> int:
        process_name = (target.process_name or "").strip().lower()
        if process_name in _TERMINAL_PROCESS_NAMES:
            return 240
        if re.search(r"\bterminal\b|终端", target.identity_text()):
            return 120
        return -1

    def read_conversation(self, target: ConnectorTarget) -> str:
        session = self._ensure_session(target)
        return "\n".join(session.transcript[-40:]).strip()

    def send_message(
        self,
        target: ConnectorTarget,
        message: str,
        cooldown: float = 10.0,
    ) -> ConnectorActionResult:
        session = self._ensure_session(target)
        session.last_command_at = time.time()
        session.command_count += 1

        command = (message or "").strip()
        if not command:
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="send_message",
                error="empty_command",
            )

        marker = f"__OPENWUKONG_CWD_{session.command_count}__:"
        wrapped_command = self._wrap_command_with_cwd_marker(command, marker)

        runner = CommandRunner(
            CommandExecutionPolicy(
                workspace_root=session.workspace_root,
                timeout_sec=self.command_timeout,
                audit_log_path=self.audit_log_path,
            )
        )
        report = runner.execute(
            CommandExecutionRequest(
                argv=(
                    self.shell_executable,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    wrapped_command,
                ),
                cwd=session.cwd,
                reason="terminal connector command",
            )
        )
        runner_data = report.to_dict()
        if report.timed_out:
            stdout = report.stdout.strip()
            stderr = report.stderr.strip()
            session.last_exit_code = None
            session.transcript.append(f"$ {command}")
            session.transcript.append(f"[timeout] {self.command_timeout:g}s")
            if stdout:
                session.transcript.append(stdout)
            if stderr:
                session.transcript.append(f"[stderr]\n{stderr}")
            session.transcript = session.transcript[-200:]
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="send_message",
                action_key=f"{session.session_key}:{session.command_count}",
                payload={
                    "cwd": session.cwd,
                    "route_id": self.route_id,
                    "transport": self.transport,
                    "shell": self.shell_executable,
                    "session_key": session.session_key,
                    "command_index": session.command_count,
                    "stdout": stdout[-4000:],
                    "stderr": stderr[-4000:],
                    "exit_code": None,
                    "timeout_sec": self.command_timeout,
                    "runner_mode": runner_data["mode"],
                    "request_id": report.request_id,
                },
                error="timeout",
            )

        stdout, final_cwd = self._extract_cwd_marker(report.stdout or "", marker)
        stderr = (report.stderr or "").strip()
        if final_cwd and os.path.isdir(final_cwd) and _path_is_within(final_cwd, session.workspace_root):
            session.cwd = os.path.abspath(final_cwd)
        stdout = stdout.strip()
        session.last_exit_code = report.exit_code
        session.transcript.append(f"$ {command}")
        if stdout:
            session.transcript.append(stdout)
        if stderr:
            session.transcript.append(f"[stderr]\n{stderr}")
        session.transcript.append(f"[exit_code] {report.exit_code}")
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=report.ok,
            connector_id=self.connector_id,
            action="send_message",
            action_key=f"{session.session_key}:{session.command_count}",
            payload={
                "cwd": session.cwd,
                "route_id": self.route_id,
                "transport": self.transport,
                "shell": self.shell_executable,
                "session_key": session.session_key,
                "command_index": session.command_count,
                "stdout": stdout[-4000:],
                "stderr": stderr[-4000:],
                "exit_code": report.exit_code,
                "timeout_sec": self.command_timeout,
                "runner_mode": runner_data["mode"],
                "request_id": report.request_id,
            },
            error="" if report.ok else report.error,
        )

    @staticmethod
    def _wrap_command_with_cwd_marker(command: str, marker: str) -> str:
        return (
            "try { "
            f"{command} "
            "} finally { "
            f"Write-Output \"{marker}$((Get-Location).ProviderPath)\" "
            "}"
        )

    @staticmethod
    def _extract_cwd_marker(stdout: str, marker: str) -> tuple[str, str]:
        lines = stdout.splitlines()
        final_cwd = ""
        visible: list[str] = []
        for line in lines:
            if line.startswith(marker):
                final_cwd = line[len(marker):].strip()
            else:
                visible.append(line)
        return "\n".join(visible), final_cwd

    def _ensure_session(self, target: ConnectorTarget) -> _TerminalSession:
        session_key = self._session_key(target)
        with self._lock:
            session = self._sessions.get(session_key)
            if session is not None:
                return session

            cwd = self._resolve_cwd(target)
            session = _TerminalSession(
                session_key=session_key,
                workspace_root=cwd,
                cwd=cwd,
            )
            self._sessions[session_key] = session
            return session

    @staticmethod
    def _session_key(target: ConnectorTarget) -> str:
        parts = [
            target.workspace_path.strip().lower(),
            target.workspace_hint.strip().lower(),
            target.project_name.strip().lower(),
            target.window_title.strip().lower(),
        ]
        key = "|".join(part for part in parts if part)
        return key or "terminal:default"

    @staticmethod
    def _resolve_cwd(target: ConnectorTarget) -> str:
        candidates = [
            target.workspace_path,
            target.workspace_hint,
            target.window_title,
        ]
        for candidate in candidates:
            candidate = (candidate or "").strip()
            if candidate and os.path.isdir(candidate):
                return os.path.abspath(candidate)
        return os.getcwd()


def _path_is_within(path: str, root: str) -> bool:
    try:
        normalized_path = os.path.normcase(str(Path(path).resolve()))
        normalized_root = os.path.normcase(str(Path(root).resolve()))
        return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
    except (OSError, ValueError):
        return False
