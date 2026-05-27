# -*- coding: utf-8 -*-
"""Persistent process broker API over CommandProcessRegistry."""

from __future__ import annotations

import dataclasses
import os

from openwukong.control.command_runner import (
    CommandExecutionRequest,
    CommandProcessRegistry,
    build_command_execution_policy,
)
from openwukong.control.session_ownership import SessionOwnership


@dataclasses.dataclass(frozen=True)
class CommandProcessBrokerConfig:
    workspace_root: str = ""
    storage_path: str = ""
    profile_id: str = "workspace-write"
    timeout_sec: float = 60.0
    audit_log_path: str = ""
    require_owned_session: bool = False


class CommandProcessBroker:
    """Unified API for persistent start/snapshot/stop process operations."""

    def __init__(self, config: CommandProcessBrokerConfig | None = None):
        self.config = config or CommandProcessBrokerConfig()
        self._registry = CommandProcessRegistry(
            build_command_execution_policy(
                self.config.profile_id,
                workspace_root=self.config.workspace_root,
                timeout_sec=max(0.1, float(self.config.timeout_sec or 60.0)),
                audit_log_path=self.config.audit_log_path,
                require_owned_session=self.config.require_owned_session,
            ),
            storage_path=self.config.storage_path,
        )

    def start(
        self,
        *,
        argv: tuple[str, ...],
        cwd: str = "",
        effects: tuple[str, ...] = (),
        reason: str = "",
        env: dict[str, str] | None = None,
        ownership: SessionOwnership | None = None,
        allow_control: bool = False,
    ) -> dict:
        request = CommandExecutionRequest(
            argv=tuple(str(item) for item in argv if str(item)),
            cwd=str(cwd or self.config.workspace_root or os.getcwd()),
            effects=tuple(str(item).strip().lower() for item in effects if str(item).strip()),
            reason=reason,
            env=dict(env or {}),
            ownership=ownership or SessionOwnership.unowned(),
        )
        if not allow_control:
            return _blocked_start_report(
                request,
                error="explicit_control_permission_required",
                ownership_required=self.config.require_owned_session,
            )
        return _start_report(self._registry.start(request))

    def snapshot(self) -> dict:
        data = dict(self._registry.snapshot())
        data["mode"] = "command-process-broker-snapshot"
        data["broker"] = self._broker_dict()
        return data

    def stop(
        self,
        process_id: str,
        *,
        allow_control: bool = False,
        grace_seconds: float = 2.0,
    ) -> dict:
        if not allow_control:
            return _blocked_stop_report(
                process_id,
                error="explicit_control_permission_required",
            )
        return _stop_report(
            self._registry.stop(process_id, grace_seconds=grace_seconds)
        )

    def stop_all(
        self,
        *,
        allow_control: bool = False,
        grace_seconds: float = 2.0,
    ) -> dict:
        if not allow_control:
            return {
                "mode": "command-process-broker-stop-all",
                "safety_mode": "explicit_control_gate",
                "ok": False,
                "control_allowed": False,
                "control_attempts": 0,
                "stopped_count": 0,
                "reports": [],
                "error": "explicit_control_permission_required",
                "broker": self._broker_dict(),
            }
        reports = [
            _stop_report(report)
            for report in self._registry.stop_all(grace_seconds=grace_seconds)
        ]
        return {
            "mode": "command-process-broker-stop-all",
            "safety_mode": "explicit_control_gate",
            "ok": all(report.get("ok") for report in reports),
            "control_allowed": bool(reports),
            "control_attempts": sum(int(report.get("control_attempts", 0) or 0) for report in reports),
            "stopped_count": len(reports),
            "reports": reports,
            "error": "" if all(report.get("ok") for report in reports) else "stop_failed",
            "broker": self._broker_dict(),
        }

    def _broker_dict(self) -> dict:
        return {
            "workspace_root": self.config.workspace_root,
            "storage_path": self.config.storage_path,
            "profile_id": self.config.profile_id,
            "timeout_sec": self.config.timeout_sec,
            "audit_log_path": self.config.audit_log_path,
            "require_owned_session": self.config.require_owned_session,
        }


def _blocked_start_report(
    request: CommandExecutionRequest,
    *,
    error: str,
    ownership_required: bool,
) -> dict:
    return {
        "mode": "command-process-broker-start",
        "safety_mode": "explicit_control_gate",
        "ok": False,
        "control_allowed": False,
        "control_attempts": 0,
        "process_id": "",
        "pid": 0,
        "argv": list(request.argv),
        "cwd": request.cwd,
        "ownership_required": ownership_required,
        "ownership": request.ownership.to_dict(),
        "error": error,
        "process_report": {},
    }


def _blocked_stop_report(process_id: str, *, error: str) -> dict:
    return {
        "mode": "command-process-broker-stop",
        "safety_mode": "explicit_control_gate",
        "ok": False,
        "found": False,
        "control_allowed": False,
        "control_attempts": 0,
        "process_id": str(process_id or ""),
        "pid": 0,
        "terminated": False,
        "killed": False,
        "exit_code": None,
        "error": error,
        "process_report": {},
    }


def _start_report(report) -> dict:
    data = report.to_dict()
    return {
        "mode": "command-process-broker-start",
        "safety_mode": "explicit_control_gate",
        "ok": data["ok"],
        "control_allowed": data["control_allowed"],
        "control_attempts": data["control_attempts"],
        "process_id": data["process_id"],
        "pid": data["pid"],
        "argv": data["argv"],
        "cwd": data["cwd"],
        "ownership_required": data["ownership_required"],
        "ownership": data["ownership"],
        "error": data["error"],
        "process_report": data,
    }


def _stop_report(report) -> dict:
    data = report.to_dict()
    return {
        "mode": "command-process-broker-stop",
        "safety_mode": "explicit_control_gate",
        "ok": data["ok"],
        "found": data["found"],
        "control_allowed": data["control_allowed"],
        "control_attempts": data["control_attempts"],
        "process_id": data["process_id"],
        "pid": data["pid"],
        "terminated": data["terminated"],
        "killed": data["killed"],
        "exit_code": data["exit_code"],
        "error": data["error"],
        "process_report": data,
    }
