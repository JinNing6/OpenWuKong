import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    AppPathVerifier,
    StartMenuAppCandidateProvider,
    StaticAppCandidateProvider,
    WindowsAppResolver,
    WindowsShortcutTargetResolver,
    WindowsStartAppsCandidateProvider,
)


class AppResolutionModuleTests(unittest.TestCase):
    def test_control_layer_resolver_prefers_running_process(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Weixin.exe",
                    process_name="Weixin.exe",
                    executable_name="Weixin.exe",
                    path="E:/software/Weixin/Weixin.exe",
                    pid=8668,
                )
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("wechat")

        self.assertTrue(report.ok)
        self.assertTrue(report.already_running)
        self.assertEqual(report.source, "running-process")
        self.assertEqual(report.path, "E:/software/Weixin/Weixin.exe")

    def test_resolver_is_exported_from_control_package(self):
        from openwukong.control import WindowsAppResolver as ExportedResolver

        self.assertIs(ExportedResolver, WindowsAppResolver)

    def test_resolver_writes_high_confidence_resolution_to_cache(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "Weixin.exe"
            exe.write_text("fake exe", encoding="utf-8")
            cache = Path(td) / "app-resolution-cache.json"
            provider = StaticAppCandidateProvider(
                [
                    AppResolutionCandidate(
                        source="running-process",
                        display_name="Weixin.exe",
                        process_name="Weixin.exe",
                        executable_name="Weixin.exe",
                        path=str(exe),
                        pid=8668,
                    )
                ]
            )

            report = WindowsAppResolver(
                cache_path=cache,
                cache_write_enabled=True,
                candidate_providers=(provider,),
            ).resolve("wechat")

            payload = json.loads(cache.read_text(encoding="utf-8"))

        self.assertTrue(report.ok)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["apps"]["wechat"]["path"], str(exe))
        self.assertEqual(payload["apps"]["wechat"]["source"], "running-process")
        self.assertEqual(payload["apps"]["wechat"]["verification"]["size"], len("fake exe"))
        self.assertEqual(payload["apps"]["wechat"]["verification"]["executable_name"], "Weixin.exe")

    def test_local_cache_candidate_rejects_stale_file_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "Weixin.exe"
            exe.write_text("current", encoding="utf-8")
            cache = Path(td) / "app-resolution-cache.json"
            cache.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "apps": {
                            "wechat": {
                                "path": str(exe),
                                "display_name": "Weixin.exe",
                                "executable_name": "Weixin.exe",
                                "verification": {
                                    "path": str(exe),
                                    "exists": True,
                                    "is_file": True,
                                    "size": 999999,
                                    "mtime_ns": exe.stat().st_mtime_ns,
                                    "executable_name": "Weixin.exe",
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = WindowsAppResolver(cache_path=cache, candidate_providers=()).resolve("wechat")

        self.assertFalse(report.ok)
        self.assertEqual(report.error, "app_not_found")

    def test_chrome_resolution_does_not_include_generic_browser_shortcuts(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="start-menu",
                    display_name="Google Chrome",
                    path="C:/Start Menu/Google Chrome.lnk",
                ),
                AppResolutionCandidate(
                    source="start-menu",
                    display_name="Tabbit Browser",
                    path="C:/Start Menu/Tabbit Browser.lnk",
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("chrome")
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(data["path"], "C:/Start Menu/Google Chrome.lnk")
        self.assertEqual(
            [candidate["display_name"] for candidate in data["candidates"]],
            ["Google Chrome"],
        )

    def test_start_menu_shortcut_target_becomes_launchable_executable_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Programs"
            root.mkdir()
            link = root / "Cursor.lnk"
            link.write_text("shortcut placeholder", encoding="utf-8")
            target = Path(td) / "Cursor.exe"
            target.write_text("fake cursor exe", encoding="utf-8")
            calls = []

            def _shortcut_resolver(path):
                calls.append(path)
                return {
                    "target_path": str(target),
                    "arguments": "--profile test",
                    "working_directory": str(target.parent),
                }

            provider = StartMenuAppCandidateProvider(
                (root,),
                shortcut_target_resolver=_shortcut_resolver,
            )

            report = WindowsAppResolver(candidate_providers=(provider,)).resolve("cursor")
            data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(Path(report.path).name, "Cursor.exe")
        self.assertEqual(calls, [str(link)])
        self.assertEqual(
            data["selected_candidate"]["metadata"]["shortcut_path"],
            str(link),
        )
        self.assertEqual(
            data["selected_candidate"]["metadata"]["shortcut_arguments"],
            "--profile test",
        )

    def test_windows_shortcut_target_resolver_does_not_pass_path_as_powershell_tail_arg(self):
        calls = []

        def _runner(command):
            calls.append(tuple(command))
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "target_path": "C:/Apps/Cursor/Cursor.exe",
                        "arguments": "",
                        "working_directory": "C:/Apps/Cursor",
                    }
                ).encode("utf-8"),
                stderr=b"",
            )

        resolver = WindowsShortcutTargetResolver(command_runner=_runner)

        data = resolver("C:/ProgramData/Microsoft/Windows/Start Menu/Programs/Cursor.lnk")

        self.assertEqual(data["target_path"], "C:/Apps/Cursor/Cursor.exe")
        command = calls[0]
        self.assertEqual(command[-2], "-Command")
        self.assertNotEqual(
            command[-1],
            "C:/ProgramData/Microsoft/Windows/Start Menu/Programs/Cursor.lnk",
        )

    def test_codex_resolution_supports_desktop_and_cli_candidates(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Codex.exe",
                    process_name="Codex.exe",
                    executable_name="Codex.exe",
                    path="C:/Users/me/AppData/Local/OpenAI/Codex/Codex.exe",
                    pid=3001,
                ),
                AppResolutionCandidate(
                    source="path",
                    display_name="codex",
                    executable_name="codex.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/codex.cmd",
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("codex")
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertTrue(report.already_running)
        self.assertEqual(data["source"], "running-process")
        self.assertEqual(data["path"], "C:/Users/me/AppData/Local/OpenAI/Codex/Codex.exe")
        self.assertEqual(
            [candidate["source"] for candidate in data["candidates"]],
            ["running-process", "path"],
        )

    def test_codex_resolution_prefers_desktop_shell_over_worker_processes(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="codex.exe",
                    process_name="codex.exe",
                    executable_name="codex.exe",
                    path="C:/Program Files/WindowsApps/OpenAI.Codex/app/resources/codex.exe",
                    pid=3002,
                ),
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Codex.exe",
                    process_name="Codex.exe",
                    executable_name="Codex.exe",
                    path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    pid=3001,
                ),
                AppResolutionCandidate(
                    source="running-process",
                    display_name="codex.exe",
                    process_name="codex.exe",
                    executable_name="codex.exe",
                    path="C:/Users/me/.cursor/extensions/openai.chatgpt/bin/codex.exe",
                    pid=3003,
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("codex")

        self.assertTrue(report.ok)
        self.assertEqual(report.source, "running-process")
        self.assertEqual(report.path, "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe")

    def test_codex_aliases_resolve_to_same_codex_identity(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="codex",
                    executable_name="codex.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/codex.cmd",
                ),
            ]
        )

        for app_name in ("openai codex", "codex cli"):
            with self.subTest(app_name=app_name):
                report = WindowsAppResolver(candidate_providers=(provider,)).resolve(app_name)
                self.assertTrue(report.ok)
                self.assertEqual(report.identity.app_id, "codex")

    def test_codex_app_alias_requires_desktop_surface_not_cli_path(self):
        cli_provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="codex",
                    executable_name="codex.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/codex.cmd",
                ),
            ]
        )
        desktop_provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="codex",
                    executable_name="codex.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/codex.cmd",
                ),
                AppResolutionCandidate(
                    source="running-process",
                    display_name="Codex.exe",
                    process_name="Codex.exe",
                    executable_name="Codex.exe",
                    path="C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
                    pid=3001,
                ),
            ]
        )

        cli_only = WindowsAppResolver(candidate_providers=(cli_provider,)).resolve("codex app")
        with_desktop = WindowsAppResolver(candidate_providers=(desktop_provider,)).resolve("codex app")

        self.assertFalse(cli_only.ok)
        self.assertEqual(cli_only.error, "app_not_found")
        self.assertTrue(with_desktop.ok)
        self.assertEqual(
            with_desktop.path,
            "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe",
        )

    def test_claude_resolution_supports_claude_code_cli_without_model_name_false_positive(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="claude",
                    executable_name="claude.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                ),
                AppResolutionCandidate(
                    source="start-menu",
                    display_name="Claude Opus 4.6 Thinking",
                    path="C:/Start Menu/Claude Opus 4.6 Thinking.lnk",
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("claude")
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(data["path"], "C:/Users/me/AppData/Roaming/npm/claude.cmd")
        self.assertEqual(
            [candidate["display_name"] for candidate in data["candidates"]],
            ["claude"],
        )

    def test_start_apps_provider_reads_packaged_app_entries(self):
        provider = WindowsStartAppsCandidateProvider(
            command_runner=lambda command: SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [
                        {
                            "Name": "Claude",
                            "AppID": "Claude_pzs8sxrjxfjjc!Claude",
                        },
                        {
                            "Name": "Claude Opus 4.6 Thinking",
                            "AppID": "model-shortcut",
                        },
                    ]
                ),
                stderr="",
            )
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("claude app")
        data = report.to_dict()

        self.assertTrue(report.ok)
        self.assertEqual(data["source"], "start-apps")
        self.assertEqual(data["selected_candidate"]["display_name"], "Claude")
        self.assertEqual(
            data["selected_candidate"]["metadata"]["app_id"],
            "Claude_pzs8sxrjxfjjc!Claude",
        )
        self.assertEqual(
            [candidate["display_name"] for candidate in data["candidates"]],
            ["Claude"],
        )

    def test_start_apps_provider_decodes_utf8_stdout_bytes(self):
        payload = json.dumps(
            [
                {
                    "Name": "Claude",
                    "AppID": "Claude_pzs8sxrjxfjjc!Claude",
                },
                {
                    "Name": "应用入口",
                    "AppID": "utf8-only",
                },
            ],
            ensure_ascii=False,
        ).encode("utf-8")
        provider = WindowsStartAppsCandidateProvider(
            command_runner=lambda command: SimpleNamespace(
                returncode=0,
                stdout=payload,
                stderr=b"",
            )
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("claude app")

        self.assertTrue(report.ok)
        self.assertEqual(report.source, "start-apps")
        self.assertEqual(report.selected_candidate.metadata["app_id"], "Claude_pzs8sxrjxfjjc!Claude")

    def test_claude_code_aliases_resolve_to_same_claude_identity(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="claude",
                    executable_name="claude.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                ),
            ]
        )

        for app_name in ("claude code", "anthropic claude", "claude cli"):
            with self.subTest(app_name=app_name):
                report = WindowsAppResolver(candidate_providers=(provider,)).resolve(app_name)
                self.assertTrue(report.ok)
                self.assertEqual(report.identity.app_id, "claude")

    def test_claude_app_alias_requires_desktop_surface_not_cli_path(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="path",
                    display_name="claude",
                    executable_name="claude.cmd",
                    path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("claude app")

        self.assertFalse(report.ok)
        self.assertEqual(report.error, "app_not_found")


    def test_claude_desktop_alias_prefers_desktop_when_cli_process_is_transient(self):
        provider = StaticAppCandidateProvider(
            [
                AppResolutionCandidate(
                    source="running-process",
                    display_name="claude.exe",
                    process_name="claude.exe",
                    executable_name="claude.exe",
                    path="C:/Program Files/WindowsApps/Claude_1.9255.2.0_x64__pzs8sxrjxfjjc/app/claude.exe",
                    pid=11140,
                ),
                AppResolutionCandidate(
                    source="running-process",
                    display_name="claude.exe",
                    process_name="claude.exe",
                    executable_name="claude.exe",
                    path="C:/Users/me/.local/bin/claude.exe",
                    pid=75596,
                ),
            ]
        )

        report = WindowsAppResolver(candidate_providers=(provider,)).resolve("claude desktop")

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, "resolved")
        self.assertEqual(
            report.path,
            "C:/Program Files/WindowsApps/Claude_1.9255.2.0_x64__pzs8sxrjxfjjc/app/claude.exe",
        )

    def test_path_verifier_records_authenticode_signature_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "Weixin.exe"
            exe.write_text("fake exe", encoding="utf-8")
            verifier = AppPathVerifier(
                signature_reader=lambda path: {
                    "status": "Valid",
                    "subject": "CN=Tencent Technology",
                    "issuer": "CN=Trusted Root",
                }
            )

            verification = verifier.verify_path(str(exe), expected_executable_names=("Weixin.exe",))

        self.assertTrue(verification.ok)
        self.assertEqual(verification.signature_status, "Valid")
        self.assertEqual(verification.signature_subject, "CN=Tencent Technology")


if __name__ == "__main__":
    unittest.main()
