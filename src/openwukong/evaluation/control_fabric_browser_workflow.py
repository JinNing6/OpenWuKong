# -*- coding: utf-8 -*-
"""Fabric-level browser form workflow runner."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Optional

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_discovery import SessionDiscovery, SessionDiscoveryOptions
from openwukong.control.session_ownership import build_ownership_index


@dataclasses.dataclass(frozen=True)
class BrowserWorkflowStep:
    action: str
    url: str = ""
    selector: str = ""
    value: str = ""

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "url": self.url,
            "selector": self.selector,
            "value_preview": _clip(self.value),
        }


@dataclasses.dataclass(frozen=True)
class BrowserWorkflowExpectations:
    expected_url_contains: tuple[str, ...] = ()
    expected_text_contains: tuple[str, ...] = ()
    expected_link_href_contains: tuple[str, ...] = ()
    expected_link_text_contains: tuple[str, ...] = ()
    min_result_count: int = 0

    def has_checks(self) -> bool:
        return bool(
            self.expected_url_contains
            or self.expected_text_contains
            or self.expected_link_href_contains
            or self.expected_link_text_contains
            or self.min_result_count > 0
        )

    def to_dict(self) -> dict:
        return {
            "expected_url_contains": list(self.expected_url_contains),
            "expected_text_contains": list(self.expected_text_contains),
            "expected_link_href_contains": list(self.expected_link_href_contains),
            "expected_link_text_contains": list(self.expected_link_text_contains),
            "min_result_count": max(0, int(self.min_result_count or 0)),
        }


@dataclasses.dataclass(frozen=True)
class BrowserWorkflowStepReport:
    index: int
    step: BrowserWorkflowStep
    execution_report: dict

    @property
    def ok(self) -> bool:
        return bool(self.execution_report.get("ok"))

    @property
    def control_attempts(self) -> int:
        return int(self.execution_report.get("control_attempts", 0) or 0)

    def to_dict(self) -> dict:
        data = self.step.to_dict()
        data.update(
            {
                "index": self.index,
                "ok": self.ok,
                "control_attempts": self.control_attempts,
                "execution_report": dict(self.execution_report or {}),
            }
        )
        return data


@dataclasses.dataclass(frozen=True)
class BrowserWorkflowReport:
    steps: tuple[BrowserWorkflowStepReport, ...]
    allow_control: bool
    ok: bool
    final_target: ConnectorTarget
    expectations: BrowserWorkflowExpectations = dataclasses.field(
        default_factory=BrowserWorkflowExpectations
    )
    quality_checks: tuple[dict, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "control-fabric-browser-workflow"

    @property
    def safety_mode(self) -> str:
        return "explicit_control_gate_sequence"

    @property
    def control_allowed(self) -> bool:
        return bool(self.allow_control and self.ok)

    @property
    def control_attempts(self) -> int:
        return sum(step.control_attempts for step in self.steps)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def final_page_identity(self) -> dict:
        if not self.steps:
            return {}
        action_report = (
            self.steps[-1]
            .execution_report.get("action_report", {})
        )
        identity = action_report.get("post_action_identity") or action_report.get("page_identity") or {}
        return dict(identity) if isinstance(identity, dict) else {}

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "step_count": self.step_count,
            "steps": [step.to_dict() for step in self.steps],
            "final_target": _target_to_dict(self.final_target),
            "final_page_identity": self.final_page_identity,
            "expectations": self.expectations.to_dict(),
            "quality_checks": [dict(check) for check in self.quality_checks],
            "quality_summary": _quality_summary(self.quality_checks),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_control_fabric_browser_workflow(
    *,
    process_name: str,
    window_title: str,
    resource_url: str,
    debugger_url: str,
    steps: tuple[BrowserWorkflowStep, ...],
    expectations: BrowserWorkflowExpectations | None = None,
    allow_control: bool = False,
    settle_seconds: float = 0.0,
    fabric: ControlFabric | None = None,
    browser_action_runner: Optional[object] = None,
    session_discovery: Optional[object] = None,
) -> BrowserWorkflowReport:
    started = time.perf_counter()
    active_fabric = fabric or ControlFabric.with_default_connectors()
    base_target = ConnectorTarget(
        process_name=process_name,
        window_title=window_title,
        resource_url=resource_url,
        debugger_url=debugger_url,
    )
    target_for_execution: object = (
        session_discovery.enrich(base_target) if session_discovery is not None else base_target
    )
    step_reports: list[BrowserWorkflowStepReport] = []
    error = ""
    active_expectations = expectations or BrowserWorkflowExpectations()

    for index, step in enumerate(steps):
        intent = ControlIntent(
            action=step.action,
            url=step.url,
            selector=step.selector,
            value=step.value,
            text=step.value,
        )
        execution = active_fabric.execute(
            target_for_execution,
            intent,
            allow_control=allow_control,
            browser_action_runner=browser_action_runner,
        )
        execution_data = execution.to_dict()
        step_report = BrowserWorkflowStepReport(
            index=index,
            step=step,
            execution_report=execution_data,
        )
        step_reports.append(step_report)
        if not execution.ok:
            error = execution.error or "workflow_step_failed"
            break
        connector_target = _connector_target_from_target(target_for_execution)
        target_for_execution = _target_after_step(connector_target, execution_data)
        if settle_seconds > 0 and step.action in {"navigate_url", "click_locator", "submit_form"}:
            time.sleep(settle_seconds)

    steps_ok = bool(step_reports) and all(step.ok for step in step_reports) and len(step_reports) == len(steps)
    final_target = _connector_target_from_target(target_for_execution)
    quality_checks = _build_quality_checks(tuple(step_reports), final_target, active_expectations)
    quality_ok = all(bool(check.get("passed")) for check in quality_checks)
    if steps_ok and not quality_ok:
        error = "workflow_quality_assertion_failed"
    ok = steps_ok and quality_ok
    return BrowserWorkflowReport(
        steps=tuple(step_reports),
        allow_control=allow_control,
        ok=ok,
        final_target=final_target,
        expectations=active_expectations,
        quality_checks=quality_checks,
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    fabric: ControlFabric | None = None,
    browser_action_runner: Optional[object] = None,
    session_discovery: Optional[object] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run a Fabric-gated browser form workflow."
    )
    parser.add_argument("--process-name", default="chrome.exe")
    parser.add_argument("--window-title", default="")
    parser.add_argument("--resource-url", default="")
    parser.add_argument("--debugger-url", default="")
    parser.add_argument("--discover-sessions", action="store_true")
    parser.add_argument("--browser-debug-port", action="append", type=int, default=None)
    parser.add_argument("--discovery-timeout", type=float, default=0.2)
    parser.add_argument("--readiness-manifest", action="append", default=None)
    parser.add_argument("--readiness-manifest-dir", action="append", default=None)
    parser.add_argument("--require-owned-session", action="store_true")
    parser.add_argument("--start-url", default="")
    parser.add_argument("--input-selector", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--submit-selector", default="")
    parser.add_argument("--results-selector", default="")
    parser.add_argument("--expect-url-contains", action="append", default=None)
    parser.add_argument("--expect-text-contains", action="append", default=None)
    parser.add_argument("--expect-link-href-contains", action="append", default=None)
    parser.add_argument("--expect-link-text-contains", action="append", default=None)
    parser.add_argument("--min-result-count", type=int, default=0)
    parser.add_argument("--settle-seconds", type=float, default=0.0)
    parser.add_argument("--allow-control", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    steps = _build_form_steps(
        start_url=args.start_url,
        input_selector=args.input_selector,
        query=args.query,
        submit_selector=args.submit_selector,
        results_selector=args.results_selector,
    )
    ownership_paths = _manifest_paths_from_args(
        tuple(args.readiness_manifest or ()),
        tuple(args.readiness_manifest_dir or ()),
    )
    require_owned_session = bool(args.require_owned_session or ownership_paths)
    active_fabric = fabric or ControlFabric.with_default_connectors(
        ownership_index=build_ownership_index(ownership_paths),
        require_owned_session_for_execution=require_owned_session,
    )
    report = run_control_fabric_browser_workflow(
        process_name=args.process_name,
        window_title=args.window_title,
        resource_url=args.resource_url,
        debugger_url=args.debugger_url,
        steps=steps,
        expectations=BrowserWorkflowExpectations(
            expected_url_contains=_clean_tuple(args.expect_url_contains or ()),
            expected_text_contains=_clean_tuple(args.expect_text_contains or ()),
            expected_link_href_contains=_clean_tuple(args.expect_link_href_contains or ()),
            expected_link_text_contains=_clean_tuple(args.expect_link_text_contains or ()),
            min_result_count=max(0, int(args.min_result_count or 0)),
        ),
        allow_control=args.allow_control,
        settle_seconds=max(0.0, float(args.settle_seconds or 0.0)),
        fabric=active_fabric,
        browser_action_runner=browser_action_runner,
        session_discovery=_session_discovery_from_args(
            discover_sessions=args.discover_sessions,
            browser_debug_ports=tuple(args.browser_debug_port or ()),
            discovery_timeout=float(args.discovery_timeout or 0.2),
            session_discovery=session_discovery,
        ),
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
            "Control Fabric browser workflow: "
            f"ok={data['ok']} "
            f"steps={data['step_count']} "
            f"attempts={data['control_attempts']}"
        )
    return 0 if report.ok else 1


def _session_discovery_from_args(
    *,
    discover_sessions: bool,
    browser_debug_ports: tuple[int, ...],
    discovery_timeout: float,
    session_discovery: Optional[object],
) -> object | None:
    if not discover_sessions:
        return None
    return session_discovery or SessionDiscovery(
        SessionDiscoveryOptions(
            browser_debug_ports=browser_debug_ports or SessionDiscoveryOptions().browser_debug_ports,
            request_timeout=max(0.05, float(discovery_timeout)),
        )
    )


def _manifest_paths_from_args(paths: tuple[str, ...], dirs: tuple[str, ...]) -> tuple[Path, ...]:
    collected: list[Path] = []
    for value in paths or ():
        path = Path(str(value))
        if path.is_file():
            collected.append(path)
    for value in dirs or ():
        directory = Path(str(value))
        if not directory.is_dir():
            continue
        collected.extend(sorted(directory.glob("*.json")))
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in collected:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)


def _build_form_steps(
    *,
    start_url: str,
    input_selector: str,
    query: str,
    submit_selector: str,
    results_selector: str,
) -> tuple[BrowserWorkflowStep, ...]:
    steps: list[BrowserWorkflowStep] = []
    if start_url:
        steps.append(BrowserWorkflowStep(action="navigate_url", url=start_url))
    if input_selector:
        steps.append(
            BrowserWorkflowStep(
                action="set_input_value",
                selector=input_selector,
                value=query,
            )
        )
    if submit_selector:
        steps.append(BrowserWorkflowStep(action="submit_form", selector=submit_selector))
    steps.append(BrowserWorkflowStep(action="read_page"))
    if results_selector:
        steps.append(BrowserWorkflowStep(action="extract_results", selector=results_selector))
    return tuple(steps)


def _connector_target_from_target(target_or_window: object) -> ConnectorTarget:
    if isinstance(target_or_window, ConnectorTarget):
        return target_or_window
    to_connector_target = getattr(target_or_window, "to_connector_target", None)
    if callable(to_connector_target):
        target = to_connector_target()
        if isinstance(target, ConnectorTarget):
            return target
    return ConnectorTarget(
        pid=int(getattr(target_or_window, "pid", 0) or 0),
        process_name=str(getattr(target_or_window, "process_name", "") or ""),
        window_title=str(getattr(target_or_window, "window_title", "") or ""),
        project_name=str(getattr(target_or_window, "project_name", "") or ""),
        workspace_hint=str(getattr(target_or_window, "workspace_hint", "") or ""),
        workspace_path=str(getattr(target_or_window, "workspace_path", "") or ""),
        resource_url=str(getattr(target_or_window, "resource_url", "") or ""),
        debugger_url=str(getattr(target_or_window, "debugger_url", "") or ""),
        ide_bridge_url=str(getattr(target_or_window, "ide_bridge_url", "") or ""),
    )


def _target_after_step(target: ConnectorTarget, execution_data: dict) -> ConnectorTarget:
    action_report = execution_data.get("action_report", {})
    if not isinstance(action_report, dict):
        return target
    identity = action_report.get("post_action_identity") or action_report.get("page_identity") or {}
    if not isinstance(identity, dict):
        return target
    href = str(identity.get("href", "") or "").strip()
    title = str(identity.get("title", "") or "").strip()
    if not href and not title:
        return target
    window_title = _window_title_from_page_title(title, target.window_title)
    return dataclasses.replace(
        target,
        resource_url=href or target.resource_url,
        window_title=window_title or target.window_title,
    )


def _build_quality_checks(
    steps: tuple[BrowserWorkflowStepReport, ...],
    final_target: ConnectorTarget,
    expectations: BrowserWorkflowExpectations,
) -> tuple[dict, ...]:
    if not expectations.has_checks():
        return ()
    evidence = _quality_evidence(steps, final_target)
    checks: list[dict] = []
    checks.extend(
        _contains_checks(
            "expected_url_contains",
            expectations.expected_url_contains,
            evidence["urls"],
        )
    )
    checks.extend(
        _contains_checks(
            "expected_text_contains",
            expectations.expected_text_contains,
            evidence["texts"],
        )
    )
    checks.extend(
        _contains_checks(
            "expected_link_href_contains",
            expectations.expected_link_href_contains,
            evidence["link_hrefs"],
        )
    )
    checks.extend(
        _contains_checks(
            "expected_link_text_contains",
            expectations.expected_link_text_contains,
            evidence["link_texts"],
        )
    )
    if expectations.min_result_count > 0:
        observed = len(evidence["items"])
        checks.append(
            {
                "kind": "min_result_count",
                "expected": expectations.min_result_count,
                "observed": observed,
                "passed": observed >= expectations.min_result_count,
            }
        )
    return tuple(checks)


def _quality_evidence(
    steps: tuple[BrowserWorkflowStepReport, ...],
    final_target: ConnectorTarget,
) -> dict:
    urls = [final_target.resource_url]
    texts: list[str] = []
    link_hrefs: list[str] = []
    link_texts: list[str] = []
    items: list[dict] = []
    for step in steps:
        action_report = step.execution_report.get("action_report", {})
        if not isinstance(action_report, dict):
            continue
        for key in ("page_identity", "post_action_identity"):
            identity = action_report.get(key, {})
            if isinstance(identity, dict):
                urls.append(str(identity.get("href", "") or ""))
                texts.append(str(identity.get("title", "") or ""))
        action_result = action_report.get("action_result", {})
        if not isinstance(action_result, dict):
            continue
        urls.append(str(action_result.get("href", "") or ""))
        texts.append(str(action_result.get("title", "") or ""))
        texts.append(str(action_result.get("textExcerpt", "") or ""))
        action_items = action_result.get("items", ())
        if isinstance(action_items, list):
            for item in action_items:
                if not isinstance(item, dict):
                    continue
                item_text = str(item.get("text", "") or "")
                item_href = str(item.get("href", "") or "")
                if item_text or item_href:
                    items.append({"text": item_text, "href": item_href})
                    link_texts.append(item_text)
                    link_hrefs.append(item_href)
                    texts.append(item_text)
                    urls.append(item_href)
    return {
        "urls": tuple(value for value in urls if value),
        "texts": tuple(value for value in texts if value),
        "link_hrefs": tuple(value for value in link_hrefs if value),
        "link_texts": tuple(value for value in link_texts if value),
        "items": tuple(items),
    }


def _contains_checks(kind: str, expected_values: tuple[str, ...], observed_values: tuple[str, ...]) -> tuple[dict, ...]:
    checks: list[dict] = []
    for expected in _clean_tuple(expected_values):
        expected_lower = expected.lower()
        matched = next(
            (observed for observed in observed_values if expected_lower in observed.lower()),
            "",
        )
        checks.append(
            {
                "kind": kind,
                "expected": expected,
                "observed": _clip(matched, 1000),
                "passed": bool(matched),
            }
        )
    return tuple(checks)


def _quality_summary(checks: tuple[dict, ...]) -> dict:
    passed = sum(1 for check in checks if check.get("passed"))
    failed = sum(1 for check in checks if not check.get("passed"))
    return {
        "total": len(checks),
        "passed": passed,
        "failed": failed,
    }


def _clean_tuple(values) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in values if str(value).strip())


def _window_title_from_page_title(page_title: str, previous: str) -> str:
    if not page_title:
        return previous
    process = "Google Chrome" if "Google Chrome" in previous else ""
    return f"{page_title} - {process}".strip(" -") if process else page_title


def _target_to_dict(target: ConnectorTarget) -> dict:
    return {
        "process_name": target.process_name,
        "window_title": target.window_title,
        "resource_url": target.resource_url,
        "debugger_url": target.debugger_url,
    }


def _clip(value: str, limit: int = 500) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


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
