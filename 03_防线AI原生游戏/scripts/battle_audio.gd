# battle_audio.gd —— 战斗四层音轨（W4.3 · 成员 A · 2026-08-31）
# Autoload（注册片段见 W4/audio/战斗音频实现说明.md §5，由 B 加一行即可）。
# 四层：
#   heartbeat  心跳层 —— 程序合成（AudioStreamGenerator 正弦 thump），无需外部资源；bpm 曲线来自
#              W3.3 pressure_params.json heartbeat_bpm.table_curve（B4 冲突已按表编码，见说明文档）
#   strings    战斗弦乐层 —— battle_strings.ogg（BGM#4 的元素层，见 W4/audio/BGM4作曲Brief.md）
#   noise      白噪爆发层 —— 程序合成（按 phase 区间随机爆发，0.5s 短爆）
#   friend     旧友旋律动机层 —— friend_motif.ogg；阶段二断续（开沉交错）/阶段三持续清晰
#
# 降级语义（任务要求：资源缺失静默降级）：
#   strings/friend 资源不存在 → 该层禁用 + push_warning，其余层照常；heartbeat/noise 永不依赖资源。
#   任何资源 load 失败都不会使入口抛错（_try_load_* 全部防御）。
#
# 公共 API：
#   start_battle() / stop_battle(fade_secs) / set_phase(p) / set_pressure(p)
#   trigger_glitch()（sfx_glitch.wav，QTE 失败/记忆闪烁用）/ get_bpm() / is_running()
#   signal battle_audio_phase_changed(new_phase) / battle_audio_glitch(burst_only)
#
# 注意：函数按「先定义后调用」排列；_ready 与 _process 置末。

class_name BattleAudio
extends Node

# ---- 路径（与 W4/audio 说明文档、BGM4 Brief 一致）----
const STRINGS_PATH := "res://assets/audio/battle_strings.ogg"
const FRIEND_PATH := "res://assets/audio/friend_motif.ogg"
const GLITCH_PATH := "res://assets/audio/sfx_glitch.wav"

# ---- 心跳 bpm 曲线（pressure_params.json heartbeat_bpm.table_curve 原值；B4 定稿上限 160）----
const BPM_TABLE: Array = [[0, 120], [15, 130], [30, 140], [45, 150], [60, 160], [90, 160]]
const AFTERMATH_BPM := 110

# ---- 噪声爆发（pressure_params.json layer_noise）----
const NOISE_DURATION := 0.5                 # 每次爆发时长（秒）
const NOISE_INTERVALS := {                  # [min, max] 秒
	"phase1": [8.0, 10.0],
	"phase2": [7.0, 9.0],
	"phase3": [6.0, 8.0],
}
const NOISE_AMPLITUDE := 0.34
const NOISE_TAU := 6.0                      # 爆发包络衰减速度（指数）

# ---- 弦乐层音量（pressure_params.json layer_strings.volumes）----
const STRINGS_VOLUME := {"phase1": 0.8, "phase2_start": 0.8, "phase2_end": 0.5, "phase3": 0.4}
const STRINGS_AFTERMATH_TO_DB := -30.0

# ---- 旧友动机层（pressure_params.json layer_friend）----
const FRIEND_VOLUME := {"phase2": 0.5, "phase3": 0.6}
const FRIEND_STUTTER_PERIOD := 1.4          # 断续周期（秒）：0.75 开 / 0.65 沉
const FRIEND_STUTTER_ON := 0.75

# ---- 心跳 thump 合成参数 ----
const THUMP_BASE := 85.0                    # 主叩声频率（Hz）
const THUMP_CLICK := 220.0                  # 次叩声频率（Hz）
const THUMP_AMP := 0.62
const THUMP_LEN := 0.30                     # 单次 thump 时长（秒）
const MIX_RATE := 44100.0

var _running := false
var _elapsed := 0.0                         # 战斗内计时（秒），aftermath 继续走
var _phase := "idle"                        # idle/phase1/phase2/phase3/aftermath
var _bpm := 120
var _beat_accum := 0.0                      # 距下一拍的时间（秒）
var _noise_accum := 0.0                     # 距下次爆发的计时
var _noise_interval := 9.0
var _pressure := 0.5                        # 0~1（W4.1 契约 pressure_level）

# 层节点
var _heartbeat_player: AudioStreamPlayer
var _heartbeat_pb: AudioStreamGeneratorPlayback
var _noise_player: AudioStreamPlayer
var _noise_pb: AudioStreamGeneratorPlayback
var _strings_player: AudioStreamPlayer
var _friend_player: AudioStreamPlayer
var _glitch_player: AudioStreamPlayer

var _strings_available := false
var _friend_available := false
var _friend_mode := ""                      # ""=off / "stutter" / "steady"
var _friend_stutter_t := 0.0


# ── 公共 API ──

## 战斗开始（5.1 触发）：phase1 参数立即可用。
func start_battle() -> void:
	_elapsed = 0.0
	_beat_accum = 0.0
	_noise_accum = 2.0                       # 开场先给一段安静，第 8-10s 第一次爆发
	_noise_interval = _roll_noise_interval()
	_running = true
	_set_phase("phase1", true)
	print("[BattleAudio] 战斗开始 → phase1（bpm %d）" % _bpm)


## 战斗结束（5.5 后摇完毕，或 resolve_battle 调用处）：全层淡出。
func stop_battle(fade_secs: float = 2.0) -> void:
	_running = false
	_phase = "idle"
	for p in [_heartbeat_player, _noise_player, _strings_player, _friend_player]:
		if p != null:
			_fade_player(p, -40.0, fade_secs)
	_heartbeat_pb = null
	_noise_pb = null
	print("[BattleAudio] 战斗结束，全层淡出 %.1fs" % fade_secs)


## 设置战斗阶段："phase1" / "phase2" / "phase3" / "aftermath"。
func set_phase(phase: String) -> void:
	_set_phase(phase, false)


## 压力值（0~1）注入：驱动噪声密度与弦乐微压（压力越高越密/越小）。
func set_pressure(p: float) -> void:
	_pressure = clampf(p, 0.0, 1.0)


## QTE 失误 / 记忆闪烁：触发 glitch 音（sfx_glitch.wav 0.5s）。
## burst_only=true 时仅音效（考古 4.x.5 闪烁用）；false 时附 battle_audio_glitch 信号（接战斗视觉裂纹）。
func trigger_glitch(burst_only: bool = true) -> void:
	if _glitch_player != null:
		_glitch_player.stop()
		_glitch_player.play()
	battle_audio_glitch.emit(burst_only)
	if burst_only:
		print("[BattleAudio] glitch 音效（记忆闪烁）")
	else:
		print("[BattleAudio] glitch 音效 + 战斗裂纹信号")


func get_bpm() -> int:
	return _bpm


func is_running() -> bool:
	return _running


## 立即触发一次白噪爆发（外部可调；本轮 0.5s 短路程由引擎定时器驱动，默认用不到）。
func debug_noise_burst() -> void:
	_push_noise_burst()


# ── 阶段切换 ──

func _set_phase(phase: String, quiet: bool) -> void:
	_phase = phase
	match phase:
		"phase1":
			_bpm = _bpm_from_elapsed()
			_set_strings_volume(STRINGS_VOLUME["phase1"], 0.6)
			_set_friend_mode("")
		"phase2":
			_bpm = _bpm_from_elapsed()
			_set_strings_volume(STRINGS_VOLUME["phase2_start"], 0.6)  # 随后由 _process 线性渐降至 0.5
			_set_friend_mode("stutter")
		"phase3":
			_bpm = _bpm_from_elapsed()
			_set_strings_volume(STRINGS_VOLUME["phase3"], 0.8)
			_set_friend_mode("steady")
		"aftermath":
			_bpm = AFTERMATH_BPM
			_set_strings_volume_db(STRINGS_AFTERMATH_TO_DB, 2.0)
			_set_friend_mode("")
		_:
			push_warning("[BattleAudio] 未知 phase：%s" % phase)
			return
	if not quiet:
		battle_audio_phase_changed.emit(phase)
		print("[BattleAudio] phase → %s（bpm %d，pressure %.2f）" % [phase, _bpm, _pressure])


func _bpm_from_elapsed() -> int:
	# 阶梯表（pressure_params.table_curve）：与心跳表格一致；B4 定稿后如改 160 上限只改本表。
	var bpm := BPM_TABLE[0][1]
	for row in BPM_TABLE:
		if _elapsed >= float(row[0]):
			bpm = int(row[1])
	return bpm


func _roll_noise_interval() -> float:
	var itv: Array = NOISE_INTERVALS.get(_phase, [8.0, 10.0])
	# 压力越高，间隔越密（压力 0→1 映射为 1.15x~0.8x）
	var factor := lerpf(1.15, 0.8, _pressure)
	return randf_range(float(itv[0]), float(itv[1])) * factor


func _set_strings_volume(v: float, fade_secs: float) -> void:
	if _strings_player == null:
		return
	_fade_player(_strings_player, linear_to_db(v), fade_secs)


func _set_strings_volume_db(v_db: float, fade_secs: float) -> void:
	if _strings_player == null:
		return
	_fade_player(_strings_player, v_db, fade_secs)


func _set_friend_mode(mode: String) -> void:
	_friend_mode = mode
	_friend_stutter_t = 0.0
	if _friend_player == null:
		return
	match mode:
		"stutter":
			_fade_player(_friend_player, linear_to_db(FRIEND_VOLUME["phase2"]), 0.4)
		"steady":
			_fade_player(_friend_player, linear_to_db(FRIEND_VOLUME["phase3"]), 0.4)
		_:
			_fade_player(_friend_player, -40.0, 0.6)


func _fade_player(p: AudioStreamPlayer, to_db: float, secs: float) -> void:
	if p == null:
		return
	if _tween_for_volume.has(p) and _tween_for_volume[p] != null and _tween_for_volume[p].is_valid():
		_tween_for_volume[p].kill()
	var tw := create_tween()
	tw.tween_property(p, "volume_db", to_db, maxf(0.01, secs))
	_tween_for_volume[p] = tw		# 音量 tween 引用表：防止并发 tween 打架


# ── 每帧驱动（心跳节拍器 + 噪声爆发时机 + friend 断续方波）──

func _process(delta: float) -> void:
	if not _running:
		return
	_elapsed += delta

	# bpm 阶梯推进（phase1-3；aftermath 固定）
	if _phase != "aftermath":
		_bpm = _bpm_from_elapsed()

	# 弦乐层线性渐降（phase2 区间 30→60s：0.8→0.5，对应 pressure_params layer_strings）
	if _phase == "phase2" and _strings_player != null:
		var pct := clampf((_elapsed - 30.0) / 30.0, 0.0, 1.0)
		_strings_player.volume_db = linear_to_db(
			lerpf(STRINGS_VOLUME["phase2_start"], STRINGS_VOLUME["phase2_end"], pct))

	# 心跳：拍距推进，到拍触发 thump
	_beat_accum -= delta
	if _beat_accum <= 0.0:
		_push_thump()
		_beat_accum += 60.0 / maxf(float(_bpm), 1.0)

	# 噪声爆发
	_noise_accum -= delta
	if _noise_accum <= 0.0:
		_push_noise_burst()
		_noise_accum = _roll_noise_interval()

	# friend 断续方波（phase2）
	if _friend_mode == "stutter" and _friend_player != null and _friend_available:
		_friend_stutter_t += delta
		var on := fmod(_friend_stutter_t, FRIEND_STUTTER_PERIOD) < FRIEND_STUTTER_ON
		var vol := linear_to_db(FRIEND_VOLUME["phase2"] if on else 0.003)
		if not is_equal_approx(_friend_player.volume_db, vol):
			_friend_player.volume_db = vol


# ── 程序合成：心跳 thump ──

func _push_thump() -> void:
	if _heartbeat_pb == null or not _heartbeat_pb.can_push_buffer():
		return
	var n := int(THUMP_LEN * MIX_RATE)
	var buf := PackedVector2Array()
	buf.resize(n)
	var amp := THUMP_AMP * lerpf(1.0, 1.06, _pressure)   # 压力越高，心跳越重
	for i in n:
		var t := float(i) / MIX_RATE
		var s := amp * (0.70 * sin(TAU * THUMP_BASE * t) * exp(-t * 22.0)
			+ 0.30 * sin(TAU * THUMP_CLICK * t) * exp(-t * 55.0))
		buf[i] = Vector2(s, s)
	_heartbeat_pb.push_buffer(buf)


# ── 程序合成：白噪爆发（0.5s 短爆，指数包络）──

func _push_noise_burst() -> void:
	if _noise_pb == null or not _noise_pb.can_push_buffer():
		return
	var n := int(NOISE_DURATION * MIX_RATE)
	var buf := PackedVector2Array()
	buf.resize(n)
	for i in n:
		var t := float(i) / MIX_RATE
		var s := NOISE_AMPLITUDE * randf_range(-1.0, 1.0) * exp(-t * NOISE_TAU)
		buf[i] = Vector2(s, s)
	_noise_pb.push_buffer(buf)


# ── 资源加载（全部防御：缺失→静默降级，仅 warning）──

func _try_load_player(path: String, bus: String = "Master") -> AudioStreamPlayer:
	if not ResourceLoader.exists(path):
		push_warning("[BattleAudio] 资源缺失，该层禁用：%s" % path)
		return null
	var stream: AudioStream = load(path)
	if stream == null:
		push_warning("[BattleAudio] 资源加载失败，该层禁用：%s" % path)
		return null
	var p := AudioStreamPlayer.new()
	p.stream = stream
	p.bus = bus
	add_child(p)
	return p


func _make_generator_player() -> AudioStreamPlayer:
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = MIX_RATE
	gen.buffer_length = 0.5
	var p := AudioStreamPlayer.new()
	p.stream = gen
	add_child(p)
	return p


var _tween_for_volume := {}    # AudioStreamPlayer -> Tween（音量淡变防重叠）


# ── 入口 ──

func _ready() -> void:
	_tween_for_volume = {}

	# 心跳层（合成器，无资源依赖）
	_heartbeat_player = _make_generator_player()
	_heartbeat_player.play()
	_heartbeat_pb = _heartbeat_player.get_stream_playback()

	# 噪声层（合成器，无资源依赖）
	_noise_player = _make_generator_player()
	_noise_player.play()
	_noise_pb = _noise_player.get_stream_playback()

	# 弦乐层 / 旧友动机层（资源缺失→null→层禁用）
	_strings_player = _try_load_player(STRINGS_PATH)
	_strings_available = _strings_player != null
	_friend_player = _try_load_player(FRIEND_PATH)
	_friend_available = _friend_player != null

	# glitch 音（W3 待人工 #2 补交：0.5s 白噪/电流音）
	_glitch_player = _try_load_player(GLITCH_PATH)

	if _strings_player != null:
		_strings_player.volume_db = -60.0
	if _friend_player != null:
		_friend_player.volume_db = -60.0

	print("[BattleAudio] 就绪：heartbeat 合成 ✔ / noise 合成 ✔ / strings %s / friend %s / glitch %s" % [
		("✔" if _strings_available else "—（禁用）"),
		("✔" if _friend_available else "—（禁用）"),
		("✔" if _glitch_player != null else "—（禁用）"),
	])
