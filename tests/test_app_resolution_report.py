import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.control.app_resolution import (
    AppResolutionCandidate,
    StaticAppCandidateProvider,
    WindowsAppResolver,
)
from openwukong.evaluation.app_resolution_report import (
    build_app_resolution_report,
    main,
)


class AppResolutionReportTests(unittest.TestCase):
    def test_report_is_read_only_and_includes_resolution_details(self):
        exe = "E:/software/Weixin/Weixin.exe"
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="Weixin.exe",
                            process_name="Weixin.exe",
                            executable_name="Weixin.exe",
                            path=exe,
                            pid=8668,
                        )
                    ]
                ),
            )
        )

        report = build_app_resolution_report(["wechat"], resolver=resolver)
        data = report.to_dict()

        self.assertEqual(data["mode"], "app-resolution-report")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["summary"]["resolved"], 1)
        self.assertEqual(data["apps"][0]["app_name"], "wechat")
        self.assertEqual(data["apps"][0]["resolution"]["path"], exe)
        self.assertEqual(data["apps"][0]["resolution"]["source"], "running-process")

    def test_report_summarizes_ambiguous_resolution(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
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
                ),
            )
        )

        data = build_app_resolution_report(["wechat"], resolver=resolver).to_dict()

        self.assertEqual(data["summary"]["ambiguous"], 1)
        self.assertEqual(data["apps"][0]["resolution"]["error"], "ambiguous_app_candidates")
        self.assertEqual(data["apps"][0]["candidate_count"], 2)

    def test_main_writes_json_output(self):
        exe = "E:/software/Weixin/Weixin.exe"
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
                    [
                        AppResolutionCandidate(
                            source="running-process",
                            display_name="Weixin.exe",
                            process_name="Weixin.exe",
                            executable_name="Weixin.exe",
                            path=exe,
                            pid=8668,
                        )
                    ]
                ),
            )
        )

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "app-resolution.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["--app-name", "wechat", "--output", str(output), "--json"],
                    resolver_factory=lambda args: resolver,
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "app-resolution-report")
        self.assertEqual(payload["apps"][0]["resolution"]["path"], exe)

    def test_report_can_cover_codex_and_claude_agent_surfaces(self):
        resolver = WindowsAppResolver(
            candidate_providers=(
                StaticAppCandidateProvider(
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
                            display_name="claude",
                            executable_name="claude.cmd",
                            path="C:/Users/me/AppData/Roaming/npm/claude.cmd",
                        ),
                    ]
                ),
            )
        )

        data = build_app_resolution_report(["codex", "claude"], resolver=resolver).to_dict()

        self.assertEqual(data["summary"]["app_count"], 2)
        self.assertEqual(data["summary"]["resolved"], 2)
        self.assertEqual(data["apps"][0]["resolution"]["app_id"], "codex")
        self.assertEqual(data["apps"][1]["resolution"]["app_id"], "claude")
        self.assertEqual(data["control_attempts"], 0)


if __name__ == "__main__":
    unittest.main()
