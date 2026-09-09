import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.ide_bridge_settings_apply import (
    apply_bridge_settings_file,
    main,
    parse_jsonc_object,
)


class IDEBridgeSettingsApplyTests(unittest.TestCase):
    def test_apply_preserves_existing_jsonc_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "settings.json"
            settings_path.write_text(
                '{\n'
                '  "workbench.colorTheme": "GitHub Light",\n'
                '  // keep this user note\n'
                '  "files.autoSave": "afterDelay"\n'
                '}\n',
                encoding="utf-8",
            )
            original = settings_path.read_text(encoding="utf-8")

            report = apply_bridge_settings_file(
                settings_path,
                {
                    "openwukong.bridge.port": 8787,
                    "openwukong.bridge.allowedCommands": ["composer.startComposerPrompt"],
                },
                backup_dir=Path(td) / "backups",
            )

            updated = settings_path.read_text(encoding="utf-8")
            parsed = parse_jsonc_object(updated)
            backup_text = Path(report["backup_path"]).read_text(encoding="utf-8")

        self.assertEqual(report["status"], "applied")
        self.assertTrue(report["changed"])
        self.assertEqual(report["applied_keys"], ["openwukong.bridge.port", "openwukong.bridge.allowedCommands"])
        self.assertEqual(backup_text, original)
        self.assertIn("// keep this user note", updated)
        self.assertEqual(parsed["workbench.colorTheme"], "GitHub Light")
        self.assertEqual(parsed["files.autoSave"], "afterDelay")
        self.assertEqual(parsed["openwukong.bridge.port"], 8787)
        self.assertEqual(parsed["openwukong.bridge.allowedCommands"], ["composer.startComposerPrompt"])

    def test_apply_refuses_existing_openwukong_keys_without_replace(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "settings.json"
            settings_path.write_text(
                '{\n'
                '  "openwukong.bridge.port": 9999,\n'
                '  "files.autoSave": "afterDelay"\n'
                '}\n',
                encoding="utf-8",
            )
            original = settings_path.read_text(encoding="utf-8")

            report = apply_bridge_settings_file(
                settings_path,
                {"openwukong.bridge.port": 8787},
                backup_dir=Path(td) / "backups",
            )
            after = settings_path.read_text(encoding="utf-8")
            backup_dir_exists = (Path(td) / "backups").exists()

        self.assertEqual(report["status"], "refused_existing_openwukong_keys")
        self.assertFalse(report["changed"])
        self.assertEqual(report["existing_keys"], ["openwukong.bridge.port"])
        self.assertEqual(after, original)
        self.assertFalse(backup_dir_exists)

    def test_apply_can_replace_existing_openwukong_keys_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "settings.json"
            settings_path.write_text(
                '{\n'
                '  "openwukong.bridge.port": 9999,\n'
                '  "openwukong.bridge.allowedCommands": ["old.command"],\n'
                '  "files.autoSave": "afterDelay"\n'
                '}\n',
                encoding="utf-8",
            )
            original = settings_path.read_text(encoding="utf-8")

            report = apply_bridge_settings_file(
                settings_path,
                {
                    "openwukong.bridge.port": 8787,
                    "openwukong.bridge.allowedCommands": ["composer.sendToAgent"],
                },
                backup_dir=Path(td) / "backups",
                replace_existing=True,
                timestamp="fixed",
            )
            parsed = parse_jsonc_object(settings_path.read_text(encoding="utf-8"))
            backup_text = Path(report["backup_path"]).read_text(encoding="utf-8")

        self.assertEqual(report["status"], "replaced")
        self.assertTrue(report["changed"])
        self.assertEqual(backup_text, original)
        self.assertEqual(parsed["files.autoSave"], "afterDelay")
        self.assertEqual(parsed["openwukong.bridge.port"], 8787)
        self.assertEqual(parsed["openwukong.bridge.allowedCommands"], ["composer.sendToAgent"])

    def test_cli_applies_validated_settings_to_jsonc_file(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / "settings.json"
            bridge_settings_path = Path(td) / "validated-settings.json"
            settings_path.write_text('{\n  "files.autoSave": "afterDelay"\n}\n', encoding="utf-8")
            bridge_settings_path.write_text(
                json.dumps(
                    {
                        "openwukong.bridge.port": 8787,
                        "openwukong.bridge.allowedCommands": ["composer.startComposerPrompt"],
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--settings-file",
                        str(settings_path),
                        "--bridge-settings",
                        str(bridge_settings_path),
                        "--backup-dir",
                        str(Path(td) / "backups"),
                        "--json",
                    ]
                )

            printed = json.loads(stdout.getvalue())
            parsed = parse_jsonc_object(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["status"], "applied")
        self.assertEqual(parsed["openwukong.bridge.port"], 8787)


if __name__ == "__main__":
    unittest.main()
