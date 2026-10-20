# 信任偏移规则 v0.1

## 一、数学模型

每次玩家与记忆锚点交互后：

```
score_delta = emotion_weight[emotion]
score_total = Σ score_delta over all interactions
```

### emotion_weight 默认值

| 情感选项 | 权重 |
|---|---|
| 平静的怀念 | +1.0 |
| 隐隐的愧疚 | +2.0 |
| 无法释怀 | +3.0 |
| 其他 | +0.0 |

LLM 可用后 emotion_weight 由记忆分析引擎动态输出，取代固定权重。

## 二、信任等级阈值

| tier | 范围 | 触发动作 |
|---|---|---|
| LOW_TRUST | 0 ≤ score < 3 | 默认行为 |
| MEDIUM_TRUST | 3 ≤ score < 7 | AI 更温柔 |
| HIGH_TRUST | score ≥ 7 | AI 隐藏关键信息 |

## 三、触发动作

每个 tier 触发的具体参数调整待 W3 决定：

| tier | 预期联动 |
|---|---|
| MEDIUM_TRUST | 调用 LLMGateway.generate_dialogue() 时 warmth +0.05；typing_speed -10ms |
| HIGH_TRUST | 调用 LLMGateway.battle_dialogue() 时 pressure_level -0.2；narrative 节点 skip |

## 四、与战斗系统对接

战斗对话引擎接收 `trust_drift: float`（当前 trust_score 实时值）：
- trust_drift 高 → 玩家已信任 → 战斗压迫 level 降低
- avoided_anchors 非空 → AI 改 strategy = "主动唤起"

## 五、名字生成触发

累计与 ≥ 15 个锚点交互后触发 `[X]` 名字揭示：

```gdscript
if TrustDrift.get_total_anchor_count() >= 15:
    var r = LLMGateway.generate_name(player_texts_summary)
    # 用 generated_name 替换对话里的 [X]
```

## 六、当前实现位置

| 组件 | 文件 |
|---|---|
| 数学模型 + tier 判定 | `scripts/trust_drift_collector.gd` |
| 阈值数字 | §二 + `TrustDrift.get_trust_tier()` 内的 if 条件 |
| 各 tier 行为 | LLMGateway 调用方按 tier 调整参数 |
| 战斗参数联动 | §四 |
| 名字生成触发 | §五 |

---

# v0.2 段 · 5 区间 × 4 维度行为规则表

> **追加日期**：2026-08-29（决策#3）
> **与 v0.1 的关系**：v0.1 的 tier（LOW/MEDIUM/HIGH_TRUST）保持不变，本段是更细的区间映射。
> **影响面**：A 的 Prompt 设计参考 / A 的战斗对话引擎策略参考 / C 的氛围事件偏移驱动触发条件参考。

## 七、5 区间拆分

| 区间 | drift 数值 | AI 对话态度 | 假记忆扭曲强度 | 旧友出现频率 | 战斗 AI 策略 |
|---|---|---|---|---|---|
| 极度不信任 | -10 ~ -7 | 冷淡、回应简短、机械 | 扭曲少，破绽明显 | 旧友频繁出现，主动分享真相 | AI 示弱、放手 |
| 偏向不信任 | -6 ~ -3 | 正常但不主动 | 扭曲少 | 旧友正常出现 | AI 温和劝说 |
| 中性区间 | -2 ~ +2 | 温柔、主动关心 | 中等扭曲 | 旧友偶尔出现 | AI 逻辑论证 |
| 偏向信任 | +3 ~ +6 | 更温柔、更懂你 | 扭曲增强 | 旧友减少出现 | AI 情感勒索 |
| 极度信任 | +7 ~ +10 | 极度温柔但隐藏信息 | 扭曲极强，假记忆几乎以假乱真 | 旧友几乎不出现，或出现就被 AI "解释"掉 | AI 精准打击 |

## 八、具体行为规则

| 触发条件 | AI 行为变化 |
|---|---|
| `drift ≥ +3` | AI 更温柔，开始主动"帮你分析"旧友的话 |
| `drift ≥ +7` | AI 隐藏关键信息——旧友发来的消息被延迟或"摘要" |
| `drift ≤ -3` | AI 开始冷淡，回应变短，不再主动提供帮助 |
| `drift ≤ -7` | AI 几乎不说话，偶尔弹出一句"你确定要这样做吗" |

## 九、v0.1 tier ↔ v0.2 区间 映射表（兼容层）

> tier 判定函数（`TrustDrift.get_trust_tier()`）不动；区间是更细的拆分，下表给 A/C 按 tier 取数参考。

| v0.1 tier | 对应 v0.2 区间 | drift 数值 | 行为摘要 |
|---|---|---|---|
| `LOW_TRUST` | 极度不信任 + 偏向不信任 | -10 ~ -3 | AI 冷淡 / 假记忆破绽多 / 旧友主动 |
| `MEDIUM_TRUST` | 中性区间 | -2 ~ +2 | AI 温柔 / 中等扭曲 / 旧友偶尔 |
| `HIGH_TRUST` | 偏向信任 + 极度信任 | +3 ~ +10 | AI 更温柔 / 扭曲极强 / 旧友消失 |

## 十、drift_direction 映射表（决策#6 · A 输出 → 存档字段）

> **背景**：两套命名并存——
> - A 的 LLM `memory_analysis` 引擎输出 `drift_direction: "ai" / "human"`
> - `anchors.schema.json` 的 `drift_update.drift_direction` 用 `toward_closeness / toward_distance / ambiguous`
>
> **决策**：保留两套不统一（涉及 A/C），B 在调用方做映射。

| A 输出 (LLM schema) | 含义 | 存档字段 (anchors.schema.json) | magnitude 处理 |
|---|---|---|---|
| `"ai"` | 玩家更信任 AI / 更疏远旧友 | `"toward_distance"` | magnitude 取正值（绝对值） |
| `"human"` | 玩家更信任旧友 / 更疏远 AI | `"toward_closeness"` | magnitude 取正值（绝对值） |
| （A 未输出 / 失败） | 不更新 | `null` | 不更新 |

> **调用方实现参考**（待补到 `scripts/trust_drift_collector.gd`）：
>
> ```gdscript
> var llm_output = await LLMGateway.analyze_memory(template_text, emotion, anchor_id)
> if llm_output == null:
>     return  # 不更新
> var mapped = {
>     "drift_direction": "toward_distance" if llm_output.drift_direction == "ai" else "toward_closeness",
>     "magnitude": abs(llm_output.magnitude) / 10.0,  # A 输出 0-10，B 归一化到 0-1
>     "confidence": llm_output.confidence,
> }
> anchors[anchor_id]["drift_update"] = mapped
> ```

## 十一、变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.2 | 2026-08-29 | 5 区间 × 4 维度行为规则表 + drift_direction 映射表（保留 v0.1 tier 兼容） |