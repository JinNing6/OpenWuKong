# -*- coding: utf-8 -*-
"""
daemon.py - IDE 监控守护进程

将所有组件整合为一个可 24 小时持续运行的守护进程:
- 事件驱动 + 轮询混合模式
- 定期健康检查 + 自愈
- 优雅启动/停止/重载
- 结构化日志全程记录

启动方式:
    python daemon.py                                  # 使用 config.json 默认配置
    python daemon.py --target Antigravity.exe          # 指定目标进程
    python daemon.py --target Antigravity.exe --duration 120  # 运行 120 秒后退出
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# 确保模块可以互相导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import setup_logger, get_logger, log_event, EventCounter
from ide_monitor import IDEMonitor, IDEDiff
from watchdog import Watchdog, HealthStatus
from uia_events import UIAEventEngine, PollingEventEngine, UIAEvent, EventType


def load_config(config_path: str = "config.json") -> dict:
    """加载配置文件"""
    defaults = {
        "target_process": "Antigravity.exe",
        "poll_interval_sec": 2,
        "health_check_interval_sec": 60,
        "max_memory_mb": 500,
        "log_dir": "logs",
        "log_retention_days": 7,
        "auto_reconnect": True,
        "max_consecutive_errors": 10,
        "use_com_events": False,
        "max_events_per_second": 50,
        "event_queue_max_size": 10000,
        "console_output": True,
    }

    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            defaults.update(user_config)
        except Exception:
            pass

    return defaults


class IDEMonitorDaemon:
    """
    IDE 监控守护进程

    整合: IDEMonitor + UIAEventEngine/PollingEventEngine + Watchdog + Logger
    """

    def __init__(self, config: dict):
        self._config = config
        self._running = False
        self._start_time = 0.0
        self._duration: Optional[float] = None

        # 日志
        log_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            config["log_dir"],
        )
        self._root_logger = setup_logger(
            log_dir=log_dir,
            retention_days=config["log_retention_days"],
            console_output=config["console_output"],
        )
        self._logger = get_logger("daemon")
        self._event_counter = EventCounter(self._root_logger)

        # IDE 监控器
        self._monitor = IDEMonitor(config["target_process"])

        # 事件引擎
        self._com_engine: Optional[UIAEventEngine] = None
        self._poll_engine = PollingEventEngine()
        self._use_com = config.get("use_com_events", True)

        # Watchdog
        self._watchdog = Watchdog(
            target_process_name=config["target_process"],
            max_memory_mb=config["max_memory_mb"],
            max_consecutive_errors=config["max_consecutive_errors"],
            on_reconnect=self._handle_reconnect,
            on_full_reset=self._handle_full_reset,
        )

        # 计数器
        self._poll_count = 0
        self._event_count = 0
        self._change_count = 0

    def start(self, duration: Optional[float] = None):
        """启动守护进程"""
        self._running = True
        self._start_time = time.time()
        self._duration = duration

        log_event(
            self._logger,
            f"Daemon starting | target={self._config['target_process']} "
            f"| poll_interval={self._config['poll_interval_sec']}s "
            f"| duration={'unlimited' if not duration else f'{duration}s'}",
            event_type="daemon_start",
        )

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # 连接 IDE
        if not self._monitor.connect():
            log_event(self._logger, "Waiting for IDE process...", event_type="waiting")
            # 等待 IDE 进程出现
            while self._running:
                if self._monitor.connect():
                    break
                time.sleep(2)
                if self._duration and time.time() - self._start_time > self._duration:
                    log_event(self._logger, "Duration expired while waiting", level=30)
                    self._running = False
                    return

        self._watchdog.target_pid = self._monitor.pid

        # 尝试启动 COM 事件引擎
        if self._use_com:
            try:
                self._com_engine = UIAEventEngine(
                    target_pids={self._monitor.pid},
                    max_events_per_second=self._config.get("max_events_per_second", 50),
                )
                if self._com_engine.start():
                    log_event(self._logger, "COM event engine active", event_type="com_engine")
                else:
                    log_event(self._logger, "COM engine failed, using polling only", level=30)
                    self._com_engine = None
            except Exception as e:
                log_event(self._logger, f"COM engine error: {e}, using polling only", level=30)
                self._com_engine = None

        # 主循环
        try:
            self._main_loop()
        finally:
            self._shutdown()

    def stop(self):
        """停止守护进程"""
        self._running = False

    def _main_loop(self):
        """主事件循环"""
        poll_interval = self._config["poll_interval_sec"]
        health_interval = self._config["health_check_interval_sec"]
        last_health_check = time.time()

        log_event(self._logger, "Entering main loop", event_type="main_loop")

        while self._running:
            loop_start = time.time()

            # 检查持续时间限制
            if self._duration and (loop_start - self._start_time) > self._duration:
                log_event(self._logger, "Duration limit reached", event_type="duration_end")
                break

            # 1. 处理 COM 事件
            if self._com_engine:
                events = self._com_engine.drain_events(max_count=50)
                for event in events:
                    self._handle_event(event)

            # 2. 轮询 IDE 状态变化
            try:
                diff = self._monitor.detect_changes()
                if diff and diff.has_changes:
                    self._handle_change(diff)
                    self._watchdog.record_success()
                elif diff:
                    self._watchdog.record_success()

                # 生成轮询快照供 PollingEventEngine 检测
                self._poll_count += 1
                if self._poll_count % 10 == 0:
                    self._update_poll_snapshot()

            except Exception as e:
                log_event(self._logger, f"Poll error: {e}", level=30)
                self._watchdog.record_error()

            # 3. 定期健康检查
            if loop_start - last_health_check >= health_interval:
                self._health_check()
                last_health_check = loop_start

            # 4. 定期 GC
            if self._poll_count % 100 == 0:
                gc.collect()

            # 等待下一个周期
            elapsed = time.time() - loop_start
            sleep_time = max(0.1, poll_interval - elapsed)
            time.sleep(sleep_time)

    def _handle_event(self, event: UIAEvent):
        """处理一个 UIA 事件"""
        self._event_count += 1
        self._event_counter.count(event.event_type.value)

        log_event(
            self._logger,
            f"Event: {event.event_type.value} | {event.element_name[:40]}",
            event_type=event.event_type.value,
            event_data=event.to_dict(),
            pid=event.pid,
        )

    def _handle_change(self, diff: IDEDiff):
        """处理 IDE 状态变化"""
        self._change_count += 1

        if diff.file_changed:
            log_event(
                self._logger,
                f"Active file: {diff.old_file} -> {diff.new_file}",
                event_type="file_change",
                event_data=diff.to_dict(),
            )
        if diff.tabs_added:
            log_event(
                self._logger,
                f"Tabs opened: {diff.tabs_added}",
                event_type="tabs_change",
            )
        if diff.tabs_removed:
            log_event(
                self._logger,
                f"Tabs closed: {diff.tabs_removed}",
                event_type="tabs_change",
            )
        if diff.terminal_new_lines > 0:
            log_event(
                self._logger,
                f"Terminal new output: ~{diff.terminal_new_lines} chars",
                event_type="terminal_output",
            )
        if diff.title_changed and not diff.file_changed:
            log_event(
                self._logger,
                f"Title changed: {diff.old_title} -> {diff.new_title}",
                event_type="title_change",
            )

    def _health_check(self):
        """执行健康检查"""
        status = self._watchdog.check()
        uptime = time.time() - self._start_time

        log_event(
            self._logger,
            f"Health: alive={status.target_alive} mem={status.memory_mb:.0f}MB "
            f"errors={status.consecutive_errors} uptime={uptime/3600:.1f}h "
            f"polls={self._poll_count} events={self._event_count} changes={self._change_count}",
            event_type="health_check",
            event_data={
                **status.to_dict(),
                "uptime_hours": round(uptime / 3600, 2),
                "total_polls": self._poll_count,
                "total_events": self._event_count,
                "total_changes": self._change_count,
            },
        )

    def _update_poll_snapshot(self):
        """更新轮询快照"""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            import psutil as _psutil

            snapshot = {"pids": {}}
            for w in windows[:15]:
                try:
                    pid = w.process_id()
                    title = w.window_text() or ""
                    name = _psutil.Process(pid).name()
                    snapshot["pids"][pid] = {"name": name, "title": title}
                except Exception:
                    continue

            self._poll_engine.detect_changes(snapshot)

            # 消费轮询事件
            events = self._poll_engine.drain_events()
            for event in events:
                self._handle_event(event)

        except Exception:
            pass

    def _handle_reconnect(self):
        """处理重连"""
        log_event(self._logger, "Attempting reconnect...", event_type="reconnect_start")
        if self._monitor.reconnect():
            self._watchdog.target_pid = self._monitor.pid
            if self._com_engine:
                self._com_engine.update_target_pids({self._monitor.pid})
            log_event(
                self._logger,
                f"Reconnected to PID {self._monitor.pid}",
                event_type="reconnect_success",
            )
        else:
            log_event(self._logger, "Reconnect failed", event_type="reconnect_fail", level=30)

    def _handle_full_reset(self):
        """处理完整重置"""
        log_event(self._logger, "Full reset: cleaning up...", event_type="reset_start")

        # 停止 COM 引擎
        if self._com_engine:
            try:
                self._com_engine.stop()
            except Exception:
                pass

        # 强制 GC
        gc.collect()

        # 重新连接
        self._handle_reconnect()

        # 重启 COM 引擎
        if self._use_com:
            try:
                self._com_engine = UIAEventEngine(
                    target_pids={self._monitor.pid},
                    max_events_per_second=self._config.get("max_events_per_second", 50),
                )
                self._com_engine.start()
            except Exception:
                self._com_engine = None

        log_event(self._logger, "Full reset complete", event_type="reset_complete")

    def _shutdown(self):
        """优雅关闭"""
        log_event(
            self._logger,
            f"Shutting down | uptime={time.time() - self._start_time:.0f}s "
            f"| polls={self._poll_count} | events={self._event_count} | changes={self._change_count}",
            event_type="daemon_stop",
        )

        if self._com_engine:
            try:
                self._com_engine.stop()
            except Exception:
                pass

        # 输出最终统计
        stats = self._event_counter.get_stats()
        diag = self._watchdog.get_diagnostics()
        log_event(
            self._logger,
            "Final stats",
            event_type="final_stats",
            event_data={
                "event_stats": stats,
                "watchdog": diag,
            },
        )

    def _signal_handler(self, signum, frame):
        """信号处理"""
        log_event(
            self._logger,
            f"Received signal {signum}, stopping...",
            event_type="signal",
        )
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="UIA Agent - IDE Monitor Daemon")
    parser.add_argument(
        "--target", type=str, default=None,
        help="Target IDE process name (e.g. Antigravity.exe, Code.exe)",
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="Run duration in seconds (default: unlimited)",
    )
    parser.add_argument(
        "--config", type=str, default="config.json",
        help="Path to config file",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=None,
        help="Poll interval in seconds",
    )
    parser.add_argument(
        "--no-com-events", action="store_true",
        help="Disable COM event engine, use polling only",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    # 命令行参数覆盖配置文件
    if args.target:
        config["target_process"] = args.target
    if args.poll_interval is not None:
        config["poll_interval_sec"] = args.poll_interval
    if args.no_com_events:
        config["use_com_events"] = False

    daemon = IDEMonitorDaemon(config)
    daemon.start(duration=args.duration)


if __name__ == "__main__":
    main()
