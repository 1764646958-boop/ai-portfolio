# dialog_manager.gd —— 对话系统管理器（Autoload 单例）
# 职责：读对话 JSON → 管理对话流程（下一句 / 选项 / 结束）
# 配置：项目设置 → Autoload → 添加本文件，节点名 DialogManager
#
# 设计（延续 EventBus 的解耦模式）：
#   DialogManager 是"导演"，只发信号；四套 UI 是"演员"，订阅信号自己渲染。
#   UI 在 dialogue_started 时按 data.mode 判断是否激活自己。

extends Node

# ── 信号（UI 订阅）──
signal dialogue_started(data: Dictionary)                    # 一段对话开始，data 含 mode 等
signal line_shown(speaker: String, name: String, text: String)  # 显示一句
signal choices_shown(choices: Array)                         # 显示选项 [{text, next}]
signal dialogue_ended                                        # 对话结束

# ── 状态机 ──
enum State { IDLE, SHOWING, CHOOSING, ENDED }
var _state: int = State.IDLE

var dialogues: Dictionary = {}   # dialogue_id -> data（所有已加载对话）
var current: Dictionary = {}     # 当前对话
var _line_index: int = 0


## 从 JSON 文件加载对话表（path 形如 "res://config/dialogues_sample.json"）
func load_from_file(path: String) -> void:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("DialogManager: 无法打开对话文件 %s" % path)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("DialogManager: JSON 格式错误（顶层应为对象）%s" % path)
		return
	register(parsed)


## 注册一组对话（可直接传字典，便于测试/运行时生成）
func register(data: Dictionary) -> void:
	# 支持两种结构：{"dialogues": {id: {...}}} 或 {id: {...}}
	var src: Dictionary = data.get("dialogues", data)
	for id in src:
		dialogues[id] = src[id]


## 开始一段对话（dialogue_id 形如 "CF_INTRO_01"）
func start(dialogue_id: String) -> void:
	if not dialogues.has(dialogue_id):
		push_error("DialogManager: 找不到对话 %s" % dialogue_id)
		return
	current = dialogues[dialogue_id]
	_line_index = 0
	_state = State.SHOWING
	dialogue_started.emit(current)
	_show_line()


## 推进到下一句（玩家点击 / 按空格时调用）。仅在 SHOWING 状态有效。
func advance() -> void:
	if _state != State.SHOWING:
		return
	_line_index += 1
	var lines: Array = current.get("lines", [])
	if _line_index < lines.size():
		_show_line()
	else:
		_show_choices_or_end()


## 玩家选择某个选项（index 从 0 开始）。仅在 CHOOSING 状态有效。
func select_choice(index: int) -> void:
	if _state != State.CHOOSING:
		return
	var choices: Array = current.get("choices", [])
	if index < 0 or index >= choices.size():
		return
	var next_id: String = choices[index].get("next", "")
	if next_id.is_empty():
		end()
	else:
		start(next_id)


## 结束当前对话
func end() -> void:
	if _state == State.IDLE:
		return
	current = {}
	_line_index = 0
	_state = State.IDLE
	dialogue_ended.emit()


func _show_line() -> void:
	var line: Dictionary = current.get("lines", [])[_line_index]
	line_shown.emit(
		line.get("speaker", "ai"),
		line.get("name", ""),
		line.get("text", "")
	)


func _show_choices_or_end() -> void:
	var choices: Array = current.get("choices", [])
	if choices.is_empty():
		_state = State.ENDED
		dialogue_ended.emit()
	else:
		_state = State.CHOOSING
		choices_shown.emit(choices)
