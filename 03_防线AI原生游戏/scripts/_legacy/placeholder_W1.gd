extends Node
## 场景 2 · 占位空场景
## 用于验证 SceneManager 可加载/卸载至少 2 个场景;自身不承载玩法。


func _ready() -> void:
	# 该场景暂无锚点物品,注册空列表,证明"每个场景独立锚点列表"这一结构成立
	SceneManager.register_anchors([])
