# visual_novel_ui.gd —— 模式 B：视觉小说界面（CanvasLayer）
# 挂到 CanvasLayer 节点上。纯代码构建 UI（无需手搭节点树）。
# 订阅 DialogManager 信号，在 mode == "visual_novel" 时激活。
#
# 布局：背景 + 旧友立绘（左/右/中三档）+ 底部大文本框（角色名带颜色条 + 对白）
#       + 右下角三角快进指示器（打字完成后呼吸）+ 选项
# 交互：按空格 / 点击空白 → 推进下一句；点击选项 → 选择。
# 打字机：对白逐字显示，速度取 dialogue.typing_speed（默认 60ms/字）。
# 感想输入：dialogue_ended 后淡入，提交后淡出（M3 接入 MemoryAnchorStorage）。
#
# 占位说明：立绘、背景均为色块占位，等 D 交付美术资源后替换。

extends CanvasLayer

# ── 颜色（对应 ui_design_spec.md 的设计 Token）──
const C_NAME        := Color("#FFB74D")       # 角色名 暖橙
const C_TEXT        := Color("#FFFFFF")       # 对白 白
const C_BOX_BG      := Color(0, 0, 0, 0.65)   # 文本框底 半透明黑
const C_BG          := Color("#1E2A38")       # 背景占位 深冷蓝
const C_PORTRAIT    := Color(0.55, 0.55, 0.55, 0.6)  # 立绘占位 灰剪影
const C_BTN_BORDER  := Color("#FFB74D")       # 选项描边 暖橙
const C_REFLECT_BG  := Color(0, 0, 0, 0.78)   # 感想面板底 深半透

# ── 节点引用 ──
var _root: Control
var _name_label: Label
var _name_bar: Panel                  # ★ 新增：名字左侧颜色条
var _text_label: Label
var _portrait: Panel
var _portrait_label: Label
var _choices_box: HBoxContainer
var _next_indicator: Control          # ★ 新增：右下角三角快进
var _reflection_panel: PanelContainer # ★ 新增：感想输入面板
var _reflection_input: LineEdit       # ★ 新增：感想输入框

# 当前是否在显示选项（有选项时，点击/空格不推进，只选选项）
var _showing_choices: bool = false

# ── 打字机状态 ──
var _typing_label: Label = null
var _typing_full: String = ""
var _typing_chars: int = 0
var _typing_speed: float = 0.06
var _typing_timer: float = 0.0

# ── next 指示器呼吸动画 ──
var _next_indicator_time: float = 0.0


func _ready() -> void:
	_build_ui()
	_root.visible = false
	_next_indicator.visible = false
	_reflection_panel.visible = false
	DialogManager.dialogue_started.connect(_on_started)
	DialogManager.line_shown.connect(_on_line)
	DialogManager.choices_shown.connect(_on_choices)
	DialogManager.dialogue_ended.connect(_on_ended)


func _process(delta: float) -> void:
	# 打字机：逐字更新当前对白
	if _typing_label != null:
		_typing_timer += delta
		while _typing_timer >= _typing_speed and _typing_chars < _typing_full.length():
			_typing_timer -= _typing_speed
			_typing_chars += 1
			_typing_label.text = _typing_full.substr(0, _typing_chars)
		if _typing_chars >= _typing_full.length():
			_typing_label = null
			# ★ 打字完成，显示右下角快进三角
			if _root.visible and not _showing_choices:
				_next_indicator.visible = true
				_next_indicator_time = 0.0

	# next 指示器呼吸（仅可见时累计 + 重绘）
	if _next_indicator.visible:
		_next_indicator_time += delta
		_next_indicator.queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	# 感想面板打开时不抢输入（让玩家能输入文字 / 点保存）
	if _reflection_panel.visible and _reflection_panel.modulate.a > 0.9:
		return
	# 空格推进下一句（仅本 UI 可见时响应，避免与其它模式 UI 抢输入）
	if not _root.visible:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE and not _showing_choices:
			DialogManager.advance()


# ── 信号响应 ──
func _on_started(data: Dictionary) -> void:
	if data.get("mode", "") != "visual_novel":
		_root.visible = false
		return
	_root.visible = true
	_showing_choices = false
	_choices_box.visible = false
	_next_indicator.visible = false       # ★ 新对话开始时隐藏
	_reflection_panel.visible = false     # ★ 新对话时清掉上一次的感想面板
	_reflection_panel.modulate.a = 0.0
	_reflection_input.text = ""
	_clear_text()
	_typing_speed = float(data.get("typing_speed", 60)) / 1000.0
	_set_portrait(data.get("portrait_position", "center"))


func _on_line(speaker: String, name: String, text: String) -> void:
	_name_label.text = name
	_typing_label = _text_label
	_typing_full = text
	_typing_chars = 0
	_typing_timer = 0.0
	_text_label.text = ""
	_next_indicator.visible = false       # ★ 新一句开始时隐藏


func _on_choices(choices: Array) -> void:
	_showing_choices = true
	_next_indicator.visible = false       # ★ 选项时隐藏快进三角
	_choices_box.visible = true
	for child in _choices_box.get_children():
		child.queue_free()
	for i in choices.size():
		_choices_box.add_child(_make_choice_button(choices[i].get("text", ""), i))


func _on_ended() -> void:
	_showing_choices = false
	_choices_box.visible = false
	_next_indicator.visible = false
	_root.visible = false                 # 对话结束，回到场景
	_show_reflection_panel()              # ★ 最后才出现感想输入


# ── UI 构建 ──
func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.gui_input.connect(_on_root_input)
	add_child(_root)

	# 背景占位（等 D 交付场景插画后替换）
	var bg := ColorRect.new()
	bg.color = C_BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(bg)

	# 旧友立绘占位（灰剪影，永无正脸）
	_portrait = Panel.new()
	_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var psb := StyleBoxFlat.new()
	psb.bg_color = C_PORTRAIT
	_portrait.add_theme_stylebox_override("panel", psb)
	_root.add_child(_portrait)

	_portrait_label = Label.new()
	_portrait_label.text = "旧友立绘（占位）"
	_portrait_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	_portrait_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_portrait_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_portrait_label.add_theme_font_size_override("font_size", 18)
	_portrait_label.add_theme_color_override("font_color", Color(1, 1, 1, 0.45))
	_portrait.add_child(_portrait_label)

	# ★ 底部大文本框：280px 高，左右留白 40px（更宽更舒展）
	var box := PanelContainer.new()
	box.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	box.offset_left = 40
	box.offset_right = -40
	box.offset_top = -304      # 304 - 24 底距 = 280px
	box.offset_bottom = -24
	var bsb := StyleBoxFlat.new()
	bsb.bg_color = C_BOX_BG
	bsb.set_corner_radius_all(8)
	bsb.content_margin_left = 32
	bsb.content_margin_right = 32
	bsb.content_margin_top = 24
	bsb.content_margin_bottom = 24
	box.add_theme_stylebox_override("panel", bsb)
	_root.add_child(box)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 16)
	box.add_child(vbox)

	# ★ 名字行：左侧颜色条 + 名字，与对白视觉错开
	var name_hbox := HBoxContainer.new()
	name_hbox.add_theme_constant_override("separation", 12)
	name_hbox.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	vbox.add_child(name_hbox)

	_name_bar = Panel.new()
	_name_bar.custom_minimum_size = Vector2(4, 26)
	_name_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var bar_sb := StyleBoxFlat.new()
	bar_sb.bg_color = C_NAME
	bar_sb.set_corner_radius_all(2)
	_name_bar.add_theme_stylebox_override("panel", bar_sb)
	_name_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	name_hbox.add_child(_name_bar)

	_name_label = Label.new()
	_name_label.add_theme_font_size_override("font_size", 20)
	_name_label.add_theme_color_override("font_color", C_NAME)
	_name_label.text = ""
	_name_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	name_hbox.add_child(_name_label)

	_text_label = Label.new()
	_text_label.add_theme_font_size_override("font_size", 22)
	_text_label.add_theme_color_override("font_color", C_TEXT)
	_text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_text_label.text = ""
	vbox.add_child(_text_label)

	# 选项区上移（文本框上方 56px）
	_choices_box = HBoxContainer.new()
	_choices_box.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_choices_box.offset_left = 40
	_choices_box.offset_right = -40
	_choices_box.offset_top = -360
	_choices_box.offset_bottom = -316
	_choices_box.add_theme_constant_override("separation", 16)
	_choices_box.visible = false
	_root.add_child(_choices_box)

	# ★ 右下角三角快进指示器（默认隐藏，仅打字完成后显示 + 呼吸）
	_next_indicator = Control.new()
	_next_indicator.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_next_indicator.offset_left = -76
	_next_indicator.offset_right = -36
	_next_indicator.offset_top = -68
	_next_indicator.offset_bottom = -28
	_next_indicator.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_next_indicator.visible = false
	_next_indicator.draw.connect(_draw_next_indicator)
	_root.add_child(_next_indicator)

	# ★ 感想输入面板（默认隐藏，dialogue_ended 才淡入）
	_build_reflection_panel()


func _build_reflection_panel() -> void:
	_reflection_panel = PanelContainer.new()
	_reflection_panel.set_anchors_preset(Control.PRESET_CENTER)
	_reflection_panel.offset_left = -320
	_reflection_panel.offset_right = 320
	_reflection_panel.offset_top = -120
	_reflection_panel.offset_bottom = 120
	var rsb := StyleBoxFlat.new()
	rsb.bg_color = C_REFLECT_BG
	rsb.set_corner_radius_all(12)
	rsb.content_margin_left = 28
	rsb.content_margin_right = 28
	rsb.content_margin_top = 24
	rsb.content_margin_bottom = 24
	rsb.border_color = C_NAME
	rsb.set_border_width_all(1)
	_reflection_panel.add_theme_stylebox_override("panel", rsb)
	_reflection_panel.visible = false
	_reflection_panel.modulate.a = 0.0
	_root.add_child(_reflection_panel)

	var rvbox := VBoxContainer.new()
	rvbox.add_theme_constant_override("separation", 12)
	_reflection_panel.add_child(rvbox)

	var title := Label.new()
	title.text = "记下此刻的感想…"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", C_NAME)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rvbox.add_child(title)

	_reflection_input = LineEdit.new()
	_reflection_input.placeholder_text = "例：和 AI 的对话让我觉得……"
	_reflection_input.custom_minimum_size = Vector2(0, 44)
	_reflection_input.add_theme_font_size_override("font_size", 18)
	rvbox.add_child(_reflection_input)

	var submit := Button.new()
	submit.text = "保存"
	submit.custom_minimum_size = Vector2(0, 40)
	submit.pressed.connect(_on_reflection_submit)
	rvbox.add_child(submit)


func _set_portrait(pos: String) -> void:
	# 立绘高 756px（约 70% 屏），宽 500px，水平位置三档（正式版改用 anchor 比例）
	_portrait.offset_top = 40
	_portrait.offset_bottom = 40 + 756
	var w := 500
	match pos:
		"left":
			_portrait.anchor_left = 0.0
			_portrait.anchor_right = 0.0
			_portrait.offset_left = 60
			_portrait.offset_right = 60 + w
		"right":
			_portrait.anchor_left = 1.0
			_portrait.anchor_right = 1.0
			_portrait.offset_left = -60 - w
			_portrait.offset_right = -60
		_:
			_portrait.anchor_left = 0.5
			_portrait.anchor_right = 0.5
			_portrait.offset_left = -w / 2
			_portrait.offset_right = w / 2


func _make_choice_button(text: String, index: int) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.custom_minimum_size = Vector2(0, 44)
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.add_theme_font_size_override("font_size", 20)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.border_color = C_BTN_BORDER
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(8)
	btn.add_theme_stylebox_override("normal", sb)
	btn.add_theme_color_override("font_color", C_NAME)
	btn.pressed.connect(func() -> void: DialogManager.select_choice(index))
	return btn


func _clear_text() -> void:
	_name_label.text = ""
	_text_label.text = ""


func _on_root_input(event: InputEvent) -> void:
	if not _root.visible:
		return
	# 感想面板打开时不抢输入
	if _reflection_panel.visible and _reflection_panel.modulate.a > 0.9:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if not _showing_choices:
			DialogManager.advance()


# ── next 指示器自绘 ──
func _draw_next_indicator() -> void:
	# 居中三角形（24 高 × 20 宽），呼吸 alpha 0.5~1.0
	var pts := PackedVector2Array([
		Vector2(2, 0),
		Vector2(22, 12),
		Vector2(2, 24),
	])
	var phase: float = 0.5 + 0.5 * sin(_next_indicator_time * 3.0)
	var alpha: float = lerp(0.5, 1.0, phase)
	_next_indicator.draw_colored_polygon(pts, Color(C_NAME.r, C_NAME.g, C_NAME.b, alpha))


# ── 感想面板交互 ──
func _show_reflection_panel() -> void:
	_reflection_panel.visible = true
	_reflection_input.grab_focus()
	var tween := create_tween()
	tween.tween_property(_reflection_panel, "modulate:a", 1.0, 0.4)


func _on_reflection_submit() -> void:
	var text := _reflection_input.text.strip_edges()
	if text.is_empty():
		return
	# M3 接入 MemoryAnchorStorage / trust_drift_collector；此处仅打印
	print("[Reflection] ", text)
	_reflection_input.text = ""
	var tween := create_tween()
	tween.tween_property(_reflection_panel, "modulate:a", 0.0, 0.3)
	tween.tween_callback(func() -> void: _reflection_panel.visible = false)
