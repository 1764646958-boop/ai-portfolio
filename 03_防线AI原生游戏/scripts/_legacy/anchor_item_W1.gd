class_name AnchorItem
extends ColorRect
## 记忆锚点原型:一个可点击的"锚点物品"占位色块。
## 玩家点击 → 发出 item_clicked 信号,携带物品名与范本浮现文字。

## 物品名(占位;后续替换为美术/物品配置)
@export var item_name: String = "未命名物品"
## 点击后浮现的"记忆范本"文字(占位;后续由 LLM 记忆生成引擎输出)
@export var revealed_text: String = "(没有浮现任何记忆)"

signal item_clicked(item_name: String, revealed_text: String)

const HOVER_MODULATE := Color(1, 1, 1, 0.72)


func _ready() -> void:
	# ColorRect 默认不接收点击,必须设为 STOP 才能触发 gui_input
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = item_name
	mouse_entered.connect(_on_mouse_entered)
	mouse_exited.connect(_on_mouse_exited)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton \
			and event.button_index == MOUSE_BUTTON_LEFT \
			and event.pressed:
		item_clicked.emit(item_name, revealed_text)


func _on_mouse_entered() -> void:
	modulate = HOVER_MODULATE


func _on_mouse_exited() -> void:
	modulate = Color.WHITE
