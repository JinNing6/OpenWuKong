# -*- coding: utf-8 -*-
"""Explicitly approved WeChat Moments publish probe."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from pathlib import Path
from typing import Iterable

from openwukong.control.foreground_takeover import (
    ForegroundTakeoverRequest,
    validate_foreground_takeover_request,
)
from openwukong.evaluation.wechat_send_probe import Win32WeChatKeyboardAutomation


@dataclasses.dataclass(frozen=True)
class WeChatMomentsPublishReport:
    status: str
    body_sha256: str
    visibility: str
    allow_publish: bool
    control_allowed: bool = False
    publish_attempts: int = 0
    keyboard_input_attempts: int = 0
    mouse_input_attempts: int = 0
    clipboard_write_attempts: int = 0
    clipboard_restore_attempts: int = 0
    foreground_restore_attempts: int = 0
    foreground_restored: bool | None = None
    final_foreground_hwnd: int = 0
    target_verified: bool = False
    moments_surface_verified: bool = False
    publish_panel_verified: bool = False
    post_publish_verified: bool = False
    post_publish_verification: dict = dataclasses.field(default_factory=dict)
    pre_publish_screenshot_path: str = ""
    publish_panel_screenshot_path: str = ""
    post_publish_screenshot_path: str = ""
    artifact_path: str = ""
    transport: str = "foreground-keyboard-clipboard"
    foreground_takeover_validated: bool = False
    foreground_takeover_validation: dict = dataclasses.field(default_factory=dict)
    foreground_takeover_request: dict = dataclasses.field(default_factory=dict)
    phases: tuple[dict, ...] = ()
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self) | {
            "mode": "wechat-moments-text-publish-probe",
            "safety_mode": "explicit_opt_in_real_publish",
            "body_sha256": self.body_sha256,
            "phases": [dict(phase) for phase in self.phases],
            "post_publish_verification": dict(self.post_publish_verification),
            "foreground_takeover_validation": dict(self.foreground_takeover_validation),
            "foreground_takeover_request": dict(self.foreground_takeover_request),
        }


def run_wechat_moments_text_publish_probe(
    *,
    body: str,
    visibility: str = "public",
    allow_publish: bool = False,
    automation: object | None = None,
    output_dir: str | Path = "",
    foreground_takeover_request: ForegroundTakeoverRequest | dict | None = None,
    moments_entry_relative: Iterable[float] | None = None,
    publish_relative: Iterable[float] | None = None,
    publish_submit_relative: Iterable[float] | None = None,
) -> WeChatMomentsPublishReport:
    started = time.perf_counter()
    content = str(body or "")
    audience = str(visibility or "").strip().casefold()
    body_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    empty = lambda status, **kwargs: WeChatMomentsPublishReport(
        status=status,
        body_sha256=body_sha256,
        visibility=audience,
        allow_publish=allow_publish,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        **kwargs,
    )

    if not allow_publish:
        return empty("blocked_requires_explicit_opt_in")
    if not content.strip():
        return empty("blocked_empty_body")
    if audience not in {"public", "partial", "private", "selected"}:
        return empty("blocked_visibility_invalid")
    points = {
        "moments_entry_relative": _point(moments_entry_relative),
        "publish_relative": _point(publish_relative),
        "publish_submit_relative": _point(publish_submit_relative),
    }
    if any(point is None for point in points.values()):
        return empty("blocked_moments_coordinates_required")

    validation = validate_foreground_takeover_request(
        foreground_takeover_request,
        action="publish_moments",
        target_process_names=("weixin.exe", "wechat.exe"),
        selected_transport="foreground-keyboard-clipboard",
    )
    takeover_fields = _takeover_fields(validation)
    if not validation.valid:
        return empty(
            "blocked_foreground_takeover_request_required"
            if validation.decision == "missing_foreground_takeover_request"
            else "blocked_foreground_takeover_request_invalid",
            error=validation.decision,
            **takeover_fields,
        )

    active = automation or Win32WeChatKeyboardAutomation()
    root = Path(
        output_dir or Path("logs") / "runtime" / "wechat-moments-publish"
    ).resolve()
    pre_path = root / "pre_publish.png"
    panel_path = root / "publish_panel.png"
    post_path = root / "post_publish.png"
    artifact_path = root / "report.json"
    phases: list[dict] = []
    keyboard_inputs = 0
    mouse_inputs = 0
    clipboard_writes = 0
    clipboard_restores = 0
    foreground_restores = 0
    publish_attempts = 0
    restore_fields: dict = {}
    previous_hwnd = 0
    try:
        window_hwnd = int(active.find_wechat_window())
        previous_hwnd = int(active.get_foreground_window())
        if not active.set_foreground_window(window_hwnd):
            raise RuntimeError("wechat_foreground_activation_failed")
        active.click_relative(*points["moments_entry_relative"])
        mouse_inputs += 1
        active.sleep(1.0)
        pre = str(active.screenshot(pre_path))
        moments_verified = bool(active.verify_moments_surface(pre))
        phases.append({"phase": "open_moments", "status": "ok" if moments_verified else "blocked"})
        if not moments_verified:
            restore_fields = _restore(active, previous_hwnd)
            foreground_restores += int(previous_hwnd > 0)
            return _persist_moments(
                artifact_path,
                started,
                empty(
                    "blocked_moments_surface_not_verified",
                    target_verified=False,
                    moments_surface_verified=False,
                    pre_publish_screenshot_path=pre,
                    phases=tuple(phases),
                    foreground_restore_attempts=foreground_restores,
                    **restore_fields,
                    **takeover_fields,
                ),
            )
        active.click_relative(*points["publish_relative"])
        mouse_inputs += 1
        active.sleep(0.5)
        panel = str(active.screenshot(panel_path))
        panel_verified = bool(active.verify_publish_panel(panel))
        phases.append({"phase": "open_publish_panel", "status": "ok" if panel_verified else "blocked"})
        if not panel_verified:
            restore_fields = _restore(active, previous_hwnd)
            foreground_restores += int(previous_hwnd > 0)
            return _persist_moments(
                artifact_path,
                started,
                empty(
                    "blocked_publish_panel_not_verified",
                    target_verified=True,
                    moments_surface_verified=True,
                    publish_panel_verified=False,
                    pre_publish_screenshot_path=pre,
                    publish_panel_screenshot_path=panel,
                    phases=tuple(phases),
                    foreground_restore_attempts=foreground_restores,
                    **restore_fields,
                    **takeover_fields,
                ),
            )
        active.paste_text(content)
        keyboard_inputs += 1
        set_visibility = getattr(active, "set_visibility", None)
        if callable(set_visibility) and not bool(set_visibility(audience)):
            raise RuntimeError("wechat_moments_visibility_set_failed")
        if audience != "public" and not callable(set_visibility):
            raise RuntimeError("wechat_moments_visibility_selector_missing")
        active.click_relative(*points["publish_submit_relative"])
        mouse_inputs += 1
        publish_attempts = 1
        active.sleep(1.0)
        post = _capture(active, window_hwnd, post_path)
        verification = _verify_body(active, content, pre, post)
        verified = bool(verification.get("verified"))
        phases.append({"phase": "publish", "status": "ok", "publish_attempts": 1})
        phases.append({"phase": "post_publish_verify", "status": "ok" if verified else "unverified", "verified": verified})
        active.restore_clipboard()
        clipboard_restores += 1
        restore_fields = _restore(active, previous_hwnd)
        foreground_restores += int(previous_hwnd > 0)
        phases.append({"phase": "restore_state", "status": "ok"})
        return _persist_moments(
            artifact_path,
            started,
            empty(
                "sent" if verified else "unverified",
                control_allowed=True,
                publish_attempts=publish_attempts,
                keyboard_input_attempts=keyboard_inputs,
                mouse_input_attempts=mouse_inputs,
                clipboard_write_attempts=clipboard_writes + 1,
                clipboard_restore_attempts=clipboard_restores,
                foreground_restore_attempts=foreground_restores,
                target_verified=True,
                moments_surface_verified=True,
                publish_panel_verified=True,
                post_publish_verified=verified,
                post_publish_verification=verification,
                pre_publish_screenshot_path=pre,
                publish_panel_screenshot_path=panel,
                post_publish_screenshot_path=post,
                phases=tuple(phases),
                **restore_fields,
                **takeover_fields,
            ),
        )
    except Exception as exc:
        try:
            active.restore_clipboard()
            clipboard_restores += 1
        except Exception:
            pass
        if previous_hwnd:
            try:
                restore_fields = _restore(active, previous_hwnd)
                foreground_restores += 1
            except Exception:
                pass
        phases.append({"phase": "failed", "status": "failed", "error": str(exc)})
        return _persist_moments(
            artifact_path,
            started,
            empty(
                "failed",
                control_allowed=bool(publish_attempts),
                publish_attempts=publish_attempts,
                keyboard_input_attempts=keyboard_inputs,
                mouse_input_attempts=mouse_inputs,
                clipboard_write_attempts=clipboard_writes,
                clipboard_restore_attempts=clipboard_restores,
                foreground_restore_attempts=foreground_restores,
                phases=tuple(phases),
                error=str(exc),
                **restore_fields,
                **takeover_fields,
            ),
        )


def _point(value: Iterable[float] | None) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        point = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if len(point) != 2 or any(item < 0 or item > 1 for item in point):
        return None
    return point


def _takeover_fields(validation) -> dict:
    data = validation.to_dict()
    return {
        "foreground_takeover_validated": bool(validation.valid),
        "foreground_takeover_validation": data,
        "foreground_takeover_request": dict(data.get("request") or {}),
    }


def _restore(active: object, hwnd: int) -> dict:
    if int(hwnd or 0) <= 0:
        return {"foreground_restored": None, "final_foreground_hwnd": 0}
    active.set_foreground_window(int(hwnd))
    final = int(active.get_foreground_window() or 0)
    return {"foreground_restored": final == int(hwnd), "final_foreground_hwnd": final}


def _capture(active: object, hwnd: int, path: Path) -> str:
    capture = getattr(active, "capture_bound_window", None)
    if not callable(capture):
        return ""
    try:
        return str(capture(int(hwnd), path) or "")
    except Exception:
        return ""


def _verify_body(active: object, body: str, before_path: str, after_path: str) -> dict:
    verifier = getattr(active, "verify_published_body", None)
    if callable(verifier):
        try:
            result = verifier(body, before_path, after_path)
        except TypeError:
            result = verifier(body, after_path)
        return dict(result) if isinstance(result, dict) else {"verified": bool(result)}
    return {"verified": False, "error": "moments_post_publish_verifier_missing"}


def _persist_moments(path: Path, started: float, report: WeChatMomentsPublishReport) -> WeChatMomentsPublishReport:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = dataclasses.replace(
        report,
        artifact_path=str(path),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


__all__ = ["WeChatMomentsPublishReport", "run_wechat_moments_text_publish_probe"]
