# -*- coding: utf-8 -*-
"""
《防线》 · llm_server/tools/eval_fake_memory.py
假记忆生成引擎评测工具（W3.6 · 与「假记忆Prompt调优方案.md」配套）

用途：对记忆考古三关（MA_BRACELET_01 / MA_ROSE_01 / MA_FLOWER_01）各生成
1 组 3 变体（neg_distortion / positive_twist / micro_drift），并按四项
判定标准打分：
  ① 结构合法 —— 3 个变体、枚举齐全、字段完整（复用 validate_schema）
  ② 相似度     —— difflib.SequenceMatcher(variant_text, template_text).ratio()
                  必须落在 0.30 ~ 0.85（过低=脱靶编造；过高=改动不足，假得不像假）
  ③ 扭曲点     —— distortion_note 命中 twistable_elements 列表内关键词
                  启发式判定（含局限说明；精确判定靠人工复审）
  ④ 文本长度   —— 去空白后中文字符数 ≥ 30

执行::
    python tools/eval_fake_memory.py                 # 默认 Mock（Key 空自动 Mock）
    python tools/eval_fake_memory.py --live          # 真实 DeepSeek（需 Key + 网络）
    python tools/eval_fake_memory.py --trust -2      # 指定 trust_bias（-10~+10）
    python tools/eval_fake_memory.py --outfile eval_result.json

Mock 说明：Mock 数据仅用于链路自检（打分照常输出，但结果不代表 LLM 质量，
评分表中以 `[mock]` 标注）。

Prompt 调优方法论（R1/R2/R3 旋转实验）见：
W3\llm\假记忆Prompt调优方案.md
"""

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engines import MockClient, run_engine, validate_schema  # noqa: E402
from prompts import (FAKE_MEMORY_V3_OUTPUT_SCHEMA, VALID_VARIANT_TYPES,  # noqa: E402
                     build_fake_memory_v3, build_fake_memory_v3_1, build_fake_memory_v3_2)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ANCHORS_PATH = REPO_ROOT / "config" / "anchors.json"

# 记忆考古三关（anchors.json v7.1，辨识度见 archaeology 文案）
LEVELS = [
    {"level": 1, "anchor_id": "MA_BRACELET_01", "difficulty": 0.70},
    {"level": 2, "anchor_id": "MA_ROSE_01", "difficulty": 0.50},
    {"level": 3, "anchor_id": "MA_FLOWER_01", "difficulty": 0.30},
]

# Prompt 版本 → build 函数（R1 基线=v3 原样；R2=v3_1 加硬约束+示例；R3=v3_2 trust 分级措辞）
TEMPLATES = {
    "v3": build_fake_memory_v3,
    "v3_1": build_fake_memory_v3_1,
    "v3_2": build_fake_memory_v3_2,
}

# 评分标准阈值（与「假记忆Prompt调优方案.md」一致；v1.1：按变体类型分级）
# 设计依据：micro_drift 的目标就是「几乎选对、只改一处」，相似度必须允许 0.9+；
#            而 neg/positive 是明显扭曲，相似度过高 = 没改。
SIM_MIN_NEG, SIM_MAX_NEG = 0.30, 0.93   # neg_distortion / positive_twist
SIM_MIN_MICRO, SIM_MAX_MICRO = 0.60, 0.995  # micro_drift（贴原版但确实有改动）
PAIR_MAX = 0.98        # 三个变体两两相似度上限（=1.0 说明字字相同：三卡一模一样，必判 FAIL）
PAIR_PREFIX = 100      # 变体两两比较前 PAIR_PREFIX 字符（捕捉「只有尾巴不同」的偷懒写法）
LEN_MIN = 30

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"    ✅ {name}")
    else:
        FAIL.append(name)
        print(f"    ❌ {name} ← {detail}")


def run() -> dict:
    parser = argparse.ArgumentParser(description="假记忆三关评测（W3.6）")
    parser.add_argument("--trust", type=float, default=0.0,
                        help="trust_bias（-10~+10；正值=偏向 AI，负值=偏向人类）")
    parser.add_argument("--template", type=str, default="v3", choices=list(TEMPLATES),
                        help="Prompt 模板版本（v3=R1 基线 / v3_1=R2 / v3_2=R3）")
    parser.add_argument("--live", action="store_true", help="真实 DeepSeek 模式（需 Key+网络）")
    parser.add_argument("--outfile", type=str, default="", help="评测结果 JSON 输出路径（可选）")
    args = parser.parse_args()

    # 指定实验模板：临时替换 ENGINES 中 fake_memory 的 build（进程内生效，不动引擎定义）
    from engines import ENGINES  # noqa: E402
    ENGINES["fake_memory"].build = TEMPLATES[args.template]

    # ---- 客户端：--live 且有 Key → DeepSeekClient；否则 Mock ----
    client, mode = None, "MOCK"
    if args.live:
        try:
            from deepseek_client import DeepSeekClient
            c = DeepSeekClient()
            if c.is_ready:
                client, mode = c, "LIVE"
            else:
                print("  ⚠️ --live 但 Key 为空，回退 Mock")
        except Exception as e:
            print(f"  ⚠️ DeepSeekClient 创建失败（{e}），回退 Mock")
    if client is None:
        client = MockClient(engine_name="fake_memory")

    # ---- 加载 anchors.json 取范本与 twistable_elements ----
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    print(f"\n模式={mode} · 模板={args.template} · trust_bias={args.trust} · 关卡={len(LEVELS)}")

    results = []
    for lv in LEVELS:
        aid = lv["anchor_id"]
        entry = anchors[aid]
        template = entry["revealed_text"]
        twistable = entry["llm_params"]["twistable_elements"]
        print(f"\n[关卡{lv['level']}] {aid}（辨识度 {lv['difficulty']:.0%}）")

        if getattr(client, "engine_name", None) == "fake_memory":
            print("  [mock] 固定 mock 数据，仅链路自检，不代表 LLM 质量")

        result = run_engine(client, "fake_memory",
                            template_text=template,
                            trust_bias=args.trust,
                            anchor_id=aid,
                            twistable_elements=twistable)
        if result is None:
            print("  ❌ 引擎调用失败（None）")
            results.append({"level": lv["level"], "anchor_id": aid, "error": "engine returned None"})
            continue

        ok_struct, errs = validate_schema(result, FAKE_MEMORY_V3_OUTPUT_SCHEMA, "fake_memory")
        check("① 结构合法（3 变体 + 枚举齐 + 字段全）", ok_struct, "; ".join(errs) or "")

        # Mock 数据是固定的通用文本（不随关卡/范本变化），②③④⑤ 实际评分无意义：
        # —— 只打印打分，不判 PASS/FAIL；① 结构仍判（mock 下也须合规）。
        scoring_enabled = mode == "LIVE"
        if not scoring_enabled:
            print("    [mock] ②③④⑤ 仅打印展示，不计入通过/失败（判分需 --live 真实数据）")

        variants = result["fake_variants"]
        for v in variants:
            vt = v["variant_type"]
            note = v["distortion_note"]
            text = v["variant_text"]
            ratio = SequenceMatcher(None, text, template).ratio()
            n_chars = len(text.replace(" ", "").replace("\n", ""))

            print(f"    —— {vt} ——（相似度 {ratio:.2f} · 长度 {n_chars} · note: {note[:36]}…）")
            in_twist = any(kw in note for kw in twistable)
            sim_min, sim_max = (SIM_MIN_MICRO, SIM_MAX_MICRO) if vt == "micro_drift" \
                else (SIM_MIN_NEG, SIM_MAX_NEG)
            if scoring_enabled:
                check(f"② {vt} 相似度 {ratio:.2f} ∈ [{sim_min},{sim_max}]（分级）",
                       sim_min <= ratio <= sim_max, f"ratio={ratio:.3f}")
                check(f"③ 扭曲点命中 {in_twist}（note 命中 twistable 关键词）",
                       in_twist,
                       f"note={note[:40]!r} / twistable={twistable}")
                check(f"④ 长度 {n_chars} ≥ {LEN_MIN}", n_chars >= LEN_MIN, f"len={n_chars}")
            v["_score"] = {
                "similarity": round(ratio, 4),
                "char_len": n_chars,
                "twistable_hit": in_twist,
                "scored": scoring_enabled,
            }

        # ⑤ 变体间一致性：三个变体两两不得雷同（=1.0 全同 → 三卡一模一样，玩家无从选择）
        if len(variants) == 3 and scoring_enabled:
            pairs = []
            for i in range(3):
                for j in range(i + 1, 3):
                    a, b = variants[i]["variant_text"], variants[j]["variant_text"]
                    full = SequenceMatcher(None, a, b).ratio()
                    pre = SequenceMatcher(None, a[:PAIR_PREFIX], b[:PAIR_PREFIX]).ratio()
                    pairs.append((variants[i]["variant_type"], variants[j]["variant_type"],
                                  round(full, 3), round(pre, 3)))
            ok = all(p[2] <= PAIR_MAX for p in pairs) and all(p[3] < 1.0 for p in pairs)
            detail = "; ".join(f"{p[0]}↔{p[1]} full={p[2]} pref={p[3]}" for p in pairs)
            check("⑤ 变体两两不同（full ≤ 0.98 且前 100 字不完全一致）", ok, detail)
            result["_variant_pair_similarity"] = pairs

        results.append({"level": lv["level"], "anchor_id": aid,
                        "difficulty": lv["difficulty"], "trust_bias": args.trust,
                        "mode": mode, "result": result})

    print("\n=== 汇总 ===")
    print(f"通过 {len(PASS)} / 失败 {len(FAIL)}（共 {len(PASS) + len(FAIL)} 项判分项）")
    for f in FAIL:
        print(f"  FAIL: {f}")
    if mode == "MOCK":
        print("  ⚠️ MOCK 模式：仅①结构判分（②③④ mock 不判分）；请用 --live 复跑得到真实 LLM 质量分。")

    if args.outfile:
        Path(args.outfile).write_text(
            json.dumps({"mode": mode, "trust_bias": args.trust, "results": results},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"结果已写入 {args.outfile}")
    return {"mode": mode, "trust_bias": args.trust, "results": results,
            "pass_count": len(PASS), "fail_count": len(FAIL)}


if __name__ == "__main__":
    run()
