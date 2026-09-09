# -*- coding: utf-8 -*-
"""Read-only readiness probe for the OpenClaw Weixin channel.

This is deliberately separate from the desktop Weixin/File Transfer Assistant
surface. OpenClaw-Weixin is an iLink bot channel: useful for background Weixin
messaging when configured, but it does not prove control over the user's
personal desktop WeChat client.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional


_CHANNEL_ID = "openclaw-weixin"
_PACKAGE_NAME = "@tencent-weixin/openclaw-weixin"
_DEFAULT_STATE_DIR = Path.home() / ".openclaw"
_MIN_OPENCLAW_NODE = (22, 19, 0)


@dataclasses.dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "args": list(self.args),
            "returncode": int(self.returncode),
            "stdout": _bounded_text(self.stdout, limit=1200),
            "stderr": _bounded_text(self.stderr, limit=1200),
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class WeChatOpenClawReadinessReport:
    cli_path: str
    node_path: str
    node_version: str
    openclaw_version: str
    openclaw_command: dict
    state_dir: str
    config_path: str
    config_present: bool
    plugin_source: dict
    plugin_config: dict
    accounts: tuple[dict, ...]
    target_user_id: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-openclaw-readiness"

    @property
    def safety_mode(self) -> str:
        return "read_only_openclaw_config_probe"

    @property
    def plugin_enabled(self) -> bool:
        return bool(self.plugin_config.get("enabled", False))

    @property
    def account_configured(self) -> bool:
        return any(bool(item.get("configured", False)) for item in self.accounts)

    @property
    def target_ready(self) -> bool:
        return _looks_like_weixin_user_id(self.target_user_id)

    @property
    def openclaw_runtime_ready(self) -> bool:
        if not self.cli_path:
            return False
        if self.openclaw_command.get("returncode") not in (0, None):
            return False
        return bool(self.openclaw_version)

    @property
    def bot_channel_ready(self) -> bool:
        return bool(
            self.openclaw_runtime_ready
            and self.plugin_enabled
            and self.account_configured
        )

    @property
    def send_action_ready(self) -> bool:
        return bool(self.bot_channel_ready and self.target_ready)

    @property
    def ok(self) -> bool:
        return self.decision == "openclaw_weixin_bot_channel_send_ready"

    @property
    def decision(self) -> str:
        if self.error:
            return "openclaw_weixin_readiness_failed"
        if not self.cli_path:
            return "openclaw_cli_missing"
        if not self.node_version:
            return "node_runtime_missing"
        if not _node_version_at_least(self.node_version, _MIN_OPENCLAW_NODE):
            return "openclaw_cli_node_runtime_too_old"
        if self.openclaw_command.get("returncode") not in (0, None):
            return "openclaw_cli_runtime_unavailable"
        if not self.config_present:
            return "openclaw_config_missing"
        if not self.plugin_config.get("present", False):
            return "openclaw_weixin_plugin_not_configured"
        if not self.plugin_enabled:
            return "openclaw_weixin_plugin_not_enabled"
        if not self.account_configured:
            return "openclaw_weixin_account_not_logged_in"
        if not self.target_ready:
            return "openclaw_weixin_target_user_id_missing"
        return "openclaw_weixin_bot_channel_send_ready"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": False,
            "control_attempts": 0,
            "native_call_attempts": 0,
            "send_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "desktop_wechat_control_verified": False,
            "desktop_file_transfer_assistant_verified": False,
            "surface_id": "wechat-openclaw-bot-channel",
            "channel_id": _CHANNEL_ID,
            "package_name": _PACKAGE_NAME,
            "bot_channel_ready": self.bot_channel_ready,
            "send_action_ready": self.send_action_ready,
            "target_user_id_present": bool(self.target_user_id),
            "target_user_id_kind": (
                "ilink_wechat_user_id" if self.target_ready else "missing_or_invalid"
            ),
            "cli_path": self.cli_path,
            "node_path": self.node_path,
            "node_version": self.node_version,
            "node_min_required": ".".join(str(item) for item in _MIN_OPENCLAW_NODE),
            "openclaw_version": self.openclaw_version,
            "openclaw_command": dict(self.openclaw_command),
            "state_dir": self.state_dir,
            "config_path": self.config_path,
            "config_present": self.config_present,
            "plugin_source": dict(self.plugin_source),
            "plugin_config": dict(self.plugin_config),
            "accounts": [dict(item) for item in self.accounts],
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


CommandRunner = Callable[[tuple[str, ...], float], CommandResult]


def run_wechat_openclaw_readiness(
    *,
    state_dir: str = "",
    config_path: str = "",
    plugin_source_dir: str = "",
    target_user_id: str = "",
    request_timeout: float = 5.0,
    command_runner: CommandRunner | None = None,
    environment: dict | None = None,
) -> WeChatOpenClawReadinessReport:
    started = time.perf_counter()
    try:
        env = dict(os.environ if environment is None else environment)
        resolved_state_dir = _resolve_state_dir(state_dir, env)
        resolved_config_path = Path(config_path) if config_path else resolved_state_dir / "openclaw.json"
        runner = command_runner or _run_command
        cli_path = shutil.which("openclaw") or ""
        node_path = shutil.which("node") or ""
        node_result = runner(("node", "--version"), request_timeout) if node_path else CommandResult(("node", "--version"), 127, error="not_found")
        node_version = _extract_node_version(node_result.stdout or node_result.stderr)
        if not cli_path:
            openclaw_result = CommandResult(("openclaw", "--version"), 127, error="not_found")
        elif not node_version:
            openclaw_result = CommandResult(("openclaw", "--version"), 127, error="node_runtime_missing")
        elif not _node_version_at_least(node_version, _MIN_OPENCLAW_NODE):
            openclaw_result = CommandResult(("openclaw", "--version"), 126, error="node_runtime_too_old")
        else:
            openclaw_result = runner(
                _openclaw_version_command(cli_path=cli_path, node_path=node_path),
                request_timeout,
            )
        openclaw_version = _extract_openclaw_version(
            "\n".join((openclaw_result.stdout, openclaw_result.stderr))
        )
        config = _read_json_object(resolved_config_path)
        plugin_config = _extract_plugin_config(config)
        accounts = _read_openclaw_weixin_accounts(resolved_state_dir)
        plugin_source = _read_plugin_source_summary(Path(plugin_source_dir)) if plugin_source_dir else {}
        error = ""
    except Exception as exc:
        resolved_state_dir = _resolve_state_dir(state_dir, environment or os.environ)
        resolved_config_path = Path(config_path) if config_path else resolved_state_dir / "openclaw.json"
        cli_path = ""
        node_path = ""
        node_version = ""
        openclaw_version = ""
        openclaw_result = CommandResult(("openclaw", "--version"), 127)
        config = {}
        plugin_config = {}
        accounts = ()
        plugin_source = {}
        error = str(exc) or exc.__class__.__name__
    return WeChatOpenClawReadinessReport(
        cli_path=cli_path,
        node_path=node_path,
        node_version=node_version,
        openclaw_version=openclaw_version,
        openclaw_command=openclaw_result.to_dict(),
        state_dir=str(resolved_state_dir),
        config_path=str(resolved_config_path),
        config_present=bool(config),
        plugin_source=plugin_source,
        plugin_config=plugin_config,
        accounts=tuple(dict(item) for item in accounts),
        target_user_id=_redact_identifier(target_user_id),
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only OpenClaw Weixin channel readiness probe."
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

    report = run_wechat_openclaw_readiness(
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
            "OpenClaw Weixin readiness: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"accounts={len(data['accounts'])}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


def _run_command(args: tuple[str, ...], timeout: float) -> CommandResult:
    try:
        completed = subprocess.run(
            list(args),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(0.1, float(timeout or 0.1)),
        )
        return CommandResult(
            args=tuple(args),
            returncode=int(completed.returncode),
            stdout=str(completed.stdout or ""),
            stderr=str(completed.stderr or ""),
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            args=tuple(args),
            returncode=124,
            stdout=str(exc.stdout or ""),
            stderr=str(exc.stderr or ""),
            error="timeout",
        )
    except Exception as exc:
        return CommandResult(
            args=tuple(args),
            returncode=127,
            error=str(exc) or exc.__class__.__name__,
        )


def _openclaw_version_command(*, cli_path: str, node_path: str) -> tuple[str, ...]:
    cli = Path(cli_path)
    if cli.suffix.casefold() in {".cmd", ".bat"}:
        module_entry = cli.parent / "node_modules" / "openclaw" / "openclaw.mjs"
        if node_path and module_entry.is_file():
            return (node_path, str(module_entry), "--version")
    return (cli_path or "openclaw", "--version")


def _resolve_state_dir(value: str, env: dict) -> Path:
    explicit = str(value or "").strip()
    if explicit:
        return Path(explicit)
    for key in ("OPENCLAW_STATE_DIR", "CLAWDBOT_STATE_DIR"):
        env_value = str(env.get(key, "") or "").strip()
        if env_value:
            return Path(env_value)
    return _DEFAULT_STATE_DIR


def _read_json_object(path: Path) -> dict:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _extract_plugin_config(config: dict) -> dict:
    plugins = config.get("plugins")
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    entry = entries.get(_CHANNEL_ID) if isinstance(entries, dict) else None
    channels = config.get("channels")
    section = channels.get(_CHANNEL_ID) if isinstance(channels, dict) else None
    account_sections = (
        section.get("accounts")
        if isinstance(section, dict) and isinstance(section.get("accounts"), dict)
        else {}
    )
    return {
        "present": isinstance(entry, dict) or isinstance(section, dict),
        "enabled": bool(isinstance(entry, dict) and entry.get("enabled", False)),
        "channel_section_present": isinstance(section, dict),
        "account_config_count": len(account_sections) if isinstance(account_sections, dict) else 0,
        "bot_agent_configured": bool(
            isinstance(section, dict) and str(section.get("botAgent", "") or "").strip()
        ),
        "channel_config_updated_at": (
            str(section.get("channelConfigUpdatedAt", "") or "")
            if isinstance(section, dict)
            else ""
        ),
    }


def _read_openclaw_weixin_accounts(state_dir: Path) -> tuple[dict, ...]:
    plugin_state = state_dir / _CHANNEL_ID
    account_index = _read_json_array(plugin_state / "accounts.json")
    accounts_dir = plugin_state / "accounts"
    rows: list[dict] = []
    for account_id in account_index:
        row = _read_account_file(accounts_dir / f"{account_id}.json", account_id=str(account_id))
        if row:
            rows.append(row)
    if accounts_dir.is_dir():
        for path in sorted(accounts_dir.glob("*.json")):
            if path.name.endswith(".sync.json") or path.name.endswith(".context-tokens.json"):
                continue
            account_id = path.stem
            if any(item.get("account_id_hash") == _sha256_prefix(account_id) for item in rows):
                continue
            row = _read_account_file(path, account_id=account_id)
            if row:
                rows.append(row)
    legacy = _read_account_file(
        state_dir / "credentials" / _CHANNEL_ID / "credentials.json",
        account_id="legacy-single-account",
    )
    if legacy:
        legacy["legacy"] = True
        rows.append(legacy)
    return tuple(rows)


def _read_json_array(path: Path) -> tuple[str, ...]:
    try:
        if not path.is_file():
            return ()
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(str(item).strip() for item in data if str(item or "").strip())


def _read_account_file(path: Path, *, account_id: str) -> dict:
    data = _read_json_object(path)
    if not data:
        return {}
    token = str(data.get("token", "") or "")
    base_url = str(data.get("baseUrl", "") or "")
    user_id = str(data.get("userId", "") or "")
    return {
        "path": str(path),
        "account_id_hash": _sha256_prefix(account_id),
        "configured": bool(token.strip()),
        "token_present": bool(token.strip()),
        "token_length": len(token),
        "token_sha256_prefix": _sha256_prefix(token) if token else "",
        "base_url": _safe_base_url(base_url),
        "saved_at": str(data.get("savedAt", "") or ""),
        "user_id_present": bool(user_id.strip()),
        "user_id_hash": _sha256_prefix(user_id) if user_id else "",
    }


def _read_plugin_source_summary(path: Path) -> dict:
    if not path.is_dir():
        return {"present": False}
    package = _read_json_object(path / "package.json")
    manifest = _read_json_object(path / "openclaw.plugin.json")
    readme = ""
    try:
        readme = (path / "README.md").read_text(encoding="utf-8", errors="replace")
    except Exception:
        readme = ""
    return {
        "present": True,
        "package_name": str(package.get("name", "") or ""),
        "package_version": str(package.get("version", "") or ""),
        "package_author": str(package.get("author", "") or ""),
        "package_license": str(package.get("license", "") or ""),
        "peer_openclaw": _string_mapping(package.get("peerDependencies", {})).get("openclaw", ""),
        "node_engine": _string_mapping(package.get("engines", {})).get("node", ""),
        "plugin_id": str(manifest.get("id", "") or ""),
        "plugin_version": str(manifest.get("version", "") or ""),
        "channel_declared": _CHANNEL_ID in set(str(item) for item in manifest.get("channels", []) if item),
        "ilink_appid": str(package.get("ilink_appid", "") or ""),
        "readme_mentions_sendmessage": "sendmessage" in readme.casefold(),
        "readme_mentions_qr_login": "qr code" in readme.casefold() or "二维码" in readme,
    }


def _string_mapping(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _safe_base_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        from urllib.parse import urlsplit, urlunsplit

        parsed = urlsplit(text)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    except Exception:
        return ""


def _extract_node_version(text: str) -> str:
    match = re.search(r"v?(\d+\.\d+\.\d+)", str(text or ""))
    return match.group(1) if match else ""


def _extract_openclaw_version(text: str) -> str:
    match = re.search(r"(\d{4}\.\d+\.\d+)", str(text or ""))
    return match.group(1) if match else ""


def _node_version_at_least(version: str, minimum: tuple[int, int, int]) -> bool:
    parsed = _version_tuple(version)
    return parsed >= minimum if parsed else False


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(value or ""))
    if not match:
        return ()
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _looks_like_weixin_user_id(value: str) -> bool:
    raw = str(value or "").strip().casefold()
    return raw.endswith("@im.wechat") and len(raw) > len("@im.wechat")


def _redact_identifier(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    suffix = "@im.wechat" if text.casefold().endswith("@im.wechat") else ""
    return f"<sha256:{_sha256_prefix(text)}>{suffix}"


def _sha256_prefix(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]


def _bounded_text(value: str, *, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


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
    "CommandResult",
    "WeChatOpenClawReadinessReport",
    "main",
    "run_wechat_openclaw_readiness",
]


if __name__ == "__main__":
    raise SystemExit(main())
