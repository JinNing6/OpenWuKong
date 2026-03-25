# -*- coding: utf-8 -*-
"""
research_supervisor.py — 科研项目 AI 督导器

核心逻辑:
  1. 监控各 IDE 窗口中的 AI Agent 状态
  2. 当 Agent 从 Running→Idle 时，读取对话结果
  3. 判断是否达到既定目标
  4. 未达标 → 在 Chat 输入框自动发送续跑指令
  5. 达标 → 标记完成，转向下一个项目

使用:
    python research_supervisor.py                    # 交互式配置
    python research_supervisor.py --config goals.json # 从配置文件加载
    python research_supervisor.py --demo              # 演示模式（只读）
"""

from __future__ import annotations

import re
import sys
import io
import os
import json
import time
import enum
import dataclasses
from typing import Optional, Callable
from datetime import datetime

import psutil
from pywinauto import Desktop
from pywinauto.application import Application
from pywinauto.keyboard import send_keys

from logger import get_logger, log_event
from ai_monitor import MultiProjectAIMonitor, AIStatus, AIProjectState

logger = get_logger("supervisor")

# ── 强制 UTF-8 ──
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════
#  项目目标定义
# ═══════════════════════════════════════════════

class GoalStatus(enum.Enum):
    PENDING = "pending"       # 还没开始
    RUNNING = "running"       # Agent 正在执行
    CHECKING = "checking"     # Agent 空闲,正在检查结果
    ACHIEVED = "achieved"     # 目标达成 ✅
    FAILED = "failed"         # 多次尝试后仍失败


@dataclasses.dataclass
class ProjectGoal:
    """单个科研项目的目标定义"""
    project_name: str           # 项目名（匹配窗口标题关键词）
    goal_description: str       # 目标描述
    success_keywords: list[str] # 成功信号关键词（在 AI 输出中检测）
    failure_keywords: list[str] # 失败信号关键词
    retry_command: str          # 未达标时发送的续跑指令
    max_retries: int = 20       # 最大重试次数
    cooldown_sec: float = 10.0  # 重试间隔（秒）

    # 运行时状态
    status: GoalStatus = GoalStatus.PENDING
    retry_count: int = 0
    last_action_time: float = 0
    matched_pid: int = 0
    history: list[str] = dataclasses.field(default_factory=list)

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.history.append(entry)
        if len(self.history) > 100:
            self.history = self.history[-50:]


# ═══════════════════════════════════════════════
#  Chat 输入框操作
# ═══════════════════════════════════════════════

def _find_chat_input(app: Application) -> Optional[object]:
    """
    在 IDE 窗口中找到 AI Chat 输入框

    策略：从所有窗口的 descendants 中找到最后一个可编辑的
    Edit 控件（通常是底部的 Chat 输入框）
    """
    for win in app.windows():
        try:
            wt = win.window_text() or ""
            if not wt or "Program Manager" in wt:
                continue

            descendants = win.descendants()

            # 收集候选输入框
            candidates = []
            for d in descendants:
                try:
                    ct = d.element_info.control_type or ""
                    name = (d.element_info.name or "").lower()

                    # 匹配 Chat 输入框特征
                    if ct == "Edit":
                        # 排除搜索框、过滤框等
                        if any(kw in name for kw in ["search", "filter", "find", "terminal"]):
                            continue
                        # Chat 输入框通常有以下特征
                        if any(kw in name for kw in [
                            "ask", "message", "chat", "prompt", "type",
                            "send", "input", "antigravity", "agent",
                        ]) or name == "" or name.strip() == "":
                            candidates.append(d)

                except Exception:
                    continue

            # 返回最后一个候选（通常是底部的 Chat 输入框）
            if candidates:
                return candidates[-1]
        except Exception:
            continue
    return None


def _send_chat_message(app: Application, message: str, pid: int) -> bool:
    """
    在 IDE 的 AI Chat 输入框中发送消息

    流程:
    1. 找到 Chat 输入框
    2. 设置焦点
    3. 清空并输入消息
    4. 按 Enter 发送
    """
    chat_input = _find_chat_input(app)
    if not chat_input:
        log_event(logger, f"PID={pid}: Chat 输入框未找到", event_type="chat_not_found")
        return False

    try:
        # 设置焦点
        chat_input.set_focus()
        time.sleep(0.1)

        # 清空已有内容
        try:
            chat_input.set_edit_text("")
        except Exception:
            send_keys("^a{DELETE}", pause=0.02)

        time.sleep(0.05)

        # 输入消息
        try:
            chat_input.set_edit_text(message)
        except Exception:
            # fallback: 逐字输入
            chat_input.type_keys(message, with_spaces=True, pause=0.01)

        time.sleep(0.1)

        # 按 Enter 发送
        send_keys("{ENTER}", pause=0.05)

        log_event(
            logger,
            f"PID={pid}: 已发送指令({len(message)} chars)",
            event_type="command_sent",
            event_data={"message_preview": message[:80]},
        )
        return True

    except Exception as e:
        log_event(
            logger,
            f"PID={pid}: 发送失败 - {e}",
            event_type="send_failed",
        )
        return False


# ═══════════════════════════════════════════════
#  对话内容读取
# ═══════════════════════════════════════════════

def _read_ai_conversation(app: Application) -> str:
    """
    读取 IDE 窗口中 AI 对话的最近内容

    从 Document/Text 控件中提取可能的 AI 输出
    """
    texts = []

    for win in app.windows()[:3]:
        try:
            wt = win.window_text() or ""
            if not wt or "Program Manager" in wt:
                continue

            for d in win.descendants():
                try:
                    ct = d.element_info.control_type or ""
                    name = (d.element_info.name or "").strip()

                    if ct in ("Text", "Document", "Edit"):
                        content = ""
                        try:
                            content = d.window_text() or ""
                        except Exception:
                            content = name

                        # 过滤太短和重复
                        if len(content) > 20 and content != wt:
                            texts.append(content[:500])

                except Exception:
                    continue
        except Exception:
            continue

    return "\n".join(texts[-10:])  # 最近 10 段文本


# ═══════════════════════════════════════════════
#  督导器核心
# ═══════════════════════════════════════════════

class ResearchSupervisor:
    """
    科研项目 AI 督导器

    在 AI Agent 完成任务时自动检查目标 → 未达标时续发指令
    """

    def __init__(self, goals: list[ProjectGoal]):
        self.goals = goals
        self.monitor = MultiProjectAIMonitor()
        self._prev_states: dict[int, AIStatus] = {}
        self._running = False

    def run(
        self,
        interval: float = 5.0,
        dry_run: bool = False,
        max_total_hours: float = 24.0,
    ):
        """
        启动督导循环

        Args:
            interval: 轮询间隔(秒)
            dry_run: True=只监控不操作(演示模式)
            max_total_hours: 最长运行时间(小时)
        """
        self._running = True
        start_time = time.time()
        max_seconds = max_total_hours * 3600

        print("=" * 60)
        print("  Research Supervisor — 科研 AI 督导器")
        print(f"  {len(self.goals)} 个项目目标")
        print(f"  模式: {'🔍 只读演示' if dry_run else '🤖 自动督导'}")
        print(f"  最长运行: {max_total_hours}h")
        print("=" * 60)

        for g in self.goals:
            print(f"  📌 {g.project_name}: {g.goal_description}")
        print()

        try:
            while self._running:
                elapsed = time.time() - start_time
                if elapsed > max_seconds:
                    print(f"\n  ⏰ 已达最大运行时间 ({max_total_hours}h)，停止。")
                    break

                # 检查是否所有目标都已达成
                all_achieved = all(
                    g.status == GoalStatus.ACHIEVED for g in self.goals
                )
                if all_achieved:
                    print("\n  🎉 所有项目目标已达成！")
                    break

                # 扫描 IDE 窗口
                states = self.monitor.scan_all()

                # 匹配项目 ↔ 窗口
                for goal in self.goals:
                    if goal.status == GoalStatus.ACHIEVED:
                        continue

                    matched = self._match_project(goal, states)
                    if not matched:
                        continue

                    self._process_goal(goal, matched, dry_run)

                # 打印仪表盘
                self._print_dashboard(states, elapsed)

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n  Supervisor 已停止。")

        # 输出最终报告
        self._print_report()

    def _match_project(
        self, goal: ProjectGoal, states: list[AIProjectState]
    ) -> Optional[AIProjectState]:
        """将项目目标匹配到 IDE 窗口"""
        for s in states:
            # 按项目名关键词匹配
            if goal.project_name.lower() in s.project_name.lower():
                goal.matched_pid = s.pid
                return s
            if goal.project_name.lower() in s.window_title.lower():
                goal.matched_pid = s.pid
                return s
        return None

    def _process_goal(
        self, goal: ProjectGoal, state: AIProjectState, dry_run: bool
    ):
        """处理单个项目目标"""
        prev_status = self._prev_states.get(state.pid)
        current_status = state.ai_status
        self._prev_states[state.pid] = current_status

        # ── 检测 Running → Idle 转换（Agent 完成了一轮） ──
        if prev_status == AIStatus.RUNNING and current_status == AIStatus.IDLE:
            goal.status = GoalStatus.CHECKING
            goal.log(f"Agent 完成一轮，开始检查结果...")

            # 读取 AI 对话内容
            try:
                app = Application(backend="uia").connect(process=state.pid)
                conversation = _read_ai_conversation(app)

                # 检查成功信号
                achieved = self._check_success(goal, conversation)

                if achieved:
                    goal.status = GoalStatus.ACHIEVED
                    goal.log("🎉 目标达成！")
                    log_event(
                        logger,
                        f"ACHIEVED: {goal.project_name}",
                        event_type="goal_achieved",
                    )
                    return

                # 未达标 → 发送续跑指令
                if goal.retry_count >= goal.max_retries:
                    goal.status = GoalStatus.FAILED
                    goal.log(f"❌ 已重试 {goal.max_retries} 次，标记失败")
                    return

                # 冷却检查
                now = time.time()
                if now - goal.last_action_time < goal.cooldown_sec:
                    return

                goal.retry_count += 1
                goal.last_action_time = now

                if dry_run:
                    goal.status = GoalStatus.RUNNING
                    goal.log(f"[DRY RUN] 将发送: {goal.retry_command[:60]}")
                else:
                    # 实际发送指令
                    success = _send_chat_message(
                        app, goal.retry_command, state.pid
                    )
                    if success:
                        goal.status = GoalStatus.RUNNING
                        goal.log(
                            f"已发送续跑指令 (第 {goal.retry_count} 次): "
                            f"{goal.retry_command[:50]}"
                        )
                    else:
                        goal.log("⚠ 发送失败，下轮重试")

            except Exception as e:
                goal.log(f"检查异常: {str(e)[:50]}")

        elif current_status == AIStatus.RUNNING:
            goal.status = GoalStatus.RUNNING

        elif current_status == AIStatus.ERROR:
            # Agent 报错 → 也触发续跑
            goal.log("Agent 报错，等待冷却后重试")

    def _check_success(self, goal: ProjectGoal, conversation: str) -> bool:
        """检查对话内容是否包含成功信号"""
        conv_lower = conversation.lower()

        # 先检查失败信号
        for kw in goal.failure_keywords:
            if kw.lower() in conv_lower:
                goal.log(f"检测到失败信号: '{kw}'")
                return False

        # 再检查成功信号
        for kw in goal.success_keywords:
            if kw.lower() in conv_lower:
                goal.log(f"检测到成功信号: '{kw}'")
                return True

        return False

    def _print_dashboard(self, states: list[AIProjectState], elapsed: float):
        """打印督导仪表盘"""
        hours = elapsed / 3600
        minutes = (elapsed % 3600) / 60

        lines = [
            "\033[2J\033[H",  # 清屏
            "=" * 60,
            f"  🔬 Research Supervisor  |  {int(hours)}h {int(minutes)}m",
            "=" * 60,
            "",
        ]

        for goal in self.goals:
            # 状态 emoji
            emoji = {
                GoalStatus.PENDING: "⏸",
                GoalStatus.RUNNING: "🔄",
                GoalStatus.CHECKING: "🔍",
                GoalStatus.ACHIEVED: "🏆",
                GoalStatus.FAILED: "❌",
            }.get(goal.status, "❓")

            retry_info = ""
            if goal.retry_count > 0:
                retry_info = f" (retry {goal.retry_count}/{goal.max_retries})"

            lines.append(
                f"  {emoji} {goal.project_name[:25]:<25} "
                f"{goal.status.value:<10}{retry_info}"
            )
            lines.append(f"     📌 {goal.goal_description[:50]}")

            # 最近一条日志
            if goal.history:
                lines.append(f"     └ {goal.history[-1]}")
            lines.append("")

        # IDE 窗口状态
        lines.append("─" * 60)
        for s in states:
            lines.append(f"  {s.status_emoji} {s.project_name[:20]:<20} "
                         f"{s.ai_status.value:<8} {s.ai_model}")
        lines.append("=" * 60)

        print("\n".join(lines), flush=True)

    def _print_report(self):
        """输出最终报告"""
        print("\n" + "=" * 60)
        print("  📊 督导报告")
        print("=" * 60)

        for goal in self.goals:
            emoji = "🏆" if goal.status == GoalStatus.ACHIEVED else "❌"
            print(f"\n  {emoji} {goal.project_name}")
            print(f"     状态: {goal.status.value}")
            print(f"     重试次数: {goal.retry_count}")
            if goal.history:
                print(f"     最后记录: {goal.history[-1]}")
        print()


# ═══════════════════════════════════════════════
#  预置模板
# ═══════════════════════════════════════════════

def load_goals_from_file(path: str) -> list[ProjectGoal]:
    """从 JSON 文件加载项目目标"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    goals = []
    for item in data.get("goals", []):
        goals.append(ProjectGoal(
            project_name=item["project_name"],
            goal_description=item["goal_description"],
            success_keywords=item.get("success_keywords", []),
            failure_keywords=item.get("failure_keywords", []),
            retry_command=item.get("retry_command",
                "继续寻找最佳方案并执行，目标是超越当前 SOTA 基线。"
                "分析之前的结果，找出瓶颈，尝试新的策略。"
            ),
            max_retries=item.get("max_retries", 20),
            cooldown_sec=item.get("cooldown_sec", 10.0),
        ))
    return goals


def save_example_config(path: str):
    """生成示例配置文件"""
    example = {
        "goals": [
            {
                "project_name": "DOW",
                "goal_description": "DoW 攻击向量 ASR > 85%, 达到 USENIX 2027 投稿标准",
                "success_keywords": [
                    "ASR: 0.9", "ASR: 0.8", "benchmark passed",
                    "all vectors passed", "达标", "SOTA"
                ],
                "failure_keywords": [
                    "Error", "failed", "rate limit"
                ],
                "retry_command": (
                    "继续优化实验方案，分析上一轮失败用例，调整攻击策略参数，"
                    "重新运行 benchmark 直到 ASR 超过 85%。"
                    "如果当前策略不行就换一种新方法。"
                ),
                "max_retries": 30,
                "cooldown_sec": 15
            },
            {
                "project_name": "Measurement",
                "goal_description": "MCP 安全扫描完成 1835+ 信号，漏洞检出率超过 Semgrep 3x",
                "success_keywords": [
                    "scan complete", "1835", "detection rate",
                    "超过", "3x", "完成"
                ],
                "failure_keywords": [
                    "Error", "crashed", "timeout"
                ],
                "retry_command": (
                    "继续扫描剩余仓库，修复之前的解析错误，"
                    "确保所有 1835 个仓库都完成 AST 分析。"
                    "如果有新的漏洞模式，更新检测规则。"
                ),
                "max_retries": 20,
                "cooldown_sec": 10
            }
        ]
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(example, f, ensure_ascii=False, indent=2)
    print(f"  示例配置已保存: {path}")


# ═══════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Research Supervisor — 科研 AI 督导器"
    )
    parser.add_argument(
        "--config", type=str, default="",
        help="项目目标配置文件路径 (JSON)"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="演示模式（只读，不发送指令）"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0,
        help="轮询间隔（秒）"
    )
    parser.add_argument(
        "--max-hours", type=float, default=24.0,
        help="最大运行时间（小时）"
    )
    parser.add_argument(
        "--gen-config", type=str, default="",
        help="生成示例配置文件到指定路径"
    )
    args = parser.parse_args()

    # 生成示例配置
    if args.gen_config:
        save_example_config(args.gen_config)
        return

    # 加载目标
    if args.config:
        if not os.path.exists(args.config):
            print(f"  ❌ 配置文件不存在: {args.config}")
            print(f"  用 --gen-config goals.json 生成示例配置")
            return
        goals = load_goals_from_file(args.config)
    else:
        # 默认：用演示目标
        print("  ℹ 未指定配置文件，使用内置演示目标")
        print("  用 --gen-config goals.json 生成配置文件")
        print()
        goals = [
            ProjectGoal(
                project_name="DOW",
                goal_description="DoW 攻击 ASR > 85%",
                success_keywords=["ASR: 0.9", "ASR: 0.8", "passed", "达标"],
                failure_keywords=["Error", "failed"],
                retry_command=(
                    "继续寻找最佳方案并执行，分析之前的实验结果，"
                    "优化参数，重新跑分，直到超越 SOTA 基线。"
                ),
            ),
        ]

    supervisor = ResearchSupervisor(goals)
    supervisor.run(
        interval=args.interval,
        dry_run=args.demo,
        max_total_hours=args.max_hours,
    )


if __name__ == "__main__":
    main()
