# memory_anchor_ui.gd —— 记忆锚点浮现 UI（CanvasLayer 覆盖层）
# 玩家点击场景热点（EventBus.object_interacted）→ 卡片浮现
# 卡片流程：
#   句 1：淡入 + 打字机逐字浮现（80ms/字）→ 停留 0.5s → 淡出 0.5s
#   句 2：淡入 + 打字机逐字浮现 → 停留 → 淡出
#   ……
#   句 N：淡入 + 打字机逐字浮现 → 停留 → 自动浮现情感按钮 + 自由输入
# 文字位置：标题下、垂直居中（不上贴底）
# 交互：
#   - 弹窗下方外侧：常驻"阅读全文 ▷"按钮
#     - TYPING：点击 → 当前句立即填满 + 直接进入 FADING_OUT
#     - POST_TYPING：点击 → 跳过等待 + 立即 FADING_OUT
#     - FADING_OUT：点击 → 立即完成淡出 + 进入下一句
#     - ALL_DONE：按钮隐藏（选项已自动浮现）
# 段按 \\n 拆分；每段按 "。" "！" "？" "…" 拆句
# 数据从 config/anchors.json 运行时加载

extends CanvasLayer

const EMOTION_OPTIONS := [
	"平静的怀念",
	"隐隐的愧疚",
	"无法释怀",
]

const ANCHORS_JSON_PATH := "res://config/anchors.json"

## 句子的拆分边界（标点后切分）
const SENTENCE_DELIMS := ["。", "！", "？", "…"]
## 打字机 80ms/字 + 每帧最多 4 字
const TYPING_SPEED_SEC_PER_CHAR := 0.08
const MAX_CHARS_PER_FRAME := 4
## 句打完 → 停留 → 淡出 → 下一句
const SENTENCE_DISPLAY_AFTER_TYPING_SEC := 0.5
const SENTENCE_FADE_OUT_SEC := 0.5
const SENTENCE_FADE_IN_SEC := 0.4
## 自由输入
const FREE_INPUT_PLACEHOLDER := "或输入你自己的感受..."
const FREE_INPUT_MAX_LEN := 50

enum Phase { TYPING, POST_TYPING, FADING_OUT, ALL_DONE }

## 玩家选了自由输入路径（供 DialogManager / MemoryArchaeology 等订阅响应）
signal free_input_chosen(object_id: String, text: String, llm_result: Dictionary)

## object_id → 锚点数据（顶层 _meta 字段自动跳过）
var ANCHOR_MAP: Dictionary = {}

var _root: Control
var _card: PanelContainer
var _title_label: Label
var _text_label: Label
var _options_box: HBoxContainer
var _options_label: Label
var _free_input_container: VBoxContainer
var _free_input_label: Label
var _free_input_lineedit: LineEdit
var _free_input_submit: Button
var _advance_button: Control
var _advance_label: Label
var _current_object_id: String = ""
var _current_revealed_text: String = ""

## 句子结构：所有段拼平后按标点拆句
var _sentences := []
var _current_sentence: int = 0
var _phase: int = Phase.ALL_DONE
var _display_timer: float = 0.0
var _fade_tween: Tween = null

## 打字机状态
var _typing_full: String = ""
var _typing_chars: int = 0
var _typing_timer: float = 0.0
var _typing_active: bool = false

## 预建的情感按钮池
var _emotion_buttons: Array[Button] = []


func _ready() -> void:
	layer = 20
	_load_anchors()
	_build_ui()
	_root.visible = false
	EventBus.object_interacted.connect(_on_object_interacted)


func _process(delta: float) -> void:
	match _phase:
		Phase.TYPING:
			if not _typing_active:
				return
			_typing_timer += delta
			var chars_this_frame := 0
			while _typing_timer >= TYPING_SPEED_SEC_PER_CHAR and _typing_chars < _typing_full.length() and chars_this_frame < MAX_CHARS_PER_FRAME:
				var next_char := _typing_full.substr(_typing_chars, 1)
				var extra_pause := 0.0
				match next_char:
					"。":
						extra_pause = TYPING_SPEED_SEC_PER_CHAR * 2.0
					"，", "；", "：", "、", "？", "！", "…":
						extra_pause = TYPING_SPEED_SEC_PER_CHAR * 0.5
				_typing_timer -= TYPING_SPEED_SEC_PER_CHAR + extra_pause
				_typing_chars += 1
				chars_this_frame += 1
			if chars_this_frame > 0:
				_refresh_text()
			if _typing_chars >= _typing_full.length():
				_typing_active = false
				_phase = Phase.POST_TYPING
				_display_timer = 0.0
		Phase.POST_TYPING:
			_display_timer += delta
			if _display_timer >= SENTENCE_DISPLAY_AFTER_TYPING_SEC:
				_start_fade_out()
		Phase.FADING_OUT:
			pass  ## 由 Tween.finished 推进 _next_sentence
		Phase.ALL_DONE:
			pass


## 当前句开始打字（伴随淡入）
func _start_typing_sentence() -> void:
	if _current_sentence >= _sentences.size():
		_enter_all_done()
		return
	_typing_full = _sentences[_current_sentence]
	_typing_chars = 0
	_typing_timer = 0.0
	_typing_active = true
	_text_label.text = ""
	_text_label.modulate.a = 0.0
	_kill_fade_tween()
	_fade_tween = create_tween()
	_fade_tween.tween_property(_text_label, "modulate:a", 1.0, SENTENCE_FADE_IN_SEC)
	_phase = Phase.TYPING


## 开始当前句淡出动画
func _start_fade_out() -> void:
	_kill_fade_tween()
	_fade_tween = create_tween()
	_fade_tween.tween_property(_text_label, "modulate:a", 0.0, SENTENCE_FADE_OUT_SEC)
	_fade_tween.finished.connect(_on_fade_out_finished)
	_phase = Phase.FADING_OUT


## 淡出完成后 → 下一句开始打字
func _on_fade_out_finished() -> void:
	if _phase == Phase.FADING_OUT:
		_current_sentence += 1
		_start_typing_sentence()


## 全部句子打完 → 自动浮现情感按钮 + 自由输入
func _enter_all_done() -> void:
	_phase = Phase.ALL_DONE
	_text_label.modulate.a = 1.0
	_advance_button.visible = false
	_options_label.visible = true
	for btn in _emotion_buttons:
		btn.visible = btn.text != ""
	_free_input_container.visible = true
	_free_input_lineedit.grab_focus()


func _kill_fade_tween() -> void:
	if _fade_tween != null and _fade_tween.is_valid():
		_fade_tween.kill()
	_fade_tween = null


## 立即完成当前句填满（用于按钮快进）
func _finish_typing_now() -> void:
	_typing_chars = _typing_full.length()
	_typing_active = false
	_refresh_text()
	_phase = Phase.POST_TYPING
	_display_timer = 0.0


## 跳过等待 + 立即淡出
func _skip_to_fade_out() -> void:
	_display_timer = SENTENCE_DISPLAY_AFTER_TYPING_SEC


## 跳过淡出动画，立即进入下一句
func _skip_fade_out() -> void:
	if _fade_tween != null and _fade_tween.is_valid():
		_fade_tween.kill()
	_fade_tween = null
	_text_label.modulate.a = 0.0
	_current_sentence += 1
	_start_typing_sentence()


## 当前句打字部分显示
func _refresh_text() -> void:
	_text_label.text = _typing_full.substr(0, _typing_chars)


func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)

	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.4)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	shade.gui_input.connect(_on_shade_input)
	_root.add_child(shade)

	var vp: Vector2 = get_viewport().get_visible_rect().size
	var card_w: float = min(1100.0, vp.x * 0.82)
	var card_h: float = min(360.0, vp.y * 0.45)
	var side_margin: float = 80.0
	var bottom_margin: float = 110.0  ## 给弹窗外侧按钮留位置

	_card = PanelContainer.new()
	_card.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_card.offset_left = side_margin
	_card.offset_right = -side_margin
	_card.offset_top = -card_h - bottom_margin
	_card.offset_bottom = -bottom_margin
	_card.custom_minimum_size = Vector2(card_w, card_h)
	_root.add_child(_card)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 36)
	margin.add_theme_constant_override("margin_right", 36)
	margin.add_theme_constant_override("margin_top", 24)
	margin.add_theme_constant_override("margin_bottom", 24)
	_card.add_child(margin)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	margin.add_child(vbox)

	_title_label = Label.new()
	_title_label.add_theme_color_override("font_color", Color(1.0, 0.72, 0.3))
	_title_label.add_theme_font_size_override("font_size", 22)
	vbox.add_child(_title_label)

	vbox.add_child(HSeparator.new())

	_text_label = Label.new()
	_text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_text_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text_label.add_theme_font_size_override("font_size", 22)
	_text_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER  ## 文字上移、垂直居中
	vbox.add_child(_text_label)

	vbox.add_child(HSeparator.new())

	_options_label = Label.new()
	_options_label.text = "选择此刻的感受："
	_options_label.add_theme_font_size_override("font_size", 14)
	_options_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.7, 1))
	_options_label.visible = false
	vbox.add_child(_options_label)

	_options_box = HBoxContainer.new()
	_options_box.add_theme_constant_override("separation", 12)
	_options_box.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_child(_options_box)

	for i in EMOTION_OPTIONS.size():
		var btn := _make_emotion_button("")
		btn.visible = false
		_options_box.add_child(btn)
		_emotion_buttons.append(btn)

	_free_input_container = VBoxContainer.new()
	_free_input_container.add_theme_constant_override("separation", 4)
	_free_input_container.visible = false
	vbox.add_child(_free_input_container)

	_free_input_label = Label.new()
	_free_input_label.text = "或输入你自己的感受（按 Enter 提交）："
	_free_input_label.add_theme_font_size_override("font_size", 14)
	_free_input_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.7, 1))
	_free_input_container.add_child(_free_input_label)

	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 8)
	_free_input_container.add_child(input_row)

	_free_input_lineedit = LineEdit.new()
	_free_input_lineedit.placeholder_text = FREE_INPUT_PLACEHOLDER
	_free_input_lineedit.max_length = FREE_INPUT_MAX_LEN
	_free_input_lineedit.custom_minimum_size = Vector2(400, 40)
	_free_input_lineedit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_free_input_lineedit.text_submitted.connect(_on_free_input_submit)
	input_row.add_child(_free_input_lineedit)

	_free_input_submit = Button.new()
	_free_input_submit.text = "确认"
	_free_input_submit.custom_minimum_size = Vector2(80, 40)
	_free_input_submit.disabled = true
	_free_input_submit.pressed.connect(_on_free_input_submit.bind(""))
	input_row.add_child(_free_input_submit)

	_free_input_lineedit.text_changed.connect(func(t: String) -> void:
		_free_input_submit.disabled = t.strip_edges().is_empty()
	)

	## "阅读全文 ▷"按钮：放在弹窗下方外侧，固定底部居中
	var btn_size := Vector2(150, 44)
	_advance_button = Control.new()
	_advance_button.custom_minimum_size = btn_size
	_advance_button.size = btn_size
	## 弹窗下方居中：锚定底部，X 居中
	_advance_button.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_advance_button.offset_left = -btn_size.x / 2
	_advance_button.offset_right = btn_size.x / 2
	_advance_button.offset_top = -btn_size.y - 30
	_advance_button.offset_bottom = -30
	_advance_button.mouse_filter = Control.MOUSE_FILTER_STOP
	_advance_button.draw.connect(_on_advance_button_draw)
	_advance_button.gui_input.connect(_on_advance_button_input)
	_advance_button.visible = false
	_root.add_child(_advance_button)

	_advance_label = Label.new()
	_advance_label.text = "阅读全文 ▷"
	_advance_label.add_theme_font_size_override("font_size", 14)
	_advance_label.add_theme_color_override("font_color", Color(0.3, 0.2, 0.1, 1))
	_advance_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	_advance_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_advance_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_advance_button.add_child(_advance_label)


func _on_advance_button_draw() -> void:
	var rect := Rect2(Vector2.ZERO, _advance_button.size)
	_advance_button.draw_rect(rect, Color(1.0, 0.72, 0.3, 0.45), true)
	_advance_button.draw_rect(rect, Color(0.3, 0.2, 0.1, 1), false, 1.5)


## 按钮点击;;TYPING 立即填满；POST_TYPING 跳淡出；FADING_OUT 跳下一句
func _on_advance_button_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed):
		return
	match _phase:
		Phase.TYPING:
			_finish_typing_now()
			_start_fade_out()
		Phase.POST_TYPING:
			_skip_to_fade_out()
		Phase.FADING_OUT:
			_skip_fade_out()
		Phase.ALL_DONE:
			pass  ## 按钮已在 ALL_DONE 隐藏


func _make_emotion_button(emotion: String) -> Button:
	var btn := Button.new()
	btn.text = emotion
	btn.custom_minimum_size = Vector2(0, 44)
	btn.add_theme_font_size_override("font_size", 18)
	btn.pressed.connect(_on_emotion_pressed.bind(emotion))
	return btn


## 按标点拆分句子（保留标点）；支持多段（\n）拼平
func _split_sentences(text: String) -> Array:
	var sentences := []
	for segment in text.split("\n", false):
		var current := ""
		for i in segment.length():
			var ch := segment.substr(i, 1)
			current += ch
			if ch in SENTENCE_DELIMS:
				sentences.append(current)
				current = ""
		if not current.is_empty():
			sentences.append(current)
	return sentences


func _load_anchors() -> void:
	var f := FileAccess.open(ANCHORS_JSON_PATH, FileAccess.READ)
	if f == null:
		push_error("[MemoryAnchorUI] 无法打开 %s" % ANCHORS_JSON_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("[MemoryAnchorUI] anchors.json 格式错误（顶层应为对象）")
		return
	for key in parsed:
		if key == "_meta":
			continue
		ANCHOR_MAP[key] = parsed[key]
	print("[MemoryAnchorUI] 加载锚点映射 %d 条（来源 %s）" % [ANCHOR_MAP.size(), ANCHORS_JSON_PATH])


func _on_object_interacted(object_id: String) -> void:
	if not ANCHOR_MAP.has(object_id):
		return
	_text_label.text = ""  ## 立刻清空旧对话文字，避免 root 显示后残留
	_kill_fade_tween()
	_current_object_id = object_id
	var data: Dictionary = ANCHOR_MAP[object_id]
	_title_label.text = "「%s」" % data["item_name"]
	_current_revealed_text = data.get("revealed_text", "")
	_sentences = _split_sentences(_current_revealed_text)
	_current_sentence = 0
	_display_timer = 0.0
	_typing_full = ""
	_typing_chars = 0
	_typing_active = false
	_text_label.modulate.a = 1.0
	_advance_button.visible = true
	_advance_button.queue_redraw()
	_free_input_container.visible = false
	_free_input_lineedit.text = ""
	_free_input_submit.disabled = true
	_options_label.visible = false
	for btn in _emotion_buttons:
		btn.visible = false
	var emotions: Array = data.get("emotion_options", EMOTION_OPTIONS)
	for i in _emotion_buttons.size():
		var btn := _emotion_buttons[i]
		if i < emotions.size():
			btn.text = emotions[i]
			btn.disabled = false
		else:
			btn.text = ""
			btn.disabled = true
	_root.visible = true
	if _sentences.is_empty():
		_enter_all_done()
		return
	_start_typing_sentence()


func _close_overlay() -> void:
	_root.visible = false
	_text_label.text = ""
	_kill_fade_tween()
	_current_object_id = ""
	_advance_button.visible = false
	_free_input_container.visible = false
	_free_input_lineedit.text = ""
	_free_input_submit.disabled = true
	_options_label.visible = false


func _on_emotion_pressed(emotion: String) -> void:
	EventBus.anchor_resolved.emit(_current_object_id, emotion)
	print("[记忆锚点] 解析结果 → object_id=%s | 情感=%s" % [_current_object_id, emotion])
	_close_overlay()


## 自由输入路径：调 LLMGateway.analyze_memory → 用 magnitude 直接更新 TrustDrift
func _on_free_input_submit(text: String) -> void:
	var trimmed: String = text.strip_edges()
	if trimmed.is_empty():
		return
	var result: Dictionary = LLMGateway.analyze_memory(_current_revealed_text, trimmed, _current_object_id)
	var magnitude: float = float(result.get("drift_magnitude", 0.0))
	var direction: String = str(result.get("drift_direction", ""))
	var confidence: float = float(result.get("drift_confidence", 0.0))
	TrustDrift.record_drift(_current_object_id, magnitude, direction, confidence)
	free_input_chosen.emit(_current_object_id, trimmed, result)
	print("[记忆锚点] 自由输入 → object_id=%s | text=%s | dir=%s mag=%.1f" % [_current_object_id, trimmed, direction, magnitude])
	_close_overlay()


func _on_shade_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed):
		return
	if _phase == Phase.ALL_DONE:
		_close_overlay()
