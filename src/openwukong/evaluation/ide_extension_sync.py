"""Controlled sync/audit for the local OpenWukong IDE extension install."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterable

from openwukong.evaluation.ide_extension_readiness import (
    DEFAULT_EXTENSION_DIR,
    _default_installed_extension_roots,
    _find_installed_extensions,
    _read_package_json,
)


ProcessSnapshotProvider = Callable[[], Iterable[dict]]

_KEY_FILES = ("package.json", "README.md", "src/extension.js")
_IGNORED_COPY_NAMES = {"logs", ".git", ".vscode-test", "node_modules", "__pycache__"}


@dataclasses.dataclass(frozen=True)
class IDEExtensionSyncInstance:
    path: str
    root: str
    status: str
    stale: bool
    active_process_detected: bool
    source_fingerprint: str = ""
    installed_fingerprint: str = ""
    backup_path: str = ""
    changed: bool = False
    error: str = ""
    diagnostics: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "root": self.root,
            "status": self.status,
            "stale": self.stale,
            "active_process_detected": self.active_process_detected,
            "source_fingerprint": self.source_fingerprint,
            "installed_fingerprint": self.installed_fingerprint,
            "backup_path": self.backup_path,
            "changed": self.changed,
            "error": self.error,
            "diagnostics": dict(self.diagnostics),
        }


@dataclasses.dataclass(frozen=True)
class IDEExtensionSyncReport:
    extension_dir: str
    extension_name: str
    extension_publisher: str
    extension_version: str
    apply: bool
    allow_active_profile_update: bool
    install_if_missing: bool
    installed_roots: tuple[str, ...]
    active_processes: tuple[dict, ...]
    instances: tuple[IDEExtensionSyncInstance, ...]
    source_fingerprint: str = ""
    elapsed_ms: float = 0.0
    error: str = ""

    @property
    def mode(self) -> str:
        return "ide-extension-sync"

    @property
    def safety_mode(self) -> str:
        return "controlled_file_sync" if self.apply else "read_only"

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
    def write_attempts(self) -> int:
        return sum(1 for item in self.instances if item.changed)

    @property
    def backup_attempts(self) -> int:
        return sum(1 for item in self.instances if item.backup_path)

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if not self.extension_name or not self.extension_publisher:
            return "source_missing"
        if any(item.status == "apply_refused_active_process" for item in self.instances):
            return "apply_refused_active_process"
        if any(item.status == "failed" for item in self.instances):
            return "failed"
        if any(item.changed for item in self.instances):
            return "applied"
        if any(item.stale for item in self.instances):
            return "stale_install_detected"
        if self.instances:
            return "up_to_date"
        if self.install_if_missing:
            return "install_missing_available"
        return "no_installed_extension"

    @property
    def blocking_reason(self) -> str:
        mapping = {
            "failed": self.error or "ide_extension_sync_failed",
            "source_missing": "source_extension_package_missing",
            "apply_refused_active_process": "active_ide_process_detected",
            "stale_install_detected": "installed_extension_needs_controlled_update",
            "no_installed_extension": "extension_not_installed",
            "install_missing_available": "extension_install_requires_apply",
            "up_to_date": "",
            "applied": "",
        }
        return mapping.get(self.status, self.status)

    @property
    def safe_run_ok(self) -> bool:
        return self.status not in {"failed", "source_missing"}

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "control_allowed": self.control_allowed,
            "control_attempts": self.control_attempts,
            "window_input_attempts": self.window_input_attempts,
            "write_attempts": self.write_attempts,
            "backup_attempts": self.backup_attempts,
            "status": self.status,
            "blocking_reason": self.blocking_reason,
            "safe_run_ok": self.safe_run_ok,
            "extension_dir": self.extension_dir,
            "extension_name": self.extension_name,
            "extension_publisher": self.extension_publisher,
            "extension_version": self.extension_version,
            "source_fingerprint": self.source_fingerprint,
            "apply": self.apply,
            "allow_active_profile_update": self.allow_active_profile_update,
            "install_if_missing": self.install_if_missing,
            "installed_roots": list(self.installed_roots),
            "active_processes": [dict(item) for item in self.active_processes],
            "instances": [item.to_dict() for item in self.instances],
            "elapsed_ms": round(float(self.elapsed_ms or 0.0), 3),
            "error": self.error,
        }


def sync_ide_extension_install(
    *,
    extension_dir: str | Path = DEFAULT_EXTENSION_DIR,
    installed_extension_roots: Iterable[str | Path] | None = None,
    apply: bool = False,
    allow_active_profile_update: bool = False,
    install_if_missing: bool = False,
    backup_dir: str | Path = "logs/runtime/ide-extension-sync-backups",
    process_snapshot_provider: ProcessSnapshotProvider | None = None,
    timestamp: str | None = None,
) -> IDEExtensionSyncReport:
    started = time.perf_counter()
    source_dir = Path(extension_dir).expanduser()
    package = _read_package_json(source_dir / "package.json")
    extension_name = str(package.get("name", "") or "")
    extension_publisher = str(package.get("publisher", "") or "")
    extension_version = str(package.get("version", "") or "")
    roots = tuple(Path(root).expanduser() for root in (installed_extension_roots or _default_installed_extension_roots()))
    root_strings = tuple(str(root) for root in roots)
    source_fingerprint = _extension_fingerprint(source_dir)
    active_processes = tuple(_active_ide_processes(process_snapshot_provider))
    if not extension_name or not extension_publisher:
        return IDEExtensionSyncReport(
            extension_dir=str(source_dir),
            extension_name=extension_name,
            extension_publisher=extension_publisher,
            extension_version=extension_version,
            source_fingerprint=source_fingerprint,
            apply=bool(apply),
            allow_active_profile_update=bool(allow_active_profile_update),
            install_if_missing=bool(install_if_missing),
            installed_roots=root_strings,
            active_processes=active_processes,
            instances=(),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    installed = _find_installed_extensions(
        roots,
        extension_name=extension_name,
        extension_publisher=extension_publisher,
    )
    instance_inputs = list(installed)
    if not instance_inputs and install_if_missing and roots:
        root = roots[0]
        instance_inputs.append(
            {
                "path": str(root / _extension_folder_name(extension_publisher, extension_name, extension_version)),
                "install_missing": True,
            }
        )

    instances: list[IDEExtensionSyncInstance] = []
    for instance in instance_inputs:
        path = Path(str(instance.get("path", "") or "")).expanduser()
        root = _matching_root(path, roots)
        installed_fingerprint = _extension_fingerprint(path)
        diagnostics = {key: value for key, value in instance.items() if key != "path"}
        stale = bool(
            diagnostics.get("install_missing", False)
            or diagnostics.get("legacy_fixed_port_risk", False)
            or source_fingerprint != installed_fingerprint
        )
        active = _root_has_active_ide_process(root, active_processes)
        if not stale:
            instances.append(
                IDEExtensionSyncInstance(
                    path=str(path),
                    root=str(root),
                    status="up_to_date",
                    stale=False,
                    active_process_detected=active,
                    source_fingerprint=source_fingerprint,
                    installed_fingerprint=installed_fingerprint,
                    diagnostics=diagnostics,
                )
            )
            continue
        if not apply:
            instances.append(
                IDEExtensionSyncInstance(
                    path=str(path),
                    root=str(root),
                    status="stale_install_detected",
                    stale=True,
                    active_process_detected=active,
                    source_fingerprint=source_fingerprint,
                    installed_fingerprint=installed_fingerprint,
                    diagnostics=diagnostics,
                )
            )
            continue
        if active and not allow_active_profile_update:
            instances.append(
                IDEExtensionSyncInstance(
                    path=str(path),
                    root=str(root),
                    status="apply_refused_active_process",
                    stale=True,
                    active_process_detected=True,
                    source_fingerprint=source_fingerprint,
                    installed_fingerprint=installed_fingerprint,
                    error="active_ide_process_detected",
                    diagnostics=diagnostics,
                )
            )
            continue
        try:
            backup_path = _replace_installed_extension(
                source_dir=source_dir,
                destination=path,
                installed_root=root,
                extension_publisher=extension_publisher,
                extension_name=extension_name,
                backup_dir=Path(backup_dir),
                timestamp=timestamp,
            )
            new_fingerprint = _extension_fingerprint(path)
            instances.append(
                IDEExtensionSyncInstance(
                    path=str(path),
                    root=str(root),
                    status="applied",
                    stale=False,
                    active_process_detected=active,
                    source_fingerprint=source_fingerprint,
                    installed_fingerprint=new_fingerprint,
                    backup_path=str(backup_path) if backup_path else "",
                    changed=True,
                    diagnostics=diagnostics,
                )
            )
        except Exception as exc:
            instances.append(
                IDEExtensionSyncInstance(
                    path=str(path),
                    root=str(root),
                    status="failed",
                    stale=True,
                    active_process_detected=active,
                    source_fingerprint=source_fingerprint,
                    installed_fingerprint=installed_fingerprint,
                    error=str(exc) or exc.__class__.__name__,
                    diagnostics=diagnostics,
                )
            )

    return IDEExtensionSyncReport(
        extension_dir=str(source_dir),
        extension_name=extension_name,
        extension_publisher=extension_publisher,
        extension_version=extension_version,
        source_fingerprint=source_fingerprint,
        apply=bool(apply),
        allow_active_profile_update=bool(allow_active_profile_update),
        install_if_missing=bool(install_if_missing),
        installed_roots=root_strings,
        active_processes=active_processes,
        instances=tuple(instances),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _extension_fingerprint(path: Path) -> str:
    if not path.is_dir():
        return ""
    digest = hashlib.sha256()
    for name in _KEY_FILES:
        item = path / name
        digest.update(name.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        if item.is_file():
            digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _extension_folder_name(publisher: str, name: str, version: str) -> str:
    suffix = f"-{version}" if version else ""
    return f"{publisher}.{name}{suffix}"


def _matching_root(path: Path, roots: tuple[Path, ...]) -> Path:
    for root in roots:
        try:
            path.resolve().relative_to(root.resolve())
            return root
        except ValueError:
            continue
    return path.parent


def _active_ide_processes(provider: ProcessSnapshotProvider | None) -> tuple[dict, ...]:
    rows = provider() if provider else _default_process_snapshot()
    selected: list[dict] = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "") or row.get("process_name", "") or "")
        executable = str(row.get("executable_path", "") or row.get("path", "") or "")
        command_line = str(row.get("command_line", "") or "")
        if _process_is_cursor(name, executable, command_line) or _process_is_vscode(
            name,
            executable,
            command_line,
        ):
            selected.append(
                {
                    "pid": _safe_int(row.get("pid", row.get("process_id", 0))),
                    "name": name,
                    "executable_path": executable,
                    "command_line": _truncate_text(command_line, 240),
                }
            )
    return tuple(selected)


def _default_process_snapshot() -> tuple[dict, ...]:
    if not sys.platform.startswith("win"):
        return ()
    rows = _powershell_process_snapshot(_cim_process_snapshot_script())
    if rows:
        return rows
    return _powershell_process_snapshot(_get_process_snapshot_script())


def _powershell_process_snapshot(script: str) -> tuple[dict, ...]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3.0,
            check=False,
        )
    except Exception:
        return ()
    if completed.returncode != 0 or not completed.stdout.strip():
        return ()
    try:
        data = json.loads(completed.stdout)
    except ValueError:
        return ()
    if isinstance(data, dict):
        data = [data]
    return tuple(item for item in data if isinstance(item, dict))


def _cim_process_snapshot_script() -> str:
    return (
        "$rows = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match '^(Cursor|Code|Code - Insiders|VSCodium)\\.exe$' } | "
        "Select-Object @{Name='pid';Expression={$_.ProcessId}},"
        "@{Name='name';Expression={$_.Name}},"
        "@{Name='executable_path';Expression={$_.ExecutablePath}},"
        "@{Name='command_line';Expression={$_.CommandLine}}\n"
        "$rows | ConvertTo-Json -Compress"
    )


def _get_process_snapshot_script() -> str:
    return (
        "$rows = Get-Process | "
        "Where-Object { $_.ProcessName -match '^(Cursor|Code|Code - Insiders|VSCodium)$' } | "
        "Select-Object @{Name='pid';Expression={$_.Id}},"
        "@{Name='name';Expression={$_.ProcessName}},"
        "@{Name='executable_path';Expression={$_.Path}},"
        "@{Name='command_line';Expression={$_.Path}}\n"
        "$rows | ConvertTo-Json -Compress"
    )


def _root_has_active_ide_process(root: Path, processes: tuple[dict, ...]) -> bool:
    product = _root_product(root)
    if not product:
        return False
    for process in processes:
        name = str(process.get("name", "") or "")
        executable = str(process.get("executable_path", "") or "")
        command_line = str(process.get("command_line", "") or "")
        if product == "cursor" and _process_is_cursor(name, executable, command_line):
            return True
        if product == "vscode" and _process_is_vscode(name, executable, command_line):
            return True
    return False


def _root_product(root: Path) -> str:
    text = str(root).replace("\\", "/").casefold()
    if "/.cursor/extensions" in text or text.endswith("/.cursor/extensions"):
        return "cursor"
    if "/.vscode/extensions" in text or text.endswith("/.vscode/extensions"):
        return "vscode"
    return ""


def _process_is_cursor(name: str, executable: str, command_line: str) -> bool:
    name_text = str(name or "").strip().casefold()
    if name_text.removesuffix(".exe") == "cursor":
        return True
    text = f"{name} {executable} {command_line}".casefold()
    return "cursor.exe" in text or "/cursor/" in text.replace("\\", "/")


def _process_is_vscode(name: str, executable: str, command_line: str) -> bool:
    name_text = str(name or "").strip().casefold().removesuffix(".exe")
    if name_text in {"code", "code - insiders", "vscodium"}:
        return True
    text = f"{name} {executable} {command_line}".casefold()
    normalized = text.replace("\\", "/")
    return (
        "code.exe" in text
        or "code - insiders.exe" in text
        or "vscodium.exe" in text
        or "/microsoft vs code/" in normalized
        or "/vscodium/" in normalized
    )


def _replace_installed_extension(
    *,
    source_dir: Path,
    destination: Path,
    installed_root: Path,
    extension_publisher: str,
    extension_name: str,
    backup_dir: Path,
    timestamp: str | None,
) -> Path | None:
    source = source_dir.resolve()
    root = installed_root.resolve()
    target = destination.resolve()
    _require_child(root, target)
    expected_prefix = f"{extension_publisher}.{extension_name}".casefold()
    if not target.name.casefold().startswith(expected_prefix):
        raise ValueError("target_extension_identity_mismatch")
    backup_path: Path | None = None
    if target.exists():
        backup_root = backup_dir.resolve()
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_path = _unique_backup_path(
            backup_root / f"{target.name}.openwukong-backup-{timestamp or time.strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copytree(target, backup_path)
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=_copy_ignore)
    return backup_path


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _IGNORED_COPY_NAMES}


def _unique_backup_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}-{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("backup_path_exhausted")


def _require_child(parent: Path, child: Path) -> None:
    try:
        child.relative_to(parent)
    except ValueError as exc:
        raise ValueError("target_outside_installed_extension_root") from exc


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _truncate_text(value: str, limit: int) -> str:
    text = str(value or "")
    max_length = max(0, int(limit))
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[: max_length - 3] + "..."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    parser.add_argument("--installed-extension-root", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-active-profile-update", action="store_true")
    parser.add_argument("--install-if-missing", action="store_true")
    parser.add_argument("--backup-dir", default="logs/runtime/ide-extension-sync-backups")
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = sync_ide_extension_install(
        extension_dir=args.extension_dir,
        installed_extension_roots=tuple(args.installed_extension_root) or None,
        apply=args.apply,
        allow_active_profile_update=args.allow_active_profile_update,
        install_if_missing=args.install_if_missing,
        backup_dir=args.backup_dir,
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
            "IDE extension sync: "
            f"status={data['status']} apply={str(data['apply']).lower()} "
            f"writes={data['write_attempts']}"
        )
        if data["blocking_reason"]:
            print(f"Blocking: {data['blocking_reason']}")
    if args.apply and report.status not in {"applied", "up_to_date"}:
        return 1
    return 0 if report.safe_run_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
