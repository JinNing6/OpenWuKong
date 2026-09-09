import json
import socketserver
import threading
import unittest
import contextlib
import io
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from openwukong.evaluation.cursor_draft_hook_probe import main, probe_cursor_draft_hook


class _DraftHookHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.requests.append((self.path, payload))
        if self.path != "/v1/ide/cursor/draft-hook":
            self._send_json({"ok": False, "error": "unexpected_endpoint"}, status=404)
            return
        self._send_json(
            {
                "ok": True,
                "decision": "cursor_draft_hook_ready"
                if not payload.get("allow_write")
                else "cursor_draft_hook_written",
                "dry_run": not payload.get("allow_write"),
                "can_write_draft": True,
                "composer_id": "composer-1",
            }
        )

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class CursorDraftHookProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), _DraftHookHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.bridge_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        _DraftHookHandler.requests = []

    def test_dry_run_probe_calls_draft_hook_without_control_attempts(self):
        report = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path=Path("E:/ideaProjects/agent/openwukong"),
            message="OPENWUKONG_DRAFT_HOOK_DRY_RUN",
        )
        data = report.to_dict()

        self.assertEqual(data["mode"], "cursor-draft-hook-probe")
        self.assertEqual(data["safety_mode"], "dry_run_bridge_contract")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["draft_write_attempts"], 0)
        self.assertEqual(data["bridge_probe_attempts"], 1)
        self.assertEqual(data["decision"], "cursor_draft_hook_ready")
        self.assertEqual(_DraftHookHandler.requests[0][0], "/v1/ide/cursor/draft-hook")
        self.assertFalse(_DraftHookHandler.requests[0][1]["allow_write"])
        self.assertEqual(
            _DraftHookHandler.requests[0][1]["target"]["workspace_path"],
            "E:\\ideaProjects\\agent\\openwukong",
        )

    def test_write_probe_is_blocked_without_isolated_safety_profile(self):
        report = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_DRAFT_HOOK_WRITE",
            allow_write=True,
        )
        data = report.to_dict()

        self.assertEqual(data["decision"], "cursor_draft_hook_write_requires_isolated_profile")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["bridge_probe_attempts"], 0)
        self.assertEqual(_DraftHookHandler.requests, [])

    def test_live_attach_profile_is_dry_run_only(self):
        dry_run = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_LIVE_ATTACH_DRY_RUN",
            safety_profile="live_cursor_attach_draft_probe",
        )
        dry_data = dry_run.to_dict()

        write = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_LIVE_ATTACH_WRITE",
            allow_write=True,
            safety_profile="live_cursor_attach_draft_probe",
        )
        write_data = write.to_dict()

        self.assertTrue(dry_data["ok"])
        self.assertEqual(_DraftHookHandler.requests[0][1]["safety_profile"], "live_cursor_attach_draft_probe")
        self.assertFalse(_DraftHookHandler.requests[0][1]["allow_write"])
        self.assertEqual(write_data["decision"], "cursor_draft_hook_write_requires_isolated_profile")
        self.assertEqual(write_data["bridge_probe_attempts"], 0)
        self.assertEqual(len(_DraftHookHandler.requests), 1)

    def test_live_attach_write_profile_records_single_draft_attempt(self):
        report = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_LIVE_ATTACH_WRITE",
            allow_write=True,
            safety_profile="live_cursor_attach_draft_write_probe",
        )
        data = report.to_dict()

        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["safety_mode"], "live_attach_draft_write_probe")
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["draft_write_attempts"], 1)
        self.assertEqual(data["decision"], "cursor_draft_hook_written")
        self.assertTrue(_DraftHookHandler.requests[0][1]["allow_write"])
        self.assertEqual(
            _DraftHookHandler.requests[0][1]["safety_profile"],
            "live_cursor_attach_draft_write_probe",
        )

    def test_isolated_write_probe_records_single_draft_attempt(self):
        report = probe_cursor_draft_hook(
            self.bridge_url,
            workspace_path="E:/ideaProjects/agent/openwukong",
            message="OPENWUKONG_DRAFT_HOOK_WRITE",
            allow_write=True,
            safety_profile="isolated_cursor_draft_probe",
            composer_ids=("composer-1",),
        )
        data = report.to_dict()

        self.assertTrue(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 1)
        self.assertEqual(data["draft_write_attempts"], 1)
        self.assertEqual(data["decision"], "cursor_draft_hook_written")
        self.assertTrue(_DraftHookHandler.requests[0][1]["allow_write"])
        self.assertEqual(_DraftHookHandler.requests[0][1]["safety_profile"], "isolated_cursor_draft_probe")
        self.assertEqual(_DraftHookHandler.requests[0][1]["composer_ids"], ["composer-1"])

    def test_cli_discovers_dynamic_bridge_url_from_registry_when_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "OpenWukong" / "ide-bridges"
            registry.mkdir(parents=True)
            (registry / "cursor.json").write_text(
                json.dumps(
                    {
                        "schema_version": "openwukong-ide-bridge-registry-v1",
                        "ide_bridges": [
                            {
                                "type": "ide_bridge",
                                "enabled": True,
                                "app_name": "Cursor",
                                "bridge_url": self.bridge_url,
                                "dynamic_port": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with patch.dict(
                "os.environ",
                {"LOCALAPPDATA": td, "PROGRAMDATA": ""},
                clear=True,
            ), contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--message",
                        "OPENWUKONG_DYNAMIC_REGISTRY_DRAFT_HOOK",
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["bridge_url"], self.bridge_url)
        self.assertEqual(data["decision"], "cursor_draft_hook_ready")


if __name__ == "__main__":
    unittest.main()
