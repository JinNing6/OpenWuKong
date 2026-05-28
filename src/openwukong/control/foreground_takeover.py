# -*- coding: utf-8 -*-
"""Explicit request contract for foreground desktop takeover.

Foreground keyboard, mouse, and clipboard transports can affect the user's
active desktop session. This module keeps those transports behind a structured
request object that can be logged, reviewed, validated, and consumed by the
specific app probe before any foreground primitive runs.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Mapping


@dataclasses.dataclass(frozen=True)
class ForegroundTakeoverRequest:
    """Auditable request for a foreground-only control transport."""

    status: str = "approval_required"
    action: str = ""
    app_family: str = ""
    target_process_name: str = ""
    target_window_title: str = ""
    selected_route: str = ""
    selected_transport: str = ""
    transport_channel: str = ""
    risk_flags: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    request_reason: str = "foreground_takeover_confirmation_required"
    request_id: str = ""

    @property
    def mode(self) -> str:
        return "foreground-takeover-request"

    @property
    def safety_mode(self) -> str:
        return "explicit_foreground_takeover_request"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        request_id = self.request_id or _request_id(
            self.action,
            self.target_process_name,
            self.target_window_title,
            self.selected_transport,
        )
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "request_id": request_id,
            "status": self.status,
            "action": self.action,
            "app_family": self.app_family,
            "target_process_name": self.target_process_name,
            "target_window_title": self.target_window_title,
            "selected_route": self.selected_route,
            "selected_transport": self.selected_transport,
            "transport_channel": self.transport_channel,
            "risk_flags": list(self.risk_flags),
            "verification_requirements": list(self.verification_requirements),
            "request_reason": self.request_reason,
        }


@dataclasses.dataclass(frozen=True)
class ForegroundTakeoverValidationReport:
    """Validation result before a foreground takeover request is consumed."""

    valid: bool
    decision: str
    reason: str = ""
    request: ForegroundTakeoverRequest | None = None
    expected_action: str = ""
    expected_transport: str = ""
    expected_target_process_names: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        return "foreground-takeover-validation"

    @property
    def safety_mode(self) -> str:
        return "validation_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "valid": self.valid,
            "decision": self.decision,
            "reason": self.reason,
            "expected_action": self.expected_action,
            "expected_transport": self.expected_transport,
            "expected_target_process_names": list(self.expected_target_process_names),
            "request": self.request.to_dict() if self.request else {},
        }


def build_foreground_takeover_request(report: object) -> ForegroundTakeoverRequest:
    """Build a foreground takeover request from a dispatch or execution report."""

    dispatch = getattr(report, "dispatch_report", report)
    target = getattr(dispatch, "target", None)
    intent = getattr(dispatch, "intent", None)
    route_plan = getattr(dispatch, "route_plan", None)
    transport = getattr(dispatch, "transport_capability", None)
    return ForegroundTakeoverRequest(
        status="approval_required",
        action=str(getattr(intent, "action", "") or ""),
        app_family=str(getattr(route_plan, "app_family", "") or getattr(transport, "app_family", "") or ""),
        target_process_name=str(getattr(target, "process_name", "") or ""),
        target_window_title=str(getattr(target, "window_title", "") or ""),
        selected_route=str(getattr(dispatch, "selected_route", "") or getattr(transport, "selected_route", "") or ""),
        selected_transport=str(getattr(transport, "selected_transport", "") or ""),
        transport_channel=str(getattr(transport, "transport_channel", "") or ""),
        risk_flags=_tuple_attr(transport, "risk_flags"),
        verification_requirements=_tuple_attr(transport, "verification_requirements"),
    )


def validate_foreground_takeover_request(
    request: ForegroundTakeoverRequest | Mapping[str, object] | None,
    *,
    action: str,
    target_process_names: tuple[str, ...] = (),
    selected_transport: str = "",
) -> ForegroundTakeoverValidationReport:
    """Validate that a foreground takeover request matches the pending action."""

    parsed = _parse_request(request)
    expected_action = _norm(action)
    expected_transport = _norm(selected_transport)
    expected_names = tuple(_norm(item) for item in target_process_names if _norm(item))

    if parsed is None:
        return _validation(
            False,
            "missing_foreground_takeover_request",
            "foreground takeover request is required",
            None,
            expected_action,
            expected_transport,
            expected_names,
        )
    if _norm(parsed.action) != expected_action:
        return _validation(
            False,
            "foreground_takeover_action_mismatch",
            "request action does not match pending action",
            parsed,
            expected_action,
            expected_transport,
            expected_names,
        )
    if expected_transport and _norm(parsed.selected_transport) != expected_transport:
        return _validation(
            False,
            "foreground_takeover_transport_mismatch",
            "request transport does not match pending transport",
            parsed,
            expected_action,
            expected_transport,
            expected_names,
        )
    if expected_names and _norm(parsed.target_process_name) not in expected_names:
        return _validation(
            False,
            "foreground_takeover_target_mismatch",
            "request target process does not match pending target",
            parsed,
            expected_action,
            expected_transport,
            expected_names,
        )
    if _norm(parsed.status) not in {"approval_required", "approved"}:
        return _validation(
            False,
            "foreground_takeover_status_invalid",
            "request status must be approval_required or approved",
            parsed,
            expected_action,
            expected_transport,
            expected_names,
        )
    return _validation(
        True,
        "allow_foreground_takeover",
        "",
        parsed,
        expected_action,
        expected_transport,
        expected_names,
    )


def _validation(
    valid: bool,
    decision: str,
    reason: str,
    request: ForegroundTakeoverRequest | None,
    expected_action: str,
    expected_transport: str,
    expected_names: tuple[str, ...],
) -> ForegroundTakeoverValidationReport:
    return ForegroundTakeoverValidationReport(
        valid=valid,
        decision=decision,
        reason=reason,
        request=request,
        expected_action=expected_action,
        expected_transport=expected_transport,
        expected_target_process_names=expected_names,
    )


def _parse_request(
    request: ForegroundTakeoverRequest | Mapping[str, object] | None,
) -> ForegroundTakeoverRequest | None:
    if isinstance(request, ForegroundTakeoverRequest):
        return request
    if not isinstance(request, Mapping):
        return None
    payload = dict(request)
    if payload.get("mode") and payload.get("mode") != "foreground-takeover-request":
        return None
    return ForegroundTakeoverRequest(
        status=str(payload.get("status", "") or ""),
        action=str(payload.get("action", "") or ""),
        app_family=str(payload.get("app_family", "") or ""),
        target_process_name=str(payload.get("target_process_name", "") or ""),
        target_window_title=str(payload.get("target_window_title", "") or ""),
        selected_route=str(payload.get("selected_route", "") or ""),
        selected_transport=str(payload.get("selected_transport", "") or ""),
        transport_channel=str(payload.get("transport_channel", "") or ""),
        risk_flags=_tuple_payload(payload.get("risk_flags")),
        verification_requirements=_tuple_payload(payload.get("verification_requirements")),
        request_reason=str(payload.get("request_reason", "") or ""),
        request_id=str(payload.get("request_id", "") or ""),
    )


def _tuple_attr(obj: object, name: str) -> tuple[str, ...]:
    value = getattr(obj, name, ()) if obj is not None else ()
    return _tuple_payload(value)


def _tuple_payload(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    try:
        return tuple(str(item) for item in value if str(item or "").strip())
    except TypeError:
        text = str(value or "").strip()
        return (text,) if text else ()


def _request_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"fgt-{digest[:16]}"


def _norm(value: object) -> str:
    return str(value or "").strip().lower()
