# interactable.gd —— 场景热点交互（2D 场景切换版）
# 挂载到 Area2D 上。节点结构（名字必须精确）：
#   Hotspot (Area2D)        ← 挂本脚本
#   ├── CollisionShape2D    ← 热点范围（RectangleShape2D 或多边形）
#   └── Sprite2D            ← 占位图标/色块（悬停时提亮表示"微光"）
#
# 依赖：EventBus、SceneManager 已注册为 Autoload
# 用法：object_id 按命名规范填（如 CF_PHOTO_01）
#       出口热点需勾选 is_exit 并填 target_scene（如 "res://scenes/coffee_shop.tscn"）

extends Area2D

## 热点唯一标识：场景缩写_类型_序号（如 CF_PHOTO_01）
@export var object_id: String = "CF_PHOTO_01"

## 是否为场景出口（点击后切换到另一场景）
@export var is_exit: bool = false

## 出口目标场景路径（is_exit 为 true 时生效）
@export var target_scene: String = ""

## 出口用绿色 + 光标变箭头；锚点用白色 + 光标变手形（视觉/交互双重区分）
const COLOR_EXIT := Color(0.3, 0.8, 0.4)
const COLOR_EXIT_HOVER := Color(0.5, 1.0, 0.6)
const COLOR_ANCHOR_HOVER := Color(1.4, 1.3, 1.0)

## 场景路径 → 显示名（出口文字标签用，与 SceneManager 路径一致）
const SCENE_NAMES := {
	"res://scenes/coffee_shop.tscn": "咖啡店",
	"res://scenes/classroom.tscn": "教室",
	"res://scenes/dormitory.tscn": "宿舍",
	"res://scenes/street.tscn": "街道",
	"res://scenes/apartment.tscn": "公寓",
	"res://scenes/battle.tscn": "战斗",
}

## ── 测试期文字注释 ──────────────────────────────────────────────
## 每个热点上方浮一行文字，显示 object_id 与用途，方便联调时认点位。
## 正式打包前把 DEBUG_LABELS 改成 false 即可全局关掉（不用改任何场景文件）。
const DEBUG_LABELS := true

## 注释配色（按用途区分，黑描边保证任何背景上都读得清）
const COLOR_LABEL_EXIT := Color(0.55, 1.0, 0.65)    # 出口 → 绿
const COLOR_LABEL_ARCH := Color(1.0, 0.85, 0.35)    # 考古入口 → 金
const COLOR_LABEL_ANCHOR := Color(0.55, 0.90, 1.0)  # 有范本内容 → 青
const COLOR_LABEL_PLAIN := Color(0.92, 0.92, 0.92)  # 普通锚点 → 白


func _ready() -> void:
	# Area2D 鼠标信号（需有 CollisionShape2D；input_pickable 默认 true）
	mouse_entered.connect(_on_mouse_entered)
	mouse_exited.connect(_on_mouse_exited)
	input_event.connect(_on_input_event)
	_apply_baseline_color()


func _on_mouse_entered() -> void:
	EventBus.object_approached.emit(object_id)
	_set_glow(true)
	_set_cursor(true)
	print("悬停：", object_id)   # 验收标准：悬停输出（微光 = 触发确认）


func _on_mouse_exited() -> void:
	EventBus.object_left.emit(object_id)
	_set_glow(false)
	_set_cursor(false)
	print("离开：", object_id)


func _on_input_event(_viewport: Node, event: InputEvent, _shape_idx: int) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		EventBus.object_interacted.emit(object_id)
		print("触发：", object_id)   # W1 验收标准：控制台输出此句
		if is_exit and not target_scene.is_empty():
			SceneManager.change_scene(target_scene)


## 微光效果：悬停时把 Sprite2D 子节点提亮（出口与锚点用不同颜色）
func _set_glow(active: bool) -> void:
	for child in get_children():
		if child is Sprite2D:
			if is_exit:
				child.modulate = COLOR_EXIT_HOVER if active else COLOR_EXIT
			else:
				child.modulate = COLOR_ANCHOR_HOVER if active else Color.WHITE


## 初始化：出口方块上绿色（与锚点视觉区分）+ 白色箭头；所有热点都加文字注释
func _apply_baseline_color() -> void:
	if is_exit:
		for child in get_children():
			if child is Sprite2D:
				child.modulate = COLOR_EXIT
		_ensure_exit_arrow()
	_ensure_debug_label()


## 出口角标：白色三角形 ▷（方向 = "前进/出去"）
func _ensure_exit_arrow() -> void:
	if has_node("ExitArrow"):
		return
	var arrow := Polygon2D.new()
	arrow.name = "ExitArrow"
	arrow.polygon = PackedVector2Array([
		Vector2(-12, -18),
		Vector2(-12, 18),
		Vector2(18, 0),
	])
	arrow.color = Color(1, 1, 1, 0.92)
	arrow.z_index = 10
	add_child(arrow)


## 该热点对应的记忆考古关卡号；0 = 不是考古入口。
## 直接问 ArchaeologyTrigger 的映射表（config/archaeology_triggers.json），不硬编码 ID——
## 改了那张表，这里显示的文字自动跟着变。
func _get_archaeology_level() -> int:
	return ArchaeologyTrigger.get_level_for(object_id)


## 该热点在 MemoryAnchorUI 里有没有范本内容（B 写了 anchors.json 才为 true）
func _has_anchor_content() -> bool:
	return MemoryAnchorUI.ANCHOR_MAP.has(object_id)


## 测试期文字注释，方块上方显示。两行——第一行永远是 object_id，第二行是用途：
##   考古   → "ST_ACC_01" / "★考古关卡1"   （金）
##   有范本 → "AP_PHOTO_01" / "●有范本"    （青）
##   出口   → "EXIT_CF" / "→ 咖啡店"        （绿）
##   普通   → "ST_LAMP_01"（只有一行）      （白）
##
## 为什么分两行：单行拼起来会到 261px 宽，而街上相邻点位中心只隔 250px——
## ST_FLOWER_01 和 ST_FLOWER_02 的标签会互相压住 11px（实测）。拆行后宽度 = 两行里较宽的
## 那行（≈130px），横向不再打架。
##
## 方块 100×100 中心即父 Area2D 原点 → 文字水平居中，悬在方块上边缘上方 6px。
## 关掉：把本文件顶部 DEBUG_LABELS 改成 false。
func _ensure_debug_label() -> void:
	if not DEBUG_LABELS or has_node("DebugLabel"):
		return
	var tag := ""
	var color := COLOR_LABEL_PLAIN
	var level := _get_archaeology_level()
	if is_exit:
		color = COLOR_LABEL_EXIT
		tag = "→ " + SCENE_NAMES.get(target_scene, target_scene.get_file().get_basename())
	elif level > 0:
		color = COLOR_LABEL_ARCH
		tag = "★考古关卡" + str(level)
	elif _has_anchor_content():
		color = COLOR_LABEL_ANCHOR
		tag = "●有范本"
	var text := object_id if tag.is_empty() else object_id + "\n" + tag
	var label := Label.new()
	label.name = "DebugLabel"
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 20)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 8)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.z_index = 20
	add_child(label)
	# Node2D 父级下 Control 不会自动布局：按内容最小尺寸定 size 并居中
	label.reset_size()
	label.position = Vector2(
		-label.size.x * 0.5,
		-50.0 - label.size.y - 6.0
	)


## 光标：出口 → 箭头（"可点"提示）；锚点 → 手形（"可拿取/触发"提示）
func _set_cursor(hover: bool) -> void:
	if not hover:
		Input.set_default_cursor_shape(Input.CURSOR_ARROW)
		return
	if is_exit:
		Input.set_default_cursor_shape(Input.CURSOR_ARROW)
	else:
		Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND)
