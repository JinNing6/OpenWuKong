import json
import unittest
from pathlib import Path
from unittest import mock

from openwukong.evaluation.simulation import (
    L1SimulationHarness,
    load_simulation_fixture,
    main,
)


class L1PrimaryUserScenariosTests(unittest.TestCase):
    def test_primary_user_scenario_fixture_generates_simulation_only_plans(self):
        fixture = load_simulation_fixture(
            Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        )

        report = L1SimulationHarness().run_suite(fixture)
        data = report.to_dict()
        plans = {
            result["case_id"]: result["primary_scenario_plan"]
            for result in data["results"]
        }

        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.failed_cases, 0)
        self.assertEqual(
            set(plans),
            {
                "wechat_chat_draft_reply",
                "browser_research_collect_sources",
                "files_search_find_candidate",
                "word_document_create_background",
                "codex_project_submit_task_draft",
            },
        )
        for plan in plans.values():
            self.assertEqual(plan["mode"], "primary-scenario-plan")
            self.assertEqual(plan["safety_mode"], "simulation_only")
            self.assertFalse(plan["control_allowed"])
            self.assertEqual(plan["control_attempts"], 0)
            self.assertTrue(plan["draft_action"])

        self.assertEqual(
            plans["wechat_chat_draft_reply"]["route_id"],
            "uia-semantic-chat-draft",
        )
        self.assertEqual(
            plans["wechat_chat_draft_reply"]["proposed_action"],
            "draft_chat_message",
        )
        self.assertTrue(plans["wechat_chat_draft_reply"]["requires_confirmation"])
        self.assertIn("send_message", plans["wechat_chat_draft_reply"]["blocked_primitives"])
        wechat_policy = plans["wechat_chat_draft_reply"]["side_effect_policy"]
        self.assertEqual(wechat_policy["mode"], "primary-scenario-side-effect-policy")
        self.assertEqual(wechat_policy["taxonomy_version"], "primary-side-effects-v1")
        self.assertEqual(
            wechat_policy["blocked_categories"],
            ["external_communication"],
        )
        self.assertIn(
            "external_communication.send_message",
            [effect["effect_id"] for effect in wechat_policy["confirmation_required_effects"]],
        )

        self.assertEqual(
            plans["browser_research_collect_sources"]["route_id"],
            "browser-devtools-or-extension",
        )
        self.assertEqual(
            plans["browser_research_collect_sources"]["proposed_action"],
            "draft_browser_research_plan",
        )
        self.assertIn("cdp.dom_snapshot", plans["browser_research_collect_sources"]["evidence_ids"])
        self.assertEqual(
            plans["browser_research_collect_sources"]["side_effect_policy"]["blocked_categories"],
            ["browser_navigation", "browser_form_submit"],
        )

        self.assertEqual(
            plans["files_search_find_candidate"]["route_id"],
            "windows-search-index",
        )
        self.assertEqual(
            plans["files_search_find_candidate"]["proposed_action"],
            "rank_file_candidates",
        )
        self.assertIn("windows_search.index_snapshot", plans["files_search_find_candidate"]["evidence_ids"])
        self.assertEqual(
            plans["files_search_find_candidate"]["side_effect_policy"]["blocked_categories"],
            ["file_open", "file_modify", "filesystem_scan"],
        )

        self.assertEqual(
            plans["word_document_create_background"]["route_id"],
            "office-word-com",
        )
        self.assertEqual(
            plans["word_document_create_background"]["connector_id"],
            "office-word",
        )
        self.assertEqual(
            plans["word_document_create_background"]["proposed_action"],
            "create_owned_word_document",
        )
        self.assertFalse(plans["word_document_create_background"]["requires_confirmation"])
        self.assertIn(
            "office_com_create_document",
            plans["word_document_create_background"]["allowed_primitives"],
        )
        self.assertIn(
            "modify_user_document",
            plans["word_document_create_background"]["blocked_primitives"],
        )
        self.assertEqual(
            plans["word_document_create_background"]["side_effect_policy"]["allowed_categories"],
            ["recorded_read", "local_draft", "office_document"],
        )
        self.assertEqual(
            plans["word_document_create_background"]["side_effect_policy"]["blocked_categories"],
            ["office_document"],
        )

        self.assertEqual(
            plans["codex_project_submit_task_draft"]["route_id"],
            "codex-task-draft",
        )
        self.assertEqual(
            plans["codex_project_submit_task_draft"]["proposed_action"],
            "draft_codex_project_task",
        )
        self.assertTrue(plans["codex_project_submit_task_draft"]["requires_confirmation"])
        self.assertIn("submit_task", plans["codex_project_submit_task_draft"]["blocked_primitives"])
        self.assertEqual(
            plans["codex_project_submit_task_draft"]["side_effect_policy"]["blocked_categories"],
            ["agent_task_submission", "agent_start"],
        )
        self.assertEqual(
            [
                effect["category"]
                for effect in plans["codex_project_submit_task_draft"]["side_effect_policy"][
                    "confirmation_required_effects"
                ]
            ],
            ["agent_task_submission", "agent_start"],
        )

    def test_primary_user_scenario_cli_json_report_contains_plans(self):
        stdout_path = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        with mock.patch("sys.stdout") as stdout:
            exit_code = main([str(stdout_path), "--json"])

        payload = "".join(call.args[0] for call in stdout.write.call_args_list)
        data = json.loads(payload)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["passed_cases"], 5)
        self.assertEqual(
            data["results"][0]["primary_scenario_plan"]["safety_mode"],
            "simulation_only",
        )

    def test_primary_user_scenario_cli_summary_json_is_scheduler_friendly(self):
        stdout_path = Path("tests/fixtures/evaluation/l1_primary_user_scenarios.json")
        with mock.patch("sys.stdout") as stdout:
            exit_code = main([str(stdout_path), "--summary-json"])

        payload = "".join(call.args[0] for call in stdout.write.call_args_list)
        data = json.loads(payload)

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["mode"], "l1-simulation-summary")
        self.assertEqual(data["suite"], "l1-primary-user-scenarios")
        self.assertEqual(data["passed_cases"], 5)
        self.assertEqual(data["failed_cases"], 0)
        self.assertEqual(data["safety_mode"], "simulation_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["scenario_count"], 5)
        self.assertNotIn("results", data)
        scenarios = {item["scenario_id"]: item for item in data["scenarios"]}
        self.assertEqual(
            scenarios["wechat.chat.draft_reply"]["proposed_action"],
            "draft_chat_message",
        )
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["blocked_primitive_count"],
            2,
        )
        self.assertEqual(
            scenarios["browser.research.collect_sources"]["blocked_effect_categories"],
            ["browser_navigation", "browser_form_submit"],
        )
        self.assertEqual(
            scenarios["word.document.create_background"]["proposed_action"],
            "create_owned_word_document",
        )
        self.assertEqual(
            scenarios["word.document.create_background"]["blocked_effect_categories"],
            ["office_document"],
        )
        self.assertEqual(
            scenarios["codex.project.submit_task_draft"]["confirmation_required_effect_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
