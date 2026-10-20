# _screenshot_capture.gd —— 临时截图脚本（验证 visual_novel UI）
# 挂在 _screenshot.tscn，运行后自动加载对话并按时间点截多张图：
#   t=0.4s  : 第一句打字中（半截字）
#   t=1.4s  : 第一句完成 + 右下三角出现
#   t=2.4s  : 第二句进行中（验证下一段时三角隐藏）
#   t=4.0s  : 对话结束 + 感想面板淡入
#   t=4.8s  : 感想面板完全显示
# 截图存到 res://_screenshots/

extends Node

const SHOT_DIR := "res://_screenshots/"
const SHOTS := [
	{"t": 0.4, "label": "01_typing"},
	{"t": 1.4, "label": "02_done_with_indicator"},
	{"t": 2.4, "label": "03_next_line_typing"},
	{"t": 4.0, "label": "04_reflection_fadein"},
	{"t": 4.8, "label": "05_reflection_full"},
]
var _next_shot := 0
var _elapsed := 0.0


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SHOT_DIR))
	DialogManager.load_from_file("res://config/dialogues_sample.json")
	DialogManager.dialogue_ended.connect(_on_dialogue_ended)
	DialogManager.start("VN_TEST_01")
	set_process(true)


func _process(delta: float) -> void:
	_elapsed += delta
	while _next_shot < SHOTS.size() and _elapsed >= SHOTS[_next_shot]["t"]:
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var path := "%sui_vn_%s.png" % [SHOT_DIR, SHOTS[_next_shot]["label"]]
		img.save_png(path)
		print("[shot] ", path)
		_next_shot += 1
	if _next_shot >= SHOTS.size():
		# 多等一帧让最后截图落盘
		await get_tree().process_frame
		get_tree().quit()


func _on_dialogue_ended() -> void:
	pass  # 时间由 _process 推进