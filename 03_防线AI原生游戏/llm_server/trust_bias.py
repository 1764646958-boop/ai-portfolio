# -*- coding: utf-8 -*-
"""
《防线》 · W2/llm/trust_bias.py
信任偏移值累积器 v0.1（隐藏数值，不对玩家展示）

设计依据（团队选题报告 §4.3）：
- 范围：-10（完全偏向人类）~ +10（完全偏向 AI），起点 0
- 输入：记忆分析引擎输出 {drift_direction, magnitude, confidence}
- 规则：ai → 正向累积；human → 负向累积；按 magnitude × confidence 加权，clamp 到 [-10, +10]

B 侧对接：信任偏移行为触发规则表（战斗压迫参数/记忆考古难度）读取 value 即可；
规则表本身由 B 设计，本类只提供累积 API。
"""


class TrustBias:
    """信任偏移值累积器。"""

    def __init__(self, start=0.0, lo=-10.0, hi=10.0):
        """
        Args:
            start: 初始偏移值（默认 0）
            lo/hi: 偏移范围（默认 -10 ~ +10）
        """
        self.lo = lo
        self.hi = hi
        self._value = self._clamp(start)

    # -- 内部工具 --------------------------------------------------------

    def _clamp(self, v):
        return max(self.lo, min(self.hi, v))

    # -- 主 API ----------------------------------------------------------

    def update(self, drift_direction, magnitude, confidence):
        """按一次记忆分析结果更新偏移值。

        Args:
            drift_direction: "ai" 或 "human"
            magnitude: 0~10 的漂移强度
            confidence: 0~1 的判定置信度

        Returns:
            float: 更新后的偏移值（已 clamp）
        """
        if drift_direction not in ("ai", "human"):
            raise ValueError(f"drift_direction 必须是 'ai' 或 'human'，收到：{drift_direction!r}")

        delta = float(magnitude) * float(confidence)
        if drift_direction == "human":
            delta = -delta

        self._value = self._clamp(self._value + delta)
        return self._value

    def reset(self, start=0.0):
        """重置偏移值（新游戏/新玩家时调用）。"""
        self._value = self._clamp(start)

    # -- 只读属性 --------------------------------------------------------

    @property
    def value(self):
        """当前偏移值（只读，隐藏数值）。"""
        return self._value

    @property
    def tendency(self):
        """倾向标签：'ai' / 'human' / 'neutral'（供日志/调试用，不展示给玩家）。"""
        if self._value > 0.5:
            return "ai"
        if self._value < -0.5:
            return "human"
        return "neutral"

    def __repr__(self):
        return f"<TrustBias value={self._value:.2f} tendency={self.tendency}>"
