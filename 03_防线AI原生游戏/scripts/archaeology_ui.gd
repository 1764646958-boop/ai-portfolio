# archaeology_ui.gd —— 记忆考古战斗 UI（Autoload 常驻，layer 30）
# W4 ②③ 交付宿主：消费 MemoryArchaeology 信号，按关卡难度切输入玩法层：
#   LEVEL 1（手链/70%）→ mode1 三卡选择 + 3s 读秒后决定
#   LEVEL 2（玫瑰/50%）→ mode2 碎片拖拽入光门（真相碎片重/慢，假碎片轻/顺滑）
#   LEVEL 3（花朵/30%）→ mode3 双按钮 QTE（限时点中真相按钮）
# 内置 ③ 四项 UI 动画（全 GPU transform/opacity，D 资产到位只换纹理）：
#   记忆卡片翻转 / 计时条抖动 / 碎片选中高光 / 选项悬停
# 判定仍走 MemoryArchaeology.choose()：真相 = variant_id == "truth"。
# 阻力/时间窗/灵敏度全部读 config/qte_params.json —— A/B 压迫参数终稿覆写即生效。
#
# 注意：本文件所有私有函数按"被调用者在前"排列（GDScript 下划线顺序坑），
#       _ready 在文件末尾。占位色块，D 交付切图后替换。

extends CanvasLayer

# ── 颜色 Token（与 ui_design_spec 冷暖二元一致）──
const C_TRUTH_WARM := Color("#FFB74D")    # 真相/真实记忆 = 微弱暖橙残留
const C_FAKE_COLD  := Color("#7FB3C8")    # 假碎片 = 冷蓝（占位用淡蓝便于辨认）
const C_BG_SHADE   := Color(0.03, 0.05, 0.10, 0.86)
const C_TITLE      := Color("#FFB74D")
const C_TEXT       := Color("#FFFFFF")
const C_HINT       := Color(0.7, 0.75, 0.8)
const C_BAR_OK     := Color("#9CCC65")
const C_BAR_WARN   := Color("#FFCA28")
const C_BAR_DANGER := Color("#EF5350")
const C_TRUTH_HINT := Color(1.0, 0.72, 0.45, 0.9)
const C_EXIT_ZONE  := Color(0.55, 0.9, 0.8, 0.16)

const QTE_PARAMS_PATH := "res://config/qte_params.json"
const LAYER := 30   # 高于 MemoryAnchorUI(20)/DialogueHistory(12)，低于 SceneManager 黑幕(100)

## 调试热键开关：F1/F2/F3 开考古关卡1/2/3、F4 中止（正式入口接入后置 false）
const DEBUG_HOTKEYS := true

# 卡片/碎片统一尺寸
const SHARD_SIZE := Vector2(280, 120)

# ── 运行时状态 ──
var _params: Dictionary = {}
var _level: int = 1
var _mode: int = 1
var _variants: Array = []

var _root: Control
var _title_label: Label
var _intro_label: Label       # 渐暗后"主人公想起什么"的引子（策划稿 §4.2②）
var _countdown_label: Label
var _bar_shown_color: Color = Color.WHITE   # 计时条当前显示色（逐帧逼近目标色，避免阈值处硬切）
var _countdown_urgent: bool = false
var _countdown_pulse: Tween
var _hint_label: Label
var _bar: ColorRect          # 行动窗口条（可抖动，只动 position）
var _bar_frame: Control      # 条外框：随窗口缩放；条在框内从左生长
var _exit_zone: Control
var _exit_zone_rect := Rect2()
var _flash_rect: ColorRect
var _content: Control

var _drag_active_id: String = ""
var _shards: Array = []      # [{id, control, origin}]
var _action_remaining: float = 0.0
var _action_total: float = 0.0
var _choice_made: bool = false
var _content_finished: bool = false

var _intro_active: bool = false  # 引子期间：卡片延迟翻转、读秒不显示
var _intro_delay: float = 0.0    # 引子时长，作为卡片翻转入场延迟
var _timed_out: bool = false     # 超时收尾：结果文案走"默认接受假记忆"分支
var _tier: Dictionary = {"window_scale": 1.0, "truth_follow_scale": 1.0, "label": ""}


# ── 纯辅助 ──

func _variant(id: String) -> Dictionary:
	for v in _variants:
		if v.get("variant_id", "") == id:
			return v
	return {}


func _is_truth(id: String) -> bool:
	return _variant(id).get("is_truth", false)


func _warm_or_cold(id: String) -> Color:
	return C_TRUTH_WARM if _is_truth(id) else C_FAKE_COLD


## QTE(难度3)配对：真相 + 最接近真相的假(micro_drift，无则 neg_distortion)
func _qte_pair() -> Array:
	var truth_id := ""
	var near_id := ""
	for v in _variants:
		if v.get("is_truth", false):
			truth_id = v["variant_id"]
		elif v.get("variant_id", "") == "micro_drift":
			near_id = v["variant_id"]
	if truth_id.is_empty():
		return []
	if near_id.is_empty():
		for v in _variants:
			if not v.get("is_truth", false):
				near_id = v["variant_id"]
				break
	return [truth_id, near_id]


## 当前信任档位对应的难度修正（策划稿 §4.3：越偏 AI，假记忆越隐蔽）
## 返回 {"window_scale": float, "truth_follow_scale": float, "label": String}
func _tier_mod() -> Dictionary:
	var table: Dictionary = _params.get("difficulty_by_tier", {})
	var tier: String = TrustDrift.get_trust_tier()
	var m = table.get(tier, {})
	if typeof(m) != TYPE_DICTIONARY:
		m = {}
	return {
		"window_scale": float(m.get("window_scale", 1.0)),
		"truth_follow_scale": float(m.get("truth_follow_scale", 1.0)),
		"label": String(m.get("label", "")),
	}


## 引子（转场）时长与文案：关卡号 → lines；无则回退 mode1 的 1.4s / 空串
func _intro_secs() -> float:
	return maxf(float(_params.get("intro", {}).get("secs", 0.0)), 0.0)


func _intro_line(level: int) -> String:
	var lines: Dictionary = _params.get("intro", {}).get("lines", {})
	return String(lines.get(str(level), ""))


# ── 动画原语（只动 transform/opacity，GPU 友好；③ 交付项）──

func _tween_scale(ctrl: Control, to: float, secs: float) -> void:
	var t := ctrl.create_tween()
	t.tween_property(ctrl, "scale", Vector2(to, to), secs).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


## 记忆卡片翻转：scale.x 0→1 + 轻微 alpha 淡入（伪 3D 翻牌）
func _flip_in(ctrl: Control, delay: float) -> void:
	ctrl.pivot_offset = ctrl.size / 2.0
	ctrl.scale = Vector2(0.01, 1.0)
	ctrl.modulate.a = 0.0
	var t := ctrl.create_tween()
	t.tween_interval(_intro_delay + delay)   # 转场：先黑屏听引子，再逐张翻出
	t.tween_property(ctrl, "scale:x", 1.0, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.parallel().tween_property(ctrl, "modulate:a", 1.0, 0.22)


## 选项/碎片悬停 + 选中高光（mouse_entered/exited，scale 1.06）
## 悬停 tween 必须"先杀旧再建新"：来回快速划过多张卡片时，
## 前一个 tween 仍在跑同一个 scale 属性，两个 tween 互相拉扯 → 卡片抖动/卡在半路。
func _hover_tween(ctrl: Control, to: float, secs: float) -> void:
	var prev = ctrl.get_meta("_hover_tween", null)
	if prev is Tween and prev.is_valid():
		prev.kill()
	var t := ctrl.create_tween()
	t.tween_property(ctrl, "scale", Vector2(to, to), secs).set_trans(Tween.TRANS_SINE)
	ctrl.set_meta("_hover_tween", t)


## 选项/碎片悬停 + 选中高光（mouse_entered/exited，scale 1.06）
func _bind_hover(ctrl: Control) -> void:
	var hover: float = float(_params.get("anim", {}).get("hover_scale", 1.06))
	ctrl.mouse_entered.connect(func() -> void:
		if _choice_made or not _drag_active_id.is_empty():
			return
		_hover_tween(ctrl, hover, 0.12)
	)
	ctrl.mouse_exited.connect(func() -> void:
		if _choice_made or not _drag_active_id.is_empty():
			return
		_hover_tween(ctrl, 1.0, 0.12)
	)


## 行动窗口条颜色：剩余占比 → 绿/黄/红
func _bar_color(ratio: float) -> Color:
	if ratio > 0.5:
		return C_BAR_OK
	elif ratio > 0.25:
		return C_BAR_WARN
	return C_BAR_DANGER


# ── 组件构造 ──

func _styled_button(text: String, tint: Color) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.add_theme_font_size_override("font_size", 18)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.border_color = tint
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(10)
	sb.content_margin_left = 18
	sb.content_margin_right = 18
	sb.content_margin_top = 10
	sb.content_margin_bottom = 10
	btn.add_theme_stylebox_override("normal", sb)
	btn.add_theme_stylebox_override("hover", sb)
	btn.add_theme_color_override("font_color", tint)
	btn.add_theme_color_override("font_hover_color", Color.WHITE)
	return btn


func _make_card(id: String) -> Button:
	var v: Dictionary = _variant(id)
	var tint := _warm_or_cold(id)
	var btn := _styled_button(v.get("text", ""), tint)
	btn.custom_minimum_size = Vector2(300, 150)
	btn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.pressed.connect(_on_card_pressed.bind(id))
	btn.gui_input.connect(_on_widget_input.bind(id))
	_bind_hover(btn)
	return btn


func _make_shard(id: String) -> Control:
	var v: Dictionary = _variant(id)
	var tint := _warm_or_cold(id)
	var shard := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(tint.r, tint.g, tint.b, 0.18)
	sb.border_color = tint
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(12)
	shard.add_theme_stylebox_override("panel", sb)
	var label := Label.new()
	label.text = v.get("text", "")
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", 15)
	label.add_theme_color_override("font_color", C_TEXT)
	label.size = SHARD_SIZE - Vector2(24, 20)
	label.position = Vector2(12, 8)
	shard.add_child(label)
	shard.mouse_filter = Control.MOUSE_FILTER_STOP
	shard.size = SHARD_SIZE
	shard.gui_input.connect(_on_widget_input.bind(id))
	_bind_hover(shard)
	return shard


func _make_qte_button(id: String, label_text: String) -> Button:
	var v: Dictionary = _variant(id)
	var tint := _warm_or_cold(id)
	var btn := _styled_button(label_text, tint)
	btn.custom_minimum_size = Vector2(0, 90)
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.add_theme_font_size_override("font_size", 20)
	btn.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	btn.pressed.connect(_on_card_pressed.bind(id))
	_bind_hover(btn)
	return btn


# ── 模式布局（每次开局重置 _content）──

func _clear_content() -> void:
	for child in _content.get_children():
		child.queue_free()
	_shards.clear()
	_choice_made = false
	_content_finished = false
	_drag_active_id = ""
	_exit_zone.visible = false
	_action_total = 0.0
	_bar.visible = false
	_countdown_label.visible = false
	_intro_active = false
	_intro_delay = 0.0
	_timed_out = false
	_tier = _tier_mod()
	_intro_label.text = ""
	_intro_label.visible = false


## mode1：三张卡横排在内容区中央
func _setup_mode1() -> void:
	var hbox := HBoxContainer.new()
	hbox.set_anchors_preset(Control.PRESET_CENTER)
	hbox.offset_left = -720
	hbox.offset_right = 720
	hbox.offset_top = -180
	hbox.offset_bottom = 180
	hbox.add_theme_constant_override("separation", 24)
	_content.add_child(hbox)
	var i := 0
	for v in _variants:
		var card := _make_card(v["variant_id"])
		hbox.add_child(card)
		_flip_in(card, 0.08 * i)
		i += 1


## mode2：光门在屏幕上方中央(窗口坐标)，碎片在下方；绝对定位用 size+position
func _setup_mode2() -> void:
	var p2: Dictionary = _params.get("mode2_drag", {})
	_position_exit_zone(p2.get("exit_zone", {}))
	var slots: Array = p2.get("shard_base_positions", [])
	var i := 0
	for v in _variants:
		var id: String = v["variant_id"]
		var shard := _make_shard(id)
		_content.add_child(shard)
		var slot: Vector2 = Vector2(960, 700)
		if slots.size() > 0:
			var b: Dictionary = slots[min(i, slots.size() - 1)]
			slot = Vector2(float(b.get("x", 960)), float(b.get("y", 700)))
		var origin := slot - SHARD_SIZE / 2.0
		shard.global_position = origin
		_shards.append({"id": id, "control": shard, "origin": origin})
		_flip_in(shard, 0.1 * i)
		i += 1


func _position_exit_zone(zone: Dictionary) -> void:
	var cx := float(zone.get("cx", 960))
	var cy := float(zone.get("cy", 260))
	var w := float(zone.get("w", 480))
	var h := float(zone.get("h", 130))
	_exit_zone_rect = Rect2(cx - w / 2.0, cy - h / 2.0, w, h)
	_exit_zone.size = Vector2(w, h)
	_exit_zone.global_position = _exit_zone_rect.position
	_exit_zone.visible = true


## mode3：真相按钮 + 最像的假按钮，A/B 随机左右
func _setup_mode3() -> void:
	var pair := _qte_pair()
	if pair.is_empty():
		return
	var left_first := randf() < 0.5
	var left_id: String = pair[0] if left_first else pair[1]
	var right_id: String = pair[1] if left_first else pair[0]
	var hbox := HBoxContainer.new()
	hbox.set_anchors_preset(Control.PRESET_CENTER)
	hbox.offset_left = -700
	hbox.offset_right = 700
	hbox.offset_top = -160
	hbox.offset_bottom = 160
	hbox.add_theme_constant_override("separation", 30)
	_content.add_child(hbox)
	var b1 := _make_qte_button(left_id, "A · " + _variant(left_id).get("text", ""))
	var b2 := _make_qte_button(right_id, "B · " + _variant(right_id).get("text", ""))
	b1.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(b1)
	hbox.add_child(b2)
	_flip_in(b1, 0.1)
	_flip_in(b2, 0.2)


# ── 交互：卡片 / QTE 提交 & 拖拽 ──

func _on_card_pressed(id: String) -> void:
	if _choice_made:
		return
	_submit(id)


func _submit(id: String) -> void:
	if MemoryArchaeology.get_state() != MemoryArchaeology.State.CHOOSING:
		return
	_choice_made = true
	MemoryArchaeology.choose(id)


## 拖拽起点：mode2 且已进入可作答阶段时，按在碎片上开始拖动
func _on_widget_input(event: InputEvent, id: String) -> void:
	if _mode != 2 or _choice_made:
		return
	if MemoryArchaeology.get_state() != MemoryArchaeology.State.CHOOSING:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_drag_active_id = id
		_hint_label.text = "拖住碎片送进光门——真相碎片更沉"
		_hint_label.add_theme_color_override("font_color", C_TRUTH_HINT)


## 调试热键：F1/F2/F3 直接开考古关卡 1/2/3，F4 中止当前关卡。
## B 把正式入口（锚点/场景热点）接进 MemoryArchaeology.start_level() 后，把 DEBUG_HOTKEYS 置 false 即可。
func _handle_debug_key(keycode: int) -> void:
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit:
		return                      # 正在输入框打字，不抢键
	var st: int = MemoryArchaeology.get_state()
	if keycode == KEY_F4:
		if st == MemoryArchaeology.State.COUNTDOWN or st == MemoryArchaeology.State.CHOOSING:
			MemoryArchaeology.abort()
		return
	var level := 0
	match keycode:
		KEY_F1: level = 1
		KEY_F2: level = 2
		KEY_F3: level = 3
	if level == 0:
		return
	if st != MemoryArchaeology.State.IDLE and st != MemoryArchaeology.State.ENDED:
		return                      # 已有一关在进行中（避免半途重入）
	print("[ArchaeologyUI] 调试热键：开始考古关卡 %d" % level)
	MemoryArchaeology.start_level(level)


## 全局松开：无论落在哪个控件上都触发判定/回弹（_input 先于 GUI 消费）
func _input(event: InputEvent) -> void:
	if DEBUG_HOTKEYS and event is InputEventKey and event.pressed and not event.echo:
		_handle_debug_key(event.keycode)
		return
	if _mode != 2 or _drag_active_id.is_empty():
		return
	if event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_drop_shard()


func _drop_shard() -> void:
	if _drag_active_id.is_empty():
		return
	var mouse := _root.get_global_mouse_position()
	var released_id := _drag_active_id
	_drag_active_id = ""
	if _exit_zone_rect.has_point(mouse):
		_submit(released_id)          # 拖进光门 → 判定
		return
	for entry in _shards:             # 未进光门：回弹原点
		if entry["id"] == released_id:
			var tween: Tween = entry["control"].create_tween()
			tween.tween_property(entry["control"], "global_position", entry["origin"], 0.18)
			return


## 拖拽跟随：真相 truth_follow(慢/沉)，假碎片 fake_follow(快/顺滑)
func _update_drag() -> void:
	if _drag_active_id.is_empty():
		return
	var target := _root.get_global_mouse_position()
	var is_t := _is_truth(_drag_active_id)
	var follow: float = float(_params.get("mode2_drag", {}).get("fake_follow", 0.55))
	if is_t:
		follow = float(_params.get("mode2_drag", {}).get("truth_follow", 0.10))
		follow *= float(_tier["truth_follow_scale"])   # 越偏 AI，真相碎片越沉
	for entry in _shards:
		if entry["id"] == _drag_active_id:
			var c: Control = entry["control"]
			c.global_position = c.global_position.lerp(target - SHARD_SIZE / 2.0, follow)
			return


# ── 行动窗口（读秒后倒计时 + 抖动）──

func _start_action_window(secs: float) -> void:
	_action_total = maxf(secs, 0.2)
	_action_remaining = _action_total
	_bar.visible = true
	_bar.position = Vector2.ZERO
	_bar_shown_color = C_BAR_OK      # 新窗口从满血绿起步，不带上一局的残留色
	_update_bar(1.0)


## delta 用于颜色平滑：直接赋 _bar_color(ratio) 会在阈值处"啪"地跳色，
## 逐帧 lerp 逼近目标色，绿→黄→红的过渡才连贯。
func _update_bar(ratio: float, delta: float = 0.016) -> void:
	_bar.size.x = _bar_frame.size.x * clampf(ratio, 0.0, 1.0)
	var target := _bar_color(ratio)
	if _bar_shown_color != target:
		_bar_shown_color = _bar_shown_color.lerp(target, clampf(delta * 12.0, 0.0, 1.0))
	_bar.color = _bar_shown_color


## 抖动幅度（px）：剩余时间从阈值走到 0 的过程中，幅度 0 → timer_jitter_px 线性加剧。
## 原实现一越过阈值就恒定 ±5px，临超时那一刻反而没有更急的压迫感。
## 抽成纯函数是为了可被无头测试直接断言（sin(ticks) 的相位在测试里不可控）。
func _jitter_amp(remaining: float, below_secs: float) -> float:
	if below_secs <= 0.0 or remaining >= below_secs:
		return 0.0
	var k := 1.0 - clampf(remaining / below_secs, 0.0, 1.0)
	return float(_params.get("anim", {}).get("timer_jitter_px", 5.0)) * k


func _tick_action_window(delta: float) -> void:
	if _action_total <= 0.0:
		return
	_action_remaining -= delta
	var ratio := clampf(_action_remaining / _action_total, 0.0, 1.0)
	_update_bar(ratio, delta)
	# 计时条抖动：剩余 < 阈值 → 横向轻颤（动 position，transform 层；③ 交付项）
	var jitter_below: float = float(_params.get("anim", {}).get("timer_jitter_below_secs", 1.0))
	var amp := _jitter_amp(_action_remaining, jitter_below)
	if amp > 0.0:
		var k := 1.0 - clampf(_action_remaining / jitter_below, 0.0, 1.0)
		var freq_ms: float = 40.0 - 16.0 * k                                # 周期 40ms → 24ms
		_bar.position = Vector2(sin(Time.get_ticks_msec() / freq_ms) * amp, 0)
	else:
		_bar.position = Vector2.ZERO
	if _action_remaining <= 0.0:
		_action_remaining = 0.0
		_action_total = 0.0
		_bar.position = Vector2.ZERO
		_on_action_timeout()


## 行动窗口用尽且未作答 → 超时失败
func _on_action_timeout() -> void:
	if _choice_made or _content_finished:
		return
	_content_finished = true
	_timed_out = true             # 先打标：abort 同步 emit archaeology_ended，文案要用到
	if MemoryArchaeology.get_state() == MemoryArchaeology.State.CHOOSING:
		MemoryArchaeology.abort()     # abort 会 emit archaeology_ended → 走失败展示
	else:
		_close_level()


# ── 结果 / 收尾 ──

## 判定白屏（intensity:1=选对-轻 / 2=选错-强）；由 MemoryArchaeology.flash_triggered 驱动
func _play_flash(intensity: int) -> void:
	_flash_rect.visible = true
	_flash_rect.modulate.a = 0.0
	var peak: float = 0.9 if intensity >= 2 else 0.55
	var t := create_tween()
	t.tween_property(_flash_rect, "modulate:a", peak, 0.06)
	t.tween_property(_flash_rect, "modulate:a", 0.0, 0.45)
	t.tween_callback(func() -> void: _flash_rect.visible = false)


## 结果文案入场：淡入 + 轻微弹出。
## 只动 modulate/scale，不动 position —— _hint_label 在 VBoxContainer 里，
## 容器每次布局都会重写子节点 position，动画 position 会被直接抹掉。
func _animate_hint_in() -> void:
	if _hint_label == null:
		return
	_hint_label.modulate.a = 0.0
	_hint_label.pivot_offset = _hint_label.size / 2.0
	_hint_label.scale = Vector2(0.94, 0.94)
	var t := _hint_label.create_tween()
	t.set_parallel(true)
	t.tween_property(_hint_label, "modulate:a", 1.0, 0.22)
	t.tween_property(_hint_label, "scale", Vector2.ONE, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func _show_result(success: bool, timed_out: bool = false) -> void:
	if timed_out:
		# 策划稿 §4.4 阶段一：超时 ≠ 玩家选错，而是"没来得及反驳" → AI 默认你接受了假记忆
		_hint_label.text = "⌛ 超时 —— 你没有反驳，AI 默认你接受了它给的版本"
		_hint_label.add_theme_color_override("font_color", C_BAR_WARN)
	elif success:
		_hint_label.text = "✔ 你保住了这段记忆"
		_hint_label.add_theme_color_override("font_color", C_TRUTH_HINT)
	else:
		_hint_label.text = "✘ 这段记忆被改写了……"
		_hint_label.add_theme_color_override("font_color", C_BAR_DANGER)
	_countdown_label.visible = false
	_set_countdown_pulse(false)
	_animate_hint_in()
	# 1.6s 后淡出本层，留时间给 DialogManager/剧情接管
	var t := create_tween()
	t.tween_interval(1.6)
	t.tween_callback(_close_level)


func _close_level() -> void:
	_action_total = 0.0
	_bar.visible = false
	_content_finished = true
	_drag_active_id = ""
	_exit_zone.visible = false
	var t := create_tween()
	t.tween_property(_root, "modulate:a", 0.0, 0.25)
	t.tween_callback(func() -> void:
		_root.modulate.a = 1.0
		_root.visible = false
	)


# ── MemoryArchaeology 信号消费 ──

## 转场结束：收起引子，放出标题/提示条（计时到点或玩家提前可作答时触发，幂等）
func _end_intro() -> void:
	if not _intro_active:
		return
	_intro_active = false
	_intro_label.visible = false
	_title_label.visible = true
	_hint_label.visible = true


## 契约：level_started 一旦发出，本关必定开局（MemoryArchaeology.start_level 已在 emit 前
## 挡掉"进行中重复调用"）。因此这里可以放心清空重置，不会出现"UI 已重置但关卡没开"的空界面。
func _on_level_started(level: int, title: String, _anchor_id: String, difficulty_desc: String) -> void:
	_level = level
	_mode = level          # 关卡号即玩法模式（1 卡片 / 2 拖拽 / 3 QTE）
	_clear_content()
	_title_label.text = title
	_hint_label.text = "识别 %s" % difficulty_desc
	_hint_label.add_theme_color_override("font_color", C_HINT)
	_countdown_label.text = ""
	_countdown_urgent = false           # 新一关重置紧迫态，否则上一关的红字/脉冲会带进来
	_set_countdown_pulse(false)
	# 转场（策划稿 §4.2②：点击 → 屏幕渐暗 → 主人公想起什么 → 卡片浮现）
	_intro_delay = _intro_secs()
	_intro_label.text = _intro_line(level)
	_intro_active = _intro_delay > 0.0 and not _intro_label.text.is_empty()
	_intro_label.visible = _intro_active
	_intro_label.modulate.a = 0.0 if _intro_active else 1.0
	_title_label.visible = not _intro_active   # 引子期间只留一行独白，卡片随后翻出
	_hint_label.visible = not _intro_active
	_root.modulate.a = 0.0
	_root.visible = true
	var t := create_tween()
	t.tween_property(_root, "modulate:a", 1.0, 0.3)
	if _intro_active:
		var it := create_tween()
		it.tween_property(_intro_label, "modulate:a", 1.0, 0.5)
		it.tween_interval(maxf(_intro_delay - 0.5, 0.0))
		it.tween_callback(_end_intro)


func _on_variants_shown(variants: Array) -> void:
	_variants = variants
	match _mode:
		1:
			_setup_mode1()
		2:
			_setup_mode2()
		_:
			_setup_mode3()
	_countdown_label.visible = not _intro_active


## 倒计时脉冲：最后几秒心搏式放大/回缩。开着时循环，关掉必须 kill，
## 否则隐藏后的 label 上还挂着一个永不停歇的循环 tween。
func _set_countdown_pulse(active: bool) -> void:
	if _countdown_pulse != null and _countdown_pulse.is_valid():
		_countdown_pulse.kill()
	_countdown_pulse = null
	if _countdown_label == null:
		return
	if not active:
		_countdown_label.scale = Vector2.ONE
		return
	_countdown_label.pivot_offset = _countdown_label.size / 2.0
	var t := _countdown_label.create_tween()
	t.set_loops()
	t.tween_property(_countdown_label, "scale", Vector2(1.12, 1.12), 0.28).set_trans(Tween.TRANS_SINE)
	t.tween_property(_countdown_label, "scale", Vector2.ONE, 0.28).set_trans(Tween.TRANS_SINE)
	_countdown_pulse = t


func _on_countdown(remaining: float) -> void:
	if _intro_active:
		return                    # 转场期间让位给引子；转场一结束下一帧自会补上
	if remaining <= 0.0:
		_countdown_label.visible = false
		_set_countdown_pulse(false)
		return
	_countdown_label.text = "记忆浮现中 %d …" % int(ceil(remaining))
	# 最后 3 秒：转警示色 + 脉冲。紧迫感要提前给到，不能等真的没了才反应。
	var urgent_below: float = float(_params.get("anim", {}).get("countdown_urgent_secs", 3.0))
	var urgent := remaining <= urgent_below
	if urgent != _countdown_urgent:
		_countdown_urgent = urgent
		_countdown_label.add_theme_color_override("font_color",
			C_BAR_DANGER if urgent else C_TRUTH_HINT)
		_set_countdown_pulse(urgent)


func _on_choices_enabled() -> void:
	_end_intro()                 # 玩家可作答即立刻收引子，别让转场吃掉行动窗口
	_countdown_label.visible = false
	var secs := 6.0
	match _mode:
		1:
			secs = float(_params.get("mode1_card", {}).get("window_secs", 8.0))
		2:
			secs = float(_params.get("mode2_drag", {}).get("window_secs", 5.0))
		3:
			secs = float(_params.get("mode3_qte", {}).get("window_secs", 4.0))
	# 档位难度（策划稿 §4.3）：窗口按信任档位伸缩
	_tier = _tier_mod()
	secs *= float(_tier["window_scale"])
	_hint_label.text = ("选择你认为没有被改写的那一段"
		if _mode == 1 else
		("把真正的碎片拖进光门" if _mode == 2 else "A / B 二选一 —— 相信你的记忆"))
	var tag: String = _tier["label"]
	if not tag.is_empty():
		_hint_label.text += "　·　%s" % tag
	_hint_label.add_theme_color_override("font_color", C_TRUTH_HINT)
	_start_action_window(secs)


func _on_choice_recorded(_variant_id: String, success: bool, _shard: String) -> void:
	_choice_made = true
	_action_total = 0.0
	_bar.visible = false
	_show_result(success)


func _on_archaeology_ended(_success: bool, _shard: String) -> void:
	if not _choice_made:
		# abort/超时结束：补一次强闪后按失败收起（超时另有文案）
		_play_flash(2)
		_show_result(false, _timed_out)


# ── 引擎回调 / 入口（置于文件尾，所有被调用函数均已定义）──

func _process(_delta: float) -> void:
	if not _root.visible:
		return
	_update_drag()
	_tick_action_window(_delta)


func _build_ui() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)

	var shade := ColorRect.new()
	shade.color = C_BG_SHADE
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(shade)

	# 判定瞬间全屏白闪
	_flash_rect = ColorRect.new()
	_flash_rect.color = Color.WHITE
	_flash_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flash_rect.visible = false
	_root.add_child(_flash_rect)

	# 中央面板（承载文字区；内容区供模式布局）
	var panel := Control.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	_root.add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	vbox.offset_left = 80
	vbox.offset_right = -80
	vbox.offset_top = 70
	vbox.offset_bottom = -70
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)

	_title_label = Label.new()
	_title_label.add_theme_font_size_override("font_size", 30)
	_title_label.add_theme_color_override("font_color", C_TITLE)
	_title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(_title_label)

	# 转场引子：屏幕渐暗后浮出的主人公独白（§4.2②）
	_intro_label = Label.new()
	_intro_label.add_theme_font_size_override("font_size", 24)
	_intro_label.add_theme_color_override("font_color", C_TRUTH_HINT)
	_intro_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_intro_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_intro_label.visible = false
	vbox.add_child(_intro_label)

	_countdown_label = Label.new()
	_countdown_label.add_theme_font_size_override("font_size", 22)
	_countdown_label.add_theme_color_override("font_color", C_TRUTH_HINT)
	_countdown_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_countdown_label.visible = false
	vbox.add_child(_countdown_label)

	_hint_label = Label.new()
	_hint_label.add_theme_font_size_override("font_size", 17)
	_hint_label.add_theme_color_override("font_color", C_HINT)
	_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(_hint_label)

	# 行动窗口条外框（条在其中从左生长；抖动动条不动框）
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
	_bar.color = C_BAR_OK
	_bar.size = Vector2(_bar_frame.size.x, 12)
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar.visible = false
	_bar_frame.add_child(_bar)

	# 中部可变内容区
	_content = Control.new()
	_content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(_content)

	# 出口光门（mode2 用，层叠在内容之上；默认隐藏）
	_exit_zone = Panel.new()
	var esb := StyleBoxFlat.new()
	esb.bg_color = C_EXIT_ZONE
	esb.border_color = Color(0.55, 0.9, 0.8, 0.6)
	esb.set_border_width_all(2)
	esb.set_corner_radius_all(14)
	_exit_zone.add_theme_stylebox_override("panel", esb)
	_exit_zone.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_exit_zone.visible = false
	var exit_label := Label.new()
	exit_label.text = "光门（出口）"
	exit_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	exit_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	exit_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	exit_label.add_theme_color_override("font_color", Color(0.8, 1.0, 0.95, 0.7))
	_exit_zone.add_child(exit_label)
	_root.add_child(_exit_zone)

	_root.visible = false


func _load_params() -> void:
	var f := FileAccess.open(QTE_PARAMS_PATH, FileAccess.READ)
	if f == null:
		push_warning("[ArchaeologyUI] %s 未找到，使用内置默认" % QTE_PARAMS_PATH)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) == TYPE_DICTIONARY:
		_params = parsed


func _ready() -> void:
	layer = LAYER
	_load_params()
	_build_ui()
	MemoryArchaeology.level_started.connect(_on_level_started)
	MemoryArchaeology.variants_shown.connect(_on_variants_shown)
	MemoryArchaeology.countdown_updated.connect(_on_countdown)
	MemoryArchaeology.choices_enabled.connect(_on_choices_enabled)
	MemoryArchaeology.choice_recorded.connect(_on_choice_recorded)
	MemoryArchaeology.flash_triggered.connect(_play_flash)
	MemoryArchaeology.archaeology_ended.connect(_on_archaeology_ended)
	print("[ArchaeologyUI] 启动：已订阅记忆考古信号，layer=%d" % layer)
