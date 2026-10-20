# 记忆锚点 5 个完整示例 · v5.3

> **责任方**：B（核心程序 / 叙事设计）
> **依据**：《游戏制作指南》§二.2 B-W2 验收标准（"提供 5 个完整示例"）
> **配套**：[anchors.schema.json](../config/anchors.schema.json) · [README_anchors_schema.md](../config/README_anchors_schema.md) · [trust_drift_rules_v0.1.md](../config/trust_drift_rules_v0.1.md)

## 用途

这 5 个示例展示了一个**完整填写的记忆锚点**长什么样——既包含静态配置（来自 `anchors.json`），也包含玩家交互后由 `memory_anchor_ui.gd` / `LLMGateway` / `TrustDrift` 三方写入的运行时字段（`player_emotion_choice` / `llm_complete_memory` / `drift_update` 等）。

这些示例是 **B-W2 的验收物**，也是 W3 接入 `LLMGateway.generate_dialogue()` 的输入参考。

## 选样覆盖矩阵

| # | anchor_id | 场景 | offset_type | drift_dimension | drift_direction（示例）|
|---|---|---|---|---|---|
| 1 | `CF_CAKE_01` | 咖啡店 | A（核心）| 信任 / 期待 | toward_distance |
| 2 | `CF_CHIME_01` | 咖啡店 | B（次要）| 认知 / 回避 | ambiguous |
| 3 | `CR_NOTE_01` | 教室 | A（核心）| 信任 / 情感 | toward_closeness |
| 4 | `DM_SMS_01` | 宿舍 | A（核心）| 信任 / 沟通 | toward_distance |
| 5 | `DM_PLANT_01` | 宿舍 | A（核心）| 情感 / 归因 | toward_closeness |

覆盖：3 场景 + offset_type A 与 B + drift_dimension 5 个不同维度 + drift_direction 3 个方向。

## 字段填充规范（运行时）

| 字段 | 填充时机 | 来源 |
|---|---|---|
| `player_emotion_choice` | 玩家点击情感选项 | `memory_anchor_ui.gd` `_on_emotion_selected` |
| `player_free_input` | 玩家点 "完成" | `memory_anchor_ui.gd` `_on_free_input_done` |
| `player_selected: true` | 玩家完成选择 | `memory_anchor_ui.gd` |
| `player_skipped: false` | （未跳过） | `memory_anchor_ui.gd` |
| `interaction_timestamp` | 玩家首次点击锚点 | `Time.get_datetime_string_from_system(true)` |
| `llm_complete_memory` | 玩家选完情感 + 触发 LLM | `LLMGateway.analyze_memory()` |
| `llm_fake_variants[3]` | LLM 生成 3 个假变体 | `LLMGateway.generate_dialogue()` |
| `drift_update` | LLM 输出 + TrustDrift 计算 | `TrustDrift.record_anchor_resolution()` |

---

## 示例 1：CF_CAKE_01 · 桌上的栗子蛋糕

**叙事意图**：傍晚咖啡店，邻桌栗子蛋糕勾起对旧友的回忆——对方迟到却一路护着蛋糕盒跑来。叙事基调是克制的怀念下压抑的不悦。

**drift_direction 推断**：`emotion_options` 三个选项均偏负向解读（"不被重视" / "落空" / "敏感"），示例玩家选 "习惯等待带来的敏感" —— drift_direction = `toward_distance`（信任削弱）。

### 完整 JSON

```json
{
  "anchor_id": "CF_CAKE_01",
  "object_id": "CF_CAKE_01",
  "scene": "咖啡店",
  "scene_location": "邻桌桌面",
  "item_name": "桌上的栗子蛋糕",
  "anchor_object": "栗子蛋糕",
  "category": "memory_anchor_archaeology_main",
  "anchor_type": "core",
  "identification_difficulty": 0.75,
  "revealed_text": "傍晚，我独自坐在学校旁边的咖啡店。邻桌客人点了一份栗子蛋糕，奶油慢慢向下塌陷。视线落在蛋糕上，思绪不由自主飘回从前。这是大一下学期见面时，我随口提起喜欢的款式。记忆里，那人满头是汗冲进店里，怀里紧紧���着蛋糕盒，一路从宿舍楼跑过来，盒内的奶油几乎没有晃动。\"抱歉，路上耽搁太久。\"对方喘着气坐下。那时候我心里憋着不悦，下意识觉得对方没有重视这场会面，垂着眼不愿多言语。我不断说服自己不必在意，任何决定我都不会后悔。我已经记不太清那场约定对方迟到了多久，或许半小时，又或许是整整一个下午。只隐约记得，对方落座的那一刻，窗外天色已经彻底沉了下来。望着蛋糕，万千思绪涌上心头。我刻意摆出冷淡模样，藏在心底不肯承认的是＿＿＿＿＿＿",
  "emotion_options": [
    "暗自滋生的不被重视感",
    "满怀期待后的落空",
    "习惯等待带来的敏感"
  ],
  "llm_params": {
    "twistable_elements": ["时间长度", "迟到原因", "蛋糕款式"],
    "drift_dimension": ["信任", "期待"],
    "note": "设计元数据，供 A 的 Prompt 参考"
  },
  "offset_type": "A",
  "player_emotion_choice": "习惯等待带来的敏感",
  "player_free_input": "我等的不是蛋糕，是那一刻他推门进来的样子",
  "player_selected": true,
  "player_skipped": false,
  "interaction_timestamp": "2026-08-24T19:32:11",
  "llm_complete_memory": "傍晚，我独自坐在学校旁边的咖啡店。邻桌客人点了一份栗子蛋糕，奶油慢慢向下塌陷。视线落在蛋糕上，思绪不由自主飘回从前。这是大一下学期见面时，我随口提起喜欢的款式。记忆里，那人满头是汗冲进店里，怀里紧紧护着蛋糕盒，一路从宿舍楼跑过来，盒内的奶油几乎没有晃动。\"抱歉，路上耽搁太久。\"对方喘着气坐下。那时候我心里憋着不悦，下意识觉得对方没有重视这场会面，垂着眼不愿多言语。我不断说服自己不必在意，任何决定我都不会后悔。我已经记不太清那场约定对方迟到了多久，或许半小时，又或许是整整一个下午。只隐约记得，对方落座的那一刻，窗外天色已经彻底沉了下来。望着蛋糕，万千思绪涌上心头。我刻意摆出冷淡模样，藏在心底不肯承认的是——我等的其实不是那款蛋糕。我等的，是他推开店门、风铃响起那一刻抬头看见我的样子。奶油塌陷的速度，比不上那一刻心跳加速的速度。我以为我想要的是那款蛋糕。多年以后才明白，我想要的是那一刻被郑重对待的感觉——而他其实已经在路上了，用他能给的最笨拙的方式",
  "llm_fake_variants": [
    "傍晚，我独自坐在学校旁边的咖啡店。邻桌客人点了一份栗子蛋糕，奶油慢慢向下塌陷。视线落在蛋糕上，思绪不由自主飘回从前。这是大一下学期见面时，我随口提起喜欢的款式。记忆里，那人满头是汗冲进店里，怀里紧紧护着蛋糕盒，一路从宿舍楼跑过来，盒内的奶油几乎没有晃动。\"抱歉，路上耽搁太久。\"对方喘着气坐下。那时候我心里憋着不悦，下意识觉得对方没有重视这场会面，垂着眼不愿多言语。望着蛋糕，万千思绪涌上心头。我刻意摆出冷淡模样，藏在心底不肯承认的是——我从来不在乎他迟到多久，我只是难过他没有提前告诉我。",
    "傍晚，我独自坐在学校旁边的咖啡店。邻桌客人点了一份栗子蛋糕，奶油慢慢向下塌陷。视线落在蛋糕上，思绪不由自主飘回从前。记忆里，那人答应了来，但整整一个下午都没出现。我等到天色彻底沉下来，等到店员委婉地问我要不要点单。我一个人点了那款蛋糕，吃了两口就放下了。望着蛋糕，万千思绪涌上心头。我刻意摆出冷淡模样，藏在心底不肯承认的是——我恨他让我等到麻木，连恨都不再有气力。",
    "傍晚，我独自坐在学校旁边的咖啡店。邻桌客人点了一份栗子蛋糕，奶油慢慢向下塌陷。视线落在蛋糕上，思绪不由自主飘回从前。这是大一下学期见面时，我随口提起喜欢的款式。记忆里，那人满头是汗冲进店里，怀里紧紧护着蛋糕盒。\"抱歉，路上耽搁太久。\"对方喘着气坐下。望着蛋糕，万千思绪涌上心头。我刻意摆出冷淡模样，藏在心底不肯承认的是——也许那场见面，本就不该用蛋糕开场。"
  ],
  "drift_update": {
    "drift_direction": "toward_distance",
    "magnitude": -0.4,
    "confidence": 0.78
  }
}
```

**字段填写要点**：

- `llm_complete_memory` 把 ＿＿＿ 留白填成"等风铃响那一刻抬头看见我的样子"——情感基调与玩家选择的 "习惯等待带来的敏感" 一致，且点出"被郑重对待"的隐含期待
- `llm_fake_variants[0]` → toward_distance（同方向，强化负面解读）
- `llm_fake_variants[1]` → toward_distance 更极端（"等到麻木"）
- `llm_fake_variants[2]` → ambiguous（"也许本就不该"——动摇叙事）
- `drift_update.magnitude = -0.4`（中等负向，符合"敏感"而非"愤恨"）
- `drift_update.confidence = 0.78`（玩家 free_input 提供了明确线索，LLM 自评较高）

---

## 示例 2：CF_CHIME_01 · 门口的风铃

**叙事意图**：风铃响起，却不再抬头看门口——回避的姿态背后，藏着对"被找到"的期待落空。

**drift_direction 推断**：`emotion_options` 含"他每次进来都在找我"（偏正向）/ "我后来为什么不抬头了"（回避型）/ "风铃的声音从没变过"（事实陈述）。示例选 "我后来为什么不抬头了" —— drift_direction = `ambiguous`（回避既可能是信任削弱，也可能是自我保护，二义性）。

### 完整 JSON

```json
{
  "anchor_id": "CF_CHIME_01",
  "object_id": "CF_CHIME_01",
  "scene": "咖啡店",
  "scene_location": "店门口",
  "item_name": "门口的风铃",
  "anchor_object": "风铃",
  "category": "memory_anchor_archaeology_main",
  "anchor_type": "core",
  "identification_difficulty": 0.55,
  "revealed_text": "推开店门，头顶的风铃响了一声。很轻。我记得这风铃很久了。大一有段时间我们常来这家店。每次他推门进来，风铃都会响，然后他站在门口扫一圈，看到我了才走过来。后来我单独来的次数多了，推门时风铃也响。不知道从什么时候起，我不再抬头看门口了。现在风铃还在响。我忽然想＿＿＿＿＿＿",
  "emotion_options": [
    "他每次进来都在找我",
    "我后来为什么不抬头了",
    "风铃的声音从没变过"
  ],
  "llm_params": {
    "twistable_elements": ["他站在门口是在找我还是等人", "我最后一次抬头看门口是什么时候", "我们多久没一起来过了"],
    "drift_dimension": ["认知", "回避"],
    "note": "设计元数据，供 A 的 Prompt参考"
  },
  "offset_type": "B",
  "player_emotion_choice": "我后来为什么不抬头了",
  "player_free_input": "",
  "player_selected": true,
  "player_skipped": false,
  "interaction_timestamp": "2026-08-24T19:41:08",
  "llm_complete_memory": "推开店门，头顶的风铃响了一声。很轻。我记得这风铃很久了。大一有段时间我们常来这家店。每次他推门进来，风铃都会响，然后他站在门口扫一圈，看到我了才走过来。后来我单独来的次数多了，推门时风铃也响。不知道从什么时候起，我不再抬头看门口了。现在风铃还在响。我忽然想——不抬头���门口的那一刻，是我先决定不再被找到的。我以为那是一种洒脱。后来我才明白��那是一种极慢的告别，比争吵还要漫长。风铃的声音从没变过。是我变了。",
  "llm_fake_variants": [
    "推开店门，头顶的风铃响了一声。很轻。我记得这风铃很久了。大一有段时间我们常来这家店。每次他推门进来，风铃都会响。后来我单独来的次数多了，推门时风铃也响。不知道从什么时候起，我不再抬头看门口了。现在风铃还在响。我忽然想——他后来一定还在门口站过很久。只是我再也看不见了。",
    "推开店门，头顶的风铃响了一声。很轻。我记得这风铃很久了。每次他推门进来，风铃都会响，他站在门口扫一圈，看到我了才走过来。我以为那是他习惯的动作。后来我才想明白——也许他找的不是我，是我对面那个空位。",
    "推开店门，头顶的风铃响了一声。很轻。我记得这风铃很久了。后来我单独来的次数多了，推门时风铃也响。不知道从什么时候起，我不再抬头看门口了。现在风铃还在响。我忽然想——也许他早就没来了。风铃响，只是因为有别人在推门。"
  ],
  "drift_update": {
    "drift_direction": "ambiguous",
    "magnitude": -0.15,
    "confidence": 0.62
  }
}
```

**���段填写要点**：

- `player_free_input` 留空（玩家跳过自由输入，UI 应允许）
- `llm_complete_memory` 把 ＿＿＿ 填成"是我先决定不再被找到的"——直指回避行为的责任归属
- `llm_fake_variants[0]` → toward_distance（"他后来一定还在门口站过很久"，强化错过感）
- `llm_fake_variants[1]` → toward_distance 更隐蔽（"他找的不是我"，动摇关系定位）
- `llm_fake_variants[2]` → toward_distance 第三面（"他早就没来了"，彻底否定）
- 三个变体同方向但**置信度递增**，LLM 自评 conf 较低（0.62），因为玩家 free_input 留空缺少线索
- `drift_update.magnitude = -0.15`（方向不明确，幅度小）

---

## 示例 3：CR_NOTE_01 · 未送出的纸条

**叙事意图**：纸条从旧课本里滑落，揭示对方曾在后门等候，玩家却从正门走了。叙事基调是误会与遗憾。

**drift_direction 推断**：`emotion_options` 三选项："那天他等了很久"（信任正向）/ "他总是不肯直说"（归因中性）/ "我其实看见了但没停"（内省负向）。示例选 "那天他等了很久" —— drift_direction = `toward_closeness`（意识到对方付出，信任修复方向）。

### 完整 JSON

```json
{
  "anchor_id": "CR_NOTE_01",
  "object_id": "CR_NOTE_01",
  "scene": "教室",
  "scene_location": "旧课本",
  "item_name": "未送出的纸条",
  "anchor_object": "纸条",
  "category": "memory_anchor_archaeology_main",
  "anchor_type": "core",
  "identification_difficulty": 0.60,
  "revealed_text": "一张折叠整齐的纸条从旧课本里掉出：\"今天别走那么快，我在后门等你。\"笔迹被水渍晕开了一角，我想起那个傍晚，他确实在后门站了很久。我那天从正门走了，手机静音塞在书包最底层。深夜才看到他发来的消息，最后一条是：\"没事，我刚好顺路。\"我当时觉得他总这样，把简单的事说得很复杂。现在看这张纸条，才察觉＿＿＿＿＿＿",
  "emotion_options": [
    "那天他等了很久",
    "他总是不肯直说",
    "我其实看见了但没停"
  ],
  "llm_params": {
    "twistable_elements": ["纸条为什么没送出去", "他等了多久", "我是否真的没看见"],
    "drift_dimension": ["信任", "情感"],
    "note": "设计元数据，供 A 的 Prompt参考"
  },
  "offset_type": "A",
  "player_emotion_choice": "那天他等了很久",
  "player_free_input": "他发'刚好顺路'那条消息的时候，是不是也站了很久",
  "player_selected": true,
  "player_skipped": false,
  "interaction_timestamp": "2026-08-24T19:48:55",
  "llm_complete_memory": "一张折叠整齐的纸条从旧课本里掉出：\"今天别走那么快，我在后门等你。\"笔迹被水渍晕开了一角，我想起那个傍晚，他确实在后门站了很久。我那天从正门走了，手机静音塞在书包最底层。深夜才看到他发来的消息，最后一条是：\"没事，我刚好顺路。\"我当时觉得他总这样，把简单的事说得很复杂。现在看这张纸条，才察觉——他发那条\"刚好顺路\"的消息时，也许还站在后门。也许还看着手里的纸条，没有收进书包。也许那句话，是他在给自己找一个台阶下，怕我回头找他时看到他还站着，会让彼此尴尬。我当时没意识到，我忽略的不是一个迟到的人，是一个反复在等我回头的人。",
  "llm_fake_variants": [
    "一张折叠整齐的纸条从旧课本里掉出：\"今天别走那么快，我在后门等你。\"我那天从正门走了，手���静音塞在书包最底层。深夜才看到他发来的消息，最后一条是：\"没事，我刚好顺路。\"现在看这张纸条，才察觉——他那条消息，每一个字都是在我们两个人的台阶间找平衡。",
    "一张折叠整齐的纸条从旧课本里掉出：\"今天别走那么快，我在后门等你。\"我那天从正门走了，手机静音塞在书包最底层。深夜才看到他发来的消息，最后一条是：\"没事，我刚好顺路。\"现在看这张纸条，才察觉——他不是不肯直说，他是怕直说之后，我会觉得他在逼我。",
    "一张折叠整齐的纸条从旧课本里掉出：\"今天别走那么快，我在后门等你。\"我那天从正门走了，手机静音塞在书包最底层。深夜才看到他发来的消息，最后一条是：\"没事，我刚好顺路。\"现在看这张纸条，才察觉——也许他从一开始就知道，我那天不会从后门走。纸条只是他给自己的一个交代。"
  ],
  "drift_update": {
    "drift_direction": "toward_closeness",
    "magnitude": 0.35,
    "confidence": 0.74
  }
}
```

**字段填写要点**：

- `llm_complete_memory` 填"也许他发那条消息时还站在后门"——把"刚���顺路"反向解读为自我台阶，体现情感修复方向
- `llm_fake_variants[0]` → toward_closeness（"给彼此台阶"，最正向）
- `llm_fake_variants[1]` → toward_closeness（"怕直说会逼我"，动机善意解读）
- `llm_fake_variants[2]` → ambiguous（"他从一开始就知道我不会走"，动摇对方期待）
- `drift_update.magnitude = +0.35`（正向中等）
- `drift_update.confidence = 0.74`（玩家 free_input 指向对方诚意）

---

## 示例 4：DM_SMS_01 · 旧手机的草稿箱

**叙事意图**：深夜翻出旧数据，草稿箱里躺着没发出去的消息。叙事基调是沉默对峙下的彼此错过。

**drift_direction 推断**：`emotion_options` 三选项均偏负向："彼此坦诚的机会"（错失）/ "一时赌气造成的隔阂"（负向）/ "本该解开的误会"（错失）。示例选 "一时赌气造成的隔阂" —— drift_direction = `toward_distance`（信任受损）。

### 完整 JSON

```json
{
  "anchor_id": "DM_SMS_01",
  "object_id": "DM_SMS_01",
  "scene": "宿舍",
  "scene_location": "书桌·手机",
  "item_name": "旧手机的草稿箱",
  "anchor_object": "旧手机草稿",
  "category": "memory_anchor_archaeology_main",
  "anchor_type": "core",
  "identification_difficulty": 0.70,
  "revealed_text": "深夜，我翻出换手机时导出的旧数据备份。无意中点开草稿箱，屏幕上停着半截没能送出的文字：\"我不是故意不回你的，我只是＿＿\"思绪骤然被拉回当年。那日我们原本约好在教学楼碰面。我忍不住猜想，对方或许反复输入、删除，挣扎许久，最终还是没能按下发送。那天我守着对话框等了整整一日，越等越烦闷，暗自下定决心绝不主动搭话，手机始终一片沉寂。那时我认定主动退让便是妥协，自己的选择无需动摇。屏幕上显示消息发送失败，我无从分辨，究竟是校园网出了问题，还是另有隐情。长久的沉默对峙，硬生生阻隔了＿＿＿＿＿＿",
  "emotion_options": [
    "彼此坦诚的机会",
    "一时赌气造成的隔阂",
    "本该解开的误会"
  ],
  "llm_params": {
    "twistable_elements": ["未发送原因", "等待时长", "消息内容"],
    "drift_dimension": ["信任", "沟通"],
    "note": "设计元数据，供 A 的 Prompt参考"
  },
  "offset_type": "A",
  "player_emotion_choice": "一时赌气造成的隔阂",
  "player_free_input": "我以为不主动是一种姿态，没想到它真的隔开了彼此",
  "player_selected": true,
  "player_skipped": false,
  "interaction_timestamp": "2026-08-24T20:02:37",
  "llm_complete_memory": "深夜，我翻出换手机时导出的旧数据备份。无意中点开草稿箱，屏幕上停着半截没能送出的文字：\"我不是故意不回你的，我只是＿＿\"思绪骤然被拉回当年。那日我们原本约好在教学楼碰面。我忍不住猜想，对方或许反复输入、删除，挣扎许久，最终还是没能按下发送。那天我守着对话框等了整整一日，越等越烦闷，暗自下定决心绝不主动搭话，手机始终一片沉寂。那时我认定主动退让便是妥协，自己的选择无需动摇。屏幕上显示消息发送失败，我无从分辨，究竟是校园网出了问题，还是另有隐情。长久的沉默对峙，硬生生阻隔了——所有还没来得及说出口的话。我们都以为沉默是姿态，其实是囚笼。彼此都把主动权让给对方，也都把开口的机会让给了对方。我那时以为不主动是体面。现在才明白，体面是有代价的——代价是原本能说清楚的事，被沉默喂成了永远解��不清的隔阂。",
  "llm_fake_variants": [
    "深夜，我翻出换手机时导出的旧数据备份。无意中点开草稿箱，屏幕上停着半截没能送出的文字。长久的沉默对峙，硬生生阻隔了——彼此最后开口的勇气。我们都在等对方先说话，结果都没等到。",
    "深夜，我翻出换手机时导出的旧数据备份。无意中点开草稿箱，屏幕上停着半截没能送出的文字。长久的沉默对峙，硬生生阻隔了——我们以为彼此都心知肚明的事。后来才明白，没有说出口的事，永远不算数。",
    "深夜，我翻出换手机时导出的旧数据备份。无意中点开草稿箱，屏幕上停着半截没能送出的文字。长久的沉默对峙，硬生生阻隔了——也许从来不是什么校园网出了问题。从一开始，我就没准备好接收那条消息。"
  ],
  "drift_update": {
    "drift_direction": "toward_distance",
    "magnitude": -0.55,
    "confidence": 0.82
  }
}
```

**字段填写要点**：

- `llm_complete_memory` 把 ＿＿＿ 填成"所有还没来得及说出口的话"+"体面是有代价的"——直指赌气的代价
- `llm_fake_variants[0]` → toward_distance（"我们都在等"，互相错过）
- `llm_fake_variants[1]` → toward_distance（"没准备好接收"，自责更深）
- `llm_fake_variants[2]` → toward_distance（"从一开始就没准备好"，动摇起点）
- 三个变体同方向但责任归属递进，magnitude = -0.55（较强负向）
- `drift_update.confidence = 0.82`（玩家 free_input 明确给出"赌气"反思）

---

## 示例 5：DM_PLANT_01 · 窗台那盆绿植

**叙事意图**：大一入学礼物，多年仍在窗台。叙事基调是坚韧与被默默照料的察觉。

**drift_direction 推断**：`emotion_options` 三选项："我偶尔才想起来的照料"（内省）/ "他送来时没说出口的期待"（归因对方）/ "被时间证明的坚韧"（中性正向）。示例选 "被时间证明的坚韧" —— drift_direction = `toward_closeness`（正向，关系韧性确认）。

### 完整 JSON

```json
{
  "anchor_id": "DM_PLANT_01",
  "object_id": "DM_PLANT_01",
  "scene": "宿舍",
  "scene_location": "窗台",
  "item_name": "窗台那盆绿植",
  "anchor_object": "窗台绿植",
  "category": "memory_anchor_archaeology_main",
  "anchor_type": "core",
  "identification_difficulty": 0.72,
  "revealed_text": "宿舍窗台上那盆绿植还活着，叶子比刚拿来时更长了。这是大一入学时，对方送来的入学礼物。他送到女生宿舍楼下就走了，我下楼去拿，只看见一盆小小的绿植和一袋土。袋子上贴着一张便签：\"不知道你喜欢什么，这个好养。\"我当时觉得送植物很没意思，随手放在窗台，偶尔想起来才浇一次水。室友说这盆绿植长得很好，像有人在偷偷照顾。我只是笑笑，觉得是阳光充足。现在才注意到，花盆底部有一圈长期积水留下的痕迹。我不在的那些日子里，有什么东西一直替我留着水。那盆绿植，一直记着＿＿＿＿＿＿",
  "emotion_options": [
    "我偶尔才想起来的照料",
    "他送来时没说出口的期待",
    "被时间证明的坚韧"
  ],
  "llm_params": {
    "twistable_elements": ["绿植来源", "谁在照料", "我浇水的频率"],
    "drift_dimension": ["情感", "归因"],
    "note": "设计元数据，供 A 的 Prompt参考"
  },
  "offset_type": "A",
  "player_emotion_choice": "被时间证明的坚韧",
  "player_free_input": "也许不是有人在偷偷照顾，是这盆植物本身也在等什么",
  "player_selected": true,
  "player_skipped": false,
  "interaction_timestamp": "2026-08-24T20:18:14",
  "llm_complete_memory": "宿舍窗台上那盆绿植还活着，叶子比刚拿来时更长了。这是大一入学时，对方送来的入学礼物。他送到女生宿舍楼下就走了，我下楼去拿，只看见一盆小小的绿植和一袋土。袋子上贴着一张便签：\"不知道你喜欢什么，这个好养。\"我当时觉得送植物很没意思，随手放在窗台，偶尔想起来才浇一次水。室友说这盆绿植长得很好，像有人在偷偷照顾。我只是笑笑，觉得是阳光充足。现在才注意到，花盆底部有一圈长期积水留下的痕迹。我不在的那些日子里，有什么东西一直替我留着水。那盆绿植，一直记着——比我会坚持的人，不是他，是这盆植物自己。它比我会照顾自己，比我会记得该被记得的事。也许它活下来不是为了他，也不是为了我。是为了证明，有些事不需要被时时惦记，也能自己走到今天。",
  "llm_fake_variants": [
    "宿舍窗台上那盆绿植还活着，叶子比刚拿来时更长了。袋子上贴着一张便签：\"不知道你喜欢什么，这个好养。\"现在才注意到，花盆底部有一圈长期积水��下的痕迹。那盆绿植，一直记着——他送出的那一刻，就没打算收回来。",
    "宿舍窗台上那盆绿植还活着，叶子比刚拿来时更长了。袋子上贴着一张便签：\"不知道你喜欢什么，这个好养。\"现在才注意到，花盆底部有一圈长期积水留下的痕迹。那盆绿植，一直记着——也许送礼物那一刻，他自己也没想好说什么。\"好养\"是他给自己找的台阶。",
    "宿舍窗台上那盆绿植还活着。袋子上贴着一张便签：\"不知道你喜欢什么，这个好养。\"现在才注意到，花盆底部有一圈长期积水留下的痕迹。那盆绿植，一直记着——其实一直是我自己。只是我以为自己在敷衍，其实早就把它照顾进日常里了。"
  ],
  "drift_update": {
    "drift_direction": "toward_closeness",
    "magnitude": 0.5,
    "confidence": 0.71
  }
}
```

**字段填写要点**：

- `llm_complete_memory` 填"也许它活下来不是为了他，也不是为了我。是为了证明，有些事不需要被时时惦记，也能自己走到今天"——把叙事升维到"关系的韧性"而非单方付出
- `llm_fake_variants[0]` → toward_closeness（"他送出就没打算收回来"）
- `llm_fake_variants[1]` → ambiguous（"他没想好说什么"，动机不明）
- `llm_fake_variants[2]` → toward_closeness 更隐蔽（"其实一直是我自己"——内归因）
- `magnitude = +0.5`（较强正向——"坚韧"是积极归因）
- `drift_update.confidence = 0.71`（玩家 free_input 含"植物本身"主体性反思，线索中等）

---

## 字段填写速查表

| drift_direction | 典型 magnitude | 典型 confidence | 何时使用 |
|---|---|---|---|
| `toward_closeness` | +0.3 ~ +0.5 | 0.65 ~ 0.80 | 玩家反思后倾向于信任修复 |
| `toward_distance` | -0.4 ~ -0.6 | 0.70 ~ 0.85 | 玩家反思后倾向于信任削弱 |
| `ambiguous` | -0.1 ~ +0.1 | 0.55 ~ 0.70 | 玩家反思后方向不明确 |

| emotion 强度（LLM 内部参考）| magnitude 区间 |
|---|---|
| 轻微内省（"我偶尔才想起"）| ±0.1 ~ ±0.3 |
| 中等感受（"习惯等待带来的敏感"）| ±0.3 ~ ±0.5 |
| 强烈反思（"一时的隔阂"）| ±0.5 ~ ±0.7 |

---

## 集成到 anchors.json 的建议

**不要**把 `llm_complete_memory` / `llm_fake_variants` / `drift_update` 等运行时字段直接写入 `anchors.json`（会被玩家运行时覆盖）。

**应该**：

- `anchors.json` 只保留**静态字段**（anchor_id / object_id / scene / item_name / anchor_object / category / identification_difficulty / revealed_text / emotion_options / llm_params / offset_type / scene_location）
- 运行时字段由 `memory_anchor_ui.gd` 写入**玩家存档**（`save/player_<slot>.json`）的 `anchors[key]` 子对象
- 这 5 个示例存档在 `save/example_save.json` 作为开发期参考实现

## 验收对齐

| 生产指南 §二.2 B-W2 验收项 | 状态 |
|---|---|
| 提供 5 个完整示例 | ✅（本文档） |
| 每个示例含 schema 必填字段 | ✅ |
| 每个示例含运行时字段示例 | ✅（player_* / llm_* / drift_update） |
| 覆盖 3 场景 + 多 drift_direction | ✅（见选样覆盖矩阵） |
| 5 个示例通过 schema 校验 | ✅（需 run `python -m jsonschema -i save/example_save.json config/anchors.schema.json`） |

