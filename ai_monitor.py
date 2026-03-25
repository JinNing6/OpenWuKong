# -*- coding: utf-8 -*-
"""
ai_monitor.py — 多项目 AI 对话持续监控模块

核心能力:
- 枚举所有 IDE 窗口（VS Code / Antigravity / Cursor）
- 检测每个窗口中的 AI Agent 运行状态（Thinking/Idle/Loading/Error）
- 提取 AI 输出进度文本
- 持续轮询 + 变化事件回调
- 实时仪表盘输出

使用:
    # 单次扫描
    monitor = MultiProjectAIMonitor()
    dashboard = monitor.scan_all()

    # 持续监控
    monitor.watch(interval=3, on_change=my_callback)
"""

from __future__ import annotations

import re
import sys
import io
import time
import enum
import dataclasses
from typing import Optional, Callable

import psutil
from pywinauto import Desktop
from pywinauto.application import Application

from logger import get_logger, log_event

logger = get_logger("ai_monitor")

# ── 强制 UTF-8 ──
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════
#  数据模型
# ═══════════════════════════════════════════════

class AIStatus(enum.Enum):
    """AI Agent 运行状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 正在执行（Thinking）
    LOADING = "loading"     # 模型加载中
    ERROR = "error"         # 出错
    UNKNOWN = "unknown"     # 无法判定


@dataclasses.dataclass
class AIProjectState:
    """单个项目窗口的 AI 状态快照"""
    timestamp: float
    pid: int
    process_name: str
    project_name: str       # 从窗口标题提取的项目名
    window_title: str
    ai_status: AIStatus
    ai_model: str           # 检测到的模型名（如 "Claude Opus 4.6"）
    agent_enabled: bool     # Agent 开关是否开启
    progress_text: str      # 进度文本（如 "311/550"）
    progress_pct: float     # 进度百分比（0-100），-1 表示无法解析
    last_ai_output: str     # 最近一条 AI 输出文本
    ai_element_count: int   # AI 相关控件数量

    @property
    def status_emoji(self) -> str:
        return {
            AIStatus.IDLE: "💤",
            AIStatus.RUNNING: "🔄",
            AIStatus.LOADING: "⏳",
            AIStatus.ERROR: "❌",
            AIStatus.UNKNOWN: "❓",
        }.get(self.ai_status, "❓")

    def summary_line(self) -> str:
        model_tag = f" [{self.ai_model}]" if self.ai_model else ""
        progress = f" {self.progress_text}" if self.progress_text else ""
        return (
            f"{self.status_emoji} {self.project_name[:25]:<25}"
            f" {self.ai_status.value:<8}{model_tag}{progress}"
        )


# ═══════════════════════════════════════════════
#  AI 状态判定引擎
# ═══════════════════════════════════════════════

# 状态关键词（从 UIA 实测数据提取）
_RUNNING_KEYWORDS = [
    "thinking", "generating", "running", "processing",
    "executing", "working", "writing", "analyzing",
    "searching", "fetching", "compiling",
]
_LOADING_KEYWORDS = [
    "loading", "connecting", "starting", "initializing",
    "model is loading", "warming up",
]
_ERROR_KEYWORDS = [
    "error", "failed", "could not", "unexpected error",
    "timed out", "rate limit", "quota exceeded",
]

# 进度正则: "311/550", "56%", "50 of 100"
_PROGRESS_RE = re.compile(
    r"(\d+)\s*/\s*(\d+)"  # 311/550
    r"|(\d+(?:\.\d+)?)\s*%"  # 56% or 56.5%
    r"|(\d+)\s+of\s+(\d+)"  # 50 of 100
)

# IDE 进程名判定
_IDE_PROCESS_NAMES = {
    "code.exe", "Code.exe", "Code - Insiders.exe",
    "cursor.exe", "Cursor.exe",
    "antigravity.exe", "Antigravity.exe",
    "idea64.exe", "idea.exe",
    "webstorm64.exe", "pycharm64.exe",
    "windsurf.exe", "Windsurf.exe",
}


def _detect_ai_status(
    buttons: list[dict],
    texts: list[dict],
    checkboxes: list[dict],
) -> tuple[AIStatus, str, bool, str, float, str]:
    """
    从 UIA 控件中判定 AI 状态

    Returns:
        (status, model_name, agent_enabled, progress_text, progress_pct, last_output)
    """
    status = AIStatus.UNKNOWN
    model_name = ""
    agent_enabled = False
    progress_text = ""
    progress_pct = -1.0
    last_output = ""

    # ── 从按钮文字判定模型和状态 ──
    for btn in buttons:
        name = btn.get("name", "").lower()

        # Agent 模型按钮（如 "Claude Opus 4.6 (Thinking)"）
        for model_kw in ["claude", "gpt", "gemini", "llama", "qwen", "deepseek", "copilot"]:
            if model_kw in name:
                raw_name = btn.get("name", "")
                # 提取模型名（括号前的部分）
                paren_idx = raw_name.find("(")
                if paren_idx > 0:
                    model_name = raw_name[:paren_idx].strip()
                    paren_content = raw_name[paren_idx + 1:].rstrip(")")
                    if any(kw in paren_content.lower() for kw in _RUNNING_KEYWORDS):
                        status = AIStatus.RUNNING
                    elif any(kw in paren_content.lower() for kw in _LOADING_KEYWORDS):
                        status = AIStatus.LOADING
                    elif any(kw in paren_content.lower() for kw in _ERROR_KEYWORDS):
                        status = AIStatus.ERROR
                    else:
                        if status == AIStatus.UNKNOWN:
                            status = AIStatus.IDLE
                else:
                    model_name = raw_name.strip()
                    if status == AIStatus.UNKNOWN:
                        status = AIStatus.IDLE
                break

    # ── 从 CheckBox 判定 Agent 开关 ──
    for cb in checkboxes:
        name = cb.get("name", "").lower()
        if "agent" in name or "toggle agent" in name:
            agent_enabled = cb.get("checked", False)
            break

    # ── 从 Text 控件提取进度和状态 ──
    for txt in texts:
        content = txt.get("text", "")
        content_lower = content.lower()

        # 进度提取
        if not progress_text:
            m = _PROGRESS_RE.search(content)
            if m:
                if m.group(1) and m.group(2):
                    # "311/550" 格式
                    cur, total = int(m.group(1)), int(m.group(2))
                    if 0 < total <= 100000 and cur <= total:
                        progress_text = f"{cur}/{total}"
                        progress_pct = round(cur / total * 100, 1)
                elif m.group(3):
                    # "56%" 格式
                    progress_pct = float(m.group(3))
                    progress_text = f"{progress_pct}%"
                elif m.group(4) and m.group(5):
                    # "50 of 100" 格式
                    cur, total = int(m.group(4)), int(m.group(5))
                    if 0 < total <= 100000 and cur <= total:
                        progress_text = f"{cur}/{total}"
                        progress_pct = round(cur / total * 100, 1)

        # 状态关键词检测（补充按钮信号）
        if status == AIStatus.UNKNOWN:
            if any(kw in content_lower for kw in _RUNNING_KEYWORDS):
                status = AIStatus.RUNNING
            elif any(kw in content_lower for kw in _LOADING_KEYWORDS):
                status = AIStatus.LOADING
            elif any(kw in content_lower for kw in _ERROR_KEYWORDS):
                status = AIStatus.ERROR

        # 最近一条有意义的 AI 输出
        if not last_output and len(content) > 20:
            # 过滤掉路径和系统消息
            if not content.startswith("E:\\") and not content.startswith("C:\\"):
                last_output = content[:120]

    return status, model_name, agent_enabled, progress_text, progress_pct, last_output


def _extract_project_name(title: str) -> str:
    """从窗口标题提取项目名"""
    # "ProjectName - Antigravity - FileName"
    # "ProjectName - Visual Studio Code - FileName"
    parts = title.split(" - ")
    if len(parts) >= 2:
        return parts[0].strip()
    return title[:30].strip()


# ═══════════════════════════════════════════════
#  多项目 AI 监控器
# ═══════════════════════════════════════════════

class MultiProjectAIMonitor:
    """
    多项目 AI 对话持续监控器

    使用示例:
        monitor = MultiProjectAIMonitor()

        # 单次扫描
        states = monitor.scan_all()
        for s in states:
            print(s.summary_line())

        # 持续监控
        def on_change(old, new):
            print(f"{new.project_name}: {old.ai_status} -> {new.ai_status}")

        monitor.watch(interval=3, on_change=on_change)
    """

    def __init__(self, backend: str = "uia"):
        self._backend = backend
        self._desktop = Desktop(backend=backend)
        self._last_states: dict[int, AIProjectState] = {}  # pid -> state
        self._scan_count = 0

    def scan_all(self) -> list[AIProjectState]:
        """
        扫描所有 IDE 窗口，提取 AI 状态

        Returns:
            每个项目窗口的 AIProjectState 列表
        """
        t0 = time.perf_counter()
        results = []
        seen_pids: set[int] = set()

        windows = self._desktop.windows()

        for w in windows:
            try:
                pid = w.process_id()
                if pid in seen_pids:
                    continue

                proc = psutil.Process(pid)
                pname = proc.name()

                # 判断是否为 IDE 进程
                if pname not in _IDE_PROCESS_NAMES:
                    # 宽松匹配
                    pname_lower = pname.lower()
                    if not any(kw in pname_lower for kw in ["code", "antigravity", "cursor", "idea", "webstorm", "pycharm", "windsurf"]):
                        continue

                title = w.window_text() or ""
                if not title or "Program Manager" in title:
                    continue

                seen_pids.add(pid)

                # 连接并探测
                state = self._probe_project(pid, pname, title)
                if state:
                    results.append(state)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._scan_count += 1

        log_event(
            logger,
            f"Scan #{self._scan_count}: {len(results)} projects in {elapsed_ms:.0f}ms",
            event_type="scan_complete",
            event_data={"project_count": len(results), "elapsed_ms": round(elapsed_ms, 1)},
        )

        return results

    def _probe_project(self, pid: int, pname: str, title: str) -> Optional[AIProjectState]:
        """探测单个 IDE 窗口的 AI 状态"""
        try:
            app = Application(backend=self._backend).connect(process=pid)
        except Exception:
            return None

        # 枚举所有窗口
        all_wins = []
        try:
            all_wins = app.windows()
        except Exception:
            try:
                all_wins = [app.top_window()]
            except Exception:
                return None

        buttons = []
        texts = []
        checkboxes = []
        ai_element_count = 0

        AI_KEYWORDS = {
            "copilot", "chat", "cline", "cursor", "ai", "assistant",
            "github", "gemini", "claude", "gpt", "thinking", "generating",
            "loading", "spinner", "busy", "agent", "model",
        }

        for win in all_wins:
            try:
                wt = win.window_text() or ""
                if not wt or "Program Manager" in wt:
                    continue

                descendants = win.descendants()

                for d in descendants:
                    try:
                        ct = d.element_info.control_type or ""
                        name = (d.element_info.name or "").strip()

                        if not name:
                            continue

                        name_lower = name.lower()

                        # 判断是否 AI 相关
                        is_ai = any(kw in name_lower for kw in AI_KEYWORDS)

                        if ct == "Button" and is_ai:
                            buttons.append({"name": name, "type": ct})
                            ai_element_count += 1

                        elif ct == "CheckBox" and is_ai:
                            checked = False
                            try:
                                toggle_state = d.get_toggle_state()
                                checked = toggle_state == 1
                            except Exception:
                                pass
                            checkboxes.append({"name": name, "checked": checked})
                            ai_element_count += 1

                        elif ct == "Text" and (is_ai or len(name) > 30):
                            text_content = name
                            try:
                                wtext = d.window_text()
                                if wtext and len(wtext) > len(name):
                                    text_content = wtext
                            except Exception:
                                pass
                            texts.append({"name": name, "text": text_content[:300]})
                            if is_ai:
                                ai_element_count += 1

                        # 无障碍模式：读取 Document/Edit 内容（终端、AI Chat 输出）
                        elif ct in ("Document", "Edit"):
                            try:
                                doc_text = d.window_text() or ""
                                # 过滤掉纯标题重复和空内容
                                if len(doc_text) > 30 and doc_text != wt:
                                    texts.append({
                                        "name": f"[{ct}] {name[:40]}",
                                        "text": doc_text[:500],
                                    })
                                    if is_ai:
                                        ai_element_count += 1
                            except Exception:
                                pass

                    except Exception:
                        continue
            except Exception:
                continue

        # 判定 AI 状态
        status, model, agent_on, prog_text, prog_pct, last_out = _detect_ai_status(
            buttons, texts, checkboxes
        )

        project_name = _extract_project_name(title)

        return AIProjectState(
            timestamp=time.time(),
            pid=pid,
            process_name=pname,
            project_name=project_name,
            window_title=title,
            ai_status=status,
            ai_model=model,
            agent_enabled=agent_on,
            progress_text=prog_text,
            progress_pct=prog_pct,
            last_ai_output=last_out,
            ai_element_count=ai_element_count,
        )

    def get_dashboard(self, states: Optional[list[AIProjectState]] = None) -> str:
        """生成文本仪表盘"""
        if states is None:
            states = self.scan_all()

        lines = [
            "=" * 60,
            "  AI Monitor Dashboard",
            f"  {time.strftime('%Y-%m-%d %H:%M:%S')}  |  {len(states)} projects",
            "=" * 60,
            "",
        ]

        if not states:
            lines.append("  No IDE projects detected.")
            lines.append("")
            return "\n".join(lines)

        # 按状态排序：Running > Loading > Error > Idle > Unknown
        priority = {
            AIStatus.RUNNING: 0,
            AIStatus.LOADING: 1,
            AIStatus.ERROR: 2,
            AIStatus.IDLE: 3,
            AIStatus.UNKNOWN: 4,
        }
        states_sorted = sorted(states, key=lambda s: priority.get(s.ai_status, 5))

        for s in states_sorted:
            lines.append(f"  {s.summary_line()}")
            if s.last_ai_output:
                preview = s.last_ai_output[:60].replace("\n", " ")
                lines.append(f"    └ {preview}")

        lines.append("")

        # 统计
        running = sum(1 for s in states if s.ai_status == AIStatus.RUNNING)
        idle = sum(1 for s in states if s.ai_status == AIStatus.IDLE)
        loading = sum(1 for s in states if s.ai_status == AIStatus.LOADING)
        errors = sum(1 for s in states if s.ai_status == AIStatus.ERROR)

        lines.append(f"  Running: {running}  Idle: {idle}  Loading: {loading}  Errors: {errors}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def watch(
        self,
        interval: float = 3.0,
        on_change: Optional[Callable[[Optional[AIProjectState], AIProjectState], None]] = None,
        on_tick: Optional[Callable[[list[AIProjectState]], None]] = None,
        dashboard: bool = True,
        max_iterations: int = 0,
    ):
        """
        持续监控循环

        Args:
            interval: 轮询间隔（秒）
            on_change: 状态变化回调 (old_state, new_state)
            on_tick: 每次轮询回调 (all_states)
            dashboard: 是否打印仪表盘
            max_iterations: 最大轮询次数（0=无限）
        """
        print("  Starting AI Monitor... (Ctrl+C to stop)")
        print(f"  Polling interval: {interval}s")
        print()

        iteration = 0
        try:
            while True:
                iteration += 1
                if max_iterations > 0 and iteration > max_iterations:
                    break

                states = self.scan_all()

                # 变化检测
                if on_change:
                    current_pids = {s.pid for s in states}
                    old_pids = set(self._last_states.keys())

                    for s in states:
                        old = self._last_states.get(s.pid)
                        if old is None:
                            # 新项目出现
                            on_change(None, s)
                        elif old.ai_status != s.ai_status:
                            # 状态变化
                            on_change(old, s)

                    # 项目消失
                    for pid in old_pids - current_pids:
                        old = self._last_states[pid]
                        disappeared = AIProjectState(
                            timestamp=time.time(),
                            pid=pid,
                            process_name=old.process_name,
                            project_name=old.project_name,
                            window_title="(closed)",
                            ai_status=AIStatus.UNKNOWN,
                            ai_model="",
                            agent_enabled=False,
                            progress_text="",
                            progress_pct=-1,
                            last_ai_output="",
                            ai_element_count=0,
                        )
                        on_change(old, disappeared)

                # 更新缓存
                self._last_states = {s.pid: s for s in states}

                # 回调
                if on_tick:
                    on_tick(states)

                # 仪表盘
                if dashboard:
                    # 清屏（Windows）
                    print("\033[2J\033[H", end="", flush=True)
                    print(self.get_dashboard(states))

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n  Monitor stopped.")


# ═══════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Monitor — 多项目 AI 对话监控器")
    parser.add_argument(
        "--mode", choices=["scan", "watch"], default="watch",
        help="scan=单次扫描, watch=持续监控"
    )
    parser.add_argument(
        "--interval", type=float, default=3.0,
        help="轮询间隔（秒），默认 3"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="JSON 格式输出"
    )
    args = parser.parse_args()

    monitor = MultiProjectAIMonitor()

    if args.mode == "scan":
        states = monitor.scan_all()

        if args.json:
            import json
            output = []
            for s in states:
                output.append({
                    "project": s.project_name,
                    "pid": s.pid,
                    "status": s.ai_status.value,
                    "model": s.ai_model,
                    "agent_enabled": s.agent_enabled,
                    "progress": s.progress_text,
                    "progress_pct": s.progress_pct,
                    "last_output": s.last_ai_output[:100],
                })
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(monitor.get_dashboard(states))

    else:
        def on_change(old, new):
            if old is None:
                log_event(
                    logger,
                    f"NEW: {new.project_name} [{new.ai_status.value}]",
                    event_type="project_appeared",
                )
            elif new.window_title == "(closed)":
                log_event(
                    logger,
                    f"GONE: {old.project_name}",
                    event_type="project_disappeared",
                )
            else:
                log_event(
                    logger,
                    f"CHANGE: {new.project_name} "
                    f"{old.ai_status.value} -> {new.ai_status.value}",
                    event_type="status_changed",
                    event_data={"old_status": old.ai_status.value, "new_status": new.ai_status.value},
                )

        monitor.watch(
            interval=args.interval,
            on_change=on_change,
            dashboard=True,
        )


if __name__ == "__main__":
    main()
