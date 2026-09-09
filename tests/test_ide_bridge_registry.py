import json
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.control.ide_bridge_registry import discover_ide_bridge_urls


class IDEBridgeRegistryTests(unittest.TestCase):
    def test_discovers_local_ide_bridge_urls_from_env_and_registry_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "ide-bridges"
            registry.mkdir()
            (registry / "cursor.json").write_text(
                json.dumps(
                    {
                        "schema_version": "openwukong-ide-bridge-registry-v1",
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18180",
                            },
                            {
                                "type": "ide_bridge",
                                "enabled": False,
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18181",
                            },
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Visual Studio Code",
                                "bridge_url": "http://127.0.0.1:18182",
                            },
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Cursor",
                                "bridge_url": "http://example.com:18183",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_ide_bridge_urls(
                ("http://127.0.0.1:18179",),
                target=ConnectorTarget(process_name="Cursor.exe", window_title="Cursor"),
                registry_paths=(str(registry),),
                environment={
                    "OPENWUKONG_IDE_BRIDGE_URLS": "http://127.0.0.1:18178 http://example.com:18177",
                },
            )

        self.assertEqual(
            urls,
            (
                "http://127.0.0.1:18179",
                "http://127.0.0.1:18178",
                "http://127.0.0.1:18180",
            ),
        )

    def test_default_paths_read_localappdata_openwukong_ide_bridge_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "OpenWukong" / "ide-bridges"
            registry.mkdir(parents=True)
            (registry / "bridge.json").write_text(
                json.dumps(
                    {
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18184",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_ide_bridge_urls(
                target=ConnectorTarget(process_name="Cursor.exe"),
                environment={"LOCALAPPDATA": str(root)},
            )

        self.assertEqual(urls, ("http://127.0.0.1:18184",))

    def test_workspace_target_filters_same_ide_family_registry_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "ide-bridges"
            registry.mkdir()
            workspace_a = Path(tmp) / "workspace-a"
            workspace_b = Path(tmp) / "workspace-b"
            workspace_a.mkdir()
            workspace_b.mkdir()
            (registry / "bridges.json").write_text(
                json.dumps(
                    {
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18185",
                                "workspace_folders": [
                                    {"fsPath": str(workspace_a)}
                                ],
                            },
                            {
                                "type": "ide_bridge",
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18186",
                                "workspace_folders": [
                                    {"uri": workspace_b.as_uri()}
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_ide_bridge_urls(
                target=ConnectorTarget(
                    process_name="Cursor.exe",
                    workspace_path=str(workspace_b),
                ),
                registry_paths=(registry,),
                environment={},
            )

        self.assertEqual(urls, ("http://127.0.0.1:18186",))

    def test_workspace_target_rejects_legacy_entry_without_workspace_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "ide-bridges"
            registry.mkdir()
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (registry / "bridge.json").write_text(
                json.dumps(
                    {
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "app_name": "Cursor",
                                "bridge_url": "http://127.0.0.1:18187",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_ide_bridge_urls(
                target=ConnectorTarget(
                    process_name="Cursor.exe",
                    workspace_path=str(workspace),
                ),
                registry_paths=(registry,),
                environment={},
            )

        self.assertEqual(urls, ())


if __name__ == "__main__":
    unittest.main()
