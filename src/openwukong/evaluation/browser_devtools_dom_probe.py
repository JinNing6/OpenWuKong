# -*- coding: utf-8 -*-
"""Opt-in harmless Browser DevTools DOM write-and-clear probe."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional

from openwukong.connectors.browser import (
    BrowserDevToolsClient,
    BrowserDevToolsTarget,
)
from openwukong.evaluation.browser_devtools_health import (
    BrowserDevToolsHealthReport,
    run_browser_devtools_health,
)


_PROBE_ELEMENT_ID = "openwukong-dom-probe"


@dataclasses.dataclass(frozen=True)
class BrowserDevToolsDomProbeReport:
    debugger_url: str
    ok: bool
    health_report: BrowserDevToolsHealthReport
    target: BrowserDevToolsTarget | None = None
    token: str = ""
    write_result: dict | None = None
    write_verify_result: dict | None = None
    clear_result: dict | None = None
    clear_verify_result: dict | None = None
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "browser-devtools-dom-probe"

    @property
    def safety_mode(self) -> str:
        return "isolated_dom_write_clear_probe"

    @property
    def health_ok(self) -> bool:
        return self.health_report.ok

    @property
    def write_verified(self) -> bool:
        data = self.write_verify_result or {}
        return bool(self.write_verify_result) and bool(data.get("present")) and data.get("text") == self.token

    @property
    def clear_verified(self) -> bool:
        data = self.clear_verify_result or {}
        return bool(self.clear_verify_result) and not bool(data.get("present")) and not data.get("text")

    @property
    def token_visible_after_write(self) -> bool:
        return bool((self.write_verify_result or {}).get("text") == self.token)

    @property
    def token_visible_after_clear(self) -> bool:
        return bool((self.clear_verify_result or {}).get("text") == self.token)

    @property
    def control_allowed(self) -> bool:
        return bool(self.health_ok and self.target is not None)

    @property
    def control_attempts(self) -> int:
        return 1 if self.write_result is not None else 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "ok": self.ok,
            "health_ok": self.health_ok,
            "write_verified": self.write_verified,
            "clear_verified": self.clear_verified,
            "token_visible_after_write": self.token_visible_after_write,
            "token_visible_after_clear": self.token_visible_after_clear,
            "debugger_url": self.debugger_url,
            "token": self.token,
            "target": _target_to_dict(self.target),
            "page_identity": dict(self.health_report.page_identity or {}),
            "write_result": dict(self.write_result or {}),
            "write_verify_result": dict(self.write_verify_result or {}),
            "clear_result": dict(self.clear_result or {}),
            "clear_verify_result": dict(self.clear_verify_result or {}),
            "health_report": self.health_report.to_dict(),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_browser_devtools_dom_probe(
    *,
    debugger_url: str,
    window_title: str = "",
    resource_url: str = "",
    token: str = "OPENWUKONG_DOM_PROBE",
    devtools_client: BrowserDevToolsClient | None = None,
) -> BrowserDevToolsDomProbeReport:
    started = time.perf_counter()
    active_client = devtools_client or BrowserDevToolsClient()
    health = run_browser_devtools_health(
        debugger_url=debugger_url,
        window_title=window_title,
        resource_url=resource_url,
        devtools_client=active_client,
    )
    if not health.ok or health.target is None:
        return BrowserDevToolsDomProbeReport(
            debugger_url=str(debugger_url or "").strip(),
            ok=False,
            health_report=health,
            token=token,
            error=health.error or "browser_devtools_health_failed",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    write_result: dict = {}
    write_verify_result: dict = {}
    clear_result: dict = {}
    clear_verify_result: dict = {}
    error = ""
    try:
        write_result = _evaluate_value(
            active_client,
            debugger_url,
            health.target,
            _write_expression(token),
        )
        write_verify_result = _evaluate_value(
            active_client,
            debugger_url,
            health.target,
            _read_expression(),
        )
        clear_result = _evaluate_value(
            active_client,
            debugger_url,
            health.target,
            _clear_expression(),
        )
        clear_verify_result = _evaluate_value(
            active_client,
            debugger_url,
            health.target,
            _read_expression(),
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__

    report = BrowserDevToolsDomProbeReport(
        debugger_url=str(debugger_url or "").strip(),
        ok=not error,
        health_report=health,
        target=health.target,
        token=token,
        write_result=write_result,
        write_verify_result=write_verify_result,
        clear_result=clear_result,
        clear_verify_result=clear_verify_result,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    return dataclasses.replace(
        report,
        ok=report.ok and report.write_verified and report.clear_verified,
        error=report.error or _verification_error(report),
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    devtools_client: BrowserDevToolsClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run an opt-in harmless Browser DevTools DOM write-and-clear probe."
    )
    parser.add_argument("--debugger-url", required=True)
    parser.add_argument("--window-title", default="")
    parser.add_argument("--resource-url", default="")
    parser.add_argument("--token", default="OPENWUKONG_DOM_PROBE")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_browser_devtools_dom_probe(
        debugger_url=args.debugger_url,
        window_title=args.window_title,
        resource_url=args.resource_url,
        token=args.token,
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
            "Browser DevTools DOM probe: "
            f"ok={data['ok']} "
            f"write_verified={data['write_verified']} "
            f"clear_verified={data['clear_verified']}"
        )
    return 0


def _evaluate_value(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    expression: str,
) -> dict:
    result = client.evaluate(debugger_url, target, expression)
    if not isinstance(result, dict):
        return {}
    value = result.get("value")
    return dict(value) if isinstance(value, dict) else {}


def _write_expression(token: str) -> str:
    node_id = json.dumps(_PROBE_ELEMENT_ID)
    token_json = json.dumps(str(token or ""))
    return (
        "(() => {"
        f"const id = {node_id};"
        f"const token = {token_json};"
        "let el = document.getElementById(id);"
        "if (!el) {"
        "el = document.createElement('div');"
        "el.id = id;"
        "el.setAttribute('data-openwukong-probe', 'true');"
        "el.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;overflow:hidden;';"
        "(document.documentElement || document.body).appendChild(el);"
        "}"
        "el.textContent = token;"
        "return {present: true, text: el.textContent};"
        "})()"
    )


def _read_expression() -> str:
    node_id = json.dumps(_PROBE_ELEMENT_ID)
    return (
        "(() => {"
        f"const el = document.getElementById({node_id});"
        "return {present: !!el, text: el ? el.textContent : ''};"
        "})()"
    )


def _clear_expression() -> str:
    node_id = json.dumps(_PROBE_ELEMENT_ID)
    return (
        "(() => {"
        f"const el = document.getElementById({node_id});"
        "if (el && el.getAttribute('data-openwukong-probe') === 'true') {"
        "el.remove();"
        "return {removed: true};"
        "}"
        "return {removed: false};"
        "})()"
    )


def _verification_error(report: BrowserDevToolsDomProbeReport) -> str:
    if not report.write_verified:
        return "dom_write_not_verified"
    if not report.clear_verified:
        return "dom_clear_not_verified"
    return ""


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
