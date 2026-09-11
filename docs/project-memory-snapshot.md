# OpenWukong Project Memory Snapshot

Updated: 2026-09-09

## Current Decision

OpenWukong is a developer-workstation AIOS Copilot. The current control strategy is connector-first: use deterministic CLI, native bridge, DevTools, app-server, or extension transports before UIA or foreground desktop input. As of R288, WeChat is temporarily classified as an explicit foreground implementation: the validated path is desktop WeChat File Transfer Assistant foreground takeover with target verification and Python WinRT OCR readback, and it must not be counted as background-native or no-foreground execution. Tencent OpenClaw-Weixin is paused as a desktop-control route because it is a separate iLink bot/API channel, not personal desktop WeChat control; it can be revived only as a separate bot-channel messaging surface if needed.

R290 preserved the complete current working-tree version as remote baseline commit `afe317c9148f894b8d19ddb8f1f2f2934e74068a` on `origin/codex/background-safe-control-layer`. The approved next implementation direction is capability-first WeChat desktop control: one shared desktop action and verification kernel, with native bridges as optional accelerators and UIA or explicitly approved foreground fallback paths.

## Runtime / Deployment State

- Local Windows workspace: `E:\ideaProjects\agent\openwukong`.
- Python virtual environment is used through `.venv\Scripts\python.exe`.
- Codex app operation now has a verified owned loopback app-server path using `codex app-server --listen ws://127.0.0.1:<port>`.
- The owned Codex app-server path does not use keyboard, mouse, clipboard, UIA set-value, or foreground desktop control.
- R290 baseline push verified that local `HEAD` and remote `origin/codex/background-safe-control-layer` both resolve to `afe317c9148f894b8d19ddb8f1f2f2934e74068a`.
- R291 implementation checkpoint:
  - capability-first desktop action model, fresh surface profiles, route
    negotiation, personal-WeChat observer/resolver, WeChat action dispatcher,
    monitoring, side-effect gates, Moments contracts, and optional Windows
    UIA/foreground backend are implemented on top of the preserved baseline
  - focused WeChat/Desktop regression passed 96 tests
  - current live dry-run bound personal Weixin PID 28976, HWND 133790, title 微信,
    found only two structural elements, no semantic composer or submit
    controls, unresolved 文件传输助手, and zero control/input attempts
  - remote implementation checkpoint is
    8b90e5012c842527544cf83aa93274669880441f; rollback baseline remains
    afe317c9148f894b8d19ddb8f1f2f2934e74068a

## Verified Facts

- R262 accepted the first strict Codex app-server send/readback proof with foreground focus stable.
- R264 initially failed in the integrated runner because WebSocket live notifications did not deliver `turn/completed`, but the real session JSONL contained assistant `response_item` and `event_msg.task_complete.last_agent_message`.
- R265 verified the fixed integrated path:
  - artifact: `logs/runtime/codex-app-server-integrated-r265/integrated_real_send_r265.json`
  - decision: `codex_app_server_turn_start_verified`
  - marker: `OPENWUKONG_REAL_SEND_R265_20260628T133942`
  - Codex thread start verified: true
  - Codex turn start verified: true
  - strict assistant/session readback verified: true
  - transport matrix `send_ready`: true
  - `control_attempts=0`
  - `window_input_attempts=0`
  - `foreground_no_steal_verified=true`
- R266 promoted that proof into the Computer Operation Readiness Matrix:
  - artifact: `logs/runtime/computer-operation-status-r266/computer_operation_readiness_r266.json`
  - Codex `readiness_level`: `background_execute`
  - Codex `operation_status`: `background_execute_verified`
  - Codex `verified`: true
  - summary `background_execute_verified_surfaces`: `["codex"]`
  - matrix `control_attempts=0`
- R267 verified owned Browser DevTools as the second background-execute surface:
  - browser artifact: `logs/runtime/owned-browser-safe-operation-demo-r267/owned_browser_safe_operation_demo.json`
  - matrix artifact: `logs/runtime/computer-operation-status-r267/computer_operation_readiness_r267.json`
  - Browser `operation_status`: `background_execute_verified`
  - Browser `verified`: true
  - combined summary `background_execute_verified_surfaces`: `["codex", "browser"]`
  - Browser demo used isolated headless Chrome, loopback DevTools, DOM write/submit/readback, manifest stop, and profile cleanup
  - `desktop_control_attempts=0`
  - `window_input_attempts=0`
  - residual process check found no R267 Chrome/helper process; only the checking PowerShell command matched its own command line
- R268 promoted owned IDE live bridge evidence into the Computer Operation Readiness Matrix:
  - matrix artifact: `logs/runtime/computer-operation-status-r268/computer_operation_readiness_r268.json`
  - strict IDE artifact accepted: `logs/runtime/owned-ide-live-bridge-demo-r246/owned_ide_live_bridge_demo.json`
  - summary `background_execute_verified_surfaces`: `["codex", "browser", "ide"]`
  - verified background execute count: `3`
  - matrix `control_attempts=0`
- Cursor attach-only correction after an isolated-profile mistake:
  - isolated Cursor launch with `--user-data-dir` created a login window and must not be used for the already logged-in user workflow
  - stale isolated bridge registry file `4c1cfd516bb01beeb08af937.json` was removed
  - remaining correct bridge registry is `08c4d25ccf4c4102de5eed67.json`
  - correct live Cursor bridge is `http://127.0.0.1:8787`, bound to `E:\ideaProjects\agent\PaoPaoHeZi`
  - attach-only dry run artifact: `logs/runtime/cursor-attach-r270-correct-bridge/cursor_attach_r270_correct_bridge.json`
  - R270 did not launch Cursor, did not use window input, and kept foreground stable, but `/v1/ide/cursor/draft-hook` timed out after 8 seconds on the live `PaoPaoHeZi` session
- R271 fixed and validated the live logged-in Cursor route:
  - added `live_cursor_attach_draft_probe` for attach-only dry-runs against the existing logged-in bridge.
  - `/v1/ide/cursor/draft-hook` now rejects unsafe safety profiles before reading the VS Code command registry.
  - Cursor draft-hook command discovery and isolated draft commands are bounded by `openwukong.bridge.cursorDraftHookCommandAwaitTimeoutMs`.
  - live attach dry-run no longer reads `composer.getComposerHandleById`; handle reads remain isolated-profile-only.
  - added `openwukong.bridge.autoStartRequiresWorkspace=true` by default so empty Cursor windows do not publish bridge endpoints without workspace identity.
  - final correct bridge: `http://127.0.0.1:8787`, registry `10fe1fa3e9302e323b861bc8.json`, workspace `E:\ideaProjects\agent\PaoPaoHeZi`.
  - stale empty-workspace bridge on `8789` was stopped, its registry was removed, and it did not respawn after the workspace-required autoStart guard was synced.
  - attach-only artifact: `logs/runtime/cursor-attach-r271/cursor_attach_r271_final.json`
  - attach result: `decision=cursor_attach_bridge_dry_run_ready`, `ok=true`, `launch_attempts=0`, `window_input_attempts=0`, `foreground_changed=false`
  - real Cursor Agent dispatch artifact: `logs/runtime/cursor-attach-r271/cursor_agent_send_r271_final.json`
  - dispatch result: `decision=cursor_agent_send_dispatched`, `ok=true`, `command_id=composer.sendToAgent`, `dispatch_status=resolved`, `chat_elapsed_ms=30.519`, `window_input_attempts=0`, `keyboard_input_attempts=0`, `clipboard_write_attempts=0`, `foreground_changed=false`
- R272 tightened Cursor transcript acceptance:
  - `cursor_transcript_readback` is now role-aware and defaults to `required_response_role=assistant`.
  - required markers in Cursor user bubbles, request/prompt blobs, `composerData`, or ambiguous `agentKv:blob` rows no longer count as assistant completion.
  - historical R75 was reclassified from broad marker accepted to `cursor_transcript_readback_non_response_marker_only`: the marker was found in an `agentKv:blob` prompt and `bubbleId... type=1` user text/richText, not in an assistant response.
  - real R272 send artifact: `logs/runtime/cursor-transcript-r272/cursor_agent_strict_readback_r272.json`
  - R272 marker: `OPENWUKONG_CURSOR_AGENT_STRICT_R272_20260628T144055`
  - R272 dispatch: `command_id=composer.sendToAgent`, `dispatch_status=resolved`
  - R272 strict result: `decision=cursor_agent_assistant_transcript_readback_pending`; after 22 polls / 120 seconds, `required_markers_found=[]`, `required_markers_found_anywhere=[]`, and `response_marker_locations=[]`.
  - R272 used the existing logged-in `8787` bridge only; no Cursor launch, keyboard input, mouse input, or clipboard write was used.
- R273/R274 split Cursor draft proof from Cursor Agent completion:
  - `live_cursor_attach_draft_write_probe` can write a new Cursor draft through `composer.createNew` with `skipShowAndFocus` and `skipSelect`.
  - accepted draft artifact: `logs/runtime/cursor-draft-r273/live_draft_validation.json`
  - R273 draft result: `decision=cursor_draft_hook_validated`, `readback_verified=true`, `draft_write_attempts=1`, `window_input_attempts=0`, `foreground_changed=false`, marker found in local Cursor storage on user/draft-side state.
  - R274 added `/v1/ide/cursor/glass-agent-query` and `live_cursor_glass_agent_query_probe` to test Cursor's `glass.newAgentWithQuery` without using the generic command allowlist.
  - R274 dry-run artifact: `logs/runtime/cursor-glass-r274/glass_query_dry_run_after_reload.json`; command selected: `glass.newAgentWithQuery`.
  - R274 real dispatch artifact: `logs/runtime/cursor-glass-r274/glass_agent_live_validation_r274b.json`
  - R274 result: `decision=cursor_glass_agent_query_readback_pending`, `dispatch_status=resolved`, `foreground_changed=false`, `system_dialog_detected=false`, `window_input_attempts=0`, `keyboard_input_attempts=0`, `clipboard_write_attempts=0`, but neither user nor assistant local transcript readback found `OPENWUKONG_CURSOR_GLASS_AGENT_R274B_20260628T171413`.
  - full SQLite marker searches also found zero matches:
    `logs/runtime/cursor-glass-r274/global_marker_search_r274b.json` and
    `logs/runtime/cursor-glass-r274/workspace_marker_search_r274b.json`.
  - Cursor bundle inspection showed `glass.newAgentWithQuery` emits `setPendingPromptRequested` plus `newAgentRequested`; it is not the internal `submitInitialLocalAgentMessage` / `submitChatMaybeAbortCurrent` path.
- Focused validation passed: `python -m unittest tests.test_codex_app_server_probe tests.test_codex_app_server_bridge tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss` ran 107 tests OK.
- Wider control validation passed: `python -m unittest tests.test_codex_app_server_probe tests.test_codex_app_server_bridge tests.test_agent_native_connector_probe tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss tests.test_major_real_no_loss tests.test_objective_readiness_matrix tests.test_computer_operation_readiness_matrix` ran 185 tests OK.
- R266 matrix validation passed: `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss` ran 49 tests OK.
- R267 browser/matrix validation passed: `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_owned_browser_safe_operation_demo tests.test_browser_devtools_action tests.test_browser_devtools_health tests.test_browser_devtools_dom_probe tests.test_control_fabric_browser_workflow tests.test_agent_app_transport_matrix` ran 43 tests OK.
- R268/R270 Cursor and matrix validation passed: `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_owned_ide_live_bridge_demo tests.test_owned_ide_safe_operation_demo tests.test_owned_browser_safe_operation_demo tests.test_ide_bridge_registry tests.test_cursor_attach_bridge_validation tests.test_cursor_isolated_draft_hook_runner tests.test_cursor_draft_hook_probe tests.test_cursor_draft_hook_validation` ran 46 tests OK.
- R272 strict Cursor transcript validation passed:
  - `python -m unittest tests.test_cursor_transcript_readback` ran 6 tests OK.
  - `python -m unittest tests.test_cursor_transcript_readback tests.test_agent_app_real_no_loss tests.test_ide_extension_connector tests.test_ide_bridge_capture tests.test_ide_bridge_contract_probe` ran 75 tests OK.
  - reusable learning was added to `C:/Users/Zhangjinqian/.codex/skills/ide-extension-bounded-await-debug/SKILL.md`: dispatch `resolved` is not assistant completion, and marker acceptance must require assistant/response-side evidence.
- R274 Cursor Glass validation passed locally:
  - `node --check extensions\openwukong-vscode\src\extension.js` passed.
  - `python -m py_compile` passed for the new Cursor Glass probe/validation modules and touched bridge files.
  - `python -m unittest tests.test_cursor_glass_agent_query_probe tests.test_cursor_glass_agent_query_validation tests.test_ide_extension_scaffold` ran 12 tests OK.
  - after marker-readback correction, `python -m unittest tests.test_cursor_glass_agent_query_validation tests.test_cursor_glass_agent_query_probe` ran 8 tests OK.
- R275 split Cursor Agent readiness from generic IDE readiness in the Computer Operation Readiness Matrix:
  - Cursor now has its own `cursor` surface with `display_name=Cursor Agent`.
  - verified Cursor capabilities are represented separately from full background execution:
    `background_draft_injection` from R273 draft-hook evidence and
    `foreground_uia_clipboard_draft_fallback` from the 2026-05-19 Application Control Bus probe.
  - Cursor remains blocked for full background Agent send because
    `cursor_submit_native_service_hook` and `assistant_response_marker_readback`
    are still missing.
  - generated artifact:
    `logs/runtime/computer-operation-status-r275/computer_operation_readiness_r275.json`
  - status artifact:
    `logs/runtime/computer-operation-status-r275/computer_operation_status_r275.json`
  - markdown artifact:
    `logs/runtime/computer-operation-status-r275/computer_operation_status_r275.md`
  - real artifact summary:
    Cursor is in `background_draft_surfaces=["cursor"]`, not in
    `background_execute_surfaces` or `background_execute_verified_surfaces`;
    Cursor `operation_status=cursor_submit_readback_blocked`;
    Cursor `can_write_without_focus=true` and
    `can_execute_without_focus=false`.
- R275 validation passed:
  - `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 13 tests OK.
  - `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss` ran 57 tests OK.
  - `python -m py_compile src\openwukong\evaluation\computer_operation_readiness_matrix.py src\openwukong\evaluation\computer_operation_status_report.py` passed.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R276 split WeChat readiness into foreground, fixture, route, and real native-send layers:
  - historical live WeChat File Transfer Assistant send is preserved as `foreground_file_transfer_send` only.
  - owned WeChat native bridge fixture smoke is preserved as `native_bridge_fixture_send_verified` partial capability only.
  - WeChat no longer promotes to `background_execute` from bridge URL plus background screenshot evidence alone; a real `wechat-native-bridge-send` report with native call, zero window/keyboard/clipboard attempts, foreground stability, target match, and marker readback is required for `background_execute_verified`.
  - generated artifact: `logs/runtime/computer-operation-status-r276/computer_operation_readiness_r276.json`.
  - status artifact: `logs/runtime/computer-operation-status-r276/computer_operation_status_r276.json`.
  - markdown artifact: `logs/runtime/computer-operation-status-r276/computer_operation_status_r276.md`.
  - R276 artifact summary: `foreground_send_surfaces=["wechat"]`; WeChat is not in `background_execute_surfaces`; WeChat `readiness_level=foreground_required`; WeChat `blocking_reason=wechat_native_send_readback_not_verified`.
- R276 validation passed:
  - `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 17 tests OK.
  - `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_wechat_native_endpoint_publisher` ran 78 tests OK.
  - `python -m py_compile src\openwukong\evaluation\computer_operation_readiness_matrix.py src\openwukong\evaluation\computer_operation_status_report.py src\openwukong\control\wechat_native_bridge.py src\openwukong\connectors\wechat_native_bridge.py` passed.
- R277 performed a real explicit opt-in WeChat File Transfer Assistant foreground send on the current Windows machine:
  - personal WeChat was resolved from the running app path `E:\software\Weixin\Weixin.exe`; Enterprise WeChat was observed separately but not selected for sending.
  - system-dialog preflight artifact: `logs/runtime/wechat-real-send-r277/preflight_system_dialog.json`; result `system_dialog_clear`.
  - read-only locator artifact: `logs/runtime/wechat-real-send-r277/wechat_locator_before_send.json`; personal WeChat window `微信` was selected for the send probe.
  - foreground takeover request artifact: `logs/runtime/wechat-real-send-r277/foreground_takeover_request.json`; approved transport `foreground-keyboard-clipboard`.
  - prepare/no-send artifact: `logs/runtime/wechat-real-send-r277/prepare_no_send/report.json`; it intentionally stopped before sending with `blocked_target_not_verified`, and the captured target screenshot showed `文件传输助手`.
  - real send artifact: `logs/runtime/wechat-real-send-r277/real_send/report.json`; marker `OPENWUKONG_WECHAT_R277_REAL_SEND_20260628T174958`, `status=sent`, `send_attempts=1`, `keyboard_input_attempts=6`, `clipboard_write_attempts=2`, `clipboard_restore_attempts=1`, `foreground_restore_attempts=1`, `post_send_screenshot_bound=true`.
  - visual confirmation screenshot: `logs/runtime/wechat-real-send-r277/real_send/post_send_verify_chat_crop.png`; it shows the marker in the `文件传输助手` conversation.
  - automatic post-send marker verifier remains unavailable in this path: `post_send_verified=false`, `post_send_verification.method=not_available`.
- R277 regenerated computer-operation status artifacts:
  - WeChat-focused readiness: `logs/runtime/computer-operation-status-r277/computer_operation_readiness_r277.json`.
  - WeChat-focused status: `logs/runtime/computer-operation-status-r277/computer_operation_status_r277.json` and `.md`.
  - full evidence readiness: `logs/runtime/computer-operation-status-r277/computer_operation_readiness_r277_full_evidence.json`.
  - full evidence status: `logs/runtime/computer-operation-status-r277/computer_operation_status_r277_full_evidence.json` and `.md`.
  - full evidence summary: `background_execute_surfaces=["codex","browser","terminal","git","ide"]`, `background_execute_verified_surfaces=["codex","browser","ide"]`, `background_draft_surfaces=["cursor"]`, `foreground_send_surfaces=["wechat"]`, `verified_background_execute_count=3`, `verified_background_draft_count=1`.
- R277 fixed a status-reporting gap:
  - `computer_operation_status_report` now accepts `--codex-app-server-ws-url` and `--codex-app-server-turn-start-report`.
  - status summary now includes `verified_background_execute_count`.
  - this prevents full status reports from incorrectly showing Codex as blocked when a strict Codex app-server turn report is supplied.
- R277 reusable learning was added to `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`: wrapper/status reports must not silently drop lower-level readiness evidence, because that creates a false capability regression.
- R277 validation passed:
  - `python -m unittest tests.test_computer_operation_status_report tests.test_computer_operation_readiness_matrix` ran 18 tests OK.
  - `python -m unittest tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_objective_readiness_matrix tests.test_agent_app_transport_matrix tests.test_agent_app_real_no_loss tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_wechat_native_endpoint_publisher` ran 79 tests OK.
  - `python -m py_compile src\openwukong\evaluation\computer_operation_status_report.py tests\test_computer_operation_status_report.py` passed.
- Static validation passed:
  - `python -m py_compile` on the touched Codex app-server and transport modules.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R278 replaced the WeChat post-send OCR readback backend before rerunning any fresh send:
  - root cause of the Windows Defender alert was the exploratory OCR backend that launched PowerShell with `-EncodedCommand` and `-ExecutionPolicy Bypass`; that launcher shape is no longer used by the WeChat OCR/readback path.
  - `src/openwukong/evaluation/wechat_send_probe.py` now uses Python WinRT bindings to call Windows OCR directly through `Windows.Media.Ocr`, `Windows.Graphics.Imaging`, and `Windows.Storage.Streams`.
  - Windows-only OCR dependencies were declared in `pyproject.toml` and `requirements.txt`, and installed in `.venv` for the current machine.
  - replay artifact: `logs/runtime/wechat-readback-r278/post_send_python_winrt_ocr_replay_r277.json`.
  - replay source screenshot: `logs/runtime/wechat-real-send-r277/real_send/post_send_verify.png`.
  - replay result: `verified=true`, `ocr_method=python-winrt-windows-media-ocr`, `normalized_marker_matched=true`, `fresh_send_attempted=false`, `powershell_encoded_command_used=false`.
  - regression added: `tests/test_wechat_send_probe.py` asserts the WeChat OCR/readback module does not contain `-EncodedCommand`, `ExecutionPolicy`, or the removed PowerShell OCR helper name.
  - reusable learning added to `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`: encoded PowerShell OCR/readback launchers are a Defender-risk pattern and must be replaced with native API backends such as Python WinRT.
- R278 validation passed:
  - `python -m py_compile src\openwukong\evaluation\wechat_send_probe.py tests\test_wechat_send_probe.py` passed.
  - `python -m unittest tests.test_wechat_send_probe` ran 14 tests OK.
  - `pip show winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams` confirmed version `3.2.1` installed in `.venv`.
- R279 performed a fresh explicit opt-in WeChat File Transfer Assistant foreground send with integrated Python WinRT OCR readback:
  - preflight artifact: `logs/runtime/wechat-real-send-r279/preflight_system_dialog.json`; result `system_dialog_clear`.
  - narrow security-window scan artifact: `logs/runtime/wechat-real-send-r279/security_window_scan.json`; result `security_window_detected=false`.
  - read-only WeChat locator artifact: `logs/runtime/wechat-real-send-r279/wechat_locator_before_send.json`; personal WeChat `Weixin.exe` window `微信` and Enterprise WeChat `WXWork.exe` window `企业微信` were both observed, and the send probe selected personal WeChat by exact process/class.
  - foreground takeover request artifact: `logs/runtime/wechat-real-send-r279/foreground_takeover_request.json`.
  - real send artifact: `logs/runtime/wechat-real-send-r279/real_send/report.json`; marker `OPENWUKONG_WECHAT_R279_REAL_SEND_20260628T190000`, `status=sent`, `send_attempts=1`, `keyboard_input_attempts=6`, `clipboard_write_attempts=2`, `clipboard_restore_attempts=1`, `foreground_restore_attempts=1`, `post_send_screenshot_bound=true`.
  - automated readback result: `post_send_verified=true`, `post_send_verification.method=windows-media-ocr-readback`, `ocr_method=python-winrt-windows-media-ocr`, `normalized_marker_matched=true`.
  - status artifact: `logs/runtime/computer-operation-status-r279/computer_operation_status_r279.json` and `.md`.
  - R279 status keeps WeChat as `readiness_level=foreground_required`; it adds foreground evidence fields `wechat_foreground_post_send_verified=true`, `wechat_foreground_post_send_ocr_method=python-winrt-windows-media-ocr`, and verified capability `foreground_post_send_marker_readback`.
  - R279 did not prove background-native WeChat control; blocker remains `wechat_native_send_readback_not_verified`.
- R279 validation passed:
  - `python -m py_compile src\openwukong\evaluation\computer_operation_readiness_matrix.py tests\test_computer_operation_readiness_matrix.py` passed.
  - `python -m unittest tests.test_computer_operation_readiness_matrix` ran 13 tests OK.
  - final focused validation `python -m unittest tests.test_wechat_send_probe tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 32 tests OK.
  - final `python -m py_compile` on `wechat_send_probe.py`, `computer_operation_readiness_matrix.py`, `computer_operation_status_report.py`, and their focused tests passed.
  - final `git diff --check` reported only existing CRLF normalization warnings.
- R280 added an explicit WeChat native bridge real-send probe:
  - new module: `src/openwukong/evaluation/wechat_native_bridge_real_send_probe.py`.
  - new tests: `tests/test_wechat_native_bridge_real_send_probe.py`.
  - the probe discovers localhost WeChat native bridge URLs from explicit args, env/default registry paths, performs a dry-run first, requires `--allow-send` before calling `/v1/wechat/send`, never falls back to foreground keyboard/mouse/clipboard, and emits a nested `send_report` consumable by the readiness matrix.
  - fixture validation proves the wrapper report can promote WeChat to `background_execute_verified` only when the nested `wechat-native-bridge-send` report has one native call, one send, marker readback, foreground stability, and zero window/keyboard/clipboard attempts.
  - current-machine dry-run artifact: `logs/runtime/wechat-native-real-r280/dry_run.json`; result `decision=wechat_native_bridge_url_missing`, `discovered_urls=[]`, `send_attempts=0`, `native_call_attempts=0`, `window_input_attempts=0`.
  - current-machine read-only UIA artifact: `logs/runtime/wechat-native-real-r280/accessibility_probe.json`; personal WeChat remained `structure_only` with `input_candidate_count=0`, `semantic_input_count=0`, and no safe UIA write surface.
  - reusable learning added to `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`: read-only bridge evidence must not masquerade as native send; discovery, dry-run, and real send/readback must remain separate.
- R280 validation passed:
  - `python -m unittest tests.test_wechat_native_bridge_real_send_probe` ran 4 tests OK.
  - `python -m unittest tests.test_wechat_native_bridge tests.test_wechat_native_bridge_fixture_smoke tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_fabric_binding tests.test_wechat_native_bridge_real_send_probe tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 41 tests OK.
  - `python -m py_compile src\openwukong\evaluation\wechat_native_bridge_real_send_probe.py tests\test_wechat_native_bridge_real_send_probe.py src\openwukong\evaluation\wechat_native_bridge_fixture_smoke.py src\openwukong\control\wechat_native_bridge.py` passed.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R281 added an opt-in WeChat external-command native bridge backend boundary:
  - implementation: `src/openwukong/control/wechat_native_endpoint_publisher.py`.
  - regression tests: `tests/test_wechat_native_endpoint_publisher.py`.
  - backend name: `external-command`.
  - CLI config: `--external-command-json '["path-to-command", "arg1"]'`.
  - env fallback: `OPENWUKONG_WECHAT_NATIVE_EXTERNAL_COMMAND_JSON`.
  - the backend delegates `/v1/wechat/capabilities` and `/v1/wechat/send` to one explicit local command over JSON stdin/stdout using `subprocess.run(..., shell=False)`.
  - it does not use keyboard, mouse, clipboard, window input, SendInput, UIA mutation, or foreground focus takeover.
  - it remains blocked when no command is configured.
  - it blocks external command responses that omit explicit background-safety declarations or send-result zero-input/focus-stability declarations.
  - fixture validation proves a configured command can complete the existing native bridge contract with one native call, one send, marker readback, and zero window/keyboard/clipboard attempts.
  - current-machine conclusion: this is a safe adapter boundary, not live WeChat background-send proof; a concrete real WeChat external command/SDK backend is still required.
- R281 validation passed:
  - `python -m py_compile src\openwukong\control\wechat_native_endpoint_publisher.py tests\test_wechat_native_endpoint_publisher.py` passed.
  - `python -m unittest tests.test_wechat_native_endpoint_publisher` ran 15 tests OK.
  - `python -m unittest tests.test_wechat_native_bridge tests.test_wechat_native_bridge_fixture_smoke tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_fabric_binding tests.test_wechat_native_bridge_real_send_probe tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 46 tests OK.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R282 added a read-only WeChat native transport discovery probe:
  - implementation: `src/openwukong/evaluation/wechat_native_transport_discovery.py`.
  - regression tests: `tests/test_wechat_native_transport_discovery.py`.
  - the probe uses `psutil` and Python networking APIs to enumerate personal WeChat processes, loopback listening ports, HTTP/CDP fingerprints, optional `/v1/wechat/capabilities` bridge-contract readiness, and redacted named-pipe candidates.
  - it never calls `/v1/wechat/send` and keeps native/send/window/keyboard/clipboard attempts at zero.
  - current-machine artifact: `logs/runtime/wechat-native-transport-r282/discovery.json`.
  - current-machine result: `decision=wechat_loopback_ports_unknown_protocol`, `ok=false`.
  - personal WeChat loopback ports observed: `14013`, `14016`, `14019`, `14022`, `14023`.
  - all observed personal WeChat loopback ports were classified as `tcp-unknown`, not HTTP, not Chrome DevTools Protocol, and not the OpenWukong `/v1/wechat/capabilities` bridge contract.
  - conclusion: these ports are useful native-transport evidence, but they are not yet a send-capable backend and must not promote WeChat readiness.
- R282 validation passed:
  - `python -m py_compile src\openwukong\evaluation\wechat_native_transport_discovery.py tests\test_wechat_native_transport_discovery.py` passed.
  - `python -m unittest tests.test_wechat_native_transport_discovery` ran 4 tests OK.
  - `python -m unittest tests.test_wechat_native_transport_discovery tests.test_wechat_native_bridge_real_send_probe tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 48 tests OK.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R283 added a read-only WeChat native static discovery probe:
  - implementation: `src/openwukong/evaluation/wechat_native_static_discovery.py`.
  - regression tests: `tests/test_wechat_native_static_discovery.py`.
  - the probe discovers Weixin install directories, scans bounded `.dll`/`.exe` candidates, parses PE export tables, counts static IPC/send/helper keyword signals, and reads only explicit OpenWukong helper manifests if present.
  - it never launches WeChat, attaches to a process, calls internal IPC, sends a message, uses UIA mutation, or touches keyboard/mouse/clipboard/focus.
  - current-machine artifact: `logs/runtime/wechat-native-static-r283/discovery.json`.
  - current-machine result: `decision=weixin_static_surfaces_found_without_send_contract`, `ok=false`.
  - scanned files: `24`.
  - helper manifests: `0`.
  - static signal summary included `name:ilink=3`, `name:mojo=1`, `keyword:ilink=9`, `keyword:mojo=6`, `keyword:ipc=13`, `keyword:pipe=20`, `keyword:localhost=6`, `keyword:127.0.0.1=1`, `export:send-like=7`, and `export:conversation-like=7`.
  - counters stayed zero: `send_attempts=0`, `native_call_attempts=0`, `window_input_attempts=0`, `keyboard_input_attempts=0`, and `clipboard_write_attempts=0`.
  - conclusion: current Weixin binaries expose useful ilink/mojo/IPC clues, but no OpenWukong-consumable helper contract or proven send protocol is available yet.
- R283 validation passed:
  - `python -m py_compile src\openwukong\evaluation\wechat_native_static_discovery.py tests\test_wechat_native_static_discovery.py` passed.
  - `python -m unittest tests.test_wechat_native_static_discovery` ran 5 tests OK.
  - `python -m unittest tests.test_wechat_native_static_discovery tests.test_wechat_native_transport_discovery tests.test_wechat_native_bridge_real_send_probe tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 53 tests OK.
  - final `python -m py_compile` on the new static discovery module/test and adjacent WeChat native modules passed.
  - `git diff --check` reported only existing CRLF normalization warnings.
- R284 investigated Tencent OpenClaw-Weixin as a separate Weixin bot-channel path:
  - source inspected from `https://github.com/Tencent/openclaw-weixin`.
  - local source snapshot: `logs/runtime/openclaw-weixin-r284/openclaw-weixin`.
  - package: `@tencent-weixin/openclaw-weixin`.
  - source package version: `2.4.6`.
  - channel id: `openclaw-weixin`.
  - protocol evidence: iLink bot HTTP JSON APIs including `getupdates`, `sendmessage`, `getuploadurl`, `getconfig`, and `sendtyping`.
  - important boundary: this is a background Weixin bot-channel candidate, not personal desktop WeChat control and not File Transfer Assistant proof.
- R284 added a read-only OpenClaw-Weixin readiness probe:
  - implementation: `src/openwukong/evaluation/wechat_openclaw_readiness.py`.
  - regression tests: `tests/test_wechat_openclaw_readiness.py`.
  - the probe checks `openclaw` CLI and Node version, reads `~/.openclaw/openclaw.json`, redacts account/token/user metadata, optionally summarizes public plugin source metadata, and keeps all control/send/input counters at zero.
  - it does not start the OpenClaw gateway, perform QR login, call `sendmessage`, or touch desktop focus/keyboard/mouse/clipboard.
  - current-machine artifact: `logs/runtime/openclaw-weixin-r284/readiness.json`.
  - current-machine result: `decision=openclaw_cli_node_runtime_too_old`, `ok=false`.
  - local runtime facts: `node_version=22.17.1`, `node_min_required=22.19.0`, `config_present=true`, `plugin_present=false`, `plugin_enabled=false`, `account_count=0`, `bot_channel_ready=false`, `send_action_ready=false`, `desktop_wechat_control_verified=false`, and `send_attempts=0`.
  - `npm view openclaw` reported OpenClaw version `2026.6.10` and engine requirement `node >=22.19.0`.
- R284 validation passed:
  - `python -m py_compile src\openwukong\evaluation\wechat_openclaw_readiness.py tests\test_wechat_openclaw_readiness.py` passed.
  - `python -m unittest tests.test_wechat_openclaw_readiness` ran 6 tests OK.
  - `python -m unittest tests.test_wechat_openclaw_readiness tests.test_wechat_native_static_discovery tests.test_wechat_native_transport_discovery tests.test_wechat_native_bridge_real_send_probe tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 59 tests OK.
- R285 added a no-send OpenClaw-Weixin setup gate:
  - implementation: `src/openwukong/evaluation/wechat_openclaw_setup_gate.py`.
  - regression tests: `tests/test_wechat_openclaw_setup_gate.py`.
  - the gate consumes OpenClaw-Weixin readiness, emits structured blockers and proposed setup steps, and keeps `install_attempts=0`, `login_attempts=0`, `gateway_start_attempts=0`, `send_attempts=0`, and all desktop/input counters at zero.
  - it separates three states: proposed setup steps, observed readiness, and a later explicit real send/readback probe.
  - current-machine artifact: `logs/runtime/openclaw-weixin-r285/setup_gate.json`.
  - current-machine result: `decision=openclaw_weixin_setup_blocked_node_runtime`, `ok=false`, `ready_for_send_probe=false`.
  - observed blockers: Node `22.17.1 < 22.19.0`, OpenClaw-Weixin plugin not configured, no logged-in OpenClaw-Weixin account, and no explicit `@im.wechat` target.
  - proposed steps include installing or activating Node `>=22.19.0` or Node 24, installing `@tencent-weixin/openclaw-weixin`, enabling the plugin, QR login, gateway restart, target provision, and rerunning the no-send gate; none of those steps was executed by R285.
- R285 validation passed:
  - `python -m py_compile src\openwukong\evaluation\wechat_openclaw_setup_gate.py tests\test_wechat_openclaw_setup_gate.py src\openwukong\evaluation\wechat_openclaw_readiness.py tests\test_wechat_openclaw_readiness.py` passed.
  - `python -m unittest tests.test_wechat_openclaw_setup_gate` ran 6 tests OK.
  - `python -m unittest tests.test_wechat_openclaw_setup_gate tests.test_wechat_openclaw_readiness tests.test_wechat_native_static_discovery tests.test_wechat_native_transport_discovery tests.test_wechat_native_bridge_real_send_probe tests.test_wechat_native_endpoint_publisher tests.test_wechat_native_bridge tests.test_wechat_native_fabric_binding tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report` ran 65 tests OK.
  - `git diff --check` reported only existing CRLF normalization warnings.
  - secret-pattern scan on the R285 artifact and new setup-gate module/test found no matches.
- R286 executed the non-send OpenClaw-Weixin environment setup:
  - installed isolated portable Node.js `v24.18.0` under `E:\codeenvir\node-v24.18.0-win-x64` after downloading the official Windows x64 zip and verifying it against the official `SHASUMS256.txt`.
  - installed OpenClaw `2026.6.10` under that portable Node prefix without changing the system PATH.
  - backed up the existing OpenClaw config to `C:\Users\Zhangjinqian\.openclaw\openclaw.json.openwukong-r286-backup-20260629124101` before modifying it.
  - installed `@tencent-weixin/openclaw-weixin`, enabled `plugins.entries.openclaw-weixin.enabled=true`, and set `session.dmScope=per-account-channel-peer`.
  - QR login was attempted once through `openclaw channels login --channel openclaw-weixin`, but no phone confirmation occurred before the QR refresh limit; artifact `logs/runtime/openclaw-weixin-r286/login_attempt_summary.json` records `decision=openclaw_weixin_qr_login_not_completed` and does not store QR URLs.
  - post-plugin no-send gate artifact: `logs/runtime/openclaw-weixin-r286/setup_gate_after_plugin.json`.
  - post-login-timeout no-send gate artifact: `logs/runtime/openclaw-weixin-r286/setup_gate_after_login_timeout.json`.
  - current no-send gate result: `decision=openclaw_weixin_setup_blocked_login`, Node `24.18.0`, OpenClaw `2026.6.10`, plugin present/enabled, no configured account, no explicit `@im.wechat` target, and `send_attempts=0`.
- R286 validation passed:
  - `python -m unittest tests.test_wechat_openclaw_setup_gate tests.test_wechat_openclaw_readiness` ran 12 tests OK.
  - process scan found no lingering Node/OpenClaw/OpenClaw-Weixin process after the failed QR login; only the scan command itself matched.
  - secret-pattern scan on `logs/runtime/openclaw-weixin-r286` found no QR URL, token, cookie, password, or session-id matches.
- R287 retried OpenClaw-Weixin QR authorization after the user reported desktop WeChat was already logged in:
  - before retry no-send gate artifact: `logs/runtime/openclaw-weixin-r287/setup_gate_before_qr_retry.json`.
  - QR authorization command: `openclaw channels login --channel openclaw-weixin`.
  - result artifact: `logs/runtime/openclaw-weixin-r287/login_retry_summary.json`.
  - post-timeout no-send gate artifact: `logs/runtime/openclaw-weixin-r287/setup_gate_after_qr_retry_timeout.json`.
  - result: `decision=openclaw_weixin_qr_login_not_completed`; QR codes expired without phone-side confirmation; no QR URL was stored in artifacts.
  - post-retry no-send gate remains `decision=openclaw_weixin_setup_blocked_login`, with Node `24.18.0`, OpenClaw `2026.6.10`, plugin present/enabled, `accounts=[]`, no explicit `@im.wechat` target, and `send_attempts=0`.
  - process scan found no lingering OpenClaw/Node process; only scan commands matched.
  - secret-pattern scan on `logs/runtime/openclaw-weixin-r287` found no QR URL, token, cookie, password, or session-id matches.
  - `python -m unittest tests.test_wechat_openclaw_setup_gate tests.test_wechat_openclaw_readiness` ran 12 tests OK.
  - reusable guardrail added to `C:/Users/Zhangjinqian/.codex/skills/desktop-background-control-testing/SKILL.md`: `Desktop Login Masquerades As Bot Channel Auth`.
- R288 records the route decision from the user: WeChat is temporarily a foreground-only implementation. No new send or GUI action happened in R288. The accepted live proof remains R279 foreground File Transfer Assistant send/readback. OpenClaw-Weixin is no longer the active desktop WeChat control route; it remains only a possible separate bot-channel route.

## Open Blockers

- Codex app-server WebSocket notifications can miss live assistant delta/completion even when the session completes successfully. The accepted fallback is strict session JSONL readback from assistant-owned records only.
- The current proof is for Codex app-server text send/readback, not arbitrary desktop mouse/keyboard takeover.
- Other target apps still need their own owned/background transports before they can be marked send-ready without foreground interaction.
- Full Cursor model transcript/readback after `composer.sendToAgent` remains blocked. R272 proves `composer.sendToAgent` can resolve without persisting even the marker request into the currently readable Cursor transcript stores, so dispatch success must not be treated as operation completion.
- Cursor `glass.newAgentWithQuery` is also not a verified submit route. R274 proves the command is callable and returns `resolved`, but it does not persist the marker into readable workspace/global Cursor storage and does not produce assistant-side completion evidence.
- Cursor now has a durable matrix distinction: background draft insertion and foreground UIA/clipboard fallback are preserved as real capabilities, but the Cursor Agent surface remains `cursor_submit_readback_blocked` until a true submit/readback route is verified.
- WeChat now has a durable matrix distinction: explicit foreground File Transfer Assistant send is revalidated on the current machine, local native bridge fixture protocol is verified, and historical live read-only/native endpoint evidence exists, but real background-native File Transfer Assistant send/readback remains unimplemented or unverified.
- WeChat foreground send now has automated Python WinRT OCR marker readback verified in a fresh integrated R279 report, but it still uses foreground keyboard/clipboard and therefore cannot count as background-native control.
- Current machine has no registered WeChat native bridge URL as of R280. R281 added a safe external-command adapter boundary, but no concrete real WeChat external command/SDK backend is configured yet. R282 found live personal WeChat loopback ports `14013`, `14016`, `14019`, `14022`, and `14023`, but classified them as `tcp-unknown`, not HTTP/CDP and not the OpenWukong bridge contract. R283 found ilink/mojo/IPC static binary evidence but no helper manifest or proven send contract. R286 cleared the OpenClaw-Weixin Node/plugin blockers for the separate bot-channel route, but R286/R287 QR authorization did not complete and no OpenClaw-Weixin account credentials exist. As of R288, that OpenClaw auth gap is no longer an active blocker for the desktop-control objective because WeChat work is temporarily foreground-only; it matters only if the separate bot-channel route is revived. UIA read-only evidence confirms personal WeChat exposes no semantic write surface, so real desktop WeChat background send remains blocked until a send-capable desktop backend is installed, implemented, or proven at the protocol level.

## Next Actions

1. Productize the verified WeChat foreground path: add an explicit foreground takeover permission gate, exact personal-WeChat target resolution, File Transfer Assistant or selected-contact verification, clipboard backup/restore, focus restore, Python WinRT OCR readback, and a final report that marks the route `foreground_required` rather than `background_execute`.
2. Keep Cursor submit work paused unless a real submit-capable service hook or official transcript/readback surface is found; do not keep retrying `composer.sendToAgent` or `glass.newAgentWithQuery`.
3. Add an Office object-model connector before claiming background Office write readiness.

## Guardrails

- Do not count user message echoes, request JSON, or `item/started` user records as assistant readback.
- Session fallback is valid only when assistant `response_item` or `task_complete.last_agent_message` contains the required marker.
- Owned ephemeral Codex app-server tests should start a fresh thread instead of reusing stale `thread/list useStateDbOnly=true` results.
- Do not introduce real foreground input unless the route policy and no-foreground contract explicitly allow it.
- Do not launch Cursor with an isolated `--user-data-dir` for the user's normal logged-in workflow; it opens an unauthenticated Cursor profile. Use the already registered live bridge `http://127.0.0.1:8787` for `PaoPaoHeZi` attach-only validation.
- When discovering IDE bridge URLs for a target workspace, require registry workspace identity to match; do not accept a same-family Cursor bridge from a different workspace.
- Do not treat empty-workspace Cursor bridges as ready. Auto-started IDE bridges must either have a workspace folder or remain unpublished until the workspace appears.
- Do not call `vscode.commands.getCommands(true)` or Cursor private commands before rejecting unsafe draft-hook profiles; rejection paths must be fast and independent of command-service health.
- For Cursor transcript acceptance, require assistant/response-side marker evidence. User bubbles (`type=1`), prompt blobs, request JSON, and ambiguous blob hits are diagnostic only.
- For WeChat readiness, do not collapse foreground File Transfer Assistant sends, fixture bridge sends, bridge route readiness, and real native send/readback into one state. Only real native send/readback with zero window/keyboard/clipboard attempts may count as background execute.
- WeChat foreground implementation is allowed only as explicit takeover. It must use target verification, foreground permission, clipboard/focus restoration, OCR marker readback, and clear `foreground_required` reporting; it must never satisfy a no-foreground contract.
- Static Weixin binary evidence such as ilink/mojo DLL names, PE exports, IPC strings, pipe strings, or localhost strings is discovery evidence only. It can prioritize helper/protocol work but must not promote WeChat to background execution without a concrete send contract and marker readback.
- OpenClaw-Weixin evidence must stay separate from desktop WeChat evidence. A configured iLink bot channel may prove background Weixin messaging as a bot, but it must not be reported as personal desktop WeChat control or File Transfer Assistant control.
- OpenClaw-Weixin setup plans must not be reported as executed capability. A no-send setup gate may only become `ready_for_send_probe`; a separate opt-in send/readback artifact is required before bot-channel send proof exists.
- Desktop WeChat login does not count as OpenClaw-Weixin bot-channel account auth. Account readiness must be proven by OpenClaw-Weixin's own redacted account credential state or capability readback.

## R292 WeChat implementation checkpoint

- Shared DesktopAction and SurfaceCapabilityProfile contracts, capability
  planner, personal-WeChat observer/resolver, lifecycle/read/draft/message
  dispatcher, send/media/file contracts, Moments, monitoring, side-effect
  gates, and optional Windows UIA/foreground backend are present.
- Focused WeChat/Desktop regression passed 98 tests.
- Live dry-run still finds only two structural elements in personal Weixin
  PID 28976/HWND 133790 and cannot resolve File Transfer Assistant or a
  semantic composer; all control and input attempts stayed at zero.
- Full repository discovery remains non-clean at 1020 tests with 11 failures
  and 1 error from pre-existing areas and known expectation drift.
- Remote implementation checkpoint is fdb1a2a; rollback baseline remains
  afe317c9148f894b8d19ddb8f1f2f2934e74068a.

## R293 File Transfer Assistant real send

- User-authorized real foreground test sent marker
  OPENWUKONG_WECHAT_FILEHELPER_DIRECT_20260909_1105_01 to the personal
  WeChat File Transfer Assistant.
- Evidence is kept in the ignored runtime report
  logs/runtime/wechat-file-helper-direct-test-20260909/report.json and the
  bound post-send screenshot in the same run directory.
- Result: status sent, exact target verified, Python WinRT Windows Media OCR
  post-send readback verified, one send attempt, six keyboard-input attempts,
  two clipboard writes, one clipboard restore, and one foreground restore.
- Boundary: this is explicit foreground text-send evidence only. It does not
  promote WeChat to background-native readiness and does not prove attachment,
  Moments, receive-monitor, or arbitrary-contact coverage.

## R294 WeChat attachment and Moments foreground paths

- Added an explicit File Transfer Assistant attachment probe with workspace
  root containment, file size/SHA-256 metadata, CF_HDROP clipboard restore,
  bound-window capture, and no-retry side-effect reporting.
- Added positioned WinRT OCR evidence for Moments surface, publish panel, and
  post-publish body readback. The isolated runtime now declares
  `winrt-Windows.Foundation.Collections` alongside the other WinRT OCR
  packages; `pip check` passed during setup.
- Added `run_wechat_moments_text_publish_probe` and wired
  `WeChatWindowsBackend.publish_moment`. The probe requires explicit publish
  opt-in, a typed `publish_moments` foreground takeover request, relative
  coordinates for the three UI steps, one publish attempt, and state restore.
- Focused validation after this slice: 95 tests passed; compileall and
  `git diff --check` passed.
- Live attachment screenshot showed the expected attachment card, while the
  machine report stayed `unverified` because composer-boundary OCR failed.
  No real Moments post was executed in this checkpoint; therefore the code
  path is implemented but live Moments publish/readback remains unverified.
- Remote checkpoint: `b3207c9`; rollback baseline remains `afe317c9`.

## R295 File Explorer, browser, and Office adapters

- File Explorer has a registered `filesystem` connector on the
  `filesystem-native` route with workspace containment, overwrite and
  confirmation gates, and state readback for list/search/stat/mkdir/copy/move/
  rename.
- Browser typed actions now map through the health-gated DevTools runner for
  page read, navigation, input, click, form submit, and result extraction;
  legacy HTTP/text commands remain available.
- Office has a registered `OfficeSessionConnector` on
  `office-object-model-or-addin`. Word create/read/append, Excel cell
  read/write, and PowerPoint read/add-text use a private COM instance and
  return object-model readback without foreground input.
- Technology freshness checked 2026-09-11: official Microsoft automation and
  object-model documentation plus official PyPI metadata were consulted;
  Python 3.13.5 consumes pywin32 312, which is declared as
  `pywin32>=312; sys_platform == 'win32'`; `pip check` passed.
- Combined focused validation passed 164 tests; broader repository failures
  remain the previously recorded unrelated baseline failures. No real browser
  submission or Office user-document mutation was executed.

## R296 Typed browser actions reach the shared fabric

- `ControlFabric.execute` now maps typed browser action names to the existing
  health-gated DevTools runner and forwards typed selector/value/url parameters.
- This removes the main-entry mismatch between `BrowserSessionConnector` and
  the fabric's special DevTools dispatch branch.
- Focused validation now passes 166 tests, including fabric-level typed browser
  dispatch; `pip check` and `git diff --check` pass.
