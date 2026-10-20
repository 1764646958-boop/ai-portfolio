# chat_ui.gd —— 模式 A：AI 聊天 App 界面（CanvasLayer）
# 挂到 CanvasLayer 节点上。纯代码构建 UI（无需手搭节点树）。
# 订阅 DialogManager 信号，在 mode == "chat_app" 时激活。
#
# 交互：鼠标点击空白处 或 按空格 → 推进下一句；点击选项 → 选择。
# 打字机：收到一句后逐字显示，速度取 dialogue.typing_speed（默认 60ms/字）。

extends CanvasLayer

# ── 颜色（对应 ui_design_spec.md 的设计 Token）──
const C_AI_BUBBLE   := Color("#FFB74D")
const C_AI_TEXT     := Color("#FFF8E7")
const C_FRIEND_BUBBLE := Color("#F0F0F0")
const C_FRIEND_TEXT := Color("#333333")
const C_PLAYER_BUBBLE := Color("#4FC3F7")   # W3：玩家消息 右侧浅蓝气泡
const C_PLAYER_TEXT := Color("#FFFFFF")
const C_BG          := Color("#FFFFFF")
const C_LINE        := Color("#E0E0E0")
const C_TEXT_MID    := Color("#8A8A8A")
const C_ACCENT      := Color("#FF7043")     # W3：发送按钮/未读红点

# ── 节点引用 ──
var _root: Control
var _msg_vbox: VBoxContainer
var _scroll: ScrollContainer
var _choices_box: HBoxContainer
var _name_label: Label

# ── 打字机状态 ──
var _typing_label: Label = null
var _typing_full: String = ""
var _typing_chars: int = 0
var _typing_speed: float = 0.06
var _typing_timer: float = 0.0

# 当前是否在显示选项（有选项时，点击/空格不推进，只选选项）
var _showing_choices: bool = false

# ── W3：自由输入 + LLM 对接 ──
var _input_line: LineEdit
var _send_button: Button
var _unread_badge: Label                 # 状态栏未读红点（AI 推送计数）
var _unread_count: int = 0
var _npc_name: String = "林默"           # 当前 AI 角色名（对话或推送用）
var _speaker_name: String = "林默 · 你的AI陪伴"
var _reply_seq: int = 0                  # 自由输入生成回复的递增序号
var _history: Array = []                 # 本次会话简短历史（供 player_history_summary）
var _pending_messages: Array = []        # 界面隐藏时收到的 AI 推送，打开后补显示
var _pushed_scenes := {}                 # 已推送过的场景路径（避免重复提示）


func _ready() -> void:
	_build_ui()
	_root.visible = false
	DialogManager.dialogue_started.connect(_on_started)
	DialogManager.line_shown.connect(_on_line)
	DialogManager.choices_shown.connect(_on_choices)
	DialogManager.dialogue_ended.connect(_on_ended)
	# W3：常驻 Autoload —— 场景切换后 AI 主动推送（模拟"AI 主动聊天"，见 A 大纲 3.1）
	EventBus.scene_changed.connect(_on_scene_changed)


func _process(delta: float) -> void:
	# 打字机：逐字更新当前气泡
	if _typing_label == null:
		return
	_typing_timer += delta
	while _typing_timer >= _typing_speed and _typing_chars < _typing_full.length():
		_typing_timer -= _typing_speed
		_typing_chars += 1
		_typing_label.text = _typing_full.substr(0, _typing_chars)
	if _typing_chars >= _typing_full.length():
		_typing_label = null


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	# T 键：打开/关闭聊天 App（探索中随时可看 AI 消息，W3 交付）
	if event.keycode == KEY_T:
		if _root.visible:
			_close_chat()
		else:
			_open_chat()
		return
	# 空格推进下一句（仅本 UI 可见时响应，避免与其它模式 UI 抢输入）
	if not _root.visible:
		return
	if event.keycode == KEY_SPACE and not _showing_choices:
		DialogManager.advance()


# ── 信号响应 ──
func _on_started(data: Dictionary) -> void:
	if data.get("mode", "") != "chat_app":
		_root.visible = false
		return
	_root.visible = true
	_showing_choices = false
	_clear_messages()
	_name_label.text = data.get("speaker_name", "林默 · 你的AI陪伴")
	_speaker_name = _name_label.text
	_typing_speed = float(data.get("typing_speed", 60)) / 1000.0
	_clear_unread()   # W3：打开界面 → 未读清零


func _on_line(speaker: String, name: String, text: String) -> void:
	# W3 三态渲染：ai=左橙 / player=右浅蓝 / 其他(friend)=右灰
	var is_ai: bool = (speaker == "ai")
	var is_player: bool = (speaker == "player")
	var bubble := _make_bubble(is_ai, is_player)
	var label := _bubble_label(bubble)
	_msg_vbox.add_child(_make_row(bubble, is_ai, is_player))
	# 玩家消息立即显示；AI 消息走打字机
	if is_player:
		label.text = text
		_scroll_to_bottom.call_deferred()
		return
	_typing_label = label
	_typing_full = text
	_typing_chars = 0
	_typing_timer = 0.0
	_scroll_to_bottom.call_deferred()


func _on_choices(choices: Array) -> void:
	_showing_choices = true
	_choices_box.visible = true
	for child in _choices_box.get_children():
		child.queue_free()
	for i in choices.size():
		_choices_box.add_child(_make_choice_button(choices[i].get("text", ""), i))


func _on_ended() -> void:
	_showing_choices = false
	_choices_box.visible = false
	_root.visible = false   # 对话结束，回到场景（不再停留在聊天界面）


# ── UI 构建 ──
func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.gui_input.connect(_on_root_input)
	add_child(_root)

	# 背景
	var bg := ColorRect.new()
	bg.color = C_BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(bg)

	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(vbox)

	# 顶部状态栏（48px）
	vbox.add_child(_make_statusbar())

	# 消息区（滚动）
	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(_scroll)

	_msg_vbox = VBoxContainer.new()
	_msg_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_msg_vbox.add_theme_constant_override("separation", 16)
	_scroll.add_child(_msg_vbox)

	# 选项区（默认隐藏）
	_choices_box = HBoxContainer.new()
	_choices_box.add_theme_constant_override("separation", 12)
	_choices_box.visible = false
	vbox.add_child(_choices_box)

	# 底部输入区（54px，占位）
	vbox.add_child(_make_inputbar())


func _make_statusbar() -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 48)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color("#FFF3E0")   # 浅暖橙底，与纯白消息区区分，状态栏一眼可见
	sb.border_color = C_LINE
	sb.border_width_bottom = 1
	sb.content_margin_left = 24
	sb.content_margin_right = 24
	panel.add_theme_stylebox_override("panel", sb)

	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 12)
	panel.add_child(bar)

	_name_label = Label.new()
	_name_label.add_theme_font_size_override("font_size", 20)
	_name_label.add_theme_color_override("font_color", Color("#5D4037"))
	_name_label.text = "林默 · 你的AI陪伴"
	_name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(_name_label)

	# W3：未读红点（AI 推送新消息时显示数字；打开界面后清零）
	_unread_badge = Label.new()
	_unread_badge.add_theme_font_size_override("font_size", 14)
	_unread_badge.add_theme_color_override("font_color", Color.WHITE)
	_unread_badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_unread_badge.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_unread_badge.custom_minimum_size = Vector2(22, 22)
	_unread_badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var bsb := StyleBoxFlat.new()
	bsb.bg_color = C_ACCENT
	bsb.set_corner_radius_all(11)
	_unread_badge.add_theme_stylebox_override("normal", bsb)
	_unread_badge.visible = false
	bar.add_child(_unread_badge)

	# 信号三点（8px，可见）
	for i in 3:
		var dot := ColorRect.new()
		dot.custom_minimum_size = Vector2(8, 8)
		dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		dot.color = C_TEXT_MID
		bar.add_child(dot)
	return panel


func _make_inputbar() -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 54)
	var sb := StyleBoxFlat.new()
	sb.bg_color = C_BG
	sb.border_color = C_LINE
	sb.border_width_top = 1
	sb.content_margin_left = 24
	sb.content_margin_right = 24
	sb.content_margin_top = 7
	sb.content_margin_bottom = 7
	panel.add_theme_stylebox_override("panel", sb)

	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 12)
	panel.add_child(bar)

	# W3：真实可输入框（替代 W2 占位）
	_input_line = LineEdit.new()
	_input_line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_input_line.custom_minimum_size = Vector2(0, 40)
	_input_line.placeholder_text = "和 AI 说点什么…"
	_input_line.max_length = 200
	_input_line.text_submitted.connect(_on_text_submitted)
	bar.add_child(_input_line)

	_send_button = Button.new()
	_send_button.text = "发送"
	_send_button.custom_minimum_size = Vector2(90, 40)
	_send_button.add_theme_font_size_override("font_size", 16)
	var btn_sb := StyleBoxFlat.new()
	btn_sb.bg_color = C_ACCENT
	btn_sb.set_corner_radius_all(8)
	_send_button.add_theme_stylebox_override("normal", btn_sb)
	_send_button.add_theme_color_override("font_color", C_PLAYER_TEXT)
	_send_button.pressed.connect(_send_current_input)
	_send_button.disabled = true
	bar.add_child(_send_button)

	_input_line.text_changed.connect(func(_t: String) -> void:
		_send_button.disabled = _input_line.text.strip_edges().is_empty()
	)
	return panel


func _make_button(text: String, outline: bool) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.custom_minimum_size = Vector2(120, 40)
	btn.add_theme_font_size_override("font_size", 16)
	var sb := StyleBoxFlat.new()
	sb.set_corner_radius_all(8)
	if outline:
		sb.bg_color = C_BG
		sb.border_color = C_AI_BUBBLE
		sb.set_border_width_all(1)
		btn.add_theme_color_override("font_color", C_AI_BUBBLE)
	else:
		sb.bg_color = C_AI_BUBBLE
		btn.add_theme_color_override("font_color", C_AI_TEXT)
	btn.add_theme_stylebox_override("normal", sb)
	return btn


func _make_choice_button(text: String, index: int) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.custom_minimum_size = Vector2(0, 44)
	btn.add_theme_font_size_override("font_size", 20)
	var sb := StyleBoxFlat.new()
	sb.bg_color = C_BG
	sb.border_color = C_AI_BUBBLE
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(8)
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	btn.add_theme_stylebox_override("normal", sb)
	btn.add_theme_color_override("font_color", C_AI_BUBBLE)
	btn.pressed.connect(func() -> void: DialogManager.select_choice(index))
	return btn


func _make_row(bubble: PanelContainer, is_ai: bool, is_player: bool = false) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 12)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if is_ai:
		row.add_child(_make_avatar(is_ai))
		row.add_child(bubble)
		row.add_child(spacer)
	else:
		row.add_child(spacer)
		row.add_child(bubble)
		row.add_child(_make_avatar(is_ai, is_player))
	return row


func _make_avatar(is_ai: bool, is_player: bool = false) -> Panel:
	var p := Panel.new()
	p.custom_minimum_size = Vector2(40, 40)
	var sb := StyleBoxFlat.new()
	if is_ai:
		sb.bg_color = C_AI_BUBBLE
	elif is_player:
		sb.bg_color = C_ACCENT
	else:
		sb.bg_color = Color("#999999")
	sb.set_corner_radius_all(20)
	p.add_theme_stylebox_override("panel", sb)
	return p


func _make_bubble(is_ai: bool, is_player: bool = false) -> PanelContainer:
	var pc := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	if is_player:
		sb.bg_color = C_PLAYER_BUBBLE
	else:
		sb.bg_color = C_AI_BUBBLE if is_ai else C_FRIEND_BUBBLE
	sb.set_corner_radius_all(16)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 12
	sb.content_margin_bottom = 12
	pc.add_theme_stylebox_override("panel", sb)
	return pc


func _bubble_label(bubble: PanelContainer) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", 18)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(800, 0)
	bubble.add_child(label)
	return label


func _clear_messages() -> void:
	for child in _msg_vbox.get_children():
		child.queue_free()
	_choices_box.visible = false


func _scroll_to_bottom() -> void:
	_scroll.scroll_vertical = int(_msg_vbox.get_combined_minimum_size().y)


func _on_root_input(event: InputEvent) -> void:
	if not _root.visible:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if not _showing_choices:
			DialogManager.advance()


# ────────────────────────────────────────────────────────────────────────────
# W3：自由输入 + AI 主动推送
# ────────────────────────────────────────────────────────────────────────────

## 玩家按回车 / 点发送：渲染玩家气泡 → 请求 LLM 回复
func _send_current_input() -> void:
	var text := _input_line.text.strip_edges()
	if text.is_empty():
		return
	_input_line.text = ""
	_send_button.disabled = true
	# 立即渲染玩家消息（右侧浅蓝气泡）
	_on_line("player", "我", text)
	_history.append("我：" + text)
	_request_llm_reply(text)


func _on_text_submitted(_text: String) -> void:
	_send_current_input()


## 通过 C↔A 适配层请求 AI 回复（LLM 骨架期走 fallback；W4 接真后自动生效）
## 适配层返回 {dialogue_id: {lines:[...]}}，逐条渲染为 AI 气泡
func _request_llm_reply(player_text: String) -> void:
	var context := "玩家在 AI 聊天界面发来消息：" + player_text
	var summary := "；".join(_history)
	var table := LLMDialogueAdapter.generate(
		"AI_REPLY_%d" % _reply_seq,
		"chat_app",
		_npc_name,
		_speaker_name,
		context,
		summary,
	)
	_reply_seq += 1
	if table.is_empty():
		return
	var data: Dictionary = table.values()[0]
	for line in data.get("lines", []):
		_on_line("ai", line.get("name", _npc_name), line.get("text", ""))


## AI 主动推送一条消息（场景/氛围系统调用）：
## 界面可见 → 立即渲染为 AI 气泡；界面隐藏 → 未读 +1 + 暂存（打开后补显示）
func push_ai_message(text: String, name: String = "林默") -> void:
	if _root.visible:
		_on_line("ai", name, text)
		return
	_pending_messages.append({"text": text, "name": name})
	_unread_count += 1
	_update_unread()


## W3：T 键打开聊天 App（探索中常驻）。打开时补渲染暂存消息 + 清未读。
func _open_chat() -> void:
	if _root.visible:
		return
	_root.visible = true
	for m in _pending_messages:
		_on_line("ai", m.get("name", "林默"), m.get("text", ""))
	_pending_messages.clear()
	_clear_unread()
	_input_line.grab_focus()


func _close_chat() -> void:
	if not _root.visible:
		return
	_root.visible = false
	_input_line.release_focus()


## W3：场景切换后 AI 主动推一条（模拟 A 大纲 3.1"AI 主动聊天"）——每个场景只推一次
func _on_scene_changed(target_path: String) -> void:
	if _pushed_scenes.has(target_path):
		return
	_pushed_scenes[target_path] = true
	var hints := {
		"res://scenes/coffee_shop.tscn": "逛累了可以坐下来歇歇。那个靠窗的位置，还给你留着。",
		"res://scenes/classroom.tscn": "教室里好像还有不少东西。你想看看吗？",
		"res://scenes/dormitory.tscn": "宿舍还是老样子。那盆绿植，有人一直在照看它。",
		"res://scenes/street.tscn": "这条路你走过很多遍。今天也走走吧。",
	}
	var hint: String = hints.get(target_path, "我一直在。想聊的时候，说一声就行。")
	push_ai_message(hint)


func _clear_unread() -> void:
	_unread_count = 0
	_update_unread()


func _update_unread() -> void:
	if _unread_badge == null:
		return
	if _unread_count <= 0:
		_unread_badge.visible = false
		return
	_unread_badge.visible = true
	_unread_badge.text = str(_unread_count)
