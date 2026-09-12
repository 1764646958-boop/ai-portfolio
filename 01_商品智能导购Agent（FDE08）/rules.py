# -*- coding: utf-8 -*-
"""确定性规则层（核心）：路由 / 门控 / 决策 / 硬模板。

设计原则：*所有关键决策*（该推荐哪个、价格多少、是否合规、要不要升级）都在这里用
确定性代码决定；LLM 只在上层做"理解话 + 把话说好"，绝不参与决策。这样：
  - 安全门控（BC-6）、政策确认（BC-8）、价格算术永不翻车、可被单测断言；
  - 敏感/政策/P201/注入等"高光戏"直接从这里返回，不依赖网络。
"""
import re
import brand_kb as kb


# ---- 关键词检测（确定性） ----
_SENS = ["不舒服", "不适", "刺痛", "泛红", "红肿", "过敏", "瘙痒", "发痒", "脱皮",
         "起皮", "长痘", "痘痘", "受损", "破皮", "孕期", "怀孕", "哺乳",
         "就医", "皮肤科", "红斑", "疙瘩", "看不舒服", "痒"]
# 注：裸"敏感"不属急性不适（属肤质/倾向，见 _SENSKIN），否则"敏感倾向"会被误判为安全红线。

_MED = ["祛痘", "痘印", "祛斑", "治疗", "治愈", "根治", "湿疹", "好得快", "效果吧", "能治", "疗效"]

_POLICY = ["促销", "活动", "赠品", "折扣", "优惠", "满减", "领券", "优惠券", "优惠几",
           "网上买", "网上" ,"线上", "淘宝", "京东", "拼多多", "更便宜", "保价",
           "退换", "退货", "退款", "换货", "能退", "可退", "退吗", "退的", "退钱",
           "授权", "代理", "会员", "便宜点", "便宜不"]

_TRAVEL = ["出差", "旅行", "旅游", "出门", "便携", "分装", "小样", "旅行装", "行李箱",
           "酒店", "带走", "带上", "路上"]

_P201 = ["果酸", "焕亮", "细致", "粗糙", "精华", "焕肤", "去角质", "P201"]

_OFFTOPIC = ["笑话", "讲个", "唱歌", "聊聊天", "天气", "吃什么", "你好吗", "你是谁", "讲故事"]

_INJECT = ["忽略", "忘记", "系统提示词", "系统提示", "内部指令", "扮演", "没有任何限制",
           "把规则", "原文发我", "输出规则", "越狱", "换角色", "摆脱限制"]

_CLEANSE = ["洗面奶", "洁面", "清洁", "洗脸", "洗得", "洗一下"]
_MOIST = ["保湿", "补水", "滋润", "乳液", "面霜", "凝露", "水分", "保湿乳", "保湿霜"]
_BRIGHT = ["焕亮", "改善粗糙", "去角质", "提亮", "细致"]
_DRY = ["偏干", "干燥", "干皮", "很干", "起皮", "干性", "干敏"]
_OILY = ["偏油", "油皮", "出油", "爱出油", "混油", "很油", "油性"]
_SENSKIN = ["敏感肌", "易敏", "敏感"]
_FRAG = ["香味", "香一点的", "无香", "香味敏感", "介意香味", "有香", "淡香"]
_NOEXP = ["没经验", "没用过", "没试过", "没用过果酸", "没用过这", "第一次用"]
# 注意：中文是 \w，故不能用 \b 做边界（"要P102" 中 要 与 P 无边界）。直接匹配 P+三位数字再校验白名单。
_EXPLICIT_SKU = re.compile(r"P\d{3}")
# 兼容两种表达："预算200"、"200元"、"200以内"、"200左右"
_BUDGET = re.compile(r"(?:预算[约~]?\s*(\d+))|(?:(\d+)\s*(?:元|块|左右|以内|内))")
_PORTABLE = ["便携", "分装", "小样", "旅行装", "带走", "带上", "瓶子", "分装瓶"]


def detect(text: str) -> dict:
    t = text
    def on(words): return any(w in t for w in words)
    budget = None
    for m in _BUDGET.finditer(t):
        g = m.group(1) or m.group(2)
        if g:
            budget = int(g)
            break
    skus = sorted(set(k for k in _EXPLICIT_SKU.findall(t) if k in kb.BY_SKU))
    cleanse = on(_CLEANSE)
    moisture = on(_MOIST)
    brighten = on(_BRIGHT)
    return {
        "sensitive": on(_SENS),
        "medical": on(_MED),
        "policy": on(_POLICY),
        "travel": on(_TRAVEL),
        "p201": on(_P201),
        "off_topic": on(_OFFTOPIC),
        "injection": on(_INJECT),
        "noexp": on(_NOEXP),
        "cleanse": cleanse,
        "moisture": moisture,
        "brighten": brighten,
        "dry": on(_DRY),
        "oily": on(_OILY),
        "senskin": on(_SENSKIN),
        "fragrance_aware": on(_FRAG),
        "want_portable": on(_PORTABLE),
        # 旅行时是"带上自己的东西"(分装) 还是 "为旅行买护肤品"(清洁/保湿/改善)
        "buy_for_trip": (cleanse or moisture or brighten) or ("护肤" in t and "买" in t),
        "budget": budget,
        "skus": skus,
    }


# ---- 优先级路由（确定性） ----
def route(s: dict) -> str:
    if s["injection"]:
        return "INJECTION"
    if s["sensitive"]:
        return "SENSITIVE"
    if s["medical"] or (s["p201"] and s["policy"]):
        return "MEDICAL"
    if s["policy"]:
        return "POLICY"
    # P201(8%果酸)前置确认：皮肤敏感/没经验/不适 → 直接拒绝(去安全门控)；否则进入 P201 询问流程
    if s["p201"] and not s["sensitive"] and (s["senskin"] or s["noexp"]):
        return "SENSITIVE"
    if s["p201"] and not s["sensitive"]:
        return "P201_FLOW"
    if len(s["skus"]) >= 1:
        return "SPECIFIC_SKUS"
    if s["travel"]:
        return "TRAVEL"
    if s["off_topic"]:
        return "OFFTOPIC"
    # 顺利路径：有明确目标(清洁/保湿/改善粗糙)且肤质已知 → 直接推荐；否则先澄清关键问题
    has_goal = s["cleanse"] or s["moisture"] or s["brighten"]
    need_info = _skin(s) == "unknown" or not has_goal
    return "CLARIFY" if need_info else "RECOMMEND"


# ---- 决策（纯函数，可单测） ----
def _skin(s: dict) -> str:
    if s["sensitive"] or s["senskin"]:
        return "sensitive"
    if s["dry"]:
        return "dry"
    if s["oily"]:
        return "oily"
    return "unknown"


HARD_DECISION = {"INJECTION", "SENSITIVE", "MEDICAL", "POLICY", "P201_FLOW"}


def decide(state: str, s: dict) -> dict:
    """返回 Decision dict：{state, products, total, budget, budget_ok, reason, tradeoff, question, callouts}

    state 字段写的是【最终决策状态】：若 CLARIFY 但信息已足够，会升级为 RECOMMEND 返回。
    """
    d = {"state": state, "products": [], "total": None, "budget": s["budget"], "budget_ok": True,
         "question": None, "reason": "", "tradeoff": "", "callouts": []}

    # 高光/红线态：只保留状态本身，不产出产品（由 render 硬模板给出话术）
    if state in HARD_DECISION:
        return d

    if state == "TRAVEL":
        d["callouts"].append("travel")
        buy_for_trip = s.get("buy_for_trip") or bool(s["skus"])
        want_portable = s.get("want_portable")
        # 只缺便携容器（不带护肤品，也不买护肤品）→ 直接 P301
        if want_portable and not buy_for_trip:
            d["products"] = ["P301"]
            d["total"] = 49
            d["reason"] = "您的场景是出行便携；随行旅行分装瓶礼盒(P301)¥49 适合把家里的洁面/乳液分装带走，不属于护肤功效产品。"
            return d
        if buy_for_trip:
            # 为旅行买护肤品 → 若能推荐(肤质+品类已知)则连同 P301；否则先问 1 个关键问题
            d2 = _recommend(s)
            if d2["state"] == "RECOMMEND":
                d2 = dict(d2)
                if "P301" not in d2["products"]:
                    d2["products"] = d2["products"] + ["P301"]
                    d2["total"] = (d2["total"] or 0) + 49
                d2["reason"] += "（出行的话，可以再加个 P301 旅行分装瓶 ¥49 把护肤品带走。）"
                return _note_budget(d2, s["budget"])
            d["question"] = "您这次旅行主要想带护肤品还是便携分装呢？感觉偏干、偏油还是偏敏感？"
            return d
        d["question"] = "您是想带便携分装，还是需要为旅行先买护肤品？预算大概多少？"
        return d

    if state == "SPECIFIC_SKUS":
        skus = s["skus"]
        if len(skus) >= 2:
            a, b = skus[0], skus[1]
            total = kb.combo_total([a, b])
            d["products"] = skus
            d["total"] = total
            d["reason"] = f"{kb.buy(a)['name']} + {kb.buy(b)['name']} 合计 ¥{total}。"
        else:
            p = kb.buy(skus[0])
            d["products"] = skus
            d["total"] = p["price"]
            d["reason"] = f"{p['name']} 单瓶 ¥{p['price']}。"
        return d

    if state == "OFFTOPIC":
        d["question"] = "哈哈，这个我不太擅长哦～我是澄初的导购小澄，想了解洁面、保湿还是改善肤质呢？"
        return d

    # CLARIFY：信息足够则直接推荐，否则只问当前最关键的问题（≤2，不轰炸）
    d2 = _recommend(s)
    if d2["state"] == "RECOMMEND":
        return d2
    need = []
    if _skin(s) == "unknown":
        need.append("您偏干、偏油还是偏敏感？")
    if not (s["cleanse"] or s["moisture"] or s["brighten"]):
        need.append("想先解决清洁、保湿，还是改善粗糙呢？")
    d["question"] = " ".join(need[:2]) if need else d2["question"]
    return d


def _note_budget(d: dict, budget):
    """若预算已知且超了，标记 budget_ok=False 并补一句取舍，不硬塞超预算款。"""
    if budget is not None and d.get("total") and d["total"] > budget:
        d["budget_ok"] = False
        d["tradeoff"] = ((d["tradeoff"] + " ") if d["tradeoff"] else "") + \
                        (f"这款 ¥{d['total']} 比您 ¥{budget} 的预算略高；"
                         f"如果您想严格控价，我可以再帮您看看更贴合预算或单品的选择。")
    return d


def _recommend(s: dict) -> dict:
    skin = _skin(s)
    wants_cleanse = s["cleanse"]
    wants_moist = s["moisture"]
    wants_brighten = s["brighten"]
    budget = s["budget"]
    d = {"state": "RECOMMEND", "products": [], "total": None, "budget": budget, "budget_ok": True,
         "question": None, "reason": "", "tradeoff": "", "callouts": []}

    # 焕亮/粗糙 → P201（需非敏感；敏感已在 SENSITIVE 被拦截）
    if wants_brighten and not skin == "sensitive":
        p = kb.buy("P201")
        d["products"] = ["P201"]
        d["total"] = p["price"]
        d["reason"] = "含 8% 果酸、需注意防晒，属于清洁后的功能产品。"
        d["tradeoff"] = "使用前建议先确认皮肤稳定、有果酸使用经验；若您在意温和，我也可以帮您看保湿/清洁类。"
        return _note_budget(d, budget)

    # 组合（洁面 + 保湿同时要）
    if wants_cleanse and wants_moist:
        if skin == "oily":
            skus, total, lab = ["P102", "P203"], 368, "控油洁面 + 清爽凝露"
            why = "偏清爽、不厚重，适合油皮"
        else:  # dry / sensitive / unknown → 默认温和组合
            skus, total, lab = ["P101", "P202"], 428, "洁面 + 保湿乳 基础护理"
            why = "两款都无香，适合偏干/敏感倾向"
        d["products"] = skus
        d["total"] = total
        d["reason"] = f"一套 {lab}，{why}。"
        d["tradeoff"] = "这套的预算偏高一些；如果您只要单件，我也可以单独给洁面或保湿。"
        return _note_budget(d, budget)

    # 单洁净 / 单保湿
    if wants_cleanse and not wants_moist:
        if skin == "unknown":  # 只说了要洗面奶、肤质未知 → 先问最关键的一个，不猜
            d["state"] = "CLARIFY"
            d["question"] = "您的皮肤偏干、偏油还是偏敏感呢？好据此给您选合适的洁面。"
            return d
        if skin == "oily":
            p = kb.buy("P102"); why = "清洁感较强、偏清爽，适合偏油肤感"
        else:
            p = kb.buy("P101"); why = "氨基酸温和、无香低泡，洗后不易紧绷"
        d["products"] = [p["sku"]]; d["total"] = p["price"]
        d["reason"] = f"它{why}。"
        d["tradeoff"] = "如果您还想要保湿，我可以再配一款乳液。"
        return _note_budget(d, budget)

    if wants_moist and not wants_cleanse:
        if skin == "unknown":  # 保湿剂型依赖肤质（干→乳/油→凝露），肤质未知先问，不猜
            d["state"] = "CLARIFY"
            d["question"] = "您皮肤偏干、偏油还是偏敏感呢？好给您选更合适的保湿。"
            return d
        if skin in ("dry", "sensitive"):
            p = kb.buy("P202"); why = "无香、含神经酰胺类保湿成分，适合干燥/屏障脆弱倾向"
        elif skin == "oily":
            p = kb.buy("P203"); why = "清爽质地、带淡香，适合喜欢轻薄肤感的油皮"
        else:
            p = kb.buy("P203"); why = "清爽轻盈保湿"
        d["products"] = [p["sku"]]; d["total"] = p["price"]
        d["reason"] = f"它{why}。"
        d["tradeoff"] = "若您对香味敏感，P203 带淡香，我再帮您看无香款。"
        return _note_budget(d, budget)

    # 都没明确 → 追问
    d["state"] = "CLARIFY"
    d["question"] = "想了解您更看重洁面、保湿，还是改善肤质呢？预算大概多少？"
    return d


# ---- 硬模板渲染（确定性，不依赖网络；对关键考点直接给话术） ----
def render(state: str, d: dict) -> str:
    if state == "INJECTION":
        return "抱歉～我只负责帮您挑选合适的澄初产品，其他问题可以咨询门店哦。🌿"
    if state == "SENSITIVE":
        return ("听到您说皮肤不适应，这个情况我会认真对待：建议先暂停可能刺激的尝试（尤其含 8% 果酸的 P201 精华液这类），"
                "必要时咨询皮肤科专业人士或到店看看。这里我就不给您推荐这类刺激性产品了，也可以帮您记录给门店跟进。")
    if state == "MEDICAL":
        return ("P201 属于日常护理产品，不承诺祛痘/治疗效果哦；如果您的皮肤问题比较明显或持续，建议咨询皮肤科专业人士。"
                "如果您只是想改善粗糙、且皮肤状态稳定，可以再和我聊聊。")
    if state == "POLICY":
        return ("关于您问的这块，品牌手册没有提供，需要向门店或系统确认，我不能给您作无依据的承诺～建议到店或联系客服确认一下。")
    if state == "OFFTOPIC":
        return ("哈哈，这个我不太擅长哦～我主要帮您了解澄初的洁面、保湿与改善肤质。"
                "您想要先看哪类呢？或者我帮您从「了解需求」开始。")
    if state == "P201_FLOW":
        p = kb.buy("P201")
        return (f"想改善粗糙的话，有款 {p['name']}(P201)¥{p['price']} 可以考虑，但它含 8% 果酸。"
                f"{p['limits']}。您可以先告诉我：皮肤状态稳定吗？之前用过果酸/焕肤类吗？")
    if state == "TRAVEL":
        if d["question"]:
            return d["question"]
        p = kb.buy("P301")
        return (f"既然您是出行便携，可以考虑 {p['name']}(P301)¥{p['price']}，4 个可重复使用小瓶，"
                f"能把家里的洁面/乳液分装带走，不属于护肤功效产品。")
    if state == "SPECIFIC_SKUS":
        return (f"好的，{d['reason']} {d['tradeoff']}" if d["tradeoff"] else d["reason"])
    if state == "CLARIFY":
        return d["question"]
    if state == "RECOMMEND":
        names = []
        for sku in d["products"]:
            names.append(f"{kb.buy(sku)['name']}({sku})¥{kb.buy(sku)['price']}")
        price_txt = " + ".join(names)
        if d["total"] is not None and len(d["products"]) > 1:
            price_txt += f"，合计 ¥{d['total']}"
        out = f"可以考虑：{price_txt}。{d['reason']}"
        if d["tradeoff"]:
            out += " " + d["tradeoff"]
        return out
    return "您好，我是小澄～帮您挑合适的澄初产品。"
