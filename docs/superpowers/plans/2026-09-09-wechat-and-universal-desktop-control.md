# 微信与通用桌面操作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a capability-first desktop action kernel and use it to cover the complete set of basic operations for the personal Windows WeChat desktop client, with the Windows File Explorer, browser, and Office adapters sharing the same contracts afterward.

**Architecture:** Introduce a versioned desktop action model, short-lived runtime surface capability profiles, per-action route negotiation, and result verification above the existing `ControlFabric`. WeChat will be a surface adapter composed of observation, target resolution, execution, and verification; native endpoints remain optional accelerators, while UIA, approved foreground input, OCR, and file state provide general fallbacks. The first implementation plan covers the shared kernel and WeChat; File Explorer, browser, and Office follow as separate adapter slices using the same interfaces.

**Tech Stack:** Python 3.13 project virtual environment, dataclasses, existing `ControlFabric`, `ConnectorTarget`/`SessionConnector`, pywinauto UIA, psutil process discovery, Python WinRT Windows OCR, existing trajectory and side-effect gates, unittest fixtures, and JSON evidence reports.

---

## Scope and acceptance rules

- The WeChat action catalog includes application/window lifecycle, navigation and search, contact/group inspection, message reading and management, text and emoji, image/media, file transfer, Moments browsing and publishing, receive monitoring, ordinary notification/display/download settings, drafts, and state restoration.
- Sending a chat message or publishing a Moment requires a target and content confirmation before a side-effecting route runs. The post-action message or Moment must be read back.
- Delete, recall, add-friend, group membership changes, bulk forwarding or broadcast, account switching, login authorization, and security settings remain in the catalog but require a separate exact confirmation and post-action readback. Payment, red packets, and transfers are outside this plan.
- A route may be reported as ready only when its required target, ownership, capability, approval, and verification evidence are present. A dispatched key or native response without readback is not success.
- Existing connector APIs and previously verified foreground File Transfer Assistant evidence remain backward compatible.

## Task 1: Add the versioned desktop action model

**Files:**
- Create: `src/openwukong/control/desktop_action.py`
- Modify: `src/openwukong/control/fabric.py` (accept conversion from the new model while preserving `ControlIntent`)
- Test: `tests/test_desktop_action.py`

- [ ] **Step 1: Write failing serialization and risk tests**

```python
from openwukong.control.desktop_action import (
    DesktopAction,
    DesktopApproval,
    DesktopTarget,
    DesktopVerification,
)

def test_action_round_trip_preserves_target_parameters_and_effect():
    action = DesktopAction(
        action="wechat.chat.send_text",
        target=DesktopTarget(process_name="Weixin.exe", conversation_name="张三"),
        parameters={"text": "hello"},
        effect_class="external_communication",
        verification=DesktopVerification(required_markers=("hello",)),
        approval=DesktopApproval(required=True, approval_id="approval-1"),
    )
    restored = DesktopAction.from_dict(action.to_dict())
    assert restored == action

def test_high_risk_action_requires_exact_approval():
    action = DesktopAction(
        action="wechat.contact.add",
        target=DesktopTarget(process_name="Weixin.exe", conversation_name="张三"),
        effect_class="high_risk",
    )
    assert action.requires_confirmation is True
    assert action.approval.required is True
```

- [ ] **Step 2: Run the focused test and verify the missing model failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_desktop_action -v`  
Expected: FAIL because `openwukong.control.desktop_action` does not yet exist.

- [ ] **Step 3: Implement the minimal immutable model**

Implement `DesktopTarget`, `DesktopVerification`, `DesktopApproval`, and `DesktopAction` as frozen dataclasses with:

```python
class DesktopAction:
    schema_version = "openwukong-desktop-action-v1"

    @property
    def requires_confirmation(self) -> bool:
        return self.effect_class in {
            "external_communication",
            "local_write",
            "delete",
            "high_risk",
        }

    def to_control_intent(self) -> ControlIntent:
        return ControlIntent(
            action=self.action,
            text=str(self.parameters.get("text", "")),
            value=str(self.parameters.get("value", "")),
            parameters=dict(self.parameters),
            allow_submit=self.approval.confirmed,
            allow_foreground_interaction=self.approval.allow_foreground,
            confirmed_effect_ids=self.approval.confirmed_effect_ids,
        )
```

`to_dict()` must retain native scalar types, omit secrets, and include schema version, target, parameters, effect class, verification, and approval. `from_dict()` must reject an unknown schema version and malformed target identity.

- [ ] **Step 4: Add the ControlIntent conversion and run the focused test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_desktop_action -v`  
Expected: PASS.

- [ ] **Step 5: Commit the action model**

```text
git add src/openwukong/control/desktop_action.py src/openwukong/control/fabric.py tests/test_desktop_action.py
git commit -m "feat: add versioned desktop action model"
```

## Task 2: Add runtime surface capability profiles

**Files:**
- Create: `src/openwukong/control/surface_capabilities.py`
- Modify: `src/openwukong/evaluation/accessibility_probe.py` (expose normalized facts without changing its read-only behavior)
- Test: `tests/test_surface_capabilities.py`

- [ ] **Step 1: Write failing freshness and capability tests**

```python
from datetime import datetime, timezone, timedelta
from openwukong.control.surface_capabilities import (
    CapabilityEvidence,
    SurfaceCapabilityProfile,
)

def test_profile_supports_only_observed_action_and_bound_target():
    profile = SurfaceCapabilityProfile(
        process_name="Weixin.exe",
        pid=123,
        hwnd=456,
        observed_at=datetime.now(timezone.utc),
        capabilities={"wechat.chat.read": {"route": "uia", "confidence": 90}},
        evidence=(CapabilityEvidence(source="uia", field="message_list", value=True),),
    )
    assert profile.supports("wechat.chat.read") is True
    assert profile.supports("wechat.chat.send_text") is False
    assert profile.is_bound(pid=123, hwnd=456) is True

def test_expired_profile_cannot_execute():
    profile = SurfaceCapabilityProfile(
        process_name="Weixin.exe",
        pid=123,
        hwnd=456,
        observed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        ttl_seconds=30,
    )
    assert profile.is_fresh(now=datetime.now(timezone.utc)) is False
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_surface_capabilities -v`  
Expected: FAIL because the profile module is missing.

- [ ] **Step 3: Implement profile, evidence, and freshness checks**

Use an immutable profile with `capabilities: dict[str, dict]`, `evidence: tuple[CapabilityEvidence, ...]`, `observed_at`, `ttl_seconds`, `pid`, and `hwnd`. Implement `supports(action, minimum_confidence=0)`, `is_bound(pid, hwnd)`, `is_fresh(now)`, and `to_dict()`. A profile with missing PID/HWND or stale evidence must not report an executable write capability.

- [ ] **Step 4: Add probe normalization and run focused tests**

Expose a helper that maps existing `AccessibilityWindowSnapshot` elements to capability names such as `desktop.observe`, `wechat.chat.read`, `wechat.chat.draft`, and `wechat.moments.publish`. Keep the probe read-only and retain the original element evidence. Run: `.\.venv\Scripts\python.exe -m unittest tests.test_surface_capabilities tests.test_accessibility_probe -v`  
Expected: PASS.

- [ ] **Step 5: Commit the capability profile**

```text
git add src/openwukong/control/surface_capabilities.py src/openwukong/evaluation/accessibility_probe.py tests/test_surface_capabilities.py
git commit -m "feat: add runtime desktop capability profiles"
```

## Task 3: Make route selection capability-first with optional bridges

**Files:**
- Create: `src/openwukong/control/desktop_action_planner.py`
- Modify: `src/openwukong/connectors/route_policy.py`
- Modify: `src/openwukong/control/transport_capability.py`
- Modify: `src/openwukong/control/fabric.py`
- Test: `tests/test_desktop_action_planner.py`

- [ ] **Step 1: Write failing route negotiation tests**

```python
def test_wechat_without_native_bridge_uses_verified_uia_or_foreground_fallback():
    plan = plan_desktop_action(
        action=_wechat_send_action(),
        profile=_wechat_profile(capabilities={"wechat.chat.send_text": {"route": "uia"}}),
        connectors=(),
    )
    assert plan.selected_route == "uia-semantic"
    assert plan.blocked is False

def test_wechat_without_any_write_capability_stays_read_only():
    plan = plan_desktop_action(
        action=_wechat_send_action(),
        profile=_wechat_profile(capabilities={"wechat.chat.read": {"route": "uia"}}),
        connectors=(),
    )
    assert plan.blocked is True
    assert plan.reason == "capability_missing"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_desktop_action_planner -v`  
Expected: FAIL because capability-first planning is not implemented.

- [ ] **Step 3: Implement per-action route negotiation**

Implement `DesktopActionPlan` and `plan_desktop_action()` with this order: verified native/extension/DevTools/object model, UIA semantic, approved foreground UIA, vision plus approved input, read-only or blocked. A native connector scores higher only when its `route_ready()` and capability report satisfy the action; it must not be required just because the process is Weixin.exe. Carry forward `ControlRouteStep`, `TransportCapabilityReport`, side-effect requirements, and missing capabilities.

- [ ] **Step 4: Integrate the plan into ControlFabric without breaking legacy dispatch**

When `ControlIntent.parameters` contains a normalized desktop action and a capability profile, call the new planner before connector dispatch. Keep existing browser, terminal, Git, IDE, and agent routes unchanged when no desktop profile is supplied. Add explicit `execution_mode` values for `background_semantic`, `foreground_desktop`, `read_only`, and `none`.

- [ ] **Step 5: Run existing routing regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_control_fabric tests.test_transport_capability_matrix tests.test_desktop_action_planner -v`  
Expected: existing tests pass; new planner tests pass.

- [ ] **Step 6: Commit capability-first routing**

```text
git add src/openwukong/control/desktop_action_planner.py src/openwukong/connectors/route_policy.py src/openwukong/control/transport_capability.py src/openwukong/control/fabric.py tests/test_desktop_action_planner.py
git commit -m "feat: negotiate desktop routes from observed capabilities"
```

## Task 4: Build the WeChat surface observer and target resolver

**Files:**
- Create: `src/openwukong/connectors/wechat_desktop.py`
- Create: `src/openwukong/control/wechat_surface.py`
- Modify: `src/openwukong/evaluation/wechat_locator.py`
- Test: `tests/test_wechat_surface.py`

- [ ] **Step 1: Write fixture-driven discovery tests**

Cover personal `Weixin.exe` selection over `WXWork.exe`, multiple windows, login-state detection, search controls, conversation list, message list, Moments entry, publish panel, and missing semantic controls. Assert that discovery performs zero keyboard, mouse, clipboard, or UIA mutation attempts.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_surface -v`  
Expected: FAIL because the surface observer and resolver are missing.

- [ ] **Step 3: Implement read-only observation**

`WeChatSurfaceObserver.inspect()` must return a `SurfaceCapabilityProfile` plus normalized control candidates. It must bind process path, PID, HWND, window title, and session/login evidence. It must not focus the window or mutate UI state.

- [ ] **Step 4: Implement exact target resolution**

`WeChatTargetResolver.resolve(kind, query)` must return ordered candidates containing target type, display name, stable text anchors, source evidence, and a confidence score. Exact match or an explicit selected candidate is required for write actions; ambiguous matches return `target_unresolved` and no control attempts.

- [ ] **Step 5: Run discovery and locator regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_surface tests.test_wechat_locator tests.test_accessibility_probe -v`  
Expected: PASS.

- [ ] **Step 6: Commit the observer and resolver**

```text
git add src/openwukong/connectors/wechat_desktop.py src/openwukong/control/wechat_surface.py src/openwukong/evaluation/wechat_locator.py tests/test_wechat_surface.py
git commit -m "feat: add WeChat surface observation and target resolution"
```

## Task 5: Implement WeChat lifecycle, navigation, reading, drafts, and message management

**Files:**
- Modify: `src/openwukong/connectors/wechat_desktop.py`
- Modify: `src/openwukong/control/wechat_surface.py`
- Modify: `src/openwukong/connectors/desktop_uia.py`
- Test: `tests/test_wechat_desktop_read_and_navigation.py`

- [ ] **Step 1: Add failing action contract tests**

Cover `attach`, `inspect`, `launch`, `minimize`, `restore`, `open_search`, `search_contact`, `search_group`, `open_conversation`, `read_conversation`, `read_contact`, `read_group`, `draft_text`, `copy_message`, `quote_message`, `reply_message`, `forward_message`, `favorite_message`, `translate_message`, `mark_unread`, `pin_conversation`, `mute_conversation`, and `archive_conversation`. Use fixture control trees and assert each result includes route, target binding, verification, and attempt counters.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_desktop_read_and_navigation -v`  
Expected: FAIL for the new action methods.

- [ ] **Step 3: Implement read-only and reversible actions first**

Map semantic controls through the existing UIA locator helpers. Use foreground takeover only for actions that cannot be performed semantically. For every action, capture a precondition snapshot, execute at most once, then verify the expected state or text. Mark message operations that cannot identify a stable message ID as `capability_missing` rather than selecting by an ambiguous index.

- [ ] **Step 4: Implement draft and navigation verification**

Draft verification must read the composer value and confirm `send_attempts == 0`. Navigation verification must reread the conversation/contact/group title after every open or search action. Window lifecycle operations must verify process and HWND state after the operation.

- [ ] **Step 5: Run focused and existing UIA tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_desktop_read_and_navigation tests.test_wechat_uia_action_contract tests.test_desktop_uia_connector -v`  
Expected: PASS.

- [ ] **Step 6: Commit the non-sending WeChat actions**

```text
git add src/openwukong/connectors/wechat_desktop.py src/openwukong/control/wechat_surface.py src/openwukong/connectors/desktop_uia.py tests/test_wechat_desktop_read_and_navigation.py
git commit -m "feat: add WeChat lifecycle navigation and read actions"
```

## Task 6: Implement text, emoji, image, video, voice, and file transfer with verification

**Files:**
- Modify: `src/openwukong/connectors/wechat_desktop.py`
- Modify: `src/openwukong/control/wechat_surface.py`
- Modify: `src/openwukong/evaluation/wechat_send_probe.py`
- Test: `tests/test_wechat_desktop_send_and_transfer.py`

- [ ] **Step 1: Add failing send and transfer tests**

Cover semantic `set_value` plus `invoke`, the existing foreground keyboard/clipboard fallback, text and emoji payloads, file path validation, image/video/voice attachment selection, post-send readback, clipboard restoration, foreground restoration, and no-repeat behavior after verification failure.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_desktop_send_and_transfer -v`  
Expected: FAIL for the new transfer action contracts.

- [ ] **Step 3: Implement semantic and foreground execution paths**

Use existing `WeChatUiaSemanticActionSenderAdapter` for a verified composer and submit control. Use the existing foreground probe only after a validated `ForegroundTakeoverRequest`; save and restore clipboard and foreground HWND. For attachment actions, accept only explicit files inside an approved root or explicitly authorized paths, pass files through a deterministic selection operation, and include file size/hash metadata in the plan.

- [ ] **Step 4: Add post-action verifier and unknown-result state**

Verify the target conversation and required marker, attachment name or thumbnail. If the action may have happened but readback is missing, return `verification_failed` with `send_attempts == 1` and do not retry automatically. Keep native bridge reports separate from foreground reports; a fixture endpoint cannot promote the live machine to background-ready.

- [ ] **Step 5: Run send and transfer regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_desktop_send_and_transfer tests.test_wechat_send_probe tests.test_wechat_native_bridge tests.test_wechat_native_bridge_real_send_probe -v`  
Expected: PASS.

- [ ] **Step 6: Commit verified send and transfer paths**

```text
git add src/openwukong/connectors/wechat_desktop.py src/openwukong/control/wechat_surface.py src/openwukong/evaluation/wechat_send_probe.py tests/test_wechat_desktop_send_and_transfer.py
git commit -m "feat: add verified WeChat message and media transfer actions"
```

## Task 7: Implement Moments browsing and publishing

**Files:**
- Modify: `src/openwukong/connectors/wechat_desktop.py`
- Modify: `src/openwukong/control/wechat_surface.py`
- Test: `tests/test_wechat_moments.py`

- [ ] **Step 1: Add failing Moments contract tests**

Cover opening the Moments surface, reading visible posts, preparing a text-only draft, selecting images or video, selecting public/partial/not-visible audience, cancelling without publish, publishing once, and readback of the newly published post.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_moments -v`  
Expected: FAIL because the Moments action handlers are missing.

- [ ] **Step 3: Implement preview and explicit publish confirmation**

Require a `MomentsPublishRequest` containing body, media list, visibility, target HWND/PID, and approval ID. Validate every media path and produce a preview report before any publish control. Prefer semantic or native routes; otherwise execute once through bound foreground takeover.

- [ ] **Step 4: Implement publish readback and cancellation**

After publishing, reread the personal feed and match body plus media metadata. A missing match returns `verification_failed` and prevents another publish attempt. A cancel path must restore state and record zero publish attempts.

- [ ] **Step 5: Run Moments and side-effect regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_moments tests.test_control_fabric_execution tests.test_no_foreground_contract -v`  
Expected: PASS.

- [ ] **Step 6: Commit Moments support**

```text
git add src/openwukong/connectors/wechat_desktop.py src/openwukong/control/wechat_surface.py tests/test_wechat_moments.py
git commit -m "feat: add verified WeChat Moments actions"
```

## Task 8: Implement receive monitoring, unread state, notifications, and recovery

**Files:**
- Create: `src/openwukong/control/wechat_monitor.py`
- Modify: `src/openwukong/connectors/wechat_desktop.py`
- Test: `tests/test_wechat_monitor.py`

- [ ] **Step 1: Add failing monitor and dedup tests**

```python
def test_monitor_emits_only_new_messages_for_bound_conversation():
    monitor = WeChatMonitor(source=_fixture_source(["m1", "m1", "m2"]))
    assert monitor.poll_once().messages == ["m1"]
    assert monitor.poll_once().messages == []
    assert monitor.poll_once().messages == ["m2"]
```

Also cover pause/resume, window loss, login-state change, unread count, desktop notifications, and no-notification behavior when nothing changed.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_monitor -v`  
Expected: FAIL because the monitor module is missing.

- [ ] **Step 3: Implement bounded polling and deduplication**

Bind monitor state to PID, HWND, conversation identity, start/end time, and a cursor. Derive dedup keys from message identity where available, otherwise from normalized sender/time/text/attachment evidence. Polling must be read-only and must not focus or mutate the window.

- [ ] **Step 4: Add recovery and quiet behavior**

When the window or login state changes, stop with `state_changed` and require rebinding. When there is no new message, return a quiet result. Persist cursor and restore state only after successful cleanup.

- [ ] **Step 5: Run monitor and lifecycle regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_monitor tests.test_session_discovery tests.test_window_capture -v`  
Expected: PASS.

- [ ] **Step 6: Commit monitoring and recovery**

```text
git add src/openwukong/control/wechat_monitor.py src/openwukong/connectors/wechat_desktop.py tests/test_wechat_monitor.py
git commit -m "feat: add bounded WeChat receive monitoring"
```

## Task 9: Add ordinary WeChat settings and high-risk action gates

**Files:**
- Modify: `src/openwukong/control/side_effects.py`
- Modify: `src/openwukong/control/wechat_surface.py`
- Modify: `src/openwukong/connectors/wechat_desktop.py`
- Test: `tests/test_wechat_side_effects.py`

- [ ] **Step 1: Add failing gate tests**

Assert that ordinary notification, shortcut, display, chat-display, and download-directory settings require readback and stay within the requested scope. Assert that delete, recall, add-friend, group membership, bulk forward/broadcast, account switch, login authorization, and security settings return `confirmation_required` without control attempts when approval is absent or mismatched.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_side_effects -v`  
Expected: FAIL for the new action-specific gates.

- [ ] **Step 3: Implement effect classification and exact approval binding**

Map every action in the catalog to a side-effect class. Extend the existing side-effect report with target identity hash, approval ID, visibility or recipient scope, and expiry. The execution path must compare the approved action and target with the planned action before any UI mutation.

- [ ] **Step 4: Run side-effect and foreground approval regressions**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_side_effects tests.test_foreground_takeover tests.test_no_foreground_contract -v`  
Expected: PASS.

- [ ] **Step 5: Commit action-specific gates**

```text
git add src/openwukong/control/side_effects.py src/openwukong/control/wechat_surface.py src/openwukong/connectors/wechat_desktop.py tests/test_wechat_side_effects.py
git commit -m "feat: gate WeChat side effects by action and target"
```

## Task 10: Integrate status reporting and preserve evidence boundaries

**Files:**
- Modify: `src/openwukong/evaluation/computer_operation_readiness_matrix.py`
- Modify: `src/openwukong/evaluation/computer_operation_status_report.py`
- Modify: `src/openwukong/connectors/registry.py`
- Modify: `src/openwukong/connectors/__init__.py`
- Test: `tests/test_wechat_readiness_integration.py`

- [ ] **Step 1: Add failing readiness tests**

Cover these states: read-only WeChat probe, semantic draft-ready, foreground text-send verified, foreground Moments-publish verified, native fixture-only, native real-send verified, and blocked due missing capability or readback. Assert fixture evidence never promotes a live endpoint.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_readiness_integration -v`  
Expected: FAIL because the readiness matrix does not consume the new capability profiles and action evidence.

- [ ] **Step 3: Register the WeChat desktop connector and merge evidence**

Register the connector without removing the existing native bridge. Add action-level verified capabilities and keep surface status separate from extra capabilities such as `background_draft` and `foreground_moments_publish`. Preserve the existing rule that a real native send/readback with zero window, keyboard, and clipboard attempts is required for background promotion.

- [ ] **Step 4: Run readiness and full focused regression**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_wechat_readiness_integration tests.test_computer_operation_readiness_matrix tests.test_computer_operation_status_report tests.test_wechat_native_bridge tests.test_wechat_send_probe -v`  
Expected: PASS, except for any pre-existing generic-desktop expectation drift, which must be reported separately and not hidden.

- [ ] **Step 5: Commit readiness integration**

```text
git add src/openwukong/evaluation/computer_operation_readiness_matrix.py src/openwukong/evaluation/computer_operation_status_report.py src/openwukong/connectors/registry.py src/openwukong/connectors/__init__.py tests/test_wechat_readiness_integration.py
git commit -m "feat: integrate WeChat action readiness evidence"
```

## Task 11: Run controlled Windows verification for WeChat

**Files:**
- Create: `src/openwukong/evaluation/wechat_basic_operations_demo.py`
- Test: `tests/test_wechat_basic_operations_demo.py`
- Runtime output: `logs/runtime/wechat-basic-operations-<run-id>/`

- [ ] **Step 1: Add a no-send demo gate**

The demo must discover and bind personal WeChat, capture a read-only capability profile, resolve a user-selected target, and emit a plan for every catalog category without executing external communication.

- [ ] **Step 2: Run the no-send demo**

Run: `.\.venv\Scripts\python.exe -m openwukong.evaluation.wechat_basic_operations_demo --workspace-path . --target-name "文件传输助手" --dry-run --json`  
Expected: a JSON report with `control_allowed=false`, zero keyboard/mouse/clipboard attempts, capability coverage, missing capabilities, and a deterministic artifact path.

- [ ] **Step 3: Run one explicit text-send verification**

Only after the dry-run report and foreground takeover request are valid, run one marker message to File Transfer Assistant. Verify target, message marker, OCR readback, foreground restoration, clipboard restoration, and cleanup. Do not test a normal contact or group without a new explicit user instruction.

- [ ] **Step 4: Run one explicit Moments verification**

Use user-provided text and a temporary media file, record the selected visibility, publish once, read back the new personal-feed entry, and remove temporary artifacts. If the publish panel or audience selector cannot be verified, stop without publishing.

- [ ] **Step 5: Run the complete focused regression**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_desktop_action tests.test_surface_capabilities tests.test_desktop_action_planner tests.test_wechat_surface tests.test_wechat_desktop_read_and_navigation tests.test_wechat_desktop_send_and_transfer tests.test_wechat_moments tests.test_wechat_monitor tests.test_wechat_side_effects tests.test_wechat_readiness_integration tests.test_wechat_native_bridge tests.test_wechat_send_probe -v`  
Expected: all new tests pass; any pre-existing failures are listed with their original expectations and are not reclassified as success.

- [ ] **Step 6: Commit the verification harness**

```text
git add src/openwukong/evaluation/wechat_basic_operations_demo.py tests/test_wechat_basic_operations_demo.py
git commit -m "test: add controlled WeChat basic operations verification"
```

## Follow-on adapter plans

After the shared kernel and WeChat acceptance report are stable, create separate plans for:

1. **Windows File Explorer:** Shell/UIA observation, reversible file operations, path-bound selection, and file-system readback.
2. **Browser:** existing DevTools connector projected into the desktop action model, with UIA/visual fallback only when the controlled browser session is unavailable.
3. **Office:** object-model or add-in adapter for Word, Excel, and PowerPoint, with close/reopen content verification.

These adapters must register capabilities with the same profile and use the same `ControlFabric`, side-effect gate, foreground takeover, trajectory recorder, and evidence schema.

## Final verification checklist

- [ ] Re-read every changed module and test; run `git diff --check`.
- [ ] Run the complete focused regression from Task 11.
- [ ] Run the existing project regression that covers connectors, control fabric, UIA, readiness, and trajectory reporting.
- [ ] Confirm all dry-run paths report zero control attempts.
- [ ] Confirm foreground paths require exact approval and restore state.
- [ ] Confirm no native fixture or historical report promotes an unverified live WeChat route.
- [ ] Confirm no payment, red-packet, or transfer action appears in current implementation or acceptance fixtures.
- [ ] Record the final WeChat readiness matrix and remaining missing capabilities in `.agents/conversation_index.md` and the project snapshot only after evidence is complete.
