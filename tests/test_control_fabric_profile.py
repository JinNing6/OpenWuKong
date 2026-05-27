import contextlib
import io
import json
import tempfile
import unittest

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.control_fabric_profile import main


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


def _window(process_name: str, title: str, elements):
    return AccessibilityWindowSnapshot(
        pid=2026,
        process_name=process_name,
        window_title=title,
        class_name="Chrome_WidgetWin_1",
        elements=tuple(elements),
    )


class ControlFabricProfileTests(unittest.TestCase):
    def test_cli_outputs_unified_dispatch_profile_from_static_observer(self):
        observer = StaticAccessibilityObserver(
            [
                _window(
                    "Cursor.exe",
                    "openwukong - Cursor",
                    [_element("Document", name="editor", patterns=("Text",))],
                ),
                _window(
                    "notepad.exe",
                    "Untitled - Notepad",
                    [_element("Edit", name="Text editor", patterns=("Value", "Text"))],
                ),
                _window("Weixin.exe", "微信", []),
            ]
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--json"], observer=observer)

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "control-fabric-profile")
        self.assertEqual(data["safety_mode"], "plan_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_count"], 3)
        self.assertEqual(data["summary"]["connector_missing"], 1)
        self.assertEqual(data["summary"]["connector_installed_not_ready"], 0)
        self.assertEqual(data["decision_counts"]["connector_required"], 1)
        self.assertEqual(data["decision_counts"]["dispatch_background_uia"], 1)
        self.assertEqual(data["decision_counts"]["blocked"], 1)
        self.assertEqual(data["execution_mode_counts"]["none"], 2)
        self.assertEqual(data["execution_mode_counts"]["background_uia"], 1)
        self.assertEqual(len(data["dispatch_plans"]), 3)

    def test_cli_can_bind_default_connectors_without_executing_control(self):
        observer = StaticAccessibilityObserver(
            [
                _window(
                    "Cursor.exe",
                    "openwukong - Cursor",
                    [_element("Document", name="editor", patterns=("Text",))],
                )
            ]
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--with-default-connectors", "--json"], observer=observer)

        data = json.loads(stdout.getvalue())
        plan = data["dispatch_plans"][0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["safety_mode"], "plan_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(plan["decision"], "connector_required")
        self.assertEqual(data["summary"]["connector_missing"], 0)
        self.assertEqual(data["summary"]["connector_installed_not_ready"], 1)
        self.assertEqual(plan["candidate_connector_ids"], ["ide-extension"])
        self.assertIn("ide-extension", plan["installed_connector_ids"])
        self.assertFalse(plan["connector_ready"])

    def test_cli_can_discover_sessions_before_planning(self):
        class _FakeDiscovery:
            def enrich(self, target):
                from openwukong.control.session_discovery import DiscoveredControlTarget

                return DiscoveredControlTarget(
                    source=target,
                    debugger_url="",
                    ide_bridge_url="http://127.0.0.1:8787",
                    workspace_path="",
                    evidence=(
                        {
                            "kind": "ide_bridge",
                            "url": "http://127.0.0.1:8787",
                        },
                    ),
                )

        observer = StaticAccessibilityObserver(
            [
                _window(
                    "Cursor.exe",
                    "openwukong - Cursor",
                    [_element("Document", name="editor", patterns=("Text",))],
                )
            ]
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                ["--with-default-connectors", "--discover-sessions", "--json"],
                observer=observer,
                session_discovery=_FakeDiscovery(),
            )

        data = json.loads(stdout.getvalue())
        plan = data["dispatch_plans"][0]
        self.assertEqual(exit_code, 0)
        self.assertEqual(plan["decision"], "dispatch_connector")
        self.assertTrue(plan["connector_ready"])
        self.assertEqual(plan["target"]["ide_bridge_url"], "http://127.0.0.1:8787")
        self.assertEqual(plan["session_discovery"]["evidence"][0]["kind"], "ide_bridge")

    def test_cli_accepts_workspace_root_for_session_discovery(self):
        observer = StaticAccessibilityObserver(
            [
                _window(
                    "pwsh.exe",
                    "PowerShell",
                    [_element("Document", name="Console", patterns=("Text",))],
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--discover-sessions",
                        "--workspace-root",
                        tmp,
                        "--json",
                    ],
                    observer=observer,
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "control-fabric-profile")


if __name__ == "__main__":
    unittest.main()
