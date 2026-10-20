# 场景探索系统技术方案 · 2D 场景切换版

- **成员**：C
- **周次**：W1（8/10-8/16）
- **引擎**：MagicAI（Godot 4.x）
- **维度决策**：纯 2D 场景，人物移动 = 场景切换（2026-08-13 确认）

---

## 一、方案结论

本作采用 **纯 2D 场景 + 场景切换式移动**（非 3D 第一人称、非自由 WASD 移动）：

- 每个场景 = 一张 2D 背景图 + 若干可点击"热点"
- **移动**：点击场景中的出口热点 → 淡入淡出 → 切换到另一场景
- **交互**：鼠标悬停热点 → 微光；点击 → 触发事件（记忆锚点/氛围事件）

## 二、核心机制

| 机制 | 实现 | 归属 |
|---|---|---|
| 场景管理 | `SceneManager`（Autoload）：`change_scene(path)` | C |
| 热点交互 | `interactable.gd`（挂 Area2D）：悬停/点击信号 | C |
| 事件分发 | `EventBus`（Autoload）：`object_approached/interacted/left` | C → B 订阅 |
| 淡入淡出 | CanvasLayer + ColorRect + Tween | W2 实现 |

## 三、场景结构

```
场景根 (Node2D)
├── Sprite2D              ← 背景图（D 交付 PNG）
├── Hotspot (Area2D) ×N   ← 记忆锚点物品
│   ├── CollisionShape2D
│   └── Sprite2D          ← 占位图标（悬停提亮=微光）
└── Hotspot (Area2D) ×M   ← 场景出口（is_exit=true）
```

## 四、交互流程

```
鼠标悬停热点  → EventBus.object_approached  → B 的锚点微光
鼠标点击热点  → EventBus.object_interacted  → B 的范本浮现 / 氛围事件
鼠标移出热点  → EventBus.object_left        → B 的微光消失
点击出口热点  → SceneManager.change_scene() → 场景切换
```

## 五、与 W2 的衔接

- **W1**：热点交互 + 场景切换基础链路跑通（本方案）
- **W2**：场景 1（咖啡店/教室）可探索区域完整搭建 + 淡入淡出过渡
- **W3**：场景 2-3 + 旧友"偶遇"事件 + AI 消息界面

## 六、性能基准

| 项 | 目标 |
|---|---|
| 场景渲染（2D 背景 + 热点） | 稳定 60fps |
| 场景切换 | 无卡顿、无黑屏闪烁（W2 加淡入淡出后） |

## 七、验收标准（周日自检）

- [ ] 悬停热点 → 微光 + 事件发出
- [ ] 点击热点 → `触发：[object_id]` 输出 + 事件发出
- [ ] 点击出口 → 场景切换成功
- [ ] 交互逻辑与 B 的记忆锚点系统解耦（B 只靠 EventBus 订阅了