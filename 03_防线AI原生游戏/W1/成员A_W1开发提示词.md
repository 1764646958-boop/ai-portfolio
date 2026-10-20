# 《防线》成员A · 第一周开发提示词

> 用途：每个提示词对应一个 W1 交付物。把整个代码块（``` 之间）粘贴到 Claude Code 即可。
> 环境：Python 3.11 + openai / python-dotenv / requests（已安装）。所有 LLM 调用统一走 **DeepSeek API**。
>
> ⚠️ **API Key 策略**：开发阶段 API Key **暂为空置**，代码只需能读取 `.env` 并在 Key 为空时进入「Mock 模式」即可；**代码开发完成后，你再统一填入真实 Key 跑真实结果**。

---

## 0. 使用前准备

1. 本目录下创建 `.env` 文件，**Key 先留空**（开发阶段不用填）：

```ini
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

2. 在 `D:\learn\saishi\chcz\new\W1` 目录下开 Claude Code 会话，按 1→2→3→4 顺序执行。

3. 所有提示词都要求代码在 **Key 为空时能正常完成开发与自检（Mock 模式）**，等你代码全部开发完，再统一填入 `DEEPSEEK_API_KEY` 重跑真实结果。

4. 模型名说明：默认 `deepseek-chat`；如 Key 支持 V3.2 / R1 系列，改 `.env` 里 `DEEPSEEK_MODEL` 即可，无需改代码。

---

## 提示词 1：DeepSeek API 连通验证脚本（交付物①）

```text
你是《防线》游戏开发团队中成员A（主创/LLM架构师）的编程助手。《防线》是一款AI原生心理叙事探索游戏。第一周交付物之一是「LLM API 连通验证报告」。本项目的 LLM 引擎统一使用 DeepSeek API（OpenAI 兼容格式），不要使用 Claude API。

【环境】
- 工作目录：D:\learn\saishi\chcz\new\W1
- Python 3.11，已安装 openai、python-dotenv、requests
- API Key 从 .env 读取（变量名 DEEPSEEK_API_KEY），当前为「空置」状态
- DeepSeek 接口：base_url = https://api.deepseek.com ，模型名 deepseek-chat

【任务】在 W1 下创建 llm/ 目录，完成：
1. llm/deepseek_client.py —— 封装 DeepSeek 客户端类，方法：chat(messages, json_mode=False)；从 .env 读取 Key。
2. llm/test_connectivity.py —— 连通测试脚本，依次完成：
   (a) 基础连通测试：一次简单对话
   (b) 结构化 JSON 测试：用 response_format={"type":"json_object"}，让模型输出 {"drift_direction","magnitude","confidence"} 三个字段
   (c) 延迟测试：对同一请求连续测 5 次，统计平均/最小/最大延迟
3. 生成 llm/连通验证报告.md，包含：测试时间、请求/响应样例、延迟数据表格、结论。

【API Key 空置处理（重要）】
- 脚本启动时检测 DEEPSEEK_API_KEY 是否为空。
- 若为空：进入「Mock 模式」——不发起真实网络请求，用固定模拟响应完成 (a)(b)(c) 全部逻辑与报告生成，报告顶部加醒目横幅「【Mock 模式】待填入真实 Key 后重跑」；延迟表格用模拟数据并注明「模拟值」。
- 若不为空：走真实 DeepSeek 调用，报告标注真实测试时间。

【硬约束】
- 所有 LLM 调用必须走 DeepSeek（base_url https://api.deepseek.com，model deepseek-chat）
- API Key 从 .env 读取，禁止硬编码到代码里；Key 为空必须能跑通（Mock 模式），不能直接报错崩溃
- 用 Markdown 表格呈现延迟数据

【验收标准】Key 为空时脚本能完整跑通并生成 Mock 报告；填入 Key 后重跑能得到真实结构化 JSON 与真实延迟表格。
```

---

## 提示词 2：Prompt 原型 v0.1（交付物②）

```text
你是《防线》游戏开发团队中成员A（主创/LLM架构师）的编程助手。第一周交付物之一是「Prompt 原型 v0.1」——包含两个引擎的 Prompt：记忆分析引擎 + 对话生成引擎。所有 LLM 调用统一用 DeepSeek API（OpenAI 兼容，base_url https://api.deepseek.com，model deepseek-chat，Key 从 .env 读 DEEPSEEK_API_KEY，当前为空置）。

【游戏设计背景（必须严格遵守）】
- AI 角色（核心NPC）：一个「从不说谎」的AI陪伴者，温柔、精准、永远"为你好"。性格参数：warmth 恒高(0.85-0.95)、helpfulness 高(0.90-1.00)、manipulation 随信任偏移动态变化。
- 记忆锚点系统：玩家在场景中与物品（照片/日记/票根等）交互，物品自带一段 2-3 句「虚构记忆范本」，玩家补充一个情感词，LLM 在范本基础上微调生成完整记忆，而非从零生成。

【任务】在 W1/llm/ 下创建：
1. llm/prompts.py —— 两个 System Prompt 模板（用 Python 常量/函数组织）：
   - 记忆分析引擎 Prompt：
     * 输入：虚构记忆范本 template_text + 玩家情感补充 player_emotion + 锚点ID
     * 分析四个维度：情感温度 / 归因模式 / 选择性回避 / 自我暴露深度
     * 强制输出结构化 JSON：{"drift_direction":"ai"|"human","magnitude":0-10,"confidence":0-1}
   - 对话生成引擎 Prompt：
     * 输入：对话上下文 + NPC角色设定 + 玩家行为摘要
     * 人设硬约束：从不正面说谎、温柔服务于目标、不暴露真实意图
     * 强制输出结构化 JSON：{"dialogue_text":"...","warmth":0-1,"manipulation":0-1,"helpfulness":0-1}
2. llm/test_prompts.py —— 用「真实游戏场景」的测试用例跑通两个 Prompt，同一输入连测 3 次，验证：结构合法、输出稳定。

【真实测试用例（直接用它，不要用通用用例）】
- 记忆分析用例：template_text="咖啡店墙上的照片：去年夏天，旧友迟到了半小时但带了栗子蛋糕。你觉得那天的他______" ，player_emotion="有点可爱"
- 对话生成用例：context="玩家刚完成一个记忆锚点交互，选择跳过没看旧友的短信" ，npc_character="温柔不说谎的AI" ，player_history_summary="对旧友疏离、易愧疚"

【API Key 空置处理（重要）】
- test_prompts.py 检测 DEEPSEEK_API_KEY 是否为空。
- 若为空：进入「Mock 模式」——不调用真实 API，改为「结构自检」：校验两个 Prompt 模板内容完整、JSON Schema 字段齐全、测试用例已就绪，打印一份 Mock 自检报告（标注「待填入真实 Key 后重跑真实测试」）。
- 若不为空：走真实 DeepSeek 调用，同一输入连测 3 次并打印三次输出对比。

【硬约束】所有调用走 DeepSeek；JSON 输出必须能被 json.loads 解析；Key 为空不能崩溃。

【验收标准】Key 为空时能完成 Prompt 模板 + 测试代码 + 结构自检；填入 Key 后能跑真实 3 次稳定性测试。
```

---

## 提示词 3：第一幕脚本大纲（交付物③）

```text
你是《防线》游戏开发团队中成员A（主叙事）的创作助手。《防线》是一款第一人称心理叙事探索游戏（Demo为第一幕，30分钟以上可玩）。第一周交付物之一是「第一幕脚本大纲」。

【任务】在 W1/script/ 下生成文件「第一幕脚本大纲.md」，覆盖 Demo 全部 7 个模块：
1. 开场+AI登场+场景探索
2. 场景探索+记忆锚点交互
3. 日常对话与信任偏移累积
4. 记忆考古关卡×3
5. 记忆解体重构（完整战斗，90秒三阶段）
6. AI自命名机制揭示
7. 第一幕收尾悬念

每个模块需包含：节点列表、对话概要、分支逻辑，并且每个对话节点都要标注「需LLM」或「固定文案」（即 LLM 调用时机标记）。

【关键角色设定（严格遵守）】
- 主人公：女性，18-20岁学生，第一人称视角，正与旧友疏远、适应AI陪伴
- 旧友：男性学生，话多、忠诚、敏感多疑；台词保持「笨拙的热忱」基调，全程看不到正脸（只有背影/侧影）
- AI：不说谎的陪伴者，温柔精准、选择性展示真相
- 场景：校园/小镇（教室、咖啡店、街道、公寓）

【已确认的记忆考古三关主题（严格遵守，按时间从前往后）】
模块4「记忆考古关卡×3」的三关记忆主题与真记忆范本已确定，起草大纲、B 成员写范本时直接采用，不要再另起主题：
- 4.1 蓝色贝壳的手链（某个夜晚，辨识度70%）：旧友在之前的某一天突然问我喜欢什么颜色，我回答蓝色。之后的一天，旧友十分高兴的分享着自己的收获，顺势告诉我为我买了一个礼物，我很期待——那天晚上，他将礼物送给了我。是一个带着蓝色贝壳的手链，他亲手把手链戴到我的手上，面色带着微红与掩饰不住的笑意，我也十分开心，说，我会珍惜这个礼物的。
- 4.2 紫色的玫瑰（冬天的路灯下，辨识度50%）：那天我们从自习室学习后出来，他说要给我一个从没人送过的礼物，他带着我绕了一圈，之后快步跑去拿东西，回来之后，他让我转身，拿出了一捧紫色玫瑰，我转头之后，震惊极了，他的笑容与言语，让那天黄晕的灯光更加温和。
- 4.3 针织的蓝色花朵（春季，辨识度30%）：春天的那一天，是一个周日，也是妇女节。我因为论文的忙碌不能和旧友一块出去玩。旧友一直在感慨外面玩的人很多，而且每个女孩子都能免费拿一枝花。那天，他为我买了一支花，针织的蓝色花朵，但是，直到我们彻底分开之后，我才知道这件事。

【硬约束】大纲必须覆盖全部7个模块；每个模块都要有明确的「需LLM/固定文案」标记。

【验收标准】大纲能直接作为 B 成员写「虚构记忆范本」和 C 成员做场景/对话系统的依据。
```

---

## 提示词 4：Shader 技术路径研究 + 视野侵蚀原型（交付物⑤）

```text
你是《防线》游戏开发团队中成员A（主程序/Shader开发）的技术助手。第一周交付物之一是「Shader 技术路径初步研究」，为第三周开发四项视觉压迫Shader（视野侵蚀/色调分离/画面抖动/隧道视觉）打基础。引擎方向为 Godot 4.x（MagicAI 是 Godot 4.6.2 AI定制版，语法一致）。

【任务】在 W1/shader/ 下完成：
1. shader/Shader技术路径研究.md，内容包含：
   - Godot 4 的 Shader 语言（gdshader）基础语法
   - CanvasItem shader vs Spatial shader 的选择，以及如何做全屏后处理效果（视野侵蚀是后处理类）
   - 视野侵蚀/色调分离/画面抖动/隧道视觉 四项 Shader 各自的实现思路
   - 性能注意点（如何保证战斗场景 30fps 以上）
2. shader/视野侵蚀Shader原型.gdshader —— 一个动态遮罩 Shader，参数可配置：侵蚀速度、透明度、边缘柔化。

【硬约束】Shader 用 Godot 4 的 gdshader 语法；原型里参数必须可配置；研究文档要具体到「怎么落地」而不是泛泛而谈。

【验收标准】原型 Shader 能直接贴进 Godot 材质使用；研究文档覆盖四项 Shader 的实现路径。
```

---

## 附：W1 交付物与提示词对应关系

| 交付物 | 类型 | 提示词 | 能否用 Claude Code | Key 依赖 |
|---|---|---|---|---|
| ① LLM API 连通验证报告 | 技术 | 1 | ✅ 全自动 | 空置走 Mock |
| ② Prompt 原型 v0.1 | 技术+创作 | 2 | ✅ 为主，需你验收 | 空置走 Mock |
| ③ 第一幕脚本大纲 | 叙事 | 3 | 🟡 起草+你定稿 | 无需 |
| ④ BGM#1 动机草图 | 音乐 | —（手动，DAW） | ❌ 手动 | 无需 |
| ⑤ Shader 技术路径研究 | 技术 | 4 | ✅ 全自动 | 无需 |
| ⑥ 接收B范本10条→校准大纲 | 协作 | —（等B） | 🔗 依赖B | 无需 |

> 开发完成后统一填入 Key 的操作：编辑 `.env`，把 `DEEPSEEK_API_KEY=` 后面填上真实 Key，然后重跑提示词 1、2 的测试脚本即可拿到真实结果。
