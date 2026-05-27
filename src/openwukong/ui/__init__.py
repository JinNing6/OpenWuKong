# -*- coding: utf-8 -*-
"""ui — OpenWukong 控制面板 UI"""

# Dashboard 模块可能尚未创建（由另一对话实现）
try:
    from openwukong.ui.dashboard import WukongApp
except ImportError:
    WukongApp = None

# 悟空桌面宠物
try:
    from openwukong.ui.wukong_mascot import WukongMascot
except ImportError:
    WukongMascot = None

__all__ = ["WukongApp", "WukongMascot"]
