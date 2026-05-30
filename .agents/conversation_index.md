# Conversation Index

Last updated: 2026-05-30

## North Star

Build an `AIOS Copilot` for the developer workstation.

Target capability:
- span IDE and desktop applications
- understand user tasks
- monitor progress
- decide when to wait, steer, recover, or stop
- act as a higher-level supervisor, not just a chat gateway

Current product framing:
- not "full AIOS" yet
- first become a reliable `cross-app copilot / supervisor`
- the execution baseline is `connector-first`, with `UIA` only as fallback

## Agreed Roadmap

Stage 1: Take the developer chain
- `Codex / Cursor / Copilot / Terminal / Git / Browser`

Stage 2: Stabilize the loop
- `Perceive -> Decide -> Take over -> Recover`

Stage 3: Expand surfaces
- `Documents / Spreadsheets / Web back office / IM`

Stage 4: Unified shell
- only after the above is stable
- then talk about a true `AIOS` shell layer

## Current Stage

Current stage: `Stage 1 - Developer workstation copilot foundation`

Why:
- the repo already has parser, monitor, cortex, supervisor, and UI
- the main bottleneck is not "having an LLM"
- the bottleneck is reliable execution, workspace identity, and recovery

## What Exists Now

Core chain already exists:
- `task_parser.py`: natural language -> task goals
- `ai_monitor.py`: window/process/project sensing
- `strategic_cortex.py`: LLM-based strategic decision
- `agent_supervisor.py`: matching, supervision, steer, retry, snapshot
- `supervisor_panel.py`: visual orchestration UI

## Validated Progress

2026-04-14
- strengthened `SteerOperator` so it prefers the matched window instead of only the PID
- added multi-path input/send fallback logic
- added `matched_window_title` propagation through supervisor state
- added `pyperclip` to requirements and installed it in `.venv`
- installed `pytest` in `.venv`
- added tests for steer behavior

2026-04-15
- added `Codex.exe` support in monitor process detection
- added Codex single-window fallback match in supervisor logic
- fixed supervisor panel pre-match to use `matched_window_title`
- changed task cards to display the real matched window title when available
- created `.agents` rules and this conversation index for persistent progress tracking
- introduced a first-class `connectors` package
- added `ConnectorTarget`, `ConnectorActionResult`, `SessionConnector`, and `ConnectorManager`
- added `UIAIDEConnector` as the current fallback IDE connector
- switched `AgentSupervisor` conversation read and steer flow to connector routing instead of direct `Application + SteerOperator` orchestration
- added `connector_hint` and `active_connector` to supervisor goal state and snapshots
- added connector registry tests
- added `TerminalCommandConnector` as the first real non-UIA connector
- added `workspace_path` support to goal/config/connector target routing
- added a direct terminal supervision path that does not depend on window matching
- validated managed PowerShell execution and transcript capture
- added terminal connector tests
- added `GitCommandConnector` as the second real non-UIA connector
- extended direct connector supervision to support `connector_hint=git`
- added managed git transcript capture and workspace-bound git execution
- added git connector tests
- added `BrowserSessionConnector` as the third real non-UIA connector
- extended direct connector supervision to support `connector_hint=browser`
- added `resource_url` routing through goal/config/snapshot/UI state
- added managed HTTP navigation, title extraction, and transcript capture
- added browser connector tests
- added supervisor browser config regression tests
- upgraded connector selection from first-match to score-based routing
- added `CodexDesktopConnector`, `CursorIDEConnector`, and `CopilotIDEConnector`
- registered IDE-specialized connectors ahead of the generic `UIAIDEConnector`
- tightened terminal/git routing so `workspace_path` alone no longer steals IDE sessions
- added task parser connector hint inference for `codex / cursor / copilot / terminal / git / browser`
- added IDE connector routing tests
- added task parser connector hint tests
- added first-class `workspace / session / task / action` identity model
- added `WorkspaceIdentityModel`, `WorkspaceRef`, `SessionRef`, `TaskRef`, `ActionRecord`, and `IdentitySnapshot`
- added runtime identity fields to supervisor goals: `task_id / workspace_id / workspace_label / active_session_id / last_action_id`
- changed supervisor matching to try workspace-bound session binding before window-title fallback
- added identity snapshot export and action recording for bind/read/send flows
- added workspace identity tests
- added supervisor identity snapshot tests
- upgraded workspace identity to support `known workspace roots` from config/runtime registration
- added workspace-root discovery from file/title paths using repo and project markers:
  `.git / .idea / .vscode / pyproject.toml / package.json / Cargo.toml / go.mod / requirements.txt`
- changed `workspace_id` generation to become path-aware when a real root path or resource URL is known
- added tests for:
  - reusing a registered root for pathless IDE states
  - raising nested file paths back to the repo root before binding

2026-05-17
- decided evaluation should be simulation-first:
  - build L1 offline replay first
  - skip L2 sandbox for now
  - only move to L3 real-environment shadow mode after L1 is stable
- added `openwukong.evaluation` package
- added `L1SimulationHarness`, `L1SimulationReport`, and `L1CaseResult`
- added JSON fixture loading and CLI report output via `python -m openwukong.evaluation.simulation`
- added L1 regression tests for:
  - Codex recorded-window routing
  - browser recorded-window routing
  - direct terminal routing without live windows
  - failed expectation reporting
  - fixture-file loading and report serialization
- added baseline fixture:
  `tests/fixtures/evaluation/l1_developer_workstation.json`
  covering Codex, Cursor, Chrome, Terminal, and Git

2026-05-18
- expanded L1 simulation semantics:
  - expected no-match cases can now pass without live connector resolution
  - `min_match_score` expectations can now flag weak/low-confidence matches
  - offline fuzzy auto-match threshold was raised to reduce false positives
- expanded the baseline L1 fixture to cover:
  - same-workspace disambiguation using connector preference
  - no-match behavior for missing projects
- added L1 wrong-target and route-quality reporting:
  - `forbidden_matched_pid` expectation detects known wrong targets
  - report JSON now includes connector confusion matrix
  - report JSON now includes low-score case summaries
  - report JSON now includes wrong-target case IDs
- fixed workspace identity scoring so exact project names outrank alias substring matches such as:
  `openwukong` over `openwukong-archive`
- expanded baseline fixture to cover:
  - wrong-target guard for similarly named Codex windows
  - ambiguous Cursor title selection
- added route-quality summary reporting:
  - per-connector case counts
  - pass/fail counts
  - min and average match score
- added same-name different-path workspace fixture coverage
- fixed recorded title-path workspace identity:
  - state titles now feed path data through `title_hint`, not explicit `workspace_path`
  - title-derived nested file paths can be raised to the named workspace component when project markers are unavailable
- added cross-run L1 trend reporting:
  - added `L1TrendReport` and `build_trend_report`
  - trend reports aggregate multiple L1 fixture runs into total pass rate, connector quality, and regression summaries
  - duplicate suite runs are counted as separate runs instead of collapsing by suite name
- extended the L1 CLI:
  - `--trend` accepts multiple fixture files
  - trend output supports both text and JSON modes
- started L3 shadow mode:
  - added `openwukong.evaluation.shadow`
  - added read-only `StaticStateObserver` and `FastDesktopStateObserver`
  - added `L3ShadowHarness`, `L3ShadowPlan`, and `L3ShadowReport`
  - shadow reports include `control_allowed=false`, `control_attempts=0`, route quality, proposed actions, and risk buckets
  - added CLI entry via `python -m openwukong.evaluation.shadow`
- tightened direct connector routing:
  - `terminal` and `git` now remain windowless in L1/L3 matching even when IDE windows are present
  - added regression coverage so git goals do not steal similarly named IDE windows
- ran L3 shadow mode against the real desktop fast-scan path:
  - report saved to `logs/evaluation/l3_shadow_real_fast_scan_20260518.json`
  - report now exports `observed_states` so real desktop misses can be converted into L1 fixtures
  - real scan observed Codex, Microsoft Edge, Cursor, and Antigravity windows
  - direct terminal/git goals remained safe with `control_attempts=0`
- expanded fast-scan process coverage:
  - Chrome, Edge, and Firefox windows are now included in read-only fast scans
  - browser window titles such as `page title - Google Chrome` now resolve to the page title instead of the browser brand
- added a real recorded L1 replay fixture:
  - `tests/fixtures/evaluation/l1_real_fast_scan_20260518.json`
  - covers real Codex title-only routing, Edge browser routing, Cursor remote/local routing, and Antigravity UIA fallback
- split L3 expectation profiles:
  - `exact` remains the default profile for recorded replay compatibility
  - `goal` ignores synthetic exact-window expectations such as `matched_pid`, `forbidden_matched_pid`, and `matched_window_title`
  - `goal` keeps connector/workspace expectations and adds a default confidence floor for visible-target connectors
  - low-confidence shadow plans now get `safety_decision=block_low_confidence`
  - CLI supports `--profile exact|goal`
- added a dedicated L3 goal-profile fixture:
  - `tests/fixtures/evaluation/l3_goal_current_desktop_20260518.json`
  - top-level `states` capture the read-only window snapshot for deterministic replay
  - `cases` contain only goal-level expectations, with no exact PID/window replay assertions
  - covers current Codex, Edge, Cursor remote/local, and Antigravity fallback targets
- ran live L3 goal fixture:
  - report saved to `logs/evaluation/l3_goal_current_desktop_live_20260518.json`
  - result: `5/5 passed`, `control_attempts=0`

2026-05-19
- added repeated-run L3 shadow trend reporting:
  - added `L3ShadowTrendReport` and `build_shadow_trend_report`
  - trend reports aggregate repeated read-only shadow runs into pass rate, connector quality, low-confidence cases, unverifiable cases, false-target cases, and unstable cases
  - unstable case detection now flags connector, matched-window, and workspace drift across repeated runs
- extended the L3 shadow CLI:
  - `--repeat N` runs the same suite multiple times through the same observer/harness path
  - `--interval SECONDS` optionally waits between repeated read-only scans
  - repeated runs output `mode=l3-shadow-trend`
  - control remains disabled: `control_allowed=false`, `control_attempts=0`
- added L3 trend regression tests for:
  - repeated report aggregation
  - connector/window drift detection
  - CLI `--repeat` JSON output without control attempts
- verified deterministic recorded-state L3 trend:
  - report saved to `logs/evaluation/l3_goal_current_desktop_recorded_trend_20260519.json`
  - result: `10/10 passed`, `run_count=2`, `control_attempts=0`, no unstable cases
- ran current live L3 trend against the desktop visible on 2026-05-19:
  - report saved to `logs/evaluation/l3_goal_current_desktop_trend_20260519.json`
  - result: `2/10 passed`, `run_count=2`, `control_attempts=0`
  - only Codex stayed confidently visible across the repeated scans
  - Edge/Cursor/Antigravity target cases were correctly classified as low-confidence or unverifiable because the current live desktop only exposed 3 observed states
  - this is an environment-presence signal, not permission to control or retry against the wrong window
- added a read-only Windows accessibility capability probe:
  - added `openwukong.evaluation.accessibility_probe`
  - scans top-level Windows desktop windows through accessibility metadata without clicking, typing, invoking controls, reading connector transcripts, or running app commands
  - report JSON exposes `mode=windows-accessibility-capability`, `safety_mode=read_only`, `control_allowed=false`, and `control_attempts=0`
  - scores per-window capability from UIA-style structure, stable identifiers, control types, inferred safe patterns, semantic input/action candidates, and risk buckets
  - recommends route priority per app family:
    `browser-devtools-or-extension`, `ide-extension-connector`, `office-object-model-or-addin`, `uia-semantic`, `uia-structural`, `msaa-win32-fallback`, `vision-fallback-last`
  - added conservative regression coverage so generic wrapper methods are not mistaken for real capabilities
  - added regression coverage so `TextPattern` alone is treated as readable text, not writable semantic input
  - added Windows console encoding protection for non-GBK window titles such as zero-width characters in browser titles
- ran live Windows accessibility capability scan on 2026-05-19:
  - report saved to `logs/evaluation/windows_accessibility_capability_20260519.json`
  - result: `window_count=15`, `total_elements=991`, `control_attempts=0`
  - capability distribution:
    `semantic=8`, `partial_semantic=4`, `structure_only=2`, `window_only=1`
  - strong/usable UIA-style surfaces included File Explorer, Microsoft Edge shell, Notepad shell, Antigravity/Codex-like Chromium shells, Clash Verge shell, and taskbar/actions
  - weak surfaces included `Weixin.exe` and `Docker Desktop.exe`, which exposed little more than structural panes
  - `NVIDIA Overlay.exe` was effectively `window_only`
  - Windows Terminal exposed shell chrome actions but not reliable terminal text/input semantics through this scan, so terminal control should remain connector-native rather than UIA-first
- added the first deterministic control route policy layer:
  - added `openwukong.connectors.route_policy`
  - added `ControlRouteStep`, `ControlRoutePlan`, and `ControlRouteMatrix`
  - route plans now classify app family and produce:
    primary route, fallback routes, locator source, action primitives, confidence floor, control decision, missing capabilities, and blocked status
  - current app-family routing includes:
    `browser`, `ide`, `terminal`, `git`, `office`, `im`, `overlay`, `system-shell`, `electron-cef`, and `generic-desktop`
  - primary deterministic routes now include:
    `browser-devtools-or-extension`, `ide-extension-connector`, `terminal-native-session`, `git-cli`, `office-object-model-or-addin`, `app-native-bridge-required`, `uia-semantic`, `uia-structural-observe`, and `no-deterministic-route`
  - Windows Terminal is now explicitly routed to `terminal-native-session`; UIA is downgraded to `uia-observe-chrome-only`
  - weak IM/Electron/overlay surfaces are blocked until a deterministic connector/native bridge exists
  - accessibility probe JSON now embeds per-window `control_route_plan` and a top-level `route_matrix`
- reran live Windows accessibility capability scan after route policy integration:
  - report saved to `logs/evaluation/windows_accessibility_capability_20260519.json`
  - result: `window_count=19`, `total_elements=1447`, `control_attempts=0`
  - route matrix summary:
    - app families:
      `browser=1`, `electron-cef=2`, `generic-desktop=3`, `ide=3`, `im=1`, `overlay=1`, `system-shell=6`, `terminal=2`
    - primary routes:
      `browser-devtools-or-extension=1`, `ide-extension-connector=3`, `terminal-native-session=2`, `uia-semantic=9`, `uia-structural-observe=1`, `app-native-bridge-required=2`, `no-deterministic-route=1`
    - blocked windows:
      `微信`, `Containers - Docker Desktop`, `NVIDIA GeForce Overlay`
- wired the deterministic route policy into shadow planning and the real steer safety gate:
  - `ConnectorManager.resolve_session_connector` now supports explicit `enforce_route_policy=True`
  - explicit connector preferences can no longer override a blocked route when enforcement is enabled
  - `AgentSupervisor._steer(..., dry_run=False)` now enables route-policy enforcement before calling connector `send_message`
  - blocked real steer attempts are recorded as `status=blocked`, do not call the connector, do not increment retry count, and emit a route-policy lifecycle error
  - dry-run planning remains non-destructive and does not trigger control
  - direct terminal/git/browser routes remain allowed through deterministic connector families
  - L3 shadow plans now include:
    `app_family`, `primary_route_id`, `route_control_decision`, and `route_missing_capabilities`
  - blocked route-policy targets in L3 shadow now add `route_policy_blocked` and get `safety_decision=block_route_policy`
- verified recorded L3 shadow after route-policy wiring:
  - report saved to `logs/evaluation/l3_goal_current_desktop_recorded_route_policy_20260519.json`
  - result: `5/5 passed`, `observed_state_count=8`, `control_attempts=0`
  - route fields correctly identify Codex/Cursor/Antigravity as `ide`, Edge as `browser`, and route them to deterministic connector-first primary routes
- deepened the first deterministic connector behind `terminal-native-session`:
  - `TerminalCommandConnector` now exposes route contract payload fields:
    `route_id=terminal-native-session`, `transport=managed-powershell-subprocess`, `shell`, `session_key`, and `command_index`
  - terminal sessions now persist cwd across commands by wrapping PowerShell execution and reading back the final provider path
  - `Set-Location` / `cd` style commands now affect subsequent commands within the same managed session
  - terminal commands now have a configurable `command_timeout`
  - timed-out commands return `success=false`, `error=timeout`, `exit_code=null`, and append `[timeout] Ns` to the transcript
  - execution remains non-interactive via `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass`
  - this is still a managed PowerShell subprocess transport, not full ConPTY yet; ConPTY remains the next deeper terminal substrate when interactive terminal-buffer control is required
- deepened the first deterministic connector behind `browser-devtools-or-extension`:
  - `ConnectorTarget` now carries an optional `debugger_url` so browser sessions can bind to a Chrome/Edge DevTools endpoint without relying on visual matching
  - `BrowserSessionConnector` now supports a DevTools `EVAL ...` command path through `Runtime.evaluate`
  - the connector selects DevTools page targets by `resource_url` before falling back to title matching
  - HTTP navigation remains available as an explicit fallback route:
    `route_id=browser-http-session`, `transport=requests-session`
  - DevTools action payloads expose:
    `route_id=browser-devtools-or-extension`, `transport=chrome-devtools-protocol`, `debugger_url`, `target_id`, `target_url`, `expression`, and returned remote object data
  - the default DevTools client can discover targets from `/json/list` and evaluate expressions over a minimal CDP WebSocket path
  - tests use local fake HTTP/CDP servers and injected fake clients; no live user browser is controlled
- started the deterministic connector behind `ide-extension-connector`:
  - `ConnectorTarget` now carries optional `ide_bridge_url`
  - added `IDEExtensionConnector` and `IDEExtensionBridgeClient`
  - the connector only claims targets with an explicit IDE bridge URL, so existing Codex/Cursor/Copilot/UIA fallback routing remains unchanged when no bridge is configured
  - bridge actions use a local JSON contract:
    `POST /v1/ide/read` and `POST /v1/ide/send`
  - action payloads expose:
    `route_id=ide-extension-connector`, `transport=vscode-extension-bridge`, `bridge_url`, `command_id`, `session_key`, and `command_index`
  - L1 simulation now supports `connector_hint=ide-extension` as a windowless direct route when `ide_bridge_url` is present
  - supervisor config loading and snapshots now preserve `ide_bridge_url`
  - added a minimal VS Code/Cursor-compatible extension scaffold under `extensions/openwukong-vscode`
  - the scaffold exposes start/stop commands and local bridge endpoints; real send behavior requires a configured IDE command id instead of assuming Cursor/Copilot private UI internals
- deepened `ide-extension-connector` with semantic IDE actions:
  - `IDEExtensionConnector.send_message` now recognizes:
    `IDE STATE` and `IDE COMMAND <command_id>`
  - `IDE STATE` calls `POST /v1/ide/state` and returns workspace folders, active editor metadata, visible editor count, and diagnostics from the extension bridge
  - `IDE COMMAND <command_id>` calls `POST /v1/ide/command` with JSON arguments parsed before any bridge call
  - invalid command argument JSON is blocked locally with `invalid_ide_command_arguments`
  - VS Code/Cursor extension scaffold now exposes `/v1/ide/state` and `/v1/ide/command`
  - extension command execution is controlled by `openwukong.bridge.allowedCommands`; commands outside the allowlist return `command_not_allowlisted`
  - the extension gathers diagnostics through VS Code language diagnostics instead of screen scraping
- added configurable IDE chat adapter capability discovery:
  - `IDEExtensionConnector.send_message` now recognizes:
    `IDE CAPABILITIES` and `IDE CHAT <adapter_id>`
  - `IDE CAPABILITIES` calls `POST /v1/ide/capabilities` and returns available command ids plus configured chat adapter availability
  - `IDE CHAT <adapter_id>` calls `POST /v1/ide/chat` and sends a message through the named adapter
  - missing chat messages are blocked locally with `missing_ide_chat_message`
  - JSON bridge error bodies from non-2xx responses now remain semantic connector errors instead of becoming opaque HTTP exceptions
  - VS Code/Cursor extension scaffold now exposes `/v1/ide/capabilities` and `/v1/ide/chat`
  - extension config now includes `openwukong.bridge.chatAdapters` with placeholder entries for `cursor`, `copilot`, and `codex`
  - the scaffold discovers available commands via `vscode.commands.getCommands(true)` and does not assume private Cursor/Copilot/Codex command ids
- added bridge-present IDE evaluation fixtures:
  - `tests/fixtures/evaluation/l1_ide_extension_bridge_present.json` covers:
    `IDE CAPABILITIES`, `IDE STATE`, and `IDE CHAT cursor`
  - the L1 fixture verifies explicit `ide_bridge_url` routes directly to `ide-extension` with no live window match and no UIA dependency
  - `tests/fixtures/evaluation/l3_ide_extension_bridge_present.json` covers the same semantic bridge actions under L3 shadow goal profile
  - L3 shadow now maps windowless `ide-extension` plans back to the IDE route policy:
    `app_family=ide`, `primary_route_id=ide-extension-connector`, `route_control_decision=prefer_deterministic_connector`
  - the VS Code extension scaffold now documents the chat adapter mapping workflow and explicitly warns not to hardcode private command ids
- added a read-only IDE bridge capability capture harness:
  - added `openwukong.evaluation.ide_bridge_capture`
  - the harness only calls `POST /v1/ide/capabilities`
  - it never calls `/v1/ide/command`, `/v1/ide/chat`, UIA, vision, click, or keyboard input
  - reports expose `mode=ide-bridge-capability-capture`, `safety_mode=read_only`, `control_allowed=false`, and `control_attempts=0`
  - adapter mappings preserve unavailable command candidates without enabling them as active `commandId`
  - CLI supports JSON output and optional report file writing for local capability capture

## Last Verified State

Verified locally:
- fast scan can now see `Codex.exe`
- keyword `openwukong` can pre-match to the single visible `Codex` window on this machine
- `py_compile` passed for the updated monitor, supervisor, UI, and helper test files
- `unittest` passed for:
  - `tests.test_steer_operator`
  - `tests.test_ai_monitor_helpers`
  - `tests.test_connector_registry`
  - `tests.test_terminal_connector`
  - `tests.test_git_connector`
  - `tests.test_browser_connector`
  - `tests.test_supervisor_browser_config`
  - `tests.test_ide_connector_routing`
  - `tests.test_task_parser_connector_hints`
  - `tests.test_workspace_identity`
  - `tests.test_supervisor_identity_snapshot`
- current full related regression suite passed:
  - `34 tests`
  - includes connector routing, parser hints, browser/git/terminal direct paths, workspace identity, and supervisor identity snapshot
- terminal smoke check succeeded:
  - command execution via managed PowerShell
  - transcript capture via terminal connector
- browser DevTools route verified locally:
  - focused browser connector suite: `9 tests` passed
  - related connector/evaluation regression suite: `77 tests` passed
  - L1 developer workstation baseline fixture: `10/10 passed`
  - `py_compile` passed for updated connector and browser test files
- IDE extension bridge route verified locally:
  - focused IDE extension/config/L1 scaffold suite: `24 tests` passed
  - related connector/evaluation regression suite: `92 tests` passed
  - L1 developer workstation baseline fixture: `10/10 passed`
  - `py_compile` passed for updated connector, simulation, supervisor, and test files
  - `node --check extensions\openwukong-vscode\src\extension.js` passed
- IDE semantic bridge actions verified locally:
  - focused IDE extension connector/scaffold suite: `11 tests` passed
  - related connector/evaluation regression suite: `95 tests` passed
  - L1 developer workstation baseline fixture: `10/10 passed`
  - `py_compile` passed for updated IDE extension connector and tests
  - `node --check extensions\openwukong-vscode\src\extension.js` passed
- IDE chat adapter capability discovery verified locally:
  - focused IDE extension connector/scaffold suite: `15 tests` passed
  - related connector/evaluation regression suite: `99 tests` passed
  - L1 developer workstation baseline fixture: `10/10 passed`
  - `py_compile` passed for updated IDE extension connector and tests
  - `node --check extensions\openwukong-vscode\src\extension.js` passed
- bridge-present IDE fixtures verified locally:
  - focused bridge-present L1/L3/doc tests: `3 tests` passed
  - related connector/evaluation regression suite: `102 tests` passed
  - L1 developer workstation baseline fixture: `10/10 passed`
  - L1 bridge-present IDE fixture: `3/3 passed`
  - L1 baseline + bridge-present trend: `13/13 passed`, `run_count=2`
  - L3 current desktop recorded goal fixture: `5/5 passed`, `control_attempts=0`
  - L3 bridge-present IDE fixture: `3/3 passed`, `control_attempts=0`
  - `py_compile` passed for updated shadow and test files
  - `node --check extensions\openwukong-vscode\src\extension.js` passed
- IDE bridge capability capture harness verified locally:
  - focused IDE bridge capture suite: `3 tests` passed
  - related connector/evaluation regression suite: `105 tests` passed
  - L1 bridge-present IDE fixture: `3/3 passed`
  - L3 bridge-present IDE fixture: `3/3 passed`, `control_attempts=0`
  - `py_compile` passed for updated capture module and tests
  - `node --check extensions\openwukong-vscode\src\extension.js` passed
  - live default bridge probe against `http://127.0.0.1:8787` was attempted in read-only mode and saved to:
    `logs/evaluation/ide_bridge_capabilities_20260519.json`
  - probe result: bridge unavailable / connection timeout, `ok=false`, `control_attempts=0`, no adapter mapping was fabricated
- git smoke check succeeded:
  - `git status --short --branch` execution in the repo root
  - transcript capture via git connector
- browser smoke check succeeded:
  - local HTTP page fetch via managed browser connector
  - page title extraction and transcript capture
- parser connector hint smoke check succeeded:
  - `Codex` input resolves to `connector_hint=codex`
  - browser input resolves to `connector_hint=browser` plus extracted `resource_url`
  - terminal input resolves to `connector_hint=terminal` plus default `workspace_path=.`
- workspace identity smoke checks succeeded:
  - explicit `workspace_path` resolves to a root-aware `workspace_id`
  - Codex session binds to the same workspace id before title fallback
  - supervisor snapshot now exports `identity.workspaces / sessions / tasks / actions`
  - registered workspace roots can now be reused for pathless IDE states with the same root-aware workspace id
  - nested file paths inside a repo can now be raised back to the repo root before workspace binding
- L1 simulation harness verified locally:
  - `python -m openwukong.evaluation.simulation tests\fixtures\evaluation\l1_developer_workstation.json`
  - result: `10/10 passed`
- L1 trend reporting verified locally:
  - `python -m openwukong.evaluation.simulation --trend tests\fixtures\evaluation\l1_developer_workstation.json tests\fixtures\evaluation\l1_developer_workstation.json --json`
  - result: `20/20 passed`, `run_count=2`, no regressions
- L3 shadow mode verified locally:
  - API tests cover read-only plan generation from observed state snapshots
  - API tests cover unverifiable case reporting without control attempts
  - CLI tests cover `--states` deterministic replay mode
  - result: `control_attempts=0`
- L3 real fast-scan verified locally:
  - `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l1_developer_workstation.json --json`
  - result: `control_attempts=0`, `observed_state_count=8`
  - expected baseline comparison result: `3/10 passed`, because the baseline fixture contains simulated PID/window expectations and the real desktop did not contain those target windows
- L3 goal-profile fast-scan verified locally:
  - `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l1_developer_workstation.json --profile goal --json`
  - report saved to `logs/evaluation/l3_shadow_goal_profile_real_fast_scan_20260518.json`
  - result: `control_attempts=0`, `observed_state_count=8`, `3/10 passed`
  - all 7 failed synthetic-baseline targets are now classified as low confidence rather than PID mismatch or unverifiable
- dedicated L3 goal fixture verified locally:
  - `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --states tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --profile goal --json`
  - result: `5/5 passed`, `control_attempts=0`
- dedicated L3 goal fixture live fast-scan verified locally:
  - `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --profile goal --json`
  - report saved to `logs/evaluation/l3_goal_current_desktop_live_20260518.json`
  - result: `5/5 passed`, `observed_state_count=8`, `control_attempts=0`
- real recorded L1 fast-scan fixture verified locally:
  - `python -m openwukong.evaluation.simulation tests\fixtures\evaluation\l1_real_fast_scan_20260518.json`
  - result: `5/5 passed`
- combined baseline + real fast-scan trend verified locally:
  - `python -m openwukong.evaluation.simulation --trend tests\fixtures\evaluation\l1_developer_workstation.json tests\fixtures\evaluation\l1_real_fast_scan_20260518.json --json`
  - result: `15/15 passed`, no regressions
- latest related unittest suite passed:
  - `56 tests`
  - includes L1 simulation, connector routing, parser hints, identity, terminal/git/browser connector tests, and supervisor browser config tests
- `py_compile` passed for:
  - `src/openwukong/monitor/ai_monitor.py`
  - `src/openwukong/evaluation/__init__.py`
  - `src/openwukong/evaluation/simulation.py`
  - `src/openwukong/evaluation/shadow.py`
  - `src/openwukong/supervisor/identity.py`
  - `tests/test_ai_monitor_helpers.py`
  - `tests/test_l1_simulation_harness.py`
  - `tests/test_l3_shadow_mode.py`
  - `tests/test_workspace_identity.py`
- L3 repeated trend verified locally:
  - recorded-state repeat:
    `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --states tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --profile goal --repeat 2 --json`
    result: `10/10 passed`, `run_count=2`, `control_attempts=0`
  - live fast-scan repeat:
    `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --profile goal --repeat 2 --interval 0.1 --json`
    result: `2/10 passed`, `run_count=2`, `control_attempts=0`, low-confidence/unverifiable cases reflect currently missing live target windows
- Windows accessibility capability probe verified locally:
  - focused tests:
    `python -m unittest tests.test_accessibility_probe`
    result: `7 tests` passed
  - related regression suite:
    `python -m unittest tests.test_accessibility_probe tests.test_ai_monitor_helpers tests.test_l1_simulation_harness tests.test_l3_shadow_mode tests.test_workspace_identity tests.test_connector_registry tests.test_ide_connector_routing tests.test_task_parser_connector_hints tests.test_supervisor_identity_snapshot tests.test_terminal_connector tests.test_git_connector tests.test_browser_connector tests.test_supervisor_browser_config`
    result: `63 tests` passed
  - `py_compile` passed for:
    - `src/openwukong/evaluation/accessibility_probe.py`
    - `tests/test_accessibility_probe.py`
  - live read-only probe:
    `python -m openwukong.evaluation.accessibility_probe --json --no-elements --max-windows 20 --max-elements 120`
    result: `window_count=15`, `total_elements=991`, `control_attempts=0`
- deterministic control route policy verified locally:
  - TDD red checks failed first because `openwukong.connectors.route_policy` and report-level `route_matrix` did not exist
  - focused route-policy + probe tests:
    `python -m unittest tests.test_control_route_policy tests.test_accessibility_probe`
    result: `13 tests` passed
  - related regression suite:
    `python -m unittest tests.test_control_route_policy tests.test_accessibility_probe tests.test_ai_monitor_helpers tests.test_l1_simulation_harness tests.test_l3_shadow_mode tests.test_workspace_identity tests.test_connector_registry tests.test_ide_connector_routing tests.test_task_parser_connector_hints tests.test_supervisor_identity_snapshot tests.test_terminal_connector tests.test_git_connector tests.test_browser_connector tests.test_supervisor_browser_config`
    result: `69 tests` passed
  - `py_compile` passed for:
    - `src/openwukong/connectors/route_policy.py`
    - `src/openwukong/connectors/__init__.py`
    - `src/openwukong/evaluation/accessibility_probe.py`
    - `tests/test_control_route_policy.py`
    - `tests/test_accessibility_probe.py`
  - live read-only probe after route matrix integration:
    `python -m openwukong.evaluation.accessibility_probe --json --no-elements --max-windows 20 --max-elements 120`
    result: `window_count=19`, `total_elements=1447`, `control_attempts=0`, blocked windows are `微信`, `Containers - Docker Desktop`, and `NVIDIA GeForce Overlay`
- route-policy safety gate verified locally:
  - TDD red checks failed first because:
    - `ConnectorManager.resolve_session_connector` did not accept `enforce_route_policy`
    - L3 shadow plans did not expose route-policy fields
    - real supervisor steer still called connector `send_message` for a blocked Weixin target
  - focused route-policy safety tests:
    `python -m unittest tests.test_supervisor_route_policy tests.test_connector_registry tests.test_l3_shadow_mode`
    result: `16 tests` passed
  - related regression suite:
    `python -m unittest tests.test_supervisor_route_policy tests.test_control_route_policy tests.test_accessibility_probe tests.test_ai_monitor_helpers tests.test_l1_simulation_harness tests.test_l3_shadow_mode tests.test_workspace_identity tests.test_connector_registry tests.test_ide_connector_routing tests.test_task_parser_connector_hints tests.test_supervisor_identity_snapshot tests.test_terminal_connector tests.test_git_connector tests.test_browser_connector tests.test_supervisor_browser_config`
    result: `73 tests` passed
  - `py_compile` passed for:
    - `src/openwukong/connectors/base.py`
    - `src/openwukong/connectors/registry.py`
    - `src/openwukong/connectors/route_policy.py`
    - `src/openwukong/evaluation/shadow.py`
    - `src/openwukong/supervisor/agent_supervisor.py`
    - `tests/test_connector_registry.py`
    - `tests/test_l3_shadow_mode.py`
    - `tests/test_supervisor_route_policy.py`
  - recorded L3 route-policy shadow:
    `python -m openwukong.evaluation.shadow tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --states tests\fixtures\evaluation\l3_goal_current_desktop_20260518.json --profile goal --json`
    result: `5/5 passed`, `control_attempts=0`
- terminal-native-session connector verified locally:
  - TDD red checks failed first because:
    - `TerminalCommandConnector` did not accept `command_timeout`
    - cwd changes from `Set-Location` did not persist between commands
    - terminal command payloads did not expose the route contract fields
  - focused terminal connector tests:
    `python -m unittest tests.test_terminal_connector`
    result: `6 tests` passed
  - related regression suite:
    `python -m unittest tests.test_supervisor_route_policy tests.test_control_route_policy tests.test_accessibility_probe tests.test_ai_monitor_helpers tests.test_l1_simulation_harness tests.test_l3_shadow_mode tests.test_workspace_identity tests.test_connector_registry tests.test_ide_connector_routing tests.test_task_parser_connector_hints tests.test_supervisor_identity_snapshot tests.test_terminal_connector tests.test_git_connector tests.test_browser_connector tests.test_supervisor_browser_config`
    result: `76 tests` passed
  - `py_compile` passed for:
    - `src/openwukong/connectors/terminal.py`
    - `tests/test_terminal_connector.py`

## Strategic Gaps

1. Execution is still too `UIA-heavy`
- connector routing now exists
- `TerminalCommandConnector`, `GitCommandConnector`, and `BrowserSessionConnector` now exist
- `TerminalCommandConnector` now has a first route-contract-aware managed terminal session implementation
- `CodexDesktopConnector`, `CursorIDEConnector`, and `CopilotIDEConnector` now exist
- `IDEExtensionConnector` now exists as the first deterministic IDE bridge route
- but the Codex/Cursor/Copilot specialized connectors are still `UIA-backed` unless a bridge URL is configured
- this is acceptable for fallback
- this is not enough for a durable copilot core
- 2026-05-19 accessibility probe confirms the practical boundary:
  UIA is useful for discovery, scoring, and fallback operation on many conventional surfaces, but it cannot be the universal primary route for high-precision app control

2. Browser support is still `HTTP-first`
- the current browser connector is a managed requests session
- it is good enough for deterministic navigation and transcript capture
- it is not a JS-capable interactive browser yet

3. Identity is stronger, but still not fully grounded
- `workspace / session / task / action` identity now exists
- workspace ids are now root-aware when a real path or URL is known
- configured and learned workspace roots can now be reused across pathless IDE states
- file/title-derived paths can now be lifted back to the workspace root via repo/project markers
- but IDE session roots are still not coming from native app semantics
- this still needs stronger per-app workspace-root extraction and session metadata binding

4. Recovery is still reactive
- L1 offline replay now exists
- there is still no L3 shadow-mode benchmark loop yet
- there is still no stable recovery benchmark loop yet

5. App-control routing has a first deterministic locator/action contract and a real steer safety gate
- `ControlRoutePlan` now maps:
  app family -> primary route -> locator source -> action primitive -> confidence threshold -> fallback path -> safety decision
- accessibility reports now embed this contract per window and as a route matrix
- `ConnectorManager` can enforce the route policy
- `AgentSupervisor._steer(..., dry_run=False)` now enforces it before connector `send_message`
- next step is to make L3/live fixtures cover more blocked and allowed app families, then deepen the concrete native connectors behind the allowed primary routes
- weak UIA apps such as Weixin, Docker Desktop, overlays, and terminal buffers still need specialized connectors, app extensions, native bridges, protocol APIs, or CLI/control-plane APIs before visual fallback

## Next 3 Priorities

Priority 1: Expand L1 simulation coverage
- add recorded fixtures for more route and mismatch cases
- same-workspace connector-preference and no-match cases now exist
- wrong-target and ambiguous-title cases now exist
- same-name different-path workspace cases now exist
- route quality summary now exists inside a single report
- cross-run trend reports now exist
- real fast-scan fixture now exists
- next add fixtures only where new L3 evidence exposes real misses

Priority 2: Build L3 shadow mode after L1 stabilizes
- first read-only L3 shadow harness now exists
- real fast-scan report has now been run and captured
- L3 goal-only expectation profile now exists
- dedicated L3 goal fixture now exists and passes in both recorded-state and live fast-scan mode
- repeated L3 goal-profile trend reporting now exists
- next refresh live goal fixtures from current observed states when desktop composition changes, then compare repeated trend results over time
- keep clicking, typing, connector reads, and command execution disabled

Priority 3: Use evaluation results to choose connector depth
- keep `connector-first` as baseline
- deepen native/plugin connectors only where L1/L3 evidence shows UIA is weak
- preserve `UIAIDEConnector` as fallback instead of primary long-term control
- current evidence:
  - browser must be present in read-only fast scan, now fixed
  - Antigravity currently routes through generic `uia-ide`, acceptable as fallback but not a Stage 1 primary connector
  - repeated live L3 on 2026-05-19 shows environment-presence drift must be separated from route-logic drift before moving to any control mode
  - Windows accessibility probe on 2026-05-19 shows UIA can identify many shells but does not provide universal, high-confidence input semantics across all app families
  - next connector design should prioritize IDE extension/native connector, browser DevTools/extension, terminal native session connector, and per-app bridges before relying on vision fallback
  - first route matrix now exists and is wired into `ConnectorManager`, L3 shadow plans, and real supervisor steer safety
  - next deepen primary connector families in this order:
    IDE bridge real extension command adapters, browser DOM action primitives beyond `Runtime.evaluate`, then app-specific native bridges for blocked IM/Electron surfaces
  - `terminal-native-session` has started with managed PowerShell subprocess sessions; full ConPTY is still reserved for interactive terminal-buffer control
  - `browser-devtools-or-extension` has started with DevTools target discovery and `Runtime.evaluate`; browser extension/native-host packaging is still future work
  - `ide-extension-connector` now supports local bridge state reads, diagnostics, allowlisted command execution, command capability discovery, configurable chat adapter dispatch, bridge-present L1/L3 fixture coverage, and a read-only capability capture CLI; real Cursor/Copilot/Codex adapter command mappings from installed products still require a running local bridge

## Working Rules For Future Turns

When a new conversation starts in this repo:
- first read this file
- identify the current stage and next priorities
- map the user's request onto the roadmap
- prefer changes that improve the current stage instead of adding scattered features
- after substantial progress, update this file before ending the turn

## Session Notes

2026-04-15
- product direction confirmed with the user:
  build an `AIOS Copilot` first, not a full AIOS shell
- the agreed execution order is:
  `Codex/Cursor/Copilot/Terminal/Git/Browser`
- connector-first execution has moved from planning into implementation
- current state:
  `AgentSupervisor -> ConnectorManager -> BrowserSessionConnector / GitCommandConnector / TerminalCommandConnector / CodexDesktopConnector / CursorIDEConnector / CopilotIDEConnector / UIAIDEConnector`
- terminal, git, and browser goals can now run without window matching when `connector_hint=terminal|git|browser`
- matched IDE goals can now auto-route to `codex / cursor / copilot` before falling back to generic `uia-ide`
- supervisor now carries a first-cut identity graph:
  `workspace -> session -> task -> action`
- current identity quality:
  stronger than raw title matching, now root-aware when path/url/root registry is available, but still limited by missing native IDE workspace-root introspection
- browser support is currently `managed HTTP session`, not a JS-capable browser automation layer
- this session deepened identity binding:
  - explicit and registered workspace roots now stay stable instead of collapsing to title-only names
  - nested file paths can now be normalized back to repo roots before binding
  - the next high-value step remains native workspace/session extraction for `Codex / Cursor / Copilot`

2026-05-17
- route decision updated with the user:
  L1 offline simulation first, no L2 sandbox for now, then L3 real-environment shadow mode if L1 is stable
- implemented first L1 harness:
  `fixture JSON -> offline state replay -> goal matching -> connector routing -> expectation report`
- baseline task fixture covers:
  `Codex / Cursor / Chrome / Terminal / Git`
- current L1 status:
  `5/5` baseline cases pass
- next high-value step:
  expand L1 fixtures with collision, ambiguity, no-match, wrong-target, and connector-preference cases before entering L3 shadow mode

2026-05-18
- continued L1 expansion:
  - added no-match expectation handling
  - added minimum match score checks
  - raised offline fuzzy acceptance threshold to reduce weak false-positive matches
  - expanded baseline fixture from `5/5` to `7/7`
- current verification:
  - L1 CLI fixture run: `7/7 passed`
  - related regression suite: `33 tests` passed
- next high-value step:
  add explicit wrong-target, ambiguous-title, low-score trend, and per-connector confusion-matrix style reporting before L3 shadow mode
- continued L1 pressure testing:
  - added `forbidden_matched_pid`
  - added connector confusion, low-score, and wrong-target summaries in report JSON
  - added wrong-target and ambiguous-title fixture cases
  - fixed exact project identity preference over alias substring matches
- current verification:
  - L1 CLI fixture run: `9/9 passed`
  - related regression suite: `36 tests` passed
- next high-value step:
  add same-name different-path workspace fixtures and route-quality trend reports before entering L3 shadow mode
- continued L1 route-quality work:
  - added per-connector route quality summary
  - added same-name different-path fixture
  - fixed title-derived nested file paths so they can resolve back to the named workspace component even without project markers
- current verification:
  - L1 CLI fixture run: `10/10 passed`
  - related regression suite: `38 tests` passed
- next high-value step:
  add cross-run trend reports and then decide whether L1 is stable enough to begin L3 shadow mode
- continued L1 trend-report work:
  - added `L1TrendReport` and `build_trend_report`
  - extended CLI with `--trend` for multi-fixture aggregation
  - verified duplicate fixture runs are counted separately for connector run counts
- current verification:
  - L1 CLI fixture run: `10/10 passed`
  - L1 trend CLI run over two baseline fixtures: `20/20 passed`, `run_count=2`
  - related regression suite: `41 tests` passed
- next high-value step:
  use the stable L1 harness to begin L3 shadow-mode design, while keeping real desktop control disabled
- started L3 shadow mode:
  - added read-only state observers and shadow report dataclasses
  - added API and CLI entry for producing route/action plans from observed state snapshots
  - reports explicitly keep `control_allowed=false` and `control_attempts=0`
  - risk classification now separates wrong target, unverifiable, low confidence, and generic expectation failures
  - fixed direct `git`/`terminal` L1 matching so live IDE windows cannot steal windowless connector routes
- current verification:
  - L1 CLI fixture run: `10/10 passed`
  - L1 trend CLI run over two baseline fixtures: `20/20 passed`, `run_count=2`
  - related regression suite: `45 tests` passed
- next high-value step:
  run L3 shadow mode against the real desktop fast-scan path, then convert any route misses into new L1 fixtures before considering control mode
- ran real L3 fast-scan:
  - observed 8 real windows after adding browser process support
  - report exports observed state metadata for fixture generation
  - comparison against the synthetic baseline produced `3/10 passed`; this is expected because synthetic baseline expectations include recorded PIDs and target windows absent from the real desktop
  - terminal/git remained windowless and safe
- converted real scan into L1 replay:
  - added `l1_real_fast_scan_20260518.json`
  - covers Codex, Edge, Cursor, and Antigravity fallback
- current verification:
  - L1 baseline fixture: `10/10 passed`
  - real fast-scan L1 fixture: `5/5 passed`
  - combined trend: `15/15 passed`
  - related regression suite: `50 tests` passed
- next high-value step:
  split L3 live-shadow evaluation into a goal-only expectation profile so real desktop runs are judged by connector/workspace/target confidence, not by synthetic fixture PIDs
- split L3 scoring profiles:
  - added `expectation_profile=exact|goal`
  - added CLI `--profile exact|goal`
  - `goal` profile ignores exact PID/window replay assertions but keeps connector/workspace and confidence checks
  - current live baseline under goal profile: `3/10 passed`, `7` low-confidence cases, `0` unverifiable cases, `control_attempts=0`
- current verification:
  - L1 baseline fixture: `10/10 passed`
  - real fast-scan L1 fixture: `5/5 passed`
  - combined trend: `15/15 passed`
  - related regression suite: `52 tests` passed
- next high-value step:
  create a dedicated L3 goal fixture for the actual current desktop targets, then use repeated goal-profile runs to decide where native connectors are required
- added dedicated L3 goal fixture:
  - no exact PID/window expectations
  - recorded-state replay path: `5/5 passed`
  - live fast-scan path: `5/5 passed`
  - live report: `logs/evaluation/l3_goal_current_desktop_live_20260518.json`
- current verification:
  - L1 baseline fixture: `10/10 passed`
  - real fast-scan L1 fixture: `5/5 passed`
  - dedicated L3 goal fixture: `5/5 passed`
  - combined trend: `15/15 passed`
  - related regression suite: `53 tests` passed
- next high-value step:
  add repeated-run trend reporting for L3 goal fixtures so connector drift and unstable window identity become visible before any control mode

2026-05-19
- added repeated-run L3 shadow trend reporting:
  - `--repeat` and `--interval` are now available on the shadow CLI
  - trend JSON exposes `mode=l3-shadow-trend`, `run_count`, `observed_state_counts`, connector summaries, risk cases, and unstable cases
  - unstable cases detect connector/window/workspace drift across runs
- current verification:
  - focused L3 tests: `9 tests` passed
  - related regression suite: `56 tests` passed
  - recorded-state L3 repeat: `10/10 passed`, `control_attempts=0`
  - current live L3 repeat: `2/10 passed`, `control_attempts=0`, because current desktop composition no longer matches all 2026-05-18 goal targets
- next high-value step:
  use the 2026-05-19 live trend report to decide whether to refresh a current-desktop goal fixture first, then run repeated L3 trend over a stable visible target set before designing any native/extension connector upgrade
- evaluated Windows accessibility as the next perception/control substrate:
  - implemented `accessibility_probe` to scan UIA-style accessible structure in read-only mode
  - live run produced `15` windows and `991` elements with `control_attempts=0`
  - result supports a hybrid route, not pure UIA and not pure vision:
    connector/native API first where available, UIA/MSAA/Win32 accessibility as semantic fallback, vision only as last-resort verification and locator aid
  - concrete next step is to convert capability reports into a deterministic route matrix for `IDE / Browser / Terminal / Git / Explorer / IM / Electron-CEF / Office`
- started implementing the deterministic route matrix:
  - added route policy dataclasses and app-family classification
  - accessibility probe now emits `control_route_plan` and `route_matrix`
  - current live matrix separates:
    deterministic connector-first targets (`browser`, `ide`, `terminal`),
    acceptable UIA semantic fallback targets (`system-shell`, some generic desktop surfaces),
    and blocked targets that require app-native bridges (`Weixin`, `Docker Desktop`, `NVIDIA Overlay`)
  - next high-value step is to wire this route matrix into L3 shadow planning and then into `ConnectorManager` as a safety gate before any real action path
- wired route matrix into the control path:
  - `ConnectorManager` route-policy enforcement exists
  - L3 shadow emits route-policy fields and blocks unsafe route-policy targets in the plan
  - supervisor real steer now blocks before connector `send_message` if the target's route is unsafe
  - next high-value step is to implement the first deeper deterministic connector behind an allowed primary route, starting with Terminal native session or Browser DevTools/extension
- deepened terminal-native-session:
  - added managed session cwd persistence, timeout handling, and explicit route contract payloads
  - this makes terminal control more deterministic without relying on UIA or visual terminal-buffer scraping
  - next high-value step is now `browser-devtools-or-extension`, replacing the current HTTP-only browser connector with a DOM/DevTools-capable connector path
- deepened browser-devtools-or-extension:
  - added `BrowserDevToolsClient` and `BrowserDevToolsTarget`
  - added optional `ConnectorTarget.debugger_url`
  - added DevTools target discovery, target selection, and `EVAL` -> `Runtime.evaluate` execution
  - kept HTTP session navigation as a fallback route instead of removing it
  - current verification:
    - browser connector suite: `9 tests` passed
    - related regression suite: `77 tests` passed
    - L1 baseline fixture: `10/10 passed`
    - updated connector files passed `py_compile`
  - next high-value step is now `ide-extension-connector`, then richer browser DOM action primitives such as semantic element query/input/click over DevTools or extension APIs
- started ide-extension-connector:
  - added `IDEExtensionConnector` and `IDEExtensionBridgeClient`
  - added optional `ConnectorTarget.ide_bridge_url`
  - added local JSON bridge contract endpoints:
    `/v1/ide/read` and `/v1/ide/send`
  - wired `connector_hint=ide-extension` into L1 as a direct windowless route
  - wired `ide_bridge_url` through supervisor goal loading, target construction, and snapshots
  - added VS Code/Cursor-compatible extension scaffold at `extensions/openwukong-vscode`
  - current verification:
    - focused IDE extension/config/L1 scaffold suite: `24 tests` passed
    - related regression suite: `92 tests` passed
    - L1 baseline fixture: `10/10 passed`
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is product-specific IDE command adapters for Cursor/Copilot/Codex and richer semantic IDE actions such as active file, selection, diagnostics, command execution, and chat-send integration
- deepened IDE semantic bridge actions:
  - added `IDE STATE` -> `/v1/ide/state`
  - added `IDE COMMAND <command_id>` -> `/v1/ide/command`
  - command arguments are parsed locally as JSON before bridge execution
  - VS Code scaffold now returns diagnostics from `vscode.languages.getDiagnostics`
  - VS Code scaffold now requires `openwukong.bridge.allowedCommands` before `vscode.commands.executeCommand`
  - current verification:
    - focused IDE extension connector/scaffold suite: `11 tests` passed
    - related regression suite: `95 tests` passed
    - L1 baseline fixture: `10/10 passed`
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is product-specific chat adapter configuration for Cursor/Copilot/Codex and an L1/L3 fixture for bridge-present IDE targets
- added IDE chat adapter capability discovery:
  - added `IDE CAPABILITIES` -> `/v1/ide/capabilities`
  - added `IDE CHAT <adapter_id>` -> `/v1/ide/chat`
  - extension config now exposes `openwukong.bridge.chatAdapters`
  - extension uses `vscode.commands.getCommands(true)` to report adapter availability instead of hardcoding private product command ids
  - current verification:
    - focused IDE extension connector/scaffold suite: `15 tests` passed
    - related regression suite: `99 tests` passed
    - L1 baseline fixture: `10/10 passed`
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is bridge-present L1/L3 fixtures plus real adapter command mapping documentation for the IDE products installed on the workstation
- added bridge-present IDE fixture coverage:
  - added L1 fixture `l1_ide_extension_bridge_present.json`
  - added L3 shadow fixture `l3_ide_extension_bridge_present.json`
  - added L3 route-policy mapping for windowless `ide-extension` plans so shadow reports still show `app_family=ide` and `primary_route_id=ide-extension-connector`
  - added `extensions/openwukong-vscode/README.md` documenting the adapter discovery and mapping workflow
  - current verification:
    - focused bridge-present tests: `3 tests` passed
    - related regression suite: `102 tests` passed
    - L1 baseline fixture: `10/10 passed`
    - L1 bridge-present fixture: `3/3 passed`
    - L1 combined trend: `13/13 passed`
    - L3 current desktop recorded goal fixture: `5/5 passed`
    - L3 bridge-present fixture: `3/3 passed`, `control_attempts=0`
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is to run the bridge in a real installed Cursor/VS Code-compatible product, capture `IDE CAPABILITIES`, and convert the discovered adapter command ids into a local mapping fixture without enabling uncontrolled execution
- added read-only IDE bridge capability capture:
  - added `python -m openwukong.evaluation.ide_bridge_capture`
  - the capture path only calls `/v1/ide/capabilities` and writes a safety-stamped report
  - active adapter `commandId` is emitted only when the bridge marks the adapter as available
  - unavailable candidates are preserved for review but not enabled
  - current verification:
    - focused capture tests: `3 tests` passed
    - related regression suite: `105 tests` passed
    - L1 bridge-present fixture: `3/3 passed`
    - L3 bridge-present fixture: `3/3 passed`, `control_attempts=0`
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - read-only live probe:
    - attempted `http://127.0.0.1:8787`
    - saved report to `logs/evaluation/ide_bridge_capabilities_20260519.json`
    - result was `ok=false` because no local bridge responded within timeout
    - no real adapter mapping was created because the data source was unavailable
  - next high-value step is to launch/install the VS Code-compatible bridge in the target IDE, run the same read-only capture, and only then create a local mapping fixture from real discovered command ids
- ran the IDE bridge in a real installed Cursor extension-development host:
  - added `onStartupFinished` activation to the VS Code-compatible extension manifest while keeping default `openwukong.bridge.autoStart=false`
  - launched Cursor 3.0.9 with an isolated temporary user-data/extensions profile and `openwukong.bridge.autoStart=true`
  - real read-only capture succeeded against `http://127.0.0.1:8787`
  - saved capability report to `logs/evaluation/ide_bridge_capabilities_20260519_cursor.json`
  - result: `ok=true`, `metadata.ide_name=Cursor`, `command_count=3094`, `control_attempts=0`
  - generated real adapter candidate report at `logs/evaluation/ide_bridge_adapter_candidates_cursor_20260519.json`
  - result: `candidate_count=270`; Cursor-related candidates include `composer.openComposer`, `composer.focusComposer`, `composer.openChatAsEditor`, `composer.newAgentChat`, `composer.startComposerPrompt`, `composer.sendToAgent`, `composerMode.chat`, `composerMode.agent`, `workbench.action.chat.open`, and `aichat.newchataction`
  - no active `IDE CHAT cursor` command was enabled yet because discovered command argument contracts have not been validated in a sacrificial control session
  - temporary Cursor bridge host processes were closed by filtering only the isolated `cursor-bridge-user-data` profile
  - current verification:
    - related regression suite: `105 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is to validate one Cursor chat command candidate and its argument contract in an isolated sacrificial workspace before enabling the adapter mapping for real control
- added and ran the IDE bridge command contract probe:
  - added `openwukong.evaluation.ide_bridge_contract_probe`
  - the probe executes allowlisted IDE commands only through the local JSON bridge and records before/after `/v1/ide/state`
  - each command variant is checked against a sacrificial workspace file hash so mutating commands are not promoted
  - tested variants are `no_args`, `string_message`, and `object_message`; only commands with a safe `object_message` contract are eligible for `IDE CHAT`
  - real Cursor isolated run used temporary `cursor-user-data`, temporary extension dir, port `8788`, and `logs/runtime/ide-contract-probe/workspace`
  - real probe report saved to `logs/evaluation/ide_bridge_contract_probe_cursor_20260519.json`
  - result: `composer.startComposerPrompt` is `callable`, accepted `object_message`, `workspace_changed=false`, `control_attempts=3`
  - probe report now emits `validated_mapping.cursor.commandId=composer.startComposerPrompt`
  - real `/v1/ide/chat` smoke test also passed through the Cursor adapter with `command_id=composer.startComposerPrompt`
  - chat smoke report saved to `logs/evaluation/ide_bridge_chat_smoke_cursor_20260519.json`
  - sacrificial workspace remained unchanged except for the original `README.md`
  - temporary Cursor bridge host processes were closed by filtering only the isolated `ide-contract-probe/cursor-user-data` profile
  - current verification:
    - focused contract probe tests: `5 tests` passed
    - related regression suite: `110 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is to wire the validated Cursor mapping into a controlled config path and then add a supervisor-level `IDE CHAT cursor` regression that remains isolated by default
- wired validated Cursor mapping into the controlled supervisor path:
  - `ide_bridge_contract_probe` can now build VS Code/Cursor settings from `validated_mapping`
  - CLI now supports `--settings-output`, `--settings-host`, `--settings-port`, and `--settings-no-autostart`
  - generated validated settings report at `logs/evaluation/ide_bridge_validated_cursor_settings_20260519.json`
  - settings contain:
    `openwukong.bridge.autoStart=true`,
    `openwukong.bridge.allowedCommands=[composer.startComposerPrompt]`,
    and `openwukong.bridge.chatAdapters.cursor.commandId=composer.startComposerPrompt`
  - added `TaskGoal.ide_chat_adapter`
  - `load_goals` now preserves `ide_chat_adapter`
  - supervisor steer now wraps plain retry text into `IDE CHAT <adapter>` when `connector_hint=ide-extension` and `ide_chat_adapter` is configured
  - added supervisor regression coverage so a plain retry message routes to `/v1/ide/chat` with `adapter_id=cursor`
  - ran real isolated Cursor supervisor smoke on port `8789` using a temporary profile and sacrificial workspace:
    `logs/runtime/ide-supervisor-chat-smoke/workspace`
  - real smoke report saved to `logs/evaluation/ide_supervisor_chat_smoke_cursor_20260519.json`
  - result: `retry_count=1`, `total_steers=1`, `active_connector=ide-extension`, action detail was `IDE CHAT cursor\n\nOPENWUKONG_SUPERVISOR_E2E_NO_EDIT`
  - sacrificial workspace remained unchanged except for the original `README.md`
  - temporary Cursor bridge host processes were closed by filtering only the isolated `ide-supervisor-chat-smoke/cursor-user-data` profile
  - current verification:
    - focused mapping/supervisor tests: `7 tests` passed
    - related regression suite: `111 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is to add an explicit E2E assertion that the message appears in Cursor's visible Composer input or conversation state, because current bridge-level success proves command dispatch, not UI text presence or model reply capture
- added and ran visible Cursor Composer E2E verification:
  - added `openwukong.evaluation.ide_visible_verification`
  - the verifier performs a read-only UIA scan for a unique token in target IDE window title, element `name`, and element `value_preview`
  - CLI supports process/title filters, polling timeout, output JSON, and JSON stdout
  - added deterministic tests for token hit detection, process/title filtering, and CLI JSON output
  - real isolated Cursor run used temporary profile `logs/runtime/ide-visible-e2e/cursor-user-data`, port `8790`, and sacrificial workspace `logs/runtime/ide-visible-e2e/workspace`
  - supervisor dispatched unique token `OPENWUKONG_VISIBLE_E2E_20260519_162445` through `IDE CHAT cursor`
  - dispatch report saved to `logs/evaluation/ide_visible_e2e_dispatch_cursor_20260519.json`
  - visible UIA token scan saved to `logs/evaluation/ide_visible_e2e_uia_cursor_20260519.json`
  - no-title-filter UIA token scan saved to `logs/evaluation/ide_visible_e2e_uia_cursor_no_title_filter_20260519.json`
  - accessibility dump saved to `logs/evaluation/ide_visible_e2e_accessibility_dump_20260519.json`
  - final E2E result saved to `logs/evaluation/ide_visible_e2e_result_cursor_20260519.json`
  - result: bridge dispatch succeeded (`retry_count=1`, `active_connector=ide-extension`), but visible token verification failed (`message_visible=false`, `hit_count=0`)
  - root cause evidence from UIA: isolated Cursor profile showed `Log In` and `Cursor’s AI features require you to be logged in`
  - conclusion: current validated Cursor bridge proves command dispatch, but not visible Composer message insertion or model reply capture in an unauthenticated isolated profile
  - temporary Cursor bridge host processes were closed by filtering only the isolated `ide-visible-e2e/cursor-user-data` profile
  - current verification:
    - focused visible verification tests: `3 tests` passed
    - related regression suite: `114 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value step is to rerun the visible E2E in an authenticated sacrificial Cursor profile or explicitly authorize use of the normal Cursor profile; without authentication, Cursor's AI surface blocks Composer message verification
- validated the currently open normal Cursor window supplied by the user:
  - target window: `config - PaoPaoHeZi - Cursor`, PID `50200`, normal profile `AppData\Roaming\Cursor`
  - read-only accessibility dump saved to `logs/evaluation/cursor_current_accessibility_dump_20260519.json`
  - UIA exposed the right-side Agent input as an `Edit` control with rect `[1747, 224, 2504, 281]`; placeholder text `Plan, Build, / for commands, @ for context` was visible in the tree
  - normal Cursor did not have the OpenWukong IDE bridge active on `http://127.0.0.1:8787`; report saved to `logs/evaluation/ide_bridge_capabilities_current_cursor_20260519.json`
  - non-submit `set_edit_text` probe returned injected=true but UIA did not read back the token, so ValuePattern is not reliable for Cursor Agent input; report saved to `logs/evaluation/cursor_current_uia_input_probe_20260519.json`
  - non-submit clipboard paste probe succeeded: token `OPENWUKONG_UIA_PASTE_PROBE_20260519_1637` appeared in both `Edit.value` and child `Text`, then was cleared with no token remaining; report saved to `logs/evaluation/cursor_current_uia_paste_probe_20260519.json`
  - post-clear read-only verifier confirmed the same token was no longer visible in Cursor UIA (`message_visible=false`, `hit_count=0`); report saved to `logs/evaluation/cursor_current_uia_paste_probe_clear_check_20260519.json`
  - conclusion: current architecture can precisely locate and write to the visible Cursor Agent input via UIA + keyboard/clipboard fallback, but direct bridge control is not available in this normal Cursor session until the bridge extension is installed/loaded
  - next high-value steps:
    - promote the successful non-submit UIA paste probe into a reusable guarded harness/test
    - add an explicit send/reply capture test only after deciding whether to use the normal Cursor profile or an authenticated sacrificial profile
    - install/load the IDE bridge in the target Cursor profile if connector-first control is required for production use
- enriched the public README presentation layer:
  - added the existing Wukong-vs-lobster visual assets from `assets/images/` to the top-level README
  - rewrote the README around the current AIOS Copilot north star, connector-first route policy, L1/L3 evaluation loop, and IDE bridge direction
  - validated that every README image reference resolves to a real local file
  - confirmed `assets/images/` was not tracked before this update, which explains why the remote GitHub README could not display those images
  - next concrete actions:
    - commit and push `README.md` plus `assets/images/*.png` so the remote GitHub page can render the visuals
    - keep `.agents/conversation_index.md` as local continuity context unless the repository owner decides to publish it
- started the formal Application Control Bus:
  - added `openwukong.control.application_bus` with:
    - `ApplicationControlBus`
    - `ControlTarget`
    - `ControlElementSnapshot`
    - `TextHit`
    - `InputActionOptions`
    - `InputActionReport`
    - `PywinautoUIABackend`
  - added `openwukong.evaluation.uia_input_probe`, a guarded non-submit CLI probe that writes a token, verifies it through UIA, and clears it
  - added `tests/test_application_control_bus.py` covering:
    - `set_text` fake-success fallback to clipboard paste
    - failed write verification
    - submit rejection unless explicitly allowed
    - clear-after fallback via `force_clear_input`
    - CLI JSON report output
  - real current-Cursor probe:
    - first reusable bus run saved to `logs/evaluation/application_control_bus_cursor_probe_20260519.json`
    - it correctly detected a cleanup bug: write verified, but clear verification failed with `clear_not_verified`
    - added failing regression for that case and fixed bus cleanup by adding verified force-clear fallback
    - fixed run saved to `logs/evaluation/application_control_bus_cursor_probe_fixed_20260519.json`
    - result: `ok=true`, `control_attempts=2`, `write_method=clipboard_paste`, `token_visible_after_write=true`, `token_visible_after_clear=false`, `submitted=false`
    - independent post-clear verifier saved to `logs/evaluation/application_control_bus_cursor_probe_fixed_clear_check_20260519.json`
    - result: `message_visible=false`, `hit_count=0`
  - stabilized test discovery by removing import-time `sys.stdout/sys.stderr = io.TextIOWrapper(...)` replacement from:
    - `tests/test_multi_window_ops.py`
    - `tests/test_feasibility.py`
    - `src/openwukong/monitor/ai_monitor.py`
    - `src/openwukong/planner/ollama_planner.py`
  - current verification:
    - focused Application Control Bus tests: `5 tests` passed
    - focused related suite: `19 tests` passed
    - full unittest discovery: `123 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value steps:
    - route `UIAIDEConnector` through `ApplicationControlBus` for non-bridge IDE fallback
    - add a guarded send/reply capture path behind explicit approval
    - add product-specific locator policies for Cursor, VS Code/Copilot, Chrome, Terminal, and Office surfaces
- evaluated and implemented background-safe control mode:
  - added `InputActionOptions.allow_foreground_interaction`
  - when `allow_foreground_interaction=false`, `ApplicationControlBus` does not call window focus, input focus, clipboard paste, keyboard typing, or force-clear
  - background-safe mode only allows semantic `set_text` style methods; if verification fails and foreground fallbacks are required, the report returns `foreground_required=true` and `error=foreground_required`
  - added report fields:
    - `foreground_interaction_allowed`
    - `foreground_required`
  - added `--background-safe` to `openwukong.evaluation.uia_input_probe`
  - added tests covering:
    - background mode never uses focus/clipboard/keyboard fallback
    - background mode can write and clear when `set_text` actually verifies
    - CLI background-safe JSON report
  - real current-Cursor background-safe probe:
    - saved to `logs/evaluation/application_control_bus_cursor_background_safe_probe_20260519.json`
    - result: `ok=false`, `control_attempts=1`, `foreground_interaction_allowed=false`, `foreground_required=true`, `error=foreground_required`
    - steps were only `input_found`, `set_text:executed`, `set_text:not_verified`, and `background_cleared_after`
    - conclusion: current Cursor Agent input cannot be controlled in the background through UIA `set_text`; it needs foreground fallback unless the IDE bridge/extension route is active
    - independent post-probe scan saved to `logs/evaluation/application_control_bus_cursor_background_safe_probe_clear_check_20260519.json`
    - result: `message_visible=false`, `hit_count=0`
  - current verification:
    - focused Application Control Bus suite: `8 tests` passed
    - focused related suite: `15 tests` passed
    - full unittest discovery: `126 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - route decision:
    - true background work should use connector/native APIs first: IDE bridge, Chrome DevTools/extension, Terminal ConPTY, Git CLI, Office COM/Office.js
    - UIA background semantic actions are useful when the target supports Value/Invoke/Toggle/Selection patterns and verification passes
    - UIA clipboard/keyboard fallback is foreground-required and must be treated as an explicit, schedulable interruption, not background automation
- added universal one-pass application control profiling:
  - added `openwukong.evaluation.universal_app_profile`
  - profiler is read-only and does not attempt control
  - it converts any visible window snapshot into:
    - `one_step_status`
    - `recommended_route`
    - `background_safe`
    - `foreground_required`
    - `blocked`
    - capability/risk/missing-capability summaries
  - one-step statuses:
    - `connector_required`
    - `background_semantic_ready`
    - `foreground_or_native_required`
    - `observe_only`
    - `blocked`
  - added CLI:
    - `python -m openwukong.evaluation.universal_app_profile --json`
    - supports `--max-windows`, `--max-elements`, and `--output`
  - added `tests/test_universal_app_profile.py` covering:
    - connector/background/foreground/blocked classification
    - native connector priority for browser, Office, and terminal app families
    - CLI JSON output with a static observer
  - live current-desktop read-only profile saved to:
    `logs/evaluation/universal_app_profile_current_desktop_20260519.json`
  - live result:
    - scanned `25` windows
    - `13` windows were `background_semantic_ready`
    - `8` windows were `connector_required`
    - `4` windows were `blocked`
    - `0` windows were classified as `foreground_or_native_required` in this run
  - route counts from the current desktop:
    - `uia-semantic`: `13`
    - `ide-extension-connector`: `5`
    - `terminal-native-session`: `2`
    - `browser-devtools-or-extension`: `1`
    - `app-native-bridge-required`: `2`
    - `no-deterministic-route`: `2`
  - conclusion:
    - there is no honest "one implementation controls all software precisely" route
    - there is now a one-pass capability layer that avoids one-by-one guessing by auto-classifying every visible app into deterministic routes
    - next precision work should prioritize connector packs for the `connector_required` categories, especially IDE, browser, terminal, and Office
  - current verification:
    - universal profile focused tests: `3 tests` passed
    - related focused suite: `19 tests` passed
    - full unittest discovery: `129 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
- added the first unified Control Fabric layer:
  - added `openwukong.control.fabric`
  - new abstractions:
    - `ControlIntent`
    - `ControlFabric`
    - `ControlDispatchReport`
  - the fabric is a plan-only policy entrypoint that turns any window snapshot plus a logical intent into one of:
    - `dispatch_connector`
    - `connector_required`
    - `dispatch_background_uia`
    - `dispatch_foreground_uia`
    - `foreground_or_native_required`
    - `blocked`
  - it keeps connector/native API first, semantic UIA second, foreground UIA only when explicitly allowed, and blocked routes when no deterministic route exists
  - added `openwukong.evaluation.control_fabric_profile`
    - CLI: `python -m openwukong.evaluation.control_fabric_profile --output <json>`
    - read-only, `plan_only`, `control_attempts=0`
    - can scan all visible windows in one pass and emit unified dispatch plans
  - added tests:
    - `tests/test_control_fabric.py`
    - `tests/test_control_fabric_profile.py`
  - live current-desktop Control Fabric profile saved to:
    `logs/evaluation/control_fabric_profile_current_desktop_20260519.json`
  - live result:
    - scanned `25` windows
    - `0` connector dispatches were ready in this run because no runtime connector was bound to the scanned windows
    - `8` windows required connector/native bridge routes
    - `13` windows were background UIA semantic candidates
    - `2` windows required foreground/native escalation
    - `2` windows were blocked
  - route counts:
    - `uia-semantic`: `13`
    - `ide-extension-connector`: `5`
    - `terminal-native-session`: `2`
    - `browser-devtools-or-extension`: `1`
    - `app-native-bridge-required`: `2`
    - `no-deterministic-route`: `2`
  - current verification:
    - Control Fabric focused tests: `6 tests` passed
    - related focused suite: `27 tests` passed
    - full unittest discovery: `135 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value steps:
    - bind installed connectors into `ControlFabric` runtime mode without enabling uncontrolled execution
    - add connector readiness probes for IDE bridge, browser DevTools, terminal managed session, and Office COM/Office.js
    - add an execution report layer behind explicit per-route safety gates while keeping profile mode read-only by default
- bound default connector runtime candidates into `ControlFabric` without enabling execution:
  - added `ControlFabric.with_default_connectors()`
  - added `default_connector_manager()`
  - default plan-only candidates now include:
    - `browser`
    - `git`
    - `terminal`
    - `ide-extension`
  - added session readiness separation:
    - browser route is ready only when a `debugger_url` is present for DevTools
    - IDE extension route is ready only when an `ide_bridge_url` is present
    - terminal/git routes are ready only when a real workspace directory is bound
    - otherwise the plan reports `connector_required`, not `dispatch_connector`
  - `ControlDispatchReport` now includes:
    - `installed_connector_ids`
    - `candidate_connector_ids`
    - `connector_ready`
  - `control_fabric_profile` now supports:
    - `--with-default-connectors`
  - profile summary now splits connector-required windows into:
    - `connector_missing`
    - `connector_installed_not_ready`
  - live current-desktop default-connector profile saved to:
    `logs/evaluation/control_fabric_profile_default_connectors_current_desktop_20260519.json`
  - live result:
    - scanned `22` windows in this run
    - `0` connector dispatches were session-ready
    - `6` windows had installed connector candidates but missing runtime session readiness
    - `0` connector-required windows lacked an installed connector candidate
    - `12` windows were background UIA semantic candidates
    - `2` windows required foreground/native escalation
    - `2` windows were blocked
    - candidate connector ids observed: `browser`, `ide-extension`
  - current verification:
    - Control Fabric/profile focused tests: `11 tests` passed
    - related connector/control suite: `55 tests` passed
    - full unittest discovery: `140 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value steps:
    - add real readiness probes that can discover `debugger_url`, `ide_bridge_url`, and workspace binding automatically
    - add read-only connector health checks for IDE bridge, browser DevTools, and terminal workspace sessions
    - only after that, add an explicit execution layer behind route-specific safety gates
- added read-only connector session discovery:
  - added `openwukong.control.session_discovery`
  - new abstractions:
    - `SessionDiscovery`
    - `SessionDiscoveryOptions`
    - `DiscoveredControlTarget`
  - discovery enriches windows/targets with connector session coordinates:
    - browser `debugger_url` from read-only Chrome DevTools `/json/version`
    - IDE `ide_bridge_url` from read-only `/v1/ide/capabilities`
    - terminal/git `workspace_path` only when the visible window identity matches a configured workspace root
  - discovery explicitly does not send any input/control command
  - `ControlFabric` dispatch reports now include `session_discovery` evidence
  - `control_fabric_profile` now supports:
    - `--discover-sessions`
    - `--workspace-root <path>`
  - fixed a CLI regression where `--workspace-root` used an immutable tuple default with `argparse append`
  - added tests:
    - `tests/test_session_discovery.py`
    - additional profile CLI coverage for `--discover-sessions` and `--workspace-root`
  - live current-desktop discovered-session profile saved to:
    `logs/evaluation/control_fabric_profile_discovered_sessions_current_desktop_20260519.json`
  - live result:
    - scanned `22` windows
    - `0` connector dispatches were session-ready
    - `6` windows still had installed connector candidates but missing runtime session readiness
    - `12` windows were background UIA semantic candidates
    - `2` windows required foreground/native escalation
    - `2` windows were blocked
    - `discovered_count=0`, meaning the current desktop did not expose Chrome/Edge DevTools, IDE bridge, or matching terminal workspace roots during this scan
  - current verification:
    - session discovery/profile focused tests: `7 tests` passed
    - related connector/control suite: `45 tests` passed
    - full unittest discovery: `146 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value steps:
    - add bridge/devtools launch helpers that can safely make selected sessions discoverable without taking over normal user apps
    - add read-only health reports for each discovered endpoint
    - then add opt-in route-specific execution gates
- 2026-05-21 added plan-only session readiness launch helpers:
  - added `openwukong.control.session_readiness_plan`
  - added `openwukong.evaluation.session_readiness_plan`
  - new abstractions:
    - `SessionReadinessPlanOptions`
    - `SessionReadinessAction`
    - `SessionReadinessPlanReport`
    - `build_session_readiness_plan`
  - helpers generate auditable plans only:
    - `mode=session-readiness-launch-plan`
    - `safety_mode=plan_only`
    - `control_allowed=false`
    - `control_attempts=0`
  - generated plan types:
    - isolated Browser DevTools launch command with `--remote-debugging-port` and isolated `--user-data-dir`
    - isolated VS Code-compatible IDE bridge launch command with extension development path and settings preview
    - terminal/git workspace binding plan with no foreground process launch
  - added CLI:
    - `python -m openwukong.evaluation.session_readiness_plan`
    - supports repeated `--route`, browser/IDE/workspace options, `--json`, and `--output`
  - generated current project readiness plan:
    `logs/evaluation/session_readiness_plan_current_project_20260521.json`
  - plan result:
    - `3` actions generated
    - browser readiness URL: `http://127.0.0.1:9222`
    - IDE bridge readiness URL: `http://127.0.0.1:8787`
    - terminal workspace root: `E:/ideaProjects/agent/openwukong`
    - all actions remain plan-only; no process was launched
  - current verification:
    - session readiness focused tests: `4 tests` passed
    - related connector/control suite: `49 tests` passed
    - full unittest discovery: `150 tests` passed
    - updated Python files passed `py_compile`
    - extension JavaScript passed `node --check`
  - next high-value steps:
    - add opt-in `--execute` for readiness helpers with strict isolated-profile guardrails
    - after launching a helper, immediately run `control_fabric_profile --discover-sessions` as the readiness assertion
    - keep normal user apps untouched unless the route explicitly targets an isolated helper session
- 2026-05-21 added opt-in session readiness execution and cleanup:
  - extended `openwukong.control.session_readiness_plan` with:
    - `SessionReadinessExecutionReport`
    - `SessionReadinessLaunchResult`
    - `SessionReadinessStopReport`
    - `SessionReadinessStopResult`
    - `SessionReadinessLauncher`
    - `SessionReadinessTerminator`
    - `execute_session_readiness_plan`
    - `stop_session_readiness_manifest`
  - execution remains explicit and guarded:
    - default CLI behavior is still plan-only
    - `--execute` only starts command actions that create an isolated helper profile
    - non-isolated command actions are rejected with `isolated_profile_required`
    - terminal/git workspace binding is recorded as `workspace_bound` without launching foreground software
    - execution reports keep `control_allowed=false` and `control_attempts=0`
  - added cleanup path:
    - execution writes a manifest under `logs/runtime/session-readiness/`
    - `--stop-manifest` terminates only manifest-recorded managed helper PIDs
    - Windows cleanup uses process-tree termination for isolated helper processes
    - unmanaged manifests and unmanaged launch records are rejected
  - added CLI support:
    - `--execute`
    - `--manifest`
    - `--stop-manifest`
    - execution/stop JSON output through the existing `--output` and `--json` paths
  - generated current project non-launching execution report:
    `logs/evaluation/session_readiness_execution_workspace_binding_20260521.json`
  - generated current project stop report for the same manifest:
    `logs/evaluation/session_readiness_stop_workspace_binding_20260521.json`
  - result:
    - terminal workspace binding: `workspace_bound`
    - git workspace binding: `workspace_bound`
    - `launch_attempts=0`
    - `stop_attempts=0`
    - no real browser/IDE helper process was started in this verification run
  - current verification:
    - session readiness focused tests: `10 tests` passed
    - related connector/control suite: `27 tests` passed
    - full unittest discovery: `156 tests` passed
    - updated Python files passed `py_compile`
  - next high-value steps:
    - run a real isolated Browser DevTools helper through `--execute`, then immediately verify `control_fabric_profile --discover-sessions`
    - run the same loop for the isolated IDE bridge helper once the target profile is ready
    - add connector health reports for every discovered endpoint before enabling any route-specific execution beyond helper readiness
- 2026-05-21 validated and fixed the real isolated Browser DevTools readiness loop:
  - first live attempt launched Chrome with a relative `--user-data-dir`:
    `logs/runtime/browser-devtools-profile-live-20260521`
  - Chrome showed a native error dialog:
    it could not create/read/write that data directory
  - cleanup worked:
    `--stop-manifest logs/runtime/session-readiness/browser-devtools-live-20260521.json`
    stopped PID `1728`
  - root cause:
    readiness helper argv used cwd-dependent relative profile paths and did not pre-create the helper profile directory before launching the external app
  - fixed `openwukong.control.session_readiness_plan`:
    - helper profile/cache paths now normalize to absolute paths
    - isolated `--user-data-dir` and `--extensions-dir` directories are created before `Popen`
    - execution manifest still records launched helper PIDs for cleanup
  - second live attempt launched isolated Chrome successfully:
    - executable: `C:\Program Files\Google\Chrome\Application\chrome.exe`
    - DevTools port: `9223`
    - PID: `63748`, then `77728` in the final fixed run
    - `/json/version` returned `Chrome/148.0.7778.168`
    - `/json/list` included the visible `about:blank` page target
  - discovered and fixed a higher-risk browser session discovery bug:
    - previous discovery treated any live browser DevTools endpoint as ready for every browser window
    - this incorrectly marked a normal `msedge.exe` window as ready for the isolated Chrome endpoint
    - `SessionDiscovery` now requires browser product ownership and visible target ownership:
      - Chrome endpoint only binds to Chrome windows
      - Edge endpoint only binds to Edge windows
      - DevTools `/json/list` target title or URL must match the visible window/resource URL
    - unmatched browser windows remain `connector_required`
  - final live Control Fabric profile:
    `logs/evaluation/control_fabric_profile_browser_devtools_discovered_live_fixed_20260521.json`
  - final result:
    - `connector_dispatch_ready=1`
    - isolated `chrome.exe` `about:blank - Google Chrome` was `dispatch_connector`
    - normal `msedge.exe` stayed `connector_required`
    - `control_allowed=false`
    - `control_attempts=0`
  - cleanup result:
    `logs/evaluation/session_readiness_stop_browser_devtools_live_fixed2_20260521.json`
    stopped PID `77728`
  - process check:
    - no `chrome.exe` process remained after cleanup
  - reusable skill created:
    `C:\Users\Zhangjinqian\.codex\skills\debug-connector-helper-readiness\SKILL.md`
  - current verification:
    - session discovery/readiness/control focused suite: `30 tests` passed
    - full unittest discovery: `159 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - next high-value steps:
    - add an explicit connector health report for discovered Browser DevTools endpoints
    - run a read-only Browser connector capability call against the isolated helper before enabling write/eval actions
    - run the same readiness ownership loop for the isolated IDE bridge helper
- 2026-05-21 added read-only Browser DevTools endpoint health reports:
  - added `openwukong.evaluation.browser_devtools_health`
  - new report mode:
    - `mode=browser-devtools-health`
    - `safety_mode=read_only`
    - `control_allowed=false`
    - `control_attempts=0`
  - health check behavior:
    - lists DevTools targets from a debugger endpoint
    - strictly matches target by resource URL or visible window title
    - evaluates only page identity:
      `document.title`, `location.href`, and `document.readyState`
    - reports `endpoint_ready`, `target_matched`, `evaluated_read_only`, target metadata, and page identity
    - unmatched targets are rejected with `devtools_target_not_matched`
  - added CLI:
    - `python -m openwukong.evaluation.browser_devtools_health`
    - supports `--debugger-url`, `--window-title`, `--resource-url`, `--json`, and `--output`
  - live isolated Chrome verification:
    - launched isolated Chrome helper on DevTools port `9223`
    - PID: `7652`
    - health report saved to:
      `logs/evaluation/browser_devtools_health_live_20260521.json`
    - result:
      - `ok=true`
      - `endpoint_ready=true`
      - `target_matched=true`
      - `evaluated_read_only=true`
      - target: `about:blank`
      - page identity: `href=about:blank`, `readyState=complete`
      - `control_attempts=0`
  - cleanup:
    - stopped helper through:
      `logs/runtime/session-readiness/browser-devtools-health-20260521.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_health_20260521.json`
    - `stop_attempts=1`
    - no `chrome.exe` process remained after cleanup
  - current verification:
    - browser DevTools health focused tests: `3 tests` passed
    - browser/session/control related suite: `31 tests` passed
    - full unittest discovery: `162 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - next high-value steps:
    - add an opt-in harmless DOM write-and-clear probe against the isolated helper
    - require the health report to pass before any Browser connector write/eval action is considered executable
    - then repeat the same readiness/health/cleanup loop for the IDE bridge helper
- 2026-05-21 added and live-validated isolated Browser DevTools DOM write-and-clear probe:
  - added `openwukong.evaluation.browser_devtools_dom_probe`
  - new report mode:
    - `mode=browser-devtools-dom-probe`
    - `safety_mode=isolated_dom_write_clear_probe`
    - `control_allowed=true` only after health target matching passes
    - `control_attempts=1` for the write/verify/clear/verify probe sequence
  - probe behavior:
    - runs `browser-devtools-health` first
    - refuses to write if DevTools target ownership is not proven
    - writes a token into a fixed hidden probe node:
      `#openwukong-dom-probe`
    - verifies the token is visible after write
    - removes only the probe-owned node
    - verifies the token is absent after clear
    - unmatched targets do not evaluate or mutate DOM
  - added CLI:
    - `python -m openwukong.evaluation.browser_devtools_dom_probe`
    - supports `--debugger-url`, `--window-title`, `--resource-url`, `--token`, `--json`, and `--output`
  - live isolated Chrome verification:
    - launched isolated Chrome helper on DevTools port `9223`
    - PID: `37836`
    - DOM probe report saved to:
      `logs/evaluation/browser_devtools_dom_probe_live_20260521.json`
    - result:
      - `ok=true`
      - `health_ok=true`
      - `write_verified=true`
      - `clear_verified=true`
      - `token_visible_after_write=true`
      - `token_visible_after_clear=false`
      - token: `OPENWUKONG_DOM_PROBE_20260521`
      - target: `about:blank`
  - cleanup:
    - stopped helper through:
      `logs/runtime/session-readiness/browser-devtools-dom-probe-20260521.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_dom_probe_20260521.json`
    - `stop_attempts=1`
    - no `chrome.exe` process remained after cleanup
  - current verification:
    - browser DOM probe focused tests: `3 tests` passed
    - browser/session/control related suite: `34 tests` passed
    - full unittest discovery: `165 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - current browser control status:
    - isolated Browser DevTools path now has a proven sequence:
      readiness launch -> endpoint ownership discovery -> read-only health -> DOM write -> verify -> clear -> verify -> manifest cleanup
    - normal user browsers are still not controlled unless they expose an owned DevTools/extension endpoint
  - next high-value steps:
    - promote Browser DevTools action execution behind a required passing health/probe gate
    - add explicit action reports for common browser operations:
      read page identity, inspect DOM, set form value, click allowed locator
    - run the same readiness/health/cleanup loop for the isolated IDE bridge helper
- 2026-05-21 promoted Browser DevTools into a health-gated action layer and live-validated search navigation:
  - added `openwukong.evaluation.browser_devtools_action`
  - added report mode:
    - `mode=browser-devtools-action`
    - `safety_mode=gated_browser_devtools_action`
    - every action first runs `browser-devtools-health`
    - unmatched targets are rejected before mutation with `control_attempts=0`
  - supported initial actions:
    - `navigate_url` through CDP `Page.navigate`
    - `read_page` through read-only DOM text extraction
    - `set_input_value` through selector-bound value set plus `input/change` events
    - `click_locator` through selector-bound DOM click
    - `extract_results` through selector-bound result extraction
  - extended `BrowserDevToolsClient` with generic `call_method(...)` so non-`Runtime.evaluate` CDP commands can be executed over the same audited target websocket
  - live isolated Chrome validation:
    - launched isolated Chrome helper on DevTools port `9231`
    - PID: `80984`
    - navigation action report saved to:
      `logs/evaluation/browser_devtools_action_navigate_search_live_20260521.json`
    - result:
      - `ok=true`
      - `health_ok=true`
      - `control_allowed=true`
      - `control_attempts=1`
      - action: `navigate_url`
      - navigated URL:
        `https://www.bing.com/search?q=OpenWukong%20AIOS%20Copilot`
      - post-action identity:
        title `OpenWukong AIOS Copilot - 搜索`
  - live read-page validation:
    - read action report saved to:
      `logs/evaluation/browser_devtools_action_read_search_live_20260521.json`
    - result:
      - `ok=true`
      - `readyState=complete`
      - `control_attempts=0`
      - extracted Bing search page text excerpt from the isolated helper tab
  - cleanup:
    - stopped helper through:
      `logs/runtime/session-readiness/browser-devtools-action-20260521.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_action_20260521.json`
    - `stop_attempts=1`
    - follow-up process filter found no Chrome process with:
      `browser-devtools-profile-action-20260521` or `--remote-debugging-port=9231`
  - current browser control status:
    - isolated Browser DevTools can now precisely open/search/read pages through deterministic CDP actions
    - this validates precise browser operation for owned/isolated DevTools endpoints
    - normal user browsers remain untouched unless an owned DevTools/extension endpoint is explicitly bound
  - current verification:
    - action focused tests: `4 tests` passed
    - generic CDP method focused tests: `2 tests` passed
    - browser/session/control related suite: `50 tests` passed
    - full unittest discovery: `170 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - next high-value steps:
    - add a browser form workflow evaluation fixture:
      navigate -> set input -> click/submit -> read/extract results
    - bind this action layer behind `ControlFabric` execution gates instead of keeping it as a standalone evaluation CLI
    - run the same readiness/health/action/cleanup loop for the isolated IDE bridge helper
- 2026-05-21 bound Browser DevTools actions behind explicit `ControlFabric` execution gates:
  - extended `openwukong.control.fabric` with:
    - `ControlExecutionReport`
    - `ControlFabric.execute(...)`
    - browser action fields on `ControlIntent`: `url`, `selector`, and `value`
  - execution remains opt-in:
    - `dispatch(...)` is still plan-only and keeps `control_allowed=false`
    - `execute(...)` refuses with `explicit_control_permission_required` unless `allow_control=True`
    - execution is blocked unless dispatch already selected:
      `dispatch_connector -> browser-devtools-or-extension -> browser`
    - session readiness still requires a `debugger_url`
  - added CLI:
    - `python -m openwukong.evaluation.control_fabric_execute`
    - supports explicit target coordinates plus `--allow-control`
    - writes the full Fabric dispatch report and nested Browser DevTools action report
  - live isolated Chrome validation through the unified Fabric execution entrypoint:
    - launched isolated Chrome helper on DevTools port `9232`
    - PID: `47592`
    - navigation report saved to:
      `logs/evaluation/control_fabric_execute_browser_search_live_20260521.json`
    - result:
      - `mode=control-fabric-execution`
      - `decision=executed`
      - `selected_route=browser-devtools-or-extension`
      - `selected_connector_id=browser`
      - nested dispatch report first confirmed `dispatch_connector`
      - nested browser action report then executed `navigate_url`
      - `control_attempts=1`
  - live read-page validation through the same Fabric entrypoint:
    - read report saved to:
      `logs/evaluation/control_fabric_execute_browser_read_live_20260521.json`
    - result:
      - `ok=true`
      - nested health check matched the owned DevTools target
      - `readyState=complete`
      - search page text excerpt was extracted from the isolated helper tab
      - `control_attempts=0`
  - cleanup:
    - stopped helper through:
      `logs/runtime/session-readiness/browser-devtools-fabric-execute-20260521.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_fabric_execute_20260521.json`
    - follow-up process filter found no Chrome process with:
      `browser-devtools-profile-fabric-execute-20260521` or `--remote-debugging-port=9232`
  - current verification:
    - Control Fabric execution focused tests: `3 tests` passed
    - Control Fabric execute CLI focused tests: `2 tests` passed
    - related control/browser/readiness suite: `36 tests` passed
    - full unittest discovery: `175 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - next high-value steps:
    - add a Fabric-level browser form workflow fixture:
      navigate -> set input -> click/submit -> read/extract results
    - add session discovery integration to `control_fabric_execute` so the CLI can resolve debugger URLs from visible windows before executing
    - repeat the same Fabric execution gate design for the isolated IDE bridge helper
- 2026-05-21 added and live-validated a Fabric-level browser form workflow:
  - added `openwukong.evaluation.control_fabric_browser_workflow`
  - new report mode:
    - `mode=control-fabric-browser-workflow`
    - `safety_mode=explicit_control_gate_sequence`
    - every step calls `ControlFabric.execute(...)`, so each step first passes Fabric dispatch gating and then Browser DevTools health gating
    - each step stores the full nested Fabric execution report and Browser DevTools action report
  - added workflow primitives:
    - `BrowserWorkflowStep`
    - `BrowserWorkflowStepReport`
    - `BrowserWorkflowReport`
    - `run_control_fabric_browser_workflow(...)`
  - added CLI:
    - `python -m openwukong.evaluation.control_fabric_browser_workflow`
    - fixed browser form workflow schema:
      `navigate_url -> set_input_value -> submit_form -> read_page -> extract_results`
    - supports `--start-url`, `--input-selector`, `--query`, `--submit-selector`, `--results-selector`, `--settle-seconds`, and `--allow-control`
  - strengthened Browser DevTools action primitives:
    - added `submit_form`
    - `submit_form` finds the selector's nearest `form` and uses `requestSubmit(...)` when available
    - `extract_results` is now treated as read-only for control-attempt accounting
  - discovered and fixed a real workflow issue:
    - first live form workflow used `click_locator` and returned `ok=true`, but only extracted Bing home links because the click target did not actually submit the search
    - replaced button-click submission with semantic `submit_form`
    - added wait-after-submit coverage so the workflow does not read/extract before a form navigation has had time to settle
  - live isolated Chrome validation:
    - launched isolated Chrome helper on DevTools port `9233`
    - PID: `25260`
    - final workflow report saved to:
      `logs/evaluation/control_fabric_browser_workflow_bing_submit_settled_live_20260521.json`
    - result:
      - `ok=true`
      - `step_count=5`
      - `control_attempts=3`
      - steps:
        `navigate_url`, `set_input_value`, `submit_form`, `read_page`, `extract_results`
      - `submit_form` navigated to:
        `https://www.bing.com/search?q=OpenWukong+Control+Fabric+workflow&form=QBLH`
      - `read_page` extracted real Bing search result text containing:
        `OpenWuKong — AI Desktop Assistant | Rust-Powered, Cross-Platform`
      - `extract_results` extracted real result-page links from the owned isolated tab
  - cleanup:
    - stopped helper through:
      `logs/runtime/session-readiness/browser-devtools-workflow-20260521.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_workflow_20260521.json`
    - follow-up process filter found no Chrome process with:
      `browser-devtools-profile-workflow-20260521` or `--remote-debugging-port=9233`
  - current verification:
    - browser workflow focused tests: `4 tests` passed
    - Browser DevTools action plus Fabric execution focused tests: `10 tests` passed
    - related control/browser/readiness suite: `51 tests` passed
    - full unittest discovery: `180 tests` passed
    - updated Python files passed `py_compile`
    - VS Code extension JavaScript passed `node --check`
  - next high-value steps:
    - add session discovery integration to `control_fabric_execute` and `control_fabric_browser_workflow`
    - add workflow result quality assertions so search workflows can require expected URL/query/text/link evidence
    - repeat the same Fabric execution gate design for the isolated IDE bridge helper
- 2026-05-21 added workflow result quality assertions and hardened helper cleanup:
  - extended `openwukong.evaluation.control_fabric_browser_workflow` with:
    - `BrowserWorkflowExpectations`
    - report-level `expectations`, `quality_checks`, and `quality_summary`
    - quality evidence aggregation from final URL, page identity, read-page text excerpts, and extracted result items
  - added CLI quality flags:
    - `--expect-url-contains`
    - `--expect-text-contains`
    - `--expect-link-href-contains`
    - `--expect-link-text-contains`
    - `--min-result-count`
  - workflow semantics are now stricter:
    - all Fabric-gated steps can pass, but the workflow still returns `ok=false` with `workflow_quality_assertion_failed` if expected URL/text/link/result-count evidence is missing
    - this prevents the earlier false-positive class where a browser workflow completed actions without proving the business result
  - live isolated Chrome validation:
    - launched isolated Chrome helper on DevTools port `9235`
    - health report saved to:
      `logs/evaluation/browser_devtools_health_workflow_quality_rerun_20260521_9235.json`
    - strong workflow report saved to:
      `logs/evaluation/control_fabric_browser_workflow_quality_bing_strong_live_20260521.json`
    - result:
      - `ok=true`
      - `step_count=5`
      - `control_attempts=3`
      - final URL:
        `https://www.bing.com/search?q=OpenWukong+Control+Fabric+workflow&form=QBLH`
      - quality checks:
        `4/4 passed`
      - asserted evidence included:
        `q=OpenWukong+Control+Fabric+workflow`, `AI Desktop Assistant`, `openwukong.app`, and at least one extracted result item
  - discovered and fixed a real helper cleanup gap:
    - manifest stop could terminate the originally recorded launcher PID while leaving Chrome child/main processes alive on the same managed profile/port
    - a repeated stop could also fail before argv-based residual cleanup when the recorded PID was already gone
  - fixed `openwukong.control.session_readiness_plan`:
    - stop now kills the recorded PID tree, then also scans and terminates manifest-owned residual processes by managed argv tokens such as `--user-data-dir`, `--extensions-dir`, and `--remote-debugging-port`
    - stop is now idempotent for already-exited recorded PIDs, while still rejecting unmanaged manifests and unmanaged launch records
    - PowerShell residual scanning now passes the script through subprocess `input` without the invalid `stdin` conflict
  - cleanup verification:
    - stopped the 9235 helper through:
      `logs/runtime/session-readiness/browser-devtools-workflow-quality-rerun-20260521-9235.json`
    - stop report saved to:
      `logs/evaluation/session_readiness_stop_browser_devtools_workflow_quality_rerun_20260521_9235.json`
    - follow-up process filter found no Chrome process with:
      `browser-devtools-profile-workflow-quality-rerun-20260521-9235` or `--remote-debugging-port=9235`
    - also cleaned the older `browser-devtools-quality-20260521` manifest residual on port `9234`
  - current verification:
    - session readiness focused tests: `14 tests` passed
    - related browser/control/readiness suite: `57 tests` passed
    - full unittest discovery: `186 tests` passed
    - updated Python files passed `compileall`
    - VS Code extension JavaScript passed `node --check`
    - note: full discovery still prints the existing Twine upload Unicode traceback from packaging test output, but the test suite exits `0` and reports `OK`
  - next high-value steps:
    - add session discovery integration to `control_fabric_execute` and `control_fabric_browser_workflow` so debugger URLs can be resolved from owned discovered sessions
    - tighten browser result extraction selectors so result-item assertions target organic results instead of header/navigation links
    - repeat the Fabric execution gate and cleanup loop for the isolated IDE bridge helper
- 2026-05-22 integrated session discovery into Fabric browser execution and workflow CLIs:
  - extended `openwukong.evaluation.control_fabric_execute` with:
    - injectable `session_discovery`
    - `--discover-sessions`
    - `--browser-debug-port`
    - `--discovery-timeout`
  - extended `openwukong.evaluation.control_fabric_browser_workflow` with:
    - optional `--debugger-url`
    - injectable `session_discovery`
    - `--discover-sessions`
    - `--browser-debug-port`
    - `--discovery-timeout`
    - first-step discovery evidence preserved in the nested Fabric dispatch report
    - discovered `debugger_url` carried forward across workflow steps through the connector target
  - added regression coverage:
    - `control_fabric_execute` can execute a browser action after discovering the DevTools endpoint
    - `control_fabric_browser_workflow` can run without a manually supplied debugger URL when discovery is enabled
  - live isolated Chrome validation:
    - launched isolated helper on DevTools port `9237`
    - workflow command did not pass `--debugger-url`
    - discovery found `http://127.0.0.1:9237` from `about:blank`
    - Fabric workflow completed:
      `navigate_url -> set_input_value -> submit_form -> read_page -> extract_results`
    - report saved to:
      `logs/evaluation/control_fabric_browser_workflow_discovered_local_live_20260522.json`
    - result:
      - `ok=true`
      - `step_count=5`
      - `control_attempts=3`
      - `quality_checks=4/4 passed`
      - final target retained `debugger_url=http://127.0.0.1:9237`
  - attempted external Bing validation on port `9236`:
    - first step proved discovery worked and used `http://127.0.0.1:9236`
    - Bing navigation failed with `net::ERR_CONNECTION_CLOSED`, so the workflow correctly stopped instead of acting on a mismatched `chrome-error://chromewebdata/` target
  - cleanup:
    - stopped helpers through manifests:
      `logs/runtime/session-readiness/browser-devtools-discovery-workflow-20260522-9236.json`
      and
      `logs/runtime/session-readiness/browser-devtools-discovery-workflow-20260522-9237.json`
    - residual process scan found no Chrome process with the 9236/9237 profiles or remote debugging ports
  - current verification:
    - session discovery focused CLI tests: `2 tests` passed
    - related control/browser/readiness suite: `55 tests` passed
    - full unittest discovery: `188 tests` passed
    - updated Python files passed `compileall`
    - VS Code extension JavaScript passed `node --check`
    - note: full discovery still prints the existing Twine upload Unicode traceback from packaging test output, but the test suite exits `0` and reports `OK`
  - next high-value steps:
    - promote the same discovery pattern to the IDE bridge helper path
    - add endpoint ownership labels so discovered sessions can be tied to a managed manifest/session id, not only port and title
    - design the unified background-safe session registry above browser/IDE/terminal/git connectors
- 2026-05-22 started Stage 1 unified session registry:
  - added `openwukong.control.session_registry`
  - new registry primitives:
    - `SessionCapability`
    - `ControlSession`
    - `SessionRegistry`
    - `SessionRegistrySnapshot`
    - `build_session_registry_snapshot(...)`
  - registry behavior:
    - normalizes connector targets, discovered targets, and UIA-style window snapshots into one `ControlSession` shape
    - reuses the existing deterministic route policy to classify `app_family` and `preferred_route`
    - records route-specific capabilities such as:
      `browser_devtools`, `dom_locator`, `ide_bridge`, `terminal_native_session`, `git_cli`, `office_object_model`, `uia_semantic`, and `uia_structural`
    - exposes unified `capability_ids`, `action_ids`, `background_safe`, target coordinates, route plan, and session discovery evidence
    - merges repeated discoveries for the same visible/session identity instead of duplicating sessions
    - can feed a registered `ControlSession` back into `ControlFabric.dispatch(...)`
  - package export:
    - exported registry primitives from `openwukong.control`
  - TDD coverage added:
    - browser DevTools session registration
    - repeated discovery merge
    - repeated capability evidence dedupe
    - terminal workspace command session registration
    - UIA semantic generic window registration
    - mixed-target snapshot counts
    - package-level exports
    - ControlFabric dispatch integration from a registered session
  - current verification:
    - session registry focused tests: `8 tests` passed
    - related control/discovery/browser workflow suite: `37 tests` passed
    - full unittest discovery: `196 tests` passed
    - updated Python files passed `compileall`
    - note: full discovery still prints the existing Twine upload Unicode traceback from packaging test output, but the test suite exits `0` and reports `OK`
  - next high-value steps:
    - add a read-only registry report CLI over live/recorded window observations
    - add endpoint ownership labels from readiness manifests into registry sessions
    - start `Command Intelligence Layer` as the PowerShell/CLI execution substrate under the registry
- 2026-05-22 added read-only Session Registry report CLI:
  - added `openwukong.evaluation.session_registry_report`
  - new report mode:
    - `mode=session-registry-report`
    - `safety_mode=read_only`
    - `control_allowed=false`
    - `control_attempts=0`
  - CLI behavior:
    - supports live read-only fast desktop scan when no state file is provided
    - supports recorded JSON inputs through `--states`
    - accepts `states`, `observed_states`, or `windows` arrays
    - supports `--discover-sessions` before registry registration
    - supports discovery options:
      `--browser-debug-port`, `--ide-bridge-url`, `--workspace-root`, and `--discovery-timeout`
    - supports `--output` and `--json`
  - added report primitives:
    - `StaticRegistryObserver`
    - `SessionRegistryReport`
    - `run_session_registry_report(...)`
    - `load_registry_states(...)`
  - TDD coverage added:
    - static observer read-only report
    - JSON stdout plus output file write
    - recorded state file loading
    - session discovery before registry registration
  - command-line validation:
    - recorded fixture report saved to:
      `logs/evaluation/session_registry_report_recorded_20260522.json`
      with `observed_state_count=8`, `session_count=8`, and `control_attempts=0`
    - live fast-scan report saved to:
      `logs/evaluation/session_registry_report_live_fast_scan_20260522.json`
      with `observed=2`, `sessions=2`, and `control_attempts=0`
  - current verification:
    - session registry report focused tests: `4 tests` passed
    - related registry/discovery/profile/shadow suite: `33 tests` passed
    - full unittest discovery: `200 tests` passed
    - updated Python files passed `compileall`
    - note: full discovery still prints the existing Twine upload Unicode traceback from packaging test output, but the test suite exits `0` and reports `OK`
  - next high-value steps:
    - add endpoint ownership labels from readiness manifests into registry sessions
    - start `Command Intelligence Layer` as the PowerShell/CLI execution substrate under the registry
    - integrate registry report output into ControlFabric profile so route planning and session inventory share one source of truth
- 2026-05-25 added readiness-manifest ownership labels to session registry:
  - added `openwukong.control.session_ownership`
  - new ownership primitives:
    - `SessionOwnership`
    - `SessionOwnershipIndex`
    - `load_readiness_manifest_ownership(...)`
    - `build_ownership_index(...)`
  - ownership behavior:
    - loads only `session-readiness-execution` manifests with `isolated_helper_launch` safety mode
    - binds browser helpers by exact DevTools endpoint
    - binds IDE helpers by exact bridge endpoint plus workspace root when present
    - binds terminal/git workspace sessions by workspace root
    - marks isolated helper launches as `cleanup_ready=true`
    - marks workspace-bound terminal/git ownership as non-cleanup ownership evidence
  - registry integration:
    - `SessionRegistry` accepts an optional ownership index
    - `ControlSession` now includes an `ownership` object in snapshots
    - `SessionRegistrySnapshot` now exposes `ownership_counts`
  - report CLI integration:
    - added `--readiness-manifest`
    - added `--readiness-manifest-dir`
    - report output now attaches ownership metadata to matching sessions
  - package export:
    - exported ownership primitives from `openwukong.control`
  - TDD coverage added:
    - browser readiness manifest ownership loading
    - exact browser endpoint ownership matching
    - IDE endpoint and workspace ownership matching
    - workspace-bound terminal ownership matching
    - registry ownership attachment
    - report CLI manifest ownership binding
    - package-level ownership exports
  - current verification:
    - focused ownership/registry/report tests: `19 tests` passed
    - expanded control/readiness/discovery/browser workflow suite: `54 tests` passed
    - updated Python files passed `compileall`
    - temporary end-to-end CLI validation produced `ownership_counts={"owned":1,"unowned":0}`
  - next high-value steps:
    - add an execution ownership gate so background actions can require `owned=true` before mutation
    - start the `Command Intelligence Layer` for PowerShell/CLI-backed operations under the same ownership model
    - attach ownership-aware cleanup/stop commands to registry/report output
- 2026-05-25 researched public Codex computer-operation architecture signals:
  - public OpenAI materials indicate Codex is not one universal UI-control primitive:
    - local Codex CLI/IDE/app paths execute file and command work through a local harness with approvals and sandboxing
    - Codex cloud runs tasks in isolated repo/container environments
    - Codex app computer use is described as seeing/clicking/typing with its own cursor, initially on macOS
    - OpenAI Computer Use API exposes a screenshot/action loop for click/type/scroll/wait/drag/screenshot
    - Windows Codex sandbox uses OS-enforced command execution boundaries, including setup binary, command-runner binary, restricted tokens, synthetic SIDs, sandbox users, ACLs, and firewall rules
    - Codex app/CLI/IDE also uses worktrees, skills, plugins, MCP, browser, terminals, automations, and review queues
  - architecture implication for OpenWukong:
    - keep connector/native API first, not vision first
    - add a Windows command-runner/sandbox layer before broad autonomous execution
    - require ownership/session gating before mutation
    - treat UIA/MSAA/Computer Use vision as observation and fallback layers
    - use isolated app/helper sessions to avoid stealing user focus where possible
    - package repeatable workflows as skills/plugins instead of hardcoding one-off app hacks
  - next high-value steps:
    - design and implement the execution ownership gate
    - design the Windows Command Intelligence Layer around a dedicated runner/broker
    - evaluate feasibility of a separate background control surface for Windows apps: owned helper process, virtual desktop/RDP/VM, or app-specific connector
- 2026-05-25 implemented execution ownership gate:
  - updated `openwukong.control.fabric`:
    - `ControlFabric` accepts an optional `SessionOwnershipIndex`
    - `ControlFabric` can require owned sessions for execution with `require_owned_session_for_execution`
    - `ControlDispatchReport` now includes ownership metadata
    - `ControlExecutionReport` now includes `ownership_required` and ownership metadata
    - ready connector actions are blocked with `owned_session_required` before runner invocation when ownership is required but missing
  - updated execution CLIs:
    - `openwukong.evaluation.control_fabric_execute`
    - `openwukong.evaluation.control_fabric_browser_workflow`
    - both accept `--readiness-manifest`, `--readiness-manifest-dir`, and `--require-owned-session`
    - passing a readiness manifest automatically enables the ownership gate for that run
  - TDD coverage added:
    - ready browser action is blocked when owned session is required and no ownership matches
    - browser action executes when ownership matches through `SessionOwnershipIndex`
    - execution CLI blocks with `--require-owned-session`
    - execution CLI binds readiness manifest ownership before control
    - browser workflow CLI binds readiness manifest ownership before multi-step control
  - current verification:
    - focused new ownership-gate tests: `5 tests` passed
    - related fabric/ownership/registry/report suite: `47 tests` passed
    - expanded control/readiness/discovery/browser suite: `82 tests` passed
    - full unittest discovery: `212 tests` passed
    - updated Python files passed `compileall`
    - direct CLI no-ownership validation returned `owned_session_required` with `control_attempts=0`
  - next high-value steps:
    - start the Windows `Command Intelligence Layer` under this ownership gate
    - design a dedicated command runner/broker with audit logs, cwd/env policy, timeout, and process cleanup
    - extend ownership-aware stop/cleanup reports so managed browser/IDE/terminal helpers can be terminated cleanly
- 2026-05-25 implemented Command Intelligence Layer v1:
  - added `openwukong.control.command_runner`
  - new command primitives:
    - `CommandExecutionPolicy`
    - `CommandExecutionRequest`
    - `CommandExecutionReport`
    - `CommandRunner`
  - runner behavior:
    - executes explicit argv only, never `shell=True`
    - enforces workspace/cwd boundary before starting a process
    - supports timeout with `timeout` reports and `control_attempts=1`
    - blocks before process start with `owned_session_required` when ownership is required but missing
    - writes append-only JSONL audit records with request/result metadata
    - captures stdout/stderr with bounded output in reports
  - added `openwukong.evaluation.command_intelligence_execute`
    - supports `--workspace-path`, `--cwd`, `--timeout`, `--audit-log`
    - supports `--readiness-manifest`, `--readiness-manifest-dir`, and `--require-owned-session`
    - passing a readiness manifest automatically enables the ownership gate
    - uses argv remainder after `--`, so command execution is structured rather than shell-string based
  - package export:
    - exported command runner primitives from `openwukong.control`
  - TDD coverage added:
    - argv execution in workspace
    - audit JSONL creation
    - cwd outside workspace preflight block
    - timeout reporting
    - ownership-required preflight block
    - owned workspace command execution
    - CLI readiness manifest ownership binding
    - CLI ownership-required block
    - package-level command runner exports
  - current verification:
    - focused Command Intelligence tests: `8 tests` passed
    - command/terminal/git/ownership/fabric related suite: `41 tests` passed
    - expanded control/command/readiness/discovery/browser suite: `88 tests` passed
    - full unittest discovery: `220 tests` passed
    - updated Python files passed `compileall`
    - direct CLI validation:
      - no ownership manifest returned `owned_session_required` with `control_attempts=0`
      - owned workspace manifest executed `owned-command-cli` and wrote one audit record
  - next high-value steps:
    - migrate `TerminalCommandConnector` and `GitCommandConnector` onto `CommandRunner`
    - add command policy profiles for read-only, workspace-write, network-enabled, and elevated-forbidden modes
    - add cleanup-aware long-running process tracking before supporting persistent terminal sessions
- 2026-05-25 migrated terminal/git connectors onto CommandRunner:
  - updated `openwukong.connectors.terminal.TerminalCommandConnector`
    - now executes PowerShell argv through `CommandRunner`
    - preserves existing managed PowerShell subprocess contract
    - preserves transcript and session cwd marker behavior
    - adds optional `audit_log_path`
    - payload now includes `runner_mode=command-intelligence-execution` and `request_id`
  - updated `openwukong.connectors.git.GitCommandConnector`
    - now executes `git` argv through `CommandRunner`
    - preserves git command normalization and transcript behavior
    - adds optional `command_timeout` and `audit_log_path`
    - payload now includes `runner_mode=command-intelligence-execution`, `request_id`, and `timeout_sec`
  - fixed migration regressions:
    - removed a circular import created by `command_runner -> session_ownership -> connectors.__init__ -> git -> command_runner`
    - made `session_ownership` lazily import `ConnectorTarget`
    - fixed Windows short-path versus long-path workspace containment checks for terminal cwd updates
  - TDD coverage added:
    - terminal connector writes CommandRunner audit JSONL and exposes runner metadata
    - git connector writes CommandRunner audit JSONL and exposes runner metadata
    - existing terminal cwd persistence and timeout tests continue to pass through CommandRunner
  - current verification:
    - new focused migration tests: `2 tests` passed after RED/GREEN
    - terminal/git connector suite: `11 tests` passed
    - command/terminal/git/ownership/fabric suite: `34 tests` passed
    - expanded control/command/readiness/discovery/browser suite: `90 tests` passed
    - full unittest discovery: `222 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add command policy profiles for read-only, workspace-write, network-enabled, and elevated-forbidden modes
    - add long-running process tracking and cleanup reports for persistent terminal sessions
    - wire ownership-aware command execution into higher-level ControlFabric connector execution paths
- 2026-05-25 added command policy profiles and Fabric connector execution:
  - updated `openwukong.control.command_runner`
    - added `build_command_execution_policy(...)`
    - added policy `profile_id`
    - added explicit request `effects`
    - profiles:
      - `read-only`: allows `read`
      - `workspace-write`: allows `read`, `workspace_write`
      - `network-enabled`: allows `read`, `workspace_write`, `network`
    - `elevated` is forbidden for all profiles by default
    - disallowed effects block before process start with `control_attempts=0`
  - updated `openwukong.evaluation.command_intelligence_execute`
    - added `--profile`
    - added repeatable `--effect`
  - updated `openwukong.control.fabric`
    - `ControlFabric.execute(...)` now executes non-browser deterministic connectors through `send_message(...)`
    - browser DevTools still uses the specialized browser action runner
    - terminal/git/IDE-style connector execution now shares explicit-control and ownership gates
    - connector action results are normalized into `ControlExecutionReport.action_report`
  - TDD coverage added:
    - read-only profile blocks declared workspace writes
    - workspace-write profile allows declared workspace writes
    - elevated effect is blocked under network-enabled profile
    - CLI `--profile read-only --effect workspace_write` blocks before process start
    - Fabric executes ready terminal connector through generic connector path
    - Fabric blocks terminal connector before invocation when ownership is required but missing
  - current verification:
    - focused RED/GREEN tests: `6 tests` passed
    - command/fabric/connector suite: `53 tests` passed
    - expanded control/command/readiness/discovery/browser suite: `107 tests` passed
    - full unittest discovery: `228 tests` passed
    - updated Python files passed `compileall`
    - direct CLI validation:
      - `read-only + workspace_write` returned `effect_not_allowed:workspace_write` with `control_attempts=0`
      - `workspace-write + workspace_write` executed and printed `workspace-write-ok`
  - next high-value steps:
    - add long-running process tracking and cleanup reports for persistent terminal sessions
    - add ownership-aware execution tests for real `TerminalCommandConnector`/`GitCommandConnector` via `ControlFabric`
    - add structured command planning layer that maps model intents to argv/effects/profile before execution
- 2026-05-25 added long-running process tracking and cleanup reports:
  - updated `openwukong.control.command_runner`
    - added `CommandProcessRegistry`
    - added `CommandProcessStartReport`
    - added `CommandProcessStopReport`
    - supports long-running argv process start under the same workspace/profile/effect/ownership policy gates
    - tracks `process_id`, pid, argv, cwd, started time, active/stale process snapshots
    - supports `stop(process_id)` and `stop_all(...)`
    - writes JSONL audit records for process start and stop
    - keeps `shell=False`, `stdin=DEVNULL`, `stdout=DEVNULL`, and `stderr=DEVNULL` for long-running starts
    - on Windows, waits briefly after process exit so cwd handles are released before callers remove workspace directories
  - package export:
    - exported process registry/report primitives from `openwukong.control`
  - TDD coverage added:
    - start/track/stop a long-running process
    - ownership-required start blocks before process start
    - start/stop audit JSONL records are written
    - `stop_all(...)` cleans multiple active processes
    - package-level export covers `CommandProcessRegistry`
  - debugging note:
    - initial stop tests exposed a Windows timing issue where `Popen.wait()` returned but the child cwd handle remained locked briefly
    - direct reproduction showed cleanup succeeded after a short delay
    - `CommandProcessRegistry.stop(...)` now includes a conservative Windows settle before returning
  - current verification:
    - focused long-running process tests: `4 tests` passed
    - full Command Intelligence tests: `16 tests` passed
    - command/fabric/connector suite: `57 tests` passed
    - expanded control/command/readiness/discovery/browser suite: `111 tests` passed
    - full unittest discovery: `232 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add ownership-aware execution tests for real `TerminalCommandConnector`/`GitCommandConnector` via `ControlFabric`
    - add a structured command planning layer that maps intents to argv/effects/profile before execution
    - add persistent broker storage so process tracking can survive across CLI invocations
- 2026-05-25 added structured command planning layer:
  - added `openwukong.control.command_planner`
  - new planning primitives:
    - `CommandPlanIntent`
    - `CommandPlanReport`
    - `CommandPlanner`
    - `plan_command_intent(...)`
  - planner behavior:
    - converts structured intents into argv-only `CommandExecutionRequest` plus `CommandExecutionPolicy`
    - supports deterministic operations such as `git.status`, `git.diff`, `git.log`, `python.module`, and explicit `raw.argv`
    - rejects free-form shell command strings before execution with `shell_command_not_allowed`
    - rejects raw shell launchers such as `powershell.exe -Command ...` before execution
    - selects least-privilege profiles from declared effects:
      `read-only`, `workspace-write`, or `network-enabled`
    - preserves workspace/cwd validation before the runner is invoked
    - produces plan-only reports with `control_allowed=false` and `control_attempts=0`
  - added CLI:
    - `openwukong.evaluation.command_intelligence_plan`
    - accepts `--intent-json` or `--intent-file`
    - emits JSON plan reports without executing commands
  - package export:
    - exported planner primitives from `openwukong.control`
  - TDD coverage added:
    - planner API exports
    - `git.status` intent maps to read-only argv
    - shell command strings are blocked
    - shell launcher argv is blocked
    - least-privilege profile selection from effects
    - planned command executes through `CommandRunner` without shell
    - CLI emits JSON plan from structured intent
  - current verification:
    - focused planner tests: `7 tests` passed after RED/GREEN
    - command/planner/fabric/terminal/git regression suite: `50 tests` passed
    - full unittest discovery: `239 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add ownership-aware execution tests for real `TerminalCommandConnector`/`GitCommandConnector` via `ControlFabric`
    - add persistent broker storage so process tracking can survive across CLI invocations
    - connect planner output into higher-level task/supervisor execution flow instead of invoking runner inputs manually
- 2026-05-25 connected command planning into ControlFabric execution:
  - updated `openwukong.control.fabric`
    - added `ControlCommandExecutionReport`
    - added `ControlFabric.execute_command_intent(...)`
  - new execution path:
    - accepts a structured `CommandPlanIntent` or intent dictionary
    - plans first through `CommandPlanner`
    - blocks invalid plans before process execution
    - requires explicit `allow_control=True` before any command attempt
    - binds workspace ownership from the fabric `SessionOwnershipIndex`
    - enforces `require_owned_session_for_execution` before `CommandRunner`
    - executes valid plans through `CommandRunner` and embeds both plan and action reports
  - strengthened real connector validation:
    - added ownership-aware execution coverage for real `TerminalCommandConnector` through `ControlFabric`
    - added ownership-aware execution coverage for real `GitCommandConnector` through `ControlFabric`
  - package export:
    - exported `ControlCommandExecutionReport` from `openwukong.control`
  - TDD coverage added:
    - command intent execution requires explicit control permission
    - valid planned argv executes through the fabric runner path
    - invalid shell-string plans are blocked before runner execution
    - owned workspace is required when configured
    - fabric ownership index can bind owned workspace command execution
    - real Terminal connector executes only after ownership gate passes
    - real Git connector executes only after ownership gate passes
  - current verification:
    - focused ControlFabric execution tests: `14 tests` passed after RED/GREEN
    - command/planner/fabric/terminal/git regression suite: `62 tests` passed
    - full unittest discovery: `246 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add persistent broker storage so process tracking can survive across CLI invocations
    - connect supervisor/task flow to `ControlFabric.execute_command_intent(...)`
    - extend planner operation templates beyond git/python into npm, pytest, uv, docker, and Windows service-safe workflows
- 2026-05-25 added persistent broker storage for process tracking:
  - updated `openwukong.control.command_runner.CommandProcessRegistry`
    - added optional `storage_path`
    - writes active long-running process metadata to a JSON process store after successful `start(...)`
    - loads active process records on registry initialization
    - marks restored records in `snapshot()` with `restored=true`
    - prunes stale/exited records from storage during `snapshot()`
    - removes stopped records from storage during `stop(...)`
    - supports stopping a restored process by PID when the original `Popen` handle is not present
  - storage contract:
    - `mode=command-intelligence-process-store`
    - `safety_mode=workspace_process_registry`
    - stores `process_id`, `pid`, `argv`, `cwd`, effects, ownership, and start time
    - no shell strings are persisted or replayed
  - TDD coverage added:
    - started process metadata is persisted to JSON storage
    - a new registry instance can restore an active process into snapshot state
    - a restored registry instance can stop the process and remove it from storage
  - current verification:
    - full Command Intelligence tests: `19 tests` passed after RED/GREEN
    - command/planner/fabric/terminal/git regression suite: `60 tests` passed
    - full unittest discovery: `249 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add a broker CLI/API around persistent process start/snapshot/stop
    - connect supervisor/task flow to `ControlFabric.execute_command_intent(...)`
    - extend planner operation templates beyond git/python into npm, pytest, uv, docker, and Windows service-safe workflows
- 2026-05-25 added persistent process broker API and CLI:
  - added `openwukong.control.command_process_broker`
  - new broker primitives:
    - `CommandProcessBrokerConfig`
    - `CommandProcessBroker`
  - broker behavior:
    - wraps `CommandProcessRegistry` with a stable API for `start`, `snapshot`, `stop`, and `stop_all`
    - keeps explicit-control gating at the broker boundary
    - reuses persistent registry storage across broker instances
    - emits normalized JSON-style reports:
      `command-process-broker-start`, `command-process-broker-snapshot`, `command-process-broker-stop`, and `command-process-broker-stop-all`
  - added CLI:
    - `openwukong.evaluation.command_process_broker`
    - subcommands: `start`, `snapshot`, `stop`, `stop-all`
    - supports `--workspace-path`, `--storage-path`, `--profile`, `--timeout`, `--audit-log`, `--require-owned-session`, `--allow-control`, and `--json`
    - `start` uses argv remainder after `--`, preserving structured argv execution
  - Windows process-stop hardening:
    - persistent starts keep detached `Popen` handles alive inside the current Python process to avoid ResourceWarning noise
    - restored PID stop first reuses a retained handle when present
    - restored PID stop falls back to Windows `taskkill /PID ... /T /F` when no `Popen` handle exists
  - package export:
    - exported broker primitives from `openwukong.control`
  - TDD coverage added:
    - broker API exports
    - broker start blocks without explicit control permission
    - broker start/snapshot/stop lifecycle works through persistent storage
    - CLI snapshot is read-only
    - CLI start blocks without `--allow-control`
    - CLI start/snapshot/stop lifecycle works end-to-end
  - debugging note:
    - initial GREEN run revealed a Windows restored-PID stop failure: `os.kill(pid, SIGTERM)` returned `PermissionError`
    - root cause was using the generic PID path even when the retained `Popen` handle existed
    - fix now prefers retained `Popen` and uses documented Windows `taskkill` as the no-handle fallback
  - current verification:
    - focused broker tests: `6 tests` passed after RED/GREEN and Windows stop hardening
    - command/broker/planner/fabric/terminal/git regression suite: `66 tests` passed
    - full unittest discovery: `255 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - connect supervisor/task flow to `ControlFabric.execute_command_intent(...)`
    - extend planner operation templates beyond git/python into npm, pytest, uv, docker, and Windows service-safe workflows
    - add broker-backed UI/session registry reporting so active long-running processes appear in the unified control inventory
- 2026-05-25 connected supervisor task flow to structured command execution:
  - updated `openwukong.supervisor.agent_supervisor.TaskGoal`
    - added structured command fields:
      `command_operation`, `command_argv`, `command_args`, `command_effects`, `command_profile`,
      `command_timeout_sec`, `command_audit_log_path`, and `command_require_owned_session`
    - `load_goals(...)` now preserves those fields from JSON config
    - supervisor snapshots now expose command fields for UI/reporting
  - added `openwukong.supervisor.command_execution`
    - new `SupervisorCommandExecutionConfig`
    - new `SupervisorCommandExecutor`
    - converts a `TaskGoal` into `CommandPlanIntent`
    - plans through `CommandPlanner`
    - executes through `ControlFabric.execute_command_intent(...)`
    - never parses `retry_command` shell text into executable argv
  - updated `AgentSupervisor._steer(...)`
    - when a goal has structured command fields, real steer now runs through the structured command/fabric path
    - dry-run steer remains plan-only with `control_attempts=0`
    - non-command goals keep the existing connector `send_message(...)` path
  - TDD coverage added:
    - goal config preserves structured command fields
    - supervisor snapshot exposes command fields
    - executor plans a structured goal with no control attempts
    - executor blocks without explicit control permission
    - executor runs structured argv with explicit control
    - executor rejects unstructured `retry_command` shell text with `empty_argv`
    - `AgentSupervisor._steer(...)` executes structured commands through the fabric path instead of connector text injection
  - current verification:
    - focused supervisor command execution tests: `7 tests` passed after RED/GREEN
    - command/fabric/supervisor related regression suite: `61 tests` passed
    - full unittest discovery: `262 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - extend planner operation templates beyond git/python into npm, pytest, uv, docker, and Windows service-safe workflows
    - add broker-backed UI/session registry reporting so active long-running processes appear in the unified control inventory
    - add L1/L3 fixtures for supervisor structured-command goals and real command-intent route scoring
- 2026-05-25 expanded structured command planner templates for developer workflows:
  - updated `openwukong.control.command_planner`
    - added `pytest.run`
      - maps to `python -m pytest ...`
      - defaults to `workspace_write` because pytest commonly writes cache/report artifacts
    - added `npm.run`
      - maps to platform command `npm(.cmd) run <script> -- <args...>`
      - requires an explicit script name with `npm_script_required` on missing script
      - defaults to `workspace_write`
    - added `uv.run`
      - maps to platform command `uv(.cmd) run <command...>`
      - rejects wrapped shell launchers such as `powershell.exe` before execution
      - defaults to `workspace_write` because uv can update the project environment
    - added Docker Compose templates:
      - `docker.compose.ps`
      - `docker.compose.logs`
      - `docker.compose.config`
      - `docker.compose.dry-run-up`
      - `docker.compose.up`
    - read-only Docker Compose operations default to `read`
    - `docker.compose.up` defaults to `network`, selecting the `network-enabled` profile
  - TDD coverage added:
    - pytest argv/profile mapping
    - npm script argv/profile mapping and missing-script rejection
    - uv argv/profile mapping and wrapped shell launcher rejection
    - Docker Compose read-only operation mapping
    - Docker Compose dry-run up mapping
    - Docker Compose real up mapping to network-enabled profile
  - current verification:
    - focused command planner tests: `15 tests` passed after RED/GREEN
    - command/fabric/supervisor related regression suite: `66 tests` passed
    - full unittest discovery: `270 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add L1/L3 fixtures for supervisor structured-command goals and real command-intent route scoring
    - add broker-backed UI/session registry reporting so active long-running processes appear in the unified control inventory
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
- 2026-05-26 added L1/L3 command-plan scoring for structured command goals:
  - updated `openwukong.evaluation.simulation`
    - L1 results now include a `command_plan` report when a goal has structured command fields
    - L1 planning remains non-destructive with `control_allowed=false` and `control_attempts=0`
    - invalid structured command plans now fail the L1 case with `command_plan error=...`
    - fixture expectations can assert command-plan fields:
      `ok`, `operation`, `profile_id`, `effects`, `argv`, and `argv_prefix`
    - recorded goal parsing now preserves:
      `command_operation`, `command_argv`, `command_args`, `command_effects`, `command_profile`,
      `command_timeout_sec`, `command_audit_log_path`, and `command_require_owned_session`
  - updated `openwukong.evaluation.shadow`
    - L3 shadow plans now embed `command_plan`
    - structured command goals use proposed action `shadow_plan_command_intent`
    - invalid command plans add risk `command_plan_invalid`
    - invalid command plans produce safety decision `block_command_plan`
    - shadow mode remains read-only with `control_attempts=0`
  - updated `openwukong.supervisor.command_execution`
    - empty `command_effects` now remain empty so `CommandPlanner` can choose operation-specific default effects/profile
    - this fixes `pytest.run`, `npm.run`, `uv.run`, and Docker Compose templates being incorrectly downgraded to `read-only`
  - added deterministic fixture:
    - `tests/fixtures/evaluation/l1_structured_command_goals.json`
    - covers `pytest.run`, `npm.run`, and `docker.compose.dry-run-up`
  - TDD coverage added:
    - L1 command-plan report emission
    - L1 invalid command-plan failure
    - L1 structured-command fixture replay
    - L3 command-plan embedding
    - L3 invalid command-plan blocking
    - L3 structured-command fixture replay
  - current verification:
    - focused new L1/L3 command-plan tests: `6 tests` passed after RED/GREEN
    - L1/L3/command planner/supervisor/fabric related suite: `69 tests` passed
    - full unittest discovery: `276 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add broker-backed UI/session registry reporting so active long-running processes appear in the unified control inventory
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
    - add real L3 shadow trend fixtures for structured command goals captured from current workstation state
- 2026-05-26 added broker-backed unified session inventory for background processes:
  - updated `openwukong.control.command_runner`
    - active process snapshots now preserve `reason`, declared `effects`, and `ownership` metadata
    - broker snapshots can describe why a long-running process exists and whether it belongs to an owned/session-bound route
  - updated `openwukong.control.session_registry`
    - added broker snapshot registration for active command-process sessions
    - broker-managed processes now appear as `managed-process` sessions
    - preferred route is `command-process-broker`
    - capability is `command_process_broker`
    - supported background-safe actions are:
      `read_process_snapshot`, `stop_process`, and `stop_all_processes`
    - target identity is stable through `command-process:<process_id>` and includes pid, argv-derived process name, workspace path, route plan, evidence, and ownership
  - updated `openwukong.evaluation.session_registry_report`
    - added repeatable CLI option `--process-broker-snapshot`
    - read-only session registry reports can merge live/recorded window observations with broker-managed background processes
    - report control remains disabled with `control_allowed=false` and `control_attempts=0`
  - TDD coverage added:
    - broker snapshot preserves effects and ownership metadata
    - session registry converts broker snapshots into background-safe managed-process sessions
    - session registry report CLI can include a broker snapshot file
  - current verification:
    - focused new RED/GREEN tests: `3 tests` passed
    - broker/session/report regression suite: `23 tests` passed
    - expanded control/command/session regression suite: `104 tests` passed
    - full unittest discovery: `279 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - wire supervisor/task flow to start long-running process intents through the broker instead of only one-shot command runner
    - add L1/L3 fixtures for broker-managed background process lifecycle visibility
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
- 2026-05-26 wired supervisor long-running structured commands to the process broker:
  - updated `openwukong.supervisor.agent_supervisor.TaskGoal`
    - added `command_run_mode`
    - added `command_process_storage_path`
    - config loading now preserves both fields
    - UI/snapshot export now exposes both fields
  - updated `openwukong.supervisor.command_execution`
    - added `SupervisorCommandProcessStartReport`
    - added `SupervisorCommandExecutor.start_process_goal(...)`
    - long-running goals plan through the same structured command planner before broker start
    - explicit control remains required before process start
    - owned-session requirements are checked before broker start
    - broker start reports include command plan, broker start report, broker snapshot, and process id
  - updated `openwukong.supervisor.agent_supervisor.AgentSupervisor._steer(...)`
    - structured command goals with `command_run_mode=long-running` now start through `CommandProcessBroker`
    - one-shot structured command goals keep the existing `ControlFabric.execute_command_intent(...)` path
    - successful broker starts record action type `start_command_process`
    - active session id is set to `command-process:<process_id>` so the started process can be surfaced through the unified session inventory
  - updated `openwukong.control.fabric`
    - added `plan_command_intent(...)` so command planning with ownership binding can be shared by one-shot execution and broker starts
  - TDD coverage added:
    - goal config preserves long-running command fields
    - supervisor snapshots expose long-running command fields
    - executor starts a long-running goal through the process broker
    - executor blocks broker start without explicit control
    - `_steer(...)` starts long-running structured commands through the broker and records `start_command_process`
  - current verification:
    - focused new RED/GREEN tests: `5 tests` passed
    - supervisor/broker/control related regression suite: `67 tests` passed
    - full unittest discovery: `283 tests` passed
    - updated Python files passed `compileall`
  - next high-value steps:
    - add L1/L3 fixtures for broker-managed background process lifecycle visibility
    - connect session registry report to live broker storage/snapshot discovery instead of only explicit snapshot files
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
- 2026-05-26 added L1/L3 broker-managed process lifecycle visibility fixtures:
  - added fixture `tests/fixtures/evaluation/l1_broker_managed_process_lifecycle.json`
    - records a long-running `python -m http.server 8765` command intent
    - includes a replayed process broker snapshot for `proc-l1-http`
    - expects the unified session registry to expose one owned `managed-process` session through `command-process-broker`
    - keeps L1/L3 evaluation read-only with `control_allowed=false` and `control_attempts=0`
  - updated `openwukong.evaluation.simulation`
    - L1 case results now include a `session_registry` report
    - L1 fixtures can replay `process_broker_snapshots` / `broker_snapshots`
    - L1 expectations can assert session count, app-family counts, route counts, ownership counts, and required session/capability/action ids
    - command goals now preserve `command_run_mode` and `command_process_storage_path`
  - updated `openwukong.evaluation.shadow`
    - L3 shadow plans now include the same `session_registry` report
    - broker-backed long-running structured command goals are labeled as `shadow_plan_command_process_start`
  - TDD coverage added:
    - L1 fixture exports broker-managed process sessions through the unified session registry
    - L3 shadow replay preserves broker-managed session visibility without control attempts
  - current verification:
    - focused new RED/GREEN tests: `2 tests` passed
    - L1/L3/session/supervisor related regression suite: `62 tests` passed
    - L1 CLI JSON replay passed with `session_registry.session_count=1`
    - L3 CLI JSON replay passed with `proposed_action=shadow_plan_command_process_start`
    - updated Python test/source files passed `compileall`
  - next high-value steps:
    - connect session registry report to live broker storage/snapshot discovery instead of only explicit snapshot files
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
    - add a read-only live smoke path that enumerates current broker-managed processes and exports them into the unified inventory
- 2026-05-27 connected session registry report to broker storage discovery and fixed Windows PID liveness abort:
  - root cause of the Codex/test `aborted` symptom:
    - the new broker-storage replay tests wrote the current Python test process PID into a temporary process store
    - `CommandProcessRegistry._load_store()` called `_pid_running(pid)`
    - on Windows `_pid_running()` used Unix-style `os.kill(pid, 0)`
    - Python's Windows `os.kill` semantics can terminate the target process for non-console-control signals, so the test runner killed itself and Codex saw only `aborted` without a normal traceback
  - updated `openwukong.control.command_runner`
    - `_pid_running()` now branches on `os.name == "nt"`
    - Windows liveness checks now use read-only `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` through `ctypes` and always close the handle
    - Unix-like systems keep the existing `os.kill(pid, 0)` probe
  - updated `openwukong.evaluation.session_registry_report`
    - added `--process-broker-storage` to load a broker persistent store read-only and register its snapshot into the unified registry
    - added `--discover-process-brokers` to discover default broker storage paths under workspace roots/current directory
    - default discovery currently checks:
      `logs/runtime/supervisor-command-processes.json`
      and `logs/runtime/processes.json`
    - implementation reuses `CommandProcessBroker.snapshot()` instead of parsing store internals directly
  - TDD coverage added:
    - Windows process liveness regression that proves `os.kill` is not called on the Windows path
    - CLI report can include broker storage directly without a pre-exported snapshot
    - CLI report can discover default broker storage under a workspace root
  - reusable pattern captured:
    - created global skill `windows-process-liveness-safety`
    - validated with skill quick validator
  - current verification:
    - Windows liveness focused RED/GREEN test passed
    - broker storage discovery focused tests passed
    - session registry / command intelligence / process broker related suite: `45 tests` passed
    - full unittest discovery: `288 tests` passed
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files
  - next high-value steps:
    - add a read-only live smoke path that enumerates current broker-managed processes and exports them into the unified inventory without window focus or input
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
    - extend broker discovery to support multiple known storage roots from config files
- 2026-05-27 added broker-only session registry smoke path:
  - updated `openwukong.evaluation.session_registry_report`
    - added CLI flag `--broker-only`
    - broker-only mode forces an empty observer and skips desktop/window observation entirely
    - can be combined with `--process-broker-storage` or `--discover-process-brokers`
    - output remains read-only with `control_allowed=false` and `control_attempts=0`
  - TDD coverage added:
    - broker-only mode uses an observer that would fail if desktop scanning were attempted
    - the test verifies broker storage is still exported into the unified registry while `observed_state_count=0`
  - current verification:
    - focused broker-only RED/GREEN test passed
    - session registry / command intelligence / process broker related suite: `46 tests` passed
    - broker-only CLI smoke passed:
      `.venv\Scripts\python.exe -m openwukong.evaluation.session_registry_report --broker-only --discover-process-brokers --workspace-root . --json`
    - CLI smoke reported `observed_state_count=0`
    - full unittest discovery: `289 tests` passed
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files before this index update
  - next high-value steps:
    - extend broker discovery to support multiple known storage roots from config files
    - introduce a richer side-effect taxonomy for daemon/system-level operations beyond `read/workspace_write/network`
    - add a scheduler-friendly JSON summary mode for broker-only smoke reports
- 2026-05-27 added L1 primary user scenario simulation pack:
  - scope decision:
    - user selected four high-frequency scenes:
      WeChat chat, browser research, local file search, and Codex project task drafting
    - all scenarios are L1 simulation only for now
    - no real WeChat/browser/Codex/file-system actions are launched, scanned, clicked, or typed into
    - future "real simulation" must remain isolated and non-interfering with normal desktop work
  - added fixture `tests/fixtures/evaluation/l1_primary_user_scenarios.json`
    - `wechat_chat_draft_reply`
      - recorded UIA-like chat metadata and input locator
      - outputs `draft_chat_message`
      - blocks `send_message`
    - `browser_research_collect_sources`
      - recorded CDP/DOM/search-result evidence
      - outputs `draft_browser_research_plan`
      - routes to `browser-devtools-or-extension`
    - `files_search_find_candidate`
      - recorded Windows Search/file metadata candidates
      - outputs `rank_file_candidates`
      - routes to `windows-search-index`
    - `codex_project_submit_task_draft`
      - recorded workspace and task payload evidence
      - outputs `draft_codex_project_task`
      - blocks `submit_task` and `start_agent`
  - updated `openwukong.evaluation.simulation`
    - L1 case results now include `primary_scenario_plan`
    - primary scenario plans use a shared schema:
      `mode`, `safety_mode`, `control_allowed`, `control_attempts`,
      `scenario_id`, `family`, `route_id`, `connector_id`,
      `proposed_action`, `requires_confirmation`,
      `allowed_primitives`, `blocked_primitives`, `evidence_ids`,
      `draft_action`, and `risks`
    - all primary scenario plans are `safety_mode=simulation_only`
    - all primary scenario plans keep `control_allowed=false` and `control_attempts=0`
    - L1 expectations can assert route/action/confirmation/evidence/blocked primitive fields
  - TDD coverage added:
    - fixture test verifies all four primary scenarios generate simulation-only plans
    - CLI JSON test verifies the report serializes `primary_scenario_plan`
  - current verification:
    - primary scenario focused RED/GREEN tests: `2 tests` passed
    - L1/L3 related regression suite: `37 tests` passed
    - L1 CLI JSON replay passed with `4/4` cases
    - full unittest discovery: `291 tests` passed
    - fixture JSON validated with `python -m json.tool`
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files before this index update
  - next high-value steps:
    - add L2.5 "real simulation" mode for these same scenes using isolated profiles/temp directories and explicit no-focus/no-input constraints
    - add a scheduler-friendly JSON summary mode for L1/L2.5 scenario smoke reports
    - introduce a richer side-effect taxonomy for external communication, file open/modify, browser navigation, and agent task submission
- 2026-05-27 added L2.5 primary scenario smoke by reusing the unified L1 plan:
  - design decision:
    - do not create a parallel scenario router
    - reuse the existing unified route:
      `L1SimulationHarness -> primary_scenario_plan -> isolated smoke artifact`
    - L2.5 smoke treats the L1 plan as the source of truth for route, connector, draft action, blocked primitives, and confirmation gate
  - added `openwukong.evaluation.primary_scenario_smoke`
    - runs the L1 harness over a primary scenario fixture
    - writes one draft artifact per scenario under an isolated output root
    - default output root is a secure temporary directory
    - CLI:
      `.venv\Scripts\python.exe -m openwukong.evaluation.primary_scenario_smoke tests\fixtures\evaluation\l1_primary_user_scenarios.json --json`
    - report mode is `primary-scenario-smoke`
    - case mode is `primary-scenario-smoke-case`
    - artifact mode is `primary-scenario-smoke-artifact`
  - no-interference guarantees:
    - `safety_mode=isolated_no_focus`
    - `control_allowed=false`
    - `control_attempts=0`
    - `desktop_scan_attempts=0`
    - `window_input_attempts=0`
    - `live_app_launch_attempts=0`
    - `real_filesystem_scan_attempts=0`
    - artifacts include isolation flags:
      desktop scan/window input/live app launch/real user profile/real filesystem scan all disabled
  - TDD coverage added:
    - L2.5 smoke reuses L1 primary scenario plans and writes isolated draft artifacts
    - CLI JSON preserves the no-interference counters
  - current verification:
    - focused L2.5 smoke RED/GREEN tests: `2 tests` passed
    - L2.5 CLI smoke passed with `4/4` cases
    - primary/L1/L3 related regression suite: `39 tests` passed
    - full unittest discovery: `293 tests` passed
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files before this index update
  - next high-value steps:
    - add a scheduler-friendly compact JSON summary mode for L1/L2.5 scenario smoke reports
    - add per-scenario isolated adapters:
      browser static DOM bundle, file-search temp index, Codex draft queue, WeChat recorded UIA bundle
    - introduce a richer side-effect taxonomy for external communication, file open/modify, browser navigation, and agent task submission
- 2026-05-27 added scheduler-friendly compact JSON summaries for L1 and L2.5 scenario reports:
  - updated `openwukong.evaluation.simulation`
    - added CLI flag `--summary-json`
    - emits compact mode `l1-simulation-summary`
    - includes suite, pass counts, pass rate, scenario count, compact scenario rows, route quality, and safety fields
    - excludes the full `results` payload
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - added CLI flag `--summary-json`
    - emits compact mode `primary-scenario-smoke-summary`
    - includes no-interference counters, artifact count, scenario count, and compact scenario rows
    - excludes full `cases` and artifact paths
  - scheduler commands:
    - L1 summary:
      `.venv\Scripts\python.exe -m openwukong.evaluation.simulation tests\fixtures\evaluation\l1_primary_user_scenarios.json --summary-json`
    - L2.5 summary:
      `.venv\Scripts\python.exe -m openwukong.evaluation.primary_scenario_smoke tests\fixtures\evaluation\l1_primary_user_scenarios.json --summary-json`
  - TDD coverage added:
    - L1 summary JSON is compact, has `simulation_only`, `control_attempts=0`, and includes four scenario rows
    - L2.5 summary JSON is compact, has all no-interference counters at zero, and includes artifact count without full case payloads
  - current verification:
    - focused summary RED/GREEN tests: `2 tests` passed
    - L1 summary CLI replay passed
    - L2.5 summary CLI replay passed
    - primary/L1/L3 related regression suite: `41 tests` passed
    - full unittest discovery: `295 tests` passed
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files before this index update
  - next high-value steps:
    - add per-scenario isolated adapters:
      browser static DOM bundle, file-search temp index, Codex draft queue, WeChat recorded UIA bundle
    - introduce a richer side-effect taxonomy for external communication, file open/modify, browser navigation, and agent task submission
    - add trend comparison for compact summaries so repeated smoke runs can show regressions
- 2026-05-27 added per-scenario isolated adapters for L2.5 primary scenario smoke:
  - design decision:
    - adapters are still isolated artifacts, not live executors
    - they reuse the existing `primary_scenario_plan`
    - they are written under the L2.5 output root and never touch real app/user state
  - updated `openwukong.evaluation.simulation`
    - `primary_scenario_plan` now carries recorded context needed by downstream isolated adapters
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - each smoke case now includes:
      `adapter_id` and `adapter_artifact_path`
    - summary JSON includes:
      `adapter_artifact_count`, per-scenario `adapter_id`, and `adapter_artifact_written`
    - draft artifacts remain separate from adapter artifacts
  - isolated adapters added:
    - `wechat-recorded-uia-bundle`
      - includes contact, message draft, recorded input locator, and `send_allowed=false`
    - `browser-static-dom-bundle`
      - includes query, expected source count, recorded source titles, and `live_navigation_allowed=false`
    - `file-search-temp-index`
      - includes query, file type filters, recorded candidates, candidate count, and `real_filesystem_scan_allowed=false`
    - `codex-draft-queue`
      - includes project id, one queued draft action, and both `submit_allowed=false` and `start_agent_allowed=false`
  - TDD coverage added:
    - L2.5 smoke verifies each adapter artifact is written under the isolated output root
    - adapter artifacts preserve `isolated_no_focus`, `control_attempts=0`, and isolation metadata
    - browser/file/Codex adapter payloads expose static DOM/source titles, temp index candidate count, and draft queue count
    - summary JSON exposes adapter ids and adapter artifact written state
  - current verification:
    - focused adapter RED/GREEN tests: `3 tests` passed
    - L2.5 summary CLI replay passed with `adapter_artifact_count=4`
    - primary/L1/L3 related regression suite: `41 tests` passed
    - full unittest discovery: `295 tests` passed
    - updated Python files passed `compileall`
    - `git diff --check` passed for touched project files before this index update
  - next high-value steps:
    - introduce a richer side-effect taxonomy for external communication, file open/modify, browser navigation, and agent task submission
    - add trend comparison for compact summaries so repeated smoke runs can show regressions
    - add fixture variants for failure cases: missing contact, empty browser results, no file candidates, and unsafe Codex task submission
- 2026-05-27 introduced a unified primary-scenario side-effect taxonomy:
  - added `openwukong.evaluation.side_effects`
    - taxonomy version:
      `primary-side-effects-v1`
    - defines stable effect ids for:
      external communication, browser navigation, browser form submit, file open,
      file modify, real filesystem scan, agent task submission, agent start,
      recorded-context reads, and isolated draft writes
    - each effect records category, primitive, severity, confirmation requirement,
      and policy decision
  - updated `openwukong.evaluation.simulation`
    - each `primary_scenario_plan` now includes `side_effect_policy`
    - L1 compact summary now includes:
      `blocked_effect_count`, `blocked_effect_categories`, and
      `confirmation_required_effect_count`
    - expectation comparison can now assert blocked effect category/id
    - file-search simulation now explicitly blocks `real_filesystem_scan`
      in addition to file open/modify
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - smoke cases now export `blocked_effects` and `confirmation_required_effects`
    - draft artifacts and adapter artifacts preserve the full `side_effect_policy`
    - L2.5 compact summary exposes the same blocked/confirmation effect counters
  - TDD coverage added:
    - L1 primary scenario plans expose side-effect policy and categories
    - L1 summary JSON exposes blocked effect categories and confirmation counts
    - L2.5 draft/adapter artifacts preserve side-effect policy
    - L2.5 case and summary JSON expose blocked effect details
  - current verification:
    - RED verified first:
      side-effect tests failed on missing `side_effect_policy` and missing summary fields
    - focused side-effect tests:
      `6 tests` passed
    - L1 summary CLI replay passed with `4/4` cases and side-effect categories
    - L2.5 summary CLI replay passed with `4/4` cases and no-interference counters at zero
    - evaluation/broker/supervisor related regression suite:
      `88 tests` passed
    - full unittest discovery:
      `295 tests` passed
    - updated Python files passed `compileall`
    - touched files had no trailing whitespace by direct `rg` check
    - `git diff --check` is currently blocked by unrelated pre-existing trailing whitespace
      in dirty files such as `src/openwukong/monitor/ai_monitor.py` and
      `src/openwukong/supervisor/agent_supervisor.py`
  - next high-value steps:
    - add fixture variants for failure cases:
      missing contact, empty browser results, no file candidates, and unsafe Codex task submission
    - start mapping confirmed taxonomy decisions into isolated owned-session dry-run
      workflows so future live execution can share the same allow/block/confirm gates
- 2026-05-27 mapped side-effect taxonomy into the unified control fabric gate:
  - direction decision:
    - user rejected compact-summary trend work as too indirect
    - next work moved directly toward the core goal:
      precise real computer operation through a unified execution gate
  - added `openwukong.control.side_effects`
    - moved the canonical taxonomy out of evaluation into the control layer
    - exports:
      `build_side_effect_policy`, `evaluate_side_effect_policy`, and
      `SideEffectGateReport`
    - gate decisions include:
      `allow`, `side_effect_confirmation_required`, and
      `blocked_by_side_effect_policy`
    - gate output preserves blocked effect ids/categories, confirmation-required
      effect ids, confirmed effect ids, and the original policy
  - updated `openwukong.evaluation.side_effects`
    - now compatibility-reexports the control-layer taxonomy/gate
    - avoids making `openwukong.control` depend on `openwukong.evaluation`
  - updated `openwukong.control.fabric`
    - `ControlIntent` now accepts:
      `side_effect_policy`, `confirmed_effect_ids`, and
      `allow_blocked_side_effects`
    - every `ControlDispatchReport` now includes a `side_effect_gate`
    - dispatch stops before connector resolution/execution when the side-effect
      gate requires confirmation or blocks the intended action
    - `execute(..., allow_control=True)` still refuses to call the connector when
      the dispatch report is blocked by side effects
  - updated exports in `openwukong.control.__init__`
  - updated `openwukong.evaluation.simulation`
    - primary scenario planning now imports the taxonomy from the control layer
  - TDD coverage added:
    - available IDE connector is blocked when an external communication effect
      requires confirmation
    - terminal connector execution is not called when a file modification effect
      is blocked by the side-effect gate
  - current verification:
    - RED verified first:
      focused control tests failed because `openwukong.control.side_effects`
      did not exist
    - focused control fabric tests:
      `25 tests` passed
    - control/L1/L2.5 focused suite:
      `31 tests` passed
    - L1 primary scenario summary CLI:
      `4/4` cases passed
    - L2.5 primary scenario smoke summary CLI:
      `4/4` cases passed with all no-interference counters at zero
    - updated control/evaluation files passed `compileall`
    - full unittest discovery:
      `297 tests` passed
    - touched files passed direct trailing-whitespace check and scoped
      `git diff --check`
  - next high-value steps:
    - add failure-case fixtures for the four primary scenarios:
      missing contact, empty browser results, no file candidates, unsafe Codex task
    - add explicit positive-path fixture/gate coverage for confirmed side effects
      in isolated owned sessions
    - start turning browser research and Codex task drafting from static artifacts
      into isolated owned-session dry-run workflows while keeping no-focus/no-input
      guarantees
- 2026-05-27 added isolated owned-session dry-run workflows for browser research and Codex task drafting:
  - direction:
    - moved beyond static L2.5 artifacts for the two safest connector-first surfaces
    - kept WeChat and file-search as static/adapter artifacts only because real send/open/scan
      behavior needs stronger native bridges and user confirmation
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - browser and Codex cases now write an additional artifact under:
      `owned_session_dry_runs/`
    - case dictionaries now include:
      `owned_session_dry_run_id` and `owned_session_dry_run_artifact_path`
    - summary JSON now includes:
      `owned_session_dry_run_artifact_count`,
      `owned_session_dry_run_id`, and `owned_session_dry_run_written`
  - browser owned-session dry-run:
    - emits `browser-owned-session-dry-run`
    - creates only an isolated output-root profile directory
    - uses a `dry-run://browser/...` endpoint as an owned-session marker
    - dispatches through `ControlFabric.dispatch(...)` to
      `browser-devtools-or-extension`
    - action is read/extract oriented and uses a dry-run side-effect policy that
      allows only recorded-context read and local draft write
  - Codex owned-session dry-run:
    - emits `codex-owned-session-dry-run`
    - creates only an isolated output-root bridge directory
    - uses a `dry-run://ide-bridge/...` endpoint as an owned-session marker
    - dispatches through `ControlFabric.dispatch(...)` to
      `ide-extension-connector`
    - action remains `draft_codex_project_task`, not submit/start agent
  - no-interference guarantees:
    - no desktop scan
    - no window input
    - no live app launch
    - no live connector call
    - no real user profile
    - no real filesystem scan
    - all dry-run artifacts keep `control_allowed=false` and `control_attempts=0`
  - TDD coverage added:
    - browser/Codex dry-run artifacts are written under the isolated output root
    - artifacts embed owned-session metadata, ControlFabric dispatch reports,
      side-effect gate results, and isolation flags
    - WeChat/file-search explicitly do not receive owned-session dry-run artifacts
    - compact summary reports exactly two owned-session dry-run artifacts
  - current verification:
    - RED verified first:
      L2.5 tests failed on missing `owned_session_dry_run_artifact_path` and
      missing `owned_session_dry_run_artifact_count`
    - focused L2.5 test:
      `3 tests` passed
    - control/L1/L2.5/session related suite:
      `46 tests` passed
    - L2.5 summary CLI:
      `4/4` cases passed and `owned_session_dry_run_artifact_count=2`
    - L2.5 full JSON CLI:
      `4/4` cases passed and all no-interference counters stayed at zero
    - L1 summary CLI:
      `4/4` cases passed
    - updated evaluation files passed `compileall`
    - full unittest discovery:
      `297 tests` passed
    - touched files passed direct trailing-whitespace check and scoped
      `git diff --check`
  - next high-value steps:
    - add explicit confirmed-side-effect positive path in isolated owned sessions,
      proving confirmation can unlock controlled dispatch without bypassing the gate
    - add failure-case fixtures for the four primary scenarios
    - begin replacing Codex dry-run bridge marker with an actual local mock bridge server
      owned by the test harness, still with no user-app focus or real task submission
- 2026-05-27 upgraded browser/Codex owned-session smoke from dry-run to local mock execution:
  - direction:
    - moved the two safest connector-first scenarios one layer closer to real precise control
    - still avoided real desktop/app interaction:
      no desktop scan, no window input, no live app launch, no real user profile, no real filesystem scan
    - WeChat and file-search remain static/adapter-only because they still need stronger
      native bridges and confirmation semantics before any real execution
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - smoke cases now expose:
      `owned_session_execution_id` and `owned_session_execution_artifact_path`
    - compact summary JSON now exposes:
      `owned_session_execution_artifact_count`,
      `owned_session_execution_id`, and `owned_session_execution_written`
    - execution artifacts are written under:
      `owned_session_executions/`
  - browser local mock execution:
    - emits `browser-owned-session-local-mock-devtools`
    - runs through `ControlFabric.execute(..., allow_control=True)`
    - uses an owned `browser-devtools-or-extension` route with a local mock DevTools runner
    - only performs `extract_results` over recorded titles; it does not navigate,
      click, type, or submit forms
  - Codex local mock execution:
    - emits `codex-owned-session-local-mock-bridge`
    - starts a temporary `127.0.0.1` `ThreadingHTTPServer` mock IDE bridge
    - runs through the real `IDEExtensionConnector` and `ControlFabric.execute(..., allow_control=True)`
    - posts to `/v1/ide/send`, records the bridge request, then shuts down and joins the server thread
    - this validates the real connector/fabric path without submitting a real Codex task
      or starting a real agent
  - no-interference guarantees:
    - top-level smoke report remains:
      `control_allowed=false`, `control_attempts=0`
    - L2.5 summary remains:
      `desktop_scan_attempts=0`, `window_input_attempts=0`,
      `live_app_launch_attempts=0`, `real_filesystem_scan_attempts=0`
    - execution artifacts distinguish:
      `desktop_control_attempts=0` from local mock connector calls
  - TDD coverage added:
    - RED verified for missing Codex execution artifact and summary count
    - RED verified again for missing browser execution artifact and count
    - tests assert browser/Codex execution artifacts stay under the isolated output root
    - tests assert browser route uses `browser-devtools-or-extension`
    - tests assert Codex route uses `ide-extension-connector` and records `/v1/ide/send`
  - current verification:
    - focused L2.5 smoke:
      `3 tests` passed
    - related control/L1/L2.5/browser/IDE/session suite:
      `69 tests` passed
    - L2.5 summary CLI:
      `4/4` cases passed and `owned_session_execution_artifact_count=2`
    - L2.5 full JSON CLI:
      `4/4` cases passed and all no-interference counters stayed at zero
    - L1 summary CLI:
      `4/4` cases passed
    - updated evaluation files passed `compileall`
    - full unittest discovery:
      `297 tests` passed
  - next high-value steps:
    - replace the browser local mock runner with an actual isolated DevTools fixture/server,
      then with a real owned Chrome profile when ready
    - add confirmed-side-effect positive-path fixtures proving confirmation unlocks
      controlled execution without bypassing the side-effect gate
    - add failure-case fixtures:
      missing contact, empty browser results, no file candidates, unsafe Codex task
- 2026-05-27 replaced the primary browser local mock runner with an actual local CDP fixture:
  - context:
    - user correctly recalled that a real isolated Browser DevTools path had already been
      live-validated on 2026-05-21
    - that earlier path proved:
      isolated Chrome launch, `/json/list` readiness, health-gated actions,
      Fabric-gated browser workflow execution, and manifest cleanup with no residual Chrome process
    - this session did not relaunch real Chrome in order to avoid affecting normal desktop work
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - browser owned-session execution no longer uses a Python runner that directly returns
      fake action data
    - it now starts a local in-process CDP fixture:
      `ThreadingHTTPServer` for `/json/list` plus a local WebSocket server for
      `Runtime.evaluate`
    - `ControlFabric.execute(..., allow_control=True)` now uses the normal default
      browser action runner, which calls `BrowserDevToolsClient` against the fixture
    - execution artifact now includes:
      `local_devtools_fixture`, HTTP request count, CDP request count, CDP request methods,
      and the nested `browser-devtools-action` health/action report
  - behavior:
    - browser scenario still performs only `extract_results`
    - no real browser is launched
    - no desktop scan, window input, live app launch, user profile access, or real filesystem scan
    - this moves the primary scenario one layer closer to the already validated real owned
      Chrome profile path without re-running a visible browser helper
  - TDD coverage:
    - RED verified first:
      browser primary smoke failed because `local_connector_call_attempts` was still `1`
      and no real DevTools action/fixture evidence existed
    - GREEN:
      primary smoke now observes at least two CDP `Runtime.evaluate` calls:
      health identity and result extraction
  - current verification:
    - focused primary scenario smoke:
      `3 tests` passed
    - related primary/browser/CDP/Fabric/readiness/ownership suite:
      `64 tests` passed
    - L2.5 summary CLI:
      `4/4` cases passed and `owned_session_execution_artifact_count=2`
    - L2.5 full JSON CLI:
      `4/4` cases passed and all no-interference counters stayed at zero
  - next high-value steps:
    - add an opt-in primary smoke mode that uses the existing real isolated Chrome
      readiness helper and immediately runs cleanup
    - add confirmed-side-effect positive-path fixtures for browser navigation and agent task
      submission while preserving the side-effect gate
    - add failure-case fixtures for the four main scenarios
- 2026-05-27 added and live-validated opt-in real isolated Chrome helper mode:
  - direction:
    - user explicitly allowed a real launch for validation
    - default L2.5 primary smoke remains non-interfering and does not launch real apps
    - real launch now requires the explicit CLI/API opt-in:
      `--allow-owned-browser-helper-launch`
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - added per-case fields:
      `owned_browser_helper_id` and `owned_browser_helper_artifact_path`
    - compact summary now includes:
      `owned_browser_helper_artifact_count`, `owned_browser_helper_id`, and
      `owned_browser_helper_written`
    - report `live_app_launch_attempts` stays `0` by default and becomes `1` only
      when the opt-in owned helper is actually launched
  - owned browser helper behavior:
    - uses the existing `session_readiness_plan` implementation rather than a new
      launcher path
    - launches Chrome with:
      `--remote-debugging-port=<port>` plus an absolute isolated `--user-data-dir`
    - writes a manifest under the isolated output root
    - probes DevTools `/json/list` before cleanup
    - requires target ownership evidence:
      `target_match_ok=true` against the expected owned smoke URL
    - stops strictly through `stop_session_readiness_manifest`
  - safety properties:
    - no desktop scan
    - no window input
    - no real user profile
    - no real filesystem scan
    - helper artifact records:
      `desktop_control_attempts=0`, `window_input_attempts=0`,
      `real_user_profile_allowed=false`
  - live validation:
    - Chrome executable:
      `C:\Program Files\Google\Chrome\Application\chrome.exe`
    - final opt-in run:
      `logs/runtime/primary-scenario-smoke-real-helper-20260527-29383-default-url`
    - result:
      `4/4` primary scenarios passed
    - helper result:
      `status=started_and_stopped`, `launch_attempts=1`, `stop_attempts=1`
    - readiness result:
      `/json/list` returned a matching page target titled
      `OpenWukong Primary Smoke`
    - cleanup check:
      no non-PowerShell process remained with `--remote-debugging-port=29383`
      or the isolated output-root profile in its command line
  - TDD coverage added:
    - RED verified first for missing opt-in API arguments
    - RED verified again for missing readiness/target ownership fields
    - tests use a fake readiness launcher, fake terminator, and fake readiness probe
      so unit tests do not launch real Chrome
    - tests assert the profile path is absolute, inside the output root, pre-created,
      and passed through `--user-data-dir`
    - tests assert manifest-based cleanup calls the recorded PID and owned argv
  - current verification:
    - focused opt-in helper test:
      `1 test` passed
    - full primary scenario smoke tests:
      `4 tests` passed
    - real opt-in primary smoke summary:
      `4/4` cases passed, `owned_browser_helper_artifact_count=1`,
      `live_app_launch_attempts=1`
    - default L2.5 summary CLI:
      `4/4` cases passed, `owned_browser_helper_artifact_count=0`,
      `live_app_launch_attempts=0`
    - L1 summary CLI:
      `4/4` cases passed
    - full unittest discovery:
      `298 tests` passed
    - updated files passed `compileall`
    - touched files had no trailing whitespace by direct `rg` check
  - next high-value steps:
    - add a real owned-browser positive-path action behind confirmation:
      navigate/read/extract from the owned Chrome page, still never using the user's
      normal browser profile
    - add confirmed-side-effect positive-path fixtures for browser navigation and
      Codex task submission while preserving the side-effect gate
    - add failure-case fixtures:
      missing contact, empty browser results, no file candidates, unsafe Codex task
- 2026-05-27 added and live-validated real owned-browser read action:
  - direction:
    - advanced the browser path from real isolated helper readiness to a real
      connector-first read action inside the owned Chrome session
    - default L2.5 primary smoke still does not launch real apps
    - real execution still requires:
      `--allow-owned-browser-helper-launch`
  - updated `openwukong.evaluation.primary_scenario_smoke`
    - after owned Chrome readiness and target ownership matching, the helper now
      executes a read-only `read_page` action through:
      `ControlFabric.execute(..., allow_control=True)`
    - action uses a first-class owned `SessionOwnership` record:
      `ownership_source=primary_scenario_smoke_real_browser_helper`
    - helper artifact now records:
      `owned_browser_action_id=browser-owned-helper-read-page`,
      `owned_browser_action`, and `owned_browser_action_control_attempts`
    - the action keeps:
      `desktop_control_attempts=0`, `window_input_attempts=0`, and
      `owned_browser_action_control_attempts=0`
  - live validation:
    - final opt-in run:
      `logs/runtime/primary-scenario-smoke-real-helper-20260527-29385-read-action`
    - result:
      `4/4` primary scenarios passed
    - readiness:
      `/json/list` matched the owned `OpenWukong Primary Smoke` page target
    - action:
      `browser-devtools-action` executed `read_page`
    - action result:
      page title and text excerpt both returned `OpenWukong Primary Smoke`
    - cleanup:
      `stop_attempts=1`, no non-PowerShell process remained with
      `--remote-debugging-port=29385` or the isolated output-root profile in its
      command line
  - cleanup bug fixed:
    - first real action run succeeded but exposed a Windows cleanup false negative:
      `taskkill /T` reported a Chrome child process could not be terminated even
      though the owned residual scan found no remaining process
    - updated `SessionReadinessStopResult` with a `warning` field
    - updated `stop_session_readiness_manifest` so a tree-kill warning is not a
      stop failure when owned residual cleanup succeeds
  - TDD coverage added:
    - RED verified for missing owned browser action runner/API
    - RED verified for the Windows child-process cleanup warning case
    - tests assert the real action path dispatches through
      `browser-devtools-or-extension`, calls `read_page`, and keeps action
      `control_attempts=0`
    - tests assert cleanup warning is preserved while stop status remains `stopped`
  - current verification:
    - focused owned browser helper/action test:
      `1 test` passed
    - focused cleanup warning regression:
      `1 test` passed
    - related readiness + primary smoke suite:
      `19 tests` passed
    - real opt-in primary smoke with read action:
      `4/4` cases passed, `owned_browser_helper_artifact_count=1`,
      `live_app_launch_attempts=1`
    - default L2.5 summary CLI:
      `4/4` cases passed, `owned_browser_helper_artifact_count=0`,
      `live_app_launch_attempts=0`
    - L1 summary CLI:
      `4/4` cases passed
    - full unittest discovery:
      `299 tests` passed
    - updated files passed `compileall`
    - touched files passed direct trailing-whitespace check and scoped
      `git diff --check`
  - next high-value steps:
    - add an owned-browser `extract_results` positive-path action over a local
      deterministic page with links
    - then add a confirmed browser-navigation positive path that only navigates
      within the owned Chrome profile and never touches the normal user browser
    - extend the same owned-session execute pattern to Codex/Cursor bridge submit
      drafts behind explicit confirmation
- 2026-05-27 added and live-validated primary real no-loss scenario probes:
  - direction:
    - upgraded the four primary user scenarios from simulation/static smoke into
      real no-loss probes where each scenario either uses a read-only live probe
      or an owned isolated resource
    - kept the hard safety boundary:
      no external communication, no window typing, no user-profile browser use,
      no real user filesystem scan, no user file modification, and no Codex task
      submission
  - added `openwukong.evaluation.primary_real_no_loss`
    - exposes `run_primary_real_no_loss(...)`, `summarize_report(...)`, and a CLI:
      `python -m openwukong.evaluation.primary_real_no_loss`
    - report mode is `primary-scenario-real-no-loss`
    - every case and report keeps:
      `safety_mode=real_no_loss`, `control_allowed=false`,
      and `control_attempts=0`
  - scenario coverage:
    - WeChat:
      read-only Windows accessibility/UIA capability probe against live WeChat
      windows; observed Weixin/WXWork surfaces were correctly blocked for write
      control because they lack deterministic semantic input
    - Browser:
      launched an owned isolated Chrome helper profile, matched its DevTools page
      target, executed a read-only `read_page` action through `ControlFabric`, and
      cleaned up the helper
    - Files:
      created and searched only an owned temp index under the output root; did not
      scan the user's real filesystem
    - Codex:
      probed the local IDE bridge capability endpoint read-only; current real
      bridge was unavailable, so the case passed as safely unavailable without
      submit/start attempts
  - live validation:
    - output root:
      `logs/runtime/primary-real-no-loss-20260527-29386`
    - result:
      `4/4` no-loss cases passed, `3/4` real-verified
    - top-level safety counters:
      `external_communication_attempts=0`,
      `window_input_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`,
      `owned_app_launch_attempts=1`
    - cleanup check:
      no non-PowerShell process remained with `--remote-debugging-port=29386` or
      the isolated output-root profile in its command line; port `29386` had no
      active listener afterward
  - TDD coverage added:
    - RED verified first for missing `primary_real_no_loss` module
    - tests assert all no-loss counters stay at zero, browser uses the owned
      helper read action, file candidates stay under the output root, Codex does
      not submit/start, and summary output omits detailed sensitive probe data
  - current verification:
    - focused real no-loss test:
      `1 test` passed
    - related real no-loss / primary smoke / readiness / accessibility / IDE
      bridge suite:
      `31 tests` passed
    - real no-loss CLI:
      `4/4` cases passed, `3/4` real-verified, with all destructive/noisy counters
      at zero
    - full unittest discovery:
      `300 tests` passed
    - updated files passed `compileall`
    - touched files passed direct trailing-whitespace check and scoped
      `git diff --check`
  - next high-value steps:
    - start the real Codex/Cursor IDE bridge and rerun real no-loss so the Codex
      scenario moves from safe `unavailable` to real read-only verified
    - add an owned-browser `extract_results` positive-path action over a local
      deterministic page with links
    - add a stronger WeChat native/bridge read-only locator probe while keeping
      send actions blocked until a deterministic connector and explicit
      confirmation exist
- 2026-05-27 upgraded WeChat from generic UIA scan to a dedicated read-only
  UIA + Win32 locator:
  - direction:
    - kept WeChat in real no-loss mode
    - strengthened observation evidence without typing, clicking, invoking,
      setting values, hooking live events, or sending messages
  - added `openwukong.evaluation.wechat_locator`
    - combines existing UIA capability snapshots with read-only Win32 child HWND
      metadata
    - records top-level WeChat window identity, UIA semantic-input/action counts,
      Win32 child class counts, visible child counts, input-like class hints, and
      draft locator candidate count
    - always keeps:
      `control_allowed=false`, `control_attempts=0`, `send_attempts=0`,
      `window_input_attempts=0`, and `write_control_ready=false`
    - route recommendation remains connector-first:
      `wechat-native-bridge-required`, then read-only UIA/Win32/MSAA evidence,
      with vision only as last fallback
  - updated `openwukong.evaluation.primary_real_no_loss`
    - WeChat scenario now reports:
      `real_probe_kind=wechat-uia-win32-read-only-locator`
    - WeChat case details now embed a compact locator report while still omitting
      child element detail from summary output
  - live validation:
    - output root:
      `logs/runtime/primary-real-no-loss-wechat-locator-20260527`
    - result:
      `4/4` no-loss cases passed in summary mode without launching owned browser
      helper
    - WeChat locator:
      matched `2` live WeChat-family windows
    - live `Weixin.exe` evidence:
      UIA exposed `1` element, `0` semantic inputs; Win32 exposed `3` child HWNDs,
      `1` visible child HWND, and class evidence including `Qt51514QWindowIcon`,
      `Chrome_WidgetWin_0`, and `Intermediate D3D Window`
    - live result:
      `read_only_verified=true`, `control_decision=read_only_verified_write_blocked`
    - safety counters:
      `send_attempts=0`, `window_input_attempts=0`, `control_attempts=0`,
      `external_communication_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`,
      `owned_app_launch_attempts=0`
  - TDD coverage added:
    - RED verified first for missing `openwukong.evaluation.wechat_locator`
    - tests assert the locator merges UIA and Win32 evidence and keeps all control
      counters at zero
    - primary real no-loss integration test now asserts the WeChat case uses the
      dedicated locator and preserves write blocking
  - current verification:
    - focused WeChat locator test:
      `1 test` passed
    - focused primary real no-loss test:
      `1 test` passed
    - related accessibility / primary real no-loss / WeChat locator suite:
      `10 tests` passed
    - live WeChat no-loss CLI:
      `4/4` cases passed, WeChat `real_verified=true`, all destructive/noisy
      counters stayed at zero
  - next high-value steps:
    - add MSAA read-only object retrieval for WeChat HWNDs through OLEACC
      `AccessibleObjectFromWindow`/event-derived evidence, still without action
    - add a WeChat focus/event read-only monitor with `SetWinEventHook` only after
      a bounded message-loop lifecycle and cleanup test exist
    - do not test draft typing or sending until a deterministic WeChat native bridge
      or connector exists and the side-effect gate requires explicit confirmation
- 2026-05-27 added live MSAA/OLEACC read-only evidence to the WeChat locator:
  - direction:
    - completed the next WeChat observation layer without changing the safety
      boundary
    - used OLEACC `AccessibleObjectFromWindow` only for read-only
      `IAccessible` metadata
    - explicitly blocked MSAA mutation methods:
      `accDoDefaultAction`, `accSelect`, `put_accName`, and `put_accValue`
  - updated `openwukong.evaluation.wechat_locator`
    - added `MsaaAccessibleSnapshot`
    - added `StaticMsaaObserver` for deterministic tests
    - added `CtypesMsaaObserver` for live OLEACC reads
    - locator windows now record:
      MSAA object count, name/value counts, role counts, source list, read-method
      list, blocked mutation-method list, and MSAA error count
    - locator candidate scoring now includes MSAA locator signals
  - live validation:
    - output root:
      `logs/runtime/primary-real-no-loss-wechat-msaa-20260527`
    - result:
      `4/4` no-loss cases passed in summary mode without launching owned browser
      helper
    - live `Weixin.exe` evidence:
      UIA exposed `1` element and `0` semantic inputs; Win32 exposed `3` child
      HWNDs; MSAA exposed `4` accessible objects, `2` names, and `0` MSAA errors
    - live `WXWork.exe` evidence:
      MSAA exposed `1` accessible object, `1` name, and `0` MSAA errors
    - live result:
      `read_only_verified=true`, `control_decision=read_only_verified_write_blocked`
    - safety counters:
      `send_attempts=0`, `window_input_attempts=0`, `control_attempts=0`,
      `external_communication_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`,
      `owned_app_launch_attempts=0`
  - TDD coverage added:
    - RED verified first for missing `MsaaAccessibleSnapshot`
    - tests assert MSAA evidence is merged with UIA and Win32 evidence
    - tests assert read-method reporting and blocked mutation-method reporting
      are present while write control remains blocked
  - current verification:
    - focused WeChat locator tests:
      `2 tests` passed
    - focused primary real no-loss test:
      `1 test` passed
    - live WeChat MSAA no-loss CLI:
      `4/4` cases passed, WeChat `real_verified=true`, all destructive/noisy
      counters stayed at zero
  - next high-value steps:
    - add role/state normalization for MSAA numeric constants so live reports are
      easier to interpret
    - add a bounded read-only WinEvent focus/change monitor only after lifecycle
      cleanup tests exist
    - design the WeChat native connector contract before any draft typing or send
      path is allowed
- 2026-05-27 added and live-validated explicit opt-in WeChat File Transfer
  Assistant send:
  - direction:
    - created a separate real-send probe outside the default no-loss path
    - default behavior remains blocked; sending requires explicit opt-in,
      target restriction, and target confirmation after opening
    - this validated that controlled foreground + keyboard/clipboard operation
      can send to a safe self-chat target, but it is not yet a background or fully
      semantic native connector
  - added `openwukong.evaluation.wechat_send_probe`
    - report mode:
      `wechat-file-helper-send-probe`
    - default status without `allow_send`:
      `blocked_requires_explicit_opt_in`
    - non-file-helper targets are blocked:
      `blocked_target_not_allowed`
    - target must be exactly `文件传输助手`
    - target search/open runs before sending and captures a pre-send screenshot
    - sending remains blocked as `blocked_target_not_verified` unless target
      verification succeeds or the caller passes the explicit
      `--confirm-target-after-open` second-stage confirmation
    - tracks:
      send attempts, keyboard input attempts, clipboard writes/restores,
      foreground restore attempts, target verification, screenshot path, and
      window HWNDs
  - live validation:
    - prepare run:
      `logs/runtime/wechat-filehelper-send-prepare-20260527/pre_send_target.png`
      confirmed the target was `文件传输助手` and the input box was focused
    - confirmed send run:
      `status=sent`, `send_attempts=1`, `keyboard_input_attempts=6`,
      `clipboard_write_attempts=2`, `clipboard_restore_attempts=1`,
      `foreground_restore_attempts=1`, `target_verified=true`
    - sent message:
      `OpenWukong live send probe 2026-05-27 16:15:59`
    - post-send screenshot:
      `logs/runtime/wechat-filehelper-send-confirmed-20260527/post_send_wechat_foreground_verify.png`
      visually confirmed the message appeared in WeChat File Transfer Assistant
  - TDD coverage added:
    - RED verified first for missing `openwukong.evaluation.wechat_send_probe`
    - tests cover:
      blocked default, blocked non-file-helper target, blocked unverified target,
      sent path after verification, and explicit second-stage confirmation
    - tests assert clipboard/foreground restoration counters and keyboard/send
      counters
  - next high-value steps:
    - add post-send screenshot/report persistence to the probe artifact contract
    - add OCR or accessibility-based post-send verification instead of relying on
      manual visual confirmation
    - replace foreground keyboard/clipboard send with a WeChat-native connector
      contract if a stable app-specific bridge is found
- 2026-05-27 archived the real WeChat control milestone and hardened send
  artifacts:
  - direction:
    - user confirmed the first live WeChat File Transfer Assistant send succeeded
    - user clarified that a Codex-looking screenshot was caused by manual window
      switching during testing, not by a wrong-target send
    - tightened artifact capture so post-send screenshots prefer the bound WeChat
      HWND instead of relying on whatever window is foreground at capture time
  - updated `openwukong.evaluation.wechat_send_probe`
    - report now includes:
      `post_send_screenshot_path`, `post_send_screenshot_hwnd`,
      `post_send_screenshot_bound`, `post_send_screenshot_mode`,
      `artifact_path`, `transport`, and per-phase records
    - successful send phase now attempts a bound-window screenshot through the
      target HWND
    - generated JSON reports are persisted to `report.json`
  - added milestone archive:
    - `.agents/milestones/2026-05-27-real-wechat-control.md`
    - records implemented capabilities, live validation evidence, safety
      boundaries, known gaps, and next steps
  - current boundary:
    - live WeChat sending is validated only for File Transfer Assistant
    - current transport is still `foreground-keyboard-clipboard`
    - fully background/native WeChat control remains a separate next milestone
  - archive pre-push live validation:
    - user explicitly allowed another real send before archival push
    - sent message:
      `OpenWukong archive live send probe 2026-05-27 16:34:43`
    - output root:
      `logs/runtime/wechat-filehelper-send-archive-20260527-163443`
    - result:
      `status=sent`, `send_attempts=1`, `target_verified=true`
    - post-send artifact used bound WeChat HWND screenshot capture:
      `post_send_screenshot_bound=true`, `post_send_screenshot_mode=bound-window`
- 2026-05-27 started the Background-Safe Control Layer:
  - direction:
    - shifted from proving foreground control works to making the system decide
      whether an action can run without stealing focus
    - added a pure plan-only transport capability matrix before adding more live
      app actions
  - added `openwukong.control.transport_capability`
    - classifies route plan + intent into:
      `background-native`, `background-read-only`, `foreground-required`, or
      `blocked`
    - records:
      selected transport, transport channel, focus-safety, confirmation need,
      risk flags, verification requirements, and fallback transports
    - currently maps:
      browser DevTools, IDE extension, Terminal native session, Git CLI, Office
      object model, UIA semantic, UIA structural read-only, missing native bridge
      foreground fallback, and no-route blocks
  - integrated the matrix into `ControlFabric` dispatch reports:
    - report now embeds `transport_capability`
    - top-level report exposes:
      `transport_capability_level`, `selected_transport`,
      `can_execute_without_focus`, and
      `transport_requires_user_confirmation`
  - TDD coverage added:
    - RED verified first for missing `openwukong.control.transport_capability`
    - tests cover:
      background-native browser DevTools, foreground-required WeChat send without
      native bridge, background-read-only structural UIA, blocked overlay, and
      ControlFabric report embedding
  - current verification:
    - focused transport capability tests:
      `5 tests` passed
    - related route/fabric regression suite:
      `25 tests` passed
    - targeted compileall over `src/openwukong/control` passed
  - next high-value steps:
    - add a CLI/report endpoint for the transport capability matrix
    - enforce foreground-required actions through a user-visible confirmation gate
    - add OCR/accessibility post-action verification for foreground transports
- 2026-05-27 added the transport capability matrix CLI/report endpoint:
  - direction:
    - made the Background-Safe Control Layer runnable as a standalone read-only
      profile before enforcing it in live execution paths
  - added `openwukong.evaluation.transport_capability_matrix`
    - CLI:
      `python -m openwukong.evaluation.transport_capability_matrix`
    - accepts action/text/max window options
    - emits JSON with:
      `background_native`, `background_read_only`, `foreground_required`,
      `blocked`, `can_execute_without_focus`, and
      `requires_user_confirmation`
    - writes optional JSON artifacts through `--output`
    - remains `plan_only` with `control_allowed=false` and
      `control_attempts=0`
  - live read-only validation:
    - command:
      `python -m openwukong.evaluation.transport_capability_matrix --max-windows 3 --max-elements 20 --action read_text --json`
    - result:
      scanned `3` windows, classified `2` as `background-native` read paths and
      `1` as `blocked`
    - no control attempts were made
  - TDD coverage added:
    - RED verified first for missing
      `openwukong.evaluation.transport_capability_matrix`
    - tests cover JSON output, WeChat send foreground-required classification,
      and `--output` artifact writing
  - current verification:
    - transport profile tests:
      `3 tests` passed
    - related transport/control profile regression suite:
      `22 tests` passed
    - `compileall -q src tests` passed
  - next high-value steps:
    - enforce this matrix before any real execution call
    - route `foreground-required` actions into an explicit foreground takeover
      request rather than letting callers invoke them silently
    - add post-action OCR/accessibility verification for foreground transports
- 2026-05-27 enforced the transport capability matrix before real execution:
  - direction:
    - moved the matrix from reporting-only into the `ControlFabric.execute`
      safety path
    - any explicit real execution now evaluates transport capability before
      connector/action-runner dispatch
  - updated `openwukong.control.fabric`
    - `ControlExecutionReport` now includes:
      `transport_gate_decision` and `transport_gate_error`
    - foreground-required transports are blocked with:
      `transport_gate_decision=blocked_foreground_takeover_required`
      and `error=foreground_takeover_confirmation_required`
    - no-route/blocked transports are blocked with:
      `transport_gate_decision=blocked_transport_capability`
      and `error=transport_capability_blocked`
    - background-native connector execution remains allowed after the gate
  - TDD coverage added:
    - RED verified first in `tests/test_control_fabric_execution.py`
    - tests cover:
      foreground-required WeChat send blocking, blocked overlay transport
      blocking, and browser DevTools background-native execution still passing
  - live read-only CLI validation:
    - command:
      `python -m openwukong.evaluation.control_fabric_execute --process-name Weixin.exe --window-title 微信 --action send_message --text probe --allow-control --json`
    - result:
      `ok=false`, `control_attempts=0`,
      `transport_gate_decision=blocked_foreground_takeover_required`,
      `error=foreground_takeover_confirmation_required`
    - no app connector, action runner, keyboard, or clipboard control was called
  - current verification:
    - control fabric execution tests:
      `17 tests` passed
    - related transport/control regression suite:
      `40 tests` passed
    - `compileall -q src tests` passed
  - next high-value steps:
    - create an explicit foreground takeover request object/report instead of
      only returning an error
    - wire WeChat send probe to consume that request object before any foreground
      keyboard/clipboard action
    - add OCR/accessibility verification after foreground takeover completes
- 2026-05-27 added explicit foreground takeover request contracts:
  - direction:
    - upgraded foreground-required control from a plain blocking error into an
      auditable request object that downstream probes must validate before any
      keyboard, clipboard, mouse, or foreground-focus primitive can run
    - kept the background-safe control boundary intact: foreground takeover is
      still blocked at `ControlFabric.execute` and only emitted as a request for
      a narrower, app-specific probe to consume
  - added `openwukong.control.foreground_takeover`
    - `ForegroundTakeoverRequest` records:
      action, app family, target process/window, selected route, selected
      transport, risk flags, verification requirements, request status, and a
      stable request id
    - `validate_foreground_takeover_request` rejects missing requests, action
      mismatch, transport mismatch, target mismatch, and invalid request status
    - validation reports are read-only and always keep:
      `control_allowed=false` and `control_attempts=0`
  - updated `openwukong.control.fabric`
    - `ControlExecutionReport` now embeds `foreground_takeover_request` when a
      foreground-required transport is blocked
    - WeChat-style foreground fallback now returns a concrete request with:
      `selected_transport=foreground-keyboard-clipboard` and verification
      requirements for pre-action target verification, post-action bound-window
      verification, and state restoration
  - updated `openwukong.evaluation.wechat_send_probe`
    - real File Transfer Assistant send now requires a valid foreground takeover
      request before it attempts to find a window, focus WeChat, write clipboard,
      or send keyboard input
    - missing request is blocked as
      `blocked_foreground_takeover_request_required`
    - invalid request is blocked as
      `blocked_foreground_takeover_request_invalid`
    - CLI accepts `--foreground-takeover-request` and can read either a direct
      request JSON or a full execution report containing
      `foreground_takeover_request`
    - successful send reports now include a `post_action_verify` phase plus
      `post_send_verified` and `post_send_verification` fields, ready for OCR or
      accessibility readback implementations
  - TDD coverage added:
    - RED verified first for missing
      `openwukong.control.foreground_takeover`
    - RED verified first for WeChat sending without takeover request still
      reaching the send path
    - RED verified first for missing post-send verification fields
    - tests cover:
      ControlFabric request emission, request validation, WeChat missing-request
      blocking, valid-request send path, explicit target confirmation override,
      and optional post-send accessibility verification
  - current verification:
    - foreground takeover + WeChat send probe tests:
      `9 tests` passed
    - related control/transport regression suite:
      `25 tests` passed
  - next high-value steps:
    - replace the optional post-send verifier stub with a real OCR/accessibility
      readback implementation for the bound WeChat HWND
    - add a CLI flow that emits a takeover request, pauses for operator approval,
      then consumes the approved request in the WeChat probe
    - generalize foreground takeover request consumption for other foreground
      fallback probes so the safety contract is uniform across apps
- 2026-05-27 added a unified desktop task runner for app launch, browser search,
  and WeChat send:
  - direction:
    - moved from separate probes toward a single gated user-task entrypoint
    - kept the safety model explicit:
      launch requires `allow_launch`; browser search uses DevTools when
      available and otherwise requires launch/open permission; WeChat send
      requires explicit send permission, foreground takeover approval, and an
      additional external-communication permission for non-File-Transfer targets
  - added `openwukong.evaluation.desktop_task_runner`
    - `run_desktop_task(...)` supports:
      `open_app`, `browser_search`, and `wechat_send`
    - report mode:
      `desktop-task-runner`
    - shared counters:
      `launch_attempts`, `browser_navigation_attempts`, `send_attempts`,
      `control_allowed`, selected transport, and nested subreports
    - app launch path:
      resolves software from Windows Start Menu entries and launches without
      shell-string command composition
    - browser search path:
      builds encoded Bing search URLs
      uses `browser-devtools-or-extension` when a debugger URL is provided
      falls back to system browser URL open only after `allow_launch`
    - WeChat send path:
      obtains a foreground takeover request from `ControlFabric`
      returns `foreground_takeover_request_pending` until approved
      consumes the request through the WeChat send probe after approval
      supports the existing second-stage `confirm_target_after_open` operator
      confirmation for real foreground sends
  - updated `openwukong.evaluation.wechat_send_probe`
    - non-File-Transfer targets are no longer treated as the same generic
      invalid target
    - they now require `allow_external_target`
    - default blocked status:
      `blocked_external_target_requires_explicit_permission`
    - this gives a controlled route for "send message to a person" while keeping
      accidental external communication blocked by default
  - TDD coverage added:
    - RED verified first for missing `desktop_task_runner`
    - RED verified first for WeChat external-target permission behavior
    - tests cover:
      open-app launch permission, Start Menu launcher dispatch, browser DevTools
      search, system-browser search fallback gate, foreground takeover request
      pending state, approved WeChat send, second-stage target confirmation, and
      external-target send blocking
  - safe CLI smoke validation:
    - `open_app --app-name wechat --json` returned
      `blocked_launch_requires_explicit_permission` with `launch_attempts=0`
    - `browser_search --query openwukong --json` returned
      `blocked_browser_requires_debugger_or_launch_permission` with
      `browser_navigation_attempts=0`
    - `wechat_send --target-name 文件传输助手 --message hello --allow-send --json`
      returned `foreground_takeover_request_pending` with `send_attempts=0`
      and a concrete `foreground_takeover_request`
  - current verification:
    - desktop task runner tests:
      `9 tests` passed
    - WeChat send probe tests:
      `9 tests` passed
    - related desktop task / WeChat / foreground / browser / control fabric
      regression suite:
      `46 tests` passed
  - next high-value steps:
    - add an approval-file workflow that writes a takeover request JSON and then
      consumes an approved request for real WeChat sends
    - add real bound-window OCR/accessibility verification for WeChat post-send
      success instead of only optional injected verifier support
    - add a browser research/extraction task on top of opened search results
      using DevTools DOM extraction
- 2026-05-27 ran real background-safe desktop task validation and fixed issues
  found during live testing:
  - real test policy update:
    - prefer background/owned connector tests before foreground tests
    - browser real tests should use DevTools/CDP on an owned headless or already
      debuggable browser when possible
    - WeChat cannot currently send in the background; the safe background test is
      read-only locator evidence plus foreground takeover request generation
    - foreground WeChat sending remains available only when explicitly approved
  - real findings:
    - `open_app --app-name wechat --allow-launch` initially resolved the Start
      Menu shortcut for Enterprise WeChat
    - after excluding Enterprise WeChat, read-only resolution found WeChat Input
      Method, exposing that personal WeChat launch must use exact aliases rather
      than substring matching
    - no existing browser DevTools endpoint was available on ports
      `9222/9223/9238/9333`
    - owned/headless Chrome DevTools background navigation worked without using
      the user's foreground browser
    - a first owned Chrome cleanup attempt stopped only the parent process; child
      Chromium processes kept the profile locked, so cleanup must kill by exact
      owned `--user-data-dir`
    - CDP navigation can return `errorText`; this must be treated as failure, not
      a successful browser action
  - fixes:
    - tightened `WindowsAppLauncher.resolve("wechat")` so it will not launch
      Enterprise WeChat or WeChat Input Method as personal WeChat
    - added exact personal-WeChat alias matching; if no exact shortcut exists,
      report `app_not_found` instead of launching a nearby product
    - updated Browser DevTools action handling so `Page.navigate` `errorText`
      produces `ok=false`, `control_allowed=false`, and an auditable
      `navigation_failed:*` error while preserving the CDP result
  - real validation:
    - read-only personal WeChat launch resolution now returns
      `app_not_found` on this machine instead of opening Enterprise WeChat or
      WeChat Input Method
    - background owned/headless Chrome positive navigation succeeded:
      post-action title was `OpenWukong_BG`, transport was
      `chrome-devtools-protocol`, and cleanup removed the owned profile
    - background owned/headless browser search succeeded through CDP:
      query `OpenWukong_background_search_20260527`, title read back
      `OpenWukong_background_search_20260527 - 搜索`
    - WeChat background send validation returned
      `foreground_takeover_request_pending`, `send_attempts=0`, and a concrete
      `foreground_takeover_request`
    - primary real no-loss summary passed `4/4` cases with:
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`, and `owned_app_launch_attempts=0`
  - reusable skill created:
    - `desktop-background-control-testing`
    - location:
      `C:\Users\Zhangjinqian\.codex\skills\desktop-background-control-testing`
    - captures:
      background-first testing, exact app resolution, CDP `errorText` handling,
      owned browser process cleanup, and foreground takeover gating
    - validation:
      `quick_validate.py` returned `Skill is valid!`
  - current unit coverage:
    - desktop task runner tests now include:
      Enterprise WeChat exclusion, WeChat Input Method exclusion, and exact
      personal WeChat preference
    - browser DevTools action tests now include:
      navigation error handling for CDP `errorText`
  - next high-value steps:
    - add explicit app path configuration for personal WeChat, since this machine
      lacks an exact personal WeChat Start Menu shortcut
    - add owned/headless browser helper support directly to
      `desktop_task_runner` so background browser testing does not require an
      external script wrapper
    - implement real OCR/accessibility post-send verification before expanding
      foreground WeChat sends beyond File Transfer Assistant
- 2026-05-27 replaced fixed app-path thinking with a dynamic App Identity
  Resolver:
  - direction:
    - user clarified that a shipped product cannot rely on fixed local paths
    - corrected the plan from "explicit app path registry" to a dynamic app
      identity/resolver layer with local cache support, not a hardcoded path
      table
  - updated `openwukong.evaluation.desktop_task_runner`
    - added app identity primitives:
      `AppIdentity`, `AppIdentityRegistry`, `AppResolutionCandidate`,
      `AppResolutionReport`, and `WindowsAppResolver`
    - resolver layers now include:
      running process detection, optional local cache JSON, Start Menu entries,
      Windows App Paths registry, and PATH executable lookup
    - built-in identities include exact/exclusion rules for:
      personal WeChat, Cursor, Chrome, and Edge
    - personal WeChat is identity-matched by exact aliases/processes:
      `微信`, `wechat`, `weixin`, `Weixin.exe`, `WeChat.exe`
    - personal WeChat explicitly excludes:
      Enterprise WeChat, WeCom/WXWork, Work WeChat, and WeChat Input Method
    - same executable path across multiple running processes is deduped into one
      running app candidate; different equally ranked paths remain ambiguous and
      blocked
    - `open_app` now returns `app_already_running` when the target app is already
      running, with `launch_attempts=0` and no foreground/focus action
  - real validation:
    - `open_app --app-name wechat --allow-launch --json` now resolves the live
      running personal WeChat process from:
      `E:\software\Weixin\Weixin.exe`
    - report status:
      `app_already_running`
    - no launch was attempted:
      `launch_attempts=0`
    - CLI exit code now treats `app_already_running` as success
  - TDD coverage added:
    - RED verified first for missing resolver primitives
    - RED verified first for multiple live WeChat child processes with the same
      executable path being misclassified as ambiguity
    - tests cover:
      Enterprise WeChat exclusion, WeChat Input Method exclusion, exact personal
      WeChat preference, running-process preference, same-path running-process
      dedupe, ambiguous same-priority different paths, local cache candidate
      use, and success exit code for `app_already_running`
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added the rule that same executable path across multiple running processes
      should be deduped, while same-rank different paths should remain ambiguous
    - `quick_validate.py` returned `Skill is valid!`
  - next high-value steps:
    - move the resolver out of `desktop_task_runner` into a reusable
      `control/app_resolution` module once another caller needs it
    - add signed-binary or product-metadata verification for cached paths before
      launch
    - add a local cache write path after a high-confidence resolution succeeds
- 2026-05-28 promoted app resolution into the reusable control layer:
  - direction:
    - continued the dynamic identity/resolver route instead of fixed app paths
    - made application discovery a shared control-layer capability, not a
      private implementation detail of `desktop_task_runner`
  - added `openwukong.control.app_resolution`
    - owns:
      `AppIdentity`, `AppIdentityRegistry`, `AppResolutionCandidate`,
      `AppResolutionReport`, candidate providers, and `WindowsAppResolver`
    - keeps resolver sources centralized:
      running processes, optional local cache, Start Menu, Windows App Paths,
      and PATH executable lookup
    - preserves strict personal-WeChat identity matching and exclusions for
      Enterprise WeChat, WeCom/WXWork, Work WeChat, and WeChat Input Method
  - updated public control exports:
    - `from openwukong.control import WindowsAppResolver` now works
    - `desktop_task_runner` now consumes the shared control-layer resolver and
      no longer defines its own private resolver classes
  - safe real validation:
    - ran direct read-only resolution through `WindowsAppResolver().resolve("wechat")`
    - result:
      `ok=true`, `source=running-process`, `already_running=true`
    - resolved personal WeChat path:
      `E:\software\Weixin\Weixin.exe`
    - no launch, focus, keyboard, clipboard, mouse, or app operation was made
  - TDD coverage added:
    - RED verified first for missing `openwukong.control.app_resolution`
    - RED verified first for missing package-level `openwukong.control`
      resolver export
    - tests cover:
      control-layer resolver import, running-process preference, and package
      export stability
  - current verification:
    - app resolution + desktop task runner tests:
      `19 tests` passed
  - next high-value steps:
    - add signed-binary or product-metadata verification for cached paths before
      launch
    - add a local cache write path after a high-confidence resolution succeeds
    - route Browser/Cursor/Codex task entrypoints through the shared
      `control.app_resolution` module instead of local ad-hoc discovery
- 2026-05-28 added verified app-resolution cache write/read safety:
  - direction:
    - made dynamic app discovery reusable across sessions without trusting stale
      local paths
    - kept cache behavior explicit and evidence-based:
      high-confidence discoveries can be cached, but cached paths must be
      revalidated before they are used
  - updated `openwukong.control.app_resolution`
    - added `AppPathVerification` and `AppPathVerifier`
    - added optional `PowerShellAuthenticodeSignatureReader` using read-only
      `Get-AuthenticodeSignature -LiteralPath`
    - `WindowsAppResolver(cache_write_enabled=True)` now writes cache entries
      only after a high-confidence resolution succeeds and the selected path
      passes file metadata verification
    - cache entries store:
      path, display name, executable name, source, cached time, file size,
      modification time, and optional Authenticode signature metadata
    - `LocalCacheAppCandidateProvider` now revalidates cached file metadata
      before returning a local-cache candidate
    - stale cached paths with mismatched file metadata are ignored and normal
      discovery continues
  - safe real validation:
    - resolved live personal WeChat through the shared resolver with a temporary
      cache file and `cache_write_enabled=True`
    - result:
      `ok=true`, `source=running-process`, `already_running=true`
    - cached path:
      `E:\software\Weixin\Weixin.exe`
    - cached size:
      `3130416`
    - no launch, focus, keyboard, clipboard, mouse, or app operation was made
    - temporary cache file was deleted after validation
  - TDD coverage added:
    - RED verified first for missing `AppPathVerifier`
    - tests cover:
      high-confidence resolution cache write, stale metadata cache rejection,
      and Authenticode signature metadata capture through an injected reader
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added app-resolution cache safety rules:
      write only after high-confidence discovery, store file/signature metadata,
      revalidate before launch, and ignore stale cache entries
    - `quick_validate.py` returned `Skill is valid!`
  - current verification:
    - app resolution + desktop task runner tests:
      `22 tests` passed
  - next high-value steps:
    - route Browser/Cursor/Codex task entrypoints through the shared
      `control.app_resolution` module instead of local ad-hoc discovery
    - add publisher allowlist policy on top of Authenticode metadata for
      launch-sensitive apps
    - add a resolver CLI/report endpoint for user-facing diagnostics
- 2026-05-28 added a read-only app resolution diagnostics endpoint:
  - direction:
    - turned the shared application resolver into a user-facing diagnostics
      surface that higher-level task runners and UI panels can consume
    - kept the endpoint strictly read-only by default:
      no launch, focus, keyboard, clipboard, mouse, or foreground control
  - added `openwukong.evaluation.app_resolution_report`
    - CLI:
      `python -m openwukong.evaluation.app_resolution_report --app-name wechat --json`
    - supports repeated `--app-name`
    - supports optional `--cache-path`, `--write-cache`, `--verify-signature`,
      `--output`, `--json`, and `--strict`
    - report mode:
      `app-resolution-report`
    - safety fields:
      `safety_mode=read_only`, `control_allowed=false`,
      `control_attempts=0`
    - summary fields:
      app count, resolved count, not-found count, ambiguous count,
      already-running count, cache-write flag, and signature-verification flag
    - per-app entries include:
      selected source/path, already-running state, candidate count, selected
      candidate, and the full underlying `AppResolutionReport`
  - fixed a precision issue found by the new endpoint:
    - live `chrome` diagnostics initially included `Tabbit Browser` as a
      candidate because generic alias `browser` was used as a fuzzy candidate
      substring
    - tightened `candidate_matches_identity` so aliases resolve user input but
      do not fuzzy-match candidate display names
    - `browser` remains a user request alias for Chrome, but no longer pulls in
      unrelated browser-branded shortcuts
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.app_resolution_report --app-name wechat --app-name chrome --app-name cursor --json`
    - result:
      `app_count=3`, `resolved=3`, `not_found=0`, `ambiguous=0`,
      `already_running=2`, `control_attempts=0`
    - resolved:
      personal WeChat from `E:\software\Weixin\Weixin.exe`,
      Chrome from the Google Chrome Start Menu shortcut plus App Paths registry
      evidence, and Cursor from the running process plus Start Menu evidence
    - after the precision fix, Chrome candidates no longer include
      `Tabbit Browser`
  - TDD coverage added:
    - RED verified first for missing
      `openwukong.evaluation.app_resolution_report`
    - RED verified first for generic `browser` alias mixing unrelated browser
      shortcuts into Chrome candidates
    - tests cover:
      read-only report contract, ambiguous summary, JSON output writing, and
      generic browser shortcut exclusion
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added rule that generic words such as `browser` should be request aliases
      only, never candidate-name substring matches
    - `quick_validate.py` returned `Skill is valid!`
  - next high-value steps:
    - route `desktop_task_runner` app opening through the new diagnostics/cache
      flags so open tasks can persist high-confidence discoveries
    - add publisher allowlist policy on top of Authenticode metadata for
      launch-sensitive apps
    - add Cursor/Codex task entrypoints that bind through `control.app_resolution`
      before using IDE bridge/native connectors
- 2026-05-28 started Codex/Claude agent-surface integration:
  - status clarification:
    - browser background CDP control and WeChat File Transfer real-send have
      passed key real validations, but the primary scenarios are not all
      productized yet
    - file search and live Codex/Claude task submission remain gated work
    - Codex/Claude are now connected at the safe discovery/binding layer, not
      at uncontrolled real task execution
  - expanded shared app resolution:
    - added default identities for `codex` and `claude`
    - Codex aliases now include `openai codex`, `codex cli`,
      `codex app`, and `codex ide`
    - Claude aliases now include `claude code`, `anthropic claude`,
      `claude cli`, and `claude desktop`
    - fixed multi-process Codex ambiguity by preferring the primary
      `Codex.exe` desktop shell over helper/extension/worker `codex.exe`
      processes for app identity resolution
  - added `openwukong.control.agent_surface`
    - maps resolved agent products to transport surfaces without executing
      anything
    - Codex surfaces:
      standalone Codex CLI as `codex-cli-managed-terminal`,
      Codex desktop shell as `codex-desktop-shell`,
      helper/extension workers as evidence-only `codex-extension-worker`
    - Claude surfaces:
      Claude Code CLI as `claude-code-cli-managed-terminal`
    - all real task submission remains blocked behind side-effect effects:
      `agent_task_submission.submit_task` and `agent_start.start_agent`
  - added `openwukong.evaluation.agent_surface_report`
    - CLI:
      `python -m openwukong.evaluation.agent_surface_report --agent codex --agent claude --json`
    - report mode:
      `agent-surface-report`
    - safety fields:
      `safety_mode=read_only`, `control_allowed=false`,
      `control_attempts=0`
    - output includes selected transport, all transport candidates,
      app-resolution evidence, and side-effect gate state
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_surface_report --agent codex --agent 'openai codex' --agent claude --agent 'claude code' --json`
    - result:
      `agent_count=4`, `resolved=4`, `not_found=0`,
      `transport_not_ready=0`, `background_capable=4`,
      `confirmation_required=4`, `control_attempts=0`
    - Codex selected transport:
      `codex-cli-managed-terminal` from
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\958d608b5e0546a5\codex.exe`
    - Codex app resolution still selects the desktop shell
      `C:\Program Files\WindowsApps\OpenAI.Codex_26.519.11010.0_x64__2p2nqsd0c76g0\app\Codex.exe`
      while keeping resource/extension helper processes as evidence only
    - Claude selected transport:
      `claude-code-cli-managed-terminal` from
      `C:\Users\Zhangjinqian\.local\bin\Claude.exe`
    - no launch, focus, keyboard, clipboard, mouse, shell command execution,
      Codex task submission, or Claude task submission occurred
  - TDD coverage added:
    - RED verified for missing `agent_surface_report`
    - RED verified for missing `openwukong.control` package export
    - tests cover:
      Codex CLI-vs-desktop-vs-helper transport classification,
      Claude Code CLI classification, read-only JSON output, and package export
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added a multi-surface agent-product rule:
      split product discovery from task-submission transport selection; prefer
      configured native/IDE bridge or standalone CLI for background task
      submission; keep desktop shells as foreground/bridge-required surfaces;
      treat helper/extension worker processes as evidence only
    - no `quick_validate.py` exists in this skill directory in the current
      environment, so validation is covered by targeted project tests
  - current verification:
    - targeted agent/app resolution tests:
      `19 tests` passed
  - next high-value steps:
    - add a guarded agent-task draft/execute contract that uses
      `AgentSurfaceBindingReport` and requires explicit confirmation before
      real Codex/Claude task submission
    - wire Codex bridge/CLI and Claude CLI into `ControlFabric` with the same
      side-effect gate used by primary scenarios
    - add real no-loss smoke tests for Codex/Claude with dry-run/no-op prompts
      before enabling any destructive or long-running agent action
- 2026-05-28 added guarded Codex/Claude agent task contracts:
  - direction:
    - moved from agent surface discovery to a staged task contract:
      draft-only by default, dry-run command planning, and confirmed execution
      only after explicit agent side-effect confirmation
    - this keeps Codex/Claude integration on the same background-safe control
      path as browser/terminal/WeChat instead of bypassing gates through CLI
      shortcuts
  - added `openwukong.control.agent_task`
    - `run_agent_task(...)` produces an `agent-task-runner` report
    - default behavior writes a local `agent-task-draft` artifact and never
      executes Codex/Claude
    - command contracts:
      - Claude Code:
        `claude -p --permission-mode plan --max-turns 1 --output-format json --no-session-persistence <task>`
      - Codex:
        `codex exec <task>` through the resolved standalone Codex CLI surface
    - real execution requires:
      `execute=true`, `allow_agent_task=true`, confirmed
      `agent_task_submission.submit_task`, and confirmed
      `agent_start.start_agent`
    - dry-run builds the command plan after confirmation but keeps
      `agent_command_attempts=0`
  - added `openwukong.evaluation.agent_task_runner`
    - CLI:
      `python -m openwukong.evaluation.agent_task_runner --agent claude --task "..."`
    - supports:
      `--workspace-root`, `--output-root`, `--execute`, `--dry-run`,
      `--allow-agent-task`, repeated `--confirm-effect`, `--timeout-sec`,
      `--audit-log`, `--output`, `--json`, and `--strict`
    - report fields include:
      selected transport, command plan, side-effect gate, draft artifact path,
      execution status, execution report, and command attempt count
  - safe real validation:
    - Claude draft-only command:
      `python -m openwukong.evaluation.agent_task_runner --agent claude --task 'No-op draft only...' --workspace-root . --output-root logs\runtime\agent-tasks --json`
    - result:
      `decision=draft_written`, `safety_mode=draft_only`,
      `execution_requested=false`, `execution_attempted=false`,
      `agent_command_attempts=0`
    - Codex dry-run command with both agent effects confirmed:
      `python -m openwukong.evaluation.agent_task_runner --agent codex --task 'No-op dry run only...' --workspace-root . --output-root logs\runtime\agent-tasks --execute --dry-run --allow-agent-task --confirm-effect agent_task_submission.submit_task --confirm-effect agent_start.start_agent --json`
    - result:
      `decision=dry_run_ready`, `safety_mode=dry_run`,
      `side_effect_gate.allowed=true`, `execution_attempted=false`,
      `agent_command_attempts=0`
    - Claude unconfirmed execute request:
      `python -m openwukong.evaluation.agent_task_runner --agent claude --task 'No-op execute request should be blocked.' --workspace-root . --output-root logs\runtime\agent-tasks --execute --json`
    - result:
      `decision=agent_task_confirmation_required`,
      `execution_attempted=false`, `agent_command_attempts=0`
    - no real Codex/Claude task was submitted or started in these validations
  - TDD coverage added:
    - RED verified first for missing `run_agent_task`
    - tests cover:
      default Claude draft-only behavior, unconfirmed Codex execute blocking,
      confirmed dry-run with zero command attempts, confirmed execution through
      an injected command executor, and CLI JSON artifact output
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added staged agent task contract rules:
      draft-only by default, dry-run command planning, confirmed execute only
      after both agent side-effect confirmations, and dry-run/unconfirmed execute
      must keep command attempts at zero
  - next high-value steps:
    - connect `agent_task_runner` into `ControlFabric` so higher-level tasks can
      invoke the same guarded contract without calling the CLI directly
    - add a real no-op confirmed execution test only after explicitly choosing
      the execution surface and accepting token/network side effects
    - add result readback/parsing for Codex/Claude execution reports before
      enabling long-running project tasks
- 2026-05-28 ran real Codex/Claude live no-loss agent tests:
  - user explicitly authorized real testing
  - test isolation:
    - all live agent tests ran in temporary empty workspaces under `%TEMP%`
    - no foreground focus, keyboard, clipboard, mouse, browser, WeChat, or
      current project app interaction was used
    - after each live test, the temporary workspace was recursively inspected
      and remained empty
  - Claude live test:
    - command path:
      `agent_task_runner --agent claude --execute --allow-agent-task ...`
    - actual command plan invoked:
      `Claude.exe -p --permission-mode plan --max-turns 1 --output-format json --no-session-persistence <no-op prompt>`
    - result:
      `decision=execution_failed`, `execution_attempted=true`,
      `agent_command_attempts=1`, `execution_error=exit_code=1`
    - stdout reported:
      `Not logged in - Please run /login`
    - `claude auth status --text` confirmed:
      `Not logged in. Run claude auth login to authenticate.`
    - no model work was performed by Claude and the temp workspace stayed empty
  - Codex CLI safety fix before live execution:
    - local `codex exec --help` showed that `--ask-for-approval` is a top-level
      Codex flag, not an `exec` subcommand flag
    - RED test added to enforce safe flag ordering
    - updated `build_agent_command_plan` so Codex uses:
      `codex --sandbox read-only --ask-for-approval never -C <temp-workspace> exec --skip-git-repo-check --ephemeral --ignore-rules --json <no-op prompt>`
    - targeted agent task tests passed after the fix
  - Codex live test:
    - command path:
      `agent_task_runner --agent codex --execute --allow-agent-task ...`
    - result:
      `decision=executed`, `ok=true`, `execution_attempted=true`,
      `agent_command_attempts=1`, `execution_ok=true`
    - stdout JSONL included:
      `thread.started`, `turn.started`, and an agent message:
      `OPENWUKONG_AGENT_LIVE_SMOKE_OK`
    - reported usage:
      `input_tokens=19073`, `cached_input_tokens=10112`,
      `output_tokens=189`, `reasoning_output_tokens=173`
    - temp workspace inspection showed no files written
  - live issue discovered:
    - Codex stderr reported several global skill load errors caused by missing
      YAML frontmatter in existing skill files:
      `altmind-native-ime-ranking-regression`,
      `altmind-semantic-memory-learning-compatibility`, and
      `debug-async-ui`
    - this did not block the no-op task, but it should be fixed separately
      because it pollutes real Codex agent startup
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added the safe live Codex CLI smoke command shape and completion check
      for empty/expected temp workspace contents
  - current conclusion:
    - Codex real background no-loss task execution is proven
    - Claude CLI surface is installed and callable, but not authenticated on
      this machine, so live Claude execution is blocked by auth rather than by
      our control layer
  - next high-value steps:
    - fix malformed global skill frontmatter so Codex live runs start cleanly
    - add structured parsing of Codex JSONL and Claude JSON execution outputs
      into `AgentTaskRunReport`
    - after Claude login, rerun the same no-loss `claude -p` live smoke
- 2026-05-28 added explicit agent app/desktop surface support:
  - user clarified that Claude integration must cover the application side,
    not only the CLI
  - implementation:
    - added `WindowsStartAppsCandidateProvider` so packaged Windows apps can be
      discovered via `Get-StartApps` and AppUserModelID without launching them
    - added Claude/Codex app and desktop aliases while keeping product identity
      separate from transport selection
    - made agent surface binding request-aware:
      `claude app`, `claude desktop`, `codex app`, and `codex desktop` now
      require an app/desktop shell surface and are not silently satisfied by CLI
    - added Claude Desktop shell transport:
      `claude-desktop-shell`, `desktop-shell-native-bridge-or-foreground`,
      `background_capable=false`, `execution_allowed=false`
    - generic `claude` and `codex` still report all discovered surfaces and
      prefer the background-capable CLI for confirmed agent task execution
  - root-cause fix:
    - real diagnostics initially lost `Get-StartApps` data because Python text
      mode decoded PowerShell stdout with the local GBK codec and hit a Unicode
      decode error
    - fixed by forcing PowerShell UTF-8 output and decoding stdout bytes
      explicitly
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_surface_report --agent "claude desktop" --agent "claude" --agent "codex app" --agent "codex" --json`
    - result:
      `agent_count=4`, `resolved=4`, `not_found=0`,
      `transport_not_ready=0`, `background_capable=2`,
      `confirmation_required=4`, `control_attempts=0`
    - `claude desktop` selected:
      `claude-desktop-shell`, source `start-apps`,
      target `Claude_pzs8sxrjxfjjc!Claude`, background disabled
    - generic `claude` selected:
      `claude-code-cli-managed-terminal`, with Claude Desktop shell also
      reported as a non-background app surface
    - `codex app` selected:
      `codex-desktop-shell`, source `running-process`,
      target current Codex Desktop executable, background disabled
    - generic `codex` selected:
      `codex-cli-managed-terminal`, with Codex Desktop shell and helper workers
      reported separately
    - no app launch, focus takeover, keyboard, clipboard, mouse, or agent task
      submission occurred
  - TDD coverage added:
    - app/desktop requests are not satisfied by CLI-only candidates
    - Claude generic request reports both CLI and desktop surfaces while
      preferring the background CLI
    - StartApps provider parses packaged app entries and UTF-8 stdout bytes
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added explicit app/desktop-vs-CLI surface rules and Windows StartApps
      UTF-8 handling notes
  - next high-value steps:
    - add a native/UIA bridge probe for Claude Desktop and Codex Desktop that
      only reads app state first, then gates any foreground task submission
    - keep CLI as the only proven background Codex execution route until a
      desktop native bridge is available
    - after Claude login, validate CLI no-loss execution separately from
      desktop app surface testing
- 2026-05-28 added targeted AI conversation message and acceptance contract:
  - direction:
    - moved above raw `agent_task_runner` into a conversation-aware envelope:
      agent, project name, task/session name, message body, acceptance
      criteria, required markers, and forbidden markers
    - this is the common layer for future Codex App, Claude App, Cursor chat,
      Claude CLI, and Codex CLI task/message delivery
  - added `openwukong.control.agent_conversation`
    - `run_agent_conversation(...)`
    - `compose_agent_conversation_message(...)`
    - `evaluate_agent_conversation_acceptance(...)`
    - wraps the existing staged `agent_task_runner` instead of bypassing the
      side-effect gates
    - draft-only remains the default behavior
    - confirmed execute still requires:
      `agent_task_submission.submit_task`, `agent_start.start_agent`, and
      `allow_agent_task=true`
    - app/desktop surfaces with no command contract now return:
      `agent_conversation_requires_app_bridge_or_foreground`
      plus a `foreground_takeover_request` describing the app bridge/foreground
      requirements
  - added `openwukong.evaluation.agent_conversation_runner`
    - CLI supports:
      `--agent`, `--project-name`, `--task-name`, `--message`,
      repeated `--acceptance-criterion`, repeated `--acceptance-marker`,
      repeated `--forbid-marker`, `--execute`, `--dry-run`,
      `--allow-agent-task`, repeated `--confirm-effect`, `--output`, `--json`
    - report includes:
      composed message, selected transport, foreground request if needed,
      nested agent-task report, command attempts, and acceptance report
  - safe real validation:
    - draft-only Codex targeted message:
      `agent_conversation_runner --agent codex --project-name openwukong --task-name agent-conversation-contract ... --json`
      returned `decision=conversation_draft_written`,
      `agent_command_attempts=0`
    - Claude Desktop app-surface execute request:
      `agent_conversation_runner --agent "claude desktop" ... --execute ...`
      returned
      `decision=agent_conversation_requires_app_bridge_or_foreground`,
      `selected_transport=claude-desktop-shell`,
      `agent_command_attempts=0`, and a foreground/native bridge request
    - real Codex CLI no-loss conversation execution in an empty `%TEMP%`
      workspace:
      returned `decision=conversation_executed_and_accepted`, `ok=true`,
      `agent_command_attempts=1`
      with required markers:
      `OPENWUKONG_ACCEPTANCE: PASS` and `CONVERSATION_READBACK_OK`
    - recursive inspection of the temporary workspace after the live run:
      `ItemCount=0`
  - live issue still present:
    - Codex stderr still reports global skill frontmatter/YAML errors and
      Windows sandbox spawn setup warnings
    - this is separate startup hygiene and should be fixed before relying on
      long-running real Codex tasks
  - TDD coverage added:
    - conversation draft writes project/task/message/acceptance envelope
    - confirmed dry-run builds Codex command with the targeted message
    - fake confirmed execute accepts result markers
    - app surface execution request emits foreground/native bridge request
    - CLI JSON report writes the conversation report
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added targeted agent chat envelope and acceptance-marker validation rules
  - next high-value steps:
    - add read-only Codex/Claude Desktop UIA probe to identify project/task
      labels, chat transcript, and composer candidates without focus takeover
    - add a foreground/native bridge consumer for app surfaces only after the
      read-only probe can prove target project/task identity
    - fix malformed global Codex skill frontmatter so real Codex runs start
      without noisy startup errors
- 2026-05-28 added and live-tested read-only agent app UIA probe:
  - implementation:
    - added `openwukong.evaluation.agent_app_uia_probe`
    - supports live UIA scanning and replay from saved `accessibility_probe`
      JSON files
    - binds the requested agent app surface first, then filters matching app
      windows by agent process/pid
    - reports target project/task evidence, visible/accessibility-tree match
      state, composer candidates, semantic composer count, selected transport,
      and foreground/native-bridge request when needed
    - all app UIA probe paths are read-only:
      `control_allowed=false`, `control_attempts=0`
  - robustness fix:
    - replay loader now reads JSON bytes and supports UTF-8 BOM and UTF-16 BOM
      so PowerShell-redirection logs can be replayed reliably
  - safe real validation:
    - full UIA snapshot saved:
      `logs\runtime\agent-app-uia\live-uia-probe-elements.json`
    - Codex App replay report saved:
      `logs\runtime\agent-app-uia\codex-app-uia-replay.json`
    - Codex App live report saved:
      `logs\runtime\agent-app-uia\codex-app-uia-live.json`
    - live Codex App result:
      `decision=agent_app_uia_target_visible_input_not_found`,
      `matched_window_count=1`, `control_attempts=0`
    - live Codex App evidence:
      `project_match=matched_visible` for `openwukong`
      and `task_match=matched_visible` for `支持不同 IDE 监工输入`
    - live Codex App limitation:
      `composer_candidate_count=0`, `semantic_composer_count=0`, so the app
      surface is observable but not yet safe for direct background message
      submission through UIA
    - Claude App live report saved:
      `logs\runtime\agent-app-uia\claude-app-uia-live.json`
    - live Claude App result:
      app surface resolved through StartApps/AUMID, but
      `decision=agent_app_window_not_found` because no Claude app window was
      running
  - TDD coverage added:
    - target-visible/no-composer app surface emits foreground/native-bridge
      request without any control attempt
    - semantic composer case reports `agent_app_uia_ready` while still making
      zero control attempts
    - replay CLI handles UTF-16 JSON logs from PowerShell redirection
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added app UIA probe-before-send rule and PowerShell UTF-16 JSON replay
      handling rule
  - current conclusion:
    - Codex App can now be precisely read for project/task context through UIA
    - Codex App cannot yet be claimed as direct background-send capable because
      the currently exposed composer is not available as a semantic UIA input
    - Claude App is discoverable but needs a running window before app UIA
      capability can be assessed
  - next high-value steps:
    - implement a native/DevTools-style connector for Electron-based agent app
      surfaces instead of relying on UIA text injection
    - keep Codex CLI as the proven background task execution route while app
      surfaces remain bridge/foreground gated
    - optionally run a user-approved foreground-only Codex/Claude app draft test
      after the read-only probe proves the target and a reversible draft path
- 2026-05-28 added read-only native connector probe for Electron-style agent apps:
  - implementation:
    - added `openwukong.evaluation.agent_native_connector_probe`
    - combines the existing agent app UIA target probe with process command-line
      inspection for Electron/Chromium DevTools exposure
    - detects `--remote-debugging-port=<port>` or
      `--remote-debugging-port <port>` on matching app processes
    - probes only local read-only DevTools metadata endpoints:
      `/json/version` and `/json/list`
    - reports endpoint count, ready endpoint count, target metadata, process
      evidence, and nested app UIA evidence
    - keeps `control_allowed=false` and `control_attempts=0`
  - correctness fix:
    - app UIA text-match evidence now distinguishes visible elements from
      accessible-tree-only/offscreen virtual-list nodes by intersecting element
      rects with the app `RootWebArea`/`RootView` bounds
  - safe real validation:
    - Codex App native probe report saved:
      `logs\runtime\agent-native\codex-app-native-live.json`
    - result:
      `decision=agent_native_connector_not_exposed`,
      `process_count=627`, `endpoint_count=0`,
      `ready_endpoint_count=0`, `control_attempts=0`
    - Claude App native probe report saved:
      `logs\runtime\agent-native\claude-app-native-live.json`
    - result:
      `decision=agent_app_window_not_found`,
      `endpoint_count=0`, `ready_endpoint_count=0`,
      `control_attempts=0`
  - TDD coverage added:
    - reachable Electron/Chromium remote debugging endpoint reports
      `agent_native_connector_ready`
    - target-visible app with no debug port reports
      `agent_native_connector_not_exposed`
    - no debug port is reported directly even when the app target is not
      currently visible in UIA
    - CLI writes JSON reports
    - offscreen UIA nodes are not marked visible just because they are present
      in the accessibility tree
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added Electron app native connector probe-before-DOM-control rule
  - current conclusion:
    - current Codex App process is not exposing a DevTools/native DOM control
      endpoint, so app-side background send still requires a real native bridge
      or an explicitly approved foreground draft path
    - the proven non-disruptive background route remains Codex CLI
    - app-side observation is improving and now correctly separates target
      presence, visible state, and native endpoint readiness
  - next high-value steps:
    - add a first-class local native bridge contract for agent apps instead of
      relying on an already-exposed Electron debug port
    - wire agent app UIA/native probe results into the higher-level
      `agent_conversation_runner` so app-surface requests get richer gating
      diagnostics automatically
- 2026-05-28 added and live-tested hidden Word COM background operation:
  - implementation:
    - added `openwukong.evaluation.office_word_runner`
    - uses the Microsoft Word object model instead of UIA or keyboard/mouse
      input
    - creates an owned temporary `.docx`, writes a marker, saves with
      `SaveAs2`, closes, reopens read-only/hidden, verifies marker readback,
      closes, and quits the owned Word COM instance
    - sets `Application.Visible=False` and `DisplayAlerts=0`
    - avoids `AddToRecentFiles`
    - reports:
      `control_attempts=0`, `window_input_attempts=0`,
      and `office_com_attempts=1`
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.office_word_runner --document-path logs\runtime\word\openwukong-word-background-probe.docx --marker OPENWUKONG_WORD_BACKGROUND_OK_20260528 --output logs\runtime\word\word-background-probe.json --json`
    - result:
      `decision=word_background_probe_verified`, `ok=true`,
      `save_verified=true`, `readback_verified=true`,
      `word_started=true`, `visible_requested=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `office_com_attempts=1`
    - artifacts:
      `logs\runtime\word\openwukong-word-background-probe.docx`
      and `logs\runtime\word\word-background-probe.json`
    - read-only process check after the run found no visible `WINWORD`
      process output
  - TDD coverage added:
    - fake Word COM verifies hidden mode, save/open/readback/quit flow
    - unavailable Word COM reports `word_com_not_available` with zero COM
      attempts
    - CLI writes JSON report
  - reusable skill updated:
    - `desktop-background-control-testing`
    - added Office object-model-first and Word hidden COM no-loss test rules
  - current conclusion:
    - Word is now a proven precise background operation path on this machine
      through COM, without focus takeover or window input
    - this fills one more primary scenario toward the goal:
      Office/Word can be controlled semantically in the background when the
      local Word COM server is available
  - next high-value steps:
    - wire Word COM runner into the primary scenario harness/control fabric
    - add Excel/PowerPoint COM parity later if Office scenarios expand beyond
      Word
    - continue unifying primary scenario reports across WeChat, browser,
      file search, Word, Cursor, Codex, and Claude
- 2026-05-28 wired Word into the unified primary no-loss scenario suite and
  hardened owned browser background cleanup:
  - implementation:
    - added `word.document.create_background` to the L1 primary scenario
      fixture, simulation route plan, smoke adapters, side-effect taxonomy, and
      real no-loss runner
    - added browser executable auto-resolution so `chrome.exe`/`msedge.exe`
      can resolve through installed app evidence instead of relying on PATH
    - changed owned browser helper launch to headless mode for no-focus real
      validation
    - fixed Windows owned Chromium cleanup to use UTF-16LE
      `powershell -EncodedCommand` for multi-line CIM scans instead of stdin
      scripts
    - changed cleanup semantics from "single taskkill return code" to
      repeated command-line scan, cleanup attempts, and final exact
      `--user-data-dir` rescan
  - root-cause fix:
    - `powershell -Command -` parses stdin one statement at a time, so the
      multi-line `foreach` process scan could return no PIDs even while owned
      Chrome/crashpad children were still running
    - `taskkill /T /F` can also clear the owned Chromium tree while reporting
      child-process warnings; final owned-profile rescan is the reliable
      success criterion
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.primary_real_no_loss tests\fixtures\evaluation\l1_primary_user_scenarios.json --output-root logs\runtime\primary-real-no-loss-main-20260528-r8 --allow-owned-browser-helper-launch --owned-browser-debug-port 9471 --summary-json`
    - result:
      `passed_cases=5/5`, `failed_cases=0`, `real_verified_cases=4`,
      `control_attempts=0`, `window_input_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`
    - verified r8 owned browser helper report:
      `status=started_and_stopped`, stop result `status=stopped`,
      `error=""`, `warning=""`
    - final CIM command-line rescan for the r8 owned browser profile returned
      `[]`, so no owned Chrome helper process remained
  - TDD coverage added:
    - Word primary scenario planning, smoke adapter, and real no-loss case
    - installed browser executable resolution for owned helper launch
    - encoded PowerShell scan command generation
    - already-gone Chromium child PID cleanup
    - taskkill child-warning cleanup with final rescan success
  - verification:
    - `python -m unittest discover tests`: `391 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only existing CRLF conversion warnings
  - current conclusion:
    - the unified no-loss primary suite now covers WeChat read-only locator,
      owned browser DevTools read, owned temp file search, hidden Word COM
      document creation, and Codex IDE bridge availability gating
    - it is still not correct to claim "all apps fully controllable"; app
      surfaces without native/semantic background bridge remain gated
    - Codex app background send remains bridge-required in this suite, while
      Codex CLI background execution was validated separately
  - next high-value steps:
    - wire richer Codex/Claude app UIA/native probe diagnostics into
      `agent_conversation_runner`
    - add Cursor/VS Code IDE bridge live capture as a first-class real no-loss
      case
    - add Excel/PowerPoint COM parity only after the Word path stays stable
- 2026-05-28 wired app-surface UIA/native diagnostics into targeted agent
  conversation runs:
  - implementation:
    - `run_agent_conversation(...)` now accepts an app-surface probe runner
      and records `app_surface_probe` in both the returned report and the
      saved conversation draft
    - `agent_conversation_runner` now defaults to the read-only
      `agent_native_connector_probe` for app/desktop surfaces that require a
      native bridge or foreground gate
    - the probe is only invoked when a requested app/desktop agent surface has
      no command contract and would otherwise return
      `agent_conversation_requires_app_bridge_or_foreground`
    - no CLI fallback is used for explicit app/desktop requests
  - safe real validation:
    - `codex app` app-surface execute request produced:
      `decision=agent_conversation_requires_app_bridge_or_foreground`,
      `agent_command_attempts=0`, `control_attempts=0`,
      `app_surface_probe.decision=agent_native_connector_not_exposed`
    - Codex App probe evidence:
      project `openwukong` was visible through UIA, requested task
      `background app probe diagnostics` was not visible, no semantic composer
      and no native endpoint were exposed
    - `claude desktop` app-surface execute request produced:
      `decision=agent_conversation_requires_app_bridge_or_foreground`,
      `agent_command_attempts=0`, `control_attempts=0`,
      `app_surface_probe.decision=agent_native_connector_not_exposed`
    - Claude Desktop probe evidence:
      a semantic composer was visible, but the target project/task was not
      visible and no native endpoint was exposed, so no background send was
      allowed
    - artifacts:
      `logs\runtime\agent-conversation-probe\codex-app-conversation.json`
      and
      `logs\runtime\agent-conversation-probe\claude-desktop-conversation.json`
  - TDD coverage added:
    - direct conversation reports include injected app-surface probe diagnostics
      when bridge-required
    - CLI runner writes app-surface probe diagnostics into JSON output for
      app/desktop execute requests
  - verification:
    - `python -m unittest tests.test_agent_conversation tests.test_agent_app_uia_probe tests.test_agent_native_connector_probe`: OK
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
    - `python -m unittest discover tests`: `393 tests OK`
  - current conclusion:
    - Codex/Claude app-surface requests are now richer and safer: they
      automatically report target visibility, composer readiness, and native
      endpoint exposure before any possible foreground/native bridge action
    - direct background app send is still not proven for these app surfaces;
      current evidence keeps them gated until a native bridge or exposed
      deterministic endpoint exists
  - next high-value steps:
    - add Cursor/VS Code IDE bridge live capture as a first-class real no-loss
      case
    - define the native bridge command contract that can consume
      `agent_app_uia_ready` or `agent_native_connector_ready`
    - add a no-focus screenshot/visual verification artifact only after the
      background route is deterministic
- 2026-05-28 deferred Cursor/VS Code scope and hardened Claude Desktop
  app-vs-CLI targeting:
  - scope update:
    - user explicitly said VS Code is not needed and Cursor should be ignored
      for now
    - current near-term work should focus on Codex/Claude/app-surface control
      and the shared background/no-focus control layer, not IDE bridge live
      capture
  - root-cause fix:
    - `claude desktop` could become ambiguous when a transient Claude Code CLI
      process was running because both Desktop and CLI expose `claude.exe`
      running-process candidates with equal score
    - app resolution now applies request-surface filtering for Claude:
      `desktop/app` requests prefer Desktop candidates when present, while
      `cli/code` requests prefer CLI candidates when present
    - Claude surface classification is centralized through the same helper so
      WindowsApps Claude Desktop shells, StartApps entries, and CLI paths are
      not classified differently by resolver and agent-surface layers
  - safe real validation:
    - `agent_surface_report --agent "claude desktop"` resolved the running
      WindowsApps Claude Desktop shell:
      `C:\Program Files\WindowsApps\Claude_1.9255.2.0_x64__pzs8sxrjxfjjc\app\claude.exe`
      with `control_attempts=0`
    - `agent_native_connector_probe --agent "claude desktop"` stayed read-only,
      found the Claude Desktop window and semantic composer, but correctly
      reported `agent_native_connector_not_exposed` because no native/DevTools
      endpoint is exposed and the requested project/task was not visible
  - TDD coverage added:
    - resolver regression for `claude desktop` with simultaneous WindowsApps
      Desktop `claude.exe` and transient CLI `.local/bin/claude.exe`
    - surface regression for selecting the WindowsApps Desktop shell instead
      of CLI for explicit `claude desktop`
  - verification:
    - `python -m unittest tests.test_app_resolution tests.test_agent_surface_report tests.test_agent_app_uia_probe tests.test_agent_native_connector_probe tests.test_agent_conversation`: OK
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - explicit Claude Desktop targeting is now precise enough for the next
      app-surface work and is no longer polluted by temporary Claude CLI
      process evidence
    - Claude Desktop still cannot be claimed as direct background-send capable
      until a native bridge or exposed deterministic endpoint exists
  - next high-value steps:
    - design and implement the native bridge command contract for agent app
      surfaces
    - keep Codex CLI as the proven background execution route while Codex App
      and Claude Desktop remain app-surface gated
    - add no-focus screenshot/visual verification only after the deterministic
      app bridge exists
- 2026-05-28 added no-focus background screenshot artifacts to agent app UIA
  probes:
  - implementation:
    - added `openwukong.evaluation.window_capture`
    - introduced `BackgroundWindowCaptureReport` and
      `PrintWindowBackgroundCaptureProvider`
    - `agent_app_uia_probe` now supports optional `--screenshot-dir`
    - when requested, matched app windows with HWNDs are captured to PNG
      artifacts without clicking, typing, setting foreground, or using window
      input
    - reports now include:
      `background_screenshot_count`,
      `background_screenshot_success_count`,
      `background_screenshot_focus_stable`, and per-screenshot
      foreground-HWND before/after evidence
  - safe real validation:
    - Claude Desktop app UIA probe with `--screenshot-dir` captured:
      `logs\runtime\agent-app-uia\claude-desktop-screenshots-r14\01-claude.exe-77064-138024.png`
    - report saved:
      `logs\runtime\agent-app-uia\claude-desktop-uia-screenshot-r14.json`
    - result:
      `control_attempts=0`,
      `background_screenshot_count=1`,
      `background_screenshot_success_count=1`,
      `background_screenshot_focus_stable=true`
    - the captured image showed the real Claude Desktop window and current
      conversation state; project/task match was still missing, so the probe
      correctly did not claim task readiness
  - TDD coverage added:
    - direct `run_agent_app_uia_probe(...)` screenshot injection keeps
      `control_attempts=0` and records stable foreground evidence
    - CLI `--screenshot-dir` writes screenshot metadata into the JSON report
  - verification:
    - `python -m unittest discover tests`: `397 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - app-surface observation now has a concrete visual artifact path that can
      verify what was seen without stealing focus
    - this improves verification for Claude/Codex app surfaces, but does not
      change the execution gate: direct background send still requires a
      native bridge or deterministic endpoint
  - next high-value steps:
    - pass screenshot options through higher-level native/conversation probes
      when a caller needs visual evidence
    - design and implement the native bridge command contract for app-side
      message submission
    - keep proving foreground stability on every real screenshot run instead
      of assuming screenshot success implies no-focus behavior
- 2026-05-28 wired no-focus screenshot diagnostics through native and
  conversation probes:
  - implementation:
    - `run_agent_native_connector_probe(...)` now accepts `screenshot_dir` and
      `window_capture_provider` and passes them through to the app UIA probe
    - `agent_native_connector_probe` CLI now supports `--screenshot-dir`
    - `run_agent_conversation(...)` now accepts
      `app_surface_screenshot_dir` and passes it to the app-surface probe only
      when an app/desktop surface is bridge/foreground gated
    - `agent_conversation_runner` CLI now supports
      `--app-surface-screenshot-dir`
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_conversation_runner --agent "claude desktop" ... --execute --allow-agent-task --confirm-effect agent_task_submission.submit_task --confirm-effect agent_start.start_agent --app-surface-screenshot-dir logs\runtime\agent-conversation-screenshot-r15-shots ...`
    - result:
      `decision=agent_conversation_requires_app_bridge_or_foreground`,
      `agent_command_attempts=0`, `control_attempts=0`
    - attached app-surface probe result:
      `agent_native_connector_not_exposed`,
      `background_screenshot_count=1`,
      `background_screenshot_success_count=1`,
      `background_screenshot_focus_stable=true`
    - screenshot artifact:
      `logs\runtime\agent-conversation-screenshot-r15-shots\01-claude.exe-77064-138024.png`
    - JSON report:
      `logs\runtime\agent-conversation-screenshot-r15.json`
  - TDD coverage added:
    - native connector probe pass-through for screenshot provider and CLI
      `--screenshot-dir`
    - direct conversation runner pass-through for
      `app_surface_screenshot_dir`
    - CLI pass-through for `--app-surface-screenshot-dir`
  - verification:
    - `python -m unittest discover tests`: `401 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - high-level app-surface diagnostics now carry accessibility evidence,
      native endpoint evidence, and optional no-focus visual evidence in the
      same report
    - this does not bypass the execution gate; Claude Desktop still requires a
      native bridge or approved foreground path for actual app message
      submission
  - next high-value steps:
    - define the native bridge command contract for app-side message
      submission
    - add a dry-run bridge adapter that can validate contract shape without
      touching real apps
    - only after bridge readiness is proven, add a gated real app-message
      sender path
- 2026-05-28 added the app-side native bridge dry-run contract:
  - implementation:
    - added `openwukong.control.agent_app_bridge` with
      `AgentAppBridgeRequest`, `AgentAppBridgeDryRunReport`, and
      `AgentAppBridgeDryRunAdapter`
    - the bridge request records schema version, request id, selected agent
      transport, target UIA evidence, native endpoint readiness, no-focus
      screenshot stability, payload, and required/forbidden result markers
    - `run_agent_conversation(...)` now attaches `app_bridge_dry_run` to both
      returned reports and saved draft artifacts when an app/desktop surface
      is bridge-required and the read-only app-surface probe returned evidence
    - no real bridge send is attempted in this layer:
      `control_attempts=0` and `bridge_send_attempts=0`
  - TDD coverage added:
    - ready native/UIA probe builds a dry-run bridge payload without attempting
      a send
    - missing native endpoint and missing target evidence are reported as
      explicit dry-run decisions instead of falling back to foreground or CLI
    - conversation drafts persist the bridge dry-run contract alongside the
      existing app-surface probe diagnostics
  - verification:
    - `python -m unittest tests.test_agent_app_bridge tests.test_agent_conversation.AgentConversationTests.test_app_surface_probe_ready_attaches_bridge_dry_run_contract`: OK
    - `python -m unittest tests.test_agent_conversation tests.test_agent_app_bridge tests.test_agent_native_connector_probe`: OK
    - `python -m compileall -q src tests`: OK
    - `python -m unittest discover tests`: `405 tests OK`
  - reusable pattern:
    - updated global skill `desktop-background-control-testing` so future app
      send work must first expose a dry-run bridge contract with target,
      endpoint, payload, marker, and zero-send evidence
  - current conclusion:
    - the control layer now has a stable, audited contract for app-side agent
      message submission
    - this is still not a real sender; it is the gate that prevents imprecise
      app UI typing and ensures a future sender only runs against proven
      native endpoint readiness
  - next high-value steps:
    - implement the first real native bridge adapter behind this contract for
      an owned/exposed endpoint only
    - add post-send readback verification against required markers before any
      app-side execution is marked accepted
    - keep Cursor/VS Code out of near-term scope per the latest user direction
- 2026-05-28 implemented the gated app-side CDP native bridge sender:
  - implementation:
    - added `AgentAppBridgeCdpAdapter` and `AgentAppBridgeSendReport`
    - the sender consumes the existing dry-run contract and refuses to call
      the endpoint unless target evidence, native endpoint readiness, and
      visual/no-focus stability gates are already ready
    - the sender uses the exposed DevTools websocket target and
      `Runtime.evaluate` to set a semantic composer, dispatch input/change
      events, click a visible send/submit button, and read back page text
    - reports now separate `bridge_send_attempts` and `native_call_attempts`
      from `window_input_attempts`; CDP/native sends keep
      `window_input_attempts=0`
    - post-send readback is checked against required and forbidden markers
      before a bridge execution can be reported as accepted
    - `run_agent_conversation(...)` can now accept an injected
      `app_bridge_sender`, and `agent_conversation_runner` exposes an explicit
      `--allow-app-bridge-send` flag; without the flag/injected sender the CLI
      remains probe/dry-run only
  - TDD coverage added:
    - ready CDP endpoint sends through the native adapter and verifies markers
      without window input
    - missing endpoint or non-ready dry-run requests do not call the native
      endpoint
    - verified submit with missing result markers is reported as acceptance
      pending, not accepted
    - conversation runner uses the bridge sender only when explicitly enabled
      and side-effect confirmation has passed, while keeping CLI command
      attempts at zero
  - verification:
    - `python -m unittest tests.test_agent_app_bridge tests.test_agent_conversation tests.test_agent_native_connector_probe tests.test_browser_connector`: OK
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
    - `python -m unittest discover tests`: `410 tests OK`
  - reusable pattern:
    - updated global skill `desktop-background-control-testing` to require
      explicit opt-in, dry-run-contract consumption, native-call/window-input
      counter separation, and marker-based readback for real app bridge sends
  - current conclusion:
    - the architecture now has a real no-keyboard/no-mouse bridge sender path
      for app surfaces that expose a compatible DevTools/native endpoint
    - Codex/Claude desktop apps still cannot be declared fully background
      send-capable on this machine unless their real app surfaces expose such
      an endpoint and the target/session is visible; otherwise they remain
      correctly gated
  - next high-value steps:
    - run safe real probes against Codex App and Claude Desktop with
      `--allow-app-bridge-send` only in an owned/test conversation where a
      ready endpoint is detected
    - add a live owned Electron/Chromium fixture test that exercises the real
      websocket path end to end without touching user apps
    - continue excluding Cursor/VS Code until the user reopens that scope
- 2026-05-28 accelerated into real no-loss testing and hardened owned browser
  target readiness:
  - implementation:
    - added `openwukong.evaluation.agent_app_bridge_fixture_smoke`, an owned
      local DevTools HTTP/WebSocket fixture that exercises the real
      `AgentAppBridgeCdpAdapter` websocket path without touching user apps
    - changed the bridge send selector regex to use ASCII-safe Unicode escapes
      for Chinese send/submit/run/start labels
    - fixed owned browser helper readiness so a launch that lands on
      `chrome://newtab/` no longer fails or gets misaccepted; the helper now
      creates the exact expected target through the local DevTools HTTP
      endpoint `PUT /json/new?{encoded_url}` and then re-reads `/json/list`
      for strict target matching
  - safe real validation:
    - owned CDP fixture smoke verified real websocket `Runtime.evaluate`,
      marker readback, `bridge_send_attempts=1`, `native_call_attempts=1`,
      and `window_input_attempts=0`
    - Codex App and Claude Desktop real no-focus probes were run with
      `--allow-app-bridge-send`; both correctly stayed gated because no ready
      native endpoint was exposed, while no-focus screenshots succeeded and
      no send/window input occurred
    - first primary real no-loss run found a real owned-browser failure:
      Chrome launched to `chrome://newtab/` instead of the requested
      `about:blank#openwukong-primary-real-r2`
    - after the readiness fix, primary real no-loss run
      `logs\runtime\primary-real-no-loss-r3` passed `5/5`:
      WeChat read-only locator, owned browser DevTools read, owned temp file
      search, hidden Word COM document creation, and Codex bridge capability
      gating
    - r3 counters:
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`
    - exact owned Chrome profile rescan after r3 returned no matching
      Chrome/crashpad process
  - TDD coverage added:
    - owned app-bridge fixture CLI/report tests
    - owned browser helper regression for the real `chrome://newtab/` launch
      mismatch followed by deterministic `/json/new` target creation
  - verification:
    - `python -m unittest tests.test_primary_scenario_smoke tests.test_primary_real_no_loss tests.test_agent_app_bridge_fixture_smoke tests.test_agent_app_bridge`: OK
    - `python -m unittest discover tests`: `413 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - reusable pattern:
    - updated global skill `desktop-background-control-testing` so future
      owned-browser tests must strict-match `/json/list` targets and use
      `PUT /json/new?{encoded_url}` when Chrome opens a default tab
  - current conclusion:
    - the core no-loss primary suite is now real-tested and stable for the
      main safe surfaces
    - precise cross-app control is not "all apps solved"; apps like WeChat,
      Codex App, and Claude Desktop still require deterministic native bridge
      exposure before background write/send can be considered safe
  - next high-value steps:
    - implement or discover a deterministic native bridge for Codex App and
      Claude Desktop app surfaces
    - keep WeChat write/send behind a native bridge or explicit foreground
      takeover gate; the current real evidence is read-only locator only
    - add background visual verification artifacts to the primary suite where
      they improve acceptance without stealing focus
- 2026-05-28 added no-focus visual evidence to the primary real no-loss suite:
  - implementation:
    - `primary_real_no_loss` now accepts `background_screenshot_dir` and a
      window capture provider
    - the WeChat real no-loss case captures matched windows through
      `PrintWindowBackgroundCaptureProvider` and records per-image
      foreground HWND before/after evidence
    - top-level reports and summary reports now include:
      `background_screenshot_count`,
      `background_screenshot_success_count`, and
      `background_screenshot_focus_stable`
    - explicit relative screenshot directories are resolved from the current
      working directory instead of being nested under `output_root`
    - the primary WeChat target filter now excludes `WXWork.exe`/Enterprise
      WeChat/WeCom so personal WeChat evidence is not polluted by a similar
      app
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.primary_real_no_loss tests\fixtures\evaluation\l1_primary_user_scenarios.json --output-root logs\runtime\primary-real-no-loss-r6 --allow-owned-browser-helper-launch --owned-browser-debug-port 9464 --owned-browser-url about:blank#openwukong-primary-real-r6 --background-screenshot-dir logs\runtime\primary-real-no-loss-r6\background-screenshots --json`
    - result:
      `passed_cases=5/5`, `failed_cases=0`, `real_verified_cases=4`,
      `control_attempts=0`, `window_input_attempts=0`,
      `external_communication_attempts=0`,
      `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`
    - visual evidence:
      `background_screenshot_count=1`,
      `background_screenshot_success_count=1`,
      `background_screenshot_focus_stable=true`
    - screenshot artifact:
      `logs\runtime\primary-real-no-loss-r6\background-screenshots\wechat_chat_draft_reply\01-Weixin.png`
    - screenshot metadata showed `foreground_hwnd_before` and
      `foreground_hwnd_after` were equal, so the capture did not steal focus
    - exact owned Chrome profile rescan after r6 returned no matching
      Chrome/crashpad process
  - TDD coverage added:
    - primary real no-loss report aggregation for no-focus background
      screenshots
    - explicit relative screenshot path resolution
    - personal WeChat filter excluding Enterprise WeChat/WeCom
  - verification:
    - `python -m unittest tests.test_primary_real_no_loss tests.test_agent_app_uia_probe tests.test_agent_native_connector_probe`: OK
    - `python -m unittest discover tests`: `416 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - primary real no-loss tests now have auditable visual evidence without
      foreground takeover for personal WeChat observation
    - this still proves observation, not WeChat background send; write/send
      remains blocked until a deterministic native bridge exists
  - next high-value steps:
    - add equivalent background visual/readback evidence for Codex App and
      Claude Desktop app-surface probes when they are part of the primary
      suite
    - continue implementing or discovering deterministic app-native bridges
      for Codex/Claude/WeChat before allowing background writes
- 2026-05-28 added a unified agent desktop app real no-loss runner:
  - implementation:
    - added `openwukong.evaluation.agent_app_real_no_loss`, a multi-agent
      runner that delegates to the read-only native connector probe and
      aggregates app-surface safety evidence
    - default app surfaces are `codex app` and `claude desktop`; Cursor is
      supported as an optional desktop-shell/native-bridge surface but is not
      included in the default real run
    - reports now aggregate `control_attempts`, `window_input_attempts`,
      `bridge_send_attempts`, `agent_command_attempts`,
      background screenshot counts, focus stability, native-ready cases, and
      gated cases
    - JSON output for the new runner is ASCII-safe so Windows PowerShell
      `ConvertFrom-Json` can parse reports even when UIA returns mixed
      language text
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --project-name openwukong --task-name agent-app-real-no-loss --output-root logs\runtime\agent-app-real-no-loss-r2 --screenshot-dir logs\runtime\agent-app-real-no-loss-r2\screenshots --output logs\runtime\agent-app-real-no-loss-r2\report.json`
    - result:
      `passed_cases=2/2`, `failed_cases=0`, `native_ready_cases=0`,
      `gated_cases=2`, `real_verified_cases=2`
    - safety counters:
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`
    - visual evidence:
      `background_screenshot_count=2`,
      `background_screenshot_success_count=2`,
      `background_screenshot_focus_stable=true`
    - evidence artifacts:
      `logs\runtime\agent-app-real-no-loss-r2\report.json`
      `logs\runtime\agent-app-real-no-loss-r2\screenshots\codex_app\01-Codex.exe-61920-199972.png`
      `logs\runtime\agent-app-real-no-loss-r2\screenshots\claude_desktop\01-claude.exe-77064-138024.png`
    - `ConvertFrom-Json` successfully parsed the r2 report after switching the
      new runner to ASCII-safe JSON
  - current conclusion:
    - Codex App and Claude Desktop are now real-observable in the background
      with no-focus screenshot evidence
    - both remain correctly gated for background send/control because neither
      exposes a ready native endpoint on this machine during the test
    - hidden Word COM tests not showing a Word taskbar icon is expected and is
      the intended no-loss background Office path
  - next high-value steps:
    - implement or install deterministic native app bridges for Codex App and
      Claude Desktop, then re-run the same no-loss runner expecting
      `native_ready_cases > 0`
    - keep app-side message sending disabled until native endpoint readiness,
      target visibility, and no-focus visual evidence are all present
- 2026-05-28 added UIA semantic action readiness for agent desktop apps:
  - implementation:
    - `agent_app_uia_probe` now reports visible `Invoke` submit candidates in
      addition to semantic composer candidates
    - added `openwukong.control.agent_app_uia_action`, a dry-run contract for
      future UIA semantic actions based on `ValuePattern` composer readiness
      and `InvokePattern` submit readiness
    - `agent_app_real_no_loss` now aggregates:
      `uia_semantic_action_ready_cases`, `uia_value_set_attempts`, and
      `uia_invoke_attempts`
    - the UIA action contract is diagnostic-only: it never calls SetValue,
      Invoke, keyboard, mouse, or clipboard APIs
  - official-doc basis:
    - Microsoft UI Automation `ValuePattern.SetValue` sets a supported
      control value through UIA
    - Microsoft UI Automation `InvokePattern.Invoke` invokes a supported
      control through UIA provider semantics
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --agent cursor --project-name openwukong --task-name agent-app-real-no-loss --output-root logs\runtime\agent-app-real-no-loss-r3 --screenshot-dir logs\runtime\agent-app-real-no-loss-r3\screenshots --output logs\runtime\agent-app-real-no-loss-r3\report.json`
    - result:
      `passed_cases=3/3`, `failed_cases=0`, `native_ready_cases=0`,
      `uia_semantic_action_ready_cases=0`, `gated_cases=3`,
      `real_verified_cases=3`
    - safety counters:
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`,
      `uia_value_set_attempts=0`, `uia_invoke_attempts=0`
    - visual evidence:
      `background_screenshot_count=5`,
      `background_screenshot_success_count=5`,
      `background_screenshot_focus_stable=true`
    - readiness diagnosis:
      Codex App: task not visible, no semantic composer, 6 submit candidates
      Claude Desktop: project/task not visible, 1 semantic composer, 0 submit
      candidates
      Cursor: project/task not visible, 6 semantic composers, 8 submit
      candidates
  - verification:
    - `python -m unittest discover tests`: `424 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - we now have a second background-control readiness lane beyond CDP:
      UIA semantic Value/Invoke readiness
    - real desktop apps are still correctly gated because the specific target
      project/task is not visible in the tested app surfaces, and Claude lacks
      an exposed submit Invoke candidate in the current UIA tree
  - next high-value steps:
    - add a controlled foreground-prep/no-send flow that brings the target
      project/task into view, then immediately reverts to background no-loss
      validation before enabling any semantic action
    - only after target visibility plus Value/Invoke readiness are both proven,
      add an explicit opt-in UIA semantic sender for owned or explicitly
      approved external-agent targets
- 2026-05-28 refined UIA semantic action readiness diagnostics:
  - implementation:
    - changed `AgentAppUiaSemanticActionRequest.target_ready` to mean only
      target visibility/matching, while `uia_value_pattern_ready` separately
      reports whether a semantic composer supports ValuePattern
    - added regression coverage for a project-only/new-task case where the
      target is visible but no ValuePattern composer exists
  - safe real validation:
    - project-only command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --agent cursor --project-name openwukong --output-root logs\runtime\agent-app-real-no-loss-r5-project-only --screenshot-dir logs\runtime\agent-app-real-no-loss-r5-project-only\screenshots --output logs\runtime\agent-app-real-no-loss-r5-project-only\report.json`
    - result:
      `passed_cases=3/3`, `native_ready_cases=0`,
      `uia_semantic_action_ready_cases=0`, `gated_cases=3`,
      `background_screenshot_count=5`, `background_screenshot_focus_stable=true`
    - safety counters remained zero:
      `control_attempts=0`, `window_input_attempts=0`,
      `uia_value_set_attempts=0`, `uia_invoke_attempts=0`
    - refined readiness diagnosis:
      Codex App: `target_ready=true`, `uia_value_pattern_ready=false`,
      `uia_invoke_pattern_ready=true`, decision
      `uia_semantic_action_value_pattern_not_ready`
      Claude Desktop: `target_ready=false`, `uia_value_pattern_ready=true`,
      `uia_invoke_pattern_ready=false`, decision
      `uia_semantic_action_target_not_ready`
      Cursor: `target_ready=false`, `uia_value_pattern_ready=true`,
      `uia_invoke_pattern_ready=true`, decision
      `uia_semantic_action_target_not_ready`
  - verification:
    - `python -m unittest discover tests`: `425 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - project-only/new-task semantics are now diagnosed correctly; Codex App is
      no longer mislabeled as target-missing when the project is present
    - the real remaining app-side blockers are now concrete: Codex needs a
      native/CDP bridge or a UIA-exposed ValuePattern composer; Claude/Cursor
      need the intended project surface to be visible before semantic action
      can be considered
- 2026-05-28 added WeChat UIA semantic action dry-run readiness:
  - implementation:
    - added `openwukong.control.wechat_uia_action`, a dry-run contract for
      WeChat conversation targets based on target visibility, UIA ValuePattern
      composer readiness, UIA InvokePattern submit readiness, and no-focus
      background screenshot stability
    - integrated the WeChat dry-run into `primary_real_no_loss` details and
      summary counters:
      `uia_semantic_action_ready_cases`, `uia_value_set_attempts`,
      `uia_invoke_attempts`
    - primary real no-loss case artifacts are now ASCII-escaped JSON so
      Windows PowerShell `ConvertFrom-Json` can parse them reliably even when
      fixture text contains Chinese/mojibake strings
  - official-doc basis:
    - Microsoft UI Automation control patterns define semantic provider
      capabilities independent of visual appearance
    - Microsoft `ValuePattern.SetValue` and `InvokePattern.Invoke` are the
      semantic write/invoke primitives, but this layer is dry-run only
    - Python `json.dumps` defaults `ensure_ascii=True`, which is safer for
      Windows-side JSON audit tooling
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.primary_real_no_loss tests\fixtures\evaluation\l1_primary_user_scenarios.json --output-root logs\runtime\primary-real-no-loss-r7-wechat-uia --background-screenshot-dir logs\runtime\primary-real-no-loss-r7-wechat-uia\background-screenshots --summary-json`
    - result:
      `passed_cases=5/5`, `failed_cases=0`, `real_verified_cases=3`,
      `background_screenshot_count=1`,
      `background_screenshot_success_count=1`,
      `background_screenshot_focus_stable=true`
    - safety counters remained zero:
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `uia_value_set_attempts=0`,
      `uia_invoke_attempts=0`, `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`
    - live WeChat diagnosis:
      WeChat was observable and captured in the background, but current UIA
      exposure was only one structural Pane; no target contact, ValuePattern
      composer, or InvokePattern submit control was exposed, so decision was
      `wechat_uia_semantic_action_target_not_ready`
    - artifact parse verification:
      PowerShell `ConvertFrom-Json` successfully parsed
      `logs\runtime\primary-real-no-loss-r7-wechat-uia\real_no_loss\wechat_chat_draft_reply.json`
  - verification:
    - `python -m unittest discover tests`: `428 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - prior real WeChat File Transfer Assistant sending remains valid as an
      explicit foreground opt-in path
    - the no-focus background path is now correctly evidence-gated: current
      live WeChat build does not expose enough UIA semantics for precise
      background sending, so a WeChat native bridge/hook or controlled
      foreground-prep plus confirmation remains required before background
      write actions can be enabled
- 2026-05-28 added real no-loss Agent CLI background probes:
  - implementation:
    - added `openwukong.evaluation.agent_cli_real_no_loss`, a no-focus
      real runner for Codex/Claude CLI transports
    - the runner creates owned temporary workspaces under `logs\runtime`,
      sends a marker-based no-loss prompt through existing guarded
      `run_agent_conversation`, records foreground HWND before/after, checks
      workspace file deltas, and writes ASCII-safe JSON artifacts
    - statuses classify execution outcomes without treating environment
      blockers as control failures:
      `verified`, `cli_auth_required`, `cli_access_denied`,
      `cli_executable_not_found`, `background_cli_unavailable`,
      `skipped_requires_cli_execution_opt_in`, `failed_workspace_mutated`
  - official-doc basis:
    - Anthropic Claude Code CLI supports non-interactive `-p`, JSON output,
      max turns, and `--permission-mode plan`
    - local Codex CLI help was blocked by WindowsApps alias access, so the
      runner relies on existing local surface resolution and the established
      Codex no-loss command shape:
      `--sandbox read-only --ask-for-approval never -C <owned-workspace> exec
      --skip-git-repo-check --ephemeral --ignore-rules --json`
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.agent_cli_real_no_loss --agent claude --agent codex --output-root logs\runtime\agent-cli-real-no-loss-r1 --output logs\runtime\agent-cli-real-no-loss-r1\report.json --allow-cli-execution --timeout-sec 45 --json`
    - result:
      `passed_cases=2/2`, `failed_cases=0`, `verified_cases=1`,
      `agent_command_attempts=2`, `window_input_attempts=0`,
      `foreground_focus_stable=true`
    - Codex CLI:
      `status=verified`, `real_verified=true`, returned
      `OPENWUKONG_AGENT_CLI_NO_LOSS: PASS`, workspace stayed clean, foreground
      HWND stayed stable
    - Claude CLI:
      `status=cli_auth_required`, `real_verified=false`, command returned
      `Not logged in - Please run /login`, workspace stayed clean, foreground
      HWND stayed stable
    - report parse verification:
      PowerShell `ConvertFrom-Json` parsed
      `logs\runtime\agent-cli-real-no-loss-r1\report.json` and confirmed per
      case status, command attempts, zero window input, clean workspace, and
      stable foreground focus
  - verification:
    - `python -m unittest discover tests`: `432 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK
  - current conclusion:
    - Codex now has a real verified no-focus background task path through the
      standalone CLI transport
    - Claude CLI is structurally ready but blocked by local authentication,
      while Claude Desktop remains app-bridge/foreground-gated
    - this advances the target state for agent products without weakening the
      rule that explicit app/desktop requests must not silently fall back to
      CLI
- 2026-05-29 added a unified major-scenario real no-loss acceptance runner:
  - implementation:
    - added `openwukong.evaluation.major_real_no_loss`, which aggregates the
      primary scenario runner, agent desktop app runner, and agent CLI runner
      into one auditable requirement matrix
    - requirements now explicitly separate:
      WeChat background observation vs WeChat background send,
      Word hidden COM document work,
      owned browser CDP research/read,
      owned file search,
      Codex/Claude CLI background tasks,
      and Codex App/Claude Desktop/Cursor app background chat
    - `goal_complete` is now deliberately strict: all named requirements must
      be verified, runner failures must be zero, control/window-input attempts
      must be zero, and background screenshot focus must remain stable
    - fixed `agent_cli_real_no_loss` so a user-driven foreground change during
      a non-interactive CLI probe is recorded but no longer misclassified as an
      automation failure when `window_input_attempts=0`
    - fixed owned browser helper cleanup so `browser-profile-real-helper` is
      deleted after manifest-based process stop, with boundary-checked
      `profile_cleanup` evidence written into `helper.json`
  - safe real validation:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r3 --output logs\runtime\major-real-no-loss-r3\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9478 --owned-browser-url "data:text/html,<title>OpenWukong Major No Loss R3</title><body>OpenWukong Major No Loss R3</body>" --background-screenshot-dir logs\runtime\major-real-no-loss-r3\background-screenshots --allow-agent-cli-execution --agent-cli-timeout-sec 45`
    - result:
      `safe_run_ok=true`, `goal_complete=false`, `unmet_requirements=5`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=2`,
      `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`
    - verified requirements:
      `wechat_background_observation`,
      `word_background_document`,
      `browser_background_research`,
      `file_background_search`,
      `codex_cli_background_task`
    - remaining unmet requirements:
      `wechat_background_send` is still gated because current WeChat UIA
      exposure lacks a target/composer/submit semantic control;
      `claude_cli_background_task` is blocked by local Claude login;
      `codex_app_background_chat`, `claude_desktop_background_chat`, and
      `cursor_background_chat` still require a deterministic native bridge or
      exposed semantic app control before background sending is safe
    - cleanup verification:
      PowerShell parsed `logs\runtime\major-real-no-loss-r3\report.json`;
      helper metadata showed
      `profile_cleanup.attempted=true`,
      `profile_cleanup.deleted=true`,
      `profile_cleanup.error=""`, and
      `profile_exists=false`
  - verification:
    - `python -m unittest discover tests`: `434 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - the main safe/background scenarios now have one repeatable acceptance
      command and a strict requirement-by-requirement status report
    - the system can already perform verified background/no-loss work for
      Word, owned browser research/read, owned file search, WeChat background
      observation, and Codex CLI task execution
    - the full objective is not complete until background write/send is
      verified for WeChat and app-surface Codex/Claude/Cursor, and Claude CLI
      is authenticated or otherwise bypassed by a native app bridge
- 2026-05-29 connected opt-in app bridge sending to the real no-loss app and
  major runners:
  - implementation:
    - `agent_app_real_no_loss` now builds an app bridge dry-run contract for
      each app surface and records it in the case artifact
    - real app bridge sending is available only behind explicit
      `allow_app_bridge_send` / `--allow-app-bridge-send`
    - the sender is invoked only when the dry-run request is ready:
      target matched, semantic composer present, native endpoint ready, and
      background visual focus stable
    - default behavior remains read-only; without the explicit flag the runner
      never calls the sender even when a sender object is supplied
    - `major_real_no_loss` now forwards app bridge send options and markers to
      the app runner, so the unified acceptance command can verify app-surface
      background chat when a deterministic native bridge becomes available
    - major requirement evidence now preserves `app_bridge_send_verified`
    - app bridge sender reports now contribute their own
      `control_attempts` and `window_input_attempts` to the no-loss safety
      counters, so an unsafe sender cannot be hidden behind an accepted
      bridge result
  - official-doc basis:
    - Python `dataclasses` and `argparse` official docs were checked for the
      report/CLI extension pattern
    - Chrome DevTools Protocol `Runtime.evaluate` docs were checked for the
      native CDP bridge execution primitive already used by the app bridge
  - safe real validation:
    - read-only app command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --agent cursor --project-name openwukong --task-name desktop-message --output-root logs\runtime\agent-app-real-no-loss-r6-bridge-ready --screenshot-dir logs\runtime\agent-app-real-no-loss-r6-bridge-ready\screenshots --output logs\runtime\agent-app-real-no-loss-r6-bridge-ready\report.json --json`
    - read-only result:
      `passed_cases=3/3`, `native_ready_cases=0`,
      `app_bridge_send_verified_cases=0`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success_count=4/4`,
      `background_screenshot_focus_stable=true`
    - opt-in gated app command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --agent cursor --project-name openwukong --task-name desktop-message --output-root logs\runtime\agent-app-real-no-loss-r7-bridge-send-gated --screenshot-dir logs\runtime\agent-app-real-no-loss-r7-bridge-send-gated\screenshots --output logs\runtime\agent-app-real-no-loss-r7-bridge-send-gated\report.json --allow-app-bridge-send --bridge-message "OPENWUKONG_APP_BRIDGE_GATED_CHECK" --acceptance-marker "OPENWUKONG_ACCEPTANCE: PASS"`
    - opt-in gated result:
      `passed_cases=3/3`, `native_ready_cases=0`,
      `app_bridge_send_verified_cases=0`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success_count=4/4`,
      `background_screenshot_focus_stable=true`
    - unified major command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r5-app-bridge-gated --output logs\runtime\major-real-no-loss-r5-app-bridge-gated\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9481 --owned-browser-url "data:text/html,<title>OpenWukong Major No Loss R5</title><body>OpenWukong Major No Loss R5</body>" --background-screenshot-dir logs\runtime\major-real-no-loss-r5-app-bridge-gated\background-screenshots --allow-app-bridge-send --app-bridge-message "OPENWUKONG_APP_BRIDGE_GATED_CHECK" --app-acceptance-marker "OPENWUKONG_ACCEPTANCE: PASS" --allow-agent-cli-execution --agent-cli-timeout-sec 45`
    - unified major result:
      `safe_run_ok=true`, `goal_complete=false`, `unmet_requirements=5`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=2`,
      `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`
  - verification:
    - `python -m unittest tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: OK
    - `python -m unittest discover tests`: `438 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - app-surface background chat now has the right final safety gate:
      dry-run evidence first, explicit opt-in second, native bridge send third,
      marker-based readback before acceptance
    - this machine still has no ready native endpoint for Codex App, Claude
      Desktop, or Cursor app-surface chat in the tested state, so no bridge
      send was attempted
    - next high-value step is to install or implement one deterministic
      app-native bridge endpoint, then re-run the same major command expecting
      one app chat requirement to flip from gated/unavailable to verified
- 2026-05-29 added an opt-in UIA semantic sender for agent desktop apps:
  - implementation:
    - `agent_app_uia_action` now includes
      `AgentAppUiaSemanticActionSenderAdapter` and a default
      `PywinautoUiaSemanticActionOperator`
    - the sender consumes the existing UIA dry-run contract and only executes
      when target, ValuePattern composer, InvokePattern submit control, and
      no-focus visual evidence are ready
    - execution uses UIA provider semantics only:
      `ValuePattern.SetValue` for the composer and `InvokePattern.Invoke` for
      the submit control; it does not use keyboard, mouse, clipboard, or
      `SendInput`
    - sender reports now include `uia_value_set_attempts`,
      `uia_invoke_attempts`, foreground HWND before/after, marker readback,
      missing required markers, and present forbidden markers
    - `agent_app_real_no_loss` now exposes explicit
      `allow_uia_semantic_action` / `--allow-uia-semantic-action` gates,
      aggregates UIA SetValue/Invoke attempts, and marks a case verified only
      when the sender reports `uia_semantic_action_send_accepted` with zero
      control/window-input attempts
    - `major_real_no_loss` now forwards UIA semantic action options and treats
      `uia_semantic_action_send_accepted` as satisfying an app background chat
      requirement
    - the global `desktop-background-control-testing` skill was updated with
      the reusable UIA semantic sender safety pattern
  - official-doc basis:
    - Microsoft UI Automation control patterns define provider semantics
      independent of visual control appearance
    - Microsoft `IUIAutomationValuePattern::SetValue` / `ValuePattern.SetValue`
      set supported control values through the provider
    - Microsoft `IUIAutomationInvokePattern::Invoke` invokes a control action
      such as a button through the provider
  - safe real validation:
    - app UIA-gated command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --agent cursor --project-name openwukong --task-name desktop-message --output-root logs\runtime\agent-app-real-no-loss-r8-uia-gated --screenshot-dir logs\runtime\agent-app-real-no-loss-r8-uia-gated\screenshots --output logs\runtime\agent-app-real-no-loss-r8-uia-gated\report.json --allow-uia-semantic-action --uia-message "OPENWUKONG_UIA_GATED_CHECK" --uia-acceptance-marker "OPENWUKONG_UIA_ACCEPTANCE: PASS"`
    - app UIA-gated result:
      `passed_cases=3/3`, `control_attempts=0`,
      `window_input_attempts=0`, `uia_value_set_attempts=0`,
      `uia_invoke_attempts=0`, `uia_semantic_action_send_verified_cases=0`,
      `bridge_send_attempts=0`, `background_screenshot_success_count=4/4`,
      `background_screenshot_focus_stable=true`
    - unified major command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r6-uia-gated --output logs\runtime\major-real-no-loss-r6-uia-gated\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9482 --owned-browser-url "data:text/html,<title>OpenWukong Major No Loss R6</title><body>OpenWukong Major No Loss R6</body>" --background-screenshot-dir logs\runtime\major-real-no-loss-r6-uia-gated\background-screenshots --allow-uia-semantic-action --uia-message "OPENWUKONG_UIA_GATED_CHECK" --uia-acceptance-marker "OPENWUKONG_UIA_ACCEPTANCE: PASS" --allow-app-bridge-send --app-bridge-message "OPENWUKONG_APP_BRIDGE_GATED_CHECK" --app-acceptance-marker "OPENWUKONG_ACCEPTANCE: PASS" --allow-agent-cli-execution --agent-cli-timeout-sec 45`
    - unified major result:
      `safe_run_ok=true`, `goal_complete=false`, `unmet_requirements=5`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=2`,
      app subreport `uia_value_set_attempts=0`,
      app subreport `uia_invoke_attempts=0`,
      `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`
  - verification:
    - `python -m unittest tests.test_agent_app_uia_action_contract tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: OK
    - `python -m unittest discover tests`: `444 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - we now have two real opt-in app-surface execution paths:
      native bridge/CDP and UIA semantic Value/Invoke
    - both are safely gated in the current live state because Codex App,
      Claude Desktop, and Cursor do not currently expose a ready target for
      `openwukong/desktop-message`
    - next high-value step is a controlled target-prep/no-send flow or a real
      native/extension bridge so one app surface exposes a ready target and can
      flip from gated to verified without foreground takeover
- 2026-05-29 added a UIA draft-only app-surface path and captured Cursor
  provider negative evidence:
  - implementation:
    - `agent_app_uia_action` now ranks UIA composer candidates before action:
      Cursor/agent chat composers such as `aislash-editor-input` are preferred,
      while Monaco editor inputs, filter boxes, problem filters, search/find
      fields, and tiny editor accessibility shims are rejected
    - send contracts now require a positive send/submit Invoke candidate and
      reject unrelated Invoke controls such as menu `Go`, branch buttons, and
      project action buttons
    - added `AgentAppUiaSemanticDraftDryRunAdapter` and
      `AgentAppUiaSemanticDraftWriterAdapter`
    - draft-only execution uses UIA `ValuePattern.SetValue` for the selected
      composer, never invokes submit, records cleanup attempts separately, and
      rejects foreground HWND changes
    - `agent_app_real_no_loss` now exposes explicit
      `allow_uia_semantic_draft` / `--allow-uia-semantic-draft` gates and
      reports `uia_semantic_draft_verified_cases`
    - failed draft attempts now surface provider-specific decisions such as
      `uia_semantic_action_draft_foreground_changed` instead of being collapsed
      into generic gated status
  - official-doc basis:
    - Microsoft UI Automation control patterns and `ValuePattern.SetValue`
      docs were checked before extending the provider-semantic write path
    - draft-only deliberately does not use `InvokePattern.Invoke`
  - safe/real validation:
    - read-only Cursor project probe:
      `logs\runtime\agent-app-real-no-loss-r9-cursor-project-probe\report.json`
      showed `PaoPaoHeZi` target visible, background screenshots stable, and a
      selectable `aislash-editor-input` composer
    - real draft-only command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent cursor --project-name PaoPaoHeZi --output-root logs\runtime\agent-app-real-no-loss-r10-cursor-uia-draft --screenshot-dir logs\runtime\agent-app-real-no-loss-r10-cursor-uia-draft\screenshots --output logs\runtime\agent-app-real-no-loss-r10-cursor-uia-draft\report.json --allow-uia-semantic-draft --uia-draft-message OPENWUKONG_UIA_DRAFT_PROBE_R10 --json`
    - real result before the status-classification follow-up:
      `passed_cases=0/1`, `uia_value_set_attempts=1`,
      `uia_invoke_attempts=0`, `window_input_attempts=0`,
      `background_screenshot_success_count=3/3`,
      `background_screenshot_focus_stable=true`
    - provider negative evidence:
      Cursor exposed a ValuePattern candidate, but `SetValue` did not change
      the draft value (`draft_value` stayed newline), cleanup could not verify,
      and foreground HWND changed from `467268` to `70038`
    - read-only post-change command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent cursor --project-name PaoPaoHeZi --output-root logs\runtime\agent-app-real-no-loss-r11-cursor-readonly-after-draft --screenshot-dir logs\runtime\agent-app-real-no-loss-r11-cursor-readonly-after-draft\screenshots --output logs\runtime\agent-app-real-no-loss-r11-cursor-readonly-after-draft\report.json --json`
    - read-only post-change result:
      `passed_cases=1/1`, `control_attempts=0`,
      `window_input_attempts=0`, `uia_value_set_attempts=0`,
      `uia_invoke_attempts=0`, `uia_semantic_draft_ready=true`,
      `uia_semantic_action_ready=false`,
      `background_screenshot_success_count=3/3`,
      `background_screenshot_focus_stable=true`
  - verification:
    - `python -m unittest tests.test_agent_app_uia_action_contract tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: OK
    - `python -m unittest discover tests`: `448 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - UIA structure is useful for precise detection and gating, but Cursor's
      current provider is not a background-safe write transport even when it
      exposes ValuePattern
    - this is strong evidence that app-surface background writing for
      Electron/IDE agents should move to native/extension bridge rather than
      relying on UIA `SetValue`
    - next concrete action: implement one native/extension bridge for Cursor or
      Codex app-surface chat, then re-run the same no-loss runner expecting
      native bridge verification without provider focus changes
- 2026-05-29 connected explicit IDE extension bridge endpoints into the
  unified agent app no-loss path:
  - implementation:
    - `agent_native_connector_probe` now accepts explicit
      `ide_bridge_urls` / `--ide-bridge-url` values and probes each one through
      the read-only `/v1/ide/capabilities` contract
    - discovered IDE bridge endpoints are represented beside CDP endpoints with
      `endpoint_type=ide_bridge`, `bridge_url`, `metadata`, `commands`,
      `chat_adapters`, `adapter_mapping`, `preferred_chat_adapter`, and
      `capability_ok`
    - `AgentAppBridgeNativeAdapter` now routes app bridge sends by endpoint
      type:
      `ide_bridge` goes through `IDEExtensionBridgeClient.send_chat`, while
      existing DevTools/CDP endpoints keep the prior DOM/CDP path
    - IDE bridge sends report the same no-loss counters as CDP sends:
      `bridge_send_attempts`, `native_call_attempts`, `control_attempts=0`,
      and `window_input_attempts=0`
    - the app bridge dry-run contract can now be ready for an IDE native bridge
      even when UIA composer semantics are not the write transport
    - multi-window agent targeting now prefers the matched window whose title
      contains the requested project/task, preventing a generic Cursor/Codex
      window from becoming the bridge request target when another project
      window is also open
    - `agent_app_real_no_loss` and `major_real_no_loss` now forward
      `ide_bridge_urls` and `workspace_path`, so the same unified acceptance
      command can verify extension/native app chat once the bridge is running
  - official-doc basis:
    - VS Code official extension command docs were checked for
      `vscode.commands.executeCommand`
    - VS Code activation event docs were checked for extension startup and
      command activation behavior
    - VS Code command-line docs were checked for isolated extension-host
      options such as `--user-data-dir` and `--extensions-dir`
  - safe/real validation:
    - read-only Cursor project command:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent cursor --project-name PaoPaoHeZi --output-root logs\runtime\agent-app-real-no-loss-r13-ide-bridge-project --screenshot-dir logs\runtime\agent-app-real-no-loss-r13-ide-bridge-project\screenshots --output logs\runtime\agent-app-real-no-loss-r13-ide-bridge-project\report.json --ide-bridge-url http://127.0.0.1:8787 --workspace-path E:\ideaProjects\agent\openwukong`
    - result:
      `passed_cases=1/1`, `failed_cases=0`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success_count=3/3`,
      `background_screenshot_focus_stable=true`
    - project targeting evidence:
      app bridge dry-run target selected
      `config - PaoPaoHeZi - Cursor` instead of the unrelated
      `start.md - trustusb-2 ... - Cursor` window
    - bridge state:
      endpoint `http://127.0.0.1:8787` was recorded as
      `endpoint_type=ide_bridge`, but `ready=false` because no bridge server
      was listening on that port
  - verification:
    - red/green targeted TDD:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: OK
    - full suite:
      `python -m unittest discover tests`: `453 tests OK`
    - `python -m compileall -q src tests`: OK
    - `git diff --check`: OK, only CRLF warnings
  - current conclusion:
    - the unified no-loss path now understands IDE/native extension bridges and
      can verify app-surface background chat when such a bridge is live
    - the current machine still lacks a running Cursor bridge on 8787, so the
      real run correctly stayed gated and made no send attempt
    - next concrete action: start/install the OpenWukong IDE bridge in an
      isolated or user-approved Cursor/VS Code extension host, configure a
      real chat adapter command, and rerun the same no-loss command expecting
      `cursor_background_chat` to flip from gated to verified
- 2026-05-29 verified the Cursor IDE bridge path end to end in an isolated
  extension host:
  - implementation:
    - `execute_session_readiness_plan` now writes the IDE bridge
      `settings_preview` into the isolated `--user-data-dir/User/settings.json`
      before launching the extension host, so `autoStart`, host, and port are
      real launch-time settings rather than plan-only metadata
    - `ide_bridge_capture` now infers read-only Cursor/Copilot/Codex review
      candidates from raw command discovery and exposes `active_mapping` plus
      `cursor_review_candidates` without enabling an adapter before validation
    - app bridge target readiness can now be satisfied by a ready IDE bridge
      endpoint whose metadata/active editor proves the requested project,
      instead of requiring UIA `target_matched=true`
  - official-doc basis:
    - VS Code command docs and API docs were checked for command discovery and
      `executeCommand`
    - VS Code user/workspace settings docs were checked for settings file
      behavior
    - Python `dataclasses` and `unittest` docs were checked for the report and
      regression-test patterns used here
  - safe/real validation:
    - isolated Cursor bridge launch:
      `python -m openwukong.evaluation.session_readiness_plan --route ide-extension-connector ... --ide-bridge-port 8791 --execute ...`
      launched an isolated Cursor extension host with PID `16484`
    - readiness:
      `http://127.0.0.1:8791/v1/ide/capabilities` returned `ok=true`,
      `ide_name=Cursor`, `command_count=3204`, and the written settings file
      contained `openwukong.bridge.autoStart=true`, host `127.0.0.1`, port
      `8791`
    - candidate discovery:
      `capabilities-v2.json` inferred Cursor candidates including
      `composer.startComposerPrompt`, `composer.startComposerPrompt2`, and
      `composer.sendToAgent` while keeping the adapter disabled until probe
    - contract probe:
      before allowlisting, `composer.startComposerPrompt` was blocked by
      `command_not_allowlisted`; after allowlisting only that command in the
      isolated profile, the probe accepted `object_message`, changed no
      workspace files, and produced validated mapping
      `cursor -> composer.startComposerPrompt`
    - validated capabilities:
      `capabilities-v3-validated.json` reported the Cursor adapter as
      `available=true` with command `composer.startComposerPrompt`
    - no-loss dry-run:
      `agent-app-real-no-loss-r14-isolated-ide-bridge-readonly-v2` reported
      `passed_cases=1/1`, `native_ready_cases=1`,
      `app_bridge_dry_run.decision=app_bridge_dry_run_ready`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `background_screenshot_focus_stable=true`
    - opt-in real bridge send:
      `agent-app-real-no-loss-r14-isolated-ide-bridge-send` reported
      `passed_cases=1/1`, `app_bridge_send_verified_cases=1`,
      `bridge_send_attempts=1`, `command_id=composer.startComposerPrompt`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `background_screenshot_focus_stable=true`
    - post-send read-only check:
      `agent-app-real-no-loss-r14-isolated-ide-bridge-post-send-readonly`
      again reported `passed_cases=1/1`, `native_ready_cases=1`, and
      `background_screenshot_focus_stable=true`
    - cleanup:
      `session-readiness-stop` stopped manifest-owned PID `16484`; port
      `8791` then reported `TcpTestSucceeded=false`
  - verification:
    - targeted red/green:
      `python -m unittest tests.test_ide_bridge_capture.IDEBridgeCaptureTests.test_capture_infers_cursor_review_candidates_from_raw_commands_without_enabling_adapter`: RED then OK
    - targeted red/green:
      `python -m unittest tests.test_agent_app_bridge.AgentAppBridgeTests.test_ide_bridge_endpoint_metadata_can_satisfy_target_without_uia_match`: RED then OK
    - targeted suite:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_ide_bridge_capture tests.test_session_readiness_plan`: `51 tests OK`
    - full suite:
      `python -m unittest discover tests`: `456 tests OK`
    - `python -m compileall -q src tests`: OK
  - current conclusion:
    - Cursor app-surface background control is now verified through the
      connector-first route in an isolated real Cursor extension host:
      extension bridge discovery -> command contract probe -> validated
      adapter -> no-loss opt-in send
    - this does not yet mean every Cursor/Codex/Claude app window is solved;
      normal user-profile Cursor bridge installation, Codex app bridge, and
      Claude Desktop bridge/auth remain separate surfaces
- 2026-05-29 promoted the isolated Cursor IDE bridge validation into the
  unified major no-loss runner:
  - implementation:
    - `major_real_no_loss` now has an explicit owned IDE bridge helper path
      behind `--allow-owned-ide-bridge-helper-launch`
    - the helper starts an isolated VS Code-compatible IDE extension host with
      separate `--user-data-dir`, `--extensions-dir`, workspace root, bridge
      host/port, and manifest
    - the runner now performs the full Cursor bridge preparation sequence
      automatically:
      launch isolated host -> read capabilities -> select candidate command ->
      write narrow temporary allowlist -> run command contract probe -> write
      validated chat adapter settings -> re-read validated capabilities
    - only a ready validated endpoint is forwarded to
      `agent_app_real_no_loss`; the actual app bridge send still uses the
      existing opt-in native bridge gate and keeps `control_attempts=0` and
      `window_input_attempts=0`
    - helper launch, stop, cleanup, and isolated command-probe counters are
      recorded separately from real app control counters:
      `owned_ide_bridge_launch_attempts`,
      `owned_ide_bridge_stop_attempts`,
      `owned_ide_bridge_cleanup_ok`, and
      `isolated_ide_command_probe_attempts`
    - the runner stops the owned IDE helper from the manifest after the app
      validation finishes, so the bridge remains alive during validation but
      does not leak after the run
  - official-doc basis:
    - VS Code CLI docs were checked for isolated launch options such as
      `--user-data-dir` and `--extensions-dir`
    - VS Code settings docs were checked for `settings.json` behavior
    - Python `dataclasses` and `argparse` docs were checked before extending
      the report model and CLI
  - safe/real validation:
    - unified command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r15-owned-ide-bridge-unified --output logs\runtime\major-real-no-loss-r15-owned-ide-bridge-unified\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9484 --owned-browser-url "data:text/html,<title>OpenWukong Major Owned IDE Bridge R15</title><body>OpenWukong Major Owned IDE Bridge R15</body>" --agent-app cursor --project-name openwukong --task-name major-owned-ide-bridge-r15 --allow-app-bridge-send --app-bridge-message "OPENWUKONG_MAJOR_OWNED_IDE_BRIDGE_R15" --allow-owned-ide-bridge-helper-launch --owned-ide-executable "E:\cursor\cursor\cursor\Cursor.exe" --owned-ide-bridge-port 8794 --owned-ide-capability-timeout-sec 45 --json`
    - result summary:
      `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=1`, `owned_ide_bridge_launch_attempts=1`,
      `owned_ide_bridge_stop_attempts=1`,
      `owned_ide_bridge_cleanup_ok=true`,
      `isolated_ide_command_probe_attempts=3`,
      `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`
    - requirement result:
      `cursor_background_chat=verified` through
      `app_bridge_send_accepted`; WeChat observation, Word hidden COM,
      browser CDP, and file search were also verified in the same run
    - cleanup check:
      port `8794` reported `TcpTestSucceeded=false`, and no process command
      line still contained the owned IDE bridge runtime root
  - verification:
    - red test:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_prepares_owned_ide_bridge_and_forwards_endpoint_to_agent_app`: failed before implementation, then OK
    - red test:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_prepare_owned_ide_bridge_helper_validates_adapter_with_injected_safe_steps`: failed before injection support, then OK
    - targeted suite:
      `python -m unittest tests.test_major_real_no_loss tests.test_ide_bridge_capture tests.test_ide_bridge_contract_probe tests.test_session_readiness_plan tests.test_agent_app_real_no_loss tests.test_agent_app_bridge tests.test_agent_native_connector_probe`: `61 tests OK`
  - current conclusion:
    - the main unified acceptance path can now one-command verify Cursor
      background app-surface chat through a connector-first owned bridge,
      without keyboard/mouse/window input and without leaving helper processes
    - the remaining unmet major requirements in this run are not Cursor:
      WeChat background send still requires a deterministic native bridge or
      stronger semantic surface, Codex/Claude CLI were intentionally skipped
      without execution opt-in, and Codex App / Claude Desktop still need
      their own native/app bridge paths
- 2026-05-29 verified Codex CLI execution and fixed IDE-bridge agent scoping:
  - implementation:
    - `agent_cli_real_no_loss` now records foreground snapshots before and
      after CLI execution:
      `hwnd`, `pid`, `process_name`, and `window_title`
    - CLI reports now classify foreground changes as:
      `stable`, `changed_to_agent_surface`,
      `changed_to_unrelated_surface`, or `changed_unknown`
    - CLI reports now expose `foreground_no_steal_verified`, so normal user
      foreground movement can be distinguished from an agent CLI stealing focus
    - `agent_native_connector_probe` no longer falls back from the requested
      agent adapter to any available IDE adapter; a Cursor adapter can only
      satisfy `agent_id=cursor`, not `codex` or `claude`
    - `AgentAppBridgeRequest` now enforces the same agent/adapter match as a
      second safety layer before treating an IDE bridge endpoint as target-ready
  - official-doc basis:
    - Microsoft Win32 docs for `GetForegroundWindow` and related window/PID
      APIs were checked before adding foreground attribution
  - safe/real validation:
    - focused CLI command:
      `python -m openwukong.evaluation.agent_cli_real_no_loss --agent codex --agent claude --output-root logs\runtime\agent-cli-real-no-loss-r17-execution-focus-attribution --output logs\runtime\agent-cli-real-no-loss-r17-execution-focus-attribution\report.json --allow-cli-execution --timeout-sec 120 --json`
    - focused CLI result:
      `passed_cases=2/2`, `verified_cases=1`,
      `agent_command_attempts=2`, `window_input_attempts=0`,
      `foreground_focus_stable=true`,
      `foreground_no_steal_verified=true`
    - Codex CLI result:
      `status=verified`, `real_verified=true`, `workspace_clean=true`,
      exact marker `OPENWUKONG_AGENT_CLI_NO_LOSS: PASS`
    - Claude CLI result:
      `status=cli_auth_required`, `real_verified=false`, local CLI returned
      `Not logged in · Please run /login`; this is an auth/environment blocker,
      not a control-layer blocker
    - unified major command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r19-owned-ide-cli-scoped --output logs\runtime\major-real-no-loss-r19-owned-ide-cli-scoped\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9486 --owned-browser-url "data:text/html,<title>OpenWukong Major Scoped R19</title><body>OpenWukong Major Scoped R19</body>" --project-name openwukong --task-name major-owned-ide-cli-r19 --allow-app-bridge-send --app-bridge-message "OPENWUKONG_MAJOR_OWNED_IDE_CLI_R19" --allow-owned-ide-bridge-helper-launch --owned-ide-executable "E:\cursor\cursor\cursor\Cursor.exe" --owned-ide-bridge-port 8796 --owned-ide-capability-timeout-sec 45 --allow-agent-cli-execution --agent-cli-timeout-sec 120`
    - unified major result:
      `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `agent_command_attempts=2`, `bridge_send_attempts=1`,
      `background_screenshot_success_count=6/6`,
      `background_screenshot_focus_stable=true`,
      `owned_ide_bridge_cleanup_ok=true`
    - requirement result after fixing the false positive:
      `codex_cli_background_task=verified`,
      `cursor_background_chat=verified`,
      `codex_app_background_chat=gated_native_endpoint_missing`,
      `claude_desktop_background_chat=unavailable`,
      `claude_cli_background_task=auth_required`
    - cleanup check:
      port `8796` reported `TcpTestSucceeded=false`, and no process command
      line still contained the owned IDE bridge runtime root
  - regression evidence:
    - red test:
      `tests.test_agent_cli_real_no_loss.AgentCliRealNoLossTests.test_unrelated_foreground_change_is_not_classified_as_cli_focus_steal`: failed before snapshot attribution, then OK
    - red test:
      `tests.test_agent_cli_real_no_loss.AgentCliRealNoLossTests.test_agent_surface_foreground_change_is_classified_as_focus_steal_risk`: failed before snapshot attribution, then OK
    - red test:
      `tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_ide_bridge_endpoint_does_not_reuse_cursor_adapter_for_codex_app`: failed before adapter scoping, then OK
    - red test:
      `tests.test_agent_app_bridge.AgentAppBridgeTests.test_ide_bridge_cursor_adapter_cannot_satisfy_codex_app_request`: failed before bridge request scoping, then OK
    - targeted suite:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_cli_real_no_loss`: `43 tests OK`
  - current conclusion:
    - developer-workstation background path now has verified real coverage for
      browser, Word hidden COM, file search, WeChat observation, Cursor app
      bridge, and Codex CLI
    - the remaining true gaps are:
      WeChat deterministic background send,
      Claude CLI login/auth,
      Codex App native/app bridge,
      Claude Desktop native/app bridge
- 2026-05-29 added an explicit WeChat UIA semantic send gate and verified the
  real current-machine negative case:
  - implementation:
    - `wechat_uia_action` now has an explicit opt-in sender that consumes the
      existing dry-run contract, uses only UIA `ValuePattern.SetValue` and
      `InvokePattern.Invoke`, records UIA value/invoke attempts separately,
      and reports zero keyboard, clipboard, mouse, or window input attempts
    - the sender requires post-action readback markers and rejects the result
      if foreground focus changes, a forbidden marker appears, or the required
      marker is missing
    - `primary_real_no_loss` can now run this WeChat sender behind
      `allow_wechat_uia_semantic_send`; default behavior remains dry-run only
    - `major_real_no_loss` exposes the same option through
      `--allow-wechat-uia-semantic-send`,
      `--wechat-uia-message`,
      `--wechat-uia-acceptance-marker`, and
      `--wechat-uia-forbid-marker`
    - fixed the major requirement aggregation bug where
      `wechat_background_send` read the wrong case layer; it now reads
      `case.details.background_send_verified`
  - official-doc basis:
    - Microsoft UI Automation `ValuePattern.SetValue` docs were checked:
      it sets a supported control value, but provider support/read-only state
      must be validated
    - Microsoft UI Automation `InvokePattern.Invoke` docs were checked:
      it requests a control's single unambiguous action, but behavior depends
      on the provider implementation
    - Microsoft UI Automation control pattern overview was checked for the
      pattern-based client/provider model
  - safe/real validation:
    - focused regression:
      `python -m unittest tests.test_wechat_uia_action_contract tests.test_primary_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_agent_app_uia_action_contract`: `38 tests OK`
    - focused real command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r20-wechat-uia-send --output logs\runtime\major-real-no-loss-r20-wechat-uia-send\report.json --allow-wechat-uia-semantic-send --wechat-uia-message OPENWUKONG_WECHAT_UIA_R20_20260529 --wechat-uia-acceptance-marker OPENWUKONG_WECHAT_UIA_R20_20260529 --json`
    - R20 result:
      `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `external_communication_attempts=0`,
      `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`
    - R20 WeChat evidence:
      WeChat observation remained verified, but send stayed gated with
      `wechat_uia_semantic_action_target_not_ready`; the real current window
      exposed only one UIA `Pane`, no semantic input, no semantic submit
      control, and therefore no send attempt was made
    - full real command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r21-wechat-uia-owned-ide-cli --output logs\runtime\major-real-no-loss-r21-wechat-uia-owned-ide-cli\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9487 --owned-browser-url "data:text/html,<title>OpenWukong Major R21</title><body>OpenWukong Major R21</body>" --allow-wechat-uia-semantic-send --wechat-uia-message OPENWUKONG_WECHAT_UIA_R21_20260529 --wechat-uia-acceptance-marker OPENWUKONG_WECHAT_UIA_R21_20260529 --project-name openwukong --task-name major-wechat-uia-owned-ide-cli-r21 --allow-app-bridge-send --app-bridge-message OPENWUKONG_MAJOR_WECHAT_UIA_OWNED_IDE_CLI_R21 --allow-owned-ide-bridge-helper-launch --owned-ide-executable "E:\cursor\cursor\cursor\Cursor.exe" --owned-ide-bridge-port 8797 --owned-ide-capability-timeout-sec 45 --allow-agent-cli-execution --agent-cli-timeout-sec 120`
    - R21 result:
      `safe_run_ok=true`, `goal_complete=false`,
      `unmet=4`, `control_attempts=0`,
      `window_input_attempts=0`, `agent_command_attempts=2`,
      `bridge_send_attempts=1`,
      `background_screenshot_success_count=6/6`,
      `background_screenshot_focus_stable=true`,
      `owned_ide_bridge_cleanup_ok=true`
    - R21 requirement result:
      `wechat_background_observation=verified`,
      `wechat_background_send=gated (wechat_uia_semantic_action_target_not_ready)`,
      `word_background_document=verified`,
      `browser_background_research=verified`,
      `file_background_search=verified`,
      `codex_cli_background_task=verified`,
      `claude_cli_background_task=auth_required`,
      `cursor_background_chat=verified`,
      `codex_app_background_chat=gated_native_endpoint_missing`,
      `claude_desktop_background_chat=unavailable`
    - cleanup:
      port `8797` reported `TcpTestSucceeded=false`, and no non-PowerShell
      process command line still contained the R21 owned helper runtime root
  - current conclusion:
    - WeChat now has a strict background semantic sender path when the target
      conversation and UIA Value/Invoke controls are actually exposed
    - the current live WeChat state did not expose that surface, so the runner
      correctly refused to send and recorded provider-negative evidence
    - next concrete action is no longer "try harder with UIA"; it is to build
      a WeChat native/semantic connector or a deterministic target-conversation
      bridge that can expose the File Transfer Assistant composer without
      foreground keyboard/clipboard takeover
- 2026-05-29 added the WeChat native bridge contract and wired it into the
  unified no-loss runners:
  - implementation:
    - added `wechat_native_bridge`, a local JSON bridge contract for
      deterministic WeChat background sends through `/v1/wechat/capabilities`
      and `/v1/wechat/send`
    - the bridge dry-run validates endpoint readiness, exact target
      conversation match, send-action availability, background-safe flags,
      and no foreground/window-input requirement
    - the bridge sender is opt-in only, records native call attempts
      separately from send attempts, and rejects success if the bridge reports
      window input, keyboard input, clipboard writes, foreground change,
      missing required markers, or forbidden markers
    - `primary_real_no_loss` now accepts explicit
      `wechat_native_bridge_urls`, bridge message/marker options, an injected
      dry-run adapter, and an injected sender; default behavior still sends
      nothing
    - `major_real_no_loss` now exposes the same route through
      `--wechat-native-bridge-url`,
      `--allow-wechat-native-bridge-send`,
      `--wechat-native-bridge-message`,
      `--wechat-native-bridge-acceptance-marker`, and
      `--wechat-native-bridge-forbid-marker`
    - `wechat_background_send` evidence now reports both the old UIA decision
      and the native bridge decision, so the current blocker is explicit:
      no WeChat native bridge URL configured
  - official-doc basis:
    - Python `urllib.request` official docs were checked before implementing
      the standard-library HTTP JSON client
    - Python `http.server` official docs were checked before adding the local
      fake bridge tests
  - validation:
    - red tests first:
      `tests.test_wechat_native_bridge` failed on missing module,
      primary failed on missing `wechat_native_bridge_urls`, and major failed
      on missing `wechat_native_bridge_urls`
    - targeted green:
      `python -m unittest tests.test_wechat_native_bridge tests.test_primary_real_no_loss.PrimaryRealNoLossTests.test_runner_can_execute_opt_in_wechat_native_bridge_send_without_window_input tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_passes_wechat_native_bridge_options_and_marks_wechat_send_verified`: `5 tests OK`
    - focused regression:
      `python -m unittest tests.test_wechat_native_bridge tests.test_wechat_uia_action_contract tests.test_primary_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_agent_app_bridge`: `45 tests OK`
    - full suite:
      `python -m unittest discover tests`: `471 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke without a WeChat bridge URL:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r22-wechat-native-bridge-contract-no-url --output logs\runtime\major-real-no-loss-r22-wechat-native-bridge-contract-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`,
      `wechat_background_observation=verified`, and
      `wechat_background_send=gated (wechat_native_bridge_url_missing)`
  - current conclusion:
    - the unified architecture now has a first-class deterministic route for
      WeChat background send when a native/local connector is available
    - the current machine still does not have that real WeChat native bridge
      installed, so real WeChat send remains gated rather than falling back to
      keyboard/mouse/clipboard
    - next concrete action is to implement the actual Windows-side WeChat
      connector behind this contract, or to select a supported WeChat-side
      protocol/automation integration that can expose File Transfer Assistant
      conversation operations without foreground takeover
- 2026-05-29 added the generic Agent App native bridge contract for Codex and
  Claude desktop app surfaces:
  - implementation:
    - added `agent_native_bridge`, a local JSON bridge contract for
      deterministic agent app background sends through
      `/v1/agent/capabilities` and `/v1/agent/chat`
    - the bridge dry-run validates endpoint readiness, exact agent adapter,
      project/task availability, send-action availability, background-safe
      flags, and no foreground/window-input requirement
    - the bridge sender is opt-in only, records native call attempts
      separately from bridge send attempts, and rejects success if the bridge
      reports window input, keyboard input, clipboard writes, foreground
      change, missing required markers, or forbidden markers
    - `agent_native_connector_probe` now accepts explicit
      `agent_native_bridge_urls` and exposes ready
      `endpoint_type=agent_native_bridge` endpoints only when the bridge
      matches the requested agent/project/task
    - `agent_app_bridge` now treats an `agent_native_bridge` endpoint as a
      first-class native sender, mapped back into the existing
      `app_bridge_send_accepted` acceptance contract
    - `agent_app_real_no_loss` and `major_real_no_loss` now forward
      `--agent-native-bridge-url` to agent app probes
  - official-doc basis:
    - Python `urllib.request` official docs were checked before implementing
      the standard-library HTTP JSON client
    - Python `http.server` official docs were checked before adding the local
      fake bridge tests
  - validation:
    - red tests first:
      `tests.test_agent_native_bridge` failed on missing module,
      native connector probe failed on missing `agent_native_bridge_urls`,
      app bridge failed on missing `agent_native_bridge_client`, and agent app
      / major runners failed on missing forwarding options
    - targeted green:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: `47 tests OK`
    - full suite:
      `python -m unittest discover tests`: `480 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke without an agent bridge URL:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r23-agent-native-bridge-contract-no-url --output logs\runtime\major-real-no-loss-r23-agent-native-bridge-contract-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=5/5`, and
      `background_screenshot_focus_stable=true`
  - current conclusion:
    - the unified architecture now has reusable native bridge contracts for
      both IM-style apps and agent app surfaces
    - Codex App and Claude Desktop are now blocked by missing real app-side
      bridge endpoints, not by the orchestration/control architecture
    - the next concrete action is to implement or install real Windows-side
      app bridges for Codex App / Claude Desktop, then run an opt-in bridge
      send test with required readback markers
- 2026-05-29 hardened Agent App native bridge surface identity:
  - implementation:
    - `agent_native_bridge` requests now require a declared
      `required_surface_kind=desktop_app`
    - capability reports must expose a matching `surface_kind` /
      `surface_type` / `bridge_surface`; a CLI-only bridge now fails with
      `agent_native_bridge_surface_not_ready`
    - `agent_native_connector_probe` carries `surface_kind` into endpoint
      metadata and refuses to mark `endpoint_type=agent_native_bridge` ready
      unless the endpoint is explicitly a `desktop_app` bridge
    - `agent_app_bridge` now checks the endpoint metadata before treating an
      agent native bridge as target-ready, so CLI bridges cannot satisfy
      Codex App / Claude Desktop background-chat requirements
  - official-doc basis:
    - Python `dataclasses` docs were checked before changing the request
      dataclass contract
    - Python `http.server` docs were checked for the local bridge test server
      pattern
  - validation:
    - red tests first:
      `test_sender_refuses_cli_only_bridge_for_desktop_app_request`,
      `test_agent_native_bridge_endpoint_does_not_accept_cli_surface_for_app`,
      and `test_agent_native_bridge_cli_surface_cannot_satisfy_app_request`
      failed before implementation
    - targeted green:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_bridge`: `29 tests OK`
    - full suite:
      `python -m unittest discover tests`: `483 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke without app bridge URLs:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r24-agent-native-bridge-surface-gate-no-url --output logs\runtime\major-real-no-loss-r24-agent-native-bridge-surface-gate-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=5/5`, and
      `background_screenshot_focus_stable=true`
  - current conclusion:
    - the generic app bridge contract is now harder to misuse: background app
      control cannot be marked verified by a CLI-only endpoint
    - the next implementation target remains a real desktop-app bridge
      endpoint for Codex App / Claude Desktop, or a WeChat native connector
      that exposes File Transfer Assistant without foreground takeover
- 2026-05-29 hardened Agent App native bridge desktop app binding:
  - implementation:
    - `AgentNativeBridgeRequest` now carries expected desktop app evidence:
      process names, matched PIDs, and matched HWNDs
    - bridge dry-run now requires `app_binding` / `desktop_app_binding` /
      `target_app` evidence for `required_surface_kind=desktop_app`
    - a bridge that is unbound, or bound to the wrong desktop process, fails
      with `agent_native_bridge_app_binding_not_ready`
    - `agent_native_connector_probe` now propagates app binding metadata,
      expected process/PID/HWND evidence, and refuses to mark a native bridge
      endpoint ready unless the binding matches the requested desktop app
    - `agent_app_bridge` now rechecks agent-native endpoint metadata before
      satisfying Codex App / Claude Desktop target readiness, so a standalone
      local service cannot be mistaken for app control
  - official-doc basis:
    - Python `dataclasses` docs were checked before extending the request
      dataclass contract
    - Python `http.server` docs were checked for the local fake bridge test
      server pattern
  - validation:
    - red tests first:
      `test_sender_refuses_unbound_bridge_for_desktop_app_request`,
      `test_sender_refuses_bridge_bound_to_wrong_desktop_process`,
      `test_agent_native_bridge_endpoint_requires_matching_app_binding`,
      `test_agent_native_bridge_unbound_endpoint_cannot_satisfy_app_request`,
      and `test_agent_native_bridge_wrong_app_binding_cannot_satisfy_app_request`
      failed before implementation
    - targeted green:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_bridge`: `34 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: `55 tests OK`
    - full suite:
      `python -m unittest discover tests`: `488 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke without app bridge URLs:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r25-agent-native-bridge-app-binding-no-url --output logs\runtime\major-real-no-loss-r25-agent-native-bridge-app-binding-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=5/5`, and
      `background_screenshot_focus_stable=true`
  - current conclusion:
    - the app native bridge contract now requires three layers before a
      background app-chat route can be considered real:
      `desktop_app` surface, matching agent adapter, and matching desktop app
      binding evidence
    - current remaining true gaps are unchanged: real Codex App / Claude
      Desktop native bridge endpoints, and a real WeChat native connector for
      deterministic background send
- 2026-05-29 added read-only agent native bridge registry discovery:
  - implementation:
    - added `native_bridge_registry` for local-only agent native bridge URL
      discovery from:
      `OPENWUKONG_AGENT_NATIVE_BRIDGE_URLS`,
      `OPENWUKONG_AGENT_NATIVE_BRIDGE_REGISTRY_PATHS`,
      explicit registry file paths, and default user/machine registry paths
    - registry discovery accepts only local HTTP(S) loopback endpoints and
      filters entries by bridge type, agent id, enabled flag, and desktop app
      surface kind before probing
    - `agent_native_connector_probe` now merges explicit URLs with registry
      discovery, then still applies the existing native bridge dry-run,
      desktop surface, and desktop app binding gates
    - `agent_app_real_no_loss` and `major_real_no_loss` now pass registry
      paths through to agent app probes and expose
      `--agent-native-bridge-registry`
  - official-doc basis:
    - Python `json` docs were checked before defining the registry file parser
    - Python `urllib.parse` docs were checked before local URL validation
  - validation:
    - red tests first:
      `test_discovers_agent_native_bridge_endpoint_from_registry_file`,
      `test_passes_agent_native_bridge_registry_paths_to_native_probe`,
      and `test_runner_passes_agent_native_bridge_registry_paths_to_agent_app_runner`
      failed before implementation
    - targeted green:
      `python -m unittest tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_discovers_agent_native_bridge_endpoint_from_registry_file tests.test_agent_app_real_no_loss.AgentAppRealNoLossTests.test_passes_agent_native_bridge_registry_paths_to_native_probe tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_passes_agent_native_bridge_registry_paths_to_agent_app_runner`: `3 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_bridge tests.test_agent_native_bridge`: `58 tests OK`
    - full suite:
      `python -m unittest discover tests`: `491 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke without any explicit bridge URL:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r26-agent-native-bridge-registry-no-url --output logs\runtime\major-real-no-loss-r26-agent-native-bridge-registry-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=5/5`, and
      `background_screenshot_focus_stable=true`
  - current conclusion:
    - Codex App / Claude Desktop native bridge endpoints can now be installed
      and discovered as local plugins instead of requiring per-run manual URL
      flags
    - the remaining work is to build or install the actual app-side bridges;
      the orchestration layer will now discover them and still reject unsafe,
      remote, CLI-only, or unbound endpoints
- 2026-05-29 added a CDP-backed Agent App native bridge and fixed no-loss
  focus attribution:
  - implementation:
    - added `agent_native_cdp_bridge`, a real app-side bridge implementation
      that exposes the existing `/v1/agent/capabilities` and `/v1/agent/chat`
      contract over a local HTTP server and submits messages through Chrome
      DevTools Protocol `Runtime.evaluate`
    - the bridge reports `surface_kind=desktop_app`, explicit
      `app_binding` evidence, and keeps `control_attempts`,
      `window_input_attempts`, `keyboard_input_attempts`, and
      `clipboard_write_attempts` at zero
    - target selection prefers explicit DevTools target URL, then target/window
      title, then a conservative page/webview fallback
    - `major_real_no_loss` now distinguishes raw foreground stability from
      automation-caused focus risk:
      `automation_focus_risk_attempts == 0` makes a pure observation run
      `automation_focus_safe=true`, while bridge sends, agent commands,
      launches, or window-input attempts still make focus changes fail the run
    - report JSON now includes both raw `background_screenshot_focus_stable`
      evidence and the derived `automation_focus_safe` decision
  - official-doc basis:
    - Chrome DevTools Protocol `Runtime.evaluate` docs were checked before
      implementing the CDP bridge execution path
    - Python `json` and `urllib.parse` docs were already checked for bridge
      registry parsing and local URL validation in the previous step
  - validation:
    - red tests first:
      `tests.test_agent_native_cdp_bridge` failed on missing module before the
      bridge was implemented
    - red tests first:
      `test_safe_run_allows_unrelated_focus_change_when_no_automation_attempts`
      and
      `test_safe_run_fails_focus_change_when_bridge_send_was_attempted`
      failed before `automation_focus_safe` existed
    - targeted green:
      `python -m unittest tests.test_agent_native_cdp_bridge`: `3 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_native_cdp_bridge tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: `63 tests OK`
    - full suite:
      `python -m unittest discover tests`: `496 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - real no-loss smoke before attribution fix:
      R27 produced zero automation attempts and 5/5 background screenshots,
      but failed because the raw foreground changed during pure observation
    - real no-loss smoke after attribution fix:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r28-agent-native-cdp-bridge-focus-attribution-no-url --output logs\runtime\major-real-no-loss-r28-agent-native-cdp-bridge-focus-attribution-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=6/6`,
      `background_screenshot_focus_stable=true`,
      `automation_focus_risk_attempts=0`, and
      `automation_focus_safe=true`
  - current conclusion:
    - Codex App / Claude Desktop / Cursor-style desktop app control now has a
      concrete CDP-native bridge implementation when the app exposes a local
      DevTools endpoint or an installed helper registers one
    - no-loss reporting now avoids false negatives from unrelated user focus
      changes during pure observation, without weakening the rule that any
      automation send/launch/window-input attempt must preserve foreground
      safety
    - remaining true gaps are still app-side endpoints and product-specific
      connectors: WeChat native bridge, Codex App bridge installation, Claude
      Desktop bridge installation, and auth/permission for real agent execution
- 2026-05-29 tightened direct DevTools app-bridge routing for Electron-style
  agent apps:
  - implementation:
    - `AgentAppBridgeRequest` now treats a bound local DevTools endpoint as a
      valid native app control surface even when UIA does not expose a semantic
      composer, as long as the UIA probe has already matched the target app
      surface and the endpoint is bound to the expected desktop process
    - direct CDP sends now score DevTools page/webview targets by task name and
      project name before falling back to the first page/webview, reducing the
      risk of sending to an unrelated settings/about target
    - the DevTools route still records zero `control_attempts` and zero
      `window_input_attempts`; send attempts are still gated behind the
      explicit `allow_app_bridge_send` path
  - official-doc basis:
    - Chrome DevTools Protocol `Target` docs were checked for target discovery
      semantics and target IDs
    - Chrome DevTools Protocol `Runtime.evaluate` docs were checked for the
      existing execution command used by the CDP sender
  - validation:
    - red tests first:
      `test_bound_devtools_endpoint_is_ready_without_uia_semantic_composer`
      failed with `app_bridge_target_not_ready` before implementation
    - red tests first:
      `test_cdp_adapter_prefers_target_matching_project_or_task` failed
      because CDP selected `page-settings` instead of `page-openwukong`
    - targeted green:
      `python -m unittest tests.test_agent_app_bridge.AgentAppBridgeTests.test_bound_devtools_endpoint_is_ready_without_uia_semantic_composer tests.test_agent_app_bridge.AgentAppBridgeTests.test_cdp_adapter_prefers_target_matching_project_or_task`: `2 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: `56 tests OK`
    - full suite:
      `python -m unittest discover tests`: `498 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - owned local DevTools fixture:
      `python -m openwukong.evaluation.agent_app_bridge_fixture_smoke --json`
      produced `ok=true`, `decision=agent_app_bridge_fixture_smoke_verified`,
      `Runtime.evaluate` request count `1`, `desktop_control_attempts=0`, and
      `window_input_attempts=0`
    - real no-loss smoke without bridge/send opt-in:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r29-bound-devtools-target-selection-no-url --output logs\runtime\major-real-no-loss-r29-bound-devtools-target-selection-no-url\report.json --json`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `background_screenshot_success_count=6/6`,
      `automation_focus_risk_attempts=0`, and
      `automation_focus_safe=true`
  - current conclusion:
    - if Codex App / Claude Desktop / Cursor exposes a local DevTools endpoint
      on the actual desktop process, OpenWukong can now move from
      `gated_native_endpoint_missing` to a precise CDP dry-run route even when
      Windows accessibility does not expose the chat input
    - the current live machine still did not expose those local app endpoints
      during R29, so real app chat remains gated rather than falling back to
      foreground keyboard, mouse, or clipboard
  - additional live verification:
    - R30 ran the owned-browser plus agent-CLI opt-in path:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r30-owned-browser-agent-cli --output logs\runtime\major-real-no-loss-r30-owned-browser-agent-cli\report.json --json --allow-owned-browser-helper-launch --owned-browser-debug-port 9488 --owned-browser-url "data:text/html,<title>OpenWukong Major R30</title><body>OpenWukong Major R30</body>" --allow-agent-cli-execution --agent-cli-timeout-sec 120`
    - R30 produced `safe_run_ok=true`, `control_attempts=0`,
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=2`,
      `owned_app_launch_attempts=1`,
      `background_screenshot_success_count=6/6`, and
      `automation_focus_safe=true`
    - R30 verified:
      `wechat_background_observation`, `word_background_document`,
      `browser_background_research`, `file_background_search`, and
      `codex_cli_background_task`
    - R30 still gated:
      `wechat_background_send` with `wechat_native_bridge_url_missing`,
      `codex_app_background_chat`, `claude_desktop_background_chat`, and
      `cursor_background_chat` with `gated_native_endpoint_missing`
    - R30 still reports `claude_cli_background_task=auth_required` because
      the local Claude CLI returned `Not logged in - Please run /login`
- 2026-05-29 added explicit local DevTools URL probing with process-port
  ownership validation for agent app surfaces:
  - implementation:
    - `NativeProcessSnapshot` now records `listening_ports`
    - `list_native_processes` collects TCP listening ports per PID through
      `psutil.net_connections(kind="tcp")`
    - `agent_native_connector_probe` now accepts explicit local
      `debugger_urls` / `--debugger-url`, but marks them ready only when the
      URL is local loopback and the port belongs to a matching target app
      process
    - unbound explicit endpoints are recorded as
      `devtools_endpoint_not_bound_to_agent_process` and are not probed or
      treated as ready
    - `agent_app_real_no_loss` and `major_real_no_loss` now forward explicit
      debugger URLs into the same safe probe path
  - official-doc basis:
    - Chrome DevTools Protocol `Target` docs were checked for DevTools target
      discovery shape
    - psutil `net_connections` docs were checked for process-port ownership
      discovery
  - validation:
    - red tests first:
      `test_reports_ready_from_explicit_debugger_url_owned_by_matching_process_port`,
      `test_explicit_debugger_url_is_not_ready_without_matching_process_port_binding`,
      `test_passes_explicit_debugger_urls_to_native_probe`, and
      `test_runner_passes_explicit_debugger_urls_to_agent_app_runner` failed
      before the new API existed
    - targeted green:
      `python -m unittest tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_reports_ready_from_explicit_debugger_url_owned_by_matching_process_port tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_explicit_debugger_url_is_not_ready_without_matching_process_port_binding tests.test_agent_app_real_no_loss.AgentAppRealNoLossTests.test_passes_explicit_debugger_urls_to_native_probe tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_passes_explicit_debugger_urls_to_agent_app_runner`: `4 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_bridge`: `60 tests OK`
    - full suite:
      `python -m unittest discover tests`: `502 tests OK`
    - compile/check:
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
    - R31 unbound explicit URL smoke:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r31-explicit-debugger-url-unbound --output logs\runtime\major-real-no-loss-r31-explicit-debugger-url-unbound\report.json --json --debugger-url http://127.0.0.1:9444`
      produced `safe_run_ok=true`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `automation_focus_safe=true`, and each app surface endpoint reported
      `devtools_endpoint_not_bound_to_agent_process`
  - current conclusion:
    - users or installers can now expose/declare a local DevTools endpoint
      without relying on command-line flag parsing, while the safety gate still
      refuses endpoints that are not owned by the matched desktop app process
    - this directly supports real Codex App / Claude Desktop / Cursor app
      background control once the app is launched with an owned local DevTools
      port or a companion bridge registers one
- 2026-05-29 added automatic owned-process DevTools port discovery for agent
  app surfaces:
  - implementation:
    - `agent_native_connector_probe` now scans TCP listening ports already
      owned by the matched target desktop app process, not only command-line
      `--remote-debugging-port` flags or manually supplied `--debugger-url`
    - the probe first reads local `/json/version`; only ports whose response
      looks like Chrome DevTools Protocol are retained as endpoints
    - ordinary non-DevTools listening ports are suppressed instead of being
      reported as unhealthy native endpoints
    - explicitly supplied debugger URLs keep precedence over automatic
      listening-port discovery so user/installer configuration remains the
      authoritative binding when both point to the same port
  - official-doc basis:
    - Chrome DevTools Protocol `Target` docs were checked again for target
      discovery shape
    - psutil `net_connections` docs were checked for process-owned listening
      port discovery
  - validation:
    - red tests first:
      `test_auto_discovers_devtools_from_matching_process_listening_port` and
      `test_auto_listening_non_devtools_port_is_suppressed` failed because no
      listening-port probing occurred
    - targeted green:
      `python -m unittest tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_auto_discovers_devtools_from_matching_process_listening_port tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_auto_listening_non_devtools_port_is_suppressed`: `2 tests OK`
    - focused regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_bridge tests.test_agent_native_cdp_bridge`: `65 tests OK`
    - R32 real no-loss smoke without launch/send opt-in:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r32-auto-listening-devtools --output logs\runtime\major-real-no-loss-r32-auto-listening-devtools\report.json --json`
      produced `safe_run_ok=true`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success_count=6/6`,
      `background_screenshot_focus_stable=true`, and
      `automation_focus_safe=true`
    - R32 found no ready automatic CDP/native endpoint on the current live
      Codex App / Claude Desktop / Cursor processes; all three app-chat
      surfaces remained correctly gated with
      `gated_native_endpoint_missing`
  - current conclusion:
    - the app-native discovery path is now less dependent on manual flags:
      if a matched Electron-style desktop app already owns a local CDP
      listening port, OpenWukong can discover it automatically in read-only
      mode and route it into the existing bridge contract
    - current live machine evidence still says Codex App / Claude Desktop /
      Cursor do not expose a usable local background control endpoint in their
      present running state, so the next real unlock is starting/installing an
      owned app-side bridge or DevTools-enabled helper without stealing focus
- 2026-05-29 added no-focus managed lifecycle for the agent native CDP bridge:
  - implementation:
    - `session_readiness_plan` now has an `agent-native-cdp-bridge` route that
      launches `openwukong.control.agent_native_cdp_bridge` as a managed
      background helper without requiring an isolated browser profile or
      foreground window takeover
    - helper actions are marked as `managed_background_helper`, so execution is
      allowed only through the explicit helper lifecycle and cleanup manifest
      path
    - the CDP bridge helper can write a local native bridge registry file,
      allowing the existing registry discovery path to pick up installed or
      started app-side bridges without per-run manual URL flags
    - the CLI exposes the helper parameters needed by installers or scenario
      runners: agent id/name, local host/port, registry path, debugger URL, app
      binding evidence, project/task, and target selectors
  - official-doc basis:
    - Python `subprocess` docs were checked before adding the managed helper
      process lifecycle and manifest-backed stop path
  - validation:
    - red tests first:
      `test_agent_native_cdp_bridge_plan_uses_background_python_helper_and_registry`,
      `test_execute_allows_agent_native_cdp_bridge_managed_background_helper`,
      `test_stop_manifest_accepts_agent_native_cdp_bridge_helper`,
      `test_write_registry_creates_local_agent_native_bridge_entry`, and
      `test_cli_outputs_agent_native_cdp_bridge_plan_json` failed before the
      route, registry writer, stop allowlist, and CLI options existed
    - targeted/focused green:
      `python -m unittest tests.test_session_readiness_plan tests.test_agent_native_cdp_bridge tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`: `71 tests OK`
    - R33 no-focus helper smoke:
      `python -m openwukong.evaluation.session_readiness_plan --route agent-native-cdp-bridge ... --execute`
      started managed helper PID `23908`, wrote
      `logs\runtime\agent-native-cdp-bridge-r33\native-bridges.json`, and kept
      `control_attempts=0`
    - R33 read-only registry probe:
      `python -m openwukong.evaluation.agent_native_connector_probe --agent "codex app" ... --agent-native-bridge-registry logs\runtime\agent-native-cdp-bridge-r33\native-bridges.json`
      discovered the registry endpoint, rejected it as unhealthy because the
      test used a fake debugger URL, and kept `control_attempts=0`
    - R33 cleanup:
      `python -m openwukong.evaluation.session_readiness_plan --stop-manifest logs\runtime\agent-native-cdp-bridge-r33\manifest.json --json`
      reported `stop_attempts=1` and `status=stopped`; a follow-up process
      check confirmed PID `23908` was gone
    - full verification:
      `python -m unittest discover tests`: `509 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - OpenWukong now has the no-focus helper lifecycle needed to start,
      register, discover, probe, and stop app-side CDP bridges without
      keyboard, mouse, clipboard, or foreground takeover
    - this does not make Codex App / Claude Desktop / Cursor app chat fully
      unlocked by itself; those products still need a real owned DevTools
      endpoint or installed app-side bridge, after which the current control
      layer can discover and gate the route precisely
- 2026-05-29 integrated the no-focus agent native CDP helper into the unified
  major real no-loss runner:
  - implementation:
    - the CDP helper registry writer now merges entries instead of overwriting
      the file, so Codex App / Claude Desktop / Cursor-style helpers can share
      one local registry without deleting each other
    - `major_real_no_loss` now has an explicit
      `--allow-agent-native-cdp-bridge-helper-launch` path that starts the
      managed Python helper, waits for its registry entry, forwards that
      registry to agent app probes, and stops it through the session readiness
      manifest
    - the major report now exposes
      `agent_native_cdp_bridge_launch_attempts`,
      `agent_native_cdp_bridge_stop_attempts`, and
      `agent_native_cdp_bridge_cleanup_ok`
    - fixed a critical cleanup-token bug where the target app debugger URL
      from `--debugger-url http://127...` could be treated as an owned-process
      cleanup token; in a parent major run this could match and kill the
      current runner before it wrote the final report
    - residual cleanup now excludes the target debugger URL and includes the
      registry path as the owned helper token
  - official-doc basis:
    - Python `subprocess` docs were checked again before changing managed
      helper launch/cleanup behavior
  - validation:
    - red tests first:
      `test_write_registry_preserves_other_agent_bridge_entries` failed before
      registry merge existed
    - red tests first:
      `test_runner_prepares_agent_native_cdp_bridge_helper_and_forwards_registry`,
      `test_prepare_agent_native_cdp_bridge_helper_launches_and_waits_for_registry`,
      and `test_cli_forwards_agent_native_cdp_bridge_helper_options` failed
      before major-runner integration and CLI flags existed
    - red test first:
      `test_agent_native_cdp_bridge_residual_tokens_exclude_target_debugger_url`
      failed because the target debugger URL was included in cleanup tokens and
      the split `--registry-path` value was missing
    - focused green:
      `python -m unittest tests.test_agent_native_cdp_bridge tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_session_readiness_plan`: `58 tests OK`
    - R37 real no-loss smoke:
      `run_major_scenario_real_no_loss(... allow_agent_native_cdp_bridge_helper_launch=True, agent_apps=("codex app",), cli_agents=(), debugger_url=http://127.0.0.1:65530 ...)`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `agent_native_cdp_bridge_launch_attempts=1`,
      `agent_native_cdp_bridge_stop_attempts=1`,
      `agent_native_cdp_bridge_cleanup_ok=true`, and
      `bridge_send_attempts=0`
    - R37 intentionally used a fake debugger URL, so agent app chat stayed
      gated with `agent_native_connector_endpoint_unhealthy` instead of
      sending anything
    - R37 helper PID `14020` was confirmed gone after cleanup
    - full verification:
      `python -m unittest discover tests`: `515 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the unified no-loss runner can now start, register, probe, and clean up
      an app-side native CDP bridge as part of the same acceptance report used
      for WeChat / Word / Browser / File / Codex / Claude / Cursor scenarios
    - the current machine still needs a real owned DevTools/native endpoint for
      Codex App / Claude Desktop / Cursor app chat to move from gated to
      verified send; the runner now has the correct no-focus lifecycle once
      such an endpoint exists
- 2026-05-29 extended the agent native CDP helper path into a multi-app helper
  fleet:
  - implementation:
    - `major_real_no_loss` now accepts
      `agent_native_cdp_bridge_helper_specs`, allowing one run to prepare
      multiple background CDP bridge helpers for Codex App / Claude Desktop /
      Cursor-style app surfaces
    - added `prepare_agent_native_cdp_bridge_helper_fleet`, which launches each
      helper in an isolated output subdirectory, aggregates launch/stop/cleanup
      counts, and forwards every ready helper registry to agent app probes
    - added CLI support through repeated
      `--agent-native-cdp-bridge-helper-spec` JSON objects, so a real no-loss
      run can configure several app-side helpers without a new flag family per
      product
    - helper fleet reports now expose
      `mode=agent-native-cdp-bridge-helper-fleet`, per-helper subreports,
      `registry_paths`, aggregate `launch_attempts`, aggregate
      `stop_attempts`, and aggregate `cleanup_ok`
  - official-doc basis:
    - Python `argparse` docs were checked before adding repeated JSON helper
      spec CLI arguments
  - validation:
    - red test first:
      `test_runner_prepares_agent_native_cdp_bridge_helper_fleet` failed
      because `run_major_scenario_real_no_loss` did not accept helper specs
    - red test first:
      `test_cli_forwards_agent_native_cdp_bridge_helper_specs` failed because
      the CLI did not accept repeated helper spec arguments
    - focused green:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_native_cdp_bridge tests.test_session_readiness_plan tests.test_agent_app_real_no_loss`: `61 tests OK`
    - R38 real no-loss smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=(), allow_agent_native_cdp_bridge_helper_launch=True, agent_native_cdp_bridge_helper_specs=(codex, claude, cursor fake-debugger specs))`
      produced `safe_run_ok=true`, `goal_complete=false`,
      `agent_native_cdp_bridge_launch_attempts=3`,
      `agent_native_cdp_bridge_stop_attempts=3`,
      `agent_native_cdp_bridge_cleanup_ok=true`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `bridge_send_attempts=0`
    - R38 intentionally used fake debugger URLs, so all three app chat
      surfaces stayed gated with `agent_native_connector_endpoint_unhealthy`
      rather than sending anything
    - R38 helper PIDs `93828`, `92968`, and `14804` were confirmed gone after
      cleanup
    - full verification:
      `python -m unittest discover tests`: `517 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the acceptance runner can now exercise Codex App / Claude Desktop /
      Cursor helper lifecycle together in one no-focus run
    - this is the correct infrastructure for the final real-send step; the
      remaining gap is still actual owned app-side endpoints for those products
      instead of fake debugger URLs
- 2026-05-29 added a machine-readable agent app endpoint acceptance package:
  - implementation:
    - `major_real_no_loss` now emits top-level
      `agent_app_endpoint_acceptance`
    - the package summarizes each Codex App / Claude Desktop / Cursor app
      surface with `agent_id`, current status, endpoint readiness,
      send-verification state, observed endpoint errors, no-focus requirement,
      and `safe_to_send_now`
    - each case now includes a reusable `helper_spec_template` for the
      no-focus `--agent-native-cdp-bridge-helper-spec` path, including the
      expected process name, bridge port, and placeholder owned DevTools URL
    - helper fleet evidence is attached back to the matching agent case through
      `helper_status`, so fake, unhealthy, or real helper state is visible next
      to the endpoint acceptance decision
  - official-doc basis:
    - Python `dataclasses` docs were checked before extending the dataclass
      report payload with a computed property
  - validation:
    - red test first:
      `test_report_exposes_agent_app_endpoint_acceptance_package` failed with
      missing `agent_app_endpoint_acceptance`
    - targeted green:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_report_exposes_agent_app_endpoint_acceptance_package`: OK
    - focused regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_agent_native_cdp_bridge tests.test_session_readiness_plan`: `62 tests OK`
    - R39 real no-loss smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=())`
      wrote
      `logs/runtime/major-real-no-loss-r39-agent-endpoint-acceptance/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `endpoint_total_cases=3`, and
      `endpoint_safe_to_send_now=false`
    - R39 reported all three app surfaces as
      `provide_owned_debugger_url_or_install_agent_native_bridge`
    - full verification:
      `python -m unittest discover tests`: `518 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the major acceptance report now tells the next runner or installer
      exactly what each agent app needs before any app-chat send can be
      attempted
    - the system is still correctly not claiming unified precise background
      app-chat control for Codex App / Claude Desktop / Cursor until a real
      owned local DevTools/native endpoint is present and send readback passes
- 2026-05-29 added the owned agent-app DevTools launch route:
  - implementation:
    - `session_readiness_plan` now supports route
      `agent-app-devtools-owned`
    - the route launches an explicitly provided agent desktop app executable
      with an isolated `--user-data-dir`, `--remote-debugging-port`,
      `--no-first-run`, and `--disable-crash-reporter`
    - the Windows subprocess launcher now uses `SW_SHOWMINNOACTIVE` and a new
      process group for readiness helpers, so owned helper launches request a
      minimized/no-activate startup instead of normal foreground activation
    - manifest stop now accepts `launch_agent_app_devtools_owned` and cleans
      residual owned processes by the recorded remote-debugging port and
      isolated profile token
    - the readiness CLI exposes:
      `--agent-app-executable`, `--agent-app-debug-port`,
      `--agent-app-user-data-dir`, and `--agent-app-url`
    - `agent_app_endpoint_acceptance` now includes
      `owned_devtools_launch_plan_template` for Codex App / Claude Desktop /
      Cursor with default readiness URLs:
      `http://127.0.0.1:19555`, `http://127.0.0.1:19556`, and
      `http://127.0.0.1:19557`
  - official-doc basis:
    - Electron / Chromium-style command-line debugging behavior and Python
      `subprocess` startup handling were checked before adding the route and
      no-activate launcher path
  - validation:
    - red tests first:
      `test_agent_app_devtools_owned_plan_uses_isolated_profile_and_remote_debugging`,
      `test_execute_allows_agent_app_devtools_owned_and_writes_manifest`,
      `test_cli_outputs_agent_app_devtools_owned_plan_json`,
      `test_stop_manifest_accepts_agent_app_devtools_owned_helper`, and
      `test_subprocess_launcher_uses_no_activate_startupinfo_on_windows`
      failed before the route, CLI args, stop allowlist, and startup info
      existed
    - red test first:
      `test_report_exposes_agent_app_endpoint_acceptance_package` failed before
      the endpoint package included an owned DevTools launch plan template
    - focused green:
      `python -m unittest tests.test_session_readiness_plan tests.test_major_real_no_loss`: `46 tests OK`
    - R40 plan smoke:
      `python -m openwukong.evaluation.session_readiness_plan --route agent-app-devtools-owned --agent-app-executable Codex.exe --agent-app-debug-port 19555 --agent-app-user-data-dir logs/runtime/agent-app-devtools/codex/profile --json`
      produced a plan-only report with `control_attempts=0`,
      `foreground_required=false`, an isolated profile, and readiness URL
      `http://127.0.0.1:19555`
    - R40 real no-loss smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=())`
      wrote
      `logs/runtime/major-real-no-loss-r40-agent-app-devtools-plan/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, and launch templates for all three app
      surfaces with `startup_mode=minimized_no_activate`
    - full verification:
      `python -m unittest discover tests`: `523 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the remaining app-surface gap is no longer only "provide a debugger URL";
      OpenWukong can now generate and safely manage the owned app launch shape
      needed to create one
    - the route is not yet auto-executed inside the major runner because real
      GUI app launch still requires explicit permission and app-specific path
      resolution; the current default remains plan/report-only and no-focus
- 2026-05-29 added safe agent app executable resolution for owned DevTools:
  - implementation:
    - `WindowsAppResolver` now treats explicit `codex app` / `codex desktop`
      requests as desktop-surface requests and refuses to satisfy them with
      `codex.cmd`, extension worker `codex.exe`, or other CLI/helper paths
    - the existing Claude surface split was tightened so explicit
      `claude app` / `claude desktop` also returns `app_not_found` when only a
      CLI candidate is available, instead of falling back to CLI transport
    - `major_real_no_loss` now builds a read-only
      `agent_app_devtools_resolution` report for Codex App / Claude Desktop /
      Cursor and exposes it both top-level and inside subreports
    - `agent_app_endpoint_acceptance` now fills
      `owned_devtools_launch_plan_template.executable` from the resolved app
      executable path when available, and records `executable_ready` plus
      `executable_resolution_status`
  - official-doc basis:
    - Microsoft Windows application registration / App Paths and
      PowerShell `Get-StartApps` documentation were checked before relying on
      resolver evidence sources for executable and packaged-app identity
  - validation:
    - red tests first:
      `test_codex_app_alias_requires_desktop_surface_not_cli_path` and
      `test_claude_app_alias_requires_desktop_surface_not_cli_path` failed
      because app aliases could still resolve to CLI paths
    - red test first:
      `test_report_exposes_agent_app_endpoint_acceptance_package` failed before
      `agent_app_devtools_resolution` was emitted top-level and before launch
      templates consumed resolved executable paths
    - focused green:
      `python -m unittest tests.test_agent_surface_report tests.test_app_resolution tests.test_major_real_no_loss`: `43 tests OK`
    - R41 real read-only app resolution smoke:
      `python -m openwukong.evaluation.app_resolution_report --app-name codex --app-name "codex app" --app-name "claude desktop" --app-name cursor --json`
      produced `control_attempts=0`, resolved all four names, and selected
      the real desktop app paths for Codex App, Claude Desktop, and Cursor
    - R41 real no-loss smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=())`
      wrote
      `logs/runtime/major-real-no-loss-r41-agent-app-resolution/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, and `executable_ready=true` for all three app
      launch templates
    - full verification:
      `python -m unittest discover tests`: `525 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - current machine evidence now proves OpenWukong can identify the real
      Codex App, Claude Desktop, and Cursor executable paths without hardcoded
      install locations and without confusing them with CLI/helper processes
    - the remaining app-chat gap is explicit opt-in execution of the owned
      DevTools launch route, probing the new endpoint, then performing native
      bridge send/readback verification without foreground takeover
- 2026-05-29 integrated owned agent-app DevTools launch into the unified
  no-loss runner behind an explicit opt-in gate:
  - implementation:
    - `major_real_no_loss` now accepts
      `allow_agent_app_devtools_owned_launch`
    - the runner now builds the read-only `agent_app_devtools_resolution`
      report before agent app probing, then can prepare an
      `agent-app-devtools-owned-launch-fleet` from those resolved executable
      paths
    - `prepare_agent_app_devtools_owned_launch_fleet` launches only
      `executable_ready=true` app surfaces through the existing
      `agent-app-devtools-owned` session readiness route, using per-agent
      isolated profiles and default local DevTools ports:
      Codex `19555`, Claude `19556`, Cursor `19557`
    - the runner forwards ready owned DevTools debugger URLs to
      `agent_app_real_no_loss`, and then stops the owned launch manifests in
      `finally`
    - the major report now exposes
      `agent_app_devtools_launch_attempts`,
      `agent_app_devtools_stop_attempts`,
      `agent_app_devtools_cleanup_ok`, and a new
      `subreports.agent_app_devtools_owned_launch`
    - the CLI exposes `--allow-agent-app-devtools-owned-launch`
    - default behavior remains no GUI launch: without the explicit flag,
      `agent_app_devtools_launch_attempts=0`
  - official-doc basis:
    - Python `subprocess` docs were checked for the managed helper lifecycle
      and Python `argparse` docs were checked before adding the CLI gate
  - validation:
    - red tests first:
      `test_runner_prepares_agent_app_devtools_owned_launch_and_forwards_debugger_urls`,
      `test_prepare_agent_app_devtools_owned_launch_fleet_launches_resolved_apps`,
      and `test_cli_forwards_agent_app_devtools_owned_launch_option` failed
      before runner integration, fleet preparation, and CLI support existed
    - targeted green:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_prepares_agent_app_devtools_owned_launch_and_forwards_debugger_urls tests.test_major_real_no_loss.MajorRealNoLossTests.test_prepare_agent_app_devtools_owned_launch_fleet_launches_resolved_apps tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_forwards_agent_app_devtools_owned_launch_option`: OK
    - focused regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_session_readiness_plan tests.test_app_resolution tests.test_agent_surface_report`: `89 tests OK`
    - R42 real no-launch smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=())`
      wrote
      `logs/runtime/major-real-no-loss-r42-agent-app-devtools-owned-no-launch/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_app_devtools_launch_attempts=0`,
      `agent_app_devtools_stop_attempts=0`,
      `agent_app_devtools_cleanup_ok=true`, and
      `executable_ready_cases=3`
    - full verification:
      `python -m unittest discover tests`: `528 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - OpenWukong now has the full no-loss runner lifecycle to resolve,
      launch, forward, and clean up owned Codex App / Claude Desktop / Cursor
      DevTools endpoints, but it executes only with an explicit opt-in flag
    - the next gap is a real opt-in background launch test on this machine,
      then endpoint probing and native bridge send/readback verification
      against the launched owned endpoints
- 2026-05-29 completed the first real opt-in owned agent-app DevTools launch
  smoke on this machine:
  - validation:
    - R43 real owned launch smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=(), allow_agent_app_devtools_owned_launch=True)`
      wrote
      `logs/runtime/major-real-no-loss-r43-agent-app-devtools-owned-real-launch/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_app_devtools_launch_attempts=3`,
      `agent_app_devtools_stop_attempts=3`,
      `agent_app_devtools_cleanup_ok=true`, and owned debugger URLs:
      `http://127.0.0.1:19555`, `http://127.0.0.1:19556`,
      `http://127.0.0.1:19557`
    - residual process scan for tokens `19555`, `19556`, `19557`, and
      `major-real-no-loss-r43-agent-app-devtools-owned-real-launch` found only
      the scanning PowerShell process itself, so no owned app/profile process
      remained after cleanup
  - current conclusion:
    - the system can now really launch and clean up owned Codex App / Claude
      Desktop / Cursor DevTools endpoints without keyboard, mouse, clipboard,
      bridge send, or window-input attempts
    - the next gap is endpoint health probing plus native bridge send/readback
      verification against those owned endpoints
- 2026-05-29 added real endpoint health gating for owned agent-app DevTools:
  - implementation:
    - `prepare_agent_app_devtools_owned_launch_fleet` now waits for each owned
      DevTools endpoint through read-only `/json/version` and `/json/list`
      probes before marking the helper `ready`
    - helper reports now include `endpoint_health`, `healthy_endpoint_count`,
      the launched PID, and command evidence
    - `agent_app_real_no_loss` can now receive `debugger_urls_by_agent`, so
      Codex / Claude / Cursor probes only receive their own owned DevTools URL
      instead of every launched endpoint
    - `major_real_no_loss` now forwards synthetic owned process evidence into
      the agent app probe process provider, binding each owned DevTools port to
      the exact launched executable/PID/port tuple before any native probe
      treats it as usable
  - official-doc basis:
    - Chrome DevTools Protocol documentation was checked before treating
      `/json/version` and `/json/list` as the health gate for a usable local
      DevTools target
  - validation:
    - red tests first:
      `test_filters_debugger_urls_by_agent_before_native_probe`,
      `test_prepare_agent_app_devtools_owned_launch_fleet_waits_for_endpoint_health`,
      and `test_runner_forwards_owned_devtools_process_provider_and_urls_by_agent`
      failed before per-agent URL routing, endpoint health wait, and owned
      process evidence forwarding existed
    - focused green:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_session_readiness_plan`: `85 tests OK`
    - R44 real owned endpoint health smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=(), allow_agent_app_devtools_owned_launch=True)`
      wrote
      `logs/runtime/major-real-no-loss-r44-agent-app-devtools-health-real-launch/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_app_devtools_launch_attempts=3`,
      `agent_app_devtools_stop_attempts=3`,
      `agent_app_devtools_cleanup_ok=true`, `healthy_endpoint_count=0`, and
      no forwarded ready debugger URLs
    - R44 evidence:
      Codex App and Claude Desktop did not expose HTTP DevTools at the requested
      ports within the health timeout; Cursor exposed `/json/version` with a
      browser-level websocket but `/json/list` returned no page targets, so it
      was correctly classified as `devtools_targets_not_ready`
    - residual process scan for tokens `19555`, `19556`, `19557`, and
      `major-real-no-loss-r44-agent-app-devtools-health-real-launch` found only
      the scanning PowerShell process itself
    - full verification:
      `python -m unittest discover tests`: `531 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the controlled endpoint health gate is now honest: owned app launch is
      real and safely cleaned up, but Codex App / Claude Desktop do not expose
      usable DevTools through this CLI flag route on this machine, and Cursor
      exposes only a browser-level endpoint without a page target
    - the next engineering route should stop assuming plain
      `--remote-debugging-port` unlocks all desktop agent apps; the next useful
      work is either Browser-level CDP `Target` domain probing for Cursor, or a
      product-specific native/extension bridge for Codex and Claude Desktop
- 2026-05-29 added Browser-level CDP `Target` probing for owned agent-app
  DevTools endpoints:
  - implementation:
    - `BrowserDevToolsClient` can now call a browser-level CDP method by
      reading `/json/version.webSocketDebuggerUrl` and sending the command over
      that websocket
    - `prepare_agent_app_devtools_owned_launch_fleet` now injects that client
      into endpoint health checks and calls `Target.getTargets` whenever
      `/json/version` exposes a browser websocket
    - endpoint health now records `browser_websocket_url`,
      `browser_level_ready`, `browser_target_count`, `browser_targets`, and
      `browser_level_error`
    - readiness remains conservative: a successful browser-level probe does
      not mark the endpoint ready unless `/json/list` exposes a target websocket
      that the current bridge can control
  - official-doc basis:
    - Chrome DevTools Protocol `Target` domain documentation was checked before
      using `Target.getTargets` as the browser-level discovery method
  - validation:
    - red tests first:
      `test_devtools_client_calls_browser_level_cdp_method_from_version_websocket`
      failed before browser-level CDP calls existed, and
      `test_prepare_agent_app_devtools_owned_launch_fleet_probes_browser_level_targets_without_ready`
      failed before the owned endpoint health report could run and record the
      browser-level target probe
    - focused green:
      `python -m unittest tests.test_browser_connector.BrowserConnectorTests.test_devtools_client_calls_browser_level_cdp_method_from_version_websocket tests.test_major_real_no_loss.MajorRealNoLossTests.test_prepare_agent_app_devtools_owned_launch_fleet_probes_browser_level_targets_without_ready tests.test_major_real_no_loss tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_session_readiness_plan`:
      `88 tests OK`
    - R45 real owned Browser-level CDP smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=(), allow_agent_app_devtools_owned_launch=True)`
      wrote
      `logs/runtime/major-real-no-loss-r45-cursor-browser-target-probe-real-launch/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_app_devtools_launch_attempts=3`,
      `agent_app_devtools_stop_attempts=3`,
      `agent_app_devtools_cleanup_ok=true`, `healthy_endpoint_count=0`, and
      no forwarded ready debugger URLs
    - R45 evidence:
      Codex App and Claude Desktop still did not expose HTTP DevTools on the
      requested owned ports; Cursor did expose a browser-level websocket and
      `Target.getTargets` succeeded with `browser_level_ready=true`, but it
      returned `browser_target_count=0`, so the system correctly kept Cursor
      `ready=false` for message submission
    - residual process scan for tokens `19555`, `19556`, `19557`, and
      `major-real-no-loss-r45-cursor-browser-target-probe-real-launch` found
      only the scanning PowerShell process itself
    - full verification:
      `python -m unittest discover tests`: `533 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - Cursor is one layer closer: the owned endpoint can be reached at the
      browser CDP layer, but this specific launch shape still exposes no
      controllable page target, so it cannot yet be used for app-chat send or
      readback
    - Codex App and Claude Desktop continue to require product-specific
      native/extension connectors or another officially supported automation
      transport; plain Electron `--remote-debugging-port` is not sufficient on
      this machine
    - next concrete action: build the app-agent transport matrix that separates
      browser-level CDP discovery, page-target CDP control, UIA semantic draft
      probes, extension/native bridges, and CLI transports, then implement the
      first product-specific bridge where a no-focus send/readback path is
      actually available
- 2026-05-29 added the app-agent transport matrix and corrected owned
  DevTools diagnostic binding:
  - implementation:
    - added `agent_app_transport_matrix`, a plan-only per-agent matrix that
      separates `agent-native-bridge`, `ide-extension-bridge`,
      `app-devtools-page-target`, `app-devtools-browser-target`,
      `uia-semantic-send`, `uia-semantic-draft`, and foreground fallback
    - `agent_app_real_no_loss` now embeds a `transport_matrix` on every case
      and emits a `transport_matrix_summary`
    - `major_real_no_loss` now exposes `agent_app_transport_matrix_summary`
      at top level
    - owned DevTools helpers that launched but did not become send-ready are
      now still forwarded as read-only diagnostic debugger URLs, and their
      synthetic process/port evidence is forwarded to the native app probe
    - `agent_native_connector_probe` now accepts a matching agent process with
      an explicit `--remote-debugging-port` in its command line even when it is
      an owned helper outside the currently selected app instance directory
    - page-target CDP is no longer marked `send_ready` unless the target
      context is verified by UIA project/task visibility or by target
      title/URL containing the requested project/task context
  - official-doc basis:
    - Chrome DevTools Protocol `Target` documentation was checked again for the
      browser/page target distinction
    - Microsoft UI Automation control pattern documentation was checked before
      treating `ValuePattern.SetValue` and `InvokePattern.Invoke` as separate
      UIA draft/send candidates rather than guaranteed background send proof
  - validation:
    - red tests first:
      `test_browser_level_devtools_is_read_only_not_send_ready`,
      `test_agent_native_bridge_is_selected_before_page_target_and_uia`,
      `test_page_target_cdp_without_verified_target_context_is_not_send_ready`,
      `test_runner_forwards_probeable_unready_owned_devtools_for_read_only_matrix`,
      `test_explicit_debugger_url_accepts_owned_remote_debugging_process_outside_selected_app_dir`,
      and `test_major_report_exposes_agent_app_transport_matrix_summary`
      failed before the matrix, diagnostic forwarding, owned helper binding,
      and target-context gating existed
    - focused green:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract`:
      `89 tests OK`
    - R47 real smoke initially proved why the target-context gate was needed:
      Cursor exposed an owned page-target DevTools endpoint, but the app probe
      reported `agent_app_target_not_visible`; the first matrix version
      incorrectly counted this as `background_send_ready_cases=1`
    - R48 real owned DevTools matrix smoke:
      `run_major_scenario_real_no_loss(... agent_apps=("codex app", "claude desktop", "cursor"), cli_agents=(), allow_agent_app_devtools_owned_launch=True)`
      wrote
      `logs/runtime/major-real-no-loss-r48-target-context-gated-matrix-real-launch/major-real-no-loss-report.json`
      and produced `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_app_devtools_launch_attempts=3`,
      `agent_app_devtools_stop_attempts=3`,
      `agent_app_devtools_cleanup_ok=true`
    - R48 evidence:
      Codex App and Claude Desktop owned DevTools ports still timed out on
      `/json/version`; Cursor exposed an owned DevTools page target and
      browser websocket, but because the requested project/task context was not
      visible or present in the target title/URL, the matrix reported
      `background_send_ready_cases=0`, `background_read_only_cases=1`,
      and `selected_send_transport_counts.none=3`
    - residual process scan for tokens `19555`, `19556`, `19557`, and
      `major-real-no-loss-r48-target-context-gated-matrix-real-launch` found
      only the scanning PowerShell process itself
    - full verification:
      `python -m unittest discover tests`: `539 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the system now has an honest app-agent transport matrix: it can tell
      transport-online, browser/page target discovery, UIA draft/send
      candidates, and real send-readback readiness apart
    - current real state is still not goal-complete for Codex App / Claude
      Desktop / Cursor app chat: Cursor has background CDP read-only/page-target
      evidence but no verified target conversation; Codex App and Claude
      Desktop still do not expose usable owned DevTools endpoints
    - next concrete action: implement or install a product-specific
      native/extension bridge for at least one app-agent surface, then rerun
      the matrix until it shows a verified `selected_send_transport` with
      readback markers and zero window input
- 2026-05-30 reran real no-loss probes for the currently prioritized app
  surfaces after narrowing the immediate focus away from VS Code/Cursor:
  - R49 agent app read-only probe:
    `python -m openwukong.evaluation.agent_app_real_no_loss --agent "codex app" --agent "claude desktop" --project-name openwukong --task-name "agent-app-background-readonly-r49" ...`
    wrote
    `logs/runtime/agent-app-readonly-r49/report.json`
  - R49 evidence:
    - `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`
    - background capture succeeded for the Codex App window through
      `PrintWindow`, with `background_screenshot_focus_stable=true`
    - Codex App was detected as a real desktop shell, but the requested
      `openwukong` project/task context was not visible in the app surface,
      no semantic composer was exposed, and no native endpoint was present
    - Claude Desktop resolved through Start Apps, but no Claude window was
      currently open, so no app-side action could be attempted
    - transport matrix stayed honest:
      `background_send_ready_cases=0`,
      `background_draft_ready_cases=0`,
      `selected_send_transport_counts.none=2`
  - R49 Word COM background probe:
    `python -m openwukong.evaluation.office_word_runner --document-path logs/runtime/word-real-r49/openwukong-word-r49.docx --marker OPENWUKONG_WORD_REAL_R49 ...`
    wrote
    `logs/runtime/word-real-r49/report.json`
  - R49 Word evidence:
    - `decision=word_background_probe_verified`, `word_started=true`,
      `visible_requested=false`, `save_verified=true`,
      `readback_verified=true`, `control_attempts=0`,
      `window_input_attempts=0`, `office_com_attempts=1`
    - residual `WINWORD` scan found no leftover Word process after quit
    - this explains why Word may not appear as a normal visible program icon
      during this test: the validated route is hidden Office COM automation on
      an owned temporary document, not foreground UI automation
  - regression:
    `python -m unittest tests.test_office_word_runner tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe`:
    `38 tests OK`
  - current conclusion:
    - Word background control is verified on this machine for owned documents
      through hidden COM automation
    - Codex App / Claude Desktop app-side chat is still not verified for
      background send/readback; the blocker is not the safety harness but lack
      of target-visible composer/native bridge evidence on the current desktop
    - next concrete action: build a first product-specific app bridge or app
      instrumentation path for Codex App or Claude Desktop, then require the
      same readback-marker and no-window-input proof before marking app-side
      agent chat complete
- 2026-05-30 added an explicit capability-completion gate to the standalone
  agent-app real no-loss report:
  - implementation:
    - `AgentAppRealNoLossReport` now exposes `goal_complete`,
      `background_send_ready_cases`, `background_draft_ready_cases`, and
      `app_side_send_verified_cases`
    - `goal_complete` is true only when every requested app-side case has a
      verified send/readback path, all cases pass, window input remains zero,
      agent command attempts remain zero, and background screenshot focus stays
      stable
    - this keeps `passed_cases` scoped to no-loss execution safety, while
      `goal_complete` records whether the product capability was actually
      proven
  - official-doc basis:
    - Python dataclasses documentation was checked before adding report-level
      derived properties and serialization fields
  - validation:
    - red tests first:
      `test_runs_agent_app_probes_without_control_attempts_and_writes_artifacts`
      and
      `test_allow_app_bridge_send_executes_ready_native_bridge_without_window_input`
      failed because `goal_complete` and `app_side_send_verified_cases` did not
      exist
    - targeted green:
      the same two tests passed after the report fields were added
    - focused regression:
      `python -m unittest tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix tests.test_major_real_no_loss tests.test_agent_native_connector_probe`:
      `64 tests OK`
    - R50 real app read-only probe:
      `logs/runtime/agent-app-readonly-r50-goal-gate/report.json` now reports
      `goal_complete=false`, `background_send_ready_cases=0`,
      `background_draft_ready_cases=0`,
      `app_side_send_verified_cases=0`, `control_attempts=0`, and
      `window_input_attempts=0`
    - full verification:
      `python -m unittest discover tests`: `539 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - future app-agent reports can no longer be confused: a safe no-loss probe
      can pass while `goal_complete=false` until real app-side send/readback is
      verified
    - next concrete action remains the product-specific app bridge or
      instrumentation path for Codex App / Claude Desktop
- 2026-05-30 tightened app-bridge dry-run diagnostics for target-visible app
  shells without a native endpoint:
  - implementation:
    - `AgentAppBridgeRequest.target_ready` now means the requested app/window
      context is bound, not that UIA composer or native endpoint control is
      ready
    - when UIA proves the target context is visible but no native bridge exists,
      app bridge dry-run now reports
      `app_bridge_native_connector_not_ready` with only
      `native_endpoint_not_ready` in validation errors
    - this separates the two next actions cleanly:
      target/context work vs product-specific bridge installation
  - official-doc basis:
    - Python built-in `property` documentation was checked before adjusting
      report-level derived readiness semantics
  - validation:
    - red test first:
      `test_target_visible_without_composer_reports_only_native_endpoint_missing`
      failed because the bridge dry-run incorrectly returned
      `app_bridge_target_not_ready`
    - targeted green:
      the new test plus existing target-missing and endpoint-missing bridge
      tests passed after the readiness split
    - focused regression:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix`:
      `56 tests OK`
    - R51/R52 real Codex App read-only probes:
      - `logs/runtime/codex-app-readonly-r51-project-only/report.json`
        proved the current Codex App surface can be background-captured and can
        show `openwukong` project context with `target_matched=true`, but has
        no semantic composer and no endpoint
      - `logs/runtime/codex-app-readonly-r52-bridge-diagnostics/report.json`
        now reports `app_bridge_dry_run.decision=app_bridge_native_connector_not_ready`,
        `request.target_ready=true`,
        `request.native_endpoint_ready=false`,
        `control_attempts=0`, `window_input_attempts=0`, and
        `background_screenshot_focus_stable=true`
  - current conclusion:
    - Codex App is no longer blocked at target discovery for this visible
      thread; it is specifically blocked at native bridge/instrumentation
      availability
    - next concrete action: implement/install the Codex App desktop native
      bridge or equivalent product-specific instrumentation, then rerun the
      same dry-run until `native_endpoint_ready=true` before any real send
- 2026-05-30 advanced the Cursor/Codex-style owned DevTools path without
  treating an unlogged isolated Cursor as the user's real signed-in app:
  - implementation:
    - Start Menu `.lnk` entries are now resolved through a read-only Windows
      shortcut target resolver before app launch planning; on the current
      machine
      `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Cursor\Cursor.lnk`
      resolves to `E:\cursor\cursor\cursor\Cursor.exe`
    - agent-app owned DevTools launch planning now forwards the requested
      workspace path as a VS Code/Cursor-compatible folder argument for
      Cursor-like surfaces
    - DevTools launch resolution can fall back from a pathless `Get-StartApps`
      selected candidate to a launchable `.exe` candidate discovered from the
      Start Menu shortcut
    - isolated agent-app owned profiles are now removed after the helper is
      stopped, and profile cleanup participates in `cleanup_ok`
  - official-doc basis:
    - VS Code command-line folder opening and Cursor command-line folder
      opening docs were checked before forwarding the workspace as a positional
      folder argument
    - Windows shortcut target access was implemented through `WScript.Shell`
      / shortcut `TargetPath` semantics, with the shortcut path embedded in the
      PowerShell script rather than passed as a fragile tail argument
  - validation:
    - red tests first covered missing `agent_app_workspace_path`, missing
      fleet `workspace_path` forwarding, Start Menu shortcut target extraction,
      pathless `Get-StartApps` fallback to a launchable candidate, and isolated
      profile cleanup
    - focused regression:
      `python -m unittest tests.test_app_resolution tests.test_desktop_task_runner tests.test_major_real_no_loss tests.test_session_readiness_plan tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix`:
      `129 tests OK`
    - R56 real Cursor isolated owned launch:
      `logs/runtime/major-real-no-loss-r56-cursor-owned-workspace-real-launch/major-real-no-loss-report.json`
      showed the correct Start Menu-derived executable was launched with
      `E:\ideaProjects\agent\openwukong` as the workspace, with
      `launch_attempts=1`, `stop_attempts=1`, `cleanup_ok=true`,
      `control_attempts=0`, and `window_input_attempts=0`; the transport
      matrix stayed honest with `background_read_only_cases=1`,
      `background_send_ready_cases=0`, and `status=gated_native_endpoint_missing`
    - R57 real Cursor isolated owned launch verified the new cleanup fields:
      `profile_cleanup_attempted=true`, `profile_cleanup_ok=true`, profile
      directory absent after stop, and no residual owned Cursor debug-port
      process
    - a separate no-send default user-profile Cursor probe using the same
      Start Menu-derived executable and `--remote-debugging-port=19558`
      confirmed `ready=true`, `focus_stable=true`, a Cursor 3.5.33 CDP endpoint,
      and no residual probe process; this proves a signed-in/default-profile
      attach route is viable, but it is not yet wired into the reusable harness
      as a safe product capability
    - full verification:
      `python -m unittest discover tests`: `547 tests OK`
      `python -m compileall -q src tests`: OK
      `git diff --check`: OK
  - current conclusion:
    - the previous "wrong/unlogged Cursor" behavior came from intentionally
      using an isolated `--user-data-dir`; this is safe for no-loss testing but
      cannot reuse the user's signed-in Cursor state
    - the correct system design should split Cursor into two background routes:
      isolated owned helper for clean read-only/DevTools health tests, and a
      default-profile/existing-process attach route for signed-in app-side
      validation, both still requiring zero keyboard/mouse/window input
    - next concrete action: formalize the default-profile/existing Cursor
      attach route in the harness, then add target-context/readback validation
      before any Cursor app-side send can be called complete
- 2026-05-30 formalized the signed-in/default-profile Cursor DevTools route
  and corrected the report contract so it no longer confuses that route with
  an isolated unlogged Cursor:
  - implementation:
    - `SessionReadinessPlanOptions` now has
      `agent_app_use_default_profile`; when enabled for Cursor-like app
      surfaces, the owned DevTools launch omits `--user-data-dir` and records
      `creates_isolated_profile=false`
    - `prepare_agent_app_devtools_owned_launch_fleet` now accepts
      `default_profile_agents`, records `profile_mode`,
      `uses_default_profile`, and leaves `user_data_dir=""` for default
      profile helpers
    - the major no-loss CLI now exposes
      `--allow-agent-app-devtools-default-profile-launch`
    - `agent_app_endpoint_acceptance` now uses the actual launch helper report
      when building `owned_devtools_launch_plan_template`, so the acceptance
      package shows the true command, profile mode, workspace path, and argv
      instead of a stale isolated-profile template
  - validation:
    - red tests first covered default-profile plan generation, fleet
      forwarding, CLI flag forwarding, and the acceptance-template mismatch
      where a real default-profile helper was still reported as
      `--user-data-dir` isolated
    - focused regression:
      `python -m unittest tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_app_resolution tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix`:
      `120 tests OK`
    - R59 real no-loss Cursor default-profile launch:
      `logs/runtime/major-real-no-loss-r59-cursor-default-profile-report-template/major-real-no-loss-report.json`
      showed `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `profile_mode=default-user-profile`, `uses_default_profile=true`,
      `user_data_dir=""`, and the command:
      `E:\cursor\cursor\cursor\Cursor.exe --remote-debugging-port=19557 --no-first-run --disable-crash-reporter E:/ideaProjects/agent/openwukong`
    - the R59 acceptance template now matches the actual route:
      no `--user-data-dir`, readiness URL `http://127.0.0.1:19557`, workspace
      argument `E:\ideaProjects\agent\openwukong`, and no matching residual
      Cursor debug-port process after cleanup
  - current conclusion:
    - the correct Cursor executable path is already derived from the Start
      Menu shortcut; the earlier unlogged behavior was specifically caused by
      the isolated `--user-data-dir` test mode
    - Cursor default-profile background attachment is now reusable and
      reportable as a no-focus read-only route
    - this is still not app-chat completion: the next required proof is a
      verified Cursor conversation target plus app-bridge send/readback
      acceptance; until that exists, `goal_complete` must remain false
- 2026-05-30 advanced Cursor from read-only DevTools attach to project-level
  app-bridge readiness without sending:
  - implementation:
    - `AgentAppBridgeRequest.target_ready` now accepts a bound
      `app-devtools-page-target` when the endpoint process binding matches the
      requested agent app and the DevTools target title/URL/id proves the
      requested project/task context
    - project and task matching now read DevTools page target `title`, `url`,
      `target_id`, and `id`, not only endpoint metadata or UIA tree matches
    - app-bridge dry-run remains strict: a missing task query still blocks the
      request, and a nonmatching project target still returns
      `app_bridge_target_not_ready`
  - validation:
    - red tests first covered:
      a Cursor DevTools page target titled `openwukong - Cursor` satisfying
      project-level target readiness without UIA match; a nonmatching project
      staying blocked; and a missing task context staying blocked
    - focused regression:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_agent_native_connector_probe`:
      `93 tests OK`
    - R60 real no-loss Cursor default-profile project-context run:
      `logs/runtime/major-real-no-loss-r60-cursor-devtools-project-context/major-real-no-loss-report.json`
      showed `safe_run_ok=true`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_focus_stable=true`, app bridge dry-run
      `ok=true`, `decision=app_bridge_dry_run_ready`,
      `target_ready=true`, and transport matrix selected
      `app-devtools-page-target` as a background send candidate
    - an additional real read-only Cursor DOM inventory over the same
      default-profile DevTools route showed the workbench body contained
      `openwukong`, `New Agent`, and `Loading Chat`, but
      `composerCandidateCount=0`, `safeComposerCandidateCount=0`, and no send
      button candidates; no message was sent, and no matching residual
      `--remote-debugging-port=19557` Cursor process remained
  - current conclusion:
    - Cursor can now be selected as a no-focus project-level background app
      bridge target through DevTools page target evidence
    - current Cursor chat DOM was still loading and exposed no safe composer,
      so the correct behavior is to stop before send rather than write into an
      unsafe or nonexistent input
    - next concrete action: add a first-class CDP composer-readiness probe to
      the app bridge report, then only allow real send when that probe finds a
      safe chat composer and readback markers can be verified without window
      input
- 2026-05-30 added the first-class CDP composer-readiness gate for Cursor-style
  app bridges:
  - implementation:
    - `AgentAppBridgeCdpAdapter` now runs a read-only
      `agent-app-bridge-cdp-composer-probe` before any CDP send expression
    - the probe inventories visible textbox/contenteditable/input candidates,
      rejects code-editor-like targets, records safe composer counts, and
      returns `app_bridge_composer_not_ready` before any send when no safe chat
      composer is proven
    - app real no-loss reports now attach `app_bridge_composer_probe`
      separately from `app_bridge_send_report`, so dry-run target readiness and
      actual composer readiness are no longer conflated
    - the local DevTools fixture smoke now requires the two-step CDP sequence:
      read-only composer probe first, send second, with zero window input
  - validation:
    - red tests first covered a ready composer probe before send, a blocked
      no-safe-composer route with `bridge_send_attempts=0`, and fixture smoke
      moving from one CDP request to two
    - focused regression:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix tests.test_major_real_no_loss tests.test_agent_native_connector_probe tests.test_agent_app_bridge_fixture_smoke`:
      `97 tests OK`
    - R61 real Cursor default-profile no-loss run:
      `logs/runtime/major-real-no-loss-r61-cursor-composer-readiness/major-real-no-loss-report.json`
      used the Start Menu shortcut
      `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Cursor\Cursor.lnk`,
      resolved it to `E:\cursor\cursor\cursor\Cursor.exe`, and launched the
      default-profile helper with DevTools on `127.0.0.1:19557`
    - R61 evidence:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_focus_stable=true`, launch attempts `1`, stop
      attempts `1`, cleanup OK, and no residual Cursor debug-port process
    - the real CDP page target was `openwukong - Cursor`; the read-only
      composer probe found one visible textbox candidate with class
      `aislash-editor-input`, but it lacked a safe chat semantic hint, so the
      system correctly stopped at `app_bridge_composer_not_ready` without
      setting text or submitting
  - current conclusion:
    - the correct signed-in Cursor route is now the default-profile Start Menu
      shortcut route, not the isolated unlogged profile route
    - Cursor can be targeted in the background by project context and probed
      without stealing focus
    - the remaining blocker for real Cursor chat send is a stricter selector
      or product bridge that can prove `aislash-editor-input` is the intended
      chat composer and verify readback after send; until that proof exists,
      `goal_complete` must remain false
    - next concrete action: add a Cursor-specific chat-composer contract for
      `aislash-editor-input` with readback-marker verification, then run an
      explicit opt-in real send test only after the probe reports ready
- 2026-05-30 completed the first real background Cursor app-chat send path:
  - implementation:
    - the CDP composer probe now recognizes Cursor's real Lexical composer:
      `DIV role=textbox contenteditable=true data-lexical-editor=true` with
      class `aislash-editor-input`, but only when the Cursor workbench context
      and `New Agent` chat surface are present
    - Cursor composer readiness is recorded as
      `productComposerContract=cursor-agent-chat-aislash-editor-input`
    - CDP send now uses the Lexical-compatible edit primitive:
      focus the in-page composer, range-select its contents, use
      `document.execCommand('insertText')`, dispatch composed input/change
      events, and wait for Lexical state to settle before readback
    - the send path now finds Cursor's actual submit control through the
      `codicon-arrow-up-two` icon and its `.anysphere-icon-button` ancestor,
      scoped to the proved Cursor composer region
    - submit verification is no longer assumed after click: the report requires
      `postComposerText` to no longer contain the submitted message, and then
      validates required/forbidden readback markers
    - failure paths attempt cleanup through repeated range-select/delete loops,
      and real diagnostics confirmed failed draft attempts did not persist
      after the owned helper was stopped and relaunched
  - validation:
    - red tests first covered Cursor `aislash-editor-input` readiness,
      Lexical `execCommand('insertText')`, async settle waits, cleanup loops,
      Cursor arrow-up submit discovery, `.anysphere-icon-button` ancestor
      targeting, and post-submit composer readback
    - focused regression:
      `python -m unittest tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix tests.test_major_real_no_loss tests.test_agent_native_connector_probe tests.test_agent_app_bridge_fixture_smoke`:
      `99 tests OK`
    - real R62:
      `logs/runtime/major-real-no-loss-r62-cursor-aislash-composer-contract/major-real-no-loss-report.json`
      proved the Cursor composer contract in the signed-in/default-profile
      Start Menu route with `composer_probe_decision=app_bridge_composer_ready`,
      `safe_composer_found=true`, `bridge_send_attempts=0`,
      `control_attempts=0`, and `window_input_attempts=0`
    - real R63-R74 diagnostics:
      showed direct `textContent` writes do not update Cursor's Lexical state,
      `execCommand('insertText')` does, the long composed message moves the
      submit icon below the previous y-bound, and the clickable ancestor is
      `.anysphere-icon-button`
    - real R75:
      `logs/runtime/major-real-no-loss-r75-cursor-real-send-verified-submit/major-real-no-loss-report.json`
      successfully sent a real Cursor app-chat message in the background via
      the correct Start Menu/default-profile route:
      `safe_run_ok=true`, `agent_app_goal_complete=true`,
      `app_bridge_send_verified=true`,
      `send_decision=app_bridge_send_accepted`, `control_attempts=0`,
      `window_input_attempts=0`, `launch_attempts=1`, `stop_attempts=1`,
      `cleanup_ok=true`, no residual `Cursor.exe --remote-debugging-port=19557`
      process, `sendButtonContract=cursor-arrow-up-two-submit`, and
      readback contained `OPENWUKONG_CURSOR_REAL_SEND_R75`
  - current conclusion:
    - Cursor is now genuinely verified for background project targeting,
      composer detection, text insertion, submit, and readback-marker
      acceptance without keyboard/mouse/window input
    - the global objective is still incomplete because Codex app, Claude app,
      browser, Word, WeChat, and file/task scenarios must each keep their own
      current evidence and completion gates
    - next concrete action: promote this Cursor-specific CDP path into the
      transport matrix as a verified app-send capability, then continue the
      same no-focus proof pattern for Codex/Claude app chat or browser/file
      tasks
- 2026-05-30 tightened the unified app transport matrix and refreshed Word
  real background evidence:
  - implementation:
    - `app-devtools-page-target` no longer becomes background send-ready from
      page-target context alone; it now requires either a ready
      `app_bridge_composer_probe` or a verified `app_bridge_send_report`
    - matrix evidence now records composer probe decision, product composer
      contract, app bridge send decision, send verification, and submit button
      contract when those proofs exist
    - `agent_app_real_no_loss` now rebuilds the transport matrix after the
      app bridge composer/send path, so reports distinguish:
      target page available, composer not proven, composer ready, and send
      verified
  - official-doc basis:
    - Chrome DevTools Protocol Runtime/Target documentation was checked before
      changing the CDP page-target readiness contract
  - validation:
    - red tests first showed the old matrix incorrectly marked a matching
      Cursor DevTools page target as send-ready without a composer probe
    - green focused regression:
      `python -m unittest tests.test_agent_app_transport_matrix`:
      `6 tests OK`
    - broader focused regression:
      `python -m unittest tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix tests.test_major_real_no_loss`:
      `57 tests OK`
    - real Word R76:
      `logs/runtime/word-real-r76/report.json` verified hidden Word COM
      creation of an owned temporary document with
      `decision=word_background_probe_verified`, `save_verified=true`,
      `readback_verified=true`, `visible_requested=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `office_com_attempts=1`, and marker `OPENWUKONG_WORD_REAL_R76`
    - post-run process scan found no residual `WINWORD.EXE`
  - current conclusion:
    - Cursor's real background send proof is now represented more honestly in
      the unified matrix: target context alone is not enough, composer/send
      evidence is required
    - Word owned-document background operation is currently verified on this
      machine through hidden COM without foreground input or residual process
    - next concrete actions:
      1. run the strict full verification suite for this matrix change
      2. continue the same no-focus proof pattern for browser current real
         owned-helper action and Codex/Claude app chat surfaces
- 2026-05-30 refreshed browser, WeChat, file, Word, Codex app, and Claude
  app no-focus evidence against the current desktop:
  - real primary R77:
    `logs/runtime/primary-real-no-loss-r77-browser-owned`
    - command ran the L1 primary scenario fixture with an explicit owned
      browser helper on DevTools port `9460`, isolated profile, and
      `about:blank#openwukong-primary-smoke`
    - suite result:
      `passed_cases=5/5`, `failed_cases=0`, `real_verified_cases=4`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `real_user_filesystem_scan_attempts=0`,
      `user_file_modification_attempts=0`, `owned_app_launch_attempts=1`,
      `background_screenshot_count=1`,
      `background_screenshot_focus_stable=true`
    - browser helper artifact:
      `logs/runtime/primary-real-no-loss-r77-browser-owned/owned_browser_primary_smoke/owned_browser_helpers/browser_research_collect_sources/helper.json`
      verified:
      `status=started_and_stopped`, exact target match for
      `about:blank#openwukong-primary-smoke`,
      `owned_browser_action.decision=executed`,
      `owned_browser_action.action_report.action=read_page`,
      `owned_browser_action_control_attempts=0`,
      `readiness_stop.stop_attempts=1`,
      `profile_cleanup.attempted=true`, and
      `profile_cleanup.deleted=true`
    - post-run cleanup checks:
      no `chrome.exe` / `msedge.exe` process remained with
      `--remote-debugging-port=9460` or the owned profile path, and the owned
      profile directory was absent
    - WeChat in R77:
      current personal WeChat/Weixin window was found and background-captured
      through `PrintWindow` with focus stable; write remained correctly blocked
      because UIA/MSAA exposed no deterministic semantic input and no native
      bridge URL was configured
    - Word in R77:
      hidden COM owned-document path passed again with
      `decision=word_background_probe_verified`, `save_verified=true`,
      `readback_verified=true`, `visible_requested=false`,
      `control_attempts=0`, and `window_input_attempts=0`
    - file search in R77:
      owned temp-file index search passed with no real user filesystem scan and
      no user file modification
    - Codex project task draft in R77:
      current IDE bridge at `http://127.0.0.1:8787` was unavailable, so the
      Codex primary scenario remains `real_verified=false` for task draft;
      this is a bridge availability gap, not a control-layer send attempt
  - real agent-app R78:
    `logs/runtime/agent-app-real-no-loss-r78-codex-claude-readonly`
    - ran read-only background probes for `codex app` and `claude desktop`
      with background screenshots
    - suite result:
      `passed_cases=2/2`, `failed_cases=0`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`,
      `background_screenshot_count=2`,
      `background_screenshot_success_count=2`,
      `background_screenshot_focus_stable=true`,
      `background_send_ready_cases=0`, `background_draft_ready_cases=0`
    - Codex app:
      desktop app surface and `openwukong` project were visible, background
      screenshot succeeded, but no native endpoint was exposed and no semantic
      composer was verified; status remained
      `gated_native_endpoint_missing`
    - Claude Desktop:
      app surface was visible and background screenshot succeeded, but the
      requested `openwukong` project/task was not visible and no native endpoint
      or semantic composer was exposed; status remained
      `gated_native_endpoint_missing`
  - current conclusion:
    - browser owned-helper background control is now current and verified on
      this machine with exact target creation, CDP read action, process stop,
      and profile cleanup
    - WeChat can currently be observed and background-captured, but precise
      background send remains blocked without a WeChat-native bridge or a
      stronger semantic input surface
    - Codex app and Claude Desktop can be observed/captured in the background,
      but precise app-side background task/chat submission remains blocked by
      missing native/DevTools/extension endpoints
    - next concrete action: implement or install a native/extension bridge for
      Codex/Claude app surfaces, or route Codex/Claude background execution
      through their proven CLI surfaces while keeping desktop-app status
      separately reported
- 2026-05-30 clarified the correct Cursor real-test route:
  - the correct user-profile Cursor entry is the Start Menu shortcut:
    `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Cursor\Cursor.lnk`
  - the shortcut resolves on this machine to:
    `E:\cursor\cursor\cursor\Cursor.exe`
  - the earlier unlogged Cursor behavior is classified as an isolated-profile
    test-mode artifact, not a failure of the correct Cursor route
  - R75 remains the authoritative successful Cursor app-chat evidence:
    `logs/runtime/major-real-no-loss-r75-cursor-real-send-verified-submit/major-real-no-loss-report.json`
    used the default user profile with DevTools on `127.0.0.1:19557`, sent
    `OPENWUKONG_CURSOR_REAL_SEND_R75`, verified readback, and kept
    `control_attempts=0` and `window_input_attempts=0`
  - future Cursor app-chat validation must use
    `--allow-agent-app-devtools-default-profile-launch` for signed-in tests;
    isolated-profile launches are only valid for cold-start or unauthenticated
    negative evidence
  - no duplicate real Cursor send was run in this clarification pass, because
    repeating the R75 send would write another test message into the real
    Cursor chat while adding little new evidence
- 2026-05-30 added current real no-loss evidence for Codex/Claude CLI
  background execution while keeping desktop App status separate:
  - dry-run route check:
    `logs/runtime/agent-cli-real-no-loss-r79-dry-run/report.json`
    confirmed the current machine resolves:
    - Codex CLI:
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\958d608b5e0546a5\codex.exe`
      with `codex-cli-managed-terminal`
    - Codex Desktop Shell:
      `C:\Program Files\WindowsApps\OpenAI.Codex_26.519.11010.0_x64__2p2nqsd0c76g0\app\Codex.exe`
      as a separate non-background-send desktop surface
    - Claude Code CLI:
      `C:\Users\Zhangjinqian\.local\bin\Claude.exe`
      with `claude-code-cli-managed-terminal`
    - Claude Desktop Shell:
      `C:\Program Files\WindowsApps\Claude_1.9659.2.0_x64__pzs8sxrjxfjjc\app\claude.exe`
      as a separate native-bridge-required desktop surface
  - real run:
    `logs/runtime/agent-cli-real-no-loss-r79-real/report.json`
    produced `total_cases=2`, `passed_cases=2`, `verified_cases=1`,
    `agent_command_attempts=2`, `window_input_attempts=0`,
    `control_attempts=0`, `foreground_focus_stable=true`, and clean owned
    temporary workspaces for both agents
  - Codex CLI is now current verified real background execution:
    `status=verified`, `real_verified=true`, `accepted=true`,
    command family `codex exec`, exact safety flags
    `--sandbox read-only --ask-for-approval never -C <owned-temp-workspace>
    exec --skip-git-repo-check --ephemeral --ignore-rules --json`, exit code
    `0`, and required marker `OPENWUKONG_AGENT_CLI_NO_LOSS: PASS`
    was observed
  - Claude CLI was attempted through the safe non-interactive route but is not
    current verified because this machine returned
    `Not logged in · Please run /login`; it is classified as
    `cli_auth_required`, with `real_verified=false`, not as a control-layer or
    routing failure
  - desktop App status remains unchanged and separate:
    Codex app and Claude Desktop can be observed/background-captured, but
    precise app-side background task/chat submission still requires a native,
    DevTools, or extension endpoint; CLI success must not be used as proof of
    desktop App chat capability
