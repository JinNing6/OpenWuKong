# -*- coding: utf-8 -*-
"""Apply OpenWukong IDE bridge settings to VS Code-compatible JSONC settings."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Optional


def parse_jsonc_object(text: str) -> dict:
    data = json.loads(_strip_jsonc_comments(text))
    if not isinstance(data, dict):
        raise ValueError("settings_json_must_be_object")
    return data


def apply_bridge_settings_file(
    settings_file: str | Path,
    bridge_settings: dict,
    *,
    backup_dir: str | Path | None = None,
    timestamp: str | None = None,
    replace_existing: bool = False,
) -> dict:
    path = Path(settings_file)
    text = path.read_text(encoding="utf-8") if path.exists() else "{\n}\n"
    parsed = parse_jsonc_object(text)
    updates = _openwukong_settings(bridge_settings)
    if not updates:
        return {
            "mode": "ide-bridge-settings-apply",
            "status": "no_openwukong_settings",
            "changed": False,
            "settings_file": str(path),
            "applied_keys": [],
            "existing_keys": [],
            "backup_path": "",
        }

    existing_keys = [key for key in updates if key in parsed]
    if existing_keys and not replace_existing:
        return {
            "mode": "ide-bridge-settings-apply",
            "status": "refused_existing_openwukong_keys",
            "changed": False,
            "settings_file": str(path),
            "applied_keys": [],
            "existing_keys": existing_keys,
            "backup_path": "",
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_file(path, text, backup_dir=backup_dir, timestamp=timestamp)
    if replace_existing:
        updated_text = _replace_top_level_settings(parsed, updates)
        status = "replaced" if existing_keys else "applied"
    else:
        updated_text = _insert_top_level_settings(text, updates)
        status = "applied"
    path.write_text(updated_text, encoding="utf-8")
    return {
        "mode": "ide-bridge-settings-apply",
        "status": status,
        "changed": True,
        "settings_file": str(path),
        "applied_keys": list(updates.keys()),
        "existing_keys": [],
        "backup_path": str(backup_path),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply validated OpenWukong IDE bridge settings to a JSONC settings file."
    )
    parser.add_argument("--settings-file", required=True, help="VS Code/Cursor User settings.json path.")
    parser.add_argument("--bridge-settings", required=True, help="JSON file containing OpenWukong bridge settings.")
    parser.add_argument("--backup-dir", default="", help="Optional backup directory.")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace existing openwukong.* settings after creating a backup.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)

    bridge_settings = json.loads(Path(args.bridge_settings).read_text(encoding="utf-8-sig"))
    if not isinstance(bridge_settings, dict):
        raise ValueError("bridge_settings_must_be_object")
    report = apply_bridge_settings_file(
        args.settings_file,
        bridge_settings,
        backup_dir=args.backup_dir or None,
        replace_existing=args.replace_existing,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "IDE bridge settings apply: "
            f"status={report['status']} changed={report['changed']} file={report['settings_file']}"
        )
    return 0


def _openwukong_settings(settings: dict) -> dict:
    selected: dict = {}
    for key, value in settings.items():
        if isinstance(key, str) and key.startswith("openwukong."):
            selected[key] = value
    return selected


def _backup_file(
    path: Path,
    original_text: str,
    *,
    backup_dir: str | Path | None,
    timestamp: str | None,
) -> Path:
    stamp = timestamp or time.strftime("%Y%m%d-%H%M%S")
    destination_dir = Path(backup_dir) if backup_dir else path.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = destination_dir / f"{path.name}.openwukong-backup-{stamp}.jsonc"
    if path.exists():
        shutil.copy2(path, backup_path)
    else:
        backup_path.write_text(original_text, encoding="utf-8")
    return backup_path


def _insert_top_level_settings(text: str, updates: dict) -> str:
    close_index = _find_final_object_close(text)
    prefix = text[:close_index].rstrip()
    suffix = text[close_index:]
    parsed = parse_jsonc_object(text)
    rendered_updates = _render_settings_block(updates)
    separator = "\n" if not parsed else ",\n"
    return f"{prefix}{separator}{rendered_updates}\n{suffix.lstrip()}"


def _replace_top_level_settings(parsed: dict, updates: dict) -> str:
    merged = dict(parsed)
    for key, value in updates.items():
        merged[key] = value
    return json.dumps(merged, ensure_ascii=False, indent=2) + "\n"


def _render_settings_block(updates: dict) -> str:
    lines: list[str] = []
    for key, value in updates.items():
        rendered_value = json.dumps(value, ensure_ascii=False, indent=2)
        rendered_value = rendered_value.replace("\n", "\n  ")
        lines.append(f'  {json.dumps(key, ensure_ascii=False)}: {rendered_value}')
    return ",\n".join(lines)


def _find_final_object_close(text: str) -> int:
    index = len(text) - 1
    while index >= 0 and text[index].isspace():
        index -= 1
    if index < 0 or text[index] != "}":
        raise ValueError("settings_json_must_end_with_object")
    return index


def _strip_jsonc_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escape = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


if __name__ == "__main__":
    raise SystemExit(main())
