# -*- coding: utf-8 -*-
"""
agent_supervisor.py — 通用 IDE Agent 全时督导器

适用场景：任何通过智能 IDE（Cursor/Antigravity/VS Code + AI Agent）执行的任务。
科研跑分、功能开发、Bug 修复、UI 设计、部署运维……所有 Agent 任务皆可督导。

设计灵感：借鉴 OpenClaw 龙虾项目的 subagent-lifecycle-events（细粒度生命周期）、
subagent-control（steer 续发机制 + 速率限制）、cascade-kill（级联终止）模式。

核心逻辑：
  监控 → Agent 空闲? → 读取对话 → 达标? → YES: ✅ → NO: steer 续发指令
  监控 → Agent 报错?                           → 自动重试
  监控 → Agent 超时?                           → stall 检测 → 续发

使用：
    # 生成配置模板
    python agent_supervisor.py --gen-config goals.json

    # 启动督导（自动操控）
    python agent_supervisor.py --config goals.json

    # 演示模式（只读不操作）
    python agent_supervisor.py --config goals.json --demo

    # 24 小时全时运行
    python agent_supervisor.py --config goals.json --max-hours 24
"""

from __future__ import annotations

import sys
import io
import copy
import os
import json
import re
import time
import enum
import uuid
import dataclasses
from typing import Optional, Callable
from datetime import datetime
import difflib

import psutil
from pywinauto import Desktop
from pywinauto.application import Application
from pywinauto.keyboard import send_keys

from openwukong.core.constants import PROJECT_ALIASES, PROJECT_ALIAS_REVERSE
from openwukong.connectors import (
    BrowserSessionConnector,
    CodexDesktopConnector,
    ConnectorManager,
    ConnectorTarget,
    CopilotIDEConnector,
    CursorIDEConnector,
    GitCommandConnector,
    IDEExtensionConnector,
    TerminalCommandConnector,
    UIAIDEConnector,
)
from openwukong.core.logger import get_logger, log_event
from openwukong.monitor.ai_monitor import MultiProjectAIMonitor, AIStatus, AIProjectState
from openwukong.daemon.watchdog import Watchdog
from openwukong.core.run_logger import RunLogger
from openwukong.supervisor.identity import ActionRecord, WorkspaceIdentityModel

logger = get_logger("supervisor")

# 注: UTF-8 由 ai_monitor.py 统一处理，此处无需重复包装


# ═══════════════════════════════════════════════
#  生命周期事件（借鉴 OpenClaw subagent-lifecycle-events）
# ═══════════════════════════════════════════════

class LifecycleEvent(enum.Enum):
    """Agent 生命周期事件类型——比简单的 Running/Idle 更细致"""
    SPAWNED = "spawned"             # 首次探测到 Agent 运行
    RUNNING = "running"             # Agent 持续运行中
    COMPLETED = "completed"         # Agent 完成一轮 (Running→Idle)
    ERROR = "error"                 # Agent 报错
    STALLED = "stalled"             # Agent 长时间无变化
    STEERED = "steered"             # 已发送续发指令
    GOAL_ACHIEVED = "goal-achieved" # 目标达成
    GOAL_FAILED = "goal-failed"     # 达到重试上限
    KILLED = "killed"               # 被手动终止
    MATCH_FAILED = "match-failed"   # 项目匹配失败
    MATCH_SUCCESS = "match-success" # 项目匹配成功


class GoalStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    CHECKING = "checking"
    ACHIEVED = "achieved"
    STALLED = "stalled"
    FAILED = "failed"


# ═══════════════════════════════════════════════
#  任务目标（通用）
# ═══════════════════════════════════════════════

@dataclasses.dataclass
class TaskGoal:
    """
    单个任务目标——适用于任何 IDE Agent 可执行的工作
    """
    # ── 匹配 ──
    window_match: str               # 窗口标题匹配关键词

    # ── 目标 ──
    task_name: str                  # 任务名称
    goal: str                       # 目标描述（给人看的）
    success_keywords: list[str]     # 成功信号
    failure_keywords: list[str]     # 失败信号

    # ── Steer 行为（借鉴 OpenClaw steer 机制）──
    retry_command: str              # 未达标时续发的指令
    max_retries: int = 30           # 最大续发次数
    cooldown_sec: float = 10.0      # 两次续发最小间隔（速率限制）
    stall_timeout: float = 600.0    # 无变化超时（秒）
    connector_hint: str = "auto"    # 优先连接器，例如 uia-ide / terminal / browser
    workspace_path: str = ""        # 受管 connector 的工作目录
    resource_url: str = ""          # 受管 browser connector 的目标地址
    ide_bridge_url: str = ""        # 受管 IDE extension/native-host bridge 地址
    ide_chat_adapter: str = ""      # IDE bridge chat adapter, e.g. cursor/copilot/codex
    command_operation: str = ""
    command_argv: list[str] = dataclasses.field(default_factory=list)
    command_args: list[str] = dataclasses.field(default_factory=list)
    command_effects: list[str] = dataclasses.field(default_factory=list)
    command_profile: str = ""
    command_timeout_sec: float = 60.0
    command_audit_log_path: str = ""
    command_require_owned_session: bool = False
    command_run_mode: str = ""
    command_process_storage_path: str = ""

    # ── 运行时（不写入配置）──
    status: GoalStatus = GoalStatus.PENDING
    retry_count: int = 0
    last_action_time: float = 0
    last_status_change: float = 0
    matched_pid: int = 0
    matched_window_title: str = ""
    active_connector: str = ""
    task_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4())[:8])
    workspace_id: str = ""
    workspace_label: str = ""
    active_session_id: str = ""
    last_action_id: str = ""
    last_match_time: float = 0
    match_fail_notified: bool = False
    lifecycle: list[dict] = dataclasses.field(default_factory=list)

    def emit(self, event: LifecycleEvent, detail: str = ""):
        """记录生命周期事件"""
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "event": event.value,
            "detail": detail,
            "id": str(uuid.uuid4())[:8],  # 幂等键
        }
        self.lifecycle.append(entry)
        if len(self.lifecycle) > 200:
            self.lifecycle = self.lifecycle[-100:]

    @property
    def last_event(self) -> str:
        if not self.lifecycle:
            return ""
        e = self.lifecycle[-1]
        return f"[{e['ts']}] {e['event']}: {e['detail']}"


# ═══════════════════════════════════════════════
#  Chat 操作（Steer 层）
# ═══════════════════════════════════════════════

class SteerOperator:
    """
    IDE AI Chat 面板操作

    命名灵感来自 OpenClaw 的 steer 机制：
    向 Agent 注入新指令，带速率限制和幂等保护。
    """

    # Chat 输入框特征词（覆盖主流 IDE）
    _CHAT_HINTS = [
        "ask", "message", "chat", "prompt", "type",
        "send", "input", "agent", "copilot", "cline",
        "ask anything", "type a message", "compose",
        "write", "query", "instruction",
    ]
    _EXCLUDE_HINTS = [
        "search", "filter", "find", "terminal",
        "grep", "replace", "rename", "breadcrumb",
        "address", "url", "path", "filename",
    ]

    # AutomationId 特征词（比 name 更稳定）
    _AUTOMATION_ID_HINTS = [
        "chat", "input", "prompt", "message",
        "composer", "agent", "ask",
    ]

    # 可接受的输入控件类型（扩大范围）
    _INPUT_CONTROL_TYPES = {
        "Edit", "RichEdit", "RichEdit20W", "TextBox",
        "Document", "ComboBox",
    }

    # 速率限制追踪（借鉴 OpenClaw STEER_RATE_LIMIT_MS）
    _last_steer: dict[int, float] = {}

    _SEND_HINTS = ["send", "submit", "发送", "提交"]
    _SEND_EXCLUDE_HINTS = ["feedback", "issue", "share", "settings"]
    _last_steer: dict[str, float] = {}

    @staticmethod
    def _window_key(window_title: str) -> str:
        return (window_title or "").strip().lower()

    @classmethod
    def _scope_key(cls, pid: int, preferred_window_title: str = "") -> str:
        title_key = cls._window_key(preferred_window_title)
        return f"{pid}:{title_key}" if title_key else str(pid)

    @classmethod
    def _ordered_windows(
        cls,
        app: Application,
        preferred_window_title: str = "",
    ) -> list[object]:
        try:
            windows = list(app.windows())
        except Exception:
            return []

        visible_windows: list[tuple[str, object]] = []
        for win in windows:
            try:
                title = win.window_text() or ""
            except Exception:
                continue
            if not title or "Program Manager" in title:
                continue
            visible_windows.append((title, win))

        if not preferred_window_title:
            return [win for _, win in visible_windows]

        preferred = cls._window_key(preferred_window_title)
        preferred_head = preferred.split(" - ")[0].strip()

        exact: list[object] = []
        partial: list[object] = []
        fallback: list[object] = []

        for title, win in visible_windows:
            lowered = title.lower()
            if lowered == preferred:
                exact.append(win)
            elif preferred and (preferred in lowered or lowered in preferred):
                partial.append(win)
            elif preferred_head and preferred_head in lowered:
                partial.append(win)
            else:
                fallback.append(win)

        return exact + partial + fallback

    @classmethod
    def _is_probably_writable(cls, wrapper: object) -> bool:
        try:
            if hasattr(wrapper, "is_enabled") and not wrapper.is_enabled():
                return False
        except Exception:
            pass

        try:
            control_type = wrapper.element_info.control_type or ""
        except Exception:
            control_type = ""

        if control_type in ("Edit", "RichEdit", "RichEdit20W", "TextBox", "ComboBox"):
            return True

        try:
            is_read_only = wrapper.get_value_pattern_attribute("IsReadOnly")
            if is_read_only is not None:
                return not bool(is_read_only)
        except Exception:
            pass

        return control_type == "Document"

    @classmethod
    def _score_input_candidate(cls, wrapper: object, win: object) -> int:
        try:
            control_type = wrapper.element_info.control_type or ""
        except Exception:
            control_type = ""

        try:
            name = (wrapper.element_info.name or "").lower()
        except Exception:
            name = ""

        try:
            automation_id = (wrapper.element_info.automation_id or "").lower()
        except Exception:
            automation_id = ""

        if any(kw in name for kw in cls._EXCLUDE_HINTS):
            return -1
        if any(kw in automation_id for kw in cls._EXCLUDE_HINTS):
            return -1

        score = 0
        if control_type in ("Edit", "RichEdit", "RichEdit20W", "TextBox"):
            score += 90
        elif control_type == "Document":
            score += 55
        elif control_type == "ComboBox":
            score += 35

        if automation_id and any(kw in automation_id for kw in cls._AUTOMATION_ID_HINTS):
            score += 120

        if any(kw in name for kw in cls._CHAT_HINTS):
            score += 90

        if not name.strip():
            score += 20

        if cls._is_probably_writable(wrapper):
            score += 40

        try:
            rect = wrapper.rectangle()
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            score += min(width // 40, 25)
            if 20 <= height <= 200:
                score += 20

            try:
                win_rect = win.rectangle()
                win_mid_y = win_rect.top + ((win_rect.bottom - win_rect.top) // 2)
                if rect.top >= win_mid_y:
                    score += 25
                if rect.bottom >= win_rect.bottom - 220:
                    score += 20
            except Exception:
                pass
        except Exception:
            pass

        return score

    @staticmethod
    def _copy_to_clipboard(text: str) -> tuple[bool, str]:
        try:
            import pyperclip

            pyperclip.copy(text)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _focus_window(win: object):
        try:
            win.set_focus()
            time.sleep(0.05)
        except Exception:
            pass

    @staticmethod
    def _focus_input(wrapper: object):
        try:
            wrapper.set_focus()
            time.sleep(0.03)
        except Exception:
            pass

        try:
            wrapper.click_input()
            time.sleep(0.05)
        except Exception:
            pass

    @classmethod
    def _clear_input(cls, wrapper: object):
        try:
            wrapper.set_edit_text("")
            return
        except Exception:
            pass

        for clear_action in (
            lambda: send_keys("^a{BACKSPACE}", pause=0.02),
            lambda: wrapper.type_keys("^a{BACKSPACE}", set_foreground=True, pause=0.02),
        ):
            try:
                clear_action()
                return
            except Exception:
                continue

    @classmethod
    def _inject_message(cls, wrapper: object, message: str) -> tuple[bool, str]:
        attempts: list[tuple[str, Callable[[], None]]] = []

        if cls._is_probably_writable(wrapper):
            attempts.append(("set_edit_text", lambda: wrapper.set_edit_text(message)))

        clipboard_ready, clipboard_error = cls._copy_to_clipboard(message)
        if clipboard_ready:
            attempts.extend(
                [
                    ("global_paste", lambda: send_keys("^v", pause=0.02)),
                    ("wrapper_paste", lambda: wrapper.type_keys("^v", set_foreground=True, pause=0.02)),
                ]
            )

        attempts.extend(
            [
                ("global_type", lambda: send_keys(message, with_spaces=True, pause=0.01)),
                ("wrapper_type", lambda: wrapper.type_keys(message, with_spaces=True, set_foreground=True, pause=0.01)),
            ]
        )

        errors = []
        if not clipboard_ready and clipboard_error:
            errors.append(f"clipboard: {clipboard_error}")

        for attempt_name, attempt in attempts:
            try:
                attempt()
                return True, attempt_name
            except Exception as exc:
                errors.append(f"{attempt_name}: {exc}")

        return False, "; ".join(errors[-4:])

    @classmethod
    def _find_send_button(
        cls,
        app: Application,
        preferred_window_title: str = "",
    ) -> Optional[object]:
        best_wrapper = None
        best_score = -1

        for win in cls._ordered_windows(app, preferred_window_title):
            try:
                for button in win.descendants(control_type="Button"):
                    try:
                        name = (button.element_info.name or "").lower()
                        automation_id = (button.element_info.automation_id or "").lower()
                        if not (
                            any(hint in name for hint in cls._SEND_HINTS)
                            or any(hint in automation_id for hint in cls._SEND_HINTS)
                        ):
                            continue
                        if any(hint in name for hint in cls._SEND_EXCLUDE_HINTS):
                            continue
                        if any(hint in automation_id for hint in cls._SEND_EXCLUDE_HINTS):
                            continue

                        score = 100
                        try:
                            rect = button.rectangle()
                            win_rect = win.rectangle()
                            if rect.bottom >= win_rect.bottom - 220:
                                score += 20
                            if rect.right >= win_rect.right - 260:
                                score += 20
                        except Exception:
                            pass

                        if score > best_score:
                            best_score = score
                            best_wrapper = button
                    except Exception:
                        continue
            except Exception:
                continue

        return best_wrapper

    @classmethod
    def _submit_message(
        cls,
        app: Application,
        chat_input: object,
        preferred_window_title: str = "",
    ) -> tuple[bool, str]:
        send_button = cls._find_send_button(app, preferred_window_title)
        if send_button is not None:
            try:
                send_button.click_input()
                return True, "button_click"
            except Exception:
                pass

        for submit_name, submit_action in (
            ("global_enter", lambda: send_keys("{ENTER}", pause=0.02)),
            ("wrapper_enter", lambda: chat_input.type_keys("{ENTER}", set_foreground=True, pause=0.02)),
        ):
            try:
                submit_action()
                return True, submit_name
            except Exception:
                continue

        return False, ""

    @classmethod
    def find_chat_input(
        cls,
        app: Application,
        preferred_window_title: str = "",
    ) -> Optional[object]:
        """
        定位 IDE 窗口中的 AI Chat 输入框

        三层探测策略:
          1. AutomationId 精确匹配（最稳定）
          2. 控件名称关键词匹配（覆盖面广）
          3. 尺寸启发式匹配（兜底方案）
        """
        all_diagnostics = []  # 用于调试输出

        best_candidate = None
        best_score = -1

        for win in cls._ordered_windows(app, preferred_window_title):
            try:
                wt = win.window_text() or ""
                window_best = None
                window_best_score = -1
                window_candidates = 0

                for d in win.descendants():
                    try:
                        ct = d.element_info.control_type or ""
                        if ct not in cls._INPUT_CONTROL_TYPES:
                            continue

                        score = cls._score_input_candidate(d, win)
                        if score < 0:
                            continue

                        window_candidates += 1
                        if score > window_best_score:
                            window_best_score = score
                            window_best = d
                    except Exception:
                        continue

                if window_best is not None:
                    all_diagnostics.append(
                        f"Window '{wt[:50]}': candidates={window_candidates}, best_score={window_best_score}"
                    )
                    if window_best_score > best_score:
                        best_score = window_best_score
                        best_candidate = window_best
                else:
                    all_diagnostics.append(f"Window '{wt[:50]}': candidates=0")
            except Exception:
                continue

        if best_candidate is not None:
            log_event(
                logger,
                (
                    f"Chat输入框定位成功: score={best_score}, "
                    f"title={preferred_window_title or '(auto)'}"
                ),
                event_type="steer_input_found",
            )
            return best_candidate

        if all_diagnostics:
            log_event(
                logger,
                f"Chat输入框未找到。诊断: {'; '.join(all_diagnostics)}",
                event_type="steer_no_input",
                level=30,
            )
        else:
            log_event(logger, "Chat输入框未找到: 无可用窗口", event_type="steer_no_input", level=30)

        return None

        for win in app.windows():
            try:
                wt = win.window_text() or ""
                if not wt or "Program Manager" in wt:
                    continue

                candidates_by_id = []       # AutomationId 匹配
                candidates_by_name = []     # 名称关键词匹配
                candidates_by_heuristic = []  # 尺寸启发式匹配

                for d in win.descendants():
                    try:
                        ct = d.element_info.control_type or ""
                        if ct not in cls._INPUT_CONTROL_TYPES:
                            continue

                        name = (d.element_info.name or "").lower()
                        automation_id = (d.element_info.automation_id or "").lower()

                        # 排除干扰控件
                        if any(kw in name for kw in cls._EXCLUDE_HINTS):
                            continue
                        if any(kw in automation_id for kw in cls._EXCLUDE_HINTS):
                            continue

                        # === 策略1: AutomationId 匹配 ===
                        if automation_id and any(
                            kw in automation_id for kw in cls._AUTOMATION_ID_HINTS
                        ):
                            candidates_by_id.append(d)
                            continue

                        # === 策略2: 名称关键词匹配 ===
                        if any(kw in name for kw in cls._CHAT_HINTS):
                            candidates_by_name.append(d)
                            continue

                        # === 策略3: 无名称的可编辑控件（尺寸启发式）===
                        if name.strip() == "" or ct in ("Edit", "RichEdit"):
                            try:
                                rect = d.rectangle()
                                width = rect.right - rect.left
                                height = rect.bottom - rect.top
                                # Chat 输入框通常宽度 > 200px，高度 20-300px
                                if width > 200 and 20 <= height <= 300:
                                    candidates_by_heuristic.append(d)
                            except Exception:
                                # 无法获取尺寸，仍作为候选
                                candidates_by_heuristic.append(d)

                    except Exception:
                        continue

                # 按优先级返回（ID > 名称 > 启发式）
                if candidates_by_id:
                    result = candidates_by_id[-1]
                    try:
                        log_event(logger, f"Chat输入框定位成功(AutomationId): {result.element_info.automation_id}",
                                  event_type="steer_input_found")
                    except Exception:
                        log_event(logger, "Chat输入框定位成功(AutomationId)", event_type="steer_input_found")
                    return result

                if candidates_by_name:
                    result = candidates_by_name[-1]
                    try:
                        log_event(logger, f"Chat输入框定位成功(Name): {result.element_info.name}",
                                  event_type="steer_input_found")
                    except Exception:
                        log_event(logger, "Chat输入框定位成功(Name)", event_type="steer_input_found")
                    return result

                if candidates_by_heuristic:
                    result = candidates_by_heuristic[-1]
                    try:
                        log_event(logger, f"Chat输入框定位成功(Heuristic): ct={result.element_info.control_type}",
                                  event_type="steer_input_found")
                    except Exception:
                        log_event(logger, "Chat输入框定位成功(Heuristic)", event_type="steer_input_found")
                    return result

                # 记录诊断信息
                all_diagnostics.append(
                    f"Window '{wt[:50]}': "
                    f"id={len(candidates_by_id)}, name={len(candidates_by_name)}, "
                    f"heuristic={len(candidates_by_heuristic)}"
                )

            except Exception:
                continue

        # 所有窗口都没找到，输出诊断日志
        if all_diagnostics:
            log_event(
                logger,
                f"Chat输入框未找到。诊断: {'; '.join(all_diagnostics)}",
                event_type="steer_no_input",
                level=30,
            )
        else:
            log_event(logger, "Chat输入框未找到: 无可用窗口", event_type="steer_no_input", level=30)

        return None

    @classmethod
    def steer(
        cls,
        app: Application,
        message: str,
        pid: int,
        cooldown: float = 10.0,
        preferred_window_title: str = "",
    ) -> tuple[bool, str]:
        """
        向 Agent 发送续跑指令（steer）

        Returns: (success, idempotency_key)
        """
        # 速率限制
        scope_key = cls._scope_key(pid, preferred_window_title)
        now = time.time()
        last = cls._last_steer.get(scope_key, 0)
        if now - last < cooldown:
            return False, ""

        ordered_windows = cls._ordered_windows(app, preferred_window_title)
        if ordered_windows:
            cls._focus_window(ordered_windows[0])

        chat_input = cls.find_chat_input(app, preferred_window_title)
        if not chat_input:
            log_event(
                logger,
                f"PID={pid}: Chat 输入框未找到 title={preferred_window_title or '(auto)'}",
                event_type="steer_no_input",
            )
            return False, ""

        idempotency_key = str(uuid.uuid4())[:8]

        try:
            cls._focus_input(chat_input)
            cls._clear_input(chat_input)

            injected, injection_method = cls._inject_message(chat_input, message)
            if not injected:
                raise RuntimeError("message injection failed")

            time.sleep(0.1)

            submitted, submit_method = cls._submit_message(
                app, chat_input, preferred_window_title
            )
            if not submitted:
                raise RuntimeError("message submit failed")

            cls._last_steer[scope_key] = now

            log_event(
                logger,
                (
                    f"PID={pid}: steer #{idempotency_key} ({len(message)} chars) "
                    f"[inject={injection_method}, submit={submit_method}]"
                ),
                event_type="steer_sent",
                event_data={
                    "key": idempotency_key,
                    "preview": message[:80],
                    "window_title": preferred_window_title,
                    "inject_method": injection_method,
                    "submit_method": submit_method,
                },
            )
            return True, idempotency_key
        except Exception as exc:
            log_event(
                logger,
                f"PID={pid}: steer 失败 - {exc}",
                event_type="steer_failed",
                event_data={"window_title": preferred_window_title},
            )
            return False, ""

        now = time.time()
        last = cls._last_steer.get(pid, 0)
        if now - last < cooldown:
            return False, ""

        chat_input = cls.find_chat_input(app)
        if not chat_input:
            log_event(logger, f"PID={pid}: Chat 输入框未找到",
                      event_type="steer_no_input")
            return False, ""

        idempotency_key = str(uuid.uuid4())[:8]

        try:
            # 必须前置窗口并物理输入
            chat_input.click_input()
            chat_input.type_keys("^a{DELETE}", set_foreground=True)
            time.sleep(0.05)

            # 使用剪贴板避免庞大或者带特殊符号的内容引发 pywinauto 转义崩溃
            import pyperclip
            pyperclip.copy(message)
            time.sleep(0.05)

            chat_input.type_keys("^v", set_foreground=True)
            time.sleep(0.1)

            # 发送回车
            chat_input.type_keys("{ENTER}", set_foreground=True)

            cls._last_steer[pid] = now

            log_event(
                logger,
                f"PID={pid}: steer #{idempotency_key} ({len(message)} chars)",
                event_type="steer_sent",
                event_data={"key": idempotency_key, "preview": message[:80]},
            )
            return True, idempotency_key

        except Exception as e:
            log_event(logger, f"PID={pid}: steer 失败 - {e}",
                      event_type="steer_failed")
            return False, ""

    @staticmethod
    def read_conversation(app: Application, preferred_window_title: str = "") -> str:
        """读取 AI 对话面板最近内容"""
        texts = []
        for win in SteerOperator._ordered_windows(app, preferred_window_title)[:3]:
            try:
                wt = win.window_text() or ""
                if not wt or "Program Manager" in wt:
                    continue
                for d in win.descendants():
                    try:
                        ct = d.element_info.control_type or ""
                        if ct not in ("Text", "Document", "Edit"):
                            continue
                        try:
                            content = d.window_text() or ""
                        except Exception:
                            content = (d.element_info.name or "").strip()
                        if len(content) > 8 and content != wt:
                            texts.append(content[:500])
                    except Exception:
                        continue
            except Exception:
                continue

        return "\n".join(texts[-25:])

        for win in app.windows()[:3]:
            try:
                wt = win.window_text() or ""
                if not wt or "Program Manager" in wt:
                    continue
                for d in win.descendants():
                    try:
                        ct = d.element_info.control_type or ""
                        if ct not in ("Text", "Document", "Edit"):
                            continue
                        content = ""
                        try:
                            content = d.window_text() or ""
                        except Exception:
                            content = (d.element_info.name or "").strip()
                        # 降低最小长度阈值(8)以捕获短信号如 "passed"/"FAILED"/"ASR: 0.9"
                        if len(content) > 8 and content != wt:
                            texts.append(content[:500])
                    except Exception:
                        continue
            except Exception:
                continue
        # 保留更多历史条目(25)以覆盖复杂对话中的关键信号
        return "\n".join(texts[-25:])


# ═══════════════════════════════════════════════
#  督导器核心
# ═══════════════════════════════════════════════

class AgentSupervisor:
    """
    通用 IDE Agent 全时督导器

    状态机 + 生命周期事件驱动：
    PENDING → RUNNING → CHECKING → RUNNING/ACHIEVED/FAILED
                 ↕             ↕
              STALLED      (steer)
    """

    def __init__(
        self,
        goals: list[TaskGoal],
        on_tick_callback: Optional[Callable] = None,
    ):
        self.goals = goals
        self.monitor = MultiProjectAIMonitor()
        self.identity_model = WorkspaceIdentityModel()
        self.connector_manager = ConnectorManager([
            BrowserSessionConnector(),
            GitCommandConnector(),
            TerminalCommandConnector(),
            IDEExtensionConnector(),
            CodexDesktopConnector(),
            CursorIDEConnector(),
            CopilotIDEConnector(),
            UIAIDEConnector(),
        ])
        self._prev_states: dict[tuple[int, str], AIStatus] = {}
        self._total_steers = 0
        self._total_events = 0
        self._on_tick = on_tick_callback
        self._start_time: float = 0
        self._stop_event: Optional[object] = None  # threading.Event 由外部注入
        self._latest_states: list[AIProjectState] = []
        self._recent_actions: list[ActionRecord] = []
        self._identity_snapshot = self.identity_model.build_snapshot(self.goals, [], [])

        for goal in self.goals:
            self._refresh_goal_identity(goal)

        # 加载全智能的战略皮层
        from openwukong.supervisor.strategic_cortex import StrategicCortex
        self.cortex = StrategicCortex(model="qwen3.5:9b")


        # 集成看门狗：只监控本进程内存 (默认限制 1024MB = 1GB)，一旦超限或连续报错则完全重置
        self._watchdog = Watchdog(
            max_memory_mb=1024.0,
            max_consecutive_errors=15,
            on_full_reset=self._perform_full_reset,
        )

    def _perform_full_reset(self):
        """执行完整重置，回收内存并重建 UIA 监控树"""
        import gc
        log_event(logger, "AgentSupervisor triggered FULL RESET due to memory/error limits", level=30)
        self.monitor = MultiProjectAIMonitor()  # 重新建立 UIA 入口
        gc.collect()  # 强制垃圾回收
        if getattr(self, "run_logger", None):
            self.run_logger.record_event("full_reset", {"reason": "memory/error limits"})

    def _refresh_goal_identity(self, goal: TaskGoal):
        task_ref = self.identity_model.task_for_goal(goal)
        goal.workspace_id = task_ref.workspace_id
        goal.workspace_label = task_ref.workspace_name

    def _refresh_identity_snapshot(self, states: Optional[list[AIProjectState]] = None):
        if states is not None:
            self._latest_states = list(states)
        self._identity_snapshot = self.identity_model.build_snapshot(
            self.goals,
            self._latest_states,
            self._recent_actions[-50:],
        )

    def _record_action(
        self,
        *,
        goal: TaskGoal,
        session_id: str,
        connector_id: str,
        action_type: str,
        status: str,
        detail: str,
    ):
        self._refresh_goal_identity(goal)
        record = self.identity_model.create_action_record(
            task_id=goal.task_id,
            workspace_id=goal.workspace_id,
            session_id=session_id,
            connector_id=connector_id,
            action_type=action_type,
            status=status,
            detail=detail,
        )
        goal.last_action_id = record.action_id
        self._recent_actions.append(record)
        if len(self._recent_actions) > 200:
            self._recent_actions = self._recent_actions[-120:]
        self._refresh_identity_snapshot()

    def _build_connector_target(
        self,
        goal: TaskGoal,
        pid: int,
        window_title: str = "",
        process_name: str = "",
        project_name: str = "",
    ) -> ConnectorTarget:
        if not process_name and pid:
            try:
                process_name = psutil.Process(pid).name()
            except Exception:
                process_name = ""

        self._refresh_goal_identity(goal)
        return ConnectorTarget(
            workspace_id=goal.workspace_id,
            session_id=goal.active_session_id,
            pid=pid,
            process_name=process_name,
            window_title=window_title or goal.matched_window_title,
            project_name=project_name or goal.window_match,
            workspace_hint=goal.window_match,
            workspace_path=goal.workspace_path,
            resource_url=goal.resource_url,
            ide_bridge_url=goal.ide_bridge_url,
        )

    def _resolve_session_connector(
        self,
        goal: TaskGoal,
        target: ConnectorTarget,
        enforce_route_policy: bool = False,
    ):
        connector = self.connector_manager.resolve_session_connector(
            target,
            preferred=goal.connector_hint,
            enforce_route_policy=enforce_route_policy,
        )
        goal.active_connector = connector.connector_id
        session_ref = self.identity_model.session_for_target(target, connector.connector_id)
        goal.active_session_id = session_ref.session_id
        return connector

    @staticmethod
    def _format_ide_chat_command(adapter_id: str, message: str) -> str:
        adapter = (adapter_id or "").strip()
        content = (message or "").strip()
        if not adapter or not content:
            return message
        if content.upper().startswith("IDE CHAT "):
            return content
        return f"IDE CHAT {adapter}\n\n{content}"

    @staticmethod
    def _is_direct_connector_goal(goal: TaskGoal) -> bool:
        return (goal.connector_hint or "").strip().lower() in {
            "terminal",
            "git",
            "browser",
            "ide-extension",
        }

    def _run_direct_connector_goal(self, goal: TaskGoal, dry_run: bool):
        self._refresh_goal_identity(goal)
        connector_hint = (goal.connector_hint or "").strip().lower()
        process_name = "powershell.exe"
        if connector_hint == "git":
            process_name = "git.exe"
        elif connector_hint == "browser":
            process_name = "browser.exe"
        elif connector_hint == "ide-extension":
            process_name = "code.exe"
        target = self._build_connector_target(
            goal,
            pid=0,
            window_title=goal.resource_url or goal.workspace_path or goal.ide_bridge_url or goal.window_match,
            process_name=process_name,
            project_name=goal.task_name,
        )
        try:
            connector = self._resolve_session_connector(
                goal,
                target,
                enforce_route_policy=not dry_run,
            )
        except PermissionError as exc:
            goal.status = GoalStatus.FAILED
            detail = str(exc)
            goal.emit(LifecycleEvent.ERROR, detail[:160])
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=goal.active_connector or goal.connector_hint,
                action_type="send_message",
                status="blocked",
                detail=detail[:200],
            )
            self._total_events += 1
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_blocked_by_route_policy", {
                    "goal_name": goal.task_name,
                    "pid": target.pid,
                    "process": target.process_name,
                    "window_title": target.window_title,
                    "error": detail,
                })
            return
        self._record_action(
            goal=goal,
            session_id=goal.active_session_id,
            connector_id=connector.connector_id,
            action_type="bind_direct_session",
            status="ready",
            detail=target.window_title or target.project_name or goal.task_name,
        )

        if goal.status == GoalStatus.PENDING:
            goal.status = GoalStatus.CHECKING
            goal.last_status_change = time.time()
            goal.emit(
                LifecycleEvent.SPAWNED,
                f"Direct connector ready: {connector.connector_id}",
            )
            self._total_events += 1
        elif goal.status in (GoalStatus.RUNNING, GoalStatus.STALLED):
            goal.status = GoalStatus.CHECKING
            goal.last_status_change = time.time()
            goal.emit(
                LifecycleEvent.COMPLETED,
                f"Connector step completed, checking [{connector.connector_id}]",
            )
            self._total_events += 1

        self._smart_evaluate(
            goal,
            target.pid,
            dry_run,
            target.window_title,
            target.process_name,
            target.project_name,
        )

    def run(
        self,
        interval: float = 5.0,
        dry_run: bool = False,
        max_hours: float = 24.0,
    ):
        """启动督导循环"""
        # 初始化日志器
        self.run_logger = RunLogger(run_mode="demo" if dry_run else "auto")
        self.run_logger.set_goals([
            {"task_name": g.task_name, "window_match": g.window_match, "goal": g.goal}
            for g in self.goals
        ])

        start_time = time.time()
        self._start_time = start_time
        max_seconds = max_hours * 3600

        self.run_logger.record_event("supervisor_start", {
            "dry_run": dry_run,
            "max_hours": max_hours,
            "goal_count": len(self.goals)
        })

        print("=" * 60)
        print("  🤖 Agent Supervisor — IDE 全时督导")
        print(f"  {len(self.goals)} 个任务目标")
        print(f"  模式: {'🔍 只读演示' if dry_run else '⚡ 自动督导'}")
        print(f"  最长运行: {max_hours}h")
        print("=" * 60)
        for g in self.goals:
            print(f"  📌 [{g.window_match}] {g.task_name}")
            print(f"     目标: {g.goal}")
        print()

        try:
            while True:
                try:
                    # 外部停止信号
                    if self._stop_event and self._stop_event.is_set():
                        print("\n  🛑 收到停止信号")
                        break

                    elapsed = time.time() - start_time
                    if elapsed > max_seconds:
                        print(f"\n  ⏰ 已达最大运行时间 ({max_hours}h)")
                        break

                    if all(g.status in (GoalStatus.ACHIEVED, GoalStatus.FAILED)
                           for g in self.goals):
                        achieved = sum(1 for g in self.goals
                                       if g.status == GoalStatus.ACHIEVED)
                        print(f"\n  🏁 全部任务处理完毕 "
                              f"({achieved}/{len(self.goals)} 达标)")
                        break

                    # ── 混合扫描：快速发现 + 定向深探 ──
                    # Phase 1: 快速扫描所有窗口（~300ms，仅获取 PID/Title）
                    states = self.monitor.scan_windows_fast()
                    self._refresh_identity_snapshot(states)

                    for goal in self.goals:
                        if goal.status in (GoalStatus.ACHIEVED, GoalStatus.FAILED):
                            continue
                        if self._is_direct_connector_goal(goal):
                            self._run_direct_connector_goal(goal, dry_run)
                            continue
                        # Phase 2: 匹配目标窗口
                        matched = self._match_window(goal, states)
                        if matched:
                            # Phase 3: 仅对匹配窗口做深度 UIA 探测（获取真实 ai_status）
                            # 传入 matched.window_title 确保深探使用正确的项目窗口
                            deep_state = self.monitor.probe_single(matched.pid, matched.window_title)
                            if deep_state:
                                self._tick(goal, deep_state, dry_run)
                            else:
                                # 深探失败（窗口消失/COM超时），用快速状态兜底
                                self._tick(goal, matched, dry_run)

                    self._dashboard(states, elapsed)

                    # 触发健康检查 (如有异常会通过回调执行 _perform_full_reset)
                    self._watchdog.check()
                    self._watchdog.record_success()

                    if self._stop_event:
                        if self._stop_event.wait(interval):
                            print("\n  🛑 收到停止信号")
                            break
                    else:
                        time.sleep(interval)

                except Exception as e:
                    self._watchdog.record_error()
                    # 全局防崩兜底：即使出现 WMI/COM 意外报错，也能继续运行
                    log_event(logger, f"AgentSupervisor loop error: {e}", level=40, exc_info=True)
                    print(f"\n  ⚠️ 督导底层异常: {e}")
                    if self._stop_event:
                        if self._stop_event.wait(min(interval, 5.0)):
                            break
                    else:
                        time.sleep(min(interval, 5.0))  # 防止疯狂报错刷屏

        except KeyboardInterrupt:
            print("\n  督导已停止。")
        finally:
            if getattr(self, "run_logger", None):
                elapsed = time.time() - self._start_time
                self.run_logger.end_run("stopped", summary={
                    "total_steers": self._total_steers,
                    "total_events": self._total_events,
                    "elapsed_sec": round(elapsed, 1),
                    "achieved": sum(1 for g in self.goals if g.status.value == "achieved")
                })

        self._report()

    # ── 窗口匹配 ──

    def _match_window(
        self, goal: TaskGoal, states: list[AIProjectState]
    ) -> Optional[AIProjectState]:
        self._refresh_goal_identity(goal)
        kw = goal.window_match.lower()
        if not kw:
            return None

        # ═══ 构建搜索词集合（别名完全展开）═══
        search_terms = set()
        search_terms.add(kw)

        # 正向：用户关键词 → 可能的标识符
        for alias, target in PROJECT_ALIASES.items():
            if alias in kw or kw in alias:
                search_terms.add(target)
                search_terms.add(alias)
            if target in kw or kw in target:
                search_terms.add(target)
                search_terms.add(alias)

        # 反向：如果关键词本身是标识符，展开其所有别名
        if kw in PROJECT_ALIAS_REVERSE:
            for alias in PROJECT_ALIAS_REVERSE[kw]:
                search_terms.add(alias)

        # 去掉太短的词（< 2 字符容易误匹配），但不清空原始词
        filtered_terms = {t for t in search_terms if len(t) >= 2}
        if not filtered_terms and kw:
            # 如果过滤后为空（比如用户只输入了 "1"），保留原始关键词，否则匹配必然失败
            search_terms = {kw}
            log_event(logger, f"⚠️  过滤后搜索词为空，保留原始匹配词: '{kw}'", level=30)
        else:
            search_terms = filtered_terms

        log_event(logger, f"🔍 正在匹配窗口: goal={goal.task_name}, search_terms={sorted(search_terms)}")
        if getattr(self, "run_logger", None) and (not goal.last_match_time or time.time() - goal.last_match_time > 15):
            # 只有初次或者间隔较长时才详细记录，避免日志爆炸
            self.run_logger.record_event("match_window_scan", {
                "goal_name": goal.task_name,
                "window_match": kw,
                "search_terms_used": list(search_terms),
                "active_windows_scanned": len(states)
            })

        # ═══ 如果 states 为空，尝试快速扫描补救 ═══
        if not states:
            try:
                fast_states = self.monitor.scan_windows_fast()
                if fast_states:
                    states = fast_states
                    log_event(logger, f"⚡ 快速扫描补救: 发现 {len(states)} 个窗口")
            except Exception:
                pass

        # ═══ 排除督导系统自身的面板 ═══
        safe_states = []
        for s in states:
            lower_title = s.window_title.lower()
            if "wukong task supervisor" in lower_title or "悟空" in lower_title or "supervisor ui" in lower_title:
                continue
            safe_states.append(s)
        states = safe_states

        workspace_match, workspace_session, workspace_score = (
            self.identity_model.bind_workspace_state_to_goal(goal, states)
        )
        if workspace_match is not None and workspace_session is not None:
            if goal.matched_pid != workspace_match.pid:
                log_event(
                    logger,
                    (
                        f"🧭 Workspace match: goal='{goal.task_name}', "
                        f"workspace='{goal.workspace_label or goal.workspace_id}', "
                        f"project='{workspace_match.project_name}', pid={workspace_match.pid}, "
                        f"connector={workspace_session.connector_id}, score={workspace_score}"
                    ),
                    level=20,
                )
                goal.emit(
                    LifecycleEvent.MATCH_SUCCESS,
                    f"Workspace绑定: {goal.workspace_label or goal.workspace_id} -> {workspace_match.project_name}"
                )
                self._record_action(
                    goal=goal,
                    session_id=workspace_session.session_id,
                    connector_id=workspace_session.connector_id,
                    action_type="match_session",
                    status="bound",
                    detail=f"{workspace_match.project_name} (PID:{workspace_match.pid})",
                )
                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("match_success", {
                        "layer": "workspace_identity",
                        "workspace_id": goal.workspace_id,
                        "workspace_name": goal.workspace_label,
                        "project": workspace_match.project_name,
                        "pid": workspace_match.pid,
                        "goal_name": goal.task_name,
                        "connector": workspace_session.connector_id,
                    })
            goal.matched_pid = workspace_match.pid
            goal.matched_window_title = workspace_match.window_title
            goal.active_session_id = workspace_session.session_id
            return workspace_match

        # ═══ Layer 1: 精确子串匹配（最快路径）═══
        for s in states:
            p_name = s.project_name.lower()
            w_title = s.window_title.lower()

            for term in search_terms:
                if term in p_name or term in w_title:
                    if goal.matched_pid != s.pid:
                        log_event(logger, f"✅ L1精确匹配成功: term='{term}', project='{s.project_name}', pid={s.pid}")
                        goal.emit(LifecycleEvent.MATCH_SUCCESS, f"匹配到项目: {s.project_name} (PID:{s.pid})")
                        if getattr(self, "run_logger", None):
                            self.run_logger.record_event("match_success", {
                                "layer": "L1_exact", "term": term,
                                "project": s.project_name, "pid": s.pid,
                                "goal_name": goal.task_name,
                            })
                    goal.matched_pid = s.pid
                    goal.matched_window_title = s.window_title
                    goal.last_match_time = time.time()
                    goal.match_fail_notified = False
                    return s

        # ═══ Layer 2: 路径感知匹配（从窗口标题中的路径提取项目名）═══
        for s in states:
            w_title = s.window_title
            # 提取窗口标题中可能包含的文件路径
            path_parts = self._extract_path_components(w_title)
            for term in search_terms:
                for path_part in path_parts:
                    # 精确相等 或 长词包含短词（短词至少 3 字符，防止 "src" 匹配一切）
                    matched = False
                    if term == path_part:
                        matched = True
                    elif len(term) >= 3 and term in path_part:
                        matched = True
                    elif len(path_part) >= 3 and path_part in term:
                        matched = True

                    if matched:
                        if goal.matched_pid != s.pid:
                            log_event(logger, f"✅ L2路径匹配成功: term='{term}', path_part='{path_part}', pid={s.pid}")
                            goal.emit(LifecycleEvent.MATCH_SUCCESS, f"路径匹配到: {s.project_name} (PID:{s.pid})")
                            if getattr(self, "run_logger", None):
                                self.run_logger.record_event("match_success", {
                                    "layer": "L2_path", "term": term,
                                    "path_part": path_part,
                                    "project": s.project_name, "pid": s.pid,
                                    "goal_name": goal.task_name,
                                })
                        goal.matched_pid = s.pid
                        goal.matched_window_title = s.window_title
                        goal.last_match_time = time.time()
                        goal.match_fail_notified = False
                        return s

        # ═══ Layer 3: 模糊匹配（降低阈值，多字段比较）═══
        best_match = None
        highest_ratio = 0.0
        best_term = ""

        seen_names = [s.project_name for s in states]

        for s in states:
            p_name = s.project_name.lower()
            w_title = s.window_title.lower()
            path_parts = self._extract_path_components(s.window_title)

            for term in search_terms:
                # 对 project_name 匹配
                ratio_name = difflib.SequenceMatcher(None, term, p_name).ratio()
                # 对窗口标题匹配（通常比率较低因为标题很长）
                ratio_title = difflib.SequenceMatcher(None, term, w_title).ratio()
                # 对路径组件匹配（新增）
                ratio_path = 0.0
                for pp in path_parts:
                    r = difflib.SequenceMatcher(None, term, pp).ratio()
                    ratio_path = max(ratio_path, r)

                max_ratio = max(ratio_name, ratio_title, ratio_path)
                if max_ratio > highest_ratio:
                    highest_ratio = max_ratio
                    best_match = s
                    best_term = term

        # 降低阈值到 0.5（之前是 0.7，太严格了）
        if highest_ratio > 0.5 and best_match:
            if goal.matched_pid != best_match.pid:
                log_event(logger, f"✨ L3模糊匹配成功: '{best_term}' ~ '{best_match.project_name}' ({highest_ratio*100:.1f}%)", level=20)
                goal.emit(LifecycleEvent.MATCH_SUCCESS, f"模糊匹配到: {best_match.project_name} ({highest_ratio*100:.0f}%)")
                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("match_success", {
                        "layer": "L3_fuzzy", "term": best_term,
                        "project": best_match.project_name,
                        "ratio": round(highest_ratio, 3),
                        "pid": best_match.pid,
                        "goal_name": goal.task_name,
                    })
            goal.matched_pid = best_match.pid
            goal.matched_window_title = best_match.window_title
            goal.last_match_time = time.time()
            goal.match_fail_notified = False
            return best_match

        codex_states = [
            s for s in states
            if "codex" in (s.process_name or "").lower()
        ]
        if len(codex_states) == 1:
            fallback = codex_states[0]
            if goal.matched_pid != fallback.pid:
                log_event(
                    logger,
                    (
                        f"L4 Codex fallback match: goal='{goal.task_name}', "
                        f"window='{fallback.window_title}', pid={fallback.pid}"
                    ),
                    level=20,
                )
                goal.emit(
                    LifecycleEvent.MATCH_SUCCESS,
                    f"Codex fallback: {fallback.window_title or fallback.process_name}"
                )
                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("match_success", {
                        "layer": "L4_codex_fallback",
                        "project": fallback.project_name,
                        "window_title": fallback.window_title,
                        "pid": fallback.pid,
                        "goal_name": goal.task_name,
                    })
            goal.matched_pid = fallback.pid
            goal.matched_window_title = fallback.window_title
            goal.last_match_time = time.time()
            goal.match_fail_notified = False
            return fallback

        # ═══ 匹配失败后的提示逻辑 ═══
        if states and not goal.match_fail_notified:
            now = time.time()
            if goal.last_match_time == 0 or now - goal.last_match_time > 15:
                # 构建更详尽的诊断信息，帮助排错
                all_active = [f"{s.project_name}(PID:{s.pid})" for s in states]
                search_terms_str = ', '.join(sorted(search_terms))
                diagnostic = (
                    f"匹配失败 ❌\n"
                    f"目标: '{kw}' (解析词: {search_terms_str})\n"
                    f"活跃项目 ({len(states)}个): {', '.join(all_active)[:150]}...\n"
                    f"建议: 尝试输入更准确的项目名称，或在 IDE 中打开该项目后再重试。"
                )
                if best_match:
                    diagnostic += f"\n最接近的是 '{best_match.project_name}' (相似度: {highest_ratio*100:.1f}%)"

                log_event(logger, f"❌ 匹配失败诊断: {diagnostic}", level=30, event_type="match_failed_detailed")

                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("match_failed", {
                        "goal_name": goal.task_name,
                        "window_match": kw,
                        "search_terms": list(search_terms),
                        "active_projects": all_active,
                        "best_match": best_match.project_name if best_match else None,
                        "best_ratio": round(highest_ratio, 2)
                    })

                goal.emit(LifecycleEvent.MATCH_FAILED, diagnostic)
                goal.match_fail_notified = True

        if not states and not goal.match_fail_notified:
            goal.emit(LifecycleEvent.MATCH_FAILED, "当前未检测到任何运行中的 IDE 项目窗口")
            goal.match_fail_notified = True

        return None

    @staticmethod
    def _extract_path_components(title: str) -> list[str]:
        """
        从窗口标题中提取路径组件（目录名）

        例：
          "task_parser.py - openwukong - Antigravity" → ["openwukong"]
          "e:\\ideaProjects\\agent\\openwukong\\src" → ["ideaprojects", "agent", "openwukong", "src"]
        """
        components = []

        # 方法1: 提取 Windows 路径（拆分各级目录 + 完整路径字符串）
        path_matches = re.findall(r'[A-Za-z]:\\[\w\\.-]+', title)
        for path_str in path_matches:
            parts = [p.lower() for p in path_str.split('\\') if p and not re.match(r'^[A-Za-z]:$', p)]
            components.extend(parts)
            # 完整路径也作为一个组件（用于全路径匹配场景）
            components.append(path_str.lower())

        # 方法2: 提取 Unix 路径
        unix_matches = re.findall(r'/[\w/.-]+', title)
        for path_str in unix_matches:
            parts = [p.lower() for p in path_str.split('/') if p]
            components.extend(parts)

        # 方法3: 从 dash 分隔的标题片段中提取
        # 使用统一正则，避免 raw string 和 literal string 重复
        dash_parts = re.split(r'\s[-—–]\s', title)
        for part in dash_parts:
            p = part.strip().lower()
            # 过滤过长的片段（>50字符通常是完整路径/无用信息）
            if p and len(p) <= 50:
                components.append(p)

        # 去重并过滤
        seen = set()
        unique = []
        for c in components:
            c_clean = c.strip().lower()
            if c_clean and c_clean not in seen and len(c_clean) >= 2:
                seen.add(c_clean)
                unique.append(c_clean)

        return unique

    # ── 核心状态机（受 OpenClaw lifecycle 启发）──

    def _tick(self, goal: TaskGoal, state: AIProjectState, dry_run: bool):
        state_key = (state.pid, state.window_title or goal.matched_window_title)
        prev = self._prev_states.get(state_key)
        curr = state.ai_status
        self._prev_states[state_key] = curr
        now = time.time()

        # RunLogger: 状态转换事件（低频记录，每次状态真正变化时）
        if prev != curr and getattr(self, "run_logger", None):
            self.run_logger.record_event("tick_transition", {
                "goal_name": goal.task_name, "pid": state.pid,
                "prev": prev.value if prev else "first_detect",
                "curr": curr.value,
            })

        # ── 首次检测到运行 → SPAWNED ──
        if prev is None and curr == AIStatus.RUNNING:
            goal.status = GoalStatus.RUNNING
            goal.last_status_change = now
            goal.emit(LifecycleEvent.SPAWNED, f"Agent 首次探测, PID={state.pid}")
            self._total_events += 1
            return

        # ── 首次检测到 IDLE → 初始化计时器，不误报 stall ──
        if prev is None and curr == AIStatus.IDLE:
            goal.last_status_change = now  # 初始化计时器防止立即触发 stall
            log_event(logger, f"💤 首次探测到 IDLE 状态, PID={state.pid}, 初始化计时器")
            # 不直接 return，让后面的 PENDING 处理可以介入

    # ── PENDING 且当前 IDLE: 主动发起首次检查/指令 ──
        if goal.status == GoalStatus.PENDING and curr == AIStatus.IDLE:
            goal.last_status_change = now
            goal.status = GoalStatus.CHECKING
            goal.emit(LifecycleEvent.COMPLETED, "Agent 空闲，主动全智能检查")
            self._total_events += 1
            self._smart_evaluate(
                goal,
                state.pid,
                dry_run,
                state.window_title,
                state.process_name,
                state.project_name,
            )
            return

        # ── Running → Idle: Agent 完成一轮 (COMPLETED) ──
        if prev == AIStatus.RUNNING and curr == AIStatus.IDLE:
            goal.last_status_change = now
            goal.status = GoalStatus.CHECKING
            goal.emit(LifecycleEvent.COMPLETED, "Agent 完成一轮，进入全智能检查")
            self._total_events += 1
            self._smart_evaluate(
                goal,
                state.pid,
                dry_run,
                state.window_title,
                state.process_name,
                state.project_name,
            )
            return

        # ── Idle → Error || Error 持续: 报错重试 ──
        if curr == AIStatus.ERROR:
            if now - goal.last_action_time > goal.cooldown_sec:
                goal.emit(LifecycleEvent.ERROR, "Agent 报错，触发全智能诊断")
                self._total_events += 1
                self._smart_evaluate(
                    goal,
                    state.pid,
                    dry_run,
                    state.window_title,
                    state.process_name,
                    state.project_name,
                )
            return

        # ── Running 持续 ──
        if curr == AIStatus.RUNNING:
            if goal.status != GoalStatus.RUNNING:
                goal.status = GoalStatus.RUNNING
                goal.last_status_change = now  # 确保回到 RUNNING 时刷新计时器
            return

        # ── Idle 持续 → stall 检测 ──
        if curr == AIStatus.IDLE and prev == AIStatus.IDLE:
            if (goal.status in (GoalStatus.RUNNING, GoalStatus.CHECKING)
                    and now - goal.last_status_change > goal.stall_timeout):
                goal.status = GoalStatus.STALLED
                goal.emit(LifecycleEvent.STALLED, f"Agent 静默 {goal.stall_timeout:.0f}s，触发智能唤醒")
                self._total_events += 1
                self._smart_evaluate(
                    goal,
                    state.pid,
                    dry_run,
                    state.window_title,
                    state.process_name,
                    state.project_name,
                )

    # ── 目标检查（全智能检测，依赖 StrategicCortex）──

    def _smart_evaluate(
        self,
        goal: TaskGoal,
        pid: int,
        dry_run: bool,
        window_title: str = "",
        process_name: str = "",
        project_name: str = "",
    ):
        """调用 Cortex 评估状态，决定 steer 或 success"""
        try:
            if window_title:
                goal.matched_window_title = window_title
            target = self._build_connector_target(
                goal,
                pid,
                window_title=goal.matched_window_title,
                process_name=process_name,
                project_name=project_name,
            )
            connector = self._resolve_session_connector(goal, target)
            conv = connector.read_conversation(target)
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=connector.connector_id,
                action_type="read_conversation",
                status="ok",
                detail=f"{len(conv or '')} chars",
            )

            if not conv.strip() and goal.retry_count == 0:
                goal.emit(
                    LifecycleEvent.COMPLETED,
                    f"Bootstrap initial action via [{connector.connector_id}]",
                )
                self._total_events += 1
                self._steer(goal, target, dry_run, goal.retry_command)
                return

            percept_summary = {
                "retry_count": goal.retry_count,
                "status": goal.status.value,
                "stalled": goal.status == GoalStatus.STALLED,
                "connector": connector.connector_id,
            }

            decision = self.cortex.analyze_and_decide(
                goal_text=goal.goal,
                percept_summary=percept_summary,
                conversation=conv,
                retry_count=goal.retry_count
            )

            if decision.goal_achieved or decision.recommended_action == "wait":
                if decision.goal_achieved:
                    goal.status = GoalStatus.ACHIEVED
                    goal.emit(LifecycleEvent.GOAL_ACHIEVED, f"🏆 目标达成! (理由: {decision.reasoning})")
                    self._total_events += 1
                    if getattr(self, "run_logger", None):
                        self.run_logger.record_event("goal_achieved", {"goal": goal.task_name, "reasoning": decision.reasoning})
                else:
                    goal.emit(LifecycleEvent.COMPLETED, f"🧠 Cortex: 继续等待 ({decision.reasoning})")
            elif decision.recommended_action in ("steer", "pivot"):
                goal.emit(LifecycleEvent.COMPLETED, f"💡 Cortex 判断需引导: {decision.reasoning}")
                steer_content = decision.steer_content or goal.retry_command
                self._steer(
                    goal,
                    target,
                    dry_run,
                    steer_content,
                )
            elif decision.recommended_action == "abort":
                goal.status = GoalStatus.FAILED
                goal.emit(LifecycleEvent.GOAL_FAILED, f"⭕ Cortex 决定放弃: {decision.reasoning}")
                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("goal_aborted", {"goal": goal.task_name, "reasoning": decision.reasoning})

        except psutil.NoSuchProcess:
            goal.emit(LifecycleEvent.ERROR, f"进程 PID={pid} 已退出")
        except Exception as e:
            err_type = type(e).__name__
            goal.emit(LifecycleEvent.ERROR, f"智能检查异常 ({err_type}): {str(e)[:50]}")


    # ── Steer 续发（借鉴 OpenClaw steerControlledSubagentRun）──

    # ── 指数退避参数 ──
    _BASE_COOLDOWN = 10.0   # 基础冷却（秒）
    _MAX_COOLDOWN = 60.0    # 最大冷却（秒）
    _ESCALATION_THRESHOLD = 3  # 连续相同 steer 无效后追加诊断

    def _steer(
        self,
        goal: TaskGoal,
        target: ConnectorTarget,
        dry_run: bool,
        steer_content: str = "",
    ):
        # 重试上限检查
        if goal.retry_count >= goal.max_retries:
            goal.status = GoalStatus.FAILED
            goal.emit(
                LifecycleEvent.GOAL_FAILED,
                f"已达重试上限 ({goal.max_retries})"
            )
            self._total_events += 1
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_limit_reached", {
                    "goal_name": goal.task_name, "retry_count": goal.retry_count,
                    "max_retries": goal.max_retries,
                })
            return

        # 指数退避：重试越多冷却越长
        backoff_multiplier = min(2 ** (goal.retry_count // 3), 6)  # 每3次翻倍，上限6x
        effective_cooldown = min(
            self._BASE_COOLDOWN * backoff_multiplier,
            self._MAX_COOLDOWN,
        )
        try:
            connector = self._resolve_session_connector(
                goal,
                target,
                enforce_route_policy=not dry_run,
            )
        except PermissionError as exc:
            goal.status = GoalStatus.FAILED
            detail = str(exc)
            goal.emit(LifecycleEvent.ERROR, detail[:160])
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=goal.active_connector or goal.connector_hint,
                action_type="send_message",
                status="blocked",
                detail=detail[:200],
            )
            self._total_events += 1
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_blocked_by_route_policy", {
                    "goal_name": goal.task_name,
                    "pid": target.pid,
                    "process": target.process_name,
                    "window_title": target.window_title,
                    "error": detail,
                })
            return

        # 使用传入的 steer_content，如果为空则回退
        from openwukong.supervisor.command_execution import (
            SupervisorCommandExecutor,
            goal_uses_process_broker,
            goal_has_structured_command,
        )

        if goal_has_structured_command(goal):
            command_executor = SupervisorCommandExecutor()
            action_type = (
                "start_command_process"
                if goal_uses_process_broker(goal)
                else "execute_command_intent"
            )
            if dry_run:
                plan_report = command_executor.plan_goal(goal)
                plan_data = plan_report.to_dict()
                if plan_report.ok:
                    goal.retry_count += 1
                    goal.status = GoalStatus.RUNNING
                    goal.emit(
                        LifecycleEvent.STEERED,
                        f"[DRY] structured command plan: {plan_data.get('operation', '')}",
                    )
                    action_status = "dry_run"
                else:
                    goal.emit(
                        LifecycleEvent.ERROR,
                        f"structured command plan blocked: {plan_report.error}",
                    )
                    action_status = "blocked"
                self._record_action(
                    goal=goal,
                    session_id=goal.active_session_id,
                    connector_id=connector.connector_id,
                    action_type=action_type,
                    status=action_status,
                    detail=str(plan_data.get("argv", []))[:120],
                )
                self._total_events += 1
                if plan_report.ok:
                    self._total_steers += 1
                return

            command_report = (
                command_executor.start_process_goal(goal, allow_control=True)
                if goal_uses_process_broker(goal)
                else command_executor.execute_goal(goal, allow_control=True)
            )
            command_data = command_report.to_dict()
            if command_report.ok:
                goal.retry_count += 1
                goal.last_action_time = time.time()
                goal.status = GoalStatus.RUNNING
                if goal_uses_process_broker(goal):
                    process_id = str(command_data.get("process_id", "") or "")
                    goal.active_session_id = (
                        f"command-process:{process_id}" if process_id else goal.active_session_id
                    )
                else:
                    goal.active_session_id = goal.active_session_id or target.session_id
                goal.emit(
                    LifecycleEvent.STEERED,
                    (
                        f"structured command process started #{goal.retry_count}"
                        if goal_uses_process_broker(goal)
                        else f"structured command executed #{goal.retry_count}"
                    ),
                )
                self._record_action(
                    goal=goal,
                    session_id=goal.active_session_id,
                    connector_id=(
                        "command-process-broker"
                        if goal_uses_process_broker(goal)
                        else connector.connector_id
                    ),
                    action_type=action_type,
                    status="ok",
                    detail=(
                        str(command_data.get("process_id", "") or "")
                        if goal_uses_process_broker(goal)
                        else str(command_data.get("action_report", {}).get("stdout", ""))[:120]
                    ),
                )
                self._total_steers += 1
                self._total_events += 1
                if getattr(self, "run_logger", None):
                    event_name = (
                        "structured_command_process_started"
                        if goal_uses_process_broker(goal)
                        else "structured_command_executed"
                    )
                    self.run_logger.record_event(event_name, {
                        "goal_name": goal.task_name,
                        "retry_count": goal.retry_count,
                        "connector": (
                            "command-process-broker"
                            if goal_uses_process_broker(goal)
                            else connector.connector_id
                        ),
                    })
            else:
                detail = command_report.error or "structured_command_failed"
                goal.emit(LifecycleEvent.ERROR, detail[:160])
                self._record_action(
                    goal=goal,
                    session_id=goal.active_session_id,
                    connector_id=connector.connector_id,
                    action_type=action_type,
                    status="error",
                    detail=detail[:120],
                )
                self._total_events += 1
                if getattr(self, "run_logger", None):
                    self.run_logger.record_event("structured_command_failed", {
                        "goal_name": goal.task_name,
                        "retry_count": goal.retry_count,
                        "connector": connector.connector_id,
                        "error": detail,
                    })
            return

        steer_content = steer_content or goal.retry_command
        if goal.retry_count > 0 and goal.retry_count % self._ESCALATION_THRESHOLD == 0:
            escalation_hint = (
                f"\n[系统提示: 已第 {goal.retry_count} 次辅助引导。"
                f"请检查是否陷入循环，尝试换一种方法解决问题。]"
            )
            steer_content = steer_content + escalation_hint
            log_event(logger, f"⬆️ Steer 升级: 第 {goal.retry_count} 次，追加诊断提示", level=20)

        if (
            (goal.connector_hint or "").strip().lower() == "ide-extension"
            and (goal.ide_chat_adapter or "").strip()
        ):
            steer_content = self._format_ide_chat_command(
                goal.ide_chat_adapter,
                steer_content,
            )

        if dry_run:
            goal.retry_count += 1
            goal.status = GoalStatus.RUNNING
            goal.emit(
                LifecycleEvent.STEERED,
                f"[DRY] 将发送: {steer_content[:60]}... (冷却: {effective_cooldown:.0f}s)"
            )
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=connector.connector_id,
                action_type="send_message",
                status="dry_run",
                detail=steer_content[:120],
            )
            self._total_steers += 1
            self._total_events += 1
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_dry_run", {
                    "goal_name": goal.task_name, "retry_count": goal.retry_count,
                    "effective_cooldown": effective_cooldown,
                    "connector": connector.connector_id,
                })
            return

        # 实际 steer（使用退避后的冷却时间）
        result = connector.send_message(
            target,
            steer_content,
            effective_cooldown,
        )
        if result.success:
            goal.retry_count += 1
            goal.last_action_time = time.time()
            goal.status = GoalStatus.RUNNING
            goal.active_session_id = goal.active_session_id or target.session_id
            goal.emit(
                LifecycleEvent.STEERED,
                f"📤 指令已发送 #{goal.retry_count} key={result.action_key} "
                f"[{result.connector_id}] (冷却: {effective_cooldown:.0f}s)"
            )
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=result.connector_id,
                action_type="send_message",
                status="ok",
                detail=steer_content[:120],
            )
            self._total_steers += 1
            self._total_events += 1
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_sent", {
                    "goal_name": goal.task_name, "retry_count": goal.retry_count,
                    "effective_cooldown": effective_cooldown,
                    "connector": result.connector_id,
                    "escalated": goal.retry_count % self._ESCALATION_THRESHOLD == 0,
                })
        else:
            goal.emit(LifecycleEvent.ERROR, "steer 失败（速率限制或输入框未找到）")
            self._record_action(
                goal=goal,
                session_id=goal.active_session_id,
                connector_id=result.connector_id,
                action_type="send_message",
                status="error",
                detail=result.error or "send_message_failed",
            )
            if getattr(self, "run_logger", None):
                self.run_logger.record_event("steer_failed", {
                    "goal_name": goal.task_name, "retry_count": goal.retry_count,
                    "pid": target.pid,
                    "connector": result.connector_id,
                    "error": result.error,
                })

    # ── 仪表盘 ──

    def _dashboard(self, states: list[AIProjectState], elapsed: float):
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)

        emoji_map = {
            GoalStatus.PENDING:  "⏸", GoalStatus.RUNNING: "🔄",
            GoalStatus.CHECKING: "🔍", GoalStatus.ACHIEVED: "🏆",
            GoalStatus.STALLED:  "⚠", GoalStatus.FAILED:  "❌",
        }

        lines = [
            "\033[2J\033[H",
            "=" * 62,
            f"  🤖 Agent Supervisor  │  {h}h {m}m  │  "
            f"steers:{self._total_steers}  events:{self._total_events}",
            "=" * 62, "",
        ]

        for g in self.goals:
            e = emoji_map.get(g.status, "❓")
            retry = f" #{g.retry_count}/{g.max_retries}" if g.retry_count else ""
            lines.append(
                f"  {e} {g.task_name[:30]:<30} {g.status.value}{retry}"
            )
            lines.append(f"     📌 {g.goal[:50]}")
            if g.last_event:
                lines.append(f"     └ {g.last_event}")
            lines.append("")

        lines.append("─" * 62)
        for s in states:
            model = f" [{s.ai_model}]" if s.ai_model else ""
            lines.append(
                f"  {s.status_emoji} {s.project_name[:20]:<20} "
                f"{s.ai_status.value:<8}{model}"
            )
        lines.append("=" * 62)

        print("\n".join(lines), flush=True)

        # 回调钩子 — 推送状态快照给 UI 层
        if self._on_tick:
            try:
                snapshot = self.get_snapshot(elapsed)
                self._on_tick(snapshot)
            except Exception:
                pass  # 回调失败不影响核心逻辑

    # ── 快照（供 UI 层消费）──

    def get_snapshot(self, elapsed: float = 0) -> dict:
        """
        生成当前状态的线程安全快照

        Returns:
            {
                "elapsed": float,
                "total_steers": int,
                "total_events": int,
                "goals": [
                    {
                        "task_name": str,
                        "goal": str,
                        "window_match": str,
                        "status": str,  # GoalStatus.value
                        "retry_count": int,
                        "max_retries": int,
                        "matched_pid": int,
                        "matched_window_title": str,
                        "task_id": str,
                        "workspace_id": str,
                        "workspace_label": str,
                        "connector_hint": str,
                        "workspace_path": str,
                        "resource_url": str,
                        "ide_bridge_url": str,
                        "ide_chat_adapter": str,
                        "command_operation": str,
                        "command_argv": list[str],
                        "command_args": list[str],
                        "command_effects": list[str],
                        "command_profile": str,
                        "command_run_mode": str,
                        "command_process_storage_path": str,
                        "active_connector": str,
                        "active_session_id": str,
                        "last_action_id": str,
                        "lifecycle": list[dict],  # 最近 5 条
                        "last_event": str,
                    }
                ],
                "identity": {
                    "workspaces": list[dict],
                    "sessions": list[dict],
                    "tasks": list[dict],
                    "actions": list[dict],
                }
            }
        """
        if elapsed <= 0:
            elapsed = time.time() - self._start_time if self._start_time else 0

        self._refresh_identity_snapshot()
        goal_snapshots = []
        for g in self.goals:
            goal_snapshots.append({
                "task_name": g.task_name,
                "goal": g.goal,
                "window_match": g.window_match,
                "status": g.status.value,
                "retry_count": g.retry_count,
                "max_retries": g.max_retries,
                "matched_pid": g.matched_pid,
                "matched_window_title": g.matched_window_title,
                "task_id": g.task_id,
                "workspace_id": g.workspace_id,
                "workspace_label": g.workspace_label,
                "connector_hint": g.connector_hint,
                "workspace_path": g.workspace_path,
                "resource_url": g.resource_url,
                "ide_bridge_url": g.ide_bridge_url,
                "ide_chat_adapter": g.ide_chat_adapter,
                "command_operation": g.command_operation,
                "command_argv": list(g.command_argv),
                "command_args": list(g.command_args),
                "command_effects": list(g.command_effects),
                "command_profile": g.command_profile,
                "command_run_mode": g.command_run_mode,
                "command_process_storage_path": g.command_process_storage_path,
                "active_connector": g.active_connector,
                "active_session_id": g.active_session_id,
                "last_action_id": g.last_action_id,
                "lifecycle": copy.deepcopy(g.lifecycle[-5:]),
                "last_event": g.last_event,
            })

        return {
            "elapsed": elapsed,
            "total_steers": self._total_steers,
            "total_events": self._total_events,
            "goals": goal_snapshots,
            "identity": self._identity_snapshot.to_dict(),
        }

    # ── 报告 ──

    def _report(self):
        print("\n" + "=" * 62)
        print("  📊 督导报告")
        print("=" * 62)
        achieved_count = 0
        for g in self.goals:
            is_ok = g.status == GoalStatus.ACHIEVED
            if is_ok:
                achieved_count += 1
            e = "🏆" if is_ok else "❌"
            print(f"\n  {e} {g.task_name}")
            connector_text = g.active_connector or g.connector_hint
            print(
                f"     状态: {g.status.value}  |  Steers: {g.retry_count}"
                f"  |  Connector: {connector_text}"
            )
            # 最近 3 条生命周期事件
            for ev in g.lifecycle[-3:]:
                print(f"     [{ev['ts']}] {ev['event']}: {ev['detail']}")
        print(f"\n  总计: {achieved_count}/{len(self.goals)} 达标, "
              f"共 {self._total_steers} 次 steer, "
              f"{self._total_events} 个事件")
        print()

        # 统一通过 RunLogger 导出报告（JSON + Markdown）
        if getattr(self, "run_logger", None):
            try:
                md_report = self.run_logger.export_markdown()
                if md_report:
                    print(f"  📄 Markdown 报告已保存: {self.run_logger.log_dir}")
                print(f"  📄 JSON 日志已保存: {self.run_logger.filepath}")
            except Exception:
                pass

        # 兼容旧的 supervisor_report.json（保留向后兼容）
        try:
            report = {
                "timestamp": datetime.now().isoformat(),
                "run_id": getattr(self, "run_logger", None) and self.run_logger.run_id or "unknown",
                "summary": {
                    "total": len(self.goals),
                    "achieved": achieved_count,
                    "total_steers": self._total_steers,
                    "total_events": self._total_events,
                },
                "goals": [
                    {
                        "task_name": g.task_name,
                        "status": g.status.value,
                        "retry_count": g.retry_count,
                        "lifecycle": g.lifecycle[-10:],
                    }
                    for g in self.goals
                ],
            }
            report_path = os.path.join("logs", "supervisor_report.json")
            os.makedirs("logs", exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ═══════════════════════════════════════════════
#  配置文件
# ═══════════════════════════════════════════════

def _config_string_list(value) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item)]


def load_goals(path: str) -> list[TaskGoal]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    goals = []
    for item in data.get("goals", []):
        goals.append(TaskGoal(
            window_match=item["window_match"],
            task_name=item["task_name"],
            goal=item["goal"],
            success_keywords=item.get("success_keywords", []),
            failure_keywords=item.get("failure_keywords", ["Error", "failed"]),
            retry_command=item.get("retry_command",
                "继续寻找最佳方案并执行，分析之前的结果，优化策略，直到达到目标。"
            ),
            max_retries=item.get("max_retries", 30),
            cooldown_sec=item.get("cooldown_sec", 10.0),
            stall_timeout=item.get("stall_timeout", 600),
            connector_hint=item.get("connector_hint", "auto"),
            workspace_path=item.get("workspace_path", ""),
            resource_url=item.get("resource_url", ""),
            ide_bridge_url=item.get("ide_bridge_url", ""),
            ide_chat_adapter=item.get("ide_chat_adapter", ""),
            command_operation=item.get("command_operation", ""),
            command_argv=_config_string_list(item.get("command_argv", [])),
            command_args=_config_string_list(item.get("command_args", [])),
            command_effects=_config_string_list(item.get("command_effects", [])),
            command_profile=item.get("command_profile", ""),
            command_timeout_sec=float(item.get("command_timeout_sec", 60.0) or 60.0),
            command_audit_log_path=item.get("command_audit_log_path", ""),
            command_require_owned_session=bool(item.get("command_require_owned_session", False)),
            command_run_mode=item.get("command_run_mode", ""),
            command_process_storage_path=item.get("command_process_storage_path", ""),
        ))
    return goals


def save_example_config(path: str):
    example = {
        "_doc": (
            "Agent Supervisor 通用任务配置。"
            "每个 goal 对应一个 IDE 窗口中需要督导的任务。"
            "window_match 匹配窗口标题关键词。"
            "Agent 完成时检查 success_keywords 判断目标是否达成，"
            "未达标则自动发送 retry_command 续发指令（steer）。"
        ),
        "goals": [
            {
                "window_match": "DOW",
                "task_name": "安全攻防基准测试",
                "goal": "全部攻击向量 ASR > 85%",
                "success_keywords": ["ASR: 0.9", "ASR: 0.8", "passed", "达标"],
                "failure_keywords": ["Error", "failed", "rate limit"],
                "retry_command": (
                    "分析上一轮实验结果中的失败用例，"
                    "寻找更优方案，调整参数后重新执行，直到超过目标。"
                ),
                "max_retries": 30,
                "cooldown_sec": 15,
                "stall_timeout": 600,
                "connector_hint": "auto",
                "workspace_path": ""
            },
            {
                "window_match": "cpop",
                "task_name": "功能开发与测试",
                "goal": "pnpm test 全部通过, pnpm check 无错误",
                "success_keywords": [
                    "all tests passed", "0 errors", "通过",
                    "pnpm test", "done"
                ],
                "failure_keywords": ["FAILED", "error", "TypeError"],
                "retry_command": (
                    "检查最新测试与 lint 输出，修复全部失败项，"
                    "然后重新运行 pnpm test 和 pnpm check 验证。"
                ),
                "max_retries": 20,
                "connector_hint": "auto",
                "workspace_path": ""
            },
            {
                "window_match": "Measurement",
                "task_name": "安全扫描数据收集",
                "goal": "1835 仓库扫描完成",
                "success_keywords": ["scan complete", "1835", "完成"],
                "failure_keywords": ["Error", "timeout"],
                "retry_command": "继续扫描剩余仓库，修复解析错误，确保全部完成。",
                "connector_hint": "auto",
                "workspace_path": ""
            },
            {
                "window_match": "openwukong-terminal",
                "task_name": "终端基线检查",
                "goal": "在仓库根目录执行基础检查并返回结果",
                "success_keywords": ["0 failed", "working tree clean", "通过"],
                "failure_keywords": ["Traceback", "FAILED", "error"],
                "retry_command": "先执行 `git status`，再执行基础检查命令，并汇总结果。",
                "connector_hint": "terminal",
                "workspace_path": ".",
                "max_retries": 10,
                "cooldown_sec": 5,
                "stall_timeout": 60
            },
            {
                "window_match": "openwukong-git",
                "task_name": "Git 基线检查",
                "goal": "在仓库根目录检查 Git 状态并返回结果",
                "success_keywords": ["working tree clean", "nothing to commit", "On branch"],
                "failure_keywords": ["fatal:", "not a git repository", "error:"],
                "retry_command": "git status --short --branch",
                "connector_hint": "git",
                "workspace_path": ".",
                "max_retries": 10,
                "cooldown_sec": 5,
                "stall_timeout": 60
            },
            {
                "window_match": "openwukong-browser",
                "task_name": "Browser 基线导航",
                "goal": "访问指定 URL 并返回页面主要信息",
                "success_keywords": ["200", "title:", "url:"],
                "failure_keywords": ["connection error", "timeout", "invalid browser command"],
                "retry_command": "GET http://127.0.0.1:8000/",
                "connector_hint": "browser",
                "workspace_path": ".",
                "resource_url": "http://127.0.0.1:8000/",
                "max_retries": 10,
                "cooldown_sec": 5,
                "stall_timeout": 60
            }
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(example, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 示例配置已保存: {path}")
    print(f"  编辑后用 --config {path} 启动")


# ═══════════════════════════════════════════════
#  start.bat 集成入口
# ═══════════════════════════════════════════════

def cli_entry(args: list[str]):
    """从 start.bat supervisor 模式调用"""
    import argparse
    parser = argparse.ArgumentParser(
        description="Smart Agent Supervisor — 通用 IDE Agent 全时智能督导"
    )
    parser.add_argument("--config", type=str, default="",
                        help="任务配置文件 (JSON)")
    parser.add_argument("--demo", action="store_true",
                        help="只读演示模式")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="轮询间隔（秒），默认放宽到 15s")
    parser.add_argument("--max-hours", type=float, default=24.0,
                        help="最大运行小时数")
    parser.add_argument("--gen-config", type=str, default="",
                        help="生成示例配置")
    parsed = parser.parse_args(args)

    if parsed.gen_config:
        save_example_config(parsed.gen_config)
        return

    if parsed.config:
        if not os.path.exists(parsed.config):
            print(f"  ❌ 配置文件不存在: {parsed.config}")
            print(f"  生成模板: python agent_supervisor.py --gen-config goals.json")
            return
        goals = load_goals(parsed.config)
    else:
        print("  ℹ 未指定配置，使用内置演示目标")
        print("  生成配置: python agent_supervisor.py --gen-config goals.json\n")
        goals = [
            TaskGoal(
                window_match="DOW",
                task_name="演示任务",
                goal="Agent 完成当前工作",
                success_keywords=[],
                failure_keywords=[],
                retry_command="继续寻找最佳方案并执行。",
            ),
        ]

    print("  🧠 启用全智能大脑驱动（Smart Supervisor）")
    supervisor = AgentSupervisor(goals)

    supervisor.run(
        interval=parsed.interval,
        dry_run=parsed.demo,
        max_hours=parsed.max_hours,
    )


if __name__ == "__main__":
    cli_entry(sys.argv[1:])
