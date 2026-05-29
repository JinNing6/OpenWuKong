import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.agent_app_real_no_loss import (
    main,
    run_agent_app_real_no_loss,
)


class _FakeProbeReport:
    def __init__(self, **payload):
        self.payload = dict(payload)

    def to_dict(self):
        return dict(self.payload)


class AgentAppRealNoLossTests(unittest.TestCase):
    def test_runs_agent_app_probes_without_control_attempts_and_writes_artifacts(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            agent = kwargs["agent"]
            if agent == "claude desktop":
                return _FakeProbeReport(
                    mode="agent-native-connector-probe",
                    safety_mode="read_only",
                    ok=True,
                    decision="agent_native_connector_ready",
                    agent=agent,
                    project_name=kwargs["project_name"],
                    task_name=kwargs["task_name"],
                    control_allowed=False,
                    control_attempts=0,
                    endpoint_count=1,
                    ready_endpoint_count=1,
                    bridge_send_attempts=0,
                    app_uia_probe={
                        "matched_window_count": 1,
                        "target_matched": True,
                        "semantic_composer_count": 1,
                        "submit_candidate_count": 1,
                        "composer_candidates": [
                            {
                                "control_type": "Edit",
                                "name": "Write your prompt to Claude",
                                "is_enabled": True,
                                "visible": True,
                                "patterns": ["Value"],
                                "semantic_composer": True,
                            }
                        ],
                        "submit_candidates": [
                            {
                                "control_type": "Button",
                                "name": "Send",
                                "is_enabled": True,
                                "visible": True,
                                "patterns": ["Invoke"],
                            }
                        ],
                        "background_screenshot_count": 1,
                        "background_screenshot_success_count": 1,
                        "background_screenshot_focus_stable": True,
                    },
                )
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=agent,
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                bridge_send_attempts=0,
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_app_real_no_loss(
                agents=("codex app", "claude desktop"),
                project_name="openwukong",
                task_name="agent-app-real-no-loss",
                output_root=root,
                screenshot_dir=root / "screenshots",
                probe_runner=fake_probe_runner,
            )
            data = report.to_dict()

            artifact_paths = [Path(case["artifact_path"]) for case in data["cases"]]
            artifact_payloads = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in artifact_paths
            ]

        self.assertEqual([call["agent"] for call in calls], ["codex app", "claude desktop"])
        self.assertEqual(
            Path(calls[0]["screenshot_dir"]).resolve(),
            (root / "screenshots" / "codex_app").resolve(),
        )
        self.assertEqual(data["mode"], "agent-app-real-no-loss")
        self.assertEqual(data["safety_mode"], "real_no_loss")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["agent_command_attempts"], 0)
        self.assertEqual(data["total_cases"], 2)
        self.assertEqual(data["passed_cases"], 2)
        self.assertEqual(data["native_ready_cases"], 1)
        self.assertEqual(data["uia_semantic_action_ready_cases"], 1)
        self.assertEqual(data["gated_cases"], 1)
        self.assertEqual(data["real_verified_cases"], 2)
        self.assertEqual(data["background_screenshot_count"], 2)
        self.assertEqual(data["background_screenshot_success_count"], 2)
        self.assertTrue(data["background_screenshot_focus_stable"])
        self.assertEqual(data["cases"][0]["status"], "gated_native_endpoint_missing")
        self.assertEqual(data["cases"][1]["status"], "native_connector_ready")
        self.assertEqual(
            data["cases"][1]["uia_semantic_action_dry_run"]["decision"],
            "uia_semantic_action_dry_run_ready",
        )
        self.assertEqual(data["cases"][1]["uia_value_set_attempts"], 0)
        self.assertEqual(data["cases"][1]["uia_invoke_attempts"], 0)
        self.assertEqual(artifact_payloads[0]["probe"]["decision"], "agent_native_connector_not_exposed")

    def test_allow_app_bridge_send_executes_ready_native_bridge_without_window_input(self):
        sender_calls = []

        def fake_probe_runner(**kwargs):
            agent = kwargs["agent"]
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=agent,
                agent_id="claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                bridge_send_attempts=0,
                endpoints=[
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
                app_uia_probe={
                    "decision": "agent_app_uia_ready",
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
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
            )

        def fake_bridge_sender(request):
            sender_calls.append(request)
            return {
                "mode": "agent-app-bridge-send",
                "safety_mode": "native_bridge_execute",
                "ok": True,
                "decision": "app_bridge_send_accepted",
                "accepted": True,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "request": request.to_dict(),
                "action_result": {
                    "composerFound": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "OPENWUKONG_ACCEPTANCE: PASS",
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_app_real_no_loss(
                agents=("claude desktop",),
                project_name="openwukong",
                task_name="desktop-message",
                output_root=root,
                screenshot_dir=root / "screenshots",
                probe_runner=fake_probe_runner,
                allow_app_bridge_send=True,
                app_bridge_sender=fake_bridge_sender,
                bridge_message="Send this through the app surface.",
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            )
            data = report.to_dict()
            case = data["cases"][0]
            artifact = json.loads(Path(case["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(len(sender_calls), 1)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["app_bridge_send_verified_cases"], 1)
        self.assertEqual(data["gated_cases"], 0)
        self.assertEqual(case["status"], "app_bridge_send_accepted")
        self.assertTrue(case["app_bridge_send_verified"])
        self.assertEqual(case["bridge_send_attempts"], 1)
        self.assertEqual(case["app_bridge_dry_run"]["decision"], "app_bridge_dry_run_ready")
        self.assertEqual(case["app_bridge_send_report"]["decision"], "app_bridge_send_accepted")
        self.assertEqual(
            case["app_bridge_send_report"]["request"]["payload"]["message"],
            "Send this through the app surface.",
        )
        self.assertEqual(artifact["app_bridge_send_report"]["decision"], "app_bridge_send_accepted")

    def test_passes_explicit_ide_bridge_urls_to_native_probe(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_endpoint_unhealthy",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=0,
                endpoints=[
                    {
                        "endpoint_type": "ide_bridge",
                        "bridge_url": "http://127.0.0.1:8787",
                        "ready": False,
                        "error": "connection_failed",
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            )

        report = run_agent_app_real_no_loss(
            agents=("cursor",),
            project_name="PaoPaoHeZi",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            ide_bridge_urls=("http://127.0.0.1:8787",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        data = report.to_dict()

        self.assertEqual(calls[0]["ide_bridge_urls"], ("http://127.0.0.1:8787",))
        self.assertEqual(calls[0]["workspace_path"], "E:/ideaProjects/agent/openwukong")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["cases"][0]["probe"]["endpoints"][0]["endpoint_type"], "ide_bridge")

    def test_passes_explicit_agent_native_bridge_urls_to_native_probe(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="codex",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                endpoints=[
                    {
                        "endpoint_type": "agent_native_bridge",
                        "bridge_url": "http://127.0.0.1:18888",
                        "ready": True,
                        "preferred_chat_adapter": "codex",
                        "send_command_id": "agent_app_conversation.native_bridge_send_message",
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            agent_native_bridge_urls=("http://127.0.0.1:18888",),
        )
        data = report.to_dict()

        self.assertEqual(
            calls[0]["agent_native_bridge_urls"],
            ("http://127.0.0.1:18888",),
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["cases"][0]["status"], "native_connector_ready")
        self.assertEqual(
            data["cases"][0]["probe"]["endpoints"][0]["endpoint_type"],
            "agent_native_bridge",
        )

    def test_passes_agent_native_bridge_registry_paths_to_native_probe(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="codex",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                endpoints=[],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "native-bridges.json"
            report = run_agent_app_real_no_loss(
                agents=("codex app",),
                project_name="openwukong",
                task_name="desktop-message",
                probe_runner=fake_probe_runner,
                agent_native_bridge_registry_paths=(registry_path,),
            )
        data = report.to_dict()

        self.assertEqual(
            calls[0]["agent_native_bridge_registry_paths"],
            (registry_path,),
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)

    def test_app_bridge_sender_is_not_called_without_explicit_allow_flag(self):
        sender_calls = []

        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                endpoints=[
                    {
                        "debugger_url": "http://127.0.0.1:9333",
                        "ready": True,
                        "targets": [{"target_id": "page-1", "ready": True}],
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            )

        def fake_bridge_sender(request):
            sender_calls.append(request)
            return {}

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            allow_app_bridge_send=False,
            app_bridge_sender=fake_bridge_sender,
            bridge_message="Do not send by default.",
        )
        data = report.to_dict()

        self.assertEqual(sender_calls, [])
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["app_bridge_send_verified_cases"], 0)
        self.assertEqual(data["cases"][0]["status"], "native_connector_ready")
        self.assertEqual(data["cases"][0]["app_bridge_send_report"], {})

    def test_app_bridge_sender_window_input_attempt_breaks_no_loss_gate(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                window_input_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                endpoints=[
                    {
                        "debugger_url": "http://127.0.0.1:9333",
                        "ready": True,
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-1",
                            }
                        ],
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            )

        def unsafe_sender(request):
            return {
                "mode": "agent-app-bridge-send",
                "safety_mode": "native_bridge_execute",
                "ok": True,
                "decision": "app_bridge_send_accepted",
                "accepted": True,
                "control_attempts": 0,
                "window_input_attempts": 1,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "request": request.to_dict(),
            }

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            allow_app_bridge_send=True,
            app_bridge_sender=unsafe_sender,
            bridge_message="This sender is unsafe.",
        )
        data = report.to_dict()

        self.assertEqual(data["window_input_attempts"], 1)
        self.assertEqual(data["failed_cases"], 1)
        self.assertFalse(data["cases"][0]["passed"])
        self.assertIn("window_input_attempts_nonzero", data["cases"][0]["errors"])

    def test_allow_uia_semantic_action_executes_ready_semantic_sender_without_window_input(self):
        sender_calls = []

        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                window_input_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                app_uia_probe={
                    "decision": "agent_app_uia_ready",
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
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
                    "composer_candidates": [
                        {
                            "control_type": "Edit",
                            "name": "Write your prompt to Claude",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Value"],
                            "semantic_composer": True,
                        }
                    ],
                    "submit_candidates": [
                        {
                            "control_type": "Button",
                            "name": "Send",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Invoke"],
                        }
                    ],
                },
            )

        def fake_uia_sender(request):
            sender_calls.append(request)
            return {
                "mode": "agent-app-uia-semantic-action-send",
                "safety_mode": "uia_semantic_execute",
                "ok": True,
                "decision": "uia_semantic_action_send_accepted",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "uia_value_set_attempts": 1,
                "uia_invoke_attempts": 1,
                "foreground_focus_stable": True,
                "request": request.to_dict(),
                "operation_result": {
                    "composer_found": True,
                    "value_set": True,
                    "submit_found": True,
                    "invoke_attempted": True,
                    "invoke_verified": True,
                    "readbackText": "OPENWUKONG_UIA_ACCEPTANCE: PASS",
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_app_real_no_loss(
                agents=("claude desktop",),
                project_name="openwukong",
                task_name="desktop-message",
                output_root=root,
                probe_runner=fake_probe_runner,
                allow_uia_semantic_action=True,
                uia_semantic_sender=fake_uia_sender,
                uia_message="Send through UIA.",
                uia_required_markers=("OPENWUKONG_UIA_ACCEPTANCE: PASS",),
            )
            data = report.to_dict()
            case = data["cases"][0]
            artifact = json.loads(Path(case["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(len(sender_calls), 1)
        self.assertEqual(data["uia_semantic_action_send_verified_cases"], 1)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(case["status"], "uia_semantic_action_send_accepted")
        self.assertTrue(case["uia_semantic_action_send_verified"])
        self.assertTrue(case["passed"])
        self.assertEqual(
            case["uia_semantic_action_send_report"]["request"]["payload"]["message"],
            "Send through UIA.",
        )
        self.assertEqual(
            artifact["uia_semantic_action_send_report"]["decision"],
            "uia_semantic_action_send_accepted",
        )

    def test_allow_uia_semantic_draft_writes_and_cleans_without_invoking_submit(self):
        writer_calls = []

        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                window_input_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                app_uia_probe={
                    "decision": "agent_app_uia_ready",
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "matched_windows": [
                        {
                            "process_name": "Cursor.exe",
                            "pid": 99496,
                            "window_title": "config - PaoPaoHeZi - Cursor",
                            "hwnd": 70038,
                        }
                    ],
                    "composer_candidates": [
                        {
                            "control_type": "Edit",
                            "class_name": "aislash-editor-input",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Value"],
                            "semantic_composer": True,
                            "rect": [1687, 230, 2481, 291],
                        }
                    ],
                    "submit_candidates": [],
                },
            )

        def fake_draft_writer(request, *, cleanup=True, restore_value=""):
            writer_calls.append((request, cleanup, restore_value))
            return {
                "mode": "agent-app-uia-semantic-action-draft",
                "safety_mode": "uia_semantic_draft",
                "ok": True,
                "decision": "uia_semantic_action_draft_verified",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "uia_value_set_attempts": 1,
                "uia_invoke_attempts": 0,
                "cleanup_value_set_attempts": 1,
                "cleanup_verified": True,
                "foreground_focus_stable": True,
                "request": request.to_dict(),
                "operation_result": {
                    "composer_found": True,
                    "value_set": True,
                    "draft_value": request.message,
                    "cleanup_attempted": True,
                    "cleanup_value_set": True,
                    "post_cleanup_value": restore_value,
                    "readbackText": request.message,
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_app_real_no_loss(
                agents=("cursor",),
                project_name="PaoPaoHeZi",
                output_root=root,
                probe_runner=fake_probe_runner,
                allow_uia_semantic_draft=True,
                uia_draft_writer=fake_draft_writer,
                uia_draft_message="OPENWUKONG_UIA_DRAFT_PROBE",
            )
            data = report.to_dict()
            case = data["cases"][0]
            artifact = json.loads(Path(case["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(len(writer_calls), 1)
        self.assertEqual(data["uia_semantic_draft_verified_cases"], 1)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(case["status"], "uia_semantic_action_draft_verified")
        self.assertTrue(case["uia_semantic_draft_verified"])
        self.assertTrue(case["passed"])
        self.assertEqual(
            case["uia_semantic_draft_report"]["request"]["payload"]["message"],
            "OPENWUKONG_UIA_DRAFT_PROBE",
        )
        self.assertEqual(
            artifact["uia_semantic_draft_report"]["decision"],
            "uia_semantic_action_draft_verified",
        )

    def test_failed_uia_semantic_draft_surfaces_provider_failure_status(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                window_input_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                app_uia_probe={
                    "decision": "agent_app_uia_ready",
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "background_screenshot_focus_stable": True,
                    "matched_windows": [
                        {
                            "process_name": "Cursor.exe",
                            "pid": 99496,
                            "window_title": "config - PaoPaoHeZi - Cursor",
                            "hwnd": 70038,
                        }
                    ],
                    "composer_candidates": [
                        {
                            "control_type": "Edit",
                            "class_name": "aislash-editor-input",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Value"],
                            "semantic_composer": True,
                            "rect": [1687, 230, 2481, 291],
                        }
                    ],
                },
            )

        def failing_draft_writer(request, *, cleanup=True, restore_value=""):
            del request, cleanup, restore_value
            return {
                "mode": "agent-app-uia-semantic-action-draft",
                "safety_mode": "uia_semantic_draft",
                "ok": False,
                "decision": "uia_semantic_action_draft_foreground_changed",
                "control_attempts": 0,
                "window_input_attempts": 0,
                "uia_value_set_attempts": 1,
                "uia_invoke_attempts": 0,
                "cleanup_value_set_attempts": 1,
                "cleanup_verified": False,
                "foreground_focus_stable": False,
            }

        report = run_agent_app_real_no_loss(
            agents=("cursor",),
            project_name="PaoPaoHeZi",
            probe_runner=fake_probe_runner,
            allow_uia_semantic_draft=True,
            uia_draft_writer=failing_draft_writer,
            uia_draft_message="OPENWUKONG_UIA_DRAFT_PROBE",
        )
        data = report.to_dict()
        case = data["cases"][0]

        self.assertEqual(case["status"], "uia_semantic_action_draft_foreground_changed")
        self.assertFalse(case["passed"])
        self.assertEqual(data["uia_semantic_draft_verified_cases"], 0)
        self.assertIn("uia_semantic_draft_not_verified", case["errors"])

    def test_uia_semantic_sender_is_not_called_without_explicit_allow_flag(self):
        sender_calls = []

        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=0,
                ready_endpoint_count=0,
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
                    "background_screenshot_focus_stable": True,
                    "composer_candidates": [
                        {
                            "control_type": "Edit",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Value"],
                            "semantic_composer": True,
                        }
                    ],
                    "submit_candidates": [
                        {
                            "control_type": "Button",
                            "name": "Send",
                            "is_enabled": True,
                            "visible": True,
                            "patterns": ["Invoke"],
                        }
                    ],
                },
            )

        def fake_uia_sender(request):
            sender_calls.append(request)
            return {}

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            allow_uia_semantic_action=False,
            uia_semantic_sender=fake_uia_sender,
            uia_message="Do not send by default.",
        )
        data = report.to_dict()

        self.assertEqual(sender_calls, [])
        self.assertEqual(data["uia_semantic_action_send_verified_cases"], 0)
        self.assertEqual(data["cases"][0]["uia_semantic_action_send_report"], {})

    def test_reports_focus_unstable_when_any_background_capture_changes_foreground(self):
        def fake_probe_runner(**kwargs):
            del kwargs
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_native_connector_not_exposed",
                "control_attempts": 0,
                "app_uia_probe": {
                    "matched_window_count": 1,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": False,
                },
            }

        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="focus-check",
            probe_runner=fake_probe_runner,
        )
        data = report.to_dict()

        self.assertEqual(data["control_attempts"], 0)
        self.assertFalse(data["background_screenshot_focus_stable"])
        self.assertEqual(data["cases"][0]["status"], "gated_native_endpoint_missing")

    def test_main_writes_json_report(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_app_window_not_found",
                "control_attempts": 0,
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "app_uia_probe": {"matched_window_count": 0},
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-app-real-no-loss.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--agent",
                        "claude desktop",
                        "--project-name",
                        "openwukong",
                        "--task-name",
                        "desktop-message",
                        "--output-root",
                        str(root / "out"),
                        "--screenshot-dir",
                        str(root / "screenshots"),
                        "--output",
                        str(output),
                        "--json",
                    ],
                    probe_runner=fake_probe_runner,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "agent-app-real-no-loss")
        self.assertEqual(payload["total_cases"], 2)
        self.assertEqual(payload["passed_cases"], 2)
        self.assertEqual(calls[1]["agent"], "claude desktop")
        self.assertEqual(
            Path(calls[1]["screenshot_dir"]).resolve(),
            (root / "screenshots" / "claude_desktop").resolve(),
        )

    def test_main_writes_ascii_safe_json_for_windows_shell_tools(self):
        def fake_probe_runner(**kwargs):
            del kwargs
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_native_connector_not_exposed",
                "control_attempts": 0,
                "app_uia_probe": {
                    "matched_window_count": 1,
                    "project_match": {
                        "evidence": [{"name": "中文项目"}],
                    },
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "agent-app-real-no-loss.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--agent",
                        "codex app",
                        "--output-root",
                        str(root / "out"),
                        "--output",
                        str(output),
                        "--json",
                    ],
                    probe_runner=fake_probe_runner,
                )
            text = output.read_text(encoding="utf-8")
            payload = json.loads(text)

        self.assertEqual(code, 0)
        self.assertIn("\\u4e2d\\u6587\\u9879\\u76ee", text)
        self.assertEqual(
            payload["cases"][0]["probe"]["app_uia_probe"]["project_match"]["evidence"][0]["name"],
            "中文项目",
        )


if __name__ == "__main__":
    unittest.main()
