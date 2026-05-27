# -*- coding: utf-8 -*-
"""
theme.py — OpenWukong 统一主题系统
=====================================
双主题配色：Tokyo Night（暗色）+ Ghostwhite Minimal（亮色）
所有颜色值使用 (light_color, dark_color) 元组格式，
CustomTkinter 根据当前 appearance_mode 自动选取对应颜色。

设计理念：Apple HIG + OpenAI 极简风格
"""

from __future__ import annotations

# ═══════════════════════════════════════════
#  全局配色系统（light, dark 元组）
# ═══════════════════════════════════════════

COLORS = {
    # 背景层级
    "bg_dark":       ("#f4f4f5", "#1a1b26"),     # 最深背景
    "bg_card":       ("#ffffff", "#24283b"),     # 卡片背景
    "bg_sidebar":    ("#e4e4e7", "#16161e"),     # 侧边栏
    "bg_input":      ("#f4f4f5", "#1f2335"),     # 输入框
    "bg_hover":      ("#d4d4d8", "#292e42"),     # 悬停态
    "bg_surface":    ("#f0f0f2", "#1f2335"),     # 表面色

    # 强调色
    "accent_blue":   ("#3b82f6", "#7aa2f7"),     # 主强调蓝
    "accent_cyan":   ("#06b6d4", "#2ac3de"),     # 运行态青
    "accent_green":  ("#10b981", "#9ece6a"),     # 成功绿
    "accent_orange": ("#f59e0b", "#e0af68"),     # 警告橙
    "accent_red":    ("#ef4444", "#f7768e"),     # 错误红
    "accent_purple": ("#8b5cf6", "#bb9af7"),     # 紫（督导指令）

    # 文字层级
    "text_primary":  ("#18181b", "#c0caf5"),     # 主文字
    "text_secondary": ("#52525b", "#565f89"),    # 次要文字
    "text_dim":      ("#a1a1aa", "#3b4261"),     # 最暗文字
    "text_bright":   ("#000000", "#ffffff"),     # 最亮文字

    # 边框
    "border":        ("#d4d4d8", "#292e42"),     # 通用边框
    "border_accent": ("#bfdbfe", "#3b4261"),     # 强调边框

    # 进度条
    "progress_bg":   ("#e4e4e7", "#3b4261"),     # 进度条底色
}


# ═══════════════════════════════════════════
#  运行模式定义
# ═══════════════════════════════════════════

MODES = {
    "scan":       {"label": "🔍 单次扫描 · Scan",        "desc": "扫描一次所有 IDE 窗口，显示 AI Agent 状态"},
    "monitor":    {"label": "📡 持续监控 · Monitor",     "desc": "持续轮询 IDE 状态变化，实时更新面板"},
    "demo":       {"label": "👀 悟空演示 · Demo",        "desc": "只读模式：显示悟空的监控与分析逻辑"},
    "supervisor": {"label": "⚡ 悟空全托管 · Wukong",  "desc": "自动托管续发：检测空闲/报错/超时时注入指令"},
}


# ═══════════════════════════════════════════
#  AI 状态 → 颜色 / Emoji 映射
# ═══════════════════════════════════════════

STATUS_STYLE = {
    "running":  {"color": COLORS["accent_cyan"],   "emoji": "🔄", "label": "Running"},
    "idle":     {"color": COLORS["text_secondary"], "emoji": "⚪", "label": "Idle"},
    "loading":  {"color": COLORS["accent_orange"],  "emoji": "⏳", "label": "Loading"},
    "error":    {"color": COLORS["accent_red"],     "emoji": "❌", "label": "Error"},
    "unknown":  {"color": COLORS["text_dim"],       "emoji": "❓", "label": "Unknown"},
}


# ═══════════════════════════════════════════
#  日志级别颜色
# ═══════════════════════════════════════════

LOG_COLORS = {
    "info":     COLORS["text_primary"],
    "success":  COLORS["accent_green"],
    "warning":  COLORS["accent_orange"],
    "error":    COLORS["accent_red"],
    "event":    COLORS["accent_cyan"],
    "steer":    COLORS["accent_purple"],
}


# ═══════════════════════════════════════════
#  悟空督导面板 状态颜色映射
# ═══════════════════════════════════════════

# 督导任务状态颜色（light, dark 元组）
STATUS_COLORS = {
    "pending":  ("#94a3b8", "#565f89"),
    "running":  ("#06b6d4", "#2ac3de"),
    "checking": ("#3b82f6", "#7aa2f7"),
    "achieved": ("#10b981", "#9ece6a"),
    "stalled":  ("#f59e0b", "#e0af68"),
    "failed":   ("#ef4444", "#f7768e"),
}

# 督导任务状态 Emoji
STATUS_EMOJI = {
    "pending":  "⏸",
    "running":  "🔄",
    "checking": "🔍",
    "achieved": "🏆",
    "stalled":  "⚠",
    "failed":   "❌",
}

# 事件类型标记
EVENT_MARKERS = {
    "spawned": "🟢", "running": "🔵", "completed": "✅",
    "error": "🔴", "stalled": "🟡", "steered": "📤",
    "goal-achieved": "🏆", "goal-failed": "❌", "killed": "💀",
    "match-failed": "🔍", "match-success": "🎯",
}
