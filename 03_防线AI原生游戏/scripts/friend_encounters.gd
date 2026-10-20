# friend_encounters.gd —— 旧友「偶遇」事件调度（Autoload 单例）
# 职责：监听场景切换，按剧情顺序触发旧友偶遇事件（visual_novel 对话）。
# 文案在 config/friend_encounters.json（与 A 大纲 1.4 / 3.2 对齐；ENC_03 为 W3 新增）。
#
# 触发规则（事件队列，任意探索顺序都不会错过）：
#   进入场景时，若该场景有待触发事件且其前置事件已完成 → 触发（每场景每事件一次）。
#   ENC_01 街道转角剪影      → street.tscn    （A 大纲 1.4：无台词，系统文字）
#   ENC_02 校园小路正式出场   → classroom.tscn （A 大纲 3.2 台词 + 3.3 AI 翻译）
#   ENC_03 宿舍楼下浇水       → dormitory.tscn （W3 原创，呼应 DM_PLANT_01 与 AI 推送提示）
#
# 依赖：DialogManager、EventBus 已注册为 Autoload。

extends Node

const DIALOGUE_FILE := "res://config/friend_encounters.json"

## 事件 → 前置事件（"" 表示无前置）
const SEQUENCE := {
	"ENC_01": "",
	"ENC_02": "ENC_01",
	"ENC_03": "ENC_02",
}

## 场景路径 → 该场景负责的事件
const SCENE_MAP := {
	"res://scenes/street.tscn": "ENC_01",
	"res://scenes/classroom.tscn": "ENC_02",
	"res://scenes/dormitory.tscn": "ENC_03",
}

var _pending := []   # [{scene, id}] 未触发事件（按解锁顺序消费）
var _fired := {}     # dialogue_id -> true（已触发，防重复）


func _ready() -> void:
	DialogManager.load_from_file(DIALOGUE_FILE)
	EventBus.scene_changed.connect(_on_scene_changed)
	for scene in SCENE_MAP:
		_pending.append({"scene": scene, "id": SCENE_MAP[scene]})


func _on_scene_changed(target_path: String) -> void:
	for i in range(_pending.size()):
		var entry: Dictionary = _pending[i]
		if entry["scene"] != target_path:
			continue
		var prereq: String = SEQUENCE[entry["id"]]
		if prereq != "" and not _fired.has(prereq):
			continue   # 前置未完成 → 保留在队列，下次进入再触发
		_pending.remove_at(i)
		_fired[entry["id"]] = true
		# 延迟到 SceneManager 淡入结束（0.3s 黑幕）后再开始，避免盖在黑幕里
		get_tree().create_timer(0.4).timeout.connect(func() -> void:
			DialogManager.start(entry["id"])
		)
		return   # 每次进入场景至多触发一个事件
