import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openwukong.evaluation.wechat_openclaw_readiness import CommandResult
from openwukong.evaluation.wechat_openclaw_setup_gate import (
    main,
    run_wechat_openclaw_setup_gate,
)


class WeChatOpenClawSetupGateTests(unittest.TestCase):
    def test_node_runtime_too_old_blocks_without_executing_setup(self):
        report = run_wechat_openclaw_setup_gate(
            readiness_report=_readiness(
                decision="openclaw_cli_node_runtime_too_old",
                node_version="22.17.1",
                plugin_present=False,
                plugin_enabled=False,
                account_count=0,
                target_ready=False,
            )
        )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "openclaw_weixin_setup_blocked_node_runtime")
        self.assertIn("node_runtime_too_old", _blocker_ids(data))
        self.assertIn("install_compatible_node_runtime", _step_ids(data))
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["install_attempts"], 0)
        self.assertEqual(data["login_attempts"], 0)
        self.assertFalse(data["desktop_wechat_control_verified"])
        self.assertTrue(all(not step["executed"] for step in data["setup_steps"]))

    def test_plugin_missing_adds_install_and_enable_steps(self):
        data = run_wechat_openclaw_setup_gate(
            readiness_report=_readiness(
                plugin_present=False,
                plugin_enabled=False,
                account_count=0,
                target_ready=False,
            )
        ).to_dict()
        steps = {step["action_id"]: step for step in data["setup_steps"]}

        self.assertEqual(data["decision"], "openclaw_weixin_setup_blocked_plugin")
        self.assertIn("openclaw_weixin_plugin_not_configured", _blocker_ids(data))
        self.assertEqual(
            steps["install_openclaw_weixin_plugin"]["command_argv"],
            ["openclaw", "plugins", "install", "@tencent-weixin/openclaw-weixin"],
        )
        self.assertTrue(steps["install_openclaw_weixin_plugin"]["mutates_environment"])
        self.assertEqual(
            steps["enable_openclaw_weixin_plugin"]["command_argv"],
            ["openclaw", "config", "set", "plugins.entries.openclaw-weixin.enabled", "true"],
        )
        self.assertEqual(data["send_attempts"], 0)

    def test_logged_out_account_requires_qr_login_step(self):
        data = run_wechat_openclaw_setup_gate(
            readiness_report=_readiness(
                plugin_present=True,
                plugin_enabled=True,
                account_count=0,
                target_ready=False,
            )
        ).to_dict()
        steps = {step["action_id"]: step for step in data["setup_steps"]}

        self.assertEqual(data["decision"], "openclaw_weixin_setup_blocked_login")
        self.assertIn("openclaw_weixin_account_not_logged_in", _blocker_ids(data))
        self.assertEqual(
            steps["login_openclaw_weixin_account"]["command_argv"],
            ["openclaw", "channels", "login", "--channel", "openclaw-weixin"],
        )
        self.assertTrue(steps["login_openclaw_weixin_account"]["requires_user_action"])
        self.assertTrue(steps["login_openclaw_weixin_account"]["requires_terminal_interaction"])
        self.assertEqual(data["gateway_start_attempts"], 0)

    def test_account_ready_without_target_blocks_at_target_gate(self):
        data = run_wechat_openclaw_setup_gate(
            readiness_report=_readiness(
                plugin_present=True,
                plugin_enabled=True,
                account_count=1,
                target_ready=False,
            )
        ).to_dict()
        steps = {step["action_id"]: step for step in data["setup_steps"]}

        self.assertEqual(data["decision"], "openclaw_weixin_setup_blocked_target")
        self.assertIn("openclaw_weixin_target_user_id_missing", _blocker_ids(data))
        self.assertEqual(steps["login_openclaw_weixin_account"]["status"], "already_satisfied")
        self.assertEqual(steps["provide_explicit_ilink_target"]["status"], "proposed_only")
        self.assertEqual(data["send_attempts"], 0)

    def test_fully_ready_gate_allows_only_later_send_probe(self):
        data = run_wechat_openclaw_setup_gate(
            readiness_report=_readiness(
                plugin_present=True,
                plugin_enabled=True,
                account_count=1,
                target_ready=True,
            )
        ).to_dict()

        self.assertTrue(data["ok"])
        self.assertEqual(data["decision"], "openclaw_weixin_setup_gate_ready_for_send_probe")
        self.assertTrue(data["ready_for_send_probe"])
        self.assertTrue(data["requires_real_send_probe"])
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertFalse(data["desktop_file_transfer_assistant_verified"])

    def test_cli_writes_no_send_report(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            (state / "openclaw.json").write_text(
                json.dumps(
                    {
                        "plugins": {
                            "entries": {
                                "openclaw-weixin": {"enabled": False},
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = Path(td) / "setup_gate.json"
            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ), mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness._run_command",
                side_effect=_healthy_runner(),
            ), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "--state-dir",
                        str(state),
                        "--output",
                        str(output),
                        "--json",
                    ]
                )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["decision"], "openclaw_weixin_setup_blocked_plugin")
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["install_attempts"], 0)


def _readiness(
    *,
    decision: str = "openclaw_weixin_target_user_id_missing",
    node_version: str = "22.19.0",
    plugin_present: bool = True,
    plugin_enabled: bool = True,
    account_count: int = 1,
    target_ready: bool = False,
) -> dict:
    accounts = [
        {
            "account_id_hash": f"hash-{index}",
            "configured": True,
            "token_present": True,
            "token_length": 12,
            "token_sha256_prefix": "abc123",
        }
        for index in range(account_count)
    ]
    bot_ready = plugin_present and plugin_enabled and account_count > 0
    return {
        "mode": "wechat-openclaw-readiness",
        "safety_mode": "read_only_openclaw_config_probe",
        "ok": bool(bot_ready and target_ready),
        "decision": (
            "openclaw_weixin_bot_channel_send_ready"
            if bot_ready and target_ready
            else decision
        ),
        "cli_path": "/bin/openclaw",
        "node_path": "/bin/node",
        "node_version": node_version,
        "node_min_required": "22.19.0",
        "openclaw_command": {"returncode": 0},
        "openclaw_version": "2026.6.10",
        "config_present": True,
        "plugin_config": {
            "present": plugin_present,
            "enabled": plugin_enabled,
        },
        "accounts": accounts,
        "bot_channel_ready": bot_ready,
        "send_action_ready": bool(bot_ready and target_ready),
        "target_user_id_kind": "ilink_wechat_user_id" if target_ready else "missing_or_invalid",
        "target_user_id_present": target_ready,
        "desktop_wechat_control_verified": False,
        "desktop_file_transfer_assistant_verified": False,
        "send_attempts": 0,
    }


def _healthy_runner():
    def run(args, _timeout):
        mapping = {
            ("node", "--version"): CommandResult(
                ("node", "--version"),
                0,
                stdout="v22.19.0\n",
            ),
            ("/bin/openclaw", "--version"): CommandResult(
                ("/bin/openclaw", "--version"),
                0,
                stdout="2026.6.10\n",
            ),
        }
        return mapping.get(tuple(args), CommandResult(tuple(args), 127, error="not_found"))

    return run


def _blocker_ids(data: dict) -> set[str]:
    return {str(item["id"]) for item in data["blockers"]}


def _step_ids(data: dict) -> set[str]:
    return {str(item["action_id"]) for item in data["setup_steps"]}


if __name__ == "__main__":
    unittest.main()
