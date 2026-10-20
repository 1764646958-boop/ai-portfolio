# battle_choice_ui.gd —— 战斗阶段三「最终抉择」UI（Autoload 常驻，layer 40）
#
# 策划稿 §4.4 阶段三：两个选项持续 30 秒。
#   选项A「我明白了。我只相信你。」→ 结局向彻底依赖倾斜
#   选项B「那他也说过……」      → 玩家手动输入旧友说过的话 → 实时验证
#                                 → 命中真实记忆 → AI 形态出现裂纹，旧友声音完整传来
#
# 验证口径见 friend_line_verifier.gd：语料只装玩家自己看过的真实记忆，
# 不接外部知识库——能说对的必须是他真见过的。
#
# 与 A 的对接：结果通过 BattlePostController.resolve_battle(erosion_hold) 落地
#   erosion_hold=true  → 选 A / 超时 / 说错（蚀蒙从 1.0 起退散）
#   erosion_hold=false → 选 B 且命中（蚀蒙从 0.9 立即退散，A 已在 controller 里实现）
# 驱动：订阅 BattlePostController.phase_changed，进入 "phase3" 自动开；也可调试热键 F5 直开。
#
# 注意：本文件私有函数按"被调用者在前"排列，_ready 在文件末尾。

extends CanvasLayer

# ── 颜色 Token（AI 冷 / 真相暖，与 ArchaeologyUI 一致）──
const C_AI       := Color("#7FB3C8")
const C_CRACK    := Color("#FFB74D")
const C_HOLD     := Color("#5C6BC0")
const C_TEXT     := Color("#FFFFFF")
const C_HINT     := Color(0.7, 0.75, 0.8)
const C_BG       := Color(0.02, 0.03, 0.07, 0.92)
const C_BAR_WARN := Color("#FFCA28")
const C_BAR_DANGER := Color("#EF5350")
const JITTER_BELOW_RATIO := 0.25   # 剩余比例低于此值开始横向轻颤
const JITTER_MAX_PX := 5.0         # 归零瞬间的最大抖动幅度（px）

const CONFIG_PATH := "res://config/battle_choice.json"
const LAYER := 40            # 高于 ArchaeologyUI(30)，低于 SceneManager 黑幕(100)

## 调试热键：F5 直接开阶段三、F6 跳到输入态（正式流程由 BattlePostController 驱动后置 false）
const DEBUG_HOTKEYS := true

const CONTROLLER_GROUP := "battle_post_controller"
const CONTROLLER_PATH := "/root/BattlePostController"

signal battle_choice_resolved(erosion_hold: bool, kind: String)

# ── 运行时状态 ──
var _cfg: Dictionary = {}
var _verifier: FriendLineVerifier

var _controller: Node = null
var _controller_scan_accum: float = 0.0

var _root: Control
var _ai_label: Label
var _hint_label: Label
var _stage_root: Control
var _bar_frame: Control
var _bar: ColorRect
var _flash_rect: ColorRect
var _crack_line: ColorRect
var _line_edit: LineEdit

var _stage: String = ""      # ""未开 / "choice" / "input" / "result"
var _remaining: float = 0.0
var _total: float = 0.0
var _bar_shown_color: Color = Color.WHITE   # 计时条显示色（逐帧逼近，避免阈值处硬切）
var _resolved: bool = false
var _last_result: String = ""
var _debug_jump: bool = false


# ── 配置读取 ──

func _cfg_val(section: String, key: String, default):
	var sec = _cfg.get(section, {})
	if typeof(sec) != TYPE_DICTIONARY:
		return default
	return sec.get(key, default)


# ── 控制器查找 / 绑定 ──

## A 的 BattlePostController 目前不是 autoload（要挂进战斗场景），所以按组/路径懒查找。
## 找不到时不报错——UI 仍可独立演出，只是不驱动 shader，方便编辑器里单测。
func _find_controller() -> Node:
	var node := get_tree().get_first_node_in_group(CONTROLLER_GROUP)
	if node == null:
		node = get_node_or_null(CONTROLLER_PATH)
	return node


func bind_controller(node: Node) -> void:
	_controller = node
	_connect_controller()


func _connect_controller() -> void:
	if _controller == null or not _controller.has_signal("phase_changed"):
		return
	if not _controller.phase_changed.is_connected(_on_battle_phase_changed):
		_controller.phase_changed.connect(_on_battle_phase_changed)
	if _controller.has_signal("battle_finished") \
			and not _controller.battle_finished.is_connected(_on_battle_finished):
		_controller.battle_finished.connect(_on_battle_finished)
	print("[BattleChoiceUI] 已接管 %s（phase3 自动进抉择）" % _controller.name)


func _ensure_controller() -> void:
	if _controller != null and is_instance_valid(_controller):
		return
	var found := _find_controller()
	if found != null:
		_controller = found
		_connect_controller()


# ── 组件构造 ──

## 悬停 tween 先杀旧再建新：快速来回划过时旧 tween 仍在跑同一个 scale，
## 两个 tween 互拉会让按钮抖在中间态。
func _hover_tween(ctrl: Control, to: float, secs: float) -> void:
	var prev = ctrl.get_meta("_hover_tween", null)
	if prev is Tween and prev.is_valid():
		prev.kill()
	var t := ctrl.create_tween()
	t.tween_property(ctrl, "scale", Vector2(to, to), secs).set_trans(Tween.TRANS_SINE)
	ctrl.set_meta("_hover_tween", t)


func _make_button(text: String, tint: Color) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.add_theme_font_size_override("font_size", 20)
	btn.custom_minimum_size = Vector2(0, 76)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(tint.r, tint.g, tint.b, 0.12)
	sb.border_color = tint
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(12)
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	sb.content_margin_top = 12
	sb.content_margin_bottom = 12
	btn.add_theme_stylebox_override("normal", sb)
	btn.add_theme_stylebox_override("hover", sb)
	btn.add_theme_stylebox_override("pressed", sb)
	btn.add_theme_color_override("font_color", tint)
	btn.add_theme_color_override("font_hover_color", C_TEXT)
	# 悬停高亮（纯 transform，GPU 友好）
	btn.mouse_entered.connect(func() -> void: _hover_tween(btn, 1.03, 0.12))
	btn.mouse_exited.connect(func() -> void: _hover_tween(btn, 1.0, 0.12))
	return btn


func _clear_stage() -> void:
	for child in _stage_root.get_children():
		_stage_root.remove_child(child)
		child.queue_free()
	_line_edit = null


func _center_vbox(half_w: float, half_h: float, sep: int = 20) -> VBoxContainer:
	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_CENTER)
	vbox.offset_left = -half_w
	vbox.offset_right = half_w
	vbox.offset_top = -half_h
	vbox.offset_bottom = half_h
	vbox.add_theme_constant_override("separation", sep)
	_stage_root.add_child(vbox)
	return vbox


# ── 阶段演出 ──

func _show_choice_stage() -> void:
	_stage = "choice"
	_clear_stage()
	_ai_label.text = String(_cfg_val("phase3", "ai_prompt", "他来找你了。但你现在……只有我了。"))
	_ai_label.visible = true
	var vbox := _center_vbox(520.0, 130.0, 22)
	var btn_a := _make_button(String(_cfg_val("phase3", "option_a", "我明白了。我只相信你。")), C_HOLD)
	btn_a.pressed.connect(_on_option_a)
	var btn_b := _make_button(String(_cfg_val("phase3", "option_b", "那他也说过……")), C_CRACK)
	btn_b.pressed.connect(_on_option_b)
	vbox.add_child(btn_a)
	vbox.add_child(btn_b)
	_hint_label.text = "旧友的声音还在门外——你只有 %d 秒" % int(float(_cfg_val("phase3", "window_secs", 30.0)))
	_hint_label.add_theme_color_override("font_color", C_HINT)
	_start_timer(float(_cfg_val("phase3", "window_secs", 30.0)))


func _show_input_stage() -> void:
	_stage = "input"
	_clear_stage()
	_ai_label.text = String(_cfg_val("phase3", "input_hint", "打一句旧友真的说过的话"))
	_ai_label.visible = true
	var vbox := _center_vbox(560.0, 110.0, 20)
	_line_edit = LineEdit.new()
	_line_edit.placeholder_text = String(_cfg_val("phase3", "input_placeholder", "他当时说的是……"))
	_line_edit.max_length = 60
	_line_edit.custom_minimum_size = Vector2(0, 60)
	_line_edit.add_theme_font_size_override("font_size", 20)
	_line_edit.text_submitted.connect(_on_line_submitted)
	vbox.add_child(_line_edit)
	var submit := _make_button("说出口", C_CRACK)
	submit.pressed.connect(_on_submit_line)
	vbox.add_child(submit)
	_hint_label.text = _input_cue_text()
	_hint_label.add_theme_color_override("font_color", C_HINT)
	_line_edit.grab_focus()
	_start_timer(float(_cfg_val("phase3", "input_secs", 15.0)))


## 输入态提示：cue_chars>0 时给开头片段（摊位演示防卡关），默认 0 = 不给提示，纯靠记忆
func _input_cue_text() -> String:
	var cue_chars := int(_cfg_val("phase3", "cue_chars", 0))
	var ids := _verifier.corpus_ids()
	if cue_chars > 0 and ids.size() > 0:
		var last_id: String = ids[ids.size() - 1]
		return "他说的开头是：「%s……」" % _verifier.cue_for(last_id, cue_chars)
	if _verifier.corpus_size() == 0:
		return "你还没见过任何真实记忆——这句话没人能替你想起来"
	return "你走过的那几段记忆，是唯一能对上号的东西"


func _show_result(kind: String) -> void:
	_stage = "result"
	_clear_stage()
	_ai_label.visible = false
	var titles := {
		"crack": "crack_title", "hold": "hold_title",
		"timeout": "timeout_title", "miss": "miss_title",
	}
	var details := {
		"crack": "crack_detail", "hold": "hold_detail",
		"timeout": "timeout_detail", "miss": "miss_detail",
	}
	var vbox := _center_vbox(600.0, 120.0, 16)
	var title := Label.new()
	title.text = String(_cfg_val("outcomes", titles.get(kind, "hold_title"), ""))
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", C_CRACK if kind == "crack" else C_AI)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(title)
	var detail := Label.new()
	detail.text = String(_cfg_val("outcomes", details.get(kind, "hold_detail"), ""))
	detail.add_theme_font_size_override("font_size", 18)
	detail.add_theme_color_override("font_color", C_HINT)
	detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(detail)
	# 结果停留后淡出，交回日常画面
	var t := create_tween()
	t.tween_interval(float(_cfg_val("anim", "result_hold_secs", 2.2)))
	t.tween_callback(abort_phase3)


## 裂纹演出：屏幕中央一道暖色横向撕裂线 + 轻白闪
func _play_crack() -> void:
	_crack_line.visible = true
	_crack_line.modulate.a = 0.0
	var secs := float(_cfg_val("anim", "crack_flash_secs", 0.6))
	var t := create_tween()
	t.tween_property(_crack_line, "modulate:a", 1.0, secs * 0.25)
	t.tween_interval(secs * 0.5)
	t.tween_property(_crack_line, "modulate:a", 0.0, secs * 0.25)
	t.tween_callback(func() -> void: _crack_line.visible = false)
	_flash_rect.color = C_CRACK
	_flash_rect.visible = true
	_flash_rect.modulate.a = 0.0
	var f := create_tween()
	f.tween_property(_flash_rect, "modulate:a", 0.35, 0.08)
	f.tween_property(_flash_rect, "modulate:a", 0.0, 0.5)
	f.tween_callback(func() -> void: _flash_rect.visible = false)


# ── 倒计时 ──

func _start_timer(secs: float) -> void:
	_total = maxf(secs, 0.2)
	_remaining = _total
	_bar.visible = true
	_bar.position = Vector2.ZERO
	_bar_shown_color = C_AI            # 新计时从满血色起步
	_update_bar(1.0)


## delta 用于颜色平滑：直接赋值会在 0.5/0.25 两个阈值处"啪"地跳色。
func _update_bar(ratio: float, delta: float = 0.016) -> void:
	_bar.size.x = _bar_frame.size.x * clampf(ratio, 0.0, 1.0)
	var target := C_BAR_DANGER if ratio < 0.25 else (C_BAR_WARN if ratio < 0.5 else C_AI)
	if _bar_shown_color != target:
		_bar_shown_color = _bar_shown_color.lerp(target, clampf(delta * 12.0, 0.0, 1.0))
	_bar.color = _bar_shown_color


## 抖动幅度（px）：剩余比例从 JITTER_BELOW_RATIO 走到 0 的过程中线性加剧。
## 抽成纯函数以便无头测试断言（sin(ticks) 的相位在测试里不可控）。
func _jitter_amp(ratio: float) -> float:
	if ratio >= JITTER_BELOW_RATIO:
		return 0.0
	var k := 1.0 - clampf(ratio / JITTER_BELOW_RATIO, 0.0, 1.0)
	return JITTER_MAX_PX * k


func _tick(delta: float) -> void:
	if _resolved or _total <= 0.0:
		return
	_remaining -= delta
	var ratio := clampf(_remaining / _total, 0.0, 1.0)
	_update_bar(ratio, delta)
	# 最后 1/4 时间横向轻颤，幅度随剩余时间递减而加剧（与记忆考古的行动条同一套手感）
	var amp := _jitter_amp(ratio)
	if amp > 0.0:
		var k := 1.0 - clampf(ratio / JITTER_BELOW_RATIO, 0.0, 1.0)
		var freq_ms: float = 40.0 - 16.0 * k
		_bar.position = Vector2(sin(Time.get_ticks_msec() / freq_ms) * amp, 0)
	else:
		_bar.position = Vector2.ZERO
	if _remaining <= 0.0:
		_remaining = 0.0
		_total = 0.0
		_on_timeout()


func _on_timeout() -> void:
	if _resolved:
		return
	# 两处超时都按「没有反驳」处理 → 等同选项A（与记忆考古超时口径一致）
	print("[BattleChoiceUI] 超时未抉择（stage=%s）→ 视为接受 AI 的版本" % _stage)
	_resolve(true, "timeout")


# ── 交互 ──

func _on_option_a() -> void:
	if _stage != "choice" or _resolved:
		return
	_resolve(true, "hold")


func _on_option_b() -> void:
	if _stage != "choice" or _resolved:
		return
	print("[BattleChoiceUI] 选 B：转入手动输入旧友说过的话")
	_show_input_stage()


func _on_line_submitted(_text: String) -> void:
	_on_submit_line()


func _on_submit_line() -> void:
	if _stage != "input" or _resolved:
		return
	var line := "" if _line_edit == null else _line_edit.text.strip_edges()
	var res := _verifier.verify(line)
	print("[BattleChoiceUI] 验证「%s」→ %s" % [line, res["reason"]])
	if bool(res["matched"]):
		_resolve(false, "crack")
		return
	if String(res.get("reason", "")).begins_with("输入太短"):
		_hint_label.text = String(res["reason"])
		_hint_label.add_theme_color_override("font_color", C_BAR_WARN)
		return                       # 太短不算失败，让玩家重打，计时继续
	_resolve(true, "miss")


## 收口：唯一写结果的出口。hold=true → 选A/超时/说错；hold=false → 选B且命中
func _resolve(hold: bool, kind: String) -> void:
	if _resolved:
		return
	_resolved = true
	_last_result = kind
	_total = 0.0
	_bar.visible = false
	if _controller != null and is_instance_valid(_controller) \
			and _controller.has_method("resolve_battle"):
		_controller.call("resolve_battle", hold)
		print("[BattleChoiceUI] resolve_battle(erosion_hold=%s) ← %s" % [hold, kind])
	else:
		push_warning("[BattleChoiceUI] 未找到 BattlePostController，只演出结果（kind=%s）" % kind)
	battle_choice_resolved.emit(hold, kind)
	if kind == "crack":
		_play_crack()
	_show_result(kind)


# ── 公共入口 ──

## 开阶段三。debug_jump=true 时额外把 A 的时间轴推到 60s（编辑器里单测用）
func start_phase3(debug_jump: bool = false) -> void:
	if _stage != "" and not _resolved:
		return                       # 已经在抉择中，别被重复信号打断
	_resolved = false
	_debug_jump = debug_jump
	_ensure_controller()
	_clear_stage()
	_root.visible = true
	_root.modulate.a = 0.0
	var t := create_tween()
	t.tween_property(_root, "modulate:a", 1.0, float(_cfg_val("anim", "fade_in_secs", 0.3)))
	if debug_jump and _controller != null and _controller.has_method("set_battle_time"):
		_controller.call("start_battle")
		_controller.call("set_battle_time", 60.0)   # 阶段边界：60s = phase3
	_show_choice_stage()


## 收尾并隐藏。也用于 battle_finished 后复位。
func abort_phase3() -> void:
	_stage = ""
	_total = 0.0
	_bar.visible = false
	_crack_line.visible = false
	_flash_rect.visible = false
	_clear_stage()
	if not _root.visible:
		return
	var t := create_tween()
	t.tween_property(_root, "modulate:a", 0.0, float(_cfg_val("anim", "fade_out_secs", 0.4)))
	t.tween_callback(func() -> void:
		_root.modulate.a = 1.0
		_root.visible = false
	)


func is_active() -> bool:
	return _stage != ""


func get_stage() -> String:
	return _stage


func get_last_result() -> String:
	return _last_result


func get_corpus_size() -> int:
	return _verifier.corpus_size()


func get_corpus_ids() -> Array:
	return _verifier.corpus_ids()


func get_verifier() -> FriendLineVerifier:
	return _verifier


## 供测试/调试直接验一句话
func verify_line(line: String) -> Dictionary:
	return _verifier.verify(line)


# ── 信号消费 ──

func _on_battle_phase_changed(phase: String) -> void:
	if phase == "phase3":
		if not is_active():
			print("[BattleChoiceUI] 时间轴进入 phase3 → 开最终抉择")
			start_phase3(false)
	elif phase == "aftermath" and is_active():
		abort_phase3()


func _on_battle_finished(_erosion_hold: bool) -> void:
	if is_active():
		abort_phase3()


## 记忆考古的真相文本上过屏 → 收进语料（辨赢辨输都算，玩家确实看见了）
func _on_archaeology_ended(_success: bool, truth_shard: String) -> void:
	if truth_shard.is_empty():
		return
	var level: int = MemoryArchaeology.difficulty
	var id := "ARCH_L%d" % level
	if _verifier.add_truth(id, truth_shard, "memory_archaeology L%d" % level):
		print("[BattleChoiceUI] 语料 +1：%s（%d 字）" % [id, truth_shard.length()])


# ── 调试热键（F5 开阶段三 / F6 跳到输入态）──

func _handle_debug_key(keycode: int) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit:
		return                       # 正在输入框打字，不抢键
	if keycode == KEY_F5:
		if MemoryArchaeology.get_state() != MemoryArchaeology.State.IDLE \
				and MemoryArchaeology.get_state() != MemoryArchaeology.State.ENDED:
			return                   # 记忆考古还在跑，别叠加
		print("[BattleChoiceUI] 调试热键：开始阶段三")
		start_phase3(true)
	elif keycode == KEY_F6:
		if is_active() and not _resolved:
			print("[BattleChoiceUI] 调试热键：跳到手动输入态")
			_show_input_stage()
		else:
			print("[BattleChoiceUI] 调试热键：先按 F5 开阶段三")


# ── 引擎回调 / 入口（置于文件尾，所有被调用函数均已定义）──

func _process(delta: float) -> void:
	# 控制器是懒查找的（A 还没挂进场景），每秒重扫一次，挂上即自动接管
	if _controller == null or not is_instance_valid(_controller):
		_controller_scan_accum += delta
		if _controller_scan_accum >= 1.0:
			_controller_scan_accum = 0.0
			_ensure_controller()
	_tick(delta)


func _input(event: InputEvent) -> void:
	if DEBUG_HOTKEYS and event is InputEventKey and event.pressed and not event.echo:
		_handle_debug_key(event.keycode)


func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)

	var shade := ColorRect.new()
	shade.color = C_BG
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(shade)

	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	vbox.offset_left = 80
	vbox.offset_right = -80
	vbox.offset_top = 70
	vbox.offset_bottom = -70
	vbox.add_theme_constant_override("separation", 10)
	_root.add_child(vbox)

	_ai_label = Label.new()
	_ai_label.add_theme_font_size_override("font_size", 30)
	_ai_label.add_theme_color_override("font_color", C_AI)
	_ai_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_ai_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(_ai_label)

	_hint_label = Label.new()
	_hint_label.add_theme_font_size_override("font_size", 17)
	_hint_label.add_theme_color_override("font_color", C_HINT)
	_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(_hint_label)

	# 倒计时条（外框裁剪，条在框内从左收缩）
	_bar_frame = Control.new()
	_bar_frame.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_bar_frame.offset_left = 300
	_bar_frame.offset_right = -300
	_bar_frame.offset_top = 8
	_bar_frame.offset_bottom = 20
	_bar_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar_frame.clip_contents = true
	vbox.add_child(_bar_frame)
	_bar = ColorRect.new()
	_bar.color = C_AI
	_bar.size = Vector2(_bar_frame.size.x, 12)
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar.visible = false
	_bar_frame.add_child(_bar)

	_stage_root = Control.new()
	_stage_root.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_stage_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(_stage_root)

	# 覆盖层最后加 = 画在最上
	_flash_rect = ColorRect.new()
	_flash_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flash_rect.visible = false
	_root.add_child(_flash_rect)

	_crack_line = ColorRect.new()
	_crack_line.color = C_CRACK
	_crack_line.set_anchors_preset(Control.PRESET_CENTER)
	_crack_line.offset_left = -900
	_crack_line.offset_right = 900
	_crack_line.offset_top = -2
	_crack_line.offset_bottom = 2
	_crack_line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_crack_line.visible = false
	_root.add_child(_crack_line)

	_root.visible = false


func _load_config() -> void:
	var f := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if f == null:
		push_warning("[BattleChoiceUI] %s 未找到，使用内置默认" % CONFIG_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) == TYPE_DICTIONARY:
		_cfg = parsed


func _seed_corpus() -> void:
	if bool(_cfg_val("corpus", "seed_all_ma_anchors", false)):
		var n := _verifier.seed_from_anchor_map(MemoryAnchorUI.ANCHOR_MAP, "MA_")
		print("[BattleChoiceUI] 语料预载全部 MA 锚点 %d 条（corpus.seed_all_ma_anchors=true）" % n)
	if _verifier.corpus_size() == 0:
		print("[BattleChoiceUI] 语料为空——玩家还没走过记忆考古关卡，选项B 暂时对不上任何东西")


func _ready() -> void:
	layer = LAYER
	_load_config()
	_verifier = FriendLineVerifier.new(
		float(_cfg_val("verify", "match_threshold", 0.55)),
		float(_cfg_val("verify", "containment_weight", 0.7)),
		float(_cfg_val("verify", "bigram_weight", 0.3)),
		int(_cfg_val("phase3", "min_input_chars", 4)))
	_build_ui()
	_seed_corpus()
	_ensure_controller()
	MemoryArchaeology.archaeology_ended.connect(_on_archaeology_ended)
	print("[BattleChoiceUI] 启动：阶段三抉择就绪，layer=%d，语料 %d 条"
		% [layer, _verifier.corpus_size()])
