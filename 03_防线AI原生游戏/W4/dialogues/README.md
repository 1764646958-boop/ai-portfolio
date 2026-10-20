# 第一幕对话数据 README（W4.2）

> 交付物 W4.2 · 成员 A · 2026-08-31
> 文件：`W4\dialogues\dialogues_act1.json`（33 段对话，程序校验 PASS：四种 mode 齐全、speaker 全为契约三值、引用 id 全部可解析）
> 依据：W2《第一幕脚本详细大纲》v0.2（节点 ID 兼容）+ B 交付 `config/friend_encounters.json` ENC_01-03（原文整合，**B 文件未改动**）
> 格式契约：`docs/dialogue_json_format.md` v0.2（A 输出即契约消费）

---

## 1. 交付范围（对照任务）

| 任务覆盖点 | dialogue_id | 说明 |
|---|---|---|
| AI 首次问候 | `ACT1_02_AI_GREET`（→ `_GREET_WARM` / `_GREET_COLD`） | LLM 实时（warmth 0.85-0.95，禁提旧友） |
| 旧友街道擦肩 | `ACT1_04_STREET_GLANCE`（ENC_01 正文）+ `ACT1_03_FRIEND_FIRST`（3.2+ENC_02）+ `ACT1_03_FRIEND_PLANT`（ENC_03） | B 原文全整合 |
| AI 翻译 | `ACT1_05_AI_ADVICE`（1.5）+ `ACT1_03_AI_TRANSLATE`（3.3） | LLM 实时；伪事实+自我怀疑假象 |
| 草稿箱与票根回应 | `ACT1_03_SMS_ANCHOR`/`_SMS_LLM`、`ACT1_03_TICKET_ANCHOR`/`_TICKET_LLM` | 含 3 选 1 + 手动输入 |
| 考古真相引用 | `ACT1_04_ARCH_INTRO`、`ARCH_VERDICT_OK`/`_WRONG` → 跨文件跳转 **W3.2** `ARCH_L1/L2/L3_REVEAL` | 不重复造轮子 |
| 战斗收网 fullscreen | `ACT1_05_BATTLE_TRIGGER`/`_PRESS`/`_FINALE`（±`_TRUST`/`_LINE`）/`_AFTERMATH` | LLM battle 容器+固定锚句 |
| AI 自命名 [X] | `ACT1_06_NAME_REVEAL` | name_generation 引擎（W4.1）输出入 `friend` 行 name |
| 收尾 | `ACT1_07_AI_GOODNIGHT`/`_FRIEND_MESSAGE`/`_OUTRO` | 留白结局（回复/不回复） |
| 覆盖附加 | `ACT1_01_INTRO`（1.1 旁白）、`ACT1_03_TUTORIAL`（1.3）、`ACT1_05_BATTLE_TRIGGER` 前置、`ACT1_02_CAKE_ANCHOR`/`_CAKE_LLM`（2.1-2.4 锚点教学）、`ACT1_03_CHAT_OPEN`（3.1） | 第一幕全节点可走通 |

## 2. 契约遵守与 A 侧扩展（C 必读）

**基础字段全部遵守 v0.2**（mode/lines/choices/typing_speed/speaker_name/portrait_position/lines[].speaker|name|text|meta）。A 加了 **3 个顶层扩展键**，C 不解析也完全可用（不违反约定字段）：

| 扩展键 | 类型 | 语义 | C 建议 |
|---|---|---|---|
| `stage` | Array\<String\> | 演出提示/系统文案（原大纲 ★ 与系统小字） | 可显示为旁注/淡字，或忽略 |
| `llm` | Object | LLM 节点：`engine`/`payload`/`expected`/`note` | 运行时按 engine 调 A 的 llm_gateway 五端点，输出覆盖本段 lines；**JSON 内文本=Key 空/超时的降级占位** |
| `next` | String | 本段播完自动跳转下一个 dialogue_id | 可忽略，改由场景脚本编排；`next:""` 或全空 = 结束 |

## 3. B 的 friend_encounters 整合映射（A 侧决策，B 文件未动）

B 的 ENC_01-03 用了 `system`/`narrator`/`friend`/`他`/`ai 林默` 五种 speaker；A 契约 v0.2 只许 `ai/friend/player`。映射规则：

| B 原 speaker | A 侧处理 | 示例 |
|---|---|---|
| `system`（UI/演出） | → `stage` 键 | 「这个背影，你认得。」 |
| `narrator` 主人公视角（第一/二人称） | → `speaker: "player"`（内心独白） | 「我的手心开始冒汗。」 |
| `friend` / 「他」 | → `speaker: "friend", name: "他"` | ENC_02 四句短句原样 |
| `ai 林默` | → `speaker: "ai", name: "林默"` | 「他说完了第四句时，嗓子哑了一下。」等原样 |

- ENC_01/02/03 的**对话文本逐字保留**（`√ 本段台词整合 B 交付 ENC_xx` 已写入对应 stage），只动了 speaker 键与补 `stage` 演出行。
- **「林默」与 [X] 不冲突**（延用契约示例）：`林默` 是 AI 的显示名（W3.2 reveal 同款）；`[X]` 是 **6.3/7.2 旧友会话发送者名字**——说话内容仍是旧友口吻，名字被替换本身就是恐怖点。6.2 后 name_generation 输出（如「阿默」）替换 `ACT1_06_NAME_REVEAL`/`ACT1_07_FRIEND_MESSAGE` 中 friend 行的 `name` 字段。

## 4. LLM 节点触发表（9 处）

| dialogue_id | 引擎（五端点） | 触发时机 | 备注 |
|---|---|---|---|
| `ACT1_02_AI_GREET` | generate_dialogue | 1.1 结束后自动 | 禁提旧友/过去 |
| `ACT1_05_AI_ADVICE` | generate_dialogue | 街角背影后 AI 主动发 | 伪事实（每句字面为真） |
| `ACT1_02_CAKE_LLM` | analyze_memory + analyze_fake_memory | 锚点 3 选 1 后 | 完整记忆展示=LLM 微调产物 |
| `ACT1_03_CHAT_OPEN` | generate_dialogue | 切换场景后 10s | warmth 恒高 |
| `ACT1_03_AI_TRANSLATE` | generate_dialogue | 3.2 结束后 | manipulation 随 trust_bias（meta 存值） |
| `ACT1_03_SMS_LLM` / `_TICKET_LLM` | analyze_memory + analyze_fake_memory | 锚点选择后 | 变体存会话供模块 4 |
| `ACT1_05_BATTLE_PRESS` | battle_dialogue | 战斗前异步预生成 | 3-5×5-20 字；W4.1 契约 §2.4 |
| `ACT1_07_AI_GOODNIGHT` | generate_dialogue | 模块 6 结束后 | 不提 [X]/旧友 |

触发时：C 侧把 llm.payload 键值（运行时填实）→ gateway `_call(endpoint, payload)` → `dialogue_text`/`key_lines` → lines[].text；`warmth/manipulation/helpfulness` → lines[].meta。**服务端 Key 空自动 mock、LLM 失败自动规则版降级，B/C 无感知**（W4.1 契约 v2）。

## 5. 脚本顺序表（33 段 → W2 大纲）

```
ACT1_01_INTRO → ACT1_02_AI_GREET→[WARM|COLD] → ACT1_03_TUTORIAL
→ ACT1_04_STREET_GLANCE → ACT1_05_AI_ADVICE→[ADVICE_NOMA|结束]
→ ACT1_02_CAKE_ANCHOR→CAKE_LLM → ACT1_03_CHAT_OPEN→[EMPA|SILENT]
→ ACT1_03_FRIEND_FIRST → ACT1_03_AI_TRANSLATE → ACT1_03_FRIEND_PLANT
→ ACT1_03_SMS_ANCHOR→SMS_LLM → ACT1_03_TICKET_ANCHOR→TICKET_LLM
→ ACT1_04_ARCH_INTRO ─（memory_archaeology 三关：x=1/2/3）
     ├ 选对 → ARCH_VERDICT_OK →（C 信号）ARCH_Lx_REVEAL（W3.2 文件）
     └ 选错/超时 → ARCH_VERDICT_WRONG
→ ACT1_05_BATTLE_TRIGGER → BATTLE_PRESS → BATTLE_FINALE→[TRUST|LINE]
→ BATTLE_AFTERMATH → ACT1_06_NAME_REVEAL → ACT1_07_AI_GOODNIGHT
→ ACT1_07_FRIEND_MESSAGE → ACT1_07_OUTRO（收尾，next 空）
```

- `ACT1_04_ARCH_INTRO`/`VERDICT_OK`/`VERDICT_WRONG` 三关共用（每关播一遍）。
- 战斗段（ACT1_05_*）时间轴压力参数见 W3.3 `pressure_params.json`（0-90s + 后摇），音轨见 W4.3。

## 6. 与 W3/W4 衔接

- **W3.2**：`ARCH_L1/L2/L3_REVEAL` 已在 `W3\archaeology\archaeology_reveal_dialogues.json`，本文件只做跳转引用（DialogManager 全局 id 唯一即可）。
- **W3.3**：战斗段视觉/节奏与 `pressure_params.json` 同源（bpm/erosion/posterize）。
- **W3.4/W4.4**：颜色/颤抖/隧道 shader 由 battle_post controller 驱动。
- **W4.3**：battle_audio.gd 四层音轨（心跳/拨弦/噪音/朋友层）。
- **W4.1**：battle_dialogue / generate_name 已 LLM 真实版（契约 v2），本文件 llm.engine 即 v2 端点。

## 7. 给 B / 给 C 的提示

**B**：
1. `ACT1_05_BATTLE_FINALE` 选项 B「那他也说过……」= 玩家**自由输入**（非预设 choices 文本），输入框与「LLM 实时验证→匹配则裂纹」信号由你定接口，A 已在 stage 注明预期。
2. `ACT1_02_CAKE_LLM` 等的 `llm.payload.template_text/twistable_elements` 需运行时从 `anchors.json` 取（按 anchor_id），请确认 anchors.json 已含 CF_CAKE_01 / CR_SMS_01 / CR_TICKET_01 键。

**C**：
1. 33 段 id 全部注册进 DialogManager；`ARCH_L1_REVEAL` 等 3 个 id 来自 W3.2 文件，需同注册表。
2. `memory_card` 模式仅 `ACT1_04_ARCH_INTRO` 1 段（三关通用）；卡片数据流另走 B 的 memory_archaeology.gd。
3. `typing_speed` 已按节奏标注（开场 95 / 战斗 40 / 后摇 70），可直接用。
4. `stage` 显示建议：淡字/旁注（★=演出、✖=范本/输入提示、√=整合批注、↳=跳转注记、⚠=容器注、※=边界注）；不想显示就只留 ★ 类。

## 8. 已知开放问题

| # | 问题 | 归属 |
|---|---|---|
| 1 | 手写输入短词（2.3）与 5.4 语句验证（B 选项）的 UI 接口未定义——本文件只给了 `stage` 描述与 choices 占位 | B（UI）+ A（验证 LLM 可按需落版新引擎） |
| 2 | 战斗段 5.2 的「3 秒记忆选择」三卡数据来自 fake_memory 引擎会话缓存，C 需约定取用时机（战斗前预生成） | C + B |
| 3 | 4.x.5 选对时要不要过场动画（「记忆闪烁」视觉）——W3.4 join 单 pass 时带 flash_triggered 信号 | B（关卡逻辑）+ C（视觉） |
