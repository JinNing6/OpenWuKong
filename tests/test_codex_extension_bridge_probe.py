import json
import tempfile
import unittest
from pathlib import Path

from openwukong.evaluation.codex_extension_bridge_probe import (
    probe_codex_extension_bridge,
)


class CodexExtensionBridgeProbeTests(unittest.TestCase):
    def test_probe_reports_webview_bridge_required_for_context_only_commands(self):
        with tempfile.TemporaryDirectory() as td:
            extension = _write_codex_extension_fixture(Path(td) / "openai.chatgpt-1.0.0")
            client = _CodexCapabilitiesClient(extension)

            report = probe_codex_extension_bridge(
                "http://127.0.0.1:8787",
                workspace_path="E:/ideaProjects/agent/openwukong",
                bridge_client=client,
                installed_extension_roots=(Path(td),),
            ).to_dict()

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["decision"], "codex_extension_webview_bridge_required")
        self.assertFalse(report["prompt_send_ready"])
        self.assertTrue(report["requires_webview_bridge"])
        self.assertEqual(report["extension_exports_type"], "object")
        self.assertEqual(report["extension_export_keys"], ["noop"])
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)
        roles = {item["command_id"]: item for item in report["command_roles"]}
        self.assertEqual(roles["chatgpt.addToThread"]["role"], "context_only")
        self.assertFalse(roles["chatgpt.addToThread"]["prompt_send"])
        evidence_markers = {
            marker
            for item in report["webview_route_evidence"]
            for marker in item["markers"]
        }
        self.assertIn("composer_prefill", evidence_markers)
        self.assertIn("shared-object-set", evidence_markers)
        self.assertIn("open-vscode-command", evidence_markers)

    def test_probe_reports_endpoint_missing_without_control_attempts(self):
        client = _FailingClient()

        report = probe_codex_extension_bridge(
            "http://127.0.0.1:8787",
            workspace_path="E:/ideaProjects/agent/openwukong",
            bridge_client=client,
        ).to_dict()

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "codex_extension_bridge_endpoint_unavailable")
        self.assertEqual(report["control_attempts"], 0)
        self.assertEqual(report["window_input_attempts"], 0)


class _CodexCapabilitiesClient:
    def __init__(self, extension_path: Path):
        self.extension_path = extension_path
        self.calls = []

    def read_codex_capabilities(self, bridge_url, target):
        self.calls.append(
            {
                "bridge_url": bridge_url,
                "workspace_path": target.workspace_path,
            }
        )
        return {
            "ok": True,
            "decision": "codex_webview_bridge_required",
            "extension": {
                "installed": True,
                "extension_path": str(self.extension_path),
                "version": "1.0.0",
                "display_name": "Codex",
                "exports_type": "object",
                "export_keys": ["noop"],
            },
            "prompt_send_ready": False,
            "requires_webview_bridge": True,
            "command_roles": [
                {
                    "command_id": "chatgpt.addToThread",
                    "role": "context_only",
                    "prompt_send": False,
                    "available": True,
                    "contributed": True,
                },
                {
                    "command_id": "chatgpt.newCodexPanel",
                    "role": "surface_open",
                    "prompt_send": False,
                    "available": True,
                    "contributed": True,
                },
            ],
            "contributed_commands": [
                {
                    "command_id": "chatgpt.addToThread",
                    "title": "Add to Codex Thread",
                    "category": "Codex",
                }
            ],
        }


class _FailingClient:
    def read_codex_capabilities(self, bridge_url, target):
        raise TimeoutError("endpoint missing")


def _write_codex_extension_fixture(path: Path) -> Path:
    (path / "webview" / "assets").mkdir(parents=True)
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "chatgpt",
                "publisher": "openai",
                "version": "1.0.0",
                "displayName": "Codex",
            }
        ),
        encoding="utf-8",
    )
    (path / "out").mkdir()
    (path / "out" / "extension.js").write_text(
        "vscode.commands.registerCommand('chatgpt.addToThread',()=>{})",
        encoding="utf-8",
    )
    (path / "webview" / "assets" / "page.js").write_text(
        "shared-object-set composer_prefill open-vscode-command",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
