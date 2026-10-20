# llm_server —— 《防线》LLM HTTP 服务端（W3.1）

给 Godot 侧 `scripts/llm_gateway.gd` 提供 HTTP 接口（POST /llm/{endpoint}）。

## 快速开始

```bash
python llm_server.py              # 端口 8000；Key 空 → 自动 Mock
python test_llm_server.py         # 全端点自测（Mock 19/19 PASS）
```

## 依赖

```bash
pip install openai python-dotenv
```

## 填入真实 Key

1. 复制 `.env.example` 为 `.env`
2. `DEEPSEEK_API_KEY=` 后填入真实 Key
3. 重启 `python llm_server.py`（控制台显示"真实 DeepSeek"即生效）

对接契约（payload/响应逐字段表 + B 接入说明）见 `W3\llm\llm_server对接契约.md`。
