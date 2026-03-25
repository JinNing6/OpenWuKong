# -*- coding: utf-8 -*-
"""
ide_monitor.py - IDE 专用监控器

针对 VS Code / IntelliJ IDEA / Antigravity 等 IDE 的控件树解析:
- 当前活跃文件提取
- 终端输出读取
- 打开的标签页列表
- 编辑器内容抓取
- 前后快照 diff（只报告变化部分）
"""

from __future__ import annotations

import time
import dataclasses
from typing import Optional

import psutil
from pywinauto.application import Application
from pywinauto import Desktop

from logger import get_logger, log_event

logger = get_logger("ide_monitor")


@dataclasses.dataclass
class IDEState:
    """多窗口 IDE 状态快照"""
    timestamp: float
    pid: int
    process_name: str
    window_title: str              # 焦点窗口标题
    all_window_titles: list[str]   # 所有窗口标题
    focused_window_index: int      # 焦点窗口在列表中的位置
    active_file: str
    open_tabs: list[str]
    terminal_texts: list[str]
    editor_text: str
    total_elements: int
    element_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "pid": self.pid,
            "process_name": self.process_name,
            "window_title": self.window_title[:100],
            "all_windows": len(self.all_window_titles),
            "focused_index": self.focused_window_index,
            "active_file": self.active_file,
            "open_tabs": self.open_tabs[:20],
            "terminal_count": len(self.terminal_texts),
            "editor_text_len": len(self.editor_text),
            "total_elements": self.total_elements,
        }


@dataclasses.dataclass
class IDEDiff:
    """前后快照 diff"""
    file_changed: bool
    tabs_added: list[str]
    tabs_removed: list[str]
    terminal_new_lines: int
    title_changed: bool
    old_file: str = ""
    new_file: str = ""
    old_title: str = ""
    new_title: str = ""

    @property
    def has_changes(self) -> bool:
        return (
            self.file_changed
            or self.tabs_added
            or self.tabs_removed
            or self.terminal_new_lines > 0
            or self.title_changed
        )

    def to_dict(self) -> dict:
        return {
            "file_changed": self.file_changed,
            "old_file": self.old_file,
            "new_file": self.new_file,
            "tabs_added": self.tabs_added[:10],
            "tabs_removed": self.tabs_removed[:10],
            "terminal_new_lines": self.terminal_new_lines,
            "title_changed": self.title_changed,
        }


# IDE 配置：不同 IDE 的控件特征
IDE_PROFILES = {
    "vscode": {
        "process_names": ["code.exe", "Code.exe"],
        "title_separator": " - ",
        "file_index": 0,  # 标题中文件名的位置
        "tab_control_type": "TabItem",
        "terminal_name_contains": "Terminal",
        "editor_control_type": "Document",
    },
    "antigravity": {
        "process_names": ["Antigravity.exe"],
        "title_separator": " - ",
        "file_index": -1,  # 标题格式: "project - Antigravity - file"
        "tab_control_type": "TabItem",
        "terminal_name_contains": "Terminal",
        "editor_control_type": "Edit",
    },
    "idea": {
        "process_names": ["idea64.exe", "idea.exe"],
        "title_separator": " \u2013 ",
        "file_index": -1,
        "tab_control_type": "TabItem",
        "terminal_name_contains": "Terminal",
        "editor_control_type": "Edit",
    },
    "generic": {
        "process_names": [],
        "title_separator": " - ",
        "file_index": 0,
        "tab_control_type": "TabItem",
        "terminal_name_contains": "Terminal",
        "editor_control_type": "Edit",
    },
}


class IDEMonitor:
    """
    IDE 状态监控器

    使用示例:
        monitor = IDEMonitor("Antigravity.exe")
        monitor.connect()

        # 获取当前 IDE 状态
        state = monitor.get_state()
        print(state.active_file, state.open_tabs)

        # 持续检测变化
        diff = monitor.detect_changes()
        if diff.has_changes:
            print(f"File changed: {diff.old_file} -> {diff.new_file}")
    """

    def __init__(self, target_process: str, backend: str = "uia"):
        self._target = target_process
        self._backend = backend
        self._desktop = Desktop(backend=backend)
        self._app: Optional[Application] = None
        self._pid: int = 0
        self._profile = self._match_profile(target_process)
        self._last_state: Optional[IDEState] = None
        self._connected = False

    def _match_profile(self, process_name: str) -> dict:
        """匹配 IDE 配置文件"""
        pn_lower = process_name.lower()
        for name, profile in IDE_PROFILES.items():
            if name == "generic":
                continue
            for pn in profile["process_names"]:
                if pn.lower() in pn_lower or pn_lower in pn.lower():
                    log_event(logger, f"Matched IDE profile: {name}", event_type="profile_match")
                    return profile
        return IDE_PROFILES["generic"]

    def connect(self) -> bool:
        """连接到目标 IDE 进程"""
        try:
            windows = self._desktop.windows()
            for w in windows:
                try:
                    pid = w.process_id()
                    proc = psutil.Process(pid)
                    if self._target.lower() in proc.name().lower():
                        self._pid = pid
                        self._app = Application(backend=self._backend).connect(process=pid)
                        self._connected = True
                        log_event(
                            logger,
                            f"Connected to {proc.name()} (PID: {pid})",
                            event_type="ide_connected",
                            pid=pid,
                            process_name=proc.name(),
                        )
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception:
                    continue

            log_event(logger, f"IDE process not found: {self._target}", level=30)
            return False
        except Exception as e:
            log_event(logger, f"Connection failed: {e}", level=40)
            return False

    def reconnect(self) -> bool:
        """断线重连"""
        self._app = None
        self._connected = False
        return self.connect()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pid(self) -> int:
        return self._pid

    def is_alive(self) -> bool:
        """检查目标进程是否仍存活"""
        if not self._pid:
            return False
        try:
            proc = psutil.Process(self._pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_state(self) -> Optional[IDEState]:
        """
        获取 IDE 多窗口状态快照

        遍历目标进程的所有窗口，检测焦点窗口，
        从焦点窗口提取标签页/终端/编辑器状态。
        """
        if not self._connected or not self._app:
            return None

        try:
            # 枚举所有窗口
            all_windows = []
            try:
                all_windows = self._app.windows()
            except Exception:
                # fallback 到单窗口
                try:
                    all_windows = [self._app.top_window()]
                except Exception:
                    pass

            if not all_windows:
                log_event(logger, "No windows found", level=30)
                return None

            # 收集所有窗口标题
            all_titles = []
            for w in all_windows:
                try:
                    t = w.window_text() or ""
                    if t and "Program Manager" not in t:
                        all_titles.append(t)
                except Exception:
                    continue

            # 识别焦点窗口
            focused_win = None
            focused_idx = 0
            try:
                # 方法1: 尝试 app.active_()
                focused_win = self._app.active_()
            except Exception:
                pass

            if focused_win is None:
                try:
                    # 方法2: 检查每个窗口的 has_focus
                    for i, w in enumerate(all_windows):
                        try:
                            if w.has_focus():
                                focused_win = w
                                focused_idx = i
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            if focused_win is None:
                # 方法3: 回退到 top_window
                try:
                    focused_win = self._app.top_window()
                except Exception:
                    focused_win = all_windows[0] if all_windows else None

            if focused_win is None:
                return None

            # 从焦点窗口提取状态
            title = ""
            try:
                title = focused_win.window_text() or ""
            except Exception:
                pass

            # 先尝试从焦点窗口获取 descendants，服务于 Tab/Terminal/Editor 提取
            descendants = []
            try:
                descendants = focused_win.descendants()
            except Exception:
                pass

            active_file = self._extract_active_file(title)
            tabs = self._extract_tabs(descendants)
            terminals = self._extract_terminals(descendants)
            editor_text = self._extract_editor(descendants)

            # 元素统计
            type_counts: dict[str, int] = {}
            for d in descendants:
                try:
                    ct = d.element_info.control_type or "Unknown"
                    type_counts[ct] = type_counts.get(ct, 0) + 1
                except Exception:
                    pass

            # 如果焦点窗口没有标签页，从其他窗口也收集
            if not tabs:
                for w in all_windows:
                    if w is focused_win:
                        continue
                    try:
                        other_desc = w.descendants(control_type=self._profile["tab_control_type"])
                        for d in other_desc:
                            try:
                                name = d.element_info.name or ""
                                if name and len(name) > 1:
                                    tabs.append(name)
                            except Exception:
                                continue
                    except Exception:
                        continue
                    if tabs:
                        break

            state = IDEState(
                timestamp=time.time(),
                pid=self._pid,
                process_name=self._target,
                window_title=title,
                all_window_titles=all_titles,
                focused_window_index=focused_idx,
                active_file=active_file,
                open_tabs=tabs,
                terminal_texts=terminals,
                editor_text=editor_text,
                total_elements=len(descendants),
                element_counts=type_counts,
            )

            return state

        except Exception as e:
            log_event(logger, f"Failed to get IDE state: {e}", level=30)
            self._connected = False
            return None

    def detect_changes(self) -> Optional[IDEDiff]:
        """
        多信号增量变化检测

        Phase 1: 多窗口快速指纹（~10ms）
          - 读取所有窗口标题列表 + 焦点窗口标题
          - 两者都未变 → 返回"无变化"

        Phase 2: 深度状态获取（仅在有变化时执行）
          - 窗口标题变化 = 可能切换了文件
          - 焦点窗口变化 = 切换了窗口
          - 窗口数量变化 = 打开/关闭了窗口
        """
        if not self._connected or not self._app:
            return None

        # ─── Phase 1: 多窗口快速指纹 ───
        try:
            quick_titles = []
            quick_focused = ""

            try:
                all_wins = self._app.windows()
            except Exception:
                all_wins = []
                try:
                    all_wins = [self._app.top_window()]
                except Exception:
                    pass

            for w in all_wins:
                try:
                    t = w.window_text() or ""
                    if t and "Program Manager" not in t:
                        quick_titles.append(t)
                except Exception:
                    continue

            # 检测焦点窗口
            try:
                fw = self._app.active_()
                if fw:
                    quick_focused = fw.window_text() or ""
            except Exception:
                if quick_titles:
                    quick_focused = quick_titles[0]

        except Exception as e:
            log_event(logger, f"Quick detect failed: {e}", level=30)
            self._connected = False
            return None

        if self._last_state is not None:
            old = self._last_state
            titles_unchanged = (
                sorted(quick_titles) == sorted(old.all_window_titles)
            )
            focus_unchanged = (
                quick_focused == old.window_title
            )

            if titles_unchanged and focus_unchanged:
                # 多信号验证通过：窗口列表+焦点都没变
                return IDEDiff(
                    file_changed=False,
                    tabs_added=[],
                    tabs_removed=[],
                    terminal_new_lines=0,
                    title_changed=False,
                )

        # ─── Phase 2: 深度状态获取 ───
        current = self.get_state()
        if current is None:
            return None

        if self._last_state is None:
            self._last_state = current
            return IDEDiff(
                file_changed=False,
                tabs_added=[],
                tabs_removed=[],
                terminal_new_lines=0,
                title_changed=False,
            )

        old = self._last_state

        # 文件变化
        file_changed = old.active_file != current.active_file

        # 标签页变化
        old_tabs = set(old.open_tabs)
        new_tabs = set(current.open_tabs)
        tabs_added = list(new_tabs - old_tabs)
        tabs_removed = list(old_tabs - new_tabs)

        # 终端新输出
        old_term_len = sum(len(t) for t in old.terminal_texts)
        new_term_len = sum(len(t) for t in current.terminal_texts)
        terminal_new_lines = max(0, new_term_len - old_term_len)

        # 标题变化
        title_changed = old.window_title != current.window_title

        diff = IDEDiff(
            file_changed=file_changed,
            tabs_added=tabs_added,
            tabs_removed=tabs_removed,
            terminal_new_lines=terminal_new_lines,
            title_changed=title_changed,
            old_file=old.active_file,
            new_file=current.active_file,
            old_title=old.window_title[:50],
            new_title=current.window_title[:50],
        )

        self._last_state = current
        return diff

    def _extract_active_file(self, title: str) -> str:
        """从窗口标题提取当前活跃文件"""
        if not title:
            return ""

        sep = self._profile["title_separator"]
        parts = title.split(sep)
        if not parts:
            return title

        idx = self._profile["file_index"]
        try:
            return parts[idx].strip()
        except IndexError:
            return parts[0].strip()

    def _extract_tabs(self, descendants) -> list[str]:
        """从控件树提取打开的标签页"""
        tab_type = self._profile["tab_control_type"]
        tabs = []
        for d in descendants:
            try:
                if d.element_info.control_type == tab_type:
                    name = d.element_info.name or ""
                    if name and len(name) > 1:
                        tabs.append(name)
            except Exception:
                continue
        return tabs

    def _extract_terminals(self, descendants) -> list[str]:
        """从控件树提取终端文本"""
        keyword = self._profile["terminal_name_contains"]
        terminals = []
        for d in descendants:
            try:
                name = d.element_info.name or ""
                ctrl_type = d.element_info.control_type or ""
                if keyword.lower() in name.lower() and ctrl_type in ("Edit", "Document", "Text"):
                    try:
                        text = d.window_text() or ""
                        if text and len(text) > 5:
                            terminals.append(text[:2000])
                    except Exception:
                        pass
            except Exception:
                continue
        return terminals

    def _extract_editor(self, descendants) -> str:
        """从控件树提取编辑器文本"""
        editor_type = self._profile["editor_control_type"]
        for d in descendants:
            try:
                ctrl_type = d.element_info.control_type or ""
                name = d.element_info.name or ""
                if ctrl_type == editor_type and "editor" in name.lower():
                    try:
                        return d.window_text()[:5000] or ""
                    except Exception:
                        pass
            except Exception:
                continue
        return ""
