# -*- coding: utf-8 -*-
"""Side-effect taxonomy and execution gate for control intents."""

from __future__ import annotations

import dataclasses


TAXONOMY_VERSION = "primary-side-effects-v1"

_EFFECT_DEFINITIONS: dict[str, dict[str, object]] = {
    "recorded_context.read": {
        "category": "recorded_read",
        "primitive": "read_recorded_context",
        "severity": "none",
        "requires_confirmation": False,
        "description": "Read recorded fixture metadata only.",
    },
    "local_draft.write": {
        "category": "local_draft",
        "primitive": "write_draft_artifact",
        "severity": "low",
        "requires_confirmation": False,
        "description": "Write an isolated draft artifact under the smoke output root.",
    },
    "external_communication.send_message": {
        "category": "external_communication",
        "primitive": "send_message",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Send a message to another person or external channel.",
    },
    "browser_navigation.open_live_tab": {
        "category": "browser_navigation",
        "primitive": "open_live_tab",
        "severity": "medium",
        "requires_confirmation": False,
        "description": "Open or navigate a live browser tab outside the recorded bundle.",
    },
    "browser_form_submit.submit_form": {
        "category": "browser_form_submit",
        "primitive": "submit_form",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Submit a live browser form or trigger a remote web action.",
    },
    "file_open.open_file": {
        "category": "file_open",
        "primitive": "open_file",
        "severity": "low",
        "requires_confirmation": False,
        "description": "Open a user file in a real application.",
    },
    "file_modify.modify_file": {
        "category": "file_modify",
        "primitive": "modify_file",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Modify, move, delete, or write a user file.",
    },
    "filesystem_scan.real_user_files": {
        "category": "filesystem_scan",
        "primitive": "real_filesystem_scan",
        "severity": "medium",
        "requires_confirmation": False,
        "description": "Scan real user directories instead of a recorded or temporary index.",
    },
    "agent_task_submission.submit_task": {
        "category": "agent_task_submission",
        "primitive": "submit_task",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Submit a task to an agent product or coding assistant.",
    },
    "agent_start.start_agent": {
        "category": "agent_start",
        "primitive": "start_agent",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Start a real agent run that can perform follow-on actions.",
    },
    "office_document.create_owned_temp": {
        "category": "office_document",
        "primitive": "create_owned_temp_document",
        "severity": "low",
        "requires_confirmation": False,
        "description": "Create or modify an owned temporary Office document under the test output root.",
    },
    "office_document.open_user_document": {
        "category": "office_document",
        "primitive": "open_user_document",
        "severity": "medium",
        "requires_confirmation": False,
        "description": "Open a user-owned Office document outside the isolated test output root.",
    },
    "office_document.modify_user_document": {
        "category": "office_document",
        "primitive": "modify_user_document",
        "severity": "high",
        "requires_confirmation": True,
        "description": "Modify a user-owned Office document.",
    },
}


@dataclasses.dataclass(frozen=True)
class SideEffectGateReport:
    """Plan-only gate result for possible external side effects."""

    allowed: bool
    decision: str = "allow"
    reason: str = ""
    policy: dict = dataclasses.field(default_factory=dict)
    blocked_effects: tuple[dict, ...] = ()
    confirmation_required_effects: tuple[dict, ...] = ()
    confirmed_effect_ids: tuple[str, ...] = ()
    allow_blocked_effects: bool = False

    @property
    def mode(self) -> str:
        return "side-effect-control-gate"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "taxonomy_version": str(self.policy.get("taxonomy_version", TAXONOMY_VERSION)),
            "allowed": self.allowed,
            "decision": self.decision,
            "reason": self.reason,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "allow_blocked_effects": self.allow_blocked_effects,
            "confirmed_effect_ids": list(self.confirmed_effect_ids),
            "blocked_effects": [dict(effect) for effect in self.blocked_effects],
            "blocked_effect_ids": [
                str(effect.get("effect_id", "") or "")
                for effect in self.blocked_effects
            ],
            "blocked_effect_categories": _effect_categories(self.blocked_effects),
            "confirmation_required_effects": [
                dict(effect) for effect in self.confirmation_required_effects
            ],
            "confirmation_required_effect_ids": [
                str(effect.get("effect_id", "") or "")
                for effect in self.confirmation_required_effects
            ],
            "policy": dict(self.policy),
        }


def build_side_effect_policy(
    *,
    allowed_effect_ids: object = (),
    blocked_effect_ids: object = (),
    confirmation_required_effect_ids: object = (),
) -> dict:
    """Build a serializable side-effect policy from stable effect ids."""

    allowed_ids = _string_tuple(allowed_effect_ids)
    blocked_ids = _string_tuple(blocked_effect_ids)
    explicit_confirmation_ids = set(_string_tuple(confirmation_required_effect_ids))

    allowed_effects = tuple(_effect_record(effect_id, decision="allow") for effect_id in allowed_ids)
    blocked_effects = tuple(_effect_record(effect_id, decision="block") for effect_id in blocked_ids)
    confirmation_required_effects = tuple(
        effect
        for effect in blocked_effects
        if effect["effect_id"] in explicit_confirmation_ids or bool(effect.get("requires_confirmation", False))
    )

    return {
        "mode": "primary-scenario-side-effect-policy",
        "taxonomy_version": TAXONOMY_VERSION,
        "allowed_effects": [dict(effect) for effect in allowed_effects],
        "blocked_effects": [dict(effect) for effect in blocked_effects],
        "confirmation_required_effects": [
            dict(effect) for effect in confirmation_required_effects
        ],
        "allowed_categories": _effect_categories(allowed_effects),
        "blocked_categories": _effect_categories(blocked_effects),
        "confirmation_required_categories": _effect_categories(confirmation_required_effects),
    }


def evaluate_side_effect_policy(
    policy: object,
    *,
    confirmed_effect_ids: object = (),
    allow_blocked_effects: bool = False,
) -> SideEffectGateReport:
    """Evaluate whether an intent may proceed past side-effect policy."""

    normalized_policy = policy if isinstance(policy, dict) else {}
    blocked_effects = _dict_tuple(normalized_policy.get("blocked_effects", ()))
    confirmation_required = _dict_tuple(
        normalized_policy.get("confirmation_required_effects", ())
    )
    confirmed_ids = _string_tuple(confirmed_effect_ids)
    confirmed = set(confirmed_ids)
    unconfirmed = tuple(
        effect
        for effect in confirmation_required
        if str(effect.get("effect_id", "") or "") not in confirmed
    )
    if unconfirmed:
        return SideEffectGateReport(
            allowed=False,
            decision="side_effect_confirmation_required",
            reason="side_effect_confirmation_required",
            policy=normalized_policy,
            blocked_effects=blocked_effects,
            confirmation_required_effects=unconfirmed,
            confirmed_effect_ids=confirmed_ids,
            allow_blocked_effects=bool(allow_blocked_effects),
        )
    if blocked_effects and not allow_blocked_effects:
        return SideEffectGateReport(
            allowed=False,
            decision="blocked_by_side_effect_policy",
            reason="blocked_by_side_effect_policy",
            policy=normalized_policy,
            blocked_effects=blocked_effects,
            confirmation_required_effects=(),
            confirmed_effect_ids=confirmed_ids,
            allow_blocked_effects=False,
        )
    return SideEffectGateReport(
        allowed=True,
        decision="allow",
        reason="side_effect_policy_allows_intent",
        policy=normalized_policy,
        blocked_effects=blocked_effects,
        confirmation_required_effects=confirmation_required,
        confirmed_effect_ids=confirmed_ids,
        allow_blocked_effects=bool(allow_blocked_effects),
    )


def _effect_record(effect_id: str, *, decision: str) -> dict:
    definition = dict(_EFFECT_DEFINITIONS.get(effect_id, {}))
    if not definition:
        definition = {
            "category": "unknown",
            "primitive": effect_id.rsplit(".", 1)[-1],
            "severity": "unknown",
            "requires_confirmation": False,
            "description": "",
        }
    return {
        "effect_id": effect_id,
        "category": str(definition.get("category", "") or ""),
        "primitive": str(definition.get("primitive", "") or ""),
        "severity": str(definition.get("severity", "") or ""),
        "decision": decision,
        "requires_confirmation": bool(definition.get("requires_confirmation", False)),
        "description": str(definition.get("description", "") or ""),
    }


def _effect_categories(effects: tuple[dict, ...]) -> list[str]:
    categories: list[str] = []
    for effect in effects:
        category = str(effect.get("category", "") or "")
        if category and category not in categories:
            categories.append(category)
    return categories


def _dict_tuple(value: object) -> tuple[dict, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in items:
            items.append(text)
    return tuple(items)
