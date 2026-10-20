# test_dialogue.gd —— 对话系统测试入口
# 挂到场景的任意 Node 上，运行后自动加载示例对话并依次演示两套 UI：
#   1) CF_INTRO_01（chat_app 模式）→ 2) VN_TEST_01（visual_novel 模式）
# 用途：验证 DialogManager + 多套 UI 跑通。正式接入后删除或替换。

extends Node

var _vn_started := false


func _ready() -> void:
	DialogManager.load_from_file("res://config/dialogues_sample.json")
	DialogManager.dialogue_ended.connect(_on_ended)
	DialogManager.start("CF_INTRO_01")


func _on_ended() -> void:
	# chat_app 演示结束后，自动接一段 visual_novel
	if _vn_started:
		return
	_vn_started = true
	DialogManager.start("VN_TEST_01")
