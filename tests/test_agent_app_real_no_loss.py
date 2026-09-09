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


class _FakeComposerProbeSender:
    def __init__(self, probe_payload):
        self.probe_payload = dict(probe_payload)
        self.probe_calls = []
        self.send_calls = []

    def probe_composer(self, request):
        self.probe_calls.append(request)
        payload = dict(self.probe_payload)
        payload.setdefault("mode", "agent-app-bridge-cdp-composer-probe")
        payload.setdefault("safety_mode", "read_only_native_probe")
        payload.setdefault("control_attempts", 0)
        payload.setdefault("window_input_attempts", 0)
        payload.setdefault("bridge_send_attempts", 0)
        payload.setdefault("native_probe_attempts", 1)
        payload["request"] = request.to_dict()
        return payload

    def send(self, request):
        self.send_calls.append(request)
        raise AssertionError("send should not run during read-only composer probe")


class _FakeThreadStartClient:
    def __init__(
        self,
        *,
        thread_id: str,
        cwd: str,
        turn_id: str = "turn-1",
        assistant_text: str = "",
    ):
        self.thread_id = thread_id
        self.cwd = cwd
        self.turn_id = turn_id
        self.assistant_text = assistant_text
        self.calls = []
        self.turn_calls = []

    def initialize_start_thread_and_list_threads(
        self,
        ws_url,
        *,
        params,
        request_timeout,
        thread_list_limit,
    ):
        self.calls.append(
            {
                "ws_url": ws_url,
                "params": dict(params),
                "request_timeout": request_timeout,
                "thread_list_limit": thread_list_limit,
            }
        )
        thread = {"id": self.thread_id, "cwd": self.cwd, "preview": "target"}
        return {
            "request_attempts": 3,
            "thread_start_response": {
                "id": 2,
                "result": {"thread": dict(thread), "cwd": self.cwd},
            },
            "thread_list_response": {
                "id": 3,
                "result": {"data": [dict(thread)], "nextCursor": None},
            },
            "notifications": [],
        }

    def initialize_start_turn_and_collect(
        self,
        ws_url,
        *,
        params,
        request_timeout,
    ):
        self.turn_calls.append(
            {
                "ws_url": ws_url,
                "params": dict(params),
                "request_timeout": request_timeout,
            }
        )
        return {
            "request_attempts": 2,
            "turn_start_response": {
                "id": 2,
                "result": {
                    "turn": {
                        "id": self.turn_id,
                        "items": [],
                        "status": "inProgress",
                    }
                },
            },
            "notifications": [
                {
                    "method": "item/agentMessage/delta",
                    "params": {
                        "threadId": self.thread_id,
                        "turnId": self.turn_id,
                        "itemId": "agent-message-1",
                        "delta": self.assistant_text,
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": self.thread_id,
                        "turn": {
                            "id": self.turn_id,
                            "items": [],
                            "status": "completed",
                        },
                    },
                },
            ],
        }


class _FakeForegroundObserver:
    def __init__(self, *, before: dict, after: dict):
        self.before = list(before) if isinstance(before, list) else [dict(before)]
        self.after = list(after) if isinstance(after, list) else [dict(after)]
        self.before_index = 0
        self.after_index = 0

    def get_foreground_snapshot(self):
        return self._next(self.before, "before_index")

    def get_foreground_snapshot_after(self):
        return self._next(self.after, "after_index")

    def _next(self, snapshots, index_name):
        index = getattr(self, index_name)
        if index >= len(snapshots):
            value = snapshots[-1]
        else:
            value = snapshots[index]
        setattr(self, index_name, index + 1)
        return dict(value)


class _FakeSystemDialogObserver:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture_system_dialogs(self):
        if not self.snapshots:
            return []
        if self.index >= len(self.snapshots):
            value = self.snapshots[-1]
        else:
            value = self.snapshots[self.index]
        self.index += 1
        return value


class AgentAppRealNoLossTests(unittest.TestCase):
    def test_falls_back_when_artifact_subdir_is_not_writable(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_not_exposed",
                agent=kwargs["agent"],
                agent_id="codex",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                window_input_attempts=0,
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
            (root / "agent_app_real_no_loss").write_text(
                "not a directory",
                encoding="utf-8",
            )

            report = run_agent_app_real_no_loss(
                agents=("codex app",),
                project_name="openwukong",
                task_name="agent-app-real-no-loss",
                output_root=root,
                probe_runner=fake_probe_runner,
            )
            data = report.to_dict()
            artifact_path = Path(data["cases"][0]["artifact_path"])

            self.assertTrue(artifact_path.exists())
            self.assertNotEqual(artifact_path.parent, root / "agent_app_real_no_loss")
            self.assertEqual(
                json.loads(artifact_path.read_text(encoding="utf-8"))["agent"],
                "codex app",
            )

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
        self.assertFalse(data["goal_complete"])
        self.assertEqual(data["background_send_ready_cases"], 1)
        self.assertEqual(data["background_draft_ready_cases"], 1)
        self.assertEqual(data["app_side_send_verified_cases"], 0)
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
            data["transport_matrix_summary"]["background_send_ready_cases"],
            1,
        )
        self.assertEqual(
            data["cases"][1]["transport_matrix"]["selected_send_transport"]["transport_id"],
            "uia-semantic-send",
        )
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
        self.assertEqual(data["app_side_send_verified_cases"], 1)
        self.assertTrue(data["goal_complete"])
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

    def test_app_bridge_auth_required_status_is_reported_without_foreground_input(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                bridge_send_attempts=0,
                endpoints=[
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:19557",
                        "ready": True,
                        "targets": [
                            {
                                "target_id": "cursor-page",
                                "id": "cursor-page",
                                "type": "page",
                                "title": "openwukong - Cursor",
                                "url": "vscode-file://cursor/workbench.html",
                                "ready": True,
                                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-page",
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
                            "process_name": "Cursor.exe",
                            "pid": 13592,
                            "window_title": "openwukong - Cursor",
                            "hwnd": 138024,
                        }
                    ],
                },
            )

        def fake_bridge_sender(request):
            return {
                "mode": "agent-app-bridge-send",
                "safety_mode": "native_bridge_execute",
                "ok": False,
                "decision": "app_bridge_auth_required",
                "accepted": False,
                "auth_required": True,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "request": request.to_dict(),
                "action_result": {
                    "composerFound": True,
                    "messageSet": True,
                    "submitAttempted": False,
                    "submitVerified": False,
                    "readbackText": "Cursor's AI features require you to be logged in",
                },
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = run_agent_app_real_no_loss(
                agents=("cursor",),
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

        self.assertEqual(case["status"], "auth_required")
        self.assertFalse(case["passed"])
        self.assertEqual(case["app_bridge_send_report"]["decision"], "app_bridge_auth_required")
        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)

    def test_app_bridge_pending_readback_status_is_preserved(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                bridge_send_attempts=0,
                endpoints=[
                    {
                        "endpoint_type": "ide_bridge",
                        "bridge_url": "http://127.0.0.1:8787",
                        "ready": True,
                        "preferred_chat_adapter": "cursor",
                        "adapter_mapping": {
                            "cursor": {
                                "label": "Cursor Chat",
                                "commandId": "composer.startComposerPrompt",
                                "available": True,
                                "availableCandidates": ["composer.startComposerPrompt"],
                                "commandCandidates": ["composer.startComposerPrompt"],
                            }
                        },
                        "metadata": {
                            "ide_name": "Cursor",
                            "requested_workspace_path": "E:/ideaProjects/agent/openwukong",
                            "requested_workspace_name": "openwukong",
                            "workspace_target_source": "explicit_probe_request",
                            "readback_action_ready": True,
                            "capabilities": ["agent_app_conversation.read_transcript"],
                        },
                    }
                ],
                app_uia_probe={
                    "decision": "agent_app_task_not_visible",
                    "matched_window_count": 1,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                    "matched_windows": [
                        {
                            "process_name": "Cursor.exe",
                            "pid": 32080,
                            "window_title": "openwukong - Cursor",
                            "hwnd": 19208036,
                        }
                    ],
                },
            )

        def fake_bridge_sender(request):
            return {
                "mode": "agent-app-bridge-send",
                "safety_mode": "native_bridge_execute",
                "ok": False,
                "decision": "app_bridge_message_submitted_acceptance_pending",
                "accepted": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "request": request.to_dict(),
                "action_result": {
                    "bridgeOk": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "ide=Cursor\nworkspaceFolders=0\naction=chat_send",
                },
                "missing_required_markers": ["OPENWUKONG_ACCEPTANCE: PASS"],
            }

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_app_real_no_loss(
                agents=("cursor",),
                project_name="openwukong",
                task_name="new-background-task",
                output_root=td,
                probe_runner=fake_probe_runner,
                allow_app_bridge_send=True,
                app_bridge_sender=fake_bridge_sender,
                bridge_message="Send this through the app surface.",
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(case["status"], "app_bridge_message_submitted_acceptance_pending")
        self.assertFalse(case["passed"])
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertEqual(data["app_bridge_send_verified_cases"], 0)
        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)

    def test_cursor_pending_app_bridge_is_accepted_by_transcript_readback(self):
        readback_calls = []

        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                bridge_send_attempts=0,
                endpoints=[
                    {
                        "endpoint_type": "ide_bridge",
                        "bridge_url": "http://127.0.0.1:8787",
                        "ready": True,
                        "preferred_chat_adapter": "cursor",
                        "adapter_mapping": {
                            "cursor": {
                                "label": "Cursor Chat",
                                "commandId": "composer.startComposerPrompt",
                                "available": True,
                                "availableCandidates": ["composer.startComposerPrompt"],
                                "commandCandidates": ["composer.startComposerPrompt"],
                            }
                        },
                        "metadata": {
                            "ide_name": "Cursor",
                            "requested_workspace_path": "E:/ideaProjects/agent/openwukong",
                            "requested_workspace_name": "openwukong",
                            "readback_action_ready": True,
                            "capabilities": ["agent_app_conversation.read_transcript"],
                        },
                    }
                ],
                app_uia_probe={
                    "decision": "agent_app_task_not_visible",
                    "matched_window_count": 1,
                    "target_matched": False,
                    "background_screenshot_focus_stable": True,
                },
            )

        def fake_bridge_sender(request):
            return {
                "mode": "agent-app-bridge-send",
                "safety_mode": "native_bridge_execute",
                "ok": False,
                "decision": "app_bridge_message_submitted_acceptance_pending",
                "accepted": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "bridge_send_attempts": 1,
                "native_call_attempts": 1,
                "request": request.to_dict(),
                "action_result": {
                    "bridgeOk": True,
                    "messageSet": True,
                    "submitAttempted": True,
                    "submitVerified": True,
                    "readbackText": "ide=Cursor\nworkspaceFolders=0\naction=chat_send",
                },
                "missing_required_markers": ["OPENWUKONG_ACCEPTANCE: PASS"],
            }

        def fake_cursor_transcript_readback(**kwargs):
            readback_calls.append(dict(kwargs))
            return _FakeProbeReport(
                mode="cursor-transcript-readback",
                safety_mode="read_only_local_storage",
                ok=True,
                decision="cursor_transcript_readback_accepted",
                control_attempts=0,
                window_input_attempts=0,
                bridge_send_attempts=0,
                required_markers_found=["OPENWUKONG_ACCEPTANCE: PASS"],
                missing_required_markers=[],
                forbidden_markers_found=[],
                readback_text="OPENWUKONG_ACCEPTANCE: PASS",
            )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_app_real_no_loss(
                agents=("cursor",),
                project_name="openwukong",
                task_name="new-background-task",
                output_root=td,
                workspace_path="E:/ideaProjects/agent/openwukong",
                probe_runner=fake_probe_runner,
                allow_app_bridge_send=True,
                app_bridge_sender=fake_bridge_sender,
                bridge_message="Send this through the app surface.",
                required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
                cursor_transcript_readback_runner=fake_cursor_transcript_readback,
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(len(readback_calls), 1)
        self.assertEqual(
            readback_calls[0]["required_markers"],
            ("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        self.assertEqual(case["status"], "app_bridge_send_accepted")
        self.assertTrue(case["passed"])
        self.assertEqual(data["app_bridge_send_verified_cases"], 1)
        self.assertEqual(case["bridge_send_attempts"], 1)
        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)
        self.assertEqual(
            case["app_bridge_send_report"]["decision"],
            "app_bridge_send_accepted",
        )
        self.assertEqual(
            case["app_bridge_send_report"]["cursor_transcript_readback_report"]["decision"],
            "cursor_transcript_readback_accepted",
        )

    def test_ready_devtools_app_bridge_runs_composer_probe_without_send(self):
        def fake_probe_runner(**kwargs):
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=True,
                decision="agent_native_connector_ready",
                agent=kwargs["agent"],
                agent_id="cursor",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_allowed=False,
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=1,
                bridge_send_attempts=0,
                endpoints=[
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
                                "ready": True,
                                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/cursor-workbench",
                            }
                        ],
                    }
                ],
                app_uia_probe={
                    "decision": "agent_app_project_not_visible",
                    "matched_window_count": 1,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "matched_windows": [
                        {
                            "process_name": "Cursor.exe",
                            "pid": 13592,
                            "window_title": "Cursor",
                            "hwnd": 3150324,
                        }
                    ],
                },
            )

        sender = _FakeComposerProbeSender(
            {
                "ok": False,
                "decision": "app_bridge_composer_not_ready",
                "safe_composer_found": False,
                "action_result": {
                    "composerFound": False,
                    "safeComposerCandidateCount": 0,
                    "readbackText": "New Agent\nLoading Chat",
                },
            }
        )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_app_real_no_loss(
                agents=("cursor",),
                project_name="openwukong",
                task_name="",
                output_root=Path(td),
                probe_runner=fake_probe_runner,
                app_bridge_sender=sender,
                allow_app_bridge_send=False,
            )
            data = report.to_dict()
            case = data["cases"][0]

        self.assertEqual(len(sender.probe_calls), 1)
        self.assertEqual(sender.send_calls, [])
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(case["app_bridge_dry_run"]["decision"], "app_bridge_dry_run_ready")
        self.assertEqual(
            case["app_bridge_composer_probe"]["decision"],
            "app_bridge_composer_not_ready",
        )
        self.assertEqual(case["app_bridge_composer_probe"]["native_probe_attempts"], 1)
        self.assertFalse(case["app_bridge_send_verified"])

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

    def test_passes_explicit_debugger_urls_to_native_probe(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
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
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:9444",
                        "ready": True,
                        "process": {
                            "process_name": "claude.exe",
                            "pid": 77064,
                            "listening_ports": [9444],
                        },
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:9444/devtools/page/page-1",
                            }
                        ],
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 0,
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

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
            debugger_urls=("http://127.0.0.1:9444",),
        )
        data = report.to_dict()

        self.assertEqual(calls[0]["debugger_urls"], ("http://127.0.0.1:9444",))
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["cases"][0]["status"], "native_connector_ready")

    def test_filters_debugger_urls_by_agent_before_native_probe(self):
        calls = []

        def fake_probe_runner(**kwargs):
            calls.append(dict(kwargs))
            return _FakeProbeReport(
                mode="agent-native-connector-probe",
                safety_mode="read_only",
                ok=False,
                decision="agent_native_connector_endpoint_unhealthy",
                agent=kwargs["agent"],
                agent_id="codex" if kwargs["agent"] == "codex app" else "claude",
                project_name=kwargs["project_name"],
                task_name=kwargs["task_name"],
                control_attempts=0,
                endpoint_count=1,
                ready_endpoint_count=0,
                bridge_send_attempts=0,
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "background_screenshot_focus_stable": True,
                },
            )

        with tempfile.TemporaryDirectory() as td:
            report = run_agent_app_real_no_loss(
                agents=("codex app", "claude desktop"),
                project_name="openwukong",
                task_name="owned-devtools",
                output_root=Path(td),
                debugger_urls=("http://127.0.0.1:19444",),
                debugger_urls_by_agent={
                    "codex": ("http://127.0.0.1:19555",),
                    "claude desktop": ("http://127.0.0.1:19556",),
                },
                probe_runner=fake_probe_runner,
            )
            data = report.to_dict()

        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(
            calls[0]["debugger_urls"],
            ("http://127.0.0.1:19444", "http://127.0.0.1:19555"),
        )
        self.assertEqual(
            calls[1]["debugger_urls"],
            ("http://127.0.0.1:19444", "http://127.0.0.1:19556"),
        )

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

    def test_passes_explicit_codex_app_server_ws_urls_to_native_probe(self):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "send_contract_ready": False,
                            "selected_thread_id": "thread-abc",
                            "selected_thread_cwd": "E:/ideaProjects/agent/openwukong",
                            "observed_thread_count": 1,
                        },
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
            bridge_message="Run background Codex app dry-run and report OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        data = report.to_dict()

        self.assertEqual(
            calls[0]["codex_app_server_ws_urls"],
            ("ws://127.0.0.1:19731",),
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["cases"][0]["status"], "native_connector_ready")
        self.assertEqual(
            data["cases"][0]["probe"]["endpoints"][0]["endpoint_type"],
            "codex_app_server_ws",
        )
        dry_run = data["cases"][0]["codex_app_server_turn_dry_run"]
        self.assertEqual(
            dry_run["decision"],
            "codex_app_server_turn_dry_run_ready",
        )
        self.assertEqual(dry_run["control_attempts"], 0)
        self.assertEqual(dry_run["window_input_attempts"], 0)
        self.assertEqual(dry_run["native_call_attempts"], 0)
        self.assertEqual(dry_run["app_server_turn_start_attempts"], 0)
        params = dry_run["request"]["turn_start_params"]
        self.assertEqual(params["threadId"], "thread-abc")
        self.assertEqual(params["cwd"], "E:/ideaProjects/agent/openwukong")
        self.assertIn("OPENWUKONG_ACCEPTANCE: PASS", params["input"][0]["text"])
        self.assertFalse(data["cases"][0]["transport_matrix"]["send_ready"])
        self.assertEqual(
            data["cases"][0]["transport_matrix"]["best_available_transport"]["transport_id"],
            "codex-app-server-ws",
        )

    def test_codex_app_server_ws_wrong_selected_thread_prepares_thread_start_contract(self):
        def fake_probe_runner(**kwargs):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "selected_thread_id": "thread-other",
                            "selected_thread_cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                            "observed_thread_count": 1,
                            "observed_threads": [
                                {
                                    "id": "thread-other",
                                    "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                                    "preview": "other project",
                                }
                            ],
                        },
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 0,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            bridge_message="OPENWUKONG_CODEX_APP_SERVER_TURN_DRY_RUN OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        case = report.to_dict()["cases"][0]

        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)
        self.assertEqual(case["bridge_send_attempts"], 0)
        self.assertTrue(case["codex_app_server_thread_start_ready"])
        self.assertFalse(case["codex_app_server_turn_start_ready"])
        self.assertTrue(case["codex_app_server_thread_start_required"])
        self.assertEqual(
            case["codex_app_server_turn_dry_run"]["decision"],
            "codex_app_server_thread_start_dry_run_ready",
        )
        self.assertEqual(
            case["codex_app_server_turn_dry_run"]["request"]["thread_start_params"]["cwd"],
            "E:/ideaProjects/agent/openwukong",
        )
        self.assertFalse(case["transport_matrix"]["send_ready"])

    def test_codex_app_server_thread_start_opt_in_rechecks_turn_contract(self):
        def fake_probe_runner(**kwargs):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "selected_thread_id": "thread-other",
                            "selected_thread_cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                            "observed_thread_count": 1,
                            "observed_threads": [
                                {
                                    "id": "thread-other",
                                    "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                                    "preview": "other project",
                                }
                            ],
                        },
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 0,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            bridge_message="OPENWUKONG_CODEX_APP_SERVER_TURN_DRY_RUN OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
            allow_codex_app_server_thread_start=True,
            codex_app_server_client=_FakeThreadStartClient(
                thread_id="thread-openwukong",
                cwd="E:/ideaProjects/agent/openwukong",
            ),
            codex_app_server_foreground_hwnd_provider=lambda: 9001,
        )
        case = report.to_dict()["cases"][0]

        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)
        self.assertTrue(case["codex_app_server_thread_start_verified"])
        self.assertEqual(case["codex_app_server_thread_start_attempts"], 1)
        self.assertEqual(case["codex_app_server_native_call_attempts"], 1)
        self.assertEqual(
            case["codex_app_server_thread_start_report"]["decision"],
            "codex_app_server_thread_start_verified",
        )
        after = case["codex_app_server_turn_after_thread_start_dry_run"]
        self.assertEqual(after["decision"], "codex_app_server_turn_dry_run_ready")
        self.assertTrue(after["turn_start_ready"])
        self.assertFalse(after["thread_start_required"])
        self.assertEqual(after["request"]["thread_id"], "thread-openwukong")
        self.assertEqual(
            after["request"]["turn_start_params"]["threadId"],
            "thread-openwukong",
        )

    def test_codex_app_server_turn_start_opt_in_accepts_readback_marker(self):
        def fake_probe_runner(**kwargs):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "selected_thread_id": "thread-other",
                            "selected_thread_cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                            "observed_thread_count": 1,
                            "observed_threads": [
                                {
                                    "id": "thread-other",
                                    "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                                    "preview": "other project",
                                }
                            ],
                        },
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 0,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )
        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            bridge_message="Return OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
            allow_codex_app_server_thread_start=True,
            allow_codex_app_server_turn_start=True,
            codex_app_server_client=client,
            codex_app_server_foreground_hwnd_provider=lambda: 9001,
        )
        data = report.to_dict()
        case = data["cases"][0]

        self.assertEqual(case["status"], "codex_app_server_turn_start_verified")
        self.assertTrue(case["codex_app_server_turn_start_verified"])
        self.assertEqual(case["codex_app_server_thread_start_attempts"], 1)
        self.assertEqual(case["codex_app_server_turn_start_attempts"], 1)
        self.assertEqual(case["codex_app_server_native_call_attempts"], 2)
        self.assertEqual(data["codex_app_server_turn_start_verified_cases"], 1)
        self.assertEqual(data["app_side_send_verified_cases"], 1)
        self.assertTrue(case["transport_matrix"]["send_ready"])
        self.assertEqual(
            case["transport_matrix"]["selected_send_transport"]["transport_id"],
            "codex-app-server-ws",
        )
        self.assertTrue(
            case["transport_matrix"]["selected_send_transport"]["evidence"][
                "strict_assistant_readback_verified"
            ]
        )
        self.assertEqual(case["control_attempts"], 0)
        self.assertEqual(case["window_input_attempts"], 0)
        self.assertIn(
            "OPENWUKONG_ACCEPTANCE: PASS",
            case["codex_app_server_turn_start_report"]["assistant_readback_text"],
        )
        self.assertEqual(client.turn_calls[0]["params"]["threadId"], "thread-openwukong")

    def test_codex_app_server_turn_start_focus_failure_becomes_case_status(self):
        def fake_probe_runner(**kwargs):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "selected_thread_id": "thread-other",
                            "selected_thread_cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                            "observed_thread_count": 1,
                            "observed_threads": [
                                {
                                    "id": "thread-other",
                                    "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                                    "preview": "other project",
                                }
                            ],
                        },
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 0,
                    "target_matched": False,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )
        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            bridge_message="Return OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
            allow_codex_app_server_thread_start=True,
            allow_codex_app_server_turn_start=True,
            codex_app_server_client=client,
            codex_app_server_foreground_hwnd_provider=_FakeForegroundObserver(
                before=[
                    {
                        "hwnd": 1001,
                        "pid": 101,
                        "process_name": "explorer.exe",
                        "window_title": "",
                    },
                    {
                        "hwnd": 1001,
                        "pid": 101,
                        "process_name": "explorer.exe",
                        "window_title": "",
                    },
                ],
                after=[
                    {
                        "hwnd": 1001,
                        "pid": 101,
                        "process_name": "explorer.exe",
                        "window_title": "",
                    },
                    {
                        "hwnd": 2002,
                        "pid": 202,
                        "process_name": "Codex.exe",
                        "window_title": "Codex",
                        "executable_path": (
                            "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe"
                        ),
                    },
                ],
            ),
        )
        data = report.to_dict()
        case = data["cases"][0]

        self.assertEqual(case["status"], "codex_app_server_turn_start_foreground_changed")
        self.assertFalse(case["passed"])
        self.assertFalse(case["codex_app_server_turn_start_verified"])
        self.assertTrue(case["codex_app_server_thread_start_verified"])
        self.assertIn("codex_app_server_turn_start_not_verified", case["errors"])
        self.assertEqual(
            case["codex_app_server_turn_start_report"]["foreground_change_classification"],
            "changed_to_agent_surface",
        )
        self.assertFalse(
            case["codex_app_server_turn_start_report"]["foreground_no_steal_verified"]
        )
        self.assertEqual(data["codex_app_server_turn_start_verified_cases"], 0)

    def test_codex_app_server_preexisting_system_dialog_becomes_case_status_without_call(self):
        def fake_probe_runner(**kwargs):
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
                        "endpoint_type": "codex_app_server_ws",
                        "bridge_url": "ws://127.0.0.1:19731",
                        "debugger_url": "ws://127.0.0.1:19731",
                        "ready": True,
                        "commands": ["initialize", "thread/list"],
                        "metadata": {
                            "thread_api_ready": True,
                            "turn_start_foreground_safe": True,
                            "selected_thread_id": "thread-openwukong",
                            "selected_thread_cwd": "E:/ideaProjects/agent/openwukong",
                            "observed_thread_count": 1,
                            "observed_threads": [
                                {
                                    "id": "thread-openwukong",
                                    "cwd": "E:/ideaProjects/agent/openwukong",
                                    "preview": "target project",
                                }
                            ],
                        },
                    }
                ],
                app_uia_probe={
                    "matched_window_count": 1,
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            )

        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )
        report = run_agent_app_real_no_loss(
            agents=("codex app",),
            project_name="openwukong",
            task_name="desktop-message",
            bridge_message="Return OPENWUKONG_ACCEPTANCE: PASS",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            probe_runner=fake_probe_runner,
            codex_app_server_ws_urls=("ws://127.0.0.1:19731",),
            workspace_path="E:/ideaProjects/agent/openwukong",
            allow_codex_app_server_turn_start=True,
            codex_app_server_client=client,
            codex_app_server_system_dialog_observer=_FakeSystemDialogObserver(
                [
                    [
                        {
                            "hwnd": 301,
                            "title": "Error",
                            "process_name": "Codex.exe",
                            "text": (
                                "Error launching app\n"
                                "Unable to find Electron app at "
                                "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                                "?type=click&tag=17888037027795083491\n"
                                "Cannot find module"
                            ),
                        }
                    ]
                ]
            ),
        )
        data = report.to_dict()
        case = data["cases"][0]

        self.assertEqual(
            case["status"],
            "codex_app_server_turn_start_system_dialog_detected",
        )
        self.assertFalse(case["passed"])
        self.assertEqual(case["codex_app_server_turn_start_attempts"], 0)
        self.assertEqual(case["codex_app_server_native_call_attempts"], 0)
        self.assertEqual(client.turn_calls, [])
        self.assertIn("codex_app_server_turn_start_not_verified", case["errors"])

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

    def test_status_distinguishes_app_window_not_found_from_generic_unavailable(self):
        def fake_probe_runner(**kwargs):
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_app_window_not_found",
                "agent": kwargs["agent"],
                "agent_id": "claude",
                "control_attempts": 0,
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "app_uia_probe": {
                    "decision": "agent_app_window_not_found",
                    "matched_window_count": 0,
                    "target_matched": False,
                    "background_screenshot_focus_stable": True,
                },
            }

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
        )
        case = report.to_dict()["cases"][0]

        self.assertEqual(case["status"], "app_window_not_found")
        self.assertTrue(case["passed"])
        self.assertFalse(case["real_verified"])

    def test_status_distinguishes_installed_app_not_running_from_missing_window(self):
        def fake_probe_runner(**kwargs):
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_app_window_not_found",
                "agent": kwargs["agent"],
                "agent_id": "claude",
                "control_attempts": 0,
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "app_uia_probe": {
                    "decision": "agent_app_window_not_found",
                    "matched_window_count": 0,
                    "target_matched": False,
                    "background_screenshot_focus_stable": True,
                    "selected_transport": {
                        "transport_id": "claude-desktop-shell",
                        "transport": "desktop-shell-native-bridge-or-foreground",
                        "source": "start-apps",
                        "path": "Claude_pzs8sxrjxfjjc!Claude",
                        "ready": True,
                        "background_capable": False,
                    },
                },
            }

        report = run_agent_app_real_no_loss(
            agents=("claude desktop",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
        )
        case = report.to_dict()["cases"][0]

        self.assertEqual(
            case["status"],
            "app_installed_not_running_connector_required",
        )
        self.assertTrue(case["passed"])
        self.assertFalse(case["real_verified"])

    def test_status_distinguishes_target_project_not_visible_from_missing_endpoint(self):
        def fake_probe_runner(**kwargs):
            return {
                "mode": "agent-native-connector-probe",
                "safety_mode": "read_only",
                "ok": False,
                "decision": "agent_native_connector_not_exposed",
                "agent": kwargs["agent"],
                "agent_id": "cursor",
                "control_attempts": 0,
                "endpoint_count": 0,
                "ready_endpoint_count": 0,
                "app_uia_probe": {
                    "decision": "agent_app_project_not_visible",
                    "matched_window_count": 1,
                    "target_matched": False,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
                    "background_screenshot_count": 1,
                    "background_screenshot_success_count": 1,
                    "background_screenshot_focus_stable": True,
                    "matched_windows": [
                        {
                            "process_name": "Cursor.exe",
                            "pid": 40904,
                            "window_title": "start.md - trustusb-2 [SSH: QLV10-1] - Cursor",
                            "hwnd": 9966186,
                        }
                    ],
                },
            }

        report = run_agent_app_real_no_loss(
            agents=("cursor",),
            project_name="openwukong",
            task_name="desktop-message",
            probe_runner=fake_probe_runner,
        )
        case = report.to_dict()["cases"][0]

        self.assertEqual(case["status"], "target_project_not_visible")
        self.assertTrue(case["passed"])
        self.assertTrue(case["real_verified"])

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
