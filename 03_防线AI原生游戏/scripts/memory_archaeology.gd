# memory_archaeology.gd —— 记忆考古关卡控制器（Autoload 单例）
# 流程：start(anchor_id) → fetch 3 versions → 3s countdown → player choose → judge → reveal
# 当前从 fake_memory_cache 取版本；上游 LLM 可用后切到 LLMGateway.analyze_memory()

extends Node

enum State { IDLE, COUNTDOWN, CHOOSING, ENDED }

## 难度系数 1/2/3 — 关卡 1 辨识度高(易识别) → 关卡 3 辨识度低(极难)
var difficulty: int = 1

var _state: int = State.IDLE
var _current_anchor_id: String = ""
var _current_emotion: String = ""
var _current_variants: Array = []
var _countdown_remaining: float = 0.0
const COUNTDOWN_SEC := 3.0

var _fake_cache: FakeMemoryCache

## 记忆闪烁音效(A 提供 sfx_glitch.wav,B 预留加载路径)
const GLITCH_SFX_PATH := "res://assets/audio/sfx_glitch.wav"
var _glitch_player: AudioStreamPlayer

## 关卡配置(3 关)
const LEVEL_CONFIG := [
	{
		"level": 1,
		"anchor_id": "MA_BRACELET_01",
		"title": "蓝色贝壳的手链",
		"difficulty_desc": "70%（易识别）",
		"identification_difficulty": 0.70,
	},
	{
		"level": 2,
		"anchor_id": "MA_ROSE_01",
		"title": "紫色的玫瑰",
		"difficulty_desc": "50%（中等）",
		"identification_difficulty": 0.50,
	},
	{
		"level": 3,
		"anchor_id": "MA_FLOWER_01",
		"title": "针织的蓝色花朵",
		"difficulty_desc": "30%（极难）",
		"identification_difficulty": 0.30,
	},
]


signal archaeology_started(anchor_id: String, difficulty: int)
## C 接此信号显示关卡主题标题(进入 memory_card 模式)
signal level_started(level: int, title: String, anchor_id: String, difficulty_desc: String)
signal variants_shown(variants: Array)
signal countdown_updated(remaining: float)
signal choices_enabled()
signal choice_recorded(variant_id: String, is_truth: bool, truth_shard: String)
## C 接此信号做屏幕白屏(intensity:1=选对-轻 / 2=选错-强)
signal flash_triggered(intensity: int)
## C 接此信号切 visual_novel 模式解锁旧友视角(full=完整 / partial=片段+AI修正)
signal truth_shard_unlock(level: String, shard: String)
signal archaeology_ended(success: bool, truth_shard: String)


## 关卡启动器 — level:1=手链 / 2=玫瑰 / 3=花朵；C 在场景切换时调用
## 已在关卡中时整体忽略（不会发出 level_started）——守卫必须先于 emit：
## 否则 level_started 已把消费方的 UI 重置，而 start() 随后拒绝开局，玩家会卡在空界面。
func start_level(level: int, emotion: String = "") -> void:
	if _state != State.IDLE and _state != State.ENDED:
		push_warning("[MemoryArchaeology] 已在进行中,忽略 start_level(%d)" % level)
		return
	var cfg: Dictionary = {}
	for c in LEVEL_CONFIG:
		if int(c["level"]) == level:
			cfg = c
			break
	if cfg.is_empty():
		push_warning("[MemoryArchaeology] 关卡 %d 不在 LEVEL_CONFIG 中" % level)
		return
	# 先 emit 关卡引入信号(C 接后切到 memory_card 模式显示标题)
	level_started.emit(level, cfg["title"], cfg["anchor_id"], cfg["difficulty_desc"])
	# 默认 emotion:取 anchors.json 的 emotion_options[0](若有);为空则 LLM 由调度层 fallback
	var default_emotion: String = emotion if emotion != "" else "被时间带走的忐忑"
	start(cfg["anchor_id"], default_emotion, level)


func _ready() -> void:
	# MemoryAnchorUI 是 autoload，启动顺序保证 ANCHOR_MAP 已加载
	var anchor_map: Dictionary = MemoryAnchorUI.ANCHOR_MAP
	_fake_cache = FakeMemoryCache.new(anchor_map)
	print("[MemoryArchaeology] 启动；锚点数据 %d 条" % anchor_map.size())
	_setup_glitch_player()


## 开始一个关卡
## diff:1=最容易 / 2=中等 / 3=最难
func start(anchor_id: String, emotion: String, diff: int = 1) -> void:
	if _state != State.IDLE and _state != State.ENDED:
		push_warning("[MemoryArchaeology] 已在进行中,忽略 start()")
		return
	difficulty = diff
	_current_anchor_id = anchor_id
	_current_emotion = emotion
	archaeology_started.emit(anchor_id, difficulty)
	_current_variants = _fetch_variants(anchor_id, emotion)
	variants_shown.emit(_current_variants)
	_state = State.COUNTDOWN
	_countdown_remaining = COUNTDOWN_SEC


func _process(delta: float) -> void:
	if _state != State.COUNTDOWN:
		return
	_countdown_remaining -= delta
	countdown_updated.emit(_countdown_remaining)
	if _countdown_remaining <= 0.0:
		_countdown_remaining = 0.0
		_state = State.CHOOSING
		choices_enabled.emit()


## 玩家选择某个版本
## variant_id:"truth" / "neg_distortion" / "micro_drift"
func choose(variant_id: String) -> void:
	if _state != State.CHOOSING:
		push_warning("[MemoryArchaeology] 不在 CHOOSING 状态,忽略 choose()")
		return
	# 单循环同时找出玩家选的和真相版
	var picked: Dictionary = {}
	var truth: Dictionary = {}
	for v in _current_variants:
		if v["variant_id"] == variant_id:
			picked = v
		if v["is_truth"]:
			truth = v
	var success: bool = picked.get("is_truth", false)
	var truth_shard: String = truth.get("text", "")

	var intensity: int = 1 if success else 2
	_play_flash(intensity)

	choice_recorded.emit(variant_id, success, truth_shard)

	var unlock_level: String = "full" if success else "partial"
	truth_shard_unlock.emit(unlock_level, truth_shard)

	_record_archaeology_result(_current_anchor_id, success, unlock_level)

	_state = State.ENDED
	archaeology_ended.emit(success, truth_shard)


func abort() -> void:
	_state = State.ENDED
	archaeology_ended.emit(false, "")


func get_state() -> int:
	return _state


func _fetch_variants(anchor_id: String, emotion: String) -> Array:
	if _fake_cache == null:
		return []
	# 上游 LLM 可用后改为：LLMGateway.analyze_memory(template_text, emotion, anchor_id)
	return _fake_cache.get_variants(anchor_id, emotion)


# ============================================================================
# 记忆闪烁
# ============================================================================

func _setup_glitch_player() -> void:
	_glitch_player = AudioStreamPlayer.new()
	_glitch_player.bus = "SFX"
	add_child(_glitch_player)
	if ResourceLoader.exists(GLITCH_SFX_PATH):
		_glitch_player.stream = load(GLITCH_SFX_PATH)
	else:
		push_warning("[MemoryArchaeology] %s 未找到(A 待提供);闪烁时只触发 flash_triggered 信号" % GLITCH_SFX_PATH)


func _play_flash(intensity: int) -> void:
	if _glitch_player and _glitch_player.stream:
		_glitch_player.play()
	flash_triggered.emit(intensity)


# ============================================================================
# 状态写入(供战斗阶段引用)
# ============================================================================

func _record_archaeology_result(anchor_id: String, success: bool, unlock_level: String) -> void:
	# TODO:TrustDrift 提供 record_archaeology_result() 接口后切换
	if Engine.has_singleton("TrustDrift") or has_node("/root/TrustDrift"):
		pass
	else:
		print("[MemoryArchaeology] 写入考古结果: %s success=%s level=%s" % [anchor_id, success, unlock_level])


# ============================================================================
# 调试用
# ============================================================================

func simulate_full_run(anchor_id: String, emotion: String, player_picks_truth: bool = true) -> Dictionary:
	# 一键模拟完整关卡（跳过倒计时，立即可选）
	start(anchor_id, emotion, 1)
	if _state == State.COUNTDOWN:
		_countdown_remaining = 0.0
		countdown_updated.emit(0.0)
		_state = State.CHOOSING
		choices_enabled.emit()
	var pick := "truth" if player_picks_truth else "neg_distortion"
	choose(pick)
	return {
		"anchor_id": anchor_id,
		"emotion": emotion,
		"picked": pick,
		"success": player_picks_truth,
	}