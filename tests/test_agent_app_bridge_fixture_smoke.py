import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.agent_app_bridge_fixture_smoke import (
    main,
    run_agent_app_bridge_fixture_smoke,
)


class AgentAppBridgeFixtureSmokeTests(unittest.TestCase):
    def test_fixture_smoke_uses_real_devtools_websocket_without_window_input(self):
        report = run_agent_app_bridge_fixture_smoke(
            message="Use the app bridge fixture.",
            required_markers=("OPENWUKONG_ACCEPTANCE: PASS",),
        )
        data = report.to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "agent_app_bridge_fixture_smoke_verified")
        self.assertEqual(data["desktop_control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["bridge_send_report"]["decision"], "app_bridge_send_accepted")
        self.assertEqual(data["bridge_send_report"]["native_call_attempts"], 1)
        self.assertEqual(data["bridge_send_report"]["native_probe_attempts"], 1)
        self.assertEqual(data["bridge_send_report"]["composer_probe_report"]["decision"], "app_bridge_composer_ready")
        self.assertEqual(data["fixture"]["cdp_request_count"], 2)
        self.assertEqual(data["fixture"]["cdp_requests"][0]["method"], "Runtime.evaluate")
        self.assertEqual(data["fixture"]["cdp_requests"][1]["method"], "Runtime.evaluate")
        self.assertIn("composerSelectors", data["fixture"]["cdp_requests"][0]["params"]["expression"])
        self.assertIn("Use the app bridge fixture.", data["fixture"]["cdp_requests"][1]["params"]["expression"])

    def test_main_writes_fixture_smoke_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "agent-app-bridge-fixture.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--message",
                        "Use the app bridge fixture.",
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
        self.assertEqual(payload["bridge_send_report"]["window_input_attempts"], 0)
        self.assertEqual(payload["fixture"]["cdp_request_count"], 2)


if __name__ == "__main__":
    unittest.main()
