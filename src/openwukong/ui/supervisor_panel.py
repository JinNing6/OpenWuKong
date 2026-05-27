# -*- coding: utf-8 -*-
"""
supervisor_panel.py — 🐵 悟空（WuKong）任务督导 UI 面板

可视化的多任务并发督导面板：
- 多任务卡片列表（实时进度条 + 状态 + 生命周期事件）
- 全局统计面板（达标率、Steer 次数、事件计数）
- 事件流（全局生命周期事件实时滚动）
- 控制区（启动/停止/加载配置）

技术栈：CustomTkinter + threading + queue.Queue

配色：双主题支持（Tokyo Night 暗色 + Ghostwhite Minimal 亮色）
"""

from __future__ import annotations

import os
import json
import time
import queue
import threading
import dataclasses
from typing import Optional, Callable
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from openwukong.supervisor.agent_supervisor import (
    AgentSupervisor,
    TaskGoal,
    GoalStatus,
    LifecycleEvent,
    load_goals,
)
from openwukong.supervisor.task_parser import TaskParser
from openwukong.monitor.ai_monitor import MultiProjectAIMonitor
from openwukong.ui.theme import (
    COLORS,
    STATUS_COLORS,
    STATUS_EMOJI,
    EVENT_MARKERS,
)


# ═══════════════════════════════════════════════
#  Colors 兼容层（保留旧属性名，映射到 theme.py 元组）
# ═══════════════════════════════════════════════

class Colors:
    """主题配色兼容层 — 所有值均为 (light, dark) 元组"""
    BG          = COLORS["bg_dark"]
    CARD        = COLORS["bg_card"]
    CARD_HOVER  = COLORS["bg_hover"]
    SURFACE     = COLORS["bg_surface"]
    ACCENT      = COLORS["accent_blue"]
    SUCCESS     = COLORS["accent_green"]
    WARNING     = COLORS["accent_orange"]
    ERROR       = COLORS["accent_red"]
    RUNNING     = COLORS["accent_cyan"]
    PENDING     = COLORS["text_secondary"]
    TEXT        = COLORS["text_primary"]
    TEXT_DIM    = COLORS["text_secondary"]
    TEXT_BRIGHT = COLORS["text_bright"]
    PROGRESS_BG = COLORS["progress_bg"]
    BORDER      = COLORS["border"]

    STATUS_COLORS = STATUS_COLORS
    STATUS_EMOJI  = STATUS_EMOJI


# ═══════════════════════════════════════════════
#  TaskCard — 单个任务卡片组件
# ═══════════════════════════════════════════════

class TaskCard(ctk.CTkFrame):
    """
    单个督导任务的可视化卡片

    显示：任务名称、目标、窗口匹配、状态、进度条、
         Steer 计数器、最近生命周期事件
    """

    def __init__(self, master, index: int = 0, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=2,
            border_color=COLORS["border"],
            **kwargs,
        )

        self._index = index
        self._current_status = "pending"

        # ── 行 0: 标题行 ──
        self._header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._header_frame.grid(row=0, column=0, sticky="ew",
                                padx=16, pady=(14, 4))
        self._header_frame.grid_columnconfigure(1, weight=1)

        self._status_emoji = ctk.CTkLabel(
            self._header_frame,
            text="⏸",
            font=ctk.CTkFont(size=20),
            text_color=COLORS["text_primary"],
            width=30,
        )
        self._status_emoji.grid(row=0, column=0, padx=(0, 8))

        self._task_name = ctk.CTkLabel(
            self._header_frame,
            text=f"任务 {index + 1}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._task_name.grid(row=0, column=1, sticky="w")

        self._status_badge = ctk.CTkLabel(
            self._header_frame,
            text="等待中",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="e",
        )
        self._status_badge.grid(row=0, column=2, padx=(8, 0))

        # ── 行 1: 目标描述 ──
        self._goal_label = ctk.CTkLabel(
            self,
            text="目标: —",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._goal_label.grid(row=1, column=0, sticky="w", padx=16, pady=(2, 2))

        # ── 行 2: 窗口/PID 信息 ──
        self._window_label = ctk.CTkLabel(
            self,
            text="窗口: —",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._window_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 6))

        # ── 行 3: 进度条 ──
        self._progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._progress_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 4))
        self._progress_frame.grid_columnconfigure(0, weight=1)

        self._progressbar = ctk.CTkProgressBar(
            self._progress_frame,
            width=400,
            height=10,
            corner_radius=5,
            progress_color=COLORS["accent_blue"],
            fg_color=COLORS["progress_bg"],
        )
        self._progressbar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._progressbar.set(0)

        self._progress_pct = ctk.CTkLabel(
            self._progress_frame,
            text="0%",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"],
            width=40,
        )
        self._progress_pct.grid(row=0, column=1)

        # ── 行 4: Steer 计数 + 最近事件 ──
        self._info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._info_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))
        self._info_frame.grid_columnconfigure(1, weight=1)

        self._steer_label = ctk.CTkLabel(
            self._info_frame,
            text="Steers: 0/0",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
            width=100,
        )
        self._steer_label.grid(row=0, column=0, padx=(0, 12))

        self._event_label = ctk.CTkLabel(
            self._info_frame,
            text="等待启动...",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._event_label.grid(row=0, column=1, sticky="w")

        # 使卡片可以水平伸展
        self.grid_columnconfigure(0, weight=1)

    def update_from_snapshot(self, goal_data: dict):
        """从 AgentSupervisor 快照更新卡片显示"""
        status = goal_data.get("status", "pending")
        self._current_status = status

        # ── 更新边框色 ──
        border_color = STATUS_COLORS.get(status, COLORS["border"])
        self.configure(border_color=border_color)

        # ── 状态 Emoji ──
        emoji = STATUS_EMOJI.get(status, "❓")
        self._status_emoji.configure(text=emoji)

        # ── 任务名称 ──
        task_name = goal_data.get("task_name", f"任务 {self._index + 1}")
        self._task_name.configure(text=task_name)

        # ── 状态徽章 ──
        status_names = {
            "pending": "等待中", "running": "运行中", "checking": "检查中",
            "achieved": "已达标", "stalled": "已停滞", "failed": "已失败",
        }
        status_text = status_names.get(status, status)
        status_color = STATUS_COLORS.get(status, COLORS["text_secondary"])
        self._status_badge.configure(text=status_text, text_color=status_color)

        # ── 目标 ──
        goal = goal_data.get("goal", "—")
        self._goal_label.configure(text=f"目标: {goal}")

        # ── 窗口/PID ──
        window_match = goal_data.get("window_match", "—")
        matched_window_title = goal_data.get("matched_window_title", "").strip()
        window_label = matched_window_title or window_match
        pid = goal_data.get("matched_pid", 0)
        if pid:
            self._window_label.configure(
                text=f"窗口: {window_label} (PID: {pid})",
                text_color=COLORS["text_secondary"],
            )
        else:
            self._window_label.configure(
                text=f"窗口: {window_label} — 未匹配",
                text_color=COLORS["accent_orange"],
            )

        # ── 进度条 ──
        progress = self._calc_progress(goal_data)
        progress_color = STATUS_COLORS.get(status, COLORS["accent_blue"])
        self._progressbar.configure(progress_color=progress_color)
        self._progressbar.set(progress)
        self._progress_pct.configure(
            text=f"{int(progress * 100)}%",
            text_color=progress_color,
        )

        # ── Steer 计数 ──
        retry = goal_data.get("retry_count", 0)
        max_r = goal_data.get("max_retries", 0)
        self._steer_label.configure(text=f"Steers: {retry}/{max_r}")

        # ── 最近事件 ──
        last_event = goal_data.get("last_event", "")
        if last_event:
            # 截取到合理长度
            display = last_event[:80] + "…" if len(last_event) > 80 else last_event
            self._event_label.configure(text=display, text_color=status_color)
        else:
            self._event_label.configure(text="等待启动...", text_color=COLORS["text_secondary"])

    @staticmethod
    def _calc_progress(goal_data: dict) -> float:
        """计算任务进度 (0.0 ~ 1.0)"""
        status = goal_data.get("status", "pending")

        if status == "achieved":
            return 1.0
        if status == "failed":
            return 1.0  # 失败也是 100%（红色）
        if status == "pending":
            return 0.0

        # 运行中/停滞：基于 retry_count / max_retries 估算
        retry = goal_data.get("retry_count", 0)
        max_r = goal_data.get("max_retries", 1)
        if max_r <= 0:
            max_r = 1

        # 至少显示 5% 表示已开始
        raw = retry / max_r
        return max(0.05, min(raw, 0.95))  # 不超过 95%（直到达标）


# ═══════════════════════════════════════════════
#  EventStream — 全局事件流
# ═══════════════════════════════════════════════

class EventStream(ctk.CTkFrame):
    """全局生命周期事件流面板"""

    MAX_EVENTS = 50

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)

        # 标题
        self._title = ctk.CTkLabel(
            self,
            text="📋 事件流 · Event Stream",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._title.grid(row=0, column=0, sticky="w", padx=16, pady=(10, 4))

        # 事件文本框
        self._textbox = ctk.CTkTextbox(
            self,
            height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_surface"],
            corner_radius=8,
            wrap="word",
            state="disabled",
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.grid_rowconfigure(1, weight=1)

        self._event_count = 0
        self._seen_event_ids: set[str] = set()  # 去重：已渲染过的事件 ID

    def append_events(self, goals: list[dict]):
        """从快照中提取新事件并追加到事件流（已渲染事件自动去重）"""
        new_lines = []
        for g in goals:
            task_name = g.get("task_name", "?")[:16]
            for ev in g.get("lifecycle", []):
                # 利用 lifecycle 条目中的唯一 id 做去重
                ev_id = ev.get("id", "")
                if ev_id in self._seen_event_ids:
                    continue
                if ev_id:
                    self._seen_event_ids.add(ev_id)

                ts = ev.get("ts", "??:??:??")
                event_type = ev.get("event", "unknown")
                detail = ev.get("detail", "")[:60]

                # 事件类型颜色标记
                type_marker = EVENT_MARKERS.get(event_type, "⚪")

                line = f"[{ts}] {type_marker} {event_type:<14} {task_name} — {detail}"
                new_lines.append(line)

        if not new_lines:
            return

        self._textbox.configure(state="normal")

        for line in new_lines:
            self._textbox.insert("end", line + "\n")
            self._event_count += 1

        # 限制最大行数
        if self._event_count > self.MAX_EVENTS:
            # 删除最旧的行
            excess = self._event_count - self.MAX_EVENTS
            self._textbox.delete("1.0", f"{excess + 1}.0")
            self._event_count = self.MAX_EVENTS

        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def clear(self):
        """清空事件流"""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
        self._event_count = 0
        self._seen_event_ids.clear()


# ═══════════════════════════════════════════════
#  StatsBar — 顶部统计面板
# ═══════════════════════════════════════════════

class StatsBar(ctk.CTkFrame):
    """顶部统计条：达标率 / Steers / 事件 / 运行时间"""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            height=60,
            **kwargs,
        )
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._stats = {}
        stat_defs = [
            ("achieved", "🟢 达标", "0/0", COLORS["accent_green"]),
            ("steers",   "📤 Steer", "0", COLORS["accent_blue"]),
            ("events",   "⚡ 事件", "0", COLORS["accent_orange"]),
            ("elapsed",  "⏱ 运行时间", "00:00:00", COLORS["accent_cyan"]),
        ]

        for col, (key, title, default, color) in enumerate(stat_defs):
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.grid(row=0, column=col, padx=12, pady=10)

            title_lbl = ctk.CTkLabel(
                frame,
                text=title,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_secondary"],
            )
            title_lbl.pack()

            value_lbl = ctk.CTkLabel(
                frame,
                text=default,
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=color,
            )
            value_lbl.pack()

            self._stats[key] = value_lbl

    def update_from_snapshot(self, snapshot: dict):
        """从快照更新统计数据"""
        goals = snapshot.get("goals", [])
        total = len(goals)
        achieved = sum(1 for g in goals if g.get("status") == "achieved")

        self._stats["achieved"].configure(text=f"{achieved}/{total}")
        self._stats["steers"].configure(text=str(snapshot.get("total_steers", 0)))
        self._stats["events"].configure(text=str(snapshot.get("total_events", 0)))

        elapsed = snapshot.get("elapsed", 0)
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self._stats["elapsed"].configure(text=f"{h:02d}:{m:02d}:{s:02d}")


# ═══════════════════════════════════════════════
#  SupervisorPanel — 悟空督导主面板
# ═══════════════════════════════════════════════

class SupervisorPanel(ctk.CTkFrame):
    """
    🐵 悟空（WuKong）— 任务督导主面板

    集成到 Dashboard 中作为独立页面使用。
    可独立运行用于测试。
    """

    # UI 刷新间隔（毫秒）
    REFRESH_MS = 500

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_dark"], **kwargs)

        self._queue: queue.Queue = queue.Queue(maxsize=100)
        self._worker: Optional[_SupervisorWorker] = None
        self._goals: list[TaskGoal] = []
        self._task_cards: list[TaskCard] = []
        self._is_running = False
        self._last_snapshot: Optional[dict] = None
        self._config_path = ""

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # 任务卡片列表可伸展

        self._build_ui()
        self._start_refresh_loop()

    def _build_ui(self):
        """构建 UI 组件"""

        # ── 顶部标题 ──
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        title_frame.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            title_frame,
            text="🐵 悟空 · WuKong",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text_bright"],
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        subtitle_lbl = ctk.CTkLabel(
            title_frame,
            text="多任务并发督导面板\nWuKong Task Supervisor",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        subtitle_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # 运行状态指示灯
        self._status_indicator = ctk.CTkLabel(
            title_frame,
            text="● 待机",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
            anchor="e",
        )
        self._status_indicator.grid(row=0, column=1, sticky="e")

        # ── 统计条 ──
        self._stats_bar = StatsBar(self)
        self._stats_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))

        # ── 中间区域：任务卡片 + 事件流 ──
        middle_frame = ctk.CTkFrame(self, fg_color="transparent")
        middle_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        middle_frame.grid_columnconfigure(0, weight=1)
        middle_frame.grid_rowconfigure(0, weight=3)  # 任务卡片占更多空间
        middle_frame.grid_rowconfigure(1, weight=1)  # 事件流

        # 任务卡片滚动区域
        self._scroll_frame = ctk.CTkScrollableFrame(
            middle_frame,
            fg_color="transparent",
            corner_radius=0,
            label_text="📋 任务列表",
            label_font=ctk.CTkFont(size=13, weight="bold"),
            label_text_color=COLORS["text_primary"],
            label_fg_color=COLORS["bg_dark"],
        )
        self._scroll_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        # 空状态提示
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="暂无任务\n\n在下方输入框中描述你的任务\n例如：帮悟空盯着 Cursor 里的项目，确保测试全部通过",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
            justify="center",
        )
        self._empty_label.grid(row=0, column=0, pady=40)

        # 事件流
        self._event_stream = EventStream(middle_frame)
        self._event_stream.grid(row=1, column=0, sticky="nsew")

        # ── 底部控制栏 ──
        self._build_control_bar()

    def _build_control_bar(self):
        """构建底部控制区（自然语言输入 + 按钮栏）"""
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        bottom_frame.grid_columnconfigure(0, weight=1)

        # ── 第一行：自然语言输入区 ──
        nl_frame = ctk.CTkFrame(bottom_frame, fg_color=COLORS["bg_card"], corner_radius=12)
        nl_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        nl_frame.grid_columnconfigure(0, weight=1)

        nl_label = ctk.CTkLabel(
            nl_frame,
            text="🧠 描述你的任务",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        nl_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(10, 4))

        self._nl_input = ctk.CTkTextbox(
            nl_frame,
            fg_color=COLORS["bg_surface"],
            text_color=COLORS["text_primary"],
            font=ctk.CTkFont(size=13),
            corner_radius=8,
            height=70,
            border_width=1,
            border_color=COLORS["border"],
        )
        self._nl_input.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 12))
        self._nl_input.insert("1.0", "例如：帮我盯着 Cursor 里的 DOW 项目，ASR 要跑到 85%")
        self._nl_input.configure(text_color=COLORS["text_secondary"])

        # 聚焦时清除 placeholder
        def _on_focus_in(e):
            current = self._nl_input.get("1.0", "end").strip()
            if current.startswith("例如："):
                self._nl_input.delete("1.0", "end")
                self._nl_input.configure(text_color=COLORS["text_primary"])
        def _on_focus_out(e):
            current = self._nl_input.get("1.0", "end").strip()
            if not current:
                self._nl_input.insert("1.0", "例如：帮我盯着 Cursor 里的 DOW 项目，ASR 要跑到 85%")
                self._nl_input.configure(text_color=COLORS["text_secondary"])
        self._nl_input.bind("<FocusIn>", _on_focus_in)
        self._nl_input.bind("<FocusOut>", _on_focus_out)

        # 右侧按钮组
        btn_stack = ctk.CTkFrame(nl_frame, fg_color="transparent")
        btn_stack.grid(row=1, column=1, sticky="ns", padx=(0, 16), pady=(0, 12))

        self._parse_btn = ctk.CTkButton(
            btn_stack,
            text="🧠 智能解析",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent_blue"],
            hover_color=("#2563eb", "#6990d9"),
            text_color=COLORS["text_bright"],
            corner_radius=8,
            width=110,
            height=32,
            command=self._on_parse,
        )
        self._parse_btn.pack(pady=(0, 4))

        # 高级入口：加载 JSON
        self._load_btn = ctk.CTkButton(
            btn_stack,
            text="📄 JSON导入",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            width=110,
            height=28,
            command=self._on_load_config,
        )
        self._load_btn.pack()

        # ── 第二行：启动/停止 + 开关 ──
        control_frame = ctk.CTkFrame(bottom_frame, fg_color=COLORS["bg_card"], corner_radius=12)
        control_frame.grid(row=1, column=0, sticky="ew")
        control_frame.grid_columnconfigure(3, weight=1)

        # 启动按钮
        self._start_btn = ctk.CTkButton(
            control_frame,
            text="▶  启动督导",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent_green"],
            hover_color=("#059669", "#7fb356"),
            text_color=COLORS["text_bright"],
            corner_radius=8,
            width=130,
            height=38,
            command=self._on_start,
        )
        self._start_btn.grid(row=0, column=0, padx=(16, 8), pady=12)

        # 停止按钮
        self._stop_btn = ctk.CTkButton(
            control_frame,
            text="⏹  停止",
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["accent_red"],
            hover_color=("#dc2626", "#d4637c"),
            text_color=COLORS["text_bright"],
            corner_radius=8,
            width=100,
            height=38,
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.grid(row=0, column=1, padx=(0, 8), pady=12)

        # 演示模式开关
        self._demo_var = ctk.BooleanVar(value=True)
        self._demo_switch = ctk.CTkSwitch(
            control_frame,
            text="演示模式（只读）",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
            variable=self._demo_var,
            onvalue=True,
            offvalue=False,
            progress_color=COLORS["accent_blue"],
        )
        self._demo_switch.grid(row=0, column=3, padx=(0, 16), sticky="e")

    # ═══════════════════════════════════════════
    #  操作回调
    # ═══════════════════════════════════════════

    def _on_parse(self):
        """🧠 智能解析：将自然语言描述解析为 TaskGoal"""
        raw_text = self._nl_input.get("1.0", "end").strip()

        # 忽略 placeholder
        if not raw_text or raw_text.startswith("例如："):
            self._status_indicator.configure(
                text="● 请先输入任务描述",
                text_color=COLORS["accent_orange"],
            )
            return

        # 拒绝超短无意义输入（如只输入"1"）
        if len(raw_text) < 2:
            self._status_indicator.configure(
                text="● 输入太短啦，请描述一下你想让悟空帮你盯什么任务",
                text_color=COLORS["accent_orange"],
            )
            return

        # 切换为加载状态
        self._parse_btn.configure(text="⏳ 分析中...", state="disabled")
        self._status_indicator.configure(
            text="● 🧠 正在用 AI 解析任务...",
            text_color=COLORS["accent_cyan"],
        )

        # 后台线程执行 LLM 解析
        def _do_parse():
            try:
                # 1. 快速扫描当前活跃的 IDE 窗口（轻量，无 UIA 深探，<500ms）
                monitor = MultiProjectAIMonitor()
                states = monitor.scan_windows_fast()
                active_windows = [s.window_title for s in states] if states else []

                # 2. 调用解析器并注入窗口列表
                parser = TaskParser()
                results = parser.parse(raw_text, active_windows=active_windows)

                # 回到 UI 主线程
                self.after(0, lambda: self._on_parse_done(results, None))
            except Exception as e:
                self.after(0, lambda: self._on_parse_done(None, str(e)))

        threading.Thread(target=_do_parse, daemon=True, name="NL-Parser").start()

    def _on_parse_done(self, results: list[dict] | None, error: str | None):
        """解析完成回调（UI 主线程）"""
        # 恢复按钮
        self._parse_btn.configure(text="🧠 智能解析", state="normal")

        if error or not results:
            self._status_indicator.configure(
                text=f"● 解析失败: {(error or '未能理解任务描述')[:40]}",
                text_color=COLORS["accent_red"],
            )
            return

        # 将解析结果转为 TaskGoal 对象
        goals = []
        for task_data in results:
            try:
                goal = TaskGoal(
                    window_match=task_data.get("window_match", "IDE"),
                    task_name=task_data.get("task_name", "未命名任务"),
                    goal=task_data.get("goal", ""),
                    success_keywords=task_data.get("success_keywords", ["done", "passed"]),
                    failure_keywords=task_data.get("failure_keywords", ["Error", "failed"]),
                    retry_command=task_data.get("retry_command", "继续完成任务。"),
                    max_retries=task_data.get("max_retries", 30),
                    cooldown_sec=task_data.get("cooldown_sec", 10),
                    stall_timeout=task_data.get("stall_timeout", 600),
                    connector_hint=task_data.get("connector_hint", "auto"),
                    workspace_path=task_data.get("workspace_path", ""),
                    resource_url=task_data.get("resource_url", ""),
                )
                goals.append(goal)
            except Exception:
                continue

        if not goals:
            self._status_indicator.configure(
                text="● 解析失败: 无法生成有效任务",
                text_color=COLORS["accent_red"],
            )
            return

        # 更新目标列表
        self._goals = goals
        self._config_path = ""  # 来自自然语言，非文件

        # ── 智能预匹配：解析后立即做一次快速窗口匹配 ──
        try:
            pre_monitor = MultiProjectAIMonitor()
            pre_states = pre_monitor.scan_windows_fast()
            if pre_states:
                from openwukong.core.constants import PROJECT_ALIASES, PROJECT_ALIAS_REVERSE
                import difflib

                for goal in self._goals:
                    kw = goal.window_match.lower()
                    goal.matched_pid = 0
                    goal.matched_window_title = ""
                    # 构建搜索词集合（复用别名逻辑）
                    search_terms = {kw}
                    for alias, target in PROJECT_ALIASES.items():
                        if alias in kw or kw in alias:
                            search_terms.add(target)
                            search_terms.add(alias)
                        if target in kw or kw in target:
                            search_terms.add(target)
                            search_terms.add(alias)
                    if kw in PROJECT_ALIAS_REVERSE:
                        for alias in PROJECT_ALIAS_REVERSE[kw]:
                            search_terms.add(alias)
                    search_terms = {t for t in search_terms if len(t) >= 2} or {kw}

                    # L1 精确匹配
                    for s in pre_states:
                        p_name = s.project_name.lower()
                        w_title = s.window_title.lower()
                        for term in search_terms:
                            if term in p_name or term in w_title:
                                goal.matched_pid = s.pid
                                goal.matched_window_title = s.window_title
                                break
                        if goal.matched_pid:
                            break

                    # L2 模糊匹配（如果 L1 失败）
                    if not goal.matched_pid:
                        best_ratio = 0.0
                        best_state = None
                        for s in pre_states:
                            for term in search_terms:
                                ratio = difflib.SequenceMatcher(None, term, s.project_name.lower()).ratio()
                                if ratio > best_ratio:
                                    best_ratio = ratio
                                    best_state = s
                        if best_ratio > 0.5 and best_state:
                            goal.matched_pid = best_state.pid
                            goal.matched_window_title = best_state.window_title

                    if not goal.matched_pid:
                        codex_states = [
                            s for s in pre_states
                            if "codex" in (s.process_name or "").lower()
                        ]
                        if len(codex_states) == 1:
                            goal.matched_pid = codex_states[0].pid
                            goal.matched_window_title = codex_states[0].window_title
        except Exception:
            pass  # 预匹配失败不影响后续流程

        self._rebuild_task_cards()
        self._event_stream.clear()

        # 检查预匹配结果
        matched_count = sum(1 for g in self._goals if g.matched_pid)
        if matched_count == len(self._goals):
            self._status_indicator.configure(
                text=f"● ✅ 已解析 {len(goals)} 个任务，窗口已匹配 — 正在自动启动...",
                text_color=COLORS["accent_green"],
            )
            # 自动启动督导
            self.after(300, self._on_start)
        elif matched_count > 0:
            self._status_indicator.configure(
                text=f"● ✅ 已解析 {len(goals)} 个任务（{matched_count}/{len(goals)} 已匹配）— 点击启动",
                text_color=COLORS["accent_green"],
            )
        else:
            self._status_indicator.configure(
                text=f"● ✅ 已解析 {len(goals)} 个任务 — 点击「启动督导」开始",
                text_color=COLORS["accent_green"],
            )

    def _on_load_config(self):
        """加载 goals.json 配置文件"""
        # 默认查找项目根目录的 goals.json
        initial_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
        )

        filepath = filedialog.askopenfilename(
            title="选择任务配置文件",
            initialdir=initial_dir,
            filetypes=[
                ("JSON 配置文件", "*.json"),
                ("所有文件", "*.*"),
            ],
        )
        if not filepath:
            return

        try:
            self._goals = load_goals(filepath)
            self._config_path = filepath
            self._rebuild_task_cards()
            self._event_stream.clear()

            # 更新状态指示
            filename = os.path.basename(filepath)
            self._status_indicator.configure(
                text=f"● 已加载 {filename}（{len(self._goals)} 个任务）",
                text_color=COLORS["accent_green"],
            )
        except Exception as e:
            self._status_indicator.configure(
                text=f"● 加载失败: {str(e)[:40]}",
                text_color=COLORS["accent_red"],
            )

    def _rebuild_task_cards(self):
        """重建任务卡片列表"""
        # 清理旧卡片
        for card in self._task_cards:
            card.destroy()
        self._task_cards.clear()

        # 隐藏空状态提示
        if self._goals:
            self._empty_label.grid_forget()

        # 创建新卡片
        for i, goal in enumerate(self._goals):
            card = TaskCard(self._scroll_frame, index=i)
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=(0, 8))

            # 初始化卡片数据
            card.update_from_snapshot({
                "task_name": goal.task_name,
                "goal": goal.goal,
                "window_match": goal.window_match,
                "status": goal.status.value,
                "retry_count": goal.retry_count,
                "max_retries": goal.max_retries,
                "matched_pid": goal.matched_pid,
                "matched_window_title": goal.matched_window_title,
                "connector_hint": goal.connector_hint,
                "workspace_path": goal.workspace_path,
                "resource_url": goal.resource_url,
                "active_connector": goal.active_connector,
                "lifecycle": [],
                "last_event": "",
            })

            self._task_cards.append(card)

    def _on_start(self):
        """启动督导"""
        if self._is_running:
            return

        if not self._goals:
            self._status_indicator.configure(
                text="● 请先描述任务或导入配置文件",
                text_color=COLORS["accent_orange"],
            )
            return

        self._is_running = True
        self._event_stream.clear()

        # 重新创建 goals（清理运行时状态）
        if self._config_path:
            try:
                self._goals = load_goals(self._config_path)
                self._rebuild_task_cards()
            except Exception:
                pass

        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # 启动后台线程
        dry_run = self._demo_var.get()
        self._worker = _SupervisorWorker(
            goals=self._goals,
            output_queue=self._queue,
            dry_run=dry_run,
        )
        self._worker.start()

        # 更新 UI 状态
        if dry_run:
            mode_text = "🔍 演示模式"
        else:
            mode_text = "🧠 全智能督导"
        self._status_indicator.configure(
            text=f"● 运行中 — {mode_text}",
            text_color=COLORS["accent_cyan"],
        )
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._load_btn.configure(state="disabled")
        self._parse_btn.configure(state="disabled")
        self._nl_input.configure(state="disabled")
        self._demo_switch.configure(state="disabled")

    def _on_stop(self):
        """停止督导"""
        if not self._is_running:
            return

        if self._worker:
            self._worker.stop()
            self._worker = None

        self._is_running = False

        self._status_indicator.configure(
            text="● 已停止",
            text_color=COLORS["accent_orange"],
        )
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._load_btn.configure(state="normal")
        self._parse_btn.configure(state="normal")
        self._nl_input.configure(state="normal")
        self._demo_switch.configure(state="normal")

    # ═══════════════════════════════════════════
    #  UI 刷新循环
    # ═══════════════════════════════════════════

    def _start_refresh_loop(self):
        """启动 UI 定时刷新"""
        self._process_queue()
        self.after(self.REFRESH_MS, self._start_refresh_loop)

    def _process_queue(self):
        """从队列中读取快照并更新 UI"""
        latest_snapshot = None

        # 只取最新的快照（丢弃过时的）
        while not self._queue.empty():
            try:
                latest_snapshot = self._queue.get_nowait()
            except queue.Empty:
                break

        if latest_snapshot is None:
            return

        self._last_snapshot = latest_snapshot

        # 更新统计条
        self._stats_bar.update_from_snapshot(latest_snapshot)

        # 更新任务卡片
        goals_data = latest_snapshot.get("goals", [])
        for i, goal_data in enumerate(goals_data):
            if i < len(self._task_cards):
                self._task_cards[i].update_from_snapshot(goal_data)

        # 更新事件流
        self._event_stream.append_events(goals_data)

        # 检查是否所有任务已完成
        if self._is_running and goals_data:
            all_done = all(
                g.get("status") in ("achieved", "failed")
                for g in goals_data
            )
            if all_done:
                achieved = sum(1 for g in goals_data if g.get("status") == "achieved")
                total = len(goals_data)
                self._status_indicator.configure(
                    text=f"● 完成 — {achieved}/{total} 达标",
                    text_color=COLORS["accent_green"] if achieved == total else COLORS["accent_orange"],
                )
                self._on_stop()


# ═══════════════════════════════════════════════
#  _SupervisorWorker — 后台督导线程
# ═══════════════════════════════════════════════

class _SupervisorWorker(threading.Thread):
    """
    后台线程：运行 AgentSupervisor 并通过 Queue 推送状态快照

    通过 threading.Event 实现优雅停止。
    """

    def __init__(
        self,
        goals: list[TaskGoal],
        output_queue: queue.Queue,
        dry_run: bool = True,
        interval: float = 15.0,
        max_hours: float = 24.0,
    ):
        super().__init__(daemon=True, name="Wukong-Worker")
        self._goals = goals
        self._queue = output_queue
        self._dry_run = dry_run
        self._interval = interval
        self._max_hours = max_hours
        self._stop_event = threading.Event()

    def run(self):
        """后台线程入口"""
        try:
            supervisor = AgentSupervisor(
                goals=self._goals,
                on_tick_callback=self._on_tick,
            )
            # 注入停止事件
            supervisor._stop_event = self._stop_event

            supervisor.run(
                interval=self._interval,
                dry_run=self._dry_run,
                max_hours=self._max_hours,
            )
        except Exception as e:
            # 推送错误快照
            self._queue.put({
                "elapsed": 0,
                "total_steers": 0,
                "total_events": 0,
                "goals": [],
                "error": str(e),
            })

    def _on_tick(self, snapshot: dict):
        """回调：将快照推送到队列"""
        try:
            # 非阻塞放入，如果队列满了就丢弃最旧的
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put_nowait(snapshot)
        except Exception:
            pass

    def stop(self):
        """优雅停止"""
        self._stop_event.set()


# ═══════════════════════════════════════════════
#  独立运行入口（调试用）
# ═══════════════════════════════════════════════

def run_standalone():
    """独立运行悟空督导面板（调试/演示用）"""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("🐵 OpenWukong — 悟空 · WuKong")
    root.geometry("900x750")
    root.minsize(800, 600)

    # 设置窗口图标背景色
    root.configure(fg_color=COLORS["bg_dark"])

    panel = SupervisorPanel(root)
    panel.pack(fill="both", expand=True)

    def on_closing():
        panel._on_stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    run_standalone()
