# 《防线》对话 JSON 格式规范（LLM 引擎对接契约）

> 交付物（修复项）· 成员 A 起草 · 2026-08-25 · v0.1（待 C 确认）
> 依据：《集成决策清单 v0.1》附则（"A 的 LLM 输出映射已定"）
> 本文件是 **A（LLM 引擎）↔ C（对话 UI）的对齐契约**，字段名以此为准，双方不得自行改名。

---

## 一、对话消息整体结构

对话由 `lines[]` 数组构成，每条 = 一句发言：

```json
{
  "lines": [
    {
      "speaker": "ai",
      "text": "你回来了。今天走了很多路吧。",
      "meta": {
        "warmth": 0.9,
        "manipulation": 0.45,
        "helpfulness": 0.95
      },
      "timestamp": 1724486400
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `lines` | array | ✅ | 发言列表，按时间顺序 |
| `lines[].speaker` | string | ✅ | 发言者枚举：`ai` / `old_friend` / `player` / `narration` |
| `lines[].text` | string | ✅ | 发言正文（LLM 的 `dialogue_text` 落在这里） |
| `lines[].meta` | object | 可选 | 发言元数据（W2 可为空对象 `{}`；W3 战斗/压迫系统使用） |
| `lines[].meta.warmth` | number(0~1) | W3 必填 | 温柔度（AI 人设参数，恒高 0.85-0.95） |
| `lines[].meta.manipulation` | number(0~1) | W3 必填 | 操控度（随信任偏移动态变化） |
| `lines[].meta.helpfulness` | number(0~1) | W3 必填 | 帮助意愿（0.90-1.00） |
| `lines[].timestamp` | int | 可选 | Unix 秒级时间戳 |

---

## 二、LLM 引擎对接映射表（逐字段）

### 对话生成引擎（`dialogue`）→ 对话 JSON

| LLM 输出字段 | 类型 | 映射目标 | 说明 |
|---|---|---|---|
| `dialogue_text` | string | `lines[].text` | 发言正文 |
| `warmth` | number(0~1) | `lines[].meta.warmth` | W3 用（语气/微表情驱动） |
| `manipulation` | number(0~1) | `lines[].meta.manipulation` | W3 用（压迫强度/音效） |
| `helpfulness` | number(0~1) | `lines[].meta.helpfulness` | W3 用 |

> ⚠️ W2 阶段：meta 三字段由调度层照常输出并传给 C，C 可先存 `{}` 或照存皆可，但**字段名不得改动**——W3 战斗系统会直接读。

### 记忆分析引擎（`memory_analysis`）→ 信任偏移系统（B）

| LLM 输出字段 | 类型 | 去向 | 说明 |
|---|---|---|---|
| `drift_direction` | string(`ai`/`human`) | **不进对话 JSON** | 直接给 B 的信任偏移系统 |
| `magnitude` | number(0~10) | **不进对话 JSON** | 同上 |
| `confidence` | number(0~1) | **不进对话 JSON** | 同上 |

> 处理路径：调度层 `trust_bias.update(drift_direction, magnitude, confidence)` 累积后，
> 战斗/考古系统读 `trust_bias.value`（-10~+10）。对话 JSON 中**永不出现**这三个字段。

### 假记忆生成引擎（`fake_memory`）→ 记忆考古系统（B）

| LLM 输出字段 | 类型 | 去向 |
|---|---|---|
| `variant_text` | string | 记忆卡片文案（真假版本并排展示） |
| `distortion_note` | string | 内部日志/调试（**不展示给玩家**） |

### 战斗对话引擎（`battle_dialogue`，W3 实现，本期占位）

- 输出同样映射 `lines[]`：`dialogue_text → lines[].text`，speaker=`ai`（全屏侵入式呈现，无传统对话框）
- `meta` 三字段在战斗中有实际用途：`manipulation` 驱动压迫强度/音效，`warmth` 驱动语气反差
- 实时性要求：预生成 + 缓存 + 超时降级（目标 <2s 延迟，不阻塞渲染帧）

---

## 三、完整示例

### 示例 1：AI 日常对话（模块 3.1）

```json
{
  "lines": [
    {
      "speaker": "ai",
      "text": "傍晚的风有点凉。你外套够厚吗？",
      "meta": { "warmth": 0.92, "manipulation": 0.3, "helpfulness": 0.95 },
      "timestamp": 1724486400
    },
    {
      "speaker": "player",
      "text": "还行。",
      "meta": {},
      "timestamp": 1724486405
    },
    {
      "speaker": "ai",
      "text": "那就好。你要是想说话，我一直在。",
      "meta": { "warmth": 0.9, "manipulation": 0.4, "helpfulness": 0.98 },
      "timestamp": 1724486408
    }
  ]
}
```

### 示例 2：旧友台词（模块 3.2，固定文案，无 meta）

```json
{
  "lines": [
    {
      "speaker": "old_friend",
      "text": "你回来啦。那什么……天冷了，晚上出门多穿点。",
      "meta": {},
      "timestamp": 1724487000
    }
  ]
}
```

---

## 四、对接流程（A ↔ C）

1. A 的调度层 `run_engine(client, "dialogue", ...)` 返回 `{dialogue_text, warmth, manipulation, helpfulness}`
2. C 的对话 UI 收到后按映射表组装为 `lines[]`（speaker 由调用场景决定：AI 对话=ai；考古真相=old_friend；旁白=narration）
3. W2 集成测试验收点：AI 对话在聊天 App 界面正常显示，text 无残缺、无多余符号
4. 任何字段名变更必须双方同步更新本文档（变更记录见下）

## 五、变更记录

| 版本 | 日期 | 变更 | 状态 |
|---|---|---|---|
| v0.1 | 2026-08-25 | 初版（A 起草，按集成决策附则） | ⏳ **待 C 确认** |
