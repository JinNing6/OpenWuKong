# -*- coding: utf-8 -*-
"""Read-only discovery for possible WeChat native transport surfaces.

This probe intentionally does not send messages. It enumerates local WeChat
processes, loopback listening ports, lightweight HTTP/CDP fingerprints, and
named-pipe candidates so unsupported internal IPC is not mistaken for a
send-capable native bridge.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


_DEFAULT_HTTP_PATHS = (
    "/",
    "/json/version",
    "/json/list",
    "/status",
    "/health",
    "/version",
)
_WECHAT_PROCESS_NAMES = ("Weixin.exe", "WeChatAppEx.exe")
_WECHAT_PIPE_PATTERNS = (
    "weixin",
    "wechat",
    "xwechat",
    "wx",
    "tencent",
    "mojo",
)


@dataclasses.dataclass(frozen=True)
class WeChatNativeTransportDiscoveryReport:
    processes: tuple[dict, ...]
    ports: tuple[dict, ...]
    named_pipes: tuple[str, ...]
    explicit_ports: tuple[int, ...]
    probe_bridge_contract: bool
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-transport-discovery"

    @property
    def safety_mode(self) -> str:
        return "read_only_discovery"

    @property
    def ok(self) -> bool:
        return self.decision == "send_capable_wechat_native_bridge_found"

    @property
    def decision(self) -> str:
        if self.error:
            return "wechat_native_transport_discovery_failed"
        if any(_port_send_ready(port) for port in self.ports):
            return "send_capable_wechat_native_bridge_found"
        if any(_port_bridge_ready(port) for port in self.ports):
            return "wechat_native_bridge_found_without_send_action"
        if any(_port_cdp_ready(port) for port in self.ports):
            return "debug_transport_found_not_wechat_send_bridge"
        if any(_port_tcp_unknown(port) for port in self.ports):
            return "wechat_loopback_ports_unknown_protocol"
        if self.processes:
            return "wechat_process_found_without_loopback_transport"
        return "wechat_native_transport_not_found"

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
            "processes": [dict(item) for item in self.processes],
            "ports": [dict(item) for item in self.ports],
            "named_pipes": list(self.named_pipes),
            "explicit_ports": list(self.explicit_ports),
            "probe_bridge_contract": self.probe_bridge_contract,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_wechat_native_transport_discovery(
    *,
    explicit_ports: tuple[int, ...] = (),
    request_timeout: float = 1.0,
    probe_bridge_contract: bool = False,
    include_named_pipes: bool = True,
    max_named_pipes: int = 200,
    http_paths: tuple[str, ...] = _DEFAULT_HTTP_PATHS,
    process_snapshot: tuple[dict, ...] | None = None,
    connection_snapshot: tuple[dict, ...] | None = None,
) -> WeChatNativeTransportDiscoveryReport:
    started = time.perf_counter()
    try:
        processes = tuple(process_snapshot) if process_snapshot is not None else _wechat_processes()
        ports = tuple(
            _probe_port(
                item,
                request_timeout=request_timeout,
                http_paths=http_paths,
                probe_bridge_contract=probe_bridge_contract,
            )
            for item in _candidate_ports(
                processes,
                explicit_ports=explicit_ports,
                connection_snapshot=connection_snapshot,
            )
        )
        named_pipes = (
            _wechat_named_pipes(limit=max(0, int(max_named_pipes or 0)))
            if include_named_pipes
            else ()
        )
        error = ""
    except Exception as exc:
        processes = ()
        ports = ()
        named_pipes = ()
        error = str(exc) or exc.__class__.__name__
    return WeChatNativeTransportDiscoveryReport(
        processes=tuple(dict(item) for item in processes),
        ports=tuple(dict(item) for item in ports),
        named_pipes=tuple(str(item) for item in named_pipes),
        explicit_ports=_int_tuple(explicit_ports),
        probe_bridge_contract=bool(probe_bridge_contract),
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only WeChat native transport discovery."
    )
    parser.add_argument("--port", action="append", type=int, default=[])
    parser.add_argument("--request-timeout", type=float, default=1.0)
    parser.add_argument("--probe-bridge-contract", action="store_true")
    parser.add_argument("--skip-named-pipes", action="store_true")
    parser.add_argument("--max-named-pipes", type=int, default=200)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_wechat_native_transport_discovery(
        explicit_ports=tuple(args.port or ()),
        request_timeout=args.request_timeout,
        probe_bridge_contract=args.probe_bridge_contract,
        include_named_pipes=not args.skip_named_pipes,
        max_named_pipes=args.max_named_pipes,
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
            "WeChat native transport discovery: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"ports={len(data['ports'])}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


def _wechat_processes() -> tuple[dict, ...]:
    try:
        import psutil
    except Exception:
        return ()

    rows: list[dict] = []
    attrs = ("pid", "name", "exe", "cmdline")
    for proc in psutil.process_iter(attrs, ad_value=""):
        info = dict(getattr(proc, "info", {}) or {})
        name = str(info.get("name", "") or "")
        exe = str(info.get("exe", "") or "")
        cmdline = _cmdline_text(info.get("cmdline", ""))
        if not _is_personal_wechat_process(name, exe, cmdline):
            continue
        rows.append(
            {
                "pid": int(info.get("pid", 0) or 0),
                "name": name,
                "exe": exe,
                "cmdline": _bounded_text(cmdline, limit=1000),
            }
        )
    return tuple(sorted(rows, key=lambda item: (str(item.get("name", "")), int(item.get("pid", 0)))))


def _candidate_ports(
    processes: tuple[dict, ...],
    *,
    explicit_ports: tuple[int, ...],
    connection_snapshot: tuple[dict, ...] | None,
) -> tuple[dict, ...]:
    process_by_pid = {int(item.get("pid", 0) or 0): dict(item) for item in processes}
    candidates: dict[int, dict] = {}
    for port in _int_tuple(explicit_ports):
        if port > 0:
            candidates[port] = {
                "host": "127.0.0.1",
                "port": port,
                "pid": 0,
                "process": {},
                "source": "explicit",
            }
    connections = (
        tuple(connection_snapshot)
        if connection_snapshot is not None
        else _listening_tcp_connections()
    )
    for conn in connections:
        pid = int(conn.get("pid", 0) or 0)
        if pid not in process_by_pid:
            continue
        host = str(conn.get("host", "") or "")
        if not _is_loopback_or_any(host):
            continue
        port = int(conn.get("port", 0) or 0)
        if port <= 0:
            continue
        candidates[port] = {
            "host": _connect_host(host),
            "port": port,
            "pid": pid,
            "process": dict(process_by_pid.get(pid, {})),
            "source": "psutil.net_connections",
        }
    return tuple(candidates[port] for port in sorted(candidates))


def _listening_tcp_connections() -> tuple[dict, ...]:
    try:
        import psutil
    except Exception:
        return ()

    rows: list[dict] = []
    try:
        connections = psutil.net_connections(kind="tcp")
    except Exception:
        return ()
    for conn in connections:
        if str(getattr(conn, "status", "") or "").upper() != "LISTEN":
            continue
        laddr = getattr(conn, "laddr", None)
        host = str(getattr(laddr, "ip", "") or "")
        port = int(getattr(laddr, "port", 0) or 0)
        rows.append({"host": host, "port": port, "pid": int(getattr(conn, "pid", 0) or 0)})
    return tuple(rows)


def _probe_port(
    item: dict,
    *,
    request_timeout: float,
    http_paths: tuple[str, ...],
    probe_bridge_contract: bool,
) -> dict:
    host = _connect_host(str(item.get("host", "") or "127.0.0.1"))
    port = int(item.get("port", 0) or 0)
    report = dict(item)
    report.update(
        {
            "host": host,
            "port": port,
            "tcp_connect": False,
            "http_probes": [],
            "bridge_contract_probe": {},
            "protocol_guess": "unreachable",
        }
    )
    try:
        with socket.create_connection((host, port), timeout=max(0.1, request_timeout)):
            report["tcp_connect"] = True
    except Exception as exc:
        report["tcp_error"] = exc.__class__.__name__
        return report

    http_probes = tuple(
        _http_get_probe(host, port, path, timeout=request_timeout)
        for path in tuple(http_paths or ())
    )
    report["http_probes"] = [dict(item) for item in http_probes]
    if probe_bridge_contract:
        report["bridge_contract_probe"] = _bridge_contract_probe(
            host,
            port,
            timeout=request_timeout,
        )
    report["protocol_guess"] = _protocol_guess(report)
    return report


def _http_get_probe(host: str, port: int, path: str, *, timeout: float) -> dict:
    clean_path = str(path or "/").strip() or "/"
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path
    url = f"http://{host}:{int(port)}{clean_path}"
    result = {"method": "GET", "path": clean_path, "http_like": False}
    try:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "openwukong-wechat-readonly-discovery/1"},
        )
        with urllib.request.urlopen(request, timeout=max(0.1, timeout)) as response:
            body = response.read(512)
            result.update(
                {
                    "http_like": True,
                    "status": int(getattr(response, "status", 0) or 0),
                    "content_type": str(response.headers.get("Content-Type", "") or ""),
                    "body_prefix": _decode_body_prefix(body),
                    "json": _decode_json_object(body),
                }
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(512)
        result.update(
            {
                "http_like": True,
                "http_error": int(exc.code or 0),
                "body_prefix": _decode_body_prefix(body),
                "json": _decode_json_object(body),
            }
        )
    except Exception as exc:
        result["error"] = exc.__class__.__name__
    return result


def _bridge_contract_probe(host: str, port: int, *, timeout: float) -> dict:
    url = f"http://{host}:{int(port)}/v1/wechat/capabilities"
    payload = json.dumps(
        {
            "action": "read_capabilities",
            "target_name": "File Transfer Assistant",
        },
        ensure_ascii=True,
    ).encode("utf-8")
    result = {"method": "POST", "path": "/v1/wechat/capabilities", "attempted": True}
    try:
        request = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "openwukong-wechat-readonly-discovery/1",
            },
        )
        with urllib.request.urlopen(request, timeout=max(0.1, timeout)) as response:
            body = response.read(4096)
            data = _decode_json_object(body)
            result.update(
                {
                    "http_like": True,
                    "status": int(getattr(response, "status", 0) or 0),
                    "body_prefix": _decode_body_prefix(body),
                    "json": data,
                    "bridge_ready": bool(isinstance(data, dict) and data.get("ok", False)),
                    "send_action_ready": _send_action_ready(data),
                }
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(512)
        result.update(
            {
                "http_like": True,
                "http_error": int(exc.code or 0),
                "body_prefix": _decode_body_prefix(body),
                "json": _decode_json_object(body),
                "bridge_ready": False,
                "send_action_ready": False,
            }
        )
    except Exception as exc:
        result.update(
            {
                "error": exc.__class__.__name__,
                "bridge_ready": False,
                "send_action_ready": False,
            }
        )
    return result


def _wechat_named_pipes(*, limit: int) -> tuple[str, ...]:
    if os.name != "nt" or limit <= 0:
        return ()
    try:
        names = os.listdir(r"\\.\pipe\\")
    except Exception:
        return ()
    selected = []
    for name in names:
        lowered = str(name or "").casefold()
        if any(pattern in lowered for pattern in _WECHAT_PIPE_PATTERNS):
            selected.append(_sanitize_pipe_name(str(name)))
        if len(selected) >= limit:
            break
    return tuple(sorted(selected))


def _protocol_guess(report: dict) -> str:
    bridge = report.get("bridge_contract_probe")
    if isinstance(bridge, dict) and bridge.get("bridge_ready"):
        if bridge.get("send_action_ready"):
            return "wechat-native-bridge-send-ready"
        return "wechat-native-bridge-read-only"
    if any(_http_probe_cdp_ready(item) for item in report.get("http_probes", []) or []):
        return "chrome-devtools-protocol"
    if any(bool(item.get("http_like", False)) for item in report.get("http_probes", []) or []):
        return "http"
    if bool(report.get("tcp_connect", False)):
        return "tcp-unknown"
    return "unreachable"


def _http_probe_cdp_ready(item: dict) -> bool:
    data = item.get("json")
    if not isinstance(data, dict):
        return False
    return bool(data.get("Browser") or data.get("Protocol-Version") or data.get("webSocketDebuggerUrl"))


def _port_send_ready(port: dict) -> bool:
    bridge = port.get("bridge_contract_probe")
    return bool(isinstance(bridge, dict) and bridge.get("bridge_ready") and bridge.get("send_action_ready"))


def _port_bridge_ready(port: dict) -> bool:
    bridge = port.get("bridge_contract_probe")
    return bool(isinstance(bridge, dict) and bridge.get("bridge_ready"))


def _port_cdp_ready(port: dict) -> bool:
    return str(port.get("protocol_guess", "") or "") == "chrome-devtools-protocol"


def _port_tcp_unknown(port: dict) -> bool:
    return str(port.get("protocol_guess", "") or "") == "tcp-unknown"


def _send_action_ready(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("send_action_ready", "send_ready", "can_send", "can_send_message"):
        if key in data:
            return bool(data.get(key, False))
    capabilities = data.get("capabilities")
    if isinstance(capabilities, list):
        normalized = {str(item or "").strip().casefold() for item in capabilities}
        return bool(
            normalized
            & {
                "wechat.conversation.native_bridge_send_message",
                "wechat.conversation.send_message",
                "wechat.send_message",
                "send_message",
            }
        )
    return False


def _is_personal_wechat_process(name: str, exe: str, cmdline: str) -> bool:
    text = " ".join((name, exe, cmdline)).casefold()
    if "wxwork" in text or "wecom" in text or "enterprise wechat" in text:
        return False
    process = str(name or "").strip().casefold()
    if process == "weixin.exe":
        return True
    if process == "wechatappex.exe" and "xwechat" in text:
        return True
    return False


def _is_loopback_or_any(host: str) -> bool:
    value = str(host or "").strip().casefold()
    return value in {"", "0.0.0.0", "::", "127.0.0.1", "::1", "localhost"}


def _connect_host(host: str) -> str:
    value = str(host or "").strip()
    if value in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    if value == "::1":
        return "localhost"
    return value


def _decode_body_prefix(raw: bytes, *, limit: int = 240) -> str:
    return bytes(raw or b"")[:limit].decode("utf-8", errors="replace")


def _decode_json_object(raw: bytes) -> dict:
    try:
        data = json.loads(bytes(raw or b"").decode("utf-8-sig"))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _cmdline_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _int_tuple(values: object) -> tuple[int, ...]:
    if values is None:
        return ()
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    result = []
    for item in items:
        try:
            value = int(item)
        except Exception:
            continue
        if value > 0:
            result.append(value)
    return tuple(result)


def _bounded_text(value: object, *, limit: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _sanitize_pipe_name(value: str) -> str:
    text = str(value or "")
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "<redacted-email>",
        text,
    )
    return text


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
    "WeChatNativeTransportDiscoveryReport",
    "main",
    "run_wechat_native_transport_discovery",
]


if __name__ == "__main__":
    raise SystemExit(main())
