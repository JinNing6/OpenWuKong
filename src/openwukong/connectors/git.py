# -*- coding: utf-8 -*-
"""Managed Git connector backed by deterministic git CLI execution."""

from __future__ import annotations

import dataclasses
import os
import re
import shlex
import threading
import time

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


@dataclasses.dataclass
class _GitSession:
    session_key: str
    cwd: str
    transcript: list[str] = dataclasses.field(default_factory=list)
    last_exit_code: int = 0
    command_count: int = 0
    last_command_at: float = 0.0


class GitCommandConnector(SessionConnector):
    """A deterministic connector that runs git commands inside a workspace."""

    connector_id = "git"
    display_name = "Managed Git"

    def __init__(self, *, command_timeout: float = 60.0, audit_log_path: str = ""):
        self._sessions: dict[str, _GitSession] = {}
        self._lock = threading.Lock()
        self.command_timeout = max(0.1, float(command_timeout))
        self.audit_log_path = audit_log_path

    def supports_target(self, target: ConnectorTarget) -> bool:
        process_name = (target.process_name or "").strip().lower()
        if process_name in {"git.exe", "git"}:
            return True
        return bool(re.search(r"\bgit\b", target.identity_text()))

    def match_score(self, target: ConnectorTarget) -> int:
        process_name = (target.process_name or "").strip().lower()
        if process_name in {"git.exe", "git"}:
            return 240
        if re.search(r"\bgit\b", target.identity_text()):
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
                error="empty_git_command",
            )

        try:
            git_args = self._normalize_git_args(command)
        except ValueError as exc:
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="send_message",
                error=str(exc),
            )

        report = CommandRunner(
            CommandExecutionPolicy(
                workspace_root=session.cwd,
                timeout_sec=self.command_timeout,
                audit_log_path=self.audit_log_path,
            )
        ).execute(
            CommandExecutionRequest(
                argv=("git", *git_args),
                cwd=session.cwd,
                reason="git connector command",
            )
        )
        runner_data = report.to_dict()

        stdout = (report.stdout or "").strip()
        stderr = (report.stderr or "").strip()
        session.last_exit_code = report.exit_code
        session.transcript.append(f"$ git {' '.join(git_args)}")
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
                "args": git_args,
                "stdout": stdout[-4000:],
                "stderr": stderr[-4000:],
                "exit_code": report.exit_code,
                "timeout_sec": self.command_timeout,
                "runner_mode": runner_data["mode"],
                "request_id": report.request_id,
            },
            error="" if report.ok else report.error,
        )

    def _ensure_session(self, target: ConnectorTarget) -> _GitSession:
        session_key = self._session_key(target)
        with self._lock:
            session = self._sessions.get(session_key)
            if session is not None:
                return session

            cwd = self._resolve_cwd(target)
            session = _GitSession(session_key=session_key, cwd=cwd)
            self._sessions[session_key] = session
            return session

    @staticmethod
    def _session_key(target: ConnectorTarget) -> str:
        parts = [
            target.workspace_path.strip().lower(),
            target.workspace_hint.strip().lower(),
            target.project_name.strip().lower(),
        ]
        key = "|".join(part for part in parts if part)
        return key or "git:default"

    @staticmethod
    def _resolve_cwd(target: ConnectorTarget) -> str:
        candidate = (target.workspace_path or "").strip()
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)
        return os.getcwd()

    @staticmethod
    def _normalize_git_args(command: str) -> list[str]:
        parts = shlex.split(command, posix=False)
        if not parts:
            raise ValueError("empty_git_command")
        head = parts[0].lower()
        if head == "git":
            parts = parts[1:]
        if not parts:
            raise ValueError("empty_git_command")
        return parts
