# -*- coding: utf-8 -*-
"""Bind discovered WeChat native bridge endpoints into ControlFabric targets."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from openwukong.connectors.base import ConnectorTarget
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex
from openwukong.control.wechat_native_bridge import (
    WeChatNativeBridgeClient,
    build_wechat_native_bridge_request,
)
from openwukong.control.wechat_native_bridge_registry import (
    discover_wechat_native_bridge_urls,
)


@dataclasses.dataclass(frozen=True)
class WeChatNativeFabricBinding:
    bridge_url: str
    target: ConnectorTarget
    ownership: SessionOwnership

    def to_dict(self) -> dict:
        return {
            "bridge_url": self.bridge_url,
            "target": {
                "process_name": self.target.process_name,
                "window_title": self.target.window_title,
                "conversation_name": self.target.conversation_name,
                "wechat_native_bridge_url": self.target.wechat_native_bridge_url,
                "background_screenshot_focus_stable": self.target.background_screenshot_focus_stable,
                "background_screenshot_count": self.target.background_screenshot_count,
                "background_screenshot_success_count": self.target.background_screenshot_success_count,
            },
            "ownership": self.ownership.to_dict(),
        }


def wechat_native_fabric_bindings_from_registry(
    explicit_urls=(),
    *,
    registry_paths=(),
    target_name: str,
    background_screenshot_focus_stable: bool = True,
    background_screenshot_count: int = 0,
    background_screenshot_success_count: int = 0,
    process_name: str = "Weixin.exe",
    window_title: str = "",
    manifest_path: str | Path = "",
    environment: dict | None = None,
    probe_capabilities: bool = True,
    capability_client: object | None = None,
    capability_request_timeout: float = 1.0,
) -> tuple[WeChatNativeFabricBinding, ...]:
    urls = discover_wechat_native_bridge_urls(
        explicit_urls,
        registry_paths=registry_paths,
        environment=environment,
    )
    bindings: list[WeChatNativeFabricBinding] = []
    for url in urls:
        bridge_url = str(url or "").strip().rstrip("/")
        if not bridge_url:
            continue
        conversation_name = str(target_name or "").strip()
        capability_report = _read_capabilities(
            bridge_url,
            conversation_name,
            client=capability_client,
            request_timeout=capability_request_timeout,
        ) if probe_capabilities else {}
        capability_targets = _capability_target_candidates(capability_report)
        capability_target = _matching_capability_target(capability_report, conversation_name)
        capability_target_verified = bool(capability_target) or not capability_targets
        target_evidence = capability_target if capability_target_verified else {}
        report_evidence = capability_report if capability_target_verified else {}
        conversation_name = (
            _first_text(
                target_evidence,
                "conversation_name",
                "name",
                "display_name",
                "target_name",
                "title",
            )
            or conversation_name
        )
        title = (
            str(window_title or "").strip()
            or _first_text(target_evidence, "window_title", "title")
            or _first_text(report_evidence, "window_title", "title")
        )
        if not title and conversation_name:
            title = f"{conversation_name} - WeChat"
        process = (
            _first_text(target_evidence, "process_name", "process")
            or _first_text(capability_report, "process_name", "process")
            or _nested_text(capability_report, "app_binding", "process_name")
            or str(process_name or "Weixin.exe").strip()
        )
        pid = _first_int(
            0,
            (target_evidence, ("pid", "process_id")),
            (capability_report, ("pid", "process_id")),
            (_nested_dict(capability_report, "app_binding"), ("pid", "process_id")),
        )
        target = ConnectorTarget(
            pid=pid,
            process_name=process,
            window_title=title,
            session_id=_first_text(
                target_evidence,
                "conversation_id",
                "id",
                "target_id",
                "session_id",
            ),
            conversation_name=conversation_name,
            wechat_native_bridge_url=bridge_url,
            background_screenshot_focus_stable=_first_bool(
                background_screenshot_focus_stable,
                (target_evidence, ("background_screenshot_focus_stable",)),
                (report_evidence, ("background_screenshot_focus_stable",)),
            ),
            background_screenshot_count=_first_int(
                background_screenshot_count,
                (target_evidence, ("background_screenshot_count",)),
                (report_evidence, ("background_screenshot_count",)),
            ),
            background_screenshot_success_count=_first_int(
                background_screenshot_success_count,
                (target_evidence, ("background_screenshot_success_count",)),
                (report_evidence, ("background_screenshot_success_count",)),
            ),
        )
        ownership = SessionOwnership(
            owned=True,
            ownership_source="wechat_native_bridge_registry",
            manifest_path=str(manifest_path or ""),
            route_id="app-native-bridge-required",
            connector_id="wechat-native-bridge",
            action_id="bind_wechat_native_bridge",
            pid=target.pid,
            endpoint=bridge_url,
            cleanup_ready=False,
        )
        bindings.append(
            WeChatNativeFabricBinding(
                bridge_url=bridge_url,
                target=target,
                ownership=ownership,
            )
        )
    return tuple(bindings)


def ownership_index_from_wechat_native_bridge_registry(
    explicit_urls=(),
    *,
    registry_paths=(),
    target_name: str,
    background_screenshot_focus_stable: bool = True,
    background_screenshot_count: int = 0,
    background_screenshot_success_count: int = 0,
    process_name: str = "Weixin.exe",
    window_title: str = "",
    manifest_path: str | Path = "",
    environment: dict | None = None,
    probe_capabilities: bool = True,
    capability_client: object | None = None,
    capability_request_timeout: float = 1.0,
) -> SessionOwnershipIndex:
    bindings = wechat_native_fabric_bindings_from_registry(
        explicit_urls,
        registry_paths=registry_paths,
        target_name=target_name,
        background_screenshot_focus_stable=background_screenshot_focus_stable,
        background_screenshot_count=background_screenshot_count,
        background_screenshot_success_count=background_screenshot_success_count,
        process_name=process_name,
        window_title=window_title,
        manifest_path=manifest_path,
        environment=environment,
        probe_capabilities=probe_capabilities,
        capability_client=capability_client,
        capability_request_timeout=capability_request_timeout,
    )
    return SessionOwnershipIndex(tuple(binding.ownership for binding in bindings))


def _read_capabilities(
    bridge_url: str,
    target_name: str,
    *,
    client: object | None,
    request_timeout: float,
) -> dict:
    if not bridge_url:
        return {}
    capability_client = client or WeChatNativeBridgeClient(
        request_timeout=_capability_request_timeout(request_timeout)
    )
    request = build_wechat_native_bridge_request(
        bridge_url=bridge_url,
        target_name=target_name,
        message="capability_probe",
    )
    try:
        read = getattr(capability_client, "read_capabilities")
        data = read(request)
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _capability_request_timeout(value: float) -> float:
    try:
        return max(0.1, float(value))
    except (TypeError, ValueError):
        return 1.0


def _matching_capability_target(capability_report: dict, target_name: str) -> dict:
    normalized_target = _normalize(target_name)
    candidates = _capability_target_candidates(capability_report)
    if not normalized_target:
        return candidates[0] if candidates else {}
    for target in candidates:
        if target.get("available", True) is False:
            continue
        haystack = " ".join(
            str(target.get(key, "") or "")
            for key in (
                "name",
                "display_name",
                "target_name",
                "conversation_name",
                "title",
                "window_title",
                "alias",
                "id",
                "conversation_id",
                "session_id",
            )
        )
        normalized_haystack = _normalize(haystack)
        if (
            normalized_target
            and normalized_haystack
            and (
                normalized_target in normalized_haystack
                or normalized_haystack in normalized_target
            )
        ):
            return target
    return {}


def _capability_target_candidates(capability_report: dict) -> tuple[dict, ...]:
    if not isinstance(capability_report, dict):
        return ()
    candidates: list[dict] = []
    for key in ("targets", "conversations", "sessions"):
        value = capability_report.get(key)
        if isinstance(value, list):
            candidates.extend(dict(item) for item in value if isinstance(item, dict))
    target = capability_report.get("target")
    if isinstance(target, dict):
        candidates.append(dict(target))
    return tuple(candidates)


def _first_text(source: dict, *keys: str) -> str:
    if not isinstance(source, dict):
        return ""
    for key in keys:
        value = source.get(key)
        if value:
            return str(value).strip()
    return ""


def _nested_dict(source: dict, key: str) -> dict:
    if not isinstance(source, dict):
        return {}
    value = source.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _nested_text(source: dict, outer_key: str, inner_key: str) -> str:
    return _first_text(_nested_dict(source, outer_key), inner_key)


def _first_bool(default: bool, *sources_and_keys: tuple[dict, tuple[str, ...]]) -> bool:
    for source, keys in sources_and_keys:
        if not isinstance(source, dict):
            continue
        for key in keys:
            if key in source:
                return bool(source.get(key, False))
    return bool(default)


def _first_int(
    default: int,
    *sources_and_keys: tuple[dict, tuple[str, ...]],
) -> int:
    for source, keys in sources_and_keys:
        if not isinstance(source, dict):
            continue
        for key in keys:
            if key not in source:
                continue
            try:
                return max(0, int(source.get(key, 0) or 0))
            except (TypeError, ValueError):
                return 0
    try:
        return max(0, int(default or 0))
    except (TypeError, ValueError):
        return 0


def _normalize(value: object) -> str:
    return str(value or "").strip().casefold()


__all__ = [
    "WeChatNativeFabricBinding",
    "ownership_index_from_wechat_native_bridge_registry",
    "wechat_native_fabric_bindings_from_registry",
]
