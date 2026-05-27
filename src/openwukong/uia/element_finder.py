# -*- coding: utf-8 -*-
"""
element_finder.py - 跨进程 UI 元素搜索模块

通过 UIA 控件树实现:
- 搜索指定窗口内的所有输入框 / 按钮 / 文本
- 跨所有进程全局搜索某种类型的元素
- 通过 AutomationId / Name / ControlType 精确定位元素
- 获取元素的属性（值、位置、可写性等）
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from pywinauto import Desktop
from pywinauto.application import Application


@dataclasses.dataclass
class ElementInfo:
    """UI 元素信息"""
    control_type: str
    name: str
    automation_id: str
    value: str
    rect: tuple[int, int, int, int]  # left, top, right, bottom
    is_enabled: bool
    is_writable: bool
    process_name: str
    pid: int
    window_title: str
    # 内部引用，用于后续交互操作
    _wrapper: object = dataclasses.field(default=None, repr=False)

    def __str__(self) -> str:
        rw = "RW" if self.is_writable else "RO"
        return (
            f"[{self.control_type}] {self.name or self.automation_id or '(unnamed)'} "
            f"({rw}) value=\"{self.value[:30]}\" "
            f"@ {self.process_name}:{self.window_title[:25]}"
        )


class _DescendantCache:
    """控件树后代缓存 + 名称/ID 哈希索引

    核心优化：避免每次操作都调用 win.descendants()
    缓存 TTL 默认 2s，命中期间 find_by_name 从 O(N) 降为 O(1)
    """

    def __init__(self, ttl: float = 2.0):
        self._ttl = ttl
        self._timestamp = 0.0
        self._descendants = []
        self._name_index: dict[str, list] = {}      # lower_name -> [wrapper, ...]
        self._id_index: dict[str, object] = {}       # automation_id -> wrapper
        self._pid = 0

    def get(self, app, pid: int = 0) -> list:
        """获取后代列表（命中缓存则直接返回）"""
        import time
        now = time.time()
        if (
            self._descendants
            and (now - self._timestamp) < self._ttl
            and pid == self._pid
        ):
            return self._descendants

        # 重新获取
        try:
            win = app.top_window()
            self._descendants = win.descendants()
            self._pid = pid
            self._timestamp = now
            self._rebuild_indexes()
        except Exception:
            self._descendants = []
            self._name_index = {}
            self._id_index = {}

        return self._descendants

    def _rebuild_indexes(self):
        """重建名称和 ID 的哈希索引"""
        self._name_index.clear()
        self._id_index.clear()

        for d in self._descendants:
            try:
                name = d.element_info.name or ""
                if name:
                    key = name.lower()
                    if key not in self._name_index:
                        self._name_index[key] = []
                    self._name_index[key].append(d)
            except Exception:
                pass

            try:
                aid = d.element_info.automation_id or ""
                if aid:
                    self._id_index[aid] = d
            except Exception:
                pass

    def find_by_name(self, name: str, exact: bool = False) -> list:
        """O(1) 名称索引查找"""
        if exact:
            key = name.lower()
            return self._name_index.get(key, [])
        else:
            name_lower = name.lower()
            results = []
            for key, wrappers in self._name_index.items():
                if name_lower in key:
                    results.extend(wrappers)
            return results

    def find_by_id(self, automation_id: str):
        """O(1) ID 索引查找"""
        return self._id_index.get(automation_id)

    def invalidate(self):
        """强制清除缓存"""
        self._timestamp = 0
        self._descendants = []
        self._name_index.clear()
        self._id_index.clear()


class ElementFinder:
    """
    UI 元素搜索引擎（含缓存优化）

    核心能力:
    - find_in_window(app, control_type):   在指定窗口内搜索控件
    - find_inputs(app):                    搜索所有输入框
    - find_buttons(app):                   搜索所有按钮
    - find_texts(app):                     搜索所有文本
    - find_by_id(app, automation_id):      按 AutomationId 精确定位（O(1) 缓存索引）
    - find_by_name(app, name):             按 Name 模糊搜索（O(1) 缓存索引）
    - global_find_inputs():                跨所有进程搜索输入框
    - get_element_tree(app):               获取完整控件树摘要
    """

    def __init__(self, backend: str = "uia"):
        self._backend = backend
        self._desktop = Desktop(backend=backend)
        self._cache = _DescendantCache(ttl=2.0)

    @staticmethod
    def _extract_info(
        wrapper,
        proc_name: str = "",
        pid: int = 0,
        win_title: str = "",
    ) -> ElementInfo:
        """从 pywinauto wrapper 提取元素信息"""
        ctrl_type = ""
        name = ""
        auto_id = ""
        value = ""
        rect = (0, 0, 0, 0)
        enabled = False
        writable = False

        try:
            ctrl_type = wrapper.element_info.control_type or "Unknown"
        except Exception:
            pass
        try:
            name = wrapper.element_info.name or ""
        except Exception:
            pass
        try:
            auto_id = wrapper.element_info.automation_id or ""
        except Exception:
            pass
        try:
            value = wrapper.window_text() or ""
        except Exception:
            pass
        try:
            r = wrapper.rectangle()
            rect = (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
        try:
            enabled = wrapper.is_enabled()
        except Exception:
            pass
        try:
            # Edit 类型默认可写（除非 IsReadOnly）
            if ctrl_type == "Edit" and enabled:
                writable = True
                try:
                    ro = wrapper.get_value_pattern_attribute("IsReadOnly")
                    if ro:
                        writable = False
                except Exception:
                    pass
        except Exception:
            pass

        return ElementInfo(
            control_type=ctrl_type,
            name=name,
            automation_id=auto_id,
            value=value,
            rect=rect,
            is_enabled=enabled,
            is_writable=writable,
            process_name=proc_name,
            pid=pid,
            window_title=win_title,
            _wrapper=wrapper,
        )

    def find_in_window(
        self,
        app: Application,
        control_type: Optional[str] = None,
        max_results: int = 50,
    ) -> list[ElementInfo]:
        """在指定应用的所有窗口内搜索控件"""
        try:
            import psutil
        except ImportError:
            psutil = None

        results: list[ElementInfo] = []

        # 枚举所有窗口（多窗口准确性保障）
        all_wins = []
        try:
            all_wins = app.windows()
        except Exception:
            pass
        if not all_wins:
            try:
                all_wins = [app.top_window()]
            except Exception:
                return results

        for win in all_wins:
            try:
                pid = win.process_id()
                proc_name = ""
                if psutil:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except Exception:
                        pass
                win_title = win.window_text() or ""
                if not win_title or "Program Manager" in win_title:
                    continue

                kwargs = {}
                if control_type:
                    kwargs["control_type"] = control_type

                descendants = win.descendants(**kwargs)
                for d in descendants:
                    try:
                        info = self._extract_info(d, proc_name, pid, win_title)
                        results.append(info)
                        if len(results) >= max_results:
                            return results
                    except Exception:
                        continue
            except Exception:
                continue

        return results

    def find_inputs(self, app: Application, max_results: int = 50) -> list[ElementInfo]:
        """搜索指定窗口内的所有输入框 (Edit 控件)"""
        return self.find_in_window(app, control_type="Edit", max_results=max_results)

    def find_buttons(self, app: Application, max_results: int = 50) -> list[ElementInfo]:
        """搜索指定窗口内的所有按钮"""
        return self.find_in_window(app, control_type="Button", max_results=max_results)

    def find_texts(self, app: Application, max_results: int = 50) -> list[ElementInfo]:
        """搜索指定窗口内的所有文本元素"""
        return self.find_in_window(app, control_type="Text", max_results=max_results)

    def find_by_id(self, app: Application, automation_id: str) -> Optional[ElementInfo]:
        """通过 AutomationId 精确定位元素（O(1) 缓存索引）"""
        try:
            win = app.top_window()
            pid = win.process_id()

            import psutil
            proc_name = ""
            try:
                proc_name = psutil.Process(pid).name()
            except Exception:
                pass

            # 先确保缓存已加载
            self._cache.get(app, pid)

            # O(1) 索引查找
            d = self._cache.find_by_id(automation_id)
            if d:
                return self._extract_info(d, proc_name, pid, win.window_text() or "")
        except Exception:
            pass
        return None

    def find_by_name(
        self,
        app: Application,
        name: str,
        exact: bool = False,
        max_results: int = 20,
    ) -> list[ElementInfo]:
        """通过 Name 搜索元素（O(1) 缓存索引 + 模糊匹配）"""
        results: list[ElementInfo] = []

        try:
            win = app.top_window()
            pid = win.process_id()

            import psutil
            proc_name = ""
            try:
                proc_name = psutil.Process(pid).name()
            except Exception:
                pass

            # 触发缓存加载
            self._cache.get(app, pid)

            # O(1) 索引查找（包含模糊匹配）
            matched_wrappers = self._cache.find_by_name(name, exact=exact)

            for d in matched_wrappers[:max_results]:
                try:
                    info = self._extract_info(
                        d, proc_name, pid, win.window_text() or ""
                    )
                    results.append(info)
                except Exception:
                    continue
        except Exception:
            pass

        return results

    def global_find_inputs(self, max_per_window: int = 10) -> list[ElementInfo]:
        """跨所有进程全局搜索输入框"""
        try:
            import psutil
        except ImportError:
            psutil = None

        results: list[ElementInfo] = []
        windows = self._desktop.windows()

        for w in windows:
            try:
                title = w.window_text()
                if not title or "Program Manager" in title:
                    continue

                pid = w.process_id()
                proc_name = ""
                if psutil:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except Exception:
                        pass

                edits = w.descendants(control_type="Edit")
                for edit in edits[:max_per_window]:
                    try:
                        info = self._extract_info(edit, proc_name, pid, title)
                        results.append(info)
                    except Exception:
                        continue
            except Exception:
                continue

        return results

    def get_element_tree(
        self, app: Application, max_depth: int = 3
    ) -> dict:
        """获取控件树摘要（类型统计 + 前 N 个元素详情）"""
        try:
            win = app.top_window()
            descendants = win.descendants()

            type_counts: dict[str, int] = {}
            sample_elements: list[dict] = []

            for i, d in enumerate(descendants):
                try:
                    ct = d.element_info.control_type or "Unknown"
                    type_counts[ct] = type_counts.get(ct, 0) + 1

                    if i < 30:
                        name = d.element_info.name or ""
                        aid = d.element_info.automation_id or ""
                        sample_elements.append({
                            "type": ct,
                            "name": name[:50],
                            "automation_id": aid[:30],
                        })
                except Exception:
                    continue

            return {
                "window_title": win.window_text(),
                "total_elements": len(descendants),
                "type_counts": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
                "sample_elements": sample_elements,
            }
        except Exception as e:
            return {"error": str(e)}
