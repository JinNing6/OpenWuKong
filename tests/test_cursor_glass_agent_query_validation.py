import unittest

from openwukong.evaluation.cursor_glass_agent_query_validation import (
    validate_cursor_glass_agent_query,
)


class CursorGlassAgentQueryValidationTests(unittest.TestCase):
    def test_dry_run_validation_does_not_send_or_readback(self):
        client = _GlassAgentQueryClient()
        report = validate_cursor_glass_agent_query(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_DRY_RUN",
            allow_write=False,
            bridge_client=client,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 100, "title": "Codex"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "cursor-glass-agent-query-validation")
        self.assertEqual(data["decision"], "cursor_glass_agent_query_dry_run_ready")
        self.assertTrue(data["ok"])
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_send_attempts"], 0)
        self.assertEqual(data["agent_request_attempts"], 0)
        self.assertFalse(data["assistant_response_verified"])
        self.assertEqual(client.calls[0]["allow_write"], False)

    def test_live_query_requires_assistant_side_readback_for_success(self):
        seen_roles = []

        def cursor_transcript_readback_runner(**kwargs):
            seen_roles.append(kwargs["required_response_role"])
            self.assertEqual(kwargs["required_markers"], ("OPENWUKONG_GLASS_ASSISTANT",))
            if kwargs["required_response_role"] == "user":
                return {
                    "decision": "cursor_transcript_readback_accepted",
                    "ok": True,
                    "required_response_role": "user",
                    "required_markers_found": ["OPENWUKONG_GLASS_ASSISTANT"],
                    "missing_required_markers": [],
                }
            return {
                "decision": "cursor_transcript_readback_accepted",
                "ok": True,
                "required_response_role": "assistant",
                "required_markers_found": ["OPENWUKONG_GLASS_ASSISTANT"],
                "missing_required_markers": [],
            }

        report = validate_cursor_glass_agent_query(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="reply with OPENWUKONG_GLASS_ASSISTANT",
            required_markers=("OPENWUKONG_GLASS_ASSISTANT",),
            allow_write=True,
            safety_profile="live_cursor_glass_agent_query_probe",
            bridge_client=_GlassAgentQueryClient(),
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 100, "title": "Codex"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_glass_agent_query_assistant_validated")
        self.assertTrue(data["ok"])
        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["bridge_send_attempts"], 1)
        self.assertTrue(data["user_prompt_verified"])
        self.assertTrue(data["assistant_response_verified"])
        self.assertEqual(seen_roles, ["user", "assistant"])

    def test_user_marker_only_is_not_full_agent_completion(self):
        def cursor_transcript_readback_runner(**kwargs):
            if kwargs["required_response_role"] == "user":
                return {
                    "decision": "cursor_transcript_readback_accepted",
                    "ok": True,
                    "required_response_role": "user",
                    "required_markers_found": ["OPENWUKONG_GLASS_USER_ONLY"],
                    "missing_required_markers": [],
                }
            return {
                "decision": "cursor_transcript_readback_non_response_marker_only",
                "ok": False,
                "required_response_role": "assistant",
                "required_markers_found": [],
                "required_markers_found_anywhere": ["OPENWUKONG_GLASS_USER_ONLY"],
                "missing_required_markers": ["OPENWUKONG_GLASS_USER_ONLY"],
            }

        report = validate_cursor_glass_agent_query(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_USER_ONLY",
            allow_write=True,
            safety_profile="live_cursor_glass_agent_query_probe",
            bridge_client=_GlassAgentQueryClient(),
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 100, "title": "Codex"},
            ]),
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_glass_agent_query_user_marker_only")
        self.assertFalse(data["ok"])
        self.assertTrue(data["user_prompt_verified"])
        self.assertFalse(data["assistant_response_verified"])
        self.assertEqual(data["error"], "cursor_glass_agent_query_user_marker_only")

    def test_foreground_change_rejects_even_if_assistant_readback_succeeds(self):
        def cursor_transcript_readback_runner(**kwargs):
            return {
                "decision": "cursor_transcript_readback_accepted",
                "ok": True,
                "required_response_role": kwargs["required_response_role"],
                "required_markers_found": ["OPENWUKONG_GLASS_FOCUS"],
                "missing_required_markers": [],
            }

        report = validate_cursor_glass_agent_query(
            "http://127.0.0.1:8799",
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_GLASS_FOCUS",
            allow_write=True,
            safety_profile="live_cursor_glass_agent_query_probe",
            bridge_client=_GlassAgentQueryClient(),
            cursor_transcript_readback_runner=cursor_transcript_readback_runner,
            focus_observer=_FocusSequence([
                {"hwnd": 100, "title": "Codex"},
                {"hwnd": 200, "title": "Cursor"},
                {"hwnd": 200, "title": "Cursor"},
            ]),
            post_action_observation_delay_sec=0.001,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_glass_agent_query_failed_foreground_changed")
        self.assertFalse(data["ok"])
        self.assertTrue(data["foreground_changed"])
        self.assertFalse(data["assistant_response_verified"])


class _GlassAgentQueryClient:
    def __init__(self):
        self.calls = []

    def cursor_glass_agent_query(
        self,
        bridge_url,
        target,
        *,
        message,
        allow_write=False,
        safety_profile="",
    ):
        del bridge_url, target
        self.calls.append(
            {
                "message": message,
                "allow_write": allow_write,
                "safety_profile": safety_profile,
            }
        )
        return {
            "ok": True,
            "decision": "cursor_glass_agent_query_dispatched"
            if allow_write
            else "cursor_glass_agent_query_ready",
            "dry_run": not allow_write,
            "command_id": "glass.newAgentWithQuery",
            "dispatch_status": "resolved" if allow_write else "",
        }


class _FocusSequence:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def capture(self):
        if self.index >= len(self.snapshots):
            return dict(self.snapshots[-1])
        value = dict(self.snapshots[self.index])
        self.index += 1
        return value


if __name__ == "__main__":
    unittest.main()
