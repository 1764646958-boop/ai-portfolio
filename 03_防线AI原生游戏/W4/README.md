# W4 · 成员 A 交付物索引

> 阶段：W4（8/31-9/6）· 成员 A（主叙事/LLM 架构/Shader/音乐）
> 状态：**5 项完成 + 收尾 README 完成**。待人工项见 §4；W2-W4 最终交付总表见 §7。

---

## 1. 交付物清单

| 任务 | W4 目录 | 仓库新增/更新（defense-line-dev/） | 验收状态 |
|---|---|---|---|
| W4.1 战斗对话/名字生成 LLM 真实版+契约 v2 | `W3\llm\llm_server对接契约.md`（v1→**v2**，契约本件） | `llm_server\prompts.py`（battle/name 模板+build）、`llm_server\engines.py`（post_validate/规则版兜底/Mock 修正） | ✅ 真实 DeepSeek 实测 4 场景全符（策略树/压力公式/名字「阿默」）；Mock 19/19 保持 |
| W4.2 第一幕对话数据 | `W4\dialogues\dialogues_act1.json`、`W4\dialogues\README.md` | — | ✅ 33 段程序校验 PASS（四 mode/三 speaker/引用全解析）；B 的 ENC_01-03 原文整合 |
| W4.3 战斗四层音频 + BGM#4 Brief | `W4\audio\战斗音频实现说明.md`、`W4\audio\BGM4作曲Brief.md` | `assets\shaders\` 无、`scripts\battle_audio.gd`、`assets\audio\sfx_glitch.wav`（W3 待人工#2 闭环） | ✅ 括号配平自查；四层（2 合成+2 资源，缺失静默降级）；Brief 含 stem 导出与验收 |
| W4.4 战斗后处理四合一 | `W4\shaders\四Shader合并与调校说明.md` | `assets\shaders\battle_post.gdshader`、`scripts\battle_post_controller.gd` | ✅ 21 uniform 命名与 W3.4 一致 + enable_* 四开关；90s+30s 曲线驱动；phase→battle_audio 联调 |
| W4.5 PPT 框架 + 演示分镜 | `W4\presentation\PPT框架_17页.md`、`W4\presentation\演示视频分镜.md` | — | ✅ 17 页（技术应用 6 页）；6 场景 OBS 摄制规格与后期要点 |
| W4 收尾 | `W4\README.md`（本文件） | — | ✅ 见 §7 总表 |

> 注：`llm_server\prompts.py / engines.py` 为 W4.1 对 **A 自建 W3.1 文件的迭代**（新增模板/校验，未动 B/C 文件）；仓库其余已有文件零改动。

## 2. 给 B 的提示

1. **Autoload 注册 2 行**（battle 运行时组件，均在仓库新增、开箱即用）：
   ```ini
   battle_audio="*res://scripts/battle_audio.gd"
   battle_post="*res://scripts/battle_post_controller.gd"
   ```
2. **pressure_params.json 同步**：W4.4 controller 优先读 `res://config/pressure_params.json`（不存在则用内置同值表）。B 终稿 B1-B7 后，复制终稿到该路径即完成所有视觉/音频同步（A 侧零改动）。
3. **5.4 选项 B 的 LLM 验证**：玩家输入旧友台词→验证接口未定义。建议复用 `battle_dialogue` 引擎（payload 加 `player_line` 可选段）或由 A 在 W5 落版 `validate_player_line` 新引擎——**W5 待办**。
4. **battle 容器对话**：`ACT1_05_BATTLE_PRESS` 是 LLM 容器（`llm.engine=battle_dialogue`），JSON 文本仅降级占位；战斗前异步预生成，勿阻塞演出。
5. **sfx_glitch.wav 已补交**（W3 待人工 #2 闭环）；`memory_archaeology.gd`/`archaeology_reveal_dialogues.json` 期待路径 `res://assets/audio/sfx_glitch.wav` 现可用。

## 3. 给 C 的提示

1. **battle_post 单 pass 替换**：删 W3.4 四个散装 ColorRect → 1 个全屏 ColorRect 挂 `battle_post.gdshader`，节点加组 `battle_post`（controller 自动吸附，三种绑定方式见 W4\shaders\四Shader合并与调校说明.md §4）。
2. **W4.2 契约扩展键**：`stage`（演出提示，可忽略）/ `llm`（引擎节点，运行时替换）/ `next`（段间自动跳转，可忽略）。speaker 映射（B 的 system/narrator → A 的 player/stage）见 W4\dialogues\README.md §3。
3. **跨文件跳转**：`ACT1_04_ARCH_VERDICT_OK` 的 next 指向 W3.2 文件的 `ARCH_L1_REVEAL`（按关注入 L1/L2/L3），两个 JSON 同注册表即可。
4. **材料引用**：PPT（W4.5）与视频分镜（W4.5）为最终路演材料，录制/讲解由 B/C 分担（分镜后有主讲分配）。

## 4. 待人工处理项

| # | 项 | 说明 | 归属 |
|---|---|---|---|
| 1 | B1-B7 终稿 | 战斗参数终稿（B4 bpm 170 vs 160、B1 窗口、B5 局部暖色、B6/B7）；**定稿后按 §2.2 放 res://config/pressure_params.json 即全链路生效** | B（A 已按默认值编码） |
| 2 | BGM#2/#3/#4 成曲 + `battle_strings.ogg` / `friend_motif.ogg` | Brief 全数就位（W3.5 + W4.3）；作曲待开工 | A/作曲 |
| 3 | 5.4 LLM 验证旧友台词接口 | 未定义（复用 battle_dialogue 或 W5 新引擎） | A+B |
| 4 | Autoload 注册两行 / ColorRect 单 pass 替换 | §2.1/§3.1 接入动作 | B / C |
| 5 | PPT 实测数字 | 帧预算实测 / 最终评测数据由 A 在录制前跑测补页 9/13 | A |
| 6 | 演示视频录制 | 分镜就绪（6 场景 ≈5m20s），OBS 规格见分镜 §0 | A+B |
| 7 | .env 真 Key 本地建 / 环境变量注入 | 契约 §1 已注；Key 不落仓库 | A（本地） |

## 5. 一页流程（此表 = 交付确认）

```
W4.1 契约 v2（battle/name 真实版,策略树+压力公式+post_validate）→ B/C 零改动
W4.2 dialogues_act1.json（33 段;ENC 整合;LLM 9 节点;ARCH 跨文件引用）→ C（DialogManager）
W4.3 battle_audio.gd（四层/合成/静默降级）+ sfx_glitch.wav（补 W3#2）+ BGM4 Brief
W4.4 battle_post.gdshader（单 pass 四合一）+ controller（90s 时间轴/JSON 优先）
W4.5 PPT 17 页（技术应用 6 页,0.501s）+ 演示分镜 6 场景
└→ B：B1-B7 终稿 → res://config/pressure_params.json（一处同步全链路）
```

## 6. W4 自查验收项（A 侧全部执行）

- [x] `dialogues_act1.json` 33 段 JSON 解析、speaker∈{ai,friend,player}、choice/next 引用闭环（跨文件白名单 3 项）
- [x] `battle_post.gdshader` 21 uniform、括号配平、单 pass 管线数学说明（W4\shaders\… §2）
- [x] `battle_audio.gd` / `battle_post_controller.gd` 括号配平、21/17 函数、API 齐全（start/set_phase/set_pressure/trigger_glitch/start/set_shake/resolve/get_uniforms）
- [x] sfx_glitch.wav 0.5s/44.1k/mono/16bit 生成可读（44144 B）
- [x] 仓库零修改 B/C 现有文件（仅新增 A 产物 + W4.1 对 A 自建 llm_server 的迭代）
- [x] W4.1 真实 LLM 验证：guilt 0.85/drift+3 → emotional_leverage（pressure 0.66）；avoid3/drift-5 → show_weakness（0.9）；neutral（0.75）；name→「阿默」

## 7. W2-W4 最终交付总表（跨阶段汇总）

### LLM 服务器链路
| 交付 | 位置 | 状态 |
|---|---|---|
| 五端点 llm_server + 契约（v1→v2） | `defense-line-dev\llm_server\` + `W3\llm\llm_server对接契约.md` | ✅ 自测 19/19；真实 DeepSeek 通；W1 连通实测 **0.501s** |
| 假记忆 V3 生成 + 评测调优 | 引擎 + `llm_server\tools\eval_fake_memory.py` + `W3\llm\假记忆Prompt调优方案.md` | ✅ R1 60% → **R2 33/33**；R3 97/91%（观察级） |

### 脚本 / 对话生产
| 交付 | 位置 | 状态 |
|---|---|---|
| 第一幕脚本详细大纲 v0.2 | `W2\script\` | ✅（W2） |
| 记忆考古三关文案 + reveal JSON | `W3\archaeology\` | ✅ |
| 第一幕对话数据 33 段 | `W4\dialogues\` | ✅ |
| 战斗压迫参数表 v1（md+json） | `W3\battle\` | ✅（B 终稿待确认 B1-B7） |

### 引擎 / 表现（Shader+音频）
| 交付 | 位置 | 状态 |
|---|---|---|
| 三枚视觉压迫 Shader（W3.4） | `assets\shaders\color_grade|screen_shake|tunnel_vision.gdshader` | ✅ |
| 战斗单 pass 合并 + controller（W4.4） | `battle_post.gdshader` + `battle_post_controller.gd` | ✅ |
| 战斗四层音频（W4.3） | `battle_audio.gd` + `sfx_glitch.wav` | ✅ |
| BGM#1 完成曲 | `assets\audio\w1_*.mp3` | ✅（W2） |
| BGM#2/#3 Brief（W3.5）/ BGM#4 Brief（W4.3） | `W3\audio\` / `W4\audio\` | ✅ Brief；成曲待产 |

### 路演材料（W4.5）
| 交付 | 位置 | 状态 |
|---|---|---|
| 17 页 PPT 框架 | `W4\presentation\PPT框架_17页.md` | ✅ |
| 6 场景演示分镜 | `W4\presentation\演示视频分镜.md` | ✅ |

---

*W4 阶段完成。下一步：W5（9/7-9/13）重点 = B 终稿对齐、BGM 成曲、5.4 验证接口、视频录制。*
