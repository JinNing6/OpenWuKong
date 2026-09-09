# -*- coding: utf-8 -*-
"""Serializable control trajectories for audit, replay, and training data.

The recorder writes bounded JSON evidence for control plans/results. It only
records reports and artifact paths; it never performs desktop control.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Iterable, Mapping


TRAJECTORY_SCHEMA_VERSION = "control-trajectory-v1"

_DIRECT_ARTIFACT_PATH_KEYS = {
    "artifact_path",
    "capture_path",
    "dom_snapshot_path",
    "html_path",
    "json_path",
    "manifest_path",
    "output_path",
    "post_send_screenshot_path",
    "pre_send_screenshot_path",
    "report_path",
    "readback_path",
    "scratch_path",
    "screenshot_path",
    "state_path",
    "trajectory_path",
}
_ARTIFACT_KEY_SUFFIXES = (
    "_artifact_path",
    "_capture_path",
    "_manifest_path",
    "_output_path",
    "_report_path",
    "_screenshot_path",
    "_snapshot_path",
    "_state_path",
)
_PATH_CONTEXT_MARKERS = (
    "artifact",
    "capture",
    "manifest",
    "report",
    "screenshot",
    "snapshot",
    "state",
)
_IGNORED_ROLE_PARTS = {
    "action_report",
    "details",
    "payload",
    "report",
    "request",
    "response",
    "result",
}


@dataclasses.dataclass(frozen=True)
class TrajectoryArtifact:
    artifact_id: str
    role: str
    path: str
    media_type: str = ""
    sha256: str = ""

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "role": self.role,
            "path": self.path,
            "media_type": self.media_type,
            "sha256": self.sha256,
        }


@dataclasses.dataclass(frozen=True)
class ControlTrajectoryStep:
    step_id: str
    phase: str
    action: str
    report: dict
    artifacts: tuple[TrajectoryArtifact, ...] = ()
    timestamp: float = 0.0

    @property
    def control_attempts(self) -> int:
        return _safe_int(self.report.get("control_attempts"))

    def to_dict(self) -> dict:
        return {
            "mode": "control-trajectory-step",
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
            "step_id": self.step_id,
            "phase": self.phase,
            "action": self.action,
            "timestamp": self.timestamp,
            "control_attempts": self.control_attempts,
            "report": dict(self.report),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclasses.dataclass(frozen=True)
class ControlTrajectory:
    trajectory_id: str
    scenario: str = ""
    target_id: str = ""
    metadata: dict = dataclasses.field(default_factory=dict)
    steps: tuple[ControlTrajectoryStep, ...] = ()
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def mode(self) -> str:
        return "control-trajectory"

    @property
    def safety_mode(self) -> str:
        return "evidence_recording"

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return sum(step.control_attempts for step in self.steps)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "trajectory_id": self.trajectory_id,
            "scenario": self.scenario,
            "target_id": self.target_id,
            "metadata": dict(self.metadata),
            "step_count": len(self.steps),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [step.to_dict() for step in self.steps],
        }


class ControlTrajectoryRecorder:
    """Append-only JSON recorder for a single control trajectory."""

    def __init__(
        self,
        root: str | Path,
        *,
        trajectory_id: str = "",
        scenario: str = "",
        target_id: str = "",
        metadata: Mapping[str, object] | None = None,
    ):
        self.root = Path(root)
        self.trajectory_id = trajectory_id or f"traj-{uuid.uuid4().hex[:16]}"
        self.scenario = str(scenario or "")
        self.target_id = str(target_id or "")
        self.metadata = dict(metadata or {})
        self.created_at = time.time()
        self._steps: list[ControlTrajectoryStep] = []

    @property
    def directory(self) -> Path:
        return self.root / self.trajectory_id

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    @property
    def steps_dir(self) -> Path:
        return self.directory / "steps"

    def record_step(
        self,
        *,
        phase: str,
        action: str,
        report: object,
        artifacts: Iterable[TrajectoryArtifact | Mapping[str, object]] = (),
    ) -> ControlTrajectoryStep:
        """Record a report and update the trajectory manifest."""

        self.steps_dir.mkdir(parents=True, exist_ok=True)
        index = len(self._steps) + 1
        normalized_phase = _slug(phase or "step")
        step = ControlTrajectoryStep(
            step_id=f"step-{index:04d}",
            phase=str(phase or "step"),
            action=str(action or ""),
            report=_report_dict(report),
            artifacts=tuple(_artifact(item) for item in artifacts),
            timestamp=time.time(),
        )
        path = self.steps_dir / f"{index:04d}-{normalized_phase}.json"
        _write_json(path, step.to_dict())
        self._steps.append(step)
        self.write_manifest()
        return step

    def trajectory(self) -> ControlTrajectory:
        now = time.time()
        return ControlTrajectory(
            trajectory_id=self.trajectory_id,
            scenario=self.scenario,
            target_id=self.target_id,
            metadata=dict(self.metadata),
            steps=tuple(self._steps),
            created_at=self.created_at,
            updated_at=now,
        )

    def write_manifest(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        _write_json(self.manifest_path, self.trajectory().to_dict())
        return self.manifest_path


def build_trajectory_artifact(
    path: str | Path,
    *,
    role: str,
    media_type: str = "",
    artifact_id: str = "",
    compute_hash: bool = False,
) -> TrajectoryArtifact:
    """Build a serializable artifact reference, optionally hashing a file."""

    path_text = str(path)
    artifact_hash = _sha256(path) if compute_hash else ""
    return TrajectoryArtifact(
        artifact_id=artifact_id or _artifact_id(role, path_text),
        role=str(role or ""),
        path=path_text,
        media_type=str(media_type or ""),
        sha256=artifact_hash,
    )


def extract_trajectory_artifacts(
    report: object,
    *,
    compute_hash: bool = True,
) -> tuple[TrajectoryArtifact, ...]:
    """Extract existing artifact files from a nested report payload.

    Only known artifact-like path fields are considered, and only files that
    already exist on disk are attached. This keeps workspace/profile paths and
    other operational directories out of the trajectory artifact list.
    """

    artifacts: list[TrajectoryArtifact] = []
    seen_paths: set[str] = set()

    def add_candidate(path_value: object, role_parts: tuple[str, ...]) -> None:
        if isinstance(path_value, Path):
            raw_path = str(path_value)
        elif isinstance(path_value, str):
            raw_path = path_value
        else:
            return
        file_path = _existing_file_path(raw_path)
        if file_path is None:
            return
        resolved = str(file_path.resolve())
        if resolved in seen_paths:
            return
        seen_paths.add(resolved)
        artifacts.append(
            build_trajectory_artifact(
                resolved,
                role=_artifact_role(role_parts),
                media_type=_guess_media_type(file_path),
                compute_hash=compute_hash,
            )
        )

    def walk(value: object, parts: tuple[str, ...]) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key or "")
                child_parts = (*parts, key_text)
                if _is_artifact_path_key(key_text, parts):
                    add_candidate(child, child_parts)
                walk(child, child_parts)
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, (*parts, str(index)))

    walk(_report_dict(report), ())
    return tuple(artifacts)


def _report_dict(report: object) -> dict:
    if hasattr(report, "to_dict"):
        data = report.to_dict()
        return dict(data) if isinstance(data, dict) else {"value": data}
    if isinstance(report, Mapping):
        return dict(report)
    return {"value": str(report or "")}


def _artifact(value: TrajectoryArtifact | Mapping[str, object]) -> TrajectoryArtifact:
    if isinstance(value, TrajectoryArtifact):
        return value
    payload = dict(value)
    return TrajectoryArtifact(
        artifact_id=str(payload.get("artifact_id", "") or ""),
        role=str(payload.get("role", "") or ""),
        path=str(payload.get("path", "") or ""),
        media_type=str(payload.get("media_type", "") or ""),
        sha256=str(payload.get("sha256", "") or ""),
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _artifact_id(role: str, path: str) -> str:
    digest = hashlib.sha256(f"{role}\x1f{path}".encode("utf-8")).hexdigest()
    return f"artifact-{digest[:16]}"


def _sha256(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_file_path(value: str) -> Path | None:
    text = str(value or "").strip()
    if not text or "://" in text:
        return None
    try:
        path = Path(text).expanduser()
        if not path.is_file():
            return None
        return path
    except (OSError, ValueError):
        return None


def _is_artifact_path_key(key: str, parent_parts: tuple[str, ...]) -> bool:
    normalized = str(key or "").strip().lower()
    if normalized in _DIRECT_ARTIFACT_PATH_KEYS:
        return True
    if any(normalized.endswith(suffix) for suffix in _ARTIFACT_KEY_SUFFIXES):
        return True
    if normalized != "path":
        return False
    context = "_".join(str(part or "").lower() for part in parent_parts)
    return any(marker in context for marker in _PATH_CONTEXT_MARKERS)


def _artifact_role(parts: tuple[str, ...]) -> str:
    useful_parts = [
        part
        for part in parts
        if part
        and not part.isdigit()
        and part.lower() not in _IGNORED_ROLE_PARTS
    ]
    if not useful_parts:
        useful_parts = ["artifact"]
    return _underscore_slug("_".join(useful_parts[-4:]))


def _underscore_slug(value: str) -> str:
    text = "".join(
        char.lower() if char.isalnum() else "_"
        for char in str(value or "")
    ).strip("_")
    while "__" in text:
        text = text.replace("__", "_")
    return text or "artifact"


def _guess_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".jsonl":
        return "application/x-ndjson"
    if suffix == ".png":
        return "image/png"

    guess_file_type = getattr(mimetypes, "guess_file_type", None)
    if callable(guess_file_type):
        media_type = guess_file_type(path, strict=False)[0]
    else:
        media_type = mimetypes.guess_type(str(path), strict=False)[0]
    return str(media_type or "")


def _slug(value: str) -> str:
    text = "".join(
        char.lower() if char.isalnum() else "-"
        for char in str(value or "")
    ).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text or "step"


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
