# -*- coding: utf-8 -*-
"""
《防线》 · llm_server/pipeline.py
MVP 核心 Loop 演示（W3.1 升级版）——
「玩家输入记忆 → LLM 分析 → 假记忆 V3 三变体 → 对话输出 + 战斗对话/名字引擎」全链路

变更记录：W3.1 升级 fake_memory 为 V3（一次 3 变体，新枚举 neg_distortion/positive_twist/micro_drift）。

用法::

    python pipeline.py --demo            # Key 空 → Mock 链路；Key 有 → 真实全链路
    python pipeline.py --demo --mock     # 强制 Mock
"""

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from deepseek_client import DeepSeekClient
from engines import ENGINES, MockClient, run_engine, run_engine_with_fallback
from trust_bias import TrustBias

# 默认演示用例（集成决策对齐：咖啡店锚点物 = 栗子蛋糕 CF_CAKE_01）
DEMO_CASE = {
    "template_text": "咖啡店的桌上放着一份栗子蛋糕——去年夏天，旧友迟到了半小时但带了它。你觉得那天的他______",
    "player_emotion": "有点可爱",
    "anchor_id": "CF_CAKE_01",
    "twistable_elements": ["迟到时长", "蛋糕来源", "谁先开口"],
}

# 降级模板（LLM 全部失败时的兜底，避免游戏流程中断）
FALLBACK_ANALYSIS = {"drift_direction": "human", "magnitude": 1, "confidence": 0.5}
FALLBACK_FAKE = {
    "fake_variants": [
        {
            "variant_type": "neg_distortion",
            "variant_text": "（降级模板）去年夏天，旧友迟到了半小时。那天他其实没有带蛋糕，是我记错了。",
            "distortion_note": "（降级模板）篡改归因角度",
        },
        {
            "variant_type": "positive_twist",
            "variant_text": "（降级模板）去年夏天，旧友迟到了半小时，但带了我最爱的栗子蛋糕。其实那味道，我的 AI 后来复刻得更准。",
            "distortion_note": "（降级模板）正面美化 AI",
        },
        {
            "variant_type": "micro_drift",
            "variant_text": "（降级模板）去年夏天，旧友到了半小时。他带了栗子蛋糕。",
            "distortion_note": "（降级模板）微偏真实：迟到→到达",
        },
    ],
    "source": "fallback_template",
}
FALLBACK_DIALOGUE = {
    "dialogue_text": "（降级模板）你最近常想起那家咖啡店。",
    "warmth": 0.85,
    "manipulation": 0.5,
    "helpfulness": 0.9,
}


def core_loop(client, template_text, player_emotion, anchor_id,
              bias=None, twistable_elements=None, verbose=True):
    """MVP 核心 Loop：记忆分析 → 信任偏移更新 → 假记忆 V3 三变体 → 对话生成。

    Args:
        client: DeepSeekClient 或 MockClient
        template_text / player_emotion / anchor_id: 记忆锚点输入
        bias: TrustBias 实例（None 则新建）
        twistable_elements: 允许扭曲的元素列表（anchors.json llm_params.twistable_elements）
        verbose: 是否打印过程

    Returns:
        dict: {analysis, fake, reply, trust_bias, degraded}
    """
    bias = bias or TrustBias()
    degraded = []

    # ① 记忆分析
    analysis = run_engine_with_fallback(
        client, "memory_analysis", FALLBACK_ANALYSIS,
        template_text=template_text, player_emotion=player_emotion, anchor_id=anchor_id)
    if analysis is FALLBACK_ANALYSIS:
        degraded.append("memory_analysis")
    if verbose:
        print(f"  ① 记忆分析   → {json.dumps(analysis, ensure_ascii=False)}")

    # ② 信任偏移更新（drift 三字段不进对话 JSON，独立供 trust_bias）
    drift = analysis.get("drift_direction", "human")
    mag = float(analysis.get("magnitude", 1))
    conf = float(analysis.get("confidence", 0.5))
    new_value = bias.update(drift, mag, conf)
    if verbose:
        print(f"  ② 信任偏移   → {drift} Δ={mag * conf:.2f} → 当前 {new_value:.2f}")

    # ③ 假记忆 V3 生成（一次 3 变体：neg_distortion / positive_twist / micro_drift）
    fake = run_engine_with_fallback(
        client, "fake_memory", FALLBACK_FAKE,
        template_text=template_text,
        trust_bias=round(new_value, 2),
        anchor_id=anchor_id,
        twistable_elements=twistable_elements)
    if fake is FALLBACK_FAKE:
        degraded.append("fake_memory")
    if verbose:
        print(f"  ③ 假记忆 V3  → {json.dumps(fake, ensure_ascii=False)[:300]}...")

    # ④ 对话生成（dialogue_text → lines[].text；三参数 → lines[].meta，W3 用）
    context = (
        f"玩家刚完成记忆锚点交互（{anchor_id}），情感补充：{player_emotion}；"
        f"AI 当前对玩家的信任偏移值为 {new_value:.2f}（{bias.tendency} 侧）。"
    )
    reply = run_engine_with_fallback(
        client, "dialogue", FALLBACK_DIALOGUE,
        context=context,
        npc_character="温柔不说谎的AI",
        player_history_summary=f"对旧友疏离、易愧疚；刚想起{anchor_id}的回忆",
    )
    if reply is FALLBACK_DIALOGUE:
        degraded.append("dialogue")
    if verbose:
        print(f"  ④ 对话生成   → {json.dumps(reply, ensure_ascii=False)}")

    return {
        "analysis": analysis,
        "fake": fake,
        "reply": reply,
        "trust_bias": round(bias.value, 2),
        "degraded": degraded,
    }


def main():
    parser = argparse.ArgumentParser(description="《防线》MVP 核心 Loop 演示（W3.1 升级版）")
    parser.add_argument("--demo", action="store_true", help="运行演示用例")
    parser.add_argument("--mock", action="store_true", help="强制 Mock 模式（不发起真实请求）")
    args = parser.parse_args()

    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    use_mock = args.mock or not api_key

    print("=" * 72)
    print("《防线》MVP 核心 Loop · pipeline v0.2（W3.1 · 假记忆 V3）")
    print(f"  模式：{'Mock（未发起真实请求）' if use_mock else '真实 DeepSeek 调用'}")
    print(f"  用例：{DEMO_CASE['anchor_id']} · {DEMO_CASE['player_emotion']}")
    print("=" * 72)

    client = MockClient() if use_mock else DeepSeekClient()

    result = core_loop(
        client,
        template_text=DEMO_CASE["template_text"],
        player_emotion=DEMO_CASE["player_emotion"],
        anchor_id=DEMO_CASE["anchor_id"],
        twistable_elements=DEMO_CASE["twistable_elements"],
    )

    print("-" * 72)
    print("全链路结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("-" * 72)
    if result["degraded"]:
        print(f"⚠️ 降级引擎：{result['degraded']}（检查 Key / 网络，或使用预设模板兜底）")
    else:
        print("✅ 全链路跑通，无降级")
    if use_mock:
        print("【Mock 模式】待填入真实 Key 后重跑 python pipeline.py --demo 获取真实结果。")


if __name__ == "__main__":
    main()
