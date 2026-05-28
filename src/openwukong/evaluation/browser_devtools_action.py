# -*- coding: utf-8 -*-
"""Health-gated Browser DevTools action runner."""

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


_PAGE_IDENTITY_EXPRESSION = (
    "({"
    "title: document.title,"
    "href: location.href,"
    "readyState: document.readyState"
    "})"
)


class BrowserDevToolsActionError(Exception):
    def __init__(self, message: str, *, action_result: dict | None = None):
        super().__init__(message)
        self.action_result = dict(action_result or {})


@dataclasses.dataclass(frozen=True)
class BrowserDevToolsActionReport:
    debugger_url: str
    action: str
    ok: bool
    health_report: BrowserDevToolsHealthReport
    target: BrowserDevToolsTarget | None = None
    action_result: dict | None = None
    post_action_identity: dict | None = None
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "browser-devtools-action"

    @property
    def safety_mode(self) -> str:
        return "gated_browser_devtools_action"

    @property
    def health_ok(self) -> bool:
        return self.health_report.ok

    @property
    def control_allowed(self) -> bool:
        return bool(self.health_ok and self.target is not None and not self.error)

    @property
    def control_attempts(self) -> int:
        if not self.action_result:
            return 0
        return 0 if self.action in {"read_page", "extract_results"} else 1

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "ok": self.ok,
            "health_ok": self.health_ok,
            "action": self.action,
            "debugger_url": self.debugger_url,
            "target": _target_to_dict(self.target),
            "page_identity": dict(self.health_report.page_identity or {}),
            "action_result": dict(self.action_result or {}),
            "post_action_identity": dict(self.post_action_identity or {}),
            "health_report": self.health_report.to_dict(),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_browser_devtools_action(
    *,
    debugger_url: str,
    window_title: str = "",
    resource_url: str = "",
    action: str,
    url: str = "",
    selector: str = "",
    value: str = "",
    devtools_client: BrowserDevToolsClient | None = None,
) -> BrowserDevToolsActionReport:
    started = time.perf_counter()
    active_client = devtools_client or BrowserDevToolsClient()
    action_name = str(action or "").strip()
    debugger = str(debugger_url or "").strip()

    health = run_browser_devtools_health(
        debugger_url=debugger,
        window_title=window_title,
        resource_url=resource_url,
        devtools_client=active_client,
    )
    if not health.ok or health.target is None:
        return BrowserDevToolsActionReport(
            debugger_url=debugger,
            action=action_name,
            ok=False,
            health_report=health,
            error=health.error or "browser_devtools_health_failed",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    try:
        action_result = _run_action(
            active_client,
            debugger,
            health.target,
            action_name,
            url=url,
            selector=selector,
            value=value,
        )
        if action_name in {"navigate_url", "click_locator", "submit_form"}:
            post_identity = _read_page_identity(active_client, debugger, health.target)
        else:
            post_identity = dict(health.page_identity or {})
    except BrowserDevToolsActionError as exc:
        return BrowserDevToolsActionReport(
            debugger_url=debugger,
            action=action_name,
            ok=False,
            health_report=health,
            target=health.target,
            action_result=exc.action_result,
            error=str(exc) or exc.__class__.__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:
        return BrowserDevToolsActionReport(
            debugger_url=debugger,
            action=action_name,
            ok=False,
            health_report=health,
            target=health.target,
            error=str(exc) or exc.__class__.__name__,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    return BrowserDevToolsActionReport(
        debugger_url=debugger,
        action=action_name,
        ok=True,
        health_report=health,
        target=health.target,
        action_result=action_result,
        post_action_identity=post_identity,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    devtools_client: BrowserDevToolsClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run a health-gated Browser DevTools action."
    )
    parser.add_argument("--debugger-url", required=True)
    parser.add_argument("--window-title", default="")
    parser.add_argument("--resource-url", default="")
    parser.add_argument("--action", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--selector", default="")
    parser.add_argument("--value", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_browser_devtools_action(
        debugger_url=args.debugger_url,
        window_title=args.window_title,
        resource_url=args.resource_url,
        action=args.action,
        url=args.url,
        selector=args.selector,
        value=args.value,
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
            "Browser DevTools action: "
            f"ok={data['ok']} "
            f"action={data['action']} "
            f"control_attempts={data['control_attempts']}"
        )
    return 0


def _run_action(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    action: str,
    *,
    url: str,
    selector: str,
    value: str,
) -> dict:
    if action == "navigate_url":
        target_url = str(url or "").strip()
        if not target_url:
            raise ValueError("missing_url")
        result = client.call_method(
            debugger_url,
            target,
            "Page.navigate",
            {"url": target_url},
        )
        action_result = {
            "navigated_url": target_url,
            "cdp_result": dict(result or {}),
        }
        error_text = str((result or {}).get("errorText", "") or "").strip()
        if error_text:
            raise BrowserDevToolsActionError(
                f"navigation_failed:{error_text}",
                action_result=action_result,
            )
        return action_result
    if action == "read_page":
        return _read_page(client, debugger_url, target)
    if action == "set_input_value":
        return _set_input_value(client, debugger_url, target, selector, value)
    if action == "click_locator":
        return _click_locator(client, debugger_url, target, selector)
    if action == "submit_form":
        return _submit_form(client, debugger_url, target, selector)
    if action == "extract_results":
        return _extract_results(client, debugger_url, target, selector)
    raise ValueError("unsupported_browser_action")


def _read_page(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
) -> dict:
    expression = (
        "(() => {"
        "const text = (document.body ? document.body.innerText : document.documentElement.innerText) || '';"
        "return {"
        "title: document.title,"
        "href: location.href,"
        "readyState: document.readyState,"
        "textExcerpt: text.replace(/\\s+/g, ' ').trim().slice(0, 4000)"
        "};"
        "})()"
    )
    return _evaluate_value(client, debugger_url, target, expression)


def _set_input_value(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    selector: str,
    value: str,
) -> dict:
    selector_text = str(selector or "").strip()
    if not selector_text:
        raise ValueError("missing_selector")
    selector_json = json.dumps(selector_text)
    value_json = json.dumps(str(value or ""))
    expression = (
        "(() => {"
        f"const selector = {selector_json};"
        f"const nextValue = {value_json};"
        "const el = document.querySelector(selector);"
        "if (!el) return {found: false, selector, value: ''};"
        "el.focus();"
        "el.value = nextValue;"
        "el.dispatchEvent(new Event('input', {bubbles: true}));"
        "el.dispatchEvent(new Event('change', {bubbles: true}));"
        "return {found: true, selector, value: el.value};"
        "})()"
    )
    result = _evaluate_value(client, debugger_url, target, expression)
    if not result.get("found"):
        raise ValueError("selector_not_found")
    if str(result.get("value", "")) != str(value or ""):
        raise ValueError("input_value_not_verified")
    return result


def _click_locator(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    selector: str,
) -> dict:
    selector_text = str(selector or "").strip()
    if not selector_text:
        raise ValueError("missing_selector")
    selector_json = json.dumps(selector_text)
    expression = (
        "(() => {"
        f"const selector = {selector_json};"
        "const el = document.querySelector(selector);"
        "if (!el) return {found: false, clicked: false, selector};"
        "el.scrollIntoView({block: 'center', inline: 'center'});"
        "el.click();"
        "return {found: true, clicked: true, selector};"
        "})()"
    )
    result = _evaluate_value(client, debugger_url, target, expression)
    if not result.get("clicked"):
        raise ValueError("click_not_verified")
    return result


def _submit_form(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    selector: str,
) -> dict:
    selector_text = str(selector or "").strip()
    if not selector_text:
        raise ValueError("missing_selector")
    selector_json = json.dumps(selector_text)
    expression = (
        "(() => {"
        f"const selector = {selector_json};"
        "const el = document.querySelector(selector);"
        "const form = el ? el.closest('form') : document.querySelector('form');"
        "if (!form) return {found: !!el, submitted: false, selector, formAction: ''};"
        "const tag = el ? el.tagName : '';"
        "const type = el ? String(el.type || '').toLowerCase() : '';"
        "const canBeSubmitter = !!el && (tag === 'BUTTON' || tag === 'INPUT') && "
        "(type === 'submit' || type === 'image' || type === '');"
        "if (typeof form.requestSubmit === 'function') {"
        "if (canBeSubmitter) form.requestSubmit(el);"
        "else form.requestSubmit();"
        "} else {"
        "form.submit();"
        "}"
        "return {found: !!el, submitted: true, selector, formAction: form.action || location.href};"
        "})()"
    )
    result = _evaluate_value(client, debugger_url, target, expression)
    if not result.get("submitted"):
        raise ValueError("form_submit_not_verified")
    return result


def _extract_results(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
    selector: str,
) -> dict:
    selector_text = str(selector or "a").strip() or "a"
    selector_json = json.dumps(selector_text)
    expression = (
        "(() => {"
        f"const selector = {selector_json};"
        "const nodes = Array.from(document.querySelectorAll(selector)).slice(0, 20);"
        "return {selector, items: nodes.map((node) => ({"
        "text: (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 500),"
        "href: node.href || ''"
        "}))};"
        "})()"
    )
    return _evaluate_value(client, debugger_url, target, expression)


def _read_page_identity(
    client: BrowserDevToolsClient,
    debugger_url: str,
    target: BrowserDevToolsTarget,
) -> dict:
    return _evaluate_value(client, debugger_url, target, _PAGE_IDENTITY_EXPRESSION)


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
    return dict(value) if isinstance(value, dict) else {"value": value}


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
