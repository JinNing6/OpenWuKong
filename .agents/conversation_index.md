# Conversation Index

Last updated: 2026-06-29

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
- 2026-05-30 refreshed current Codex/Claude desktop App read-only evidence:
  - report:
    `logs/runtime/agent-app-real-no-loss-r80-codex-claude-readonly/report.json`
  - suite result:
    `total_cases=2`, `passed_cases=2`, `goal_complete=false`,
    `native_ready_cases=0`, `background_send_ready_cases=0`,
    `background_draft_ready_cases=0`, `bridge_send_attempts=0`,
    `agent_command_attempts=0`, `window_input_attempts=0`,
    `background_screenshot_success_count=2/2`, and
    `background_screenshot_focus_stable=true`
  - Codex app:
    current desktop shell can be resolved and background-captured; UIA evidence
    sees the `openwukong` project as visible, but the requested
    `major-real-no-loss` task is missing, semantic composer count is `0`, and
    native endpoint count is `0`, so status stays
    `gated_native_endpoint_missing`
  - Claude Desktop:
    current desktop shell can be resolved and background-captured, but
    `openwukong` and `major-real-no-loss` are not visible in the current app
    surface, semantic composer count is `0`, and native endpoint count is `0`,
    so status stays `gated_native_endpoint_missing`
  - current conclusion:
    Codex/Claude desktop App surfaces have strong no-focus observation and
    screenshot evidence, but no precise background App-side task/chat control
    until a native/extension/DevTools endpoint is available or installed
- 2026-05-30 tightened Cursor app resolution and Codex/Claude default-profile
  DevTools probes:
  - implementation:
    - `WindowsAppResolver` now ranks pathless `Get-StartApps` entries below
      launchable path candidates, so Cursor resolves to the Start Menu
      shortcut target instead of selecting `Anysphere.Cursor` with an empty
      path when both are present
    - current local Cursor resolution now selects:
      `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Cursor\Cursor.lnk`
      -> `E:\cursor\cursor\cursor\Cursor.exe`
    - agent app DevTools owned launch now allows default-profile launches for
      non-workspace desktop app surfaces such as Codex and Claude Desktop, not
      only Cursor/VS Code-like apps
    - added CLI knobs:
      `--agent-app-devtools-endpoint-wait-timeout-sec` and
      `--agent-app-devtools-request-timeout-sec`
  - official-doc basis:
    - Microsoft `Get-StartApps` documentation confirms the cmdlet returns app
      names and AppUserModelIDs, not executable paths; executable shortcut
      resolution must therefore remain separate from StartApps identity
      evidence
  - validation:
    - red regression first proved pathless `start-apps` incorrectly beat
      launchable Start Menu Cursor evidence
    - targeted green regression:
      `python -m unittest tests.test_app_resolution.AppResolutionModuleTests.test_launchable_start_menu_candidate_beats_pathless_start_apps_entry`
      passed
    - current resolver check now reports `source=start-menu` and
      `path=E:\cursor\cursor\cursor\Cursor.exe` for `cursor`
    - Codex/Claude R83:
      `logs/runtime/major-real-no-loss-r83-codex-claude-default-profile-devtools-propagated-timeout/major-real-no-loss-report.json`
      launched both desktop apps with default profiles and local ports
      `19555/19556`, kept `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success_count=3/3`, and cleaned owned launches
      after the probe
    - R83 also proved the Codex/Claude Desktop HTTP DevTools endpoints are not
      usable on this machine even with request timeout increased to `2.0s`;
      they still time out on `/json/version`, so desktop app chat send remains
      gated by missing native/extension/product endpoint rather than by our
      timeout wiring
    - post-run process scan found no residual Codex/Claude DevTools helpers
      except the scan process itself
  - current conclusion:
    - Cursor's correct signed-in route is the Start Menu shortcut/default user
      profile route; the earlier unlogged Cursor evidence was isolated-profile
      negative evidence
    - Codex/Claude Desktop default-profile probe infrastructure is now
      correct and audited, but desktop-app precise background send is still
      not achieved without a real connector endpoint
- 2026-06-01 compared the installed OpenAI bundled `computer-use` plugin with
  OpenWukong's current control architecture:
  - local plugin evidence:
    - installed at:
      `C:\Users\Zhangjinqian\.codex\plugins\cache\openai-bundled\computer-use\26.527.31326`
    - manifest describes it as Windows desktop control from Codex with
      interactive/read/write capability
    - implementation entrypoint is `scripts/computer-use-client.mjs`, which
      talks to `codex-computer-use.exe` through a native pipe and exposes the
      `sky` Window2 API
    - declared runtime primitives include `list_apps`, `list_windows`,
      `launch_app`, `get_window_state`, `click`, `press_key`, `type_text`,
      `scroll`, `set_value`, `drag`, `perform_secondary_action`, and
      `activate_window`
    - plugin guidance states Windows automation uses SendInput, UI
      Automation, and Windows.Graphics.Capture; occluded-window screenshots
      are supported, but input methods activate the target window
  - comparison conclusion:
    - Computer Use is a strong universal Windows UI fallback and app/window
      discovery layer, especially for occluded screenshots and basic UIA text
      snapshots
    - it is not a substitute for OpenWukong's connector-first path because it
      is still mainly window/input/accessibility driven, while OpenWukong's
      strongest verified paths use product-native transports such as CDP,
      Office COM, IDE bridge/DevTools, managed CLI, and owned filesystem
      contracts
    - best integration direction is to add Computer Use as a guarded
      foreground/semiforeground fallback transport below native connectors and
      UIA semantic providers, with the same no-loss counters, target
      resolution, readback verification, and confirmation gates already used
      by OpenWukong
- 2026-06-01 integrated Computer Use into the agent app transport matrix as a
  guarded fallback contract:
  - implementation:
    - added `openwukong.control.computer_use_transport` with a static
      read-only probe for the installed bundled Computer Use client; this
      checks the client entrypoint and native pipe configuration without
      starting helper processes, sending input, or touching desktop focus
    - `agent_native_connector_probe` now attaches `computer_use_probe` evidence
      to app-surface reports
    - `agent_app_transport_matrix` now emits a `computer-use-window2`
      candidate whenever Computer Use evidence exists
    - a ready Computer Use candidate is classified only as
      `background-read-only` with operation scope `inspect-snapshot-only`;
      it never sets `can_send_without_focus` or `can_draft_without_focus`
      because Computer Use input actions activate the target window
    - native pipe missing or unverified runtime state is explicitly surfaced as
      `native_pipe_unavailable` / blocked rather than silently falling back to
      keyboard or mouse input
  - official-doc basis:
    - OpenAI Computer Use documentation describes the tool as a UI
      screenshot/action loop and recommends isolated environments,
      allowlists/guardrails, and human oversight for risky actions; this
      supports keeping Computer Use below native connectors and behind
      confirmation/focus gates
  - validation:
    - red tests first proved the matrix lacked `computer-use-window2` and that
      the report summary did not count Computer Use read-only cases
    - green targeted tests:
      `python -m unittest tests.test_computer_use_transport tests.test_agent_app_transport_matrix`
      passed with `11` tests
    - native connector regression:
      `python -m unittest tests.test_agent_native_connector_probe` passed with
      `20` tests
    - agent app no-loss regression:
      `python -m unittest tests.test_agent_app_real_no_loss` passed with `17`
      tests
    - current local static probe reports the bundled plugin is installed at
      `C:\Users\Zhangjinqian\.codex\plugins\cache\openai-bundled\computer-use\26.527.31326`
      but `SKY_CUA_NATIVE_PIPE_DIRECTORY` is not configured in the Python
      process, so the fallback is currently `native_pipe_unavailable`
    - R84 read-only real app probe:
      `logs/runtime/agent-app-real-no-loss-r84-computer-use-fallback-readonly/report.json`
      kept `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `background_screenshot_focus_stable=true`,
      and `goal_complete=false`
    - R84 Codex app case is still `gated_native_endpoint_missing`; R84 Claude
      Desktop case is `unavailable` in the current visible surface; both cases
      carry a blocked `computer-use-window2` candidate with
      `native_pipe_unavailable` and risk flags
      `input_actions_activate_window` / `not_background_write_transport`
  - current conclusion:
    - the unified architecture is stronger because it now accounts for the
      installed Computer Use plugin as a first-class fallback surface
    - the overall product goal is still not complete: Computer Use is not
      currently connected in this session, and even when connected it should
      prove read-only background observation first before any foreground-gated
      input action can be considered
    - next concrete actions:
      1. add a real Computer Use runtime probe path that records
         `sky.list_apps` / `get_window_state` readiness when the native pipe is
         actually available
      2. keep Codex/Claude desktop app chat on native/DevTools/extension bridge
         work; do not treat Computer Use input as background app-chat proof
      3. add the same fallback accounting to WeChat's app matrix after its
         native bridge and UIA semantic gaps are reported
- 2026-06-01 upgraded Computer Use fallback from static install evidence to a
  runtime-readiness contract:
  - implementation:
    - `build_computer_use_runtime_probe` now wraps the static plugin/native
      pipe check and can consume an injected read-only runtime probe result
    - runtime readiness requires `list_apps_ready` plus a read-only state
      signal such as `window_state_ready`, `background_snapshot_ready`, or
      `accessibility_tree_available`
    - any `control_attempts`, `window_input_attempts`, or
      `foreground_activation_attempts` causes
      `computer_use_runtime_not_read_only`, so Computer Use cannot be promoted
      to background observation if it activated or typed into a window
    - `agent_native_connector_probe` now uses the runtime contract by default
      while still accepting an injected probe runner for tests or a future
      live bridge implementation
  - validation:
    - new red/green tests cover a ready read-only runtime probe and a blocked
      foreground-activation runtime probe
    - focused regression:
      `python -m unittest tests.test_computer_use_transport
      tests.test_agent_app_transport_matrix tests.test_agent_native_connector_probe
      tests.test_agent_app_real_no_loss` passed with `50` tests
    - current local runtime probe still reports:
      `mode=computer-use-runtime-probe`, `plugin_installed=true`,
      `native_pipe_configured=false`, `native_pipe_ready=false`,
      `decision=native_pipe_unavailable`, `control_attempts=0`,
      `window_input_attempts=0`, and `foreground_activation_attempts=0`
    - R85 read-only real app probe:
      `logs/runtime/agent-app-real-no-loss-r85-computer-use-runtime-readonly/report.json`
      kept `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `background_screenshot_focus_stable=true`,
      and `goal_complete=false`
    - R85 app cases carry `computer-use-runtime-probe` evidence:
      Codex app is still `gated_native_endpoint_missing`, Claude Desktop is
      `unavailable`, and both Computer Use candidates remain blocked by
      `native_pipe_unavailable`
  - current conclusion:
    - the runtime contract is ready for a future live Computer Use bridge
      without weakening no-loss semantics
    - the final product goal remains incomplete: no current evidence proves
      Codex/Claude desktop app chat or WeChat background send through a
      deterministic, no-focus transport
- 2026-06-01 added Computer Use fallback accounting to the WeChat/IM primary
  no-loss path:
  - implementation:
    - `wechat_locator` now accepts a `computer_use_probe` and exports
      `computer_use_probe`, `computer_use_read_only_ready`,
      `computer_use_write_control_ready=false`,
      `computer_use_attempts`, `computer_use_window_input_attempts`, and
      `computer_use_foreground_activation_attempts`
    - `primary_real_no_loss` now runs or accepts an injected Computer Use
      runtime probe for the WeChat case and propagates the evidence into the
      case details and top-level summary counters
    - a ready Computer Use fallback is treated only as
      `computer-use-read-only`; it never promotes WeChat to background send or
      draft-ready because Computer Use input actions activate the target window
  - validation:
    - red tests first proved `build_wechat_locator_report` and
      `run_primary_real_no_loss` had no Computer Use fallback accounting API
    - green focused tests:
      `python -m unittest tests.test_wechat_locator.WeChatLocatorTests.test_attaches_computer_use_fallback_without_promoting_write_control tests.test_primary_real_no_loss.PrimaryRealNoLossTests.test_runner_converts_primary_scenarios_to_real_no_loss_probes`
      passed
    - wider regression:
      `python -m unittest tests.test_computer_use_transport
      tests.test_wechat_locator tests.test_primary_real_no_loss
      tests.test_major_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss`
      passed with `97` tests
    - real no-loss read-only R86:
      `logs/runtime/primary-real-no-loss-r86-wechat-computer-use-readonly`
      produced `passed_cases=5/5`, `real_verified_cases=3`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `background_screenshot_success_count=1`,
      and `background_screenshot_focus_stable=true`
    - R86 WeChat evidence:
      Weixin window `hwnd=396116` was background-captured through PrintWindow
      without focus change; UIA remained `structure_only`, semantic composer
      counts stayed `0`, native bridge URLs were absent, and
      `background_send_verified=false`
    - R86 Computer Use evidence:
      bundled plugin was detected at
      `C:\Users\Zhangjinqian\.codex\plugins\cache\openai-bundled\computer-use\26.527.31326`,
      but the Python runtime still had `native_pipe_configured=false`,
      `native_pipe_ready=false`, `decision=native_pipe_unavailable`,
      `computer_use_attempts=0`, and `window_input_attempts=0`
  - current conclusion:
    - WeChat/IM is now aligned with the unified fallback accounting model:
      native bridge first, UIA semantic only if proven, Computer Use as
      read-only fallback, foreground takeover as an explicit separate gate
    - the final goal is still incomplete because WeChat background send and
      Codex/Claude desktop-app chat still lack deterministic no-focus write
      transports
    - next concrete actions:
      1. build a generic non-agent app transport matrix so WeChat, Office,
         Browser, File Search, and agent apps expose the same selected route /
         fallback / blocker schema
      2. add a live Computer Use bridge runner that records `sky.list_apps` and
         `get_window_state` readiness when the native pipe is available, still
         without input actions
      3. continue Codex/Claude desktop-app bridge work separately from the
         already verified CLI routes
- 2026-06-01 added a unified primary-scenario transport matrix:
  - implementation:
    - added `openwukong.evaluation.primary_transport_matrix`
    - `primary_real_no_loss` now embeds `transport_matrix` in full reports and
      `transport_matrix_summary` in summaries
    - primary scenarios now share the same selected transport / fallback /
      blocker schema across WeChat, Browser, File Search, Word, and Codex
    - the matrix separates `can_execute_without_focus` from
      `can_write_without_focus`, so read-only evidence cannot be promoted into
      background send/task-submit capability
  - validation:
    - red tests first proved there was no `primary_transport_matrix` module and
      no `transport_matrix` field in primary reports
    - green focused tests:
      `python -m unittest tests.test_primary_transport_matrix tests.test_primary_real_no_loss.PrimaryRealNoLossTests.test_runner_converts_primary_scenarios_to_real_no_loss_probes`
      passed with `3` tests
    - wider regression:
      `python -m unittest tests.test_primary_transport_matrix
      tests.test_primary_real_no_loss tests.test_major_real_no_loss
      tests.test_computer_use_transport tests.test_wechat_locator
      tests.test_agent_app_transport_matrix tests.test_agent_native_connector_probe
      tests.test_agent_app_real_no_loss` passed with `99` tests
    - R87 real no-loss run without owned browser launch:
      `logs/runtime/primary-real-no-loss-r87-transport-matrix-readonly`
      kept `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, and background screenshot focus stable; the
      matrix correctly marked Browser and Codex as blocked in that run
    - R88 real no-loss run with owned browser helper:
      `logs/runtime/primary-real-no-loss-r88-transport-matrix-owned-browser`
      produced `passed_cases=5/5`, `real_verified_cases=4`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `owned_app_launch_attempts=1`, and
      `background_screenshot_focus_stable=true`
    - R88 matrix summary:
      `goal_complete=false`, `background_execute_ready_cases=4/5`,
      `background_write_ready_cases=1`, `background_read_only_cases=1`,
      `blocked_cases=1`, `write_blocked_cases=2`
    - R88 selected routes:
      Browser=`browser-devtools-owned`, File Search=`owned-filesystem-index`,
      Word=`office-word-com`, WeChat=`wechat-read-only-locator`, and
      Codex=`none` because the IDE bridge at `127.0.0.1:8787` was unavailable
    - post-run process scan found no owned browser helper residue beyond the
      scan process itself
  - current conclusion:
    - the architecture is on the right path and now has report-level evidence
      for current goal distance
    - the final goal is not yet complete:
      WeChat still lacks deterministic no-focus background send, Codex desktop
      task submission still lacks a connected bridge, and Computer Use native
      pipe is still unavailable in this Python runtime
    - next concrete actions:
      1. connect or implement the real Codex/Cursor/Claude desktop bridge path
         for project/task submission with readback
      2. implement a deterministic WeChat native bridge or verified semantic
         UIA send path for File Transfer Assistant only
      3. add a live Computer Use bridge runner when the native pipe is
         available, but keep it below native connectors and behind focus/input
         gates
- 2026-06-01 added a goal-level objective readiness matrix for the full
  desktop-control objective:
  - implementation:
    - added `openwukong.evaluation.objective_readiness_matrix`
    - `major_real_no_loss` now embeds `objective_readiness_matrix` at the
      top level
    - the matrix combines major requirements with primary transport evidence,
      agent app transport matrices, and agent CLI evidence
    - each requirement now reports `selected_transport`,
      `capability_level`, `can_execute_without_focus`,
      `can_write_without_focus`, `satisfied`, and `blocking_reason`
    - this makes the current objective auditable across:
      WeChat, Word, Browser, File Search, Codex CLI, Claude CLI, Codex App,
      Claude Desktop, and Cursor
  - validation:
    - red tests first proved the module and major report field were missing
    - green focused tests:
      `python -m unittest tests.test_objective_readiness_matrix
      tests.test_major_real_no_loss.MajorRealNoLossTests.test_major_report_exposes_agent_app_transport_matrix_summary`
      passed with `2` tests
    - wider regression:
      `python -m unittest tests.test_objective_readiness_matrix
      tests.test_primary_transport_matrix tests.test_primary_real_no_loss
      tests.test_major_real_no_loss tests.test_computer_use_transport
      tests.test_wechat_locator tests.test_agent_app_transport_matrix
      tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss`
      passed with `100` tests
    - R89 real no-loss run:
      `logs/runtime/major-real-no-loss-r89-objective-readiness`
      kept `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `background_screenshot_success_count=5/5`,
      and `background_screenshot_focus_stable=true`
    - R90 real no-loss run with safe CLI execution:
      `logs/runtime/major-real-no-loss-r90-objective-readiness-cli`
      kept `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, `background_screenshot_success_count=5/5`,
      `background_screenshot_focus_stable=true`, and no owned helper residue
      after the run
    - R90 objective readiness summary:
      `requirement_count=10`, `safe_run_ok=true`, `goal_complete=false`,
      `satisfied_count=5`, `background_execute_ready_count=6`,
      `background_write_ready_count=2`, `gated_count=3`,
      `auth_required_count=1`, `unavailable_count=1`
    - R90 satisfied requirements:
      WeChat background observation, Word background document, Browser
      background research, File background search, and Codex CLI background
      task
    - R90 remaining unmet requirements:
      `wechat_background_send`, `claude_cli_background_task`,
      `codex_app_background_chat`, `claude_desktop_background_chat`, and
      `cursor_background_chat`
  - current conclusion:
    - the system is now able to state the exact distance to the objective from
      current real evidence, instead of relying on manual interpretation
    - the best next engineering move is no longer another broad scan; it is to
      implement/attach deterministic write transports for the five remaining
      unmet requirements:
      1. WeChat native bridge or verified File Transfer Assistant semantic send
      2. Claude CLI login/auth handling or auth-state prerequisite reporting
      3. Codex desktop app bridge
      4. Claude Desktop bridge
      5. Cursor default-profile/DevTools app bridge readback path
- 2026-06-01 tightened Cursor DevTools/app-bridge readiness diagnostics:
  - root cause found:
    - R91/R92 showed Cursor DevTools `/json/version` could be ready while
      `/json/list` had no page target
    - `_wait_for_agent_app_devtools_endpoint_health` returned immediately on
      empty targets instead of polling until a page target appeared or timeout
    - current machine also has an existing default-profile Cursor process
      without `--remote-debugging-port`, so default-profile launch can expose
      only browser-level DevTools without a workbench page target
  - implementation:
    - endpoint health now keeps polling when targets are temporarily empty and
      preserves the last diagnostic payload on timeout
    - added bridge-level auth-gate detection for Cursor/Codex/Claude login
      text from both send readback and composer-probe readback
    - `agent_app_real_no_loss` now reports `auth_required` when the bridge
      returns `app_bridge_auth_required`
    - `major_real_no_loss` now preserves `auth_required` before native-ready
      gated classification
  - validation:
    - red tests first reproduced:
      1. empty Cursor target list returning too early
      2. Cursor login page being classified as `submit_not_verified`
      3. composer-probe login evidence being lost when send timed out
      4. app requirement demoting `auth_required` to gated
    - focused tests passed after fixes
    - wider regression passed:
      `python -m unittest tests.test_agent_app_bridge
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_objective_readiness_matrix tests.test_primary_transport_matrix
      tests.test_primary_real_no_loss tests.test_major_real_no_loss
      tests.test_computer_use_transport tests.test_wechat_locator
      tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss`
      with `147` tests
    - R93 default-profile Cursor send:
      `logs/runtime/major-real-no-loss-r93-cursor-default-profile-send-after-target-wait`
      kept `control_attempts=0`, `window_input_attempts=0`, focus stable, and
      helper cleanup ok; after the wait fix it made `97` endpoint attempts but
      still saw `target_count=0`, confirming the default-profile single-instance
      limitation rather than an early-return bug
    - R94/R95/R96/R97 isolated-profile Cursor runs:
      isolated profile produced a real DevTools page target and composer probe
      (`target_count=1`) without window input
    - R97:
      `logs/runtime/major-real-no-loss-r97-cursor-isolated-profile-probe-auth-fixed`
      kept `control_attempts=0`, `window_input_attempts=0`, focus stable,
      helper cleanup ok, no port-19557 helper residue, and classified
      Cursor as `auth_required (auth_required)`
    - R97 objective summary:
      `satisfied_count=4`, `gated_count=1`, `auth_required_count=1`,
      `unavailable_count=4`, `failed_count=0`
  - current conclusion:
    - Cursor background CDP/page-target route is technically reachable in an
      owned isolated profile, but app chat execution needs a logged-in profile
      or a native/extension bridge bound to the real logged-in Cursor session
    - default-profile Cursor cannot be considered stable while a normal Cursor
      process is already running without remote debugging
    - next concrete actions:
      1. implement a real Cursor/Codex/Claude extension or native connector
         that exposes project/task submission from the logged-in app session
      2. keep DevTools page-target control as a diagnostic and fallback, not the
         primary production write path
      3. continue WeChat background send work via native bridge or verified
         semantic UIA send with post-send readback
- 2026-06-01 added a read-only IDE extension bridge readiness probe:
  - implementation:
    - added `openwukong.evaluation.ide_extension_readiness`
    - the probe checks the local VS Code/Cursor bridge scaffold, installed
      extension roots, `/v1/ide/capabilities`, and the selected chat adapter
      without launching apps, sending messages, or using window input
    - reports `status`, `blocking_reason`, `extension_installed`,
      `bridge_ready`, `selected_chat_adapter`,
      `can_execute_without_focus`, and `can_write_without_focus`
    - added a CLI:
      `python -m openwukong.evaluation.ide_extension_readiness --json`
  - validation:
    - red test first proved the module was missing
    - green tests cover:
      1. installed extension plus available chat adapter => `ready`
      2. scaffold present but no installed extension => `extension_not_installed`
      3. installed extension but no endpoint => `bridge_unavailable`
      4. bridge reachable but adapter unavailable => `chat_adapter_unavailable`
    - focused regression:
      `python -m unittest tests.test_ide_extension_readiness
      tests.test_ide_extension_scaffold tests.test_ide_extension_connector
      tests.test_major_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_app_real_no_loss` passed with `102` tests
    - updated global skill `debug-connector-helper-readiness` with:
      empty DevTools target waiting, browser-level vs page-target readiness,
      and login-gate-first classification
    - skill validation passed:
      `quick_validate.py .../debug-connector-helper-readiness`
  - real no-loss/read-only probe:
    - command:
      `python -m openwukong.evaluation.ide_extension_readiness --json
      --agent-id cursor --project-name openwukong --workspace-path
      E:\ideaProjects\agent\openwukong --request-timeout 2`
    - result:
      `status=extension_not_installed`,
      `blocking_reason=install_extension_in_logged_in_ide_profile`,
      `scaffold_present=true`, `package_json_present=true`,
      `extension_installed=false`, `bridge_ready=false`,
      `can_execute_without_focus=false`, `can_write_without_focus=false`
    - local evidence:
      Cursor extension directory currently contains Claude Code and
      Cursor Pyright extensions, but no OpenWukong IDE bridge extension
      install; `127.0.0.1:8787` is not serving `/v1/ide/capabilities`
  - current conclusion:
    - the Python connector and extension scaffold exist, but the real logged-in
      Cursor session is not yet bridge-enabled
    - next concrete action is to package/install or dev-load
      `extensions/openwukong-vscode` into the logged-in Cursor profile, then
      run `IDE CAPABILITIES` and configure a real chat adapter command id
      before any app-side message send
- 2026-06-01 bridge-enabled the real logged-in Cursor profile without window
  input:
  - implementation:
    - changed the OpenWukong VS Code-compatible extension manifest so the local
      bridge auto-starts on activation while keeping the default bind host at
      `127.0.0.1`
    - documented the auto-start/local-bind behavior in
      `extensions/openwukong-vscode/README.md`
    - fixed `ide_extension_readiness` package parsing to tolerate UTF-8 BOM
      `package.json` files produced by Windows/PowerShell tooling
  - real no-loss validation:
    - packaged the extension with `@vscode/vsce` using `npm_config_ignore_scripts`
      to avoid the current `vsce-sign` postinstall failure on this machine
    - installed `logs/runtime/openwukong-vscode-bridge-0.1.0.vsix` into the real
      Cursor profile with Cursor CLI `--install-extension ... --force`
    - Cursor CLI now lists:
      `openwukong-local.openwukong-vscode-bridge@0.1.0`
    - `python -m openwukong.evaluation.ide_extension_readiness --json ...`
      now reports `extension_installed=true`, `bridge_ready=true`,
      `can_execute_without_focus=true`, `control_attempts=0`,
      `window_input_attempts=0`, and `bridge_send_attempts=0`
    - readiness status is now `chat_adapter_unavailable`, not
      `extension_not_installed`
    - capability capture saved at
      `logs/runtime/cursor-ide-bridge-r98/capabilities.json`
      observed `3459` commands from the real Cursor bridge and inferred Cursor
      candidates including `composer.startComposerPrompt`,
      `composer.startComposerPrompt2`, `composer.sendToAgent`,
      `composer.newAgentChat`, `composer.openComposer`, `composer.createNew`,
      `aichat.newchataction`, and `workbench.action.chat.open`
    - Codex extension commands are also visible through the same bridge,
      including `chatgpt.newCodexPanel`
  - current conclusion:
    - the logged-in Cursor session is now background-readable through the
      OpenWukong extension bridge
    - the system still must not claim Cursor background chat submission is
      complete until a sacrificial/isolated command-contract probe validates
      the exact adapter command and argument shape without destructive edits or
      foreground takeover
    - next concrete actions:
      1. build a non-destructive adapter contract validator that records focus
         stability and workspace diffs while probing candidate commands
      2. validate Cursor adapter command shape before enabling `/v1/ide/chat`
         for real project task submission
      3. repeat the same bridge/capability/contract path for Codex and Claude
         extension surfaces instead of falling back to UI vision
- 2026-06-01 added and ran the non-destructive Cursor command-contract probe:
  - implementation:
    - `ide_bridge_contract_probe` now records Windows foreground focus before
      and after each command variant with `GetForegroundWindow` /
      `GetWindowTextW`
    - probe results now expose `foreground_changed`, `focus_stable`, and
      validation-level `foregroundChanged`
    - recommended chat adapters now require:
      command accepted, no workspace diff, and no foreground takeover
    - regression coverage now proves a command that steals focus is not
      recommended even if it otherwise executes
  - real no-loss validation:
    - launched an isolated Cursor profile/workspace at
      `logs/runtime/cursor-ide-contract-r99` with bridge port `8792`
    - captured `3203` commands from the isolated Cursor bridge
    - probed first Cursor chat candidates:
      `composer.startComposerPrompt`, `composer.startComposerPrompt2`, and
      `composer.sendToAgent`
    - result:
      `control_attempts=9`, `workspace_changed=false`,
      `foreground_changed=false`, `focus_stable=true`,
      but all variants returned `command_not_allowlisted`
    - validated settings therefore kept Cursor `commandId=""` and
      `available=false`
    - stopped the isolated Cursor process through the manifest; follow-up
      process scan found no `cursor-ide-contract-r99` residue except the scan
      process itself
  - validation:
    - focused regression:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_readiness tests.test_ide_extension_scaffold
      tests.test_ide_bridge_capture` passed with `18` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - the bridge can read Cursor in the background and can run a safe isolated
      contract probe without focus takeover
    - Cursor background chat submission is still not complete because the
      extension intentionally blocks unallowlisted command execution
    - the next concrete action is to add a controlled allowlist/config path for
      sacrificial command validation, then validate the exact Cursor chat
      command and argument shape before enabling real logged-in project task
      submission
- 2026-06-01 added controlled Cursor contract validation and proved an
  isolated background chat endpoint path:
  - implementation:
    - added `build_probe_allowlist_settings` to generate temporary VS
      Code/Cursor `settings.json` for sacrificial profiles only
    - added CLI flags:
      `--probe-settings-output` and `--write-probe-settings-only`
    - documented the isolated contract-probe workflow in
      `extensions/openwukong-vscode/README.md`
    - extended `ide_bridge_contract_probe` with `target_foreground` and
      `background_execution_observed`
    - recommended adapters now require:
      accepted `object_message`, no workspace diff, no foreground hwnd change,
      and target window not already foreground
    - regression coverage now catches both:
      foreground-stealing commands and false positives where the target IDE was
      already the foreground window
  - real no-loss validation:
    - R100 wrote isolated profile settings and allowed the first three Cursor
      candidates:
      `composer.startComposerPrompt`, `composer.startComposerPrompt2`, and
      `composer.sendToAgent`
    - R100 proved those commands are callable through `/v1/ide/command`, but
      also exposed a verification gap because Cursor was already foreground
      during the probe
    - R101 repeated the validation after minimizing the isolated Cursor window
      and restoring the foreground to Edge
    - R101 contract probe:
      `logs/runtime/cursor-ide-contract-r101/contract-probe.json`
      showed `control_attempts=9`, `workspace_changed=false`,
      `foreground_changed=false`, `target_foreground=false`,
      `background_execution_observed=true`, and recommended all three
      candidate commands
    - R101 selected validated mapping:
      Cursor `commandId=composer.startComposerPrompt` with
      `acceptedVariant=object_message`
    - R101 `/v1/ide/chat` endpoint probe:
      `logs/runtime/cursor-ide-contract-r101/chat-endpoint-probe.json`
      returned `ok=true`, `command_id=composer.startComposerPrompt`,
      `foreground_changed=false`, `target_foreground=false`, and the isolated
      workspace still contained only `README.md`
    - stopped the isolated Cursor process through the manifest; follow-up
      process scan found no `cursor-ide-contract-r101` residue except the scan
      process itself
  - validation:
    - focused regression:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_readiness tests.test_ide_extension_scaffold
      tests.test_ide_bridge_capture tests.test_ide_extension_connector
      tests.test_session_readiness_plan` passed with `64` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - Cursor now has a verified isolated background extension-bridge path for
      `/v1/ide/chat`, including no foreground takeover and no workspace edits
    - this is not yet a full real logged-in Cursor project-task completion
      proof, because the validation used an isolated profile and did not verify
      model response/readback or task result acceptance in the logged-in user
      profile
    - next concrete actions:
      1. install/write only the validated Cursor mapping into the real logged-in
         Cursor profile under explicit no-loss gating, then run a harmless
         project task submission/readback check
      2. repeat the same extension-bridge validation path for Codex App and
         Claude Desktop surfaces
      3. keep WeChat background send as a separate native/semantic bridge track
- 2026-06-01 validated the real logged-in Cursor profile bridge and tightened
  project-target readiness reporting:
  - real no-loss validation:
    - R102 applied the R101 validated Cursor mapping to the real logged-in
      Cursor profile settings with a backup under
      `logs/runtime/cursor-real-profile-r102/settings-backups`
    - live readiness now reports:
      `status=ready`, `extension_installed=true`, `bridge_ready=true`,
      selected adapter `cursor`, and command
      `composer.startComposerPrompt`
    - direct real `/v1/ide/chat` probe:
      `logs/runtime/cursor-real-profile-r102/chat-endpoint-probe.json`
      returned `ok=true`, `command_id=composer.startComposerPrompt`,
      `foreground_focus_stable=true`, `target_foreground_before=false`,
      `target_foreground_after=false`, `workspace_changed=false`, and
      `git_status_unchanged=true`
    - the same R102 probe also showed the remaining verification gap:
      `workspaceFolders=[]`, `workspace_bound_to_requested_path=false`, and
      `post_send_readback_available=false`
  - implementation:
    - explicit IDE bridge probes now preserve
      `requested_workspace_path`, `requested_workspace_name`, and
      `workspace_target_source=explicit_probe_request` in endpoint metadata
    - app bridge target matching now accepts those explicit IDE bridge
      workspace targets for new background tasks while keeping the readback
      marker gate
    - `agent_app_real_no_loss` now preserves the precise app bridge decision
      such as `app_bridge_message_submitted_acceptance_pending` instead of
      collapsing it back to `gated_native_endpoint_missing`
  - real standardized runner:
    - R105:
      `logs/runtime/cursor-real-profile-r105-standard-agent-app/agent-app-report.json`
      reached the standard app bridge path with
      `app_bridge_dry_run_ready`, `bridge_send_attempts=1`,
      `control_attempts=0`, and `window_input_attempts=0`
    - R105 status is intentionally
      `app_bridge_message_submitted_acceptance_pending` because the current
      IDE bridge response only reports `ide=Cursor`, `workspaceFolders=0`,
      and `action=chat_send`; it does not expose the Cursor model reply or the
      required acceptance marker
  - validation:
    - red tests first reproduced:
      1. explicit IDE bridge workspace targets being dropped from endpoint
         metadata
      2. app bridge dry-run rejecting a ready explicit IDE bridge because
         Cursor self-reported `workspaceFolders=[]`
      3. pending readback decisions being hidden behind a generic gated status
    - focused regression passed:
      `python -m unittest tests.test_agent_native_connector_probe
      tests.test_agent_app_bridge tests.test_agent_app_real_no_loss
      tests.test_ide_extension_connector tests.test_ide_bridge_contract_probe
      tests.test_ide_bridge_settings_apply tests.test_objective_readiness_matrix`
      with `93` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - Cursor has now proven real logged-in profile background dispatch through
      the extension bridge without foreground takeover, keyboard, mouse, or
      clipboard input
    - Cursor is still not fully complete for the final goal because the bridge
      cannot yet read back the Cursor model response or verify acceptance
      markers, and the IDE API still reports no bound workspace folders
    - next concrete actions:
      1. add a real Cursor transcript/readback path or native Cursor-side
         result hook so acceptance markers can be verified
      2. repeat the same extension/native bridge path for Codex App and Claude
         Desktop
      3. continue the WeChat background send track through native bridge or
         verified semantic UIA send with readback
- 2026-06-01 added a read-only Cursor transcript/readback verifier and wired it
  into the app-surface acceptance path:
  - implementation:
    - added `openwukong.evaluation.cursor_transcript_readback`
    - the scanner binds a requested workspace to Cursor
      `%APPDATA%\Cursor\User\workspaceStorage\*/workspace.json`
    - it opens Cursor `state.vscdb` files through SQLite `file:` URI
      `mode=ro`, reads selected composer IDs, and scans `cursorDiskKV`
      `composerData:*`, `bubbleId:*`, `messageRequestContext:*`,
      `checkpointId:*`, and matching `agentKv:blob:*` rows
    - reports include `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, selected composer IDs, scanned keys,
      required/forbidden marker results, and redacted marker snippets
    - `agent_app_real_no_loss` can now use the scanner to upgrade Cursor
      `app_bridge_message_submitted_acceptance_pending` to
      `app_bridge_send_accepted` when transcript markers prove acceptance
    - CLI support was added with
      `--enable-cursor-transcript-readback` and
      `--cursor-user-data-root`
  - validation:
    - red tests first reproduced:
      1. missing `cursor_transcript_readback` module
      2. missing `cursor_transcript_readback_runner` integration point
    - focused green tests:
      `python -m unittest tests.test_cursor_transcript_readback
      tests.test_agent_app_real_no_loss.AgentAppRealNoLossTests.test_cursor_pending_app_bridge_is_accepted_by_transcript_readback`
      passed with `3` tests
    - wider regression:
      `python -m unittest tests.test_cursor_transcript_readback
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe
      tests.test_objective_readiness_matrix` passed with `71` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - real no-loss/read-only evidence:
    - artifacts saved under
      `logs/runtime/cursor-transcript-readback-r106`
    - R106 R105-marker scan:
      `r105-pending.json` found the real openwukong Cursor workspace and
      selected composer `a9a6e98f-5a1e-475d-8051-8c4d7bc7b8fa`, kept all
      control/window/bridge counters at zero, and correctly reported
      `cursor_transcript_readback_pending` because
      `OPENWUKONG_CURSOR_STANDARD_RUN_R105_NO_EDIT` is absent from local
      transcript storage
    - R106 historical R75-marker scan:
      `r75-accepted.json` found `OPENWUKONG_CURSOR_REAL_SEND_R75` through the
      same read-only path and reported `cursor_transcript_readback_accepted`
      with all control/window/bridge counters at zero
  - current conclusion:
    - Cursor now has a real local transcript evidence path for acceptance
      verification, not just a bridge-send acknowledgement
    - the latest R105 send remains pending because its marker never reached
      Cursor transcript storage, so the next Cursor task is to adjust the
      command/message submission shape or add a Cursor-side result hook until
      new background sends produce verifiable transcript markers
    - next concrete actions:
      1. run a fresh harmless Cursor background send with transcript readback
         enabled and use R106 diagnostics to distinguish submit-shape failure
         from model-response latency
      2. repeat the same extension/native bridge + transcript/result-hook
         pattern for Codex App and Claude Desktop
      3. keep WeChat background send on native/semantic bridge track with
         post-send readback rather than visual confirmation
- 2026-06-01 completed the next Cursor real-profile background send probes and
  narrowed the remaining gap to Cursor-specific task-submission semantics:
  - real no-loss evidence:
    - R107 used the real Cursor profile, `/v1/ide/chat`,
      `composer.startComposerPrompt`, and transcript readback:
      `logs/runtime/cursor-real-profile-r107-transcript-readback/agent-app-report.json`
      reported `app_bridge_message_submitted_acceptance_pending`,
      `bridge_send_attempts=1`, `control_attempts=0`,
      `window_input_attempts=0`, and
      `background_screenshot_focus_stable=true`
    - R108 direct command string probe:
      `logs/runtime/cursor-real-profile-r108-direct-command-variants/string-message.json`
      returned `ok=true` but the marker was still absent from transcript
      storage
    - R109 updated the real Cursor bridge settings with a backup and tested
      `composer.sendToAgent`; the runner again stayed
      `app_bridge_message_submitted_acceptance_pending` with no keyboard,
      mouse, clipboard, or foreground-control attempts
    - R110 command matrix covered four direct bridge variants:
      `composer.startComposerPrompt2` string/object and
      `composer.sendToAgent` string/object; all four returned `ok=true` with
      `result=null`, but all four transcript scans stayed
      `cursor_transcript_readback_pending`
  - validation:
    - focused regression for transcript readback and app integration passed
      with `3` tests
    - wider regression passed:
      `python -m unittest tests.test_cursor_transcript_readback
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe
      tests.test_objective_readiness_matrix` with `71` tests
    - settings replacement regression passed:
      `python -m unittest tests.test_ide_bridge_settings_apply` with `4`
      tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - the architecture has proven background discovery, routing, bridge
      command execution, background screenshots, and local transcript readback
      without relying on vision as the primary control layer
    - the final goal is not yet fully achieved because the tested Cursor VS
      Code command IDs acknowledge execution but do not actually persist a new
      chat/task message in Cursor transcript storage
    - the next concrete action is to stop guessing command IDs and implement
      or discover a Cursor-side native/result hook that can write/read the real
      composer/task state, then reuse that hook pattern for Codex App and
      Claude Desktop
- 2026-06-01 advanced Cursor from transcript-only readback to live composer
  state introspection:
  - implementation:
    - added Cursor composer state discovery on top of the read-only transcript
      scanner; it reports `scanned_composer_ids`, key-family counts, marker
      locations, and hook candidates across `composerData:*`,
      `bubbleId:*`, `messageRequestContext:*`, `checkpointId:*`, and matching
      `agentKv:blob:*`
    - `cursor_transcript_readback` now accepts extra composer IDs through
      `extra_composer_ids` / `--composer-id`, so live bridge getter results can
      be included without losing the workspace-selected composer evidence
    - `ide_bridge_contract_probe` now ignores its own `logs/runtime` artifacts
      when checking workspace mutation and supports `--variant` to avoid
      unnecessary repeated snapshots in real probes
    - the OpenWukong Cursor extension source now exposes a planned read-only
      `/v1/ide/cursor/composer-state` endpoint that summarizes Cursor composer
      handles without returning the huge internal manager object
  - real no-loss evidence:
    - R111 saved read-only state-discovery artifacts under
      `logs/runtime/cursor-composer-state-discovery-r111`
    - R111 historical R75 marker discovery confirmed real accepted messages
      live in `bubbleId:<composer>:<bubble>` plus matching `agentKv:blob:*`
    - R112 getter probe:
      `logs/runtime/cursor-readonly-command-introspection-r112/readonly-command-probe-noargs.json`
      ran `composer.getOrderedSelectedComposerIds`,
      `composer.getBackgroundComposerInfo`, `composer.getComposerHandleById`,
      and `composer.getCurrentWorkspaceRepoUrl` through the real bridge with
      `control_attempts=4`, no workspace changes, no foreground change, and
      WeChat remaining the foreground window
    - R112 discovered the live selected composer is
      `5db3f4d0-8745-4fbc-ab00-4c97296d65f7`, while the workspace DB selected
      composer is still `a9a6e98f-5a1e-475d-8051-8c4d7bc7b8fa`
    - rescanning R110 with both composer IDs still reported
      `cursor_transcript_readback_pending`, proving the failed background send
      did not merely land in the live composer missed by the old scanner
    - `composer.getComposerHandleById` with the live composer ID returned a
      real Cursor handle in the background; the summarized state shows an empty
      draft (`text=""`, `conversationMap={}`, `status="none"`), consistent
      with the prior screenshot and transcript evidence
    - packaged and installed
      `logs/runtime/openwukong-vscode-bridge-0.1.0-r113.vsix`; static install
      verification found the new composer-state endpoint under
      `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0\src\extension.js`
    - the running Cursor extension host has not been reloaded, so the live
      `/v1/ide/cursor/composer-state` endpoint currently returns `404`; it is
      intentionally not forced because reloading Cursor would interrupt the
      user's foreground work
    - R114 rerun:
      `logs/runtime/cursor-live-composer-state-r114/live-composer-state-rerun.json`
      confirmed the existing bridge can read the live selected Cursor composer
      state in the background with `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`, and
      `readonly_command_attempts=2`; the live composer is agent/edit mode
      (`status="none"`, `unified_mode="agent"`, `force_mode="edit"`,
      `is_agentic=true`) with an empty draft
  - validation:
    - TDD red tests first reproduced missing discovery, missing extra composer
      ID scanning, runtime-log false mutation, missing CLI variant filtering,
      and missing extension endpoint source
    - focused regression passed:
      `python -m unittest tests.test_cursor_transcript_readback
      tests.test_ide_bridge_contract_probe...runtime_log...
      tests.test_ide_bridge_contract_probe...variant...
      tests.test_ide_extension_scaffold` with `10` tests
    - wider regression passed:
      `python -m unittest tests.test_cursor_transcript_readback
      tests.test_ide_bridge_contract_probe tests.test_ide_extension_scaffold
      tests.test_ide_extension_connector tests.test_agent_app_real_no_loss
      tests.test_agent_app_bridge tests.test_agent_native_connector_probe
      tests.test_objective_readiness_matrix` with `101` tests
    - live composer summary regression passed:
      `python -m unittest tests.test_cursor_live_composer_state` with `4`
      tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - Cursor now has a concrete background read path into live composer state,
      not only local SQLite transcript readback
    - Cursor task submission is still not complete: current evidence proves the
      tested command IDs do not mutate the live composer draft or transcript
    - next concrete actions:
      1. when user work can tolerate a Cursor reload, verify the new
         `/v1/ide/cursor/composer-state` endpoint live
      2. use the live handle shape to find a safe Cursor-native draft/message
         mutation method instead of executing generic commands blindly
      3. apply the same live-state summary endpoint pattern to Codex App and
         Claude Desktop bridges
- 2026-06-01 advanced Cursor command-contract discovery toward the real
  query-draft entry point:
  - implementation:
    - added the `query_object` probe argument shape so command-contract probes
      can validate commands that expect `{ query: message }`
    - changed Cursor review candidate priority so
      `workbench.action.chat.open` is discovered before the older
      `composer.startComposerPrompt*` and `composer.sendToAgent` command ids
    - changed active capability mapping so newly reviewed candidates are tried
      before stale configured candidates, without automatically enabling an
      unvalidated `commandId`
    - updated the VS Code/Cursor bridge extension so `/v1/ide/chat` maps
      `workbench.action.chat.open` to `vscode.commands.executeCommand(
      commandId, { query: message })` while preserving the existing
      `{ message, target, metadata }` envelope for other adapter commands
  - validation:
    - RED first:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_scaffold tests.test_ide_bridge_capture`
      initially failed because `query_object`, extension argument mapping, and
      Cursor candidate priority were missing
    - focused regression passed:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_scaffold tests.test_ide_bridge_capture`
      with `20` tests, then `tests.test_ide_bridge_capture` with `6` tests
      after adding the stale-config ordering regression
    - wider regression passed:
      `python -m unittest tests.test_cursor_live_composer_state
      tests.test_cursor_transcript_readback tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_scaffold tests.test_ide_bridge_capture
      tests.test_ide_extension_connector tests.test_agent_app_real_no_loss
      tests.test_agent_app_bridge tests.test_agent_native_connector_probe
      tests.test_objective_readiness_matrix` with `112` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
    - `node --check extensions\openwukong-vscode\src\extension.js` passed
    - read-only live capability capture:
      `logs/runtime/cursor-chat-open-candidate-r116/capabilities.json`
      reported `ok=true`, `control_attempts=0`, `command_count=3466`,
      `cursor_review_candidates[0]=workbench.action.chat.open`, and
      `active_mapping.cursor.commandCandidates[0]=workbench.action.chat.open`
    - packaged but did not install or reload Cursor:
      `logs/runtime/openwukong-vscode-bridge-0.1.0-r116.vsix`; static VSIX
      verification confirmed the packaged extension contains
      `buildChatCommandArguments`, `workbench.action.chat.open`, and
      `query: message`
  - current conclusion:
    - the next Cursor real-send attempt will no longer keep prioritizing the
      already-disproven `composer.sendToAgent` / `composer.startComposerPrompt`
      paths
    - full Cursor task submission is still not proven because this turn stayed
      read-only against the live profile and did not reload/install the new
      extension or execute `workbench.action.chat.open`; that command is known
      from bundle inspection to call a focus path, so the next real probe must
      run with foreground-change gating or in an isolated profile
    - next concrete actions:
      1. dev-load or install R116 bridge into an isolated Cursor profile first,
         then validate `workbench.action.chat.open` with `query_object` and
         foreground/workspace mutation gates
      2. if isolated validation is background-safe, apply the mapping to the
         logged-in profile only when a Cursor reload is acceptable
      3. continue Codex App, Claude Desktop, and WeChat background bridge work
         after Cursor has a proven write/readback contract
- 2026-06-01 ran the R117 isolated Cursor query-draft validation and found a
  critical safety gap:
  - real isolated setup:
    - wrote temporary bridge settings under
      `logs/runtime/cursor-ide-contract-r117/user-data/User/settings.json`
      allowlisting `workbench.action.chat.open`,
      `composer.getOrderedSelectedComposerIds`, and
      `composer.getComposerHandleById`
    - launched isolated Cursor with
      `--user-data-dir=logs/runtime/cursor-ide-contract-r117/user-data`,
      `--extensions-dir=logs/runtime/cursor-ide-contract-r117/extensions`,
      `--extensionDevelopmentPath=extensions/openwukong-vscode`, workspace
      `logs/runtime/cursor-ide-contract-r117/workspace`, and bridge port
      `8793`
    - launch manifest:
      `logs/runtime/cursor-ide-contract-r117/manifest.json`
  - real evidence:
    - read-only capability capture:
      `logs/runtime/cursor-ide-contract-r117/capabilities.json`
      reported `ok=true`, `control_attempts=0`, `command_count=3203`,
      `active_mapping.cursor.commandId=workbench.action.chat.open`, and
      `active_mapping.cursor.commandCandidates[0]=workbench.action.chat.open`
    - command probe:
      `logs/runtime/cursor-ide-contract-r117/contract-probe-query-object.json`
      returned `status=callable`, `accepted_variant=query_object`,
      `recommended_adapter=true`, `workspace_changed=false`,
      `foreground_changed=false`, `target_foreground=false`, with foreground
      recorded as `Weixin` before and after the immediate command check
    - live composer state:
      `logs/runtime/cursor-ide-contract-r117/live-composer-state-after-query.json`
      proved the command did write a draft:
      composer `fd610dd0-eeb9-427e-84f6-b379cbb6519b` had
      `text=OPENWUKONG_CURSOR_R117_QUERY_DRAFT_NO_EDIT` and matching
      `rich_text`; readback used only read-only bridge commands and reported
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `readonly_command_attempts=3`
  - user-visible negative evidence:
    - while R117 was running, a Windows system picker appeared:
      `选择应用以打开 "session-start"` with Cursor highlighted
    - this proves the immediate foreground snapshot was too narrow: the command
      can write a Cursor draft but can also trigger a delayed/system-level
      external-protocol dialog, so it is not acceptable as a fully background
      safe real-profile route yet
  - cleanup:
    - stopped the isolated Cursor process through
      `logs/runtime/cursor-ide-contract-r117/manifest.json`
    - stop report:
      `logs/runtime/cursor-ide-contract-r117/stop.json`
      reported `status=stopped`, `stop_attempts=1`, `control_attempts=0`
    - follow-up process scan found no `cursor-ide-contract-r117` Cursor
      processes, only the scan command itself
  - implementation hardening:
    - added delayed post-action focus observation to
      `ide_bridge_contract_probe` via
      `post_action_observation_delay_sec` /
      `--post-action-observation-delay-sec`
    - added `system_dialog_detected` to variant results, command results,
      report summaries, and validated mapping rejection evidence
    - commands are no longer recommended when delayed focus reveals a
      `session-start`, `选择应用以打开`, `choose an app`,
      `how do you want to open`, or `open with` style system dialog
  - validation:
    - RED first:
      `tests.test_ide_bridge_contract_probe.IDEBridgeContractProbeTests.test_probe_marks_delayed_system_dialog_as_not_recommended`
      failed because `post_action_observation_delay_sec` did not exist
    - focused regression passed for that test after implementation
    - wider regression passed:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_ide_bridge_capture tests.test_ide_extension_scaffold
      tests.test_cursor_live_composer_state tests.test_cursor_transcript_readback
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_objective_readiness_matrix`
      with `100` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - `workbench.action.chat.open` is now proven to be a real Cursor draft
      write primitive in an isolated profile
    - it is not proven background-safe because the external `session-start`
      picker appeared; do not apply it to the logged-in real profile as a
      production route yet
    - next concrete actions:
      1. stop treating generic VS Code command execution as sufficient for
         Cursor send; find or implement a Cursor-native draft/write hook that
         does not emit the `session-start` external protocol
      2. use the delayed-dialog guard on any future real IDE command probes
      3. keep the R117 positive draft-write evidence, but route final Cursor
         real send through native state mutation or a dedicated extension-side
         bridge rather than `workbench.action.chat.open` directly
- 2026-06-01 immediately hardened the Cursor capability-capture route after the
  user-visible `session-start` picker:
  - root-cause evidence:
    - Cursor bundle inspection shows `workbench.action.chat.open` calls
      `createComposer({partialState:{text,richText}, openInNewTab:true})`,
      then `fireShouldForceText`, then `showAndFocus`
    - this explains why R117 could both write the draft and still trigger a
      delayed Windows external-protocol picker
  - implementation:
    - `ide_bridge_capture` now classifies
      `workbench.action.chat.open` as a Cursor risky candidate instead of an
      active/review command candidate
    - read-only capability reports now expose
      `cursor_risky_candidates` and `risky_candidate_reasons`
    - stale adapter mappings that already expose the risky command are
      neutralized: the command is removed from active `commandCandidates` and
      tracked under `riskyCommandCandidates`
    - the delayed system-dialog guard already matches the real Chinese
      `选择应用以打开` title as well as `session-start`/English markers
  - validation:
    - RED first:
      `tests.test_ide_bridge_capture.IDEBridgeCaptureTests.test_capture_classifies_cursor_chat_open_as_risky_not_active`
      failed because `cursor_risky_candidates` did not exist and
      `workbench.action.chat.open` was still first in active candidates
    - focused regression passed for the risky-candidate downgrade and delayed
      system-dialog guard
    - wider regression passed:
      `python -m unittest tests.test_ide_bridge_capture
      tests.test_ide_bridge_contract_probe tests.test_ide_extension_scaffold
      tests.test_cursor_live_composer_state tests.test_cursor_transcript_readback
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_objective_readiness_matrix`
      with `100` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - the popup does not invalidate the architecture; it invalidates this
      specific Cursor command as a production background sender
    - future Cursor sends must use a dedicated native/extension-side composer
      mutation hook or another command proven by delayed-dialog gating
- 2026-06-01 advanced the Cursor path from command guessing to internal hook
  planning:
  - implementation:
    - added `openwukong.evaluation.cursor_bundle_composer_hooks`, a read-only
      static scanner for Cursor's `workbench.desktop.main.js`
    - the scanner reports `workbench.action.chat.open` as a
      `risky_focus_command` and separates it from internal hook candidates
    - the scanner extracts candidate internal surfaces:
      `composerService.createComposer.partialState`,
      `composerDataService.updateComposerData`, and
      `composerDataService.updateComposerDataSetStore`
    - added `/v1/ide/cursor/draft-hook` to the VS Code/Cursor bridge
      extension
    - the new endpoint is dry-run by default and only calls
      `handle.setData({ text, richText })` when both `allow_write=true` and
      `safety_profile=isolated_cursor_draft_probe` are supplied
    - added `IDEExtensionBridgeClient.cursor_draft_hook` and
      `openwukong.evaluation.cursor_draft_hook_probe` so the draft hook can be
      dry-run or isolated-write probed without keyboard, mouse, clipboard, or
      foreground control
  - real read-only evidence:
    - static scan artifact:
      `logs/runtime/cursor-bundle-composer-hooks-r118/hook-discovery.json`
    - result:
      `decision=cursor_native_hook_candidates_found`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`
    - bundle counts:
      `chat_open_command_count=1`,
      `create_composer_partial_state_count=20`,
      `update_composer_data_count=111`,
      `update_composer_data_set_store_count=244`,
      `fire_should_force_text_count=42`,
      `show_and_focus_count=26`, `submit_chat_count=87`
  - validation:
    - RED first:
      `tests.test_cursor_bundle_composer_hooks` failed because the discovery
      module did not exist
    - RED first:
      `tests.test_ide_extension_scaffold...command_endpoints` failed because
      `/v1/ide/cursor/draft-hook` and `handleCursorDraftHook` did not exist
    - RED first:
      `tests.test_cursor_draft_hook_probe` failed because the Python probe
      module did not exist
    - focused tests passed after implementation:
      `tests.test_cursor_bundle_composer_hooks`,
      `tests.test_ide_extension_scaffold`, and
      `tests.test_cursor_draft_hook_probe`
    - JS syntax passed:
      `node --check extensions/openwukong-vscode/src/extension.js`
    - wider regression passed:
      `python -m unittest tests.test_cursor_bundle_composer_hooks
      tests.test_cursor_draft_hook_probe tests.test_ide_extension_scaffold
      tests.test_cursor_live_composer_state tests.test_cursor_transcript_readback
      tests.test_ide_bridge_capture tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_connector tests.test_agent_app_real_no_loss
      tests.test_agent_app_bridge tests.test_agent_native_connector_probe
      tests.test_objective_readiness_matrix` with `119` tests
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - Cursor now has a concrete draft-only bridge endpoint and a guarded probe
      path, but it has not yet been installed/reloaded into a live or isolated
      Cursor extension host
    - next concrete action is to package/dev-load this updated extension into
      an isolated Cursor profile, run dry-run first, then run one isolated
      `allow_write=true` draft probe with delayed foreground/system-dialog
      gates and live composer readback
- 2026-06-01 added the Cursor draft-hook validation harness and packaged the
  updated bridge:
  - implementation:
    - added `openwukong.evaluation.cursor_draft_hook_validation`
    - the validation harness always runs a dry-run draft-hook probe first
    - isolated writes require `allow_write=true` and
      `safety_profile=isolated_cursor_draft_probe`
    - after an isolated write, the harness checks:
      foreground stability, delayed system-dialog detection, live composer
      state readback, and required marker presence in `text` or `rich_text`
    - system dialogs such as `选择应用以打开 "session-start"` now fail the
      validation even if readback contains the marker
  - packaging:
    - created
      `logs/runtime/openwukong-vscode-bridge-0.1.0-r119.vsix`
    - static VSIX verification confirmed the packaged extension contains
      `/v1/ide/cursor/draft-hook`, `handle.setData({`, and
      `cursor_draft_hook_write_requires_isolated_profile`
  - validation:
    - RED first:
      `tests.test_cursor_draft_hook_validation` failed because the validation
      module did not exist
    - green focused test:
      `python -m unittest tests.test_cursor_draft_hook_validation` passed
      with `4` tests
    - JS syntax passed:
      `node --check extensions/openwukong-vscode/src/extension.js`
    - wider regression passed:
      `python -m unittest tests.test_cursor_draft_hook_validation
      tests.test_cursor_draft_hook_probe tests.test_cursor_bundle_composer_hooks
      tests.test_cursor_live_composer_state tests.test_cursor_transcript_readback
      tests.test_ide_bridge_capture tests.test_ide_bridge_contract_probe
      tests.test_ide_extension_scaffold tests.test_ide_extension_connector
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_objective_readiness_matrix`
      with `123` tests
  - current conclusion:
    - the next real Cursor step is now executable and properly gated:
      install/dev-load the R119 VSIX into an isolated Cursor profile, run
      validation dry-run, then run exactly one isolated write validation with
      delayed focus/system-dialog gates and live composer readback
    - this still should not be applied to the logged-in real Cursor profile
      until the isolated validation proves stable and no-focus
- 2026-06-01 triaged the user-visible Windows picker screenshot:
  - observation:
    - Windows displayed `选择应用以打开 "session-start"` with Cursor highlighted
      during the Cursor real probe
    - this confirms the R117 negative evidence: `workbench.action.chat.open`
      is a real draft-write primitive, but it can escape into the Windows
      shell/open-with flow and is not a production-safe background sender
  - validation:
    - added a regression assertion that the exact Chinese Unicode title
      `选择应用以打开` is classified as a system dialog
    - focused regression passed:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_cursor_draft_hook_validation tests.test_ide_bridge_capture`
      with `24` tests
  - current conclusion:
    - users should close the picker rather than selecting an app/default
    - continue with the R119 `/v1/ide/cursor/draft-hook` route in an isolated
      Cursor profile; do not use `workbench.action.chat.open` for the real
      logged-in profile
- 2026-06-01 corrected the Cursor background-testing policy after user
  feedback that launching isolated Cursor still steals focus:
  - real evidence:
    - R126/R128 isolated Cursor runs used no keyboard, mouse, clipboard, or
      bridge send attempts, and no `session-start` dialog appeared
    - however the test still starts a visible Cursor GUI process; the user
      correctly pointed out that this launch path itself can抢占焦点 and
      therefore must not be classified as a true background route
    - R129 verified the new safety default:
      `logs/runtime/cursor-isolated-draft-hook-r129-block-visible-gui/report.json`
      returned `decision=cursor_visible_gui_launch_blocked`,
      `launch_attempts=0`, `draft_write_attempts=0`,
      `window_input_attempts=0`, and `visible_gui_launch_allowed=false`
  - implementation:
    - `cursor_isolated_draft_hook_runner` now blocks visible GUI launch by
      default
    - a real isolated Cursor GUI launch now requires explicit
      `--allow-visible-gui-launch`
    - the report exposes `visible_gui_launch_allowed` so downstream runners
      can distinguish attach-only/background-safe probes from foreground-risk
      validation
    - the extension-side Cursor draft hook was hardened to infer
      `composerId` from pre/post `loadedComposers` ids when
      `composer.createNew` does not return an id
  - validation:
    - RED first:
      `tests.test_cursor_isolated_draft_hook_runner` failed because
      `allow_visible_gui_launch` did not exist and visible launch was not
      blocked by default
    - focused regression passed:
      `python -m unittest tests.test_cursor_isolated_draft_hook_runner` with
      `4` tests
    - Cursor bridge focused regression passed:
      `python -m unittest tests.test_cursor_isolated_draft_hook_runner
      tests.test_cursor_draft_hook_validation tests.test_cursor_live_composer_state
      tests.test_cursor_draft_hook_probe tests.test_ide_extension_scaffold` with
      `20` tests
    - wider no-loss regression passed:
      `python -m unittest tests.test_cursor_isolated_draft_hook_runner
      tests.test_session_readiness_plan tests.test_cursor_draft_hook_validation
      tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state
      tests.test_ide_extension_scaffold tests.test_ide_bridge_capture
      tests.test_ide_bridge_contract_probe tests.test_ide_extension_connector
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_objective_readiness_matrix
      tests.test_primary_real_no_loss tests.test_major_real_no_loss` with
      `198` tests
    - `node --check extensions/openwukong-vscode/src/extension.js` passed
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - true background Cursor control must attach to an already-running bridge,
      a packaged extension in the user's running Cursor, or a non-visible
      native/helper endpoint
    - starting a visible GUI app is now explicitly a foreground-risk action,
      not a background validation path
    - next concrete action:
      build an attach-only Cursor bridge validation path that never launches
      Cursor, then test draft/readback only when a bridge is already available
- 2026-06-01 implemented the attach-only Cursor bridge validation path after
  confirming that visible GUI launch is itself a focus-stealing risk:
  - implementation:
    - added `openwukong.evaluation.cursor_attach_bridge_validation`
    - the runner never launches Cursor, never stops Cursor, and only probes an
      already-running bridge URL
    - write mode is blocked by default with
      `decision=cursor_attach_bridge_write_blocked`; the current path is
      dry-run/readiness only until a no-focus draft/readback route is active
    - `ide_extension_readiness` now treats Cursor as ready for background
      write only when `/v1/ide/cursor/draft-hook` is available, preventing a
      stale generic IDE bridge from being reported as production-ready
  - real attach-only evidence:
    - `logs/runtime/cursor-attach-bridge-r131/report.json` attached to the
      existing bridge on `127.0.0.1:8787` and returned
      `decision=cursor_attach_bridge_draft_hook_unavailable`,
      `launch_attempts=0`, `control_attempts=0`,
      `window_input_attempts=0`, `foreground_changed=false`, and
      `system_dialog_detected=false`
    - the installed Cursor extension files under
      `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0`
      were synced from the repo without restarting Cursor; backup saved at
      `logs/runtime/cursor-installed-openwukong-backup-20260601-181444`
    - `logs/runtime/cursor-attach-bridge-r132-after-disk-sync/report.json`
      still returned `cursor_attach_bridge_draft_hook_unavailable`, proving
      the running extension host is stale in memory; no reload was forced
      because reload would steal focus from the user's current work
  - validation:
    - focused regression passed:
      `python -m unittest tests.test_cursor_attach_bridge_validation` with
      `4` tests
    - readiness regression passed:
      `python -m unittest tests.test_ide_extension_readiness` with `6` tests
    - wider no-loss regression passed:
      `python -m unittest tests.test_cursor_attach_bridge_validation
      tests.test_ide_extension_readiness
      tests.test_cursor_isolated_draft_hook_runner
      tests.test_session_readiness_plan tests.test_cursor_draft_hook_validation
      tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state
      tests.test_ide_extension_scaffold tests.test_ide_bridge_capture
      tests.test_ide_bridge_contract_probe tests.test_ide_extension_connector
      tests.test_agent_app_real_no_loss tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_objective_readiness_matrix
      tests.test_primary_real_no_loss tests.test_major_real_no_loss` with
      `208` tests
    - `node --check extensions\openwukong-vscode\src\extension.js` passed
    - `git diff --check` passed; only existing LF-to-CRLF warnings were shown
  - current conclusion:
    - the architecture direction remains correct, but the standard is stricter:
      "real background" means no visible GUI startup, no forced app reload, no
      foreground switch, no keyboard/mouse/clipboard, and no system dialog
    - Cursor logged-in profile is not yet background-write ready in the active
      process because its bridge is still the old in-memory extension host
    - next concrete actions:
      1. wait for a natural Cursor extension-host reload or user-approved
         foreground maintenance window, then re-run attach-only R133 against
         the already-running bridge
      2. continue background-safe surfaces that do not need GUI focus:
         browser CDP, hidden Word COM, Codex CLI, Claude CLI/native endpoint,
         and WeChat only through semantic/native bridge or explicit foreground
         permission
      3. keep app launch/open-window requests as foreground-gated actions
         unless a non-visible/native launch transport exists
- 2026-06-01 tightened the no-focus acceptance standard after the user
  clarified that the core failure is focus stealing itself, not only the
  `session-start` picker:
  - policy clarification:
    - a route is not production background-safe if it starts a visible GUI,
      forces an app reload, switches foreground focus, uses keyboard/mouse or
      clipboard primitives, or raises a system dialog
    - the `session-start` picker is treated as one concrete failure signal,
      but visible GUI launch and foreground takeover are independently enough
      to fail a background validation
  - verified current safe evidence:
    - R140 browser helper:
      `logs/runtime/primary-real-r140-20260601-184502/owned_browser_primary_smoke/owned_browser_helpers/browser_research_collect_sources/helper.json`
      used an owned headless Chrome profile over CDP; `Runtime.evaluate`
      confirmed the exact expected `data:` URL and marker
      `OPENWUKONG_BROWSER_BACKGROUND_R140`; the helper was stopped and the
      profile cleanup reported `deleted=true`
    - R140 Word:
      `logs/runtime/primary-real-r140-20260601-184502/real_no_loss/word_document_create_background.json`
      verified hidden Word COM write/readback with `visible_requested=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `office_com_attempts=1`, and foreground HWND stable on Codex before and
      after the operation
    - process rescan for the R140 browser helper showed no lingering Chrome
      helper process for the owned profile or debug port; only the scan
      PowerShell command matched its own query
  - regression validation:
    - passed:
      `python -m unittest tests.test_office_word_runner
      tests.test_primary_real_no_loss tests.test_primary_transport_matrix
      tests.test_agent_surface_report tests.test_agent_cli_real_no_loss
      tests.test_browser_devtools_health tests.test_browser_devtools_action
      tests.test_primary_scenario_smoke tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix
      tests.test_cursor_attach_bridge_validation
      tests.test_ide_extension_readiness` with `97` tests
    - passed:
      `node --check extensions/openwukong-vscode/src/extension.js`
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - current conclusion:
    - browser and Word have real no-focus background evidence for the owned
      safe probes
    - Cursor remains attach-only until the already-running bridge exposes the
      draft hook without reload or visible launch
    - app launch/open-window tasks remain foreground-gated unless a native or
      connector background transport exists
- 2026-06-02 continued the real no-focus evidence pass without launching
  visible GUI apps or sending external messages:
  - R141 primary scenario no-focus screenshot pass:
    - command:
      `python -m openwukong.evaluation.primary_real_no_loss
      tests/fixtures/evaluation/l1_primary_user_scenarios.json
      --output-root logs/runtime/primary-real-r141-20260602-nofocus-screens
      --summary-json --allow-owned-browser-helper-launch
      --owned-browser-debug-port 19479
      --background-screenshot-dir
      logs/runtime/primary-real-r141-20260602-nofocus-screens/screenshots`
    - result:
      `5/5` passed, `control_attempts=0`,
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `owned_app_launch_attempts=1`, and
      `background_screenshot_focus_stable=true`
    - WeChat evidence:
      `logs/runtime/primary-real-r141-20260602-nofocus-screens/real_no_loss/wechat_chat_draft_reply.json`
      found one personal WeChat window, captured one `PrintWindow`
      screenshot to
      `logs/runtime/primary-real-r141-20260602-nofocus-screens/screenshots/wechat_chat_draft_reply/01-Weixin.png`,
      reported `foreground_changed=false`, and kept all send/window-input
      counters at zero
    - Browser evidence:
      the owned headless Chrome helper used CDP against the expected page,
      stopped the helper, deleted the owned profile, and a follow-up process
      scan found no lingering process for port `19479` or the owned profile
    - Word evidence:
      hidden Word COM remained verified with `visible_requested=false`,
      `office_com_attempts=1`, `foreground_change_classification=stable`,
      and `foreground_no_steal_verified=true`
    - Codex project app case remained unavailable through the IDE bridge in
      this primary scenario and was not misreported as writable
  - R142 agent app-surface read-only pass:
    - probed `codex app`, `claude desktop`, and `cursor app` with no send,
      no draft write, no command execution, and
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`
    - Codex Desktop produced one no-focus `PrintWindow` screenshot and
      read-only diagnostics, but no native endpoint was exposed; therefore
      app-side background send/draft remained blocked
    - Claude Desktop resolved as a running desktop process in the separate
      surface report, but no matching visible app window was available to the
      app UIA probe, so desktop app-side control remains not verified
    - `cursor app` is not a registered exact app alias; the correct app alias
      is `cursor`
  - R143 Cursor app alias correction:
    - probing `cursor` resolved the correct Start Menu shortcut at
      `E:\cursor\cursor\cursor\Cursor.exe`
    - no Cursor window was running, and the probe correctly refused to launch
      it because visible GUI launch is foreground-risk
  - R144 Codex/Claude CLI no-focus pass:
    - command:
      `python -m openwukong.evaluation.agent_cli_real_no_loss
      --agent codex --agent claude
      --output-root logs/runtime/agent-cli-real-r144-20260602-nofocus
      --output logs/runtime/agent-cli-real-r144-20260602-nofocus/report.json
      --json --allow-cli-execution --timeout-sec 45`
    - result:
      `2/2` passed at the safety-report level,
      `verified_cases=1`, `agent_command_attempts=2`,
      `window_input_attempts=0`,
      `foreground_focus_stable=true`, and
      `foreground_no_steal_verified=true`
    - Codex CLI was truly verified:
      selected `codex-cli-managed-terminal`, returned required marker
      `OPENWUKONG_AGENT_CLI_NO_LOSS: PASS`, and kept the owned workspace clean
    - Claude CLI selected `claude-code-cli-managed-terminal` correctly but
      still returned `Not logged in - Please run /login`; this remains an auth
      blocker, not a control-layer or focus-stealing failure
  - regression validation:
    - passed:
      `python -m unittest tests.test_primary_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe
      tests.test_agent_cli_real_no_loss tests.test_primary_transport_matrix
      tests.test_agent_app_transport_matrix
      tests.test_cursor_attach_bridge_validation
      tests.test_ide_extension_readiness` with `78` tests
  - current conclusion:
    - verified no-focus real capabilities now include:
      WeChat read-only locator plus background HWND screenshot, Browser owned
      headless CDP, Word hidden COM, Codex CLI task probe, and Codex Desktop
      read-only background screenshot
    - still not complete:
      WeChat background send needs a native bridge or verified semantic UIA
      sender; Cursor needs an already-running updated bridge or natural reload;
      Claude CLI needs login; Claude Desktop needs visible/no-focus target
      evidence plus a native connector before app-side send can be attempted
- 2026-06-02 tightened WeChat background-send readiness so no-focus visual
  evidence is mandatory before any UIA or native-bridge send can be reported
  ready:
  - implementation:
    - `WeChatUiaSemanticActionRequest` now records
      `background_screenshot_count`, `background_screenshot_success_count`,
      `background_screenshot_verified`, and screenshot artifacts
    - UIA semantic send dry-run now returns
      `wechat_uia_semantic_action_background_screenshot_not_verified` when
      target/composer/send controls look ready but no successful no-focus
      screenshot exists
    - `WeChatNativeBridgeRequest` now uses the same screenshot evidence gate
      and returns `wechat_native_bridge_background_screenshot_not_verified`
      when a bridge/target/send action is otherwise ready but no background
      screenshot has been verified
    - `primary_real_no_loss` now passes the WeChat `PrintWindow` evidence into
      both UIA and native-bridge request contracts and has a primary-runner
      guard so injected/fake native dry-runs cannot bypass the screenshot gate
  - validation:
    - passed:
      `python -m unittest tests.test_wechat_uia_action_contract
      tests.test_wechat_native_bridge tests.test_primary_real_no_loss
      tests.test_primary_transport_matrix` with `21` tests
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss
      tests.test_agent_native_connector_probe tests.test_agent_cli_real_no_loss
      tests.test_agent_app_transport_matrix
      tests.test_cursor_attach_bridge_validation
      tests.test_ide_extension_readiness` with `67` tests
    - R145 real no-focus primary pass:
      `logs/runtime/primary-real-r145-20260602-wechat-screenshot-gate`
      returned `5/5` passed, `control_attempts=0`,
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `owned_app_launch_attempts=1`,
      `background_screenshot_count=1`,
      `background_screenshot_success_count=1`, and
      `background_screenshot_focus_stable=true`
    - R145 WeChat artifact:
      `logs/runtime/primary-real-r145-20260602-wechat-screenshot-gate/real_no_loss/wechat_chat_draft_reply.json`
      found one personal `Weixin.exe` window, produced one `PrintWindow`
      screenshot, kept foreground HWND stable, and kept send/window-input
      attempts at zero
    - R145 Browser artifact:
      the owned Chrome helper launched with `--headless`, used an isolated
      profile, verified the expected CDP page, stopped, and deleted the owned
      profile
  - current conclusion:
    - WeChat is implemented and real-verified for personal-window resolution,
      read-only locator diagnostics, no-focus HWND screenshot capture, and
      safe gating of UIA/native send routes
    - WeChat is not yet complete for true background send: the current live
      WeChat surface exposes no verified semantic composer/send control and
      no native bridge URL, so background send remains correctly blocked
    - the next concrete WeChat action is to build or attach a real native
      WeChat bridge endpoint, then run one opt-in file-helper send with the
      same no-focus screenshot/readback gates
- 2026-06-02 tightened the unified major-scenario no-focus gate and ran R146:
  - implementation:
    - `major_real_no_loss` now exposes `cli_foreground_focus_stable` and
      `cli_foreground_no_steal_verified`
    - `automation_focus_safe` now requires both:
      primary/app background screenshots stayed focus-safe, and CLI foreground
      changes were classified as no-steal
    - added a regression so a CLI command that changes foreground into an
      agent surface fails `safe_run_ok`, even if primary/app screenshots are
      stable
  - validation:
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `39` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix tests.test_agent_cli_real_no_loss`
      with `47` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - R146 real unified no-focus run:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs/runtime/major-real-r146-20260602-unified-nofocus
      --output logs/runtime/major-real-r146-20260602-unified-nofocus/report.json
      --json --allow-owned-browser-helper-launch
      --owned-browser-debug-port 19481 --allow-agent-cli-execution
      --agent-cli-timeout-sec 45`
    - top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `agent_command_attempts=2`, `owned_app_launch_attempts=1`,
      `background_screenshot_success_count=3/3`,
      `background_screenshot_focus_stable=true`,
      `cli_foreground_focus_stable=false`,
      `cli_foreground_no_steal_verified=true`, and
      `automation_focus_safe=true`
    - owned browser helper cleanup:
      helper status was `started_and_stopped`, owned profile cleanup reported
      `deleted=true`, and a process command-line scan found no matching
      Chrome/Edge process for port `19481` or the R146 runtime path
    - objective readiness:
      `10` requirements, `5` satisfied, `goal_complete=false`
      verified:
      WeChat background observation, Word hidden COM document,
      browser owned CDP read-page, owned file search, Codex CLI background task
      unsatisfied:
      WeChat background send, Claude CLI background task, Codex app background
      chat, Claude Desktop background chat, Cursor background chat
    - current blockers:
      WeChat still lacks a native bridge URL or semantic UIA send target;
      Claude CLI is installed but not logged in;
      Codex app and Cursor app lack a ready no-focus native/DevTools bridge;
      Claude Desktop app surface is unavailable/not visible to the no-focus app
      probe
  - current conclusion:
    - the project now has a single real no-loss acceptance report that can
      answer whether the whole objective is complete
    - as of R146 the safe background foundation is real, but the full
      objective is not yet achieved
    - next concrete action should target one of the remaining blockers with a
      connector-first route, preferably Cursor/Codex app bridge attach or a
      real WeChat native bridge, because UIA/vision cannot honestly satisfy
      no-focus background send for those surfaces today
- 2026-06-02 integrated attach-only IDE extension bridge readiness into the
  unified major no-loss acceptance report:
  - implementation:
    - `major_real_no_loss` now has a read-only
      `--probe-existing-ide-extension-bridge` option
    - the probe calls an already-running IDE extension bridge only; it does
      not launch Cursor, reload an extension host, type, click, use clipboard,
      or send a chat message
    - the resulting `ide_extension_readiness` report is written both at the
      top level and inside `subreports`
    - readiness counters are included in top-level safety accounting, so any
      accidental control/window-input/bridge-send attempt would fail the
      unified report instead of being hidden
    - the existing bridge URL is forwarded to agent-app probes only when the
      attach-only readiness probe reports `bridge_ready=true`; unavailable
      bridges are recorded as evidence but not promoted to control endpoints
  - validation:
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `42` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss
      tests.test_ide_extension_readiness tests.test_cursor_attach_bridge_validation
      tests.test_agent_app_real_no_loss` with `72` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix tests.test_agent_cli_real_no_loss
      tests.test_ide_extension_readiness tests.test_cursor_attach_bridge_validation
      tests.test_agent_app_real_no_loss` with `80` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - R148 real unified no-focus run:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs/runtime/major-real-r148-20260602-ide-readiness
      --output logs/runtime/major-real-r148-20260602-ide-readiness/report.json
      --json --allow-owned-browser-helper-launch
      --owned-browser-debug-port 19482 --allow-agent-cli-execution
      --agent-cli-timeout-sec 45 --probe-existing-ide-extension-bridge
      --ide-extension-bridge-url http://127.0.0.1:8787
      --ide-extension-agent-id cursor --ide-extension-request-timeout-sec 0.5`
    - top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `external_communication_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=2`,
      `owned_app_launch_attempts=1`, `background_screenshot_success=3/3`,
      `background_screenshot_focus_stable=true`,
      `cli_foreground_no_steal_verified=true`, and
      `automation_focus_safe=true`
    - IDE extension readiness:
      `status=bridge_unavailable`,
      `blocking_reason=bridge_endpoint_unavailable`,
      `bridge_ready=false`, and `can_write_without_focus=false`
      for `http://127.0.0.1:8787`
    - owned browser helper cleanup:
      a follow-up process scan found no process matching port `19482` or the
      R148 runtime profile path
    - objective readiness remains:
      `10` requirements, `5` satisfied, `goal_complete=false`
      verified:
      WeChat background observation, Word hidden COM document,
      browser owned CDP read-page, owned file search, Codex CLI background task
      unsatisfied:
      WeChat background send, Claude CLI background task, Codex app background
      chat, Claude Desktop background chat, Cursor background chat
  - current conclusion:
    - the unified acceptance report can now answer not only whether app chat
      endpoints are usable, but also whether an already-running IDE bridge is
      present and eligible to be forwarded
    - current Cursor bridge state is not ready in the active environment, and
      the report correctly keeps it as a blocker rather than attempting a
      foreground reload or visible launch
    - next concrete actions:
      1. continue connector-first work on one remaining write blocker:
         WeChat native bridge, Codex/Cursor app native/IDE bridge, or Claude
         login/native bridge
      2. keep visible app launch/reload as foreground-gated maintenance only
      3. preserve R148 as the authoritative no-focus completion gate until all
         five remaining unsatisfied requirements become verified
- 2026-06-02 added an explicit app endpoint readiness layer to the unified
  no-focus acceptance report:
  - implementation:
    - `major_real_no_loss` now exposes `agent_app_endpoint_readiness`
    - this is a read-only derived report built from existing app probe and
      endpoint-acceptance evidence; it does not run probes, launch apps, send
      messages, type, click, or touch clipboard
    - the report lists each agent app's observed endpoint count, ready endpoint
      count, ready endpoint type/URL/source, endpoint errors, whether the app
      can enter a background-send contract validation, helper template, owned
      DevTools launch template, and supplemental IDE extension readiness
    - a stale/unavailable IDE bridge can now refine the app blocker, for
      example Cursor moves from generic `gated_native_endpoint_missing` to the
      more actionable `bridge_endpoint_unavailable`
  - validation:
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `43` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe
      tests.test_agent_app_bridge tests.test_agent_app_transport_matrix
      tests.test_ide_extension_readiness tests.test_cursor_attach_bridge_validation
      tests.test_objective_readiness_matrix` with `131` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - R149 real unified no-focus run:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs/runtime/major-real-r149-20260602-endpoint-readiness
      --output logs/runtime/major-real-r149-20260602-endpoint-readiness/report.json
      --json --allow-owned-browser-helper-launch
      --owned-browser-debug-port 19483 --allow-agent-cli-execution
      --agent-cli-timeout-sec 45 --probe-existing-ide-extension-bridge
      --ide-extension-bridge-url http://127.0.0.1:8787
      --ide-extension-agent-id cursor --ide-extension-request-timeout-sec 0.5`
    - top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success=3/3`, and
      `automation_focus_safe=true`
    - endpoint readiness:
      `total_cases=3`, `observed_endpoint_cases=0`,
      `ready_endpoint_cases=0`,
      `background_send_contract_candidate_cases=0`, `blocked_cases=3`
    - endpoint blockers:
      Codex app=`gated_native_endpoint_missing`,
      Claude Desktop=`unavailable`,
      Cursor=`bridge_endpoint_unavailable`
    - owned browser helper cleanup:
      a follow-up process scan found no process matching port `19483` or the
      R149 runtime profile path
  - current conclusion:
    - the app-write blockers are now separated by phase:
      no endpoint observed, endpoint observed but unhealthy, endpoint ready but
      send not verified, or send verified
    - current real environment is still in the first phase for all app chat
      surfaces: no Codex/Cursor/Claude app endpoint is currently observed and
      ready for background-send contract validation
    - next concrete actions:
      1. build or attach one real no-focus app write transport, preferably an
         agent native bridge for Codex/Cursor app or a WeChat native bridge for
         File Transfer Assistant
      2. only after `ready_endpoint_cases > 0`, run the dry-run bridge contract
         and then opt-in send/readback acceptance
      3. keep R149 as the current endpoint-readiness baseline for app-surface
         work
- 2026-06-02 integrated the owned app bridge fixture smoke into the unified
  no-focus acceptance report:
  - implementation:
    - `major_real_no_loss` now has an optional
      `--run-agent-app-bridge-fixture-smoke` gate
    - the smoke reuses the existing local owned DevTools fixture and validates
      the app bridge sender contract through local HTTP/WebSocket CDP without
      launching WeChat, Cursor, Claude, or Codex desktop windows
    - the report now exposes
      `agent_app_bridge_fixture_smoke_enabled`,
      `agent_app_bridge_fixture_smoke_ok`,
      `agent_app_bridge_fixture_control_attempts`, and
      `agent_app_bridge_fixture_native_call_attempts`
    - fixture failure now contributes to `failed_runner_count`, so a broken
      bridge substrate cannot be hidden behind a green unified report
    - this is bridge substrate evidence only; it does not promote any real app
      endpoint to ready and does not satisfy Codex/Cursor/Claude app chat
      requirements
  - validation:
    - passed:
      `python -m unittest tests.test_agent_app_bridge_fixture_smoke
      tests.test_agent_native_cdp_bridge` with `8` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `46` tests
    - passed:
      `python -m unittest tests.test_major_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe
      tests.test_agent_app_bridge tests.test_agent_app_transport_matrix
      tests.test_ide_extension_readiness tests.test_cursor_attach_bridge_validation
      tests.test_objective_readiness_matrix
      tests.test_agent_app_bridge_fixture_smoke tests.test_agent_native_cdp_bridge`
      with `142` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - R150 real unified no-focus run:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs/runtime/major-real-r150-20260602-bridge-fixture
      --output logs/runtime/major-real-r150-20260602-bridge-fixture/report.json
      --allow-owned-browser-helper-launch --owned-browser-debug-port 19484
      --allow-agent-cli-execution --agent-cli-timeout-sec 45
      --probe-existing-ide-extension-bridge
      --ide-extension-bridge-url http://127.0.0.1:8787
      --ide-extension-agent-id cursor --ide-extension-request-timeout-sec 0.5
      --run-agent-app-bridge-fixture-smoke
      --agent-app-bridge-fixture-message OPENWUKONG_APP_BRIDGE_FIXTURE_R150
      --agent-app-bridge-fixture-acceptance-marker
      "OPENWUKONG_ACCEPTANCE: PASS"`
    - top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `agent_command_attempts=2`,
      `background_screenshot_success=3/3`, `background_screenshot_focus_stable=true`,
      `agent_app_bridge_fixture_smoke_enabled=true`,
      `agent_app_bridge_fixture_smoke_ok=true`, and
      `agent_app_bridge_fixture_native_call_attempts=1`
    - fixture evidence:
      `decision=agent_app_bridge_fixture_smoke_verified`,
      `desktop_control_attempts=0`, `window_input_attempts=0`,
      `cdp_request_count=2`, and native call attempts were recorded through
      the bridge send report
    - endpoint readiness remains:
      `total_cases=3`, `observed_endpoint_cases=0`,
      `ready_endpoint_cases=0`,
      `background_send_contract_candidate_cases=0`, `blocked_cases=3`
    - endpoint blockers:
      Codex app=`gated_native_endpoint_missing`,
      Claude Desktop=`unavailable`,
      Cursor=`bridge_endpoint_unavailable`
    - cleanup:
      a follow-up process scan found no Chrome/Edge/crashpad process matching
      port `19484` or the R150 runtime browser profile path
  - current conclusion:
    - the bridge sender substrate is now verified inside the same unified
      no-focus report used for the main objective
    - the remaining real blocker is not the bridge contract itself; it is
      discovering or installing one real no-focus app endpoint for WeChat,
      Codex app, Cursor, or Claude Desktop, then running dry-run contract and
      opt-in send/readback against that endpoint
    - next concrete actions:
      1. implement or attach a real no-focus app endpoint, with WeChat native
         bridge or Cursor/Codex native/IDE bridge as the highest-leverage path
      2. require `ready_endpoint_cases > 0` before attempting any real app-side
         send
      3. preserve R150 as the bridge-substrate baseline and R149/R150 endpoint
         readiness as the app-surface blocker baseline
- 2026-06-02 integrated a real Codex Desktop app-server WebSocket readiness
  route into the unified no-focus acceptance path:
  - implementation:
    - added `openwukong.evaluation.codex_app_server_probe`, a stdlib
      read-only WebSocket JSON-RPC probe for local
      `codex.exe app-server --listen ws://127.0.0.1:<port>`
    - the probe calls only `initialize` and `thread/list`, records
      `request_attempts=2`, `control_attempts=0`, and
      `window_input_attempts=0`, and does not send turns or chat messages
    - `agent_native_connector_probe` now accepts
      `--codex-app-server-ws-url` and exposes ready endpoints as
      `endpoint_type=codex_app_server_ws`
    - `agent_app_real_no_loss` and `major_real_no_loss` now forward explicit
      Codex app-server WebSocket URLs into the same unified no-loss report
    - `agent_app_transport_matrix` treats `codex_app_server_ws` as
      `background-native` thread readiness only: it is ready evidence, but
      `can_send_without_focus=false` until a turn-send/readback contract is
      implemented
    - fixed major requirement attribution so a real ready endpoint reports
      `native_connector_ready_but_send_not_verified` instead of stale
      `gated_native_endpoint_missing`
  - validation:
    - passed:
      `python -m unittest tests.test_codex_app_server_probe
      tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss
      tests.test_agent_app_transport_matrix tests.test_major_real_no_loss`
      with `104` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
    - R151 first real run exposed a useful startup-resolution bug:
      `Get-Command codex.exe` resolved to the MSIX Desktop resource path and
      `Start-Process` returned `Access is denied`; the no-focus runner was
      corrected to use the real CLI bin under
      `%LOCALAPPDATA%\OpenAI\Codex\bin\...\codex.exe`
    - R152 real unified no-focus run:
      `logs/runtime/major-real-r152-20260602-codex-app-server-ws-requirement`
      started a hidden managed Codex app-server helper on
      `ws://127.0.0.1:19733`, passed that endpoint to the unified major
      report, then stopped the helper by PID
    - R152 top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=2`, `background_screenshot_success=3/3`,
      and `background_screenshot_focus_stable=true`
    - R152 Codex app evidence:
      `codex_app_background_chat=gated(native_connector_ready_but_send_not_verified)`,
      `ready_endpoint_count=1`,
      `ready_endpoint_type=codex_app_server_ws`, and
      endpoint readiness blocker
      `native_connector_ready_but_send_not_verified`
    - cleanup:
      final process scan found no non-shell process matching port `19733`,
      owned browser port `19486`, or the R152 runtime profile path
  - current conclusion:
    - Codex Desktop now has a real no-focus native endpoint readiness route in
      the unified acceptance report
    - this is not yet Codex app background chat completion: the remaining
      Codex app work is to implement a safe turn-start/send contract and
      readback marker verification over the app-server API
    - WeChat remains real-verified for observation/background screenshot and
      has prior opt-in File Transfer Assistant send evidence, but the unified
      product-grade no-focus send requirement still needs a reusable native
      bridge or verified semantic sender/readback route
    - remaining unsatisfied requirements after R152:
      WeChat background send, Claude CLI auth, Claude Desktop app chat, Cursor
      app chat, and Codex app send/readback
- 2026-06-02 integrated Codex app-server turn dry-run contract into the
  unified no-focus acceptance path and added precision guards:
  - implementation:
    - added `openwukong.control.codex_app_server_bridge`, a dry-run only
      contract builder for Codex app-server `turn/start`
    - the contract records schema version, endpoint evidence, selected
      `threadId`, `cwd`, required/forbidden result markers, read-only sandbox
      policy, and zero send/native/window-input attempts
    - `agent_app_real_no_loss` now emits
      `codex_app_server_turn_dry_run` and
      `codex_app_server_turn_contract_ready` for ready
      `codex_app_server_ws` endpoints
    - `major_real_no_loss` now surfaces that contract in
      `agent_app_endpoint_readiness`
    - added workspace/thread ownership validation: a Codex app-server thread
      selected from a different `cwd` now reports
      `codex_app_server_workspace_mismatch` instead of being promoted to a
      ready send contract
    - hardened agent app DevTools launch planning so
      `C:\Program Files\WindowsApps\...` MSIX/Electron shell paths are not
      marked as background-launchable helper executables; they now carry
      `launch_blocking_reason=msix_windowsapps_not_background_launchable`
  - validation:
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe tests.test_agent_native_connector_probe
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `109` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
    - R153 real unified no-focus run:
      `logs/runtime/major-real-r153-20260602-codex-turn-dry-run`
      started hidden Codex app-server on `ws://127.0.0.1:19734` and proved
      a dry-run `turn/start` payload could be generated without any real
      app-server `turn/start`, bridge send, keyboard, mouse, clipboard, or
      window input attempts
    - R153 also exposed a critical precision issue: the live app-server
      selected thread belonged to
      `E:\ideaProjects\agent\CyberHuaTuo`, not the current `openwukong`
      workspace, so endpoint readiness alone is not enough for precise
      control
    - R154 real unified no-focus run:
      `logs/runtime/major-real-r154-20260602-codex-thread-workspace-guard`
      passed an explicit `--workspace-path E:\ideaProjects\agent\openwukong`;
      the report correctly blocked the Codex turn dry-run with
      `decision=codex_app_server_workspace_mismatch`,
      `validation_errors=['workspace_mismatch']`, and
      `workspace_match=false`
    - R154 kept `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, and left no non-shell helper process matching
      the app-server/browser ports or runtime path
    - during the same real-testing window a WindowsApps/MSIX Codex launch
      popup appeared (`Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_...?...`), confirming that
      MSIX shell paths must not be used as background Electron helper paths;
      that risk is now covered by regression tests and launch-plan blocking
  - current conclusion:
    - Codex app-server now has a real no-focus endpoint readiness route and a
      safe dry-run send contract, but precise project routing is still not
      complete until the app-server can select or create the correct
      `openwukong` thread before real send/readback
    - this is a useful quality bar for every future app connector: endpoint
      readiness, payload schema, no-focus safety, session ownership, and
      readback markers must all pass before any real action is accepted
    - remaining unsatisfied requirements remain:
      WeChat product-grade background send, Claude CLI auth, Claude Desktop app
      chat, Cursor app chat, and Codex app correct-thread send/readback
- 2026-06-02 upgraded the Codex app-server contract from single-step
  `turn/start` dry-run to a two-stage session-safe contract:
  - implementation:
    - `CodexAppServerTurnRequest` now inspects `observed_threads` from the
      app-server probe instead of trusting only `selected_thread_id`
    - if an observed thread matches the requested workspace, the contract uses
      that thread for `turn/start` even when the app-server's selected thread
      points at another project
    - if no matching thread exists but an explicit workspace is supplied, the
      contract now produces a safe `thread/start` dry-run with:
      `cwd=<requested workspace>`, `approvalPolicy=never`,
      `sandbox=read-only`, and `threadSource=user`
    - in the missing-thread case, `turn_start_ready=false` and the generated
      `turn_start_params.threadId` stays empty, so the system cannot
      accidentally send to the wrong project
    - `agent_app_real_no_loss` and `major_real_no_loss` now expose:
      `codex_app_server_thread_start_required`,
      `codex_app_server_thread_start_ready`, and
      `codex_app_server_turn_start_ready`
  - validation:
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe tests.test_agent_native_connector_probe
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `112` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
    - R155 real unified no-focus run:
      `logs/runtime/major-real-r155-20260602-codex-thread-start-dry-run`
      started hidden Codex app-server on `ws://127.0.0.1:19736`, passed
      `--workspace-path E:\ideaProjects\agent\openwukong`, then stopped the
      helper by PID
    - R155 top-level result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `background_screenshot_success=4/4`, and no non-shell helper process
      remained for the app-server/browser ports or runtime path
    - R155 Codex contract evidence:
      `turn_contract_ready=true`,
      `thread_start_required=true`,
      `thread_start_ready=true`,
      `turn_start_ready=false`,
      `decision=codex_app_server_thread_start_dry_run_ready`,
      `thread_start_params.cwd=E:\ideaProjects\agent\openwukong`,
      while the observed selected thread still belonged to
      `E:\ideaProjects\agent\CyberHuaTuo-Plugin`
  - current conclusion:
    - Codex app control has moved from "endpoint ready but wrong-thread risk"
      to a precise staged contract:
      1. attach app-server,
      2. choose an already matching workspace thread when present,
      3. otherwise create the correct workspace thread,
      4. only then run `turn/start` and readback-marker acceptance
    - this still does not satisfy the Codex app background chat requirement,
      because no real `thread/start`, real `turn/start`, or readback marker
      verification has been executed yet
    - next concrete action:
      implement an opt-in Codex app-server `thread/start` executor with
      foreground/focus checks and read-only params, verify it creates or
      returns an `openwukong` thread without window input, then run the
      already-prepared `turn/start` dry-run against that newly owned thread
- 2026-06-02 confirmed the visible `Error launching app` dialog reported by
  the user is the same blocked MSIX/Electron launch-entry failure:
  - symptom:
    `Unable to find Electron app at
    C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\?type=click&tag=...`
  - interpretation:
    this is not a Codex app-server protocol failure and not a WeChat/browser
    control failure; it is a bad foreground-prone launch path caused by
    treating a WindowsApps/MSIX Codex package path plus query parameters as a
    normal Electron executable/app directory
  - current guard:
    `major_real_no_loss` now treats `C:\Program Files\WindowsApps\...` app
    shell paths as installation/foreground-shell evidence only, sets
    `launch_blocking_reason=msix_windowsapps_not_background_launchable`, and
    keeps launch attempts at zero for owned DevTools-style background helper
    startup
  - validation:
    passed targeted regression:
    `python -m unittest tests.test_major_real_no_loss
    tests.test_codex_app_server_bridge tests.test_agent_app_real_no_loss`
    with `75` tests
    passed `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - next concrete action remains unchanged:
    use the hidden app-server path only, implement the opt-in `thread/start`
    executor, verify correct `openwukong` thread ownership without focus
    change, then move to `turn/start` dry-run/readback acceptance
- 2026-06-02 implemented and verified opt-in Codex app-server `thread/start`
  execution for correct-workspace session ownership:
  - implementation:
    - added `CodexAppServerThreadStartAdapter` and
      `CodexAppServerThreadStartExecutionReport`
    - added a WebSocket JSON-RPC client path:
      `initialize -> thread/start -> thread/list`
    - exposed `--allow-codex-app-server-thread-start` and
      `--codex-app-server-thread-start-timeout` in the agent-app and major
      no-loss runners
    - default remains dry-run only; real thread creation occurs only behind
      the explicit opt-in flag
    - real `turn/start` is still not executed; after a verified `thread/start`,
      the runner only rebuilds the `turn/start` dry-run contract against the
      newly owned thread
    - focus is checked through foreground HWND before/after; the executor
      records native call attempts separately from window input attempts
  - bug found during real validation:
    - first real R156 created the correct `openwukong` thread, but immediate
      `thread/list useStateDbOnly=true` still returned stale previous threads,
      so the first implementation reported
      `codex_app_server_thread_start_list_verification_failed`
    - root cause was an overly strict readback strategy against an eventually
      consistent state-db list
    - fix:
      accept thread creation only when the `thread/start` response and a
      same-connection `thread/started` notification both identify a thread
      whose `cwd` exactly matches the requested workspace; stale thread-list
      output is preserved as diagnostic evidence and still fails if response
      or notification is missing/mismatched
    - the reusable pattern was added to the global
      `desktop-background-control-testing` skill
  - validation:
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe tests.test_agent_native_connector_probe
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `117` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
    - R157 real no-focus run:
      `logs/runtime/agent-app-r157-20260602-codex-thread-start-real/report.json`
      started hidden Codex app-server on `ws://127.0.0.1:19738`, created a
      Codex thread for `E:\ideaProjects\agent\openwukong`, then stopped the
      helper by PID
    - R157 evidence:
      `failed_cases=0`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `thread_start_verified=true`, `thread_start_attempts=1`,
      `native_call_attempts=1`,
      `thread_start_decision=codex_app_server_thread_start_verified`,
      `verified_by_notification=true`, `foreground_focus_stable=true`,
      `after_turn_decision=codex_app_server_turn_dry_run_ready`,
      `after_turn_ready=true`,
      `after_cwd=E:\ideaProjects\agent\openwukong`, and
      `remaining_owned_helpers=0`
  - current conclusion:
    - Codex App is now background-controllable through app-server for the
      session/thread ownership layer: the system can create and verify the
      correct project thread without GUI focus, keyboard, mouse, clipboard, or
      WindowsApps launch
    - the Codex App background chat requirement is still not complete because
      no real `turn/start` has been executed and no assistant readback marker
      has been accepted yet
    - next concrete action:
      add an opt-in `turn/start` executor that consumes only a verified
      thread-owned dry-run contract, records native app-server attempts, uses
      read-only sandbox/approval settings, waits for completion/readback
      events, and accepts success only when required/forbidden markers pass
- 2026-06-02 tightened handling for the second user-reported Codex
  MSIX/Electron protocol error dialog:
  - symptom:
    foreground popup titled `Error` with body similar to
    `Error launching app`, `Unable to find Electron app at
    C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\?type=click&tag=...`,
    and `Cannot find module`
  - root cause classification:
    same failure family as the earlier `选择应用以打开 "session-start"` picker;
    a foreground-prone protocol/deep-link path is being routed through a
    WindowsApps Codex shell instead of the hidden app-server connector
  - implementation:
    - upgraded IDE bridge foreground snapshots to preserve window class,
      process identity, executable path, and child-window/body text where
      available
    - upgraded system-dialog detection to classify `session-start`,
      Windows open-with, and Codex MSIX/Electron launch errors as hard
      foreground blockers
    - added regression coverage for both the generic dialog detector and
      Cursor draft-hook validation so readback success cannot mask this
      focus-stealing failure
  - validation:
    - passed:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_cursor_draft_hook_validation` with `22` tests
    - passed broader regression:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_cursor_draft_hook_validation tests.test_major_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe` with `105` tests
    - passed:
      `git diff --check`; only existing LF-to-CRLF warnings were emitted
  - current conclusion:
    - WeChat/browser/Word no-loss paths are not implicated by this popup.
    - Codex app control must continue through hidden `codex.exe app-server`
      and never through `C:\Program Files\WindowsApps\OpenAI.Codex...\...`
      foreground launch/deep-link handling.
    - next concrete action remains:
      implement the opt-in real `turn/start` executor on the already verified
      app-server thread and accept it only through assistant readback markers.
- 2026-06-02 implemented the opt-in Codex app-server `turn/start` executor
  and tightened the third user-reported Codex WindowsApps/Electron popup:
  - implementation:
    - added `CodexAppServerTurnStartAdapter` and
      `CodexAppServerTurnStartExecutionReport`
    - added app-server WebSocket flow:
      `initialize -> turn/start -> collect notifications until turn/completed`
    - exposed `--allow-codex-app-server-turn-start` and
      `--codex-app-server-turn-start-timeout` in the agent-app and major
      no-loss runners
    - turn execution remains opt-in and consumes only a verified
      workspace-owned dry-run contract
    - success requires assistant readback markers and forbidden-marker checks;
      user prompt text alone is not counted as assistant readback
    - the report now separates `thread/start` native calls from `turn/start`
      native calls and still keeps keyboard, mouse, clipboard, bridge-send,
      and window-input attempts at zero
  - real validation:
    - R158:
      `logs/runtime/agent-app-r158-20260602-codex-turn-start-real/report.json`
      started a hidden Codex app-server on `ws://127.0.0.1:19739`, created
      or selected the correct `openwukong` thread, then issued an opt-in
      `turn/start`
    - R158 evidence:
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`,
      `thread_start_verified=true`, `thread_start_attempts=1`,
      `turn_start_attempts=1`, and `native_call_attempts=2`
    - R158 did not complete Codex background chat:
      `codex_app_server_turn_start_verified_cases=0`,
      `turn_completed=false`, missing marker
      `OPENWUKONG_ACCEPTANCE: PASS`, and the app-server stderr included
      Windows sandbox `spawn setup refresh` errors
    - therefore this proves native app-server command submission, not
      accepted assistant completion/readback yet
  - new popup:
    - symptom:
      foreground `Error` dialog containing
      `A JavaScript error occurred in the main process`,
      `Uncaught Exception`, and `Error: AttachConsole failed`, with stack
      paths under
      `C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\app\...`
    - classification:
      same blocked WindowsApps/MSIX Codex Electron-shell failure family as
      the earlier `session-start` picker and
      `Unable to find Electron app` / `Cannot find module` dialog
    - implementation:
      `ide_bridge_contract_probe` system-dialog detection now treats
      `AttachConsole failed`, Electron main-process JavaScript errors, and
      `Uncaught Exception` as hard foreground blockers when tied to Codex,
      WindowsApps, or Electron evidence
    - Cursor draft-hook validation also rejects this popup even when composer
      readback text appears to contain the expected marker
    - reusable rule added to global skill:
      `desktop-background-control-testing`
  - validation:
    - passed:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_cursor_draft_hook_validation` with `24` tests
    - passed broader regression:
      `python -m unittest tests.test_ide_bridge_contract_probe
      tests.test_cursor_draft_hook_validation tests.test_major_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe` with `113` tests
  - current conclusion:
    - WeChat File Transfer Assistant send was previously real-verified, but
      that specific milestone used an explicitly approved foreground
      keyboard/clipboard transport, not a product-grade background-native
      WeChat bridge
    - browser and Word no-loss paths remain unaffected
    - Codex app-server can now create a correct project thread and issue
      opt-in `turn/start` without GUI input, but Codex background chat is not
      accepted until a real assistant completion/readback marker passes
    - next concrete actions:
      1. inspect app-server `TurnStartParams` and execution options to avoid
         sandbox/setup-refresh failure for no-loss readback tests
      2. add system-dialog polling to the Codex app-server turn executor so a
         WindowsApps/Electron popup immediately fails the run with a precise
         blocker reason
      3. rerun Codex `turn/start` against an owned no-loss workspace and then
         the target `openwukong` workspace only after the sandbox/tool
         behavior is understood
- 2026-06-02 hardened Codex app-server real-turn no-focus validation after
  the user reported another Codex foreground JavaScript error popup:
  - implementation:
    - `CodexAppServerTurnStartAdapter` now checks
      `windowsSandbox/readiness` before issuing `turn/start`
    - `turn/start` execution now polls for Windows system dialogs while the
      native WebSocket call is in flight
    - foreground verification was upgraded from raw HWND equality to
      foreground snapshots and classification:
      `stable`, `changed_to_unrelated_surface`,
      `changed_to_agent_surface`, `changed_to_system_dialog`, and
      `changed_unknown`
    - a user switching to an unrelated identifiable app no longer causes a
      false no-loss failure; a switch to Codex, a Codex/MSIX/Electron error
      dialog, or an unknown foreground surface still fails
    - agent-app case status now surfaces failed `turn/start` decisions, so a
      failed real turn is no longer masked as only
      `codex_app_server_thread_start_verified`
  - validation:
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge`
      with `20` tests
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_agent_app_real_no_loss`
      with `45` tests
    - passed broader regression:
      `python -m unittest tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe tests.test_agent_native_connector_probe
      tests.test_agent_app_transport_matrix
      tests.test_objective_readiness_matrix`
      with `132` tests
    - R160 real no-loss run:
      `logs/runtime/agent-app-r160-20260602-codex-turn-focus-classification/report.json`
      started hidden Codex app-server on `ws://127.0.0.1:19741`, created a
      correct `openwukong` thread, then issued opt-in `turn/start`
    - R160 evidence:
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `thread_start_verified=true`,
      `thread_fg_class=stable`, `turn_attempts=1`,
      `windows_sandbox_readiness_status=ready`, but
      `turn_decision=codex_app_server_turn_start_foreground_changed` because
      foreground changed from `explorer.exe` to `Codex.exe`
      (`changed_to_agent_surface`)
  - current conclusion:
    - Codex app-server `thread/start` is background/session safe.
    - Codex app-server `turn/start` is not yet no-focus/action safe on this
      desktop app path, because it activates the Codex WindowsApps desktop
      shell.
    - the app-server v2 `TurnStartParams` schema currently exposes model,
      effort, cwd, approval, sandbox, personality, service tier, and
      output schema controls, but no observed background/headless/no-activate
      flag
    - for product-grade Codex task submission, either find an app-server
      option or alternate Codex connector that does not activate the desktop
      shell, or route background Codex execution through the CLI/extension
      transport while keeping the desktop shell as read-only/session evidence
  - next concrete actions:
    1. search for a non-activating Codex background action route:
       CLI `exec`, IDE extension, or another app-server method
    2. keep `turn/start` gated as foreground-risk until a no-focus real run
       proves otherwise
    3. apply the same foreground-classified action-safety standard to Claude
       Desktop and other agent apps
- 2026-06-02 hardened the Codex non-activating background route:
  - implementation:
    - added a default local Codex CLI discovery path for
      `%LOCALAPPDATA%\OpenAI\Codex\bin\...\codex.exe`
    - the resolver now exposes this as `local-agent-cli` so Codex background
      task submission can bind to the standalone CLI even when no CLI process
      is already running
    - `C:\Program Files\WindowsApps\OpenAI.Codex...\app\resources\codex.exe`
      is no longer classified as a CLI surface; it remains helper/worker
      evidence only
    - agent CLI reports now lift `selected_transport` to the case top level,
      so readiness matrices can show the actual transport even when the run is
      not marker-verified
    - Codex/agent CLI usage-limit failures are now classified as
      `cli_usage_limit` instead of generic `cli_execution_failed`
  - validation:
    - passed:
      `python -m unittest tests.test_app_resolution
      tests.test_agent_surface_report tests.test_agent_task_runner
      tests.test_agent_cli_real_no_loss`
      with `43` tests
    - passed:
      `python -m unittest tests.test_agent_cli_real_no_loss
      tests.test_objective_readiness_matrix tests.test_app_resolution
      tests.test_agent_surface_report tests.test_agent_task_runner`
      with `45` tests
    - current resolver check:
      `WindowsAppResolver().resolve('codex cli')` resolves only to
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\716dda49c14d31a0\codex.exe`
      and not to a WindowsApps resource path
    - R161 real no-loss run:
      `logs/runtime/agent-cli-real-r161-20260602-local-cli-provider/report.json`
      ran Codex CLI from LocalAppData with read-only sandbox, approval never,
      an owned temporary workspace, and zero window input attempts
    - R161 focus evidence:
      foreground changed from VMware to Cursor, classified as
      `changed_to_unrelated_surface`, so no Codex focus steal was detected
    - R161 execution result:
      the CLI returned a usage-limit error:
      `You've hit your usage limit... try again at 7:43 PM`, so the required
      marker was not produced and Codex CLI task completion remains unverified
      for the current account/time window
  - current conclusion:
    - Codex has a correct background execution substrate via standalone CLI,
      and it avoids the WindowsApps/MSIX foreground-shell failure family
    - the current blocker for Codex CLI marker verification is service quota,
      not local control precision or focus safety
    - Codex Desktop App still needs a non-activating native route before it
      can be counted as background app-chat verified
  - next concrete actions:
    1. keep Codex desktop `turn/start` blocked for no-focus action tests
    2. use Codex CLI as the background task route once quota is available
    3. continue the same route hardening for Claude Desktop/Claude CLI and
       Cursor app bridge
- 2026-06-02 fixed the repeated Codex WindowsApps/Electron foreground error
  route after the user reported another `Error launching app` dialog with
  `?type=click&tag=...`:
  - root cause:
    - generic `codex` resolution could still select a running
      `C:\Program Files\WindowsApps\OpenAI.Codex...\app\Codex.exe` desktop
      shell when that shell was already running
    - Codex app-server `turn/start` dry-run could still be considered ready
      for a Windows desktop app-server endpoint; runtime focus checks caught
      the failure after the fact, but the action could still trigger the
      desktop shell and its MSIX/Electron notification/deep-link failure
      family
  - implementation:
    - generic `codex` now prefers CLI/connector surfaces for background task
      execution; only explicit `codex app` or `codex desktop` selects the
      desktop shell
    - `codex_candidate_surface_kind` now treats WindowsApps
      `app\resources\codex.exe` and Cursor extension workers as helper
      evidence, not CLI
    - Codex app-server `turn/start` now requires endpoint metadata
      `turn_start_foreground_safe=true`; otherwise a matched-thread turn
      dry-run fails before any native call with
      `codex_app_server_turn_start_foreground_risk`
    - Windows/Codex Desktop app-server evidence gets the explicit block reason
      `windows_desktop_app_server_turn_start_foreground_risk`
  - validation:
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss
      tests.test_codex_app_server_bridge` with `46` tests
    - passed broader regression:
      `python -m unittest tests.test_app_resolution
      tests.test_agent_surface_report tests.test_agent_task_runner
      tests.test_agent_cli_real_no_loss tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe tests.test_agent_native_connector_probe
      tests.test_agent_app_transport_matrix
      tests.test_objective_readiness_matrix` with `178` tests
    - current resolver check:
      `WindowsAppResolver().resolve('codex')` and `resolve('codex cli')`
      select
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\716dda49c14d31a0\codex.exe`;
      `resolve('codex app')` separately selects the WindowsApps desktop shell
    - replayed R160 Windows Desktop app-server evidence after forcing the
      thread to match `openwukong`: dry-run now returns
      `codex_app_server_turn_start_foreground_risk`, `turn_start_ready=false`,
      and `app_server_turn_start_attempts=0`
    - `git diff --check` passed with only existing LF-to-CRLF warnings
  - current conclusion:
    - this foreground popup family should no longer be triggered by our
      no-focus Codex app-server path
    - Codex Desktop app-server remains useful for session/thread evidence and
      `thread/start`, but not for background `turn/start` on this Windows
      desktop route
    - Codex background task execution should continue through the standalone
      CLI or a future extension/native connector with explicit foreground-safe
      metadata
- 2026-06-02 advanced Claude/Cursor no-focus route hardening:
  - real read-only app-surface validation:
    - R162:
      `logs/runtime/agent-app-r162-20260602-claude-cursor-readonly/report.json`
      probed `claude desktop` and `cursor` with no send, no UIA write, no
      keyboard, no mouse, and no clipboard
    - R162 evidence:
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`, and
      `background_screenshot_focus_stable=true`
    - Claude Desktop process existed, but no target app window was visible to
      the read-only UIA probe
    - Cursor was background screenshot-capable, but the matched window was a
      different project (`trustusb-2`), so `openwukong` was not safe to target
  - implementation:
    - app no-loss case status now distinguishes `app_window_not_found`,
      `target_project_not_visible`, and `target_task_not_visible` from the
      generic `gated_native_endpoint_missing`/`unavailable` states
    - R163:
      `logs/runtime/agent-app-r163-20260602-claude-cursor-status-precision/report.json`
      verified the refined statuses:
      `claude desktop -> app_window_not_found` and
      `cursor -> target_project_not_visible`
    - added Cursor Agent CLI as a first-class background task transport:
      generic `cursor` prefers `cursor-agent` when installed, while explicit
      `cursor app`/`cursor desktop` still resolves only to the desktop shell
    - added `cursor-agent-cli-managed-terminal` and command planning for
      `cursor-agent -p --output-format json <task>`
    - major no-loss defaults now include `cursor` in CLI agents and add a
      separate `cursor_cli_background_task` requirement
    - CLI no-loss probes now resolve explicit CLI aliases
      (`codex cli`, `claude cli`, `cursor agent`) so a missing CLI cannot
      silently fall back to a desktop app shell
  - validation:
    - passed targeted TDD checks for Cursor CLI resolution, surface binding,
      command planning, CLI no-loss success/fallback behavior, and major
      requirement aggregation
    - passed broader regression:
      `python -m unittest tests.test_app_resolution
      tests.test_agent_surface_report tests.test_agent_task_runner
      tests.test_agent_cli_real_no_loss tests.test_agent_app_real_no_loss
      tests.test_agent_app_transport_matrix tests.test_agent_app_bridge
      tests.test_agent_app_uia_action_contract
      tests.test_agent_native_connector_probe tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix` with `195` tests
    - R165:
      `logs/runtime/agent-cli-r165-20260602-cursor-cli-no-desktop-fallback/report.json`
      verified this machine has no `cursor-agent`; result was
      `background_cli_unavailable`, `selected_transport=""`,
      `agent_command_attempts=0`, `window_input_attempts=0`, and stable
      foreground
    - resolver check:
      `cursor` currently resolves to the running desktop shell because
      `cursor-agent` is absent; `cursor agent` returns `app_not_found`;
      `cursor app` resolves to the desktop shell
    - `git diff --check` passed with only existing LF-to-CRLF warnings
  - current conclusion:
    - Claude CLI/background route is structurally present; Claude Desktop app
      route is not currently background app-chat ready because no target app
      window was visible in the read-only probe
    - Cursor desktop can be inspected and background-captured, but the
      currently visible Cursor project is not `openwukong`, so app-chat send
      remains unsafe until the correct project/session is visible or an IDE
      bridge/native connector reports the correct workspace
    - Cursor Agent CLI is now supported as the best background task route when
      installed; this machine currently lacks `cursor-agent`
  - next concrete actions:
    1. install or locate official `cursor-agent`, then rerun Cursor CLI
       no-loss marker verification
    2. use a no-focus attach/bridge route to verify Cursor `openwukong`
       workspace identity before any app chat send
    3. continue Claude app-side validation only after a visible/attachable
       target Claude window or native bridge is present
- 2026-06-02 Codex MSIX/Electron `?type=click&tag=...` popup hardening:
  - trigger:
    - real desktop produced repeated Codex error dialogs:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.52...\type=click&tag=...`,
      and `Cannot find module`
    - this is the same foreground-blocking family as prior
      `session-start` open-with pickers and `AttachConsole failed` Codex
      Electron dialogs
  - root cause:
    - the underlying route can still activate the WindowsApps/Codex Desktop
      Electron shell or protocol/deep-link handler instead of using a proven
      hidden app-server/CLI/native connector action path
    - the previous implementation detected delayed dialogs after a call, but
      did not treat an already-open system dialog as a hard preflight blocker
      before `thread/start` or `turn/start`
    - `thread/start` lacked the same system-dialog observer and evidence
      fields that `turn/start` already had
  - implementation:
    - `CodexAppServerThreadStartAdapter` now accepts
      `system_dialog_observer`, samples before/during/after the native call,
      exposes `system_dialog_detected` and `system_dialog_snapshots`, and
      returns `codex_app_server_thread_start_system_dialog_detected` with
      zero request/native attempts if a dialog is already open
    - `CodexAppServerTurnStartAdapter` now samples existing dialogs before
      the native call and returns
      `codex_app_server_turn_start_system_dialog_detected` with
      `request_attempts=0`, `app_server_turn_start_attempts=0`, and
      `native_call_attempts=0`
    - `agent_app_real_no_loss` now passes the dialog observer into the
      Codex app-server path and surfaces system-dialog decisions as failed
      case statuses even when attempts are zero
    - updated global skill
      `desktop-background-control-testing` so this is a reusable preflight
      gate, not just post-action evidence
  - validation:
    - added TDD tests for pre-existing Codex Electron error dialogs and
      `session-start` open-with dialogs before app-server calls
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge` with `23` tests
    - passed related regression:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_agent_app_real_no_loss tests.test_major_real_no_loss
      tests.test_ide_bridge_contract_probe tests.test_cursor_draft_hook_validation`
      with `122` tests
    - passed wider agent/no-loss regression:
      `python -m unittest tests.test_app_resolution
      tests.test_agent_surface_report tests.test_agent_task_runner
      tests.test_agent_cli_real_no_loss tests.test_agent_app_real_no_loss
      tests.test_agent_app_transport_matrix tests.test_agent_app_bridge
      tests.test_agent_app_uia_action_contract
      tests.test_agent_native_connector_probe tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix tests.test_codex_app_server_bridge`
      with `219` tests
  - current conclusion:
    - the current Codex Desktop app-server `turn/start` route remains
      action-unsafe unless endpoint metadata proves foreground safety; when
      this popup family appears, the runner now stops immediately instead of
      continuing with more native actions
    - this is not a failure of the overall architecture; it reinforces the
      chosen layering: CLI/native/extension connector first, desktop shell
      protocol activation only behind explicit foreground gates
  - next concrete actions:
    1. keep Codex Desktop app-server `turn/start` disabled for real background
       execution unless a route proves `turn_start_foreground_safe=true`
    2. route Codex background tasks through the standalone Codex CLI or a
       native/extension connector, not the WindowsApps desktop shell
    3. continue validating agent app surfaces with system-dialog preflight
       gates before any native/action call
- 2026-06-02 top-level system-dialog preflight for major no-loss runs:
  - decision:
    - moved the Codex popup hardening from app-server-local protection toward
      the full major no-loss orchestration layer
    - `major_real_no_loss` now performs a read-only desktop system-dialog
      preflight before primary scenarios, agent app probes, agent CLI probes,
      owned helper launches, or fixture smoke runs
  - implementation:
    - added `openwukong.control.desktop_system_dialog` with
      `run_desktop_system_dialog_preflight`
    - the preflight enumerates visible top-level Windows dialogs read-only and
      detects the foreground-blocking family:
      `session-start`, Windows open-with, Codex/Electron
      `Error launching app`, `Unable to find Electron app`,
      `Cannot find module`, `AttachConsole failed`, and
      `?type=click&tag=...`
    - `MajorScenarioRealNoLossReport` now exposes
      `system_dialog_preflight`, `system_dialog_preflight_failed`, and a
      `subreports.system_dialog_preflight` artifact section
    - if the preflight fails, the major runner short-circuits before invoking
      any child runner; primary/app/CLI/helper attempts remain zero
  - validation:
    - added tests for the standalone preflight detector and the top-level
      major-runner short-circuit contract
    - passed:
      `python -m unittest tests.test_desktop_system_dialog_preflight
      tests.test_major_real_no_loss` with `50` tests
    - passed wider regression:
      `python -m unittest tests.test_desktop_system_dialog_preflight
      tests.test_app_resolution tests.test_agent_surface_report
      tests.test_agent_task_runner tests.test_agent_cli_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract
      tests.test_agent_native_connector_probe tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix tests.test_codex_app_server_bridge
      tests.test_primary_real_no_loss` with `230` tests
    - real read-only preflight on the current desktop returned
      `system_dialog_clear`, `system_dialog_count=0`,
      `control_attempts=0`, `window_input_attempts=0`,
      `native_call_attempts=0`
    - R166:
      `logs/runtime/major-r166-20260602-system-dialog-preflight/report.json`
      ran a default major no-loss probe with no send/launch permissions:
      `safe_run_ok=true`, `system_dialog_preflight=system_dialog_clear`,
      `background_screenshot_success_count=3/3`,
      `background_screenshot_focus_stable=true`,
      `control_attempts=0`, `window_input_attempts=0`,
      `bridge_send_attempts=0`, `agent_command_attempts=0`
  - current conclusion:
    - the harness now protects the whole major validation path from existing
      Windows/Codex protocol error dialogs before any desktop automation
      sub-runner starts
    - the overall goal is still incomplete: R166 still reports unmet
      requirements for WeChat background send, browser background research,
      Codex/Claude/Cursor CLI background tasks, and Codex/Claude/Cursor app
      background chat
  - next concrete actions:
    1. wire the same preflight report into `primary_real_no_loss` if it is
       run standalone outside `major_real_no_loss`
    2. continue closing the largest remaining verified gap: background agent
       task execution through Codex CLI / Claude CLI / Cursor Agent CLI or
       native/extension connectors
    3. keep real sends behind explicit opt-in and require preflight clear,
       target identity, semantic/native endpoint, and readback markers
- 2026-06-02 standalone primary system-dialog preflight and tighter dialog
  scanning:
  - trigger:
    - another user-visible Codex WindowsApps/Electron dialog appeared:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - a direct real preflight scan later returned `system_dialog_clear`
      because the dialog was no longer visible/enumerable at scan time; a
      narrow read-only top-level scan for `Error` / `#32770` also found no
      active dialog
  - root cause update:
    - the previously added hard gate protected `major_real_no_loss`, but
      standalone `primary_real_no_loss` could still be run without the same
      preflight
    - the dialog scanner also needed a privacy/safety tightening: child text
      should only be read for likely system-dialog candidates, not for every
      visible top-level user window
  - implementation:
    - `primary_real_no_loss` now runs
      `run_desktop_system_dialog_preflight` before L1 replay, owned browser
      helper checks, WeChat probes, Word COM probes, IDE bridge probes, or
      Computer Use probes
    - on preflight failure it returns immediately with zero control/window/
      external/owned-launch attempts and exposes
      `system_dialog_preflight_failed` plus the preflight report in both full
      and summary outputs
    - `major_real_no_loss` now passes its already-recorded preflight report
      into the primary runner, so the combined report remains deterministic
      while standalone primary still has its own default real preflight
    - `desktop_system_dialog` now avoids broad child-text reads; it probes
      child text only for likely dialog candidates such as `Error`, `#32770`,
      `session-start`, open-with titles, or explicit Codex/Electron protocol
      evidence
    - generic `title=Error` WindowsApps windows without Codex/OpenAI/Electron
      evidence are no longer treated as this specific Codex popup family
    - updated the global `desktop-background-control-testing` skill with the
      reusable rule: if a user reports a visible dialog but preflight returns
      clear, first verify same desktop/session with a narrow top-level scan
      and avoid broad user-window child text dumps
  - official-doc basis:
    - Microsoft `EnumWindows` documentation confirms it enumerates top-level
      windows and is more reliable than looping with `GetWindow`
    - Microsoft `GetWindowTextW` documentation notes cross-process control
      text limitations, which explains why child dialog text should be
      handled separately and only for candidates
    - Microsoft `SendMessageTimeoutW` / `WM_GETTEXT` documentation supports a
      bounded fallback for already-identified candidate dialog child text
  - validation:
    - new RED/GREEN coverage:
      - standalone primary stops before any scenario work when system-dialog
        preflight fails
      - major passes its existing preflight report into primary instead of
        letting primary touch the real desktop again
      - ordinary WindowsApps/Notepad `Error` does not get classified as a
        Codex dialog
      - child text probing is limited to likely system-dialog candidates
    - passed targeted suites:
      `python -m unittest tests.test_desktop_system_dialog_preflight
      tests.test_primary_real_no_loss tests.test_major_real_no_loss` with
      `62` tests
    - passed Codex/app regression:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_agent_app_real_no_loss` with `51` tests
    - passed wide regression:
      `python -m unittest tests.test_desktop_system_dialog_preflight
      tests.test_app_resolution tests.test_agent_surface_report
      tests.test_agent_task_runner tests.test_agent_cli_real_no_loss
      tests.test_agent_app_real_no_loss tests.test_agent_app_transport_matrix
      tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract
      tests.test_agent_native_connector_probe tests.test_major_real_no_loss
      tests.test_objective_readiness_matrix tests.test_codex_app_server_bridge
      tests.test_primary_real_no_loss` with `234` tests
    - real read-only preflight currently returns `system_dialog_clear`,
      `system_dialog_count=0`, `control_attempts=0`,
      `window_input_attempts=0`, and `native_call_attempts=0`
    - R168:
      `logs/runtime/primary-r168-20260602-system-dialog-preflight-tightened`
      ran standalone primary no-loss with no send/keyboard/mouse/clipboard:
      `system_dialog_preflight_failed=false`, `passed_cases=5/5`,
      `failed_cases=0`, `real_verified_cases=3`,
      `control_attempts=0`, `external_communication_attempts=0`,
      `window_input_attempts=0`, and `owned_app_launch_attempts=0`
  - current conclusion:
    - the reported popup is still the known blocked Codex WindowsApps/MSIX
      Electron-shell route, not a failure of the connector-first architecture
    - both major and standalone primary no-loss entries now have a preflight
      hard gate before any desktop automation subrunner starts
    - the overall objective remains incomplete: browser/Codex in the R168
      standalone run were not verified because owned browser helper and IDE/
      native bridge were not enabled, and agent app/CLI background task gaps
      still need deterministic connector/CLI routes
  - next concrete actions:
    1. identify the exact route that is still activating the Codex
       WindowsApps desktop shell and route it permanently to standalone Codex
       CLI or a proven native/extension connector
    2. continue background-safe agent task execution validation for Codex CLI,
       Claude CLI, and Cursor Agent CLI/native bridges
    3. keep all real sends/actions behind explicit opt-in plus preflight
       clear, target identity, native/semantic endpoint, no-focus evidence,
       and readback markers
- 2026-06-02 Codex CLI real background probe and CLI system-dialog guard:
  - trigger:
    - another user-visible Codex WindowsApps/Electron popup appeared with
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - immediate read-only preflight and narrow Codex/Error process scan did
      not find an active top-level dialog, so the popup was either already
      closed, transient, or outside the current enumerable top-level window
      set
  - root cause update:
    - the latest real Codex CLI no-loss probe selected the standalone CLI at
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\...\codex.exe`,
      not the WindowsApps desktop shell
    - the standalone `agent_cli_real_no_loss` runner still lacked its own
      system-dialog preflight/postflight gate, so a delayed or pre-existing
      Codex/Electron dialog could have been missed even when the CLI returned
      the acceptance marker
  - implementation:
    - `agent_cli_real_no_loss` now samples
      `run_desktop_system_dialog_preflight` before and after each CLI case
    - pre-existing system dialogs produce
      `system_dialog_detected_preflight`, skip the agent command, and keep
      `agent_command_attempts=0`
    - post-command system dialogs produce
      `system_dialog_detected_postflight`, overriding any successful CLI
      acceptance marker
    - CLI case/report JSON now exposes
      `system_dialog_detected`, `system_dialog_preflight_failed`,
      `system_dialog_postflight_failed`, `system_dialog_preflight`, and
      `system_dialog_postflight`
  - validation:
    - added RED/GREEN coverage for:
      - pre-existing Codex MSIX/Electron `?type=click&tag=...` dialogs
        blocking CLI execution before any command attempt
      - delayed JavaScript/`AttachConsole failed` dialogs overriding a
        successful CLI marker after command execution
    - passed:
      `python -m unittest tests.test_agent_cli_real_no_loss` with `12` tests
    - passed related regression:
      `python -m unittest tests.test_agent_cli_real_no_loss
      tests.test_major_real_no_loss tests.test_objective_readiness_matrix
      tests.test_agent_task_runner tests.test_agent_surface_report` with
      `80` tests
    - passed system-dialog/major regression:
      `python -m unittest tests.test_desktop_system_dialog_preflight
      tests.test_agent_cli_real_no_loss tests.test_major_real_no_loss` with
      `65` tests
    - `git diff --check` passed with only existing LF-to-CRLF warnings
    - R171:
      `logs/runtime/agent-cli-r171-20260602-codex-cli-system-dialog-guard`
      ran a real Codex CLI background no-loss probe:
      `status=verified`, `verified_cases=1/1`,
      `selected_transport=codex-cli-managed-terminal`,
      `window_input_attempts=0`, `workspace_clean=true`,
      `system_dialog_preflight_failed=false`, and
      `system_dialog_postflight_failed=false`
  - current conclusion:
    - Codex CLI is now a real verified background task route for the no-loss
      marker probe on this machine
    - the reported popup was not reproduced by the R171 Codex CLI route; if
      it appears again, the standalone CLI runner will now fail the run
      instead of silently accepting the marker
    - the remaining Codex risk is the WindowsApps desktop shell/protocol
      activation family, which must stay out of background task execution
      unless a native/extension connector proves foreground safety
  - next concrete actions:
    1. fold the verified Codex CLI route into the major readiness matrix with
       `--allow-agent-cli-execution`
    2. continue Claude CLI/app and Cursor Agent/native bridge validation under
       the same no-focus and system-dialog gates
    3. fix the separate Codex CLI skill-loading warnings for malformed global
       skill frontmatter so live CLI probes start cleaner
- 2026-06-02 R172 major matrix with owned browser helper and agent CLI:
  - validation:
    - ran:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs\runtime\major-r172-20260602-cli-owned-browser-guard
      --allow-agent-cli-execution --agent-cli-timeout-sec 120
      --allow-owned-browser-helper-launch --owned-browser-debug-port 9491 --json`
    - result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `external_communication_attempts=0`,
      `owned_app_launch_attempts=1`, and `agent_command_attempts=2`
    - verified ready requirements:
      `wechat_background_observation`, `word_background_document`,
      `browser_background_research`, `file_background_search`,
      and `codex_cli_background_task`
    - remaining unsatisfied requirements:
      `wechat_background_send`, `claude_cli_background_task`,
      `cursor_cli_background_task`, `codex_app_background_chat`,
      `claude_desktop_background_chat`, and `cursor_background_chat`
    - no owned browser helper residue remained after cleanup
  - conclusion:
    - the background-safe architecture is working for connector/native paths
      and Codex CLI, but app chat surfaces still need native/extension
      session identity plus no-focus send/readback before being called
      complete
- 2026-06-02 hard block for Codex/Claude WindowsApps MSIX agent app launch:
  - trigger:
    - another real Codex popup appeared:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
  - root cause:
    - `session_readiness_plan` still allowed the
      `agent-app-devtools-owned` route to append DevTools/Electron flags to
      any `agent_app_executable`
    - when the executable came from
      `C:\Program Files\WindowsApps\OpenAI.Codex...\app\Codex.exe`, that
      MSIX desktop shell could be launched like a normal Electron helper and
      produce visible foreground error dialogs
    - Microsoft docs support treating Store/MSIX apps as AUMID/AppID/URI
      activated surfaces rather than ordinary background helper executables
  - implementation:
    - `SessionReadinessAction` now carries `blocked_reason`
    - `execute_session_readiness_plan` rejects any action with
      `blocked_reason` before preparing profiles or calling the launcher
    - `agent-app-devtools-owned` now returns
      `block_agent_app_devtools_owned_msix` with
      `windowsapps_msix_executable_not_background_launchable` when the target
      executable is under `Program Files\WindowsApps`
    - the blocked action has empty `argv`, empty `command`,
      `launch_attempts=0`, and `foreground_required=true`
  - validation:
    - RED/GREEN test added:
      `test_agent_app_devtools_owned_plan_blocks_windowsapps_msix_executable`
    - passed:
      `python -m unittest tests.test_session_readiness_plan` with `31` tests
    - passed related regression:
      `python -m unittest tests.test_session_readiness_plan
      tests.test_major_real_no_loss tests.test_desktop_system_dialog_preflight
      tests.test_codex_app_server_bridge tests.test_agent_app_real_no_loss`
      with `135` tests
    - real no-loss verification with the actual current Codex WindowsApps
      path returned `launch_attempts=0`, `status=rejected`, `argv=[]`, and
      `error=windowsapps_msix_executable_not_background_launchable`
    - real read-only desktop system-dialog preflight returned
      `system_dialog_clear`, `system_dialog_count=0`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `native_call_attempts=0`
    - `git diff --check` passed with only existing LF-to-CRLF warnings
  - current conclusion:
    - this popup family now has defense in depth:
      system-dialog preflight/postflight catches visible dialogs, and the
      lowest launch-planning layer refuses to launch MSIX agent app shells as
      background DevTools helpers
    - Codex background execution should continue through the standalone
      Codex CLI or a proven native/extension connector; the WindowsApps
      desktop shell remains evidence/foreground-only unless it exposes a
      verified safe native endpoint
  - next concrete actions:
    1. continue closing app-surface gaps through native/extension bridge
       readiness instead of owned MSIX app launches
    2. fix Claude Desktop UIA process-name normalization so visible
       `claude` windows are not misreported as absent
    3. keep all agent app `turn/start` execution behind explicit
       no-focus/readback gates
- 2026-06-03 Claude Desktop app window detection hardening:
  - trigger:
    - R172/R174-style Claude app probes reported
      `agent_app_window_not_found` even though real `Get-Process` showed a
      visible Claude main window
    - real evidence on this machine:
      PID `42028`, `ProcessName=claude`, `MainWindowTitle=Claude`,
      `MainWindowHandle=855894`
  - root cause:
    - `agent_app_uia_probe` matched agent windows only against process names
      such as `claude.exe`
    - Windows/.NET/PowerShell process views can expose `ProcessName=claude`
      without the `.exe` suffix
    - the live UIA top-level scan could also omit the Claude window entirely
      even when Win32 top-level enumeration saw the HWND
  - implementation:
    - `agent_app_uia_probe` now normalizes process-name aliases so
      `codex/codex.exe`, `claude/claude.exe`, and `cursor/cursor.exe`
      all match the same agent surface
    - `accessibility_probe` now merges a read-only Win32 top-level-window
      fallback into the UIA window list
    - the Win32 fallback records only top-level HWND, title, class name, PID,
      and process name; it does not enumerate child controls, click, type, or
      invoke anything
    - duplicate suppression uses HWND first, then PID+title
  - validation:
    - added RED/GREEN coverage:
      - `test_claude_desktop_process_name_without_exe_matches_window`
      - `test_win32_fallback_adds_top_level_window_missing_from_uia`
    - passed:
      `python -m unittest tests.test_accessibility_probe
      tests.test_agent_app_uia_probe` with `18` tests
    - passed related regression:
      `python -m unittest tests.test_accessibility_probe
      tests.test_agent_app_uia_probe tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss` with `95` tests
    - real R175:
      `logs/runtime/claude-uia-r175-20260603-win32-fallback-process-name-normalized.json`
      changed Claude Desktop from `agent_app_window_not_found` to
      `agent_app_uia_target_visible_input_not_found`,
      `matched_window_count=1`, `matched pid=42028`,
      `matched hwnd=855894`, and `control_attempts=0`
    - real R176:
      `logs/runtime/claude-uia-r176-20260603-win32-fallback-background-capture.json`
      kept foreground stable while attempting HWND capture, but
      `PrintWindow` returned `print_window_failed`;
      this is provider negative evidence, not permission to use focus or
      vision as the primary control channel
    - real system-dialog preflight before the probe was
      `system_dialog_clear`, with zero control/window/native attempts
    - `git diff --check` passed with only existing LF-to-CRLF warnings
  - current conclusion:
    - Claude Desktop is now correctly classified as a visible app surface
      rather than absent
    - Claude Desktop remains not background-send-ready: no native bridge,
      no semantic composer, and current `PrintWindow` capture failed while
      preserving focus
  - next concrete actions:
    1. add a stronger no-focus background capture fallback for Electron/MSIX
       app windows where `PrintWindow` fails
    2. continue app-surface readiness through native/extension bridges rather
       than UIA writes
    3. rerun the major readiness matrix so
       `claude_desktop_background_chat` moves from `unavailable` to
       visible/gated with explicit blocking evidence
- 2026-06-03 R177 major readiness rerun after Claude visibility hardening:
  - validation:
    - ran:
      `python -m openwukong.evaluation.major_real_no_loss
      --output-root logs\runtime\major-r177-20260603-claude-visible-gated
      --allow-agent-cli-execution --agent-cli-timeout-sec 120
      --allow-owned-browser-helper-launch --owned-browser-debug-port 9492 --json`
    - result:
      `safe_run_ok=true`, `goal_complete=false`, `control_attempts=0`,
      `window_input_attempts=0`, `external_communication_attempts=0`,
      `owned_app_launch_attempts=1`, `agent_command_attempts=2`,
      `background_screenshot_count=5`,
      `background_screenshot_success_count=4`,
      `background_screenshot_focus_stable=true`, and
      `system_dialog_preflight_failed=false`
    - objective readiness summary:
      `requirement_count=11`, `satisfied_count=4`, `gated_count=1`,
      `auth_required_count=1`, `unavailable_count=5`, `failed_count=0`,
      `background_execute_ready_count=4`,
      `background_write_ready_count=2`
    - verified requirements in this environment:
      `browser_background_research`, `word_background_document`,
      `file_background_search`, and `codex_cli_background_task`
    - current unsatisfied requirements:
      `wechat_background_observation`, `wechat_background_send`,
      `claude_cli_background_task`, `cursor_cli_background_task`,
      `codex_app_background_chat`, `claude_desktop_background_chat`,
      and `cursor_background_chat`
    - Claude Desktop matrix status:
      `claude_desktop_background_chat` remains unsatisfied, but the
      blocking reason is now `target_project_not_visible`; the independent
      R175/R176 probes proved the Claude window itself is visible
    - current desktop caveat:
      WeChat was not visible/enumerable in this R177 run, so
      `wechat_background_observation` was `unavailable`; this is environment
      presence, not a regression of the previously verified WeChat route
  - current conclusion:
    - the main architecture remains correct: connector/native routes are
      stable, CLI routes can run in the background, and app surfaces are now
      being classified more precisely instead of guessed through vision
    - the full goal is still not complete because app chat surfaces need
      native/extension bridge readiness and Claude/Cursor CLI or app-side
      execution still lacks verified no-focus send/readback
  - next concrete actions:
    1. implement a no-focus background capture fallback for Electron/MSIX
       windows where `PrintWindow` fails
    2. rerun WeChat read-only/send validation only when the personal WeChat
       window is present and target identity can be proven
    3. continue agent app background task submission through native/extension
       connectors, not foreground UIA typing
- 2026-06-03 Codex MSIX/Electron `type=click&tag` action-layer hardening:
  - trigger:
    - another user-visible Codex popup appeared:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - immediate read-only system-dialog preflight was clear, so the dialog
      was already closed/transient or outside the current enumerable dialog
      set
  - why earlier rounds did not fully solve it:
    - launch-layer hardening correctly blocked
      `agent-app-devtools-owned` from treating WindowsApps/MSIX Codex as a
      background-launchable Electron helper
    - CLI-layer hardening correctly guarded standalone Codex CLI probes with
      preflight/postflight dialog checks
    - the remaining gap was action/protocol-layer: a Codex Desktop app-server
      endpoint could still self-report `turn_start_foreground_safe=true`,
      allowing `turn/start` to be treated as background-safe even when the
      endpoint identity was `surface_kind=desktop_app`
    - that gap matches the observed `type=click&tag` family, which is a
      desktop/protocol activation risk rather than a normal hidden CLI route
  - official-doc basis:
    - Microsoft packaged/MSIX apps can receive protocol/URI activation through
      their package manifest, and URI/query parameters are passed to the app
      activation handler
    - this supports treating WindowsApps/MSIX protocol/deep-link activation
      as a foreground-prone app surface, not a normal background helper path
  - implementation:
    - `CodexAppServerTurnRequest.turn_start_foreground_safe` now treats
      `surface_kind=desktop_app` or `Codex Desktop` user-agent evidence as a
      forced block
    - forced desktop-shell evidence overrides any
      `turn_start_foreground_safe=true` metadata
    - endpoint summaries and payload diagnostics now preserve
      `windows_desktop_app_server_turn_start_foreground_risk` for this case
  - validation:
    - added RED/GREEN coverage:
      `test_turn_dry_run_blocks_windows_desktop_endpoint_even_when_marked_safe`
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge` with `24`
      tests
    - passed related regression:
      `python -m unittest tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss` with `77` tests
    - real read-only system-dialog preflight returned `system_dialog_clear`,
      `system_dialog_count=0`, `control_attempts=0`,
      `window_input_attempts=0`, and `native_call_attempts=0`
    - real R178:
      `logs/runtime/agent-app-r178-20260603-codex-msix-popup-guard`
      ran Codex app no-loss with `--allow-codex-app-server-turn-start` but
      no safe endpoint contract:
      `passed_cases=1/1`, `control_attempts=0`,
      `window_input_attempts=0`, `bridge_send_attempts=0`,
      `agent_command_attempts=0`,
      `codex_app_server_turn_start_attempts=0`, and
      `codex_app_server_native_call_attempts=0`
  - current conclusion:
    - the repeated popup family is now guarded at three layers:
      system-dialog pre/postflight, launch-plan MSIX blocking, and
      Codex app-server `turn/start` action-layer blocking
    - Codex Desktop remains foreground/native-bridge-required for app chat;
      background task execution should use standalone Codex CLI or a proven
      native/extension connector, not WindowsApps desktop-shell `turn/start`
  - next concrete actions:
    1. keep Codex Desktop app-server `thread/start` and `turn/start` as
       separate layers; only thread/session creation can be considered after
       no-focus evidence
    2. implement the no-focus background capture fallback for Electron/MSIX
       windows where `PrintWindow` fails
    3. continue agent app background task submission through native/extension
       connectors with readback markers
- 2026-06-03 R179 Codex Windows app-server safe-flag bypass hardening:
  - trigger:
    - another visible Codex/Electron dialog was reported:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - read-only `desktop_system_dialog` preflight immediately after the
      report was `system_dialog_clear`, so the dialog was transient/closed,
      but the screenshot is still treated as real blocking evidence
  - root cause found:
    - the prior hardening forced `turn/start` blocked for
      `surface_kind=desktop_app` and `Codex Desktop` user-agent evidence
    - a remaining bypass existed when a Codex app-server endpoint reported
      `platform_os=windows` and `turn_start_foreground_safe=true` while its
      `surface_kind` looked headless
    - in that case the dry-run incorrectly became
      `codex_app_server_turn_dry_run_ready`, which could allow a real
      `turn/start` action to enter the same WindowsApps/MSIX protocol
      activation family
  - official-doc basis:
    - Microsoft URI/protocol activation docs confirm packaged apps receive
      URI activation through the package manifest and can handle query
      parameters
    - Microsoft packaged-app activation docs confirm packaged desktop apps
      can retrieve protocol/click activation information
    - this supports treating Windows Codex app-server `turn/start` self
      reports as insufficient safety evidence
  - implementation:
    - `CodexAppServerTurnRequest.turn_start_foreground_safe` now force-blocks
      `platform_os=windows` for Codex app-server `turn/start`
    - endpoint summaries now report the effective safe flag, not only the raw
      metadata value
    - metadata path/URI fields containing `WindowsApps`, `OpenAI.Codex`, or
      `type=click&tag` are treated as forced foreground-risk evidence
    - `PrintWindowBackgroundCaptureProvider` has a no-focus
      `screen-bounds-bitblt-fallback` path for Electron/MSIX windows where
      `PrintWindow` fails; the fallback is explicitly labeled and is not
      treated as occlusion-proof
  - validation:
    - added RED/GREEN coverage:
      `test_turn_dry_run_blocks_windows_endpoint_even_when_marked_safe`
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge` with `25`
      tests
    - passed:
      `python -m unittest tests.test_window_capture
      tests.test_agent_app_real_no_loss tests.test_major_real_no_loss
      tests.test_codex_app_server_bridge` with `103` tests
    - real read-only system-dialog preflight after the fix returned
      `system_dialog_clear`, `system_dialog_count=0`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `native_call_attempts=0`
  - current conclusion:
    - Codex app-server `turn/start` on Windows must remain blocked for
      background/no-focus execution even if the endpoint self-reports
      foreground safety
    - Codex background project task execution should continue through
      standalone Codex CLI or a future native/extension connector with
      independent no-focus readback evidence
  - next concrete actions:
    1. keep all real Codex app `turn/start` execution disabled on Windows
       app-server endpoints until an independent native/extension connector
       proves no foreground activation
    2. use the new BitBlt fallback only as visual verification evidence, not
       as a control primitive
    3. continue no-loss validation for WeChat, Browser, Word, file search,
       Codex CLI, and Claude/Cursor app surfaces with explicit background
       gates
- 2026-06-03 R181 WeChat native bridge registry discovery:
  - trigger:
    - R180 real no-loss matrix showed WeChat observation is now verified, but
      `wechat_background_send` remains gated by
      `wechat_native_bridge_url_missing`
    - this means the missing piece is not window recognition; it is automatic
      local native bridge endpoint discovery
  - implementation:
    - added `openwukong.control.wechat_native_bridge_registry`
    - supported explicit URLs, `OPENWUKONG_WECHAT_NATIVE_BRIDGE_URLS`,
      `OPENWUKONG_WECHAT_NATIVE_BRIDGE_REGISTRY_PATHS`, and default local
      registry paths:
      `%LOCALAPPDATA%\OpenWukong\wechat-native-bridges.json` and
      `%PROGRAMDATA%\OpenWukong\wechat-native-bridges.json`
    - registry discovery accepts only loopback/local URLs, filters disabled
      entries and non-WeChat bridge types, and never launches GUI apps
    - `primary_real_no_loss` now resolves effective WeChat native bridge URLs
      before building dry-run requests
    - `major_real_no_loss` now forwards WeChat native bridge registry paths
      to primary and exposes CLI `--wechat-native-bridge-registry`
    - updated global skill `desktop-background-control-testing` with the
      reusable rule: bridge URL missing should first check read-only
      local registry/env discovery before the route is classified absent
  - official-doc basis:
    - Python `os.environ` docs confirm environment variables are represented
      as a mapping and can be queried safely from process state
    - Python `json` and `pathlib` docs were checked for standard-library
      JSON registry loading and path handling
  - validation:
    - added tests:
      `tests.test_wechat_native_bridge_registry`,
      `test_runner_discovers_wechat_native_bridge_url_from_registry_file`,
      and
      `test_runner_passes_wechat_native_bridge_registry_paths_to_primary_runner`
    - passed targeted tests: `4` tests OK
    - passed related regression:
      `python -m unittest tests.test_wechat_native_bridge
      tests.test_wechat_native_bridge_registry tests.test_primary_real_no_loss
      tests.test_major_real_no_loss` with `66` tests OK
    - real R181:
      `logs/runtime/major-r181-20260603-wechat-bridge-registry`
      returned `safe_run_ok=true`, `goal_complete=false`,
      `control_attempts=0`, `window_input_attempts=0`,
      `agent_command_attempts=2`, `background_screenshot_count=6`,
      `background_screenshot_success_count=6`, and
      `background_screenshot_focus_stable=true`
    - R181 verified:
      `wechat_background_observation`, `word_background_document`,
      `browser_background_research`, `file_background_search`, and
      `codex_cli_background_task`
    - R181 remaining unsatisfied:
      `wechat_background_send`, `claude_cli_background_task`,
      `cursor_cli_background_task`, `codex_app_background_chat`,
      `claude_desktop_background_chat`, and `cursor_background_chat`
    - R181 WeChat send is still gated on this machine because no WeChat
      native bridge registry file or URL is currently installed
  - current conclusion:
    - current machine can precisely observe WeChat in the background and can
      use a WeChat native bridge automatically once it is installed and
      registered
    - the product has moved closer to a unified solution because native
      bridge discovery is no longer hand-wired per run
    - full goal remains incomplete: app-side chat for WeChat/Codex/Claude/
      Cursor still requires installed native/extension bridges or auth
  - next concrete actions:
    1. add an owned/local WeChat bridge fixture smoke so the registry route
       can be exercised end-to-end without touching personal chats
    2. continue Claude/Cursor app-surface readiness through native/extension
       bridges, not foreground UIA typing
    3. keep real WeChat sends behind explicit native bridge readiness and
       target/readback markers
- 2026-06-03 R182 Codex WindowsApps `thread/start` foreground-risk block:
  - trigger:
    - user reported another visible Codex/Electron popup:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - immediate read-only system-dialog scan was clear, so the dialog had
      already been dismissed or was transient, but the screenshot is treated
      as real foreground-blocking evidence
  - why earlier rounds did not fully solve it:
    - previous fixes blocked Codex Windows app-server `turn/start` when the
      endpoint reported Windows/Desktop/MSIX/protocol activation risk
    - the remaining gap was the staged `thread/start` path: it was considered
      session-safe and could still make a real app-server client request when
      the endpoint identity looked like `headless_app_server`
    - on this machine, Codex exposes both standalone app-server processes and
      WindowsApps/MSIX Codex app-server evidence; the WindowsApps endpoint
      family can still route into the desktop shell/protocol activation path
  - official-doc basis:
    - Microsoft Windows packaged/MSIX apps support manifest/protocol URI
      activation and receive activation/query parameters through the app
      activation handler
    - therefore `type=click&tag` evidence must be treated as desktop
      activation risk, not a normal background helper argument
  - implementation:
    - `CodexAppServerThreadStartExecutionReport` now exposes
      `thread_start_block_reason`
    - endpoint summaries now include a separate
      `thread_start_block_reason`
    - real `CodexAppServerThreadStartAdapter.start()` short-circuits before
      any client request when endpoint metadata contains WindowsApps/MSIX
      Codex desktop package evidence, `Codex Desktop` user-agent evidence, or
      protocol activation markers such as `type=click&tag`
    - updated global skill `desktop-background-control-testing` with this
      reusable rule
  - validation:
    - added RED/GREEN regression:
      `test_thread_start_executor_blocks_windowsapps_codex_activation_risk`
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge` with `26`
      tests OK
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss` with `78` tests OK
    - read-only postflight system-dialog scan returned
      `system_dialog_clear`, `system_dialog_count=0`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `native_call_attempts=0`
    - `git diff --check` returned exit code `0`; only existing LF/CRLF
      warnings were printed
  - current conclusion:
    - Codex WindowsApps/MSIX desktop package endpoints are now blocked for
      both real `thread/start` and real `turn/start`
    - background Codex task execution should use standalone Codex CLI,
      non-MSIX helper app-server, or a proven native connector with
      no-focus readback; WindowsApps/MSIX Codex desktop shell remains a
      foreground-risk surface
  - next concrete actions:
    1. continue the owned/local WeChat native bridge fixture smoke
    2. keep Codex app-side real chat behind non-MSIX/native connector
       readiness, not WindowsApps desktop-shell activation
    3. continue Claude/Cursor app-surface readiness through native/extension
       bridges with the same foreground-risk gate
- 2026-06-03 R183 WeChat native bridge fixture smoke integrated into major
  no-loss:
  - trigger:
    - R181 proved WeChat background observation and registry discovery, but
      the main major runner still could not exercise the full registry ->
      native bridge -> send/readback path without touching personal chats
  - implementation:
    - `major_real_no_loss` now imports the owned local WeChat native bridge
      fixture smoke runner
    - `MajorScenarioRealNoLossReport` now includes
      `wechat_native_bridge_fixture_smoke_report`,
      `wechat_native_bridge_fixture_smoke_enabled`,
      `wechat_native_bridge_fixture_smoke_ok`,
      `wechat_native_bridge_fixture_control_attempts`, and
      `wechat_native_bridge_fixture_native_call_attempts`
    - the major safe gate now fails if an enabled WeChat fixture smoke fails
    - the report and subreports now preserve
      `wechat_native_bridge_fixture_smoke`
    - CLI now exposes:
      `--run-wechat-native-bridge-fixture-smoke`,
      `--wechat-native-bridge-fixture-message`,
      `--wechat-native-bridge-fixture-acceptance-marker`, and
      `--wechat-native-bridge-fixture-forbid-marker`
  - official-doc basis:
    - Python `http.server.ThreadingHTTPServer` docs confirm the local owned
      fixture can use threaded request handling for loopback bridge requests
    - Python `argparse` docs confirm repeated marker flags can use
      `action="append"`
    - Python `dataclasses` docs were checked for the report field extension
      pattern
  - validation:
    - added RED/GREEN major runner tests:
      `test_runner_can_verify_wechat_native_bridge_fixture_smoke_without_window_input`,
      `test_wechat_native_bridge_fixture_smoke_failure_fails_safe_gate`, and
      `test_cli_forwards_wechat_native_bridge_fixture_smoke_options`
    - passed targeted tests:
      the three new tests OK
    - passed independent fixture tests:
      `python -m unittest tests.test_wechat_native_bridge_fixture_smoke`
      with `2` tests OK
    - passed related regression:
      `python -m unittest tests.test_wechat_native_bridge
      tests.test_wechat_native_bridge_registry tests.test_primary_real_no_loss
      tests.test_major_real_no_loss` with `69` tests OK
    - real R183:
      `logs/runtime/major-r183-20260603-wechat-fixture-smoke`
      returned `safe_run_ok=true`, `goal_complete=false`,
      `failed_runner_count=0`, `control_attempts=0`,
      `window_input_attempts=0`, `agent_command_attempts=2`,
      `background_screenshot_count=6`,
      `background_screenshot_success_count=6`,
      `background_screenshot_focus_stable=true`,
      `wechat_native_bridge_fixture_smoke_enabled=true`,
      `wechat_native_bridge_fixture_smoke_ok=true`, and
      `wechat_native_bridge_fixture_native_call_attempts=1`
    - R183 WeChat fixture evidence:
      local registry discovered `http://127.0.0.1:<port>`,
      fixture saw one capability request and one send request,
      send report was `wechat_native_bridge_send_accepted`, and
      missing/forbidden readback marker lists were empty
    - postflight system-dialog scan returned `system_dialog_clear`,
      `system_dialog_count=0`, `control_attempts=0`,
      `window_input_attempts=0`, and `native_call_attempts=0`
    - final `git diff --check` returned exit code `0`; only existing LF/CRLF
      warnings were printed
  - current conclusion:
    - the major runner now proves the generic WeChat native bridge route
      end-to-end without affecting real WeChat chats
    - this does not mark real personal WeChat send complete; real send still
      requires an installed trusted native bridge registry/URL and explicit
      target/readback markers
  - next concrete actions:
    1. install or implement the real WeChat native bridge adapter behind the
       same registry contract, then rerun a file-helper-only send with
       explicit markers
    2. continue Claude/Cursor app-surface readiness through native/extension
       bridges with no-focus screenshots and readback markers
    3. keep Codex app-side real chat behind non-MSIX/native connector
       readiness; standalone Codex CLI remains the verified background route
- 2026-06-03 R184 Codex CLI delayed WindowsApps/Electron popup hardening:
  - trigger:
    - user reported another visible Codex/Electron dialog:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\?type=click&tag=...`,
      and `Cannot find module`
    - current read-only desktop scan was clear, so the specific dialog had
      already been dismissed or was transient; the screenshot is still
      treated as real foreground-blocking evidence
  - root cause evidence:
    - R183 did use the standalone Codex CLI path:
      `C:\Users\Zhangjinqian\AppData\Local\OpenAI\Codex\bin\716dda49c14d31a0\codex.exe`
      and not a WindowsApps executable for the top-level command
    - however that Codex CLI run internally attempted PowerShell tool calls
      and stderr contained `windows sandbox: spawn setup refresh`
    - the previous CLI acceptance logic trusted the required PASS marker too
      much and only ran an immediate postflight system-dialog scan, so it
      could miss delayed MSIX/Electron popups and still mark the CLI route as
      verified
  - official-doc basis:
    - Microsoft packaged/MSIX apps support URI/protocol activation and can
      receive query parameters through activation handling, so
      `type=click&tag` remains desktop activation risk evidence
    - Python `time` docs were checked for using monotonic elapsed-time
      polling and short sleeps in the delayed postflight scan
  - implementation:
    - `agent_cli_real_no_loss` now accepts
      `system_dialog_postflight_poll_sec`
    - real command runs default to a short delayed postflight system-dialog
      polling window; fake/unit command executors keep zero delay by default
    - CLI stdout/stderr/error evidence now hard-fails the case as
      `cli_runtime_foreground_risk` when it contains:
      `windows sandbox: spawn setup refresh`, `Error launching app`,
      `Unable to find Electron app`, `AttachConsole failed`,
      `?type=click`, `type=click&tag`, or WindowsApps OpenAI Codex paths
    - the no-loss CLI prompt now explicitly forbids file inspection and shell
      command/tool execution, but this is treated as secondary guidance; the
      hard gate is still evidence-based
    - updated global skill `desktop-background-control-testing` with the
      reusable pattern: PASS markers cannot mask delayed Codex/MSIX dialogs
      or CLI stderr/stdout foreground-risk evidence
  - validation:
    - added RED/GREEN regressions:
      `test_delayed_post_cli_system_dialog_overrides_success_marker` and
      `test_codex_cli_sandbox_spawn_setup_refresh_is_not_verified`
    - passed `python -m unittest tests.test_agent_cli_real_no_loss` with
      `14` tests OK
    - passed `python -m unittest tests.test_major_real_no_loss` with
      `53` tests OK
    - passed `python -m unittest tests.test_codex_app_server_bridge` with
      `26` tests OK
    - passed `python -m unittest tests.test_desktop_system_dialog_preflight`
      with `4` tests OK
    - passed `python -m unittest tests.test_agent_app_real_no_loss` with
      `28` tests OK
    - current read-only system-dialog preflight returned
      `system_dialog_clear`, `system_dialog_count=0`, `control_attempts=0`,
      `window_input_attempts=0`, and `native_call_attempts=0`
    - `git diff --check` returned exit code `0`; only existing LF/CRLF
      warnings were printed
  - current conclusion:
    - the Codex desktop/MSIX surface remains blocked for background app-side
      chat
    - standalone Codex CLI is still a possible background transport, but it
      can no longer be considered verified when its internal runtime emits
      sandbox/MSIX/Electron foreground-risk evidence
    - full goal remains incomplete until Codex app-side execution uses a
      proven non-MSIX/native connector or a CLI mode that can avoid internal
      desktop/sandbox foreground activation
  - next concrete actions:
    1. rerun the major no-loss matrix without real Codex CLI execution, or
       with the new CLI runtime-risk gate if the user explicitly allows it
    2. continue WeChat real file-helper send only through native bridge/UIA
       semantic gates with explicit target/readback markers
    3. prioritize non-MSIX/native connectors for Codex/Claude/Cursor app chat
       before any further foreground-risk real sends
- 2026-06-03 R189 Codex WindowsApps app-server probe owner guard:
  - trigger:
    - user reported another visible Codex/Electron dialog:
      `Error launching app`, `Unable to find Electron app at
      C:\Program Files\WindowsApps\OpenAI.Codex_26.527...\type=click&tag=...`,
      and `Cannot find module`
    - current read-only system-dialog scan was clear, so the dialog had
      already been dismissed or was transient, but the screenshot is still
      treated as real foreground-blocking evidence
  - investigation:
    - R188 Cursor real UIA draft verification did not contain Codex,
      WindowsApps, `session-start`, or `type=click` evidence; it failed only
      as `uia_semantic_action_draft_value_not_verified`, with
      `control_attempts=0`, `window_input_attempts=0`, and focus stable
    - process scan showed both Codex Desktop/MSIX processes under
      `C:\Program Files\WindowsApps\OpenAI.Codex...` and standalone
      AppDataLocal/Cursor-extension `codex.exe app-server` processes
    - the current WindowsApps Codex app-server child had no TCP listening
      port, so this specific popup is most likely from Codex Desktop or its
      plugin/protocol activation path, not from the latest Cursor UIA draft
      test
  - official-doc basis:
    - Microsoft packaged/MSIX apps support URI/protocol activation through
      the package manifest and activation handler, so `type=click&tag`
      evidence is desktop activation risk
    - Electron command-line/application-path handling was checked; passing
      path/query-like activation evidence to the packaged shell can be
      interpreted as an app path and produce `Unable to find Electron app`
  - implementation:
    - `agent_native_connector_probe` now reports top-level
      `window_input_attempts=0`
    - explicit Codex app-server WebSocket probes now check the owning
      listening process before any `initialize`/`thread/list` RPC
    - if the port owner is WindowsApps/OpenAI.Codex or contains
      `type=click&tag`/`?type=click` activation evidence, the endpoint is
      recorded as `codex_app_server_windowsapps_probe_blocked`, with
      `probe_block_reason=windowsapps_codex_app_server_foreground_risk`,
      `commands=[]`, and no RPC call
    - updated global skill `desktop-background-control-testing` with this
      reusable owner-check rule
  - validation:
    - added RED/GREEN regression:
      `test_blocks_windowsapps_codex_app_server_ws_probe_before_rpc`
    - passed:
      `python -m unittest tests.test_agent_native_connector_probe` with
      `24` tests OK
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss` with `28`
      tests OK
    - passed:
      `python -m unittest tests.test_codex_app_server_bridge
      tests.test_codex_app_server_probe` with `32` tests OK
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `53` tests OK
    - current read-only system-dialog preflight returned
      `system_dialog_clear`, `system_dialog_count=0`,
      `control_attempts=0`, `window_input_attempts=0`, and
      `native_call_attempts=0`
    - `git diff --check` returned exit code `0`; only existing LF/CRLF
      warnings were printed
  - current conclusion:
    - Codex Desktop/MSIX remains an unsafe foreground-risk surface for
      background app-side actions
    - the safe Codex route should be a non-MSIX standalone CLI/helper,
      Cursor/IDE extension app-server, or a proven native connector with
      no-focus readback
    - Cursor UIA draft is not sufficient for precise background message
      entry because ValuePattern write was not verified; Cursor should move
      to extension/native bridge
  - next concrete actions:
    1. stop treating Codex Desktop/MSIX app-server as a background connector
    2. continue Cursor/Codex/Claude through native/extension bridge contracts
       rather than UIA or Codex Desktop protocol activation
    3. keep real sends behind explicit target, transport, and readback gates
- 2026-06-04 R190 native/app bridge acceptance-readback gate:
  - trigger:
    - user asked to start filling the remaining gaps after confirming many
      routes had already been verified
    - current gap is not endpoint discovery alone; app/agent bridge routes
      must prove that a post-send transcript/readback path exists before a
      required acceptance marker can be trusted
  - official-doc basis:
    - Python `unittest` docs were checked for targeted command-line test
      execution and assertions
    - Python `dataclasses` docs were checked for the existing immutable report
      object/update style
  - implementation:
    - `agent_native_bridge` now requires explicit readback capability for
      dry-run readiness, via keys such as `readback_action_ready` or
      capabilities such as `agent_app_conversation.read_transcript`
    - missing native readback capability now returns
      `agent_native_bridge_readback_not_ready`, keeps `/v1/agent/chat`
      attempts at zero, and reports `readback_not_ready`
    - `agent_app_bridge` now adds `acceptance_readback_ready`; when
      `required_markers` are present, an endpoint must be CDP-readable or
      declare readback capability before the dry-run can be ready
    - app bridge dry-runs without marker readback now return
      `app_bridge_readback_not_ready` and report
      `acceptance_readback_not_ready`
    - `agent_app_real_no_loss` artifact writing now falls back to a unique
      sibling/temp artifact directory when the default artifact directory is
      not writable, preventing historical ACL/permission pollution from
      aborting the evaluation runner
  - validation:
    - added RED/GREEN regressions:
      `test_sender_refuses_bridge_without_readback_capability_for_marker_verification`,
      `test_agent_native_bridge_without_readback_metadata_is_not_dry_run_ready_for_markers`,
      and `test_falls_back_when_artifact_subdir_is_not_writable`
    - passed targeted tests:
      `python -m unittest tests.test_agent_native_bridge` with `7` tests OK
    - passed:
      `python -m unittest tests.test_agent_app_bridge` with `28` tests OK
    - passed:
      `python -m unittest tests.test_agent_native_connector_probe` with `24`
      tests OK
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss` with `29` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_app_bridge
      tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss
      tests.test_major_real_no_loss` with `141` tests OK
  - current conclusion:
    - connector/native bridge readiness is now closer to the final product
      acceptance bar: endpoint ready + target ready is insufficient unless
      the route can also read back markers without foreground input
    - this directly supports the target direction for WeChat/Cursor/Codex/
      Claude app-surface control: no send can be called complete without
      explicit no-focus readback
    - this does not by itself install real WeChat/Cursor/Codex/Claude bridges;
      it hardens the shared contract those bridges must satisfy
  - next concrete actions:
    1. implement or install the real WeChat native bridge adapter using this
       readback contract, then rerun file-helper-only real send/readback
    2. run Cursor/Codex/Claude native or extension bridge probes and require
       `acceptance_readback_ready=true` before any real send
    3. keep Codex Desktop/MSIX routes blocked unless a non-MSIX/native
       connector passes the same readback gate
- 2026-06-04 R191 agent native bridge fixture enters major no-loss gate:
  - trigger:
    - user asked to continue filling the remaining gaps toward unified,
      precise, no-focus computer operation
    - the standalone agent native bridge fixture smoke existed, but the
      unified `major_real_no_loss` runner did not yet execute or gate it
  - official-doc basis:
    - Python `http.server` docs were checked for the loopback
      `ThreadingHTTPServer` fixture shape
    - Python `argparse` docs were checked for repeatable CLI marker options
    - Python `dataclasses` docs were checked for safe default report fields
  - implementation:
    - added `agent_native_bridge_fixture_smoke_report` to
      `MajorScenarioRealNoLossReport`
    - major reports now expose:
      `agent_native_bridge_fixture_smoke_enabled`,
      `agent_native_bridge_fixture_smoke_ok`,
      `agent_native_bridge_fixture_control_attempts`, and
      `agent_native_bridge_fixture_native_call_attempts`
    - native fixture smoke failures now count toward `failed_runner_count`
      and force `safe_run_ok=false`
    - `window_input_attempts` and `control_attempts` include the native
      fixture counters, preserving the no-focus invariant
    - `major_real_no_loss` can now run the owned local HTTP native fixture
      through `run_agent_native_bridge_fixture_smoke`
    - CLI gained:
      `--run-agent-native-bridge-fixture-smoke`,
      `--agent-native-bridge-fixture-message`,
      `--agent-native-bridge-fixture-acceptance-marker`, and
      `--agent-native-bridge-fixture-forbid-marker`
  - validation:
    - RED tests failed for missing runner kwargs, missing report field, and
      missing CLI arguments before implementation
    - passed targeted GREEN tests:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_can_verify_agent_native_bridge_fixture_smoke_without_window_input tests.test_major_real_no_loss.MajorRealNoLossTests.test_agent_native_bridge_fixture_smoke_failure_fails_safe_gate tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_forwards_agent_native_bridge_fixture_smoke_options`
      with `3` tests OK
    - passed standalone fixture tests:
      `python -m unittest tests.test_agent_native_bridge_fixture_smoke` with
      `3` tests OK
    - passed major runner suite:
      `python -m unittest tests.test_major_real_no_loss` with `56` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_bridge_fixture_smoke tests.test_major_real_no_loss tests.test_agent_native_bridge tests.test_agent_app_bridge tests.test_agent_app_real_no_loss`
      with `123` tests OK
    - ran real CLI path with the owned loopback native fixture; the fixture
      itself reported `agent_native_bridge_fixture_smoke_ok=true`,
      `native_call_attempts=1`, and `window_input_attempts=0`
    - the same CLI command returned nonzero because the default full major
      scenario still includes currently unavailable WeChat/Word/agent app
      requirements, not because the native fixture failed
    - `git diff --check` returned exit code `0`; only existing LF/CRLF
      warnings were printed
  - current conclusion:
    - the generic agent native bridge route is now a first-class major
      no-loss gate, not just a standalone smoke
    - this strengthens the target architecture: every app-specific native
      connector can be proven through the same zero window-input, native
      call, readback-marker contract before real app sends are trusted
    - this still does not mean every desktop app is universally controllable;
      apps without a native/extension/object-model connector remain gated
      behind bridge-required or foreground-required states
  - next concrete actions:
    1. install or implement the real WeChat native bridge adapter against
       this same fixture-proven contract
    2. add Cursor/Codex/Claude app-side native/extension bridge probes to the
       major gate with explicit readback markers
    3. add a fixture-only/full-goal CLI mode or fixture profile so owned
       connector gates can return success without also requiring unavailable
       real app scenarios
- 2026-06-04 R192 fixture-only major scenario scope:
  - trigger:
    - user asked to start after confirming that several main scenarios are
      still incomplete
    - R191 proved the agent native bridge fixture route, but a real CLI run
      still returned nonzero when unrelated default WeChat/Word/agent-app
      scenarios were unavailable in the current environment
  - official-doc basis:
    - Python `argparse` docs were checked for new boolean CLI flags
    - Python `dataclasses` docs were checked for report default fields
    - Python `unittest` docs were checked for targeted regression execution
  - implementation:
    - `major_real_no_loss` now accepts:
      `run_primary_scenarios`, `run_agent_app_scenarios`, and
      `run_agent_cli_scenarios`
    - CLI gained:
      `--skip-primary-scenarios`, `--skip-agent-app-scenarios`, and
      `--skip-agent-cli-scenarios`
    - skipped runner groups now emit explicit disabled reports with
      zero `control_attempts`, zero `window_input_attempts`, zero failed
      cases, and a visible `decision`
    - requirements are now built only for enabled scenario groups, so a
      fixture-only connector gate can finish without being marked incomplete
      by unrelated unavailable apps
    - top-level reports now expose `scenario_scope` and formatted output
      shows which scenario groups were enabled
  - validation:
    - added RED/GREEN regressions:
      `test_runner_can_run_agent_native_fixture_scope_without_real_scenario_runners`
      and `test_cli_forwards_real_scenario_skip_options`
    - initial RED run failed with:
      `unexpected keyword argument 'run_primary_scenarios'` and
      CLI `unrecognized arguments`
    - passed targeted GREEN tests:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_can_run_agent_native_fixture_scope_without_real_scenario_runners tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_forwards_real_scenario_skip_options`
      with `2` tests OK
    - ran real fixture-only CLI path:
      `python -m openwukong.evaluation.major_real_no_loss --skip-primary-scenarios --skip-agent-app-scenarios --skip-agent-cli-scenarios --run-agent-native-bridge-fixture-smoke ... --json`
      and it returned exit code `0` with `safe_run_ok=true`,
      `goal_complete=true`, `agent_native_bridge_fixture_smoke_ok=true`,
      `native_call_attempts=1`, `control_attempts=0`, and
      `window_input_attempts=0`
    - ran the same scoped path for the WeChat native bridge fixture:
      `--run-wechat-native-bridge-fixture-smoke`, returning exit code `0`
      with `safe_run_ok=true`, `wechat_native_bridge_fixture_smoke_ok=true`,
      `native_call_attempts=1`, `control_attempts=0`, and
      `window_input_attempts=0`
    - passed:
      `python -m unittest tests.test_major_real_no_loss` with `58` tests OK
    - passed related regression:
      `python -m unittest tests.test_agent_native_bridge_fixture_smoke tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_app_bridge`
      with `67` tests OK
    - passed combined regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_native_bridge_fixture_smoke tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_app_bridge`
      with `125` tests OK
  - current conclusion:
    - owned connector gates can now be verified as independent, successful
      acceptance runs without touching or requiring unrelated real software
    - this directly unblocks rapid iteration on real WeChat/Cursor/Codex/
      Claude bridge adapters: each adapter can first pass a fixture-only or
      scoped major gate, then graduate to the full major goal
    - the full product goal remains incomplete until real app-side bridges
      are installed/implemented and pass readback-gated sends
  - next concrete actions:
    1. run the same scoped major gate for the WeChat native bridge fixture
       and then replace the fixture with a real installed bridge endpoint
    2. add Cursor/Codex/Claude native/extension bridge probes as scoped major
       gates before enabling any real app-side send
    3. once scoped gates pass, rerun full major without skips to measure the
       remaining real-world gaps
- 2026-06-05 R193 no-loss runner progress/timeout and Cursor non-interference:
  - trigger:
    - user asked whether the main scenarios were complete and then reported
      that normal Cursor use was interrupted by an OpenWukong IDE Bridge
      notification:
      `OpenWukong bridge failed to start: listen EADDRINUSE ... 127.0.0.1:8787`
    - a full `major_real_no_loss` status run had previously timed out without
      giving enough evidence about the stuck stage
  - official-doc basis:
    - Python `threading.Thread.join(timeout)` / daemon-thread behavior,
      `queue`, `argparse`, and `dataclasses` docs were checked for the stage
      timeout/report implementation
    - Node.js `net.Server.listen` docs were checked for `EADDRINUSE` handling
      and port fallback behavior
    - VS Code notification UX/API docs were checked; auto-start bridge
      failures should not interrupt normal IDE work
  - implementation:
    - `major_real_no_loss` now accepts `runner_timeout_sec` and CLI
      `--runner-timeout-sec`
    - each major sub-stage records progress to
      `major-real-no-loss-progress.json`, including started/completed/
      timed_out state and elapsed time
    - timed-out stages return a failed timeout subreport with
      `attempt_counters_reliable=false`, `unknown_post_timeout_runner_state=true`,
      and keep the final report from falsely claiming completion
    - CLI now has `_force_exit_process`; when a runner timeout is reported and
      `--runner-timeout-sec` is enabled, the process writes output, flushes, and
      force-exits so non-daemon child threads cannot keep the CLI alive
    - the VS Code/Cursor bridge extension no longer auto-starts by default
    - auto-start failures are silent by default and no longer show the previous
      disruptive warning
    - manual bridge start still works, and if a preferred port such as `8787`
      is occupied the extension can silently try nearby ports through
      `openwukong.bridge.autoPortOnConflict`
  - validation:
    - passed targeted tests:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_times_out_hung_primary_runner_and_writes_progress tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_forwards_runner_timeout_option`
      with `2` tests OK
    - passed `python -m unittest tests.test_major_real_no_loss` with `60`
      tests OK
    - passed related regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_native_bridge_fixture_smoke tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_app_bridge tests.test_wechat_native_bridge_fixture_smoke`
      with `129` tests OK
    - ran a real no-send/no-GUI-launch status snapshot with
      `--runner-timeout-sec 20`; it wrote
      `logs/runtime/major-current-status-20260605-r193/report.json` and
      showed:
      - `safe_run_ok=false`, `goal_complete=false`
      - `runner_timed_out=true`, `runner_stage_failed=true`
      - `control_attempts=0`, `window_input_attempts=0`,
        `agent_command_attempts=0`, `automation_focus_safe=true`
      - satisfied requirements: `3/11`
      - unmet requirements:
        `wechat_background_send`, `browser_background_research`,
        `codex_cli_background_task`, `claude_cli_background_task`,
        `cursor_cli_background_task`, `codex_app_background_chat`,
        `claude_desktop_background_chat`, `cursor_background_chat`
      - stage evidence:
        `system_dialog_preflight` completed, `primary` completed,
        `ide_extension_readiness` completed, `agent_app` timed out,
        `agent_cli` timed out
    - after the Cursor interruption report, only static checks were possible:
      process creation/PowerShell/cmd repeatedly timed out, so extension tests
      for the new non-interference behavior were not executed in this turn
  - current conclusion:
    - the main goal is still not complete; current evidence proves only part
      of the main scenario matrix
    - the runner is now much more observable: even when full status commands
      hang, stage progress and final reports can identify the stuck layer
    - thread-level timeout is insufficient for some real agent runners because
      non-daemon threads or subprocesses can still keep the CLI process alive;
      the CLI force-exit path is needed for timeout-gated real status snapshots
    - Cursor must be treated as a user work surface; normal profiles should not
      auto-start the bridge or receive bridge error notifications
  - next concrete actions:
    1. stop probing user Cursor by default; use only isolated profiles or an
       explicit bridge URL supplied by the user
    2. run extension scaffold tests once process spawning recovers
    3. split agent app/CLI status into narrower no-focus probes so Codex,
       Claude, and Cursor can be diagnosed independently without blocking the
       full major snapshot
- 2026-06-05 R194 default major snapshots stop probing user Cursor:
  - trigger:
    - user explicitly said they also need to use Cursor and OpenWukong must not
      affect normal work
    - R193 disabled bridge auto-start, but default `major_real_no_loss` still
      selected Cursor in both app and CLI agent defaults
  - official-doc basis:
    - Python `unittest` docs were checked for the assertion methods used in
      the regression tests
    - Python `argparse` docs were checked for default and explicit option
      forwarding behavior
  - implementation:
    - `DEFAULT_AGENT_APPS` changed from
      `("codex app", "claude desktop", "cursor")` to
      `("codex app", "claude desktop")`
    - `DEFAULT_CLI_AGENTS` changed from
      `("codex", "claude", "cursor")` to `("codex", "claude")`
    - added tests requiring default CLI behavior to exclude Cursor app and
      Cursor CLI surfaces unless explicitly requested
    - existing explicit Cursor paths remain intact, including tests that pass
      `--agent-app cursor` and direct runner calls with `agent_apps=("cursor",)`
    - updated global `desktop-background-control-testing` skill with the
      reusable rule: active Cursor/VS Code work surfaces are protected; IDE
      bridges must not auto-start, fixed-port probe, or notify on conflicts in
      normal user profiles
  - validation:
    - RED for `test_cli_default_agent_apps_do_not_probe_user_cursor` was run
      before the implementation and failed as expected because default
      `agent_apps` contained `cursor`
    - after implementation, process creation became unstable again:
      `cmd.exe /c echo ok`, PowerShell reads, and `tasklist` repeatedly timed
      out, so GREEN/unit regression could not be executed in this turn
    - static file checks confirmed:
      - `DEFAULT_AGENT_APPS = ("codex app", "claude desktop")`
      - `DEFAULT_CLI_AGENTS = ("codex", "claude")`
      - new default-exclusion tests are present
      - explicit Cursor app tests/runner paths are still present
      - Cursor requirements remain in the objective matrix
  - current conclusion:
    - default real no-loss snapshots now avoid touching user Cursor by
      construction
    - Cursor is still part of the final goal, but must enter verification only
      through an isolated profile or explicit target/bridge URL
    - process spawning instability remains a local verification blocker for
      fresh GREEN tests, not a reason to probe user Cursor
  - next concrete actions:
    1. once process spawning recovers, run the two new default Cursor exclusion
       tests and the extension scaffold tests
    2. run a no-Cursor default `major_real_no_loss` snapshot with
       `--runner-timeout-sec` to remeasure Codex/Claude/primary gaps
    3. add per-agent app/CLI sub-stage isolation so Codex and Claude can be
       diagnosed without Cursor or each other blocking the full report
- 2026-06-05 R195 per-agent major runner isolation:
  - trigger:
    - R193 real status snapshot showed whole `agent_app` and `agent_cli`
      stages timing out, which hid whether Codex and Claude failed for the
      same reason or independently
    - R194 removed Cursor from default probes to protect the user's active
      Cursor session, but Codex/Claude still needed narrower no-focus
      diagnostics
  - official-doc basis:
    - Python `unittest` docs were checked for the new regression assertions
    - Python `argparse` docs were checked for explicit boolean CLI flags
    - Python `dataclasses` docs were rechecked for default-field behavior used
      by the surrounding report model
  - implementation:
    - `run_major_scenario_real_no_loss` gained:
      `isolate_agent_app_scenarios` and `isolate_agent_cli_scenarios`
    - CLI gained:
      `--isolate-agent-app-scenarios` and
      `--isolate-agent-cli-scenarios`
    - when enabled, agent app probes run one agent at a time with stage names
      such as `agent_app:codex app` and `agent_app:claude desktop`
    - when enabled, agent CLI probes run one agent at a time with stage names
      such as `agent_cli:codex` and `agent_cli:claude`
    - per-agent subreports are merged into a normal app/CLI report while
      preserving summed counters, cases, focus-stability booleans, and the
      raw isolated subreports
    - added regression coverage for:
      - direct runner per-agent app/CLI isolation
      - CLI forwarding of the two isolation flags
  - validation:
    - static implementation checks confirmed:
      - new function params are present
      - new CLI args are present and forwarded
      - isolated app/CLI stage names are present
      - `_merge_agent_runner_reports` and `_safe_stage_id` are present
      - new tests are present
      - Cursor remains excluded from default app/CLI agents
    - fresh GREEN tests were not run in this turn because even
      `cmd.exe /c echo ok` timed out repeatedly, indicating local process
      creation/exit instability
  - current conclusion:
    - the major runner can now represent the intended next diagnostic shape:
      Codex and Claude can be measured separately, and a stuck route does not
      need to hide the other route's evidence
    - this remains unverified by fresh test execution until process spawning
      recovers
    - no Cursor app, bridge, or CLI probe was run in this turn
  - next concrete actions:
    1. once process spawning recovers, run the new isolation tests plus the
       default Cursor-exclusion tests
    2. run a default no-Cursor snapshot with
       `--runner-timeout-sec 20 --isolate-agent-app-scenarios --isolate-agent-cli-scenarios`
    3. use the isolated report to decide whether Codex/Claude need app-server,
       native bridge, or CLI-specific fixes next
- 2026-06-05 R196 adaptive IDE bridge port and registry discovery:
  - trigger:
    - user pointed out the IDE bridge should adaptively find an unused port
      instead of colliding with the active Cursor session on `127.0.0.1:8787`
    - user explicitly needs to keep using Cursor while OpenWukong tests run
  - official-doc basis:
    - Node.js `net.Server.listen` documentation was checked: binding port `0`
      lets the operating system assign an unused port, which is then available
      from `server.address().port` after `listening`
  - implementation:
    - VS Code/Cursor bridge extension now supports `openwukong.bridge.port = 0`
      to request an OS-assigned unused loopback port
    - if the preferred port and configured consecutive fallback ports are
      unavailable, `openwukong.bridge.dynamicPortOnConflict=true` falls back to
      port `0` instead of interrupting the IDE session
    - the extension records the actual started `bridge_url` in a local
      OpenWukong IDE bridge registry under `%LOCALAPPDATA%/OpenWukong/ide-bridges`
    - registry writes are best-effort: a local file write failure logs a
      warning but does not fail bridge startup
    - bridge metadata now exposes `bridge_url` and `bridge_state_file`
    - added `openwukong.control.ide_bridge_registry`:
      - reads explicit URLs, `OPENWUKONG_IDE_BRIDGE_URLS`, and registry paths
      - accepts only loopback/local URLs
      - filters disabled entries and mismatched IDE products
      - supports default `%LOCALAPPDATA%/OpenWukong/ide-bridges` discovery
    - `SessionDiscoveryOptions.ide_bridge_urls` now defaults to empty, not a
      fixed `8787-8790` scan
    - `run_primary_real_no_loss` and its CLI now default to no IDE bridge URL;
      they only probe an explicit URL or a registry-discovered URL
    - docs and scaffold tests were updated to document dynamic ports and the
      protected daily-work Cursor profile rule
  - validation:
    - process creation remained unstable: `cmd.exe /c echo ok` timed out, so
      fresh Python unit tests could not be executed in this turn
    - Node REPL static checks confirmed:
      - package JSON parses
      - `openwukong.bridge.port` allows `0`
      - `dynamicPortOnConflict` defaults to `true`
      - `autoStart` remains default `false`
      - extension code uses `listenOnPort(candidate, host, 0)` and
        `candidate.address()`
      - extension writes an `openwukong-ide-bridge-registry-v1` file under
        `ide-bridges`
      - session discovery no longer has default fixed IDE bridge URLs
      - primary no-loss runner no longer defaults to `http://127.0.0.1:8787`
      - tests cover default no-probe behavior and dynamic registry discovery
  - current conclusion:
    - the design is now the right shape for user-safe Cursor coexistence:
      bridges do not auto-start, do not force a shared port, and do not require
      fixed-port probing for discovery
    - this does not yet prove full precise control of every app; it removes a
      real safety/UX blocker in the IDE bridge route
    - fresh GREEN tests remain pending until local process creation recovers
  - next concrete actions:
    1. once process spawning recovers, run:
       `python -m unittest tests.test_ide_extension_scaffold tests.test_ide_bridge_registry tests.test_session_discovery tests.test_primary_real_no_loss`
    2. run a no-Cursor/no-fixed-IDE-probe major snapshot with isolated
       Codex/Claude stages
    3. only test Cursor bridge/chat through an isolated Cursor profile or a
       user-supplied explicit bridge URL
- 2026-06-05 R197 dynamic IDE bridge validation and registry instance hardening:
  - trigger:
    - continue the active goal while protecting the user's current Cursor work
      surface
    - validate the R196 dynamic-port/no-fixed-probe implementation without
      starting real Cursor or touching the user's IDE
  - implementation:
    - hardened the IDE bridge registry writer so registry filenames are
      instance-scoped by including the bridge process id in the hash seed
    - this prevents two windows in the same profile/workspace family from
      overwriting each other's bridge registry entry or deleting a shared entry
      on shutdown
    - updated extension scaffold tests to require the process id in the
      registry instance key
    - updated the global `desktop-background-control-testing` skill with the
      reusable rule for per-instance, best-effort local bridge registries
  - validation:
    - direct shell remained unstable:
      `cmd.exe /c echo ok` timed out
    - direct Python through Node child_process printed `ok` but did not return
      a reliable exit/close event in one probe, so process-handle instability
      remains a local verification caveat
    - non-GUI unittest groups were run through the existing Node REPL without
      touching Cursor or real apps:
      - `tests.test_ide_bridge_registry`,
        `tests.test_session_discovery`,
        `tests.test_ide_extension_scaffold` output
        `Ran 14 tests ... OK`
      - `tests.test_primary_real_no_loss` output
        `Ran 11 tests ... OK`
      - major default Cursor-exclusion/isolation tests run individually:
        three exited with code `0`, and the fourth output
        `Ran 1 test ... OK` before the external process event timed out
    - final static checks confirmed:
      - dynamic port fallback still uses `listenOnPort(candidate, host, 0)`
      - bound ports are read from `candidate.address()`
      - registry writes are best-effort
      - registry instance key includes `process.pid`
      - session discovery has no default fixed IDE bridge URLs
      - primary no-loss runner has no default `http://127.0.0.1:8787`
  - current conclusion:
    - the IDE bridge route is now substantially safer for daily Cursor
      coexistence: no auto-start by default, no fixed-port default probing,
      adaptive ports, registry discovery, and instance-scoped state files
    - this is progress toward the final goal, but it is not proof that all
      main scenarios are fully background-operable yet
    - the remaining local process exit instability should be diagnosed
      separately before relying on long real-run snapshots
  - next concrete actions:
    1. run a no-Cursor/no-fixed-IDE-probe major status snapshot once process
       exit handling is stable enough for long runners
    2. continue Codex/Claude background routes through app-server/native or CLI
       probes, keeping app/session/turn safety separated
    3. only verify Cursor real chat through isolated profile or explicit
       user-supplied bridge URL
- 2026-06-05 R198 adaptive bridge final validation and current objective status:
  - trigger:
    - user confirmed the IDE bridge should be self-adaptive by dynamically
      finding an unused port instead of requiring fixed per-machine paths or
      a shared `127.0.0.1:8787`
    - user also needs to keep using the current Cursor window during tests
  - implementation status:
    - adaptive IDE bridge porting is implemented:
      - `openwukong.bridge.port = 0` requests an OS-assigned unused port
      - `openwukong.bridge.dynamicPortOnConflict=true` falls back to port `0`
        when the preferred/fallback range is unavailable
      - the actual bound `bridge_url` is published in a per-instance local
        registry under `%LOCALAPPDATA%/OpenWukong/ide-bridges`
      - discovery reads explicit URLs, environment URLs, and local registry
        entries, accepts only loopback/local URLs, and tolerates stale entries
      - default session discovery and primary no-loss runs no longer probe
        fixed IDE bridge URLs such as `http://127.0.0.1:8787`
    - major no-loss runner observability is improved:
      - primary scenario progress is written to
        `primary-real-no-loss-progress.json`
      - `major_real_no_loss` can stop after the first runner timeout with
        `--stop-on-runner-timeout`, writing a final report instead of hanging
      - default major snapshots exclude Cursor app/CLI surfaces unless the run
        uses an isolated profile or explicit user-supplied target
  - validation:
    - passed non-GUI regression without starting or probing Cursor:
      `python -m unittest tests.test_ide_extension_scaffold tests.test_ide_bridge_registry tests.test_session_discovery tests.test_primary_real_no_loss`
      with `25` tests OK
    - latest no-Cursor, no-fixed-IDE-probe real status snapshot with owned
      headless browser helper:
      `logs/runtime/major-current-status-20260605-r203-browser/report.json`
      returned process exit code `0`
    - r203 snapshot showed:
      - `safe_run_ok=true`, `goal_complete=false`
      - `control_attempts=0`, `window_input_attempts=0`
      - `automation_focus_safe=true`
      - verified/satisfied:
        `wechat_background_observation`,
        `word_background_document`,
        `browser_background_research`,
        `file_background_search`
      - still unmet:
        `wechat_background_send`,
        `codex_cli_background_task`,
        `claude_cli_background_task`,
        `cursor_cli_background_task`,
        `codex_app_background_chat`,
        `claude_desktop_background_chat`,
        `cursor_background_chat`
  - current conclusion:
    - the adaptive-port/registry design is now the correct default for
      multi-machine and daily Cursor coexistence; it removes the fixed-port
      collision class that produced the user-visible bridge warning
    - the project has not yet reached full precise operation for all desktop
      software; the safe background substrate is working for several major
      routes, but chat/send/task-submission routes still need native bridge or
      CLI acceptance gates
  - next concrete actions:
    1. keep Cursor protected by default; only test Cursor chat through an
       isolated profile or explicit bridge URL
    2. close the WeChat send gap through the native bridge/UIA semantic sender
       gate with readback and zero keyboard/mouse/clipboard attempts
    3. close Codex/Claude through no-loss CLI or native app-server routes,
       rejecting any MSIX/Electron foreground-risk evidence
- 2026-06-05 R199 real Codex CLI background verification and CLI route accuracy:
  - trigger:
    - continue the active objective toward verified, precise, background
      operation for Codex/Claude/Cursor without touching the user's active
      Cursor workspace
    - R198 left Codex/Claude CLI routes unverified because real execution had
      not been opted in
  - official-doc basis:
    - Python `unittest` and `dataclasses` documentation was checked before the
      classification/test update
  - implementation:
    - tightened `agent_cli_real_no_loss` status classification so a missing
      CLI transport or not-ready command plan is reported as
      `background_cli_unavailable` before `skipped_requires_cli_execution_opt_in`
    - added regression coverage so a missing `cursor-agent` CLI is not masked
      by the dry-run execution gate
    - updated the global `desktop-background-control-testing` skill with the
      reusable rule that dry-run status must not hide transport absence
  - validation:
    - passed:
      `python -m unittest tests.test_agent_cli_real_no_loss tests.test_agent_task_runner tests.test_agent_conversation`
      with `33` tests OK
    - real no-loss Codex CLI probe:
      `logs/runtime/agent-cli-status-20260605-r200-codex-real/report.json`
      showed:
      - `status=verified`, `real_verified=true`
      - selected transport `codex-cli-managed-terminal`
      - `agent_command_attempts=1`
      - `window_input_attempts=0`
      - `system_dialog_detected=false`
      - workspace remained clean
      - required marker `OPENWUKONG_AGENT_CLI_NO_LOSS: PASS` was read back
    - real no-loss Claude CLI probe:
      `logs/runtime/agent-cli-status-20260605-r200-claude-real/report.json`
      showed:
      - selected transport `claude-code-cli-managed-terminal`
      - `agent_command_attempts=1`
      - `window_input_attempts=0`
      - `system_dialog_detected=false`
      - status `cli_auth_required` because this machine is not logged in
    - full no-Cursor major snapshot with owned headless browser helper and
      real Codex/Claude CLI execution:
      `logs/runtime/major-current-status-20260605-r204-cli-real/report.json`
      returned exit code `0` with:
      - `safe_run_ok=true`, `goal_complete=false`
      - `control_attempts=0`, `window_input_attempts=0`
      - `agent_command_attempts=2`
      - no runner timeout
      - satisfied requirements increased to `5/11`:
        `wechat_background_observation`,
        `word_background_document`,
        `browser_background_research`,
        `file_background_search`,
        `codex_cli_background_task`
      - remaining unmet:
        `wechat_background_send`,
        `claude_cli_background_task`,
        `cursor_cli_background_task`,
        `codex_app_background_chat`,
        `claude_desktop_background_chat`,
        `cursor_background_chat`
    - Cursor agent dry-run after the fix:
      `logs/runtime/agent-cli-status-20260605-r202-cursor-dry-fixed/report.json`
      showed `status=background_cli_unavailable`,
      `selected_transport=""`, `agent_command_attempts=0`, and
      `window_input_attempts=0`
  - current conclusion:
    - Codex CLI is now a verified precise background task route on this machine
    - Claude CLI control path is structurally ready and no-loss, but real task
      execution is blocked by local auth state, not by OpenWukong routing
    - Cursor CLI route is not currently available on this machine because
      `cursor-agent` was not resolved; Cursor desktop remains protected unless
      an isolated profile or explicit bridge URL is supplied
    - WeChat background send still requires a native bridge URL or a UIA
      semantic target that exposes target/composer/submit patterns; the current
      WeChat UIA snapshot remains read-only only
  - next concrete actions:
    1. close WeChat send by installing/implementing a real native bridge or
       proving a UIA semantic sender target exists with readback
    2. after Claude login is available, rerun the same no-loss Claude CLI probe
    3. for Cursor, either install/resolve `cursor-agent` for CLI background
       tasks or use an isolated Cursor profile/explicit IDE bridge URL for
       desktop chat verification
- 2026-06-05 R200 adaptive bridge revalidation and Cursor surface split:
  - trigger:
    - user reiterated that the bridge should be adaptive by dynamically finding
      an unused port, instead of colliding with the active Cursor workspace
  - implementation status:
    - adaptive IDE bridge behavior is present in code:
      - `openwukong.bridge.port` allows `0`
      - `openwukong.bridge.dynamicPortOnConflict` defaults to `true`
      - the extension uses `listenOnPort(candidate, host, 0)` for dynamic
        assignment and reads the actual bound port from `candidate.address()`
      - the actual bridge URL is written to a per-instance registry under
        `%LOCALAPPDATA%/OpenWukong/ide-bridges`
      - `SessionDiscoveryOptions.ide_bridge_urls` defaults to empty and reads
        explicit/env/registry URLs instead of probing fixed `8787`
    - current major runner defaults keep Cursor desktop protected:
      - `DEFAULT_AGENT_APPS = ("codex app", "claude desktop")`
      - `DEFAULT_CLI_AGENTS` includes `cursor` only as the `cursor-agent`
        background CLI route, with regression coverage proving it does not
        fall back to the Cursor desktop shell when unavailable
  - validation:
    - passed non-GUI regression without starting or probing Cursor desktop:
      `python -m unittest tests.test_ide_extension_scaffold tests.test_ide_bridge_registry tests.test_session_discovery tests.test_primary_real_no_loss`
      with `25` tests OK
    - passed targeted Cursor-protection and CLI-route regressions:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_aggregates_main_surfaces_and_marks_unmet_background_actions tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_default_agent_apps_do_not_probe_user_cursor tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_default_cli_agents_include_only_cursor_agent_cli_route tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_can_isolate_agent_app_and_cli_scenarios_per_agent tests.test_agent_cli_real_no_loss.AgentCliRealNoLossTests.test_cli_probe_does_not_fall_back_to_cursor_desktop_shell_when_agent_cli_missing tests.test_agent_cli_real_no_loss.AgentCliRealNoLossTests.test_dry_run_reports_background_cli_unavailable_when_agent_cli_missing`
      with `6` tests OK
  - current conclusion:
    - the fixed-port collision class is addressed by dynamic port assignment
      plus local registry discovery
    - the default path should no longer create `127.0.0.1:8787` conflict
      popups in the user's active Cursor window
    - this is still not a claim that all desktop apps are fully background
      operable; WeChat send, Claude auth, and app-chat send/readback gates
      remain separate acceptance items
  - next concrete actions:
    1. rerun a major no-loss snapshot when needed, with Cursor desktop still
       protected and Cursor CLI treated only as `cursor-agent`
    2. close WeChat background send through a native bridge or proven UIA
       semantic sender with readback
    3. close Claude/Codex app-chat through background-safe native app-server or
       CLI routes without MSIX/Electron foreground dialogs
- 2026-06-05 R201 current major no-loss evidence and protected Cursor reporting:
  - trigger:
    - continue the active objective toward verified precise background control
      across WeChat, Word, Browser, Codex, Claude, and Cursor while preserving
      the user's active Cursor desktop session
  - official-doc basis:
    - Python `dataclasses` documentation was checked for the immutable report
      model/default-field pattern
    - Python `unittest` documentation was checked for the focused regression
      tests
  - implementation:
    - fixed major objective reporting for protected Cursor desktop:
      - when a default no-loss run intentionally omits Cursor desktop app/chat
        probing, `cursor_background_chat` now reports `status=gated` with
        blocking reason
        `gated_cursor_desktop_protected_explicit_bridge_required`
      - compact evidence now preserves:
        `protected_default`, `protection_reason`,
        `required_endpoint_kind`, and `next_action`
      - this replaces the misleading previous `case_missing` report for a
        deliberately protected user work surface
    - updated the global `desktop-background-control-testing` skill with the
      reusable rule that protected work surfaces must be represented as gated
      protected requirements, not as missing cases
  - validation:
    - passed focused regression:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_missing_default_cursor_app_case_is_reported_as_protected_gate tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_aggregates_main_surfaces_and_marks_unmet_background_actions tests.test_major_real_no_loss.MajorRealNoLossTests.test_cli_default_agent_apps_do_not_probe_user_cursor tests.test_objective_readiness_matrix`
      with `4` tests OK
    - R205 real no-loss snapshot before the reporting fix:
      `logs/runtime/major-current-status-20260605-r205-cursor-cli-default/report.json`
      showed `safe_run_ok=true`, `control_attempts=0`,
      `window_input_attempts=0`, `agent_command_attempts=2`,
      `owned_app_launch_attempts=1`, no runner timeout, and
      `cursor_background_chat` still as `case_missing`
    - R206 real no-loss snapshot after the reporting fix:
      `logs/runtime/major-current-status-20260605-r206-cursor-protected-gate/report.json`
      returned exit code `0` with:
      - `safe_run_ok=true`, `goal_complete=false`
      - `control_attempts=0`, `window_input_attempts=0`
      - `agent_command_attempts=2`
      - `owned_app_launch_attempts=1`
      - `background_screenshot_focus_stable=true`
      - `cli_foreground_focus_stable=true`
      - `runner_timed_out=false`, `failed_runner_count=0`
      - objective summary:
        `requirement_count=11`, `satisfied_count=5`, `gated_count=3`,
        `auth_required_count=1`, `unavailable_count=2`
      - `cursor_background_chat` now reports protected gated evidence:
        `protected_default=true`,
        `protection_reason=active_cursor_desktop_protected`,
        `required_endpoint_kind=explicit_ide_bridge_or_isolated_cursor_profile`
    - R206 owned headless browser helper evidence:
      - helper status `started_and_stopped`
      - profile cleanup `attempted=true`, `deleted=true`
      - a stop warning for a Chrome child process was present, but an exact
        read-only command-line scan for the owned profile path found no
        remaining processes
  - current conclusion:
    - real no-loss execution is stable for the already verified main routes:
      WeChat background observation, hidden Word COM document work, owned
      browser CDP research, owned filesystem search, and Codex CLI background
      task
    - the full goal is still incomplete:
      - WeChat background send is gated by missing native bridge URL and no
        ready UIA semantic sender
      - Claude CLI is structurally ready but local auth is missing
      - Cursor CLI route is unavailable because `cursor-agent` is not resolved
      - Codex app chat lacks a visible/ready target task or safe app bridge
      - Claude Desktop app is not visible/resolved in the current run
      - Cursor desktop app chat is protected by default and requires an
        explicit bridge URL or isolated profile
  - next concrete actions:
    1. build/attach a deterministic WeChat native bridge or prove a UIA
       semantic sender with readback for File Transfer Assistant only
    2. close Claude after login/auth is available by rerunning the same no-loss
       CLI probe
    3. for Cursor desktop, use only an explicit IDE bridge URL or isolated
       profile; otherwise keep it protected and do not probe the user's active
       window
- 2026-06-05 R208 adaptive IDE bridge default and scoped-goal reporting fix:
  - trigger:
    - user pointed out the IDE bridge should adaptively find an unused port
      instead of colliding with the active Cursor workspace on `127.0.0.1:8787`
    - a scoped fixture-only major run exposed that an empty requirement set
      could incorrectly promote top-level `goal_complete=true`
  - official-doc basis:
    - Node.js `net.Server.listen` documentation was checked: port `0`
      requests an operating-system-assigned unused port, and the actual bound
      port must be read from `server.address().port` after listening
    - Python `dataclasses` and `pathlib` documentation was checked before
      extending readiness report fields and installed-extension diagnostics
  - implementation:
    - changed the OpenWukong VS Code/Cursor bridge default port from `8787`
      to `0` in both `extension.js` and `package.json`
    - kept explicit fixed ports available only as opt-in settings, with the
      existing dynamic fallback/registry discovery path preserved
    - updated extension docs to make `port=0` the default daily-work profile
      recommendation
    - strengthened `ide_extension_readiness` so it reports installed stale
      extension copies that still use default `8787`, `autoStart=true`, no
      dynamic fallback, or disruptive bridge-start warning popups
    - confirmed the user's current Cursor-installed extension copy is stale:
      `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0`
      still has default `8787`, `autoStart=true`, no dynamic fallback, and a
      `OpenWukong bridge failed to start` warning path
    - fixed `MajorScenarioRealNoLossReport.goal_complete` so empty
      requirements can still be safe scoped runs but never count as global
      objective completion
    - updated global skills:
      `debug-connector-helper-readiness` for installed IDE bridge stale-copy
      checks, and `desktop-background-control-testing` for fixture-only
      `goal_complete=false`
  - validation:
    - passed:
      `python -m unittest tests.test_ide_extension_scaffold tests.test_ide_extension_readiness tests.test_ide_bridge_registry tests.test_session_discovery`
      with `21` tests OK
    - read-only installed-extension probe returned:
      `status=installed_extension_stale`,
      `blocking_reason=installed_extension_uses_fixed_port_or_disruptive_autostart`,
      `control_attempts=0`, `window_input_attempts=0`
    - passed full major regression:
      `python -m unittest tests.test_major_real_no_loss`
      with `67` tests OK
    - R208 fixture-only major smoke:
      `logs/runtime/major-wechat-native-bridge-fixture-r208-goal-fix/report.json`
      returned exit code `0` with:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `requirements=[]`
      - `wechat_native_bridge_fixture_smoke_ok=true`
      - `control_attempts=0`, `window_input_attempts=0`
      - `wechat_native_bridge_fixture_native_call_attempts=1`
  - current conclusion:
    - the repository version now defaults to adaptive IDE bridge ports and
      should not create new fixed-port `8787` collisions
    - the visible Cursor popup came from an already-installed old extension
      copy, not from the current repository source
    - the active Cursor install was only inspected read-only in this run; it
      was not patched or reloaded, so the user's active Cursor work surface was
      not disturbed
    - the full desktop-control objective remains incomplete at `5/11`
      verified main requirements until WeChat real native send, Claude auth,
      Cursor CLI/bridge, and app-chat routes are closed
  - next concrete actions:
    1. update/reinstall the Cursor OpenWukong extension through a controlled
       reload or isolated profile so the active installed copy uses the R208
       adaptive-port bridge
    2. keep Cursor protected by default; use registry-discovered or explicit
       bridge URLs only after the updated extension is active
    3. continue closing WeChat native bridge, Claude auth, and app-chat
       background routes with zero keyboard/mouse/clipboard/window input
- 2026-06-05 R209 controlled IDE extension sync for adaptive-port rollout:
  - trigger:
    - user confirmed the bridge should be self-adaptive by dynamically finding
      an unused port, and also made clear that active Cursor must not be
      disrupted while they are working
  - implementation:
    - added `openwukong.evaluation.ide_extension_sync`, a controlled
      install-audit/sync tool for the OpenWukong IDE extension
    - default mode is read-only audit:
      `python -m openwukong.evaluation.ide_extension_sync --json`
    - apply mode backs up and replaces stale installed extension copies, but
      refuses to write an active Cursor/VS Code profile unless explicitly
      overridden with `--allow-active-profile-update`
    - sync reports keep `control_attempts=0` and `window_input_attempts=0`,
      so the tool can be used while the user is working
    - copy excludes runtime/noise directories such as `logs`, `.git`,
      `.vscode-test`, `node_modules`, and `__pycache__`
  - validation:
    - passed:
      `python -m unittest tests.test_ide_extension_sync`
      with `4` tests OK
    - passed focused IDE/session regression:
      `python -m unittest tests.test_ide_extension_sync tests.test_ide_extension_readiness tests.test_ide_extension_scaffold tests.test_ide_bridge_registry tests.test_session_discovery`
      with `25` tests OK
    - passed protected Cursor gate regression:
      `python -m unittest tests.test_ide_extension_sync tests.test_ide_extension_readiness tests.test_ide_extension_scaffold tests.test_ide_bridge_registry tests.test_session_discovery tests.test_major_real_no_loss.MajorRealNoLossTests.test_missing_default_cursor_app_case_is_reported_as_protected_gate`
      with `26` tests OK
    - `git diff --check` passed, with only pre-existing CRLF warnings
    - read-only real audit report:
      `logs/runtime/ide-extension-sync-r209-dry-run/report.json`
      returned `status=stale_install_detected`,
      `write_attempts=0`, `control_attempts=0`,
      `window_input_attempts=0`
    - real apply attempt without active-profile override:
      `logs/runtime/ide-extension-sync-r209-apply-refused-active/report.json`
      returned `status=apply_refused_active_process`,
      `blocking_reason=active_ide_process_detected`,
      `write_attempts=0`, `control_attempts=0`,
      `window_input_attempts=0`
  - current conclusion:
    - repository source is already adaptive: default `openwukong.bridge.port=0`
      and actual OS-assigned port is published through the local IDE bridge
      registry
    - the current user-visible Cursor interruption is from the installed stale
      extension copy under
      `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0`
    - because active Cursor processes are present, the new sync tool correctly
      refused to patch the live profile; this preserves the user's current work
  - next concrete actions:
    1. when the user is ready to close/reload Cursor, run controlled sync apply
       or update through an isolated profile so the installed copy receives the
       adaptive bridge
    2. after the updated extension is active, validate registry discovery of
       the dynamic bridge URL without probing fixed port `8787`
    3. continue the remaining main-scenario closures after the IDE bridge no
       longer interrupts active work
- 2026-06-05 R210 objective closure plan for no-focus next actions:
  - trigger:
    - active goal continuation required concrete progress toward the full
      background desktop-control objective without disrupting the user's active
      Cursor/desktop work
    - R209 had identified stale Cursor bridge install safety, but the goal
      matrix still required manual interpretation for the next safe action per
      unmet requirement
  - implementation:
    - extended `objective_readiness_matrix` with a machine-readable
      `closure_plan`
    - each unmet required objective item now emits:
      `action_id`, `action_kind`, preferred transport, safe probe runner,
      whether it is safe to run now, whether it is blocked by external state,
      required verification gates, forbidden actions, and notes
    - added specific closure actions for:
      - WeChat background send:
        `attach_wechat_native_bridge_or_verified_uia_send`
      - owned browser research:
        `run_owned_browser_devtools_no_loss_probe`
      - Codex CLI:
        `rerun_codex_cli_no_loss_with_execution_opt_in`
      - Claude CLI:
        separate managed CLI opt-in rerun from proven auth-required state
      - Cursor CLI:
        `resolve_cursor_agent_cli_or_explicit_ide_bridge`
      - Codex app:
        `attach_codex_native_app_server_or_cdp_bridge`
      - Claude Desktop:
        `attach_claude_desktop_native_or_devtools_bridge`
      - Cursor app:
        `update_or_attach_cursor_ide_bridge_without_touching_active_profile`
    - updated the global `desktop-background-control-testing` skill so future
      reports do not confuse `skipped_requires_*_opt_in` with proven
      `auth_required`
  - validation:
    - official-doc basis:
      Python dataclasses documentation was checked before adding dataclass
      fields with `default_factory`
    - passed:
      `python -m unittest tests.test_objective_readiness_matrix`
      with `2` tests OK before the final opt-in/auth distinction, then the
      expanded objective/major focused suite with `5` tests OK
    - `git diff --check` passed, with only pre-existing CRLF warnings
    - R210 real read-only major audit:
      `logs/runtime/major-real-no-loss-r210-closure-plan-readonly-v2/report.json`
      returned:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `external_communication_attempts=0`
      - `owned_app_launch_attempts=0`
      - `bridge_send_attempts=0`
      - `agent_command_attempts=0`
      - `background_screenshot_success_count=2`
      - `background_screenshot_focus_stable=true`
      - `objective_readiness_matrix.summary.requirement_count=11`
      - `satisfied_count=3`
      - `closure_plan.action_count=8`
      - `closure_plan.safe_to_run_now_count=8`
      - `closure_plan.external_state_blocked_count=0`
    - R210 unsatisfied requirements in the most conservative read-only run:
      `wechat_background_send`, `browser_background_research`,
      `codex_cli_background_task`, `claude_cli_background_task`,
      `cursor_cli_background_task`, `codex_app_background_chat`,
      `claude_desktop_background_chat`, `cursor_background_chat`
  - current conclusion:
    - the system still has not achieved the full goal; the latest conservative
      no-launch/no-send audit only satisfies `3/11` because owned browser and
      managed CLI execution were intentionally not opted in during this run
    - the new closure plan makes the next safe move explicit instead of
      ambiguous: it can now drive follow-up runs without using keyboard,
      mouse, clipboard, foreground takeover, or active Cursor modification
    - important correction:
      Claude CLI should only be marked `auth_required` after the no-loss CLI
      probe actually observes the auth gate; a skipped execution opt-in now
      maps to a managed rerun action instead
  - next concrete actions:
    1. run the safe closure actions that are pure background/no-loss:
       owned browser DevTools probe and managed Codex/Claude CLI no-loss probe
       with explicit execution opt-in
    2. keep Cursor active profile protected; only run read-only sync audit
       until the user closes/reloads Cursor or supplies an explicit bridge URL
    3. continue WeChat through native bridge or verified UIA semantic send for
       File Transfer Assistant only, with marker readback and zero window input
- 2026-06-05 R211 executed safe closure actions for owned browser and managed CLI:
  - trigger:
    - R210 closure plan identified safe background/no-loss actions that could
      be run immediately without touching active Cursor, foreground input, or
      external messaging
  - real managed CLI no-loss run:
    - command:
      `python -m openwukong.evaluation.agent_cli_real_no_loss --agent codex --agent claude --agent cursor --output-root logs\runtime\agent-cli-real-no-loss-r211-managed-cli --output logs\runtime\agent-cli-real-no-loss-r211-managed-cli\report.json --allow-cli-execution --timeout-sec 120 --json`
    - report:
      `logs/runtime/agent-cli-real-no-loss-r211-managed-cli/report.json`
    - result:
      - `passed_cases=3/3`
      - `verified_cases=1`
      - `agent_command_attempts=2`
      - `window_input_attempts=0`
      - `foreground_no_steal_verified=true`
      - `system_dialog_detected=false`
    - per-agent evidence:
      - Codex CLI:
        `status=verified`, `real_verified=true`,
        selected transport `codex-cli-managed-terminal`, marker readback
        accepted, workspace clean, no window input
      - Claude CLI:
        `status=cli_auth_required`, selected transport
        `claude-code-cli-managed-terminal`, workspace clean, no window input
      - Cursor agent CLI:
        `status=background_cli_unavailable`, no command attempts, workspace
        clean, no window input
    - foreground note:
      the Codex CLI case saw foreground HWND change from Codex to Cursor, but
      it was classified as `changed_to_unrelated_surface`; the run therefore
      kept `foreground_no_steal_verified=true`
  - real owned browser + CLI scoped major run:
    - command:
      `python -m openwukong.evaluation.major_real_no_loss --output-root logs\runtime\major-real-no-loss-r211-owned-browser-cli --output logs\runtime\major-real-no-loss-r211-owned-browser-cli\report.json --allow-owned-browser-helper-launch --owned-browser-debug-port 9491 --owned-browser-url "data:text/html,<title>OpenWukong R211 Owned Browser</title><body>OpenWukong R211 Owned Browser</body>" --skip-agent-app-scenarios --isolate-agent-cli-scenarios --allow-agent-cli-execution --agent-cli-timeout-sec 120 --runner-timeout-sec 180 --json`
    - report:
      `logs/runtime/major-real-no-loss-r211-owned-browser-cli/report.json`
    - result:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `external_communication_attempts=0`
      - `owned_app_launch_attempts=1`
      - `agent_command_attempts=2`
      - `background_screenshot_success_count=1`
      - `background_screenshot_focus_stable=true`
      - final process scan found no R211 owned browser helper process matching
        the owned profile or DevTools port
    - verified scoped requirements:
      - WeChat background observation:
        `status=verified`
      - Word hidden COM document:
        `status=verified`
      - Browser owned DevTools research:
        `status=verified`, selected transport `browser-devtools-owned`
      - File owned filesystem search:
        `status=verified`
    - remaining scoped blockers in that run:
      - WeChat background send:
        `gated`, `wechat_native_bridge_url_missing`
      - Codex CLI:
        `unavailable`, `cli_usage_limit`
      - Claude CLI:
        `auth_required`, `local_cli_not_logged_in`
      - Cursor CLI:
        `gated`, `background_cli_unavailable`
  - current conclusion:
    - Browser background control is now re-verified through an owned isolated
      DevTools helper with cleanup and no window input
    - Codex CLI capability was verified in the standalone R211 CLI run, but a
      later scoped major rerun reported `cli_usage_limit`; current objective
      status must treat Codex CLI as temporarily availability-gated until a
      fresh no-loss CLI run verifies it again
    - Claude CLI is now correctly proven as `auth_required`, not merely
      skipped for lack of execution opt-in
    - Cursor agent CLI is not available; Cursor desktop remains a protected
      IDE bridge problem, not a CLI fallback problem
    - the full objective remains incomplete because app desktop chat routes,
      WeChat background send, Cursor bridge install/update, and current Codex
      CLI availability are not all verified at once
  - next concrete actions:
    1. continue with WeChat native bridge or verified UIA semantic send for
       File Transfer Assistant only
    2. keep Codex/Claude desktop app chat on native/app-server/DevTools bridge
       discovery; do not use CLI as a substitute for explicit app surfaces
    3. when Cursor can be reloaded or an explicit bridge URL is available,
       update/attach the adaptive IDE bridge and validate Cursor background
       chat through registry-discovered dynamic port
- 2026-06-06 R212 Claude Desktop app-only default route:
  - trigger:
    - user clarified that Claude should be treated as a desktop App surface
      for the current roadmap, and Claude CLI should be paused for now
  - implementation:
    - changed the major no-loss default CLI set from
      `("codex", "claude", "cursor")` to `("codex", "cursor")`
    - kept `claude desktop` in the default App-surface set
    - changed major requirement construction so CLI requirements are generated
      only for the CLI agents selected in that run
    - retained explicit Claude CLI support through `--cli-agent claude` for
      future isolated diagnostics, but it no longer substitutes for a Claude
      Desktop App requirement
  - official-doc basis:
    - Python `argparse` documentation was checked for the CLI default/override
      behavior before changing the runner defaults
  - validation:
    - passed:
      `python -m unittest tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `70` tests OK
    - R212 real Claude App-only read-only probe:
      `logs/runtime/major-real-no-loss-r212-claude-app-only-readonly/report.json`
      returned:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `agent_command_attempts=0`
      - `window_input_attempts=0`
      - Claude CLI subreport disabled with zero cases
      - Claude Desktop resolved to
        `C:\Users\Zhangjinqian\.local\bin\Claude.exe`
      - Claude Desktop App requirement status:
        `unavailable`, blocking reason `app_surface_not_ready`
      - no owned App launch, no bridge send, no keyboard/mouse/clipboard/window
        input
    - `git diff --check` passed with only existing CRLF warnings
  - current conclusion:
    - Claude is now routed as an App-surface target by default, not as a CLI
      target
    - the current machine has a resolvable Claude executable, but no ready
      local DevTools/native bridge endpoint for no-focus App chat submission
    - next Claude work should attach or create a deterministic App-side bridge
      contract before any real App message send; do not fall back to CLI for
      Claude Desktop requests
  - next concrete actions:
    1. implement/read-only probe Claude Desktop native or DevTools endpoint
       discovery with endpoint-owner validation
    2. if no endpoint exists, prepare an explicit foreground-gated or isolated
       owned App launch path; do not run it by default while the user is
       working
    3. continue WeChat native bridge send and Cursor adaptive bridge rollout as
       separate remaining blockers
- 2026-06-06 R213/R214 current no-loss status and owned App launch-plan hardening:
  - trigger:
    - active goal continuation required more real evidence toward precise
      background operation for the main scenarios without disturbing the
      user's active Cursor/desktop work
    - the R212 Claude App-only report showed that the App DevTools launch
      template still used a relative fallback profile path
  - implementation:
    - changed agent App owned DevTools launch-plan templates so fallback
      `user_data_dir` values are absolute paths under the current major run
      output directory
    - preserved default-profile launch reports as `user_data_dir=""`; only
      isolated owned-profile templates get an absolute owned profile path
    - added regression coverage proving the template path is absolute, under
      the current run directory, mirrored in argv, and not created by a
      read-only report
  - official-doc basis:
    - Python `pathlib` documentation was checked before changing path
      normalization and path composition
  - validation:
    - passed focused tests:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_owned_devtools_launch_plan_template_uses_absolute_owned_profile tests.test_major_real_no_loss.MajorRealNoLossTests.test_endpoint_acceptance_uses_actual_default_profile_devtools_launch_report tests.test_major_real_no_loss.MajorRealNoLossTests.test_report_exposes_agent_app_endpoint_readiness_summary`
    - passed broader regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `71` tests OK
    - R213 Claude App template read-only probe:
      `logs/runtime/major-real-no-loss-r213-claude-app-template-readonly/report.json`
      returned:
      - `safe_run_ok=true`
      - `agent_command_attempts=0`
      - `window_input_attempts=0`
      - `owned_app_launch_attempts=0`
      - `user_data_dir` under
        `logs/runtime/major-real-no-loss-r213-claude-app-template-readonly/agent-app-devtools/claude/profile`
      - profile directory was not created during the read-only report
    - sandboxed default major read-only run:
      `logs/runtime/major-real-no-loss-r213-default-readonly-status/report.json`
      showed Word COM as `word_com_not_available` because COM dispatch failed
      with a missing login session
    - non-sandbox hidden Word COM probe:
      `logs/runtime/word-r213-real-com-escalated/report.json`
      verified Word background document creation/readback with:
      - `decision=word_background_probe_verified`
      - `save_verified=true`
      - `readback_verified=true`
      - `visible_requested=false`
      - foreground stayed on Cursor
      - `window_input_attempts=0`
    - non-sandbox default major no-loss run:
      `logs/runtime/major-real-no-loss-r213-default-readonly-escalated/report.json`
      returned:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `owned_app_launch_attempts=0`
      - `background_screenshot_success_count=3`
      - verified requirements:
        `wechat_background_observation`, `word_background_document`,
        `file_background_search`
    - R214 owned browser + non-Claude CLI no-loss run:
      `logs/runtime/major-real-no-loss-r214-owned-browser-codex-cursor-cli/report.json`
      returned:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `external_communication_attempts=0`
      - `owned_app_launch_attempts=1`
      - `agent_command_attempts=1`
      - `background_screenshot_focus_stable=true`
      - `cli_foreground_no_steal_verified=true`
      - verified requirements:
        `wechat_background_observation`, `word_background_document`,
        `browser_background_research`, `file_background_search`,
        `codex_cli_background_task`
      - final exact process scan for the owned profile/DevTools port found
        zero residual owned browser helper processes
    - `git diff --check` passed with only existing CRLF warnings
  - current conclusion:
    - the current verified objective state is `5/10` requirements:
      WeChat observation, Word hidden COM document, browser owned DevTools,
      file search, and Codex CLI background task
    - the full goal remains incomplete; missing requirements are:
      `wechat_background_send`, `cursor_cli_background_task`,
      `codex_app_background_chat`, `claude_desktop_background_chat`, and
      `cursor_background_chat`
    - Word needs an interactive/non-sandbox session for COM; sandboxed runs can
      report a false negative because Office COM creation may fail with a
      missing login session
    - Claude remains App-only by default; no Claude CLI was run in R213/R214
  - next concrete actions:
    1. WeChat: close background send through native bridge or verified UIA
       semantic sender for File Transfer Assistant only, with marker readback
    2. Cursor: keep active profile protected; finish adaptive IDE bridge
       rollout only via inactive/isolated profile or explicit bridge URL
    3. Codex/Claude App: attach native App-server/CDP bridge endpoint with
       endpoint-owner validation before any real app-side message submission
- 2026-06-06 R215/R216 Claude App-only and WeChat read-only evidence:
  - trigger:
    - user clarified Claude must be treated as an App surface for now, not CLI
    - tests must continue without stealing focus or interrupting active Cursor
  - official-doc basis:
    - checked Microsoft `Get-StartApps` documentation; it returns current-user
      installed app names and AppIDs, which is installation/resolution evidence,
      not proof that a window is running or background-controllable
  - implementation:
    - added App-only status
      `app_installed_not_running_connector_required` for resolved StartApps/MSIX
      desktop shells with no running matched window
    - updated major no-loss requirement mapping so that status is `gated`, not
      `unavailable`, and it does not create or imply a Claude CLI fallback
    - added regression tests covering Agent App status and major requirement
      classification
  - validation:
    - real WeChat read-only/no-focus probe:
      `logs/runtime/primary-r215-wechat-readonly-escalated`
      - `system_dialog_clear`
      - `matching_window_count=2`
      - `background_screenshot_success_count=2`
      - foreground HWND stayed stable
      - `send_attempts=0`, `window_input_attempts=0`
      - current WeChat UIA surface is structure-only; no semantic composer or
        Invoke-ready send control, so native bridge remains required for
        background send
    - real Claude App-only/no-focus probe:
      `logs/runtime/agent-app-r216-claude-app-only-readonly`
      - status `app_installed_not_running_connector_required`
      - StartApps resolved `Claude_pzs8sxrjxfjjc!Claude`
      - no matched Claude window, no endpoint, no background send contract
      - `agent_command_attempts=0`, confirming no CLI fallback
    - real major App-only/no-focus probe:
      `logs/runtime/major-r216-claude-app-only-readonly`
      - `safe_run_ok=true`, `goal_complete=false`
      - `control_attempts=0`, `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `claude_desktop_background_chat` is `gated` with blocking reason
        `app_installed_not_running_connector_required`
    - tests passed:
      `python -m unittest tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `102` tests OK
  - current conclusion:
    - Claude route is correctly App-only; local machine has Claude App
      installation evidence but no running App window or native/background
      connector endpoint
    - WeChat observation is solid and background screenshot-safe, but precision
      send still needs a native WeChat bridge; UIA-only send is not acceptable
      on the observed surface
    - the full goal remains incomplete; no claim of universal precise desktop
      control is justified yet
  - next concrete actions:
    1. implement or attach a per-app native bridge registry endpoint for WeChat
       send to File Transfer Assistant only
    2. add/attach Claude Desktop native/CDP bridge with endpoint-owner and
       session/composer validation before any App message send
    3. keep Cursor active profile protected while fixing adaptive bridge port
       publishing for isolated or explicit bridge routes
- 2026-06-06 R217 Cursor/IDE bridge no-focus safety hardening:
  - trigger:
    - user reported Cursor popup:
      `OpenWukong bridge failed to start: listen EADDRINUSE 127.0.0.1:8787`
    - user also clarified they need to keep using Cursor normally, so active
      Cursor profile must not be patched or restarted
  - official-doc basis:
    - checked Node.js `server.listen(0)` / `server.address().port` behavior for
      OS-assigned unused ports
    - checked VS Code `contributes.configuration` docs for extension setting
      defaults
    - checked Microsoft PowerShell `Get-CimInstance` and `Get-Process`
      documentation for process snapshot fallback design
  - implementation:
    - confirmed repository extension source already defaults to:
      `openwukong.bridge.port=0`, `autoStart=false`,
      `dynamicPortOnConflict=true`, and registry publication of the actual
      bound URL
    - changed IDE extension readiness default so it no longer probes fixed
      `http://127.0.0.1:8787`; it now only probes explicit bridge URLs or
      loopback URLs discovered from the local IDE bridge registry
    - added CLI support for explicit `--bridge-registry-path`
    - fixed IDE extension sync active-process detection:
      - if `Get-CimInstance Win32_Process` is denied, fallback to
        `Get-Process`
      - match `Cursor` / `Code` process names even when they do not include
        `.exe`
      - preserve the no-write guard for active Cursor/VS Code profiles
    - added regressions proving:
      - default readiness does not touch fixed `8787`
      - registry dynamic URLs are probed instead
      - active Cursor is detected even with name `Cursor` and no executable
        path
      - CIM denial falls back to `Get-Process`
  - real no-focus validation:
    - read-only sync audit:
      `logs/runtime/ide-extension-sync-r217-readonly-after-fix/report.json`
      returned:
      - `status=stale_install_detected`
      - current installed Cursor extension path:
        `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0`
      - installed copy is stale:
        `port_default=8787`, `auto_start_default=true`,
        `dynamic_port_on_conflict_declared=false`,
        `source_disruptive_start_popup=true`
      - active Cursor processes detected
      - `active_process_detected=true`
      - `write_attempts=0`, `window_input_attempts=0`
    - default readiness audit now returned quickly with:
      - `bridge_url=""`
      - `bridge_urls=[]`
      - `bridge_ready=false`
      - no fixed-port capability probe
      - status remains `installed_extension_stale` because the installed copy
        is old
    - controlled apply safety gate:
      `logs/runtime/ide-extension-sync-r217-apply-refusal/report.json`
      returned:
      - `status=apply_refused_active_process`
      - `blocking_reason=active_ide_process_detected`
      - `write_attempts=0`, `backup_attempts=0`,
        `window_input_attempts=0`
  - validation:
    - passed:
      `python -m unittest tests.test_ide_extension_readiness tests.test_ide_extension_sync tests.test_ide_bridge_registry tests.test_session_discovery`
      with `25` tests OK
    - passed focused major IDE bridge tests:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_probes_existing_ide_extension_bridge_and_forwards_ready_endpoint tests.test_major_real_no_loss.MajorRealNoLossTests.test_runner_records_unavailable_existing_ide_extension_bridge_without_forwarding`
      with `2` tests OK
    - passed broader regression:
      `python -m unittest tests.test_ide_extension_readiness tests.test_ide_extension_sync tests.test_ide_bridge_registry tests.test_session_discovery tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `97` tests OK
    - `git diff --check` passed with only existing CRLF warnings
  - current conclusion:
    - the Cursor popup root cause is the stale installed Cursor extension, not
      the current repository extension source
    - the source path is now safer by default for future install/sync:
      dynamic port, no auto-start in normal profiles, registry discovery, and
      active-profile write refusal
    - the active Cursor install remains stale because the user is using Cursor;
      this is intentionally not modified until Cursor is inactive or an
      isolated profile is used
    - full objective remains incomplete; this closes the Cursor bridge
      infrastructure safety issue but does not yet prove app-side Cursor chat
      send in a real no-focus session
  - next concrete actions:
    1. when Cursor is inactive, apply the controlled extension sync or use an
       isolated Cursor profile, then verify registry-discovered dynamic bridge
    2. continue Claude Desktop as App-only through native/CDP bridge discovery,
       not CLI
    3. continue WeChat send only through native bridge or a verified semantic
       provider contract; keep UIA-only send blocked on current surface
- 2026-06-06 R218 Claude App-only native connector no-CLI gate:
  - trigger:
    - user clarified Claude must be treated as the desktop/App surface for this
      track, not as `claude` CLI
    - risk found in native connector process matching:
      `claude.exe` is shared by Claude Desktop evidence and Claude Code CLI,
      so a CLI process with a DevTools/listening port could be mis-bound as a
      Claude Desktop endpoint
  - official-doc basis:
    - checked official psutil docs for `process_iter(["pid", "name", "exe",
      "cmdline"])` and process filtering by `name`, `exe`, and `cmdline`
      before modifying process ownership classification
  - implementation:
    - updated native connector process matching to carry the requested agent
      surface into `_matching_agent_processes`
    - reused app-resolution surface classifiers for Codex/Claude/Cursor
      running processes
    - added command-line/path fallback classification for known CLI fragments:
      `.local/bin`, `AppData/Roaming/npm`, Claude Code node module paths,
      Codex local bin paths, and `cursor-agent`
    - for explicit `claude desktop` / `claude app`, reject CLI-classified
      `claude.exe` processes before probing DevTools or listening ports
    - for Claude App requests with only ambiguous process-name evidence and no
      selected desktop directory/window binding, keep the route unbound instead
      of treating a CLI endpoint as an App connector
    - added regression:
      `test_claude_desktop_probe_rejects_claude_code_cli_process_debugger`
      proves a Claude Code CLI process exposing `--remote-debugging-port` is
      not probed as Claude Desktop and leaves window/control attempts at zero
  - real no-focus validation:
    - ran:
      `python -m openwukong.evaluation.agent_app_real_no_loss --agent "claude desktop" --project-name openwukong --task-name desktop-message --output-root logs/runtime/agent-app-r218-claude-app-only-readonly --json`
    - artifact:
      `logs/runtime/agent-app-r218-claude-app-only-readonly/agent_app_real_no_loss/claude_desktop.json`
    - observed:
      - `status=app_surface_not_ready`
      - `decision=agent_app_surface_not_ready`
      - `endpoint_count=0`
      - `ready_endpoint_count=0`
      - `process_count=626`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `bridge_send_attempts=0`
      - `agent_command_attempts=0`
    - conclusion:
      - this machine currently has no ready Claude Desktop/App background
        connector endpoint for the requested project/task
      - the route correctly did not fall back to Claude CLI
  - validation:
    - watched the new focused test fail first with
      `ready_endpoint_count=1`, proving the previous bug
    - passed:
      `python -m unittest tests.test_agent_native_connector_probe`
      with `25` tests OK
    - passed:
      `python -m unittest tests.test_app_resolution`
      with `24` tests OK
    - passed:
      `python -m unittest tests.test_agent_app_real_no_loss`
      with `30` tests OK
    - passed:
      `python -m unittest tests.test_major_real_no_loss`
      with `69` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_app_resolution tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `151` tests OK
    - `git diff --check` passed with only existing CRLF warnings
  - current conclusion:
    - Claude App route is now structurally safer: desktop/App requests cannot
      silently bind to known Claude Code CLI processes or endpoints
    - the overall goal is still not complete; Claude Desktop app-side
      background chat remains gated until a native/App connector or verified
      desktop CDP bridge is present and session/composer readiness passes
  - next concrete actions:
    1. add/read a Claude Desktop native bridge registry or official app-local
       endpoint if available, then validate endpoint owner and composer/session
       readiness before any send
    2. keep WeChat background send on native-bridge path only; UIA-only send
       remains blocked for current observed surface
    3. keep Cursor active profile protected; sync stale extension only when
       Cursor is inactive or an isolated profile is used

- 2026-06-06 R221 Claude App-only launch-plan hardening:
  - trigger:
    - user clarified again that Claude must be treated as App/Desktop for this
      track, temporarily not CLI
    - R219/R220 evidence showed the major no-loss report could still publish a
      Claude Desktop owned-DevTools launch template using a CLI-style
      `.local/bin/Claude.exe` path, and Codex MSIX evidence could still expose
      copyable Electron argv despite being blocked
  - official-doc basis:
    - checked Electron supported command-line switches before deciding when
      `--remote-debugging-port` / `--user-data-dir` launch templates are valid:
      https://www.electronjs.org/docs/latest/api/command-line-switches
    - checked Microsoft AppUserModelID guidance for Windows packaged app
      identity evidence:
      https://learn.microsoft.com/en-us/windows/win32/shell/appids
  - implementation:
    - updated major no-loss agent-app launch planning to classify candidate
      surfaces with the shared app-resolution classifiers before emitting an
      owned DevTools launch plan
    - explicit `claude desktop` / Claude App routes now block CLI-classified
      paths with `agent_app_cli_path_not_background_launchable`
    - WindowsApps/MSIX app evidence is now blocked as
      `msix_windowsapps_not_background_launchable` for owned DevTools launch
      templates
    - blocked launch templates keep evidence fields but force
      `executable_ready=false` and `argv=[]`, so the report cannot be copied
      into a foreground-stealing/error-dialog command
    - the launchable agent-app fleet skips cases classified as CLI/MSIX blocked
      even if an earlier resolution report claimed `executable_ready=true`
  - validation:
    - added failing tests first:
      `test_claude_desktop_devtools_resolution_rejects_cli_executable_path`
      and
      `test_claude_desktop_owned_devtools_template_blocks_cli_executable_path`
    - red result before fix:
      CLI-style Claude executable was incorrectly treated as ready and blocked
      templates lacked the new launch-blocking reason
    - passed focused regression:
      `python -m unittest tests.test_major_real_no_loss.MajorRealNoLossTests.test_claude_desktop_devtools_resolution_rejects_cli_executable_path tests.test_major_real_no_loss.MajorRealNoLossTests.test_claude_desktop_owned_devtools_template_blocks_cli_executable_path tests.test_major_real_no_loss.MajorRealNoLossTests.test_owned_devtools_launch_plan_template_uses_absolute_owned_profile`
      with `3` tests OK
    - passed:
      `python -m unittest tests.test_major_real_no_loss`
      with `71` tests OK
    - passed combined regression:
      `python -m unittest tests.test_major_real_no_loss tests.test_agent_native_connector_probe tests.test_app_resolution tests.test_agent_app_real_no_loss`
      with `150` tests OK
    - `git diff --check` passed with only CRLF-normalization warnings
    - fresh no-loss artifact:
      `logs/runtime/major-r221-current-readiness-app-only-claude/major-real-no-loss-report.json`
    - R221 observed:
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `owned_app_launch_attempts=0`
      - `agent_app_devtools_launch_attempts=0`
      - `system_dialog_clear`
      - Claude Desktop status remained `app_surface_not_ready`
      - Claude template:
        `launch_blocking_reason=agent_app_cli_path_not_background_launchable`,
        `executable_ready=false`, `argv=[]`
      - Codex MSIX template:
        `launch_blocking_reason=msix_windowsapps_not_background_launchable`,
        `argv=[]`
  - current conclusion:
    - Claude App/Desktop route no longer falls back to or exposes a CLI launch
      path in the major no-loss plan
    - the overall objective is still not complete:
      R221 reported `safe_run_ok=false`, `goal_complete=false`,
      `satisfied_count=1`, `gated_count=3`, `unavailable_count=6`
    - the next real milestone is not CLI execution; it is a Claude Desktop
      native/App connector or already-running verified local endpoint with
      target/session/composer readiness and no-focus readback
  - next concrete actions:
    1. add a Claude Desktop App connector discovery contract that only accepts
       loopback/native endpoints owned by the desktop app surface, not CLI
       processes
    2. add a dry-run Claude App message envelope/readback contract before any
       real send path exists
    3. keep Codex WindowsApps/MSIX desktop shell blocked for background
       `thread/start` / `turn/start`; use app-server/native helper only when
       owner identity is non-MSIX and foreground preflight remains clear

- 2026-06-06 R222 Claude native-bridge app-binding guard:
  - trigger:
    - after R221 blocked Claude App launch-plan fallback to CLI, a second
      reusable risk remained: a future native bridge capability report could
      claim `surface_kind=desktop_app` and `process_name=Claude.exe` while its
      `app_binding.executable_path` still pointed to the Claude Code CLI path
      under `.local/bin`
  - implementation:
    - added `app_binding_surface_kind` to agent-native connector endpoint
      metadata
    - classified native bridge `app_binding` with the same shared
      app-resolution surface classifiers used for process discovery
    - explicit desktop_app native bridge requests now reject
      `app_binding_surface_kind=cli` as
      `agent_native_bridge_app_binding_not_ready`
    - preserved rejected binding path metadata for audit while keeping endpoint
      readiness false and send/native attempts at zero
  - validation:
    - added failing regression first:
      `test_claude_desktop_native_bridge_rejects_cli_app_binding_path`
    - red result before fix:
      a fake Claude native bridge with `surface_kind=desktop_app`,
      `process_name=Claude.exe`, and
      `executable_path=C:/Users/me/.local/bin/claude.exe` was incorrectly
      accepted as `ok=true`
    - passed focused regression and adjacent bridge tests:
      `python -m unittest tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_claude_desktop_native_bridge_rejects_cli_app_binding_path tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_reports_ready_agent_native_bridge_endpoint_from_explicit_bridge_url tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_agent_native_bridge_endpoint_does_not_accept_cli_surface_for_app tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_agent_native_bridge_endpoint_requires_matching_app_binding`
      with `4` tests OK
    - passed related regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss`
      with `127` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_app_resolution tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `154` tests OK
    - real Claude App-only native connector probe artifact:
      `logs/runtime/agent-native-r222-claude-app-only/claude_desktop.json`
    - probe observed:
      - `decision=agent_app_surface_not_ready`
      - `endpoint_count=0`
      - `ready_endpoint_count=0`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `computer_use_decision=computer_use_client_missing`
      - only Claude CLI paths under `.local/bin` were discovered; they were
        not accepted as Claude Desktop/App
    - fresh major no-loss artifact:
      `logs/runtime/major-r222-current-readiness-after-claude-binding-guard/major-real-no-loss-report.json`
    - R222 major observed:
      - `safe_run_ok=false`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `owned_app_launch_attempts=0`
      - `agent_app_devtools_launch_attempts=0`
      - `system_dialog_clear`
      - Claude launch template remained blocked:
        `agent_app_cli_path_not_background_launchable`, `argv=[]`
      - Codex MSIX launch template remained blocked:
        `msix_windowsapps_not_background_launchable`, `argv=[]`
      - objective summary stayed:
        `satisfied_count=1`, `gated_count=3`, `unavailable_count=6`
    - `git diff --check` passed with only CRLF-normalization warnings
  - reusable pattern captured:
    - updated global skill:
      `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
    - added trigger, diagnosis, required fix, regression test, and completion
      standard for App bridge binding masquerading as CLI
  - current conclusion:
    - Claude App/Desktop is now protected at both launch-plan and native-bridge
      app-binding layers
    - this still does not mean Claude App background messaging is complete;
      the machine currently lacks a verified Claude Desktop native/App
      connector endpoint and visible target/session/composer readiness
  - next concrete actions:
    1. build the Claude Desktop App connector discovery contract against a real
       desktop extension/native endpoint shape, still App-only and loopback-only
    2. add a Claude App dry-run message envelope/readback contract once a
       desktop endpoint exists
    3. keep all real sends disabled until target/session/composer readiness and
       no-focus readback are proven

- 2026-06-06 R223 Claude native-bridge name-only binding guard:
  - trigger:
    - R222 protected explicit CLI paths in native bridge `app_binding`, but a
      narrower endpoint-readiness risk remained:
      if a bridge capability report only exposed `process_name=Claude.exe` and
      `window_title=Claude`, without a desktop-classified executable path or a
      UIA-matched pid/hwnd, the endpoint could still be counted as ready when
      the Claude App target was not visible
  - implementation:
    - tightened `_agent_native_bridge_app_binding_ok`
    - for explicit `desktop_app` requests, app binding now needs strong
      ownership evidence:
      desktop-classified binding path, or independently matched UIA pid/hwnd
    - name-only bindings are no longer sufficient for endpoint readiness
    - endpoint metadata `app_binding_ready` is now overwritten with the strict
      binding decision, not the bridge's softer self-report
  - validation:
    - first test attempt for the visible-window case passed immediately,
      proving existing UIA pid/hwnd matching already covered that scenario
    - added the actual failing regression:
      `test_claude_desktop_native_bridge_without_visible_target_rejects_name_only_app_binding`
    - red result before fix:
      a fake Claude Desktop native bridge with only
      `process_name=Claude.exe` / `window_title=Claude` was counted as
      `ready_endpoint_count=1`
    - after the fix, passed focused regression set:
      `python -m unittest tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_claude_desktop_native_bridge_without_visible_target_rejects_name_only_app_binding tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_claude_desktop_native_bridge_rejects_name_only_app_binding tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_claude_desktop_native_bridge_rejects_cli_app_binding_path tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_reports_ready_agent_native_bridge_endpoint_from_explicit_bridge_url tests.test_agent_native_connector_probe.AgentNativeConnectorProbeTests.test_discovers_agent_native_bridge_endpoint_from_registry_file`
      with `5` tests OK
    - passed:
      `python -m unittest tests.test_agent_native_connector_probe`
      with `28` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_connector_probe tests.test_app_resolution tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `156` tests OK
    - real Claude App-only native connector probe artifact:
      `logs/runtime/agent-native-r223-claude-app-only/claude_desktop.json`
    - probe observed:
      - `decision=agent_app_surface_not_ready`
      - `endpoint_count=0`
      - `ready_endpoint_count=0`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `computer_use_decision=computer_use_client_missing`
      - `app_resolution_decision=not_found`
    - fresh major no-loss artifact:
      `logs/runtime/major-r223-current-readiness-after-name-only-bridge-guard/major-real-no-loss-report.json`
    - R223 major observed:
      - `safe_run_ok=false`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `owned_app_launch_attempts=0`
      - `agent_app_devtools_launch_attempts=0`
      - `system_dialog_clear`
      - Claude App launch template stayed blocked:
        `agent_app_cli_path_not_background_launchable`, `argv=[]`
      - Codex MSIX launch template stayed blocked:
        `msix_windowsapps_not_background_launchable`, `argv=[]`
      - objective summary remained:
        `satisfied_count=1`, `gated_count=3`, `unavailable_count=6`
    - `git diff --check` passed with only CRLF-normalization warnings
  - reusable pattern updated:
    - updated global skill:
      `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
    - added the rule that name-only app bindings are not sufficient unless
      backed by a desktop-classified executable path or independently matched
      UIA pid/hwnd
  - current conclusion:
    - Claude App/Desktop endpoint discovery is now stricter:
      it rejects CLI paths and rejects name-only bridge bindings
    - background Claude App messaging is still incomplete until a real verified
      desktop/native endpoint exists with target/session/composer/readback
      readiness
  - next concrete actions:
    1. model the Claude Desktop extension/native endpoint capability shape and
       add a dry-run message envelope contract for that shape
    2. keep real Claude sends disabled until endpoint ownership, target
       visibility/session identity, composer readiness, and readback markers
       are proven
    3. continue moving the same strong binding rule into other app connectors
       where endpoint ownership can otherwise be inferred from names alone

- 2026-06-06 R224 core native-bridge dry-run App binding guard:
  - trigger:
    - user clarified Claude must be treated as the App/Desktop surface for now,
      not CLI
    - R222/R223 had hardened endpoint discovery, but the core
      `agent_native_bridge` dry-run adapter itself could still accept a
      direct bridge capability report that claimed `surface_kind=desktop_app`
      while binding to the Claude CLI path or only self-reporting
      `process_name=Claude.exe` / `window_title=Claude`
  - implementation:
    - moved the strong App binding rule into
      `src/openwukong/control/agent_native_bridge.py`
    - core dry-run now classifies bridge `app_binding` with the shared
      Claude/Codex/Cursor surface classifiers and command-line/path fragments
    - explicit `desktop_app` dry-run requests reject CLI bindings such as
      `.local/bin/claude.exe`, `AppData/Roaming/npm`, Claude Code module
      paths, `cursor-agent`, and known agent CLI helper paths
    - explicit `desktop_app` dry-run requests also reject name-only bindings
      unless backed by a desktop-classified executable path or an independently
      matched expected pid/hwnd
    - the positive native-bridge fixture now includes a desktop-classified
      Codex executable path instead of relying on name-only self-report
  - validation:
    - official documentation checked before editing:
      Claude Desktop Extensions/MCPB documentation and Microsoft UI Automation
      documentation
    - added failing regressions first:
      `test_dry_run_rejects_claude_desktop_bridge_bound_to_cli_path`
      and
      `test_dry_run_rejects_claude_desktop_bridge_with_name_only_binding`
    - red result before fix:
      both direct dry-run cases returned `ok=true`
    - after the fix, focused red-green command passed:
      `python -m unittest tests.test_agent_native_bridge.AgentNativeBridgeTests.test_dry_run_rejects_claude_desktop_bridge_bound_to_cli_path tests.test_agent_native_bridge.AgentNativeBridgeTests.test_dry_run_rejects_claude_desktop_bridge_with_name_only_binding`
      with `2` tests OK
    - passed:
      `python -m unittest tests.test_agent_native_bridge`
      with `9` tests OK
    - passed adjacent regression:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_app_real_no_loss`
      with `67` tests OK
    - passed combined regression:
      `python -m unittest tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_app_resolution tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix`
      with `165` tests OK
    - real Claude App-only native connector probe artifact:
      `logs/runtime/agent-native-r224-claude-app-core-contract/claude_desktop.json`
    - probe observed:
      - `decision=agent_app_surface_not_ready`
      - `endpoint_count=0`
      - `ready_endpoint_count=0`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `computer_use_decision=computer_use_client_missing`
      - `app_resolution_decision=not_found`
    - fresh major no-loss artifact:
      `logs/runtime/major-r224-current-readiness-core-native-bridge-contract/major-real-no-loss-report.json`
    - R224 major observed:
      - `safe_run_ok=false`
      - `goal_complete=false`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `agent_command_attempts=0`
      - `owned_app_launch_attempts=0`
      - `agent_app_devtools_launch_attempts=0`
      - `system_dialog_clear`
      - Claude App status stayed `app_surface_not_ready`
      - Claude launch template stayed blocked as
        `agent_app_cli_path_not_background_launchable` with `argv=[]`
      - objective summary stayed:
        `satisfied_count=1`, `gated_count=3`, `unavailable_count=6`
  - reusable pattern updated:
    - updated global skill:
      `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
    - added the rule that direct native-bridge dry-run callers must enforce
      the same CLI/name-only App binding guard as endpoint discovery
  - current conclusion:
    - Claude CLI is no longer an acceptable substitute for Claude App/Desktop
      in launch planning, endpoint discovery, or direct native bridge dry-run
    - Claude App background messaging is still incomplete until a real
      Claude Desktop/native extension endpoint exists and proves endpoint
      ownership, target/session/composer readiness, readback markers, and
      no-focus stability
  - next concrete actions:
    1. build a Claude Desktop extension/native endpoint fixture that mirrors
       MCPB/local desktop extension ownership and capability shape
    2. add the Claude App dry-run message envelope/readback contract against
       that fixture, with send attempts still forced to zero
    3. keep all real Claude App sends disabled until real endpoint ownership
       and no-focus readback are proven

- 2026-06-07 R227 dynamic helper ports and focus-risk classification:
  - trigger:
    - user reported Cursor extension popup:
      `OpenWukong bridge failed to start: listen EADDRINUSE 127.0.0.1:8787`
    - user asked to use dynamic unused ports so normal Cursor work is not
      interrupted
  - implementation:
    - browser helper defaults to `--remote-debugging-port=0` and reads the
      actual Chrome DevTools endpoint from `DevToolsActivePort`
    - browser CDP WebSocket client omits the browser-style `Origin` header so
      Chromium does not reject non-allowlisted loopback automation clients
    - IDE bridge source already defaults to dynamic port `0`, silently handles
      port conflicts, and publishes the actual bound port through the local
      OpenWukong IDE bridge registry
    - session readiness planning now also defaults `ide_bridge_port=0`
    - session readiness execution now resolves an isolated IDE bridge dynamic
      port from the local registry instead of recording
      `http://127.0.0.1:0`
    - CLI `openwukong.evaluation.session_readiness_plan --ide-bridge-port`
      now defaults to `0`; fixed ports are explicit isolated-profile choices
    - background screenshot focus reporting now distinguishes:
      `stable`, `external_focus_change`, `target_lost_focus`, and
      `changed_to_target_window`
    - only `changed_to_target_window` is treated as automation focus risk, so
      user-driven focus changes during long no-loss probes do not falsely fail
      the run
  - validation:
    - added failing tests first for:
      - browser dynamic DevTools port readback
      - browser helper defaulting to `--remote-debugging-port=0`
      - CDP WebSocket client omitting `Origin`
      - IDE bridge plan defaulting to dynamic port
      - isolated IDE bridge execution reading the real port from registry
      - CLI IDE bridge defaulting to dynamic port
      - background screenshot external focus changes not counting as focus risk
    - focused dynamic-port tests passed:
      `python -m unittest tests.test_session_readiness_plan.SessionReadinessPlanTests.test_ide_bridge_plan_defaults_to_dynamic_port tests.test_session_readiness_plan.SessionReadinessPlanTests.test_execute_dynamic_ide_bridge_reads_registry_port_after_launch tests.test_session_readiness_plan.SessionReadinessPlanTests.test_cli_ide_bridge_defaults_to_dynamic_port`
      with `3` tests OK
    - passed:
      `python -m unittest tests.test_session_readiness_plan`
      with `35` tests OK
    - passed focus/real no-loss related regression:
      `python -m unittest tests.test_primary_real_no_loss tests.test_agent_app_uia_probe tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_window_capture`
      with `127` tests OK
    - passed combined dynamic-port/browser/IDE regression:
      `python -m unittest tests.test_session_readiness_plan tests.test_primary_scenario_smoke tests.test_primary_real_no_loss tests.test_major_real_no_loss tests.test_browser_connector tests.test_browser_devtools_health tests.test_control_fabric_browser_workflow tests.test_ide_extension_scaffold tests.test_ide_extension_readiness tests.test_ide_extension_sync tests.test_ide_bridge_registry`
      with `171` tests OK
    - `git diff --check` passed with only CRLF-normalization warnings
    - fresh real no-loss artifact:
      `logs/runtime/major-r227-dynamic-ports-focus-classified/major-real-no-loss-report.json`
    - R227 real observed:
      - `safe_run_ok=true`
      - `goal_complete=false`
      - `automation_focus_safe=true`
      - `background_screenshot_focus_stable=true`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `owned_app_launch_attempts=1`
      - browser helper command used `--remote-debugging-port=0`
      - browser helper actual endpoint was `http://127.0.0.1:55346`
      - browser readback marker:
        `OPENWUKONG_DYNAMIC_PORTS_R227`
      - browser helper stopped and isolated profile cleanup succeeded
      - objective summary:
        `satisfied_count=4`, `gated_count=3`, `unavailable_count=3`
  - current conclusion:
    - fixed-port collision should no longer be part of the owned helper or
      isolated IDE bridge default path
    - if the user's active Cursor still shows the `8787` popup, the installed
      extension copy is stale; run read-only `ide_extension_readiness` or
      controlled `ide_extension_sync`, but do not overwrite an active Cursor
      profile unless explicitly allowed
    - browser search/readback through an owned helper is now truly dynamic-port,
      background-safe, and cleanup-backed
    - this still does not mean every app can be precisely controlled:
      remaining unsatisfied requirements are
      `wechat_background_send`, `codex_cli_background_task`,
      `cursor_cli_background_task`, `codex_app_background_chat`,
      `claude_desktop_background_chat`, and `cursor_background_chat`
  - next concrete actions:
    1. audit the active installed Cursor extension read-only and report whether
       it is stale, without touching the active profile
    2. keep WeChat real send behind `File Transfer Assistant` plus native bridge
       or verified UIA send/readback/no-focus gates
    3. build App/Desktop native endpoint contracts for Codex and Claude instead
       of falling back to CLI or MSIX foreground launch

- 2026-06-07 R228 dynamic IDE URL defaults plus process-only app visibility:
  - trigger:
    - user clarified that bridge ports should dynamically use an unused port
      instead of fixed values, because normal Cursor work must not be
      interrupted
  - implementation:
    - added `openwukong.evaluation.ide_bridge_url_resolution` so Cursor probe
      CLIs can resolve the actual IDE bridge URL from the local registry when
      `--bridge-url` is omitted
    - changed Cursor draft-hook, live-composer-state, draft-hook-validation,
      and attach-bridge-validation CLIs away from fixed `8787` defaults
    - changed IDE contract probe settings builders and `--settings-port`
      default to `0`
    - changed owned IDE bridge helper default from fixed `8791` to `0`, then
      uses the launch report's actual `readiness_url` for capability capture,
      contract probe, and downstream agent app routing
    - changed isolated Cursor draft-hook runner default from fixed `8797` to
      `0`, then uses the launch report's actual dynamic URL for readiness and
      validation
    - updated CLI help text to avoid recommending fixed `8787` examples
    - added a process-only read-only fallback in `accessibility_probe` so
      running important apps such as `Weixin.exe`, `Cursor.exe`, `Codex.exe`,
      `claude.exe`, and `winword.exe` are still visible when no accessible
      top-level window is exposed
  - validation:
    - TDD red observed for:
      - CLI omitted `--bridge-url` still probing fixed `8787`
      - probe settings defaulting to `8787`
      - owned helper reporting `http://127.0.0.1:0`
      - isolated Cursor runner reporting `http://127.0.0.1:0`
    - focused tests then passed:
      `python -m unittest tests.test_cursor_draft_hook_probe tests.test_ide_bridge_contract_probe.IDEBridgeContractProbeTests.test_probe_allowlist_settings_defaults_to_dynamic_port tests.test_ide_bridge_contract_probe.IDEBridgeContractProbeTests.test_validated_bridge_settings_default_to_dynamic_port tests.test_ide_bridge_contract_probe.IDEBridgeContractProbeTests.test_cli_can_write_probe_settings_without_contacting_bridge tests.test_major_real_no_loss.MajorRealNoLossTests.test_prepare_owned_ide_bridge_helper_uses_dynamic_launch_readiness_url`
      with `8` tests OK
    - isolated Cursor runner dynamic-port test passed:
      `python -m unittest tests.test_cursor_isolated_draft_hook_runner.CursorIsolatedDraftHookRunnerTests.test_runner_launches_isolated_cursor_profile_validates_and_stops`
      with `1` test OK
    - related regression passed:
      `python -m unittest tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss`
      with `150` tests OK
    - accessibility fallback focused regression passed:
      `python -m unittest tests.test_accessibility_probe tests.test_wechat_locator tests.test_primary_real_no_loss`
      with `27` tests OK
    - read-only live Cursor extension readiness:
      - `status=installed_extension_stale`
      - installed path:
        `C:\Users\Zhangjinqian\.cursor\extensions\openwukong-local.openwukong-vscode-bridge-0.1.0`
      - installed copy still has `port_default=8787`,
        `auto_start_default=true`, no dynamic fallback, and disruptive popup
        source
    - controlled sync audit stayed read-only:
      - `status=stale_install_detected`
      - `write_attempts=0`
      - `backup_attempts=0`
      - active Cursor processes detected, so no active profile update was
        attempted
    - `git diff --check` passed with only CRLF-normalization warnings
  - current conclusion:
    - repo/source defaults now use dynamic unused ports for IDE bridge helper
      paths; fixed ports are explicit only
    - current user-facing Cursor popup is from the stale installed extension
      copy, not the repo source
    - because Cursor is actively in use, updating the installed extension must
      remain a controlled operation and should not be done implicitly
    - WeChat is now read-only visible through process-only fallback when UIA
      exposes no top-level window, but background send still remains blocked
      until a native bridge or verified semantic UIA target is available
  - next concrete actions:
    1. when the user is ready or Cursor is closed, run controlled IDE extension
       sync to replace the stale installed Cursor bridge with the dynamic-port
       source copy
    2. continue WeChat background send through a deterministic native bridge
       or verified UIA semantic target, not blind visual/keyboard fallback
    3. continue Codex/Claude App native endpoint contracts and avoid MSIX
       foreground/protocol launches that create system dialogs

- 2026-06-07 R229 agent-app route correction plus dynamic-port confirmation:
  - trigger:
    - user reiterated that bridge ports should dynamically use an unused port
      and asked whether WeChat/app routes are implemented without disrupting
      normal Cursor work
  - implementation:
    - kept Cursor as an IDE route but moved `codex.exe` out of the IDE process
      family and into an explicit `agent-app` family with `claude.exe`
    - added `agent-app` route policy:
      `app-native-bridge-required` with `block_until_deterministic_route`
      until a verified app/native endpoint exists
    - updated accessibility readiness so process-only `claude.exe` and
      `codex.exe` are visible and recommended through
      `app-native-bridge-required`, not generic desktop or IDE bridge
    - updated WeChat/IM process-only recommended routes so `Weixin.exe`,
      `wechat.exe`, and `wxwork.exe` also report
      `app-native-bridge-required` before MSAA/vision fallback
    - corrected primary scenario smoke so Codex desktop App no longer writes a
      fake successful IDE-extension execution artifact; it now remains a
      dry-run/gated task until a real native bridge exists
  - validation:
    - related route/accessibility/profile regression passed:
      `python -m unittest tests.test_accessibility_probe tests.test_transport_capability_matrix tests.test_universal_app_profile tests.test_primary_scenario_smoke tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe`
      with `127` tests OK
    - full related dynamic-port/major-scenario/agent-app regression passed:
      `python -m unittest tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_primary_scenario_smoke tests.test_session_registry_report tests.test_transport_capability_matrix tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_connector_probe`
      with `286` tests OK
    - read-only live accessibility probe observed:
      - `claude.exe`: `agent-app`, `app-native-bridge-required`,
        `block_until_deterministic_route`
      - `codex.exe`: `agent-app`, `app-native-bridge-required`,
        `block_until_deterministic_route`
      - `Cursor.exe`: `ide`, `ide-extension-connector`,
        `prefer_deterministic_connector`
      - `Weixin.exe`: `im`, `app-native-bridge-required`,
        `block_until_deterministic_route`
    - source scan for fixed default bridge ports only found the diagnostic stale
      extension detector in `ide_extension_readiness.py`
    - `git diff --check` passed with CRLF-normalization warnings only
  - current conclusion:
    - dynamic unused-port behavior is implemented in repo/source defaults for
      IDE/browser owned helper paths; the active Cursor popup is from a stale
      installed extension copy, not the current repo source
    - WeChat has real prior send verification and is now classified correctly,
      but current safe/background policy still blocks process-only WeChat until
      native bridge or verified semantic target is available
    - Codex/Claude desktop Apps are now deliberately blocked from fake IDE
      execution and require a native/app bridge; this is stricter and closer to
      the target architecture
  - next concrete actions:
    1. implement or bind a real `agent-native-bridge` connector for Codex and
       Claude desktop App sessions
    2. implement WeChat native bridge/readback registry so `File Transfer
       Assistant` send can be repeated as a deterministic background-safe route
    3. when Cursor is idle or explicitly allowed, sync the installed Cursor
       extension from repo source so the stale fixed `8787` popup disappears

- 2026-06-07 R230 agent-native bridge becomes a real Fabric connector:
  - trigger:
    - goal continuation required moving Codex/Claude desktop App routes from
      "recognized but blocked" toward true background execution through a
      deterministic native endpoint
  - implementation:
    - added `ConnectorTarget.agent_native_bridge_url` so native agent App
      endpoints are first-class routing targets instead of being overloaded
      onto IDE bridge URLs
    - added `AgentNativeBridgeConnector` with route id
      `app-native-bridge-required` and connector id `agent-native-bridge`
    - registered `AgentNativeBridgeConnector` in the default Fabric connector
      manager
    - changed Fabric routing so:
      - Codex/Claude/Cursor agent targets with no native endpoint report
        `connector_required` with candidate `agent-native-bridge`
      - owned targets with `agent_native_bridge_url` can execute through the
        native bridge without window input, keyboard input, clipboard writes, or
        foreground takeover
      - weak non-agent App surfaces such as generic Electron or WeChat are not
        falsely assigned to the agent-native connector; they remain blocked or
        foreground/native-gated until a target-specific connector exists
    - changed transport capability so `app-native-bridge-required` maps to a
      background-native `agent-native-bridge` transport, while connector
      readiness remains a Fabric/session ownership responsibility
    - added ownership matching for `app-native-bridge-required` against
      `agent_native_bridge_url`
    - corrected the real terminal connector regression test to use a workspace
      temp directory because the current sandbox denied PowerShell access to the
      default system temp short path
  - validation:
    - TDD red observed:
      - default runtime returned `blocked` instead of `connector_required` for
        Codex App native route
      - `ConnectorTarget` had no `agent_native_bridge_url`
      - Fabric could not execute an owned native agent bridge endpoint
    - focused tests passed:
      `python -m unittest tests.test_control_fabric.ControlFabricTests.test_default_runtime_requires_agent_native_endpoint_for_codex_app tests.test_control_fabric_execution.ControlFabricExecutionTests.test_execute_runs_owned_agent_native_bridge_without_window_input`
      with `2` tests OK
    - related regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_primary_scenario_smoke`
      with `78` tests OK
    - broad related regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_primary_scenario_smoke tests.test_session_registry_report tests.test_transport_capability_matrix tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_native_connector_probe`
      with `324` tests OK
    - read-only live accessibility probe still observed the real current state:
      `claude.exe`, `codex.exe`, and `Weixin.exe` have no exposed native
      endpoint yet and remain `app-native-bridge-required` /
      `block_until_deterministic_route`; `Cursor.exe` remains
      `ide-extension-connector`
    - `git diff --check` passed with CRLF-normalization warnings only
  - current conclusion:
    - the architecture now has a real Fabric execution path for background
      Codex/Claude desktop App control when a verified native bridge endpoint is
      available
    - current live Codex/Claude Apps on this machine still do not expose that
      endpoint, so real desktop App sends correctly remain gated
    - the next bottleneck is no longer Fabric routing; it is endpoint binding:
      discovering, launching, or installing the actual Codex/Claude native App
      bridge without using foreground protocol launchers or stale fixed ports
  - next concrete actions:
    1. add an agent-native bridge registry/launcher path that can publish
       `agent_native_bridge_url` for owned Codex/Claude desktop App sessions
    2. connect `agent_native_connector_probe` ready endpoints to Fabric
       ownership records so successful probe output can be executed directly
    3. implement the equivalent WeChat native connector/registry instead of
       treating WeChat as an agent-native target

- 2026-06-07 R231 agent-native probe output binds directly into Fabric:
  - trigger:
    - successful `agent_native_connector_probe` endpoint discovery needed to
      become an executable Fabric-owned session instead of staying as an
      isolated report
  - implementation:
    - added `openwukong.control.agent_native_probe_binding`
    - added `AgentNativeFabricBinding`
    - added `agent_native_fabric_bindings_from_probe_report(...)`
    - added `ownership_index_from_agent_native_probe_report(...)`
    - probe endpoints with `endpoint_type=agent_native_bridge`,
      `ready=true`, and a local `bridge_url` are converted into:
      - `ConnectorTarget.agent_native_bridge_url`
      - `SessionOwnership` with
        `route_id=app-native-bridge-required`
      - `connector_id=agent-native-bridge`
      - owned workspace/project/task metadata from endpoint binding fields
    - exported the binding helpers through `openwukong.control`
  - validation:
    - focused binding test passed:
      `python -m unittest tests.test_agent_native_probe_binding`
      with `1` test OK
    - import smoke passed for:
      `AgentNativeFabricBinding`,
      `agent_native_fabric_bindings_from_probe_report`, and
      `ownership_index_from_agent_native_probe_report`
    - broad related regression later passed under R232 with `331` tests OK
  - current conclusion:
    - when a verified agent native bridge endpoint exists, probe output can now
      become an owned Fabric target and execute through
      `agent-native-bridge` without keyboard, clipboard, window input, or
      foreground takeover
    - current live Codex/Claude desktop Apps still do not expose such an
      endpoint, so live app sends remain correctly gated
  - next concrete actions:
    1. publish or discover real Codex/Claude desktop App native bridge
       endpoints without MSIX/protocol foreground launch
    2. add equivalent WeChat native bridge/readback registry binding
    3. run no-loss real tests only after endpoint ownership is proven

- 2026-06-07 R232 all owned helper defaults use dynamic unused ports:
  - trigger:
    - user clarified that ports should dynamically use unoccupied loopback
      ports instead of fixed values
    - remaining fixed defaults still existed for agent app DevTools and
      agent-native CDP bridge helper paths
  - implementation:
    - kept IDE bridge source default at `openwukong.bridge.port=0`
    - kept browser helper default at `--remote-debugging-port=0`
    - changed `SessionReadinessPlanOptions.agent_app_debug_port` default from
      `9555` to `0`
    - changed `SessionReadinessPlanOptions.agent_bridge_port` default from
      `18888` to `0`
    - changed CLI defaults in:
      - `openwukong.evaluation.session_readiness_plan`
      - `openwukong.evaluation.major_real_no_loss`
    - `agent-app-devtools-owned` now publishes an empty readiness URL while
      configured for port `0`, then execution reads the actual endpoint from
      `DevToolsActivePort`
    - `agent-native-cdp-bridge` now publishes an empty readiness URL while
      configured for port `0`, then execution reads the actual endpoint from
      the native bridge registry after the helper binds
    - `prepare_agent_native_cdp_bridge_helper(...)` now reads the launched
      dynamic bridge URL from the launch report before waiting for registry
      readiness
    - fleet normalization now allows `bridge_port=0` as a valid dynamic helper
      spec
    - agent app DevTools fleet/template defaults now also use dynamic port `0`
      and never publish `http://127.0.0.1:0`
  - validation:
    - TDD red observed before fix:
      - agent native CDP helper default published
        `http://127.0.0.1:18888`
      - dynamic agent native execution reported `http://127.0.0.1:0`
      - agent app DevTools default published `http://127.0.0.1:9555`
      - dynamic agent app execution reported `http://127.0.0.1:0`
    - focused new dynamic-port tests passed with `4` tests OK
    - full `session_readiness_plan` suite passed:
      `python -m unittest tests.test_session_readiness_plan`
      with `41` tests OK
    - major/agent bridge regression passed:
      `python -m unittest tests.test_major_real_no_loss tests.test_primary_scenario_smoke tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_native_probe_binding`
      with `116` tests OK
    - broad related control/readiness/accessibility regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_primary_scenario_smoke tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_session_registry_report tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_native_probe_binding`
      with `331` tests OK
    - source scan found no remaining fixed defaults in
      `major_real_no_loss.py` for `19555`, `18890`, `18891`, or `18892`
    - source/test scan found no `http://127.0.0.1:0` publication in the
      touched readiness and major scenario paths
    - read-only live accessibility probe observed:
      - `claude.exe`, `codex.exe`, and `Weixin.exe` remain
        `app-native-bridge-required` / `block_until_deterministic_route`
      - `Cursor.exe` remains `ide-extension-connector` /
        `prefer_deterministic_connector`
      - `control_attempts=0`
    - `git diff --check` passed with CRLF-normalization warnings only
  - current conclusion:
    - source-side owned helper defaults now consistently use OS-assigned
      unused loopback ports across browser, IDE, agent app DevTools, and
      agent-native CDP bridge helpers
    - fixed ports are still supported only when explicitly provided for an
      isolated test/profile
    - the active Cursor fixed-8787 popup, if it still appears, is from the
      stale installed Cursor extension copy, not the current repo source
  - next concrete actions:
    1. when Cursor is idle or explicitly allowed, run controlled extension sync
       so the installed copy also gets the dynamic-port source
    2. continue Codex/Claude App endpoint publication/discovery so
       `agent-native-bridge` can be used live
    3. continue WeChat native bridge/readback registry so prior send success
       becomes repeatable and background-safe

- 2026-06-07 R233 WeChat native bridge is a first-class Fabric connector:
  - trigger:
    - goal continuation required moving WeChat from a one-off native bridge
      contract toward the same unified ControlFabric execution path used by
      browser/IDE/agent-native routes
  - implementation:
    - added `ConnectorTarget.wechat_native_bridge_url`
    - added `ConnectorTarget.conversation_name`
    - added background screenshot evidence fields to `ConnectorTarget`:
      `background_screenshot_focus_stable`,
      `background_screenshot_count`, and
      `background_screenshot_success_count`
    - added `WeChatNativeBridgeConnector`
      - connector id: `wechat-native-bridge`
      - route id: `app-native-bridge-required`
      - sends through `WeChatNativeBridgeSenderAdapter`
      - refuses readiness unless a local WeChat native URL, target
        conversation name, and background screenshot evidence are present
      - does not use keyboard, mouse, clipboard, SendInput, or foreground
        takeover
    - registered `WeChatNativeBridgeConnector` in the default Fabric connector
      manager ahead of the generic agent-native connector
    - extended Fabric route candidates for `app-native-bridge-required` to
      include both:
      - `agent-native-bridge` for Codex/Claude/Cursor agent apps
      - `wechat-native-bridge` for WeChat/Weixin targets
    - extended `SessionOwnershipIndex` so owned WeChat native bridge sessions
      match by `wechat_native_bridge_url`
    - added `openwukong.control.wechat_native_fabric_binding`
      - `WeChatNativeFabricBinding`
      - `wechat_native_fabric_bindings_from_registry(...)`
      - `ownership_index_from_wechat_native_bridge_registry(...)`
      - converts discovered WeChat native registry URLs into Fabric targets and
        owned session records
    - exported WeChat native Fabric binding helpers through
      `openwukong.control`
  - validation:
    - TDD red observed:
      - `ConnectorTarget` rejected `conversation_name`
      - no `wechat_native_fabric_binding` module existed
      - Fabric had no WeChat native connector candidate
    - focused WeChat Fabric tests passed:
      `python -m unittest tests.test_control_fabric_execution.ControlFabricExecutionTests.test_wechat_native_bridge_requires_background_screenshot_evidence tests.test_control_fabric_execution.ControlFabricExecutionTests.test_execute_runs_wechat_native_bridge_without_window_input`
      with `2` tests OK
    - registry-to-Fabric binding passed:
      `python -m unittest tests.test_wechat_native_fabric_binding`
      with `1` test OK
    - WeChat/Fabric/ownership related regression passed:
      `python -m unittest tests.test_control_fabric_execution tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding tests.test_session_ownership`
      with `32` tests OK
    - primary/transport related regression passed:
      `python -m unittest tests.test_transport_capability_matrix tests.test_primary_transport_matrix tests.test_primary_scenario_smoke tests.test_agent_native_probe_binding`
      with `16` tests OK
    - broad related regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_primary_scenario_smoke tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_session_registry_report tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_native_probe_binding tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding`
      with `340` tests OK
    - import smoke passed:
      `WeChatNativeBridgeConnector`,
      `WeChatNativeFabricBinding`,
      `wechat_native_fabric_bindings_from_registry`, and
      `ownership_index_from_wechat_native_bridge_registry`
    - read-only live accessibility probe still observed:
      - real `Weixin.exe` is process-only/window-only in the current desktop
      - no live WeChat native endpoint is registered
      - route remains `app-native-bridge-required` /
        `block_until_deterministic_route`
      - `control_attempts=0`
    - `git diff --check` passed with CRLF-normalization warnings only
  - current conclusion:
    - WeChat now has the same unified background execution path as the agent
      native bridge path when a verified local WeChat native bridge endpoint
      exists
    - unlike the prior one-off send probe, Fabric execution now requires:
      native endpoint ownership, target conversation identity, and background
      screenshot evidence before send
    - current real WeChat on this desktop still lacks a registered native
      endpoint, so live WeChat sends remain correctly gated
  - next concrete actions:
    1. implement or install a real WeChat native endpoint publisher that writes
       `wechat-native-bridges.json` with a dynamic local URL
    2. connect the real publisher to `File Transfer Assistant` readback and
       background screenshot capture so the Fabric target can be built from
       evidence instead of manual fields
    3. continue Codex/Claude desktop App endpoint publication/discovery so the
       existing `agent-native-bridge` path becomes live

- 2026-06-07 R234 WeChat native endpoint publisher added with dynamic port readiness:
  - trigger:
    - continuation of the full desktop-control goal, focusing on replacing
      one-off WeChat bridge fixtures with a reusable background endpoint
      publisher that uses unused loopback ports and registry discovery
  - docs consulted before code changes:
    - official Python `http.server` documentation for `ThreadingHTTPServer`
    - official Python `socketserver` documentation for `serve_forever` and
      `server_close`
    - official Python `argparse` documentation for CLI argument handling
  - implementation:
    - added `openwukong.control.wechat_native_endpoint_publisher`
      - `WeChatNativeEndpointConfig`
      - `WeChatNativeEndpointPublisher`
      - `WeChatNativeBackend`
      - `UnavailableWeChatNativeBackend`
      - `make_wechat_native_endpoint_handler`
      - `write_wechat_native_bridge_registry`
    - publisher binds to `127.0.0.1:0` by default and writes the actual bound
      URL, never `http://127.0.0.1:0`
    - default backend intentionally returns
      `wechat_native_backend_not_configured`, with zero window, keyboard, and
      clipboard attempts, so it cannot be mistaken for a real send-ready bridge
    - registry writer preserves unrelated WeChat bridge entries and updates an
      existing entry by same process/conversation or same URL
    - exported the publisher API through `openwukong.control`
    - extended `SessionReadinessPlanOptions` and CLI with:
      - `wechat_bridge_python_executable`
      - `wechat_bridge_host`
      - `wechat_bridge_port`
      - `wechat_bridge_registry_path`
      - process/window/conversation identity fields
    - added readiness route `wechat-native-bridge`
      - action id: `launch_wechat_native_bridge`
      - connector id: `wechat-native-bridge`
      - managed background helper
      - dynamic readiness URL readback through
        `discover_wechat_native_bridge_urls`
    - added stop-manifest support for the WeChat helper action so launched
      publisher processes can be terminated by the same managed helper cleanup
      path
  - validation:
    - TDD red observed:
      - no `wechat_native_endpoint_publisher` module
      - `SessionReadinessPlanOptions` rejected WeChat bridge fields
      - CLI rejected `--wechat-bridge-*` arguments
    - publisher tests passed:
      `python -m unittest tests.test_wechat_native_endpoint_publisher`
      with `5` tests OK
    - WeChat readiness focused tests passed:
      `python -m unittest` for WeChat plan, dynamic registry readback, CLI
      dynamic default, and stop-manifest acceptance with `4` tests OK
    - WeChat/Fabric/readiness related regression passed:
      `python -m unittest tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding tests.test_control_fabric_execution tests.test_session_readiness_plan`
      with `77` tests OK
    - broad related regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_primary_scenario_smoke tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_session_registry_report tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_native_probe_binding tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding tests.test_wechat_native_endpoint_publisher`
      with `349` tests OK
    - read-only live accessibility probe still observed:
      - `control_attempts=0`
      - `claude.exe`, `Codex.exe`, and `Weixin.exe` remain blocked until a
        verified deterministic endpoint exists
      - `Cursor.exe` remains on the deterministic IDE connector route
  - current conclusion:
    - WeChat now has a real reusable endpoint publisher envelope with dynamic
      port registration, readiness-plan launch, and manifest cleanup
    - this still does not mean real WeChat is fully controllable on this
      machine; the missing piece is a real native backend that can safely
      implement send/readback/background screenshot against the live WeChat
      client
  - next concrete actions:
    1. implement the real WeChat backend behind
       `WeChatNativeBackend.capabilities/send_message`
    2. wire background screenshot/readback evidence into the publisher so the
       Fabric target can be built entirely from live evidence
    3. continue Codex/Claude desktop App endpoint publication/discovery so the
       agent-native route becomes live

- 2026-06-07 R235 WeChat publisher now has a live read-only evidence backend:
  - trigger:
    - continuation of the full desktop-control goal, specifically connecting
      the reusable WeChat endpoint publisher to real no-focus locator and
      background screenshot evidence
  - docs consulted before code changes:
    - Microsoft Learn `PrintWindow` documentation, including its synchronous
      blocking behavior
    - Microsoft Learn `GetForegroundWindow` documentation for foreground
      window evidence
    - Microsoft Learn `GetWindowRect` documentation for HWND bounds
    - Microsoft Learn `AccessibleObjectFromWindow` documentation for MSAA
      read-only accessibility access
  - implementation:
    - added `LiveWeChatEvidenceBackend`
      - returns real WeChat locator evidence through
        `build_wechat_locator_report`
      - captures target HWNDs through the existing
        `PrintWindowBackgroundCaptureProvider`
      - reports background screenshot count, success count, and
        focus-stability evidence in `/v1/wechat/capabilities`
      - never advertises `send_message`; `send_action_ready=false`
      - `/v1/wechat/send` returns
        `wechat_native_send_backend_not_configured` with zero window,
        keyboard, and clipboard attempts
    - added `FastWin32AccessibilityObserver`
      - default live backend observer now uses Win32 top-level windows and
        process-only fallback instead of Pywinauto/UIA descendant scans
      - UIA remains opt-in through `accessibility_backend="uia"`
    - default live backend disables MSAA unless explicitly enabled, keeping
      readiness fast and avoiding COM/accessibility stalls during endpoint
      health checks
    - added capability timeout protection:
      - `capability_timeout_sec`
      - timeout result:
        `wechat_live_evidence_timeout`
      - timeout path still reports zero control/window/keyboard/clipboard
        attempts
    - exported `LiveWeChatEvidenceBackend`,
      `FastWin32AccessibilityObserver`, and `build_wechat_native_backend`
      through `openwukong.control`
    - publisher CLI now supports:
      - `--backend read-only-evidence|unavailable`
      - `--capture-dir`
      - `--capability-timeout-sec`
      - `--accessibility-backend win32|uia`
      - `--accessibility-max-windows`
      - `--accessibility-max-elements-per-window`
      - `--enable-msaa`
  - validation:
    - TDD red observed:
      - `LiveWeChatEvidenceBackend` import missing
      - WeChat readiness action did not pass `--backend`
      - live endpoint probe initially timed out on heavier UIA/MSAA path
    - publisher tests passed:
      `python -m unittest tests.test_wechat_native_endpoint_publisher`
      with `9` tests OK
    - WeChat/readiness/Fabric related regression passed:
      `python -m unittest tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding tests.test_control_fabric_execution tests.test_session_readiness_plan tests.test_window_capture tests.test_wechat_locator`
      with `87` tests OK
    - broad related regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_primary_scenario_smoke tests.test_cursor_draft_hook_probe tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_bridge_contract_probe tests.test_cursor_isolated_draft_hook_runner tests.test_session_readiness_plan tests.test_major_real_no_loss tests.test_session_registry_report tests.test_accessibility_probe tests.test_universal_app_profile tests.test_agent_app_uia_probe tests.test_agent_app_bridge tests.test_agent_app_real_no_loss tests.test_agent_native_bridge tests.test_agent_native_connector_probe tests.test_agent_native_probe_binding tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_fabric_binding tests.test_wechat_native_endpoint_publisher tests.test_window_capture tests.test_wechat_locator`
      with `359` tests OK
    - real live read-only endpoint probe:
      - dynamic bridge URL example: `http://127.0.0.1:60693`
      - `ok=true`
      - `backend=read-only-evidence`
      - `locator_window_count=2`
      - `background_screenshot_count=2`
      - `background_screenshot_success_count=2`
      - `background_screenshot_focus_stable=true`
      - `send_action_ready=false`
      - `window_input_attempts=0`
      - `keyboard_input_attempts=0`
      - `clipboard_write_attempts=0`
    - real live `/v1/wechat/send` refusal probe:
      - `ok=false`
      - `sent=false`
      - `error=wechat_native_send_backend_not_configured`
      - window/keyboard/clipboard attempts all `0`
  - current conclusion:
    - WeChat now has a live dynamic-port endpoint that can provide real
      no-focus observation and background screenshot evidence
    - this is a material step toward precise background WeChat control, but it
      still deliberately does not send messages; real write/send remains gated
      until a deterministic native backend is implemented and verified
  - next concrete actions:
    1. design and implement the real WeChat send backend behind the same
       endpoint, starting with File Transfer Assistant only and requiring
       readback plus foreground-stability evidence
    2. feed live evidence backend output into Fabric binding so targets can be
       built from `/capabilities` evidence rather than manual screenshot
       counts
    3. continue Codex/Claude desktop App endpoint publication/discovery

- 2026-06-07 R236 WeChat Fabric binding now consumes live capability evidence safely:
  - trigger:
    - continuation of the full desktop-control goal, specifically removing
      manual screenshot-count fields from WeChat Fabric binding and using the
      native endpoint `/v1/wechat/capabilities` report as the source of truth
  - docs consulted before code changes:
    - official Python `urllib.request` documentation
    - official Python `dataclasses` documentation
  - implementation:
    - `wechat_native_fabric_bindings_from_registry(...)` now probes each
      discovered dynamic local WeChat bridge URL and extracts:
      - process name / PID when reported
      - conversation/session identity when verified
      - window title when target evidence is verified
      - background screenshot focus-stability, count, and success count
    - capability probing is compatibility-preserving:
      - enabled by default for live endpoints
      - falls back to the existing manual evidence arguments if the endpoint
        is unreachable or probing is explicitly disabled
    - `ownership_index_from_wechat_native_bridge_registry(...)` forwards the
      same capability-probe options, so owned-session binding remains aligned
      with Fabric targets
    - read-only endpoints that report `send_action_ready=false` can provide
      observation evidence, but the send adapter still blocks before calling
      `/v1/wechat/send`
    - tightened target-safety semantics:
      - `LiveWeChatEvidenceBackend` now separates "WeChat window observed"
        from "requested conversation verified"
      - if the visible/readable WeChat window title does not match the
        requested target conversation, the endpoint marks the target
        `available=false` with
        `availability_reason=wechat_conversation_not_verified`
      - Fabric binding does not promote screenshot counts from unavailable
        capability targets, preventing "saw a WeChat window" from becoming
        "can operate File Transfer Assistant"
  - validation:
    - TDD red observed:
      - registry binding left background screenshot counts at `0` even when a
        capability endpoint reported real screenshot evidence
      - read-only capability targets were initially over-promoted into
        Fabric-ready targets
      - live read-only probe revealed an important precision issue: current
        WeChat top-level title was another chat while the requested target was
        File Transfer Assistant
    - focused binding tests passed:
      `python -m unittest tests.test_wechat_native_fabric_binding`
      with `2` tests OK before the safety-tightening additions
    - WeChat/Fabric/ownership related regression passed:
      `python -m unittest tests.test_wechat_native_fabric_binding tests.test_control_fabric_execution tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_endpoint_publisher tests.test_session_ownership`
      with `42` tests OK
    - endpoint and binding focused tests passed:
      `python -m unittest tests.test_wechat_native_fabric_binding tests.test_wechat_native_endpoint_publisher`
      with `13` tests OK
    - WeChat/readiness/window related regression passed:
      `python -m unittest tests.test_wechat_native_fabric_binding tests.test_control_fabric_execution tests.test_wechat_native_bridge tests.test_wechat_native_bridge_registry tests.test_wechat_native_endpoint_publisher tests.test_session_ownership tests.test_wechat_native_bridge_registry tests.test_wechat_native_bridge tests.test_session_readiness_plan tests.test_window_capture tests.test_wechat_locator`
      with `101` tests OK
    - safe live read-only binding probe:
      - dynamic bridge URL example: `http://127.0.0.1:53012`
      - registry binding found `1` endpoint
      - current WeChat window was not verified as File Transfer Assistant
      - target screenshot counts stayed `0`
      - Fabric blocked at dispatch:
        `dispatch_gate_not_ready`
      - `control_attempts=0`
      - no action report was created, so `/v1/wechat/send` was not called
    - attempted broad all-related regression twice, but the outer command
      timed out at 5 minutes and then 10 minutes without returning a complete
      result; subsequent shell and Node tool calls also timed out, indicating
      the local tool execution channel or machine load was unstable rather
      than a deterministic code assertion failure
  - current conclusion:
    - WeChat registry-to-Fabric binding now uses live endpoint evidence and is
      stricter about target conversation verification
    - this improves precision and safety: observation of a WeChat HWND is no
      longer enough to mark a specific chat target ready
    - real WeChat write/send remains intentionally gated until a deterministic
      native send backend can verify the target conversation, write without
      foreground takeover, and read back the sent marker
  - next concrete actions:
    1. restore/inspect the local shell execution channel, then rerun
       `git diff --check` and the broad related regression
    2. design the real File Transfer Assistant send backend with explicit
       target verification, readback, no foreground takeover, and zero
       keyboard/clipboard/window input attempts
    3. continue Codex/Claude desktop App endpoint publication/discovery so
       agent-native routes can be validated with the same endpoint ownership
       and capability-evidence pattern

- 2026-06-07 R237 Local command execution channel still unavailable; keep goal active:
  - trigger:
    - automatic continuation of the full desktop-control goal after R236
  - observed state:
    - `cmd /c echo shell-ok` timed out from the repository workdir
    - `cmd /c echo shell-ok` also timed out from `C:\Users\Zhangjinqian`
    - disabling shell login semantics did not change the timeout
    - MCP metadata tools remained available, so this is not evidence that the
      OpenWukong control architecture regressed
  - safety decision:
    - did not launch real GUI tests
    - did not run additional browser/WeChat/Cursor/Codex/Claude control
      attempts
    - did not mark the active product goal complete
    - did not mark the goal blocked yet, because the strict repeated-turn
      blocked threshold is not satisfied
  - current conclusion:
    - R236's focused and related WeChat/Fabric validations remain the latest
      completed evidence
    - broad regression and `git diff --check` are still pending until the local
      shell execution channel can start even minimal commands again
  - next concrete actions when shell recovers:
    1. run a minimal command liveness check outside and inside the repository
    2. inspect for orphaned Python/unittest helper processes without killing
       unrelated user work
    3. run `git diff --check`
    4. rerun focused WeChat binding/publisher tests
    5. rerun broad related control/readiness/accessibility regression
    6. continue implementation of the deterministic File Transfer Assistant
       native send backend only after those checks are green or the remaining
       failures are clearly classified as unrelated environment issues

- 2026-06-27 R238 Cua-inspired no-foreground contract and trajectory evidence base:
  - trigger:
    - user asked what parts of Cua should be absorbed, then asked to start
      implementing the first batch
  - docs consulted before code changes:
    - Cua no-foreground/control trajectory documentation
    - official Python `dataclasses` documentation
  - implementation:
    - added `openwukong.control.execution_contract`
      - global `NoForegroundContract`
      - `build_no_foreground_contract(...)`
      - `validate_no_foreground_contract(...)`
      - validates focus stability, foreground takeover, keyboard/mouse/window
        input, clipboard writes, and cursor movement against the selected route
    - added `openwukong.control.trajectory`
      - `ControlTrajectoryRecorder`
      - `ControlTrajectory`
      - `ControlTrajectoryStep`
      - `TrajectoryArtifact`
      - append-only JSON manifest/step records for dispatch/action evidence
    - wired `ControlFabric` dispatch reports to include
      `no_foreground_contract`
    - wired `ControlFabric` execution reports to include
      `no_foreground_contract` and `no_foreground_validation`
    - exported the new contract and trajectory APIs from
      `openwukong.control`
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_no_foreground_contract tests.test_control_trajectory`
      with `6` tests OK
    - related Fabric/transport regression passed:
      `python -m unittest tests.test_control_fabric tests.test_transport_capability_matrix tests.test_no_foreground_contract tests.test_control_trajectory`
      with `23` tests OK
    - execution-gate regression passed:
      `python -m unittest tests.test_control_fabric_execution tests.test_no_foreground_contract tests.test_control_trajectory`
      with `26` tests OK
    - wider control-layer regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory`
      with `87` tests OK
    - `py_compile` passed for:
      - `src/openwukong/control/execution_contract.py`
      - `src/openwukong/control/trajectory.py`
      - `src/openwukong/control/fabric.py`
      - `src/openwukong/control/__init__.py`
      - `tests/test_no_foreground_contract.py`
      - `tests/test_control_trajectory.py`
    - `git diff --check` passed for the touched files; Git reported only
      existing CRLF normalization warnings on modified files
  - current conclusion:
    - Cua's no-foreground contract has been absorbed as an OpenWuKong-native
      global control/evidence contract rather than a visual-click-first agent
      layer
    - trajectory recording now gives a reusable evidence schema for future
      replay/debug/training data without triggering any desktop control
  - next concrete actions:
    1. attach `ControlTrajectoryRecorder` to `ControlFabric.execute(...)` and
       the primary real-no-loss runners when an output root is provided
    2. promote no-foreground validation failures into hard execution failures
       for all non-command desktop control paths
    3. extend L1/L3 fixture schema with trajectory/oracle fields inspired by
       Cua-Bench while preserving connector-first routing

- 2026-06-27 R239 Trajectory recording is now attached to execution and primary no-loss cases:
  - trigger:
    - user asked to continue after R238's next concrete action
  - docs consulted before code changes:
    - official Python `pathlib` documentation
    - previously consulted Cua no-foreground/trajectory documentation remains
      the product reference for the absorbed pattern
  - implementation:
    - `ControlFabric.execute(...)` now accepts:
      - `trajectory_root`
      - `trajectory_metadata`
    - when `trajectory_root` is provided, Fabric writes a
      `ControlTrajectoryRecorder` manifest with:
      - dispatch step
      - execution step
      - route / connector / decision metadata
    - `ControlExecutionReport.to_dict()` now exposes:
      - `trajectory_id`
      - `trajectory_path`
      - `trajectory_error`
    - `control_fabric_execute` CLI now accepts `--trajectory-root` and passes
      entrypoint metadata into the Fabric trajectory
    - `primary_real_no_loss` now writes a per-case trajectory under
      `control_trajectories/` when writing each case artifact
    - primary case details now include `trajectory_path`
  - validation:
    - focused execution/primary/trajectory tests passed:
      `python -m unittest tests.test_control_fabric_execution tests.test_primary_real_no_loss tests.test_control_trajectory`
      with `37` tests OK
    - related Fabric/transport/contract/primary regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss`
      with `58` tests OK
    - wider control-layer regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss`
      with `102` tests OK
    - `py_compile` passed for:
      - `src/openwukong/control/fabric.py`
      - `src/openwukong/control/trajectory.py`
      - `src/openwukong/evaluation/control_fabric_execute.py`
      - `src/openwukong/evaluation/primary_real_no_loss.py`
      - `tests/test_control_fabric_execution.py`
      - `tests/test_primary_real_no_loss.py`
    - `git diff --check` passed for touched files; Git reported only CRLF
      normalization warnings
  - current conclusion:
    - real control execution and primary no-loss case reports now produce
      durable, structured trajectory evidence when an output root is available
    - this turns the Cua-inspired trajectory idea into a native OpenWuKong
      audit/replay substrate without changing default route gates
  - next concrete actions:
    1. promote no-foreground validation failures into hard execution failures
       for non-command desktop control paths
    2. attach screenshot/app-state artifacts to trajectory steps where existing
       probes already emit artifact paths
    3. extend L1/L3 fixture schema with trajectory/oracle fields inspired by
       Cua-Bench while preserving connector-first routing

- 2026-06-27 R240 No-foreground validation is now a hard gate for non-command desktop execution:
  - trigger:
    - user asked to start the next step after the computer-operation readiness
      discussion
  - docs consulted before code changes:
    - official Python `dataclasses` documentation
    - official Python `unittest` documentation for focused regression coverage
  - implementation:
    - `ControlFabric.execute(...)` now calls `_enforce_no_foreground_contract`
      after an action report is produced and before trajectory finalization
    - non-command desktop routes now fail execution when the action report
      violates the no-foreground contract
    - command routes remain excluded from this desktop hard gate:
      - `terminal-native-session`
      - `git-cli`
    - hard-gate failures set:
      - `ok=false`
      - `decision=failed`
      - `control_allowed=false`
      - `error=no_foreground_contract_violation:<violations>`
    - `validate_no_foreground_contract(...)` now merges top-level action
      report fields with nested connector `payload` fields, so native
      connector evidence is actually checked
  - validation:
    - focused hard-gate tests passed:
      `python -m unittest tests.test_control_fabric_execution tests.test_no_foreground_contract`
      with `27` tests OK
    - related Fabric/transport/contract/trajectory regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_no_foreground_contract tests.test_control_trajectory`
      with `46` tests OK
    - wider control-layer regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss`
      with `104` tests OK
    - `py_compile` passed for:
      - `src/openwukong/control/fabric.py`
      - `src/openwukong/control/execution_contract.py`
      - `tests/test_control_fabric_execution.py`
      - `tests/test_no_foreground_contract.py`
    - `git diff --check` passed for touched files; Git reported only CRLF
      normalization warnings
  - TDD evidence:
    - first focused run failed because terminal connector evidence was nested
      under action report `payload`, while the validator only checked top-level
      fields
    - validator was corrected to merge nested `payload` evidence before
      evaluating focus/input violations
  - current conclusion:
    - OpenWuKong now has a real execution-time safety boundary: a route that
      promises no foreground takeover cannot silently succeed after stealing
      focus or using keyboard/mouse/clipboard
    - this materially raises the system from "records unsafe evidence" to
      "fails unsafe execution" for non-command desktop control paths
  - next concrete actions:
    1. attach screenshot/app-state artifacts to trajectory steps where existing
       probes already emit artifact paths
    2. build a Computer Operation Readiness Matrix across Browser / Terminal /
       Git / IDE / Office / WeChat / Generic Desktop
    3. implement the first end-to-end safe operation demo with an owned browser:
       launch isolated browser, operate a controlled page, verify DOM readback,
       and persist trajectory evidence

- 2026-06-27 R241 Computer Operation Readiness Matrix added:
  - trigger:
    - user asked to continue after Windows Defender allowed the Codex Desktop
      helper warning and wanted project progress resumed
  - safety note:
    - real Codex Desktop Computer Use was not used for this task
    - all work stayed in file edits, Fabric dispatch plans, and test commands
  - docs consulted before code changes:
    - official Python `dataclasses` documentation
    - official Python `argparse` documentation
    - official Python `unittest` documentation
  - implementation:
    - added `openwukong.evaluation.computer_operation_readiness_matrix`
    - the new plan-only matrix classifies seven computer operation surfaces:
      - Browser
      - Terminal
      - Git
      - IDE
      - Office
      - WeChat
      - Generic Desktop
    - each surface is classified into:
      - `background_execute`
      - `read_only`
      - `foreground_required`
      - `blocked`
    - the matrix is built from `ControlFabric.dispatch(...)` and therefore
      respects connector readiness, route policy, transport capability, and
      no-control plan-only boundaries
    - current default workspace classification is:
      - `terminal`: `background_execute`
      - `git`: `background_execute`
      - `browser`: `blocked` until owned debugger URL evidence exists
      - `ide`: `blocked` until IDE bridge URL evidence exists
      - `office`: `blocked` until an Office object-model/add-in connector is
        present
      - `wechat`: `blocked` until WeChat native bridge URL plus background
        screenshot evidence exists
      - `generic_desktop`: `foreground_required` under current Fabric gates
    - with explicit browser debugger URL, IDE bridge URL, WeChat native bridge
      URL, and verified WeChat background screenshot evidence, Browser / IDE /
      WeChat promote to `background_execute` without attempting control
    - added CLI support:
      - `python -m openwukong.evaluation.computer_operation_readiness_matrix`
      - optional JSON output and evidence flags for browser, IDE, WeChat, and
        workspace path
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_computer_operation_readiness_matrix`
      with `3` tests OK
    - related Fabric/transport/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_transport_capability_matrix tests.test_primary_transport_matrix tests.test_no_foreground_contract tests.test_computer_operation_readiness_matrix`
      with `27` tests OK
    - wider control-layer regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix`
      with `113` tests OK
    - `py_compile` passed for:
      - `src/openwukong/evaluation/computer_operation_readiness_matrix.py`
      - `tests/test_computer_operation_readiness_matrix.py`
    - `git diff --check` passed for the touched readiness matrix files
  - current conclusion:
    - OpenWuKong can already operate the developer workstation in background
      mode for Terminal and Git through structured command/session routes
    - Browser / IDE / WeChat are architecturally ready but require explicit
      deterministic connector evidence before background execution is allowed
    - Office and arbitrary Generic Desktop remain below the safe background
      operation bar in the current Fabric policy
  - next concrete actions:
    1. implement the first end-to-end safe operation demo with an owned browser:
       launch isolated browser, operate a controlled page, verify DOM readback,
       and persist trajectory evidence
    2. attach screenshot/app-state artifacts to trajectory steps where existing
       probes already emit artifact paths
    3. add or bind an Office object-model connector if Office document creation
       remains part of the primary workstation objective

- 2026-06-27 R242 Owned Browser Safe Operation Demo added:
  - trigger:
    - user said "start" after R241 identified owned browser as the next
      concrete path to prove safe computer operation
  - docs consulted before code changes:
    - official Python `subprocess` documentation
    - official Python `http.server` documentation
    - Chrome DevTools Protocol `Page` domain documentation
  - safety note:
    - real Codex Desktop Computer Use was not used
    - no foreground mouse/keyboard desktop control was used
    - tests use fake launch/action runners and do not require a real Chrome
      installation
  - implementation:
    - added `openwukong.evaluation.owned_browser_safe_operation_demo`
    - the demo starts a loopback controlled page server
    - it launches an owned isolated browser through existing
      `SessionReadinessPlan` using:
      - isolated `--user-data-dir`
      - local DevTools endpoint
      - `--headless=new`
      - manifest-based cleanup
    - it runs the existing Fabric-gated browser workflow against the owned
      browser only, with ownership enforced from the readiness manifest
    - workflow steps:
      - navigate to controlled page
      - set input value
      - submit the controlled form
      - read the page
      - extract result links
    - quality gates verify:
      - URL contains the verified state
      - DOM text contains the required marker
      - result link href and text contain the expected evidence
      - at least one result is extracted
    - the demo stops the owned browser via manifest PID-tree cleanup
    - the isolated browser profile is deleted by default and can be kept only
      with explicit `--keep-profile`
    - the demo writes:
      - `owned_browser_safe_operation_demo.json`
      - browser workflow artifact
      - stop artifact
      - `ControlTrajectoryRecorder` manifest with controlled page, launch,
        workflow, cleanup, and final report steps
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_owned_browser_safe_operation_demo`
      with `3` tests OK
    - related browser/session/Fabric/trajectory regression passed:
      `python -m unittest tests.test_owned_browser_safe_operation_demo tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_control_trajectory tests.test_control_fabric_execution`
      with `82` tests OK
    - wider control/browser/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_owned_browser_safe_operation_demo`
      with `170` tests OK
    - `py_compile` passed for:
      - `src/openwukong/evaluation/owned_browser_safe_operation_demo.py`
      - `tests/test_owned_browser_safe_operation_demo.py`
    - `git diff --check` passed for the touched owned-browser demo files
    - live owned Chrome demo passed on this Windows workstation:
      `python -m openwukong.evaluation.owned_browser_safe_operation_demo --browser-executable "C:\Program Files\Google\Chrome\Application\chrome.exe" --output-root logs\runtime\owned-browser-safe-operation-demo-live --settle-seconds 0.2`
      with:
      - `ok=true`
      - `decision=owned_browser_demo_verified`
      - `control_attempts=3`
      - `desktop_control_attempts=0`
      - `window_input_attempts=0`
      - `stop_attempts=1`
      - `profile_cleanup.deleted=true`
      - `browser_workflow.quality_summary.failed=0`
      - trajectory manifest written under
        `logs/runtime/owned-browser-safe-operation-demo-live/control_trajectories/`
  - current conclusion:
    - OpenWuKong now has a first explicit Browser computer-operation demo that
      performs real browser-side DOM operations through a deterministic
      DevTools connector contract while preserving the no-foreground design
    - the demo has now passed a live owned Chrome run on Windows, while the
      default tests remain hermetic and do not depend on external browser state
  - next concrete actions:
    1. attach screenshot/app-state artifacts to trajectory steps where existing
       probes already emit artifact paths
    2. promote the same owned-session pattern to IDE bridge and WeChat native
       bridge demos once their connector evidence is present
    3. add a compact dashboard/report view for readiness matrix plus owned
       browser live-demo artifacts

- 2026-06-27 R243 Trajectory Artifact Auto-Attach added:
  - trigger:
    - user asked to continue after R242, and the current roadmap's first next
      action was to attach screenshot/app-state artifacts to trajectory steps
  - docs consulted before code changes:
    - official Python `pathlib` documentation
    - official Python `mimetypes` documentation
  - safety note:
    - real Codex Desktop Computer Use was not used
    - no foreground mouse/keyboard desktop control was used
    - this change only records existing artifact files that probe reports
      already wrote to disk
  - implementation:
    - added `extract_trajectory_artifacts(...)` to
      `openwukong.control.trajectory`
    - the extractor recursively scans nested reports for known artifact-like
      path fields, including:
      - `artifact_path`
      - `output_path`
      - `screenshot_path`
      - `report_path`
      - `manifest_path`
      - `trajectory_path`
      - matching suffix forms such as `_screenshot_path` and `_state_path`
    - only existing files are attached; missing files, URLs, profile
      directories, and workspace directories are ignored
    - attached artifacts now receive deterministic roles, inferred media types,
      and SHA-256 hashes
    - `ControlFabric.execute(..., trajectory_root=...)` now attaches action
      report artifacts to the execution step automatically
    - `primary_real_no_loss` case trajectories now attach existing probe
      artifacts from case details, such as background screenshot outputs, while
      keeping the existing case report artifact reference
  - validation:
    - focused regression passed:
      `python -m unittest tests.test_control_trajectory tests.test_control_fabric_execution tests.test_primary_real_no_loss`
      with `41` tests OK
    - wider control/browser/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_owned_browser_safe_operation_demo`
      with `172` tests OK
    - `py_compile` passed for:
      - `src/openwukong/control/trajectory.py`
      - `src/openwukong/control/fabric.py`
      - `src/openwukong/evaluation/primary_real_no_loss.py`
      - `tests/test_control_trajectory.py`
      - `tests/test_control_fabric_execution.py`
      - `tests/test_primary_real_no_loss.py`
    - `git diff --check` passed for touched code/test files, with only CRLF
      working-copy warnings
  - current conclusion:
    - execution trajectories now preserve the concrete screenshot and app-state
      files needed for audit, debugging, replay, and later training-data export
      without broadening the control surface
  - next concrete actions:
    1. promote the owned-session pattern to IDE bridge and WeChat native bridge
       demos once their connector evidence is present
    2. add a compact dashboard/report view for readiness matrix plus owned
       browser live-demo and trajectory artifacts
    3. extend artifact auto-attach coverage to standalone probe CLIs that write
       reports outside Fabric or primary-real-no-loss

- 2026-06-27 R244 Computer Operation Status Report added:
  - trigger:
    - user asked to continue after R243
    - IDE and WeChat owned-session demos still require live bridge evidence, so
      the next directly actionable roadmap item was a compact readiness plus
      artifact report view
  - docs consulted before code changes:
    - official Python `json` documentation
    - official Python `argparse` documentation
    - official Python `pathlib` documentation
  - safety note:
    - real Codex Desktop Computer Use was not used
    - no foreground mouse/keyboard desktop control was used
    - the new report only reads existing JSON/Markdown-ready evidence and does
      not launch or control applications
  - implementation:
    - added `openwukong.evaluation.computer_operation_status_report`
    - the report combines:
      - `ComputerOperationReadinessMatrixReport`
      - owned-browser safe-operation demo JSON
      - owned-browser trajectory manifest artifacts
    - if an owned-browser demo report is supplied or discovered, its verified
      DevTools readiness URL and controlled-page URL are fed into the readiness
      matrix so Browser can be shown as `background_execute`
    - report outputs include:
      - JSON status report
      - Markdown status view
      - surface readiness table
      - owned-browser demo status
      - trajectory artifact roles, media types, counts, and file-existence
        checks
      - next actions derived from blocked IDE / Office / WeChat surfaces
    - CLI added:
      - `python -m openwukong.evaluation.computer_operation_status_report`
      - supports explicit owned-browser report path
      - supports runtime-root discovery
      - supports `--output`, `--markdown-output`, and `--json`
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_computer_operation_status_report`
      with `3` tests OK
    - related readiness/demo/trajectory regression passed:
      `python -m unittest tests.test_computer_operation_status_report tests.test_computer_operation_readiness_matrix tests.test_owned_browser_safe_operation_demo tests.test_control_trajectory tests.test_control_fabric_execution tests.test_primary_real_no_loss`
      with `50` tests OK
    - wider control/browser/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_owned_browser_safe_operation_demo`
      with `175` tests OK
    - `py_compile` passed for:
      - `src/openwukong/evaluation/computer_operation_status_report.py`
      - `tests/test_computer_operation_status_report.py`
    - `git diff --check` passed for touched R244 files
    - generated current workstation status artifacts:
      - `logs/runtime/computer-operation-status-r244/status.json`
      - `logs/runtime/computer-operation-status-r244/status.md`
    - generated report summary:
      - `surface_count=7`
      - `background_execute_count=3`
      - `blocked_count=3`
      - `foreground_required_count=1`
      - `owned_browser_demo_status=verified`
      - `owned_browser_artifact_count=4`
      - `observed_prior_control_attempts=3`
      - `observed_prior_window_input_attempts=0`
  - current conclusion:
    - the current validated computer-operation level is:
      - Browser: `background_execute` through owned DevTools demo evidence
      - Terminal: `background_execute`
      - Git: `background_execute`
      - IDE: `blocked` until live IDE bridge evidence is available
      - Office: `blocked` until an Office object-model/add-in connector exists
      - WeChat: `blocked` until native bridge plus background screenshot
        evidence is available
      - Generic Desktop: `foreground_required`
  - next concrete actions:
    1. implement the IDE owned-session demo against explicit IDE bridge
       evidence or a hermetic bridge fixture
    2. implement the WeChat native bridge demo once native bridge URL and
       background screenshot evidence are present
    3. extend artifact auto-attach coverage to standalone probe CLIs that write
       reports outside Fabric or primary-real-no-loss

- 2026-06-27 R245 Hermetic Owned IDE Bridge Demo added:
  - trigger:
    - user asked to start after R244
    - the selected breakthrough was to move IDE from `blocked` to
      `background_execute` using owned bridge evidence before attempting generic
      desktop control
  - docs consulted before code changes:
    - official Python `http.server` documentation
    - official Python `urllib.request` documentation
    - official Python `mimetypes` documentation
  - safety note:
    - real Codex Desktop Computer Use was not used
    - no real IDE, Cursor, or VS Code process was launched
    - no foreground mouse/keyboard desktop control was used
    - the demo uses only a local loopback hermetic bridge and an owned scratch
      workspace under `logs/runtime`
  - implementation:
    - added `openwukong.evaluation.owned_ide_safe_operation_demo`
    - the demo starts a local hermetic IDE bridge with endpoints matching the
      existing IDE extension bridge contract:
      - `/v1/ide/capabilities`
      - `/v1/ide/state`
      - `/v1/ide/read`
      - `/v1/ide/send`
      - `/v1/ide/command`
    - the demo writes an IDE session ownership manifest compatible with
      `SessionOwnershipIndex`
    - Fabric execution then runs through the real `IDEExtensionConnector`
      route:
      - read owned IDE state
      - write an owned scratch buffer
      - read back the scratch marker
    - the write action is scoped to `local_draft.write` side-effect policy and
      stays within the owned output workspace
    - trajectory evidence now includes IDE state, scratch, readback, ownership,
      Fabric execution, and final report artifacts
    - `extract_trajectory_artifacts(...)` now recognizes `scratch_path` and
      `readback_path`
    - `computer_operation_status_report` now accepts:
      - `--owned-ide-report`
      - `--no-discover-owned-ide-report`
      and can promote IDE readiness from owned demo evidence
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_owned_ide_safe_operation_demo tests.test_computer_operation_status_report tests.test_control_trajectory`
      with `9` tests OK
    - related IDE/Fabric/readiness tests passed:
      `python -m unittest tests.test_owned_ide_safe_operation_demo tests.test_computer_operation_status_report tests.test_computer_operation_readiness_matrix tests.test_owned_browser_safe_operation_demo tests.test_control_trajectory tests.test_control_fabric_execution tests.test_ide_bridge_capture tests.test_ide_extension_readiness tests.test_ide_bridge_registry`
      with `56` tests OK
    - wider control/browser/IDE/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_owned_browser_safe_operation_demo tests.test_owned_ide_safe_operation_demo tests.test_ide_bridge_capture tests.test_ide_extension_readiness tests.test_ide_bridge_registry`
      with `195` tests OK
    - `py_compile` passed for:
      - `src/openwukong/evaluation/owned_ide_safe_operation_demo.py`
      - `src/openwukong/evaluation/computer_operation_status_report.py`
      - `src/openwukong/control/trajectory.py`
      - `tests/test_owned_ide_safe_operation_demo.py`
      - `tests/test_computer_operation_status_report.py`
    - `git diff --check` passed for touched R245 files
    - generated hermetic owned IDE demo:
      - `logs/runtime/owned-ide-safe-operation-demo-r245/owned_ide_safe_operation_demo.json`
      - `ok=true`
      - `decision=owned_ide_demo_verified`
      - `control_attempts=2`
      - `desktop_control_attempts=0`
      - `window_input_attempts=0`
      - `quality_summary.failed=0`
    - generated combined R245 status report:
      - `logs/runtime/computer-operation-status-r245/status.json`
      - `logs/runtime/computer-operation-status-r245/status.md`
      - `surface_count=7`
      - `background_execute_count=4`
      - `blocked_count=2`
      - `foreground_required_count=1`
      - `owned_browser_demo_status=verified`
      - `owned_ide_demo_status=verified`
      - `observed_prior_control_attempts=5`
      - `observed_prior_window_input_attempts=0`
  - current conclusion:
    - the current validated computer-operation level is:
      - Browser: `background_execute`
      - Terminal: `background_execute`
      - Git: `background_execute`
      - IDE: `background_execute` through hermetic owned bridge evidence
      - Office: `blocked`
      - WeChat: `blocked`
      - Generic Desktop: `foreground_required`
  - next concrete actions:
    1. move from hermetic IDE bridge to live VS Code/Cursor bridge evidence in
       an owned scratch workspace
    2. implement the WeChat native bridge demo once native bridge URL and
       background screenshot evidence are present
    3. extend artifact auto-attach coverage to standalone probe CLIs that write
       reports outside Fabric or primary-real-no-loss

- 2026-06-27 R246 Owned IDE Live Bridge Path added:
  - trigger:
    - user asked to continue after R245
    - the selected breakthrough was to move IDE from a hermetic-only bridge
      proof toward a live VS Code/Cursor bridge path using an owned scratch
      workspace and no foreground desktop control
  - docs consulted before code changes:
    - official VS Code Extension API documentation
    - official Python `argparse` documentation
  - safety note:
    - real Codex Desktop Computer Use was not used
    - no real IDE, Cursor, or VS Code process was launched by the demo
    - no foreground mouse/keyboard desktop control was used
    - the live demo refuses to execute the write step unless bridge metadata
      proves the bridge is bound to the owned scratch workspace
  - implementation:
    - extended the VS Code-compatible bridge extension with two built-in
      workspace-scoped commands:
      - `openwukong.writeScratch`
      - `openwukong.readScratch`
    - added those commands to the default `openwukong.bridge.allowedCommands`
      list because they only touch `.openwukong/openwukong-owned-scratch.txt`
      under the current workspace
    - documented the owned scratch command workflow in
      `extensions/openwukong-vscode/README.md`
    - added `openwukong.evaluation.owned_ide_live_bridge_demo`
    - the live demo can use an explicit `--ide-bridge-url` or discover a local
      bridge from the registry
    - the live demo verifies:
      - `/v1/ide/capabilities` is reachable
      - `openwukong.writeScratch` is available
      - the bridge metadata's first workspace equals the owned scratch
        workspace under the output root
      - Fabric execution is owned through `SessionOwnershipIndex`
      - the scratch marker is read back
      - window/keyboard/clipboard foreground counters remain zero
    - `computer_operation_status_report` now discovers both:
      - `owned_ide_safe_operation_demo.json`
      - `owned_ide_live_bridge_demo.json`
    - created global skill:
      `C:/Users/Zhangjinqian/.codex/skills/owned-session-manifest-compatibility`
      after the reusable `owned_session_required` / ownership-manifest schema
      pattern surfaced during R246 validation
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_owned_ide_live_bridge_demo tests.test_ide_extension_scaffold`
      with `9` tests OK
    - related IDE/status/readiness tests passed:
      `python -m unittest tests.test_owned_ide_live_bridge_demo tests.test_owned_ide_safe_operation_demo tests.test_computer_operation_status_report tests.test_computer_operation_readiness_matrix tests.test_control_trajectory tests.test_control_fabric_execution tests.test_ide_bridge_capture tests.test_ide_extension_readiness tests.test_ide_bridge_registry tests.test_ide_extension_scaffold`
      with `62` tests OK
    - wider control/browser/IDE/readiness regression passed:
      `python -m unittest tests.test_control_fabric tests.test_control_fabric_execution tests.test_transport_capability_matrix tests.test_agent_app_bridge tests.test_agent_app_uia_action_contract tests.test_wechat_native_bridge tests.test_no_foreground_contract tests.test_control_trajectory tests.test_primary_real_no_loss tests.test_primary_transport_matrix tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_control_fabric_browser_workflow tests.test_session_readiness_plan tests.test_owned_browser_safe_operation_demo tests.test_owned_ide_safe_operation_demo tests.test_owned_ide_live_bridge_demo tests.test_ide_bridge_capture tests.test_ide_extension_readiness tests.test_ide_bridge_registry tests.test_ide_extension_scaffold`
      with `204` tests OK
    - `py_compile` passed for touched Python modules/tests
    - `node --check extensions/openwukong-vscode/src/extension.js` passed
    - `git diff --check` passed for touched R246 files, with only CRLF
      working-copy warnings
    - global skill validation passed:
      `quick_validate.py C:/Users/Zhangjinqian/.codex/skills/owned-session-manifest-compatibility`
    - generated owned IDE live-path demo artifact:
      - `logs/runtime/owned-ide-live-bridge-demo-r246/owned_ide_live_bridge_demo.json`
      - `ok=true`
      - `decision=owned_ide_live_bridge_demo_verified`
      - `control_attempts=2`
      - `desktop_control_attempts=0`
      - `window_input_attempts=0`
      - `quality_summary.failed=0`
    - generated combined R246 status report:
      - `logs/runtime/computer-operation-status-r246/status.json`
      - `logs/runtime/computer-operation-status-r246/status.md`
      - `surface_count=7`
      - `background_execute_count=4`
      - `blocked_count=2`
      - `foreground_required_count=1`
      - `owned_browser_demo_status=verified`
      - `owned_ide_demo_status=verified`
      - `owned_ide_artifact_count=11`
      - `observed_prior_window_input_attempts=0`
  - current conclusion:
    - the current validated computer-operation level is:
      - Browser: `background_execute`
      - Terminal: `background_execute`
      - Git: `background_execute`
      - IDE: `background_execute` through owned bridge evidence, with a
        live VS Code/Cursor bridge path now implemented and workspace-gated
      - Office: `blocked`
      - WeChat: `blocked`
      - Generic Desktop: `foreground_required`
    - this reaches "operate the computer" for owned deterministic surfaces, not
      arbitrary desktop takeover; arbitrary Generic Desktop remains unsafe
      without a native connector or foreground authorization
  - next concrete actions:
    1. run the live IDE bridge demo against an actual VS Code/Cursor process
       opened on the owned scratch workspace after the extension is installed
       and the bridge is manually started
    2. implement the WeChat native bridge demo once native bridge URL and
       background screenshot evidence are present
    3. add an Office object-model/add-in connector before claiming background
       Office write readiness

- 2026-06-27 R247 Correct Cursor Profile Bridge Attempt:
  - trigger:
    - user clarified that the manually opened Cursor process was the correct
      logged-in process and that the previously launched isolated Cursor
      instance was the wrong one
  - safety note:
    - stopped the wrong isolated Cursor launch recorded in
      `logs/runtime/cursor-owned-live-r247/session_readiness_manifest.json`
      using manifest-scoped stop only
    - after the correction, no new isolated Cursor profile was launched
    - later `cursor --reuse-window` probes were cleaned up after they created
      no-window helper processes
  - live findings:
    - correct visible Cursor window:
      `pasted-text.txt - PaoPaoHeZi - Cursor`
    - initial live bridge was reachable at `http://127.0.0.1:8787`
      and exposed Cursor command candidates including `composer.sendToAgent`
    - installed correct-profile extension path:
      `C:/Users/Zhangjinqian/.cursor/extensions/openwukong-local.openwukong-vscode-bridge-0.1.0`
    - the installed extension was stale:
      - fixed default port `8787`
      - disruptive autostart warning path still present
      - no dynamic registry fallback
      - no `openwukong.writeScratch` / `openwukong.readScratch`
    - correct-profile extension sync was applied with backup:
      `logs/runtime/cursor-owned-live-r247/ide_extension_sync_correct_profile.json`
    - user-level Cursor settings were updated outside the repository to keep
      existing Cursor adapter commands and add:
      - `openwukong.writeScratch`
      - `openwukong.readScratch`
      - dynamic bridge port fallback settings
    - after the stale extension host was stopped, Cursor did not automatically
      re-activate the OpenWukong bridge
    - current bridge registry remains empty:
      `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges`
    - current Cursor NodeService processes expose no OpenWukong bridge listener
  - current blocker:
    - the correct Cursor window needs a real extension-host/window reload after
      the profile update before the live bridge demo can run
    - current evidence points to Cursor extension host/window state, not to a
      missing extension install or missing login
  - next concrete actions:
    1. reload the correct Cursor window once, then verify registry discovery
       and `openwukong.writeScratch` capability
    2. run `owned_ide_live_bridge_demo` against the discovered live bridge
       only after workspace binding is confirmed
    3. add a dedicated "installed extension updated but active host still old"
       readiness status so future runs stop before hanging on stale hosts

- 2026-06-27 R248/R249 Live Cursor Send and Bounded Await Recovery:
  - trigger:
    - user reloaded the correct logged-in Cursor window and explicitly allowed
      a real send validation
    - after a first real Cursor Agent send attempt, the bridge stopped
      responding, which exposed an extension-host request-handler hang rather
      than a missing login or missing bridge install
  - docs consulted before code changes:
    - official VS Code API documentation for extension command execution and
      extension-host APIs
  - safety note:
    - no foreground mouse, keyboard, or clipboard route was used for the
      validation
    - the deterministic scratch validation used only the installed Cursor
      extension bridge and a workspace-scoped scratch file under
      `E:/ideaProjects/agent/PaoPaoHeZi/.openwukong`
    - the later Cursor restart was performed only after the user reported the
      window was unusable and asked to close it and restart Cursor
  - live findings before the fix:
    - correct Cursor bridge registry appeared at:
      `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/0eeee662e051336efe7f99d3.json`
    - bridge URL was `http://127.0.0.1:8787`
    - bridge workspace was `E:/ideaProjects/agent/PaoPaoHeZi`
    - capabilities exposed `openwukong.writeScratch`,
      `openwukong.readScratch`, and Cursor command candidates including
      `composer.sendToAgent`
    - safe scratch validation passed:
      - artifact:
        `logs/runtime/cursor-owned-live-r247/cursor_live_scratch_validation.json`
      - marker:
        `OPENWUKONG_CURSOR_SCRATCH_R248_20260627162710`
      - `ok=true`
      - `readback_verified=true`
      - `window_input_attempts=0`
      - `keyboard_input_attempts=0`
      - `clipboard_write_attempts=0`
    - first real send attempt through `composer.sendToAgent` timed out after
      35 seconds and subsequent `/v1/ide/capabilities` calls also timed out
    - root cause:
      - `handleChat(...)` awaited `vscode.commands.executeCommand(...)`
        directly
      - Cursor Agent/private commands can be long-running or non-resolving from
        the extension-host perspective, so one Agent send blocked the local
        bridge request path
  - implementation:
    - updated `extensions/openwukong-vscode/src/extension.js`
      `handleChat(...)` to use a bounded await helper for chat adapter commands
    - added `executeCommandWithBoundedAwait(...)` and
      `normalizeCommandAwaitTimeout(...)`
    - chat send responses now include `dispatch_status`:
      - `resolved` when the command returns within the bound
      - `pending` when the command is dispatched but does not resolve before
        the timeout
      - `rejected` only when the command promise rejects
    - added extension setting:
      `openwukong.bridge.chatCommandAwaitTimeoutMs`
      with default `2500`
    - documented that `dispatch_status=pending` means dispatch-pending and
      transcript/state readback is a separate proof layer
    - extended `tests/test_ide_extension_scaffold.py` to lock the bounded await
      contract, setting, README wording, and dispatch-pending behavior
    - synced the fixed extension into the correct Cursor profile with backup:
      `logs/runtime/cursor-owned-live-r247/ide_extension_sync_r248_chat_timeout.json`
  - recovery and live validation:
    - user reported the Cursor window was unusable and asked to close it and
      restart Cursor
    - all `Cursor.exe` processes were stopped, the stale bridge registry file
      was removed, and the normal Cursor profile was restarted on:
      `E:/ideaProjects/agent/PaoPaoHeZi`
    - new live registry appeared at:
      `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/0358330502d0e374c785665d.json`
    - visible Cursor window after restart:
      `pasted-text.txt - PaoPaoHeZi - Cursor`
    - installed running extension source contained:
      `executeCommandWithBoundedAwait`, `chatCommandAwaitTimeoutMs`,
      `dispatch_status`, and `Promise.race`
    - real Cursor Agent send validation artifact:
      `logs/runtime/cursor-owned-live-r247/cursor_live_agent_send_validation_r249.json`
    - real send marker:
      `OPENWUKONG_CURSOR_AGENT_SEND_R249_20260627163729`
    - real send result:
      - `ok=true`
      - `send_ok=true`
      - `send_status=200`
      - `send_elapsed_ms=230`
      - `dispatch_status=resolved`
      - `command_id=composer.sendToAgent`
      - `adapter_id=cursor`
      - `capability_alive_after_send=true`
      - `control_attempts=0`
      - `window_input_attempts=0`
      - `keyboard_input_attempts=0`
      - `clipboard_write_attempts=0`
    - transcript readback remains separate and currently pending:
      - `full_readback_ok=false`
      - `readback_decision=cursor_transcript_readback_pending`
      - scanned key:
        `composerData:5a04a9fe-de69-4691-ad54-ca141c04f53a`
  - validation:
    - focused tests passed:
      `python -m unittest tests.test_ide_extension_scaffold`
      with `4` tests OK
    - syntax check passed:
      `node --check extensions/openwukong-vscode/src/extension.js`
    - `git diff --check` passed for the touched extension and scaffold test
      files, with only CRLF working-copy warnings
    - created reusable global skill:
      `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug`
  - current conclusion:
    - the correct logged-in Cursor profile now has a live OpenWukong bridge
      that can execute deterministic owned scratch commands and dispatch a real
      Cursor Agent send without freezing the bridge
    - this validates background IDE operation at the bridge/command-dispatch
      layer for Cursor
    - full model-response proof still requires a stronger Cursor transcript or
      state readback path; the current storage scanner did not find the marker
      after dispatch
  - next concrete actions:
    1. strengthen Cursor transcript/state readback so a sent marker and Agent
       reply can be verified after dispatch without foreground UI control
    2. promote the live Cursor send path into an owned live IDE demo/report once
       transcript readback or an equivalent state proof is available
    3. keep arbitrary Generic Desktop at `foreground_required` until there is a
       deterministic native bridge or explicitly authorized foreground session

## 2026-06-28 R250-R253: Reboot recovery, Cursor bridge hardening, and Codex-panel route split

- user rebooted Windows and asked to continue from the Cursor/Codex bridge
  validation work
- context and rules:
  - reread `.agents/README.md`
  - reread `.agents/conversation_index.md`
  - used the global `project-memory-snapshot` workflow; this file remains the
    repository-owned durable memory for current project state
  - used the global `ide-extension-bounded-await-debug` workflow because the
    failure involved VS Code/Cursor extension bridge endpoints and private IDE
    commands hanging the bridge
  - official docs consulted before code changes:
    - VS Code API documentation for `vscode.commands.executeCommand`,
      extension commands, and extension-host APIs
    - Python official dataclasses documentation for touched report dataclasses
- reboot recovery:
  - no active bridge registry existed after reboot
  - restarted the correct logged-in Cursor profile, not the wrong login-needed
    program:
    `E:/cursor/cursor/cursor/Cursor.exe E:/ideaProjects/agent/PaoPaoHeZi`
  - live bridge restored at:
    `http://127.0.0.1:8787`
  - active registry after final restart:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/1cb852fd550221186240d6c2.json`
  - running workspace:
    `e:/ideaProjects/agent/PaoPaoHeZi`
- R250 after-reboot deterministic validation:
  - safe scratch validation passed with marker:
    `OPENWUKONG_CURSOR_SCRATCH_R250_AFTER_REBOOT_20260628`
  - artifact:
    `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_after_reboot_scratch_validation.json`
  - no foreground mouse, keyboard, or clipboard route was used
- R250/R251 send and state-read findings:
  - `composer.sendToAgent` dispatch returned quickly after the R248 bounded
    chat-await fix:
    - R250 marker:
      `OPENWUKONG_CURSOR_AGENT_SEND_R250_AFTER_REBOOT_20260628`
    - artifact:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_agent_send_after_reboot_r250.json`
    - `send_elapsed_ms=101`
    - `dispatch_status=resolved`
  - first composer-state hardening added bounded await around
    `composer.getComposerHandleById`, but live validation showed this was not
    sufficient:
    - immediate composer-state returned
      `cursor_live_composer_state_pending`
    - following `/v1/ide/capabilities` calls then timed out
  - mandatory third-round复盘 conclusion:
    - first fix solved the unbounded `/v1/ide/chat` await
    - second fix solved an unbounded composer-state await
    - both missed a deeper layer: invoking Cursor's private
      `composer.getComposerHandleById` can itself poison/block the extension
      host or command service while an Agent turn is active, even if our caller
      stops awaiting it
- R251/R252 selected-only composer-state fix:
  - changed `/v1/ide/cursor/composer-state` default behavior to read selected
    composer ids only
  - full handle reads now require:
    - `include_handles: true`
    - `safety_profile: "isolated_cursor_read_probe"`
  - Python client and live probe now carry:
    - `include_handles`
    - `handle_read_allowed`
    - `handle_read_policy`
    - `pending_commands`
    - `command_errors`
  - fallback state read no longer invokes
    `composer.getComposerHandleById` unless isolated read profile is explicit
  - live selected-only validation before and after send stayed alive:
    - artifact before send:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_composer_state_r251_selected_only_before_send.json`
    - R252 send artifact:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_agent_send_r252_selected_only.json`
    - post-send state artifact:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_composer_state_r252_after_send.json`
    - `state_status=selected_only`
    - `handle_read_allowed=false`
    - capabilities remained alive after state read
- R253 command/draft-hook safety gate:
  - added `DANGEROUS_CURSOR_COMMANDS` in
    `extensions/openwukong-vscode/src/extension.js`
  - `/v1/ide/command` now blocks direct
    `composer.getComposerHandleById` with:
    `cursor_command_requires_isolated_profile`
    unless the request carries an isolated Cursor safety profile
  - Cursor draft hook now blocks both dry-run and write handle reads outside:
    `safety_profile: "isolated_cursor_draft_probe"`
  - draft-hook validation now passes isolated safety profile into the dry-run
    phase and uses isolated read profile for post-write composer readback
  - updated extension README and scaffold tests to lock the new safety contract
  - updated global reusable skill:
    `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug`
    with the lesson that bounded await is not enough if command invocation
    itself is unsafe
- R253 live install and validation:
  - controlled sync applied the updated extension to Cursor:
    `logs/runtime/cursor-owned-live-r250-after-reboot/ide_extension_sync_r253_command_gate.json`
  - backup directory:
    `logs/runtime/cursor-owned-live-r250-after-reboot/ide-extension-backups-r253`
  - after a final selected-handle policy correction, controlled sync was
    applied again:
    `logs/runtime/cursor-owned-live-r250-after-reboot/ide_extension_sync_r254_selected_handle_policy.json`
  - final backup directory:
    `logs/runtime/cursor-owned-live-r250-after-reboot/ide-extension-backups-r254`
  - restarted the correct Cursor profile:
    `E:/ideaProjects/agent/PaoPaoHeZi`
  - final active registry:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/a0754ea87f8734e3307d9820.json`
  - final bridge process id:
    `40732`
  - installed running extension source contains:
    - `DANGEROUS_CURSOR_COMMANDS`
    - `cursor_command_requires_isolated_profile`
    - `cursor_draft_hook_read_requires_isolated_profile`
  - live gate validation artifact:
    `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_r253_command_gate_validation.json`
  - live gate result:
    - `ok=true`
    - capabilities before gate: HTTP `200`, about `76.74ms`
    - default composer-state: HTTP `200`, `state_status=selected_only`
    - direct dangerous command: HTTP `403`,
      `error=cursor_command_requires_isolated_profile`
    - draft hook without safety: HTTP `409`,
      `error=cursor_draft_hook_read_requires_isolated_profile`
    - capabilities after gate: HTTP `200`, about `18.225ms`
    - `control_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - final post-R254 live gate check:
    - artifact:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_r254_final_gate_check.json`
    - `ok=true`
    - capabilities: HTTP `200`
    - direct dangerous command: HTTP `403`
    - `error=cursor_command_requires_isolated_profile`
    - running installed source contains the selected-handle policy correction:
      `if (allowHandleRead && !commandSet.has(CURSOR_COMPOSER_HANDLE_COMMAND))`
  - safe owned scratch command still works after the gate:
    - artifact:
      `logs/runtime/cursor-owned-live-r250-after-reboot/cursor_live_r253_scratch_after_gate.json`
    - marker:
      `OPENWUKONG_CURSOR_SCRATCH_R253_COMMAND_GATE_20260628`
    - write/read both HTTP `200`
    - marker readback verified
- OpenAI Codex panel route discovery:
  - live capabilities expose OpenAI/Codex extension commands such as:
    - `chatgpt.addToThread`
    - `chatgpt.addFileToThread`
    - `chatgpt.newChat`
    - `chatgpt.newCodexPanel`
    - `chatgpt.openSidebar`
    - `chatgpt.openCommandMenu`
  - installed Codex extension:
    `C:/Users/Zhangjinqian/.cursor/extensions/openai.chatgpt-26.5623.31443-win32-x64`
  - local code inspection showed:
    - `chatgpt.addToThread` adds the active editor/selection to context; it
      does not accept prompt text
    - `chatgpt.addFileToThread` adds file URI context
    - `chatgpt.newChat` and `chatgpt.newCodexPanel` open/create UI surfaces;
      they do not expose a direct prompt-send command contract
    - webview assets support prefill through `shared-object-set` key
      `composer_prefill` followed by an `open-vscode-command` message, but
      that is a webview-message route, not a plain
      `vscode.commands.executeCommand(...)` prompt-send route
- current conclusion:
  - background IDE bridge operation is now stable for:
    - capabilities
    - owned scratch write/read
    - selected-only Cursor composer state
    - rejecting dangerous Cursor private handle reads in normal profiles
  - `composer.sendToAgent` dispatch can return successfully, but transcript
    readback still has no marker proof
  - the visible right-side agent is the OpenAI Codex extension panel, so the
    next real breakthrough is not more `composer.sendToAgent` retries; it is a
    Codex-extension-specific bridge or webview-message path for:
    1. prefill/send prompt
    2. observe thread/turn state
    3. prove transcript/readback without foreground input
- validation:
  - focused tests:
    `python -m unittest tests.test_ide_extension_scaffold tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_draft_hook_probe tests.test_ide_extension_connector`
    with `36` tests OK
  - related tests:
    `python -m unittest tests.test_ide_extension_scaffold tests.test_cursor_live_composer_state tests.test_cursor_draft_hook_validation tests.test_cursor_draft_hook_probe tests.test_ide_extension_connector tests.test_ide_extension_readiness tests.test_cursor_attach_bridge_validation`
    with `49` tests OK
  - syntax:
    `node --check extensions/openwukong-vscode/src/extension.js`
    OK
  - skill validation:
    `quick_validate.py C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug`
    OK
  - diff check:
    `git diff --check` passed for touched files with only CRLF working-copy
    warnings
- next concrete actions:
  1. build a Codex extension bridge/readback probe that targets the installed
     `openai.chatgpt` extension and its webview/shared-object route, rather
     than Cursor composer private commands
  2. add a Codex-panel capability matrix that marks `chatgpt.addToThread` as
     context-only and blocks treating it as a prompt-send command
  3. promote "operate computer via IDE" only after a complete
     `send + transcript/readback` proof exists for the Codex panel; until then
     the validated level is stable background IDE bridge control, not full
     arbitrary desktop operation

## 2026-06-28 R255-R256: Codex extension command matrix and webview-route proof

- user asked to continue after the Cursor bridge hardening work
- context and rules:
  - reread `.agents/README.md`
  - reread `.agents/conversation_index.md`
  - used the global `project-memory-snapshot` workflow; this file remains the
    repository-owned durable memory for current project state
  - official docs consulted before code changes:
    - VS Code API documentation for extension commands, `vscode.extensions`,
      and webview/extension-host boundaries
  - OpenAI product handling:
    - checked the locally installed OpenAI Codex extension first:
      `C:/Users/Zhangjinqian/.cursor/extensions/openai.chatgpt-26.5623.31443-win32-x64`
- implementation:
  - added read-only endpoint:
    `POST /v1/ide/codex/capabilities`
  - endpoint inspects the installed `openai.chatgpt` extension through
    `vscode.extensions.getExtension("openai.chatgpt")`
  - endpoint classifies known Codex commands instead of treating them as
    prompt-send commands:
    - `chatgpt.addToThread`: `context_only`
    - `chatgpt.addFileToThread`: `context_only`
    - `chatgpt.newChat`: `surface_open`
    - `chatgpt.newCodexPanel`: `surface_open`
    - `chatgpt.openSidebar`: `surface_open`
    - `chatgpt.openCommandMenu`: `surface_open`
    - `chatgpt.showLspMcpCliArgs`: `diagnostic`
  - endpoint reports:
    - `prompt_send_ready`
    - `requires_webview_bridge`
    - `extension.exports` type and export keys
    - contributed `chatgpt.*` commands
    - zero control/window/keyboard/clipboard attempts
  - added Python client method:
    `IDEExtensionBridgeClient.read_codex_capabilities(...)`
  - added read-only probe:
    `openwukong.evaluation.codex_extension_bridge_probe`
  - the probe scans the local installed Codex extension for route markers:
    - `composer_prefill`
    - `shared-object-set`
    - `open-vscode-command`
  - updated extension README and tests to lock the Codex command-role
    contract
- live validation:
  - controlled sync applied the new bridge endpoint:
    `logs/runtime/codex-extension-bridge-r255/ide_extension_sync_r255_codex_capabilities.json`
  - after adding runtime export-key probing, controlled sync applied again:
    `logs/runtime/codex-extension-bridge-r255/ide_extension_sync_r256_codex_exports.json`
  - Cursor was restarted on the correct logged-in profile:
    `E:/ideaProjects/agent/PaoPaoHeZi`
  - final live bridge registry:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/08c4d25ccf4c4102de5eed67.json`
  - final live bridge process id:
    `59500`
  - live probe artifact:
    `logs/runtime/codex-extension-bridge-r255/codex_extension_bridge_probe_live_r256.json`
  - live result:
    - `ok=true`
    - `decision=codex_extension_webview_bridge_required`
    - `extension_installed=true`
    - `extension_version=26.5623.31443`
    - `prompt_send_ready=false`
    - `requires_webview_bridge=true`
    - `extension_exports_type=undefined`
    - `extension_export_keys=[]`
    - `control_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - webview route snippet artifact:
    `logs/runtime/codex-extension-bridge-r255/codex_webview_route_snippets_r256.json`
  - route evidence:
    - `out/extension.js` contains host-side handling for
      `shared-object-set` and `open-vscode-command`
    - `webview/assets/composer-BSCaQqMy.js` contains
      `composer_prefill` and `prefillPrompt`
    - `codex-micro-insert-composer-text` exists in the webview bundle and is
      a DOM/webview-side event handler, not a VS Code command
- current conclusion:
  - the OpenAI Codex extension has no public prompt-send command exposed
    through `vscode.commands`
  - the OpenAI Codex extension exports no callable public extension API in the
    live profile (`extension.exports` is `undefined`)
  - the available route is webview/shared-object based:
    - host handles `shared-object-set`
    - webview consumes `composer_prefill`
    - webview can ask host to run commands through `open-vscode-command`
  - because VS Code does not expose a public API for one extension to post
    arbitrary messages into another extension's webview, a complete Codex panel
    send path needs a dedicated Codex-side bridge strategy rather than retries
    through public `chatgpt.*` commands
- validation:
  - focused tests:
    `python -m unittest tests.test_codex_extension_bridge_probe tests.test_ide_extension_connector tests.test_ide_extension_scaffold`
    with `20` tests OK
  - related tests:
    `python -m unittest tests.test_codex_extension_bridge_probe tests.test_ide_extension_connector tests.test_ide_extension_scaffold tests.test_ide_extension_readiness tests.test_ide_extension_sync`
    with `35` tests OK
  - syntax:
    `node --check extensions/openwukong-vscode/src/extension.js`
    OK
  - Python compile:
    `python -m py_compile src/openwukong/evaluation/codex_extension_bridge_probe.py src/openwukong/connectors/ide_extension.py`
    OK
  - diff check:
    `git diff --check` passed for the touched Codex bridge files with only
    CRLF working-copy warnings
- next concrete actions:
  1. design a Codex-side bridge strategy that can set `composer_prefill` and
     trigger `chatgpt.newChat/newCodexPanel` without foreground keyboard or
     clipboard input
  2. keep `chatgpt.addToThread` and `chatgpt.addFileToThread` permanently
     marked as context-only, not prompt-send
  3. only promote Codex panel operation after a live `send + transcript/readback`
     marker proof exists through the Codex-specific bridge

## 2026-06-28 R257: Codex webview/shared-object bridge strategy contract

- user asked to continue from the Codex extension command-matrix work
- context and rules:
  - reread `.agents/README.md`
  - reread `.agents/conversation_index.md`
  - used the global `project-memory-snapshot` workflow; this file remains the
    repository-owned durable memory for current project state
  - official docs consulted before code changes:
    - VS Code Webview API documentation for message-passing and webview
      ownership boundaries
- extra local inspection:
  - inspected the installed OpenAI Codex extension URI handler around
    `registerUriHandler`
  - handler class `hI` only uses `uri.path` and calls
    `codexWebviewProvider.navigateToRoute(path)`
  - no URI/deep-link prompt or `composer_prefill` parameter contract was found
  - snippet files written under:
    `logs/runtime/codex-extension-bridge-r255/uri_handler_*.txt`
- implementation:
  - added dry-run strategy module:
    `src/openwukong/evaluation/codex_webview_bridge_strategy.py`
  - added tests:
    `tests/test_codex_webview_bridge_strategy.py`
  - the strategy report consumes the R256 Codex extension probe and classifies
    all candidate routes:
    - `public_vscode_prompt_command`: blocked because no `chatgpt.*` command
      is classified as `prompt_send`
    - `public_extension_exports_api`: blocked because live
      `openai.chatgpt` has `extension.exports=undefined`
    - `deep_link_prefill`: blocked because the URI handler only navigates by
      path and exposes no prompt/prefill contract
    - `cross_extension_webview_post_message`: blocked because VS Code does not
      expose another extension's webview object for arbitrary `postMessage`
    - `foreground_keyboard_or_clipboard`: rejected by the no-foreground and
      no-clipboard operation contract
    - `codex_side_shared_object_bridge`: selected as the only candidate route
      because `composer_prefill`, `shared-object-set`, and
      `open-vscode-command` markers are verified
  - required contract now explicitly lists the future bridge steps:
    1. run inside the Codex extension/webview boundary or an explicitly owned
       patched Codex profile
    2. set shared object key `composer_prefill` with text, cwd, and attachments
    3. trigger `chatgpt.newChat` or `chatgpt.newCodexPanel` after prefill is
       present
    4. submit from Codex-side code without keyboard, mouse, or clipboard input
    5. read thread or turn state and prove the marker appears in transcript or
       response
- live strategy validation:
  - input probe artifact:
    `logs/runtime/codex-extension-bridge-r255/codex_extension_bridge_probe_live_r256.json`
  - strategy artifact:
    `logs/runtime/codex-extension-bridge-r255/codex_webview_bridge_strategy_r257.json`
  - result:
    - `ok=true`
    - `decision=codex_webview_bridge_strategy_ready`
    - `recommended_strategy=codex_side_shared_object_bridge`
    - `implementation_stage=dry_run_contract`
    - `public_prompt_command_ready=false`
    - `public_extension_api_ready=false`
    - `webview_route_verified=true`
    - `control_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
- validation:
  - focused tests:
    `python -m unittest tests.test_codex_webview_bridge_strategy tests.test_codex_extension_bridge_probe`
    with `4` tests OK
  - related tests:
    `python -m unittest tests.test_codex_webview_bridge_strategy tests.test_codex_extension_bridge_probe tests.test_ide_extension_connector tests.test_ide_extension_scaffold tests.test_ide_extension_readiness tests.test_ide_extension_sync`
    with `37` tests OK
  - Python compile:
    `python -m py_compile src/openwukong/evaluation/codex_webview_bridge_strategy.py src/openwukong/evaluation/codex_extension_bridge_probe.py src/openwukong/connectors/ide_extension.py`
    OK
  - diff check:
    `git diff --check` passed for the touched strategy files with only CRLF
    working-copy warnings
- current conclusion:
  - the next build step should not target `vscode.commands`,
    `extension.exports`, URI deep links, or foreground UI
  - the only evidence-backed route is a Codex-side shared-object bridge that
    runs within the Codex extension/webview boundary or an explicitly owned
    patched Codex profile
- next concrete actions:
  1. build an isolated Codex-profile patch/sync mechanism that can add a
     minimal Codex-side bridge without touching the user's normal Codex
     extension install
  2. implement the first bridge dry-run inside that isolated profile:
     set `composer_prefill` only, verify it appears in composer state, and make
     zero send attempts
  3. only after prefill readback is proven, add Codex-side submit and transcript
     marker readback

## 2026-06-28 R258: Isolated Codex bridge patch/sync mechanism

- user asked to continue after Windows reboot and after the correct Cursor/Codex
  bridge process was available
- context and rules:
  - reread `.agents/README.md`
  - reread `.agents/conversation_index.md`
  - used the global `project-memory-snapshot` workflow; this file remains the
    repository-owned durable memory for current project state
  - official docs consulted before code changes:
    - VS Code command API documentation for `registerCommand` command
      contribution/runtime behavior
    - VS Code Webview API documentation for webview ownership/message
      boundaries
- implementation:
  - added isolated Codex bridge patch module:
    `src/openwukong/evaluation/codex_isolated_bridge_patch.py`
  - added tests:
    `tests/test_codex_isolated_bridge_patch.py`
  - the patch mechanism:
    - treats the normal Cursor/VS Code extension profile as read-only
    - blocks any isolated root under normal extension roots such as
      `.cursor/extensions` and `.vscode/extensions`
    - validates the live Codex extension markers:
      `composer_prefill`, `shared-object-set`, and `open-vscode-command`
    - validates the concrete Codex entrypoint insertion anchor:
      `e.push(Ue);let _e=new hI(Ue);`
    - copies the Codex extension only into an explicit isolated root when
      `--apply` is passed
    - patches only the isolated copy with command:
      `openwukong.codexBridge.prefillDryRun`
    - command behavior is intentionally prefill-only:
      writes shared object key `composer_prefill`, broadcasts
      `shared-object-updated`, and returns zero send/control/keyboard/
      clipboard attempts
    - writes an isolated manifest:
      `openwukong-codex-bridge-manifest.json`
    - reports `codex_extension_source_not_found` when automatic extension
      discovery fails instead of treating the current repository as a source
- live isolated patch validation:
  - source Codex extension:
    `C:/Users/Zhangjinqian/.cursor/extensions/openai.chatgpt-26.5623.31443-win32-x64`
  - source version:
    `26.5623.31443`
  - live dry-run artifact:
    `logs/runtime/codex-extension-bridge-r258/codex_isolated_bridge_patch_dry_run.json`
  - live apply artifact:
    `logs/runtime/codex-extension-bridge-r258/codex_isolated_bridge_patch_applied.json`
  - isolated patched extension:
    `logs/runtime/codex-extension-bridge-r258/isolated-extensions/openai.chatgpt-26.5623.31443-win32-x64`
  - result:
    - `ok=true`
    - `decision=codex_isolated_bridge_patch_applied`
    - `normal_profile_touched=false`
    - `write_attempts=3`
    - `copy_attempts=1`
    - `patch_attempts=1`
    - `send_attempts=0`
    - `control_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - second-pass verification:
    - isolated copy contains `OPENWUKONG_CODEX_BRIDGE_PATCH_V1`
    - isolated copy contains `openwukong.codexBridge.prefillDryRun`
    - normal source extension does not contain the OpenWukong patch marker
    - isolated manifest exists and records zero send/control/input attempts
- validation:
  - focused tests:
    `python -m unittest tests.test_codex_isolated_bridge_patch tests.test_codex_webview_bridge_strategy tests.test_codex_extension_bridge_probe`
    with `9` tests OK
  - related tests:
    `python -m unittest tests.test_codex_isolated_bridge_patch tests.test_codex_webview_bridge_strategy tests.test_codex_extension_bridge_probe tests.test_ide_extension_connector tests.test_ide_extension_scaffold tests.test_ide_extension_readiness tests.test_ide_extension_sync`
    with `42` tests OK
  - Python compile:
    `python -m py_compile src/openwukong/evaluation/codex_isolated_bridge_patch.py src/openwukong/evaluation/codex_webview_bridge_strategy.py src/openwukong/evaluation/codex_extension_bridge_probe.py`
    OK
  - JavaScript syntax:
    `node --check logs/runtime/codex-extension-bridge-r258/isolated-extensions/openai.chatgpt-26.5623.31443-win32-x64/out/extension.js`
    OK
  - diff/whitespace:
    `git diff --check` passed for tracked touched files
    - direct trailing-whitespace scan over the two new files produced no
      matches
  - Git hygiene:
    - `logs/` is ignored by `.gitignore`
    - the 724 MB isolated Codex copy under `logs/runtime` does not appear in
      `git status`
- current conclusion:
  - we now have a safe isolated patched Codex extension copy that can be used
    for the first real `composer_prefill` bridge experiment
  - no normal Cursor/Codex extension install was modified
- next concrete actions:
  1. launch a Cursor/Codex test profile that uses the isolated extension root
     instead of the normal `.cursor/extensions` root
  2. execute `openwukong.codexBridge.prefillDryRun` against that isolated
     profile through the owned IDE bridge and prove `composer_prefill` readback
     in composer state
  3. only after prefill readback is proven, add a second isolated command for
     Codex-side submit and transcript marker readback

## 2026-06-28 R259 - Codex app-server real send probe

- scope:
  - validate a real Codex app-server send path without foreground desktop
    input
  - use the bundled local Codex CLI instead of touching the live Codex
    Desktop stdio app-server process
- verified environment:
  - live Codex Desktop process is backed by:
    `C:/Program Files/WindowsApps/OpenAI.Codex_26.623.5546.0_x64__2p2nqsd0c76g0/app/resources/codex.exe app-server --analytics-default-enabled`
  - direct WindowsApps binary execution from PowerShell is blocked by
    Windows permissions
  - bundled local Codex CLI is available at:
    `C:/Users/Zhangjinqian/AppData/Local/OpenAI/Codex/bin/aec6b7c6fcdfb66a/codex.exe`
  - `codex --version` reports `codex-cli 0.142.3`
  - `codex app-server --help` supports `--listen <URL>` including
    `ws://IP:PORT`
- readiness result:
  - launched an ephemeral loopback app-server with:
    `codex app-server --listen ws://127.0.0.1:57232`
  - `probe_codex_app_server_ws` returned:
    - `ok=true`
    - `decision=codex_app_server_ws_ready`
    - `thread_list_ok=true`
    - `initialize_ok=true`
    - `control_attempts=0`
    - `window_input_attempts=0`
  - artifact:
    `logs/runtime/codex-real-send-r259/ephemeral_ws_readiness.json`
- real send result:
  - launched a second ephemeral loopback app-server with:
    `codex app-server --listen ws://127.0.0.1:62497`
  - created a real Codex thread for this repository:
    `019f0c7f-7582-7831-956f-d1d2c7caf578`
  - `windowsSandbox/readiness` returned `status=ready`
  - called `turn/start` with marker:
    `OPENWUKONG_REAL_SEND_R259_20260628T123147`
  - created turn:
    `019f0c7f-8176-77d2-86f9-e6a89b625b28`
  - `app_server_thread_start_attempts=1`
  - `app_server_turn_start_attempts=1`
  - `control_attempts=0`
  - `window_input_attempts=0`
  - artifact:
    `logs/runtime/codex-real-send-r259/codex_real_send_actual.json`
- observed failure:
  - the send reached Codex and wrote a session JSONL under:
    `C:/Users/Zhangjinqian/.codex/sessions/2026/06/28/rollout-2026-06-28T12-31-47-019f0c7f-7582-7831-956f-d1d2c7caf578.jsonl`
  - the session contains the user marker request and a `token_count` event
  - that `token_count` event reports:
    `credits.has_credits=false`, `credits.unlimited=false`, and
    `credits.balance=0`
  - the thread then emitted `thread/status/changed` with `systemError`
  - no assistant delta or marker readback was produced
- conclusion:
  - the no-foreground app-server send path reached `thread/start` and
    `turn/start`
  - the remaining blocker for transcript marker readback is the Codex account
    credit state, not local bridge delivery
  - the ephemeral WS app-server process was terminated after the probe and left
    no live helper process
- next concrete actions:
  1. restore usable Codex credits/account state and rerun the same marker-only
     real send probe
  2. after assistant marker readback succeeds, promote the ephemeral WS
     app-server launcher/cleanup path into a first-class connector
  3. update connector metadata and foreground gates so owned ephemeral
     loopback app-servers are not misclassified as live foreground Desktop UI

## 2026-06-28 R260-R262 - Codex app-server real send verified

- user asked to retry after the previous Codex credit blocker
- rerun basis:
  - used the bundled local Codex CLI:
    `C:/Users/Zhangjinqian/AppData/Local/OpenAI/Codex/bin/aec6b7c6fcdfb66a/codex.exe`
  - used ephemeral loopback `codex app-server --listen ws://127.0.0.1:<port>`
  - did not touch the live Codex Desktop stdio app-server process
  - used `approvalPolicy=never` and read-only sandbox policy
  - all probes kept:
    - `control_attempts=0`
    - `window_input_attempts=0`
- R260:
  - artifact:
    `logs/runtime/codex-real-send-r260/codex_real_send_actual.json`
  - result was initially reported as success, but stricter inspection showed
    the marker hit came from `userMessage` echo, not assistant output
  - R260 is not accepted as assistant readback proof
  - this exposed a reusable parser requirement:
    marker validation must count only `item/agentMessage/delta`,
    assistant `response_item`, or `task_complete.last_agent_message`
- R261:
  - artifact:
    `logs/runtime/codex-real-send-r261/codex_real_send_actual.json`
  - real thread:
    `019f0ca2-76a6-78b2-b21a-d199db1d4b9e`
  - real turn:
    `019f0ca2-839c-7bc2-a5fa-576f7a6b479c`
  - assistant delta text:
    `OPENWUKONG_REAL_SEND_R261_20260628T131001`
  - `turn_status=completed`
  - `system_error_seen=false`
  - strict assistant marker readback was verified
  - foreground hwnd changed during the run:
    - before: Codex window, hwnd `394890`
    - after: Weixin window, hwnd `132456`
  - because of that foreground change, R261 proves send/readback but is not
    used as no-foreground stability proof
- R262:
  - artifact:
    `logs/runtime/codex-real-send-r262/codex_real_send_actual.json`
  - real thread:
    `019f0ca4-0c52-7dc2-9b04-de368e1b224f`
  - real turn:
    `019f0ca4-1810-7070-8090-1a8263ce1b10`
  - assistant delta text:
    `OPENWUKONG_REAL_SEND_R262_20260628T131145`
  - `assistant_marker_seen_in_delta=true`
  - `assistant_marker_seen_in_session=true`
  - `turn_done=true`
  - `turn_status=completed`
  - `system_error_seen=false`
  - `foreground_hwnd_before=394890`
  - `foreground_hwnd_after=394890`
  - `foreground_focus_stable=true`
  - no live ephemeral app-server process remained after cleanup
- current conclusion:
  - the owned ephemeral Codex app-server WS path can now:
    1. start a real thread for the repository
    2. call real `turn/start`
    3. receive assistant `item/agentMessage/delta`
    4. verify exact assistant marker readback
    5. complete without foreground focus change in the accepted R262 run
  - this is the first accepted end-to-end Codex app operation proof through a
    product-native app-server transport, not keyboard/mouse/clipboard
  - reusable validation pattern was promoted into a global skill:
    `C:/Users/Zhangjinqian/.codex/skills/codex-app-server-marker-readback-debug/SKILL.md`
    - `quick_validate.py` passed
- next concrete actions:
  1. promote the ephemeral WS app-server launcher/cleanup and strict assistant
     readback parser into first-class connector code with regression tests
  2. fix connector metadata/gating so owned loopback app-server endpoints are
     classified separately from live Windows Desktop app-server foreground risk
  3. update the readiness matrix so Codex App moves from blocked/dry-run to
     background native app-server send/readback ready when the strict contract
     passes

## 2026-06-28 R263-R265 - Codex app-server first-class connector promoted

- continued the owned ephemeral Codex app-server work after R262
- code promoted the ephemeral app-server path into first-class connector logic:
  - owned `codex app-server --listen ws://127.0.0.1:<port>` launcher/cleanup
  - owned endpoint metadata:
    - `surface_kind=owned_ephemeral_app_server`
    - `owned_loopback_app_server=true`
    - `turn_start_foreground_safe=true`
    - `force_fresh_thread_start=true`
  - readiness matrix accepts Codex app-server send only after strict
    `turn/start` verification
- R263 real integrated run:
  - artifact:
    `logs/runtime/codex-app-server-integrated-r263/integrated_real_send_r263.json`
  - failed because a stale R262 thread from `thread/list useStateDbOnly=true`
    was reused and the fresh app-server returned `thread not found`
  - fix: owned ephemeral app-server now forces fresh `thread/start`
- R264 real integrated run:
  - artifact:
    `logs/runtime/codex-app-server-integrated-r264/integrated_real_send_r264.json`
  - created a new thread and real turn
  - WebSocket notifications did not deliver `turn/completed`, so the runner
    initially reported `codex_app_server_turn_start_completion_missing`
  - later evidence from the real session JSONL proved assistant completion:
    - assistant `response_item`
    - `event_msg.task_complete.last_agent_message`
    - exact marker:
      `OPENWUKONG_REAL_SEND_R264_20260628T132940`
  - fix: strict session fallback was added, counting only assistant-owned
    records and never request/user echoes
- R265 real integrated run:
  - artifact:
    `logs/runtime/codex-app-server-integrated-r265/integrated_real_send_r265.json`
  - marker:
    `OPENWUKONG_REAL_SEND_R265_20260628T133942`
  - result:
    - `decision=codex_app_server_turn_start_verified`
    - `codex_app_server_thread_start_verified=true`
    - `codex_app_server_turn_start_verified=true`
    - transport matrix `send_ready=true`
    - strict assistant/session readback verified
    - `control_attempts=0`
    - `window_input_attempts=0`
    - `foreground_no_steal_verified=true`
  - temporary owned app-server process was stopped after the run
- validation:
  - focused Codex/app-server suite: 107 tests OK
  - wider control suite: 185 tests OK
  - `py_compile` OK for touched modules
  - `git diff --check` OK except existing CRLF normalization warnings
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/codex-app-server-marker-readback-debug/SKILL.md`
  - created project memory snapshot:
    `docs/project-memory-snapshot.md`
- current conclusion:
  - Codex now has a verified background native app-server send/readback path
    for real messages
  - this reaches "operate the app through a product-native transport" for
    Codex, not arbitrary OS-level mouse/keyboard takeover
- next concrete actions:
  1. use the same first-class connector standard for Cursor owned bridge /
     browser DevTools paths
  2. add a concise Computer Operation Readiness Matrix view that surfaces
     Codex as `background_execute_verified`
  3. keep foreground UIA/desktop input gated as fallback, not the primary route

## 2026-06-28 R266 - Computer Operation Matrix surfaces Codex verified background execution

- continued after R265 by promoting the verified Codex app-server proof into
  the plan-only Computer Operation Readiness Matrix
- implementation:
  - added a first-class `codex` surface to
    `src/openwukong/evaluation/computer_operation_readiness_matrix.py`
  - added `operation_status` and `verified` fields per surface
  - Codex keeps `readiness_level=background_execute` for compatibility, and
    adds `operation_status=background_execute_verified` only when strict
    app-server turn evidence passes
  - CLI now accepts `--codex-app-server-turn-start-report`
    - it can read either a bare turn/start report or a full integrated artifact
    - R265 artifact is accepted directly
- strict Codex matrix requirements:
  - `decision=codex_app_server_turn_start_verified`
  - `turn_completed=true`
  - `turn_status=completed`
  - required marker appears in assistant readback
  - no missing required markers
  - no forbidden markers
  - `foreground_no_steal_verified=true`
  - `control_attempts=0`
  - `window_input_attempts=0`
  - exactly one app-server turn/start attempt
- generated R266 artifact:
  `logs/runtime/computer-operation-status-r266/computer_operation_readiness_r266.json`
  - summary `background_execute_verified_surfaces=["codex"]`
  - Codex `operation_status=background_execute_verified`
  - Codex `verified=true`
  - matrix `control_attempts=0`
- validation:
  - `tests.test_computer_operation_readiness_matrix`: 5 tests OK
  - related suite:
    `tests.test_computer_operation_readiness_matrix`
    `tests.test_objective_readiness_matrix`
    `tests.test_agent_app_transport_matrix`
    `tests.test_agent_app_real_no_loss`
    - 49 tests OK
  - `py_compile` OK for the matrix module
  - `git diff --check` OK for touched files except existing CRLF warning on
    `.agents/conversation_index.md`
- current conclusion:
  - Codex is now visibly classified as a verified background-execute surface
    in the project-level operation matrix
  - Terminal/Git remain background-execute ready by deterministic connector
  - Browser/Cursor/WeChat/Office remain unverified or blocked until their own
    owned/background evidence passes
- next concrete actions:
  1. run the same owned/background verification standard for Cursor owned
     bridge and browser DevTools
  2. when each passes, feed their artifacts into the matrix rather than
     manually marking them ready
  3. keep Generic Desktop foreground-required until a semantic native route is
     proven

## 2026-06-28 R267 - Browser DevTools verified and promoted into operation matrix

- selected Browser DevTools as the next surface after Codex because it already
  has an owned isolated helper path and does not depend on user login state
- code changes:
  - extended `ComputerOperationReadinessOptions` with
    `owned_browser_demo_report`
  - added CLI flag `--owned-browser-demo-report`
  - Browser remains blocked/ready-only by default, but upgrades to:
    - `readiness_level=background_execute`
    - `operation_status=background_execute_verified`
    - `verified=true`
    only when an owned browser demo artifact passes strict checks
- strict Browser verification requires:
  - `decision=owned_browser_demo_verified`
  - `safety_mode=isolated_owned_browser_devtools`
  - Browser workflow `ok=true`
  - workflow quality summary has `failed=0` and passed checks
  - owned DevTools launch result started
  - manifest stop succeeded
  - profile cleanup deleted the isolated profile
  - `desktop_control_attempts=0`
  - `window_input_attempts=0`
  - Browser CDP control attempts are present for real DOM operation
- real R267 run:
  - command launched isolated headless Chrome with loopback DevTools
  - marker:
    `OPENWUKONG_OWNED_BROWSER_R267`
  - browser demo artifact:
    `logs/runtime/owned-browser-safe-operation-demo-r267/owned_browser_safe_operation_demo.json`
  - result:
    - `decision=owned_browser_demo_verified`
    - `control_attempts=3`
    - `desktop_control_attempts=0`
    - `window_input_attempts=0`
    - workflow steps:
      `navigate_url`, `set_input_value`, `submit_form`, `read_page`,
      `extract_results`
    - quality summary: `passed=6`, `failed=0`
    - manifest stop succeeded
    - isolated profile cleanup deleted the profile
  - residual process check found no R267 Chrome/helper process; only the
    current PowerShell check command matched its own command line
- generated matrix:
  `logs/runtime/computer-operation-status-r267/computer_operation_readiness_r267.json`
  - summary `background_execute_verified_surfaces=["codex","browser"]`
  - background execute surfaces:
    `["codex","browser","terminal","git"]`
  - verified background execute count: `2`
  - matrix `control_attempts=0`
- validation:
  - `tests.test_computer_operation_readiness_matrix`: 7 tests OK
  - related browser/matrix suite:
    `tests.test_computer_operation_readiness_matrix`
    `tests.test_owned_browser_safe_operation_demo`
    `tests.test_browser_devtools_action`
    `tests.test_browser_devtools_health`
    `tests.test_browser_devtools_dom_probe`
    `tests.test_control_fabric_browser_workflow`
    `tests.test_agent_app_transport_matrix`
    - 43 tests OK
  - `py_compile` OK for touched Browser/matrix modules
  - `git diff --check` OK except existing CRLF warning on
    `.agents/conversation_index.md`
- current conclusion:
  - Browser is now the second verified background-execute surface after Codex
  - verified surfaces now cover:
    - Codex app-server text send/readback
    - owned Browser DevTools DOM operation/readback
  - Terminal/Git remain deterministic background-execute ready but not yet
    artifact-marked as `background_execute_verified`
- next concrete actions:
  1. run the same evidence standard for Cursor owned bridge
  2. then decide whether Terminal/Git need explicit verified artifact status or
     whether deterministic command connector readiness is enough for this stage
  3. keep Office/WeChat/Generic Desktop blocked or foreground-required until
     owned native routes pass equivalent proofs

## 2026-06-28 R268-R270 - IDE matrix verification and Cursor attach-only correction

- R268 promoted owned IDE live bridge evidence into the Computer Operation
  Readiness Matrix:
  - accepted artifact:
    `logs/runtime/owned-ide-live-bridge-demo-r246/owned_ide_live_bridge_demo.json`
  - generated matrix:
    `logs/runtime/computer-operation-status-r268/computer_operation_readiness_r268.json`
  - summary:
    `background_execute_verified_surfaces=["codex","browser","ide"]`
  - verified background execute count: `3`
  - matrix `control_attempts=0`
- implementation:
  - `ComputerOperationReadinessOptions` now accepts `owned_ide_demo_report`
  - matrix CLI accepts `--owned-ide-demo-report`
  - IDE only becomes `operation_status=background_execute_verified` when
    strict owned live bridge evidence passes:
    owned scratch workspace binding, `openwukong.writeScratch`, readback,
    quality checks, ownership gate, and zero desktop/window/keyboard/clipboard
    input
  - status report now passes owned browser/IDE matrix evidence, not just bridge
    URLs, when it discovers runtime artifacts
- Cursor process correction:
  - attempted isolated Cursor validation with `--user-data-dir` created an
    unauthenticated Cursor login window
  - that route is not suitable for the user's already logged-in Cursor workflow
  - removed stale isolated bridge registry:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/4c1cfd516bb01beeb08af937.json`
  - retained correct live bridge:
    `http://127.0.0.1:8787`
  - correct bridge is registered in:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/08c4d25ccf4c4102de5eed67.json`
  - correct bridge is bound to:
    `E:/ideaProjects/agent/PaoPaoHeZi`
- registry hardening:
  - IDE bridge discovery now filters by workspace identity when target
    `workspace_path` is provided
  - same-family Cursor bridges from different workspaces are no longer accepted
  - legacy registry entries without workspace identity are rejected for
    workspace-specific attach
- R270 attach-only run:
  - artifact:
    `logs/runtime/cursor-attach-r270-correct-bridge/cursor_attach_r270_correct_bridge.json`
  - no launch attempts
  - no stop attempts
  - `control_attempts=0`
  - `window_input_attempts=0`
  - foreground stayed stable on Codex
  - bridge readiness passed against `http://127.0.0.1:8787`
  - draft-hook dry-run timed out after 8 seconds on live `PaoPaoHeZi`
- validation:
  - focused related tests:
    `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_owned_ide_live_bridge_demo tests.test_owned_ide_safe_operation_demo tests.test_owned_browser_safe_operation_demo tests.test_ide_bridge_registry tests.test_cursor_attach_bridge_validation tests.test_cursor_isolated_draft_hook_runner tests.test_cursor_draft_hook_probe tests.test_cursor_draft_hook_validation`
    with `46` tests OK
  - `py_compile` OK for touched matrix/status/registry/Cursor attach modules
  - `git diff --check` reported only existing CRLF normalization warnings
- current conclusion:
  - Codex, Browser, and IDE now have artifact-backed verified background
    execution status in the matrix
  - live Cursor should now be handled through attach-only `8787`, not by
    launching an isolated profile
  - the next real Cursor blocker is live draft-hook latency/timeout, not
    workspace or bridge selection
- next concrete actions:
  1. fix/bound `/v1/ide/cursor/draft-hook` on the live logged-in
     `PaoPaoHeZi` bridge without starting a new Cursor process
  2. add a strict attach-only Cursor send/readback artifact after the bounded
     route passes
  3. keep isolated Cursor profile launch disabled for the normal logged-in
     workflow unless the user explicitly asks for isolated-profile testing

## 2026-06-28 R271 - Live Cursor attach-only fix and real dispatch proof

- trigger:
  - user corrected that the previous isolated Cursor process was the wrong
    login window and that the correct logged-in Cursor process was already
    open
- root cause review:
  - R248 fixed unbounded `/v1/ide/chat` awaits
  - R253 gated dangerous Cursor private handle reads
  - the remaining R270 timeout happened because draft-hook still read the VS
    Code command registry before rejecting or selecting the safe profile; a
    stale/poisoned command service could therefore block even an intended
    fast rejection
  - a second failure layer appeared during recovery: an empty Cursor window
    auto-started an OpenWukong bridge on `8789` with no workspace identity
- implementation:
  - added `live_cursor_attach_draft_probe` for attach-only dry-runs against
    the existing logged-in Cursor bridge
  - `/v1/ide/cursor/draft-hook` now validates unsafe safety profiles before
    `vscode.commands.getCommands(true)`
  - added bounded command discovery via
    `openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs`
  - live attach dry-run checks a low-risk `composer.createNew` route and does
    not read `composer.getComposerHandleById`
  - live attach writes remain blocked; private handle reads remain
    isolated-profile-only
  - added `openwukong.bridge.autoStartRequiresWorkspace=true` so empty Cursor
    windows do not publish workspace-less bridge endpoints
  - synced the updated extension into:
    `C:/Users/Zhangjinqian/.cursor/extensions/openwukong-local.openwukong-vscode-bridge-0.1.0`
    with backups under `logs/runtime/cursor-attach-r271/`
- live correction:
  - stopped only the stale Cursor NodeService that owned the old 8787 bridge,
    then restored the correct `PaoPaoHeZi` workspace bridge
  - stopped the empty-workspace 8789 bridge and removed only its registry file
  - final registry set contains only:
    `C:/Users/Zhangjinqian/AppData/Local/OpenWukong/ide-bridges/10fe1fa3e9302e323b861bc8.json`
  - final correct bridge:
    `http://127.0.0.1:8787`
  - final workspace:
    `E:/ideaProjects/agent/PaoPaoHeZi`
- validation artifacts:
  - attach-only:
    `logs/runtime/cursor-attach-r271/cursor_attach_r271_final.json`
    - `decision=cursor_attach_bridge_dry_run_ready`
    - `ok=true`
    - `launch_attempts=0`
    - `window_input_attempts=0`
    - `foreground_changed=false`
    - dry-run response:
      `cursor_draft_hook_live_attach_ready`
      with `handle_read_allowed=false`
  - real Cursor Agent dispatch:
    `logs/runtime/cursor-attach-r271/cursor_agent_send_r271_final.json`
    - `decision=cursor_agent_send_dispatched`
    - `ok=true`
    - `command_id=composer.sendToAgent`
    - `dispatch_status=resolved`
    - `chat_elapsed_ms=30.519`
    - `scratch_readback_verified=true`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
    - `foreground_changed=false`
  - final bridge state:
    - `8787` is live and workspace-bound
    - `8789` did not respawn after the autoStart workspace guard
- validation:
  - focused suite:
    `python -m unittest tests.test_ide_extension_scaffold tests.test_cursor_draft_hook_probe tests.test_cursor_draft_hook_validation tests.test_cursor_attach_bridge_validation tests.test_ide_extension_connector tests.test_ide_extension_readiness tests.test_ide_extension_sync tests.test_ide_bridge_registry tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_owned_ide_live_bridge_demo`
    with `70` tests OK
  - `node --check extensions/openwukong-vscode/src/extension.js` passed
  - `py_compile` passed for touched Python modules
  - `git diff --check` reported only CRLF normalization warnings
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug/SKILL.md`
  - added patterns for:
    1. rejection paths hanging before they reject
    2. empty IDE windows publishing workspace-less bridges
- next concrete actions:
  1. add strict Cursor transcript/readback proof after `composer.sendToAgent`
     without active-profile private handle reads
  2. promote R271 live Cursor dispatch evidence into the readiness matrix once
     transcript/readback acceptance criteria are defined
  3. keep isolated Cursor launches disabled for the normal logged-in workflow

## 2026-06-28 R272 - Strict Cursor assistant transcript gate and dispatch-only negative proof

- trigger:
  - user asked to continue after correcting that the previously opened Cursor
    login window was the wrong process and that the correct logged-in Cursor
    bridge was already running
- implementation:
  - tightened `cursor_transcript_readback` from broad marker search to
    role-aware marker evidence
  - default acceptance now requires `required_response_role=assistant`
  - Cursor `bubbleId... type=1` is classified as user-side
  - Cursor `bubbleId... type=2` is classified as assistant-side
  - `composerData`, `messageRequestContext`, prompt blobs, and ambiguous
    `agentKv:blob` hits no longer satisfy final assistant readback
  - exact marker scanning now also checks `bubbleId`, `messageRequestContext`,
    `composerData`, and `agentKv:blob` rows so selected-composer drift does not
    hide diagnostic hits
  - CLI gained `--required-response-role` and `--allow-any-role`; the latter
    is discovery-only
- false-positive review:
  - historical `OPENWUKONG_CURSOR_REAL_SEND_R75` was reclassified as
    `cursor_transcript_readback_non_response_marker_only`
  - the marker existed in:
    - `agentKv:blob:6048a022...` as ambiguous prompt/request content
    - `bubbleId:a9a6e98f... type=1` user `text` / `richText`
  - no assistant-side marker location was present
- real R272 send:
  - artifact:
    `logs/runtime/cursor-transcript-r272/cursor_agent_strict_readback_r272.json`
  - marker:
    `OPENWUKONG_CURSOR_AGENT_STRICT_R272_20260628T144055`
  - route:
    existing logged-in Cursor bridge `http://127.0.0.1:8787`
    bound to `E:/ideaProjects/agent/PaoPaoHeZi`
  - result:
    - `command_id=composer.sendToAgent`
    - `dispatch_status=resolved`
    - strict transcript result:
      `cursor_agent_assistant_transcript_readback_pending`
    - after `22` polls / about `120` seconds:
      `required_markers_found=[]`
    - `required_markers_found_anywhere=[]`
    - `response_marker_locations=[]`
    - scanned keys only contained current `composerData`
  - no Cursor process was launched
  - no keyboard, mouse, clipboard, or foreground UI input path was used
- validation:
  - `python -m unittest tests.test_cursor_transcript_readback`
    with `6` tests OK
  - `python -m unittest tests.test_cursor_transcript_readback
    tests.test_agent_app_real_no_loss tests.test_ide_extension_connector
    tests.test_ide_bridge_capture tests.test_ide_bridge_contract_probe`
    with `75` tests OK
  - `py_compile` passed for
    `src/openwukong/evaluation/cursor_transcript_readback.py` and
    `tests/test_cursor_transcript_readback.py`
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug/SKILL.md`
  - added the pattern that dispatch `resolved` is not assistant completion and
    marker acceptance must require assistant/response-side evidence
- current conclusion:
  - Cursor dispatch is not the same as operation completion
  - `composer.sendToAgent` can return resolved while neither the user marker
    nor an assistant marker appears in the readable local transcript stores
  - do not promote R271/R272 Cursor Agent dispatch to
    `background_execute_verified`
- next concrete actions:
  1. stop spending primary effort on more `composer.sendToAgent` retries
  2. build a verifiable Cursor native composer/draft-submit hook or locate an
     official/readable transcript surface that exposes assistant response rows
  3. keep the strict assistant transcript gate as the acceptance condition for
     any future Cursor Agent send proof

## 2026-06-28 R273/R274 - Cursor draft write verified, Glass Agent query proven prefill-only

- trigger:
  - user asked to continue after the correct logged-in Cursor window was open
    and allowed real send validation
  - previous attempts had accidentally opened an unauthenticated Cursor login
    window, so all live work stayed on the registered `PaoPaoHeZi` bridge
- R273 implementation:
  - added `live_cursor_attach_draft_write_probe` as an explicit live safety
    profile for Cursor draft writes
  - live draft writes use `composer.createNew` with `skipShowAndFocus`,
    `skipSelect`, `openInNewTab=false`, and Agent-mode `partialState`
  - live draft readback uses local Cursor storage with
    `required_response_role=user`; it does not read private composer handles
    in the user's active profile
- R273 live result:
  - artifact:
    `logs/runtime/cursor-draft-r273/live_draft_validation.json`
  - decision:
    `cursor_draft_hook_validated`
  - marker:
    `OPENWUKONG_CURSOR_LIVE_DRAFT_R273_20260628T165752`
  - `draft_write_attempts=1`
  - `window_input_attempts=0`
  - `foreground_changed=false`
  - marker found in Cursor `composerData` user/draft-side state
  - conclusion: Cursor background draft injection is verified, but this is not
    assistant completion
- R274 implementation:
  - added dedicated endpoint:
    `/v1/ide/cursor/glass-agent-query`
  - added safety profile:
    `live_cursor_glass_agent_query_probe`
  - added Python probe and strict validation:
    `cursor_glass_agent_query_probe.py`
    and `cursor_glass_agent_query_validation.py`
  - validation accepts completion only when assistant-side transcript readback
    finds the required marker; `user_marker_only` is explicitly incomplete
  - validation now supports `--required-marker` so the prompt may differ from
    the marker expected in assistant output
- R274 live setup:
  - extension synced into the installed Cursor profile with backup:
    `logs/runtime/cursor-glass-r274/ide-extension-backups/openwukong-local.openwukong-vscode-bridge-0.1.0.openwukong-backup-20260628-170831`
  - the correct workspace bridge stayed:
    `http://127.0.0.1:8787`
    for `E:/ideaProjects/agent/PaoPaoHeZi`
  - temporary `workbench.action.reloadWindow` allowlist change was restored
    after reload
- R274 dry-run result:
  - artifact:
    `logs/runtime/cursor-glass-r274/glass_query_dry_run_after_reload.json`
  - decision:
    `cursor_glass_agent_query_ready`
  - selected command:
    `glass.newAgentWithQuery`
- R274 real send result:
  - artifact:
    `logs/runtime/cursor-glass-r274/glass_agent_live_validation_r274b.json`
  - marker:
    `OPENWUKONG_CURSOR_GLASS_AGENT_R274B_20260628T171413`
  - `command_id=glass.newAgentWithQuery`
  - `dispatch_status=resolved`
  - `decision=cursor_glass_agent_query_readback_pending`
  - `foreground_changed=false`
  - `system_dialog_detected=false`
  - `window_input_attempts=0`
  - `keyboard_input_attempts=0`
  - `clipboard_write_attempts=0`
  - user-side readback: pending, marker absent
  - assistant-side readback: pending, marker absent
  - full SQLite marker searches found zero matches:
    - `logs/runtime/cursor-glass-r274/global_marker_search_r274b.json`
    - `logs/runtime/cursor-glass-r274/workspace_marker_search_r274b.json`
- Cursor bundle evidence:
  - `glass.newAgentWithQuery` emits:
    `setPendingPromptRequested`
    followed by
    `newAgentRequested`
  - the real submit path is deeper:
    `submitInitialLocalAgentMessage`
    calling
    `submitChatMaybeAbortCurrent`
  - conclusion:
    `glass.newAgentWithQuery` is a prefill/open route, not a verified submit
    route
- validation:
  - `node --check extensions/openwukong-vscode/src/extension.js` passed
  - `py_compile` passed for the new Cursor Glass probe/validation modules and
    touched bridge files
  - `python -m unittest tests.test_cursor_glass_agent_query_probe
    tests.test_cursor_glass_agent_query_validation tests.test_ide_extension_scaffold`
    ran `12` tests OK
  - after adding `--required-marker`,
    `python -m unittest tests.test_cursor_glass_agent_query_validation
    tests.test_cursor_glass_agent_query_probe`
    ran `8` tests OK
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug/SKILL.md`
  - added the pattern that Agent-query-like commands may only prefill/open a
    draft and must not be treated as submit routes without assistant-side
    readback
- current conclusion:
  - Cursor can now be controlled to the level of background draft injection
    with local storage proof
  - Cursor still cannot be claimed as background Agent execution because both
    `composer.sendToAgent` and `glass.newAgentWithQuery` resolve without
    assistant-side completion evidence
- next concrete actions:
  1. stop retrying `composer.sendToAgent` and `glass.newAgentWithQuery` as
     submit routes
  2. find or build an in-process Cursor service hook to reach
     `submitInitialLocalAgentMessage` / `submitChatMaybeAbortCurrent`, or find
     an official transcript/readback surface
  3. in parallel, continue expanding real computer-operation coverage through
     transports already proven background-safe: Codex app-server, Browser
     DevTools, owned IDE bridge, and Cursor draft injection

## 2026-06-28 R275 Cursor Readiness Matrix Split

- user correction:
  - Cursor had already been implemented earlier through foreground UIA/clipboard
    fallback and later through the live logged-in draft-hook path
  - the missing piece is not "Cursor control exists", but "Cursor Agent submit
    plus assistant readback exists without foreground input"
- implementation:
  - added a dedicated `cursor` / `Cursor Agent` surface to
    `computer_operation_readiness_matrix`
  - added explicit report fields:
    - `verified_capabilities`
    - `partial_capabilities`
    - `fallback_transports`
  - preserved real Cursor capabilities separately:
    - `background_draft_injection`
    - `foreground_uia_clipboard_draft_fallback`
  - kept full Cursor Agent send blocked with:
    - `operation_status=cursor_submit_readback_blocked`
    - missing `cursor_submit_native_service_hook`
    - missing `assistant_response_marker_readback`
  - updated `computer_operation_status_report` markdown and next actions so
    Cursor draft/fallback proof does not imply `background_execute`
  - exposed Cursor evidence JSON arguments in both readiness/status CLIs
- real read-only artifact generation:
  - `logs/runtime/computer-operation-status-r275/computer_operation_readiness_r275.json`
  - `logs/runtime/computer-operation-status-r275/computer_operation_status_r275.json`
  - `logs/runtime/computer-operation-status-r275/computer_operation_status_r275.md`
  - summary from real artifacts:
    - `background_draft_surfaces=["cursor"]`
    - Cursor not present in `background_execute_surfaces`
    - Cursor not present in `background_execute_verified_surfaces`
    - Cursor `can_write_without_focus=true`
    - Cursor `can_execute_without_focus=false`
- validation:
  - `python -m unittest tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report` ran `13` tests OK
  - `python -m unittest tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report
    tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix
    tests.test_agent_app_real_no_loss` ran `57` tests OK
  - `python -m py_compile src\openwukong\evaluation\computer_operation_readiness_matrix.py
    src\openwukong\evaluation\computer_operation_status_report.py` passed
  - `git diff --check` reported only existing CRLF normalization warnings
- reusable learning:
  - updated global skill
    `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug/SKILL.md`
  - added the pattern that capability matrices must not collapse draft,
    foreground fallback, private command dispatch, and assistant-completed
    submit into one readiness state
- next concrete actions:
  1. implement or discover a submit-capable Cursor service hook around
     `submitInitialLocalAgentMessage` / `submitChatMaybeAbortCurrent`
  2. prove assistant/response-side readback after that hook with zero keyboard,
     clipboard, mouse, and foreground changes
  3. keep Cursor draft and foreground UIA fallback available as separate
     capabilities, not as background execution proof

## 2026-06-28 R276 WeChat Readiness Matrix Split

- user correction:
  - stop forcing the Cursor path for now
  - move the next breakthrough to WeChat because WeChat had already been
    implemented earlier
- historical evidence reclassified:
  - 2026-05-27 live WeChat File Transfer Assistant send remains a real
    successful send, but it used explicit foreground keyboard/clipboard
    takeover and is therefore a foreground fallback, not background control
  - the WeChat native bridge contract, dynamic endpoint registry, fixture
    smoke, live read-only evidence backend, and Fabric binding remain valid
    infrastructure
  - fixture sends prove the local bridge protocol only; they do not prove real
    personal WeChat background sending
- implementation:
  - added WeChat-specific readiness logic in
    `computer_operation_readiness_matrix`
  - added evidence JSON inputs:
    - `wechat_foreground_send_report`
    - `wechat_native_bridge_send_report`
    - `wechat_native_bridge_fixture_report`
  - added CLI flags with the same names in readiness/status reports
  - added `foreground_send_surfaces` summary output
  - WeChat now only becomes `background_execute_verified` when a real
    `wechat-native-bridge-send` report proves:
    - one native call
    - zero window/keyboard/clipboard attempts
    - foreground focus stable
    - target matched
    - background screenshot verified
    - required marker readback present
    - forbidden markers absent
  - bridge URL plus screenshot evidence alone is now kept out of
    `background_execute`
  - foreground File Transfer Assistant send is preserved as verified capability
    `foreground_file_transfer_send`
  - fixture bridge send is preserved as partial capability
    `native_bridge_fixture_send_verified`
- real read-only artifact generation:
  - `logs/runtime/computer-operation-status-r276/computer_operation_readiness_r276.json`
  - `logs/runtime/computer-operation-status-r276/computer_operation_status_r276.json`
  - `logs/runtime/computer-operation-status-r276/computer_operation_status_r276.md`
  - R276 artifact summary:
    - `foreground_send_surfaces=["wechat"]`
    - WeChat is not in `background_execute_surfaces`
    - WeChat `readiness_level=foreground_required`
    - WeChat `operation_status=foreground_required`
    - WeChat `blocking_reason=wechat_native_send_readback_not_verified`
- validation:
  - `python -m py_compile src\openwukong\evaluation\computer_operation_readiness_matrix.py
    src\openwukong\evaluation\computer_operation_status_report.py` passed
  - focused suite:
    `python -m unittest tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `17` tests OK
  - related suite:
    `python -m unittest tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report
    tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix
    tests.test_agent_app_real_no_loss tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_wechat_native_endpoint_publisher`
    ran `78` tests OK
  - `python -m py_compile src\openwukong\control\wechat_native_bridge.py
    src\openwukong\connectors\wechat_native_bridge.py` passed
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
  - added the pattern that foreground IM sends, native bridge fixtures, route
    readiness, and real background-native send/readback must not be collapsed
    into one capability
- next concrete actions:
  1. implement the real WeChat File Transfer Assistant native send/readback
     backend behind the existing local bridge contract
  2. keep it File Transfer Assistant only until target matching and readback are
     deterministic
  3. maintain zero window/keyboard/clipboard and foreground-stability gates as
     hard acceptance criteria

## 2026-06-28 R277 WeChat Real Foreground Send Revalidated

- trigger:
  - user explicitly allowed a real WeChat send test and redirected the next
    breakthrough from Cursor to WeChat
  - the goal was to verify the already implemented foreground File Transfer
    Assistant path without mistaking it for background-native control
- real preflight and target selection:
  - app resolution selected the already running personal WeChat executable:
    `E:\software\Weixin\Weixin.exe`
  - system-dialog preflight stayed clear:
    `logs/runtime/wechat-real-send-r277/preflight_system_dialog.json`
  - read-only locator found personal WeChat `微信` and Enterprise WeChat
    separately; the send probe remained constrained to personal
    `Weixin.exe` / `WeChat.exe`
  - locator artifact:
    `logs/runtime/wechat-real-send-r277/wechat_locator_before_send.json`
- foreground takeover evidence:
  - foreground takeover request:
    `logs/runtime/wechat-real-send-r277/foreground_takeover_request.json`
  - approved action:
    `send_message`
  - approved target:
    `文件传输助手`
  - approved transport:
    `foreground-keyboard-clipboard`
  - risk flags preserved:
    `native_connector_missing`, `foreground_focus_steal`,
    `clipboard_mutation`
- prepare/no-send run:
  - artifact:
    `logs/runtime/wechat-real-send-r277/prepare_no_send/report.json`
  - result:
    `blocked_target_not_verified`
  - send attempts stayed zero
  - screenshot confirmed the File Transfer Assistant target before the real run
- real send result:
  - artifact:
    `logs/runtime/wechat-real-send-r277/real_send/report.json`
  - marker:
    `OPENWUKONG_WECHAT_R277_REAL_SEND_20260628T174958`
  - status:
    `sent`
  - `send_attempts=1`
  - `keyboard_input_attempts=6`
  - `clipboard_write_attempts=2`
  - `clipboard_restore_attempts=1`
  - `foreground_restore_attempts=1`
  - `target_verified=true`
  - `post_send_screenshot_bound=true`
  - bound-window screenshot:
    `logs/runtime/wechat-real-send-r277/real_send/post_send_verify.png`
  - cropped visual evidence:
    `logs/runtime/wechat-real-send-r277/real_send/post_send_verify_chat_crop.png`
  - screenshot visibly contains the marker in the `文件传输助手`
    conversation
- important limitation:
  - `post_send_verified=false`
  - `post_send_verification.method=not_available`
  - therefore R277 proves a real foreground fallback send, not automated
    marker readback and not background-native WeChat control
- status/reporting fix:
  - `computer_operation_status_report` now accepts:
    `--codex-app-server-ws-url`
    and
    `--codex-app-server-turn-start-report`
  - status summary now includes:
    `verified_background_execute_count`
  - reason:
    full evidence status reports were otherwise unable to include the
    existing strict Codex app-server proof and could misleadingly show Codex as
    blocked
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
  - added the pattern that wrapper/status reports must not silently drop
    lower-level readiness evidence, because that creates a false capability
    regression
- generated artifacts:
  - focused readiness:
    `logs/runtime/computer-operation-status-r277/computer_operation_readiness_r277.json`
  - focused status:
    `logs/runtime/computer-operation-status-r277/computer_operation_status_r277.json`
  - focused markdown:
    `logs/runtime/computer-operation-status-r277/computer_operation_status_r277.md`
  - full evidence readiness:
    `logs/runtime/computer-operation-status-r277/computer_operation_readiness_r277_full_evidence.json`
  - full evidence status:
    `logs/runtime/computer-operation-status-r277/computer_operation_status_r277_full_evidence.json`
  - full evidence markdown:
    `logs/runtime/computer-operation-status-r277/computer_operation_status_r277_full_evidence.md`
  - full evidence summary:
    - `background_execute_surfaces=["codex","browser","terminal","git","ide"]`
    - `background_execute_verified_surfaces=["codex","browser","ide"]`
    - `background_draft_surfaces=["cursor"]`
    - `foreground_send_surfaces=["wechat"]`
    - `verified_background_execute_count=3`
    - `verified_background_draft_count=1`
- validation:
  - `python -m unittest tests.test_computer_operation_status_report
    tests.test_computer_operation_readiness_matrix`
    ran `18` tests OK
  - `python -m unittest tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report
    tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix
    tests.test_agent_app_real_no_loss tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_wechat_native_endpoint_publisher`
    ran `79` tests OK
  - `python -m py_compile
    src\openwukong\evaluation\computer_operation_status_report.py
    tests\test_computer_operation_status_report.py`
    passed
- next concrete actions:
  1. add automated post-send marker readback for the bound WeChat HWND, using
     OCR/accessibility if available, so the foreground fallback can be verified
     without manual screenshot inspection
  2. implement the real WeChat native File Transfer Assistant send/readback
     backend behind the existing local bridge contract
  3. keep WeChat `foreground_file_transfer_send`,
     `native_bridge_fixture_send_verified`, and real
     `background_execute_verified` as separate capability layers

## 2026-06-28 R278 - WeChat OCR readback moved off encoded PowerShell

- user reported Windows Defender false positive:
  - `Trojan:Win32/Steanoz.Z!MTB`
  - affected command line shape:
    `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -EncodedCommand ...`
  - this came from the exploratory Windows OCR verifier, not from a fresh
    WeChat send
- change:
  - removed the WeChat post-send OCR/readback dependency on encoded
    PowerShell launchers
  - `src/openwukong/evaluation/wechat_send_probe.py` now calls Windows OCR
    through Python WinRT:
    `Windows.Media.Ocr`, `Windows.Graphics.Imaging`, and
    `Windows.Storage.Streams`
  - declared Windows-only dependencies in:
    - `pyproject.toml`
    - `requirements.txt`
  - installed the same packages in `.venv`:
    - `winrt-Windows.Media.Ocr==3.2.1`
    - `winrt-Windows.Graphics.Imaging==3.2.1`
    - `winrt-Windows.Storage.Streams==3.2.1`
- regression:
  - `tests/test_wechat_send_probe.py` now verifies that the WeChat
    OCR/readback module does not contain:
    - `-EncodedCommand`
    - `ExecutionPolicy`
    - `_run_ocr_powershell`
- real screenshot replay:
  - artifact:
    `logs/runtime/wechat-readback-r278/post_send_python_winrt_ocr_replay_r277.json`
  - source screenshot:
    `logs/runtime/wechat-real-send-r277/real_send/post_send_verify.png`
  - marker:
    `OPENWUKONG_WECHAT_R277_REAL_SEND_20260628T174958`
  - result:
    - `verified=true`
    - `ocr_method=python-winrt-windows-media-ocr`
    - `normalized_marker_matched=true`
    - `fresh_send_attempted=false`
    - `powershell_encoded_command_used=false`
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
  - added failure pattern:
    encoded PowerShell OCR/readback launchers can trip Defender; use a native
    API backend such as Python WinRT and add a no-encoded-launcher regression
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\wechat_send_probe.py
    tests\test_wechat_send_probe.py`
    passed
  - `python -m unittest tests.test_wechat_send_probe`
    ran `14` tests OK
- next concrete action:
  - run one fresh explicit foreground WeChat File Transfer Assistant send with
    the Python WinRT OCR helper active, and require the integrated report to
    show `post_send_verified=true` without encoded PowerShell

## 2026-06-28 R279 - Fresh WeChat foreground send with Python WinRT OCR readback

- preflight:
  - `logs/runtime/wechat-real-send-r279/preflight_system_dialog.json`
    reported `system_dialog_clear`
  - `logs/runtime/wechat-real-send-r279/security_window_scan.json`
    reported `security_window_detected=false`
  - `logs/runtime/wechat-real-send-r279/wechat_locator_before_send.json`
    observed both personal WeChat and Enterprise WeChat:
    - personal: `Weixin.exe`, title `微信`, class `Qt51514QWindowIcon`
    - enterprise: `WXWork.exe`, title `企业微信`, class `WeWorkWindow`
  - the send probe selected personal WeChat by exact process/class, not by
    fuzzy app name
- foreground takeover:
  - `logs/runtime/wechat-real-send-r279/foreground_takeover_request.json`
  - request id:
    `fgt-wechat-r279-filehelper-python-winrt-ocr`
- real send:
  - artifact:
    `logs/runtime/wechat-real-send-r279/real_send/report.json`
  - marker:
    `OPENWUKONG_WECHAT_R279_REAL_SEND_20260628T190000`
  - result:
    - `status=sent`
    - `target_name=文件传输助手`
    - `send_attempts=1`
    - `keyboard_input_attempts=6`
    - `clipboard_write_attempts=2`
    - `clipboard_restore_attempts=1`
    - `foreground_restore_attempts=1`
    - `post_send_screenshot_bound=true`
    - `post_send_verified=true`
    - `post_send_verification.method=windows-media-ocr-readback`
    - `ocr_method=python-winrt-windows-media-ocr`
    - `normalized_marker_matched=true`
- status report:
  - `logs/runtime/computer-operation-status-r279/computer_operation_status_r279.json`
  - `logs/runtime/computer-operation-status-r279/computer_operation_status_r279.md`
  - WeChat remains `readiness_level=foreground_required`
  - WeChat verified capabilities now include:
    - `foreground_file_transfer_send`
    - `foreground_post_send_marker_readback`
  - evidence now includes:
    - `wechat_foreground_post_send_verified=true`
    - `wechat_foreground_post_send_verification_method=windows-media-ocr-readback`
    - `wechat_foreground_post_send_ocr_method=python-winrt-windows-media-ocr`
    - `wechat_foreground_post_send_normalized_marker_matched=true`
  - background-native blocker remains:
    `wechat_native_send_readback_not_verified`
- code update:
  - `computer_operation_readiness_matrix` now preserves foreground post-send
    readback evidence without promoting WeChat to background execution
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\computer_operation_readiness_matrix.py
    tests\test_computer_operation_readiness_matrix.py`
    passed
  - `python -m unittest tests.test_computer_operation_readiness_matrix`
    ran `13` tests OK
  - final focused validation:
    `python -m unittest tests.test_wechat_send_probe
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `32` tests OK
  - final focused `python -m py_compile` on the WeChat send probe,
    readiness matrix, status report, and focused tests passed
  - `git diff --check` reported only existing CRLF normalization warnings
- next concrete action:
  - implement a real WeChat native bridge send/readback backend that keeps
    window, keyboard, clipboard, and foreground-focus attempts at zero

## 2026-06-28 R280 - WeChat native real-send probe and current backend blocker

- added explicit native real-send probe:
  - `src/openwukong/evaluation/wechat_native_bridge_real_send_probe.py`
  - test:
    `tests/test_wechat_native_bridge_real_send_probe.py`
- behavior:
  - discovers localhost/loopback WeChat native bridge URLs from explicit
    `--bridge-url`, env/default registry paths, and supplied registry paths
  - performs WeChat native bridge dry-run first
  - requires explicit `--allow-send` before calling `/v1/wechat/send`
  - never falls back to foreground keyboard, mouse, clipboard, SendInput, or
    UIA mutation
  - emits a wrapper report with nested `send_report` accepted by the readiness
    matrix
- regression coverage:
  - no `--allow-send` calls only capabilities endpoints, send/native attempts
    remain zero
  - ready local fixture with `--allow-send` performs one native call, one send,
    zero window/keyboard/clipboard attempts, and marker readback
  - wrapper report fed into readiness matrix promotes WeChat to
    `background_execute_verified` only through the nested real
    `wechat-native-bridge-send` report
  - bridge endpoint with `send_action_ready=false` never calls `/v1/wechat/send`
- current-machine dry-run:
  - artifact:
    `logs/runtime/wechat-native-real-r280/dry_run.json`
  - result:
    - `decision=wechat_native_bridge_url_missing`
    - `discovered_urls=[]`
    - `send_attempts=0`
    - `native_call_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - conclusion:
    no send-capable WeChat native bridge URL is registered on this machine
- UIA read-only check:
  - artifact:
    `logs/runtime/wechat-native-real-r280/accessibility_probe.json`
  - personal WeChat remains `structure_only`
  - `input_candidate_count=0`
  - `semantic_input_count=0`
  - `semantic_action_count=0`
  - conclusion:
    UIA is not a safe background write backend for WeChat on this machine
- reusable learning:
  - updated global skill:
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
  - added pattern:
    read-only bridge evidence must not masquerade as native send; discovery,
    dry-run, and real send/readback must stay separate
- validation:
  - `python -m unittest tests.test_wechat_native_bridge_real_send_probe`
    ran `4` tests OK
  - `python -m unittest tests.test_wechat_native_bridge
    tests.test_wechat_native_bridge_fixture_smoke
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_fabric_binding
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `41` tests OK
  - `python -m py_compile` on the new probe/test and WeChat bridge modules
    passed
  - `git diff --check` reported only existing CRLF normalization warnings
- next concrete action:
  - implement or install a send-capable WeChat native bridge backend serving
    `/v1/wechat/capabilities` and `/v1/wechat/send`, then rerun
    `wechat_native_bridge_real_send_probe --allow-send`

## 2026-06-28 R281 - WeChat external-command native bridge backend boundary

- added an opt-in external-command backend for the local WeChat native endpoint:
  - `src/openwukong/control/wechat_native_endpoint_publisher.py`
  - backend name: `external-command`
  - CLI argument:
    `--external-command-json '["path-to-command", "arg1"]'`
  - env fallback:
    `OPENWUKONG_WECHAT_NATIVE_EXTERNAL_COMMAND_JSON`
- behavior:
  - the publisher still serves the existing `/v1/wechat/capabilities` and
    `/v1/wechat/send` contract
  - the backend delegates to one explicit local command via JSON stdin/stdout
  - it uses `subprocess.run(..., shell=False)` and waits for completion, so it
    does not create a detached helper process
  - it never uses keyboard, mouse, clipboard, window input, SendInput, UIA
    mutation, or foreground focus takeover
  - it remains blocked when no command is configured
  - successful capability responses must explicitly declare background safety
    and all foreground/window/keyboard/mouse/clipboard requirements as false
  - successful send responses must explicitly declare foreground stability and
    zero control/window/keyboard/clipboard attempts
- regression coverage:
  - no external command configured is not send-ready and reports zero input
    attempts
  - a fixture external command can complete `/capabilities -> /send` through the
    native bridge sender and produce marker readback with one native call and
    zero window/keyboard/clipboard attempts
  - a failing external command is blocked and keeps input counters at zero
  - an underspecified external command that omits safety declarations is blocked
  - `main(... --backend external-command --external-command-json ... --serve-once)`
    accepts JSON argv and publishes the dynamic registry URL
- validation:
  - `python -m py_compile
    src\openwukong\control\wechat_native_endpoint_publisher.py
    tests\test_wechat_native_endpoint_publisher.py`
    passed
  - `python -m unittest tests.test_wechat_native_endpoint_publisher`
    ran `15` tests OK
  - `python -m unittest tests.test_wechat_native_bridge
    tests.test_wechat_native_bridge_fixture_smoke
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_fabric_binding
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `46` tests OK
  - `git diff --check` reported only existing CRLF normalization warnings
- current-machine conclusion:
  - this implements the safe adapter boundary for a send-capable local backend
  - it does not by itself prove live WeChat background send/readback, because no
    real WeChat external command/SDK backend has been configured yet
- next concrete action:
  - implement the concrete WeChat external command adapter against a real local
    native mechanism, then run the endpoint publisher with `--backend
    external-command` and rerun `wechat_native_bridge_real_send_probe
    --allow-send`

## 2026-06-28 R282 - WeChat native transport discovery probe

- added a read-only WeChat native transport discovery probe:
  - `src/openwukong/evaluation/wechat_native_transport_discovery.py`
  - test:
    `tests/test_wechat_native_transport_discovery.py`
- behavior:
  - enumerates personal WeChat processes with `psutil`
  - enumerates loopback listening TCP ports owned by personal WeChat processes
  - probes lightweight HTTP/CDP fingerprints by GET only
  - optionally probes the existing read-only `/v1/wechat/capabilities` native
    bridge contract
  - enumerates candidate named pipes with email-like pipe prefixes redacted
  - never calls `/v1/wechat/send`
  - keeps `native_call_attempts=0`, `send_attempts=0`,
    `window_input_attempts=0`, `keyboard_input_attempts=0`, and
    `clipboard_write_attempts=0`
- regression coverage:
  - unknown TCP loopback ports remain `tcp-unknown` and do not become ready
  - CDP-like ports are classified as debug transports, not WeChat send bridges
  - send-capable bridge detection only uses `/v1/wechat/capabilities` and does
    not call `/v1/wechat/send`
  - CLI writes a JSON report with zero send attempts
- current-machine discovery:
  - artifact:
    `logs/runtime/wechat-native-transport-r282/discovery.json`
  - result:
    - `decision=wechat_loopback_ports_unknown_protocol`
    - `ok=false`
    - personal WeChat loopback ports:
      `14013`, `14016`, `14019`, `14022`, `14023`
    - all probed ports classified as `tcp-unknown`
    - `send_attempts=0`
    - `native_call_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - conclusion:
    the live Weixin loopback ports are not HTTP, Chrome DevTools Protocol, or
    the OpenWukong `/v1/wechat/capabilities` bridge contract
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\wechat_native_transport_discovery.py
    tests\test_wechat_native_transport_discovery.py`
    passed
  - `python -m unittest tests.test_wechat_native_transport_discovery`
    ran `4` tests OK
  - `python -m unittest tests.test_wechat_native_transport_discovery
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `48` tests OK
  - `git diff --check` reported only existing CRLF normalization warnings
- next concrete action:
  - decide whether to build a supported local helper around a documented SDK
    surface or reverse-engineer Weixin's internal Mojo/ilink IPC separately;
    do not treat the discovered TCP ports as send-capable without protocol-level
    evidence and marker readback

## 2026-06-29 R283 - WeChat native static IPC/helper discovery probe

- added a read-only WeChat native static discovery probe:
  - `src/openwukong/evaluation/wechat_native_static_discovery.py`
  - test:
    `tests/test_wechat_native_static_discovery.py`
- behavior:
  - discovers Weixin install directories from explicit input, environment, and
    running personal WeChat process evidence
  - scans bounded `.dll` and `.exe` candidates without launching, injecting,
    attaching, sending, or calling internal IPC
  - parses PE export tables using the Microsoft PE/COFF RVA/export directory
    layout and records only bounded export samples
  - records keyword hit counts for static IPC/send/helper signals such as
    `ilink`, `mojo`, `ipc`, `pipe`, `localhost`, and send/message terms
  - reads only explicit OpenWukong helper manifests if present
  - keeps `native_call_attempts=0`, `send_attempts=0`,
    `window_input_attempts=0`, `keyboard_input_attempts=0`, and
    `clipboard_write_attempts=0`
- regression coverage:
  - ASCII and UTF-16LE keyword signals are counted without leaking surrounding
    binary context
  - a synthetic PE64 export table is parsed and exposes send/mojo-like exports
  - static ilink/mojo/IPC evidence does not become send-ready without a helper
    contract
  - a documented helper manifest is represented as static contract evidence,
    still with zero send/native/window attempts during discovery
  - CLI writes a JSON report with zero control attempts
- current-machine discovery:
  - artifact:
    `logs/runtime/wechat-native-static-r283/discovery.json`
  - result:
    - `decision=weixin_static_surfaces_found_without_send_contract`
    - `ok=false`
    - scanned files: `24`
    - helper manifests: `0`
    - static signal summary includes:
      `name:ilink=3`, `name:mojo=1`, `keyword:ilink=9`,
      `keyword:mojo=6`, `keyword:ipc=13`, `keyword:pipe=20`,
      `keyword:localhost=6`, `keyword:127.0.0.1=1`,
      `export:send-like=7`, `export:conversation-like=7`
    - `send_attempts=0`
    - `native_call_attempts=0`
    - `window_input_attempts=0`
    - `keyboard_input_attempts=0`
    - `clipboard_write_attempts=0`
  - conclusion:
    current Weixin binaries contain useful ilink/mojo/IPC clues, but there is
    no OpenWukong-consumable helper contract or proven send protocol yet
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\wechat_native_static_discovery.py
    tests\test_wechat_native_static_discovery.py`
    passed
  - `python -m unittest tests.test_wechat_native_static_discovery`
    ran `5` tests OK
  - `python -m unittest tests.test_wechat_native_static_discovery
    tests.test_wechat_native_transport_discovery
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `53` tests OK
  - final `python -m py_compile` on the new static discovery module/test and
    adjacent WeChat native discovery/probe modules passed
  - `git diff --check` reported only existing CRLF normalization warnings
- next concrete action:
  - build a concrete helper/adapter only after one of these is available:
    a documented helper contract, a supported SDK surface, or a separately
    gated protocol implementation for the observed ilink/mojo IPC; static
    binary evidence alone must not promote WeChat to background execution

## 2026-06-29 R284 - OpenClaw-Weixin bot-channel readiness probe

- investigated Tencent's OpenClaw Weixin channel as a separate breakthrough
  path:
  - source inspected from:
    `https://github.com/Tencent/openclaw-weixin`
  - local source snapshot:
    `logs/runtime/openclaw-weixin-r284/openclaw-weixin`
  - package:
    `@tencent-weixin/openclaw-weixin`
  - plugin version from source:
    `2.4.6`
  - plugin channel id:
    `openclaw-weixin`
  - protocol:
    iLink bot HTTP JSON APIs including `getupdates`, `sendmessage`,
    `getuploadurl`, `getconfig`, and `sendtyping`
- important capability boundary:
  - OpenClaw-Weixin is a background Weixin bot-channel candidate
  - it is not personal desktop WeChat control
  - it does not prove File Transfer Assistant send/readback
  - it must be represented as `wechat-openclaw-bot-channel`, not as the
    desktop `wechat` surface
- added a read-only readiness probe:
  - `src/openwukong/evaluation/wechat_openclaw_readiness.py`
  - test:
    `tests/test_wechat_openclaw_readiness.py`
- behavior:
  - checks `openclaw` CLI and Node version without shell execution
  - avoids running `.cmd` shims through `shell=True`; if a Windows shim must be
    executed and Node is new enough, it resolves the adjacent `openclaw.mjs`
    path and runs it through `node` directly
  - reads `~/.openclaw/openclaw.json` without emitting secret values
  - reads OpenClaw-Weixin account metadata from
    `~/.openclaw/openclaw-weixin/accounts.json` and account files, redacting
    account IDs, user IDs, and tokens to hash/length metadata
  - optionally records public plugin source metadata
  - never starts the OpenClaw gateway, never performs QR login, never calls
    `sendmessage`, and keeps all desktop/native/send counters at zero
- regression coverage:
  - Node runtime too old blocks readiness before plugin state is promoted
  - disabled plugin is reported without leaking token values
  - configured account without explicit `@im.wechat` target is channel-ready
    but not send-ready
  - configured account plus explicit iLink target becomes bot-channel
    send-ready in report semantics while still making zero send attempts
  - plugin source summary reads public package/manifest/README contract
  - CLI writes a JSON report with zero control attempts
- current-machine discovery:
  - artifact:
    `logs/runtime/openclaw-weixin-r284/readiness.json`
  - result:
    - `decision=openclaw_cli_node_runtime_too_old`
    - `ok=false`
    - `node_version=22.17.1`
    - `node_min_required=22.19.0`
    - `config_present=true`
    - `plugin_present=false`
    - `plugin_enabled=false`
    - `account_count=0`
    - `bot_channel_ready=false`
    - `send_action_ready=false`
    - `desktop_wechat_control_verified=false`
    - `send_attempts=0`
  - current OpenClaw package evidence:
    `npm view openclaw` reports version `2026.6.10` and engine
    `node >=22.19.0`
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\wechat_openclaw_readiness.py
    tests\test_wechat_openclaw_readiness.py`
    passed
  - `python -m unittest tests.test_wechat_openclaw_readiness`
    ran `6` tests OK
  - `python -m unittest tests.test_wechat_openclaw_readiness
    tests.test_wechat_native_static_discovery
    tests.test_wechat_native_transport_discovery
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `59` tests OK
- next concrete action:
  - if Weixin bot-channel is acceptable, prepare a no-send setup gate for
    upgrading Node to `>=22.19.0`, installing/enabling
    `@tencent-weixin/openclaw-weixin`, running QR login, and then performing a
    real explicit target `@im.wechat` marker send/readback through the bot
    channel
  - keep desktop WeChat File Transfer Assistant background control blocked
    until a separate native desktop helper/protocol proves real send/readback

## 2026-06-29 R285 - OpenClaw-Weixin no-send setup gate

- added a no-send setup gate for the Tencent OpenClaw-Weixin bot-channel route:
  - `src/openwukong/evaluation/wechat_openclaw_setup_gate.py`
  - test:
    `tests/test_wechat_openclaw_setup_gate.py`
- behavior:
  - consumes the R284 readiness shape or runs the readiness probe directly
  - emits structured blockers for Node, OpenClaw CLI, plugin, login account,
    gateway/setup state, and explicit target readiness
  - emits proposed setup steps with `executed=false`, including:
    - verify Node and OpenClaw versions
    - install or activate Node `>=22.19.0` or Node 24
    - install `@tencent-weixin/openclaw-weixin`
    - enable `plugins.entries.openclaw-weixin.enabled`
    - run QR login for `openclaw-weixin`
    - restart the OpenClaw gateway
    - provide an explicit `@im.wechat` target
    - rerun the no-send setup gate before any send probe
  - keeps `install_attempts=0`, `login_attempts=0`,
    `gateway_start_attempts=0`, `send_attempts=0`,
    `native_call_attempts=0`, and all window/keyboard/clipboard counters at
    zero
  - even when all prerequisites are satisfied, the gate can only report
    `ready_for_send_probe=true`; a separate explicit real send/readback probe
    is still required
- current-machine setup gate:
  - artifact:
    `logs/runtime/openclaw-weixin-r285/setup_gate.json`
  - result:
    - `decision=openclaw_weixin_setup_blocked_node_runtime`
    - `ok=false`
    - `ready_for_send_probe=false`
    - blocker:
      Node `22.17.1` is older than required `22.19.0`
    - blocker:
      OpenClaw-Weixin plugin is not installed/configured
    - blocker:
      no logged-in OpenClaw-Weixin account is configured
    - blocker:
      no explicit `@im.wechat` target is provided
    - all setup/login/send/input attempts stayed zero
- validation:
  - `python -m py_compile
    src\openwukong\evaluation\wechat_openclaw_setup_gate.py
    tests\test_wechat_openclaw_setup_gate.py
    src\openwukong\evaluation\wechat_openclaw_readiness.py
    tests\test_wechat_openclaw_readiness.py`
    passed
  - `python -m unittest tests.test_wechat_openclaw_setup_gate`
    ran `6` tests OK
  - `python -m unittest tests.test_wechat_openclaw_setup_gate
    tests.test_wechat_openclaw_readiness
    tests.test_wechat_native_static_discovery
    tests.test_wechat_native_transport_discovery
    tests.test_wechat_native_bridge_real_send_probe
    tests.test_wechat_native_endpoint_publisher
    tests.test_wechat_native_bridge
    tests.test_wechat_native_fabric_binding
    tests.test_computer_operation_readiness_matrix
    tests.test_computer_operation_status_report`
    ran `65` tests OK
  - `git diff --check` reported only existing CRLF normalization warnings
  - secret-pattern scan on the R285 artifact and new setup gate module/test
    found no matches
- reusable learning:
  - added `Setup Plan Masquerades As Executed Capability` to
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
- next concrete action:
  - if pursuing OpenClaw-Weixin, execute the R285 setup plan outside the
    no-send gate: activate Node `>=22.19.0`, install/enable the plugin, scan
    QR login, provide a real explicit `@im.wechat` target, rerun the setup
    gate, then run a separate opt-in marker send/readback
  - keep desktop WeChat File Transfer Assistant background control blocked
    until a separate native desktop helper/protocol proves real send/readback

## 2026-06-29 R286 - OpenClaw-Weixin environment setup and QR login gate

- executed the non-send setup portion of the R285 OpenClaw-Weixin plan:
  - downloaded official Node.js Windows x64 zip for `v24.18.0`
  - verified the zip against official `SHASUMS256.txt`
  - installed the portable runtime at:
    `E:\codeenvir\node-v24.18.0-win-x64`
  - installed OpenClaw under that portable Node prefix:
    `OpenClaw 2026.6.10 (aa69b12)`
  - did not change the system PATH; commands in this run used a process-local
    PATH with the portable Node directory first
- modified local OpenClaw state/config:
  - backed up existing config to:
    `C:\Users\Zhangjinqian\.openclaw\openclaw.json.openwukong-r286-backup-20260629124101`
  - installed `@tencent-weixin/openclaw-weixin`
  - enabled:
    `plugins.entries.openclaw-weixin.enabled=true`
  - set:
    `session.dmScope=per-account-channel-peer`
- current no-send setup-gate artifacts:
  - after plugin install:
    `logs/runtime/openclaw-weixin-r286/setup_gate_after_plugin.json`
  - after QR login timeout:
    `logs/runtime/openclaw-weixin-r286/setup_gate_after_login_timeout.json`
  - login attempt summary:
    `logs/runtime/openclaw-weixin-r286/login_attempt_summary.json`
- current-machine result:
  - Node blocker cleared:
    `node_version=24.18.0`
  - OpenClaw blocker cleared:
    `openclaw_version=2026.6.10`
  - plugin blocker cleared:
    `plugin_present=true`, `plugin_enabled=true`
  - remaining blockers:
    - `openclaw_weixin_account_not_logged_in`
    - `openclaw_weixin_target_user_id_missing`
  - gate decision:
    `openclaw_weixin_setup_blocked_login`
  - `send_attempts=0`
  - `window_input_attempts=0`
  - `keyboard_input_attempts=0`
  - `clipboard_write_attempts=0`
- QR login attempt:
  - command:
    `openclaw channels login --channel openclaw-weixin`
  - the command generated QR codes, but no phone confirmation arrived before
    the QR refresh limit
  - final result:
    `openclaw_weixin_qr_login_not_completed`
  - no QR URL was stored in artifacts or memory
- cleanup/validation:
  - `python -m unittest tests.test_wechat_openclaw_setup_gate
    tests.test_wechat_openclaw_readiness`
    ran `12` tests OK
  - process scan found no lingering Node/OpenClaw/OpenClaw-Weixin process after
    the failed QR login; only the scan command itself matched
  - secret-pattern scan on `logs/runtime/openclaw-weixin-r286` found no QR URL,
    token, cookie, password, or session-id matches
- next concrete action:
  - rerun QR login when the user is ready to scan and confirm immediately
  - after login succeeds, rerun the no-send setup gate with an explicit
    `@im.wechat` target
  - only then restart the OpenClaw gateway and run a separate opt-in marker
    send/readback through the bot channel
  - keep desktop WeChat File Transfer Assistant background control blocked
    until a separate native desktop helper/protocol proves real send/readback

## 2026-06-29 R287 - OpenClaw-Weixin QR retry blocked by missing bot auth

- user clarified that desktop WeChat was already logged in
- important correction:
  - desktop WeChat login is not the same state as OpenClaw-Weixin bot-channel
    authorization
  - OpenClaw-Weixin still needs its own account credential under the
    OpenClaw-Weixin state/account store
  - a visible logged-in desktop WeChat window does not populate that bot
    credential store
- pre-retry no-send gate:
  - artifact:
    `logs/runtime/openclaw-weixin-r287/setup_gate_before_qr_retry.json`
  - result:
    `decision=openclaw_weixin_setup_blocked_login`
  - Node/OpenClaw/plugin remained ready:
    `node_version=24.18.0`, `openclaw_version=2026.6.10`,
    `plugin_present=true`, `plugin_enabled=true`
  - remaining blockers:
    `openclaw_weixin_account_not_logged_in` and
    `openclaw_weixin_target_user_id_missing`
- QR retry:
  - command:
    `openclaw channels login --channel openclaw-weixin`
  - generated QR codes and one-use links, but no phone-side confirmation
    arrived before the refresh limit
  - final result:
    `Channel login failed: Error: 二维码多次失效，连接流程已停止。请稍后再试。`
  - summary artifact:
    `logs/runtime/openclaw-weixin-r287/login_retry_summary.json`
  - no QR URL was stored in artifacts or memory
- post-retry no-send gate:
  - artifact:
    `logs/runtime/openclaw-weixin-r287/setup_gate_after_qr_retry_timeout.json`
  - result:
    `decision=openclaw_weixin_setup_blocked_login`
  - `accounts=[]`
  - `send_attempts=0`
  - `window_input_attempts=0`
  - `keyboard_input_attempts=0`
  - `clipboard_write_attempts=0`
- validation:
  - `python -m unittest tests.test_wechat_openclaw_setup_gate
    tests.test_wechat_openclaw_readiness`
    ran `12` tests OK
  - process scan found no lingering OpenClaw/Node process after the failed QR
    retry; only scan commands matched
  - secret-pattern scan on `logs/runtime/openclaw-weixin-r287` found no QR URL,
    token, cookie, password, or session-id matches
- reusable learning:
  - added `Desktop Login Masquerades As Bot Channel Auth` to
    `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`
- why the previous two QR attempts did not solve it:
  - R286 and R287 both reached the OpenClaw-Weixin auth flow and generated
    QR codes
  - neither run observed phone-side confirmation before QR expiry
  - no account files were created, so the no-send gate correctly stayed at
    `openclaw_weixin_account_not_logged_in`
  - desktop WeChat being logged in cannot satisfy this state because OpenClaw
    needs a separate bot-channel credential
- next concrete action:
  - do not run a third blind QR retry
  - first change the method: verify phone-side scan/confirmation, use the QR
    link directly on the phone if scanning fails, inspect sanitized
    OpenClaw-Weixin auth logs, and check network/proxy reachability to the
    iLink auth endpoint
  - after account credentials exist, rerun the no-send gate with an explicit
    `@im.wechat` target, then restart gateway and run a separate opt-in
    marker send/readback

## 2026-06-29 R288 - WeChat route decision: foreground implementation

- user decision:
  - WeChat is temporarily classified as an explicit foreground implementation
  - do not continue forcing OpenClaw-Weixin as the desktop WeChat control route
- active WeChat capability:
  - preserve the R279 verified foreground desktop WeChat File Transfer
    Assistant send/readback path
  - accepted proof remains:
    `logs/runtime/wechat-real-send-r279/real_send/report.json`
  - marker readback was verified through Python WinRT OCR in R279
  - this capability remains `foreground_required`, not
    `background_execute`
- routes paused or blocked:
  - OpenClaw-Weixin is paused/deprioritized as a desktop-control route because
    it is a separate iLink bot/API channel, not personal desktop WeChat window
    control
  - OpenClaw-Weixin may be revived only as a separate bot-channel messaging
    surface if needed
  - desktop WeChat background-native send/readback remains blocked until a
    concrete native helper, supported SDK, or proven protocol adapter performs
    a real opt-in send/readback with zero window/keyboard/clipboard attempts
- no action taken in R288:
  - no new WeChat send
  - no QR login retry
  - no OpenClaw gateway start
  - no GUI control attempt
- next concrete action:
  - productize the WeChat foreground path with explicit foreground permission,
    exact personal-WeChat target verification, clipboard backup/restore, focus
    restore, Python WinRT OCR readback, and final reporting that marks the
    surface as `foreground_required`
  - keep WeChat out of `background_execute` readiness until a separate native
    desktop proof exists
  - continue background/no-foreground work on stronger connector surfaces such
    as Browser, Codex app-server, Terminal/Git, Office object model, IDE
    bridges, or sandbox GUI/Cua if universal human-like desktop operation is
    still desired

## 2026-09-09 R289 - Computer operation capability audit

- capability conclusion:
  - OpenWuKong is currently a connector-first, controlled desktop copilot,
    not an unrestricted universal computer-use agent
  - explicit evidence matrix: `5` background-execute surfaces, `1`
    background draft surface, `1` foreground-required surface, `1` read-only
    generic desktop surface, and `2` blocked surfaces
  - current default report without injected historical Codex/WeChat evidence:
    `4` background, `1` read-only, and `4` blocked
- verified or ready routes:
  - Codex app-server WebSocket, owned Browser DevTools, IDE extension bridge,
    managed Terminal, and workspace-bound Git
  - Cursor draft injection is background-safe; full Agent submit/readback is
    still blocked
  - WeChat File Transfer Assistant send/readback is verified only through an
    explicit foreground takeover; native background send remains unverified
- current live probe:
  - read-only Windows scan observed `16` windows and `579` UI elements
  - Edge, ChatGPT, and Clash exposed semantic UIA capabilities; Weixin exposed
    structure-only evidence, confirming app-specific route limits
- validation caveat:
  - targeted regression ran `109` tests with `107` passing and `2` failing
  - both failures retain the old expectation that `generic_desktop` is
    `foreground_required`, while current implementation classifies the
    synthetic structural-read surface as `read_only`; no implementation fix
    was made in this audit
- next actions:
  - build Cursor native submit/readback evidence, add an Office object-model
    connector, and pursue a concrete WeChat native adapter before claiming
    broader background control

## 2026-09-09 R290 - Current version pushed as remote baseline

- baseline commit:
  - `afe317c9148f894b8d19ddb8f1f2f2934e74068a`
  - subject: `chore: snapshot current agent control baseline`
  - contains the complete current working-tree code, tests, extension,
    documentation, project snapshot, and prior control evidence
- remote location:
  - `origin/codex/background-safe-control-layer`
  - remote ref verified to point to the same SHA as local `HEAD`
- pre-push checks:
  - tracked and untracked repository scan found no PEM private key, bearer
    token, credential-field, or common provider-token matches
  - targeted regression ran `109` tests with `107` passing and `2` retaining
    the known generic-desktop expectation drift (`read_only` versus the old
    `foreground_required` assertion)
- continuation point:
  - keep `afe317c` as the rollback baseline
  - begin the approved capability-first WeChat implementation plan from the
    current branch after the baseline has been preserved

## 2026-09-09 R291 - Capability-first WeChat implementation checkpoint

- implemented contracts and execution layers:
  - versioned DesktopAction with target, effect, approval, verification,
    typed parameters, and safe audit serialization
  - fresh PID/HWND-bound SurfaceCapabilityProfile with generic UIA
    normalization and zero-control observational guarantees
  - per-action route negotiation across optional native, UIA semantic,
    approved foreground, and blocked paths
  - read-only personal-WeChat observer and exact or explicitly selected target
    resolver; enterprise WeChat is excluded
  - WeChat action dispatcher for lifecycle, navigation, reading, drafting,
    message management, text/emoji, media/file contracts, Moments, settings,
    monitoring, and high-risk confirmation gates
  - optional Windows backend using existing UIA probing and audited foreground
    OCR send probe; it is not registered as a background-native route
  - read-only wechat-basic-operations-demo CLI for live capability reports
- validation:
  - focused WeChat/Desktop regression: 96 tests passed
  - live dry-run observed personal Weixin PID 28976, HWND 133790, title 微信,
    two structural elements, no semantic composer or submit controls,
    unresolved 文件传输助手, and zero control/window-input/keyboard/clipboard
    attempts
  - full repository discovery run remains separately known to contain
    pre-existing failures outside this checkpoint; do not treat it as a clean
    release gate
- remote checkpoint:
  - origin/codex/background-safe-control-layer points to
    8b90e5012c842527544cf83aa93274669880441f
  - rollback baseline remains afe317c9148f894b8d19ddb8f1f2f2934e74068a
- remaining implementation:
  - connect the Windows backend to a live explicit foreground request for one
    user-selected contact, then add real attachment transfer and Moments
    verification only after target and panel locators are proven
  - add action-level readiness reporting and separate File Explorer, browser,
    and Office adapter plans after WeChat evidence is complete
## 2026-09-09 R292 - WeChat implementation and verification checkpoint

- completed implementation slice:
  - versioned desktop action and evidence-bound surface capability contracts
  - capability-first planner that preserves foreground versus background mode
  - personal-WeChat observer, exact target resolver, lifecycle/navigation/read/
    draft dispatcher, text/emoji/media/file contracts, Moments contracts,
    receive monitor, high-risk confirmation gate, and controlled dry-run CLI
  - optional Windows backend that combines UIA probing with the audited
    foreground OCR send probe; no live native background backend is claimed
- validation:
  - focused WeChat/Desktop regression ran 98 tests and passed
  - live dry-run bound personal Weixin PID 28976, HWND 133790, title 微信; it
    exposed two structural elements, no semantic composer or submit controls,
    unresolved 文件传输助手, and zero control, keyboard, mouse, clipboard, or
    window-input attempts
  - full repository discovery ran 1020 tests with 11 failures and 1 error;
    failures include the known generic-desktop expectation drift and other
    pre-existing baseline tests outside this implementation slice
- remote state:
  - origin/codex/background-safe-control-layer points to fdb1a2a
  - rollback baseline remains afe317c
- next action:
  - obtain an explicit user-selected contact and message only when a real
    foreground send verification is authorized; then add attachment and
    Moments panel locators, followed by readiness-matrix integration
