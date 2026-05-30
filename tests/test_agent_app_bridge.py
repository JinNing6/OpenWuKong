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

    def test_target_visible_without_composer_reports_only_native_endpoint_missing(self):
        probe = _ready_probe()
        probe["decision"] = "agent_native_connector_not_exposed"
        probe["endpoint_count"] = 0
        probe["ready_endpoint_count"] = 0
        probe["endpoints"] = []
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "decision": "agent_app_uia_target_visible_input_not_found",
            "target_matched": True,
            "semantic_composer_count": 0,
            "composer_candidates": [],
            "submit_candidate_count": 3,
        }
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="",
            message="Summarize the active task.",
            composed_message="Project: openwukong\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_native_connector_not_ready")
        self.assertTrue(data["request"]["target_ready"])
        self.assertFalse(data["request"]["native_endpoint_ready"])
        self.assertEqual(data["validation_errors"], ["native_endpoint_not_ready"])

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

    def test_ide_bridge_endpoint_metadata_can_satisfy_target_without_uia_match(self):
        probe = _ready_ide_bridge_probe()
        probe["decision"] = "agent_app_target_not_visible"
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "decision": "agent_app_task_not_visible",
            "target_matched": False,
            "semantic_composer_count": 0,
            "matched_windows": [
                {
                    "process_name": "Cursor.exe",
                    "pid": 16484,
                    "window_title": "[Extension Development Host] workspace - Cursor",
                    "hwnd": 2491830,
                }
            ],
        }
        probe["endpoints"][0]["metadata"] = {
            "ide_name": "Cursor",
            "workspaceFolders": [],
            "activeTextEditor": {
                "fsPath": "E:\\ideaProjects\\agent\\openwukong\\logs\\runtime\\ide-bridge-r14\\workspace\\README.md"
            },
        }
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="workspace",
            task_name="isolated-ide-bridge",
            message="Summarize the active task.",
            composed_message="Project: workspace\nTask: isolated-ide-bridge",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_dry_run_ready")
        self.assertTrue(data["request"]["target_ready"])
        self.assertEqual(data["request"]["target"]["hwnd"], 2491830)
        self.assertEqual(data["request"]["endpoint"]["preferred_chat_adapter"], "cursor")

    def test_ide_bridge_cursor_adapter_cannot_satisfy_codex_app_request(self):
        probe = _ready_ide_bridge_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["metadata"] = {
            "ide_name": "Cursor",
            "workspaceFolders": [
                {
                    "name": "openwukong",
                    "fsPath": "E:\\ideaProjects\\agent\\openwukong",
                }
            ],
        }
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="isolated-ide-bridge",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: isolated-ide-bridge",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])
        self.assertEqual(data["request"]["endpoint"]["preferred_chat_adapter"], "cursor")

    def test_agent_native_bridge_endpoint_metadata_can_satisfy_target_without_uia_match(self):
        probe = _ready_agent_native_bridge_probe()
        probe["decision"] = "agent_app_target_not_visible"
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "decision": "agent_app_task_not_visible",
            "target_matched": False,
            "semantic_composer_count": 0,
            "matched_windows": [
                {
                    "process_name": "Codex.exe",
                    "pid": 32000,
                    "window_title": "Codex",
                    "hwnd": 2491830,
                }
            ],
        }
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: desktop-message",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_dry_run_ready")
        self.assertTrue(data["request"]["target_ready"])
        self.assertEqual(data["request"]["endpoint"]["endpoint_type"], "agent_native_bridge")
        self.assertEqual(data["request"]["endpoint"]["preferred_chat_adapter"], "codex")

    def test_agent_native_bridge_cli_surface_cannot_satisfy_app_request(self):
        probe = _ready_agent_native_bridge_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["metadata"]["surface_kind"] = "cli"
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: desktop-message",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_agent_native_bridge_unbound_endpoint_cannot_satisfy_app_request(self):
        probe = _ready_agent_native_bridge_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["metadata"].pop("app_binding", None)
        probe["endpoints"][0]["metadata"]["app_binding_ready"] = False
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: desktop-message",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_agent_native_bridge_wrong_app_binding_cannot_satisfy_app_request(self):
        probe = _ready_agent_native_bridge_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["metadata"]["app_binding"] = {
            "process_name": "Claude.exe",
            "pid": 77064,
            "hwnd": 138024,
            "window_title": "Claude",
        }
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: desktop-message",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_native_adapter_sends_agent_native_bridge_without_cdp_or_window_input(self):
        bridge = _FakeAgentNativeBridgeClient(
            {
                "ok": True,
                "sent": True,
                "foreground_focus_stable": True,
                "window_input_attempts": 0,
                "keyboard_input_attempts": 0,
                "clipboard_write_attempts": 0,
                "readbackText": "OPENWUKONG_ACCEPTANCE: PASS\nCodex accepted.",
            }
        )
        request = build_agent_app_bridge_request(
            agent="codex app",
            agent_id="codex",
            project_name="openwukong",
            task_name="desktop-message",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: desktop-message\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "codex-desktop-shell"},
            app_surface_probe=_ready_agent_native_bridge_probe(),
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )

        report = AgentAppBridgeNativeAdapter(agent_native_bridge_client=bridge).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_send_accepted")
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["transport"], "agent-native-bridge")
        self.assertEqual(data["action_result"]["bridge_url"], "http://127.0.0.1:18888")
        self.assertEqual(bridge.send_calls[0].agent_id, "codex")
        self.assertIn("Project: openwukong", bridge.send_calls[0].composed_message)

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
            [
                _ready_cdp_composer_probe(),
                {
                    "composerFound": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "OPENWUKONG_ACCEPTANCE: PASS\nSummarize the active task.",
                },
            ]
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
        self.assertEqual(data["native_probe_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["target"]["target_id"], "page-1")
        self.assertEqual(devtools.evaluate_calls[0][0], "http://127.0.0.1:9333")
        self.assertEqual(devtools.evaluate_calls[0][1].target_id, "page-1")
        self.assertTrue(data["composer_probe_report"]["ok"])
        self.assertEqual(data["composer_probe_report"]["decision"], "app_bridge_composer_ready")
        self.assertIn("composerSelectors", devtools.evaluate_calls[0][2])
        self.assertIn("Summarize the active task.", devtools.evaluate_calls[1][2])

    def test_cdp_adapter_does_not_send_without_safe_composer(self):
        devtools = _FakeDevToolsClient(
            {
                "composerFound": False,
                "composerCandidateCount": 0,
                "safeComposerCandidateCount": 0,
                "readbackText": "New Agent\nLoading Chat",
            }
        )
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="",
            message="OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
            composed_message="Project: openwukong\n\nMessage:\nOPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_ready_cursor_devtools_probe(),
            required_markers=("OPENWUKONG_APP_BRIDGE_REAL_NO_LOSS",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_composer_not_ready")
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertEqual(data["native_probe_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(len(devtools.evaluate_calls), 1)
        self.assertEqual(
            data["composer_probe_report"]["decision"],
            "app_bridge_composer_not_ready",
        )

    def test_cdp_adapter_allows_cursor_aislash_chat_composer_contract(self):
        devtools = _CursorAislashContractDevToolsClient()
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="",
            message="OPENWUKONG_CURSOR_AISLASH_CONTRACT",
            composed_message="Project: openwukong\n\nMessage:\nOPENWUKONG_CURSOR_AISLASH_CONTRACT",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_ready_cursor_devtools_probe(),
            required_markers=("OPENWUKONG_CURSOR_AISLASH_CONTRACT",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "app_bridge_send_accepted")
        self.assertEqual(data["native_probe_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(
            data["composer_probe_report"]["action_result"]["selectedComposer"][
                "productComposerContract"
            ],
            "cursor-agent-chat-aislash-editor-input",
        )
        self.assertIn(".aislash-editor-input", devtools.evaluate_calls[0][2])
        self.assertIn("cursor-agent-chat-aislash-editor-input", devtools.evaluate_calls[0][2])
        self.assertIn(".aislash-editor-input", devtools.evaluate_calls[1][2])
        self.assertIn("cursor-agent-chat-aislash-editor-input", devtools.evaluate_calls[1][2])

    def test_cdp_adapter_send_expression_has_no_submit_cleanup_guard(self):
        devtools = _NoSubmitCleanupGuardDevToolsClient()
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="",
            message="OPENWUKONG_CURSOR_NO_SUBMIT_CLEANUP",
            composed_message="Project: openwukong\n\nMessage:\nOPENWUKONG_CURSOR_NO_SUBMIT_CLEANUP",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=_ready_cursor_devtools_probe(),
            required_markers=("OPENWUKONG_CURSOR_NO_SUBMIT_CLEANUP",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_submit_not_verified")
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["action_result"]["cleanupAttempted"], True)
        self.assertEqual(data["action_result"]["cleanupVerified"], True)
        self.assertIn("cleanupAttempted", devtools.evaluate_calls[1][2])
        self.assertIn("originalText", devtools.evaluate_calls[1][2])
        self.assertIn("data-lexical-editor", devtools.evaluate_calls[1][2])
        self.assertIn("execCommand('insertText'", devtools.evaluate_calls[1][2])
        self.assertIn("execCommand('delete'", devtools.evaluate_calls[1][2])
        self.assertIn("async ()", devtools.evaluate_calls[1][2])
        self.assertIn("await sleep", devtools.evaluate_calls[1][2])
        self.assertIn("cleanupTargetText", devtools.evaluate_calls[1][2])
        self.assertIn("cleanupIndex", devtools.evaluate_calls[1][2])
        self.assertIn("selectNodeContents", devtools.evaluate_calls[1][2])
        self.assertIn("codicon-arrow-up-two", devtools.evaluate_calls[1][2])
        self.assertIn("submitWaitIndex", devtools.evaluate_calls[1][2])
        self.assertIn("anysphere-icon-button", devtools.evaluate_calls[1][2])
        self.assertIn("postComposerText", devtools.evaluate_calls[1][2])

    def test_bound_devtools_endpoint_is_ready_without_uia_semantic_composer(self):
        probe = _ready_probe()
        probe["app_uia_probe"]["composer_candidate_count"] = 0
        probe["app_uia_probe"]["semantic_composer_count"] = 0
        probe["endpoints"][0]["process"] = {
            "process_name": "claude.exe",
            "pid": 77064,
            "executable_path": "C:/Program Files/WindowsApps/Claude/app/claude.exe",
        }
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_devtools_page_target_project_can_satisfy_target_without_uia_match(self):
        probe = _ready_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["process"] = {
            "process_name": "Cursor.exe",
            "pid": 13592,
            "executable_path": "E:/cursor/cursor/cursor/Cursor.exe",
        }
        probe["endpoints"][0]["targets"] = [
            {
                "target_id": "cursor-workbench",
                "id": "cursor-workbench",
                "type": "page",
                "title": "openwukong - Cursor",
                "url": "vscode-file://vscode-app/e:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                "ready": True,
            }
        ]
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="",
            message="Summarize the active task.",
            composed_message="Project: openwukong\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "app_bridge_dry_run_ready")
        self.assertTrue(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_devtools_page_target_without_project_context_stays_blocked(self):
        probe = _ready_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["process"] = {
            "process_name": "Cursor.exe",
            "pid": 13592,
        }
        probe["endpoints"][0]["targets"] = [
            {
                "target_id": "cursor-workbench",
                "id": "cursor-workbench",
                "type": "page",
                "title": "other-project - Cursor",
                "url": "vscode-file://vscode-app/e:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                "ready": True,
            }
        ]
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="",
            message="Summarize the active task.",
            composed_message="Project: openwukong\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_devtools_page_target_without_task_context_stays_blocked(self):
        probe = _ready_probe()
        probe["app_uia_probe"] = {
            **probe["app_uia_probe"],
            "target_matched": False,
            "semantic_composer_count": 0,
        }
        probe["endpoints"][0]["process"] = {
            "process_name": "Cursor.exe",
            "pid": 13592,
        }
        probe["endpoints"][0]["targets"] = [
            {
                "target_id": "cursor-workbench",
                "id": "cursor-workbench",
                "type": "page",
                "title": "openwukong - Cursor",
                "url": "vscode-file://vscode-app/e:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                "ready": True,
            }
        ]
        request = build_agent_app_bridge_request(
            agent="cursor",
            agent_id="cursor",
            project_name="openwukong",
            task_name="missing-task",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: missing-task",
            selected_transport={"transport_id": "cursor-desktop-shell"},
            app_surface_probe=probe,
        )

        report = AgentAppBridgeDryRunAdapter().prepare(request)
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "app_bridge_target_not_ready")
        self.assertFalse(data["request"]["target_ready"])
        self.assertTrue(data["request"]["native_endpoint_ready"])

    def test_cdp_adapter_prefers_target_matching_project_or_task(self):
        devtools = _FakeDevToolsClient(
            [
                _ready_cdp_composer_probe(),
                {
                    "composerFound": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "OPENWUKONG_ACCEPTANCE: PASS\nTarget matched.",
                },
            ]
        )
        probe = _ready_probe()
        probe["endpoints"][0]["targets"] = [
            {
                "target_id": "page-settings",
                "id": "page-settings",
                "type": "page",
                "title": "Settings",
                "url": "app://claude/settings.html",
                "ready": True,
                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-settings",
            },
            {
                "target_id": "page-openwukong",
                "id": "page-openwukong",
                "type": "page",
                "title": "openwukong - bridge-contract",
                "url": "app://claude/chat/openwukong/bridge-contract",
                "ready": True,
                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-openwukong",
            },
        ]
        request = build_agent_app_bridge_request(
            agent="claude desktop",
            agent_id="claude",
            project_name="openwukong",
            task_name="bridge-contract",
            message="Summarize the active task.",
            composed_message="Project: openwukong\nTask: bridge-contract\n\nMessage:\nSummarize the active task.",
            selected_transport={"transport_id": "claude-desktop-shell"},
            app_surface_probe=probe,
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )

        report = AgentAppBridgeCdpAdapter(devtools_client=devtools).send(request)
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(devtools.evaluate_calls[0][1].target_id, "page-openwukong")

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
            [
                _ready_cdp_composer_probe(),
                {
                    "composerFound": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "Task submitted but result is still pending.",
                },
            ]
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
        self.values = list(value) if isinstance(value, list) else [dict(value)]
        self.evaluate_calls = []

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        value = self.values.pop(0) if len(self.values) > 1 else self.values[0]
        return {"type": "object", "value": dict(value)}


class _CursorAislashContractDevToolsClient:
    def __init__(self):
        self.evaluate_calls = []

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        has_contract = (
            ".aislash-editor-input" in expression
            and "cursor-agent-chat-aislash-editor-input" in expression
        )
        if "selectedComposer" in expression:
            return {
                "type": "object",
                "value": {
                    "composerFound": has_contract,
                    "safeComposerFound": has_contract,
                    "composerCandidateCount": 1,
                    "safeComposerCandidateCount": 1 if has_contract else 0,
                    "selectedComposer": {
                        "tag": "DIV",
                        "role": "textbox",
                        "className": "aislash-editor-input",
                        "safeChatHint": False,
                        "productComposerContract": (
                            "cursor-agent-chat-aislash-editor-input"
                            if has_contract
                            else ""
                        ),
                    }
                    if has_contract
                    else None,
                    "readbackText": "openwukong\nNew Agent\nPlan, Build, / for commands, @ for context",
                },
            }
        return {
            "type": "object",
            "value": {
                "composerFound": has_contract,
                "safeComposerFound": has_contract,
                "composerCandidateCount": 1,
                "safeComposerCandidateCount": 1 if has_contract else 0,
                "messageSet": has_contract,
                "submitAttempted": has_contract,
                "submitVerified": has_contract,
                "readbackText": (
                    "OPENWUKONG_CURSOR_AISLASH_CONTRACT"
                    if has_contract
                    else "New Agent"
                ),
            },
        }


class _NoSubmitCleanupGuardDevToolsClient:
    def __init__(self):
        self.evaluate_calls = []

    def evaluate(self, debugger_url, target, expression):
        self.evaluate_calls.append((debugger_url, target, expression))
        if "selectedComposer" in expression:
            return {"type": "object", "value": _ready_cdp_composer_probe()}
        has_cleanup_guard = "cleanupAttempted" in expression and "originalText" in expression
        return {
            "type": "object",
            "value": {
                "composerFound": True,
                "safeComposerFound": True,
                "composerCandidateCount": 1,
                "safeComposerCandidateCount": 1,
                "messageSet": True,
                "submitAttempted": False,
                "submitVerified": False,
                "cleanupAttempted": has_cleanup_guard,
                "cleanupVerified": has_cleanup_guard,
                "readbackText": "New Agent",
            },
        }


class _FakeIDEBridgeClient:
    def __init__(self, value):
        self.value = dict(value)
        self.chat_calls = []

    def send_chat(self, bridge_url, target, adapter_id, message):
        self.chat_calls.append((bridge_url, target, adapter_id, message))
        return dict(self.value)


class _FakeAgentNativeBridgeClient:
    def __init__(self, value):
        self.value = dict(value)
        self.capability_calls = []
        self.send_calls = []

    def read_capabilities(self, request):
        self.capability_calls.append(request)
        return {
            "ok": True,
            "background_safe": True,
            "surface_kind": "desktop_app",
            "app_binding": {
                "process_name": "Codex.exe",
                "pid": 77064,
                "hwnd": 138024,
                "window_title": "Codex",
            },
            "capabilities": ["agent_app_conversation.native_bridge_send_message"],
            "agents": [{"agent_id": request.agent_id, "available": True}],
            "projects": [{"name": request.project_name, "available": True}],
            "tasks": [{"name": request.task_name, "available": True}],
        }

    def send_message(self, request):
        self.send_calls.append(request)
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


def _ready_cdp_composer_probe():
    return {
        "composerFound": True,
        "safeComposerFound": True,
        "composerCandidateCount": 1,
        "safeComposerCandidateCount": 1,
        "selectedComposer": {
            "tag": "TEXTAREA",
            "placeholder": "Plan, Build, / for commands, @ for context",
            "safeChatHint": True,
        },
        "readbackText": "New Agent\nPlan, Build, / for commands, @ for context",
    }


def _ready_cursor_devtools_probe():
    probe = _ready_probe()
    probe["agent"] = "cursor"
    probe["agent_id"] = "cursor"
    probe["project_name"] = "openwukong"
    probe["task_name"] = ""
    probe["endpoints"] = [
        {
            "endpoint_type": "devtools",
            "debugger_url": "http://127.0.0.1:19557",
            "ready": True,
            "process": {
                "process_name": "Cursor.exe",
                "pid": 13592,
                "executable_path": "E:/cursor/cursor/cursor/Cursor.exe",
            },
            "targets": [
                {
                    "target_id": "cursor-workbench",
                    "id": "cursor-workbench",
                    "type": "page",
                    "title": "openwukong - Cursor",
                    "url": "vscode-file://vscode-app/e:/cursor/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                    "ready": True,
                }
            ],
        }
    ]
    probe["app_uia_probe"] = {
        **probe["app_uia_probe"],
        "target_matched": False,
        "semantic_composer_count": 0,
    }
    return probe


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


def _ready_agent_native_bridge_probe():
    probe = _ready_probe()
    probe["endpoints"] = [
        {
            "endpoint_type": "agent_native_bridge",
            "bridge_url": "http://127.0.0.1:18888",
            "debugger_url": "http://127.0.0.1:18888",
            "ready": True,
            "preferred_chat_adapter": "codex",
            "send_command_id": "agent_app_conversation.native_bridge_send_message",
            "metadata": {
                "agent_id": "codex",
                "surface_kind": "desktop_app",
                "app_binding_ready": True,
                "app_binding": {
                    "process_name": "Codex.exe",
                    "pid": 77064,
                    "hwnd": 138024,
                    "window_title": "Codex",
                },
                "projects": [{"name": "openwukong", "available": True}],
                "tasks": [{"name": "desktop-message", "available": True}],
            },
        }
    ]
    return probe


if __name__ == "__main__":
    unittest.main()
