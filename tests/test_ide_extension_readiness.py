import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.ide_bridge_registry import IDE_BRIDGE_REGISTRY_SCHEMA_VERSION
from openwukong.evaluation.ide_extension_readiness import (
    probe_ide_extension_bridge_readiness,
)


class _HTTPProbe:
    def __init__(self, response=None, error=None, responses_by_path=None):
        self.response = dict(response or {})
        self.error = error
        self.responses_by_path = dict(responses_by_path or {})
        self.calls = []

    def post_json(self, url, payload, timeout=2.0):
        self.calls.append((url, dict(payload), timeout))
        if self.error:
            raise self.error
        for path, response in self.responses_by_path.items():
            if url.endswith(path):
                return dict(response)
        return dict(self.response)


class IDEExtensionReadinessTests(unittest.TestCase):
    def test_reports_ready_bridge_with_available_chat_adapter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            http = _HTTPProbe(
                responses_by_path={
                    "/v1/ide/capabilities": {
                        "ok": True,
                        "metadata": {"ide_name": "Cursor"},
                        "commands": ["cursor.chat.send", "composer.createNew"],
                        "chat_adapters": [
                            {
                                "adapter_id": "cursor",
                                "command_id": "cursor.chat.send",
                                "available": True,
                            }
                        ],
                    },
                    "/v1/ide/cursor/draft-hook": {
                        "ok": True,
                        "decision": "cursor_draft_hook_ready",
                        "mutation_strategy": "command_create_new_composer",
                    },
                }
            )

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["bridge_ready"])
        self.assertTrue(report["extension_installed"])
        self.assertTrue(report["can_execute_without_focus"])
        self.assertTrue(report["can_write_without_focus"])
        self.assertTrue(report["cursor_draft_hook_ready"])
        self.assertEqual(report["selected_chat_adapter"]["adapter_id"], "cursor")
        self.assertEqual(http.calls[0][0], "http://127.0.0.1:8787/v1/ide/capabilities")
        self.assertEqual(http.calls[0][1]["target"]["project_name"], "openwukong")
        self.assertEqual(http.calls[1][0], "http://127.0.0.1:8787/v1/ide/cursor/draft-hook")
        self.assertFalse(http.calls[1][1]["allow_write"])

    def test_default_readiness_does_not_probe_fixed_8787(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            http = _HTTPProbe(
                responses_by_path={
                    "/v1/ide/capabilities": {
                        "ok": True,
                        "metadata": {"ide_name": "Cursor"},
                    },
                }
            )

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                agent_id="cursor",
                http_probe=http,
                environment={},
            ).to_dict()

        self.assertEqual(report["status"], "bridge_unavailable")
        self.assertEqual(report["bridge_url"], "")
        self.assertEqual(report["bridge_urls"], [])
        self.assertEqual(http.calls, [])

    def test_discovers_dynamic_bridge_url_from_registry_without_fixed_probe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            registry_root = root / "ide-bridges"
            registry_root.mkdir()
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            (registry_root / "cursor-instance.json").write_text(
                json.dumps(
                    {
                        "schema_version": IDE_BRIDGE_REGISTRY_SCHEMA_VERSION,
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:45678",
                                "dynamic_port": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            http = _HTTPProbe(
                responses_by_path={
                    "/v1/ide/capabilities": {
                        "ok": True,
                        "metadata": {"ide_name": "Cursor"},
                        "commands": ["composer.createNew"],
                        "chat_adapters": [
                            {
                                "adapter_id": "cursor",
                                "command_id": "",
                                "available": False,
                            }
                        ],
                    },
                    "/v1/ide/cursor/draft-hook": {
                        "ok": True,
                        "decision": "cursor_draft_hook_ready",
                        "mutation_strategy": "command_create_new_composer",
                    },
                }
            )

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                agent_id="cursor",
                bridge_registry_paths=(registry_root,),
                http_probe=http,
                environment={},
            ).to_dict()

        self.assertEqual(report["bridge_url"], "http://127.0.0.1:45678")
        self.assertEqual(report["bridge_urls"], ["http://127.0.0.1:45678"])
        self.assertEqual(http.calls[0][0], "http://127.0.0.1:45678/v1/ide/capabilities")
        self.assertEqual(http.calls[1][0], "http://127.0.0.1:45678/v1/ide/cursor/draft-hook")
        self.assertEqual(report["status"], "ready")

    def test_reports_extension_not_installed_without_promoting_bridge_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            installed_root.mkdir()
            http = _HTTPProbe(error=TimeoutError("timed out"))

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "extension_not_installed")
        self.assertFalse(report["bridge_ready"])
        self.assertFalse(report["extension_installed"])
        self.assertIn("timed out", report["bridge_error"])
        self.assertFalse(report["can_write_without_focus"])

    def test_detects_installed_extension_package_written_with_utf8_bom(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0",
                encoding="utf-8-sig",
            )
            http = _HTTPProbe(error=ConnectionError("connection refused"))

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertTrue(report["extension_installed"])
        self.assertEqual(report["status"], "bridge_unavailable")

    def test_reports_stale_installed_extension_with_fixed_port_popup_risk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            installed = _write_installed_extension(
                installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0",
                legacy_fixed_port=True,
            )
            (installed / "src").mkdir()
            (installed / "src" / "extension.js").write_text(
                'const port = config.get("bridge.port", 8787);\n'
                'vscode.window.showWarningMessage(`OpenWukong bridge failed to start: ${error.message}`);\n',
                encoding="utf-8",
            )
            http = _HTTPProbe(error=ConnectionError("connection refused"))

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "installed_extension_stale")
        self.assertEqual(
            report["blocking_reason"],
            "installed_extension_uses_fixed_port_or_disruptive_autostart",
        )
        self.assertTrue(report["installed_extension_stale"])
        self.assertTrue(report["installed_instances"][0]["legacy_fixed_port_risk"])
        self.assertEqual(report["installed_instances"][0]["port_default"], 8787)
        self.assertTrue(report["installed_instances"][0]["auto_start_default"])
        self.assertTrue(report["installed_instances"][0]["source_disruptive_start_popup"])

    def test_reports_bridge_unavailable_when_extension_is_installed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            http = _HTTPProbe(error=ConnectionError("connection refused"))

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "bridge_unavailable")
        self.assertTrue(report["extension_installed"])
        self.assertFalse(report["bridge_ready"])
        self.assertEqual(report["blocking_reason"], "bridge_endpoint_unavailable")

    def test_reports_chat_adapter_unavailable_for_read_only_bridge(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            http = _HTTPProbe(
                {
                    "ok": True,
                    "metadata": {"ide_name": "Cursor"},
                    "commands": ["workbench.action.files.save"],
                    "chat_adapters": [
                        {
                            "adapter_id": "copilot",
                            "command_id": "",
                            "available": False,
                            "available_candidates": [],
                        }
                    ],
                }
            )

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="copilot",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "chat_adapter_unavailable")
        self.assertTrue(report["bridge_ready"])
        self.assertTrue(report["can_execute_without_focus"])
        self.assertFalse(report["can_write_without_focus"])
        self.assertEqual(report["blocking_reason"], "chat_adapter_not_available")

    def test_reports_stale_bridge_when_cursor_draft_hook_endpoint_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            extension_dir = _write_extension_scaffold(root / "source")
            installed_root = root / "cursor-extensions"
            _write_installed_extension(installed_root / "openwukong-local.openwukong-vscode-bridge-0.1.0")
            http = _HTTPProbe(
                responses_by_path={
                    "/v1/ide/capabilities": {
                        "ok": True,
                        "metadata": {"ide_name": "Cursor"},
                        "commands": ["composer.sendToAgent"],
                        "chat_adapters": [
                            {
                                "adapter_id": "cursor",
                                "command_id": "composer.sendToAgent",
                                "available": True,
                            }
                        ],
                    },
                    "/v1/ide/cursor/draft-hook": {
                        "ok": False,
                        "error": "not_found",
                    },
                }
            )

            report = probe_ide_extension_bridge_readiness(
                extension_dir=extension_dir,
                installed_extension_roots=(installed_root,),
                bridge_url="http://127.0.0.1:8787",
                agent_id="cursor",
                http_probe=http,
            ).to_dict()

        self.assertEqual(report["status"], "cursor_draft_hook_unavailable")
        self.assertTrue(report["bridge_ready"])
        self.assertFalse(report["cursor_draft_hook_ready"])
        self.assertFalse(report["can_write_without_focus"])
        self.assertEqual(report["blocking_reason"], "cursor_draft_hook_endpoint_missing_or_stale")


def _write_extension_scaffold(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "openwukong-vscode-bridge",
                "publisher": "openwukong-local",
                "version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_installed_extension(
    path: Path,
    *,
    encoding: str = "utf-8",
    legacy_fixed_port: bool = False,
) -> Path:
    path.mkdir(parents=True)
    package = {
        "name": "openwukong-vscode-bridge",
        "publisher": "openwukong-local",
        "version": "0.1.0",
    }
    if legacy_fixed_port:
        package["contributes"] = {
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
        }
    (path / "package.json").write_text(
        json.dumps(package),
        encoding=encoding,
    )
    return path


if __name__ == "__main__":
    unittest.main()
