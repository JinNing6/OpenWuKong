import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.primary_real_no_loss import (
    run_primary_real_no_loss,
    summarize_report,
)
from openwukong.evaluation.simulation import load_simulation_fixture
from openwukong.evaluation.wechat_locator import (
    StaticWin32WindowObserver,
    Win32ChildWindowSnapshot,
)


class _FakeReadinessLauncher:
    def __init__(self):
        self.calls = []

    def launch(self, argv: tuple[str, ...], cwd: str | None = None) -> int:
        self.calls.append({"argv": tuple(argv), "cwd": cwd})
        return 5656


class _FakeReadinessTerminator:
    def __init__(self):
        self.tree_pids = []
        self.owned_argv = []

    def terminate_tree(self, pid: int) -> None:
        self.tree_pids.append(int(pid))

    def terminate_owned_processes(self, argv: tuple[str, ...]) -> None:
        self.owned_argv.append(tuple(argv))


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


class PrimaryRealNoLossTests(unittest.TestCase):
    def test_runner_converts_primary_scenarios_to_real_no_loss_probes(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=7001,
                    process_name="Weixin.exe",
                    window_title="文件传输助手 - 微信",
                    hwnd=7001,
                    elements=(
                        _element("List", name="chat list", patterns=("Selection",)),
                        _element("Edit", name="输入", patterns=("Value", "Text")),
                        _element("Button", name="发送", patterns=("Invoke",)),
                    ),
                )
            ]
        )
        readiness_calls: list[str] = []
        action_calls: list[dict] = []
        bridge_calls: list[str] = []

        def _fake_readiness_probe(debugger_url: str) -> dict:
            readiness_calls.append(debugger_url)
            return {
                "mode": "browser-helper-readiness-probe",
                "ok": True,
                "debugger_url": debugger_url,
                "target_count": 1,
                "targets": [
                    {
                        "type": "page",
                        "title": "OpenWukong Primary Smoke",
                        "url": "about:blank#openwukong-primary-smoke",
                    }
                ],
                "error": "",
            }

        def _fake_browser_action_runner(**kwargs) -> dict:
            action_calls.append(dict(kwargs))
            return {
                "mode": "browser-devtools-action",
                "safety_mode": "gated_browser_devtools_action",
                "ok": True,
                "health_ok": True,
                "control_allowed": True,
                "control_attempts": 0,
                "action": kwargs["action"],
                "debugger_url": kwargs["debugger_url"],
                "target": {
                    "type": "page",
                    "title": "OpenWukong Primary Smoke",
                    "url": kwargs["resource_url"],
                },
                "page_identity": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                },
                "action_result": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                    "textExcerpt": "OpenWukong Primary Smoke",
                },
                "post_action_identity": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                },
                "error": "",
            }

        def _fake_ide_bridge_probe(bridge_url: str) -> dict:
            bridge_calls.append(bridge_url)
            return {
                "mode": "ide-bridge-capability-capture",
                "safety_mode": "read_only",
                "control_allowed": False,
                "control_attempts": 0,
                "bridge_url": bridge_url,
                "ok": True,
                "command_count": 2,
                "commands": ["openwukong.readState", "openwukong.sendMessage"],
                "chat_adapters": [
                    {
                        "adapter_id": "codex",
                        "available": True,
                        "command_id": "openwukong.sendMessage",
                    }
                ],
                "error": "",
            }

        with tempfile.TemporaryDirectory() as tmp:
            report = run_primary_real_no_loss(
                fixture,
                output_root=tmp,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=_FakeReadinessLauncher(),
                owned_browser_helper_terminator=_FakeReadinessTerminator(),
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9451,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
                accessibility_observer=observer,
                wechat_win32_observer=StaticWin32WindowObserver(
                    {
                        0: (),
                        7001: (
                            Win32ChildWindowSnapshot(
                                hwnd=7101,
                                parent_hwnd=7001,
                                class_name="Edit",
                                text_preview="",
                                rect=(0, 0, 200, 40),
                                is_visible=True,
                                is_enabled=True,
                            ),
                        ),
                    }
                ),
                ide_bridge_urls=("http://127.0.0.1:8787",),
                ide_bridge_probe=_fake_ide_bridge_probe,
            )
            data = report.to_dict()
            output_root = Path(tmp).resolve()

            self.assertEqual(data["mode"], "primary-scenario-real-no-loss")
            self.assertEqual(data["safety_mode"], "real_no_loss")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["external_communication_attempts"], 0)
            self.assertEqual(data["window_input_attempts"], 0)
            self.assertEqual(data["real_user_filesystem_scan_attempts"], 0)
            self.assertEqual(data["user_file_modification_attempts"], 0)
            self.assertEqual(data["owned_app_launch_attempts"], 1)
            self.assertEqual(data["passed_cases"], 4)
            self.assertEqual(data["real_verified_cases"], 4)

            cases = {case["scenario_id"]: case for case in data["cases"]}
            self.assertEqual(cases["wechat.chat.draft_reply"]["status"], "verified")
            self.assertEqual(
                cases["wechat.chat.draft_reply"]["real_probe_kind"],
                "wechat-uia-win32-read-only-locator",
            )
            self.assertEqual(cases["wechat.chat.draft_reply"]["send_attempts"], 0)
            self.assertEqual(cases["wechat.chat.draft_reply"]["window_input_attempts"], 0)
            self.assertGreaterEqual(
                cases["wechat.chat.draft_reply"]["details"]["matching_window_count"],
                1,
            )
            self.assertEqual(
                cases["wechat.chat.draft_reply"]["details"]["locator"]["control_decision"],
                "read_only_verified_write_blocked",
            )
            self.assertEqual(
                cases["wechat.chat.draft_reply"]["details"]["locator"]["window_input_attempts"],
                0,
            )
            self.assertEqual(
                cases["wechat.chat.draft_reply"]["details"]["locator"]["windows"][0]["win32_child_window_count"],
                1,
            )

            self.assertEqual(cases["browser.research.collect_sources"]["status"], "verified")
            self.assertEqual(
                cases["browser.research.collect_sources"]["real_probe_kind"],
                "owned-browser-devtools-read-page",
            )
            self.assertEqual(
                cases["browser.research.collect_sources"]["details"]["action"],
                "read_page",
            )
            self.assertEqual(
                cases["browser.research.collect_sources"]["details"]["action_title"],
                "OpenWukong Primary Smoke",
            )
            self.assertEqual(action_calls[0]["debugger_url"], "http://127.0.0.1:9451")
            self.assertEqual(readiness_calls, ["http://127.0.0.1:9451"])

            self.assertEqual(cases["files.search.find_candidate"]["status"], "verified")
            self.assertEqual(
                cases["files.search.find_candidate"]["real_probe_kind"],
                "owned-filesystem-temp-index",
            )
            self.assertEqual(
                cases["files.search.find_candidate"]["owned_filesystem_scan_attempts"],
                1,
            )
            self.assertEqual(
                cases["files.search.find_candidate"]["real_user_filesystem_scan_attempts"],
                0,
            )
            candidate_paths = cases["files.search.find_candidate"]["details"]["candidate_paths"]
            self.assertGreaterEqual(len(candidate_paths), 1)
            for path in candidate_paths:
                self.assertTrue(str(Path(path).resolve()).startswith(str(output_root)))

            self.assertEqual(cases["codex.project.submit_task_draft"]["status"], "verified")
            self.assertEqual(
                cases["codex.project.submit_task_draft"]["real_probe_kind"],
                "ide-bridge-capabilities-read-only",
            )
            self.assertEqual(cases["codex.project.submit_task_draft"]["submit_attempts"], 0)
            self.assertEqual(cases["codex.project.submit_task_draft"]["start_agent_attempts"], 0)
            self.assertEqual(bridge_calls, ["http://127.0.0.1:8787"])

            for case in cases.values():
                artifact_path = Path(case["artifact_path"]).resolve()
                self.assertTrue(str(artifact_path).startswith(str(output_root)))
                self.assertTrue(artifact_path.is_file())
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                self.assertEqual(artifact["safety_mode"], "real_no_loss")

            summary = summarize_report(report)
            self.assertEqual(summary["mode"], "primary-scenario-real-no-loss-summary")
            self.assertEqual(summary["passed_cases"], 4)
            self.assertEqual(summary["real_verified_cases"], 4)
            self.assertNotIn("details", summary["scenarios"][0])


if __name__ == "__main__":
    unittest.main()
