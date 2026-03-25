# -*- coding: utf-8 -*-
"""
service_wrapper.py - 24/7 进程级保活器

在 daemon.py 之上提供进程级别的保护:
- 自动重启崩溃的 daemon 进程
- 指数退避策略（防止持续崩溃导致 CPU 空转）
- 每日自动重启（清理内存碎片）
- 详细的运行时统计日志
- 支持 Windows 计划任务开机自启

使用方式:
    python service_wrapper.py                  # 默认监控 Antigravity.exe
    python service_wrapper.py --target Code.exe
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path


# ──────────────────── 配置 ────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DAEMON_SCRIPT = os.path.join(SCRIPT_DIR, "daemon.py")
PYTHON_EXE = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe")
LOG_FILE = os.path.join(SCRIPT_DIR, "logs", "service_wrapper.log")

# 退避策略
INITIAL_RESTART_DELAY = 3       # 首次重启等待秒数
MAX_RESTART_DELAY = 300         # 最大退避 5 分钟
RESET_DELAY_AFTER = 3600       # 稳定运行 1 小时后重置退避计数
DAILY_RESTART_HOUR = 4         # 每天凌晨 4 点自动重启（清理内存）
MAX_RAPID_CRASHES = 10          # 快速崩溃上限（连续<30s 就崩溃）
RAPID_CRASH_THRESHOLD = 30     # 低于此秒数算"快速崩溃"


def log(msg: str, level: str = "INFO"):
    """写入服务日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)

    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class ServiceWrapper:
    """
    进程级保活器

    核心行为:
    1. 启动 daemon.py 子进程
    2. 等待子进程退出
    3. 如果是崩溃退出 → 指数退避重启
    4. 如果是信号退出 → 优雅停止
    5. 每天凌晨 4 点自动重启（清理内存碎片）
    """

    def __init__(self, target_process: str = "Antigravity.exe", extra_args: list = None):
        self._target = target_process
        self._extra_args = extra_args or []
        self._running = True
        self._child: subprocess.Popen | None = None

        # 统计
        self._total_starts = 0
        self._total_crashes = 0
        self._rapid_crashes = 0
        self._restart_delay = INITIAL_RESTART_DELAY
        self._service_start_time = time.time()

        # 信号
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def run(self):
        """主循环"""
        log(f"Service wrapper starting | target={self._target} | pid={os.getpid()}")
        log(f"Daemon script: {DAEMON_SCRIPT}")
        log(f"Python: {PYTHON_EXE}")
        log(f"Daily restart at {DAILY_RESTART_HOUR}:00")

        while self._running:
            # 启动 daemon
            start_ts = time.time()
            exit_code = self._run_daemon()
            run_duration = time.time() - start_ts

            if not self._running:
                log("Service wrapper shutting down (signal received)")
                break

            # 分析退出原因
            self._total_crashes += 1

            if run_duration < RAPID_CRASH_THRESHOLD:
                self._rapid_crashes += 1
                log(f"Rapid crash detected! Duration={run_duration:.1f}s "
                    f"exit_code={exit_code} rapid_count={self._rapid_crashes}",
                    level="WARNING")

                if self._rapid_crashes >= MAX_RAPID_CRASHES:
                    log(f"Too many rapid crashes ({self._rapid_crashes}), "
                        f"stopping service wrapper", level="ERROR")
                    break
            else:
                # 稳定运行了一段时间，重置退避
                self._rapid_crashes = 0
                self._restart_delay = INITIAL_RESTART_DELAY
                log(f"Daemon exited after {run_duration:.0f}s | exit_code={exit_code}")

            # 指数退避
            delay = min(self._restart_delay, MAX_RESTART_DELAY)
            log(f"Restarting in {delay}s... "
                f"(crashes={self._total_crashes} starts={self._total_starts})")

            # 等待期间检查是否被停止
            wait_end = time.time() + delay
            while time.time() < wait_end and self._running:
                time.sleep(1)

            # 增加退避
            self._restart_delay = min(self._restart_delay * 2, MAX_RESTART_DELAY)

        # 汇报最终统计
        uptime = time.time() - self._service_start_time
        log(f"Service wrapper stopped | uptime={uptime / 3600:.1f}h "
            f"| starts={self._total_starts} | crashes={self._total_crashes}")

    def _run_daemon(self) -> int:
        """启动并运行 daemon 子进程"""
        cmd = [PYTHON_EXE, DAEMON_SCRIPT, "--target", self._target] + self._extra_args
        self._total_starts += 1
        log(f"Starting daemon #{self._total_starts}: {' '.join(cmd)}")

        try:
            self._child = subprocess.Popen(
                cmd,
                cwd=SCRIPT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            # 实时转发子进程输出
            if self._child.stdout:
                for line in self._child.stdout:
                    line = line.rstrip()
                    if line:
                        print(f"  [daemon] {line}", flush=True)

            self._child.wait()
            exit_code = self._child.returncode
            self._child = None
            return exit_code

        except Exception as e:
            log(f"Failed to start daemon: {e}", level="ERROR")
            self._child = None
            return -1

    def _should_daily_restart(self) -> bool:
        """检查是否到了每日重启时间"""
        now = datetime.now()
        return now.hour == DAILY_RESTART_HOUR and now.minute < 5

    def _signal_handler(self, signum, frame):
        """信号处理"""
        log(f"Received signal {signum}")
        self._running = False

        # 终止子进程
        if self._child and self._child.poll() is None:
            log("Terminating daemon child process...")
            try:
                self._child.terminate()
                try:
                    self._child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    log("Force killing daemon...", level="WARNING")
                    self._child.kill()
            except Exception as e:
                log(f"Error stopping daemon: {e}", level="WARNING")


# ──────────────────── Windows 计划任务注册 ────────────────────

def register_startup_task():
    """注册 Windows 计划任务实现开机自启"""
    task_name = "UIA-Agent-24h"
    python = PYTHON_EXE
    script = os.path.abspath(__file__)

    # 构建 schtasks 命令
    cmd = (
        f'schtasks /Create /TN "{task_name}" '
        f'/TR "\"{python}\" \"{script}\"" '
        f'/SC ONLOGON /RL HIGHEST /F'
    )

    log(f"Registering startup task: {task_name}")
    log(f"Command: {cmd}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"✓ Task '{task_name}' registered successfully")
        log(f"  Will auto-start on login")
    else:
        log(f"✗ Failed to register task: {result.stderr}", level="ERROR")
        log(f"  Try running as Administrator", level="WARNING")

    return result.returncode == 0


def unregister_startup_task():
    """删除 Windows 计划任务"""
    task_name = "UIA-Agent-24h"
    cmd = f'schtasks /Delete /TN "{task_name}" /F'

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"✓ Task '{task_name}' removed")
    else:
        log(f"✗ Failed to remove task: {result.stderr}", level="WARNING")

    return result.returncode == 0


def show_status():
    """显示当前服务状态"""
    task_name = "UIA-Agent-24h"
    cmd = f'schtasks /Query /TN "{task_name}" /FO LIST /V'

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"\n  Task '{task_name}' is registered:")
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if any(k in line for k in ["Status", "Task To Run", "Next Run", "Last Run"]):
                print(f"    {line}")
    else:
        print(f"\n  Task '{task_name}' is NOT registered")
        print(f"  Use: python service_wrapper.py install")

    # 检查是否有 daemon 在运行
    import psutil
    daemon_pids = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if "daemon.py" in cmdline and "python" in cmdline.lower():
                daemon_pids.append(proc.info["pid"])
        except Exception:
            continue

    if daemon_pids:
        print(f"\n  Active daemon processes: {daemon_pids}")
    else:
        print(f"\n  No active daemon processes found")

    # 检查日志
    if os.path.exists(LOG_FILE):
        size_kb = os.path.getsize(LOG_FILE) / 1024
        print(f"\n  Service log: {LOG_FILE} ({size_kb:.1f} KB)")
        # 显示最后几行
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            print(f"  Last entries:")
            for line in lines[-5:]:
                print(f"    {line.rstrip()}")
        except Exception:
            pass
    print()


# ──────────────────── 入口 ────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UIA Agent - 24/7 Service Wrapper",
        epilog="Examples:\n"
               "  python service_wrapper.py              # Start 24/7 monitoring\n"
               "  python service_wrapper.py install       # Register auto-start on login\n"
               "  python service_wrapper.py uninstall     # Remove auto-start\n"
               "  python service_wrapper.py status        # Show service status\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command", nargs="?", default="run",
        choices=["run", "install", "uninstall", "status"],
        help="run=start monitoring, install=register auto-start, "
             "uninstall=remove auto-start, status=show status",
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="Target IDE process name",
    )
    parser.add_argument(
        "--no-com-events", action="store_true",
        help="Disable COM event engine",
    )

    args = parser.parse_args()

    if args.command == "install":
        register_startup_task()
        return
    elif args.command == "uninstall":
        unregister_startup_task()
        return
    elif args.command == "status":
        show_status()
        return

    # 加载目标进程
    target = args.target
    if not target:
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                target = config.get("target_process", "Antigravity.exe")
            except Exception:
                target = "Antigravity.exe"
        else:
            target = "Antigravity.exe"

    extra_args = []
    if args.no_com_events:
        extra_args.append("--no-com-events")

    wrapper = ServiceWrapper(target_process=target, extra_args=extra_args)
    wrapper.run()


if __name__ == "__main__":
    main()
