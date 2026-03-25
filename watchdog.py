# -*- coding: utf-8 -*-
"""
watchdog.py - 自愈看门狗

持续监控 UIA Agent 及目标 IDE 的健康状态:
- IDE 进程存活检测
- 进程 PID 变化 → 自动重连
- UIA 连接健康心跳
- 本进程内存监控
- 累计错误计数 → 触发完整重置
"""

from __future__ import annotations

import os
import time
import dataclasses
from typing import Optional, Callable

import psutil

from logger import get_logger, log_event

logger = get_logger("watchdog")


@dataclasses.dataclass
class HealthStatus:
    """健康检查结果"""
    timestamp: float
    target_alive: bool
    target_pid: int
    pid_changed: bool
    connection_healthy: bool
    memory_mb: float
    memory_over_limit: bool
    consecutive_errors: int
    needs_reconnect: bool
    needs_full_reset: bool

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class Watchdog:
    """
    自愈看门狗

    使用示例:
        def reconnect_fn():
            monitor.reconnect()

        def reset_fn():
            # 完整重置所有组件
            ...

        dog = Watchdog(
            target_pid=1672,
            max_memory_mb=500,
            max_consecutive_errors=10,
            on_reconnect=reconnect_fn,
            on_full_reset=reset_fn,
        )

        # 在主循环中定期调用
        status = dog.check()
        if status.needs_reconnect:
            dog.trigger_reconnect()
    """

    def __init__(
        self,
        target_pid: int = 0,
        target_process_name: str = "",
        max_memory_mb: float = 500.0,
        max_consecutive_errors: int = 10,
        on_reconnect: Optional[Callable] = None,
        on_full_reset: Optional[Callable] = None,
    ):
        self._target_pid = target_pid
        self._target_process_name = target_process_name
        self._max_memory_mb = max_memory_mb
        self._max_consecutive_errors = max_consecutive_errors
        self._on_reconnect = on_reconnect
        self._on_full_reset = on_full_reset
        self._consecutive_errors = 0
        self._last_check_time = 0.0
        self._self_pid = os.getpid()
        self._total_reconnects = 0
        self._total_resets = 0

    @property
    def target_pid(self) -> int:
        return self._target_pid

    @target_pid.setter
    def target_pid(self, pid: int):
        self._target_pid = pid

    def record_error(self):
        """记录一次操作错误"""
        self._consecutive_errors += 1
        if self._consecutive_errors % 5 == 0:
            log_event(
                logger,
                f"Consecutive errors: {self._consecutive_errors}/{self._max_consecutive_errors}",
                event_type="error_count",
                level=30,
            )

    def record_success(self):
        """记录一次成功操作（重置错误计数）"""
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0

    def check(self) -> HealthStatus:
        """执行一次完整的健康检查"""
        now = time.time()
        self._last_check_time = now

        # 目标进程存活检测
        target_alive = self._check_target_alive()

        # PID 变化检测
        pid_changed = False
        if not target_alive and self._target_process_name:
            new_pid = self._find_process_by_name(self._target_process_name)
            if new_pid and new_pid != self._target_pid:
                pid_changed = True
                log_event(
                    logger,
                    f"Target PID changed: {self._target_pid} -> {new_pid}",
                    event_type="pid_change",
                    pid=new_pid,
                )
                self._target_pid = new_pid
                target_alive = True

        # UIA 连接心跳
        connection_healthy = target_alive  # 简化：进程活着就认为连接可用

        # 本进程内存
        memory_mb = self._get_self_memory_mb()
        memory_over_limit = memory_mb > self._max_memory_mb

        if memory_over_limit:
            log_event(
                logger,
                f"Memory over limit: {memory_mb:.1f}MB > {self._max_memory_mb}MB",
                event_type="memory_warning",
                level=30,
            )

        # 判断是否需要重连或完整重置
        needs_reconnect = pid_changed or (not target_alive and bool(self._target_process_name))
        needs_full_reset = (
            self._consecutive_errors >= self._max_consecutive_errors
            or memory_over_limit
        )

        status = HealthStatus(
            timestamp=now,
            target_alive=target_alive,
            target_pid=self._target_pid,
            pid_changed=pid_changed,
            connection_healthy=connection_healthy,
            memory_mb=memory_mb,
            memory_over_limit=memory_over_limit,
            consecutive_errors=self._consecutive_errors,
            needs_reconnect=needs_reconnect,
            needs_full_reset=needs_full_reset,
        )

        # 自动触发动作
        if needs_full_reset:
            self.trigger_full_reset()
        elif needs_reconnect:
            self.trigger_reconnect()

        return status

    def trigger_reconnect(self):
        """触发重连"""
        self._total_reconnects += 1
        log_event(
            logger,
            f"Triggering reconnect (#{self._total_reconnects})",
            event_type="reconnect",
        )
        if self._on_reconnect:
            try:
                self._on_reconnect()
                self._consecutive_errors = 0
            except Exception as e:
                log_event(logger, f"Reconnect failed: {e}", level=40)
                self._consecutive_errors += 1

    def trigger_full_reset(self):
        """触发完整重置"""
        self._total_resets += 1
        log_event(
            logger,
            f"Triggering full reset (#{self._total_resets}), "
            f"errors={self._consecutive_errors}, memory={self._get_self_memory_mb():.1f}MB",
            event_type="full_reset",
            level=30,
        )
        if self._on_full_reset:
            try:
                self._on_full_reset()
                self._consecutive_errors = 0
            except Exception as e:
                log_event(logger, f"Full reset failed: {e}", level=40)

    def _check_target_alive(self) -> bool:
        """检查目标进程是否存活"""
        if not self._target_pid:
            return False
        try:
            proc = psutil.Process(self._target_pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _find_process_by_name(self, name: str) -> Optional[int]:
        """按进程名查找新 PID"""
        name_lower = name.lower()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if name_lower in proc.info["name"].lower():
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _get_self_memory_mb(self) -> float:
        """获取本进程内存使用 (MB)"""
        try:
            return psutil.Process(self._self_pid).memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def get_diagnostics(self) -> dict:
        """获取诊断信息"""
        return {
            "target_pid": self._target_pid,
            "target_process": self._target_process_name,
            "consecutive_errors": self._consecutive_errors,
            "total_reconnects": self._total_reconnects,
            "total_resets": self._total_resets,
            "self_memory_mb": round(self._get_self_memory_mb(), 1),
            "memory_limit_mb": self._max_memory_mb,
            "last_check": self._last_check_time,
        }
