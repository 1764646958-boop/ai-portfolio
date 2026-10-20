class_name UILayers
## UI Canvas 层级规划(第一周:规划,不实现具体 UI)
## 使用:新增 CanvasLayer 时设置 layer = UILayers.Layer.DIALOG 等
## 完整说明见 config/ui_canvas_layers.md

enum Layer {
	WORLD = 0,             ## 世界/场景层(默认,非 CanvasLayer)
	DIALOG = 1,            ## 对话 UI 层(玩家对话、NPC 对话)
	MEMORY_ANCHOR = 2,     ## 记忆锚点提示层(锚点交互提示、范本浮现)
	MEMORY_CARD = 3,       ## 记忆卡片层(记忆考古关卡卡片)
	AI_MESSAGE = 4,        ## AI 消息界面层(LLM 实时消息流)
	COMBAT_HUD = 5,        ## 战斗 HUD 层(记忆解体重构战斗)
	FULLSCREEN_DIALOG = 6, ## 全屏侵入对话层(全屏侵入式对白/过场)
}
