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
import time
import enum
import dataclasses
import concurrent.futures
from typing import Optional, Callable

import psutil
from pywinauto import Desktop
from pywinauto.application import Application

from openwukong.core.logger import get_logger, log_event

logger = get_logger("ai_monitor")

# ── 强制 UTF-8 ──
if sys.stdout and hasattr(sys.stdout, "buffer"):
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
if sys.stderr and hasattr(sys.stderr, "buffer"):
    reconfigure = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


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
    "codex.exe", "Codex.exe",
    "chrome.exe", "Chrome.exe",
    "msedge.exe", "MSEdge.exe",
    "firefox.exe", "Firefox.exe",
}

_WORKSPACE_PROCESS_KEYWORDS = [
    "code", "antigravity", "cursor", "idea",
    "webstorm", "pycharm", "windsurf", "codex",
    "chrome", "msedge", "firefox",
]


def _is_supported_workspace_process(process_name: str) -> bool:
    if not process_name:
        return False

    if process_name in _IDE_PROCESS_NAMES:
        return True

    pname_lower = process_name.lower()
    return any(keyword in pname_lower for keyword in _WORKSPACE_PROCESS_KEYWORDS)


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
    """
    针对不同 IDE 窗口标题格式智能提取项目名

    支持格式：
    - VS Code / Cursor: "FileName - ProjectName - Cursor"
    - IntelliJ / PyCharm: "ProjectName [Path] - FileName - PyCharm"
    - Antigravity: "ProjectName - Antigravity - FileName"

    关键修复 (2026-03-31):
    - Antigravity 标题格式中 IDE 名在中间段而非最后段
    - 必须检查所有段（包括中间段）是否为 IDE 名
    """
    if not title:
        return ""

    # 统一处理各种 Dash 变体 (en-dash, em-dash, hyphen)
    # 并支持带空格和不带空格的分割
    separators = [r"\s-\s", r"\s—\s", r"\s–\s", r" - ", r" — ", r" – "]
    regex_pattern = "|".join(separators)
    parts = [p.strip() for p in re.split(regex_pattern, title) if p.strip()]

    # 0. 强匹配 JetBrains 风格: "ProjectName [e:\path] - ..."
    if " [" in title and "] - " in title:
        m = re.match(r"^(.*?) \[.*?\]", title)
        if m:
            return m.group(1).strip()

    # 0.5 一些 Web / 桌面工作台会使用 "Project — 中文名 · Brand" 形式
    if len(parts) == 2 and "·" in parts[1]:
        left = parts[0].strip()
        if left and len(left) <= 40:
            return left

    ide_names = [
        "cursor",
        "code",
        "pycharm",
        "intellij",
        "clion",
        "webstorm",
        "antigravity",
        "windsurf",
        "codex",
        "google chrome",
        "chrome",
        "microsoft edge",
        "edge",
        "firefox",
    ]

    if len(parts) >= 3:
        # 三段式格式: "A - B - C"
        last_part_lower = parts[-1].lower()
        mid_part_lower = parts[1].lower()
        first_part_lower = parts[0].lower()

        # Case 1: IDE 名在最后段 (Cursor/VS Code 格式: "File - Project - Cursor")
        if any(ide in last_part_lower for ide in ide_names):
            has_ext = re.search(r"\.[a-z0-9]{1,10}$", first_part_lower)
            if has_ext:
                return parts[1]  # File.py - Project - IDE → Project
            return parts[0]      # Project - IDE - File → Project

        # Case 2: IDE 名在中间段 (Antigravity 格式: "Project - Antigravity - File.py")
        if any(ide in mid_part_lower for ide in ide_names):
            return parts[0]      # Project - Antigravity - File.py → Project

    if len(parts) >= 2:
        # 2段式通常是 "Project - IDE" 或 "File - Project"
        last_part_lower = parts[-1].lower()
        if any(ide in last_part_lower for ide in ide_names):
            return parts[0]
        # 也检查第一段是否可能是 IDE 名
        first_part_lower = parts[0].lower()
        if any(ide in first_part_lower for ide in ide_names):
            return parts[1]
        return parts[1] # 假设 File - Project

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

        关键修复 (2026-03-31):
        - 每个 PID 只做一次 UIA 深度探测（避免 N×5s 超时）
        - 但为该 PID 的每个窗口标题各生成一条 AIProjectState
        - AI 状态信息共享自同一次探测结果

        Returns:
            每个项目窗口的 AIProjectState 列表
        """
        t0 = time.perf_counter()
        results = []

        # Phase 1: 收集每个 PID 的所有窗口标题（快速，无 UIA）
        pid_windows: dict[int, list[tuple[str, str]]] = {}  # pid -> [(title, pname)]
        seen_titles: set[str] = set()

        windows = self._desktop.windows()
        for w in windows:
            try:
                pid = w.process_id()
                proc = psutil.Process(pid)
                pname = proc.name()

                if not _is_supported_workspace_process(pname):
                    continue

                title = w.window_text() or ""
                if not title or "Program Manager" in title:
                    continue

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                if pid not in pid_windows:
                    pid_windows[pid] = []
                pid_windows[pid].append((title, pname))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        # Phase 2: 每个 PID 只做一次深度 UIA 探测
        for pid, title_list in pid_windows.items():
            primary_title, pname = title_list[0]

            # 用第一个窗口标题做深度探测（获取 AI 状态）
            probe_result = self._probe_project(pid, pname, primary_title)

            if probe_result:
                # 第一个窗口直接使用探测结果
                results.append(probe_result)

                # 其余窗口复用 AI 状态，但独立提取项目名
                for extra_title, _ in title_list[1:]:
                    extra_project = _extract_project_name(extra_title)
                    results.append(AIProjectState(
                        timestamp=time.time(),
                        pid=pid,
                        process_name=pname,
                        project_name=extra_project,
                        window_title=extra_title,
                        ai_status=probe_result.ai_status,
                        ai_model=probe_result.ai_model,
                        agent_enabled=probe_result.agent_enabled,
                        progress_text=probe_result.progress_text,
                        progress_pct=probe_result.progress_pct,
                        last_ai_output=probe_result.last_ai_output,
                        ai_element_count=probe_result.ai_element_count,
                    ))
            else:
                # 探测失败（超时），仍然为所有窗口创建精简记录
                for title, _ in title_list:
                    project_name = _extract_project_name(title)
                    results.append(AIProjectState(
                        timestamp=time.time(),
                        pid=pid,
                        process_name=pname,
                        project_name=project_name,
                        window_title=title,
                        ai_status=AIStatus.UNKNOWN,
                        ai_model="",
                        agent_enabled=False,
                        progress_text="",
                        progress_pct=-1,
                        last_ai_output="",
                        ai_element_count=0,
                    ))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._scan_count += 1

        proj_list = [f"{r.project_name}({r.pid})" for r in results]
        summary = ", ".join(proj_list) if proj_list else "None"

        log_event(
            logger,
            f"Scan #{self._scan_count}: {len(results)} projects found: {summary} ({elapsed_ms:.0f}ms)",
            event_type="scan_complete",
            event_data={
                "project_count": len(results),
                "projects": proj_list,
                "elapsed_ms": round(elapsed_ms, 1)
            },
        )

        return results

    def scan_windows_fast(self) -> list[AIProjectState]:
        """
        ⚡ 快速窗口扫描（仅获取标题和 PID，不做 UIA 深度探测）

        用途：窗口匹配、项目列表获取（不需要 AI 状态信息时使用）
        耗时：通常 <100ms，远快于 scan_all() 的 5-30s

        关键修复 (2026-03-31):
        - 移除 seen_pids 去重，改为 seen_titles 去重
        - 同一 PID (如 Antigravity.exe) 可能同时打开多个项目窗口
        - 每个不同项目的窗口都需要返回，否则窗口匹配将丢失项目

        Returns:
            AIProjectState 精简列表（ai_status 等字段为默认值）
        """
        t0 = time.perf_counter()
        results = []
        seen_titles: set[str] = set()  # 按标题去重，而非按 PID
        verified_ide_pids: set[int] = set()  # 已验证为 IDE 进程的 PID 缓存

        try:
            windows = self._desktop.windows()
        except Exception:
            return results

        for w in windows:
            try:
                pid = w.process_id()

                # 仅对未验证的 PID 做进程名检查（缓存已验证的）
                if pid not in verified_ide_pids:
                    proc = psutil.Process(pid)
                    pname = proc.name()

                    if not _is_supported_workspace_process(pname):
                        continue

                    verified_ide_pids.add(pid)
                else:
                    proc = psutil.Process(pid)
                    pname = proc.name()

                title = w.window_text() or ""
                if not title or "Program Manager" in title:
                    continue

                # 跳过重复标题（同一窗口可能被枚举多次）
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                project_name = _extract_project_name(title)

                # 跳过提取出的项目名就是 IDE 名本身的情况（无意义）
                # 例如纯 "Antigravity" 标题 → project_name = "Antigravity"，不含项目信息
                # 但保留有实际项目名的窗口

                # 创建精简状态（不做 UIA 深度探测）
                results.append(AIProjectState(
                    timestamp=time.time(),
                    pid=pid,
                    process_name=pname,
                    project_name=project_name,
                    window_title=title,
                    ai_status=AIStatus.UNKNOWN,
                    ai_model="",
                    agent_enabled=False,
                    progress_text="",
                    progress_pct=-1,
                    last_ai_output="",
                    ai_element_count=0,
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        elapsed_ms = (time.perf_counter() - t0) * 1000
        proj_list = [f"{r.project_name}({r.pid})" for r in results]
        summary = ", ".join(proj_list) if proj_list else "None"

        log_event(
            logger,
            f"FastScan: {len(results)} projects found: {summary} ({elapsed_ms:.0f}ms)",
            event_type="fast_scan_complete",
            event_data={
                "project_count": len(results),
                "projects": proj_list,
                "elapsed_ms": round(elapsed_ms, 1)
            },
        )

        return results

    def probe_single(self, pid: int, window_title: str = "") -> Optional[AIProjectState]:
        """
        ⚡ 对单个已知 PID 做深度 UIA 探测（公开接口）

        用途：混合扫描架构——先 scan_windows_fast() 发现窗口，
              再对匹配的那 1 个 PID 调用此方法获取真实 ai_status

        关键修复 (2026-03-31):
        - 新增 window_title 参数：优先使用 fast_scan 已匹配的窗口标题
        - 解决同一 PID 多窗口时随机取标题导致项目名被覆盖的问题

        Args:
            pid: 目标进程 PID
            window_title: 已知的窗口标题（从 fast_scan 匹配结果传入）
                          如果为空则自动获取

        Returns:
            完整的 AIProjectState（含 ai_status），或 None（进程不存在/探测超时）
        """
        try:
            proc = psutil.Process(pid)
            pname = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

        # 如果调用方已提供标题，直接使用；否则自动获取
        title = window_title
        if not title:
            try:
                for w in self._desktop.windows():
                    try:
                        if w.process_id() == pid:
                            t = w.window_text() or ""
                            if t and "Program Manager" not in t:
                                title = t
                                break
                    except Exception:
                        continue
            except Exception:
                pass

        if not title:
            return None

        t0 = time.perf_counter()
        result = self._probe_project(pid, pname, title)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if result:
            log_event(
                logger,
                f"ProbeSingle: {result.project_name}({pid}) "
                f"status={result.ai_status.value} ({elapsed_ms:.0f}ms)",
                event_type="probe_single_complete",
            )

        return result

    def _probe_project(self, pid: int, pname: str, title: str) -> Optional[AIProjectState]:
        """探测单个 IDE 窗口的 AI 状态（带 5 秒超时防假死）"""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._probe_project_unsafe, pid, pname, title)
                return future.result(timeout=5.0)
        except concurrent.futures.TimeoutError:
            log_event(logger, f"UIA probe timeout for PID={pid} ({pname})", level=30)
            return None
        except Exception as e:
            return None

    def _probe_project_unsafe(self, pid: int, pname: str, title: str) -> Optional[AIProjectState]:
        """
        [内部] 定向 UIA 探测逻辑

        核心算法 (2026-03-31 重构):
        ┌─────────────────────────────────────────────────┐
        │  旧: app.windows() → 遍历全部 W 个窗口 × D 元素  │
        │      复杂度 O(W×D) → W=11 时必然超时            │
        │                                                 │
        │  新: app.windows() → 标题匹配锁定目标窗口       │
        │      仅遍历 1 个窗口 × D 元素                    │
        │      复杂度 O(D) → <1s                          │
        └─────────────────────────────────────────────────┘

        Fallback 链:
        1. 精确匹配 title → 单窗口探测
        2. 子串匹配 title → 单窗口探测
        3. top_window() → 单窗口探测
        """
        try:
            app = Application(backend=self._backend).connect(process=pid)
        except Exception:
            return None

        # ── Phase 1: 轻量操作——获取窗口列表并定位目标 ──
        target_win = None
        try:
            all_wins = app.windows()

            # 策略 1: 精确匹配标题
            for w in all_wins:
                try:
                    wt = w.window_text() or ""
                    if wt == title:
                        target_win = w
                        break
                except Exception:
                    continue

            # 策略 2: 子串匹配（标题可能有动态后缀变化）
            if target_win is None and title:
                title_key = title.split(" - ")[0].strip()  # 取首段作为匹配键
                for w in all_wins:
                    try:
                        wt = w.window_text() or ""
                        if title_key and title_key in wt:
                            target_win = w
                            break
                    except Exception:
                        continue

            # 策略 3: Fallback 到 top_window
            if target_win is None:
                target_win = app.top_window()

        except Exception:
            try:
                target_win = app.top_window()
            except Exception:
                return None

        if target_win is None:
            return None

        # ── Phase 2: 重量操作——仅遍历目标窗口的 UI 树 ──
        buttons = []
        texts = []
        checkboxes = []
        ai_element_count = 0

        AI_KEYWORDS = {
            "copilot", "chat", "cline", "cursor", "ai", "assistant",
            "github", "gemini", "claude", "gpt", "thinking", "generating",
            "loading", "spinner", "busy", "agent", "model",
        }

        try:
            descendants = target_win.descendants()

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
                            wt = target_win.window_text() or ""
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
            pass

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
