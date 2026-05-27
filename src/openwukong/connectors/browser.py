# -*- coding: utf-8 -*-
"""Managed browser connector backed by HTTP and DevTools routes."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import html
import json
import os
import re
import shlex
import socket
import ssl
import struct
import threading
import time
from urllib.parse import urljoin, urlparse

import requests

from openwukong.connectors.base import (
    ConnectorActionResult,
    ConnectorTarget,
    SessionConnector,
)

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}
_BROWSER_PROCESS_NAMES = {
    "msedge.exe",
    "chrome.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "browser.exe",
}


@dataclasses.dataclass(frozen=True)
class BrowserDevToolsTarget:
    target_id: str
    type: str
    title: str
    url: str
    web_socket_debugger_url: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "BrowserDevToolsTarget":
        return cls(
            target_id=str(data.get("id", "") or data.get("targetId", "") or ""),
            type=str(data.get("type", "") or ""),
            title=str(data.get("title", "") or ""),
            url=str(data.get("url", "") or ""),
            web_socket_debugger_url=str(data.get("webSocketDebuggerUrl", "") or ""),
        )


class BrowserDevToolsError(RuntimeError):
    """Raised when the DevTools route cannot complete a command."""


class BrowserDevToolsClient:
    """Small Chrome DevTools Protocol client for page target operations."""

    def __init__(self, *, request_timeout: float = 5.0):
        self.request_timeout = max(0.1, float(request_timeout))

    def list_targets(self, debugger_url: str) -> tuple[BrowserDevToolsTarget, ...]:
        endpoint = self._debugger_http_endpoint(debugger_url, "/json/list")
        response = requests.get(endpoint, timeout=self.request_timeout)
        response.raise_for_status()
        targets = response.json()
        if not isinstance(targets, list):
            raise BrowserDevToolsError("devtools_targets_not_list")
        return tuple(
            BrowserDevToolsTarget.from_dict(item)
            for item in targets
            if isinstance(item, dict)
        )

    def evaluate(
        self,
        debugger_url: str,
        target: BrowserDevToolsTarget,
        expression: str,
    ) -> dict:
        del debugger_url
        if not target.web_socket_debugger_url:
            raise BrowserDevToolsError("devtools_target_missing_websocket")
        message = self._send_cdp_command(
            target.web_socket_debugger_url,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        result = message.get("result", {})
        if not isinstance(result, dict):
            raise BrowserDevToolsError("devtools_invalid_runtime_result")
        if result.get("exceptionDetails"):
            return {
                "type": "exception",
                "exceptionDetails": result.get("exceptionDetails"),
            }
        remote_object = result.get("result", {})
        if not isinstance(remote_object, dict):
            raise BrowserDevToolsError("devtools_invalid_remote_object")
        return remote_object

    def call_method(
        self,
        debugger_url: str,
        target: BrowserDevToolsTarget,
        method: str,
        params: dict | None = None,
    ) -> dict:
        del debugger_url
        if not target.web_socket_debugger_url:
            raise BrowserDevToolsError("devtools_target_missing_websocket")
        method_name = str(method or "").strip()
        if not method_name:
            raise BrowserDevToolsError("missing_devtools_method")
        message = self._send_cdp_command(
            target.web_socket_debugger_url,
            method_name,
            dict(params or {}),
        )
        result = message.get("result", {})
        if not isinstance(result, dict):
            raise BrowserDevToolsError("devtools_invalid_method_result")
        return result

    @staticmethod
    def _debugger_http_endpoint(debugger_url: str, path: str) -> str:
        base = (debugger_url or "").strip()
        if not base:
            raise BrowserDevToolsError("missing_debugger_url")
        if "://" not in base:
            base = f"http://{base}"
        return f"{base.rstrip('/')}{path}"

    def _send_cdp_command(self, websocket_url: str, method: str, params: dict) -> dict:
        sock = self._connect_websocket(websocket_url)
        try:
            request = {
                "id": 1,
                "method": method,
                "params": params,
            }
            self._send_ws_json(sock, request)
            while True:
                message = self._recv_ws_json(sock)
                if int(message.get("id", 0) or 0) != 1:
                    continue
                if "error" in message:
                    error = message.get("error") or {}
                    raise BrowserDevToolsError(str(error.get("message", error)))
                return message
        finally:
            try:
                self._send_ws_frame(sock, b"", opcode=0x8)
            except OSError:
                pass
            sock.close()

    def _connect_websocket(self, websocket_url: str) -> socket.socket:
        parsed = urlparse(websocket_url)
        if parsed.scheme not in {"ws", "wss"}:
            raise BrowserDevToolsError("invalid_devtools_websocket_url")
        host = parsed.hostname or ""
        if not host:
            raise BrowserDevToolsError("missing_devtools_websocket_host")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        raw_sock = socket.create_connection((host, port), timeout=self.request_timeout)
        raw_sock.settimeout(self.request_timeout)
        sock = raw_sock
        if parsed.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname=host)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host_header = f"{host}:{port}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
        sock.sendall(request)
        response = self._recv_until(sock, b"\r\n\r\n")
        status_line = response.split(b"\r\n", 1)[0]
        if b" 101 " not in status_line:
            sock.close()
            raise BrowserDevToolsError("devtools_websocket_handshake_failed")
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if accept.encode("ascii") not in response:
            sock.close()
            raise BrowserDevToolsError("devtools_websocket_accept_mismatch")
        return sock

    @staticmethod
    def _recv_until(sock: socket.socket, marker: bytes) -> bytes:
        chunks: list[bytes] = []
        data = b""
        while marker not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            data = b"".join(chunks)
        return data

    @classmethod
    def _send_ws_json(cls, sock: socket.socket, message: dict) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        cls._send_ws_frame(sock, payload, opcode=0x1)

    @classmethod
    def _recv_ws_json(cls, sock: socket.socket) -> dict:
        text = cls._recv_ws_message(sock)
        message = json.loads(text)
        if not isinstance(message, dict):
            raise BrowserDevToolsError("devtools_websocket_non_object_message")
        return message

    @classmethod
    def _send_ws_frame(cls, sock: socket.socket, payload: bytes, *, opcode: int) -> None:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked = cls._mask_payload(payload, mask)
        sock.sendall(bytes(header) + mask + masked)

    @classmethod
    def _recv_ws_message(cls, sock: socket.socket) -> str:
        fragments: list[bytes] = []
        while True:
            first, second = cls._recv_exact(sock, 2)
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", cls._recv_exact(sock, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", cls._recv_exact(sock, 8))[0]

            mask = cls._recv_exact(sock, 4) if masked else b""
            payload = cls._recv_exact(sock, length) if length else b""
            if masked:
                payload = cls._mask_payload(payload, mask)

            if opcode == 0x8:
                raise BrowserDevToolsError("devtools_websocket_closed")
            if opcode == 0x9:
                cls._send_ws_frame(sock, payload, opcode=0xA)
                continue
            if opcode not in {0x0, 0x1}:
                continue
            fragments.append(payload)
            if fin:
                return b"".join(fragments).decode("utf-8", errors="replace")

    @staticmethod
    def _recv_exact(sock: socket.socket, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise BrowserDevToolsError("devtools_websocket_unexpected_eof")
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _mask_payload(payload: bytes, mask: bytes) -> bytes:
        return bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


@dataclasses.dataclass
class _BrowserSession:
    session_key: str
    base_url: str = ""
    transcript: list[str] = dataclasses.field(default_factory=list)
    last_url: str = ""
    last_status_code: int = 0
    command_count: int = 0
    last_command_at: float = 0.0
    client: requests.Session = dataclasses.field(default_factory=requests.Session)


class BrowserSessionConnector(SessionConnector):
    """A deterministic browser connector using DevTools first when available."""

    connector_id = "browser"
    display_name = "Managed Browser"
    devtools_route_id = "browser-devtools-or-extension"
    http_route_id = "browser-http-session"

    def __init__(self, *, devtools_client: BrowserDevToolsClient | None = None):
        self._sessions: dict[str, _BrowserSession] = {}
        self._lock = threading.Lock()
        self._devtools_client = devtools_client or BrowserDevToolsClient()

    def supports_target(self, target: ConnectorTarget) -> bool:
        process_name = (target.process_name or "").strip().lower()
        if process_name in _BROWSER_PROCESS_NAMES:
            return True
        if target.debugger_url:
            return True
        if target.resource_url:
            return True
        hint = " ".join(
            [
                target.workspace_hint or "",
                target.window_title or "",
            ]
        ).lower()
        return "browser" in hint or "http" in hint

    def match_score(self, target: ConnectorTarget) -> int:
        process_name = (target.process_name or "").strip().lower()
        if target.debugger_url:
            return 260
        if process_name in _BROWSER_PROCESS_NAMES:
            return 220
        if target.resource_url:
            return 180
        if re.search(r"\bbrowser\b|https?://", target.identity_text()):
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
                error="empty_browser_command",
            )

        try:
            devtools_expression = self._parse_devtools_eval_command(command)
        except ValueError as exc:
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="devtools_evaluate",
                action_key=f"{session.session_key}:{session.command_count}",
                error=str(exc),
            )
        if devtools_expression:
            return self._send_devtools_eval(target, session, devtools_expression)

        try:
            method, url, body = self._parse_browser_command(command, target, session)
        except ValueError as exc:
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="send_message",
                error=str(exc),
            )

        try:
            response = session.client.request(
                method,
                url,
                data=body or None,
                timeout=20,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            session.transcript.append(f"$ {method} {url}")
            session.transcript.append(f"[request_error] {exc}")
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="send_message",
                action_key=f"{session.session_key}:{session.command_count}",
                error=str(exc),
            )

        session.base_url = response.url or session.base_url
        session.last_url = response.url
        session.last_status_code = response.status_code
        title, excerpt = self._extract_response_summary(response)
        session.transcript.append(f"$ {method} {url}")
        session.transcript.append(
            f"[{response.status_code}] {title or response.url}"
        )
        if excerpt:
            session.transcript.append(excerpt)
        session.transcript = session.transcript[-200:]

        return ConnectorActionResult(
            success=response.status_code < 400,
            connector_id=self.connector_id,
            action="send_message",
            action_key=f"{session.session_key}:{session.command_count}",
            payload={
                "route_id": self.http_route_id,
                "transport": "requests-session",
                "session_key": session.session_key,
                "command_index": session.command_count,
                "url": response.url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "title": title,
                "text_excerpt": excerpt,
            },
            error="" if response.status_code < 400 else f"status_code={response.status_code}",
        )

    def _send_devtools_eval(
        self,
        target: ConnectorTarget,
        session: _BrowserSession,
        expression: str,
    ) -> ConnectorActionResult:
        debugger_url = (target.debugger_url or "").strip()
        action_key = f"{session.session_key}:{session.command_count}"
        if not debugger_url:
            session.transcript.append(f"$ CDP Runtime.evaluate {expression}")
            session.transcript.append("[devtools_error] missing_debugger_url")
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="devtools_evaluate",
                action_key=action_key,
                payload={
                    "route_id": self.devtools_route_id,
                    "transport": "chrome-devtools-protocol",
                    "session_key": session.session_key,
                    "command_index": session.command_count,
                    "expression": expression,
                },
                error="missing_debugger_url",
            )

        try:
            targets = tuple(self._devtools_client.list_targets(debugger_url))
        except Exception as exc:
            session.transcript.append(f"$ CDP Runtime.evaluate {expression}")
            session.transcript.append(f"[devtools_error] {exc}")
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="devtools_evaluate",
                action_key=action_key,
                payload={
                    "route_id": self.devtools_route_id,
                    "transport": "chrome-devtools-protocol",
                    "debugger_url": debugger_url,
                    "session_key": session.session_key,
                    "command_index": session.command_count,
                    "expression": expression,
                },
                error=str(exc) or "devtools_target_list_failed",
            )

        devtools_target = self._select_devtools_target(target, targets)
        if devtools_target is None:
            session.transcript.append(f"$ CDP Runtime.evaluate {expression}")
            session.transcript.append("[devtools_error] devtools_target_not_found")
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="devtools_evaluate",
                action_key=action_key,
                payload={
                    "route_id": self.devtools_route_id,
                    "transport": "chrome-devtools-protocol",
                    "debugger_url": debugger_url,
                    "session_key": session.session_key,
                    "command_index": session.command_count,
                    "expression": expression,
                    "target_count": len(targets),
                },
                error="devtools_target_not_found",
            )

        try:
            result = self._devtools_client.evaluate(
                debugger_url,
                devtools_target,
                expression,
            )
        except Exception as exc:
            session.transcript.append(f"$ CDP Runtime.evaluate {expression}")
            session.transcript.append(
                f"[target] {devtools_target.title or devtools_target.url}"
            )
            session.transcript.append(f"[devtools_error] {exc}")
            return ConnectorActionResult(
                success=False,
                connector_id=self.connector_id,
                action="devtools_evaluate",
                action_key=action_key,
                payload={
                    "route_id": self.devtools_route_id,
                    "transport": "chrome-devtools-protocol",
                    "debugger_url": debugger_url,
                    "session_key": session.session_key,
                    "command_index": session.command_count,
                    "target_id": devtools_target.target_id,
                    "target_type": devtools_target.type,
                    "target_title": devtools_target.title,
                    "target_url": devtools_target.url,
                    "expression": expression,
                },
                error=str(exc) or "devtools_evaluate_failed",
            )

        success = result.get("type") != "exception"
        session.last_url = devtools_target.url
        session.transcript.append(f"$ CDP Runtime.evaluate {expression}")
        session.transcript.append(
            f"[target] {devtools_target.title or devtools_target.url}"
        )
        session.transcript.append(f"[result] {self._devtools_result_excerpt(result)}")
        session.transcript = session.transcript[-200:]
        return ConnectorActionResult(
            success=success,
            connector_id=self.connector_id,
            action="devtools_evaluate",
            action_key=action_key,
            payload={
                "route_id": self.devtools_route_id,
                "transport": "chrome-devtools-protocol",
                "debugger_url": debugger_url,
                "session_key": session.session_key,
                "command_index": session.command_count,
                "target_id": devtools_target.target_id,
                "target_type": devtools_target.type,
                "target_title": devtools_target.title,
                "target_url": devtools_target.url,
                "expression": expression,
                "result": result,
            },
            error="" if success else "devtools_runtime_exception",
        )

    def _ensure_session(self, target: ConnectorTarget) -> _BrowserSession:
        session_key = self._session_key(target)
        with self._lock:
            session = self._sessions.get(session_key)
            if session is not None:
                return session

            session = _BrowserSession(
                session_key=session_key,
                base_url=(target.resource_url or "").strip(),
            )
            self._sessions[session_key] = session
            return session

    @staticmethod
    def _session_key(target: ConnectorTarget) -> str:
        parts = [
            target.debugger_url.strip().lower(),
            target.resource_url.strip().lower(),
            target.workspace_hint.strip().lower(),
            target.project_name.strip().lower(),
            target.window_title.strip().lower(),
        ]
        key = "|".join(part for part in parts if part)
        return key or "browser:default"

    @staticmethod
    def _parse_devtools_eval_command(command: str) -> str:
        stripped = (command or "").strip()
        prefixes = (
            "CDP Runtime.evaluate ",
            "CDP EVAL ",
            "EVAL ",
        )
        upper = stripped.upper()
        for prefix in prefixes:
            if upper.startswith(prefix.upper()):
                expression = stripped[len(prefix):].strip()
                if not expression:
                    raise ValueError("empty_devtools_expression")
                return expression
        return ""

    @classmethod
    def _select_devtools_target(
        cls,
        target: ConnectorTarget,
        targets: tuple[BrowserDevToolsTarget, ...],
    ) -> BrowserDevToolsTarget | None:
        page_targets = tuple(
            item
            for item in targets
            if (item.type or "").lower() in {"page", "webview"} or not item.type
        )
        candidates = page_targets or targets
        if not candidates:
            return None

        resource_url = cls._normalize_url_for_match(target.resource_url)
        if resource_url:
            for candidate in candidates:
                if cls._normalize_url_for_match(candidate.url) == resource_url:
                    return candidate
            for candidate in candidates:
                candidate_url = cls._normalize_url_for_match(candidate.url)
                if candidate_url and (
                    candidate_url.startswith(resource_url)
                    or resource_url.startswith(candidate_url)
                ):
                    return candidate

        title = (target.window_title or "").strip().lower()
        if title:
            for candidate in candidates:
                candidate_title = (candidate.title or "").strip().lower()
                if candidate_title and (
                    candidate_title in title or title in candidate_title
                ):
                    return candidate
        return candidates[0]

    @staticmethod
    def _normalize_url_for_match(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return value.lower().rstrip("/")
        path = parsed.path.rstrip("/") or "/"
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=path,
            fragment="",
        )
        return normalized.geturl().rstrip("/")

    @staticmethod
    def _devtools_result_excerpt(result: dict) -> str:
        if "value" in result:
            return str(result.get("value", ""))[:2000]
        if "description" in result:
            return str(result.get("description", ""))[:2000]
        return json.dumps(result, ensure_ascii=False, sort_keys=True)[:2000]

    @staticmethod
    def _parse_browser_command(
        command: str,
        target: ConnectorTarget,
        session: _BrowserSession,
    ) -> tuple[str, str, str]:
        first_line, _, body = command.partition("\n\n")
        parts = shlex.split(first_line, posix=False)
        if not parts:
            raise ValueError("empty_browser_command")

        if len(parts) >= 2 and parts[0].upper() in _HTTP_METHODS:
            method = parts[0].upper()
            url = parts[1]
        else:
            method = "GET"
            url = parts[0]

        if not url:
            raise ValueError("missing_browser_url")

        if not urlparse(url).scheme:
            base_url = (target.resource_url or session.base_url or "").strip()
            if base_url:
                url = urljoin(base_url, url)
            else:
                url = f"https://{url.lstrip('/')}"

        return method, url, body.strip()

    @staticmethod
    def _extract_response_summary(response: requests.Response) -> tuple[str, str]:
        content_type = response.headers.get("content-type", "").lower()
        text = response.text or ""
        if "html" not in content_type:
            excerpt = re.sub(r"\s+", " ", text).strip()
            return "", excerpt[:2000]

        title_match = re.search(
            r"<title[^>]*>(.*?)</title>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        title = html.unescape(title_match.group(1).strip()) if title_match else ""

        clean = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        clean = re.sub(r"(?is)<style.*?>.*?</style>", " ", clean)
        clean = re.sub(r"(?s)<[^>]+>", " ", clean)
        clean = html.unescape(clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return title, clean[:2000]
