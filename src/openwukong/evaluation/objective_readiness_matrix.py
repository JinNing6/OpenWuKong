# -*- coding: utf-8 -*-
"""Goal-level readiness matrix for the desktop-control objective."""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Iterable


BACKGROUND_NATIVE = "background-native"
BACKGROUND_READ_ONLY = "background-read-only"
BLOCKED = "blocked"


@dataclasses.dataclass(frozen=True)
class ObjectiveClosureAction:
    requirement_id: str
    action_id: str
    action_kind: str
    preferred_transport: str
    safe_probe_runner: str
    safe_to_run_now: bool
    background_safe: bool
    requires_user_confirmation: bool
    blocked_by_external_state: bool = False
    blocking_reason: str = ""
    verification_requirements: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "action_id": self.action_id,
            "action_kind": self.action_kind,
            "preferred_transport": self.preferred_transport,
            "safe_probe_runner": self.safe_probe_runner,
            "safe_to_run_now": self.safe_to_run_now,
            "background_safe": self.background_safe,
            "requires_user_confirmation": self.requires_user_confirmation,
            "blocked_by_external_state": self.blocked_by_external_state,
            "blocking_reason": self.blocking_reason,
            "verification_requirements": list(self.verification_requirements),
            "forbidden_actions": list(self.forbidden_actions),
            "notes": list(self.notes),
        }


@dataclasses.dataclass(frozen=True)
class ObjectiveReadinessItem:
    requirement_id: str
    surface: str
    capability: str
    status: str
    satisfied: bool
    source_runner: str
    selected_transport: str
    capability_level: str
    can_execute_without_focus: bool = False
    can_write_without_focus: bool = False
    required_for_goal: bool = True
    blocking_reason: str = ""
    evidence: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "surface": self.surface,
            "capability": self.capability,
            "status": self.status,
            "satisfied": self.satisfied,
            "source_runner": self.source_runner,
            "selected_transport": self.selected_transport,
            "capability_level": self.capability_level,
            "can_execute_without_focus": self.can_execute_without_focus,
            "can_write_without_focus": self.can_write_without_focus,
            "required_for_goal": self.required_for_goal,
            "blocking_reason": self.blocking_reason,
            "evidence": dict(self.evidence),
        }


@dataclasses.dataclass(frozen=True)
class ObjectiveReadinessMatrixReport:
    requirements: tuple[ObjectiveReadinessItem, ...]
    safe_run_ok: bool = True

    @property
    def mode(self) -> str:
        return "objective-readiness-matrix"

    @property
    def safety_mode(self) -> str:
        return "plan_only"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def goal_complete(self) -> bool:
        return bool(
            self.safe_run_ok
            and self.requirements
            and all(item.satisfied for item in self.requirements if item.required_for_goal)
        )

    def summary(self) -> dict:
        statuses = Counter(item.status for item in self.requirements)
        closure_actions = self.closure_actions
        return {
            "requirement_count": len(self.requirements),
            "goal_complete": self.goal_complete,
            "safe_run_ok": self.safe_run_ok,
            "satisfied_count": sum(1 for item in self.requirements if item.satisfied),
            "gated_count": statuses.get("gated", 0),
            "auth_required_count": statuses.get("auth_required", 0),
            "usage_limit_count": statuses.get("usage_limit", 0)
            + statuses.get("cli_usage_limit", 0),
            "unavailable_count": statuses.get("unavailable", 0),
            "failed_count": statuses.get("failed", 0),
            "background_execute_ready_count": sum(
                1 for item in self.requirements if item.can_execute_without_focus
            ),
            "background_write_ready_count": sum(
                1 for item in self.requirements if item.can_write_without_focus
            ),
            "unsatisfied_requirements": [
                item.requirement_id
                for item in self.requirements
                if item.required_for_goal and not item.satisfied
            ],
            "closure_action_count": len(closure_actions),
            "safe_closure_probe_count": sum(
                1 for item in closure_actions if item.safe_to_run_now and item.background_safe
            ),
            "external_state_blocked_closure_count": sum(
                1 for item in closure_actions if item.blocked_by_external_state
            ),
            "selected_transport_counts": dict(
                sorted(
                    Counter(
                        item.selected_transport or "none"
                        for item in self.requirements
                    ).items()
                )
            ),
        }

    @property
    def closure_actions(self) -> tuple[ObjectiveClosureAction, ...]:
        return tuple(
            _closure_action_for_item(item)
            for item in self.requirements
            if item.required_for_goal and not item.satisfied
        )

    @property
    def closure_plan(self) -> dict:
        actions = self.closure_actions
        return {
            "mode": "objective-closure-plan",
            "safety_mode": "plan_only",
            "control_allowed": False,
            "control_attempts": 0,
            "window_input_attempts": 0,
            "action_count": len(actions),
            "safe_to_run_now_count": sum(
                1 for item in actions if item.safe_to_run_now and item.background_safe
            ),
            "external_state_blocked_count": sum(
                1 for item in actions if item.blocked_by_external_state
            ),
            "actions": [item.to_dict() for item in actions],
        }

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "goal_complete": self.goal_complete,
            "summary": self.summary(),
            "closure_plan": self.closure_plan,
            "requirements": [item.to_dict() for item in self.requirements],
        }


def build_objective_readiness_matrix(
    *,
    primary_report: dict | object | None = None,
    agent_app_report: dict | object | None = None,
    agent_cli_report: dict | object | None = None,
    requirements: Iterable[dict | object] = (),
    safe_run_ok: bool = True,
) -> ObjectiveReadinessMatrixReport:
    primary = _dict_from_report(primary_report)
    app = _dict_from_report(agent_app_report)
    cli = _dict_from_report(agent_cli_report)
    primary_transports = _primary_transports_by_scenario(primary)
    app_cases = _cases_by_key(app, "agent")
    cli_cases = _cases_by_key(cli, "agent")
    items = tuple(
        _item_for_requirement(
            _dict_from_report(requirement),
            primary_transports=primary_transports,
            app_cases=app_cases,
            cli_cases=cli_cases,
        )
        for requirement in requirements
    )
    return ObjectiveReadinessMatrixReport(
        requirements=items,
        safe_run_ok=bool(safe_run_ok),
    )


def _item_for_requirement(
    requirement: dict,
    *,
    primary_transports: dict[str, dict],
    app_cases: dict[str, dict],
    cli_cases: dict[str, dict],
) -> ObjectiveReadinessItem:
    requirement_id = str(requirement.get("requirement_id", "") or "")
    surface = str(requirement.get("surface", "") or "")
    capability = str(requirement.get("capability", "") or "")
    status = str(requirement.get("status", "") or "")
    satisfied = bool(requirement.get("satisfied", False)) or status == "verified"
    source_runner = str(requirement.get("source_runner", "") or "")
    blocking_reason = "" if satisfied else str(requirement.get("blocking_reason", "") or status)

    transport = _transport_for_requirement(
        requirement_id,
        surface=surface,
        source_runner=source_runner,
        primary_transports=primary_transports,
        app_cases=app_cases,
        cli_cases=cli_cases,
    )
    can_execute = bool(transport.get("can_execute_without_focus", False))
    can_write = bool(transport.get("can_write_without_focus", False))
    return ObjectiveReadinessItem(
        requirement_id=requirement_id,
        surface=surface,
        capability=capability,
        status=status,
        satisfied=satisfied,
        source_runner=source_runner,
        selected_transport=str(transport.get("selected_transport", "") or "none"),
        capability_level=str(transport.get("capability_level", "") or BLOCKED),
        can_execute_without_focus=can_execute,
        can_write_without_focus=can_write,
        blocking_reason=blocking_reason,
        evidence={
            **_dict_value(requirement.get("evidence")),
            **_dict_value(transport.get("evidence")),
        },
    )


def _transport_for_requirement(
    requirement_id: str,
    *,
    surface: str,
    source_runner: str,
    primary_transports: dict[str, dict],
    app_cases: dict[str, dict],
    cli_cases: dict[str, dict],
) -> dict:
    scenario_id = _primary_scenario_id(requirement_id)
    if scenario_id:
        return _primary_transport(primary_transports.get(scenario_id, {}))
    if source_runner == "agent_cli_real_no_loss" or requirement_id.endswith("_cli_background_task"):
        return _cli_transport(cli_cases.get(surface, {}), surface=surface)
    if source_runner == "agent_app_real_no_loss" or requirement_id.endswith("_background_chat"):
        return _app_transport(app_cases.get(surface, {}))
    return {}


def _closure_action_for_item(item: ObjectiveReadinessItem) -> ObjectiveClosureAction:
    requirement_id = item.requirement_id
    if requirement_id == "wechat_background_send":
        return _closure_action(
            item,
            action_id="attach_wechat_native_bridge_or_verified_uia_send",
            action_kind="connector_required",
            preferred_transport="wechat-native-bridge",
            safe_probe_runner="openwukong.evaluation.primary_real_no_loss",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "file_transfer_assistant_target_verified",
                "native_bridge_capability_ok_or_uia_value_invoke_verified",
                "required_marker_readback",
                "foreground_stability",
                "zero_window_input",
            ),
            forbidden_actions=_external_send_forbidden_actions(),
            notes=(
                "Read-only locator evidence is not enough for send.",
                "Only File Transfer Assistant can be used for no-loss WeChat send validation.",
            ),
        )
    if requirement_id == "browser_background_research":
        return _closure_action(
            item,
            action_id="run_owned_browser_devtools_no_loss_probe",
            action_kind="owned_helper_opt_in",
            preferred_transport="browser-devtools-owned",
            safe_probe_runner="openwukong.evaluation.primary_real_no_loss",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "owned_browser_profile_boundary",
                "cdp_target_match",
                "dom_readback",
                "owned_helper_cleanup",
                "zero_window_input",
            ),
            forbidden_actions=(
                "default_profile_browser_launch",
                "unmanaged_browser_process",
                "keyboard_input",
                "mouse_input",
                "clipboard_input",
            ),
            notes=("Use an owned isolated browser helper only; do not bind to unrelated user tabs.",),
        )
    if requirement_id == "codex_cli_background_task":
        return _closure_action(
            item,
            action_id="rerun_codex_cli_no_loss_with_execution_opt_in",
            action_kind="managed_cli_opt_in",
            preferred_transport="codex-cli-managed-terminal",
            safe_probe_runner="openwukong.evaluation.agent_cli_real_no_loss",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "managed_cli_no_loss_prompt",
                "read_only_or_ephemeral_workspace",
                "required_marker_readback",
                "no_runtime_foreground_risk_markers",
                "zero_window_input",
            ),
            forbidden_actions=_agent_forbidden_actions(),
            notes=("CLI route is separate from Codex desktop app chat.",),
        )
    if requirement_id == "claude_cli_background_task":
        if item.status != "auth_required" and "auth" not in item.blocking_reason:
            return _closure_action(
                item,
                action_id="rerun_claude_cli_no_loss_with_execution_opt_in",
                action_kind="managed_cli_opt_in",
                preferred_transport="claude-cli-managed-terminal",
                safe_probe_runner="openwukong.evaluation.agent_cli_real_no_loss",
                safe_to_run_now=True,
                background_safe=True,
                requires_user_confirmation=True,
                verification_requirements=(
                    "managed_cli_no_loss_prompt",
                    "required_marker_readback_or_auth_gate",
                    "zero_window_input",
                ),
                forbidden_actions=_agent_forbidden_actions(),
                notes=("Only classify auth_required after the no-loss CLI probe actually observes the auth gate.",),
            )
        return _closure_action(
            item,
            action_id="resolve_claude_cli_auth_then_rerun_no_loss_cli",
            action_kind="auth_required",
            preferred_transport="claude-cli-managed-terminal",
            safe_probe_runner="openwukong.evaluation.agent_cli_real_no_loss",
            safe_to_run_now=False,
            background_safe=True,
            requires_user_confirmation=True,
            blocked_by_external_state=True,
            verification_requirements=(
                "claude_auth_status_logged_in",
                "managed_cli_no_loss_prompt",
                "required_marker_readback",
                "zero_window_input",
            ),
            forbidden_actions=_agent_forbidden_actions(),
            notes=("Do not replace an explicit Claude CLI requirement with Claude Desktop.",),
        )
    if requirement_id == "cursor_cli_background_task":
        return _closure_action(
            item,
            action_id="resolve_cursor_agent_cli_or_explicit_ide_bridge",
            action_kind="transport_resolution",
            preferred_transport="cursor-agent-cli-or-ide-bridge",
            safe_probe_runner="openwukong.evaluation.agent_cli_real_no_loss",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=False,
            verification_requirements=(
                "explicit_cursor_agent_cli_or_bridge_url",
                "managed_cli_or_bridge_readback",
                "zero_window_input",
            ),
            forbidden_actions=_agent_forbidden_actions(),
            notes=("Active Cursor desktop remains protected unless an explicit bridge URL is supplied.",),
        )
    if requirement_id == "cursor_background_chat":
        return _closure_action(
            item,
            action_id="update_or_attach_cursor_ide_bridge_without_touching_active_profile",
            action_kind="ide_bridge_required",
            preferred_transport="ide-extension-bridge",
            safe_probe_runner="openwukong.evaluation.ide_extension_sync",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "installed_extension_adaptive_port",
                "registry_discovered_loopback_bridge_url",
                "chat_adapter_or_composer_contract_ready",
                "required_marker_readback",
                "zero_window_input",
            ),
            forbidden_actions=(
                "patch_active_cursor_profile_without_override",
                "probe_fixed_8787_by_default",
                "launch_visible_cursor_without_foreground_gate",
            )
            + _agent_forbidden_actions(),
            notes=(
                "Read-only sync audit is safe while Cursor is active.",
                "Live extension update must wait for Cursor reload/close or use an isolated profile.",
            ),
        )
    if requirement_id == "codex_app_background_chat":
        return _closure_action(
            item,
            action_id="attach_codex_native_app_server_or_cdp_bridge",
            action_kind="native_endpoint_required",
            preferred_transport="codex-app-server-ws-or-agent-native-bridge",
            safe_probe_runner="openwukong.evaluation.agent_native_connector_probe",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "endpoint_owner_not_msix_protocol_activation",
                "thread_or_session_workspace_match",
                "turn_send_contract_ready",
                "required_marker_readback",
                "zero_window_input",
            ),
            forbidden_actions=(
                "windowsapps_electron_flag_launch",
                "codex_turn_start_when_endpoint_is_desktop_msix",
                "ignore_session_start_or_error_dialog",
            )
            + _agent_forbidden_actions(),
            notes=("Thread/session readiness is separate from turn/action safety.",),
        )
    if requirement_id == "claude_desktop_background_chat":
        return _closure_action(
            item,
            action_id="attach_claude_desktop_native_or_devtools_bridge",
            action_kind="native_endpoint_required",
            preferred_transport="agent-native-bridge-or-devtools-page-target",
            safe_probe_runner="openwukong.evaluation.agent_native_connector_probe",
            safe_to_run_now=True,
            background_safe=True,
            requires_user_confirmation=True,
            verification_requirements=(
                "endpoint_owner_verified",
                "target_context_verified",
                "composer_contract_ready",
                "required_marker_readback",
                "zero_window_input",
            ),
            forbidden_actions=_agent_forbidden_actions(),
            notes=("Do not satisfy an explicit Claude Desktop requirement with Claude CLI.",),
        )
    return _closure_action(
        item,
        action_id="inspect_unmet_requirement_transport",
        action_kind="transport_resolution",
        preferred_transport=item.selected_transport or "none",
        safe_probe_runner="openwukong.evaluation.major_real_no_loss",
        safe_to_run_now=True,
        background_safe=True,
        requires_user_confirmation=False,
        verification_requirements=("requirement_specific_readback", "zero_window_input"),
        forbidden_actions=("keyboard_input", "mouse_input", "clipboard_input"),
    )


def _closure_action(
    item: ObjectiveReadinessItem,
    *,
    action_id: str,
    action_kind: str,
    preferred_transport: str,
    safe_probe_runner: str,
    safe_to_run_now: bool,
    background_safe: bool,
    requires_user_confirmation: bool,
    blocked_by_external_state: bool = False,
    verification_requirements: Iterable[str] = (),
    forbidden_actions: Iterable[str] = (),
    notes: Iterable[str] = (),
) -> ObjectiveClosureAction:
    return ObjectiveClosureAction(
        requirement_id=item.requirement_id,
        action_id=action_id,
        action_kind=action_kind,
        preferred_transport=preferred_transport,
        safe_probe_runner=safe_probe_runner,
        safe_to_run_now=bool(safe_to_run_now),
        background_safe=bool(background_safe),
        requires_user_confirmation=bool(requires_user_confirmation),
        blocked_by_external_state=bool(blocked_by_external_state),
        blocking_reason=item.blocking_reason,
        verification_requirements=_unique(verification_requirements),
        forbidden_actions=_unique(forbidden_actions),
        notes=_unique(notes),
    )


def _external_send_forbidden_actions() -> tuple[str, ...]:
    return (
        "keyboard_input",
        "mouse_input",
        "clipboard_input",
        "sendinput",
        "external_send_without_readback_marker",
    )


def _agent_forbidden_actions() -> tuple[str, ...]:
    return (
        "keyboard_input",
        "mouse_input",
        "clipboard_input",
        "foreground_takeover_without_gate",
        "cli_fallback_for_explicit_desktop_app_request",
    )


def _primary_scenario_id(requirement_id: str) -> str:
    mapping = {
        "wechat_background_observation": "wechat.chat.draft_reply",
        "wechat_background_send": "wechat.chat.draft_reply",
        "word_background_document": "word.document.create_background",
        "browser_background_research": "browser.research.collect_sources",
        "file_background_search": "files.search.find_candidate",
    }
    return mapping.get(requirement_id, "")


def _primary_transport(item: dict) -> dict:
    if not item:
        return {}
    return {
        "selected_transport": str(item.get("selected_transport", "") or "none"),
        "capability_level": str(item.get("capability_level", "") or BLOCKED),
        "can_execute_without_focus": bool(item.get("can_execute_without_focus", False)),
        "can_write_without_focus": bool(item.get("can_write_without_focus", False)),
        "evidence": {
            "primary_transport_blocking_reason": str(item.get("blocking_reason", "") or ""),
            "primary_transport_operation_scope": str(item.get("operation_scope", "") or ""),
        },
    }


def _cli_transport(case: dict, *, surface: str) -> dict:
    status = str(case.get("status", "") or "")
    verified = bool(status == "verified" and case.get("real_verified", False))
    selected = str(case.get("selected_transport", "") or "")
    if not selected and verified:
        selected = f"{surface}-cli-managed-terminal"
    return {
        "selected_transport": selected or "none",
        "capability_level": BACKGROUND_NATIVE if verified else BLOCKED,
        "can_execute_without_focus": verified,
        "can_write_without_focus": verified,
        "evidence": {
            "cli_status": status,
            "cli_real_verified": bool(case.get("real_verified", False)),
        },
    }


def _app_transport(case: dict) -> dict:
    matrix = _dict_value(case.get("transport_matrix"))
    selected_send = _dict_value(matrix.get("selected_send_transport"))
    best_available = _dict_value(matrix.get("best_available_transport"))
    selected = selected_send or best_available
    send_ready = bool(matrix.get("send_ready", False)) or bool(
        case.get("app_bridge_send_verified", False)
    ) or bool(case.get("uia_semantic_action_send_verified", False))
    read_ready = bool(selected)
    return {
        "selected_transport": str(selected.get("transport_id", "") or "none"),
        "capability_level": str(selected.get("capability_level", "") or (BACKGROUND_NATIVE if send_ready else BLOCKED)),
        "can_execute_without_focus": bool(read_ready or send_ready),
        "can_write_without_focus": send_ready,
        "evidence": {
            "agent_status": str(case.get("status", "") or ""),
            "send_ready": bool(matrix.get("send_ready", False)),
            "draft_ready": bool(matrix.get("draft_ready", False)),
            "app_bridge_send_verified": bool(case.get("app_bridge_send_verified", False)),
            "uia_semantic_action_send_verified": bool(
                case.get("uia_semantic_action_send_verified", False)
            ),
        },
    }


def _primary_transports_by_scenario(primary_report: dict) -> dict[str, dict]:
    matrix = _dict_value(primary_report.get("transport_matrix"))
    return {
        str(item.get("scenario_id", "") or ""): dict(item)
        for item in _list_value(matrix.get("scenarios"))
        if isinstance(item, dict)
    }


def _cases_by_key(report: dict, key: str) -> dict[str, dict]:
    return {
        str(item.get(key, "") or ""): dict(item)
        for item in _list_value(report.get("cases"))
        if isinstance(item, dict)
    }


def _dict_from_report(value: dict | object | None) -> dict:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            return dict(data)
    return {}


def _dict_value(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in items if str(item or "").strip()))
