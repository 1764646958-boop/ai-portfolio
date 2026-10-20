# scene_manager.gd —— 场景切换管理器（Autoload 单例）
# 职责：2D 场景之间的切换。本作"移动 = 场景切换"，这是探索系统的核心。
# 配置：项目设置 → Autoload → 添加本文件，节点名 SceneManager
#
# W2：新增淡入淡出过渡——黑屏淡出(0.3s) → 切换场景 → 淡入恢复(0.3s)。
#     过渡层挂在 SceneManager 下（Autoload 常驻），不受场景切换释放影响。

extends Node

const FADE_DURATION := 0.3

# 过渡黑幕（常驻，平时全透明；过渡时变黑）
var _fade_rect: ColorRect
var _transitioning: bool = false


func _ready() -> void:
	# 顶层 CanvasLayer + 全屏黑色 ColorRect，平时透明
	var layer := CanvasLayer.new()
	layer.layer = 100   # 顶层，盖住所有游戏场景
	add_child(layer)

	_fade_rect = ColorRect.new()
	_fade_rect.color = Color(0, 0, 0, 0)
	_fade_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_fade_rect)


## 切换到目标场景（path 形如 "res://scenes/coffee_shop.tscn"），带淡入淡出
func change_scene(path: String) -> void:
	if path.is_empty():
		push_error("SceneManager: 目标场景路径为空")
		return
	if _transitioning:
		return   # 过渡进行中，忽略重复触发

	_transitioning = true
	_fade_rect.mouse_filter = Control.MOUSE_FILTER_STOP  # 过渡期间挡点击

	# 1) 淡出到黑
	await _fade_to(1.0)

	# 2) 切换场景
	var err := get_tree().change_scene_to_file(path)
	if err != OK:
		push_error("SceneManager: 场景切换失败 %s (err=%d)" % [path, err])
		await _fade_to(0.0)   # 失败也要恢复
		_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_transitioning = false
		return

	# 3) 通知 + 淡入恢复
	EventBus.scene_changed.emit(path)
	await _fade_to(0.0)

	_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_transitioning = false


## 把黑幕 alpha 过渡到目标值
func _fade_to(target_alpha: float) -> void:
	var tween := create_tween()
	tween.tween_property(_fade_rect, "color:a", target_alpha, FADE_DURATION)
	await tween.finished
