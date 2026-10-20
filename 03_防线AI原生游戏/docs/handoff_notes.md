# 交接说明 · 成员 C → 团队

本周 C 的交付物及对应使用说明，请各成员按需取用。

---

## 一、给 B：触发器接口（记忆锚点系统对接）

**文件**：`trigger_interface.md`（本包已含）

**你要做的**：在记忆锚点系统里订阅 `EventBus` 的 3 个信号，收到 `object_id` 后处理对应的锚点逻辑。

**代码示例**（详见接口文档 §四）：
```gdscript
func _ready() -> void:
    EventBus.object_approached.connect(_on_object_approached)
    EventBus.object_interacted.connect(_on_object_interacted)
    EventBus.object_left.connect(_on_object_left)

func _on_object_interacted(object_id: String) -> void:
    if object_id.begins_with("CF_"):   # 只处理记忆锚点类热点
        _show_template(object_id)      # 范本浮现 + 打字机
```

**关键点**：
- 你**只处理 `object_id` 对应的锚点内容**，完全不用管鼠标检测、场景切换——那些 C 已经做好了。
- 信号的 `object_id` 遵循命名规范 `场景缩写_类型_序号`（如 `CF_PHOTO_01`），见文档 §三。
- 出口热点 C 已处理（`is_exit` + `target_scene`），你不需要为出口写逻辑。

---

## 二、给 D：对话 UI 线框（视觉风格定稿）

**文件**（本包已含三件套）：
1. `dialogue_ui_wireframes.md` —— 文字稿（布局 + 状态 + 动画）
2. `ui_design_spec.md` —— 精确标注（尺寸 / 间距 / 颜色 / 四状态）
3. `ui_wireframes_preview.html` —— **可交互预览**（浏览器打开，悬停/点击有真实效果）

**你要做的**：基于线框做视觉风格定稿（立绘、头像、字体、质感）。

**必须保留**：
- ⚠️ **冷暖二元对立**：暖橙（`#FFB74D` 系）= AI 温柔面 / 真实记忆；冷蓝（`#2C3E50` 系）= 假记忆 / 侵蚀。这是玩家辨别真假记忆的**核心视觉线索**，定稿时不能把颜色统一掉。

**可以替换**：文案、立绘、头像、字体、质感纹理。

**基准分辨率**：1920×1080。

---

## 三、给 A：对话 UI 的 `mode` 映射

你的对话 JSON 里的 `mode` 字段，直接决定游戏用哪套 UI，共 4 个值：

| `mode` 值 | UI | 触发场景 |
|---|---|---|
| `chat_app` | AI 聊天 App | 与 AI 对话 |
| `visual_novel` | 视觉小说 | 与旧友面对面 |
| `fullscreen` | 全屏侵入 | 战斗中的 AI 对话 |
| `memory_card` | 记忆卡片 | 记忆考古辨真伪 |

> W2 落地时，对话系统读 JSON → 按 `mode` 切换，一套代码跑四套 UI。请保持这 4 个枚举值不变。

---

## 四、给团队：场景切换方案

**文件**：`scene_exploration_plan.md`（本包已含）

**结论**：本作采用**纯 2D 场景 + 场景切换式移动**（非 3D 第一人称）。移动 = 点击出口热点切换场景；交互 = 悬停/点击热点触发事件。供全员了解玩法底层架构。
