# -*- coding: utf-8 -*-
"""Read-only WeChat basic-operation capability report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Iterable

from openwukong.connectors.wechat_desktop import WeChatSurfaceObserver
from openwukong.control.wechat_surface import WeChatTargetResolution, WeChatTargetResolver
from openwukong.evaluation.accessibility_probe import AccessibilityWindowSnapshot


WECHAT_BASIC_ACTIONS = (
    "wechat.window.inspect",
    "wechat.window.attach",
    "wechat.chat.search",
    "wechat.chat.open",
    "wechat.chat.read",
    "wechat.chat.draft",
    "wechat.chat.send_text",
    "wechat.chat.send_emoji",
    "wechat.media.send_image",
    "wechat.media.send_video",
    "wechat.media.send_voice",
    "wechat.file.send",
    "wechat.file.download",
    "wechat.moments.open",
    "wechat.moments.read",
    "wechat.moments.draft",
    "wechat.moments.publish",
    "wechat.monitor.poll",
    "wechat.settings.read",
    "wechat.settings.update",
)


def run_wechat_basic_operations_demo(
    *,
    windows: Iterable[AccessibilityWindowSnapshot] | None = None,
    target_name: str = "",
    target_type: str = "conversation",
    dry_run: bool = True,
    workspace_path: str = "",
) -> dict:
    """Build a no-control capability report for the current WeChat surface."""

    if not dry_run:
        raise ValueError("wechat_basic_operations_demo_requires_dry_run")
    observed_at = datetime.now(timezone.utc)
    snapshot = WeChatSurfaceObserver().inspect(
        windows=windows,
        observed_at=observed_at,
    )
    if target_name.strip():
        target = WeChatTargetResolver().resolve(
            snapshot,
            target_type=target_type,
            query=target_name,
        )
    else:
        target = WeChatTargetResolution(
            ok=False,
            decision="target_not_requested",
            candidates=snapshot.targets,
        )
    profile_time = snapshot.profile.observed_at
    capabilities = {
        action: snapshot.profile.supports(action, now=profile_time)
        for action in WECHAT_BASIC_ACTIONS
    }
    missing = [
        action for action, supported in capabilities.items() if not supported
    ]
    return {
        "mode": "wechat-basic-operations-demo",
        "safety_mode": "read_only_dry_run",
        "dry_run": True,
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
        "workspace_path": str(workspace_path or ""),
        "surface": snapshot.to_dict(),
        "target": target.to_dict(),
        "capabilities": capabilities,
        "missing_capabilities": missing,
        "planned_side_effects": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only WeChat basic-operations capability report."
    )
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--target-name", default="")
    parser.add_argument(
        "--target-type",
        default="conversation",
        choices=("conversation", "group", "official_account"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required. Observe and plan only; never send or mutate WeChat.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_wechat_basic_operations_demo(
            target_name=args.target_name,
            target_type=args.target_type,
            dry_run=args.dry_run,
            workspace_path=args.workspace_path,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "wechat basic dry-run "
            f"decision={report['surface']['decision']} "
            f"target={report['target']['decision']} "
            f"supported={sum(report['capabilities'].values())}/"
            f"{len(report['capabilities'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
