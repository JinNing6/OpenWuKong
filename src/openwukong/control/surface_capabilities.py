# -*- coding: utf-8 -*-
"""Short-lived, evidence-bound capabilities for a desktop surface."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_PROFILE_TTL_SECONDS = 60.0
_READ_ONLY_PREFIXES = ("read", "inspect", "observe", "list", "snapshot")
_WRITE_ACTION_HINTS = (
    "send",
    "set_",
    "write",
    "invoke",
    "select",
    "toggle",
    "upload",
    "delete",
    "move",
    "rename",
    "publish",
    "draft",
)


@dataclasses.dataclass(frozen=True)
class CapabilityEvidence:
    """One observed fact used to grant a surface capability."""

    source: str
    field: str
    value: Any
    source_id: str = ""

    def __post_init__(self) -> None:
        for field in ("source", "field", "source_id"):
            object.__setattr__(self, field, str(getattr(self, field) or "").strip())
        if not self.source or not self.field:
            raise ValueError("capability evidence requires source and field")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "field": self.field,
            "value": self.value,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityEvidence":
        if not isinstance(value, Mapping):
            raise ValueError("capability evidence must be an object")
        return cls(
            source=str(value.get("source", "") or ""),
            field=str(value.get("field", "") or ""),
            value=value.get("value"),
            source_id=str(value.get("source_id", "") or ""),
        )


@dataclasses.dataclass(frozen=True)
class SurfaceCapabilityProfile:
    """Evidence-backed capabilities for one process/window/session surface."""

    process_name: str = ""
    pid: int = 0
    hwnd: int = 0
    window_title: str = ""
    surface_id: str = ""
    session_id: str = ""
    process_path: str = ""
    observed_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ttl_seconds: float = DEFAULT_PROFILE_TTL_SECONDS
    capabilities: Mapping[str, Mapping[str, Any]] = dataclasses.field(default_factory=dict)
    evidence: tuple[CapabilityEvidence, ...] = ()

    def __post_init__(self) -> None:
        for field in (
            "process_name",
            "window_title",
            "surface_id",
            "session_id",
            "process_path",
        ):
            object.__setattr__(self, field, str(getattr(self, field) or "").strip())
        for field in ("pid", "hwnd"):
            value = int(getattr(self, field) or 0)
            if value < 0:
                raise ValueError(f"{field} must be non-negative")
            object.__setattr__(self, field, value)
        if not isinstance(self.observed_at, datetime):
            raise ValueError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(
            self,
            "observed_at",
            self.observed_at.astimezone(timezone.utc),
        )
        ttl = float(self.ttl_seconds or 0.0)
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        object.__setattr__(self, "ttl_seconds", ttl)
        normalized: dict[str, dict[str, Any]] = {}
        for action, grant in dict(self.capabilities or {}).items():
            action_name = str(action or "").strip()
            if not action_name:
                raise ValueError("capability action name must be non-empty")
            if not isinstance(grant, Mapping):
                raise ValueError(f"capability grant for {action_name} must be an object")
            data = dict(grant)
            confidence = int(data.get("confidence", 0) or 0)
            if confidence < 0 or confidence > 100:
                raise ValueError(f"capability confidence for {action_name} must be 0..100")
            data["route"] = str(data.get("route", "") or "").strip()
            data["confidence"] = confidence
            data["read_only"] = bool(
                data.get("read_only", _looks_read_only(action_name))
            )
            normalized[action_name] = data
        object.__setattr__(self, "capabilities", normalized)
        object.__setattr__(
            self,
            "evidence",
            tuple(
                item
                if isinstance(item, CapabilityEvidence)
                else CapabilityEvidence.from_dict(item)
                for item in (self.evidence or ())
            ),
        )

    @property
    def control_attempts(self) -> int:
        """Profiles are observational and never perform a control attempt."""

        return 0

    @property
    def target_identity(self) -> str:
        return "|".join(
            (
                self.process_name.casefold(),
                str(self.pid),
                str(self.hwnd),
                self.window_title,
                self.surface_id,
                self.session_id,
            )
        )

    def is_bound(self, *, pid: int, hwnd: int) -> bool:
        """Return true only for a positive PID/HWND pair observed by this profile."""

        return bool(
            self.pid
            and self.hwnd
            and int(pid or 0) == self.pid
            and int(hwnd or 0) == self.hwnd
        )

    def is_fresh(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        current = current.astimezone(timezone.utc)
        age = current - self.observed_at
        return timedelta(0) <= age <= timedelta(seconds=self.ttl_seconds)

    def supports(
        self,
        action: str,
        *,
        minimum_confidence: int = 0,
        now: datetime | None = None,
    ) -> bool:
        action_name = str(action or "").strip()
        grant = self.capabilities.get(action_name)
        if not grant or not self.is_fresh(now=now):
            return False
        confidence = int(grant.get("confidence", 0) or 0)
        if confidence < int(minimum_confidence):
            return False
        if not bool(grant.get("read_only", _looks_read_only(action_name))):
            if not self.pid or not self.hwnd:
                return False
        return True

    def grant(self, action: str) -> dict[str, Any]:
        return dict(self.capabilities.get(str(action or "").strip(), {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "openwukong-surface-capability-v1",
            "process_name": self.process_name,
            "pid": self.pid,
            "hwnd": self.hwnd,
            "window_title": self.window_title,
            "surface_id": self.surface_id,
            "session_id": self.session_id,
            "process_path": self.process_path,
            "observed_at": self.observed_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "capabilities": {
                action: dict(grant) for action, grant in self.capabilities.items()
            },
            "evidence": [item.to_dict() for item in self.evidence],
            "control_attempts": self.control_attempts,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SurfaceCapabilityProfile":
        if not isinstance(value, Mapping):
            raise ValueError("surface capability profile must be an object")
        version = str(value.get("schema_version", "") or "")
        if version != "openwukong-surface-capability-v1":
            raise ValueError(
                f"unsupported surface capability schema: {version or '<missing>'}"
            )
        observed_at = value.get("observed_at")
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        return cls(
            process_name=str(value.get("process_name", "") or ""),
            pid=int(value.get("pid", 0) or 0),
            hwnd=int(value.get("hwnd", 0) or 0),
            window_title=str(value.get("window_title", "") or ""),
            surface_id=str(value.get("surface_id", "") or ""),
            session_id=str(value.get("session_id", "") or ""),
            process_path=str(value.get("process_path", "") or ""),
            observed_at=observed_at,
            ttl_seconds=float(value.get("ttl_seconds", DEFAULT_PROFILE_TTL_SECONDS)),
            capabilities=dict(value.get("capabilities", {}) or {}),
            evidence=tuple(
                CapabilityEvidence.from_dict(item)
                for item in (value.get("evidence", ()) or ())
            ),
        )


def profile_from_accessibility_window(
    window: object,
    *,
    observed_at: datetime | None = None,
    ttl_seconds: float = DEFAULT_PROFILE_TTL_SECONDS,
) -> SurfaceCapabilityProfile:
    """Normalize a read-only AccessibilityWindowSnapshot into generic grants."""

    elements = tuple(getattr(window, "elements", ()) or ())
    text_count = 0
    value_count = 0
    invoke_count = 0
    for element in elements:
        control_type = str(getattr(element, "control_type", "") or "").strip()
        patterns = {str(item) for item in (getattr(element, "patterns", ()) or ())}
        if control_type in {"Text", "Edit", "Document", "ListItem", "DataItem"}:
            text_count += 1
        if control_type in {"Edit", "Document", "ComboBox"} and patterns & {
            "Value",
            "TextEdit",
        }:
            value_count += 1
        if (
            control_type in {"Button", "Hyperlink", "MenuItem", "SplitButton"}
            and "Invoke" in patterns
        ):
            invoke_count += 1

    capabilities: dict[str, dict[str, Any]] = {
        "desktop.inspect": {
            "route": "uia-structural-observe",
            "confidence": 90,
            "read_only": True,
        },
        "desktop.screenshot": {
            "route": "uia-window-observe",
            "confidence": 80,
            "read_only": True,
        },
    }
    if text_count:
        capabilities["desktop.read_text"] = {
            "route": "uia-structural-observe",
            "confidence": min(95, 60 + text_count),
            "read_only": True,
        }
    if value_count:
        capabilities["desktop.set_value"] = {
            "route": "uia-semantic",
            "confidence": min(95, 70 + value_count),
            "read_only": False,
            "candidate_count": value_count,
        }
    if invoke_count:
        capabilities["desktop.invoke"] = {
            "route": "uia-semantic",
            "confidence": min(95, 70 + invoke_count),
            "read_only": False,
            "candidate_count": invoke_count,
        }

    evidence = (
        CapabilityEvidence(
            source="accessibility_probe", field="element_count", value=len(elements)
        ),
        CapabilityEvidence(
            source="accessibility_probe",
            field="text_candidate_count",
            value=text_count,
        ),
        CapabilityEvidence(
            source="accessibility_probe",
            field="value_candidate_count",
            value=value_count,
        ),
        CapabilityEvidence(
            source="accessibility_probe",
            field="invoke_candidate_count",
            value=invoke_count,
        ),
    )
    return SurfaceCapabilityProfile(
        process_name=str(getattr(window, "process_name", "") or ""),
        pid=int(getattr(window, "pid", 0) or 0),
        hwnd=int(getattr(window, "hwnd", 0) or 0),
        window_title=str(getattr(window, "window_title", "") or ""),
        surface_id=str(getattr(window, "class_name", "") or ""),
        observed_at=observed_at or datetime.now(timezone.utc),
        ttl_seconds=ttl_seconds,
        capabilities=capabilities,
        evidence=evidence,
    )


def _looks_read_only(action: str) -> bool:
    leaf = action.rsplit(".", 1)[-1].casefold()
    if leaf.startswith(_READ_ONLY_PREFIXES):
        return True
    return not leaf.startswith(_WRITE_ACTION_HINTS)


__all__ = [
    "CapabilityEvidence",
    "DEFAULT_PROFILE_TTL_SECONDS",
    "SurfaceCapabilityProfile",
    "profile_from_accessibility_window",
]
