# trust_pressure_mapper.gd —— B2「压力二轨制」映射层 + B1 QTE 窗口阶梯（W5 · T2）
#
# 数据依据（B 拍板终稿，数值不可改）：
#   · defenseline_B_docs/pressure_params.md          §B2 二轨制 / §B1 3 战 × 3 tier 窗口阶梯
#   · defenseline_B_docs/battle_difficulty_curve.md  §4 参数（reaction_window / hint_delay 逐格值）
#   · defenseline_B_docs/battle_narrative_rhythm.md  3 战信任轨迹（第 1/2/3 战语义）
#
# 本文件只做「映射」，**不改任何既有文件**：
#   · B2：pressure_level 拆二轨 —— dialogue 轨（话术宽松，与 trust_drift 负相关）
#                                qte 轨（操作接管，与 trust_drift 正相关）
#   · B1：反应窗阶梯 3 战 × 3 tier（3.0 → 1.0s）；hint_delay 阶梯一并提供
#
# 【数值外置（w5-t2.1）】下方 const 是**内置默认值**（= B 终稿，永远可用的兜底）；
#   启动时 _ready() 会读 config/pressure_mapping.json 覆盖它们 —— B/C 调参改 JSON 即可，
#   无需改代码，也不会出现「数值写在两个 .gd 里」的同步问题。
#   逐项独立生效：JSON 缺失 / 解析失败 / 某一项非法 → **只有那一项**回退内置常量 + push_warning，
#   其余项照常生效，且绝不阻断战斗流程。current_mapping_source() 可查本次实际用了哪一层。
#
# 接入方式由 B 决定（Autoload 注册 / 并入 trust_drift_collector / 战斗脚本局部实例化）；
# 三种方式的侵入度对照见 W5/patches/B2二轨制映射补丁说明.md。
#
# 自测：实例化后调用 self_test()，打印双轨表 + 9 格窗口表 + 边界用例。
#       回归测试（不需改工程、不依赖 Autoload）：
#         Godot_v4.6.3-stable_win64_console.exe --headless --path <repo> -s scripts/tests/test_trust_pressure_mapper.gd
#         退出码 0 = 全绿；1 = 有失败项（可直接接 CI）

extends Node

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

const TRUST_DRIFT_MIN := -10.0
const TRUST_DRIFT_MAX := 10.0
const TRUST_DRIFT_SPAN := 20.0  # MAX - MIN

const TIER_LOW := "LOW_TRUST"
const TIER_MEDIUM := "MEDIUM_TRUST"
const TIER_HIGH := "HIGH_TRUST"

# B1 · 反应窗阶梯（秒）：battle_index(1..3) → tier → 秒
# 第1战 3.0/2.5/2.0 ；第2战 2.5/2.0/1.5 ；第3战 2.0/1.5/1.0（HIGH 第 3 战 1.0s 为全局最短）
const QTE_WINDOW_TABLE := {
	1: {"LOW_TRUST": 3.0, "MEDIUM_TRUST": 2.5, "HIGH_TRUST": 2.0},
	2: {"LOW_TRUST": 2.5, "MEDIUM_TRUST": 2.0, "HIGH_TRUST": 1.5},
	3: {"LOW_TRUST": 2.0, "MEDIUM_TRUST": 1.5, "HIGH_TRUST": 1.0},
}

# B1 附带 · hint_delay 阶梯（秒）：第1战 0.0/0.0/1.0 ；第2战 0.0/2.0/3.0 ；第3战 2.0/4.0/5.0
const HINT_DELAY_TABLE := {
	1: {"LOW_TRUST": 0.0, "MEDIUM_TRUST": 0.0, "HIGH_TRUST": 1.0},
	2: {"LOW_TRUST": 0.0, "MEDIUM_TRUST": 2.0, "HIGH_TRUST": 3.0},
	3: {"LOW_TRUST": 2.0, "MEDIUM_TRUST": 4.0, "HIGH_TRUST": 5.0},
}

# ⚠️⚠️ A 建议值，待 B 复核 ⚠️⚠️
# trust_drift_collector 的 score 是**累加制、只增不减**（0 起，无负值），
# 而 B2 的压力公式需要 -10~+10 的 trust_drift。此处按 tier 取**代表锚点**换算：
#   score < 3  → -5.0（LOW）   3 ≤ score < 7 → 0.0（MEDIUM）   score ≥ 7 → +7.0（HIGH）
# 阈值 3 / 7 与 scripts/trust_drift_collector.gd 的 get_trust_tier() 保持一致；
# **若 B 调整 tier 阈值、或改用 drift 制，必须同步改这三个锚点常量。**
const SCORE_TO_MEDIUM := 3.0      # score < 3 → LOW
const SCORE_TO_HIGH := 7.0        # 3 ≤ score < 7 → MEDIUM ；≥ 7 → HIGH
const DRIFT_ANCHOR_LOW := -5.0    # ⚠️ A 建议值（B 未拍 LOW 的具体 drift 数值）
const DRIFT_ANCHOR_MEDIUM := 0.0  # ⚠️ A 建议值（取 v0.2 区间「中性 -2~+2」的中点）
const DRIFT_ANCHOR_HIGH := 7.0    # ⚠️ A 建议值（对齐 B1/B3 第 3 战档位与 v0.2「+7~+10」下限）

## TrustDrift Autoload 路径（缺失时回退 MEDIUM，不报错）
const TRUST_DRIFT_AUTOLOAD := "/root/TrustDrift"

## 外部数值表（见文件头「数值外置」；A owner，B 可覆盖）
const PRESSURE_MAPPING_PATH := "res://config/pressure_mapping.json"


# ---------------------------------------------------------------------------
# 运行时可覆盖的映射值（默认 = 上面的内置常量；_ready() 时由 JSON 覆盖）
# ---------------------------------------------------------------------------

var _drift_min: float = TRUST_DRIFT_MIN
var _drift_max: float = TRUST_DRIFT_MAX
var _qte_window_table: Dictionary = QTE_WINDOW_TABLE.duplicate(true)
var _hint_delay_table: Dictionary = HINT_DELAY_TABLE.duplicate(true)
var _score_to_medium: float = SCORE_TO_MEDIUM
var _score_to_high: float = SCORE_TO_HIGH
var _anchor_low: float = DRIFT_ANCHOR_LOW
var _anchor_medium: float = DRIFT_ANCHOR_MEDIUM
var _anchor_high: float = DRIFT_ANCHOR_HIGH

## 本次实际生效的数值来源（诊断用；self_test()/回归测试会打印与断言）
var _mapping_source: String = "内置常量（尚未加载）"
var _mapping_used: Array[String] = []
var _mapping_skipped: Array[String] = []


func _ready() -> void:
	reload_mapping()


# ---------------------------------------------------------------------------
# 数值表加载（容错：任何一项坏掉都只回退那一项，绝不抛错、绝不阻断战斗）
# ---------------------------------------------------------------------------

## 把全部运行时值重置为内置常量（每次 reload 先重置 → 失败时不留上一次的残值）
func _reset_to_builtin() -> void:
	_drift_min = TRUST_DRIFT_MIN
	_drift_max = TRUST_DRIFT_MAX
	_qte_window_table = QTE_WINDOW_TABLE.duplicate(true)
	_hint_delay_table = HINT_DELAY_TABLE.duplicate(true)
	_score_to_medium = SCORE_TO_MEDIUM
	_score_to_high = SCORE_TO_HIGH
	_anchor_low = DRIFT_ANCHOR_LOW
	_anchor_medium = DRIFT_ANCHOR_MEDIUM
	_anchor_high = DRIFT_ANCHOR_HIGH


## 读外部数值表覆盖内置常量；返回来源描述。可重复调用（运行中热重载调参）。
## path 可覆写（回归测试用）；任何失败都保持内置常量，绝不抛错。
func reload_mapping(path: String = PRESSURE_MAPPING_PATH) -> String:
	_reset_to_builtin()
	_mapping_used.clear()
	_mapping_skipped.clear()

	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_warning("[TrustPressureMapper] %s 未找到 → 全部使用内置常量" % path)
		_mapping_source = "内置常量（JSON 缺失）"
		return _mapping_source
	var text := f.get_as_text()
	f.close()

	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("[TrustPressureMapper] %s 解析失败（非 JSON 对象）→ 全部使用内置常量" % path)
		_mapping_source = "内置常量（JSON 非法）"
		return _mapping_source

	# ① trust_drift 定义域
	var drift_raw = parsed.get("trust_drift")
	if typeof(drift_raw) == TYPE_DICTIONARY:
		var lo := _valid_float(drift_raw.get("min"), TRUST_DRIFT_MIN)
		var hi := _valid_float(drift_raw.get("max"), TRUST_DRIFT_MAX)
		if hi > lo:
			_drift_min = lo
			_drift_max = hi
			_mapping_used.append("trust_drift")
		else:
			_mapping_skipped.append("trust_drift(max<=min)")
	else:
		_mapping_skipped.append("trust_drift(缺失)")

	# ② 两张 3×3 阶梯表（整表校验：缺任意一格即整表回退，避免"半新半旧"的混值）
	var qte := _parse_table(parsed.get("qte_window_table"), QTE_WINDOW_TABLE)
	if qte.is_empty():
		_mapping_skipped.append("qte_window_table(缺失/格数不足)")
	else:
		_qte_window_table = qte
		_mapping_used.append("qte_window_table")

	var hint := _parse_table(parsed.get("hint_delay_table"), HINT_DELAY_TABLE)
	if hint.is_empty():
		_mapping_skipped.append("hint_delay_table(缺失/格数不足)")
	else:
		_hint_delay_table = hint
		_mapping_used.append("hint_delay_table")

	# ③ collector score → drift 锚点（逐项独立回退）
	var c2d = parsed.get("collector_to_drift")
	if typeof(c2d) == TYPE_DICTIONARY:
		_score_to_medium = _valid_float(c2d.get("score_to_medium"), SCORE_TO_MEDIUM)
		_score_to_high = _valid_float(c2d.get("score_to_high"), SCORE_TO_HIGH)
		_anchor_low = _valid_float(c2d.get("anchor_low"), DRIFT_ANCHOR_LOW)
		_anchor_medium = _valid_float(c2d.get("anchor_medium"), DRIFT_ANCHOR_MEDIUM)
		_anchor_high = _valid_float(c2d.get("anchor_high"), DRIFT_ANCHOR_HIGH)
		_mapping_used.append("collector_to_drift")
	else:
		_mapping_skipped.append("collector_to_drift(缺失)")

	_mapping_source = "JSON(%s) used=[%s]%s" % [
		path.get_file(),
		", ".join(_mapping_used),
		"" if _mapping_skipped.is_empty() else " skipped=[" + ", ".join(_mapping_skipped) + "]",
	]
	if not _mapping_skipped.is_empty():
		push_warning("[TrustPressureMapper] 以下项未采用 JSON 值、已回退内置常量：%s"
			% ", ".join(_mapping_skipped))
	return _mapping_source


## 本次实际生效的数值来源（诊断/测试用）
func current_mapping_source() -> String:
	return _mapping_source


## 纯数值判定（bool 不算数字，避免 true→1.0 这类静默转换）
func _is_number(v) -> bool:
	return typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT


## 取 JSON 数值，非法则回退 default
func _valid_float(v, default_value: float) -> float:
	return float(v) if _is_number(v) else default_value


## 解析 3×3 阶梯表：以 default_table 的键为准逐格取值，
## 任一格缺失或非数字 → 返回 {}（调用方据此整表回退）。
func _parse_table(raw, default_table: Dictionary) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return {}
	var built := {}
	for battle in default_table.keys():
		var row_raw = raw.get(str(battle))
		if typeof(row_raw) != TYPE_DICTIONARY:
			return {}
		var row := {}
		for tier in default_table[battle].keys():
			var cell = row_raw.get(tier)
			if not _is_number(cell):
				return {}
			row[tier] = float(cell)
		built[battle] = row
	return built


## 运行时定义域跨度（内置常量 TRUST_DRIFT_SPAN 是默认值；JSON 覆盖 min/max 后以此为准）
func _drift_span() -> float:
	return _drift_max - _drift_min


# ---------------------------------------------------------------------------
# B2 · 二轨制映射
# ---------------------------------------------------------------------------

## 话术轨压迫度：trust_drift -10~+10 → 1.0~0.0（**负相关**）
## 值越高 = AI 话术压迫越用力。注意：B2 的 dialogue 轨在实现上只驱动
## 「压迫感/话术克制度」，**不驱动 warmth**——warmth 恒高 0.85~0.95（AI 始终温柔）。
func dialogue_pressure(t: float) -> float:
	return (_drift_max - _clamp_drift(t)) / _drift_span()


## 操作接管轨：trust_drift -10~+10 → 0.0~1.0（**正相关**）
## 值越高 = AI 越接管操作（反应窗越短、hint 越提前等）。
func qte_pressure(t: float) -> float:
	return (_clamp_drift(t) - _drift_min) / _drift_span()


## 双轨一次取全：{"dialogue": 0.0~1.0, "qte": 0.0~1.0}
## 两极锚点：t=-10 → (1.0, 0.0) ；t=+10 → (0.0, 1.0)
## 「话术与操作的剪刀差」= 高信任时 dialogue 低（温柔）+ qte 高（接管）。
func pressure_pair(t: float) -> Dictionary:
	var drift := _clamp_drift(t)
	return {
		"dialogue": (_drift_max - drift) / _drift_span(),
		"qte": (drift - _drift_min) / _drift_span(),
	}


# ---------------------------------------------------------------------------
# B1 · QTE 窗口 / hint_delay 阶梯
# ---------------------------------------------------------------------------

## 反应窗（秒）：battle_index 1..3（第 1/2/3 战）；tier 缺省时实时读信任等级。
func battle_qte_window(battle_index: int, tier: String = "") -> float:
	var index := _normalize_battle_index(battle_index)
	var resolved := _resolve_tier(tier)
	return float(_qte_window_table[index][resolved])


## 提示延迟（秒）：同上；
func battle_hint_delay(battle_index: int, tier: String = "") -> float:
	var index := _normalize_battle_index(battle_index)
	var resolved := _resolve_tier(tier)
	return float(_hint_delay_table[index][resolved])


# ---------------------------------------------------------------------------
# 信任来源（⚠️ 换算为 A 建议值，待 B 复核）
# ---------------------------------------------------------------------------

## 从 TrustDrift Autoload 读 score 并换算为 trust_drift（-10~+10 代表锚点）。
## 缺失时回退 MEDIUM 档（0.0），**不报错、不阻断战斗流程**。
func trust_drift_from_collector() -> float:
	# has_node() 走绝对路径，实例未入树时引擎会先报错——先挡一道，保持日志干净
	if not is_inside_tree():
		push_warning("[TrustPressureMapper] 实例未入场景树 → 回退 MEDIUM 锚点 %.1f"
			% _anchor_medium)
		return _anchor_medium

	if not has_node(TRUST_DRIFT_AUTOLOAD):
		push_warning("[TrustPressureMapper] 未找到 %s（TrustDrift 未注册为 Autoload？）→ 回退 MEDIUM 锚点 %.1f"
			% [TRUST_DRIFT_AUTOLOAD, _anchor_medium])
		return _anchor_medium

	var collector := get_node(TRUST_DRIFT_AUTOLOAD)
	if not collector.has_method("get_trust_score"):
		push_warning("[TrustPressureMapper] %s 无 get_trust_score() → 回退 MEDIUM 锚点 %.1f"
			% [TRUST_DRIFT_AUTOLOAD, _anchor_medium])
		return _anchor_medium

	return anchor_for_score(float(collector.get_trust_score()))


## 纯换算：collector 的 score → B2 的 trust_drift 代表锚点（不依赖场景树，可单独测）。
## score < score_to_medium → LOW 锚点；< score_to_high → MEDIUM 锚点；否则 HIGH 锚点。
func anchor_for_score(score: float) -> float:
	if score < _score_to_medium:
		return _anchor_low
	if score < _score_to_high:
		return _anchor_medium
	return _anchor_high


## 公开的「drift → tier」反查（= _tier_from_drift 的对外入口，供接入方与回归测试使用）。
func tier_for_drift(drift: float) -> String:
	return _tier_from_drift(drift)


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------

## 越界一律 clamp 到 [-10, +10]（B2 定义域；JSON 覆盖定义域时以 JSON 为准）
func _clamp_drift(t: float) -> float:
	if is_nan(t):
		push_warning("[TrustPressureMapper] trust_drift 为 NaN → 按 MEDIUM 锚点 %.1f 处理"
			% _anchor_medium)
		return _anchor_medium
	return clampf(t, _drift_min, _drift_max)


## battle_index 越界（非 1~3）→ push_warning + 回退第 1 战
func _normalize_battle_index(battle_index: int) -> int:
	if _qte_window_table.has(battle_index):
		return battle_index
	push_warning("[TrustPressureMapper] battle_index=%d 越界（有效 1~3）→ 回退第 1 战"
		% battle_index)
	return 1


## tier 字符串容错：空串 → 实时读信任等级；含 "HIGH"/"MEDIUM"/"LOW" 即归位；
## 无法识别 → push_warning + MEDIUM。
func _resolve_tier(tier: String) -> String:
	var raw := tier.strip_edges()
	if raw.is_empty():
		return _tier_from_drift(trust_drift_from_collector())
	var upper := raw.to_upper()
	if upper.contains("HIGH"):
		return TIER_HIGH
	if upper.contains("MEDIUM") or upper.contains("MID"):
		return TIER_MEDIUM
	if upper.contains("LOW"):
		return TIER_LOW
	push_warning("[TrustPressureMapper] 无法识别的 tier=%s → 回退 MEDIUM_TRUST" % tier)
	return TIER_MEDIUM


## 锚点反查：+7 及以上 → HIGH ；0 及以上 → MEDIUM ；其余 → LOW
## （与 trust_drift_from_collector() 的三个锚点严格互逆）
func _tier_from_drift(drift: float) -> String:
	if drift >= _anchor_high:
		return TIER_HIGH
	if drift >= _anchor_medium:
		return TIER_MEDIUM
	return TIER_LOW


# ---------------------------------------------------------------------------
# 自测（打印，供 B review / 接入前验证）
# ---------------------------------------------------------------------------

func self_test() -> void:
	print("=== trust_pressure_mapper self_test（B2 二轨制 + B1 窗口阶梯）===")

	print("[数值来源] %s" % _mapping_source)
	if not is_inside_tree():
		print("  （实例未入树：_ready() 未跑，当前为内置常量；入树后会自动读 %s）"
			% PRESSURE_MAPPING_PATH)

	print("[B2] trust_drift → (dialogue_pressure, qte_pressure)")
	for t in [-10.0, -5.0, 0.0, 5.0, 10.0]:
		var pair := pressure_pair(t)
		print("  t=%+6.1f → dialogue=%.4f  qte=%.4f" % [t, pair["dialogue"], pair["qte"]])

	print("[B2] 两极锚点校验：t=-10 → (1.0, 0.0) ；t=+10 → (0.0, 1.0)")
	var lo := pressure_pair(-10.0)
	var hi := pressure_pair(10.0)
	print("  t=-10 → (%.4f, %.4f)  %s" % [lo["dialogue"], lo["qte"],
		"OK" if is_equal_approx(lo["dialogue"], 1.0) and is_equal_approx(lo["qte"], 0.0) else "FAIL"])
	print("  t=+10 → (%.4f, %.4f)  %s" % [hi["dialogue"], hi["qte"],
		"OK" if is_equal_approx(hi["dialogue"], 0.0) and is_equal_approx(hi["qte"], 1.0) else "FAIL"])

	print("[B2] 边界：t=-99 / t=+99 应被 clamp 到 ±10（与两极锚点同值）")
	var below := pressure_pair(-99.0)
	var above := pressure_pair(99.0)
	print("  t=-99 → (%.4f, %.4f)" % [below["dialogue"], below["qte"]])
	print("  t=+99 → (%.4f, %.4f)" % [above["dialogue"], above["qte"]])

	print("[B1] 反应窗阶梯（秒）· 3 战 × 3 tier —— 应逐格等于 B 终稿")
	for battle in [1, 2, 3]:
		var cells: Array[String] = []
		for tier in [TIER_LOW, TIER_MEDIUM, TIER_HIGH]:
			cells.append("%.1f" % battle_qte_window(battle, tier))
		print("  第 %d 战：LOW=%s  MEDIUM=%s  HIGH=%s"
			% [battle, cells[0], cells[1], cells[2]])

	print("[B1] hint_delay 阶梯（秒）")
	for battle in [1, 2, 3]:
		var cells: Array[String] = []
		for tier in [TIER_LOW, TIER_MEDIUM, TIER_HIGH]:
			cells.append("%.1f" % battle_hint_delay(battle, tier))
		print("  第 %d 战：LOW=%s  MEDIUM=%s  HIGH=%s"
			% [battle, cells[0], cells[1], cells[2]])

	print("[容错] battle_index=9（越界）→ 应回退第 1 战值；tier=\"high\"（小写）→ 应识别为 HIGH")
	print("  battle_qte_window(9, LOW)  = %.1f" % battle_qte_window(9, TIER_LOW))
	print("  battle_qte_window(1, \"high\") = %.1f" % battle_qte_window(1, "high"))
	print("  battle_hint_delay(1, \"HIGH_TRUST\") = %.1f" % battle_hint_delay(1, "HIGH_TRUST"))

	print("[容错] tier 缺省（\"\"）→ 实时读 TrustDrift（未注册 Autoload 时回退 MEDIUM 并 push_warning）")
	print("  battle_qte_window(2) = %.1f（入树且 TrustDrift 在线时随实时信任变化）" % battle_qte_window(2))
	print("  trust_drift_from_collector() = %.1f" % trust_drift_from_collector())

	print("=== self_test 结束 ===")
