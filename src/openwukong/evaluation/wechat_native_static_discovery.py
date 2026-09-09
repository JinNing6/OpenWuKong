# -*- coding: utf-8 -*-
"""Read-only static discovery for possible WeChat native IPC/helper surfaces.

The probe scans Weixin/WeChat binaries and helper manifests without launching
apps, attaching debuggers, sending messages, or calling internal IPC. Static
signals such as DLL names, exports, or strings are reported as evidence only;
they are not promoted into a send-capable backend without a real send contract.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path
from typing import Optional


_WECHAT_PROCESS_NAMES = ("weixin.exe", "wechatappex.exe")
_CANDIDATE_SUFFIXES = (".dll", ".exe")
_CANDIDATE_NAME_HINTS = (
    "weixin",
    "wechat",
    "wx",
    "ilink",
    "mojo",
    "xnet",
    "mars",
    "wmpf",
    "wcprobe",
    "xplugin",
    "ipc",
    "bridge",
    "helper",
)
_STATIC_KEYWORDS = (
    "send",
    "message",
    "chat",
    "conversation",
    "filehelper",
    "file transfer",
    "mojo",
    "ilink",
    "ipc",
    "pipe",
    "localhost",
    "127.0.0.1",
    "wechat",
    "weixin",
    "xwechat",
    "wxid",
    "openapi",
    "sdk",
    "capabilities",
)
_DOCUMENTED_HELPER_MANIFEST_NAMES = (
    "openwukong-wechat-native-helper.json",
    "wechat-native-helper.openwukong.json",
)
_MAX_HASH_BYTES = 64 * 1024 * 1024
_MAX_PE_PARSE_BYTES = 256 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class WeChatNativeStaticDiscoveryReport:
    install_dirs: tuple[str, ...]
    scanned_files: tuple[dict, ...]
    helper_manifests: tuple[dict, ...]
    discovered_install_dirs: tuple[str, ...] = ()
    explicit_install_dirs: tuple[str, ...] = ()
    max_files: int = 0
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def mode(self) -> str:
        return "wechat-native-static-discovery"

    @property
    def safety_mode(self) -> str:
        return "read_only_static_scan"

    @property
    def ok(self) -> bool:
        return self.decision == "documented_wechat_native_helper_contract_found"

    @property
    def decision(self) -> str:
        if self.error:
            return "wechat_native_static_discovery_failed"
        if any(_helper_manifest_send_ready(item) for item in self.helper_manifests):
            return "documented_wechat_native_helper_contract_found"
        if not self.install_dirs:
            return "weixin_install_not_found"
        if _has_static_ipc_or_send_signal(self.scanned_files):
            return "weixin_static_surfaces_found_without_send_contract"
        if self.scanned_files:
            return "weixin_binaries_found_without_native_send_surface"
        return "weixin_install_dirs_found_without_candidate_binaries"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "safety_mode": self.safety_mode,
            "ok": self.ok,
            "decision": self.decision,
            "control_allowed": False,
            "control_attempts": 0,
            "native_call_attempts": 0,
            "send_attempts": 0,
            "window_input_attempts": 0,
            "keyboard_input_attempts": 0,
            "clipboard_write_attempts": 0,
            "install_dirs": list(self.install_dirs),
            "explicit_install_dirs": list(self.explicit_install_dirs),
            "discovered_install_dirs": list(self.discovered_install_dirs),
            "scanned_file_count": len(self.scanned_files),
            "scanned_files": [dict(item) for item in self.scanned_files],
            "helper_manifests": [dict(item) for item in self.helper_manifests],
            "static_signal_summary": _static_signal_summary(self.scanned_files),
            "max_files": int(self.max_files or 0),
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


def run_wechat_native_static_discovery(
    *,
    install_dirs: tuple[str, ...] = (),
    recursive_depth: int = 1,
    max_files: int = 160,
    max_export_names: int = 240,
    max_keyword_bytes: int = 16 * 1024 * 1024,
    process_snapshot: tuple[dict, ...] | None = None,
) -> WeChatNativeStaticDiscoveryReport:
    started = time.perf_counter()
    explicit_dirs = _string_tuple(install_dirs)
    try:
        discovered_dirs = _discover_install_dirs(process_snapshot=process_snapshot)
        selected_dirs = _existing_dirs(explicit_dirs or discovered_dirs)
        files = _candidate_files(
            selected_dirs,
            recursive_depth=max(0, int(recursive_depth or 0)),
            max_files=max(0, int(max_files or 0)),
        )
        scanned = tuple(
            _scan_candidate_file(
                path,
                max_export_names=max_export_names,
                max_keyword_bytes=max_keyword_bytes,
            )
            for path in files
        )
        helper_manifests = _read_helper_manifests(selected_dirs)
        error = ""
    except Exception as exc:
        discovered_dirs = ()
        selected_dirs = ()
        scanned = ()
        helper_manifests = ()
        error = str(exc) or exc.__class__.__name__
    return WeChatNativeStaticDiscoveryReport(
        install_dirs=tuple(str(item) for item in selected_dirs),
        scanned_files=tuple(dict(item) for item in scanned),
        helper_manifests=tuple(dict(item) for item in helper_manifests),
        discovered_install_dirs=tuple(str(item) for item in discovered_dirs),
        explicit_install_dirs=explicit_dirs,
        max_files=max(0, int(max_files or 0)),
        error=error,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only static discovery over local WeChat binaries."
    )
    parser.add_argument("--install-dir", action="append", default=[])
    parser.add_argument("--recursive-depth", type=int, default=1)
    parser.add_argument("--max-files", type=int, default=160)
    parser.add_argument("--max-export-names", type=int, default=240)
    parser.add_argument("--max-keyword-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    report = run_wechat_native_static_discovery(
        install_dirs=tuple(args.install_dir or ()),
        recursive_depth=args.recursive_depth,
        max_files=args.max_files,
        max_export_names=args.max_export_names,
        max_keyword_bytes=args.max_keyword_bytes,
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if args.json:
        _write_stdout(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _write_stdout(
            "WeChat native static discovery: "
            f"ok={str(data['ok']).lower()} "
            f"decision={data['decision']} "
            f"files={data['scanned_file_count']}"
        )
    if args.strict and not data["ok"]:
        return 1
    return 0


def _discover_install_dirs(
    *, process_snapshot: tuple[dict, ...] | None = None
) -> tuple[str, ...]:
    rows = tuple(process_snapshot) if process_snapshot is not None else _wechat_processes()
    dirs: list[str] = []
    env_dir = str(os.environ.get("OPENWUKONG_WECHAT_INSTALL_DIR", "") or "").strip()
    if env_dir:
        dirs.append(env_dir)
    for row in rows:
        exe = str(row.get("exe", "") or "").strip()
        if not exe:
            continue
        path = Path(exe)
        parent = path.parent
        dirs.append(str(parent))
        for child in _version_subdirs(parent):
            dirs.append(str(child))
    return _unique_strings(dirs)


def _wechat_processes() -> tuple[dict, ...]:
    try:
        import psutil
    except Exception:
        return ()

    rows: list[dict] = []
    for proc in psutil.process_iter(("pid", "name", "exe", "cmdline"), ad_value=""):
        info = dict(getattr(proc, "info", {}) or {})
        name = str(info.get("name", "") or "")
        exe = str(info.get("exe", "") or "")
        cmdline = _cmdline_text(info.get("cmdline", ""))
        if not _is_personal_wechat_process(name, exe, cmdline):
            continue
        rows.append(
            {
                "pid": int(info.get("pid", 0) or 0),
                "name": name,
                "exe": exe,
            }
        )
    return tuple(rows)


def _candidate_files(
    install_dirs: tuple[str, ...],
    *,
    recursive_depth: int,
    max_files: int,
) -> tuple[Path, ...]:
    if max_files <= 0:
        return ()
    candidates: dict[str, Path] = {}
    for root_text in install_dirs:
        root = Path(root_text)
        if root.is_file() and root.suffix.casefold() in _CANDIDATE_SUFFIXES:
            candidates[str(root.resolve()).casefold()] = root
            continue
        if not root.is_dir():
            continue
        for path in _walk_candidate_files(root, max_depth=recursive_depth):
            key = str(path.resolve()).casefold()
            candidates.setdefault(key, path)
            if len(candidates) >= max_files:
                break
        if len(candidates) >= max_files:
            break
    return tuple(sorted(candidates.values(), key=_candidate_sort_key))[:max_files]


def _walk_candidate_files(root: Path, *, max_depth: int) -> tuple[Path, ...]:
    rows: list[Path] = []
    queue: list[tuple[Path, int]] = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        try:
            children = tuple(current.iterdir())
        except Exception:
            continue
        for child in children:
            if child.is_file() and child.suffix.casefold() in _CANDIDATE_SUFFIXES:
                rows.append(child)
            elif child.is_dir() and depth < max_depth:
                queue.append((child, depth + 1))
    return tuple(rows)


def _scan_candidate_file(
    path: Path,
    *,
    max_export_names: int,
    max_keyword_bytes: int,
) -> dict:
    stat = path.stat()
    export_report = _parse_pe_exports(path, max_names=max_export_names)
    keyword_hits = _keyword_hits_for_file(path, max_bytes=max_keyword_bytes)
    exports = tuple(str(item) for item in export_report.get("export_names", []) or ())
    public_pe_report = dict(export_report)
    public_pe_report["export_names"] = list(exports[:80])
    public_pe_report["export_names_sample_limit"] = 80
    return {
        "name": path.name,
        "path": str(path),
        "size": int(stat.st_size),
        "sha256_prefix": _sha256_prefix(path),
        "name_hints": _name_hints(path.name),
        "pe": public_pe_report,
        "interesting_exports": _interesting_exports(exports),
        "keyword_hits": keyword_hits,
        "static_signals": _file_static_signals(path.name, exports, keyword_hits),
    }


def _parse_pe_exports(path: Path, *, max_names: int = 240) -> dict:
    try:
        size = path.stat().st_size
        if size <= 0:
            return {"is_pe": False, "export_names": [], "error": "empty_file"}
        if size > _MAX_PE_PARSE_BYTES:
            return {
                "is_pe": False,
                "export_names": [],
                "error": "file_too_large_for_pe_parse",
            }
        return _parse_pe_exports_from_bytes(path.read_bytes(), max_names=max_names)
    except Exception as exc:
        return {
            "is_pe": False,
            "export_names": [],
            "error": str(exc) or exc.__class__.__name__,
        }


def _parse_pe_exports_from_bytes(data: bytes, *, max_names: int = 240) -> dict:
    raw = bytes(data or b"")
    if len(raw) < 0x40 or raw[:2] != b"MZ":
        return {"is_pe": False, "export_names": [], "error": "missing_mz_header"}
    pe_offset = _u32(raw, 0x3C)
    if pe_offset <= 0 or pe_offset + 24 > len(raw):
        return {"is_pe": False, "export_names": [], "error": "invalid_pe_offset"}
    if raw[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        return {"is_pe": False, "export_names": [], "error": "missing_pe_signature"}

    coff_offset = pe_offset + 4
    (
        machine,
        section_count,
        _timestamp,
        _symbol_table,
        _symbol_count,
        optional_header_size,
        characteristics,
    ) = struct.unpack_from("<HHIIIHH", raw, coff_offset)
    optional_offset = coff_offset + 20
    optional_end = optional_offset + optional_header_size
    if optional_end > len(raw) or optional_header_size < 2:
        return {"is_pe": True, "export_names": [], "error": "invalid_optional_header"}
    magic = _u16(raw, optional_offset)
    if magic == 0x10B:
        data_directory_offset = optional_offset + 96
        number_of_rva_offset = optional_offset + 92
        pe_kind = "PE32"
    elif magic == 0x20B:
        data_directory_offset = optional_offset + 112
        number_of_rva_offset = optional_offset + 108
        pe_kind = "PE32+"
    else:
        return {
            "is_pe": True,
            "machine": _machine_name(machine),
            "pe_kind": f"unknown:{magic:#x}",
            "export_names": [],
            "error": "unsupported_optional_header_magic",
        }

    if number_of_rva_offset + 4 > optional_end:
        return {"is_pe": True, "export_names": [], "error": "missing_rva_directory_count"}
    number_of_rva_and_sizes = _u32(raw, number_of_rva_offset)
    if number_of_rva_and_sizes < 1 or data_directory_offset + 8 > optional_end:
        return {
            "is_pe": True,
            "machine": _machine_name(machine),
            "pe_kind": pe_kind,
            "export_names": [],
            "export_count": 0,
        }

    export_rva, export_size = struct.unpack_from("<II", raw, data_directory_offset)
    sections = _parse_sections(
        raw,
        optional_end,
        section_count=section_count,
    )
    base = {
        "is_pe": True,
        "machine": _machine_name(machine),
        "pe_kind": pe_kind,
        "characteristics": int(characteristics),
        "section_count": int(section_count),
        "export_rva": int(export_rva),
        "export_size": int(export_size),
    }
    if not export_rva:
        return {**base, "export_names": [], "export_count": 0}

    export_offset = _rva_to_offset(export_rva, sections, file_size=len(raw))
    if export_offset is None or export_offset + 40 > len(raw):
        return {**base, "export_names": [], "error": "invalid_export_directory_rva"}
    fields = struct.unpack_from("<IIHHIIIIIII", raw, export_offset)
    number_of_functions = fields[6]
    number_of_names = fields[7]
    address_of_names = fields[9]
    names_offset = _rva_to_offset(address_of_names, sections, file_size=len(raw))
    if not names_offset:
        return {
            **base,
            "export_names": [],
            "export_count": int(number_of_functions),
            "named_export_count": int(number_of_names),
            "error": "invalid_export_names_rva",
        }

    names: list[str] = []
    for index in range(min(int(number_of_names), max(0, int(max_names or 0)))):
        pointer_offset = names_offset + index * 4
        if pointer_offset + 4 > len(raw):
            break
        name_rva = _u32(raw, pointer_offset)
        name_offset = _rva_to_offset(name_rva, sections, file_size=len(raw))
        if name_offset is None:
            continue
        value = _read_c_string(raw, name_offset, limit=512)
        if value:
            names.append(value)
    return {
        **base,
        "export_count": int(number_of_functions),
        "named_export_count": int(number_of_names),
        "export_names": names,
        "export_names_truncated": int(number_of_names) > len(names),
    }


def _parse_sections(
    raw: bytes,
    section_offset: int,
    *,
    section_count: int,
) -> tuple[dict, ...]:
    sections: list[dict] = []
    for index in range(max(0, int(section_count))):
        offset = section_offset + index * 40
        if offset + 40 > len(raw):
            break
        (
            name,
            virtual_size,
            virtual_address,
            size_of_raw_data,
            pointer_to_raw_data,
            _ptr_reloc,
            _ptr_line,
            _num_reloc,
            _num_line,
            _characteristics,
        ) = struct.unpack_from("<8sIIIIIIHHI", raw, offset)
        sections.append(
            {
                "name": name.split(b"\x00", 1)[0].decode("ascii", errors="replace"),
                "virtual_size": int(virtual_size),
                "virtual_address": int(virtual_address),
                "size_of_raw_data": int(size_of_raw_data),
                "pointer_to_raw_data": int(pointer_to_raw_data),
            }
        )
    return tuple(sections)


def _rva_to_offset(
    rva: int,
    sections: tuple[dict, ...],
    *,
    file_size: int,
) -> int | None:
    value = int(rva or 0)
    if value <= 0:
        return None
    for section in sections:
        virtual_address = int(section.get("virtual_address", 0) or 0)
        virtual_size = int(section.get("virtual_size", 0) or 0)
        raw_size = int(section.get("size_of_raw_data", 0) or 0)
        raw_pointer = int(section.get("pointer_to_raw_data", 0) or 0)
        span = max(virtual_size, raw_size)
        if virtual_address <= value < virtual_address + span:
            offset = raw_pointer + (value - virtual_address)
            if 0 <= offset < file_size:
                return offset
    if 0 <= value < file_size:
        return value
    return None


def _keyword_hits_for_file(path: Path, *, max_bytes: int) -> dict:
    limit = max(0, int(max_bytes or 0))
    if limit <= 0:
        return {}
    try:
        with path.open("rb") as fh:
            return _keyword_hits_for_bytes(fh.read(limit))
    except Exception as exc:
        return {"error": exc.__class__.__name__}


def _keyword_hits_for_bytes(data: bytes) -> dict:
    raw = bytes(data or b"")
    lowered = raw.lower()
    hits: dict[str, int] = {}
    for keyword in _STATIC_KEYWORDS:
        count = 0
        for pattern in _keyword_patterns(keyword):
            count += lowered.count(pattern)
        if count:
            hits[keyword] = int(count)
    return hits


def _keyword_patterns(keyword: str) -> tuple[bytes, ...]:
    ascii_pattern = keyword.casefold().encode("ascii", errors="ignore")
    utf16_pattern = keyword.casefold().encode("utf-16le", errors="ignore")
    return tuple(pattern for pattern in (ascii_pattern, utf16_pattern) if pattern)


def _read_helper_manifests(install_dirs: tuple[str, ...]) -> tuple[dict, ...]:
    rows: list[dict] = []
    for root_text in install_dirs:
        root = Path(root_text)
        if not root.is_dir():
            continue
        for name in _DOCUMENTED_HELPER_MANIFEST_NAMES:
            path = root / name
            if not path.is_file():
                continue
            rows.append(_read_helper_manifest(path))
    return tuple(rows)


def _read_helper_manifest(path: Path) -> dict:
    result = {"path": str(path), "name": path.name, "send_action_ready": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        result["error"] = exc.__class__.__name__
        return result
    if not isinstance(data, dict):
        result["error"] = "manifest_not_object"
        return result
    result.update(
        {
            "schema": str(data.get("schema", "") or ""),
            "command_declared": bool(data.get("command")),
            "background_safe": bool(data.get("background_safe", False)),
            "send_action_ready": bool(data.get("send_action_ready", False)),
            "requires_foreground": bool(data.get("requires_foreground", True)),
            "window_input_required": bool(data.get("window_input_required", True)),
            "keyboard_input_required": bool(data.get("keyboard_input_required", True)),
            "clipboard_required": bool(data.get("clipboard_required", True)),
        }
    )
    return result


def _helper_manifest_send_ready(item: dict) -> bool:
    return bool(
        str(item.get("schema", "") or "") == "openwukong.wechat.native_helper.v1"
        and item.get("command_declared", False)
        and item.get("background_safe", False)
        and item.get("send_action_ready", False)
        and not item.get("requires_foreground", True)
        and not item.get("window_input_required", True)
        and not item.get("keyboard_input_required", True)
        and not item.get("clipboard_required", True)
    )


def _has_static_ipc_or_send_signal(files: tuple[dict, ...]) -> bool:
    return any(item.get("static_signals") for item in files)


def _static_signal_summary(files: tuple[dict, ...]) -> dict:
    summary: dict[str, int] = {}
    for item in files:
        for signal in item.get("static_signals", []) or []:
            summary[str(signal)] = summary.get(str(signal), 0) + 1
    return dict(sorted(summary.items()))


def _file_static_signals(name: str, exports: tuple[str, ...], keywords: dict) -> list[str]:
    signals: set[str] = set()
    lowered_name = str(name or "").casefold()
    for token in ("mojo", "ilink", "ipc", "bridge", "helper"):
        if token in lowered_name:
            signals.add(f"name:{token}")
    for token in ("mojo", "ilink", "ipc", "pipe", "localhost", "127.0.0.1"):
        if int(keywords.get(token, 0) or 0) > 0:
            signals.add(f"keyword:{token}")
    if _has_send_like_export(exports):
        signals.add("export:send-like")
    if _has_conversation_like_export(exports):
        signals.add("export:conversation-like")
    return sorted(signals)


def _interesting_exports(exports: tuple[str, ...], *, limit: int = 40) -> list[str]:
    interesting = []
    for name in exports:
        lowered = name.casefold()
        if any(token in lowered for token in ("send", "msg", "message", "chat", "conv", "mojo", "ipc", "ilink")):
            interesting.append(name)
        if len(interesting) >= limit:
            break
    return interesting


def _has_send_like_export(exports: tuple[str, ...]) -> bool:
    return any(
        token in name.casefold()
        for name in exports
        for token in ("send", "sendmessage", "postmessage", "message")
    )


def _has_conversation_like_export(exports: tuple[str, ...]) -> bool:
    return any(
        token in name.casefold()
        for name in exports
        for token in ("chat", "conversation", "session")
    )


def _name_hints(name: str) -> list[str]:
    lowered = str(name or "").casefold()
    return [token for token in _CANDIDATE_NAME_HINTS if token in lowered]


def _candidate_sort_key(path: Path) -> tuple[int, str]:
    name = path.name.casefold()
    priority = 0 if any(token in name for token in _CANDIDATE_NAME_HINTS) else 1
    return (priority, str(path).casefold())


def _sha256_prefix(path: Path) -> str:
    digest = hashlib.sha256()
    remaining = _MAX_HASH_BYTES
    try:
        with path.open("rb") as fh:
            while remaining > 0:
                chunk = fh.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
    except Exception:
        return ""
    return digest.hexdigest()[:16]


def _version_subdirs(parent: Path) -> tuple[Path, ...]:
    try:
        children = tuple(parent.iterdir())
    except Exception:
        return ()
    rows = []
    for child in children:
        if not child.is_dir():
            continue
        name = child.name
        if name and all(part.isdigit() for part in name.split(".") if part):
            rows.append(child)
    return tuple(sorted(rows, key=lambda item: item.name, reverse=True))


def _is_personal_wechat_process(name: str, exe: str, cmdline: str) -> bool:
    text = " ".join((name, exe, cmdline)).casefold()
    if "wxwork" in text or "wecom" in text or "enterprise wechat" in text:
        return False
    process = str(name or "").strip().casefold()
    return process in _WECHAT_PROCESS_NAMES


def _existing_dirs(values: tuple[str, ...]) -> tuple[str, ...]:
    rows = []
    for value in values:
        path = Path(value)
        if path.exists():
            rows.append(str(path))
    return _unique_strings(rows)


def _string_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        items = tuple(values)  # type: ignore[arg-type]
    except TypeError:
        items = (values,)
    return tuple(str(item).strip() for item in items if str(item or "").strip())


def _unique_strings(values: object) -> tuple[str, ...]:
    seen: set[str] = set()
    rows: list[str] = []
    for item in _string_tuple(values):
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    return tuple(rows)


def _cmdline_text(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _u16(raw: bytes, offset: int) -> int:
    if offset + 2 > len(raw):
        return 0
    return int(struct.unpack_from("<H", raw, offset)[0])


def _u32(raw: bytes, offset: int) -> int:
    if offset + 4 > len(raw):
        return 0
    return int(struct.unpack_from("<I", raw, offset)[0])


def _read_c_string(raw: bytes, offset: int, *, limit: int) -> str:
    if offset < 0 or offset >= len(raw):
        return ""
    end = min(len(raw), offset + max(1, int(limit or 1)))
    stop = raw.find(b"\x00", offset, end)
    if stop < 0:
        stop = end
    return raw[offset:stop].decode("utf-8", errors="replace")


def _machine_name(machine: int) -> str:
    return {
        0x014C: "x86",
        0x8664: "x64",
        0xAA64: "arm64",
        0x01C0: "arm",
    }.get(int(machine or 0), f"unknown:{int(machine or 0):#x}")


def _write_stdout(text: str) -> None:
    output = text + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write(output.encode("utf-8", errors="replace"))
        flush = getattr(buffer, "flush", None)
        if callable(flush):
            flush()


__all__ = [
    "WeChatNativeStaticDiscoveryReport",
    "main",
    "run_wechat_native_static_discovery",
]


if __name__ == "__main__":
    raise SystemExit(main())
