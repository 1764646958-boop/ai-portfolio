# anchors.schema.json 使用说明

> **责任方**：B（核心程序 / 叙事设计）— W2 交付物
> **依据**：《游戏制作指南》§二.2 B-W2 验收标准第③条、§三 ③
> **配套文档**：[trigger_interface.md](../docs/trigger_interface.md) · [integration_decisions.md](../docs/integration_decisions.md) · [dialogue_json_format.md](../docs/dialogue_json_format.md)

## 这是什么

[`anchors.schema.json`](./anchors.schema.json) 是《防线》记忆锚点的**统一数据契约**，用 JSON Schema Draft-07 定义。它既覆盖**静态配置**（范本文本、情感选项、LLM 微调参数），也覆盖**玩家运行时写入字段**（玩家选择、LLM 假记忆生成结果、信任偏移更新）。

## 为什么需要

- 防止 B / A / C 三方对"一个锚点长什么样"理解不一致
- 校验 `config/anchors.json` 里每个锚点数据���否符合规范
- 作为 LLM 调度接口的输入/输出字段参考（[生产指南 §6.1](../README.md)）
- 让后续接入测试 / 数据迁移工具可以自动校验

## 必填字段（10 个）

| 字段 | 类型 | 说明 |
|---|---|---|
| `anchor_id` | string | 同 object_id，作 LLM 入参 |
| `object_id` | string (pattern) | `^(CF\|CR\|ST\|AP\|EXIT)_[A-Z]+_[0-9]{2,}$` |
| `scene` | string enum | 咖啡店 / 教室 / 街道 / 公寓 |
| `item_name` | string | UI 显示名 |
| `anchor_object` | string | 物品本体表述 |
| `category` | string enum | memory_anchor / memory_anchor_archaeology_main / memory_anchor_location |
| `revealed_text` | string | 范本文本，结尾可含 `＿＿＿` 留白 |
| `emotion_options` | array[3] | 恰好 3 个情感选项 |
| `identification_difficulty` | number 0-1 | 辨识难度系数 |
| `llm_params` | object | 至少含 twistable_elements + drift_dimension |

## 运行时写入字段（默认 null）

由 `memory_anchor_ui.gd` 在交互时填充：
- `player_emotion_choice` / `player_free_input` / `player_selected` / `player_skipped`
- `interaction_timestamp` (ISO 8601)
- `llm_complete_memory` / `llm_fake_variants[3]`
- `drift_update{direction, magnitude, confidence}` — **不**进对话 JSON，直接给信任偏移系统（[C 集成决��� §附](../docs/integration_decisions.md)）

## 当前状态（v7.0，2026-08-24）

- ✅ schema 文件已创建并通过 JSON 合法性校验（0 mojibake）
- ✅ `anchors.json` 已按 schema 重构，**26/26 通过 schema 校验**
- ✅ 全部 10 个必填字段补齐：anchor_id / object_id / scene / item_name / anchor_object / category / revealed_text / emotion_options / identification_difficulty / llm_params
- ✅ 5 个可选字段也已填充：scene_location / offset_type（v5.3 设计元数据，作为扩展保留）/ anchor_type 默认 core
- ✅ `CR_SMS_01`（教室场景）复用 `DM_SMS_01` 的 `llm_params`（B 未单独给 CR 草稿箱范本，仅 scene_location 调整为"教室·书桌"）
- ✅ `scene` 字段统一为中文（与 `object_id_types.gd SCENE_ABBREV` / `trigger_interface.md §三` 保持一致）

## v5.3 → v7.0 迁移记录

迁移脚本：`scripts/migrate_v53_to_v7.py`（临时备份于 `C:\Users\辣酱汤\.claude\tmp\migrate_v53.py`）

| 字段 | 来源 | 数量 |
|---|---|---|
| `anchor_id` | 取 key 值 | 26/26 |
| `object_id` | 取 key 值（已符合 `^(CF\|CR\|ST\|AP\|DM\|EXIT)_[A-Z]+_[0-9]{2,}$` 规范）| 26/26 |
| `scene_location` | B v5.3 范本 `scene_location` | 26/26 |
| `identification_difficulty` | B v5.3 范本（0.51~0.75 范围）| 26/26 |
| `llm_params` | B v5.3 范本 `drift_params` → 重命名为 `llm_params`，含 `twistable_elements` + `drift_dimension` + `note` | 26/26 |
| `offset_type` | B v5.3 设计元数据（A/B/C/D 4 型）| 26/26 |

## 下一步（W2-B 剩余任务清单）

1. ~~把 26 个现有锚点补齐 schema 必填字段~~ ✅ 已完成（v7.0）
2. ~~给 5 个锚点写完整示例（含 `player_selected` / `llm_complete_memory` / `drift_update` 等运行时字段的实际填写示例，[生产指南 §二.2 B-W2 验收](README.md)）~~ ✅ 已完成
   - 文档：[`docs/anchors_examples_v5.3.md`](../docs/anchors_examples_v5.3.md)
   - 数据实例：`save/example_save.json`（5/5 通过 schema 校验）——该实例文件未随仓库分发
   - 覆盖：3 场景 × A/B offset_type × 3 drift_direction（toward_closeness / toward_distance / ambiguous）
3. 范���扩至 25 条 → 40 条（[生产指南 §二.2 B-W3](README.md)）
4. 引入 `python -m jsonschema -i anchors.json anchors.schema.json` 校验进 CI / commit hook

## 运行时字段填写规范

参考 [`docs/anchors_examples_v5.3.md`](../docs/anchors_examples_v5.3.md)：

| 字段 | 来源 | 写入时机 |
|---|---|---|
| `player_emotion_choice` | 玩家点击情感选项 | 玩家选择完成时 |
| `player_free_input` | 玩家自由输入 | 玩家点 "完成" 时（可空字符串）|
| `player_selected: true` | UI 完成交互 | `memory_anchor_ui.gd` |
| `interaction_timestamp` | `Time.get_datetime_string_from_system(true)` | 玩家首次点击 |
| `llm_complete_memory` | `LLMGateway.analyze_memory(emotion + free_input + revealed_text)` | 玩家选完情感 + 触发 LLM |
| `llm_fake_variants[3]` | `LLMGateway.generate_dialogue(llm_params)` | 同上 |
| `drift_update` | `LLMGateway` 输出 + `TrustDrift.record_anchor_resolution()` | LLM 返回后写入 |

> **不要**把运行时字段写入 `anchors.json`（会被覆盖），写到 `save/player_<slot>.json` 的 `anchors[key]` 子对象。

## 校验示例

```bash
# 需要先 pip install jsonschema
python -m jsonschema -i config/anchors.json config/anchors.schema.json
```

GDScript 侧校验可参考 Godot 的 `JSON.validate()` + 字段读取（Godot 内置不支持 JSON Schema 校验，需自己写最小验证）。