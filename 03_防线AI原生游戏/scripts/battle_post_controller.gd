# battle_post_controller.gd —— 战斗后处理控制器（W4.4 · 成员 A）
# 驱动 assets/shaders/battle_post.gdshader（单 pass 合并版）：按 90s 时间轴 +
# 30s 后摇推进全部 uniform；数据源 W3\battle\pressure_params.json v1
# （res://config/pressure_params.json 存在时优先读该文件；否则用内置同值表）。
#
# 公共 API：
#   start_battle()                 重置时间轴并启动（phase1）
#   stop_battle(fade_reset=true)   终止并复位 uniform（回日常色）
#   set_shake(amount)              事件驱动抖动（峰值 0.03；帧间 lerp 0.2 衰减）
#   resolve_battle(erosion_hold)   进入后摇：erosion_hold=true（玩家选 A,只信 AI）
#                                  → 蚀蒙从 1.0 起退散；false（选 B,记起旧友的话）
#                                  → 从当前 0.9 立即退散（W3.3 phase3.resolve）
#   get_uniforms() -> Dictionary   当前 uniform 快照（调试/HUD/录音对照用）
#   set_battle_time(secs)          测试/回放用：直接跳到某个时间点
#   flash_warm_mask(center_uv)     B5：局部暖色 mask 闪现（最近 3 次交互锚点；3 槽 FIFO）
#   flash_warm_mask_from_screen_pos(screen_pos)  便捷：屏幕坐标→UV 后触发（锚点系统用）
#   clear_warm_mask()              清除全部暖色 mask
#   signal phase_changed(phase)    "phase1"/"phase2"/"phase3"/"aftermath"
#   signal battle_finished(hold)   120s 流程结束
#
# 绑定材质（三选一，按序尝试）：
#   1) bind_shader_material(mat) 显式绑定
#   2) target_path 属性指向挂 ColorRect 的节点（取其 material）
#   3) 节点组 "battle_post"（C 把 ColorRect 加入同组即可自动吸附）
# 若 /root/battle_audio（W4.3 autoload）存在，phase_changed 时自动联调其 set_phase。

class_name BattlePostController
extends Node

signal phase_changed(phase: String)
signal battle_finished(erosion_hold: bool)

const PARAMS_FILE := "res://config/pressure_params.json"
const GROUP_NAME := "battle_post"
const TOTAL_SECS := 120.0            # 90s 战斗 + 30s 后摇
const AFTERMATH_DURATION := 20.0     # 后摇视觉退散时长（W3.3 aftermath）
const SHAKE_DECAY_LERP := 0.2        # 帧间衰减系数（pressure_params curves.shake_amount.decay_lerp）
const SHAKE_PEAK := 0.03

# ── 局部暖色 mask（B5：刺痛型暖色，最近 3 次交互锚点，≈15% 画面；数据见 pressure_params.warm_mask）──
const WARM_MASK_SLOTS := 3           # 槽位数 = 「最近 3 次交互过的锚点」
const WARM_MASK_PEAK := 0.85         # 置峰强度（warm_mask.peak_strength）
const WARM_MASK_RADIUS := 0.22       # UV 半径 ≈ 15% 画面面积（πr²≈0.152，warm_mask.radius_uv）
const WARM_MASK_DECAY_SECS := 1.0    # 峰值线性衰减至 0 的时长（warm_mask.decay_secs；0.5-1s 后被 AI 文字框遮盖）

# W3\battle\pressure_params.json 内置同值表（curves 节逐 5 秒点；若 JSON 存在则以 JSON 为准）
const DEFAULT_TABLES := {
	"erosion_progress": [
		[0, 0.000], [5, 0.067], [10, 0.133], [15, 0.200], [20, 0.267], [25, 0.333],
		[30, 0.400], [35, 0.500], [40, 0.600], [45, 0.700], [50, 0.800], [55, 0.900],
		[60, 0.900], [65, 0.900], [70, 0.900], [75, 0.900], [80, 0.900], [85, 0.900], [90, 0.900]
	],
	"tunnel_radius": [[30, 0.200], [35, 0.175], [40, 0.150], [45, 0.125], [50, 0.100], [55, 0.075], [60, 0.050], [90, 0.050]],
	"red_retain": [[0, 1.00], [5, 0.75], [10, 0.50], [15, 0.25], [20, 0.00], [90, 0.00]],
	"green_retain": [[0, 1.00], [20, 1.00], [25, 0.75], [30, 0.50], [35, 0.25], [40, 0.00], [90, 0.00]],
	"blue_retain": [
		[0, 1.00], [10, 1.00], [15, 0.95], [20, 0.95], [25, 0.90], [30, 0.90], [35, 0.90],
		[40, 0.85], [45, 0.85], [50, 0.80], [60, 0.90], [90, 0.90]
	],
	"posterize_amount": [
		[0, 0.00], [15, 0.00], [20, 0.10], [25, 0.10], [30, 0.20], [35, 0.25], [40, 0.30],
		[45, 0.35], [50, 0.40], [55, 0.45], [60, 0.50], [90, 0.50]
	],
	"posterize_levels": 16.0,
}

# 后摇复位目标（W3.3 aftermath 节 + curves 备注）
const DEFAULT_AFTERMATH := {
	"erosion_from_hold": 1.0,   # erosion_hold=true 时后摇起点
	"erosion_from_break": 0.9,  # erosion_hold=false 时后摇起点（当前战斗末峰值）
	"erosion_to": 0.0,
	"tunnel_to": 0.30,
	"posterize_to": 0.00,
	"retain_to": 1.00,
}

# 阶段边界（秒 → phase id；与 W3.3 phase1/2/3、aftermath 一致）
const PHASE_BOUNDS: Array = [
	[0.0, "phase1"], [30.0, "phase2"], [60.0, "phase3"], [90.0, "aftermath"],
]

var _mat: ShaderMaterial = null
var target_path := NodePath("")
var _running := false
var _t := 0.0
var _phase := "idle"
var _shake := 0.0
var _shake_seed := 0.0
var _erosion_hold := true
var _tables: Dictionary = {}
var _aftermath: Dictionary = {}
var _audio: Node = null

# 暖色 mask 3 槽状态（FIFO：最新交互推入，最旧挤出）
var _warm_centers: Array = [Vector2(0.5, 0.5), Vector2(0.5, 0.5), Vector2(0.5, 0.5)]
var _warm_radii: Array = [0.0, 0.0, 0.0]
var _warm_strengths: Array = [0.0, 0.0, 0.0]


# ── 绑定 ──

## 显式绑定 ShaderMaterial（推荐；也可只设 target_path 或加组 "battle_post"）。
func bind_shader_material(mat: ShaderMaterial) -> void:
	_mat = mat


func _auto_bind_material() -> void:
	if _mat != null:
		return
	var node: Node = null
	if not target_path.is_empty():
		node = get_node_or_null(target_path)
	else:
		node = get_tree().get_first_node_in_group(GROUP_NAME)
	if node is CanvasItem and (node.material as ShaderMaterial) is ShaderMaterial:
		_mat = node.material
		print("[BattlePost] 绑定材质：%s" % node.name)
	elif node == null:
		push_warning("[BattlePost] 未找到 battle_post 节点（target_path/组 %s）——get_uniforms 仍可用，但无画面输出" % GROUP_NAME)


# ── 公共 API ──

func start_battle() -> void:
	_t = 0.0
	_shake = 0.0
	_shake_seed = randf_range(0.0, 100.0)
	_erosion_hold = true
	_running = true
	_auto_bind_material()
	# 待命：复位为「日常」（防止上一场残留）
	_set_phase("phase1")

func stop_battle(reset_uniforms: bool = true) -> void:
	_running = false
	_phase = "idle"
	if reset_uniforms:
		_apply_reset_uniforms()
	print("[BattlePost] 停止（复位=%s）" % reset_uniforms)


## 事件驱动抖动（pressure_params curves.shake_amount：置峰后帧间衰减）。
func set_shake(amount: float) -> void:
	_shake = maxf(_shake, clampf(amount, 0.0, SHAKE_PEAK))
	if _mat != null:
		_mat.set_shader_parameter("shake_amount", _shake)
		_mat.set_shader_parameter("shake_seed", _shake_seed)


## 最终抉择后进入后摇（5.5）。erosion_hold=true → 玩家选了「只相信你」；
## false → 玩家记起旧友的话（W3.3 phase3.resolve：choice_a 蚀蒙 1.0 / choice_b 立即退散）。
func resolve_battle(erosion_hold: bool = true) -> void:
	_erosion_hold = erosion_hold
	_set_phase("aftermath")


## 测试/回放：直接跳到任意时间点（下一帧自动应用 uniform）。
func set_battle_time(secs: float) -> void:
	_t = clampf(secs, 0.0, TOTAL_SECS)
	_running = true
	_phase = "idle"          # 强制重新判定阶段
	_evaluate_phase()


# ── 局部暖色 mask（B5：刺痛型暖色，仅最近 3 次交互锚点位置）──

## 在指定屏幕 UV 处闪现局部暖色 mask（FIFO 3 槽）。
## 调用方：锚点交互系统／考古 UI（玩家与记忆锚点交互时）。
func flash_warm_mask(center_uv: Vector2, radius: float = WARM_MASK_RADIUS) -> void:
	_warm_centers = [_warm_centers[1], _warm_centers[2], center_uv]
	_warm_radii = [_warm_radii[1], _warm_radii[2], radius]
	_warm_strengths = [_warm_strengths[1], _warm_strengths[2], WARM_MASK_PEAK]
	_push_warm_mask_uniforms()


## 便捷：由屏幕坐标（如锚点节点的 global_position）换算 UV 后触发（锚点坐标映射）。
func flash_warm_mask_from_screen_pos(screen_pos: Vector2) -> void:
	var vp := get_viewport()
	var size := Vector2(1920.0, 1080.0)
	if vp != null:
		size = vp.get_visible_rect().size
	if size.x > 0.0 and size.y > 0.0:
		flash_warm_mask(screen_pos / size)


## 清除全部暖色 mask（战斗复位/回放用）。
func clear_warm_mask() -> void:
	for i in WARM_MASK_SLOTS:
		_warm_strengths[i] = 0.0
	_push_warm_mask_uniforms()


func _push_warm_mask_uniforms() -> void:
	if _mat == null:
		return
	for i in WARM_MASK_SLOTS:
		_mat.set_shader_parameter("warm_mask_center_%d" % i, _warm_centers[i])
		_mat.set_shader_parameter("warm_mask_radius_%d" % i, _warm_radii[i])
		_mat.set_shader_parameter("warm_mask_strength_%d" % i, _warm_strengths[i])


## 当前 uniform 快照（供调试面板/HUD/录音对照；键名与 shader uniform 一致）。
func get_uniforms() -> Dictionary:
	var vals := {
		"battle_time": _t,
		"phase": _phase,
		"erosion_progress": _curve_at(_curve_table("erosion_progress"), _t),
		"tunnel_radius": _curve_at(_curve_table("tunnel_radius"), _t),
		"red_retain": _curve_at(_curve_table("red_retain"), _t),
		"green_retain": _curve_at(_curve_table("green_retain"), _t),
		"blue_retain": _curve_at(_curve_table("blue_retain"), _t),
		"posterize_amount": _curve_at(_curve_table("posterize_amount"), _t),
		"posterize_levels": float(_tables.get("posterize_levels", DEFAULT_TABLES["posterize_levels"])),
		"shake_amount": _shake,
		"shake_seed": _shake_seed,
	}
	if _phase == "aftermath":
		var pct := clampf((_t - 90.0) / AFTERMATH_DURATION, 0.0, 1.0)
		vals["erosion_progress"] = lerpf(_erosion_hold_from(), 0.0, pct)
		vals["tunnel_radius"] = lerpf(0.05, _aftermath["tunnel_to"], pct)
		vals["red_retain"] = lerpf(vals["red_retain"], _aftermath["retain_to"], pct)
		vals["green_retain"] = lerpf(vals["green_retain"], _aftermath["retain_to"], pct)
		vals["blue_retain"] = lerpf(vals["blue_retain"], _aftermath["retain_to"], pct)
		vals["posterize_amount"] = lerpf(vals["posterize_amount"], _aftermath["posterize_to"], pct)
	return vals


# ── 阶段推进 ──

func _evaluate_phase() -> void:
	var new_phase := ""
	for row in PHASE_BOUNDS:
		if _t >= float(row[0]):
			new_phase = String(row[1])
	if new_phase != _phase:
		_set_phase(new_phase)


func _set_phase(phase: String) -> void:
	_phase = phase
	phase_changed.emit(phase)
	if _audio != null:
		_audio.set_phase(phase)
	print("[BattlePost] phase → %s（t=%.1fs）" % [phase, _t])


func _erosion_hold_from() -> float:
	return float(_aftermath["erosion_from_hold"] if _erosion_hold else _aftermath["erosion_from_break"])


# ── 每帧驱动 ──

func _process(delta: float) -> void:
	if not _running:
		return
	if _mat == null:
		_auto_bind_material()
	_t += delta
	_evaluate_phase()

	# 应用 uniform
	if _mat != null:
		var u := get_uniforms()
		for key in ["erosion_progress", "tunnel_radius", "red_retain", "green_retain",
				"blue_retain", "posterize_amount", "posterize_levels", "shake_amount", "shake_seed"]:
			_mat.set_shader_parameter(key, u[key])

	# 抖动帧间衰减（lerp 向 0）
	_shake = lerpf(_shake, 0.0, SHAKE_DECAY_LERP)
	if _shake < 0.0001:
		_shake = 0.0
	if _mat != null:
		_mat.set_shader_parameter("shake_amount", _shake)

	# 暖色 mask 衰减（B5：0.5-1s 后被 AI 文字框遮盖 → 线性衰减至 0）
	var warm_alive := false
	for i in WARM_MASK_SLOTS:
		if _warm_strengths[i] > 0.0:
			_warm_strengths[i] = maxf(_warm_strengths[i] - WARM_MASK_PEAK * delta / WARM_MASK_DECAY_SECS, 0.0)
			warm_alive = true
	if warm_alive:
		_push_warm_mask_uniforms()

	# 后摇结束（t=120s）
	if _phase == "aftermath" and _t >= TOTAL_SECS:
		_running = false
		_apply_reset_uniforms()
		battle_finished.emit(_erosion_hold)
		print("[BattlePost] 战斗流程结束（hold=%s）" % _erosion_hold)


# ── uniform 复位（日常画面）──

func _apply_reset_uniforms() -> void:
	if _mat == null:
		return
	_mat.set_shader_parameter("erosion_progress", 0.0)
	_mat.set_shader_parameter("tunnel_radius", 0.05)
	_mat.set_shader_parameter("red_retain", 1.0)
	_mat.set_shader_parameter("green_retain", 1.0)
	_mat.set_shader_parameter("blue_retain", 1.0)
	_mat.set_shader_parameter("posterize_amount", 0.0)
	_mat.set_shader_parameter("shake_amount", 0.0)
	clear_warm_mask()


# ── 曲线工具 ──

func _curve_table(name: String) -> Array:
	return _tables.get(name, DEFAULT_TABLES[name])


## 逐点查找（表短，线性扫即够；t 超出表尾=取末值）。
func _curve_at(table: Array, t: float) -> float:
	if table.is_empty():
		return 0.0
	var last: Array = table[table.size() - 1]
	if t >= float(last[0]):
		return float(last[1])
	for i in range(1, table.size()):
		var row: Array = table[i]
		if t < float(row[0]):
			var prev: Array = table[i - 1]
			var span := float(row[0]) - float(prev[0])
			var frac := 0.0 if span <= 0.0 else (t - float(prev[0])) / span
			return lerpf(float(prev[1]), float(row[1]), frac)
	return float(table[0][1])


# ── 数据加载（res://config/pressure_params.json 优先，缺失→内置表）──

func _load_params() -> void:
	_tables = {}
	_aftermath = DEFAULT_AFTERMATH.duplicate(true)
	if ResourceLoader.exists(PARAMS_FILE):
		var f := FileAccess.open(PARAMS_FILE, FileAccess.READ)
		if f != null:
			var parsed = JSON.parse_string(f.get_as_text())
			f.close()
			if typeof(parsed) == TYPE_DICTIONARY and parsed.has("curves"):
				for key in parsed["curves"]:
					if key == "_meta":
						continue
					var val = parsed["curves"][key]
					if typeof(val) == TYPE_DICTIONARY and val.has("curve") and typeof(val["curve"]) == TYPE_ARRAY:
						_tables[key] = val["curve"]
				print("[BattlePost] 压力参数表已从 %s 加载：" % PARAMS_FILE, _tables.keys())
				return
	push_warning("[BattlePost] %s 未找到或不完整 → 使用内置同值表（W3\\battle\\pressure_params.json v1）" % PARAMS_FILE)
	_tables = DEFAULT_TABLES.duplicate(true)


# ── 入口 ──

func _ready() -> void:
	_load_params()
	_audio = get_node_or_null("/root/battle_audio")
	if _audio != null:
		print("[BattlePost] 已关联 battle_audio（phase 联动 set_phase）")
	_apply_reset_uniforms()
	print("[BattlePost] 就绪：调用 start_battle() 启动 90s+30s 流程")
