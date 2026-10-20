# -*- coding: utf-8 -*-
"""
《防线》 · W2/llm/test_engines.py
LLM 调度层 v0.1 —— 测试脚本（Mock/真实双模式，沿用 W1 风格）

行为：
  - DEEPSEEK_API_KEY 为空 → Mock 模式：结构自检（模板完整/schema 齐全/build 无残留）
    + MockClient 跑通 pipeline 全链路 + TrustBias 单元测试
  - Key 非空 → 真实模式：三引擎各连测 3 次 + pipeline 真实全链路
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

LLM_DIR = os.path.dirname(os.path.abspath(__file__))
W2_DIR = os.path.dirname(LLM_DIR)
sys.path.insert(0, LLM_DIR)

for _p in (os.path.join(W2_DIR, ".env"), os.path.join(LLM_DIR, ".env")):
    load_dotenv(_p)

from prompts import (
    MEMORY_ANALYSIS_SYSTEM_TEMPLATE,
    DIALOGUE_GENERATION_SYSTEM_TEMPLATE,
    FAKE_MEMORY_SYSTEM_TEMPLATE,
    MEMORY_ANALYSIS_OUTPUT_SCHEMA,
    DIALOGUE_OUTPUT_SCHEMA,
    FAKE_MEMORY_OUTPUT_SCHEMA,
    build_memory_analysis_prompt,
    build_dialogue_generation_prompt,
    build_fake_memory_prompt,
)
from engines import ENGINES, MockClient, extract_json, validate_schema, run_engine
from trust_bias import TrustBias
from pipeline import core_loop, DEMO_CASE

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").strip()

RUN_TIMES = 3
TEMPERATURE = 0.7

# 真实用例（与集成决策对齐：CF_CAKE_01 栗子蛋糕）
MEMORY_CASE = {
    "template_text": "咖啡店的桌上放着一份栗子蛋糕——去年夏天，旧友迟到了半小时但带了它。你觉得那天的他______",
    "player_emotion": "有点可爱",
    "anchor_id": "CF_CAKE_01",
}
FAKE_CASE = {
    "real_memory": "去年夏天，旧友迟到了半小时但带了栗子蛋糕。他把蛋糕递给我，有点不好意思。",
    "trust_bias": 2.5,
    "variant_type": "subtle_shift",
}
DIALOGUE_CASE = {
    "context": "玩家刚完成记忆锚点交互（CF_CAKE_01），选择跳过没看旧友的短信",
    "npc_character": "温柔不说谎的AI",
    "player_history_summary": "对旧友疏离、易愧疚",
}


def banner(text):
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Mock 模式：结构自检 + 链路验证 + TrustBias 单元测试
# ---------------------------------------------------------------------------

def mock_self_check():
    banner("Mock 模式 · 调度层自检报告（未发起真实 API 调用）")
    print("【说明】当前 DEEPSEEK_API_KEY 为空，仅做静态结构自检 + Mock 链路验证。")
    print("【待办】待填入真实 Key 后重跑本脚本，即可得到真实 3 次稳定性测试。\n")

    checks = []

    # 1. 三引擎模板完整
    checks.append((
        "记忆分析引擎 · 模板内容完整",
        all(k in MEMORY_ANALYSIS_SYSTEM_TEMPLATE for k in
            ("记忆分析引擎", "情感温度", "归因模式", "选择性回避", "自我暴露深度")),
        "含引擎名 + 四分析维度",
    ))
    checks.append((
        "对话生成引擎 · 模板内容完整",
        all(k in DIALOGUE_GENERATION_SYSTEM_TEMPLATE for k in
            ("从不正面说谎", "温柔服务于目标", "不暴露真实意图")),
        "含三条人设硬约束",
    ))
    checks.append((
        "假记忆生成引擎 · 模板内容完整",
        all(k in FAKE_MEMORY_SYSTEM_TEMPLATE for k in
            ("假记忆生成引擎", "negative_twist", "positive_twist", "subtle_shift")),
        "含引擎名 + 三变体类型",
    ))

    # 2. Schema 字段齐全
    checks.append((
        "记忆分析 Schema 字段齐全",
        set(MEMORY_ANALYSIS_OUTPUT_SCHEMA) == {"drift_direction", "magnitude", "confidence"},
        "drift_direction / magnitude / confidence",
    ))
    checks.append((
        "对话生成 Schema 字段齐全",
        set(DIALOGUE_OUTPUT_SCHEMA) == {"dialogue_text", "warmth", "manipulation", "helpfulness"},
        "dialogue_text / warmth / manipulation / helpfulness",
    ))
    checks.append((
        "假记忆 Schema 字段齐全",
        set(FAKE_MEMORY_OUTPUT_SCHEMA) == {"variant_text", "distortion_note"},
        "variant_text / distortion_note",
    ))

    # 3. 引擎注册表完整
    checks.append((
        "ENGINES 注册表含三引擎",
        set(ENGINES) == {"memory_analysis", "fake_memory", "dialogue"},
        "memory_analysis / fake_memory / dialogue",
    ))

    # 4. build 函数格式化正常（无残留占位符）
    mem_msgs = build_memory_analysis_prompt(**MEMORY_CASE)
    fake_msgs = build_fake_memory_prompt(**FAKE_CASE)
    dlg_msgs = build_dialogue_generation_prompt(**DIALOGUE_CASE)
    checks.append((
        "三 build 函数格式化正常",
        all(f"{{{k}}}" not in mem_msgs[0]["content"] for k in MEMORY_CASE)
        and all(f"{{{k}}}" not in fake_msgs[0]["content"] for k in FAKE_CASE)
        and all(f"{{{k}}}" not in dlg_msgs[0]["content"] for k in DIALOGUE_CASE),
        "输入已注入，无残留占位符",
    ))

    # 5. TrustBias 单元测试
    tb = TrustBias()
    tb.update("ai", 3, 1.0)      # +3.0
    tb.update("human", 5, 0.5)   # -2.5 → 0.5
    v = tb.value
    checks.append((
        "TrustBias 累积逻辑正确",
        abs(v - 0.5) < 1e-9,
        f"ai+3.0 后 human-2.5 → {v:.2f}",
    ))
    tb.update("ai", 10, 1.0)     # +10 → clamp 到 10
    checks.append((
        "TrustBias 上限 clamp",
        tb.value == 10.0,
        f"clamp 到 +10 → {tb.value}",
    ))
    tb.reset()
    tb.update("human", 10, 1.0)  # -10 → clamp 到 -10
    checks.append((
        "TrustBias 下限 clamp",
        tb.value == -10.0,
        f"clamp 到 -10 → {tb.value}",
    ))

    # 6. Mock 全链路（MockClient + core_loop）
    mock_client = MockClient()
    result = core_loop(
        mock_client,
        template_text=DEMO_CASE["template_text"],
        player_emotion=DEMO_CASE["player_emotion"],
        anchor_id=DEMO_CASE["anchor_id"],
        verbose=False,
    )
    checks.append((
        "Mock 全链路跑通（pipeline core_loop）",
        all(k in result for k in ("analysis", "fake", "reply", "trust_bias"))
        and result["analysis"].get("drift_direction") in ("ai", "human")
        and result["reply"].get("dialogue_text")
        and result["degraded"] == [],
        f"analysis/fake/reply/trust_bias={result['trust_bias']} 无降级",
    ))
    checks.append((
        "Mock 输出可通过 schema 校验",
        validate_schema(result["analysis"], MEMORY_ANALYSIS_OUTPUT_SCHEMA, "analysis")[0]
        and validate_schema(result["fake"], FAKE_MEMORY_OUTPUT_SCHEMA, "fake")[0]
        and validate_schema(result["reply"], DIALOGUE_OUTPUT_SCHEMA, "reply")[0],
        "三引擎输出结构合法",
    ))

    n_pass = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  —— {detail}")
        n_pass += ok

    print("\n" + "=" * 72)
    print(f"  自检结论：{n_pass}/{len(checks)} 项通过")
    print("=" * 72)
    return n_pass == len(checks)


# ---------------------------------------------------------------------------
# 真实模式：连测 3 次
# ---------------------------------------------------------------------------

def run_engine_stability(name, case, schema):
    from deepseek_client import DeepSeekClient
    client = DeepSeekClient()
    banner(f"引擎：{name} · 同一输入连测 {RUN_TIMES} 次（temperature={TEMPERATURE}）")

    results = []
    for i in range(1, RUN_TIMES + 1):
        try:
            obj = run_engine(client, name, max_retries=1, **case)
            if obj is None:
                results.append({"ok": False, "obj": None, "errors": ["全部尝试失败（降级）"]})
                print(f"  [{i}] 降级（None）")
                continue
            ok, errors = validate_schema(obj, schema, name)
            print(f"  [{i}] {'通过' if ok else '失败'} {json.dumps(obj, ensure_ascii=False)}")
            results.append({"ok": ok, "obj": obj, "errors": errors})
        except Exception as e:
            print(f"  [{i}] 异常：{e}")
            results.append({"ok": False, "obj": None, "errors": [str(e)]})

    valid = [r for r in results if r["ok"]]
    print(f"  稳定性：{len(valid)}/{RUN_TIMES} 结构合法")
    return len(valid) == RUN_TIMES


def run_real_test():
    ok1 = run_engine_stability("memory_analysis", MEMORY_CASE, MEMORY_ANALYSIS_OUTPUT_SCHEMA)
    ok2 = run_engine_stability("fake_memory", FAKE_CASE, FAKE_MEMORY_OUTPUT_SCHEMA)
    ok3 = run_engine_stability("dialogue", DIALOGUE_CASE, DIALOGUE_OUTPUT_SCHEMA)

    banner("真实模式 · pipeline 全链路")
    from deepseek_client import DeepSeekClient
    result = core_loop(
        DeepSeekClient(),
        template_text=DEMO_CASE["template_text"],
        player_emotion=DEMO_CASE["player_emotion"],
        anchor_id=DEMO_CASE["anchor_id"],
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok4 = result["degraded"] == []

    print("\n" + "=" * 72)
    print(f"  真实模式结论：三引擎稳定 {ok1 and ok2 and ok3} · 全链路无降级 {ok4}")
    print("=" * 72)
    return ok1 and ok2 and ok3 and ok4


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    banner("《防线》· LLM 调度层 v0.1 · 测试")
    print(f"  DEEPSEEK_API_KEY : {'已配置' if DEEPSEEK_API_KEY else '空置（进入 Mock 模式）'}")

    if DEEPSEEK_API_KEY:
        ok = run_real_test()
    else:
        ok = mock_self_check()

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
