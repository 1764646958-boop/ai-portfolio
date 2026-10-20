extends Node
## 场景 1 · 记忆锚点原型(由场景管理框架 SceneManager 加载/卸载)
## 交互链路:点击色块(锚点物品) → 范本浮现 → 情感选项 → 控制台输出选择结果
## 验收标准:点击色块 → 文字浮现 → 点击选项 → 控制台输出选择结果

## 三个情感选项,占位情感基调
## (后续接入 LLM 情感微调 / 记忆五引擎时,替换为模型输出)
const EMOTION_OPTIONS: Array[String] = [
	"平静的怀念",
	"隐隐的愧疚",
	"无法释怀",
]

var _last_item_name: String = ""
var _last_revealed_text: String = ""

@onready var anchor_area: HBoxContainer = %AnchorArea
@onready var memory_label: Label = %MemoryLabel
@onready var option_area: HBoxContainer = %OptionArea
@onready var state_label: Label = %StateLabel


func _ready() -> void:
	_connect_anchors()
	_connect_options()
	reset_flow()
	_register_anchors_to_manager()


## 将本场景独立的锚点物品列表注册给 SceneManager(记忆锚点层预留)
func _register_anchors_to_manager() -> void:
	var anchors: Array[Dictionary] = []
	for child in anchor_area.get_children():
		if child is AnchorItem:
			anchors.append({
				"id": child.name,
				"item_name": child.item_name,
				"revealed_text": child.revealed_text,
			})
	SceneManager.register_anchors(anchors)


## 连接所有锚点物品色块
func _connect_anchors() -> void:
	for child in anchor_area.get_children():
		if child is AnchorItem:
			child.item_clicked.connect(_on_anchor_clicked)


## 连接三个情感选项按钮
func _connect_options() -> void:
	for i in option_area.get_child_count():
		var btn := option_area.get_child(i) as Button
		if btn == null:
			continue
		btn.text = EMOTION_OPTIONS[i]
		btn.pressed.connect(_on_option_pressed.bind(i))


## 重置为初始状态:只有色块可见,文字与选项隐藏
func reset_flow() -> void:
	_last_item_name = ""
	_last_revealed_text = ""
	memory_label.text = ""
	state_label.text = "点击一个色块(锚点物品),唤醒一段记忆范本。"
	for child in option_area.get_children():
		child.visible = false


## 步骤 1→2:点击色块,浮现记忆范本,显示情感选项
func _on_anchor_clicked(item_name: String, revealed_text: String) -> void:
	_last_item_name = item_name
	_last_revealed_text = revealed_text

	print("=== 记忆锚点原型 ===")
	print("[1. 物品交互] 玩家点击了锚点物品:「%s」" % item_name)

	state_label.text = "已唤醒记忆,请选择一个情感选项。"
	memory_label.text = revealed_text
	for child in option_area.get_children():
		child.visible = true


## 步骤 3→4:点击情感选项,控制台输出选择结果
func _on_option_pressed(index: int) -> void:
	var emotion: String = EMOTION_OPTIONS[index]

	print("[2. 文字浮现] 记忆范本:%s" % _last_revealed_text)
	print("[3. 情感选项] 玩家选择了:「%s」" % emotion)
	print("[4. 控制台输出] 锚点解析结果 → 物品=%s | 记忆=%s | 情感=%s"
		% [_last_item_name, _last_revealed_text, emotion])
	print("=== 原型验收:交互链路已跑通 ===")

	# 后续扩展:此处将 (物品, 记忆范本, 情感) 交给 LLM 微调接口 / 记忆五引擎
