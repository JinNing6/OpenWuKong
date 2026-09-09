# -*- coding: utf-8 -*-
"""Build an isolated patched Codex extension copy for bridge experiments.

The normal Cursor/VS Code extension profile is treated as read-only.  Applying
this patch requires an explicit isolated extension root and only writes under
that root.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Iterable, Optional

from openwukong.evaluation.codex_extension_bridge_probe import (
    WEBVIEW_ROUTE_MARKERS,
    _find_codex_extension_path,
)


CODEX_EXTENSION_COMMAND = "openwukong.codexBridge.prefillDryRun"
PATCH_MARKER = "OPENWUKONG_CODEX_BRIDGE_PATCH_V1"
MANIFEST_NAME = "openwukong-codex-bridge-manifest.json"
EXTENSION_ENTRYPOINT = Path("out") / "extension.js"
DEFAULT_ISOLATED_EXTENSION_ROOT = Path("logs") / "runtime" / "codex-isolated-bridge" / "extensions"
_MISSING_SOURCE_EXTENSION = Path("__openwukong_missing_codex_extension__")

_ANCHOR = "e.push(Ue);let _e=new hI(Ue);"
_PATCHED_ANCHOR_PREFIX = "e.push(Ue);"
_PATCHED_ANCHOR_SUFFIX = "let _e=new hI(Ue);"


@dataclasses.dataclass(frozen=True)
class CodexIsolatedBridgePatchReport:
    source_extension_path: str
    isolated_extension_root: str
    isolated_extension_path: str
    apply: bool
    overwrite: bool = False
    decision: str = ""
    source_extension_version: str = ""
    source_fingerprint: str = ""
    isolated_fingerprint: str = ""
    marker_evidence: tuple[dict, ...] = ()
    patch_plan: dict = dataclasses.field(default_factory=dict)
    manifest_path: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "codex-isolated-bridge-patch"

    @property
    def safety_mode(self) -> str:
        return "isolated_extension_copy_apply" if self.apply else "dry_run_no_writes"

    @property
    def ok(self) -> bool:
        return self.decision in {
            "codex_isolated_bridge_patch_ready",
            "codex_isolated_bridge_patch_applied",
            "codex_isolated_bridge_patch_already_present",
        }

    @property
    def normal_profile_touched(self) -> bool:
        return False

    @property
    def control_allowed(self) -> bool:
        return False

    @property
    def control_attempts(self) -> int:
        return 0

    @property
    def window_input_attempts(self) -> int:
        return 0

    @property
    def keyboard_input_attempts(self) -> int:
        return 0

    @property
    def clipboard_write_attempts(self) -> int:
        return 0

    @property
    def send_attempts(self) -> int:
        return 0

    @property
    def copy_attempts(self) -> int:
        return 1 if self.decision == "codex_isolated_bridge_patch_applied" else 0

    @property
    def patch_attempts(self) -> int:
        return 1 if self.decision in {
            "codex_isolated_bridge_patch_applied",
            "codex_isolated_bridge_patch_already_present",
        } else 0

    @property
    def write_attempts(self) -> int:
        if self.decision == "codex_isolated_bridge_patch_applied":
            return 3
        return 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "apply": self.apply,
            "overwrite": self.overwrite,
            "normal_profile_touched": self.normal_profile_touched,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "keyboard_input_attempts": self.keyboard_input_attempts,
            "clipboard_write_attempts": self.clipboard_write_attempts,
            "send_attempts": self.send_attempts,
            "copy_attempts": self.copy_attempts,
            "patch_attempts": self.patch_attempts,
            "write_attempts": self.write_attempts,
            "source_extension_path": self.source_extension_path,
            "isolated_extension_root": self.isolated_extension_root,
            "isolated_extension_path": self.isolated_extension_path,
            "source_extension_version": self.source_extension_version,
            "source_fingerprint": self.source_fingerprint,
            "isolated_fingerprint": self.isolated_fingerprint,
            "marker_evidence": [dict(item) for item in self.marker_evidence],
            "patch_plan": dict(self.patch_plan),
            "manifest_path": self.manifest_path,
            "elapsed_ms": round(float(self.elapsed_ms or 0.0), 3),
            "error": self.error,
        }


def build_codex_isolated_bridge_patch(
    *,
    source_extension_path: str | Path = "",
    isolated_extension_root: str | Path = DEFAULT_ISOLATED_EXTENSION_ROOT,
    apply: bool = False,
    overwrite: bool = False,
    installed_extension_roots: Iterable[str | Path] = (),
    timestamp: str | None = None,
) -> CodexIsolatedBridgePatchReport:
    started = time.perf_counter()
    source = _resolve_source_extension(source_extension_path, installed_extension_roots)
    isolated_root = Path(isolated_extension_root).expanduser()
    isolated_path = isolated_root / source.name if source.name else isolated_root

    def _report(
        decision: str,
        *,
        error: str = "",
        isolated_fingerprint: str = "",
        manifest_path: str = "",
        patch_plan: dict | None = None,
    ) -> CodexIsolatedBridgePatchReport:
        return CodexIsolatedBridgePatchReport(
            source_extension_path=str(source),
            isolated_extension_root=str(isolated_root),
            isolated_extension_path=str(isolated_path),
            source_extension_version=_read_extension_version(source),
            source_fingerprint=_extension_fingerprint(source),
            isolated_fingerprint=isolated_fingerprint,
            marker_evidence=_scan_marker_evidence(source),
            patch_plan=patch_plan or _patch_plan(source, isolated_path),
            manifest_path=manifest_path,
            apply=bool(apply),
            overwrite=bool(overwrite),
            decision=decision,
            error=error,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    validation_error = _validate_source(source)
    if validation_error:
        return _report("codex_isolated_bridge_patch_blocked", error=validation_error)

    root_error = _validate_isolated_root(
        source=source,
        isolated_root=isolated_root,
        isolated_path=isolated_path,
    )
    if root_error:
        return _report("codex_isolated_bridge_patch_blocked", error=root_error)

    patch_error = _validate_patchable_entrypoint(source / EXTENSION_ENTRYPOINT)
    if patch_error:
        return _report("codex_isolated_bridge_patch_blocked", error=patch_error)

    if not apply:
        return _report("codex_isolated_bridge_patch_ready")

    try:
        if isolated_path.exists():
            if not overwrite:
                return _report(
                    "codex_isolated_bridge_patch_blocked",
                    error="isolated_extension_target_exists_requires_overwrite",
                )
            _require_child(isolated_root.resolve(), isolated_path.resolve())
            shutil.rmtree(isolated_path)

        isolated_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, isolated_path)
        patched = _patch_entrypoint(isolated_path / EXTENSION_ENTRYPOINT)
        manifest = _write_manifest(
            source=source,
            isolated_root=isolated_root,
            isolated_path=isolated_path,
            patched=patched,
            timestamp=timestamp,
        )
        decision = (
            "codex_isolated_bridge_patch_applied"
            if patched
            else "codex_isolated_bridge_patch_already_present"
        )
        return _report(
            decision,
            isolated_fingerprint=_extension_fingerprint(isolated_path),
            manifest_path=str(manifest),
        )
    except Exception as exc:
        return _report(
            "codex_isolated_bridge_patch_failed",
            error=str(exc) or exc.__class__.__name__,
        )


def _resolve_source_extension(
    source_extension_path: str | Path,
    installed_extension_roots: Iterable[str | Path],
) -> Path:
    if source_extension_path:
        return Path(source_extension_path).expanduser()
    found = _find_codex_extension_path(installed_extension_roots)
    return Path(found).expanduser() if found else _MISSING_SOURCE_EXTENSION


def _validate_source(source: Path) -> str:
    if not str(source):
        return "codex_extension_source_not_found"
    if not source.is_dir():
        return "codex_extension_source_not_found"
    if not (source / "package.json").is_file():
        return "codex_extension_package_json_missing"
    if not (source / EXTENSION_ENTRYPOINT).is_file():
        return "codex_extension_entrypoint_missing"
    markers = _all_markers(_scan_marker_evidence(source))
    missing = sorted(set(WEBVIEW_ROUTE_MARKERS) - markers)
    if missing:
        return "codex_extension_webview_markers_missing:" + ",".join(missing)
    return ""


def _validate_isolated_root(*, source: Path, isolated_root: Path, isolated_path: Path) -> str:
    if not str(isolated_root):
        return "isolated_extension_root_required"
    normal_roots = tuple(root.resolve() for root in _normal_extension_roots())
    resolved_root = isolated_root.resolve()
    resolved_path = isolated_path.resolve()
    resolved_source = source.resolve()
    if resolved_path == resolved_source:
        return "isolated_target_matches_source_extension"
    if _path_contains(resolved_source, resolved_path):
        return "isolated_target_inside_source_extension"
    for normal_root in normal_roots:
        if _path_contains(normal_root, resolved_root) or _path_contains(normal_root, resolved_path):
            return "isolated_root_inside_normal_extension_profile"
        if resolved_root == normal_root or resolved_path == normal_root:
            return "isolated_root_is_normal_extension_profile"
    return ""


def _validate_patchable_entrypoint(entrypoint: Path) -> str:
    text = entrypoint.read_text(encoding="utf-8", errors="ignore")
    if PATCH_MARKER in text:
        return ""
    if _ANCHOR not in text:
        return "codex_extension_bridge_insertion_anchor_missing"
    for marker in ("shared-object-set", "open-vscode-command", "triggerNewChatViaWebview"):
        if marker not in text:
            return f"codex_extension_entrypoint_marker_missing:{marker}"
    return ""


def _patch_entrypoint(entrypoint: Path) -> bool:
    text = entrypoint.read_text(encoding="utf-8", errors="ignore")
    if PATCH_MARKER in text:
        return False
    patched = text.replace(
        _ANCHOR,
        _PATCHED_ANCHOR_PREFIX + _bridge_command_snippet() + _PATCHED_ANCHOR_SUFFIX,
        1,
    )
    if patched == text:
        raise ValueError("codex_extension_bridge_insertion_anchor_missing")
    entrypoint.write_text(patched, encoding="utf-8")
    return True


def _bridge_command_snippet() -> str:
    return (
        f'const {PATCH_MARKER}="1";'
        f'e.push(ut.commands.registerCommand("{CODEX_EXTENSION_COMMAND}",async owArgs=>{{'
        'const owInput=owArgs&&typeof owArgs==="object"?owArgs:{};'
        'const owText=typeof owInput.text==="string"?owInput.text:"";'
        'const owCwd=typeof owInput.cwd==="string"?owInput.cwd:null;'
        'const owCommentAttachments=Array.isArray(owInput.commentAttachments)?owInput.commentAttachments:void 0;'
        'if(!owText.trim()&&!(owCommentAttachments&&owCommentAttachments.length))'
        'return{ok:!1,decision:"codex_prefill_dry_run_rejected",error:"empty_prefill_text",'
        f'command:"{CODEX_EXTENSION_COMMAND}",send_attempts:0,control_attempts:0,'
        'window_input_attempts:0,keyboard_input_attempts:0,clipboard_write_attempts:0};'
        'const owValue={text:owText,cwd:owCwd,clearText:owInput.clearText!==!1};'
        'owCommentAttachments&&owCommentAttachments.length&&(owValue.commentAttachments=owCommentAttachments);'
        'Ue.sharedObjectRepository.set("composer_prefill",owValue);'
        'typeof Ue.broadcastToAllViews==="function"&&'
        'Ue.broadcastToAllViews({type:"shared-object-updated",key:"composer_prefill",value:owValue});'
        'return{ok:!0,decision:"codex_prefill_dry_run_written",'
        f'command:"{CODEX_EXTENSION_COMMAND}",prefill_text_length:owText.length,'
        'comment_attachment_count:owCommentAttachments?owCommentAttachments.length:0,cwd:owCwd,'
        'send_attempts:0,control_attempts:0,window_input_attempts:0,'
        'keyboard_input_attempts:0,clipboard_write_attempts:0};'
        '}));'
    )


def _write_manifest(
    *,
    source: Path,
    isolated_root: Path,
    isolated_path: Path,
    patched: bool,
    timestamp: str | None,
) -> Path:
    manifest_path = isolated_path / MANIFEST_NAME
    data = {
        "mode": "codex-isolated-bridge-patch-manifest",
        "patch_marker": PATCH_MARKER,
        "command": CODEX_EXTENSION_COMMAND,
        "patched": bool(patched),
        "created_at": timestamp or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_extension_path": str(source),
        "isolated_extension_root": str(isolated_root),
        "isolated_extension_path": str(isolated_path),
        "source_fingerprint": _extension_fingerprint(source),
        "isolated_fingerprint": _extension_fingerprint(isolated_path),
        "send_attempts": 0,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "keyboard_input_attempts": 0,
        "clipboard_write_attempts": 0,
    }
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _patch_plan(source: Path, isolated_path: Path) -> dict:
    return {
        "patch_marker": PATCH_MARKER,
        "command": CODEX_EXTENSION_COMMAND,
        "entrypoint": str(EXTENSION_ENTRYPOINT).replace("\\", "/"),
        "insertion_anchor": _ANCHOR,
        "target_entrypoint": str(isolated_path / EXTENSION_ENTRYPOINT) if str(isolated_path) else "",
        "normal_profile_allowed": False,
        "prefill_key": "composer_prefill",
        "prefill_value_shape": {
            "text": "string",
            "cwd": "string|null",
            "clearText": "boolean",
            "commentAttachments": "array optional",
        },
        "operations": [
            "copy_source_extension_to_isolated_root",
            "register_internal_prefill_dry_run_command",
            "write_composer_prefill_shared_object",
            "broadcast_shared_object_updated",
        ],
        "forbidden_operations": [
            "normal_extension_profile_write",
            "foreground_mouse_or_keyboard_input",
            "clipboard_write",
            "prompt_submit",
        ],
        "source_entrypoint": str(source / EXTENSION_ENTRYPOINT) if str(source) else "",
    }


def _scan_marker_evidence(extension_path: Path) -> tuple[dict, ...]:
    if not extension_path.is_dir():
        return ()
    files = [extension_path / EXTENSION_ENTRYPOINT]
    assets_dir = extension_path / "webview" / "assets"
    if assets_dir.is_dir():
        files.extend(sorted(assets_dir.glob("*.js")))
    evidence: list[dict] = []
    for file_path in files:
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        markers = tuple(marker for marker in WEBVIEW_ROUTE_MARKERS if marker in text)
        if markers:
            evidence.append(
                {
                    "path": str(file_path),
                    "markers": list(markers),
                    "size": file_path.stat().st_size,
                }
            )
        if set(WEBVIEW_ROUTE_MARKERS).issubset(_all_markers(evidence)):
            break
    return tuple(evidence)


def _all_markers(evidence: Iterable[dict]) -> set[str]:
    found: set[str] = set()
    for item in evidence:
        found.update(str(marker) for marker in item.get("markers", ()) or ())
    return found


def _read_extension_version(extension_path: Path) -> str:
    try:
        package = json.loads((extension_path / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(package.get("version", "") or "")


def _extension_fingerprint(path: Path) -> str:
    if not path.is_dir():
        return ""
    digest = hashlib.sha256()
    for item in (path / "package.json", path / EXTENSION_ENTRYPOINT):
        digest.update(str(item.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        if item.is_file():
            digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _normal_extension_roots() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".cursor" / "extensions",
        home / ".vscode" / "extensions",
    )


def _path_contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_child(parent: Path, child: Path) -> None:
    if not _path_contains(parent, child):
        raise ValueError("target_outside_isolated_extension_root")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-extension", default="")
    parser.add_argument("--isolated-extension-root", default=str(DEFAULT_ISOLATED_EXTENSION_ROOT))
    parser.add_argument("--installed-extension-root", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_codex_isolated_bridge_patch(
        source_extension_path=args.source_extension,
        isolated_extension_root=args.isolated_extension_root,
        apply=args.apply,
        overwrite=args.overwrite,
        installed_extension_roots=tuple(args.installed_extension_root or ()),
    )
    data = report.to_dict()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(
            "Codex isolated bridge patch: "
            f"decision={data['decision']} apply={str(data['apply']).lower()} "
            f"writes={data['write_attempts']} target={data['isolated_extension_path']}"
        )
        if data["error"]:
            print(f"Blocking: {data['error']}")
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
