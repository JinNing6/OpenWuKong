# -*- coding: utf-8 -*-
"""Read-only UIA probe for agent desktop/app conversation surfaces."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.agent_surface import (
    AgentSurfaceBindingReport,
    build_agent_surface_binding,
)
from openwukong.control.app_resolution import WindowsAppResolver, lower_text
from openwukong.control.foreground_takeover import ForegroundTakeoverRequest
from openwukong.evaluation.accessibility_probe import (
    AccessibilityCapabilityReport,
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    PywinautoAccessibilityObserver,
    WindowsCapabilityProbe,
)
from openwukong.evaluation.window_capture import (
    BackgroundWindowCaptureReport,
    PrintWindowBackgroundCaptureProvider,
)


_SEMANTIC_COMPOSER_PATTERNS = {"Value", "TextEdit"}
_COMPOSER_HINTS = (
    "message",
    "chat",
    "ask",
    "prompt",
    "composer",
    "textbox",
    "textarea",
    "input",
    "reply",
    "plan, build",
    "commands",
    "context",
    "发送",
    "输入",
    "消息",
    "提问",
    "询问",
    "回复",
)


@dataclasses.dataclass(frozen=True)
class AgentAppElementEvidence:
    control_type: str
    name: str = ""
    automation_id: str = ""
    class_name: str = ""
    value_preview: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    is_enabled: bool = False
    patterns: tuple[str, ...] = ()
    process_name: str = ""
    window_title: str = ""
    pid: int = 0
    visible: bool = False

    @property
    def semantic_composer(self) -> bool:
        return bool(set(self.patterns) & _SEMANTIC_COMPOSER_PATTERNS)

    def to_dict(self) -> dict:
        return {
            "process_name": self.process_name,
            "pid": int(self.pid or 0),
            "window_title": self.window_title,
            "control_type": self.control_type,
            "name": self.name,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "value_preview": self.value_preview,
            "rect": list(self.rect),
            "is_enabled": self.is_enabled,
            "patterns": list(self.patterns),
            "visible": self.visible,
            "semantic_composer": self.semantic_composer,
        }


@dataclasses.dataclass(frozen=True)
class AgentAppTextMatchReport:
    query: str = ""
    evidence: tuple[AgentAppElementEvidence, ...] = ()

    @property
    def requested(self) -> bool:
        return bool(self.query)

    @property
    def matched(self) -> bool:
        return not self.requested or bool(self.evidence)

    @property
    def visible(self) -> bool:
        return any(item.visible for item in self.evidence)

    @property
    def decision(self) -> str:
        if not self.requested:
            return "not_requested"
        if self.visible:
            return "matched_visible"
        if self.evidence:
            return "matched_accessible_tree_only"
        return "missing"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "requested": self.requested,
            "matched": self.matched,
            "visible": self.visible,
            "decision": self.decision,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclasses.dataclass(frozen=True)
class AgentAppWindowEvidence:
    process_name: str
    pid: int
    window_title: str
    class_name: str = ""
    hwnd: int = 0
    element_count: int = 0
    input_candidate_count: int = 0
    semantic_input_count: int = 0
    text_readable_count: int = 0
    capability_score: int = 0
    capability_level: str = ""
    risks: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "process_name": self.process_name,
            "pid": int(self.pid or 0),
            "window_title": self.window_title,
            "class_name": self.class_name,
            "hwnd": int(self.hwnd or 0),
            "element_count": int(self.element_count or 0),
            "input_candidate_count": int(self.input_candidate_count or 0),
            "semantic_input_count": int(self.semantic_input_count or 0),
            "text_readable_count": int(self.text_readable_count or 0),
            "capability_score": int(self.capability_score or 0),
            "capability_level": self.capability_level,
            "risks": list(self.risks),
        }


@dataclasses.dataclass(frozen=True)
class AgentAppUiaProbeReport:
    agent: str
    project_name: str
    task_name: str
    surface_binding: AgentSurfaceBindingReport
    matched_windows: tuple[AccessibilityWindowSnapshot, ...]
    project_match: AgentAppTextMatchReport
    task_match: AgentAppTextMatchReport
    composer_candidates: tuple[AgentAppElementEvidence, ...]
    background_screenshots: tuple[BackgroundWindowCaptureReport, ...] = ()
    foreground_takeover_request: ForegroundTakeoverRequest | None = None
    accessibility_window_count: int = 0
    accessibility_total_elements: int = 0
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "agent-app-uia-probe"

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
    def matched_window_count(self) -> int:
        return len(self.matched_windows)

    @property
    def composer_candidate_count(self) -> int:
        return len(self.composer_candidates)

    @property
    def semantic_composer_count(self) -> int:
        return sum(1 for item in self.composer_candidates if item.semantic_composer)

    @property
    def background_screenshot_count(self) -> int:
        return len(self.background_screenshots)

    @property
    def background_screenshot_success_count(self) -> int:
        return sum(1 for item in self.background_screenshots if item.ok)

    @property
    def background_screenshot_focus_stable(self) -> bool:
        return not any(item.foreground_changed for item in self.background_screenshots)

    @property
    def target_matched(self) -> bool:
        return self.project_match.matched and self.task_match.matched

    @property
    def ok(self) -> bool:
        return (
            self.surface_binding.ok
            and self.matched_window_count > 0
            and self.target_matched
            and self.semantic_composer_count > 0
        )

    @property
    def decision(self) -> str:
        if not self.surface_binding.ok or not _selected_app_surface(self.surface_binding):
            return "agent_app_surface_not_ready"
        if not self.matched_windows:
            return "agent_app_window_not_found"
        if not self.project_match.matched:
            return "agent_app_project_not_visible"
        if not self.task_match.matched:
            return "agent_app_task_not_visible"
        if self.semantic_composer_count:
            return "agent_app_uia_ready"
        if self.composer_candidates:
            return "agent_app_uia_composer_not_semantic"
        return "agent_app_uia_target_visible_input_not_found"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "agent": self.agent,
            "agent_id": self.surface_binding.agent_id,
            "project_name": self.project_name,
            "task_name": self.task_name,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "accessibility_window_count": int(self.accessibility_window_count or 0),
            "accessibility_total_elements": int(self.accessibility_total_elements or 0),
            "matched_window_count": self.matched_window_count,
            "matched_windows": [_window_evidence(item).to_dict() for item in self.matched_windows],
            "project_match": self.project_match.to_dict(),
            "task_match": self.task_match.to_dict(),
            "target_matched": self.target_matched,
            "composer_candidate_count": self.composer_candidate_count,
            "semantic_composer_count": self.semantic_composer_count,
            "composer_candidates": [item.to_dict() for item in self.composer_candidates],
            "background_screenshot_count": self.background_screenshot_count,
            "background_screenshot_success_count": self.background_screenshot_success_count,
            "background_screenshot_focus_stable": self.background_screenshot_focus_stable,
            "background_screenshots": [item.to_dict() for item in self.background_screenshots],
            "foreground_takeover_request": (
                self.foreground_takeover_request.to_dict()
                if self.foreground_takeover_request
                else {}
            ),
            "selected_transport": (
                self.surface_binding.selected_transport.to_dict()
                if self.surface_binding.selected_transport
                else {}
            ),
            "surface_binding": self.surface_binding.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_agent_app_uia_probe(
    *,
    agent: str,
    project_name: str = "",
    task_name: str = "",
    observer: object | None = None,
    resolver: WindowsAppResolver | None = None,
    accessibility_report: AccessibilityCapabilityReport | None = None,
    screenshot_dir: str | Path = "",
    window_capture_provider: object | None = None,
    max_windows: int = 80,
    max_elements: int = 1200,
) -> AgentAppUiaProbeReport:
    started = time.perf_counter()
    surface = build_agent_surface_binding(agent, resolver=resolver)
    report = accessibility_report or WindowsCapabilityProbe(
        observer=observer
        or PywinautoAccessibilityObserver(
            max_windows=max(1, int(max_windows or 1)),
            max_elements_per_window=max(1, int(max_elements or 1)),
        )
    ).run()
    matched_windows = _matching_agent_windows(
        report.windows,
        surface=surface,
    )
    project_match = _match_text(matched_windows, str(project_name or "").strip())
    task_match = _match_text(matched_windows, str(task_name or "").strip())
    composer_candidates = _find_composer_candidates(matched_windows)
    background_screenshots = _capture_background_screenshots(
        matched_windows,
        screenshot_dir=screenshot_dir,
        window_capture_provider=window_capture_provider,
    )
    foreground_request = None
    if surface.ok and matched_windows and project_match.matched and task_match.matched and not any(
        item.semantic_composer for item in composer_candidates
    ):
        foreground_request = _build_app_foreground_request(surface)
    return AgentAppUiaProbeReport(
        agent=str(agent or "").strip(),
        project_name=str(project_name or "").strip(),
        task_name=str(task_name or "").strip(),
        surface_binding=surface,
        matched_windows=matched_windows,
        project_match=project_match,
        task_match=task_match,
        composer_candidates=composer_candidates,
        background_screenshots=background_screenshots,
        foreground_takeover_request=foreground_request,
        accessibility_window_count=report.window_count,
        accessibility_total_elements=report.total_elements,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def load_accessibility_report(path: str | Path) -> AccessibilityCapabilityReport:
    data = _load_json_file(path)
    windows = tuple(_window_from_dict(item) for item in data.get("windows", []) if isinstance(item, dict))
    return AccessibilityCapabilityReport(windows=windows, elapsed_ms=float(data.get("elapsed_ms", 0) or 0))


def format_agent_app_uia_probe_report(report: AgentAppUiaProbeReport) -> str:
    lines = [
        "Agent App UIA Probe",
        f"Decision: {report.decision}  OK: {str(report.ok).lower()}  Control attempts: {report.control_attempts}",
        f"Agent: {report.agent}  Project: {report.project_name or '-'}  Task: {report.task_name or '-'}",
        f"Matched windows: {report.matched_window_count}  Composer candidates: {report.composer_candidate_count}  Semantic composers: {report.semantic_composer_count}",
        f"Background screenshots: {report.background_screenshot_success_count}/{report.background_screenshot_count}",
        f"Project match: {report.project_match.decision}  Task match: {report.task_match.decision}",
    ]
    for window in report.matched_windows:
        lines.append(
            f"- {window.process_name} pid={window.pid} {window.window_title} "
            f"score={window.capability_score()} level={window.capability_level()}"
        )
    return "\n".join(lines).rstrip()


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
    observer: object | None = None,
    window_capture_provider: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Run a read-only agent app UIA probe.")
    parser.add_argument("--agent", required=True, help="Agent app surface, for example 'codex app'.")
    parser.add_argument("--project-name", default="", help="Expected project/workspace name.")
    parser.add_argument("--task-name", default="", help="Expected task or conversation name.")
    parser.add_argument("--input", default="", help="Replay an accessibility_probe JSON file.")
    parser.add_argument("--output", default="", help="Write the probe report JSON to a file.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--screenshot-dir", default="", help="Optionally write no-focus background screenshots for matched windows.")
    parser.add_argument("--max-windows", type=int, default=80)
    parser.add_argument("--max-elements", type=int, default=1200)
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else WindowsAppResolver()
    accessibility_report = load_accessibility_report(args.input) if args.input else None
    report = run_agent_app_uia_probe(
        agent=args.agent,
        project_name=args.project_name,
        task_name=args.task_name,
        observer=observer,
        resolver=resolver,
        accessibility_report=accessibility_report,
        screenshot_dir=args.screenshot_dir,
        window_capture_provider=window_capture_provider,
        max_windows=args.max_windows,
        max_elements=args.max_elements,
    )
    payload = report.to_dict()
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        _write_stdout(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _write_stdout(format_agent_app_uia_probe_report(report))
    return 0


def _matching_agent_windows(
    windows: Iterable[AccessibilityWindowSnapshot],
    *,
    surface: AgentSurfaceBindingReport,
) -> tuple[AccessibilityWindowSnapshot, ...]:
    process_names = set(_agent_process_names(surface.agent_id))
    selected = surface.selected_transport
    selected_pid = int(selected.pid or 0) if selected else 0
    matched: list[AccessibilityWindowSnapshot] = []
    for window in windows:
        process_name = lower_text(window.process_name)
        if selected_pid and int(window.pid or 0) == selected_pid:
            matched.append(window)
            continue
        if process_name in process_names:
            matched.append(window)
    return tuple(matched)


def _capture_background_screenshots(
    windows: tuple[AccessibilityWindowSnapshot, ...],
    *,
    screenshot_dir: str | Path = "",
    window_capture_provider: object | None = None,
) -> tuple[BackgroundWindowCaptureReport, ...]:
    if not str(screenshot_dir or "").strip():
        return ()
    provider = window_capture_provider or PrintWindowBackgroundCaptureProvider()
    capture = getattr(provider, "capture_window", None)
    if not callable(capture):
        return ()
    root = Path(screenshot_dir)
    reports: list[BackgroundWindowCaptureReport] = []
    for index, window in enumerate(windows, start=1):
        hwnd = int(window.hwnd or 0)
        if hwnd <= 0:
            continue
        stem = _safe_filename(
            f"{index:02d}-{window.process_name or 'window'}-{window.pid or 0}-{hwnd}"
        )
        output_path = root / f"{stem}.png"
        try:
            report = capture(hwnd, output_path)
        except Exception as exc:
            report = BackgroundWindowCaptureReport(
                hwnd=hwnd,
                output_path=str(output_path),
                ok=False,
                error=f"capture_exception:{type(exc).__name__}",
            )
        reports.append(report)
    return tuple(reports)


def _match_text(
    windows: tuple[AccessibilityWindowSnapshot, ...],
    query: str,
) -> AgentAppTextMatchReport:
    normalized_query = lower_text(query)
    if not normalized_query:
        return AgentAppTextMatchReport(query="")
    evidence: list[AgentAppElementEvidence] = []
    for window in windows:
        if normalized_query in lower_text(window.window_title):
            evidence.append(
                AgentAppElementEvidence(
                    control_type="Window",
                    name=window.window_title,
                    value_preview=window.window_title,
                    rect=(0, 0, 0, 0),
                    is_enabled=True,
                    process_name=window.process_name,
                    window_title=window.window_title,
                    pid=window.pid,
                    visible=True,
                )
            )
        for element in window.elements:
            haystack = " ".join(
                (
                    element.name,
                    element.automation_id,
                    element.class_name,
                    element.value_preview,
                )
            )
            if normalized_query not in lower_text(haystack):
                continue
            evidence.append(_element_evidence(window, element))
    return AgentAppTextMatchReport(
        query=query,
        evidence=tuple(evidence[:20]),
    )


def _find_composer_candidates(
    windows: tuple[AccessibilityWindowSnapshot, ...],
) -> tuple[AgentAppElementEvidence, ...]:
    candidates: list[AgentAppElementEvidence] = []
    for window in windows:
        for element in window.elements:
            if not _is_composer_candidate(window, element):
                continue
            candidates.append(_element_evidence(window, element))
    candidates.sort(key=lambda item: (not item.semantic_composer, not item.visible, -item.rect[1]))
    return tuple(candidates[:20])


def _is_composer_candidate(
    window: AccessibilityWindowSnapshot,
    element: AccessibilityElementSnapshot,
) -> bool:
    control_type = str(element.control_type or "")
    if control_type not in {"Edit", "Document", "ComboBox"}:
        return False
    text = lower_text(
        " ".join(
            (
                element.name,
                element.automation_id,
                element.class_name,
                element.value_preview,
            )
        )
    )
    has_hint = any(hint in text for hint in _COMPOSER_HINTS)
    has_semantic = bool(set(element.patterns) & _SEMANTIC_COMPOSER_PATTERNS)
    visible = _rect_visible(element.rect, _window_root_rect(window))
    near_bottom = visible and int(element.rect[1] or 0) >= 500
    if control_type == "Edit":
        return bool(element.is_enabled and (has_hint or has_semantic or near_bottom))
    return bool(element.is_enabled and has_hint)


def _element_evidence(
    window: AccessibilityWindowSnapshot,
    element: AccessibilityElementSnapshot,
) -> AgentAppElementEvidence:
    return AgentAppElementEvidence(
        control_type=element.control_type,
        name=element.name,
        automation_id=element.automation_id,
        class_name=element.class_name,
        value_preview=element.value_preview,
        rect=element.rect,
        is_enabled=element.is_enabled,
        patterns=element.patterns,
        process_name=window.process_name,
        window_title=window.window_title,
        pid=window.pid,
        visible=_rect_visible(element.rect, _window_root_rect(window)),
    )


def _window_evidence(window: AccessibilityWindowSnapshot) -> AgentAppWindowEvidence:
    return AgentAppWindowEvidence(
        process_name=window.process_name,
        pid=window.pid,
        window_title=window.window_title,
        class_name=window.class_name,
        hwnd=window.hwnd,
        element_count=window.element_count,
        input_candidate_count=window.input_candidate_count,
        semantic_input_count=window.semantic_input_count,
        text_readable_count=window.text_readable_count,
        capability_score=window.capability_score(),
        capability_level=window.capability_level(),
        risks=window.risks(),
    )


def _build_app_foreground_request(surface: AgentSurfaceBindingReport) -> ForegroundTakeoverRequest:
    selected = surface.selected_transport
    return ForegroundTakeoverRequest(
        status="approval_required",
        action="send_agent_app_conversation_message",
        app_family=surface.agent_id,
        target_process_name=_process_name_for_agent(surface.agent_id),
        target_window_title=surface.agent_name,
        selected_route=selected.route_id if selected else "",
        selected_transport=selected.transport if selected else "",
        transport_channel="foreground_or_native_bridge",
        risk_flags=("agent_task_submission", "foreground_focus_or_native_bridge"),
        verification_requirements=(
            "target_project_or_task_name_visible",
            "message_echo_or_result_marker_visible",
        ),
        request_reason="agent_app_uia_composer_not_background_semantic",
    )


def _window_from_dict(data: dict) -> AccessibilityWindowSnapshot:
    return AccessibilityWindowSnapshot(
        pid=int(data.get("pid", 0) or 0),
        process_name=str(data.get("process_name", "") or ""),
        window_title=str(data.get("window_title", "") or ""),
        class_name=str(data.get("class_name", "") or ""),
        hwnd=int(data.get("hwnd", 0) or 0),
        elements=tuple(
            _element_from_dict(item)
            for item in data.get("elements", [])
            if isinstance(item, dict)
        ),
        scan_error=str(data.get("scan_error", "") or ""),
    )


def _load_json_file(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    try:
        loaded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        loaded = None
        for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                loaded = json.loads(raw.decode(encoding))
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        if loaded is None:
            raise
    if not isinstance(loaded, dict):
        raise ValueError("accessibility report JSON must be an object")
    return loaded


def _element_from_dict(data: dict) -> AccessibilityElementSnapshot:
    rect = data.get("rect", (0, 0, 0, 0))
    return AccessibilityElementSnapshot(
        control_type=str(data.get("control_type", "") or "Unknown"),
        name=str(data.get("name", "") or ""),
        automation_id=str(data.get("automation_id", "") or ""),
        class_name=str(data.get("class_name", "") or ""),
        value_preview=str(data.get("value_preview", "") or ""),
        rect=_rect_tuple(rect),
        is_enabled=bool(data.get("is_enabled", False)),
        patterns=tuple(str(item) for item in data.get("patterns", []) if str(item or "").strip()),
    )


def _rect_tuple(value: object) -> tuple[int, int, int, int]:
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError:
        items = []
    padded = (items + [0, 0, 0, 0])[:4]
    return tuple(int(item or 0) for item in padded)  # type: ignore[return-value]


def _rect_visible(
    rect: tuple[int, int, int, int],
    bounds: tuple[int, int, int, int] | None = None,
) -> bool:
    left, top, right, bottom = _rect_tuple(rect)
    if not (right > left and bottom > top):
        return False
    if bounds is None:
        return right > 0 and bottom > 0 and left < 10000 and top < 10000
    bound_left, bound_top, bound_right, bound_bottom = _rect_tuple(bounds)
    if not (bound_right > bound_left and bound_bottom > bound_top):
        return right > 0 and bottom > 0 and left < 10000 and top < 10000
    return (
        right > bound_left
        and left < bound_right
        and bottom > bound_top
        and top < bound_bottom
    )


def _window_root_rect(window: AccessibilityWindowSnapshot) -> tuple[int, int, int, int] | None:
    for element in window.elements:
        automation_id = str(element.automation_id or "")
        class_name = str(element.class_name or "")
        if (
            automation_id == "RootWebArea"
            or class_name == "RootView"
            or element.control_type == "Document"
        ):
            rect = _rect_tuple(element.rect)
            if rect[2] > rect[0] and rect[3] > rect[1]:
                return rect
    return None


def _selected_app_surface(surface: AgentSurfaceBindingReport) -> bool:
    selected = surface.selected_transport
    if selected is None:
        return False
    text = lower_text(" ".join((selected.transport_id, selected.transport, selected.route_id)))
    return "desktop" in text or "app" in text or "shell" in text


def _agent_process_names(agent_id: str) -> tuple[str, ...]:
    normalized = lower_text(agent_id)
    if normalized == "codex":
        return ("codex.exe",)
    if normalized == "claude":
        return ("claude.exe",)
    if normalized == "cursor":
        return ("cursor.exe",)
    return (normalized,)


def _process_name_for_agent(agent_id: str) -> str:
    normalized = lower_text(agent_id)
    if normalized == "codex":
        return "Codex.exe"
    if normalized == "claude":
        return "Claude.exe"
    if normalized == "cursor":
        return "Cursor.exe"
    return str(agent_id or "").strip()


def _safe_filename(value: str) -> str:
    text = "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "-"
        for ch in str(value or "")
    )
    text = "-".join(part for part in text.split("-") if part)
    return text[:120] or "window"


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
