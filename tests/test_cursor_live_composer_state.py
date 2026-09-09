import unittest

from openwukong.evaluation.cursor_live_composer_state import (
    probe_cursor_live_composer_state,
    summarize_cursor_composer_handle,
)


class CursorLiveComposerStateTests(unittest.TestCase):
    def test_summarizes_nested_cursor_composer_handle_without_manager_blob(self):
        handle = {
            "composerId": "composer-1",
            "manager": {
                "loadedComposers": {
                    "store": {
                        "byId": {
                            "other": {
                                "composerId": "other",
                                "text": "wrong",
                            }
                        }
                    }
                },
                "data": {
                    "byId": {
                        "composer-1": {
                            "composerId": "composer-1",
                            "text": "draft text",
                            "richText": "<p>draft text</p>",
                            "status": "none",
                            "unifiedMode": "agent",
                            "forceMode": "edit",
                            "isAgentic": True,
                            "hasPendingPlan": False,
                            "hasBlockingPendingActions": False,
                            "conversationMap": {"bubble-1": {}, "bubble-2": {}},
                            "queueItems": [{}],
                            "todos": [{}, {}],
                            "conversationState": {
                                "rootPromptMessagesJson": ["prompt"],
                                "turns": [{}, {}, {}],
                            },
                        }
                    }
                },
                "largeInternalBlob": "x" * 1000,
            },
        }

        summary = summarize_cursor_composer_handle(handle, "composer-1")

        self.assertEqual(summary["composer_id"], "composer-1")
        self.assertTrue(summary["has_state"])
        self.assertEqual(summary["text"], "draft text")
        self.assertEqual(summary["status"], "none")
        self.assertEqual(summary["conversation_bubble_count"], 2)
        self.assertEqual(summary["queue_item_count"], 1)
        self.assertEqual(summary["todo_count"], 2)
        self.assertEqual(summary["turn_count"], 3)
        self.assertNotIn("manager", summary)
        self.assertNotIn("largeInternalBlob", str(summary))

    def test_summarizes_cursor_loaded_composers_store_path(self):
        handle = {
            "composerId": "composer-1",
            "manager": {
                "loadedComposers": {
                    "store": {
                        "byId": {
                            "composer-1": {
                                "composerId": "composer-1",
                                "text": "",
                                "status": "none",
                                "unifiedMode": "agent",
                                "forceMode": "edit",
                                "isAgentic": True,
                            }
                        }
                    },
                    "byId": {
                        "composer-1": {
                            "composerId": "composer-1",
                            "text": "fallback",
                            "status": "stale",
                        }
                    },
                }
            },
        }

        summary = summarize_cursor_composer_handle(handle, "composer-1")

        self.assertEqual(summary["status"], "none")
        self.assertEqual(summary["unified_mode"], "agent")
        self.assertEqual(summary["force_mode"], "edit")
        self.assertTrue(summary["is_agentic"])

    def test_fallback_probe_defaults_to_selected_ids_without_handle_read(self):
        client = _FakeCursorBridgeClient(
            {
                "composer.getOrderedSelectedComposerIds": {
                    "ok": True,
                    "result": ["composer-1"],
                },
                "composer.getComposerHandleById": {
                    "ok": True,
                    "result": {
                        "composerId": "composer-1",
                        "text": "",
                        "status": "none",
                        "conversationMap": {},
                    },
                },
            }
        )

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            bridge_client=client,
        ).to_dict()

        self.assertEqual(report["decision"], "cursor_live_composer_selected_ids_ready")
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])
        self.assertEqual(report["composer_ids"], ["composer-1"])
        self.assertEqual(report["readonly_command_attempts"], 1)
        self.assertEqual(report["bridge_send_attempts"], 0)
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["state_status"], "selected_only")
        self.assertFalse(report["include_handles"])
        self.assertFalse(report["handle_read_allowed"])
        self.assertEqual(report["handle_read_policy"], "isolated_cursor_read_probe_required")
        self.assertEqual(report["composers"], [])
        self.assertEqual(
            [call["command_id"] for call in client.calls],
            ["composer.getOrderedSelectedComposerIds"],
        )

    def test_fallback_probe_reads_handles_only_with_isolated_safety_profile(self):
        client = _FakeCursorBridgeClient(
            {
                "composer.getOrderedSelectedComposerIds": {
                    "ok": True,
                    "result": ["composer-1"],
                },
                "composer.getComposerHandleById": {
                    "ok": True,
                    "result": {
                        "composerId": "composer-1",
                        "text": "",
                        "status": "none",
                        "conversationMap": {},
                    },
                },
            }
        )

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            bridge_client=client,
            include_handles=True,
            safety_profile="isolated_cursor_read_probe",
        ).to_dict()

        self.assertEqual(report["decision"], "cursor_live_composer_state_ready")
        self.assertEqual(report["readonly_command_attempts"], 2)
        self.assertEqual(report["composers"][0]["status"], "none")
        self.assertTrue(report["include_handles"])
        self.assertEqual(
            [call["command_id"] for call in client.calls],
            ["composer.getOrderedSelectedComposerIds", "composer.getComposerHandleById"],
        )
        self.assertEqual(
            client.calls[1]["safety_profile"],
            "isolated_cursor_read_probe",
        )

    def test_probe_prefers_semantic_composer_state_endpoint_when_available(self):
        client = _SemanticCursorBridgeClient()

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            composer_ids=("composer-1",),
            bridge_client=client,
        ).to_dict()

        self.assertEqual(report["decision"], "cursor_live_composer_state_ready")
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])
        self.assertEqual(report["composer_ids"], ["composer-1"])
        self.assertEqual(report["readonly_command_attempts"], 1)
        self.assertFalse(report["include_handles"])
        self.assertEqual(report["composers"][0]["text"], "semantic draft")
        self.assertEqual(client.calls[0]["composer_ids"], ["composer-1"])
        self.assertFalse(client.calls[0]["include_handles"])
        self.assertFalse(hasattr(client, "execute_command_calls"))

    def test_probe_accepts_selected_only_state_without_handle_read(self):
        client = _SelectedOnlySemanticCursorBridgeClient()

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            bridge_client=client,
        ).to_dict()

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "cursor_live_composer_selected_ids_ready")
        self.assertEqual(report["state_status"], "selected_only")
        self.assertEqual(report["selected_composer_ids"], ["composer-1"])
        self.assertEqual(report["composer_ids"], ["composer-1"])
        self.assertFalse(report["include_handles"])
        self.assertFalse(report["handle_read_allowed"])
        self.assertEqual(report["handle_read_policy"], "isolated_cursor_read_probe_required")
        self.assertEqual(report["composers"], [])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)

    def test_probe_preserves_semantic_pending_state_without_treating_bridge_as_dead(self):
        client = _PendingSemanticCursorBridgeClient()

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            bridge_client=client,
        ).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "cursor_live_composer_state_pending")
        self.assertEqual(report["state_status"], "pending")
        self.assertEqual(
            report["pending_commands"][0]["command_id"],
            "composer.getComposerHandleById",
        )
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        self.assertEqual(report["bridge_send_attempts"], 0)

    def test_probe_can_include_extra_composer_ids(self):
        client = _FakeCursorBridgeClient(
            {
                "composer.getOrderedSelectedComposerIds": {
                    "ok": True,
                    "result": ["workspace-composer"],
                },
                "composer.getComposerHandleById": {
                    "ok": True,
                    "result": {
                        "composerId": "live-composer",
                        "text": "live draft",
                        "status": "none",
                    },
                },
            }
        )

        report = probe_cursor_live_composer_state(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            composer_ids=("live-composer",),
            bridge_client=client,
            include_handles=True,
            safety_profile="isolated_cursor_read_probe",
        ).to_dict()

        self.assertEqual(report["composer_ids"], ["workspace-composer", "live-composer"])
        self.assertEqual(len(report["composers"]), 2)


class _FakeCursorBridgeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute_command(self, bridge_url, target, command_id, arguments, safety_profile=""):
        self.calls.append(
            {
                "bridge_url": bridge_url,
                "workspace_path": target.workspace_path,
                "command_id": command_id,
                "arguments": list(arguments),
                "safety_profile": safety_profile,
            }
        )
        if command_id == "composer.getComposerHandleById" and arguments:
            response = dict(self.responses[command_id])
            result = dict(response["result"])
            result["composerId"] = arguments[0]
            response["result"] = result
            return response
        return dict(self.responses[command_id])


class _SemanticCursorBridgeClient:
    def __init__(self):
        self.calls = []

    def cursor_composer_state(
        self,
        bridge_url,
        target,
        *,
        composer_ids=None,
        max_composers=8,
        include_handles=False,
        safety_profile="",
    ):
        self.calls.append(
            {
                "bridge_url": bridge_url,
                "workspace_path": target.workspace_path,
                "composer_ids": list(composer_ids or []),
                "max_composers": max_composers,
                "include_handles": include_handles,
                "safety_profile": safety_profile,
            }
        )
        return {
            "ok": True,
            "state_status": "ready",
            "selected_composer_ids": ["composer-1"],
            "composer_ids": ["composer-1"],
            "composers": [
                {
                    "composer_id": "composer-1",
                    "text": "semantic draft",
                    "rich_text": "semantic draft",
                }
            ],
        }


class _SelectedOnlySemanticCursorBridgeClient:
    def cursor_composer_state(
        self,
        bridge_url,
        target,
        *,
        composer_ids=None,
        max_composers=8,
        include_handles=False,
        safety_profile="",
    ):
        return {
            "ok": True,
            "state_status": "selected_only",
            "selected_composer_ids": ["composer-1"],
            "composer_ids": ["composer-1"],
            "composers": [],
            "include_handles": include_handles,
            "handle_read_allowed": False,
            "handle_read_policy": "isolated_cursor_read_probe_required",
        }


class _PendingSemanticCursorBridgeClient:
    def cursor_composer_state(
        self,
        bridge_url,
        target,
        *,
        composer_ids=None,
        max_composers=8,
        include_handles=False,
        safety_profile="",
    ):
        return {
            "ok": True,
            "state_status": "pending",
            "selected_composer_ids": ["composer-1"],
            "composer_ids": ["composer-1"],
            "composers": [],
            "pending_commands": [
                {
                    "command_id": "composer.getComposerHandleById",
                    "composer_id": "composer-1",
                    "timeout_ms": 2500,
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
