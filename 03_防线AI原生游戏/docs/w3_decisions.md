# 《防线》决策记录 · 成员 B

> 本周内对 B 工作产生影响的拍板记录。每条决策带理由与影响面。
> 周中如有新拍板，按顺序追加。

---

## 决策#1 · 2026-08-29 · fake_memory 引擎升级方式

**议题**：A 当前 fake_memory 引擎 schema 只输出 1 个变体（`{variant_text, distortion_note}`），任务② 要求接口输出 3 变体（neg/pos/micro）。

**拍板**：B 在调用方包装 3 次调用，**不等 A 升级**；A 升级后无缝切换。

**理由**：
- 便捷度：B 调用方包 3 次（同一 anchor + emotion 调 3 次，variant_type 不同），今天就能跑通；
- 协作：A 升级调度层是 A 的工作（任务② 共同部分），B 不应阻塞；
- 后续：A 升级后 B 改 1 行调用即可，零破坏。

**影响面**：
- B：`scripts/llm_gateway.gd` 或 `scripts/memory_archaeology.gd` 加 3 次调用包装层
- A：升级 `W2/llm/engines.py` 的 `FAKE_MEMORY_OUTPUT_SCHEMA` 为 `fake_variants[3]`（不在 B 控制范围）

---

## 决策#2 · 2026-08-29 · 氛围事件 id 命名

**议题**：`config/ambient_events.json` 用 `CF_001 / ST_001` 风格；工作指南举例用 `AMB_CF_01`。

**拍板**：沿用现有 `CF_001` / `ST_001` 风格（**不动 id**），文档举例改回。

**理由**：现有 id 已写入 `ambient_events.json` 并在 `_meta.notes` 里被 C 的氛围事件脚本引用。改名要同步改 C 的脚本，工作量大于收益。

**影响面**：
- B：`docs/w3_decisions.md` 记录（本文）
- B：任务⑤ 写新氛围事件时，**沿用 `CF_xxx / CR_xxx / ST_xxx / AP_xxx / X_xxx`** 风格
- C：无需改动

---

## 决策#3 · 2026-08-29 · trust_drift 规则扩展方式

**议题**：`config/trust_drift_rules_v0.1.md` 是 3 tier（LOW/MEDIUM/HIGH）；任务⑥ 要求 5 区间 × 4 维度（AI态度/假记忆强度/旧友频率/战斗策略）。

**拍板**：在 v0.1.md 基础上**追加** v0.2 段（5 区间），保留 v0.1 tier 判定兼容。

**理由**：v0.1 的 tier 判定已被 `scripts/trust_drift_collector.gd` 引用（`get_trust_tier()` if 条件）。**保留 v0.1 不动**，新加 v0.2 段给 工作指南用的 5 区间，二者通过映射表衔接（tier → 区间）。

**影响面**：
- B：`config/trust_drift_rules_v0.1.md` 追加 v0.2 段（不重写）
- B：tasks⑥ 信任偏移规则表交付物按 v0.2 段写
- A / C：引用 tier 时不变，新增的"区间"概念只给 W3 任务交付物

---

## 决策#4 · 2026-08-29 · 场景 4 锚点 object_id 编号

**议题**：工作指南给场景 4 的 10 条编号用 `ST_SHOP_01 / ST_BUS_01 ... / PK_BENCH_01` 等具体名。

**拍板**：**按 工作指南**用具体编号（与 C 的 `object_id_types.gd` SCENE_ABBREV 一致）。

**理由**：
- 便捷度：工作指南已经写好，C 后续给锚点标记时也用同一套；
- 协作：与 C 命名规范完全对齐（CF/CR/ST/PK + 类型 + 序号）。

**影响面**：
- B：任务④ 10 条场景 4 范本（等 C 的 ST_*/PK_* 锚点标记到位后写入 `anchors.json`）
- C：锚点标记沿用同一套 id（已在 `object_id_types.gd` 的 `SCENE_ABBREV` 里给 ST/PK 留好）

---

## 决策#5 · 2026-08-29 · 记忆考古专用范本 object_id 类型

**议题**：3 条记忆考古专用范本（手链 70% / 玫瑰 50% / 针织花 30%），需要新增 MA_ 类型枚举。

**拍板**：B 扩 `object_id_types.gd` enum，加 `MA_BRACELET / MA_ROSE / MA_FLOWER`。

**理由**：
- 整洁：3 条记忆考古专用范本有专门前缀 MA_，与场景锚点（CF/CR/DM/ST/PK）区分；
- 后续协作：C 的 `interactable.gd` 校验直接按 enum 通过，不需要特殊处理。

**影响面**：
- B：`config/object_id_types.gd` 加 MA_ 三个值
- C：autoload 加载顺序保证 enum 已可用即可（无需改代码）

---

## 决策#6 · 2026-08-29 · drift_direction 枚举不一致处理

**议题**：两套命名并存——`trust_drift_rules_v0.1.md` 用 `ai / human`（A 的 LLM 输出）；`anchors.schema.json` 的 `drift_update.drift_direction` 用 `toward_closeness / toward_distance / ambiguous`（存档格式）。

**拍板**：**保留两套**，B 在 `trust_drift_rules_v0.1.md` v0.2 段加映射表（A 输出 → 存档字段）。

**理由**：
- 涉及 A（A 的 LLM schema 已是 ai/human，**不能改 A 的输出**）和 C（C 已在 schema 用 toward_closeness/toward_distance）；
- B 在调用方做映射（`ai/human` → `toward_distance/toward_closeness`，`magnitude` 取绝对值）。

**影响面**：
- B：v0.2 段加映射表
- A：不动
- C：不动

---

## 决策#7 · 2026-08-29 · 不阻塞项优先级

**议题**：周中才有 A/C 的交付物（场景 4 锚点标记、LLM 假记忆生成 3 变体、A 记忆考古关卡 4.x 框架、sfx_glitch.wav 音频素材）。

**拍板**：**不阻塞的先做**，按以下优先级。

**优先级 P0（不依赖任何外部资料）**：
- ✅ docs/w3_decisions.md（本文）
- ✅ config/object_id_types.gd 加 MA_ enum（决策#5）
- ✅ config/trust_drift_rules_v0.1.md 追加 v0.2 段（决策#3 + 决策#6 映射表）
- ✅ scripts/memory_archaeology.gd 补记忆闪烁信号 + 状态写入（任务① 完成度）

**优先级 P1（依赖到位后做）**：
- ⏳ config/anchors.json 加 15 条新范本（任务④，等 C 锚点标记）
- ⏳ scripts/memory_archaeology.gd 切到 LLMGateway.analyze_memory()（任务②，等 A 升级调度层）
- ⏳ assets/audio/sfx_glitch.wav 加载路径（任务③，等 A 音频素材）
- ⏳ config/ambient_events.json description 填充（任务⑤，A 填文风）

**优先级 P2（A/C 周中交付后做）**：
- ⏳ 旧友文案定稿（任务⑤，v1.7 修订 + 场景 3/4 新增）
- ⏳ 氛围事件 12-16 条混合驱动版本（任务⑤）

---

## 决策#8 · 2026-08-29 · 文档约定

**议题**：工作指南里有些字段名 / 概念与现有项目不一致。

**拍板**：以**现有项目代码为准**（`anchors.schema.json` / `object_id_types.gd` / `trust_drift_rules_v0.1.md`）。工作指南是任务清单参考，不是契约。

**理由**：项目代码已落地、A/C 已对接。工作指南是给 B 的工作指南，**项目代码**才是给 A/C 的契约。

**影响面**：所有 交付物字段名以 schema/现有代码为准。

---

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-08-29 | 初版（8 条决策，记录 启动会议拍板） |