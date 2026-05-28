# -*- coding: utf-8 -*-
"""Unified desktop task runner for launch, browser search, and WeChat send.

This is the first user-facing orchestration layer above the lower-level
ControlFabric and app-specific probes. It keeps external communication and
foreground takeover behind explicit gates while allowing deterministic browser
and application launch paths to share one report contract.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from openwukong.connectors import ConnectorTarget
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    AppResolutionReport,
    StartMenuAppCandidateProvider,
    StaticAppCandidateProvider,
    WindowsAppResolver,
    default_start_menu_roots,
    normalize_app_name,
)
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.evaluation.wechat_send_probe import run_wechat_file_helper_send_probe


_BING_SEARCH_BASE = "https://www.bing.com/search?q="
_WECHAT_PROCESS_NAME = "Weixin.exe"
_WECHAT_WINDOW_TITLE = "微信"


@dataclasses.dataclass(frozen=True)
class DesktopTaskReport:
    task_type: str
    status: str
    app_name: str = ""
    target_name: str = ""
    message: str = ""
    query: str = ""
    control_allowed: bool = False
    launch_attempts: int = 0
    browser_navigation_attempts: int = 0
    send_attempts: int = 0
    selected_transport: str = ""
    browser_search_url: str = ""
    app_launch: dict = dataclasses.field(default_factory=dict)
    browser_action: dict = dataclasses.field(default_factory=dict)
    foreground_takeover_request: dict = dataclasses.field(default_factory=dict)
    wechat_send: dict = dataclasses.field(default_factory=dict)
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "desktop-task-runner"

    @property
    def safety_mode(self) -> str:
        return "explicit_task_gate"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "task_type": self.task_type,
            "status": self.status,
            "app_name": self.app_name,
            "target_name": self.target_name,
            "message": self.message,
            "query": self.query,
            "control_allowed": self.control_allowed,
            "launch_attempts": self.launch_attempts,
            "browser_navigation_attempts": self.browser_navigation_attempts,
            "send_attempts": self.send_attempts,
            "selected_transport": self.selected_transport,
            "browser_search_url": self.browser_search_url,
            "app_launch": dict(self.app_launch),
            "browser_action": dict(self.browser_action),
            "foreground_takeover_request": dict(self.foreground_takeover_request),
            "wechat_send": dict(self.wechat_send),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class FakeAppLauncher:
    """Deterministic test launcher with the same interface as WindowsAppLauncher."""

    def __init__(self, apps: dict[str, str]):
        self.apps = dict(apps)
        self.launches: list[str] = []

    def resolve(self, app_name: str) -> dict:
        key = normalize_app_name(app_name)
        path = self.apps.get(key) or self.apps.get(app_name)
        if not path:
            return {"ok": False, "error": "app_not_found", "app_name": app_name}
        return {"ok": True, "app_name": app_name, "path": path, "source": "fake"}

    def launch(self, resolved_app: dict) -> dict:
        path = str(resolved_app.get("path", "") or "")
        self.launches.append(path)
        return {"ok": True, "path": path, "pid": 4242, "source": resolved_app.get("source", "")}


class FakeBrowserOpener:
    def __init__(self, *, ok: bool = True):
        self.ok = ok
        self.opened_urls: list[str] = []

    def open(self, url: str) -> bool:
        self.opened_urls.append(url)
        return self.ok


class WindowsAppLauncher:
    """Resolve apps through Start Menu entries and launch without shell strings."""

    def __init__(
        self,
        *,
        start_menu_roots: tuple[str | Path, ...] = (),
        resolver: WindowsAppResolver | None = None,
        cache_path: str | Path = "",
    ):
        self.start_menu_roots = tuple(Path(root) for root in start_menu_roots) or default_start_menu_roots()
        self.resolver = resolver or WindowsAppResolver(
            start_menu_roots=self.start_menu_roots,
            cache_path=cache_path,
            candidate_providers=(
                (StartMenuAppCandidateProvider(self.start_menu_roots),)
                if start_menu_roots
                else None
            ),
        )

    def resolve(self, app_name: str) -> dict:
        name = str(app_name or "").strip()
        if not name:
            return {"ok": False, "error": "empty_app_name", "app_name": name}
        return self.resolver.resolve(name).to_dict()

    def launch(self, resolved_app: dict) -> dict:
        if bool(resolved_app.get("already_running")):
            return {
                "ok": True,
                "path": str(resolved_app.get("path", "") or ""),
                "pid": int(resolved_app.get("pid", 0) or 0),
                "source": str(resolved_app.get("source", "") or ""),
                "already_running": True,
                "resolution": dict(resolved_app),
            }
        path = str(resolved_app.get("path", "") or "").strip()
        if not path:
            return {"ok": False, "error": "empty_launch_path"}
        suffix = Path(path).suffix.lower()
        try:
            if os.name == "nt" and suffix in {".lnk", ".url"}:
                os.startfile(os.path.normpath(path))
                return {
                    "ok": True,
                    "path": path,
                    "pid": 0,
                    "source": resolved_app.get("source", ""),
                    "resolution": dict(resolved_app),
                }
            process = subprocess.Popen(
                [path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            return {"ok": False, "path": path, "error": str(exc)}
        return {
            "ok": True,
            "path": path,
            "pid": int(process.pid),
            "source": resolved_app.get("source", ""),
            "resolution": dict(resolved_app),
        }


class SystemBrowserOpener:
    def open(self, url: str) -> bool:
        return bool(webbrowser.open(url, new=2, autoraise=True))


def run_desktop_task(
    *,
    task_type: str,
    app_name: str = "",
    target_name: str = "",
    message: str = "",
    query: str = "",
    allow_launch: bool = False,
    allow_send: bool = False,
    allow_external_communication: bool = False,
    approve_foreground_takeover: bool = False,
    confirm_target_after_open: bool = False,
    browser_debugger_url: str = "",
    app_launcher: object | None = None,
    browser_opener: object | None = None,
    browser_action_runner: object | None = None,
    wechat_automation: object | None = None,
    output_dir: str | Path = "",
) -> DesktopTaskReport:
    started = time.perf_counter()
    kind = str(task_type or "").strip().lower().replace("-", "_")
    if kind == "open_app":
        return _run_open_app(
            started,
            app_name=app_name,
            allow_launch=allow_launch,
            app_launcher=app_launcher,
        )
    if kind == "browser_search":
        return _run_browser_search(
            started,
            query=query,
            allow_launch=allow_launch,
            browser_debugger_url=browser_debugger_url,
            browser_opener=browser_opener,
            browser_action_runner=browser_action_runner,
        )
    if kind == "wechat_send":
        return _run_wechat_send(
            started,
            target_name=target_name,
            message=message,
            allow_send=allow_send,
            allow_launch=allow_launch,
            allow_external_communication=allow_external_communication,
            approve_foreground_takeover=approve_foreground_takeover,
            confirm_target_after_open=confirm_target_after_open,
            app_launcher=app_launcher,
            wechat_automation=wechat_automation,
            output_dir=output_dir,
        )
    return _report(started, task_type=kind, status="blocked_unknown_task_type", error="unknown_task_type")


def _run_open_app(
    started: float,
    *,
    app_name: str,
    allow_launch: bool,
    app_launcher: object | None,
) -> DesktopTaskReport:
    name = str(app_name or "").strip()
    if not allow_launch:
        return _report(
            started,
            task_type="open_app",
            status="blocked_launch_requires_explicit_permission",
            app_name=name,
        )
    launcher = app_launcher or WindowsAppLauncher()
    resolved = launcher.resolve(name)
    if not resolved.get("ok"):
        return _report(
            started,
            task_type="open_app",
            status="blocked_app_not_found",
            app_name=name,
            app_launch=resolved,
            error=str(resolved.get("error", "") or "app_not_found"),
        )
    launched = launcher.launch(resolved)
    already_running = bool(launched.get("already_running"))
    return _report(
        started,
        task_type="open_app",
        status=(
            "app_already_running"
            if launched.get("ok") and already_running
            else "app_launched" if launched.get("ok") else "failed_app_launch"
        ),
        app_name=name,
        control_allowed=bool(launched.get("ok") and not already_running),
        launch_attempts=0 if already_running else 1,
        app_launch=launched,
        error="" if launched.get("ok") else str(launched.get("error", "") or "app_launch_failed"),
    )


def _run_browser_search(
    started: float,
    *,
    query: str,
    allow_launch: bool,
    browser_debugger_url: str,
    browser_opener: object | None,
    browser_action_runner: object | None,
) -> DesktopTaskReport:
    text = str(query or "").strip()
    if not text:
        return _report(started, task_type="browser_search", status="blocked_empty_query")
    url = _search_url(text)
    debugger = str(browser_debugger_url or "").strip()
    if debugger:
        execution = ControlFabric.with_default_connectors().execute(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Browser",
                resource_url="about:blank",
                debugger_url=debugger,
            ),
            ControlIntent(action="navigate_url", url=url),
            allow_control=True,
            browser_action_runner=browser_action_runner,
        )
        data = execution.to_dict()
        transport = data.get("dispatch_report", {}).get("selected_transport") or data.get("selected_transport", "")
        return _report(
            started,
            task_type="browser_search",
            status="browser_search_opened" if execution.ok else "blocked_browser_devtools_action_failed",
            query=text,
            control_allowed=bool(execution.control_allowed),
            browser_navigation_attempts=int(data.get("control_attempts", 0) or 0),
            selected_transport=str(transport or "chrome-devtools-protocol"),
            browser_search_url=url,
            browser_action=data,
            error="" if execution.ok else str(data.get("error", "") or "browser_devtools_action_failed"),
        )
    if not allow_launch:
        return _report(
            started,
            task_type="browser_search",
            status="blocked_browser_requires_debugger_or_launch_permission",
            query=text,
            browser_search_url=url,
        )
    opener = browser_opener or SystemBrowserOpener()
    ok = bool(opener.open(url))
    return _report(
        started,
        task_type="browser_search",
        status="browser_search_opened" if ok else "failed_browser_open",
        query=text,
        control_allowed=ok,
        browser_navigation_attempts=1 if ok else 0,
        selected_transport="system-browser-url-open",
        browser_search_url=url,
        error="" if ok else "browser_open_failed",
    )


def _run_wechat_send(
    started: float,
    *,
    target_name: str,
    message: str,
    allow_send: bool,
    allow_launch: bool,
    allow_external_communication: bool,
    approve_foreground_takeover: bool,
    confirm_target_after_open: bool,
    app_launcher: object | None,
    wechat_automation: object | None,
    output_dir: str | Path,
) -> DesktopTaskReport:
    target = str(target_name or "").strip()
    text = str(message or "").strip()
    launch_data: dict = {}
    launch_attempts = 0
    if allow_launch:
        launch_report = _run_open_app(
            started,
            app_name="wechat",
            allow_launch=True,
            app_launcher=app_launcher,
        )
        launch_data = launch_report.app_launch
        launch_attempts = launch_report.launch_attempts
        if launch_report.status != "app_launched":
            return _report(
                started,
                task_type="wechat_send",
                status="blocked_wechat_launch_failed",
                target_name=target,
                message=text,
                launch_attempts=launch_attempts,
                app_launch=launch_data,
                error=launch_report.error,
            )
    takeover = ControlFabric().execute(
        ConnectorTarget(process_name=_WECHAT_PROCESS_NAME, window_title=_WECHAT_WINDOW_TITLE),
        ControlIntent(action="send_message", text=text),
        allow_control=True,
    ).to_dict().get("foreground_takeover_request", {})
    if not allow_send:
        return _report(
            started,
            task_type="wechat_send",
            status="blocked_requires_explicit_send_permission",
            target_name=target,
            message=text,
            launch_attempts=launch_attempts,
            app_launch=launch_data,
            foreground_takeover_request=takeover,
        )
    if target != "文件传输助手" and not allow_external_communication:
        return _report(
            started,
            task_type="wechat_send",
            status="blocked_external_target_requires_explicit_permission",
            target_name=target,
            message=text,
            launch_attempts=launch_attempts,
            app_launch=launch_data,
            foreground_takeover_request=takeover,
        )
    if not approve_foreground_takeover:
        return _report(
            started,
            task_type="wechat_send",
            status="foreground_takeover_request_pending",
            target_name=target,
            message=text,
            launch_attempts=launch_attempts,
            app_launch=launch_data,
            foreground_takeover_request=takeover,
        )
    send_report = run_wechat_file_helper_send_probe(
        target_name=target,
        message=text,
        allow_send=True,
        allow_external_target=allow_external_communication,
        confirm_target_after_open=confirm_target_after_open,
        automation=wechat_automation,
        output_dir=output_dir,
        foreground_takeover_request=takeover,
    )
    data = send_report.to_dict()
    return _report(
        started,
        task_type="wechat_send",
        status=str(data.get("status", "") or "failed_wechat_send"),
        target_name=target,
        message=text,
        control_allowed=bool(data.get("control_allowed")),
        launch_attempts=launch_attempts,
        send_attempts=int(data.get("send_attempts", 0) or 0),
        selected_transport=str(data.get("transport", "") or ""),
        app_launch=launch_data,
        foreground_takeover_request=takeover,
        wechat_send=data,
        error=str(data.get("error", "") or ""),
    )


def _search_url(query: str) -> str:
    return _BING_SEARCH_BASE + quote_plus(str(query or "").strip())


def _report(started: float, **kwargs) -> DesktopTaskReport:
    return DesktopTaskReport(elapsed_ms=(time.perf_counter() - started) * 1000, **kwargs)


def desktop_task_exit_code(status: str) -> int:
    return 0 if status in {"app_launched", "app_already_running", "browser_search_opened", "sent"} else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a gated desktop task.")
    parser.add_argument("--task-type", required=True, choices=("open_app", "browser_search", "wechat_send"))
    parser.add_argument("--app-name", default="")
    parser.add_argument("--target-name", default="")
    parser.add_argument("--message", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--allow-launch", action="store_true")
    parser.add_argument("--allow-send", action="store_true")
    parser.add_argument("--allow-external-communication", action="store_true")
    parser.add_argument("--approve-foreground-takeover", action="store_true")
    parser.add_argument("--confirm-target-after-open", action="store_true")
    parser.add_argument("--browser-debugger-url", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_desktop_task(
        task_type=args.task_type,
        app_name=args.app_name,
        target_name=args.target_name,
        message=args.message,
        query=args.query,
        allow_launch=args.allow_launch,
        allow_send=args.allow_send,
        allow_external_communication=args.allow_external_communication,
        approve_foreground_takeover=args.approve_foreground_takeover,
        confirm_target_after_open=args.confirm_target_after_open,
        browser_debugger_url=args.browser_debugger_url,
        output_dir=args.output_dir,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            f"{data['task_type']} status={data['status']} "
            f"launch={data['launch_attempts']} "
            f"browser={data['browser_navigation_attempts']} "
            f"send={data['send_attempts']}"
        )
    return desktop_task_exit_code(report.status)


if __name__ == "__main__":
    raise SystemExit(main())
