# 场景交互触发器标准接口（C → B）· 2D 版

- **交付方**：C（成员 C）
- **使用方**：B（记忆锚点系统订阅这些信号）
- **对应文档**：《游戏制作指南》§6.2 场景交互接口
- **维度**：纯 2D，交互 = 鼠标悬停/点击热点（本作"移动 = 场景切换"）

---

## 一、接口总览

C 提供全局事件总线 `EventBus`（Autoload 单例）。B 的记忆锚点系统通过订阅信号工作，不直接耦合 C 的热点脚本。

所有可交互热点（记忆锚点、氛围事件、场景出口）统一挂 `interactable.gd`，用 `object_id` 区分。

## 二、信号定义

| 信号 | 触发时机 | 参数 | B 的响应 |
|---|---|---|---|
| `object_approached` | 鼠标悬停进入热点 | `object_id: String` | 锚点微光 |
| `object_interacted` | 鼠标点击热点 | `object_id: String` | 范本浮现 + 打字机 |
| `object_left` | 鼠标移出热点 | `object_id: String` | 微光消失 |
| `scene_changed` | 场景切换完成 | `target_path: String` | 场景管理用 |

对应《游戏制作指南》§6.2 的 `OnObjectApproach / OnObjectInteract / OnObjectLeave`。

2D 下"靠近/离开"映射为"鼠标悬停进入/移出"，`distance` 参数已移除。

## 三、object_id 命名规范

**格式**：`场景缩写_类型_序号`

| 场景 | 缩写 | 类型枚举 | 示例 |
|---|---|---|---|
| 咖啡店 | CF | PHOTO/DIARY/TICKET/SMS/MUSIC/CAKE/FOOD/ACC/FLOWER/MARK | CF_CAKE_01 |
| 教室 | CR | 同上 | CR_SMS_01 |
| 街道 | ST | 同上 | ST_TICKER_01 |
| 公寓 | AP | 同上 | AP_MUSIC_01 |

**出口热点**：`EXIT_<目标场景缩写>`，如 `EXIT_CR`（通往教室的出口）。

## 四、代码接入示例（B 侧）

```gdscript
# B 的记忆锚点系统里，任意脚本监听即可：
func _ready() -> void:
    EventBus.object_approached.connect(_on_object_approached)
    EventBus.object_interacted.connect(_on_object_interacted)
    EventBus.object_left.connect(_on_object_left)

func _on_object_approached(object_id: String) -> void:
    if object_id.begins_with("CF_"):   # 只处理记忆锚点类热点
        _show_glow(object_id)

func _on_object_interacted(object_id: String) -> void:
    _show_template(object_id)          # 范本浮现 + 打字机

func _on_object_left(object_id: String) -> void:
    _hide_glow(object_id)
```

## 五、场景结构要求（2D）

每个可交互热点（Area2D）的节点结构：

```
Hotspot (Area2D)          ← 挂 interactable.gd，设 object_id
├── CollisionShape2D      ← 热点范围（RectangleShape2D 或多边形）
└── Sprite2D              ← 占位图标（悬停时提亮=微光）
```

场景整体结构：

```
场景根 (Node2D)
├── Sprite2D              ← 背景图（D 交付，PNG 3840×2160）
├── Hotspot 记忆锚点 ×N    ← object_id 按命名规范
└── Hotspot 出口 ×M        ← is_exit=true + target_scene
```

## 六、验收标准（周日自检）

- [ ] 鼠标悬停热点 → 控制台输出接近事件 + Sprite2D 提亮（微光）
- [ ] 点击热点 → 控制台输出 `触发：[object_id]`
- [ ] 鼠标移出 → 控制台输出离开事件 + 提亮消失
- [ ] 点击出口热点 → 切换到目标场景
- [ ] B 能仅凭本文档 + EventBus 订阅开发锚点系统，无需改动 C 的触发器代码