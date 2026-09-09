import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.evaluation import ide_extension_sync as sync_module
from openwukong.evaluation.ide_extension_sync import sync_ide_extension_install


class IDEExtensionSyncTests(unittest.TestCase):
    def test_dry_run_reports_stale_installed_extension_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_extension(root / "source")
            installed_root = root / ".cursor" / "extensions"
            installed = _write_legacy_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0"
            )
            before = (installed / "package.json").read_text(encoding="utf-8")

            report = sync_ide_extension_install(
                extension_dir=source,
                installed_extension_roots=(installed_root,),
                process_snapshot_provider=lambda: (),
            ).to_dict()
            after = (installed / "package.json").read_text(encoding="utf-8")

        self.assertEqual(report["status"], "stale_install_detected")
        self.assertEqual(report["safety_mode"], "read_only")
        self.assertEqual(report["write_attempts"], 0)
        self.assertFalse(report["instances"][0]["changed"])
        self.assertTrue(report["instances"][0]["stale"])
        self.assertEqual(after, before)

    def test_apply_refuses_when_cursor_process_is_active(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_extension(root / "source")
            installed_root = root / ".cursor" / "extensions"
            installed = _write_legacy_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0"
            )

            report = sync_ide_extension_install(
                extension_dir=source,
                installed_extension_roots=(installed_root,),
                apply=True,
                process_snapshot_provider=lambda: (
                    {
                        "pid": 42,
                        "name": "Cursor.exe",
                        "executable_path": "C:/Users/me/AppData/Local/Programs/Cursor/Cursor.exe",
                        "command_line": "Cursor.exe " + ("x" * 400),
                    },
                ),
            ).to_dict()
            installed_package = json.loads((installed / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "apply_refused_active_process")
        self.assertEqual(report["write_attempts"], 0)
        self.assertLessEqual(len(report["active_processes"][0]["command_line"]), 240)
        self.assertEqual(report["instances"][0]["error"], "active_ide_process_detected")
        self.assertTrue(report["instances"][0]["active_process_detected"])
        self.assertEqual(
            installed_package["contributes"]["configuration"]["properties"]["openwukong.bridge.port"]["default"],
            8787,
        )

    def test_apply_refuses_when_cursor_process_name_has_no_exe_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_extension(root / "source")
            installed_root = root / ".cursor" / "extensions"
            _write_legacy_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0"
            )

            report = sync_ide_extension_install(
                extension_dir=source,
                installed_extension_roots=(installed_root,),
                apply=True,
                process_snapshot_provider=lambda: (
                    {
                        "pid": 43,
                        "name": "Cursor",
                        "executable_path": "",
                        "command_line": "",
                    },
                ),
            ).to_dict()

        self.assertEqual(report["status"], "apply_refused_active_process")
        self.assertEqual(report["write_attempts"], 0)
        self.assertTrue(report["instances"][0]["active_process_detected"])

    def test_default_process_snapshot_falls_back_to_get_process_when_cim_is_denied(self):
        class _Completed:
            def __init__(self, returncode, stdout=""):
                self.returncode = returncode
                self.stdout = stdout

        calls = []

        def _run(*args, **kwargs):
            del kwargs
            command = " ".join(str(item) for item in args[0])
            calls.append(command)
            if "Get-CimInstance" in command:
                return _Completed(1, "")
            return _Completed(
                0,
                json.dumps(
                    [
                        {
                            "pid": 44,
                            "name": "Cursor",
                            "executable_path": "E:/cursor/cursor/Cursor.exe",
                            "command_line": "E:/cursor/cursor/Cursor.exe",
                        }
                    ]
                ),
            )

        with patch.object(sync_module.subprocess, "run", _run):
            rows = sync_module._default_process_snapshot()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Cursor")
        self.assertIn("Get-CimInstance", calls[0])
        self.assertIn("Get-Process", calls[1])

    def test_apply_updates_inactive_instance_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_extension(root / "source")
            (source / "logs").mkdir()
            (source / "logs" / "runtime.log").write_text("skip", encoding="utf-8")
            installed_root = root / ".cursor" / "extensions"
            installed = _write_legacy_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0"
            )
            backup_root = root / "backups"

            report = sync_ide_extension_install(
                extension_dir=source,
                installed_extension_roots=(installed_root,),
                apply=True,
                backup_dir=backup_root,
                process_snapshot_provider=lambda: (),
                timestamp="fixed",
            ).to_dict()
            installed_package = json.loads((installed / "package.json").read_text(encoding="utf-8"))
            backup_path = Path(report["instances"][0]["backup_path"])
            backup_exists = backup_path.is_dir()
            backup_package = json.loads((backup_path / "package.json").read_text(encoding="utf-8"))
            logs_copied = (installed / "logs" / "runtime.log").exists()

        self.assertEqual(report["status"], "applied")
        self.assertEqual(report["write_attempts"], 1)
        self.assertEqual(report["backup_attempts"], 1)
        self.assertTrue(backup_exists)
        self.assertEqual(
            installed_package["contributes"]["configuration"]["properties"]["openwukong.bridge.port"]["default"],
            0,
        )
        self.assertEqual(
            backup_package["contributes"]["configuration"]["properties"]["openwukong.bridge.port"]["default"],
            8787,
        )
        self.assertFalse(logs_copied)

    def test_install_if_missing_plans_destination_without_apply(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_extension(root / "source")
            installed_root = root / ".cursor" / "extensions"
            installed_root.mkdir(parents=True)

            report = sync_ide_extension_install(
                extension_dir=source,
                installed_extension_roots=(installed_root,),
                install_if_missing=True,
                process_snapshot_provider=lambda: (),
            ).to_dict()

        self.assertEqual(report["status"], "stale_install_detected")
        self.assertEqual(report["write_attempts"], 0)
        self.assertTrue(report["instances"][0]["diagnostics"]["install_missing"])
        self.assertTrue(report["instances"][0]["path"].endswith("openwukong-local.openwukong-vscode-bridge-0.1.0"))


def _write_source_extension(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "src").mkdir()
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "openwukong-vscode-bridge",
                "publisher": "openwukong-local",
                "version": "0.1.0",
                "contributes": {
                    "configuration": {
                        "properties": {
                            "openwukong.bridge.port": {
                                "type": "number",
                                "default": 0,
                            },
                            "openwukong.bridge.autoStart": {
                                "type": "boolean",
                                "default": False,
                            },
                            "openwukong.bridge.dynamicPortOnConflict": {
                                "type": "boolean",
                                "default": True,
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (path / "README.md").write_text("adaptive bridge", encoding="utf-8")
    (path / "src" / "extension.js").write_text(
        'const preferredPort = config.get("bridge.port", 0);\n'
        "const bound = await listenOnPort(candidate, host, 0);\n"
        "const address = candidate.address();\n",
        encoding="utf-8",
    )
    return path


def _write_legacy_extension(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "src").mkdir()
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "openwukong-vscode-bridge",
                "publisher": "openwukong-local",
                "version": "0.1.0",
                "contributes": {
                    "configuration": {
                        "properties": {
                            "openwukong.bridge.port": {
                                "type": "number",
                                "default": 8787,
                            },
                            "openwukong.bridge.autoStart": {
                                "type": "boolean",
                                "default": True,
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (path / "README.md").write_text("legacy bridge", encoding="utf-8")
    (path / "src" / "extension.js").write_text(
        'const port = config.get("bridge.port", 8787);\n'
        'vscode.window.showWarningMessage(`OpenWukong bridge failed to start: ${error.message}`);\n',
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
