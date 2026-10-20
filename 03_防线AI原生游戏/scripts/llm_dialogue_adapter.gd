# llm_dialogue_adapter.gd —— A 的 LLM 单句输出 → C 对话 JSON 适配层
# ---------------------------------------------------------------------------
# 背景：LLMGateway.generate_dialogue 输出的是单句
#       {dialogue_text, warmth, manipulation, helpfulness}
#       而 DialogManager 消费的是对话 JSON
#       {mode, speaker_name, typing_speed, lines[], choices[]}
# 本层负责把前者包装成后者，打通 C↔A 对话链路。
#
# 用法（任意场景脚本中）：
#   var table: Dictionary = LLMDialogueAdapter.generate(
#       "LLM_REPLY_01", "chat_app", "林默", "林默 · 你的AI陪伴",
#       context, npc_character, player_history_summary,
#       [{"text": "「继续听」", "next": ""}],          # 可选，默认无选项
#   )
#   DialogManager.register(table)                      # {dialogue_id: {...}}
#   DialogManager.start("LLM_REPLY_01")
#
# 说明：
#   - dialogue_text 按换行拆成多句，全部变为 AI 发言（speaker="ai"）
#   - warmth/manipulation/helpfulness 附到每句的 meta 字段（UI 可读）
#   - dialogue_text 为空时用占位句，保证对话流程不中断
class_name LLMDialogueAdapter
extends RefCounted

## 打字机默认速度（毫秒/字，与 dialogues_sample.json 一致）
const DEFAULT_TYPING_SPEED := 60
## dialogue_text 为空时的占位句
const FALLBACK_TEXT := "（信号有些模糊……我还在想该怎么开口。）"


## 主入口：直接调用 A 的 LLMGateway.generate_dialogue，把结果包装成对话 JSON
## gateway 可注入（便于测试）；默认取 autoload 全局名 LLMGateway
## 返回 register-ready 结构：{dialogue_id: {mode, speaker_name, typing_speed, lines, choices}}
static func generate(
		dialogue_id: String,
		mode: String,
		npc_character: String,
		speaker_name: String,
		context: String,
		player_history_summary: String,
		choices: Array = [],
		typing_speed: int = DEFAULT_TYPING_SPEED,
		gateway: Node = null
	) -> Dictionary:
	var llm: Node = gateway
	if llm == null:
		llm = _get_autoload("LLMGateway")
	var llm_result: Dictionary = {}
	if llm != null and llm.has_method("generate_dialogue"):
		llm_result = llm.generate_dialogue(context, npc_character, player_history_summary)
	return wrap_llm_result(dialogue_id, mode, npc_character, speaker_name, llm_result, choices, typing_speed)


## 纯转换：把 A 的 LLM 输出字典包装成对话 JSON（不依赖 autoload，可单测）
## llm_result 期望含 dialogue_text / warmth / manipulation / helpfulness
static func wrap_llm_result(
		dialogue_id: String,
		mode: String,
		npc_character: String,
		speaker_name: String,
		llm_result: Dictionary,
		choices: Array = [],
		typing_speed: int = DEFAULT_TYPING_SPEED
	) -> Dictionary:
	var text: String = String(llm_result.get("dialogue_text", "")).strip_edges()
	if text.is_empty():
		text = FALLBACK_TEXT
	var meta: Dictionary = {
		"warmth": llm_result.get("warmth", 0.0),
		"manipulation": llm_result.get("manipulation", 0.0),
		"helpfulness": llm_result.get("helpfulness", 0.0),
	}
	var lines: Array = []
	for raw_line in text.split("\n"):
		var line := String(raw_line).strip_edges()
		if line.is_empty():
			continue
		lines.append({"speaker": "ai", "name": npc_character, "text": line, "meta": meta})
	if lines.is_empty():
		lines.append({"speaker": "ai", "name": npc_character, "text": FALLBACK_TEXT, "meta": meta})
	return {
		dialogue_id: {
			"mode": mode,
			"speaker_name": speaker_name,
			"typing_speed": typing_speed,
			"lines": lines,
			"choices": choices,
		}
	}


static func _get_autoload(name: String) -> Node:
	var tree := Engine.get_main_loop()
	if tree is SceneTree:
		var root: Node = tree.root
		if root != null and root.has_node(name):
			return root.get_node(name)
	return null
