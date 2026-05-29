import unittest

from openwukong.control.agent_app_transport_matrix import (
    build_agent_app_transport_matrix,
)


class AgentAppTransportMatrixTests(unittest.TestCase):
    def test_browser_level_devtools_is_read_only_not_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "cursor",
                "agent_id": "cursor",
                "project_name": "openwukong",
                "task_name": "cursor-chat",
                "ready_endpoint_count": 0,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:19557",
                        "ready": False,
                        "target_count": 0,
                        "version": {
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1"
                        },
                        "targets": [],
                        "error": "devtools_targets_not_ready",
                    }
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 0,
                    "submit_candidate_count": 0,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertFalse(matrix["draft_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "app-devtools-browser-target")
        self.assertTrue(candidate["ready"])
        self.assertEqual(candidate["capability_level"], "background-read-only")
        self.assertEqual(candidate["operation_scope"], "discovery-only")
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "page_target_missing")
        self.assertEqual(matrix["summary"]["background_read_only"], 1)
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)

    def test_agent_native_bridge_is_selected_before_page_target_and_uia(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "claude desktop",
                "agent_id": "claude",
                "project_name": "openwukong",
                "task_name": "claude-task",
                "ready_endpoint_count": 2,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:9333",
                        "ready": True,
                        "target_count": 1,
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "title": "Claude",
                                "url": "app://claude",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/page-1",
                                "ready": True,
                            }
                        ],
                    },
                    {
                        "endpoint_type": "agent_native_bridge",
                        "bridge_url": "http://127.0.0.1:18888",
                        "ready": True,
                        "preferred_chat_adapter": "claude",
                        "send_command_id": "agent_app_conversation.native_bridge_send_message",
                        "metadata": {"surface_ok": True, "app_binding_ok": True},
                    },
                ],
                "app_uia_probe": {
                    "target_matched": True,
                    "semantic_composer_count": 1,
                    "submit_candidate_count": 1,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertTrue(matrix["send_ready"])
        self.assertTrue(matrix["draft_ready"])
        self.assertEqual(
            matrix["selected_send_transport"]["transport_id"],
            "agent-native-bridge",
        )
        self.assertEqual(
            matrix["selected_send_transport"]["transport_channel"],
            "agent_native_bridge",
        )
        self.assertTrue(
            _candidate(matrix, "app-devtools-page-target")["can_send_without_focus"]
        )
        self.assertTrue(
            _candidate(matrix, "uia-semantic-draft")["can_draft_without_focus"]
        )

    def test_page_target_cdp_without_verified_target_context_is_not_send_ready(self):
        matrix = build_agent_app_transport_matrix(
            {
                "agent": "cursor",
                "agent_id": "cursor",
                "project_name": "openwukong",
                "task_name": "major-real-no-loss",
                "ready_endpoint_count": 1,
                "endpoints": [
                    {
                        "endpoint_type": "devtools",
                        "debugger_url": "http://127.0.0.1:19557",
                        "ready": True,
                        "target_count": 1,
                        "version": {
                            "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/browser/browser-1"
                        },
                        "targets": [
                            {
                                "target_id": "page-1",
                                "type": "page",
                                "title": "Cursor",
                                "url": "app://cursor/workbench.html",
                                "webSocketDebuggerUrl": "ws://127.0.0.1:19557/devtools/page/page-1",
                                "ready": True,
                            }
                        ],
                    }
                ],
                "app_uia_probe": {
                    "target_matched": False,
                    "semantic_composer_count": 4,
                    "submit_candidate_count": 4,
                    "background_screenshot_focus_stable": True,
                },
            }
        ).to_dict()

        self.assertFalse(matrix["send_ready"])
        self.assertEqual(matrix["selected_send_transport"], {})
        candidate = _candidate(matrix, "app-devtools-page-target")
        self.assertTrue(candidate["ready"])
        self.assertFalse(candidate["can_send_without_focus"])
        self.assertEqual(candidate["blocking_reason"], "target_context_not_verified")
        self.assertEqual(matrix["summary"]["background_send_ready"], 0)


def _candidate(matrix, transport_id):
    for item in matrix["candidates"]:
        if item["transport_id"] == transport_id:
            return item
    raise AssertionError(f"missing candidate {transport_id}: {matrix['candidates']}")


if __name__ == "__main__":
    unittest.main()
