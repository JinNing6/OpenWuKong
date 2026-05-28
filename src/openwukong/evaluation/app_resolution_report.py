# -*- coding: utf-8 -*-
"""Read-only app resolution diagnostics CLI."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from openwukong.control.app_resolution import (
    AppPathVerifier,
    PowerShellAuthenticodeSignatureReader,
    WindowsAppResolver,
)


@dataclasses.dataclass(frozen=True)
class AppResolutionDiagnosticsReport:
    app_names: tuple[str, ...]
    resolutions: tuple[object, ...]
    cache_path: str = ""
    cache_write_enabled: bool = False
    signature_verification_enabled: bool = False
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "app-resolution-report"

    @property
    def safety_mode(self) -> str:
        return "read_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def summary(self) -> dict:
        errors = Counter(str(_resolution_dict(item).get("error", "") or "") for item in self.resolutions)
        return {
            "app_count": len(self.resolutions),
            "resolved": sum(1 for item in self.resolutions if bool(_resolution_dict(item).get("ok"))),
            "not_found": errors.get("app_not_found", 0),
            "ambiguous": errors.get("ambiguous_app_candidates", 0),
            "already_running": sum(
                1 for item in self.resolutions if bool(_resolution_dict(item).get("already_running"))
            ),
            "cache_write_enabled": self.cache_write_enabled,
            "signature_verification_enabled": self.signature_verification_enabled,
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "cache_path": self.cache_path,
            "summary": self.summary(),
            "apps": [
                _app_entry(app_name, resolution)
                for app_name, resolution in zip(self.app_names, self.resolutions)
            ],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def build_app_resolution_report(
    app_names: Iterable[str],
    *,
    resolver: WindowsAppResolver | None = None,
    cache_path: str | Path = "",
    cache_write_enabled: bool = False,
    verify_signature: bool = False,
) -> AppResolutionDiagnosticsReport:
    started = time.perf_counter()
    names = tuple(str(name or "").strip() for name in app_names if str(name or "").strip())
    verifier = AppPathVerifier(
        signature_reader=PowerShellAuthenticodeSignatureReader() if verify_signature else None
    )
    active_resolver = resolver or WindowsAppResolver(
        cache_path=cache_path,
        cache_write_enabled=cache_write_enabled,
        path_verifier=verifier,
    )
    resolutions = tuple(active_resolver.resolve(name) for name in names)
    return AppResolutionDiagnosticsReport(
        app_names=names,
        resolutions=resolutions,
        cache_path=str(cache_path or ""),
        cache_write_enabled=cache_write_enabled,
        signature_verification_enabled=verify_signature,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(
    argv: Optional[list[str]] = None,
    *,
    resolver_factory: object | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only app resolution diagnostics report."
    )
    parser.add_argument(
        "--app-name",
        action="append",
        required=True,
        help="Application name or alias to resolve. Repeat for multiple apps.",
    )
    parser.add_argument("--cache-path", default="", help="Optional app resolution cache path.")
    parser.add_argument("--write-cache", action="store_true", help="Write high-confidence resolutions to cache.")
    parser.add_argument(
        "--verify-signature",
        action="store_true",
        help="Collect Authenticode signature metadata for verified executable paths.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print report JSON.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when any app is unresolved.")
    args = parser.parse_args(argv)

    resolver = resolver_factory(args) if callable(resolver_factory) else None
    report = build_app_resolution_report(
        args.app_name,
        resolver=resolver,
        cache_path=args.cache_path,
        cache_write_enabled=args.write_cache,
        verify_signature=args.verify_signature,
    )
    data = report.to_dict()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        summary = data["summary"]
        _write_stdout(
            "App resolution report: "
            f"apps={summary['app_count']} "
            f"resolved={summary['resolved']} "
            f"not_found={summary['not_found']} "
            f"ambiguous={summary['ambiguous']} "
            f"already_running={summary['already_running']}"
        )
    if args.strict and data["summary"]["resolved"] != data["summary"]["app_count"]:
        return 1
    return 0


def _app_entry(app_name: str, resolution: object) -> dict:
    data = _resolution_dict(resolution)
    candidates = data.get("candidates", [])
    selected = data.get("selected_candidate", {})
    return {
        "app_name": app_name,
        "ok": bool(data.get("ok")),
        "decision": str(data.get("decision", "")),
        "source": str(data.get("source", "")),
        "path": str(data.get("path", "")),
        "already_running": bool(data.get("already_running")),
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "selected_candidate": selected if isinstance(selected, dict) else {},
        "resolution": data,
    }


def _resolution_dict(resolution: object) -> dict:
    if hasattr(resolution, "to_dict") and callable(getattr(resolution, "to_dict")):
        return dict(resolution.to_dict())
    if isinstance(resolution, dict):
        return dict(resolution)
    return {}


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
