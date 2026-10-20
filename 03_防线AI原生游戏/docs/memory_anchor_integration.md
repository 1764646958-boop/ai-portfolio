# 记忆锚点系统联动契约（C ↔ B）

- **涉及方**：C（场景热点 / 交互 / UI）+ B（记忆锚点内容 / 信任偏移 / 记忆 LLM 引擎）
- **版本**：v0.1（W2，周日集成测试前对齐）
- **状态**：锚点物细节待 A 确认，冲突点已逐行核对 B 代码坐实

---

## 一、统一交互链路（目标架构）

```
玩家悬停热点   → interactable.gd → EventBus.object_approached  → 微光（C 已实现）
玩家点击热点   → interactable.gd → EventBus.object_interacted  → 范本浮现（C 的 memory_anchor_ui 承接）
玩家选情感     → memory_anchor_ui → EventBus.anchor_resolved    → B 的信任偏移系统消费
点击出口热点   → interactable.gd → SceneManager.change_scene    → 场景切换（C 已实现）
```

**核心原则**：EventBus 是唯一的事件主干。B 的锚点系统订阅信号，不直接碰 C 的热点脚本。

## 二、双方分工（明确边界）

| 环节 | 归属 | 说明 |
|---|---|---|
| 世界热点（Area2D + object_id） | C | `interactable.gd`，已实现 |
| 锚点浮现 UI（范本 + 情感选项） | C | `memory_anchor_ui.gd`，已实现（替代 B 的 ColorRect 原型） |
| 记忆范本文本（revealed_text） | B | 12 份范本（_extract_B_虚构记忆范本），填进 `config/anchors.json` |
| 情感选项内容 | B → A | W2 用 B 的 3 个占位项；W3 接 A 的 LLM 情感微调 |
| 信任偏移 / drift 判定 | B | 订阅 `anchor_resolved`，接 A 的记忆分析引擎 |

> B 的 W1 原型（`anchor_item.gd` 的 ColorRect + `memory_anchor.gd` 的 HBox 色块）是占位验证，**不在成品里用**。成品锚点 = C 的世界热点 + C 的浮现 UI + B 的内容。

## 三、信号约定

### C → B（B 订阅）

| 信号 | 参数 | B 响应 |
|---|---|---|
| `object_interacted` | `object_id: String` | 查映射 → 浮现范本 |
| `object_approached` | `object_id: String` | 微光（可选） |
| `object_left` | `object_id: String` | 微光消失（可选） |

### B → C（B 发出，本契约新增）

| 信号 | 参数 | 消费方 |
|---|---|---|
| `anchor_resolved` | `object_id: String, emotion: String` | B 信任偏移系统 / A 记忆分析引擎（W3） |

`anchor_resolved` 已加进 `EventBus.gd`。W3 时 B 在这里接 A 的 `drift_direction/magnitude/confidence`（见 [`dialogue_json_format.md`](./dialogue_json_format.md) §LLM 引擎对接）。

## 四、object_id → 记忆范本 映射草案（**待 A 确认锚点物**）

映射层现在由 `memory_anchor_ui.gd` 从 `config/anchors.json` 运行时加载（B 已接管）。

| B 范本 | 锚点物 | 建议 object_id | 场景 | 备注 |
|---|---|---|---|---|
| #1 | 栗子蛋糕 | `CF_CAKE_01` | 咖啡店 | 与已建的 `CF_PHOTO_01` 二选一（已替换） |
| #2 | 手机草稿箱 | `CR_SMS_01` ✅已建 | 教室 | 已写入映射 |
| #3 | 旧书票根 | `CR_TICKET_01` | 教室 | |
| #4 | 旧友语音留言 | `AP_MUSIC_01` | 公寓 | |
| #5 | 便利店酸奶 | `ST_FOOD_01` | 街道 | |
| #6 | 巷口手链 | `ST_ACC_01` | 街道 | 考古主线锚点 |
| #7 | 冬夜花束 | `ST_FLOWER_01` | 街道 | 考古主线锚点（玫瑰） |
| #8 | 自习室窗边 | `CR_SMS_02` | 教室 | |
| #9 | 针织蓝花 | `ST_FLOWER_02` | 街道 | 考古主线锚点 |
| #10 | 公交站划痕 | `ST_MARK_01` | 街道 | 非物品，是地点 |
| #11 | 下雨屋檐 | `ST_MARK_02` | 街道 | 非物品，是地点 |
| #12 | 告别录音 | `AP_MUSIC_02` | 公寓 | |

### ⚠️ 需要 A 拍板的 4 件事

1. **教室锚点物**：是「手机草稿箱」还是「照片」？C W2 默认 `CR_SMS_01`（手机）+ `CF_PHOTO_01`（照片）。
2. **咖啡店锚点**：照片 vs 栗子蛋糕？B 范本 #1 是蛋糕，但 C 默认是照片（**已统一为 `CF_CAKE_01`**）。
3. **类型枚举扩容**：现有 PHOTO/DIARY/TICKET/SMS/MUSIC 覆盖不了 B 的 12 份范本，需增 CAKE/FOOD/ACC/FLOWER/MARK 等（**已统一成新枚举**，见 [`config/object_id_types.gd`](../config/object_id_types.gd)）。
4. **#10/#11 是「地点」不是「物品」**：公交站划痕、屋檐——归入记忆锚点还是氛围事件？决定要不要单独建 ST_MARK_XX（**已统一走记忆锚点 + MARK 类型**，W3 再细化）。

## 五、5 个冲突点 + 解决方案（已逐行核对 B 代码）

| # | 冲突 | 现状 | 方案 |
|---|---|---|---|
| 1 | SceneManager 重名 | 双方 autoload 都叫 SceneManager，实现完全不同 | **合并只保留 C 的**；B 的旧 SceneManager 已归档到 `scripts/_legacy/scene_manager_W1.gd` |
| 2 | B 未订阅 EventBus | B 的 `AnchorItem.item_clicked` 自闭环，无任何 EventBus 引用 | **B 锚点系统改订阅 EventBus**；废弃 `anchor_item.gd`（ColorRect 原型，已归档到 `_legacy`） |
| 3 | 交互范式不同 | B 用 ColorRect（UI 层 HBox），C 用 Area2D（世界层） | **世界热点统一 C 的 interactable**（Area2D）；锚点浮现用 C 的 `memory_anchor_ui.gd`（CanvasLayer 覆盖层） |
| 4 | 数据模型不同 | C 用 `object_id`（机器名）；B 用 `item_name+revealed_text` | **增加 object_id → {item_name, revealed_text} 映射层**（已外迁到 `config/anchors.json`） |
| 5 | 分辨率不一致 | B 1280×720 vs C 1920×1080 | **统一 1920×1080**（已在 `project.godot` 设置） |

## 六、周日联动测试清单

- [ ] 点击我的热点 → `EventBus.object_interacted` 发出 → `memory_anchor_ui` 浮现范本
- [ ] 点情感选项 → `EventBus.anchor_resolved(object_id, emotion)` 发出
- [ ] B 订阅 `anchor_resolved` → 控制台打印收到的 `object_id + emotion`
- [ ] 非锚点热点（出口）点击 → 不弹锚点 UI，正常切场景
- [ ] 分辨率 1920×1080 下 UI 不拉伸错位
- [ ] 场景切换后锚点映射表不残留（旧场景的 `object_id` 不再触发）

## 七、anchors.json 数据契约（B 维护）

`memory_anchor_ui.gd` 在 `_ready` 调用 `_load_anchors()`，从 `res://config/anchors.json` 读取。

**JSON 顶层结构**：
```json
{
  "_meta": { ... },           // 注释/版本字段，自动跳过
  "CF_CAKE_01": {             // object_id 作为 key
    "item_name": "...",
    "revealed_text": "...",
    "emotion_options": ["...", "...", "..."],  // 可选；无则用全局 EMOTION_OPTIONS
    "scene": "咖啡店",
    "anchor_object": "...",
    "category": "memory_anchor"   // 或 "memory_anchor_archaeology_main" / "memory_anchor_location"
  },
  ...
}
```

**字段说明**：
- `item_name`：锚点物显示名（玩家在卡片标题里看到的）
- `revealed_text`：范本全文（含换行 `\n`，卡片正文）
- `emotion_options`：该锚点专属的 3 个情感选项（B 范本里的【参考选项】）
- `scene` / `anchor_object` / `category`：元数据，W3 记忆考古关卡按 `category` 分类用

**添加新锚点**：直接在 `anchors.json` 添加新 key，C 的场景 tscn 里增加对应 Area2D 节点（设 `object_id`）即可，**无需改 `memory_anchor_ui.gd`**。