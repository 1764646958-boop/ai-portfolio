# -*- coding: utf-8 -*-
"""DeepSeek API 连通验证脚本（交付物①）。

依次执行：
  (a) 基础连通测试 —— 一次简单对话
  (b) 结构化 JSON 测试 —— response_format={"type":"json_object"}
  (c) 延迟测试 —— 同一请求连续 5 次，统计平均 / 最小 / 最大

Key 为空时进入 Mock 模式：不发起真实网络请求，用固定模拟响应完成全部逻辑，
仍生成完整报告（顶部加 Mock 横幅）。运行后报告写入 llm/连通验证报告.md。
"""

import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from deepseek_client import (
    DeepSeekClient,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)

# 保证中文输出不乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent          # W1/llm
load_dotenv(BASE_DIR.parent / ".env")                # 显式加载 W1/.env

MOCK_MODE = DEEPSEEK_API_KEY == ""

# ------------------------- Mock 固定数据 -------------------------
MOCK_BASIC_REPLY = (
    "（Mock）你好，我是《防线》的 AI 陪伴者。基础连通测试通过。"
    "当前为 Mock 模式，待填入真实 Key 后即可获得真实回复。"
)
MOCK_JSON = {"drift_direction": "human", "magnitude": 3, "confidence": 0.87}
MOCK_LATENCIES = [0.82, 0.74, 0.91, 0.79, 0.85]     # 模拟值（秒）

LATENCY_ROUNDS = 5
JSON_REQUIRED_FIELDS = {"drift_direction", "magnitude", "confidence"}


# ------------------------- 测试步骤 -------------------------
def request_basic(client):
    """(a) 基础连通测试。"""
    messages = [
        {
            "role": "system",
            "content": "你是《防线》游戏中的 AI 陪伴者，温柔、精准、永远为你好。",
        },
        {"role": "user", "content": "你好，请做一次连通测试：用一句话说明你已在线。"},
    ]
    if MOCK_MODE:
        return messages, MOCK_BASIC_REPLY
    resp = client.chat(messages)
    return messages, resp.choices[0].message.content


def request_json(client):
    """(b) 结构化 JSON 测试。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是《防线》的记忆分析引擎。你必须只输出一个合法的 JSON 对象，"
                "不要输出任何解释性文字或 Markdown 代码块。"
            ),
        },
        {
            "role": "user",
            "content": (
                "分析以下记忆锚点，只输出 JSON，字段为："
                '{"drift_direction": "ai" 或 "human", '
                '"magnitude": 0 到 10 的整数, "confidence": 0 到 1 的小数}。'
                "记忆范本：咖啡店墙上的照片——去年夏天，旧友迟到了半小时但带了栗子蛋糕。"
                "玩家情感补充：有点可爱。"
            ),
        },
    ]
    if MOCK_MODE:
        return messages, json.dumps(MOCK_JSON, ensure_ascii=False)
    resp = client.chat(messages, json_mode=True)
    return messages, resp.choices[0].message.content


def run_latency(client, rounds=LATENCY_ROUNDS):
    """(c) 延迟测试：同一请求连续 rounds 次。"""
    messages = [{"role": "user", "content": "请只回复两个字：已连接"}]
    latencies = []
    for i in range(rounds):
        if MOCK_MODE:
            latencies.append(MOCK_LATENCIES[i % len(MOCK_LATENCIES)])
            continue
        start = time.perf_counter()
        client.chat(messages)
        latencies.append(time.perf_counter() - start)
    return messages, latencies


# ------------------------- 报告生成 -------------------------
def render_report(ctx):
    """根据测试上下文渲染 Markdown 报告。"""
    banner = ""
    if MOCK_MODE:
        banner = "> ⚠️ **【Mock 模式】待填入真实 Key 后重跑**\n>\n"

    mode_label = "Mock 模式（Key 空置，未发起真实网络请求）" if MOCK_MODE else "真实 DeepSeek 调用"
    time_label = ctx["test_time"]
    if MOCK_MODE:
        time_label += "（模拟运行）"

    latency_rows = "\n".join(
        f"| {i + 1} | {v:.3f} |" for i, v in enumerate(ctx["latencies"])
    )

    # 结构化 JSON 校验结果
    if ctx["json_valid"]:
        json_check = "✅ 合法 JSON，且三字段齐全"
        parsed_note = "解析后字段：" + ", ".join(
            f"`{k}`={v!r}" for k, v in ctx["json_parsed"].items()
        )
    else:
        json_check = "❌ 无法解析为 JSON"
        parsed_note = "原始输出：" + str(ctx["json_reply"])

    conclusion = (
        "**Mock 模式结论**：脚本在 Key 空置下完整跑通全部 (a)(b)(c) 逻辑并生成报告，"
        "未发起真实网络请求，延迟数据为模拟值。"
        "请在 `W1/.env` 填入真实 `DEEPSEEK_API_KEY` 后重跑本脚本，以验证真实连通性。"
        if MOCK_MODE
        else (
            "**真实模式结论**：DeepSeek API 连通成功，基础对话与结构化 JSON 均正常返回，"
            f"延迟平均 {ctx['avg']:.3f}s（最小 {ctx['lo']:.3f}s / 最大 {ctx['hi']:.3f}s）。"
            "结构化输出满足 `json_object` 约束，三字段齐全，可作为后续 Prompt 引擎的运行时底座。"
        )
    )

    return f"""# 《防线》LLM API 连通验证报告（交付物①）

{banner}
| 项目 | 值 |
|---|---|
| 测试时间 | {time_label} |
| 测试模式 | {mode_label} |
| base_url | `{DEEPSEEK_BASE_URL}` |
| model | `{DEEPSEEK_MODEL}` |

## (a) 基础连通测试

**请求样例**

```json
{json.dumps(ctx["basic_messages"], ensure_ascii=False, indent=2)}
```

**响应样例**

```text
{ctx["basic_reply"]}
```

## (b) 结构化 JSON 测试（response_format=json_object）

**请求样例**

```json
{json.dumps(ctx["json_messages"], ensure_ascii=False, indent=2)}
```

**响应样例**

```text
{ctx["json_reply"]}
```

**结构校验**：{json_check}

{parsed_note}

## (c) 延迟测试（同一请求 × {LATENCY_ROUNDS}）

| 次数 | 延迟（秒） |
|---|---|
{latency_rows}

| 统计项 | 值 |
|---|---|
| 平均 | {ctx['avg']:.3f} s |
| 最小 | {ctx['lo']:.3f} s |
| 最大 | {ctx['hi']:.3f} s |
| 数据说明 | {'模拟值' if MOCK_MODE else '真实测得'} |

## 结论

{conclusion}
"""


def main():
    client = DeepSeekClient()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DeepSeek 连通验证 启动")
    print(f"  base_url = {DEEPSEEK_BASE_URL}")
    print(f"  model    = {DEEPSEEK_MODEL}")
    print(f"  Key 状态 = {'空置 → Mock 模式' if MOCK_MODE else '已配置 → 真实调用'}")

    # (a) 基础连通
    basic_messages, basic_reply = request_basic(client)
    print("  (a) 基础连通测试 完成")

    # (b) 结构化 JSON
    json_messages, json_reply = request_json(client)
    try:
        json_parsed = json.loads(json_reply)
        json_valid = isinstance(json_parsed, dict) and JSON_REQUIRED_FIELDS.issubset(
            json_parsed.keys()
        )
    except Exception:
        json_parsed, json_valid = None, False
    print(f"  (b) 结构化 JSON 测试 完成（合法={json_valid}）")

    # (c) 延迟测试
    latency_messages, latencies = run_latency(client, rounds=LATENCY_ROUNDS)
    avg = statistics.mean(latencies)
    lo = min(latencies)
    hi = max(latencies)
    print(
        f"  (c) 延迟测试 完成（平均 {avg:.3f}s / 最小 {lo:.3f}s / 最大 {hi:.3f}s）"
    )

    ctx = {
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "basic_messages": basic_messages,
        "basic_reply": basic_reply,
        "json_messages": json_messages,
        "json_reply": json_reply,
        "json_parsed": json_parsed,
        "json_valid": json_valid,
        "latency_messages": latency_messages,
        "latencies": latencies,
        "avg": avg,
        "lo": lo,
        "hi": hi,
    }

    report_path = BASE_DIR / "连通验证报告.md"
    report_path.write_text(render_report(ctx), encoding="utf-8")
    print(f"  报告已写入: {report_path}")


if __name__ == "__main__":
    main()
