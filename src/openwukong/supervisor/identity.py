# -*- coding: utf-8 -*-
"""Workspace/session/task/action identity model for supervisor routing."""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import time
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from openwukong.core.config import load_config
from openwukong.core.constants import PROJECT_ALIASES, PROJECT_ALIAS_REVERSE

_IDE_BRANDS = {
    "cursor",
    "codex",
    "code",
    "visual studio code",
    "vscode",
    "copilot",
    "github copilot",
    "windsurf",
    "antigravity",
    "idea",
    "intellij",
    "pycharm",
    "webstorm",
    "clion",
    "terminal",
    "browser",
    "git",
}

_PROCESS_TO_CONNECTOR = {
    "codex": "codex",
    "cursor": "cursor",
    "windsurf": "cursor",
    "git": "git",
    "powershell": "terminal",
    "pwsh": "terminal",
    "cmd": "terminal",
    "bash": "terminal",
    "browser": "browser",
    "chrome": "browser",
    "msedge": "browser",
    "firefox": "browser",
}

_WORKSPACE_ROOT_MARKERS = (
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    text = text.strip("-")
    return text or "unknown"


def _short_hash(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:10]


@dataclasses.dataclass(frozen=True)
class WorkspaceRef:
    workspace_id: str
    display_name: str
    canonical_name: str
    root_path: str = ""
    resource_url: str = ""
    basis: str = "unknown"
    aliases: tuple[str, ...] = ()
    match_tokens: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "display_name": self.display_name,
            "canonical_name": self.canonical_name,
            "root_path": self.root_path,
            "resource_url": self.resource_url,
            "basis": self.basis,
            "aliases": list(self.aliases),
            "match_tokens": list(self.match_tokens),
        }


@dataclasses.dataclass(frozen=True)
class SessionRef:
    session_id: str
    workspace_id: str
    connector_id: str
    pid: int = 0
    process_name: str = ""
    window_title: str = ""
    project_name: str = ""
    workspace_name: str = ""
    workspace_path: str = ""
    resource_url: str = ""
    source: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "connector_id": self.connector_id,
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title,
            "project_name": self.project_name,
            "workspace_name": self.workspace_name,
            "workspace_path": self.workspace_path,
            "resource_url": self.resource_url,
            "source": self.source,
        }


@dataclasses.dataclass(frozen=True)
class TaskRef:
    task_id: str
    task_name: str
    workspace_id: str
    workspace_name: str
    connector_hint: str
    status: str = ""
    workspace_path: str = ""
    resource_url: str = ""
    window_match: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "connector_hint": self.connector_hint,
            "status": self.status,
            "workspace_path": self.workspace_path,
            "resource_url": self.resource_url,
            "window_match": self.window_match,
        }


@dataclasses.dataclass(frozen=True)
class ActionRecord:
    action_id: str
    task_id: str
    workspace_id: str
    session_id: str
    connector_id: str
    action_type: str
    status: str
    detail: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "workspace_id": self.workspace_id,
            "session_id": self.session_id,
            "connector_id": self.connector_id,
            "action_type": self.action_type,
            "status": self.status,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


@dataclasses.dataclass(frozen=True)
class IdentitySnapshot:
    workspaces: tuple[WorkspaceRef, ...] = ()
    sessions: tuple[SessionRef, ...] = ()
    tasks: tuple[TaskRef, ...] = ()
    actions: tuple[ActionRecord, ...] = ()

    def to_dict(self) -> dict:
        return {
            "workspaces": [workspace.to_dict() for workspace in self.workspaces],
            "sessions": [session.to_dict() for session in self.sessions],
            "tasks": [task.to_dict() for task in self.tasks],
            "actions": [action.to_dict() for action in self.actions],
        }


class WorkspaceIdentityModel:
    """Resolve workspaces, sessions, tasks, and actions into a shared identity graph."""

    def __init__(
        self,
        known_roots: Optional[dict[str, str]] = None,
        auto_load_config: bool = True,
    ):
        self._known_roots_by_name: dict[str, set[str]] = {}
        if auto_load_config:
            self._load_configured_workspaces()
        for name, root_path in (known_roots or {}).items():
            self.register_workspace_root(name, root_path)

    def workspace_for_goal(self, goal: Any) -> WorkspaceRef:
        return self.resolve_workspace(
            workspace_path=getattr(goal, "workspace_path", ""),
            resource_url=getattr(goal, "resource_url", ""),
            name_hint=getattr(goal, "window_match", ""),
            title_hint=getattr(goal, "matched_window_title", ""),
        )

    def workspace_for_state(self, state: Any) -> WorkspaceRef:
        return self.resolve_workspace(
            workspace_path="",
            resource_url="",
            name_hint=getattr(state, "project_name", ""),
            title_hint=getattr(state, "window_title", ""),
        )

    def session_for_state(self, state: Any) -> SessionRef:
        workspace = self.workspace_for_state(state)
        process_name = str(getattr(state, "process_name", "") or "")
        window_title = str(getattr(state, "window_title", "") or "")
        project_name = str(getattr(state, "project_name", "") or "")
        connector_id = self._infer_connector_id(
            process_name=process_name,
            window_title=window_title,
            project_name=project_name,
        )
        session_key = "|".join(
            part
            for part in [
                connector_id,
                str(getattr(state, "pid", 0) or 0),
                window_title.strip().lower(),
                workspace.workspace_id,
            ]
            if part
        )
        return SessionRef(
            session_id=f"session:{_short_hash(session_key)}",
            workspace_id=workspace.workspace_id,
            connector_id=connector_id,
            pid=int(getattr(state, "pid", 0) or 0),
            process_name=process_name,
            window_title=window_title,
            project_name=project_name,
            workspace_name=workspace.display_name,
            workspace_path=workspace.root_path,
            resource_url=workspace.resource_url,
            source="monitor",
        )

    def session_for_target(self, target: Any, connector_id: str = "") -> SessionRef:
        workspace = self.resolve_workspace(
            workspace_path=getattr(target, "workspace_path", ""),
            resource_url=getattr(target, "resource_url", ""),
            name_hint=getattr(target, "project_name", "") or getattr(target, "workspace_hint", ""),
            title_hint=getattr(target, "window_title", ""),
        )
        process_name = str(getattr(target, "process_name", "") or "")
        window_title = str(getattr(target, "window_title", "") or "")
        session_connector = connector_id or self._infer_connector_id(
            process_name=process_name,
            window_title=window_title,
            project_name=str(getattr(target, "project_name", "") or ""),
        )
        session_key = "|".join(
            part
            for part in [
                session_connector,
                str(getattr(target, "pid", 0) or 0),
                window_title.strip().lower(),
                workspace.workspace_id,
            ]
            if part
        )
        return SessionRef(
            session_id=f"session:{_short_hash(session_key)}",
            workspace_id=workspace.workspace_id,
            connector_id=session_connector,
            pid=int(getattr(target, "pid", 0) or 0),
            process_name=process_name,
            window_title=window_title,
            project_name=str(getattr(target, "project_name", "") or ""),
            workspace_name=workspace.display_name,
            workspace_path=workspace.root_path,
            resource_url=workspace.resource_url,
            source="target",
        )

    def task_for_goal(self, goal: Any) -> TaskRef:
        workspace = self.workspace_for_goal(goal)
        return TaskRef(
            task_id=str(getattr(goal, "task_id", "") or ""),
            task_name=str(getattr(goal, "task_name", "") or ""),
            workspace_id=workspace.workspace_id,
            workspace_name=workspace.display_name,
            connector_hint=str(getattr(goal, "connector_hint", "") or "auto"),
            status=str(getattr(getattr(goal, "status", ""), "value", getattr(goal, "status", "")) or ""),
            workspace_path=workspace.root_path,
            resource_url=workspace.resource_url,
            window_match=str(getattr(goal, "window_match", "") or ""),
        )

    def create_action_record(
        self,
        *,
        task_id: str,
        workspace_id: str,
        session_id: str,
        connector_id: str,
        action_type: str,
        status: str,
        detail: str,
        timestamp: Optional[float] = None,
    ) -> ActionRecord:
        stamp = timestamp if timestamp is not None else time.time()
        seed = "|".join(
            [
                task_id,
                workspace_id,
                session_id,
                connector_id,
                action_type,
                status,
                detail,
                f"{stamp:.6f}",
            ]
        )
        return ActionRecord(
            action_id=f"action:{_short_hash(seed)}",
            task_id=task_id,
            workspace_id=workspace_id,
            session_id=session_id,
            connector_id=connector_id,
            action_type=action_type,
            status=status,
            detail=detail,
            timestamp=stamp,
        )

    def bind_workspace_state_to_goal(
        self,
        goal: Any,
        states: Iterable[Any],
    ) -> tuple[Optional[Any], Optional[SessionRef], int]:
        goal_workspace = self.workspace_for_goal(goal)
        preferred_connector = str(getattr(goal, "connector_hint", "") or "").strip().lower()
        best_state = None
        best_session = None
        best_score = -1

        for state in states:
            session = self.session_for_state(state)
            if session.workspace_id != goal_workspace.workspace_id:
                continue

            score = 1000
            if preferred_connector and preferred_connector != "auto" and session.connector_id == preferred_connector:
                score += 150
            if int(getattr(goal, "matched_pid", 0) or 0) and int(getattr(state, "pid", 0) or 0) == int(getattr(goal, "matched_pid", 0) or 0):
                score += 30
            if str(getattr(goal, "matched_window_title", "") or "").strip().lower() == str(getattr(state, "window_title", "") or "").strip().lower():
                score += 20

            score += self._exact_workspace_name_bonus(goal_workspace, session)
            score += self._workspace_token_overlap(goal_workspace, session)

            if score > best_score:
                best_score = score
                best_state = state
                best_session = session

        return best_state, best_session, best_score

    def build_snapshot(
        self,
        goals: Iterable[Any],
        states: Iterable[Any],
        actions: Iterable[ActionRecord],
    ) -> IdentitySnapshot:
        workspace_map: dict[str, WorkspaceRef] = {}
        session_map: dict[str, SessionRef] = {}
        task_refs: list[TaskRef] = []

        for goal in goals:
            workspace = self.workspace_for_goal(goal)
            workspace_map[workspace.workspace_id] = workspace
            task_ref = self.task_for_goal(goal)
            task_refs.append(task_ref)

        for state in states:
            workspace = self.workspace_for_state(state)
            workspace_map[workspace.workspace_id] = workspace
            session = self.session_for_state(state)
            session_map[session.session_id] = session

        return IdentitySnapshot(
            workspaces=tuple(sorted(workspace_map.values(), key=lambda item: item.workspace_id)),
            sessions=tuple(sorted(session_map.values(), key=lambda item: item.session_id)),
            tasks=tuple(task_refs),
            actions=tuple(actions),
        )

    def resolve_workspace(
        self,
        *,
        workspace_path: str = "",
        resource_url: str = "",
        name_hint: str = "",
        title_hint: str = "",
    ) -> WorkspaceRef:
        explicit_path = self._normalize_path(workspace_path)
        title_path = self._extract_path_from_title(title_hint)
        explicit_root = self._resolve_workspace_root(
            explicit_path,
            allow_parent_search=False,
        )
        title_root = self._resolve_workspace_root(title_path, allow_parent_search=True)
        normalized_path = explicit_root or title_root

        name_canonical_hint = self._canonicalize_name(name_hint)
        if normalized_path and not explicit_root and name_canonical_hint:
            normalized_path = (
                self._raise_path_to_named_component(normalized_path, name_canonical_hint)
                or normalized_path
            )
        normalized_url = (resource_url or "").strip()

        canonical_name = (
            self._canonicalize_name(os.path.basename(normalized_path))
            or self._canonicalize_url_name(normalized_url)
            or self._canonicalize_name(name_hint)
            or self._canonicalize_name(self._extract_project_like_text(title_hint))
        )

        path_from_registry = False
        if not normalized_path and canonical_name:
            known_root = self._lookup_known_root(
                canonical_name,
                hints=[name_hint, title_hint, workspace_path],
            )
            if known_root:
                normalized_path = known_root
                path_from_registry = True

        display_name = (
            os.path.basename(normalized_path)
            or canonical_name
            or self._extract_project_like_text(name_hint)
            or self._extract_project_like_text(title_hint)
            or normalized_url
            or "unknown"
        )

        if normalized_url:
            basis = "url"
        elif normalized_path:
            basis = "registry" if path_from_registry else "path"
        elif canonical_name:
            basis = "name"
        elif title_hint:
            basis = "title"
        else:
            basis = "unknown"

        workspace_key = canonical_name or _slug(display_name)
        workspace_id = self._build_workspace_id(workspace_key, normalized_path, normalized_url)
        aliases = tuple(sorted(PROJECT_ALIAS_REVERSE.get(canonical_name, []))) if canonical_name else ()

        token_sources = [canonical_name, display_name, name_hint, title_hint, os.path.basename(normalized_path)]
        match_tokens = self._build_match_tokens(token_sources, aliases)

        if normalized_path and canonical_name:
            self.register_workspace_root(canonical_name, normalized_path, aliases=aliases)

        return WorkspaceRef(
            workspace_id=workspace_id,
            display_name=display_name,
            canonical_name=canonical_name or _slug(display_name),
            root_path=normalized_path,
            resource_url=normalized_url,
            basis=basis,
            aliases=aliases,
            match_tokens=match_tokens,
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        candidate = (path or "").strip()
        if not candidate:
            return ""
        try:
            return os.path.abspath(candidate)
        except Exception:
            return os.path.normpath(candidate)

    def _resolve_workspace_root(self, path: str, allow_parent_search: bool = True) -> str:
        candidate = self._normalize_path(path)
        if not candidate:
            return ""

        path_is_file = self._looks_like_file_path(candidate)
        start = candidate
        if path_is_file:
            start = os.path.dirname(start)

        if not start:
            return candidate

        if not os.path.exists(start):
            return start

        if not allow_parent_search and not path_is_file:
            return start

        cursor = start
        nearest_marker_root = ""
        highest_git_root = ""
        while True:
            if os.path.isdir(os.path.join(cursor, ".git")):
                highest_git_root = cursor
            elif not nearest_marker_root and self._contains_workspace_marker(cursor):
                nearest_marker_root = cursor

            parent = os.path.dirname(cursor)
            if not parent or parent == cursor:
                break
            cursor = parent

        return highest_git_root or nearest_marker_root or start

    @staticmethod
    def _extract_path_from_title(title: str) -> str:
        text = title or ""
        match = re.search(r"[A-Za-z]:\\[^\\/:*?\"<>|\r\n]+(?:\\[^\\/:*?\"<>|\r\n]+)+", text)
        if match:
            return match.group(0)
        return ""

    @staticmethod
    def _looks_like_file_path(path: str) -> bool:
        lowered = (path or "").strip().lower()
        if not lowered:
            return False
        if os.path.isfile(path):
            return True
        basename = os.path.basename(lowered)
        return "." in basename and not basename.startswith(".")

    @staticmethod
    def _contains_workspace_marker(path: str) -> bool:
        for marker in _WORKSPACE_ROOT_MARKERS:
            if os.path.exists(os.path.join(path, marker)):
                return True
        return False

    @staticmethod
    def _raise_path_to_named_component(path: str, canonical_name: str) -> str:
        candidate = (path or "").strip()
        expected = _slug(canonical_name)
        if not candidate or not expected:
            return ""

        parts: list[str] = []
        cursor = os.path.normpath(candidate)
        while True:
            head, tail = os.path.split(cursor)
            if tail:
                parts.append(tail)
            if not head or head == cursor:
                if head:
                    parts.append(head)
                break
            cursor = head

        rebuilt: list[str] = []
        for part in reversed(parts):
            rebuilt.append(part)
            if _slug(part) == expected:
                return os.path.normpath(os.path.join(*rebuilt))
        return ""

    def _canonicalize_name(self, value: str) -> str:
        text = (value or "").strip().lower()
        if not text:
            return ""

        if text in PROJECT_ALIASES:
            return PROJECT_ALIASES[text]

        exact_matches = []
        for alias, target in PROJECT_ALIASES.items():
            alias_lower = alias.lower()
            if alias_lower == text:
                return target
            if alias_lower and alias_lower in text:
                exact_matches.append((len(alias_lower), target))

        if exact_matches:
            exact_matches.sort(reverse=True)
            return exact_matches[0][1]

        cleaned = self._extract_project_like_text(text).lower()
        if cleaned in PROJECT_ALIASES:
            return PROJECT_ALIASES[cleaned]

        slugged = _slug(cleaned)
        return "" if slugged == "unknown" else slugged

    def _canonicalize_url_name(self, url: str) -> str:
        parsed = urlparse(url or "")
        if not parsed.netloc and not parsed.path:
            return ""
        path_name = os.path.basename(parsed.path.rstrip("/"))
        return self._canonicalize_name(path_name or parsed.netloc)

    def _load_configured_workspaces(self):
        try:
            config = load_config()
        except Exception:
            return

        workspaces = config.get("workspaces", {})
        if not isinstance(workspaces, dict):
            return

        for name, value in workspaces.items():
            if isinstance(value, str):
                self.register_workspace_root(name, value)
                continue
            if isinstance(value, dict):
                path = str(value.get("path", "") or "")
                aliases = value.get("aliases", []) or []
                self.register_workspace_root(name, path, aliases=aliases)

    def register_workspace_root(
        self,
        name: str,
        root_path: str,
        aliases: Iterable[str] = (),
    ):
        normalized_root = self._resolve_workspace_root(
            root_path,
            allow_parent_search=False,
        )
        if not normalized_root:
            return

        for candidate_name in [name, *(aliases or [])]:
            canonical_name = self._canonicalize_name(candidate_name)
            if not canonical_name:
                continue
            if canonical_name not in self._known_roots_by_name:
                self._known_roots_by_name[canonical_name] = set()
            self._known_roots_by_name[canonical_name].add(normalized_root)

    def _lookup_known_root(self, canonical_name: str, hints: Iterable[str]) -> str:
        candidates = sorted(self._known_roots_by_name.get(canonical_name, set()))
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]

        hint_blob = " ".join((hint or "").strip().lower() for hint in hints if hint).strip()
        if hint_blob:
            matched = [
                candidate for candidate in candidates
                if os.path.basename(candidate).lower() in hint_blob or candidate.lower() in hint_blob
            ]
            if len(matched) == 1:
                return matched[0]

        return ""

    def _extract_project_like_text(self, text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""

        parts = [part.strip() for part in re.split(r"\s[-|]\s| - | \| ", raw) if part.strip()]
        candidates = [raw, *parts]

        for candidate in candidates:
            lowered = candidate.lower().strip()
            if not lowered:
                continue
            if lowered in _IDE_BRANDS:
                continue
            if any(brand == lowered for brand in _IDE_BRANDS):
                continue
            if re.fullmatch(r"[a-z]:\\.*", lowered):
                return os.path.basename(candidate)
            if len(lowered) >= 2:
                return candidate

        return raw

    @staticmethod
    def _build_match_tokens(values: Iterable[str], aliases: Iterable[str]) -> tuple[str, ...]:
        tokens: set[str] = set()
        for value in [*values, *aliases]:
            lowered = (value or "").strip().lower()
            if not lowered:
                continue
            tokens.add(lowered)
            tokens.add(_slug(lowered))
        return tuple(sorted(token for token in tokens if token and token != "unknown"))

    @staticmethod
    def _build_workspace_id(workspace_key: str, root_path: str, resource_url: str) -> str:
        if root_path:
            return f"workspace:{workspace_key}:{_short_hash(root_path.lower())}"
        if resource_url:
            return f"workspace:{workspace_key}:{_short_hash(resource_url.lower())}"
        return f"workspace:{workspace_key}"

    @staticmethod
    def _infer_connector_id(
        *,
        process_name: str,
        window_title: str,
        project_name: str,
    ) -> str:
        blob = " ".join([process_name, window_title, project_name]).strip().lower()
        if "copilot" in blob:
            return "copilot"

        normalized_process = process_name.lower().replace(".exe", "")
        for hint, connector_id in _PROCESS_TO_CONNECTOR.items():
            if hint and hint in normalized_process:
                return connector_id

        if "visual studio code" in blob or normalized_process == "code":
            return "uia-ide"

        return "uia-ide"

    @staticmethod
    def _workspace_token_overlap(workspace: WorkspaceRef, session: SessionRef) -> int:
        blob = " ".join(
            [
                session.workspace_name,
                session.project_name,
                session.window_title,
                session.workspace_path,
                session.resource_url,
            ]
        ).lower()
        score = 0
        for token in workspace.match_tokens:
            if token and token in blob:
                score += 5
        return score

    @staticmethod
    def _exact_workspace_name_bonus(workspace: WorkspaceRef, session: SessionRef) -> int:
        expected = (workspace.canonical_name or workspace.display_name or "").strip().lower()
        if not expected:
            return 0

        candidates = [
            session.project_name,
            os.path.basename(session.workspace_path or ""),
        ]
        for candidate in candidates:
            lowered = (candidate or "").strip().lower()
            if lowered and (lowered == expected or _slug(lowered) == expected):
                return 120
        return 0
