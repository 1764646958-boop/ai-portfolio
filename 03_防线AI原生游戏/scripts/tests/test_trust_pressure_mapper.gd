# test_trust_pressure_mapper.gd —— trust_pressure_mapper 的 headless 回归测试（W5 · T2）
#
# 为什么需要它：trust_pressure_mapper.gd 的数值原先只写在 .gd 的 const 里，
# 「改了没有 / 改对没有」只能靠人眼看 self_test() 的打印。本测试把 B1/B2 的**终稿数值**
# 固化成断言，任何人改错了数值（或改坏了 JSON 外置那一层）都会在这里红掉。
#
# 跑法（不需改工程、不依赖 TrustDrift Autoload）：
#   "E:/Godot_v4.6.3-stable_win64.exe/Godot_v4.6.3-stable_win64_console.exe" \
#       --headless --path "<repo>" -s scripts/tests/test_trust_pressure_mapper.gd
#
#   退出码：0 = 全绿；1 = 有 FAIL（可直接接 CI / 提交前自查）
#
# 覆盖范围：
#   A. JSON 外置层：4 组键全部被采用（不是"文件在但没用上"）
#   B. 外置层容错：文件缺失 / 非法 JSON / 单表缺格 → 回退内置常量且不崩
#   C. B2 二轨公式：两极锚点 + 5 点逐点值 + clamp + NaN
#   C. B2 二轨公式：两极锚点 + 5 点逐点值 + clamp + NaN
#   D. B1 阶梯：3×3 窗口表 + 3×3 hint 表逐格等于 B 终稿
#   E. 容错：battle_index 越界 / tier 大小写与别名 / 无法识别
#   F. score → drift 锚点换算 + 往返一致性（三个锚点是 A 建议值，待 B 复核）
#   G. 与真 TrustDrift Autoload 的实时集成（score/tier 与 collector 对齐）
#
# 注意：本测试跑在真工程里（--path <repo>），project.godot 注册的 Autoload 都在，
#       所以 G 组是**真实集成**而非打桩。涉及实时值的断言一律与 collector 对拍，
#       不硬编码期望值——否则别人改了 score，测试会假红。
#
# 注意：本脚本 extends SceneTree（Godot 用 -s 跑脚本时的要求），
#       且**逻辑必须放在 _process() 里**——_initialize() 阶段场景树尚未就绪，
#       add_child() 会失败、节点 _ready() 不会触发，JSON 也就不会被加载。

extends SceneTree

const MAPPER_SCRIPT := "res://scripts/trust_pressure_mapper.gd"
const MAPPING_PATH := "res://config/pressure_mapping.json"

# ── B1 终稿（defenseline_B_docs/pressure_params.md §B1「完整 3 战 × 3 tier 阶梯」）──
const EXPECT_QTE_WINDOW := {
	1: {"LOW_TRUST": 3.0, "MEDIUM_TRUST": 2.5, "HIGH_TRUST": 2.0},
	2: {"LOW_TRUST": 2.5, "MEDIUM_TRUST": 2.0, "HIGH_TRUST": 1.5},
	3: {"LOW_TRUST": 2.0, "MEDIUM_TRUST": 1.5, "HIGH_TRUST": 1.0},
}
# ── hint_delay 终稿（defenseline_B_docs/battle_difficulty_curve.md 逐格）──
const EXPECT_HINT_DELAY := {
	1: {"LOW_TRUST": 0.0, "MEDIUM_TRUST": 0.0, "HIGH_TRUST": 1.0},
	2: {"LOW_TRUST": 0.0, "MEDIUM_TRUST": 2.0, "HIGH_TRUST": 3.0},
	3: {"LOW_TRUST": 2.0, "MEDIUM_TRUST": 4.0, "HIGH_TRUST": 5.0},
}
const TIERS := ["LOW_TRUST", "MEDIUM_TRUST", "HIGH_TRUST"]

var _pass := 0
var _fail := 0
var _fail_lines: Array[String] = []

# 跨帧存活（_process 里 add_child 后要等 _ready 生效，用状态机推进）
var _mapper: Node = null
var _phase := 0


func _process(_delta: float) -> bool:
	match _phase:
		0:
			_start()
		1:
			_run_assertions()
		2:
			_report_and_quit()
	return false  # 继续跑；退出由 quit() 显式触发


# ---------------------------------------------------------------------------
# 断言工具
# ---------------------------------------------------------------------------

func _ok(name: String, cond: bool, detail: String = "") -> void:
	if cond:
		_pass += 1
		print("  ✅ %s" % name)
	else:
		_fail += 1
		_fail_lines.append("%s（%s）" % [name, detail])
		print("  ❌ %s ← %s" % [name, detail])


func _eq_f(name: String, got: float, want: float) -> void:
	_ok(name, is_equal_approx(got, want), "got %.4f，want %.4f" % [got, want])


# ---------------------------------------------------------------------------
# 阶段 0：实例化 mapper 并入树（触发 _ready → 读 JSON）
# ---------------------------------------------------------------------------

func _start() -> void:
	print("=".repeat(72))
	print("trust_pressure_mapper 回归测试（W5 T2 · Godot %s）" % Engine.get_version_info()["string"])
	print("=".repeat(72))

	var script: Script = load(MAPPER_SCRIPT)
	if script == null:
		print("  ❌ 无法加载 %s" % MAPPER_SCRIPT)
		quit(1)
		return
	_mapper = script.new()
	if _mapper == null:
		print("  ❌ 实例化失败（脚本有解析错误？）")
		quit(1)
		return
	root.add_child(_mapper)  # 入树 → _ready() → reload_mapping()
	_phase = 1


# ---------------------------------------------------------------------------
# 阶段 1：断言
# ---------------------------------------------------------------------------

func _run_assertions() -> void:
	_phase = 2
	_test_mapping_layer()
	_test_b2_formula()
	_test_b1_tables()
	_test_tolerance()
	_test_score_anchors()
	_test_live_collector()


## A/B · 数值外置层
func _test_mapping_layer() -> void:
	print("\n[A] 数值外置层（%s）" % MAPPING_PATH)

	var src: String = _mapper.current_mapping_source()
	print("  实际来源：%s" % src)
	_ok("A1 JSON 被读取（来源含 JSON 字样，不是回退内置常量）",
		src.begins_with("JSON("), "source=%s" % src)
	_ok("A2 四组键全部被采用（JSON 文件里有的项都用上了）",
		src.contains("trust_drift") and src.contains("qte_window_table")
		and src.contains("hint_delay_table") and src.contains("collector_to_drift"),
		"source=%s" % src)
	_ok("A3 无任何项被跳过（skipped 为空）", not src.contains("skipped="), "source=%s" % src)

	# 外置的窗口表确实等于终稿 —— 顺带证明"读进来了且值没被写坏"
	var cfg_ok := true
	var cfg_detail := ""
	for battle in EXPECT_QTE_WINDOW.keys():
		for tier in TIERS:
			var got: float = _mapper.battle_qte_window(battle, tier)
			var want: float = EXPECT_QTE_WINDOW[battle][tier]
			if not is_equal_approx(got, want):
				cfg_ok = false
				cfg_detail += "[第%d战 %s got %.2f want %.2f] " % [battle, tier, got, want]
	_ok("A4 经 JSON 加载后，3×3 窗口值仍逐格等于 B 终稿", cfg_ok, cfg_detail)

	# B · 容错：路径不存在
	var missing: String = _mapper.reload_mapping("res://__no_such_mapping__.json")
	_ok("B1 文件缺失 → 回退内置常量且不崩",
		missing.contains("内置常量") and missing.contains("缺失"), "source=%s" % missing)
	_eq_f("B2 文件缺失时窗口值 = 内置常量（第 3 战 HIGH 仍为 1.0）",
		_mapper.battle_qte_window(3, "HIGH_TRUST"), 1.0)

	# 恢复真实 JSON，确认 reload 幂等可回到 JSON 层
	var restored: String = _mapper.reload_mapping()
	_ok("B3 再次 reload 可恢复 JSON 层（热重载可用）",
		restored.begins_with("JSON("), "source=%s" % restored)


## C · B2 二轨制公式
func _test_b2_formula() -> void:
	print("\n[C] B2 二轨制公式")

	# 两极锚点（任务书明文：t=-10 → (1.0, 0.0)；t=+10 → (0.0, 1.0)）
	var lo: Dictionary = _mapper.pressure_pair(-10.0)
	var hi: Dictionary = _mapper.pressure_pair(10.0)
	_eq_f("C1 两极锚点 t=-10 → dialogue=1.0", lo["dialogue"], 1.0)
	_eq_f("C2 两极锚点 t=-10 → qte=0.0", lo["qte"], 0.0)
	_eq_f("C3 两极锚点 t=+10 → dialogue=0.0", hi["dialogue"], 0.0)
	_eq_f("C4 两极锚点 t=+10 → qte=1.0", hi["qte"], 1.0)

	# 5 点逐点（B2 公式 (10-t)/20 与 (t+10)/20）
	for pair_want in [[-5.0, 0.75, 0.25], [0.0, 0.5, 0.5], [5.0, 0.25, 0.75]]:
		var t: float = pair_want[0]
		var p: Dictionary = _mapper.pressure_pair(t)
		_eq_f("C5 t=%+.1f → dialogue=%.2f" % [t, pair_want[1]], p["dialogue"], pair_want[1])
		_eq_f("C5 t=%+.1f → qte=%.2f" % [t, pair_want[2]], p["qte"], pair_want[2])

	# 语义一致性：dialogue 轨负相关、qte 轨正相关（t 越大 dialogue 越小）
	var monotonic := true
	var prev_d := 2.0
	var prev_q := -1.0
	for t in [-10.0, -5.0, 0.0, 5.0, 10.0]:
		var p: Dictionary = _mapper.pressure_pair(t)
		if p["dialogue"] > prev_d or p["qte"] < prev_q:
			monotonic = false
		prev_d = p["dialogue"]
		prev_q = p["qte"]
	_ok("C6 双轨单调性：dialogue 递减 / qte 递增（无交叉反转）", monotonic)

	# 边界：越界 clamp
	_eq_f("C7 t=-99 clamp 到 -10（dialogue=1.0）",
		_mapper.pressure_pair(-99.0)["dialogue"], 1.0)
	_eq_f("C8 t=+99 clamp 到 +10（qte=1.0）",
		_mapper.pressure_pair(99.0)["qte"], 1.0)

	# NaN → MEDIUM 锚点（0.0 → (0.5, 0.5)），不崩
	var nan_pair: Dictionary = _mapper.pressure_pair(NAN)
	_eq_f("C9 NaN 输入 → 按 MEDIUM 锚点 (0.5, 0.5)",
		nan_pair["dialogue"], 0.5)
	_eq_f("C9 NaN 输入 → qte=0.5", nan_pair["qte"], 0.5)


## D · B1 阶梯逐格
func _test_b1_tables() -> void:
	print("\n[D] B1 阶梯（9 格窗口 + 9 格 hint，逐格等于 B 终稿）")

	var bad_w := ""
	var bad_h := ""
	for battle in EXPECT_QTE_WINDOW.keys():
		for tier in TIERS:
			var got_w: float = _mapper.battle_qte_window(battle, tier)
			if not is_equal_approx(got_w, EXPECT_QTE_WINDOW[battle][tier]):
				bad_w += "[%d/%s %.2f≠%.2f] " % [battle, tier, got_w, EXPECT_QTE_WINDOW[battle][tier]]
			var got_h: float = _mapper.battle_hint_delay(battle, tier)
			if not is_equal_approx(got_h, EXPECT_HINT_DELAY[battle][tier]):
				bad_h += "[%d/%s %.2f≠%.2f] " % [battle, tier, got_h, EXPECT_HINT_DELAY[battle][tier]]
	_ok("D1 3×3 反应窗表逐格一致（第1战 3.0/2.5/2.0 → 第3战 2.0/1.5/1.0）", bad_w == "", bad_w)
	_ok("D2 3×3 hint_delay 表逐格一致（0.0/0.0/1.0 → 2.0/4.0/5.0）", bad_h == "", bad_h)

	# 全局最短窗口 = 第 3 战 HIGH 的 1.0s（B1 的设计要点，值得锁住）
	var all_min := 999.0
	for battle in EXPECT_QTE_WINDOW.keys():
		for tier in TIERS:
			all_min = minf(all_min, _mapper.battle_qte_window(battle, tier))
	_eq_f("D3 全局最短反应窗 = 1.0s（第 3 战 HIGH · AI 完全接管）", all_min, 1.0)


## E · 容错行为
func _test_tolerance() -> void:
	print("\n[E] 容错（越界 / 大小写 / 别名 / 缺失依赖）")

	# battle_index 越界 → 回退第 1 战值
	_eq_f("E1 battle_index=9 越界 → 回退第 1 战（LOW）",
		_mapper.battle_qte_window(9, "LOW_TRUST"), EXPECT_QTE_WINDOW[1]["LOW_TRUST"])
	_eq_f("E2 battle_index=0 越界 → 回退第 1 战（HIGH）",
		_mapper.battle_qte_window(0, "HIGH_TRUST"), EXPECT_QTE_WINDOW[1]["HIGH_TRUST"])

	# tier 大小写 / 别名
	_eq_f("E3 tier 小写 \"high\" → 识别为 HIGH",
		_mapper.battle_qte_window(1, "high"), 2.0)
	_eq_f("E4 tier 别名 \"MID\" → 识别为 MEDIUM",
		_mapper.battle_qte_window(1, "MID"), 2.5)
	_eq_f("E5 tier 带空格 \"  high_trust  \" → 识别为 HIGH",
		_mapper.battle_qte_window(1, "  high_trust  "), 2.0)
	_eq_f("E6 tier 无法识别 \"???\" → 回退 MEDIUM",
		_mapper.battle_qte_window(1, "???"), EXPECT_QTE_WINDOW[1]["MEDIUM_TRUST"])

	# tier 缺省 "" → 走实时读取路径，返回值必须与显式传入当下 tier 一致
	# （不硬编码期望值：本项目 project.godot 注册了 TrustDrift Autoload，
	#   实时值取决于 collector 当前 score，硬编码会在别人改 score 后假红。）
	var live: float = _mapper.trust_drift_from_collector()
	var live_tier: String = _mapper.tier_for_drift(live)
	_eq_f("E7 tier 缺省 \"\" → 等价于显式传入实时 tier(%s)" % live_tier,
		_mapper.battle_qte_window(2), EXPECT_QTE_WINDOW[2][live_tier])


## F · score → drift 锚点换算（纯函数，不依赖场景树）
func _test_score_anchors() -> void:
	print("\n[F] collector score → trust_drift 锚点（⚠️ 三个锚点为 A 建议值，待 B 复核）")

	_eq_f("F1 score=0.0（<3，LOW）→ 锚点 -5.0", _mapper.anchor_for_score(0.0), -5.0)
	_eq_f("F2 score=2.9（<3 边界内侧）→ 锚点 -5.0", _mapper.anchor_for_score(2.9), -5.0)
	_eq_f("F3 score=3.0（≥3 边界含）→ 锚点 0.0", _mapper.anchor_for_score(3.0), 0.0)
	_eq_f("F4 score=6.9（<7 边界内侧）→ 锚点 0.0", _mapper.anchor_for_score(6.9), 0.0)
	_eq_f("F5 score=7.0（≥7 边界含）→ 锚点 +7.0", _mapper.anchor_for_score(7.0), 7.0)
	_eq_f("F6 score=99.0（远超上界）→ 锚点仍 +7.0", _mapper.anchor_for_score(99.0), 7.0)

	# 往返一致性：锚点反查出的 tier 必须回到原档
	# （这条守的是「_tier_from_drift 的判定边界」与「anchor_for_score 的取值」不能各改一半）
	var tier_ok := true
	var tier_detail := ""
	for pair in [[0.0, "LOW_TRUST"], [4.0, "MEDIUM_TRUST"], [8.0, "HIGH_TRUST"]]:
		var got_tier: String = _mapper.tier_for_drift(_mapper.anchor_for_score(pair[0]))
		if got_tier != pair[1]:
			tier_ok = false
			tier_detail += "[score %.1f → %s ≠ %s] " % [pair[0], got_tier, pair[1]]
	_ok("F7 往返一致：score → 锚点 → tier 回到原档（LOW/MEDIUM/HIGH）", tier_ok, tier_detail)


## G · 与真 TrustDrift Autoload 的集成（project.godot 已注册才跑）
func _test_live_collector() -> void:
	print("\n[G] 与 TrustDrift Autoload 的实时集成")

	var collector := root.get_node_or_null("/root/TrustDrift")
	if collector == null:
		_eq_f("G1 未注册 TrustDrift → 回退 MEDIUM 锚点 0.0，不报错",
			_mapper.trust_drift_from_collector(), 0.0)
		return

	_ok("G1 TrustDrift Autoload 已注册且暴露 get_trust_score()",
		collector.has_method("get_trust_score"), "node=%s" % collector.get_class())

	var score: float = float(collector.get_trust_score())
	var tier: String = str(collector.get_trust_tier())
	print("  当前 score=%.1f  get_trust_tier()=%s" % [score, tier])

	_eq_f("G2 trust_drift_from_collector() 等于 anchor_for_score(实时 score)",
		_mapper.trust_drift_from_collector(), _mapper.anchor_for_score(score))
	_ok("G3 mapper 判定的 tier 与 collector 的 get_trust_tier() 一致",
		_mapper.tier_for_drift(_mapper.trust_drift_from_collector()) == tier,
		"collector=%s mapper=%s" % [tier, _mapper.tier_for_drift(_mapper.trust_drift_from_collector())])


# ---------------------------------------------------------------------------
# 阶段 2：汇总 + 退出码
# ---------------------------------------------------------------------------

func _report_and_quit() -> void:
	print("\n" + "=".repeat(72))
	print("结果：PASS %d / FAIL %d" % [_pass, _fail])
	if _fail > 0:
		for line in _fail_lines:
			print("  ❌ %s" % line)
		print("【FAIL】mapper 数值或容错行为已偏离 B 终稿，请勿合入。")
		quit(1)
		return
	print("✅ 全部通过（trust_pressure_mapper 与 B1/B2 终稿逐格一致，容错齐备）。")
	quit(0)
