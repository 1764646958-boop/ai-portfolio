# 《防线》集成决策清单（C 侧先拍板）

- **说明方**：C
- **审阅方**：A、B
- **版本**：v0.1（周日集成前对齐）
- **原则**：改动成本低（映射集中在 `anchors.json` 一处），先拍板不阻塞进度；有异议请周日前提出，否则按此推进。

---

## 第一部分：技术对接冲突（B 关注）

### 冲突 1：SceneManager 重名

- **现状**：双方 autoload 都叫 SceneManager，实现完全不同（C：`change_scene_to_file`+淡入淡出；B：`add_child`+`register_anchors`），合并必冲突。
- **方案 A**：保留 C 的 SceneManager（探索主链路），B 的 `register_anchors / get_anchors` 能力并入 C 的。
- **方案 B**：保留 B 的，C 的淡入淡出并入 B 的。
- **方案 C**：各自改名（SceneManager / MemoryAnchorStore）。
- ✅ **C 选 A**：C 的带淡入淡出 + EventBus 联动，是主链路；B 的锚点注册能力并入即可。

### 冲突 2：B 未订阅 EventBus

- **现状**：B 的 `anchor_item.gd` 用自带 `item_clicked` 信号自闭环，没接 C 的事件总线。
- **方案 A**：B 改成订阅 `EventBus.object_interacted`，情感选完发 `EventBus.anchor_resolved`（信号解耦）。
- **方案 B**：C 直接调 B 的锚点方法（耦合）。
- ✅ **C 选 A**：符合 EventBus 架构，两边互不依赖对方内部实现。

### 冲突 3：交互范式不同

- **现状**：B 用 ColorRect（UI 层色块），C 用 Area2D（世界层热点）。
- **方案 A**：场景热点统一用 C 的 Area2D + `interactable.gd`，锚点浮现用 CanvasLayer 覆盖层。
- **方案 B**：保留 B 的 ColorRect 作为锚点。
- ✅ **C 选 A**：成品是 2D 世界场景，热点必须是世界对象，ColorRect 只是原型占位。

### 冲突 4：数据模型不同

- **现状**：C 用 `object_id`（机器名），B 用 `item_name`（显示名）+ `revealed_text`（范本）。
- **方案 A**：加一层 `object_id → {item_name, revealed_text}` 映射。
- **方案 B**：直接用 `item_name` 当 `object_id`。
- ✅ **C 选 A**：机器名和显示名分离，后续换文本不改代码。

### 冲突 5：分辨率不一致

- **现状**：B 1280×720，C 1920×1080。
- **方案 A**：统一 1920×1080。
- **方案 B**：统一 1280×720。
- ✅ **C 选 A**：D 的背景图是 3840×2160，正好 2×1080p，1080p 是最优。

---

## 第二部分：内容决策（A 关注，B 提供范本）

### 冲突 6：教室锚点物

- **方案 A**：旧手机的草稿箱 `CR_SMS_01`（对齐 B 范本 #2，有现成文字）。
- **方案 B**：照片（B 的 12 份范本里无「照片」，文字需现写）。
- ✅ **C 选 A**：有内容支撑。

### 冲突 7：咖啡店锚点物

- **方案 A**：栗子蛋糕 `CF_CAKE_01`（对齐 B 范本 #1，有现成文字）。
- **方案 B**：照片 `CF_PHOTO_01`（无对应范本）。
- ✅ **C 选 A**：同上，选有内容支撑的。

### 冲突 8：object_id 类型枚举

- **现状**：现有 PHOTO / DIARY / TICKET / SMS / MUSIC 五种，盖不住 B 的 12 份范本（蛋糕、手链、花束、酸奶、公交站、屋檐…）。
- **方案 A**：扩容，新增 CAKE / FOOD / ACC / FLOWER / MARK。
- **方案 B**：不扩容，尽量套现有五类。
- ✅ **C 选 A**：类型本身是 C 的命名规范，扩容不冲突，但提前报备。

### 冲突 9：地点类怎么归类

- **现状**：公交站划痕（#10）、下雨屋檐（#11）不是「物品」而是「地点」。
- **方案 A**：先都归记忆锚点（统一走热点交互），氛围事件 W3 再拆。
- **方案 B**：单独做氛围事件。
- ✅ **C 选 A**：W2 先跑通主链路，W3 再细化。

---

## 附：已定的约定（无异议即按此执行，不单独讨论）

A 的 LLM 输出映射已定：

- `dialogue_text` → `lines[].text`
- `warmth / manipulation / helpfulness` → `lines[].meta`（W3 用）
- `drift_direction / magnitude / confidence` **不进**对话 JSON，直接给 B 的信任偏移系统

详见 [`dialogue_json_format.md`](./dialogue_json_format.md) §「LLM 引擎对接」。