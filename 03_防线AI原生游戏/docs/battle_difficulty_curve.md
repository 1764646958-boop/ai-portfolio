# 战斗难度曲线对照表

> B 给 A 的 QTE 难度设计参考。trust_drift tier（LOW/MEDIUM/HIGH）× 3 场战斗 × 4 个 QTE 参数。
> A 据此实现 qte_params.json 实际数值（C 维护）+ Shader/音频压迫调校。

## 4 个 QTE 参数

| 参数 | 含义 | 取值范围 |
|---|---|---|
| `reaction_window` | 玩家反应时间窗（秒） | 1.0 ~ 8.0 |
| `success_threshold` | 成功判定阈值（0-1，玩家操作准确率） | 0.3 ~ 0.9 |
| `hint_delay` | 提示出现延迟（秒，0 = 无提示） | 0.0 ~ 5.0 |
| `penalty_intensity` | 失败惩罚强度（0-1，影响视觉/音频反馈） | 0.2 ~ 1.0 |

> `config/qte_params.json` 当前 owner: C（mode1_card window 8.0 / mode2_drag truth 0.10 vs fake 0.55 / mode3_qte window 4.0 + anim 参数）—— 本表给的是叙事意图参考值，最终数值由 C+A 决定。

---

## 第 1 战 · 犹豫期（场景 2 教室后，trust 进入"偏向不信任"）

| tier | reaction_window | success_threshold | hint_delay | penalty_intensity |
|---|---|---|---|---|
| LOW_TRUST | 8.0 | 0.50 | 0.0 | 0.30 |
| MEDIUM_TRUST | 7.0 | 0.55 | 0.0 | 0.35 |
| HIGH_TRUST | 6.0 | 0.60 | 1.0 | 0.40 |

**设计意图**：
- 玩家刚失去旧友，给宽时间窗让玩家熟悉 QTE；
- LOW_TRUST 时 hint 即时出现，AI 完全透明；
- HIGH_TRUST 时 hint 提前 1s 出现（AI "主动帮忙"），但降低通过率要求（玩家被 AI 接手的感觉）。

---

## 第 2 战 · 拉锯期（场景 4 街道后，trust 进入"中性"）

| tier | reaction_window | success_threshold | hint_delay | penalty_intensity |
|---|---|---|---|---|
| LOW_TRUST | 6.0 | 0.60 | 0.0 | 0.50 |
| MEDIUM_TRUST | 5.0 | 0.65 | 2.0 | 0.60 |
| HIGH_TRUST | 4.0 | 0.70 | 3.0 | 0.70 |

**设计意图**：
- 旧友频繁出现，玩家分心 → 时间窗缩短；
- AI 与旧友博弈开始，hint 延迟到达（信息差压迫）；
- HIGH_TRUST 时 hint 延迟 3s，玩家更依赖 AI 来"预判"。

---

## 第 3 战 · 终局（场景 5 公寓，trust 进入"极度信任"）

| tier | reaction_window | success_threshold | hint_delay | penalty_intensity |
|---|---|---|---|---|
| LOW_TRUST | 4.0 | 0.70 | 2.0 | 0.80 |
| MEDIUM_TRUST | 3.0 | 0.75 | 4.0 | 0.90 |
| HIGH_TRUST | 2.5 | 0.80 | 5.0 | 1.00 |

**设计意图**：
- 即便不信任 AI，终局压迫仍强（HIGH_TRUST 时间窗 2.5s 是全局最短）；
- MEDIUM_TRUST 时 hint 几乎来不及看（"AI 替你做决定"压迫）；
- HIGH_TRUST 时 AI 完全接管——通关不再是挑战，改为"AI 接管"叙事动画。

---

## 难度曲线图（reaction_window × tier）

```
reaction_window（秒）
8.0 ┤ ●─ 第 1 战 LOW_TRUST
7.0 ┤   ●─ 第 1 战 MEDIUM
6.0 ┤     ●─ 第 1 战 HIGH_TRUST
6.0 ┤       ●─ 第 2 战 LOW_TRUST
5.0 ┤         ●─ 第 2 战 MEDIUM
4.0 ┤           ●─ 第 2 战 HIGH_TRUST  ●─ 第 3 战 LOW_TRUST
3.0 ┤                                    ●─ 第 3 战 MEDIUM_TRUST
2.5 ┤                                      ●─ 第 3 战 HIGH_TRUST
     └────────────────────────────────────→
      第 1 战        第 2 战        第 3 战
      (犹豫期)      (拉锯期)      (终局)
```

> **关键设计意图**：trust 升高时 reaction_window 缩短——玩家越信任 AI，AI 越"着急"替玩家做决定。这是叙事核心机制（信任反噬）的反向呈现。

---

## tier ↔ 区间 对照（基于 trust_drift_rules 的 v0.1 tier + v0.2 5 区间）

| v0.1 tier | 对应 v0.2 区间 | drift 数值 | 第几战倾向 |
|---|---|---|---|
| LOW_TRUST | 极度不信任 + 偏向不信任 | -10 ~ -3 | 第 1 战 |
| MEDIUM_TRUST | 中性 | -2 ~ +2 | 第 2 战 |
| HIGH_TRUST | 偏向信任 + 极度信任 | +3 ~ +10 | 第 3 战 |

> tier 判定函数（`TrustDrift.get_trust_tier()`）不动；区间是更细的拆分。本表给 A/C 按 tier 取数参考。

---

## A 实现清单

| 项 | 涉及文件 | 备注 |
|---|---|---|
| qte_params.json 数值填充 | `config/qte_params.json` | C 维护 owner，B 给参考值 |
| Shader 反应窗视觉提示 | `scripts/archaeology_ui.gd` + Shader | 时间窗可视化（圆形进度条 / 抖动） |
| 音频压迫响应 | `scripts/battle_audio.gd`（A 实现） | penalty_intensity → 失真强度 |
| 终局接管特效 | Shader + UI | HIGH_TRUST 第 3 战通关改为"AI 接管"叙事动画 |

## B 工时投入参考

写本表 ~2h；后续 Beta 试玩根据实际压迫感受调参 ~1h。

---

## 关联文档

- 信任偏移规则：`config/trust_drift_rules_v0.1.md`
- 叙事节奏表：`docs/battle_narrative_rhythm.md`
- QTE 参数文件：`config/qte_params.json`