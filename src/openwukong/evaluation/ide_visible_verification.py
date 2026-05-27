# -*- coding: utf-8 -*-
"""Read-only visible text verification for IDE chat E2E checks."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from typing import Iterable, Optional

from openwukong.evaluation.accessibility_probe import (
    AccessibilityWindowSnapshot,
    PywinautoAccessibilityObserver,
    StaticAccessibilityObserver,
)


@dataclasses.dataclass(frozen=True)
class VisibleTextHit:
    pid: int
    process_name: str
    window_title: str
    source: str
    text_preview: str
    control_type: str = ""
    automation_id: str = ""
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "source": self.source,
            "text_preview": self.text_preview,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "rect": list(self.rect),
        }


@dataclasses.dataclass(frozen=True)
class VisibleTextVerificationReport:
    token: str
    process_names: tuple[str, ...]
    title_contains: tuple[str, ...]
    windows_scanned: int
    hits: tuple[VisibleTextHit, ...]
    elapsed_ms: float

    @property
    def mode(self) -> str:
        return "ide-visible-text-verification"

    @property
    def safety_mode(self) -> str:
        return "read_only_uia_scan"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def message_visible(self) -> bool:
        return bool(self.hits)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "token": self.token,
            "process_names": list(self.process_names),
            "title_contains": list(self.title_contains),
            "windows_scanned": self.windows_scanned,
            "message_visible": self.message_visible,
            "hit_count": len(self.hits),
            "hits": [hit.to_dict() for hit in self.hits],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def verify_visible_text(
    token: str,
    *,
    observer: Optional[object] = None,
    process_names: Iterable[str] = ("Cursor.exe",),
    title_contains: Iterable[str] = (),
    max_windows: int = 80,
    max_elements: int = 5000,
    timeout: float = 0.0,
    interval: float = 0.5,
) -> VisibleTextVerificationReport:
    token_value = str(token or "")
    if not token_value:
        raise ValueError("missing_visible_text_token")

    process_filter = _normalize_filter(process_names)
    title_filter = tuple(item.lower() for item in _normalize_filter(title_contains))
    started = time.perf_counter()
    deadline = started + max(0.0, float(timeout))
    latest_report = VisibleTextVerificationReport(
        token=token_value,
        process_names=process_filter,
        title_contains=title_filter,
        windows_scanned=0,
        hits=(),
        elapsed_ms=0.0,
    )

    while True:
        live_observer = observer or PywinautoAccessibilityObserver(
            max_windows=max(1, int(max_windows)),
            max_elements_per_window=max(1, int(max_elements)),
        )
        windows = tuple(live_observer.snapshot())
        hits = tuple(_find_hits(windows, token_value, process_filter, title_filter))
        latest_report = VisibleTextVerificationReport(
            token=token_value,
            process_names=process_filter,
            title_contains=title_filter,
            windows_scanned=len(windows),
            hits=hits,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        if hits or timeout <= 0 or time.perf_counter() >= deadline:
            return latest_report
        time.sleep(max(0.05, float(interval)))


def main(argv: Optional[list[str]] = None, *, observer: Optional[object] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify whether a token is exposed in visible IDE UIA text."
    )
    parser.add_argument("token", help="Unique text token to find in the IDE UI.")
    parser.add_argument("--process-name", action="append", default=[], help="Target process name. Repeatable.")
    parser.add_argument("--title-contains", action="append", default=[], help="Window-title substring filter. Repeatable.")
    parser.add_argument("--max-windows", type=int, default=80, help="Maximum top-level windows to inspect.")
    parser.add_argument("--max-elements", type=int, default=5000, help="Maximum descendants to inspect per window.")
    parser.add_argument("--timeout", type=float, default=0.0, help="Seconds to poll until the token appears.")
    parser.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print report as JSON.")
    args = parser.parse_args(argv)

    report = verify_visible_text(
        args.token,
        observer=observer,
        process_names=tuple(args.process_name or ["Cursor.exe"]),
        title_contains=tuple(args.title_contains or []),
        max_windows=args.max_windows,
        max_elements=args.max_elements,
        timeout=args.timeout,
        interval=args.interval,
    )
    data = report.to_dict()
    if args.output:
        from pathlib import Path

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        status = "visible" if report.message_visible else "not-visible"
        _write_stdout(
            f"IDE visible text verification {status}: "
            f"hits={len(report.hits)} windows={report.windows_scanned}"
        )
    return 0


def _find_hits(
    windows: tuple[AccessibilityWindowSnapshot, ...],
    token: str,
    process_filter: tuple[str, ...],
    title_filter: tuple[str, ...],
) -> list[VisibleTextHit]:
    needle = token.lower()
    hits: list[VisibleTextHit] = []
    for window in windows:
        if not _window_matches(window, process_filter, title_filter):
            continue
        title = window.window_title or ""
        if needle in title.lower():
            hits.append(
                VisibleTextHit(
                    pid=window.pid,
                    process_name=window.process_name,
                    window_title=window.window_title,
                    source="window_title",
                    text_preview=_clip(title),
                )
            )
        for element in window.elements:
            for source, text in (
                ("name", element.name),
                ("value_preview", element.value_preview),
            ):
                if text and needle in text.lower():
                    hits.append(
                        VisibleTextHit(
                            pid=window.pid,
                            process_name=window.process_name,
                            window_title=window.window_title,
                            source=source,
                            text_preview=_clip(text),
                            control_type=element.control_type,
                            automation_id=element.automation_id,
                            rect=element.rect,
                        )
                    )
    return hits


def _window_matches(
    window: AccessibilityWindowSnapshot,
    process_filter: tuple[str, ...],
    title_filter: tuple[str, ...],
) -> bool:
    if process_filter:
        process = (window.process_name or "").lower()
        if process not in process_filter:
            return False
    if title_filter:
        title = (window.window_title or "").lower()
        if not any(item in title for item in title_filter):
            return False
    return True


def _normalize_filter(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = str(value or "").strip().lower()
        if item and item not in seen:
            selected.append(item)
            seen.add(item)
    return tuple(selected)


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
