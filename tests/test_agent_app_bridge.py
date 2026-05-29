import unittest

from openwukong.control.agent_app_bridge import (
    AgentAppBridgeCdpAdapter,
    AgentAppBridgeDryRunAdapter,
    AgentAppBridgeNativeAdapter,
    build_agent_app_bridge_request,
)


class AgentAppBridgeTests(unittest.TestCase):
    def test_ready_native_probe_builds_dry_run_bridge_payload_without_send_attempts(self):
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={
                "transport_id": "claude-desktop-shell",
                "route_id": "claude-desktop-connector-required",
                "transport": "desktop-shell-native-bridge-or-foreground",
                "path": "C:/Program Files/WindowsApps/Claude/app/claude.exe",
                "pid": 11140,
            },
            app_surface_probe=_ready_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("DO_NOT_SEND",),
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_dry_run_ready")
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["request"]["ready"])
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])
        self.assertEqual(data["request"]["target"]["hwnd"], 138024)
        self.assertEqual(data["request"]["endpoint"]["debugger_url"], "http://127.0.0.1:9333")
        self.assertEqual(data["request"]["payload"]["message"], "Summarize the active task.")
        self.assertEqual(
            data["request"]["payload"]["required_markers"],
            ["OPENWUKONG_ACCEPTANCE: PASS"],
        )

    def test_dry_run_reports_native_endpoint_missing_without_falling_back_to_foreground(self):
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe={
                **_ready_probe(),
                "decision": "agent_native_connector_not_exposed",
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "endpoints": [],
            },
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_native_connector_not_ready")
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertTrue(data["request"]["target_ready"])
        self.assertFalse(data["request"]["native_endpoint_ready"])

    def test_dry_run_reports_target_missing_even_when_endpoint_exists(self):
        probe = _ready_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "project_match": {"decision": "missing"},
            "task_match": {"decision": "missing"},
        }
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="missing-project",
            task_name="missing-task",
            message="Summarize the active task.",
            composed_message="Project: missing-project\nTask: missing-task",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "app_bridge_target_not_ready")
        self.assertEqual(report.bridge_send_attempts, 0)

    def test_dry_run_prefers_project_window_when_agent_has_multiple_windows(self):
        probe = _ready_ide_bridge_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "matched_windows": [
                {
                    "process_name": "Cursor.exe",
                    "pid": 100,
                    "window_title": "start.md - other-project - Cursor",
                    "hwnd": 111,
                },
                {
                    "process_name": "Cursor.exe",
                    "pid": 200,
                    "window_title": "config - PaoPaoHeZi - Cursor",
                    "hwnd": 222,
                },
            ],
        }
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="PaoPaoHeZi",
            task_name="",
            message="Summarize the active task.",
            composed_message="Project: PaoPaoHeZi\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["request"]["target_ready"])
        self.assertEqual(data["request"]["target"]["pid"], 200)
        self.assertEqual(data["request"]["target"]["hwnd"], 222)

    def test_cdp_adapter_sends_message_to_ready_endpoint_and_verifies_markers(self):
        devtools = _FakeDevToolsClient(
            {
                "composerFound": True,
                "messageSet": True,
                "submitAttempted": True,
                "submitVerified": True,
                "readbackText": "OPENWUKONG_ACCEPTANCE: PASS\nSummarize the active task.",
            }
        )
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=_ready_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_send_accepted")
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["target"]["target_id"], "page-1")
        self.assertEqual(devtools.evaluate_calls[0][0], "http://127.0.0.1:9333")
        self.assertEqual(devtools.evaluate_calls[0][1].target_id, "page-1")
        self.assertIn("Summarize the active task.", devtools.evaluate_calls[0][2])

    def test_cdp_adapter_does_not_send_when_request_not_ready(self):
        devtools = _FakeDevToolsClient({})
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe={
                **_ready_probe(),
                "ready_endpoint_count": 0,
                "endpoints": [],
            },
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "app_bridge_request_not_ready")
        self.assertEqual(report.bridge_send_attempts, 0)
        self.assertEqual(report.native_call_attempts, 0)
        self.assertEqual(devtools.evaluate_calls, [])

    def test_cdp_adapter_reports_acceptance_pending_after_verified_submit(self):
        devtools = _FakeDevToolsClient(
            {
                "composerFound": True,
                "messageSet": True,
                "submitAttempted": True,
                "submitVerified": True,
                "readbackText": "Task submitted but result is still pending.",
            }
        )
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=_ready_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "app_bridge_message_submitted_acceptance_pending")
        self.assertEqual(report.bridge_send_attempts, 1)

    def test_native_adapter_sends_ide_bridge_chat_without_cdp_or_window_input(self):
        bridge = _FakeIDEBridgeClient(
            {
                "ok": True,
                "action_key": "ide-chat:1",
                "conversation": "OPENWUKONG_ACCEPTANCE: PASS\nCursor accepted.",
                "metadata": {
                    "adapter_id": "cursor",
                    "command_id": "cursor.chat.submit",
                    "ide_name": "Cursor",
                },
            }
        )
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="PaoPaoHeZi",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: PaoPaoHeZi\nTask: desktop-message\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_ready_ide_bridge_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )

        report = AgentAppBridgeNativeAdapter(ide_bridge_client=bridge).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_send_accepted")
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["transport"], "vscode-extension-bridge")
        self.assertEqual(data["action_result"]["adapter_id"], "cursor")
        self.assertEqual(data["action_result"]["command_id"], "cursor.chat.submit")
        self.assertEqual(bridge.chat_calls[0][0], "http://127.0.0.1:8787")
        self.assertEqual(bridge.chat_calls[0][2], "cursor")
        self.assertIn("Project: PaoPaoHeZi", bridge.chat_calls[0][3])


class _FakeDevToolsClient:
    def __init__(self, value):
        self.value = dict(value)
        self.evaluate_calls = []

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        return {"type": "object", "value": dict(self.value)}


class _FakeIDEBridgeClient:
    def __init__(self, value):
        self.value = dict(value)
        self.chat_calls = []

    def send_chat(self, bridge_url, target, adapter_id, message):
        self.chat_calls.append((bridge_url, target, adapter_id, message))
        return dict(self.value)


def _ready_probe():
    return {
        "mode": "agent-native-connector-probe",
        "decision": "agent_native_connector_ready",
        "control_attempts": 0,
        "endpoint_count": 1,
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "debugger_url": "http://127.0.0.1:9333",
                "ready": True,
                "targets": [
                    {
                        "target_id": "page-1",
                        "id": "page-1",
                        "type": "page",
                        "title": "Claude",
                        "url": "app://claude/index.html",
                        "ready": True,
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-1",
                    }
                ],
            }
        ],
        "app_uia_probe": {
            "decision": "agent_app_uia_ready",
            "target_matched": True,
            "composer_candidate_count": 1,
            "semantic_composer_count": 1,
            "background_screenshot_count": 1,
            "background_screenshot_success_count": 1,
            "background_screenshot_focus_stable": True,
            "matched_windows": [
                {
                    "process_name": "claude.exe",
                    "pid": 77064,
                    "window_title": "Claude",
                    "hwnd": 138024,
                }
            ],
        },
    }


def _ready_ide_bridge_probe():
    probe = _ready_probe()
    probe["endpoints"] = [
        {
            "endpoint_type": "ide_bridge",
            "bridge_url": "http://127.0.0.1:8787",
            "ready": True,
            "preferred_chat_adapter": "cursor",
            "adapter_mapping": {
                "cursor": {
                    "label": "Cursor Chat",
                    "commandId": "cursor.chat.submit",
                    "available": True,
                    "availableCandidates": ["cursor.chat.submit"],
                    "commandCandidates": ["cursor.chat.submit"],
                }
            },
            "chat_adapters": [
                {
                    "adapter_id": "cursor",
                    "label": "Cursor Chat",
                    "command_id": "cursor.chat.submit",
                    "available": True,
                    "available_candidates": ["cursor.chat.submit"],
                }
            ],
            "metadata": {"ide_name": "Cursor"},
        }
    ]
    return probe


if __name__ == "__main__":
    unittest.main()
