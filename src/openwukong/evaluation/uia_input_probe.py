# -*- coding: utf-8 -*-
"""Guarded UIA input probe.

This probe writes a unique token into a located input, verifies it through the
visible UIA tree, and clears it without submitting by default.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from openwukong.control.application_bus import (
    ApplicationControlBus,
    ControlTarget,
    InputActionOptions,
    PywinautoUIABackend,
)


def main(argv: Optional[list[str]] = None, *, bus: Optional[ApplicationControlBus] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe a UIA input by writing, verifying, and clearing a token."
    )
    parser.add_argument("--pid", type=int, required=True, help="Target process PID.")
    parser.add_argument("--process-name", default="", help="Target process name.")
    parser.add_argument("--window-title", default="", help="Preferred target window title.")
    parser.add_argument("--token", default="", help="Token to write. Generated if omitted.")
    parser.add_argument(
        "--method",
        action="append",
        default=[],
        help="Input method to try. Repeatable. Defaults to set_text, clipboard_paste, type_text.",
    )
    parser.add_argument(
        "--no-clear-after",
        action="store_true",
        help="Leave the token in the input after verification.",
    )
    parser.add_argument(
        "--background-safe",
        action="store_true",
        help="Do not focus the window or use clipboard/keyboard fallback methods.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print report as JSON.")
    args = parser.parse_args(argv)

    token = args.token or _default_token()
    control_bus = bus or ApplicationControlBus(PywinautoUIABackend())
    options = InputActionOptions(
        clear_after=not args.no_clear_after,
        allow_foreground_interaction=not args.background_safe,
        methods=tuple(args.method) if args.method else InputActionOptions().methods,
    )
    report = control_bus.write_text(
        ControlTarget(
            pid=args.pid,
            process_name=args.process_name,
            window_title=args.window_title,
        ),
        token,
        options,
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
        status = "ok" if report.ok else "failed"
        _write_stdout(
            "UIA input probe "
            f"{status}: attempts={report.control_attempts} "
            f"method={report.write_method or '-'} error={report.error or '-'}"
        )
    return 0


def _default_token() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"OPENWUKONG_UIA_INPUT_PROBE_{stamp}"


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
