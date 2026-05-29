import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openwukong.evaluation import primary_scenario_smoke
from openwukong.evaluation.primary_scenario_smoke import main, run_primary_scenario_smoke, summarize_report
from openwukong.evaluation.simulation import load_simulation_fixture


class _FakeReadinessLauncher:
    def __init__(self):
        self.calls: list[dict] = []

    def launch(self, argv: tuple[str, ...], cwd: str | None = None) -> int:
        self.calls.append({"argv": tuple(argv), "cwd": cwd})
        return 424242


class _FakeReadinessTerminator:
    def __init__(self):
        self.tree_pids: list[int] = []
        self.owned_argv: list[tuple[str, ...]] = []

    def terminate_tree(self, pid: int) -> None:
        self.tree_pids.append(int(pid))

    def terminate_owned_processes(self, argv: tuple[str, ...]) -> None:
        self.owned_argv.append(tuple(argv))


class PrimaryScenarioSmokeTests(unittest.TestCase):
    def test_smoke_reuses_l1_primary_scenario_plans_and_writes_isolated_artifacts(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )

        with tempfile.TemporaryDirectory() as tmp:
            report = run_primary_scenario_smoke(fixture, output_root=tmp)
            data = report.to_dict()
            output_root = Path(tmp).resolve()

            self.assertEqual(data["mode"], "primary-scenario-smoke")
            self.assertEqual(data["safety_mode"], "isolated_no_focus")
            self.assertFalse(data["control_allowed"])
            self.assertEqual(data["control_attempts"], 0)
            self.assertEqual(data["desktop_scan_attempts"], 0)
            self.assertEqual(data["window_input_attempts"], 0)
            self.assertEqual(data["live_app_launch_attempts"], 0)
            self.assertEqual(data["real_filesystem_scan_attempts"], 0)
            self.assertEqual(data["passed_cases"], 5)
            self.assertEqual(data["failed_cases"], 0)

            cases = {case["case_id"]: case for case in data["cases"]}
            self.assertEqual(
                set(cases),
                {
                    "wechat_chat_draft_reply",
                    "browser_research_collect_sources",
                    "files_search_find_candidate",
                    "word_document_create_background",
                    "codex_project_submit_task_draft",
                },
            )
            for case in cases.values():
                artifact_path = Path(case["artifact_path"]).resolve()
                adapter_artifact_path = Path(case["adapter_artifact_path"]).resolve()
                self.assertEqual(case["owned_browser_helper_id"], "")
                self.assertEqual(case["owned_browser_helper_artifact_path"], "")
                self.assertTrue(
                    str(artifact_path).startswith(str(output_root)),
                    f"{artifact_path} is outside {output_root}",
                )
                self.assertTrue(
                    str(adapter_artifact_path).startswith(str(output_root)),
                    f"{adapter_artifact_path} is outside {output_root}",
                )
                self.assertTrue(artifact_path.is_file())
                self.assertTrue(adapter_artifact_path.is_file())
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                adapter_artifact = json.loads(adapter_artifact_path.read_text(encoding="utf-8"))
                self.assertEqual(artifact["status"], "draft_only")
                self.assertEqual(artifact["source_plan"]["mode"], "primary-scenario-plan")
                self.assertEqual(artifact["source_plan"]["control_attempts"], 0)
                self.assertEqual(
                    artifact["side_effect_policy"]["mode"],
                    "primary-scenario-side-effect-policy",
                )
                self.assertEqual(artifact["isolation"]["output_root"], str(output_root))
                self.assertEqual(adapter_artifact["mode"], "primary-scenario-adapter-artifact")
                self.assertEqual(adapter_artifact["safety_mode"], "isolated_no_focus")
                self.assertEqual(adapter_artifact["control_attempts"], 0)
                self.assertEqual(
                    adapter_artifact["side_effect_policy"]["taxonomy_version"],
                    "primary-side-effects-v1",
                )
                self.assertEqual(adapter_artifact["isolation"]["output_root"], str(output_root))

            browser_dry_run_path = Path(
                cases["browser_research_collect_sources"]["owned_session_dry_run_artifact_path"]
            ).resolve()
            codex_dry_run_path = Path(
                cases["codex_project_submit_task_draft"]["owned_session_dry_run_artifact_path"]
            ).resolve()
            self.assertTrue(str(browser_dry_run_path).startswith(str(output_root)))
            self.assertTrue(str(codex_dry_run_path).startswith(str(output_root)))
            self.assertTrue(browser_dry_run_path.is_file())
            self.assertTrue(codex_dry_run_path.is_file())
            self.assertEqual(
                cases["wechat_chat_draft_reply"]["owned_session_dry_run_artifact_path"],
                "",
            )
            self.assertEqual(
                cases["files_search_find_candidate"]["owned_session_dry_run_artifact_path"],
                "",
            )
            self.assertEqual(
                cases["word_document_create_background"]["owned_session_dry_run_artifact_path"],
                "",
            )

            browser_dry_run = json.loads(browser_dry_run_path.read_text(encoding="utf-8"))
            self.assertEqual(browser_dry_run["mode"], "primary-scenario-owned-session-dry-run")
            self.assertEqual(browser_dry_run["safety_mode"], "isolated_owned_session_dry_run")
            self.assertFalse(browser_dry_run["control_allowed"])
            self.assertEqual(browser_dry_run["control_attempts"], 0)
            self.assertEqual(browser_dry_run["route_id"], "browser-devtools-or-extension")
            self.assertTrue(browser_dry_run["ownership"]["owned"])
            self.assertEqual(browser_dry_run["ownership"]["connector_id"], "browser")
            self.assertEqual(browser_dry_run["dispatch_report"]["decision"], "dispatch_connector")
            self.assertEqual(browser_dry_run["dispatch_report"]["control_attempts"], 0)
            self.assertTrue(browser_dry_run["dispatch_report"]["ownership"]["owned"])
            self.assertEqual(browser_dry_run["side_effect_gate"]["decision"], "allow")
            self.assertFalse(browser_dry_run["isolation"]["live_app_launch_allowed"])
            self.assertFalse(browser_dry_run["isolation"]["window_input_allowed"])

            browser_execution_path_text = cases["browser_research_collect_sources"].get(
                "owned_session_execution_artifact_path"
            )
            self.assertTrue(browser_execution_path_text)
            browser_execution_path = Path(browser_execution_path_text).resolve()
            self.assertTrue(str(browser_execution_path).startswith(str(output_root)))
            self.assertTrue(browser_execution_path.is_file())
            browser_execution = json.loads(browser_execution_path.read_text(encoding="utf-8"))
            self.assertEqual(
                browser_execution["execution_id"],
                "browser-owned-session-local-mock-devtools",
            )
            self.assertEqual(
                browser_execution["safety_mode"],
                "isolated_owned_session_local_mock",
            )
            self.assertEqual(
                browser_execution["execute_report"]["selected_route"],
                "browser-devtools-or-extension",
            )
            self.assertEqual(
                browser_execution["execute_report"]["selected_connector_id"],
                "browser",
            )
            self.assertEqual(browser_execution["execute_report"]["decision"], "executed")
            self.assertTrue(browser_execution["execute_report"]["ok"])
            self.assertGreaterEqual(browser_execution["local_connector_call_attempts"], 2)
            self.assertEqual(browser_execution["desktop_control_attempts"], 0)
            self.assertEqual(
                browser_execution["execute_report"]["action_report"]["mode"],
                "browser-devtools-action",
            )
            self.assertTrue(browser_execution["execute_report"]["action_report"]["health_ok"])
            self.assertEqual(
                browser_execution["execute_report"]["action_report"]["action"],
                "extract_results",
            )
            self.assertEqual(
                browser_execution["execute_report"]["action_report"]["action_result"]["selector"],
                "a",
            )
            self.assertEqual(
                browser_execution["local_devtools_fixture"]["target"]["type"],
                "page",
            )
            self.assertGreaterEqual(
                browser_execution["local_devtools_fixture"]["cdp_request_count"],
                2,
            )
            self.assertEqual(
                browser_execution["local_devtools_fixture"]["cdp_requests"][0]["method"],
                "Runtime.evaluate",
            )
            self.assertGreaterEqual(
                len(browser_execution["execute_report"]["action_report"]["action_result"]["items"]),
                3,
            )
            self.assertFalse(browser_execution["isolation"]["window_input_allowed"])

            codex_dry_run = json.loads(codex_dry_run_path.read_text(encoding="utf-8"))
            self.assertEqual(codex_dry_run["route_id"], "ide-extension-connector")
            self.assertTrue(codex_dry_run["ownership"]["owned"])
            self.assertEqual(codex_dry_run["ownership"]["connector_id"], "ide-extension")
            self.assertEqual(codex_dry_run["dispatch_report"]["decision"], "dispatch_connector")
            self.assertEqual(
                codex_dry_run["dispatch_report"]["selected_connector_id"],
                "ide-extension",
            )
            self.assertEqual(codex_dry_run["dispatch_report"]["control_attempts"], 0)
            self.assertFalse(codex_dry_run["isolation"]["real_user_profile_allowed"])

            codex_execution_path_text = cases["codex_project_submit_task_draft"].get(
                "owned_session_execution_artifact_path"
            )
            self.assertTrue(codex_execution_path_text)
            codex_execution_path = Path(codex_execution_path_text).resolve()
            self.assertTrue(str(codex_execution_path).startswith(str(output_root)))
            self.assertTrue(codex_execution_path.is_file())
            codex_execution = json.loads(codex_execution_path.read_text(encoding="utf-8"))
            self.assertEqual(
                codex_execution["mode"],
                "primary-scenario-owned-session-execution",
            )
            self.assertEqual(
                codex_execution["safety_mode"],
                "isolated_owned_session_local_mock",
            )
            self.assertEqual(
                codex_execution["execution_id"],
                "codex-owned-session-local-mock-bridge",
            )
            self.assertFalse(codex_execution["desktop_control_allowed"])
            self.assertEqual(codex_execution["desktop_control_attempts"], 0)
            self.assertTrue(codex_execution["local_connector_call_allowed"])
            self.assertEqual(codex_execution["local_connector_call_attempts"], 1)
            self.assertEqual(codex_execution["execute_report"]["decision"], "executed")
            self.assertTrue(codex_execution["execute_report"]["ok"])
            self.assertTrue(codex_execution["execute_report"]["ownership"]["owned"])
            self.assertEqual(
                codex_execution["execute_report"]["selected_route"],
                "ide-extension-connector",
            )
            self.assertEqual(
                codex_execution["execute_report"]["selected_connector_id"],
                "ide-extension",
            )
            self.assertEqual(
                codex_execution["execute_report"]["action_report"]["payload"]["transport"],
                "vscode-extension-bridge",
            )
            self.assertEqual(
                codex_execution["mock_bridge"]["request_count"],
                1,
            )
            self.assertEqual(
                codex_execution["mock_bridge"]["requests"][0]["path"],
                "/v1/ide/send",
            )
            self.assertIn(
                "L1",
                codex_execution["mock_bridge"]["requests"][0]["payload"]["message"],
            )
            self.assertFalse(codex_execution["isolation"]["window_input_allowed"])
            self.assertFalse(codex_execution["isolation"]["live_app_launch_allowed"])

            self.assertIn(
                "send_message",
                cases["wechat_chat_draft_reply"]["blocked_primitives"],
            )
            self.assertIn(
                "submit_task",
                cases["codex_project_submit_task_draft"]["blocked_primitives"],
            )
            self.assertEqual(
                cases["wechat_chat_draft_reply"]["adapter_id"],
                "wechat-recorded-uia-bundle",
            )
            self.assertEqual(
                cases["browser_research_collect_sources"]["adapter_id"],
                "browser-static-dom-bundle",
            )
            self.assertEqual(
                cases["files_search_find_candidate"]["adapter_id"],
                "file-search-temp-index",
            )
            self.assertEqual(
                cases["codex_project_submit_task_draft"]["adapter_id"],
                "codex-draft-queue",
            )
            self.assertEqual(
                cases["word_document_create_background"]["adapter_id"],
                "word-owned-docx-template",
            )
            self.assertEqual(
                [
                    effect["category"]
                    for effect in cases["files_search_find_candidate"]["blocked_effects"]
                ],
                ["file_open", "file_modify", "filesystem_scan"],
            )

            browser_adapter = json.loads(
                Path(cases["browser_research_collect_sources"]["adapter_artifact_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("static_dom", browser_adapter)
            self.assertIn("source_titles", browser_adapter["static_dom"])

            file_adapter = json.loads(
                Path(cases["files_search_find_candidate"]["adapter_artifact_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("temp_index", file_adapter)
            self.assertEqual(file_adapter["temp_index"]["candidate_count"], 2)

            word_adapter = json.loads(
                Path(cases["word_document_create_background"]["adapter_artifact_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("word_document", word_adapter)
            self.assertEqual(
                word_adapter["word_document"]["marker"],
                "OPENWUKONG_WORD_PRIMARY_SCENARIO",
            )
            self.assertTrue(word_adapter["word_document"]["owned_document_allowed"])
            self.assertFalse(word_adapter["word_document"]["user_document_allowed"])

            codex_adapter = json.loads(
                Path(cases["codex_project_submit_task_draft"]["adapter_artifact_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("draft_queue", codex_adapter)
            self.assertEqual(codex_adapter["draft_queue"]["queued_count"], 1)

    def test_owned_browser_helper_launch_is_explicit_opt_in_and_manifest_stopped(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )

        with tempfile.TemporaryDirectory() as tmp:
            launcher = _FakeReadinessLauncher()
            terminator = _FakeReadinessTerminator()
            readiness_calls: list[str] = []
            action_calls: list[dict] = []

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

            report = run_primary_scenario_smoke(
                fixture,
                output_root=tmp,
                allow_owned_browser_helper_launch=True,
                owned_browser_helper_launcher=launcher,
                owned_browser_helper_terminator=terminator,
                owned_browser_helper_readiness_probe=_fake_readiness_probe,
                owned_browser_helper_action_runner=_fake_browser_action_runner,
                owned_browser_debug_port=9341,
                owned_browser_executable="chrome.exe",
                owned_browser_url="about:blank#openwukong-primary-smoke",
            )
            data = report.to_dict()
            output_root = Path(tmp).resolve()

            cases = {case["case_id"]: case for case in data["cases"]}
            browser_case = cases["browser_research_collect_sources"]
            helper_path = Path(browser_case["owned_browser_helper_artifact_path"]).resolve()
            self.assertEqual(
                browser_case["owned_browser_helper_id"],
                "browser-owned-helper-readiness-launch",
            )
            self.assertTrue(str(helper_path).startswith(str(output_root)))
            self.assertTrue(helper_path.is_file())

            helper = json.loads(helper_path.read_text(encoding="utf-8"))
            self.assertEqual(helper["mode"], "primary-scenario-owned-browser-helper")
            self.assertEqual(
                helper["safety_mode"],
                "isolated_owned_browser_helper_opt_in",
            )
            self.assertEqual(helper["status"], "started_and_stopped")
            self.assertTrue(helper["launch_allowed"])
            self.assertFalse(helper["desktop_control_allowed"])
            self.assertEqual(helper["desktop_control_attempts"], 0)
            self.assertEqual(helper["window_input_attempts"], 0)
            self.assertFalse(helper["real_user_profile_allowed"])
            self.assertEqual(helper["readiness_plan"]["action_count"], 1)
            self.assertEqual(helper["readiness_execution"]["launch_attempts"], 1)
            self.assertTrue(helper["readiness_probe"]["ok"])
            self.assertEqual(helper["readiness_probe"]["target_count"], 1)
            self.assertTrue(helper["readiness_probe"]["target_match_ok"])
            self.assertEqual(
                helper["readiness_probe"]["expected_url"],
                "about:blank#openwukong-primary-smoke",
            )
            self.assertEqual(readiness_calls, ["http://127.0.0.1:9341"])
            self.assertEqual(helper["readiness_stop"]["stop_attempts"], 1)
            profile_path = Path(helper["profile_path"]).resolve()
            self.assertFalse(profile_path.exists())
            self.assertTrue(helper["profile_cleanup"]["attempted"])
            self.assertTrue(helper["profile_cleanup"]["deleted"])
            self.assertEqual(helper["profile_cleanup"]["error"], "")
            self.assertEqual(helper["owned_browser_action_id"], "browser-owned-helper-read-page")
            self.assertEqual(helper["owned_browser_action_control_attempts"], 0)
            self.assertEqual(helper["owned_browser_action"]["decision"], "executed")
            self.assertTrue(helper["owned_browser_action"]["ok"])
            self.assertEqual(
                helper["owned_browser_action"]["selected_route"],
                "browser-devtools-or-extension",
            )
            self.assertEqual(
                helper["owned_browser_action"]["action_report"]["action"],
                "read_page",
            )
            self.assertEqual(
                helper["owned_browser_action"]["action_report"]["action_result"]["title"],
                "OpenWukong Primary Smoke",
            )
            self.assertEqual(len(action_calls), 1)
            self.assertEqual(action_calls[0]["debugger_url"], "http://127.0.0.1:9341")
            self.assertEqual(action_calls[0]["action"], "read_page")
            self.assertEqual(
                action_calls[0]["resource_url"],
                "about:blank#openwukong-primary-smoke",
            )
            self.assertTrue(helper["isolation"]["live_connector_call_allowed"])
            self.assertTrue(Path(helper["manifest_path"]).resolve().is_file())
            self.assertTrue(
                str(Path(helper["manifest_path"]).resolve()).startswith(str(output_root))
            )
            self.assertEqual(launcher.tree_pids if hasattr(launcher, "tree_pids") else [], [])
            self.assertEqual(terminator.tree_pids, [424242])
            self.assertEqual(len(launcher.calls), 1)

            argv = launcher.calls[0]["argv"]
            self.assertIn("--remote-debugging-port=9341", argv)
            user_data_args = [
                value for value in argv if value.startswith("--user-data-dir=")
            ]
            self.assertEqual(len(user_data_args), 1)
            user_data_dir = Path(user_data_args[0].split("=", 1)[1])
            self.assertTrue(user_data_dir.is_absolute())
            self.assertTrue(str(user_data_dir).startswith(str(output_root)))
            self.assertFalse(user_data_dir.exists())
            self.assertEqual(terminator.owned_argv, [tuple(argv)])

            summary = summarize_report(report)
            self.assertEqual(summary["owned_browser_helper_artifact_count"], 1)
            scenarios = {item["scenario_id"]: item for item in summary["scenarios"]}
            self.assertEqual(
                scenarios["browser.research.collect_sources"]["owned_browser_helper_id"],
                "browser-owned-helper-readiness-launch",
            )
            self.assertTrue(
                scenarios["browser.research.collect_sources"][
                    "owned_browser_helper_written"
                ]
            )
            self.assertEqual(
                scenarios["codex.project.submit_task_draft"]["owned_browser_helper_id"],
                "",
            )

    def test_owned_browser_helper_creates_expected_target_after_new_tab_launch(self):
        execution_data = {
            "mode": "session-readiness-execution",
            "launch_attempts": 1,
            "results": [
                {
                    "status": "started",
                    "readiness_url": "http://127.0.0.1:9341",
                }
            ],
        }
        expected_url = "about:blank#openwukong-primary-smoke"
        probe_calls: list[str] = []
        opened_targets: list[tuple[str, str]] = []

        def _fake_readiness_probe(debugger_url: str) -> dict:
            probe_calls.append(debugger_url)
            if opened_targets:
                targets = [
                    {
                        "type": "page",
                        "title": "OpenWukong Primary Smoke",
                        "url": expected_url,
                    }
                ]
            else:
                targets = [
                    {
                        "type": "page",
                        "title": "New Tab",
                        "url": "chrome://newtab/",
                    }
                ]
            return {
                "mode": "browser-helper-readiness-probe",
                "ok": True,
                "debugger_url": debugger_url,
                "target_count": len(targets),
                "targets": targets,
                "error": "",
            }

        def _fake_open_target(debugger_url: str, target_url: str) -> dict:
            opened_targets.append((debugger_url, target_url))
            return {
                "ok": True,
                "method": "PUT",
                "url": f"{debugger_url}/json/new?about%3Ablank%23openwukong-primary-smoke",
                "status": 200,
                "target": {"url": target_url},
                "error": "",
            }

        with patch.object(
            primary_scenario_smoke,
            "_open_owned_browser_helper_target",
            side_effect=_fake_open_target,
        ):
            result = primary_scenario_smoke._run_owned_browser_helper_readiness_probe(
                execution_data=execution_data,
                readiness_probe=_fake_readiness_probe,
                expected_url=expected_url,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["target_match_ok"])
        self.assertEqual(result["matched_targets"][0]["url"], expected_url)
        self.assertTrue(result["target_open_attempted"])
        self.assertEqual(result["target_open_result"]["method"], "PUT")
        self.assertEqual(opened_targets, [("http://127.0.0.1:9341", expected_url)])
        self.assertEqual(
            probe_calls,
            ["http://127.0.0.1:9341", "http://127.0.0.1:9341"],
        )

    def test_smoke_cli_outputs_json_and_preserves_no_interference_counters(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")

        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([str(fixture_path), "--output-root", tmp, "--json"])

            data = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["passed_cases"], 5)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["desktop_scan_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["live_app_launch_attempts"], 0)
        self.assertEqual(data["real_filesystem_scan_attempts"], 0)

    def test_smoke_cli_summary_json_is_scheduler_friendly(self):
        fixture_path = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")

        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        str(fixture_path),
                        "--output-root",
                        tmp,
                        "--summary-json",
                    ]
                )

            data = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "primary-scenario-smoke-summary")
        self.assertEqual(data["suite"], "l1-primary-user-scenarios")
        self.assertEqual(data["passed_cases"], 5)
        self.assertEqual(data["failed_cases"], 0)
        self.assertEqual(data["safety_mode"], "isolated_no_focus")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["desktop_scan_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["live_app_launch_attempts"], 0)
        self.assertEqual(data["real_filesystem_scan_attempts"], 0)
        self.assertEqual(data["artifact_count"], 5)
        self.assertEqual(data["owned_session_dry_run_artifact_count"], 2)
        self.assertEqual(data["owned_session_execution_artifact_count"], 2)
        self.assertEqual(data["owned_browser_helper_artifact_count"], 0)
        self.assertNotIn("cases", data)
        scenarios = {item["scenario_id"]: item for item in data["scenarios"]}
        self.assertTrue(scenarios["wechat.chat.draft_reply"]["artifact_written"])
        self.assertEqual(
            scenarios["browser.research.collect_sources"]["adapter_id"],
            "browser-static-dom-bundle",
        )
        self.assertTrue(scenarios["browser.research.collect_sources"]["adapter_artifact_written"])
        self.assertEqual(
            scenarios["browser.research.collect_sources"]["owned_session_dry_run_id"],
            "browser-owned-session-dry-run",
        )
        self.assertTrue(scenarios["browser.research.collect_sources"]["owned_session_dry_run_written"])
        self.assertEqual(
            scenarios["browser.research.collect_sources"]["owned_session_execution_id"],
            "browser-owned-session-local-mock-devtools",
        )
        self.assertTrue(
            scenarios["browser.research.collect_sources"]["owned_session_execution_written"]
        )
        self.assertEqual(
            scenarios["browser.research.collect_sources"]["owned_browser_helper_id"],
            "",
        )
        self.assertFalse(
            scenarios["browser.research.collect_sources"]["owned_browser_helper_written"]
        )
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["owned_session_dry_run_id"],
            "codex-owned-session-dry-run",
        )
        self.assertTrue(scenarios["codex.project.submit_task_draft"]["owned_session_dry_run_written"])
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["owned_session_execution_id"],
            "codex-owned-session-local-mock-bridge",
        )
        self.assertTrue(
            scenarios["codex.project.submit_task_draft"]["owned_session_execution_written"]
        )
        self.assertEqual(
            scenarios["wechat.chat.draft_reply"]["owned_session_dry_run_id"],
            "",
        )
        self.assertEqual(
            scenarios["word.document.create_background"]["adapter_id"],
            "word-owned-docx-template",
        )
        self.assertEqual(
            scenarios["word.document.create_background"]["owned_session_dry_run_id"],
            "",
        )
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["blocked_primitive_count"],
            2,
        )
        self.assertEqual(
            scenarios["wechat.chat.draft_reply"]["blocked_effect_categories"],
            ["external_communication"],
        )
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["confirmation_required_effect_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
