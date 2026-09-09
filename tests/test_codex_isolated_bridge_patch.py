import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.evaluation.codex_isolated_bridge_patch import (
    CODEX_EXTENSION_COMMAND,
    MANIFEST_NAME,
    PATCH_MARKER,
    build_codex_isolated_bridge_patch,
)


class CodexIsolatedBridgePatchTests(unittest.TestCase):
    def test_dry_run_reports_ready_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_codex_extension(root / "openai.chatgpt-1.0.0")
            isolated_root = root / "isolated"
            before = (source / "out" / "extension.js").read_text(encoding="utf-8")

            report = build_codex_isolated_bridge_patch(
                source_extension_path=source,
                isolated_extension_root=isolated_root,
            ).to_dict()
            after = (source / "out" / "extension.js").read_text(encoding="utf-8")

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_isolated_bridge_patch_ready")
        self.assertEqual(report["safety_mode"], "dry_run_no_writes")
        self.assertEqual(report["write_attempts"], 0)
        self.assertEqual(report["copy_attempts"], 0)
        self.assertFalse(report["normal_profile_touched"])
        self.assertFalse(Path(report["isolated_extension_path"]).exists())
        self.assertEqual(before, after)
        self.assertEqual(report["patch_plan"]["command"], CODEX_EXTENSION_COMMAND)
        self.assertIn("composer_prefill", report["patch_plan"]["prefill_key"])

    def test_apply_writes_only_isolated_copy_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_codex_extension(root / "openai.chatgpt-1.0.0")
            isolated_root = root / "isolated"
            source_entrypoint = source / "out" / "extension.js"
            before = source_entrypoint.read_text(encoding="utf-8")

            report = build_codex_isolated_bridge_patch(
                source_extension_path=source,
                isolated_extension_root=isolated_root,
                apply=True,
                timestamp="2026-06-28T00:00:00+0800",
            ).to_dict()

            target = Path(report["isolated_extension_path"])
            patched = (target / "out" / "extension.js").read_text(encoding="utf-8")
            manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
            after = source_entrypoint.read_text(encoding="utf-8")
            target_exists = target.is_dir()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_isolated_bridge_patch_applied")
        self.assertEqual(report["safety_mode"], "isolated_extension_copy_apply")
        self.assertEqual(report["write_attempts"], 3)
        self.assertEqual(report["copy_attempts"], 1)
        self.assertEqual(report["patch_attempts"], 1)
        self.assertTrue(target_exists)
        self.assertIn(PATCH_MARKER, patched)
        self.assertIn(CODEX_EXTENSION_COMMAND, patched)
        self.assertIn('Ue.sharedObjectRepository.set("composer_prefill",owValue)', patched)
        self.assertIn('Ue.broadcastToAllViews({type:"shared-object-updated"', patched)
        self.assertNotIn(PATCH_MARKER, after)
        self.assertEqual(before, after)
        self.assertEqual(manifest["command"], CODEX_EXTENSION_COMMAND)
        self.assertEqual(manifest["send_attempts"], 0)
        self.assertEqual(manifest["control_attempts"], 0)

    def test_apply_blocks_normal_extension_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_codex_extension(root / "openai.chatgpt-1.0.0")
            normal_root = root / ".cursor" / "extensions"

            with patch(
                "openwukong.evaluation.codex_isolated_bridge_patch._normal_extension_roots",
                return_value=(normal_root,),
            ):
                report = build_codex_isolated_bridge_patch(
                    source_extension_path=source,
                    isolated_extension_root=normal_root,
                    apply=True,
                ).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(report["decision"], "codex_isolated_bridge_patch_blocked")
        self.assertEqual(report["error"], "isolated_root_inside_normal_extension_profile")
        self.assertEqual(report["write_attempts"], 0)
        self.assertFalse(report["normal_profile_touched"])

    def test_missing_insertion_anchor_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_codex_extension(root / "openai.chatgpt-1.0.0")
            (source / "out" / "extension.js").write_text(
                (
                    "function activate(){"
                    'const a="shared-object-set";'
                    'const b="open-vscode-command";'
                    "function triggerNewChatViaWebview(){}"
                    "}"
                ),
                encoding="utf-8",
            )

            report = build_codex_isolated_bridge_patch(
                source_extension_path=source,
                isolated_extension_root=root / "isolated",
            ).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(report["decision"], "codex_isolated_bridge_patch_blocked")
        self.assertEqual(report["error"], "codex_extension_bridge_insertion_anchor_missing")
        self.assertEqual(report["write_attempts"], 0)

    def test_missing_auto_discovered_source_reports_source_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            report = build_codex_isolated_bridge_patch(
                isolated_extension_root=root / "isolated",
                installed_extension_roots=(root / "empty-extensions",),
            ).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(report["decision"], "codex_isolated_bridge_patch_blocked")
        self.assertEqual(report["error"], "codex_extension_source_not_found")
        self.assertEqual(report["write_attempts"], 0)


def _write_codex_extension(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "out").mkdir()
    (path / "webview" / "assets").mkdir(parents=True)
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "chatgpt",
                "publisher": "openai",
                "version": "1.0.0",
                "main": "./out/extension.js",
            }
        ),
        encoding="utf-8",
    )
    (path / "out" / "extension.js").write_text(
        (
            "function activate(t){let e=t.subscriptions;"
            "class Wl{};class hI{};"
            "const markerA='shared-object-set';"
            "const markerB='open-vscode-command';"
            "function triggerNewChatViaWebview(){}"
            "let Ue=new Wl(t.extensionUri);e.push(Ue);let _e=new hI(Ue);"
            "e.push(ut.window.registerUriHandler(_e));}"
        ),
        encoding="utf-8",
    )
    (path / "webview" / "assets" / "composer.js").write_text(
        "const key='composer_prefill';",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
