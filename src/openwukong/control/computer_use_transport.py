# -*- coding: utf-8 -*-
"""Plan-only Computer Use transport capability probe.

This module never talks to the desktop helper or executes UI input. It records
whether the bundled Computer Use client entrypoint and native pipe wiring are
present so higher-level reports can decide whether the runtime fallback is
available for read-only snapshots or still blocked.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Callable, Mapping


COMPUTER_USE_CLIENT_RELATIVE_PATH = Path("scripts") / "computer-use-client.mjs"
NATIVE_PIPE_ENV = "SKY_CUA_NATIVE_PIPE_DIRECTORY"


@dataclasses.dataclass(frozen=True)
class ComputerUseStaticProbeReport:
    plugin_root: str
    client_script_path: str
    plugin_installed: bool
    native_pipe_configured: bool
    native_pipe_directory: str = ""

    @property
    def mode(self) -> str:
        return "computer-use-static-probe"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def computer_use_attempts(self) -> int:
        return 0

    @property
    def input_actions_activate_window(self) -> bool:
        return True

    @property
    def ready(self) -> bool:
        return False

    @property
    def native_pipe_ready(self) -> bool:
        return False

    @property
    def decision(self) -> str:
        if not self.plugin_installed:
            return "computer_use_client_missing"
        if not self.native_pipe_configured:
            return "native_pipe_unavailable"
        return "computer_use_runtime_unverified"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "computer_use_attempts": self.computer_use_attempts,
            "ready": self.ready,
            "plugin_installed": self.plugin_installed,
            "native_pipe_configured": self.native_pipe_configured,
            "native_pipe_ready": self.native_pipe_ready,
            "native_pipe_directory": self.native_pipe_directory,
            "input_actions_activate_window": self.input_actions_activate_window,
            "decision": self.decision,
            "plugin_root": self.plugin_root,
            "client_script_path": self.client_script_path,
        }


@dataclasses.dataclass(frozen=True)
class ComputerUseRuntimeProbeReport:
    static_probe: dict
    runtime_probe: dict
    error: str = ""

    @property
    def mode(self) -> str:
        return "computer-use-runtime-probe"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return _int_value(self.runtime_probe.get("control_attempts"))

    @property
    def window_input_attempts(self) -> int:
        return _int_value(self.runtime_probe.get("window_input_attempts"))

    @property
    def foreground_activation_attempts(self) -> int:
        return _int_value(self.runtime_probe.get("foreground_activation_attempts"))

    @property
    def computer_use_attempts(self) -> int:
        return _int_value(self.runtime_probe.get("computer_use_attempts"))

    @property
    def plugin_installed(self) -> bool:
        return bool(self.static_probe.get("plugin_installed", False))

    @property
    def native_pipe_configured(self) -> bool:
        return bool(self.static_probe.get("native_pipe_configured", False))

    @property
    def list_apps_ready(self) -> bool:
        return bool(self.runtime_probe.get("list_apps_ready", False))

    @property
    def window_state_ready(self) -> bool:
        return bool(self.runtime_probe.get("window_state_ready", False))

    @property
    def background_snapshot_ready(self) -> bool:
        return bool(self.runtime_probe.get("background_snapshot_ready", False))

    @property
    def accessibility_tree_available(self) -> bool:
        return bool(self.runtime_probe.get("accessibility_tree_available", False))

    @property
    def input_actions_activate_window(self) -> bool:
        return True

    @property
    def decision(self) -> str:
        if not self.plugin_installed:
            return "computer_use_client_missing"
        if not self.native_pipe_configured:
            return "native_pipe_unavailable"
        if self.error:
            return "computer_use_runtime_probe_failed"
        if not self.runtime_probe:
            return "computer_use_runtime_runner_missing"
        if self.control_attempts or self.window_input_attempts or self.foreground_activation_attempts:
            return "computer_use_runtime_not_read_only"
        if not self.list_apps_ready:
            return "computer_use_list_apps_not_ready"
        if not (
            self.window_state_ready
            or self.background_snapshot_ready
            or self.accessibility_tree_available
        ):
            return "computer_use_window_state_not_ready"
        return "computer_use_read_only_ready"

    @property
    def ready(self) -> bool:
        return self.decision == "computer_use_read_only_ready"

    @property
    def native_pipe_ready(self) -> bool:
        return self.ready

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "foreground_activation_attempts": self.foreground_activation_attempts,
            "computer_use_attempts": self.computer_use_attempts,
            "ready": self.ready,
            "plugin_installed": self.plugin_installed,
            "native_pipe_configured": self.native_pipe_configured,
            "native_pipe_ready": self.native_pipe_ready,
            "native_pipe_directory": str(self.static_probe.get("native_pipe_directory", "") or ""),
            "input_actions_activate_window": self.input_actions_activate_window,
            "list_apps_attempts": _int_value(self.runtime_probe.get("list_apps_attempts")),
            "list_apps_ready": self.list_apps_ready,
            "window_state_attempts": _int_value(self.runtime_probe.get("window_state_attempts")),
            "window_state_ready": self.window_state_ready,
            "background_snapshot_ready": self.background_snapshot_ready,
            "accessibility_tree_available": self.accessibility_tree_available,
            "observed_app_count": _int_value(self.runtime_probe.get("observed_app_count")),
            "observed_window_count": _int_value(self.runtime_probe.get("observed_window_count")),
            "screenshot_count": _int_value(self.runtime_probe.get("screenshot_count")),
            "decision": self.decision,
            "error": self.error,
            "plugin_root": str(self.static_probe.get("plugin_root", "") or ""),
            "client_script_path": str(self.static_probe.get("client_script_path", "") or ""),
            "static_probe": dict(self.static_probe),
            "runtime_probe": dict(self.runtime_probe),
        }


def build_computer_use_static_probe(
    *,
    plugin_root: str | Path = "",
    env: Mapping[str, str] | None = None,
) -> ComputerUseStaticProbeReport:
    root = _resolve_plugin_root(plugin_root)
    client_script = root / COMPUTER_USE_CLIENT_RELATIVE_PATH if root else Path("")
    values = env if env is not None else os.environ
    pipe_dir = str(values.get(NATIVE_PIPE_ENV, "") or "").strip()
    return ComputerUseStaticProbeReport(
        plugin_root=str(root) if root else "",
        client_script_path=str(client_script) if client_script else "",
        plugin_installed=bool(client_script and client_script.is_file()),
        native_pipe_configured=bool(pipe_dir),
        native_pipe_directory=pipe_dir,
    )


def build_computer_use_runtime_probe(
    *,
    plugin_root: str | Path = "",
    env: Mapping[str, str] | None = None,
    runtime_probe_runner: Callable[[dict], object] | None = None,
) -> ComputerUseRuntimeProbeReport:
    static_probe = build_computer_use_static_probe(
        plugin_root=plugin_root,
        env=env,
    ).to_dict()
    if not bool(static_probe.get("plugin_installed", False)) or not bool(
        static_probe.get("native_pipe_configured", False)
    ):
        return ComputerUseRuntimeProbeReport(static_probe=static_probe, runtime_probe={})
    if runtime_probe_runner is None:
        return ComputerUseRuntimeProbeReport(static_probe=static_probe, runtime_probe={})
    try:
        runtime_probe = _dict_from_report(runtime_probe_runner(static_probe))
        return ComputerUseRuntimeProbeReport(
            static_probe=static_probe,
            runtime_probe=runtime_probe,
        )
    except Exception as exc:
        return ComputerUseRuntimeProbeReport(
            static_probe=static_probe,
            runtime_probe={
                "computer_use_attempts": 1,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "foreground_activation_attempts": 0,
            },
            error=str(exc) or exc.__class__.__name__,
        )


def _resolve_plugin_root(plugin_root: str | Path) -> Path:
    if plugin_root:
        return _select_client_root(Path(plugin_root).expanduser().resolve())
    home = Path.home()
    root = home / ".codex" / "plugins" / "cache" / "openai-bundled" / "computer-use"
    if not root.is_dir():
        return root
    return _select_client_root(root)


def _select_client_root(root: Path) -> Path:
    if (root / COMPUTER_USE_CLIENT_RELATIVE_PATH).is_file():
        return root
    try:
        version_dirs = sorted(
            (
                item
                for item in root.iterdir()
                if item.is_dir()
                and (item / COMPUTER_USE_CLIENT_RELATIVE_PATH).is_file()
            ),
            key=lambda item: item.name,
            reverse=True,
        )
    except OSError:
        return root
    return version_dirs[0] if version_dirs else root


def _dict_from_report(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
