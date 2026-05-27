# -*- coding: utf-8 -*-
"""
experience_memory.py — 海马体经验记忆系统

仿照大脑海马体设计，实现督导决策的经验存储与检索:

  记忆编码 (Encoding):  每次决策后，记录 (状态, 动作, 结果, 奖励) 四元组
  记忆提取 (Retrieval): 给定当前状态，检索最相似的历史经验
  记忆固化 (Consolidation): 高频成功模式沉淀为规则（Phase 4 HabitNet 消费）

存储格式: JSONL (每行一条 Episode)，人类可读，增量追加

设计原则:
  1. 零依赖——不需要向量数据库，用状态指纹做精确/模糊匹配
  2. 写入即持久——崩溃不丢数据
  3. 内存可控——仅缓存最近 N 条，全量在磁盘
"""

from __future__ import annotations

import json
import os
import time
import hashlib
import dataclasses
from typing import Optional
from collections import defaultdict

from openwukong.core.logger import get_logger, log_event

logger = get_logger("experience_memory")


# ═══════════════════════════════════════════════
#  Episode — 单次决策经历
# ═══════════════════════════════════════════════

@dataclasses.dataclass
class Episode:
    """
    单次决策经历——海马体的最小记忆单元

    类比: 大脑中一次「情境→行为→结果」的因果记忆
    """
    # ── 识别 ──
    episode_id: str             # 唯一ID
    timestamp: float            # 记录时间

    # ── 状态 ──
    state_fingerprint: str      # Percept 的指纹 (e.g. "r1|i0|e0|fcN|taN|u0|ce0")
    goal_name: str              # 任务名称
    goal_status: str            # 任务当前状态
    retry_count: int            # 当前重试计数

    # ── 决策 ──
    action_taken: str           # 采取的动作 (wait/steer/check/abort)
    action_detail: str          # 动作详情 (e.g. steer内容概要)
    decision_layer: str         # 哪一层做的决策 (brainstem/limbic/cortex)

    # ── 结果 ──
    outcome: str                # 结果 (success/fail/pending/error)
    reward: float               # 奖励信号 (-1.0 ~ 1.0)

    # ── 上下文 ──
    context: dict               # 额外上下文 (紧急度、错误类型等)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Episode:
        return cls(**{k: v for k, v in data.items()
                      if k in {f.name for f in dataclasses.fields(cls)}})

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ═══════════════════════════════════════════════
#  ExperienceMemory — 海马体
# ═══════════════════════════════════════════════

class ExperienceMemory:
    """
    海马体经验记忆系统

    核心功能:
      record()       — 记忆编码：记录一次决策经历
      recall()       — 记忆提取：检索相似的历史经验
      consolidate()  — 记忆固化：提炼高频成功模式 (Phase 4)
      get_stats()    — 统计概览

    使用:
        memory = ExperienceMemory("logs/experience_memory.jsonl")

        # 记录
        memory.record(
            state_fingerprint="r1|i0|e0|fcN|taN|u0|ce0",
            goal_name="安全攻防测试",
            goal_status="running",
            retry_count=2,
            action_taken="steer",
            action_detail="继续执行V3攻击向量...",
            decision_layer="brainstem",
            outcome="success",
            reward=0.5,
            context={"urgency": 0.3},
        )

        # 检索
        similar = memory.recall("r1|i0|e0|fcN|taN|u0|ce0", top_k=5)
        for ep in similar:
            print(ep.action_taken, ep.reward)
    """

    # 内存缓存上限
    MAX_MEMORY_CACHE = 500

    def __init__(self, memory_path: str = "logs/experience_memory.jsonl"):
        self._path = memory_path
        self._cache: list[Episode] = []
        self._total_recorded = 0

        # 确保存储目录存在
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)

        # 加载已有记录
        self._load_existing()

    def _load_existing(self):
        """启动时加载已有的经验记录"""
        if not os.path.exists(self._path):
            return

        try:
            loaded = 0
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ep = Episode.from_dict(data)
                        self._cache.append(ep)
                        loaded += 1
                    except (json.JSONDecodeError, TypeError):
                        continue

            # 仅保留最近的 N 条在内存中
            if len(self._cache) > self.MAX_MEMORY_CACHE:
                self._cache = self._cache[-self.MAX_MEMORY_CACHE:]

            self._total_recorded = loaded
            if loaded > 0:
                log_event(
                    logger,
                    f"海马体加载: {loaded} 条经验, 内存缓存 {len(self._cache)} 条",
                    event_type="memory_loaded",
                )
        except Exception as e:
            log_event(
                logger,
                f"海马体加载失败: {e}",
                event_type="memory_load_error",
                level=30,
            )

    def record(
        self,
        state_fingerprint: str,
        goal_name: str,
        goal_status: str,
        retry_count: int,
        action_taken: str,
        action_detail: str = "",
        decision_layer: str = "brainstem",
        outcome: str = "pending",
        reward: float = 0.0,
        context: Optional[dict] = None,
    ) -> Episode:
        """
        记忆编码：记录一次决策经历

        Args:
            state_fingerprint: Percept 的状态指纹
            goal_name: 任务名称
            goal_status: 任务当前GoalStatus
            retry_count: 当前重试次数
            action_taken: 采取的动作
            action_detail: 动作详情
            decision_layer: 决策层 (brainstem/limbic/cortex)
            outcome: 结果
            reward: 奖励信号 (-1.0 ~ 1.0)
            context: 额外上下文

        Returns: 创建的 Episode
        """
        # 生成唯一ID
        raw = f"{time.time()}{state_fingerprint}{action_taken}"
        episode_id = hashlib.md5(raw.encode()).hexdigest()[:12]

        episode = Episode(
            episode_id=episode_id,
            timestamp=time.time(),
            state_fingerprint=state_fingerprint,
            goal_name=goal_name,
            goal_status=goal_status,
            retry_count=retry_count,
            action_taken=action_taken,
            action_detail=action_detail[:200],  # 截断防止过长
            decision_layer=decision_layer,
            outcome=outcome,
            reward=reward,
            context=context or {},
        )

        # 追加到磁盘
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(episode.to_json_line() + "\n")
        except Exception as e:
            log_event(
                logger,
                f"海马体写入失败: {e}",
                event_type="memory_write_error",
                level=30,
            )

        # 追加到内存缓存
        self._cache.append(episode)
        if len(self._cache) > self.MAX_MEMORY_CACHE:
            self._cache = self._cache[-self.MAX_MEMORY_CACHE:]

        self._total_recorded += 1
        return episode

    def recall(
        self,
        state_fingerprint: str,
        top_k: int = 5,
        goal_name: Optional[str] = None,
    ) -> list[Episode]:
        """
        记忆提取：检索与当前状态最相似的历史经验

        匹配策略（分级）:
          1. 精确匹配: fingerprint 完全相同
          2. 模糊匹配: fingerprint 各字段的编辑距离
          3. 目标匹配: 同一个 goal_name 的历史经验

        Args:
            state_fingerprint: 当前状态指纹
            top_k: 返回最相似的 K 条
            goal_name: 可选，限定同一任务的经验

        Returns: 相似度从高到低排序的 Episode 列表
        """
        if not self._cache:
            return []

        candidates = self._cache
        if goal_name:
            candidates = [ep for ep in candidates if ep.goal_name == goal_name]

        # 对每个候选计算相似度
        scored = []
        for ep in candidates:
            sim = self._fingerprint_similarity(state_fingerprint, ep.state_fingerprint)
            scored.append((sim, ep))

        # 按相似度降序 + 时间降序
        scored.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)

        return [ep for _, ep in scored[:top_k]]

    def _fingerprint_similarity(self, fp_a: str, fp_b: str) -> float:
        """
        状态指纹相似度计算

        将指纹拆分为字段，逐字段比较:
          - 相同 → 1.0
          - 数值差异 → 用高斯核衰减
          - 不同 → 0.0
        """
        parts_a = fp_a.split("|")
        parts_b = fp_b.split("|")

        if not parts_a or not parts_b:
            return 0.0

        # 取较短的长度进行比较
        min_len = min(len(parts_a), len(parts_b))
        if min_len == 0:
            return 0.0

        score = 0.0
        for i in range(min_len):
            a, b = parts_a[i], parts_b[i]
            if a == b:
                score += 1.0
            else:
                # 尝试提取数值部分
                try:
                    prefix_a = a.rstrip("0123456789")
                    prefix_b = b.rstrip("0123456789")
                    if prefix_a == prefix_b:
                        num_a = int(a[len(prefix_a):])
                        num_b = int(b[len(prefix_b):])
                        # 高斯核：差异越大越不相似
                        diff = abs(num_a - num_b)
                        score += max(0.0, 1.0 - diff * 0.3)
                except (ValueError, IndexError):
                    pass  # 不同类型，得分为 0

        return round(score / min_len, 3)

    def update_outcome(self, episode_id: str, outcome: str, reward: float):
        """
        延迟更新经验结果

        有些结果需要过一段时间才能确定（例如 steer 后需要等 Agent 跑完）
        """
        for ep in reversed(self._cache):
            if ep.episode_id == episode_id:
                ep.outcome = outcome
                ep.reward = reward
                log_event(
                    logger,
                    f"经验更新: {episode_id} → {outcome} (reward={reward})",
                    event_type="memory_updated",
                )
                return True
        return False

    def get_stats(self) -> dict:
        """统计概览"""
        if not self._cache:
            return {
                "total_recorded": self._total_recorded,
                "in_memory": 0,
                "outcomes": {},
                "layers": {},
                "avg_reward": 0.0,
            }

        outcome_counts: dict[str, int] = defaultdict(int)
        layer_counts: dict[str, int] = defaultdict(int)
        total_reward = 0.0

        for ep in self._cache:
            outcome_counts[ep.outcome] += 1
            layer_counts[ep.decision_layer] += 1
            total_reward += ep.reward

        return {
            "total_recorded": self._total_recorded,
            "in_memory": len(self._cache),
            "outcomes": dict(outcome_counts),
            "layers": dict(layer_counts),
            "avg_reward": round(total_reward / len(self._cache), 3),
        }

    def consolidate(self) -> dict[str, str]:
        """
        记忆固化：提炼高频成功模式

        将 (state_fingerprint → action) 中成功率最高的映射
        提取出来，供 HabitNet (Phase 4) 使用

        Returns: {state_fingerprint: best_action} 规则字典
        """
        if not self._cache:
            return {}

        # 按 (fingerprint, action) 统计成功率
        stats: dict[tuple[str, str], list[float]] = defaultdict(list)
        for ep in self._cache:
            key = (ep.state_fingerprint, ep.action_taken)
            stats[key].append(ep.reward)

        # 按 fingerprint 分组，找每个状态的最佳动作
        best_rules: dict[str, str] = {}
        fingerprints: dict[str, list[tuple[str, float, int]]] = defaultdict(list)

        for (fp, action), rewards in stats.items():
            avg_reward = sum(rewards) / len(rewards)
            count = len(rewards)
            fingerprints[fp].append((action, avg_reward, count))

        for fp, actions in fingerprints.items():
            # 选择：成功率最高且样本量 >= 3 的动作
            qualified = [(a, r, c) for a, r, c in actions if c >= 3]
            if qualified:
                best = max(qualified, key=lambda x: x[1])
                if best[1] > 0.3:  # 只固化平均奖励 > 0.3 的规则
                    best_rules[fp] = best[0]

        if best_rules:
            log_event(
                logger,
                f"记忆固化: {len(best_rules)} 条规则提炼完成",
                event_type="memory_consolidated",
                event_data={"rule_count": len(best_rules)},
            )

        return best_rules

    def get_recent_trajectory(
        self,
        goal_name: str,
        last_n: int = 10,
    ) -> list[Episode]:
        """
        获取特定任务的最近 N 步轨迹

        用于 LLM 分析任务进展趋势
        """
        episodes = [
            ep for ep in self._cache
            if ep.goal_name == goal_name
        ]
        return episodes[-last_n:]
