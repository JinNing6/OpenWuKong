import unittest

from openwukong.connectors import ConnectorTarget
from openwukong.control.fabric import ControlFabric, ControlIntent
from openwukong.control.session_discovery import DiscoveredControlTarget
from openwukong.control.session_ownership import SessionOwnership, SessionOwnershipIndex
from openwukong.control.session_registry import (
    ControlSession,
    SessionRegistry,
    build_session_registry_snapshot,
)


class _SemanticWindow:
    process_name = "notepad.exe"
    window_title = "notes.txt - Notepad"
    element_count = 8
    semantic_input_count = 1
    semantic_action_count = 2
    input_candidate_count = 1
    stable_identifier_count = 5
    text_readable_count = 3
    risks = ()


class SessionRegistryTests(unittest.TestCase):
    def test_registry_is_exported_from_control_package(self):
        from openwukong.control import SessionRegistry as ExportedSessionRegistry
        from openwukong.control import build_session_registry_snapshot as exported_builder

        self.assertIs(ExportedSessionRegistry, SessionRegistry)
        self.assertIs(exported_builder, build_session_registry_snapshot)

    def test_registers_discovered_browser_devtools_session(self):
        discovered = DiscoveredControlTarget(
            source=ConnectorTarget(
                process_name="chrome.exe",
                window_title="about:blank - Google Chrome",
                resource_url="about:blank",
            ),
            debugger_url="http://127.0.0.1:9237",
            resource_url="about:blank",
            evidence=(
                {
                    "kind": "browser_devtools",
                    "url": "http://127.0.0.1:9237",
                    "target_title": "about:blank",
                    "target_url": "about:blank",
                },
            ),
        )

        session = SessionRegistry().register(discovered)
        data = session.to_dict()

        self.assertIsInstance(session, ControlSession)
        self.assertEqual(data["app_family"], "browser")
        self.assertTrue(data["background_safe"])
        self.assertEqual(data["preferred_route"], "browser-devtools-or-extension")
        self.assertIn("browser_devtools", data["capability_ids"])
        self.assertIn("dom_locator", data["capability_ids"])
        self.assertIn("set_input", data["action_ids"])
        self.assertEqual(data["target"]["debugger_url"], "http://127.0.0.1:9237")
        self.assertEqual(data["session_discovery"]["discovered_fields"]["debugger_url"], "http://127.0.0.1:9237")

    def test_control_fabric_can_dispatch_registered_session(self):
        session = SessionRegistry().register(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Example - Google Chrome",
                resource_url="https://example.test/",
                debugger_url="http://127.0.0.1:9222",
            )
        )

        report = ControlFabric.with_default_connectors().dispatch(
            session,
            ControlIntent(action="read_page"),
        ).to_dict()

        self.assertEqual(report["decision"], "dispatch_connector")
        self.assertEqual(report["selected_connector_id"], "browser")
        self.assertEqual(report["target"]["debugger_url"], "http://127.0.0.1:9222")

    def test_registers_manifest_ownership_for_matching_session(self):
        ownership = SessionOwnership(
            owned=True,
            ownership_source="session_readiness_manifest",
            manifest_path="browser.json",
            route_id="browser-devtools-or-extension",
            connector_id="browser",
            action_id="launch_browser_devtools_isolated",
            endpoint="http://127.0.0.1:9222",
            profile_path="E:/tmp/profile",
            cleanup_ready=True,
        )
        session = SessionRegistry(
            ownership_index=SessionOwnershipIndex((ownership,))
        ).register(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Example - Google Chrome",
                resource_url="https://example.test/",
                debugger_url="http://127.0.0.1:9222",
            )
        )
        data = session.to_dict()

        self.assertTrue(data["ownership"]["owned"])
        self.assertEqual(data["ownership"]["manifest_path"], "browser.json")
        self.assertTrue(data["ownership"]["cleanup_ready"])

    def test_merges_repeated_discovery_for_same_control_session(self):
        registry = SessionRegistry()
        first = registry.register(
            ConnectorTarget(
                process_name="chrome.exe",
                window_title="Example - Google Chrome",
                resource_url="https://example.test/",
            )
        )
        second = registry.register(
            DiscoveredControlTarget(
                source=ConnectorTarget(
                    process_name="chrome.exe",
                    window_title="Example - Google Chrome",
                    resource_url="https://example.test/",
                ),
                debugger_url="http://127.0.0.1:9222",
                resource_url="https://example.test/",
                evidence=({"kind": "browser_devtools", "url": "http://127.0.0.1:9222"},),
            )
        )
        snapshot = registry.snapshot().to_dict()

        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(snapshot["session_count"], 1)
        self.assertEqual(snapshot["sessions"][0]["target"]["debugger_url"], "http://127.0.0.1:9222")
        self.assertIn("browser_devtools", snapshot["sessions"][0]["capability_ids"])

    def test_merges_repeated_capability_evidence_without_duplicate_sessions(self):
        registry = SessionRegistry()
        for port in (9222, 9222):
            registry.register(
                DiscoveredControlTarget(
                    source=ConnectorTarget(
                        process_name="chrome.exe",
                        window_title="Example - Google Chrome",
                        resource_url="https://example.test/",
                    ),
                    debugger_url=f"http://127.0.0.1:{port}",
                    resource_url="https://example.test/",
                    evidence=(
                        {
                            "kind": "browser_devtools",
                            "url": f"http://127.0.0.1:{port}",
                            "target_url": "https://example.test/",
                        },
                    ),
                )
            )

        snapshot = registry.snapshot().to_dict()

        self.assertEqual(snapshot["session_count"], 1)
        browser_capability = next(
            item
            for item in snapshot["sessions"][0]["capabilities"]
            if item["capability_id"] == "browser_devtools"
        )
        self.assertEqual(len(browser_capability["evidence"]), 1)

    def test_registers_terminal_workspace_as_background_safe_command_session(self):
        session = SessionRegistry().register(
            ConnectorTarget(
                process_name="pwsh.exe",
                window_title="openwukong - PowerShell",
                workspace_path="E:/ideaProjects/agent/openwukong",
            )
        )
        data = session.to_dict()

        self.assertEqual(data["app_family"], "terminal")
        self.assertEqual(data["preferred_route"], "terminal-native-session")
        self.assertTrue(data["background_safe"])
        self.assertIn("terminal_native_session", data["capability_ids"])
        self.assertIn("run_command", data["action_ids"])
        self.assertEqual(data["target"]["workspace_path"], "E:/ideaProjects/agent/openwukong")

    def test_registers_command_process_broker_snapshot_as_background_session(self):
        broker_snapshot = {
            "mode": "command-process-broker-snapshot",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": 0,
            "active_count": 1,
            "stale_count": 0,
            "processes": [
                {
                    "process_id": "proc-1",
                    "pid": 4242,
                    "argv": ["python.exe", "-m", "http.server", "8765"],
                    "cwd": "E:/ideaProjects/agent/openwukong",
                    "running": True,
                    "exit_code": None,
                    "started_at": 123.0,
                    "restored": True,
                    "reason": "background dev server",
                    "effects": ["workspace_write", "network"],
                    "ownership": {
                        "owned": True,
                        "ownership_source": "test",
                        "route_id": "terminal-native-session",
                        "connector_id": "terminal",
                        "workspace_root": "E:/ideaProjects/agent/openwukong",
                    },
                }
            ],
            "stale_processes": [],
            "broker": {
                "workspace_root": "E:/ideaProjects/agent/openwukong",
                "storage_path": "E:/ideaProjects/agent/openwukong/logs/runtime/processes.json",
                "profile_id": "network-enabled",
            },
        }

        snapshot = build_session_registry_snapshot(
            [],
            process_broker_snapshots=[broker_snapshot],
        ).to_dict()
        session = snapshot["sessions"][0]

        self.assertEqual(snapshot["session_count"], 1)
        self.assertEqual(snapshot["app_family_counts"], {"managed-process": 1})
        self.assertEqual(
            snapshot["preferred_route_counts"],
            {"command-process-broker": 1},
        )
        self.assertEqual(session["app_family"], "managed-process")
        self.assertEqual(session["preferred_route"], "command-process-broker")
        self.assertTrue(session["background_safe"])
        self.assertIn("command_process_broker", session["capability_ids"])
        self.assertIn("read_process_snapshot", session["action_ids"])
        self.assertIn("stop_process", session["action_ids"])
        self.assertEqual(session["target"]["session_id"], "command-process:proc-1")
        self.assertEqual(session["target"]["pid"], 4242)
        self.assertEqual(session["target"]["process_name"], "python.exe")
        self.assertEqual(session["target"]["workspace_path"], "E:/ideaProjects/agent/openwukong")
        self.assertEqual(
            session["session_discovery"]["discovered_fields"]["process_id"],
            "proc-1",
        )
        self.assertEqual(
            session["capabilities"][0]["evidence"][0]["effects"],
            ["workspace_write", "network"],
        )
        self.assertTrue(session["ownership"]["owned"])

    def test_registers_uia_semantic_window_as_foreground_or_accessibility_session(self):
        session = SessionRegistry().register(_SemanticWindow())
        data = session.to_dict()

        self.assertEqual(data["app_family"], "generic-desktop")
        self.assertEqual(data["preferred_route"], "uia-semantic")
        self.assertFalse(data["background_safe"])
        self.assertIn("uia_semantic", data["capability_ids"])
        self.assertIn("set_text", data["action_ids"])
        self.assertIn("click", data["action_ids"])

    def test_builds_snapshot_from_mixed_targets(self):
        snapshot = build_session_registry_snapshot(
            [
                ConnectorTarget(
                    process_name="chrome.exe",
                    window_title="Example - Google Chrome",
                    resource_url="https://example.test/",
                    debugger_url="http://127.0.0.1:9222",
                ),
                ConnectorTarget(
                    process_name="cursor.exe",
                    window_title="openwukong - Cursor",
                    ide_bridge_url="http://127.0.0.1:8787",
                ),
                _SemanticWindow(),
            ]
        ).to_dict()

        self.assertEqual(snapshot["mode"], "session-registry-snapshot")
        self.assertEqual(snapshot["control_attempts"], 0)
        self.assertEqual(snapshot["session_count"], 3)
        self.assertEqual(
            snapshot["app_family_counts"],
            {"browser": 1, "generic-desktop": 1, "ide": 1},
        )
        self.assertEqual(
            snapshot["preferred_route_counts"]["browser-devtools-or-extension"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
