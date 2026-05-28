import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    AppPathVerifier,
    StaticAppCandidateProvider,
    WindowsAppResolver,
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

        for app_name in ("openai codex", "codex cli", "codex app"):
            with self.subTest(app_name=app_name):
                report = WindowsAppResolver(candidate_providers=(provider,)).resolve(app_name)
                self.assertTrue(report.ok)
                self.assertEqual(report.identity.app_id, "codex")

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

        for app_name in ("claude code", "anthropic claude", "claude cli", "claude app", "claude desktop app"):
            with self.subTest(app_name=app_name):
                report = WindowsAppResolver(candidate_providers=(provider,)).resolve(app_name)
                self.assertTrue(report.ok)
                self.assertEqual(report.identity.app_id, "claude")

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
