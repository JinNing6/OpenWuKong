# OpenWukong IDE Bridge

This extension exposes a local JSON bridge for VS Code-compatible IDE products.
OpenWukong should use this bridge before UIA or vision when `ide_bridge_url` is configured.

## Bridge Endpoints

- `POST /v1/ide/read`: read a compact conversation/session summary.
- `POST /v1/ide/state`: read workspace folders, active editor metadata, visible editor count, and diagnostics.
- `POST /v1/ide/command`: execute an allowlisted command from `openwukong.bridge.allowedCommands`.
- `POST /v1/ide/capabilities`: discover available command ids and configured chat adapter availability.
- `POST /v1/ide/chat`: send a message through a named chat adapter.

## Chat Adapter Mapping

Use `IDE CAPABILITIES` from OpenWukong before enabling any product-specific chat adapter.
The extension calls `vscode.commands.getCommands(true)` and reports which configured adapter candidates are available in the current IDE.

Configure adapters through `openwukong.bridge.chatAdapters`:

```json
{
  "openwukong.bridge.chatAdapters": {
    "cursor": {
      "label": "Cursor Chat",
      "commandId": "",
      "commandCandidates": []
    },
    "copilot": {
      "label": "GitHub Copilot Chat",
      "commandId": "",
      "commandCandidates": []
    },
    "codex": {
      "label": "Codex",
      "commandId": "",
      "commandCandidates": []
    }
  }
}
```

Do not hardcode private command ids as defaults. Cursor, Copilot, Codex, and VS Code-derived products can change internal command names across versions. Treat the command ids reported by `IDE CAPABILITIES` on the user's installed product as the source of truth, then set `commandId` or `commandCandidates` explicitly for that local environment.

## Safety Rules

- Keep `openwukong.bridge.allowedCommands` narrow.
- Keep chat adapters disabled until capability discovery proves the target command exists.
- Prefer `IDE STATE`, `IDE CAPABILITIES`, and L3 shadow fixtures before any real command execution.
- Use UIA or vision only as fallback observation, not as the primary control route.
