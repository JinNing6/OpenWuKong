# OpenWukong IDE Bridge

This extension exposes a local JSON bridge for VS Code-compatible IDE products.
OpenWukong should use this bridge before UIA or vision when `ide_bridge_url` is configured.
The bridge does not auto-start by default, so normal Cursor/VS Code workspaces
are not interrupted. Start it explicitly with `OpenWukong: Start IDE Bridge`,
or enable `openwukong.bridge.autoStart` only inside an isolated test profile.
By default, `openwukong.bridge.port` is `0`, so the operating system assigns an
unused loopback port. If a fixed preferred port is configured and already in
use, the bridge can silently try nearby ports through
`openwukong.bridge.autoPortOnConflict`, then bind to an operating-system-assigned
unused loopback port when `openwukong.bridge.dynamicPortOnConflict` is enabled.
The started bridge publishes the actual `bridge_url` under the local
OpenWukong IDE bridge registry so control code can discover it without
probing fixed ports.

## Bridge Endpoints

- `POST /v1/ide/read`: read a compact conversation/session summary.
- `POST /v1/ide/state`: read workspace folders, active editor metadata, visible editor count, and diagnostics.
- `POST /v1/ide/command`: execute an allowlisted command from `openwukong.bridge.allowedCommands`.
- `POST /v1/ide/capabilities`: discover available command ids and configured chat adapter availability.
- `POST /v1/ide/codex/capabilities`: inspect the installed OpenAI Codex extension and classify its `chatgpt.*` commands without executing them.
- `POST /v1/ide/chat`: send a message through a named chat adapter.
- `POST /v1/ide/cursor/glass-agent-query`: probe Cursor's
  `glass.newAgentWithQuery` route behind an explicit live safety profile.

Chat adapter commands may start a long-running Agent turn. The bridge uses
`openwukong.bridge.chatCommandAwaitTimeoutMs` as a bounded await and returns a
`dispatch_status` of `pending` when the IDE command does not resolve quickly.
Treat that as dispatch-pending rather than as a completed model response; use a
separate transcript or state readback step to verify delivery.

Cursor readback commands can also be blocked while an Agent turn is active. The
Cursor composer-state endpoint defaults to a safe selected-id read and does not
call `composer.getComposerHandleById` in normal profiles. Handle reads require
`include_handles: true` and `safety_profile: "isolated_cursor_read_probe"`.
The generic `/v1/ide/command` endpoint also blocks direct
`composer.getComposerHandleById` calls unless the request carries an isolated
Cursor safety profile, even when that command appears in
`openwukong.bridge.allowedCommands`.
When enabled, handle reads use
`openwukong.bridge.cursorReadCommandAwaitTimeoutMs` as a bounded await and
return `state_status: pending` with `pending_commands` when private Cursor read
commands do not resolve quickly. Treat that as state-pending, keep the bridge
alive, and retry readback later instead of classifying the bridge as dead.

The Cursor draft hook has three safety profiles:

- `live_cursor_attach_draft_probe`: live logged-in attach-only dry-run. It
  checks whether the low-risk `composer.createNew` draft route is available,
  but does not write, submit, or read private composer handles.
- `live_cursor_attach_draft_write_probe`: live logged-in draft write. It can
  create a new Cursor draft through `composer.createNew` with
  `skipShowAndFocus` and `skipSelect`, and must be accepted only after local
  Cursor storage readback finds the marker on user/draft-side state. This does
  not prove assistant completion.
- `isolated_cursor_draft_probe`: isolated-profile draft mutation. This may read
  private composer handles for readback and should be run only in a sacrificial
  Cursor profile.

Cursor's Glass Agent query probe uses a separate safety profile:

- `live_cursor_glass_agent_query_probe`: live logged-in Agent query dispatch.
  The endpoint hardcodes the Cursor command candidates instead of using the
  generic command allowlist, sends no mouse, keyboard, or clipboard input, and
  must be accepted only after assistant-side marker readback appears in local
  Cursor transcript storage. A user/prompt-side marker only proves the request
  was stored; it does not prove the Agent completed.

## Owned Scratch Command

The extension registers two built-in workspace-scoped commands for live bridge
verification:

- `openwukong.writeScratch`: writes a provided marker to
  `.openwukong/openwukong-owned-scratch.txt` in the first workspace folder and
  returns readback metadata.
- `openwukong.readScratch`: reads the same file without changing editor focus.

These commands are included in the default `openwukong.bridge.allowedCommands`
because they only touch the current workspace's OpenWukong scratch file. Use the
live owned IDE demo only when the IDE is opened on an isolated scratch workspace;
the runner verifies the bridge metadata before executing `openwukong.writeScratch`.

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

## Codex Extension Mapping

Use `POST /v1/ide/codex/capabilities` before attempting to automate the OpenAI
Codex panel. The endpoint reads the installed `openai.chatgpt` extension
metadata and classifies known `chatgpt.*` commands:

- `chatgpt.addToThread` and `chatgpt.addFileToThread` are context-only.
- `chatgpt.newChat`, `chatgpt.newCodexPanel`, `chatgpt.openSidebar`, and
  `chatgpt.openCommandMenu` open Codex UI surfaces.
- No command is treated as a prompt-send route unless it is explicitly marked
  as `prompt_send: true` by this bridge.

When the endpoint returns `codex_webview_bridge_required`, the correct next
step is a Codex-specific webview/shared-object bridge, not a retry through
Cursor composer commands.

## Isolated Contract Probe

Validate candidate chat commands only in an isolated Cursor profile and sacrificial workspace before enabling them in a real logged-in profile.

Use the contract probe to write temporary profile settings before launching the isolated IDE:

```powershell
python -m openwukong.evaluation.ide_bridge_contract_probe `
  http://127.0.0.1:8792 `
  --candidate-report logs\runtime\cursor-ide-bridge-r98\capabilities.json `
  --adapter-id cursor `
  --max-commands 3 `
  --probe-settings-output logs\runtime\cursor-ide-contract-r100\user-data\User\settings.json `
  --settings-port 8792 `
  --write-probe-settings-only `
  --json
```

Then launch the isolated Cursor profile with that `user-data` directory and run the contract probe against the bridge. The final real profile settings should come only from a successful validation report: accepted command, object-message argument shape, no workspace diff, and no foreground change.

## Safety Rules

- Keep `openwukong.bridge.autoStart` disabled in normal daily-work IDE profiles.
- If `openwukong.bridge.autoStart` is enabled for a controlled profile, keep
  `openwukong.bridge.autoStartRequiresWorkspace = true` so empty Cursor windows
  do not publish bridge endpoints with no workspace identity.
- Keep `openwukong.bridge.allowedCommands` narrow.
- Keep `openwukong.bridge.port = 0` unless a specific isolated test profile
  needs a fixed endpoint. If an older profile still has `8787`, reset it to `0`
  or rely on the dynamic conflict fallback.
- Use `--probe-settings-output` only for an isolated Cursor profile or equivalent sacrificial IDE profile.
- Keep chat adapters disabled until capability discovery proves the target command exists.
- Treat Cursor private handle commands as isolated-profile-only, even if they
  are present in the command allowlist.
- Use `live_cursor_attach_draft_probe` only for attach-only dry-runs against an
  already logged-in Cursor bridge. This profile checks whether a low-risk
  `composer.createNew` draft route is available, but it does not read private
  composer handles and it does not allow writes.
- Use `live_cursor_attach_draft_write_probe` only when a real live Cursor draft
  write is explicitly intended. It may create a draft in the logged-in Cursor
  workspace, but it must not be counted as an Agent response unless a separate
  assistant-side transcript readback also passes.
- Use `openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs` to bound
  draft-hook command discovery and isolated draft command awaits. A pending
  response is a failed readiness signal, not proof that a draft was written.
- Prefer `IDE STATE`, `IDE CAPABILITIES`, and L3 shadow fixtures before any real command execution.
- Use UIA or vision only as fallback observation, not as the primary control route.
