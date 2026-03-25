# -*- coding: utf-8 -*-
"""
logger.py - 结构化日志系统

提供 24 小时持续运行的日志基础设施:
- JSON 格式日志（时间戳、级别、模块、事件类型、数据）
- 文件轮转（每天一个文件，保留 7 天）
- 控制台 + 文件双输出
- 事件统计器（每小时汇报事件计数）
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """JSON 格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }

        # 附加自定义字段
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "event_data"):
            log_data["data"] = record.event_data
        if hasattr(record, "pid"):
            log_data["pid"] = record.pid
        if hasattr(record, "process_name"):
            log_data["process_name"] = record.process_name

        if record.exc_info and record.exc_info[1]:
            log_data["error"] = str(record.exc_info[1])
            log_data["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else ""

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """控制台友好的格式化器"""

    COLORS = {
        "DEBUG": "\033[90m",     # 灰色
        "INFO": "\033[36m",      # 青色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = record.levelname[0]  # 首字母
        module = record.name.split(".")[-1][:12]
        msg = record.getMessage()

        parts = [f"{color}[{ts}][{level}][{module:<12}]{self.RESET} {msg}"]

        if hasattr(record, "event_type"):
            parts.append(f" ({record.event_type})")

        if record.exc_info and record.exc_info[1]:
            parts.append(f" | ERR: {record.exc_info[1]}")

        return "".join(parts)


class EventCounter:
    """事件统计器 - 每小时汇报一次事件计数"""

    def __init__(self, logger: logging.Logger, report_interval: int = 3600):
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._logger = logger
        self._report_interval = report_interval
        self._last_report = time.time()
        self._start_time = time.time()
        self._total_events = 0

    def count(self, event_type: str):
        """记录一个事件"""
        with self._lock:
            self._counts[event_type] = self._counts.get(event_type, 0) + 1
            self._total_events += 1

            # 检查是否到了汇报时间
            now = time.time()
            if now - self._last_report >= self._report_interval:
                self._report(now)

    def _report(self, now: float):
        """汇报统计"""
        uptime_hours = (now - self._start_time) / 3600
        self._logger.info(
            f"Event stats: {self._total_events} total events in {uptime_hours:.1f}h",
            extra={
                "event_type": "stats_report",
                "event_data": {
                    "counts": dict(self._counts),
                    "total": self._total_events,
                    "uptime_hours": round(uptime_hours, 2),
                },
            },
        )
        self._counts.clear()
        self._last_report = now

    def get_stats(self) -> dict:
        """获取当前统计"""
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "total_events": self._total_events,
                "current_counts": dict(self._counts),
                "uptime_seconds": round(uptime, 1),
            }


def setup_logger(
    name: str = "uia-agent",
    log_dir: str = "logs",
    level: int = logging.DEBUG,
    retention_days: int = 7,
    console_output: bool = True,
) -> logging.Logger:
    """
    配置并返回 logger 实例

    Args:
        name: logger 名称
        log_dir: 日志目录路径
        level: 日志级别
        retention_days: 日志保留天数
        console_output: 是否输出到控制台
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 文件 handler（JSON 格式，每天轮转）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / f"{name}.log",
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    file_handler.suffix = "%Y-%m-%d"
    logger.addHandler(file_handler)

    # 控制台 handler
    if console_output:
        console_handler = logging.StreamHandler(
            stream=sys.stdout if sys.stdout else sys.__stdout__
        )
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """获取子模块 logger（继承主 logger 配置）"""
    return logging.getLogger(f"uia-agent.{module_name}")


def log_event(
    logger: logging.Logger,
    msg: str,
    event_type: str = "",
    event_data: Any = None,
    level: int = logging.INFO,
    pid: int = 0,
    process_name: str = "",
):
    """发送一条带结构化数据的日志"""
    extra: dict[str, Any] = {}
    if event_type:
        extra["event_type"] = event_type
    if event_data is not None:
        extra["event_data"] = event_data
    if pid:
        extra["pid"] = pid
    if process_name:
        extra["process_name"] = process_name

    logger.log(level, msg, extra=extra)
