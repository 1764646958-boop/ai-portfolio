# 《防线》战斗测试驱动脚本 · 视野侵蚀 Shader 接入验证
# 引擎：MagicAI（Godot 4.6.2 AI 定制版，GDScript 4 语法）
# 对应 shader：res://assets/shaders/视野侵蚀Shader原型.gdshader
# 对应场景：res://scenes/battle_test.tscn（本脚本挂在场景根节点）
#
# 设计依据：《防线》团队选题报告 §4.4「记忆解体重构」90 秒三阶段战斗
#   - 阶段一·认知入侵(0-30s)：视野侵蚀 0→40%，冷蓝边框向内收缩
#   - 阶段二·记忆崩塌(30-60s)：侵蚀推到 0.9（隧道视觉占位，W3 接隧道 shader）
#   - 阶段三·最终抉择(60-90s)：保持高压；接口留给 LLM 战斗对话（W3）
#   - 后摇(90-100s)：演示用缓缓退散
#
# 铁律：Shader 只吃 uniform 数字，本脚本每帧不读 LLM/磁盘/网络；
#       LLM 调用必须异步，绝不阻塞 _process 渲染循环。

extends Node2D

@onready var overlay: ColorRect = $Overlay
# 注意：成员不能叫 material —— Node2D 原生就有 material 属性，重名会被 Godot 4 判为
# 「Member "material" redefined (original in native class 'Node2D')」，脚本直接编译不过。
# 故名 overlay_mat；右侧 overlay.material 取的是 ColorRect 自身的材质，保持原样。
@onready var overlay_mat: ShaderMaterial = overlay.material

const PHASE1_END := 30.0
const PHASE2_END := 60.0
const PHASE3_END := 90.0
const AFTER_END := 100.0

# 阶段一视觉预设（与美术方案 12 色色彩卡「冷蓝」#4A6B8A 呼应，可调）
const EROSION_COLOR := Color(0.05, 0.13, 0.30)   # 冷蓝（AI 界面）
const EROSION_OPACITY_MAX := 0.88                 # 最终不透明度

var battle_time := 0.0
var current_phase := 0


func _ready() -> void:
	# 初始状态：无侵蚀，全屏清晰
	overlay_mat.set_shader_parameter("erosion_progress", 0.0)
	overlay_mat.set_shader_parameter("erosion_opacity", 0.0)
	overlay_mat.set_shader_parameter("edge_softness", 0.14)
	overlay_mat.set_shader_parameter("erosion_color", EROSION_COLOR)
	overlay_mat.set_shader_parameter("erosion_center", Vector2(0.5, 0.5))
	print("[BattleTest] 战斗测试场景就绪：阶段一(0-30s) → 阶段二(30-60s) → 阶段三(60-90s)")


func _process(delta: float) -> void:
	battle_time += delta
	var phase := _phase_of(battle_time)
	if phase != current_phase:
		current_phase = phase
		print("[BattleTest] 进入阶段 %d @ %.1fs" % [phase, battle_time])

	match phase:
		1:
			# 阶段一·认知入侵：侵蚀进度 0 → 0.4（30 秒占 40% 屏幕）
			# 平滑版（默认）；如需「每 5 秒收缩一次」的阶梯感，改用：
			#   var p := floor(battle_time / 5.0) / 6.0 * 0.4
			var p := battle_time / PHASE1_END * 0.4
			overlay_mat.set_shader_parameter("erosion_progress", p)
			# 冷蓝遮罩渐显（0 → 0.88）
			overlay_mat.set_shader_parameter(
				"erosion_opacity", EROSION_OPACITY_MAX * battle_time / PHASE1_END)
		2:
			# 阶段二·记忆崩塌：侵蚀 0.4 → 0.9，视野被压缩
			# TODO(W3)：接入「隧道视觉」shader（tunnel_radius 0.2 → 0.05），
			#           与视野侵蚀合并为一次后处理 pass（见 Shader 技术路径研究 §3.0）
			var t := (battle_time - PHASE1_END) / (PHASE2_END - PHASE1_END)
			overlay_mat.set_shader_parameter("erosion_progress", 0.4 + 0.5 * t)
			overlay_mat.set_shader_parameter("erosion_opacity", EROSION_OPACITY_MAX)
		3:
			# 阶段三·最终抉择：保持高压
			# TODO(W3)：接入 LLM 战斗对话引擎后，按玩家选择驱动：
			#   选 A（依赖）→ erosion_progress 继续收敛到 1.0
			#   选 B（输入旧友的话）→ 遮罩裂纹式退散（需新 uniform 或贴图）
			overlay_mat.set_shader_parameter("erosion_progress", 0.9)
			overlay_mat.set_shader_parameter("erosion_opacity", EROSION_OPACITY_MAX)
		_:
			# 后摇（演示用）：缓缓退散，模拟「战斗结束，AI 回到日常模式」
			var t := (battle_time - PHASE3_END) / (AFTER_END - PHASE3_END)
			var k := clampf(t, 0.0, 1.0)
			overlay_mat.set_shader_parameter("erosion_progress", 0.9 * (1.0 - k))
			overlay_mat.set_shader_parameter("erosion_opacity", EROSION_OPACITY_MAX * (1.0 - k))


func _phase_of(t: float) -> int:
	if t <= PHASE1_END:
		return 1
	if t <= PHASE2_END:
		return 2
	if t <= PHASE3_END:
		return 3
	return 4


# ---- 外部控制接口（W3 战斗系统/交互事件调用）----

func reset_battle() -> void:
	"""重置战斗（重开时调用）。"""
	battle_time = 0.0
	current_phase = 0

func set_erosion_progress(p: float) -> void:
	"""外部直接控制侵蚀进度（如拖拽阻力触发）。"""
	overlay_mat.set_shader_parameter("erosion_progress", clampf(p, 0.0, 1.0))

func set_erosion_opacity(o: float) -> void:
	"""外部控制遮罩不透明度。"""
	overlay_mat.set_shader_parameter("erosion_opacity", clampf(o, 0.0, 1.0))
