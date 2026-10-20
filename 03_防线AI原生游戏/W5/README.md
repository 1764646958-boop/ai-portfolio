# W5 · 成员 A 交付物索引（B 终稿落地：暖色 mask + 参数校准）

> 阶段：W5（9/7-9/13）· 成员 A（主叙事/LLM 架构/Shader/音乐）
> 本批内容：B 于 W4 ② 拍板的 B1-B7 终稿（defenseline_B_docs/pressure_params.md · 9/9 收报）落地——
> B5 局部暖色 mask 新增实现 + 参数校准（blue_retain 0.90 / bpm 160 / shake 0.03 确认）。

---

## 1. 交付物清单

| 任务 | 仓库文件 | 验收状态 |
|---|---|---|
| W5.1 B5 局部暖色 mask | `assets/shaders/battle_post.gdshader`（§E 3 槽 uniform）+ `scripts/battle_post_controller.gd`（flash API） | ✅ 代码就绪；待引擎内视觉调校 |
| W5.2 B 终稿参数校准 | `config/pressure_params.json`（**v2 新建**，controller 优先加载）+ controller `DEFAULT_TABLES`（同步） | ✅ blue_retain 0.90 / shake 0.03 确认 / bpm 160 |
| W5.3 B6 碎片 shake 字段 | `config/qte_params.json`（v0.2：truth_shake 0.01 / fake_shake 0.03） | ⏳ 请 C 复核 |
| W5.4 B4 音频同步 | `scripts/battle_audio.gd`（BPM_TABLE 上限 160） | ✅ |
| W5.5 说明文档 | `W5/shaders/B5暖色mask与参数校准说明.md` | ✅ |

## 2. 给 B 的提示

1. **blue_retain 0.90 语义请复核**：B5「90% 灰度 + 10% 冷蓝偏移」本批按「保留 0.90（微量灰白化 -0.1）」落地（依据 W3 口径注 -0.1~-0.2 取上端）；若本意为「灰化 90%」，只需改 `pressure_params.json` 与 controller 各一处数值。
2. **暖色 mask 调用点**：锚点交互系统触发时调用 `battle_post_controller.flash_warm_mask_from_screen_pos(锚点屏幕坐标)`（自动完成坐标映射）；「最近 3 次交互锚点」由 controller 3 槽 FIFO 维护。
3. B1/B3/B7 口径已在 `pressure_params.json` v2 注释中定稿记录。

## 3. 给 C 的提示

1. **qte_params.json v0.2**：已按 B6 拍板追加 `truth_shake: 0.01` / `fake_shake: 0.03`（mode2_drag）——请复核并维持 owner 口径；碎片拖拽实现（`archaeology_ui.gd`）按此值驱动 truth/fake 碎片的像素级振幅抖动。
2. **battle_post 单 pass**（W4 既定动作，若尚未接入）：全屏 ColorRect 挂 `battle_post.gdshader`，节点加组 `battle_post` 即被 controller 自动吸附。

## 4. W5 待办（尚未完成，明确列出）

- **B2 二轨制映射实现**：`trust_drift_collector`（pressure_level.dialogue 负相关 / .qte 正相关）——B2 规则已定，映射层待写。
- **5.4 验证旧友台词接口**：`validate_player_line` 新引擎（玩家输入旧友台词 → LLM 验证）——W4 既有待办。
- **引擎内最终视觉调校**：blue_retain 0.90 / 暖色 mask 半径与强度 / 四层音频——按试玩反馈推进。
- **BGM 成曲**（#2/#3/#4/#5/过渡曲）与演示视频录制——见 W4/README §4 待人工项。

---

*W5 批次（B 终稿落地）。下一步：引擎内调校 + B2 映射 + W5 其余排期任务。*
