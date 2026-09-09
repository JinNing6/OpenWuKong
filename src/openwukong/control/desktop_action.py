# -*- coding: utf-8 -*-
"""Versioned, application-independent desktop action contracts."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


DESKTOP_ACTION_SCHEMA_VERSION = "openwukong-desktop-action-v1"

_CONFIRMATION_EFFECTS = frozenset(
    {
        "external_communication",
        "local_write",
        "delete",
        "high_risk",
    }
)
_SENSITIVE_KEY = re.compile(
    r"(?:password|passphrase|secret|token|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization|private[_-]?key|credential)",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class DesktopTarget:
    """Identity of the process/window/session/resource an action addresses."""

    surface_id: str = ""
    process_name: str = ""
    window_title: str = ""
    pid: int = 0
    hwnd: int = 0
    session_id: str = ""
    workspace_id: str = ""
    target_type: str = ""
    conversation_name: str = ""
    conversation_id: str = ""
    resource_id: str = ""

    def __post_init__(self) -> None:
        for field in (
            "surface_id",
            "process_name",
            "window_title",
            "session_id",
            "workspace_id",
            "target_type",
            "conversation_name",
            "conversation_id",
            "resource_id",
        ):
            value = str(getattr(self, field) or "").strip()
            object.__setattr__(self, field, value)
        for field in ("pid", "hwnd"):
            value = int(getattr(self, field) or 0)
            if value < 0:
                raise ValueError(f"{field} must be non-negative")
            object.__setattr__(self, field, value)

    @property
    def identity_key(self) -> str:
        """Return a stable, non-secret target identity string."""

        values = (
            self.surface_id,
            self.process_name.casefold(),
            self.window_title,
            str(self.pid),
            str(self.hwnd),
            self.session_id,
            self.workspace_id,
            self.target_type,
            self.conversation_name,
            self.conversation_id,
            self.resource_id,
        )
        return "|".join(values)

    @property
    def identity_hash(self) -> str:
        return hashlib.sha256(self.identity_key.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DesktopTarget":
        if not isinstance(value, Mapping):
            raise ValueError("desktop action target must be an object")
        allowed = {field.name for field in dataclasses.fields(cls)}
        return cls(**{key: value[key] for key in allowed if key in value})


@dataclasses.dataclass(frozen=True)
class DesktopVerification:
    """Postcondition and readback contract for one desktop action."""

    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    required_state: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    allowed_sources: tuple[str, ...] = ()
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_markers",
            tuple(str(item) for item in self.required_markers if str(item)),
        )
        object.__setattr__(
            self,
            "forbidden_markers",
            tuple(str(item) for item in self.forbidden_markers if str(item)),
        )
        object.__setattr__(self, "required_state", dict(self.required_state or {}))
        object.__setattr__(
            self,
            "allowed_sources",
            tuple(str(item) for item in self.allowed_sources if str(item)),
        )
        timeout = float(self.timeout_seconds or 0.0)
        if timeout < 0:
            raise ValueError("verification timeout must be non-negative")
        object.__setattr__(self, "timeout_seconds", timeout)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_markers": list(self.required_markers),
            "forbidden_markers": list(self.forbidden_markers),
            "required_state": dict(self.required_state),
            "allowed_sources": list(self.allowed_sources),
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "DesktopVerification":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValueError("desktop action verification must be an object")
        return cls(
            required_markers=tuple(value.get("required_markers", ()) or ()),
            forbidden_markers=tuple(value.get("forbidden_markers", ()) or ()),
            required_state=dict(value.get("required_state", {}) or {}),
            allowed_sources=tuple(value.get("allowed_sources", ()) or ()),
            timeout_seconds=float(value.get("timeout_seconds", 10.0) or 0.0),
        )


@dataclasses.dataclass(frozen=True)
class DesktopApproval:
    """Exact approval state required before a side-effecting action."""

    required: bool = False
    confirmed: bool = False
    allow_foreground: bool = False
    approval_id: str = ""
    confirmed_effect_ids: tuple[str, ...] = ()
    expires_at: str = ""

    def __post_init__(self) -> None:
        for field in ("approval_id", "expires_at"):
            object.__setattr__(self, field, str(getattr(self, field) or "").strip())
        object.__setattr__(
            self,
            "confirmed_effect_ids",
            tuple(str(item) for item in self.confirmed_effect_ids if str(item)),
        )
        if self.confirmed and not self.approval_id:
            raise ValueError("confirmed desktop approval requires approval_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": bool(self.required),
            "confirmed": bool(self.confirmed),
            "allow_foreground": bool(self.allow_foreground),
            "approval_id": self.approval_id,
            "confirmed_effect_ids": list(self.confirmed_effect_ids),
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "DesktopApproval":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValueError("desktop action approval must be an object")
        return cls(
            required=bool(value.get("required", False)),
            confirmed=bool(value.get("confirmed", False)),
            allow_foreground=bool(value.get("allow_foreground", False)),
            approval_id=str(value.get("approval_id", "") or ""),
            confirmed_effect_ids=tuple(value.get("confirmed_effect_ids", ()) or ()),
            expires_at=str(value.get("expires_at", "") or ""),
        )


@dataclasses.dataclass(frozen=True)
class DesktopAction:
    """Application-independent action that can be compiled to ControlIntent."""

    action: str
    target: DesktopTarget
    parameters: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    effect_class: str = "read_only"
    preconditions: tuple[str, ...] = ()
    verification: DesktopVerification = dataclasses.field(
        default_factory=DesktopVerification
    )
    approval: DesktopApproval = dataclasses.field(default_factory=DesktopApproval)
    request_id: str = ""

    def __post_init__(self) -> None:
        action = str(self.action or "").strip()
        if not action:
            raise ValueError("desktop action requires a non-empty action")
        object.__setattr__(self, "action", action)
        if not isinstance(self.target, DesktopTarget):
            object.__setattr__(self, "target", DesktopTarget.from_dict(self.target))
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        object.__setattr__(
            self,
            "effect_class",
            str(self.effect_class or "read_only").strip() or "read_only",
        )
        object.__setattr__(
            self,
            "preconditions",
            tuple(str(item) for item in self.preconditions if str(item)),
        )
        if not isinstance(self.verification, DesktopVerification):
            object.__setattr__(
                self, "verification", DesktopVerification.from_dict(self.verification)
            )
        if not isinstance(self.approval, DesktopApproval):
            object.__setattr__(self, "approval", DesktopApproval.from_dict(self.approval))
        if self.effect_class in _CONFIRMATION_EFFECTS and not self.approval.required:
            object.__setattr__(
                self,
                "approval",
                dataclasses.replace(self.approval, required=True),
            )
        object.__setattr__(self, "request_id", str(self.request_id or "").strip())

    @property
    def requires_confirmation(self) -> bool:
        return bool(
            self.approval.required or self.effect_class in _CONFIRMATION_EFFECTS
        )

    @property
    def approval_satisfied(self) -> bool:
        if not self.requires_confirmation:
            return True
        return bool(self.approval.confirmed and self.approval.approval_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the protocol form, preserving native parameter types."""

        return {
            "schema_version": DESKTOP_ACTION_SCHEMA_VERSION,
            "request_id": self.request_id,
            "action": self.action,
            "target": self.target.to_dict(),
            "parameters": dict(self.parameters),
            "effect_class": self.effect_class,
            "preconditions": list(self.preconditions),
            "verification": self.verification.to_dict(),
            "approval": self.approval.to_dict(),
        }

    def to_safe_dict(self) -> dict[str, Any]:
        """Serialize an audit form with sensitive parameter values redacted."""

        data = self.to_dict()
        data["parameters"] = _safe_parameters(self.parameters)
        return data

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DesktopAction":
        if not isinstance(value, Mapping):
            raise ValueError("desktop action must be an object")
        version = str(value.get("schema_version", "") or "")
        if version != DESKTOP_ACTION_SCHEMA_VERSION:
            raise ValueError(f"unsupported desktop action schema: {version or '<missing>'}")
        target = DesktopTarget.from_dict(value.get("target", {}))
        parameters = value.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ValueError("desktop action parameters must be an object")
        return cls(
            action=str(value.get("action", "") or ""),
            target=target,
            parameters=dict(parameters),
            effect_class=str(value.get("effect_class", "read_only") or "read_only"),
            preconditions=tuple(value.get("preconditions", ()) or ()),
            verification=DesktopVerification.from_dict(value.get("verification")),
            approval=DesktopApproval.from_dict(value.get("approval")),
            request_id=str(value.get("request_id", "") or ""),
        )

    def to_control_intent(self):
        """Convert to the legacy fabric intent without importing it at module load."""

        from openwukong.control.fabric import ControlIntent

        parameters = dict(self.parameters)
        text = str(parameters.get("text", parameters.get("message", "")) or "")
        value = str(parameters.get("value", "") or "")
        confirmed = self.approval_satisfied and self.approval.confirmed
        return ControlIntent(
            action=self.action,
            text=text,
            url=str(parameters.get("url", "") or ""),
            selector=str(parameters.get("selector", "") or ""),
            value=value,
            submit=bool(parameters.get("submit", False)),
            allow_submit=bool(confirmed),
            allow_foreground_interaction=bool(
                confirmed and self.approval.allow_foreground
            ),
            allow_blocked_side_effects=bool(parameters.get("allow_blocked_side_effects", False)),
            confirmed_effect_ids=self.approval.confirmed_effect_ids,
            side_effect_policy=dict(parameters.get("side_effect_policy", {}) or {}),
            preferred_connector_id=str(
                parameters.get("preferred_connector_id", "") or ""
            ),
            preferred_route_id=str(parameters.get("preferred_route_id", "") or ""),
            parameters=parameters,
        )


def _safe_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in parameters.items():
        key_text = str(key)
        if _SENSITIVE_KEY.search(key_text):
            safe[key_text] = {"redacted": True}
            continue
        if key_text.casefold() in {"text", "message", "body", "content"}:
            text = str(value or "")
            safe[key_text] = {
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "length": len(text),
            }
            continue
        safe[key_text] = _safe_value(value)
    return safe


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _safe_parameters(value)
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)
    return value


__all__ = [
    "DESKTOP_ACTION_SCHEMA_VERSION",
    "DesktopAction",
    "DesktopApproval",
    "DesktopTarget",
    "DesktopVerification",
]
