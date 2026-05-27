# -*- coding: utf-8 -*-
"""
constants.py - 项目全局常量映射

集中管理项目别名、默认关键词等，用于自然语言解析与窗口匹配。
"""

# 项目中文名到英文标识符（通常是窗口标题的一部分）的映射
PROJECT_ALIASES = {
    "悟空": "openwukong",
    "西游": "openwukong",
    "悟空项目": "openwukong",
    "openwukong": "openwukong",

    "霜落": "frostfall",
    "frostfall": "frostfall",

    "提莫": "timo",
    "timo": "timo",

    "雷达": "radar",
    "radar": "radar",

    "安全": "safety",
    "safety": "safety",

    "雇得": "goood",
    "goood": "goood",

    "绿洲": "oasis",
    "oasis": "oasis",

    "图谱": "atlas",
    "atlas": "atlas",

    "dow": "isdow",
    "isdow": "isdow"
}

# 反向别名映射：标识符 → 所有可能的别名列表
# 用于窗口匹配时的多关键词展开
def _build_reverse_aliases() -> dict:
    """从 PROJECT_ALIASES 构建反向映射"""
    reverse = {}
    for alias, target in PROJECT_ALIASES.items():
        if target not in reverse:
            reverse[target] = set()
        reverse[target].add(alias)
        reverse[target].add(target)  # 确保标识符本身也在列表中
    return {k: list(v) for k, v in reverse.items()}

PROJECT_ALIAS_REVERSE = _build_reverse_aliases()

# 默认成功关键词
DEFAULT_SUCCESS_KEYWORDS = ["done", "passed", "完成", "成功", "通过"]

# 默认失败关键词
DEFAULT_FAILURE_KEYWORDS = ["Error", "failed", "失败"]
