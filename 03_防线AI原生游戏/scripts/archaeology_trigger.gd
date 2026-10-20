# archaeology_trigger.gd —— 记忆考古正式入口（Autoload 单例）
# 把场景热点接进 MemoryArchaeology.start_level()，取代 F1/F2/F3 调试热键
# （archaeology_ui.gd:385 注：「B 把正式入口接进 start_level() 后，把 DEBUG_HOTKEYS 置 false」）。
#
# 映射表在 config/archaeology_triggers.json（object_id → 关卡号），改数据不用改代码。
#
# 两条触发路径，进任何一条之前都先查同一张表：
#   1) anchor_resolved —— 该锚点在 anchors.json 里有范本卡时走这条：
#      点热点 → 读范本 → 选情感 → 开考古。这是设计上的正路（先回忆起这段记忆，
#      再辨析哪个版本才是真的），玩家的情感选择顺带当作 emotion 传给关卡。
#   2) object_interacted —— 该锚点还没有范本卡时走这条（B 的 anchors.json 尚未收录）：
#      热点点了不该没反应，直接进考古。B 的内容落地后这条自然不再走——
#      判据是 MemoryAnchorUI.ANCHOR_MAP，卡在不在由数据决定，代码里不写死任何 id。
#
# 无 UI，只做信号转接，不占 CanvasLayer 层级。

extends Node

const TRIGGERS_PATH := "res://config/archaeology_triggers.json"

## object_id → 关卡号（1/2/3）
var _triggers: Dictionary = {}

## 已点开范本卡、正在等玩家选情感的考古锚点（空串＝没有待处理的）
var _pending: String = ""


func _load_triggers() -> void:
	var f := FileAccess.open(TRIGGERS_PATH, FileAccess.READ)
	if f == null:
		push_error("[考古入口] 无法打开 %s" % TRIGGERS_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("[考古入口] %s 格式错误（顶层应为对象）" % TRIGGERS_PATH)
		return
	var table = parsed.get("triggers", {})
	if typeof(table) != TYPE_DICTIONARY:
		push_error("[考古入口] %s 缺少 triggers 对象" % TRIGGERS_PATH)
		return
	for key in table:
		_triggers[str(key)] = int(table[key])
	print("[考古入口] 加载 %d 条考古触发映射（来源 %s）" % [_triggers.size(), TRIGGERS_PATH])


# ── 查询接口（供调试 / 测试断言）──

func has_trigger(object_id: String) -> bool:
	return _triggers.has(object_id)


func get_level_for(object_id: String) -> int:
	return int(_triggers.get(object_id, 0))


func get_trigger_count() -> int:
	return _triggers.size()


func get_pending() -> String:
	return _pending


# ── 触发 ──

## 当前是否允许开新关卡。MemoryArchaeology.start_level 自己也会拦，
## 这里先拦一次是为了不发无谓的 warning、也不把 pending 状态搞脏。
func _can_start() -> bool:
	var st: int = MemoryArchaeology.get_state()
	return st == MemoryArchaeology.State.IDLE or st == MemoryArchaeology.State.ENDED


func _start(object_id: String, emotion: String = "") -> void:
	if not _can_start():
		push_warning("[考古入口] 已有考古关卡在进行中，忽略 %s" % object_id)
		return
	var level: int = get_level_for(object_id)
	if level <= 0:
		return
	print("[考古入口] %s → 记忆考古关卡 %d" % [object_id, level])
	MemoryArchaeology.start_level(level, emotion)


# ── 信号消费 ──

func _on_object_interacted(object_id: String) -> void:
	if not has_trigger(object_id):
		return
	if MemoryAnchorUI.ANCHOR_MAP.has(object_id):
		_pending = object_id      # 有范本卡 → 让玩家先读完、选完情感
		return
	_start(object_id)             # 无范本卡 → 直接进考古（B 的内容到位后自然不走这条）


func _on_anchor_resolved(object_id: String, emotion: String) -> void:
	if object_id != _pending:
		return
	_pending = ""
	_start(object_id, emotion)


func _on_scene_changed(_target_path: String) -> void:
	_pending = ""                 # 换场景了，之前点开的那张卡不再算数


# ── 入口（置于末尾：所有被调用的私有函数均已定义）──

func _ready() -> void:
	_load_triggers()
	EventBus.object_interacted.connect(_on_object_interacted)
	EventBus.anchor_resolved.connect(_on_anchor_resolved)
	EventBus.scene_changed.connect(_on_scene_changed)
