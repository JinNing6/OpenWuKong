# -*- coding: utf-8 -*-
"""
run_logger.py — OpenWuKong 全链路运行日志系统

负责记录每次"启动督导"到"停止/完成"生命周期内的所有核心状态流转，
最终输出一份结构化的 JSON 文件和 Markdown 报告，供赛博华佗审计和用户回归使用。
"""

import os
import glob
import time
import json
import uuid
import datetime
from typing import Any, Optional
from collections import Counter


class RunLogger:
    """单次运行的日志记录器"""

    # 日志保留天数
    RETENTION_DAYS = 7

    def __init__(self, run_mode: str = "auto", log_dir: str = "logs/runs"):
        self.run_id = str(uuid.uuid4())[:8]

        # 找到项目根目录（向上三级：core → openwukong → src → 根）
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
        self.log_dir = os.path.join(root, log_dir)
        os.makedirs(self.log_dir, exist_ok=True)

        # 构造安全的文件名，包含时间戳和随机ID
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._base_name = f"run_{now_str}_{self.run_id}"
        self.filepath = os.path.join(self.log_dir, f"{self._base_name}.json")

        # 事件计数器
        self._event_counts: Counter = Counter()

        self.data: dict[str, Any] = {
            "run_id": self.run_id,
            "start_time": datetime.datetime.now().isoformat(),
            "mode": run_mode,
            "end_time": None,
            "status": "running",
            "goals": [],
            "events": [],
        }
        self.flush()

        # 自动清理旧日志
        self._auto_cleanup()

    def set_goals(self, goals_data: list[dict]):
        """记录初始目标"""
        self.data["goals"] = goals_data
        self.flush()

    def record_event(self, event_type: str, details: dict):
        """记录一个运行期事件"""
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "details": details,
        }
        self.data["events"].append(event)
        self._event_counts[event_type] += 1

        # 限制内存中的事件数量，超过 2000 条时截断保留最近的
        if len(self.data["events"]) > 2000:
            self.data["events"] = self.data["events"][-1500:]

        self.flush()

    def end_run(self, final_status: str, summary: dict = None):
        """结束本次记录"""
        self.data["end_time"] = datetime.datetime.now().isoformat()
        self.data["status"] = final_status
        # 合并事件统计到 summary
        full_summary = summary or {}
        full_summary["event_counts"] = dict(self._event_counts)
        full_summary["total_logged_events"] = sum(self._event_counts.values())
        self.data["summary"] = full_summary
        self.flush()

    def get_summary(self) -> dict:
        """返回结构化的运行摘要"""
        start = self.data.get("start_time", "")
        end = self.data.get("end_time", "")
        elapsed = 0.0
        if start and end:
            try:
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
                elapsed = (t1 - t0).total_seconds()
            except Exception:
                pass

        goals = self.data.get("goals", [])
        return {
            "run_id": self.run_id,
            "mode": self.data.get("mode", "unknown"),
            "status": self.data.get("status", "unknown"),
            "elapsed_sec": round(elapsed, 1),
            "goal_count": len(goals),
            "goals": goals,
            "event_counts": dict(self._event_counts),
            "total_events": sum(self._event_counts.values()),
        }

    def export_markdown(self) -> str:
        """导出 Markdown 格式的人类可读报告，同时保存到文件"""
        summary = self.get_summary()

        lines = [
            f"# 🤖 OpenWuKong 督导运行报告",
            f"",
            f"**运行 ID**: `{summary['run_id']}`",
            f"**模式**: {summary['mode']}",
            f"**状态**: {summary['status']}",
            f"**用时**: {summary['elapsed_sec']}s",
            f"",
            f"## 📌 任务目标 ({summary['goal_count']}个)",
            f"",
        ]

        for i, g in enumerate(summary.get("goals", []), 1):
            name = g.get("task_name", "未命名")
            match = g.get("window_match", "?")
            goal = g.get("goal", "无")
            lines.append(f"### {i}. {name}")
            lines.append(f"- **匹配词**: `{match}`")
            lines.append(f"- **目标**: {goal}")
            lines.append("")

        lines.append("## 📊 事件统计")
        lines.append("")
        lines.append("| 事件类型 | 次数 |")
        lines.append("|---------|------|")
        for etype, count in sorted(summary.get("event_counts", {}).items(), key=lambda x: -x[1]):
            lines.append(f"| {etype} | {count} |")
        lines.append("")
        lines.append(f"**总计**: {summary['total_events']} 个事件")
        lines.append("")

        # 最近 20 条关键事件
        events = self.data.get("events", [])
        key_events = [
            e for e in events
            if e.get("type") in (
                "supervisor_start", "match_failed", "match_success",
                "steer_sent", "steer_failed", "steer_limit_reached",
                "goal_check", "tick_transition", "full_reset",
            )
        ]
        recent = key_events[-20:]
        if recent:
            lines.append("## 🕐 关键事件时间线（最近 20 条）")
            lines.append("")
            for ev in recent:
                ts = ev.get("timestamp", "")
                if "T" in ts:
                    ts = ts.split("T")[1][:8]
                etype = ev.get("type", "")
                detail = ev.get("details", {})
                detail_str = ", ".join(f"{k}={v}" for k, v in detail.items()) if isinstance(detail, dict) else str(detail)
                lines.append(f"- `[{ts}]` **{etype}**: {detail_str[:120]}")
            lines.append("")

        md_content = "\n".join(lines)

        # 保存到文件
        md_path = os.path.join(self.log_dir, f"{self._base_name}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
        except Exception:
            pass

        return md_content

    def flush(self):
        """落盘写入"""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _auto_cleanup(self):
        """自动清理超过保留期的旧日志文件"""
        try:
            cutoff = time.time() - (self.RETENTION_DAYS * 86400)
            for pattern in ("run_*.json", "run_*.md"):
                for filepath in glob.glob(os.path.join(self.log_dir, pattern)):
                    try:
                        if os.path.getmtime(filepath) < cutoff:
                            os.remove(filepath)
                    except Exception:
                        continue
        except Exception:
            pass
