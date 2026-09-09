import unittest

from openwukong.evaluation.codex_webview_bridge_strategy import (
    build_codex_webview_bridge_strategy,
)


class CodexWebviewBridgeStrategyTests(unittest.TestCase):
    def test_strategy_recommends_codex_side_shared_object_bridge(self):
        report = build_codex_webview_bridge_strategy(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            probe_report={
                "decision": "codex_extension_webview_bridge_required",
                "project_name": "openwukong",
                "prompt_send_ready": False,
                "requires_webview_bridge": True,
                "extension_exports_type": "undefined",
                "extension_export_keys": [],
                "webview_route_evidence": [
                    {
                        "path": "out/extension.js",
                        "markers": ["shared-object-set", "open-vscode-command"],
                    },
                    {
                        "path": "webview/assets/composer.js",
                        "markers": ["composer_prefill"],
                    },
                ],
            },
        ).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_webview_bridge_strategy_ready")
        self.assertEqual(report["recommended_strategy"], "codex_side_shared_object_bridge")
        self.assertFalse(report["public_prompt_command_ready"])
        self.assertFalse(report["public_extension_api_ready"])
        self.assertTrue(report["webview_route_verified"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        routes = {item["route_id"]: item for item in report["routes"]}
        self.assertEqual(routes["public_vscode_prompt_command"]["status"], "blocked")
        self.assertEqual(routes["public_extension_exports_api"]["status"], "blocked")
        self.assertEqual(routes["deep_link_prefill"]["status"], "blocked")
        self.assertEqual(routes["cross_extension_webview_post_message"]["status"], "blocked")
        self.assertEqual(routes["codex_side_shared_object_bridge"]["status"], "candidate")
        self.assertEqual(routes["foreground_keyboard_or_clipboard"]["status"], "rejected")
        required_steps = [item["step"] for item in report["required_contract"]]
        self.assertEqual(
            required_steps,
            ["codex_side_bridge", "prefill", "surface", "send", "readback"],
        )

    def test_strategy_prefers_public_prompt_command_if_available(self):
        report = build_codex_webview_bridge_strategy(
            "http://127.0.0.1:8787",
            probe_report={
                "prompt_send_ready": True,
                "extension_exports_type": "undefined",
                "extension_export_keys": [],
                "webview_route_evidence": [],
            },
        ).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_public_prompt_command_available")
        self.assertEqual(report["recommended_strategy"], "public_prompt_command")
        self.assertEqual(report["required_contract"], [])


if __name__ == "__main__":
    unittest.main()
