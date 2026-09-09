# -*- coding: utf-8 -*-
"""No-send setup gate for the OpenClaw Weixin bot channel.

This module intentionally prepares only an auditable setup plan. It does not
install packages, start a gateway, perform QR login, or call sendmessage.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from openwukong.evaluation.wechat_openclaw_readiness import (
    WeChatOpenClawReadinessReport,
    run_wechat_openclaw_readiness,
)


_CHANNEL_ID = "openclaw-weixin"
_PACKAGE_NAME = "@tencent-weixin/openclaw-weixin"


@dataclasses.dataclass(frozen=True)
class OpenClawSetupStep:
    action_id: str
    description: str
    command_argv: tuple[str, ...] = ()
    status: str = "proposed_only"
    requires_user_action: bool = False
    mutates_environment: bool = False
    requires_terminal_interaction: bool = False
    blocks_until_completed: bool = True
    reference: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "command_argv": list(self.command_argv),
            "status": self.status,
            "executed": False,
            "requires_user_action": self.requires_user_action,
            "mutates_environment": self.mutates_environment,
            "requires_terminal_interaction": self.requires_terminal_interaction,
            "blocks_until_completed": self.blocks_until_completed,
            "reference": self.reference,
        }


@dataclasses.dataclass(frozen=True)
class WeChatOpenClawSetupGateReport:
    readiness: dict
    blockers: tuple[dict, ...]
    setup_steps: tuple[OpenClawSetupStep, ...]
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-openclaw-setup-gate"

    @property
    def safety_mode(self) -> str:
        return "no_send_no_install_no_login_setup_plan"

    @property
    def ready_for_send_probe(self) -> bool:
        return not self.blockers and bool(self.readiness.get("send_action_ready", False))

    @property
    def ok(self) -> bool:
        return self.ready_for_send_probe

    @property
    def decision(self) -> str:
        if self.ready_for_send_probe:
            return "openclaw_weixin_setup_gate_ready_for_send_probe"
        blocker_ids = {str(item.get("id", "")) for item in self.blockers}
        if "readiness_failed" in blocker_ids:
            return "openclaw_weixin_setup_gate_readiness_failed"
        if "node_runtime_missing" in blocker_ids or "node_runtime_too_old" in blocker_ids:
            return "openclaw_weixin_setup_blocked_node_runtime"
        if "openclaw_cli_missing" in blocker_ids or "openclaw_cli_runtime_unavailable" in blocker_ids:
            return "openclaw_weixin_setup_blocked_cli_runtime"
        if (
            "openclaw_weixin_plugin_not_configured" in blocker_ids
            or "openclaw_weixin_plugin_not_enabled" in blocker_ids
        ):
            return "openclaw_weixin_setup_blocked_plugin"
        if "openclaw_weixin_account_not_logged_in" in blocker_ids:
            return "openclaw_weixin_setup_blocked_login"
        if "openclaw_weixin_target_user_id_missing" in blocker_ids:
            return "openclaw_weixin_setup_blocked_target"
        return "openclaw_weixin_setup_blocked"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": False,
            "setup_ready": self.ready_for_send_probe,
            "ready_for_send_probe": self.ready_for_send_probe,
            "requires_real_send_probe": True,
            "send_probe_not_run_reason": (
                "" if self.ready_for_send_probe else "setup_prerequisites_not_satisfied"
            ),
            "surface_id": "wechat-openclaw-bot-channel",
            "channel_id": _CHANNEL_ID,
            "package_name": _PACKAGE_NAME,
            "bot_channel_ready": bool(self.readiness.get("bot_channel_ready", False)),
            "send_action_ready": bool(self.readiness.get("send_action_ready", False)),
            "desktop_wechat_control_verified": False,
            "desktop_file_transfer_assistant_verified": False,
            "control_attempts": 0,
            "native_call_attempts": 0,
            "send_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "install_attempts": 0,
            "login_attempts": 0,
            "gateway_start_attempts": 0,
            "blockers": [dict(item) for item in self.blockers],
            "setup_steps": [step.to_dict() for step in self.setup_steps],
            "readiness_decision": self.readiness.get("decision", ""),
            "readiness": dict(self.readiness),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_wechat_openclaw_setup_gate(
    *,
    readiness_report: WeChatOpenClawReadinessReport | dict | None = None,
    state_dir: str = "",
    config_path: str = "",
    plugin_source_dir: str = "",
    target_user_id: str = "",
    request_timeout: float = 5.0,
) -> WeChatOpenClawSetupGateReport:
    started = time.perf_counter()
    if readiness_report is None:
        readiness_data = run_wechat_openclaw_readiness(
            state_dir=state_dir,
            config_path=config_path,
            plugin_source_dir=plugin_source_dir,
            target_user_id=target_user_id,
            request_timeout=request_timeout,
        ).to_dict()
    elif isinstance(readiness_report, WeChatOpenClawReadinessReport):
        readiness_data = readiness_report.to_dict()
    else:
        readiness_data = dict(readiness_report)
    blockers = _build_blockers(readiness_data)
    steps = _build_setup_steps(readiness_data, blockers)
    return WeChatOpenClawSetupGateReport(
        readiness=readiness_data,
        blockers=tuple(blockers),
        setup_steps=tuple(steps),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a no-send OpenClaw Weixin setup gate report."
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--config-path", default="")
    parser.add_argument("--plugin-source-dir", default="")
    parser.add_argument("--target-user-id", default="")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_wechat_openclaw_setup_gate(
        state_dir=args.state_dir,
        config_path=args.config_path,
        plugin_source_dir=args.plugin_source_dir,
        target_user_id=args.target_user_id,
        request_timeout=args.request_timeout,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "OpenClaw Weixin setup gate: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"blockers={len(data['blockers'])}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


def _build_blockers(readiness: dict) -> list[dict]:
    blockers: list[dict] = []
    if str(readiness.get("error", "") or "").strip():
        blockers.append(_blocker("readiness_failed", "Readiness probe failed."))

    cli_path = str(readiness.get("cli_path", "") or "").strip()
    node_version = str(readiness.get("node_version", "") or "").strip()
    node_min = str(readiness.get("node_min_required", "22.19.0") or "22.19.0")
    openclaw_command = readiness.get("openclaw_command", {})
    openclaw_returncode = (
        openclaw_command.get("returncode") if isinstance(openclaw_command, dict) else None
    )
    if not cli_path:
        blockers.append(_blocker("openclaw_cli_missing", "OpenClaw CLI is not on PATH."))
    if not node_version:
        blockers.append(_blocker("node_runtime_missing", "Node runtime is missing."))
    elif not _version_at_least(node_version, node_min):
        blockers.append(
            _blocker(
                "node_runtime_too_old",
                f"Node {node_version} is older than required {node_min}.",
            )
        )
    if openclaw_returncode not in (0, None) and _version_at_least(node_version, node_min):
        blockers.append(
            _blocker(
                "openclaw_cli_runtime_unavailable",
                "OpenClaw CLI did not return a usable version.",
            )
        )

    if not bool(readiness.get("config_present", False)):
        blockers.append(_blocker("openclaw_config_missing", "OpenClaw config is missing."))
    plugin = readiness.get("plugin_config", {})
    plugin = plugin if isinstance(plugin, dict) else {}
    if not bool(plugin.get("present", False)):
        blockers.append(
            _blocker(
                "openclaw_weixin_plugin_not_configured",
                "OpenClaw-Weixin plugin is not installed or configured.",
            )
        )
    elif not bool(plugin.get("enabled", False)):
        blockers.append(
            _blocker(
                "openclaw_weixin_plugin_not_enabled",
                "OpenClaw-Weixin plugin is configured but disabled.",
            )
        )
    accounts = readiness.get("accounts", [])
    configured_account_count = sum(
        1 for item in accounts if isinstance(item, dict) and item.get("configured", False)
    ) if isinstance(accounts, list) else 0
    if configured_account_count <= 0:
        blockers.append(
            _blocker(
                "openclaw_weixin_account_not_logged_in",
                "No redacted OpenClaw-Weixin account credential is configured.",
            )
        )
    if not bool(readiness.get("send_action_ready", False)):
        target_kind = str(readiness.get("target_user_id_kind", "") or "")
        if target_kind != "ilink_wechat_user_id":
            blockers.append(
                _blocker(
                    "openclaw_weixin_target_user_id_missing",
                    "An explicit iLink target user id ending with @im.wechat is required.",
                )
            )
    return _dedupe_blockers(blockers)


def _build_setup_steps(readiness: dict, blockers: list[dict]) -> list[OpenClawSetupStep]:
    blocker_ids = {str(item.get("id", "")) for item in blockers}
    steps: list[OpenClawSetupStep] = [
        OpenClawSetupStep(
            action_id="verify_node_runtime",
            description="Verify that the active Node runtime satisfies OpenClaw.",
            command_argv=("node", "--version"),
            status="already_satisfied" if "node_runtime_missing" not in blocker_ids and "node_runtime_too_old" not in blocker_ids else "proposed_only",
            reference="https://docs.openclaw.ai/install",
        ),
        OpenClawSetupStep(
            action_id="verify_openclaw_cli",
            description="Verify that the OpenClaw CLI is available.",
            command_argv=("openclaw", "--version"),
            status="already_satisfied" if "openclaw_cli_missing" not in blocker_ids and "openclaw_cli_runtime_unavailable" not in blocker_ids else "proposed_only",
            reference="https://docs.openclaw.ai/install",
        ),
    ]
    if "node_runtime_missing" in blocker_ids or "node_runtime_too_old" in blocker_ids:
        steps.append(
            OpenClawSetupStep(
                action_id="install_compatible_node_runtime",
                description="Install or activate Node >=22.19.0 or Node 24 before using OpenClaw.",
                requires_user_action=True,
                mutates_environment=True,
                reference="https://docs.openclaw.ai/install",
            )
        )
    if "openclaw_cli_missing" in blocker_ids or "openclaw_cli_runtime_unavailable" in blocker_ids:
        steps.append(
            OpenClawSetupStep(
                action_id="install_or_update_openclaw_cli",
                description="Install or update OpenClaw after the compatible Node runtime is active.",
                command_argv=("npm", "install", "-g", "openclaw@latest"),
                mutates_environment=True,
                reference="https://docs.openclaw.ai/install",
            )
        )

    plugin_present = "openclaw_weixin_plugin_not_configured" not in blocker_ids
    plugin_enabled = "openclaw_weixin_plugin_not_enabled" not in blocker_ids and plugin_present
    steps.append(
        OpenClawSetupStep(
            action_id="install_openclaw_weixin_plugin",
            description="Install the Tencent OpenClaw-Weixin channel plugin.",
            command_argv=("openclaw", "plugins", "install", _PACKAGE_NAME),
            status="already_satisfied" if plugin_present else "proposed_only",
            mutates_environment=not plugin_present,
            reference="https://github.com/Tencent/openclaw-weixin#manual-installation",
        )
    )
    steps.append(
        OpenClawSetupStep(
            action_id="enable_openclaw_weixin_plugin",
            description="Enable the OpenClaw-Weixin plugin in OpenClaw config.",
            command_argv=("openclaw", "config", "set", "plugins.entries.openclaw-weixin.enabled", "true"),
            status="already_satisfied" if plugin_enabled else "proposed_only",
            mutates_environment=not plugin_enabled,
            reference="https://github.com/Tencent/openclaw-weixin#manual-installation",
        )
    )

    account_ready = "openclaw_weixin_account_not_logged_in" not in blocker_ids
    steps.append(
        OpenClawSetupStep(
            action_id="login_openclaw_weixin_account",
            description="Run QR login for the OpenClaw-Weixin bot channel.",
            command_argv=("openclaw", "channels", "login", "--channel", _CHANNEL_ID),
            status="already_satisfied" if account_ready else "proposed_only",
            requires_user_action=not account_ready,
            mutates_environment=not account_ready,
            requires_terminal_interaction=not account_ready,
            reference="https://github.com/Tencent/openclaw-weixin#manual-installation",
        )
    )
    steps.append(
        OpenClawSetupStep(
            action_id="restart_openclaw_gateway",
            description="Restart the OpenClaw gateway after plugin or login changes.",
            command_argv=("openclaw", "gateway", "restart"),
            status="already_satisfied" if not _needs_gateway_restart(blocker_ids) else "proposed_only",
            mutates_environment=_needs_gateway_restart(blocker_ids),
            reference="https://github.com/Tencent/openclaw-weixin#manual-installation",
        )
    )

    target_ready = "openclaw_weixin_target_user_id_missing" not in blocker_ids
    steps.append(
        OpenClawSetupStep(
            action_id="provide_explicit_ilink_target",
            description="Provide the destination as an explicit target user id ending with @im.wechat.",
            command_argv=(
                sys.executable,
                "-m",
                "openwukong.evaluation.wechat_openclaw_setup_gate",
                "--target-user-id",
                "<target@im.wechat>",
            ),
            status="already_satisfied" if target_ready else "proposed_only",
            requires_user_action=not target_ready,
            mutates_environment=False,
            reference="https://github.com/Tencent/openclaw-weixin",
        )
    )
    steps.append(
        OpenClawSetupStep(
            action_id="rerun_openclaw_setup_gate",
            description="Re-run this no-send setup gate and inspect readiness before any real send probe.",
            command_argv=(
                sys.executable,
                "-m",
                "openwukong.evaluation.wechat_openclaw_setup_gate",
                "--target-user-id",
                "<target@im.wechat>",
                "--json",
            ),
            status="proposed_only",
            mutates_environment=False,
            blocks_until_completed=False,
            reference="https://github.com/Tencent/openclaw-weixin",
        )
    )
    return steps


def _needs_gateway_restart(blocker_ids: set[str]) -> bool:
    return bool(
        blocker_ids
        & {
            "openclaw_weixin_plugin_not_configured",
            "openclaw_weixin_plugin_not_enabled",
            "openclaw_weixin_account_not_logged_in",
        }
    )


def _blocker(identifier: str, message: str) -> dict:
    return {"id": identifier, "message": message}


def _dedupe_blockers(blockers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in blockers:
        identifier = str(item.get("id", ""))
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        result.append(item)
    return result


def _version_at_least(value: str, minimum: str) -> bool:
    parsed = _version_tuple(value)
    required = _version_tuple(minimum)
    return bool(parsed and required and parsed >= required)


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(value or ""))
    if not match:
        return ()
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


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


__all__ = [
    "OpenClawSetupStep",
    "WeChatOpenClawSetupGateReport",
    "main",
    "run_wechat_openclaw_setup_gate",
]


if __name__ == "__main__":
    raise SystemExit(main())
