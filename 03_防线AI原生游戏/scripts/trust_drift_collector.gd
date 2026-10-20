# trust_drift_collector.gd —— 信任偏移信号收集器（Autoload 单例）
# 订阅 EventBus.anchor_resolved → 记录每个锚点交互事件到内存
# score 和 scene_counts 在 _on_anchor_resolved 增量更新，O(1) 查询
# 权重从 config/emotion_registry.json 加载

extends Node

const EMOTION_REGISTRY_PATH := "res://config/emotion_registry.json"

## emotion → weight
var _emotion_weight: Dictionary = {}

## 增量 score：_on_anchor_resolved 时累加
var _cached_score: float = 0.0

## 增量场景计数：abbrev → count
var _scene_counts: Dictionary = {}

## 历史事件（保留以便回放/调试）
var _history: Array[Dictionary] = []


func _ready() -> void:
	_load_emotion_weights()
	EventBus.anchor_resolved.connect(_on_anchor_resolved)
	print("[TrustDrift] 启动；权重表 %d 条" % _emotion_weight.size())


func _load_emotion_weights() -> void:
	var f := FileAccess.open(EMOTION_REGISTRY_PATH, FileAccess.READ)
	if f == null:
		push_warning("[TrustDrift] emotion_registry.json 未找到；weight 默认 0")
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	for key in parsed:
		if key == "_meta":
			continue
		_emotion_weight[key] = float((parsed[key] as Dictionary).get("weight", 0.0))


func _on_anchor_resolved(object_id: String, emotion: String) -> void:
	# 预设路径：emotion 查表得 weight
	var weight := float(_emotion_weight.get(emotion, 0.0))
	_record_event(object_id, emotion, weight, "", 0.0)


## 自由输入路径：LLM 直接给出 magnitude，不再经 emotion 查表
func record_drift(object_id: String, magnitude: float, drift_direction: String = "", confidence: float = 0.0) -> void:
	_record_event(object_id, "[free_input]", magnitude, drift_direction, confidence)


func _record_event(object_id: String, emotion: String, score_delta: float, drift_direction: String, confidence: float) -> void:
	var event: Dictionary = {
		"object_id": object_id,
		"emotion": emotion,
		"timestamp": Time.get_unix_time_from_system(),
		"drift_direction": drift_direction,
		"drift_magnitude": score_delta,
		"drift_confidence": confidence,
	}
	_history.append(event)
	_cached_score += score_delta
	# object_id 前 2 字符是场景缩写（CF/CR/ST/AP）
	if object_id.length() >= 2:
		var abbrev := object_id.substr(0, 2)
		_scene_counts[abbrev] = int(_scene_counts.get(abbrev, 0)) + 1
	var label := "[free]" if emotion == "[free_input]" else emotion
	print("[TrustDrift] 记录 %d: %s %s | score=%.1f" % [_history.size(), object_id, label, _cached_score])


## 累计偏移值（O(1)）
func get_trust_score() -> float:
	return _cached_score


## 信任等级：LOW(<3) / MEDIUM(3~7) / HIGH(>=7)
func get_trust_tier() -> String:
	var s := _cached_score
	if s >= 7.0:
		return "HIGH_TRUST"
	elif s >= 3.0:
		return "MEDIUM_TRUST"
	else:
		return "LOW_TRUST"


## 按场景缩写统计交互次数（O(1)）
func count_by_scene(scene_abbrev: String) -> int:
	return int(_scene_counts.get(scene_abbrev, 0))


## 总交互次数 — 用于名字生成触发（≥15 锚点）
func get_total_anchor_count() -> int:
	return _history.size()


func dump_history() -> Array[Dictionary]:
	return _history.duplicate(true)