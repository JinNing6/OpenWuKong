# -*- coding: utf-8 -*-
"""Dynamic Windows application identity resolution.

This module treats app launching as a target-resolution problem before it is a
process-start problem. It intentionally prefers exact identity signals and
blocks ambiguous same-priority candidates instead of launching a nearby product.
"""

from __future__ import annotations

import dataclasses
import base64
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class AppIdentity:
    app_id: str
    aliases: tuple[str, ...]
    exact_names: tuple[str, ...] = ()
    executable_names: tuple[str, ...] = ()
    excluded_name_fragments: tuple[str, ...] = ()
    strict_exact_match: bool = False

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "aliases": list(self.aliases),
            "exact_names": list(self.exact_names),
            "executable_names": list(self.executable_names),
            "excluded_name_fragments": list(self.excluded_name_fragments),
            "strict_exact_match": self.strict_exact_match,
        }


@dataclasses.dataclass(frozen=True)
class AppResolutionCandidate:
    source: str
    display_name: str = ""
    path: str = ""
    executable_name: str = ""
    process_name: str = ""
    pid: int = 0
    metadata: dict = dataclasses.field(default_factory=dict)

    @property
    def already_running(self) -> bool:
        return self.source == "running-process" or int(self.pid or 0) > 0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "display_name": self.display_name,
            "path": self.path,
            "executable_name": self.executable_name,
            "process_name": self.process_name,
            "pid": int(self.pid or 0),
            "already_running": self.already_running,
            "metadata": dict(self.metadata),
        }


@dataclasses.dataclass(frozen=True)
class AppResolutionReport:
    app_name: str
    identity: AppIdentity
    ok: bool
    decision: str
    selected_candidate: AppResolutionCandidate | None = None
    candidates: tuple[AppResolutionCandidate, ...] = ()
    error: str = ""

    @property
    def mode(self) -> str:
        return "app-resolution"

    @property
    def path(self) -> str:
        return self.selected_candidate.path if self.selected_candidate else ""

    @property
    def source(self) -> str:
        return self.selected_candidate.source if self.selected_candidate else ""

    @property
    def already_running(self) -> bool:
        return bool(self.selected_candidate and self.selected_candidate.already_running)

    @property
    def pid(self) -> int:
        return int(self.selected_candidate.pid or 0) if self.selected_candidate else 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "decision": self.decision,
            "app_name": self.app_name,
            "app_id": self.identity.app_id,
            "identity": self.identity.to_dict(),
            "path": self.path,
            "source": self.source,
            "already_running": self.already_running,
            "pid": self.pid,
            "selected_candidate": (
                self.selected_candidate.to_dict() if self.selected_candidate else {}
            ),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "error": self.error,
        }


@dataclasses.dataclass(frozen=True)
class AppPathVerification:
    path: str
    ok: bool
    status: str
    exists: bool = False
    is_file: bool = False
    size: int = 0
    mtime_ns: int = 0
    executable_name: str = ""
    expected_executable_names: tuple[str, ...] = ()
    signature_status: str = ""
    signature_subject: str = ""
    signature_issuer: str = ""
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "status": self.status,
            "exists": self.exists,
            "is_file": self.is_file,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "executable_name": self.executable_name,
            "expected_executable_names": list(self.expected_executable_names),
            "signature_status": self.signature_status,
            "signature_subject": self.signature_subject,
            "signature_issuer": self.signature_issuer,
            "errors": list(self.errors),
        }


class PowerShellAuthenticodeSignatureReader:
    def __call__(self, path: str) -> dict:
        if os.name != "nt":
            return {}
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$sig = Get-AuthenticodeSignature -LiteralPath $args[0]; "
                "[pscustomobject]@{"
                "Status=[string]$sig.Status;"
                "Subject=[string]$sig.SignerCertificate.Subject;"
                "Issuer=[string]$sig.SignerCertificate.Issuer"
                "} | ConvertTo-Json -Compress"
            ),
            path,
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return {}
        if completed.returncode != 0 or not completed.stdout.strip():
            return {}
        try:
            payload = json.loads(completed.stdout)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            "status": str(payload.get("Status", "") or ""),
            "subject": str(payload.get("Subject", "") or ""),
            "issuer": str(payload.get("Issuer", "") or ""),
        }


class AppPathVerifier:
    def __init__(
        self,
        *,
        signature_reader: object | None = None,
        verify_signature: bool = False,
    ):
        self.signature_reader = (
            signature_reader
            if signature_reader is not None
            else PowerShellAuthenticodeSignatureReader() if verify_signature else None
        )

    def verify_path(
        self,
        path: str,
        *,
        expected_executable_names: tuple[str, ...] = (),
        cached_verification: dict | None = None,
    ) -> AppPathVerification:
        path_text = str(path or "").strip()
        candidate_path = Path(path_text) if path_text else Path()
        errors: list[str] = []
        exists = bool(path_text) and candidate_path.exists()
        is_file = exists and candidate_path.is_file()
        size = 0
        mtime_ns = 0
        executable_name = candidate_path.name if path_text else ""
        if not path_text:
            errors.append("empty_path")
        elif not exists:
            errors.append("path_not_found")
        elif not is_file:
            errors.append("path_not_file")
        else:
            stat = candidate_path.stat()
            size = int(stat.st_size)
            mtime_ns = int(stat.st_mtime_ns)
        expected = tuple(str(item or "") for item in expected_executable_names if str(item or "").strip())
        expected_lower = {lower_text(item) for item in expected}
        if (
            expected_lower
            and candidate_path.suffix.lower() == ".exe"
            and lower_text(executable_name) not in expected_lower
        ):
            errors.append("unexpected_executable_name")
        if isinstance(cached_verification, dict):
            cached_size = _optional_int(cached_verification.get("size"))
            cached_mtime = _optional_int(cached_verification.get("mtime_ns"))
            cached_name = str(cached_verification.get("executable_name", "") or "")
            if cached_size is not None and size and cached_size != size:
                errors.append("cached_size_mismatch")
            if cached_mtime is not None and mtime_ns and cached_mtime != mtime_ns:
                errors.append("cached_mtime_mismatch")
            if cached_name and executable_name and lower_text(cached_name) != lower_text(executable_name):
                errors.append("cached_executable_name_mismatch")
        signature_status = ""
        signature_subject = ""
        signature_issuer = ""
        if is_file and callable(self.signature_reader):
            try:
                signature = self.signature_reader(str(candidate_path))
            except Exception:
                signature = {}
            if isinstance(signature, dict):
                signature_status = str(signature.get("status", "") or signature.get("Status", "") or "")
                signature_subject = str(signature.get("subject", "") or signature.get("Subject", "") or "")
                signature_issuer = str(signature.get("issuer", "") or signature.get("Issuer", "") or "")
        ok = not errors
        return AppPathVerification(
            path=path_text,
            ok=ok,
            status="verified" if ok else "invalid",
            exists=exists,
            is_file=is_file,
            size=size,
            mtime_ns=mtime_ns,
            executable_name=executable_name,
            expected_executable_names=expected,
            signature_status=signature_status,
            signature_subject=signature_subject,
            signature_issuer=signature_issuer,
            errors=tuple(errors),
        )


class AppIdentityRegistry:
    def __init__(self, identities: tuple[AppIdentity, ...] = ()):
        self._identities = tuple(identities) or default_app_identities()

    def identity_for(self, app_name: str) -> AppIdentity:
        key = normalize_app_name(app_name)
        for identity in self._identities:
            values = {
                normalize_app_name(identity.app_id),
                *(normalize_app_name(item) for item in identity.aliases),
            }
            if key in values:
                return identity
        return AppIdentity(
            app_id=key or "unknown",
            aliases=(key,) if key else (),
            exact_names=(str(app_name or "").strip(),) if str(app_name or "").strip() else (),
            strict_exact_match=False,
        )


class StaticAppCandidateProvider:
    def __init__(
        self,
        candidates: tuple[AppResolutionCandidate, ...] | list[AppResolutionCandidate],
    ):
        self._candidates = tuple(candidates)

    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name, identity
        return self._candidates


class WindowsRunningProcessCandidateProvider:
    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name
        try:
            import psutil
        except Exception:
            return ()
        items: list[AppResolutionCandidate] = []
        executable_names = {lower_text(item) for item in identity.executable_names}
        if not executable_names:
            return ()
        for process in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = str(process.info.get("name", "") or "")
                exe = str(process.info.get("exe", "") or "")
                pid = int(process.info.get("pid", 0) or 0)
            except Exception:
                continue
            if lower_text(name) not in executable_names:
                continue
            items.append(
                AppResolutionCandidate(
                    source="running-process",
                    display_name=name,
                    path=exe,
                    executable_name=Path(exe).name if exe else name,
                    process_name=name,
                    pid=pid,
                )
            )
        return tuple(items)


class LocalCacheAppCandidateProvider:
    def __init__(self, cache_path: str | Path, *, verifier: AppPathVerifier | None = None):
        self.cache_path = Path(cache_path) if str(cache_path or "").strip() else None
        self.verifier = verifier or AppPathVerifier()

    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        if self.cache_path is None or not self.cache_path.is_file():
            return ()
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return ()
        apps = payload.get("apps") if isinstance(payload, dict) else {}
        if not isinstance(apps, dict):
            return ()
        entry = apps.get(identity.app_id) or apps.get(normalize_app_name(app_name))
        if not isinstance(entry, dict):
            return ()
        path = str(entry.get("path", "") or "").strip()
        if not path:
            return ()
        cached_verification = entry.get("verification")
        verification = self.verifier.verify_path(
            path,
            expected_executable_names=identity.executable_names,
            cached_verification=cached_verification if isinstance(cached_verification, dict) else None,
        )
        if not verification.ok:
            return ()
        return (
            AppResolutionCandidate(
                source="local-cache",
                display_name=str(entry.get("display_name", "") or identity.app_id),
                path=path,
                executable_name=str(entry.get("executable_name", "") or Path(path).name),
                metadata={
                    "cache_path": str(self.cache_path),
                    "cache_verification": verification.to_dict(),
                },
            ),
        )


class StartMenuAppCandidateProvider:
    def __init__(
        self,
        roots: tuple[str | Path, ...] = (),
        *,
        shortcut_target_resolver: object | None = None,
    ):
        self.roots = tuple(Path(root) for root in roots) or default_start_menu_roots()
        self.shortcut_target_resolver = (
            shortcut_target_resolver
            if shortcut_target_resolver is not None
            else WindowsShortcutTargetResolver()
        )

    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name
        items: list[AppResolutionCandidate] = []
        for root in self.roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_dir():
                    continue
                if path.suffix.lower() not in {".lnk", ".url", ".exe"}:
                    continue
                resolved = self._resolved_shortcut_candidate(path, identity)
                if resolved is not None:
                    items.append(resolved)
                    continue
                items.append(
                    AppResolutionCandidate(
                        source="start-menu",
                        display_name=path.stem,
                        path=str(path),
                        executable_name=path.name if path.suffix.lower() == ".exe" else "",
                    )
                )
        return tuple(items)

    def _resolved_shortcut_candidate(
        self,
        path: Path,
        identity: AppIdentity,
    ) -> AppResolutionCandidate | None:
        if path.suffix.lower() != ".lnk":
            return None
        if not _start_menu_name_matches_identity(path.stem, identity):
            return None
        resolver = self.shortcut_target_resolver
        if not callable(resolver):
            return None
        try:
            shortcut = resolver(str(path))
        except Exception:
            return None
        if not isinstance(shortcut, dict):
            return None
        target_path = str(
            shortcut.get("target_path", "") or shortcut.get("TargetPath", "") or ""
        ).strip()
        if not target_path or Path(target_path).suffix.lower() != ".exe":
            return None
        return AppResolutionCandidate(
            source="start-menu",
            display_name=path.stem,
            path=target_path,
            executable_name=Path(target_path).name,
            metadata={
                "shortcut_path": str(path),
                "shortcut_arguments": str(
                    shortcut.get("arguments", "") or shortcut.get("Arguments", "") or ""
                ),
                "shortcut_working_directory": str(
                    shortcut.get("working_directory", "")
                    or shortcut.get("WorkingDirectory", "")
                    or ""
                ),
            },
        )


class WindowsShortcutTargetResolver:
    def __init__(self, *, command_runner: object | None = None, timeout_sec: float = 5.0):
        self.command_runner = command_runner
        self.timeout_sec = float(timeout_sec)

    def __call__(self, path: str) -> dict:
        if os.name != "nt":
            return {}
        path_b64 = base64.b64encode(str(path or "").encode("utf-8")).decode("ascii")
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                f"$path = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{path_b64}')); "
                "$shell = New-Object -ComObject WScript.Shell; "
                "$shortcut = $shell.CreateShortcut($path); "
                "[pscustomobject]@{"
                "target_path=[string]$shortcut.TargetPath;"
                "arguments=[string]$shortcut.Arguments;"
                "working_directory=[string]$shortcut.WorkingDirectory"
                "} | ConvertTo-Json -Compress"
            ),
        ]
        try:
            if callable(self.command_runner):
                completed = self.command_runner(command)
            else:
                completed = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=False,
                    timeout=self.timeout_sec,
                    check=False,
                )
        except Exception:
            return {}
        if completed.returncode != 0:
            return {}
        stdout = _decode_command_output(getattr(completed, "stdout", b"")).strip()
        if not stdout:
            return {}
        try:
            payload = json.loads(stdout)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}


class WindowsStartAppsCandidateProvider:
    def __init__(
        self,
        *,
        command_runner: object | None = None,
        timeout_sec: float = 5.0,
    ):
        self.command_runner = command_runner
        self.timeout_sec = float(timeout_sec)

    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name, identity
        if os.name != "nt" and self.command_runner is None:
            return ()
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
            ),
        ]
        completed = self._run_command(command)
        if getattr(completed, "returncode", 1) != 0:
            return ()
        stdout = _decode_command_output(getattr(completed, "stdout", b"")).strip()
        if not stdout:
            return ()
        try:
            payload = json.loads(stdout)
        except Exception:
            return ()
        rows = payload if isinstance(payload, list) else [payload]
        items: list[AppResolutionCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("Name", "") or "").strip()
            app_id = str(row.get("AppID", "") or row.get("AppId", "") or "").strip()
            if not name or not app_id:
                continue
            items.append(
                AppResolutionCandidate(
                    source="start-apps",
                    display_name=name,
                    metadata={"app_id": app_id},
                )
            )
        return tuple(items)

    def _run_command(self, command: list[str]) -> object:
        if callable(self.command_runner):
            return self.command_runner(command)
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=self.timeout_sec,
            check=False,
        )


class AppPathsRegistryCandidateProvider:
    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name
        if os.name != "nt":
            return ()
        try:
            import winreg
        except Exception:
            return ()
        roots = (
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
        )
        items: list[AppResolutionCandidate] = []
        for executable in identity.executable_names:
            for hive, base_key in roots:
                key_path = base_key + "\\" + executable
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        value, _value_type = winreg.QueryValueEx(key, "")
                except OSError:
                    continue
                path = str(value or "").strip()
                if not path:
                    continue
                items.append(
                    AppResolutionCandidate(
                        source="app-paths-registry",
                        display_name=Path(path).stem,
                        path=path,
                        executable_name=Path(path).name,
                        metadata={"registry_key": key_path},
                    )
                )
        return tuple(items)


class PathExecutableCandidateProvider:
    def candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        del app_name
        items: list[AppResolutionCandidate] = []
        for executable in identity.executable_names:
            found = shutil.which(executable)
            if not found:
                continue
            items.append(
                AppResolutionCandidate(
                    source="path",
                    display_name=Path(found).stem,
                    path=found,
                    executable_name=Path(found).name,
                )
            )
        return tuple(items)


class WindowsAppResolver:
    def __init__(
        self,
        *,
        identity_registry: AppIdentityRegistry | None = None,
        candidate_providers: tuple[object, ...] | None = None,
        start_menu_roots: tuple[str | Path, ...] = (),
        cache_path: str | Path = "",
        cache_write_enabled: bool = False,
        path_verifier: AppPathVerifier | None = None,
    ):
        self.identity_registry = identity_registry or AppIdentityRegistry()
        self.cache_path = Path(cache_path) if str(cache_path or "").strip() else None
        self.cache_write_enabled = bool(cache_write_enabled)
        self.path_verifier = path_verifier or AppPathVerifier()
        self.candidate_providers = (
            candidate_providers
            if candidate_providers is not None
            else (
                WindowsRunningProcessCandidateProvider(),
                StartMenuAppCandidateProvider(start_menu_roots),
                WindowsStartAppsCandidateProvider(),
                AppPathsRegistryCandidateProvider(),
                PathExecutableCandidateProvider(),
            )
        )

    def resolve(self, app_name: str) -> AppResolutionReport:
        name = str(app_name or "").strip()
        identity = self.identity_registry.identity_for(name)
        candidates = self._collect_candidates(name, identity)
        matched = tuple(
            candidate
            for candidate in candidates
            if candidate_matches_identity(candidate, identity)
        )
        deduped = _prefer_requested_agent_surface_candidates(
            name,
            identity,
            dedupe_candidates(matched),
        )
        if not deduped:
            return AppResolutionReport(
                app_name=name,
                identity=identity,
                ok=False,
                decision="not_found",
                candidates=tuple(candidates),
                error="app_not_found",
            )
        ranked = sorted(
            deduped,
            key=lambda candidate: (
                candidate_selection_priority(candidate),
                -candidate_score(candidate, identity),
                candidate_key(candidate),
            ),
        )
        best = ranked[0]
        ties = [
            candidate
            for candidate in ranked
            if candidate_selection_priority(candidate) == candidate_selection_priority(best)
            and candidate_score(candidate, identity) == candidate_score(best, identity)
            and candidate_unique_value(candidate) != candidate_unique_value(best)
        ]
        if ties:
            return AppResolutionReport(
                app_name=name,
                identity=identity,
                ok=False,
                decision="ambiguous",
                candidates=tuple([best, *ties]),
                error="ambiguous_app_candidates",
            )
        report = AppResolutionReport(
            app_name=name,
            identity=identity,
            ok=True,
            decision="resolved",
            selected_candidate=best,
            candidates=tuple(ranked),
        )
        self._write_cache_if_enabled(report)
        return report

    def _collect_candidates(
        self,
        app_name: str,
        identity: AppIdentity,
    ) -> tuple[AppResolutionCandidate, ...]:
        items: list[AppResolutionCandidate] = []
        if self.cache_path is not None:
            items.extend(
                LocalCacheAppCandidateProvider(
                    self.cache_path,
                    verifier=self.path_verifier,
                ).candidates(app_name, identity)
            )
        for provider in self.candidate_providers:
            getter = getattr(provider, "candidates", None)
            if not callable(getter):
                continue
            try:
                items.extend(tuple(getter(app_name, identity)))
            except Exception:
                continue
        return tuple(items)

    def _write_cache_if_enabled(self, report: AppResolutionReport) -> None:
        candidate = report.selected_candidate
        if not self.cache_write_enabled or self.cache_path is None or candidate is None:
            return
        if candidate.source == "local-cache" or not candidate.path:
            return
        if candidate_score(candidate, report.identity) < 900:
            return
        verification = self.path_verifier.verify_path(
            candidate.path,
            expected_executable_names=report.identity.executable_names,
        )
        if not verification.ok:
            return
        payload = _read_cache_payload(self.cache_path)
        apps = payload.setdefault("apps", {})
        if not isinstance(apps, dict):
            apps = {}
            payload["apps"] = apps
        apps[report.identity.app_id] = {
            "path": candidate.path,
            "display_name": candidate.display_name or report.identity.app_id,
            "executable_name": candidate.executable_name or Path(candidate.path).name,
            "source": candidate.source,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "verification": verification.to_dict(),
        }
        _write_cache_payload(self.cache_path, payload)


def default_app_identities() -> tuple[AppIdentity, ...]:
    return (
        AppIdentity(
            app_id="wechat",
            aliases=("wechat", "weixin", "\u5fae\u4fe1"),
            exact_names=("\u5fae\u4fe1", "wechat", "weixin"),
            executable_names=("Weixin.exe", "WeChat.exe"),
            excluded_name_fragments=(
                "\u4f01\u4e1a\u5fae\u4fe1",
                "\u5fae\u4fe1\u8f93\u5165\u6cd5",
                "wecom",
                "wxwork",
                "workwechat",
            ),
            strict_exact_match=True,
        ),
        AppIdentity(
            app_id="cursor",
            aliases=("cursor",),
            exact_names=("Cursor",),
            executable_names=("Cursor.exe",),
        ),
        AppIdentity(
            app_id="codex",
            aliases=(
                "codex",
                "openai codex",
                "codex cli",
                "codex app",
                "openai codex app",
                "codex desktop",
                "codex desktop app",
                "codex ide",
            ),
            exact_names=("Codex", "OpenAI Codex", "Codex CLI", "Codex App", "Codex Desktop"),
            executable_names=("Codex.exe", "codex.exe", "codex.cmd", "codex.bat", "codex"),
        ),
        AppIdentity(
            app_id="claude",
            aliases=(
                "claude",
                "claude code",
                "anthropic claude",
                "claude cli",
                "claude app",
                "claude desktop",
                "claude desktop app",
                "claude code desktop",
                "claude code app",
            ),
            exact_names=("Claude", "Claude Code", "Anthropic Claude", "Claude Desktop"),
            executable_names=("Claude.exe", "claude.exe", "claude.cmd", "claude.bat", "claude"),
        ),
        AppIdentity(
            app_id="chrome",
            aliases=("chrome", "googlechrome", "google chrome", "\u8c37\u6b4c\u6d4f\u89c8\u5668", "browser"),
            exact_names=("Google Chrome", "Chrome", "\u8c37\u6b4c\u6d4f\u89c8\u5668"),
            executable_names=("chrome.exe",),
        ),
        AppIdentity(
            app_id="edge",
            aliases=("edge", "microsoftedge", "microsoft edge"),
            exact_names=("Microsoft Edge", "Edge"),
            executable_names=("msedge.exe",),
        ),
    )


def candidate_matches_identity(candidate: AppResolutionCandidate, identity: AppIdentity) -> bool:
    names = candidate_names(candidate)
    lower_executables = {lower_text(item) for item in identity.executable_names}
    if candidate_excluded(candidate, identity):
        return False
    if lower_executables and (
        lower_text(candidate.process_name) in lower_executables
        or lower_text(candidate.executable_name) in lower_executables
        or lower_text(Path(candidate.path).name) in lower_executables
    ):
        return True
    exact = {
        normalize_app_name(item)
        for item in (*identity.exact_names, *identity.aliases)
        if normalize_app_name(item)
    }
    if any(name in exact for name in names):
        return True
    if identity.strict_exact_match:
        return False
    return False


def _start_menu_name_matches_identity(name: str, identity: AppIdentity) -> bool:
    normalized = normalize_app_name(name)
    if not normalized:
        return False
    accepted = {
        normalize_app_name(item)
        for item in (*identity.exact_names, *identity.aliases)
        if normalize_app_name(item)
    }
    return normalized in accepted


def requested_agent_surface_kind(app_name: str, identity: AppIdentity) -> str:
    if identity.app_id not in {"claude", "codex"}:
        return ""
    normalized = " ".join(str(app_name or "").replace("-", " ").lower().split())
    tokens = set(normalized.split())
    if "cli" in tokens:
        return "cli"
    if tokens & {"app", "desktop"}:
        return "desktop"
    if identity.app_id == "claude" and "code" in tokens:
        return "cli"
    return ""


def codex_candidate_surface_kind(candidate: AppResolutionCandidate) -> str:
    path_text = _normalized_candidate_path(candidate.path)
    exe = _candidate_file_name(candidate)
    exe_lower = lower_text(exe)
    name = normalize_app_name(candidate.display_name)
    if exe_lower in {"codex.cmd", "codex.bat", "codex"}:
        return "cli"
    if exe_lower == "codex.exe" and (
        "/.local/bin/" in path_text
        or "/appdata/roaming/npm/" in path_text
        or "/extensions/" in path_text
        or "/resources/" in path_text
    ):
        return "cli"
    if exe == "Codex.exe":
        return "desktop"
    if candidate.source in {"start-apps", "start-menu"} and name in {
        "codex",
        "openaicodex",
        "codexapp",
        "codexdesktop",
    }:
        return "desktop"
    return ""


def claude_candidate_surface_kind(candidate: AppResolutionCandidate) -> str:
    path_text = _normalized_candidate_path(candidate.path)
    exe = lower_text(_candidate_file_name(candidate))
    name = normalize_app_name(candidate.display_name)
    if exe in {"claude.cmd", "claude.bat", "claude"}:
        return "cli"
    if exe == "claude.exe" and (
        "/.local/bin/" in path_text
        or "/appdata/roaming/npm/" in path_text
    ):
        return "cli"
    if candidate.source == "start-apps" and name in {"claude", "claudedesktop", "anthropicclaude"}:
        return "desktop"
    if candidate.source == "start-menu" and name in {"claude", "claudedesktop", "anthropicclaude"}:
        return "desktop"
    if exe == "claude.exe" and (
        "/program files/windowsapps/claude_" in path_text
        or "/programs/claude/" in path_text
        or "/anthropic/" in path_text
        or "/anthropicclaude/" in path_text
    ):
        return "desktop"
    if candidate.source == "path" and exe == "claude.exe":
        return "cli"
    return ""


def _prefer_requested_agent_surface_candidates(
    app_name: str,
    identity: AppIdentity,
    candidates: tuple[AppResolutionCandidate, ...],
) -> tuple[AppResolutionCandidate, ...]:
    requested_surface = requested_agent_surface_kind(app_name, identity)
    if identity.app_id == "codex" and requested_surface:
        return tuple(
            candidate
            for candidate in candidates
            if codex_candidate_surface_kind(candidate) == requested_surface
        )
    if identity.app_id == "claude" and requested_surface:
        preferred = tuple(
            candidate
            for candidate in candidates
            if claude_candidate_surface_kind(candidate) == requested_surface
        )
        return preferred
    return candidates


def candidate_score(candidate: AppResolutionCandidate, identity: AppIdentity) -> int:
    if candidate.already_running:
        raw_executable_names = tuple(str(item or "").strip() for item in identity.executable_names if str(item or "").strip())
        primary_executable_name = raw_executable_names[0] if raw_executable_names else ""
        raw_candidate_executable_names = {
            str(candidate.process_name or "").strip(),
            str(candidate.executable_name or "").strip(),
            Path(candidate.path).name if candidate.path else "",
        }
        if primary_executable_name and primary_executable_name in raw_candidate_executable_names:
            return 1000
        executable_names = tuple(lower_text(item) for item in raw_executable_names)
        candidate_executable_names = {
            lower_text(candidate.process_name),
            lower_text(candidate.executable_name),
            lower_text(Path(candidate.path).name),
        }
        if executable_names and candidate_executable_names & set(executable_names):
            return 980
        return 960
    names = candidate_names(candidate)
    exact = {normalize_app_name(item) for item in identity.exact_names if normalize_app_name(item)}
    aliases = {normalize_app_name(item) for item in identity.aliases if normalize_app_name(item)}
    executable_names = {lower_text(item) for item in identity.executable_names if lower_text(item)}
    if lower_text(candidate.executable_name) in executable_names or lower_text(Path(candidate.path).name) in executable_names:
        return 950
    if names & exact:
        return 900
    if names & aliases:
        return 800
    return 100


def candidate_excluded(candidate: AppResolutionCandidate, identity: AppIdentity) -> bool:
    haystack = " ".join(
        item
        for item in (
            candidate.display_name,
            candidate.executable_name,
            candidate.process_name,
            Path(candidate.path).stem if candidate.path else "",
            str(candidate.path or ""),
        )
        if item
    ).lower()
    return any(str(fragment or "").lower() in haystack for fragment in identity.excluded_name_fragments)


def candidate_names(candidate: AppResolutionCandidate) -> set[str]:
    names = {
        normalize_app_name(candidate.display_name),
        normalize_app_name(candidate.executable_name),
        normalize_app_name(Path(candidate.executable_name).stem if candidate.executable_name else ""),
        normalize_app_name(candidate.process_name),
        normalize_app_name(Path(candidate.process_name).stem if candidate.process_name else ""),
    }
    if candidate.path:
        path = Path(candidate.path)
        names.add(normalize_app_name(path.stem))
        names.add(normalize_app_name(path.name))
    return {name for name in names if name}


def dedupe_candidates(
    candidates: tuple[AppResolutionCandidate, ...],
) -> tuple[AppResolutionCandidate, ...]:
    deduped: list[AppResolutionCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate_unique_value(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return tuple(deduped)


def source_priority(source: str) -> int:
    order = {
        "running-process": 0,
        "local-cache": 1,
        "start-apps": 2,
        "start-menu": 3,
        "app-paths-registry": 4,
        "path": 5,
    }
    return order.get(str(source or ""), 99)


def candidate_selection_priority(candidate: AppResolutionCandidate) -> int:
    if candidate.source == "start-apps" and not str(candidate.path or "").strip():
        return 98
    return source_priority(candidate.source)


def candidate_unique_value(candidate: AppResolutionCandidate) -> str:
    if candidate.path:
        return str(Path(candidate.path).as_posix()).lower()
    if candidate.already_running:
        return f"pid:{int(candidate.pid or 0)}:{lower_text(candidate.process_name)}"
    return candidate_key(candidate)


def candidate_key(candidate: AppResolutionCandidate) -> str:
    return "|".join(
        [
            str(source_priority(candidate.source)),
            lower_text(candidate.source),
            lower_text(candidate.display_name),
            lower_text(candidate.path),
            lower_text(candidate.executable_name),
            lower_text(candidate.process_name),
            str(int(candidate.pid or 0)),
        ]
    )


def default_start_menu_roots() -> tuple[Path, ...]:
    roots = [
        Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return tuple(roots)


def _read_cache_payload(cache_path: Path) -> dict:
    if cache_path.is_file():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            payload.setdefault("version", 1)
            return payload
    return {"version": 1, "apps": {}}


def _write_cache_payload(cache_path: Path, payload: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload["version"] = 1
    tmp_path = cache_path.with_name(cache_path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(cache_path)


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _decode_command_output(value: object) -> str:
    if isinstance(value, bytes):
        for encoding in ("utf-8-sig", "utf-16", "mbcs"):
            try:
                return value.decode(encoding)
            except Exception:
                continue
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def normalize_app_name(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if not ch.isspace())


def lower_text(value: str) -> str:
    return str(value or "").strip().lower()


def _candidate_file_name(candidate: AppResolutionCandidate) -> str:
    for value in (
        candidate.executable_name,
        Path(candidate.path).name if candidate.path else "",
        candidate.process_name,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalized_candidate_path(value: str) -> str:
    return str(value or "").replace("\\", "/").lower()


__all__ = [
    "AppIdentity",
    "AppIdentityRegistry",
    "AppPathsRegistryCandidateProvider",
    "AppPathVerification",
    "AppPathVerifier",
    "AppResolutionCandidate",
    "AppResolutionReport",
    "LocalCacheAppCandidateProvider",
    "PathExecutableCandidateProvider",
    "PowerShellAuthenticodeSignatureReader",
    "StartMenuAppCandidateProvider",
    "StaticAppCandidateProvider",
    "WindowsStartAppsCandidateProvider",
    "WindowsAppResolver",
    "WindowsRunningProcessCandidateProvider",
    "WindowsShortcutTargetResolver",
    "candidate_excluded",
    "claude_candidate_surface_kind",
    "candidate_key",
    "candidate_matches_identity",
    "candidate_names",
    "candidate_score",
    "candidate_selection_priority",
    "candidate_unique_value",
    "codex_candidate_surface_kind",
    "dedupe_candidates",
    "default_app_identities",
    "default_start_menu_roots",
    "lower_text",
    "normalize_app_name",
    "requested_agent_surface_kind",
    "source_priority",
]
