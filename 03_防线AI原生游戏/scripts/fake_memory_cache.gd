# fake_memory_cache.gd —— 假记忆生成本地缓存层
# 同一 anchor + emotion 确定性生成 3 版变体：truth / neg_distortion / micro_drift
# 负面扭曲后缀从 config/emotion_registry.json 加载；上游 LLM 可用后改 _generate_variants 内部为真实调用

class_name FakeMemoryCache
extends RefCounted

const EMOTION_REGISTRY_PATH := "res://config/emotion_registry.json"
const DEFAULT_NEG_SUFFIX := "\n\n（或许从一开始，我就不该把这件事看得太重。）"

## 缓存键 → 3 版变体数组
var _cache: Dictionary = {}

## 锚点范本数据（从 MemoryAnchorUI.ANCHOR_MAP 引用）
var _anchor_data: Dictionary = {}

## emotion → neg_distort_suffix（运行时从 emotion_registry.json 加载）
var _neg_suffixes: Dictionary = {}


func _init(anchor_map: Dictionary = {}) -> void:
	_anchor_data = anchor_map
	_load_neg_suffixes()


## 取 3 版假记忆 — 同输入多次调用返回同结果（缓存）
func get_variants(anchor_id: String, emotion: String) -> Array:
	var key := "%s:%s" % [anchor_id, emotion]
	if _cache.has(key):
		return _cache[key]
	var variants := _generate_variants(anchor_id, emotion)
	_cache[key] = variants
	return variants


## 判定玩家选的版本是不是真相版
func is_truth(anchor_id: String, emotion: String, player_choice_variant_id: String) -> bool:
	for v in get_variants(anchor_id, emotion):
		if v["variant_id"] == player_choice_variant_id:
			return v["is_truth"]
	return false


func clear_cache() -> void:
	_cache.clear()


# ============================================================================
# 内部
# ============================================================================

func _load_neg_suffixes() -> void:
	var f := FileAccess.open(EMOTION_REGISTRY_PATH, FileAccess.READ)
	if f == null:
		push_warning("[FakeMemoryCache] emotion_registry.json 未找到；使用默认后缀")
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	for key in parsed:
		if key == "_meta":
			continue
		_neg_suffixes[key] = (parsed[key] as Dictionary).get("neg_distort_suffix", DEFAULT_NEG_SUFFIX)


func _generate_variants(anchor_id: String, emotion: String) -> Array:
	var truth_text: String = ""
	if _anchor_data.has(anchor_id):
		truth_text = _anchor_data[anchor_id].get("revealed_text", "")
	else:
		truth_text = "（锚点 %s 不在 anchors.json 中）" % anchor_id

	return [
		{"variant_id": "truth", "text": truth_text, "is_truth": true, "source": "anchors.json"},
		{"variant_id": "neg_distortion", "text": _neg_distort(truth_text, emotion), "is_truth": false, "source": "emotion_registry.json"},
		{"variant_id": "micro_drift", "text": _micro_drift(truth_text, emotion), "is_truth": false, "source": "mock_micro_drift"},
	]


## 负面扭曲：文末追加对方视角的自责式反思（从 emotion_registry.json 查表）
func _neg_distort(truth: String, emotion: String) -> String:
	var suffix: String = _neg_suffixes.get(emotion, DEFAULT_NEG_SUFFIX)
	return truth + suffix


## 微偏真实：把"约定"类词替换为"偶遇"，改变相遇性质
func _micro_drift(truth: String, _emotion: String) -> String:
	var drifted := truth
	drifted = drifted.replace("约定", "偶遇")
	drifted = drifted.replace("约定好", "碰巧")
	drifted = drifted.replace("约好", "碰巧")
	drifted = drifted.replace("约在此", "偶遇在")
	if drifted == truth:
		drifted += "\n\n（其实那天只是巧合。我们其实没约好。）"
	return drifted


func dump_cache() -> Array:
	return _cache.keys()