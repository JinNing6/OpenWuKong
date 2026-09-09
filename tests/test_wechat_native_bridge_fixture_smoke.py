import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.wechat_native_bridge_fixture_smoke import (
    main,
    run_wechat_native_bridge_fixture_smoke,
)


class WeChatNativeBridgeFixtureSmokeTests(unittest.TestCase):
    def test_fixture_smoke_uses_registry_discovery_without_window_input(self):
        report = run_wechat_native_bridge_fixture_smoke(
            message="OPENWUKONG_WECHAT_FIXTURE: PASS",
            required_markers=("OPENWUKONG_WECHAT_FIXTURE: PASS",),
            forbidden_markers=("OPENWUKONG_WECHAT_FIXTURE: FAIL",),
        )
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(
            data["decision"],
            "wechat_native_bridge_fixture_smoke_verified",
        )
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["window_input_attempts"], 0)
        self.assertEqual(data["native_call_attempts"], 1)
        self.assertEqual(data["send_attempts"], 1)
        self.assertEqual(
            data["send_report"]["decision"],
            "wechat_native_bridge_send_accepted",
        )
        self.assertEqual(data["send_report"]["window_input_attempts"], 0)
        self.assertEqual(data["send_report"]["keyboard_input_attempts"], 0)
        self.assertEqual(data["send_report"]["clipboard_write_attempts"], 0)
        self.assertEqual(data["send_report"]["missing_required_markers"], [])
        self.assertEqual(data["send_report"]["present_forbidden_markers"], [])
        self.assertEqual(data["fixture"]["capability_request_count"], 1)
        self.assertEqual(data["fixture"]["send_request_count"], 1)
        self.assertEqual(
            data["fixture"]["send_requests"][0]["message"],
            "OPENWUKONG_WECHAT_FIXTURE: PASS",
        )
        self.assertTrue(data["registry"]["registered"])
        self.assertEqual(data["registry"]["discovered_urls"], [data["bridge_url"]])

    def test_main_writes_fixture_smoke_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "wechat-native-bridge-fixture.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--message",
                        "OPENWUKONG_WECHAT_FIXTURE: PASS",
                        "--acceptance-marker",
                        "OPENWUKONG_WECHAT_FIXTURE: PASS",
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["control_attempts"], 0)
        self.assertEqual(payload["window_input_attempts"], 0)
        self.assertEqual(payload["send_report"]["native_call_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
