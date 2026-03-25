# -*- coding: utf-8 -*-
"""
process_tree.py - 进程树管理模块

通过 psutil + pywinauto 实现:
- 枚举所有带 GUI 窗口的进程
- 通过 PID / 进程名 / 窗口标题 精确定位目标进程
- 获取进程的详细元信息（路径、CPU、内存等）
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import psutil
from pywinauto import Desktop
from pywinauto.application import Application


@dataclasses.dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    exe_path: str
    window_titles: list[str]
    cpu_percent: float
    memory_mb: float

    def __str__(self) -> str:
        titles = ", ".join(self.window_titles[:3])
        return f"[PID={self.pid}] {self.name} | windows: {titles}"


class ProcessTree:
    """
    进程树管理器

    核心能力:
    - list_gui_processes():   列出所有有窗口的进程
    - find_by_name(name):     按进程名查找
    - find_by_title(keyword): 按窗口标题关键词查找
    - find_by_pid(pid):       按 PID 精确定位
    - connect(pid):           通过 PID 连接进程并返回 pywinauto Application
    """

    def __init__(self, backend: str = "uia"):
        self._backend = backend
        self._desktop = Desktop(backend=backend)

    def list_gui_processes(self) -> list[ProcessInfo]:
        """列出所有带 GUI 窗口的进程"""
        windows = self._desktop.windows()
        pid_map: dict[int, list[str]] = {}

        for w in windows:
            try:
                pid = w.process_id()
                title = w.window_text()
                if pid not in pid_map:
                    pid_map[pid] = []
                if title:
                    pid_map[pid].append(title)
            except Exception:
                continue

        result: list[ProcessInfo] = []
        for pid, titles in pid_map.items():
            try:
                proc = psutil.Process(pid)
                info = ProcessInfo(
                    pid=pid,
                    name=proc.name(),
                    exe_path=proc.exe(),
                    window_titles=titles,
                    cpu_percent=proc.cpu_percent(interval=0),
                    memory_mb=proc.memory_info().rss / (1024 * 1024),
                )
                result.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return sorted(result, key=lambda p: p.name.lower())

    def find_by_name(self, name: str) -> list[ProcessInfo]:
        """按进程名查找（不区分大小写，支持部分匹配）"""
        name_lower = name.lower()
        return [p for p in self.list_gui_processes() if name_lower in p.name.lower()]

    def find_by_title(self, keyword: str) -> list[ProcessInfo]:
        """按窗口标题关键词查找"""
        keyword_lower = keyword.lower()
        return [
            p for p in self.list_gui_processes()
            if any(keyword_lower in t.lower() for t in p.window_titles)
        ]

    def find_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """按 PID 精确查找"""
        matches = [p for p in self.list_gui_processes() if p.pid == pid]
        return matches[0] if matches else None

    def connect(self, pid: int, retries: int = 3) -> Application:
        """
        通过 PID 连接到目标进程，返回 pywinauto Application 对象

        Args:
            pid: 目标进程 PID
            retries: 连接失败时的重试次数
        """
        import time as _time

        last_err = None
        for attempt in range(retries):
            try:
                return Application(backend=self._backend).connect(process=pid)
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    _time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Failed to connect to PID {pid} after {retries} attempts: {last_err}")

    def is_alive(self, pid: int) -> bool:
        """检查进程是否仍然存活"""
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def reconnect(self, pid: int) -> Optional[Application]:
        """
        断线重连: 检查进程是否存活，若存活则重新连接

        Returns:
            Application 对象（成功）或 None（进程不存在）
        """
        if not self.is_alive(pid):
            return None
        try:
            return self.connect(pid)
        except Exception:
            return None

    def connect_by_name(self, name: str) -> tuple[ProcessInfo, Application]:
        """通过进程名连接（取第一个匹配的）"""
        procs = self.find_by_name(name)
        if not procs:
            raise ValueError(f"No process found matching: {name}")
        proc = procs[0]
        app = self.connect(proc.pid)
        return proc, app

    def connect_by_title(self, keyword: str) -> tuple[ProcessInfo, Application]:
        """通过窗口标题关键词连接"""
        procs = self.find_by_title(keyword)
        if not procs:
            raise ValueError(f"No window found matching: {keyword}")
        proc = procs[0]
        app = self.connect(proc.pid)
        return proc, app
