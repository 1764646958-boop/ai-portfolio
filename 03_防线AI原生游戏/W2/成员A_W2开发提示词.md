# 《防线》成员A · W2 开发提示词（可直接粘贴给 Claude Code / Codex）

> 用途：每个提示词对应一个 W2 交付物或修复项。把整个代码块（``` 之间）粘贴给 AI Coding 工具即可。
> 环境：Python 3.11 + openai / python-dotenv / requests（已安装）。LLM 调用统一走 DeepSeek API。
> 建议工作目录：`D:\learn\saishi\chcz\new\New game 1\W1`（提示词 1 会自行复制到 W2/）
> API Key 策略：与 W1 一致——Key 为空时进入 Mock 模式，代码必须能完整自检；填入 Key 后跑真实结果。

---

## 提示词 1：LLM 调度层 v0.1（交付物① · 最核心）

```text
你是《防线》游戏开发团队中成员A（主创/LLM架构师）的编程助手。《防线》是AI原生心理叙事探索游戏。
W2 交付物是「LLM 调度层 v0.1」：在 W1 已验证的双引擎基础上，升级为统一可调度的三引擎层 + 信任偏移累积器 + 全链路 pipeline。
所有 LLM 调用统一用 DeepSeek API（OpenAI 兼容，base_url https://api.deepseek.com，model deepseek-chat，Key 从 .env 读 DEEPSEEK_API_KEY）。

【工作目录与文件组织】
1. 创建目录 `D:\learn\saishi\chcz\new\New game 1\W2\llm\`
2. 从 `W1\llm\` 复制 deepseek_client.py / prompts.py / test_prompts.py / test_connectivity.py 到 W2\llm\（保留 W1 快照不动）
3. 复制 `W1\.env` 到 `W2\.env`

【任务】
1. 升级 `W2/llm/deepseek_client.py`：
   - chat() 增加 timeout=30s 参数；新增带指数退避的重试封装 retry_chat(messages, json_mode, max_retries=2)
2. 扩展 `W2/llm/prompts.py`（保留原有双引擎，新增假记忆引擎）：
   - 新增 FAKE_MEMORY_SYSTEM_TEMPLATE：角色=「假记忆生成引擎」；输入=真实记忆文本 real_memory + 当前信任偏移值 trust_bias（-10~+10）+ 变体类型 variant_type；
     变体类型枚举：negative_twist（负面扭曲：篡改归因角度）/ positive_twist（正面扭曲：过度美化AI）/ subtle_shift（微偏真实：最危险，几乎选对）；
     人设约束：扭曲必须基于真实记忆的语义变体，不凭空编造（幻觉防护-设计层）；
     输出 JSON：{"variant_text": "变体后的记忆文本", "distortion_note": "扭曲点一句话说明"}
   - 新增 FAKE_MEMORY_OUTPUT_SCHEMA 与 build_fake_memory_prompt(real_memory, trust_bias, variant_type)
3. 新建 `W2/llm/engines.py`（核心交付）：
   - 统一引擎调度：ENGINES 注册表（memory_analysis / fake_memory / dialogue 三引擎，各自绑定 build 函数 + schema）
   - run_engine(name, client, **kwargs) -> dict 统一管线：build messages → retry_chat(json_mode=True) → extract_json → validate_schema → 校验失败自动重试（最多2次）→ 仍失败走降级（返回 None 并写日志到 user://logs/engines.log，调用方用预设模板兜底）
   - extract_json 与 validate_schema 从 W1 的 test_prompts.py 移植（保持原逻辑）
4. 新建 `W2/llm/trust_bias.py`（信任偏移累积器）：
   - class TrustBias: start=0.0, 范围 [-10, +10]；update(drift_direction, magnitude, confidence)：ai→正向、human→负向，按 magnitude×confidence 加权累积后 clamp；value 属性只读
5. 新建 `W2/llm/pipeline.py`（MVP 核心 Loop 演示）：
   - core_loop(client, template_text, player_emotion, anchor_id)：记忆分析 → trust_bias.update → 假记忆生成(subtle_shift) → 对话生成 → 返回 dict {analysis, fake, reply, trust_bias}
   - 命令行入口：python pipeline.py --demo（用内置示例跑通并打印全链路结果）
6. 新建 `W2/llm/test_engines.py`（Mock/真实双模式，沿用 W1 风格）：
   - Mock 模式（Key 空）：校验三引擎模板完整、schema 字段齐全、build 函数无残留占位符、pipeline 用模拟响应跑通
   - 真实模式（Key 有）：三引擎各连测 3 次，打印结构合法性与稳定性小结
7. 更新 `W2/llm/test_prompts.py` 的 MEMORY_CASE（集成决策对齐）：
   - anchor_id 从 "anchor_cafe_photo_01" 改为 "CF_CAKE_01"
   - template_text 改为锚点物=栗子蛋糕 的范本：「咖啡店的桌上放着一份栗子蛋糕——去年夏天，旧友迟到了半小时但带了它。你觉得那天的他______」（锚点物是蛋糕，不是照片）

【硬约束】
- 所有 LLM 调用走 DeepSeek（base_url https://api.deepseek.com，model deepseek-chat）
- anchor_id 遵循集成决策的 object_id 规范：大写地点前缀_类型枚举_序号（如 CF_CAKE_01 / CR_SMS_01）；枚举含 PHOTO/DIARY/TICKET/SMS/MUSIC/CAKE/FOOD/ACC/FLOWER/MARK
- 对话引擎输出字段保持 {dialogue_text, warmth, manipulation, helpfulness}（warmth/manipulation/helpfulness 映射 lines[].meta，W3 用，本期只输出）
- 记忆分析引擎输出 {drift_direction, magnitude, confidence}，独立于对话 JSON，直接供 trust_bias 使用
- JSON 输出必须能被 json.loads 解析；Key 为空不能崩溃

【验收标准】
1. Key 为空：python test_engines.py 输出 Mock 自检报告，全部 PASS
2. Key 为空：python pipeline.py --demo 能跑通（Mock 响应）
3. 填入真实 Key 后：python pipeline.py --demo 一次跑通全链路（分析→偏移→假记忆→对话），输出均为合法 JSON
4. 生成 W2/llm/调度层说明.md：三引擎接口、trust_bias API、pipeline 用法、降级策略、给 B 的信任偏移对接说明、给 C 的 dialogue 输出说明
```

---

## 提示词 2：第一幕脚本详细大纲（交付物② · AI 起草 + 人工定稿）

```text
你是《防线》游戏开发团队中成员A（主叙事）的创作助手。《防线》是第一人称心理叙事探索游戏（Demo=第一幕，30分钟以上）。
W2 交付物是「第一幕脚本详细大纲」：在 W1 初稿基础上，把每个节点细化到可直接执行。

【输入文件（先读取）】
1. `D:\learn\saishi\chcz\new\New game 1\W1\第一幕脚本大纲.docx` —— 用 python-docx 提取全文（若未安装则 pip install python-docx）
2. `D:\learn\saishi\chcz\new\New game 1\W1\成员A_W1开发提示词.md` —— 含已确认的三关主题

【任务】在 `D:\learn\saishi\chcz\new\New game 1\W2\script\` 生成「第一幕脚本详细大纲.md」，覆盖 7 个模块，每个节点细化：
- 【需LLM·对话生成引擎】节点：补全 ①触发条件（什么情况下触发）②上下文摘要输入（给 LLM 的关键信息）③期望输出 ④分支逻辑（不同玩家选择走向）
- 【需LLM·记忆分析引擎】节点：补全 锚点ID + 范本 + 情感选项 3 个 + 分析输出用途（更新信任偏移）
- 【需LLM·假记忆生成引擎】节点：补全 真实记忆来源 + 三个变体（负面扭曲/正面扭曲/微偏真实）的扭曲方向
- 【需LLM·战斗对话引擎】节点：补全 阶段话术策略方向（温柔劝说/逻辑论证/情感勒索/示弱 四选策略说明）
- 【固定文案】节点：补全**完整文案正文**（旁白、旧友台词、AI 台词、系统提示），不做摘要式占位

【已确认的集成决策（必须遵守）】
- 咖啡店锚点物 = 栗子蛋糕，object_id = CF_CAKE_01（范本：#1「去年夏天，旧友迟到了半小时但带了栗子蛋糕。你觉得那天的他______」）
- 教室锚点物 = 旧手机草稿箱，object_id = CR_SMS_01（范本：#2「有一条没发出去的消息：『我不是故意不回你的，我只是______』」）
- 记忆考古三关主题不变：4.1 蓝色贝壳手链（某个夜晚，辨识度70%）/ 4.2 紫色玫瑰（冬天路灯下，50%）/ 4.3 针织蓝色花朵（春季，30%）
- AI 自命名触发：累计 ≥15 个锚点交互

【角色设定（严格遵守）】
- 主人公：女性 18-20 岁学生，第一人称，正与旧友疏远、适应 AI 陪伴
- 旧友：男性学生，话多、忠诚、敏感多疑；台词保持「笨拙的热忱」基调；全程无正脸（背影/侧影）
- AI：从不说谎的陪伴者，温柔精准、选择性展示真相（人设三约束：从不正面说谎/温柔服务于目标/不暴露真实意图）

【硬约束】
- 大纲必须覆盖全部 7 个模块；每个对话节点必须有「需LLM/固定文案」标记
- 文案避免 AI 味：不写「在这个快节奏的时代」类空话；对话像真实的人在说话
- 三关辨识度 70%→50%→30% 递进关系在文案中体现（越近的记忆越难辨）

【验收标准】
1. 每个模块的节点数、LLM 标记与 W1 初稿一致（可增不可删）
2. 固定文案节点全部有完整正文（不是「待填」）
3. 能直接作为 B 写虚构记忆范本（25 条）、C 做场景/对话系统的依据
4. 生成 .docx 对外版（可选，用 python-docx）
```

---

## 提示词 3：视野侵蚀 Shader 接入引擎（交付物③ · AI 可执行 + 引擎内验证人工）

```text
你是《防线》游戏开发团队中成员A（主程序/Shader开发）的技术助手。引擎：MagicAI（Godot 4.6.2 AI定制版，gdshader 语法与 Godot 4.x 一致）。

【输入文件（先读取）】
1. `D:\learn\saishi\chcz\new\New game 1\W1\shader\视野侵蚀Shader原型.gdshader` —— 原型（6 个 uniform：erosion_progress/erosion_speed/erosion_opacity/edge_softness/erosion_color/erosion_center）
2. `D:\learn\saishi\chcz\new\New game 1\W1\shader\Shader技术路径研究.md` —— 研究文档（§5.1 有驱动脚本骨架）

【任务】在 `D:\learn\saishi\chcz\new\New game 1\W2\shader\` 生成三件套：
1. `battle_test.gd` —— 战斗测试驱动脚本（挂在战斗场景根节点）：
   - battle_time 计时；阶段一 0-30s：erosion_progress = battle_time/30.0*0.4（30s 占 40% 屏幕）
   - 阶段二 30-60s：tunnel_radius 0.2→0.05（占位，注释说明 W3 接隧道视觉 shader）、erosion_progress 推到 0.9
   - 阶段三 60-90s：留 set_shader_parameter 接口（注释说明 W3 接 LLM 战斗对话）
   - 每阶段切换打印 log
2. `battle_test.tscn` —— Godot 场景文件（文本格式直接编写）：根节点 Node2D + 全屏 ColorRect（anchors 四边 0~1 铺满）+ ShaderMaterial 引用视野侵蚀Shader原型.gdshader
3. `接入说明.md` —— 人工操作清单：①Godot 项目建 res://assets/shaders/ 复制 .gdshader ②新建场景挂脚本 ③ColorRect 全屏铺法（Layout→Full Rect）④运行验证（战斗 ≥30fps / 日常 60fps）⑤PerfDog 压测入口

【附加任务：修正标注】
在 `W1\shader\Shader技术路径研究.md` 的 §3.3 画面抖动小节开头，加一段醒目标注（不改原文）：
「⚠️ 修正标注（W2，2026-08）：选题报告 §7.4 写『画面抖动（顶点位移）』；经 W1 研究确认顶点位移版只能整幅平移且边缘露缝，落地采用 UV 偏移版为主、顶点位移为备选——对外口径以此为准。」

【硬约束】
- shader 参数名必须与原型 uniform 完全一致（erosion_progress 等），不得自创参数名
- GDScript 用 Godot 4 语法（@onready / set_shader_parameter）
- 不修改 W1 原文件（除上述修正标注）

【验收标准】
1. battle_test.gd 参数映射正确、时间轴符合 90 秒三阶段设计
2. battle_test.tscn 能被 Godot 直接打开且节点树完整
3. 接入说明.md 人工照做 10 分钟内能跑起来
```

---

## 提示词 4：dialogue_json_format.md 对齐说明（修复项 · AI 起草 + C 确认）

```text
你是《防线》游戏开发团队中成员A（主创/LLM架构师）的编程助手。《防线》的对话数据格式由集成决策（integration_decisions.docx 附则）约定，需要一份对齐文档供 C（对话UI）与 A（LLM引擎）共同确认。

【背景（已拍板的集成决策）】
- 对话生成引擎输出 JSON：{"dialogue_text": "...", "warmth": 0~1, "manipulation": 0~1, "helpfulness": 0~1}
- 映射约定：dialogue_text → lines[].text；warmth/manipulation/helpfulness → lines[].meta（W3 用）
- 记忆分析引擎输出 {drift_direction, magnitude, confidence} 不进对话 JSON，直接给 B 的信任偏移系统

【任务】在 `D:\learn\saishi\chcz\new\New game 1\W2\docs\` 生成「dialogue_json_format.md」，内容：
1. 对话消息整体结构：lines[] 数组（每条 = 一条发言），含字段说明（text / meta / speaker / timestamp 等，speaker 枚举=ai|old_friend|player|narration）
2. meta 字段结构：{warmth, manipulation, helpfulness}（W3 战斗/压迫系统用，W2 可留空）
3. LLM 引擎对接映射表：LLM 输出字段 → 对话 JSON 字段（逐字段对照）
4. 信任偏移三字段（drift_direction/magnitude/confidence）的独立传递路径说明：不进对话 JSON，由调度层 trust_bias 累积后供 B 使用
5. 示例：一段完整的 AI 对话 JSON 示例（含 meta）
6. 变更记录：v0.1 2026-08-25 起草，待 C 确认

【硬约束】
- 字段名必须与 W1 的 prompts.py 输出 schema 完全一致（dialogue_text/warmth/manipulation/helpfulness）
- 文档定位是「对齐契约」：A 与 C 双方以此为准对接，措辞清晰无歧义

【验收标准】
1. 映射表逐字段覆盖 LLM 全部输出
2. 示例 JSON 可被 json.loads 解析
3. C 拿到即可确认或提出修改点
```

---

## 完全人工执行清单（AI 不参与或仅辅助建议）

| 交付物 | 说明 |
|---|---|
| BGM#1 完整曲目 | W1 动机（W1（loop）.mp3 + .cwp）→ DAW（Cakewalk）完成主界面曲 30-60s，导出 WAV/OGG |
| 脚本详细大纲·情感定稿 | 提示词 2 产出草稿后，**人工润色**（去 AI 味、情感节奏、旧友"笨拙的热忱"手感）——AGENTS.md 铁律 |
| Shader/场景引擎内验证 | 提示词 3 产出文件后，在 MagicAI 里实际跑起来、调参、确认帧率 |
| 与 B/C 接口联调 | 调度层 ↔ 记忆锚点系统 ↔ 对话 UI 的三方对接、拍板分歧 |
| 周日 20:00 集成测试 | MVP 全链路实测（8/29-30） |
