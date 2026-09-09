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
        self.assertEqual(properties["openwukong.bridge.port"]["default"], 0)
        self.assertEqual(properties["openwukong.bridge.port"]["minimum"], 0)
        self.assertEqual(properties["openwukong.bridge.host"]["default"], "127.0.0.1")
        self.assertFalse(properties["openwukong.bridge.autoStart"]["default"])
        self.assertIn("openwukong.bridge.autoStartRequiresWorkspace", properties)
        self.assertTrue(
            properties["openwukong.bridge.autoStartRequiresWorkspace"]["default"]
        )
        self.assertIn("openwukong.bridge.autoPortOnConflict", properties)
        self.assertIn("openwukong.bridge.dynamicPortOnConflict", properties)
        self.assertTrue(properties["openwukong.bridge.dynamicPortOnConflict"]["default"])
        self.assertIn("openwukong.bridge.silentAutoStartFailures", properties)
        self.assertIn("openwukong.bridge.sendCommand", properties)
        self.assertIn("openwukong.bridge.allowedCommands", properties)
        self.assertIn(
            "openwukong.writeScratch",
            properties["openwukong.bridge.allowedCommands"]["default"],
        )
        self.assertIn(
            "openwukong.readScratch",
            properties["openwukong.bridge.allowedCommands"]["default"],
        )
        self.assertIn(
            "workbench.action.files.save",
            properties["openwukong.bridge.allowedCommands"]["default"],
        )
        self.assertIn("openwukong.bridge.chatAdapters", properties)
        self.assertIn("openwukong.bridge.chatCommandAwaitTimeoutMs", properties)
        self.assertEqual(
            properties["openwukong.bridge.chatCommandAwaitTimeoutMs"]["default"],
            2500,
        )
        self.assertIn("openwukong.bridge.cursorReadCommandAwaitTimeoutMs", properties)
        self.assertEqual(
            properties["openwukong.bridge.cursorReadCommandAwaitTimeoutMs"]["default"],
            2500,
        )
        self.assertIn("openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs", properties)
        self.assertEqual(
            properties["openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs"]["default"],
            2500,
        )
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
        self.assertIn("/v1/ide/codex/capabilities", source)
        self.assertIn("/v1/ide/chat", source)
        self.assertIn("/v1/ide/cursor/composer-state", source)
        self.assertIn("/v1/ide/cursor/draft-hook", source)
        self.assertIn("/v1/ide/cursor/glass-agent-query", source)
        self.assertIn("handleCodexCapabilities", source)
        self.assertIn("OPENAI_CODEX_EXTENSION_ID", source)
        self.assertIn("CODEX_COMMAND_ROLES", source)
        self.assertIn("codex_webview_bridge_required", source)
        self.assertIn("chatgpt.addToThread", source)
        self.assertIn("context_only", source)
        self.assertIn("surface_open", source)
        self.assertIn("prompt_send_ready", source)
        self.assertIn("requires_webview_bridge", source)
        self.assertIn("exports_type", source)
        self.assertIn("export_keys", source)
        self.assertIn("handleCursorComposerState", source)
        self.assertIn("handleCursorDraftHook", source)
        self.assertIn("summarizeComposerHandle", source)
        self.assertIn("collectCursorHandleDiagnostics", source)
        self.assertIn("write_method_candidates", source)
        self.assertIn("function_path", source)
        self.assertIn("prototype_function_keys", source)
        self.assertIn("Object.getPrototypeOf", source)
        self.assertIn("setData", source)
        self.assertIn("applyCursorDraftMutation", source)
        self.assertIn("composer.createNew", source)
        self.assertIn("command_create_new_composer", source)
        self.assertIn("collectComposerIdsFromHandle", source)
        self.assertIn("inferCreatedComposerId", source)
        self.assertIn("beforeComposerIds", source)
        self.assertIn("afterComposerIds", source)
        self.assertIn("created && typeof created === \"string\"", source)
        self.assertIn("skipShowAndFocus", source)
        self.assertIn("skipSelect", source)
        self.assertIn("state_direct_patch", source)
        self.assertIn("loadedComposers.byId", source)
        self.assertIn("loadedComposers.store.byId", source)
        self.assertIn("mutation_strategy", source)
        self.assertIn("updateComposerData", source)
        self.assertIn("buildCursorPlainTextRichText", source)
        self.assertIn("cursor_draft_hook_write_requires_explicit_profile", source)
        self.assertIn("typeof handle.setData === \"function\"", source)
        self.assertIn("handle.setData({", source)
        self.assertIn("buildChatCommandArguments", source)
        self.assertIn("workbench.action.chat.open", source)
        self.assertIn("query: message", source)
        self.assertIn("executeCommandWithBoundedAwait", source)
        self.assertIn("chatCommandAwaitTimeoutMs", source)
        self.assertIn("cursorReadCommandAwaitTimeoutMs", source)
        self.assertIn("dispatch_status", source)
        self.assertIn("state_status", source)
        self.assertIn("pending_commands", source)
        self.assertIn("cursor_composer_state_command_rejected", source)
        self.assertIn("include_handles", source)
        self.assertIn("isolated_cursor_read_probe_required", source)
        self.assertIn("handle_read_allowed", source)
        self.assertIn("DANGEROUS_CURSOR_COMMANDS", source)
        self.assertIn("commandSafetyDecision", source)
        self.assertIn("cursor_command_requires_isolated_profile", source)
        self.assertIn("cursor_draft_hook_read_requires_isolated_or_live_profile", source)
        self.assertIn("LIVE_CURSOR_ATTACH_DRAFT_PROFILE", source)
        self.assertIn("live_cursor_attach_draft_probe", source)
        self.assertIn("cursor_draft_hook_live_attach_ready", source)
        self.assertIn("LIVE_CURSOR_ATTACH_DRAFT_WRITE_PROFILE", source)
        self.assertIn("live_cursor_attach_draft_write_probe", source)
        self.assertIn("cursor_draft_hook_live_attach_written", source)
        self.assertIn("cursor_local_storage_user_draft_marker_required", source)
        self.assertIn("buildCursorCreateNewDraftArguments", source)
        self.assertIn("CURSOR_GLASS_NEW_AGENT_WITH_QUERY_COMMANDS", source)
        self.assertIn("live_cursor_glass_agent_query_probe", source)
        self.assertIn("handleCursorGlassAgentQuery", source)
        self.assertIn("selectCursorGlassAgentQueryCommand", source)
        self.assertIn("cursor_glass_agent_query_dispatched", source)
        self.assertIn("cursor_local_storage_assistant_marker_required", source)
        self.assertIn("cursor_draft_hook_command_pending", source)
        self.assertIn("cursorDraftHookCommandAwaitTimeoutMs", source)
        self.assertIn("isolated_cursor_draft_probe_required", source)
        self.assertIn("pending: true", source)
        self.assertIn("Promise.race", source)
        self.assertNotIn(
            "const selectedIds = await vscode.commands.executeCommand(CURSOR_SELECTED_COMPOSER_IDS_COMMAND);",
            source,
        )
        self.assertNotIn(
            "const handle = await vscode.commands.executeCommand(CURSOR_COMPOSER_HANDLE_COMMAND, composerId);",
            source,
        )
        self.assertIn("setTimeout", source)
        self.assertIn("openwukong.writeScratch", source)
        self.assertIn("openwukong.readScratch", source)
        self.assertIn("writeOwnedScratch", source)
        self.assertIn("readOwnedScratch", source)
        self.assertIn(".openwukong", source)
        self.assertIn("openwukong-owned-scratch.txt", source)
        self.assertIn("vscode.workspace.fs.writeFile", source)
        self.assertIn("vscode.workspace.fs.readFile", source)
        self.assertIn("vscode.commands.executeCommand", source)
        self.assertIn("vscode.commands.getCommands", source)
        self.assertIn("vscode.languages.getDiagnostics", source)
        self.assertIn("workspaceFolders", source)
        self.assertIn("allowedCommands", source)
        self.assertIn("chatAdapters", source)

    def test_vscode_extension_avoids_cursor_disruptive_port_conflict_popups(self):
        source = (EXTENSION_DIR / "src" / "extension.js").read_text(encoding="utf-8")

        self.assertIn("autoPortOnConflict", source)
        self.assertIn("autoStartRequiresWorkspace", source)
        self.assertIn("maybeAutoStartBridge", source)
        self.assertIn("hasWorkspaceFolder", source)
        self.assertIn("onDidChangeWorkspaceFolders", source)
        self.assertIn("workspace folder required", source)
        self.assertIn("dynamicPortOnConflict", source)
        self.assertIn("silentAutoStartFailures", source)
        self.assertIn('config.get("bridge.port", 0)', source)
        self.assertIn("EADDRINUSE", source)
        self.assertIn("candidate.listen(port, host)", source)
        self.assertIn("listenOnPort(candidate, host, 0)", source)
        self.assertIn("candidate.address()", source)
        self.assertIn("writeBridgeRegistryState", source)
        self.assertIn("safeWriteBridgeRegistryState", source)
        self.assertIn("process.pid", source)
        self.assertIn("openwukong-ide-bridge-registry-v1", source)
        self.assertIn("ide-bridges", source)
        self.assertIn("listenBridgeServer", source)
        self.assertIn("createBridgeServer", source)
        self.assertIn("notify", source)
        self.assertNotIn(
            "OpenWukong bridge failed to start: ${error.message}",
            source,
        )

    def test_vscode_extension_documents_chat_adapter_mapping_workflow(self):
        readme = (EXTENSION_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("IDE CAPABILITIES", readme)
        self.assertIn("/v1/ide/codex/capabilities", readme)
        self.assertIn("openai.chatgpt", readme)
        self.assertIn("chatgpt.addToThread", readme)
        self.assertIn("context-only", readme)
        self.assertIn("codex_webview_bridge_required", readme)
        self.assertIn("openwukong.bridge.chatAdapters", readme)
        self.assertIn("openwukong.bridge.chatCommandAwaitTimeoutMs", readme)
        self.assertIn("openwukong.bridge.cursorReadCommandAwaitTimeoutMs", readme)
        self.assertIn("openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs", readme)
        self.assertIn("openwukong.bridge.autoStartRequiresWorkspace", readme)
        self.assertIn("dispatch-pending", readme)
        self.assertIn("state-pending", readme)
        self.assertIn("composer.getComposerHandleById", readme)
        self.assertIn("isolated_cursor_read_probe", readme)
        self.assertIn("isolated_cursor_draft_probe", readme)
        self.assertIn("live_cursor_attach_draft_probe", readme)
        self.assertIn("live_cursor_attach_draft_write_probe", readme)
        self.assertIn("live_cursor_glass_agent_query_probe", readme)
        self.assertIn("/v1/ide/cursor/glass-agent-query", readme)
        self.assertIn("assistant-side marker readback", readme)
        self.assertIn("isolated-profile-only", readme)
        self.assertIn("vscode.commands.getCommands(true)", readme)
        self.assertIn("Do not hardcode private command ids", readme)
        self.assertIn("--probe-settings-output", readme)
        self.assertIn("isolated Cursor profile", readme)
        self.assertIn("openwukong.writeScratch", readme)
        self.assertIn("openwukong-owned-scratch.txt", readme)


if __name__ == "__main__":
    unittest.main()
