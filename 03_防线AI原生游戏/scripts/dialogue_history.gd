# dialogue_history.gd —— 对话历史回顾（Autoload 常驻）
# W4 交付物之一：记录 DialogManager 播放过的所有对白行，H 键随时打开回顾面板。
# W5③ 优化：加搜索过滤 + 命中高亮；修重建时的双重布局卡顿；新行自动滚到底。
#
# 设计：
#   - 常驻 Autoload，跨场景累积，保留最近 MAX_ENTRIES 条（先进先出）。
#   - 订阅 DialogManager.line_shown 增量记录，不修改 DialogManager / 各 UI。
#   - H 键开合面板；面板为全屏只读滚动列表（ESC / 关闭按钮 / H 关闭）。
#   - 搜索框按关键词过滤（对白文本 + 说话人），命中处高亮；空串＝显示全部。
#
# 颜色沿用对话四模式约定：ai=暖橙 / player=浅蓝 / friend=灰 / 其它=白。
# 层叠：layer 12（低于 MemoryAnchorUI 20、SceneManager 黑幕 100）。
#
# 注意：本文件函数按"先定义后调用"排列（GDScript 对下划线私有函数
# 有引用顺序限制，见本会话 dev 测试踩坑），_ready 放在文件末尾。

extends CanvasLayer

const MAX_ENTRIES := 300
const C_AI_TEXT    := Color("#FFB74D")
const C_PLAYER_TEXT := Color("#4FC3F7")
const C_FRIEND_TEXT := Color("#BBBBBB")
const C_OTHER_TEXT  := Color("#EEEEEE")
const C_PANEL_BG    := Color(0.10, 0.10, 0.13, 0.96)
const C_TITLE       := Color("#FFB74D")
const C_HILITE      := "#FFD54F"      # 搜索命中高亮色（BBCode）

var _root: Control            # 整屏根（遮罩 + 面板）
var _list_vbox: VBoxContainer
var _scroll: ScrollContainer
var _count_label: Label
var _search_edit: LineEdit
var _entries: Array = []      # [{speaker, name, text}] 按时间序，[0] 最早
var _filter: String = ""      # 当前搜索关键词（已去空白 + 小写）


# ── 查询接口（供调试 / 断言 / 未来回溯 UI）──

func get_history() -> Array:
	return _entries.duplicate(true)


func get_entry_count() -> int:
	return _entries.size()


## 把一条历史渲染成纯文本行（外部回溯/导出用，含说话人）
func format_entry(entry: Dictionary) -> String:
	var who: String = entry.get("name", "")
	if who.is_empty():
		who = entry.get("speaker", "")
	if who.is_empty():
		return entry.get("text", "")
	return "%s：%s" % [who, entry.get("text", "")]


## 当前过滤下可见的条目数（供测试断言）
func get_visible_count() -> int:
	if _filter.is_empty():
		return _entries.size()
	var n := 0
	for e in _entries:
		if _matches(e):
			n += 1
	return n


## 设置搜索关键词（外部/测试用；面板内输入框走 _on_search_changed）
func set_filter(text: String) -> void:
	_filter = text.strip_edges().to_lower()
	if _search_edit != null and _search_edit.text != text:
		_search_edit.text = text
	if _root != null and _root.visible:
		_refresh_all()


# ── 过滤 / 高亮 ──

## 条目是否命中当前关键词：对白文本 + 说话人名，任一包含即算
func _matches(entry: Dictionary) -> bool:
	if _filter.is_empty():
		return true
	var hay := ("%s %s %s" % [
		entry.get("text", ""), entry.get("name", ""), entry.get("speaker", "")
	]).to_lower()
	return hay.contains(_filter)


## BBCode 转义：对白里可能出现 [ ]，不转义会被当成标签吃掉
func _escape_bbcode(s: String) -> String:
	return s.replace("[", "[lb]")


## 把命中关键词包上高亮色（大小写不敏感，逐段扫描）
func _highlight(text: String) -> String:
	var safe := _escape_bbcode(text)
	if _filter.is_empty():
		return safe
	var lower := safe.to_lower()
	var out := ""
	var cursor := 0
	while true:
		var idx := lower.find(_filter, cursor)
		if idx < 0:
			out += safe.substr(cursor)
			break
		out += safe.substr(cursor, idx - cursor)
		out += "[color=%s][b]%s[/b][/color]" % [C_HILITE, safe.substr(idx, _filter.length())]
		cursor = idx + _filter.length()
	return out


# ── 颜色映射（被 _add_row 调用，置于其前）──

func _color_for(speaker: String) -> Color:
	if speaker == "ai":
		return C_AI_TEXT
	elif speaker == "player":
		return C_PLAYER_TEXT
	elif speaker == "friend":
		return C_FRIEND_TEXT
	return C_OTHER_TEXT


# ── 列表渲染层 ──

## 追加一行可见条目（新消息实时滚入）
## 用 RichTextLabel 而非 Label：高亮要把命中片段染色，Label 做不到。
func _add_row(speaker: String, name: String, text: String) -> void:
	var row := RichTextLabel.new()
	row.bbcode_enabled = true
	row.fit_content = true          # 随内容撑高，否则在 VBox 里高度为 0
	row.scroll_active = false       # 滚动交给外层 ScrollContainer
	row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_font_size_override("normal_font_size", 18)
	var who := name if not name.is_empty() else speaker
	var body := _highlight(text)
	var line := ("%s：%s" % [_escape_bbcode(who), body]) if not who.is_empty() else body
	row.text = "[color=#%s]%s[/color]" % [
		_color_for(speaker).to_html(false), line
	]
	_list_vbox.add_child(row)


## 打开面板 / 改关键词时全量重建。
## 刻意用 remove_child + free 而不是 queue_free：queue_free 的节点要到帧末才消失，
## 重建 300 条时会短暂挂着 600 个子节点并触发两次布局 —— 这正是"滚动卡"的来源。
func _refresh_all() -> void:
	for child in _list_vbox.get_children():
		_list_vbox.remove_child(child)
		child.free()
	var shown := 0
	for e in _entries:
		if not _matches(e):
			continue
		_add_row(e.get("speaker", ""), e.get("name", ""), e.get("text", ""))
		shown += 1
	_update_count(shown)


func _update_count(shown: int) -> void:
	if _count_label == null:
		return
	if _filter.is_empty():
		_count_label.text = "共 %d 条" % _entries.size()
	elif shown == 0:
		_count_label.text = "无匹配 —— 换个词试试"
	else:
		_count_label.text = "匹配 %d / %d 条" % [shown, _entries.size()]


## 滚到底部（最新一条）。必须等一帧，否则 VBox 还没重新布局，max_value 是旧值。
func _scroll_to_bottom() -> void:
	if _scroll == null:
		return
	await get_tree().process_frame
	_scroll.scroll_vertical = int(_scroll.get_v_scroll_bar().max_value)


# ── 记录层 ──

## 追加一行历史（FIFO，超上限丢最旧）
func _append_line(speaker: String, name: String, text: String) -> void:
	if text.strip_edges().is_empty():
		return
	_entries.append({
		"speaker": speaker,
		"name": name,
		"text": text,
		"time": Time.get_ticks_msec(),
	})
	if _entries.size() > MAX_ENTRIES:
		_entries.remove_at(0)


# ── 面板开关 ──

func _open() -> void:
	if _root.visible:
		return
	_refresh_all()
	_root.visible = true
	_scroll_to_bottom()


func _close() -> void:
	if not _root.visible:
		return
	_root.visible = false


func _toggle() -> void:
	if _root.visible:
		_close()
	else:
		_open()


# ── 事件 / 输入（连接在 _ready，文本上后于所调用函数）──

func _on_search_changed(new_text: String) -> void:
	_filter = new_text.strip_edges().to_lower()
	_refresh_all()
	_scroll_to_bottom()


func _on_line_shown(speaker: String, name: String, text: String) -> void:
	_append_line(speaker, name, text)
	if _root == null or not _root.visible:
		return
	# 面板开着时实时追加；但当前有搜索词且这条不匹配，就不塞进列表
	if _filter.is_empty():
		_add_row(speaker, name, text)
		_update_count(_list_vbox.get_child_count())
		_scroll_to_bottom()
	elif _matches(_entries.back()):
		_add_row(speaker, name, text)
		_update_count(_list_vbox.get_child_count())
		_scroll_to_bottom()
	else:
		_update_count(_list_vbox.get_child_count())


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	if event.keycode == KEY_H:
		_toggle()
	elif event.keycode == KEY_ESCAPE and _root != null and _root.visible:
		_close()


# ── UI 构建（_ready 直接调用，置于 _ready 前）──

func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)

	# 背景遮罩（点击面板外区域不穿透到场景热点）
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.45)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.add_child(shade)

	# 居中面板
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -560
	panel.offset_right = 560
	panel.offset_top = -420
	panel.offset_bottom = 420
	var psb := StyleBoxFlat.new()
	psb.bg_color = C_PANEL_BG
	psb.set_corner_radius_all(12)
	psb.border_color = C_TITLE
	psb.set_border_width_all(1)
	panel.add_theme_stylebox_override("panel", psb)
	_root.add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)

	# 顶栏：标题 + 计数 + 提示 + 关闭
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 16)
	vbox.add_child(bar)

	var title := Label.new()
	title.text = "对话历史"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", C_TITLE)
	bar.add_child(title)

	_count_label = Label.new()
	_count_label.add_theme_font_size_override("font_size", 15)
	_count_label.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7))
	_count_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_count_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.add_child(_count_label)

	var tip := Label.new()
	tip.text = "H / ESC 关闭"
	tip.add_theme_font_size_override("font_size", 15)
	tip.add_theme_color_override("font_color", Color(0.6, 0.6, 0.65))
	tip.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.add_child(tip)

	var close_btn := Button.new()
	close_btn.text = "关闭"
	close_btn.pressed.connect(_close)
	bar.add_child(close_btn)

	# 搜索栏
	var search_bar := HBoxContainer.new()
	search_bar.add_theme_constant_override("separation", 10)
	vbox.add_child(search_bar)

	var search_icon := Label.new()
	search_icon.text = "搜索"
	search_icon.add_theme_font_size_override("font_size", 16)
	search_icon.add_theme_color_override("font_color", Color(0.7, 0.7, 0.75))
	search_icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	search_bar.add_child(search_icon)

	_search_edit = LineEdit.new()
	_search_edit.placeholder_text = "输入关键词，回车跳到最新一条"
	_search_edit.clear_button_enabled = true
	_search_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_search_edit.add_theme_font_size_override("font_size", 16)
	_search_edit.text_changed.connect(_on_search_changed)
	_search_edit.text_submitted.connect(func(_t: String) -> void: _scroll_to_bottom())
	search_bar.add_child(_search_edit)

	# 滚动列表
	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	vbox.add_child(_scroll)

	_list_vbox = VBoxContainer.new()
	_list_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list_vbox.add_theme_constant_override("separation", 6)
	_scroll.add_child(_list_vbox)


# ── 入口（置于末尾：所有被调用的私有函数均已定义）──

func _ready() -> void:
	layer = 12
	_build_ui()
	_root.visible = false
	DialogManager.line_shown.connect(_on_line_shown)
	print("[DialogueHistory] 启动，已订阅对话行信号")
