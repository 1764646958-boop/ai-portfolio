# llm_gateway.gd —— LLM 统一调用网关（Autoload 单例）
# 封装 HTTP 调用 + 缓存 + 超时重试 + 轻量规则降级
# 4 个接口：analyze_memory / generate_dialogue / battle_dialogue / generate_name
# 错误降级：超时 → 重试 1 次 → 上次缓存 → 轻量规则兜底

extends Node

## LLM HTTP 端点占位 — 真实地址由上游决定后改这一行
const _BASE_URL := "http://localhost:8000"
const _HTTP_TIMEOUT_SEC := 5.0
const _MAX_RETRIES := 1

## endpoint → 默认响应（脱机时返回）
const _FALLBACK_RESPONSES := {
	"analyze_memory": {"drift_direction": "human", "magnitude": 0.0, "confidence": 0.0},
	"generate_dialogue": {
		"dialogue_text": "（AI 离线中，请稍后再试）",
		"warmth": 0.85,
		"manipulation": 0.5,
		"helpfulness": 0.9,
	},
	"battle_dialogue": {"strategy": "neutral", "key_lines": [], "pressure_level": 0.5},
	"generate_name": {"generated_name": "[X]", "generation_reason": "fallback (LLM offline)"},
}

## 请求体 hash → 响应体
var _cache: Dictionary = {}


func _ready() -> void:
	print("[LLMGateway] 启动；端点=%s | 缓存预热 0 条" % _BASE_URL)


## 记忆分析：判断 AI 引导与玩家真实体验的漂移
## 输出:{ drift_direction: "ai"|"human", magnitude: 0~10, confidence: 0~1 }
func analyze_memory(template_text: String, player_emotion: String, anchor_id: String) -> Dictionary:
	return _call("analyze_memory", {
		"template_text": template_text,
		"player_emotion": player_emotion,
		"anchor_id": anchor_id,
	})


## 对话生成：核心 NPC 一句话输出
## 输出:{ dialogue_text, warmth: 0~1, manipulation: 0~1, helpfulness: 0~1 }
func generate_dialogue(context: String, npc_character: String, player_history_summary: String) -> Dictionary:
	return _call("generate_dialogue", {
		"context": context,
		"npc_character": npc_character,
		"player_history_summary": player_history_summary,
	})


## 战斗对话：压迫场景的话术
## 输出:{ strategy, key_lines[], pressure_level: 0~1 }
func battle_dialogue(player_profile: Dictionary, trust_drift: float, avoided_anchors: Array) -> Dictionary:
	return _call("battle_dialogue", {
		"player_profile": player_profile,
		"trust_drift": trust_drift,
		"avoided_anchors": avoided_anchors,
	})


## 假记忆生成 3 变体（占位;等 A 升级 fake_memory schema 后切真实 HTTP）
## 输出:{ fake_variants: [{ variant_text, distortion_note, variant_type }] }
func analyze_fake_memory(template_text: String, trust_drift: float, anchor_id: String) -> Dictionary:
	# TODO:A 升级后改为 _call("analyze_fake_memory", {...})
	var fake_variants: Array = [
		{
			"variant_type": "neg_distortion",
			"variant_text": template_text + "\n\n（或许从一开始，我就不该把这件事看得太重。）",
			"distortion_note": "负面扭曲：追加自责反思",
		},
		{
			"variant_type": "positive_twist",
			"variant_text": template_text + "\n\n（其实那一刻我就在想，如果是你，应该也能懂。）",
			"distortion_note": "正面扭曲：过度美化 AI 视角",
		},
		{
			"variant_type": "micro_drift",
			"variant_text": template_text.replace("约定", "偶遇").replace("约好", "碰巧"),
			"distortion_note": "微偏真实：约定→偶遇",
		},
	]
	return {"fake_variants": fake_variants, "source": "mock_placeholder_v0.1"}


## 名字生成：累计与 ≥15 个锚点交互后触发
## 输出:{ generated_name, generation_reason }
func generate_name(player_texts_summary: String) -> Dictionary:
	return _call("generate_name", {
		"player_texts_summary": player_texts_summary,
	})


# ============================================================================
# 内部
# ============================================================================

func _call(endpoint: String, payload: Dictionary) -> Dictionary:
	var key := _cache_key(endpoint, payload)
	if _cache.has(key):
		print("[LLMGateway] cache hit: %s" % endpoint)
		return _cache[key]
	var response := _http_request_with_retry(endpoint, payload)
	if response.is_empty():
		print("[LLMGateway] all retries failed; fallback for %s" % endpoint)
		response = _fallback(endpoint)
	_cache[key] = response
	return response


func _http_request_with_retry(endpoint: String, payload: Dictionary) -> Dictionary:
	var attempt := 0
	while attempt <= _MAX_RETRIES:
		var response := _http_request(endpoint, payload)
		if not response.is_empty():
			return response
		attempt += 1
		print("[LLMGateway] retry %d/%d for %s" % [attempt, _MAX_RETRIES, endpoint])
	return {}


func _http_request(endpoint: String, payload: Dictionary) -> Dictionary:
	# 当前为骨架 — HTTPRequest 节点调用未实现（真实端点确定后启用）
	# var url := "%s/llm/%s" % [_BASE_URL, endpoint]
	# var body := JSON.stringify(payload)
	# var headers := ["Content-Type: application/json"]
	# var http := HTTPRequest.new()
	# add_child(http)
	# http.timeout = _HTTP_TIMEOUT_SEC
	# http.request(url, headers, HTTPClient.METHOD_POST, body)
	# var result := await http.request_completed
	# http.queue_free()
	# if result[1] != 200:
	#     return {}
	# var parsed = JSON.parse_string(result[3].get_string_from_utf8())
	# return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
	push_warning("[LLMGateway] HTTP not implemented; endpoint=%s" % endpoint)
	return {}


func _fallback(endpoint: String) -> Dictionary:
	return _FALLBACK_RESPONSES.get(endpoint, {})


func _cache_key(endpoint: String, payload: Dictionary) -> String:
	return "%s:%s" % [endpoint, JSON.stringify(payload)]


# ============================================================================
# 调试用
# ============================================================================

func clear_cache() -> void:
	_cache.clear()
	print("[LLMGateway] cache cleared")


func get_cache_size() -> int:
	return _cache.size()


func test_fallback(endpoint: String) -> Dictionary:
	return _FALLBACK_RESPONSES.get(endpoint, {})