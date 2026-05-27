# -*- coding: utf-8 -*-
"""Read-only Windows accessibility capability probe.

The probe inventories windows and exposed UI elements, then estimates whether an
app can be operated through semantic APIs such as UI Automation control
patterns. It does not click, type, invoke, set values, or read connector
transcripts.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from typing import Iterable, Optional


_INPUT_CONTROL_TYPES = {"Edit", "Document", "ComboBox"}
_ACTION_CONTROL_TYPES = {"Button", "Hyperlink", "MenuItem", "SplitButton", "CheckBox", "RadioButton"}
_TEXT_CONTROL_TYPES = {"Text", "Edit", "Document"}
_SEMANTIC_INPUT_PATTERNS = {"Value", "TextEdit"}
_SEMANTIC_ACTION_PATTERNS = {"Invoke", "SelectionItem", "Toggle", "ExpandCollapse"}
_READABLE_PATTERNS = {"Text", "Value"}

_BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
}
_IDE_PROCESSES = {
    "code.exe",
    "code - insiders.exe",
    "cursor.exe",
    "codex.exe",
    "antigravity.exe",
    "windsurf.exe",
}
_OFFICE_PROCESSES = {
    "winword.exe",
    "excel.exe",
    "powerpnt.exe",
    "outlook.exe",
    "onenote.exe",
    "msaccess.exe",
}


@dataclasses.dataclass(frozen=True)
class AccessibilityElementSnapshot:
    control_type: str
    name: str = ""
    automation_id: str = ""
    class_name: str = ""
    value_preview: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    is_enabled: bool = False
    patterns: tuple[str, ...] = ()

    @property
    def is_input_candidate(self) -> bool:
        return self.control_type in _INPUT_CONTROL_TYPES

    @property
    def is_action_candidate(self) -> bool:
        return self.control_type in _ACTION_CONTROL_TYPES

    @property
    def has_semantic_input(self) -> bool:
        return bool(set(self.patterns) & _SEMANTIC_INPUT_PATTERNS)

    @property
    def has_semantic_action(self) -> bool:
        return bool(set(self.patterns) & _SEMANTIC_ACTION_PATTERNS)

    @property
    def is_text_readable(self) -> bool:
        if self.control_type in _TEXT_CONTROL_TYPES:
            return True
        return bool(set(self.patterns) & _READABLE_PATTERNS)

    @property
    def has_stable_identifier(self) -> bool:
        return bool((self.automation_id or "").strip() or (self.name or "").strip())

    def to_dict(self) -> dict:
        return {
            "control_type": self.control_type,
            "name": self.name,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "value_preview": self.value_preview,
            "rect": list(self.rect),
            "is_enabled": self.is_enabled,
            "patterns": list(self.patterns),
        }


@dataclasses.dataclass(frozen=True)
class AccessibilityWindowSnapshot:
    pid: int
    process_name: str
    window_title: str
    class_name: str = ""
    hwnd: int = 0
    elements: tuple[AccessibilityElementSnapshot, ...] = ()
    scan_error: str = ""

    @property
    def element_count(self) -> int:
        return len(self.elements)

    @property
    def input_candidate_count(self) -> int:
        return sum(1 for element in self.elements if element.is_input_candidate)

    @property
    def semantic_input_count(self) -> int:
        return sum(1 for element in self.elements if element.is_input_candidate and element.has_semantic_input)

    @property
    def semantic_action_count(self) -> int:
        return sum(1 for element in self.elements if element.is_action_candidate and element.has_semantic_action)

    @property
    def text_readable_count(self) -> int:
        return sum(1 for element in self.elements if element.is_text_readable)

    @property
    def stable_identifier_count(self) -> int:
        return sum(1 for element in self.elements if element.has_stable_identifier)

    def control_type_counts(self) -> dict:
        return dict(sorted(Counter(element.control_type for element in self.elements).items()))

    def pattern_counts(self) -> dict:
        counts: Counter[str] = Counter()
        for element in self.elements:
            counts.update(element.patterns)
        return dict(sorted(counts.items()))

    def capability_score(self) -> int:
        score = 10
        if self.scan_error:
            score -= 10
        score += min(self.element_count, 50) // 2
        if self.input_candidate_count:
            score += 15
        if self.semantic_input_count:
            score += 25
        if self.semantic_action_count:
            score += 20
        if self.text_readable_count:
            score += 15
        if self.stable_identifier_count:
            score += min(10, int(self.stable_identifier_count / max(1, self.element_count) * 10))
        return max(0, min(100, score))

    def capability_level(self) -> str:
        score = self.capability_score()
        if self.element_count == 0:
            return "window_only"
        if self.semantic_input_count or self.semantic_action_count:
            return "semantic" if score >= 70 else "partial_semantic"
        if self.input_candidate_count or self.text_readable_count:
            return "structural"
        return "structure_only"

    def risks(self) -> tuple[str, ...]:
        risks: list[str] = []
        if self.scan_error:
            risks.append("scan_error")
        if self.element_count == 0:
            risks.append("no_accessible_elements")
        if self.input_candidate_count and not self.semantic_input_count:
            risks.append("input_without_semantic_pattern")
        if self.stable_identifier_count < max(1, self.element_count // 3) and self.element_count:
            risks.append("weak_stable_identifiers")
        if self.capability_score() < 40:
            risks.append("low_confidence")
        return tuple(risks)

    def recommended_routes(self) -> tuple[str, ...]:
        routes: list[str] = []
        pname = self.process_name.lower()
        if pname in _BROWSER_PROCESSES:
            routes.append("browser-devtools-or-extension")
        if pname in _IDE_PROCESSES:
            routes.append("ide-extension-connector")
        if pname in _OFFICE_PROCESSES:
            routes.append("office-object-model-or-addin")
        if self.capability_level() in {"semantic", "partial_semantic"}:
            routes.append("uia-semantic")
        elif self.element_count:
            routes.append("uia-structural")
        routes.append("msaa-win32-fallback")
        routes.append("vision-fallback-last")
        return tuple(dict.fromkeys(routes))

    def to_dict(self, *, include_elements: bool = True) -> dict:
        from openwukong.connectors.route_policy import build_control_route_plan

        data = {
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "class_name": self.class_name,
            "hwnd": self.hwnd,
            "scan_error": self.scan_error,
            "element_count": self.element_count,
            "control_type_counts": self.control_type_counts(),
            "pattern_counts": self.pattern_counts(),
            "input_candidate_count": self.input_candidate_count,
            "semantic_input_count": self.semantic_input_count,
            "semantic_action_count": self.semantic_action_count,
            "text_readable_count": self.text_readable_count,
            "stable_identifier_count": self.stable_identifier_count,
            "capability_score": self.capability_score(),
            "capability_level": self.capability_level(),
            "risks": list(self.risks()),
            "recommended_routes": list(self.recommended_routes()),
            "control_route_plan": build_control_route_plan(self).to_dict(),
        }
        if include_elements:
            data["elements"] = [element.to_dict() for element in self.elements]
        return data


@dataclasses.dataclass(frozen=True)
class AccessibilityCapabilityReport:
    windows: tuple[AccessibilityWindowSnapshot, ...]
    elapsed_ms: float = 0.0

    @property
    def window_count(self) -> int:
        return len(self.windows)

    @property
    def total_elements(self) -> int:
        return sum(window.element_count for window in self.windows)

    @property
    def control_attempts(self) -> int:
        return 0

    def capability_levels(self) -> dict:
        return dict(sorted(Counter(window.capability_level() for window in self.windows).items()))

    def to_dict(self, *, include_elements: bool = True) -> dict:
        from openwukong.connectors.route_policy import build_control_route_matrix

        sorted_windows = sorted(
            self.windows,
            key=lambda item: (-item.capability_score(), item.process_name.lower(), item.window_title.lower()),
        )
        return {
            "mode": "windows-accessibility-capability",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": self.control_attempts,
            "window_count": self.window_count,
            "total_elements": self.total_elements,
            "capability_levels": self.capability_levels(),
            "windows": [
                window.to_dict(include_elements=include_elements)
                for window in sorted_windows
            ],
            "route_matrix": build_control_route_matrix(sorted_windows).to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class StaticAccessibilityObserver:
    def __init__(self, windows: Iterable[AccessibilityWindowSnapshot]):
        self._windows = tuple(windows)

    def snapshot(self) -> tuple[AccessibilityWindowSnapshot, ...]:
        return self._windows


class PywinautoAccessibilityObserver:
    """Read-only observer that inventories UIA metadata from visible windows."""

    def __init__(self, *, max_windows: int = 30, max_elements_per_window: int = 200):
        self.max_windows = max_windows
        self.max_elements_per_window = max_elements_per_window

    def snapshot(self) -> tuple[AccessibilityWindowSnapshot, ...]:
        try:
            import psutil
            from pywinauto import Desktop
        except Exception as exc:
            return (
                AccessibilityWindowSnapshot(
                    pid=0,
                    process_name="",
                    window_title="",
                    elements=(),
                    scan_error=f"dependency_error: {exc}",
                ),
            )

        windows: list[AccessibilityWindowSnapshot] = []
        seen: set[tuple[int, str]] = set()
        try:
            desktop_windows = Desktop(backend="uia").windows()
        except Exception as exc:
            return (
                AccessibilityWindowSnapshot(
                    pid=0,
                    process_name="",
                    window_title="",
                    elements=(),
                    scan_error=f"desktop_scan_error: {exc}",
                ),
            )

        for wrapper in desktop_windows:
            if len(windows) >= self.max_windows:
                break
            try:
                title = wrapper.window_text() or ""
                if not title or title == "Program Manager":
                    continue
                pid = int(wrapper.process_id())
                key = (pid, title)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    process_name = psutil.Process(pid).name()
                except Exception:
                    process_name = ""
                windows.append(self._snapshot_window(wrapper, pid, process_name, title))
            except Exception:
                continue
        return tuple(windows)

    def _snapshot_window(self, wrapper, pid: int, process_name: str, title: str) -> AccessibilityWindowSnapshot:
        class_name = _safe_wrapper_attr(wrapper, "class_name")
        hwnd = _safe_handle(wrapper)
        try:
            descendants = wrapper.descendants()
        except Exception as exc:
            return AccessibilityWindowSnapshot(
                pid=pid,
                process_name=process_name,
                window_title=title,
                class_name=class_name,
                hwnd=hwnd,
                elements=(),
                scan_error=f"descendants_error: {exc}",
            )

        elements = []
        for child in descendants[: self.max_elements_per_window]:
            snapshot = _element_from_wrapper(child)
            if snapshot is not None:
                elements.append(snapshot)

        return AccessibilityWindowSnapshot(
            pid=pid,
            process_name=process_name,
            window_title=title,
            class_name=class_name,
            hwnd=hwnd,
            elements=tuple(elements),
            scan_error="",
        )


class WindowsCapabilityProbe:
    def __init__(self, *, observer: Optional[object] = None):
        self.observer = observer or PywinautoAccessibilityObserver()

    def run(self) -> AccessibilityCapabilityReport:
        started = time.perf_counter()
        windows = tuple(self.observer.snapshot())
        return AccessibilityCapabilityReport(
            windows=windows,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )


def format_capability_report(report: AccessibilityCapabilityReport) -> str:
    lines = [
        "Windows Accessibility Capability",
        (
            f"Windows: {report.window_count}  Elements: {report.total_elements}  "
            f"Control attempts: {report.control_attempts}"
        ),
        "",
    ]
    for window in sorted(report.windows, key=lambda item: -item.capability_score()):
        lines.append(
            f"{window.capability_score():>3} {window.capability_level():<16} "
            f"{window.process_name or '-'} pid={window.pid} {window.window_title[:80]}"
        )
        lines.append(
            "    "
            f"elements={window.element_count} inputs={window.input_candidate_count} "
            f"semantic_inputs={window.semantic_input_count} "
            f"semantic_actions={window.semantic_action_count} "
            f"text={window.text_readable_count}"
        )
        if window.risks():
            lines.append(f"    risks={','.join(window.risks())}")
        lines.append(f"    routes={','.join(window.recommended_routes())}")
    return "\n".join(lines).rstrip()


def _element_from_wrapper(wrapper) -> Optional[AccessibilityElementSnapshot]:
    try:
        element_info = wrapper.element_info
    except Exception:
        return None

    control_type = _safe_element_info_attr(element_info, "control_type") or "Unknown"
    name = _safe_element_info_attr(element_info, "name")
    automation_id = _safe_element_info_attr(element_info, "automation_id")
    class_name = _safe_element_info_attr(element_info, "class_name")
    rect = _safe_rect(wrapper)
    is_enabled = _safe_bool_call(wrapper, "is_enabled")
    value_preview = _safe_value_preview(wrapper)
    patterns = _infer_patterns(wrapper, control_type)
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name[:200],
        automation_id=automation_id[:100],
        class_name=class_name[:100],
        value_preview=value_preview[:200],
        rect=rect,
        is_enabled=is_enabled,
        patterns=patterns,
    )


def _infer_patterns(wrapper, control_type: str) -> tuple[str, ...]:
    patterns: list[str] = []
    if control_type in {"Edit", "ComboBox"}:
        patterns.append("Value")
    if control_type in {"Text", "Edit", "Document"}:
        patterns.append("Text")
    if control_type in {"Button", "Hyperlink", "MenuItem", "SplitButton"}:
        patterns.append("Invoke")
    if control_type in {"List", "ListItem", "ComboBox", "DataGrid", "DataItem", "Tab", "TabItem"}:
        patterns.append("Selection")
    if control_type in {"DataGrid", "Table"}:
        patterns.append("Grid")
    if control_type in {"CheckBox", "RadioButton"}:
        patterns.append("Toggle")
    return tuple(sorted(dict.fromkeys(patterns)))


def _safe_element_info_attr(element_info, attr: str) -> str:
    try:
        return str(getattr(element_info, attr) or "")
    except Exception:
        return ""


def _safe_wrapper_attr(wrapper, attr: str) -> str:
    try:
        value = getattr(wrapper, attr)
        if callable(value):
            value = value()
        return str(value or "")
    except Exception:
        return ""


def _safe_handle(wrapper) -> int:
    for attr in ("handle", "hwnd"):
        try:
            value = getattr(wrapper, attr)
            if callable(value):
                value = value()
            return int(value or 0)
        except Exception:
            continue
    return 0


def _safe_rect(wrapper) -> tuple[int, int, int, int]:
    try:
        rect = wrapper.rectangle()
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return (0, 0, 0, 0)


def _safe_bool_call(wrapper, method_name: str) -> bool:
    try:
        method = getattr(wrapper, method_name)
        return bool(method())
    except Exception:
        return False


def _safe_value_preview(wrapper) -> str:
    for method_name in ("window_text", "get_value"):
        try:
            method = getattr(wrapper, method_name)
            value = method()
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def main(argv: Optional[list[str]] = None, *, observer: Optional[object] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only Windows accessibility capability probe."
    )
    parser.add_argument("--json", action="store_true", help="Print report as JSON.")
    parser.add_argument(
        "--no-elements",
        action="store_true",
        help="Omit per-element details from JSON output.",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=30,
        help="Maximum number of top-level windows to inspect in live mode.",
    )
    parser.add_argument(
        "--max-elements",
        type=int,
        default=200,
        help="Maximum number of UIA descendants to inspect per window in live mode.",
    )
    args = parser.parse_args(argv)

    live_observer = observer or PywinautoAccessibilityObserver(
        max_windows=max(1, args.max_windows),
        max_elements_per_window=max(1, args.max_elements),
    )
    report = WindowsCapabilityProbe(observer=live_observer).run()
    if args.json:
        _write_stdout(json.dumps(report.to_dict(include_elements=not args.no_elements), ensure_ascii=False, indent=2))
    else:
        _write_stdout(format_capability_report(report))
    return 0


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
