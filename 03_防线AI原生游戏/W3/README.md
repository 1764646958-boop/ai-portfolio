# W3 · 成员 A 交付物索引

> 阶段：W3（8/24-8/30）· 成员 A（主叙事/LLM 架构/Shader/音乐）
> 状态：**全部 6 项完成**。待人工项见 §4。

---

## 1. 交付物清单

| 任务 | W3 目录 | 仓库新增（defense-line-dev/） | 验收状态 |
|---|---|---|---|
| W3.1 五端点 LLM 服务器 | `W3\llm\llm_server对接契约.md`（v1） | `llm_server\`（deepseek_client/prompts/engines/trust_bias/pipeline/llm_server + test_llm_server + .env.example + README） | ✅ 自测 **19/19 PASS**；服务器引导验证（五种变体、source: mock_v3/v3 合法） |
| W3.2 记忆考古三关 | `W3\archaeology\记忆考古三关文案.md`、`archaeology_reveal_dialogues.json` | — | ✅ reveal JSON 校验 PASS；三关全要素 + LLM 质量基准示范 |
| W3.3 战斗压迫参数表 | `W3\battle\压迫参数表_v1.md`、`pressure_params.json` | — | ✅ JSON 可解析；与 md 逐 5 秒表同值；**待 B 确认 B1-B7**（md §6） |
| W3.4 三项视觉压迫 Shader | `W3\shaders\三项Shader接入说明.md` | `assets\shaders\color_grade.gdshader`、`screen_shake.gdshader`、`tunnel_vision.gdshader` | ✅ 语法自查+接入说明（uniform 映射/单 pass 合并预案/性能预算 <2ms） |
| W3.5 BGM#2/#3 作曲 Brief | `W3\audio\BGM23作曲Brief.md` | — | ✅ 文档仅产出；两奏规格/动机引用/导出规范/验收标准 |
| W3.6 假记忆评测+调优 | `W3\llm\假记忆Prompt调优方案.md`、`eval_r1_baseline.json`、`eval_r2_v31.json`、`eval_r3_v32_trust5.json`、`eval_r3_v32_trust-5.json` | `llm_server\tools\eval_fake_memory.py`（+prompts.py 的 v3_1/v3_2 实验模板） | ✅ **R1→R3 实测**：R1 60% → **R2 33/33（100%，推荐升正式 v4）** → R3 两级 97%/91% |

## 2. 给 B 的提示

1. **W3.3 待确认清单 B1-B7**（`W3\battle\压迫参数表_v1.md` §6）：请 B 批注或直接改 `pressure_params.json`；A 在 W4.4 实现 controller 前按默认值（此处提示 B：改动请在两日内给，便于 W4.4 一次性对齐）。
2. **W3.1 契约 v1**（`W3\llm\llm_server对接契约.md`）：llm_gateway.gd 启用 `_http_request` 即可接入；默认 `--mock` 模式（无 Key）也能演示——**Key 注入方式见契约 §3**（或 `DEEPSEEK_API_KEY` 环境变量直传，不动 .env）。
3. **W3.6 结论传达给 B**：假记忆 V3 prompt 在 R2 修法后 33/33 达标——契约不变；若 B 侧期望「三选一有难度梯度」（70/50/30%），micro_drift 相似度 0.87~0.98 符合预期。

## 3. 给 C 的提示

1. **W3.4 Shader 挂载**：三枚 ColorRect 的树序（vision_erosion → tunnel_vision → color_grade → screen_shake）与 mouse_filter 设置见 `W3\shaders\三项Shader接入说明.md` §2；W4.4 会用单 pass 合并版替换（**届时删除四个散装 ColorRect，换成 battle_post 一个**）。
2. **W3.2 reveal 对话**：`archaeology_reveal_dialogues.json` 三个 dialogue_id（ARCH_L1/2/3_REVEAL）接 `truth_shard_unlock` 信号播放；AI 从不说谎、speaker 仅 ai/friend/player。
3. **W3.3 参数表 JSON**：`pressure_params.json` 就是 W4.4 controller 的驱动数据源（同 md）。

## 4. 待人工处理项

| # | 项 | 说明 | 归属 |
|---|---|---|---|
| 1 | B1-B7 确认 | 战斗参数表 v1 待 B 终稿（窗口 8s vs 3s、170 vs 160bpm 等） | B（A 会随 W4.4 同步） |
| 2 | `sfx_glitch.wav` | `res://assets/audio/sfx_glitch.wav` 仍缺失（memory_archaeology.gd 期待；W3.4 白噪爆发共用）——**A 需产出一段 0.5s 白噪/电流音** | A |
| 3 | BGM#2/#3 成曲 | Brief 已出（W3.5），音频制作未开工 | A/作曲 |
| 4 | .env 真 Key | 仓库 `defense-line-dev/.env` 未建（凡 .env 不入库）；开发机可用 `DEEPSEEK_API_KEY` 环境变量直传 llm_server 或复制 W2/.env **本地**使用 | A |
| 5 | v3_1 升正式 v4 | 调优方案 §5.1 结论：R2 达标，正式接入由 A 在 W4.x 落版（ENGINES.build 指向 v4） | A |

## 5. 一页流程（此表= 交付确认）

```
llm_server（五端点,19/19 PASS）
  ├─→ W3.1 契约 v1 → B（llm_gateway.gd 启用 HTTP）
  ├─→ W3.2 考古文案+reveal JSON → C（truth_shard_unlock 信号接）
  ├─→ W3.3 参数表 v1（md+json）→ B 确认 B1-B7 → W4.4 实现
  ├─→ W3.4 三 Shader + 接入说明 → C（预览）/W4.4（合并）
  ├─→ W3.5 BGM2/3 Brief → 作曲（A 值守）
  └─→ W3.6 评测工具+调优方案（R2 33/33）→ 假记忆引擎 v4 落版依据
```

---

*W3 阶段完成。下一步：W4（8/31-9/6）任务按 W4.1 顺序执行。*
