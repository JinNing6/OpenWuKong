import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extensions" / "openwukong-vscode"


class IDEExtensionScaffoldTests(unittest.TestCase):
    def test_vscode_extension_manifest_declares_bridge_commands_and_config(self):
        package_json = EXTENSION_DIR / "package.json"
        data = json.loads(package_json.read_text(encoding="utf-8"))

        self.assertEqual(data["main"], "./src/extension.js")
        self.assertIn("onStartupFinished", data["activationEvents"])
        self.assertIn("onCommand:openwukong.startBridge", data["activationEvents"])
        self.assertIn("onCommand:openwukong.stopBridge", data["activationEvents"])
        command_ids = {
            item["command"]
            for item in data["contributes"]["commands"]
        }
        self.assertIn("openwukong.startBridge", command_ids)
        self.assertIn("openwukong.stopBridge", command_ids)

        properties = data["contributes"]["configuration"]["properties"]
        self.assertIn("openwukong.bridge.port", properties)
        self.assertIn("openwukong.bridge.sendCommand", properties)
        self.assertIn("openwukong.bridge.allowedCommands", properties)
        self.assertIn(
            "workbench.action.files.save",
            properties["openwukong.bridge.allowedCommands"]["default"],
        )
        self.assertIn("openwukong.bridge.chatAdapters", properties)
        chat_adapters = properties["openwukong.bridge.chatAdapters"]["default"]
        self.assertIn("cursor", chat_adapters)
        self.assertIn("copilot", chat_adapters)
        self.assertIn("codex", chat_adapters)

    def test_vscode_extension_bridge_exposes_semantic_state_and_command_endpoints(self):
        source = (EXTENSION_DIR / "src" / "extension.js").read_text(encoding="utf-8")

        self.assertIn("http.createServer", source)
        self.assertIn("/v1/ide/read", source)
        self.assertIn("/v1/ide/send", source)
        self.assertIn("/v1/ide/state", source)
        self.assertIn("/v1/ide/command", source)
        self.assertIn("/v1/ide/capabilities", source)
        self.assertIn("/v1/ide/chat", source)
        self.assertIn("vscode.commands.executeCommand", source)
        self.assertIn("vscode.commands.getCommands", source)
        self.assertIn("vscode.languages.getDiagnostics", source)
        self.assertIn("workspaceFolders", source)
        self.assertIn("allowedCommands", source)
        self.assertIn("chatAdapters", source)

    def test_vscode_extension_documents_chat_adapter_mapping_workflow(self):
        readme = (EXTENSION_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("IDE CAPABILITIES", readme)
        self.assertIn("openwukong.bridge.chatAdapters", readme)
        self.assertIn("vscode.commands.getCommands(true)", readme)
        self.assertIn("Do not hardcode private command ids", readme)


if __name__ == "__main__":
    unittest.main()
