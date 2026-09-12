# -*- coding: utf-8 -*-
"""agent.py —— 编排层：把规则的"决策"与 LLM 的"理解/措辞"缝合起来。

核心承诺：
  1. 无论有没有网络 / API key，回复都先由 rules.py 确定性决定；
  2. 只对"非高光态"尝试 LLM 意图补全 + 措辞；任何一步失败都回退硬模板/事实句；
  3. 价格、合规、升级判断永不经过 LLM。
"""
import os
import brand_kb as kb
import rules
import nl


MODEL = nl.MODEL
# 离线模式：强制走硬模板，适合无网/无 key 演示或单测
OFFLINE = os.environ.get("CHENGCHU_OFFLINE", "").strip() == "1"

# 这些状态只走确定性模板，不让 LLM 自由发挥（避免越权/改语气/编政策）
HARD_STATES = {"INJECTION", "SENSITIVE", "MEDICAL", "POLICY", "P201_FLOW"}


# ---- 对话上下文取用 ----
def _turn_texts(messages):
    return [m.get("content", "") for m in messages if m.get("role") == "user"]


def _all_user_text(messages):
    return "\n".join(_turn_texts(messages))


def _last_user_text(messages):
    allu = _turn_texts(messages)
    return allu[-1] if allu else ""


# ---- 把 LLM 意图与确定性信号合并（LLM 只用于补全，不覆盖关键门控） ----
def _merge(s, intent):
    out = dict(s)
    # 用户没明说的维度，用 LLM 的理解补上；但"敏感/医学/政策/注入"这类红线
    # 以确定性关键词为准（宁可漏、不可误杀风险误报造成越权），所以只做"或"融合。
    for k in ("cleanse", "moisture", "brighten", "travel", "policy",
              "sensitive", "medical", "off_topic", "injection", "senskin", "noexp"):
        if not out.get(k) and intent.get(k):
            out[k] = True
    # 肤质：确定性没判出，才参考 LLM
    if out.get("skin") in (None, "unknown") and intent.get("skin") in ("oily", "dry", "sensitive"):
        out["skin"] = intent["skin"]
        if intent["skin"] == "sensitive":
            out["senskin"] = True
        elif intent["skin"] == "oily":
            out["oily"] = True
        elif intent["skin"] == "dry":
            out["dry"] = True
    if out.get("budget") is None and intent.get("budget"):
        out["budget"] = intent["budget"]
    return out


def chat(messages, temperature=0.0):
    """核心入口。返回文本回复。messages 形如 [{"role","content"}...]。"""
    return _run(messages, use_llm=not OFFLINE)


def _run(messages, use_llm):
    allu = _all_user_text(messages)
    last = _last_user_text(messages)
    s = rules.detect(allu)  # 累积上下文判定 → 旅行/敏感等状态可跨轮维持

    # 1) 确定性路由
    state = rules.route(s)

    # 2) LLM 意图补全（仅非高光态 & 有 key & 非离线）
    intent = {}
    if use_llm and state not in HARD_STATES:
        intent = nl.extract_intent(last)  # 只抽最新一句的新槽，防历史混淆
        s = _merge(s, intent)

    # 3) 决策（一次），拿到"终态" fstate —— CLARIFY 可能升级为 RECOMMEND
    d = rules.decide(state, s)
    fstate = d["state"]

    # 4) 红线态，或未启用 LLM → 永远只走确定性模板，绝不外发未见后端的文本
    if fstate in HARD_STATES or not use_llm:
        return rules.render(fstate, d)

    # 5) 需要澄清 / 无产品 → 模板
    if fstate in ("CLARIFY", "OFFTOPIC") or not d.get("products"):
        return rules.render(fstate, d)

    # 6) 否则：事实句 + 可选（严格校验的）LLM 润色
    basics = nl.word_reply(d)
    if basics is None:
        return rules.render(fstate, d)
    polished = nl.polish_reply(basics)
    return polished if polished is not None else basics


def trace(text):
    """透视：返回【最终决策状态】(而非粗路由)，供前端"决策面板"展示。

    注意：CLARIFY 若信息已足够，decide() 会升级为 RECOMMEND，这里报真实终态。
    """
    s = rules.detect(text)
    state = rules.route(s)
    d = rules.decide(state, s)
    return {
        "state": d["state"],  # 终态（可能从 CLARIFY 升级为 RECOMMEND）
        "routed_state": state,  # 粗路由（用于对比，看是否发生了澄清→推荐）
        "signals": s,
        "products": d.get("products"),
        "total": d.get("total"),
        "reason": d.get("reason"),
        "tradeoff": d.get("tradeoff"),
        "budget_ok": d.get("budget_ok"),
        "question": d.get("question"),
    }


def sanity_ping():
    """自检：模块能导入、规则能跑。返回 dict。"""
    try:
        s = rules.detect("我皮肤容易泛红，想保湿")
        st = rules.route(s)
        return {"ok": True, "state": st, "model": MODEL, "offline": OFFLINE,
                "api_key": bool(nl.API_KEY)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
