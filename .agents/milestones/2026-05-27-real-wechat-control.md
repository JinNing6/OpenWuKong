# 2026-05-27 Real WeChat Control Milestone

## Milestone

This version proves that OpenWuKong can move from read-only desktop
observation to a real, gated action against a live Windows application.

Validated live target:
- WeChat for Windows
- File Transfer Assistant

Validated live action:
- Open the File Transfer Assistant conversation.
- Send a timestamped text message.
- Preserve an audit trail with screenshots and JSON reports.

## Implemented Capabilities

### Primary Real No-Loss Harness

Added `openwukong.evaluation.primary_real_no_loss`.

It runs the primary user scenarios in a real but non-destructive mode:
- WeChat: live read-only UIA/Win32/MSAA locator.
- Browser: owned isolated Chrome profile and DevTools read action.
- Files: owned temp-index search only.
- Codex: read-only IDE bridge capability probe.

Safety counters are explicit:
- `control_allowed=false`
- `control_attempts=0`
- `external_communication_attempts=0`
- `window_input_attempts=0`
- `real_user_filesystem_scan_attempts=0`
- `user_file_modification_attempts=0`

### WeChat Locator

Added `openwukong.evaluation.wechat_locator`.

It combines:
- UI Automation window and element capability snapshots.
- Win32 child HWND enumeration.
- MSAA/OLEACC `AccessibleObjectFromWindow` read-only metadata.

The locator records:
- top-level HWND
- process and class identity
- UIA semantic input/action counts
- Win32 child class counts
- MSAA object/name/value/role counts
- read-only route recommendations

It explicitly blocks write control until a deterministic connector exists.

### Explicit Opt-In WeChat Send Probe

Added `openwukong.evaluation.wechat_send_probe`.

Default behavior is blocked. A real send requires:
- `--allow-send`
- target name exactly equal to File Transfer Assistant
- target open/verification phase
- optional second-stage confirmation for live operator-controlled tests

The probe tracks:
- send attempts
- keyboard input attempts
- clipboard write and restore attempts
- foreground restore attempts
- pre-send screenshot
- post-send screenshot
- bound-window screenshot metadata
- transport id
- per-phase execution records
- report JSON path

Current transport:
- `foreground-keyboard-clipboard`

Important boundary:
- This is a controlled foreground transport, not a background-native connector yet.
- Post-send verification now prefers bound HWND screenshot capture so user window
  switching does not silently invalidate the artifact.

## Live Validation

### Read-Only WeChat Validation

Output roots:
- `logs/runtime/primary-real-no-loss-wechat-locator-20260527`
- `logs/runtime/primary-real-no-loss-wechat-msaa-20260527`

Results:
- matched live WeChat-family windows
- Weixin UIA exposed limited structure
- Win32 exposed child HWNDs
- MSAA exposed live accessible objects with zero MSAA errors
- write control stayed blocked

### Real WeChat Send Validation

Validated target:
- File Transfer Assistant

Validated message:
- `OpenWukong live send probe 2026-05-27 16:15:59`

Evidence:
- prepare screenshot:
  `logs/runtime/wechat-filehelper-send-prepare-20260527/pre_send_target.png`
- post-send screenshot:
  `logs/runtime/wechat-filehelper-send-confirmed-20260527/post_send_wechat_foreground_verify.png`

Result:
- message appeared in the live WeChat File Transfer Assistant conversation
- clipboard restore attempted
- foreground restore attempted

Archive pre-push validation:
- message:
  `OpenWukong archive live send probe 2026-05-27 16:34:43`
- output root:
  `logs/runtime/wechat-filehelper-send-archive-20260527-163443`
- result:
  `status=sent`, `send_attempts=1`, `keyboard_input_attempts=6`,
  `clipboard_write_attempts=2`, `clipboard_restore_attempts=1`,
  `foreground_restore_attempts=1`, `target_verified=true`
- screenshot mode:
  `bound-window`, with `post_send_screenshot_bound=true`
- evidence:
  `logs/runtime/wechat-filehelper-send-archive-20260527-163443/post_send_verify.png`

### Artifact Contract Validation

Output roots:
- `logs/runtime/wechat-filehelper-send-artifact-prepare-20260527`
- `logs/runtime/wechat-filehelper-send-artifact-confirmed-20260527`

Validated fields:
- `artifact_path`
- `pre_send_screenshot_path`
- `post_send_screenshot_path`
- `post_send_screenshot_hwnd`
- `post_send_screenshot_bound`
- `transport`
- `phases`

## Tests

Current verification:
- `python -m unittest discover tests`
- result before archival push: full suite passing

Focused coverage:
- `tests/test_primary_real_no_loss.py`
- `tests/test_wechat_locator.py`
- `tests/test_wechat_send_probe.py`

## Known Boundaries

Still not solved:
- Fully background WeChat message sending.
- A stable WeChat-native bridge.
- OCR/accessibility-based post-send text verification.
- General-contact sending beyond File Transfer Assistant.

Current safe rule:
- File Transfer Assistant is the only allowed live send target.
- General chat sending must stay blocked until a deterministic connector,
  confirmation gate, and post-send verification exist.

## Next Steps

1. Add post-send OCR or accessibility verification against the bound WeChat HWND.
2. Build a transport comparison harness:
   `foreground-keyboard-clipboard` vs `bound-hwnd-screenshot` vs future native bridge.
3. Search for a stable WeChat-native connector path before expanding to other contacts.
