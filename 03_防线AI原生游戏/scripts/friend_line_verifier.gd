# friend_line_verifier.gd —— 阶段三「旧友说过的话」匹配器
#
# 作用：判断玩家手动输入的那句话，是否来自他真正见过的真实记忆。
# 语料只装玩家自己看过的内容——已走过的记忆考古关卡真相文本（辨赢辨输都上过屏），
# 不接任何外部知识库。理由与策划稿「幻觉防护 · 不是编的，是选的」同源：
# 玩家能说对的，必须是他真的记得的。
#
# 本地匹配（离线可用，与 FakeMemoryCache 同一套占位约定）：
#   score = containment_weight × 包含度 + bigram_weight × 二元组覆盖率
#   包含度 = 玩家输入在语料条目中的最长公共子串 / 输入长度
#            （玩家给的是短句、语料是整段，所以用不对称的「被包住多少」而非对称相似度）
#   LLM 升级缝：LLMGateway 一旦提供 verify_friend_line(line, corpus) 就直接改走它
#            （语义改写正是二元组比不了、而 LLM 擅长的部分）。当前 LLMGateway 无此
#            方法，has_method 判定为假 → 自动走本地。加了不用改这里。

class_name FriendLineVerifier
extends RefCounted

const DEFAULT_THRESHOLD := 0.55
const DEFAULT_CONTAINMENT_WEIGHT := 0.7
const DEFAULT_BIGRAM_WEIGHT := 0.3
const DEFAULT_MIN_INPUT_CHARS := 4

var threshold: float = DEFAULT_THRESHOLD
var containment_weight: float = DEFAULT_CONTAINMENT_WEIGHT
var bigram_weight: float = DEFAULT_BIGRAM_WEIGHT
var min_input_chars: int = DEFAULT_MIN_INPUT_CHARS

## [{id, text, source, norm}]
var _entries: Array = []
## id → true，避免同一条重复入语料
var _seen: Dictionary = {}


func _init(p_threshold: float = DEFAULT_THRESHOLD,
		p_containment_weight: float = DEFAULT_CONTAINMENT_WEIGHT,
		p_bigram_weight: float = DEFAULT_BIGRAM_WEIGHT,
		p_min_input_chars: int = DEFAULT_MIN_INPUT_CHARS) -> void:
	threshold = p_threshold
	containment_weight = p_containment_weight
	bigram_weight = p_bigram_weight
	min_input_chars = p_min_input_chars


# ============================================================================
# 语料库
# ============================================================================

## 收一条真实记忆。id 相同则忽略；文本过短（<8 字）也忽略，避免脏数据拉低匹配质量。
func add_truth(id: String, text: String, source: String = "") -> bool:
	if id.is_empty() or _seen.has(id):
		return false
	var norm := _normalize(text)
	if norm.length() < 8:
		return false
	_seen[id] = true
	_entries.append({"id": id, "text": text, "source": source, "norm": norm})
	return true


## 从 MemoryAnchorUI.ANCHOR_MAP 批量载入（只取指定前缀的锚点）
func seed_from_anchor_map(anchor_map: Dictionary, id_prefix: String = "MA_") -> int:
	var added := 0
	for key in anchor_map:
		if not String(key).begins_with(id_prefix):
			continue
		var data = anchor_map[key]
		if typeof(data) != TYPE_DICTIONARY:
			continue
		if add_truth(String(key), String(data.get("revealed_text", "")), "anchors.json"):
			added += 1
	return added


func has_entry(id: String) -> bool:
	return _seen.has(id)


func corpus_size() -> int:
	return _entries.size()


func corpus_ids() -> Array:
	var ids: Array = []
	for e in _entries:
		ids.append(e["id"])
	return ids


func corpus_texts() -> Array:
	var texts: Array = []
	for e in _entries:
		texts.append(e["text"])
	return texts


func clear() -> void:
	_entries.clear()
	_seen.clear()


## 给 UI 的提示片段：取该条目前 cue_chars 个正文字符（cue_chars<=0 返回空串＝不给提示）
func cue_for(id: String, cue_chars: int) -> String:
	if cue_chars <= 0:
		return ""
	for e in _entries:
		if e["id"] == id:
			var t: String = e["text"]
			return t.substr(0, mini(cue_chars, t.length()))
	return ""


# ============================================================================
# 判定
# ============================================================================

## 返回 {matched, score, best_id, best_source, containment, bigram, method, reason}
func verify(line: String) -> Dictionary:
	var out := {
		"matched": false, "score": 0.0, "best_id": "", "best_source": "",
		"containment": 0.0, "bigram": 0.0, "method": "local", "reason": "",
	}
	var norm := _normalize(line)
	if norm.length() < min_input_chars:
		out["reason"] = "输入太短（至少 %d 字）" % min_input_chars
		return out
	if _entries.is_empty():
		out["reason"] = "语料为空——玩家还没见过任何真实记忆"
		return out

	# LLM 优先（有则用，无则本地）
	var llm := _llm_verify(line)
	if not llm.is_empty():
		out["method"] = "llm"
		out["matched"] = bool(llm.get("matched", false))
		out["score"] = float(llm.get("score", 0.0))
		out["best_id"] = String(llm.get("best_id", ""))
		out["best_source"] = String(llm.get("reason", ""))
		return out

	var best_score := 0.0
	var best_id := ""
	var best_source := ""
	var best_containment := 0.0
	var best_bigram := 0.0
	for e in _entries:
		var entry_norm: String = e["norm"]
		var lcs := _lcs_len(norm, entry_norm)
		var containment := float(lcs) / float(norm.length())
		var bigram := _bigram_ratio(norm, entry_norm)
		var score := containment_weight * containment + bigram_weight * bigram
		if score > best_score:
			best_score = score
			best_id = e["id"]
			best_source = e["source"]
			best_containment = containment
			best_bigram = bigram

	out["score"] = best_score
	out["best_id"] = best_id
	out["best_source"] = best_source
	out["containment"] = best_containment
	out["bigram"] = best_bigram
	out["matched"] = best_score >= threshold
	if out["matched"]:
		out["reason"] = "命中 %s（%.2f ≥ %.2f）" % [best_id, best_score, threshold]
	else:
		out["reason"] = "最高 %.2f < 阈值 %.2f（最接近：%s）" % [best_score, threshold, best_id]
	return out


## LLM 升级缝：LLMGateway 提供 verify_friend_line 后自动启用；拿不到结果一律回退本地。
func _llm_verify(line: String) -> Dictionary:
	if not LLMGateway.has_method("verify_friend_line"):
		return {}
	var res = LLMGateway.call("verify_friend_line", line, corpus_texts())
	if typeof(res) != TYPE_DICTIONARY or res.is_empty():
		return {}
	return res


# ============================================================================
# 字符串工具
# ============================================================================

## 只保留 CJK + 字母数字 并转小写——标点/空白/换行不参与匹配
func _normalize(s: String) -> String:
	var out := ""
	for i in range(s.length()):
		var c := s[i]
		if _keep_char(c.unicode_at(0)):
			out += c.to_lower()
	return out


func _keep_char(code: int) -> bool:
	if code >= 0x4E00 and code <= 0x9FFF:      # CJK 统一表意
		return true
	if code >= 0x3400 and code <= 0x4DBF:      # CJK 扩展 A
		return true
	if code >= 0xF900 and code <= 0xFAFF:      # CJK 兼容表意
		return true
	if code >= 0x30 and code <= 0x39:          # 0-9
		return true
	if code >= 0x41 and code <= 0x5A:          # A-Z
		return true
	if code >= 0x61 and code <= 0x7A:          # a-z
		return true
	return false


## 最长公共子串长度（滚动两行 DP；只关心长度，不回溯内容）
func _lcs_len(a: String, b: String) -> int:
	var n := a.length()
	var m := b.length()
	if n == 0 or m == 0:
		return 0
	var prev := PackedInt32Array()
	prev.resize(m + 1)
	var cur := PackedInt32Array()
	cur.resize(m + 1)
	var best := 0
	for i in range(1, n + 1):
		for j in range(1, m + 1):
			if a[i - 1] == b[j - 1]:
				cur[j] = prev[j - 1] + 1
				if cur[j] > best:
					best = cur[j]
		# 交换后 cur 是上一轮的 prev，必须清零再进下一轮
		var tmp := prev
		prev = cur
		cur = tmp
		for j in range(m + 1):
			cur[j] = 0
	return best


## 输入的二元组有多大比例在语料条目里出现过（改写顺序/夹杂其他字也能给分）
func _bigram_ratio(needle: String, hay: String) -> float:
	if needle.length() < 2:
		return 1.0 if hay.contains(needle) else 0.0
	var total := 0
	var hit := 0
	for i in range(needle.length() - 1):
		total += 1
		if hay.contains(needle.substr(i, 2)):
			hit += 1
	return 0.0 if total == 0 else float(hit) / float(total)
