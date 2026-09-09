import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openwukong.evaluation.wechat_openclaw_readiness import (
    CommandResult,
    main,
    run_wechat_openclaw_readiness,
)


class WeChatOpenClawReadinessTests(unittest.TestCase):
    def test_node_runtime_too_old_blocks_before_plugin_state(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            _write_config(state, plugin_enabled=True)

            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ):
                report = run_wechat_openclaw_readiness(
                    state_dir=str(state),
                    command_runner=_runner(
                        {
                            ("node", "--version"): CommandResult(
                                ("node", "--version"),
                                0,
                                stdout="v22.17.1\n",
                            ),
                            ("openclaw", "--version"): CommandResult(
                                ("openclaw", "--version"),
                                1,
                                stderr="Node.js v22.19+ is required",
                            ),
                        }
                    ),
                )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "openclaw_cli_node_runtime_too_old")
        self.assertFalse(data["desktop_wechat_control_verified"])
        self.assertEqual(data["send_attempts"], 0)

    def test_plugin_disabled_is_reported_without_reading_secret_values(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            _write_config(state, plugin_enabled=False)
            _write_account(state, "abc-im-bot", token="super-secret-token")

            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ):
                report = run_wechat_openclaw_readiness(
                    state_dir=str(state),
                    command_runner=_healthy_runner(),
                )
        data = report.to_dict()
        serialized = json.dumps(data, ensure_ascii=False)

        self.assertEqual(data["decision"], "openclaw_weixin_plugin_not_enabled")
        self.assertFalse(data["plugin_config"]["enabled"])
        self.assertEqual(data["accounts"][0]["token_length"], len("super-secret-token"))
        self.assertIn("token_sha256_prefix", data["accounts"][0])
        self.assertNotIn("super-secret-token", serialized)
        self.assertEqual(data["native_call_attempts"], 0)

    def test_account_ready_without_target_is_not_send_ready(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            _write_config(state, plugin_enabled=True)
            _write_account(state, "abc-im-bot", token="secret-token")

            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ):
                report = run_wechat_openclaw_readiness(
                    state_dir=str(state),
                    command_runner=_healthy_runner(),
                )
        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["decision"], "openclaw_weixin_target_user_id_missing")
        self.assertTrue(data["bot_channel_ready"])
        self.assertFalse(data["send_action_ready"])
        self.assertEqual(data["surface_id"], "wechat-openclaw-bot-channel")
        self.assertFalse(data["desktop_file_transfer_assistant_verified"])

    def test_account_and_explicit_ilink_target_make_bot_channel_send_ready(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            _write_config(state, plugin_enabled=True)
            _write_account(state, "abc-im-bot", token="secret-token")

            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ):
                report = run_wechat_openclaw_readiness(
                    state_dir=str(state),
                    command_runner=_healthy_runner(),
                    target_user_id="friend@im.wechat",
                )
        data = report.to_dict()

        self.assertTrue(data["ok"], data)
        self.assertEqual(data["decision"], "openclaw_weixin_bot_channel_send_ready")
        self.assertTrue(data["send_action_ready"])
        self.assertEqual(data["send_attempts"], 0)
        self.assertEqual(data["target_user_id_kind"], "ilink_wechat_user_id")

    def test_plugin_source_summary_reads_public_contract_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "plugin"
            source.mkdir()
            (source / "package.json").write_text(
                json.dumps(
                    {
                        "name": "@tencent-weixin/openclaw-weixin",
                        "version": "2.4.6",
                        "license": "MIT",
                        "author": "Tencent",
                        "peerDependencies": {"openclaw": ">=2026.5.12"},
                        "engines": {"node": ">=22"},
                        "ilink_appid": "bot",
                    }
                ),
                encoding="utf-8",
            )
            (source / "openclaw.plugin.json").write_text(
                json.dumps(
                    {
                        "id": "openclaw-weixin",
                        "version": "2.4.6",
                        "channels": ["openclaw-weixin"],
                    }
                ),
                encoding="utf-8",
            )
            (source / "README.md").write_text(
                "QR code login and sendmessage endpoint",
                encoding="utf-8",
            )
            state = Path(td) / "state"
            _write_config(state, plugin_enabled=False)

            with mock.patch(
                "openwukong.evaluation.wechat_openclaw_readiness.shutil.which",
                side_effect=lambda name: f"/bin/{name}",
            ):
                report = run_wechat_openclaw_readiness(
                    state_dir=str(state),
                    plugin_source_dir=str(source),
                    command_runner=_healthy_runner(),
                )
        source_data = report.to_dict()["plugin_source"]

        self.assertTrue(source_data["present"])
        self.assertEqual(source_data["package_name"], "@tencent-weixin/openclaw-weixin")
        self.assertEqual(source_data["plugin_id"], "openclaw-weixin")
        self.assertTrue(source_data["readme_mentions_sendmessage"])
        self.assertTrue(source_data["readme_mentions_qr_login"])

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            _write_config(state, plugin_enabled=False)
            output = Path(td) / "report.json"
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
        self.assertEqual(data["decision"], "openclaw_weixin_plugin_not_enabled")
        self.assertEqual(data["control_attempts"], 0)


def _write_config(state: Path, *, plugin_enabled: bool) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "openclaw.json").write_text(
        json.dumps(
            {
                "plugins": {
                    "entries": {
                        "openclaw-weixin": {
                            "enabled": plugin_enabled,
                        }
                    }
                },
                "channels": {
                    "openclaw-weixin": {
                        "botAgent": "OpenWukong/1.0",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _write_account(state: Path, account_id: str, *, token: str) -> None:
    account_dir = state / "openclaw-weixin" / "accounts"
    account_dir.mkdir(parents=True, exist_ok=True)
    (state / "openclaw-weixin" / "accounts.json").write_text(
        json.dumps([account_id]),
        encoding="utf-8",
    )
    (account_dir / f"{account_id}.json").write_text(
        json.dumps(
            {
                "token": token,
                "savedAt": "2026-06-29T00:00:00.000Z",
                "baseUrl": "https://ilinkai.weixin.qq.com/secret/path",
                "userId": "friend@im.wechat",
            }
        ),
        encoding="utf-8",
    )


def _healthy_runner():
    return _runner(
        {
            ("node", "--version"): CommandResult(
                ("node", "--version"),
                0,
                stdout="v22.19.0\n",
            ),
            ("openclaw", "--version"): CommandResult(
                ("openclaw", "--version"),
                0,
                stdout="2026.6.10\n",
            ),
            ("/bin/openclaw", "--version"): CommandResult(
                ("/bin/openclaw", "--version"),
                0,
                stdout="2026.6.10\n",
            ),
        }
    )


def _runner(mapping):
    def run(args, _timeout):
        return mapping.get(tuple(args), CommandResult(tuple(args), 127, error="not_found"))

    return run


if __name__ == "__main__":
    unittest.main()
