# -*- coding: utf-8 -*-
"""Read-only Codex app-server WebSocket readiness probe."""

from __future__ import annotations

import base64
import dataclasses
import json
import os
import socket
import struct
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_CODEX_APP_SERVER_TIMEOUT_SEC = 2.0
DEFAULT_CODEX_APP_SERVER_STARTUP_TIMEOUT_SEC = 10.0


@dataclasses.dataclass
class OwnedCodexAppServerWsProcess:
    codex_path: str
    workspace_path: str
    ws_url: str
    process: object
    stdout_log: str = ""
    stderr_log: str = ""
    server_socket_ready: bool = False
    startup_error: str = ""

    @property
    def mode(self) -> str:
        return "owned-codex-app-server-ws-process"

    @property
    def safety_mode(self) -> str:
        return "owned_ephemeral_loopback_app_server"

    @property
    def pid(self) -> int:
        return int(getattr(self.process, "pid", 0) or 0)

    @property
    def command(self) -> tuple[str, ...]:
        return (
            self.codex_path,
            "app-server",
            "--listen",
            self.ws_url,
        )

    @property
    def ok(self) -> bool:
        return bool(self.server_socket_ready and not self.startup_error)

    @property
    def decision(self) -> str:
        if self.ok:
            return "owned_codex_app_server_ws_ready"
        if self.startup_error:
            return "owned_codex_app_server_ws_start_failed"
        return "owned_codex_app_server_ws_socket_not_ready"

    def stop(self, *, timeout: float = 5.0) -> None:
        process = self.process
        poll = getattr(process, "poll", None)
        returncode = poll() if callable(poll) else None
        if returncode is not None:
            return
        terminate = getattr(process, "terminate", None)
        if callable(terminate):
            terminate()
        wait = getattr(process, "wait", None)
        if callable(wait):
            try:
                wait(timeout=max(0.1, float(timeout)))
                return
            except Exception:
                pass
        kill = getattr(process, "kill", None)
        if callable(kill):
            kill()
        if callable(wait):
            try:
                wait(timeout=max(0.1, float(timeout)))
            except Exception:
                pass

    def to_dict(self) -> dict:
        poll = getattr(self.process, "poll", None)
        returncode = poll() if callable(poll) else None
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "codex_path": self.codex_path,
            "workspace_path": self.workspace_path,
            "ws_url": self.ws_url,
            "pid": self.pid,
            "command": list(self.command),
            "stdout_log": self.stdout_log,
            "stderr_log": self.stderr_log,
            "server_socket_ready": self.server_socket_ready,
            "process_returncode": returncode,
            "startup_error": self.startup_error,
            "control_attempts": 0,
            "window_input_attempts": 0,
        }


def launch_owned_codex_app_server_ws(
    *,
    codex_path: str | Path,
    workspace_path: str | Path,
    output_dir: str | Path = "",
    port: int = 0,
    startup_timeout: float = DEFAULT_CODEX_APP_SERVER_STARTUP_TIMEOUT_SEC,
    popen_factory: object | None = None,
) -> OwnedCodexAppServerWsProcess:
    workspace = Path(workspace_path)
    executable = Path(codex_path)
    selected_port = int(port or _allocate_local_port())
    ws_url = f"ws://127.0.0.1:{selected_port}"
    log_root = Path(output_dir) if str(output_dir or "").strip() else workspace / "logs" / "runtime" / "codex-app-server-owned"
    log_root.mkdir(parents=True, exist_ok=True)
    stdout_log = log_root / f"codex-app-server-{selected_port}.stdout.log"
    stderr_log = log_root / f"codex-app-server-{selected_port}.stderr.log"
    command = [str(executable), "app-server", "--listen", ws_url]
    factory = popen_factory or subprocess.Popen
    process = None
    startup_error = ""
    try:
        with stdout_log.open("ab") as stdout_file, stderr_log.open("ab") as stderr_file:
            process = factory(
                command,
                cwd=str(workspace),
                stdout=stdout_file,
                stderr=stderr_file,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        socket_ready = _wait_for_tcp_socket(
            "127.0.0.1",
            selected_port,
            process=process,
            timeout=max(0.1, float(startup_timeout)),
        )
    except Exception as exc:
        startup_error = str(exc) or exc.__class__.__name__
        if process is None:
            process = _NullProcess()
        socket_ready = False
    endpoint = OwnedCodexAppServerWsProcess(
        codex_path=str(executable),
        workspace_path=str(workspace),
        ws_url=ws_url,
        process=process,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        server_socket_ready=socket_ready,
        startup_error=startup_error,
    )
    if not socket_ready:
        endpoint.stop()
    return endpoint


@dataclasses.dataclass(frozen=True)
class CodexAppServerWsProbeReport:
    ws_url: str
    initialize_response: dict = dataclasses.field(default_factory=dict)
    thread_list_response: dict = dataclasses.field(default_factory=dict)
    notifications: tuple[dict, ...] = ()
    request_attempts: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "codex-app-server-ws-probe"

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
    def background_safe(self) -> bool:
        return True

    @property
    def initialize_ok(self) -> bool:
        return bool(self.initialize_response.get("result", {}).get("codexHome"))

    @property
    def thread_list_ok(self) -> bool:
        result = self.thread_list_response.get("result")
        return isinstance(result, dict) and isinstance(result.get("data"), list)

    @property
    def ok(self) -> bool:
        return bool(not self.error and self.initialize_ok and self.thread_list_ok)

    @property
    def decision(self) -> str:
        if not self.ws_url:
            return "codex_app_server_ws_url_missing"
        if self.error:
            return "codex_app_server_ws_probe_failed"
        if not self.initialize_ok:
            return "codex_app_server_initialize_not_ready"
        if not self.thread_list_ok:
            return "codex_app_server_thread_list_not_ready"
        return "codex_app_server_ws_ready"

    def to_dict(self) -> dict:
        threads = self.thread_list_response.get("result", {}).get("data", [])
        if not isinstance(threads, list):
            threads = []
        observed_threads = _compact_threads(threads)
        selected_thread = observed_threads[0] if observed_threads else {}
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "background_safe": self.background_safe,
            "ws_url": self.ws_url,
            "request_attempts": int(self.request_attempts or 0),
            "initialize_ok": self.initialize_ok,
            "thread_list_ok": self.thread_list_ok,
            "observed_thread_count": len(threads),
            "observed_threads": observed_threads,
            "selected_thread_id": str(selected_thread.get("id", "") or ""),
            "selected_thread_cwd": str(selected_thread.get("cwd", "") or ""),
            "selected_thread_preview": str(selected_thread.get("preview", "") or ""),
            "codex_home": str(
                self.initialize_response.get("result", {}).get("codexHome", "") or ""
            ),
            "user_agent": str(
                self.initialize_response.get("result", {}).get("userAgent", "") or ""
            ),
            "platform_family": str(
                self.initialize_response.get("result", {}).get("platformFamily", "")
                or ""
            ),
            "platform_os": str(
                self.initialize_response.get("result", {}).get("platformOs", "") or ""
            ),
            "notifications": [dict(item) for item in self.notifications],
            "initialize_response": dict(self.initialize_response),
            "thread_list_response": dict(self.thread_list_response),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def probe_codex_app_server_ws(
    ws_url: str,
    *,
    request_timeout: float = DEFAULT_CODEX_APP_SERVER_TIMEOUT_SEC,
    thread_list_limit: int = 1,
    client: object | None = None,
) -> CodexAppServerWsProbeReport:
    started = time.perf_counter()
    endpoint = str(ws_url or "").strip().rstrip("/")
    if not endpoint:
        return CodexAppServerWsProbeReport(
            ws_url="",
            error="codex_app_server_ws_url_missing",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    active_client = client or CodexAppServerWsClient(request_timeout=request_timeout)
    request_attempts = 0
    try:
        call = getattr(active_client, "initialize_and_list_threads")
        data = call(
            endpoint,
            request_timeout=max(0.1, float(request_timeout)),
            thread_list_limit=max(0, int(thread_list_limit or 0)),
        )
        request_attempts = int(data.get("request_attempts", 2) or 0)
        return CodexAppServerWsProbeReport(
            ws_url=endpoint,
            initialize_response=dict(data.get("initialize_response", {}) or {}),
            thread_list_response=dict(data.get("thread_list_response", {}) or {}),
            notifications=tuple(
                dict(item)
                for item in data.get("notifications", []) or []
                if isinstance(item, dict)
            ),
            request_attempts=request_attempts,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:
        return CodexAppServerWsProbeReport(
            ws_url=endpoint,
            request_attempts=request_attempts,
            error=str(exc) or exc.__class__.__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


class CodexAppServerWsClient:
    def __init__(self, *, request_timeout: float = DEFAULT_CODEX_APP_SERVER_TIMEOUT_SEC):
        self.request_timeout = max(0.1, float(request_timeout))

    def initialize_and_list_threads(
        self,
        ws_url: str,
        *,
        request_timeout: float | None = None,
        thread_list_limit: int = 1,
    ) -> dict:
        timeout = self.request_timeout if request_timeout is None else max(0.1, float(request_timeout))
        with _JsonRpcWebSocket(ws_url, timeout=timeout) as ws:
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {
                            "name": "openwukong-codex-app-server-probe",
                            "version": "0.1.0",
                        },
                        "capabilities": {
                            "experimentalApi": True,
                            "optOutNotificationMethods": [],
                        },
                    },
                }
            )
            initialize = ws.recv_response(1)
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "thread/list",
                    "params": {
                        "limit": max(0, int(thread_list_limit or 0)),
                        "archived": False,
                        "useStateDbOnly": True,
                    },
                }
            )
            thread_list = ws.recv_response(2)
            return {
                "request_attempts": 2,
                "initialize_response": initialize,
                "thread_list_response": thread_list,
                "notifications": ws.notifications,
            }

    def initialize_start_thread_and_list_threads(
        self,
        ws_url: str,
        *,
        params: dict,
        request_timeout: float | None = None,
        thread_list_limit: int = 5,
    ) -> dict:
        timeout = self.request_timeout if request_timeout is None else max(0.1, float(request_timeout))
        with _JsonRpcWebSocket(ws_url, timeout=timeout) as ws:
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {
                            "name": "openwukong-codex-app-server-thread-start",
                            "version": "0.1.0",
                        },
                        "capabilities": {
                            "experimentalApi": True,
                            "optOutNotificationMethods": [],
                        },
                    },
                }
            )
            initialize = ws.recv_response(1)
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "thread/start",
                    "params": dict(params or {}),
                }
            )
            thread_start = ws.recv_response(2)
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "thread/list",
                    "params": {
                        "limit": max(1, int(thread_list_limit or 1)),
                        "archived": False,
                        "useStateDbOnly": True,
                    },
                }
            )
            thread_list = ws.recv_response(3)
            return {
                "request_attempts": 3,
                "initialize_response": initialize,
                "thread_start_response": thread_start,
                "thread_list_response": thread_list,
                "notifications": ws.notifications,
            }

    def initialize_start_turn_and_collect(
        self,
        ws_url: str,
        *,
        params: dict,
        request_timeout: float | None = None,
    ) -> dict:
        timeout = self.request_timeout if request_timeout is None else max(0.1, float(request_timeout))
        with _JsonRpcWebSocket(ws_url, timeout=timeout) as ws:
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {
                            "name": "openwukong-codex-app-server-turn-start",
                            "version": "0.1.0",
                        },
                        "capabilities": {
                            "experimentalApi": True,
                            "optOutNotificationMethods": [],
                        },
                    },
                }
            )
            initialize = ws.recv_response(1)
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "windowsSandbox/readiness",
                    "params": {},
                }
            )
            readiness = ws.recv_response(2)
            if _windows_sandbox_readiness_status(readiness) != "ready":
                return {
                    "request_attempts": 2,
                    "initialize_response": initialize,
                    "windows_sandbox_readiness_response": readiness,
                    "turn_start_response": {},
                    "notifications": ws.notifications,
                }
            ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "turn/start",
                    "params": dict(params or {}),
                }
            )
            turn_start = ws.recv_response(3)
            turn_id = _turn_id_from_turn_start_response(turn_start)
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    message = ws.recv_message(max(0.1, deadline - time.time()))
                except (TimeoutError, OSError, socket.timeout):
                    break
                if _is_turn_completed_message(
                    message,
                    turn_id=turn_id,
                ) or _is_terminal_sandbox_error_message(message):
                    break
            return {
                "request_attempts": 3,
                "initialize_response": initialize,
                "windows_sandbox_readiness_response": readiness,
                "turn_start_response": turn_start,
                "notifications": ws.notifications,
            }


class _JsonRpcWebSocket:
    def __init__(self, ws_url: str, *, timeout: float):
        self.ws_url = ws_url
        self.timeout = max(0.1, float(timeout))
        self.notifications: list[dict] = []
        self._socket: socket.socket | None = None

    def __enter__(self) -> "_JsonRpcWebSocket":
        self._socket = _connect_websocket(self.ws_url, timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def send_json(self, payload: dict) -> None:
        sock = self._require_socket()
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(body)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
        sock.sendall(bytes(header) + mask + masked)

    def recv_response(self, request_id: int) -> dict:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            message = self._recv_json(max(0.1, deadline - time.time()))
            if int(message.get("id", -1) or -1) == int(request_id):
                return message
            self.notifications.append(message)
        raise TimeoutError(f"codex_app_server_ws_response_timeout:{request_id}")

    def recv_message(self, timeout: float) -> dict:
        message = self._recv_json(timeout)
        self.notifications.append(message)
        return message

    def _recv_json(self, timeout: float) -> dict:
        sock = self._require_socket()
        sock.settimeout(max(0.1, float(timeout)))
        header = _recv_exact(sock, 2)
        first, second = header
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
        mask = _recv_exact(sock, 4) if second & 0x80 else b""
        payload = _recv_exact(sock, length) if length else b""
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 8:
            raise ConnectionError("codex_app_server_ws_closed")
        if opcode != 1:
            return self._recv_json(timeout)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("codex_app_server_message_not_object")
        return data

    def _require_socket(self) -> socket.socket:
        if self._socket is None:
            raise RuntimeError("codex_app_server_ws_not_connected")
        return self._socket


def _connect_websocket(ws_url: str, *, timeout: float) -> socket.socket:
    parsed = urlsplit(ws_url)
    if parsed.scheme != "ws":
        raise ValueError("codex_app_server_ws_scheme_required")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("codex_app_server_ws_localhost_required")
    port = int(parsed.port or 0)
    if port <= 0:
        raise ValueError("codex_app_server_ws_port_required")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(max(0.1, float(timeout)))
    try:
        sock.connect((parsed.hostname, port))
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
        sock.sendall(request)
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)
            if not response:
                break
        status_line = response.split(b"\r\n", 1)[0]
        if b"101" not in status_line:
            raise ConnectionError(
                response.decode("ascii", errors="replace").splitlines()[0]
                if response
                else "codex_app_server_ws_handshake_empty"
            )
        return sock
    except Exception:
        try:
            sock.close()
        except OSError:
            pass
        raise


def _allocate_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_tcp_socket(
    host: str,
    port: int,
    *,
    process: object | None,
    timeout: float,
) -> bool:
    deadline = time.time() + max(0.1, float(timeout))
    while time.time() < deadline:
        poll = getattr(process, "poll", None)
        if callable(poll) and poll() is not None:
            return False
        try:
            with socket.create_connection(
                (host, int(port)),
                timeout=min(0.25, max(0.1, deadline - time.time())),
            ):
                return True
        except OSError:
            time.sleep(0.05)
    return False


class _NullProcess:
    pid = 0

    def poll(self):
        return 1

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None

    def wait(self, timeout=None):
        del timeout
        return 1


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise ConnectionError("codex_app_server_ws_short_read")
        chunks.extend(chunk)
    return bytes(chunks)


def _compact_threads(threads: list) -> list[dict]:
    values: list[dict] = []
    for thread in threads:
        if not isinstance(thread, dict):
            continue
        values.append(
            {
                "id": str(thread.get("id", "") or ""),
                "cwd": str(thread.get("cwd", "") or ""),
                "preview": str(thread.get("preview", "") or ""),
            }
        )
    return values


def _turn_id_from_turn_start_response(response: dict) -> str:
    result = response.get("result")
    if not isinstance(result, dict):
        return ""
    turn = result.get("turn")
    if not isinstance(turn, dict):
        return ""
    return str(turn.get("id", "") or "").strip()


def _windows_sandbox_readiness_status(response: dict) -> str:
    result = response.get("result")
    if not isinstance(result, dict):
        return ""
    return str(result.get("status", "") or "").strip()


def _is_turn_completed_message(message: dict, *, turn_id: str) -> bool:
    if not isinstance(message, dict):
        return False
    if str(message.get("method", "") or "") != "turn/completed":
        return False
    params = message.get("params")
    if not isinstance(params, dict):
        return False
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return False
    observed_turn_id = str(turn.get("id", "") or "").strip()
    if turn_id and observed_turn_id and observed_turn_id != turn_id:
        return False
    return str(turn.get("status", "") or "").strip() in {
        "completed",
        "failed",
        "interrupted",
    }


def _is_terminal_sandbox_error_message(message: dict) -> bool:
    if not isinstance(message, dict):
        return False
    method = str(message.get("method", "") or "").strip().casefold()
    if method not in {"error", "server/error", "notification/error"}:
        return False
    haystack = "\n".join(_extract_all_strings(message)).casefold()
    return bool(
        "windows sandbox" in haystack
        or "spawn setup refresh" in haystack
        or "sandboxerror" in haystack
        or "sandbox error" in haystack
    )


def _extract_all_strings(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            values.extend(_extract_all_strings(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            values.extend(_extract_all_strings(child))
    return values


__all__ = [
    "CodexAppServerWsClient",
    "CodexAppServerWsProbeReport",
    "OwnedCodexAppServerWsProcess",
    "launch_owned_codex_app_server_ws",
    "probe_codex_app_server_ws",
]
