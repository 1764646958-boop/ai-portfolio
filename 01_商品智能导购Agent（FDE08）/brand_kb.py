# -*- coding: utf-8 -*-
"""澄初个人护理 品牌知识库 —— 08题 唯一事实来源（单一事实源）

所有产品事实、价格、组合、边界规则集中于此。rules.py(定性决策)与 nl.py(措辞/校验)
只从这里读取，禁止在别处硬编码价格或产品。

字段：sku / name / spec / price / category / features / efficacy / skin_type / limits / risky
"""

# 品牌定位（官方口径，不可违背）
BRAND = {
    "name": "澄初",
    "positioning": "用清晰、克制的产品信息，帮助顾客做适合自己的日常护理选择。",
    "principles": [
        "先了解需求，再提出选择；不制造焦虑，不夸大效果，不强推连带购买。",
        "沟通语气温和、具体、尊重顾客决定；多用「可以考虑」「如果您在意……」等表达。",
        "手册未提供的信息（促销、赠品、线上渠道价格、退换货、渠道授权政策）一律不得编造，应说明「需要向门店或系统确认」。",
    ],
    "forbidden_claims": [
        "不得说「治愈、治疗、保证有效、绝对不过敏、马上见效」等承诺。",
        "不对价格、赠品、退换或授权作无依据承诺。",
        "不作医疗诊断；顾客提到明显不适、受损或持续问题时，建议其停止刺激性尝试并咨询专业人士（保持温和，不制造恐慌）。",
        "不贬低、不评价其他品牌；只介绍澄初，不横向对比竞品。",
    ],
}

# 产品目录
PRODUCTS = [
    {"sku": "P101", "name": "云感氨基酸舒润洁面乳", "spec": "150ml", "price": 169,
     "category": "洁面乳·氨基酸温和", "features": "无香型、低泡、洗后易冲净",
     "efficacy": "温和清洁、舒润不紧绷", "skin_type": "偏干/敏感倾向可考虑",
     "limits": "个体差异，首次使用建议局部测试", "risky": False},
    {"sku": "P102", "name": "净澈控油洁面啫喱", "spec": "150ml", "price": 149,
     "category": "洁面啫喱·控油清爽", "features": "清洁感较强、带香味",
     "efficacy": "净澈控油、清爽", "skin_type": "偏油、偏好清爽肤感者",
     "limits": "对香味敏感者不优先推荐", "risky": False},
    {"sku": "P201", "name": "焕亮果酸细致精华液", "spec": "30ml", "price": 229,
     "category": "功效精华·含果酸(去角质/焕亮)", "features": "含 8% 果酸复合成分",
     "efficacy": "焕亮、细致、改善粗糙", "skin_type": "有焕肤经验、状态稳定、希望改善粗糙者",
     "limits": "敏感、受损或正在不适的皮肤不推荐；需注意防晒；不承诺治疗效果；使用前先确认是否有敏感/不适与既往使用经验",
     "risky": True,  # 高浓度果酸 → 敏感边界(BC-6)核心触发点
     "precheck": "先确认：皮肤状态正常吗？之前用过果酸/焕肤类吗？"},
    {"sku": "P202", "name": "屏护神经酰胺保湿乳", "spec": "50ml", "price": 259,
     "category": "保湿乳·神经酰胺屏障", "features": "无香型、含神经酰胺类保湿成分",
     "efficacy": "保湿、屏护、修护屏障", "skin_type": "干燥、屏障脆弱倾向可考虑",
     "limits": "不承诺治疗/修复；明显不适建议咨询专业人士", "risky": False},
    {"sku": "P203", "name": "水漾轻盈保湿凝露", "spec": "50ml", "price": 219,
     "category": "保湿凝露·轻盈清爽", "features": "清爽质地、带淡香",
     "efficacy": "轻盈保湿、清爽", "skin_type": "偏油、喜欢轻薄肤感者",
     "limits": "对香味敏感者不优先推荐", "risky": False},
    {"sku": "P301", "name": "随行旅行分装瓶礼盒", "spec": "4 个可重复使用小瓶", "price": 49,
     "category": "配件礼盒·非护肤功效", "features": "可重复使用的旅行分装瓶，不属于护肤功效产品",
     "efficacy": "非护肤功效（仅便携分装）", "skin_type": "-",
     "limits": "仅当顾客明确提及出差/旅行携带需求时再连带推荐；先确认预算与偏好", "risky": False},
]

# 唯一允许的组合（手册）
COMBOS = [
    {"items": ["P101", "P202"], "total": 428, "label": "洁面 + 保湿乳 基础护理",
     "for": "偏干、敏感倾向、希望简单护理的顾客"},
    {"items": ["P102", "P203"], "total": 368, "label": "控油洁面 + 清爽凝露 组合",
     "for": "偏油、可接受香味、喜欢清爽感的顾客"},
]

# 敏感性关键词 / 风险提示
P201_SOLO_NOTE = "P201 精华液可单独讨论，不强行捆绑组合。"
P301_COMBO_RULE = "P301 旅行分装瓶礼盒：顾客未提及出差/旅行时，回答中不得出现 P301、旅行装、便携分装等字样，也不得做「如果以后出差/旅行…」之类假设性引导；仅当顾客明确提到出差/旅行场景时介绍（¥49），可作连带推荐，不与护肤组合强行捆绑。"
SENSITIVE_NOTE = "顾客提到明显不适、受损、持续问题或疑似症状时：不推荐刺激性产品（尤其 P201 果酸精华），建议停止刺激性尝试，温和建议咨询专业人士；不诊断。"

# 场景政策（官方口径：未提供 → 一律需向门店或系统确认）
POLICY = {
    "sensitive_discomfort": SENSITIVE_NOTE,
    "online_price": "顾客问「网上更便宜 / 线上什么价」：手册未提供线上渠道价格与保价政策，不得编造或承诺同价；如实说明需要向门店或系统确认，可提示以官方门店/系统信息为准，不贬低线上。",
    "promo_gift": "顾客问促销、折扣、赠品、满减：手册未提供促销与赠品政策，不得编造，统一回应「需要向门店或系统确认」，可建议留意门店或官方信息。",
    "return_policy": "顾客问退换货：手册未提供退换货政策，不得编造，回应需要向门店或系统确认。",
    "travel": "顾客提到出差、旅行、出门、便携、分装、小样、旅行装等词时，立即识别为旅行场景，不再纠缠肤质：若只缺便携容器 → 直接介绍 P301 ¥49；若想为旅行购买护肤品 → 先问 1 个关键问题再按肤质推荐，并可在确认后连带 P301；预算内明确报 ¥49。",
    "medical": "涉及功效性/医疗表述（祛痘、痘印、祛斑、湿疹、过敏治疗等）：产品为日常护理用品，不承诺治疗效果，不说「治疗/治愈/根除」；若皮肤问题明显或持续，温和建议咨询专业人士。",
}

# 追问维度与原则
QUESTIONING = {
    "max_per_turn": 2,
    "principle": "信息不足时只追问当前最关键的问题（最多 2 个），不一次抛出大量问题；顾客回答后逐步收敛，目标是在少量对话轮次内给出建议。",
    "dimensions": ["肤质/感受（干/油/敏感/是否不适）", "使用目的（清洁/保湿/改善粗糙）", "预算范围", "是否介意香味", "使用经验（尤其涉及 P201 时）", "场景（日常/旅行）"],
}

# 允许出现的所有价格（用于输出校验）
ALL_PRICES = sorted({p["price"] for p in PRODUCTS} | {c["total"] for c in COMBOS})  # [49,149,169,219,229,259,368,428]
BY_SKU = {p["sku"]: p for p in PRODUCTS}


def buy(sku):  # 便捷
    return BY_SKU[sku]


def price_of(*skus):
    return sum(BY_SKU[s]["price"] for s in skus)


def combo_total(items):
    items = list(items)
    for c in COMBOS:
        if sorted(c["items"]) == sorted(items):
            return c["total"]
    return price_of(*items)  # 非手册组合按单品价精确相加


def build_product_lines():
    return "\n".join(
        f"- {p['sku']} {p['name']} {p['spec']}，¥{p['price']}。特点：{p['features']}。功效：{p['efficacy']}。适合：{p['skin_type']}。注意：{p['limits']}"
        for p in PRODUCTS
    )


def build_combo_lines():
    return "\n".join(
        f"- {c['items'][0]} + {c['items'][1]} = ¥{c['total']}（{c['for']}；{c['label']}）" for c in COMBOS
    )
