# -*- coding: utf-8 -*-
"""
uia_controller.py - UIA 核心控制器

整合 ProcessTree + ElementFinder，提供统一的高级操作接口:
- 连接进程 → 查找元素 → 执行交互（点击/输入/读取）
- 支持链式操作和批量查询
"""

from __future__ import annotations

import time
from typing import Optional

from pywinauto.application import Application

from process_tree import ProcessTree, ProcessInfo
from element_finder import ElementFinder, ElementInfo


class UIAController:
    """
    UIA 核心控制器

    使用示例:
        ctrl = UIAController()

        # 列出所有 GUI 进程
        procs = ctrl.list_processes()

        # 连接到 Edge 浏览器
        ctrl.connect_to("msedge")

        # 查找地址栏并输入
        inputs = ctrl.find_inputs()
        ctrl.type_text(inputs[0], "https://example.com")

        # 查找并点击按钮
        buttons = ctrl.find_buttons()
        ctrl.click(buttons[0])

        # 读取某个元素的当前值
        value = ctrl.read_value(inputs[0])
    """

    def __init__(self, backend: str = "uia"):
        self._backend = backend
        self._process_tree = ProcessTree(backend=backend)
        self._element_finder = ElementFinder(backend=backend)
        self._current_app: Optional[Application] = None
        self._current_process: Optional[ProcessInfo] = None

    # ── 进程管理 ──

    def list_processes(self) -> list[ProcessInfo]:
        """列出所有带 GUI 窗口的进程"""
        return self._process_tree.list_gui_processes()

    def connect_to(self, target: str | int) -> ProcessInfo:
        """
        连接到目标进程

        Args:
            target: PID (int) 或 进程名/窗口标题关键词 (str)

        Returns:
            连接的进程信息
        """
        if isinstance(target, int):
            proc_info = self._process_tree.find_by_pid(target)
            if not proc_info:
                raise ValueError(f"No process found with PID: {target}")
            self._current_app = self._process_tree.connect(target)
            self._current_process = proc_info
        else:
            # 先按进程名找，找不到再按窗口标题找
            procs = self._process_tree.find_by_name(target)
            if not procs:
                procs = self._process_tree.find_by_title(target)
            if not procs:
                raise ValueError(f"No process found matching: {target}")

            self._current_process = procs[0]
            self._current_app = self._process_tree.connect(procs[0].pid)

        return self._current_process

    @property
    def connected(self) -> bool:
        """是否已连接进程"""
        return self._current_app is not None

    @property
    def current_process(self) -> Optional[ProcessInfo]:
        """当前连接的进程"""
        return self._current_process

    def _ensure_connected(self) -> Application:
        if not self._current_app:
            raise RuntimeError("Not connected. Call connect_to() first.")

        # 心跳检测：验证连接是否仍有效
        try:
            self._current_app.top_window()
        except Exception:
            # 连接失效，尝试自动重连
            if self._current_process:
                try:
                    if self._process_tree.is_alive(self._current_process.pid):
                        self._current_app = self._process_tree.connect(
                            self._current_process.pid
                        )
                    else:
                        self._current_app = None
                        self._current_process = None
                        raise RuntimeError(
                            "Target process no longer alive. Call connect_to() again."
                        )
                except RuntimeError:
                    raise
                except Exception:
                    self._current_app = None
                    self._current_process = None
                    raise RuntimeError(
                        "Reconnection failed. Call connect_to() again."
                    )

        return self._current_app

    def disconnect(self):
        """断开当前连接并清理资源"""
        self._current_app = None
        self._current_process = None

    # ── 元素查找 ──

    def find_inputs(self, max_results: int = 50) -> list[ElementInfo]:
        """查找当前窗口中的所有输入框"""
        app = self._ensure_connected()
        return self._element_finder.find_inputs(app, max_results=max_results)

    def find_buttons(self, max_results: int = 50) -> list[ElementInfo]:
        """查找当前窗口中的所有按钮"""
        app = self._ensure_connected()
        return self._element_finder.find_buttons(app, max_results=max_results)

    def find_texts(self, max_results: int = 50) -> list[ElementInfo]:
        """查找当前窗口中的所有文本元素"""
        app = self._ensure_connected()
        return self._element_finder.find_texts(app, max_results=max_results)

    def find_by_id(self, automation_id: str) -> Optional[ElementInfo]:
        """通过 AutomationId 精确定位元素"""
        app = self._ensure_connected()
        return self._element_finder.find_by_id(app, automation_id)

    def find_by_name(self, name: str, exact: bool = False) -> list[ElementInfo]:
        """通过 Name 搜索元素"""
        app = self._ensure_connected()
        return self._element_finder.find_by_name(app, name, exact=exact)

    def get_tree(self) -> dict:
        """获取当前窗口的控件树摘要"""
        app = self._ensure_connected()
        return self._element_finder.get_element_tree(app)

    def global_find_inputs(self, max_per_window: int = 10) -> list[ElementInfo]:
        """跨所有进程全局搜索输入框（无需预先连接）"""
        return self._element_finder.global_find_inputs(max_per_window=max_per_window)

    # ── 交互操作 ──

    def type_text(self, element: ElementInfo, text: str, clear_first: bool = True) -> bool:
        """
        向输入框输入文本

        Args:
            element: 目标输入框的 ElementInfo
            text: 要输入的文本
            clear_first: 是否先清空现有内容

        Returns:
            是否成功
        """
        wrapper = element._wrapper
        if wrapper is None:
            raise ValueError("Element has no wrapper reference for interaction")

        try:
            if clear_first:
                try:
                    wrapper.set_edit_text("")
                except Exception:
                    wrapper.type_keys("^a{DELETE}", pause=0.02)

            # 优先使用 set_edit_text（更稳定），fallback 到 type_keys
            try:
                wrapper.set_edit_text(text)
            except Exception:
                wrapper.type_keys(text, with_spaces=True, pause=0.02)
            return True
        except Exception:
            return False

    def click(self, element: ElementInfo) -> bool:
        """点击元素"""
        wrapper = element._wrapper
        if wrapper is None:
            raise ValueError("Element has no wrapper reference for interaction")

        try:
            wrapper.click_input()
            return True
        except Exception:
            try:
                # 尝试 invoke（对按钮更可靠）
                wrapper.invoke()
                return True
            except Exception:
                return False

    def read_value(self, element: ElementInfo) -> str:
        """读取元素的当前值/文本"""
        wrapper = element._wrapper
        if wrapper is None:
            return element.value

        try:
            return wrapper.window_text() or ""
        except Exception:
            return element.value

    def focus(self, element: ElementInfo) -> bool:
        """将焦点设定到指定元素"""
        wrapper = element._wrapper
        if wrapper is None:
            return False

        try:
            wrapper.set_focus()
            return True
        except Exception:
            return False

    def screenshot_element(self, element: ElementInfo, save_path: str) -> bool:
        """截取指定元素的截图"""
        wrapper = element._wrapper
        if wrapper is None:
            return False

        try:
            img = wrapper.capture_as_image()
            img.save(save_path)
            return True
        except Exception:
            return False

    # ── 便捷方法 ──

    def find_and_type(self, field_name: str, text: str) -> bool:
        """查找输入框并输入文本（一步到位）"""
        elements = self.find_by_name(field_name)
        edits = [e for e in elements if e.control_type == "Edit"]
        if not edits:
            return False
        return self.type_text(edits[0], text)

    def find_and_click(self, button_name: str) -> bool:
        """查找按钮并点击（一步到位）"""
        elements = self.find_by_name(button_name)
        buttons = [e for e in elements if e.control_type in ("Button", "MenuItem", "Hyperlink")]
        if not buttons:
            return False
        return self.click(buttons[0])

    def wait_for_element(
        self,
        name: str,
        timeout: float = 10.0,
        interval: float = 0.5,
    ) -> Optional[ElementInfo]:
        """等待元素出现"""
        start = time.time()
        while time.time() - start < timeout:
            elements = self.find_by_name(name)
            if elements:
                return elements[0]
            time.sleep(interval)
        return None
