# -*- coding: utf-8 -*-
"""Read-only Browser DevTools endpoint health report."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from openwukong.connectors.browser import (
    BrowserDevToolsClient,
    BrowserDevToolsTarget,
)


_READ_ONLY_PAGE_IDENTITY_EXPRESSION = (
    "({"
    "title: document.title,"
    "href: location.href,"
    "readyState: document.readyState"
    "})"
)


@dataclasses.dataclass(frozen=True)
class BrowserDevToolsHealthReport:
    debugger_url: str
    ok: bool
    endpoint_ready: bool
    target_matched: bool
    evaluated_read_only: bool
    target: BrowserDevToolsTarget | None = None
    page_identity: dict | None = None
    target_count: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "browser-devtools-health"

    @property
    def safety_mode(self) -> str:
        return "read_only"

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
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "ok": self.ok,
            "endpoint_ready": self.endpoint_ready,
            "target_matched": self.target_matched,
            "evaluated_read_only": self.evaluated_read_only,
            "debugger_url": self.debugger_url,
            "target_count": self.target_count,
            "target": _target_to_dict(self.target),
            "page_identity": dict(self.page_identity or {}),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_browser_devtools_health(
    *,
    debugger_url: str,
    window_title: str = "",
    resource_url: str = "",
    devtools_client: BrowserDevToolsClient | None = None,
) -> BrowserDevToolsHealthReport:
    started = time.perf_counter()
    active_client = devtools_client or BrowserDevToolsClient()
    debugger = str(debugger_url or "").strip()
    try:
        targets = tuple(active_client.list_targets(debugger))
    except Exception as exc:
        return BrowserDevToolsHealthReport(
            debugger_url=debugger,
            ok=False,
            endpoint_ready=False,
            target_matched=False,
            evaluated_read_only=False,
            error=str(exc) or "devtools_target_list_failed",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    target = _select_strict_target(
        targets,
        window_title=window_title,
        resource_url=resource_url,
    )
    if target is None:
        return BrowserDevToolsHealthReport(
            debugger_url=debugger,
            ok=False,
            endpoint_ready=True,
            target_matched=False,
            evaluated_read_only=False,
            target_count=len(targets),
            error="devtools_target_not_matched",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    try:
        result = active_client.evaluate(
            debugger,
            target,
            _READ_ONLY_PAGE_IDENTITY_EXPRESSION,
        )
    except Exception as exc:
        return BrowserDevToolsHealthReport(
            debugger_url=debugger,
            ok=False,
            endpoint_ready=True,
            target_matched=True,
            evaluated_read_only=False,
            target=target,
            target_count=len(targets),
            error=str(exc) or "devtools_read_only_evaluate_failed",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    identity = result.get("value") if isinstance(result, dict) else {}
    if not isinstance(identity, dict):
        identity = {}
    return BrowserDevToolsHealthReport(
        debugger_url=debugger,
        ok=True,
        endpoint_ready=True,
        target_matched=True,
        evaluated_read_only=True,
        target=target,
        page_identity=identity,
        target_count=len(targets),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    devtools_client: BrowserDevToolsClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only Browser DevTools endpoint health check."
    )
    parser.add_argument("--debugger-url", required=True)
    parser.add_argument("--window-title", default="")
    parser.add_argument("--resource-url", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_browser_devtools_health(
        debugger_url=args.debugger_url,
        window_title=args.window_title,
        resource_url=args.resource_url,
        devtools_client=devtools_client,
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
            "Browser DevTools health: "
            f"ok={data['ok']} "
            f"endpoint_ready={data['endpoint_ready']} "
            f"target_matched={data['target_matched']}"
        )
    return 0


def _select_strict_target(
    targets: tuple[BrowserDevToolsTarget, ...],
    *,
    window_title: str,
    resource_url: str,
) -> BrowserDevToolsTarget | None:
    candidates = tuple(
        target
        for target in targets
        if (target.type or "").lower() in {"page", "webview"} or not target.type
    )
    candidates = candidates or targets
    normalized_resource = _normalize_url(resource_url)
    if normalized_resource:
        for target in candidates:
            if _normalize_url(target.url) == normalized_resource:
                return target
        return None

    normalized_title = str(window_title or "").strip().lower()
    if normalized_title:
        for target in candidates:
            target_title = str(target.title or "").strip().lower()
            if target_title and target_title in normalized_title:
                return target
        return None

    return candidates[0] if len(candidates) == 1 else None


def _normalize_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return text.lower().rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        fragment="",
    )
    return normalized.geturl().rstrip("/")


def _target_to_dict(target: BrowserDevToolsTarget | None) -> dict:
    if target is None:
        return {}
    return {
        "target_id": target.target_id,
        "type": target.type,
        "title": target.title,
        "url": target.url,
        "webSocketDebuggerUrl": target.web_socket_debugger_url,
    }


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
