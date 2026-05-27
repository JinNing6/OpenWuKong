# -*- coding: utf-8 -*-
"""Structured command planning before argv-only execution."""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

from openwukong.control.command_runner import (
    CommandExecutionPolicy,
    CommandExecutionRequest,
    build_command_execution_policy,
)
from openwukong.control.session_ownership import SessionOwnership


_SHELL_LAUNCHERS = {
    "bash",
    "bash.exe",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "sh",
    "sh.exe",
}
_DOCKER_COMPOSE_READ_OPERATIONS = {
    "docker.compose.config": "config",
    "docker.compose.logs": "logs",
    "docker.compose.ps": "ps",
}


@dataclasses.dataclass(frozen=True)
class CommandPlanIntent:
    """Structured model output that can be converted into a runner request."""

    operation: str = "raw.argv"
    workspace_root: str = ""
    cwd: str = ""
    argv: tuple[str, ...] = ()
    args: tuple[str, ...] = ()
    command: str = ""
    reason: str = ""
    effects: tuple[str, ...] = ()
    profile_id: str = ""
    timeout_sec: float = 60.0
    audit_log_path: str = ""
    require_owned_session: bool = False
    max_output_chars: int = 8000
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    ownership: SessionOwnership = dataclasses.field(default_factory=SessionOwnership.unowned)

    @classmethod
    def from_dict(cls, data: dict) -> "CommandPlanIntent":
        if not isinstance(data, dict):
            data = {}
        ownership = data.get("ownership")
        return cls(
            operation=str(data.get("operation", "raw.argv") or "raw.argv"),
            workspace_root=str(data.get("workspace_root", data.get("workspace_path", "")) or ""),
            cwd=str(data.get("cwd", "") or ""),
            argv=_string_tuple(data.get("argv")),
            args=_string_tuple(data.get("args")),
            command=str(data.get("command", "") or ""),
            reason=str(data.get("reason", "") or ""),
            effects=_normalized_effects(data.get("effects")),
            profile_id=str(data.get("profile_id", data.get("profile", "")) or ""),
            timeout_sec=_safe_float(data.get("timeout_sec", data.get("timeout", 60.0)), 60.0),
            audit_log_path=str(data.get("audit_log_path", data.get("audit_log", "")) or ""),
            require_owned_session=bool(data.get("require_owned_session", False)),
            max_output_chars=_safe_int(data.get("max_output_chars", 8000), 8000),
            env=_string_dict(data.get("env")),
            ownership=_ownership_from_dict(ownership),
        )

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "workspace_root": self.workspace_root,
            "cwd": self.cwd,
            "argv": list(self.argv),
            "args": list(self.args),
            "command_present": bool(self.command),
            "reason": self.reason,
            "effects": list(self.effects),
            "profile_id": self.profile_id,
            "timeout_sec": self.timeout_sec,
            "audit_log_path": self.audit_log_path,
            "require_owned_session": self.require_owned_session,
            "max_output_chars": self.max_output_chars,
            "env_keys": sorted(str(key) for key in self.env),
            "ownership": self.ownership.to_dict(),
        }


@dataclasses.dataclass(frozen=True)
class CommandPlanReport:
    """Plan-only report that can feed CommandRunner without shell strings."""

    intent: CommandPlanIntent
    ok: bool
    execution_request: CommandExecutionRequest
    policy: CommandExecutionPolicy
    error: str = ""

    @property
    def mode(self) -> str:
        return "command-intelligence-plan"

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
            "ok": self.ok,
            "error": self.error,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "operation": _normalize_operation(self.intent.operation),
            "argv": list(self.execution_request.argv),
            "cwd": self.execution_request.cwd,
            "workspace_root": self.policy.workspace_root,
            "effects": list(self.execution_request.effects),
            "profile_id": self.policy.profile_id,
            "reason": self.execution_request.reason,
            "ownership_required": self.policy.require_owned_session,
            "ownership": self.execution_request.ownership.to_dict(),
            "shell": False,
            "policy": {
                "profile_id": self.policy.profile_id,
                "allowed_effects": list(self.policy.allowed_effects),
                "workspace_root": self.policy.workspace_root,
                "timeout_sec": self.policy.timeout_sec,
                "audit_log_path": self.policy.audit_log_path,
                "require_owned_session": self.policy.require_owned_session,
                "max_output_chars": self.policy.max_output_chars,
                "forbid_elevation": self.policy.forbid_elevation,
            },
            "intent": self.intent.to_dict(),
        }


class CommandPlanner:
    """Convert structured command intents into least-privilege runner inputs."""

    def plan(self, intent: CommandPlanIntent | dict) -> CommandPlanReport:
        normalized_intent = (
            intent
            if isinstance(intent, CommandPlanIntent)
            else CommandPlanIntent.from_dict(intent if isinstance(intent, dict) else {})
        )
        operation = _normalize_operation(normalized_intent.operation)
        workspace_root = str(normalized_intent.workspace_root or "").strip()
        cwd = str(normalized_intent.cwd or workspace_root or os.getcwd()).strip()

        argv, argv_error = _argv_for_operation(operation, normalized_intent)
        effects = _effects_for_operation(operation, normalized_intent)
        profile_id = _profile_for_effects(effects, normalized_intent.profile_id)
        policy = build_command_execution_policy(
            profile_id,
            workspace_root=workspace_root or cwd,
            timeout_sec=max(0.1, float(normalized_intent.timeout_sec or 60.0)),
            audit_log_path=normalized_intent.audit_log_path,
            require_owned_session=normalized_intent.require_owned_session,
            max_output_chars=normalized_intent.max_output_chars,
        )
        request = CommandExecutionRequest(
            argv=argv,
            cwd=cwd,
            reason=normalized_intent.reason,
            effects=effects,
            env=normalized_intent.env,
            ownership=normalized_intent.ownership,
        )

        error = (
            _shell_command_error(normalized_intent)
            or argv_error
            or _shell_launcher_error(argv)
            or _workspace_error(workspace_root, cwd)
            or _effect_error(effects, policy)
        )
        if error:
            request = dataclasses.replace(
                request,
                argv=() if error == "shell_command_not_allowed" else request.argv,
            )
        return CommandPlanReport(
            intent=normalized_intent,
            ok=not bool(error),
            execution_request=request,
            policy=policy,
            error=error,
        )


def plan_command_intent(intent: CommandPlanIntent | dict) -> CommandPlanReport:
    return CommandPlanner().plan(intent)


def _argv_for_operation(
    operation: str,
    intent: CommandPlanIntent,
) -> tuple[tuple[str, ...], str]:
    if operation == "raw.argv":
        argv = _string_tuple(intent.argv)
        return argv, "" if argv else "empty_argv"
    if operation == "git.status":
        return ("git", "status", "--short"), ""
    if operation == "git.diff":
        return ("git", "diff", *intent.args), ""
    if operation == "git.log":
        return ("git", "log", "--oneline", *intent.args), ""
    if operation == "python.module":
        if not intent.args:
            return (), "python_module_required"
        module, *args = intent.args
        return (sys.executable, "-m", module, *args), ""
    if operation == "pytest.run":
        return (sys.executable, "-m", "pytest", *intent.args), ""
    if operation == "npm.run":
        if not intent.args:
            return (), "npm_script_required"
        script_name, *script_args = intent.args
        argv = (_platform_command("npm"), "run", script_name)
        if not script_args:
            return argv, ""
        if script_args[0] == "--":
            return (*argv, *script_args), ""
        return (*argv, "--", *script_args), ""
    if operation == "uv.run":
        if not intent.args:
            return (), "uv_command_required"
        wrapped_shell_error = _shell_launcher_error(intent.args[:1])
        if wrapped_shell_error:
            return (_platform_command("uv"), "run", *intent.args), wrapped_shell_error
        return (_platform_command("uv"), "run", *intent.args), ""
    if operation in _DOCKER_COMPOSE_READ_OPERATIONS:
        return (
            "docker",
            "compose",
            _DOCKER_COMPOSE_READ_OPERATIONS[operation],
            *intent.args,
        ), ""
    if operation == "docker.compose.dry-run-up":
        return ("docker", "compose", "--dry-run", "up", *intent.args), ""
    if operation == "docker.compose.up":
        return ("docker", "compose", "up", *intent.args), ""
    return (), f"unsupported_operation:{operation}"


def _effects_for_operation(
    operation: str,
    intent: CommandPlanIntent,
) -> tuple[str, ...]:
    if intent.effects:
        return _normalized_effects(intent.effects)
    if operation.startswith("git.") or operation == "python.module":
        return ("read",)
    if operation == "pytest.run":
        return ("workspace_write",)
    if operation in {"npm.run", "uv.run"}:
        return ("workspace_write",)
    if (
        operation in _DOCKER_COMPOSE_READ_OPERATIONS
        or operation == "docker.compose.dry-run-up"
    ):
        return ("read",)
    if operation == "docker.compose.up":
        return ("network",)
    return ("read",)


def _profile_for_effects(effects: tuple[str, ...], explicit_profile: str) -> str:
    explicit = str(explicit_profile or "").strip().lower().replace("_", "-")
    if explicit:
        return explicit
    effect_set = set(effects)
    if "network" in effect_set:
        return "network-enabled"
    if "workspace_write" in effect_set:
        return "workspace-write"
    return "read-only"


def _shell_command_error(intent: CommandPlanIntent) -> str:
    return "shell_command_not_allowed" if str(intent.command or "").strip() else ""


def _shell_launcher_error(argv: tuple[str, ...]) -> str:
    if not argv:
        return ""
    executable = Path(str(argv[0])).name.lower()
    if executable not in _SHELL_LAUNCHERS:
        return ""
    return f"shell_launcher_not_allowed:{executable}"


def _platform_command(name: str) -> str:
    return f"{name}.cmd" if os.name == "nt" else name


def _workspace_error(workspace_root: str, cwd: str) -> str:
    if not cwd:
        return "cwd_required"
    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        return "cwd_not_directory"
    if workspace_root and not _is_relative_to(cwd_path, Path(workspace_root)):
        return "cwd_outside_workspace"
    return ""


def _effect_error(effects: tuple[str, ...], policy: CommandExecutionPolicy) -> str:
    allowed = set(policy.allowed_effects)
    for effect in effects:
        if policy.forbid_elevation and effect == "elevated":
            return "effect_not_allowed:elevated"
        if effect not in allowed:
            return f"effect_not_allowed:{effect}"
    return ""


def _normalize_operation(value: str) -> str:
    operation = str(value or "raw.argv").strip().lower().replace("_", ".")
    return operation or "raw.argv"


def _normalized_effects(value) -> tuple[str, ...]:
    return tuple(
        str(item).strip().lower()
        for item in _iterable(value)
        if str(item).strip()
    )


def _string_tuple(value) -> tuple[str, ...]:
    return tuple(str(item) for item in _iterable(value) if str(item))


def _iterable(value) -> tuple:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _string_dict(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key).strip()
    }


def _ownership_from_dict(value) -> SessionOwnership:
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
        pid=_safe_int(value.get("pid"), 0),
        endpoint=str(value.get("endpoint", "") or ""),
        profile_path=str(value.get("profile_path", "") or ""),
        extensions_path=str(value.get("extensions_path", "") or ""),
        workspace_root=str(value.get("workspace_root", "") or ""),
        cleanup_ready=bool(value.get("cleanup_ready", False)),
    )


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
