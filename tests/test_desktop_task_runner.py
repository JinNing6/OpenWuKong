import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.desktop_task_runner import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    FakeAppLauncher,
    FakeBrowserOpener,
    WindowsAppLauncher,
    WindowsAppResolver,
    desktop_task_exit_code,
    run_desktop_task,
)
from openwukong.evaluation.wechat_send_probe import FakeWeChatKeyboardAutomation


class _FakeBrowserActionReport:
    def to_dict(self):
        return {
            "mode": "browser-devtools-action",
            "ok": True,
            "control_allowed": True,
            "control_attempts": 1,
            "action": "navigate_url",
        }


class _FakeBrowserActionRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _FakeBrowserActionReport()


class DesktopTaskRunnerTests(unittest.TestCase):
    def test_app_already_running_is_success_exit_status(self):
        self.assertEqual(desktop_task_exit_code("app_already_running"), 0)

    def test_open_app_requires_explicit_launch_permission(self):
        launcher = FakeAppLauncher({"wechat": "C:/Start Menu/WeChat.lnk"})

        report = run_desktop_task(
            task_type="open_app",
            app_name="wechat",
            app_launcher=launcher,
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "desktop-task-runner")
        self.assertEqual(data["status"], "blocked_launch_requires_explicit_permission")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(launcher.launches, [])

    def test_open_app_launches_resolved_start_menu_entry_after_permission(self):
        launcher = FakeAppLauncher({"wechat": "C:/Start Menu/WeChat.lnk"})

        report = run_desktop_task(
            task_type="open_app",
            app_name="wechat",
            allow_launch=True,
            app_launcher=launcher,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "app_launched")
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["app_name"], "wechat")
        self.assertEqual(data["launch_attempts"], 1)
        self.assertEqual(data["app_launch"]["path"], "C:/Start Menu/WeChat.lnk")
        self.assertEqual(launcher.launches, ["C:/Start Menu/WeChat.lnk"])

    def test_wechat_app_resolution_does_not_match_enterprise_wechat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            enterprise = root / "企业微信" / "企业微信.lnk"
            enterprise.parent.mkdir(parents=True)
            enterprise.write_text("fake", encoding="utf-8")
            launcher = WindowsAppLauncher(start_menu_roots=(root,))

            resolved = launcher.resolve("wechat")

        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["error"], "app_not_found")

    def test_wechat_app_resolution_does_not_match_wechat_input_method(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ime = root / "微信输入法" / "微信输入法.lnk"
            ime.parent.mkdir(parents=True)
            ime.write_text("fake", encoding="utf-8")
            launcher = WindowsAppLauncher(start_menu_roots=(root,))

            resolved = launcher.resolve("wechat")

        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["error"], "app_not_found")

    def test_wechat_app_resolution_prefers_personal_wechat_over_enterprise_wechat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            enterprise = root / "企业微信" / "企业微信.lnk"
            personal = root / "微信.lnk"
            enterprise.parent.mkdir(parents=True)
            enterprise.write_text("fake", encoding="utf-8")
            personal.write_text("fake", encoding="utf-8")
            launcher = WindowsAppLauncher(start_menu_roots=(root,))

            resolved = launcher.resolve("wechat")

        self.assertTrue(resolved["ok"])
        self.assertEqual(Path(resolved["path"]).name, "微信.lnk")

    def test_app_resolver_prefers_running_process_without_launching(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="微信",
                    process_name="Weixin.exe",
                    pid=8668,
                )
            ]
        )
        launcher = WindowsAppLauncher(
            resolver=WindowsAppResolver(candidate_providers=(provider,)),
        )

        report = run_desktop_task(
            task_type="open_app",
            app_name="wechat",
            allow_launch=True,
            app_launcher=launcher,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "app_already_running")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["launch_attempts"], 0)
        self.assertEqual(data["app_launch"]["pid"], 8668)
        self.assertEqual(data["app_launch"]["resolution"]["selected_candidate"]["source"], "running-process")

    def test_app_resolver_dedupes_multiple_running_processes_from_same_executable_path(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Weixin.exe",
                    process_name="Weixin.exe",
                    executable_name="Weixin.exe",
                    path="E:/software/Weixin/Weixin.exe",
                    pid=1001,
                ),
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Weixin.exe",
                    process_name="Weixin.exe",
                    executable_name="Weixin.exe",
                    path="E:/software/Weixin/Weixin.exe",
                    pid=1002,
                ),
            ]
        )
        launcher = WindowsAppLauncher(
            resolver=WindowsAppResolver(candidate_providers=(provider,)),
        )

        resolved = launcher.resolve("wechat")

        self.assertTrue(resolved["ok"])
        self.assertTrue(resolved["already_running"])
        self.assertEqual(resolved["source"], "running-process")
        self.assertEqual(len(resolved["candidates"]), 1)

    def test_app_resolver_blocks_ambiguous_exact_candidates_at_same_priority(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="start-menu",
                    display_name="微信",
                    path="C:/Apps/WeChat-A/微信.lnk",
                ),
                AppResolutionCandidate(
                    source="start-menu",
                    display_name="微信",
                    path="D:/Apps/WeChat-B/微信.lnk",
                ),
            ]
        )
        launcher = WindowsAppLauncher(
            resolver=WindowsAppResolver(candidate_providers=(provider,)),
        )

        resolved = launcher.resolve("wechat")

        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["error"], "ambiguous_app_candidates")
        self.assertEqual(len(resolved["candidates"]), 2)

    def test_local_cache_candidate_is_used_when_identity_matches(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "Weixin.exe"
            exe.write_text("fake", encoding="utf-8")
            cache = Path(td) / "app-cache.json"
            cache.write_text(
                '{"apps": {"wechat": {"path": "' + str(exe).replace("\\", "\\\\") + '", "display_name": "微信"}}}',
                encoding="utf-8",
            )
            launcher = WindowsAppLauncher(
                resolver=WindowsAppResolver(cache_path=cache, candidate_providers=()),
            )

            resolved = launcher.resolve("wechat")

        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["source"], "local-cache")
        self.assertEqual(Path(resolved["path"]).name, "Weixin.exe")

    def test_browser_search_uses_devtools_when_debugger_url_is_available(self):
        runner = _FakeBrowserActionRunner()

        report = run_desktop_task(
            task_type="browser_search",
            query="openwukong 精准控制",
            browser_debugger_url="http://127.0.0.1:9222",
            browser_action_runner=runner,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "browser_search_opened")
        self.assertEqual(data["browser_search_url"], "https://www.bing.com/search?q=openwukong+%E7%B2%BE%E5%87%86%E6%8E%A7%E5%88%B6")
        self.assertEqual(data["selected_transport"], "chrome-devtools-protocol")
        self.assertEqual(data["browser_navigation_attempts"], 1)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0]["action"], "navigate_url")
        self.assertEqual(runner.calls[0]["url"], data["browser_search_url"])

    def test_browser_search_without_devtools_requires_launch_permission(self):
        opener = FakeBrowserOpener()

        report = run_desktop_task(
            task_type="browser_search",
            query="openwukong",
            browser_opener=opener,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_browser_requires_debugger_or_launch_permission")
        self.assertEqual(data["browser_navigation_attempts"], 0)
        self.assertEqual(opener.opened_urls, [])

    def test_browser_search_can_open_system_browser_url_after_permission(self):
        opener = FakeBrowserOpener()

        report = run_desktop_task(
            task_type="browser_search",
            query="openwukong",
            allow_launch=True,
            browser_opener=opener,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "browser_search_opened")
        self.assertEqual(data["selected_transport"], "system-browser-url-open")
        self.assertEqual(data["browser_navigation_attempts"], 1)
        self.assertEqual(opener.opened_urls, ["https://www.bing.com/search?q=openwukong"])

    def test_wechat_send_emits_takeover_request_until_approved(self):
        automation = FakeWeChatKeyboardAutomation()

        report = run_desktop_task(
            task_type="wechat_send",
            target_name="文件传输助手",
            message="hello",
            allow_send=True,
            wechat_automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "foreground_takeover_request_pending")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["foreground_takeover_request"]["mode"], "foreground-takeover-request")
        self.assertEqual(automation.events, [])

    def test_wechat_send_consumes_takeover_request_when_approved(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=True)

        report = run_desktop_task(
            task_type="wechat_send",
            target_name="文件传输助手",
            message="hello",
            allow_send=True,
            approve_foreground_takeover=True,
            wechat_automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(data["wechat_send"]["status"], "sent")
        self.assertTrue(data["wechat_send"]["foreground_takeover_validated"])

    def test_wechat_send_can_use_second_stage_target_confirmation(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=False)

        report = run_desktop_task(
            task_type="wechat_send",
            target_name="文件传输助手",
            message="hello",
            allow_send=True,
            approve_foreground_takeover=True,
            confirm_target_after_open=True,
            wechat_automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "sent")
        self.assertEqual(data["send_attempts"], 1)
        self.assertTrue(data["wechat_send"]["target_verified"])

    def test_wechat_send_external_target_requires_extra_permission(self):
        automation = FakeWeChatKeyboardAutomation(target_verified=True)

        report = run_desktop_task(
            task_type="wechat_send",
            target_name="张三",
            message="hello",
            allow_send=True,
            approve_foreground_takeover=True,
            wechat_automation=automation,
        )
        data = report.to_dict()

        self.assertEqual(data["status"], "blocked_external_target_requires_explicit_permission")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(automation.events, [])


if __name__ == "__main__":
    unittest.main()
