import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.control.codex_app_server_bridge import (
    CodexAppServerThreadStartAdapter,
    CodexAppServerTurnStartAdapter,
    CodexAppServerTurnDryRunAdapter,
    build_codex_app_server_turn_request,
)


class CodexAppServerBridgeTests(unittest.TestCase):
    def test_turn_dry_run_builds_safe_turn_start_params_without_attempts(self):
        probe = _codex_probe(thread_id="thread-abc")
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="Run the no-loss check and report OPENWUKONG_ACCEPTANCE: PASS",
            composed_message="Project: openwukong\nTask: major-real-no-loss\nOPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=probe,
            selected_transport={
                "transport_id": "codex-app-server-ws",
                "transport_channel": "codex_app_server_ws",
            },
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_turn_dry_run_ready")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 0)
        self.assertEqual(report["app_server_turn_start_attempts"], 0)
        params = report["request"]["turn_start_params"]
        self.assertEqual(params["threadId"], "thread-abc")
        self.assertEqual(params["input"][0]["type"], "text")
        self.assertIn("OPENWUKONG_ACCEPTANCE: PASS", params["input"][0]["text"])
        self.assertEqual(params["cwd"], "E:/ideaProjects/agent/openwukong")
        self.assertEqual(params["approvalPolicy"], "never")
        self.assertEqual(params["sandboxPolicy"], {"type": "readOnly", "networkAccess": False})
        self.assertEqual(report["request"]["endpoint"]["endpoint_type"], "codex_app_server_ws")

    def test_turn_dry_run_prefers_observed_thread_matching_workspace(self):
        probe = _codex_probe(
            thread_id="thread-wrong",
            selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            observed_threads=[
                {
                    "id": "thread-wrong",
                    "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                    "preview": "other project",
                },
                {
                    "id": "thread-openwukong",
                    "cwd": "E:/ideaProjects/agent/openwukong",
                    "preview": "target project",
                },
            ],
        )
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=probe,
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_turn_dry_run_ready")
        self.assertEqual(report["request"]["thread_id"], "thread-openwukong")
        self.assertEqual(
            report["request"]["turn_start_params"]["threadId"],
            "thread-openwukong",
        )
        self.assertTrue(report["request"]["diagnostics"]["workspace_match"])
        self.assertEqual(
            report["request"]["diagnostics"]["matched_thread_cwd"],
            "E:/ideaProjects/agent/openwukong",
        )

    def test_turn_dry_run_requires_thread_id(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id=""),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_app_server_thread_id_missing")
        self.assertIn("thread_id_missing", report["validation_errors"])
        self.assertEqual(report["app_server_turn_start_attempts"], 0)

    def test_turn_dry_run_requires_readback_marker(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe",
            app_surface_probe=_codex_probe(thread_id="thread-abc"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=(),
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_app_server_required_marker_missing")
        self.assertIn("required_marker_missing", report["validation_errors"])

    def test_turn_dry_run_blocks_windows_desktop_endpoint_without_foreground_safety_evidence(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                turn_start_foreground_safe=None,
                surface_kind="desktop_app",
                platform_os="windows",
                user_agent="Codex Desktop/0.136.0-alpha.2",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_foreground_risk",
        )
        self.assertFalse(report["turn_start_ready"])
        self.assertIn("turn_start_foreground_risk", report["validation_errors"])
        self.assertFalse(report["request"]["turn_start_foreground_safe"])
        self.assertEqual(
            report["request"]["turn_start_block_reason"],
            "windows_desktop_app_server_turn_start_foreground_risk",
        )
        self.assertFalse(report["request"]["endpoint"]["turn_start_foreground_safe"])
        self.assertEqual(report["app_server_turn_start_attempts"], 0)

    def test_turn_dry_run_blocks_windows_desktop_endpoint_even_when_marked_safe(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                turn_start_foreground_safe=True,
                surface_kind="desktop_app",
                platform_os="windows",
                user_agent="Codex Desktop/26.527",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_foreground_risk",
        )
        self.assertFalse(report["turn_start_ready"])
        self.assertFalse(report["request"]["turn_start_foreground_safe"])
        self.assertEqual(
            report["request"]["turn_start_block_reason"],
            "windows_desktop_app_server_turn_start_foreground_risk",
        )
        self.assertEqual(report["request"]["endpoint"]["surface_kind"], "desktop_app")
        self.assertEqual(report["app_server_turn_start_attempts"], 0)

    def test_turn_dry_run_blocks_windows_endpoint_even_when_marked_safe(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                turn_start_foreground_safe=True,
                surface_kind="headless_app_server",
                platform_os="windows",
                user_agent="Codex app-server test",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"], report)
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_foreground_risk",
        )
        self.assertFalse(report["turn_start_ready"])
        self.assertFalse(report["request"]["turn_start_foreground_safe"])
        self.assertEqual(
            report["request"]["turn_start_block_reason"],
            "windows_desktop_app_server_turn_start_foreground_risk",
        )
        self.assertEqual(report["app_server_turn_start_attempts"], 0)

    def test_turn_dry_run_allows_owned_ephemeral_windows_loopback_endpoint(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                turn_start_foreground_safe=True,
                surface_kind="owned_ephemeral_app_server",
                platform_os="windows",
                user_agent="Codex Desktop/0.142.3",
                owned_loopback_app_server=True,
                force_fresh_thread_start=True,
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_thread_start_dry_run_ready")
        self.assertTrue(report["thread_start_required"])
        self.assertTrue(report["thread_start_ready"])
        self.assertFalse(report["turn_start_ready"])
        self.assertTrue(report["request"]["turn_start_foreground_safe"])
        self.assertEqual(report["request"]["turn_start_block_reason"], "")
        self.assertEqual(report["request"]["endpoint"]["surface_kind"], "owned_ephemeral_app_server")

    def test_turn_dry_run_prepares_thread_start_when_workspace_thread_is_missing(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_thread_start_dry_run_ready")
        self.assertTrue(report["thread_start_required"])
        self.assertTrue(report["thread_start_ready"])
        self.assertFalse(report["turn_start_ready"])
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertEqual(report["app_server_turn_start_attempts"], 0)
        self.assertFalse(report["request"]["diagnostics"]["workspace_match"])
        self.assertEqual(
            report["request"]["thread_start_params"],
            {
                "cwd": "E:/ideaProjects/agent/openwukong",
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "threadSource": "user",
            },
        )
        self.assertEqual(report["request"]["turn_start_params"]["threadId"], "")

    def test_turn_dry_run_rejects_workspace_mismatch_when_no_workspace_path_can_create_thread(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-abc",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        report = CodexAppServerTurnDryRunAdapter().prepare(request).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_app_server_workspace_mismatch")
        self.assertIn("workspace_mismatch", report["validation_errors"])
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertEqual(report["app_server_turn_start_attempts"], 0)

    def test_thread_start_executor_verifies_created_workspace_thread_without_window_input(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerThreadStartAdapter(
            client=client,
            foreground_hwnd_provider=lambda: 9001,
            system_dialog_observer=_FakeSystemDialogObserver([[]]),
        ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_thread_start_verified")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 1)
        self.assertEqual(report["app_server_thread_start_attempts"], 1)
        self.assertTrue(report["foreground_focus_stable"])
        self.assertEqual(report["thread"]["id"], "thread-openwukong")
        self.assertEqual(report["thread"]["cwd"], "E:/ideaProjects/agent/openwukong")
        self.assertEqual(
            client.calls[0]["params"],
            {
                "cwd": "E:/ideaProjects/agent/openwukong",
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "threadSource": "user",
            },
        )

    def test_thread_start_executor_rejects_foreground_change(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        focus_values = iter((1001, 2002))

        report = CodexAppServerThreadStartAdapter(
            client=_FakeThreadStartClient(
                thread_id="thread-openwukong",
                cwd="E:/ideaProjects/agent/openwukong",
            ),
            foreground_hwnd_provider=lambda: next(focus_values),
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_thread_start_foreground_changed",
        )
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertFalse(report["foreground_focus_stable"])
        self.assertFalse(report["foreground_no_steal_verified"])
        self.assertEqual(report["foreground_change_classification"], "changed_unknown")

    def test_thread_start_executor_allows_unrelated_foreground_change(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerThreadStartAdapter(
            client=_FakeThreadStartClient(
                thread_id="thread-openwukong",
                cwd="E:/ideaProjects/agent/openwukong",
            ),
            foreground_hwnd_provider=_FakeForegroundObserver(
                before={
                    "hwnd": 1001,
                    "pid": 101,
                    "process_name": "Weixin.exe",
                    "window_title": "微信",
                },
                after={
                    "hwnd": 2002,
                    "pid": 202,
                    "process_name": "chrome.exe",
                    "window_title": "Search - Google Chrome",
                },
            ),
        ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_thread_start_verified")
        self.assertFalse(report["foreground_focus_stable"])
        self.assertTrue(report["foreground_no_steal_verified"])
        self.assertEqual(
            report["foreground_change_classification"],
            "changed_to_unrelated_surface",
        )

    def test_thread_start_executor_rejects_codex_foreground_change(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerThreadStartAdapter(
            client=_FakeThreadStartClient(
                thread_id="thread-openwukong",
                cwd="E:/ideaProjects/agent/openwukong",
            ),
            foreground_hwnd_provider=_FakeForegroundObserver(
                before={
                    "hwnd": 1001,
                    "pid": 101,
                    "process_name": "Weixin.exe",
                    "window_title": "微信",
                },
                after={
                    "hwnd": 2002,
                    "pid": 202,
                    "process_name": "Codex.exe",
                    "window_title": "OpenAI Codex",
                },
            ),
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_thread_start_foreground_changed",
        )
        self.assertFalse(report["foreground_no_steal_verified"])
        self.assertEqual(
            report["foreground_change_classification"],
            "changed_to_agent_surface",
        )

    def test_thread_start_executor_accepts_thread_started_notification_when_list_lags(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/CyberHuaTuo",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerThreadStartAdapter(
            client=_FakeThreadStartClient(
                thread_id="thread-openwukong",
                cwd="E:/ideaProjects/agent/openwukong",
                observed_threads=[
                    {
                        "id": "thread-other",
                        "cwd": "E:/ideaProjects/agent/CyberHuaTuo",
                    }
                ],
                notifications=[
                    {
                        "method": "thread/started",
                        "params": {
                            "thread": {
                                "id": "thread-openwukong",
                                "cwd": "E:/ideaProjects/agent/openwukong",
                            }
                        },
                    }
                ],
            ),
            foreground_hwnd_provider=lambda: 9001,
            system_dialog_observer=_FakeSystemDialogObserver([[]]),
        ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_thread_start_verified")
        self.assertFalse(report["thread_verified_in_list"])
        self.assertTrue(report["thread_verified_by_notification"])

    def test_thread_start_executor_does_not_call_client_when_not_required(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="probe OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerThreadStartAdapter(client=client).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_app_server_thread_start_not_required")
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertEqual(client.calls, [])

    def test_turn_start_executor_accepts_completed_assistant_marker_without_window_input(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeTurnStartClient(
            thread_id="thread-openwukong",
            turn_id="turn-1",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )

        report = CodexAppServerTurnStartAdapter(
            client=client,
            foreground_hwnd_provider=lambda: 9001,
        ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_turn_start_verified")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 1)
        self.assertEqual(report["app_server_turn_start_attempts"], 1)
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertTrue(report["foreground_focus_stable"])
        self.assertTrue(report["turn_completed"])
        self.assertEqual(report["turn_id"], "turn-1")
        self.assertIn("OPENWUKONG_ACCEPTANCE: PASS", report["assistant_readback_text"])
        self.assertEqual(
            client.calls[0]["params"]["sandboxPolicy"],
            {"type": "readOnly", "networkAccess": False},
        )

    def test_turn_start_executor_ignores_user_echo_marker_for_required_readback(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="",
                notifications=[
                    {
                        "method": "item/started",
                        "params": {
                            "item": {
                                "type": "userMessage",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Return exactly OPENWUKONG_ACCEPTANCE: PASS",
                                    }
                                ],
                            },
                            "turnId": "turn-1",
                        },
                    },
                    {
                        "method": "item/completed",
                        "params": {
                            "item": {
                                "type": "userMessage",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Return exactly OPENWUKONG_ACCEPTANCE: PASS",
                                    }
                                ],
                            },
                            "turnId": "turn-1",
                        },
                    },
                    {
                        "method": "item/agentMessage/delta",
                        "params": {
                            "threadId": "thread-openwukong",
                            "turnId": "turn-1",
                            "itemId": "agent-message-1",
                            "delta": "WRONG_MARKER",
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "thread-openwukong",
                            "turn": {"id": "turn-1", "status": "completed"},
                        },
                    },
                ],
            ),
            foreground_hwnd_provider=lambda: 9001,
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_required_marker_missing",
        )
        self.assertEqual(report["assistant_readback_text"], "WRONG_MARKER")
        self.assertEqual(report["missing_required_markers"], ["OPENWUKONG_ACCEPTANCE: PASS"])

    def test_turn_start_executor_accepts_session_assistant_readback_when_live_completion_missing(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        session_records = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "USER_ECHO_ONLY"}],
                },
            },
            {
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "USER_ECHO_ONLY"},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "OPENWUKONG_ACCEPTANCE: PASS",
                        }
                    ],
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "turn-1",
                    "last_agent_message": "OPENWUKONG_ACCEPTANCE: PASS",
                },
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp) / "rollout-thread-openwukong.jsonl"
            session_path.write_text(
                "\n".join(json.dumps(item) for item in session_records),
                encoding="utf-8",
            )
            with patch(
                "openwukong.control.codex_app_server_bridge._find_codex_session_path",
                lambda thread_id: session_path if thread_id == "thread-openwukong" else None,
            ):
                report = CodexAppServerTurnStartAdapter(
                    client=_FakeTurnStartClient(
                        thread_id="thread-openwukong",
                        turn_id="turn-1",
                        assistant_text="",
                        notifications=[
                            {
                                "method": "thread/status/changed",
                                "params": {
                                    "threadId": "thread-openwukong",
                                    "status": {"type": "busy"},
                                },
                            }
                        ],
                    ),
                    foreground_hwnd_provider=lambda: 9001,
                ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_turn_start_verified")
        self.assertTrue(report["turn_completed"])
        self.assertEqual(report["turn_status"], "completed")
        self.assertTrue(report["session_task_complete_seen"])
        self.assertEqual(report["session_artifact_path"], str(session_path))
        self.assertIn("OPENWUKONG_ACCEPTANCE: PASS", report["assistant_readback_text"])
        self.assertNotIn("USER_ECHO_ONLY", report["assistant_readback_text"])
        self.assertEqual(report["missing_required_markers"], [])

    def test_turn_start_executor_rejects_forbidden_marker(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            forbidden_markers=("OPENWUKONG_ACCEPTANCE: FAIL",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="OPENWUKONG_ACCEPTANCE: PASS\nOPENWUKONG_ACCEPTANCE: FAIL",
            ),
            foreground_hwnd_provider=lambda: 9001,
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_forbidden_marker_seen",
        )
        self.assertEqual(report["window_input_attempts"], 0)

    def test_turn_start_executor_rejects_foreground_change(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        focus_values = iter((1001, 2002))

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
            ),
            foreground_hwnd_provider=lambda: next(focus_values),
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_foreground_changed",
        )
        self.assertFalse(report["foreground_focus_stable"])
        self.assertFalse(report["foreground_no_steal_verified"])
        self.assertEqual(report["foreground_change_classification"], "changed_unknown")

    def test_turn_start_executor_allows_unrelated_foreground_change(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
            ),
            foreground_hwnd_provider=_FakeForegroundObserver(
                before={
                    "hwnd": 1001,
                    "pid": 101,
                    "process_name": "Weixin.exe",
                    "window_title": "微信",
                },
                after={
                    "hwnd": 2002,
                    "pid": 202,
                    "process_name": "chrome.exe",
                    "window_title": "Search - Google Chrome",
                },
            ),
        ).start(dry_run).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_app_server_turn_start_verified")
        self.assertFalse(report["foreground_focus_stable"])
        self.assertTrue(report["foreground_no_steal_verified"])
        self.assertEqual(
            report["foreground_change_classification"],
            "changed_to_unrelated_surface",
        )

    def test_turn_start_executor_rejects_codex_system_dialog_even_with_marker(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
            ),
            foreground_hwnd_provider=lambda: 9001,
            system_dialog_observer=_FakeSystemDialogObserver(
                [
                    [],
                    [
                        {
                            "hwnd": 303,
                            "title": "Error",
                            "process_name": "Codex.exe",
                            "child_texts": [
                                "A JavaScript error occurred in the main process",
                                "Uncaught Exception:",
                                "Error: AttachConsole failed",
                            ],
                        }
                    ],
                ]
            ),
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_system_dialog_detected",
        )
        self.assertTrue(report["system_dialog_detected"])
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertIn("AttachConsole failed", str(report["system_dialog_snapshots"]))

    def test_turn_start_executor_stops_before_client_when_system_dialog_already_open(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeTurnStartClient(
            thread_id="thread-openwukong",
            turn_id="turn-1",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )

        report = CodexAppServerTurnStartAdapter(
            client=client,
            system_dialog_observer=_FakeSystemDialogObserver(
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
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_system_dialog_detected",
        )
        self.assertTrue(report["system_dialog_detected"])
        self.assertEqual(report["request_attempts"], 0)
        self.assertEqual(report["app_server_turn_start_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 0)
        self.assertEqual(client.calls, [])

    def test_thread_start_executor_stops_before_client_when_system_dialog_already_open(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/other",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerThreadStartAdapter(
            client=client,
            system_dialog_observer=_FakeSystemDialogObserver(
                [[{"hwnd": 300, "title": '选择应用以打开 "session-start"'}]]
            ),
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_thread_start_system_dialog_detected",
        )
        self.assertTrue(report["system_dialog_detected"])
        self.assertEqual(report["request_attempts"], 0)
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 0)
        self.assertEqual(client.calls, [])

    def test_thread_start_executor_blocks_windowsapps_codex_activation_risk(self):
        probe = _codex_probe(
            thread_id="thread-other",
            selected_thread_cwd="E:/ideaProjects/agent/other",
            surface_kind="headless_app_server",
            platform_os="windows",
            user_agent="Codex app-server test",
        )
        metadata = probe["endpoints"][0]["metadata"]
        metadata["executable_path"] = (
            "C:/Program Files/WindowsApps/"
            "OpenAI.Codex_26.527.7698.0_x64__2p2nqsd0c76g0/"
            "app/resources/codex.exe"
        )
        metadata["activation_uri"] = "codex://session-start?type=click&tag=644788747192184631"
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=probe,
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeThreadStartClient(
            thread_id="thread-openwukong",
            cwd="E:/ideaProjects/agent/openwukong",
        )

        report = CodexAppServerThreadStartAdapter(client=client).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_thread_start_foreground_risk",
        )
        self.assertEqual(
            report["thread_start_block_reason"],
            "windows_desktop_app_server_thread_start_foreground_risk",
        )
        self.assertEqual(report["request_attempts"], 0)
        self.assertEqual(report["app_server_thread_start_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 0)
        self.assertEqual(client.calls, [])

    def test_turn_start_executor_reports_sandbox_setup_failure(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="",
                notifications=[
                    {
                        "method": "error",
                        "params": {
                            "code": "sandboxError",
                            "message": (
                                "execution error: windows sandbox: "
                                "spawn setup refresh"
                            ),
                        },
                    }
                ],
            ),
            foreground_hwnd_provider=lambda: 9001,
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_sandbox_setup_failed",
        )
        self.assertTrue(report["sandbox_setup_failed"])
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertIn("spawn setup refresh", "\n".join(report["sandbox_error_texts"]))

    def test_turn_start_executor_stops_when_windows_sandbox_not_ready(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(thread_id="thread-openwukong"),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)

        report = CodexAppServerTurnStartAdapter(
            client=_FakeTurnStartClient(
                thread_id="thread-openwukong",
                turn_id="turn-1",
                assistant_text="",
                windows_sandbox_readiness_status="notConfigured",
            ),
            foreground_hwnd_provider=lambda: 9001,
        ).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(
            report["decision"],
            "codex_app_server_turn_start_windows_sandbox_not_ready",
        )
        self.assertEqual(report["windows_sandbox_readiness_status"], "notConfigured")
        self.assertFalse(report["windows_sandbox_ready"])
        self.assertEqual(report["app_server_readiness_attempts"], 1)
        self.assertEqual(report["app_server_turn_start_attempts"], 0)
        self.assertEqual(report["native_call_attempts"], 1)
        self.assertEqual(report["turn_start_response"], {})

    def test_turn_start_executor_does_not_call_client_when_dry_run_requires_thread_start(self):
        request = build_codex_app_server_turn_request(
            agent="codex app",
            project_name="openwukong",
            task_name="major-real-no-loss",
            message="probe",
            composed_message="Return exactly OPENWUKONG_ACCEPTANCE: PASS",
            app_surface_probe=_codex_probe(
                thread_id="thread-other",
                selected_thread_cwd="E:/ideaProjects/agent/other",
            ),
            selected_transport={"transport_id": "codex-app-server-ws"},
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            workspace_path="E:/ideaProjects/agent/openwukong",
        )
        dry_run = CodexAppServerTurnDryRunAdapter().prepare(request)
        client = _FakeTurnStartClient(
            thread_id="thread-openwukong",
            turn_id="turn-1",
            assistant_text="OPENWUKONG_ACCEPTANCE: PASS",
        )

        report = CodexAppServerTurnStartAdapter(client=client).start(dry_run).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_app_server_turn_start_dry_run_not_ready")
        self.assertEqual(report["app_server_turn_start_attempts"], 0)
        self.assertEqual(client.calls, [])


def _codex_probe(
    *,
    thread_id: str,
    selected_thread_cwd: str = "E:/ideaProjects/agent/openwukong",
    observed_threads: list[dict] | None = None,
    turn_start_foreground_safe: bool | None = True,
    surface_kind: str = "headless_app_server",
    platform_os: str = "",
    user_agent: str = "Codex app-server test",
    owned_loopback_app_server: bool = False,
    force_fresh_thread_start: bool = False,
) -> dict:
    if observed_threads is None:
        observed_threads = [
            {
                "id": thread_id,
                "cwd": selected_thread_cwd,
                "preview": "",
            }
        ]
    metadata = {
        "thread_api_ready": True,
        "send_contract_ready": False,
        "surface_kind": surface_kind,
        "platform_os": platform_os,
        "user_agent": user_agent,
        "owned_loopback_app_server": owned_loopback_app_server,
        "force_fresh_thread_start": force_fresh_thread_start,
        "selected_thread_id": thread_id,
        "selected_thread_cwd": selected_thread_cwd,
        "observed_thread_count": len(observed_threads),
        "observed_threads": observed_threads,
    }
    if turn_start_foreground_safe is not None:
        metadata["turn_start_foreground_safe"] = turn_start_foreground_safe
    return {
        "mode": "agent-native-connector-probe",
        "agent": "codex app",
        "agent_id": "codex",
        "project_name": "openwukong",
        "task_name": "major-real-no-loss",
        "control_attempts": 0,
        "window_input_attempts": 0,
        "endpoint_count": 1,
        "ready_endpoint_count": 1,
        "endpoints": [
            {
                "endpoint_type": "codex_app_server_ws",
                "bridge_url": "ws://127.0.0.1:19731",
                "debugger_url": "ws://127.0.0.1:19731",
                "ready": True,
                "commands": ["initialize", "thread/list"],
                "metadata": metadata,
            }
        ],
        "app_uia_probe": {
            "matched_window_count": 1,
            "target_matched": True,
            "background_screenshot_focus_stable": True,
        },
    }


class _FakeThreadStartClient:
    def __init__(
        self,
        *,
        thread_id: str,
        cwd: str,
        observed_threads: list[dict] | None = None,
        notifications: list[dict] | None = None,
    ):
        self.thread_id = thread_id
        self.cwd = cwd
        self.observed_threads = observed_threads
        self.notifications = notifications or []
        self.calls = []

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
        observed_threads = self.observed_threads or [dict(thread)]
        return {
            "request_attempts": 3,
            "thread_start_response": {
                "id": 2,
                "result": {"thread": dict(thread), "cwd": self.cwd},
            },
            "thread_list_response": {
                "id": 3,
                "result": {"data": observed_threads, "nextCursor": None},
            },
            "notifications": [dict(item) for item in self.notifications],
        }


class _FakeTurnStartClient:
    def __init__(
        self,
        *,
        thread_id: str,
        turn_id: str,
        assistant_text: str,
        notifications: list[dict] | None = None,
        windows_sandbox_readiness_status: str = "",
    ):
        self.thread_id = thread_id
        self.turn_id = turn_id
        self.assistant_text = assistant_text
        self.notifications = notifications
        self.windows_sandbox_readiness_status = windows_sandbox_readiness_status
        self.calls = []

    def initialize_start_turn_and_collect(
        self,
        ws_url,
        *,
        params,
        request_timeout,
    ):
        self.calls.append(
            {
                "ws_url": ws_url,
                "params": dict(params),
                "request_timeout": request_timeout,
            }
        )
        if self.windows_sandbox_readiness_status:
            return {
                "request_attempts": 2,
                "windows_sandbox_readiness_response": {
                    "id": 2,
                    "result": {"status": self.windows_sandbox_readiness_status},
                },
                "turn_start_response": {},
                "notifications": [],
            }
        notifications = self.notifications
        if notifications is None:
            notifications = [
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
            ]
        return {
            "request_attempts": 2,
            "windows_sandbox_readiness_response": {},
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
            "notifications": [dict(item) for item in notifications],
        }


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


class _FakeForegroundObserver:
    def __init__(self, *, before: dict, after: dict):
        self.before = dict(before)
        self.after = dict(after)

    def get_foreground_snapshot(self):
        return dict(self.before)

    def get_foreground_snapshot_after(self):
        return dict(self.after)


if __name__ == "__main__":
    unittest.main()
