# -*- coding: utf-8 -*-
"""Read-only WeChat surface candidates and exact target resolution."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Any


@dataclasses.dataclass(frozen=True)
class WeChatControlCandidate:
    role: str
    name: str = ""
    automation_id: str = ""
    control_type: str = ""
    patterns: tuple[str, ...] = ()
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: int = 0
    source: str = "uia"
    hwnd: int = 0

    @property
    def stable_id(self) -> str:
        return self.automation_id.strip() or self.name.strip()

    @property
    def stable(self) -> bool:
        return bool(self.stable_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "automation_id": self.automation_id,
            "control_type": self.control_type,
            "patterns": list(self.patterns),
            "rect": list(self.rect),
            "confidence": self.confidence,
            "source": self.source,
            "hwnd": self.hwnd,
            "stable_id": self.stable_id,
            "stable": self.stable,
        }


@dataclasses.dataclass(frozen=True)
class WeChatTargetCandidate:
    target_type: str
    display_name: str
    target_id: str = ""
    confidence: int = 0
    source: str = "uia"
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_type", str(self.target_type or "").strip())
        object.__setattr__(self, "display_name", str(self.display_name or "").strip())
        object.__setattr__(self, "target_id", str(self.target_id or "").strip())
        object.__setattr__(
            self,
            "confidence",
            max(0, min(100, int(self.confidence or 0))),
        )
        object.__setattr__(
            self,
            "source",
            str(self.source or "uia").strip() or "uia",
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(str(item) for item in self.evidence if str(item)),
        )
        if not self.target_type or not self.display_name:
            raise ValueError("WeChat target candidate requires type and display name")

    @property
    def stable_id(self) -> str:
        return self.target_id or self.display_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "display_name": self.display_name,
            "target_id": self.target_id,
            "confidence": self.confidence,
            "source": self.source,
            "evidence": list(self.evidence),
            "stable_id": self.stable_id,
        }


@dataclasses.dataclass(frozen=True)
class WeChatTargetResolution:
    ok: bool
    decision: str
    candidates: tuple[WeChatTargetCandidate, ...] = ()
    selected: WeChatTargetCandidate | None = None
    control_attempts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "control_attempts": self.control_attempts,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "selected": self.selected.to_dict() if self.selected else {},
        }


class WeChatTargetResolver:
    """Resolve observed candidates without touching the live WeChat window."""

    def resolve(
        self,
        surface: object,
        *,
        target_type: str = "conversation",
        query: str = "",
        selected_index: int | None = None,
    ) -> WeChatTargetResolution:
        expected_type = _normalize(target_type)
        needle = _normalize(query)
        candidates = tuple(
            candidate
            for candidate in tuple(getattr(surface, "targets", ()) or ())
            if _normalize(candidate.target_type) == expected_type
            and (not needle or needle in _normalize(candidate.display_name))
        )
        if not candidates:
            return WeChatTargetResolution(
                ok=False,
                decision="target_not_found",
                candidates=(),
            )
        if selected_index is not None:
            index = int(selected_index)
            if index < 0 or index >= len(candidates):
                return WeChatTargetResolution(
                    ok=False,
                    decision="target_selection_invalid",
                    candidates=candidates,
                )
            return WeChatTargetResolution(
                ok=True,
                decision="target_selected_explicitly",
                candidates=candidates,
                selected=candidates[index],
            )
        if len(candidates) != 1:
            return WeChatTargetResolution(
                ok=False,
                decision="target_unresolved",
                candidates=candidates,
            )
        return WeChatTargetResolution(
            ok=True,
            decision="target_exactly_resolved",
            candidates=candidates,
            selected=candidates[0],
        )


def _normalize(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


__all__ = [
    "WeChatControlCandidate",
    "WeChatTargetCandidate",
    "WeChatTargetResolution",
    "WeChatTargetResolver",
]
