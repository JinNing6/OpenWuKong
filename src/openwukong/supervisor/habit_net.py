# -*- coding: utf-8 -*-
"""
habit_net.py — 基底神经节习惯网络 + RL 学习

仿照大脑基底神经节设计：

  学习模式: Q-learning (state, action) → value
  数据来源: ExperienceMemory.consolidate() 固化的规则

类比：
  人骑自行车——一开始需要大脑皮层（LLM）全神贯注参与，
  学会后基底核自动控制，皮层可以同时想别的事。

  同理——督导器第一次遇到某种 Error 需要 LLM 分析，
  多次后 HabitNet 学会了，直接自动处理，不再唤醒 LLM。
"""

from __future__ import annotations

import json
import os
import math
from collections import defaultdict
from typing import Optional

from openwukong.core.logger import get_logger, log_event

logger = get_logger("habit_net")


class HabitNet:
    """
    基底神经节：从经验中学习自动化决策策略

    两层决策:
      1. 规则层: 从 ExperienceMemory.consolidate() 来的确定性映射
      2. Q-table: Q-learning 训练的概率性映射

    使用:
        net = HabitNet()

        # 决策
        action, confidence = net.decide(state_features)

        # 学习
        net.update(state, action, reward, next_state)

        # 导入固化规则
        rules = experience_memory.consolidate()
        net.import_rules(rules)
    """

    # ── 超参数 ──
    ALPHA = 0.1       # 学习率
    GAMMA = 0.9       # 折扣因子
    EPSILON = 0.1     # 探索率（ε-greedy）
    MIN_CONFIDENCE = 0.3  # 最低置信度阈值

    # 可用动作空间
    ACTIONS = ["wait", "steer", "check", "abort"]

    def __init__(self, persist_path: str = "logs/habit_net.json"):
        self._rules: dict[str, str] = {}      # fingerprint → best_action
        self._q_table: dict[str, dict[str, float]] = defaultdict(
            lambda: {a: 0.0 for a in self.ACTIONS}
        )
        self._persist_path = persist_path
        self._decision_count = 0

        self._load()

    def decide(self, state_fingerprint: str) -> tuple[str, float]:
        """
        基于学习到的策略做决策

        Returns: (action, confidence)
            confidence > 0.7 → 可信
            confidence < 0.3 → 不可信，应交给 LLM
        """
        self._decision_count += 1

        # ─── 1. 规则层：精确匹配（最高置信度）───
        if state_fingerprint in self._rules:
            action = self._rules[state_fingerprint]
            return action, 0.9

        # ─── 2. Q-table：概率性决策 ───
        if state_fingerprint in self._q_table:
            q_values = self._q_table[state_fingerprint]
            best_action = max(q_values, key=q_values.get)
            best_value = q_values[best_action]

            # 将 Q-value 映射到置信度
            confidence = self._q_to_confidence(best_value)

            if confidence >= self.MIN_CONFIDENCE:
                return best_action, confidence

        # ─── 3. 模糊匹配：找最相似的已知状态 ───
        best_match = self._fuzzy_lookup(state_fingerprint)
        if best_match:
            return best_match

        # ─── 没学过 → 交给上层 ───
        return "unknown", 0.0

    def update(
        self,
        state: str,
        action: str,
        reward: float,
        next_state: str,
    ):
        """
        Q-learning 更新

        Q(s,a) ← Q(s,a) + α * [r + γ * max(Q(s')) - Q(s,a)]
        """
        if action not in self.ACTIONS:
            return

        current_q = self._q_table[state][action]
        next_max_q = max(self._q_table[next_state].values())

        new_q = current_q + self.ALPHA * (
            reward + self.GAMMA * next_max_q - current_q
        )
        self._q_table[state][action] = round(new_q, 4)

        # 每 20 次更新自动持久化
        if self._decision_count % 20 == 0:
            self._save()

    def import_rules(self, rules: dict[str, str]):
        """
        从 ExperienceMemory.consolidate() 导入固化规则

        这是"海马体→基底核"的记忆转移过程
        """
        new_count = 0
        for fingerprint, action in rules.items():
            if fingerprint not in self._rules:
                new_count += 1
            self._rules[fingerprint] = action

        if new_count > 0:
            log_event(
                logger,
                f"规则导入: {new_count} 条新规则 (总计 {len(self._rules)})",
                event_type="habit_rules_imported",
            )
            self._save()

    def _fuzzy_lookup(self, fingerprint: str) -> Optional[tuple[str, float]]:
        """模糊匹配：找 Q-table 中最相似的状态"""
        if not self._q_table:
            return None

        parts = fingerprint.split("|")
        best_sim = 0.0
        best_action = None

        for known_fp, q_values in self._q_table.items():
            known_parts = known_fp.split("|")
            sim = sum(1 for a, b in zip(parts, known_parts) if a == b)
            sim /= max(len(parts), len(known_parts), 1)

            if sim > best_sim and sim > 0.5:
                best_sim = sim
                best_action_name = max(q_values, key=q_values.get)
                best_value = q_values[best_action_name]
                best_action = (
                    best_action_name,
                    round(self._q_to_confidence(best_value) * sim, 3),
                )

        return best_action

    @staticmethod
    def _q_to_confidence(q_value: float) -> float:
        """将 Q-value 映射到 [0, 1] 置信度（sigmoid）"""
        return round(1.0 / (1.0 + math.exp(-q_value * 2)), 3)

    # ═══════════════════════════════════════════════
    #  持久化
    # ═══════════════════════════════════════════════

    def _save(self):
        """保存到磁盘"""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._persist_path)),
                        exist_ok=True)
            data = {
                "rules": self._rules,
                "q_table": dict(self._q_table),
            }
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_event(logger, f"HabitNet 保存失败: {e}",
                      event_type="habit_save_error", level=30)

    def _load(self):
        """从磁盘加载"""
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._rules = data.get("rules", {})
            for k, v in data.get("q_table", {}).items():
                self._q_table[k] = v
            if self._rules or self._q_table:
                log_event(
                    logger,
                    f"HabitNet 加载: {len(self._rules)} 规则, "
                    f"{len(self._q_table)} Q-states",
                    event_type="habit_loaded",
                )
        except Exception as e:
            log_event(logger, f"HabitNet 加载失败: {e}",
                      event_type="habit_load_error", level=30)

    def get_stats(self) -> dict:
        return {
            "rules_count": len(self._rules),
            "q_states_count": len(self._q_table),
            "decision_count": self._decision_count,
        }
