# -*- coding: utf-8 -*-
"""Explicit opt-in real WeChat native bridge send probe."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional

from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeDryRunAdapter,
    WeChatNativeBridgeSenderAdapter,
    build_wechat_native_bridge_request,
)
from openwukong.control.wechat_native_bridge_registry import (
    discover_wechat_native_bridge_urls,
)
from openwukong.control.wechat_native_fabric_binding import (
    wechat_native_fabric_bindings_from_registry,
)


_FILE_HELPER_TARGET = "File Transfer Assistant"


@dataclasses.dataclass(frozen=True)
class WeChatNativeBridgeRealSendProbeReport:
    target_name: str
    message: str
    allow_send: bool
    explicit_urls: tuple[str, ...]
    registry_paths: tuple[str, ...]
    discovered_urls: tuple[str, ...]
    selected_bridge_url: str
    binding: dict = dataclasses.field(default_factory=dict)
    dry_run_report: dict = dataclasses.field(default_factory=dict)
    send_report: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-bridge-real-send-probe"

    @property
    def safety_mode(self) -> str:
        return "explicit_opt_in_native_bridge_execute"

    @property
    def ok(self) -> bool:
        return self.decision == "wechat_native_bridge_real_send_verified"

    @property
    def decision(self) -> str:
        if self.error:
            return "wechat_native_bridge_real_send_probe_failed"
        if not self.selected_bridge_url:
            return "wechat_native_bridge_url_missing"
        if not self.dry_run_report.get("ok", False):
            return str(
                self.dry_run_report.get("decision", "")
                or "wechat_native_bridge_request_not_ready"
            )
        if not self.allow_send:
            return "blocked_requires_explicit_opt_in"
        if not self.send_report:
            return "wechat_native_bridge_native_call_not_attempted"
        if not self.send_report.get("ok", False):
            return str(
                self.send_report.get("decision", "")
                or "wechat_native_bridge_send_failed"
            )
        return "wechat_native_bridge_real_send_verified"

    @property
    def control_allowed(self) -> bool:
        return bool(self.allow_send and self.send_report.get("control_allowed", False))

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def native_call_attempts(self) -> int:
        return _counter(self.send_report, "native_call_attempts")

    @property
    def send_attempts(self) -> int:
        return _counter(self.send_report, "send_attempts")

    @property
    def window_input_attempts(self) -> int:
        return _counter(self.send_report, "window_input_attempts")

    @property
    def keyboard_input_attempts(self) -> int:
        return _counter(self.send_report, "keyboard_input_attempts")

    @property
    def clipboard_write_attempts(self) -> int:
        return _counter(self.send_report, "clipboard_write_attempts")

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "native_call_attempts": self.native_call_attempts,
            "send_attempts": self.send_attempts,
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "target_name": self.target_name,
            "message": self.message,
            "allow_send": self.allow_send,
            "explicit_urls": list(self.explicit_urls),
            "registry_paths": list(self.registry_paths),
            "discovered_urls": list(self.discovered_urls),
            "selected_bridge_url": self.selected_bridge_url,
            "binding": dict(self.binding),
            "dry_run_report": dict(self.dry_run_report),
            "send_report": dict(self.send_report),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_wechat_native_bridge_real_send_probe(
    *,
    message: str,
    target_name: str = _FILE_HELPER_TARGET,
    allow_send: bool = False,
    bridge_urls: tuple[str, ...] = (),
    registry_paths: tuple[str, ...] = (),
    background_screenshot_focus_stable: bool = True,
    background_screenshot_count: int = 0,
    background_screenshot_success_count: int = 0,
    required_markers: tuple[str, ...] = (),
    forbidden_markers: tuple[str, ...] = (),
    request_timeout: float = 10.0,
    client: object | None = None,
    environment: dict | None = None,
) -> WeChatNativeBridgeRealSendProbeReport:
    started = time.perf_counter()
    message_text = str(message or "").strip()
    target_text = str(target_name or "").strip() or _FILE_HELPER_TARGET
    explicit_urls = _string_tuple(bridge_urls)
    registry_path_values = _string_tuple(registry_paths)
    required = _string_tuple(required_markers) or ((message_text,) if message_text else ())
    forbidden = _string_tuple(forbidden_markers)
    try:
        discovered = discover_wechat_native_bridge_urls(
            explicit_urls,
            registry_paths=registry_path_values,
            environment=environment,
        )
        bindings = wechat_native_fabric_bindings_from_registry(
            explicit_urls,
            registry_paths=registry_path_values,
            target_name=target_text,
            background_screenshot_focus_stable=background_screenshot_focus_stable,
            background_screenshot_count=background_screenshot_count,
            background_screenshot_success_count=background_screenshot_success_count,
            capability_client=client,
            capability_request_timeout=request_timeout,
        )
        binding = bindings[0] if bindings else None
        selected_url = (
            str(binding.bridge_url).strip()
            if binding is not None
            else (discovered[0] if discovered else "")
        )
        selected_target = binding.target if binding is not None else None
        request = build_wechat_native_bridge_request(
            bridge_url=selected_url,
            target_name=(
                str(getattr(selected_target, "conversation_name", "") or "").strip()
                if selected_target is not None
                else target_text
            ) or target_text,
            message=message_text,
            background_screenshot_focus_stable=(
                bool(getattr(selected_target, "background_screenshot_focus_stable", True))
                if selected_target is not None
                else background_screenshot_focus_stable
            ),
            background_screenshot_count=(
                int(getattr(selected_target, "background_screenshot_count", 0) or 0)
                if selected_target is not None
                else background_screenshot_count
            ),
            background_screenshot_success_count=(
                int(getattr(selected_target, "background_screenshot_success_count", 0) or 0)
                if selected_target is not None
                else background_screenshot_success_count
            ),
            required_markers=required,
            forbidden_markers=forbidden,
        )
        dry_run = WeChatNativeBridgeDryRunAdapter(
            client=client,
            request_timeout=request_timeout,
        ).prepare(request).to_dict()
        send_report: dict = {}
        if allow_send and dry_run.get("ok", False):
            send_report = WeChatNativeBridgeSenderAdapter(
                client=client,
                request_timeout=request_timeout,
            ).send(request).to_dict()
        binding_data = binding.to_dict() if binding is not None else {}
        error = ""
    except Exception as exc:
        discovered = ()
        selected_url = ""
        binding_data = {}
        dry_run = {}
        send_report = {}
        error = str(exc) or exc.__class__.__name__
    return WeChatNativeBridgeRealSendProbeReport(
        target_name=target_text,
        message=message_text,
        allow_send=bool(allow_send),
        explicit_urls=explicit_urls,
        registry_paths=registry_path_values,
        discovered_urls=tuple(discovered),
        selected_bridge_url=str(selected_url or ""),
        binding=binding_data,
        dry_run_report=dry_run,
        send_report=send_report,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicit opt-in WeChat native bridge real send probe."
    )
    parser.add_argument("--message", required=True)
    parser.add_argument("--target-name", default=_FILE_HELPER_TARGET)
    parser.add_argument("--bridge-url", action="append", default=[])
    parser.add_argument("--registry-path", action="append", default=[])
    parser.add_argument("--allow-send", action="store_true")
    parser.add_argument("--forbid-marker", action="append", default=[])
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--background-screenshot-count", type=int, default=0)
    parser.add_argument("--background-screenshot-success-count", type=int, default=0)
    parser.add_argument("--background-screenshot-focus-unstable", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_wechat_native_bridge_real_send_probe(
        message=args.message,
        target_name=args.target_name,
        allow_send=args.allow_send,
        bridge_urls=tuple(args.bridge_url or ()),
        registry_paths=tuple(args.registry_path or ()),
        background_screenshot_focus_stable=not args.background_screenshot_focus_unstable,
        background_screenshot_count=max(0, int(args.background_screenshot_count or 0)),
        background_screenshot_success_count=max(
            0,
            int(args.background_screenshot_success_count or 0),
        ),
        required_markers=(args.message,),
        forbidden_markers=tuple(args.forbid_marker or ()),
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
            "WeChat native bridge real send probe: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"native_calls={data['native_call_attempts']}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


def _counter(data: dict, key: str) -> int:
    try:
        return int(data.get(key, 0) or 0)
    except Exception:
        return 0


def _string_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    return tuple(str(item).strip() for item in items if str(item or "").strip())


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


if __name__ == "__main__":
    raise SystemExit(main())
