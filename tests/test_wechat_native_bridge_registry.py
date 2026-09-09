import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.wechat_native_bridge_registry import (
    ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS,
    ENV_WECHAT_NATIVE_BRIDGE_URLS,
    discover_wechat_native_bridge_urls,
)


class WeChatNativeBridgeRegistryTests(unittest.TestCase):
    def test_discovers_local_wechat_bridge_urls_from_explicit_env_and_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "wechat-native-bridges.json"
            registry.write_text(
                json.dumps(
                    {
                        "wechat_native_bridges": [
                            {
                                "type": "wechat_native_bridge",
                                "bridge_url": "http://127.0.0.1:18180",
                                "enabled": True,
                            },
                            {
                                "type": "wechat_native_bridge",
                                "bridge_url": "http://example.com:18180",
                            },
                            {
                                "type": "agent_native_bridge",
                                "bridge_url": "http://127.0.0.1:18181",
                            },
                            {
                                "type": "wechat_native_bridge",
                                "bridge_url": "http://127.0.0.1:18182",
                                "disabled": True,
                            },
                        ],
                        "bridges": [
                            {
                                "kind": "wechat",
                                "url": "http://localhost:18183/",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_wechat_native_bridge_urls(
                ("http://127.0.0.1:18179",),
                registry_paths=(registry,),
                environment={
                    ENV_WECHAT_NATIVE_BRIDGE_URLS: "http://127.0.0.1:18184",
                    ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS: "",
                },
            )

        self.assertEqual(
            urls,
            (
                "http://127.0.0.1:18179",
                "http://127.0.0.1:18184",
                "http://127.0.0.1:18180",
                "http://localhost:18183",
            ),
        )

    def test_default_registry_paths_use_local_appdata_and_programdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "local"
            program = root / "program"
            local_registry = local / "OpenWukong" / "wechat-native-bridges.json"
            program_registry = program / "OpenWukong" / "wechat-native-bridges.json"
            local_registry.parent.mkdir(parents=True)
            program_registry.parent.mkdir(parents=True)
            local_registry.write_text(
                json.dumps(
                    {
                        "wechat_bridges": [
                            {"bridge_url": "http://127.0.0.1:18185"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            program_registry.write_text(
                json.dumps(
                    {
                        "wechat_native_bridges": [
                            {"bridge_url": "http://127.0.0.1:18186"}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            urls = discover_wechat_native_bridge_urls(
                environment={
                    "LOCALAPPDATA": str(local),
                    "PROGRAMDATA": str(program),
                    ENV_WECHAT_NATIVE_BRIDGE_URLS: "",
                    ENV_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS: "",
                }
            )

        self.assertEqual(
            urls,
            ("http://127.0.0.1:18185", "http://127.0.0.1:18186"),
        )


if __name__ == "__main__":
    unittest.main()
