# ambient_director.gd —— 氛围事件调度器 + 占位效果层（Autoload 常驻）
# W4 交付物之一（拆分自 B 的 trigger_interface）：监听场景 → 按 config/ambient_events.json
# 判定触发 → 广播 EventBus.ambient_triggered → 播放占位视觉。
#
# 架构（解耦占位，等 A 真实 Shader/音频就绪后替换）：
#   1. 调度层（本文件前 2/3）：纯逻辑，不碰 A 资产。
#      · 进入场景后周期评估该场景适用事件（场景事件 + 跨场景 ALL 事件）。
#      · 三类触发沿用 B 骨架语义：
#          random          → 每 tick 概率 roll，每进一次场景至多触发一次
#          trust_based     → TrustDrift 当前 tier >= 事件要求 tier（整个会话只触发一次）
#          progress_based  → 全局锚点交互总数 >= interaction_count（整个会话只触发一次）
#      · 触发时只发信号 + 记录 fired_log，不直接改场景。
#   2. 效果占位（本文件后 1/3）：effect_type → 简单视觉 toast / 全屏闪色，
#      仅供联调识别事件与验证流程；A 到位后监听 EventBus.ambient_triggered 覆盖真实表现。
#
# 关键：json 顶层键即事件 id（如 CF_001）；scene 为中文场景名；ALL=跨场景常驻。
# 场景映射与 interactable.gd 的 SCENE_NAMES 保持一致。
#
# 注意：函数按"先定义后调用"排列（GDScript 下划线私有函数引用顺序限制），_ready 在末尾。

extends Node

const EVENTS_FILE := "res://config/ambient_events.json"

const TICK_SECONDS := 0.5         # 评估周期
const ENTER_HOLD_MS := 1200       # 进场(黑幕/偶遇/玩家先观感)后再开始评估
const MIN_GAP_MS := 4000          # 相邻氛围事件最小间隔，避免连发淹没

# 节奏参数（可被 ambient_events.json 的 _meta.pacing 覆写，改数值不用改代码）
const DEFAULT_MAX_PER_VISIT := 2        # 每次进场景至多触发几个氛围事件
const DEFAULT_RANDOM_MIN_DELAY_MS := 6000   # 进场后 random 事件的最早触发时间（留出"先看一圈"的空档）

## 场景路径 → 中文名（决定加载哪些事件；与 SceneManager/interactable 一致）
const SCENE_NAMES := {
	"res://scenes/coffee_shop.tscn": "咖啡店",
	"res://scenes/classroom.tscn": "教室",
	"res://scenes/dormitory.tscn": "宿舍",
	"res://scenes/street.tscn": "街道",
	"res://scenes/apartment.tscn": "公寓",
}

const TIER_RANK := {
	"LOW_TRUST": 0,
	"MEDIUM_TRUST": 1,
	"HIGH_TRUST": 2,
}

var _events: Dictionary = {}        # event_id -> 完整事件数据
var _scene_ids: Dictionary = {}     # 中文场景名 -> [event_id,...]
var _global_ids: Array[String] = [] # ALL 事件 id 列表

var _current_scene: String = ""     # 当前场景中文名（"" = 无该场景事件）
var _session_fired := {}            # trust/progress 事件：整个会话只触发一次
var _visit_fired := {}              # random 事件：本场景本次访问只触发一次
var _fired_log: Array[Dictionary] = []   # 已触发记录（供测试/可视化/调试）
var _pending_scene_sync: bool = true     # 启动后待取当前主场景

# 节奏状态（每次进场景重置）
var _visit_rolled := {}             # random 事件本次访问的掷骰结果：每进一次场景只掷一次
var _visit_fire_count: int = 0      # 本次访问已触发的氛围事件数
var _max_per_visit: int = DEFAULT_MAX_PER_VISIT
var _random_min_delay_ms: int = DEFAULT_RANDOM_MIN_DELAY_MS

var _enter_ts_ms := 0
var _last_fire_ms := 0
var _accum := 0.0

# 占位效果层
var _overlay: CanvasLayer
var _flash: ColorRect
var _toast_label: Label
var _flash_tween: Tween
var _toast_tween: Tween


# ── 查询 / 调试接口（供测试与外部可视化）──

func get_fired_log() -> Array:
	return _fired_log.duplicate(true)


func is_fired(event_id: String) -> bool:
	return _session_fired.has(event_id) or _visit_fired.has(event_id)


func has_event(event_id: String) -> bool:
	return _events.has(event_id)


## 调试用：无条件触发一个事件（绕过概率/阈值/间隔），并标记已触发防止重复。
func debug_trigger(event_id: String) -> bool:
	if not _events.has(event_id):
		push_warning("[AmbientDirector] debug_trigger: 无此事件 %s" % event_id)
		return false
	_mark_fired(event_id)
	_fire(event_id)
	return true


## 调试用：立即评估一轮（忽略进场保护与最小间隔，供无头测试）。
func debug_evaluate_immediately() -> void:
	# 时间戳置为极远过去，使 now-ts 必然越过 ENTER_HOLD/MIN_GAP（0 不行：开机早期 ticks 仍很小）
	_enter_ts_ms = -1000000000
	_last_fire_ms = -1000000000
	_visit_fire_count = 0        # 配额也一并绕过，测试可连续驱动多个事件
	_evaluate()


# ── 数据加载 ──

## 校验：事件表里出现的场景名，是否都有真实场景文件兜底。
## 现状：json 指向"公寓"的 3 条事件(AP_001~003)没有对应 scenes/apartment.tscn，
## 它们永远不会触发，也不会报错——静默死数据。这里在启动时把它喊出来。
func _validate_scene_coverage() -> void:
	var name_to_path := {}
	for p in SCENE_NAMES:
		name_to_path[SCENE_NAMES[p]] = p
	var dead := {}
	for event_id in _events:
		var scene: String = _events[event_id].get("scene", "")
		if scene == "ALL" or scene.is_empty():
			continue
		var path: String = name_to_path.get(scene, "")
		if path.is_empty() or not ResourceLoader.exists(path):
			if not dead.has(scene):
				dead[scene] = []
			dead[scene].append(event_id)
	for scene in dead:
		push_warning("[AmbientDirector] 场景「%s」没有可用场景文件，其 %d 条氛围事件永远不会触发：%s" % [
			scene, dead[scene].size(), ", ".join(PackedStringArray(dead[scene]))
		])


func _load_events() -> void:
	var f := FileAccess.open(EVENTS_FILE, FileAccess.READ)
	if f == null:
		push_error("[AmbientDirector] 无法打开 %s" % EVENTS_FILE)
		return
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("[AmbientDirector] JSON 格式错误：%s" % EVENTS_FILE)
		return
	# 节奏参数：_meta.pacing 存在则以它为准（B 调频率只改 json）
	var meta = parsed.get("_meta", {})
	if typeof(meta) == TYPE_DICTIONARY:
		var pacing = meta.get("pacing", {})
		if typeof(pacing) == TYPE_DICTIONARY:
			_max_per_visit = int(pacing.get("max_per_visit", DEFAULT_MAX_PER_VISIT))
			_random_min_delay_ms = int(pacing.get("random_min_delay_ms", DEFAULT_RANDOM_MIN_DELAY_MS))

	for key in parsed:
		if key == "_meta":
			continue
		var ev: Dictionary = parsed[key]
		_events[key] = ev
		var scene: String = ev.get("scene", "")
		if scene == "ALL":
			_global_ids.append(key)
		else:
			if not _scene_ids.has(scene):
				_scene_ids[scene] = []
			_scene_ids[scene].append(key)

	_validate_scene_coverage()


func _scene_name_for_path(path: String) -> String:
	return SCENE_NAMES.get(path, "")


func _tier_rank(tier: String) -> int:
	return int(TIER_RANK.get(tier, 0))


# ── 触发判定 ──

## trust/progress 事件属于"剧情推进型"，整会话一次；random 属于"氛围型"，每进场景一次。
func _is_session_once(event_id: String) -> bool:
	var typ: String = _events[event_id].get("trigger_type", "")
	return typ == "trust_based" or typ == "progress_based"


func _mark_fired(event_id: String) -> void:
	if _is_session_once(event_id):
		_session_fired[event_id] = true
	else:
		_visit_fired[event_id] = true


## random 事件的掷骰：每进一次场景只掷一次，结果缓存到本次访问结束。
## 原实现是每 tick（0.5s）都掷一次 —— 0.25 的"低概率"事件进场后每半秒掷一次，
## 两秒内累计命中率约 1-0.75^4 ≈ 68%，几乎每进一次必炸，"低概率"名存实亡。
## 改成每次访问掷一次，json 里的 probability 才是它字面上的意思。
func _random_roll_passed(event_id: String) -> bool:
	if not _visit_rolled.has(event_id):
		var prob := float(_events[event_id].get("trigger_param", {}).get("probability", 0.0))
		_visit_rolled[event_id] = randf() < prob
	return bool(_visit_rolled[event_id])


func _should_fire(event_id: String) -> bool:
	var ev: Dictionary = _events[event_id]
	var typ: String = ev.get("trigger_type", "")
	var param: Dictionary = ev.get("trigger_param", {})
	if typ == "random":
		# 进场后先留一段"看一圈"的空档，之后才可能冒出随机异常
		if Time.get_ticks_msec() - _enter_ts_ms < _random_min_delay_ms:
			return false
		return _random_roll_passed(event_id)
	elif typ == "trust_based":
		var need_tier: String = param.get("tier", "LOW_TRUST")
		return _tier_rank(TrustDrift.get_trust_tier()) >= _tier_rank(need_tier)
	elif typ == "progress_based":
		var need_count := int(param.get("interaction_count", 0))
		return TrustDrift.get_total_anchor_count() >= need_count
	return false


func _candidate_ids() -> Array:
	var out: Array = []
	for event_id in _global_ids:
		if not is_fired(event_id):
			out.append(event_id)
	var scene_list: Array = _scene_ids.get(_current_scene, [])
	for event_id in scene_list:
		if not is_fired(event_id):
			out.append(event_id)
	return out


## 一轮评估：至多触发一个候选事件。
func _evaluate() -> void:
	if _events.is_empty():
		return
	if _pending_scene_sync:
		return   # 尚未拿到主场景，等 _process 同步后再评估
	var now_ms := Time.get_ticks_msec()
	if now_ms - _enter_ts_ms < ENTER_HOLD_MS:
		return
	if now_ms - _last_fire_ms < MIN_GAP_MS:
		return
	if _visit_fire_count >= _max_per_visit:
		return   # 本次访问配额已满，剩下的留给下次进来
	for event_id in _candidate_ids():
		if _should_fire(event_id):
			_mark_fired(event_id)
			_last_fire_ms = now_ms
			_visit_fire_count += 1     # 计入本次访问配额（_visit_fire_count 与 _mark_fired 必须同步）
			_fire(event_id)
			return


# ── 触发 / 广播 ──

func _fire(event_id: String) -> void:
	var ev: Dictionary = _events[event_id]
	_fired_log.append({
		"id": event_id,
		"name": ev.get("name", event_id),
		"effect_type": ev.get("effect_type", ""),
		"scene": ev.get("scene", ""),
		"time": Time.get_ticks_msec(),
	})
	# 广播给 A(真实 Shader/音频) / B(日志) / 其它订阅方
	EventBus.ambient_triggered.emit(event_id, ev.get("effect_type", ""), ev.duplicate())
	print("[AmbientDirector] 触发 %s「%s」 effect=%s" % [
		event_id, ev.get("name", ""), ev.get("effect_type", "")
	])
	_run_effect(ev.get("effect_type", ""), ev.get("name", ""))


# ── 占位效果层：effect_type → 视觉占位 ──

func _run_effect(effect_type: String, event_name: String) -> void:
	# 每类占位表现力求可区分；真实实现由 A 订阅 ambient_triggered 后覆盖。
	match effect_type:
		"light_anomaly":
			_toast("[占位·灯光] " + event_name, Color(1.0, 0.9, 0.6))
			_play_flash(Color(1.0, 0.85, 0.55), 0.16, 2, 0.10)
		"photo_glitch":
			_toast("[占位·照片畸变] " + event_name, Color(0.85, 0.9, 1.0))
			_play_flash(Color(0.85, 0.9, 1.0), 0.20, 3, 0.06)
		"subtitle_stutter":
			_toast("[占位·字幕抖动] " + event_name, Color(0.95, 0.95, 0.95))
		"bgm_shift":
			_toast("[占位·BGM 变调(待 A)] " + event_name, Color(0.75, 0.6, 0.95))
		"item_displace":
			_toast("[占位·物品位移] " + event_name, Color(1.0, 0.7, 0.7))
		"ambient_sound":
			_toast("[占位·环境音(待 A)] " + event_name, Color(0.5, 0.95, 0.9))
		_:
			_toast("[占位·氛围] " + event_name, Color.WHITE)
	if effect_type in ["light_anomaly", "photo_glitch", "bgm_shift", "ambient_sound"]:
		push_warning("[AmbientDirector] %s 为占位实现，等待 A 以真实 Shader/音频替换" % effect_type)


func _play_flash(col: Color, peak: float, cycles: int, half_sec: float) -> void:
	if _flash_tween != null and _flash_tween.is_valid():
		_flash_tween.kill()
	_flash.color = Color(col.r, col.g, col.b, 0.0)
	var tween := create_tween()
	_flash_tween = tween
	for i in range(cycles):
		tween.tween_property(_flash, "color:a", peak, half_sec)
		tween.tween_property(_flash, "color:a", 0.0, half_sec * 1.8)


func _toast(text: String, col: Color) -> void:
	if _toast_tween != null and _toast_tween.is_valid():
		_toast_tween.kill()
	_toast_label.text = text
	_toast_label.add_theme_color_override("font_color", col)
	_toast_label.visible = true
	_toast_label.modulate.a = 0.0
	var tween := create_tween()
	_toast_tween = tween
	tween.tween_property(_toast_label, "modulate:a", 1.0, 0.12)
	tween.tween_interval(2.0)
	tween.tween_property(_toast_label, "modulate:a", 0.0, 0.5)
	tween.tween_callback(func() -> void: _toast_label.visible = false)


# ── 效果层构建（_ready 直接调用，置于其前）──

func _build_overlay() -> void:
	_overlay = CanvasLayer.new()
	_overlay.layer = 8   # 高于对话 UI(layer 1~)，低于 DialogueHistory(12)/记忆锚点(20)/黑幕(100)
	add_child(_overlay)

	_flash = ColorRect.new()
	_flash.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash.color = Color(0, 0, 0, 0)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(_flash)

	_toast_label = Label.new()
	_toast_label.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_toast_label.offset_top = 40
	_toast_label.offset_left = 320
	_toast_label.offset_right = -320
	_toast_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast_label.add_theme_font_size_override("font_size", 26)
	_toast_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_toast_label.add_theme_constant_override("outline_size", 8)
	_toast_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast_label.visible = false
	_overlay.add_child(_toast_label)


# ── 场景同步 ──

func _sync_scene_from_tree() -> void:
	var cs := get_tree().current_scene
	if cs == null:
		return
	var path: String = cs.scene_file_path
	if path.is_empty():
		return
	_pending_scene_sync = false
	_on_scene_changed(path)


func _on_scene_changed(target_path: String) -> void:
	_current_scene = _scene_name_for_path(target_path)
	_visit_fired.clear()          # 每进一次场景，random 事件可重新随机
	_visit_rolled.clear()         # 掷骰结果同样按"次"作废，下次进来重掷
	_visit_fire_count = 0         # 触发配额重置
	_enter_ts_ms = Time.get_ticks_msec()
	_last_fire_ms = 0
	print("[AmbientDirector] 进入场景 %s（%s）候选场景事件 %d + 全局 %d" % [
		target_path, _current_scene,
		_scene_ids.get(_current_scene, []).size(), _global_ids.size()
	])


# ── 主循环 / 入口 ──

func _process(delta: float) -> void:
	if _pending_scene_sync:
		_sync_scene_from_tree()
	_accum += delta
	if _accum >= TICK_SECONDS:
		_accum = 0.0
		_evaluate()


func _ready() -> void:
	_load_events()
	_build_overlay()
	EventBus.scene_changed.connect(_on_scene_changed)
	_enter_ts_ms = Time.get_ticks_msec()
	print("[AmbientDirector] 启动：载入事件 %d 个（全局 %d）" % [_events.size(), _global_ids.size()])
