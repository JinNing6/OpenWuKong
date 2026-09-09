import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.agent_native_bridge_fixture_smoke import (
    main,
    run_agent_native_bridge_fixture_smoke,
)


class AgentNativeBridgeFixtureSmokeTests(unittest.TestCase):
    def test_fixture_smoke_uses_real_http_bridge_and_verifies_readback(self):
        report = run_agent_native_bridge_fixture_smoke(
            message="Use the native bridge fixture.",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_native_bridge_fixture_smoke_verified")
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["send_report"]["decision"], "agent_native_bridge_send_accepted")
        self.assertEqual(
            data["send_report"]["dry_run_report"]["decision"],
            "agent_native_bridge_dry_run_ready",
        )
        self.assertTrue(
            data["send_report"]["dry_run_report"]["readback_action_ready"]
        )
        self.assertEqual(
            data["fixture"]["request_paths"],
            ["/v1/agent/capabilities", "/v1/agent/chat"],
        )
        self.assertIn(
            "Use the native bridge fixture.",
            data["fixture"]["chat_payloads"][0]["message"],
        )

    def test_fixture_smoke_fails_without_readback_capability_and_does_not_send(self):
        report = run_agent_native_bridge_fixture_smoke(
            message="Use the native bridge fixture.",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
            advertise_readback=False,
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "agent_native_bridge_fixture_smoke_failed")
        self.assertEqual(data["native_call_attempts"], 0)
        self.assertEqual(
            data["send_report"]["decision"],
            "agent_native_bridge_request_not_ready",
        )
        self.assertEqual(
            data["send_report"]["dry_run_report"]["decision"],
            "agent_native_bridge_readback_not_ready",
        )
        self.assertEqual(data["fixture"]["request_paths"], ["/v1/agent/capabilities"])

    def test_main_writes_fixture_smoke_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "agent-native-bridge-fixture.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--message",
                        "Use the native bridge fixture.",
                        "--acceptance-marker",
                        "OPENWUKONG_ACCEPTANCE: PASS",
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["window_input_attempts"], 0)
        self.assertEqual(payload["fixture"]["request_paths"][1], "/v1/agent/chat")


if __name__ == "__main__":
    unittest.main()
