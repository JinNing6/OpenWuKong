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
        self.assertEqual(data["gated_cases"], 1)
        self.assertEqual(data["real_verified_cases"], 2)
        self.assertEqual(data["background_screenshot_count"], 2)
        self.assertEqual(data["background_screenshot_success_count"], 2)
        self.assertTrue(data["background_screenshot_focus_stable"])
        self.assertEqual(data["cases"][0]["status"], "gated_native_endpoint_missing")
        self.assertEqual(data["cases"][1]["status"], "native_connector_ready")
        self.assertEqual(artifact_payloads[0]["probe"]["decision"], "agent_native_connector_not_exposed")

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
