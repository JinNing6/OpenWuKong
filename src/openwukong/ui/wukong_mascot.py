# -*- coding: utf-8 -*-
"""
wukong_mascot.py — 🐵 悟空桌面宠物

一个可爱的孙悟空形象常驻桌面，实时反映 Agent 工作状态。

功能：
  - 透明窗口 + 精灵帧切换（5 种状态）
  - 拖拽移动
  - 气泡对话提示
  - 右键菜单（打开面板 / 切换模式 / 退出）
  - 状态自动呼吸动画（缓慢上下浮动）

技术栈：tkinter（透明窗口 + Canvas）
"""

from __future__ import annotations

import os
import math
import time
import threading
from tkinter import Menu
from typing import Optional, Callable

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import tkinter as tk


# ═══════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# 精灵文件映射
SPRITE_FILES = {
    "idle":     "wukong_idle.png",
    "thinking": "wukong_thinking.png",
    "working":  "wukong_working.png",
    "success":  "wukong_success.png",
    "error":    "wukong_error.png",
}

# 气泡台词
BUBBLE_TEXTS = {
    "idle":     ["俺老孙在此！", "有啥任务尽管说~", "待命中... 🐵", "闲着也是闲着~"],
    "thinking": ["让俺想想...", "嗯... 这个有点意思", "容我三思 🤔"],
    "working":  ["看俺的筋斗云！", "正在全力以赴！", "交给俺没问题！", "忙碌中... 💪"],
    "success":  ["大功告成！🎉", "妖怪已除！", "任务完成！", "漂亮！✨"],
    "error":    ["哎呀！出问题了...", "遇到妖怪了！", "不慌，俺来修！", "有点棘手... 🔥"],
}

# 宠物窗口大小
MASCOT_SIZE = 128
# 气泡最大宽度
BUBBLE_MAX_W = 220


class WukongMascot:
    """
    🐵 悟空桌面宠物

    在桌面右下角显示一个可爱的悟空形象，
    支持拖拽、右键菜单、状态切换和气泡对话。
    """

    def __init__(
        self,
        on_open_panel: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
        initial_state: str = "idle",
    ):
        self._on_open_panel = on_open_panel
        self._on_exit = on_exit
        self._current_state = initial_state
        self._sprites: dict[str, tk.PhotoImage | None] = {}
        self._bubble_id: Optional[str] = None
        self._bubble_text_id: Optional[str] = None
        self._bubble_timer: Optional[str] = None
        self._breath_phase: float = 0.0

        # 拖拽状态
        self._drag_x = 0
        self._drag_y = 0

        # 构建窗口
        self._root = tk.Tk()
        self._root.withdraw()  # 先隐藏，配置完再显示
        self._setup_window()
        self._load_sprites()
        self._build_canvas()
        self._build_context_menu()
        self._position_bottom_right()

        # 显示
        self._root.deiconify()

        # 启动呼吸动画
        self._animate_breath()

        # 自动显示欢迎气泡
        self._root.after(500, lambda: self.show_bubble("俺老孙来也！🐵"))

    # ═══════════════════════════════════════════
    #  窗口配置
    # ═══════════════════════════════════════════

    def _setup_window(self):
        """配置透明无边框置顶窗口"""
        self._root.title("WuKong Mascot")
        self._root.overrideredirect(True)  # 无边框
        self._root.attributes("-topmost", True)  # 始终置顶

        # Windows 透明色
        transparent_color = "#010101"
        self._transparent_color = transparent_color
        self._root.configure(bg=transparent_color)
        self._root.attributes("-transparentcolor", transparent_color)

        # 窗口大小（精灵 + 气泡空间）
        self._window_w = MASCOT_SIZE + BUBBLE_MAX_W + 20
        self._window_h = MASCOT_SIZE + 60
        self._root.geometry(f"{self._window_w}x{self._window_h}")

    def _position_bottom_right(self):
        """定位到屏幕右下角"""
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - self._window_w - 20
        y = screen_h - self._window_h - 80  # 预留任务栏空间
        self._root.geometry(f"+{x}+{y}")

    # ═══════════════════════════════════════════
    #  精灵加载
    # ═══════════════════════════════════════════

    def _load_sprites(self):
        """加载所有状态的精灵图"""
        for state_key, filename in SPRITE_FILES.items():
            filepath = os.path.join(ASSETS_DIR, filename)
            if os.path.isfile(filepath):
                try:
                    if HAS_PIL:
                        pil_img = Image.open(filepath).convert("RGBA")
                        pil_img = pil_img.resize(
                            (MASCOT_SIZE, MASCOT_SIZE), Image.LANCZOS
                        )
                        # 为 tkinter 创建合成图：透明区域用透明色填充
                        bg = Image.new("RGBA", pil_img.size, self._transparent_color + "FF")
                        composite = Image.alpha_composite(bg, pil_img)
                        self._sprites[state_key] = ImageTk.PhotoImage(composite.convert("RGB"))
                    else:
                        self._sprites[state_key] = tk.PhotoImage(file=filepath)
                except Exception:
                    self._sprites[state_key] = None
            else:
                self._sprites[state_key] = None

    # ═══════════════════════════════════════════
    #  Canvas 构建
    # ═══════════════════════════════════════════

    def _build_canvas(self):
        """构建画布，放置精灵和气泡"""
        self._canvas = tk.Canvas(
            self._root,
            width=self._window_w,
            height=self._window_h,
            bg=self._transparent_color,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # 放置精灵图
        sprite = self._sprites.get(self._current_state)
        self._sprite_x = BUBBLE_MAX_W + 10
        self._sprite_y = 30
        if sprite:
            self._sprite_item = self._canvas.create_image(
                self._sprite_x, self._sprite_y,
                image=sprite, anchor="nw",
            )
        else:
            # 无图片时用 emoji 替代
            self._sprite_item = self._canvas.create_text(
                self._sprite_x + MASCOT_SIZE // 2,
                self._sprite_y + MASCOT_SIZE // 2,
                text="🐵", font=("Segoe UI Emoji", 48),
            )

        # 绑定事件
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self._canvas.bind("<Button-3>", self._on_right_click)
        self._canvas.bind("<Double-Button-1>", self._on_double_click)

    # ═══════════════════════════════════════════
    #  右键菜单
    # ═══════════════════════════════════════════

    def _build_context_menu(self):
        """构建右键菜单"""
        self._menu = Menu(self._root, tearoff=0, font=("Segoe UI", 10))
        self._menu.add_command(
            label="🖥  打开控制面板",
            command=self._cmd_open_panel,
        )
        self._menu.add_separator()
        self._menu.add_command(
            label="😴  待机",
            command=lambda: self.set_state("idle"),
        )
        self._menu.add_command(
            label="🤔  思考中",
            command=lambda: self.set_state("thinking"),
        )
        self._menu.add_command(
            label="💪  工作中",
            command=lambda: self.set_state("working"),
        )
        self._menu.add_command(
            label="🎉  成功",
            command=lambda: self.set_state("success"),
        )
        self._menu.add_command(
            label="🔥  错误",
            command=lambda: self.set_state("error"),
        )
        self._menu.add_separator()
        self._menu.add_command(
            label="❌  退出悟空",
            command=self._cmd_exit,
        )

    # ═══════════════════════════════════════════
    #  交互事件
    # ═══════════════════════════════════════════

    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self._root.winfo_x() + (event.x - self._drag_x)
        y = self._root.winfo_y() + (event.y - self._drag_y)
        self._root.geometry(f"+{x}+{y}")

    def _on_click(self, event):
        """单击：显示随机气泡"""
        import random
        texts = BUBBLE_TEXTS.get(self._current_state, BUBBLE_TEXTS["idle"])
        self.show_bubble(random.choice(texts))

    def _on_double_click(self, event):
        """双击：打开面板"""
        self._cmd_open_panel()

    def _on_right_click(self, event):
        """右键：弹出菜单"""
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _cmd_open_panel(self):
        if self._on_open_panel:
            self._on_open_panel()
        else:
            self.show_bubble("面板功能开发中~")

    def _cmd_exit(self):
        if self._on_exit:
            self._on_exit()
        self._root.destroy()

    # ═══════════════════════════════════════════
    #  状态切换
    # ═══════════════════════════════════════════

    def set_state(self, state: str, bubble_text: str = ""):
        """
        切换悟空状态

        Args:
            state: idle / thinking / working / success / error
            bubble_text: 可选的自定义气泡文字
        """
        if state not in SPRITE_FILES:
            return

        self._current_state = state

        # 更新精灵图
        sprite = self._sprites.get(state)
        if sprite:
            self._canvas.delete(self._sprite_item)
            self._sprite_item = self._canvas.create_image(
                self._sprite_x, self._sprite_y,
                image=sprite, anchor="nw",
            )
        else:
            self._canvas.delete(self._sprite_item)
            state_emoji = {"idle": "🐵", "thinking": "🤔", "working": "💪", "success": "🎉", "error": "🔥"}
            self._sprite_item = self._canvas.create_text(
                self._sprite_x + MASCOT_SIZE // 2,
                self._sprite_y + MASCOT_SIZE // 2,
                text=state_emoji.get(state, "🐵"),
                font=("Segoe UI Emoji", 48),
            )

        # 气泡
        if bubble_text:
            self.show_bubble(bubble_text)
        else:
            import random
            texts = BUBBLE_TEXTS.get(state, BUBBLE_TEXTS["idle"])
            self.show_bubble(random.choice(texts))

    # ═══════════════════════════════════════════
    #  气泡系统
    # ═══════════════════════════════════════════

    def show_bubble(self, text: str, duration_ms: int = 4000):
        """显示对话气泡"""
        # 清除旧气泡
        self._clear_bubble()

        # 气泡参数
        bubble_x = 10
        bubble_y = 10
        padding = 12

        # 计算文字大小
        font = ("Segoe UI", 10)

        # 先创建临时文字量宽度
        temp_id = self._canvas.create_text(
            0, 0, text=text, font=font,
            width=BUBBLE_MAX_W - 2 * padding,
            anchor="nw",
        )
        bbox = self._canvas.bbox(temp_id)
        self._canvas.delete(temp_id)

        if bbox:
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            text_w, text_h = 100, 20

        # 气泡圆角矩形
        bw = text_w + 2 * padding
        bh = text_h + 2 * padding
        x1, y1 = bubble_x, bubble_y
        x2, y2 = bubble_x + bw, bubble_y + bh
        r = 12

        # 绘制圆角矩形
        self._bubble_id = self._canvas.create_polygon(
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            # 小三角指向悟空
            x2 - 20, y2,
            x2 - 10, y2 + 10,
            x2 - 30, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
            x1 + r, y1,
            fill="white",
            outline="#d1d5db",
            width=1,
            smooth=True,
        )

        # 绘制文字
        self._bubble_text_id = self._canvas.create_text(
            x1 + padding, y1 + padding,
            text=text,
            font=font,
            fill="#1f2937",
            width=BUBBLE_MAX_W - 2 * padding,
            anchor="nw",
        )

        # 定时消失
        if self._bubble_timer:
            self._root.after_cancel(self._bubble_timer)
        self._bubble_timer = self._root.after(duration_ms, self._clear_bubble)

    def _clear_bubble(self):
        """清除气泡"""
        if self._bubble_id:
            self._canvas.delete(self._bubble_id)
            self._bubble_id = None
        if self._bubble_text_id:
            self._canvas.delete(self._bubble_text_id)
            self._bubble_text_id = None

    # ═══════════════════════════════════════════
    #  呼吸动画
    # ═══════════════════════════════════════════

    def _animate_breath(self):
        """呼吸浮动动画：精灵上下缓慢浮动"""
        self._breath_phase += 0.08
        offset_y = math.sin(self._breath_phase) * 3  # 3px 幅度

        # 移动精灵
        self._canvas.coords(
            self._sprite_item,
            self._sprite_x, self._sprite_y + offset_y,
        )

        # 每 50ms 刷新
        self._root.after(50, self._animate_breath)

    # ═══════════════════════════════════════════
    #  主循环
    # ═══════════════════════════════════════════

    def run(self):
        """启动悟空桌面宠物主循环"""
        self._root.mainloop()

    def get_root(self) -> tk.Tk:
        """获取 tkinter root（供外部集成）"""
        return self._root


# ═══════════════════════════════════════════════
#  独立运行入口
# ═══════════════════════════════════════════════

def run_mascot():
    """启动悟空桌面宠物"""
    mascot = WukongMascot()
    mascot.run()


if __name__ == "__main__":
    run_mascot()
