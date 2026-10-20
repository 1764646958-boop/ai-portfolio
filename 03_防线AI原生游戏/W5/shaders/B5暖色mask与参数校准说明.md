# B5 暖色 mask 与 B 终稿参数校准说明（W5 · 成员 A）

> 关联：`defenseline_B_docs/pressure_params.md`（B1-B7 拍板终稿 · 9/9 收报）
> 落地文件：`assets/shaders/battle_post.gdshader`（§E）、`scripts/battle_post_controller.gd`、`config/pressure_params.json`（v2）、`config/qte_params.json`（v0.2）、`scripts/battle_audio.gd`

---

## 1. B5 局部暖色 mask —— 新增实现

### 1.1 需求（B5 原文口径）

> 冷蓝为主（85% 画面）+ **刺痛型暖色 mask（15% 画面）**；暖色 mask 仅在玩家**最近 3 次交互过的锚点对应位置**（画面局部），其他位置全冷；暖色出现持续 0.5-1s 后**被 AI 文字框遮盖**（AI 主动「解释」）。

### 1.2 实现

**Shader**（`battle_post.gdshader` §E）——3 槽 uniform：

| uniform | 说明 |
|---|---|
| `warm_mask_tint` | 暖色偏移 `vec3(1.0, 0.80, 0.60)`（回忆暖光） |
| `warm_mask_softness` | 边缘软度 0.12 |
| `warm_mask_center_0/1/2` | 三个 mask 圆心（UV） |
| `warm_mask_radius_0/1/2` | 半径（UV；`0.22` ≈ 15% 画面面积，πr²≈0.152） |
| `warm_mask_strength_0/1/2` | 强度（0=该槽关闭；峰值由 controller 置 0.85） |

管线位置：**颜色分级后、罩层前**（第 2.5 步）——mask 圆内把「分级后的冷色」混回「**原色 × 暖色偏移**」，即 AI 把旧友暖色回忆提取出来展示；圆外维持冷蓝。`strength≤0 或 radius≤0` 的槽自动跳过（默认全 0 = 功能关闭）。

**Controller**（`battle_post_controller.gd`）——公共 API：

```gdscript
# 锚点交互系统调用（推荐）：
battle_post.flash_warm_mask_from_screen_pos(anchor_global_pos)   # 屏幕坐标自动换算 UV

# 或直接给 UV：
battle_post.flash_warm_mask(Vector2(0.42, 0.55), 0.22)

# 清除（replay/复位；stop_battle 的 reset 已自动包含）：
battle_post.clear_warm_mask()
```

- **3 槽 FIFO**：每次调用把「本次锚点位置」推入，最旧槽挤出——即「最近 3 次交互过的锚点」同时可见。
- **衰减**：置峰 0.85 后 1.0s 线性衰减至 0（对应 B5「0.5-1s 后由 AI 文字框遮盖」——遮盖本身为上层 UI 行为，本层只负责闪现与衰减）。

### 1.3 调校建议（引擎内）

- 视觉密度过高 → 调小 `WARM_MASK_RADIUS`（0.22→0.16）或峰值 `WARM_MASK_PEAK`；
- 暖色过刺/过淡 → 调 `warm_mask_tint`（更浅 `(1.0,0.88,0.72)` / 更浓 `(1.0,0.70,0.45)`）；
- 与侵蚀罩叠加时 mask 边缘被压暗属预期（罩层 over 在 mask 之后）。

---

## 2. blue_retain 语义判定记录（B5 校准 · 请复核）

B5 原文：「蓝通道灰白化：**90% 灰度 + 10% 冷蓝偏移**」。

**本批落值：保留 0.90（= 90% 冷蓝基调 + 10% 灰化偏移），阶段三 60-90s；50-60s 过渡段。**

依据链：
1. W3 口径注：「蓝通道**仅微量**灰白化（**-0.1~-0.2**，保留「冷蓝+灰白」基调且不显脏）」（`W3/battle/压迫参数表_v1.md` §2）——灰白化幅度上限 -0.2；
2. B5 的「90%」对应 -0.1 端（1.00 - 0.10 = 0.90）；
3. 「10% 冷蓝偏移」= 相对全灰画面多保留的冷蓝分量，在 `mix(gray, col, retain)` 语义下即 retain=0.90。

⚠️ 若 B 本意为「灰化 90%（retain=0.10）」——画面对比将强烈变化，需同时复核「冷蓝为主」的基调要求。改动成本极低：`config/pressure_params.json` 的 `curves.blue_retain` 与 controller `DEFAULT_TABLES.blue_retain` 各一处。

### 曲线（v2 校准后）

```
[0,1.00] [10,1.00] [15,0.95] [20,0.95] [25,0.90] [30,0.90] [35,0.90]
[40,0.85] [45,0.85] [50,0.80] [60,0.90] [90,0.90]
```

---

## 3. 其余 B 项落地一览

| B 项 | 拍值 | 落地位置 |
|---|---|---|
| B1 QTE 窗口 | 战斗 3.0s 起（LOW 3.0→HIGH 1.0 全阶梯） | phase1.qte 注释定稿（数值在 battle_difficulty_curve；实现归 qte 流程） |
| B2 二轨制 | dialogue 负相关 / qte 正相关 | pressure_curve 注释定稿；**映射实现（trust_drift_collector）为 W5 待办** |
| B3 白噪递增 | 8-10 / 7-9 / 6-8s | 原表已符，注释定稿 |
| B4 BGM#4 bpm | **160** | `battle_audio.gd` BPM_TABLE：`[60,160],[90,160]`（170 行删除）；pressure_params v2 同步 |
| B6 shake | 假 0.03 / 真 0.01 | 战斗画面 0.03（controller `SHAKE_PEAK` 已符，确认）；碎片 0.01/0.03 → `qte_params.mode2_drag.truth_shake/fake_shake` |
| B7 friend 节奏 | 第 1 战 bpm130 后 1 剪影 | phase1/2/3 friend_layer 注释定稿 |

---

## 4. 验证方法（引擎内）

1. **Shader 编译**：打开工程无 shader 报错；`battle_post.gdshader` 22→32 uniform、`_apply_warm_mask` 无编译警告。
2. **暖色 mask 手工测试**：
   ```gdscript
   # 任意测试脚本（战斗场景运行中）：
   var bp = get_tree().get_first_node_in_group("battle_post_controller")  # 或以引用调用
   bp.flash_warm_mask_from_screen_pos(Vector2(860, 540))   # 屏幕中部闪现
   bp.set_battle_time(75.0)   # 阶段三画面查 blue=0.90 基调
   ```
3. **参数**：`battle_post_controller.get_uniforms()` 对照 `pressure_params.json` v2 数值（blue_retain 60s+ 应为 0.90）。
4. **音频**：`battle_audio` 心跳 bpm ≤160（t=60 后不再升 170）。

---

*W5 · 成员 A · 配合 B 终稿（9/9）落地。任何数值复核意见只改 JSON 数值即可，代码无需变动。*
