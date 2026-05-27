# -*- coding: utf-8 -*-
"""
dashboard.py — OpenWukong 控制面板
=======================================
双主题支持：Tokyo Night（暗色）+ Ghostwhite Minimal（亮色）
Apple/OpenAI 设计风格
支持四种运行模式:
  1. 单次扫描  2. 持续监控  3. 督导演示  4. 全时督导

启动:
    python -m openwukong --gui
    python -m openwukong.ui.dashboard
"""

from __future__ import annotations

import customtkinter as ctk
import threading
import queue
import time
import json
import difflib
import os
from datetime import datetime
from typing import Optional

from openwukong.core.constants import PROJECT_ALIASES
from openwukong.ui.theme import COLORS, MODES, STATUS_STYLE, LOG_COLORS


class WukongApp(ctk.CTk):
    """OpenWukong 控制面板主窗口"""

    def __init__(self):
        super().__init__()

        # ── 窗口配置 ──
        self.title("OpenWukong · 悟空")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self._appearance_mode_state = "Dark"
        ctk.set_appearance_mode(self._appearance_mode_state)
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["bg_dark"])

        # ── 状态 ──
        self._current_mode: str = "scan"
        self._running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._log_queue: queue.Queue = queue.Queue(maxsize=500)
        self._start_time: float = 0
        self._ide_states: list = []

        # ── 构建 UI ──
        self._build_sidebar()
        self._build_main_area()

        # ── 定时刷新 ──
        self._poll_ui()

        # ── 关闭时清理 ──
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════
    #  左侧导航栏
    # ══════════════════════════════════════════

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)

        # 品牌标识
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(pady=(24, 4), padx=16, fill="x")

        ctk.CTkLabel(
            brand_frame, text="🐵",
            font=ctk.CTkFont(size=36),
            text_color=COLORS["accent_blue"],
        ).pack()

        ctk.CTkLabel(
            brand_frame, text="OpenWukong",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            brand_frame, text="IDE Agent 悟空",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(2, 0))

        # 分隔线
        ctk.CTkFrame(
            sidebar, height=1, fg_color=COLORS["border"]
        ).pack(fill="x", padx=20, pady=(20, 16))

        # 模式按钮
        ctk.CTkLabel(
            sidebar, text="运行模式 · MODES",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(padx=20, fill="x")

        self._mode_buttons: dict[str, ctk.CTkButton] = {}
        for mode_key, mode_info in MODES.items():
            btn = ctk.CTkButton(
                sidebar,
                text=mode_info["label"],
                font=ctk.CTkFont(family="Segoe UI", size=13),
                anchor="w",
                height=38,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_primary"],
                command=lambda k=mode_key: self._select_mode(k),
            )
            btn.pack(padx=12, pady=2, fill="x")
            self._mode_buttons[mode_key] = btn

        # 默认选中 scan
        self._highlight_mode("scan")

        # 分隔线
        ctk.CTkFrame(
            sidebar, height=1, fg_color=COLORS["border"]
        ).pack(fill="x", padx=20, pady=(16, 12))

        # 设置区
        ctk.CTkLabel(
            sidebar, text="设置 · SETTINGS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(padx=20, fill="x")

        # 目标进程
        ctk.CTkLabel(
            sidebar, text="目标进程",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(padx=20, pady=(8, 2), fill="x")

        self._target_entry = ctk.CTkEntry(
            sidebar, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="Antigravity.exe",
        )
        self._target_entry.pack(padx=16, fill="x")
        self._target_entry.insert(0, "Antigravity.exe")

        # 轮询间隔
        ctk.CTkLabel(
            sidebar, text="轮询间隔 (秒)",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(padx=20, pady=(8, 2), fill="x")

        self._interval_slider = ctk.CTkSlider(
            sidebar, from_=1, to=10, number_of_steps=9,
            button_color=COLORS["accent_blue"],
            button_hover_color=COLORS["accent_cyan"],
            progress_color=COLORS["accent_blue"],
            fg_color=COLORS["bg_input"],
            command=self._on_interval_change,
        )
        self._interval_slider.set(3)
        self._interval_slider.pack(padx=16, fill="x")

        self._interval_label = ctk.CTkLabel(
            sidebar, text="3.0s",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self._interval_label.pack(padx=20)

        # 底部版本与主题切换
        bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", pady=12, fill="x")

        theme_icon = "☀️ 切换亮色" if self._appearance_mode_state == "Dark" else "🌙 切换暗色"
        self._theme_btn = ctk.CTkButton(
            bottom_frame, text=theme_icon,
            font=ctk.CTkFont(size=11),
            width=120, height=28, corner_radius=6,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"],
            command=self._toggle_theme,
        )
        self._theme_btn.pack(pady=(0, 8))

        ctk.CTkLabel(
            bottom_frame, text="v0.1.0 · OpenWukong",
            font=ctk.CTkFont(size=9),
            text_color=COLORS["text_dim"],
        ).pack()

    # ══════════════════════════════════════════
    #  右侧主区域
    # ══════════════════════════════════════════

    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nswe", padx=0, pady=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)   # IDE 状态面板
        main.grid_rowconfigure(2, weight=1)   # 日志面板

        # ── 顶部状态栏 ──
        top_bar = ctk.CTkFrame(main, height=60, fg_color=COLORS["bg_card"], corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        top_bar.grid_propagate(False)
        top_bar.grid_columnconfigure(1, weight=1)

        # 模式描述
        self._mode_title = ctk.CTkLabel(
            top_bar, text=MODES["scan"]["label"],
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self._mode_title.grid(row=0, column=0, padx=(24, 8), pady=(10, 0), sticky="w")

        self._mode_desc = ctk.CTkLabel(
            top_bar, text=MODES["scan"]["desc"],
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self._mode_desc.grid(row=1, column=0, padx=(24, 8), pady=(0, 8), sticky="w")

        # 运行时间
        self._uptime_label = ctk.CTkLabel(
            top_bar, text="⏱ 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=14),
            text_color=COLORS["text_secondary"],
        )
        self._uptime_label.grid(row=0, column=1, rowspan=2, padx=8, sticky="e")

        # 启动/停止按钮
        self._start_btn = ctk.CTkButton(
            top_bar, text="▶  启动",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            width=120, height=38, corner_radius=10,
            fg_color=COLORS["accent_blue"],
            hover_color=("#2563eb", "#5d8ceb"),
            text_color=COLORS["text_bright"],
            command=self._toggle_run,
        )
        self._start_btn.grid(row=0, column=2, rowspan=2, padx=(8, 24), sticky="e")

        # ── IDE 状态面板 ──
        ide_frame = ctk.CTkFrame(main, fg_color="transparent")
        ide_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(12, 4))
        ide_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(ide_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame, text="IDE 状态 · IDE STATUS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, sticky="w")

        self._ide_count_label = ctk.CTkLabel(
            header_frame, text="0 projects",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
        )
        self._ide_count_label.grid(row=0, column=1, sticky="e")

        self._ide_scroll = ctk.CTkScrollableFrame(
            ide_frame, fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["bg_hover"],
            scrollbar_button_hover_color=COLORS["accent_blue"],
        )
        self._ide_scroll.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        ide_frame.grid_rowconfigure(1, weight=1)

        # 默认空状态
        self._ide_empty_label = ctk.CTkLabel(
            self._ide_scroll,
            text="点击「启动」开始扫描 IDE 窗口 ...\nClick Start to scan IDE windows",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"],
            justify="center",
        )
        self._ide_empty_label.pack(pady=40, expand=True)

        self._ide_cards: list[ctk.CTkFrame] = []

        # ── 日志面板 ──
        log_frame = ctk.CTkFrame(main, fg_color="transparent")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(4, 12))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            log_header, text="运行日志 · LOG",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, sticky="w")

        self._log_clear_btn = ctk.CTkButton(
            log_header, text="清空",
            font=ctk.CTkFont(size=10),
            width=50, height=22, corner_radius=6,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            command=self._clear_log,
        )
        self._log_clear_btn.grid(row=0, column=1, sticky="e")

        self._log_box = ctk.CTkTextbox(
            log_frame, height=180,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["bg_hover"],
            wrap="word",
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        # 配置日志颜色标签
        self._update_log_tags()

    def _update_log_tags(self):
        is_dark = self._appearance_mode_state == "Dark"
        for tag_name, color in LOG_COLORS.items():
            fg = color[1] if is_dark else color[0]
            self._log_box.tag_config(tag_name, foreground=fg)

    # ══════════════════════════════════════════
    #  模式切换
    # ══════════════════════════════════════════

    def _select_mode(self, mode_key: str):
        if self._running:
            self._push_log("请先停止当前任务再切换模式", "warning")
            return
        self._current_mode = mode_key
        self._highlight_mode(mode_key)
        self._mode_title.configure(text=MODES[mode_key]["label"])
        self._mode_desc.configure(text=MODES[mode_key]["desc"])

    def _highlight_mode(self, active_key: str):
        for key, btn in self._mode_buttons.items():
            if key == active_key:
                btn.configure(
                    fg_color=COLORS["accent_blue"],
                    text_color=COLORS["text_bright"],
                    hover_color=("#2563eb", "#5d8ceb"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_primary"],
                    hover_color=COLORS["bg_hover"],
                )

    # ══════════════════════════════════════════
    #  主题切换
    # ══════════════════════════════════════════

    def _toggle_theme(self):
        new_mode = "Light" if self._appearance_mode_state == "Dark" else "Dark"
        self._appearance_mode_state = new_mode
        ctk.set_appearance_mode(new_mode)
        self._update_log_tags()
        # 更新按钮图标
        if new_mode == "Dark":
            self._theme_btn.configure(text="☀️ 切换亮色")
        else:
            self._theme_btn.configure(text="🌙 切换暗色")

    # ══════════════════════════════════════════
    #  启动/停止逻辑
    # ══════════════════════════════════════════

    def _toggle_run(self):
        if self._running:
            self._stop_task()
        else:
            self._start_task()

    def _start_task(self):
        self._running = True
        self._stop_event.clear()
        self._start_time = time.time()
        self._start_btn.configure(
            text="⏹  停止",
            fg_color=COLORS["accent_red"],
            hover_color=("#dc2626", "#d85a6e"),
        )
        # 禁用模式切换
        for btn in self._mode_buttons.values():
            btn.configure(state="disabled")
        self._target_entry.configure(state="disabled")

        mode = self._current_mode
        self._push_log(f"▶ 启动模式: {MODES[mode]['label']}", "success")

        target_process = self._target_entry.get().strip() or "Antigravity.exe"
        interval = self._interval_slider.get()

        self._worker_thread = threading.Thread(
            target=self._worker,
            args=(mode, target_process, interval),
            daemon=True,
        )
        self._worker_thread.start()

    def _stop_task(self):
        self._push_log("⏹ 正在停止...", "warning")
        self._stop_event.set()
        self._running = False
        self._start_btn.configure(
            text="▶  启动",
            fg_color=COLORS["accent_blue"],
            hover_color=("#2563eb", "#5d8ceb"),
        )
        # 恢复模式切换
        for btn in self._mode_buttons.values():
            btn.configure(state="normal")
        self._target_entry.configure(state="normal")
        self._highlight_mode(self._current_mode)

    # ══════════════════════════════════════════
    #  后台工作线程
    # ══════════════════════════════════════════

    def _worker(self, mode: str, target_process: str, interval: float):
        """后台线程：执行不同模式的监控/督导"""
        try:
            if mode == "scan":
                self._worker_scan()
            elif mode == "monitor":
                self._worker_monitor(target_process, interval)
            elif mode == "demo":
                self._worker_supervisor(target_process, interval, dry_run=True)
            elif mode == "supervisor":
                self._worker_supervisor(target_process, interval, dry_run=False)
        except Exception as e:
            self._push_log(f"❌ 工作线程异常: {e}", "error")
        finally:
            if self._running:
                self._stop_event.set()
                self._running = False
                # 通过 queue 触发 UI 更新
                self._log_queue.put(("__STOPPED__", ""))

    def _worker_scan(self):
        """单次扫描模式"""
        self._push_log("正在扫描所有 IDE 窗口...", "info")

        from openwukong.monitor.ai_monitor import MultiProjectAIMonitor
        monitor = MultiProjectAIMonitor()
        states = monitor.scan_all()

        self._ide_states = states
        self._log_queue.put(("__UPDATE_IDE__", states))

        if not states:
            self._push_log("未发现任何 IDE 进程", "warning")
        else:
            self._push_log(f"✅ 发现 {len(states)} 个 IDE 项目", "success")
            for s in states:
                model_str = f" [{s.ai_model}]" if s.ai_model else ""
                progress_str = f" {s.progress_text}" if s.progress_text else ""
                self._push_log(
                    f"  {s.project_name} (PID:{s.pid}) "
                    f"→ {s.ai_status.value}{model_str}{progress_str}",
                    "event"
                )
        self._push_log("扫描完成", "success")

    def _worker_monitor(self, target_process: str, interval: float):
        """持续监控模式"""
        self._push_log(f"持续监控启动 | 目标: {target_process} | 间隔: {interval}s", "info")

        from openwukong.monitor.ai_monitor import MultiProjectAIMonitor
        monitor = MultiProjectAIMonitor()
        cycle = 0

        while not self._stop_event.is_set():
            cycle += 1
            try:
                states = monitor.scan_all()
                self._ide_states = states
                self._log_queue.put(("__UPDATE_IDE__", states))

                if cycle % 5 == 1:
                    running = sum(1 for s in states if s.ai_status.value == "running")
                    idle = sum(1 for s in states if s.ai_status.value == "idle")
                    error = sum(1 for s in states if s.ai_status.value == "error")
                    self._push_log(
                        f"[#{cycle}] {len(states)} 项目 | "
                        f"🔄 {running} 运行 · ⚪ {idle} 空闲 · ❌ {error} 错误",
                        "info"
                    )

            except Exception as e:
                self._push_log(f"轮询异常: {e}", "error")

            self._stop_event.wait(interval)

        self._push_log("持续监控已停止", "warning")

    def _worker_supervisor(self, target_process: str, interval: float, dry_run: bool):
        """督导模式 (演示/全时)"""
        mode_name = "演示模式" if dry_run else "全时督导"
        self._push_log(f"⚡ {mode_name}启动 | 目标: {target_process} | 间隔: {interval}s", "info")

        from openwukong.monitor.ai_monitor import MultiProjectAIMonitor, AIStatus

        monitor = MultiProjectAIMonitor()
        prev_states: dict[int, str] = {}
        steer_count = 0
        cycle = 0

        # 加载 goals 配置
        goals_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "goals.json"
        )
        goals_path = os.path.normpath(goals_path)
        goals_data = None

        if os.path.exists(goals_path):
            try:
                with open(goals_path, "r", encoding="utf-8") as f:
                    goals_data = json.load(f)
                goal_count = len(goals_data.get("goals", []))
                self._push_log(f"📋 加载 goals.json: {goal_count} 个任务目标", "success")
            except Exception as e:
                self._push_log(f"goals.json 加载失败: {e}", "warning")
        else:
            self._push_log(f"未找到 goals.json ({goals_path}), 使用默认逻辑", "warning")

        while not self._stop_event.is_set():
            cycle += 1
            try:
                states = monitor.scan_all()
                self._ide_states = states
                self._log_queue.put(("__UPDATE_IDE__", states))

                for s in states:
                    curr = s.ai_status.value
                    prev = prev_states.get(s.pid, "")

                    # 生命周期事件检测
                    if prev == "" and curr == "running":
                        self._push_log(
                            f"🆕 SPAWNED: {s.project_name} (PID:{s.pid}) Agent 开始运行",
                            "event"
                        )
                    elif prev == "running" and curr == "idle":
                        self._push_log(
                            f"✅ COMPLETED: {s.project_name} Agent 完成一轮",
                            "success"
                        )
                        if not dry_run:
                            self._push_log(
                                f"  → 检查目标达标情况...",
                                "info"
                            )
                            try:
                                # 动态加载最新目标
                                current_goal = None
                                if goals_data and "goals" in goals_data:
                                    for g in goals_data["goals"]:
                                        kw = g.get("window_match", "").lower()
                                        if not kw: continue

                                        # 使用全局别名常量
                                        search_terms = [kw]
                                        for alias, target in PROJECT_ALIASES.items():
                                            if alias in kw or target in kw:
                                                if target not in search_terms: search_terms.append(target)
                                                if alias not in search_terms: search_terms.append(alias)

                                        matched = False
                                        for term in search_terms:
                                            if term in s.project_name.lower() or term in s.window_title.lower():
                                                matched = True
                                                break

                                        if not matched:
                                            highest = 0.0
                                            for term in search_terms:
                                                r_name = difflib.SequenceMatcher(None, term, s.project_name.lower()).ratio()
                                                r_title = difflib.SequenceMatcher(None, term, s.window_title.lower()).ratio()
                                                highest = max(highest, r_name, r_title)
                                            if highest > 0.4:
                                                matched = True

                                        if matched:
                                            current_goal = g
                                            break

                                if not current_goal:
                                    self._push_log(f"  ⚠️ 未找到匹配的 goal，按默认重试", "warning")
                                    retry_cmd = "继续执行"
                                    success_kw = []
                                else:
                                    retry_cmd = current_goal.get("retry_command", "继续执行")
                                    success_kw = current_goal.get("success_keywords", [])

                                # 读取对话判断是否达标
                                from openwukong.supervisor.agent_supervisor import SteerOperator
                                from pywinauto import Application
                                app = Application(backend="uia").connect(process=s.pid)
                                conv = SteerOperator.read_conversation(app)

                                achieved = False
                                if success_kw and any(kw.lower() in conv.lower() for kw in success_kw):
                                    achieved = True

                                if achieved:
                                    self._push_log(f"  🏆 目标已达成!", "success")
                                else:
                                    steer_count += 1
                                    self._push_log(
                                        f"  📤 STEER #{steer_count}: 发送续发指令 - {retry_cmd[:20]}...",
                                        "steer"
                                    )
                                    SteerOperator.steer(app, retry_cmd, s.pid, cooldown=10.0)
                            except Exception as e:
                                self._push_log(f"  ❗️ 执行督导判定异常: {e}", "error")
                        else:
                            self._push_log(
                                f"  👀 [DRY] 演示模式：跳过 steer",
                                "info"
                            )
                    elif prev == "idle" and curr == "error":
                        self._push_log(
                            f"❌ ERROR: {s.project_name} Agent 报错",
                            "error"
                        )
                    elif prev == "running" and curr == "error":
                        self._push_log(
                            f"❌ CRASH: {s.project_name} Agent 运行中出错",
                            "error"
                        )

                    prev_states[s.pid] = curr

                # 周期性状态汇报
                if cycle % 10 == 1:
                    running = sum(1 for s in states if s.ai_status.value == "running")
                    self._push_log(
                        f"[Cycle #{cycle}] {len(states)} 项目活跃 | "
                        f"{running} 运行中 | Steers: {steer_count}",
                        "info"
                    )

            except Exception as e:
                self._push_log(f"督导轮询异常: {e}", "error")

            self._stop_event.wait(interval)

        self._push_log(f"{mode_name}已停止 | 共 {steer_count} 次 steer", "warning")

    # ══════════════════════════════════════════
    #  日志系统
    # ══════════════════════════════════════════

    def _push_log(self, msg: str, level: str = "info"):
        """线程安全地推送日志"""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put(("log", f"[{ts}] {msg}", level))

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ══════════════════════════════════════════
    #  UI 定时刷新
    # ══════════════════════════════════════════

    def _poll_ui(self):
        """主线程定时消费 queue 更新 UI"""
        try:
            while True:
                item = self._log_queue.get_nowait()

                if item[0] == "__UPDATE_IDE__":
                    self._render_ide_cards(item[1])
                elif item[0] == "__STOPPED__":
                    self._stop_task()
                elif item[0] == "log":
                    _, msg, level = item
                    self._append_log(msg, level)

        except queue.Empty:
            pass

        # 更新运行时间
        if self._running and self._start_time:
            elapsed = time.time() - self._start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self._uptime_label.configure(
                text=f"⏱ {h:02d}:{m:02d}:{s:02d}",
                text_color=COLORS["accent_green"],
            )
        else:
            self._uptime_label.configure(
                text="⏱ 00:00:00",
                text_color=COLORS["text_secondary"],
            )

        self.after(200, self._poll_ui)

    def _append_log(self, msg: str, level: str = "info"):
        """追加日志到文本框"""
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n", level)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    # ══════════════════════════════════════════
    #  IDE 状态卡片渲染
    # ══════════════════════════════════════════

    def _render_ide_cards(self, states: list):
        """渲染 IDE 状态卡片"""
        # 清理旧卡片
        for card in self._ide_cards:
            card.destroy()
        self._ide_cards.clear()

        if hasattr(self, "_ide_empty_label") and self._ide_empty_label.winfo_exists():
            self._ide_empty_label.destroy()

        self._ide_count_label.configure(text=f"{len(states)} projects")

        if not states:
            self._ide_empty_label = ctk.CTkLabel(
                self._ide_scroll,
                text="未发现 IDE 进程\nNo IDE processes detected",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_dim"],
                justify="center",
            )
            self._ide_empty_label.pack(pady=40, expand=True)
            return

        for s in states:
            card = self._create_ide_card(s)
            card.pack(fill="x", padx=8, pady=4)
            self._ide_cards.append(card)

    def _create_ide_card(self, state) -> ctk.CTkFrame:
        """创建单个 IDE 状态卡片"""
        status_val = state.ai_status.value
        style = STATUS_STYLE.get(status_val, STATUS_STYLE["unknown"])

        card = ctk.CTkFrame(
            self._ide_scroll,
            fg_color=COLORS["bg_dark"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            height=72,
        )
        card.grid_columnconfigure(1, weight=1)
        card.grid_propagate(False)

        # 状态指示灯
        indicator = ctk.CTkLabel(
            card, text=style["emoji"],
            font=ctk.CTkFont(size=20),
            width=36,
        )
        indicator.grid(row=0, column=0, rowspan=2, padx=(12, 4), pady=8)

        # 项目名 + PID
        name_text = f"{state.project_name}"
        name_label = ctk.CTkLabel(
            card, text=name_text,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        name_label.grid(row=0, column=1, sticky="sw", padx=4, pady=(10, 0))

        # 状态 + 模型 + 进度
        info_parts = [
            f"{state.process_name} (PID:{state.pid})",
            f"· {style['label']}",
        ]
        if state.ai_model:
            info_parts.append(f"· {state.ai_model}")
        if state.progress_text:
            info_parts.append(f"· {state.progress_text}")

        info_label = ctk.CTkLabel(
            card, text="  ".join(info_parts),
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=style["color"],
            anchor="w",
        )
        info_label.grid(row=1, column=1, sticky="nw", padx=4, pady=(0, 10))

        # 右侧进度条（如果有进度）
        if state.progress_text:
            try:
                pct_str = state.progress_text.replace("%", "")
                pct = float(pct_str) / 100.0
                progress = ctk.CTkProgressBar(
                    card, width=80, height=8,
                    progress_color=style["color"],
                    fg_color=COLORS["bg_input"],
                    corner_radius=4,
                )
                progress.set(pct)
                progress.grid(row=0, column=2, rowspan=2, padx=(8, 16), pady=8, sticky="e")
            except (ValueError, TypeError):
                pass

        return card

    # ══════════════════════════════════════════
    #  设置回调
    # ══════════════════════════════════════════

    def _on_interval_change(self, value: float):
        self._interval_label.configure(text=f"{value:.1f}s")

    # ══════════════════════════════════════════
    #  关闭清理
    # ══════════════════════════════════════════

    def _on_close(self):
        self._stop_event.set()
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        self.destroy()


def main():
    """启动 OpenWukong 控制面板"""
    app = WukongApp()
    app.mainloop()


if __name__ == "__main__":
    main()
