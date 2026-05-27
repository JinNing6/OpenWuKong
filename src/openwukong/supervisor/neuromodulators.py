# -*- coding: utf-8 -*-
"""
neuromodulators.py — 神经递质全局调节系统

仿照大脑神经递质机制，不改变决策逻辑，而是动态调节决策参数:

  🟡 多巴胺 (Dopamine)       — 奖励驱动力：成功→↑，停滞→↓
  🔴 去甲肾上腺素 (Norepinephrine) — 警觉度：出错→↑，平静→自然衰减
  🔵 血清素 (Serotonin)      — 耐心/稳定性：成功→↑，出错→↓
  🟢 GABA                    — 抑制/克制：防止过度干预

实际效果:
  多巴胺高 + GABA低 → 更积极 steer（适合快节奏任务）
  血清素高 → 更长的 stall_timeout（更耐心等待）
  去甲肾上腺素高 → 更频繁的扫描（更警觉）
"""

from __future__ import annotations

import time
import dataclasses
from typing import Optional

from openwukong.core.logger import get_logger, log_event

logger = get_logger("neuromodulators")


@dataclasses.dataclass
class NeuroState:
    """神经递质状态快照"""
    dopamine: float
    norepinephrine: float
    serotonin: float
    gaba: float
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "dopamine": round(self.dopamine, 3),
            "norepinephrine": round(self.norepinephrine, 3),
            "serotonin": round(self.serotonin, 3),
            "gaba": round(self.gaba, 3),
        }


class Neuromodulators:
    """
    神经递质全局调节器

    使用:
        neuro = Neuromodulators()

        # 事件驱动更新
        neuro.on_goal_achieved()      # 任务成功
        neuro.on_error()              # 出错
        neuro.on_stall()              # 停滞
        neuro.on_steer_sent()         # 发送了steer

        # 读取调节后的参数
        cooldown = neuro.effective_cooldown(base=10.0)
        timeout = neuro.effective_stall_timeout(base=600.0)
        interval = neuro.effective_scan_interval(base=5.0)
    """

    # ── 衰减率（每次 tick 自然恢复的量）──
    DECAY_RATE = 0.02  # 所有递质缓慢回归基线

    # ── 基线值 ──
    BASELINE = {
        "dopamine": 0.5,
        "norepinephrine": 0.3,
        "serotonin": 0.7,
        "gaba": 0.5,
    }

    def __init__(self):
        self.dopamine = self.BASELINE["dopamine"]
        self.norepinephrine = self.BASELINE["norepinephrine"]
        self.serotonin = self.BASELINE["serotonin"]
        self.gaba = self.BASELINE["gaba"]
        self._last_update = time.time()
        self._event_count = 0

    # ═══════════════════════════════════════════════
    #  事件驱动更新
    # ═══════════════════════════════════════════════

    def on_goal_achieved(self):
        """任务成功 — 多巴胺释放，血清素提升，去甲肾下降"""
        self.dopamine = min(1.0, self.dopamine + 0.2)
        self.serotonin = min(1.0, self.serotonin + 0.1)
        self.norepinephrine = max(0.0, self.norepinephrine - 0.1)
        self.gaba = min(1.0, self.gaba + 0.1)  # 成功后更克制
        self._log_event("goal_achieved")

    def on_error(self):
        """出错 — 去甲肾释放（警觉），血清素下降（急躁）"""
        self.norepinephrine = min(1.0, self.norepinephrine + 0.15)
        self.serotonin = max(0.0, self.serotonin - 0.1)
        self.gaba = max(0.0, self.gaba - 0.05)  # 出错后更激进
        self._log_event("error")

    def on_stall(self):
        """停滞 — 多巴胺下降（动力减退），GABA下降（更冲动）"""
        self.dopamine = max(0.0, self.dopamine - 0.1)
        self.gaba = max(0.0, self.gaba - 0.1)
        self._log_event("stall")

    def on_steer_sent(self):
        """发送了steer — 多巴胺微量释放（行动感），GABA微量恢复"""
        self.dopamine = min(1.0, self.dopamine + 0.05)
        self.gaba = min(1.0, self.gaba + 0.03)
        self._log_event("steer_sent")

    def on_agent_running(self):
        """Agent正在运行 — 血清素缓慢恢复（耐心等待）"""
        self.serotonin = min(1.0, self.serotonin + 0.02)
        # 不记录日志避免刷屏

    def tick(self):
        """每个主循环 tick 调用一次，执行自然衰减"""
        # 所有递质向基线缓慢回归
        for attr, baseline in self.BASELINE.items():
            current = getattr(self, attr)
            if current > baseline:
                setattr(self, attr, max(baseline, current - self.DECAY_RATE))
            elif current < baseline:
                setattr(self, attr, min(baseline, current + self.DECAY_RATE))

    # ═══════════════════════════════════════════════
    #  派生效果：调节督导参数
    # ═══════════════════════════════════════════════

    @property
    def steer_eagerness(self) -> float:
        """
        steer倾向 (0-1)

        多巴胺高（有动力）+ GABA低（不克制）→ 更积极 steer
        """
        return round(self.dopamine * (1.0 - self.gaba), 3)

    @property
    def patience(self) -> float:
        """
        耐心度 (0-1)

        血清素高 → 更愿意等待
        """
        return round(self.serotonin, 3)

    @property
    def alertness(self) -> float:
        """
        警觉度 (0-1)

        去甲肾上腺素高 → 扫描更频繁
        """
        return round(self.norepinephrine, 3)

    def effective_cooldown(self, base: float = 10.0) -> float:
        """
        根据神经递质调节 steer 冷却时间

        高steer_eagerness → 更短的冷却 (最低 base * 0.3)
        低steer_eagerness → 更长的冷却 (最高 base * 2.0)
        """
        # 倾向 0.0→2.0x，0.5→1.0x，1.0→0.3x
        multiplier = 2.0 - 1.7 * self.steer_eagerness
        return round(base * max(0.3, min(2.0, multiplier)), 1)

    def effective_stall_timeout(self, base: float = 600.0) -> float:
        """
        根据耐心度调节 stall 超时

        高耐心 → 更长的超时 (最高 base * 1.5)
        低耐心 → 更短的超时 (最低 base * 0.3)
        """
        multiplier = 0.3 + 1.2 * self.patience
        return round(base * max(0.3, min(1.5, multiplier)), 0)

    def effective_scan_interval(self, base: float = 5.0) -> float:
        """
        根据警觉度调节扫描间隔

        高警觉 → 更频繁扫描 (最快 base * 0.4)
        低警觉 → 更慢的扫描 (最慢 base * 1.5)
        """
        multiplier = 1.5 - 1.1 * self.alertness
        return round(base * max(0.4, min(1.5, multiplier)), 1)

    # ═══════════════════════════════════════════════
    #  状态输出
    # ═══════════════════════════════════════════════

    def get_state(self) -> NeuroState:
        return NeuroState(
            dopamine=self.dopamine,
            norepinephrine=self.norepinephrine,
            serotonin=self.serotonin,
            gaba=self.gaba,
            timestamp=time.time(),
        )

    def get_dashboard_line(self) -> str:
        """仪表盘显示行"""
        return (
            f"🧬 DA:{self.dopamine:.2f} NE:{self.norepinephrine:.2f} "
            f"5HT:{self.serotonin:.2f} GABA:{self.gaba:.2f} | "
            f"eagerness:{self.steer_eagerness:.2f} "
            f"patience:{self.patience:.2f} "
            f"alertness:{self.alertness:.2f}"
        )

    def _log_event(self, event_name: str):
        self._event_count += 1
        # 每5次事件记录一次日志
        if self._event_count % 5 == 1:
            log_event(
                logger,
                f"神经递质更新 ({event_name}): "
                f"DA={self.dopamine:.2f} NE={self.norepinephrine:.2f} "
                f"5HT={self.serotonin:.2f} GABA={self.gaba:.2f}",
                event_type="neuro_update",
            )
