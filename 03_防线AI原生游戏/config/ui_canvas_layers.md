# 《防线》UI Canvas 层级规划

> 依据:B 第一周「场景管理框架(场景加载/卸载 + UI Canvas 层级规划)」
> 状态:规划稿 —— 第一周只定义层级,不实现具体 UI
> 对应代码:`scripts/ui_layers.gd` 中 `enum UILayers.Layer`

## 一、层级总表

采用 CanvasLayer + `layer` 索引。数值越大渲染越靠上。

| 层索引 | 常量名 | 用途 |
|---|---|---|
| 0 | `WORLD` | 世界/场景层(默认,非 CanvasLayer) |
| 1 | `DIALOG` | 对话 UI 层(玩家对话、NPC 对话) |
| 2 | `MEMORY_ANCHOR` | 记忆锚点提示层(锚点交互提示、范本浮现) |
| 3 | `MEMORY_CARD` | 记忆卡片层(记忆考古关卡卡片) |
| 4 | `AI_MESSAGE` | AI 消息界面层(LLM 实时消息流) |
| 5 | `COMBAT_HUD` | 战斗 HUD 层(记忆解体重构战斗) |
| 6 | `FULLSCREEN_DIALOG` | 全屏侵入对话层(全屏侵入式对白/过场) |

## 二、规划说明

- 各 UI 层与场景解耦,切换场景时 UI 层仍可叠加/常驻。
- 全屏侵入对话层置于最顶,保证过场/侵入式对白不被任何内容遮挡。
- 新增 UI 时统一通过 `UILayers.Layer` 指定层级,避免魔法数字散落。

## 三、与场景管理框架的关系

- 场景负责自身世界内容与 UI 内容,UI 挂到对应 CanvasLayer。
- `SceneManager` 负责加载/卸载场景;各 UI 层由场景或全局 UI 控制器按 `UILayers.Layer` 创建。

## 四、后续(非本周)

- 对话系统、记忆卡片、AI 消息、战斗 HUD、全屏对话等 UI 在本周**不实现**,仅保留层级预留。
