# 对话数据格式约定（A → C）

- **约定方**：A（叙事 / LLM，产数据）→ C（对话系统，消费数据）
- **版本**：v0.2（W2，补 LLM 引擎对接）
- **文件**：JSON，一个文件可含多段对话

---

## 一、顶层结构

```json
{
  "dialogues": {
    "CF_INTRO_01": { "..." : "一段对话" },
    "CF_INTRO_02": { "..." : "另一段" }
  }
}
```

也可把单段对话直接传给 `DialogManager.register()`。

## 二、单段对话字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mode` | String | 是 | `chat_app` / `visual_novel` / `fullscreen` / `memory_card` |
| `lines` | Array | 是 | 对话行数组 |
| `choices` | Array | 否 | 可选回复（chat_app / visual_novel 用） |
| `typing_speed` | int | 否 | 打字机速度 ms/字，默认 60 |
| `speaker_name` | String | 否 | 聊天顶部显示的 AI 名（chat_app 用） |
| `portrait_position` | String | 否 | 立绘位置 `left/right/center`（visual_novel 用） |

### `lines` 元素

| 字段 | 类型 | 说明 |
|---|---|---|
| `speaker` | String | `ai`（AI）/ `friend`（旧友）/ `player`（主角） |
| `name` | String | 显示名（AI 名 LLM 生成，旧友名可为 `"[X]"`） |
| `text` | String | 内容 |
| `meta` | Dictionary | LLM 附加参数（warmth/manipulation/helpfulness），可选，W3 用 |

### `choices` 元素

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | String | 选项文字 |
| `next` | String | 选后跳转的 `dialogue_id`（空 = 结束对话） |

## 三、完整示例

```json
{
  "dialogues": {
    "CF_INTRO_01": {
      "mode": "chat_app",
      "speaker_name": "林默 · 你的AI陪伴",
      "typing_speed": 60,
      "lines": [
        { "speaker": "ai", "name": "林默", "text": "今天也累了吧？" },
        { "speaker": "friend", "name": "[X]", "text": "你……为什么知道？" }
      ],
      "choices": [
        { "text": "「你在说谎」", "next": "CF_INTRO_02" },
        { "text": "「继续」", "next": "CF_INTRO_03" }
      ]
    }
  }
}
```

## 四、实现对照（C 侧）

- 对话系统读 JSON → 按 `mode` 分发到四套 UI（DialogManager 发信号，UI 各自订阅）
- `choices[].next` 为空表示对话结束；非空则跳转到对应 `dialogue_id`
- `speaker` 决定气泡样式：`ai` 左侧暖橙、`friend` 右侧灰白

## 五、LLM 引擎对接（A 的 5 个引擎 → 本格式）

A 的 LLM 引擎（DeepSeek，W1 已连通）运行时输出，映射关系：

| LLM 引擎 | 输出 JSON | 映射到本格式 |
|---|---|---|
| 对话生成引擎 | `{"dialogue_text","warmth","manipulation","helpfulness"}` | `dialogue_text` → `lines[].text`；三参数 → `lines[].meta` |
| 记忆分析引擎 | `{"drift_direction","magnitude","confidence"}` | 不进对话，交给 B 的信任偏移系统 |
| 假记忆生成引擎 | 真 / 负面扭曲 / 微偏真实（3 版） | `memory_card` 模式的 3 张卡片（W3 定结构） |
| 战斗对话引擎 | 压迫对话文本 | `fullscreen` 模式的 `lines` |
| 名字生成引擎 | `[X]` 名字 + 理由 | `lines[].name` / `speaker_name` |

## 六、`lines[].meta`（可选，W3 用）

W2 静态 JSON 不填；W3 接实时 LLM 时，把对话引擎的 warmth/manipulation/helpfulness 存进来，供信任偏移系统读取：

```json
{
  "speaker": "ai",
  "name": "林默",
  "text": "今天也累了吧？",
  "meta": { "warmth": 0.9, "manipulation": 0.3, "helpfulness": 0.95 }
}
```

## 七、W2 / W3 分界

- **W2**：C 读静态 JSON；A 先按本格式手写 / 预生成对话数据
- **W3**：接 LLM 引擎，把运行时输出实时转成本格式的 `lines`，`meta` 字段开始生效

> ⚠️ `drift_direction / magnitude / confidence`（记忆分析引擎输出）是信任偏移系统的输入，**不属于对话展示数据**，不要塞进 `lines`。