import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openwukong.evaluation.accessibility_probe import (
    AccessibilityElementSnapshot,
    AccessibilityWindowSnapshot,
    StaticAccessibilityObserver,
)
from openwukong.evaluation.primary_real_no_loss import (
    PrimaryRealNoLossCase,
    PrimaryRealNoLossReport,
    _codex_case,
    _write_case_artifact,
    _resolve_installed_browser_executable,
    _resolve_background_screenshot_dir,
    run_primary_real_no_loss,
    summarize_report,
)
from openwukong.evaluation.simulation import load_simulation_fixture
from openwukong.evaluation.window_capture import BackgroundWindowCaptureReport
from openwukong.evaluation.wechat_locator import (
    StaticWin32WindowObserver,
    Win32ChildWindowSnapshot,
)
from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
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


class _FakeBackgroundCaptureProvider:
    def __init__(self):
        self.calls: list[tuple[int, Path]] = []

    def capture_window(self, hwnd: int, output_path: str | Path) -> BackgroundWindowCaptureReport:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake background screenshot")
        self.calls.append((int(hwnd), target))
        return BackgroundWindowCaptureReport(
            hwnd=int(hwnd),
            output_path=str(target),
            ok=True,
            width=320,
            height=200,
            foreground_hwnd_before=111,
            foreground_hwnd_after=111,
        )


def _clear_system_dialog_preflight():
    return {
        "mode": "desktop-system-dialog-preflight",
        "safety_mode": "read_only_desktop_scan",
        "ok": True,
        "decision": "system_dialog_clear",
        "control_allowed": False,
        "control_attempts": 0,
        "window_input_attempts": 0,
        "native_call_attempts": 0,
        "system_dialog_detected": False,
        "system_dialog_count": 0,
        "system_dialog_snapshots": [],
    }


def _element(control_type: str, *, name: str = "", patterns=()):
    return AccessibilityElementSnapshot(
        control_type=control_type,
        name=name,
        rect=(0, 0, 100, 20),
        is_enabled=True,
        patterns=tuple(patterns),
    )


class PrimaryRealNoLossTests(unittest.TestCase):
    def test_case_artifact_writes_primary_trajectory_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "background.png"
            screenshot.write_bytes(b"fake background screenshot")
            case = PrimaryRealNoLossCase(
                case_id="browser_collect_sources",
                scenario_id="browser.research.collect_sources",
                status="verified",
                passed=True,
                real_verified=True,
                real_probe_kind="browser-devtools-owned-helper",
                details={
                    "source_count": 1,
                    "background_screenshots": [
                        {
                            "ok": True,
                            "output_path": str(screenshot),
                        }
                    ],
                },
            )

            written = _write_case_artifact(root, case)
            artifact = json.loads(Path(written.artifact_path).read_text(encoding="utf-8"))
            trajectory_path = Path(written.details["trajectory_path"])
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            trajectory_artifacts = {
                item["role"]: item
                for item in trajectory["steps"][0]["artifacts"]
            }

        self.assertEqual(artifact["details"]["trajectory_path"], str(trajectory_path))
        self.assertEqual(trajectory["mode"], "control-trajectory")
        self.assertEqual(trajectory["scenario"], "browser.research.collect_sources")
        self.assertEqual(trajectory["target_id"], "browser_collect_sources")
        self.assertEqual(trajectory["metadata"]["runner"], "primary-real-no-loss")
        self.assertEqual(trajectory["step_count"], 1)
        self.assertEqual(trajectory["steps"][0]["phase"], "case_report")
        self.assertEqual(
            set(trajectory_artifacts),
            {"case_artifact", "background_screenshots_output_path"},
        )
        self.assertEqual(
            trajectory_artifacts["background_screenshots_output_path"]["media_type"],
            "image/png",
        )
        self.assertEqual(
            len(trajectory_artifacts["background_screenshots_output_path"]["sha256"]),
            64,
        )

    def test_primary_focus_stability_ignores_external_background_screenshot_change(self):
        report = PrimaryRealNoLossReport(
            suite="focus-classification",
            output_root="",
            cases=(
                PrimaryRealNoLossCase(
                    case_id="wechat",
                    scenario_id="wechat.chat.draft_reply",
                    status="blocked",
                    passed=True,
                    real_verified=True,
                    real_probe_kind="background-screenshot",
                    details={
                        "background_screenshots": [
                            BackgroundWindowCaptureReport(
                                hwnd=7001,
                                output_path="window.png",
                                ok=True,
                                foreground_hwnd_before=9001,
                                foreground_hwnd_after=9002,
                            ).to_dict()
                        ],
                    },
                ),
            ),
        )

        screenshot = report.cases[0].details["background_screenshots"][0]
        self.assertTrue(screenshot["foreground_changed"])
        self.assertFalse(screenshot["foreground_focus_risk"])
        self.assertTrue(report.background_screenshot_focus_stable)

    def test_primary_focus_stability_flags_target_activation_as_risk(self):
        report = PrimaryRealNoLossReport(
            suite="focus-classification",
            output_root="",
            cases=(
                PrimaryRealNoLossCase(
                    case_id="wechat",
                    scenario_id="wechat.chat.draft_reply",
                    status="blocked",
                    passed=True,
                    real_verified=True,
                    real_probe_kind="background-screenshot",
                    details={
                        "background_screenshots": [
                            BackgroundWindowCaptureReport(
                                hwnd=7001,
                                output_path="window.png",
                                ok=True,
                                foreground_hwnd_before=9001,
                                foreground_hwnd_after=7001,
                            ).to_dict()
                        ],
                    },
                ),
            ),
        )

        screenshot = report.cases[0].details["background_screenshots"][0]
        self.assertTrue(screenshot["foreground_focus_risk"])
        self.assertFalse(report.background_screenshot_focus_stable)

    def test_browser_executable_resolution_prefers_installed_exe_over_path_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            chrome = Path(tmp) / "chrome.exe"
            chrome.write_text("fake chrome", encoding="utf-8")
            resolver = WindowsAppResolver(
                candidate_providers=(
                    StaticAppCandidateProvider(
                        [
                            AppResolutionCandidate(
                                source="start-menu",
                                display_name="Google Chrome",
                                path="C:/Start Menu/Google Chrome.lnk",
                            ),
                            AppResolutionCandidate(
                                source="app-paths-registry",
                                display_name="Google Chrome",
                                executable_name="chrome.exe",
                                path=str(chrome),
                            ),
                        ]
                    ),
                )
            )

            resolved = _resolve_installed_browser_executable(
                "chrome.exe",
                resolver=resolver,
            )

        self.assertEqual(resolved, str(chrome.resolve()))

    def test_browser_executable_resolution_falls_back_to_requested_name(self):
        resolver = WindowsAppResolver(candidate_providers=())

        resolved = _resolve_installed_browser_executable("chrome.exe", resolver=resolver)

        self.assertEqual(resolved, "chrome.exe")

    def test_background_screenshot_dir_uses_explicit_relative_path_from_cwd(self):
        output_root = (Path("logs") / "runtime" / "primary-real-no-loss-r4").resolve()
        screenshot_dir = Path("logs") / "runtime" / "primary-real-no-loss-r4" / "background-screenshots"

        resolved = _resolve_background_screenshot_dir(
            screenshot_dir,
            output_root=output_root,
            case_id="wechat_chat_draft_reply",
        )

        self.assertEqual(
            resolved,
            screenshot_dir.resolve() / "wechat_chat_draft_reply",
        )

    def test_wechat_primary_case_excludes_enterprise_wechat_from_target_screenshots(self):
        from openwukong.evaluation.primary_real_no_loss import _is_wechat_window

        self.assertTrue(_is_wechat_window("Weixin.exe", "微信"))
        self.assertTrue(_is_wechat_window("WeChat.exe", "微信"))
        self.assertFalse(_is_wechat_window("WXWork.exe", "企业微信"))
        self.assertFalse(_is_wechat_window("WXWork.exe", "WeCom"))

    def test_codex_primary_case_does_not_probe_default_fixed_ide_bridge_url(self):
        calls: list[str] = []

        def _probe(url: str) -> dict:
            calls.append(url)
            return {"ok": True, "bridge_url": url}

        case = _codex_case(
            {
                "case_id": "codex-no-default-bridge",
                "plan": {
                    "draft_action": {
                        "intent": {"workspace": "E:/ideaProjects/agent/openwukong"}
                    }
                },
            },
            Path("logs/runtime/test-codex-no-default-bridge").resolve(),
            (),
            _probe,
        )

        self.assertEqual(calls, [])
        self.assertEqual(case.status, "unavailable")
        self.assertEqual(case.details["probed_bridge_urls"], [])

    def test_runner_stops_before_scenario_work_when_system_dialog_preflight_fails(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )
        preflight_calls = []
        harness_calls = []

        class FailingHarness:
            def run_suite(self, _fixture):
                harness_calls.append(True)
                raise AssertionError("L1 replay must not run after preflight failure")

        def _preflight_runner():
            preflight_calls.append(True)
            return {
                "mode": "desktop-system-dialog-preflight",
                "safety_mode": "read_only_desktop_scan",
                "ok": False,
                "decision": "system_dialog_detected",
                "control_allowed": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "native_call_attempts": 0,
                "system_dialog_detected": True,
                "system_dialog_count": 1,
                "system_dialog_snapshots": [
                    {
                        "hwnd": 301,
                        "title": "Error",
                        "process_name": "Codex.exe",
                        "text": (
                            "Error launching app\n"
                            "Unable to find Electron app at "
                            "C:/Program Files/WindowsApps/OpenAI.Codex_26.527/"
                            "?type=click&tag=11634605478613629973"
                        ),
                    }
                ],
            }

        def _should_not_run(*_args, **_kwargs):
            raise AssertionError("subrunner must not run after preflight failure")

        with tempfile.TemporaryDirectory() as tmp:
            report = run_primary_real_no_loss(
                fixture,
                output_root=tmp,
                harness=FailingHarness(),
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=_FakeReadinessLauncher(),
                owned_browser_helper_readiness_probe=_should_not_run,
                owned_browser_helper_action_runner=_should_not_run,
                ide_bridge_probe=_should_not_run,
                word_background_probe_runner=_should_not_run,
                computer_use_probe_runner=_should_not_run,
                system_dialog_preflight_runner=_preflight_runner,
            )
        data = report.to_dict()
        summary = summarize_report(report)

        self.assertEqual(preflight_calls, [True])
        self.assertEqual(harness_calls, [])
        self.assertTrue(data["system_dialog_preflight_failed"])
        self.assertEqual(
            data["system_dialog_preflight"]["decision"],
            "system_dialog_detected",
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["external_communication_attempts"], 0)
        self.assertEqual(data["owned_app_launch_attempts"], 0)
        self.assertEqual(data["total_cases"], 1)
        self.assertEqual(data["failed_cases"], 1)
        self.assertEqual(data["cases"], [])
        self.assertTrue(summary["system_dialog_preflight_failed"])

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
        word_calls: list[dict] = []
        browser_resolver_calls: list[str] = []
        computer_use_calls: list[bool] = []

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

        def _fake_word_background_probe(**kwargs) -> dict:
            word_calls.append(dict(kwargs))
            Path(kwargs["document_path"]).write_bytes(b"fake-docx")
            return {
                "mode": "office-word-background-probe",
                "safety_mode": "background_office_com_no_loss",
                "ok": True,
                "decision": "word_background_probe_verified",
                "document_path": kwargs["document_path"],
                "marker": kwargs["marker"],
                "readback_text": f"Marker: {kwargs['marker']}",
                "save_verified": True,
                "readback_verified": True,
                "word_started": True,
                "visible_requested": False,
                "control_allowed": True,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "foreground_hwnd_before": 1001,
                "foreground_hwnd_after": 1001,
                "foreground_focus_stable": True,
                "foreground_snapshot_before": {
                    "hwnd": 1001,
                    "pid": 11,
                    "process_name": "Weixin.exe",
                    "window_title": "WeChat",
                },
                "foreground_snapshot_after": {
                    "hwnd": 1001,
                    "pid": 11,
                    "process_name": "Weixin.exe",
                    "window_title": "WeChat",
                },
                "foreground_change_classification": "stable",
                "foreground_no_steal_verified": True,
                "office_com_attempts": 1,
                "error": "",
            }

        def _fake_browser_executable_resolver(requested: str) -> str:
            browser_resolver_calls.append(requested)
            return "C:/Program Files/Google/Chrome/Application/chrome.exe"

        def _fake_computer_use_probe() -> dict:
            computer_use_calls.append(True)
            return {
                "mode": "computer-use-runtime-probe",
                "safety_mode": "read_only",
                "ready": True,
                "native_pipe_ready": True,
                "window_state_ready": True,
                "background_snapshot_ready": True,
                "accessibility_tree_available": False,
                "input_actions_activate_window": True,
                "computer_use_attempts": 2,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "foreground_activation_attempts": 0,
                "observed_window_count": 16,
                "screenshot_count": 1,
                "decision": "computer_use_read_only_ready",
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher = _FakeReadinessLauncher()
            capture = _FakeBackgroundCaptureProvider()
            report = run_primary_real_no_loss(
                fixture,
                output_root=root,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=launcher,
                owned_browser_helper_terminator=_FakeReadinessTerminator(),
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9451,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
                browser_executable_resolver=_fake_browser_executable_resolver,
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
                word_background_probe_runner=_fake_word_background_probe,
                computer_use_probe_runner=_fake_computer_use_probe,
                background_screenshot_dir=root / "background-screenshots",
                window_capture_provider=capture,
                system_dialog_preflight_runner=_clear_system_dialog_preflight,
            )
            data = report.to_dict()
            output_root = root.resolve()
            progress = json.loads(
                (output_root / "primary-real-no-loss-progress.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(data["mode"], "primary-scenario-real-no-loss")
            self.assertEqual(data["safety_mode"], "real_no_loss")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["external_communication_attempts"], 0)
            self.assertEqual(data["window_input_attempts"], 0)
            self.assertEqual(data["uia_semantic_action_ready_cases"], 1)
            self.assertEqual(data["uia_value_set_attempts"], 0)
            self.assertEqual(data["uia_invoke_attempts"], 0)
            self.assertEqual(data["computer_use_read_only_cases"], 1)
            self.assertEqual(data["computer_use_attempts"], 2)
            self.assertEqual(data["computer_use_window_input_attempts"], 0)
            self.assertFalse(data["transport_matrix"]["goal_complete"])
            self.assertEqual(
                data["transport_matrix"]["summary"]["scenario_count"],
                5,
            )
            self.assertEqual(
                data["transport_matrix"]["summary"]["background_execute_ready_cases"],
                5,
            )
            self.assertEqual(
                data["transport_matrix"]["summary"]["background_write_ready_cases"],
                1,
            )
            self.assertEqual(
                data["transport_matrix"]["summary"]["write_blocked_cases"],
                2,
            )
            self.assertEqual(data["real_user_filesystem_scan_attempts"], 0)
            self.assertEqual(data["user_file_modification_attempts"], 0)
            self.assertEqual(data["owned_app_launch_attempts"], 1)
            self.assertEqual(data["passed_cases"], 5)
            self.assertEqual(data["real_verified_cases"], 5)
            progress_stages = [
                (item["stage_name"], item["status"])
                for item in progress["stages"]
            ]
            self.assertIn(("system_dialog_preflight", "completed"), progress_stages)
            self.assertIn(("l1_replay", "completed"), progress_stages)
            self.assertIn(("browser_smoke_cases", "completed"), progress_stages)
            self.assertIn(("wechat.chat.draft_reply", "started"), progress_stages)
            self.assertIn(("word.document.create_background", "completed"), progress_stages)

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
            self.assertTrue(
                cases["wechat.chat.draft_reply"]["details"]["computer_use_read_only_ready"]
            )
            self.assertFalse(
                cases["wechat.chat.draft_reply"]["details"]["computer_use_write_control_ready"]
            )
            self.assertEqual(
                cases["wechat.chat.draft_reply"]["details"]["computer_use_probe"]["decision"],
                "computer_use_read_only_ready",
            )
            dry_run = cases["wechat.chat.draft_reply"]["details"]["uia_semantic_action_dry_run"]
            self.assertTrue(cases["wechat.chat.draft_reply"]["details"]["uia_semantic_action_ready"])
            self.assertEqual(dry_run["decision"], "wechat_uia_semantic_action_dry_run_ready")
            self.assertEqual(dry_run["send_attempts"], 0)
            self.assertEqual(dry_run["window_input_attempts"], 0)
            self.assertEqual(dry_run["uia_value_set_attempts"], 0)
            self.assertEqual(dry_run["uia_invoke_attempts"], 0)
            self.assertTrue(dry_run["request"]["target_ready"])
            self.assertTrue(dry_run["request"]["uia_value_pattern_ready"])
            self.assertTrue(dry_run["request"]["uia_invoke_pattern_ready"])
            self.assertTrue(dry_run["request"]["background_screenshot_verified"])
            self.assertEqual(dry_run["request"]["background_screenshot_success_count"], 1)

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
            self.assertEqual(browser_resolver_calls, ["chrome.exe"])
            self.assertEqual(computer_use_calls, [True])
            self.assertEqual(
                launcher.calls[0]["argv"][0],
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
            )

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

            self.assertEqual(cases["word.document.create_background"]["status"], "verified")
            self.assertEqual(
                cases["word.document.create_background"]["real_probe_kind"],
                "office-word-com-owned-document-background",
            )
            self.assertEqual(cases["word.document.create_background"]["window_input_attempts"], 0)
            self.assertEqual(
                cases["word.document.create_background"]["user_file_modification_attempts"],
                0,
            )
            word_details = cases["word.document.create_background"]["details"]
            self.assertEqual(word_details["decision"], "word_background_probe_verified")
            self.assertEqual(word_details["office_com_attempts"], 1)
            self.assertEqual(word_details["control_attempts"], 0)
            self.assertEqual(word_details["window_input_attempts"], 0)
            self.assertTrue(word_details["foreground_no_steal_verified"])
            self.assertTrue(word_details["foreground_focus_stable"])
            self.assertEqual(word_details["foreground_change_classification"], "stable")
            self.assertEqual(
                word_details["foreground_snapshot_before"]["process_name"],
                "Weixin.exe",
            )
            self.assertTrue(Path(word_details["document_path"]).resolve().is_file())
            self.assertTrue(
                str(Path(word_details["document_path"]).resolve()).startswith(str(output_root))
            )
            self.assertEqual(word_calls[0]["marker"], "OPENWUKONG_WORD_PRIMARY_SCENARIO")

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
                artifact_text = artifact_path.read_text(encoding="utf-8")
                self.assertTrue(all(ord(char) < 128 for char in artifact_text))
                artifact = json.loads(artifact_text)
                self.assertEqual(artifact["safety_mode"], "real_no_loss")

            summary = summarize_report(report)
            self.assertEqual(summary["mode"], "primary-scenario-real-no-loss-summary")
            self.assertEqual(summary["passed_cases"], 5)
            self.assertEqual(summary["real_verified_cases"], 5)
            self.assertEqual(summary["uia_semantic_action_ready_cases"], 1)
            self.assertEqual(summary["uia_value_set_attempts"], 0)
            self.assertEqual(summary["uia_invoke_attempts"], 0)
            self.assertEqual(summary["computer_use_read_only_cases"], 1)
            self.assertEqual(summary["computer_use_attempts"], 2)
            self.assertEqual(summary["computer_use_window_input_attempts"], 0)
            self.assertFalse(summary["transport_matrix_summary"]["goal_complete"])
            self.assertEqual(
                summary["transport_matrix_summary"]["background_write_ready_cases"],
                1,
            )
            self.assertEqual(
                summary["transport_matrix_summary"]["write_blocked_cases"],
                2,
            )
            self.assertNotIn("details", summary["scenarios"][0])

    def test_runner_can_attach_no_focus_background_screenshots_to_wechat_case(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=7001,
                    process_name="Weixin.exe",
                    window_title="微信",
                    hwnd=7001,
                    elements=(_element("Pane", name="微信"),),
                )
            ]
        )

        def _fake_readiness_probe(debugger_url: str) -> dict:
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
                "page_identity": {"title": "OpenWukong Primary Smoke"},
                "action_result": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                    "textExcerpt": "OpenWukong Primary Smoke",
                },
                "post_action_identity": {"title": "OpenWukong Primary Smoke"},
                "error": "",
            }

        def _fake_word_background_probe(**kwargs) -> dict:
            Path(kwargs["document_path"]).write_bytes(b"fake-docx")
            return {
                "ok": True,
                "decision": "word_background_probe_verified",
                "document_path": kwargs["document_path"],
                "marker": kwargs["marker"],
                "save_verified": True,
                "readback_verified": True,
                "word_started": True,
                "visible_requested": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "office_com_attempts": 1,
                "error": "",
            }

        def _fake_ide_bridge_probe(bridge_url: str) -> dict:
            return {
                "mode": "ide-bridge-capability-capture",
                "safety_mode": "read_only",
                "control_allowed": False,
                "control_attempts": 0,
                "bridge_url": bridge_url,
                "ok": True,
                "command_count": 1,
                "commands": ["openwukong.readState"],
                "chat_adapters": [],
                "error": "",
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = _FakeBackgroundCaptureProvider()
            report = run_primary_real_no_loss(
                fixture,
                output_root=root,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=_FakeReadinessLauncher(),
                owned_browser_helper_terminator=_FakeReadinessTerminator(),
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9451,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
                browser_executable_resolver=lambda requested: requested,
                accessibility_observer=observer,
                wechat_win32_observer=StaticWin32WindowObserver({7001: ()}),
                ide_bridge_probe=_fake_ide_bridge_probe,
                word_background_probe_runner=_fake_word_background_probe,
                background_screenshot_dir=root / "background-screenshots",
                window_capture_provider=capture,
                system_dialog_preflight_runner=_clear_system_dialog_preflight,
            )
            data = report.to_dict()
            cases = {case["scenario_id"]: case for case in data["cases"]}
            wechat = cases["wechat.chat.draft_reply"]
            screenshot_path = Path(wechat["details"]["background_screenshots"][0]["output_path"])
            self.assertTrue(screenshot_path.is_file())
            summary = summarize_report(report)

            self.assertEqual(data["background_screenshot_count"], 1)
            self.assertEqual(data["background_screenshot_success_count"], 1)
            self.assertTrue(data["background_screenshot_focus_stable"])
            self.assertEqual(capture.calls[0][0], 7001)
            self.assertEqual(wechat["details"]["background_screenshot_count"], 1)
            self.assertEqual(wechat["details"]["background_screenshot_success_count"], 1)
            self.assertTrue(wechat["details"]["background_screenshot_focus_stable"])
            self.assertFalse(wechat["details"]["background_screenshots"][0]["foreground_changed"])
            self.assertEqual(summary["background_screenshot_count"], 1)
            self.assertTrue(summary["background_screenshot_focus_stable"])

    def test_runner_can_execute_opt_in_wechat_uia_semantic_send_without_window_input(self):
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
                        _element("Text", name="文件传输助手"),
                        _element("Edit", name="Type a message", patterns=("Value", "Text")),
                        _element("Button", name="Send", patterns=("Invoke",)),
                    ),
                )
            ]
        )
        sender_calls = []

        class FakeWeChatUiaSender:
            def send(self, request):
                sender_calls.append(request)
                return {
                    "mode": "wechat-uia-semantic-action-send",
                    "safety_mode": "uia_semantic_execute",
                    "ok": True,
                    "decision": "wechat_uia_semantic_action_send_accepted",
                    "control_attempts": 0,
                    "send_attempts": 1,
                    "window_input_attempts": 0,
                    "keyboard_input_attempts": 0,
                    "clipboard_write_attempts": 0,
                    "uia_value_set_attempts": 1,
                    "uia_invoke_attempts": 1,
                    "foreground_focus_stable": True,
                    "missing_required_markers": [],
                    "present_forbidden_markers": [],
                    "request": request.to_dict(),
                    "operation_result": {
                        "readbackText": f"File Transfer Assistant\n{request.message}",
                    },
                }

        def _fake_readiness_probe(debugger_url: str) -> dict:
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
            return {
                "mode": "browser-devtools-action",
                "ok": True,
                "health_ok": True,
                "control_attempts": 0,
                "action": kwargs["action"],
                "action_result": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                    "textExcerpt": "OpenWukong Primary Smoke",
                },
            }

        def _fake_word_background_probe(**kwargs) -> dict:
            Path(kwargs["document_path"]).write_bytes(b"fake-docx")
            return {
                "ok": True,
                "decision": "word_background_probe_verified",
                "document_path": kwargs["document_path"],
                "marker": kwargs["marker"],
                "save_verified": True,
                "readback_verified": True,
                "word_started": True,
                "visible_requested": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "office_com_attempts": 1,
                "error": "",
            }

        def _fake_ide_bridge_probe(bridge_url: str) -> dict:
            return {
                "mode": "ide-bridge-capability-capture",
                "ok": True,
                "control_attempts": 0,
                "bridge_url": bridge_url,
                "command_count": 1,
                "commands": ["openwukong.readState"],
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = _FakeBackgroundCaptureProvider()
            report = run_primary_real_no_loss(
                fixture,
                output_root=root,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=_FakeReadinessLauncher(),
                owned_browser_helper_terminator=_FakeReadinessTerminator(),
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9452,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
                browser_executable_resolver=lambda requested: requested,
                accessibility_observer=observer,
                wechat_win32_observer=StaticWin32WindowObserver({7001: ()}),
                word_background_probe_runner=_fake_word_background_probe,
                ide_bridge_probe=_fake_ide_bridge_probe,
                allow_wechat_uia_semantic_send=True,
                wechat_uia_message="OPENWUKONG_WECHAT_UIA_ACCEPTANCE: PASS",
                wechat_uia_required_markers=("OPENWUKONG_WECHAT_UIA_ACCEPTANCE: PASS",),
                wechat_uia_sender=FakeWeChatUiaSender(),
                background_screenshot_dir=root / "background-screenshots",
                window_capture_provider=capture,
                system_dialog_preflight_runner=_clear_system_dialog_preflight,
            )
            data = report.to_dict()

        self.assertEqual(len(sender_calls), 1)
        self.assertEqual(sender_calls[0].message, "OPENWUKONG_WECHAT_UIA_ACCEPTANCE: PASS")
        self.assertEqual(data["external_communication_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 1)
        self.assertEqual(data["uia_invoke_attempts"], 1)
        cases = {case["scenario_id"]: case for case in data["cases"]}
        wechat = cases["wechat.chat.draft_reply"]
        self.assertEqual(wechat["send_attempts"], 1)
        self.assertEqual(wechat["window_input_attempts"], 0)
        self.assertTrue(wechat["details"]["background_send_verified"])
        self.assertEqual(
            wechat["details"]["uia_semantic_action_send_report"]["decision"],
            "wechat_uia_semantic_action_send_accepted",
        )

    def test_runner_can_execute_opt_in_wechat_native_bridge_send_without_window_input(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=7001,
                    process_name="Weixin.exe",
                    window_title="WeChat",
                    hwnd=7001,
                    elements=(
                        _element("Text", name="File Transfer Assistant"),
                    ),
                )
            ]
        )
        bridge_requests = []
        send_requests = []

        class FakeWeChatNativeBridgeDryRun:
            def prepare(self, request):
                bridge_requests.append(request)
                return {
                    "mode": "wechat-native-bridge-dry-run",
                    "safety_mode": "dry_run",
                    "ok": True,
                    "decision": "wechat_native_bridge_dry_run_ready",
                    "control_attempts": 0,
                    "send_attempts": 0,
                    "window_input_attempts": 0,
                    "capability_probe_attempts": 1,
                    "request": request.to_dict(),
                }

        class FakeWeChatNativeBridgeSender:
            def send(self, request):
                send_requests.append(request)
                return {
                    "mode": "wechat-native-bridge-send",
                    "safety_mode": "native_bridge_execute",
                    "ok": True,
                    "decision": "wechat_native_bridge_send_accepted",
                    "control_attempts": 0,
                    "send_attempts": 1,
                    "native_call_attempts": 1,
                    "window_input_attempts": 0,
                    "keyboard_input_attempts": 0,
                    "clipboard_write_attempts": 0,
                    "foreground_focus_stable": True,
                    "missing_required_markers": [],
                    "present_forbidden_markers": [],
                    "request": request.to_dict(),
                    "action_result": {
                        "readbackText": f"File Transfer Assistant\n{request.message}",
                    },
                }

        def _fake_readiness_probe(debugger_url: str) -> dict:
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
            return {
                "mode": "browser-devtools-action",
                "ok": True,
                "health_ok": True,
                "control_attempts": 0,
                "action": kwargs["action"],
                "action_result": {
                    "title": "OpenWukong Primary Smoke",
                    "href": kwargs["resource_url"],
                    "readyState": "complete",
                    "textExcerpt": "OpenWukong Primary Smoke",
                },
            }

        def _fake_word_background_probe(**kwargs) -> dict:
            Path(kwargs["document_path"]).write_bytes(b"fake-docx")
            return {
                "ok": True,
                "decision": "word_background_probe_verified",
                "document_path": kwargs["document_path"],
                "marker": kwargs["marker"],
                "save_verified": True,
                "readback_verified": True,
                "word_started": True,
                "visible_requested": False,
                "control_attempts": 0,
                "window_input_attempts": 0,
                "office_com_attempts": 1,
                "error": "",
            }

        def _fake_ide_bridge_probe(bridge_url: str) -> dict:
            return {
                "mode": "ide-bridge-capability-capture",
                "ok": True,
                "control_attempts": 0,
                "bridge_url": bridge_url,
                "command_count": 1,
                "commands": ["openwukong.readState"],
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture = _FakeBackgroundCaptureProvider()
            report = run_primary_real_no_loss(
                fixture,
                output_root=root,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=_FakeReadinessLauncher(),
                owned_browser_helper_terminator=_FakeReadinessTerminator(),
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9453,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
                browser_executable_resolver=lambda requested: requested,
                accessibility_observer=observer,
                wechat_win32_observer=StaticWin32WindowObserver({7001: ()}),
                word_background_probe_runner=_fake_word_background_probe,
                ide_bridge_probe=_fake_ide_bridge_probe,
                wechat_native_bridge_urls=("http://127.0.0.1:18180",),
                allow_wechat_native_bridge_send=True,
                wechat_native_bridge_message="OPENWUKONG_WECHAT_NATIVE_ACCEPTANCE: PASS",
                wechat_native_bridge_required_markers=(
                    "OPENWUKONG_WECHAT_NATIVE_ACCEPTANCE: PASS",
                ),
                wechat_native_bridge_dry_run_adapter=FakeWeChatNativeBridgeDryRun(),
                wechat_native_bridge_sender=FakeWeChatNativeBridgeSender(),
                background_screenshot_dir=root / "background-screenshots",
                window_capture_provider=capture,
                system_dialog_preflight_runner=_clear_system_dialog_preflight,
            )
            data = report.to_dict()

        self.assertEqual(len(bridge_requests), 1)
        self.assertTrue(bridge_requests[0].background_screenshot_verified)
        self.assertEqual(len(send_requests), 1)
        self.assertEqual(
            send_requests[0].message,
            "OPENWUKONG_WECHAT_NATIVE_ACCEPTANCE: PASS",
        )
        self.assertEqual(data["external_communication_attempts"], 1)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["uia_value_set_attempts"], 0)
        self.assertEqual(data["uia_invoke_attempts"], 0)
        cases = {case["scenario_id"]: case for case in data["cases"]}
        wechat = cases["wechat.chat.draft_reply"]
        self.assertEqual(wechat["send_attempts"], 1)
        self.assertEqual(wechat["window_input_attempts"], 0)
        self.assertTrue(wechat["details"]["wechat_native_bridge_ready"])
        self.assertTrue(wechat["details"]["background_send_verified"])
        self.assertEqual(
            wechat["details"]["wechat_native_bridge_send_report"]["decision"],
            "wechat_native_bridge_send_accepted",
        )

    def test_runner_discovers_wechat_native_bridge_url_from_registry_file(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )
        fixture = {"suite": fixture["suite"], "cases": [fixture["cases"][0]]}
        observer = StaticAccessibilityObserver(
            [
                AccessibilityWindowSnapshot(
                    pid=7001,
                    process_name="Weixin.exe",
                    window_title="WeChat",
                    hwnd=7001,
                    elements=(
                        _element("Text", name="File Transfer Assistant"),
                    ),
                )
            ]
        )
        bridge_requests = []

        class FakeWeChatNativeBridgeDryRun:
            def prepare(self, request):
                bridge_requests.append(request)
                return {
                    "mode": "wechat-native-bridge-dry-run",
                    "safety_mode": "dry_run",
                    "ok": True,
                    "decision": "wechat_native_bridge_dry_run_ready",
                    "control_attempts": 0,
                    "send_attempts": 0,
                    "window_input_attempts": 0,
                    "capability_probe_attempts": 1,
                    "request": request.to_dict(),
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "wechat-native-bridges.json"
            registry.write_text(
                json.dumps(
                    {
                        "wechat_native_bridges": [
                            {"bridge_url": "http://127.0.0.1:18190"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "OPENWUKONG_WECHAT_NATIVE_BRIDGE_URLS": "",
                    "OPENWUKONG_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS": "",
                },
                clear=False,
            ):
                report = run_primary_real_no_loss(
                    fixture,
                    output_root=root,
                    accessibility_observer=observer,
                    wechat_win32_observer=StaticWin32WindowObserver({7001: ()}),
                    wechat_native_bridge_registry_paths=(registry,),
                    wechat_native_bridge_message="OPENWUKONG_WECHAT_REGISTRY: PASS",
                    wechat_native_bridge_required_markers=(
                        "OPENWUKONG_WECHAT_REGISTRY: PASS",
                    ),
                    wechat_native_bridge_dry_run_adapter=FakeWeChatNativeBridgeDryRun(),
                    background_screenshot_dir=root / "background-screenshots",
                    window_capture_provider=_FakeBackgroundCaptureProvider(),
                    system_dialog_preflight_runner=_clear_system_dialog_preflight,
                )
            data = report.to_dict()

        self.assertEqual(len(bridge_requests), 1)
        self.assertEqual(bridge_requests[0].bridge_url, "http://127.0.0.1:18190")
        self.assertEqual(data["external_communication_attempts"], 0)
        cases = {case["scenario_id"]: case for case in data["cases"]}
        wechat = cases["wechat.chat.draft_reply"]
        self.assertEqual(
            wechat["details"]["wechat_native_bridge_urls"],
            ["http://127.0.0.1:18190"],
        )
        self.assertTrue(wechat["details"]["wechat_native_bridge_ready"])


if __name__ == "__main__":
    unittest.main()
