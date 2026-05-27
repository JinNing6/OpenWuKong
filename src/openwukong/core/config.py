# -*- coding: utf-8 -*-
"""
config.py - 集中配置加载

提供项目全局配置的统一加载入口:
- 从 config.json 读取
- 提供默认值回退
- 支持从命令行参数覆盖
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """获取项目根目录（包含 config.json 的目录）"""
    # 向上查找 config.json
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "config.json").exists():
            return parent
    # 如果找不到，回退到 src/ 上两层
    return Path(__file__).resolve().parent.parent.parent.parent


def load_config(config_path: Optional[str] = None) -> dict:
    """
    加载配置文件

    优先级: config_path 参数 > 项目根目录 config.json > 默认值
    """
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
        "workspaces": {},
    }

    # 确定配置文件路径
    if config_path:
        full_path = os.path.abspath(config_path)
    else:
        root = get_project_root()
        full_path = str(root / "config.json")

    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            defaults.update(user_config)
        except Exception:
            pass

    return defaults


def get_log_dir() -> str:
    """获取日志目录的绝对路径"""
    root = get_project_root()
    return str(root / "logs")


def get_goals_path() -> str:
    """获取 goals.json 的绝对路径"""
    root = get_project_root()
    return str(root / "goals.json")
