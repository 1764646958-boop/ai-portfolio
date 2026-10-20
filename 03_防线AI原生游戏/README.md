# 《防线》DEFENSE LINE — 项目总仓

心理叙事探索游戏 · 2026 腾讯游戏创作大赛 AI 原生游戏赛道
团队：A（主创/叙事/LLM/Shader/音乐）· B（核心系统/叙事设计）· C（玩法程序/交互/UI）

**Git 规范：**
- 提交信息格式：`[模块] 简要描述`，例如 `[记忆锚点] 完成打字机效果+3选项按钮联动`

## 仓库结构

```
defense-line/
├── project.godot            # Godot 项目入口（Godot 4.7 / MagicAI 提交前验证）
├── assets/                  # 美术/音频/字体/Shader（shaders/ 含 A 的四件套+合并版）
├── config/                  # 锚点范本库 anchors.json / QTE 参数 / 信任偏移规则 / 对话样本
├── docs/                    # 接口契约（dialogue_json_format 等）/ 设计文档 / 周报 / 决策记录
├── scenes/                  # 场景（咖啡店/教室/宿舍/街道 + ui/）
├── scripts/                 # GDScript（EventBus/DialogManager/LLMGateway/MemoryArchaeology/battle_audio 等）
├── tools/                   # 辅助脚本（md2docx.py 等）
├── llm_server/              # A：LLM 本地服务（Python，localhost:8000，五端点对齐 LLMGateway 契约）
│                            #   启动：python llm_server.py（依赖 .env 的 DEEPSEEK_API_KEY，空则 Mock）
├── W1/  W2/  W3/  W4/       # A：每周开发产出归档（提示词/代码/文档/验收记录）
└── deliverables/            # 历周交付包存档（临时 zip 不入库）
```

## 周里程碑

| 周 | 日期 | 里程碑 |
|---|---|---|
| W1 | 8/10-8/16 | 美术方向 + 引擎选型 + 技术方案锁定 |
| W2 | 8/17-8/23 | MVP Build：核心 Loop 可演示 |
| W3 | 8/24-8/30 | Alpha Build：记忆考古×3 + 战斗框架 |
| W4 | 8/31-9/6 | Beta v1：完整 Demo + 首次外部试玩 |
| W5 | 9/7-9/13 | Beta v2：接近最终品质 + 二轮测试 |
| 提交 | 9/15 | 🏆 正式提交 |

## LLM 服务（A 交付，W3+）

- 位置：`llm_server/`；契约：`docs/dialogue_json_format.md` + `W3/llm/llm_server对接契约.md`
- 端点：`/llm/analyze_memory` `/llm/generate_dialogue` `/llm/analyze_fake_memory` `/llm/battle_dialogue` `/llm/generate_name`
- B 侧：`scripts/llm_gateway.gd` 的 `_http_request` 启用后对接；Key 配置在 `llm_server/.env`（不入库，参照 `.env.example`）
