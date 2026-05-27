import json
import tempfile
import unittest
from pathlib import Path

from openwukong.connectors import ConnectorTarget
from openwukong.control.session_ownership import (
    SessionOwnership,
    SessionOwnershipIndex,
    build_ownership_index,
    load_readiness_manifest_ownership,
)


def _write_manifest(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class SessionOwnershipTests(unittest.TestCase):
    def test_exports_ownership_api_from_control_package(self):
        from openwukong.control import (
            SessionOwnership as ExportedSessionOwnership,
            SessionOwnershipIndex as ExportedSessionOwnershipIndex,
            build_ownership_index as exported_build_ownership_index,
        )

        self.assertIs(ExportedSessionOwnership, SessionOwnership)
        self.assertIs(ExportedSessionOwnershipIndex, SessionOwnershipIndex)
        self.assertIs(exported_build_ownership_index, build_ownership_index)

    def test_loads_browser_devtools_ownership_from_readiness_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = str(Path(tmp) / "chrome-profile").replace("\\", "/")
            manifest = _write_manifest(
                Path(tmp) / "browser.json",
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "launches": [
                        {
                            "action_id": "launch_browser_devtools_isolated",
                            "route_id": "browser-devtools-or-extension",
                            "connector_id": "browser",
                            "status": "started",
                            "pid": 4242,
                            "readiness_url": "http://127.0.0.1:9237",
                            "argv": [
                                "chrome.exe",
                                "--remote-debugging-port=9237",
                                f"--user-data-dir={profile}",
                            ],
                        }
                    ],
                },
            )

            ownerships = load_readiness_manifest_ownership(manifest)

        self.assertEqual(len(ownerships), 1)
        ownership = ownerships[0]
        self.assertTrue(ownership.owned)
        self.assertEqual(ownership.route_id, "browser-devtools-or-extension")
        self.assertEqual(ownership.connector_id, "browser")
        self.assertEqual(ownership.endpoint, "http://127.0.0.1:9237")
        self.assertEqual(ownership.pid, 4242)
        self.assertEqual(ownership.profile_path, profile)
        self.assertTrue(ownership.cleanup_ready)

    def test_ownership_index_matches_browser_by_exact_debugger_endpoint(self):
        ownership = SessionOwnership(
            owned=True,
            ownership_source="session_readiness_manifest",
            manifest_path="browser.json",
            route_id="browser-devtools-or-extension",
            connector_id="browser",
            pid=4242,
            endpoint="http://127.0.0.1:9237",
            profile_path="E:/tmp/profile",
            cleanup_ready=True,
        )
        index = SessionOwnershipIndex((ownership,))

        matched = index.match(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                debugger_url="http://127.0.0.1:9237",
            )
        )
        unmatched = index.match(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                debugger_url="http://127.0.0.1:9238",
            )
        )

        self.assertTrue(matched.owned)
        self.assertEqual(matched.manifest_path, "browser.json")
        self.assertFalse(unmatched.owned)

    def test_ownership_index_matches_ide_bridge_by_endpoint_and_workspace(self):
        ownership = SessionOwnership(
            owned=True,
            ownership_source="session_readiness_manifest",
            manifest_path="ide.json",
            route_id="ide-extension-connector",
            connector_id="ide-extension",
            pid=5151,
            endpoint="http://127.0.0.1:8787",
            profile_path="E:/tmp/cursor-user-data",
            workspace_root="E:/ideaProjects/agent/openwukong",
            cleanup_ready=True,
        )
        index = SessionOwnershipIndex((ownership,))

        matched = index.match(
            ConnectorTarget(
                process_name="cursor.exe",
                window_title="openwukong - Cursor",
                ide_bridge_url="http://127.0.0.1:8787",
                workspace_path="E:/ideaProjects/agent/openwukong",
            )
        )
        workspace_mismatch = index.match(
            ConnectorTarget(
                process_name="cursor.exe",
                window_title="other - Cursor",
                ide_bridge_url="http://127.0.0.1:8787",
                workspace_path="E:/ideaProjects/agent/other",
            )
        )

        self.assertTrue(matched.owned)
        self.assertFalse(workspace_mismatch.owned)

    def test_builds_workspace_bound_terminal_ownership_from_manifest_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "openwukong").replace("\\", "/")
            manifest = _write_manifest(
                Path(tmp) / "terminal.json",
                {
                    "mode": "session-readiness-execution",
                    "safety_mode": "isolated_helper_launch",
                    "results": [
                        {
                            "action_id": "bind_terminal_workspace",
                            "route_id": "terminal-native-session",
                            "connector_id": "terminal",
                            "status": "workspace_bound",
                            "workspace_root": workspace,
                        }
                    ],
                },
            )

            index = build_ownership_index((manifest,))
            matched = index.match(
                ConnectorTarget(
                    process_name="pwsh.exe",
                    window_title="openwukong - PowerShell",
                    workspace_path=workspace,
                )
            )

        self.assertTrue(matched.owned)
        self.assertEqual(matched.route_id, "terminal-native-session")
        self.assertEqual(matched.workspace_root, workspace)
        self.assertFalse(matched.cleanup_ready)


if __name__ == "__main__":
    unittest.main()
