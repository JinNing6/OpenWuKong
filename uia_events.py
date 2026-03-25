# -*- coding: utf-8 -*-
"""
uia_events.py - UIA 事件订阅引擎 (安全版 v2)

v2 修复:
- 消除全桌面 StructureChanged 订阅 → 仅监听目标进程窗口
- COM 线程模型修复 → handler 创建/注册/消息泵全部在同一守护线程
- 事件速率限制器 → 防止事件洪水导致内存泄漏和 BSOD

通过 comtypes 直接调用 Windows UIA COM 接口订阅事件:
- 焦点变化 (FocusChanged)
- 属性变更 (PropertyChanged) - 元素名称/值变化

所有事件推入线程安全队列，供主循环消费。
"""

from __future__ import annotations

import queue
import threading
import time
import dataclasses
from enum import Enum
from typing import Optional, Callable

from logger import get_logger, log_event

logger = get_logger("events")


class EventType(str, Enum):
    """UIA 事件类型"""
    FOCUS_CHANGED = "focus_changed"
    WINDOW_OPENED = "window_opened"
    WINDOW_CLOSED = "window_closed"
    STRUCTURE_CHANGED = "structure_changed"
    PROPERTY_CHANGED = "property_changed"
    PROCESS_STARTED = "process_started"
    PROCESS_EXITED = "process_exited"


@dataclasses.dataclass
class UIAEvent:
    """UIA 事件数据"""
    event_type: EventType
    timestamp: float
    pid: int = 0
    process_name: str = ""
    element_name: str = ""
    element_type: str = ""
    automation_id: str = ""
    old_value: str = ""
    new_value: str = ""
    extra: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "pid": self.pid,
            "process_name": self.process_name,
            "element_name": self.element_name,
            "element_type": self.element_type,
            "automation_id": self.automation_id,
            "old_value": self.old_value[:100] if self.old_value else "",
            "new_value": self.new_value[:100] if self.new_value else "",
        }


class _EventRateLimiter:
    """
    事件速率限制器 — 防止 COM 事件洪水

    使用滑动窗口（1 秒）计数，超限后丢弃事件。
    线程安全：所有 COM handler 回调均在同一线程。
    """

    def __init__(self, max_per_second: int = 50):
        self._max = max_per_second
        self._window_start = 0.0
        self._count = 0
        self._dropped = 0
        self._total_dropped = 0

    def allow(self) -> bool:
        """检查是否允许当前事件通过"""
        now = time.time()

        # 新的 1 秒窗口
        if now - self._window_start >= 1.0:
            if self._dropped > 0:
                # 上一个窗口有丢弃，延迟到下一次日志输出
                self._total_dropped += self._dropped
                self._dropped = 0
            self._window_start = now
            self._count = 0

        self._count += 1
        if self._count > self._max:
            self._dropped += 1
            return False

        return True

    @property
    def total_dropped(self) -> int:
        return self._total_dropped + self._dropped


def _load_uia_com():
    """加载 UIA COM 类型库"""
    import comtypes
    import comtypes.client
    try:
        mod = comtypes.client.GetModule("UIAutomationCore.dll")
        return mod
    except Exception:
        # 如果类型库已缓存，直接导入
        try:
            from comtypes.gen import UIAutomationClient as mod
            return mod
        except ImportError:
            return None


def _safe_get_pid(sender) -> int:
    """安全获取 sender 的 PID"""
    try:
        return sender.CurrentProcessId
    except Exception:
        return 0


def _safe_get_name(sender) -> str:
    """安全获取 sender 的 Name"""
    try:
        return sender.CurrentName or ""
    except Exception:
        return ""


def _safe_get_control_type(sender) -> str:
    """安全获取 sender 的 ControlType"""
    try:
        return str(sender.CurrentControlType)
    except Exception:
        return ""


def _safe_get_automation_id(sender) -> str:
    """安全获取 sender 的 AutomationId"""
    try:
        return sender.CurrentAutomationId or ""
    except Exception:
        return ""


class UIAEventEngine:
    """
    UIA 事件订阅引擎 (安全版 v2)

    核心安全改进:
    1. COM 全生命周期在同一守护线程（CoInitialize → 注册 → 消息泵 → 注销 → CoUninitialize）
    2. 仅注册 FocusChanged 事件（全局安全的），不注册全桌面 StructureChanged
    3. 事件速率限制器防止洪水
    4. 所有 COM 访问包裹 try/except
    """

    def __init__(
        self,
        target_pid: int = 0,
        target_pids: Optional[set[int]] = None,
        max_events_per_second: int = 50,
    ):
        self._event_queue: queue.Queue[UIAEvent] = queue.Queue(maxsize=10000)

        # 兼容旧接口：支持 target_pids 参数
        if target_pids:
            self._target_pids = target_pids
        elif target_pid:
            self._target_pids = {target_pid}
        else:
            self._target_pids: set[int] = set()

        self._max_events_per_second = max_events_per_second
        self._com_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = threading.Event()
        self._init_error: Optional[str] = None

    @property
    def event_queue(self) -> queue.Queue[UIAEvent]:
        return self._event_queue

    @property
    def is_running(self) -> bool:
        return self._running and self._com_thread is not None and self._com_thread.is_alive()

    def start(self) -> bool:
        """
        启动事件引擎

        COM 全生命周期在守护线程中完成:
        CoInitialize → 创建 UIA → 注册 handler → 消息泵 → 注销 → CoUninitialize
        """
        if self._running:
            return True

        self._initialized.clear()
        self._init_error = None
        self._running = True

        self._com_thread = threading.Thread(
            target=self._com_thread_main,
            name="uia-event-engine",
            daemon=True,
        )
        self._com_thread.start()

        # 等待守护线程完成初始化（最长 10 秒）
        if not self._initialized.wait(timeout=10.0):
            log_event(
                logger, "COM engine init timeout",
                event_type="engine_error", level=40,
            )
            self._running = False
            return False

        if self._init_error:
            log_event(
                logger, f"COM engine init failed: {self._init_error}",
                event_type="engine_error", level=40,
            )
            self._running = False
            return False

        log_event(logger, "UIA event engine started (v2 safe mode)", event_type="engine_start")
        return True

    def stop(self):
        """停止事件引擎"""
        self._running = False

        if self._com_thread and self._com_thread.is_alive():
            # 发送 WM_QUIT 到消息泵线程
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(
                    self._com_thread.ident, 0x0012, 0, 0  # WM_QUIT
                )
            except Exception:
                pass

            # 等待线程退出（超时保护）
            self._com_thread.join(timeout=10)
            if self._com_thread.is_alive():
                log_event(
                    logger, "COM thread did not exit cleanly within 10s",
                    event_type="engine_warning", level=30,
                )

        log_event(logger, "UIA event engine stopped", event_type="engine_stop")

    def update_target_pids(self, pids: set[int]):
        """更新目标进程过滤器（线程安全，仅更新 Python 对象引用）"""
        self._target_pids = pids

    def update_target(self, new_pid: int):
        """更新单个目标进程（便捷方法）"""
        self._target_pids = {new_pid}

    def get_event(self, timeout: float = 0.1) -> Optional[UIAEvent]:
        """从队列中取一个事件"""
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_events(self, max_count: int = 100) -> list[UIAEvent]:
        """批量取出事件"""
        events = []
        for _ in range(max_count):
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break
        return events

    def _com_thread_main(self):
        """
        COM 守护线程主函数

        关键: 所有 COM 操作都在同一个线程完成，保证 COM 套间模型一致性。
        """
        import comtypes
        import comtypes.client
        from comtypes import COMObject
        import ctypes
        import ctypes.wintypes

        uia = None
        handlers = []
        rate_limiter = _EventRateLimiter(self._max_events_per_second)

        try:
            # ── 阶段 1: COM 初始化 ──
            comtypes.CoInitialize()

            uia_mod = _load_uia_com()
            if uia_mod is None:
                self._init_error = "Failed to load UIAutomationCore.dll type library"
                self._initialized.set()
                return

            # 创建 IUIAutomation 实例
            clsid = comtypes.GUID("{FF48DBA4-60EF-4201-AA87-54103EEF594E}")
            uia = comtypes.CoCreateInstance(clsid, interface=None)
            try:
                if hasattr(uia_mod, "IUIAutomation"):
                    uia = uia.QueryInterface(uia_mod.IUIAutomation)
            except Exception:
                pass

            # ── 阶段 2: 注册 FocusChanged 事件（全局安全） ──
            if hasattr(uia_mod, "IUIAutomationFocusChangedEventHandler"):
                try:
                    # 动态创建 handler 类（在 COM 线程内）
                    event_queue_ref = self._event_queue
                    target_pids_ref = self  # 用 self 间接引用 _target_pids，支持动态更新

                    class _FocusHandler(COMObject):
                        _com_interfaces_ = [uia_mod.IUIAutomationFocusChangedEventHandler]

                        def HandleFocusChangedEvent(self, sender):
                            try:
                                # 速率限制
                                if not rate_limiter.allow():
                                    return

                                pid = _safe_get_pid(sender)

                                # PID 过滤
                                current_pids = target_pids_ref._target_pids
                                if current_pids and pid not in current_pids:
                                    return

                                event = UIAEvent(
                                    event_type=EventType.FOCUS_CHANGED,
                                    timestamp=time.time(),
                                    pid=pid,
                                    element_name=_safe_get_name(sender),
                                    element_type=_safe_get_control_type(sender),
                                    automation_id=_safe_get_automation_id(sender),
                                )

                                try:
                                    event_queue_ref.put_nowait(event)
                                except queue.Full:
                                    pass

                            except Exception:
                                pass

                    focus_handler = _FocusHandler()
                    uia.AddFocusChangedEventHandler(None, focus_handler)
                    handlers.append(focus_handler)
                    log_event(logger, "Focus event handler registered (in COM thread)", event_type="handler_registered")
                except Exception as e:
                    log_event(logger, f"Focus handler registration failed: {e}", level=30)

            # ── 注意: 不注册 StructureChanged 事件 ──
            # 全桌面 StructureChanged (TreeScope.Subtree=7) 是
            # BSOD 的已知根因 (UIAutomationCore.dll AccessViolation)
            # 进程启动/退出检测改由 PollingEventEngine 安全实现

            # 初始化完成，通知主线程
            self._initialized.set()

            # ── 阶段 3: 消息泵循环 ──
            msg = ctypes.wintypes.MSG()
            while self._running:
                result = ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 1  # PM_REMOVE
                )
                if result:
                    if msg.message == 0x0012:  # WM_QUIT
                        break
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.05)  # 50ms 间隔，比 v1 的 10ms 更保守

        except Exception as e:
            if not self._initialized.is_set():
                self._init_error = str(e)
                self._initialized.set()
            else:
                log_event(logger, f"COM thread error: {e}", event_type="engine_error", level=40)

        finally:
            # ── 阶段 4: 安全清理 ──
            if uia:
                try:
                    uia.RemoveAllEventHandlers()
                except Exception:
                    pass

            handlers.clear()

            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

            # 报告丢弃统计
            if rate_limiter.total_dropped > 0:
                log_event(
                    logger,
                    f"Rate limiter dropped {rate_limiter.total_dropped} events total",
                    event_type="rate_limit_stats",
                )


class PollingEventEngine:
    """
    基于轮询的事件检测引擎（UIA COM 事件不可用时的 fallback）

    对比前后两次快照的 diff，检测变化。
    这是安全的检测方式，不涉及 COM 事件订阅。
    """

    def __init__(self, target_pids: Optional[set[int]] = None):
        self._event_queue: queue.Queue[UIAEvent] = queue.Queue(maxsize=10000)
        self._target_pids = target_pids or set()
        self._last_snapshot: dict = {}
        self._running = False

    @property
    def event_queue(self) -> queue.Queue[UIAEvent]:
        return self._event_queue

    def detect_changes(self, current_snapshot: dict) -> list[UIAEvent]:
        """对比前后快照，生成变更事件"""
        events = []

        if not self._last_snapshot:
            self._last_snapshot = current_snapshot
            return events

        old_pids = set(self._last_snapshot.get("pids", {}).keys())
        new_pids = set(current_snapshot.get("pids", {}).keys())

        # 进程启动
        for pid in new_pids - old_pids:
            info = current_snapshot["pids"].get(pid, {})
            event = UIAEvent(
                event_type=EventType.PROCESS_STARTED,
                timestamp=time.time(),
                pid=pid,
                process_name=info.get("name", ""),
                element_name=info.get("title", ""),
            )
            events.append(event)
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                pass

        # 进程退出
        for pid in old_pids - new_pids:
            info = self._last_snapshot["pids"].get(pid, {})
            event = UIAEvent(
                event_type=EventType.PROCESS_EXITED,
                timestamp=time.time(),
                pid=pid,
                process_name=info.get("name", ""),
            )
            events.append(event)
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                pass

        # 窗口标题变化（活跃文件切换）
        for pid in new_pids & old_pids:
            old_title = self._last_snapshot["pids"].get(pid, {}).get("title", "")
            new_title = current_snapshot["pids"].get(pid, {}).get("title", "")
            if old_title != new_title and new_title:
                event = UIAEvent(
                    event_type=EventType.FOCUS_CHANGED,
                    timestamp=time.time(),
                    pid=pid,
                    process_name=current_snapshot["pids"][pid].get("name", ""),
                    old_value=old_title,
                    new_value=new_title,
                )
                events.append(event)
                try:
                    self._event_queue.put_nowait(event)
                except queue.Full:
                    pass

        self._last_snapshot = current_snapshot
        return events

    def get_event(self, timeout: float = 0.1) -> Optional[UIAEvent]:
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_events(self, max_count: int = 100) -> list[UIAEvent]:
        events = []
        for _ in range(max_count):
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events
